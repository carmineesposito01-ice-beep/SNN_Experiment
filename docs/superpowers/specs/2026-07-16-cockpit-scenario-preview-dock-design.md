# Cockpit scenario-preview dock + time marker — Design Spec

**Date:** 2026-07-16 · **Branch/worktree:** `Simulator` · **Status:** ✅ **FINAL — approved.** Supersedes the
DRAFT (`2026-07-16-cockpit-scenario-preview-dock-DRAFT.md`, removed). Grounded on a full read of the source
on 2026-07-16 (every `file:line` verified, not recalled).

## Goal

In the live cockpit, replace the **Events** dock with a **preview of the scenario being run**: the whole
`v_leader` profile drawn statically, plus a **vertical marker at the current tick** that slides as the sim
advances — so you can see where you are in the scenario and what is coming.

User's item 1: *"Al posto del dock events, sarebbe bello avere invece un'anteprima dello scenario che stiamo
provando e la posizione temporale (un riferimento che si muove orizzontalmente e ti permette di capire a che
punto dello scenario stiamo per arrivare)."*

## Decisions (the forks, resolved)

- **① Replace, don't coexist.** Hard replace: the Events dock is removed and "Scenario" takes its slot. The
  injected-event **log disappears from the cockpit** (accepted trade-off). The injection *action* stays (see
  §3). We do **not** fold the events back onto the preview — the dock stays a clean "track + marker".
- **② Leader only.** The preview draws the scenario's `v_leader` alone. The ego is already in the Trajectory
  dock; and the ego is not known ahead (it grows with the run) so it could not be a static curve anyway.
- **③ Marker = the cockpit's current tick**, from one source (§2). Not a fork — an implementation fact.
- **④ Guida shows the preview.** Events is hidden in the "Guida" (driving) preset today; the preview is most
  useful exactly there, so "Guida" flips to **show** Scenario. The one placement improvement over Events.

## Established facts (grounded, verified this session)

- **The docks** are `DOCK_ORDER` (`layout.py:10`): Road, NetState, SpikeRate, Trajectory, Safety, **Events**,
  Inspector, SynOps + the 5 param panels. Built into `self._docks` by the loop at `app.py:107-113`.
- **"Events" = `self._timeline = EventTimelinePanel()`** (`app.py:80`) — injected brake events as clickable
  marks (`panels.py:126-196`). It is in `_ts_panels` (`app.py:91`), gets a scrub cursor via `set_cursor`,
  and its click→seek is wired at `app.py:93` (`set_on_seek(self._seek_to)`).
- **Events appears in all 4 presets**, but is **hidden in Guida**: `apply_overview:57` (bottom of Safety),
  `apply_guida:62` (in the hide-list), `apply_identificazione:79` (bottom of b), `apply_neuro_debug:90`
  (bottom of Road).
- **The marker mechanism already exists**: `_add_cursor`/`_set_cursor` (`panels.py:22-35`) draw/move a
  vertical `InfiniteLine`. Every time-series panel uses it via `set_cursor`.
- **The whole leader profile is known up front**: `self._scenarios[idx].v_leader` (indexed by tick;
  `inject_brake` reads `stepper.v_leader[min(st.t, N-1)]` at `app.py:478`). So the preview is a static curve
  + a moving marker — no per-tick recompute.
- **The current tick**: live → `self._last_result.t`; scrub → `frames[idx].t` (inside `_render_at_cursor`,
  `app.py:656-668`). The scrub set (`_ts_panels`) is driven by a **buffer index**, not a tick.
- **`_seek_to` (`app.py:670-680`) is reachable only from the event marks** (via `set_on_seek`). With the
  hard replace it becomes dead code → removed.
- **The injector is independent of the dock**: `EventInjector` (`app.py:431`) feeds both steppers
  (`:443-444`) and is read by `ReplayLog`/reconstruct (`:693,698`); the "Brake leader" button is `:134`.

## Scope

**IN**
1. A new **`ScenarioPreviewPanel`** (`sim/ui/scenario_preview.py`) — self-contained, testable alone.
2. Wire it into the cockpit as the **"Scenario"** dock, in Events' slot; remove the Events dock.
3. `layout.py`: `DOCK_ORDER` + 4 presets renamed Events→Scenario; Guida flips to show it.

**OUT**
- Editing the scenario from the cockpit (the builder's job); the advisory red (the builder's).
- Overlaying the injected events on the preview (fork ① rejected the fold).
- Click-the-preview-to-seek (a navigation control; the preview is a read-only view). Flagged for later.

## Design

### The one new unit — `sim/ui/scenario_preview.py`

