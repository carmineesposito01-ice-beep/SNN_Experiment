# Trajectory + Safety Panels Implementation Plan (Extension Phase 3a)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`) syntax.
> Runs in **`cf_sim`** (offscreen for Qt). Spec: `docs/superpowers/specs/2026-07-08-trajectory-safety-panels-design.md`. All pyqtgraph API here is already used elsewhere (GraphicsLayoutWidget X-linked plots, InfiniteLine, downsampling/clip).

**Goal:** Two new live docks — **Trajectory** (gap/speeds/accel) and **Safety** (TTC/DRAC/time-headway) — fed by a UI-layer `TrajectoryBuffer` of `StepResult` (the probe stays untouched).

**Architecture:** `sim/ui/trajectory.py` (`TrajectoryBuffer`) + `sim/ui/metrics.py` (pure `ttc`/`drac`/`time_headway`) → `TrajectoryPanel`/`SafetyPanel` in `panels.py` (intra-panel X-link only) → app records each `StepResult` and wires 2 docks (9 → 11), presets updated. No cross-dock X-link (SpikeRate lesson).

**Tech Stack:** PySide6 6.11, pyqtgraph 0.14, NumPy, pytest — `cf_sim`.

---

## File Structure

| File | Change |
|---|---|
| `sim/ui/trajectory.py` | **Create** — `TrajectoryBuffer` |
| `sim/ui/metrics.py` | **Create** — `ttc`/`drac`/`time_headway` |
| `sim/ui/panels.py` | **Modify** — add `TrajectoryPanel`, `SafetyPanel` (+ `from sim.ui import metrics`) |
| `sim/ui/layout.py` | **Modify** — `DOCK_ORDER` (11); presets place the two |
| `sim/ui/app.py` | **Modify** — `TrajectoryBuffer`; build/wire panels; record in `_paint` |
| `tests/test_sim_trajectory.py` | **Create** — buffer + metrics |
| `tests/test_sim_panels.py` | **Append** — Trajectory/Safety smoke |
| `tests/test_sim_layout.py`, `tests/test_sim_ui_smoke.py` | **Modify** — 11-dock assertions |

---

### Task 1: `TrajectoryBuffer` + `metrics.py`

**Files:** Create `sim/ui/trajectory.py`, `sim/ui/metrics.py`, `tests/test_sim_trajectory.py`.

- [ ] **Step 1: Write failing tests** — create `tests/test_sim_trajectory.py`:

```python
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.state import StepResult            # noqa: E402
from sim.ui.trajectory import TrajectoryBuffer  # noqa: E402
from sim.ui import metrics                   # noqa: E402


def _r(t, s):
    return StepResult(t=t, s=s, v=15.0, vl=13.0, dv=2.0, a_ego=-0.5, params=np.zeros(5), collided=False)


def test_trajectory_buffer_arrays_and_cap():
    tb = TrajectoryBuffer(capacity=3)
    for t in range(5):
        tb.record(_r(t, 20 - t))
    assert len(tb) == 3
    a = tb.arrays()
    assert a["t"].tolist() == [2, 3, 4]
    assert a["s"].tolist() == [18, 17, 16]
    assert a["dv"].tolist() == [2, 2, 2]


def test_trajectory_buffer_empty():
    a = TrajectoryBuffer().arrays()
    assert a["t"].size == 0 and a["s"].size == 0


def test_metrics_values():
    assert float(metrics.ttc(20, 2)) == 10.0                 # s/dv
    assert np.isinf(float(metrics.ttc(20, -1)))              # opening -> inf
    assert np.isinf(float(metrics.ttc(20, 0)))               # not closing -> inf
    assert abs(float(metrics.drac(20, 2)) - 0.1) < 1e-9      # dv^2/2s
    assert float(metrics.drac(20, -1)) == 0.0
    assert float(metrics.time_headway(20, 10)) == 2.0        # s/v
    assert np.isinf(float(metrics.time_headway(20, 0)))


def test_metrics_vectorised():
    s = np.array([20.0, 10.0]); dv = np.array([2.0, -1.0])
    assert np.allclose(metrics.ttc(s, dv), [10.0, np.inf])
```

- [ ] **Step 2: Run — verify FAIL** (`ModuleNotFoundError: sim.ui.trajectory`)

Run: `conda run -n cf_sim python -m pytest tests/test_sim_trajectory.py -q`

- [ ] **Step 3a: Create `sim/ui/trajectory.py`**

