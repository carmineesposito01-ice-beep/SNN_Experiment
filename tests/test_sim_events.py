import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.events import EventInjector  # noqa: E402


def test_brake_leader_ramps_then_holds():
    inj = EventInjector()
    inj.enqueue(tick=2, verb="brake_leader", target_v=10.0, duration=4)
    base = 20.0
    got = [inj.tick(t, base) for t in range(8)]
    assert got[0] == 20.0 and got[1] == 20.0        # before trigger: base
    assert got[2] == 20.0                            # t0: ramp start = captured base
    assert got[4] == 15.0                            # halfway (frac 2/4): 20 + (10-20)*0.5
    assert got[6] == 10.0                            # t0+duration: target
    assert got[7] == 10.0                            # holds


def test_same_tick_drain_is_insertion_ordered():
    inj = EventInjector()
    inj.enqueue(tick=0, verb="brake_leader", target_v=15.0, duration=0)
    inj.enqueue(tick=0, verb="brake_leader", target_v=5.0, duration=0)    # later wins
    assert inj.tick(0, 20.0) == 5.0


def test_unknown_verb_raises():
    inj = EventInjector()
    inj.enqueue(tick=0, verb="teleport")
    with pytest.raises(ValueError):
        inj.tick(0, 20.0)


# --- integration with SimStepper (Task 3) ---
import numpy as np                                          # noqa: E402
from utils.champion_io import load_champion                 # noqa: E402
from utils.closed_loop_eval import simulate                 # noqa: E402
from sim.backend import SoftwareBackend                     # noqa: E402
from sim.stepper import SimStepper                          # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def _scn():
    return np.array([30.0, 1.5, 2.0, 1.5, 1.5]), np.full(60, 20.0), 25.0, 20.0


def test_injector_none_is_bit_identical_to_simulate():
    pg, vl, s0, v0 = _scn()
    ref = simulate(load_champion(CHAMP).model, pg, vl, s0, v0)
    got = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0,
                     injector=None).run()
    for k in ("s", "v", "vl", "dv", "a_ego", "params"):
        np.testing.assert_array_equal(got[k], ref[k])


def test_brake_leader_changes_trajectory_deterministically():
    pg, vl, s0, v0 = _scn()

    def run_once():
        inj = EventInjector()
        inj.enqueue(tick=20, verb="brake_leader", target_v=5.0, duration=10)
        return SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0,
                          injector=inj).run()

    a, b = run_once(), run_once()
    baseline = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0).run()
    for k in ("vl", "v", "s"):
        np.testing.assert_array_equal(a[k], b[k])          # reproducible
    assert not np.array_equal(a["vl"], baseline["vl"])      # the brake actually changed the leader


# --- the ramp bug: a second brake must not teleport the leader ---
def test_two_sequential_brakes_do_not_teleport_the_leader():
    """TEETH. The ramp captured the RAW v_leader[t] instead of the leader's current effective
    speed, so a second brake restarted from 21 m/s while the leader was doing 5: measured, a
    +16.00 m/s jump in one tick (~160 m/s^2). Assert the jump, not a label."""
    inj = EventInjector()
    inj.enqueue(tick=50, verb="brake_leader", target_v=5.0, duration=10)
    inj.enqueue(tick=200, verb="brake_leader", target_v=2.0, duration=20)
    vl = np.array([inj.tick(t, 21.0) for t in range(300)])

    jumps = np.abs(np.diff(vl))
    assert jumps.max() < 21.0 * 0.1, f"leader teleported by {jumps.max():.2f} m/s in one tick"
    assert vl[200] <= vl[199] + 1e-9, "the second brake restarted ABOVE the current speed"
    assert abs(vl[199] - 5.0) < 1e-9 and abs(vl[-1] - 2.0) < 1e-9    # both brakes still work


def test_second_brake_ramps_from_the_current_speed():
    inj = EventInjector()
    inj.enqueue(tick=0, verb="brake_leader", target_v=10.0, duration=10)
    inj.enqueue(tick=20, verb="brake_leader", target_v=0.0, duration=10)
    got = [inj.tick(t, 20.0) for t in range(40)]
    assert abs(got[20] - 10.0) < 1e-9        # starts from 10 (where it was), not from 20 (raw)
    assert abs(got[25] - 5.0) < 1e-9         # halfway down from 10, not from 20
    assert abs(got[30] - 0.0) < 1e-9
