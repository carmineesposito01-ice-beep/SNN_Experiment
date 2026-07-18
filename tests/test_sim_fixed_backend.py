import math
import os
import sys

import pytest
import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion               # noqa: E402
from sim.backend import SoftwareBackend                    # noqa: E402
from sim.fixed_backend import q, FixedPointBackend          # noqa: E402
from sim.eventprop_stepper import EventPropStepper          # noqa: E402

CHAMP_BASELINE = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")
CHAMP_EVENTPROP = os.path.join(REPO, "champions", "PE_t05_gp0002", "best_model.pt")


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
    with torch.no_grad():                                      # inference only; also silences the grad-scalar warning
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

def test_twin_builds_after_the_live_net_has_stepped():
    """Pins _safe_deepcopy explicitly: once the live net has run un-guarded, cell.potential is a
    NON-leaf tensor, and a plain copy.deepcopy(model) raises RuntimeError ('Only Tensors created
    explicitly by the user ... support the deepcopy protocol'). Constructing the twin here must
    NOT raise. A regression to plain copy.deepcopy fails this test instead of only crashing live."""
    model = load_champion(CHAMP_BASELINE).model
    sb = SoftwareBackend(model); sb.reset()
    obs = torch.tensor([[0.4, 0.3, 0.5, 0.3]], dtype=torch.float32)
    for _ in range(3):
        sb.infer(obs)                                          # un-guarded forward -> state goes non-leaf
    assert not model.layer_hidden.cell.potential.is_leaf       # precondition: the state IS non-leaf now
    be = FixedPointBackend(model, nfrac=13); be.reset()        # plain copy.deepcopy would RuntimeError here
    assert tuple(be.infer(obs).shape) == (1, 5)

def test_lower_nfrac_diverges_more_from_float_baseline():     # the central proof (state-driven)
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
