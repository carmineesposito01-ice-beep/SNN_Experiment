"""Declarative scenario description + a pure, vectorised materialiser.

A scenario is DESCRIBED (a timeline of blocks + a leader style) and materialised into the
600-float v_leader that SimStepper already consumes -- manual_scenario() is the door, so nothing
downstream changes.

The split that shapes everything: THE BLOCK SAYS WHAT, THE STYLE SAYS HOW. A ramp declares its
target; the style owns the RATE. `ticks` is the block's SLOT, never the ramp's duration.

Pure: no Qt, no filesystem, no torch -- the whole feature's logic is testable as data.
"""
from dataclasses import dataclass

import numpy as np

from config import DT
from sim.scenario import manual_scenario

# The plane's limits. b_max tops out at B_MAX, the project's physical deceleration limit
# (utils/closed_loop_eval.py:22) -- the same one panic_stop uses. Not a number picked for looks.
A_MAX_RANGE = (1.0, 4.0)
B_MAX_RANGE = (1.0, 9.0)


@dataclass(frozen=True)
class Block:
    kind: str                 # "preset" | "const" | "ramp" | "sine"
    ticks: int                # the block's SLOT on the timeline -- NOT a ramp's duration
    params: dict              # {"name":…} | {"v":…} | {"to_v":…} | {"amp","period"}


@dataclass(frozen=True)
class LeaderStyle:
    """A POINT on the (a_max, b_max) plane -- continuous, not a menu.

    Acceleration and deceleration are INDEPENDENT: one "calm -> aggressive" slider would tie them
    together and only walk the placido<->aggressivo diagonal, making the two mixed quadrants
    (guardingo: crawls off then slams; spavaldo: darts away then coasts) unreachable rather than
    merely coarser.
    """
    a_max: float              # m/s^2, 1..4
    b_max: float              # m/s^2, 1..9


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    blocks: tuple
    style: LeaderStyle
    s_init: float
    v_init: float


def _rate_limited_toward(v0, target, n, style):
    """n samples going from v0 toward a CONSTANT target at the style's rate, then holding.

    Vectorised on purpose: the naive per-tick loop costs ~3.7 ms and eats the 60 fps budget of the
    live preview (measured). Toward a constant target the trajectory is analytic -- a straight line
    that saturates -- so it is a clip of a linspace, no recursion needed.
    """
    if n <= 0:
        return np.empty(0)
    rate = style.a_max if target >= v0 else style.b_max
    step = rate * DT
    ramp = v0 + np.sign(target - v0) * step * np.arange(1, n + 1)
    lo, hi = (v0, target) if target >= v0 else (target, v0)
    return np.clip(ramp, lo, hi)


def _block_samples(block, v0, style, params_gt, N):
    """The samples this block contributes, starting from speed v0."""
    n = int(block.ticks)
    if block.kind == "const":
        return _rate_limited_toward(v0, float(block.params["v"]), n, style)
    if block.kind == "ramp":
        return _rate_limited_toward(v0, float(block.params["to_v"]), n, style)
    raise ValueError(f"unknown block kind: {block.kind!r}")


def materialise(spec, params_gt, N):
    """ScenarioSpec -> Scenario. Pure: same spec, same v_leader, byte for byte."""
    out = np.empty(N, dtype=np.float64)
    v = float(spec.v_init)
    i = 0
    for block in spec.blocks:
        if i >= N:
            break
        seg = _block_samples(block, v, spec.style, params_gt, N)[: N - i]
        out[i:i + seg.size] = seg
        if seg.size:
            v = float(seg[-1])
        i += seg.size
    out[i:] = v                                   # blocks shorter than N -> the last value HOLDS
    return manual_scenario(params_gt, out, spec.s_init, spec.v_init, name=spec.name)
