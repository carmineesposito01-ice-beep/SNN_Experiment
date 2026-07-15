# Scenario Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A fourth mode where a scenario is *described* — a timeline of blocks plus a leader style on a 2-D plane — and materialised into the 600-float `v_leader` the simulator already runs.

**Architecture:** A pure, vectorised materialiser (`ScenarioSpec` → `Scenario`) with no Qt and no I/O, under a page that previews it live. `manual_scenario()` is already the door, so nothing downstream changes. `events.py` is unfrozen for a one-line ramp fix.

**Tech Stack:** Python 3, numpy, PySide6, pyqtgraph, pytest. Conda env `cf_sim`.

**Spec:** `docs/superpowers/specs/2026-07-15-scenario-builder-design.md` — read it first. Two things there are load-bearing: **`ticks` is the block's slot, never the ramp's duration**, and **`materialise` must be vectorised** (measured constraint, not a preference).

---

## Before you start

**Worktree:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator`, branch `Simulator`.

**Test runner** (⚠️ never `conda run -n cf_sim python -m pytest` — it intermittently crashes conda's plugin system):

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

**Full suite** = the 20 sim files + `tests/test_champion_io.py` (the exact command is in
`docs/superpowers/plans/2026-07-15-checkpoint-identity.md`). **Baseline: 199 passed.**

⚠️ **This plan adds a 21st sim test file** (`tests/test_sim_scenario_spec.py`). Add it to the suite
command and to the resume's list — that list is the project's single source for what to run.

**Hard rules:**
- **Frozen core, minus one**: `sim/{state,stepper,backend,probe,eventprop_stepper}.py` stay untouched.
  **`sim/events.py` is unfrozen for Task 4 only** — user decision, on evidence (`closed_loop_eval` has
  no live events, so no external golden exists). Do not take it as licence for the other five.
- **`utils/closed_loop_eval.py` is INVARIANT.** Its docstring pins it: the reports run on it. A preset
  block reuses `scenario_library()` as-is; the style never touches it.
- **No numpy LAPACK** in `cf_sim` → OMP #15 hard abort. Nothing here needs it.
- Commits: conventional, **no `Co-Authored-By`**. Push freely.
- **Do NOT fix** `ReplayLog.seed` (`app.py:591`) — out of scope, and nothing here makes it worse.

---

## File Structure

| File | Responsibility |
|---|---|
| `sim/scenario_spec.py` (new) | **The model and the materialiser.** Frozen dataclasses + `materialise()` + JSON. Pure: no Qt, no filesystem, no torch → the whole feature's logic is testable as data. ~150 lines. |
| `sim/ui/scenario_page.py` (new) | The page: timeline, 2-D style pad, live preview. Qt only; every decision it makes is delegated to `scenario_spec`. |
| `sim/events.py` | The one-line ramp fix (Task 4). |
| `sim/ui/app.py` | Wires the fourth mode into the existing 3-mode stack. |
| `tests/test_sim_scenario_spec.py` (new) | The materialiser, the style, JSON. No Qt. |
| `tests/test_sim_events.py` | The ramp fix. |
| `tests/test_sim_ui_smoke.py` | The page + the mode. |

Order: model → style → presets/JSON → the ramp fix (independent) → the page → verification.

---

### Task 1: The model and a vectorised `const`/`ramp`

**Files:**
- Create: `sim/scenario_spec.py`, `tests/test_sim_scenario_spec.py`

- [ ] **Step 1: Write the failing tests**

```python
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from config import DT                                          # noqa: E402
from sim.scenario_spec import (Block, LeaderStyle, ScenarioSpec, materialise)  # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
NORMALE = LeaderStyle(a_max=2.0, b_max=4.0)


def _spec(blocks, style=NORMALE, v_init=21.0):
    return ScenarioSpec(name="test", blocks=tuple(blocks), style=style,
                        s_init=33.5, v_init=v_init)


def test_const_block_holds_after_reaching_the_value():
    sc = materialise(_spec([Block("const", 100, {"v": 21.0})]), _PG, N=100)
    assert sc.v_leader.shape == (100,)
    np.testing.assert_allclose(sc.v_leader, 21.0)


def test_ramp_uses_the_style_rate_and_then_holds():
    """The ramp's slope is b_max, and `ticks` is the SLOT: once it arrives it holds for the rest."""
    sc = materialise(_spec([Block("ramp", 200, {"to_v": 2.0})]), _PG, N=200)
    vl = sc.v_leader
    assert vl[0] < 21.0                                        # already moving on tick 0
    # 21 -> 2 at b_max=4 m/s^2 takes 19/4 = 4.75 s = 47.5 ticks at DT=0.1
    n_ramp = int(np.ceil(19.0 / 4.0 / DT))
    assert abs(vl[n_ramp] - 2.0) < 1e-6                        # arrived
    np.testing.assert_allclose(vl[n_ramp:], 2.0)               # and holds for the rest of the slot
    dv = np.diff(vl[:n_ramp])
    assert np.all(dv >= -4.0 * DT - 1e-9)                      # never steeper than the style


