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

from sim.ui.scenario_preview import ScenarioPreviewPanel   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_set_scenario_draws_the_whole_profile(qapp):
    panel = ScenarioPreviewPanel()
    v = np.array([20.0, 21.0, 19.5, 12.0, 12.0], dtype=float)
    panel.set_scenario(v)
    x, y = panel._curve.getData()
    assert np.allclose(y, v)                       # the whole profile, not a slice
    assert np.allclose(x, np.arange(len(v)))       # x = tick index


def test_set_marker_positions_then_hides(qapp):
    panel = ScenarioPreviewPanel()
    panel.set_marker(42)
    assert panel._marker.isVisible()
    assert abs(panel._marker.value() - 42.0) < 1e-6
    panel.set_marker(None)
    assert not panel._marker.isVisible()


def test_clear_blanks_curve_and_marker(qapp):
    panel = ScenarioPreviewPanel()
    panel.set_scenario(np.arange(10.0))
    panel.set_marker(3)
    panel.clear()
    _, y = panel._curve.getData()
    assert y is None or len(y) == 0                # curve blanked
    assert not panel._marker.isVisible()           # marker hidden


def test_narrow_scenario_gets_at_least_the_minimum_y_span(qapp):
    from sim.ui.scenario_preview import _MIN_Y_SPAN
    panel = ScenarioPreviewPanel()
    v = np.linspace(20.8, 21.2, 100)               # span 0.4 m/s -- the "following" jitter case
    panel.set_scenario(v)
    lo, hi = panel._plot.getViewBox().viewRange()[1]
    assert (hi - lo) >= _MIN_Y_SPAN - 1e-6         # window floored to the min span, NOT zoomed onto 0.4 m/s
    assert lo <= float(v.min()) and hi >= float(v.max())   # the data is still inside the view


def test_wide_scenario_fits_the_data_not_the_floor(qapp):
    from sim.ui.scenario_preview import _MIN_Y_SPAN
    panel = ScenarioPreviewPanel()
    v = np.linspace(0.0, 21.0, 100)                # span 21 m/s > the floor -> fit to data, not blown up
    panel.set_scenario(v)
    lo, hi = panel._plot.getViewBox().viewRange()[1]
    span = hi - lo
    data_span = float(v.max() - v.min())
    assert span >= data_span                        # the whole profile fits
    assert span < data_span + _MIN_Y_SPAN           # fitted with light padding, not floored to a fixed big window
