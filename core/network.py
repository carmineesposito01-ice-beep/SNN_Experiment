import torch
import torch.nn as nn
from collections import deque    # F8: ring-buffer O(1) per delay assonali
from core.hardware import po2_quantize
from core.neurons import ALIFCell, LICell

class HiddenLayer_ALIF(nn.Module):
    def __init__(self, in_features, out_features, rank=16, max_delay=3, bit_shift=3):
        """R25: bit_shift esposto per ablation asse A5 (LIF leak τ vs default 3).
        Propagato ad ALIFCell come scalare (uniform leak per tutti i neuroni)."""
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.max_delay = max_delay

        self.fc_weight = nn.Parameter(torch.Tensor(out_features, in_features))
        nn.init.xavier_uniform_(self.fc_weight)
        # FIX-BUG-4 (2026-06-03): compensa penalty 1/max_delay della delay mask.
        # In forward, current = Σ_d linear(x_buffer[d], w * (delays==d)). Ogni edge
        # contribuisce solo 1/max_delay del tempo → var(current) ridotta di
        # 1/max_delay rispetto a un fc layer normale. Scalare i pesi di
        # sqrt(max_delay) ripristina la varianza target di Xavier.
        # Vedi document/BUGS_2026-06-03.md criticità #4.
        with torch.no_grad():
            self.fc_weight.mul_(max_delay ** 0.5)
        self.register_buffer('delays', torch.randint(0, max_delay, (out_features, in_features)))

        self.rec_U = nn.Parameter(torch.Tensor(out_features, rank))
        self.rec_V = nn.Parameter(torch.Tensor(rank, out_features))
        nn.init.orthogonal_(self.rec_U, gain=0.2)
        nn.init.orthogonal_(self.rec_V, gain=0.2)

        self.x_buffer = None
        self.cell = ALIFCell(out_features, bit_shift=bit_shift)

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
        # Con input spike binari {0,1} a firing rate basso, ogni riga senza
        # mean-subtraction crea un offset deterministico nel current → asimmetria
        # tra canali di output → combinata con sigmoid determina QUALE bound IDM
        # viene saturato. Vedi document/BUGS_2026-06-03.md bug #2.
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


