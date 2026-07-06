"""Compute seam for the simulator: SW today, FPGA (Fase 3) tomorrow.

v1 contract is synchronous (reset + infer). The set_input/step/get_output
split (SIMULATOR_DESIGN.md §2) lands with FpgaBackend, where async DMA needs it.
"""
from typing import Protocol

import torch


class NetworkBackend(Protocol):
    def reset(self) -> None: ...
    def infer(self, obs_norm: torch.Tensor) -> torch.Tensor: ...   # (1,4) -> (1,5)


class SoftwareBackend:
    """Wraps a champion_io-loaded CF_FSNN model; forward_step per control step."""

    def __init__(self, model, device: str = "cpu"):
        self.model = model
        self.device = device

    def reset(self) -> None:
        self.model.eval()
        self.model.reset_state(1, self.device)

    def infer(self, obs_norm: torch.Tensor) -> torch.Tensor:
        return self.model.forward_step(obs_norm.to(self.device))

    def read_probe(self) -> dict:
        """Zero-intrusion snapshot of the hidden ALIF state (AttributeMonitor pattern).

        numpy (H,) arrays: spikes (last internal tick), v_mem (potential),
        v_th_eff (base_threshold + fatigue.clamp(min=0)). Requires the standard
        .cell-nested hidden layer (baseline family).
        """
        try:
            cell = self.model.layer_hidden.cell
        except AttributeError as e:
            raise ValueError("read_probe requires a .cell-nested hidden layer "
                             "(baseline family); this model has none") from e
        v_mem = cell.potential.detach().cpu().numpy().reshape(-1)
        spikes = cell.prev_spike.detach().cpu().numpy().reshape(-1)
        v_th = (cell.base_threshold + cell.fatigue.clamp(min=0)).detach().cpu().numpy().reshape(-1)
        return {"spikes": spikes, "v_mem": v_mem, "v_th_eff": v_th}


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
