# Dataset generator — 7b: the TRAINING sink — Design Spec (**DRAFT**)

**Date:** 2026-07-17 · **Branch/worktree:** `Simulator` · **Status:** 🟡 **DRAFT — captured intent, NOT
finalised.** Split out of the combined dataset-generator draft when the user chose to decompose item 7. It
needs its **own brainstorming**; the forks below are open — especially ①, which is a risk decision, not a
design taste. **Do 7a first** (`2026-07-17-dataset-generator-7a-design.md`): 7b reuses its engine.

## Goal

Make the generated dataset consumable by the **SNN training pipeline** — i.e. emit the training contract, with
the training physics, for scenarios the user built (which the training generator has never heard of).

Comes from the user's answer "**entrambi**" when asked who consumes the dataset: analysis (→ 7a) **and**
training (→ this).

## Established facts (grounded 2026-07-17 — these are the constraints, not opinions)

- **The training contract is `(N_steps, 7)` float32** (`data/generator.py:15-26`):
  `[s, v, dv, v_l, v_dot, T_true, mask]` — col 0-3 are the SNN's V2X inputs, col 4-5 the physics ground truth
  used by the **PINN loss**, col 6 the V2X packet mask. Any training dataset must be this.
- **The physics is `simulate_trajectory`** (`:252`): ACC-IDM on an IIDM base + CAH + OU sensor noise + OU on the
  time gap + packet loss. It is what the champions were trained on.
- **`simulate_trajectory(params, profile: str, seed, noise_scale)` cannot take an arbitrary leader.** It builds
  the profile *internally*: `v_l_profile = _leader_profile(profile, N, DT, rng, params['v0'])` (`:276`). A
  built scenario's `v_leader` has **no way in**.
- **The trajectory length is fixed by config**, not by the scenario: `N = int(SIM_DURATION / DT)` (`:274`),
  `SIM_DURATION = 120.0` (`config.py:121`) → 1200 ticks. 7a's dataset is deliberately heterogeneous in length
  (built = sum of blocks, preset/generator = 600). Training needs uniformity → see fork ②.
- **`data/generator.py` is an invariant in practice**: `train.py` imports it; `Arch_Tested/README.md:63` calls
  it *"shared (intero)"*; the champion `R24F_MIXED_.../data/generator.py` is a **frozen copy** = the data
  provenance of the trained champions. 7a only ever **calls** it. 7b is the cycle that must decide whether to
  **modify** it.

## Open forks (DECIDE AT IMPLEMENTATION — ① is the whole cycle)

- **① How does a custom `v_leader` reach the training physics?**
  - **(a) An additive param in the invariant**: `simulate_trajectory(..., v_leader=None)` → when `None`, call
    `_leader_profile` exactly as today. Backward-compatible *by construction*, but it edits the file that is
    the champions' data provenance. Would need a **byte-identity regression**: same seeds → byte-identical
    datasets vs the frozen champion copy, proving the default path did not move.
  - **(b) A parallel implementation** in `sim/` that re-implements the ACC-IDM/OU/packet-loss physics taking a
    `v_leader`. Touches nothing — but risks **silently diverging** from the physics the champions were trained
    on, which is the worse failure (a dataset that looks right and is not).
  - **(c) Refactor `simulate_trajectory` into (leader-generation | physics)** and call the physics half. The
    clean design, the biggest edit to the invariant.
  - *Lean: (a) — smallest edit, and the byte-identity test makes the "did I move the provenance?" question
    answerable rather than a matter of faith. But this is the user's risk call, not mine.*
- **② Uniform length.** Training wants a fixed `N` (batching). 7a's sources have natural lengths. Truncate to
  `SIM_DURATION/DT`? Pad? Constrain the mix to sources of the right length? Reject built scenarios that are too
  short? *Lean: require/trim to `SIM_DURATION/DT` and refuse sources shorter than it — silently padding a
  leader profile invents physics.*
- **③ Are `params_gt` and the OU noise part of the randomisation here?** In 7a `params_gt` jitter is nearly
  cosmetic. In 7b `params_gt` **are the labels** — jittering them is the whole point of dataset variety (it is
  exactly what `_sample_scenario:538-581` does per regime). *Lean: yes — reuse `_sample_scenario`'s per-regime
  jitter ranges rather than inventing new ones.*
- **④ Do we also expose the driver-regime axis** (`highway/urban/truck/mixed/freeflow/launch`, weighted by the
  existing `parse_scenario_mix`)? 7a deliberately ignores it because the user's "scenari" meant the simulator's
  vocabulary. For training it is the axis that actually matters. *Lean: a second, orthogonal mix — the leader
  axis (7a's families) × the driver-regime axis.*
- **⑤ Output**: the training pipeline reads a cached tensor (`data/cache_1500_highway_cut0.0_ou0.0.pt`, per
  `Arch_Tested/A1_.../README.md:64`). Does 7b write that cache format directly, or a folder the pipeline
  ingests? **Check the cache contract first.**

## Note

This draft exists so the training intent is not lost by the 7a/7b split. It is deliberately NOT a spec: fork ①
is a decision about the provenance of every trained champion and must be taken deliberately, with the user, in
its own brainstorming — not inherited from a lean written here.