```python
"""TrajectoryBuffer -- UI-layer ring buffer of StepResult (physics trajectory), so the golden probe
(sim/probe.py) stays untouched. The app records each StepResult; Trajectory/Safety panels read it."""
from collections import deque

import numpy as np

_FIELDS = ("t", "s", "v", "vl", "dv", "a_ego")


class TrajectoryBuffer:
    def __init__(self, capacity=500):
        self._buf = deque(maxlen=capacity)

    def record(self, result):
        self._buf.append(result)

    def __len__(self):
        return len(self._buf)

    def arrays(self):
        if not self._buf:
            return {k: np.empty(0) for k in _FIELDS}
        return {k: np.array([getattr(r, k) for r in self._buf], dtype=float) for k in _FIELDS}
```

- [ ] **Step 3b: Create `sim/ui/metrics.py`**

```python
"""Pure car-following safety metrics (vectorised, scalar-friendly). Closing speed dv>0 = approaching."""
import numpy as np


def ttc(s, dv):
    s = np.asarray(s, dtype=float)
    dv = np.asarray(dv, dtype=float)
    return np.where(dv > 0, s / np.where(dv > 0, dv, 1.0), np.inf)


def drac(s, dv):
    s = np.asarray(s, dtype=float)
    dv = np.asarray(dv, dtype=float)
    return np.where(dv > 0, dv ** 2 / (2.0 * np.where(s > 0, s, 1e-9)), 0.0)


def time_headway(s, v):
    s = np.asarray(s, dtype=float)
    v = np.asarray(v, dtype=float)
    return np.where(v > 0, s / np.where(v > 0, v, 1.0), np.inf)
```

- [ ] **Step 4: Run — verify PASS**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_trajectory.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add sim/ui/trajectory.py sim/ui/metrics.py tests/test_sim_trajectory.py
git commit -m "feat(sim/ui): TrajectoryBuffer (UI-layer StepResult ring) + pure safety metrics"
```

---

### Task 2: `TrajectoryPanel` + `SafetyPanel`

**Files:** Modify `sim/ui/panels.py`; append to `tests/test_sim_panels.py`.

- [ ] **Step 1: Write failing tests** (append to `tests/test_sim_panels.py`):

```python
from sim.state import StepResult                 # noqa: E402
from sim.ui.panels import SafetyPanel, TrajectoryPanel  # noqa: E402
from sim.ui.trajectory import TrajectoryBuffer    # noqa: E402


def _traj(n=6):
    tb = TrajectoryBuffer()
    for t in range(n):
        tb.record(StepResult(t=t, s=20.0 - t, v=15.0, vl=13.0, dv=2.0, a_ego=-0.5,
                             params=np.zeros(5), collided=False))
    return tb


def test_trajectory_panel_updates(qapp):
    p = TrajectoryPanel()
    p.update_frame(_traj())
    assert p._c_s.getData()[1] is not None and float(p._c_s.getData()[1][0]) == 20.0


def test_safety_panel_updates_and_refs(qapp):
    p = SafetyPanel()
    p.update_frame(_traj())
    ttc0 = p._c_ttc.getData()[1]
    assert ttc0 is not None and abs(float(ttc0[0]) - 10.0) < 1e-6      # s=20, dv=2 -> TTC 10 s
    assert p._ttc_ref.isVisible() and abs(p._ttc_ref.value() - 1.5) < 1e-6
    assert p._drac_ref.isVisible() and abs(p._drac_ref.value() - 3.35) < 1e-6
```

- [ ] **Step 2: Run — verify FAIL** (`ImportError: TrajectoryPanel`)

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -q`

- [ ] **Step 3: Add to `sim/ui/panels.py`** — the module import (top, with the other imports) and two classes (append at end):

Add near the top imports:
```python
from sim.ui import metrics
```

