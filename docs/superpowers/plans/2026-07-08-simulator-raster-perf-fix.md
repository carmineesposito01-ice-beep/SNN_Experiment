# Simulator Raster Fix + Performance Pass (Extension Phase 3a.0)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`) syntax.
> Runs in the **`cf_sim`** conda env (offscreen for Qt). All changes in `sim/ui/*`; golden core untouched. API pre-verified against pyqtgraph 0.14.0.

**Goal:** Fix the transposed spike raster (neurons and time axes were swapped → the "neuron" axis grew with time) and cut the progressive lag/freeze under a live run.

**Diagnosis (verified):** pyqtgraph default `imageAxisOrder='col-major'`; `RasterPanel` called `setImage(sm.T)` with `sm=(frames,H)` → X-axis showed the 32 neurons, Y-axis showed time (frames, growing). Labels (`bottom="time"`, `left="neuron"`) were the reverse of the data. `setImage(sm)` gives `boundingRect w=frames (X=time), h=H (Y=neuron)` — the correct, bounded orientation. Perf: no downsampling/clip on the line plots + antialiased redraw of up to 500 points × 7 panels per frame + an unclamped `frame_dt` in `_on_timer` (`clock.restart()/1000`) that lets a slow frame cascade into a bigger step-batch (spiral of death, bounded only by `done` at t≥N=600).

**Architecture:** One-line orientation fix in `RasterPanel`; add `setDownsampling(auto=True, mode='peak')` + `setClipToView(True)` to the line-plot panels; clamp `frame_dt` to `_MAX_FRAME_DT=0.1` s in the app loop (refactored into a testable `_clamp_frame_dt`).

**Tech Stack:** PySide6 6.11, pyqtgraph 0.14 (`ImageItem`, `PlotItem.setDownsampling`/`setClipToView`), pytest — all in `cf_sim`.

---

## File Structure

| File | Change |
|---|---|
| `sim/ui/panels.py` | **Modify** — `RasterPanel.update_frame`: `setImage(sm)` (drop `.T`); `VmemPanel`/`ParamPanel.__init__`: downsampling + clipToView |
| `sim/ui/app.py` | **Modify** — add `_MAX_FRAME_DT`, `_clamp_frame_dt`; `_on_timer` uses it |
| `tests/test_sim_panels.py` | **Append** — raster orientation test; clipToView test |
| `tests/test_sim_ui_smoke.py` | **Append** — `_clamp_frame_dt` test |

---

### Task 1: Raster orientation fix

**Files:** Modify `sim/ui/panels.py`; append to `tests/test_sim_panels.py`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_sim_panels.py`):

```python
def test_raster_orientation_time_x_neuron_y(qapp):
    # F frames of H neurons -> image must be X=time(F wide), Y=neuron(H tall), NOT transposed
    F, H = 9, 4
    p = AttributeProbe(capacity=50)
    for t in range(F):
        p.record(t, {"spikes": (np.arange(H) % 2).astype(float), "v_mem": np.zeros(H),
                     "v_th_eff": np.ones(H)}, np.zeros(5))
    panel = RasterPanel()
    panel.update_frame(p)
    br = panel._img.boundingRect()
    assert round(br.width()) == F and round(br.height()) == H   # time on X, neuron on Y
```

- [ ] **Step 2: Run — verify FAIL**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py::test_raster_orientation_time_x_neuron_y -q`
Expected: FAIL — current `setImage(sm.T)` gives `width=H=4, height=F=9` (transposed), so `round(width)==9` is False.

- [ ] **Step 3: Fix `RasterPanel.update_frame` in `sim/ui/panels.py`**

Replace `self._img.setImage(sm.T, ...)` with `self._img.setImage(sm, ...)`:

```python
    def update_frame(self, probe):
        sm = probe.spikes_matrix()          # (frames, H)
        if sm.size:
            self._img.setImage(sm, autoLevels=False, levels=(0.0, 1.0))   # X=time, Y=neuron
```

- [ ] **Step 4: Run — verify PASS**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -q`
Expected: PASS (5 tests). The label assignments in `__init__` (`bottom="time"`, `left="neuron"`) are now correct without change.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/panels.py tests/test_sim_panels.py
git commit -m "fix(sim/ui): raster was transposed (neuron/time axes swapped); setImage(sm) not sm.T"
```

---

### Task 2: Performance pass — downsampling/clip + frame_dt clamp

