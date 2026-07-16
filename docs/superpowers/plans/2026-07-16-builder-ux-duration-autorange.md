# Builder UX — duration edges + frozen autorange — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set a block's duration by dragging its right edge — on the composer preview and on every block in the total preview — and stop the composer preview from jumping while you drag a node.

**Architecture:** A new isolated `DurationHandles` (x-draggable `pg.InfiniteLine`s, **commit-on-finish**) placed on the composer plot (one edge → writes `_ticks`) and the total plot (one per block → resizes `_spec.blocks[i]`, total grows). The composer's autorange gains a `refit` flag re-fitted on structural changes but frozen during a node drag. `materialise` and the frozen core are untouched.

**Tech Stack:** Python 3, numpy, PySide6, pyqtgraph 0.14, pytest. Conda env `cf_sim`.

**Spec:** `docs/superpowers/specs/2026-07-16-builder-ux-duration-autorange-design.md`. **Read §Scope first** (the coverage checklist), not §Testing.

---

## Before you start

**Worktree:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator`, branch `Simulator`.

**Test runner** (⚠️ never `conda run -n cf_sim python -m pytest`):

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_duration_handles.py -q
```

**Full suite** = the `test_sim_*.py` files + `tests/test_champion_io.py`. **Baseline: 275 passed.** This plan
adds `tests/test_sim_duration_handles.py`. ⚠️ The full suite takes **~4 minutes** — a 2-minute default
timeout looks like a hang; give it ≥420 s or run it in the background.

**Grounded facts (measured in the spike — do not re-derive):**
- `pg.InfiniteLine(angle=90, movable=True)` is x-draggable. `value()` = the x-position. `setBounds([lo,hi])`
  clamps `value()` in place and `sigPositionChanged` reports the **clamped** value.
- **`setValue` emits `sigPositionChanged` but NOT `sigPositionChangeFinished`** (Finished = real mouse
  release). A test simulates a release with `line.sigPositionChangeFinished.emit(line)`.
- `InfiniteLine.moving` is True during a real drag (not used in this plan — commit-on-finish sidesteps it).
- `self._ticks = QSpinBox(); self._ticks.setRange(1, 600)` (`scenario_page.py:115`).
- Plot objects: `self._composer_plot` / `self._composer_curve`; `self._plot` / `self._curve`.
- `_total_ticks()` = `sum(b.ticks for b in blocks)` already drives `_refresh`/`_on_use`.

**Why commit-on-finish (not live):** the resize fires on drag **release**, so re-placing the handle lines
(which clears + recreates them) happens when no drag is active — it cannot destroy the line under the
cursor, and the value→handle loop cannot form. During the drag only the line moves (immediate feedback);
the curve + boundaries snap on release. Consequence: the duration drag does **not** stress the 60 fps frame
budget (materialise runs once per release, not per frame).

**Hard rules:** frozen core `sim/{state,stepper,backend,probe,events,eventprop_stepper}.py`;
`utils/closed_loop_eval.py` INVARIANT; **`materialise` untouched**; no numpy LAPACK; commits conventional,
**no `Co-Authored-By`**; **Edit not `replace()`**; **anchor verifications to the section**.

**Process lessons (do not repeat):** the plan self-review runs against the spec's **§Scope**, not §Testing;
a test asserting "change X → Y moves" needs the **causal path verified** — compute the expected value with a
probe before the assert (this session got it wrong 4 times: a global scale that doesn't break locality, a
float boundary, a too-gentle slope, an in-place drag that skips the correction); the **sabotage must
exercise the property** it guards.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `sim/ui/duration_handles.py` | **new** — x-draggable duration edges, commit-on-finish | isolated, tested alone |
| `sim/scenario_spec.py` | pure model | `+MAX_BLOCK_TICKS` constant only |
| `sim/ui/scenario_page.py` | the composer | wire the composer edge (item 4), the total boundaries (item 5), the frozen autorange (item 3), extend `_ticks` range |
| `tests/test_sim_duration_handles.py` | **new** — the drag unit | |
| `tests/test_sim_ui_smoke.py` | the composer | append the wiring + autorange tests |

