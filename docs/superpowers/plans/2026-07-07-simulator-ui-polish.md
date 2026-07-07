# Simulator UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`).
> UI is visual/iterative: logic goes through TDD smoke tests; look-and-feel is verified with `scripts/render_simulator_frame.py` PNGs inspected after each task. All work runs in the **`cf_sim`** conda env.

**Goal:** Turn the minimal MVP UI into a polished, readable desktop app across four areas the user picked (all): top-down road view, net-panel readability, controls + status bar, and a coherent dark theme.

**Architecture:** Keep the Plan-4 structure (`sim/ui/{loop,topdown,netpanel,app}`); this plan enriches the three widgets + adds a small `theme.py`. The pure `SimLoop` is unchanged. New testable logic (ego-position integration, TTC→color, status text, reset/step) gets smoke tests; visuals get render checks.

**Tech Stack:** PySide6 (Qt6) + pyqtgraph, in `cf_sim`. Run tests: `conda run -n cf_sim bash -c "cd <wt> && QT_QPA_PLATFORM=offscreen python -m pytest tests/test_sim_ui_smoke.py -q"`.

**This is Plan 5** (post-MVP polish). Runs entirely on the `Simulator` branch.

---

## Design decisions per area

### 1. Top-down (`topdown.py`) — biggest visual win
- **Road**: dark asphalt band (fixed lane height) spanning a large `sceneRect`; dashed centre line at fixed world-x intervals + solid lane edges → scrolling road.
- **Ego pinned, world scrolls**: track absolute `ego_x` (integrate `r.v * DT` per frame); `leader_x = ego_x + (r.s + VEH_LEN)`; `centerOn(ego)` every frame so ego stays centred and the road/leader scroll past.
- **Car glyphs**: rounded-rect body + a small "nose" polygon (direction) + outline; ego blue / leader red.
- **Labels & gap**: `QGraphicsTextItem` "ego"/"leader" above each; a gap line + `s = X.X m` label between them, **coloured by TTC** (green safe / amber / red danger via a pure `ttc_color(s, dv)`).

### 2. Net-panel (`netpanel.py`)
- **Param plot**: `addLegend()` (colour→name) + live current-value in each curve's name (`v0=41.7` …); Y-range set to the union of physical bounds so values have context; x-axis labelled `time [s]`.
- **v_mem plot**: overlay the per-neuron **effective threshold** (dashed) for the sample neurons; y-label `v_mem`.
- **raster**: x-axis `time [s]`, y `neuron`.

### 3. Controls + status bar (`app.py`)
- **QStatusBar**: `t=.. (X.Xs) | ego .. m/s | leader .. m/s | gap .. m | collided | min-gap ..`, updated each frame.
- **Buttons**: existing Run/Brake + **Reset** (re-select current scenario) + **Step** (one fixed step) + a **speed** slider (steps-per-UI-tick 1–8).
- **Header**: window title + a label showing champion name + current scenario.

### 4. Theme (`theme.py` + `app.py`)
- Dark `QPalette` + a compact stylesheet (matches the black pyqtgraph plots); consistent margins/spacing; pyqtgraph `setConfigOptions(background=..., foreground=..)`.

---

### Task 1: Top-down overhaul

**Files:** Modify `sim/ui/topdown.py`; Test: append to `tests/test_sim_ui_smoke.py`.

- [ ] **Step 1: Failing tests (append)** — pure logic + widget smoke.

```python
# --- Task: top-down polish ---
from sim.ui.topdown import TopDownView, ttc_color


def test_ttc_color_bands():
    assert ttc_color(100.0, -5.0) == "safe"      # opening / far -> safe
    assert ttc_color(50.0, 0.0) == "safe"        # not closing
    danger = ttc_color(3.0, 5.0)                  # 0.6 s TTC -> danger
    caution = ttc_color(15.0, 5.0)               # 3 s TTC -> caution
    assert danger == "danger" and caution == "caution"


def test_topdown_ego_scrolls_and_leader_tracks_gap(qapp):
    view = TopDownView()
    view.update_frame(_stepv(s=30.0, v=20.0))
    ex1, lx1 = view.ego_x_m(), view.leader_x_m()
    view.update_frame(_stepv(s=25.0, v=20.0))
    ex2, lx2 = view.ego_x_m(), view.leader_x_m()
    assert ex2 > ex1                              # ego advanced (integrated v)
    assert lx2 - ex2 < lx1 - ex1                  # gap shrank (30 -> 25)
```

