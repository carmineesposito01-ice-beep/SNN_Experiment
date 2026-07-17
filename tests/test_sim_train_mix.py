"""The training mix: (leader, labels, weight) in one row, with exact quotas."""
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.train_mix import FAMILIES_TRAIN, REGIMES, TrainMixEntry, train_quotas, validate_train_mix  # noqa: E402


def _mix():
    return [TrainMixEntry("built", "mine", "launch", 30.0),
            TrainMixEntry("generator", "sinusoidal", "highway", 50.0),
            TrainMixEntry("cut_in", "sinusoidal", "urban", 20.0)]


def test_cut_in_is_a_family_of_the_training_mix():
    """The user's call: cut-in is a ROW, not a hidden global ratio. quotas() gives exactly 20 of 100 where the
    generator's `rng.random() < 0.20` gives 20 in expectation."""
    assert "cut_in" in FAMILIES_TRAIN
    assert train_quotas(_mix(), 100) == [30, 50, 20]


def test_the_quotas_are_exact_even_when_they_do_not_divide():
    mix = [TrainMixEntry("generator", "constant", "highway", 100.0 / 3),
           TrainMixEntry("generator", "free", "freeflow", 100.0 / 3),
           TrainMixEntry("cut_in", "sinusoidal", "urban", 100.0 / 3)]
    q = train_quotas(mix, 100)
    assert sum(q) == 100 and sorted(q) == [33, 33, 34]


def test_an_unknown_regime_is_refused_by_name():
    with pytest.raises(ValueError, match="regime sconosciuto"):
        validate_train_mix([TrainMixEntry("generator", "constant", "autostrada", 100.0)])


def test_the_regimes_are_the_generators_own():
    assert REGIMES == ("highway", "urban", "truck", "mixed", "freeflow", "launch")


def test_the_7a_mix_is_untouched_by_the_families_parameter():
    """The additive default must leave 7a exactly as it was: cut_in is NOT an analysis family."""
    from sim.dataset_mix import MixEntry, validate_mix
    with pytest.raises(ValueError, match="famiglia sconosciuta"):
        validate_mix([MixEntry("cut_in", "sinusoidal", 100.0)])
