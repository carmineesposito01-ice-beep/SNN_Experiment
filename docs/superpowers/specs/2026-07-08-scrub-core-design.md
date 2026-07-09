# Time-Scrub Core — Design Spec (Extension Phase 3b.1)

> Design phase (brainstorming output). **No implementation** — plan follows. Scoped entirely to `sim/ui/*`;
> the golden-tested headless core is untouched. First slice of Phase 3b (event-timeline + inspector are 3b.2/3b.3).

**Goal:** Pause the live sim and **scrub a global time cursor** over the buffered history — read every dock at a
frozen tick `t`: a vertical cursor line on the time-series plots, the **network graph** showing the neuron state
**at `t`**, and the **road reconstructed** to `t`.

**This is Extension Phase 3b.1** (study §5/§6). Runs in `cf_sim`.

---

## 1. Decisions (locked in brainstorming, 2026-07-08)

| # | Decision | Choice |
|---|---|---|
| D1 | Interaction | **Running = live** (cursor at head); **paused = scrub** (cursor free). Space toggles Run |
| D2 | Control | a **time slider** (0..len-1) in the controls row + shortcuts `Space`/`←`/`→`/`Home`/`End`; a `t=… (…s)` readout |
| D3 | Time-series docks | each exposes `set_cursor(x)` → a dashed **vertical cursor line** at `x` (hidden when live). Panels: params, v_mem, SpikeRate, Trajectory, Safety |
| D4 | NetGraph at `t` | `NeuronGraphPanel.update_frame(probe, index=-1)` becomes **index-aware** → renders `frames()[index]` |
| D5 | Road at `t` | `TopDownView.render_at(traj, index)` **reconstructs** ego/leader from the traj buffer (`ego_x = Σ v·DT` up to `index`) |
| D6 | Scope | **core scrub only**; event-timeline → 3b.2, per-neuron inspector → 3b.3 |

**Alignment:** the probe and the `TrajectoryBuffer` both record every step of the same loop, so buffer index `i`
is consistent across all docks (time-series plot with implicit `x = arange(len)`). `injector.log()` (events) is
tick-indexed — used only in 3b.2.

---

## 2. Components

### 2.1 Cursor line on time-series panels (`sim/ui/panels.py`)

A small mixin so all five panels share one implementation:

```python
class _CursorMixin:
    def set_cursor(self, x):
        for c in getattr(self, "_cursors", ()):
            if x is None:
                c.setVisible(False)
            else:
                c.setPos(float(x)); c.setVisible(True)
```

Each time-series panel inherits it, and in `__init__` builds one dashed vertical `InfiniteLine` **per plot**
(hidden), collected in `self._cursors` (via a `_add_cursor(plot)` helper). `ParamPanel`/`VmemPanel`/`SpikeRatePanel`
have one plot → one cursor; `TrajectoryPanel` (3 sub-plots) / `SafetyPanel` (2) → one per sub-plot.

### 2.2 `NeuronGraphPanel.update_frame(probe, index=-1)` — index-aware

`f = frames[index]` (clamped) instead of `frames[-1]`. Everything else unchanged; live callers pass nothing (`-1`).

### 2.3 `TopDownView.render_at(traj, index)` — reconstruct

Extract the existing placement into `_place(ego_x, s, dv)`; `update_frame(r)` keeps integrating incrementally then
calls `_place`; **`render_at(traj, index)`** reads `traj.arrays()`, computes `ego_x = cumsum(v)[i]·DT`, `s=s[i]`,
`dv=dv[i]`, and calls `_place`. At the head the two agree (both `∫v dt`).

### 2.4 App scrub logic (`sim/ui/app.py`)

- State: `self._cursor` (`None` = live/head). A `QSlider` `self._cursor_slider` in the controls row; a
  `self._cursor_readout` `QLabel`.
- **Run ON** (`_on_run_toggled(True)` / `_on_timer`): live — panels render at head; `set_cursor(None)` on all
  time-series panels; slider disabled and tracking `len-1`.
- **Run OFF** (pause): scrub enabled; slider range `0..len-1`, value = head.
- `_render_at_cursor(idx)`: `for p in time_series_panels: p.set_cursor(idx)`; `self._netstate.update_frame(self._probe, idx)`;
  `self._topdown.render_at(self._traj, idx)`; readout `f"t={frames[idx].t} ({...}s)"`.
- `_on_cursor(v)` (slider): if paused → `self._cursor = v; self._render_at_cursor(v)`.
- `_step_cursor(d)`: if paused → clamp `cursor+d` into `[0, len-1]`, set slider (→ `_on_cursor`).
- `keyPressEvent`: `Space` → toggle `_run_btn`; `Left`/`Right` → `_step_cursor(-1/+1)`; `Home`/`End` → 0 / `len-1`.

## 3. Testing (headless, `cf_sim`)

- **set_cursor**: on a panel, `set_cursor(5)` → its cursor line(s) visible at `x=5`; `set_cursor(None)` → hidden.
- **NetGraph index-aware**: two probe frames with different `v_mem`; `update_frame(probe, 0)` vs `(probe, 1)` set
  different node brushes (compare `_nodes.data`), and don't raise on out-of-range (clamped).
- **TopDownView.render_at**: after recording a known traj, `render_at(traj, i)` → `ego_x_m() == cumsum(v)[i]·DT`
  and `render_at(traj, -1) == update_frame(last)` (head agreement).
- **app scrub**: build `SimApp`, `_advance` a few steps, pause, `_render_at_cursor(2)` → `self._cursor == 2` and
  the panels' cursors visible; `_step_cursor(+1)` clamps within range.
- **regression**: full golden suite green.
- **render**: real-platform — Run a bit, pause, drag the slider / press ←→, watch the cursor line + net-graph state
  + road move to the frozen tick. Send the PNG.

## 4. Error handling / edge cases

- Empty buffer → scrub no-op. `index` clamped to `[0, len-1]`. Live→pause keeps the current head as the cursor
  start. Leaving pause (Run) restores live rendering and hides the cursor lines.

## 5. Scope boundaries (OUT — later)

- **Event-timeline** (marks from `injector.log()`, click→seek) → 3b.2.
- **Per-neuron inspector, input-encoding view** → 3b.3.
- **ReplayLog re-run beyond the 500-tick buffer** → later (scrub here is within the ring buffer).

## 6. File structure

| File | Change |
|---|---|
| `sim/ui/panels.py` | **Modify** — `_CursorMixin` + `_add_cursor` + `set_cursor`/`_cursors` on the 5 time-series panels; `NeuronGraphPanel.update_frame(probe, index=-1)` |
| `sim/ui/topdown.py` | **Modify** — extract `_place`; add `render_at(traj, index)` |
| `sim/ui/app.py` | **Modify** — cursor state, slider, readout, shortcuts, `_render_at_cursor`/`_on_cursor`/`_step_cursor`, Run on/off scrub gating |
| `tests/test_sim_panels.py` | **Append** — set_cursor + NetGraph index-aware |
| `tests/test_sim_ui_smoke.py` | **Append** — TopDownView.render_at + app scrub (cursor/step) |
