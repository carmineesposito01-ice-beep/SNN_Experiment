import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion   # noqa: E402
from sim.backend import SoftwareBackend       # noqa: E402
from sim.stepper import SimStepper            # noqa: E402
from sim.events import EventInjector          # noqa: E402
from sim.replay import ReplayLog              # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def _scn():
    return np.array([30.0, 1.5, 2.0, 1.5, 1.5]), np.full(60, 20.0), 25.0, 20.0


def test_replay_reruns_bit_identical():
    pg, vl, s0, v0 = _scn()
    inj = EventInjector()
    inj.enqueue(tick=20, verb="brake_leader", target_v=5.0, duration=10)
    orig = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0,
                      injector=inj).run()
    log = ReplayLog.from_injector(seed=0, injector=inj)
    rerun = SimStepper(SoftwareBackend(load_champion(CHAMP).model), pg, vl, s0, v0,
                       injector=log.build_injector()).run()
    for k in ("s", "v", "vl", "dv", "a_ego", "params"):
        np.testing.assert_array_equal(orig[k], rerun[k])


def test_replaylog_json_roundtrips():
    inj = EventInjector()
    inj.enqueue(tick=3, verb="brake_leader", target_v=8.0, duration=5)
    log = ReplayLog.from_injector(seed=7, injector=inj)
    back = ReplayLog.from_json(log.to_json())
    assert back.seed == 7
    assert back.events == [{"tick": 3, "verb": "brake_leader",
                            "params": {"target_v": 8.0, "duration": 5}}]
