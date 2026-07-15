"""Canonical champion loader — shared by the simulator (fase ①) and the Simulink
import (fase ②).

Reads a CF_FSNN champion checkpoint (.pt), detects its architecture family from the
state-dict signature, rebuilds the exact model via ``core.network.build_model`` and
``load_state_dict(strict=True)``.

Why this exists: the champion .pt stores NO family/config metadata (only
``{epoch, val_loss, model_state, optim_state}``), so the family MUST be inferred from
the state-dict keys/shapes. Loading one family's weights into the other class with
``strict=False`` silently leaves the readout random — the §9.4 bug. ``strict=True`` here
turns that silent failure into a loud one.

Two families appear in the versioned champions (design scope — YAGNI, seam to extend):
  * ``baseline``            — .cell-nested ALIF, readout ``layer_out.fc_weight``
  * ``eventprop_alif_full`` — flat ALIF,        readout ``layer_out.weight``
"""
import json
import os
from dataclasses import dataclass
from typing import Any, Optional

import torch

from core.network import build_model

# Readout parameter name = primary family discriminator (project idiom, Eval_FPGA.ipynb).
_EVENTPROP_READOUT = "layer_out.weight"
_BASELINE_READOUT = "layer_out.fc_weight"


# Variants build_model can produce but the simulator cannot SHOW. Naming them is what separates
# "I know what this is and cannot serve it" from "I have no idea what this is": today attn/wta carry
# the baseline signature plus an extra block, so they are silently called "baseline" and only
# strict=True stops them, with a message about tensors.
_UNSUPPORTED = {
    "attn": ("Wq", "the attention block Wq/Wk/Wv is not on the readout path the viewer draws"),
    "wta": ("inh_w_in", "the lateral-inhibition weight inh_w_in is not shown by the viewer"),
}


def _name_signature(state_dict):
    """(name, supported, reason) for a state-dict. Never raises: the caller decides what to do."""
    keys = set(state_dict.keys())

    # Stacked family: several hidden layers. The backend reads model.layer_hidden (singular), so
    # these cannot be observed without a new backend -- out of scope, see the cycle-2 spec.
    stacked_idx = [int(k.split(".")[1]) for k in keys if k.startswith("layers_hidden.")]
    if stacked_idx:
        n = max(stacked_idx) + 1
        return (f"stacked_{n}", False,
                f"stacked variant with {n} hidden layers: the viewer reads a single hidden layer")
    if "skip_weight" in keys and any(k.startswith("layer_hidden_0.") for k in keys):
        return ("stacked_2_skip", False,
                "stacked variant with a skip connection: the viewer reads a single hidden layer")

    # attn/wta = baseline signature PLUS an extra block -> must be tested BEFORE baseline.
    for name, (marker, why) in _UNSUPPORTED.items():
        if marker in keys:
            return (name, False, why)

    ep_readout = _EVENTPROP_READOUT in keys
    bl_readout = _BASELINE_READOUT in keys
    flat_alif = "layer_hidden.base_threshold" in keys
    cell_alif = "layer_hidden.cell.base_threshold" in keys
    if ep_readout and not bl_readout and flat_alif and not cell_alif:
        return ("eventprop_alif_full", True, None)
    if bl_readout and not ep_readout and cell_alif and not flat_alif:
        return ("baseline", True, None)
    return ("unknown", False,
            f"unrecognised state-dict signature (readout: eventprop={ep_readout} "
            f"baseline={bl_readout}; alif: flat={flat_alif} cell={cell_alif})")


def detect_family(state_dict) -> str:
    """Return the ``build_model`` variant for a champion ``state_dict``.

    Thin wrapper over ``_name_signature`` for callers that want the family or a loud failure.
    Raises ``ValueError`` on unknown/ambiguous/unsupported signatures.
    """
    name, supported, reason = _name_signature(state_dict)
    if not supported:
        raise ValueError(f"Cannot load this checkpoint: {name} — {reason}")
    return name


def _infer_max_delay(state_dict):
    """(inferred, p_underestimate) from the ``delays`` buffer, or (None, None) if absent.

    ``delays`` is ``randint(0, max_delay, (H, IN))`` (core/network.py:26), so its max is a LOWER
    BOUND of ``max_delay-1``: the inference is exact only if some synapse drew the top value.
    Measured over 20k draws: exact for max_delay 6 and 12, fails ~1 in 1333 at max_delay=18 with
    H=32 (128 samples), under-shooting by 1.
    """
    d = state_dict.get("layer_hidden.delays")
    if d is None:
        return None, None
    k = int(d.max()) + 1
    n = int(d.numel())
    p = ((k - 1) / k) ** n if k > 1 else 0.0     # uses the inferred k: the true one is unknowable
    return k, p


