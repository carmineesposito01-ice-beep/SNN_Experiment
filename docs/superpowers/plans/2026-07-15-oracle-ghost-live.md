# Oracle Ghost in the Live Cockpit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the ACC-IIDM oracle ("Master Splinter") as a semi-transparent ghost vehicle on the road plus its gap/speed/accel curves in the Trajectory dock and TTC/headway/DRAC in the Safety dock, behind one toggle.

**Architecture:** A second `SimStepper(backend=None)` — which already exists and is already golden-tested — advances in lockstep with the net's stepper inside `SimLoop`, sharing one `EventInjector` so both see the identical leader. Its `StepResult`s land in a second `TrajectoryBuffer`. Everything is additive to `sim/ui/` only; the frozen core is untouched.

**Tech Stack:** Python 3, PySide6, pyqtgraph, numpy, pytest. Conda env `cf_sim`.

**Spec:** `docs/superpowers/specs/2026-07-15-oracle-ghost-live-design.md` — read it first, especially the boxed methodological warning (use the PEAK, not the median) and the out-of-scope debts you must NOT fix here.

---

## Before you start — environment and rules

**Worktree:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator`, branch `Simulator`. It is a git repo of its own.

**Run tests like this** (⚠️ `conda run -n cf_sim python -m pytest` intermittently crashes conda's plugin system — call the env python directly):

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_loop.py -q
```

**The full suite** is these 20 files explicitly (non-sim tests fail in `cf_sim` — never run bare `pytest`):

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest \
  tests/test_sim_state.py tests/test_sim_backend.py tests/test_sim_stepper.py \
  tests/test_sim_scenario.py tests/test_sim_events.py tests/test_sim_probe.py \
  tests/test_sim_replay.py tests/test_sim_loop.py tests/test_sim_eventprop.py \
  tests/test_sim_input_capture.py tests/test_sim_trajectory.py tests/test_sim_layout.py \
  tests/test_sim_panels.py tests/test_sim_ui_smoke.py tests/test_sim_reconstruct.py \
  tests/test_sim_platoon.py tests/test_sim_meso_panels.py tests/test_sim_meso_road.py \
  tests/test_sim_episode.py tests/test_sim_postrun.py -q
```

**Baseline: 148 passed.** This plan adds tests to existing files only — no new test file, so the list of 20 stays 20.

**Hard rules:**
- **Frozen core** — do NOT touch `sim/{state,stepper,backend,events,probe,eventprop_stepper}.py`. This plan never needs to: `SimStepper` already accepts `backend=None`.
- **No numpy LAPACK** in `cf_sim` (`matrix_rank`, `polyfit`, `lstsq`, SVD) → OMP #15 hard abort at runtime. Nothing here needs it.
- **No workarounds** — if something fails, find the root cause. A test that does not fail without your fix is not a regression test.
- **Commits:** conventional, **no `Co-Authored-By`**. Push freely.
- **Do NOT fix** the `EventInjector` ramp bug or `ReplayLog.seed` — they belong to the scenario-builder cycle (see spec §Known debt).

---

## File Structure

No new files. Five additive changes in `sim/ui/`, each with one responsibility:

| File | Responsibility for this feature |
|---|---|
| `sim/ui/loop.py` | Owns the **lockstep**: advances the ghost exactly once per net step. The only place that can guarantee sync, because it owns the fixed-timestep accumulator. Qt-free, so fully testable headless. |
| `sim/ui/panels.py` | `TrajectoryPanel.set_ghost` / `SafetyPanel.set_ghost` — draw the ghost curves; `clear()` blanks them. |
| `sim/ui/topdown.py` | The ghost vehicle + its integrated `_ghost_x`. |
| `sim/ui/reconstruct.py` | Returns a third buffer (the ghost's) for deep-scrub. |
| `sim/ui/app.py` | Wiring: builds the ghost, owns the toggle, keeps `_src_ghost_traj` swapped with the other scrub sources. |

Task order is dependency order: `loop` → `panels` → `topdown` → `reconstruct` → `app` (which consumes all four) → final verification.

---

### Task 1: SimLoop advances the ghost in lockstep

**Files:**
- Modify: `sim/ui/loop.py:10-32`
- Test: `tests/test_sim_loop.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sim_loop.py`. Note the existing imports at the top of that file already cover `SimStepper`, `SoftwareBackend`, `SimLoop`, `load_champion`, `AttributeProbe`, `np`, and `CHAMP`; add the two new ones below the existing import block:

```python
from sim.ui.trajectory import TrajectoryBuffer   # noqa: E402
from sim.events import EventInjector             # noqa: E402
from utils.closed_loop_eval import simulate      # noqa: E402


def _pair(N=60, injector=None):
    """Net stepper + oracle stepper on the same scenario, sharing one injector."""
    pg = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
    vl = np.full(N, 20.0)
    net = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, 25.0, 20.0,
                     injector=injector)
    ghost = SimStepper(None, pg, vl, 25.0, 20.0, injector=injector)
    gtraj = TrajectoryBuffer(capacity=N + 1)
    loop = SimLoop(net, AttributeProbe(capacity=100), dt_fixed=0.1,
                   ghost=ghost, ghost_traj=gtraj)
    return loop, net, ghost, gtraj