def test_blocks_chain_from_where_the_previous_left_off():
    sc = materialise(_spec([Block("ramp", 30, {"to_v": 2.0}),       # slot too short to arrive
                            Block("const", 70, {"v": 2.0})]), _PG, N=100)
    vl = sc.v_leader
    assert vl[29] > 2.0                                         # cut mid-ramp, as designed
    assert abs(vl[30] - (vl[29] - 4.0 * DT)) < 1e-6             # next block continues from there
    assert abs(vl[-1] - 2.0) < 1e-6                             # and gets there


def test_materialise_is_pure_and_reproducible():
    s = _spec([Block("ramp", 100, {"to_v": 5.0}), Block("const", 100, {"v": 5.0})])
    np.testing.assert_array_equal(materialise(s, _PG, N=200).v_leader,
                                  materialise(s, _PG, N=200).v_leader)


def test_materialise_returns_a_scenario_the_stepper_can_run():
    from sim.stepper import SimStepper
    sc = materialise(_spec([Block("const", 60, {"v": 21.0})]), _PG, N=60)
    st = SimStepper.from_scenario(None, sc)                     # backend=None -> the oracle, no net needed
    for _ in range(60):
        if st.st.collided or st.st.t >= st.N:
            break
        st.step()
    assert st.st.t == 60                                        # it really is a runnable Scenario
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

Expected: FAIL — `ModuleNotFoundError: No module named 'sim.scenario_spec'`.

- [ ] **Step 3: Implement**

Create `sim/scenario_spec.py`:

```python
"""Declarative scenario description + a pure, vectorised materialiser.

A scenario is DESCRIBED (a timeline of blocks + a leader style) and materialised into the
600-float v_leader that SimStepper already consumes -- manual_scenario() is the door, so nothing
downstream changes.

The split that shapes everything: THE BLOCK SAYS WHAT, THE STYLE SAYS HOW. A ramp declares its
target; the style owns the RATE. `ticks` is the block's SLOT, never the ramp's duration.

Pure: no Qt, no filesystem, no torch -- the whole feature's logic is testable as data.
"""
from dataclasses import dataclass
from typing import Optional

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
    params: dict


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
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add sim/scenario_spec.py tests/test_sim_scenario_spec.py
git commit -m "feat(sim): declarative scenario model + vectorised const/ramp materialiser

A scenario is described (blocks + style) and materialised into the v_leader
SimStepper already eats; manual_scenario() is the door, so nothing downstream
changes and the core is untouched.

The block says WHAT (a target), the style says HOW (the rate); ticks is the
block's SLOT, so a ramp that arrives early holds, and one whose slot is too short
is cut where it got to and the next block continues from that speed.

_rate_limited_toward is vectorised, not a per-tick loop: toward a constant target
the trajectory is analytic (a saturating line), and the loop version costs ~3.7 ms
-- which eats the 60 fps budget of the live preview."
```

---

### Task 2: The style is a plane — and the axes are independent

**Files:**
- Modify: `sim/scenario_spec.py` (validation)
- Test: `tests/test_sim_scenario_spec.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
AGGRESSIVO = LeaderStyle(a_max=4.0, b_max=9.0)
PLACIDO = LeaderStyle(a_max=1.0, b_max=1.0)
GUARDINGO = LeaderStyle(a_max=1.0, b_max=9.0)      # crawls off, slams the brakes
SPAVALDO = LeaderStyle(a_max=4.0, b_max=1.0)       # darts away, coasts down


def test_style_changes_the_trajectory_not_the_label():
    """TEETH: the deceleration must MATCH b_max, not merely differ between styles. A style that
    only renames things passes 'they differ' and fails this."""
    for style in (PLACIDO, AGGRESSIVO):
        vl = materialise(_spec([Block("ramp", 300, {"to_v": 2.0})], style=style), _PG, N=300).v_leader
        moving = np.diff(vl)[np.diff(vl) < -1e-9]              # the braking samples
        np.testing.assert_allclose(moving, -style.b_max * DT, atol=1e-9)


def test_the_two_axes_are_independent():
    """TEETH, and this is WHY the style is a plane and not a slider: moving a_max must leave every
    braking segment byte-identical, and moving b_max must leave every accelerating segment
    byte-identical. A style that secretly couples them passes the test above and fails here."""
    blocks = [Block("ramp", 150, {"to_v": 2.0}),               # braking
              Block("ramp", 150, {"to_v": 21.0})]              # accelerating
    base = materialise(_spec(blocks, style=LeaderStyle(2.0, 4.0)), _PG, N=300).v_leader
    only_a = materialise(_spec(blocks, style=LeaderStyle(4.0, 4.0)), _PG, N=300).v_leader
    only_b = materialise(_spec(blocks, style=LeaderStyle(2.0, 9.0)), _PG, N=300).v_leader
    np.testing.assert_array_equal(base[:150], only_a[:150])    # a_max moved -> braking untouched
    assert not np.array_equal(base[150:], only_a[150:])        # ...and acceleration DID change
    assert not np.array_equal(base[:150], only_b[:150])        # b_max moved -> braking changed
    assert base[149] != only_b[149]


def test_the_four_quadrants_are_reachable_and_distinct():
    blocks = [Block("ramp", 150, {"to_v": 2.0}), Block("ramp", 150, {"to_v": 21.0})]
    out = {name: materialise(_spec(blocks, style=s), _PG, N=300).v_leader
           for name, s in (("aggressivo", AGGRESSIVO), ("placido", PLACIDO),
                           ("guardingo", GUARDINGO), ("spavaldo", SPAVALDO))}
    # guardingo brakes like aggressivo but accelerates like placido: the mixed quadrant exists
    np.testing.assert_array_equal(out["guardingo"][:150], out["aggressivo"][:150])
    np.testing.assert_array_equal(out["spavaldo"][:150], out["placido"][:150])
    assert not np.array_equal(out["guardingo"][150:], out["aggressivo"][150:])


def test_style_outside_the_plane_is_rejected():
    import pytest
    with pytest.raises(ValueError, match="a_max"):
        materialise(_spec([Block("const", 10, {"v": 5.0})], style=LeaderStyle(9.0, 4.0)), _PG, N=10)
    with pytest.raises(ValueError, match="b_max"):
        materialise(_spec([Block("const", 10, {"v": 5.0})], style=LeaderStyle(2.0, 20.0)), _PG, N=10)
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q -k "style or axes or quadrants"
```

