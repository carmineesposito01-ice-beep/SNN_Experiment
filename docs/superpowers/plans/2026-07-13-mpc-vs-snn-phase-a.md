# MPC vs SNN — Phase A (Behavioural Comparison) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended)
> or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
>
> **Spec:** `docs/superpowers/specs/2026-07-13-mpc-vs-snn-comparison-design.md`. This plan covers **Phase A
> only** (the behavioural plane). Phases B (MPC-on-FPGA) and C (Pareto + report) get their own plans.

**Goal:** A single MATLAB pipeline that runs the closed-loop car-following comparison over a shared plant
and the scenario bank, computes metrics (parity-checked against the validated Python suite), and produces
comparison tables + figures — for the SNN configs immediately, with the MPC configs slotting in once the
user's MPC model is available.

**Architecture:** Split the current bundled `ACC_IIDM` block into a **neutral longitudinal plant**
(ballistic integrator, shared by all controllers) and the **IIDM control law** (part of *our* controller,
fed by SNN-identified params). A programmatically-built Simulink harness swaps the controller subsystem
(SNN-float / SNN-B2 / MPC−preview / MPC+V2X). One driver script runs the matrix into a timestamped folder
and computes everything from that same run's data — no stale-data risk.

**Tech Stack:** MATLAB R2026a (`matlab -batch`), Simulink (programmatic model build, per
`run_plant_parity.m`), `matlab.unittest`, `snn_core.m` (float SNN) + the B2 block (as-deployed SNN),
Python reference from `utils/closed_loop_eval.py` + the simulator (for one-time metric parity goldens).

**Environment note:** all `Run:` commands are **MATLAB**, invoked headless as
`matlab -batch "cd matlab; <cmd>"` from the worktree root. New MATLAB source lives under `matlab/cf/`.

**MPC dependency:** Tasks 0/8 need the user's online-MPC Simulink model. Tasks 1–7 are MPC-independent and
can complete first; the MPC configs are wired in Task 8 and run when the model is supplied.

---

## File Structure

**Create:**
- `matlab/cf/longitudinal_plant.m` — neutral shared plant (ballistic integrator + actuator limits + crash).
- `matlab/cf/acc_iidm_law.m` — the IIDM control law (a_l estimate + acc_iidm_accel), state → a_cmd.
- `matlab/cf/build_compare_harness.m` — programmatically builds `cf_compare_harness.slx` (swappable controller).
- `matlab/cf/scenarios.m` — leader-profile bank (single-follower + platoon + ring) as data structs.
- `matlab/cf/metrics/cf_safety.m`, `cf_comfort.m`, `cf_string_stability.m`, `cf_fundamental.m` — metrics.
- `matlab/cf/run_mpc_vs_snn.m` — the all-in-one driver (run → metrics → tables → figures, timestamped).
- `matlab/cf/make_metrics_golden.py` — Python: emit `metrics_golden.mat` from the validated suite.
- `matlab/cf/tests/` — `matlab.unittest` tests: `tPlant.m`, `tLaw.m`, `tMetricsParity.m`, `tScenarios.m`,
  `tHarnessSmoke.m`, `tDriverSmoke.m`; plus `run_cf_tests.m` (runner listing them explicitly).
- `matlab/cf/README.md` — how to run the comparison + the parity discipline.

**Modify:** none of the frozen HDL/plant sources. `matlab/cf/` is a new, self-contained subtree.

**Reuse (read-only):** `matlab/snn_core.m` (float SNN), `snn_champions_lib.slx` / `snn_b2_fsm.m` (B2),
`cf_plant_lib.slx` (`plant_code()` is the source to split), `run_plant_parity.m` (the programmatic-build +
golden pattern to mirror).

---

## Task 0: Record the MPC formulation (MPC-dependent; do when the model arrives)

**Files:** Create `matlab/cf/MPC_UNDER_TEST.md`.

