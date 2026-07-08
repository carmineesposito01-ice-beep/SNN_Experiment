# Network State Map + Spike-Rate Implementation Plan

> **STATUS: ✅ COMPLETE (2026-07-08).** Executed inline in `cf_sim` (TDD). T1 input capture, T2 panels, T3 wiring — commits up to `a86f867` (pushed). 63 tests green; golden bit-identity preserved. Post-render fix: SpikeRate un-X-linked from params (a hidden param tab corrupted its axis). NetState (3 groups + spike overlay) + SpikeRate render-verified on the real `windows` platform.

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`) syntax.
> Runs in **`cf_sim`** (offscreen for Qt). Spec: `docs/superpowers/specs/2026-07-08-network-state-map-design.md`. pyqtgraph 0.14 heatmap API pre-verified (`colormap.get('viridis')` → LUT (256,3); `ImageItem.setColorMap`/RGBA `setImage((h,w,4))`; `ViewBox.setBorder`; `hideAxis`).

**Goal:** Replace the time-raster with an instantaneous **NetState** map (input/hidden/output groups, coloured borders, v_mem heat + white spike overlay on hidden) and add a **SpikeRate** trend dock.

**Architecture:** additive input capture (backend/eventprop store last `x_norm`; `read_probe`→`"input"`; `ProbeFrame.input` optional) → new `NeuronStatePanel` + `SpikeRatePanel` in `panels.py` (RasterPanel removed) → 9 docks (`Raster`→`NetState`, +`SpikeRate`) with updated presets. No physics change; golden re-verified.

**Tech Stack:** PySide6 6.11, pyqtgraph 0.14 (ImageItem heat, LUT, ViewBox border), NumPy, torch, pytest — `cf_sim`.

---

## File Structure

| File | Change |
|---|---|
| `sim/probe.py` | Add optional `ProbeFrame.input`; `record()` stores `probe.get("input")` |
| `sim/backend.py` | `SoftwareBackend`: store `_last_input` in `infer`; `read_probe` adds `"input"` |
| `sim/eventprop_stepper.py` | Store `_last_x` in `step`; `read_probe` adds `"input"` |
| `sim/ui/panels.py` | Add `NeuronStatePanel`, `SpikeRatePanel`; remove `RasterPanel` |
| `sim/ui/layout.py` | `DOCK_ORDER` (9); presets place `NetState`+`SpikeRate` |
| `sim/ui/app.py` | Build/wire the two new panels instead of raster |
| `tests/test_sim_input_capture.py` | **Create** — capture assertions (self-contained) |
| `tests/test_sim_panels.py` | Drop raster tests; add NeuronState + SpikeRate tests |
| `tests/test_sim_layout.py` | Update preset/visible assertions for 9 docks |
| `tests/test_sim_ui_smoke.py` | Update dock names/count (9) |

---

### Task 1: Input capture (additive, golden-preserving)

**Files:** Modify `sim/probe.py`, `sim/backend.py`, `sim/eventprop_stepper.py`; create `tests/test_sim_input_capture.py`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_sim_input_capture.py`:

```python
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest
import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.backend import SoftwareBackend           # noqa: E402
from sim.probe import AttributeProbe, ProbeFrame   # noqa: E402
from utils.champion_io import load_champion         # noqa: E402

BASELINE = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")
EVENTPROP = os.path.join(REPO, "champions", "PE_t05_gp0002", "best_model.pt")
IN_DIM = 4


def test_probeframe_input_optional():
    p = AttributeProbe(capacity=5)
    p.record(0, {"spikes": np.zeros(3), "v_mem": np.zeros(3), "v_th_eff": np.ones(3)}, np.zeros(5))
    assert p.frames()[-1].input is None                      # backward compatible (no "input")
    p.record(1, {"spikes": np.zeros(3), "v_mem": np.zeros(3), "v_th_eff": np.ones(3),
                 "input": np.array([0.1, 0.2, 0.3, 0.4])}, np.zeros(5))
    assert np.allclose(p.frames()[-1].input, [0.1, 0.2, 0.3, 0.4])


def test_baseline_backend_read_probe_has_input():
    b = SoftwareBackend(load_champion(BASELINE).model)
    b.reset()
    b.infer(torch.zeros(1, IN_DIM))
    d = b.read_probe()
    assert "input" in d and np.asarray(d["input"]).reshape(-1).shape[0] == IN_DIM


def test_eventprop_backend_read_probe_has_input():
    b = SoftwareBackend(load_champion(EVENTPROP).model)
    b.reset()
    b.infer(torch.zeros(1, IN_DIM))
    d = b.read_probe()
    assert "input" in d and np.asarray(d["input"]).reshape(-1).shape[0] == IN_DIM
```