Expected: `test_style_outside_the_plane_is_rejected` FAILS (nothing validates yet). The other three
should already PASS — Task 1's rate logic is per-direction by construction. **If any of them fails,
stop**: the axes are coupled and that is a real defect, not a missing feature.

- [ ] **Step 3: Implement the validation**

In `sim/scenario_spec.py`, add above `materialise`:

```python
def _check_style(style):
    """The plane's bounds. b_max above B_MAX would let the leader out-brake physics, and every
    safety metric downstream (brake_margin, DRAC) is written against that limit."""
    if not A_MAX_RANGE[0] <= style.a_max <= A_MAX_RANGE[1]:
        raise ValueError(f"a_max {style.a_max} outside {A_MAX_RANGE}")
    if not B_MAX_RANGE[0] <= style.b_max <= B_MAX_RANGE[1]:
        raise ValueError(f"b_max {style.b_max} outside {B_MAX_RANGE}")
```

and call it on the first line of `materialise`:

```python
def materialise(spec, params_gt, N):
    """ScenarioSpec -> Scenario. Pure: same spec, same v_leader, byte for byte."""
    _check_style(spec.style)
    out = np.empty(N, dtype=np.float64)
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add sim/scenario_spec.py tests/test_sim_scenario_spec.py
git commit -m "feat(sim): the leader style is a plane, with independent axes

Tests pin what makes the plane worth having: the deceleration MATCHES b_max
(not merely differs between styles), and the axes are independent -- moving a_max
leaves every braking segment byte-identical. A style that secretly coupled them
would pass 'they differ' and fail that one.

The mixed quadrants are asserted reachable: guardingo brakes like aggressivo and
accelerates like placido. On a single slider they would not exist at all.

b_max is bounded by B_MAX: above it the leader would out-brake physics, and every
safety metric downstream is written against that limit."
```

---

### Task 3: `preset` blocks (as-is), `sine`, and the JSON round-trip

