import os
import sys

import numpy as np
import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion   # noqa: E402
from sim.backend import SoftwareBackend       # noqa: E402
from sim.probe import AttributeProbe          # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def test_read_probe_shapes_and_binary_spikes():
    champ = load_champion(CHAMP)
    be = SoftwareBackend(champ.model)
    be.reset()
    be.infer(torch.tensor([[0.4, 0.3, 0.5, 0.3]], dtype=torch.float32))
    p = be.read_probe()
    H = champ.topology["hidden"]
    assert p["spikes"].shape == (H,)
    assert p["v_mem"].shape == (H,)
    assert p["v_th_eff"].shape == (H,)
    assert set(np.unique(p["spikes"])).issubset({0.0, 1.0})
    assert (p["v_th_eff"] > 0).all()


def test_probe_ringbuffer_capacity():
    pr = AttributeProbe(capacity=5, sample_every=1)
    for t in range(10):
        pr.record(t, {"spikes": np.zeros(3), "v_mem": np.zeros(3), "v_th_eff": np.ones(3)},
                  np.zeros(5))
    assert len(pr.frames()) == 5
    assert pr.frames()[0].t == 5           # kept the last 5


def test_probe_sample_every():
    pr = AttributeProbe(capacity=100, sample_every=2)
    for t in range(10):
        pr.record(t, {"spikes": np.zeros(3), "v_mem": np.zeros(3), "v_th_eff": np.ones(3)},
                  np.zeros(5))
    assert [f.t for f in pr.frames()] == [0, 2, 4, 6, 8]
    assert pr.spikes_matrix().shape == (5, 3)
