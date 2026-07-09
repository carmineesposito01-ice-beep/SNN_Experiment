# Meso/Macro Analysis Mode — Design Spec

**Date:** 2026-07-09 · **Branch/worktree:** `Simulator` · **Status:** approved design → plan next

## Goal

Add a second **mode** to the simulator — a toggle between the current **Live** single-vehicle
cockpit and a new **Meso/Macro analysis** page — that runs *platoon* and *ring* simulations
on-demand and shows the fundamental traffic-flow metrics: string stability, space-time waves, the
fundamental diagram, and per-vehicle identified parameters. Works for **all 4 champions** (BPTT +
EventProp). The methodology is **reused** from the existing, report-validated `utils/platoon_eval.py`
— nothing is invented.

## Established facts this design reuses

- `utils/platoon_eval.py` already implements the validated meso/macro methodology:
  - **MESO** — `simulate_platoon(model, params_gt, n_vehicles, v_leader_profile)`: N vehicles in a
    line, vehicle 0 (head) follows an external profile, `i` follows `i-1` (CAM from `i-1`); returns
    `v,x,gap,a` (T,N) + `v_leader` + `collided`. `platoon_metrics(rec)` → `gain_per_vehicle`
    (`|H|_i = A_i/A_0`), `head_to_tail_gain`, `max_amplification`, `string_stable_headtail` (≤1),
    `strict_monotone_decay`, `convective_upstream`, `min_gap_platoon`, `min_ttc_platoon`,
    `rms_accel_mean`, `max_decel_platoon`, `rms_jerk_mean`.
  - **MACRO** — `simulate_ring(model, params_gt, n_vehicles, ring_length, n_steps, perturb)`: N
    vehicles on a ring, density `ρ = N/L`; returns `v,x` (T,N) + `density`.
    `fundamental_diagram(model, params_gt, densities_veh_per_km, ring_length, n_steps)` → per-density
    points `{rho_veh_km, Q_veh_h, V_m_s, V_km_h, n, wave_std, unstable}` (Edie).
- Both families forward a **batch of N vehicles**: baseline `model.forward_step((N,4))→(N,5)`;
  eventprop `EventPropStepper.reset(N)` + `step((N,4))→(N,5)` (state tensors are `(N,out)`,
  `F.linear` is batch-safe, `_decode_params` is per-row). `platoon_eval` currently hardwires the
  baseline path (`_params_for` → `model.forward_step`), so it works for BPTT only today.
- The champion selector (just landed) exposes `self._champ` (the selected champion) — the analysis
  runs whichever champion is selected.

## Non-goals / invariants

- **Frozen behavioral core untouched**: `sim/state.py`, `sim/stepper.py`, `sim/backend.py`
  (infer/step), `sim/events.py`, `sim/probe.py` record(), `sim/eventprop_stepper.py` step(). The
  batched-forward reuse READS the model / calls the existing `EventPropStepper.step`; no numeric
  change.
