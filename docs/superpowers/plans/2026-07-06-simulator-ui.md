# Simulator UI (PySide6 + pyqtgraph) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A runnable desktop app: load a baseline champion, pick a scenario, watch the cars top-down (camera follows ego) and the live network panel (spike raster / v_mem / 5 params), and inject a live `brake_leader` event — all driving the Plan 1-3 headless engine.

**Architecture:** `SimLoop` (pure Python, Fix-Your-Timestep accumulator) advances `SimStepper.step()` and records the `AttributeProbe`; it has **no Qt dependency** so it is fully unit-tested. The Qt widgets (`TopDownView`, `NetPanel`, `SimApp`) render the loop's output and are verified with **offscreen smoke tests** (`QT_QPA_PLATFORM=offscreen`) plus a **render-to-PNG** script for visual inspection.

**Decisions (locked with the user):** camera **follows ego**; scenario selector = **9 scenarios** (`scenario_library(..., include_tail=True)`) **+ manual**; `sample_every=1`, ring-buffer **500**; stack **PySide6 + pyqtgraph**.

**Tech Stack:** PySide6 (Qt6), pyqtgraph, NumPy, pytest (offscreen). Builds on `sim/` (Plans 1-3).

**This is Plan 4 of 4 — the last.** After it, the MVP v1 simulator is complete.

> **Note:** Qt/pyqtgraph tasks (2-5) may need small API tweaks at execution time; the offscreen smoke tests + PNG render are the guardrails. Task 1 is pure Python and needs no PySide6.

---

## File Structure

| File | Responsibility |
|---|---|
| `sim/ui/__init__.py` | Package marker |
| `sim/ui/loop.py` | `SimLoop` — Fix-Your-Timestep accumulator (pure Python, no Qt) |
| `sim/ui/topdown.py` | `TopDownView(QGraphicsView)` — ego+leader, camera follows ego |
| `sim/ui/netpanel.py` | `NetPanel(QWidget)` — pyqtgraph raster / v_mem / params |
| `sim/ui/app.py` | `SimApp(QMainWindow)` — controls + wiring (champion, scenario, run/pause, brake) |
| `scripts/run_simulator.py` | Entry point (`python scripts/run_simulator.py`) |
| `scripts/render_simulator_frame.py` | Offscreen render → PNG for visual verification |
| `tests/test_sim_loop.py` | Loop stepping/probe/done (no Qt) |
| `tests/test_sim_ui_smoke.py` | Offscreen instantiate + update of every widget (guarded by importorskip) |

---

### Task 1: `SimLoop` (Fix-Your-Timestep, pure Python)

**Files:**
- Create: `sim/ui/__init__.py`, `sim/ui/loop.py`
- Test: `tests/test_sim_loop.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sim_loop.py
import os, sys
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion   # noqa: E402
from sim.backend import SoftwareBackend       # noqa: E402
from sim.stepper import SimStepper            # noqa: E402
from sim.probe import AttributeProbe          # noqa: E402
from sim.ui.loop import SimLoop               # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def _loop(N=60):
    pg = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
    vl = np.full(N, 20.0)
    stepper = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, 25.0, 20.0)
    probe = AttributeProbe(capacity=100)
    return SimLoop(stepper, probe, dt_fixed=0.1), stepper, probe


def test_loop_accumulates_fixed_steps_and_records_probe():
    loop, stepper, probe = _loop()
    r = loop.tick(0.35)                    # 0.35 -> 3 fixed steps (rem ~0.05)
    assert len(r) == 3 and stepper.st.t == 3 and len(probe.frames()) == 3
    assert loop.tick(0.02) == []           # rem ~0.07 < 0.1 -> 0 steps
    assert len(loop.tick(0.05)) == 1       # rem ~0.12 -> 1 step


def test_loop_reports_done_and_never_overruns_N():
    loop, stepper, probe = _loop(N=10)
    loop.tick(100.0)                       # far more than 10 steps of budget
    assert stepper.st.t <= 10
    assert loop.done is True
    assert loop.tick(100.0) == []          # done -> no further steps
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sim_loop.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.ui'`

- [ ] **Step 3: Write minimal implementation**

```python
# sim/ui/__init__.py
"""PySide6/pyqtgraph UI for the simulator (MVP v1)."""
```

