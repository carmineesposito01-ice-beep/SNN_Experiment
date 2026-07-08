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
from sim.ui.panels import NeuronStatePanel, ParamPanel, SpikeRatePanel, VmemPanel  # noqa: E402


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


def test_line_panels_have_clip_to_view(qapp):
    # downsampling + clip keep the live plots cheap; clipToViewMode() reports the clip state
    assert VmemPanel()._plot.getPlotItem().clipToViewMode() is True
    assert ParamPanel(0, "v0", "m/s", "#d1495b")._plot.getPlotItem().clipToViewMode() is True


def test_neuron_state_panel_groups_and_spike_overlay(qapp):
    H = 6
    spikes = np.array([1, 0, 1, 0, 0, 0], dtype=float)
    p = AttributeProbe(capacity=10)
    p.record(0, {"spikes": spikes, "v_mem": np.linspace(0, 1, H), "v_th_eff": np.ones(H),
                 "input": np.array([0.1, 0.2, 0.3, 0.4])}, np.array([30., 1.5, 2., 1.5, 1.5]))
    panel = NeuronStatePanel()
    panel.update_frame(p)
    assert set(panel._groups.keys()) == {"input", "hidden", "output"}
    heat = panel._groups["hidden"][1].image            # RGBA grid covering >= H cells
    assert heat.ndim == 3 and heat.shape[2] == 4 and heat.shape[0] * heat.shape[1] >= H
    ov = panel._groups["hidden"][2].image              # spike overlay: alpha>0 exactly on spiked cells
    assert int((ov[..., 3] > 0).sum()) == int(spikes.sum())
    assert panel._groups["input"][1].image.shape[0] == 1 and panel._groups["input"][1].image.shape[1] == 4


def test_spike_rate_panel_series(qapp):
    p = AttributeProbe(capacity=10)
    for t in range(3):
        p.record(t, {"spikes": np.array([1., 0, 1, 0, 0, 0, 0, 0]), "v_mem": np.zeros(8),
                     "v_th_eff": np.ones(8)}, np.zeros(5))
    panel = SpikeRatePanel()
    panel.update_frame(p)
    y = panel._curve.getData()[1]
    assert abs(float(y[-1]) - 25.0) < 1e-6             # 2/8 hidden firing = 25 %
