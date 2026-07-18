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
