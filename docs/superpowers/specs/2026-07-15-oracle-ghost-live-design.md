# Oracle ghost in the Live cockpit — Design Spec

**Date:** 2026-07-15 · **Branch/worktree:** `Simulator` · **Status:** design approved (user) → spec

## Goal

Show the **oracle** — the reference driver everything is measured against — as a semi-transparent
**ghost vehicle** on the road, plus its curves in the **Trajectory** and **Safety** docks, behind a
single toggle. The oracle is the ACC-IIDM controller driven by the scenario's **true** parameters:
what the real driver would have done, running from the same initial state.

This is the first of **three separate cycles** the user's 2026-07-15 request decomposes into. The
other two (checkpoint identity + view adaptivity; custom scenario builder) get their own spec/plan.
See §Out of scope.

## Established facts (verified in code, or measured — not assumed)

- **The oracle already exists and is already golden-tested.** `SimStepper` takes `backend=None` and
  then uses the constant `params_gt` instead of the net's prediction (`sim/stepper.py:71-74`); the rest
  of the physics is identical. `tests/test_sim_stepper.py:36-41` asserts it **bit-identical**
  (`assert_array_equal`, not `allclose`) against `utils/closed_loop_eval.simulate(None, …)`.
  → **This cycle is wiring, not physics.** No new model, no new estimator.
- **The reference model is ACC-IIDM + CAH, not plain IDM** (Treiber & Kesting Ch.12 §12.4).
  `CF_FSNN_Net.acc_iidm_accel` (`core/network.py:568`) is a `@staticmethod`: pure parametric physics,
  the net is not involved. The net only produces the 5 numbers handed to it. Plain `idm_accel`
  (`core/network.py:532`) is kept as a reference and is **not** the trained path (`:535-536`).
- **The oracle already has a name in this project**: *Master Splinter*, grey, dotted
  (`scripts/_build_eval_v3_notebook.py:89`, `presentation/_shared/figures_common_dark.py:24`).
  `champions/README.md:9-10`: it is not a checkpoint, it is *a way of running*.
- **`params_gt` is a module constant**, `sim/ui/app.py:40` = `[30.0, 1.5, 2.0, 1.5, 1.5]`, shared by
  every scenario (`sim/scenario.py:28`). It is the driver the scenarios presuppose — `build_scenarios`
  derives the equilibrium gap and `v_set = 0.7·v0` from it (`utils/closed_loop_eval.py:326-341`).
- **`EventInjector.tick(t, base_vl)` is idempotent** — MEASURED, not reasoned: 7/7 event patterns
  × 600 ticks, the leader series is **bit-identical** whether `tick()` is called once or twice per
  tick (`_events` is drained on the first call, `_brake` stays armed, `_effective_leader` is a pure
  function of `(t, base_vl, _brake)` — `sim/events.py:34-53`).
  → **The two steppers can share one injector**, so the ghost sees exactly the same leader as the net.
  This is the invariant the whole comparison rests on.
- **The ghost never leaves the road view** — MEASURED across 4 champions × 9 scenarios: worst-case
  ego↔ghost separation **29.6 m** against a **±43.8 m** viewport (`PX_PER_M = 8.0`, ~700 px dock);
  **0/36** combinations go off-screen at any tick. → No follow/clamp/off-screen-indicator machinery.
- **Absolute integration is the correct placement.** `ghost_x = Σ v_ghost·DT` (mirroring
  `topdown.py:135,139` for the ego) and `ego_x + (s_snn − s_ghost)` are *mathematically the same
  quantity* while the leader is shared, and measure the same (5.7 vs 5.6 m median max). They diverge
  only on `cut_in` (13.5 vs 7.4 m), where the absolute form is the **physically correct** one: after a
  cut-in the intruding vehicle appears at a fixed gap from *each* ego (`sim/stepper.py:59-60` sets
  `st.s` discontinuously), so the two worlds no longer share a leader.
- **The ghost has no probe.** No net → no spikes, no `read_probe()`. NetState, SpikeRate, SynOps and
  Inspector are out of its reach by construction.
