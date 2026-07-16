# Builder UX — duration edges + frozen autorange — Design Spec (cycle builder-UX)

**Date:** 2026-07-16 · **Branch/worktree:** `Simulator` · **Status:** design approved (user) → spec

## Goal

Make the scenario builder pleasant to edit: stop the composer preview from jumping while you drag a
node, and let you set a block's duration by dragging its right edge — on the block being composed and
on every block in the total preview.

The three post-verification requests (items 3, 4, 5). The bug behind them — a block added past the old
600-tick cap vanished — is already fixed: a scenario's length is now the SUM of its block ticks.

## Decided with the user (this brainstorming — do not relitigate)

- **Both item 4 AND item 5.** The duration drag lives on the composer preview (the block being
  composed) *and* on the total preview (every committed block). The user chose the completeness over
  the smaller "only item 5".
- **Autorange: fit-to-block, frozen during a node drag.** The composer's Y re-fits to the block's range
  on structural changes, never mid-node-drag.
- **The right-edge is one unified interaction.** Item 4 and item 5 are the same gesture — "drag a
  block's right edge to set its duration" — on two plots. One mechanism, two placements.

## Established facts (measured / read, not assumed)

- **`pg.InfiniteLine(angle=90, movable=True)` is a ready x-draggable vertical line.** MEASURED: it emits
  `sigPositionChanged`/`sigPositionChangeFinished`/`sigDragged`; `value()` returns the x-position;
  `setBounds([1, 600])` caps it in place (`setValue(700)` → 600). No hit-testing to write — same story as
  the 4b `TargetItem`.
- **`self._ticks = QSpinBox(); self._ticks.setRange(1, 600)`** (`scenario_page.py:115`) — the current cap
  is 600 and must be extended, because durations can now exceed 600.
- **Plot objects**: composer preview = `self._composer_plot` / `self._composer_curve`; total preview =
  `self._plot` / `self._curve` (`:154,158,164,170`).
- **Length is already the sum**: `_total_ticks()` = `sum(b.ticks for b in blocks)`, used in `_refresh`,
  `_on_use`, `_start_speed` (the just-shipped bug fix).
- **materialise is cheap at any length**: 50 min of scenario materialises in 4 ms, so a larger per-block
  cap costs nothing.
- **A preset is canonical at 600 samples** (`_PRESET_N`): `lib[name].v_leader[:n]` clamps at 600, so a
  preset block has no samples past 600 — its duration must cap there.

## Scope

> ⚠️ **This is the coverage checklist.** Check the plan against THIS list, not against §Testing (the
> cycle-4a lesson: the self-review verified the tests and missed a whole Scope requirement).

**IN**

1. **`DurationHandles`** (new, `sim/ui/duration_handles.py`) — a row of x-draggable vertical
   `InfiniteLine`s on a plot, each bound to `[min, cap]`, snapping to integer ticks, reporting
   `(id, new_ticks)` on drag. Isolated + tested alone, sibling to `DragHandles`.
2. **Item 4 — the composer's duration edge**: one `DurationHandles` line at `x = ticks` on the composer
   preview; dragging it writes `_ticks.setValue(new_ticks)` (the spinbox stays the owner).
3. **Item 5 — the total preview's boundaries**: one line per block at its right edge (the cumulative
   boundary); dragging the line for block *i* resizes block *i* (`_spec.blocks[i]` replaced with the new
   `ticks`), the total grows, blocks to the right shift. Internal boundaries are shown as reference.
4. **Item 3 — frozen autorange**: the composer's Y (and X) re-fits to the block on structural changes
   (enter a block, kind, params, duration, node count) but NOT during a node drag.
5. **`_ticks` range extended** to `[1, MAX_BLOCK_TICKS]` (6000 = 10 min/block); preset duration caps at
   600.
6. **The composer↔total sync**: dragging a boundary for a block that is currently open in the composer
   also updates `_ticks`, so the working copy never diverges from the timeline.

**OUT**

- **Left-edge / two-sided resize.** A block's left edge is the previous block's right edge, already
  draggable. Only right edges are handles.
