"""Declarative scenario description + a pure, vectorised materialiser.

A scenario is DESCRIBED (a timeline of blocks + a leader style) and materialised into the
600-float v_leader that SimStepper already consumes -- manual_scenario() is the door, so nothing
downstream changes.

The split that shapes everything: THE BLOCK SAYS WHAT, THE STYLE SAYS HOW. A ramp declares its
target; the style owns the RATE. `ticks` is the block's SLOT, never the ramp's duration.

Pure: no Qt, no filesystem, no torch -- the whole feature's logic is testable as data.
"""
import json
from dataclasses import dataclass

import numpy as np

from config import DT
from sim.scenario import manual_scenario, scenario_library

# The plane's limits. b_max tops out at B_MAX, the project's physical deceleration limit
# (utils/closed_loop_eval.py:22) -- the same one panic_stop uses. Not a number picked for looks.
A_MAX_RANGE = (1.0, 4.0)
B_MAX_RANGE = (1.0, 9.0)

_KINDS = ("preset", "const", "ramp", "sine")


@dataclass(frozen=True)
class Block:
    kind: str                 # "preset" | "const" | "ramp" | "sine"
    ticks: int                # the block's SLOT on the timeline -- NOT a ramp's duration
    params: dict              # {"name":…} | {"v":…} | {"to_v":…} | {"amp","period"}
    bias: tuple = None        # (da, db) m/s^2 ON the neutral; None = the neutral itself


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


def _preset_samples(name, n, params_gt, N):
    """A slice of scenario_library() AS-IS.

    build_scenarios (utils/closed_loop_eval.py:332) is INVARIANT by the contract in its own docstring
    -- the reports run on it -- so a preset is reproduced exactly and the style does NOT touch it.
    A validated preset you rewrite is no longer that preset.

    The honest trade: because it is verbatim, a preset does NOT join continuously to the block before
    it -- it starts where the library starts. Every other kind joins seamlessly; the alternative here
    would be rewriting a validated profile. Put presets first, or accept the seam.
    """
    lib = {s.name: s for s in scenario_library(params_gt, N=N,
                                               rng=np.random.default_rng(0), include_tail=True)}
    if name not in lib:
        raise ValueError(f"unknown preset: {name!r} (have: {sorted(lib)})")
    return lib[name].v_leader[:n]


def _sine_samples(amp, period, n, v0, style):
    """A sine oscillating around the CURRENT speed, with its amplitude clamped by the style.

    Two decisions, both load-bearing:
    * it oscillates around v0, not around an absolute mean. sin(0)=0, so the first sample IS v0 and
      the block joins the previous one CONTINUOUSLY. An absolute mean would teleport the leader
      whenever the previous block left it elsewhere -- the very defect the events fix removes.
    * the style clamps the AMPLITUDE, it does not clip tick by tick: the steepest slope of
      amp*sin(2*pi*t/period) is amp*2*pi/(period*DT), so bounding amp bounds the slope. Clipping
      would be recursive and would kill the vectorisation the live preview needs. A placid driver
      simply does not swing that hard.
    """
    rate = min(style.a_max, style.b_max)
    amp_max = rate * period * DT / (2.0 * np.pi)
    amp_eff = float(min(amp, amp_max))
    t = np.arange(n)
    return v0 + amp_eff * np.sin(2.0 * np.pi * t / float(period))


def _block_samples(block, v0, style, params_gt, N):
    """The samples this block contributes, starting from speed v0."""
    n = int(block.ticks)
    if block.kind == "const":
        return _rate_limited_toward(v0, float(block.params["v"]), n, style)
    if block.kind == "ramp":
        return _rate_limited_toward(v0, float(block.params["to_v"]), n, style)
    if block.kind == "preset":
        return _preset_samples(str(block.params["name"]), n, params_gt, N)
    if block.kind == "sine":
        return _sine_samples(float(block.params["amp"]), float(block.params["period"]), n, v0, style)
    raise ValueError(f"unknown block kind: {block.kind!r} (have: {_KINDS})")


def _check_style(style):
    """The plane's bounds. b_max above B_MAX would let the leader out-brake physics, and every
    safety metric downstream (brake_margin, DRAC) is written against that limit."""
    if not A_MAX_RANGE[0] <= style.a_max <= A_MAX_RANGE[1]:
        raise ValueError(f"a_max {style.a_max} outside {A_MAX_RANGE}")
    if not B_MAX_RANGE[0] <= style.b_max <= B_MAX_RANGE[1]:
        raise ValueError(f"b_max {style.b_max} outside {B_MAX_RANGE}")


def effective_style(block, neutral):
    """The style this block actually runs with: neutral + bias, clamped to the plane.

    ADDITIVE on purpose. An absolute per-block style would leave N unrelated styles and no driver at
    all; with a bias there is ONE driver -- the neutral is the character, the bias is the circumstance
    ("in this stretch he is edgier than usual").

    Clamped, not rejected: the bias is a nudge, the plane is physics. A nudge that would leave the
    plane is pinned at the edge rather than raising -- the user is dragging a pad, not typing a config.
    """
    if block.bias is None:
        return neutral
    da, db = block.bias
    return LeaderStyle(a_max=float(np.clip(neutral.a_max + da, *A_MAX_RANGE)),
                       b_max=float(np.clip(neutral.b_max + db, *B_MAX_RANGE)))


def materialise(spec, params_gt, N):
    """ScenarioSpec -> Scenario. Pure: same spec, same v_leader, byte for byte.

    `spec.style` is the NEUTRAL: the driver's character. Each block runs with neutral + its own bias
    (effective_style). Only the neutral is validated -- every effective style is clamped by
    construction.
    """
    _check_style(spec.style)
    out = np.empty(N, dtype=np.float64)
    v = float(spec.v_init)
    i = 0
    for block in spec.blocks:
        if i >= N:
            break
        seg = _block_samples(block, v, effective_style(block, spec.style), params_gt, N)[: N - i]
        out[i:i + seg.size] = seg
        if seg.size:
            v = float(seg[-1])
        i += seg.size
    out[i:] = v                                   # blocks shorter than N -> the last value HOLDS
    return manual_scenario(params_gt, out, spec.s_init, spec.v_init, name=spec.name)


def to_json(spec) -> str:
    """Declarative: a list of blocks, human-readable and diffable -- not 600 floats."""
    return json.dumps({
        "name": spec.name,
        "s_init": spec.s_init,
        "v_init": spec.v_init,
        "style": {"a_max": spec.style.a_max, "b_max": spec.style.b_max},
        "blocks": [{"kind": b.kind, "ticks": b.ticks, "params": b.params} for b in spec.blocks],
    }, indent=2)


def from_json(text) -> ScenarioSpec:
    """Rejects an unknown block kind BY NAME rather than applying the spec partially."""
    d = json.loads(text)
    blocks = []
    for b in d["blocks"]:
        if b["kind"] not in _KINDS:
            raise ValueError(f"unknown block kind: {b['kind']!r} (have: {_KINDS})")
        blocks.append(Block(kind=b["kind"], ticks=int(b["ticks"]), params=dict(b["params"])))
    return ScenarioSpec(name=d["name"], blocks=tuple(blocks),
                        style=LeaderStyle(a_max=float(d["style"]["a_max"]),
                                          b_max=float(d["style"]["b_max"])),
                        s_init=float(d["s_init"]), v_init=float(d["v_init"]))
