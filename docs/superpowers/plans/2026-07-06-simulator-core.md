# Simulator Core (SimStepper + backend seam) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the headless closed-loop engine of the plug&play simulator — a single-step `SimStepper` behind a swappable `NetworkBackend` seam — that reproduces `utils.closed_loop_eval.simulate()` **bit-identically**.

**Architecture:** `SimStepper` is a *structural* refactor of `simulate()` (same operations and order, mutable state hoisted into an explicit `SimState`). It drives a `NetworkBackend` (SW today via `champion_io`, FPGA in Fase ③). A `run()` convenience replays all N steps to prove bit-identical parity against the batch `simulate()` (the design's regression anchor, §3). No UI, no dynamic events yet — this is the correctness keystone.

**Tech Stack:** Python, PyTorch (CPU, `torch.no_grad`), NumPy, pytest. Reuses `utils/closed_loop_eval.py` helpers (`_norm_obs`, `_plant_step`, `_channel_obs`), `core.network.CF_FSNN_Net.acc_iidm_accel`, and `utils/champion_io.py` (loader).

**This is Plan 1 of 4** for the MVP v1 (`SIMULATOR_DESIGN.md`):
1. **Core** — SimStepper + backend seam + golden *(this plan)*.
2. Events + Scenario — `EventInjector` (live `brake_leader`, generalizes `cut_in`) + `Scenario` (wraps `build_scenarios`).
3. Probe + Replay — `AttributeProbe` (ALIF `potential/fatigue/prev_spike` ring-buffer) + `ReplayLog`.
4. UI — PySide6/pyqtgraph `topdown` + `netpanel` + `loop` + `run_simulator.py`.

**Scope note (from champion_io recon):** `SoftwareBackend` wraps `model.forward_step`, which only the **`baseline`** family exposes. `eventprop_alif_full` (incl. Donatello) is sequence-only — its live per-step path is a later plan. Plan 1's golden runs a baseline champion (`R33_C2_A1_T12_fix`).

---

## File Structure

| File | Responsibility |
|---|---|
| `sim/__init__.py` | Package marker |
| `sim/state.py` | `SimState` (mutable closed-loop state), `StepResult` (frozen per-step snapshot) |
| `sim/backend.py` | `NetworkBackend` Protocol, `SoftwareBackend` (wraps champion model), `FpgaBackend` (stub), `make_backend()` |
| `sim/stepper.py` | `SimStepper` — single-step engine (hoist of `simulate()`), `step()` + `run()` |
| `tests/test_sim_stepper.py` | Golden: SimStepper `run()` == `simulate()` bit-identical (SW + oracle + plant/channel) |

Reused (not modified): `utils/closed_loop_eval.py`, `core/network.py`, `utils/champion_io.py`. `core/` stays frozen.

---

### Task 1: `sim/` package + state types

**Files:**
- Create: `sim/__init__.py`
- Create: `sim/state.py`
- Test: `tests/test_sim_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sim_state.py
import os, sys
import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.state import SimState, StepResult  # noqa: E402


def test_simstate_defaults_are_independent():
    a, b = SimState(), SimState()
    a.pl_state["x"] = 1
    assert b.pl_state == {}          # default_factory, not shared
    assert a.t == 0 and a.collided is False


def test_stepresult_is_frozen():
    r = StepResult(t=0, s=25.0, v=20.0, vl=20.0, dv=0.0, a_ego=0.0,
                   params=np.zeros(5), collided=False)
    with pytest.raises(Exception):
        r.s = 1.0                    # frozen dataclass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sim_state.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim'`

- [ ] **Step 3: Write minimal implementation**

```python
# sim/__init__.py
"""Plug&play closed-loop simulator (MVP v1). See document/SIMULATOR_DESIGN.md."""
```

```python
# sim/state.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sim_state.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add sim/__init__.py sim/state.py tests/test_sim_state.py
git commit -m "feat(sim): SimState + StepResult types for closed-loop stepper"
```

---

### Task 2: `NetworkBackend` seam + `SoftwareBackend`

**Files:**
- Create: `sim/backend.py`
- Test: `tests/test_sim_backend.py`

The seam is synchronous in v1 (`reset()` + `infer(obs)`), matching the design's "sincrono/thread-agnostic" contract (§2). The `set_input/step/get_output` split arrives with `FpgaBackend` (Fase ③), where async DMA needs it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sim_backend.py
import os, sys
import torch
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion          # noqa: E402
from sim.backend import SoftwareBackend, FpgaBackend, make_backend  # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def test_software_backend_infer_equals_forward_step():
    # Two fresh loads of the same champion → deterministic, independent state.
    ref = load_champion(CHAMP).model
    ref.eval(); ref.reset_state(1, "cpu")
    be = make_backend("software", model=load_champion(CHAMP).model)
    be.reset()
    obs = torch.tensor([[0.4, 0.3, 0.5, 0.3]], dtype=torch.float32)
    expected = ref.forward_step(obs)
    got = be.infer(obs)
    assert torch.equal(got, expected)         # bit-identical
    assert tuple(got.shape) == (1, 5)


def test_fpga_backend_is_stub():
    with pytest.raises(NotImplementedError):
        FpgaBackend()


def test_make_backend_rejects_unknown_and_missing_model():
    with pytest.raises(ValueError):
        make_backend("software")              # no model
    with pytest.raises(ValueError):
        make_backend("banana")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sim_backend.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.backend'`

- [ ] **Step 3: Write minimal implementation**

```python
# sim/backend.py
"""Compute seam for the simulator: SW today, FPGA (Fase 3) tomorrow.

v1 contract is synchronous (reset + infer). The set_input/step/get_output
split (SIMULATOR_DESIGN.md §2) lands with FpgaBackend, where async DMA needs it.
"""
from typing import Optional, Protocol

import torch


class NetworkBackend(Protocol):
    def reset(self) -> None: ...
    def infer(self, obs_norm: torch.Tensor) -> torch.Tensor: ...   # (1,4) -> (1,5)


class SoftwareBackend:
    """Wraps a champion_io-loaded CF_FSNN model; forward_step per control step."""

    def __init__(self, model, device: str = "cpu"):
        self.model = model
        self.device = device

    def reset(self) -> None:
        self.model.eval()
        self.model.reset_state(1, self.device)

    def infer(self, obs_norm: torch.Tensor) -> torch.Tensor:
        return self.model.forward_step(obs_norm.to(self.device))


class FpgaBackend:
    """Stub — realized in Fase 3 (PYNQ overlay + AXI/DMA). Same seam."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "FpgaBackend arrives in Fase 3 (see document/POST_FPGA_ROADMAP.md)."
        )


def make_backend(target: str, model=None, device: str = "cpu") -> NetworkBackend:
    if target == "software":
        if model is None:
            raise ValueError("software backend requires a loaded model")
        return SoftwareBackend(model, device)
    if target == "fpga":
        return FpgaBackend()
    raise ValueError(f"unknown backend target: {target!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sim_backend.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add sim/backend.py tests/test_sim_backend.py
git commit -m "feat(sim): NetworkBackend seam + SoftwareBackend (champion forward_step)"
```

---

### Task 3: `SimStepper` + GOLDEN (bit-identical to `simulate()`)

**Files:**
- Create: `sim/stepper.py`
- Test: `tests/test_sim_stepper.py`

`SimStepper.step()` mirrors the loop body of `simulate()` (utils/closed_loop_eval.py:170-211) operation-for-operation, reusing the exact helpers so the result is bit-identical. `run()` replays all N steps into the same dict shape `simulate()` returns.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sim_stepper.py
import os, sys
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion            # noqa: E402
from utils.closed_loop_eval import simulate            # noqa: E402
from sim.backend import SoftwareBackend                # noqa: E402
from sim.stepper import SimStepper                     # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")
SERIES = ("s", "v", "vl", "dv", "a_ego", "params")


def _scenario():
    params_gt = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
    t = np.arange(60)
    v_leader = 20.0 + 3.0 * np.sin(0.1 * t)
    return params_gt, v_leader, 25.0, 20.0        # params_gt, v_leader, s_init, v_init


def test_stepper_sw_matches_simulate_bit_identical():
    pg, vl, s0, v0 = _scenario()
    ref = simulate(load_champion(CHAMP).model, pg, vl, s0, v0)
    got = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0).run()
    for k in SERIES:
        np.testing.assert_array_equal(got[k], ref[k])
    assert got["collided"] == ref["collided"]
    assert got["min_gap"] == ref["min_gap"]


