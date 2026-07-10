# Post-run Mode + Export — Design Spec (Phase 4, scoped)

**Date:** 2026-07-10 · **Branch/worktree:** `Simulator` · **Status:** design approved (user) → spec

## Goal

Phase 4, scoped to the two pieces the user chose (the float-vs-fixed A/B is deferred — it needs a
fixed-point Qm.n SW forward that does not exist yet):

1. **Post-run mode** — a third mode (Live / Meso-Macro / **Post-run**) showing an aggregate
   "report card" of the single episode the simulator just ran.
2. **Export** — a File → Export… menu that saves the episode as **CSV** (per-tick time-series) and
   the current window as **PNG** ("save what you see").

## Established facts (verified in code)

- The mode shell is a `QStackedWidget` in `SimApp`: page 0 = Live cockpit, page 1 = `MesoMacroPage`;
  a `QComboBox` (`_mode_sel`, items `["Live", "Meso/Macro"]`) drives `set_mode(idx)`. Adding a third
  page + item is the established pattern.
- `set_mode` already stops the live run on entering analysis (`_run_btn.setChecked(False)`) and (after
  the freeze fix) stops the road playback on returning to Live.
- Per-tick data available every frame in `_paint(results)`: each `StepResult` carries
  `t, s (gap), v, vl, dv, a_ego, params (5,), collided`; the matching `probe` frames carry `spikes`
  (firing = `spikes.mean()`). `loop.tick` records one probe frame per returned `StepResult`, so the
  last `len(results)` probe frames align with `results`.
- `sim/ui/metrics.py` already has the safety/energy primitives used by the live docks: `ttc`,
  `drac`, `time_headway`, `synops`/`synops_series`, `dense_mac`, `ann_mac`, and the Horowitz 45 nm
  constants `E_AC_PJ = 0.9`, `E_MAC_PJ = 4.6`. The SynOps dock computes per-tick SynOps from the
  champion topology dims `self._synops._dims = (IN, H, rank, OUT)`.
- The live ring buffers (`probe`, `traj`) are capped at 500 ticks; a full episode is 600 ticks. A
  full-episode summary therefore must NOT rely on the buffers (and must NOT reconstruct — that was
  the freeze we just removed). → accumulate incrementally as the episode runs.

## Design

### ① EpisodeSummary — incremental accumulator (`sim/ui/episode.py`, pure, no Qt)

A plain object updated once per tick; O(1)/tick; independent of the 500-tick buffer cap.

- `EpisodeSummary(dims)` where `dims = (IN, H, rank, OUT)` (for per-tick SynOps energy).
- `reset()` — clear all state (called on scenario/champion change).
- `update(r, spikes)` — fold in one tick: `r` (StepResult) + `spikes` (H-vector for this tick).
- Accumulates:
  - **outcome**: `collided` (any tick), `n_ticks`, `duration_s = n_ticks * DT`.
  - **safety**: `min_gap = min(r.s)`, `min_ttc = min(ttc(r.s, r.dv))`, `max_decel = max(-r.a_ego)`.
  - **comfort**: `rms_accel = sqrt(mean(a²))`, `rms_jerk = sqrt(mean(((a_t - a_{t-1})/DT)²))`
    (keeps the previous `a` to form the jerk).
  - **network**: `mean_firing`, `peak_firing` (from `spikes.mean()` per tick).
  - **energy**: `snn_pj = Σ_t synops(spikes_t, dims) * E_AC_PJ`;
    `ann_pj = n_ticks * ann_mac(dims) * E_MAC_PJ`; `advantage = ann_pj / snn_pj`.
  - **rows**: append one CSV row per tick (for export) —
    `(t, gap, v, v_leader, dv, accel, ttc, v0, T, s0, a, b, firing_pct)`.
- Read side: `summary()` → a dict of the aggregates (rounded); `rows()` → the per-tick list.
- Per-episode memory is bounded by the episode length (≤ ~600 rows) — reset each run.

`write_episode_csv(rows, path)` (same module, pure): write a header + the rows to `path`.

### ② PostRunPage (`sim/ui/postrun_page.py`)

A `QWidget` "report card":
- A header label: `champion · scenario`.
- A grid of labelled values grouped into **Esito** (esito ok/COLLISIONE, durata), **Sicurezza**
  (min gap, min TTC, max decel), **Comfort** (RMS accel, RMS jerk), **Efficienza** (energia SNN pJ,
  energia ANN pJ, vantaggio ×), **Rete** (firing medio %, firing picco %).