```python
# sim/ui/loop.py
"""SimLoop -- fixed-timestep driver (Fix-Your-Timestep, Glenn Fiedler), UI-agnostic.

Pure Python (no Qt): the app wires a QTimer to call tick(elapsed); tick advances
the physics in fixed dt steps and records the probe. Keeping this Qt-free makes the
loop logic fully testable without a display.
"""
from config import DT


class SimLoop:
    def __init__(self, stepper, probe=None, dt_fixed=DT):
        self.stepper = stepper
        self.probe = probe
        self.dt_fixed = float(dt_fixed)
        self._accum = 0.0

    @property
    def done(self) -> bool:
        st = self.stepper.st
        return bool(st.collided or st.t >= self.stepper.N)

    def tick(self, frame_dt):
        """Advance the sim by frame_dt seconds of real time; return the StepResults run."""
        self._accum += float(frame_dt)
        out = []
        while self._accum >= self.dt_fixed and not self.done:
            r = self.stepper.step()
            if self.probe is not None and hasattr(self.stepper.backend, "read_probe"):
                self.probe.record(r.t, self.stepper.backend.read_probe(), r.params)
            self._accum -= self.dt_fixed
            out.append(r)
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sim_loop.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add sim/ui/__init__.py sim/ui/loop.py tests/test_sim_loop.py
git commit -m "feat(sim/ui): SimLoop fixed-timestep driver (pure Python, no Qt)"
```

---

### Task 2: `TopDownView` (camera follows ego)

**Files:**
- Create: `sim/ui/topdown.py`
- Test: `tests/test_sim_ui_smoke.py` (topdown portion)

The follow-ego camera needs only the gap `s`: ego is pinned at scene origin, the leader sits `s + VEH_LEN` metres ahead, and the view re-centres on the ego each frame.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sim_ui_smoke.py
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6.QtWidgets import QApplication  # noqa: E402
from sim.state import StepResult            # noqa: E402
from sim.ui.topdown import TopDownView      # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _step(s):
    return StepResult(t=0, s=s, v=20.0, vl=20.0, dv=0.0, a_ego=0.0,
                      params=np.zeros(5), collided=False)


def test_topdown_instantiates_and_updates(qapp):
    view = TopDownView()
    view.update_frame(_step(30.0))
    x30 = view.leader_x_px()
    view.update_frame(_step(10.0))
    assert view.leader_x_px() < x30          # smaller gap -> leader closer
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sim_ui_smoke.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.ui.topdown'`

- [ ] **Step 3: Write minimal implementation**

```python
# sim/ui/topdown.py
"""Top-down view: ego (pinned) + leader, camera follows ego. Positions are (x,y,heading)
with y=0/heading=0 in v1 (2D-ready for future lane changes, design §9)."""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsView

PX_PER_M = 6.0
VEH_LEN_M = 5.0
VEH_W_M = 2.0


class TopDownView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene()
        self.setScene(self._scene)
        self._ego = self._vehicle(QColor("#2a7fb8"))       # ego (blue)
        self._leader = self._vehicle(QColor("#d1495b"))    # leader (red)
        self._ego.setPos(0.0, 0.0)

    def _vehicle(self, color):
        w, h = VEH_LEN_M * PX_PER_M, VEH_W_M * PX_PER_M
        item = QGraphicsRectItem(QRectF(-w / 2, -h / 2, w, h))
        item.setBrush(QBrush(color))
        self._scene.addItem(item)
        return item

    def leader_x_px(self) -> float:
        return float(self._leader.x())

    def update_frame(self, r):
        self._leader.setX((r.s + VEH_LEN_M) * PX_PER_M)    # gap ahead of ego
        self.centerOn(self._ego)                            # follow ego
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sim_ui_smoke.py -q`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add sim/ui/topdown.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim/ui): TopDownView (follow-ego camera)"
```

---

### Task 3: `NetPanel` (pyqtgraph: raster / v_mem / params)

**Files:**
- Create: `sim/ui/netpanel.py`
- Test: append to `tests/test_sim_ui_smoke.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# --- append to tests/test_sim_ui_smoke.py ---
from sim.probe import AttributeProbe        # noqa: E402
from sim.ui.netpanel import NetPanel        # noqa: E402


def test_netpanel_instantiates_and_updates(qapp):
    probe = AttributeProbe(capacity=50)
    for t in range(5):
        probe.record(t, {"spikes": (np.arange(8) % 2).astype(float),
                          "v_mem": np.linspace(0, 1, 8),
                          "v_th_eff": np.ones(8)}, np.arange(5) + t)
    panel = NetPanel()
    panel.update_frame(probe)               # must not raise
    assert panel.n_params_curves() == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sim_ui_smoke.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.ui.netpanel'`

- [ ] **Step 3: Write minimal implementation**

