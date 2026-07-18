# Fixed-point twin (Action 7) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the champion's SNN forward in fixed-point (Qm.n) as a **live ghost** beside the float network, with `nfrac` on a slider, so numeric precision's effect on the driving is visible in real time on the cockpit panels.

**Architecture:** One new file, `sim/fixed_backend.py`, implementing the existing `NetworkBackend` contract (`reset`/`infer`/`read_probe`/`read_weights`). It is **family-aware** like `SoftwareBackend`: EventProp reuses `EventPropStepper`'s explicit forward in a subclass that adds Qm.n quantization at three points (weights Q2.n once, ALIF state V→Q5.n / fatigue→Q3.n per tick, readout Q7.n at output); baseline deep-copies the model, runs `forward_step`, and quantizes `cell.potential`/`cell.fatigue` after each step. The UI's `QCheckBox("Oracolo")` becomes a three-state selector `[nessuno | Oracolo (ideale) | Fixed-point]` + an `nfrac` slider; the ghost at `app.py:519` picks its backend by mode. **The frozen core is not touched** — the twin reuses `po2_quantize` and the stepper's structure from outside.

**Tech Stack:** Python, PyTorch, PySide6 (Qt). Conda env `cf_sim`. pytest.

---

## Running the tests (READ THIS — three traps bit us this session)

**Env + suite command** (never `conda run`, never bare `pytest tests/`):

```bash
ENV=C:/Miniconda/envs/cf_sim
OUT="C:/Users/USERPO~1/AppData/Local/Temp/claude/D--Project-MBSE-0-Documenti-Platooning-Focus-Traffic-Flow-2025/6b68f726-445b-4b51-9785-cef5329bb37f/scratchpad/pytest_out.txt"
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest \
  tests/test_sim_fixed_backend.py -v > "$OUT" 2>&1; echo "PYTEST_EXIT=$?"
```

Then **Read `$OUT`** — do NOT pipe to `tail`/`head`.