- [ ] **Step 2: Run — verify FAIL**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_input_capture.py -q`
Expected: FAIL — `ProbeFrame` has no `input`; `read_probe` dicts have no `"input"`.

- [ ] **Step 3a: `sim/probe.py`** — add the optional field + store it

In `ProbeFrame` (frozen dataclass), add as the **last** field:

```python
    input: np.ndarray = None      # (in,) network input at this tick; None if not captured
```

In `record()`, build it from the probe dict (optional) and pass it:

```python
    def record(self, t, probe, params):
        if self._count % self.sample_every == 0:
            inp = probe.get("input")
            self._buf.append(ProbeFrame(
                t=t,
                spikes=np.asarray(probe["spikes"], dtype=np.float64),
                v_mem=np.asarray(probe["v_mem"], dtype=np.float64),
                v_th_eff=np.asarray(probe["v_th_eff"], dtype=np.float64),
                params=np.asarray(params, dtype=np.float64).reshape(-1),
                input=(np.asarray(inp, dtype=np.float64).reshape(-1) if inp is not None else None),
            ))
        self._count += 1
```

- [ ] **Step 3b: `sim/backend.py`** — store + expose the input (baseline)

In `SoftwareBackend.__init__` add `self._last_input = None`. In `infer()`, store it:

```python
    def infer(self, obs_norm: torch.Tensor) -> torch.Tensor:
        obs = obs_norm.to(self.device)
        self._last_input = obs.detach().cpu().numpy().reshape(-1)
        if self._eventprop:
            return self._stepper.step(obs)
        return self.model.forward_step(obs)
```

In the **baseline** branch of `read_probe()` (the non-eventprop path), add `"input"` to the returned dict:

```python
        return {"spikes": spikes, "v_mem": v_mem, "v_th_eff": v_th, "input": self._last_input}
```

- [ ] **Step 3c: `sim/eventprop_stepper.py`** — store + expose the input

In `reset()` add `self._last_x = None`. In `step()`, first line, store it:

```python
    def step(self, x_norm):
        self._last_x = x_norm.detach().cpu().numpy().reshape(-1)
        for _ in range(self.n_ticks):
            ...
```

In `read_probe()`, add `"input"` to the dict:

```python
        return {
            "spikes": self._s_prev.detach().cpu().numpy().reshape(-1),
            "v_mem": self._V.detach().cpu().numpy().reshape(-1),
            "v_th_eff": v_th.detach().cpu().numpy().reshape(-1),
            "input": self._last_x,
        }
```

- [ ] **Step 4: Run — verify PASS + golden re-verify**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_input_capture.py tests/test_sim_probe.py tests/test_sim_backend.py tests/test_sim_eventprop.py -q`
Expected: PASS (input tests green; probe/backend/eventprop golden **unchanged** — the input is data that already flows, so bit-identity holds). If a pre-existing test asserts the exact key-set of `read_probe`, add `"input"` to its expected set.

- [ ] **Step 5: Commit**

```bash
git add sim/probe.py sim/backend.py sim/eventprop_stepper.py tests/test_sim_input_capture.py
git commit -m "feat(sim): additive capture of network input in read_probe (+ ProbeFrame.input)"
```

---

### Task 2: `NeuronStatePanel` + `SpikeRatePanel` (and remove `RasterPanel`)

**Files:** Modify `sim/ui/panels.py`; modify `tests/test_sim_panels.py`.

- [ ] **Step 1: Rewrite the raster tests → new-panel tests** in `tests/test_sim_panels.py`:
  1. **Delete** `test_raster_panel_updates` and `test_raster_orientation_time_x_neuron_y`.
  2. Change the import `from sim.ui.panels import ParamPanel, RasterPanel, VmemPanel` → `from sim.ui.panels import NeuronStatePanel, ParamPanel, SpikeRatePanel, VmemPanel`.
  3. **Add**:

```python
def test_neuron_state_panel_groups_and_spike_overlay(qapp):
    H = 6
    spikes = np.array([1, 0, 1, 0, 0, 0], dtype=float)
    p = AttributeProbe(capacity=10)
    p.record(0, {"spikes": spikes, "v_mem": np.linspace(0, 1, H), "v_th_eff": np.ones(H),
                 "input": np.array([0.1, 0.2, 0.3, 0.4])}, np.array([30., 1.5, 2., 1.5, 1.5]))
    panel = NeuronStatePanel()
    panel.update_frame(p)
    assert set(panel._groups.keys()) == {"input", "hidden", "output"}
    heat = panel._groups["hidden"][1].image            # RGBA grid covering >= H cells
    assert heat.ndim == 3 and heat.shape[2] == 4 and heat.shape[0] * heat.shape[1] >= H
    ov = panel._groups["hidden"][2].image              # spike overlay: alpha>0 exactly on spiked cells
    assert int((ov[..., 3] > 0).sum()) == int(spikes.sum())
    assert panel._groups["input"][1].image.shape[0] == 1 and panel._groups["input"][1].image.shape[1] == 4


def test_spike_rate_panel_series(qapp):
    p = AttributeProbe(capacity=10)
    for t in range(3):
        p.record(t, {"spikes": np.array([1., 0, 1, 0, 0, 0, 0, 0]), "v_mem": np.zeros(8),
                     "v_th_eff": np.ones(8)}, np.zeros(5))
    panel = SpikeRatePanel()
    panel.update_frame(p)
    y = panel._curve.getData()[1]
    assert abs(float(y[-1]) - 25.0) < 1e-6             # 2/8 hidden firing = 25 %
```

- [ ] **Step 2: Run — verify FAIL**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -q`
Expected: FAIL — `ImportError` (`NeuronStatePanel`/`SpikeRatePanel` don't exist).

- [ ] **Step 3: Edit `sim/ui/panels.py`** — remove `RasterPanel`, add the two classes

Delete the whole `RasterPanel` class. Add these two classes (keep the module imports; add `import math` is not needed — use numpy):

```python
class SpikeRatePanel(QWidget):
    """Firing-rate trend: % of hidden neurons spiking per tick, over the buffer."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="spike rate (% hidden firing)")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", "rate", units="%")
        self._plot.setDownsampling(auto=True, mode="peak")
        self._plot.setClipToView(True)
        self._curve = self._plot.plot(pen=pg.mkPen("#e8871e", width=2))
        layout.addWidget(self._plot)

    def update_frame(self, probe):
        sm = probe.spikes_matrix()          # (frames, H)
        if sm.size:
            self._curve.setData(sm.mean(axis=1) * 100.0)


_GROUP_BORDERS = [("input", "#2a7fb8"), ("hidden", "#7b3fa0"), ("output", "#2e8b57")]


class NeuronStatePanel(QWidget):
    """Instantaneous neuron-state map at the latest tick: input | hidden | output groups with
    coloured borders; hidden = v_mem heat (viridis) + white overlay on neurons that spiked this tick."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._glw = pg.GraphicsLayoutWidget()
        layout.addWidget(self._glw)
        self._cmap = pg.colormap.get("viridis")
        self._lut = self._cmap.getLookupTable(0.0, 1.0, 256)
        self._groups = {}     # name -> (plot, heat_img, overlay_img_or_None)
        for row, (name, color) in enumerate(_GROUP_BORDERS):
            p = self._glw.addPlot(row=row, col=0)
            p.setTitle(name)
            p.hideAxis("left")
            p.hideAxis("bottom")
            p.getViewBox().setBorder(pg.mkPen(color, width=2))
            heat = pg.ImageItem()
            heat.setColorMap(self._cmap)
            p.addItem(heat)
            overlay = None
            if name == "hidden":
                overlay = pg.ImageItem()      # drawn on top of the heat
                p.addItem(overlay)
            self._groups[name] = (p, heat, overlay)

    def _set_strip(self, name, values):
        _, heat, _ = self._groups[name]
        heat.setImage(np.asarray(values, dtype=np.float64).reshape(1, -1), autoLevels=True)

    def _set_hidden(self, v_mem, spikes):
        _, heat, overlay = self._groups["hidden"]
        v = np.asarray(v_mem, dtype=np.float64).reshape(-1)
        H = v.size
        rows = max(1, int(np.floor(np.sqrt(H))))
        cols = int(np.ceil(H / rows))
        vmin, vmax = float(np.nanmin(v)), float(np.nanmax(v))
        idx = np.clip(((v - vmin) / (vmax - vmin + 1e-9) * 255).astype(int), 0, 255)
        base = np.zeros((rows * cols, 4), dtype=np.ubyte)
        base[:H, :3] = self._lut[idx][:, :3]
        base[:H, 3] = 255
        heat.setImage(base.reshape(rows, cols, 4))
        ov = np.zeros((rows * cols, 4), dtype=np.ubyte)
        spk = np.zeros(rows * cols, dtype=bool)
        spk[:H] = np.asarray(spikes, dtype=np.float64).reshape(-1)[:H] > 0
        ov[spk] = [255, 255, 255, 180]
        overlay.setImage(ov.reshape(rows, cols, 4))

    def update_frame(self, probe):
        frames = probe.frames()
        if not frames:
            return
        f = frames[-1]
        if f.input is not None and np.size(f.input):
            self._set_strip("input", f.input)
        self._set_hidden(f.v_mem, f.spikes)
        self._set_strip("output", f.params)
