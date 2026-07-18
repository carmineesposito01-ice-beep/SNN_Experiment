# The fixed-point twin — a live quantized ghost — Design Spec

**Date:** 2026-07-18 · **Branch/worktree:** `Simulator` · **Status:** ✅ **FINAL — approved by the user
2026-07-18.** This is **Action 7** of the Simulator backlog (the A/B float-vs-fixed study), reshaped by the
user into a richer, live form: *quantize the network in the simulation and watch it drive*.

## Goal

Let the user run the champion's SNN forward in **fixed-point (Qm.n)** as a **live ghost** alongside the float
network, with **`nfrac` adjustable by a slider**, so the effect of numeric precision on the driving is visible
in real time on the road / Trajectory / Safety panels.

## Why this shape (the exploration that grounded it)

**The fixed-point spec already exists** — in the `Simulink_Importer` worktree (HDL/FPGA track), the SNN forward's
fixed-point format is written down in prose (`document/HDL_PHASE.md` §4) and code (`matlab/snn_types.m`): po2
weights **Q2.13**, membrane **Q5.13**, adaptation (fatigue) **Q3.13**, wide accumulator **Q8.17**, readout
**Q7.13**; the arithmetic (leak = `x − bitsra(x,3)` = ×0.875, spike `V≥θ`, soft-reset `V−spike·θ`, weight
multiply = shift because po2) is in `matlab/snn_core.m`. Operating point **nfrac=13**.

**The A/B was already done in MATLAB** — `run_fixed_sweep.m` swept `nfrac ∈ {5,7,9,11,13}` and measured the
per-champion max error on the 5 params; headline **≤ 0.028 on `v0`** at nfrac=13 (`report/FPGA_PHASE_B_REPORT.md`).
So a batch A/B number is not the gap. **The gap the user wants filled is seeing it in the simulator** — the
divergence, live, as a knob moves — which MATLAB could not show.

**The simulator has the exact seam already.** `sim/backend.py` defines a `NetworkBackend` Protocol
(`reset`/`infer`/`read_probe`/`read_weights`); `SimStepper` takes a `backend` and the line
`params = self.backend.infer(_norm_obs(...))` (`sim/stepper.py:72`) is the only place the network produces the
5 params — everything downstream (the ACC-IIDM plant, the ballistic update) is float and shared. The Oracolo
ghost is `SimStepper.from_scenario(None, sc, injector=…)` (`sim/ui/app.py:519`), run in lockstep. The ALIF cell
exposes `potential`/`fatigue`/`base_threshold` (`sim/backend.py:54-56`), and the leak is *already* a po2
bit-shift (`bit_shift=3`, `core/network.py:8`). Everything the twin needs is present.

## Decisions taken (the user's calls, 2026-07-18)

1. **Fidelity = representative + adjustable `nfrac`** (chosen over bit-exact-to-FPGA). Quantize weights + state
   at the Qm.n grid with round-to-nearest + saturate, `nfrac` a knob. It shows the *effect* of precision on the
   drive; it does **not** reproduce the silicon to the bit. The two bit-exact gaps (the implicit store-back
   rounding, the per-champion po2 exponents) therefore do **not** need chasing.
2. **Consumption = a live twin** (chosen over a quantified A/B report). The fixed forward runs as a **ghost**
   reusing the Oracolo pipeline; the divergence *is* the comparison, live and visual.
3. **Approach A** (weight + state quantization, wrapping the float forward) over **B** (a full Qm.n datapath
   re-implementation). **B is kept as a possible future study** — if A convinces, try B for the datapath-faithful
   (accumulator-level) version.
4. **The ghost slot becomes a two-voice selector** `Oracolo (ideale) | Fixed-point`, plus an off state.
5. **`nfrac` is a mutable backend attribute** — no rebuild; the running ghost picks up changes going forward.
6. **The `FixedPointBackend` holds its OWN model** (a deepcopy of the loaded champion) — the forward is stateful,
   so quantizing `cell.potential` in place must not corrupt the live float network running in lockstep.

## Architecture

The one new unit is `sim/fixed_backend.py`. Everything else is reuse.