**Files:**
- Modify: `sim/scenario_spec.py`
- Test: `tests/test_sim_scenario_spec.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_preset_block_reproduces_the_library_exactly():
    """TEETH: build_scenarios is INVARIANT (its docstring pins it: the reports run on it), so a
    preset block must be byte-identical to the library's. Fails the moment the style touches it."""
    from sim.scenario import scenario_library
    lib = {s.name: s for s in scenario_library(_PG, N=600, rng=np.random.default_rng(0),
                                               include_tail=True)}
    for style in (PLACIDO, AGGRESSIVO):                        # the style must NOT matter here
        sc = materialise(_spec([Block("preset", 600, {"name": "stop_and_go"})], style=style),
                         _PG, N=600)
        np.testing.assert_array_equal(sc.v_leader, lib["stop_and_go"].v_leader)


def test_preset_block_slice_takes_the_first_ticks_samples():
    from sim.scenario import scenario_library
    lib = {s.name: s for s in scenario_library(_PG, N=600, rng=np.random.default_rng(0),
                                               include_tail=True)}
    sc = materialise(_spec([Block("preset", 200, {"name": "stop_and_go"}),
                            Block("const", 400, {"v": 5.0})]), _PG, N=600)
    np.testing.assert_array_equal(sc.v_leader[:200], lib["stop_and_go"].v_leader[:200])


def test_unknown_preset_name_is_rejected_by_name():
    import pytest
    with pytest.raises(ValueError, match="nonesuch"):
        materialise(_spec([Block("preset", 10, {"name": "nonesuch"})]), _PG, N=10)


def test_sine_amplitude_is_clamped_by_the_style():
    """A sine's steepest slope is amp*2*pi/period. Rather than clipping tick by tick (which is
    recursive and would break vectorisation), the style CLAMPS the amplitude to what it can sustain
    -- a placid driver does not make brusque oscillations. Same intent, and it stays analytic."""
    blocks = [Block("sine", 300, {"amp": 10.5, "period": 40})]
    calm = materialise(_spec(blocks, style=PLACIDO), _PG, N=300).v_leader
    hard = materialise(_spec(blocks, style=AGGRESSIVO), _PG, N=300).v_leader
    assert calm.ptp() < hard.ptp()                              # the calm driver swings less
    for vl, style in ((calm, PLACIDO), (hard, AGGRESSIVO)):
        assert np.abs(np.diff(vl)).max() <= max(style.a_max, style.b_max) * DT + 1e-9


def test_json_round_trip_is_byte_exact_on_every_kind():
    from sim.scenario_spec import from_json, to_json
    s = _spec([Block("preset", 100, {"name": "stop_and_go"}),
               Block("const", 100, {"v": 8.0}),
               Block("ramp", 100, {"to_v": 2.0}),
               Block("sine", 300, {"amp": 4.0, "period": 80})],
              style=GUARDINGO)
    back = from_json(to_json(s))
    assert back == s                                            # frozen dataclasses compare by value
    np.testing.assert_array_equal(materialise(back, _PG, N=600).v_leader,
                                  materialise(s, _PG, N=600).v_leader)


def test_no_block_boundary_ever_teleports_the_leader():
    """TEETH, and it is the test that caught a real design bug: an earlier `sine` oscillated around
    an absolute `mean` and IGNORED v0, so a sine after a ramp ending at 2 m/s jumped straight to
    10.5 -- reproducing, inside the builder, the very teleport Task 4 removes from the events.

    Every junction between blocks must respect the style's rate, not just the inside of each block.
    """
    for style in (PLACIDO, AGGRESSIVO, GUARDINGO, SPAVALDO):
        vl = materialise(_spec([Block("ramp", 100, {"to_v": 2.0}),
                                Block("sine", 100, {"amp": 6.0, "period": 60}),
                                Block("const", 100, {"v": 18.0}),
                                Block("ramp", 100, {"to_v": 4.0}),
                                Block("sine", 200, {"amp": 3.0, "period": 40})],
                               style=style), _PG, N=600).v_leader
        jump = np.abs(np.diff(vl)).max()
        limit = max(style.a_max, style.b_max) * DT + 1e-9
        assert jump <= limit, f"{style}: a {jump:.3f} m/s jump in one tick (limit {limit:.3f})"


def test_json_rejects_an_unknown_block_kind_by_name():
    import pytest
    from sim.scenario_spec import from_json
    bad = '{"name":"x","s_init":33.5,"v_init":21.0,"style":{"a_max":2.0,"b_max":4.0},' \
          '"blocks":[{"kind":"teleport","ticks":10,"params":{}}]}'
    with pytest.raises(ValueError, match="teleport"):
        from_json(bad)
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q -k "preset or sine or json"
```

Expected: FAIL — `ValueError: unknown block kind: 'preset'`, then `ImportError` for `to_json`.

- [ ] **Step 3: Implement**

In `sim/scenario_spec.py`, add the imports and extend `_block_samples`:

```python
import json

from sim.scenario import manual_scenario, scenario_library
```

```python
_KINDS = ("preset", "const", "ramp", "sine")


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
      whenever the previous block left it elsewhere -- the very defect Task 4 fixes in the events.
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
```

Extend `_block_samples`:

```python
def _block_samples(block, v0, params_gt, N):
    """The samples this block contributes, starting from speed v0."""
    n = int(block.ticks)
    if block.kind == "const":
        return _rate_limited_toward(v0, float(block.params["v"]), n, block.style)
    if block.kind == "ramp":
        return _rate_limited_toward(v0, float(block.params["to_v"]), n, block.style)
    if block.kind == "preset":
        return _preset_samples(str(block.params["name"]), n, params_gt, N)
    if block.kind == "sine":
        return _sine_samples(float(block.params["amp"]), float(block.params["period"]), n, v0, style)
    raise ValueError(f"unknown block kind: {block.kind!r} (have: {_KINDS})")
```

Add the JSON pair at the end of the file:

```python
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
```

⚠️ `Block.params` is a `dict`, so `Block` is not hashable — that is fine (nothing hashes it) and
`==` still compares by value, which is what `test_json_round_trip` needs.

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

Expected: PASS (15 tests).

- [ ] **Step 5: Commit**

```bash
git add sim/scenario_spec.py tests/test_sim_scenario_spec.py
git commit -m "feat(sim): preset blocks (as-is), sine, and a declarative JSON round-trip

A preset block reproduces scenario_library() byte-identically and the style does
NOT touch it: build_scenarios is invariant by the contract in its own docstring,
because the reports run on it. A test pins that under two opposite styles.

sine clamps its AMPLITUDE to what the style can sustain rather than clipping tick
by tick -- clipping is recursive and would kill the vectorisation the live preview
needs. A placid driver simply does not swing that hard.

JSON is a list of blocks, not 600 floats: readable, diffable, and it rejects an
unknown kind by name instead of applying a spec partially."
```

---

### Task 4: The ramp fix in `events.py`

