import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion       # noqa: E402
from utils.closed_loop_eval import simulate       # noqa: E402
from sim.backend import SoftwareBackend           # noqa: E402
from sim.stepper import SimStepper                # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")
SERIES = ("s", "v", "vl", "dv", "a_ego", "params")


def _scenario():
    params_gt = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
    t = np.arange(60)
    v_leader = 20.0 + 3.0 * np.sin(0.1 * t)
    return params_gt, v_leader, 25.0, 20.0        # params_gt, v_leader, s_init, v_init


def test_stepper_sw_matches_simulate_bit_identical():
    pg, vl, s0, v0 = _scenario()
    ref = simulate(load_champion(CHAMP).model, pg, vl, s0, v0)
    got = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0).run()
    for k in SERIES:
        np.testing.assert_array_equal(got[k], ref[k])
    assert got["collided"] == ref["collided"]
    assert got["min_gap"] == ref["min_gap"]


def test_stepper_oracle_matches_simulate():
    pg, vl, s0, v0 = _scenario()
    ref = simulate(None, pg, vl, s0, v0)               # oracle (constant params_gt)
    got = SimStepper(None, pg, vl, s0, v0).run()        # backend=None -> oracle
    for k in SERIES:
        np.testing.assert_array_equal(got[k], ref[k])


def test_stepper_matches_simulate_with_plant_and_channel():
    pg, vl, s0, v0 = _scenario()
    plant = {"tau_act": 0.3, "jerk_max": 5.0}
    channel = {"pdr": 0.8, "latency_steps": 2, "seed": 7}
    ref = simulate(load_champion(CHAMP).model, pg, vl, s0, v0, plant=plant, channel=channel)
    got = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0,
                     plant=plant, channel=channel).run()
    for k in SERIES:
        np.testing.assert_array_equal(got[k], ref[k])
