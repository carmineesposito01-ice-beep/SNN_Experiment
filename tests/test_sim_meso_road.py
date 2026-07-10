import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6.QtWidgets import QApplication          # noqa: E402
from sim.ui.meso_road import PlatoonRoadView         # noqa: E402
from sim.ui.topdown import PX_PER_M                  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _rec(T=20, N=4):
    return {"x": np.cumsum(np.full((T, N), 5.0), axis=0), "v": np.full((T, N), 10.0)}


def test_road_view_set_run_builds_cars_and_slider(qapp):
    r = PlatoonRoadView()
    r.set_run(_rec(T=20, N=4))
    assert r._slider.maximum() == 19          # T-1
    assert len(r._cars) == 4                  # one car per vehicle


def test_road_view_render_frame_positions_cars(qapp):
    rec = _rec(T=20, N=4)
    r = PlatoonRoadView(); r.set_run(rec)
    r.render_frame(5)
    assert abs(r._cars[0].pos().x() - rec["x"][5, 0] * PX_PER_M) < 1e-6


def test_road_view_play_toggles_timer(qapp):
    r = PlatoonRoadView(); r.set_run(_rec())
    r._play_btn.setChecked(True)
    assert r._timer.isActive()
    r.stop()
    assert not r._timer.isActive()
