# Scenario builder — declarative blocks + leader style — Design Spec

**Date:** 2026-07-15 · **Branch/worktree:** `Simulator` · **Status:** design approved (user) → spec

## Goal

A fourth mode — next to Live, Meso/Macro and Post-run — where the user **builds a scenario** instead of
picking one of nine. A scenario is described **declaratively** as a timeline of blocks plus a **leader
style**, and materialised into the 600-float `v_leader` that `SimStepper` already consumes.

Cycle 3 of 3 from the 2026-07-15 request (user's point 2). Cycles 1 (oracle ghost) and 2 (checkpoint
identity) are done.

## Established facts (verified in code)

- **`Scenario` is a frozen dataclass carrying exactly the `SimStepper` inputs** (`sim/scenario.py:14-21`):
  `name, params_gt, v_leader, s_init, v_init, cut_in`. **`manual_scenario()` (`:35`) is already the door**
  for arbitrary scenarios — today it is only used for a flat profile (`app.py::_manual`). Nothing
  downstream needs to change to accept a built scenario.
- **`build_scenarios` (`utils/closed_loop_eval.py:332`) is INVARIANT and must not be parametrised.** Its
  own docstring states the contract: *"i 5 scenari storici … **INVARIATO**, cosi' eval_safety legacy non
  cambia"*. It is the validated source the reports run on. The constants a "style" would want to touch
  live in there: `-7.0 m/s²` (`hard_brake`, `:359`), period `120` (`stop_and_go`, `:352`), amplitude
  `0.20` (`sinusoidal`, `:374`), noise `0.3` (`following`, `:347`), `v_set = 0.7·v0` (`:341`).
  → **A preset block reuses `scenario_library()` as-is and the style does NOT touch it.** A validated
  preset you rewrite is no longer that preset.
- **`events.py` is listed as frozen core, but that freeze protects less than the list implies** —
  verified: `closed_loop_eval` has **no live events at all**, so there is no external golden to violate;
  `tests/test_sim_events.py:53` asserts bit-identity against `simulate` **only with `injector=None`**,
  and with a brake active it only checks determinism (`:62-75`). `EventInjector` is **injected** into
  `SimStepper` (`sim/stepper.py:24`), not built by it. → **User decision (2026-07-15): unfreeze it for
  this fix.** The resume lists it among the six out of inherited caution, not because a golden covers it.
- **The ramp bug, measured**: `sim/events.py:38` sets `self._brake = (t, float(base_vl), …)` where
  `base_vl` is the **raw** `v_leader[t]` handed in by the stepper (`sim/stepper.py:61`), not the leader's
  current *effective* speed. Two sequential brakes make the leader jump **5.00 → 21.00 m/s in one tick**
  (+16 m/s ≈ 160 m/s²). Root cause and fix are one line: capture `self._effective_leader(t, base_vl)`
  **before** overwriting `_brake`.
- **The builder does NOT trigger that bug.** It produces the leader's *profile*; the bug is in the *live*
  events (the "Brake leader" button pressed twice). Recorded because an earlier draft of the resume said
  otherwise — the fix belongs to this cycle by ownership, not by causation.
- **The Meso page ignores most of a scenario** (`sim/ui/app.py:383`): it passes the module constant
  `_PARAMS_GT`, not `sc.params_gt`, and uses only `sc.v_leader`. Today they coincide; a scenario with a
  different driver would make Meso **lie silently**. → see §Scope for why `params_gt` stays out.

## Scope

**IN**
1. `sim/scenario_spec.py` — the declarative model + a **pure materialiser** to `Scenario`.
2. Block vocabulary: `preset(name)` (a slice of `scenario_library()`, as-is) · `const(v)` · `ramp(to_v)`
   · `sine(mean, amp, period)`.
3. **Leader style** — the block declares *what*, the style decides *how brusquely*.
4. A fourth mode with the timeline, a live preview of the real `v_leader`, and "use this scenario".
5. JSON round-trip (declarative, not 600 floats).
6. The `events.py` ramp fix.

**OUT — and why**
- **`params_gt` is not editable.** It is the true driver (the oracle), not a property of the scenario;
  editing it is the roadmap's "GT sliders". And the Meso page would ignore it (`app.py:383`), i.e. lie.
- **A leader with its own dynamics** — the profile becoming a *desired* speed that the leader chases with
  its own accelerations, which would make discontinuities impossible by construction instead of by fix.
  **User decision: parked for a discussion at the end of this block.** Recorded so it is not lost.
- **A leader that reacts to the ego.** Car-following assumes the leader is an independent boundary
  condition, and the 4 champions were trained and validated under it. A different experiment.
- **New live verbs / trigger conditions** (the OpenSCENARIO pattern of `SIMULATOR_DESIGN.md:203`). The
  builder shapes the profile; `brake_leader` stays the one runtime interaction. YAGNI.

## Design

### ① The declarative model (`sim/scenario_spec.py`, new)

Frozen dataclasses, no Qt, no I/O — so the whole thing is testable as pure data:

```python
@dataclass(frozen=True)
class Block:
    kind: str            # "preset" | "const" | "ramp" | "sine"
    ticks: int           # how long this block lasts
    params: dict         # kind-specific: {"name":…} | {"v":…} | {"to_v":…} | {"mean","amp","period"}

@dataclass(frozen=True)
class LeaderStyle:
    name: str            # "calmo" | "normale" | "aggressivo"
    a_max: float         # m/s²  — how hard it speeds up
    b_max: float         # m/s²  — how hard it slows down

@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    blocks: tuple
    style: LeaderStyle
    s_init: float
    v_init: float
```

