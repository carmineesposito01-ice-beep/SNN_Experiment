import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.scenario_spec import (A_MAX_RANGE, B_MAX_RANGE, V_RANGE, Block, LeaderStyle,  # noqa: E402
                               ScenarioSpec)
from sim.jitter import jitter_params_gt, jitter_spec                                    # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


def _spec():
    return ScenarioSpec(
        name="x",
        blocks=(Block("const", 100, {"v": 15.0}),
                Block("ramp", 120, {"to_v": 25.0}),
                Block("sine", 140, {"amp": 3.0, "period": 60.0}),
                Block("custom", 80, {"nodes": (12.0, 18.0, 9.0)}),
                Block("preset", 200, {"name": "hard_brake"})),
        style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)


def test_same_seed_gives_an_identical_spec():
    a = jitter_spec(_spec(), np.random.default_rng(7), 0.3)
    b = jitter_spec(_spec(), np.random.default_rng(7), 0.3)
    assert a == b                                        # frozen dataclasses compare by value


def test_zero_strength_is_the_identity():
    s = _spec()
    assert jitter_spec(s, np.random.default_rng(1), 0.0) == s   # the degenerate case: jitter is the ONLY variation


def test_the_type_is_preserved_and_the_knobs_stay_in_range():
    s = _spec()
    j = jitter_spec(s, np.random.default_rng(3), 0.5)
    assert [b.kind for b in j.blocks] == [b.kind for b in s.blocks]      # a sine stays a sine
    assert all(b.ticks >= 1 for b in j.blocks)
    assert j.blocks[4].params["name"] == "hard_brake"                    # a preset has no numeric knob
    assert V_RANGE[0] <= j.blocks[0].params["v"] <= V_RANGE[1]
    assert V_RANGE[0] <= j.blocks[1].params["to_v"] <= V_RANGE[1]
    assert j.blocks[2].params["period"] > 0.0
    assert all(V_RANGE[0] <= v <= V_RANGE[1] for v in j.blocks[3].params["nodes"])
    assert A_MAX_RANGE[0] <= j.style.a_max <= A_MAX_RANGE[1]
    assert B_MAX_RANGE[0] <= j.style.b_max <= B_MAX_RANGE[1]


def test_a_nonzero_strength_actually_moves_something():
    s = _spec()
    j = jitter_spec(s, np.random.default_rng(3), 0.5)
    assert j != s                                        # otherwise the "identity" test above proves nothing


def test_params_gt_jitter_is_seeded_and_bounded():
    from data.generator import _PHYS_BOUNDS
    a = jitter_params_gt(_PG, np.random.default_rng(5), 0.2)
    b = jitter_params_gt(_PG, np.random.default_rng(5), 0.2)
    assert np.allclose(a, b)
    assert np.allclose(jitter_params_gt(_PG, np.random.default_rng(5), 0.0), _PG)   # identity at 0
    for i, k in enumerate(("v0", "T", "s0", "a", "b")):
        lo, hi = _PHYS_BOUNDS[k]
        assert lo <= a[i] <= hi