```
SimLoop (lockstep, existing)
  ├── stepper  = SimStepper(SoftwareBackend(model))            ← the live float network, UNCHANGED
  └── ghost    = SimStepper(<ghost backend>)                   ← app.py:519, the ONE line that changes
                   backend = None                              → the ideal oracle (today)
                   backend = FixedPointBackend(model, nfrac)   → the quantized twin (new)
```

`FixedPointBackend` implements the `NetworkBackend` contract, **family-aware** like `SoftwareBackend`, with a
distinct hook per family (both handled — loading the other must not break):

- **EventProp (Donatello, Michelangelo — the FPGA-deployed family).** `sim/eventprop_stepper.py` is *already* an
  explicit stateful Python forward: it holds its own state (`_V`, `_fatigue`, `_s_prev`, `_V_out` — plain
  **writable** tensors, `:48-51`) and *already* quantizes weights via `po2_quantize` (`core.hardware`, `:35-40`).
  So the twin is a **`FixedPointEventPropStepper`** that reuses that structure and adds Qm.n quantization at the
  three points. This de-risks the important family: the state is writable and the arithmetic is right there
  (`:62-73`). Its state is its own, and it reads the model weights read-only — so no model copy is needed (the
  live network already runs a *separate* `EventPropStepper(model)` instance without conflict).
- **Baseline (Raffaello, Leonardo).** The forward is `model.forward_step`, which mutates the shared
  `layer_hidden.cell`. The twin wraps `forward_step` on a **deep-copied** model (so its in-place state
  quantization does not corrupt the live float network) and quantizes `cell.potential`/`cell.fatigue` after each
  step. Weights are pre-quantized.

## The quantization (approach A)

One primitive — round-to-nearest, saturate, `m` integer bits fixed by the format, `n = nfrac` the knob:

```python
def q(x, m, n):                       # signed Qm.n
    step = 2.0 ** (-n)
    lo, hi = -(2.0 ** m), 2.0 ** m - step
    return np.clip(np.round(x / step) * step, lo, hi)
```

Applied at **three points**, with the spec's formats (integer bits fixed, `nfrac` variable):

| what | format | when |
|---|---|---|
| weights (`fc_weight`, `rec_U`, `rec_V`, `w_out`) | Q2.**n** | once at construction; re-quantized when `nfrac` changes |
| ALIF state (`potential`, `fatigue`) | Q5.**n** / Q3.**n** | after each `forward_step`, in place |
| readout (the 5 params) | Q7.**n** | at `infer`'s output |

The weights are **already** po2 in the float forward (`core.hardware.po2_quantize`, used by both families) — the
fixed-point adds the Qm.n *fractional* clip on top: `q(po2_quantize(w), 2, nfrac)`. Why `nfrac` shows something:
a po2 weight `2⁻⁶` needs 6 fractional bits, so at `nfrac=5` it rounds to `2⁻⁵` or **0** — lowering `nfrac`
progressively kills the small po2 weights and coarsens the state, so the drive degrades **visibly**. The `m`
integer bits stay fixed (they bound the range, as on the FPGA); only `nfrac` moves, exactly like the MATLAB
sweep.

**What it does NOT capture (honest):** it quantizes *weights + state + output* at the Qm.n grid, **not** the
datapath — no wide Q8.17 accumulator, no exact po2-shift path. It shows how weight and state precision degrade
the drive as `nfrac` drops; it does **not** match the FPGA to the bit (that is B).

**Correctness — state isolation:** the fixed twin's state must not corrupt the live float network stepping in
lockstep. For **EventProp** this is free — a separate `FixedPointEventPropStepper(model)` instance holds its own
state and reads the weights read-only (exactly as the live `EventPropStepper(model)` already does). For
**baseline** it requires a **deepcopy** of the model, because `forward_step` mutates the shared cell. (The
oracle had no such issue: `backend=None`, no model.)

## The UI

Today's `QCheckBox("Oracolo")` (`sim/ui/app.py:141`) becomes a **three-state selector** — the ghost can also be
off:

`Ghost: [ nessuno ▾ | Oracolo (ideale) | Fixed-point ]` + an **`nfrac` slider** beside it.

- The combo drives `app.py:519`: `nessuno` → no ghost · `Oracolo` → `backend=None` (as today) · `Fixed-point`
  → `FixedPointBackend(model, nfrac)`.
