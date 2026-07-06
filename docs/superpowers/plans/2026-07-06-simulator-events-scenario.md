# Simulator Events + Scenario Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Feed the `SimStepper` with (a) named `Scenario`s (wrapping `build_scenarios`) and (b) live, deterministic events (`EventInjector` with the `brake_leader` verb), without breaking the bit-identical golden.

**Architecture:** `Scenario` is a frozen dataclass carrying exactly the `SimStepper` constructor inputs. `EventInjector` holds a per-tick queue drained in stable order (tick, then insertion); its only v1 verb, `brake_leader(target_v, duration)`, overrides the leader velocity from the trigger tick onward. `SimStepper` gains an optional `injector`; with `injector=None` the leader velocity is `v_leader[t]` exactly, so the Plan 1 golden still passes.

**Tech Stack:** Python, NumPy, pytest. Reuses `utils.closed_loop_eval.build_scenarios`; builds on Plan 1 `sim/`.

**This is Plan 2 of 4.** (Plan 1 = core ✓; Plan 3 = probe+replay; Plan 4 = UI.)

---

## File Structure

| File | Responsibility |
|---|---|
| `sim/scenario.py` | `Scenario` (frozen) + `scenario_library()` (wraps `build_scenarios`) + `manual_scenario()` |
| `sim/events.py` | `Event`, `EventInjector` (drain per tick, stable order), `brake_leader` verb |
| `sim/stepper.py` (modify) | Add optional `injector` + `from_scenario()`; leader velocity via injector |
| `tests/test_sim_scenario.py` | Library has the 5 named scenarios; manual round-trips |
| `tests/test_sim_events.py` | Deterministic drain order; `brake_leader` ramp; integration alters trajectory; **golden still bit-identical** |

---

### Task 1: `Scenario` + library

**Files:**
- Create: `sim/scenario.py`
- Test: `tests/test_sim_scenario.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sim_scenario.py
import os, sys
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.scenario import Scenario, scenario_library, manual_scenario  # noqa: E402


def test_library_has_five_named_scenarios():
    lib = scenario_library([30.0, 1.5, 2.0, 1.5, 1.5], N=200, rng=np.random.default_rng(0))
    names = [s.name for s in lib]
    assert names == ["following", "stop_and_go", "hard_brake", "cut_in", "sinusoidal"]
    for s in lib:
        assert s.v_leader.shape == (200,)
        assert isinstance(s.s_init, float) and isinstance(s.v_init, float)
    cut = next(s for s in lib if s.name == "cut_in")
    assert cut.cut_in is not None and len(cut.cut_in) == 2


def test_manual_scenario_roundtrips():
    vl = np.full(10, 20.0)
    s = manual_scenario([30.0, 1.5, 2.0, 1.5, 1.5], vl, 25.0, 20.0, cut_in=(5, 8.0))
    assert s.name == "manual" and s.cut_in == (5, 8.0)
    assert s.v_leader.shape == (10,) and s.s_init == 25.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sim_scenario.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.scenario'`

- [ ] **Step 3: Write minimal implementation**

```python
# sim/scenario.py
"""Scenarios for the simulator — thin wrapper over utils.closed_loop_eval.build_scenarios.

A Scenario carries exactly the SimStepper constructor inputs (params_gt, v_leader,
s_init, v_init, cut_in), so the UI/tests can pick one and run it directly.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np

from utils.closed_loop_eval import build_scenarios


@dataclass(frozen=True)
class Scenario:
    name: str
    params_gt: np.ndarray            # (5,)
    v_leader: np.ndarray             # (N,)
    s_init: float
    v_init: float
    cut_in: Optional[tuple] = None   # (t_cut, new_gap) | None


def scenario_library(params_gt, N=600, rng=None, include_tail=False):
    """The v1 scenario set (following, stop_and_go, hard_brake, cut_in, sinusoidal)."""
    pg = np.asarray(params_gt, dtype=np.float64)
    return [
        Scenario(name=name, params_gt=pg,
                 v_leader=np.asarray(vl, dtype=np.float64),
                 s_init=float(s_i), v_init=float(v_i), cut_in=cut)
        for name, vl, s_i, v_i, cut in build_scenarios(pg, N=N, rng=rng, include_tail=include_tail)
    ]


def manual_scenario(params_gt, v_leader, s_init, v_init, cut_in=None, name="manual"):
    return Scenario(name=name, params_gt=np.asarray(params_gt, dtype=np.float64),
                    v_leader=np.asarray(v_leader, dtype=np.float64),
                    s_init=float(s_init), v_init=float(v_init), cut_in=cut_in)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sim_scenario.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add sim/scenario.py tests/test_sim_scenario.py
git commit -m "feat(sim): Scenario + scenario_library wrapping build_scenarios"
```

