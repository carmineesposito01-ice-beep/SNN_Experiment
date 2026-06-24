"""
core/eventprop.py -- EventProp adjoint per CF_FSNN
====================================================

Implementazioni mantenute (post-pulizia 2026-06-01 dopo audit utente):

  * LIFLayer_EventProp       -- LIF feedforward semplice (F2.0b). Reference LIF
                                con tau_s synaptic, no delays, no Po2.
                                Usata SOLO come reference "LIF puro che funziona".

  * ALIFLayer_EventProp_Full -- LA TUA architettura A1 con EventProp adjoint:
                                * Po2 quantization (STE in backward via PowerOf2Quantize)
                                * max_delay=6 delayed synapses
                                * n_ticks=10 internal ticks per sequence step
                                * Bit-shift leak (α_m = 7/8), NO synaptic current I
                                * Adaptive threshold ALIF (base_th + fatigue learnable)
                                * Low-rank recurrence rec_U @ rec_V
                                * Soft reset V -= s · V_th_eff
                                Confronto fair vs CF_FSNN_Net baseline (stessa arch,
                                solo training method diverso).

  * LILayer_Standard         -- LI output con dt/tau leak (per F2.0b semplice).

  * LILayer_BitShift_Po2     -- LI output con bit-shift leak (V/8) + Po2 quantization.
                                Matcha baseline OutputLayer_LI per F2.1-full.

Pattern: torch.autograd.Function custom con manual_forward + manual_backward.
Vedi document/EVENTPROP_DESIGN.md per math + decisioni progettuali.

CLEANUP 2026-06-01:
  * Rimosso LIFLayer_EventProp_Recurrent + wrapper (F2.2 era stripped, no Po2 no delays)
  * Rimosso ALIFLayer_EventProp + wrapper (F2.1 stripped, no Po2 no delays)
  Erano architetture "fake" che non replicavano A1 in modo fair. Sostituiti
  da ALIFLayer_EventProp_Full che invece replica A1 al 100% architetturalmente.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

from core.hardware import po2_quantize


# ===========================================================
# WrapperFunction generico (LIF F2.0b)
# ===========================================================

class _EventPropWrapper(torch.autograd.Function):
    """Wrapper per LIFLayer_EventProp (2 grad: input, weight)."""

    @staticmethod
    def forward(ctx, input, weight, forward_fn, backward_fn):
        ctx.backward_fn = backward_fn
        saved, output = forward_fn(input, weight)
        ctx.save_for_backward(*saved)
        return output

    @staticmethod
    def backward(ctx, grad_output):
        saved = ctx.saved_tensors
        grad_input, grad_weight = ctx.backward_fn(grad_output, *saved)
        return grad_input, grad_weight, None, None


# ===========================================================
# LIFLayer_EventProp -- F2.0b reference (LIF puro feedforward)
# ===========================================================

class LIFLayer_EventProp(nn.Module):
    """LIF semplice EventProp -- REFERENCE LIF (F2.0b).

    Discretizzazione:
        I[t] = (1 - dt/tau_s) * I[t-1] + W @ x[t-1]
        V[t] = (1 - dt/tau_m) * V[t-1] + (dt/tau_m) * I[t-1]
        s[t] = (V[t] > V_th).float()
        V[t] <- V[t] * (1 - s[t])     hard reset

    Adjoint (Wunderlich&Pehle 2021):
        lV[t-1] = alpha_m * lV[t] + s[t] * (lV[t]+grad_out[t])/(I[t-1]-V_th+eps)
        lI[t-1] = lI[t] + (dt/tau_s) * (lV[t] - lI[t])
        grad_W -= x[t] outer lI[t]
        grad_input[t] = (lV[t+1] - lI[t+1]) @ W

    Args:
        dt=1e-2, mu_init=0.5: defaults post F2.0 -> F2.0b fix (encoding stabile).

    Reference uses: NO recurrence, NO delays, NO Po2, NO bias, NO adaptive threshold.
    """

    def __init__(self, in_features, out_features,
                 tau_m=2e-2, tau_s=1e-2, dt=1e-2, v_th=1.0,
                 mu_init=0.5, eps=1e-3, silent_repair=True):
        super().__init__()
        self.in_features  = in_features
        self.out_features = out_features
        self.tau_m = tau_m
        self.tau_s = tau_s
        self.dt    = dt
        self.v_th  = v_th
        self.eps   = eps
        self.silent_repair = silent_repair

        self.alpha_m = 1.0 - dt / tau_m
        self.alpha_s = 1.0 - dt / tau_s
        self.beta_m  = dt / tau_m

        self.weight = nn.Parameter(torch.Tensor(out_features, in_features))
        nn.init.normal_(self.weight, mean=0.0, std=mu_init)

    def _manual_forward(self, input, weight):
        B, T, _ = input.shape
        device = input.device
        out_dim = self.out_features
        V = torch.zeros(B, T, out_dim, device=device)
        I = torch.zeros(B, T, out_dim, device=device)
        s = torch.zeros(B, T, out_dim, device=device)
        for repair_iter in range(5):
            V.zero_(); I.zero_(); s.zero_()
            for t in range(1, T):
                I[:, t] = self.alpha_s * I[:, t-1] + F.linear(input[:, t-1], weight)
                V[:, t] = self.alpha_m * V[:, t-1] + self.beta_m * I[:, t-1]
                fired = (V[:, t] > self.v_th).float()
                s[:, t] = fired
                V[:, t] = V[:, t] * (1.0 - fired)
            if self.training and self.silent_repair and repair_iter < 4:
                is_silent = s.sum(dim=(0, 1)) == 0
                if is_silent.any():
                    with torch.no_grad():
                        weight.data[is_silent] = weight.data[is_silent] + 0.1
                    continue
            break
        return (input, I, s), s

    def _manual_backward(self, grad_output, input, I, post_spikes):
        B, T, in_dim = input.shape
        out_dim = self.out_features
        device = input.device
        lV = torch.zeros(B, T, out_dim, device=device)
        lI = torch.zeros(B, T, out_dim, device=device)
        grad_input = torch.zeros(B, T, in_dim, device=device)
        grad_weight = torch.zeros(B, out_dim, in_dim, device=device)
        for t in range(T - 2, -1, -1):
            delta = lV[:, t+1] - lI[:, t+1]
            grad_input[:, t] = F.linear(delta, self.weight.t())
            denom = I[:, t] - self.v_th
            denom = torch.where(denom.abs() < self.eps,
                                torch.sign(denom + 1e-12) * self.eps, denom)
            jump = post_spikes[:, t+1] * (lV[:, t+1] + grad_output[:, t+1]) / denom
            lV[:, t] = self.alpha_m * lV[:, t+1] + jump
            lI[:, t] = lI[:, t+1] + (self.dt / self.tau_s) * (lV[:, t+1] - lI[:, t+1])
            grad_weight -= lI[:, t].unsqueeze(2) * input[:, t].unsqueeze(1)
        return grad_input, grad_weight.sum(dim=0)

    def forward(self, input):
        return _EventPropWrapper.apply(
            input, self.weight, self._manual_forward, self._manual_backward)


# ===========================================================
# LIFLayer_BPTT_Simple -- gemello BPTT di LIFLayer_EventProp
# ===========================================================
# Per fair-compare 2x2 (BPTT vs EventProp) × (LIF vs ALIF), serve la versione
# BPTT della LIF semplice. STESSE dinamiche di LIFLayer_EventProp (synaptic
# current I + tau_s/tau_m, hard threshold V_th=1, hard reset), ma forward
# autograd-tracked e spike via SurrogateSpike_Hardware (gradient flow standard).
#
# NO custom torch.autograd.Function. NO EventProp adjoint. Solo BPTT puro.
# I parametri (weight init, alpha_m, alpha_s, dt) sono IDENTICI a
# LIFLayer_EventProp per garantire stesso modello, solo metodo di training diverso.

from core.hardware import spike_fn   # SurrogateSpike_Hardware.apply


class LIFLayer_BPTT_Simple(nn.Module):
    """LIF semplice con BPTT + SurrogateSpike. Gemello di LIFLayer_EventProp.

    Discretizzazione IDENTICA a LIFLayer_EventProp:
        I[t] = (1 - dt/tau_s) * I[t-1] + W @ x[t-1]
        V[t] = (1 - dt/tau_m) * V[t-1] + (dt/tau_m) * I[t-1]
        s[t] = SurrogateSpike(V[t], V_th)
        V[t] <- V[t] * (1 - s[t])     hard reset

    Training: standard PyTorch BPTT. SurrogateSpike_Hardware fornisce il
    gradient flow nel backward (kernel fast-sigmoid gamma=1.0, vedi
    core/hardware.py).

    Args identici a LIFLayer_EventProp (per garantire stesso modello).
    """

    def __init__(self, in_features, out_features,
                 tau_m=2e-2, tau_s=1e-2, dt=1e-2, v_th=1.0,
                 mu_init=0.5):
        super().__init__()
        self.in_features  = in_features
        self.out_features = out_features
        self.tau_m = tau_m
        self.tau_s = tau_s
        self.dt    = dt

        self.alpha_m = 1.0 - dt / tau_m
        self.alpha_s = 1.0 - dt / tau_s
        self.beta_m  = dt / tau_m

        self.weight = nn.Parameter(torch.Tensor(out_features, in_features))
        nn.init.normal_(self.weight, mean=0.0, std=mu_init)
        # v_th as buffer (broadcasted scalar). SurrogateSpike accepts tensor threshold.
        self.register_buffer('v_th_tensor', torch.ones(out_features) * v_th)

    def forward(self, input_seq):
        """input_seq: (B, T, in_features) -> spikes: (B, T, out_features).

        Replica EXACTLY le dinamiche di LIFLayer_EventProp._manual_forward,
        ma usa autograd standard (no custom Function) + spike_fn (SurrogateSpike).
        """
        B, T, _ = input_seq.shape
        device = input_seq.device

        # Initial state (no spike at t=0, matches LIFLayer_EventProp which skips t=0)
        I_prev = torch.zeros(B, self.out_features, device=device)
        V_prev = torch.zeros(B, self.out_features, device=device)
        spikes_list = [torch.zeros(B, self.out_features, device=device)]  # t=0

        for t in range(1, T):
            # I[t] = alpha_s * I[t-1] + W @ x[t-1]
            I_t = self.alpha_s * I_prev + F.linear(input_seq[:, t-1], self.weight)
            # V[t] = alpha_m * V[t-1] + beta_m * I[t-1]    (uses I_prev, not I_t)
            V_t = self.alpha_m * V_prev + self.beta_m * I_prev
            # Spike via surrogate (autograd-friendly)
            s_t = spike_fn(V_t, self.v_th_tensor)
            # Hard reset
            V_t = V_t * (1.0 - s_t)
            # Advance state
            I_prev = I_t
            V_prev = V_t
            spikes_list.append(s_t)

        return torch.stack(spikes_list, dim=1)  # (B, T, out)


# ===========================================================
# ALIFLayer_EventProp_Full -- la TUA A1 con EventProp adjoint
# ===========================================================

class _EventPropWrapperFull(torch.autograd.Function):
    """Wrapper per ALIFLayer_EventProp_Full (6 grad params)."""

    @staticmethod
    def forward(ctx, input, fc_weight, rec_U, rec_V, base_th, thresh_jump,
                forward_fn, backward_fn):
        ctx.backward_fn = backward_fn
        ctx.fc_weight = fc_weight
        ctx.rec_U = rec_U
        ctx.rec_V = rec_V
        ctx.base_th = base_th
        ctx.thresh_jump = thresh_jump
        saved, output = forward_fn(input, fc_weight, rec_U, rec_V, base_th, thresh_jump)
        ctx.save_for_backward(*saved)
        return output

    @staticmethod
    def backward(ctx, grad_output):
        saved = ctx.saved_tensors
        grads = ctx.backward_fn(grad_output, *saved,
                                ctx.fc_weight, ctx.rec_U, ctx.rec_V,
                                ctx.base_th, ctx.thresh_jump)
        grad_input, grad_W, grad_rU, grad_rV, grad_bth, grad_tj = grads
        # 8 returns matching forward args (forward_fn, backward_fn -> None)
        return grad_input, grad_W, grad_rU, grad_rV, grad_bth, grad_tj, None, None


class ALIFLayer_EventProp_Full(nn.Module):
    """LA TUA architettura A1 (HiddenLayer_ALIF + ALIFCell) con EventProp.

    Replica EXACTLY l'arch baseline:
      * Po2 quantization su fc_weight, rec_U, rec_V (STE backward via PowerOf2Quantize)
      * max_delay synapses (deque-equivalent, mask per delay value)
      * n_ticks internal ticks per sequence step (TICKS_PER_STEP=10)
      * Bit-shift leak alpha_m = 7/8 (NO synaptic current I!)
      * Adaptive threshold ALIF: V_th_eff[k] = base_th + fatigue[k].clamp(0)
      * Fatigue bit-shift leak alpha_f = 7/8 + spike-driven thresh_jump
      * Soft reset: V <- V - s · V_th_eff
      * Low-rank recurrence rec_U(out,rank) @ rec_V(rank,out)
      * base_th, thresh_jump learnable (init 1.5, 0.5 -- matches baseline)

    Gradient su base_th via path soft reset (matches baseline behavior P5: l'unico
    path di grad per base_th è la via di reset, perché spike_fn non propaga grad
    al threshold). thresh_jump: gradiente complesso (via fatigue dynamics) - per
    questa implementazione lo lasciamo a zero (treat as frozen). Future estensione
    F2.2-bis includere lambda_fatigue completo.

    Forward processa K = T_seq * n_ticks tick interni atomicamente. Per ogni
    sequence step t, x_seq[t] è REPLICATO n_ticks volte (matches baseline che
    chiama layer_hidden(x_t) n_ticks volte con stesso x_t).

    Returns: (B, K, out_dim) spikes per ogni internal tick.
    """

    def __init__(self, in_features, out_features, rank=8, max_delay=6, n_ticks=10,
                 base_th_init=1.5, thresh_jump_init=0.5,
                 alpha_m=7.0/8.0, alpha_f=7.0/8.0,
                 eps=1e-3, silent_repair=True,
                 jump_clamp=10.0, lv_clamp=50.0, denom_gate_scale=0.0,
                 lambda_margin=0.0, margin_target=0.1, denom_leak_correct=False,
                 full_threshold_adjoint=False):
        super().__init__()
        self.in_features  = in_features
        self.out_features = out_features
        self.rank = rank
        self.max_delay = max_delay
        self.n_ticks = n_ticks
        self.alpha_m = alpha_m
        self.alpha_f = alpha_f
        self.eps = eps
        # C8 (EventProp_Study): stabilizzazione del cascade adjoint sugli spike marginali
        # (denom = drive - V_th_eff -> 0 con fatigue). jump_clamp limita il termine di salto
        # per-tick; lv_clamp bound l'adjoint accumulato. Senza, grad ~1e17 (fail storico 6/11).
        self.jump_clamp = jump_clamp
        self.lv_clamp = lv_clamp
        self.denom_gate_scale = denom_gate_scale   # C8b: scala gate morbido (0 = off)
        # Margine di spike (C9): spinge i singoli spike marginali (denom=drive-V_th piccolo)
        # ad attraversare la soglia con margine -> 1/denom limitato PER COSTRUZIONE -> adjoint
        # stabile senza clamp, mantenendo la sparsita' (agisce sul margine, non sul numero di spike).
        self.lambda_margin = lambda_margin       # 0 = off (default)
        self.margin_target = margin_target       # soglia |denom| sotto cui uno spike e' "marginale"
        # C10: correzione di scala del denom adjoint. Il bit-shift leak fa drive = (dt/tau)*I =
        # (1-alpha_m)*I, quindi la corrente efficace e' I = drive/(1-alpha_m). Il denom EventProp
        # dovrebbe usare V'(t*) ~ I - V_th = drive/(1-alpha_m) - V_th, NON drive - V_th (16x troppo
        # piccolo -> 1/denom spurio -> guadagno adjoint per-spike >1). False = comportamento attuale.
        self.denom_leak_correct = denom_leak_correct
        # C13: adjoint COMPLETO della soglia adattiva. f[k+1]=alpha_f*f[k]+s[k]*tj, V_th=base_th+f.
        # lambda_fatigue: lf[k] = gVth[k] + alpha_f*lf[k+1] (gVth = -s*lV = stesso termine di base_th);
        # grad_thresh_jump = sum_k s[k]*lf[k+1]. Sblocca i 32 param di thresh_jump (ora gradiente 0).
        # False = thresh_jump congelato (comportamento attuale).
        self.full_threshold_adjoint = bool(full_threshold_adjoint)
        # Diagnostica (stash ultimo batch): frazione spike marginali + |denom| medio agli spike
        # + V_th_eff medio agli spike (sale se il fatigue accumula -> stringe il denom).
        self._marginal_frac = 0.0
        self._mean_spike_margin = 0.0
        self._mean_vth_at_spike = 0.0
        self.silent_repair = silent_repair

        # Parameters (match baseline exactly)
        self.fc_weight = nn.Parameter(torch.Tensor(out_features, in_features))
        nn.init.xavier_uniform_(self.fc_weight)
        # FIX-BUG-4 (2026-06-03): compensa penalty 1/max_delay della delay mask.
        # Stesso bug di HiddenLayer_ALIF: solo gli edge con (delays==d) contribuiscono
        # al tick d → var(current) ridotta di 1/max_delay. Vedi BUGS_2026-06-03.md.
        with torch.no_grad():
            self.fc_weight.mul_(max_delay ** 0.5)
        # delays as buffer (non-learnable random integers in [0, max_delay))
        self.register_buffer('delays',
                              torch.randint(0, max_delay, (out_features, in_features)))

        self.rec_U = nn.Parameter(torch.Tensor(out_features, rank))
        self.rec_V = nn.Parameter(torch.Tensor(rank, out_features))
        nn.init.orthogonal_(self.rec_U, gain=0.2)
        nn.init.orthogonal_(self.rec_V, gain=0.2)

        # Adaptive threshold params (learnable, init same as baseline ALIFCell)
        self.base_threshold = nn.Parameter(torch.ones(out_features) * base_th_init)
        self.thresh_jump = nn.Parameter(torch.ones(out_features) * thresh_jump_init)

        # Precompute delay masks: delay_masks[d] = (out, in) bool mask
        delay_masks = torch.zeros(max_delay, out_features, in_features)
        for d in range(max_delay):
            delay_masks[d] = (self.delays == d).float()
        self.register_buffer('delay_masks', delay_masks)

    def _manual_forward(self, x_seq, fc_weight, rec_U, rec_V, base_th, thresh_jump):
        """Forward processa l'intera sequenza in K = T_seq * n_ticks ticks interni.

        Args:
            x_seq: (B, T_seq, in_features) input continuo normalizzato
            fc_weight, rec_U, rec_V, base_th, thresh_jump: parametri (passed for
                STE handling -- po2 applicato qui, gradient flow naturale)
        Returns:
            saved: (x_repl, V_th_eff, drive, s) per backward
            output: s (B, K, out_features) spike sequence
        """
        B, T_seq, in_dim = x_seq.shape
        K = T_seq * self.n_ticks
        device = x_seq.device
        out_dim = self.out_features

        # Po2 quantization (STE handled by PowerOf2Quantize -- backward returns
        # grad_output as-is for raw weights)
        w_po2 = po2_quantize(fc_weight)
        u_po2 = po2_quantize(rec_U)
        v_po2 = po2_quantize(rec_V)
        # Effective recurrent matrix: in baseline rec_int = linear(s, v_po2),
        # rec_curr = linear(rec_int, u_po2) -- this is (u_po2 @ v_po2) applied to s
        rec_full = u_po2 @ v_po2   # (out_dim, out_dim)

        # Replicate input across n_ticks (matches baseline behavior of feeding
        # same x_t for all n_ticks calls)
        x_repl = x_seq.repeat_interleave(self.n_ticks, dim=1)   # (B, K, in_dim)

        # Trajectories (saved for backward)
        V_th_eff = torch.zeros(B, K, out_dim, device=device)
        drive = torch.zeros(B, K, out_dim, device=device)
        s = torch.zeros(B, K, out_dim, device=device)

        # Silent repair loop
        for repair_iter in range(5):
            V_th_eff.zero_(); drive.zero_(); s.zero_()
            V_state = torch.zeros(B, out_dim, device=device)
            fatigue_state = torch.zeros(B, out_dim, device=device)
            s_prev = torch.zeros(B, out_dim, device=device)

            for k in range(K):
                # Input current via delays: sum_{d=0..max_delay-1} (mask_d * W_po2) @ x[k-d]
                I_input = torch.zeros(B, out_dim, device=device)
                for d in range(self.max_delay):
                    k_input = k - d
                    if k_input >= 0:
                        I_input = I_input + F.linear(
                            x_repl[:, k_input], w_po2 * self.delay_masks[d])

                # Recurrent current from previous spike
                rec_curr = F.linear(s_prev, rec_full)

                # Drive at tick k
                drive_k = I_input + rec_curr
                drive[:, k] = drive_k

                # Membrane update: V_new = alpha_m * V + drive (NO synaptic current!)
                V_pre = self.alpha_m * V_state + drive_k

                # Effective threshold (uses fatigue from PREVIOUS step, matching baseline)
                V_th_k = base_th + fatigue_state.clamp(min=0)
                V_th_eff[:, k] = V_th_k

                # Spike
                fired = (V_pre > V_th_k).float()
                s[:, k] = fired

                # Soft reset
                V_post = V_pre - fired * V_th_k

                # Update fatigue (decay + spike contribution)
                fatigue_new = (self.alpha_f * fatigue_state
                                + fired * thresh_jump.clamp(min=0))

                # Advance state
                V_state = V_post
                fatigue_state = fatigue_new
                s_prev = fired

            # Silent repair
            if self.training and self.silent_repair and repair_iter < 4:
                is_silent = s.sum(dim=(0, 1)) == 0
                if is_silent.any():
                    with torch.no_grad():
                        fc_weight.data[is_silent] = fc_weight.data[is_silent] + 0.1
                    continue
            break

        saved = (x_repl, V_th_eff, drive, s)
        return saved, s

    def _manual_backward(self, grad_output, x_repl, V_th_eff, drive, s,
                         fc_weight, rec_U, rec_V, base_th, thresh_jump):
        """Adjoint EventProp backward su K = T_seq * n_ticks tick.

        Calcola gradienti per: input, fc_weight, rec_U, rec_V, base_th, thresh_jump.
        Po2 STE: po2_quantize backward = identity → grad su raw weight = grad
        computed using w_po2 (which is what we use for the recurrent feedback).
        """
        B, K, in_dim = x_repl.shape
        out_dim = self.out_features
        device = x_repl.device

        # Po2 quantize per backward (STE: backward su raw = same value as on w_po2)
        w_po2 = po2_quantize(fc_weight)
        u_po2 = po2_quantize(rec_U)
        v_po2 = po2_quantize(rec_V)
        rec_full = u_po2 @ v_po2
        rec_full_T = rec_full.t()

        # Adjoint state (lV = lambda_V mirrors V_state-after-reset in math)
        lV = torch.zeros(B, K, out_dim, device=device)

        # Gradient accumulators (per-sample, summed at end)
        grad_input = torch.zeros(B, K, in_dim, device=device)
        grad_W = torch.zeros(B, out_dim, in_dim, device=device)
        grad_rec_full = torch.zeros(B, out_dim, out_dim, device=device)
        grad_base_th = torch.zeros(B, out_dim, device=device)
        # thresh_jump: gradient via fatigue dynamics complex, ignored for now (= 0)

        # === Diagnostica denom + margine (C9) ===
        # denom agli spike = drive_eff - V_th_eff (cio' che l'adjoint divide per 1/denom).
        # C10: drive_eff = drive/(1-alpha_m) se denom_leak_correct (corrente efficace post-leak),
        # altrimenti drive grezzo (comportamento attuale).
        _drive_eff = drive / (1.0 - self.alpha_m) if self.denom_leak_correct else drive
        denom_all = _drive_eff - V_th_eff                     # (B, K, out)
        fired = s                                             # (B, K, out), {0,1}
        _n_fired = fired.sum().clamp(min=1.0)
        self._marginal_frac = float(
            ((fired * (denom_all.abs() < self.margin_target).float()).sum() / _n_fired).item())
        self._mean_spike_margin = float(((fired * denom_all.abs()).sum() / _n_fired).item())
        self._mean_vth_at_spike = float(((fired * V_th_eff).sum() / _n_fired).item())  # fatigue tracker
        # margin_term[k] = 2*lambda*relu(margin_target - denom) sui SOLI spike (diretto, NON ricorsivo):
        # entra solo in grad_W (peso input->drive) per spingere su il drive degli spike marginali.
        if self.lambda_margin > 0.0:
            margin_term = 2.0 * self.lambda_margin * F.relu(self.margin_target - denom_all) * fired
        else:
            margin_term = None

        # C13: adjoint del fatigue (lf) + accumulatore di grad_thresh_jump (per-sample)
        if self.full_threshold_adjoint:
            lf = torch.zeros(B, K, out_dim, device=device)
            gtj = torch.zeros(B, out_dim, device=device)
        else:
            lf = None

        for k in range(K - 2, -1, -1):
            # Rec feedback: s[k+1] entra in rec_curr[k+2] = rec_full @ s[k+1]
            # che contribuisce a V_pre[k+2]. Adjoint da lV[k+2] back to s[k+1]:
            if k + 2 < K:
                rec_feedback = F.linear(lV[:, k+2], rec_full_T)
            else:
                rec_feedback = torch.zeros(B, out_dim, device=device)

            # Total grad su s[k+1]: upstream (LI output) + recurrent feedback
            total_grad_s = grad_output[:, k+1] + rec_feedback

            # Jump al spike time k+1 (formula EventProp: denom ≈ V'(t*) discretizzato).
            # denom_all gia' calcolato sopra (con/senza correzione leak C10).
            denom_raw = denom_all[:, k+1]
            denom = torch.where(denom_raw.abs() < self.eps,
                                torch.sign(denom_raw + 1e-12) * self.eps, denom_raw)
            jump = s[:, k+1] * (lV[:, k+1] + total_grad_s) / denom
            # C8b: gate MORBIDO sul denominatore. Gli spike marginali (denom_raw -> 0) danno un
            # jump inaffidabile (formula adjoint degenere); invece di clamparlo (= direzione
            # corrotta), lo ATTENUA con gate = denom_raw^2 / (denom_raw^2 + scale^2) in [0,1]:
            # ~0 per crossing marginali (|denom|<<scale), ~1 per crossing puliti. scale=0 = off.
            if self.denom_gate_scale > 0.0:
                gate = denom_raw * denom_raw / (denom_raw * denom_raw + self.denom_gate_scale ** 2)
                jump = jump * gate
            # C8: taglia il jump per-tick (rete di sicurezza contro overflow residuo)
            if self.jump_clamp is not None:
                jump = torch.clamp(jump, -self.jump_clamp, self.jump_clamp)

            # Update adjoint: lV[k] = alpha_m * lV[k+1] + jump
            lV[:, k] = self.alpha_m * lV[:, k+1] + jump
            # C8: bound l'adjoint accumulato -> rompe il cascade su 500 tick
            if self.lv_clamp is not None:
                lV[:, k] = torch.clamp(lV[:, k], -self.lv_clamp, self.lv_clamp)

            # === Gradient accumulators ===
            # NB: usiamo lolemacs-style indexing (lV[k+1] per il contributo at step k+1)

            # 1) grad_W via delays: drive[k+1] += Σ_d (mask_d * W_po2) @ x[k+1-d]
            #    grad_W_d += -lV[k+1] outer x[k+1-d] * mask_d
            # Coefficiente di grad_W: adjoint lV[k+1] + termine di margine (C9, diretto sui pesi
            # input->drive). Il margine NON entra nella ricorsione di lV ne' in grad_input.
            coef_W = lV[:, k+1] if margin_term is None else (lV[:, k+1] + margin_term[:, k+1])
            for d in range(self.max_delay):
                k_in = k + 1 - d
                if 0 <= k_in < K:
                    grad_W_contrib = -coef_W.unsqueeze(2) * x_repl[:, k_in].unsqueeze(1)
                    grad_W = grad_W + grad_W_contrib * self.delay_masks[d].unsqueeze(0)
                    # Input grad: x[k+1-d] -> drive[k+1] via (mask_d * W_po2)
                    grad_input_contrib = F.linear(
                        lV[:, k+1], (self.delay_masks[d] * w_po2).t())
                    grad_input[:, k_in] = grad_input[:, k_in] + grad_input_contrib

            # 2) grad_rec_full: s[k+1] -> rec_curr[k+2] = rec_full @ s[k+1]
            #    grad_rec_full += -lV[k+2] outer s[k+1]
            if k + 2 < K:
                grad_rec_full = grad_rec_full - lV[:, k+2].unsqueeze(2) * s[:, k+1].unsqueeze(1)

            # 3) grad_base_th: V_th_eff[k+1] = base_th + fatigue.clamp(0)
            #    Soft reset: V_post[k+1] -= s[k+1] * V_th_eff[k+1]
            #    adjoint: grad_base_th += -s[k+1] * lV[k+1]
            #    (sum across time and batch)
            gVth = -s[:, k+1] * lV[:, k+1]               # grad reset-path su V_th[k+1]
            grad_base_th = grad_base_th + gVth

            # 4) C13: adjoint del fatigue. V_th[k+1] dipende da f[k+1] (= base_th + relu(f), deriv 1);
            #    f[k+1] = alpha_f*f[k] + s[k]*thresh_jump. lf[k+1] = gVth[k+1] + alpha_f*lf[k+2];
            #    grad_thresh_jump += s[k]*lf[k+1].
            if lf is not None:
                lf_next = lf[:, k+2] if k + 2 < K else 0.0
                lf[:, k+1] = gVth + self.alpha_f * lf_next
                gtj = gtj + s[:, k] * lf[:, k+1]

        # === Sum across batch ===
        grad_W_total = grad_W.sum(dim=0)
        grad_rec_full_total = grad_rec_full.sum(dim=0)
        grad_base_th_total = grad_base_th.sum(dim=0)

        # === Low-rank chain rule per rec_U, rec_V ===
        # rec_full = u_po2 @ v_po2, applied via F.linear(s, rec_full).
        # dL/d(rec_U) = grad_rec_full @ rec_V.t()
        # dL/d(rec_V) = rec_U.t() @ grad_rec_full
        # (Po2 STE: grad sul po2 weight = grad sul raw weight)
        grad_rec_U = grad_rec_full_total @ rec_V.t()
        grad_rec_V = rec_U.t() @ grad_rec_full_total

        # thresh_jump: zero se adjoint del fatigue disattivo (C13 off); altrimenti gtj sommato sul batch
        if self.full_threshold_adjoint:
            grad_thresh_jump = gtj.sum(dim=0)
        else:
            grad_thresh_jump = torch.zeros_like(thresh_jump)

        return (grad_input, grad_W_total, grad_rec_U, grad_rec_V,
                grad_base_th_total, grad_thresh_jump)

    def forward(self, input):
        return _EventPropWrapperFull.apply(
            input, self.fc_weight, self.rec_U, self.rec_V,
            self.base_threshold, self.thresh_jump,
            self._manual_forward, self._manual_backward,
        )


# ===========================================================
# LILayer output (2 variants)
# ===========================================================

class LILayer_Standard(nn.Module):
    """Output LI con dt/tau leak (per F2.0b semplice). Standard PyTorch autograd."""

    def __init__(self, in_features, out_features, tau=2e-2, dt=1e-2):
        super().__init__()
        self.in_features  = in_features
        self.out_features = out_features
        self.alpha = 1.0 - dt / tau
        self.weight = nn.Parameter(torch.Tensor(out_features, in_features))
        nn.init.xavier_uniform_(self.weight)

    def forward(self, input_spikes):
        B, T, _ = input_spikes.shape
        device = input_spikes.device
        v = torch.zeros(B, self.out_features, device=device)
        outs = []
        for t in range(T):
            v = self.alpha * v + F.linear(input_spikes[:, t], self.weight)
            outs.append(v.unsqueeze(1))
        return torch.cat(outs, dim=1)


class LILayer_BitShift_Po2(nn.Module):
    """Output LI con bit-shift leak (V/8) + Po2 quantize -- matches baseline.

    Replica OutputLayer_LI + LICell di baseline:
        V_out[t] = (1 - 1/8) * V_out[t-1] + po2(W) @ s[t]
                = 7/8 * V_out[t-1] + po2(W) @ s[t]

    Standard PyTorch autograd. Po2 STE già gestita da PowerOf2Quantize.
    """

    def __init__(self, in_features, out_features, alpha=7.0/8.0):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.alpha = alpha
        self.weight = nn.Parameter(torch.Tensor(out_features, in_features))
        nn.init.xavier_uniform_(self.weight)
        # FIX-BUG-2 (2026-06-03): rimuovi bias per-riga indotto da xavier_uniform.
        # Stesso bug di OutputLayer_LI: con input spike binari {0,1} a firing rate
        # basso, row_mean ≠ 0 → bias deterministico per canale → asimmetria
        # combinata con sigmoid in _decode_params. Vedi document/BUGS_2026-06-03.md.
        with torch.no_grad():
            self.weight.sub_(self.weight.mean(dim=1, keepdim=True))

    def forward(self, input_spikes):
        """input_spikes: (B, T, in_dim) -> out: (B, T, out_dim)"""
        B, T, _ = input_spikes.shape
        device = input_spikes.device
        w_po2 = po2_quantize(self.weight)
        v = torch.zeros(B, self.out_features, device=device)
        outs = []
        for t in range(T):
            v = self.alpha * v + F.linear(input_spikes[:, t], w_po2)
            outs.append(v.unsqueeze(1))
        return torch.cat(outs, dim=1)