- [ ] **Step 1: Capture the artefact.** Write `MPC_UNDER_TEST.md` recording, from the user's model: the
  block/model path, I/O ports (must map to `s,v,Δv,v_l → a_cmd`), sample time, horizon `N_p`/`N_c`, cost
  weights, constraints (a-limits, comfort), the internal prediction model, the solver, and how the leader
  is predicted in the **−preview** regime (const-velocity/accel) vs the **+V2X** regime (future preview).
- [ ] **Step 2: Commit.** `git add matlab/cf/MPC_UNDER_TEST.md && git commit -m "docs(cf): record MPC-under-test formulation"`

> Task 0 does not block Tasks 1–7. Leave it open until the MPC model is available; Task 8 consumes it.

---

## Task 1: Extract the shared plant + the IIDM control law

**Files:** Create `matlab/cf/longitudinal_plant.m`, `matlab/cf/acc_iidm_law.m`, `matlab/cf/tests/tPlant.m`,
`matlab/cf/tests/tLaw.m`. Source to split: `matlab/build_plant_lib.m::plant_code()`.

- [ ] **Step 1: Write the failing plant test.** `matlab/cf/tests/tPlant.m`:

```matlab
classdef tPlant < matlab.unittest.TestCase
  methods (Test)
    function ballistic_and_limits(tc)
      st = struct('s',30,'v',20);            % state
      % constant +1 m/s^2 command, leader at 20 m/s, dt=0.1
      [st2,acc] = longitudinal_plant(st, 1.0, 20.0, struct('dt',0.1,'a_max',3,'a_min',-9,'v_max',60));
      tc.verifyEqual(acc, 1.0, 'AbsTol', 1e-12);           % command passed through (within limits)
      tc.verifyEqual(st2.v, 20 + 1.0*0.1, 'AbsTol', 1e-12);% v ballistic
      tc.verifyEqual(st2.s, 30 + (20-20)*0.1, 'AbsTol',1e-12);% s uses v_leader - v_old
    end
    function actuator_clip_and_crash(tc)
      cfg = struct('dt',0.1,'a_max',3,'a_min',-9,'v_max',60);
      [~,acc] = longitudinal_plant(struct('s',10,'v',5), 99, 5, cfg);
      tc.verifyEqual(acc, 3, 'AbsTol',1e-12);               % clipped to a_max
      [st2,~] = longitudinal_plant(struct('s',0.05,'v',10), -9, 0, cfg);
      tc.verifyTrue(st2.collided);                          % s crossed 0 -> collision flag
    end
  end
end
```

- [ ] **Step 2: Run it — expect FAIL** (`longitudinal_plant` undefined).
  Run: `matlab -batch "cd matlab/cf; run(matlab.unittest.TestSuite.fromFile('tests/tPlant.m'))"`
  Expected: error / failure "Unrecognized function 'longitudinal_plant'".

- [ ] **Step 3: Implement the neutral plant.** `matlab/cf/longitudinal_plant.m` — ballistic integrator with
  the **controller-neutral** clamps (no IIDM-specific `1.2*v0` / `0.5*s0`; those belonged to the law):

```matlab
function [st, a_cmd] = longitudinal_plant(st, a_cmd, v_l, cfg)
%LONGITUDINAL_PLANT  Shared point-mass longitudinal plant (ballistic). One controller-neutral step.
%  st: struct(s, v[, collided]).  a_cmd: commanded accel.  v_l: leader speed.  cfg: dt,a_max,a_min,v_max.
%  Returns the updated state and the *actually applied* accel (after actuator limits / crash).
  if ~isfield(st,'collided'), st.collided = false; end
  a_cmd = min(max(a_cmd, cfg.a_min), cfg.a_max);          % actuator limits
  v_old = st.v;
  v_new = min(max(st.v + a_cmd*cfg.dt, 0), cfg.v_max);    % v >= 0, top speed cap
  s_new = st.s + (v_l - v_old)*cfg.dt;                    % ballistic gap update (old ego speed)
  if s_new <= 0                                           % crash provision
    st.collided = true; s_new = 0; v_new = 0; a_cmd = cfg.a_min;
  end
  st.s = s_new; st.v = v_new;
end
```

