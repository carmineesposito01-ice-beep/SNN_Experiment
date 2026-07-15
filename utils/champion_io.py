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
from dataclasses import dataclass
from typing import Any

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


def _infer_topology(state_dict, variant) -> dict:
    """Infer (hidden, input, rank, output) from tensor shapes.

    ``max_delay`` is intentionally not inferred: it does not change baseline tensor
    shapes and all champions use the config default (6), so it is left to build_model.
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


@dataclass
class ChampionHandle:
    """A strict-verified, ready-to-run champion."""
    model: Any
    variant: str
    topology: dict
    epoch: int
    val_loss: float


def load_champion(path, device="cpu") -> ChampionHandle:
    """Load a champion ``.pt`` into a strict-verified, eval-mode model.

    Raises ``ValueError`` on an unrecognised family and ``RuntimeError`` (from
    ``load_state_dict(strict=True)``) on any key/shape mismatch — never a silent
    partial load.
    """
    ckpt = torch.load(path, map_location=device, weights_only=False)
    state = ckpt["model_state"]
    variant = detect_family(state)
    topo = _infer_topology(state, variant)
    model = build_model(variant, hidden_size=topo["hidden"], rank=topo["rank"])
    model.load_state_dict(state, strict=True)   # §9.4 guard: raises on any mismatch
    model.to(device).eval()
    return ChampionHandle(
        model=model,
        variant=variant,
        topology=topo,
        epoch=int(ckpt.get("epoch", -1)),
        val_loss=float(ckpt.get("val_loss", float("nan"))),
    )