Order: the isolated unit → the constant → item 4 → item 5 → item 3 → verify.

---

### Task 1: `DurationHandles` — x-draggable duration edges (isolated)

**Files:**
- Create: `sim/ui/duration_handles.py`
- Test: `tests/test_sim_duration_handles.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

import pyqtgraph as pg                                     # noqa: E402
from PySide6.QtWidgets import QApplication                 # noqa: E402
from sim.ui.duration_handles import DurationHandles        # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_set_edges_places_a_line_at_start_plus_ticks(qapp):
    plot = pg.PlotWidget()
    h = DurationHandles(plot, on_resize=lambda *a: None)
    h.set_edges([(0, 0, 150, 6000), (1, 150, 200, 6000)])
    assert len(h) == 2
    assert h._lines[0].value() == 150            # start 0 + 150 ticks
    assert h._lines[1].value() == 350            # start 150 + 200 ticks


def test_set_edges_is_silent(qapp):
    """Placement is not a resize -- firing on_resize here would refresh mid-build."""
    plot = pg.PlotWidget()
    got = []
    h = DurationHandles(plot, on_resize=lambda *a: got.append(1))
    h.set_edges([(0, 0, 100, 600)])
    assert got == []


def test_a_finished_drag_reports_ticks_relative_to_the_start(qapp):
    """commit-on-finish: setValue moves the line, the release (sigPositionChangeFinished) commits.
    new_ticks is measured from the block's START, not the absolute x."""
    plot = pg.PlotWidget()
    got = []
    h = DurationHandles(plot, on_resize=lambda eid, t: got.append((eid, t)))
    h.set_edges([(1, 150, 200, 6000)])           # block 1 starts at 150, 200 ticks -> line at 350
    line = h._lines[0]
    line.setValue(300)                           # dragged left to x=300
    line.sigPositionChangeFinished.emit(line)    # released
    assert got == [(1, 150)]                      # 300 - 150


def test_the_bound_caps_the_duration(qapp):
    """setBounds([start+1, start+cap]) clamps in place; a preset (cap 600) cannot go past 600."""
    plot = pg.PlotWidget()
    got = []
    h = DurationHandles(plot, on_resize=lambda eid, t: got.append(t))
    h.set_edges([(0, 0, 100, 600)])              # cap 600
    line = h._lines[0]
    line.setValue(900)                           # try past the cap
    line.sigPositionChangeFinished.emit(line)
    assert got == [600]                           # clamped to start+cap=600 -> 600 ticks


def test_clear_removes_every_line(qapp):
    plot = pg.PlotWidget()
    h = DurationHandles(plot, on_resize=lambda *a: None)
    h.set_edges([(0, 0, 100, 600), (1, 100, 100, 600)])
    h.clear()
    assert len(h) == 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_duration_handles.py -q
```

Expected: FAIL — `ModuleNotFoundError: No module named 'sim.ui.duration_handles'`.

- [ ] **Step 3: Implement**

Create `sim/ui/duration_handles.py`:

```python
"""DurationHandles -- x-draggable vertical edges on a pyqtgraph plot, one per block, that set a block's
duration by dragging its right edge.

COMMIT-ON-FINISH: on_resize fires on the drag RELEASE (sigPositionChangeFinished), not continuously.
That is deliberate -- re-placing the lines (clear + recreate) then happens with no drag active, so it
cannot destroy the line under the cursor, and the value->handle loop cannot form. During the drag only
the line moves (immediate feedback); the curve + boundaries snap on release.

Sibling to DragHandles. Same "no hit-testing, drive it from the signal" pattern; pg.InfiniteLine is used
as-is (subclassing it crashes, per the 4b lesson with TargetItem). setBounds clamps in place and the
signal reports the CLAMPED value (measured).
"""
import pyqtgraph as pg


class DurationHandles:
    def __init__(self, plot, on_resize):
        self._plot = plot
        self._on_resize = on_resize            # on_resize(id, new_ticks) -- once, on drag release
        self._lines = []
        self._placing = False

    def __len__(self):
        return len(self._lines)

    def set_edges(self, edges):
        """edges: list of (id, start, ticks, cap). A vertical line at start+ticks, bounded to
        [start+1, start+cap] so it cannot cross the block's start or exceed its cap. Silent."""
        self.clear()
        self._placing = True
        try:
            for eid, start, ticks, cap in edges:
                ln = pg.InfiniteLine(pos=start + ticks, angle=90, movable=True,
                                     pen=pg.mkPen("#8ab4d8", width=2))
                ln.setBounds([start + 1, start + cap])
                ln._id = eid
                ln._start = int(start)
                ln.sigPositionChangeFinished.connect(self._on_finish)
                self._plot.addItem(ln)
                self._lines.append(ln)
        finally:
            self._placing = False

    def clear(self):
        for ln in self._lines:
            self._plot.removeItem(ln)
        self._lines = []

    def _on_finish(self, line):
        if self._placing:
            return
        self._on_resize(line._id, max(1, int(round(line.value())) - line._start))
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_duration_handles.py -q
```

Expected: PASS (5).

- [ ] **Step 5: Sabotage-check, then commit**

Confirm `test_a_finished_drag_reports_ticks_relative_to_the_start` has teeth: temporarily change
`- line._start` to `- 0` and rerun — it must FAIL (reports 300, not 150). Revert.

```bash
git add sim/ui/duration_handles.py tests/test_sim_duration_handles.py
git commit -m "feat(sim): DurationHandles -- x-draggable duration edges, commit-on-finish

A row of pg.InfiniteLines that set a block's duration by dragging its right edge.
Commit-on-finish (on_resize fires on the release, sigPositionChangeFinished) so
re-placing the lines cannot destroy the one under the cursor and no value<->handle
loop forms. setBounds caps in place; new_ticks is measured from the block's start.
Isolated + tested alone, sibling to DragHandles."
```

---

### Task 2: `MAX_BLOCK_TICKS` — durations may exceed 600

**Files:**
- Modify: `sim/scenario_spec.py:22-24` (constants)
- Test: `tests/test_sim_scenario_spec.py` (append)

- [ ] **Step 1: Write the failing test**

```python
def test_a_block_longer_than_600_materialises_fully():
    """The length is the sum of ticks; a block > 600 is not special. MAX_BLOCK_TICKS is the UI cap,
    not a model limit -- materialise handles any N (4 ms at 30000)."""
    from sim.scenario_spec import MAX_BLOCK_TICKS
    assert MAX_BLOCK_TICKS == 6000
    n = 1500
    vl = materialise(_spec([Block("const", n, {"v": 12.0})]), _PG, N=n).v_leader
    assert vl.shape == (n,)
    np.testing.assert_allclose(vl, 12.0)
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q -k longer_than_600
```

Expected: FAIL — `ImportError: cannot import name 'MAX_BLOCK_TICKS'`.

- [ ] **Step 3: Implement**

In `sim/scenario_spec.py`, add the constant next to `V_RANGE` (`:24`):

```python
V_RANGE = (0.0, 40.0)
MAX_BLOCK_TICKS = 6000         # the builder's per-block duration cap: 10 min at DT=0.1. materialise is
                               # vectorised (4 ms even at 30000), so this is generosity, not a limit.
```

- [ ] **Step 4: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sim/scenario_spec.py tests/test_sim_scenario_spec.py
git commit -m "feat(sim): MAX_BLOCK_TICKS -- the builder's per-block duration cap (6000)