- [ ] **Step 4: Run tPlant — expect PASS.**
  Run: `matlab -batch "cd matlab/cf; assert(run(matlab.unittest.TestSuite.fromFile('tests/tPlant.m')).Passed)"`
  Expected: no error (all pass).

- [ ] **Step 5: Write the failing law test.** `matlab/cf/tests/tLaw.m` — the IIDM law reproduces the accel
  of the current bundled `plant_code()` on the same inputs (extract-without-behaviour-change check):

```matlab
classdef tLaw < matlab.unittest.TestCase
  methods (Test)
    function matches_bundled_accel(tc)
      law = acc_iidm_law();                        % fresh stateful law (resets persistent via clear)
      p = struct('v0',30,'T',1.2,'s0',2.5,'a',1.1,'b',1.5);
      st = struct('s',40,'v',24);
      a1 = law.step(st, 22.0, p);                  % leader 22 m/s
      tc.verifyGreaterThan(a1, -9); tc.verifyLessThanOrEqual(a1, p.a);  % within [-9, a]
      % golden value regenerated once from plant_code() logic and pinned here:
      tc.verifyEqual(a1, LAW_GOLDEN_A1, 'AbsTol', 1e-9);
    end
  end
end
```

- [ ] **Step 6: Generate the law golden.** Run the accel section of `plant_code()` once on the Step-5 inputs
  to obtain `LAW_GOLDEN_A1` (a scalar), and paste it into `tLaw.m`. Command:
  `matlab -batch "cd matlab/cf; a = local_bundled_accel(40,24,22,struct('v0',30,'T',1.2,'s0',2.5,'a',1.1,'b',1.5)); fprintf('%.12f\n',a)"`
  (temporary helper `local_bundled_accel` = lines 55–77 of `plant_code()` verbatim). Expected: a printed scalar; delete the helper after pinning.

- [ ] **Step 7: Implement the law.** `matlab/cf/acc_iidm_law.m` — a small stateful object (handle) wrapping
  the a_l OU estimate + `acc_iidm_accel` (lines 55–77 of `plant_code()`), **without** the integration/clamps:

```matlab
function obj = acc_iidm_law()
%ACC_IIDM_LAW  Stateful IIDM control law (our controller's law; SNN supplies the 5 params).
%  law.step(st, v_l, p) -> a_cmd, where st=struct(s,v), p=struct(v0,T,s0,a,b).
  s = struct('alf',0,'vlp',[],'DT',0.1,'ALPHA',exp(-0.1/1.0),'COOL',0.99);
  obj.step = @step; obj.reset = @reset;
  function reset(), s.alf = 0; s.vlp = []; end
  function a_cmd = step(st, v_l, p)   % return is a_cmd (never shadows the IIDM 'a' parameter)
    if isempty(s.vlp), s.vlp = v_l; end
    s.alf = s.ALPHA*s.alf + (1-s.ALPHA)*((v_l - s.vlp)/s.DT); s.vlp = v_l;   % a_l OU estimate
    v0=max(p.v0,1e-3); T=max(p.T,1e-3); a=max(p.a,1e-3); b=max(p.b,1e-3); s0=p.s0;
    dv = st.v - v_l; sab = max(sqrt(a*b),1e-6);
    s_star = s0 + max(st.v*T + st.v*dv/(2*sab), 0); s_safe = max(st.s, 2.0);
    v_free = a*(1 - min(st.v/v0,10)^4); z = min(s_star/s_safe, 20); below = (st.v <= v0); a_z = a*(1 - z^2);
    if z < 1, if below, a_iidm = v_free*(1 - z^2); else, a_iidm = v_free; end
    else,     if below, a_iidm = a_z;             else, a_iidm = v_free + a_z; end, end
    a_l_bar = min(s.alf, a); a_cah = min(max(a_l_bar - max(dv,0)^2/(2*s_safe+1e-6), -9), a);
    dd = (a_iidm - a_cah)/(b+1e-6); a_blend = (1-s.COOL)*a_iidm + s.COOL*(a_cah + b*tanh(dd));
    if a_iidm >= a_cah, a_cmd = a_iidm; else, a_cmd = a_blend; end
    a_cmd = min(max(a_cmd, -9), a);    % clamp to [-9, a] (a = max(p.a,1e-3))
  end
end
```

