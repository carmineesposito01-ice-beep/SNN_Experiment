import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.scenario import Scenario, scenario_library, manual_scenario  # noqa: E402


def test_library_has_five_named_scenarios():
    lib = scenario_library([30.0, 1.5, 2.0, 1.5, 1.5], N=200, rng=np.random.default_rng(0))
    names = [s.name for s in lib]
    assert names == ["following", "stop_and_go", "hard_brake", "cut_in", "sinusoidal"]
    for s in lib:
        assert s.v_leader.shape == (200,)
        assert isinstance(s.s_init, float) and isinstance(s.v_init, float)
    cut = next(s for s in lib if s.name == "cut_in")
    assert cut.cut_in is not None and len(cut.cut_in) == 2


def test_manual_scenario_roundtrips():
    vl = np.full(10, 20.0)
    s = manual_scenario([30.0, 1.5, 2.0, 1.5, 1.5], vl, 25.0, 20.0, cut_in=(5, 8.0))
    assert s.name == "manual" and s.cut_in == (5, 8.0)
    assert s.v_leader.shape == (10,) and s.s_init == 25.0
