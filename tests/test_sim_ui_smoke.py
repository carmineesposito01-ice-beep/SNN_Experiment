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

from PySide6.QtWidgets import QApplication  # noqa: E402
from sim.state import StepResult            # noqa: E402
from sim.ui.topdown import TopDownView      # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# (old minimal topdown test superseded by test_topdown_ego_scrolls_and_leader_tracks_gap below)


# --- Task 3: NetPanel ---
from sim.probe import AttributeProbe        # noqa: E402
from sim.ui.netpanel import NetPanel        # noqa: E402


def test_netpanel_instantiates_and_updates(qapp):
    probe = AttributeProbe(capacity=50)
    for t in range(5):
        probe.record(t, {"spikes": (np.arange(8) % 2).astype(float),
                          "v_mem": np.linspace(0, 1, 8),
                          "v_th_eff": np.ones(8)}, np.arange(5) + t)
    panel = NetPanel()
    panel.update_frame(probe)               # must not raise
    assert panel.n_params_curves() == 5


# --- Task 4: SimApp ---
from sim.ui.app import SimApp               # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def test_simapp_loads_champion_and_advances(qapp):
    win = SimApp(CHAMP)
    assert win.scenario_count() >= 10        # 9 library (include_tail) + manual
    win.select_scenario(0)
    win._advance(0.5)                        # 5 fixed steps, headless (no timer)
    assert win.loop.stepper.st.t >= 5
    win.inject_brake()                       # enqueues a brake_leader at current tick
    win._advance(0.5)                        # must not raise


# --- Plan 5 Task 1: top-down polish ---
from sim.ui.topdown import ttc_color         # noqa: E402


def _stepv(s, v, dv=0.0):
    return StepResult(t=0, s=s, v=v, vl=v - dv, dv=dv, a_ego=0.0, params=np.zeros(5),
                      collided=False)


def test_ttc_color_bands():
    assert ttc_color(100.0, -5.0) == "safe"      # opening -> safe
    assert ttc_color(50.0, 0.0) == "safe"        # not closing -> safe
    assert ttc_color(3.0, 5.0) == "danger"       # 0.6 s TTC -> danger
    assert ttc_color(15.0, 5.0) == "caution"     # 3 s TTC -> caution


def test_topdown_ego_scrolls_and_leader_tracks_gap(qapp):
    view = TopDownView()
    view.update_frame(_stepv(s=30.0, v=20.0))
    ex1, lx1 = view.ego_x_m(), view.leader_x_m()
    view.update_frame(_stepv(s=25.0, v=20.0))
    ex2, lx2 = view.ego_x_m(), view.leader_x_m()
    assert ex2 > ex1                             # ego advanced (integrated v)
    assert (lx2 - ex2) < (lx1 - ex1)             # gap shrank 30 -> 25


# --- Plan 5 Task 2: net-panel readability ---
def test_netpanel_has_current_values(qapp):
    probe = AttributeProbe(capacity=50)
    for t in range(4):
        probe.record(t, {"spikes": np.zeros(8), "v_mem": np.linspace(0, 1, 8),
                          "v_th_eff": np.ones(8)}, np.array([30., 1.5, 2., 1.5, 1.5]))
    panel = NetPanel()
    panel.update_frame(probe)
    labels = panel.current_param_labels()        # ["v0=30.00", "T=1.50", ...]
    assert len(labels) == 5 and labels[0].startswith("v0=") and panel.n_params_curves() == 5


# --- Plan 5 Task 3: controls + status bar ---
def test_simapp_status_reset_step(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    s = win.status_text()
    assert "gap" in s and "ego" in s
    win.step_once()
    t_after = win.loop.stepper.st.t
    win.reset_run()
    assert win.loop.stepper.st.t == 0 and t_after >= 5


# --- Plan 5 Task 4: dark theme ---
from sim.ui.theme import apply_dark_theme     # noqa: E402


def test_dark_theme_applies(qapp):
    from PySide6.QtGui import QPalette
    apply_dark_theme(qapp)
    assert qapp.palette().color(QPalette.Window).lightness() < 128


def test_simapp_selector_syncs_on_programmatic_select(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(3)
    assert win._selector.currentIndex() == 3
    assert win._selector.currentText() == win._scenarios[3].name


# --- Extension Phase 1: param legibility ---
def test_netpanel_params_in_physical_units(qapp):
    probe = AttributeProbe(capacity=50)
    for t in range(4):
        probe.record(t, {"spikes": np.zeros(8), "v_mem": np.zeros(8), "v_th_eff": np.ones(8)},
                     np.array([44.0, 1.1, 2.5, 0.5, 1.0]))
    panel = NetPanel()
    panel.update_frame(probe)
    assert panel.n_params_curves() == 5                       # unchanged public API
    y_v0 = panel._param_curves[0].getData()[1]                # RAW value, not 0..1
    assert y_v0 is not None and float(np.nanmax(y_v0)) > 40.0  # v0 plotted in m/s
    assert panel.current_param_labels()[0] == "v0=44.00"


def test_netpanel_ground_truth_reference(qapp):
    panel = NetPanel()
    panel.set_ground_truth(np.array([30.0, 1.5, 2.0, 1.5, 1.5]))
    assert panel._gt_lines[0].isVisible()
    assert abs(panel._gt_lines[0].value() - 30.0) < 1e-6
    panel.set_ground_truth(None)
    assert not panel._gt_lines[0].isVisible()


def test_netpanel_firing_readout(qapp):
    probe = AttributeProbe(capacity=50)
    for t in range(3):
        probe.record(t, {"spikes": np.array([1., 0., 1., 0., 1., 0., 1., 0.]),
                         "v_mem": np.zeros(8), "v_th_eff": np.ones(8)}, np.zeros(5))
    panel = NetPanel()
    panel.update_frame(probe)
    assert "%" in panel._firing_label.text() and "50" in panel._firing_label.text()


def test_simapp_feeds_ground_truth_to_netpanel(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    gt = win._scenarios[0].params_gt
    assert win._netpanel._gt_lines[0].isVisible()
    assert abs(win._netpanel._gt_lines[0].value() - float(gt[0])) < 1e-6


# --- Extension Phase 1 polish: vertical legibility ---
def test_simapp_netpanel_gets_more_vertical_space(qapp):
    win = SimApp(CHAMP)
    lay = win.centralWidget().layout()
    # the network panel (5 params + raster + v_mem) needs more room than the thin road strip
    assert lay.stretch(lay.indexOf(win._netpanel)) > lay.stretch(lay.indexOf(win._topdown))


def test_netpanel_param_axis_labels_uncluttered(qapp):
    panel = NetPanel()
    # redundant left-axis TITLE removed (name+units+value live in the per-plot title);
    # only tick numbers remain, so short stacked plots don't overlap their labels
    assert panel._param_plots[0].getAxis("left").labelText == ""
    # but each plot is still labelled up-front, before the first frame
    assert "v0" in panel._param_plots[0].titleLabel.text
