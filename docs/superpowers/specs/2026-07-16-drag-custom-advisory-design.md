# Drag + `custom` block + physics advisory — Design Spec (cycle 4b)

**Date:** 2026-07-16 · **Branch/worktree:** `Simulator` · **Status:** design approved (user) → spec

## Goal

Let the designer **draw** a leader profile by dragging it, and tell them — without stopping them — where
the leader they described cannot physically produce what they drew.

Cycle 4b, and the last of the 2026-07-15 follow-up. The three pieces ship together because they only
mean anything together: the drag is how a `custom` block is authored, `custom` is the only thing worth
dragging, and the advisory is the only honest thing to say about a hand-drawn profile.

## Decided before this spec — do not relitigate

From the cycle-4 brainstorming, already chosen by the user:

- **The advisory's form is "light up the impossible stretches"**: the curve turns red exactly where the
  leader cannot follow it, and says by how much ("here you ask −23 m/s², yours has 9"). Rejected: the
  reachability cone (widens to ±40 m/s after 10 s → covers everything → says nothing) and the local
  corridor (`rate·DT` = 0.9 m/s wide on a 0–21 axis → an invisible thread).
- **It advises, it does not constrain.** The user's words: *«avvisi il 'designer' che quella cosa è
  infattibile, ma lui può comunque farla per i suoi scopi»*. The reason is in the codebase, not in
  taste: `brake_margin` (`utils/closed_loop_eval.py:238-241`) says in its own comment that `min < 0`
  means *«collisione fisicamente inevitabile di |min| metri»* — an unavoidable scenario **is a test**,
  and constraining the drawing would delete that whole class of evidence.
- **The rendering technique is verified** by a rendered spike: a second curve carrying `np.nan` on the
  physical samples plus `connect="finite"` draws **only** the impossible stretches. Without
  `connect="finite"` the NaNs become a straight line across the plot — i.e. the opposite of the feature.

## Established facts (measured, not assumed)

| what | number | why it matters |
|---|---|---|
| `TargetItem` (pyqtgraph 0.14) | draggable, emits `sigPositionChanged` | **no hit-testing to write** — the drag's biggest unknown, gone |
| 150 handles moved together | peak **10.12 ms** (budget 16.7) | handle count is **not** a performance limit; the eye is |
| vertical constraint via `sigPositionChanged` | converges in **2 calls**, x stays locked | the measured route; no recursion |
| the `TargetItem` subclass route | **crashes**: `__init__` calls `self.setPos(pos)` with a **tuple** | an override must handle tuple / `Point` / two-args — 3 signatures for elegance |
| declarative `ramp` in JSON | **225 B** | the baseline the "declarative, not 600 floats" principle protects |
| `custom` as 150 raw floats | 1 228 B (5×) | what naïve storage costs |
| `custom` as 600 raw floats | 4 776 B (21×) | ditto, at full length |
| **`custom` as 5 nodes** | **120 B** | **smaller than the declarative ramp** — the tension dissolves |
| `custom` as 9 / 17 nodes | 172 B / 278 B | still declarative at any useful resolution |

Plus, from the cycle-4 measurement that moved this whole cycle out of 4a: **the advisory on presets is
almost entirely false red.** `cut_in` demands −75 m/s², `aggressive_cut_in` −120, `cut_out` −210 —
those are **a different vehicle**, not a manoeuvre (`build_scenarios` does `vl[t_cut:] = 0.45·v0`,
`closed_loop_eval.py:367`); and `following` "violates" in **503 steps of 599** because its own
`rng.normal(0, 0.3)` noise divided by `DT=0.1` reads as ±13 m/s².

And one the mock produced by accident, worth keeping: **the node count controls how easy it is to break
physics.** With 5 nodes over 150 ticks each segment spans ~4 s, so the slopes come out gentle and a
drawn profile is hard to make impossible. Someone who *wants* an unavoidable scenario raises the node
count to shorten the segments. The count is not only a resolution knob.

## Scope

> ⚠️ **This section is the coverage checklist.** In cycle 4a the plan's self-review verified "every test
> the spec lists has a task" — 8 of 8 — and never read the Scope, so a whole requirement (the neutral's
> own control) reached the plan with no task and would have shipped unreachable. **Check the plan
> against THIS list, not against §Testing.**

**IN**

1. **`custom` block kind** — `params = {"nodes": [v, v, …]}` (**speeds only** — see §Design ①),
   materialised as a **linear** polyline anchored at `v0`.
2. **`physics_gap(v, neutral)`** — pure; which segments the leader cannot produce, and by how much.
3. **The drag** — one draggable handle per free node, **constrained to vertical**, on the composer's
   block preview. Only when `kind == "custom"`.
4. **A node-count control** — a spinbox; changing it **re-samples the current curve** at the new node
   positions rather than discarding the drawing.
5. **The advisory drawn in two places** — the composer's block preview while you draw, **and** the
   scenario curve below, but **only on samples that come from `custom` blocks**.
6. **`custom` inherits the preset's two rules** — the pad dies on it, and it never records a bias.
7. **JSON** — `custom` round-trips; no version field (old files simply contain no `custom`).

