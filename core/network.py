import torch
import torch.nn as nn
from core.hardware import po2_quantize
from core.neurons import ALIFCell, LICell

class HiddenLayer_ALIF(nn.Module):
    def __init__(self, in_features, out_features, rank=16, max_delay=3):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.max_delay = max_delay

        self.fc_weight = nn.Parameter(torch.Tensor(out_features, in_features))
        nn.init.xavier_uniform_(self.fc_weight)
        self.register_buffer('delays', torch.randint(0, max_delay, (out_features, in_features)))

        self.rec_U = nn.Parameter(torch.Tensor(out_features, rank))
        self.rec_V = nn.Parameter(torch.Tensor(rank, out_features))
        nn.init.orthogonal_(self.rec_U, gain=0.2)
        nn.init.orthogonal_(self.rec_V, gain=0.2)

        self.x_buffer = None
        self.cell = ALIFCell(out_features)

    def reset_state(self, batch_size, device):
        self.x_buffer = [torch.zeros(batch_size, self.in_features, device=device) for _ in range(self.max_delay)]
        self.cell.reset_state(batch_size, device)

    def forward(self, x):
        if self.x_buffer is None:
            self.reset_state(x.size(0), x.device)

        self.x_buffer.insert(0, x)
        self.x_buffer.pop()

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
# Adattamento di FSNN_V5 per IDM-2D + V2X + PYNQ-Z1
# ===========================================================
import math as _math


class CF_FSNN_Net(nn.Module):
    """
    SNN per Car-Following con training Physics-Informed (PINN).

    Architettura:
        HiddenLayer_ALIF (4 → 32, rank=8, max_delay=6)  ← V2X: [s, v, Δv, v_l]
        OutputLayer_LI   (32 → 5)                        ← IDM-2D: [v0, T, s0, a, b]

    Connessione IDM-2D ↔ ALIF (Ch12 + Ch13):
        max_delay=6  →  Tr_max = 6 × 0.1 s = 0.6 s  (tempo di reazione, Ch13)
        fatica ALIF  →  T(t) stocastico IDM-2D  (banda [T1, T2])
        rank=8       →  ricorrenza low-rank (U 32×8, V 8×32)

    Ogni passo di simulazione (Δt=0.1 s) viene elaborato con TICKS_PER_STEP
    tick SNN interni; il potenziale finale del layer LI viene mappato via
    sigmoid + scaling nei range fisici dei 5 parametri IDM-2D.

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

    def __init__(self):
        super().__init__()
        from config import (
            CF_INPUT_SIZE, CF_HIDDEN_SIZE, CF_OUTPUT_SIZE,
            CF_RANK, CF_MAX_DELAY, TICKS_PER_STEP,
            IDM2D_T1, IDM2D_T2, IDM2D_TAU, DT,
        )

        self.n_ticks  = TICKS_PER_STEP
        self.T1       = IDM2D_T1
        self.T2       = IDM2D_T2
        self.T_mean   = (IDM2D_T1 + IDM2D_T2) / 2.0
        # α = exp(-Δt / τ_OU): costante mean-reversion per loss OU  (≈ 0.9967)
        self.ou_alpha = _math.exp(-DT / IDM2D_TAU)

        self.layer_hidden = HiddenLayer_ALIF(
            CF_INPUT_SIZE, CF_HIDDEN_SIZE,
            rank=CF_RANK, max_delay=CF_MAX_DELAY,
        )
        self.layer_out = OutputLayer_LI(CF_HIDDEN_SIZE, CF_OUTPUT_SIZE)

        # Bounds come buffer → si spostano con .to(device)
        bounds = torch.tensor(self._PARAM_BOUNDS, dtype=torch.float32)
        self.register_buffer('param_lo', bounds[:, 0])   # (5,)
        self.register_buffer('param_hi', bounds[:, 1])   # (5,)

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
        """Potenziale LI grezzo → parametri IDM-2D fisici via sigmoid.
        raw:     (batch, 5)
        returns: (batch, 5) in unità fisiche
        """
        return self.param_lo + (self.param_hi - self.param_lo) * torch.sigmoid(raw)

    # ----------------------------------------------------------
    # Forward
    # ----------------------------------------------------------
    def forward_step(self, x_norm):
        """Un passo di simulazione = n_ticks tick SNN interni.

        x_norm:  (batch, 4)  — input normalizzato [s̃, ṽ, Δṽ, ṽ_l] ∈ [0, 1]
        returns: (batch, 5)  — parametri IDM-2D in unità fisiche

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
        returns:    (batch, T, 5)  — parametri IDM-2D nel tempo

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
    # Fisica IDM-2D — componenti della PINN loss
    # ----------------------------------------------------------
    @staticmethod
    def idm_accel(s, v, dv, params):
        """Accelerazione IDM-2D dai parametri predetti dalla rete.

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

        # Accelerazione IDM: a · [1 − (v/v0)^4 − (s*/s)²]
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

        Sostituisce idm_accel() nella loss — usa IIDM (risolve bias v0)
        e CAH (anticipa frenata leader, evita panic braking su cut-in).

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
        s_safe  = s.clamp(min=0.5)

        # ── IIDM base (regime free-flow separato dal car-following) ──
        v_free = a * (1.0 - (v / v0).clamp(max=10.0) ** 4)
        z      = (s_star / s_safe).clamp(max=20.0)
        # z < 1 → free-flow dominante;  z >= 1 → following dominante
        a_iidm_ff = v_free * (1.0 - z ** 2)
        a_iidm_cf = v_free - a * (z ** 2 - 1.0) / (1.0 + z).clamp(min=1e-6) ** 2
        a_iidm    = torch.where(z < 1.0, a_iidm_ff, a_iidm_cf)

        # ── CAH ─────────────────────────────────────────────────────
        a_l_bar = torch.minimum(a_l, a)          # ā_l = min(a_l, a)
        denom   = v * a_l_bar / s_safe + dv ** 2 / (2.0 * s_safe + 1e-6)
        a_cah   = v ** 2 * a_l_bar / (denom + 1e-6)
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

        params_seq: (batch, T, 5)
        returns:    scalare
        """
        T_seq      = params_seq[:, :, 1]
        T_prev     = T_seq[:, :-1]
        T_next     = T_seq[:, 1:]
        T_expected = self.ou_alpha * T_prev + (1.0 - self.ou_alpha) * self.T_mean
        return torch.mean((T_next - T_expected) ** 2)
