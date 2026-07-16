# Drag + `custom` block + physics advisory — Implementation Plan (cycle 4b)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the designer draw a leader profile by dragging its nodes, and light in red the stretches the leader they described cannot physically produce — advising, never constraining.

**Architecture:** A new `custom` block whose params are node **speeds** on a derived tick grid, materialised as a linear polyline anchored at `v0` (pure, in `scenario_spec.py`). A pure `physics_gap` and a pure `block_of_sample` layout helper feed a red overlay drawn on two plots. The drag is a small isolated `DragHandles` unit (`pg.TargetItem`, vertical-constrained) so the one measured-risk piece is tested alone. `app.py` is untouched — a built custom flows through `_on_scenario_built` like any scenario.

**Tech Stack:** Python 3, numpy, PySide6, pyqtgraph 0.14, pytest. Conda env `cf_sim`.

**Spec:** `docs/superpowers/specs/2026-07-16-drag-custom-advisory-design.md`. **Read §Scope first** — that is the coverage checklist, not §Testing (in cycle 4a the self-review checked the tests and missed a whole Scope requirement). **Architecture map:** `document/SIMULATOR_ARCHITECTURE.md` (verified file:line for every load-bearing fact).

---

## Before you start

**Worktree:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator`, branch `Simulator`.

**Test runner** (⚠️ never `conda run -n cf_sim python -m pytest` — it intermittently crashes conda's plugin system):

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

**Full suite** = the `test_sim_*.py` files + `tests/test_champion_io.py`. **Baseline: 244 passed.** This plan
adds one test file (`tests/test_sim_drag_handles.py`), so the runner's `test_sim_*.py` glob picks it up.
⚠️ The full suite takes **~3–4 minutes** — a 2-minute default timeout **looks like a hang and is not one**.
Give it ≥420 s or run it in the background.

**Hard rules (from the map):**
- **Frozen core**: `sim/{state,stepper,backend,probe,events,eventprop_stepper}.py` untouched.
- **`utils/closed_loop_eval.py` is INVARIANT.**
- **No numpy LAPACK** in `cf_sim` → OMP #15 hard abort.
- **`materialise` is not touched** — the `custom` branch lives in `_block_samples`; the layout helper is
  additive and pure.
- Commits: conventional, **no `Co-Authored-By`**. Push freely.
- **Edit, not `replace()`** for targeted text changes (fails loudly on a mismatch). **Anchor verifications
  to the section**, do not grep the whole file.

**Process lessons carried in (do not repeat):**
- The plan's **self-review runs against the spec's §Scope**, not its §Testing.
- A test asserting "change X → Y moves" needs the **causal path verified**: `const` and `ramp` are the
  same computation (`_block_samples:114-117`), and `a_max` cannot move a block that brakes. Pick inputs on
  the path.
- The RED must exercise the behaviour, not just a missing symbol: after GREEN, **sabotage the fix** and
  confirm the test catches it.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `sim/scenario_spec.py` | pure model + materialiser + JSON | `+V_RANGE`, `+_custom_node_ticks`, `+_custom_samples`, `custom` dispatch in `_block_samples`, `+physics_gap`, `+block_of_sample`, `_KINDS += custom`, JSON tuple round-trip. Stays pure. |
| `sim/ui/drag_handles.py` | **new** — a row of vertical draggable nodes on a plot | isolated, tested alone. The one measured-risk piece behind a clean interface. |
| `sim/ui/scenario_page.py` | Qt composer | wire `custom`: node-count spinbox, handle lifecycle, `kind in (preset,custom)` generalisations, advisory overlays on two plots. |
| `tests/test_sim_scenario_spec.py` | the model | append custom + physics_gap + block_of_sample + JSON tests. |
| `tests/test_sim_drag_handles.py` | **new** — the drag unit | vertical constraint, clamp, read/place. |
| `tests/test_sim_ui_smoke.py` | the composer | append lifecycle + advisory + budget tests. |

Order: model → layout helper → JSON → the drag unit → wire it → the advisory → verify.

---

### Task 1: the `custom` block — a linear polyline anchored at v0

**Files:**
- Modify: `sim/scenario_spec.py:22-25` (ranges + `_KINDS`), `:111-122` (`_block_samples`)
- Test: `tests/test_sim_scenario_spec.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
# ---- custom: a hand-drawn polyline -------------------------------------------------------------

def test_custom_is_a_linear_polyline_anchored_at_v0():
    """Node 0 IS v0 (not stored); the nodes are SPEEDS on a derived, evenly-spaced tick grid."""
    from sim.scenario_spec import _custom_node_ticks, _custom_samples
    # 3 nodes over 90 ticks: grid at 30,60,89 (linspace(0,89,4)[1:] rounded by np.interp's float xs)
    v = _custom_samples([10.0, 10.0, 4.0], n=90, v0=21.0)
    assert v.shape == (90,)
    assert v[0] == 21.0                                   # anchored at v0
    assert abs(v[-1] - 4.0) < 1e-9                        # last node is the last sample
    # linear between anchor (0,21) and first node (~30,10): midpoint ~ (21+10)/2
    assert abs(v[15] - (21.0 + (10.0 - 21.0) * 15 / 30.0)) < 0.2


def test_custom_with_zero_nodes_is_flat_at_v0():
    from sim.scenario_spec import _custom_samples
    v = _custom_samples([], n=50, v0=13.5)
    np.testing.assert_array_equal(v, np.full(50, 13.5))   # np.interp on a single point


def test_custom_clips_speeds_to_v_range_no_reverse_leader():
    """A hand-edited node beyond the physical range is pinned: v<0 is the leader in reverse, which is
    not a scenario. Clipping the NODES (not the samples) keeps the polyline linear in-range."""
    from sim.scenario_spec import _custom_samples, V_RANGE
    v = _custom_samples([-5.0, 99.0], n=40, v0=10.0)
    assert v.min() >= V_RANGE[0] - 1e-9 and v.max() <= V_RANGE[1] + 1e-9


