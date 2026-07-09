import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.state import StepResult                  # noqa: E402
from sim.ui.trajectory import TrajectoryBuffer     # noqa: E402
from sim.ui import metrics                          # noqa: E402


def _r(t, s):
    return StepResult(t=t, s=s, v=15.0, vl=13.0, dv=2.0, a_ego=-0.5, params=np.zeros(5), collided=False)


def test_trajectory_buffer_arrays_and_cap():
    tb = TrajectoryBuffer(capacity=3)
    for t in range(5):
        tb.record(_r(t, 20 - t))
    assert len(tb) == 3
    a = tb.arrays()
    assert a["t"].tolist() == [2, 3, 4]
    assert a["s"].tolist() == [18, 17, 16]
    assert a["dv"].tolist() == [2, 2, 2]


def test_trajectory_buffer_empty():
    a = TrajectoryBuffer().arrays()
    assert a["t"].size == 0 and a["s"].size == 0


def test_metrics_values():
    assert float(metrics.ttc(20, 2)) == 10.0                 # s/dv
    assert np.isinf(float(metrics.ttc(20, -1)))              # opening -> inf
    assert np.isinf(float(metrics.ttc(20, 0)))               # not closing -> inf
    assert abs(float(metrics.drac(20, 2)) - 0.1) < 1e-9      # dv^2/2s
    assert float(metrics.drac(20, -1)) == 0.0
    assert float(metrics.time_headway(20, 10)) == 2.0        # s/v
    assert np.isinf(float(metrics.time_headway(20, 0)))


def test_metrics_vectorised():
    s = np.array([20.0, 10.0])
    dv = np.array([2.0, -1.0])
    assert np.allclose(metrics.ttc(s, dv), [10.0, np.inf])
