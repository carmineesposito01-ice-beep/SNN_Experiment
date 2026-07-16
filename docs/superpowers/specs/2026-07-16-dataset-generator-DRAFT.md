# Dataset generator — Design Spec (**DRAFT**)

**Date:** 2026-07-16 · **Branch/worktree:** `Simulator` · **Status:** 🟡 **DRAFT — captured intent, NOT
finalised.** The BIGGEST of the open items — almost a sub-project. Written now so the design is not lost;
it needs its **own full brainstorming** before implementation. Many forks are open.

## Goal

From a scenario (built or from the library), or a **percentage mix** of scenarios, generate a **dataset of
many trajectories** by seeded randomisation that keeps each trajectory "of the same type" — for
training/testing at maximum customisation.

The user's item 7: *"partendo da uno scenario, creare un dataset di molte traiettorie, ottenute come
'casualizzazione' di quella creata (con qualche seed che va a modificarle quanto basta per essere della
stessa tipologia), oppure una impostazione che ti permetta di decidere la percentuale di ciascun scenario
esistente (compresi quelli creati) e poi su quelli applichi randomizzazione per ottenere diverse
traiettorie e un dataset generato dalla massima personalizzazione"*.

## Established facts (grounded now — this is the key finding)

- **The seeded, type-preserving randomisation ALREADY EXISTS** in `data/generator.py` (757 lines), the
  training-data generator. `_leader_profile(profile, N, dt, rng, v0)` (`:179`) builds a leader velocity
  profile of a given TYPE (following, sinusoidal, stop&go, launch, …) with a **seeded rng** jittering base,
  amplitude, frequency, cycle length. `simulate_trajectory(params, profile, seed, noise_scale)` (`:252`)
  runs a full trajectory with a seeded profile + OU sensor noise + IDM-2D time-gap variation. **This is
  exactly the "randomise but keep the type" the user asks for — for the built-in types.** The NEW work is
  (a) randomising a USER-BUILT scenario and (b) the percentage mix.
- **The declarative block model makes randomising a built scenario natural**: each `Block`'s params
  (`to_v`, `v`, `amp`, `period`, the neutral `a_max/b_max`, the custom `nodes`) is a knob a seeded jitter
  can nudge — a structured perturbation that keeps the scenario's shape/type, unlike blurring the 600-float
  `v_leader`.
- **materialise is cheap** (4 ms even at 30000 ticks), so generating hundreds of trajectories is fast.
- **Ties to item 2's export**: the dataset is written as .csv/.mat, so the LAPACK-free .mat writer (item 2,
  fork ③) is a shared dependency.

## Scope (very provisional — needs its own brainstorming)

**IN (sketch)**
1. A **dataset-generation setting** (likely a new mode/panel or a dialog): pick a source (one scenario, or a
   percentage mix of scenarios), a **seed** and a **count N**, and a **jitter strength**.
2. **Randomise a built scenario** by seeded per-block param jitter (keeping the type).
3. **Percentage mix**: weights per scenario (library + built) summing to 100%; draw N trajectories.
4. **Export the dataset** (folder of per-trajectory files + a manifest), reusing the item-2 writers.

**OUT (sketch)** — labelling for a specific ML task; train/val/test split logic (leave to the training
pipeline); anything already covered by `data/generator.py` for the pure library types.

## Open forks (MANY — this needs its own brainstorming)

- **① What gets randomised?** The leader profile only (block-param jitter) — OR also `params_gt` (the IDM
  driver params, as `simulate_trajectory` does) — OR the sensor/channel noise. *Lean: start with block-param
  jitter on the leader (the built-scenario novelty), and OPTIONALLY reuse `simulate_trajectory`'s params +
  noise jitter for the library types.*
- **② Each dataset item = the leader profile, or the full run?** A training/test set usually wants the full
  closed-loop run (obs + predicted params + trajectory), which is what `simulate_trajectory` produces. *Lean:
  the full run, via the existing generator path — but confirm the intended consumer.*
- **③ Reuse vs re-implement `data/generator.py`?** It already does most of this for the library types. *Lean:
  extend it (add a "from a ScenarioSpec with jitter" source) rather than a parallel generator — but it is
  training-pipeline code; touching it needs care (it may be an invariant like closed_loop_eval).* **CHECK its
  contract first.**
- **④ Output format** — a folder of per-trajectory .csv/.mat + a JSON manifest (seed, weights, jitter), or one
  combined file? *Lean: folder + manifest (reproducible, inspectable).*
- **⑤ Where in the UI** — a 6th mode, or a dialog launched from the builder? *Lean: a mode (it is a distinct
  workflow), but this is a UX fork.*
- **⑥ Jitter strength semantics** — one "how different" slider, or per-knob ranges? *Lean: one strength
  slider mapping to per-param ranges (like `_leader_profile`'s hardcoded `uniform` ranges scaled).*
- **⑦ Is `data/generator.py` an invariant?** Like `closed_loop_eval.py`, it may be pinned by the training
  pipeline. **Must check before extending it.**

## Note

This draft captures intent and the crucial reuse (`data/generator.py`). It is deliberately NOT a finalised
spec — the forks above, especially ①–③ and ⑦, need the user in a dedicated brainstorming. It is the last and
largest of the post-verification items; do it after builder-UX, scenario-lifecycle, and the cockpit dock.