`materialise(spec, params_gt, N) -> Scenario` walks the blocks, concatenates each one's samples, and
hands the result to `manual_scenario()`. Pure function: same spec → same `v_leader`, byte for byte.

### ② Style: the block says *what*, the style says *how*

This is the whole point of the feature — it must change the trajectory, not the looks.

- `ramp(to_v)` — ⚠️ **`ticks` is the block's SLOT, not the ramp's duration.** Every block owns a slice of
  the timeline (`ticks`); *within* it, the ramp moves the leader from its current speed toward `to_v` at
  the style's `b_max` (decelerating) or `a_max` (accelerating), and **holds** once it arrives.
  *aggressivo* goes 21 → 2 m/s in 2.7 s at −7 m/s²; *calmo* takes 9.5 s at −2 — same intent, different
  conduct, and the block's length does not change between the two. If the slot is **too short** the ramp
  is simply cut where it got to and the next block starts from that speed — no teleport, and the preview
  shows it. This is the one place where "the block says what, the style says how" could be read two ways:
  it is the *rate* that the style owns, never the slot.
- `sine`/`const` are **rate-limited** by the same `a_max`/`b_max`: a style cannot be outrun by a block.
- `preset` is **untouched** — it is a validated profile, reproduced exactly as `scenario_library()`
  emits it. The UI must say so, or the user will wonder why the knob does nothing there.

Styles are three named presets. `normale` matches today's numbers so an all-`preset` timeline reproduces
the current behaviour exactly.

### ③ The page (`sim/ui/scenario_page.py`, new)

A fourth entry in the mode selector. Timeline of blocks on top (add / remove / reorder / edit), the
**materialised** `v_leader` preview below — the real one, from the same function the sim will run, not a
sketch — plus the style selector and `s_init`/`v_init`. "Usa questo scenario" appends it to the Live
scenario selector via `manual_scenario`. The preview is the honesty guarantee: what you see is literally
what will run.

### ④ JSON round-trip

`to_json(spec)` / `from_json(text)` — a list of blocks, human-readable and diffable, not 600 floats.
`materialise(from_json(to_json(s)))` must equal `materialise(s)` byte for byte.

### ⑤ The `events.py` ramp fix

```python
        for e in sorted(e for e in self._events if e.tick == t):
            if e.verb == "brake_leader":
                # Start the ramp from the leader's CURRENT EFFECTIVE speed, not from the raw
                # v_leader[t]: with a brake already active those differ, and using the raw value
                # made the leader jump (measured: 5.00 -> 21.00 m/s in one tick). Evaluate BEFORE
                # overwriting _brake, or _effective_leader would answer about the new ramp.
                v_start = self._effective_leader(t, base_vl)
                self._brake = (t, v_start, float(e.params["target_v"]), int(e.params["duration"]))
```

One line of intent, and the ordering is load-bearing.

## Errors and edge cases

| case | behaviour |
|---|---|
| blocks shorter than N | the last block **holds** its final value to the end (same idiom as `_effective_leader`) |
| blocks longer than N | materialise truncates at N and the UI says so |
| empty timeline | "use this scenario" disabled; preview blank, no crash |
| `ramp` to the speed it is already at | holds for the whole slot; no division by the style's rate |
| `ramp` whose slot is too short to finish | cut where it got to; the next block starts from that speed (no teleport) |
| `preset` name not in the library | rejected by name when loading JSON (same idiom as cycle 2) |
| JSON from a future version / unknown block kind | rejected with the kind named, never partially applied |

## Testing

The materialiser is pure → tested without Qt:

1. **An all-`preset` timeline reproduces the library exactly** — `materialise` of a single
   `preset("stop_and_go")` covering all N is **bit-identical** to `scenario_library()`'s `stop_and_go`
   (`assert_array_equal`). Fails if the style ever touches a preset.
2. **The style changes the trajectory, not the looks (teeth)** — the same `ramp(to_v=2)` under *calmo*
   and *aggressivo* produces different `v_leader`, and the measured decelerations match `b_max` within
   a tick's quantisation. A test asserting only "they differ" would pass a style that just renames things.
3. **Rate limiting holds** — no block, under any style, produces `|Δv/DT|` above that style's limits.
4. **JSON round-trip is byte-exact** on every block kind.
5. **The ramp bug is dead (teeth)** — two `brake_leader` in sequence: the leader's speed is
   **monotonically non-increasing** through both, and the largest one-tick jump stays within physical
   limits. Today this test fails with +16.00 m/s. Assert the jump, not a label.
6. **The single-brake behaviour is unchanged** — `tests/test_sim_events.py:13-22` must stay green
   untouched: the fix only bites when a brake is *already* active.
7. **`injector=None` stays bit-identical to `simulate`** (`test_sim_events.py:53`) — the one golden that
   events.py really has.
8. **Reconstruct still matches live** with two brakes: fix and replay must move together.

Baseline: **199 tests green** (20 sim files + `test_champion_io.py`). Env `cf_sim`, no LAPACK (OMP #15).

## Known debt (out of scope, do NOT fix here)

- `ReplayLog.seed` is fed the **scenario index** (`sim/ui/app.py:591`). Harmless today, semantically
  wrong. It becomes a real landmine only if scenarios ever carry a seed — the builder does not add one.
- The Meso page passing `_PARAMS_GT` instead of `sc.params_gt` (`app.py:383`). Latent while `params_gt`
  stays uneditable, which this spec guarantees; it must be fixed **before** any GT-sliders work.