def test_loop_advances_ghost_once_per_net_step():
    loop, net, ghost, gtraj = _pair()
    loop.tick(0.35)                       # 3 fixed steps
    assert net.st.t == 3
    assert ghost.st.t == 3                # lockstep: never behind, never ahead
    assert len(gtraj) == 3


def test_loop_ghost_is_bit_identical_to_oracle_simulate():
    """The ghost driven through SimLoop must equal the validated oracle rollout, bit for bit."""
    N = 60
    loop, net, ghost, gtraj = _pair(N=N)
    loop.tick(100.0)                      # run the whole episode
    ref = simulate(None, np.array([30.0, 1.5, 2.0, 1.5, 1.5]), np.full(N, 20.0), 25.0, 20.0)
    got = gtraj.arrays()
    for k in ("s", "v", "vl", "dv", "a_ego"):
        np.testing.assert_array_equal(got[k], ref[k][:got[k].size])


def test_loop_ghost_and_net_see_the_same_leader_even_with_a_brake():
    """TEETH: the whole comparison is a lie if the two steppers ever see different leaders.
    Fails if the injector is duplicated per stepper, or if the ghost is stepped out of phase.
    The net's leader series comes from the StepResults tick() already returns -- no test-only
    bookkeeping inside SimLoop."""
    inj = EventInjector()
    loop, net, ghost, gtraj = _pair(N=60, injector=inj)
    seen = loop.tick(2.0)                        # 20 steps
    inj.enqueue(net.st.t, "brake_leader", target_v=5.0, duration=10)
    seen = seen + loop.tick(4.0)                 # 40 more steps, through the ramp
    net_vl = np.array([r.vl for r in seen], dtype=float)
    np.testing.assert_array_equal(gtraj.arrays()["vl"], net_vl)
    assert net_vl.min() < 20.0                   # the brake really happened (guards a vacuous pass)


def test_loop_without_ghost_is_unchanged():
    """Regression: default args must reproduce today's behaviour exactly."""
    pg = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
    vl = np.full(60, 20.0)
    net = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, 25.0, 20.0)
    loop = SimLoop(net, AttributeProbe(capacity=100), dt_fixed=0.1)
    r = loop.tick(0.35)
    assert len(r) == 3 and net.st.t == 3
    assert loop.ghost is None and loop.ghost_traj is None
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_loop.py -q
```

Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'ghost'`.

- [ ] **Step 3: Write the implementation**

Replace the body of `sim/ui/loop.py` (keep the module docstring, extend it):

```python
"""SimLoop -- fixed-timestep driver (Fix-Your-Timestep, Glenn Fiedler), UI-agnostic.

Pure Python (no Qt): the app wires a QTimer to call tick(elapsed); tick advances
the physics in fixed dt steps and records the probe. Keeping this Qt-free makes the
loop logic fully testable without a display.

Optionally drives a second stepper -- the ORACLE ghost (SimStepper with backend=None,
constant true params). It must advance here and nowhere else: the loop owns the
accumulator, so it is the only place that can guarantee the two stay in lockstep, and
lockstep is what makes them share the same leader tick (the injector is shared and its
tick() is idempotent -- measured, see the spec).
"""
from config import DT


class SimLoop:
    def __init__(self, stepper, probe=None, dt_fixed=DT, ghost=None, ghost_traj=None):
        self.stepper = stepper
        self.probe = probe
        self.dt_fixed = float(dt_fixed)
        self.ghost = ghost                  # SimStepper(backend=None) | None
        self.ghost_traj = ghost_traj        # TrajectoryBuffer | None
        self._accum = 0.0

    @property
    def done(self) -> bool:
        st = self.stepper.st
        return bool(st.collided or st.t >= self.stepper.N)

    def tick(self, frame_dt):
        """Advance the sim by frame_dt seconds of real time; return the StepResults run."""
        self._accum += float(frame_dt)
        out = []
        while self._accum >= self.dt_fixed and not self.done:
            r = self.stepper.step()
            if self.probe is not None and hasattr(self.stepper.backend, "read_probe"):
                self.probe.record(r.t, self.stepper.backend.read_probe(), r.params)
            self._step_ghost()
            self._accum -= self.dt_fixed
            out.append(r)
        return out

    def _step_ghost(self):
        """Advance the oracle exactly once per net step. If the oracle finished (collided or ran
        out of profile) it holds its last state: the episode is the NET's episode -- `done` reads
        the net's stepper, not this one."""
        if self.ghost is None:
            return
        gst = self.ghost.st
        if gst.collided or gst.t >= self.ghost.N:
            return
        rg = self.ghost.step()
        if self.ghost_traj is not None:
            self.ghost_traj.record(rg)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_loop.py -q
```

Expected: PASS (6 tests: the 2 original + 4 new).

- [ ] **Step 5: Commit**

```bash
git add sim/ui/loop.py tests/test_sim_loop.py
git commit -m "feat(sim): SimLoop advances the oracle ghost in lockstep

Second SimStepper(backend=None) stepped exactly once per net step, sharing the
injector so both see the identical leader. Bit-identical to the validated
closed_loop_eval.simulate(None, ...) rollout. Defaults keep today's behaviour."
```

---