Add helper near `_step`:
```python
def _stepv(s, v):
    return StepResult(t=0, s=s, v=v, vl=v, dv=0.0, a_ego=0.0, params=np.zeros(5), collided=False)
```

- [ ] **Step 2: Run — FAIL** (`ImportError: cannot import name 'ttc_color'`). Run in cf_sim (offscreen).
- [ ] **Step 3: Rewrite `sim/ui/topdown.py`** — road, scrolling ego, glyphs, labels, TTC gap. (Full code written at implementation; key public API: `ttc_color(s,dv)->str`, `TopDownView.ego_x_m()`, `.leader_x_m()`, `.update_frame(r)`.)
- [ ] **Step 4: Run — PASS** + render `scripts/render_simulator_frame.py` → inspect PNG, refine visuals.
- [ ] **Step 5: Commit** `feat(sim/ui): top-down road + scrolling ego + car glyphs + TTC gap`.

---

### Task 2: Net-panel readability

**Files:** Modify `sim/ui/netpanel.py`; Test: append to smoke.

- [ ] **Step 1: Failing test** — legend + current-value readout + threshold overlay exist.

```python
def test_netpanel_has_legend_and_current_values(qapp):
    probe = AttributeProbe(capacity=50)
    for t in range(4):
        probe.record(t, {"spikes": np.zeros(8), "v_mem": np.linspace(0, 1, 8),
                          "v_th_eff": np.ones(8)}, np.array([30., 1.5, 2., 1.5, 1.5]))
    panel = NetPanel()
    panel.update_frame(probe)
    labels = panel.current_param_labels()          # e.g. ["v0=30.0", "T=1.50", ...]
    assert len(labels) == 5 and labels[0].startswith("v0=")
```

- [ ] **Step 2: FAIL** (`current_param_labels` missing).
- [ ] **Step 3: Update `netpanel.py`** — `addLegend`, per-curve current-value names, bounds Y-range, axis labels, v_mem threshold overlay; expose `current_param_labels()`.
- [ ] **Step 4: PASS** + render + inspect.
- [ ] **Step 5: Commit** `feat(sim/ui): net-panel legend + live values + axis labels + threshold`.

---

### Task 3: Controls + status bar

**Files:** Modify `sim/ui/app.py`; Test: append to smoke.

- [ ] **Step 1: Failing tests** — status text, reset, step.

```python
def test_simapp_status_reset_step(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    s = win.status_text()
    assert "gap" in s and "ego" in s
    win.step_once()
    t_after = win.loop.stepper.st.t
    win.reset_run()
    assert win.loop.stepper.st.t == 0 and t_after >= 5
```

- [ ] **Step 2: FAIL** (`status_text`/`step_once`/`reset_run` missing).
- [ ] **Step 3: Update `app.py`** — `QStatusBar` + `status_text()`, `reset_run()`, `step_once()`, speed slider, champion/scenario header label.
- [ ] **Step 4: PASS** + render + inspect.
- [ ] **Step 5: Commit** `feat(sim/ui): status bar + reset/step/speed controls + header`.

---

### Task 4: Dark theme

**Files:** Create `sim/ui/theme.py`; Modify `sim/ui/app.py`; Test: append to smoke.

- [ ] **Step 1: Failing test** — theme applied.

```python
from sim.ui.theme import apply_dark_theme

def test_dark_theme_applies(qapp):
    apply_dark_theme(qapp)
    from PySide6.QtGui import QPalette
    bg = qapp.palette().color(QPalette.Window)
    assert bg.lightness() < 128                    # dark
```

- [ ] **Step 2: FAIL** (`sim.ui.theme` missing).
- [ ] **Step 3: Create `theme.py`** (dark QPalette + stylesheet + pyqtgraph config) and call `apply_dark_theme(app)` in `run_simulator.py` / `render_simulator_frame.py`.
- [ ] **Step 4: PASS** + final render across all four → inspect.
- [ ] **Step 5: Commit** `feat(sim/ui): dark theme` + push.

---

## Self-Review
- Covers all 4 user-selected areas. Logic (ttc_color, ego integration, status, reset/step, theme) is unit-smoke-tested; visuals via PNG render after each task. Pure `SimLoop` untouched → Plan-1 golden unaffected. Runs in `cf_sim`.

## Execution Handoff
Inline in `cf_sim`, render-inspect after each task, refine before commit.
