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
| `sim/ui/drag_handles.py` | **Qt only** — the drag unit (cycle 4b) | `DragHandles`: a row of `pg.TargetItem` vertically-constrained (reconnect x in `sigPositionChanged`, converges in 2), y clamped to `V_RANGE`; `set_speeds` silent, a drag notifies once. Isolated + tested alone because the drag is the one measured-risk piece |
| `sim/ui/scenario_page.py` | **Qt only** — the composer (cycles 4a/4b) | the WIDGETS own the composed block's params (no shadow dict); for `custom` the widget IS the row of handles (`_params_for` returns a TUPLE, the JSON canonical form). The PAD owns the block's point, distance-from-neutral IS the bias; it dies on preset AND custom (both ignore the style); neither records a bias. The advisory is a red overlay (`#ff2d2d`, NaN + `connect="finite"`) on the composer preview (all segments) and the scenario curve (custom segments only, via `block_of_sample`); base curves are orange so red reads as danger |

### The invariant — `utils/closed_loop_eval.py`

**INVARIANT by the contract in its own docstring** — the reports run on it. `build_scenarios` (`:332`)
produces the 9 presets; `simulate` (`:139`) is what `SimStepper` mirrors bit-for-bit; `safety_metrics`
(`:228`) computes `brake_margin` (`:241`, `min<0` = "collision physically unavoidable"). `B_MAX=9` (`:22`).

The false-red facts every advisory feature must respect (verified from these lines):
- `cut_in`: `vl[t_cut:]=0.45·v0` (`:367`) — a jump because the leader **is a different vehicle**, not a manoeuvre.
- `following`: `vl=v_set+rng.normal(0,0.3)` (`:347`) — ~4 m/s² of noise typically, ±13 in the tail.
- `panic_stop`/`hard_brake` brake at `-9`/`-7` but the `max(0,…)` clamp (`:399,359`) stops them at 0 in ~24/~30 ticks — that is why only ~24/~30 samples "violate".

### The periphery — not on the spine, one line each

`app.py` (742) wires the 4 modes + selector + deep-scrub + champion loading; `panels.py` (640) the live
dock panels; `topdown.py`/`loop.py`/`reconstruct.py` the road + ghost + scrub; `meso_*`/`postrun_page.py`
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

**272 across 23 files** (22 `test_sim_*.py` + `tests/test_champion_io.py`); **272 green** at `1516596`
(end of cycle 4b). `test_sim_ui_smoke.py` alone is 81 tests; `test_sim_drag_handles.py` (the 22nd sim
file) is the cycle-4b drag unit.

Runner — **never** `conda run -n cf_sim python -m pytest` (crashes conda's plugin system intermittently):

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

⚠️ The full suite takes **~3–4 minutes** (many tests build `SimApp` with the champion). A 2-minute default
timeout **looks like a hang and is not one** — give it ≥420 s or run it in the background.

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
