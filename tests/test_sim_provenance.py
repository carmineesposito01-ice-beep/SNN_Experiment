"""The risk guardian: data/generator.py is the champions' training-data provenance, and 7b modifies it.

This does not compare TEXT (the live file is already 56 lines ahead of every archived copy -- the `launch`
profile, the `freeflow`/`launch` regimes, `_PHYS_BOUNDS`, `wide_params=False`; all additive, all default-off).
It compares OUTPUT: same seed -> the same dataset the champion was trained on, byte for byte. That is the
question that matters, and this makes it answerable instead of a matter of faith.

Both branches are covered: cut_in_ratio=None is config's 0.20 (which drew 0 cut-ins in 8 scenarios -- the first
run of this probe was incomplete until 1.0 forced the other branch)."""
import importlib.util
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import config                                     # noqa: E402,F401
from data.generator import generate_dataset       # noqa: E402

FROZEN = os.path.join(REPO, "Arch_Tested", "R24F_MIXED_lr0.5_V08_TRUE_CHAMPION", "data", "generator.py")


@pytest.fixture(scope="module")
def frozen():
    """The champion's archived generator, loaded under its own module name.

    It does `from config import ...`; `config` is already in sys.modules (imported above) so it binds to the
    LIVE one -- which is fine and deliberate: the archived config.py is byte-identical to the live one
    (verified), so the generator is the only moving part."""
    assert os.path.isfile(FROZEN), f"copia congelata assente: {FROZEN}"
    spec = importlib.util.spec_from_file_location("frozen_generator", FROZEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _same(a, b):
    return (np.array_equal(a["raw"], b["raw"]) and np.array_equal(a["x"], b["x"])
            and np.array_equal(a["y"], b["y"]) and np.array_equal(a["mask"], b["mask"])
            and a["params"] == b["params"]
            and (a["profile"], a["scenario"], a["cut_in"]) == (b["profile"], b["scenario"], b["cut_in"]))


@pytest.mark.parametrize("cut_in_ratio", [None, 1.0])
def test_the_live_generator_still_reproduces_the_champions_dataset(frozen, cut_in_ratio):
    n = 8
    live = generate_dataset(n, base_seed=42, cut_in_ratio=cut_in_ratio)
    froz = frozen.generate_dataset(n, base_seed=42, cut_in_ratio=cut_in_ratio)
    bad = [i for i in range(n) if not _same(live[i], froz[i])]
    assert bad == [], (f"la provenienza si e' MOSSA su {len(bad)}/{n} scenari (indici {bad}, "
                       f"cut_in_ratio={cut_in_ratio}): data/generator.py non produce piu' il dataset "
                       f"su cui i champion sono stati addestrati.")
