"""The training mix: one row = one sentence -- "this leader, params from this regime, this weight".

The two axes are orthogonal by construction. In the real generator `_sample_scenario` derives BOTH the params
and the leader profile from the regime; injecting a v_leader overrides the profile half and leaves the params
half -- which is the half that matters here, because in a training set the params ARE the labels.

cut_in is a FAMILY, not a global ratio. Three reasons, in order: quotas() gives exactly 20 of 100 where the
generator's `rng.random() < 0.20` gives 20 in expectation; a row you can see beats a dice roll you cannot; and
it keeps ONE injection site, which is what we want anyway -- a cut-in replaces the leader from t_cutin on, so
injecting a designed profile there would throw most of it away."""
from dataclasses import dataclass

from sim.dataset_mix import quotas as _quotas
from sim.dataset_mix import validate_mix as _validate_families

FAMILIES_TRAIN = ("built", "preset", "generator", "cut_in")
REGIMES = ("highway", "urban", "truck", "mixed", "freeflow", "launch")


@dataclass(frozen=True)
class TrainMixEntry:
    family: str      # one of FAMILIES_TRAIN
    source: str      # a built name | a preset name | a leader profile (generator, and cut_in's leader A)
    regime: str      # one of REGIMES -- gives the params, i.e. THE LABELS
    weight: float    # percent; the mix must total 100


def validate_train_mix(mix):
    """Family + weights via 7a's arithmetic; the regime is 7b's own axis."""
    _validate_families(mix, FAMILIES_TRAIN)
    for e in mix:
        if e.regime not in REGIMES:
            raise ValueError(f"regime sconosciuto: {e.regime!r} (validi: {REGIMES})")


def train_quotas(mix, count):
    """Exact per-row counts summing to `count`."""
    validate_train_mix(mix)
    return _quotas(mix, count, FAMILIES_TRAIN)