**Files:**
- Modify: `sim/events.py:36-43`
- Test: `tests/test_sim_events.py` (append)

⚠️ `sim/events.py` is listed as frozen core. **It is unfrozen for this task only** — user decision on
evidence: `closed_loop_eval` has no live events, so there is no external golden; the bit-identity test
covers only `injector=None`. Do not touch the other five frozen files.

- [ ] **Step 1: Write the failing tests**

```python
def test_two_sequential_brakes_do_not_teleport_the_leader():
    """TEETH. The ramp captured the RAW v_leader[t] instead of the leader's current effective
    speed, so a second brake restarted from 21 m/s while the leader was doing 5: measured, a
    +16.00 m/s jump in one tick (~160 m/s^2). Assert the jump, not a label."""
    import numpy as np
    inj = EventInjector()
    inj.enqueue(tick=50, verb="brake_leader", target_v=5.0, duration=10)
    inj.enqueue(tick=200, verb="brake_leader", target_v=2.0, duration=20)
    vl = np.array([inj.tick(t, 21.0) for t in range(300)])

    jumps = np.abs(np.diff(vl))
    assert jumps.max() < 21.0 * 0.1, f"leader teleported by {jumps.max():.2f} m/s in one tick"
    assert vl[200] <= vl[199] + 1e-9, "the second brake restarted ABOVE the current speed"
    assert abs(vl[199] - 5.0) < 1e-9 and abs(vl[-1] - 2.0) < 1e-9    # both brakes still work


def test_second_brake_ramps_from_the_current_speed():
    inj = EventInjector()
    inj.enqueue(tick=0, verb="brake_leader", target_v=10.0, duration=10)
    inj.enqueue(tick=20, verb="brake_leader", target_v=0.0, duration=10)
    got = [inj.tick(t, 20.0) for t in range(40)]
    assert abs(got[20] - 10.0) < 1e-9        # starts from 10 (where it was), not from 20 (raw)
    assert abs(got[25] - 5.0) < 1e-9         # halfway down from 10, not from 20
    assert abs(got[30] - 0.0) < 1e-9
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_events.py -q -k "teleport or current_speed"
```

Expected: FAIL — `leader teleported by 16.00 m/s in one tick`. **That failure is the bug, reproduced.**

- [ ] **Step 3: Implement**

In `sim/events.py`, `tick()` (`:34-43`):

```python
    def tick(self, t, base_vl):
        """Drain events for tick t (stable order), then return the effective leader velocity."""
        for e in sorted(e for e in self._events if e.tick == t):     # order=True -> (tick, seq)
            if e.verb == "brake_leader":
                # Ramp from the leader's CURRENT EFFECTIVE speed, not from the raw v_leader[t]:
                # with a brake already active those differ, and using the raw value made the leader
                # teleport (measured: 5.00 -> 21.00 m/s in one tick, ~160 m/s^2). Evaluate BEFORE
                # overwriting _brake -- afterwards _effective_leader would answer about the NEW ramp.
                v_start = self._effective_leader(t, base_vl)
                self._brake = (t, v_start, float(e.params["target_v"]), int(e.params["duration"]))
            else:
                raise ValueError(f"unknown verb: {e.verb!r}")
        self._events = [e for e in self._events if e.tick != t]
        return self._effective_leader(t, base_vl)
```

- [ ] **Step 4: Run to verify they pass, and that nothing else moved**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_events.py tests/test_sim_replay.py tests/test_sim_reconstruct.py -q
```

Expected: PASS. The pre-existing single-brake tests (`test_sim_events.py:13-22`) must be **untouched
and green**: the fix only bites when a brake is *already* active. `test_injector_none_is_bit_identical_to_simulate`
(`:53`) must stay green — it is the one golden events.py really has.

- [ ] **Step 5: Commit**

```bash
git add sim/events.py tests/test_sim_events.py
git commit -m "fix(sim): a second brake no longer teleports the leader

The ramp captured the RAW v_leader[t] instead of the leader's current effective
speed, so a brake fired while another was active restarted from the scenario's
profile: measured, 5.00 -> 21.00 m/s in a single tick (+16 m/s, ~160 m/s^2).

The fix is one line and the ORDERING is load-bearing: read _effective_leader
BEFORE overwriting _brake, or it answers about the new ramp instead of the old one.

events.py was listed as frozen core; unfrozen for this on evidence -- closed_loop_eval
has no live events, so no external golden exists, and the bit-identity test covers
only injector=None (still green). Single-brake behaviour is untouched by
construction: the fix only bites when a brake is already active."
```

---

### Task 5: The page and the fourth mode

**Files:**
- Create: `sim/ui/scenario_page.py`
- Modify: `sim/ui/app.py:157-165` (mode stack), `:350-362` (`set_mode`)
- Test: `tests/test_sim_ui_smoke.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
# --- scenario builder: the fourth mode ---
def test_app_has_a_fourth_mode(qapp):
    win = SimApp(CHAMP)
    assert win._mode_sel.count() == 4
    assert win._mode_sel.itemText(3) == "Scenari"
    win.set_mode(3)                                   # must not raise
    assert win._mode_stack.currentIndex() == 3