- [ ] **Step 8: Run tLaw — expect PASS.**
  Run: `matlab -batch "cd matlab/cf; assert(run(matlab.unittest.TestSuite.fromFile('tests/tLaw.m')).Passed)"`

- [ ] **Step 9: Commit.**
  `git add matlab/cf/longitudinal_plant.m matlab/cf/acc_iidm_law.m matlab/cf/tests/tPlant.m matlab/cf/tests/tLaw.m`
  `git commit -m "feat(cf): split neutral plant + IIDM control law from ACC_IIDM"`

---

## Task 2: SNN controller subsystems (float + B2) as pure-MATLAB closed loops

**Files:** Create `matlab/cf/snn_controller.m`, `matlab/cf/tests/tSnnLoop.m`. Reuse `snn_core.m`, the B2 block.

- [ ] **Step 1: Write the failing SNN-loop test.** `tSnnLoop.m` — a Donatello closed loop over a benign
  "following" leader must (a) run N steps, (b) keep gap bounded and positive, (c) reproduce the existing
  `closed_loop_demo` trajectory within a tolerance (behavioural equivalence of the split path):

```matlab
classdef tSnnLoop < matlab.unittest.TestCase
  methods (Test)
    function donatello_float_follows(tc)
      vl = 20*ones(1,200);                                  % steady leader
      cfg = struct('dt',0.1,'a_max',3,'a_min',-9,'v_max',60,'ic',struct('s',40,'v',16));
      traj = snn_controller('Donatello','float').run(vl, cfg);
      tc.verifyEqual(numel(traj.s), 200);
      tc.verifyGreaterThan(min(traj.s), 0);                 % never crashes on steady leader
      tc.verifyLessThan(max(abs(diff(traj.v))), 3*0.1 + 1e-6); % accel within actuator limit
    end
  end
end
```

- [ ] **Step 2: Run — expect FAIL** (`snn_controller` undefined).
  Run: `matlab -batch "cd matlab/cf; run(matlab.unittest.TestSuite.fromFile('tests/tSnnLoop.m'))"`

- [ ] **Step 3: Implement `snn_controller`.** Factory `snn_controller(champion, repr)` → `.run(v_l, cfg)`.
  **Reuse the existing SNN path — do NOT reimplement normalisation**: weights + norm come from
  `champions_export.mat` + `snn_normalize.m`, and the per-tick forward is the same one `run_block_parity.m`
  drives (`snn_entry`/`snn_core` for `float`; the B2 block / `snn_b2_fsm` for `b2`). `cfg.ic` = initial
  `struct(s,v)` from the scenario. Skeleton (verify `snn_entry`/`snn_b2_fsm` arg shapes against the live files
  while wiring — the loop structure is the contract):

```matlab
function obj = snn_controller(champion, repr)
  d = load('champions_export.mat'); c = d.champions(strcmp({d.champions.name}, champion));
  law = acc_iidm_law(); obj.run = @run;
  function traj = run(v_l, cfg)
    clear snn_core                                  % reset persistent SNN state (per run_block_parity)
    law.reset(); st = cfg.ic;                       % IC from the scenario
    N = numel(v_l); [traj.s,traj.v,traj.a] = deal(zeros(1,N));
    for k = 1:N
      dv = st.v - v_l(k);
      xn = snn_normalize([st.s; st.v; dv; v_l(k)]); % existing physical->normalised map
      if strcmp(repr,'float'), p5 = snn_entry(xn, c); else, p5 = snn_b2_fsm(xn, c); end  % 5 params
      p = struct('v0',p5(1),'T',p5(2),'s0',p5(3),'a',p5(4),'b',p5(5));
      a_cmd = law.step(st, v_l(k), p);
      [st, a_cmd] = longitudinal_plant(st, a_cmd, v_l(k), cfg);
      traj.s(k)=st.s; traj.v(k)=st.v; traj.a(k)=a_cmd;
    end
  end
end
```

