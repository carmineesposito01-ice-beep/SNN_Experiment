import os, sys
import numpy as np
import pytest
from scipy.io import loadmat

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from scripts.export_champions import export_all, CHAMPIONS  # noqa: E402

OUT = os.path.join(REPO, "matlab", "champions_export.mat")


@pytest.fixture(scope="module")
def mat():
    export_all(OUT, n_test=16, seed=0)
    return loadmat(OUT, struct_as_record=False, squeeze_me=True)


def test_all_four_present(mat):
    champs = mat["champions"]
    names = {c.name for c in np.atleast_1d(champs)}
    assert names == {"Donatello", "Michelangelo", "Raffaello", "Leonardo"}


@pytest.mark.parametrize("name,rank", [("Donatello", 16), ("Michelangelo", 16),
                                       ("Raffaello", 8), ("Leonardo", 8)])
def test_topology_and_fields(mat, name, rank):
    c = {x.name: x for x in np.atleast_1d(mat["champions"])}[name]
    assert int(c.rank) == rank
    assert c.fc_weight.shape == (32, 4)
    assert c.rec_U.shape == (32, rank)
    assert c.rec_V.shape == (rank, 32)
    assert c.readout.shape == (5, 32)
    assert c.delays.shape == (32, 4)
    assert c.base_threshold.shape == (32,)
    assert c.leak_div.shape == (32,)
    assert c.x_phys.shape == (16, 4)
    assert c.x_norm.shape == (16, 4)
    assert c.y_params.shape == (16, 5)


def test_weights_are_po2(mat):
    c = np.atleast_1d(mat["champions"])[0]
    for W in (c.fc_weight, c.rec_U, c.rec_V, c.readout):
        nz = W[W != 0]
        k = np.log2(np.abs(nz))
        assert np.allclose(k, np.round(k)), "pesi non potenza-di-2"
        assert k.min() >= -4 - 1e-9 and k.max() <= 1 + 1e-9


def test_params_in_physical_bounds(mat):
    lo = np.array([8, 0.5, 1.0, 0.3, 0.5])
    hi = np.array([45, 2.5, 5.0, 2.5, 3.0])
    for c in np.atleast_1d(mat["champions"]):
        assert (c.y_params >= lo - 1e-3).all() and (c.y_params <= hi + 1e-3).all()