def test_moving_one_node_changes_only_its_two_segments():
    """TEETH: interp locality IS the drawing model. A change that leaked past the neighbouring nodes
    would still 'change the curve' and pass a naive test."""
    from sim.scenario_spec import _custom_samples
    base = _custom_samples([10.0, 10.0, 10.0, 10.0], n=200, v0=21.0)
    moved = _custom_samples([10.0, 4.0, 10.0, 10.0], n=200, v0=21.0)   # node index 1 moved
    d = np.flatnonzero(np.abs(base - moved) > 1e-9)
    # node 1 sits at tick ~ linspace(0,199,5)[2]=99.5; its neighbours at ~49.75 and ~149.25.
    assert d.min() > 45 and d.max() < 155                 # untouched outside [node0..node2]


def test_a_custom_block_joins_continuously():
    """Extends cycle 3's boundary property to custom: node-0-is-v0 means a custom never teleports at a
    junction (materialise threads v as each block's v0). preset is the ONLY kind that may seam."""
    prev_last = materialise(_spec([Block("ramp", 200, {"to_v": 6.0})]), _PG, N=200).v_leader[-1]
    two = materialise(_spec([Block("ramp", 200, {"to_v": 6.0}),
                             Block("custom", 200, {"nodes": [18.0, 18.0]})]), _PG, N=400).v_leader
    assert abs(two[200] - prev_last) < 1e-9               # first custom sample == previous last: no jump
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q -k "custom or joins_continuously or moving_one_node"
```

Expected: FAIL — `ImportError: cannot import name '_custom_samples'` (and `V_RANGE`).

- [ ] **Step 3: Implement**

In `sim/scenario_spec.py`, add `V_RANGE` next to the other ranges (`:22-23`) and extend `_KINDS`:

```python
A_MAX_RANGE = (1.0, 4.0)
B_MAX_RANGE = (1.0, 9.0)
V_RANGE = (0.0, 40.0)          # the leader's speed range: same as the builder's value spinbox.
                               # v<0 is the leader in reverse -- not a scenario -- so custom clips to it.

_KINDS = ("preset", "const", "ramp", "sine", "custom")
```

Add the two custom helpers just before `_block_samples` (`:110`):

```python
def _custom_node_ticks(n, count):
    """Where the free nodes sit: evenly spaced, ending at the last sample. DERIVED from (n, count),
    never stored -- storing a tick would create a second owner of a derived value (the 4a
    reopen-corruption bug). count == len(speeds); node 0 is not here (it IS v0)."""
    return np.linspace(0.0, n - 1, count + 1)[1:]


def _custom_samples(speeds, n, v0):
    """A hand-drawn polyline: v0 at tick 0, then straight to each node's speed in turn.

    LINEAR (np.interp), not spline: each segment has ONE constant acceleration, so the advisory can
    light a whole segment and quote the number exactly; and a spline can overshoot past its own nodes
    and produce v<0 (the leader in reverse), which np.interp cannot. Nodes are clipped to V_RANGE
    BEFORE interpolation, so an out-of-range node is pinned and the line between in-range nodes stays
    in range. If anyone swaps this for a spline, the edge-exact advisory test and the no-reverse test
    both go soft -- that is the guard.
    """
    xs = np.concatenate(([0.0], _custom_node_ticks(n, len(speeds))))
    ys = np.clip(np.concatenate(([float(v0)], np.asarray(speeds, dtype=np.float64))), *V_RANGE)
    return np.interp(np.arange(n), xs, ys)
```

Add the dispatch branch in `_block_samples` (after the `sine` branch, `:121`):

```python
    if block.kind == "custom":
        return _custom_samples(block.params["nodes"], n, v0)   # ignores style, like preset
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

Expected: PASS (24 existing + 5 new = 29).

- [ ] **Step 5: Sabotage-check the teeth, then commit**

Confirm `test_moving_one_node_changes_only_its_two_segments` really has teeth: temporarily change
`_custom_samples` to `np.interp(np.arange(n), xs, ys) * 1.0001` (a global scale) and rerun `-k moving_one_node`
— it must FAIL (every sample changed). Revert.

```bash
git add sim/scenario_spec.py tests/test_sim_scenario_spec.py
git commit -m "feat(sim): the custom block -- a linear polyline anchored at v0

Nodes are SPEEDS on a derived tick grid (_custom_node_ticks); node 0 is not stored,
it IS v0, so a custom never teleports at a junction and cycle 3's continuity property
extends to it instead of excluding it the way it excludes preset. Linear, not spline:
one acceleration per segment (so the advisory is exact) and np.interp cannot overshoot
past its nodes into v<0. Nodes clip to V_RANGE before interp -- the leader has no reverse."
```

---

### Task 2: `physics_gap` — which segments the leader cannot produce

**Files:**
- Modify: `sim/scenario_spec.py` (append after `effective_style`, `:149`)
- Test: `tests/test_sim_scenario_spec.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_physics_gap_is_exact_at_the_edge():
    """TEETH, both directions: a segment at exactly b_max is NOT a violation; one just past it IS.
    The off-by-one is where this bug would live."""
    from sim.scenario_spec import physics_gap, LeaderStyle
    neutral = LeaderStyle(a_max=3.0, b_max=6.0)
    # build a v whose one segment brakes at exactly b_max, then one just past it.
    at_edge = np.array([10.0, 10.0 - 6.0 * DT])           # -6.0 m/s^2 == -b_max
    past = np.array([10.0, 10.0 - 6.0001 * DT])           # just past -b_max
    assert physics_gap(at_edge, neutral)[0].sum() == 0     # == b_max is allowed
    assert physics_gap(past, neutral)[0].sum() == 1        # past it lights
    # and the acceleration edge, symmetric
    up_edge = np.array([10.0, 10.0 + 3.0 * DT])
    up_past = np.array([10.0, 10.0 + 3.0001 * DT])
    assert physics_gap(up_edge, neutral)[0].sum() == 0
    assert physics_gap(up_past, neutral)[0].sum() == 1


def test_physics_gap_returns_the_acceleration_for_the_annotation():
    from sim.scenario_spec import physics_gap, LeaderStyle
    v = np.array([21.0, 4.0])                              # -170 m/s^2 in one tick
    mask, acc = physics_gap(v, LeaderStyle(3.0, 9.0))
    assert mask[0]
    assert abs(acc[0] - (4.0 - 21.0) / DT) < 1e-9         # the number the UI quotes


def test_physics_gap_never_flags_a_placid_constant():
    from sim.scenario_spec import physics_gap, LeaderStyle
    mask, _ = physics_gap(np.full(100, 15.0), LeaderStyle(1.0, 1.0))
    assert mask.sum() == 0                                 # a flat leader asks nothing of anyone
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q -k physics_gap
```