class Deep_SNN_V5_1(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer_hidden = HiddenLayer_ALIF(784, 128, rank=16, max_delay=3)
        self.layer_out = OutputLayer_LI(128, 10)

    def forward_tick(self, x):
        spikes_h = self.layer_hidden(x)
        out = self.layer_out(spikes_h)
        return out, spikes_h


# ============================================================
# CNN Equivalente per Confronto
# ============================================================
from core.neurons import CNNBlock

class Deep_CNN_V5(nn.Module):
    """CNN classica per MNIST, strutturalmente equivalente alla SNN.
    - 2 blocchi convoluzionali (analoghi al layer hidden ALIF)
    - 1 fully-connected di output (analogo al layer output LI)
    """

    def __init__(self, num_classes=10):
        super().__init__()
        # Feature extractor: 1->16 (28x28->14x14) -> 16->32 (14x14->7x7)
        self.conv1 = CNNBlock(1, 16, kernel_size=3, padding=1, pool=True)
        self.conv2 = CNNBlock(16, 32, kernel_size=3, padding=1, pool=True)
        # Classifier: 32*7*7 = 1568 -> 128 -> 10
        self.fc_hidden = nn.Linear(32 * 7 * 7, 128)
        self.relu = nn.ReLU(inplace=True)
        self.fc_out = nn.Linear(128, num_classes)

    def forward(self, x):
        """Forward standard per addestramento CNN.
        x: (batch, 1, 28, 28)"""
        h = self.conv1(x)
        h = self.conv2(h)
        h = h.view(h.size(0), -1)      # flatten
        h_act = self.relu(self.fc_hidden(h))
        out = self.fc_out(h_act)
        return out, h_act

    def forward_tick(self, x_flat):
        """Adapter per compatibilità con il loop di simulazione SNN.
        x_flat: (batch, 784) -> reshape a (batch, 1, 28, 28)"""
        x_2d = x_flat.view(-1, 1, 28, 28)
        return self.forward(x_2d)

class Simple_ANN_V5(nn.Module):
    """ANN classica (MLP superficiale) per MNIST.
    Design: 784 -> 128 (ReLU) -> 10
    """
    def __init__(self, in_features=784, hidden_features=128, out_features=10):
        super().__init__()
        self.fc_hidden = nn.Linear(in_features, hidden_features)
        self.relu = nn.ReLU(inplace=True)
        self.fc_out = nn.Linear(hidden_features, out_features)

    def forward(self, x):
        h = x.view(x.size(0), -1)
        h_act = self.relu(self.fc_hidden(h))
        out = self.fc_out(h_act)
        return out, h_act

    def forward_tick(self, x_flat):
        return self.forward(x_flat)

class Deep_DNN_V5(nn.Module):
    """DNN profonda (MLP multistrato) per MNIST.
    Design: 784 -> 256 (ReLU) -> 128 (ReLU) -> 10
    """
    def __init__(self, in_features=784, h1=256, h2=128, out_features=10):
        super().__init__()
        self.fc1 = nn.Linear(in_features, h1)
        self.fc2 = nn.Linear(h1, h2)
        self.relu = nn.ReLU(inplace=True)
        self.fc_out = nn.Linear(h2, out_features)

    def forward(self, x):
        h = x.view(x.size(0), -1)
        h1_act = self.relu(self.fc1(h))
        h2_act = self.relu(self.fc2(h1_act))
        out = self.fc_out(h2_act)
        return out, h2_act

    def forward_tick(self, x_flat):
        return self.forward(x_flat)


# ============================================================
# RECURRENT SPIKING NEURAL NETWORK (RSNN) - Versione Full
# ============================================================
from core.neurons import RS_ALIFCell

class RSNN_HiddenLayer(nn.Module):
    """
    Layer Hidden per RSNN con Ricorrenza Full-Matrix.
    A differenza del layer ALIF standard (low-rank), questo usa una matrice
    di pesi ricorrenti completa [out_features x out_features].
    """
    def __init__(self, in_features, out_features, max_delay=3):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.max_delay = max_delay

        # Pesi Feedforward (con ritardi come nella SNN standard)
        self.fc_weight = nn.Parameter(torch.Tensor(out_features, in_features))
        nn.init.xavier_uniform_(self.fc_weight)
        # FIX-BUG-4 (2026-06-03): compensa penalty 1/max_delay della delay mask.
        # In forward, current = Σ_d linear(x_buffer[d], w * (delays==d)). Ogni edge
        # contribuisce solo 1/max_delay del tempo → var(current) ridotta di
        # 1/max_delay rispetto a un fc layer normale. Scalare i pesi di
        # sqrt(max_delay) ripristina la varianza target di Xavier.
        # Vedi document/BUGS_2026-06-03.md criticità #4.
        with torch.no_grad():
            self.fc_weight.mul_(max_delay ** 0.5)
        self.register_buffer('delays', torch.randint(0, max_delay, (out_features, in_features)))

        # Pesi Ricorrenti Full (Matrice quadrata N x N)
        self.rec_weight = nn.Parameter(torch.Tensor(out_features, out_features))
        nn.init.orthogonal_(self.rec_weight, gain=0.2)

        self.x_buffer = None
        self.cell = RS_ALIFCell(out_features)

    def reset_state(self, batch_size, device):
        self.x_buffer = [torch.zeros(batch_size, self.in_features, device=device) for _ in range(self.max_delay)]
        self.cell.reset_state(batch_size, device)

    def forward(self, x, feedback_current=0):
        if self.x_buffer is None:
            self.reset_state(x.size(0), x.device)

        self.x_buffer.insert(0, x)
        self.x_buffer.pop()

        # Quantizzazione HW-Friendly (Power-of-Two)
        w_po2 = po2_quantize(self.fc_weight)
        w_rec_po2 = po2_quantize(self.rec_weight)

        # Corrente Feedforward con Delayed Synapses
        current = torch.zeros(x.size(0), self.out_features, device=x.device)
        for d in range(self.max_delay):
            mask_d = (self.delays == d).float()
            current += torch.nn.functional.linear(self.x_buffer[d], w_po2 * mask_d)

        # Corrente Ricorrente (Full Matrix)
        rec_curr = torch.nn.functional.linear(self.cell.prev_spike, w_rec_po2)

        # Somma di tutte le correnti (FF + REC + FEEDBACK)
        return self.cell(current, rec_curr + feedback_current)


class Deep_RSNN_V5(nn.Module):
    """
    Architettura RSNN Profonda.
    Include:
    - Layer Hidden con ricorrenza interna Full.
    - Layer Output (LI) con Feedback Globale verso l'hidden.
    """
    def __init__(self):
        super().__init__()
        self.layer_hidden = RSNN_HiddenLayer(784, 128, max_delay=3)
        self.layer_out = OutputLayer_LI(128, 10)

        # Pesi di Feedback Globale (Output -> Hidden)
        self.feedback_w = nn.Parameter(torch.Tensor(128, 10))
        nn.init.normal_(self.feedback_w, mean=0, std=0.01)

        self.prev_output = None

    def reset_state(self, batch_size, device):
        self.layer_hidden.reset_state(batch_size, device)
        self.layer_out.reset_state(batch_size, device)
        self.prev_output = torch.zeros(batch_size, 10, device=device)

    def forward_tick(self, x):
        if self.prev_output is None:
            self.reset_state(x.size(0), x.device)

        fb_quant = po2_quantize(self.feedback_w)
        feedback_current = torch.nn.functional.linear(self.prev_output, fb_quant)
        spikes_h = self.layer_hidden(x, feedback_current)
        out = self.layer_out(spikes_h)
        self.prev_output = out.detach()

        return out, spikes_h


# ===========================================================
# CF_FSNN_Net — Car-Following SNN con training PINN
# Adattamento di FSNN_V5 per ACC-IDM (con base IIDM) + V2X + PYNQ-Z1
# Modello fisico: Ch12 Sez.12.4 Treiber & Kesting 2025
# ===========================================================
import math as _math


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

    def __init__(self, hidden_size=None, rank=None, max_delay=None, bit_shift=None):
        """
        Args:
            hidden_size: override CF_HIDDEN_SIZE (None → usa config). Per STEP 2B sweep.
            rank: override CF_RANK (None → usa config). Per STEP 2B sweep.
            max_delay: override CF_MAX_DELAY (None → usa config). Per STEP 2E A5 variant.
            bit_shift: override leak (None → default ALIFCell=3). R25 ablation asse A5/A6.
        """
        super().__init__()
        from config import (
            CF_INPUT_SIZE, CF_HIDDEN_SIZE, CF_OUTPUT_SIZE,
            CF_RANK, CF_MAX_DELAY, TICKS_PER_STEP,
            IDM2D_T1, IDM2D_T2, IDM2D_TAU, DT,
        )

        # STEP 2B: capacity override via kwargs (None → fallback su config).
        # STEP 2E A5: max_delay override per variant max_delay_12.
        # R25: bit_shift override per ablation asse A5/A6 (default 3 in ALIFCell).
        hidden_size = hidden_size if hidden_size is not None else CF_HIDDEN_SIZE
        rank        = rank        if rank        is not None else CF_RANK
        max_delay   = max_delay   if max_delay   is not None else CF_MAX_DELAY
        bit_shift   = bit_shift   if bit_shift   is not None else 3
        self.hidden_size = hidden_size   # esposto per logging/diagnostica
        self.rank        = rank
        self.max_delay   = max_delay
        self.bit_shift   = bit_shift

        self.n_ticks  = TICKS_PER_STEP
        self.T1       = IDM2D_T1
        self.T2       = IDM2D_T2
        self.T_mean   = (IDM2D_T1 + IDM2D_T2) / 2.0
        # α = exp(-Δt / τ_OU): costante mean-reversion per loss OU  (≈ 0.9967)
        self.ou_alpha = _math.exp(-DT / IDM2D_TAU)

        self.layer_hidden = HiddenLayer_ALIF(
            CF_INPUT_SIZE, hidden_size,
            rank=rank, max_delay=max_delay, bit_shift=bit_shift,
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

        # R29 — DecoderFix buffer:
        #   decode_offset (5,): sottratto a raw_logits PRIMA del sigmoid. Default 0
        #     = backward-compat. Quando calibrato via calibrate_decode_offset() rimuove
        #     l'asimmetria osservata empiricamente (v0_pred=37 ep1 invece di midpoint 27.5,
        #     vedi document/BUGS_2026-06-03.md fix #2 incompleto).
        #   logit_tau (5,): temperatura della sigmoid PER-CANALE. sigmoid(raw / tau).
        #     tau=1 = identità, tau>1 = sigmoid piu' "piatta" (zona lineare estesa),
        #     tau<1 = sigmoid piu' "ripida". Default 1 = backward-compat. Annealed
        #     via set_logit_tau() ad ogni epoch dal training loop (R29 DEC-1).
        self.register_buffer('decode_offset', torch.zeros(5, dtype=torch.float32))
        self.register_buffer('logit_tau',     torch.ones(5, dtype=torch.float32))

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

        FIX-BUG-1 (2026-06-03): rimosso F5 pre-scaling (raw_eq = raw / decode_scale).
        decode_scale = [1.0, 0.054, 0.108, 0.0594, 0.0676] amplificava raw di 9-18×
        per T/s0/a/b → raw_eq cadeva fuori dalla zona lineare di sigmoid →
        derivata ≈ 0 → gradient → 0 → params bloccati al random init.
        Vedi document/BUGS_2026-06-03.md bug #1.

        Il buffer `decode_scale` resta registrato per compat con eventuali
        checkpoint salvati, ma non è più usato.

        R29 DEC-1/DEC-3 (2026-06-12): applica decode_offset + logit_tau.
          (raw - decode_offset[i]) / logit_tau[i] poi sigmoid.
          Con default decode_offset=0, logit_tau=1: comportamento identico al pre-R29.
        """
        # R29 decode_offset/logit_tau: getattr-safe per varianti che NON li registrano
        # (es. EventProp, pre-R29). Assenti -> offset 0 / tau 1 = comportamento pre-R29 identico.
        off = self.decode_offset if hasattr(self, 'decode_offset') else 0.0
        tau = self.logit_tau if hasattr(self, 'logit_tau') else 1.0
        adj = (raw - off) / tau
        return self.param_lo + (self.param_hi - self.param_lo) * torch.sigmoid(adj)

    # ----------------------------------------------------------
    # R29 — Decoder calibration / tau scheduling
    # ----------------------------------------------------------
    @torch.no_grad()
    def calibrate_decode_offset(self, x_sample):
        """R29 DEC-3 (init_bias_shift): centra raw output su 0.

        Misura il raw output medio (pre-sigmoid, post-LI) su un campione di input,
        poi imposta decode_offset = raw_mean. Dopo la calibrazione, _decode_params
        produce sigmoid(0) = 0.5 in media → params al midpoint dei bound al t=0.

        Sostituisce il pattern fix-#2 (row-mean subtraction post Xavier) che era
        incompleto: rimuoveva solo la componente DI BIAS pura dei pesi ma non
        l'asimmetria emergente dall'interazione (spike rate non uniforme × pesi
        per-riga × n_ticks accumulazione).

        x_sample: (batch, T, 4) input normalizzati (es. primo batch del train_loader).
        """
        was_training = self.training
        self.eval()
        self.reset_state(x_sample.size(0), x_sample.device)
        raw_collected = []
        for t in range(x_sample.size(1)):
            raw_out = None
            for _ in range(self.n_ticks):
                spikes_h = self.layer_hidden(x_sample[:, t, :])
                raw_out  = self.layer_out(spikes_h)
            raw_collected.append(raw_out)
        # (T, batch, 5) → mean over T+batch = (5,)
        raw_stack = torch.stack(raw_collected, dim=0)
        self.decode_offset.copy_(raw_stack.mean(dim=(0, 1)))
        if was_training:
            self.train()

    def set_logit_tau(self, tau):
        """R29 DEC-1 (logit τ-annealing): aggiorna temperatura sigmoid.

        tau può essere:
          - float / 0-d tensor → applicato a tutti i 5 canali
          - 1-d tensor / iterable di lunghezza 5 → per-channel
        """
        if isinstance(tau, (int, float)):
            self.logit_tau.fill_(float(tau))
        else:
            t = torch.as_tensor(tau, dtype=torch.float32, device=self.logit_tau.device)
            if t.numel() == 1:
                self.logit_tau.fill_(float(t.item()))
            else:
                assert t.numel() == 5, f'logit_tau deve essere scalare o vettore len-5 (got {t.numel()})'
                self.logit_tau.copy_(t.view(5))

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
class CF_FSNN_Net_Stacked(_CF_FSNN_VariantBase):
    """N layer ALIF stacked + LI output (PINN-compatible).

    Args:
        n_hidden: numero layer ALIF consecutivi (≥2 usato in A2=2, A4=3).
        hidden_sizes: lista (n_hidden,) di neuroni per layer.
        ranks: lista (n_hidden,) di rank low-rank per layer.
        max_delay: max axonal delay (default config).
    """

    def __init__(self, n_hidden=2, hidden_sizes=None, ranks=None, max_delay=None):
        # hidden_size esposto = primo layer (per logging coerenza)
        hidden_sizes = hidden_sizes or [32] * n_hidden
        ranks        = ranks        or [8]  * n_hidden
        assert len(hidden_sizes) == n_hidden, "hidden_sizes deve avere len = n_hidden"
        assert len(ranks)        == n_hidden, "ranks deve avere len = n_hidden"
        super().__init__(hidden_size=hidden_sizes[0], max_delay=max_delay)
        self.n_hidden     = n_hidden
        self.hidden_sizes = hidden_sizes
        self.ranks        = ranks
        # rank esposto = primo layer (per logging coerenza)
        self.rank = ranks[0]

        # Layer 0: input = CF_INPUT_SIZE → hidden_sizes[0]
        # Layer i: input = hidden_sizes[i-1] → hidden_sizes[i]
        layers = []
        in_dim = self.CF_INPUT_SIZE
        for i in range(n_hidden):
            layers.append(HiddenLayer_ALIF(
                in_dim, hidden_sizes[i],
                rank=ranks[i], max_delay=self.max_delay,
            ))
            in_dim = hidden_sizes[i]
        self.layers_hidden = nn.ModuleList(layers)
        self.layer_out = OutputLayer_LI(hidden_sizes[-1], self.CF_OUTPUT_SIZE)
        # FIX-BUG-3 (2026-06-03): abbassa base_threshold per layer ALIF non-input.
        # In una cascata, layer i>0 riceve spike binari sparsi del layer i-1
        # → current piccolo → potential non raggiunge base_threshold=1.5 →
        # dead cascade. Threshold 1.0 garantisce propagazione del segnale.
        # Vedi document/BUGS_2026-06-03.md criticità #3.
        for i, layer in enumerate(self.layers_hidden):
            if i > 0:
                with torch.no_grad():
                    layer.cell.base_threshold.fill_(1.0)

    def reset_state(self, batch_size, device):
        for layer in self.layers_hidden:
            layer.reset_state(batch_size, device)
        self.layer_out.reset_state(batch_size, device)

    def forward_step(self, x_norm):
        raw_out = None
        for _ in range(self.n_ticks):
            h = x_norm
            for layer in self.layers_hidden:
                h = layer(h)
            raw_out = self.layer_out(h)
        return self._decode_params(raw_out)

    def forward_sequence_with_stats(self, x_seq_norm):
        """Spike rate riportato sull'ULTIMO hidden layer (più informativo per diagnosi)."""
        batch, T_len, _ = x_seq_norm.shape
        self.reset_state(batch, x_seq_norm.device)
        last_hidden_size = self.hidden_sizes[-1]
        steps, spikes = [], []
        for t in range(T_len):
            x_t = x_seq_norm[:, t, :]
            raw_out = None
            spike_h_acc = torch.zeros(batch, last_hidden_size, device=x_t.device)
            for _ in range(self.n_ticks):
                h = x_t
                for layer in self.layers_hidden:
                    h = layer(h)
                spike_h_acc = spike_h_acc + h.float()
                raw_out = self.layer_out(h)
            spike_h_rate = spike_h_acc / self.n_ticks
            spikes.append(spike_h_rate.mean(dim=1, keepdim=True))
            steps.append(self._decode_params(raw_out).unsqueeze(1))
        return torch.cat(steps, dim=1), torch.cat(spikes, dim=1)


# -----------------------------------------------------------------
# A3 — Stacked 2-hidden + MS-style membrane skip
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
        # layer_hidden_1 riceve spike binari sparsi da layer_hidden_0 → current
        # piccolo → potential non raggiunge base_threshold=1.5 → dead cascade.
        # Threshold 1.0 garantisce propagazione. Skip Po2 NON sostituisce il fix:
        # bypassa solo l'output, layer_hidden_1 va comunque sbloccato.
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
class _HiddenLayer_ALIF_MultiRate(nn.Module):
    """Variante di HiddenLayer_ALIF dove il singolo ALIFCell ha bit_shift per-neurone.

    Group split: divide hidden_size in N gruppi (≈uguali), assegna bit_shifts[i]
    al gruppo i-esimo. Tutti i bit_shift sono interi (potenze di 2 hardware-friendly).
    """

    def __init__(self, in_features, out_features, rank=8, max_delay=6, bit_shifts=(2, 3, 4)):
        super().__init__()
        self.in_features  = in_features
        self.out_features = out_features
        self.max_delay    = max_delay

        self.fc_weight = nn.Parameter(torch.Tensor(out_features, in_features))
        nn.init.xavier_uniform_(self.fc_weight)
        # FIX-BUG-4 (2026-06-03): compensa penalty 1/max_delay della delay mask.
        # In forward, current = Σ_d linear(x_buffer[d], w * (delays==d)). Ogni edge
        # contribuisce solo 1/max_delay del tempo → var(current) ridotta di
        # 1/max_delay rispetto a un fc layer normale. Scalare i pesi di
        # sqrt(max_delay) ripristina la varianza target di Xavier.
        # Vedi document/BUGS_2026-06-03.md criticità #4.
        with torch.no_grad():
            self.fc_weight.mul_(max_delay ** 0.5)
        self.register_buffer('delays', torch.randint(0, max_delay, (out_features, in_features)))

        self.rec_U = nn.Parameter(torch.Tensor(out_features, rank))
        self.rec_V = nn.Parameter(torch.Tensor(rank, out_features))
        nn.init.orthogonal_(self.rec_U, gain=0.2)
        nn.init.orthogonal_(self.rec_V, gain=0.2)

        # Per-neuron bit_shift: divide out_features in len(bit_shifts) gruppi.
        n_groups = len(bit_shifts)
        per_group = out_features // n_groups
        bs_vec = []
        for i, bs in enumerate(bit_shifts):
            if i < n_groups - 1:
                bs_vec.extend([bs] * per_group)
            else:
                # ultimo gruppo prende il resto (compensa divisione non esatta)
                bs_vec.extend([bs] * (out_features - len(bs_vec)))
        assert len(bs_vec) == out_features

        self.x_buffer = None
        self.cell = ALIFCell(out_features, bit_shift=bs_vec)

    def reset_state(self, batch_size, device):
        self.x_buffer = deque(
            [torch.zeros(batch_size, self.in_features, device=device)
             for _ in range(self.max_delay)],
            maxlen=self.max_delay,
        )
        self.cell.reset_state(batch_size, device)

    def forward(self, x):
        if self.x_buffer is None:
            self.reset_state(x.size(0), x.device)
        self.x_buffer.appendleft(x)

        w_po2 = po2_quantize(self.fc_weight)
        u_po2 = po2_quantize(self.rec_U)
        v_po2 = po2_quantize(self.rec_V)

        current = torch.zeros(x.size(0), self.out_features, device=x.device)
        for d in range(self.max_delay):
            mask_d = (self.delays == d).float()
            current += torch.nn.functional.linear(self.x_buffer[d], w_po2 * mask_d)

        rec_int  = torch.nn.functional.linear(self.cell.prev_spike, v_po2)
        rec_curr = torch.nn.functional.linear(rec_int, u_po2)
        return self.cell(current, rec_curr)


class CF_FSNN_Net_MultiRate(_CF_FSNN_VariantBase):
    """1 hidden ALIF con 3 gruppi (bit_shifts=[2,3,4]) + LI output.

    Crea gerarchia temporale intrinseca senza aumentare layer count.
    """

    def __init__(self, hidden_size=32, rank=8, max_delay=None, bit_shifts=(2, 3, 4)):
        super().__init__(hidden_size=hidden_size, max_delay=max_delay)
        self.rank        = rank
        self.bit_shifts  = bit_shifts

        self.layer_hidden = _HiddenLayer_ALIF_MultiRate(
            self.CF_INPUT_SIZE, hidden_size,
            rank=rank, max_delay=self.max_delay, bit_shifts=bit_shifts,
        )
        self.layer_out = OutputLayer_LI(hidden_size, self.CF_OUTPUT_SIZE)

    def reset_state(self, batch_size, device):
        self.layer_hidden.reset_state(batch_size, device)
        self.layer_out.reset_state(batch_size, device)

    def forward_step(self, x_norm):
        raw_out = None
        for _ in range(self.n_ticks):
            spikes_h = self.layer_hidden(x_norm)
            raw_out  = self.layer_out(spikes_h)
        return self._decode_params(raw_out)

    def forward_sequence_with_stats(self, x_seq_norm):
        batch, T_len, _ = x_seq_norm.shape
        self.reset_state(batch, x_seq_norm.device)
        steps, spikes = [], []
        for t in range(T_len):
            x_t = x_seq_norm[:, t, :]
            raw_out = None
            spike_h_acc = torch.zeros(batch, self.hidden_size, device=x_t.device)
            for _ in range(self.n_ticks):
                spike_h = self.layer_hidden(x_t)
                raw_out = self.layer_out(spike_h)
                spike_h_acc = spike_h_acc + spike_h.float()
            spike_h_rate = spike_h_acc / self.n_ticks
            spikes.append(spike_h_rate.mean(dim=1, keepdim=True))
            steps.append(self._decode_params(raw_out).unsqueeze(1))
        return torch.cat(steps, dim=1), torch.cat(spikes, dim=1)


# -----------------------------------------------------------------
# A7 — WTA inhibition pool
# -----------------------------------------------------------------
class CF_FSNN_Net_WTA(_CF_FSNN_VariantBase):
    """Baseline + 1 neurone inibitorio Po2-quantizzato (lateral inhibition).

    L'inibitore riceve dalla somma dei spike hidden (peso Po2) e ridistribuisce
    inibizione uniforme su tutti gli hidden al tick successivo (delay 1).
    Forza sparsità e competizione (ch05.3 + ch05.6).
    """

    def __init__(self, hidden_size=32, rank=8, max_delay=None, inh_strength=0.5):
        super().__init__(hidden_size=hidden_size, max_delay=max_delay)
        self.rank         = rank
        self.inh_strength = inh_strength

        self.layer_hidden = HiddenLayer_ALIF(
            self.CF_INPUT_SIZE, hidden_size,
            rank=rank, max_delay=self.max_delay,
        )
        self.layer_out = OutputLayer_LI(hidden_size, self.CF_OUTPUT_SIZE)

        # 1 weight: hidden_size → 1 (collector). Broadcast a (hidden_size,) come inibizione.
        self.inh_w_in = nn.Parameter(torch.Tensor(1, hidden_size))
        nn.init.xavier_uniform_(self.inh_w_in)
        with torch.no_grad():
            self.inh_w_in.mul_(0.2)
        # Inh state: 1 scalare per batch
        self.inh_state = None

    def reset_state(self, batch_size, device):
        self.layer_hidden.reset_state(batch_size, device)
        self.layer_out.reset_state(batch_size, device)
        self.inh_state = torch.zeros(batch_size, 1, device=device)

    def _tick(self, x_norm):
        # Iniezione inibizione del tick precedente: sottrae a TUTTI gli hidden
        # tramite la corrente esterna additiva (qui simulata con un boost negativo
        # passato attraverso il primo input). Pattern KISS: inhibition ridotta sui spike.
        # Implementazione semplice: applichiamo l'inibizione DIRETTAMENTE sulla soglia
        # incrementale del ALIFCell — ma serve dispatch più invasivo. Approccio più pulito:
        # inhibition come termine sottratto dalla corrente ricorrente. Lo facciamo iniettando
        # un additivo negativo a x_norm prima del layer (= driving force ridotta).
        # Però x_norm è (batch,4), hidden è (batch,32). Soluzione: aggiungiamo dopo il layer.

        spikes_h = self.layer_hidden(x_norm)
        # Sottrazione lateral inhibition (broadcast su hidden)
        spikes_h_inhibited = spikes_h - self.inh_strength * self.inh_state  # (batch, hidden)
        # Clamp ≥ 0: spike sono bool, ma post-inhibition è float → equivalente a "weakened spikes"
        spikes_h_inhibited = torch.clamp(spikes_h_inhibited, min=0.0)

        raw_out = self.layer_out(spikes_h_inhibited)

        # Update inh_state: collector Po2-quantizzato sui spike correnti
        inh_w_po2 = po2_quantize(self.inh_w_in)
        self.inh_state = torch.nn.functional.linear(spikes_h, inh_w_po2).detach()
        # detach per evitare grafo BPTT esplodente sul collector (ch22)
        return raw_out, spikes_h_inhibited

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
            spike_h_acc = torch.zeros(batch, self.hidden_size, device=x_t.device)
            for _ in range(self.n_ticks):
                raw_out, sp = self._tick(x_t)
                spike_h_acc = spike_h_acc + sp.float()
            spike_h_rate = spike_h_acc / self.n_ticks
            spikes.append(spike_h_rate.mean(dim=1, keepdim=True))
            steps.append(self._decode_params(raw_out).unsqueeze(1))
        return torch.cat(steps, dim=1), torch.cat(spikes, dim=1)


# -----------------------------------------------------------------
# A8 — Spike-driven attention lite (INNOVATION 2)
# -----------------------------------------------------------------
class CF_FSNN_Net_Attn(_CF_FSNN_VariantBase):
    """Baseline + spike attention lite (Q/K/V Po2, n_heads, no softmax).

    Tra hidden ALIF e LI output inseriamo:
        Q = po2_quant(Wq) @ spikes_h    shape (batch, hidden)
        K = po2_quant(Wk) @ spikes_h    shape (batch, hidden)
        V = po2_quant(Wv) @ spikes_h    shape (batch, hidden)
        score = sigmoid(sum(Q*K, dim=heads) / scale)
        attn  = score * V    (element-wise gating, no softmax)
        out   = LI(attn)

    Pattern Spikformer-lite (ch05.11, ch21). Tutti i weight Po2 → FPGA-friendly.
    """

    def __init__(self, hidden_size=32, rank=8, max_delay=None, n_heads=2):
        super().__init__(hidden_size=hidden_size, max_delay=max_delay)
        self.rank    = rank
        self.n_heads = n_heads
        assert hidden_size % n_heads == 0, "hidden_size deve essere multiplo di n_heads"
        self.head_dim = hidden_size // n_heads

        self.layer_hidden = HiddenLayer_ALIF(
            self.CF_INPUT_SIZE, hidden_size,
            rank=rank, max_delay=self.max_delay,
        )

        self.Wq = nn.Parameter(torch.Tensor(hidden_size, hidden_size))
        self.Wk = nn.Parameter(torch.Tensor(hidden_size, hidden_size))
        self.Wv = nn.Parameter(torch.Tensor(hidden_size, hidden_size))
        for w in (self.Wq, self.Wk, self.Wv):
            nn.init.xavier_uniform_(w)
            with torch.no_grad():
                w.mul_(0.5)

        self.layer_out = OutputLayer_LI(hidden_size, self.CF_OUTPUT_SIZE)
        self.attn_scale = float(self.head_dim) ** 0.5

    def reset_state(self, batch_size, device):
        self.layer_hidden.reset_state(batch_size, device)
        self.layer_out.reset_state(batch_size, device)

    def _attn(self, spikes_h):
        """Applica attention block ai spike hidden. Output stesso shape di spikes_h."""
        wq = po2_quantize(self.Wq); wk = po2_quantize(self.Wk); wv = po2_quantize(self.Wv)
        Q = torch.nn.functional.linear(spikes_h, wq)   # (B, H)
        K = torch.nn.functional.linear(spikes_h, wk)
        V = torch.nn.functional.linear(spikes_h, wv)
        # Split heads: (B, n_heads, head_dim)
        B, H = Q.shape
        Q = Q.view(B, self.n_heads, self.head_dim)
        K = K.view(B, self.n_heads, self.head_dim)
        V = V.view(B, self.n_heads, self.head_dim)
        # Score element-wise per head (no softmax): sigmoid(Q*K / sqrt(d))
        score = torch.sigmoid((Q * K).sum(dim=-1, keepdim=True) / self.attn_scale)  # (B, n_heads, 1)
        attn  = (score * V).view(B, H)
        return attn

    def _tick(self, x_norm):
        spikes_h = self.layer_hidden(x_norm)
        attn_out = self._attn(spikes_h)
        raw_out  = self.layer_out(attn_out)
        return raw_out, spikes_h

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
            spike_h_acc = torch.zeros(batch, self.hidden_size, device=x_t.device)
            for _ in range(self.n_ticks):
                raw_out, sp = self._tick(x_t)
                spike_h_acc = spike_h_acc + sp.float()
            spike_h_rate = spike_h_acc / self.n_ticks
            spikes.append(spike_h_rate.mean(dim=1, keepdim=True))
            steps.append(self._decode_params(raw_out).unsqueeze(1))
        return torch.cat(steps, dim=1), torch.cat(spikes, dim=1)


# =================================================================
# STEP 2E — Factory build_model
# =================================================================
# CLEANUP 2026-06-01 (audit utente): rimosse architetture "fake" che non
# replicavano A1 fairly (F2.0=LIF puro stripped, F2.1=ALIF stripped, F2.2=LIF
# rec full stripped). Mantenute solo due varianti EventProp ben definite:
#
#   * CF_FSNN_Net_EventProp_LIF_Simple  -- F2.0b reference LIF semplice.
#     Validazione "EventProp adjoint funziona" senza altri confounder.
#     Pure LIF feedforward, NO Po2, NO delays, NO recurrence, NO ALIF.
#
#   * CF_FSNN_Net_EventProp_Full        -- LA TUA A1 con EventProp adjoint.
#     Replica al 100% l'architettura A1 (Po2 + delays + n_ticks=10 +
#     bit-shift leak + ALIF adaptive threshold + low-rank rec), cambia
#     SOLO il training method (EventProp invece di BPTT+surrogate).
#     Confronto fair vs baseline.
#
# Vedi document/EVENTPROP_DESIGN.md.

from core.eventprop import (LIFLayer_EventProp, LIFLayer_BPTT_Simple,
                             ALIFLayer_EventProp_Full,
                             LILayer_Standard, LILayer_BitShift_Po2)


class CF_FSNN_Net_BPTT_LIF_Simple(CF_FSNN_Net):
    """LIF semplice con BPTT+surrogate -- gemello di CF_FSNN_Net_EventProp_LIF_Simple.

    Architettura IDENTICA a CF_FSNN_Net_EventProp_LIF_Simple ma training BPTT.
    Per 2x2 ablation: (BPTT vs EventProp) x (LIF vs ALIF).
    """

    def __init__(self, hidden_size=None, rank=None, max_delay=None):
        nn.Module.__init__(self)
        from config import (
            CF_INPUT_SIZE, CF_HIDDEN_SIZE, CF_OUTPUT_SIZE,
            CF_RANK, CF_MAX_DELAY, IDM2D_T1, IDM2D_T2, IDM2D_TAU, DT,
        )
        hidden_size = hidden_size if hidden_size is not None else CF_HIDDEN_SIZE
        self.hidden_size = hidden_size
        self.rank      = rank if rank is not None else CF_RANK
        self.max_delay = max_delay if max_delay is not None else CF_MAX_DELAY
        self.n_ticks  = 1
        self.T1       = IDM2D_T1
        self.T2       = IDM2D_T2
        self.T_mean   = (IDM2D_T1 + IDM2D_T2) / 2.0
        self.ou_alpha = _math.exp(-DT / IDM2D_TAU)

        # BPTT LIF + LI standard (matches LIF EventProp version)
        self.layer_hidden = LIFLayer_BPTT_Simple(
            in_features=CF_INPUT_SIZE, out_features=hidden_size)
        self.layer_out = LILayer_Standard(
            in_features=hidden_size, out_features=CF_OUTPUT_SIZE)

        bounds = torch.tensor(self._PARAM_BOUNDS, dtype=torch.float32)
        self.register_buffer('param_lo', bounds[:, 0])
        self.register_buffer('param_hi', bounds[:, 1])
        ranges = bounds[:, 1] - bounds[:, 0]
        self.register_buffer('decode_scale', ranges / ranges.max())

    def reset_state(self, batch_size, device):
        pass

    def forward_sequence_with_stats(self, x_seq_norm):
        spikes_h = self.layer_hidden(x_seq_norm)
        raw_out  = self.layer_out(spikes_h)
        B, T, _ = raw_out.shape
        flat = raw_out.reshape(B * T, -1)
        params_seq = self._decode_params(flat).reshape(B, T, -1)
        spike_rate = spikes_h.mean(dim=2)
        return params_seq, spike_rate

    def forward_sequence(self, x_seq_norm):
        return self.forward_sequence_with_stats(x_seq_norm)[0]


class CF_FSNN_Net_EventProp_LIF_Simple(CF_FSNN_Net):
    """F2.0b reference: LIF puro EventProp -- NON replica A1.

    Usata SOLO come reference "EventProp funziona su LIF semplice".
    Architettura stripped: NO Po2, NO delays, NO recurrence, NO ALIF, n_ticks=1.
    """

    def __init__(self, hidden_size=None, rank=None, max_delay=None):
        nn.Module.__init__(self)
        from config import (
            CF_INPUT_SIZE, CF_HIDDEN_SIZE, CF_OUTPUT_SIZE,
            CF_RANK, CF_MAX_DELAY, IDM2D_T1, IDM2D_T2, IDM2D_TAU, DT,
        )
        hidden_size = hidden_size if hidden_size is not None else CF_HIDDEN_SIZE
        self.hidden_size = hidden_size
        self.rank      = rank if rank is not None else CF_RANK
        self.max_delay = max_delay if max_delay is not None else CF_MAX_DELAY
        self.n_ticks  = 1
        self.T1       = IDM2D_T1
        self.T2       = IDM2D_T2
        self.T_mean   = (IDM2D_T1 + IDM2D_T2) / 2.0
        self.ou_alpha = _math.exp(-DT / IDM2D_TAU)

        self.layer_hidden = LIFLayer_EventProp(
            in_features=CF_INPUT_SIZE, out_features=hidden_size,
            silent_repair=True)
        self.layer_out = LILayer_Standard(
            in_features=hidden_size, out_features=CF_OUTPUT_SIZE)

        bounds = torch.tensor(self._PARAM_BOUNDS, dtype=torch.float32)
        self.register_buffer('param_lo', bounds[:, 0])
        self.register_buffer('param_hi', bounds[:, 1])
        ranges = bounds[:, 1] - bounds[:, 0]
        self.register_buffer('decode_scale', ranges / ranges.max())

    def reset_state(self, batch_size, device):
        pass

    def forward_sequence_with_stats(self, x_seq_norm):
        spikes_h = self.layer_hidden(x_seq_norm)
        raw_out  = self.layer_out(spikes_h)
        B, T, _ = raw_out.shape
        flat = raw_out.reshape(B * T, -1)
        params_seq = self._decode_params(flat).reshape(B, T, -1)
        spike_rate = spikes_h.mean(dim=2)
        return params_seq, spike_rate

    def forward_sequence(self, x_seq_norm):
        return self.forward_sequence_with_stats(x_seq_norm)[0]


class CF_FSNN_Net_EventProp_Full(CF_FSNN_Net):
    """LA TUA architettura A1 con EventProp adjoint.

    Replica EXACTLY CF_FSNN_Net + HiddenLayer_ALIF + ALIFCell + OutputLayer_LI:
      * Po2 quantization su TUTTI i pesi (STE backward)
      * max_delay=6 delayed synapses con mask per delay value
      * TICKS_PER_STEP=10 internal ticks per ogni step della sequenza
      * Bit-shift leak alpha_m = 7/8 (NO synaptic current I separato)
      * Adaptive threshold ALIF: V_th_eff = base_th + fatigue.clamp(0)
      * base_threshold, thresh_jump learnable (init 1.5, 0.5 -- matches baseline)
      * Low-rank recurrence rec_U @ rec_V
      * Soft reset V -= s · V_th_eff
      * LI output con bit-shift leak (V/8) + Po2 quantize

    Cambia SOLO il training method:
      Baseline: BPTT + SurrogateSpike_Hardware (γ=1.0)
      Full:     EventProp adjoint event-based esatto (this class)

    Params attesi (hidden=32, rank=8, max_delay=6, n_ticks=10):
      fc_weight (32×4=128) + rec_U (32×8=256) + rec_V (8×32=256)
      + base_th (32) + thresh_jump (32) + W_out (5×32=160) = 864 params
      ESATTAMENTE come baseline. Fair-compare perfetto.

    Nota gradiente thresh_jump: l'adjoint completo richiederebbe lambda_fatigue
    propagation. F2.1-full lo lascia a zero (treat as frozen) per semplicita'.
    Il base_threshold viene appreso via soft reset adjoint (vedi eventprop.py).
    """

    def __init__(self, hidden_size=None, rank=None, max_delay=None):
        nn.Module.__init__(self)
        from config import (
            CF_INPUT_SIZE, CF_HIDDEN_SIZE, CF_OUTPUT_SIZE,
            CF_RANK, CF_MAX_DELAY, TICKS_PER_STEP,
            IDM2D_T1, IDM2D_T2, IDM2D_TAU, DT,
        )
        hidden_size = hidden_size if hidden_size is not None else CF_HIDDEN_SIZE
        rank        = rank        if rank        is not None else CF_RANK
        max_delay   = max_delay   if max_delay   is not None else CF_MAX_DELAY
        self.hidden_size = hidden_size
        self.rank        = rank
        self.max_delay   = max_delay
        self.n_ticks  = TICKS_PER_STEP   # 10 -- match baseline
        self.T1       = IDM2D_T1
        self.T2       = IDM2D_T2
        self.T_mean   = (IDM2D_T1 + IDM2D_T2) / 2.0
        self.ou_alpha = _math.exp(-DT / IDM2D_TAU)

        # Hidden: full ALIF replica with EventProp adjoint
        self.layer_hidden = ALIFLayer_EventProp_Full(
            in_features=CF_INPUT_SIZE,
            out_features=hidden_size,
            rank=rank,
            max_delay=max_delay,
            n_ticks=self.n_ticks,
            base_th_init=1.5, thresh_jump_init=0.5,   # match baseline ALIFCell
            alpha_m=7.0/8.0, alpha_f=7.0/8.0,         # bit_shift=3 leak
            silent_repair=True,
        )
        # Output: bit-shift leak + Po2 quantize (matches baseline OutputLayer_LI)
        self.layer_out = LILayer_BitShift_Po2(
            in_features=hidden_size,
            out_features=CF_OUTPUT_SIZE,
            alpha=7.0/8.0,
        )

        # Decode bounds + F5 pre-scaling (ereditati concettualmente da baseline)
        bounds = torch.tensor(self._PARAM_BOUNDS, dtype=torch.float32)
        self.register_buffer('param_lo', bounds[:, 0])
        self.register_buffer('param_hi', bounds[:, 1])
        ranges = bounds[:, 1] - bounds[:, 0]
        self.register_buffer('decode_scale', ranges / ranges.max())

    def reset_state(self, batch_size, device):
        """No-op: EventProp processa l'intera sequenza in un singolo manual_forward."""
        pass

    def forward_sequence_with_stats(self, x_seq_norm):
        """Forward: T_seq sequence steps x n_ticks internal ticks each.

        x_seq_norm: (B, T_seq, 4)
        returns:    (params_seq (B, T_seq, 5), spike_rate (B, T_seq))

        - Hidden ALIFLayer_EventProp_Full produce (B, K, hidden) spikes
          where K = T_seq * n_ticks (internal expansion).
        - LI output processa tutti i K tick e ritorna (B, K, 5) potentials.
        - Decode SOLO al fine di ogni n_ticks block (= matches baseline che
          decode_params(raw_out) dopo l'ultimo tick interno).
        - spike_rate aggregato per step (mean su n_ticks e hidden).
        """
        B, T_seq, _ = x_seq_norm.shape
        K = T_seq * self.n_ticks
        # Hidden via custom autograd
        spikes_all = self.layer_hidden(x_seq_norm)   # (B, K, hidden)
        # Output via standard autograd
        raw_all = self.layer_out(spikes_all)          # (B, K, 5)
        # Decode at end of each n_ticks block: indices [n_ticks-1, 2n_ticks-1, ..., K-1]
        decode_idx = torch.arange(self.n_ticks - 1, K, self.n_ticks, device=raw_all.device)
        raw_decoded = raw_all[:, decode_idx, :]       # (B, T_seq, 5)
        # _decode_params expects (N, 5) -- apply per-step
        flat = raw_decoded.reshape(B * T_seq, -1)
        params_seq = self._decode_params(flat).reshape(B, T_seq, -1)
        # Spike rate per sequence step: mean over (hidden, n_ticks block)
        spikes_blocked = spikes_all.reshape(B, T_seq, self.n_ticks, -1)
        spike_rate = spikes_blocked.mean(dim=(2, 3))  # (B, T_seq)
        return params_seq, spike_rate

    def forward_sequence(self, x_seq_norm):
        return self.forward_sequence_with_stats(x_seq_norm)[0]


# =================================================================
# Factory build_model -- 3 variants only post-cleanup
# =================================================================

# =================================================================
# Factory build_model -- UNIFIED post-merge
# =================================================================
# Concentra le scelte di entrambi i branch:
#   - Architecture_Exploration: 8 architecture variants (baseline + 7 nuove)
#   - Training_Method_Exploration: 4 training method variants (baseline + 3 nuove)
# baseline e' presente in entrambi -> singola entry
def build_model(variant: str = 'baseline', hidden_size=None, rank=None,
                max_delay=None, bit_shift=None, **kwargs):
    """Factory unificata: 8 architecture + 3 EventProp variants + baseline.

    Args:
        variant: nome variante. Choices:
          --- architecture variants (da Architecture_Exploration) ---
          - 'baseline'             A1: ALIF + BPTT + surrogate (default, production)
          - 'stacked_2'            A2: 2 hidden ALIF stacked
          - 'stacked_2_skip'       A3: A2 + MS-style membrane skip
          - 'stacked_3_thin'       A4: 3 hidden ALIF thin (24x3)
          - 'max_delay_12'         A5: baseline + max_delay=12 (vs 6)
          - 'multi_rate'           A6: bit_shifts=[2,3,4] multi-rate ALIF
          - 'wta'                  A7: + lateral inhibition (1 inh neuron)
          - 'attn'                 A8: spike attention lite (Q/K/V Po2, 2 heads)
          --- training method variants (da Training_Method_Exploration) ---
          - 'bptt_lif_simple'      LIF simple + BPTT + surrogate (288 params)
          - 'eventprop_lif_simple' LIF simple + EventProp adjoint (288 params)
          - 'eventprop_alif_full'  A1 architecture + EventProp adjoint (864 params)
        hidden_size, rank, max_delay: override capacity (default config).
    """
    v = variant.lower()
    # --- baseline (shared) ---
    if v == 'baseline':
        # R25: passa max_delay e bit_shift al baseline per ablation asse A4/A5/A6
        return CF_FSNN_Net(hidden_size=hidden_size, rank=rank,
                            max_delay=max_delay, bit_shift=bit_shift)
    # --- Architecture variants ---
    if v == 'stacked_2':
        h = hidden_size or 32
        r = rank or 8
        return CF_FSNN_Net_Stacked(n_hidden=2, hidden_sizes=[h, h], ranks=[r, r])
    if v == 'stacked_2_skip':
        h = hidden_size or 32
        r = rank or 8
        return CF_FSNN_Net_StackedSkip(n_hidden=2, hidden_sizes=[h, h], ranks=[r, r])
    if v == 'stacked_3_thin':
        return CF_FSNN_Net_Stacked(n_hidden=3, hidden_sizes=[24, 24, 24], ranks=[6, 6, 6])
    if v == 'max_delay_12':
        return CF_FSNN_Net(hidden_size=hidden_size, rank=rank, max_delay=12)
    if v == 'multi_rate':
        return CF_FSNN_Net_MultiRate(hidden_size=hidden_size or 32, rank=rank or 8,
                                      bit_shifts=(2, 3, 4))
    if v == 'wta':
        return CF_FSNN_Net_WTA(hidden_size=hidden_size or 32, rank=rank or 8,
                                inh_strength=0.5)
    if v == 'attn':
        return CF_FSNN_Net_Attn(hidden_size=hidden_size or 32, rank=rank or 8, n_heads=2)
    # --- Training method variants ---
    if v == 'bptt_lif_simple':
        return CF_FSNN_Net_BPTT_LIF_Simple(hidden_size=hidden_size, rank=rank)
    if v == 'eventprop_lif_simple':
        return CF_FSNN_Net_EventProp_LIF_Simple(hidden_size=hidden_size, rank=rank)
    if v == 'eventprop_alif_full':
        return CF_FSNN_Net_EventProp_Full(hidden_size=hidden_size, rank=rank,
                                          max_delay=max_delay)
    raise ValueError(
        f"Variant '{variant}' non supportata. Choices:\n"
        "  baseline | stacked_2 | stacked_2_skip | stacked_3_thin | max_delay_12 | "
        "multi_rate | wta | attn | bptt_lif_simple | eventprop_lif_simple | eventprop_alif_full")
