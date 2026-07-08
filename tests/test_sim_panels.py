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
from sim.probe import AttributeProbe                # noqa: E402
from sim.ui.panels import ParamPanel, RasterPanel, VmemPanel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _probe(params, spikes=None):
    p = AttributeProbe(capacity=50)
    spk = spikes if spikes is not None else np.zeros(8)
    for t in range(4):
        p.record(t, {"spikes": spk, "v_mem": np.linspace(0, 1, 8), "v_th_eff": np.ones(8)},
                 np.asarray(params, dtype=float))
    return p


def test_raster_panel_updates(qapp):
    RasterPanel().update_frame(_probe([0, 0, 0, 0, 0], spikes=(np.arange(8) % 2).astype(float)))


def test_vmem_panel_updates(qapp):
    VmemPanel().update_frame(_probe([0, 0, 0, 0, 0]))


def test_param_panel_physical_value_and_title(qapp):
    p = ParamPanel(0, "v0", "m/s", "#d1495b")
    p.update_frame(_probe([44.0, 1.1, 2.5, 0.5, 1.0]))
    assert abs(p.current_value() - 44.0) < 1e-6
    y = p._curve.getData()[1]
    assert y is not None and float(np.nanmax(y)) > 40.0
    assert "v0 = 44.00 m/s" in p.plot_item.titleLabel.text


def test_param_panel_ground_truth(qapp):
    p = ParamPanel(1, "T", "s", "#2a7fb8")
    p.set_ground_truth(1.5)
    assert p._gt.isVisible() and abs(p._gt.value() - 1.5) < 1e-6
    p.set_ground_truth(None)
    assert not p._gt.isVisible()


def test_raster_orientation_time_x_neuron_y(qapp):
    # F frames of H neurons -> image must be X=time (F wide), Y=neuron (H tall), NOT transposed
    F, H = 9, 4
    p = AttributeProbe(capacity=50)
    for t in range(F):
        p.record(t, {"spikes": (np.arange(H) % 2).astype(float), "v_mem": np.zeros(H),
                     "v_th_eff": np.ones(H)}, np.zeros(5))
    panel = RasterPanel()
    panel.update_frame(p)
    br = panel._img.boundingRect()
    assert round(br.width()) == F and round(br.height()) == H   # time on X, neuron on Y
