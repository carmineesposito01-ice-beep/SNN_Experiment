import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.backend import SoftwareBackend               # noqa: E402
from sim.probe import AttributeProbe                   # noqa: E402
from sim.stepper import SimStepper                     # noqa: E402
from sim.events import EventInjector                   # noqa: E402
from sim.replay import ReplayLog                       # noqa: E402
from sim.scenario import manual_scenario               # noqa: E402
from sim.ui.trajectory import TrajectoryBuffer         # noqa: E402
from sim.ui.reconstruct import reconstruct_history     # noqa: E402
from utils.champion_io import load_champion            # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")
_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


def _short_scenario(n=40):
    v_set = 0.7 * float(_PG[0])
    return manual_scenario(_PG, np.full(n, v_set),
                           s_init=float(_PG[2]) + v_set * float(_PG[1]), v_init=v_set)


def _live_run(champion, scenario, injector, n, capacity):
    backend = SoftwareBackend(champion.model)
    stepper = SimStepper.from_scenario(backend, scenario, injector=injector)
    probe = AttributeProbe(capacity=capacity)
    traj = TrajectoryBuffer(capacity=capacity)
    for _ in range(n):
        if stepper.st.collided or stepper.st.t >= stepper.N:
            break
        r = stepper.step()
        probe.record(r.t, backend.read_probe(), r.params)
        traj.record(r)
    return probe, traj


def test_reconstruct_bit_identical_to_live():
    champion = load_champion(CHAMP)
    scenario = _short_scenario(40)
    inj = EventInjector()
    inj.enqueue(5, "brake_leader", target_v=15.0, duration=10)   # mild brake, no collision in 40 ticks
    live_probe, live_traj = _live_run(champion, scenario, inj, n=40, capacity=40)
    rlog = ReplayLog.from_injector(0, inj)
    rprobe, rtraj = reconstruct_history(champion, scenario, rlog, upto=39)
    lf, rf = live_probe.frames(), rprobe.frames()
    assert len(lf) >= 1 and len(rf) == len(lf)
    for a, b in zip(lf, rf):
        assert a.t == b.t
        np.testing.assert_array_equal(a.spikes, b.spikes)
        np.testing.assert_array_equal(a.v_mem, b.v_mem)
        np.testing.assert_array_equal(a.v_th_eff, b.v_th_eff)
        np.testing.assert_array_equal(a.params, b.params)
        np.testing.assert_array_equal(a.input, b.input)
    np.testing.assert_array_equal(live_traj.arrays()["s"], rtraj.arrays()["s"])


def test_reconstruct_respects_upto():
    champion = load_champion(CHAMP)
    scenario = _short_scenario(40)
    rlog = ReplayLog.from_injector(0, EventInjector())
    rprobe, rtraj = reconstruct_history(champion, scenario, rlog, upto=9)
    assert len(rprobe.frames()) == 10 and len(rtraj) == 10
