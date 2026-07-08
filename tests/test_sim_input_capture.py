import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest
import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.backend import SoftwareBackend           # noqa: E402
from sim.probe import AttributeProbe, ProbeFrame   # noqa: E402
from utils.champion_io import load_champion         # noqa: E402

BASELINE = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")
EVENTPROP = os.path.join(REPO, "champions", "PE_t05_gp0002", "best_model.pt")
IN_DIM = 4


def test_probeframe_input_optional():
    p = AttributeProbe(capacity=5)
    p.record(0, {"spikes": np.zeros(3), "v_mem": np.zeros(3), "v_th_eff": np.ones(3)}, np.zeros(5))
    assert p.frames()[-1].input is None                      # backward compatible (no "input")
    p.record(1, {"spikes": np.zeros(3), "v_mem": np.zeros(3), "v_th_eff": np.ones(3),
                 "input": np.array([0.1, 0.2, 0.3, 0.4])}, np.zeros(5))
    assert np.allclose(p.frames()[-1].input, [0.1, 0.2, 0.3, 0.4])


def test_baseline_backend_read_probe_has_input():
    b = SoftwareBackend(load_champion(BASELINE).model)
    b.reset()
    b.infer(torch.zeros(1, IN_DIM))
    d = b.read_probe()
    assert "input" in d and np.asarray(d["input"]).reshape(-1).shape[0] == IN_DIM


def test_eventprop_backend_read_probe_has_input():
    b = SoftwareBackend(load_champion(EVENTPROP).model)
    b.reset()
    b.infer(torch.zeros(1, IN_DIM))
    d = b.read_probe()
    assert "input" in d and np.asarray(d["input"]).reshape(-1).shape[0] == IN_DIM
