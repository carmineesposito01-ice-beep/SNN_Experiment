# Simulator Param-Legibility Implementation Plan (Extension Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`) syntax.
> Runs entirely in the **`cf_sim`** conda env: `conda run -n cf_sim python -m pytest ...` (offscreen for Qt). All changes are in `sim/ui/*`; the golden-tested headless core (`sim/state.py`, `sim/stepper.py`, `sim/backend.py`, `sim/events.py`, `sim/probe.py`, `sim/eventprop_stepper.py`) is untouched.

**Goal:** Make the 5 identified parameters legible — replace the single 0..1-normalized param plot (all 5 series cramped on one axis) with **5 linked per-parameter plots in real physical units**, each with its own scale, an optional ground-truth reference line, and a network firing-% readout.

**Architecture:** Rewrite `NetPanel` so the param section is a `pyqtgraph.GraphicsLayoutWidget` of 5 stacked, X-linked `PlotItem`s (one per param, raw `pm[:,i]`, y-label = name+units). Add `set_ground_truth(params_gt)` (a dashed horizontal reference line per param) and a firing-% label. `SimApp.select_scenario` feeds the current scenario's `params_gt`. The raster and v_mem plots are unchanged; `n_params_curves()` and `current_param_labels()` are preserved so existing tests keep passing.

**Tech Stack:** PySide6 6.11, pyqtgraph 0.14 (GraphicsLayoutWidget, InfiniteLine, setXLink), NumPy, pytest — all in `cf_sim`.

**This is Extension Phase 1** of the design study (`docs/superpowers/2026-07-07-simulator-extension-study.md` §0/§2/§6). Deliberately zero dock/library risk; the dockable shell is Phase 2.

---

## File Structure

| File | Change |
|---|---|
| `sim/ui/netpanel.py` | **Rewrite**: param section → 5 per-param physical-unit linked plots; add `set_ground_truth()` + firing-% label; keep `n_params_curves()`, `current_param_labels()`, raster, v_mem |
| `sim/ui/app.py` | **Modify** `select_scenario`: feed `sc.params_gt` to the net panel via `set_ground_truth` |
| `tests/test_sim_ui_smoke.py` | **Append** tests: physical-units param curves, GT reference line, firing readout, app feeds GT |

---

### Task 1: NetPanel — 5 per-param physical-unit plots + GT reference + firing readout

**Files:**
- Modify (rewrite): `sim/ui/netpanel.py`
- Test: append to `tests/test_sim_ui_smoke.py`

- [ ] **Step 1: Write the failing tests (append to tests/test_sim_ui_smoke.py)**

```python
# --- Extension Phase 1: param legibility ---
def test_netpanel_params_in_physical_units(qapp):
    probe = AttributeProbe(capacity=50)
    for t in range(4):
        probe.record(t, {"spikes": np.zeros(8), "v_mem": np.zeros(8), "v_th_eff": np.ones(8)},
                     np.array([44.0, 1.1, 2.5, 0.5, 1.0]))
    panel = NetPanel()
    panel.update_frame(probe)
    assert panel.n_params_curves() == 5                       # unchanged public API
    y_v0 = panel._param_curves[0].getData()[1]                # RAW value, not 0..1
    assert y_v0 is not None and float(np.nanmax(y_v0)) > 40.0  # v0 plotted in m/s
    assert panel.current_param_labels()[0] == "v0=44.00"


def test_netpanel_ground_truth_reference(qapp):
    panel = NetPanel()
    panel.set_ground_truth(np.array([30.0, 1.5, 2.0, 1.5, 1.5]))
    assert panel._gt_lines[0].isVisible()
    assert abs(panel._gt_lines[0].value() - 30.0) < 1e-6
    panel.set_ground_truth(None)
    assert not panel._gt_lines[0].isVisible()


def test_netpanel_firing_readout(qapp):
    probe = AttributeProbe(capacity=50)
    for t in range(3):
        probe.record(t, {"spikes": np.array([1., 0., 1., 0., 1., 0., 1., 0.]),
                         "v_mem": np.zeros(8), "v_th_eff": np.ones(8)}, np.zeros(5))
    panel = NetPanel()
    panel.update_frame(probe)
    assert "%" in panel._firing_label.text() and "50" in panel._firing_label.text()
```

