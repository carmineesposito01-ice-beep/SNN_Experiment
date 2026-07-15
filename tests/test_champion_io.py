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


# ---- identity: the verdict, and the bug this cycle closes ----------------------------------------

def test_resolve_identity_verdict_for_a_real_champion():
    from utils.champion_io import resolve_identity
    ckpt = torch.load(os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt"),
                      map_location="cpu", weights_only=False)
    idy = resolve_identity(ckpt["model_state"], arch=ckpt.get("arch"))
    assert idy.family == "baseline" and idy.supported is True
    assert idy.topology == {"hidden": 32, "input": 4, "rank": 8, "output": 5}
    assert idy.max_delay == 6 and idy.sources["max_delay"] == "inferred"


def test_resolve_identity_refuses_by_name_without_raising():
    from utils.champion_io import resolve_identity
    from core.network import build_model
    idy = resolve_identity(build_model("attn").state_dict())
    assert idy.family == "attn" and idy.supported is False and idy.reason


def test_load_champion_no_longer_drops_synapses_on_a_max_delay_12_checkpoint(tmp_path):
    """THE BUG THIS CYCLE CLOSES, asserted on the synapse count -- not on a label.

    Before: detect_family said 'baseline', strict=True PASSED, build_model rebuilt with the config
    default 6, and every delay >= 6 never matched `for d in range(max_delay)` -> 68/128 input
    synapses silently dropped, max |diff| on the decoded params = 5.98.
    """
    from core.network import build_model
    torch.manual_seed(0)
    original = build_model("baseline", hidden_size=32, rank=8, max_delay=12)
    path = tmp_path / "best_model.pt"
    torch.save({"epoch": 1, "val_loss": 0.1, "model_state": original.state_dict(),
                "optim_state": {}}, path)

    handle = load_champion(str(path))
    assert handle.model.max_delay == 12                    # rebuilt with the RIGHT max_delay
    assert handle.identity.max_delay == 12

    delays = handle.model.layer_hidden.delays
    dropped = int((delays >= handle.model.max_delay).sum())
    assert dropped == 0, f"{dropped} of {delays.numel()} input synapses are unreachable"

    obs = torch.zeros(1, 4)
    original.reset_state(1, "cpu")
    handle.model.reset_state(1, "cpu")
    torch.testing.assert_close(original.forward_step(obs), handle.model.forward_step(obs))


def test_load_champion_still_loads_the_four_champions_identically():
    """Regression: the four bundled champions must resolve exactly as before."""
    expected = {"R33_C2_A1_T12_fix": ("baseline", 8), "LS3_PEAK_R0_launch_d03": ("baseline", 8),
                "PE_t05_gp0002": ("eventprop_alif_full", 16), "A_lr1e2_t06_r16": ("eventprop_alif_full", 16)}
    for tag, (fam, rank) in expected.items():
        h = load_champion(os.path.join(REPO, "champions", tag, "best_model.pt"))
        assert h.variant == fam and h.topology["rank"] == rank
        assert h.identity.max_delay == 6
