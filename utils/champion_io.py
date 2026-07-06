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


def detect_family(state_dict) -> str:
    """Return the ``build_model`` variant for a champion ``state_dict``.

    Primary discriminator is the readout key; it is then cross-checked against the ALIF
    nesting signature (flat ``layer_hidden.base_threshold`` vs nested
    ``layer_hidden.cell.base_threshold``) so a malformed/hybrid state-dict fails loudly
    instead of loading wrong. Raises ``ValueError`` on unknown/ambiguous signatures.
    """
    keys = set(state_dict.keys())
    ep_readout = _EVENTPROP_READOUT in keys
    bl_readout = _BASELINE_READOUT in keys
    flat_alif = "layer_hidden.base_threshold" in keys
    cell_alif = "layer_hidden.cell.base_threshold" in keys

    if ep_readout and not bl_readout and flat_alif and not cell_alif:
        return "eventprop_alif_full"
    if bl_readout and not ep_readout and cell_alif and not flat_alif:
        return "baseline"
    raise ValueError(
        "Cannot identify champion family from state-dict signature "
        f"(readout: eventprop={ep_readout} baseline={bl_readout}; "
        f"alif: flat={flat_alif} cell={cell_alif}). Keys: {sorted(keys)}"
    )


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