### Task 2: Trajectory and Safety panels draw the ghost

**Files:**
- Modify: `sim/ui/panels.py:499-544` (TrajectoryPanel), `sim/ui/panels.py:550-592` (SafetyPanel)
- Test: `tests/test_sim_panels.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sim_panels.py`. That file already builds panels and a Qt app; reuse its existing fixtures/imports and add:

```python
def _traj_buf(n=20, v=20.0, s=25.0):
    from sim.ui.trajectory import TrajectoryBuffer
    from sim.state import StepResult
    import numpy as np
    tb = TrajectoryBuffer(capacity=n + 1)
    for t in range(n):
        tb.record(StepResult(t=t, s=s + t * 0.1, v=v, vl=20.0, dv=v - 20.0,
                             a_ego=0.1, params=np.zeros(5), collided=False))
    return tb


def test_trajectory_panel_ghost_adds_three_curves_and_keeps_one_leader():
    p = TrajectoryPanel()
    p.update_frame(_traj_buf())
    p.set_ghost(_traj_buf(v=19.0, s=24.0))
    assert p._g_s.getData()[1] is not None and len(p._g_s.getData()[1]) == 20
    assert p._g_v.getData()[1] is not None and len(p._g_v.getData()[1]) == 20
    assert p._g_a.getData()[1] is not None and len(p._g_a.getData()[1]) == 20
    # the leader is the SAME vehicle in both worlds -> exactly one leader curve on _pv
    assert not hasattr(p, "_g_vl")


def test_trajectory_panel_set_ghost_none_blanks_the_ghost_only():
    p = TrajectoryPanel()
    p.update_frame(_traj_buf())
    p.set_ghost(_traj_buf(v=19.0))
    p.set_ghost(None)
    assert p._g_s.getData()[1] is None or len(p._g_s.getData()[1]) == 0
    assert len(p._c_s.getData()[1]) == 20          # the net's curve survives


def test_safety_panel_ghost_adds_ttc_headway_drac():
    p = SafetyPanel()
    p.update_frame(_traj_buf())
    p.set_ghost(_traj_buf(v=19.0, s=24.0))
    for c in (p._g_ttc, p._g_th, p._g_drac):
        assert c.getData()[1] is not None and len(c.getData()[1]) == 20


def test_panels_clear_blanks_ghost_curves():
    """Reset/champion-swap trap: the QC already had to fix panels that did not blank."""
    for p, ghosts in ((TrajectoryPanel(), ("_g_s", "_g_v", "_g_a")),
                      (SafetyPanel(), ("_g_ttc", "_g_th", "_g_drac"))):
        p.update_frame(_traj_buf())
        p.set_ghost(_traj_buf(v=19.0))
        p.clear()
        for name in ghosts:
            d = getattr(p, name).getData()[1]
            assert d is None or len(d) == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_panels.py -q
```

Expected: FAIL — `AttributeError: 'TrajectoryPanel' object has no attribute 'set_ghost'`.

- [ ] **Step 3: Write the implementation**

In `sim/ui/panels.py`, add the shared pen constant next to the other module constants at the top of the file (near `_SAFETY_CAP`):

```python
# Oracle ghost: grey dotted, the same reference grey SynOpsPanel._ref_c uses. Legible on the dark
# theme (render-verified). The oracle is "Master Splinter" in this project's figures.
_GHOST_PEN = dict(color="#9a9a9a", width=1.6, style=Qt.DotLine)
```

In `TrajectoryPanel.__init__`, after `self._c_a = ...` (`panels.py:526`):

```python
        self._g_s = self._pg.plot(pen=pg.mkPen(**_GHOST_PEN))     # oracle gap
        self._g_v = self._pv.plot(pen=pg.mkPen(**_GHOST_PEN))     # oracle ego speed
        self._g_a = self._pa.plot(pen=pg.mkPen(**_GHOST_PEN))     # oracle accel
        # NO ghost leader curve: the leader is the same vehicle in both worlds.
```

Extend `TrajectoryPanel.clear` and add `set_ghost`:

```python
    def clear(self):
        for c in (self._c_s, self._c_v, self._c_vl, self._c_dv, self._c_a,
                  self._g_s, self._g_v, self._g_a):
            c.setData([])

    def set_ghost(self, traj):
        """Draw the oracle's gap/speed/accel, or blank them when traj is None."""
        if traj is None:
            for c in (self._g_s, self._g_v, self._g_a):
                c.setData([])
            return
        a = traj.arrays()
        if a["t"].size == 0:
            return
        self._g_s.setData(a["s"])
        self._g_v.setData(a["v"])
        self._g_a.setData(a["a_ego"])
```

In `SafetyPanel.__init__`, after `self._c_drac = ...` (`panels.py:572`):

```python
        self._g_ttc = self._pt.plot(pen=pg.mkPen(**_GHOST_PEN))    # oracle TTC
        self._g_th = self._pt.plot(pen=pg.mkPen(**_GHOST_PEN))     # oracle time-headway
        self._g_drac = self._pd.plot(pen=pg.mkPen(**_GHOST_PEN))   # oracle DRAC
```

Extend `SafetyPanel.clear` and add `set_ghost`:

