# Arch_Tested/A3_stacked_skip_BPTT_2624p/core/network.py
# Generato automaticamente: SOLO classi necessarie per variant 'stacked_2_skip'.
# Versione completa con tutte 11 varianti: repository root core/network.py
import torch
import torch.nn as nn
from collections import deque    # F8: ring-buffer O(1) per delay assonali
from core.hardware import po2_quantize
from core.neurons import ALIFCell, LICell
import math as _math

class HiddenLayer_ALIF(nn.Module):
    def __init__(self, in_features, out_features, rank=16, max_delay=3):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.max_delay = max_delay

        self.fc_weight = nn.Parameter(torch.Tensor(out_features, in_features))
        nn.init.xavier_uniform_(self.fc_weight)
        # FIX-BUG-4 (2026-06-03): compensa penalty 1/max_delay della delay mask.
        # Vedi document/BUGS_2026-06-03.md criticità #4.
        with torch.no_grad():
            self.fc_weight.mul_(max_delay ** 0.5)
        self.register_buffer('delays', torch.randint(0, max_delay, (out_features, in_features)))

        self.rec_U = nn.Parameter(torch.Tensor(out_features, rank))
        self.rec_V = nn.Parameter(torch.Tensor(rank, out_features))
        nn.init.orthogonal_(self.rec_U, gain=0.2)
        nn.init.orthogonal_(self.rec_V, gain=0.2)

        self.x_buffer = None
        self.cell = ALIFCell(out_features)

    def reset_state(self, batch_size, device):
        # F8: deque(maxlen) come ring-buffer — appendleft() è O(1) vs list.insert() O(n).
        # maxlen garantisce che il buffer non cresca oltre max_delay elementi.
        self.x_buffer = deque(
            [torch.zeros(batch_size, self.in_features, device=device)
             for _ in range(self.max_delay)],
            maxlen=self.max_delay,
        )
        self.cell.reset_state(batch_size, device)

    def forward(self, x):
        if self.x_buffer is None:
            self.reset_state(x.size(0), x.device)

        # F8: appendleft sposta l'input in testa e scarta automaticamente la coda
        # (equivalente a insert(0, x) + pop() ma O(1) invece di O(max_delay)).
        self.x_buffer.appendleft(x)

        w_po2 = po2_quantize(self.fc_weight)
        u_po2 = po2_quantize(self.rec_U)
        v_po2 = po2_quantize(self.rec_V)

        current = torch.zeros(x.size(0), self.out_features, device=x.device)
        for d in range(self.max_delay):
            mask_d = (self.delays == d).float()
            current += torch.nn.functional.linear(self.x_buffer[d], w_po2 * mask_d)

        rec_int = torch.nn.functional.linear(self.cell.prev_spike, v_po2)
        rec_curr = torch.nn.functional.linear(rec_int, u_po2)

        return self.cell(current, rec_curr)


class OutputLayer_LI(nn.Module):
    def __init__(self, in_features, out_features):
        super().__init__()
        self.fc_weight = nn.Parameter(torch.Tensor(out_features, in_features))
        nn.init.xavier_uniform_(self.fc_weight)
        # FIX-BUG-2 (2026-06-03): rimuovi bias per-riga indotto da xavier_uniform.
        # Vedi document/BUGS_2026-06-03.md bug #2.
        with torch.no_grad():
            self.fc_weight.sub_(self.fc_weight.mean(dim=1, keepdim=True))
        self.cell = LICell(out_features)

    def reset_state(self, batch_size, device):
        self.cell.reset_state(batch_size, device)

    def forward(self, input_spikes):
        if self.cell.potential is None:
            self.reset_state(input_spikes.size(0), input_spikes.device)

        w_po2 = po2_quantize(self.fc_weight)
        current = torch.nn.functional.linear(input_spikes, w_po2)
        
        return self.cell(current)


