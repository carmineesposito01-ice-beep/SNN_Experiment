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
    win._on_scenario_built(manual_scenario(sc.params_gt, sc.v_leader, sc.s_init, sc.v_init, name=name), None)


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


# --- 7a plan B: the built scenario's recipe must survive the signal ---
def _a_spec(name="mine"):
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    return ScenarioSpec(name=name, blocks=(Block("const", 120, {"v": 15.0}),),
                        style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)


def test_the_app_retains_the_spec_of_a_built_scenario(qapp):
    win = SimApp(CHAMP)
    protected = win._protected_count
    assert len(win._specs) == len(win._scenarios)            # parallel from the start
    assert all(s is None for s in win._specs[:protected])    # library + initial manual have no recipe
    win._scenario_page.set_spec(_a_spec())
    win._scenario_page._name_edit.setText("mine")
    win._scenario_page._on_use()                             # the real path: build -> emit -> append
    assert len(win._specs) == len(win._scenarios)
    assert win._specs[-1] is not None and win._specs[-1].blocks[0].kind == "const"


def test_delete_keeps_specs_aligned_with_scenarios(qapp):
    win = SimApp(CHAMP)
    win._scenario_page.set_spec(_a_spec())
    win._scenario_page._on_use()
    n = len(win._scenarios)
    win._delete_scenario()                                   # the built one is selected
    assert len(win._specs) == len(win._scenarios) == n - 1   # both popped -> still aligned


# --- 7a plan B: the 5th mode ---
def test_the_app_has_a_fifth_dataset_mode(qapp):
    win = SimApp(CHAMP)
    assert [win._mode_sel.itemText(i) for i in range(win._mode_sel.count())] == [
        "Live", "Meso/Macro", "Post-run", "Scenari", "Dataset"]
    assert win._mode_stack.count() == 5
    win.set_mode(4)
    assert win._mode_stack.currentIndex() == 4


def test_entering_the_dataset_mode_refreshes_the_built_sources(qapp):
    win = SimApp(CHAMP)
    win.set_mode(4)
    assert win._dataset_page._mix.specs() == {}           # nothing built yet (the mix table owns the sources now)
    win._scenario_page.set_spec(_a_spec())
    win._scenario_page._name_edit.setText("mine")
    win._scenario_page._on_use()
    win.set_mode(4)                                      # re-entering must pick the new spec up
    assert "mine" in win._dataset_page._mix.specs()


def test_the_generate_button_is_a_busy_control(qapp):
    win = SimApp(CHAMP)
    assert win._dataset_page._gen_btn in win._busy_controls()   # so a click cannot nest a second batch


def test_run_dataset_writes_a_dataset_and_restores_the_ui(qapp, tmp_path):
    import json
    win = SimApp(CHAMP)
    win.set_mode(4)
    p = win._dataset_page
    p._mix._rows[0].family.setCurrentText("preset")
    p._mix._rows[0].source.setCurrentText("following")
    p._mix._rows[0].weight.setValue(100.0)
    p._count.setValue(2)
    for b in p._fmt_boxes.values():
        b.setChecked(False)
    p._fmt_boxes["csv"].setChecked(True)
    p._out_dir.setText(str(tmp_path))
    win._run_dataset()
    with open(str(tmp_path / "manifest.json")) as f:
        man = json.load(f)
    assert man["count"] == 2 and len(man["trajectories"]) == 2
    assert win._dataset_page._gen_btn.isEnabled()          # _done_busy ran (try/finally)