```python
    def clear(self):
        for c in (self._c_ttc, self._c_th, self._c_drac,
                  self._g_ttc, self._g_th, self._g_drac):
            c.setData([])

    def set_ghost(self, traj):
        """Draw the oracle's TTC/headway/DRAC with the SAME formulas and the SAME clip as the net's
        curves, or blank them when traj is None."""
        if traj is None:
            for c in (self._g_ttc, self._g_th, self._g_drac):
                c.setData([])
            return
        a = traj.arrays()
        if a["t"].size == 0:
            return
        self._g_ttc.setData(np.clip(metrics.ttc(a["s"], a["dv"]), 0, _SAFETY_CAP))
        self._g_th.setData(np.clip(metrics.time_headway(a["s"], a["v"]), 0, _SAFETY_CAP))
        self._g_drac.setData(metrics.drac(a["s"], a["dv"]))
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_panels.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/panels.py tests/test_sim_panels.py
git commit -m "feat(sim): Trajectory and Safety panels can draw the oracle ghost

set_ghost(traj|None) adds gap/speed/accel and TTC/headway/DRAC in reference grey
dotted, reusing the same metric functions and the same 30 s clip as the net's
curves. clear() blanks them too (the Reset/swap trap the QC already hit once).
No ghost leader curve: it is the same vehicle in both worlds."
```

---

### Task 3: The road draws the ghost vehicle

**Files:**
- Modify: `sim/ui/topdown.py:37-149`
- Test: `tests/test_sim_ui_smoke.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sim_ui_smoke.py` (it already has a Qt app fixture and imports; add `TopDownView` and `StepResult` if not already imported):

```python
def _res(t, v, s):
    from sim.state import StepResult
    import numpy as np
    return StepResult(t=t, s=s, v=v, vl=20.0, dv=v - 20.0, a_ego=0.0,
                      params=np.zeros(5), collided=False)


def test_topdown_ghost_x_integrates_and_resets():
    from sim.ui.topdown import TopDownView
    from config import DT
    view = TopDownView()
    for t in range(10):
        view.update_ghost(_res(t, 19.0, 24.0))
    assert view.ghost_x_m() == pytest.approx(10 * 19.0 * DT)
    view.reset()
    assert view.ghost_x_m() == 0.0            # else the ghost drives off across episodes


def test_topdown_ghost_hidden_by_default_and_toggleable():
    from sim.ui.topdown import TopDownView
    view = TopDownView()
    assert view._ghost.isVisible() is False
    view.set_ghost_visible(True)
    assert view._ghost.isVisible() is True


def test_topdown_render_ghost_at_reconstructs_position():
    from sim.ui.topdown import TopDownView
    from sim.ui.trajectory import TrajectoryBuffer
    from config import DT
    view = TopDownView()
    tb = TrajectoryBuffer(capacity=11)
    for t in range(10):
        tb.record(_res(t, 19.0, 24.0))
    view.render_ghost_at(tb, 4)               # x = sum of v*DT up to index 4 inclusive
    assert view.ghost_x_m() == pytest.approx(5 * 19.0 * DT)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q
```

Expected: FAIL — `AttributeError: 'TopDownView' object has no attribute 'update_ghost'`.

- [ ] **Step 3: Write the implementation**

In `sim/ui/topdown.py`, add the constant near `_COL` (top of file):

```python
GHOST_COLOR = "#9a9a9a"      # oracle ("Master Splinter"), same reference grey as the panels
GHOST_OPACITY = 0.45
```

In `TopDownView.__init__`, after `self._leader_label = self._label("leader")` (`topdown.py:54`):

```python
        self._ghost_x = 0.0
        self._ghost = self._vehicle(GHOST_COLOR)
        self._ghost.setOpacity(GHOST_OPACITY)
        self._ghost_label = self._label("oracolo")
        self._ghost_label.setDefaultTextColor(QColor(GHOST_COLOR))
        self._set_ghost_visible_items(False)          # off until the toggle asks for it
```

Add the methods (place them next to `reset`/`ego_x_m`, `topdown.py:100-111`):

```python
    def _set_ghost_visible_items(self, on):
        self._ghost.setVisible(bool(on))
        self._ghost_label.setVisible(bool(on))

    def set_ghost_visible(self, on):
        self._set_ghost_visible_items(on)

    def ghost_x_m(self):
        return self._ghost_x

    def _place_ghost(self, ghost_x):
        self._ghost_x = ghost_x
        px = self._ghost_x * PX_PER_M
        self._ghost.setPos(px, 0)
        self._ghost_label.setPos(px - 20, VEH_W_M * PX_PER_M + 18)

    def update_ghost(self, r):
        """Integrate the oracle's position exactly like the ego's (topdown.py update_frame)."""
        self._place_ghost(self._ghost_x + r.v * DT)

    def advance_ghost(self, r):
        """Integrate without rendering -- mirrors advance() for coalesced ticks at speed>1."""
        self._ghost_x += r.v * DT

    def render_ghost_at(self, traj, index):
        """Reconstruct the oracle's position at buffer position `index`: x = sum v*DT up to index."""
        a = traj.arrays()
        if a["t"].size == 0:
            return
        n = a["t"].size
        i = index if index >= 0 else n + index
        i = max(0, min(i, n - 1))
        self._place_ghost(float(a["v"][:i + 1].sum() * DT))
```

