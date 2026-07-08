# Simulator Dockable Shell Implementation Plan (Extension Phase 2)

> **STATUS: ✅ COMPLETE (2026-07-08).** Executed inline in `cf_sim` (TDD). T1 `panels.py`, T2 `layout.py`, T3 `app.py`+remove netpanel — commits up to `24468ae` (pushed). 57 tests green; core golden untouched; both Overview + Identificazione presets render-verified on the real `windows` platform.

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`) syntax.
> Runs entirely in the **`cf_sim`** conda env: `conda run -n cf_sim python -m pytest ...` (offscreen for Qt). All changes are in `sim/ui/*` + `scripts/run_simulator.py`; the golden-tested headless core is untouched.
> Spec: `docs/superpowers/specs/2026-07-08-simulator-dockable-shell-design.md`. API pre-verified against pyqtgraph 0.14.0.

**Goal:** Turn the fixed UI into a **dockable workspace** — 8 independent docks (Road, Raster, v_mem, v0, T, s0, a, b) the user can drag / resize / tear out (pop-out) / tab-stack, with a View menu (show/hide), 4 layout presets, and guarded layout persistence.

**Architecture:** `SimApp` central widget = header + controls + a pyqtgraph `DockArea`. `NetPanel` is dissolved into focused per-graph widgets (`RasterPanel`, `VmemPanel`, `ParamPanel`) in a new `sim/ui/panels.py`. Presets + persistence live in a new `sim/ui/layout.py` (`visible_docks` derives ground-truth visibility from `saveState`; guarded `load_layout` falls back to Overview). The 5 param plots stay X-linked across docks. Firing-% moves to the status bar.

**Tech Stack:** PySide6 6.11, pyqtgraph 0.14 (`DockArea`, `Dock`, `moveDock`, `saveState`/`restoreState`), NumPy, pytest — all in `cf_sim`.

**Verified API facts (pyqtgraph 0.14.0):** `Dock(name, closable=True)`; `area.addDock(dock, position, relativeTo)` (re-adds a closed dock; on an open dock it just moves it); `area.moveDock(dock, position, neighbor)` (position incl. `'above'` for tabs); `dock.close()` hides + emits `dock.sigClosed`; `dock.addWidget(w)`; `area.saveState()` → `{'main','float'}` dict; `area.restoreState(state)` raises `KeyError` on malformed input; `QWidget.isVisible()` is unreliable headless → derive visibility from `saveState`.

---

## File Structure

| File | Change |
|---|---|
| `sim/ui/panels.py` | **Create** — `RasterPanel`, `VmemPanel`, `ParamPanel` (dissolved NetPanel) |
| `sim/ui/layout.py` | **Create** — `visible_docks`, 4 presets, `save_layout`/`load_layout` (guarded) |
| `sim/ui/app.py` | **Rewrite** — `DockArea` shell, 8 docks, X-link, View/Layout menus, firing-in-statusbar, startup load |
| `sim/ui/netpanel.py` | **Remove** — superseded by `panels.py` |
| `scripts/run_simulator.py` | **Modify** — pass `layout_path=LAYOUT_PATH` |
| `tests/test_sim_panels.py` | **Create** — panel unit tests (migrated from NetPanel tests) |
| `tests/test_sim_layout.py` | **Create** — presets, persistence round-trip, corrupt/missing fallback |
| `tests/test_sim_ui_smoke.py` | **Modify** — drop NetPanel tests; add dock/X-link/View/preset/firing tests |

---

### Task 1: `panels.py` — dissolve NetPanel into RasterPanel / VmemPanel / ParamPanel

**Files:** Create `sim/ui/panels.py`, `tests/test_sim_panels.py`.

- [ ] **Step 1: Write failing tests** — create `tests/test_sim_panels.py`:

```python
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6.QtWidgets import QApplication          # noqa: E402
from sim.probe import AttributeProbe                # noqa: E402
from sim.ui.panels import ParamPanel, RasterPanel, VmemPanel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _probe(params, spikes=None):
    p = AttributeProbe(capacity=50)
    spk = spikes if spikes is not None else np.zeros(8)
    for t in range(4):
        p.record(t, {"spikes": spk, "v_mem": np.linspace(0, 1, 8), "v_th_eff": np.ones(8)},
                 np.asarray(params, dtype=float))
    return p


def test_raster_panel_updates(qapp):
    RasterPanel().update_frame(_probe([0, 0, 0, 0, 0], spikes=(np.arange(8) % 2).astype(float)))


def test_vmem_panel_updates(qapp):
    VmemPanel().update_frame(_probe([0, 0, 0, 0, 0]))


def test_param_panel_physical_value_and_title(qapp):
    p = ParamPanel(0, "v0", "m/s", "#d1495b")
    p.update_frame(_probe([44.0, 1.1, 2.5, 0.5, 1.0]))
    assert abs(p.current_value() - 44.0) < 1e-6
    y = p._curve.getData()[1]
    assert y is not None and float(np.nanmax(y)) > 40.0
    assert "v0 = 44.00 m/s" in p.plot_item.titleLabel.text


def test_param_panel_ground_truth(qapp):
    p = ParamPanel(1, "T", "s", "#2a7fb8")
    p.set_ground_truth(1.5)
    assert p._gt.isVisible() and abs(p._gt.value() - 1.5) < 1e-6
    p.set_ground_truth(None)
    assert not p._gt.isVisible()
```

- [ ] **Step 2: Run — verify FAIL**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.ui.panels'`.

- [ ] **Step 3: Create `sim/ui/panels.py`**

```python
"""Individual live network graphs as standalone dockable widgets: RasterPanel (spike raster),
VmemPanel (v_mem sample traces + effective threshold), ParamPanel (one identified param in physical
units with an optional dashed ground-truth reference line and the live value in the title)."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

PARAM_NAMES = ["v0", "T", "s0", "a", "b"]
PARAM_UNITS = ["m/s", "s", "m", "m/s^2", "m/s^2"]
PARAM_COLORS = ["#d1495b", "#2a7fb8", "#7b3fa0", "#e8871e", "#2e8b57"]
_N_SAMPLE = 4


class RasterPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="spike raster")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", "neuron")
        self._img = pg.ImageItem()
        self._plot.addItem(self._img)
        layout.addWidget(self._plot)

    def update_frame(self, probe):
        sm = probe.spikes_matrix()
        if sm.size:
            self._img.setImage(sm.T, autoLevels=False, levels=(0.0, 1.0))


class VmemPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="v_mem (sample neurons) + effective threshold (dashed)")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", "v_mem")
        self._vmem_curves = [self._plot.plot(pen=pg.mkPen("#8fd6ff", width=1)) for _ in range(_N_SAMPLE)]
        self._vth_curves = [self._plot.plot(pen=pg.mkPen("#e8871e", width=1, style=Qt.DashLine))
                            for _ in range(_N_SAMPLE)]
        layout.addWidget(self._plot)

    def update_frame(self, probe):
        frames = probe.frames()
        if not frames:
            return
        vm = np.stack([f.v_mem for f in frames])
        vth = np.stack([f.v_th_eff for f in frames])
        for i in range(min(_N_SAMPLE, vm.shape[1])):
            self._vmem_curves[i].setData(vm[:, i])
            self._vth_curves[i].setData(vth[:, i])


class ParamPanel(QWidget):
    def __init__(self, index, name, unit, color):
        super().__init__()
        self._index = index
        self._name = name
        self._unit = unit
        self._last = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title=f"{name} ({unit})")
        self._plot.showGrid(x=False, y=True, alpha=0.2)
        self._curve = self._plot.plot(pen=pg.mkPen(color, width=2))
        self._gt = pg.InfiniteLine(angle=0, movable=False,
                                   pen=pg.mkPen("#9a9a9a", width=1, style=Qt.DashLine))
        self._gt.setVisible(False)
        self._plot.addItem(self._gt)
        layout.addWidget(self._plot)

    @property
    def plot_item(self):
        return self._plot.getPlotItem()

    def current_value(self):
        return self._last

    def set_ground_truth(self, value):
        if value is None:
            self._gt.setVisible(False)
        else:
            self._gt.setPos(float(value))
            self._gt.setVisible(True)

    def update_frame(self, probe):
        pm = probe.params_matrix()
        if pm.size:
            self._last = float(pm[-1, self._index])
            self._curve.setData(pm[:, self._index])
            self._plot.setTitle(f"{self._name} = {self._last:.2f} {self._unit}")
```

- [ ] **Step 4: Run — verify PASS**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add sim/ui/panels.py tests/test_sim_panels.py
git commit -m "feat(sim/ui): panels.py — dissolve NetPanel into Raster/Vmem/Param dock widgets"
```

---

### Task 2: `layout.py` — presets + guarded persistence

**Files:** Create `sim/ui/layout.py`, `tests/test_sim_layout.py`.

- [ ] **Step 1: Write failing tests** — create `tests/test_sim_layout.py`:

```python
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6.QtWidgets import QApplication, QLabel   # noqa: E402
from pyqtgraph.dockarea import Dock, DockArea        # noqa: E402
from sim.ui.layout import (DOCK_ORDER, apply_identificazione, apply_neuro_debug,  # noqa: E402
                           apply_overview, load_layout, save_layout, visible_docks)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _build_area():
    area = DockArea()
    docks = {}
    for name in DOCK_ORDER:
        d = Dock(name, closable=True)
        d.addWidget(QLabel(name))
        docks[name] = d
    apply_overview(area, docks)
    return area, docks


def test_overview_all_visible(qapp):
    area, docks = _build_area()
    assert visible_docks(area) == set(DOCK_ORDER)


def test_identificazione_hides_vmem(qapp):
    area, docks = _build_area()
    apply_identificazione(area, docks)
    vis = visible_docks(area)
    assert "v_mem" not in vis
    assert {"v0", "T", "s0", "a", "b"} <= vis


def test_neuro_debug_shows_raster_and_vmem(qapp):
    area, docks = _build_area()
    apply_neuro_debug(area, docks)
    assert {"Raster", "v_mem"} <= visible_docks(area)


def test_preset_then_overview_restores_all(qapp):
    area, docks = _build_area()
    apply_identificazione(area, docks)   # hides v_mem
    apply_overview(area, docks)
    assert visible_docks(area) == set(DOCK_ORDER)


def test_layout_roundtrip(qapp, tmp_path):
    area, docks = _build_area()
    p = str(tmp_path / "layout.json")
    save_layout(area, p)
    assert os.path.exists(p)
    assert load_layout(area, docks, p) is True


def test_layout_corrupt_falls_back_to_overview(qapp, tmp_path):
    area, docks = _build_area()
    p = str(tmp_path / "bad.json")
    with open(p, "w") as f:
        f.write("{ not valid json")
    assert load_layout(area, docks, p) is False
    assert visible_docks(area) == set(DOCK_ORDER)


def test_layout_missing_file_falls_back(qapp, tmp_path):
    area, docks = _build_area()
    assert load_layout(area, docks, str(tmp_path / "nope.json")) is False
    assert visible_docks(area) == set(DOCK_ORDER)
```

- [ ] **Step 2: Run — verify FAIL**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_layout.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.ui.layout'`.

- [ ] **Step 3: Create `sim/ui/layout.py`**

```python
"""Dock presets + guarded layout persistence for the simulator's DockArea shell.

visible_docks() derives the ground-truth set of placed docks from saveState() (QWidget.isVisible()
is unreliable headless). Presets arrange programmatically (moveDock/close) so they never depend on the
fragile saveState format; only the user's custom layout uses saveState/restoreState, guarded."""
import json
import os

DOCK_ORDER = ["Road", "Raster", "v_mem", "v0", "T", "s0", "a", "b"]
_PARAMS = ["v0", "T", "s0", "a", "b"]
LAYOUT_PATH = os.path.expanduser(os.path.join("~", ".cf_fsnn_sim", "layout.json"))


def visible_docks(area):
    """Set of dock names currently placed in the area (main + floating), from saveState()."""
    names = set()

    def walk(node):
        if not node:
            return
        kind = node[0]
        if kind == "dock":
            names.add(node[1])
        elif kind in ("horizontal", "vertical", "tab"):
            for child in node[1]:
                walk(child)

    state = area.saveState()
    walk(state.get("main"))
    for fl in state.get("float", []):
        if isinstance(fl, (list, tuple)) and fl and isinstance(fl[0], dict):
            walk(fl[0].get("main"))
    return names


def _show(area, docks, name, position, neighbor=None):
    ref = docks[neighbor] if neighbor else None
    area.addDock(docks[name], position, ref)   # re-adds if closed; moves if already placed


def _hide(docks, name):
    docks[name].close()   # idempotent; safe even if already closed


def apply_overview(area, docks):
    _show(area, docks, "Road", "top")
    _show(area, docks, "Raster", "bottom", "Road")
    _show(area, docks, "v_mem", "right", "Raster")
    _show(area, docks, "v0", "bottom", "Raster")
    for prev, n in zip(["v0", "T", "s0", "a"], ["T", "s0", "a", "b"]):
        _show(area, docks, n, "right", prev)


def apply_guida(area, docks):
    _show(area, docks, "Road", "left")
    _show(area, docks, "Raster", "right", "Road")
    _show(area, docks, "v_mem", "bottom", "Raster")
    _show(area, docks, "v0", "bottom", "v_mem")
    for n in ["T", "s0", "a", "b"]:
        _show(area, docks, n, "above", "v0")   # tab-stack params together


def apply_identificazione(area, docks):
    _hide(docks, "v_mem")
    _show(area, docks, "Road", "top")
    _show(area, docks, "Raster", "right", "Road")
    _show(area, docks, "v0", "bottom", "Road")
    for prev, n in zip(["v0", "T", "s0", "a"], ["T", "s0", "a", "b"]):
        _show(area, docks, n, "bottom", prev)   # 5 params stacked, dominant


def apply_neuro_debug(area, docks):
    _show(area, docks, "Raster", "top")
    _show(area, docks, "v_mem", "bottom", "Raster")
    _show(area, docks, "Road", "bottom", "v_mem")
    _show(area, docks, "v0", "right", "Raster")
    for n in ["T", "s0", "a", "b"]:
        _show(area, docks, n, "above", "v0")   # params tab-stacked, compact


PRESETS = {"Overview": apply_overview, "Guida": apply_guida,
           "Identificazione": apply_identificazione, "Neuro-debug": apply_neuro_debug}


def save_layout(area, path=LAYOUT_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(area.saveState(), f)


def load_layout(area, docks, path=LAYOUT_PATH):
    """Restore a saved layout, guarded. Returns True on success, False if it fell back to Overview
    (missing file OR any restore error — the pyqtgraph 0.14 restoreState bug safety net)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        area.restoreState(state)
        return True
    except Exception:
        apply_overview(area, docks)
        return False
```

- [ ] **Step 4: Run — verify PASS**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_layout.py -q`
Expected: PASS (7 tests). If `test_neuro_debug`/`test_identificazione` arrangement raises on a tab `'above'` for a not-yet-placed dock, ensure the tab target (`v0`) is `_show`n before the `'above'` calls — it is, in the code above.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/layout.py tests/test_sim_layout.py
git commit -m "feat(sim/ui): layout.py — 4 dock presets + guarded layout persistence"
```

---

### Task 3: `app.py` — DockArea shell, menus, X-link, firing-in-statusbar; remove netpanel

**Files:** Rewrite `sim/ui/app.py`; modify `scripts/run_simulator.py`; delete `sim/ui/netpanel.py`; modify `tests/test_sim_ui_smoke.py`.

- [ ] **Step 1: Rewrite the NetPanel-coupled smoke tests** — in `tests/test_sim_ui_smoke.py`:
  1. **Delete** the imports `from sim.ui.netpanel import NetPanel` and every `test_netpanel_*` test (migrated to `test_sim_panels.py`).
  2. **Delete** `test_simapp_netpanel_gets_more_vertical_space` (no stretch ratio under DockArea) and the old `test_simapp_feeds_ground_truth_to_netpanel`.
  3. **Add** these tests (append):

```python
from sim.ui.layout import DOCK_ORDER, visible_docks   # noqa: E402


def test_simapp_builds_eight_docks(qapp):
    win = SimApp(CHAMP)
    assert set(win._docks.keys()) == set(DOCK_ORDER)
    assert visible_docks(win._area) == set(DOCK_ORDER)   # Overview on startup (no layout_path)


def test_simapp_params_xlinked(qapp):
    win = SimApp(CHAMP)
    win._params[0].plot_item.getViewBox().setXRange(5, 25, padding=0)
    r0 = win._params[0].plot_item.getViewBox().viewRange()[0]
    r3 = win._params[3].plot_item.getViewBox().viewRange()[0]
    assert abs(r3[0] - r0[0]) < 1e-6 and abs(r3[1] - r0[1]) < 1e-6


def test_simapp_feeds_ground_truth_to_params(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    gt = win._scenarios[0].params_gt
    assert win._params[0]._gt.isVisible()
    assert abs(win._params[0]._gt.value() - float(gt[0])) < 1e-6


def test_simapp_status_has_firing(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    assert "firing" in win.status_text()


def test_simapp_view_toggle_hides_and_shows_dock(qapp):
    win = SimApp(CHAMP)
    win._set_dock_visible("v_mem", False)
    assert "v_mem" not in visible_docks(win._area)
    win._set_dock_visible("v_mem", True)
    assert "v_mem" in visible_docks(win._area)


def test_simapp_apply_preset(qapp):
    win = SimApp(CHAMP)
    win.apply_preset("Identificazione")
    assert "v_mem" not in visible_docks(win._area)
    win.apply_preset("Overview")
    assert visible_docks(win._area) == set(DOCK_ORDER)
```

- [ ] **Step 2: Run — verify FAIL** (app has no `_docks`/`_area`/`_params`/`apply_preset`)

Run: `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py -q`
Expected: FAIL — `AttributeError`/`ImportError` around `_docks`, `visible_docks`, etc.

- [ ] **Step 3: Rewrite `sim/ui/app.py`** (full file):

```python
"""SimApp -- main window: a dockable workspace (pyqtgraph DockArea) of 8 graphs (Road, Raster, v_mem,
and the 5 identified params) + champion/scenario controls + View/Layout menus (presets + persistence),
driven by a fixed-timestep QTimer loop, with a status bar (incl. network firing %)."""
import os

import numpy as np
from PySide6.QtCore import QElapsedTimer, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QSlider, QVBoxLayout, QWidget)
from pyqtgraph.dockarea import Dock, DockArea

from config import DT
from sim.backend import SoftwareBackend
from sim.events import EventInjector
from sim.probe import AttributeProbe
from sim.scenario import manual_scenario, scenario_library
from sim.stepper import SimStepper
from sim.ui.layout import (DOCK_ORDER, LAYOUT_PATH, PRESETS, apply_overview, load_layout,
                           save_layout, visible_docks)
from sim.ui.loop import SimLoop
from sim.ui.panels import PARAM_COLORS, PARAM_NAMES, PARAM_UNITS, ParamPanel, RasterPanel, VmemPanel
from sim.ui.topdown import TopDownView
from utils.champion_io import load_champion

_UI_FPS_MS = 33
_PARAMS_GT = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


class SimApp(QMainWindow):
    def __init__(self, champion_path, layout_path=None):
        super().__init__()
        self.setWindowTitle("CF_FSNN Simulator")
        self._champ_name = os.path.basename(os.path.dirname(champion_path))
        self._champ = load_champion(champion_path)
        self._scenarios = scenario_library(_PARAMS_GT, N=600,
                                            rng=np.random.default_rng(0), include_tail=True)
        self._scenarios.append(self._manual(_PARAMS_GT))
        self._current_idx = 0
        self._speed = 1
        self._last_result = None

        self._topdown = TopDownView()
        self._raster = RasterPanel()
        self._vmem = VmemPanel()
        self._params = [ParamPanel(i, n, u, c)
                        for i, (n, u, c) in enumerate(zip(PARAM_NAMES, PARAM_UNITS, PARAM_COLORS))]
        for p in self._params[1:]:
            p.plot_item.setXLink(self._params[0].plot_item)
        self._live_panels = [self._raster, self._vmem, *self._params]

        widgets = {"Road": self._topdown, "Raster": self._raster, "v_mem": self._vmem,
                   "v0": self._params[0], "T": self._params[1], "s0": self._params[2],
                   "a": self._params[3], "b": self._params[4]}
        self._area = DockArea()
        self._docks = {}
        for name in DOCK_ORDER:
            d = Dock(name, closable=True)
            d.addWidget(widgets[name])
            d.sigClosed.connect(lambda *_, n=name: self._on_dock_closed(n))
            self._docks[name] = d
        apply_overview(self._area, self._docks)   # place all docks so restoreState can find them

        self._selector = QComboBox()
        self._selector.addItems([s.name for s in self._scenarios])
        self._run_btn = QPushButton("Run"); self._run_btn.setCheckable(True)
        self._run_btn.toggled.connect(self._on_run_toggled)
        self._step_btn = QPushButton("Step"); self._step_btn.clicked.connect(self.step_once)
        self._reset_btn = QPushButton("Reset"); self._reset_btn.clicked.connect(self.reset_run)
        self._brake_btn = QPushButton("Brake leader"); self._brake_btn.clicked.connect(self.inject_brake)
        self._speed_slider = QSlider(Qt.Horizontal); self._speed_slider.setRange(1, 8)
        self._speed_slider.setValue(1); self._speed_slider.setFixedWidth(90)
        self._speed_slider.valueChanged.connect(self._on_speed)
        controls = QHBoxLayout()
        for w in (self._selector, self._run_btn, self._step_btn, self._reset_btn,
                  self._brake_btn, QLabel("speed"), self._speed_slider):
            controls.addWidget(w)

        self._header = QLabel()
        root = QVBoxLayout()
        root.addWidget(self._header)
        root.addLayout(controls)
        root.addWidget(self._area, stretch=1)
        container = QWidget(); container.setLayout(root)
        self.setCentralWidget(container)
        self._status = self.statusBar()

        self._build_menus()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._clock = QElapsedTimer()

        self.select_scenario(0)
        self._selector.currentIndexChanged.connect(self.select_scenario)

        if layout_path:
            load_layout(self._area, self._docks, layout_path)
        self._sync_view_actions()

    # ---- menus / docks ----
    def _build_menus(self):
        view = self.menuBar().addMenu("View")
        self._view_actions = {}
        for name in DOCK_ORDER:
            a = QAction(name, self, checkable=True)
            a.setChecked(True)
            a.toggled.connect(lambda vis, n=name: self._set_dock_visible(n, vis))
            view.addAction(a)
            self._view_actions[name] = a
        layout_menu = self.menuBar().addMenu("Layout")
        for name in PRESETS:
            a = QAction(name, self)
            a.triggered.connect(lambda _=False, n=name: self.apply_preset(n))
            layout_menu.addAction(a)
        layout_menu.addSeparator()
        a_save = QAction("Save layout", self); a_save.triggered.connect(self._save_layout)
        a_reset = QAction("Reset to saved", self); a_reset.triggered.connect(self._load_saved)
        layout_menu.addAction(a_save); layout_menu.addAction(a_reset)

    def apply_preset(self, name):
        PRESETS[name](self._area, self._docks)
        self._sync_view_actions()

    def _set_dock_visible(self, name, visible):
        present = name in visible_docks(self._area)
        if visible and not present:
            self._area.addDock(self._docks[name], "right")
        elif not visible and present:
            self._docks[name].close()
        self._sync_view_actions()

    def _on_dock_closed(self, name):
        a = getattr(self, "_view_actions", {}).get(name)
        if a is not None:
            a.blockSignals(True); a.setChecked(False); a.blockSignals(False)

    def _sync_view_actions(self):
        vis = visible_docks(self._area)
        for name, a in getattr(self, "_view_actions", {}).items():
            a.blockSignals(True); a.setChecked(name in vis); a.blockSignals(False)

    def _save_layout(self):
        try:
            save_layout(self._area, LAYOUT_PATH)
            self._status.showMessage(f"layout saved to {LAYOUT_PATH}", 3000)
        except OSError as e:
            self._status.showMessage(f"save failed: {e}", 5000)

    def _load_saved(self):
        load_layout(self._area, self._docks, LAYOUT_PATH)
        self._sync_view_actions()

    # ---- scenario / loop (unchanged shape) ----
    @staticmethod
    def _manual(pg):
        v_set = 0.7 * float(pg[0])
        return manual_scenario(pg, np.full(600, v_set),
                               s_init=float(pg[2]) + v_set * float(pg[1]), v_init=v_set)

    def scenario_count(self) -> int:
        return len(self._scenarios)

    def select_scenario(self, idx: int):
        self._current_idx = int(idx)
        if self._selector.currentIndex() != self._current_idx:
            self._selector.blockSignals(True)
            self._selector.setCurrentIndex(self._current_idx)
            self._selector.blockSignals(False)
        sc = self._scenarios[self._current_idx]
        self._injector = EventInjector()
        self._probe = AttributeProbe(capacity=500, sample_every=1)
        backend = SoftwareBackend(self._champ.model)
        stepper = SimStepper.from_scenario(backend, sc, injector=self._injector)
        self.loop = SimLoop(stepper, self._probe, dt_fixed=DT)
        self._last_result = None
        self._header.setText(f"champion: {self._champ_name}    |    scenario: {sc.name}")
        for i, p in enumerate(self._params):
            p.set_ground_truth(float(sc.params_gt[i]))
        self._refresh_status()

    def reset_run(self):
        self.select_scenario(self._current_idx)

    def step_once(self):
        self._paint(self.loop.tick(DT))

    def inject_brake(self):
        st = self.loop.stepper.st
        base_vl = float(self.loop.stepper.v_leader[min(st.t, self.loop.stepper.N - 1)])
        self._injector.enqueue(st.t, "brake_leader", target_v=max(0.3 * base_vl, 2.0), duration=20)

    def _advance(self, frame_dt: float):
        results = self.loop.tick(frame_dt * self._speed)
        self._paint(results)
        return results

    def _paint(self, results):
        if results:
            self._last_result = results[-1]
            self._topdown.update_frame(results[-1])
            for p in self._live_panels:
                p.update_frame(self._probe)
        self._refresh_status()

    def status_text(self) -> str:
        st = self.loop.stepper.st
        r = self._last_result
        ego = r.v if r is not None else st.v
        leader = r.vl if r is not None else float(self.loop.stepper.v_leader[0])
        gap = r.s if r is not None else st.s
        state = "COLLIDED" if st.collided else "ok"
        sm = self._probe.spikes_matrix()
        firing = f"{float(sm[-1].mean()) * 100:.1f}%" if sm.size else "--"
        return (f"t={st.t} ({st.t * DT:.1f}s)   |   ego {ego:.1f} m/s   |   leader {leader:.1f} m/s"
                f"   |   gap {gap:.1f} m   |   firing {firing}   |   {state}")

    def _refresh_status(self):
        self._status.showMessage(self.status_text())

    def _on_speed(self, v: int):
        self._speed = int(v)

    def _on_run_toggled(self, running: bool):
        if running:
            self._clock.restart()
            self._timer.start(_UI_FPS_MS)
        else:
            self._timer.stop()

    def _on_timer(self):
        self._advance(self._clock.restart() / 1000.0)
        if self.loop.done:
            self._run_btn.setChecked(False)
```

- [ ] **Step 4: Delete `sim/ui/netpanel.py`**

```bash
git rm sim/ui/netpanel.py
```

- [ ] **Step 5: Update `scripts/run_simulator.py`** — pass the layout path so the saved layout auto-loads on startup. Change the `SimApp(...)` line and import:

```python
from sim.ui.app import SimApp                # noqa: E402
from sim.ui.layout import LAYOUT_PATH        # noqa: E402
from sim.ui.theme import apply_dark_theme    # noqa: E402
...
    win = SimApp(champ, layout_path=LAYOUT_PATH)
```

- [ ] **Step 6: Run — verify the UI smoke suite PASSES**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py tests/test_sim_panels.py tests/test_sim_layout.py -q`
Expected: PASS. If `test_simapp_params_xlinked` fails (range not propagated headless), replace its body with a link-identity check: `assert win._params[3].plot_item.getViewBox().linkedView(0) is win._params[0].plot_item.getViewBox()`.

- [ ] **Step 7: Render + inspect (real windows platform)**

Run the windowed render helper (from the scratchpad, `render_windowed.py`, which builds `SimApp` and grabs a PNG) OR:
```bash
QT_QPA_PLATFORM=windows conda run -n cf_sim python scripts/run_simulator.py
```
Inspect: 8 docks present (Overview), each draggable/resizable; menuBar has View + Layout; try a preset (Identificazione hides v_mem; params dominate) and pop a single param out into its own window; firing % in the status bar. No OMP Error #15 (libomp fix from 2026-07-08 still in place).

- [ ] **Step 8: Full golden suite + commit + push**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_state.py tests/test_sim_backend.py tests/test_sim_stepper.py tests/test_sim_scenario.py tests/test_sim_events.py tests/test_sim_probe.py tests/test_sim_replay.py tests/test_sim_loop.py tests/test_sim_panels.py tests/test_sim_layout.py tests/test_sim_ui_smoke.py tests/test_sim_eventprop.py tests/test_champion_io.py -q`
Expected: PASS (all) — golden core untouched.

```bash
git add sim/ui/app.py scripts/run_simulator.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim/ui): DockArea shell — 8 docks, View/Layout menus, X-link, firing in status bar"
git push
```

---

## Self-Review

**Spec coverage (spec §1 decisions):** D1 full shell+persistence+presets (Task 2+3) ✓ · D2 DockArea (Task 3) ✓ · D3 8 docks incl. per-param (Task 3) ✓ · D4 4 presets (Task 2) ✓ · D5 programmatic presets (Task 2, moveDock/close) ✓ · D6 saveState only for custom (Task 2) ✓ · D7 NetPanel dissolved + removed (Task 1 + Task 3 Step 4) ✓ · D8 firing→status bar (Task 3 status_text) ✓ · D9 mitigation: build-all-first (apply_overview before load), unique names, guarded load_layout + fallback, round-trip + corrupt tests (Task 2) ✓ · D10 startup load via layout_path (Task 3 + run_simulator) ✓. X-link (Task 3 setXLink + test) ✓.

**Placeholder scan:** No TBDs; all code is complete and runnable. Each `_show`/`_hide`/preset function is fully written; tests reference only symbols defined in the plan.

**Type/name consistency:** `visible_docks`, `apply_overview/guida/identificazione/neuro_debug`, `PRESETS`, `save_layout`, `load_layout`, `DOCK_ORDER`, `LAYOUT_PATH` defined in `layout.py` and imported consistently in `app.py`/tests. `ParamPanel(index,name,unit,color)`, `.plot_item`, `.current_value()`, `.set_ground_truth()`, `._gt`, `._curve` consistent between `panels.py` and both test files. `SimApp._docks/_area/_params/_set_dock_visible/apply_preset` consistent between `app.py` and smoke tests.

**Scope:** One cohesive subsystem (dockable shell). New live-metric panels, time-scrub, export are explicitly out (spec §7) — not in any task.

---

## Execution Handoff

Inline execution (established for this track), in `cf_sim`, TDD per task, with a real-`windows` render inspect at Task 3 Step 7 before the final commit+push.