1. **The pipe trap.** `pytest … | tail` reports *tail's* exit code, not pytest's, and torch/OMP prints a faulthandler shutdown stack at interpreter teardown that *looks* like a crash. Always redirect to a file + `echo PYTEST_EXIT=$?`, then Read the file. `PYTEST_EXIT=0` is the only green.
2. **Single file during TDD, full glob only at T5.** RED/GREEN cycles run just `tests/test_sim_fixed_backend.py` (fast — torch loads once). The full `tests/test_sim_*.py tests/test_champion_io.py` glob is the T5 gate (~3 min → `timeout ≥ 420s` or background, and run nothing else in parallel).
3. **No LAPACK/scipy in `cf_sim`** (`matrix_rank`/`polyfit`/`svd` → OMP abort #15). The `q` primitive is `torch.round`/`torch.clamp` only.

---

## File structure

| File | New/Mod | Responsibility |
|---|---|---|
| `sim/fixed_backend.py` | **New** | `q(x,m,n)` primitive; `FixedPointBackend` (family dispatch, mutable `nfrac`, readout Q7.n); `FixedPointEventPropStepper` (EventProp path, subclasses the stepper); `_FixedBaseline` (baseline deepcopy + state quant). |
| `tests/test_sim_fixed_backend.py` | **New** | `q` unit; contract (both families); state isolation (both); ⭐ monotonicity; `nfrac` mutability. |
| `sim/ui/app.py` | **Mod** | Oracolo checkbox → 3-state selector + `nfrac` slider; `:519` ghost backend by mode; three toggle-state readers → `_ghost_visible()`. |
| `tests/test_sim_ui_smoke.py` | **Mod** | Retarget 5 `_ghost_toggle` sites to the combo; add 2 Fixed-point selector tests. |

**Frozen — MUST show empty diff at T5:** `core/`, `sim/state.py`, `sim/stepper.py`, `sim/backend.py`, `sim/eventprop_stepper.py`, `sim/probe.py`, `sim/events.py`, `utils/closed_loop_eval.py`.

**Reference values (all read from live source, not memory):**
- Loader: `from utils.champion_io import load_champion` → `load_champion(path).model`.
- Baseline champion (default, always present): `champions/R33_C2_A1_T12_fix/best_model.pt` (rank 8, `w_in (32,4)`, `w_out (5,32)`).
- EventProp champion (skip-guard if absent): `champions/PE_t05_gp0002/best_model.pt` (Donatello).
- Obs shape: `torch.tensor([[a,b,c,d]], dtype=torch.float32)` → `(1,4)`; `infer` returns `(1,5)`.
- `po2_quantize` (`core/hardware.py:46-59`): exponent clamped to `[-4,1]`, `|w|≤2⁻⁵` masked to 0 → smallest nonzero po2 weight is `2⁻⁴` → **Q2.n on weights is a no-op for every `nfrac∈[5,13]`**; the slider's visible effect lives in **state** quantization.

---

## Task 1: The `q(x, m, n)` primitive

**Files:**
- Create: `sim/fixed_backend.py`
- Test: `tests/test_sim_fixed_backend.py`

- [ ] **Step 0: Baseline is green + commit the spec §2 correction.**

The spec's §2 fix (po2 weights representable at nfrac≥4) is uncommitted. Commit it so the invariant BASE is clean, then record BASE.

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulator"
git add docs/superpowers/specs/2026-07-18-fixed-point-twin-design.md
git commit -m "docs(sim): §2 — le Q2.n sui pesi po2 sono no-op per nfrac>=4, l'effetto vive nello stato"
git rev-parse --short HEAD    # <-- this is BASE for the T5 invariant check
```

Run the full suite once (command from the preamble, but with the full glob) and confirm it is green. Expected: **399 passed** (the 7b baseline). Record the exact number N — T5 expects **N + the new tests**.

- [ ] **Step 1: Write the failing `q` tests.**

Create `tests/test_sim_fixed_backend.py` (minimal imports — T2/T3 add what they need, so the file collects green at each task):

```python
import os
import sys

import pytest
import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.fixed_backend import q                                  # noqa: E402


# ------------------------------- q primitive -------------------------------
def test_q_is_exact_for_representable_values():
    assert float(q(torch.tensor(0.0625), 2, 13)) == 0.0625     # 2^-4, exact at n>=4
    assert float(q(torch.tensor(-1.5), 5, 13)) == -1.5

def test_q_rounds_to_nearest_grid_point():
    # 0.1 at Q2.4 (step 1/16 = 0.0625): 0.1/0.0625 = 1.6 -> 2 -> 0.125
    assert abs(float(q(torch.tensor(0.1), 2, 4)) - 0.125) < 1e-6

def test_q_saturates_at_qmn_extremes():
    assert float(q(torch.tensor(5.0), 2, 4)) == 3.9375         # hi = 2^2 - 2^-4
    assert float(q(torch.tensor(-5.0), 2, 4)) == -4.0         # lo = -2^2

def test_q_kills_small_po2_at_low_nfrac():
    assert float(q(torch.tensor(0.0625), 2, 3)) == 0.0        # Q2.3 step 1/8: 0.5 -> half-to-even -> 0
    assert float(q(torch.tensor(0.0625), 2, 4)) == 0.0625     # survives at n=4
```

- [ ] **Step 2: Run — expect ImportError.**

Run `tests/test_sim_fixed_backend.py` (preamble command). Expected: FAIL — `ModuleNotFoundError: No module named 'sim.fixed_backend'` (or `ImportError: cannot import name 'q'`).

- [ ] **Step 3: Write `sim/fixed_backend.py` with `q` + the format constants.**

```python
"""FixedPointBackend -- a live Qm.n quantized twin of the champion, run as a ghost.

Approach A (spec docs/superpowers/specs/2026-07-18-fixed-point-twin-design.md): wrap the
float forward and quantize weights + ALIF state + readout at the Qm.n grid, `nfrac` a live
knob. It shows the EFFECT of precision on the drive; it is NOT bit-exact to the FPGA
(that is Approach B). Family-aware like SoftwareBackend; the frozen core is reused, never
edited (po2_quantize from core.hardware, the stepper's structure from sim.eventprop_stepper).
"""
import copy

import torch
import torch.nn.functional as F

from core.hardware import po2_quantize
from core.network import CF_FSNN_Net_EventProp_Full
from sim.eventprop_stepper import EventPropStepper

# Integer bits per the Simulink_Importer fixed-point spec (HDL_PHASE.md §4 / snn_types.m).
# nfrac is the knob; these bound the range and stay fixed, exactly as on the FPGA.
_M_WEIGHT = 2      # Q2.n  weights (po2, already in [-2, 2])
_M_VMEM = 5        # Q5.n  membrane potential
_M_FATIGUE = 3     # Q3.n  adaptation (fatigue)
_M_READOUT = 7     # Q7.n  the 5 decoded params


def q(x, m, n):
    """Signed Qm.n: round-to-nearest (half-to-even, as the FPGA), saturate to [-2^m, 2^m - 2^-n].

    torch, not numpy: every consumer -- weights, state, readout -- is a torch tensor, and
    SimStepper does params.view(-1) on infer's output (stepper.py:92), so infer must return a
    tensor; a numpy q would force a host round-trip every tick.
    """
    step = 2.0 ** (-n)
    lo = -(2.0 ** m)
    hi = 2.0 ** m - step
    return torch.clamp(torch.round(x / step) * step, lo, hi)
```

- [ ] **Step 4: Run — expect the 4 `q` tests to pass.**

Run `tests/test_sim_fixed_backend.py`. Expected: `PYTEST_EXIT=0`, 4 passed.

- [ ] **Step 5: Commit.**

```bash
git add sim/fixed_backend.py tests/test_sim_fixed_backend.py
git commit -m "feat(sim): q(x,m,n) -- primitiva fixed-point Qm.n (round-to-nearest + saturazione)"
```

---

## Task 2: The baseline path — `FixedPointBackend` + `_FixedBaseline`

**Files:**
- Modify: `sim/fixed_backend.py`
- Test: `tests/test_sim_fixed_backend.py`

- [ ] **Step 1: Write the failing baseline tests.**

First, add to the imports at the top of `tests/test_sim_fixed_backend.py` (T1 imported only `q`):

```python
import math                                              # add beside `import os`, `import sys`
from utils.champion_io import load_champion              # noqa: E402
from sim.backend import SoftwareBackend                  # noqa: E402
from sim.fixed_backend import q, FixedPointBackend       # replace the T1 `from sim.fixed_backend import q`

CHAMP_BASELINE = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")
CHAMP_EVENTPROP = os.path.join(REPO, "champions", "PE_t05_gp0002", "best_model.pt")
```

Then append the helpers + baseline tests:

```python
# ------------------------------- helpers -------------------------------
def _obs_sequence(n=60):
    """Deterministic, varied normalized (1,4) inputs (same scale as test_sim_backend.py:24)."""
    seq = []
    for k in range(n):
        a = 0.30 + 0.25 * math.sin(k / 5.0)
        b = 0.30 + 0.25 * math.sin(k / 7.0 + 1.0)
        c = 0.50 - 0.20 * math.cos(k / 6.0)
        seq.append(torch.tensor([[a, c, a - b, b]], dtype=torch.float32))
    return seq

def _param_divergence(model, nfrac, obs_seq):
    """Mean |fixed params - float params| over the sequence (both reset, independent state)."""
    fb = FixedPointBackend(model, nfrac=nfrac); fb.reset()
    sb = SoftwareBackend(model); sb.reset()
    tot = 0.0
    for obs in obs_seq:
        pf = fb.infer(obs).view(-1)
        ps = sb.infer(obs).view(-1)
        tot += float(torch.abs(pf - ps).mean())
    return tot / len(obs_seq)


# --------------------------- baseline contract ---------------------------
def test_backend_contract_baseline():
    be = FixedPointBackend(load_champion(CHAMP_BASELINE).model, nfrac=13)
    be.reset()
    out = be.infer(torch.tensor([[0.4, 0.3, 0.5, 0.3]], dtype=torch.float32))
    assert tuple(out.shape) == (1, 5)
    assert be.read_weights()["rank"] == 8                      # same topology exposure as SoftwareBackend
    assert be.read_probe()["v_mem"].shape == (32,)

def test_baseline_twin_does_not_corrupt_the_live_network():
    """State isolation: the twin deep-copies the model, so stepping it never moves the live cell."""
    model = load_champion(CHAMP_BASELINE).model
    sb = SoftwareBackend(model); sb.reset()                    # the LIVE float net (original model)
    fb = FixedPointBackend(model, nfrac=5); fb.reset()         # deep-copies model inside
    pot_before = model.layer_hidden.cell.potential.clone()
    obs = torch.tensor([[0.4, 0.3, 0.5, 0.3]], dtype=torch.float32)
    for _ in range(5):
        fb.infer(obs)                                          # step ONLY the twin
    assert torch.equal(model.layer_hidden.cell.potential, pot_before)   # fails if the deepcopy is missing

def test_lower_nfrac_diverges_more_from_float_baseline():     # ⭐ the central proof (state-driven)
    model = load_champion(CHAMP_BASELINE).model
    seq = _obs_sequence(60)
    d13 = _param_divergence(model, 13, seq)
    d5 = _param_divergence(model, 5, seq)
    assert d5 > d13, f"coarser quant must diverge more: d5={d5} d13={d13}"

def test_nfrac_change_moves_the_output_baseline():
    model = load_champion(CHAMP_BASELINE).model
    obs = torch.tensor([[0.4, 0.3, 0.5, 0.3]], dtype=torch.float32)
    be = FixedPointBackend(model, nfrac=13); be.reset()
    p13 = be.infer(obs).clone()
    be2 = FixedPointBackend(model, nfrac=5); be2.reset()
    p5 = be2.infer(obs).clone()
    assert not torch.equal(p13, p5)                            # the knob is observable at infer's output
```

- [ ] **Step 2: Run — expect failures (no `FixedPointBackend`).**

Run `tests/test_sim_fixed_backend.py`. Expected: the 4 new tests ERROR/FAIL (`ImportError`/`AttributeError` — `FixedPointBackend` undefined or the baseline engine missing). The 4 q tests still pass.

- [ ] **Step 3: Add `_FixedBaseline` + `FixedPointBackend` to `sim/fixed_backend.py`.**

Append (below `q`):

```python
class _FixedBaseline:
    """Baseline family (Raffaello, Leonardo). forward_step mutates the shared cell in place,
    so wrap a DEEP-COPIED model and quantize cell.potential (Q5.n) / cell.fatigue (Q3.n) after
    each step. Weights: forward_step re-applies po2 each call, and Q2.n on po2 is a no-op for
    nfrac>=4, so there is no separate weight hook."""

    def __init__(self, model, nfrac, device="cpu"):
        self.model = copy.deepcopy(model)     # protect the live float net from in-place state quant
        self.device = device
        self.nfrac = int(nfrac)

    def reset(self):
        self.model.eval()
        self.model.reset_state(1, self.device)

    def step(self, obs_norm):
        p = self.model.forward_step(obs_norm.to(self.device))
        cell = self.model.layer_hidden.cell
        with torch.no_grad():
            cell.potential.copy_(q(cell.potential, _M_VMEM, self.nfrac))
            cell.fatigue.copy_(q(cell.fatigue, _M_FATIGUE, self.nfrac))
        return p

    def read_probe(self):
        cell = self.model.layer_hidden.cell
        v_mem = cell.potential.detach().cpu().numpy().reshape(-1)
        spikes = cell.prev_spike.detach().cpu().numpy().reshape(-1)
        v_th = (cell.base_threshold + cell.fatigue.clamp(min=0)).detach().cpu().numpy().reshape(-1)
        return {"spikes": spikes, "v_mem": v_mem, "v_th_eff": v_th, "input": None}

    def read_weights(self):
        lh = self.model.layer_hidden
        return {"w_in": lh.fc_weight.detach().cpu().numpy(),
                "w_rec": (lh.rec_U @ lh.rec_V).detach().cpu().numpy(),
                "w_out": self.model.layer_out.fc_weight.detach().cpu().numpy(),
                "rank": int(lh.rec_V.shape[0])}


class FixedPointBackend:
    """NetworkBackend: a live Qm.n twin. Family-aware; nfrac is a mutable knob. The readout
    Q7.n is applied uniformly at infer's output; weights + state quant live in the engine."""

    def __init__(self, model, nfrac=13, device="cpu"):
        self._nfrac = int(nfrac)
        self._eventprop = isinstance(model, CF_FSNN_Net_EventProp_Full)
        if self._eventprop:
            raise NotImplementedError("EventProp path lands in T3")   # replaced in Task 3
        self._engine = _FixedBaseline(model, nfrac, device)

    @property
    def nfrac(self):
        return self._nfrac

    @nfrac.setter
    def nfrac(self, value):
        self._nfrac = int(value)
        self._engine.nfrac = int(value)      # baseline: plain knob; eventprop (T3): re-quantizes weights

    def reset(self):
        self._engine.reset()

    def infer(self, obs_norm):
        p = self._engine.step(obs_norm)
        return q(p, _M_READOUT, self._nfrac)  # readout Q7.n at infer's output (family-uniform)

    def read_probe(self):
        return self._engine.read_probe()

    def read_weights(self):
        return self._engine.read_weights()
```

- [ ] **Step 4: Run — expect all baseline tests green.**

Run `tests/test_sim_fixed_backend.py`. Expected: `PYTEST_EXIT=0`, 8 passed (4 q + 4 baseline). **If `test_lower_nfrac_diverges_more_from_float_baseline` fails** (marginal or reversed): the effect is real (MATLAB sweep measured it) but the sequence may be too benign — lengthen to `_obs_sequence(120)` or widen the sines. Do NOT weaken the assertion to `>=`; a strict `>` is the whole point.

- [ ] **Step 5: Commit.**

```bash
git add sim/fixed_backend.py tests/test_sim_fixed_backend.py
git commit -m "feat(sim): FixedPointBackend baseline -- deepcopy + Q5.n/Q3.n stato + Q7.n readout"
```

---

## Task 3: The EventProp path — `FixedPointEventPropStepper`

**Files:**
- Modify: `sim/fixed_backend.py`
- Test: `tests/test_sim_fixed_backend.py`

- [ ] **Step 1: Write the failing EventProp tests.**

Add one import at the top (`EventPropStepper` is needed by the independent-state test):

```python
from sim.eventprop_stepper import EventPropStepper       # noqa: E402
```

Then append the EventProp tests:

```python
# --------------------------- EventProp path ---------------------------
def _skip_if_no_eventprop():
    if not os.path.exists(CHAMP_EVENTPROP):
        pytest.skip("eventprop champion not present")

def test_backend_contract_eventprop():
    _skip_if_no_eventprop()
    be = FixedPointBackend(load_champion(CHAMP_EVENTPROP).model, nfrac=13)
    be.reset()
    out = be.infer(torch.tensor([[0.4, 0.3, 0.5, 0.3]], dtype=torch.float32))
    assert tuple(out.shape) == (1, 5)
    assert be.read_weights()["rank"] > 0

def test_eventprop_twin_has_independent_state():
    """Stepping the fixed twin never moves a separate live EventPropStepper's state."""
    _skip_if_no_eventprop()
    model = load_champion(CHAMP_EVENTPROP).model
    live = EventPropStepper(model); live.reset()
    be = FixedPointBackend(model, nfrac=5); be.reset()
    v_live_before = live._V.clone()
    obs = torch.tensor([[0.4, 0.3, 0.5, 0.3]], dtype=torch.float32)
    for _ in range(5):
        be.infer(obs)                                          # step ONLY the twin
    assert torch.equal(live._V, v_live_before)                # the live stepper's state is untouched

def test_eventprop_nfrac_requantizes_weights():
    """Mutating nfrac re-quantizes the weights. Observable BELOW the no-op floor (nfrac<4):
    at Q2.3 the 2^-4 po2 weights round to 0."""
    _skip_if_no_eventprop()
    model = load_champion(CHAMP_EVENTPROP).model
    be = FixedPointBackend(model, nfrac=13)
    w13 = be._engine._w_out.clone()
    be.nfrac = 3
    w3 = be._engine._w_out.clone()
    assert not torch.equal(w13, w3)                            # weights really re-quantized
```

- [ ] **Step 2: Run — expect the EventProp tests to fail.**

Run `tests/test_sim_fixed_backend.py`. Expected: the 3 new tests FAIL — `FixedPointBackend(eventprop_model)` raises `NotImplementedError("EventProp path lands in T3")`. The 8 prior tests still pass.

- [ ] **Step 3: Add `FixedPointEventPropStepper` and wire the EventProp branch.**

In `sim/fixed_backend.py`, add the subclass (below `_FixedBaseline`):

```python
class FixedPointEventPropStepper(EventPropStepper):
    """EventProp path (Donatello, Michelangelo -- the FPGA-deployed family). Reuses the
    stepper's explicit forward and adds Qm.n at the three points: weights Q2.n (re-quantized
    on nfrac change), ALIF state V->Q5.n / fatigue->Q3.n per internal tick, readout Q7.n
    applied by FixedPointBackend at infer's output. Its state is its own (separate instance),
    so no model copy is needed -- it reads the model weights read-only, exactly as the live
    EventPropStepper(model) already does.

    The n_ticks loop is copied (not super().step) on purpose: the faithful model quantizes the
    V/fatigue REGISTERS every tick, and sim/eventprop_stepper.py is frozen (no per-tick hook to
    add). Keep this loop in lockstep with EventPropStepper.step if the frozen original changes.
    """

    def __init__(self, model, nfrac):
        super().__init__(model)              # sets po2 weights + resets state
        self._nfrac = int(nfrac)
        self._requantize_weights()

    def _requantize_weights(self):
        n = self._nfrac
        h = self.model.layer_hidden
        with torch.no_grad():
            w_po2 = po2_quantize(h.fc_weight)
            self._w_masked = [q(w_po2 * h.delay_masks[d], _M_WEIGHT, n)
                              for d in range(self.max_delay)]
            self._rec_full = q(po2_quantize(h.rec_U) @ po2_quantize(h.rec_V), _M_WEIGHT, n)
            self._w_out = q(po2_quantize(self.model.layer_out.weight), _M_WEIGHT, n)

    @property
    def nfrac(self):
        return self._nfrac

    @nfrac.setter
    def nfrac(self, value):
        self._nfrac = int(value)
        self._requantize_weights()           # live: no rebuild, picks up going forward

    @torch.no_grad()
    def step(self, x_norm):
        n = self._nfrac
        self._last_x = x_norm.detach().cpu().numpy().reshape(-1)
        for _ in range(self.n_ticks):
            self._x_hist.append(x_norm)
            I = torch.zeros(self._B, self.out_dim, device=self._device)
            for d in range(self.max_delay):
                I = I + F.linear(self._x_hist[-1 - d], self._w_masked[d])
            drive = I + F.linear(self._s_prev, self._rec_full)
            V_pre = self.alpha_m * self._V + drive
            V_th = self._base_th + self._fatigue.clamp(min=0)
            fired = (V_pre > V_th).float()
            self._V = q(V_pre - fired * V_th, _M_VMEM, n)                                    # Q5.n
            self._fatigue = q(self.alpha_f * self._fatigue + fired * self._thresh_jump.clamp(min=0),
                              _M_FATIGUE, n)                                                 # Q3.n
            self._s_prev = fired
            self._V_out = self._alpha_out * self._V_out + F.linear(fired, self._w_out)
        return self.model._decode_params(self._V_out)
```

Then replace the `NotImplementedError` branch in `FixedPointBackend.__init__`:

```python
        if self._eventprop:
            self._engine = FixedPointEventPropStepper(model, nfrac)   # own state, reads weights read-only
        else:
            self._engine = _FixedBaseline(model, nfrac, device)
```

The `_engine.step(obs)` and `_engine.nfrac = …` calls in `infer`/`reset`/the setter already work for both engines (the stepper's `reset()` is inherited from `EventPropStepper.reset(batch=1, device="cpu")`, callable with no args; `step(obs)` returns `(1,5)`).

- [ ] **Step 4: Run — expect all EventProp tests green.**

Run `tests/test_sim_fixed_backend.py`. Expected: `PYTEST_EXIT=0`, 11 passed (3 EventProp now green, or skipped if the champion is truly absent — it is present, so they run). **If `test_eventprop_nfrac_requantizes_weights` fails** (`w13 == w3`): the champion happens to have no `2⁻⁴`-magnitude po2 weight (unlikely for a 32×36 matrix). Assert on `_rec_full` or `_w_masked[0]` instead, or drop `nfrac` to `2` where the mask bites harder — the point is that the setter *observably* re-runs `q(po2(w), 2, n)`.

- [ ] **Step 5: Commit.**

```bash
git add sim/fixed_backend.py tests/test_sim_fixed_backend.py
git commit -m "feat(sim): FixedPointEventPropStepper -- Q2.n pesi / Q5.n-Q3.n stato per tick, stato indipendente"
```

---

## Task 4: The UI — three-state selector + `nfrac` slider

**Files:**
- Modify: `sim/ui/app.py` (import line 11; `141-146`, `166`, `519`, `634`, `725-729`, `774`)
- Test: `tests/test_sim_ui_smoke.py` (`518`, `525`, `529`, `546`, `557`; + 2 new)

**Churn (grepped across the whole worktree — the ONLY sites):** `_ghost_toggle` lives in `app.py` at 141/142/146/166/634/725/774 and in `test_sim_ui_smoke.py` at 518/525/529/546/557. `QCheckBox` is used only at `app.py:141`, so removing the toggle orphans its import.

- [ ] **Step 1: Retarget the 5 existing ghost-toggle tests + add 2 selector tests.**

In `tests/test_sim_ui_smoke.py`, edit the four bodies (line numbers pre-edit):

At **518** (`test_app_builds_a_ghost_and_toggle_is_off_by_default`):
```python
    assert win._ghost_mode.currentText() == "nessuno"          # ghost off by default
```

At **525** and **546** and **557** (`setChecked(True)` → select the oracle):
```python
    win._ghost_mode.setCurrentText("Oracolo (ideale)")
```

At **529** (`setChecked(False)` → off):
```python
    win._ghost_mode.setCurrentText("nessuno")
```

> These four cases use only the two oracle-equivalent states (`nessuno` ↔ `Oracolo`), both `backend=None`. The mode handler must treat that switch as **visibility only** (no rebuild), so the curves accumulated by `_advance` survive the toggle — exactly as the checkbox did. The Fixed-point rebuild (Step 3) is gated on a backend-*type* change.

Append two new tests (near the ghost block, ~line 561):
```python
def test_app_fixed_point_mode_builds_a_fixed_backend(qapp):
    from sim.fixed_backend import FixedPointBackend
    win = SimApp(CHAMP)
    win._ghost_mode.setCurrentText("Fixed-point")
    assert isinstance(win.loop.ghost.backend, FixedPointBackend)
    assert win._nfrac_slider.isEnabled() is True               # the knob is live
    win._nfrac_slider.setValue(7)
    assert win.loop.ghost.backend.nfrac == 7                   # dragging it re-quantizes forward

def test_app_nfrac_slider_disabled_unless_fixed_point(qapp):
    win = SimApp(CHAMP)
    assert win._nfrac_slider.isEnabled() is False              # nessuno -> greyed
    win._ghost_mode.setCurrentText("Oracolo (ideale)")
    assert win._nfrac_slider.isEnabled() is False              # oracle -> still greyed (a dead input is a lie)
    win._ghost_mode.setCurrentText("Fixed-point")
    assert win._nfrac_slider.isEnabled() is True
```

- [ ] **Step 2: Run — expect failures (`_ghost_mode`/`_nfrac_slider` undefined).**

Run the UI smoke file:
```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest \
  tests/test_sim_ui_smoke.py -v > "$OUT" 2>&1; echo "PYTEST_EXIT=$?"
```
Expected: the ghost tests FAIL — `AttributeError: 'SimApp' object has no attribute '_ghost_mode'`.

- [ ] **Step 3: Edit `sim/ui/app.py`.**

**(a) Import — drop the now-unused `QCheckBox`, add the backend (line 11 + top imports):**
```python
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel,
```
(remove `QCheckBox,` from that line — everything else on the import line stays). Add near the other `sim.ui`/`sim` imports:
```python
from sim.fixed_backend import FixedPointBackend
```

**(b) Replace the checkbox construction (141-146) with the selector + slider:**
```python
        self._ghost_mode = QComboBox()
        self._ghost_mode.addItems(["nessuno", "Oracolo (ideale)", "Fixed-point"])
        self._ghost_mode.setToolTip(
            "Ghost sovrapposto al veicolo vero:\n"
            " nessuno -- niente ghost;\n"
            " Oracolo (ideale) -- guidatore di riferimento ACC-IIDM coi parametri veri (diverge per costruzione);\n"
            " Fixed-point -- la STESSA rete quantizzata Qm.n: la divergenza mostra l'effetto della precisione.")
        self._nfrac_lbl = QLabel("nfrac=13")
        self._nfrac_slider = QSlider(Qt.Horizontal); self._nfrac_slider.setRange(5, 13)
        self._nfrac_slider.setValue(13); self._nfrac_slider.setFixedWidth(90)
        self._nfrac_slider.setEnabled(False)                # a dead input is a lie: on only for Fixed-point
        self._nfrac_slider.setToolTip("bit frazionari Qm.n del gemello fixed-point (5..13, 13 = punto operativo)")
        self._ghost_mode.currentIndexChanged.connect(self._on_ghost_mode_changed)
        self._nfrac_slider.valueChanged.connect(self._on_nfrac_changed)
```

**(c) Layout (166) — replace `self._ghost_toggle` with the group:**
```python
                  self._brake_btn, QLabel("ghost"), self._ghost_mode, self._nfrac_lbl,
                  self._nfrac_slider, QLabel("speed"), self._speed_slider,
```

**(d) Ghost creation (519) — pick the backend by mode:**
```python
        ghost_backend = (FixedPointBackend(self._champ.model, self._nfrac_slider.value())
                         if self._ghost_mode.currentText() == "Fixed-point" else None)
        ghost = SimStepper.from_scenario(ghost_backend, sc, injector=self._injector)   # SAME injector: same leader
```

**(e) `_redraw_series` (634) and the scrub reader (774) — toggle-state → helper:**
```python
        show_ghost = self._ghost_visible()      # off -> not drawn AND not computed
```
```python
        if self._ghost_visible():
            self._topdown.render_ghost_at(self._src_ghost_traj, idx)
```

**(f) Replace `_on_ghost_toggled` (725-729) with the helper + two handlers:**
```python
    def _ghost_visible(self):
        return self._ghost_mode.currentText() != "nessuno"

    def _on_ghost_mode_changed(self, _idx=None):
        if getattr(self, "loop", None) is None:               # fired during __init__, before the loop exists
            return
        want_fixed = self._ghost_mode.currentText() == "Fixed-point"
        have_fixed = isinstance(self.loop.ghost.backend, FixedPointBackend)
        self._nfrac_slider.setEnabled(want_fixed)
        if want_fixed != have_fixed:                          # backend TYPE changed -> rebuild (restarts at t=0)
            self.select_scenario(self._current_idx)
        self._topdown.set_ghost_visible(self._ghost_visible())
        self._redraw_series(self._src_probe, self._src_traj, self._src_ghost_traj)
        if self._ghost_visible() and self._cursor is not None:
            self._topdown.render_ghost_at(self._src_ghost_traj, self._cursor)

    def _on_nfrac_changed(self, value):
        self._nfrac_lbl.setText(f"nfrac={value}")
        gb = getattr(self, "loop", None) and self.loop.ghost.backend
        if isinstance(gb, FixedPointBackend):
            gb.nfrac = value                                  # live: evolves forward, no rebuild
        if getattr(self, "loop", None) is not None:
            self._redraw_series(self._src_probe, self._src_traj, self._src_ghost_traj)
```

> **Init-order check:** `_ghost_mode`/`_nfrac_slider` are built in the controls block (was 141), which runs *before* the first `select_scenario` in `__init__`, so `:519`'s `self._ghost_mode.currentText()` is safe. The two handlers guard on `self.loop` so the `currentIndexChanged` that may fire while `addItems`/`setCurrentIndex` runs during construction is a no-op. Verify by running the smoke suite (Step 4); if construction order differs, move the connects to just after the first `select_scenario`.

- [ ] **Step 4: Run — expect the UI smoke file green.**

Run `tests/test_sim_ui_smoke.py` (Step 2 command). Expected: `PYTEST_EXIT=0`, all passed (the 5 retargeted + 2 new).

- [ ] **Step 5: Commit.**

```bash
git add sim/ui/app.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim-ui): selettore ghost 3 stati [nessuno|Oracolo|Fixed-point] + slider nfrac"
```

---

## Task 5: Full suite, invariants, render-verify, docs, push

**Files:** none new — verification + docs.

- [ ] **Step 1: Full suite green.**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest \
  tests/test_sim_*.py tests/test_champion_io.py -p no:cacheprovider > "$OUT" 2>&1; echo "PYTEST_EXIT=$?"
```
Read `$OUT`. Expected: `PYTEST_EXIT=0`, **N + (new fixed_backend tests) + 2 (ui selector)** passed — with N = the number recorded at T1 Step 0 (399). The new file adds 11 collected (3 EventProp run, not skipped — the champion is present). `timeout ≥ 420s` or run in background.

