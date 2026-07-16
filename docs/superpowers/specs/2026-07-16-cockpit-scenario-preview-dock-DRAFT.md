# Cockpit scenario-preview dock + time marker — Design Spec (**DRAFT**)

**Date:** 2026-07-16 · **Branch/worktree:** `Simulator` · **Status:** 🟡 **DRAFT — captured intent, NOT
finalised.** Written now so the design is not lost; to be reviewed and completed via proper brainstorming
when this cycle is implemented. The forks below are **open**.

## Goal

In the live cockpit, show a preview of the scenario being run, with a marker that moves horizontally so you
can see where in the scenario you are (and what is coming).

The user's item 1: *"Al posto del dock events, sarebbe bello avere invece un'anteprima dello scenario che
stiamo provando e la posizione temporale (tipo un riferimento che si muove orizzontalmente e ti permette di
capire a che punto dello scenario stiamo per arrivare)"*.

## Established facts (grounded now)

- **The docks** are in `DOCK_ORDER` (`layout.py:10`): Road, NetState, SpikeRate, Trajectory, Safety,
  **Events**, Inspector, SynOps + the 5 param panels. Each is a panel object in `app.py:_docks`.
- **"Events" = `self._timeline`** (`app.py:102`) — the brake-injection event marks. Replacing it entirely
  loses that log. See fork ①.
- **The marker mechanism already exists**: the cockpit has a scrub cursor (`_render_at_cursor`,
  `_step_cursor`) that draws a vertical cursor line on the time-series panels (`panels.py` `_cursors`). A
  moving "you are here" marker on the scenario preview is the same `InfiniteLine`-at-tick idea, advanced by
  `_advance`.
- **The scenario's leader profile is `self._scenarios[idx].v_leader`** — the whole thing is known up front,
  so the preview is a static curve + a moving marker (no per-tick recompute).

## Scope (provisional)

**IN**
1. A **ScenarioPreviewPanel** — plots the current scenario's `v_leader` (the whole track) with a vertical
   **marker at the current tick**, advancing as the sim runs (and following the scrub cursor when paused).
2. **Wire it into the cockpit** where the Events dock was.

**OUT (provisional)** — editing the scenario from the cockpit (that is the builder's job); the advisory red
(that is the builder).

## Recommended design (provisional)

- A small `ScenarioPreviewPanel(pg.PlotWidget)`: `set_scenario(v_leader)` draws the curve once;
  `set_tick(t)` moves an `InfiniteLine` marker. Wired in `app.py`: `set_scenario` on `select_scenario`,
  `set_tick` in `_advance`/`_on_timer` and `_render_at_cursor`.
- Reuses the existing cursor idea; no new machinery beyond the panel.

## Open forks (DECIDE AT IMPLEMENTATION)

- **① Replace Events, or coexist?** The user said "al posto del dock Events". But Events carries the
  brake-injection log. Options: **(a)** the new "Scenario" dock takes Events' slot in the DEFAULT layout,
  and Events stays available but hidden (toggle it back on); **(b)** replace Events entirely (lose the
  injection log). *Lean: (a) — add the dock, default-show it where Events was, keep Events one toggle away.
  Nothing is destroyed.*
- **② What does the preview show?** Just the leader profile, or the leader + the ego (a mini-Trajectory)?
  *Lean: the leader profile alone (the "scenario"), with the marker; the Trajectory dock already shows the
  ego. Keep it a clean "the track + where we are".*
- **③ The marker while running vs paused** — during a run it follows the live tick; when paused on a scrub
  cursor it follows the cursor. *Lean: the marker = the cockpit's current tick/cursor, one source.*
- **④ DOCK_ORDER change** — adding "Scenario" changes `DOCK_ORDER`; the layout tests (`test_sim_layout.py`)
  assert on the dock set. They must be updated in lockstep. Not a fork, a flag.

## Rough testing sketch

- `set_scenario` draws the leader profile; `set_tick(t)` puts the marker at t; advancing the sim moves the
  marker; the marker follows the scrub cursor when paused; the dock appears in the cockpit and Events is
  still reachable; the layout tests updated for the new DOCK_ORDER.
