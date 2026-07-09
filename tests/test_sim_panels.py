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


# --- Phase 3b.1: scrub cursor + index-aware graph ---
def test_param_panel_cursor(qapp):
    p = ParamPanel(0, "v0", "m/s", "#d1495b")
    p.set_cursor(7)
    assert p._cursors[0].isVisible() and abs(p._cursors[0].value() - 7.0) < 1e-6
    p.set_cursor(None)
    assert not p._cursors[0].isVisible()


def test_trajectory_panel_cursor_all_subplots(qapp):
    p = TrajectoryPanel()
    p.set_cursor(3)
    assert len(p._cursors) == 3 and all(c.isVisible() for c in p._cursors)


def test_neuron_graph_index_aware(qapp):
    H, IN, OUT = 6, 4, 5
    rng = np.random.default_rng(1)
    panel = NeuronGraphPanel()
    panel.set_topology(rng.standard_normal((H, IN)), rng.standard_normal((H, H)),
                       rng.standard_normal((OUT, H)))
    pr = AttributeProbe(capacity=10)
    pr.record(0, {"spikes": np.zeros(H), "v_mem": np.zeros(H), "v_th_eff": np.ones(H),
                  "input": np.zeros(IN)}, np.zeros(OUT))
    pr.record(1, {"spikes": np.ones(H), "v_mem": np.linspace(1, 2, H), "v_th_eff": np.ones(H),
                  "input": np.ones(IN)}, np.ones(OUT))
    panel.update_frame(pr, index=0)
    v0 = panel._last_vals.copy()
    panel.update_frame(pr, index=1)
    assert not np.allclose(v0, panel._last_vals)              # different tick -> different state
    panel.update_frame(pr, index=99)                          # out-of-range clamps, no raise


# --- Phase 3b (rest): event timeline ---
from sim.ui.panels import EventTimelinePanel   # noqa: E402
from sim.probe import ProbeFrame               # noqa: E402


def _pf(ticks):
    return [ProbeFrame(t=t, spikes=np.zeros(2), v_mem=np.zeros(2), v_th_eff=np.ones(2),
                       params=np.zeros(5)) for t in ticks]


def test_event_timeline_maps_ticks_and_drops_out_of_range(qapp):
    panel = EventTimelinePanel()
    frames = _pf(range(100, 200))                          # ticks 100..199 -> idx 0..99
    log = [{"tick": 130, "verb": "brake_leader", "params": {}},
           {"tick": 400, "verb": "brake_leader", "params": {}},   # dropped (out of range)
           {"tick": 50,  "verb": "brake_leader", "params": {}}]   # dropped (out of range)
    panel.update_events(log, frames)
    xs = sorted(p.pos().x() for p in panel._marks.points())
    assert xs == [30.0]                                    # only tick 130 -> idx 30


def test_event_timeline_click_seeks_by_tick(qapp):
    panel = EventTimelinePanel()
    seen = []
    panel.set_on_seek(lambda tick: seen.append(tick))
    panel.update_events([{"tick": 105, "verb": "brake_leader", "params": {}}], _pf(range(100, 110)))
    panel._on_click(panel._marks, list(panel._marks.points()))
    assert seen == [105]                                   # seeks by absolute tick, not buffer index


def test_event_timeline_has_cursor(qapp):
    panel = EventTimelinePanel()
    panel.set_cursor(4)
    assert panel._cursors[0].isVisible() and abs(panel._cursors[0].value() - 4.0) < 1e-6
    panel.set_cursor(None)
    assert not panel._cursors[0].isVisible()


# --- Phase 3b (rest): graph click + highlight ---
def test_neuron_graph_highlight_fan_in_out(qapp):
    H, IN, OUT = 6, 4, 5
    rng = np.random.default_rng(2)
    panel = NeuronGraphPanel()
    panel.set_topology(rng.standard_normal((H, IN)), rng.standard_normal((H, H)),
                       rng.standard_normal((OUT, H)))
    panel.highlight(2)
    node = IN + 2
    adj = panel._highlight.adjacency
    assert adj.shape[0] == IN + (H - 1) + (H - 1) + OUT      # fan-in(in+rec) + fan-out(rec+out)
    assert np.all((adj[:, 1] == node) | (adj[:, 0] == node))
    panel.highlight(None)
    hl = panel._highlight.adjacency
    assert hl is None or hl.shape[0] == 0        # pyqtgraph normalizes an empty overlay to None


def test_neuron_graph_click_emits_hidden_index(qapp):
    H, IN, OUT = 6, 4, 5
    rng = np.random.default_rng(3)
    panel = NeuronGraphPanel()
    panel.set_topology(rng.standard_normal((H, IN)), rng.standard_normal((H, H)),
                       rng.standard_normal((OUT, H)))
    got = []
    panel.sigNeuronClicked.connect(lambda i: got.append(i))

    class _Spot:
        def index(self_):
            return IN + 3                                   # node index of hidden neuron 3

    panel._on_node_click(panel._nodes, [_Spot()])
    assert got == [3]


def test_neuron_graph_click_ignores_non_hidden(qapp):
    H, IN, OUT = 6, 4, 5
    rng = np.random.default_rng(4)
    panel = NeuronGraphPanel()
    panel.set_topology(rng.standard_normal((H, IN)), rng.standard_normal((H, H)),
                       rng.standard_normal((OUT, H)))
    got = []
    panel.sigNeuronClicked.connect(lambda i: got.append(i))

    class _Spot:
        def index(self_):
            return 0                                        # an input node

    panel._on_node_click(panel._nodes, [_Spot()])
    assert got == []                                        # input/output clicks are no-ops