`ScenarioPreviewPanel(QWidget)`, a `pg.PlotWidget` with its **own** `InfiniteLine` marker (no coupling to
`panels.py` internals). Matches the cockpit look: dark plot, orange (`#e8871e`) static curve, white dashed
marker. API:
- `set_scenario(v_leader)` — `self._curve.setData(np.asarray(v_leader))`, drawn once. x = tick index
  (0..N-1), y = leader speed (m/s).
- `set_marker(tick)` — moves the marker to `float(tick)`; `None` hides it.
- `clear()` — `setData([])` on the curve and hides the marker.

It is **not** added to `_ts_panels` (that group receives a buffer index via `set_cursor`; the marker wants a
tick). It is driven explicitly by the app.

### The marker's single source of truth

The marker = the cockpit's current tick, set from exactly two call sites:
- **Live** — in `_paint` (`app.py:486`), after results: `if self._dock_on("Scenario"):
  self._preview.set_marker(self._last_result.t)` (gated like the other panels). Replaces the `update_events`
  line at `:538`.
- **Paused / scrub / deep-scrub** — in `_render_at_cursor` (`app.py:656`): `self._preview.set_marker(
  frames[idx].t)`.

`select_scenario` (`app.py:424`) calls `self._preview.set_scenario(sc.v_leader)` and `set_marker(None)` (new
track, marker hidden until the first tick). `_clear_panels` (`:460-465`) includes `self._preview` (its
`clear()` blanks curve + marker).

### The hard-replace surgery

**Removed**
- `EventTimelinePanel` class (`panels.py:126-196`) — no longer referenced.
- `app.py`: `self._timeline` (`:80`); its membership in `_ts_panels` (`:91`); `set_on_seek` (`:93`); the
  `"Events"` widget entry (`:102`); the `update_events` branch (`:538`); `_timeline` in `_clear_panels`
  (`:464`); the now-dead `_seek_to` (`:670-680`). Drop `EventTimelinePanel` from the `panels` import
  (`:27`) and **add** `from sim.ui.scenario_preview import ScenarioPreviewPanel`.

**Renamed — `layout.py`**
- `DOCK_ORDER` (`:10`): `"Events"` → `"Scenario"`.
- `apply_overview:57`: `_show(..., "Events", "bottom", "Safety")` → `"Scenario"`.
- `apply_guida:62`: drop `"Events"` from the hide-list (→ `("NetState", "SpikeRate", "Inspector",
  "SynOps")`) and **add** `_show(area, docks, "Scenario", "bottom", "Safety")` (same placement as Overview).
  This is decision ④.
- `apply_identificazione:79`: `"Events"` → `"Scenario"`.
- `apply_neuro_debug:90`: `"Events"` → `"Scenario"`.

**Kept** — `EventInjector` (`:431`), `inject_brake`/`_brake_btn` (`:134,476`), the injector's use by
reconstruct/replay (`:693,698`). Injection still works; only the visual dock is gone.

**Caveat (honest, documented in-code):** the preview shows the *planned* `v_leader`. An injected brake
overrides the leader live and will **not** appear on the preview (it shows in Trajectory/Road). The preview
answers "where am I in the scripted scenario", not "what did the leader actually do".

## Testing

- **New `tests/test_sim_scenario_preview.py`** (panel alone): `set_scenario(v)` → curve data equals `v`;
  `set_marker(t)` → marker at `t` and visible; `set_marker(None)` → hidden; `clear()` → curve empty + marker
  hidden.
- **Integration in `test_sim_ui_smoke.py`**: advancing the sim moves the marker to the last result's tick
  (compute the expected tick from the loop, don't hard-code); scrubbing to a cursor moves the marker to
  `frames[idx].t`; `select_scenario` redraws the curve to the new scenario's `v_leader`.
- **`test_sim_layout.py` updated**: `DOCK_ORDER` contains "Scenario" not "Events"; `apply_overview` →
  `visible_docks == set(DOCK_ORDER)` (includes Scenario); `apply_guida` shows "Scenario".
- **Expected churn**: every test naming Events / `EventTimelinePanel` (`test_sim_panels.py` has an
  `EventTimelinePanel` test; `test_sim_ui_smoke.py` may assert the Events dock) is updated in lockstep — the
  plan enumerates them before deleting the class.

## Invariants (must hold)

- Frozen core (`sim/{state,stepper,backend,probe,events,eventprop_stepper}.py`) untouched.
- `utils/closed_loop_eval.py` untouched; `sim/scenario_spec.py` `materialise` untouched.
- Runner: the env's python directly (never `conda run`); full suite ~4 min (≥420 s or background).
- Render-verify with `QT_QPA_PLATFORM=windows`. No LAPACK in `cf_sim`.
- Commits conventional, **no `Co-Authored-By`**.
