# Meso Page v2 — Design Spec

**Date:** 2026-07-10 · **Branch/worktree:** `Simulator` · **Status:** decisions approved (user) → spec

## Goal

Enrich the Meso/Macro analysis page with three user-requested additions, keeping the **batch
on-demand** model and the **frozen core**:

1. **Scenario selection in Meso** — the platoon head follows a chosen scenario's leader profile.
2. **Velocity-wave view** `v(t)` per vehicle (replaces the per-vehicle params panel) — to *see* the
   stop-and-go wave attenuation, not just the quantified string-stability gains.
3. **Platoon road view** ("like live") — the N cars on the carriageway, with a slider + Play to
   scrub/animate the recorded run.

## Established facts (verified in code)

- `sim/scenario.py::scenario_library`: **all scenarios share `params_gt`** and differ only in the
  `v_leader` profile (`following · stop_and_go · hard_brake · cut_in · sinusoidal`, + tail variants).
  → "scenario in Meso" = choosing the **head stimulus** (`v_leader`). The macro ring sweep stays
  scenario-independent (`params_gt` is constant).
- `sim/ui/platoon.py::run_platoon(champion, params_gt, n, v_leader_profile)` already accepts an
  arbitrary head profile — feeding `scenario.v_leader` is a caller change only.
- `simulate_platoon` `rec` carries `v, x, gap, a` (T,N) + `v_leader` — enough for the velocity waves
  and the road view. The T4 `rec['params']` (T,N,5) becomes unused once the params panel is removed.
- `sim/ui/topdown.py::TopDownView` is hard-wired to a single ego+leader (QGraphicsView, road scroll,
  gap coloured by TTC). A **new `PlatoonRoadView`** is needed for N cars; it reuses the road-drawing
  style + `PX_PER_M`/`VEH_LEN_M`.

## Decisions (user, 2026-07-10 — AskUserQuestion)

- **Road view**: **slider + Play**, driven by the recorded `rec` (no live sim).
- **Layout**: road strip full-width on top; 2×2 analysis below = string-stability, velocity `v(t)`,
  space-time `x(t)`, fundamental diagram `Q/V`. The params panel is removed.

## Design

### Layout (`MesoMacroPage`)

```
controls:  [ scenario ▾ ]  [ N veicoli ]  [ Run platoon ]  [ Run ring sweep ]
[=====================  PlatoonRoadView  (slider + ▶)  =====================]   top strip
[ string-stability            |  SpeedWavePanel  v(t) ]                          2×2 grid
[ SpaceTimePanel  x(t)        |  FundamentalDiagramPanel  Q/V ]
```

Root `QVBoxLayout`: controls row → road view (modest fixed-ish height) → 2×2 grid (`stretch=1`,
`setColumnStretch`/`setRowStretch` as in T4).

### ① Scenario selector (meso)

- `MesoMacroPage.__init__(scenario_names=None)` builds a `QComboBox` of scenario names in the controls
  row; exposes `selected_scenario_index() -> int`.
- `SimApp`: populate the selector with `[s.name for s in self._scenarios]`; default to the currently
  selected live scenario index. `_run_platoon` uses
  `self._scenarios[self._meso_page.selected_scenario_index()].v_leader` as the head profile
  (replacing the fixed `_platoon_head_profile()` sinusoid; that static helper is removed).
- The ring sweep (`_run_ring`) is unchanged (scenario-independent).

### ② SpeedWavePanel + `_MultiCurvePanel` base (DRY)

- Extract a base **`_MultiCurvePanel(field, title, ylabel, y_units)`** from the current
  `SpaceTimePanel`: N viridis curves of `rec[field][:, i]` vs time, with the T4 fixes centralised
  (`addWidget(self._plot)` + explicit `setXRange`/`setYRange` framing + `setClipToView`/downsampling).
  - `SpaceTimePanel` = `_MultiCurvePanel(field="x", title="spazio-tempo (traiettorie plotone)",
    ylabel="x", y_units="m")`.
  - `SpeedWavePanel` = `_MultiCurvePanel(field="v", title="onde di velocità (attenuazione stop&go)",
    ylabel="v", y_units="m/s")`.
- `SpeedWavePanel` replaces `PlatoonParamsPanel` at grid cell (0,1).
- **Removed** (YAGNI, params no longer shown): `PlatoonParamsPanel` class + its 2 tests + the
  `MesoMacroPage`/`SimApp` `params_gt` plumbing + the `rec['params']` recording in
  `utils/platoon_eval.py` (revert the T4 additive line). Removal is additive-safe → single-vehicle
  golden stays **bit-identical**.

### ③ PlatoonRoadView (`sim/ui/meso_road.py`)

- `QGraphicsView` drawing the road in `TopDownView`'s style (dark lane + dashed centre-line,
  `PX_PER_M`, `VEH_LEN_M`). Shared road constants factored out of `topdown.py` (or imported).