Expected: FAIL — `ImportError: cannot import name 'physics_gap'`.

- [ ] **Step 3: Implement**

Append to `sim/scenario_spec.py` after `effective_style` (`:149`):

```python
def physics_gap(v, neutral):
    """Which segments this driver cannot produce, and the acceleration each one demands. PURE.

    The reference is the NEUTRAL, not an effective style: on a custom the pad is dead and the bias is
    always None, so effective_style(block, neutral) == neutral anyway. acc = diff(v)/DT is exactly the
    leader acceleration the engine reads (stepper.py:76, simulate:189), so the red is the same
    arithmetic the physics runs -- not a UI approximation. `>` and `<` (strict): a segment AT the limit
    is allowed; only past it lights.
    """
    acc = np.diff(np.asarray(v, dtype=np.float64)) / DT
    mask = (acc > neutral.a_max) | (acc < -neutral.b_max)
    return mask, acc
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q -k physics_gap
```

Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add sim/scenario_spec.py tests/test_sim_scenario_spec.py
git commit -m "feat(sim): physics_gap -- the advisory, as the engine's own arithmetic

diff(v)/DT is exactly a_l_raw at stepper.py:76; the mask compares it to the neutral's
(a_max,b_max), which IS the leader's rate limit. Strict inequality: a segment at the
limit is allowed, only past it lights. Teeth on the edge, both directions."
```

---

### Task 3: `block_of_sample` — attribution from materialise's real layout

**Files:**
- Modify: `sim/scenario_spec.py` (append after `materialise`, `:171`)
- Test: `tests/test_sim_scenario_spec.py` (append)

⚠️ **Why this is its own task.** The advisory on the scenario curve must paint only custom stretches, and
the naïve `cumsum(ticks)` is wrong: `materialise` truncates the last block to N (`:163,165`) and fills a
flat hold tail (`:170`). This helper replays that exact layout so the page never re-derives it in Qt and
drifts.

- [ ] **Step 1: Write the failing tests**

```python
def test_block_of_sample_matches_the_real_layout_under_overflow():
    """TEETH: two blocks of 400 ticks sum to 800 > N=600, so the second is truncated to 200 and there
    is no flat tail. cumsum(ticks) would say block 1 owns samples 400..800 -- past the array."""
    from sim.scenario_spec import block_of_sample
    spec = _spec([Block("ramp", 400, {"to_v": 5.0}), Block("const", 400, {"v": 5.0})])
    owner = block_of_sample(spec, N=600)
    assert owner.shape == (600,)
    assert (owner[:400] == 0).all()
    assert (owner[400:] == 1).all()                        # truncated to 200, no -1 tail here


def test_block_of_sample_marks_the_flat_tail_as_no_block():
    from sim.scenario_spec import block_of_sample
    spec = _spec([Block("const", 150, {"v": 5.0})])        # 150 of 600 -> 450 flat-tail samples
    owner = block_of_sample(spec, N=600)
    assert (owner[:150] == 0).all()
    assert (owner[150:] == -1).all()                       # -1 == the hold tail (diff=0 there, never red)
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q -k block_of_sample
```

Expected: FAIL — `ImportError: cannot import name 'block_of_sample'`.

- [ ] **Step 3: Implement**

Append to `sim/scenario_spec.py` after `materialise` (`:171`):

```python
def block_of_sample(spec, N):
    """Per-sample owning-block index, built from materialise's OWN layout: the same min(ticks, N-i)
    clip and the same flat hold tail. -1 marks the tail (no block). The advisory reads this instead of
    recomputing cumsum(ticks) in Qt, which would drift the moment blocks sum past N."""
    owner = np.full(N, -1, dtype=np.int64)
    i = 0
    for bi, block in enumerate(spec.blocks):
        if i >= N:
            break
        seg = min(int(block.ticks), N - i)                 # same clip as materialise's [: N - i]
        owner[i:i + seg] = bi
        i += seg
    return owner
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q -k block_of_sample
```

Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add sim/scenario_spec.py tests/test_sim_scenario_spec.py
git commit -m "feat(sim): block_of_sample -- attribution from materialise's real layout

The advisory paints only custom stretches; cumsum(ticks) gets it wrong because
materialise truncates the last block to N and fills a flat tail. This replays that
exact layout (same min(ticks,N-i) clip, -1 for the tail) so the page never re-derives
it and drifts when blocks overflow N."
```

---

### Task 4: JSON round-trips a `custom`

**Files:**
- Modify: `sim/scenario_spec.py:194-208` (`from_json` — nodes as a tuple of floats)
- Test: `tests/test_sim_scenario_spec.py` (append)

⚠️ Reminder: `to_json`/`from_json` have **no Save/Load UI hook** — this is test-only surface today. The
point is correctness of the round-trip, not a persistence feature.

- [ ] **Step 1: Write the failing tests**