```python
# sim/ui/netpanel.py
"""Live network panel: spike raster (ImageItem), v_mem trace, 5 identified params."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget

_PARAM_NAMES = ["v0", "T", "s0", "a", "b"]
_PARAM_COLORS = ["#d1495b", "#2a7fb8", "#7b3fa0", "#e8871e", "#2e8b57"]


class NetPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self._raster_plot = pg.PlotWidget(title="spike raster (neuron × time)")
        self._raster_img = pg.ImageItem()
        self._raster_plot.addItem(self._raster_img)
        layout.addWidget(self._raster_plot)

        self._vmem_plot = pg.PlotWidget(title="v_mem (sample neurons)")
        self._vmem_curves = [self._vmem_plot.plot(pen=pg.mkPen(width=1)) for _ in range(4)]
        layout.addWidget(self._vmem_plot)

        self._param_plot = pg.PlotWidget(title="identified params [v0,T,s0,a,b]")
        self._param_curves = [self._param_plot.plot(pen=pg.mkPen(c, width=2), name=n)
                              for n, c in zip(_PARAM_NAMES, _PARAM_COLORS)]
        layout.addWidget(self._param_plot)

    def n_params_curves(self) -> int:
        return len(self._param_curves)

    def update_frame(self, probe):
        sm = probe.spikes_matrix()          # (frames, H)
        if sm.size:
            self._raster_img.setImage(sm.T, autoLevels=False, levels=(0.0, 1.0))
            frames = [f.v_mem for f in probe.frames()]
            vm = np.stack(frames)           # (frames, H)
            for i, curve in enumerate(self._vmem_curves):
                if i < vm.shape[1]:
                    curve.setData(vm[:, i])
        pm = probe.params_matrix()          # (frames, 5)
        if pm.size:
            for i, curve in enumerate(self._param_curves):
                curve.setData(pm[:, i])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sim_ui_smoke.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add sim/ui/netpanel.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim/ui): NetPanel (pyqtgraph raster/v_mem/params)"
```

---

### Task 4: `SimApp` (controls + wiring)

**Files:**
- Create: `sim/ui/app.py`
- Test: append to `tests/test_sim_ui_smoke.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# --- append to tests/test_sim_ui_smoke.py ---
from sim.ui.app import SimApp               # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def test_simapp_loads_champion_and_advances(qapp):
    win = SimApp(CHAMP)
    assert win.scenario_count() >= 10        # 9 library (include_tail) + manual
    win.select_scenario(0)
    win._advance(0.5)                        # 5 fixed steps, headless (no timer)
    assert win.loop.stepper.st.t >= 5
    win.inject_brake()                       # enqueues a brake_leader at current tick
    win._advance(0.5)                        # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sim_ui_smoke.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.ui.app'`

- [ ] **Step 3: Write minimal implementation**

```python
# sim/ui/app.py
"""SimApp -- main window: champion + scenario selector + run/pause + brake-leader,
wiring SimLoop + TopDownView + NetPanel via a QTimer (fixed-timestep)."""
import numpy as np
from PySide6.QtCore import QElapsedTimer, QTimer
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QPushButton, QVBoxLayout,
                               QWidget, QMainWindow)

from config import DT
from utils.champion_io import load_champion
from sim.backend import SoftwareBackend
from sim.stepper import SimStepper
from sim.probe import AttributeProbe
from sim.events import EventInjector
from sim.scenario import scenario_library, manual_scenario
from sim.ui.loop import SimLoop
from sim.ui.topdown import TopDownView
from sim.ui.netpanel import NetPanel

_UI_FPS_MS = 33          # ~30 Hz UI refresh; the accumulator runs physics at DT


class SimApp(QMainWindow):
    def __init__(self, champion_path):
        super().__init__()
        self.setWindowTitle("CF_FSNN Simulator")
        self._champ = load_champion(champion_path)
        pg0 = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
        self._scenarios = scenario_library(pg0, N=600, rng=np.random.default_rng(0),
                                            include_tail=True)
        self._scenarios.append(manual_scenario(pg0, np.full(600, 0.7 * 30.0), None, None)
                               if False else self._manual(pg0))

        self._topdown = TopDownView()
        self._netpanel = NetPanel()
        self._selector = QComboBox()
        self._selector.addItems([s.name for s in self._scenarios])
        self._run_btn = QPushButton("Run")
        self._run_btn.setCheckable(True)
        self._run_btn.toggled.connect(self._on_run_toggled)
        self._brake_btn = QPushButton("Brake leader")
        self._brake_btn.clicked.connect(self.inject_brake)

        controls = QHBoxLayout()
        for w in (self._selector, self._run_btn, self._brake_btn):
            controls.addWidget(w)
        self._selector.currentIndexChanged.connect(self.select_scenario)

        root = QVBoxLayout()
        root.addLayout(controls)
        root.addWidget(self._topdown, stretch=1)
        root.addWidget(self._netpanel, stretch=1)
        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._clock = QElapsedTimer()
        self.select_scenario(0)

    @staticmethod
    def _manual(pg0):
        return manual_scenario(pg0, np.full(600, 0.7 * float(pg0[0])),
                               s_init=2.0 + 0.7 * float(pg0[0]) * 1.5, v_init=0.7 * float(pg0[0]))

    def scenario_count(self) -> int:
        return len(self._scenarios)

    def select_scenario(self, idx: int):
        sc = self._scenarios[int(idx)]
        self._injector = EventInjector()
        self._probe = AttributeProbe(capacity=500, sample_every=1)
        backend = SoftwareBackend(self._champ.model)
        stepper = SimStepper.from_scenario(backend, sc, injector=self._injector)
        self.loop = SimLoop(stepper, self._probe, dt_fixed=DT)

    def inject_brake(self):
        st = self.loop.stepper.st
        base_vl = float(self.loop.stepper.v_leader[min(st.t, self.loop.stepper.N - 1)])
        self._injector.enqueue(st.t, "brake_leader", target_v=max(0.3 * base_vl, 2.0), duration=20)

    def _advance(self, frame_dt: float):
        results = self.loop.tick(frame_dt)
        if results:
            self._topdown.update_frame(results[-1])
            self._netpanel.update_frame(self._probe)
        return results

    def _on_run_toggled(self, running: bool):
        if running:
            self._clock.restart()
            self._timer.start(_UI_FPS_MS)
        else:
            self._timer.stop()

    def _on_timer(self):
        dt = self._clock.restart() / 1000.0
        self._advance(dt)
        if self.loop.done:
            self._run_btn.setChecked(False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sim_ui_smoke.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add sim/ui/app.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim/ui): SimApp window (scenario selector, run/pause, brake-leader)"
```

