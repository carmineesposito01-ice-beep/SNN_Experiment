import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion   # noqa: E402
from sim.backend import SoftwareBackend       # noqa: E402
from sim.stepper import SimStepper            # noqa: E402
from sim.probe import AttributeProbe          # noqa: E402
from sim.ui.loop import SimLoop               # noqa: E402

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