def test_stepper_oracle_matches_simulate():
    pg, vl, s0, v0 = _scenario()
    ref = simulate(None, pg, vl, s0, v0)               # oracle (constant params_gt)
    got = SimStepper(None, pg, vl, s0, v0).run()        # backend=None → oracle
    for k in SERIES:
        np.testing.assert_array_equal(got[k], ref[k])


def test_stepper_matches_simulate_with_plant_and_channel():
    pg, vl, s0, v0 = _scenario()
    plant = {"tau_act": 0.3, "jerk_max": 5.0}
    channel = {"pdr": 0.8, "latency_steps": 2, "seed": 7}
    ref = simulate(load_champion(CHAMP).model, pg, vl, s0, v0, plant=plant, channel=channel)
    got = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0,
                     plant=plant, channel=channel).run()
    for k in SERIES:
        np.testing.assert_array_equal(got[k], ref[k])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sim_stepper.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.stepper'`

- [ ] **Step 3: Write minimal implementation**

```python
# sim/stepper.py
"""SimStepper — single-step closed-loop engine.

Structural refactor of utils.closed_loop_eval.simulate(): identical operations
and order, mutable state hoisted into SimState. Reuses simulate()'s helpers so
the result is bit-identical (tests/test_sim_stepper.py). The UI loop calls step()
per QTimer tick; run() is a batch convenience used by the golden test.

backend=None reproduces simulate()'s oracle path (constant params_gt).
"""
import numpy as np
import torch

from config import ACC_AL_TAU, ACC_COOLNESS, DT
from core.network import CF_FSNN_Net
from utils.closed_loop_eval import _channel_obs, _norm_obs, _plant_step

from .state import SimState, StepResult


class SimStepper:
    def __init__(self, backend, params_gt, v_leader, s_init, v_init,
                 cut_in=None, plant=None, channel=None, device="cpu"):
        self.backend = backend                     # None → oracle
        self.params_gt = np.asarray(params_gt, dtype=np.float64)
        self.v_leader = np.asarray(v_leader, dtype=np.float64)
        self.s_init = float(s_init)
        self.v_init = float(v_init)
        self.cut_in = cut_in
        self.plant = plant
        self.channel = channel
        self.device = device
        self.N = len(self.v_leader)
        self.alpha_al = float(np.exp(-DT / ACC_AL_TAU))
        self.pg = torch.tensor(self.params_gt, dtype=torch.float32).view(1, 5)
        self.reset()

    def reset(self) -> None:
        self.st = SimState(t=0, s=self.s_init, v=self.v_init,
                           a_l_filt=0.0, vl_prev=float(self.v_leader[0]))
        self.ch_rng = (np.random.default_rng(self.channel.get("seed", 0))
                       if self.channel is not None else None)
        if self.backend is not None:
            self.backend.reset()

    @torch.no_grad()
    def step(self) -> StepResult:
        st = self.st
        t = st.t
        if self.cut_in is not None and t == int(self.cut_in[0]):
            st.s = float(self.cut_in[1])
        vl = float(self.v_leader[t])
        dv = st.v - vl
        if self.channel is not None:
            s_obs, vl_obs, _age = _channel_obs(st.s, vl, st.ch_state, self.channel,
                                               self.ch_rng, st.v)
        else:
            s_obs, vl_obs = st.s, vl
        dv_obs = st.v - vl_obs

        if self.backend is not None:
            params = self.backend.infer(_norm_obs(s_obs, st.v, dv_obs, vl_obs))
        else:
            params = self.pg

        a_l_raw = (vl_obs - st.vl_prev) / DT
        st.a_l_filt = self.alpha_al * st.a_l_filt + (1.0 - self.alpha_al) * a_l_raw
        st.vl_prev = vl_obs

        a_cmd = float(CF_FSNN_Net.acc_iidm_accel(
            torch.tensor([max(s_obs, 1e-3)]), torch.tensor([st.v]),
            torch.tensor([dv_obs]), torch.tensor([st.a_l_filt]),
            params, coolness=ACC_COOLNESS)[0])
        a_ego = _plant_step(a_cmd, st.v, st.pl_state, self.plant) if self.plant is not None else a_cmd

        # Peek the ballistic update so this step's result carries the collided flag.
        v_new = max(0.0, st.v + a_ego * DT)
        s_new = st.s + (vl - v_new) * DT           # physics uses TRUE vl (channel degrades only perception)
        collided = s_new <= 0.0

        res = StepResult(t=t, s=st.s, v=st.v, vl=vl, dv=dv, a_ego=a_ego,
                         params=params.view(-1).cpu().numpy(), collided=collided)

        st.v, st.s = v_new, s_new
        if collided:
            st.collided = True
            st.impact_dv = max(0.0, st.v - vl)
        st.t += 1
        return res

    def run(self) -> dict:
        """Replay all N steps → same dict shape as simulate() (golden comparison)."""
        series = {k: [] for k in ("s", "v", "vl", "dv", "a_ego")}
        params_used = []
        for _ in range(self.N):
            r = self.step()
            series["s"].append(r.s); series["v"].append(r.v); series["vl"].append(r.vl)
            series["dv"].append(r.dv); series["a_ego"].append(r.a_ego)
            params_used.append(r.params)
            if r.collided:
                break
        out = {k: np.asarray(val, dtype=np.float64) for k, val in series.items()}
        out["params"] = np.asarray(params_used, dtype=np.float64)
        out["collided"] = self.st.collided
        out["min_gap"] = float(self.st.s) if self.st.collided else float(out["s"].min())
        out["impact_dv"] = float(self.st.impact_dv)
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sim_stepper.py -q`
Expected: PASS (3 passed). If any array is *not* bit-identical, do NOT relax the tolerance — a mismatch means the refactor diverged from `simulate()`; diff the operation order and fix the stepper.