- [ ] **Step 4: Run tSnnLoop float — expect PASS.**
  Run: `matlab -batch "cd matlab/cf; assert(run(matlab.unittest.TestSuite.fromFile('tests/tSnnLoop.m')).Passed)"`

- [ ] **Step 5: Add the B2 case.** Extend `tSnnLoop.m` with a `donatello_b2_follows` test (same asserts,
  `snn_controller('Donatello','b2')`), and wire the B2 branch in `snn_controller` (call the B2 block / `snn_b2_fsm`).
  Run the test — expect PASS. Assert float and B2 trajectories are close but not required bit-identical
  (`verifyEqual(traj_b2.s, traj_float.s,'AbsTol',0.5)` — quantisation ≤ decimetre-scale on a benign run).

- [ ] **Step 6: Commit.**
  `git add matlab/cf/snn_controller.m matlab/cf/tests/tSnnLoop.m`
  `git commit -m "feat(cf): SNN closed-loop controller (Donatello float + B2) on the shared plant"`

---

## Task 3: MATLAB metric library + one-time parity vs Python

**Files:** Create `matlab/cf/metrics/cf_safety.m`, `cf_comfort.m`, `cf_string_stability.m`, `cf_fundamental.m`,
`matlab/cf/make_metrics_golden.py`, `matlab/cf/tests/tMetricsParity.m`.

- [ ] **Step 1: Emit the Python golden.** `make_metrics_golden.py` (mirrors `make_plant_golden.py`): build a
  handful of synthetic trajectories + one platoon + one density point, run them through the **validated**
  `utils/closed_loop_eval.safety_metrics`/`comfort_metrics` and the simulator's string-stability/fundamental
  code, and `scipy.io.savemat('metrics_golden.mat', ...)` with inputs + expected metric values.
  Run: `python matlab/cf/make_metrics_golden.py` (in the `cf_sim` env). Expected: writes `metrics_golden.mat`.

- [ ] **Step 2: Write the failing parity test.** `tMetricsParity.m` loads `metrics_golden.mat` and asserts each
  MATLAB metric matches the Python value within tol (`RelTol` 1e-3 for reductions, `AbsTol` 1e-6 for scalars):

```matlab
classdef tMetricsParity < matlab.unittest.TestCase
  properties, G, end
  methods (TestClassSetup)
    function load_golden(tc), tc.G = load('metrics_golden.mat'); end
  end
  methods (Test)
    function safety_matches(tc)
      for k = 1:numel(tc.G.cases)
        c = tc.G.cases(k); m = cf_safety(c.s, c.v, c.dv, c.dt);
        tc.verifyEqual(m.min_ttc, c.min_ttc, 'RelTol', 1e-3);
        tc.verifyEqual(m.min_gap, c.min_gap, 'AbsTol', 1e-6);
        tc.verifyEqual(m.max_drac, c.max_drac,'RelTol', 1e-3);
      end
    end
    function comfort_matches(tc)
      for k = 1:numel(tc.G.cases)
        c = tc.G.cases(k); m = cf_comfort(c.a_ego, c.dt);
        tc.verifyEqual(m.rms_accel, c.rms_accel, 'RelTol', 1e-3);
        tc.verifyEqual(m.rms_jerk,  c.rms_jerk,  'RelTol', 1e-3);
      end
    end
    function string_stability_matches(tc)
      m = cf_string_stability(tc.G.platoon.v);              % (T x N) platoon speeds
      tc.verifyEqual(m.head_to_tail_gain, tc.G.platoon.head_to_tail_gain, 'RelTol', 1e-3);
    end
  end
end
```