```python
def test_json_round_trips_a_custom_with_nodes_as_a_tuple():
    from sim.scenario_spec import from_json, to_json
    s = _spec([Block("custom", 300, {"nodes": [21.0, 8.0, 8.0, 15.0]}),
               Block("const", 300, {"v": 15.0})])
    back = from_json(to_json(s))
    assert back == s                                       # frozen dataclass compares by value
    assert isinstance(back.blocks[0].params["nodes"], tuple)   # a list would compare unequal
    np.testing.assert_array_equal(materialise(back, _PG, N=600).v_leader,
                                  materialise(s, _PG, N=600).v_leader)


def test_a_hand_edited_custom_loads_at_its_own_node_count():
    """count is len(nodes), never a stored field -- so a file edited to 7 nodes loads and draws at 7."""
    from sim.scenario_spec import from_json
    text = ('{"name":"x","s_init":33.5,"v_init":21.0,"style":{"a_max":2.0,"b_max":4.0},'
            '"blocks":[{"kind":"custom","ticks":210,"params":{"nodes":[20,18,16,14,12,10,8]}}]}')
    spec = from_json(text)
    assert len(spec.blocks[0].params["nodes"]) == 7
    assert materialise(spec, _PG, N=600).v_leader.shape == (600,)
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q -k "round_trips_a_custom or hand_edited_custom"
```

Expected: FAIL — `back == s` is False (the nodes come back as a **list**, so the `params` dict compares
unequal even though the numbers match).

- [ ] **Step 3: Implement**

`to_json` needs no change (the nodes are a plain list of floats and `_block_json` passes `params`
through). In `from_json` (`:203`), rebuild a custom's nodes as a **tuple of floats** so `Block`'s
by-value comparison round-trips. Replace the block-append line:

```python
        raw = b.get("bias")
        params = dict(b["params"])
        if b["kind"] == "custom":
            params["nodes"] = tuple(float(x) for x in params["nodes"])   # list != tuple by value (4a bias trap)
        blocks.append(Block(kind=b["kind"], ticks=int(b["ticks"]), params=params,
                            bias=tuple(float(x) for x in raw) if raw is not None else None))
```

⚠️ The `nodes` tuple is the same trap as 4a's `bias`: JSON hands back a list, `Block` compares by value,
so a list breaks the round-trip while printing identically.

- [ ] **Step 4: Run to verify they pass, and the whole model file**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

Expected: PASS (34).

- [ ] **Step 5: Sabotage-check, then commit**

Change the tuple line to a list (`params["nodes"] = [float(x) for x in params["nodes"]]`) and rerun
`-k round_trips_a_custom` — it must FAIL with two `ScenarioSpec(...)` that print identically. Revert.

```bash
git add sim/scenario_spec.py tests/test_sim_scenario_spec.py
git commit -m "feat(sim): a custom round-trips through JSON, nodes as a tuple

from_json rebuilds the nodes as a tuple of floats: JSON hands back a list, Block
compares by value, so a list breaks the round-trip while printing identically -- the
4a bias trap, verbatim. count is len(nodes), so a hand-edited file loads at its count."
```

---

### Task 5: `DragHandles` — a row of vertical draggable nodes (isolated)

**Files:**
- Create: `sim/ui/drag_handles.py`
- Test: `tests/test_sim_drag_handles.py` (new)

⚠️ This is the one piece with a measured risk (mouse interaction). It is isolated behind a small
interface and tested alone. Two measured facts drive it: `pg.TargetItem` is a ready draggable handle
(no hit-testing to write), and the vertical constraint via `sigPositionChanged` **converges in 2 calls**
— whereas subclassing `setPos` **crashes** inside `TargetItem.__init__`, which passes a tuple.

- [ ] **Step 1: Write the failing tests**

```python
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

import pyqtgraph as pg                                     # noqa: E402
from PySide6.QtWidgets import QApplication                 # noqa: E402
from sim.ui.drag_handles import DragHandles                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_place_and_read_speeds(qapp):
    plot = pg.PlotWidget()
    calls = []
    h = DragHandles(plot, on_change=lambda: calls.append(1))
    h.set_speeds(ticks=[30.0, 60.0, 90.0], speeds=[10.0, 12.0, 4.0])
    assert h.speeds() == [10.0, 12.0, 4.0]
    assert len(h) == 3


def test_a_drag_is_locked_to_vertical(qapp):
    """The measured route: reconnecting x in sigPositionChanged converges in 2 calls, x stays put."""
    plot = pg.PlotWidget()
    h = DragHandles(plot, on_change=lambda: None)
    h.set_speeds(ticks=[50.0], speeds=[10.0])
    item = h._items[0]
    item.setPos(80.0, 14.0)                                # what a diagonal drag would do
    assert item.pos().x() == 50.0                          # x locked to the node's tick
    assert item.pos().y() == 14.0                          # y moved


def test_y_is_clamped_to_v_range_not_the_plot(qapp):
    from sim.scenario_spec import V_RANGE
    plot = pg.PlotWidget()
    h = DragHandles(plot, on_change=lambda: None)
    h.set_speeds(ticks=[50.0], speeds=[10.0])
    h._items[0].setPos(50.0, -5.0)
    assert h.speeds()[0] == V_RANGE[0]                     # v<0 pinned: no reverse leader
    h._items[0].setPos(50.0, 99.0)
    assert h.speeds()[0] == V_RANGE[1]


def test_set_speeds_does_not_fire_on_change(qapp):
    """Placement is not a user edit: firing on_change mid-placement is the lifecycle bug -- a refresh
    while the row is half-built. set_speeds is silent; only a drag notifies."""
    plot = pg.PlotWidget()
    calls = []
    h = DragHandles(plot, on_change=lambda: calls.append(1))
    h.set_speeds(ticks=[30.0, 60.0], speeds=[10.0, 12.0])
    assert calls == []                                     # silent
    h._items[0].setPos(30.0, 8.0)                          # a real drag
    assert calls == [1]


def test_clear_removes_every_handle(qapp):
    plot = pg.PlotWidget()
    h = DragHandles(plot, on_change=lambda: None)
    h.set_speeds(ticks=[30.0, 60.0], speeds=[10.0, 12.0])
    h.clear()
    assert len(h) == 0 and h.speeds() == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_drag_handles.py -q
```

Expected: FAIL — `ModuleNotFoundError: No module named 'sim.ui.drag_handles'`.

- [ ] **Step 3: Implement**

Create `sim/ui/drag_handles.py`:

```python
"""DragHandles -- a row of vertically-draggable nodes on a pyqtgraph plot.

Isolated on purpose: the drag is the one piece of the scenario builder with a measured risk (mouse
interaction), so it lives behind a small interface and is tested alone. Two measured facts shape it:
pg.TargetItem is a ready draggable handle (no hit-testing to write), and constraining it to vertical
by reconnecting x in sigPositionChanged converges in 2 calls -- while subclassing setPos crashes
inside TargetItem.__init__, which passes a tuple.
"""
import numpy as np
import pyqtgraph as pg

from sim.scenario_spec import V_RANGE


class DragHandles:
    def __init__(self, plot, on_change):
        self._plot = plot
        self._on_change = on_change            # called once per user drag, never during set_speeds
        self._items = []
        self._placing = False                  # guard: set_speeds must not look like a user edit

    def __len__(self):
        return len(self._items)

    def speeds(self):
        return [float(h.pos().y()) for h in self._items]

    def set_speeds(self, ticks, speeds):
        """Place one handle per (tick, speed). Silent: placement is not a user edit."""
        self.clear()
        self._placing = True
        try:
            for x, y in zip(ticks, speeds):
                h = pg.TargetItem(pos=(float(x), float(np.clip(y, *V_RANGE))), movable=True, size=11,
                                  pen=pg.mkPen("#2a7fb8", width=2), brush=pg.mkBrush("#2a7fb8"))
                h._tick = float(x)
                h.sigPositionChanged.connect(self._constrain)
                self._plot.addItem(h)
                self._items.append(h)
        finally:
            self._placing = False

    def clear(self):
        for h in self._items:
            self._plot.removeItem(h)
        self._items = []

    def _constrain(self, item):
        """Lock x to the node's tick and clamp y to V_RANGE. Re-snapping x re-emits, but the second
        pass is a no-op (x already == tick, y already clamped), so it converges in 2 calls (measured)."""
        x, y = item.pos().x(), float(np.clip(item.pos().y(), *V_RANGE))
        if x != item._tick or y != item.pos().y():
            item.setPos(item._tick, y)                     # re-enters _constrain once, then converges
            return
        if not self._placing:
            self._on_change()
```

⚠️ The `return` after the corrective `setPos` matters: it lets the re-entrant call (which passes the
now-valid position) be the one that fires `_on_change`, so a drag notifies **once**, not twice.

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_drag_handles.py -q
```

Expected: PASS (5).

- [ ] **Step 5: Commit**

```bash
git add sim/ui/drag_handles.py tests/test_sim_drag_handles.py
git commit -m "feat(sim): DragHandles -- a row of vertical draggable nodes, isolated

The one measured-risk piece (mouse interaction) behind a small tested interface.
pg.TargetItem needs no hit-testing; the vertical constraint reconnects x in
sigPositionChanged and converges in 2 calls (the subclass route crashes inside
TargetItem.__init__ on a tuple). set_speeds is silent -- placement is not a user
edit -- and a drag notifies exactly once. y clamps to V_RANGE: no reverse leader."
```

---

### Task 6: wire `custom` into the composer (params owner + lifecycle)

**Files:**
- Modify: `sim/ui/scenario_page.py` (`__init__`, `_params_for`, `_on_kind_changed`, `_load_into_widgets`, `_composer_block`)
- Test: `tests/test_sim_ui_smoke.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_custom_kind_shows_handles_and_kills_the_pad(qapp):
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 300, {"to_v": 2.0})]))
    page.compose_new("custom", ticks=300, params={"nodes": [10.0, 10.0, 10.0, 10.0, 10.0]})
    assert len(page._handles) == 5                          # a handle per node
    assert not page._pad.isEnabled()                        # a drawn profile ignores the style
    assert not page._pad_note.isHidden()
    page._kind.setCurrentText("ramp")
    assert len(page._handles) == 0                          # switching away clears them
    assert page._pad.isEnabled()


def test_a_custom_records_no_bias(qapp):
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 300, {"to_v": 2.0})]))
    page.compose_new("ramp", ticks=150, params={"to_v": 18.0}, bias=(1.6, 4.2))
    assert page._composer_block().bias == (1.6, 4.2)        # a ramp obeys it
    page._kind.setCurrentText("custom")
    assert page._composer_block().bias is None              # a custom cannot, so it does not keep it


def test_params_for_custom_reads_the_handles(qapp):
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 300, {"to_v": 2.0})]))
    page.compose_new("custom", ticks=300, params={"nodes": [12.0, 9.0, 6.0]})
    assert page._params_for("custom") == {"nodes": (12.0, 9.0, 6.0)}   # a TUPLE: matches JSON's form


def test_the_handle_lifecycle_keeps_one_owner(qapp):
    """TEETH: kind->custom->(read)->kind->custom->Apply. A handle read while the row does not exist
    would fabricate a wrong nodes -- the two-owner failure 4a paid for."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("custom", 300, {"nodes": [20.0, 4.0, 4.0]}),
                          Block("const", 300, {"v": 4.0})]))
    page._on_row_selected(0)                                # reopen the custom
    assert page._composer_kind() == "custom"
    assert page._handles.speeds() == [20.0, 4.0, 4.0]       # handles came back
    page._on_add()                                          # Apply, no edit
    assert page._spec.blocks[0] == Block("custom", 300, {"nodes": (20.0, 4.0, 4.0)})


def test_node_count_resamples_the_current_curve(qapp):
    """Raising the count refines the drawing, it does not erase it: the shape survives."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 300, {"to_v": 2.0})]))
    page.compose_new("custom", ticks=300, params={"nodes": [20.0, 10.0]})
    v_before = page._composer_curve.getOriginalDataset()[1].copy()
    page._nodes.setValue(6)
    assert len(page._handles) == 6
    v_after = page._composer_curve.getOriginalDataset()[1]
    # same shape, resampled: the endpoints are unchanged, the curve is close
    assert abs(v_after[-1] - v_before[-1]) < 0.5
    assert np.abs(v_after - v_before).max() < 1.0
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "custom_kind or records_no_bias or params_for_custom or handle_lifecycle or node_count_resamples"
```

Expected: FAIL — `AttributeError: 'ScenarioPage' object has no attribute '_handles'`.

- [ ] **Step 3: Implement**

In `sim/ui/scenario_page.py`, extend the imports (`:17-19`):

```python
from sim.scenario import scenario_library
from sim.scenario_spec import (A_MAX_RANGE, B_MAX_RANGE, V_RANGE, _KINDS, _custom_node_ticks,
                               Block, LeaderStyle, ScenarioSpec, block_of_sample, materialise,
                               physics_gap)