Extend `reset` (`topdown.py:100-105`) — the docstring there already explains why this matters:

```python
    def reset(self):
        """Reset the integrated ego position (called per episode). Without this the car drives off
        the finite road across successive runs, and live vs scrub (which recomputes x = Σv·DT from 0)
        would disagree from the 2nd episode on. Same reasoning for the ghost."""
        self._ego_x = 0.0
        self._last_s = 0.0
        self._ghost_x = 0.0
        self._place_ghost(0.0)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/topdown.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): road draws the semi-transparent oracle ghost

Its x is integrated exactly like the ego's and zeroed in reset() -- the same bug
the ego already had once (car driving off across episodes). Hidden by default.
Measured: the ghost never leaves the viewport (worst case 29.6 m vs +-43.8 m,
0/36 champion x scenario combinations), so no follow/clamp logic is needed."
```

---

### Task 4: Deep-scrub reconstructs the ghost

**Files:**
- Modify: `sim/ui/reconstruct.py:16-49`
- Test: `tests/test_sim_reconstruct.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sim_reconstruct.py` (reuse its existing imports/fixtures):

```python
def test_reconstruct_returns_a_ghost_matching_the_live_ghost():
    """The reconstructed oracle must equal the live one on the overlap, or deep-scrub lies."""
    import numpy as np
    from sim.ui.loop import SimLoop
    from sim.ui.trajectory import TrajectoryBuffer
    from sim.stepper import SimStepper
    from sim.backend import SoftwareBackend
    from sim.probe import AttributeProbe
    from sim.replay import ReplayLog
    from sim.events import EventInjector
    from sim.scenario import manual_scenario

    pg = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
    sc = manual_scenario(pg, np.full(40, 20.0), 25.0, 20.0)
    champ = load_champion(CHAMP)
    inj = EventInjector()
    net = SimStepper.from_scenario(SoftwareBackend(champ.model), sc, injector=inj)
    ghost = SimStepper.from_scenario(None, sc, injector=inj)
    gtraj = TrajectoryBuffer(capacity=41)
    loop = SimLoop(net, AttributeProbe(capacity=100), dt_fixed=0.1, ghost=ghost, ghost_traj=gtraj)
    loop.tick(100.0)

    probe, traj, rghost = reconstruct_history(champ, sc, ReplayLog.from_injector(0, inj), 39)
    live, rec = gtraj.arrays(), rghost.arrays()
    n = min(live["t"].size, rec["t"].size)
    for k in ("s", "v", "vl", "dv", "a_ego"):
        np.testing.assert_array_equal(rec[k][:n], live[k][:n])
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_reconstruct.py -q
```

Expected: FAIL — `ValueError: not enough values to unpack (expected 3, got 2)`.

- [ ] **Step 3: Write the implementation**

Rewrite `sim/ui/reconstruct.py` — both functions now return a triple. The ghost is **fully re-run every time**, never spliced: it has no SNN forward, so it costs microseconds, and inheriting the prefix-splice complexity would buy nothing.

```python
"""reconstruct_history -- deterministic re-run of an episode into FULL-length buffers.

Deep-scrub foundation. The live probe is a 500-tick ring buffer; to scrub ticks
older than that we re-run from the ReplayLog (seed + logged events) into an
AttributeProbe/TrajectoryBuffer sized to the whole episode. Bit-identical to the
live run: same stepper.step(), same backend.read_probe(); no per-step RNG, the
scenario is a fixed array, the champion is fixed, injector.tick is deterministic.
Read-only -- the frozen core is untouched.

The oracle ghost is rebuilt here too, with backend=None. It has no SNN forward, so a
full re-run costs microseconds (against ~0.74 s for the net): it is never spliced.
"""
from sim.backend import SoftwareBackend
from sim.probe import AttributeProbe
from sim.stepper import SimStepper
from sim.ui.trajectory import TrajectoryBuffer


def _run_ghost(scenario, replaylog, n):
    """Full oracle re-run, 0..n-1. Its own injector instance: it is rebuilt from the same log,
    so it drains the identical events."""
    ghost = SimStepper.from_scenario(None, scenario, injector=replaylog.build_injector())
    gtraj = TrajectoryBuffer(capacity=n)
    for _ in range(n):
        if ghost.st.collided or ghost.st.t >= ghost.N:
            break
        gtraj.record(ghost.step())
    return gtraj


def reconstruct_history(champion, scenario, replaylog, upto):
    """Re-run scenario 0..upto and return (probe, traj, ghost_traj) filled with every tick."""
    n = int(upto) + 1
    backend = SoftwareBackend(champion.model)
    stepper = SimStepper.from_scenario(backend, scenario,
                                       injector=replaylog.build_injector())
    probe = AttributeProbe(capacity=n)
    traj = TrajectoryBuffer(capacity=n)
    for _ in range(n):
        if stepper.st.collided or stepper.st.t >= stepper.N:
            break
        r = stepper.step()
        probe.record(r.t, backend.read_probe(), r.params)
        traj.record(r)
    return probe, traj, _run_ghost(scenario, replaylog, n)


def reconstruct_spliced(champion, scenario, replaylog, upto, live_probe, live_traj):
    """Deep-scrub reconstruction that re-runs ONLY the pre-buffer prefix (episode_len - buffer)
    and splices it with the live ring buffer, which already holds the tail bit-identically. Cuts
    a 600-tick episode from ~7.7 s (full re-run) to ~1 s. Falls back to a full reconstruct if the
    live buffers don't cleanly cover the tail up to `upto`. The ghost is always fully re-run (cheap)."""
    live_frames = live_probe.frames()
    live_results = live_traj.results()
    ok = (live_frames and live_results and len(live_frames) == len(live_results)
          and live_frames[0].t == live_results[0].t and live_frames[-1].t == int(upto))
    prefix_len = live_frames[0].t if live_frames else 0
    n = int(upto) + 1
    if not ok or prefix_len <= 0:
        return reconstruct_history(champion, scenario, replaylog, upto)   # buffer already whole, or misaligned
    pfx_probe, pfx_traj, _ = reconstruct_history(champion, scenario, replaylog, prefix_len - 1)
    probe = AttributeProbe.from_frames(pfx_probe.frames() + live_frames, n)
    traj = TrajectoryBuffer.from_results(pfx_traj.results() + live_results, n)
    return probe, traj, _run_ghost(scenario, replaylog, n)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_reconstruct.py -q
```

