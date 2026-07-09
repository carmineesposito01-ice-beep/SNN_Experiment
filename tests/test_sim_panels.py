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
from sim.ui.panels import NeuronGraphPanel, ParamPanel, SpikeRatePanel, VmemPanel  # noqa: E402


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


def test_neuron_graph_topology_and_active_edges(qapp):
    H, IN, OUT = 6, 4, 5
    rng = np.random.default_rng(0)
    w_in = rng.standard_normal((H, IN))
    w_rec = rng.standard_normal((H, H))
    w_out = rng.standard_normal((OUT, H))
    panel = NeuronGraphPanel()
    panel.set_topology(w_in, w_rec, w_out)
    assert panel._pos.shape == (IN + H + OUT, 2)                       # 15 nodes
    exp_edges = IN * H + (H * H - H) + OUT * H                          # in + recurrent(no self) + out
    assert panel._skeleton.adjacency.shape[0] == exp_edges
    spikes = np.zeros(H)
    spikes[[0, 2]] = 1                                                  # hidden 0 and 2 fired
    p = AttributeProbe(capacity=5)
    p.record(0, {"spikes": spikes, "v_mem": np.linspace(0, 1, H), "v_th_eff": np.ones(H),
                 "input": np.array([0.1, 0.2, 0.3, 0.4])}, np.arange(OUT, dtype=float))
    panel.update_frame(p)
    active = panel._active.adjacency
    assert active.shape[0] == int((panel._rec_out_src == 0).sum() + (panel._rec_out_src == 2).sum())
    assert active.shape[0] > 0


def test_spike_rate_panel_series(qapp):
    p = AttributeProbe(capacity=10)
    for t in range(3):
        p.record(t, {"spikes": np.array([1., 0, 1, 0, 0, 0, 0, 0]), "v_mem": np.zeros(8),
                     "v_th_eff": np.ones(8)}, np.zeros(5))
    panel = SpikeRatePanel()
    panel.update_frame(p)
    y = panel._curve.getData()[1]
    assert abs(float(y[-1]) - 25.0) < 1e-6             # 2/8 hidden firing = 25 %


# --- Phase 3a: trajectory + safety ---
from sim.state import StepResult                       # noqa: E402
from sim.ui.panels import SafetyPanel, TrajectoryPanel  # noqa: E402
from sim.ui.trajectory import TrajectoryBuffer          # noqa: E402


def _traj(n=6):
    tb = TrajectoryBuffer()
    for t in range(n):
        tb.record(StepResult(t=t, s=20.0 - t, v=15.0, vl=13.0, dv=2.0, a_ego=-0.5,
                             params=np.zeros(5), collided=False))
    return tb


def test_trajectory_panel_updates(qapp):
    p = TrajectoryPanel()
    p.update_frame(_traj())
    assert p._c_s.getData()[1] is not None and float(p._c_s.getData()[1][0]) == 20.0


def test_safety_panel_updates_and_refs(qapp):
    p = SafetyPanel()
    p.update_frame(_traj())
    ttc0 = p._c_ttc.getData()[1]
    assert ttc0 is not None and abs(float(ttc0[0]) - 10.0) < 1e-6      # s=20, dv=2 -> TTC 10 s
    assert p._ttc_ref.isVisible() and abs(p._ttc_ref.value() - 1.5) < 1e-6
    assert p._drac_ref.isVisible() and abs(p._drac_ref.value() - 3.35) < 1e-6