```

- [ ] **Step 4: Run — verify PASS**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -q`
Expected: PASS. (`heat.setColorMap` in init is ignored for the hidden RGBA `setImage` — RGBA is direct — but harmless; input/output use the colormap + `autoLevels`.)

- [ ] **Step 5: Commit**

```bash
git add sim/ui/panels.py tests/test_sim_panels.py
git commit -m "feat(sim/ui): NeuronStatePanel (state map) + SpikeRatePanel; remove time-raster"
```

---

### Task 3: Wire the two panels into the shell (9 docks + presets)

**Files:** Modify `sim/ui/layout.py`, `sim/ui/app.py`, `tests/test_sim_layout.py`, `tests/test_sim_ui_smoke.py`.

- [ ] **Step 1: Update the layout tests** in `tests/test_sim_layout.py`:
  - `test_neuro_debug_shows_raster_and_vmem` → rename/retarget:

```python
def test_neuro_debug_shows_netstate_and_spikerate(qapp):
    area, docks = _build_area()
    apply_neuro_debug(area, docks)
    assert {"NetState", "SpikeRate", "v_mem"} <= visible_docks(area)
```

  (The other layout tests already use `DOCK_ORDER`/`set(DOCK_ORDER)` and adapt automatically.)

- [ ] **Step 2: Run — verify FAIL**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_layout.py -q`
Expected: FAIL — `DOCK_ORDER` still has `Raster`; `NetState`/`SpikeRate` unknown.

- [ ] **Step 3a: `sim/ui/layout.py`** — 9 docks + presets

Change `DOCK_ORDER` and rewrite the four presets:

```python
DOCK_ORDER = ["Road", "NetState", "SpikeRate", "v_mem", "v0", "T", "s0", "a", "b"]


def apply_overview(area, docks):
    _show(area, docks, "Road", "top")
    _show(area, docks, "NetState", "bottom", "Road")
    _show(area, docks, "SpikeRate", "right", "NetState")
    _show(area, docks, "v_mem", "bottom", "NetState")
    _show(area, docks, "v0", "bottom", "v_mem")
    for prev, n in zip(["v0", "T", "s0", "a"], ["T", "s0", "a", "b"]):
        _show(area, docks, n, "right", prev)


def apply_guida(area, docks):
    _hide(docks, "NetState")
    _hide(docks, "SpikeRate")
    _show(area, docks, "Road", "left")
    _show(area, docks, "v_mem", "right", "Road")
    _show(area, docks, "v0", "bottom", "v_mem")
    for n in ["T", "s0", "a", "b"]:
        _show(area, docks, n, "above", "v0")


def apply_identificazione(area, docks):
    _hide(docks, "v_mem")
    _hide(docks, "NetState")
    _hide(docks, "SpikeRate")
    _show(area, docks, "Road", "top")
    _show(area, docks, "v0", "bottom", "Road")
    for prev, n in zip(["v0", "T", "s0", "a"], ["T", "s0", "a", "b"]):
        _show(area, docks, n, "bottom", prev)


