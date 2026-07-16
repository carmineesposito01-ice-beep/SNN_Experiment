import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from config import DT                                    # noqa: E402
from sim.scenario import scenario_library                # noqa: E402
from sim.stepper import SimStepper                       # noqa: E402
from sim.scenario_export import (                        # noqa: E402
    leader_kinematics, write_scenario_csv, write_scenario_mat)

_PG = np.array([30.0, 1.5, 5.0, 1.5, 2.0])               # v0, T, s0, a, b -- a reasonable IDM point


def test_leader_kinematics_shapes_and_formulas():
    sc = scenario_library(_PG, N=50)[0]                  # 'following'
    k = leader_kinematics(sc, DT)
    v = np.asarray(sc.v_leader, float)
    assert np.allclose(k["t"], np.arange(v.size) * DT)
    assert np.allclose(k["v_leader"], v)
    assert k["x_leader"][0] == sc.s_init                 # starts at the initial gap
    assert np.allclose(k["a_leader"], np.diff(v, prepend=v[0]) / DT)


def test_x_leader_reproduces_the_stepper_gap():
    sc = scenario_library(_PG, N=100)[0]                 # 'following': no collision
    stepper = SimStepper.from_scenario(None, sc)         # oracle
    res = [stepper.step() for _ in range(sc.v_leader.size)]
    s = np.array([r.s for r in res])                     # gap at each tick (pre-update)
    v_ego = np.array([r.v for r in res])                 # ego speed (pre-update)
    x_leader = leader_kinematics(sc, DT)["x_leader"]
    # integrate the ego with the SAME forward-Euler rule the stepper uses (x_ego[0]=0)
    x_ego = DT * np.concatenate(([0.0], np.cumsum(v_ego[1:])))
    assert np.allclose(x_leader - x_ego, s, atol=1e-6)   # gap == x_leader - x_ego, faithfully


def test_csv_roundtrips_the_four_columns(tmp_path):
    sc = scenario_library(_PG, N=40)[0]
    p = str(tmp_path / "s.csv")
    write_scenario_csv(sc, p, DT)
    with open(p) as f:
        rows = [ln for ln in f if not ln.startswith("#")]   # drop the metadata comment lines
    data = np.genfromtxt(rows, delimiter=",", names=True)    # first remaining line = the column header
    k = leader_kinematics(sc, DT)
    assert np.allclose(data["v_leader"], k["v_leader"])
    assert np.allclose(data["x_leader"], k["x_leader"])
    assert np.allclose(data["a_leader"], k["a_leader"])


def test_mat_export_writes_the_name_and_arrays(tmp_path):
    from tests.test_sim_mat_writer import _read_mat
    sc = scenario_library(_PG, N=30)[0]
    p = str(tmp_path / "s.mat")
    write_scenario_mat(sc, p, DT)
    got = _read_mat(p)
    assert got["name"] == sc.name
    assert np.allclose(got["v_leader"].ravel(), np.asarray(sc.v_leader, float))
    assert np.allclose(got["params_gt"].ravel(), _PG)