10 min at DT=0.1. materialise is vectorised (4 ms at 30000), so the cap is generosity,
not a limit -- a block longer than the old 600 materialises fully."
```

---

### Task 3: Item 4 — the composer's duration edge

**Files:**
- Modify: `sim/ui/scenario_page.py` (imports, `__init__`, `_ticks` range, `_refresh_composer`, `+_place_composer_edge`)
- Test: `tests/test_sim_ui_smoke.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_the_composer_edge_writes_the_duration(qapp):
    """TEETH: dragging the composer edge sets the block's duration, and it is the SPINBOX that changed
    (one owner), not a shadow value. Simulate the drag: setValue on the edge line + release."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 300, {"to_v": 2.0})]))
    page.compose_new("ramp", ticks=150, params={"to_v": 18.0})
    edge = page._composer_edge._lines[0]
    edge.setValue(250)                                     # drag the edge to x=250
    edge.sigPositionChangeFinished.emit(edge)              # release
    assert page._ticks.value() == 250                      # the spinbox is the owner
    assert page._composer_block().ticks == 250


def test_the_composer_edge_caps_a_preset_at_600(qapp):
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 300, {"to_v": 2.0})]))
    page.compose_new("preset", ticks=200, params={"name": "hard_brake"})
    edge = page._composer_edge._lines[0]
    edge.setValue(5000)                                    # try to drag a preset past 600
    edge.sigPositionChangeFinished.emit(edge)
    assert page._ticks.value() == 600                      # capped at the library length
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "composer_edge" -p no:cacheprovider
```

Expected: FAIL — `AttributeError: 'ScenarioPage' object has no attribute '_composer_edge'`.

- [ ] **Step 3: Implement**

Extend the imports (`:17-20`):

```python
from sim.scenario_spec import (A_MAX_RANGE, B_MAX_RANGE, V_RANGE, MAX_BLOCK_TICKS, _KINDS,
                               _custom_node_ticks, Block, LeaderStyle, ScenarioSpec, block_of_sample,
                               materialise, physics_gap)
from sim.ui.drag_handles import DragHandles
from sim.ui.duration_handles import DurationHandles
```

Extend the `_ticks` range (`:115`):

```python
        self._ticks = QSpinBox(); self._ticks.setRange(1, MAX_BLOCK_TICKS); self._ticks.setValue(150)
```

After the composer plot's curves are built (after `self._composer_red`, `:159`), add the edge:

```python
        self._composer_edge = DurationHandles(self._composer_plot, on_resize=self._on_composer_edge)
```

Add the handler and the placer (near `_refresh_composer`):

```python
    def _on_composer_edge(self, _id, new_ticks):
        """The composer edge was released: write the duration to its single owner, the spinbox."""
        self._ticks.setValue(int(new_ticks))

    def _place_composer_edge(self):
        """One edge at x = ticks, capped by kind (a preset stops at its 600-sample library length).
        Re-placed on structural changes only (via the refit path); a drag is committed on release, so
        re-placing here never runs mid-drag."""
        if self._spec is None:
            return
        cap = 600 if self._composer_kind() == "preset" else MAX_BLOCK_TICKS
        self._composer_edge.set_edges([("composed", 0, int(self._ticks.value()), cap)])
```

Call `_place_composer_edge()` from the refit path of `_refresh_composer` (Task 5 adds `refit`; place it
where `_refit_composer()` is called). **Until Task 5 lands**, call it at the end of `_refresh_composer`
for now:

```python
    # in _refresh_composer, after setData:
        self._place_composer_edge()
```

⚠️ Task 5 moves this into the `if refit:` branch so a node drag does not re-place the edge. Do not
leave it firing on every refresh.

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "composer_edge" -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/scenario_page.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): drag the composer block's right edge to set its duration

A DurationHandles edge on the composer preview; releasing it writes _ticks (the single
owner). Capped by kind -- a preset stops at 600, its library length. _ticks range
extended to MAX_BLOCK_TICKS so durations can exceed the old 600."
```

---

### Task 4: Item 5 — the total preview's boundaries

**Files:**
- Modify: `sim/ui/scenario_page.py` (`__init__`, `_refresh`, `+_place_boundaries`, `+_on_boundary_resize`)
- Test: `tests/test_sim_ui_smoke.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_a_boundary_resizes_only_its_block_and_grows_the_total(qapp):
    """TEETH: dragging block 1's boundary by +80 grows block 1 by 80 and the total by 80; block 0 is
    byte-identical, block 2 keeps its ticks (it only shifts). The causal path was checked: cum[1]=200,
    so a drag to x=380 -> new_ticks = 380-200 = 180 = 100+80."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("const", 200, {"v": 21.0}),
                          Block("ramp", 100, {"to_v": 5.0}),
                          Block("const", 150, {"v": 5.0})]))
    before0 = materialise(page._spec, page._params_gt, page._total_ticks()).v_leader[:200].copy()
    total_before = page._total_ticks()                     # 450
    line = page._boundaries._lines[1]                      # block 1's edge, at cum=200+100=300
    line.setValue(380)                                     # drag right by 80
    line.sigPositionChangeFinished.emit(line)
    assert page._spec.blocks[1].ticks == 180               # 100 + 80
    assert page._spec.blocks[2].ticks == 150               # untouched (only shifts)
    assert page._total_ticks() == total_before + 80
    after0 = materialise(page._spec, page._params_gt, page._total_ticks()).v_leader[:200]
    np.testing.assert_array_equal(before0, after0)         # block 0 byte-identical


