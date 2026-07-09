# Time-Scrub Core Implementation Plan (Extension Phase 3b.1)

> **STATUS: ✅ COMPLETE (2026-07-08).** Executed inline in `cf_sim` (TDD). T1 cursor lines + index-aware graph, T2 render_at, T3 app wiring — commits up to `0d09894` (pushed). 77 tests green; core untouched. Render-verified: paused at t=35, cursor line on every plot + net-graph/road reconstructed to t=35.

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`) syntax.
> Runs in **`cf_sim`** (offscreen for Qt). Spec: `docs/superpowers/specs/2026-07-08-scrub-core-design.md`. All in `sim/ui/*`; golden core untouched.

**Goal:** Pause + scrub a global time cursor over the buffer — cursor line on time-series docks, network graph at the cursor tick, road reconstructed to the cursor tick, with a slider + `Space`/`←`/`→`/`Home`/`End`.

**Architecture:** cursor lines via a helper (`_add_cursor`/`_set_cursor`) on the 5 time-series panels; `NeuronGraphPanel.update_frame(probe, index=-1)` index-aware; `TopDownView.render_at(traj, index)` reconstructs `ego_x=Σv·DT`; app gates live-vs-scrub on the Run button, with a time slider, readout, and shortcuts.

**Tech Stack:** PySide6 6.11, pyqtgraph 0.14 (`InfiniteLine`), NumPy, pytest — `cf_sim`.

---

## File Structure

| File | Change |
|---|---|
| `sim/ui/panels.py` | **Modify** — `_add_cursor`/`_set_cursor` + `_cursors`/`set_cursor` on the 5 time-series panels; `NeuronGraphPanel.update_frame(probe, index=-1)` (+ `_last_vals`) |
| `sim/ui/topdown.py` | **Modify** — extract `_place`; add `render_at(traj, index)` (+ `import numpy as np`) |
| `sim/ui/app.py` | **Modify** — cursor state, slider, readout, shortcuts, `_render_at_cursor`/`_on_cursor`/`_step_cursor`, Run gating |
| `tests/test_sim_panels.py` | **Append** — set_cursor + NetGraph index-aware |
| `tests/test_sim_ui_smoke.py` | **Append** — render_at + app scrub |

---

### Task 1: cursor lines + index-aware NetGraph (`panels.py`)

- [ ] **Step 1: Write failing tests** (append to `tests/test_sim_panels.py`):

```python
def test_param_panel_cursor(qapp):
    p = ParamPanel(0, "v0", "m/s", "#d1495b")
    p.set_cursor(7)
    assert p._cursors[0].isVisible() and abs(p._cursors[0].value() - 7.0) < 1e-6
    p.set_cursor(None)
    assert not p._cursors[0].isVisible()


def test_trajectory_panel_cursor_all_subplots(qapp):
    p = TrajectoryPanel()
    p.set_cursor(3)
    assert len(p._cursors) == 3 and all(c.isVisible() for c in p._cursors)


def test_neuron_graph_index_aware(qapp):
    H, IN, OUT = 6, 4, 5
    rng = np.random.default_rng(1)
    panel = NeuronGraphPanel()
    panel.set_topology(rng.standard_normal((H, IN)), rng.standard_normal((H, H)),
                       rng.standard_normal((OUT, H)))
    pr = AttributeProbe(capacity=10)
    pr.record(0, {"spikes": np.zeros(H), "v_mem": np.zeros(H), "v_th_eff": np.ones(H),
                  "input": np.zeros(IN)}, np.zeros(OUT))
    pr.record(1, {"spikes": np.ones(H), "v_mem": np.linspace(1, 2, H), "v_th_eff": np.ones(H),
                  "input": np.ones(IN)}, np.ones(OUT))
    panel.update_frame(pr, index=0)
    v0 = panel._last_vals.copy()
    panel.update_frame(pr, index=1)
    assert not np.allclose(v0, panel._last_vals)              # different tick -> different state
    panel.update_frame(pr, index=99)                          # out-of-range clamps, no raise
```

- [ ] **Step 2: Run — verify FAIL** (`AttributeError: ... '_cursors'` / `update_frame() got ... 'index'`)

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -k "cursor or index_aware" -q`

- [ ] **Step 3a: Add cursor helpers to `sim/ui/panels.py`** (after the imports / `_N_SAMPLE`):

```python
def _add_cursor(plot):
    ln = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#ffffff", width=1, style=Qt.DashLine))
    ln.setVisible(False)
    plot.addItem(ln)
    return ln


def _set_cursor(cursors, x):
    for c in cursors:
        if x is None:
            c.setVisible(False)
        else:
            c.setPos(float(x))
            c.setVisible(True)
```

- [ ] **Step 3b: Add `_cursors` + `set_cursor` to the 5 time-series panels.** In each `__init__`, after the plot(s) and curves are built, add the `_cursors` line, and add the method. Exact per panel:

- **`VmemPanel`** — after `layout.addWidget(self._plot)`:
  ```python
        self._cursors = [_add_cursor(self._plot.getPlotItem())]

    def set_cursor(self, x):
        _set_cursor(self._cursors, x)
  ```
- **`SpikeRatePanel`** — same two additions (one plot).
- **`ParamPanel`** — after `layout.addWidget(self._plot)` (before `@property plot_item`), add the `_cursors` line and `set_cursor` method (one plot).
- **`TrajectoryPanel`** — after the curves: `self._cursors = [_add_cursor(p) for p in (self._pg, self._pv, self._pa)]` + `set_cursor`.
- **`SafetyPanel`** — `self._cursors = [_add_cursor(p) for p in (self._pt, self._pd)]` + `set_cursor`.

(All five `set_cursor` bodies are identical: `_set_cursor(self._cursors, x)`.)

- [ ] **Step 3c: Make `NeuronGraphPanel.update_frame` index-aware.** Replace its signature/first lines:

```python
    def update_frame(self, probe, index=-1):
        frames = probe.frames()
        if not frames or self._pos is None:
            return
        n = len(frames)
        i = index if index >= 0 else n + index
        i = max(0, min(i, n - 1))
        f = frames[i]
```

and at the end of the method store the rendered vector for testability — change the `vals = ...` assignment to also keep it:

```python
        self._last_vals = vals
        self._nodes.setData(pos=self._pos, brush=self._brushes(vals), pen=pens, size=13)
```

(Add `self._last_vals = None` in `__init__` next to `self._pos = None`.)

- [ ] **Step 4: Run — verify PASS**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -q`
Expected: PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add sim/ui/panels.py tests/test_sim_panels.py
git commit -m "feat(sim/ui): cursor lines on time-series panels + index-aware NeuronGraphPanel"
```

---

### Task 2: `TopDownView.render_at` (reconstruct)

- [ ] **Step 1: Write failing tests** (append to `tests/test_sim_ui_smoke.py`):

```python
from sim.ui.trajectory import TrajectoryBuffer   # noqa: E402


def _traj_seq(vs, ss):
    tb = TrajectoryBuffer()
    for i, (v, s) in enumerate(zip(vs, ss)):
        tb.record(StepResult(t=i, s=s, v=v, vl=v - 1.0, dv=1.0, a_ego=0.0, params=np.zeros(5),
                             collided=False))
    return tb


def test_topdown_render_at_reconstructs(qapp):
    from config import DT
    view = TopDownView()
    vs = [10.0, 12.0, 8.0, 15.0]
    tb = _traj_seq(vs, [30.0, 28.0, 26.0, 24.0])
    view.render_at(tb, 2)
    assert abs(view.ego_x_m() - float(np.cumsum(vs)[2] * DT)) < 1e-6
    view.render_at(tb, -1)                       # head
    assert abs(view.ego_x_m() - float(np.sum(vs) * DT)) < 1e-6
```

- [ ] **Step 2: Run — verify FAIL** (`AttributeError: ... 'render_at'`)

Run: `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py::test_topdown_render_at_reconstructs -q`

- [ ] **Step 3: Edit `sim/ui/topdown.py`** — add `import numpy as np` at the top; refactor `update_frame` to a `_place` helper + add `render_at`:

```python
    def _place(self, ego_x, s, dv):
        self._ego_x = ego_x
        self._last_s = s
        ego_px = self._ego_x * PX_PER_M
        leader_px = self.leader_x_m() * PX_PER_M
        self._ego.setPos(ego_px, 0)
        self._leader.setPos(leader_px, 0)
        self._ego_label.setPos(ego_px - 12, -VEH_W_M * PX_PER_M - 8)
        self._leader_label.setPos(leader_px - 18, -VEH_W_M * PX_PER_M - 8)
        col = QColor(_COL[ttc_color(s, dv)])
        y = VEH_W_M * PX_PER_M + 4
        self._gap_line.setLine(ego_px + VEH_LEN_M / 2 * PX_PER_M, y,
                               leader_px - VEH_LEN_M / 2 * PX_PER_M, y)
        self._gap_line.setPen(QPen(col, 2, Qt.DashLine))
        self._gap_text.setPlainText(f"s = {s:.1f} m")
        self._gap_text.setDefaultTextColor(col)
        self._gap_text.setPos((ego_px + leader_px) / 2 - 22, y + 2)
        self.centerOn(ego_px, 0)

    def update_frame(self, r):
        self._place(self._ego_x + r.v * DT, r.s, r.dv)

    def render_at(self, traj, index):
        a = traj.arrays()
        if a["t"].size == 0:
            return
        n = a["t"].size
        i = index if index >= 0 else n + index
        i = max(0, min(i, n - 1))
        self._place(float(np.cumsum(a["v"])[i] * DT), float(a["s"][i]), float(a["dv"][i]))
```

(Delete the old `update_frame` body — its logic now lives in `_place`.)

- [ ] **Step 4: Run — verify PASS** (render_at + the existing `test_topdown_ego_scrolls_and_leader_tracks_gap`)

Run: `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/topdown.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim/ui): TopDownView.render_at reconstructs ego/leader at a cursor tick"
```

---

### Task 3: App scrub wiring (slider + shortcuts + cursor render)

- [ ] **Step 1: Write failing tests** (append to `tests/test_sim_ui_smoke.py`):

```python
def test_simapp_scrub_cursor(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)                                  # ~5 buffered ticks
    win._run_btn.setChecked(False)                     # ensure paused
    win._render_at_cursor(2)
    assert win._cursor == 2
    assert win._params[0]._cursors[0].isVisible()      # cursor line shown on a time-series panel
    win._step_cursor(1)
    assert win._cursor == 3
    win._step_cursor(999)                              # clamps to head
    assert win._cursor == len(win._probe.frames()) - 1
```

- [ ] **Step 2: Run — verify FAIL** (`AttributeError: ... '_render_at_cursor'`)

Run: `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py::test_simapp_scrub_cursor -q`

- [ ] **Step 3: Edit `sim/ui/app.py`**

  1. **Imports**: add `QLabel` is already imported; ensure `QSlider` is imported (it is, used for speed). Add `from PySide6.QtCore import Qt` (already). Add `from PySide6.QtGui import QKeyEvent` is not needed.
  2. **`__init__`**: add `self._cursor = None`. Build the scrub controls and add them to the `controls` row (after the speed slider):

```python
        self._cursor_slider = QSlider(Qt.Horizontal)
        self._cursor_slider.setEnabled(False)
        self._cursor_slider.setFixedWidth(160)
        self._cursor_slider.valueChanged.connect(self._on_cursor)
        self._cursor_readout = QLabel("live")
```

     and include them in the `for w in (...)` controls loop: add `QLabel("t"), self._cursor_slider, self._cursor_readout`.
     Define the time-series panel list (after `self._live_panels = ...`): `self._ts_panels = [*self._params, self._vmem, self._spikerate, self._trajectory, self._safety]`.

  3. **Add methods** (near `_on_run_toggled`):

```python
    def _buf_len(self):
        return len(self._probe.frames())

    def _render_at_cursor(self, idx):
        frames = self._probe.frames()
        if not frames:
            return
        idx = max(0, min(int(idx), len(frames) - 1))
        self._cursor = idx
        for p in self._ts_panels:
            p.set_cursor(idx)
        self._netstate.update_frame(self._probe, idx)
        self._topdown.render_at(self._traj, idx)
        self._cursor_readout.setText(f"t={frames[idx].t} ({frames[idx].t * DT:.1f}s)")

    def _on_cursor(self, v):
        if not self._run_btn.isChecked():
            self._render_at_cursor(v)

    def _step_cursor(self, d):
        if self._run_btn.isChecked() or self._buf_len() == 0:
            return
        cur = self._cursor if self._cursor is not None else self._buf_len() - 1
        self._cursor_slider.setValue(max(0, min(cur + d, self._buf_len() - 1)))
```

  4. **`_on_run_toggled`**: gate live-vs-scrub. Replace the method with:

```python
    def _on_run_toggled(self, running: bool):
        if running:
            self._cursor = None
            self._cursor_slider.setEnabled(False)
            for p in self._ts_panels:
                p.set_cursor(None)
            self._cursor_readout.setText("live")
            self._clock.restart()
            self._timer.start(_UI_FPS_MS)
        else:
            self._timer.stop()
            n = self._buf_len()
            self._cursor_slider.setEnabled(n > 0)
            self._cursor_slider.blockSignals(True)
            self._cursor_slider.setRange(0, max(0, n - 1))
            self._cursor_slider.setValue(max(0, n - 1))
            self._cursor_slider.blockSignals(False)
```

  5. **`keyPressEvent`** (add to the class):

```python
    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key_Space:
            self._run_btn.toggle()
        elif k == Qt.Key_Left:
            self._step_cursor(-1)
        elif k == Qt.Key_Right:
            self._step_cursor(1)
        elif k == Qt.Key_Home:
            self._on_cursor(0) if not self._run_btn.isChecked() else None
        elif k == Qt.Key_End:
            self._on_cursor(self._buf_len() - 1) if not self._run_btn.isChecked() else None
        else:
            super().keyPressEvent(event)
```

  6. **`_paint`** (live): keep the slider tracking the head while running — after the panels update, inside `if results:` add:

```python
            if self._run_btn.isChecked():
                self._cursor_slider.blockSignals(True)
                self._cursor_slider.setRange(0, max(0, self._buf_len() - 1))
                self._cursor_slider.setValue(max(0, self._buf_len() - 1))
                self._cursor_slider.blockSignals(False)
```

- [ ] **Step 4: Run — panels + smoke**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py tests/test_sim_panels.py -q`
Expected: PASS.

- [ ] **Step 5: Full golden suite + render + commit + push**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_state.py tests/test_sim_backend.py tests/test_sim_stepper.py tests/test_sim_scenario.py tests/test_sim_events.py tests/test_sim_probe.py tests/test_sim_replay.py tests/test_sim_loop.py tests/test_sim_input_capture.py tests/test_sim_trajectory.py tests/test_sim_panels.py tests/test_sim_layout.py tests/test_sim_ui_smoke.py tests/test_sim_eventprop.py tests/test_champion_io.py -q`
Expected: PASS (all).

Render: build `SimApp`, advance, pause, `_render_at_cursor(mid)`, grab → confirm the white cursor line on the plots + the net-graph/road at the frozen tick. Send the PNG.

```bash
git add sim/ui/app.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim/ui): time-scrub — pause + cursor slider/shortcuts render every dock at a frozen tick"
git push
```

---

## Self-Review

**Spec coverage:** D1 Run gates live/scrub (T3 `_on_run_toggled`) ✓ · D2 slider + shortcuts + readout (T3) ✓ · D3 cursor lines on 5 time-series panels (T1) ✓ · D4 NetGraph index-aware (T1) ✓ · D5 road `render_at` reconstruct (T2) ✓ · D6 core only (event-timeline/inspector out) ✓.

**Placeholder scan:** none — full code; the per-panel `set_cursor` bodies are identical and spelled out.

**Consistency:** `set_cursor`/`_cursors` (T1) called by `_render_at_cursor` (T3); `NeuronGraphPanel.update_frame(probe, idx)` (T1) called by the app (T3); `TopDownView.render_at(traj, idx)` (T2) called by the app (T3); `_ts_panels` excludes NetState/Road (they render-at-cursor differently). `_buf_len` from `probe.frames()`.

**Scope:** event-timeline (3b.2), inspector (3b.3), ReplayLog-beyond-buffer out. Core golden untouched.

---

## Execution Handoff

Inline execution (established), in `cf_sim`, TDD per task, render-inspect + send at Task 3 Step 5.