Append at the end of the file:
```python
class TrajectoryPanel(QWidget):
    """gap / speeds (ego, leader, Δv) / accel over time — 3 X-linked sub-plots."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._glw = pg.GraphicsLayoutWidget()
        layout.addWidget(self._glw)
        self._pg = self._glw.addPlot(row=0, col=0)
        self._pv = self._glw.addPlot(row=1, col=0)
        self._pa = self._glw.addPlot(row=2, col=0)
        self._pg.setLabel("left", "gap", units="m")
        self._pv.setLabel("left", "speed", units="m/s")
        self._pa.setLabel("left", "accel", units="m/s^2")
        self._pa.setLabel("bottom", "time", units="steps")
        for p in (self._pg, self._pv, self._pa):
            p.setDownsampling(auto=True, mode="peak")
            p.setClipToView(True)
            p.showGrid(x=False, y=True, alpha=0.2)
        self._pv.setXLink(self._pg)
        self._pa.setXLink(self._pg)
        self._c_s = self._pg.plot(pen=pg.mkPen("#2e8b57", width=2))
        self._c_v = self._pv.plot(pen=pg.mkPen("#2a7fb8", width=2))
        self._c_vl = self._pv.plot(pen=pg.mkPen("#d1495b", width=2))
        self._c_dv = self._pv.plot(pen=pg.mkPen("#e8871e", width=1, style=Qt.DashLine))
        self._c_a = self._pa.plot(pen=pg.mkPen("#7b3fa0", width=2))

    def update_frame(self, traj):
        a = traj.arrays()
        if a["t"].size == 0:
            return
        self._c_s.setData(a["s"])
        self._c_v.setData(a["v"])
        self._c_vl.setData(a["vl"])
        self._c_dv.setData(a["dv"])
        self._c_a.setData(a["a_ego"])


_SAFETY_CAP = 30.0


class SafetyPanel(QWidget):
    """TTC + time-headway (s) / DRAC (m/s^2), with dashed threshold reference lines."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._glw = pg.GraphicsLayoutWidget()
        layout.addWidget(self._glw)
        self._pt = self._glw.addPlot(row=0, col=0)
        self._pd = self._glw.addPlot(row=1, col=0)
        self._pt.setLabel("left", "time", units="s")
        self._pd.setLabel("left", "DRAC", units="m/s^2")
        self._pd.setLabel("bottom", "time", units="steps")
        for p in (self._pt, self._pd):
            p.setDownsampling(auto=True, mode="peak")
            p.setClipToView(True)
            p.showGrid(x=False, y=True, alpha=0.2)
        self._pd.setXLink(self._pt)
        self._c_ttc = self._pt.plot(pen=pg.mkPen("#d1495b", width=2))
        self._c_th = self._pt.plot(pen=pg.mkPen("#2a7fb8", width=1, style=Qt.DashLine))
        self._c_drac = self._pd.plot(pen=pg.mkPen("#e8871e", width=2))
        self._ttc_ref = pg.InfiniteLine(pos=1.5, angle=0, pen=pg.mkPen("#9a9a9a", style=Qt.DashLine))
        self._drac_ref = pg.InfiniteLine(pos=3.35, angle=0, pen=pg.mkPen("#9a9a9a", style=Qt.DashLine))
        self._pt.addItem(self._ttc_ref)
        self._pd.addItem(self._drac_ref)

    def update_frame(self, traj):
        a = traj.arrays()
        if a["t"].size == 0:
            return
        self._c_ttc.setData(np.clip(metrics.ttc(a["s"], a["dv"]), 0, _SAFETY_CAP))
        self._c_th.setData(np.clip(metrics.time_headway(a["s"], a["v"]), 0, _SAFETY_CAP))
        self._c_drac.setData(metrics.drac(a["s"], a["dv"]))
```

- [ ] **Step 4: Run — verify PASS**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/panels.py tests/test_sim_panels.py
git commit -m "feat(sim/ui): TrajectoryPanel (gap/speeds/accel) + SafetyPanel (TTC/DRAC/headway)"
```

---

### Task 3: Wire the two docks into the app (11 docks + presets)

**Files:** Modify `sim/ui/layout.py`, `sim/ui/app.py`, `tests/test_sim_layout.py`.

- [ ] **Step 1: Update the layout test** — append to `tests/test_sim_layout.py`:

```python
def test_guida_shows_trajectory_and_safety(qapp):
    area, docks = _build_area()
    from sim.ui.layout import apply_guida
    apply_guida(area, docks)
    assert {"Road", "Trajectory", "Safety"} <= visible_docks(area)
```

- [ ] **Step 2: Run — verify FAIL** (`Trajectory` not in `DOCK_ORDER`)

Run: `conda run -n cf_sim python -m pytest tests/test_sim_layout.py::test_guida_shows_trajectory_and_safety -q`

- [ ] **Step 3a: `sim/ui/layout.py`** — 11 docks + presets:

```python
DOCK_ORDER = ["Road", "NetState", "SpikeRate", "v_mem", "Trajectory", "Safety",
              "v0", "T", "s0", "a", "b"]
```

Rewrite the four presets:
```python
def apply_overview(area, docks):
    _show(area, docks, "Road", "top")
    _show(area, docks, "NetState", "bottom", "Road")
    _show(area, docks, "v_mem", "bottom", "NetState")
    _show(area, docks, "Trajectory", "right", "v_mem")
    _show(area, docks, "Safety", "right", "Trajectory")
    _show(area, docks, "v0", "bottom", "v_mem")
    for prev, n in zip(["v0", "T", "s0", "a"], ["T", "s0", "a", "b"]):
        _show(area, docks, n, "right", prev)
    _show(area, docks, "SpikeRate", "right", "NetState")


