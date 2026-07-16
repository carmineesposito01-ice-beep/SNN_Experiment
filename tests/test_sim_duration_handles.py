import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

import pyqtgraph as pg                                     # noqa: E402
from PySide6.QtWidgets import QApplication                 # noqa: E402
from sim.ui.duration_handles import DurationHandles        # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_set_edges_places_a_line_at_start_plus_ticks(qapp):
    plot = pg.PlotWidget()
    h = DurationHandles(plot, on_resize=lambda *a: None)
    h.set_edges([(0, 0, 150, 6000), (1, 150, 200, 6000)])
    assert len(h) == 2
    assert h._lines[0].value() == 150            # start 0 + 150 ticks
    assert h._lines[1].value() == 350            # start 150 + 200 ticks


def test_set_edges_is_silent(qapp):
    """Placement is not a resize -- firing on_resize here would refresh mid-build."""
    plot = pg.PlotWidget()
    got = []
    h = DurationHandles(plot, on_resize=lambda *a: got.append(1))
    h.set_edges([(0, 0, 100, 600)])
    assert got == []


def test_a_finished_drag_reports_ticks_relative_to_the_start(qapp):
    """commit-on-finish: setValue moves the line, the release (sigPositionChangeFinished) commits.
    new_ticks is measured from the block's START, not the absolute x."""
    plot = pg.PlotWidget()
    got = []
    h = DurationHandles(plot, on_resize=lambda eid, t: got.append((eid, t)))
    h.set_edges([(1, 150, 200, 6000)])           # block 1 starts at 150, 200 ticks -> line at 350
    line = h._lines[0]
    line.setValue(300)                           # dragged left to x=300
    line.sigPositionChangeFinished.emit(line)    # released
    assert got == [(1, 150)]                      # 300 - 150


def test_the_bound_caps_the_duration(qapp):
    """setBounds([start+1, start+cap]) clamps in place; a preset (cap 600) cannot go past 600."""
    plot = pg.PlotWidget()
    got = []
    h = DurationHandles(plot, on_resize=lambda eid, t: got.append(t))
    h.set_edges([(0, 0, 100, 600)])              # cap 600
    line = h._lines[0]
    line.setValue(900)                           # try past the cap
    line.sigPositionChangeFinished.emit(line)
    assert got == [600]                           # clamped to start+cap=600 -> 600 ticks


def test_clear_removes_every_line(qapp):
    plot = pg.PlotWidget()
    h = DurationHandles(plot, on_resize=lambda *a: None)
    h.set_edges([(0, 0, 100, 600), (1, 100, 100, 600)])
    h.clear()
    assert len(h) == 0