def _resolve_max_delay(state_dict, family, arch=None, sidecar=None):
    """(max_delay, source, p_underestimate). source in {arch, delay_masks, sidecar, inferred}.

    The .pt carries no metadata, so max_delay is unknowable from the baseline signature alone
    (``delays`` is (H,IN) whatever max_delay is) — which is why it used to be silently defaulted
    to 6, dropping 68/128 input synapses on a max_delay_12 checkpoint. Hierarchy, most
    authoritative first.
    """
    declared, source = None, None
    if arch and arch.get("max_delay") is not None:
        declared, source = int(arch["max_delay"]), "arch"
    elif family == "eventprop_alif_full" and "layer_hidden.delay_masks" in state_dict:
        declared, source = int(state_dict["layer_hidden.delay_masks"].shape[0]), "delay_masks"
    elif sidecar and sidecar.get("cf_max_delay") is not None:
        declared, source = int(sidecar["cf_max_delay"]), "sidecar"

    inferred, p = _infer_max_delay(state_dict)

    if declared is not None:
        # Asymmetric cross-check. The inference is a LOWER BOUND, so declared > inferred is the
        # expected under-shoot, NOT a conflict. Only declared < inferred is impossible: a synapse
        # holds a delay that model could never have produced, so the declared source is refuted by
        # the weights themselves (a sidecar from another run, an arch field copied from elsewhere).
        if inferred is not None and declared < inferred:
            raise ValueError(
                f"max_delay declared as {declared} (source: {source}) is refuted by the weights: "
                f"the delays buffer holds {inferred - 1}, which requires max_delay >= {inferred}. "
                f"The checkpoint and that source do not describe the same model.")
        return declared, source, None

    if inferred is None:
        return None, None, None
    return inferred, "inferred", p


def _infer_topology(state_dict, variant) -> dict:
    """Infer (hidden, input, rank, output) from tensor shapes.

    ``max_delay`` is NOT inferable here: it does not change baseline tensor shapes (``delays`` is
    (H,IN) whatever it is). It is resolved by ``_resolve_max_delay`` — see there for why defaulting
    it silently was a real bug and not a harmless assumption.
    """
    fc = state_dict["layer_hidden.fc_weight"]        # (hidden, input)
    rec_u = state_dict["layer_hidden.rec_U"]         # (hidden, rank)
    readout_key = _EVENTPROP_READOUT if variant == "eventprop_alif_full" else _BASELINE_READOUT
    readout = state_dict[readout_key]                # (output, hidden)
    return {
        "hidden": int(fc.shape[0]),
        "input": int(fc.shape[1]),
        "rank": int(rec_u.shape[1]),
        "output": int(readout.shape[0]),
    }


@dataclass(frozen=True)
class Identity:
    """What a checkpoint IS, and how sure we are of each part."""
    family: str                  # build_model variant, the name of an unsupported one, or "unknown"
    supported: bool
    reason: Optional[str]        # why it cannot be served (None when supported)
    topology: Optional[dict]     # {hidden, input, rank, output}; None when unreadable
    max_delay: Optional[int]
    sources: dict                # {"topology": "weights", "max_delay": "arch"|"delay_masks"|...}
    max_delay_p_underestimate: Optional[float]   # only when max_delay was inferred


def resolve_identity(state_dict, arch=None, sidecar=None) -> Identity:
    """What is this checkpoint?

    Pure: no torch.load, no filesystem, no GUI — so it is testable on synthetic state-dicts,
    including the ones that lie today. Never raises for an unsupported but nameable variant: it
    returns ``supported=False`` and a reason, and the caller decides.
    """
    family, supported, reason = _name_signature(state_dict)
    if not supported:
        return Identity(family=family, supported=False, reason=reason, topology=None,
                        max_delay=None, sources={}, max_delay_p_underestimate=None)
    topo = _infer_topology(state_dict, family)
    md, md_src, p = _resolve_max_delay(state_dict, family, arch=arch, sidecar=sidecar)
    return Identity(family=family, supported=True, reason=None, topology=topo, max_delay=md,
                    sources={"topology": "weights", "max_delay": md_src},
                    max_delay_p_underestimate=p)


def _read_sidecar(path):
    """``config_snapshot.json`` next to the checkpoint, if any.

    Coverage in the corpus: cf_hidden_size/cf_rank 506/512, cf_max_delay 258/512 — and absent next
    to the 4 bundled champions. An unreadable sidecar must never block a loadable checkpoint.
    """
    p = os.path.join(os.path.dirname(os.path.abspath(path)), "config_snapshot.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


@dataclass
class ChampionHandle:
    """A strict-verified, ready-to-run champion."""
    model: Any
    variant: str
    topology: dict
    epoch: int
    val_loss: float
    identity: Identity


def load_champion(path, device="cpu") -> ChampionHandle:
    """Load a champion ``.pt`` into a strict-verified, eval-mode model.

    Raises ``ValueError`` on an unrecognised or unsupported family (naming it) and ``RuntimeError``
    (from ``load_state_dict(strict=True)``) on any key/shape mismatch — never a silent partial load.
    """
    ckpt = torch.load(path, map_location=device, weights_only=False)
    state = ckpt["model_state"]
    identity = resolve_identity(state, arch=ckpt.get("arch"), sidecar=_read_sidecar(path))
    if not identity.supported:
        raise ValueError(f"Cannot load this checkpoint: {identity.family} — {identity.reason}")
    # max_delay is the line that closes the silent-drop bug: it used to fall back to the config
    # default, which made every delay >= 6 unreachable on a max_delay_12 checkpoint.
    model = build_model(identity.family, hidden_size=identity.topology["hidden"],
                        rank=identity.topology["rank"], max_delay=identity.max_delay)
    model.load_state_dict(state, strict=True)   # §9.4 guard: raises on any mismatch
    model.to(device).eval()
    return ChampionHandle(
        model=model,
        variant=identity.family,
        topology=identity.topology,
        epoch=int(ckpt.get("epoch", -1)),
        val_loss=float(ckpt.get("val_loss", float("nan"))),
        identity=identity,
    )
