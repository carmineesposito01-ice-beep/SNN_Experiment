"""The training sink: the 8-key dict train.py's CFDataset eats, built with the champions' real physics."""
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from config import IDM_HWY                                  # noqa: E402
from data.generator import simulate_trajectory              # noqa: E402


def test_an_injected_leader_lands_in_the_trajectory():
    """traj[:,3] IS v_l_true (generator.py:329). Without this check a v_leader silently ignored would give a
    plausible, wrong dataset -- the worst failure available here."""
    v = np.linspace(20.0, 10.0, 400).astype(np.float32)
    traj = simulate_trajectory(dict(IDM_HWY), profile="sinusoidal", seed=1, v_leader=v)
    assert traj.shape == (400, 7)                 # N follows the injected length, not SIM_DURATION/DT
    assert np.allclose(traj[:, 3], v)


def test_v_leader_none_is_exactly_not_passing_it():
    """The default path must not move: the kwarg is additive, not a behaviour change."""
    a = simulate_trajectory(dict(IDM_HWY), profile="sinusoidal", seed=7)
    b = simulate_trajectory(dict(IDM_HWY), profile="sinusoidal", seed=7, v_leader=None)
    assert np.array_equal(a, b)