def test_a_preset_boundary_caps_at_600(qapp):
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("preset", 300, {"name": "hard_brake"}),
                          Block("const", 100, {"v": 5.0})]))
    line = page._boundaries._lines[0]                      # preset edge, at 300
    line.setValue(5000)
    line.sigPositionChangeFinished.emit(line)
    assert page._spec.blocks[0].ticks == 600               # capped at the library length


def test_resizing_an_open_row_syncs_the_composer(qapp):
    """TEETH: the composer<->total sync. Block 0 is open in the composer; resizing it in the total
    updates _ticks, so a later Apply does not revert the resize."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("const", 200, {"v": 21.0}), Block("ramp", 100, {"to_v": 5.0})]))
    page._on_row_selected(0)                               # open block 0 in the composer
    line = page._boundaries._lines[0]                      # block 0's edge, at 200
    line.setValue(320)                                     # resize to 320
    line.sigPositionChangeFinished.emit(line)
    assert page._ticks.value() == 320                      # composer synced
    page._on_add()                                         # Apply must not revert it
    assert page._spec.blocks[0].ticks == 320
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "boundary or resizing_an_open_row" -p no:cacheprovider
```

Expected: FAIL — `AttributeError: 'ScenarioPage' object has no attribute '_boundaries'`.

- [ ] **Step 3: Implement**

Add `from dataclasses import replace` at the top of `scenario_page.py`. After `self._scenario_red`
(`:171`), add the boundaries on the total plot:

```python
        self._boundaries = DurationHandles(self._plot, on_resize=self._on_boundary_resize)
```

Add `_place_boundaries` and `_on_boundary_resize`, and call `_place_boundaries()` at the end of
`_refresh`:

```python
    def _place_boundaries(self):
        """One edge per block at its right edge (its cumulative boundary), capped by kind. Re-placed
        on every _refresh; a drag commits on release, so this never runs mid-drag."""
        if self._spec is None or not self._spec.blocks:
            self._boundaries.clear()
            return
        edges, cum = [], 0
        for i, b in enumerate(self._spec.blocks):
            cap = 600 if b.kind == "preset" else MAX_BLOCK_TICKS
            edges.append((i, cum, int(b.ticks), cap))
            cum += int(b.ticks)
        self._boundaries.set_edges(edges)

    def _on_boundary_resize(self, i, new_ticks):
        """Block i's boundary was released: resize block i (the total grows), sync the composer if
        that row is open, then refresh (which re-places all boundaries at the new cumulative sums)."""
        if self._spec is None or i >= len(self._spec.blocks):
            return
        blocks = list(self._spec.blocks)
        blocks[i] = replace(blocks[i], ticks=int(new_ticks))
        self._spec = ScenarioSpec(name=self._spec.name, blocks=tuple(blocks),
                                  style=self._spec.style, s_init=self._spec.s_init,
                                  v_init=self._spec.v_init)
        if self._composer_row == i:                        # the open working copy must not diverge
            self._loading = True
            self._ticks.setValue(int(new_ticks))
            self._loading = False
        self._refresh_list()
        self._refresh()
```

And at the end of `_refresh` (after `self._scenario_red.setData(...)`):

```python
        self._place_boundaries()
```

⚠️ **Why re-placing all boundaries on `_refresh` does not fight the drag** (spec §③): the resize commits
on RELEASE (`sigPositionChangeFinished`), so `_refresh` → `set_edges` runs with no drag active — it
cannot destroy a line under the cursor. And dragging boundary *i* to x gives `new_ticks = x - cum[i]`, so
its re-placed position is `cum[i] + new_ticks = x` — where the cursor left it; blocks before *i* are
untouched so `cum[i]` is stable.

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "boundary or resizing_an_open_row" -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Sabotage-check the sync, then commit**

Confirm `test_resizing_an_open_row_syncs_the_composer` has teeth: temporarily comment out the
`if self._composer_row == i:` block and rerun `-k resizing_an_open_row` — Apply now reverts the resize
(the composer's stale `_ticks` overwrites it), so it must FAIL. Revert.

```bash
git add sim/ui/scenario_page.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): drag a block's boundary in the total preview to resize it

One DurationHandles edge per block on the total preview; releasing block i's edge
resizes block i (the total grows, later blocks shift), and if that block is open in the
composer its _ticks is synced so a later Apply cannot revert it. A preset caps at 600.
Re-placing all boundaries on refresh does not fight the drag -- it commits on release,
and the dragged edge re-places exactly where the cursor left it (cum[i]+new_ticks = x)."
```

---

### Task 5: Item 3 — the frozen autorange

**Files:**
- Modify: `sim/ui/scenario_page.py` (`_refresh_composer`, `+_refit_composer`, the node-handles `on_change`)
- Test: `tests/test_sim_ui_smoke.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_the_composer_autorange_is_frozen_during_a_node_drag(qapp):
    """TEETH: a node drag must NOT re-fit the Y range -- that IS the jump the user reported. Causal
    path checked: dragging a node up changes the block's max, so an auto-refit would move YRange."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("const", 600, {"v": 21.0})]))
    page.compose_new("custom", ticks=150, params={"nodes": [12.0, 12.0, 12.0]})
    y_before = page._composer_plot.getViewBox().viewRange()[1]
    page._handles._items[1].setPos(page._handles._items[1]._tick, 2.0)   # drag a node way down
    y_after = page._composer_plot.getViewBox().viewRange()[1]
    assert y_after == y_before                             # the view did NOT jump