from sim.ui.drag_handles import DragHandles
```

In `__init__`, add the node-count spinbox to the controls (after `self._period`, `:117`):

```python
        self._nodes = QSpinBox(); self._nodes.setRange(1, 25); self._nodes.setValue(5)
        self._nodes_lbl = QLabel("nodi")
```

and add `self._nodes_lbl, self._nodes` to the widget loop (`:128-131`, before `self._add`). After the
composer plot is built (`:153`), create the handles bound to it:

```python
        self._handles = DragHandles(self._composer_plot, on_change=self._refresh_composer)
```

Wire the node-count spinbox (with the other live inputs, `:165-167`):

```python
        self._nodes.valueChanged.connect(self._on_node_count_changed)
```

Replace `_params_for` (`:205-216`) to read the handles for custom:

```python
    def _params_for(self, kind):
        """The params of the block being composed, DERIVED from the widgets. For custom the widget IS
        the row of handles: one owner, no shadow list. The nodes are a TUPLE -- the same canonical form
        from_json rebuilds (Task 4), so a block built here and one loaded from JSON with the same numbers
        compare EQUAL; a list would print identically and compare unequal (the 4a bias trap). If the
        handles do not exist yet, speeds() is [] -> a flat curve, not a crash (the lifecycle guarantees
        they exist before this matters)."""
        v = float(self._value.value())
        return {"preset": {"name": self._preset.currentText()},
                "const": {"v": v},
                "ramp": {"to_v": v},
                "sine": {"amp": v, "period": int(self._period.value())},
                "custom": {"nodes": tuple(self._handles.speeds())}}[kind]
```

Replace `_on_kind_changed` (`:218-234`) to handle custom (pad death + handle show/clear + node-count
visibility). The handles are created HERE, before the trailing refresh — the §6 ordering constraint:

```python
    def _on_kind_changed(self, kind):
        """Show only the inputs this kind actually has: an input that does nothing is a lie.

        The pad dies on preset AND custom -- both ignore the style (a preset is verbatim, a custom is
        hand-drawn) -- so a live pad there is a lie. custom shows the node-count and a row of handles;
        the handles are created BEFORE the trailing refresh so _params_for('custom') never reads an
        empty row (the lifecycle constraint, spec 6)."""
        is_preset, is_sine, is_custom = kind == "preset", kind == "sine", kind == "custom"
        self._preset.setVisible(is_preset)
        for w in (self._value_lbl, self._value):
            w.setVisible(not (is_preset or is_custom))
        for w in (self._period_lbl, self._period):
            w.setVisible(is_sine)
        for w in (self._nodes_lbl, self._nodes):
            w.setVisible(is_custom)
        self._value_lbl.setText("ampiezza" if is_sine else "valore")
        self._pad.setEnabled(not (is_preset or is_custom))
        self._pad_note.setVisible(is_preset or is_custom)
        self._pad_note.setText("il preset è verbatim: il bias non lo tocca" if is_preset
                               else "il profilo disegnato non segue un rate: trascina i nodi")
        if is_custom:
            # setCurrentText fires this while _load_into_widgets is mid-write (loading=True); skip the
            # flat seed then -- the custom branch there places the real nodes. When the user picks
            # custom from the combo (not loading), seed a flat line to bend.
            if not self._loading:
                self._place_custom_handles(self._handles.speeds() or None)
        else:
            self._handles.clear()
        self._refresh_composer()

    def _place_custom_handles(self, speeds):
        """Position the handles on the current tick grid. speeds=None seeds a flat line at the start
        speed (a fresh custom you then bend); otherwise re-place the given speeds."""
        n = int(self._ticks.value())
        count = int(self._nodes.value())
        ticks = _custom_node_ticks(n, count)
        if speeds is None:
            speeds = [self._start_speed(self._composer_row
                                        if self._composer_row is not None
                                        else len(self._spec.blocks))] * count
        self._handles.set_speeds(ticks, speeds)

    def _on_node_count_changed(self, count):
        """Re-sample the current drawing at the new grid instead of discarding it."""
        if self._loading or self._composer_kind() != "custom":
            return
        n = int(self._ticks.value())
        old_ticks = _custom_node_ticks(n, len(self._handles))
        old_speeds = self._handles.speeds()
        v0 = self._start_speed(self._composer_row if self._composer_row is not None
                               else len(self._spec.blocks))
        new_ticks = _custom_node_ticks(n, int(count))
        new_speeds = np.interp(new_ticks, np.concatenate(([0.0], old_ticks)),
                               np.concatenate(([v0], old_speeds))).tolist()
        self._handles.set_speeds(new_ticks, new_speeds)
        self._refresh_composer()
```

Extend `_load_into_widgets` (`:236-259`) with a custom branch — placing the handles inside the
`_loading` guard, so their (silent) placement plus any signal cannot fire a mid-write refresh:

```python
            elif kind == "custom":
                self._nodes.setValue(len(params["nodes"]))
                self._place_custom_handles(list(params["nodes"]))
            else:
                self._value.setValue(float(params["v" if kind == "const" else "to_v"]))
