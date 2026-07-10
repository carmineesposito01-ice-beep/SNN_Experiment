# Post-run: exhaustive metrics + '?' tooltips — Design Spec

**Date:** 2026-07-10 · **Branch/worktree:** `Simulator` · **Status:** design approved (user) → spec

## Goal

Enrich the Post-run report card with the **single-episode-computable** subset of the checkpoint-trio
metrics (VALIDATION_REPORT_v3 + FPGA_REPORT), and add a **'?' hover tooltip** on every metric giving
its definition + formula. Faithful to the reports: **reuse the project's validated metric functions**,
do NOT reinvent formulas — especially for energy (a documented source of past inconsistency).

## Established facts (verified in code)

- **Reused validated functions** (all LAPACK-free; `utils.closed_loop_eval` is already imported by the
  sim via `sim/scenario.py`, so importing more from it adds no risk):
  - `closed_loop_eval.safety_metrics(traj)` → `min_gap, min_ttc, TET, TIT, max_DRAC, TED_drac, TID_drac,
    brake_margin_min = min(s − max(0,dv)²/(2·B_MAX)), impact_dv, frac_ttc_below_*` (+ constants
    `TTC_STAR, DRAC_STAR, B_MAX` reused, not hardcoded).
  - `closed_loop_eval.comfort_metrics(traj)` → `rms_accel, max_decel, rms_jerk, frac_decel_iso_viol
    (a < −3.5), frac_accel_iso_viol (a > +2.0)` (ISO 15622).
  - both take a `traj` dict of arrays: `s, dv, v, a_ego, collided, min_gap, impact_dv`.