def apply_guida(area, docks):
    for d in ("NetState", "SpikeRate", "v_mem"):
        _hide(docks, d)
    _show(area, docks, "Road", "top")
    _show(area, docks, "Trajectory", "bottom", "Road")
    _show(area, docks, "Safety", "right", "Trajectory")
    _show(area, docks, "v0", "bottom", "Trajectory")
    for n in ["T", "s0", "a", "b"]:
        _show(area, docks, n, "above", "v0")


def apply_identificazione(area, docks):
    for d in ("v_mem", "NetState", "SpikeRate", "Trajectory", "Safety"):
        _hide(docks, d)
    _show(area, docks, "Road", "top")
    _show(area, docks, "v0", "bottom", "Road")
    for prev, n in zip(["v0", "T", "s0", "a"], ["T", "s0", "a", "b"]):
        _show(area, docks, n, "bottom", prev)


def apply_neuro_debug(area, docks):
    _hide(docks, "Trajectory")
    _hide(docks, "Safety")
    _show(area, docks, "NetState", "left")
    _show(area, docks, "SpikeRate", "right", "NetState")
    _show(area, docks, "v_mem", "bottom", "NetState")
    _show(area, docks, "Road", "bottom", "v_mem")
    _show(area, docks, "v0", "right", "SpikeRate")
    for n in ["T", "s0", "a", "b"]:
        _show(area, docks, n, "above", "v0")
```

- [ ] **Step 3b: `sim/ui/app.py`**
  - Imports: add `TrajectoryPanel, SafetyPanel` to the `from sim.ui.panels import (...)` line; add `from sim.ui.trajectory import TrajectoryBuffer`.
  - Build panels (next to the others): `self._trajectory = TrajectoryPanel(); self._safety = SafetyPanel()`.
  - `widgets` map: add `"Trajectory": self._trajectory, "Safety": self._safety`.
  - In `select_scenario`, alongside the probe reset, add: `self._traj = TrajectoryBuffer()`.
  - In `_paint`, inside the `if results:` block (after `self._topdown.update_frame(results[-1])`), add:

```python
            for r in results:
                self._traj.record(r)
```

    and after the `_live_panels` loop, add:

```python
            self._trajectory.update_frame(self._traj)
            self._safety.update_frame(self._traj)
```

- [ ] **Step 4: Run — panels + layout + smoke**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py tests/test_sim_layout.py tests/test_sim_ui_smoke.py -q`
Expected: PASS (smoke `test_simapp_builds_docks` uses `set(DOCK_ORDER)` → adapts to 11).

- [ ] **Step 5: Full golden suite + render + commit + push**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_state.py tests/test_sim_backend.py tests/test_sim_stepper.py tests/test_sim_scenario.py tests/test_sim_events.py tests/test_sim_probe.py tests/test_sim_replay.py tests/test_sim_loop.py tests/test_sim_input_capture.py tests/test_sim_trajectory.py tests/test_sim_panels.py tests/test_sim_layout.py tests/test_sim_ui_smoke.py tests/test_sim_eventprop.py tests/test_champion_io.py -q`
Expected: PASS (all).

Render the **Guida** preset (Road + Trajectory + Safety foregrounded); confirm gap/speeds/accel + TTC (with the 1.5 s line) drop when braking. Send the PNG to the user.

```bash
git add sim/ui/layout.py sim/ui/app.py tests/test_sim_layout.py
git commit -m "feat(sim/ui): wire Trajectory + Safety docks (11 docks, presets updated)"
git push
```

---

## Self-Review

**Spec coverage:** D1 UI-layer `TrajectoryBuffer` (T1) ✓ · D2 pure metrics (T1) ✓ · D3 Trajectory 3 X-linked sub-plots (T2) ✓ · D4 Safety 2 sub-plots + 1.5 s / 3.35 refs (T2) ✓ · D5 11 docks + presets (T3) ✓ · D6 intra-panel X-link only, no cross-dock (T2 `setXLink` within each panel; app adds no cross-link) ✓.

**Placeholder scan:** none — full code for every unit; commands runnable.

**Consistency:** `TrajectoryBuffer.arrays()` keys (`t,s,v,vl,dv,a_ego`) consumed by both panels; `metrics.ttc/drac/time_headway` used by SafetyPanel + tested exactly; `DOCK_ORDER` 11 names match the `widgets` map (T3) and presets; `_traj` reset in `select_scenario`, appended in `_paint`, read by the two panels.

**Scope:** scrub (3b), energy dock (backlog), event-timeline out. Probe/core untouched (buffer is UI-layer).

---

## Execution Handoff

Inline execution (established), in `cf_sim`, TDD per task, render-inspect + send at Task 3 Step 5.
