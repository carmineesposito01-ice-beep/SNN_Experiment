# Cockpit scenario-preview dock — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the cockpit **Events** dock with a **Scenario** dock — a static preview of the running
scenario's `v_leader` profile plus a vertical marker that slides to the current tick.

**Architecture:** One new self-contained panel (`ScenarioPreviewPanel`, its own `InfiniteLine`, tested
alone). Then a single atomic swap in `layout.py` + `app.py` (the DOCK_ORDER rename and the widgets-dict entry
must change together, or `SimApp` won't construct). The marker is driven by the **current tick** from exactly
two sites — `_paint` (live head) and `_render_at_cursor` (scrub cursor) — deliberately **not** via
`_redraw_series` (it has paused-context callers that would pin the marker to the head) and **not** by joining
`_ts_panels` (that group is driven by a buffer index, not a tick). Finally, sweep the now-dead
`EventTimelinePanel`.

**Tech Stack:** Python, PySide6, pyqtgraph. Env: conda `cf_sim`.

**Runner (NEVER `conda run`):**
```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest <args> -p no:cacheprovider
```
**Suite scope — the "full suite" is the SIM tests only:** `tests/test_sim_*.py tests/test_champion_io.py`
(23 + 1 = 24 files). Do **not** run `pytest tests/` — the dir also holds FPGA-track scripts
(`tests/test_fpga_io.py` calls `sys.exit()` at import) that abort pytest collection with
`INTERNALERROR> SystemExit`. Those files belong to another track and are not ours to fix.

Full suite ~3–4 min → run with a **≥420 s timeout or in the background** (a 2-min timeout looks like a hang and
is not one). Render-verify with `QT_QPA_PLATFORM=windows`. No LAPACK in `cf_sim`. Commits conventional, **no
`Co-Authored-By`**. Frozen core (`sim/{state,stepper,backend,probe,events,eventprop_stepper}.py`),
`utils/closed_loop_eval.py`, and `sim/scenario_spec.py` `materialise` stay **untouched**.

**Baseline:** record it in Task 1 Step 0 (do not hard-code a magic number — a past bug). Net test delta over
the whole plan: **+3** panel-unit + **+3** integration − **3** removed `EventTimelinePanel` tests = **+3**; the
seek test is restructured (stays 1, not removed).

**Test-design rules for this plan (non-negotiable):**
- Compute every expected value from the running code (a probe, `_last_result.t`, `frames[idx].t`) — never from
  memory. The marker asserts against whatever tick the engine *actually* produced.
- Each task ends by **sabotaging the fix** and watching the guard test fail — the sabotage must exercise the
  guarded property, then revert.
- Use **Edit** (fails loud on a mismatch), never a silent `replace()`. Anchor every edit to the shown lines.
- Check the suite is **GREEN before committing**, as a separate action after pytest.

---

### Task 1: `ScenarioPreviewPanel` — isolated, tested alone

**Files:**
- Create: `sim/ui/scenario_preview.py`
- Test: `tests/test_sim_scenario_preview.py`

- [ ] **Step 0: Record the baseline**

Run the full suite (background or ≥420 s) and write down the passing count `B`:
```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -q -p no:cacheprovider
```
Expected: `B passed` (B is ~289; record the real number).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sim_scenario_preview.py`:
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

from sim.ui.scenario_preview import ScenarioPreviewPanel   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_set_scenario_draws_the_whole_profile(qapp):
    panel = ScenarioPreviewPanel()
    v = np.array([20.0, 21.0, 19.5, 12.0, 12.0], dtype=float)
    panel.set_scenario(v)
    x, y = panel._curve.getData()
    assert np.allclose(y, v)                       # the whole profile, not a slice
    assert np.allclose(x, np.arange(len(v)))       # x = tick index


def test_set_marker_positions_then_hides(qapp):
    panel = ScenarioPreviewPanel()
    panel.set_marker(42)
    assert panel._marker.isVisible()
    assert abs(panel._marker.value() - 42.0) < 1e-6
    panel.set_marker(None)
    assert not panel._marker.isVisible()


def test_clear_blanks_curve_and_marker(qapp):
    panel = ScenarioPreviewPanel()
    panel.set_scenario(np.arange(10.0))
    panel.set_marker(3)
    panel.clear()
    _, y = panel._curve.getData()
    assert y is None or len(y) == 0                # curve blanked
    assert not panel._marker.isVisible()           # marker hidden
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_preview.py -q -p no:cacheprovider
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.ui.scenario_preview'`.

- [ ] **Step 3: Implement the panel**

Create `sim/ui/scenario_preview.py`:
```python
"""ScenarioPreviewPanel — a dockable static preview of the scenario's leader profile with a tick marker.

The whole v_leader is known up front (materialise runs before the sim), so the curve is drawn once via
set_scenario() and only the marker moves (set_marker()). Self-contained: its own InfiniteLine, no coupling to
panels.py internals. The app drives the marker with the current TICK (live: the last result's t; scrub:
frames[idx].t) -- deliberately NOT a member of _ts_panels, whose set_cursor() receives a buffer index."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget


class ScenarioPreviewPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="scenario")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", "v_leader", units="m/s")
        self._plot.setMouseEnabled(x=True, y=False)
        self._curve = self._plot.plot(pen=pg.mkPen("#e8871e", width=2))   # static, no downsampling: getData is exact
        self._marker = pg.InfiniteLine(angle=90, movable=False,
                                       pen=pg.mkPen("#ffffff", width=1, style=Qt.DashLine))
        self._marker.setVisible(False)
        self._plot.addItem(self._marker)
        layout.addWidget(self._plot)

    def set_scenario(self, v_leader):
        """Draw the whole leader profile once. x = tick index (0..N-1), y = leader speed (m/s)."""
        self._curve.setData(np.asarray(v_leader, dtype=float))

    def set_marker(self, tick):
        """Move the marker to `tick` (a sim tick); hide it when tick is None."""
        if tick is None:
            self._marker.setVisible(False)
        else:
            self._marker.setPos(float(tick))
            self._marker.setVisible(True)

    def clear(self):
        self._curve.setData([])
        self._marker.setVisible(False)
```

- [ ] **Step 4: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_preview.py -q -p no:cacheprovider
```
Expected: `3 passed`.

- [ ] **Step 5: Sabotage the fix, watch the guard fail, revert**

In `set_marker`, temporarily change the else-branch to `self._marker.setVisible(False)` (never shows). Re-run:
expected FAIL on `test_set_marker_positions_then_hides` (`assert panel._marker.isVisible()`). This proves the
test exercises the visibility property. **Revert** the change; re-run → `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add sim/ui/scenario_preview.py tests/test_sim_scenario_preview.py
git commit -m "feat(sim): ScenarioPreviewPanel -- static leader curve + tick marker, tested alone"
```

---

### Task 2: The swap — Events dock → Scenario dock (layout + app + tests)

This is atomic: `DOCK_ORDER` and the `widgets` dict must change together. Land it fully green; the dead
`EventTimelinePanel` class stays in `panels.py` until Task 3 (its own tests still pass, so the suite is green).

**Files:**
- Modify: `sim/ui/layout.py:10` (DOCK_ORDER) and the 4 presets (`:57,:61-62,:79,:90`)
- Modify: `sim/ui/app.py` (`:27` import, `:80`, `:90-91`, `:93`, `:102`, `:457`, `:463`, `:490`, `:538`,
  `:668`, remove `:670-680`)
- Test: `tests/test_sim_layout.py` (Guida assertion), `tests/test_sim_ui_smoke.py` (94 comment, 223 rename,
  240-253 restructure, + 3 new marker tests)

- [ ] **Step 1: Write the failing layout assertion (decision ④)**

In `tests/test_sim_layout.py`, find the Guida test:
```python
def test_guida_shows_driving_docks(qapp):
    area, docks = _build_area()
    from sim.ui.layout import apply_guida
    apply_guida(area, docks)
    assert {"Road", "Trajectory", "Safety"} <= visible_docks(area)
```
Add one line after the existing assert:
```python
    assert "Scenario" in visible_docks(area)   # decision (4): the driving preset SHOWS the preview
```

- [ ] **Step 2: Write the 3 new integration tests**

Append to `tests/test_sim_ui_smoke.py`:
```python
# --- item 1: scenario-preview dock + tick marker ---
def test_scenario_marker_follows_the_live_tick(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)                                   # 5 live steps
    expected = win._last_result.t                       # the tick the engine just produced
    assert win._preview._marker.isVisible()
    assert abs(win._preview._marker.value() - expected) < 1e-6


def test_scenario_marker_follows_the_scrub_cursor(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    win._on_run_toggled(False)                          # pause -> scrub source ready
    win._render_at_cursor(2)                            # scrub to buffer index 2
    expected = win._src_probe.frames()[2].t             # its absolute tick
    assert abs(win._preview._marker.value() - expected) < 1e-6


def test_select_scenario_redraws_the_preview_curve(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    y0 = win._preview._curve.getData()[1]
    assert np.allclose(y0, win._scenarios[0].v_leader)
    win.select_scenario(1)
    y1 = win._preview._curve.getData()[1]
    assert np.allclose(y1, win._scenarios[1].v_leader)  # redrawn to the new scenario
```

- [ ] **Step 3: Update the churned smoke assertions**

In `tests/test_sim_ui_smoke.py`:

(a) line 94 — update the comment only (assertion is invariant):
```python
    assert set(win._docks.keys()) == set(DOCK_ORDER)     # Road/NetState/SpikeRate/Trajectory/Safety/Scenario/Inspector/SynOps + 5 params
```

(b) line 223 — rename the dock name:
```python
    assert {"Scenario", "Inspector", "SynOps"} <= set(win._docks)
```

(c) lines 240-253 — the old `test_simapp_event_click_and_neuron_select` uses the removed `_seek_to`. Replace
the whole function with a neuron-select-only test (the seek feature is gone; neuron-select coverage stays):
```python
def test_simapp_neuron_select(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    win._on_run_toggled(False)                   # pause
    win._on_neuron_selected(1)                   # select hidden neuron 1
    assert win._inspector.neuron == 1
    assert win._netstate._highlight.adjacency.shape[0] > 0
```

- [ ] **Step 4: Run the new/churned tests to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_layout.py tests/test_sim_ui_smoke.py -q -p no:cacheprovider
```
Expected: FAIL — `test_guida_shows_driving_docks` (no "Scenario" yet), the 3 marker tests (`AttributeError:
'SimApp' object has no attribute '_preview'`), and `test_simapp_builds_all_docks` (no "Scenario" in `_docks`).

- [ ] **Step 5: Rename Events → Scenario in `layout.py`**

`sim/ui/layout.py`, `DOCK_ORDER` (line 10):
```python
DOCK_ORDER = ["Road", "NetState", "SpikeRate", "Trajectory", "Safety",
              "Scenario", "Inspector", "SynOps", "v0", "T", "s0", "a", "b"]
```
`apply_overview` (line 57):
```python
    _show(area, docks, "Scenario", "bottom", "Safety")
```
`apply_guida` (lines 61-62): drop `"Events"` from the hide-list **and** show Scenario. Change:
```python
    for d in ("NetState", "SpikeRate", "Inspector", "Events", "SynOps"):
        _hide(docks, d)
```
to:
```python
    for d in ("NetState", "SpikeRate", "Inspector", "SynOps"):
        _hide(docks, d)
```
and add, right after the `_show(... "Safety" ...)` line in that function:
```python
    _show(area, docks, "Scenario", "bottom", "Safety")   # decision (4): preview visible while driving
```
`apply_identificazione` (line 79):
```python
    _show(area, docks, "Scenario", "bottom", "b")   # preview next to the params
```
`apply_neuro_debug` (line 90):
```python
    _show(area, docks, "Scenario", "bottom", "Road")
```

- [ ] **Step 6: Swap the panel in `app.py`**

Edit each anchor (use Edit; the anchors are exact):

(a) Import — line 27, drop `EventTimelinePanel` and add the new import. Change:
```python
from sim.ui.panels import (PARAM_COLORS, PARAM_NAMES, PARAM_UNITS, EventTimelinePanel,
                           NeuronGraphPanel, NeuronInspectorPanel, ParamPanel, SafetyPanel,
                           SpikeRatePanel, SynOpsPanel, TrajectoryPanel)
```
to:
```python
from sim.ui.panels import (PARAM_COLORS, PARAM_NAMES, PARAM_UNITS,
                           NeuronGraphPanel, NeuronInspectorPanel, ParamPanel, SafetyPanel,
                           SpikeRatePanel, SynOpsPanel, TrajectoryPanel)
from sim.ui.scenario_preview import ScenarioPreviewPanel
```

(b) Construction — line 80:
```python
        self._preview = ScenarioPreviewPanel()
```
(was `self._timeline = EventTimelinePanel()`).

(c) `_ts_panels` — lines 90-91, remove `self._timeline`:
```python
        self._ts_panels = [*self._params, self._spikerate, self._trajectory,
                           self._safety, self._inspector, self._synops]
```

(d) Remove the seek wiring — delete line 93 entirely:
```python
        self._timeline.set_on_seek(self._seek_to)
```

(e) widgets dict — line 102, rename the entry:
```python
                   "Scenario": self._preview, "Inspector": self._inspector, "SynOps": self._synops,
```
(was `"Events": self._timeline, ...`).

(f) `_clear_panels` — line 463, swap `self._timeline` → `self._preview`:
```python
        for p in (*self._params, self._spikerate, self._trajectory,
                  self._safety, self._preview, self._synops, self._netstate):
```

(g) `select_scenario` — after `self._clear_panels()` (line 457), draw the new scenario's curve. Change:
```python
        self._clear_panels()                              # blank stale curves/road so Reset visibly resets
        self._refresh_status()
```
to:
```python
        self._clear_panels()                              # blank stale curves/road so Reset visibly resets
        self._preview.set_scenario(sc.v_leader)           # the whole leader profile for THIS scenario
        self._preview.set_marker(None)                    # no marker until the first tick
        self._refresh_status()
```

(h) Live marker — in `_paint`, after line 490, set the marker to the live head (gated like the other panels).
Change:
```python
            self._src_probe, self._src_traj = self._probe, self._traj   # live advanced -> scrub source = live
            self._src_ghost_traj = self._ghost_traj
            last = len(results) - 1
```
to:
```python
            self._src_probe, self._src_traj = self._probe, self._traj   # live advanced -> scrub source = live
            self._src_ghost_traj = self._ghost_traj
            if self._dock_on("Scenario"):
                self._preview.set_marker(self._last_result.t)           # marker follows the live tick
            last = len(results) - 1
```

(i) Remove the old Events redraw — delete line 538 entirely:
```python
        if self._dock_on("Events"): self._timeline.update_events(self._injector.log(), probe.frames())
```
(The marker is set in `_paint`/`_render_at_cursor`, NOT here — `_redraw_series` also runs in paused contexts
where the marker must stay on the scrub cursor, not jump to the head.)

(j) Scrub marker — in `_render_at_cursor`, after the readout at line 668, add:
```python
        self._preview.set_marker(frames[idx].t)   # scrub: marker follows the cursor's absolute tick
```

(k) Remove the now-dead `_seek_to` — delete the whole method (lines 670-680):
```python
    def _seek_to(self, tick):
        if self._run_btn.isChecked():
            self._run_btn.setChecked(False)               # pause -> builds the scrub source
        frames = self._src_probe.frames()
        idx = next((i for i, f in enumerate(frames) if f.t == tick), None)
        if idx is None:
            return
        self._render_at_cursor(idx)
        self._cursor_slider.blockSignals(True)
        self._cursor_slider.setValue(idx)
        self._cursor_slider.blockSignals(False)
```

- [ ] **Step 7: Run the targeted tests to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_layout.py tests/test_sim_ui_smoke.py tests/test_sim_scenario_preview.py -q -p no:cacheprovider
```
Expected: all pass (layout Guida assertion green, 3 marker tests green, `test_simapp_neuron_select` green,
dock-set assertions green).

- [ ] **Step 8: Run the full suite (green before commit)**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -q -p no:cacheprovider
```
Expected: `B+6 passed` (baseline + 3 panel + 3 integration; the 3 `EventTimelinePanel` tests still pass —
the class is still present). The suite is ~4 min → ≥420 s timeout or background.

- [ ] **Step 9: Sabotage the live-marker wiring, watch it fail, revert**

In `_paint` (edit h), change `self._preview.set_marker(self._last_result.t)` to
`self._preview.set_marker(0)`. Re-run:
```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py::test_scenario_marker_follows_the_live_tick -q -p no:cacheprovider
```
Expected: FAIL (marker at 0, expected `_last_result.t` > 0). This proves the test tracks the real tick.
**Revert** to `self._last_result.t`; re-run → pass.

- [ ] **Step 10: Commit**

```bash
git add sim/ui/layout.py sim/ui/app.py tests/test_sim_layout.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): replace the Events dock with a Scenario preview + tick marker"
```

---

### Task 3: Sweep the dead `EventTimelinePanel`

Now nothing references it. Remove the class and its tests together.

**Files:**
- Modify: `sim/ui/panels.py` (remove the `EventTimelinePanel` class, lines ~126-196)
- Modify: `tests/test_sim_panels.py` (remove the 3 tests + `_pf` + `ProbeFrame` import + section comment,
  lines ~151-186)

- [ ] **Step 1: Confirm there are no remaining references**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -q -p no:cacheprovider -k "not event_timeline" >/dev/null
grep -rn "EventTimelinePanel\|_seek_to\|update_events" sim/ tests/
```
Expected grep hits ONLY in `sim/ui/panels.py` (the class itself) and `tests/test_sim_panels.py` (its 3 tests).
If anything else appears, stop — a reference was missed in Task 2.

- [ ] **Step 2: Remove the class from `panels.py`**

Delete the entire `EventTimelinePanel` class (from `class EventTimelinePanel(QWidget):` through the end of its
`_on_click` method, before the `_INPUT_NAMES = [...]` line). Also update the module docstring's panel list:
in the top docstring drop `EventTimelinePanel (clickable injected events).` from the sentence.

- [ ] **Step 3: Remove the 3 tests from `test_sim_panels.py`**

Delete lines ~151-186: the `# --- Phase 3b (rest): event timeline ---` comment, the
`from sim.ui.panels import EventTimelinePanel` and `from sim.probe import ProbeFrame` imports, the `_pf` helper,
and the three tests (`test_event_timeline_maps_ticks_and_drops_out_of_range`,
`test_event_timeline_click_seeks_by_tick`, `test_event_timeline_has_cursor`).

- [ ] **Step 4: Run the full suite (green before commit)**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -q -p no:cacheprovider
```
Expected: `B+3 passed` (baseline + 3 panel + 3 integration − 3 removed EventTimeline tests). ≥420 s or bg.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/panels.py tests/test_sim_panels.py
git commit -m "refactor(sim): remove the now-dead EventTimelinePanel"
```

---

### Task 4: Final verification, render-verify, docs

**Files:**
- Modify: `document/SIMULATOR_SESSION_RESUME.md`, `document/SIMULATOR_ARCHITECTURE.md`

- [ ] **Step 1: Full suite once more + confirm the invariants are untouched**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -q -p no:cacheprovider
git diff --stat HEAD~3 -- sim/state.py sim/stepper.py sim/backend.py sim/probe.py sim/events.py sim/eventprop_stepper.py utils/closed_loop_eval.py sim/scenario_spec.py
```
Expected: `B+3 passed`; the `git diff --stat` prints **nothing** (frozen core + closed_loop_eval + scenario_spec
untouched).

- [ ] **Step 2: Render-verify the dock**

Write a short throwaway script in the scratchpad that builds `SimApp(CHAMP)`, `select_scenario(0)`,
`_advance(2.0)`, grabs the `_preview` plot to a PNG (`QT_QPA_PLATFORM=windows`), and confirm by eye: the whole
`v_leader` curve is drawn, the marker sits at the current tick (~tick 20 after 2 s), and the dock is titled
"scenario". Also switch to the Guida preset and confirm the Scenario dock is visible. Delete the script after.

- [ ] **Step 3: Update the docs**

`document/SIMULATOR_ARCHITECTURE.md`: add a `sim/ui/scenario_preview.py` row to the scenario-stack module
map; remove `EventTimelinePanel` from the periphery/`panels.py` description; note "Events" is gone from
`DOCK_ORDER` (now "Scenario") and that Guida shows it; bump the test count to the real number.

`document/SIMULATOR_SESSION_RESUME.md`: mark item 1 (cockpit scenario-preview dock) **done** with the real
count; note the Events dock was hard-replaced (injection action + injector stay; the visual log is gone); the
marker is driven from `_paint`/`_render_at_cursor`; leave items 2 (scenario lifecycle) and 7 (dataset
generator) as the remaining queued drafts.

- [ ] **Step 4: Commit + push**

```bash
git add document/SIMULATOR_SESSION_RESUME.md document/SIMULATOR_ARCHITECTURE.md
git commit -m "docs(sim): resume + map -- cockpit scenario-preview dock (item 1) done"
git push origin Simulator
```

- [ ] **Step 5: Report — do NOT merge to main**

Report the cycle complete. Merge → main stays **parked** (sequenced behind Simulink_Importer, standing user
decision). Then, per executing-plans, invoke finishing-a-development-branch **only to present options** — do
not auto-merge.

---

## Self-review (against the spec)

- **Spec §"Decisions" ①/②/④** → Task 2 (hard replace; leader-only via the panel's single curve; Guida shows
  it, locked by the new layout assertion). ✓
- **Spec §Design "the one new unit"** → Task 1. ✓
- **Spec §Design "single source of truth"** → Task 2 edits (h)+(j); the plan explicitly forbids the
  `_redraw_series` path and documents why. ✓
- **Spec §Design "hard-replace surgery" removals** → Task 2 edits (a-k) + Task 3 (the class). Every removal in
  the spec's list is a named edit. ✓
- **Spec §Design "kept"** (injector, brake button, reconstruct/replay) → untouched by every task; verified by
  the Step-1 grep in Task 3 (references only in the class + its tests). ✓
- **Spec §Testing "expected churn"** → Task 2 Step 3 (94/223/240-253) + Task 3 Step 3 (panel tests). Every
  churn site the spec named has a step. ✓
- **Spec §Invariants** → Task 4 Step 1 diff-stat gate. ✓
- **Placeholder scan:** none — every code step shows complete code. ✓
- **Type/name consistency:** `set_scenario`/`set_marker`/`clear`/`_curve`/`_marker`/`_preview` identical across
  Tasks 1-2 and both test files. ✓
