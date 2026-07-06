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
