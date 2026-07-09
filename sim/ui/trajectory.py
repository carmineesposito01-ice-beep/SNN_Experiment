"""TrajectoryBuffer -- UI-layer ring buffer of StepResult (physics trajectory), so the golden probe
(sim/probe.py) stays untouched. The app records each StepResult; Trajectory/Safety panels read it."""
from collections import deque

import numpy as np

_FIELDS = ("t", "s", "v", "vl", "dv", "a_ego")


class TrajectoryBuffer:
    def __init__(self, capacity=500):
        self._buf = deque(maxlen=capacity)
        self._version = 0
        self._cache = None
        self._cache_ver = -1

    def record(self, result):
        self._buf.append(result)
        self._version += 1

    def __len__(self):
        return len(self._buf)

    def arrays(self):
        if self._cache is not None and self._cache_ver == self._version:   # Trajectory + Safety share it
            return self._cache
        if not self._buf:
            out = {k: np.empty(0) for k in _FIELDS}
        else:
            out = {k: np.array([getattr(r, k) for r in self._buf], dtype=float) for k in _FIELDS}
        self._cache, self._cache_ver = out, self._version
        return out
