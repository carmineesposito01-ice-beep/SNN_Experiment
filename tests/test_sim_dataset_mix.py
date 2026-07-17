import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.dataset_mix import MixEntry, quotas, validate_mix   # noqa: E402


def test_quotas_are_exact_not_expected():
    mix = [MixEntry("built", "mine", 40.0), MixEntry("preset", "hard_brake", 30.0),
           MixEntry("generator", "stop_and_go", 30.0)]
    q = quotas(mix, 100)
    assert q == [40, 30, 30]                 # exactly, not "in expectation"
    assert sum(q) == 100


def test_largest_remainder_absorbs_the_leftovers():
    mix = [MixEntry("preset", "a", 1 / 3 * 100), MixEntry("preset", "b", 1 / 3 * 100),
           MixEntry("preset", "c", 1 / 3 * 100)]
    q = quotas(mix, 100)
    assert sum(q) == 100                      # no trajectory lost to rounding
    assert sorted(q) == [33, 33, 34]


def test_validate_rejects_a_total_that_is_not_100():
    with pytest.raises(ValueError):
        validate_mix([MixEntry("preset", "a", 60.0), MixEntry("preset", "b", 30.0)])
    validate_mix([MixEntry("preset", "a", 60.0), MixEntry("preset", "b", 40.0)])   # ok, no raise


def test_validate_rejects_an_empty_mix_and_a_bad_family():
    with pytest.raises(ValueError):
        validate_mix([])
    with pytest.raises(ValueError):
        validate_mix([MixEntry("nonsense", "a", 100.0)])