- **The ghost is champion-independent.** It depends only on `(scenario, injector)`. Swapping champion
  does not change it — though `select_champion` → `select_scenario` (`sim/ui/app.py:324`) rebuilds it
  anyway, which is correct and costs nothing.
- **Deep-scrub of the ghost is nearly free.** `reconstruct_history` (`sim/ui/reconstruct.py:16-30`)
  re-runs the episode; with `backend=None` there is no SNN forward, so the cost is microseconds
  against the ~0.74 s of the net's reconstruct.

## Scope — what is in, what is out, and why

**IN — road + Trajectory + Safety, one toggle.**

Admission criterion, set by the user: *a view is rejected when it adds visual confusion*, not when it
looks redundant. Measured on 4 champions × 9 scenarios × 6 series (216 measurements): **peak**
separation between the net's curve and the oracle's, converted to pixels on the real axis.

| series | dock | median px | p95 px | **peak px** | % ticks ≥2px | verdict |
|---|---|---:|---:|---:|---:|---|
| gap | Trajectory | 4.38 | 15.07 | **16.35** | 72.4% | in |
| v_ego | Trajectory | 1.21 | 4.22 | **5.36** | 20.3% | in |
| accel | Trajectory | 1.24 | 3.87 | **21.61** | 20.6% | in |
| TTC | Safety | 0.00 | 2.81 | **75.87** | 5.2% | in |
| headway | Safety | 5.41 | 18.38 | **70.75** | 77.3% | in |
| DRAC | Safety | 0.00 | 5.82 | **15.62** | 11.5% | in |

> ⚠️ **Methodological note, kept deliberately.** The first pass of this analysis looked at the
> **median** separation and concluded TTC/DRAC were invisible (0.00 px) and the Safety dock should be
> dropped. That was **wrong**: TTC sits saturated at the 30 s clip for most of the episode, so the
> median is dominated by dead stretches and hides the phenomenon. The peak is **75.87 px** (88.3 px on
> `hard_brake`, 87.0 on `panic_stop`) on a 100 px box — TTC separates in only 5.2% of ticks, but those
> ticks *are the transition*, i.e. the only moment TTC means anything. **Central statistics on a
> tail phenomenon, in a safety domain where only the tail matters.** Whoever revisits this: use the
> peak, not the median.

