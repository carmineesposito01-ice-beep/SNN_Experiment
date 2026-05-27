import torch

class SurrogateSpike_Hardware(torch.autograd.Function):
    @staticmethod
    def forward(ctx, input_potential, threshold):
        ctx.save_for_backward(input_potential, threshold)
        return (input_potential >= threshold).float()

    @staticmethod
    def backward(ctx, grad_output):
        input_potential, threshold = ctx.saved_tensors
        # gamma=1.0 (A3 — applicata 2026-05-27 post-rollback B4, vedi P_S.md sezione P6).
        # Era 0.3 (Bellec et al. 2018, LSNN). Cambio motivato dall'exploding gradient
        # osservato in A1_onecycle_v3 (B126 con B4) e nel run originale (B1000 senza B4):
        # con gamma=0.3 il kernel della surrogate è largo ~3.3 unità → MOLTI neuroni
        # near-threshold contribuiscono simultaneamente al sum-grad → amplificazione
        # esplosiva attraverso la catena ricorrenza U·V in BPTT su 500-1000 tick.
        # Con gamma=1.0 il kernel si stringe a ~1 unità (3× più stretto) → 3× meno
        # neuroni concorrenti per step → riduzione del fattore di amplificazione.
        #
        # NON propaga il gradiente al threshold (return ..., None) — scelta hardware-
        # friendly preservata (compatibile con il design FPGA, non rompe l'apprendimento
        # di base_threshold/thresh_jump via reset path — vedi P_S.md sezione P5).
        #
        # Tradeoff documentato: gamma più grande riduce il flusso del gradiente nelle
        # prime epoche per reti piccole sparse (motivo della scelta originale 0.3).
        # Da rivalutare con B5 (spike-rate regularizer) se la convergenza è troppo lenta.
        # Riferimento: ch08 §default beta=10 fast-sigmoid ≈ gamma=1.0 (cheatsheet SNN-expert).
        gamma = 1.0
        spike_pseudo_derivative = 1 / (1 + gamma * torch.abs(input_potential - threshold)) ** 2
        return grad_output * spike_pseudo_derivative, None

spike_fn = SurrogateSpike_Hardware.apply

class PowerOf2Quantize(torch.autograd.Function):
    @staticmethod
    def forward(ctx, weight):
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