- [ ] **Step 2: Run — verify they FAIL**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py -q` (offscreen)
Expected: FAIL — `AttributeError: 'NetPanel' object has no attribute '_param_curves'`/`set_ground_truth`/`_firing_label` (current NetPanel has none).

- [ ] **Step 3: Rewrite `sim/ui/netpanel.py`**

```python
"""Live network panel: firing-% readout + spike raster + v_mem (with effective threshold)
+ the 5 identified params, each on its OWN plot in physical units (linked X axis), with an
optional dashed ground-truth reference line."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_PARAM_NAMES = ["v0", "T", "s0", "a", "b"]
_PARAM_UNITS = ["m/s", "s", "m", "m/s^2", "m/s^2"]
_PARAM_COLORS = ["#d1495b", "#2a7fb8", "#7b3fa0", "#e8871e", "#2e8b57"]
_N_SAMPLE = 4


class NetPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self._firing_label = QLabel("network firing: --")
        self._firing_label.setStyleSheet("color:#e0e0e0; padding:2px 4px;")
        layout.addWidget(self._firing_label)

        self._raster_plot = pg.PlotWidget(title="spike raster")
        self._raster_plot.setLabel("bottom", "time", units="steps")
        self._raster_plot.setLabel("left", "neuron")
        self._raster_img = pg.ImageItem()
        self._raster_plot.addItem(self._raster_img)
        layout.addWidget(self._raster_plot, stretch=2)

        self._vmem_plot = pg.PlotWidget(title="v_mem (sample neurons) + effective threshold (dashed)")
        self._vmem_plot.setLabel("bottom", "time", units="steps")
        self._vmem_plot.setLabel("left", "v_mem")
        self._vmem_curves = [self._vmem_plot.plot(pen=pg.mkPen("#8fd6ff", width=1))
                             for _ in range(_N_SAMPLE)]
        self._vth_curves = [self._vmem_plot.plot(pen=pg.mkPen("#e8871e", width=1, style=Qt.DashLine))
                            for _ in range(_N_SAMPLE)]
        layout.addWidget(self._vmem_plot, stretch=2)

        # 5 per-param plots, physical units, X-linked
        self._param_glw = pg.GraphicsLayoutWidget()
        self._param_plots, self._param_curves, self._gt_lines = [], [], []
        for i, (name, unit, color) in enumerate(zip(_PARAM_NAMES, _PARAM_UNITS, _PARAM_COLORS)):
            p = self._param_glw.addPlot(row=i, col=0)
            p.setLabel("left", name, units=unit)
            p.showGrid(x=False, y=True, alpha=0.2)
            if i < len(_PARAM_NAMES) - 1:
                p.getAxis("bottom").setStyle(showValues=False)
            else:
                p.setLabel("bottom", "time", units="steps")
            if self._param_plots:
                p.setXLink(self._param_plots[0])
            curve = p.plot(pen=pg.mkPen(color, width=2))
            gt = pg.InfiniteLine(angle=0, movable=False,
                                 pen=pg.mkPen("#9a9a9a", width=1, style=Qt.DashLine))
            gt.setVisible(False)
            p.addItem(gt)
            self._param_plots.append(p)
            self._param_curves.append(curve)
            self._gt_lines.append(gt)
        layout.addWidget(self._param_glw, stretch=5)

        self._last_params = None
        self._gt = None

    def n_params_curves(self) -> int:
        return len(self._param_curves)

    def current_param_labels(self):
        if self._last_params is None:
            return []
        return [f"{n}={v:.2f}" for n, v in zip(_PARAM_NAMES, self._last_params)]

    def set_ground_truth(self, params_gt):
        """Draw a dashed reference line per param at params_gt[i] (context only). None hides them."""
        self._gt = np.asarray(params_gt, dtype=float) if params_gt is not None else None
        for i, line in enumerate(self._gt_lines):
            if self._gt is not None:
                line.setPos(float(self._gt[i]))
                line.setVisible(True)
            else:
                line.setVisible(False)

    def update_frame(self, probe):
        frames = probe.frames()
        sm = probe.spikes_matrix()          # (frames, H)
        if sm.size:
            self._raster_img.setImage(sm.T, autoLevels=False, levels=(0.0, 1.0))
            vm = np.stack([f.v_mem for f in frames])
            vth = np.stack([f.v_th_eff for f in frames])
            for i in range(min(_N_SAMPLE, vm.shape[1])):
                self._vmem_curves[i].setData(vm[:, i])
                self._vth_curves[i].setData(vth[:, i])
            self._firing_label.setText(
                f"network firing: {float(sm[-1].mean()) * 100:.1f}%   (mean {float(sm.mean()) * 100:.1f}%)")
        pm = probe.params_matrix()          # (frames, 5)
        if pm.size:
            self._last_params = pm[-1]
            for i, curve in enumerate(self._param_curves):
                curve.setData(pm[:, i])     # RAW physical value (no normalization)
                self._param_plots[i].setTitle(f"{_PARAM_NAMES[i]} = {pm[-1, i]:.2f} {_PARAM_UNITS[i]}")
```

- [ ] **Step 4: Run — verify all NetPanel tests PASS** (incl. the pre-existing `test_netpanel_has_current_values`, which still holds because `n_params_curves()`/`current_param_labels()` are preserved)

Run: `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py -q`
Expected: PASS.

- [ ] **Step 5: Render + inspect + commit**

Run: `QT_QPA_PLATFORM=windows conda run -n cf_sim python scripts/render_simulator_frame.py` → inspect `sim_frame.png` (5 separate param plots with real units + values, firing % label). If cramped/wrong, tune `stretch=` / titles, then:

```bash
git add sim/ui/netpanel.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim/ui): per-param plots in physical units + firing-% readout (extension phase 1)"
```

---

### Task 2: Feed the scenario ground-truth into the net panel

**Files:**
- Modify: `sim/ui/app.py` (`select_scenario`)
- Test: append to `tests/test_sim_ui_smoke.py`

- [ ] **Step 1: Write the failing test (append)**

```python
def test_simapp_feeds_ground_truth_to_netpanel(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    gt = win._scenarios[0].params_gt
    assert win._netpanel._gt_lines[0].isVisible()
    assert abs(win._netpanel._gt_lines[0].value() - float(gt[0])) < 1e-6
```

- [ ] **Step 2: Run — verify it FAILS**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py::test_simapp_feeds_ground_truth_to_netpanel -q`
Expected: FAIL — GT line not visible (app never calls `set_ground_truth`).

- [ ] **Step 3: Modify `select_scenario` in `sim/ui/app.py`**

Add, at the end of `select_scenario` (after `self._header.setText(...)`, before `self._refresh_status()`):

```python
        self._netpanel.set_ground_truth(sc.params_gt)
```

- [ ] **Step 4: Run — verify PASS**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py -q`
Expected: PASS (all UI smoke tests).

- [ ] **Step 5: Full suite + commit + push**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_state.py tests/test_sim_backend.py tests/test_sim_stepper.py tests/test_sim_scenario.py tests/test_sim_events.py tests/test_sim_probe.py tests/test_sim_replay.py tests/test_sim_loop.py tests/test_sim_ui_smoke.py tests/test_sim_eventprop.py tests/test_champion_io.py -q`
Expected: PASS (all).

```bash
git add sim/ui/app.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim/ui): feed scenario ground-truth reference to net panel"
git push
```

---

## Self-Review

**Spec coverage (study §0/§2/§6 Phase 1):**
- "5 linked per-param plots in physical units, own scale" → Task 1 (`GraphicsLayoutWidget`, 5 `PlotItem`s, `setXLink`, raw `pm[:,i]`, `setLabel(units=…)`). ✓
- "optional GT reference (simple, not editorialised)" → Task 1 `set_ground_truth` (dashed line, hideable) + Task 2 wiring. ✓ (No badges / no "refuse to show error" — matches user decision 3.)
- "firing-% readout" → Task 1 `_firing_label`. ✓
- "drop-in NetPanel, zero dock/library risk, core untouched" → only `sim/ui/netpanel.py` + `sim/ui/app.py` change; no `DockArea`, no `restoreState`; headless-core tests re-run in Task 2 Step 5. ✓
- Backward compat: `n_params_curves()`/`current_param_labels()` preserved → pre-existing `test_netpanel_has_current_values` unaffected. ✓
- Out of scope (later phases, per study): docking, scrub/time-cursor, safety/energy metric docks beyond the firing readout, float-vs-fixed, export.

**Placeholder scan:** none — every step has runnable code/commands.

**Type consistency:** `set_ground_truth(params_gt)` (Task 1) called with `sc.params_gt` (Task 2); `_param_curves`, `_gt_lines`, `_firing_label` used consistently across tests and impl; `Scenario.params_gt` exists (`sim/scenario.py`).

---

## Execution Handoff

Inline execution (established for this track), in `cf_sim`, with a render-inspect at Task 1 Step 5 before committing.