- [ ] **Step 3: Run — expect FAIL** (metric functions undefined). Run the parity suite (command as Task 1 Step 2, file `tests/tMetricsParity.m`).

- [ ] **Step 4: Implement `cf_safety.m`.** Pure, vectorised: `min_gap=min(s)`, `ttc=s./max(dv,eps)` (∞ when
  `dv<=0`), `drac=dv.^2./(2*s)` (0 when `dv<=0`), `time_headway=s./max(v,eps)`, TET/TIT vs `TTC*` threshold,
  `brake_margin = s - max(dv,0).^2/(2*B_MAX)` (`B_MAX=9`), `collisions=any(s<=0)`. Return a struct.

- [ ] **Step 5: Implement `cf_comfort.m`.** `rms_accel=rms(a)`, `jerk=diff(a)/dt`, `rms_jerk=rms(jerk)`, ISO-2631
  band fractions. **No LAPACK.** Return a struct.

- [ ] **Step 6: Implement `cf_string_stability.m`.** For an `(T x N)` platoon speed matrix: per-vehicle
  amplitude `A_i` (std or peak-to-peak of `v_i`), gain `|H|_i = A_i/A_0`, `head_to_tail_gain=A_{N-1}/A_0`,
  `max_amplification=max(|H|_i)`, `string_stable = max<=1`, convective flag. Slope-by-hand where needed (no `polyfit`).

- [ ] **Step 7: Implement `cf_fundamental.m`.** Edie's `Q(ρ)`, `V(ρ)` from a ring run + a `wave_std` instability flag.

- [ ] **Step 8: Run tMetricsParity — expect PASS.** Iterate implementations until every metric is within tol.
  Run: `matlab -batch "cd matlab/cf; assert(run(matlab.unittest.TestSuite.fromFile('tests/tMetricsParity.m')).Passed)"`

- [ ] **Step 9: Commit.**
  `git add matlab/cf/metrics matlab/cf/make_metrics_golden.py matlab/cf/tests/tMetricsParity.m metrics_golden.mat`
  `git commit -m "feat(cf): MATLAB metric library, parity-checked against the validated Python suite"`

---

## Task 4: Scenario bank (single-follower + platoon + ring)

**Files:** Create `matlab/cf/scenarios.m`, `matlab/cf/tests/tScenarios.m`.

- [ ] **Step 1: Write the failing test.** `tScenarios.m`: `scenarios('following')` returns a struct with a
  `v_leader` vector of the expected length; `scenarios('all')` lists the 5 single-follower names; the platoon
  builder returns an `(T x N)` leader matrix with an OU perturbation at the head (seeded, reproducible).
- [ ] **Step 2: Run — expect FAIL.** (command per Task 1 Step 2, file `tests/tScenarios.m`).
- [ ] **Step 3: Implement `scenarios.m`.** Port the simulator's leader profiles (following, stop&go, hard-brake,
  cut-in, sinusoidal) as `v_leader` generators; add `platoon(N, base_profile, ou_params, seed)` using the
  **Ornstein-Uhlenbeck** update `η_k = exp(-dt/τ)·η_{k-1} + √(2dt/τ)·ξ_k` (seeded RNG) and `ring(density_grid)`.
- [ ] **Step 4: (Parity, optional-strong) Golden the profiles.** Extend `make_metrics_golden.py` to dump the
  Python simulator's `v_leader` for the 5 scenarios; add a `tScenarios` case asserting the MATLAB profiles match
  within `AbsTol 1e-9`. Run — expect PASS.
- [ ] **Step 5: Commit.** `git add matlab/cf/scenarios.m matlab/cf/tests/tScenarios.m; git commit -m "feat(cf): scenario bank (single/platoon/ring) with OU perturbation"`

---

## Task 5: The comparison harness `.slx` (swappable controller)

**Files:** Create `matlab/cf/build_compare_harness.m`, `matlab/cf/tests/tHarnessSmoke.m`.

