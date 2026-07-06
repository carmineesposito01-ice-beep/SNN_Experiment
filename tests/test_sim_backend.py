import os
import sys

import pytest
import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion                          # noqa: E402
from sim.backend import SoftwareBackend, FpgaBackend, make_backend   # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def test_software_backend_infer_equals_forward_step():
    # Two fresh loads of the same champion -> deterministic, independent state.
    ref = load_champion(CHAMP).model
    ref.eval()
    ref.reset_state(1, "cpu")
    be = make_backend("software", model=load_champion(CHAMP).model)
    be.reset()
    obs = torch.tensor([[0.4, 0.3, 0.5, 0.3]], dtype=torch.float32)
    expected = ref.forward_step(obs)
    got = be.infer(obs)
    assert torch.equal(got, expected)          # bit-identical
    assert tuple(got.shape) == (1, 5)


def test_fpga_backend_is_stub():
    with pytest.raises(NotImplementedError):
        FpgaBackend()


def test_make_backend_rejects_unknown_and_missing_model():
    with pytest.raises(ValueError):
        make_backend("software")               # no model
    with pytest.raises(ValueError):
        make_backend("banana")