def test_scenario_page_preview_is_the_real_materialised_profile(qapp):
    """The preview must come from the same function the sim will run -- not a sketch."""
    import numpy as np
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec, materialise
    from sim.ui.scenario_page import ScenarioPage
    page = ScenarioPage(params_gt=np.array([30.0, 1.5, 2.0, 1.5, 1.5]), N=600)
    spec = ScenarioSpec(name="x", blocks=(Block("ramp", 600, {"to_v": 2.0}),),
                        style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)
    page.set_spec(spec)
    shown = page._curve.getOriginalDataset()[1]
    expected = materialise(spec, page._params_gt, page._N).v_leader
    np.testing.assert_array_equal(shown, expected)


def test_scenario_page_style_pad_redraws_the_preview(qapp):
    import numpy as np
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    from sim.ui.scenario_page import ScenarioPage
    page = ScenarioPage(params_gt=np.array([30.0, 1.5, 2.0, 1.5, 1.5]), N=600)
    page.set_spec(ScenarioSpec(name="x", blocks=(Block("ramp", 600, {"to_v": 2.0}),),
                               style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0))
    before = page._curve.getOriginalDataset()[1].copy()
    page.set_style(4.0, 9.0)                          # what dragging the pad calls
    after = page._curve.getOriginalDataset()[1]
    assert not np.array_equal(before, after)          # live: the curve really moved


def test_scenario_page_emits_the_built_scenario(qapp):
    import numpy as np
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    from sim.ui.scenario_page import ScenarioPage
    page = ScenarioPage(params_gt=np.array([30.0, 1.5, 2.0, 1.5, 1.5]), N=600)
    got = []
    page.sigScenarioBuilt.connect(got.append)
    page.set_spec(ScenarioSpec(name="mio", blocks=(Block("const", 600, {"v": 15.0}),),
                               style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0))
    page._on_use()
    assert len(got) == 1 and got[0].name == "mio"
    assert got[0].v_leader.shape == (600,)


def test_app_use_scenario_appends_it_to_the_live_selector(qapp):
    win = SimApp(CHAMP)
    before = win._selector.count()
    win.set_mode(3)
    win._scenario_page.set_style(4.0, 9.0)
    win._scenario_page._on_use()
    assert win._selector.count() == before + 1
    assert win.scenario_count() == before + 1
    win._advance(0.2)                                 # and the built scenario actually runs
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "fourth_mode or scenario_page or use_scenario"
```

Expected: FAIL — `AssertionError: 3 != 4`, then `ModuleNotFoundError: sim.ui.scenario_page`.

- [ ] **Step 3: Implement the page**

Create `sim/ui/scenario_page.py`:

```python
"""ScenarioPage -- the fourth mode: describe a scenario instead of picking one.

A timeline of blocks + a 2-D style pad; the preview below is the REAL materialised v_leader, from
the same function the sim will run. Every decision is delegated to sim.scenario_spec: this file is
Qt and nothing else.
"""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QListWidget,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)

from sim.scenario_spec import (A_MAX_RANGE, B_MAX_RANGE, Block, LeaderStyle, ScenarioSpec,
                               materialise)

_QUADRANTS = [("placido", 1.0, 1.0), ("guardingo", 1.0, 9.0),
              ("spavaldo", 4.0, 1.0), ("aggressivo", 4.0, 9.0)]


class StylePad(pg.PlotWidget):
    """The (a_max, b_max) plane. A point, dragged: acceleration and deceleration are independent,
    so a single slider would only walk the placido<->aggressivo diagonal."""
    sigStyleChanged = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.setLabel("bottom", "accelerazione a_max", units="m/s²")
        self.setLabel("left", "decelerazione b_max", units="m/s²")
        self.setXRange(*A_MAX_RANGE); self.setYRange(*B_MAX_RANGE)
        self.setMouseEnabled(x=False, y=False)
        for name, a, b in _QUADRANTS:
            t = pg.TextItem(name, color="#8a8a8a", anchor=(0.5, 0.5))
            t.setPos(a, b)
            self.addItem(t)
        self._dot = pg.ScatterPlotItem(size=13, brush=pg.mkBrush("#2a7fb8"),
                                       pen=pg.mkPen("#ffffff", width=2))
        self.addItem(self._dot)
        self._a, self._b = 2.0, 4.0
        self._dot.setData([self._a], [self._b])
        self.scene().sigMouseClicked.connect(self._on_click)

    def _on_click(self, ev):
        p = self.getPlotItem().vb.mapSceneToView(ev.scenePos())
        a = float(np.clip(p.x(), *A_MAX_RANGE))
        b = float(np.clip(p.y(), *B_MAX_RANGE))
        self.set_point(a, b)

    def set_point(self, a, b):
        self._a, self._b = float(a), float(b)
        self._dot.setData([self._a], [self._b])
        self.sigStyleChanged.emit(self._a, self._b)