- [ ] **Step 5: Run the whole sim suite + commit**

Run: `python -m pytest tests/test_sim_state.py tests/test_sim_backend.py tests/test_sim_stepper.py -q`
Expected: PASS (8 passed)

```bash
git add sim/stepper.py tests/test_sim_stepper.py
git commit -m "feat(sim): SimStepper single-step engine, bit-identical to simulate()"
```

---

## Self-Review

**Spec coverage (against SIMULATOR_DESIGN.md):**
- §2 `SimStepper + SimState` → Tasks 1, 3. ✓
- §2 `NetworkBackend` (SoftwareBackend / FpgaBackend stub / make_backend) → Task 2. ✓
- §3 `SimStepper` = single-step refactor of `simulate()`, **golden bit-identical** → Task 3. ✓
- §3 "physics uses TRUE vl; channel degrades only perception" → preserved in `step()` (uses `vl`, not `vl_obs`, for the ballistic update). ✓
- Deferred (later plans, explicitly): `CarFollowingModel` registry (v1 has one model → `acc_iidm_accel` called directly), `EventInjector`/`Scenario` (Plan 2), `AttributeProbe`/`ReplayLog` (Plan 3), UI (Plan 4). Noted in header.

**Placeholder scan:** none — every step has runnable code/commands.

**Type consistency:** `SimState`/`StepResult` (Task 1) used consistently in Task 3; `NetworkBackend.reset()/infer()` (Task 2) called by `SimStepper` (Task 3); `make_backend`/`SoftwareBackend` names match across tasks.

**Known limitation (documented, not a gap):** golden runs a `baseline` champion because `SoftwareBackend.infer` needs `forward_step`; `eventprop_alif_full` live-stepping is a later plan.

---

## Execution Handoff

Two execution options once approved:
1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.
2. **Inline Execution** — tasks run in this session with checkpoints.
