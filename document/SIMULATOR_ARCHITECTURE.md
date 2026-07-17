# SIMULATOR_ARCHITECTURE.md — map of the parts

> **Purpose.** A cold-start anchor: what each part of the simulator is, how the data flows, and what
> must not move. Written from a full read of the source on **2026-07-16** (every `file:line` here was
> verified, not recalled). It complements `SIMULATOR_SESSION_RESUME.md` (which holds volatile STATE +
> pending actions); this file holds the durable SHAPE. When they disagree on state, the resume wins;
> when they disagree on shape, re-read the source and fix this file.
>
> **Why it exists.** Working from a stale mental model instead of the code produced a run of small
> avoidable errors (multi-line `replace()` failing silently, a grep "confirming" a string that lived in
> the wrong section). This map is the antidote: re-derive from here, then from source — never from memory.

---

## The spine (the one data path everything else hangs off)

```
ScenarioSpec  --materialise()-->  Scenario(v_leader: (600,))  --SimStepper.step()-->  StepResult (per tick)
  (blocks + neutral)                 via manual_scenario()          one v_leader sample consumed per tick
```

A scenario is **described** (a timeline of `Block`s + a `LeaderStyle` neutral), then **materialised** into
the 600-float `v_leader` the engine already eats. `manual_scenario()` is the door, so nothing downstream
learns a scenario was built rather than picked (`app.py:605` `_on_scenario_built` appends it like any other).

**The rule that shapes the model:** THE BLOCK SAYS WHAT, THE STYLE SAYS HOW. A `ramp` declares its target;
the style owns the RATE. `ticks` is the block's SLOT on the timeline, never a ramp's duration
(`scenario_spec.py:7-8`).

---

## Module map

### The frozen core — `sim/{state,stepper,backend,probe,events,eventprop_stepper}.py`

Bit-identical to `utils.closed_loop_eval.simulate()` and tested against it. **Do not touch** except with
explicit user consent on evidence (`events.py` was unfrozen once, in cycle 3, for the ramp fix).

| file | responsibility | key facts |
|---|---|---|
| `state.py` | `SimState` (mutable) + `StepResult` (immutable per-tick snapshot) | `StepResult` carries `t,s,v,vl,dv,a_ego,params,collided` — what every consumer reads |
| `stepper.py` | the single-step engine | `backend=None` → **oracle** (params = `params_gt` constant = the ghost). `:76` `a_l_raw=(vl_obs-vl_prev)/DT`. `:88` physics uses the **true** `vl`. `injector` can override the leader live |
| `backend.py` | wraps a champion | baseline → `model.forward_step`; eventprop → `EventPropStepper`. `read_probe`/`read_weights` feed the panels |
| `probe.py` | ring-buffer of hidden-state frames | decoupled from the stepper; `from_frames` splices for deep-scrub without re-running |
| `events.py` | the live-event injector | `brake_leader` ramps the leader from its **current effective** speed (the `:42` fix); `tick(t,base_vl)` is idempotent, which is why the ghost can share it |
| `eventprop_stepper.py` | stateful per-tick forward for the EventProp family | replicates the batch `_manual_forward` O(1)/step; golden vs `forward_sequence` |

### The scenario stack — where the builder lives

