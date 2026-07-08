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
from sim.state import StepResult                    # noqa: E402
from sim.ui.topdown import TopDownView, ttc_color   # noqa: E402
from sim.ui.app import SimApp                        # noqa: E402
from sim.ui.layout import DOCK_ORDER, visible_docks  # noqa: E402
from sim.ui.theme import apply_dark_theme            # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# --- top-down view ---
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


# --- SimApp: champion + controls + status ---
def test_simapp_loads_champion_and_advances(qapp):
    win = SimApp(CHAMP)
    assert win.scenario_count() >= 10        # 9 library (include_tail) + manual
    win.select_scenario(0)
    win._advance(0.5)                        # 5 fixed steps, headless (no timer)
    assert win.loop.stepper.st.t >= 5
    win.inject_brake()                       # enqueues a brake_leader at current tick
    win._advance(0.5)                        # must not raise


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


def test_simapp_selector_syncs_on_programmatic_select(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(3)
    assert win._selector.currentIndex() == 3
    assert win._selector.currentText() == win._scenarios[3].name


def test_dark_theme_applies(qapp):
    from PySide6.QtGui import QPalette
    apply_dark_theme(qapp)
    assert qapp.palette().color(QPalette.Window).lightness() < 128


# --- Extension Phase 2: dockable shell ---
def test_simapp_builds_eight_docks(qapp):
    win = SimApp(CHAMP)
    assert set(win._docks.keys()) == set(DOCK_ORDER)
    assert visible_docks(win._area) == set(DOCK_ORDER)   # Overview on startup (no layout_path)


def test_simapp_params_xlinked(qapp):
    win = SimApp(CHAMP)
    vb0 = win._params[0].plot_item.getViewBox()
    vb3 = win._params[3].plot_item.getViewBox()
    assert vb3.linkedView(vb3.XAxis) is vb0   # param3 X-linked to param0 (holds even when torn out)


def test_simapp_feeds_ground_truth_to_params(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    gt = win._scenarios[0].params_gt
    assert win._params[0]._gt.isVisible()
    assert abs(win._params[0]._gt.value() - float(gt[0])) < 1e-6


def test_simapp_status_has_firing(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    assert "firing" in win.status_text()


def test_simapp_view_toggle_hides_and_shows_dock(qapp):
    win = SimApp(CHAMP)
    win._set_dock_visible("v_mem", False)
    assert "v_mem" not in visible_docks(win._area)
    win._set_dock_visible("v_mem", True)
    assert "v_mem" in visible_docks(win._area)


def test_simapp_apply_preset(qapp):
    win = SimApp(CHAMP)
    win.apply_preset("Identificazione")
    assert "v_mem" not in visible_docks(win._area)
    win.apply_preset("Overview")
    assert visible_docks(win._area) == set(DOCK_ORDER)