- The `nfrac` slider: range **5→13** (the MATLAB sweep), default **13** (the operating point), live label
  `nfrac=13`. **Enabled only when Fixed-point is selected**, greyed otherwise (*an input that does nothing is a
  lie* — the project's principle). Dragging it re-quantizes the ghost's weights and the divergence evolves
  forward; for the whole curve at a given `nfrac`, re-select the scenario (it restarts at t=0).
- **Panels and road: no new code.** The grey dotted ghost curves on Trajectory/Safety and the semi-transparent
  ghost car on the road are already there — the fixed twin inherits them. Only the ghost's **legend/label**
  changes to `fixed-point (nfrac=X)` when that mode is active.

## Testing

Every test asserts a **value** (a sabotage breaks it):

1. **`q(x, m, n)`** — round-to-nearest + saturate at the grid: exact at `n=13` for ≤13-frac values, clips at the
   Qm.n extremes, rounds/kills small po2 at low `n`. Pure unit.
2. **`FixedPointBackend` honors the contract** — `reset`/`infer`/`read_probe`/`read_weights`, family-aware
   (baseline + EventProp), `infer` returns (1,5).
3. **State isolation** — stepping the fixed ghost does **not** mutate the live network's state. Baseline: two
   backends on the same loaded champion, step the fixed one, the live `cell.potential` is unchanged (fails if the
   deepcopy is missing). EventProp: the `FixedPointEventPropStepper`'s `_V`/`_fatigue` diverge from a separate
   live `EventPropStepper`'s, confirming independent state.
4. **⭐ The effect exists and is monotone** — at `nfrac=13` the twin is *close* to float; at `nfrac=5` it
   diverges *more*: `divergence(5) > divergence(13)` on the 5 params over a scenario. The central value — proof
   the slider shows something. A no-op quantization fails it.
5. **`nfrac` is mutable and re-quantizes the weights** — changing `backend.nfrac` changes the quantized weights
   and the output.
6. **The selector wiring** (app) — choosing "Fixed-point" builds the ghost with a `FixedPointBackend`; the
   slider changes its `nfrac`; "Oracolo" still builds `backend=None`.
7. **Invariants** — **core frozen bit-identical** (`FixedPointBackend` must NOT touch `core/network.py`: it
   wraps a deepcopy and quantizes externally); `closed_loop_eval`, `stepper`, `state` intact (empty diff).

Honest verification note: at `nfrac=13` a *small* divergence is expected (consistent with the MATLAB ≤0.028),
but it is **not** pinned to that number — this is representative, not bit-exact. The test is the **monotonicity**
(lower `nfrac` → larger divergence), not correspondence with the silicon.

## Files

**New:** `sim/fixed_backend.py` — the `q` primitive, `FixedPointBackend` (family dispatch, mutable `nfrac`), the
`FixedPointEventPropStepper` (EventProp path, built on the existing stepper's structure), and the baseline
wrapper (deepcopy + `forward_step` + state quantization). `tests/test_sim_fixed_backend.py`.
**Modified:** `sim/ui/app.py` (the Oracolo checkbox → a three-state selector + the `nfrac` slider; the ghost
stepper at `:519` picks the backend by mode). No change to `core/network.py`, `sim/eventprop_stepper.py`,
`sim/stepper.py`, `utils/closed_loop_eval.py`, or any frozen-core file — the fixed path reuses `po2_quantize` and
the stepper's structure without editing them.

## Scope / non-goals

- **NOT bit-exact to the FPGA.** Representative quantization. The bit-exact, datapath-faithful version is
  **Approach B**, a deliberate future study (the user asked to keep it in reserve).
- **NOT a spike/energy comparison.** The fixed-point also changes the network's spikes and energy — comparing
  SpikeRate/energy float-vs-fixed would be the richest part of the story, but the user chose the live *driving*
  twin; the ghost pipeline draws trajectory/safety/road, not ghost spikes. A natural future extension, not this
  cycle (YAGNI).
- **NOT a batch A/B report.** MATLAB already has the batch numbers (≤0.028); the deliverable here is the live,
  visual twin.
- **The frozen core stays frozen.** The quantization wraps a deepcopy and acts from outside; `core/network.py`
  is not modified.
