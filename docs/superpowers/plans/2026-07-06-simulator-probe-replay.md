# Simulator Probe + Replay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Complete the headless layer with (a) an `AttributeProbe` that snapshots the hidden ALIF state (`potential/fatigue/prev_spike`) into a ring-buffer with zero intrusion, and (b) a `ReplayLog` (seed + event-log) that reruns a session **bit-identically**.

**Architecture:** `SoftwareBackend.read_probe()` reads the champion's `layer_hidden.cell` attributes directly (AttributeMonitor pattern, design §5) — no model changes. `AttributeProbe` is a driver-fed ring-buffer decoupled from `SimStepper`. `EventInjector` gains an enqueue-log; `ReplayLog` captures seed + that log and rebuilds an injector for a bit-identical rerun (design §6).

**Tech Stack:** Python, NumPy, PyTorch, pytest. Builds on Plan 1+2 `sim/`.

**This is Plan 4 of 4's predecessor — Plan 3 of 4.** After this, only the PySide6 UI (Plan 4) remains; the headless engine is feature-complete.

---

## File Structure

| File | Responsibility |
|---|---|
| `sim/backend.py` (modify) | Add `SoftwareBackend.read_probe()` — zero-intrusion ALIF snapshot |
| `sim/probe.py` | `ProbeFrame` + `AttributeProbe` (ring-buffer, `sample_every`) |
| `sim/events.py` (modify) | Add `EventInjector` enqueue-log + `log()` |
| `sim/replay.py` | `ReplayLog` (seed + events, `build_injector`, JSON) |
| `tests/test_sim_probe.py` | read_probe shapes/values; ring-buffer capacity + sample_every |
| `tests/test_sim_replay.py` | rerun-from-log bit-identical; JSON round-trip |

---

### Task 1: `read_probe()` + `AttributeProbe`

**Files:**
- Modify: `sim/backend.py` (add `read_probe` to `SoftwareBackend`)
- Create: `sim/probe.py`
- Test: `tests/test_sim_probe.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sim_probe.py
import os, sys
import numpy as np
import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion   # noqa: E402
from sim.backend import SoftwareBackend       # noqa: E402
from sim.probe import AttributeProbe          # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def test_read_probe_shapes_and_binary_spikes():
    champ = load_champion(CHAMP)
    be = SoftwareBackend(champ.model)
    be.reset()
    be.infer(torch.tensor([[0.4, 0.3, 0.5, 0.3]], dtype=torch.float32))
    p = be.read_probe()
    H = champ.topology["hidden"]
    assert p["spikes"].shape == (H,)
    assert p["v_mem"].shape == (H,)
    assert p["v_th_eff"].shape == (H,)
    assert set(np.unique(p["spikes"])).issubset({0.0, 1.0})
    assert (p["v_th_eff"] > 0).all()


def test_probe_ringbuffer_capacity():
    pr = AttributeProbe(capacity=5, sample_every=1)
    for t in range(10):
        pr.record(t, {"spikes": np.zeros(3), "v_mem": np.zeros(3), "v_th_eff": np.ones(3)},
                  np.zeros(5))
    assert len(pr.frames()) == 5
    assert pr.frames()[0].t == 5           # kept the last 5


def test_probe_sample_every():
    pr = AttributeProbe(capacity=100, sample_every=2)
    for t in range(10):
        pr.record(t, {"spikes": np.zeros(3), "v_mem": np.zeros(3), "v_th_eff": np.ones(3)},
                  np.zeros(5))
    assert [f.t for f in pr.frames()] == [0, 2, 4, 6, 8]
    assert pr.spikes_matrix().shape == (5, 3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sim_probe.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.probe'`

- [ ] **Step 3a: Add `read_probe` to `SoftwareBackend` (sim/backend.py)**

Add this method to the `SoftwareBackend` class (after `infer`):

