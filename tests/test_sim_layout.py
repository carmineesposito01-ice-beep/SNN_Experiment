import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6.QtWidgets import QApplication, QLabel   # noqa: E402
from pyqtgraph.dockarea import Dock, DockArea        # noqa: E402
from sim.ui.layout import (DOCK_ORDER, apply_identificazione, apply_neuro_debug,  # noqa: E402
                           apply_overview, load_layout, save_layout, visible_docks)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _build_area():
    area = DockArea()
    docks = {}
    for name in DOCK_ORDER:
        d = Dock(name, closable=True)
        d.addWidget(QLabel(name))
        docks[name] = d
    apply_overview(area, docks)
    return area, docks


def test_overview_all_visible(qapp):
    area, docks = _build_area()
    assert visible_docks(area) == set(DOCK_ORDER)


def test_identificazione_hides_vmem(qapp):
    area, docks = _build_area()
    apply_identificazione(area, docks)
    vis = visible_docks(area)
    assert "v_mem" not in vis
    assert {"v0", "T", "s0", "a", "b"} <= vis


def test_neuro_debug_shows_netstate_and_spikerate(qapp):
    area, docks = _build_area()
    apply_neuro_debug(area, docks)
    assert {"NetState", "SpikeRate", "v_mem"} <= visible_docks(area)


def test_preset_then_overview_restores_all(qapp):
    area, docks = _build_area()
    apply_identificazione(area, docks)   # hides v_mem
    apply_overview(area, docks)
    assert visible_docks(area) == set(DOCK_ORDER)


def test_layout_roundtrip(qapp, tmp_path):
    area, docks = _build_area()
    p = str(tmp_path / "layout.json")
    save_layout(area, p)
    assert os.path.exists(p)
    assert load_layout(area, docks, p) is True


def test_layout_corrupt_falls_back_to_overview(qapp, tmp_path):
    area, docks = _build_area()
    p = str(tmp_path / "bad.json")
    with open(p, "w") as f:
        f.write("{ not valid json")
    assert load_layout(area, docks, p) is False
    assert visible_docks(area) == set(DOCK_ORDER)


def test_layout_missing_file_falls_back(qapp, tmp_path):
    area, docks = _build_area()
    assert load_layout(area, docks, str(tmp_path / "nope.json")) is False
    assert visible_docks(area) == set(DOCK_ORDER)