Expected: PASS. Any pre-existing test in that file that unpacks two values will now fail — fix those call sites to unpack three; that is the intended blast radius of the signature change.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/reconstruct.py tests/test_sim_reconstruct.py
git commit -m "feat(sim): reconstruct returns the oracle ghost as a third buffer

The ghost is fully re-run every time rather than spliced: with no SNN forward it
costs microseconds, so the prefix-splice complexity (which exists only because the
net's forward is slow) buys nothing here."
```

---

### Task 5: Wire the ghost into the app and add the toggle

**Files:**
- Modify: `sim/ui/app.py` — `select_scenario` (`:402-432`), `_clear_panels` (`:434-440`), `_paint` (`:458-480`), `_redraw_series` (`:489-500`), `_on_run_toggled` (`:520-546`), `_render_at_cursor` (`:551-561`), `_reconstruct` (`:582-595`), controls row (`:136-141`)
- Test: `tests/test_sim_ui_smoke.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sim_ui_smoke.py`:

```python
def test_app_builds_a_ghost_and_toggle_is_off_by_default(qt_app):
    win = SimApp(CHAMP)
    assert win.loop.ghost is not None
    assert win.loop.ghost.backend is None            # it IS the oracle, not a second net
    assert win._ghost_toggle.isChecked() is False
    assert win._topdown._ghost.isVisible() is False


def test_app_toggle_shows_ghost_on_road_and_panels(qt_app):
    win = SimApp(CHAMP)
    win._advance(1.0)
    win._ghost_toggle.setChecked(True)
    assert win._topdown._ghost.isVisible() is True
    assert len(win._trajectory._g_s.getData()[1]) > 0
    assert len(win._safety._g_ttc.getData()[1]) > 0
    win._ghost_toggle.setChecked(False)
    assert win._topdown._ghost.isVisible() is False
    d = win._trajectory._g_s.getData()[1]
    assert d is None or len(d) == 0


def test_app_ghost_scrub_source_swaps_with_the_others(qt_app):
    """TEETH: if _src_ghost_traj is not swapped together with _src_probe/_src_traj, a deep scrub
    renders the oracle from the live tail against a past net state -- a plausible-looking lie."""
    win = SimApp(CHAMP)
    win._ghost_toggle.setChecked(True)
    win._advance(70.0)                               # > 500 ticks -> the ring buffer wraps
    win._run_btn.setChecked(True)
    win._run_btn.setChecked(False)                   # manual pause -> deep reconstruct
    assert win._src_traj is not win._traj            # reconstruction really happened
    assert win._src_ghost_traj is not win._ghost_traj
    assert len(win._src_ghost_traj.arrays()["t"]) == len(win._src_traj.arrays()["t"])


def test_app_reset_blanks_the_ghost(qt_app):
    win = SimApp(CHAMP)
    win._ghost_toggle.setChecked(True)
    win._advance(1.0)
    win.reset_run()
    d = win._trajectory._g_s.getData()[1]
    assert d is None or len(d) == 0
    assert win._topdown.ghost_x_m() == 0.0
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q
```

Expected: FAIL — `AttributeError: 'SimApp' object has no attribute '_ghost_toggle'`.

- [ ] **Step 3: Write the implementation**

**3a — the toggle.** In `__init__`, after `self._brake_btn = ...` (`app.py:127`):

```python
        self._ghost_toggle = QCheckBox("Oracolo")
        self._ghost_toggle.setToolTip(
            "Guidatore di riferimento (ACC-IIDM) con i parametri veri — 'Master Splinter'.\n"
            "Parte dallo stesso stato e DIVERGE per costruzione: è un rollout indipendente,\n"
            "non l'errore istantaneo della rete. Sovrapposto = la rete guida come il guidatore vero.")
        self._ghost_toggle.toggled.connect(self._on_ghost_toggled)
```

Add `QCheckBox` to the PySide6 widget import at the top of `app.py`. Put the widget in the controls row (`app.py:137-140`), right after `self._brake_btn`:

```python
        for w in (QLabel("champion"), self._champ_selector, self._selector,
                  self._run_btn, self._step_btn, self._reset_btn,
                  self._brake_btn, self._ghost_toggle, QLabel("speed"), self._speed_slider,
                  QLabel("t"), self._cursor_slider, self._cursor_readout):
            controls.addWidget(w)
```

**3b — build the ghost.** In `select_scenario`, replace lines `app.py:411-420` with:

```python
        self._traj = TrajectoryBuffer()
        self._ghost_traj = TrajectoryBuffer()
        self._src_probe = self._probe                     # scrub source: live buffer while running
        self._src_traj = self._traj
        self._src_ghost_traj = self._ghost_traj
        self._recon_key = None                            # invalidate the reconstruction cache
        self._episode = EpisodeSummary(self._synops._dims,   # fresh per-scenario summary (refreshes dims on swap)
                                       params_gt=self._scenarios[self._current_idx].params_gt,
                                       model=self._champ.model)
        backend = SoftwareBackend(self._champ.model)
        stepper = SimStepper.from_scenario(backend, sc, injector=self._injector)
        ghost = SimStepper.from_scenario(None, sc, injector=self._injector)   # SAME injector: same leader
        self.loop = SimLoop(stepper, self._probe, dt_fixed=DT,
                            ghost=ghost, ghost_traj=self._ghost_traj)
```

**3c — clear.** Extend `_clear_panels` (`app.py:434-440`) — the panels' own `clear()` now blanks the ghost curves (Task 2), so only the explicit `set_ghost(None)` is needed for the case where the toggle is on:

```python
    def _clear_panels(self):
        """Blank every cockpit panel (empty buffers early-return in update_frame, so a redraw would
        NOT clear the old curves) and reset the road's integrated ego/ghost positions."""
        for p in (*self._params, self._spikerate, self._trajectory,
                  self._safety, self._timeline, self._synops, self._netstate):
            p.clear()
        self._trajectory.set_ghost(None)
        self._safety.set_ghost(None)
        self._topdown.reset()
```

**3d — paint.** In `_paint`, extend the scrub-source line (`app.py:461`) and drive the ghost on the road. Replace `app.py:461-468` with:

```python
            self._last_result = results[-1]
            self._src_probe, self._src_traj = self._probe, self._traj   # live advanced -> scrub source = live
            self._src_ghost_traj = self._ghost_traj
            last = len(results) - 1
            g_results = self._ghost_traj.results()[-len(results):]      # ghost stepped in lockstep by SimLoop
            for i, r in enumerate(results):                             # speed>1 -> many results per paint
                if i == last:
                    self._topdown.update_frame(r)                       # render only the final tick (others coalesce)
                else:
                    self._topdown.advance(r)                            # integrate ego position only, no QGraphics work
                self._traj.record(r)
            for i, rg in enumerate(g_results):
                if i == len(g_results) - 1:
                    self._topdown.update_ghost(rg)
                else:
                    self._topdown.advance_ghost(rg)
```

**3e — redraw.** Change `_redraw_series` (`app.py:489`) to take the ghost buffer and gate it on the toggle:

```python
    def _redraw_series(self, probe, traj, ghost_traj=None):
        for name, p in zip(("v0", "T", "s0", "a", "b"), self._params):
            if self._dock_on(name):
                p.update_frame(probe)
        if self._dock_on("SpikeRate"): self._spikerate.update_frame(probe)
        if self._dock_on("SynOps"): self._synops.update_frame(probe)
        show_ghost = self._ghost_toggle.isChecked()
        if self._dock_on("Trajectory"):
            self._trajectory.update_frame(traj)
            self._trajectory.set_ghost(ghost_traj if show_ghost else None)
        if self._dock_on("Safety"):
            self._safety.update_frame(traj)
            self._safety.set_ghost(ghost_traj if show_ghost else None)
        if self._dock_on("NetState"): self._netstate.update_frame(probe)   # head; scrub overrides via _render_at_cursor
        if self._dock_on("Events"): self._timeline.update_events(self._injector.log(), probe.frames())
        if self._dock_on("Inspector") and self._inspector.neuron is not None:
            self._inspector.update_frame(probe)
```

Update its two call sites: `app.py:473` → `self._redraw_series(self._probe, self._traj, self._ghost_traj)`, and `app.py:540` → `self._redraw_series(self._src_probe, self._src_traj, self._src_ghost_traj)`.

**3f — the toggle handler.** Add next to `_on_speed` (`app.py:517`):

```python
    def _on_ghost_toggled(self, on: bool):
        self._topdown.set_ghost_visible(on)
        self._redraw_series(self._src_probe, self._src_traj, self._src_ghost_traj)
        if on and self._cursor is not None:
            self._topdown.render_ghost_at(self._src_ghost_traj, self._cursor)
```

**3g — scrub sources.** In `_on_run_toggled`, line `app.py:524` becomes:

```python
            self._src_probe, self._src_traj = self._probe, self._traj
            self._src_ghost_traj = self._ghost_traj
```

and lines `app.py:536-539` become:

```python
            if (not auto) and frames and frames[-1].t + 1 > self._probe.capacity:   # manual pause + buffer wrapped -> reconstruct
                self._src_probe, self._src_traj, self._src_ghost_traj = self._reconstruct(frames[-1].t)
            else:
                self._src_probe, self._src_traj = self._probe, self._traj
                self._src_ghost_traj = self._ghost_traj
```

**3h — cursor.** In `_render_at_cursor` (`app.py:551`), after `self._topdown.render_at(self._src_traj, idx)`:

```python
        if self._ghost_toggle.isChecked():
            self._topdown.render_ghost_at(self._src_ghost_traj, idx)
```

**3i — reconstruct cache.** In `_reconstruct` (`app.py:582`), replace lines `:592-595`:

```python
        probe, traj, ghost = reconstruct_spliced(self._champ, self._scenarios[self._current_idx], rlog, upto,
                                                 self._probe, self._traj)
        self._recon_key, self._recon_probe, self._recon_traj = key, probe, traj
        self._recon_ghost = ghost
        return probe, traj, ghost
```

and the cache-hit branch at `:587-588`:

```python
        if self._recon_key == key:
            return self._recon_probe, self._recon_traj, self._recon_ghost
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/app.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): wire the oracle ghost into the cockpit behind one toggle

