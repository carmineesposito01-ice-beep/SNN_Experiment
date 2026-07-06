"""AttributeProbe -- ring-buffer of hidden-state snapshots for the live net panel.

Decoupled from SimStepper: the driver (UI loop / test) calls record() after each
step with the backend's read_probe() dict + the step's 5 params. sample_every
decouples UI refresh from the physics dt (nengo.Probe pattern).
"""
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ProbeFrame:
    t: int
    spikes: np.ndarray      # (H,)
    v_mem: np.ndarray       # (H,)
    v_th_eff: np.ndarray    # (H,)
    params: np.ndarray      # (5,)


class AttributeProbe:
    def __init__(self, capacity=500, sample_every=1):
        if sample_every < 1:
            raise ValueError("sample_every must be >= 1")
        self.capacity = capacity
        self.sample_every = sample_every
        self._buf = deque(maxlen=capacity)
        self._count = 0

    def record(self, t, probe, params):
        if self._count % self.sample_every == 0:
            self._buf.append(ProbeFrame(
                t=t,
                spikes=np.asarray(probe["spikes"], dtype=np.float64),
                v_mem=np.asarray(probe["v_mem"], dtype=np.float64),
                v_th_eff=np.asarray(probe["v_th_eff"], dtype=np.float64),
                params=np.asarray(params, dtype=np.float64).reshape(-1),
            ))
        self._count += 1

    def frames(self):
        return list(self._buf)

    def spikes_matrix(self):
        """(frames, H) raster of last-tick spikes; empty (0,0) if no frames."""
        return np.stack([f.spikes for f in self._buf]) if self._buf else np.empty((0, 0))

    def params_matrix(self):
        return np.stack([f.params for f in self._buf]) if self._buf else np.empty((0, 5))
