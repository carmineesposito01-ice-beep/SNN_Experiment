import os
import torch

# Toggle della quantizzazione Po2 a runtime tramite env var.
# La forward() legge l'env var ad OGNI chiamata, quindi il toggle è "live" anche
# se l'env var viene settata DOPO l'import (es. dentro main() di train.py).
# Default: attiva; per disattivare impostare PO2_ENABLED=0 nell'env.
# Costo per-call: 1 dict lookup, trascurabile (~50 ns × ~30k chiamate per training).
# Architettura PYNQ-Z1 in deploy NON è affetta (deploy usa pipeline separata).
def _po2_enabled():
    return os.environ.get('PO2_ENABLED', '1') not in ('0', 'false', 'False', 'OFF', 'off')

class SurrogateSpike_Hardware(torch.autograd.Function):
    @staticmethod
    def forward(ctx, input_potential, threshold):
        ctx.save_for_backward(input_potential, threshold)
        return (input_potential >= threshold).float()

    @staticmethod
    def backward(ctx, grad_output):
        input_potential, threshold = ctx.saved_tensors
        # Il valore di letteratura è 0.3 (Bellec et al. 2018, LSNN); qui vale 1.0 per
        # evitare l'esplosione del gradiente su 500-1000 tick: con gamma=0.3 il kernel
        # della surrogate è largo ~3.3 unità → MOLTI neuroni near-threshold contribuiscono
        # simultaneamente al sum-grad → amplificazione esplosiva attraverso la catena
        # ricorrenza U·V in BPTT. Con gamma=1.0 il kernel si stringe a ~1 unità (3× più
        # stretto) → 3× meno neuroni concorrenti per step → riduzione del fattore di
        # amplificazione. Equivalenza: fast-sigmoid beta≈10 ≈ gamma=1.0.
        #
        # NON propaga il gradiente al threshold (return ..., None) — scelta hardware-
        # friendly (compatibile con il design FPGA, non rompe l'apprendimento
        # di base_threshold/thresh_jump via reset path).
        #
        # Tradeoff: gamma più grande riduce il flusso del gradiente nelle prime epoche
        # per reti piccole sparse (motivo del valore di letteratura 0.3).
        gamma = 1.0
        spike_pseudo_derivative = 1 / (1 + gamma * torch.abs(input_potential - threshold)) ** 2
        return grad_output * spike_pseudo_derivative, None

spike_fn = SurrogateSpike_Hardware.apply

class PowerOf2Quantize(torch.autograd.Function):
    @staticmethod
    def forward(ctx, weight):
        # Bypass live se PO2_ENABLED=0 nell'env (letto ad ogni call).
        # In modalità bypass: passthrough → pesi fp32 invariati (training "ideale"
        # senza errore di quantizzazione). Backward è già passthrough nominale.
        if not _po2_enabled():
            return weight
        sign = torch.sign(weight)
        w_abs = torch.abs(weight).clamp(min=1e-5)
        log2_w = torch.clamp(torch.round(torch.log2(w_abs)), min=-4.0, max=1.0)
        # Relax mask slightly (-5) to let signals flow
        mask = (w_abs > 2 ** (-5)).float()
        return sign * (2.0 ** log2_w) * mask

    @staticmethod
    def backward(ctx, grad_output):
        return grad_output

po2_quantize = PowerOf2Quantize.apply