The ghost shares the injector with the net's stepper, so both see the identical
leader. _src_ghost_traj is swapped together with _src_probe/_src_traj at every
site: leaving it behind would render the oracle from the live tail against a past
net state during a deep scrub. Toggle off -> ghost not drawn and not computed."
```

---

### Task 6: Full suite, render-verify, and docs

**Files:**
- Modify: `document/SIMULATOR_SESSION_RESUME.md`

- [ ] **Step 1: Run the whole sim suite**

Run the 20-file command from the header of this plan.
Expected: **PASS, 148 + the new tests** (Task 1 adds 4, Task 2 adds 4, Task 3 adds 3, Task 4 adds 1, Task 5 adds 4 → expect **164 passed**). If the count is lower, find which file lost a test — do not "fix" it by deleting an assertion.

- [ ] **Step 2: Verify the frozen core is untouched**

```bash
git diff --stat origin/Simulator -- sim/state.py sim/stepper.py sim/backend.py sim/events.py sim/probe.py sim/eventprop_stepper.py
```

Expected: **empty output**. Any change here is a bug in the execution of this plan, not a decision to be justified.

- [ ] **Step 3: Render-verify — actually look at it**

Write this to `verify_ghost.py` **in your session's scratchpad directory, not in the repo** (the PNG it
writes lands in the repo but `verify_*.png` is already gitignored):

```python
import os
os.environ["QT_QPA_PLATFORM"] = "windows"      # 'offscreen' renders text as tofu
import sys
W = r"D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator"
sys.path.insert(0, W)
from PySide6.QtWidgets import QApplication
from sim.ui.app import SimApp
from sim.ui.theme import apply_dark_theme