- [ ] **Step 2: Invariants — the frozen core has an EMPTY diff.**

```bash
git diff --stat <BASE>..HEAD -- core/ sim/state.py sim/stepper.py sim/backend.py \
  sim/eventprop_stepper.py sim/probe.py sim/events.py utils/closed_loop_eval.py
```
(`<BASE>` = the commit recorded at T1 Step 0.) Expected: **no output** (empty). If anything prints, a frozen file was touched — revert that hunk; the fixed path must reuse `po2_quantize`/the stepper from outside, never edit them.

- [ ] **Step 3: Render-verify the selector + slider (real dark theme).**

Write `…/scratchpad/render_a7.py`:
```python
import os, sys
os.environ["QT_QPA_PLATFORM"] = "windows"
REPO = r"D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator"
SP = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, REPO)
from PySide6.QtWidgets import QApplication
from sim.ui.theme import apply_dark_theme
from sim.ui.app import SimApp
app = QApplication.instance() or QApplication([]); apply_dark_theme(app)
win = SimApp(os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt"))
win._ghost_mode.setCurrentText("Fixed-point"); app.processEvents()
print("mode:", win._ghost_mode.currentText(), "| slider on:", win._nfrac_slider.isEnabled(),
      "| nfrac:", win._nfrac_slider.value(), "| backend:", type(win.loop.ghost.backend).__name__)
win.resize(1400, 200); win.show(); app.processEvents()
win.grab().save(os.path.join(SP, "a7_selector.png")); print("saved")
```
Run it (env python, `QT_QPA_PLATFORM=windows`). Confirm stdout: `mode: Fixed-point | slider on: True | nfrac: 13 | backend: FixedPointBackend`. Read the PNG — the `ghost` combo shows "Fixed-point", the `nfrac=13` label and slider are present and enabled (not greyed). Send it to the user.