| file | responsibility | key facts |
|---|---|---|
| `sim/scenario.py` | `Scenario` dataclass + `scenario_library` + `manual_scenario` | thin wrapper over `build_scenarios`; carries exactly the `SimStepper` inputs |
| `sim/scenario_spec.py` | **PURE** model + materialiser + JSON | `_KINDS=(preset,const,ramp,sine,custom)`. `materialise(spec,pg,N)` threads `v` as each block's `v0` — blocks join continuously and never teleport. **A built scenario's length = the SUM of its block ticks** (the builder passes `N=sum`, one owner, no fixed cap to overflow — this was the "sine got eaten" bug). **Presets are CANONICAL at `_PRESET_N=600`** regardless of the scenario length (the cut-family scale with N), so a preset block never changes with the total length; presets max out at 600 samples. `effective_style(block,neutral)=clamp(neutral+bias)`. **`custom`** = `_custom_samples(speeds,n,v0)`, a linear `np.interp` polyline anchored at v0 (nodes are SPEEDS on a derived grid `_custom_node_ticks`, clipped to `V_RANGE`). **`physics_gap(v,neutral)`** = the advisory (mask over `diff(v)/DT` vs the neutral). **`block_of_sample(spec,N)`** = per-sample owning-block index, replaying materialise's exact layout (for the advisory's custom-only attribution) |
| `sim/scenario_export.py` | **PURE** — leader-kinematics export (item 2) | `leader_kinematics(scenario)` → `{t, v_leader, x_leader, a_leader}`; `x_leader = s_init + DT·Σ v_leader` (forward Euler, faithful to `stepper.py:88`) so `gap = x_leader − x_ego`; `a_leader = diff(v)/DT` (= `a_l_raw`). `write_scenario_csv` (commented metadata + 4 cols) and `write_scenario_mat` (via `mat_writer`). Exports the scenario DEFINITION for downstream closed-loop — NOT the ego run (that is `File → Export CSV`, the episode) |
| `sim/mat_writer.py` | **PURE, no scipy** — a tiny MAT v5 writer (item 2) | `write_mat(path, {name: array\|scalar\|str})` → Level-5 top-level variables (MATLAB `load` binds each). scipy is absent (LAPACK/OMP #15). The isolated binary-format unit: tested alone with a paired reader + spec-byte assertions (header magic, `miMATRIX=14`, class byte) so the round-trip can't be self-consistently wrong. Char = `miUINT16=4`, double = `mxDOUBLE_CLASS=6` |
| `sim/jitter.py` | **PURE** — seeded type-preserving jitter (7a) | `jitter_spec(spec, rng, strength)` nudges each block's OWN knobs (`const→v`, `ramp→to_v`, `sine→amp/period`, `custom→nodes`, all→`ticks`) + the neutral style → the scenario keeps its SHAPE and TYPE (a sine stays a sine); blurring the 600-float `v_leader` would preserve neither. A `preset` block has **no numeric knob** (verbatim, hardcoded rng) → only `ticks` moves it; the preset family's variety comes from `jitter_params_gt` (`v_set=0.7·v0` scales the whole profile). **strength=0 = the IDENTITY** (multiplier exactly 1.0, clips are no-ops) — the degenerate case that proves jitter is the only source of variation. Bounds imported from `data.generator._PHYS_BOUNDS`, never duplicated |
| `sim/dataset_mix.py` | **PURE** — the mix + exact quotas (7a) | `MixEntry(family, source, weight)` over `FAMILIES=("built","preset","generator")`; `quotas()` gives **exact** counts (largest remainder), so 30% of 100 is exactly 30 and 1/3+1/3+1/3 of 100 is 33/33/34 — no trajectory lost to rounding. "Percentage" for a controlled dataset means a count, not an expectation |
| `sim/export_formats.py` | **PURE** — the format registry (7a) | `FORMATS = {name: FormatSpec(writer, bytes_per_tick, available, reason)}` = the **single source of truth**; the UI renders its checkboxes FROM it, so no hardcoded list can diverge. csv/mat reuse item 2's writers; json is stdlib; **xlsx is hand-rolled** (a zip of XML via `zipfile` — same school as the MAT v5 writer, easier: text not binary). `parquet`/`hdf5` are **registered but disabled** (`richiede pyarrow`/`richiede h5py`): both are COMPILED libs and this env has a known OMP fragility (torch already brings one) — declaring + explaining beats risking a green suite. `bytes_per_tick` **measured, not guessed**: csv 100.7 · mat 33.5 · json 70.0 · xlsx 31.6, pinned by a test that re-measures within 10% |
| `sim/dataset_gen.py` | **PURE** — the 3-family sampler + batch (7a) | `draw_scenario(family, source, seed, strength, specs, params_gt) → Scenario` is the one funnel: built→`jitter_spec`+`materialise` (its own length) · preset→`jitter_params_gt`+`materialise` of a one-preset-block spec (600) · generator→**`_leader_profile` called READ-ONLY** from `data/generator.py`. `preview_sample` (the eye's curve — ONE representative sample where the scenario is a distribution). `decimate(kin,k)` — the physics is ALWAYS 10 Hz; the export subsamples and **recomputes `a_leader` at `dt_out`** (the 0.2 s acceleration is not the 0.1 s one); no upsampling. `generate_dataset` writes the files + `manifest.json`; same seed → identical dataset |
| `sim/train_mix.py` | **PURE** — the TRAINING mix (7b) | `TrainMixEntry(family, source, **regime**, weight)` over `FAMILIES_TRAIN=("built","preset","generator","cut_in")` and `REGIMES=(highway/urban/truck/mixed/freeflow/launch)`. The extra axis vs 7a: the **regime gives the params, and the params ARE the labels**. `cut_in` is a **family** (an exact row), not a hidden `0.20` dice roll. Reuses 7a's `quotas()` via an **additive `families=` parameter** on `validate_mix`/`quotas` — a trap, because `quotas()` calls `validate_mix()` internally and that rejected any family outside 7a's three; the default keeps all 13 existing call sites byte-identical |
| `sim/train_gen.py` | **PURE** — the training sink (7b) | `draw_training_sample(entry, seed, strength, specs) → the 8-key dict train.py's CFDataset eats`. **Two rules:** the regime forces `_sample_scenario(rng, {regime:1.0}, 0.0)` **VERBATIM** (ranges can't drift from the champions'); the family gives the leader — built/preset **inject** a materialised `v_leader` (Task-2's new param), generator/cut_in take the **untouched standard path** (so a mix of only those reproduces the standard dataset). `scenario`=the **regime name** (or `train.py:1428` warns); `leader_family`/`leader_source` ride as additive keys CFDataset ignores. Refuses `L<300` **loudly** (below it CFDataset yields ZERO windows silently). `validate_train_mix` refuses an unknown **source** for generator/cut_in by name (`_leader_profile` has no `else`→a typo would return all-zeros silently — a final-review catch; built/preset already fail loudly on a bad source). `windows_per_traj` is **pinned against the REAL CFDataset** (the user weights trajectories, training eats windows; share depends on stride, train `//2` ≠ val). `build_training_cache` → two i.i.d. batches (seed S / S+1) → the `.pt` cache `train.py --data_cache` reads unchanged; **cancel writes NOTHING**; mode-2 gate checks the PROPERTY (no shared leader), not the `jitter>0` proxy. `SECONDS_PER_TRAJ` for the UI's ETA is a constant, **not test-pinned** (it measures the machine) |
| `sim/ui/drag_handles.py` | **Qt only** — the node-drag unit (cycle 4b) | `DragHandles`: a row of `pg.TargetItem` vertically-constrained (reconnect x in `sigPositionChanged`, converges in 2), y clamped to `V_RANGE`; `set_speeds` silent, a drag notifies once. Isolated + tested alone because the drag is the one measured-risk piece |
| `sim/ui/duration_handles.py` | **Qt only** — the duration-drag unit (builder-UX) | `DurationHandles`: a row of x-draggable `pg.InfiniteLine`s, one per block's right edge. **Commit-on-finish** (`on_resize` fires on `sigPositionChangeFinished`, not continuously) so re-placing the lines never destroys the one under the cursor and no value↔handle loop forms; `setBounds` caps in place. Isolated + tested alone |
| `sim/ui/scenario_preview.py` | **Qt only** — the cockpit's Scenario dock (item 1) | `ScenarioPreviewPanel`: the running scenario's whole `v_leader` as a static orange curve (`set_scenario`, drawn once) + a white dashed **tick marker** (`set_marker(tick)`, `None`=hidden). Own `InfiniteLine`, isolated + tested alone. **Driven by the current TICK from two app sites only** — `_paint` (live head `_last_result.t`) and `_render_at_cursor` (scrub `frames[idx].t`); deliberately NOT in `_ts_panels` (that group gets a buffer index) and NOT via `_redraw_series` (its paused-context callers would pin the marker to the head). **Y-view floored to `_MIN_Y_SPAN` (15 m/s)** so a narrow-band scenario (e.g. 'following' = v_set+N(0,0.3), a ~2 m/s band) reads as a near-flat cruise instead of the autorange zooming in and amplifying jitter; wider scenarios fit their own data (bottom clamped to ≥0). Shows the PLANNED leader — an injected brake overrides the leader live and does NOT appear here (it shows in Trajectory/Road) |
| `sim/ui/scenario_page.py` | **Qt only** — the composer (cycles 4a/4b/builder-UX) | the WIDGETS own the composed block's params (no shadow dict); for `custom` the widget IS the row of handles (`_params_for` returns a TUPLE, the JSON canonical form). The PAD owns the block's point, distance-from-neutral IS the bias; it dies on preset AND custom; neither records a bias. The advisory is a red overlay (`#ff2d2d`, NaN + `connect="finite"`) — composer preview (all segments) + scenario curve (custom segments only, via `block_of_sample`); base curves orange. **Duration edges** (`DurationHandles`): `_composer_edge` (writes `_ticks`, the single owner) + `_boundaries` (one per block, resizes `_spec.blocks[i]`, syncs `_ticks` if that row is open). **Frozen autorange**: `_refresh_composer(refit=…)` — the node drag passes `refit=False` (no re-fit → no jump), every structural change re-fits via `_refit_composer` |
| `sim/ui/dataset_page.py` | **Qt only** — the 5th mode, the Dataset builder (7a plan B) | The mix is **rows of real widgets** (`_Row`), not a `QTableWidget` — every cell is already an interactive control (two cascading combos, a spin, an eye, a ✕) and a table would mean a delegate per column to get back what a widget row gives for free. The family→source combo **cascades** (`built`→`_specs` from the app, `preset`→library names, `generator`→`GENERATOR_PROFILES`); `built` is **disabled with a tooltip saying where to go build one** when no spec exists. The quota column is LIVE (`quotas()` on every edit) and Generate is **gated on total==100%** — the gate does double duty: it enables the button AND it keeps `quotas()`, which validates and raises, from being called on an invalid mix mid-refresh. Format checkboxes are **rendered FROM `FORMATS`** (unavailable → disabled + `reason` in the tooltip), so the UI cannot drift from the registry. The eye's popup draws `preview_sample` at a **fixed `PREVIEW_SEED`** and the title says *"campione"* — for a jittered/generator family the source is a DISTRIBUTION and showing one curve as "the" scenario would lie. The page only **exposes getters** (`mix/count/seed/strength/k/formats/out_dir`); the APP owns the run — the same split as Meso (`app.py:174`) |

### The invariant — `utils/closed_loop_eval.py`

**INVARIANT by the contract in its own docstring** — the reports run on it. `build_scenarios` (`:332`)
produces the 9 presets; `simulate` (`:139`) is what `SimStepper` mirrors bit-for-bit; `safety_metrics`
(`:228`) computes `brake_margin` (`:241`, `min<0` = "collision physically unavoidable"). `B_MAX=9` (`:22`).

The false-red facts every advisory feature must respect (verified from these lines):
- `cut_in`: `vl[t_cut:]=0.45·v0` (`:367`) — a jump because the leader **is a different vehicle**, not a manoeuvre.
- `following`: `vl=v_set+rng.normal(0,0.3)` (`:347`) — ~4 m/s² of noise typically, ±13 in the tail.
- `panic_stop`/`hard_brake` brake at `-9`/`-7` but the `max(0,…)` clamp (`:399,359`) stops them at 0 in ~24/~30 ticks — that is why only ~24/~30 samples "violate".

### The periphery — not on the spine, one line each

`app.py` (~800) wires the **5 modes** (Live · Meso/Macro · Post-run · Scenari · **Dataset**) + selector (+ its
"⋯" export/delete menu, `_protected_count` guards the Meso-indexed library) + deep-scrub + champion loading.
Two app-level facts the Dataset mode rests on: **`sigScenarioBuilt` carries `(scenario, spec)`** and the app
keeps **`self._specs` PARALLEL to `self._scenarios`** (`None` for the library + the initial manual one, the
recipe for anything built) — a materialised `v_leader` cannot be jittered back into a *sine that is still a
sine*, so the recipe is what the `built` family needs; `_delete_scenario` pops **both** lists or they desync.
`set_mode(4)` re-reads `_built_specs()` so a scenario built after entering the mode is not invisible.
`panels.py` (~570) the live
dock panels (the **Events** dock is GONE — hard-replaced by the Scenario preview in item 1; `EventInjector` +
the Brake button stay, only the visual event log went); `topdown.py`/`loop.py`/`reconstruct.py` the road +
ghost + scrub; `meso_*`/`postrun_page.py`
the other three modes; `layout.py`/`theme.py`/`replay.py`/`metrics.py`/`platoon.py`/`episode.py` support.

---

## The scenario builder internals (cycle 4a — what future work extends)

The right panel is a **composer**: build one block while watching it, then Add. Two owners, only two:

1. **The widgets own the params.** `_params_for(kind)` reads the kind/ticks/value/preset/period widgets
   directly — never a dict beside them. A shadow dict was tried in the 4a plan and measured to crash
   (`KeyError` on a kind change) and to silently rewrite a reopened block; deleted.
2. **The pad owns the block's point.** The bright dot is THIS block; the dim dot is the neutral; the
   distance between them IS the bias. `_composer_bias()` (`:264`) returns the difference.

Load-bearing behaviours (each has a teeth test):
- The small preview materialises a **one-block spec** starting from `_start_speed(upto)` — the speed the
  previous blocks leave behind. That coupling is the only thing making it honest instead of decorative.
- The pad **dies** on a preset (`_on_kind_changed:232`) — a verbatim profile ignores the style, so a live
  pad would be a lie; the dot goes graphite (`StylePad.setEnabled:85`) because the dot is the claim.
- The neutral has its **own** control (`_neu_a/_neu_b`); moving it carries every block, because the bias
  is a difference (`_on_neutral_changed:315`).

**Known one-computation-two-names:** `const` and `ramp` both call `_rate_limited_toward(v0,target,n,style)`
with identical arguments (`_block_samples:114-117`) — only the param key differs. The menu offers 4 kinds
of which 2 are one. Untouched (removing a kind breaks existing JSON); any test assuming a ramp↔const kind
change moves the curve will fail for the wrong reason.

---

## The advisory is grounded, not decorative

A physics advisory (cycle 4b) computes `diff(v_leader)/DT` and compares it to the neutral's `(a_max,b_max)`.
That quantity is **exactly** `a_l_raw` at `stepper.py:76` (and `simulate:189`) — the leader acceleration the
engine itself reads. And `(a_max,b_max)` genuinely IS the leader's rate limit (`_rate_limited_toward` uses
it), so "does the drawn curve exceed the leader's own rate" is the right question. The red is the same
arithmetic the physics runs, not a UI approximation.

Attribution on the scenario curve must use materialise's **real** layout, not `cumsum(ticks)`: the last
block truncates at N and a flat tail follows. Expose the per-sample owning-block index from the pure module;
a segment `k` is eligible for red iff sample `k+1` is owned by a `custom` block.

---

## Tests + the runner gotcha

**371 across 37 files** (36 `test_sim_*.py` + `tests/test_champion_io.py`); **371 green** at end of 7b plan A
(the training-sink engine; +26 over 7a, incl. a final-review fix). The pure units (`scenario_export`, `mat_writer`, `jitter`, `dataset_mix`,
`export_formats`, `dataset_gen`) are tested without Qt. Two tests earn their keep by construction:
`test_sim_scenario_export.py`'s causal `x_leader` == stepper-gap check, and `test_sim_dataset_gen.py`'s
`test_the_generator_family_is_the_REAL_training_randomisation` — a plausible-looking constant profile passes
every other test and only that one catches it.

**`data/generator.py` is the champions' training-data provenance** (`train.py` imports it; `Arch_Tested/README.md:63`
calls it *"shared (intero)"*; a copy is archived in `Arch_Tested/R24F_MIXED_.../data/generator.py`). 7a only ever
**called** it (`_leader_profile`, `_PHYS_BOUNDS`, read-only). **7b MODIFIES it** — `simulate_trajectory` gained a
`v_leader=None` parameter (additive, default-off, the `wide_params=False` mould already in the file), so a built
leader can reach the real physics. ⚠️ **The invariant therefore changed shape:** for this file the gate is NOT an
empty `git diff` (it is deliberately non-empty) but **`tests/test_sim_provenance.py`** — it proves, by comparing
OUTPUT not text, that the live generator still reproduces the champion's dataset byte-for-byte (8/8, both branches,
dtype included) despite the edit. That is a stronger gate than a diff, and it is why the change was safe. Measured
fact behind it: the live file is already 56 lines ahead of every archived copy (the `launch`/`freeflow` additions),
all additive and default-off, and provenance still holds. `parse_scenario_mix` weights driver REGIMES
(highway/urban/truck/…) — the same vocabulary 7b's regime axis now uses, reached VERBATIM via
`_sample_scenario(rng, {regime:1.0}, 0.0)` rather than copied. `test_sim_ui_smoke.py` alone is ~90 tests;
`test_sim_drag_handles.py`, `test_sim_duration_handles.py`, and `test_sim_scenario_preview.py` are the isolated UI
units (node drag / duration drag / scenario preview).