app = QApplication(sys.argv)
apply_dark_theme(app)
win = SimApp(os.path.join(W, "champions", "R33_C2_A1_T12_fix", "best_model.pt"))
win.resize(1500, 900)
win.show()
win.select_scenario(1)                          # stop_and_go: the ghost separates visibly here
win._ghost_toggle.setChecked(True)
for _ in range(60):
    win._advance(1.0)
    QApplication.processEvents()
win.grab().save(os.path.join(W, "verify_ghost.png"))
print("saved")
```

Run it with the env python, then **Read the PNG and look at it**. Check: the ghost is on the road and semi-transparent; the grey dotted curves are in Trajectory and Safety; nothing else changed. `verify_*.png` is already gitignored.

- [ ] **Step 4: Update the resume doc**

In `document/SIMULATOR_SESSION_RESUME.md`: move action 1 from "IN CORSO — spec approvata" to done, note the new test count in §How to work (replacing **148**), and add the ghost to §Architecture's Live UI description. Leave actions 2 and 3 (the other two cycles) untouched.

- [ ] **Step 5: Commit and push**

```bash
git add document/SIMULATOR_SESSION_RESUME.md
git commit -m "docs(sim): resume — cycle 1 (oracle ghost) done

164 sim tests green, frozen core bit-identical, render-verified on windows."
git push origin Simulator
```

If the suite reports a number other than 164, put the **real** number in the message and in the resume
doc. Do not write 164 because the plan said so — that is how a dated snapshot becomes a lie, and this
repo already carries a paragraph of warnings about exactly that.

---

## Notes for whoever executes this

- **The oracle is not yours to invent.** It already exists (`SimStepper(backend=None)`) and is already golden-tested bit-identical (`tests/test_sim_stepper.py:36-41`). If you find yourself writing car-following physics, stop: you have taken a wrong turn.
- **The shared injector is the load-bearing decision.** Its `tick()` is idempotent — this was measured, not assumed (7/7 event patterns × 600 ticks, bit-identical for one vs two calls per tick). If you ever give the ghost its own injector instance in the live loop, the two will see different leaders and every comparison the feature draws becomes a lie. The test in Task 1 has teeth for exactly this.
- **Do not fix the ramp bug you will notice** in `sim/events.py:37-38` (two sequential brakes make the leader jump +16 m/s). It is real and measured, it is documented in the spec, and it belongs to the scenario-builder cycle.
