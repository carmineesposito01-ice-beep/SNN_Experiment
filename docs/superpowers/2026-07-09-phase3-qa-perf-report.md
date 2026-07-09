# Phase 3 — Close-out QA + Performance Report

**Date:** 2026-07-09 · **Branch:** `Simulator` · commits up to `02efefc`

Multi-perspective review (two subagents: Python-quality + performance lens) + a real
`windows`-Qt frame-budget measurement, to close Phase 3.

## Performance profile (measured, cf_sim on this machine)

| What | Cost | Verdict |
|---|---|---|
| Pure sim step (`stepper.step`) | **10.7 ms/step** | Entirely `core/network`+`core/hardware` (po2 quantize) + torch — the **frozen model core**. Not optimizable without breaking golden. |
| `_redraw_series` (setData, 14 panels) | 19 ms | fine |
| Redraw+paint, Overview (14 docks) | 189 ms | paint-bound |
| Redraw+paint, Neuro-debug (12) | 209 ms | NetState graph (~1100 edges) is the heavy repaint |
| Redraw+paint, Guida (8) | 90 ms | ~11 fps |
| Redraw+paint, Identificazione (7) | 93 ms | — |
| `reconstruct_history` (600-tick episode) | **7.7 s** | = 600 × 10.7 ms step; inherent to the frozen core |

**Conclusions:** (1) the live frame is **paint-bound** — dominated by pyqtgraph repaint of the
*visible* plots, scaling with dock count; presets are the mitigation (use a focused preset live,
not Overview-with-14). (2) The step cost and the reconstruct time are fixed by the frozen model
core. (3) Data-prep waste (~3 ms/frame of redundant `params_matrix`/`spikes_matrix`/`arrays`
rebuilds) is real but a <3 % slice of a paint-bound frame.

## Fixes applied (commit `02efefc`)

1. **Top-down integrates every tick** (was `results[-1]` only) — at speed>1 (slider up to 8×) or a
   lagged frame, `SimLoop.tick` returns many `StepResult`s; the ego car under-advanced and jumped
   vs the scrub reconstruction. Now `_paint` loops `update_frame` over all results. **(correctness)**
2. **Scrub source reverts to live on Step** — after a deep-scrub reconstruction, `step_once`
   redrew from the live buffer but left `_src_probe` on the stale reconstruction. `_paint` now
   resets `_src` to live whenever the sim advances. **(correctness)**
3. **Reconstruct-on-pause cached + signalled** — cached by `(scenario, tick, #events)` so repeated
   pause/resume is instant; a `ricostruzione episodio…` status message covers the one-off compute.
4. **Home/End sync the cursor slider** (was rendering without moving the slider widget).
5. **`metrics.synops` delegates to `synops_series`** — single source of truth for the formula.
6. **`load_layout`** logs real restore failures (`logging.warning`, `exc_info`); still silently
   falls back to Overview only on the expected `FileNotFoundError`.
7. **Safety thresholds named** (`_TTC_REF_S=1.5`, `_DRAC_REF=3.35`) — no more bare magic numbers.
8. Earlier in the pass: **`SynOpsPanel` missing `layout.addWidget`** (blank dock) — fixed + guarded.

## Deferred (documented, not blocking) — future work

- **`SimApp.__init__` is ~98 lines** (SRP / >50-line bar). Working and fully tested; splitting into
  `_build_panels/_build_docks/_build_controls` is worthwhile hygiene but pure refactor risk during a
  close-out. Do it as a standalone task.
- **Data-prep de-duplication** (perf): 5 `ParamPanel`s each rebuild `probe.params_matrix()` and
  `SpikeRate`+`SynOps` each rebuild `spikes_matrix()` per frame. A version-counter memo on the
  `AttributeProbe` getters + `TrajectoryBuffer.arrays()` (invalidated in `record()`) would dedupe,
  bit-identically. ~3 ms/frame — only matters at speed 8; deferred because it touches the frozen
  `probe.py` and the frame is paint-bound anyway.
- **Visibility gating**: `_redraw_series` updates all 14 panels even when a preset hides most (Qt
  already skips *painting* hidden widgets, so this only saves setData/data-prep). Skip
  `update_frame` for docks not in `visible_docks(area)`, refresh on re-show.
- **Reconstruct prefix-splice**: only the pre-buffer ticks (`episode − 500`, ≤100 for these
  scenarios) actually need re-running; splicing the reconstructed prefix with the live buffer would
  cut the 7.7 s to ~1 s. Needs a clean probe/traj splice helper.
- **`EventTimelinePanel.update_events`** rebuilds the tick→idx dict and all `TextItem`s every frame;
  guard on `len(injector.log())` unchanged.
- **`NeuronGraphPanel._add_labels`** not idempotent (dormant — `set_topology` called once).
- **PEP8**: semicolon-chained statements in the constructor (style only).

## Optimization session (2026-07-09, commits `4aec6cf`..`<synops-energy pending>`)

Driven by a 5-agent workflow (3 paint/data-prep/scene lenses → synthesis → adversarial batch verify;
20 candidates → 9 ranked → verified). Implemented the verified, golden-safe wins (measured before→after):

- **#5 NetState freeze + LUT/pen reuse** — `disableAutoRange()`/`setMouseEnabled(False)` (layout static) +
  256-brush viridis LUT + singleton pens (no per-frame QPen/QBrush alloc). Per-paint: Overview 189→133 ms,
  Neuro-debug 209→173 ms, Guida 90→72 ms, Identificazione 93→70 ms.
- **#3 Throttle the heavy `_redraw_series` to ~15 fps** while running (physics + Road stay 30 fps; Step/pause
  unthrottled). Halves the heavy-repaint load; the sim/Road no longer stutter behind the plots.
- **#6 Version-memoized probe getters** (`_count` key, `record()` untouched) + `TrajectoryBuffer.arrays()` +
  `status_text` reads the last frame. Dedupes params_matrix×5 / spikes_matrix×3 / arrays×2 per redraw.
- **#7 EventTimeline** — skip the whole rebuild when unchanged (empty log / paused) + `TextItem` pool.
- **#8 Prefix-splice deep-scrub reconstruct** — re-run only the pre-buffer prefix (`episode−500` ticks) and
  splice with the live buffer. **7.7 s → 0.74 s (~10×)**; `spliced == full` regression test ships with it.

**Deferred (verifier-flagged low value):** #4 visibility-gating (Qt already skips hidden paints → marginal,
stale-data risk), #9 thin-skeleton toggle (subsumed by #1). **Available if wanted:** #1 rasterize the
NetState skeleton (~1100 edges) into a one-time `ImageItem` blit — the biggest remaining per-paint cut on
NetState-visible presets (Overview/Neuro-debug), but M-effort + fiddly image/extent alignment; not needed
for the felt-slowdown fix which #3+#5 deliver.

## Test / golden status

All sim tests green (~95); the frozen core stays **bit-identical** (stepper/backend/eventprop
goldens unchanged). New regression tests: topdown-integrates-all-ticks, step-after-reconstruct
reverts source, reconstruct-is-cached, `SynOpsPanel` plot-in-layout guard.
