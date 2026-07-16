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

from sim.ui.app import SimApp                             # noqa: E402
from sim.scenario import manual_scenario                  # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _append_user_scenario(win, name="mine"):
    sc = win._scenarios[0]
    win._on_scenario_built(manual_scenario(sc.params_gt, sc.v_leader, sc.s_init, sc.v_init, name=name))


def test_delete_removes_a_user_built_scenario_and_keeps_the_library(qapp):
    win = SimApp(CHAMP)
    protected = win._protected_count
    lib_names = [s.name for s in win._scenarios[:protected]]
    _append_user_scenario(win, "mine")
    assert win._current_idx >= protected                  # the new one is selected
    n_before = len(win._scenarios)
    win._delete_scenario()
    assert len(win._scenarios) == n_before - 1
    assert [s.name for s in win._scenarios[:protected]] == lib_names   # library slice untouched (Meso-safe)


def test_delete_refuses_a_protected_index(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)                                 # a library preset
    n = len(win._scenarios)
    win._delete_scenario()
    assert len(win._scenarios) == n                        # refused


def test_delete_action_is_disabled_on_a_protected_index(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._sync_scn_menu()
    assert not win._act_delete.isEnabled()
    _append_user_scenario(win, "mine")                     # selects the user-built one
    win._sync_scn_menu()
    assert win._act_delete.isEnabled()