```

(Insert this branch between the `sine` branch and the final `else` at `:249-253`.)

Generalise `_composer_block` (`:277`) so a custom records no bias, like a preset:

```python
        bias = None if kind in ("preset", "custom") else self._composer_bias()
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "custom or records_no_bias or handle_lifecycle or node_count or params_for"
```

Expected: PASS. (If `test_the_handle_lifecycle_keeps_one_owner` fails on the reopened equality, check that
`_load_into_widgets` runs the custom branch under `_loading=True` and that `_on_add` reads
`_params_for("custom")` AFTER the handles are placed.)

- [ ] **Step 5: Sabotage-check the lifecycle, then commit**

Confirm the lifecycle test has teeth: temporarily move `self._place_custom_handles(...)` in
`_on_kind_changed` to AFTER `self._refresh_composer()` and rerun `-k handle_lifecycle` — a
`_params_for("custom")` during that refresh now reads an empty row, so a reopened block would come back
with the wrong nodes. It must FAIL. Revert.

```bash
git add sim/ui/scenario_page.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): the composer builds a custom block by dragging its nodes

custom joins the composer with one owner for its params -- the row of handles, read
by _params_for('custom'), never a shadow list. The pad dies on custom as on preset
(both ignore the style) and a custom records no bias. A node-count spinbox re-samples
the current drawing instead of erasing it. The handles are created before the trailing
refresh (the lifecycle constraint) so a read never sees a half-built row -- the exact
two-owner failure 4a paid for, and the test has teeth on it."
```

---

### Task 7: the advisory — red on the impossible stretches

**Files:**
- Modify: `sim/ui/scenario_page.py` (`__init__` overlays, `_refresh`, `_refresh_composer`)
- Test: `tests/test_sim_ui_smoke.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_composer_preview_lights_the_impossible_segments(qapp):
    """The whole preview is one custom block, so every bad segment is eligible."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("const", 600, {"v": 21.0})], a=3.0, b=6.0))
    # a custom that brakes 21 -> 2 across one segment (past b_max=6): compose_new places the handles
    page.compose_new("custom", ticks=150, params={"nodes": [21.0, 2.0, 2.0]})
    red = page._composer_red.getOriginalDataset()[1]
    assert np.isfinite(red).any()                          # something is lit


def test_the_advisory_never_paints_a_preset(qapp):
    """TEETH: the false-red measurement, as a test. cut_in jumps because it is a different vehicle;
    following is noise. Neither is a manoeuvre, so neither lights -- whatever the neutral."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("preset", 300, {"name": "cut_in"}),
                          Block("preset", 300, {"name": "following"})], a=1.0, b=1.0))
    red = page._scenario_red.getOriginalDataset()[1]
    assert not np.isfinite(red).any()                      # zero red on preset stretches