---

### Task 2: `Event` + `EventInjector` (`brake_leader`)

**Files:**
- Create: `sim/events.py`
- Test: `tests/test_sim_events.py` (Task 2 tests only; integration added in Task 3)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sim_events.py
import os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.events import EventInjector  # noqa: E402


def test_brake_leader_ramps_then_holds():
    inj = EventInjector()
    inj.enqueue(tick=2, verb="brake_leader", target_v=10.0, duration=4)
    base = 20.0
    got = [inj.tick(t, base) for t in range(8)]
    assert got[0] == 20.0 and got[1] == 20.0        # before trigger: base
    assert got[2] == 20.0                            # t0: ramp start = captured base
    assert got[4] == 15.0                            # halfway (frac 2/4): 20 + (10-20)*0.5
    assert got[6] == 10.0                            # t0+duration: target
    assert got[7] == 10.0                            # holds


def test_same_tick_drain_is_insertion_ordered():
    inj = EventInjector()
    inj.enqueue(tick=0, verb="brake_leader", target_v=15.0, duration=0)
    inj.enqueue(tick=0, verb="brake_leader", target_v=5.0, duration=0)   # later wins
    assert inj.tick(0, 20.0) == 5.0


def test_unknown_verb_raises():
    import pytest
    inj = EventInjector()
    inj.enqueue(tick=0, verb="teleport")
    with pytest.raises(ValueError):
        inj.tick(0, 20.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sim_events.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.events'`

- [ ] **Step 3: Write minimal implementation**

```python
# sim/events.py
"""Live events for the simulator — deterministic per-tick queue.

v1 verb: brake_leader(target_v, duration) — ramps the leader velocity from its
value at the trigger tick to target_v over `duration` ticks, then holds. It
overrides the scenario's leader profile from the trigger tick onward. Verb
vocabulary follows SUMO TraCI (slowDown). ReplayLog lands in Plan 3.
"""
from dataclasses import dataclass, field


@dataclass(order=True)
class Event:
    tick: int
    seq: int                                    # insertion-order tiebreak (stable drain)
    verb: str = field(compare=False)
    params: dict = field(compare=False, default_factory=dict)


class EventInjector:
    def __init__(self):
        self._events = []                       # list[Event]
        self._seq = 0
        self._brake = None                      # (t0, v_start, target, duration) | None

    def enqueue(self, tick, verb, **params):
        self._events.append(Event(tick=int(tick), seq=self._seq, verb=verb, params=params))
        self._seq += 1

    def tick(self, t, base_vl):
        """Drain events for tick t (stable order), then return the effective leader velocity."""
        for e in sorted(e for e in self._events if e.tick == t):     # order=True → (tick, seq)
            if e.verb == "brake_leader":
                self._brake = (t, float(base_vl), float(e.params["target_v"]),
                               int(e.params["duration"]))
            else:
                raise ValueError(f"unknown verb: {e.verb!r}")
        self._events = [e for e in self._events if e.tick != t]
        return self._effective_leader(t, base_vl)

    def _effective_leader(self, t, base_vl):
        if self._brake is None:
            return float(base_vl)
        t0, v_start, target, dur = self._brake
        if t < t0:
            return float(base_vl)
        if dur <= 0 or t >= t0 + dur:
            return float(target)
        return float(v_start + (target - v_start) * ((t - t0) / dur))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sim_events.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add sim/events.py tests/test_sim_events.py
git commit -m "feat(sim): EventInjector + brake_leader verb (deterministic drain)"
```

---

### Task 3: Wire `injector` into `SimStepper` (golden preserved)

**Files:**
- Modify: `sim/stepper.py`
- Test: `tests/test_sim_events.py` (add integration + golden-regression tests)

- [ ] **Step 1: Write the failing tests (append to tests/test_sim_events.py)**

```python
# --- append to tests/test_sim_events.py ---
import numpy as np
from utils.champion_io import load_champion
from utils.closed_loop_eval import simulate
from sim.backend import SoftwareBackend
from sim.stepper import SimStepper
from sim.events import EventInjector

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def _scn():
    return np.array([30.0, 1.5, 2.0, 1.5, 1.5]), np.full(60, 20.0), 25.0, 20.0


def test_injector_none_is_bit_identical_to_simulate():
    pg, vl, s0, v0 = _scn()
    ref = simulate(load_champion(CHAMP).model, pg, vl, s0, v0)
    got = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0,
                     injector=None).run()
    for k in ("s", "v", "vl", "dv", "a_ego", "params"):
        np.testing.assert_array_equal(got[k], ref[k])


def test_brake_leader_changes_trajectory_deterministically():
    pg, vl, s0, v0 = _scn()

    def run_once():
        inj = EventInjector()
        inj.enqueue(tick=20, verb="brake_leader", target_v=5.0, duration=10)
        return SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0,
                          injector=inj).run()

    a, b = run_once(), run_once()
    baseline = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0).run()
    for k in ("vl", "v", "s"):
        np.testing.assert_array_equal(a[k], b[k])          # reproducible
    assert not np.array_equal(a["vl"], baseline["vl"])      # the brake actually changed the leader
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sim_events.py -q`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'injector'`

- [ ] **Step 3: Modify `sim/stepper.py`**

Change the `__init__` signature and the leader-velocity read; add a `from_scenario` classmethod.

In `SimStepper.__init__`, add `injector=None` after `channel=None`:

```python
    def __init__(self, backend, params_gt, v_leader, s_init, v_init,
                 cut_in=None, plant=None, channel=None, injector=None, device="cpu"):
        self.backend = backend                     # None -> oracle
        self.injector = injector                   # None -> leader follows v_leader exactly
        self.params_gt = np.asarray(params_gt, dtype=np.float64)
```
(keep the rest of `__init__` unchanged.)

In `step()`, replace the single line `vl = float(self.v_leader[t])` with:

```python
        base_vl = float(self.v_leader[t])
        vl = self.injector.tick(t, base_vl) if self.injector is not None else base_vl
```
(everything after — `dv = st.v - vl`, channel, physics — is unchanged; physics still uses this `vl` as the TRUE leader velocity.)

Add this classmethod to `SimStepper` (after `__init__`):

```python
    @classmethod
    def from_scenario(cls, backend, scenario, plant=None, channel=None,
                      injector=None, device="cpu"):
        return cls(backend, scenario.params_gt, scenario.v_leader,
                   scenario.s_init, scenario.v_init, cut_in=scenario.cut_in,
                   plant=plant, channel=channel, injector=injector, device=device)
```

- [ ] **Step 4: Run the full sim suite to verify GREEN (incl. Plan 1 golden regression)**

Run: `python -m pytest tests/test_sim_state.py tests/test_sim_backend.py tests/test_sim_stepper.py tests/test_sim_scenario.py tests/test_sim_events.py -q`
Expected: PASS (all). The Plan 1 golden (`test_sim_stepper.py`) must still pass — proof the injector seam did not change the no-event path.

- [ ] **Step 5: Commit**

```bash
git add sim/stepper.py tests/test_sim_events.py
git commit -m "feat(sim): wire EventInjector into SimStepper (brake_leader); golden preserved"
```

---

## Self-Review

**Spec coverage (SIMULATOR_DESIGN.md):**
- §2 `Scenario` (wraps `build_scenarios` + manual) → Task 1. ✓
- §6 `Event`/`EventInjector`, stable-order drain, `brake_leader` (=slow_down) → Tasks 2, 3. ✓
- §3 event insertion at the top of the step (generalizing `cut_in`) → Task 3 (leader-velocity override). ✓
- §3 physics uses TRUE `vl` → the injector produces the *true* (braked) leader velocity; physics unchanged. ✓
- Regression: Plan 1 golden re-run in Task 3 Step 4. ✓
- Deferred (Plan 3+): `control_source`/`release_to_model` (design defers past `brake_leader` in v1), `ReplayLog`.

**Placeholder scan:** none. **Type consistency:** `Scenario` fields (Task 1) consumed by `from_scenario` (Task 3); `EventInjector.tick(t, base_vl)` (Task 2) called by `SimStepper.step` (Task 3); `enqueue(tick, verb, **params)` signature consistent.

---

## Execution Handoff

Inline execution (established for this track) unless the user chooses otherwise.