- **N car polygons** (arrow-nosed, one per vehicle). At frame `t` each car is placed at
  `rec['x'][t, i]` and **coloured by speed** `rec['v'][t, i]` via a viridis LUT over `[0, v_max]`
  (`v_max` = max of `rec['v']`) → slow cars dark, fast bright → stop-and-go bands visible. Vehicle 0
  is the head.
- **Camera**: `centerOn(mean(x[t]))` so the platoon stays framed while the road scrolls (mirrors the
  live ego-pinned scroll). Road extent (`sceneRect`) computed from `rec['x']` min/max + margin in
  `set_run` (the platoon travels ~km over a run — the fixed 5 km road of `TopDownView` is not enough).
- **Controls**: a `QSlider` (0..T-1) + a **Play** `QPushButton` toggling a `QTimer` (~30 fps, loops)
  that advances the slider. Slider change → `render_frame(t)`. `set_run(rec)` stores `rec`, sets the
  slider range, computes the road extent, renders frame 0.
- **Own timer**, independent of the live `SimLoop`. Switching to Live mode (`set_mode(0)`) stops it.

### Data flow

- **Run platoon** → `rec = run_platoon(champ, _PARAMS_GT, N, scenario.v_leader)`; feed:
  string-stability (`platoon_metrics`), space-time (`x`), speed-waves (`v`), road-view (`set_run(rec)`).
- **Run ring sweep** → fundamental diagram (unchanged).

### Non-goals / invariants

- **Frozen behavioural core untouched.** `platoon_eval`: the T4 `rec['params']` line is **removed**
  (net additive-safe; single-vehicle golden bit-identical). No other `platoon_eval` change.
- **Batch on-demand**: the road-view Play animates the **recorded** `rec`, never a live sim.
- Live mode unchanged; entering Live stops the road-view timer.

## Testing strategy

1. **Scenario (meso)** — `MesoMacroPage` has a scenario selector; `SimApp._run_platoon` uses the
   selected scenario's `v_leader` (`rec['v_leader']` equals `self._scenarios[idx].v_leader`).
2. **`_MultiCurvePanel`/SpeedWavePanel** (offscreen) — `SpeedWavePanel.set_rec(rec)` makes N curves
   from `rec['v']`; the plot is in the layout; the view fits the data (regression for the auto-range
   bug). `SpaceTimePanel` keeps its existing behaviour via the shared base.
3. **PlatoonRoadView** (offscreen) — `set_run(rec)` sets slider max = T-1 and creates N car items;
   `render_frame(t)` positions the cars at `rec['x'][t]`; toggling Play starts/stops the `QTimer`.
4. **Removal** — `PlatoonParamsPanel` is gone (referencing it errors); `_PARAMS_GT`/`params_gt` no
   longer threaded to the page.
5. **Golden suite** — full sim list green; single-vehicle golden **bit-identical** (`rec['params']`
   removed cleanly).
6. **Render-verify** — meso page v2 for a **BPTT** and an **EventProp** champion on a **stop_and_go**
   scenario: velocity waves visibly attenuate down the platoon; the road view animates the same run.

## File map (delta)

- `sim/ui/meso_panels.py` — add `_MultiCurvePanel` base + `SpeedWavePanel`; refactor `SpaceTimePanel`
  onto it; **remove** `PlatoonParamsPanel`.
- `sim/ui/meso_road.py` — **new** `PlatoonRoadView` (N-car road + slider + Play).
- `sim/ui/meso_page.py` — scenario selector; road strip on top; grid = string-stability + speed-wave
  + space-time + fundamental; drop `params_gt`/params panel.
- `sim/ui/topdown.py` — factor out shared road constants (no behavioural change).
- `sim/ui/app.py` — populate the meso scenario selector; `_run_platoon` uses `scenario.v_leader` +
  feeds speed-wave + road-view; remove `_platoon_head_profile` + `params_gt` plumbing.
- `utils/platoon_eval.py` — remove the T4 `rec['params']` recording.
- Tests: `test_sim_meso_panels.py` (speed-wave + base; drop the 2 `PlatoonParamsPanel` tests),
  `test_sim_platoon.py` (drop `test_simulate_platoon_records_params` — `rec['params']` removed),
  `test_sim_meso_road.py` (**new**), `test_sim_ui_smoke.py` (update
  `test_simapp_run_platoon_populates_meso`: drop the params assertion, add a speed-wave + road-view
  assertion; scenario-driven platoon).

## Implementation phases (for the plan)

- **P1** — `_MultiCurvePanel` base + `SpeedWavePanel`; refactor `SpaceTimePanel`; remove
  `PlatoonParamsPanel` + `rec['params']`; page grid swap. (TDD + golden bit-identity.)
- **P2** — scenario selector in `MesoMacroPage` + `SimApp._run_platoon` uses `scenario.v_leader`.
- **P3** — `PlatoonRoadView` (road + N cars + slider + Play) + wire into the page top strip.
- **P4** — render-verify (BPTT + EventProp, stop_and_go), full golden, docs + memory.
