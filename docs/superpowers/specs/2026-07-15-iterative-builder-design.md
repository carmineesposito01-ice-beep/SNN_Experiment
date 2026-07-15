# Iterative builder — per-block bias + block composer — Design Spec (cycle 4a)

**Date:** 2026-07-15 · **Branch/worktree:** `Simulator` · **Status:** design approved (user) → spec

## Goal

Turn the scenario builder from *fill a form, then look* into *build the piece while you see it*. Two
things: every block gets its **own behaviour, as a bias on a single neutral driver**; and the
right-hand panel becomes where you **compose a block and preview it in isolation before adding it**.

Cycle 4a of the 2026-07-15 follow-up. **Cycle 4b — the drag, the `custom` block, and the physics
advisory — is separate, and the split is not where the design first put it** (see §The split).

## Why the bias is additive (the user's reasoning, and it is right)

If each block carried an **absolute** `(a_max, b_max)`, "the leader's style" would stop existing:
there would be N unrelated styles and the driver would lose identity. With a neutral plus a bias there
is **one driver** — the neutral is the character, the bias is the circumstance: *in this stretch he is
edgier than usual*. It is the only way to have per-block behaviour without dissolving the person.

## The split — and why the advisory moved to 4b (MEASURED)

The first draft of this spec put the physics advisory ("light up the stretches the leader cannot do")
in 4a, reasoning that presets are verbatim and therefore *could* exceed a placid neutral. **Measured on
the real library, that reasoning collapses**: the advisory on presets is almost entirely false red.

| preset | acc min | acc max | steps a placid leader (1/1) "violates" |
|---|---:|---:|---|
| following | **−12.99** | **+13.09** | **503 / 599** |
| stop_and_go | −5.50 | +5.50 | **539 / 599** |
| sinusoidal | −3.30 | +3.30 | 479 / 599 |
| hard_brake | −7.00 | 0 | 30 / 599 |
| panic_stop | −9.00 | 0 | 24 / 599 |
| **cut_in** | **−75.00** | 0 | 1 / 599 |
| **aggressive_cut_in** | **−120.00** | 0 | 1 / 599 |
| **cut_out** | **−210.00** | 0 | 1 / 599 |

Two separate reasons, both fatal to the idea:

1. **The cut-in family's "−210 m/s²" is not a violation — it is a different vehicle.** `build_scenarios`
   sets `vl[t_cut:] = 0.45·v0` (`closed_loop_eval.py:367`): the profile jumps because the leader **is
   someone else** from that tick on. Painting that red would state a falsehood.
2. **`following` "violates" in 503 steps of 599** — that is the `rng.normal(0, 0.3)` noise
   (`closed_loop_eval.py:347`) divided by `DT=0.1`. It is measurement/driving noise, not a manoeuvre.

So the advisory only says something true about a **hand-drawn** profile, where red genuinely means *you
asked for the impossible*. It belongs with the drag. **4a = bias + composer. 4b = drag + `custom` +
advisory.** `custom` is not in 4a either: with no drag nothing could create one, and it would be dead code.

## Established facts (verified in code)

- **`LeaderStyle(a_max, b_max)` is today a single absolute point, global to the `ScenarioSpec`**
  (`sim/scenario_spec.py:35-45`); `Block(kind, ticks, params)` (`:28-32`) has no style of its own, and
  `materialise` passes `spec.style` to every block (`:139-146`).
- **The rate limiting is what makes generated profiles physical.** `_rate_limited_toward` (`:57-70`)
  clips toward the target at the style's rate; `test_no_block_boundary_ever_teleports_the_leader` pins
  that no junction jumps, under all four quadrants — and already excludes `preset`, which is verbatim.
- **`DT = 0.1`** (`config.py:63`).
- **The live preview has a 16.7 ms budget** and `materialise` already eats 3.68 ms of it (measured), so
  anything added per-refresh must stay vectorised.

## Scope

**IN**
1. `Block.bias: tuple | None` — `(Δa, Δb)`; the effective style is `clamp(neutral + bias)`.
2. `effective_style(block, neutral)` — pure.
3. The right-hand panel becomes a **block composer**: kind, params, **this block's bias on the 2-D pad**,
   the block's **own preview**, then Add. Clicking a timeline row reopens it there; Add becomes Apply.
4. The neutral gets its own control, distinct from the per-block bias.

**OUT**
- **The drag, `custom`, and the advisory → cycle 4b.** Together, because they only make sense together
  (see §The split). The drag is also the one piece of this session with **no measured number behind it**:
  mouse interaction on pyqtgraph, hit-testing, undo.
- **A leader with its own dynamics.** Still parked. The tension is now resolved the other way: the user
  chose the animator, so in 4b the advisory — not a dynamics model — is what keeps physics honest.