class CF_FSNN_Net(nn.Module):
    """
    SNN per Car-Following con training Physics-Informed (PINN).

    Architettura:
        HiddenLayer_ALIF (4 → 32, rank=8, max_delay=6)  ← V2X: [s, v, Δv, v_l]
        OutputLayer_LI   (32 → 5)                        ← parametri IDM: [v0, T, s0, a, b]

    Connessione ACC-IDM ↔ ALIF (Ch12 Sez.12.4 + Ch13):
        max_delay=6  →  ritardo sinaptico hardware = 6 tick × (DT/TICKS_PER_STEP)
                        = 6 × 0.01 s = 0.06 s (ritardo assonale FPGA — F11).
                        Il tempo di reazione biologico Tr ∈ [0.1, 0.6] s è modellato
                        dal buffer delay, non dal singolo tick interno (Ch13).
        fatica ALIF  →  T(t) stocastico (processo IDM-2d su T, Ch12.6, banda [T1, T2])
        rank=8       →  ricorrenza low-rank (U 32×8, V 8×32)

    Ogni passo di simulazione (Δt=0.1 s) viene elaborato con TICKS_PER_STEP
    tick SNN interni; il potenziale finale del layer LI viene mappato via
    sigmoid + scaling nei range fisici dei 5 parametri IDM.

    Range fisici (param_lo, param_hi):
        v0 ∈ [8,  45]  m/s
        T  ∈ [0.5, 2.5] s
        s0 ∈ [1.0, 5.0] m
        a  ∈ [0.3, 2.5] m/s²
        b  ∈ [0.5, 3.0] m/s²
    """

    _PARAM_BOUNDS = [
        [ 8.0, 45.0],   # 0: v0 [m/s]
        [ 0.5,  2.5],   # 1: T  [s]
        [ 1.0,  5.0],   # 2: s0 [m]
        [ 0.3,  2.5],   # 3: a  [m/s²]
        [ 0.5,  3.0],   # 4: b  [m/s²]
    ]

    def __init__(self, hidden_size=None, rank=None, max_delay=None):
        """
        Args:
            hidden_size: override CF_HIDDEN_SIZE (None → usa config). Per STEP 2B sweep.
            rank: override CF_RANK (None → usa config). Per STEP 2B sweep.
            max_delay: override CF_MAX_DELAY (None → usa config). Per STEP 2E A5 variant.
        """
        super().__init__()
        from config import (
            CF_INPUT_SIZE, CF_HIDDEN_SIZE, CF_OUTPUT_SIZE,
            CF_RANK, CF_MAX_DELAY, TICKS_PER_STEP,
            IDM2D_T1, IDM2D_T2, IDM2D_TAU, DT,
        )

        # STEP 2B: capacity override via kwargs (None → fallback su config).
        # STEP 2E A5: max_delay override per variant max_delay_12.
        hidden_size = hidden_size if hidden_size is not None else CF_HIDDEN_SIZE
        rank        = rank        if rank        is not None else CF_RANK
        max_delay   = max_delay   if max_delay   is not None else CF_MAX_DELAY
        self.hidden_size = hidden_size   # esposto per logging/diagnostica
        self.rank        = rank
        self.max_delay   = max_delay

        self.n_ticks  = TICKS_PER_STEP
        self.T1       = IDM2D_T1
        self.T2       = IDM2D_T2
        self.T_mean   = (IDM2D_T1 + IDM2D_T2) / 2.0
        # α = exp(-Δt / τ_OU): costante mean-reversion per loss OU  (≈ 0.9967)
        self.ou_alpha = _math.exp(-DT / IDM2D_TAU)

        self.layer_hidden = HiddenLayer_ALIF(
            CF_INPUT_SIZE, hidden_size,
            rank=rank, max_delay=max_delay,
        )
        self.layer_out = OutputLayer_LI(hidden_size, CF_OUTPUT_SIZE)

        # Bounds come buffer → si spostano con .to(device)
        bounds = torch.tensor(self._PARAM_BOUNDS, dtype=torch.float32)
        self.register_buffer('param_lo', bounds[:, 0])   # (5,)
        self.register_buffer('param_hi', bounds[:, 1])   # (5,)

        # F5 — Pre-scaling per equalizzare il gradiente tra i 5 parametri.
        # Problema: d(decode_i)/d(raw_i) = (hi_i - lo_i) * σ'(raw_i).
        # I range differiscono: v0=37, T=2, s0=4, a=2.2, b=2.5.
        # Senza scaling il gradiente che arriva a raw_v0 è 37/2 = 18.5× più grande
        # di quello a raw_T → la rete impara v0 molto più velocemente di T.
        # Fix: raw_eq_i = raw_i / decode_scale_i dove decode_scale_i = (hi-lo)_i / max_range.
        # Risultato: d(decode_i)/d(raw_i) = σ'(raw_eq_i) — identico per tutti i parametri.
        ranges = bounds[:, 1] - bounds[:, 0]                  # (5,) = [37, 2, 4, 2.2, 2.5]
        self.register_buffer('decode_scale', ranges / ranges.max())  # (5,) normalizzato

    # ----------------------------------------------------------
    # Stato SNN
    # ----------------------------------------------------------
    def reset_state(self, batch_size, device):
        """Resetta potenziali, fatica e ring-buffer di tutti i layer."""
        self.layer_hidden.reset_state(batch_size, device)
        self.layer_out.reset_state(batch_size, device)

    # ----------------------------------------------------------
    # Decodifica parametri
    # ----------------------------------------------------------
    def _decode_params(self, raw):
        """Potenziale LI grezzo → parametri IDM fisici via sigmoid.

        raw:     (batch, 5)
        returns: (batch, 5) in unità fisiche

        F5 — Pre-scaling per gradiente bilanciato:
            raw_eq_i = raw_i / decode_scale_i
            d(param_i)/d(raw_i) = (hi-lo)_i * σ'(raw_eq_i) / decode_scale_i
                                 = max_range * σ'(raw_eq_i)   [uniforme tra i 5 param]
        Senza scaling raw_v0 avrebbe un gradiente 18.5× maggiore di raw_T.
        """
        # FIX-BUG-1 (2026-06-03): rimosso F5 pre-scaling. Vedi document/BUGS_2026-06-03.md.
        return self.param_lo + (self.param_hi - self.param_lo) * torch.sigmoid(raw)

    # ----------------------------------------------------------
    # Forward
    # ----------------------------------------------------------
    def forward_step(self, x_norm):
        """Un passo di simulazione = n_ticks tick SNN interni.

        x_norm:  (batch, 4)  — input normalizzato [s̃, ṽ, Δṽ, ṽ_l] ∈ [0, 1]
        returns: (batch, 5)  — parametri IDM in unità fisiche

        Il potenziale LI integra i spike dell'hidden layer su n_ticks tick;
        il valore finale è il readout usato per la decodifica.
        """
        raw_out = None
        for _ in range(self.n_ticks):
            spikes_h = self.layer_hidden(x_norm)
            raw_out  = self.layer_out(spikes_h)
        return self._decode_params(raw_out)

    def forward_sequence(self, x_seq_norm):
        """Processa una traiettoria completa (training / validazione).

        x_seq_norm: (batch, T, 4)  — sequenza normalizzata
        returns:    (batch, T, 5)  — parametri IDM nel tempo

        Lo stato SNN è resettato all'inizio della traiettoria e
        propagato correttamente tra i passi temporali successivi.
        """
        batch, T_len, _ = x_seq_norm.shape
        self.reset_state(batch, x_seq_norm.device)

        steps = []
        for t in range(T_len):
            p_t = self.forward_step(x_seq_norm[:, t, :])
            steps.append(p_t.unsqueeze(1))

        return torch.cat(steps, dim=1)   # (batch, T, 5)

    # ----------------------------------------------------------
    # Fisica ACC-IDM — componenti della PINN loss
    # ----------------------------------------------------------
    @staticmethod
    def idm_accel(s, v, dv, params):
        """Accelerazione IDM plain (Ch12) dai parametri predetti dalla rete.

        NOTA: questa funzione è mantenuta come RIFERIMENTO. Il training usa
        acc_iidm_accel() (ACC-IDM con base IIDM). Vedi note in pinn_loss().

        s, v, dv:  (batch,)   — gap [m], vel. ego [m/s], Δv = v − v_l [m/s]
        params:    (batch, 5) = [v0, T, s0, a, b]
        returns:   (batch,)   — accelerazione [m/s²]

        Implementa Ch12 Eq. 12.6–12.7 con crash provision (bmax = 9 m/s²).
        Convenzione: Δv > 0 → avvicinamento (gap in diminuzione).
        """
        v0 = params[:, 0].clamp(min=1e-3)
        T  = params[:, 1].clamp(min=1e-3)
        s0 = params[:, 2]
        a  = params[:, 3].clamp(min=1e-3)
        b  = params[:, 4].clamp(min=1e-3)

        # Spazio desiderato: s*(v, Δv) = s0 + max(0, v·T + v·Δv / (2√(a·b)))
        sqrt_ab = torch.sqrt(a * b).clamp(min=1e-6)
        s_star  = s0 + torch.relu(v * T + v * dv / (2.0 * sqrt_ab))

        # Accelerazione IDM: a · [1 − (v/v0)^delta − (s*/s)²]
        # delta=4 hardcoded (F7): coerente con IDM_HWY/URB/TRK in config.py (tutti delta=4).
        # ATTENZIONE: se il generatore usa delta≠4, le formule divergono. Verificare config.
        s_safe  = s.clamp(min=0.5)
        v_ratio = (v / v0).clamp(max=10.0)
        accel   = a * (1.0 - v_ratio ** 4 - (s_star / s_safe) ** 2)

        # Crash provision Ch11: clip a [-9, a]
        # clamp() does not accept mixed scalar/tensor bounds -> two ops
        accel = accel.clamp(min=-9.0)
        return torch.minimum(accel, a)

    @staticmethod
    def acc_iidm_accel(s, v, dv, a_l, params, coolness=0.99):
        """Accelerazione ACC-IDM con base IIDM (versione torch per PINN loss).

        Usa IIDM (ch12) per eliminare il bias v0 di IDM plain:
          z<1, v<=v0: afree*(1-z²);  z>=1, v<=v0: a*(1-z²) [vale 0 in z=1].
          v>v0: afree (z<1) o afree+a*(1-z²) (z>=1).
        Usa CAH (ch12 Eq.12.35): a_cah = min(a_l,a) - relu(Δv)²/(2s).

        s, v, dv:  (batch,) — gap [m], vel. ego [m/s], Δv = v − v_l [m/s]
        a_l:       (batch,) — acc. leader stimata (filtro OU) [m/s²]
        params:    (batch, 5) = [v0, T, s0, a, b]
        coolness:  float (0.99 fisso)
        returns:   (batch,) — accelerazione [m/s²]
        """
        v0 = params[:, 0].clamp(min=1e-3)
        T  = params[:, 1].clamp(min=1e-3)
        s0 = params[:, 2]
        a  = params[:, 3].clamp(min=1e-3)
        b  = params[:, 4].clamp(min=1e-3)

        # Gap desiderato s*
        sqrt_ab = torch.sqrt(a * b).clamp(min=1e-6)
        s_star  = s0 + torch.relu(v * T + v * dv / (2.0 * sqrt_ab))
        # min=2.0 invece di 0.5: limita d(a_IIDM)/d(T) = -2*a*z*v/s_safe.
        # Con la formula corretta a*(1-z^2), il gradiente cresce linearmente con z.
        # s_safe=0.5 → v/s_safe=76 → gn~8000 su highway; s_safe=2.0 → v/s_safe=19 → gn~200.
        s_safe  = s.clamp(min=2.0)

        # ── IIDM base (ch12: regime free-flow separato dal car-following) ──
        # afree = a*(1-(v/v0)^delta): positivo se v<=v0, negativo se v>v0
        # delta=4 hardcoded (F7): coerente con IDM_HWY/URB/TRK in config.py (tutti delta=4).
        # ATTENZIONE: se il generatore usa delta≠4, le formule divergono. Verificare config.
        v_free   = a * (1.0 - (v / v0).clamp(max=10.0) ** 4)
        z        = (s_star / s_safe).clamp(max=20.0)
        below_v0 = v <= v0
        a_z      = a * (1.0 - z.pow(2))           # termine interazione puro

        # z < 1 (free-flow): afree*(1-z²) se v<=v0, altrimenti solo afree
        a_ff = torch.where(below_v0, v_free * (1.0 - z.pow(2)), v_free)
        # z >= 1 (car-following): a*(1-z²) se v<=v0 [vale 0 in z=1], afree+a*(1-z²) se v>v0
        a_cf = torch.where(below_v0, a_z, v_free + a_z)
        a_iidm = torch.where(z < 1.0, a_ff, a_cf)

        # ── CAH (ch12 Eq.12.35) ──────────────────────────────────────
        # a_cah = ā_l − relu(Δv)²/(2s),  ā_l = min(a_l, a)
        a_l_bar = torch.minimum(a_l, a)
        a_cah   = a_l_bar - torch.relu(dv).pow(2) / (2.0 * s_safe + 1e-6)
        a_cah   = a_cah.clamp(min=-9.0)
        a_cah   = torch.minimum(a_cah, a)

        # ── Blend ACC-IDM ────────────────────────────────────────────
        c       = coolness
        diff    = (a_iidm - a_cah) / (b + 1e-6)
        a_blend = (1.0 - c) * a_iidm + c * (a_cah + b * torch.tanh(diff))
        a_acc   = torch.where(a_iidm >= a_cah, a_iidm, a_blend)

        # Crash provision (Ch11)
        a_acc = a_acc.clamp(min=-9.0)
        return torch.minimum(a_acc, a)

    def ou_residual(self, params_seq):
        """Residuo OU su T (componente λ_OU della PINN loss).

        Penalizza sequenze T(t) che non seguono la dinamica di mean-reversion
        del processo IDM-2d (Ch12 Eq. 12.19):
            E[T(t+Δt)] = α·T(t) + (1−α)·T_mean,   α = exp(−Δt / τ_OU)

        NOTA SUL FLOOR (F6): il generatore usa un processo di salto Markoviano
        per T (salta a U(T1,T2) con prob dt/tau ≈ 0.003 per step), non un OU
        continuo. Questa penalità penalizza quei salti come 'deviazioni OU'.
        Il floor irreducibile stimato è Var(U(T1,T2)) * prob_jump ≈ 1.8e-4.
        In training, L_ou < 1e-3 indica T ragionevolmente smooth — non è
        atteso scendere a zero per costruzione.

        params_seq: (batch, T, 5)
        returns:    scalare
        """
        T_seq      = params_seq[:, :, 1]
        T_prev     = T_seq[:, :-1]
        T_next     = T_seq[:, 1:]
        T_expected = self.ou_alpha * T_prev + (1.0 - self.ou_alpha) * self.T_mean
        return torch.mean((T_next - T_expected) ** 2)

    def forward_sequence_with_stats(self, x_seq_norm):
        """Come forward_sequence ma restituisce anche spike_rate del layer hidden.

        Usato da pinn_loss() per il logging diagnostico della spike activity.
        Definito direttamente nella classe (F4: rimosso il monkey-patch da train.py).

        x_seq_norm: (batch, T, 4)
        returns:    (params_seq (batch, T, 5), spike_rate (batch, T))
        """
        batch, T_len, _ = x_seq_norm.shape
        self.reset_state(batch, x_seq_norm.device)
        steps  = []
        spikes = []
        for t in range(T_len):
            x_t = x_seq_norm[:, t, :]
            raw_out     = None
            spike_h_acc = torch.zeros(batch, self.layer_hidden.out_features,
                                      device=x_t.device)
            for _ in range(self.n_ticks):
                spike_h = self.layer_hidden(x_t)
                raw_out = self.layer_out(spike_h)
                spike_h_acc = spike_h_acc + spike_h.float()
            spike_h_rate = spike_h_acc / self.n_ticks        # (batch, hidden)
            spikes.append(spike_h_rate.mean(dim=1, keepdim=True))   # (batch, 1)
            steps.append(self._decode_params(raw_out).unsqueeze(1))  # (batch, 1, 5)
        return torch.cat(steps, dim=1), torch.cat(spikes, dim=1)     # (batch,T,5), (batch,T)


