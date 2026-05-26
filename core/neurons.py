import torch
import torch.nn as nn
from core.hardware import spike_fn

class ALIFCell(nn.Module):
    def __init__(self, num_neurons):
        super().__init__()
        self.num_neurons = num_neurons
        
        # Omeostasi Locale (Fatica Neurale HW-Friendly)
        self.base_threshold = nn.Parameter(torch.ones(num_neurons) * 1.5)
        self.thresh_jump = nn.Parameter(torch.ones(num_neurons) * 0.5)
        self.bit_shift = 3  # Default hardware bit-shift (>> 3)
        
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

        # Leak HW (Bit-Shift parametrizzato, tipicamente >> 3)
        leak = self.potential / (2.0 ** self.bit_shift)
        self.potential = self.potential - leak + input_current + rec_current

        # La soglia sale in base alla fatica
        eff_thresh = self.base_threshold + torch.relu(self.fatigue)
        spikes = spike_fn(self.potential, eff_thresh)

        # Leak Fatica HW
        fatigue_leak = self.fatigue / (2.0 ** self.bit_shift)
        self.fatigue = self.fatigue - fatigue_leak + (spikes * torch.abs(self.thresh_jump))

        # Soft Reset HW (Sottrazione pura, niente zeri forzati)
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