- **Identification** — per-param RMSE vs the scenario's true constants: `param_rmse_i = sqrt(mean((pred_i −
  gt_i)²))` for `v0,T,s0,a,b` (the pattern of `utils/simulator/metrics.py`). The sim has both: predictions
  (`StepResult.params`, per tick) and ground truth (`scenario.params_gt`).
- **ρ(U·V) spectral radius** — `net_diagnostics.recurrence_spectral` computes it with
  `np.linalg.eigvals` + `svd` = **LAPACK → OMP #15 abort in cf_sim**. → compute ρ **LAPACK-free via power
  iteration** on `W = po2(rec_U) @ po2(rec_V)` (torch matmuls; `core.hardware.po2_quantize` for the po2
  weights, same as `recurrence_spectral`). Static per champion (episode-independent).
- **dead_frac** — `net_diagnostics.spike_stats` derives it from a per-internal-tick raster
  (`spike_raster`, `T·n_ticks` rows). ⚠️ that is a DIFFERENT spike path from the live docks. To stay
  consistent (see Energy §), the post-run computes dead_frac from the **per-real-step probe spikes**
  (a neuron is dead if it never fired in any real step) — the same representation the SpikeRate/NetState/
  SynOps docks use.
- **Energy** — `metrics.synops(spikes_row, n_in, n_hid, n_out, rank)` (static + dynamic SynOps per real
  step) and `metrics.ann_mac(n_in, n_hid, n_out)` (dense-RNN MACs/step), with `E_AC_PJ=0.9, E_MAC_PJ=4.6`.
  This is the path the live SynOps dock uses, faithful to the corrected FPGA scorecard.

## Energy — consistency & caveats (⚠️ the documented "magagna")

Past reports had a **double-`n_ticks`-normalization bug** that inflated the advantage to 22–30×; the
corrected figure is ~5–15×, and the advantage comes from **AC < MAC (accumulate vs multiply-accumulate),
NOT from sparsity** (the net fires ~13–21%, not ~1–2%). To avoid reintroducing any inconsistency:

1. **One energy path, reused verbatim.** The post-run computes energy with the SAME
   `metrics.synops`/`ann_mac` on the SAME **per-real-step probe spikes** the live SynOps dock uses. No
   parallel/re-derived calculation, no `n_ticks` division. `snn_pj = Σ_step (static+dynamic)·E_AC`,
   `ann_pj = n_steps · ann_mac · E_MAC`, `advantage = ann_pj / snn_pj`.
2. **Consistency invariant (tested).** For a given champion + episode, the post-run's SNN pJ / advantage
   must EQUAL what `SynOpsPanel` accumulates over the same steps (both call `metrics.synops`). A test
   asserts this equality.
3. **Breakdown decomposes the SAME total.** `fc = Σ static`, `rec_V = Σ s·rank`, `rec_U = Σ (H·rank if
   any spike)`, `out = Σ s·OUT` — sums to `Σ(static+dynamic)`. No independent estimate.
4. **Honest tooltip.** The energy '?' states: advantage from AC<MAC (not sparsity); baseline = dense RNN
   with FULL H·H recurrence (`ann_mac`); per-real-step op-count (no double-`n_ticks`); the net fires
   ~15%; the number varies typical-vs-worst-case. No overclaiming.

## Design

### ① EpisodeSummary v2 (`sim/ui/episode.py`)

Extend the accumulator to **keep the episode arrays** (already has per-tick rows; add a spikes list
`T×H`) and compute the richer summary at read time by REUSING the validated functions:

- `__init__(dims, params_gt=None, model=None)` — `params_gt` (scenario truth) for identification;
  `model` to precompute ρ (LAPACK-free power iteration, once).
- `update(r, spikes)` — unchanged core + append `spikes` to a kept list; keep incremental `synops_total`
  + the 4 energy components (fc/rec_V/rec_U/out) + a dead-mask (OR of per-step spikes).
- `summary()` — builds `traj = {s,dv,v,a_ego,collided,min_gap,impact_dv}` from the kept arrays, then:
  - `**safety_metrics(traj)**` + `**comfort_metrics(traj)**` (reused, verbatim formulas).
  - identification: `param_rmse_i` + `param_mean_i` vs `params_gt`; overall `id_accuracy =
    100·max(0, 1 − mean_i(param_rmse_i / |gt_i|))` (documented in the tooltip).
  - network: `mean/peak firing`, `dead_pct` (from the dead-mask), `max_spikes_tick`, `rho`.
  - energy: `snn_pj, ann_pj, advantage` + breakdown (as above) — the ONE reused path.
- `rows()` — extended CSV columns unchanged in spirit (per-tick), plus the summary is exported too.
- `impact_dv` handling: track the closing dv at the collision step (matches `closed_loop_eval`).

`spectral_radius_po2(model)` (new helper, in `episode.py` or `metrics.py`): power iteration on
`W = po2(rec_U) @ po2(rec_V)` (torch), ~50 iters, returns `float(ρ)`; returns `None` if the model has no
low-rank recurrence.

### ② PostRunPage v2 (`sim/ui/postrun_page.py`)

Groups (each row: `label   value   [?]`):
- **Identificazione**: NRMSE/accuracy overall + per-param (v0/T/s0/a/b) error.
- **Sicurezza**: min gap · min TTC · brake-margin · max DRAC · TET/TIT · impact-Δv.
- **Comfort**: RMS accel · max decel · RMS jerk · frac-ISO (decel/accel).
- **Salute rete / FPGA**: firing medio/picco · dead % · spike max/tick · **ρ(U·V)** (verdict
  contrattivo ρ<1 / espansivo ρ>1, coloured).
- **Efficienza**: energia SNN · energia ANN · vantaggio× · breakdown (fc/rec_V/rec_U/out).

Each metric gets a small **`?` QLabel** with `setToolTip(html)` = a definition + the formula, grounded in
HOW_IT_WORKS_v3 / the two reports. Tooltip texts live in a `_METRIC_HELP` dict (`{key: html}`) so they
are testable (assert non-empty + contains the formula token). The two summary plots (v(t), gap(t)) stay.

### ③ CSV export

The per-tick CSV is unchanged (already exported). The summary dict (all aggregates) is additionally
written as a header block / a second `episode_summary.csv` on export (key,value rows) so the report card
is exportable too.

## Non-goals / invariants

- **Frozen core untouched** (all reused functions READ arrays/weights; ρ reads po2 weights). No core change.
- **NO numpy LAPACK** in cf_sim: ρ via power iteration (not eigvals/svd); everything else is arithmetic.
- **Energy: one reused path** (see Energy §) — post-run advantage == SynOps dock advantage (tested).
- Deferred still deferred: dataset-level (collision rate, stratified NRMSE), traffic (Meso page), V2X,
  fixed-point/quantization (needs the Qm.n forward = the A/B piece), FPGA-synthesis (LUT/DSP/timing/SEU).

## Testing strategy

1. **EpisodeSummary v2** — synthetic StepResult/spikes + `params_gt`: assert `param_rmse`, safety keys
   (`brake_margin_min`, `TET`, `max_DRAC`, `impact_dv`) match hand/`safety_metrics` values; `dead_pct`
   from a mask with a never-firing neuron; `rho` finite for a low-rank model.
2. **Energy consistency (⚠️)** — over the same episode, `EpisodeSummary` `snn_pj`/`advantage` equals a
   direct `Σ metrics.synops(...)`·E_AC (same as the SynOps dock); breakdown sums to the total.
3. **ρ LAPACK-free** — `spectral_radius_po2` matches the **documented report values** within tolerance —
   Raffaello ρ≈2.99, Donatello ρ≈0.05 (VALIDATION §9.3 / FPGA §0) — and is arithmetic/torch only (no
   `np.linalg.eigvals`/`svd`, which would abort with OMP #15 in cf_sim). These known values are the
   reference (they were produced offline by `recurrence_spectral`, which we cannot run in cf_sim).
4. **PostRunPage v2** — `set_summary` fills the new groups; every metric has a non-empty tooltip
   containing its formula token; per-param rows present.
5. **App integration** — after a run, `set_mode(2)` shows the full card; export writes the summary CSV.
6. **Golden suite** — full sim list green; single-vehicle golden bit-identical.
7. **Render-verify** — Post-run v2 for a BPTT (Raffaello, ρ>1) and an EventProp (Donatello, ρ<1) episode;
   confirm ρ verdict, identification error, safety SSM, and that the energy advantage matches the dock.

## File map (delta)

- `sim/ui/episode.py` — extend `EpisodeSummary` (keep arrays/spikes; reuse safety/comfort; identification;
  dead/spike stats; energy breakdown) + `spectral_radius_po2`.
- `sim/ui/postrun_page.py` — v2 groups + per-param rows + `_METRIC_HELP` tooltips + `?` labels.
- `sim/ui/app.py` — pass `params_gt` + `model` to `EpisodeSummary`; export the summary CSV.
- Tests: `test_sim_episode.py` (extend: safety/comfort reuse, identification, dead, ρ, energy consistency),
  `test_sim_postrun.py` (extend: groups + tooltips), `test_sim_ui_smoke.py` (summary export).

## Implementation phases (for the plan)

- **Q1** — `spectral_radius_po2` (LAPACK-free ρ) + test vs an offline reference.
- **Q2** — `EpisodeSummary` v2: keep arrays/spikes; reuse `safety_metrics`/`comfort_metrics`;
  identification vs GT; dead/spike; energy breakdown + **consistency test**.
- **Q3** — `PostRunPage` v2 groups + per-param + `_METRIC_HELP` `?` tooltips.
- **Q4** — app wiring (`params_gt`/`model` into the accumulator) + summary CSV export.
- **Q5** — render-verify (BPTT ρ>1 + EventProp ρ<1) + full golden + docs/memory.
