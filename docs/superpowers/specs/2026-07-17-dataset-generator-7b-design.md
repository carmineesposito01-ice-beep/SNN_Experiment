# Dataset generator — 7b: the TRAINING sink — Design Spec

**Date:** 2026-07-17 · **Branch/worktree:** `Simulator` · **Status:** ✅ **FINAL — approved by the user
2026-07-17.** Supersedes `2026-07-17-dataset-generator-7b-DRAFT.md` (deleted in the same commit; git keeps it).
Builds on **7a**, which is complete and landed (`2026-07-17-dataset-generator-7a-design.md` — the engine and
the 5th "Dataset" mode; 345 tests green).

## Goal

Let the user **retrain the network** on leader scenarios they built, and — as the second-order capability —
**design a dataset that excites a targeted weakness**, the way the Loss_Study added `freeflow`/`launch` to make
`a` identifiable.

The deliverable is a `.pt` cache that **`train.py --data_cache <ours>` eats with zero modifications**.

## Read this first — what the DRAFT got wrong

The draft was written before the code was read end-to-end. Three of its five "open forks" were built on
premises that are **false**. They are recorded here so nobody re-inherits them:

| Draft claim | Reality (verified 2026-07-17) |
|---|---|
| *"`data/generator.py` is an invariant in practice"* — fork ① framed as *"the cycle that must decide whether to modify it"* | **It is not frozen.** All 6 archived copies under `Arch_Tested/*/data/generator.py` differ from the live file by the **same 56 lines**, and those lines are **purely additive and default-off**: the `launch` profile, the `freeflow`/`launch` regimes, `_PHYS_BOUNDS`, and `generate_dataset(..., wide_params=False)`. The last one **is literally fork ①(a)** — the project already did this, for the Loss_Study. |
| *fork ② "Training wants a fixed N (batching) → truncate? pad? refuse?"* | **The fork does not exist.** `CFDataset` (`train.py:129-159`) windows **each trajectory independently** (`while start + seq_len <= N`). Batching is over *windows*, not trajectories. Uniform length is not needed. The real constraint is `N ≥ seq_len` (default **100**, `train.py:1058`). |
| *fork ⑤ "does 7b write the cache format directly? **Check the cache contract first.**"* | **Checked.** The cache is `torch.save({'train': [...], 'val': [...], 'seed': int})` (`train.py:1462`), read back at `:1419-1424`. The lists are exactly what `generate_dataset` returns. Writing that file needs **no change to `train.py`**. |

