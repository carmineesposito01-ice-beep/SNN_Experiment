import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6.QtWidgets import QApplication          # noqa: E402
from sim.ui.postrun_page import PostRunPage          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_postrun_page_populates(qapp):
    p = PostRunPage()
    s = {"n_ticks": 3, "duration_s": 0.3, "collided": False, "min_gap": 12.5, "min_ttc": 4.0,
         "max_decel": 2.1, "rms_accel": 0.5, "rms_jerk": 1.2, "mean_firing_pct": 9.4,
         "peak_firing_pct": 15.0, "snn_pj": 400.0, "ann_pj": 6000.0, "advantage": 15.0}
    rows = [(0, 30.0, 20.0, 20.0, 0.0, 0.0, "", 30, 1.5, 2, 1.5, 1.5, 9.4),
            (1, 28.0, 20.0, 21.0, -1.0, 0.5, "", 30, 1.5, 2, 1.5, 1.5, 9.4),
            (2, 26.0, 20.5, 21.0, -0.5, 0.3, "", 30, 1.5, 2, 1.5, 1.5, 9.4)]
    p.set_summary(s, rows, "Raffaello", "following")
    assert "Raffaello" in p._header.text() and "following" in p._header.text()
    assert "12.5" in p._values["min_gap"].text()
    assert "ok" in p._values["esito"].text().lower()
    assert len(p._v_curve.getData()[0]) == 3          # speed plot has the episode length