def test_the_composer_autorange_refits_on_a_kind_change(qapp):
    """A structural change DOES re-fit: the view frames the new block."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("const", 600, {"v": 21.0})]))
    page.compose_new("const", ticks=150, params={"v": 21.0})      # a flat block ~21
    y_flat = page._composer_plot.getViewBox().viewRange()[1]
    page._kind.setCurrentText("ramp"); page._value.setValue(2.0)  # a ramp 21 -> 2, a wider range
    y_ramp = page._composer_plot.getViewBox().viewRange()[1]
    assert y_ramp != y_flat                                # re-fitted to the new, wider curve
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "autorange" -p no:cacheprovider
```

Expected: FAIL — the node drag currently lets pyqtgraph autorange, so `y_after != y_before`.

- [ ] **Step 3: Implement**

Give `_refresh_composer` a `refit` flag and add `_refit_composer`. Replace the `_refresh_composer`
signature line and add the refit call + move the edge placement into it:

```python
    def _refresh_composer(self, *_, refit=True):
        """Materialise a ONE-block spec... `refit` re-fits the view and re-places the composer edge;
        a NODE drag passes refit=False so the view does not jump (that is the item-3 fix)."""
        if self._loading or self._spec is None:
            return
        blk = self._composer_block()
        upto = self._composer_row if self._composer_row is not None else len(self._spec.blocks)
        one = ScenarioSpec(name="_", blocks=(blk,), style=self._spec.style,
                           s_init=self._spec.s_init, v_init=self._start_speed(upto))
        v = materialise(one, self._params_gt, blk.ticks).v_leader
        self._composer_curve.setData(v)
        if blk.kind == "custom":
            mask, _ = physics_gap(v, self._neutral())
            self._composer_red.setData(self._red_from_mask(v, mask))
        else:
            self._composer_red.setData([])
        if refit:
            self._refit_composer()
            self._place_composer_edge()

    def _refit_composer(self):
        """Fix the composer's Y to the block's range (+pad) and X to the block's length. Fixing them
        disables pyqtgraph's autorange, so a subsequent node-drag redraw does NOT move the view."""
        v = self._composer_curve.getOriginalDataset()[1]
        if v is None or not len(v):
            return
        lo, hi = float(np.min(v)), float(np.max(v))
        pad = max(0.5, 0.05 * (hi - lo))
        self._composer_plot.setYRange(lo - pad, hi + pad)
        self._composer_plot.setXRange(0, max(1, int(self._ticks.value())))
