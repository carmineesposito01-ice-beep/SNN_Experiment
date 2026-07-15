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
from sim.ui.loop import SimLoop                        # noqa: E402
from sim.ui.trajectory import TrajectoryBuffer         # noqa: E402
from sim.ui.reconstruct import reconstruct_history, reconstruct_spliced   # noqa: E402
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
    rprobe, rtraj, _ = reconstruct_history(champion, scenario, rlog, upto=39)
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
    rprobe, rtraj, rghost = reconstruct_history(champion, scenario, rlog, upto=9)
    assert len(rprobe.frames()) == 10 and len(rtraj) == 10
    assert len(rghost) == 10                     # the ghost honours `upto` too


def test_reconstruct_spliced_equals_full():
    # prefix-splice (re-run only pre-buffer ticks + reuse the live buffer) must be bit-identical
    champion = load_champion(CHAMP)
    scenario = _short_scenario(40)
    inj = EventInjector()
    inj.enqueue(5, "brake_leader", target_v=15.0, duration=10)
    live_probe, live_traj = _live_run(champion, scenario, inj, n=40, capacity=12)   # buffer wraps -> holds last 12
    assert len(live_probe.frames()) == 12 and live_probe.frames()[-1].t == 39
    rlog = ReplayLog.from_injector(0, inj)
    full_p, full_t, full_g = reconstruct_history(champion, scenario, rlog, upto=39)
    spl_p, spl_t, spl_g = reconstruct_spliced(champion, scenario, rlog, 39, live_probe, live_traj)
    fp, sp = full_p.frames(), spl_p.frames()
    assert len(sp) == len(fp) == 40
    for a, b in zip(fp, sp):
        assert a.t == b.t
        np.testing.assert_array_equal(a.spikes, b.spikes)
        np.testing.assert_array_equal(a.v_mem, b.v_mem)
        np.testing.assert_array_equal(a.v_th_eff, b.v_th_eff)
        np.testing.assert_array_equal(a.params, b.params)
        np.testing.assert_array_equal(a.input, b.input)
    np.testing.assert_array_equal(full_t.arrays()["s"], spl_t.arrays()["s"])
    np.testing.assert_array_equal(full_t.arrays()["a_ego"], spl_t.arrays()["a_ego"])
    np.testing.assert_array_equal(full_g.arrays()["s"], spl_g.arrays()["s"])   # ghost: same either way


def test_reconstruct_spliced_falls_back_when_tail_mismatch():
    # if the live tail does not reach `upto`, splice must fall back to a full reconstruct
    champion = load_champion(CHAMP)
    scenario = _short_scenario(40)
    rlog = ReplayLog.from_injector(0, EventInjector())
    live_probe, live_traj = _live_run(champion, scenario, EventInjector(), n=20, capacity=12)  # tail t=19, not 39
    spl_p, _, spl_g = reconstruct_spliced(champion, scenario, rlog, 39, live_probe, live_traj)
    assert len(spl_p.frames()) == 40 and spl_p.frames()[-1].t == 39
    assert len(spl_g) == 40                      # the fallback path returns the ghost too


def test_reconstruct_returns_a_ghost_matching_the_live_ghost():
    """The reconstructed oracle must equal the live one on the overlap, or deep-scrub lies:
    the road would show a ghost from one timeline against a net state from another."""
    champion = load_champion(CHAMP)
    scenario = _short_scenario(40)
    inj = EventInjector()
    inj.enqueue(5, "brake_leader", target_v=15.0, duration=10)
    net = SimStepper.from_scenario(SoftwareBackend(champion.model), scenario, injector=inj)
    ghost = SimStepper.from_scenario(None, scenario, injector=inj)
    gtraj = TrajectoryBuffer(capacity=41)
    loop = SimLoop(net, AttributeProbe(capacity=40), dt_fixed=0.1, ghost=ghost, ghost_traj=gtraj)
    loop.tick(100.0)

    _, _, rghost = reconstruct_history(champion, scenario, ReplayLog.from_injector(0, inj), 39)
    live, rec = gtraj.arrays(), rghost.arrays()
    n = min(live["t"].size, rec["t"].size)
    assert n == 40
    for k in ("s", "v", "vl", "dv", "a_ego"):
        np.testing.assert_array_equal(rec[k][:n], live[k][:n])


def test_reconstruct_spliced_also_returns_the_ghost():
    champion = load_champion(CHAMP)
    scenario = _short_scenario(40)
    inj = EventInjector()
    live_probe, live_traj = _live_run(champion, scenario, inj, n=40, capacity=12)
    rlog = ReplayLog.from_injector(0, inj)
    _, _, ghost = reconstruct_spliced(champion, scenario, rlog, 39, live_probe, live_traj)
    assert len(ghost.arrays()["t"]) == 40      # fully re-run, never spliced: it has no SNN forward
