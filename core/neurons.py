import torch
import torch.nn as nn
from core.hardware import spike_fn

class ALIFCell(nn.Module):
    def __init__(self, num_neurons, bit_shift=3):
        """ALIFCell con bit-shift leak HW-friendly.

        Args:
            num_neurons: numero di neuroni.
            bit_shift: int (uniforme) O lista/tensore di shape (num_neurons,)
                per multi-rate ALIF (STEP 2E variante A6). Default 3 = leak 1/8.
                Tutti i valori devono essere INTERI (potenze di 2) per restare
                FPGA-friendly. Buffer `leak_div = 2.0 ** bit_shift` shape (num_neurons,)
                consente broadcasting nativo nella forward.
        """
        super().__init__()
        self.num_neurons = num_neurons

        # Omeostasi Locale (Fatica Neurale HW-Friendly)
        self.base_threshold = nn.Parameter(torch.ones(num_neurons) * 1.5)
        self.thresh_jump = nn.Parameter(torch.ones(num_neurons) * 0.5)

        # STEP 2E A6: bit_shift può essere per-neurone (tensore) o scalare.
        # In entrambi i casi memorizziamo leak_div = 2^bit_shift come buffer (1, N)
        # per broadcasting con potential di shape (batch, num_neurons).
        if isinstance(bit_shift, (int, float)):
            bs_tensor = torch.full((num_neurons,), float(bit_shift))
        else:
            bs_tensor = torch.as_tensor(bit_shift, dtype=torch.float32)
            if bs_tensor.numel() != num_neurons:
                raise ValueError(
                    f"bit_shift tensor deve avere {num_neurons} elementi, "
                    f"ricevuti {bs_tensor.numel()}")
        self.register_buffer('leak_div', (2.0 ** bs_tensor).unsqueeze(0))  # (1, N)
        # bit_shift scalare esposto per backcompat con vecchio codice (es. LICell sibling).
        # Quando multi-rate, vale la media (è solo diagnostico — non usato nei calcoli).
        self.bit_shift = float(bs_tensor.mean().item())

        self.potential = None
        self.prev_spike = None
        self.fatigue = None

    def reset_state(self, batch_size, device):
        self.potential = torch.zeros(batch_size, self.num_neurons, device=device)
        self.prev_spike = torch.zeros(batch_size, self.num_neurons, device=device)
        self.fatigue = torch.zeros(batch_size, self.num_neurons, device=device)

    def forward(self, input_current, rec_current):
        if self.potential is None:
            self.reset_state(input_current.size(0), input_current.device)

        # Leak HW (Bit-Shift per-neurone, broadcast su batch)
        leak = self.potential / self.leak_div
        self.potential = self.potential - leak + input_current + rec_current

        # La soglia sale in base alla fatica.
        # clamp(min=0): fatigue >= 0 per costruzione (incrementa di thresh_jump.clamp(min=0)
        # ad ogni spike e decade verso 0 via bit-shift), quindi la clamp è ridondante
        # ma funge da guardia numerica esplicita. F10: era relu(fatigue).
        eff_thresh = self.base_threshold + self.fatigue.clamp(min=0)
        spikes = spike_fn(self.potential, eff_thresh)

        # Leak Fatica HW (stessa divisione per-neurone del potential)
        fatigue_leak = self.fatigue / self.leak_div
        # thresh_jump.clamp(min=0): thresh_jump è il salto di soglia per spike.
        # Per design ALIF il salto è sempre positivo — il segno non influenza mai il
        # comportamento. clamp(min=0) è semanticamente più corretto di torch.abs()
        # e ha gradiente nullo solo al confine (abs ha gradiente discontinuo in 0). F9.
        self.fatigue = self.fatigue - fatigue_leak + (spikes * self.thresh_jump.clamp(min=0))

        # Soft Reset HW (Sottrazione pura, niente zeri forzati).
        #
        # NOTA su detach (P5 — B4 ROLLBACK 2026-05-27):
        # Era stato applicato `.detach()` qui per spezzare la catena BPTT del reset
        # (ch22 §22.3 #5 SNN-expert, Bellec 2018). Risultato: training A1_onecycle_v3
        # esploso a B126/1485 (PRIMA del solito), spike_rate inchiodato all'1-2%.
        # Causa: SurrogateSpike_Hardware.backward() restituisce None per il gradiente
        # verso threshold (scelta hardware-friendly per FPGA). L'unico path di gradiente
        # per base_threshold e thresh_jump era quindi questa via di reset. Detacharla
        # rendeva i parametri ALIF non-apprendibili → rete dead → catena ricorrenza U·V
        # esplode prima. Vedi document/P_S.md sezione P5 per analisi completa.
        # DECISIONE: rollback. Per spezzare la catena BPTT serve un approccio diverso
        # (es. TBPTT B6, o spike-rate regularizer B5, o riduzione seq_len A2).
        self.potential = self.potential - (spikes * eff_thresh)
        self.prev_spike = spikes
        
        return spikes


class RS_ALIFCell(ALIFCell):
    """
    Versione del neurone ALIF specifica per Recurrent Spiking Neural Networks (RSNN).
    Eredita la logica di base ma permette estensioni per feedback globali
    o dinamiche di reset differenziate per la ricorrenza esplicita.
    """
    def __init__(self, num_neurons):
        super().__init__(num_neurons)
        # Possibili personalizzazioni per RSNN (es. parametri di fatica differenti)


class LICell(nn.Module):
    def __init__(self, num_neurons):
        super().__init__()
        self.num_neurons = num_neurons
        self.bit_shift = 3 # Default hardware bit-shift (>> 3)
        self.potential = None

    def reset_state(self, batch_size, device):
        self.potential = torch.zeros(batch_size, self.num_neurons, device=device)

    def forward(self, input_current):
        if self.potential is None:
            self.reset_state(input_current.size(0), input_current.device)

        # Il layer decisionale dimentica in base al bit-shift
        leak = self.potential / (2.0 ** self.bit_shift)
        self.potential = self.potential - leak + input_current
        return self.potential


# ============================================================
# CNN Building Blocks (Equivalente Classico per Confronto)
# ============================================================

class CNNBlock(nn.Module):
    """Blocco Conv2D -> BatchNorm -> ReLU -> MaxPool.
    Usato come mattone base per la rete CNN di confronto."""

    def __init__(self, in_channels, out_channels, kernel_size=3, padding=1, pool=True):
        super().__init__()
        layers = [
            nn.Conv2d(in_channels, out_channels, kernel_size, padding=padding),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        ]
        if pool:
            layers.append(nn.MaxPool2d(2))
        self.block = nn.Sequential(*layers)

    def forward(self, x):
        return self.block(x)
