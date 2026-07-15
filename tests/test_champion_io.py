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


# ---- identity: naming every variant, refusing the unsupported ones BY NAME ----------------------

def test_name_signature_recognises_the_two_supported_families():
    from utils.champion_io import _name_signature
    from core.network import build_model
    for variant in ("baseline", "eventprop_alif_full"):
        name, supported, reason = _name_signature(build_model(variant).state_dict())
        assert name == variant and supported is True and reason is None


def test_name_signature_names_unsupported_variants_instead_of_calling_them_baseline():
    """Today attn/wta resolve to 'baseline' and are only saved by a torch RuntimeError about
    tensors; stacked_* raises a generic ValueError. Naming them is what makes an honest refusal
    possible."""
    from utils.champion_io import _name_signature
    from core.network import build_model
    for variant, expected in (("attn", "attn"), ("wta", "wta"),
                              ("stacked_2", "stacked_2"), ("stacked_2_skip", "stacked_2_skip"),
                              ("stacked_3_thin", "stacked_3")):
        name, supported, reason = _name_signature(build_model(variant).state_dict())
        assert name == expected, f"{variant} resolved to {name!r}"
        assert supported is False
        assert reason, f"{variant} refused without a reason"


def test_name_signature_unknown_signature():
    from utils.champion_io import _name_signature
    name, supported, reason = _name_signature({"nonsense.weight": None})
    assert name == "unknown" and supported is False and "signature" in reason.lower()


def test_multi_rate_is_accepted_as_baseline():
    """multi_rate is numerically identical to baseline once loaded (ALIFCell.forward uses only
    leak_div). It needs no dedicated handling -- but the resolver must not claim it recognised
    the variant."""
    from utils.champion_io import _name_signature
    from core.network import build_model
    name, supported, _ = _name_signature(build_model("multi_rate").state_dict())
    assert name == "baseline" and supported is True


# ---- identity: max_delay from a hierarchy of sources ---------------------------------------------

def _sd_with_delays(max_delay, H=32, IN=4, seed=0):
    """A baseline state-dict whose `delays` really come from randint(0, max_delay)."""
    from core.network import build_model
    torch.manual_seed(seed)
    return build_model("baseline", hidden_size=H, rank=8, max_delay=max_delay).state_dict()


def test_max_delay_from_arch_field_is_exact_and_skips_inference():
    from utils.champion_io import _resolve_max_delay
    sd = _sd_with_delays(6)
    md, src, p = _resolve_max_delay(sd, "baseline", arch={"max_delay": 6}, sidecar=None)
    assert md == 6 and src == "arch" and p is None


def test_max_delay_from_delay_masks_is_exact_for_eventprop():
    from utils.champion_io import _resolve_max_delay
    from core.network import build_model
    sd = build_model("eventprop_alif_full").state_dict()
    md, src, p = _resolve_max_delay(sd, "eventprop_alif_full", arch=None, sidecar=None)
    assert md == int(sd["layer_hidden.delay_masks"].shape[0])
    assert src == "delay_masks" and p is None


def test_max_delay_from_sidecar():
    from utils.champion_io import _resolve_max_delay
    sd = _sd_with_delays(12)
    md, src, p = _resolve_max_delay(sd, "baseline", arch=None, sidecar={"cf_max_delay": 12})
    assert md == 12 and src == "sidecar" and p is None


def test_max_delay_inferred_reports_its_confidence():
    from utils.champion_io import _resolve_max_delay
    sd = _sd_with_delays(12)
    md, src, p = _resolve_max_delay(sd, "baseline", arch=None, sidecar=None)
    assert md == 12 and src == "inferred"
    assert 0.0 < p < 1e-3                       # 128 samples at k=12 -> ~1.5e-5


def test_cross_check_raises_only_when_the_weights_REFUTE_the_declared_value():
    """TEETH, and the direction is the trap. The inference is a LOWER BOUND:
      declared > inferred  -> normal under-shoot, accept silently
      declared < inferred  -> impossible: a synapse holds a delay that model could not produce
    A test asserting 'differ -> raise' would pass a wrong implementation and fail a right one."""
    from utils.champion_io import _resolve_max_delay
    sd = _sd_with_delays(12)                    # delays.max() == 11 -> inference says 12

    # declared BELOW the inference -> refuted by the weights -> must raise
    with pytest.raises(ValueError, match="12"):
        _resolve_max_delay(sd, "baseline", arch=None, sidecar={"cf_max_delay": 6})

    # declared ABOVE the inference -> the expected under-shoot -> must NOT raise
    md, src, p = _resolve_max_delay(sd, "baseline", arch=None, sidecar={"cf_max_delay": 18})
    assert md == 18 and src == "sidecar"