**OUT**

- **Free 2-D nodes** (add/move-anywhere/remove) and **free-hand drawing**. Rejected with reasons, above
  and in §Design ③.
- **Splines.** Rejected with reasons, in §Design ①.
- **Fixing `const` == `ramp`.** MEASURED in 4a: `_block_samples` sends both to
  `_rate_limited_toward(v0, target, n, style)` with identical arguments — only the param key differs, so
  the menu will now offer **5 kinds of which 2 are one**. Removing a kind breaks existing JSON and is the
  user's call, not this cycle's.
- **A leader with its own dynamics.** Still parked, and now permanently resolved the other way: the user
  chose the animator, and the advisory — not a dynamics model — is what keeps physics honest.
- **`params_gt` editing** — unchanged from cycle 3: it is the oracle, and the Meso page ignores it.

## Design

### ① The model (`sim/scenario_spec.py`, stays pure)

```python
_KINDS = ("preset", "const", "ramp", "sine", "custom")


def _custom_node_ticks(n, count):
    """Where the free nodes sit. DERIVED from (n, count) -- never stored (see below)."""
    return np.linspace(0.0, n - 1, count + 1)[1:]


def _custom_samples(speeds, n, v0):
    """A polyline: v0 at tick 0, then straight to each node's speed in turn.

    LINEAR, not spline, and both reasons carry weight:
    * each segment has ONE constant acceleration, so the advisory can light a whole segment and state
      the number exactly ("this segment asks -23") instead of maxing over a curve that varies inside it;
    * a spline through these nodes can OVERSHOOT past them -- from nodes that are all positive it can
      produce v < 0, i.e. the leader in reverse. np.interp cannot invent a value outside its inputs.
    It is also what the rest of the builder already is: _rate_limited_toward is a clipped linspace.
    """
    xs = np.concatenate(([0.0], _custom_node_ticks(n, len(speeds))))
    ys = np.concatenate(([float(v0)], np.asarray(speeds, dtype=np.float64)))
    return np.interp(np.arange(n), xs, ys)
```

**Nodes store SPEEDS, not (tick, speed) pairs — and this is not a size optimisation.** The nodes sit at
fixed, evenly spaced ticks by the design the user chose, so a node's tick is fully determined by `ticks`
and `len(speeds)`. Storing it too would create **a second owner for a derived value**: a hand-edited file
with non-uniform ticks would load, look right, and then be silently re-placed onto the uniform grid the
moment the count spinbox moved — which is *precisely* the reopen-corruption bug 4a was built to kill.
With speeds only, the model is exactly as expressive as the UI and **reopen is the identity by
construction**. `count` is `len(speeds)`; there is no count field either, for the same reason.

Two consequences fall out for free: changing `ticks` **rescales** the drawing (the grid stretches under
the same speeds), and there is no way for the count and the nodes to disagree.

**The node at tick 0 is not draggable and is not stored: it IS `v0`.** Two things follow, and they are
why the constraint pays for itself:

- a `custom` **never teleports** the leader at a junction, so cycle 3's
  `test_no_block_boundary_ever_teleports_the_leader` **extends** to `custom` instead of having to
  exclude it the way it excludes `preset`;
- storing that y would be a lie that goes stale the moment an earlier block changes. What is stored is
  exactly what the user commands — and there are no dead handles, which is the rule 4a paid for.

With no free nodes the polyline is flat at `v0` — degenerate but sensible, and `np.interp` handles a
single point natively.

**JSON** (§Scope IN 7). `custom` is a new kind, so cycle-3/4a files simply do not contain it: no version
field, no migration, nothing to detect. `to_json` needs no special case — the speeds are a plain list of
floats and `_block_json` already passes `params` through. `from_json` rebuilds them as a **tuple of
floats** for the same reason 4a's `bias` is a tuple: `Block` is a frozen dataclass compared by value, and
a list would break `from_json(to_json(s)) == s` while the numbers matched. A drawn block reads as
`{"kind": "custom", "ticks": 150, "params": {"nodes": [23.52, 4.0, 4.0, 12.0]}}` — still declarative,
still diffable, and smaller than the 225-byte `ramp` it sits next to.

### ② The advisory (same file, pure)

```python
def physics_gap(v, neutral):
    """Which segments this driver cannot produce, and the acceleration each one demands. PURE.

    The reference is the NEUTRAL, not an effective style: on a custom the pad is dead (see ④), so there
    is no bias to add. The question the advisory answers is "could THIS DRIVER do it", and the driver
    is the neutral.
    """
    acc = np.diff(v) / DT
    return (acc > neutral.a_max) | (acc < -neutral.b_max), acc
```

Returns a mask over the `n-1` segments plus the accelerations, so the page can both paint and quote the
number. The page turns the mask into the NaN-padded red curve the spike verified.

### ③ The drag (`sim/ui/scenario_page.py`, Qt only)

One `pg.TargetItem(movable=True)` per free node on the composer's preview. Vertical constraint by the
**measured** route — reconnect x in the `sigPositionChanged` handler (converges in 2 calls, x stays
locked) — not by subclassing `setPos`, which crashes inside `TargetItem.__init__` because the base
constructor passes a tuple.

