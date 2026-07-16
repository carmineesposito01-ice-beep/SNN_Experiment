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

import pyqtgraph as pg                                     # noqa: E402
from PySide6.QtWidgets import QApplication                 # noqa: E402
from sim.ui.drag_handles import DragHandles                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_place_and_read_speeds(qapp):
    plot = pg.PlotWidget()
    calls = []
    h = DragHandles(plot, on_change=lambda: calls.append(1))
    h.set_speeds(ticks=[30.0, 60.0, 90.0], speeds=[10.0, 12.0, 4.0])
    assert h.speeds() == [10.0, 12.0, 4.0]
    assert len(h) == 3


def test_a_drag_is_locked_to_vertical(qapp):
    """The measured route: reconnecting x in sigPositionChanged converges in 2 calls, x stays put."""
    plot = pg.PlotWidget()
    h = DragHandles(plot, on_change=lambda: None)
    h.set_speeds(ticks=[50.0], speeds=[10.0])
    item = h._items[0]
    item.setPos(80.0, 14.0)                                # what a diagonal drag would do
    assert item.pos().x() == 50.0                          # x locked to the node's tick
    assert item.pos().y() == 14.0                          # y moved


def test_y_is_clamped_to_v_range_not_the_plot(qapp):
    from sim.scenario_spec import V_RANGE
    plot = pg.PlotWidget()
    h = DragHandles(plot, on_change=lambda: None)
    h.set_speeds(ticks=[50.0], speeds=[10.0])
    h._items[0].setPos(50.0, -5.0)
    assert h.speeds()[0] == V_RANGE[0]                     # v<0 pinned: no reverse leader
    h._items[0].setPos(50.0, 99.0)
    assert h.speeds()[0] == V_RANGE[1]


def test_set_speeds_does_not_fire_on_change(qapp):
    """Placement is not a user edit: firing on_change mid-placement is the lifecycle bug -- a refresh
    while the row is half-built. set_speeds is silent; only a drag notifies."""
    plot = pg.PlotWidget()
    calls = []
    h = DragHandles(plot, on_change=lambda: calls.append(1))
    h.set_speeds(ticks=[30.0, 60.0], speeds=[10.0, 12.0])
    assert calls == []                                     # silent
    h._items[0].setPos(30.0, 8.0)                          # a real drag, in-place (no correction)
    assert calls == [1]


def test_a_corrected_drag_fires_on_change_exactly_once(qapp):
    """TEETH on the `return`: a drag OFF the node's tick triggers the x-snap, which re-emits
    sigPositionChanged. on_change must fire once, not once per re-emit -- an in-place drag never
    enters the correction, so it cannot test this; the off-tick drag can."""
    plot = pg.PlotWidget()
    calls = []
    h = DragHandles(plot, on_change=lambda: calls.append(1))
    h.set_speeds(ticks=[50.0], speeds=[10.0])
    calls.clear()
    h._items[0].setPos(80.0, 14.0)                         # off-tick: the x-snap re-emits
    assert calls == [1]                                    # exactly once, not [1, 1]


def test_clear_removes_every_handle(qapp):
    plot = pg.PlotWidget()
    h = DragHandles(plot, on_change=lambda: None)
    h.set_speeds(ticks=[30.0, 60.0], speeds=[10.0, 12.0])
    h.clear()
    assert len(h) == 0 and h.speeds() == []