# =================================================================
# STEP 2E — Architecture Exploration variants
# =================================================================
# Tutte le varianti ereditano `CF_FSNN_Net` per riusare:
#   - _PARAM_BOUNDS, _decode_params, decode_scale (F5 pre-scaling)
#   - param_lo/param_hi buffers
#   - acc_iidm_accel, idm_accel, ou_residual (fisica condivisa)
# e override SOLO:
#   - __init__ (sostituisce layer_hidden/layer_out con topologia variante)
#   - reset_state
#   - forward_step
#   - forward_sequence_with_stats (entry point usato da pinn_loss)
#
# Vincoli FPGA mantenuti: po2_quantize su TUTTI i pesi sinaptici, spike_fn (γ=1.0),
# bit-shift leak (intero, potenza di 2), max_delay come int con deque ring-buffer.


class _CF_FSNN_VariantBase(CF_FSNN_Net):
    """Base per le varianti — riusa fisica + decode, richiede override forward.

    Le sottoclassi NON chiamano super().__init__() perché ricostruiscono interamente
    la topologia. Usano _init_common(hidden_size, max_delay) per fisica/decode.
    """

    def __init__(self, hidden_size, max_delay=None):
        # Bypass CF_FSNN_Net.__init__ (che costruirebbe i layer baseline) e chiama
        # nn.Module.__init__ direttamente — pattern KISS, evita duplicazione fisica.
        nn.Module.__init__(self)
        from config import (
            CF_INPUT_SIZE, CF_HIDDEN_SIZE, CF_OUTPUT_SIZE,
            CF_RANK, CF_MAX_DELAY, TICKS_PER_STEP,
            IDM2D_T1, IDM2D_T2, IDM2D_TAU, DT,
        )
        self.hidden_size = hidden_size if hidden_size is not None else CF_HIDDEN_SIZE
        self.max_delay   = max_delay   if max_delay   is not None else CF_MAX_DELAY
        self.n_ticks  = TICKS_PER_STEP
        self.T1       = IDM2D_T1
        self.T2       = IDM2D_T2
        self.T_mean   = (IDM2D_T1 + IDM2D_T2) / 2.0
        self.ou_alpha = _math.exp(-DT / IDM2D_TAU)
        self.CF_INPUT_SIZE  = CF_INPUT_SIZE
        self.CF_OUTPUT_SIZE = CF_OUTPUT_SIZE
        self.CF_MAX_DELAY   = CF_MAX_DELAY

        # Decode bounds + F5 pre-scaling (identici al baseline)
        bounds = torch.tensor(self._PARAM_BOUNDS, dtype=torch.float32)
        self.register_buffer('param_lo', bounds[:, 0])
        self.register_buffer('param_hi', bounds[:, 1])
        ranges = bounds[:, 1] - bounds[:, 0]
        self.register_buffer('decode_scale', ranges / ranges.max())