```

Remove the unconditional `self._place_composer_edge()` you added at the end of `_refresh_composer` in
Task 3 — it now lives inside `if refit:`.

Point the node handles' `on_change` at the non-refitting path. In `__init__`, change:

```python
        self._handles = DragHandles(self._composer_plot,
                                    on_change=lambda: self._refresh_composer(refit=False))
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "autorange" -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Sabotage-check, then commit**

Confirm the freeze test has teeth: temporarily make the node handles' `on_change` use the default
(`on_change=self._refresh_composer`, i.e. refit=True) and rerun `-k frozen_during_a_node_drag` — the view
now re-fits on the node drag, so `y_after != y_before` and it must FAIL. Revert.

```bash
git add sim/ui/scenario_page.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): freeze the composer autorange during a node drag

_refresh_composer gains a refit flag; refit fixes the Y range to the block (+pad) and X
to its length (disabling pyqtgraph autorange) and re-places the composer edge. The node
drag is the only caller passing refit=False, so dragging a node no longer makes the view
jump -- the item-3 fix -- while a kind/params/duration change still re-frames the block."
```

---

### Task 6: frame budget, full verification, render-verify, docs

**Files:**
- Modify: `tests/test_sim_ui_smoke.py` (append), `document/SIMULATOR_SESSION_RESUME.md`, `document/SIMULATOR_ARCHITECTURE.md`

- [ ] **Step 1: A budget test — the node drag stays in a frame (commit-on-finish means the duration drag is per-release, not per-frame)**

