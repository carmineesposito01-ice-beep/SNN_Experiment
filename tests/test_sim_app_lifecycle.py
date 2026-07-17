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


# --- B2 Task 6: the training destination + cancel ---
def test_run_dataset_training_writes_a_pt_cache(qapp, tmp_path):
    import torch
    win = SimApp(CHAMP)
    win.set_mode(4)
    p = win._dataset_page
    p._dest_training.setChecked(True)
    tp = p._training
    tp._mix._rows[0].family.setCurrentText("generator")
    tp._mix._rows[0].source.setCurrentText("sinusoidal")
    tp._mix._rows[0].regime.setCurrentText("highway")
    tp._mix._rows[0].weight.setValue(100.0)
    tp._n_train.setValue(3); tp._n_val.setValue(2)
    path = str(tmp_path / "cache.pt"); tp._out_dir.setText(path)
    win._run_dataset()
    blob = torch.load(path, weights_only=False)
    assert len(blob["train"]) == 3 and len(blob["val"]) == 2
    assert tp._gen_btn.isEnabled()                         # _done_busy ran
    assert not tp._cancel_btn.isEnabled()                  # cancel back to idle


def test_the_cancel_button_is_not_a_busy_control_but_generate_is(qapp):
    """Cancel must stay clickable DURING the run -- the one control _busy does NOT disable. But the training
    Generate MUST be a busy control, or the processEvents pump could deliver a second click and nest a run."""
    win = SimApp(CHAMP)
    controls = win._busy_controls()
    assert win._dataset_page._training._cancel_btn not in controls
    assert win._dataset_page._training._gen_btn in controls


def test_a_shared_leader_in_val_mode_2_is_reported_not_crashed(qapp, tmp_path):
    """Mode 2 raises ValueError when a leader is shared (strength 0 + a const built spec). The app must SURFACE
    that in the status bar and restore the UI -- not let the exception escape the click handler."""
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    win = SimApp(CHAMP)
    sc0 = win._scenarios[0]
    win._on_scenario_built(manual_scenario(sc0.params_gt, sc0.v_leader, sc0.s_init, sc0.v_init, name="flat"),
                           ScenarioSpec(name="flat", blocks=(Block("const", 600, {"v": 20.0}),),
                                        style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0))
    win.set_mode(4)
    p = win._dataset_page; p._dest_training.setChecked(True); tp = p._training
    tp._mix._rows[0].family.setCurrentText("built")
    tp._mix._rows[0].source.setCurrentText("flat")
    tp._mix._rows[0].regime.setCurrentText("highway")
    tp._mix._rows[0].weight.setValue(100.0)
    tp._jitter.setValue(0)                                 # strength 0 -> identity -> train and val share the leader
    tp._val_sel.setCurrentIndex(1)                         # new_shapes mode: the gate must fire
    tp._n_train.setValue(2); tp._n_val.setValue(2)
    path = str(tmp_path / "cache.pt"); tp._out_dir.setText(path)
    win._run_dataset()                                     # must NOT raise
    assert not os.path.exists(path)                        # nothing written
    assert tp._gen_btn.isEnabled()                         # UI restored


def test_cancelling_a_training_run_writes_nothing(qapp, tmp_path):
    win = SimApp(CHAMP)
    win.set_mode(4)
    p = win._dataset_page; p._dest_training.setChecked(True)
    tp = p._training
    tp._mix._rows[0].family.setCurrentText("generator")
    tp._mix._rows[0].source.setCurrentText("sinusoidal")
    tp._mix._rows[0].regime.setCurrentText("highway")
    tp._mix._rows[0].weight.setValue(100.0)
    tp._n_train.setValue(5); tp._n_val.setValue(2)
    path = str(tmp_path / "cache.pt"); tp._out_dir.setText(path)
    # simulate the user clicking Cancel mid-run: request cancel on the first progress tick (the pump would
    # normally deliver the click). _run_dataset resets the flag at start, so pre-setting it does not work.
    orig = win._dataset_progress
    def cancel_on_first(i, total):
        win._cancel_dataset()
        return orig(i, total)
    win._dataset_progress = cancel_on_first
    win._run_dataset()
    assert not os.path.exists(path)                        # a cancelled run writes nothing
    assert tp._gen_btn.isEnabled() and not tp._cancel_btn.isEnabled()