```python
    def read_probe(self) -> dict:
        """Zero-intrusion snapshot of the hidden ALIF state (AttributeMonitor pattern).

        numpy (H,) arrays: spikes (last internal tick), v_mem (potential),
        v_th_eff (base_threshold + fatigue.clamp(min=0)). Requires the standard
        .cell-nested hidden layer (baseline family).
        """
        try:
            cell = self.model.layer_hidden.cell
        except AttributeError as e:
            raise ValueError("read_probe requires a .cell-nested hidden layer "
                             "(baseline family); this model has none") from e
        v_mem = cell.potential.detach().cpu().numpy().reshape(-1)
        spikes = cell.prev_spike.detach().cpu().numpy().reshape(-1)
        v_th = (cell.base_threshold + cell.fatigue.clamp(min=0)).detach().cpu().numpy().reshape(-1)
        return {"spikes": spikes, "v_mem": v_mem, "v_th_eff": v_th}
```

- [ ] **Step 3b: Create sim/probe.py**

```python
# sim/probe.py
"""AttributeProbe -- ring-buffer of hidden-state snapshots for the live net panel.

Decoupled from SimStepper: the driver (UI loop / test) calls record() after each
step with the backend's read_probe() dict + the step's 5 params. sample_every
decouples UI refresh from the physics dt (nengo.Probe pattern).
"""
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ProbeFrame:
    t: int
    spikes: np.ndarray      # (H,)
    v_mem: np.ndarray       # (H,)
    v_th_eff: np.ndarray    # (H,)
    params: np.ndarray      # (5,)


class AttributeProbe:
    def __init__(self, capacity=500, sample_every=1):
        if sample_every < 1:
            raise ValueError("sample_every must be >= 1")
        self.capacity = capacity
        self.sample_every = sample_every
        self._buf = deque(maxlen=capacity)
        self._count = 0

    def record(self, t, probe, params):
        if self._count % self.sample_every == 0:
            self._buf.append(ProbeFrame(
                t=t,
                spikes=np.asarray(probe["spikes"], dtype=np.float64),
                v_mem=np.asarray(probe["v_mem"], dtype=np.float64),
                v_th_eff=np.asarray(probe["v_th_eff"], dtype=np.float64),
                params=np.asarray(params, dtype=np.float64).reshape(-1),
            ))
        self._count += 1

    def frames(self):
        return list(self._buf)

    def spikes_matrix(self):
        """(frames, H) raster of last-tick spikes; empty (0,0) if no frames."""
        return np.stack([f.spikes for f in self._buf]) if self._buf else np.empty((0, 0))

    def params_matrix(self):
        return np.stack([f.params for f in self._buf]) if self._buf else np.empty((0, 5))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sim_probe.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add sim/backend.py sim/probe.py tests/test_sim_probe.py
git commit -m "feat(sim): read_probe (zero-intrusion ALIF snapshot) + AttributeProbe ring-buffer"
```

---

### Task 2: `EventInjector.log()` + `ReplayLog`

**Files:**
- Modify: `sim/events.py` (enqueue-log + `log()`)
- Create: `sim/replay.py`
- Test: `tests/test_sim_replay.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sim_replay.py
import os, sys
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion   # noqa: E402
from sim.backend import SoftwareBackend       # noqa: E402
from sim.stepper import SimStepper            # noqa: E402
from sim.events import EventInjector          # noqa: E402
from sim.replay import ReplayLog              # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def _scn():
    return np.array([30.0, 1.5, 2.0, 1.5, 1.5]), np.full(60, 20.0), 25.0, 20.0


def test_replay_reruns_bit_identical():
    pg, vl, s0, v0 = _scn()
    inj = EventInjector()
    inj.enqueue(tick=20, verb="brake_leader", target_v=5.0, duration=10)
    orig = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0,
                      injector=inj).run()
    log = ReplayLog.from_injector(seed=0, injector=inj)
    rerun = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0,
                       injector=log.build_injector()).run()
    for k in ("s", "v", "vl", "dv", "a_ego", "params"):
        np.testing.assert_array_equal(orig[k], rerun[k])


def test_replaylog_json_roundtrips():
    inj = EventInjector()
    inj.enqueue(tick=3, verb="brake_leader", target_v=8.0, duration=5)
    log = ReplayLog.from_injector(seed=7, injector=inj)
    back = ReplayLog.from_json(log.to_json())
    assert back.seed == 7
    assert back.events == [{"tick": 3, "verb": "brake_leader",
                            "params": {"target_v": 8.0, "duration": 5}}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sim_replay.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.replay'`

