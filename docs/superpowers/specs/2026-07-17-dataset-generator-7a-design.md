# Dataset generator — 7a: engine + analysis export — Design Spec

**Date:** 2026-07-17 · **Branch/worktree:** `Simulator` · **Status:** ✅ **FINAL — approved.** Supersedes the
combined DRAFT (`2026-07-16-dataset-generator-DRAFT.md`); its training-sink half survives as
`2026-07-17-dataset-generator-7b-DRAFT.md`. Grounded on a full read of the source on 2026-07-17 (every
`file:line` verified, not recalled).

## Goal

A 5th **"Dataset"** mode: pick a **percentage mix** of scenarios (across three families), a **seed**, a
**count**, and a **jitter strength** → generate that many randomised trajectories, each "of the same type" as
its source → export them (multi-format) plus a **manifest**.

User's item 7: *"partendo da uno scenario, creare un dataset di molte traiettorie, ottenute come
'casualizzazione' di quella creata (con qualche seed che va a modificarle quanto basta per essere della stessa
tipologia), oppure una impostazione che ti permetta di decidere la percentuale di ciascun scenario esistente
(compresi quelli creati) e poi su quelli applichi randomizzazione … un dataset generato dalla massima
personalizzazione."* Mix families, clarified by the user: *"su tutte le tipologie costruite, preset, ma anche
quelle fatte nel generatore di traiettorie usate nel training della rete (generator.py)."*

## Scope decision — 7a / 7b

The user wants the dataset usable by **both** an external consumer (MATLAB/analysis) **and**, eventually, SNN
training. Those are different subsystems (different format, different physics, different risk), sharing only
the sampling engine. **Decomposed** (user-approved):

