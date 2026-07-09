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


def test_trajectory_arrays_memoized():
    tb = TrajectoryBuffer()
    tb.record(_r(0, 20))
    a1 = tb.arrays()
    assert tb.arrays() is a1                                # cache hit between records (Trajectory+Safety share)
    tb.record(_r(1, 19))
    a2 = tb.arrays()
    assert a2 is not a1 and a2["s"].tolist() == [20, 19]    # invalidated + recomputed


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


# --- SynOps / energy metrics ---
def test_synops_static_dynamic():
    row = np.zeros(32); row[[0, 1, 2]] = 1
    static, dynamic = metrics.synops(row, 4, 32, 5, 8)
    assert static == 128                                  # IN*H
    assert dynamic == 3 * 8 + 32 * 8 + 3 * 5              # rec_V + rec_U + out = 24+256+15 = 295


def test_synops_zero_firing_no_dynamic():
    static, dynamic = metrics.synops(np.zeros(32), 4, 32, 5, 8)
    assert static == 128 and dynamic == 0                # no spike -> rec_U gate off too


def test_dense_mac_is_param_count():
    assert metrics.dense_mac(4, 32, 5, 8) == 128 + 512 + 160     # 800


def test_ann_mac_dense_rnn():
    assert metrics.ann_mac(4, 32, 5) == 128 + 1024 + 160         # dense recurrent RNN (full H*H) = 1312


def test_synops_series_matches_scalar():
    sm = np.array([[0, 0, 0], [1, 0, 1]])                # H=3
    st, dy = metrics.synops_series(sm, 2, 3, 1, 2)
    assert list(st) == [6, 6]                            # IN*H = 2*3
    assert dy[0] == 0
    assert dy[1] == 2 * 2 + 3 * 2 + 2 * 1                # s=2: rec_V 4 + rec_U 6 + out 2 = 12