Nodes ride on fixed ticks and move only in speed, so **the profile is a function of time by
construction**: no crossing, no re-sorting, no curve running backwards in time. That whole class of bug
does not exist rather than being handled. The rejected alternative is visible in the mock: a node
dragged past its neighbour makes `np.interp` — which requires increasing abscissae — draw a curve that
returns to the past; the repair is to sort, and then the node under the user's finger silently changes
index.

The **node-count spinbox** (1..25 free nodes, default 5) re-samples the current curve at the new
positions, so raising the count refines the drawing instead of erasing it. The cap is readability, not
speed: 150 handles peak at 10.12 ms.

### ④ What cycle 4a already decided

`custom` inherits the preset's two rules verbatim, because the reason is identical: `np.interp` never
receives a style, exactly as `_preset_samples` never does. So the pad **dies** on a custom and a custom
**never records a bias** — in code, `kind == "preset"` becomes `kind in ("preset", "custom")`, one word.

And the **nodes are params**, so by the 4a rule ("if a param cannot be expressed by a widget, add the
widget — do not add a dict") their widget is the handles on the plot. `_params_for("custom")` reads the
handles. One owner, no shadow list.

### ⑤ Where the red appears

On the composer's preview while you draw, **and** on the scenario curve below — but only on the samples
that come from `custom` blocks. Presets and parametric blocks are never painted: the first are a
different vehicle, the second are rate-limited by construction, and painting either would be exactly
the falsehood the preset measurement already exposed. It costs nothing: the page knows each block's
sample range from the running sum of `ticks`, so `materialise` is not touched.

## Errors and edge cases

| case | behaviour |
|---|---|
| a `custom` with zero free nodes | flat at `v0` (`np.interp` on a single point) |
| the node count changes | the current curve is re-sampled at the new grid: `np.interp(new_ticks, old_ticks, old_speeds)`; the drawing survives |
| `ticks` changes under a drawn block | free: the grid is derived, so the same speeds stretch over the new span |
| a node dragged below 0 or above 40 m/s | **clamped to `V_RANGE = (0.0, 40.0)`** — the same range the `valore` spinbox already uses. Not the plot's y range, which autoscales and would make the limit depend on what happens to be on screen. `v < 0` is the leader in reverse, which is not a scenario |
| the last node before `ticks-1` | the last value HOLDS to the end — same rule as `materialise` |
| an earlier block changes `v0` | node 0 follows; the first segment may turn red, which is honest |
| a bias or a pad click on a `custom` | ignored and **not recorded**; the pad greys out and says why |
| a cycle-3/4a JSON | loads unchanged: it contains no `custom` |

## Testing

> These are a *supplement* to the Scope check, not a substitute for it. See the warning in §Scope.

1. **A `custom` never teleports at a junction** — extend cycle 3's boundary test to include `custom`.
   This is the payoff of pinning node 0, so it is the test that proves the pin.
2. **The advisory is exact at the edge (teeth)** — a segment at exactly `b_max` is **not** red; one at
   `b_max + ε` is. The off-by-one is where this bug would live, and both directions must be pinned.
3. **The advisory never paints a preset (teeth)** — the false-red measurement becomes a test: a scenario
   containing `cut_in` and `following` has **zero** red samples on those stretches, whatever the neutral.
4. **A moved node changes only its two segments (teeth)** — a node that leaked into distant samples
   would still "change the curve" and pass a naive test.
5. **The nodes have one owner** — drag, then Add: the stored block equals what the handles showed.
   Reopening it puts the handles back where they were.
6. **The pad dies on a custom, and a custom records no bias** — the 4a pair, extended.
7. **JSON round-trips a `custom`** — `from_json(to_json(s)) == s`, with the speeds rebuilt as a
   **tuple** (a list compares unequal while printing identically -- the 4a `bias` trap, verbatim); and a
   file whose nodes were hand-edited to a different COUNT loads and draws at that count.
8. **The frame budget holds** with the handles live and the advisory recomputed per drag.
9. **A spline would fail test 1's sibling** — not a test, a note: if anyone swaps `np.interp` for a
   spline, tests 2 and 4 go soft and `v < 0` becomes reachable. The docstring says so.

Baseline: **244 tests green** (21 sim files + `test_champion_io.py`). Env `cf_sim`, no LAPACK. ⚠️ The
full suite takes ~3–4 minutes — a 2-minute default timeout looks like a hang and is not one.

## Known debt (unchanged, out of scope)

- `ReplayLog.seed` fed the scenario index (`sim/ui/app.py:591`).
- The Meso page passing `_PARAMS_GT` instead of `sc.params_gt` (`app.py:383`).
- `const` and `ramp` are one computation under two names; after this cycle the menu shows 5 kinds of
  which 2 are identical. Flagged, deliberately untouched.
- The `following` preset carries ±13 m/s² of noise-driven acceleration and the cut-in family jumps by
  design. Neither is a bug — but any future feature reasoning about "the leader's acceleration" must not
  read those as manoeuvres. This cycle is the first such feature, and §⑤ is how it avoids the trap.