- **7a (this spec)** — the engine (mix + jitter + seed + count + manifest) **+ the analysis sink** (leader
  kinematics via item 2's writers). No invariant modified. Working software on its own.
- **7b (a later cycle)** — the **training sink**: the `(N,7)` contract + `generator.py`'s ACC-IDM/OU/packet-loss
  physics. Carries its own risk decision (see the 7b draft). Built on 7a's engine.

## Established facts (grounded, verified 2026-07-17)

- **`data/generator.py` is a training-pipeline invariant in practice.** `train.py` imports
  `generate_dataset, print_dataset_stats, parse_scenario_mix`; `Arch_Tested/README.md:63` calls it
  *"shared (intero)"*; the champion `Arch_Tested/R24F_MIXED_.../data/generator.py` is a **frozen copy** — it is
  the provenance of the data the champions were trained on. **We CALL it, we never MODIFY it.** (Precedent for
  importing its privates: `Dynamic_Study_L1_6.ipynb` does `from data.generator import _sample_scenario,
  parse_scenario_mix`.)
- **`_leader_profile(profile, N, dt, rng, v0)`** (`data/generator.py:179-245`) is **pure and fully
  parametric**: it takes OUR `N`, OUR `dt`, OUR seeded `rng`, and returns `v_l` (float32, length N). Profiles:
  `constant · sinusoidal · stop_and_go · free · launch`, each with its own seeded jitter (base, amp, freq,
  cycle_len, a_launch). **This IS the training randomisation, reusable read-only.**
- **`parse_scenario_mix` weights a DIFFERENT axis** than the user's: its vocabulary is the driver/environment
  regime (`highway, urban, truck, mixed, freeflow, launch` — `generator.py:493`), which then *derives* a leader
  profile (`_sample_scenario:538-581`). The user's "scenari esistenti" are the SIMULATOR's (library + built).
  The two vocabularies overlap in name only. **We do not reuse `parse_scenario_mix`.**
- **Presets have no jitterable knob.** `_preset_samples` (`sim/scenario_spec.py:100-104`) returns
  `lib[name].v_leader[:n]` **verbatim**, built with a **hardcoded `rng=default_rng(0)`**, ignoring the style.
  Its only sensitivities are `params_gt` (`v_set = 0.7·v0` in `closed_loop_eval:341` scales the whole profile;
  `s_init` via `_equilibrium_init`) and `n` (truncation). → presets are jittered **through `params_gt`**.
- **The app does not retain built scenarios' specs.** `sigScenarioBuilt` emits the *materialised* `Scenario`
  (`scenario_page.py:522`); the `ScenarioSpec` lives only in the builder's `self._spec`. Without the spec there
  are **no blocks to jitter** → §"Spec retention".
- **`DT = 0.1` is the V2X 10 Hz rate** (`config.py:63`, *"allineato a V2X 10 Hz"*), hardcoded into the frozen
  core and `closed_loop_eval` (actuator lag `exp(-DT/τ)` `:49`, jerk limit `jmax·DT` `:62`, gap integration
  `:104`) and into `materialise` (rate limit `step = rate·DT` `scenario_spec.py:79`; sine amplitude clamp
  `amp_max = rate·period·DT/2π` `:120`). **Generation frequency is not a knob** → §"Frequency".
- **Export dependencies, verified in `cf_sim`:** `json` present (stdlib); **`openpyxl`, `xlsxwriter`,
  `pyarrow`, `fastparquet`, `h5py`, `tables`, `pandas` ALL ABSENT**; `numpy 2.5.1`, `torch 2.12.0+cpu` present.
- **Measured export sizes** (item 2 functional-verify, N=600): CSV **60 438 B** (~100.7 B/tick), MAT
  **20 072 B** (~33.5 B/tick). Both scale linearly in N → the size estimate is a calibrated linear formula.

## Design

### 1 · One product, three families

`(family, source, seed) → Scenario`. Each family randomises its own way; all yield a `v_leader` + metadata, so
nothing downstream knows the origin.

| family | randomisation | natural length |
|---|---|---|
| **built** | seeded jitter of the block params (`to_v, v, amp, period, nodes, ticks`) + the neutral `a_max/b_max` → `materialise` | sum of its blocks |
| **preset** | seeded jitter of `params_gt` (`v0` scales the profile, `s_init` shifts) → `materialise` of a one-preset-block spec | 600 (`_PRESET_N`) |
| **generator** | `_leader_profile(prof, N, DT, rng, v0)` — **read-only call** | 600 (we choose; it takes any N) |

⚠️ **The strength slider does NOT govern the generator family** — that family's jitter is the one hardcoded
inside `_leader_profile` (base/amp/freq/cycle_len). That is the price of reusing the *real* training
randomisation instead of re-interpreting it. Stated in the UI, not just here.

Lengths stay **natural** → the dataset is heterogeneous in length; the manifest records each `N`. Fine for
analysis; 7b (training) will likely need uniform length — deferred to 7b, deliberately not pre-solved here.

### 2 · Spec retention (the enabling change)

`sigScenarioBuilt` becomes `Signal(object, object)` → emits `(scenario, spec)`. The app keeps
`self._specs: list[ScenarioSpec | None]` **parallel to `_scenarios`** (`None` for library + the initial
manual; the spec for built ones). `_on_scenario_built(scenario, spec)` appends to both; `_delete_scenario`
(item 2) **pops both** → the lists stay aligned across deletions. A parallel list (not a dict keyed by index)
is what survives the delete.

**Churn:** the ~4 sites connecting/emitting `sigScenarioBuilt` must be updated in lockstep. Enumerated in the
plan before touching the signal (the item-1/item-2 lesson).

### 3 · The mix and the draw

A table of rows `(family, source, weight %)`, total must be **100**. Sources per family: built = `_specs`
non-None · preset = the library names · generator = the 5 profile types.

**Empty-built edge case:** on a fresh app no scenario has been built, so the `built` family has **no sources**
— that family is disabled in the combo (with "costruisci prima uno scenario in Scenari"), rather than offering
a row that can never be completed.

**Exact quota, not a multinomial draw**: `N=100` with 30% → **exactly 30** trajectories (largest-remainder
for the leftovers). "Percentage" for a controlled dataset means an exact count, not an expectation.

### 4 · Frequency (decimation only)

Physics **always runs at 10 Hz** (DT=0.1 — the V2X rate baked into three invariants). The export can be
**decimated by an integer `k ∈ {1,2,5,10}`** → 10 / 5 / 2 / 1 Hz. A **"?" tooltip** states that 10 Hz is the
canonical V2V rate and that decimation subsamples the export while the physics stays at 10 Hz (the app already
uses "?" formula tooltips on the post-run metrics — same idiom).

- `a_leader` is **recomputed at `dt_out`** (`diff(v)/dt_out`): the 0.2 s acceleration is **not** the 0.1 s one.
- The manifest records `dt_out`, `k`, `decimated_from = 0.1`.
- **Upsampling is refused** — it would invent data the physics never produced.
- Honest caveat, documented: decimating a noisy leader (the `following` preset is `v_set + N(0,0.3)` white
  noise) **aliases** — the result is a subsample, not a filtered signal.

### 5 · The format registry

`FORMATS = {name: FormatSpec(writer, bytes_per_tick, available, reason)}` — the **single source of truth**; the
UI renders checkboxes *from the registry*, so no hardcoded list can diverge.

| format | writer | available |
|---|---|---|
| `.csv` | item 2's `write_scenario_csv` | ✅ |
| `.mat` | item 2's `write_scenario_mat` (scipy-free MAT v5) | ✅ |
| `.json` | stdlib `json` | ✅ |
| `.xlsx` | **hand-rolled**: a zip of XML via stdlib `zipfile` (same school as the hand-rolled MAT v5; easier — text, not binary tags) | ✅ |
| `parquet` | — | ❌ `reason="richiede pyarrow"` |
| `hdf5` | — | ❌ `reason="richiede h5py"` |

`parquet`/`hdf5` are **registered but disabled**, shown greyed with the reason. This honours "prevedere altri
formati" without lying about dependencies: enabling one later = install the dep + a small writer + flip
`available`. **Why not install them now:** both are *compiled* libraries, and this env has a known OMP
fragility (the OMP #15 abort is duplicate OpenMP runtimes; `torch` already brings one). Risking a green 305-test
env for a format no consumer has asked for is a bad trade.

### 6 · The size estimate

`Σ(ticks of the drawn trajectories after decimation) × bytes_per_tick(format)`, summed over the selected
formats, shown as **"≈ 8,0 MB"** (an estimate — float formatting varies). Constants are calibrated from the
measured sizes above; `.json`/`.xlsx` get measured during implementation and pinned the same way.

**The test that keeps it honest:** write a real sample, measure the bytes, assert the registry's
`bytes_per_tick` is within ~10% → the estimate cannot silently drift as a writer changes.

### 7 · The eye (hover preview)

An 👁 next to each row's source. The load-bearing part is that the **sampling is pure and testable**:
`preview_sample(family, source, seed, strength) → v_leader`. The hover popup is a thin shell over it, reusing
`ScenarioPreviewPanel`.

⚠️ For the **generator** family and for **jittered** built scenarios the curve is **one representative sample**
(fixed preview seed), not "the" scenario — there the scenario **is a distribution**. The popup says
"campione". Only an un-jittered preset's curve is exactly what will come out.

### 8 · Output

A folder: `traj_0000.<ext>` … + **`manifest.json`** — base seed, count, mix weights, jitter strength, `k`/
`dt_out`, formats; and **per trajectory**: family, source, derived seed, `params_gt`, the drawn knobs, its `N`.
Reproducible: same seed → same dataset, and the manifest says *why* each file is what it is.

### 9 · The units

| file | responsibility |
|---|---|
| `sim/jitter.py` | **PURE** — `jitter_spec(spec, rng, strength)` (blocks + neutral) and `jitter_params_gt(pg, rng, strength)`. The heart; isolated, tested alone. |
| `sim/dataset_mix.py` | **PURE** — the mix model + exact-quota draw + the manifest dict. |
| `sim/export_formats.py` | **PURE** — the registry + the `.json` and hand-rolled `.xlsx` writers + `bytes_per_tick`. |
| `sim/dataset_gen.py` | **PURE** — the 3-family sampler (`preview_sample` lives here) + the batch loop (writes via `scenario_export` + the registry). |
| `sim/ui/dataset_page.py` | **Qt** — the 5th mode: mix table (row-widgets, not a `QTableWidget` with delegates — simpler and testable), seed/count/jitter, frequency combo + "?", format checkboxes from the registry, size estimate, folder, Generate + progress. |
| `sim/ui/app.py` | the 5th mode wiring + `_specs` parallel list + the `sigScenarioBuilt` 2-arg change. |

**Progress without freezing:** the Meso page's batch run was already fixed to not freeze (QC hardening). The
plan **reads that pattern and reuses it** rather than inventing a `processEvents()` or a new thread.

## Testing

- **`jitter`**: same seed → identical spec (reproducible); **type preserved** (a `sine` stays `sine`, `ticks ≥ 1`,
  values inside `V_RANGE`/`A_MAX_RANGE`/`B_MAX_RANGE`); **strength=0 → byte-identical spec** (the degenerate
  case proving jitter is the only source of variation).
- **`dataset_mix`**: quotas sum to N and are exact (30% of 100 → 30); largest-remainder handles 33/33/34.
- **`dataset_gen`**: each family yields a valid `Scenario`; **the generator family equals `_leader_profile`
  called directly with the same seed** (proves we reuse the real randomisation, not a re-interpretation);
  `preview_sample` is deterministic for a fixed seed.
- **`export_formats`**: each available writer round-trips; **`bytes_per_tick` is within ~10% of a measured
  sample** (the anti-drift test); unavailable formats report their reason and are not callable.
- **batch**: N files + a coherent manifest; **same seed → identical dataset** (byte-compare a couple of files).
- **app**: `_specs` stays aligned with `_scenarios` across build + delete.
- **Invariants**: frozen core + `utils/closed_loop_eval.py` + `sim/scenario_spec.py` `materialise` + **`data/generator.py`** all untouched (empty diff — we call it, we never modify it).

## Invariants

- Frozen core (`sim/{state,stepper,backend,probe,events,eventprop_stepper}.py`) untouched.
- `utils/closed_loop_eval.py`, `materialise`, and **`data/generator.py`** untouched.
- Runner: the env's python directly (never `conda run`). **Suite = the sim glob**
  (`pytest tests/test_sim_*.py tests/test_champion_io.py`), NOT `pytest tests/` (FPGA scripts abort
  collection). ~3 min → ≥420 s or background. Baseline **305 green**.
- No scipy / no LAPACK / no new compiled deps in `cf_sim`.
- Commits conventional, **no `Co-Authored-By`**. Merge → main stays parked.
