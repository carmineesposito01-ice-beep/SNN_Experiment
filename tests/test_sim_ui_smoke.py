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