Fork ③ (params are the labels → reuse `_sample_scenario`'s ranges) and ④ (the driver-regime axis) were right
and are adopted below.

## Established facts (verified by reading and by executing, 2026-07-17)

**The provenance is preserved by additive edits — measured, not assumed.**
Same seed, live `data/generator.py` vs the frozen `Arch_Tested/R24F_MIXED_lr0.5_V08_TRUE_CHAMPION/data/generator.py`:
**8/8 byte-identical** trajectories (`raw`, `x`, `y`, `mask`, `params`, metadata), on **both** branches — the
normal one and, with `cut_in_ratio=1.0` forced, the cut-in one. The archived `config.py` is **identical** to the
live one, so the generator is the only moving part and it did not move. *(The first run of this probe used the
default `cut_in_ratio=0.20` and drew 0 cut-ins in 8 scenarios — the claim was incomplete until the forced run.)*

**The training contract.** `(N,7)` float32 (`generator.py:15-26`): `[s, v, dv, v_l, v_dot, T_true, mask]`.
Col 0-3 = the SNN's V2X inputs, col 4-5 = the physics GT for the PINN loss, col 6 = the packet mask.

**The physics.** `simulate_trajectory` (`:252`): ACC-IDM on an IIDM base + CAH + OU sensor noise + OU on the
time gap + packet loss. It builds its leader **internally** (`:276`) — a built `v_leader` has no way in.

**`traj[:,3]` IS the leader profile** (`:329`: `traj[i] = [s, v, dv_true, v_l_true, v_dot, T_cur, mask]`).
This is what makes an injection **provable** rather than hoped-for.

**The rng is shared** (`:273-276`): `_leader_profile` draws from the same generator that then feeds the OU
noise and the packet loss, and it draws a *different number of values per profile* (`free` draws none,
`sinusoidal` draws 3). **Consequence:** injecting a leader skips those draws, so the downstream noise is not
what the same seed would give with a profile. Not a bug — but *"same seed, different leader, same noise"* is
**not a promise we can make**.

**Lengths.** `N = int(SIM_DURATION/DT)` = **1200** (`config.py:121,63`); `generate_dataset` strips
`warmup_steps = int(WARMUP_DURATION/DT)` = **200** (`:621,643`) → **1000 usable ticks**. Defaults:
5000 train / 500 val (`config.py:118-119`, `train.py:1187-1188`).

**Windows.** `stride_trn = seq_len//2`, `stride_val = seq_len` (`train.py:1467-1468`). Window count per
trajectory = `floor((N - seq_len)/stride) + 1` for `N ≥ seq_len`, else **0 — silently**.

**Cut-in.** `simulate_cut_in_trajectory` (`:338`) calls `_leader_profile` **twice**: leader A (`:371`, the
scenario's) and leader B (`:378`, **hardcoded `'sinusoidal'`** — a *different vehicle*). At `t_cutin`
(`:365-368`, drawn in `[warmup+10%N, warmup+60%N]`) the leader **switches** (`:403-412`) and B owns the rest.
So a cut-in **discards the designed leader from `t_cutin` on** — half to three quarters of it.

**Regimes.** `_sample_scenario` (`:520`) picks the regime from `scenario_mix` via `rng.choice` (`:536`) and
derives **both** `params` (the labels) and the profile from it (`:538-581`). Default `SCENARIO_MIX` =
`highway .50 / urban .30 / truck .10 / mixed .10` (`config.py:125`) — **`freeflow`/`launch` are not in it**.
`CUT_IN_RATIO = 0.20` (`config.py:91`), rolled per trajectory as `rng.random() < cut_in_ratio` (`:584`).

**Who reads what** (repo-wide grep, not memory): `CFDataset` reads `x`, `y`, `mask`, `params`.
`train.py:1428` reads `scenario` (cache-vs-mix sanity check → **warning only**). `train.py:2050` (the G13
diagnostic) reads `scenario`, `cut_in`, `raw`, and **degrades silently** to fewer trajectories if it finds no
highway / urban / cut-in. `print_dataset_stats` reads `raw`, `cut_in`. **`profile` is read by nothing** in the
training path.

**`val_loss` steers, it does not just report**: it selects the saved checkpoint (`train.py:798`
`save_checkpoint(..., val_loss, ...)`), drives early stopping (`:1218`), and drives `ReduceLROnPlateau`
(`:1659`).

## Decisions taken (the user's calls, 2026-07-17)

1. **Purpose** — retrain for real, *and* keep targeted excitation as a first-class capability.
2. **Fork ①** — **(a) an additive `v_leader=None` parameter** in `simulate_trajectory`. Precedent:
   `wide_params=False` in the same file. Guarded by the provenance test (below).
3. **Cut-in** — **a row of the mix**, not a percentage sprinkled per scenario. *(The user's own proposal; it
   is better than the alternative offered.)* Rationale: `quotas()` gives an exact count where the generator's
   `rng.random() < 0.20` gives an expectation; the row is visible where a global ratio is a hidden dice roll;
   and it keeps **one injection site**, which is what we want anyway since a cut-in discards the design.
4. **Regime axis** — **a column in the row**: `(family, source, regime, weight)`. One row = one sentence.
5. **Validation** — a **3-mode selector**, each with its stated consequence: Standard · New shapes · Different
   mix. "Same strength as the champion" was disambiguated by the user to mean **new shapes** (no leader shape
   shared with train), not "the canonical champion val".
6. **UI** — **one "Dataset" mode with a destination toggle**, not a 6th mode.

## Architecture

```
row (family, source, regime, weight)
   │
   ├── regime  ──► params (THE LABELS)
   │               = _sample_scenario(rng, scenario_mix={regime: 1.0}, cut_in_ratio=0.0)
   │                 ↑ reused VERBATIM: the regime is forced through its own parameter
   │
   └── family  ──► leader
        ├── built     → jitter_spec + materialise → v_leader → INJECTED
        ├── preset    → materialise(one-preset block, params from the regime) → INJECTED
        ├── generator → simulate_trajectory(params, profile=source)      ← STANDARD path, no injection
        └── cut_in    → simulate_cut_in_trajectory(params, profile=source) ← STANDARD path, no injection
   │
   ▼
traj (N,7) → strip warmup (200) → normalize() → the 8-key dict
   │
   ▼
exact quotas → train batch (seed S) + val batch (seed S+1) → torch.save({'train','val','seed'}) → .pt
```

Three properties follow, and they are the point of the design:

- **The labels are not invented.** Forcing `scenario_mix={regime: 1.0}` reuses `_sample_scenario` **verbatim**,
  so the per-regime ranges are the champions', not a copy of them that can drift.
- **Injection only where it is needed.** `generator` and `cut_in` go down the untouched path. Consequence: a mix
  of only `generator`+`cut_in` rows **reproduces the standard dataset**, and that is testable against
  `generate_dataset`.
- **The jitter changes job.** In 7a the slider also moved `params`; here `params` are the labels and the regime
  owns them. **The slider governs the LEADER (built/preset), not the params.** Jittering them twice would break
  the correspondence with the champions' label distribution — closed by construction, not by a warning.

## The injection, and the two tests that hold it

In `data/generator.py`, additive and default-off, **one site**:

```python
def simulate_trajectory(params, profile='sinusoidal', seed=None, noise_scale=1.0, v_leader=None):
    ...
    rng = np.random.default_rng(seed)
    N   = int(SIM_DURATION / DT) if v_leader is None else len(v_leader)
    v_l_profile = _leader_profile(profile, N, DT, rng, params['v0']) if v_leader is None \
                  else np.asarray(v_leader, dtype=np.float32)
```

With `v_leader=None` the path is identical to today, line for line. This is the `wide_params=False` mould.

- **The provenance gate** — same seed → dataset **byte-identical** to the frozen champion copy, on both
  branches. It is 8/8 today; it must stay 8/8 after the edit. This turns *"did I move the champions' data
  provenance?"* into a question with an answer.
- **The injection-landed gate** — `np.allclose(traj[:,3], v_leader)`. Without it, a `v_leader` silently ignored
  would produce a plausible, wrong dataset — the worst failure mode available here.

## The mix

`TrainMixEntry(family, source, regime, weight)`; `FAMILIES_TRAIN = ("built", "preset", "generator", "cut_in")`;
`REGIMES = ("highway", "urban", "truck", "mixed", "freeflow", "launch")`. Quotas reuse 7a's `quotas()`
(largest remainder, exact counts). Sources cascade from the family exactly as in 7a; for `generator` and
`cut_in` the source is a leader profile from `GENERATOR_PROFILES` (for `cut_in` it is leader **A**'s profile —
leader B stays the generator's hardcoded sinusoidal).

## The output contract

The 8-key dict, with `scenario` = **the regime name**, so `train.py:1428`'s check passes instead of warning on
every run. Our own provenance goes in **additive keys** (`leader_family`, `leader_source`) — `CFDataset`
ignores keys it does not know, so it is free and it lies to nobody. `profile` is filled for parity with
`generate_dataset` even though nothing in training reads it.

The cache is `torch.save({'train': [...], 'val': [...], 'seed': S})`. Two batches, seeds `S` and `S+1`, which
is what `train.py:1448-1455` does when it generates from scratch.

## Four constraints, and the trap

1. **Length.** `N = len(v_leader)`. After the warmup strip at least one window must survive → **`L ≥ 300`**
   (300 − 200 = 100 = `seq_len`). Below that, `CFDataset` yields **zero windows and says nothing** → we
   **refuse loudly at generation time**. A dataset that generates cleanly and trains nothing is not acceptable.
2. **Warmup.** Strip 200 ticks like `generate_dataset` (the ego starts at `0.8·v0` with a random gap: the
   transient is an artefact, not the leader's physics). On a 600-tick built scenario that is **33% of the
   design** — the UI says so; design at 1200 to match the champions' 1000 usable ticks.
3. **Frequency.** 7a's decimation knob is **disabled** here. `DT=0.1` lives inside the physics *and* inside the
   PINN loss (`a_l` re-estimated by finite differences over `DT`, `generator.py:28-30`). A decimated training
   set would be wrong in silence.
4. **Time — the constraint the design forgot, found in self-review and MEASURED.**
   `simulate_trajectory` is a 1200-step Python loop: **60.9 ms per trajectory** (20 drawn, timed). The default
   5000+500 is therefore **≈ 335 s ≈ 5.6 minutes** — **110× the work of a 7a batch** (~3 s), and 7a's
   `_busy` + `processEvents` run is **synchronous on the GUI thread**.
   *Design consequence, in order of preference:*
   - **Keep the synchronous idiom.** No threads: the codebase's rule is that `processEvents()` is safe
     *precisely because* `_busy()` closes every re-entry path. A worker thread would trade a known-safe
     pattern for a new class of bug, in a cycle that already touches the champions' provenance.
   - **Add Cancel.** The progress callback returns `False` (or raises) to abort; `finally: _done_busy()`
     already exists. ~5 lines, and it turns a 5.6-minute commitment into a 5.6-minute job you can stop.
     Partial output is **not** written — a half dataset that looks whole is the failure this project keeps
     hunting.
   - **Show the ETA**, from the measured rate × trajectories remaining, *before* the click and during the run.
     5.6 minutes is acceptable when announced and refusable; it is not when it arrives as a surprise.

**The trap — the quota you ask for is not the quota the network sees.** You weight *trajectories*; training
eats *windows*, and a short trajectory yields fewer:

| source | ticks | after warmup | windows @ stride 50 (train) | @ stride 100 (val) |
|---|---|---|---|---|
| built @ 600 | 600 | 400 | **7** | 4 |
| generator | 1200 | 1000 | **19** | 10 |

A "30% built / 70% generator" mix is **13.6% / 86.4%** in windows. This is not hidden: the table shows the
**window share** live, next to the trajectory quota — the same honesty as 7a's "≈ MB" estimate and its
"campione" popup title.

⚠️ **The share depends on the stride, and the two batches do not share it** (`train.py:1467-1468`: train
`seq_len//2`, val `seq_len`) — the same mix is 13.6% built in train and 14.6% in val. The column shows the
**train** stride, because that is where the learning happens, and it says so. *(The 19/traj and 10/traj figures
above are not from the formula: they were counted by instantiating the real `CFDataset`.)*

## The validation

**Mode 1 — Standard** *(default)*: same mix, seed `S+1`. Two i.i.d. samples → the train↔val gap **measures
overfitting**. This is what `train.py` does natively.
⚠️ *UI warning when the mix has `built`/`preset` and jitter is 0*: the val may share the leader's shape with
train (7a proved `strength=0` makes `jitter_spec` the identity) → it then measures generalisation over params
and noise, not over new leaders.

**Mode 2 — New shapes**: same mix, seed `S+1`, **plus a verified gate**: no val `v_leader` is identical to a
train one. The gate checks the **property**, not a proxy — "force jitter > 0" would be wrong in both
directions: a `const`/`ramp` built spec does not depend on `v0`, while a `preset` or a `sine` is anchored to
`v0`, which the regime already jitters per trajectory. If the mix produces a collision, generation **stops and
names it**.
⚠️ *Honest twice*: the gate catches **exact** copies, not near-copies; and a `built` stays *one shape,
rippled* — real shape variety only comes from `generator`.

**Mode 3 — Different mix**: a second mix table, for val only.
⚠️ *Strong warning*: the gap no longer measures overfitting, and `val_loss` **selects the checkpoint**, drives
**early stopping** and commands **`ReduceLROnPlateau`** — you would be choosing the champion on a distribution
you are not training on. A legitimate experiment (an out-of-distribution probe), but it must be chosen knowing
that.

## The UI

**One "Dataset" mode, with a destination toggle** at the top: `Analisi` | `Training`. Not a 6th mode: you are
always building a dataset; what changes is where it goes — and a "Training" sibling next to "Dataset" would
muddy the selector.

- **`MixTable` is extracted into a widget** (`sim/ui/mix_table.py`) with options `with_regime` and the family
  list. Analysis → one instance, no regime. Training → one instance **with** regime and the `cut_in` family.
  Val mode 3 → **a second instance**, free. The extraction is what mode 3 required anyway, and it makes train
  and val *the same thing* instead of two cousins.
  *Rationale for the refactor:* `dataset_page.py` is 281 lines today; growing it in place with `if training:`
  branches lands it near 550 lines of conditionals, and every test would first have to declare which mode it
  is in.
- **The controls stack** (`QStackedWidget`): the Analysis block is today's (formats, frequency, ≈MB); the
  Training block is new (train/val counts, the validation selector + a live warning line, the `.pt` estimate).
- **Folder + Generate + progress stay shared** — the same `_busy` idiom (`app.py:385-408`) — **plus a Cancel
  button and an ETA**, which 7a did not need and 7b does (constraint 4: a default batch is ~5.6 minutes).
  The ETA is shown *before* the click, from the measured rate × the trajectory count, so a 5-minute job is a
  decision rather than a surprise.

Switching to Training shows: the **regime** column, the **cut_in** family, the **window share** next to the
quota, **train/val** counts, the **frequency disabled with its reason in view** (not only in the tooltip),
format = **`.pt`**, the jitter caveat reworded (*governs the leader, not the params*), and the
`python train.py --data_cache …` line so the page closes the loop instead of leaving the user to guess.

The size estimate follows 7a's rule: **bytes/tick measured and pinned by a test**, never guessed.
*(Order of magnitude for sanity: 5500 × 1000 ticks × 14 columns × 4 B ≈ 308 MB.)*

**Known polish, inherited from 7a:** the eye glyph. `👁` renders as a reddish blob in Windows' default font;
`◉` is cleaner but does not read as an eye. Since 7b rewrites that table anyway, fix it properly there.

**A rendered mock of the Training block was approved by the user** (Qt widgets + the real dark theme, not a
drawing). ⚠️ It **predates** constraint 4, so it shows neither the Cancel button nor the ETA — the plan adds
both; the mock is otherwise the agreed layout.

## Files

**Engine:** `data/generator.py` (**modified**, +4 additive lines) · `sim/train_mix.py` (new — the 4-field entry,
validation, reusing `quotas`) · `sim/train_gen.py` (new — the sampler, the injection, warmup, `normalize`,
splits, the disjointness gate, the `.pt` writer).
**UI:** `sim/ui/mix_table.py` (new) · `sim/ui/dataset_page.py` (modified — shell + toggle + stacked controls) ·
`sim/ui/app.py` (modified — the run routes to the training batch).

## Testing

1. **The risk guardian** — provenance byte-identity vs the frozen champion copy, both branches. The probe
   already exists; it graduates from experiment to **permanent gate**.
2. **The injection landed** — `traj[:,3] == v_leader`.
3. **The default path did not move** — `v_leader=None` produces what it produces today.
4. **The contract against the REAL class** — feed our dict to `train.py`'s actual `CFDataset` and require
   windows out. Same school as 7a's preview using `materialise` instead of a sketch: do not trust a
   remembered contract, make the real consumer digest it.
   ✅ *Verified 2026-07-17:* `from train import CFDataset` imports cleanly in **3.2 s**, no side effects, no
   `SystemExit` (unlike `tests/test_fpga_io.py`). The test may use the real class.
5. **The window share is counted by `CFDataset`**, not by our formula.
6. **The regime is forced** — `_sample_scenario(rng, {regime: 1.0}, 0.0)` returns that regime.
7. **The gates bite** — mode 2 catches `strength=0` on `built`; `L < 300` is refused loudly.
8. **Quotas are exact**; the cache round-trips through `torch.save`/`torch.load`.

## Scope

**One spec, two plans** (engine / UI), like 7a. With the 3 validation modes and the second table, 7b is
**bigger than 7a** — if the UI plan comes out too dense, say so and split it rather than deliver a monster.

**Non-goals**, explicitly:
- **Running the training.** 7b writes the file; `train.py` stays untouched and is launched by the user.
- **Modifying `train.py`** — the cache contract makes it unnecessary. If a plan finds itself editing it, stop:
  the design was wrong.
- **The OOD probe as a validation concept.** Mode 3 exposes the mechanism with its warning; interpreting an
  OOD val is a separate, deliberate study.
- **Injecting into the cut-in path.** One site only. Reopen this only with a reason better than symmetry.
