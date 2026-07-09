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
    input: np.ndarray = None  # (in,) network input at this tick; None if not captured


class AttributeProbe:
    def __init__(self, capacity=500, sample_every=1):
        if sample_every < 1:
            raise ValueError("sample_every must be >= 1")
        self.capacity = capacity
        self.sample_every = sample_every
        self._buf = deque(maxlen=capacity)
        self._count = 0
        self._cache = {}       # {name: (version, value)} memo keyed on _count (see _memo)

    def record(self, t, probe, params):
        if self._count % self.sample_every == 0:
            inp = probe.get("input")
            self._buf.append(ProbeFrame(
                t=t,
                spikes=np.asarray(probe["spikes"], dtype=np.float64),
                v_mem=np.asarray(probe["v_mem"], dtype=np.float64),
                v_th_eff=np.asarray(probe["v_th_eff"], dtype=np.float64),
                params=np.asarray(params, dtype=np.float64).reshape(-1),
                input=(np.asarray(inp, dtype=np.float64).reshape(-1) if inp is not None else None),
            ))
        self._count += 1

    def _memo(self, name, build):
        """Cache build() keyed on _count (bumped every record()). Within one redraw no record()
        runs, so the 5 ParamPanels / 2 spike consumers sharing this probe hit the cache instead of
        rebuilding the same array. Read-only memo: record()'s body is unchanged."""
        hit = self._cache.get(name)
        if hit is not None and hit[0] == self._count:
            return hit[1]
        val = build()
        self._cache[name] = (self._count, val)
        return val

    def frames(self):
        return self._memo("frames", lambda: list(self._buf))

    def spikes_matrix(self):
        """(frames, H) raster of last-tick spikes; empty (0,0) if no frames."""
        def build():
            m = np.stack([f.spikes for f in self._buf]) if self._buf else np.empty((0, 0))
            m.flags.writeable = False       # hardened: consumers only read
            return m
        return self._memo("spikes", build)

    def params_matrix(self):
        def build():
            m = np.stack([f.params for f in self._buf]) if self._buf else np.empty((0, 5))
            m.flags.writeable = False
            return m
        return self._memo("params", build)

    @classmethod
    def from_frames(cls, frames, capacity):
        """Build a probe directly from existing ProbeFrames (deep-scrub splice). No re-run,
        record() not involved -> frozen-core-safe."""
        p = cls(capacity=capacity)
        p._buf.extend(frames)
        p._count = len(frames)
        return p