> This mirrors the **programmatic build** pattern of `run_plant_parity.m` (new_system/add_block/add_line/sim).
> The controller is a **Variant Subsystem** with 4 variants; Tasks 1–2 give the SNN variants, Task 8 the MPC.

- [ ] **Step 1: Write the failing smoke test.** `tHarnessSmoke.m`: `build_compare_harness()` creates
  `cf_compare_harness.slx`; simulating it with the **SNN-float** variant over a 200-step "following" leader
  yields logged `s,v,a_cmd` of length 200 with `min(s)>0`.
- [ ] **Step 2: Run — expect FAIL.** (file `tests/tHarnessSmoke.m`).
- [ ] **Step 3: Implement `build_compare_harness.m`.** Programmatic build: `From Workspace` (leader) →
  Variant Subsystem `CTRL` (variants: `snn_float`, `snn_b2`, `mpc_nopreview`, `mpc_v2x`) → shared plant
  (a MATLAB Function wrapping `longitudinal_plant` with persistent state) → `To Workspace` (`s,v,a_cmd`) +
  a feedback bus `(s,v,Δv,v_l)` to `CTRL`. SNN variants wrap `snn_controller`; MPC variants are placeholder
  pass-throughs until Task 8. Fixed-step, `FixedStep=1`, `StopTime=N-1` (as in `run_plant_parity`).
- [ ] **Step 4: Run tHarnessSmoke — expect PASS.** (command per Task 1 Step 4, file `tests/tHarnessSmoke.m`).
- [ ] **Step 5: Commit.** `git add matlab/cf/build_compare_harness.m matlab/cf/tests/tHarnessSmoke.m cf_compare_harness.slx; git commit -m "feat(cf): programmatic comparison harness with swappable controller variant"`

---

## Task 6: The all-in-one driver (run → metrics → tables → figures, timestamped)

**Files:** Create `matlab/cf/run_mpc_vs_snn.m`, `matlab/cf/tests/tDriverSmoke.m`.

- [ ] **Step 1: Write the failing smoke test.** `tDriverSmoke.m`: `run_mpc_vs_snn(struct('configs',{{'snn_float','snn_b2'}},'scenarios',{{'following'}},'K',1,'outdir',tempname))`
  returns a results struct and writes a fresh timestamped folder containing `results.mat` + at least one `.png`.
- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement `run_mpc_vs_snn.m`.** For each `(config, scenario, k)`: set the harness variant, run
  the sim, collect `s,v,a,v_l`; compute `cf_safety/cf_comfort` (+ `cf_string_stability` for platoon, `cf_fundamental`
  for ring); accumulate into a results struct **keyed by the run's timestamped folder** (`outdir/run_YYYYmmdd_HHMMSS/`,
  passed in via `args` — the runtime forbids clock calls in workflow scripts, but a normal MATLAB script may use
  `datestr(now)`); write `results.mat`; call the figure functions (Task 7) into that same folder. **Never** read a
  previous run's folder → no stale data.
- [ ] **Step 4: Run tDriverSmoke — expect PASS.**
- [ ] **Step 5: Commit.** `git add matlab/cf/run_mpc_vs_snn.m matlab/cf/tests/tDriverSmoke.m; git commit -m "feat(cf): all-in-one driver — run+metrics+figures into a timestamped folder"`

---

## Task 7: Figures + behavioural comparison tables

**Files:** Create `matlab/cf/figs/fig_trajectories.m`, `fig_safety_comfort_table.m`, `fig_string_stability.m`,
`fig_fundamental.m`, `fig_behavioural_pareto.m`. (Called by the driver.)

- [ ] **Step 1: Implement the figure functions.** Each takes the results struct + the run folder, writes a `.png`:
  per-scenario **trajectory overlays** (gap/v/a, one line per config), a **safety/comfort table** figure,
  the **string-stability** `|H|_i` plot, the **fundamental diagram** `Q(ρ)/V(ρ)`, and a **behavioural-Pareto**
  scaffold (behaviour score vs a cost placeholder; MPC/FPGA cost points fill in later phases). Dark theme to
  match the project. No unit tests (visual); the driver smoke test already exercises the call path.
