import torch

class SurrogateSpike_Hardware(torch.autograd.Function):
    @staticmethod
    def forward(ctx, input_potential, threshold):
        ctx.save_for_backward(input_potential, threshold)
        return (input_potential >= threshold).float()

    @staticmethod
    def backward(ctx, grad_output):
        input_potential, threshold = ctx.saved_tensors
        # gamma=0.3: valore dell'articolo LSNN originale (Bellec et al. 2018,
        # "Long short-term memory and learning-to-learn in networks of spiking neurons").
        # Una surrogate più larga (piccolo gamma) mantiene il gradiente non-zero su un
        # intervallo più ampio attorno alla soglia — vantaggioso per reti piccole con
        # pochi spike (come CF_FSNN_Net con 32 neuroni ALIF). F12.
        # Alternativa hardware-friendly: gamma=1.0 (convergenza più rapida ma meno stabile).
        gamma = 0.3
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