**Files:** Modify `sim/ui/panels.py`, `sim/ui/app.py`; append to `tests/test_sim_panels.py`, `tests/test_sim_ui_smoke.py`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sim_panels.py`:

```python
def test_line_panels_have_clip_to_view(qapp):
    # downsampling + clip keep the live plots cheap; clipToViewMode() reports the clip state
    assert VmemPanel()._plot.getPlotItem().clipToViewMode() is True
    assert ParamPanel(0, "v0", "m/s", "#d1495b")._plot.getPlotItem().clipToViewMode() is True
```

Append to `tests/test_sim_ui_smoke.py`:

```python
def test_simapp_clamps_frame_dt(qapp):
    win = SimApp(CHAMP)
    assert win._clamp_frame_dt(5.0) == 0.1     # a lagged frame can't cascade into a huge step-batch
    assert win._clamp_frame_dt(0.02) == 0.02   # normal frames pass through
```

- [ ] **Step 2: Run — verify FAIL**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py::test_line_panels_have_clip_to_view tests/test_sim_ui_smoke.py::test_simapp_clamps_frame_dt -q`
Expected: FAIL — `clipToViewMode` is `False` by default; `SimApp` has no `_clamp_frame_dt`.

- [ ] **Step 3a: Add downsampling + clip in `sim/ui/panels.py`**

In `VmemPanel.__init__`, right after `self._plot = pg.PlotWidget(...)` and its label calls (before creating curves), add:

```python
        self._plot.setDownsampling(auto=True, mode="peak")
        self._plot.setClipToView(True)
```

In `ParamPanel.__init__`, right after `self._plot = pg.PlotWidget(title=f"{name} ({unit})")` (before `showGrid`), add the same two lines:

```python
        self._plot.setDownsampling(auto=True, mode="peak")
        self._plot.setClipToView(True)
```

- [ ] **Step 3b: Add the frame_dt clamp in `sim/ui/app.py`**

Add a module constant near `_UI_FPS_MS`:

```python
_MAX_FRAME_DT = 0.1
```

Add the method (next to `_on_timer`) and use it in `_on_timer`:

```python
    def _clamp_frame_dt(self, elapsed: float) -> float:
        return min(float(elapsed), _MAX_FRAME_DT)   # avoid the spiral of death under load

    def _on_timer(self):
        self._advance(self._clamp_frame_dt(self._clock.restart() / 1000.0))
        if self.loop.done:
            self._run_btn.setChecked(False)
```

- [ ] **Step 4: Run — verify PASS**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py tests/test_sim_ui_smoke.py -q`
Expected: PASS (all).

- [ ] **Step 5: Full golden suite + render + commit + push**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_state.py tests/test_sim_backend.py tests/test_sim_stepper.py tests/test_sim_scenario.py tests/test_sim_events.py tests/test_sim_probe.py tests/test_sim_replay.py tests/test_sim_loop.py tests/test_sim_panels.py tests/test_sim_layout.py tests/test_sim_ui_smoke.py tests/test_sim_eventprop.py tests/test_champion_io.py -q`
Expected: PASS (all).

Render (real platform) and confirm the raster now reads time→right, neurons↕ (0..32, bounded):
```bash
QT_QPA_PLATFORM=windows conda run -n cf_sim python scripts/run_simulator.py
```

```bash
git add sim/ui/panels.py sim/ui/app.py tests/test_sim_panels.py tests/test_sim_ui_smoke.py
git commit -m "perf(sim/ui): downsampling+clipToView on live plots; clamp frame_dt vs spiral of death"
git push
```

---

## Self-Review

**Coverage:** raster transpose → Task 1 (`setImage(sm)` + orientation test) ✓; lag/freeze → Task 2 (downsampling+clip on line plots; frame_dt clamp against the loop spiral) ✓.

**Placeholder scan:** none — all code complete; commands runnable.

**Consistency:** `_clamp_frame_dt`/`_MAX_FRAME_DT` defined and used in `_on_timer`; `clipToViewMode` is the pyqtgraph `PlotItem` flag set by `setClipToView(True)`. `RasterPanel` labels already read `bottom="time"`, `left="neuron"` — correct once the data is untransposed.

**Scope:** Only the confirmed raster bug + the highest-value perf levers. Antialias-off and rolling-X-window are deliberately deferred — revisit only if lag persists after this pass (then profile, per the "measure not guess" fallback).

---

## Execution Handoff

Inline execution (established for this track), in `cf_sim`, TDD per task, render-inspect at Task 2 Step 5. Then resume the Phase 3a (metric panels) design.