- **Reordering blocks by drag**, drag-to-create, snapping to a grid — not asked, YAGNI.
- **The total preview's Y-freeze.** Resizing a block does not change its speed values, so the total's Y
  is stable during an item-5 drag (its X grows, which is the intended feedback). Only the composer needs
  the Y-freeze (item 3 is about the node drag, which is a composer gesture).
- **`materialise` and the frozen core** — untouched. This cycle is Qt-only plus a `_ticks` range and a
  new UI unit.

## Design

### ① `DurationHandles` (`sim/ui/duration_handles.py`, Qt only)

Sibling to `DragHandles`. Where `DragHandles` places y-draggable node dots, this places x-draggable
vertical lines — the same "no hit-testing, drive it from the signal" pattern.

```python
class DurationHandles:
    def __init__(self, plot, on_resize):
        # on_resize(id, new_ticks) -- called once per user drag
        ...
    def set_edges(self, edges):
        """edges: list of (id, start_tick, ticks, cap). Places a vertical line at start+ticks, bounded
        to [start+1, start+cap], carrying `id` and `start`. Silent (placement is not a user edit)."""
    def clear(self): ...
    def _on_drag(self, line):
        new_ticks = int(round(line.value())) - line._start        # snap to int, relative to the block
        # bounds already clamp value() into [start+1, start+cap]; report the resize
        if not self._placing:
            self._on_resize(line._id, max(1, new_ticks))
```

Same guards as `DragHandles`: a `_placing` flag so `set_edges` is silent, and `sigPositionChanged`
drives `_on_drag`. Snap to int in the handler; the `[start+1, start+cap]` bound is `setBounds` on the
line. **Not** subclassing anything — `InfiniteLine(movable=True)` is used as-is.

### ② The composer edge (item 4)

One edge, `id="composed"`, `start=0`, `ticks=_ticks.value()`, `cap = 600 if preset else MAX_BLOCK_TICKS`.
On resize → `self._ticks.setValue(new_ticks)`. The spinbox is the single owner; the line is another
input to it, exactly as the node handles are another input to `nodes`. Re-placed whenever the composed
block changes (kind/duration), so its cap tracks the kind (600 for a preset).

### ③ The total boundaries (item 5)

`set_edges([(i, cum[i], b.ticks, cap_i) for i, b in enumerate(blocks)])` where `cum[i]` is the start of
block *i* (the running sum before it) and `cap_i = 600 if b.kind=="preset" else MAX_BLOCK_TICKS`. On
resize `(i, new_ticks)`:

```python
blocks = list(self._spec.blocks)
blocks[i] = replace(blocks[i], ticks=new_ticks)   # a new frozen Block
self._spec = ScenarioSpec(..., blocks=tuple(blocks))
if self._composer_row == i:                        # the open working copy must not diverge
    self._loading = True; self._ticks.setValue(new_ticks); self._loading = False
self._refresh()          # re-materialise + re-place ALL boundaries at the new cumulative sums
```

The `if self._composer_row == i` line is the **composer↔total sync** (Scope IN 6): if the block being
resized in the total is the one open in the composer, its working-copy `_ticks` is updated in lockstep,
so a later Apply cannot silently revert the resize — the one-owner discipline across the two surfaces.