class ScenarioPage(QWidget):
    sigScenarioBuilt = Signal(object)          # emits a sim.scenario.Scenario

    def __init__(self, params_gt, N=600):
        super().__init__()
        self._params_gt = np.asarray(params_gt, dtype=np.float64)
        self._N = int(N)
        self._spec = None
        root = QVBoxLayout(self)

        controls = QHBoxLayout()
        self._kind = QComboBox(); self._kind.addItems(["preset", "const", "ramp", "sine"])
        self._ticks = QSpinBox(); self._ticks.setRange(1, 600); self._ticks.setValue(150)
        self._value = QDoubleSpinBox(); self._value.setRange(0.0, 40.0); self._value.setValue(5.0)
        self._add = QPushButton("Aggiungi blocco"); self._add.clicked.connect(self._on_add)
        self._del = QPushButton("Rimuovi"); self._del.clicked.connect(self._on_del)
        self._use = QPushButton("Usa questo scenario"); self._use.clicked.connect(self._on_use)
        for w in (QLabel("blocco"), self._kind, QLabel("durata"), self._ticks,
                  QLabel("valore"), self._value, self._add, self._del, self._use):
            controls.addWidget(w)
        controls.addStretch(1)
        root.addLayout(controls)

        mid = QHBoxLayout()
        self._list = QListWidget()
        mid.addWidget(self._list, stretch=1)
        self._pad = StylePad()
        self._pad.sigStyleChanged.connect(self.set_style)
        mid.addWidget(self._pad, stretch=1)
        root.addLayout(mid, stretch=1)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("left", "v_leader", units="m/s")
        self._plot.setLabel("bottom", "time", units="steps")
        self._curve = self._plot.plot(pen=pg.mkPen("#d1495b", width=2))
        root.addWidget(self._plot, stretch=1)

    # ---- state ----
    def set_spec(self, spec):
        self._spec = spec
        self._pad.set_point(spec.style.a_max, spec.style.b_max)   # emits -> _refresh
        self._refresh_list()
        self._refresh()

    def set_style(self, a_max, b_max):
        """Called live while the pad is dragged. No throttle: measured 0/120 frames over the 60 fps
        budget (peak 14.18 ms of 16.7). The materialiser is vectorised precisely so this holds."""
        if self._spec is None:
            return
        self._spec = ScenarioSpec(name=self._spec.name, blocks=self._spec.blocks,
                                  style=LeaderStyle(float(a_max), float(b_max)),
                                  s_init=self._spec.s_init, v_init=self._spec.v_init)
        self._refresh()

    def _refresh(self):
        if self._spec is None or not self._spec.blocks:
            self._curve.setData([])
            return
        self._curve.setData(materialise(self._spec, self._params_gt, self._N).v_leader)

    def _refresh_list(self):
        self._list.clear()
        for b in (self._spec.blocks if self._spec else ()):
            self._list.addItem(f"{b.kind}  ·  {b.ticks} tick  ·  {b.params}")

    # ---- actions ----
    def _params_for(self, kind):
        v = float(self._value.value())
        return {"preset": {"name": "stop_and_go"}, "const": {"v": v}, "ramp": {"to_v": v},
                "sine": {"amp": 0.5 * v, "period": 80}}[kind]

    def _on_add(self):
        if self._spec is None:
            return
        kind = self._kind.currentText()
        blk = Block(kind, int(self._ticks.value()), self._params_for(kind))
        self._spec = ScenarioSpec(name=self._spec.name, blocks=self._spec.blocks + (blk,),
                                  style=self._spec.style, s_init=self._spec.s_init,
                                  v_init=self._spec.v_init)
        self._refresh_list()
        self._refresh()

    def _on_del(self):
        i = self._list.currentRow()
        if self._spec is None or i < 0:
            return
        blocks = self._spec.blocks[:i] + self._spec.blocks[i + 1:]
        self._spec = ScenarioSpec(name=self._spec.name, blocks=blocks, style=self._spec.style,
                                  s_init=self._spec.s_init, v_init=self._spec.v_init)
        self._refresh_list()
        self._refresh()

    def _on_use(self):
        if self._spec is None or not self._spec.blocks:
            return
        self.sigScenarioBuilt.emit(materialise(self._spec, self._params_gt, self._N))
```

**3b — wire the fourth mode.** In `sim/ui/app.py`, after `self._postrun_page = PostRunPage()` (`:156`):

```python
        self._scenario_page = ScenarioPage(params_gt=_PARAMS_GT, N=600)
        self._scenario_page.set_spec(ScenarioSpec(
            name="nuovo", blocks=(Block("const", 600, {"v": 21.0}),),
            style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0))
        self._scenario_page.sigScenarioBuilt.connect(self._on_scenario_built)
```

Add to the stack and the selector (`:157-161`):

```python
        self._mode_stack.addWidget(self._scenario_page)  # page 3: scenario builder
        self._mode_sel = QComboBox(); self._mode_sel.addItems(["Live", "Meso/Macro", "Post-run", "Scenari"])
