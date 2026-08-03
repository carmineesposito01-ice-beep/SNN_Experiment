import os
import sys

import numpy as np
import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion       # noqa: E402
from sim.eventprop_stepper import EventPropStepper  # noqa: E402
from sim.backend import SoftwareBackend            # noqa: E402

DONATELLO = os.path.join(REPO, "champions", "PE_t05_gp0002", "best_model.pt")   # eventprop_alif_full


def test_champion_is_eventprop():
    assert load_champion(DONATELLO).variant == "eventprop_alif_full"


def test_eventprop_stepper_matches_forward_sequence():
    model = load_champion(DONATELLO).model
    torch.manual_seed(0)
    T = 40
    x = torch.rand(1, T, 4)
    with torch.no_grad():
        ref = model.forward_sequence(x)                                  # (1, T, 5)
        stepper = EventPropStepper(model)
        stepper.reset(1, "cpu")
        got = torch.stack([stepper.step(x[:, t]) for t in range(T)], dim=1)  # (1, T, 5)
    maxdiff = (got - ref).abs().max().item()
    assert maxdiff < 1e-3, f"per-step diverges from forward_sequence: max|diff|={maxdiff}"


def test_eventprop_backend_infers_and_probes():
    model = load_champion(DONATELLO).model
    be = SoftwareBackend(model)
    be.reset()
    out = be.infer(torch.rand(1, 4))
    assert tuple(out.shape) == (1, 5) and torch.isfinite(out).all()
    p = be.read_probe()
    H = model.hidden_size
    assert p["spikes"].shape == (H,)
    assert set(np.unique(p["spikes"])).issubset({0.0, 1.0})