def test_the_scenario_advisory_paints_only_custom_via_layout(qapp):
    """TEETH: attribution from block_of_sample, not cumsum. A custom that overflows N still paints only
    where its samples are, and the custom->preset seam is the preset's (unpainted)."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("custom", 300, {"nodes": [21.0, 2.0, 2.0]}),   # impossible, custom
                          Block("preset", 300, {"name": "hard_brake"})],       # brakes hard, preset
                         a=1.0, b=1.0))
    red = page._scenario_red.getOriginalDataset()[1]
    lit = np.flatnonzero(np.isfinite(red))
    assert lit.size > 0                                     # the custom lights
    assert lit.max() < 302                                  # nothing past the custom's samples (+seam)


def test_the_advisory_is_off_by_default_when_no_custom(qapp):
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 600, {"to_v": 2.0})], a=1.0, b=1.0))
    red = page._scenario_red.getOriginalDataset()[1]
    assert not np.isfinite(red).any()                      # a ramp is rate-limited -> never red
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "advisory or impossible_segments"
```

Expected: FAIL — `AttributeError: 'ScenarioPage' object has no attribute '_composer_red'`.

- [ ] **Step 3: Implement**

In `__init__`, add a red overlay curve to each plot. After `self._composer_curve` (`:152`):

```python
        self._composer_red = self._composer_plot.plot(pen=pg.mkPen("#d1495b", width=4), connect="finite")
```

After `self._curve` (`:160`):

```python
        self._scenario_red = self._plot.plot(pen=pg.mkPen("#d1495b", width=4), connect="finite")
```

Add a shared helper that turns a mask over segments into the NaN-padded red curve (the verified spike
technique), and the neutral accessor:

```python
    def _neutral(self):
        return self._spec.style if self._spec else LeaderStyle(2.0, 4.0)

    @staticmethod
    def _red_from_mask(v, seg_mask):
        """A curve that is NaN on the physical samples and equals v on both endpoints of each bad
        segment; connect='finite' then draws ONLY the impossible stretches (verified by render)."""
        red = np.full(len(v), np.nan)
        idx = np.flatnonzero(seg_mask)                     # segment k -> samples k and k+1
        if idx.size:
            red[idx] = v[idx]
            red[idx + 1] = v[idx + 1]
        return red
```

Extend `_refresh` (`:192-196`) to paint the scenario advisory on custom stretches only:

```python
    def _refresh(self):
        if self._spec is None or not self._spec.blocks:
            self._curve.setData([])
            self._scenario_red.setData([])
            return
        v = materialise(self._spec, self._params_gt, self._N).v_leader
        self._curve.setData(v)
        mask, _ = physics_gap(v, self._neutral())          # over N-1 segments
        owner = block_of_sample(self._spec, self._N)
        custom_idx = [i for i, b in enumerate(self._spec.blocks) if b.kind == "custom"]
        # segment k is red iff sample k+1 is owned by a custom block (owner of the produced sample)
        seg_custom = np.isin(owner[1:], custom_idx) if custom_idx else np.zeros(self._N - 1, bool)
        self._scenario_red.setData(self._red_from_mask(v, mask & seg_custom))
```

Extend `_refresh_composer` (`:298-306`) — the preview is one block, so every segment is eligible, but
paint only when the block is a custom:

```python
    def _refresh_composer(self, *_):
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
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "advisory or impossible_segments"
```

Expected: PASS.

- [ ] **Step 5: Sabotage-check the attribution, then commit**

Confirm `test_the_scenario_advisory_paints_only_custom_via_layout` has teeth: temporarily replace the
attribution with a naïve all-segments paint (`seg_custom = np.ones(self._N - 1, bool)`) and rerun
`-k paints_only_custom` — the preset's hard-brake stretch now lights (`lit.max()` passes 302), so it must
FAIL. Revert.

```bash
git add sim/ui/scenario_page.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): the advisory lights the stretches the leader cannot produce

A red overlay on both plots: NaN on the physical samples + connect='finite' draws only
the impossible stretches (the verified spike). The composer preview lights any bad
segment (it is one custom block); the scenario curve lights a segment only if the
sample it produces is owned by a custom block, read from block_of_sample -- so a preset
is never painted (its false red was measured) and the custom->preset seam is the
preset's. Advises, never constrains."
```

---

### Task 8: budget re-measure, full verification, render-verify, docs

**Files:**
- Modify: `tests/test_sim_ui_smoke.py` (append the budget test), `document/SIMULATOR_SESSION_RESUME.md`, `document/SIMULATOR_ARCHITECTURE.md`

- [ ] **Step 1: Write the budget test — RE-MEASURED, not inherited**

```python
def test_custom_composer_refresh_fits_in_a_frame(qapp):
    """The 4a budget (2.09 ms pad drag) predates the advisory (O(N) numpy) and 25 handles that
    re-emit sigPositionChanged. Re-measure with both on. Assert the PEAK -- the eye sees the peak."""
    import time
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("custom", 150, {"nodes": [21.0] * 25}),
                          Block("ramp", 150, {"to_v": 2.0}),
                          Block("const", 150, {"v": 2.0}),
                          Block("preset", 150, {"name": "stop_and_go"})]))
    page.compose_new("custom", ticks=150, params={"nodes": [21.0] * 25})
    for _ in range(3):
        h = page._handles._items[0]; h.setPos(h._tick, 15.0)          # warm up
    ts = []
    for k in range(40):
        h = page._handles._items[k % 25]
        t0 = time.perf_counter()
        h.setPos(h._tick, 5.0 + 0.1 * k)                              # what dragging a node does
        ts.append((time.perf_counter() - t0) * 1000)
    peak = max(ts)
    assert peak < 16.7, f"custom composer refresh peaks at {peak:.2f} ms, over the 60 fps budget"
```

**If it FAILS, do not delete the test and do not raise the number.** The advisory mask is the added
cost: cache `(materialise result, mask, owner)` per `(spec, N)` and invalidate on edit, so a drag frame
recomputes only the one-block preview, not the full-scenario advisory. Measure again.

- [ ] **Step 2: Run it**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k fits_in_a_frame
```

Expected: PASS.

- [ ] **Step 3: Run the whole suite with the real number**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest \
  tests/test_sim_scenario_spec.py tests/test_sim_ui_smoke.py tests/test_sim_drag_handles.py \
  tests/test_champion_io.py $(ls tests/test_sim_*.py | grep -vE "scenario_spec|ui_smoke|drag_handles") \
  -q -p no:cacheprovider
```

Expected: **PASS**. Baseline 244 + new (T1:5, T2:3, T3:2, T4:2, T5:5, T6:5, T7:4, T8:1 → **271**). Write
the **real** number everywhere, never the predicted one. Give it ≥420 s.

- [ ] **Step 4: Verify the frozen core and the invariant are untouched**

```bash
git diff --stat origin/Simulator -- sim/state.py sim/stepper.py sim/backend.py sim/probe.py sim/events.py sim/eventprop_stepper.py utils/closed_loop_eval.py
```

Expected: **empty**. (`sim/scenario_spec.py` changed — it is not core; `materialise` itself is unchanged,
only additive helpers were added around it.)

- [ ] **Step 5: Render-verify — actually look at it**

`QT_QPA_PLATFORM=windows` (offscreen renders text as tofu). Build `SimApp`, `set_mode(3)`,
`compose_new("custom", 300, {"nodes": [...]})`, drag a node into an impossible slope, grab and **Read the
PNG**. Check: the handles on the composer plot, the red lighting only the impossible stretch (not the
whole curve), the pad greyed with its custom note, the scenario curve below with red only on the custom
span. Save two PNGs (a physical custom → no red; an impossible one → red) and Read both.

- [ ] **Step 6: Update the docs and commit**

Update `SIMULATOR_SESSION_RESUME.md`: cycle 4b done with the **real** test count; the builder now has 5
kinds (custom = a hand-drawn polyline) + a physics advisory. Update `SIMULATOR_ARCHITECTURE.md`: add
`custom`/`physics_gap`/`block_of_sample`/`DragHandles` to the module map, and bump the test count. Mark
cycle 4b as the last of the 2026-07-15 follow-up; the merge to `main` (sequenced with `Simulink_Importer`)
is the next open item.

```bash
git add document/SIMULATOR_SESSION_RESUME.md document/SIMULATOR_ARCHITECTURE.md
git commit -m "docs(sim): resume + architecture — cycle 4b (drag + custom + advisory) done"
git push origin Simulator
```

---

## Notes for whoever executes this

- **`materialise` is not touched.** The `custom` branch is in `_block_samples`; `block_of_sample` is an
  additive pure helper that *replays* materialise's layout. If you find yourself editing `materialise`,
  stop — you are about to make the attribution drift from the layout.
- **The handles are the only owner of `nodes`.** No list beside them. `_params_for('custom')` reads them
  live. The lifecycle (create before the refresh) is what makes that safe — it is Task 6's teeth.
- **The advisory reference is the neutral**, and on a custom the neutral IS the effective style (bias is
  always None). Do not reach for `effective_style` here.
- **Attribution is "owner of sample k+1", from block_of_sample** — never `cumsum(ticks)`. The seam and the
  overflow tests are what pin it.
- **`const` and `ramp` are still one computation.** The menu now shows 5 kinds of which 2 are identical.
  Untouched, deliberately. Any test assuming a ramp↔const change moves the curve fails for the wrong
  reason.
- **Do not clip the advisory into a constraint.** An impossible scenario is a valid test (`brake_margin`
  `min<0`). The red advises; the drag stays free.
```
