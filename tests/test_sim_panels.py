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
from sim.ui.panels import NeuronGraphPanel, ParamPanel, SpikeRatePanel  # noqa: E402


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


# --- Phase 3b (rest): neuron inspector ---
from sim.ui.panels import NeuronInspectorPanel   # noqa: E402


def test_inspector_dominant_connections(qapp):
    H, IN, OUT = 6, 4, 5
    w_in = np.zeros((H, IN)); w_in[3, 2] = 5.0; w_in[3, 0] = 3.0     # #3 driven by input 2 (Δv) then 0 (s)
    w_out = np.zeros((OUT, H)); w_out[4, 3] = 7.0; w_out[3, 3] = 4.0  # #3 drives out 4 (b) then 3 (a)
    panel = NeuronInspectorPanel()
    panel.set_topology(w_in, np.zeros((H, H)), w_out)
    panel.set_neuron(3)
    txt = panel._conn.text()
    assert "#3" in panel._title.text()
    assert txt.index("Δv") < txt.index("s")     # input 2 ranked before input 0
    assert txt.index("b") < txt.index("a")      # out 4 (b) ranked before out 3 (a)


def test_inspector_traces_selected_neuron(qapp):
    panel = NeuronInspectorPanel()
    panel.set_topology(np.zeros((6, 4)), np.zeros((6, 6)), np.zeros((5, 6)))
    panel.set_neuron(2)
    pr = AttributeProbe(capacity=10)
    for t in range(4):
        spk = np.zeros(6); spk[2] = 1.0 if t == 2 else 0.0
        pr.record(t, {"spikes": spk, "v_mem": np.full(6, float(t)), "v_th_eff": np.ones(6)},
                  np.zeros(5))
    panel.update_frame(pr)
    y = panel._vmem.getData()[1]
    assert list(y) == [0.0, 1.0, 2.0, 3.0]      # neuron 2's v_mem over the buffer
    assert len(panel._spk.points()) == 1        # one spike, at t=2


def test_inspector_clear_none(qapp):
    panel = NeuronInspectorPanel()
    panel.set_topology(np.zeros((6, 4)), np.zeros((6, 6)), np.zeros((5, 6)))
    panel.set_neuron(1)
    panel.set_neuron(None)
    assert panel.neuron is None and panel._conn.text() == ""


# --- Phase 3 close: SynOps / energy dock ---
from sim.ui.panels import SynOpsPanel   # noqa: E402


def test_synops_panel_energy(qapp):
    panel = SynOpsPanel()
    assert panel._plot.parent() is panel                          # plot is actually placed in the widget
    panel.set_model(4, 32, 5, 8)
    assert abs(panel._ann_pj - (128 + 1024 + 160) * 4.6) < 1e-6   # dense-ANN energy reference (pJ)
    p = AttributeProbe(capacity=10)
    for t in range(3):
        spk = np.zeros(32); spk[:5] = 1                           # 5 firing
        p.record(t, {"spikes": spk, "v_mem": np.zeros(32), "v_th_eff": np.ones(32)}, np.zeros(5))
    panel.update_frame(p)
    ops = 128 + (5 * 8 + 32 * 8 + 5 * 5)                          # 449 SynOps
    y = panel._total_c.getData()[1]
    assert abs(float(y[-1]) - ops * 0.9) < 1e-6                    # SNN energy = SynOps × E_AC
    ref = panel._ref_c.getData()[1]
    assert ref is not None and bool(np.all(np.abs(ref - (128 + 1024 + 160) * 4.6) < 1e-6))


def test_synops_panel_cursor(qapp):
    panel = SynOpsPanel()
    panel.set_cursor(6)
    assert panel._cursors[0].isVisible() and abs(panel._cursors[0].value() - 6.0) < 1e-6


# ---- oracle ghost curves -------------------------------------------------------------------------

def _traj_buf(n=20, v=20.0, s=25.0):
    """Every series must VARY: the panels downsample with mode='peak' + clipToView, which collapses
    a flat series to its two extremes -- a constant-velocity fixture would test the downsampler,
    not set_ghost."""
    tb = TrajectoryBuffer(capacity=n + 1)
    for t in range(n):
        vt = v + t * 0.05
        tb.record(StepResult(t=t, s=s + t * 0.1, v=vt, vl=20.0, dv=vt - 20.0,
                             a_ego=0.1 + t * 0.01, params=np.zeros(5), collided=False))
    return tb


def _ydata(curve):
    """The data AS SET. getData() returns the downsampled/clipped view, which depends on an
    autorange that never happens without an event loop -- asserting on it tests pyqtgraph's
    downsampler (mode='peak' collapses a flat series to 2 points), not our set_ghost."""
    return curve.getOriginalDataset()[1]


