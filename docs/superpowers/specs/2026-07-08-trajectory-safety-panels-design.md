# Trajectory + Safety Panels — Design Spec (Extension Phase 3a)

> Design phase (brainstorming output). **No implementation** — plan follows. Scoped entirely to `sim/ui/*`;
> the golden-tested headless core (incl. `sim/probe.py`) is untouched. The physics trajectory is buffered in
> a **UI-layer** ring so the probe stays a frozen contract.

**Goal:** Surface the driving/physics signals the core already computes but discards — **trajectory**
(gap, speeds, accel over time) and **safety** (TTC, DRAC, time-headway) — as two new live docks.

**This is Extension Phase 3a** (study §6), long-deferred behind the NetViz/NetGraph interludes. Runs in `cf_sim`.

---

## 1. Decisions (locked in brainstorming, 2026-07-08)

| # | Decision | Choice |
|---|---|---|
| D1 | Substrate | `StepResult` history in a **UI-layer** `TrajectoryBuffer` (probe untouched); app appends each result |
| D2 | Metrics | pure functions in `sim/ui/metrics.py` — `ttc`, `drac`, `time_headway` (vectorised) |
| D3 | Trajectory dock | one dock, **3 X-linked sub-plots**: gap `s` (m) · speeds `v`/`vl`/`Δv` (m/s) · accel `a_ego` (m/s²) |
| D4 | Safety dock | one dock, **2 X-linked sub-plots**: TTC + time-headway (s, ref line 1.5 s) · DRAC (m/s², ref ~3.35) |
| D5 | Docks | 9 → **11** (`Trajectory`, `Safety`); the 4 presets updated |
| D6 | X-link | **intra-panel only** — NO cross-dock link (a hidden tab would corrupt the axis, per the SpikeRate lesson); a unified time cursor is Phase 3b |

**Data available (`StepResult`):** `t, s, v, vl, dv, a_ego, params, collided`. The probe records network state
only; the physics trajectory is not buffered anywhere → hence D1.

---

## 2. Components

### 2.1 `sim/ui/trajectory.py` — `TrajectoryBuffer`

```python
class TrajectoryBuffer:
    def __init__(self, capacity=500): ...        # deque(maxlen=capacity) of StepResult
    def record(self, result): ...                # append one StepResult
    def arrays(self): ...                         # {"t","s","v","vl","dv","a_ego"} -> np arrays (empty if none)
    def __len__(self): ...
```

App: `self._traj = TrajectoryBuffer()`; reset in `select_scenario`; in `_paint`, `for r in results: self._traj.record(r)` (every step, aligned with the probe).

### 2.2 `sim/ui/metrics.py` — pure safety metrics

```python
def ttc(s, dv):            # s/dv where dv>0 (closing), else +inf
def drac(s, dv):           # dv**2/(2s) where dv>0, else 0
def time_headway(s, v):    # s/v where v>0, else +inf
```

Vectorised (`np.where`), scalar-friendly. Unit-tested with exact values (e.g. `ttc(20,2)==10`, `drac(20,2)==0.1`).

### 2.3 `TrajectoryPanel` (dock `Trajectory`) — in `sim/ui/panels.py`

`GraphicsLayoutWidget`, 3 stacked `PlotItem`s X-linked to each other:
- **gap** `s` (m) — one curve;
- **speeds** — `v` (ego), `vl` (leader), `Δv` (closing) on one m/s plot (3 curves);
- **accel** `a_ego` (m/s²) — one curve, bottom plot carries the `time (steps)` x-axis.
`setDownsampling(auto, peak)` + `setClipToView(True)`. `update_frame(traj)` reads `traj.arrays()`.

### 2.4 `SafetyPanel` (dock `Safety`) — in `sim/ui/panels.py`

`GraphicsLayoutWidget`, 2 stacked X-linked `PlotItem`s:
- **times** — `TTC` + `time_headway` (s), with a dashed `InfiniteLine` at **1.5 s** (context);
- **DRAC** (m/s²), dashed ref at **~3.35** (comfortable-decel bound).
Metrics computed from `traj.arrays()` via `metrics.py`; ±inf clipped for plotting (e.g. cap at 30). Same perf config.

### 2.5 `sim/ui/layout.py` + `sim/ui/app.py`

- `DOCK_ORDER` gains `Trajectory`, `Safety` → **11**; `widgets` map + `_add_labels`/View menu updated.
- App builds both panels; `_paint` updates them from `self._traj` (network panels keep reading the probe).
- 4 presets place them — **Guida** foregrounds Road + Trajectory + Safety (the driving story); **Overview** all 11;
  **Neuro-debug**/**Identificazione** hide/compress them.
- **No cross-dock X-link** (D6).

## 3. Testing (headless, `cf_sim`)

- **TrajectoryBuffer**: `record` then `arrays()` returns the right per-field arrays; caps at `capacity`.
- **metrics**: exact values (`ttc(20,2)==10`, `ttc` closing-only → `inf` when `dv<=0`; `drac(20,2)==0.1`;
  `time_headway(20,10)==2`).
- **panels**: `TrajectoryPanel`/`SafetyPanel` build their sub-plots and `update_frame(traj)` without raising;
  Safety threshold lines exist and are visible.
- **docks/app**: 11 docks present; presets place `Trajectory`/`Safety`; preset→Overview restores all 11.
- **regression**: full golden suite green (core untouched).
- **render**: real-platform inspect of Trajectory + Safety under the Guida preset; drive + brake and watch TTC drop.

## 4. Error handling / edge cases

- Empty buffer → panels no-op. `dv<=0` (opening) → TTC/DRAC well-defined (inf/0). `v<=0` → headway inf.
- Inf metrics clipped to a plotting cap (no autorange blow-up).

## 5. Scope boundaries (OUT — later)

- **Scrub / global time cursor** → Phase 3b.
- **Energy/SynOps dock** → Phase 3a/b backlog (study §6).
- Event-timeline, per-neuron inspector, comfort/jerk bands → later.

## 6. File structure

| File | Change |
|---|---|
| `sim/ui/trajectory.py` | **Create** — `TrajectoryBuffer` |
| `sim/ui/metrics.py` | **Create** — `ttc`/`drac`/`time_headway` |
| `sim/ui/panels.py` | **Modify** — add `TrajectoryPanel`, `SafetyPanel` |
| `sim/ui/layout.py` | **Modify** — `DOCK_ORDER` (11); presets place the two |
| `sim/ui/app.py` | **Modify** — `TrajectoryBuffer`, build/wire the two panels |
| `tests/test_sim_trajectory.py` | **Create** — buffer + metrics |
| `tests/test_sim_panels.py` | **Append** — Trajectory/Safety panel smoke |
| `tests/test_sim_layout.py`, `tests/test_sim_ui_smoke.py` | **Modify** — 11-dock assertions |