- [ ] **Step 4: Docs.**

Update `document/SIMULATOR_SESSION_RESUME.md` — the top **§DOVE SIAMO** (Action 7 done: live fixed-point twin, selector + nfrac slider, both families, N+ tests green, core frozen) and **§AZIONI PENDENTI** (next: Approach B — full Qm.n datapath — kept in reserve; merge Simulator→main still parked). Add a short **"Fixed-point twin"** paragraph to `document/SIMULATOR_ARCHITECTURE.md` (the `FixedPointBackend` reuses the `NetworkBackend` seam; approach A = weight+state quant; B is future).

```bash
git add document/SIMULATOR_SESSION_RESUME.md document/SIMULATOR_ARCHITECTURE.md
git commit -m "docs(sim): Azione 7 chiusa -- il gemello fixed-point live (selettore + slider nfrac)"
```

- [ ] **Step 5: Push (branch only — NO merge to main).**

```bash
git push origin Simulator      # pushes b53bcd4d (spec) + the spec fix + T1..T5
```
Confirm `git status` is clean and `git log --oneline @{u}..HEAD` is empty afterwards. **Do not merge to main** — that stays parked per the track's standing decision.

---

## Self-review (checklist run against the spec)

- **Spec coverage:** §q → T1. §Architecture/family dispatch → T2 (baseline) + T3 (EventProp). §quantization three points → weights T3 `_requantize_weights` / baseline no-op noted; state T2 `_FixedBaseline.step` + T3 tick loop; readout T2 `FixedPointBackend.infer`. §state isolation → T2 baseline deepcopy test + T3 EventProp independent-state test. §UI three-state + slider → T4. §Testing 1-7 → q (T1), contract (T2/T3), isolation (T2/T3), ⭐monotonicity (T2), nfrac-mutable (T2 output + T3 weights), selector wiring (T4), invariants (T5). All covered.
- **Placeholder scan:** none — every code step is complete; the T1 Step 4 note about the temporary import comment is an execution instruction, not a placeholder.
- **Type consistency:** `FixedPointBackend(model, nfrac=…)`, `.nfrac` property, `.infer→(1,5)`, `._engine.step(obs)`, `_engine.nfrac` setter — consistent across T2/T3/T4. `q(x,m,n)` torch throughout. `_ghost_mode`/`_nfrac_slider`/`_ghost_visible`/`_on_ghost_mode_changed`/`_on_nfrac_changed` consistent across app.py edits and the smoke tests.
- **Known execution risks flagged:** the ⭐ monotonicity strict `>` (T2 Step 4 — lengthen the sequence, never weaken to `>=`); the init-order/handler-guard (T4 Step 3 note); the copied tick loop kept in lockstep with the frozen stepper (T3 docstring).
