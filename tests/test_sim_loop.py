import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion   # noqa: E402
from utils.closed_loop_eval import simulate   # noqa: E402
from sim.backend import SoftwareBackend       # noqa: E402
from sim.events import EventInjector          # noqa: E402
from sim.stepper import SimStepper            # noqa: E402
from sim.probe import AttributeProbe          # noqa: E402
from sim.ui.loop import SimLoop               # noqa: E402
from sim.ui.trajectory import TrajectoryBuffer   # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def _loop(N=60):
    pg = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
    vl = np.full(N, 20.0)
    stepper = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, 25.0, 20.0)
    probe = AttributeProbe(capacity=100)
    return SimLoop(stepper, probe, dt_fixed=0.1), stepper, probe


def test_loop_accumulates_fixed_steps_and_records_probe():
    loop, stepper, probe = _loop()
    r = loop.tick(0.35)                    # 0.35 -> 3 fixed steps (rem ~0.05)
    assert len(r) == 3 and stepper.st.t == 3 and len(probe.frames()) == 3
    assert loop.tick(0.02) == []           # rem ~0.07 < 0.1 -> 0 steps
    assert len(loop.tick(0.05)) == 1       # rem ~0.12 -> 1 step


def test_loop_reports_done_and_never_overruns_N():
    loop, stepper, probe = _loop(N=10)
    loop.tick(100.0)                       # far more than 10 steps of budget
    assert stepper.st.t <= 10
    assert loop.done is True
    assert loop.tick(100.0) == []          # done -> no further steps


# ---- oracle ghost (SimStepper with backend=None) -------------------------------------------------

def _pair(N=60, injector=None):
    """Net stepper + oracle stepper on the same scenario, sharing one injector."""
    pg = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
    vl = np.full(N, 20.0)
    net = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, 25.0, 20.0,
                     injector=injector)
    ghost = SimStepper(None, pg, vl, 25.0, 20.0, injector=injector)
    gtraj = TrajectoryBuffer(capacity=N + 1)
    loop = SimLoop(net, AttributeProbe(capacity=100), dt_fixed=0.1,
                   ghost=ghost, ghost_traj=gtraj)
    return loop, net, ghost, gtraj


def test_loop_advances_ghost_once_per_net_step():
    loop, net, ghost, gtraj = _pair()
    loop.tick(0.35)                       # 3 fixed steps
    assert net.st.t == 3
    assert ghost.st.t == 3                # lockstep: never behind, never ahead
    assert len(gtraj) == 3


def test_loop_ghost_is_bit_identical_to_oracle_simulate():
    """The ghost driven through SimLoop must equal the validated oracle rollout, bit for bit."""
    N = 60
    loop, net, ghost, gtraj = _pair(N=N)
    loop.tick(100.0)                      # run the whole episode
    ref = simulate(None, np.array([30.0, 1.5, 2.0, 1.5, 1.5]), np.full(N, 20.0), 25.0, 20.0)
    got = gtraj.arrays()
    for k in ("s", "v", "vl", "dv", "a_ego"):
        np.testing.assert_array_equal(got[k], ref[k][:got[k].size])


def test_loop_ghost_and_net_see_the_same_leader_even_with_a_brake():
    """TEETH: the whole comparison is a lie if the two steppers ever see different leaders.
    Fails if the injector is duplicated per stepper, or if the ghost is stepped out of phase.
    The net's leader series comes from the StepResults tick() already returns -- no test-only
    bookkeeping inside SimLoop."""
    inj = EventInjector()
    loop, net, ghost, gtraj = _pair(N=60, injector=inj)
    seen = loop.tick(2.0)                        # 20 steps
    inj.enqueue(net.st.t, "brake_leader", target_v=5.0, duration=10)
    seen = seen + loop.tick(4.0)                 # 40 more steps, through the ramp
    net_vl = np.array([r.vl for r in seen], dtype=float)
    np.testing.assert_array_equal(gtraj.arrays()["vl"], net_vl)
    assert net_vl.min() < 20.0                   # the brake really happened (guards a vacuous pass)


def test_loop_without_ghost_is_unchanged():
    """Regression: default args must reproduce today's behaviour exactly."""
    pg = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
    vl = np.full(60, 20.0)
    net = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, 25.0, 20.0)
    loop = SimLoop(net, AttributeProbe(capacity=100), dt_fixed=0.1)
    r = loop.tick(0.35)
    assert len(r) == 3 and net.st.t == 3
    assert loop.ghost is None and loop.ghost_traj is None
