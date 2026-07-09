"""TrajectoryBuffer -- UI-layer ring buffer of StepResult (physics trajectory), so the golden probe
(sim/probe.py) stays untouched. The app records each StepResult; Trajectory/Safety panels read it."""
from collections import deque

import numpy as np

_FIELDS = ("t", "s", "v", "vl", "dv", "a_ego")


class TrajectoryBuffer:
    def __init__(self, capacity=500):
        self._buf = deque(maxlen=capacity)

    def record(self, result):
        self._buf.append(result)

    def __len__(self):
        return len(self._buf)

    def arrays(self):
        if not self._buf:
            return {k: np.empty(0) for k in _FIELDS}
        return {k: np.array([getattr(r, k) for r in self._buf], dtype=float) for k in _FIELDS}