**The suite is the SIM glob — `pytest tests/test_sim_*.py tests/test_champion_io.py`, NOT `pytest tests/`.**
The `tests/` dir also holds FPGA-track scripts (`test_fpga_io.py` calls `sys.exit()` at import) that abort
pytest collection with `INTERNALERROR> SystemExit`. Those files belong to another track; not ours to fix.

Runner — **never** `conda run -n cf_sim python -m pytest` (crashes conda's plugin system intermittently):

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

⚠️ The full suite takes **~3–4 minutes** (many tests build `SimApp` with the champion). A 2-minute default
timeout **looks like a hang and is not one** — give it ≥420 s or run it in the background.

⚠️ **Do not run anything else while the suite runs.** `test_custom_composer_refresh_fits_in_a_frame` asserts a
wall-clock PEAK (< 16.7 ms over 40 drags) — it measures the machine, not just the code. Running a render script
in parallel with the suite reddened it once (7a plan B) on a diff that cannot touch the composer's drag path.
A red budget test with an innocent diff means **re-measure quiet first**, then believe it.

⚠️ No LAPACK in `cf_sim` (`matrix_rank`/`polyfit`/`lstsq`/SVD → OMP #15 hard abort). Render-verify with
`QT_QPA_PLATFORM=windows` (offscreen renders text as tofu).

---

## What `custom` cost (cycle 4b), as built

- **`scenario_spec.py`** (+62): `_KINDS += "custom"`, `_custom_samples`/`_custom_node_ticks`, a
  `_block_samples` branch, `physics_gap`, `block_of_sample`, JSON (custom params round-trip as a **tuple**).
- **`sim/ui/drag_handles.py`** (new, 59): the isolated drag unit.
- **`scenario_page.py`** (+107): the handles wired in, the advisory overlay on two plots, a node-count
  spinbox, `kind in ("preset","custom")` generalisations, orange base curves.
- **`app.py`**: **nothing** — a built custom flows through `_on_scenario_built` like any scenario.
- **`to_json`/`from_json`** have **no Save/Load UI hook** — test-only surface today.
- **Core + `closed_loop_eval.py`**: untouched (empty diff), `materialise` unchanged.

---

## Known debt (durable, out of any single cycle)

- `ReplayLog.seed` fed the scenario index (`app.py:591`).
- The Meso page passes `_PARAMS_GT` instead of `sc.params_gt` (`app.py:383`).
- `const` == `ramp` (one computation, two names) — flagged above, deliberately untouched.
- A leader with its own dynamics — parked, resolved the other way (the animator + advisory keep physics honest).