# -----------------------------------------------------------------
# A2 / A4 — Stacked N-hidden ALIF
# -----------------------------------------------------------------
class CF_FSNN_Net_StackedSkip(_CF_FSNN_VariantBase):
    """A2 + skip Po2-quantizzato dai spike del layer hidden 1 al membrane potential di LI.

    Pattern MS-ResNet (Fang et al. 2021, SNN-expert ch05.11):
        LI_pot += linear_po2(skip_weight, spikes_layer1)

    Forza l'informazione del primo layer a raggiungere l'output bypassando il secondo,
    riducendo vanishing temporale.
    """

    def __init__(self, n_hidden=2, hidden_sizes=None, ranks=None, max_delay=None):
        hidden_sizes = hidden_sizes or [32] * n_hidden
        ranks        = ranks        or [8]  * n_hidden
        assert n_hidden == 2, "StackedSkip è definito su 2 layer (skip da layer 0 a LI)"
        super().__init__(hidden_size=hidden_sizes[0], max_delay=max_delay)
        self.n_hidden     = n_hidden
        self.hidden_sizes = hidden_sizes
        self.ranks        = ranks
        self.rank = ranks[0]

        self.layer_hidden_0 = HiddenLayer_ALIF(
            self.CF_INPUT_SIZE, hidden_sizes[0],
            rank=ranks[0], max_delay=self.max_delay,
        )
        self.layer_hidden_1 = HiddenLayer_ALIF(
            hidden_sizes[0], hidden_sizes[1],
            rank=ranks[1], max_delay=self.max_delay,
        )
        self.layer_out = OutputLayer_LI(hidden_sizes[1], self.CF_OUTPUT_SIZE)
        # Skip: hidden_sizes[0] → CF_OUTPUT_SIZE (5), Po2-quantizzato
        self.skip_weight = nn.Parameter(torch.Tensor(self.CF_OUTPUT_SIZE, hidden_sizes[0]))
        nn.init.xavier_uniform_(self.skip_weight)
        # Init scale piccolo: skip è additivo, non deve dominare
        with torch.no_grad():
            self.skip_weight.mul_(0.2)
        # FIX-BUG-3 (2026-06-03): abbassa base_threshold per layer 1 (non-input).
        # Vedi document/BUGS_2026-06-03.md criticità #3.
        with torch.no_grad():
            self.layer_hidden_1.cell.base_threshold.fill_(1.0)

    def reset_state(self, batch_size, device):
        self.layer_hidden_0.reset_state(batch_size, device)
        self.layer_hidden_1.reset_state(batch_size, device)
        self.layer_out.reset_state(batch_size, device)

    def _tick(self, x_norm):
        spikes_0 = self.layer_hidden_0(x_norm)
        spikes_1 = self.layer_hidden_1(spikes_0)
        # Skip additivo Po2 sul potential di LI
        skip_po2 = po2_quantize(self.skip_weight)
        skip_curr = torch.nn.functional.linear(spikes_0, skip_po2)
        raw_out = self.layer_out(spikes_1) + skip_curr
        return raw_out, spikes_1

    def forward_step(self, x_norm):
        raw_out = None
        for _ in range(self.n_ticks):
            raw_out, _ = self._tick(x_norm)
        return self._decode_params(raw_out)

    def forward_sequence_with_stats(self, x_seq_norm):
        batch, T_len, _ = x_seq_norm.shape
        self.reset_state(batch, x_seq_norm.device)
        steps, spikes = [], []
        for t in range(T_len):
            x_t = x_seq_norm[:, t, :]
            raw_out = None
            spike_h_acc = torch.zeros(batch, self.hidden_sizes[1], device=x_t.device)
            for _ in range(self.n_ticks):
                raw_out, spikes_1 = self._tick(x_t)
                spike_h_acc = spike_h_acc + spikes_1.float()
            spike_h_rate = spike_h_acc / self.n_ticks
            spikes.append(spike_h_rate.mean(dim=1, keepdim=True))
            steps.append(self._decode_params(raw_out).unsqueeze(1))
        return torch.cat(steps, dim=1), torch.cat(spikes, dim=1)


# -----------------------------------------------------------------
# A6 — Multi-rate ALIF (INNOVATION 1)
# -----------------------------------------------------------------


# =================================================================
# build_model factory -- ristretta per Arch_Tested
# =================================================================
def build_model(variant='stacked_2_skip', hidden_size=None, rank=None,
                max_delay=None, **kwargs):
    """Factory ristretta per A3_stacked_skip_BPTT_2624p. Solo 'stacked_2_skip'."""
    v = variant.lower()
    if v == 'stacked_2_skip':
        h = hidden_size or 32; r = rank or 8
        return CF_FSNN_Net_StackedSkip(n_hidden=2, hidden_sizes=[h, h], ranks=[r, r])
    raise ValueError("Variant '%s' non supportata in A3. Solo: stacked_2_skip" % variant)
