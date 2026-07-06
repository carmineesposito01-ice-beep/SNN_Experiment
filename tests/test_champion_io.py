"""Smoke test for utils.champion_io — the shared champion loader (anti-§9.4).

For every versioned champion in champions/ it verifies:
  1. detect_family() returns the documented variant (from the state-dict signature);
  2. load_champion() strict-loads it (no missing/unexpected keys) — the §9.4 guard;
  3. the reconstructed model runs forward_sequence() -> finite (B, T, 5) output.

No val_loss golden: the champion .pt stores a composite (lambda-weighted) val_loss whose
training config is not in the file, so exact reproduction is out of scope. strict=True
loading + a finite forward IS the correctness proof for "did we rebuild the right net".
"""
import os
import sys

import pytest
import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import detect_family, load_champion  # noqa: E402

# Documented champion -> variant mapping (Eval_v3 / Eval_FPGA notebooks, EVENTPROP_STATUS).
CHAMPIONS = [
    ("A_lr1e2_t06_r16", "eventprop_alif_full"),        # Michelangelo
    ("PE_t05_gp0002", "eventprop_alif_full"),          # Donatello
    ("LS3_PEAK_R0_launch_d03", "baseline"),
    ("R33_C2_A1_T12_fix", "baseline"),
]


def _champ_path(name):
    return os.path.join(REPO, "champions", name, "best_model.pt")


def _state_dict(name):
    ckpt = torch.load(_champ_path(name), map_location="cpu", weights_only=False)
    return ckpt["model_state"]


@pytest.mark.parametrize("name,expected_variant", CHAMPIONS)
def test_detect_family(name, expected_variant):
    assert detect_family(_state_dict(name)) == expected_variant


@pytest.mark.parametrize("name,expected_variant", CHAMPIONS)
def test_load_champion_strict_and_forward(name, expected_variant):
    handle = load_champion(_champ_path(name))
    assert handle.variant == expected_variant
    B, T = 2, 8
    x = torch.rand(B, T, handle.topology["input"])
    with torch.no_grad():
        out = handle.model.forward_sequence(x)
    assert out.shape == (B, T, handle.topology["output"])
    assert torch.isfinite(out).all()


def test_unknown_family_raises():
    with pytest.raises(ValueError):
        detect_family({"foo.bar": torch.zeros(1)})