**OUT — Post-run.** Rejected on **structure**, not legibility, and the structural part was verified:
the oracle **has no net**. *Identification* is degenerate — max `|params − params_gt|` = **0.000e+00
exactly** over 36 episodes, because the oracle *uses* the true parameters (the card would read 100%
forever). *Network health* (ρ, dead%) and *Efficiency* (SynOps) measure a net that does not exist.
*Trend* would duplicate Trajectory. Only *Safety* and *Comfort* apply — and there the comparison does
have real value (measured: `rms_jerk` differs by 22.7% median / **83% max**; on `static_target` the net
scores 1.06 against the oracle's 0.18, i.e. **six times jerkier**; `min_ttc` 14.3% median). It is
worth doing — in its own cycle. Cost is the reason to defer: a second `EpisodeSummary`, a changed
`set_summary` signature, and surgery on the v3 dashboard, which is the freshest code in the repo
(5 QC rounds, `227f46d`).

**OUT — Meso/Macro.** A platoon of oracles is a legitimate string-stability baseline and the road
exists (`utils/platoon_eval.py:41-44` has the `model=None` branch), but `sim/ui/platoon.py:40-43`
always passes `forward=fw`, which takes precedence over `model` (`platoon_eval.py:79-80`), so it must
be bypassed. Different page, different cycle.

**OUT — the "shadow" reading.** Answering *"in this exact state, what would the true driver have
commanded?"* (teacher-forced `acc_iidm_accel` on the net's current state) is a different question from
the ghost's. It is cheap to add later — one pure call on the current state, no second stepper, no
architectural debt — so YAGNI applies. Recorded here so the option is not lost.

## Design

### ① Ghost stepper in the loop (`sim/ui/loop.py`)

`SimLoop.__init__(stepper, probe=None, dt_fixed=DT, ghost=None, ghost_traj=None)` — additive; with the
defaults the behaviour is byte-for-byte today's. When present, each fixed-timestep iteration advances
the ghost **in the same step** as the net's stepper and records into `ghost_traj`. The loop is the only
place that can guarantee they stay in lockstep, because it owns the accumulator (`sim/ui/loop.py:22-32`).

Termination stays governed by the **net's** stepper (`SimLoop.done`, `sim/ui/loop.py:18-20`): the
episode is the net's episode. The ghost stops on its own `collided`/`t >= N` and holds its last state.

### ② Ghost stepper construction (`sim/ui/app.py`)

In `select_scenario` (`sim/ui/app.py:402-432`), next to the existing stepper:

```
self._ghost = SimStepper.from_scenario(None, sc, injector=self._injector)   # same injector
self._ghost_traj = TrajectoryBuffer()                                       # default cap, as app.py:411
self._src_ghost_traj = self._ghost_traj                                     # scrub source, as app.py:413
self.loop = SimLoop(stepper, self._probe, dt_fixed=DT, ghost=self._ghost, ghost_traj=self._ghost_traj)
```

The shared `self._injector` is what makes net and ghost see the same leader; idempotence is measured
(§Established facts) and pinned by a test (§Testing).

**Scrub source must be mirrored.** The app does not read `self._traj` directly when scrubbing: it reads
`self._src_traj`, which is swapped to the *reconstructed* full-episode buffer once the 500-tick ring has
wrapped, and back to live on resume (`sim/ui/app.py:89,413,461,524,537-539`). The ghost needs the same
`_src_ghost_traj` indirection and must be swapped **in the same places, at the same time**. If it is
not, scrubbing past the ring buffer leaves the ghost pinned to the live tail while every other curve
shows the past — a silent, plausible-looking lie. `_reconstruct` (`app.py:594`) therefore returns a
third buffer and its cache key/tuple grow accordingly.

### ③ Road (`sim/ui/topdown.py`)

A third `_vehicle("#9a9a9a")` drawn semi-transparent (`setOpacity`), plus `_ghost_x` integrated exactly
like `_ego_x` (`+= r.v * DT`) and reset in `reset()` alongside it — the QC already fixed a real bug
where a non-reset integrated position made the car drive off across episodes (`topdown.py:100-105`).
`advance()`/`update_frame()`/`render_at()` grow a ghost counterpart; `render_at` reconstructs
`ghost_x = Σ v_ghost·DT` up to the index, mirroring `topdown.py:149`.

No follow/clamp logic: measured, the ghost never leaves the viewport.

### ④ Trajectory + Safety panels (`sim/ui/panels.py`)

`TrajectoryPanel.set_ghost(traj|None)` adds 3 curves — gap on `_pg`, ego speed on `_pv`, accel on
`_pa`. **The leader is NOT duplicated**: it is the same vehicle in both worlds, so `_c_vl` stays single.
`SafetyPanel.set_ghost(traj|None)` adds TTC + headway on `_pt` and DRAC on `_pd`, computed with the
same `metrics.ttc/time_headway/drac` and the same 30 s clip as the net's curves (`panels.py:590-592`).

Pen: `#9a9a9a`, `Qt.DotLine`, width 1.6 — the grey the SynOps dock already uses for its reference curve
(`panels.py:87`), verified legible on the dark theme in the design renders. `clear()` must blank the
ghost curves too: the QC had to fix panels that did not blank on Reset/swap, and this is the same trap.

### ⑤ Toggle (`sim/ui/app.py`)

A checkbox in the toolbar — not a dock, because it drives three places at once (road + 2 docks).
Label: **"Oracolo (Master Splinter)"**. Tooltip, stating what is being shown rather than selling it:

> Guidatore di riferimento (ACC-IIDM) con i parametri veri. Parte dallo stesso stato e **diverge per
> costruzione**: è un rollout indipendente, non l'errore istantaneo della rete. Sovrapposto = la rete
> guida come il guidatore vero.

Off → the ghost is not drawn and its redraw is skipped, following the visibility-gating pattern the QC
introduced for hidden docks. Not persisted to `layout.json` (YAGNI: it is view state, not layout).

### ⑥ Deep-scrub (`sim/ui/reconstruct.py`)

`reconstruct_history`/`reconstruct_spliced` return a **third** buffer, the ghost's, rebuilt with
`SimStepper(None, …)` and `replaylog.build_injector()`. Costs microseconds (no SNN forward), so the
ghost is simply **fully re-run** every time rather than spliced — the prefix-splice complexity
(`reconstruct.py:33-49`) exists only because the net's forward is slow, and there is no reason to
inherit it here. Note this makes the ghost's reconstruction *simpler* than the net's, not a copy of it.

The reconstructed ghost then flows into `_src_ghost_traj` in lockstep with `_src_probe`/`_src_traj`
(see ②). Same swap sites, same moment.

## Errors and edge cases

| case | behaviour |
|---|---|
| ghost collides, net does not | ghost stops, holds last state; episode continues (net governs `done`) |
| net collides, ghost does not | episode ends as today; ghost frozen at its last tick |
| toggle off | no ghost draw, redraw gated; identical to today's behaviour |
| Reset / champion swap / scenario change | ghost rebuilt in `select_scenario`; `clear()` blanks its curves; `topdown.reset()` zeroes `_ghost_x` |
| scrub before the ghost exists | `set_ghost(None)` → curves blank, no crash |
| scrub past the 500-tick ring | `_src_ghost_traj` swaps to the reconstructed ghost **together with** `_src_probe`/`_src_traj`; never one without the others |

## Testing

New `tests/test_sim_*.py` cases (env `cf_sim`, run the 20 sim test files explicitly):

1. **Ghost fidelity** — the ghost buffer filled through `SimLoop` is bit-identical to
   `closed_loop_eval.simulate(None, params_gt, …)` (`assert_array_equal`).
2. **Shared-leader invariant (teeth)** — net and ghost see the same `vl` at every tick, *including*
   with a `brake_leader` injected mid-episode. Fails if the injector is ever duplicated per stepper.
3. **Toggle off is a no-op** — with `ghost=None`, `SimLoop` output is unchanged vs today (regression).
4. **Scrub coherence** — the reconstructed ghost equals the live ghost on the buffer overlap.
5. **Scrub source stays in sync (teeth)** — after a deep scrub past the ring buffer, the tick shown by
   the ghost equals the tick shown by the net's curves. Fails if `_src_ghost_traj` is not swapped with
   `_src_probe`/`_src_traj`, which would render a ghost from the live tail against a past net state.
6. **Road placement** — `_ghost_x` after N ticks equals `Σ v_ghost·DT`; `reset()` zeroes it.
7. **Panels blank** — `clear()` empties the ghost curves (Reset/swap trap).
8. **Core bit-identity** — full sim suite green; frozen core untouched.

Baseline: **148 sim tests green** (2026-07-15). No LAPACK anywhere (OMP #15). Visual verification with
`QT_QPA_PLATFORM=windows` and actually looking at the PNG.

## Known debt found during this design (out of scope, do NOT fix here)

- **`EventInjector` ramp bug — MEASURED, real.** `sim/events.py:37-38` captures the ramp start from the
  **raw** `v_leader[t]` (`sim/stepper.py:61`), not the current effective leader speed. Two braking
  events in sequence make the leader **jump from 5.00 to 21.00 m/s in one tick** (+16 m/s ≈ 160 m/s²).
  Invisible today because the button is pressed once; `tests/test_sim_events.py:25-29` only covers
  events at the *same* tick, not in sequence. It does **not** affect the ghost (both worlds see the same
  jumping leader, so the comparison stays honest). It belongs to the **custom scenario builder** cycle,
  which is what would trigger it for real.
- `ReplayLog.seed` is fed the **scenario index** (`sim/ui/app.py:591`) — harmless today, semantically
  wrong, and a landmine once scenarios carry a real seed. Same cycle as above.

## Evidence

Design spikes (throwaway, scratchpad, not in the repo): injector idempotence (7/7 patterns × 600
ticks); curve separation sweep (216 measurements, median/p95/peak/%ticks≥2px); post-run metric deltas
(4 champions × 9 scenarios); road placement (absolute vs via-leader, 36 combinations). Rendered mocks
used real panels, a real episode and the real oracle at `QT_QPA_PLATFORM=windows`.