def test_trajectory_panel_ghost_adds_three_curves_and_keeps_one_leader(qapp):
    p = TrajectoryPanel()
    p.update_frame(_traj_buf())
    p.set_ghost(_traj_buf(v=19.0, s=24.0))
    for c in (p._g_s, p._g_v, p._g_a):
        assert _ydata(c) is not None and len(_ydata(c)) == 20
    assert float(_ydata(p._g_s)[0]) == 24.0        # the ghost's gap, not the net's (25.0)
    # the leader is the SAME vehicle in both worlds -> exactly one leader curve on _pv
    assert not hasattr(p, "_g_vl")


def test_trajectory_panel_set_ghost_none_blanks_the_ghost_only(qapp):
    p = TrajectoryPanel()
    p.update_frame(_traj_buf())
    p.set_ghost(_traj_buf(v=19.0))
    p.set_ghost(None)
    d = _ydata(p._g_s)
    assert d is None or len(d) == 0
    assert len(_ydata(p._c_s)) == 20               # the net's curve survives


def test_safety_panel_ghost_adds_ttc_headway_drac(qapp):
    p = SafetyPanel()
    p.update_frame(_traj_buf())
    p.set_ghost(_traj_buf(v=19.0, s=24.0))
    for c in (p._g_ttc, p._g_th, p._g_drac):
        assert _ydata(c) is not None and len(_ydata(c)) == 20


def test_panels_clear_blanks_ghost_curves(qapp):
    """Reset/champion-swap trap: the QC already had to fix panels that did not blank."""
    for p, ghosts in ((TrajectoryPanel(), ("_g_s", "_g_v", "_g_a")),
                      (SafetyPanel(), ("_g_ttc", "_g_th", "_g_drac"))):
        p.update_frame(_traj_buf())
        p.set_ghost(_traj_buf(v=19.0))
        p.clear()
        for name in ghosts:
            d = _ydata(getattr(p, name))
            assert d is None or len(d) == 0


# ---- network graph adapts to the real hidden size ------------------------------------------------

def _col_ys(panel, x):
    return sorted(y for px, y in panel._pos if abs(px - x) < 1e-9)


def test_neuron_graph_label_states_the_real_hidden_count(qapp):
    """panels.py hardcodes 'hidden · 32 ALIF' -- the only literal 32 in sim/. It lies for any H != 32,
    and the whole point of this cycle is that the cockpit stops lying about what it loaded."""
    H, IN, OUT = 48, 4, 5
    rng = np.random.default_rng(0)
    panel = NeuronGraphPanel()
    panel.set_topology(rng.standard_normal((H, IN)), rng.standard_normal((H, H)),
                       rng.standard_normal((OUT, H)))
    # getPlotItem().items is pyqtgraph's list of added items; _plot.items is QGraphicsView's method.
    labels = [t.toPlainText() for t in panel._plot.getPlotItem().items if hasattr(t, "toPlainText")]
    assert any("48" in t for t in labels), labels
    assert not any("32" in t for t in labels), labels


def test_neuron_graph_nodes_do_not_overlap_at_larger_H(qapp):
    """yspread's span=32.0 is tuned for 16 nodes/column; at H=64 the spacing halves and the 13 px
    markers collide."""
    rng = np.random.default_rng(0)
    spacing = {}
    for H in (32, 64):
        panel = NeuronGraphPanel()
        panel.set_topology(rng.standard_normal((H, 4)), rng.standard_normal((H, H)),
                           rng.standard_normal((5, H)))
        ys = _col_ys(panel, 1.0)
        spacing[H] = min(b - a for a, b in zip(ys, ys[1:]))
    assert spacing[64] >= spacing[32] * 0.9      # spacing must not collapse with H


def test_neuron_graph_columns_stay_aligned_and_H32_is_unchanged(qapp):
    """TEETH: the span must stay GLOBAL. Giving each column a span from its own node count would
    spread 4 inputs over 6.4 while the hidden go to 66 -- the columns would stop lining up. And at
    H=32 the layout must be pixel-identical to what it has always been (span 32.0)."""
    rng = np.random.default_rng(0)
    panel = NeuronGraphPanel()
    panel.set_topology(rng.standard_normal((32, 4)), rng.standard_normal((32, 32)),
                       rng.standard_normal((5, 32)))
    for x in (0.0, 1.0, 1.4, 2.6):
        ys = _col_ys(panel, x)
        assert abs(ys[0] - 0.0) < 1e-6 and abs(ys[-1] - 32.0) < 0.1, f"column x={x}: {ys[0]}..{ys[-1]}"
