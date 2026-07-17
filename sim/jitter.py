"""Seeded, type-preserving jitter: of a ScenarioSpec (the built family) and of params_gt (the preset family).

STRUCTURAL, not a blur. It nudges each block's OWN knobs (v, to_v, amp, period, nodes, ticks) and the neutral
style, so the scenario keeps its shape and its TYPE -- a sine stays a sine, a hard_brake stays a hard_brake.
Blurring the 600-float v_leader would preserve neither. A `preset` block has NO numeric knob
(scenario_spec.py:100-104 returns the library profile verbatim, with a hardcoded rng) -- only its `ticks` slot
moves; the preset family's real variety comes from jitter_params_gt (v_set = 0.7*v0 scales the whole profile).

strength=0 is the IDENTITY: the multiplier is exactly 1.0 and the clips are no-ops for in-range knobs, so the
spec comes back byte-identical. That degenerate case is what proves jitter is the only source of variation."""
from dataclasses import replace

import numpy as np

from data.generator import _PHYS_BOUNDS   # read-only: the canonical param bounds (= CF_FSNN_Net._PARAM_BOUNDS)
from sim.scenario_spec import (A_MAX_RANGE, B_MAX_RANGE, MAX_BLOCK_TICKS, V_RANGE, LeaderStyle, _PRESET_N)

_PARAM_KEYS = ("v0", "T", "s0", "a", "b")


def _rel(x, rng, strength, lo, hi):
    """x scaled by 1 +/- strength, clipped to [lo, hi]. strength=0 -> exactly x."""
    return float(np.clip(float(x) * (1.0 + rng.uniform(-strength, strength)), lo, hi))


def jitter_spec(spec, rng, strength):
    """A new ScenarioSpec of the SAME type with its knobs nudged. strength in [0,1]; 0 = identity."""
    blocks = []
    for b in spec.blocks:
        cap = _PRESET_N if b.kind == "preset" else MAX_BLOCK_TICKS
        ticks = int(np.clip(round(b.ticks * (1.0 + rng.uniform(-strength, strength))), 1, cap))
        p = dict(b.params)
        if b.kind == "const":
            p["v"] = _rel(p["v"], rng, strength, *V_RANGE)
        elif b.kind == "ramp":
            p["to_v"] = _rel(p["to_v"], rng, strength, *V_RANGE)
        elif b.kind == "sine":
            p["amp"] = _rel(p["amp"], rng, strength, 0.0, V_RANGE[1])
            p["period"] = _rel(p["period"], rng, strength, 1.0, float(MAX_BLOCK_TICKS))
        elif b.kind == "custom":
            p["nodes"] = tuple(_rel(v, rng, strength, *V_RANGE) for v in p["nodes"])
        # "preset": params = {"name": ...} -- verbatim, no numeric knob; only `ticks` moves it
        blocks.append(replace(b, ticks=ticks, params=p))
    style = LeaderStyle(_rel(spec.style.a_max, rng, strength, *A_MAX_RANGE),
                        _rel(spec.style.b_max, rng, strength, *B_MAX_RANGE))
    return replace(spec, blocks=tuple(blocks), style=style)


def jitter_params_gt(params_gt, rng, strength):
    """The PRESET family's only knob: v_set = 0.7*v0 scales the whole verbatim profile, s_init shifts with it.
    Bounded by the project's physical param bounds, imported (never duplicated)."""
    pg = np.asarray(params_gt, dtype=float).copy()
    for i, k in enumerate(_PARAM_KEYS):
        lo, hi = _PHYS_BOUNDS[k]
        pg[i] = _rel(pg[i], rng, strength, lo, hi)
    return pg