- **`utils/platoon_eval.py` stays report-compatible**: the family-aware forward is added via an
  **optional** `forward` hook (default = today's baseline path). Existing report scripts unaffected.
- No live-per-tick coupling: the analysis is **batch, on-demand** (press "Run" → compute → show).
  The Live mode is unchanged.

## Design

### ① Mode toggle (Live ↔ Meso/Macro)

The central widget becomes a `QStackedWidget` with two pages: page 0 = the current `DockArea`
workspace (Live); page 1 = the new `MesoMacroPage`. A top toggle (a 2-button segmented control or a
`QComboBox`) switches pages. The controls row and View/Layout menus belong to Live; the analysis
page carries its own controls. Switching to analysis stops the live timer (pauses the live sim).

### ② Family-aware batched forward

New `sim/ui/platoon.py`:
- `batched_forward(champion, n, device="cpu")` → a **stateful** object with `reset()` +
  `infer(x_batch)->(n,5)`:
  - baseline (`.model.forward_step` exists) → `model.reset_state(n); model.forward_step(x)`.
  - eventprop (`CF_FSNN_Net_EventProp_Full`) → `EventPropStepper(model); .reset(n); .step(x)`.
- `run_platoon(champion, params_gt, n, v_leader_profile)` and `run_ring(...)` /
  `run_fundamental_diagram(...)` call the `platoon_eval` sims, injecting the family-aware forward.

`utils/platoon_eval.py` gets an **additive** optional `forward=None` parameter on
`simulate_platoon`/`simulate_ring` (default keeps `_params_for`/`model.forward_step`); when given, the
loop uses `forward.infer(...)` and the caller owns `forward.reset(n)`.

**Correctness test:** batched eventprop forward for `n=1` == the single-vehicle `EventPropStepper`
(bit-identical); baseline `n` vehicles == the existing `_params_for` path.

### ③ Analysis panels (`sim/ui/meso_panels.py`)

- **StringStabilityPanel** — bar chart of `gain_per_vehicle` `|H|_i` vs vehicle index, with the `=1`
  reference line + a verdict readout (string-stable? head-to-tail gain, max amplification, monotone
  decay, convective-upstream).
- **SpaceTimePanel** — space-time diagram: `x(t)` trajectory of each of the N vehicles, coloured by
  speed (viridis) → stop-and-go waves visibly propagate upstream. (pyqtgraph multi-curve or an
  ImageItem of the speed field over (t, vehicle).)
- **FundamentalDiagramPanel** — `Q(ρ)` and `V(ρ)` from the density sweep (two X-linked plots), the
  unstable points marked (`wave_std > 0.5`), and the current operating point.
- **PlatoonParamsPanel** — the 5 ACC-IIDM params each vehicle's SNN produces (mean over the regime),
  as 5 small bar/box strips across vehicle index → identification dispersion along the platoon.

### ④ Analysis controls

A controls strip on the analysis page: `N vehicles` (spin), `perturbation amplitude`/`period`
(for the head profile), `density range` (for the sweep), and two buttons — **"Run platoon"**
(meso: string stability + space-time + per-vehicle params) and **"Run ring sweep"** (macro:
fundamental diagram). Runs use the currently selected champion + `_PARAMS_GT`.

### ⑤ Implementation phases (for the plan)

- **T1** — `MesoMacroPage` scaffold + `QStackedWidget` mode toggle wired into `SimApp` (empty
  analysis page, toggle stops the live timer). Integration test: toggle swaps pages.
- **T2** — `sim/ui/platoon.py` family-aware batched forward + `platoon_eval` additive `forward` hook;
  golden tests (eventprop batched n=1 == single-vehicle; baseline path unchanged).
- **T3** — `StringStabilityPanel` + `SpaceTimePanel` fed by `run_platoon`; wire "Run platoon".
- **T4** — `FundamentalDiagramPanel` + `PlatoonParamsPanel` fed by `run_ring`/`run_fundamental_diagram`;
  wire "Run ring sweep".
- **T5** — render-verify (all 4 champions), golden suite, docs/memory.

## Testing strategy

1. **Batched forward golden** — eventprop `batched_forward(champ, 1).infer(x)` == single-vehicle
   `EventPropStepper.step(x)`; baseline `model.forward_step` batch matches per-vehicle.
2. **platoon_eval hook** — `simulate_platoon(model, ..., forward=fw)` == `simulate_platoon(model, ...)`
   for a baseline model (the hook reproduces the default path).
3. **Panels** (offscreen) — StringStability bars == `gain_per_vehicle`; SpaceTime has N curves;
   FundamentalDiagram plots the sweep points; PlatoonParams shows 5×N.
4. **App integration** — mode toggle swaps the central page + stops the timer; "Run platoon" with the
   selected champion populates the meso panels; works for a BPTT and an EventProp champion.
5. **Golden suite** — the single-vehicle golden stays bit-identical (core + platoon_eval default path
   untouched).
6. **Render** — analysis page for Raffaello (BPTT) and Donatello (EventProp).