- **`params_gt` editing** — unchanged from cycle 3: it is the oracle, and the Meso page ignores it.

## Design

### ① The bias (`sim/scenario_spec.py`)

```python
@dataclass(frozen=True)
class Block:
    kind: str
    ticks: int
    params: dict
    bias: tuple = None        # (da, db) m/s^2 on the neutral; None = the neutral itself


def effective_style(block, neutral):
    """The style this block actually runs with: neutral + bias, clamped to the plane.

    Additive on purpose. An absolute per-block style would leave N unrelated styles and no driver;
    with a bias there is ONE driver -- the neutral is the character, the bias is the circumstance.
    Clamped, not rejected: a bias that would leave the plane is pinned at the edge, because the bias
    is a nudge and the plane is the physics.
    """
    if block.bias is None:
        return neutral
    da, db = block.bias
    return LeaderStyle(a_max=float(np.clip(neutral.a_max + da, *A_MAX_RANGE)),
                       b_max=float(np.clip(neutral.b_max + db, *B_MAX_RANGE)))
```

`materialise` calls it per block instead of passing `spec.style` straight through. **A block with
`bias=None` behaves exactly as today**, so every scenario built in cycle 3 materialises byte-identically
— pinned by a test.

`ScenarioSpec.style` changes **in meaning, not in name**: it is now the neutral. Renaming the field
would break the JSON round-trip and the cycle-3 files for no gain; the docstring carries the change.
`Block.bias` defaults to `None`, so `from_json` reads cycle-3 files unchanged and `to_json` omits it
when absent — the format stays backward-compatible without a version field.

### ② The block composer (`sim/ui/scenario_page.py`)

The right-hand half stops being a bare style pad and becomes: kind picker · params · **the 2-D pad now
editing this block's bias**, with the neutral shown as a second, dimmer marker · **the block's own
preview** · Add. Clicking a timeline row loads it back; Add becomes Apply.

Two previews answer two questions: the small one is *what does this piece do*, the big one is *what does
the scenario do*. Both come from `materialise` — the composer materialises a **one-block spec starting
from the speed the previous blocks leave behind**, so the piece you judge is the piece you get. That
starting speed is the composer's only coupling to the timeline, and it is what makes the small preview
honest rather than decorative.

## Errors and edge cases

| case | behaviour |
|---|---|
| bias pushes the style off the plane | clamped at the edge (the bias is a nudge, the plane is physics) |
| composing the first block | starts from `v_init`, same as materialise |
| composing a block in the middle | starts from where the previous blocks leave off; editing an earlier block refreshes it |
| bias on a `preset` block | ignored, and the composer says so — a preset is verbatim, the style never touched it (cycle 3) |
| cycle-3 JSON, no `bias` field | loads unchanged; `bias=None` means "the neutral" |

## Testing

1. **`bias=None` is byte-identical to cycle 3** — a spec of unbiased blocks materialises exactly as
   before. Regression on everything already built.
2. **The bias moves only its own block (teeth)** — biasing block 2 leaves blocks 1 and 3 byte-identical.
   The per-block scope is the whole feature; a leak would pass a naive "it changed" test.
3. **The bias is additive, not absolute (teeth)** — the same bias on two different neutrals yields two
   different effective styles, and `neutral + bias` matches `effective_style` exactly. An implementation
   that quietly treats the bias as an absolute passes test 2 and fails this.
4. **Clamping at the edge** — a bias beyond the plane pins at the limit and does not raise.
5. **A bias on a `preset` changes nothing** — the preset stays byte-identical to the library. Guards the
   cycle-3 invariant from the new knob.
6. **JSON is backward-compatible** — a cycle-3 file (no `bias`) round-trips and materialises identically;
   a biased spec round-trips byte-exact.
7. **The composer previews what you get (teeth)** — the small preview equals the corresponding slice of
   the full scenario after Add. It is the claim the whole feature rests on.
8. **The frame budget holds** — the composer's extra materialise keeps the refresh under 16.7 ms, peak.

Baseline: **224 tests green** (21 sim files + `test_champion_io.py`). Env `cf_sim`, no LAPACK.

## Known debt (unchanged, out of scope)

- `ReplayLog.seed` fed the scenario index (`sim/ui/app.py:591`).
- The Meso page passing `_PARAMS_GT` instead of `sc.params_gt` (`app.py:383`).
- **New, worth knowing**: the `following` preset carries ±13 m/s² of noise-driven acceleration and the
  cut-in family jumps by design (a different vehicle). Neither is a bug — but any future feature that
  reasons about "the leader's acceleration" must not read those as manoeuvres.
