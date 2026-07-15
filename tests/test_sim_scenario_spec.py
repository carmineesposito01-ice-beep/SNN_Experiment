import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from config import DT                                                          # noqa: E402
from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec, materialise    # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
NORMALE = LeaderStyle(a_max=2.0, b_max=4.0)


def _spec(blocks, style=NORMALE, v_init=21.0):
    return ScenarioSpec(name="test", blocks=tuple(blocks), style=style,
                        s_init=33.5, v_init=v_init)


def test_const_block_holds_after_reaching_the_value():
    sc = materialise(_spec([Block("const", 100, {"v": 21.0})]), _PG, N=100)
    assert sc.v_leader.shape == (100,)
    np.testing.assert_allclose(sc.v_leader, 21.0)


def test_ramp_uses_the_style_rate_and_then_holds():
    """The ramp's slope is b_max, and `ticks` is the SLOT: once it arrives it holds for the rest."""
    sc = materialise(_spec([Block("ramp", 200, {"to_v": 2.0})]), _PG, N=200)
    vl = sc.v_leader
    assert vl[0] < 21.0                                        # already moving on tick 0
    # 21 -> 2 at b_max=4 m/s^2 takes 19/4 = 4.75 s = 47.5 ticks at DT=0.1
    n_ramp = int(np.ceil(19.0 / 4.0 / DT))
    assert abs(vl[n_ramp] - 2.0) < 1e-6                        # arrived
    np.testing.assert_allclose(vl[n_ramp:], 2.0)               # and holds for the rest of the slot
    dv = np.diff(vl[:n_ramp])
    assert np.all(dv >= -4.0 * DT - 1e-9)                      # never steeper than the style


def test_blocks_chain_from_where_the_previous_left_off():
    sc = materialise(_spec([Block("ramp", 30, {"to_v": 2.0}),       # slot too short to arrive
                            Block("const", 70, {"v": 2.0})]), _PG, N=100)
    vl = sc.v_leader
    assert vl[29] > 2.0                                         # cut mid-ramp, as designed
    assert abs(vl[30] - (vl[29] - 4.0 * DT)) < 1e-6             # next block continues from there
    assert abs(vl[-1] - 2.0) < 1e-6                             # and gets there


def test_materialise_is_pure_and_reproducible():
    s = _spec([Block("ramp", 100, {"to_v": 5.0}), Block("const", 100, {"v": 5.0})])
    np.testing.assert_array_equal(materialise(s, _PG, N=200).v_leader,
                                  materialise(s, _PG, N=200).v_leader)


def test_materialise_returns_a_scenario_the_stepper_can_run():
    from sim.stepper import SimStepper
    sc = materialise(_spec([Block("const", 60, {"v": 21.0})]), _PG, N=60)
    st = SimStepper.from_scenario(None, sc)                     # backend=None -> the oracle, no net needed
    for _ in range(60):
        if st.st.collided or st.st.t >= st.N:
            break
        st.step()
    assert st.st.t == 60                                        # it really is a runnable Scenario