**Why re-placing all boundaries does not fight the drag**: dragging boundary *i* to x sets
`new_ticks = x - cum[i]`, so its new cumulative position is `cum[i] + new_ticks = x` — exactly where the
cursor left it. `cum[i]` is stable (only block *i*'s duration changed; blocks before it are untouched).
Boundaries after *i* shift right by the delta — correct. So the re-place is consistent with the gesture,
no jump.

### ④ Frozen autorange (item 3)

`_refresh_composer(*_, refit=True)` gains a `refit` flag. When `refit`, after drawing it calls
`_refit_composer()`:

```python
def _refit_composer(self):
    v = self._composer_curve.getOriginalDataset()[1]
    if v is None or not len(v): return
    lo, hi = float(np.min(v)), float(np.max(v))
    pad = max(0.5, 0.05 * (hi - lo))
    self._composer_plot.setYRange(lo - pad, hi + pad)      # fixes Y (disables auto)
    self._composer_plot.setXRange(0, max(1, self._ticks.value()))
```

The **node drag** is the only caller that passes `refit=False`: the node handles' `on_change` becomes
`lambda: self._refresh_composer(refit=False)`. Every other path (kind, params, duration, node count,
entering a block) uses the default `refit=True`. So the view is frozen during a node drag and re-fits on
any structural change. X follows `_ticks` (a duration drag grows the view — intended feedback).

### ⑤ The duration range (item 5's cap has a home)

`MAX_BLOCK_TICKS = 6000` is a new module constant in `sim/scenario_spec.py`, next to `V_RANGE` (10 min at
DT=0.1; materialise costs 4 ms even at 30000, so the cap is generosity, not a limit). Two consumers:
`self._ticks.setRange(1, MAX_BLOCK_TICKS)` (was `1, 600`), and the per-edge cap
(`600 if preset else MAX_BLOCK_TICKS`) in §② and §③. The preset cap is `_PRESET_N` (600), already the
canonical library length.

## Errors and edge cases

| case | behaviour |
|---|---|
| drag a preset's edge past 600 | `setBounds` caps at 600 (no samples beyond); the line stops |
| drag a boundary below its block's start | `setBounds` min = `start+1` (a block is ≥ 1 tick) |
| resize a block open in the composer | `_ticks` is updated too (no divergence) — §③ |
| a node drag changes the block's min/max | the Y stays frozen (no re-fit) — that IS the fix |
| change kind/params/duration/count | the Y re-fits, once, to the new curve |
| `_ticks` typed to a value > 600 for a preset | clamped to 600 by the preset cap (the composed edge cap) |
| the composed block is a preset | its edge caps at 600; the pad is already dead (4b), the note shows |
| a scenario with one block | one boundary (its right edge); dragging it grows the whole scenario |

## Testing

> A supplement to the Scope check, not a substitute.

1. **`DurationHandles` in isolation** — `set_edges` places lines at `start+ticks`, silent; a drag snaps
   to int and reports `(id, new_ticks)` once; `setBounds` caps at the block's cap; `clear` removes them.
2. **The composer edge writes the duration (teeth)** — dragging the composer edge to x sets
   `_ticks == round(x)`; and it is the spinbox that changed (one owner), not a shadow value.
3. **A boundary resizes its own block and grows the total (teeth)** — dragging block *i*'s boundary by
   +50 ticks makes `_spec.blocks[i].ticks` grow by 50 and `_total_ticks()` grow by 50; blocks *before* i
   are byte-identical, blocks *after* shift but keep their ticks.
4. **A preset edge caps at 600 (teeth)** — dragging a preset boundary past 600 leaves it at 600.
5. **The composer↔total sync (teeth)** — with block *i* open in the composer, resizing it in the total
   updates `_ticks`; a subsequent Apply does not revert the resize.
6. **The autorange is frozen during a node drag but re-fits on a kind change (teeth)** — a node drag
   leaves the composer Y range unchanged; changing the kind re-fits it. The node-drag path must NOT
   re-fit, or the jump the user reported returns.
7. **The frame budget holds** — the boundaries + re-place + advisory stay under 16.7 ms peak while
   dragging (re-measured, not inherited).
8. **No cycle-3/4a/4b regression** — the whole UI suite stays green (the composer, the pad, the nodes,
   the advisory are untouched in meaning).

Baseline: **275 green** (22 sim files + `test_champion_io.py`), + a new `test_sim_duration_handles.py`.
Env `cf_sim`, no LAPACK. ⚠️ The full suite takes ~4 min — a 2-minute default timeout looks like a hang.

## Known debt (unchanged, out of scope)

- `const` and `ramp` are one computation under two names — the menu shows 5 kinds of which 2 are
  identical. Flagged, deliberately untouched.
- `ReplayLog.seed` fed the scenario index (`app.py:591`); the Meso page passing `_PARAMS_GT` (`app.py:383`).
- Still on the user's list, for later cycles: name/delete/export (.csv+.mat), the cockpit scenario-preview
  dock (replacing Events + a time marker), and the dataset generator.
