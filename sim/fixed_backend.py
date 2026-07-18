"""FixedPointBackend -- a live Qm.n quantized twin of the champion, run as a ghost.

Approach A (spec docs/superpowers/specs/2026-07-18-fixed-point-twin-design.md): wrap the
float forward and quantize weights + ALIF state + readout at the Qm.n grid, `nfrac` a live
knob. It shows the EFFECT of precision on the drive; it is NOT bit-exact to the FPGA
(that is Approach B). Family-aware like SoftwareBackend; the frozen core is reused, never
edited (po2_quantize from core.hardware, the stepper's structure from sim.eventprop_stepper).
"""
import copy

import torch
import torch.nn.functional as F

from core.hardware import po2_quantize
from core.network import CF_FSNN_Net_EventProp_Full
from sim.eventprop_stepper import EventPropStepper

# Integer bits per the Simulink_Importer fixed-point spec (HDL_PHASE.md §4 / snn_types.m).
# nfrac is the knob; these bound the range and stay fixed, exactly as on the FPGA.
_M_WEIGHT = 2      # Q2.n  weights (po2, already in [-2, 2])
_M_VMEM = 5        # Q5.n  membrane potential
_M_FATIGUE = 3     # Q3.n  adaptation (fatigue)
_M_READOUT = 7     # Q7.n  the 5 decoded params


def q(x, m, n):
    """Signed Qm.n: round-to-nearest (half-to-even, as the FPGA), saturate to [-2^m, 2^m - 2^-n].

    torch, not numpy: every consumer -- weights, state, readout -- is a torch tensor, and
    SimStepper does params.view(-1) on infer's output (stepper.py:92), so infer must return a
    tensor; a numpy q would force a host round-trip every tick.
    """
    step = 2.0 ** (-n)
    lo = -(2.0 ** m)
    hi = 2.0 ** m - step
    return torch.clamp(torch.round(x / step) * step, lo, hi)


def _safe_deepcopy(model):
    """copy.deepcopy(model), tolerant of non-leaf state tensors left behind by a live,
    un-guarded forward_step on this SAME model object (e.g. a SoftwareBackend stepping it
    in lockstep elsewhere, before the ghost is toggled on).

    ALIFCell.potential/fatigue/prev_spike and LICell.potential (core/neurons.py) are plain
    instance attributes reassigned by arithmetic every tick -- not nn.Parameter, not a
    registered buffer. After one un-guarded step they carry a grad_fn (e.g. potential's last
    op is a subtraction -> SubBackward0), and torch.Tensor.__deepcopy__ refuses any non-leaf
    tensor outright ("Only Tensors created explicitly by the user ... support the deepcopy
    protocol"). Detaching would be safe either way (nothing here ever calls .backward()), but
    to guarantee zero footprint on the caller's model, swap in value-identical detached clones,
    deepcopy, then restore the caller's exact original tensor objects.
    """
    swapped = []  # (module, attr_name, original_tensor)
    for module in model.modules():
        for name, value in vars(module).items():
            if isinstance(value, torch.Tensor) and not value.is_leaf:
                setattr(module, name, value.detach().clone())
                swapped.append((module, name, value))
    try:
        return copy.deepcopy(model)
    finally:
        for module, name, original in swapped:
            setattr(module, name, original)


class _FixedBaseline:
    """Baseline family (Raffaello, Leonardo). forward_step mutates the shared cell in place,
    so wrap a DEEP-COPIED model and quantize cell.potential (Q5.n) / cell.fatigue (Q3.n) after
    each step. Weights: forward_step re-applies po2 each call, and Q2.n on po2 is a no-op for
    nfrac>=4, so there is no separate weight hook."""

    def __init__(self, model, nfrac, device="cpu"):
        self.model = _safe_deepcopy(model)    # protect the live float net from in-place state quant
        self.device = device
        self.nfrac = int(nfrac)

    def reset(self):
        self.model.eval()
        self.model.reset_state(1, self.device)

    def step(self, obs_norm):
        p = self.model.forward_step(obs_norm.to(self.device))
        cell = self.model.layer_hidden.cell
        with torch.no_grad():
            cell.potential.copy_(q(cell.potential, _M_VMEM, self.nfrac))
            cell.fatigue.copy_(q(cell.fatigue, _M_FATIGUE, self.nfrac))
        return p

    def read_probe(self):
        cell = self.model.layer_hidden.cell
        v_mem = cell.potential.detach().cpu().numpy().reshape(-1)
        spikes = cell.prev_spike.detach().cpu().numpy().reshape(-1)
        v_th = (cell.base_threshold + cell.fatigue.clamp(min=0)).detach().cpu().numpy().reshape(-1)
        return {"spikes": spikes, "v_mem": v_mem, "v_th_eff": v_th, "input": None}

    def read_weights(self):
        lh = self.model.layer_hidden
        return {"w_in": lh.fc_weight.detach().cpu().numpy(),
                "w_rec": (lh.rec_U @ lh.rec_V).detach().cpu().numpy(),
                "w_out": self.model.layer_out.fc_weight.detach().cpu().numpy(),
                "rank": int(lh.rec_V.shape[0])}


class FixedPointBackend:
    """NetworkBackend: a live Qm.n twin. Family-aware; nfrac is a mutable knob. The readout
    Q7.n is applied uniformly at infer's output; weights + state quant live in the engine."""

    def __init__(self, model, nfrac=13, device="cpu"):
        self._nfrac = int(nfrac)
        self._eventprop = isinstance(model, CF_FSNN_Net_EventProp_Full)
        if self._eventprop:
            raise NotImplementedError("EventProp path lands in T3")   # replaced in Task 3
        self._engine = _FixedBaseline(model, nfrac, device)

    @property
    def nfrac(self):
        return self._nfrac

    @nfrac.setter
    def nfrac(self, value):
        self._nfrac = int(value)
        self._engine.nfrac = int(value)      # baseline: plain knob; eventprop (T3): re-quantizes weights

    def reset(self):
        self._engine.reset()

    def infer(self, obs_norm):
        p = self._engine.step(obs_norm)
        return q(p, _M_READOUT, self._nfrac)  # readout Q7.n at infer's output (family-uniform)

    def read_probe(self):
        return self._engine.read_probe()

    def read_weights(self):
        return self._engine.read_weights()
