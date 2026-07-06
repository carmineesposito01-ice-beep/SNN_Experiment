import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.state import SimState, StepResult  # noqa: E402


def test_simstate_defaults_are_independent():
    a, b = SimState(), SimState()
    a.pl_state["x"] = 1
    assert b.pl_state == {}          # default_factory, not shared
    assert a.t == 0 and a.collided is False


def test_stepresult_is_frozen():
    r = StepResult(t=0, s=25.0, v=20.0, vl=20.0, dv=0.0, a_ego=0.0,
                   params=np.zeros(5), collided=False)
    with pytest.raises(Exception):
        r.s = 1.0                    # frozen dataclass