---

### Task 5: Entry point + visual render check

**Files:**
- Create: `scripts/run_simulator.py`, `scripts/render_simulator_frame.py`

- [ ] **Step 1: Create the entry point**

```python
# scripts/run_simulator.py
"""Launch the CF_FSNN simulator. Usage: python scripts/run_simulator.py [champion.pt]"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from sim.ui.app import SimApp

DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def main():
    champ = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    app = QApplication(sys.argv)
    win = SimApp(champ)
    win.resize(1000, 720)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create the offscreen render check**

```python
# scripts/render_simulator_frame.py
"""Offscreen: advance the sim a few seconds and grab the window to a PNG (visual check)."""
import os, sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from sim.ui.app import SimApp

DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def main():
    app = QApplication([])
    win = SimApp(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
    win.resize(1000, 720)
    win.select_scenario(3)          # cut_in — visually interesting
    for _ in range(80):
        win._advance(0.1)
    win.grab().save("sim_frame.png")
    print("wrote sim_frame.png", win.loop.stepper.st.t, "steps")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the render + inspect**

Run: `QT_QPA_PLATFORM=offscreen python scripts/render_simulator_frame.py`
Expected: prints `wrote sim_frame.png ... steps`. Then visually inspect `sim_frame.png` (top-down cars + net panel populated). Fix any rendering issue found.

- [ ] **Step 4: Full suite + commit**

Run: `python -m pytest tests/ -q -k "sim or champion_io"`
Expected: PASS (all sim + champion_io tests).

```bash
git add scripts/run_simulator.py scripts/render_simulator_frame.py
git commit -m "feat(sim/ui): entry point + offscreen render check"
```

---

## Self-Review

**Spec coverage (SIMULATOR_DESIGN.md §7 ui/ + §4/§5):**
- `loop.py` (QTimer + fixed-timestep accumulator) → Task 1 (logic) + Task 4 (QTimer wiring). ✓
- `topdown.py` (QGraphicsView, follow-ego) → Task 2. ✓
- `netpanel.py` (pyqtgraph raster/v_mem/params) → Task 3. ✓
- `app.py` (load checkpoint, scenario selector, run/pause, inject brake) → Task 4. ✓
- `scripts/run_simulator.py` entry → Task 5. ✓
- Decisions honoured: follow-ego (Task 2), 9+manual scenarios (Task 4 `include_tail=True` + `_manual`), sample_every=1/buffer=500 (Task 4), PySide6+pyqtgraph. ✓
- Deferred (post-v1, design §9): interpolation, QThread/FpgaBackend, EstimationQuality/UKF, lateral/MOBIL.

**Placeholder scan:** none (Qt tasks may need small API tweaks at execution; smoke tests + PNG are the guardrails). **Type consistency:** `SimLoop.tick`→StepResults consumed by `TopDownView.update_frame`; `AttributeProbe` consumed by `NetPanel.update_frame`; `SimApp.loop/_probe/_injector` names consistent across methods.

---

## Execution Handoff

Inline execution. Task 1 needs no PySide6; Tasks 2-5 require the install to have completed. Finish with the PNG visual check before the final commit.