```

Import at the top of `app.py`:

```python
from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
from sim.ui.scenario_page import ScenarioPage
```

And the handler, next to `select_scenario`:

```python
    def _on_scenario_built(self, scenario):
        """A built scenario joins the library and is selected. manual_scenario already produced a
        real Scenario, so nothing else needs to know it was built rather than picked."""
        self._scenarios.append(scenario)
        self._selector.blockSignals(True)
        self._selector.addItem(scenario.name)
        self._selector.setCurrentIndex(len(self._scenarios) - 1)
        self._selector.blockSignals(False)
        self.select_scenario(len(self._scenarios) - 1)
        self.set_mode(0)                                  # back to the cockpit to watch it run
```

⚠️ `set_mode` (`:350-362`) guards `idx != 1` for the meso road and `idx == 2` for the post-run seal.
Index 3 falls through both, which is correct — but **read it before you trust that**, and check that
`idx != 0` still pauses the live sim when entering the builder.

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q
```

Expected: PASS. ⚠️ `test_simapp_loads_champion_and_advances` asserts `scenario_count() >= 10` — the
builder does not change the startup count, so it must stay green untouched.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/scenario_page.py sim/ui/app.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): fourth mode — build a scenario instead of picking one

Timeline of blocks + the 2-D style pad, with the preview showing the REAL
materialised v_leader from the same function the sim will run -- not a sketch.
The preview redraws live while the point moves, no throttle: measured 0/120 frames
over the 60 fps budget.

A built scenario joins the library through manual_scenario, so the cockpit, the
Meso page and the post-run never learn it was built rather than picked."
```

---

### Task 6: Full verification, performance, and docs

**Files:**
- Modify: `document/SIMULATOR_SESSION_RESUME.md`

- [ ] **Step 1: Prove the live preview holds 60 fps — the measured constraint**

Append to `tests/test_sim_scenario_spec.py`:

```python
def test_materialise_holds_the_60fps_budget():
    """The live preview redraws on every drag step. Assert the PEAK, not the mean: it is the peak
    the eye sees. A per-tick Python loop (the first prototype) costs ~3.7 ms and fails this on a
    busy timeline -- which is why the materialiser is vectorised."""
    import time
    s = _spec([Block("preset", 150, {"name": "stop_and_go"}), Block("ramp", 150, {"to_v": 2.0}),
               Block("const", 150, {"v": 2.0}), Block("sine", 150, {"amp": 5.0, "period": 60})])
    for _ in range(3):
        materialise(s, _PG, N=600)                       # warm up
    ts = []
    for _ in range(60):
        t0 = time.perf_counter()
        materialise(s, _PG, N=600)
        ts.append((time.perf_counter() - t0) * 1000)
    peak = max(ts)
    assert peak < 16.7, f"materialise peaks at {peak:.2f} ms, over the 60 fps budget"
```

Run it. Expected: PASS.

- [ ] **Step 2: Run the full suite** — the 20 sim files **+ `tests/test_sim_scenario_spec.py`** (the new
21st) **+ `tests/test_champion_io.py`**.

Expected: **PASS**, 199 baseline + the new ones (Task 1: 5, Task 2: 4, Task 3: 6, Task 4: 2, Task 5: 5,
Task 6: 1 → expect **222**). Write the **real** number everywhere, never the predicted one.

- [ ] **Step 3: Verify the rest of the core is untouched**

```bash
git diff --stat origin/Simulator -- sim/state.py sim/stepper.py sim/backend.py sim/probe.py sim/eventprop_stepper.py
```

Expected: **empty**. `sim/events.py` is deliberately absent from that list — it is the one file this
cycle was allowed to change.

- [ ] **Step 4: Render-verify — actually look at it**

Write to your scratchpad a script with `QT_QPA_PLATFORM=windows` that builds `SimApp`, calls
`win.set_mode(3)`, adds a couple of blocks via `win._scenario_page`, drags the style with
`set_style(4.0, 9.0)`, grabs the window and saves a PNG. **Read the PNG and look at it**: the
timeline, the pad with its four quadrant labels, and a preview curve that matches the style.
`verify_*.png` is gitignored.

- [ ] **Step 5: Update the resume and commit**

Mark cycle 3 done. Put the **real** test count in §How to work, and **add `test_sim_scenario_spec.py`
to the explicit test list** — that list is the project's single source for what to run, and a new file
missing from it is a test nobody runs. Note that `events.py` is no longer bit-identical to its
original, and why.

```bash
git add document/SIMULATOR_SESSION_RESUME.md
git commit -m "docs(sim): resume — cycle 3 (scenario builder) done"
git push origin Simulator
```

---

## Notes for whoever executes this

- **`ticks` is the slot, not the ramp's duration.** If you find yourself computing a ramp's slope from
  its `ticks`, you have inverted the design: the style owns the rate, the block owns the slot.
- **The preset is sacred.** `build_scenarios` is invariant by the contract in its own docstring — the
  reports run on it. If a style ever changes a preset block's output, Task 3's test fails, and it is
  right and you are wrong.
- **The ordering in the events fix is the fix.** Reading `_effective_leader` after overwriting `_brake`
  compiles, runs, and is silently wrong: it answers about the new ramp.
- **Vectorisation is a requirement, not a polish pass.** It was measured: the loop costs 3.68 ms against
  a 16.7 ms frame budget shared with the repaint. Task 6's test guards it.