```python
def test_node_drag_still_fits_in_a_frame_with_the_autorange_change(qapp):
    """The autorange change touches the node-drag path (now refit=False). Confirm the node drag -- the
    only LIVE drag -- still peaks under 16.7 ms. The duration drag is commit-on-finish, so it is not a
    per-frame cost and is not measured here."""
    import time
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("custom", 150, {"nodes": [21.0] * 25}),
                          Block("ramp", 150, {"to_v": 2.0})]))
    page.compose_new("custom", ticks=150, params={"nodes": [21.0] * 25})
    for _ in range(3):
        h = page._handles._items[0]; h.setPos(h._tick, 15.0)
    ts = []
    for k in range(40):
        h = page._handles._items[k % 25]
        t0 = time.perf_counter()
        h.setPos(h._tick, 5.0 + 0.1 * k)
        ts.append((time.perf_counter() - t0) * 1000)
    assert max(ts) < 16.7, f"node drag peaks at {max(ts):.2f} ms"
```

Run it: `... -m pytest tests/test_sim_ui_smoke.py -q -k node_drag_still_fits`. Expected: PASS. If it
fails, the refit=False path is doing more than a setData — check it is not re-fitting.

- [ ] **Step 2: Run the whole suite with the real number**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest \
  tests/test_sim_scenario_spec.py tests/test_sim_ui_smoke.py tests/test_sim_drag_handles.py \
  tests/test_sim_duration_handles.py tests/test_champion_io.py \
  $(ls tests/test_sim_*.py | grep -vE "scenario_spec|ui_smoke|drag_handles|duration_handles") \
  -q -p no:cacheprovider
```

Expected: **PASS**. Baseline 275 + new (T1:5, T2:1, T3:2, T4:3, T5:2, T6:1 → **289**). Write the **real**
number everywhere. Give it ≥420 s.

- [ ] **Step 3: Verify the frozen core, the invariant, and materialise are untouched**

```bash
git diff --stat origin/Simulator -- sim/state.py sim/stepper.py sim/backend.py sim/probe.py sim/events.py sim/eventprop_stepper.py utils/closed_loop_eval.py
```

Expected: **empty**. Also confirm `materialise`'s body is unchanged: `git diff origin/Simulator -- sim/scenario_spec.py` should show only the `MAX_BLOCK_TICKS` constant added.

- [ ] **Step 4: Render-verify — actually look at it**

`QT_QPA_PLATFORM=windows` (offscreen renders text as tofu). Build `SimApp`, `set_mode(3)`, a multi-block
scenario. Grab and **Read the PNG**. Check: a duration edge on the composer preview (drag it, the block
grows); boundary lines on the total preview at each block's right edge; dragging a boundary grows that
block and the total (x-axis extends); dragging a node no longer makes the composer view jump.

- [ ] **Step 5: Update the docs and commit**

`SIMULATOR_SESSION_RESUME.md`: builder-UX done with the **real** test count; the builder now has duration
edges (composer + total) and a frozen composer autorange. `SIMULATOR_ARCHITECTURE.md`: add
`DurationHandles` and `MAX_BLOCK_TICKS` to the module map; bump the count. Note the next queued items
(scenario-lifecycle, cockpit dock, dataset generator — the DRAFT specs).

```bash
git add document/SIMULATOR_SESSION_RESUME.md document/SIMULATOR_ARCHITECTURE.md
git commit -m "docs(sim): resume + map — builder-UX (duration edges + frozen autorange) done"
git push origin Simulator
```

---

## Notes for whoever executes this

- **Commit-on-finish is load-bearing.** `on_resize` fires on the release, so re-placing the handle lines
  (clear + recreate in `_refresh`/`_place_composer_edge`) never runs with a drag active. If you switch to
  a live `sigPositionChanged`, you reintroduce the line-destroyed-under-the-cursor bug and the
  value↔handle loop — do not.
- **The spinbox `_ticks` is the single owner of the composed block's duration.** The composer edge writes
  it; it does not hold a duration of its own.
- **A boundary resizes the block to its LEFT** (the block whose right edge it is), and the total grows.
  `new_ticks = round(x) - cum[i]`, computed from the block's start.
- **The node drag must not re-fit** — that is the whole of item 3. Its `on_change` passes `refit=False`.
- **`materialise` and the frozen core stay untouched.** This cycle is Qt + one pure constant.