- [ ] **Step 3a: Add the enqueue-log to `EventInjector` (sim/events.py)**

In `EventInjector.__init__`, add `self._log = []` (after `self._seq = 0`):

```python
    def __init__(self):
        self._events = []                       # list[Event]
        self._seq = 0
        self._log = []                          # full enqueue history (for ReplayLog)
        self._brake = None                      # (t0, v_start, target, duration) | None
```

In `enqueue`, append to the log:

```python
    def enqueue(self, tick, verb, **params):
        self._events.append(Event(tick=int(tick), seq=self._seq, verb=verb, params=params))
        self._log.append({"tick": int(tick), "verb": verb, "params": dict(params)})
        self._seq += 1
```

Add a `log()` accessor (after `enqueue`):

```python
    def log(self):
        return [dict(e) for e in self._log]
```

- [ ] **Step 3b: Create sim/replay.py**

```python
# sim/replay.py
"""ReplayLog -- seed + event-log for bit-identical reruns (repeatable science bench).

Captures the scenario seed and the full event enqueue history so a session can be
replayed exactly (SIMULATOR_DESIGN.md §6). JSON-serializable.
"""
import json
from dataclasses import dataclass, field

from .events import EventInjector


@dataclass
class ReplayLog:
    seed: int
    events: list = field(default_factory=list)   # list of {tick, verb, params}

    @classmethod
    def from_injector(cls, seed, injector):
        return cls(seed=int(seed), events=injector.log())

    def build_injector(self):
        inj = EventInjector()
        for e in self.events:
            inj.enqueue(e["tick"], e["verb"], **e["params"])
        return inj

    def to_json(self):
        return json.dumps({"seed": self.seed, "events": self.events})

    @classmethod
    def from_json(cls, s):
        d = json.loads(s)
        return cls(seed=int(d["seed"]), events=list(d["events"]))
```

- [ ] **Step 4: Run the full sim suite (incl. Plan 1 golden + Plan 2 events regression)**

Run: `python -m pytest tests/ -q -k "sim or champion_io"`
Expected: PASS (all sim + champion_io tests). The Plan 2 event tests must still pass — proof the enqueue-log addition was purely additive.

- [ ] **Step 5: Commit**

```bash
git add sim/events.py sim/replay.py tests/test_sim_replay.py
git commit -m "feat(sim): EventInjector log + ReplayLog (bit-identical rerun, JSON)"
```

---

## Self-Review

**Spec coverage (SIMULATOR_DESIGN.md):**
- §5 `AttributeProbe` (ring-buffer of `potential/fatigue/prev_spike`, `sample_every`, zero intrusion) → Task 1. ✓
- §5 v_th_eff = `base_threshold + fatigue.clamp(min=0)` (matches neurons.py:61) → `read_probe`. ✓
- §6 `ReplayLog` (seed + event-log → bit-identical rerun) → Task 2. ✓
- Regression: full sim suite (Plan 1 golden + Plan 2 events) re-run in Task 2 Step 4. ✓
- Deferred (Plan 4 / later): per-tick probe granularity (v1 = per-step default), the pyqtgraph views themselves (UI).

**Placeholder scan:** none. **Type consistency:** `read_probe()` dict keys (`spikes/v_mem/v_th_eff`) consumed by `AttributeProbe.record`; `EventInjector.log()` shape (`{tick,verb,params}`) consumed by `ReplayLog.build_injector` + asserted in the JSON test.

---

## Execution Handoff

Inline execution (established for this track). After Plan 3: **STOP before Plan 4 (UI)** for a checkpoint — the UI has visual/UX decisions (design §11: viewport scale, follow-ego, scenario list, sample_every default).