- Two small pyqtgraph summary plots of the full episode from `rows()`: speed `v(t)` and gap `gap(t)`.
- `set_summary(summary_dict, rows, champion_name, scenario_name)` populates everything. Values are
  read-only labels; the collision verdict is coloured (green ok / red collided).

### ③ SimApp wiring

- `self._episode = EpisodeSummary(dims)` built from the champion topology (same dims as the SynOps
  dock); `reset()` in `select_scenario`; rebuilt on champion swap (`select_champion`).
- In `_paint`, after recording each result to `traj`, also `self._episode.update(r, spikes_t)` using
  the aligned probe frame (`self._probe.frames()[-len(results):]`).
- Mode shell: `_mode_sel.addItems([..., "Post-run"])`; `_mode_stack.addWidget(self._postrun_page)`;
  `set_mode(2)` → stop live timer + road playback (as mode 1) and `self._postrun_page.set_summary(
  self._episode.summary(), self._episode.rows(), champ, scenario)`.
- **Export menu** (new `File` menu): `Export CSV…` → `QFileDialog.getSaveFileName` →
  `write_episode_csv(self._episode.rows(), path)`; `Export PNG…` → `QFileDialog.getSaveFileName` →
  `self.grab().save(path)` (grabs whatever is on screen — "save what you see"). Both guard OSError
  and report success/failure in the status bar (like `_save_layout`).

### Non-goals / invariants

- **Frozen core untouched**: the accumulator only READS `StepResult`/`spikes` (additive), as the
  live metric docks do. No core change; single-vehicle golden stays bit-identical.
- **float-vs-fixed A/B deferred** (needs a fixed-point Qm.n forward — separate phase).
- Live mode unchanged; entering Post-run stops the live timer + road playback.

## Testing strategy

1. **EpisodeSummary** (pure, no Qt) — feed a synthetic StepResult/spikes sequence; assert
   `min_gap`/`min_ttc`/`max_decel`/`rms_accel`/`rms_jerk`/`mean_firing`/`peak_firing`/`collided`
   against hand-computed values; assert `snn_pj`/`ann_pj`/`advantage` signs (SNN < ANN) and
   `len(rows()) == n_ticks`.
2. **write_episode_csv** — rows → a temp CSV with the header + N data lines; round-trip parse.
3. **PostRunPage** (offscreen) — `set_summary(...)` fills the labels (a known value appears) and the
   two plots get the episode length.
4. **SimApp integration** (offscreen) — `_mode_stack.count() == 3`; `set_mode(2)` shows page 2, stops
   the live timer + road playback, and the report card shows the run's values after an `_advance`;
   the accumulator is fed during `_paint` (min_gap etc. non-trivial after a run); `select_scenario`
   resets it.
5. **Export wiring** — the CSV action writes a file with the episode rows; the PNG action calls
   `grab().save` to a path (assert the file exists / is non-empty). Use a temp path, no real dialog.
6. **Golden suite** — full sim list green; single-vehicle golden bit-identical.
7. **Render-verify** — Post-run page for a champion after a full episode (report card + summary plots
   populated); one CSV + one PNG exported and eyeballed.

## File map (delta)

- `sim/ui/episode.py` — **new** `EpisodeSummary` accumulator + `write_episode_csv`.
- `sim/ui/postrun_page.py` — **new** `PostRunPage` (report card + 2 summary plots).
- `sim/ui/app.py` — accumulator init/reset/update; 3rd mode wiring; `File → Export…` menu.
- Tests: `test_sim_episode.py` (**new**: accumulator + CSV), `test_sim_postrun.py` (**new**: page),
  `test_sim_ui_smoke.py` (3rd mode + export wiring).

## Implementation phases (for the plan)

- **P1** — `EpisodeSummary` accumulator + `write_episode_csv` (pure, TDD).
- **P2** — feed the accumulator from `SimApp._paint` (+ reset in `select_scenario`, rebuild on champion swap).
- **P3** — `PostRunPage` + wire the 3rd mode (`set_mode(2)` populates + stops timers).
- **P4** — `File → Export…` menu (CSV + PNG).
- **P5** — render-verify + full golden + docs/memory.