def apply_neuro_debug(area, docks):
    _show(area, docks, "NetState", "left")
    _show(area, docks, "SpikeRate", "right", "NetState")
    _show(area, docks, "v_mem", "bottom", "NetState")
    _show(area, docks, "Road", "bottom", "v_mem")
    _show(area, docks, "v0", "right", "SpikeRate")
    for n in ["T", "s0", "a", "b"]:
        _show(area, docks, n, "above", "v0")
```

- [ ] **Step 3b: `sim/ui/app.py`** — build/wire the two panels instead of raster

Change the import:

```python
from sim.ui.panels import (PARAM_COLORS, PARAM_NAMES, PARAM_UNITS, NeuronStatePanel, ParamPanel,
                           SpikeRatePanel, VmemPanel)
```

Replace `self._raster = RasterPanel()` with:

```python
        self._netstate = NeuronStatePanel()
        self._spikerate = SpikeRatePanel()
```

Update `_live_panels` (NetState + SpikeRate both consume the probe each paint):

```python
        self._live_panels = [self._netstate, self._spikerate, self._vmem, *self._params]
```

X-link the spike-rate time axis to the param master (after the param X-link loop):

```python
        self._spikerate._plot.getPlotItem().setXLink(self._params[0].plot_item)
```

Update the `widgets` map (drop `Raster`, add the two):

```python
        widgets = {"Road": self._topdown, "NetState": self._netstate, "SpikeRate": self._spikerate,
                   "v_mem": self._vmem, "v0": self._params[0], "T": self._params[1],
                   "s0": self._params[2], "a": self._params[3], "b": self._params[4]}
```

- [ ] **Step 4: Update the smoke test** in `tests/test_sim_ui_smoke.py`

`test_simapp_builds_eight_docks` → keep the name or rename; it already asserts `set(win._docks.keys()) == set(DOCK_ORDER)` and `visible_docks == set(DOCK_ORDER)`, which now cover the 9 docks automatically. No change needed unless it hardcodes names — it does not. (Optionally rename to `_builds_docks`.)

- [ ] **Step 5: Run — verify PASS**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py tests/test_sim_layout.py tests/test_sim_ui_smoke.py -q`
Expected: PASS.

- [ ] **Step 6: Full golden suite + render + commit + push**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_state.py tests/test_sim_backend.py tests/test_sim_stepper.py tests/test_sim_scenario.py tests/test_sim_events.py tests/test_sim_probe.py tests/test_sim_replay.py tests/test_sim_loop.py tests/test_sim_input_capture.py tests/test_sim_panels.py tests/test_sim_layout.py tests/test_sim_ui_smoke.py tests/test_sim_eventprop.py tests/test_champion_io.py -q`
Expected: PASS (all).

Render (real platform) Overview + Neuro-debug; inspect: NetState shows 3 coloured-bordered groups (input 4, hidden grid with white spike cells, output 5 = params); SpikeRate shows the firing-% trend; no raster.
```bash
QT_QPA_PLATFORM=windows conda run -n cf_sim python scripts/run_simulator.py
```

```bash
git add sim/ui/layout.py sim/ui/app.py tests/test_sim_layout.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim/ui): 9-dock shell with NetState+SpikeRate; presets updated"
git push
```

---

## Self-Review

**Spec coverage:** D1 raster→NetState (T2 remove + T3 wire) ✓ · D2 SpikeRate (T2) ✓ · D3 input/hidden/output groups (T2 NeuronStatePanel) ✓ · D4 v_mem heat + spike overlay (T2 `_set_hidden`) ✓ · D5 additive input capture (T1) ✓ · D6 9 docks + presets (T3) ✓.

**Placeholder scan:** none — full code for every changed unit; commands runnable.

**Consistency:** `ProbeFrame.input` (T1) read by `NeuronStatePanel.update_frame` (T2) and populated by both `read_probe`s (T1). `DOCK_ORDER` 9 names match the `widgets` map (T3) and presets (T3). `_live_panels` includes both new panels; X-link uses `self._params[0].plot_item`. `_groups` dict keys (`input`/`hidden`/`output`) consistent between panel and test.

**Scope:** scrub (3b) and trajectory/safety (3a) remain out. RasterPanel + its tests removed; the 3a.0 perf changes (downsampling/clip, frame_dt clamp) stay on the surviving line plots.

---

## Execution Handoff

Inline execution (established), in `cf_sim`, TDD per task, render-inspect at Task 3 Step 6. Then resume the pending Phase 3a (trajectory + safety) design.