- [ ] **Step 2: Render-verify.** Run the driver on `{snn_float, snn_b2} × {following, hard-brake, platoon, ring}`;
  open the PNGs and confirm the overlays/tables/plots read correctly (gap closes on hard-brake, platoon
  amplification visible, fundamental diagram sane).
  Run: `matlab -batch "cd matlab/cf; run_mpc_vs_snn(struct('configs',{{'snn_float','snn_b2'}},'scenarios',{{'following','hard_brake','platoon','ring'}},'K',3,'outdir','runs'))"`
- [ ] **Step 3: Commit.** `git add matlab/cf/figs; git commit -m "feat(cf): comparison figures (trajectories, safety/comfort, string stability, fundamental, Pareto scaffold)"`

---

## Task 8: Wire the MPC configs (MPC-dependent)

**Files:** Modify `matlab/cf/build_compare_harness.m`; create `matlab/cf/tests/tMpcLoop.m`. Needs Task 0 + the model.

- [ ] **Step 1: Write the failing MPC-loop test.** `tMpcLoop.m`: the `mpc_nopreview` variant runs a 200-step
  "following" leader with `min(s)>0` and `a_cmd` within the actuator limits.
- [ ] **Step 2: Run — expect FAIL** (placeholder variant returns 0).
- [ ] **Step 3: Wire the MPC.** Replace the two MPC placeholder variants with references to the user's MPC model
  (reference block / `From Workspace` preview for `+V2X`, const-leader assumption for `−preview`), mapping
  `(s,v,Δv,v_l) → a_cmd`. Log the per-step **solver time** to `To Workspace` (feeds the Phase-C cost axis).
- [ ] **Step 4: Run tMpcLoop — expect PASS.**
- [ ] **Step 5: Full matrix.** Run `run_mpc_vs_snn` over all 4 configs × the scenario bank × K; render-verify the
  now-complete overlays/tables. Commit. `git commit -m "feat(cf): wire the online MPC (+/- V2X) into the harness; full behavioural matrix"`

---

## Task 9: Phase A close-out

- [ ] **Step 1: Green suite.** `run_cf_tests.m` runs every `matlab/cf/tests/t*.m` explicitly.
  Run: `matlab -batch "cd matlab/cf; assert(run_cf_tests())"` — expect all pass.
- [ ] **Step 2: README + resume.** Write `matlab/cf/README.md` (how to run + the parity discipline) and add a
  Phase-A-done note to the track's `document/SESSION_RESUME.md`.
- [ ] **Step 3: Commit + push.** `git add -A && git commit -m "docs(cf): Phase A behavioural comparison — done" && git push origin Simulink_Importer`

> **Milestone of Phase A:** the SNN configs (float + B2) produce full behavioural results + figures now; the
> MPC configs complete the matrix as soon as the user's model is wired (Task 8). Phase B (MPC-on-FPGA) and
> Phase C (Pareto + create-report) follow as their own plans.

---

## Notes for the executor

- **MATLAB only.** Every `Run:` is `matlab -batch "cd matlab/cf; …"` from the worktree root (R2026a headless).
- **No LAPACK in metric code paths if this ever runs under `cf_sim`** — but here metrics run in MATLAB, so
  MATLAB's own linear algebra is fine; the LAPACK/OMP #15 gotcha is a `cf_sim`-Python constraint only.
- **Parity is the safeguard** (Task 3): trust MATLAB metrics only after `tMetricsParity` is green.
- **Frozen assets** (`snn_core.m`, B2, `cf_plant_lib.slx`) are read-only references; all new code is under `matlab/cf/`.
- **MPC dependency** is isolated to Tasks 0 and 8 — Tasks 1–7 + 9(partial) deliver the full SNN-side pipeline first.
