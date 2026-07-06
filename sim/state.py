"""Mutable + immutable state types for the closed-loop stepper.

Mirrors the explicit scalars/dicts of utils.closed_loop_eval.simulate():
  s, v, a_l_filt, vl_prev  + pl_state (plant L4) + ch_state (V2X channel L3).
"""
from dataclasses import dataclass, field

import numpy as np


@dataclass
class SimState:
    """Mutable evolving state of one closed-loop run."""
    t: int = 0
    s: float = 0.0
    v: float = 0.0
    a_l_filt: float = 0.0
    vl_prev: float = 0.0
    collided: bool = False
    impact_dv: float = 0.0
    pl_state: dict = field(default_factory=dict)   # plant (L4) mutable state
    ch_state: dict = field(default_factory=dict)   # V2X channel (L3) mutable state


@dataclass(frozen=True)
class StepResult:
    """Immutable snapshot of one control step (pre-update s/v, as simulate() logs)."""
    t: int
    s: float
    v: float
    vl: float
    dv: float
    a_ego: float
    params: np.ndarray   # (5,) [v0, T, s0, a, b]
    collided: bool
