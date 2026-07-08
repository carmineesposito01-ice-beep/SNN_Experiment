"""Compute seam for the simulator: SW today, FPGA (Fase 3) tomorrow.

v1 contract is synchronous (reset + infer). SoftwareBackend is family-aware: baseline
uses model.forward_step; eventprop_alif_full (no forward_step) uses EventPropStepper.
The set_input/step/get_output split (SIMULATOR_DESIGN.md §2) lands with FpgaBackend.
"""
from typing import Protocol

import torch

from core.network import CF_FSNN_Net_EventProp_Full
from sim.eventprop_stepper import EventPropStepper


class NetworkBackend(Protocol):
    def reset(self) -> None: ...
    def infer(self, obs_norm: torch.Tensor) -> torch.Tensor: ...   # (1,4) -> (1,5)


class SoftwareBackend:
    """Wraps a champion_io-loaded CF_FSNN model; baseline -> forward_step, eventprop -> stepper."""

    def __init__(self, model, device: str = "cpu"):
        self.model = model
        self.device = device
        self._eventprop = isinstance(model, CF_FSNN_Net_EventProp_Full)
        self._stepper = EventPropStepper(model) if self._eventprop else None
        self._last_input = None

    def reset(self) -> None:
        self.model.eval()
        if self._eventprop:
            self._stepper.reset(1, self.device)
        else:
            self.model.reset_state(1, self.device)

    def infer(self, obs_norm: torch.Tensor) -> torch.Tensor:
        obs = obs_norm.to(self.device)
        self._last_input = obs.detach().cpu().numpy().reshape(-1)
        if self._eventprop:
            return self._stepper.step(obs)
        return self.model.forward_step(obs)

    def read_probe(self) -> dict:
        """Zero-intrusion snapshot of the hidden ALIF state (numpy (H,) spikes/v_mem/v_th_eff).
        Baseline reads layer_hidden.cell; eventprop delegates to the stepper's live state."""
        if self._eventprop:
            return self._stepper.read_probe()
        try:
            cell = self.model.layer_hidden.cell
        except AttributeError as e:
            raise ValueError("read_probe requires a .cell-nested hidden layer "
                             "(baseline family); this model has none") from e
        v_mem = cell.potential.detach().cpu().numpy().reshape(-1)
        spikes = cell.prev_spike.detach().cpu().numpy().reshape(-1)
        v_th = (cell.base_threshold + cell.fatigue.clamp(min=0)).detach().cpu().numpy().reshape(-1)
        return {"spikes": spikes, "v_mem": v_mem, "v_th_eff": v_th, "input": self._last_input}


class FpgaBackend:
    """Stub -- realized in Fase 3 (PYNQ overlay + AXI/DMA). Same seam."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError(
            "FpgaBackend arrives in Fase 3 (see document/POST_FPGA_ROADMAP.md)."
        )


def make_backend(target: str, model=None, device: str = "cpu") -> NetworkBackend:
    if target == "software":
        if model is None:
            raise ValueError("software backend requires a loaded model")
        return SoftwareBackend(model, device)
    if target == "fpga":
        return FpgaBackend()
    raise ValueError(f"unknown backend target: {target!r}")
