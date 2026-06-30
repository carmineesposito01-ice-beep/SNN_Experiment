"""utils/quantize.py — Tier 5 (validita' hardware FPGA PYNQ-Z1): quantizzazione fixed-point dei param.

Sul target FPGA i 5 param identificati escono in fixed-point (e i pesi sono po2). Qui si quantizza
l'OUTPUT del modello (i 5 param che alimentano il blocco IDM analitico) per misurare il degrado
float-vs-quant su identificazione e closed-loop, da solo (T5.1) o combinato con la degradazione V2X (T5.2).

`QuantParamModel` avvolge un modello reale e ne quantizza l'output di forward_sequence/forward_step:
si da' in pasto a eval_safety esattamente come un modello normale -> closed-loop in fixed-point.
"""
import numpy as np
import torch


def fake_quant(x, frac_bits=8, int_bits=None):
    """Fixed-point Qm.n (fake-quant): arrotonda a multipli di 2^-frac_bits. int_bits => clamp range intero."""
    scale = 2.0 ** frac_bits
    q = np.round(np.asarray(x, dtype=np.float64) * scale) / scale
    if int_bits is not None:
        lim = 2.0 ** int_bits
        q = np.clip(q, -lim, lim - 1.0 / scale)
    return q


def quantize_po2(x):
    """Power-of-two: valore -> sign * 2^round(log2|valore|) (0 resta 0). Coerente coi pesi po2 dell'FPGA."""
    x = np.asarray(x, dtype=np.float64)
    out = np.zeros_like(x)
    nz = np.abs(x) > 1e-12
    out[nz] = np.sign(x[nz]) * 2.0 ** np.round(np.log2(np.abs(x[nz])))
    return out


class QuantParamModel:
    """Wrapper: quantizza i 5 param in uscita (Qm.n fixed o po2). Interfaccia identica al modello reale
    (forward_sequence/forward_step/reset_state/eval) -> usabile direttamente in eval_safety/identify."""

    def __init__(self, model, frac_bits=8, mode='fixed'):
        self.model = model
        self.frac_bits = frac_bits
        self.mode = mode

    def _q(self, t):
        arr = t.detach().cpu().numpy()
        q = quantize_po2(arr) if self.mode == 'po2' else fake_quant(arr, self.frac_bits)
        return torch.tensor(q, dtype=t.dtype)

    def forward_sequence(self, x):
        return self._q(self.model.forward_sequence(x))

    def forward_step(self, x):
        return self._q(self.model.forward_step(x))

    def reset_state(self, *a, **k):
        if hasattr(self.model, 'reset_state'):
            return self.model.reset_state(*a, **k)

    def eval(self):
        if hasattr(self.model, 'eval'):
            self.model.eval()
        return self
