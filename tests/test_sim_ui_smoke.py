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
def test_simapp_builds_docks(qapp):
    win = SimApp(CHAMP)
    assert set(win._docks.keys()) == set(DOCK_ORDER)     # 9 docks (Road/NetState/SpikeRate/v_mem/5 params)
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


def test_simapp_clamps_frame_dt(qapp):
    win = SimApp(CHAMP)
    assert win._clamp_frame_dt(5.0) == 0.1     # a lagged frame can't cascade into a huge step-batch
    assert win._clamp_frame_dt(0.02) == 0.02   # normal frames pass through


# --- Phase 3b.1: time-scrub ---
from sim.ui.trajectory import TrajectoryBuffer   # noqa: E402


def _traj_seq(vs, ss):
    tb = TrajectoryBuffer()
    for i, (v, s) in enumerate(zip(vs, ss)):
        tb.record(StepResult(t=i, s=s, v=v, vl=v - 1.0, dv=1.0, a_ego=0.0, params=np.zeros(5),
                             collided=False))
    return tb


def test_topdown_render_at_reconstructs(qapp):
    from config import DT
    view = TopDownView()
    vs = [10.0, 12.0, 8.0, 15.0]
    tb = _traj_seq(vs, [30.0, 28.0, 26.0, 24.0])
    view.render_at(tb, 2)
    assert abs(view.ego_x_m() - float(np.cumsum(vs)[2] * DT)) < 1e-6
    view.render_at(tb, -1)                       # head
    assert abs(view.ego_x_m() - float(np.sum(vs) * DT)) < 1e-6


def test_simapp_scrub_cursor(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)                                  # ~5 buffered ticks
    win._run_btn.setChecked(False)                     # ensure paused
    win._render_at_cursor(2)
    assert win._cursor == 2
    assert win._params[0]._cursors[0].isVisible()      # cursor line shown on a time-series panel
    win._step_cursor(1)
    assert win._cursor == 3
    win._step_cursor(999)                              # clamps to head
    assert win._cursor == len(win._probe.frames()) - 1


# --- Phase 3b (rest): deep-scrub + events + inspector ---
def test_simapp_builds_all_docks(qapp):
    win = SimApp(CHAMP)
    assert {"Events", "Inspector", "SynOps"} <= set(win._docks)
    assert len(win._docks) == 14


def test_simapp_deep_scrub_reconstructs_beyond_buffer(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)                       # scenario 0: gentle following, runs to completion
    win._advance(60.0)                           # whole episode -> buffer (500) wraps
    assert win.loop.stepper.st.t > win._probe.capacity
    win._on_run_toggled(False)                   # pause -> reconstruct full episode
    n = len(win._src_probe.frames())
    assert n == win.loop.stepper.st.t            # full episode reconstructed
    assert n > len(win._probe.frames())          # more than the live ring buffer
    win._render_at_cursor(0)                     # scrub to tick 0 (outside the live buffer)
    assert win._cursor == 0 and win._cursor_readout.text().startswith("t=0")


def test_simapp_event_click_and_neuron_select(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    win.inject_brake()
    win._advance(0.5)
    win._on_run_toggled(False)                   # pause
    log = win._injector.log()
    assert log
    win._seek_to(log[0]["tick"])                 # click the brake mark -> seek to its tick
    assert win._src_probe.frames()[win._cursor].t == log[0]["tick"]
    win._on_neuron_selected(1)                   # select hidden neuron 1
    assert win._inspector.neuron == 1
    assert win._netstate._highlight.adjacency.shape[0] > 0


def test_simapp_resume_reverts_to_live_source(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    win._on_run_toggled(False)                   # pause
    win._on_run_toggled(True)                    # resume
    win._timer.stop()                            # headless: don't leave a live timer running
    assert win._src_probe is win._probe and win._src_traj is win._traj


# --- Phase 3 close: SynOps / energy dock ---
def test_simapp_reconstruct_is_cached(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(60.0)                           # wrap the buffer -> pause reconstructs
    win._on_run_toggled(False)                   # cache miss (builds the full episode)
    p1, t1 = win._src_probe, win._src_traj
    win._on_run_toggled(True)                    # resume (no advance in headless test)
    win._timer.stop()
    win._on_run_toggled(False)                   # same (scenario, tick, #events) -> cache hit
    assert win._src_probe is p1 and win._src_traj is t1     # reused, not recomputed (no 7 s freeze)


def test_simapp_topdown_integrates_all_ticks_at_speed(qapp):
    from config import DT
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._speed = 4                               # >1 -> loop.tick returns MANY results per _paint
    win._advance(0.4)                            # 0.4*4 = 1.6 s -> ~16 steps in one _paint call
    expected = float(np.cumsum(win._traj.arrays()["v"])[-1] * DT)
    assert abs(win._topdown.ego_x_m() - expected) < 1e-6   # ego integrated every tick, not just results[-1]


def test_simapp_step_after_reconstruct_reverts_source(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(60.0)
    win._on_run_toggled(False)                   # pause -> deep-scrub source = reconstructed episode
    assert win._src_probe is not win._probe
    win.step_once()                              # advancing the live sim must revert the source to live
    assert win._src_probe is win._probe and win._src_traj is win._traj


def test_simapp_champion_selector_lists_and_swaps(qapp):
    win = SimApp(CHAMP)
    names = [n for n, _ in win._champions]
    assert "Raffaello" in names and len(win._champions) >= 2      # registry built from champions/ dir
    assert win._champ_name == "Raffaello"                          # launched with R33
    r8 = win._synops._dims[3]                                      # baseline rank
    don = names.index("Donatello") if "Donatello" in names else 1
    win.select_champion(don)
    assert win._champ_name == names[don]
    assert win._synops._dims[3] > 0                                # topology rebuilt for the new family
    win.select_scenario(0)
    win._advance(0.5)                                              # runs with the swapped champion, no raise
    assert win.loop.stepper.st.t >= 5


def test_simapp_mode_toggle(qapp):
    win = SimApp(CHAMP)
    assert win._mode_stack.count() == 3                  # Live + Meso/Macro + Post-run
    assert win._mode_stack.currentIndex() == 0           # starts Live
    win._run_btn.setChecked(True)
    win.set_mode(1)                                       # switch to analysis
    assert win._mode_stack.currentIndex() == 1
    assert not win._run_btn.isChecked()                  # entering analysis pauses live
    win.set_mode(0)
    assert win._mode_stack.currentIndex() == 0


def test_simapp_run_platoon_populates_meso(qapp):
    win = SimApp(CHAMP)
    win.set_mode(1)
    win._meso_page._n_spin.setValue(5)
    win._run_platoon()
    h = win._meso_page.string_stability._bars.opts["height"]
    assert h is not None and len(h) == 5                  # one bar per vehicle
    st = win._meso_page.space_time._curves
    active = [c for c in st if c.getData()[0] is not None and len(c.getData()[0]) > 0]
    assert len(active) == 5                               # 5 space-time trajectories
    sw = win._meso_page.speed_wave._curves
    activev = [c for c in sw if c.getData()[0] is not None and len(c.getData()[0]) > 0]
    assert len(activev) == 5                              # 5 velocity-wave curves


def test_simapp_run_ring_populates_fundamental(qapp):
    win = SimApp(CHAMP)
    win.set_mode(1)
    win._sweep_densities = np.array([20.0, 60.0])         # shrink the macro sweep for the test
    win._sweep_ring_len = 300.0
    win._sweep_steps = 60
    win._run_ring()
    qx, _ = win._meso_page.fundamental_diagram._q_curve.getData()
    assert qx is not None and len(qx) == 2                # two density points on Q(rho)


def test_simapp_meso_scenario_selector(qapp):
    win = SimApp(CHAMP)
    assert win._meso_page._scenario_sel.count() == win.scenario_count()   # mirrors the library
    win._meso_page._scenario_sel.setCurrentIndex(1)
    assert win._meso_page.selected_scenario_index() == 1
    win.set_mode(1); win._meso_page._n_spin.setValue(4)
    win._run_platoon()                                                     # uses scenario 1's v_leader
    st = win._meso_page.space_time._curves
    assert len([c for c in st if c.getData()[0] is not None and len(c.getData()[0]) > 0]) == 4


def test_simapp_run_platoon_feeds_road(qapp):
    win = SimApp(CHAMP)
    win.set_mode(1); win._meso_page._n_spin.setValue(5)
    win._run_platoon()
    assert len(win._meso_page.road._cars) == 5           # road built with one car per vehicle
    win._meso_page.road._play_btn.setChecked(True)
    assert win._meso_page.road._timer.isActive()
    win.set_mode(0)                                       # returning to Live stops the playback
    assert not win._meso_page.road._timer.isActive()


def test_simapp_end_of_episode_no_eager_reconstruct(qapp):
    # root-cause guard: the AUTOMATIC end-of-episode stop must NOT run the synchronous deep-scrub
    # reconstruct (that froze the GUI ~0.8s+). Manual pause still reconstructs (covered separately).
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._run_btn.setChecked(True)         # running (as live)
    win._timer.stop()                     # headless: no real timer
    win._advance(51.0)                     # >500 ticks -> ring buffer wraps
    assert win.loop.stepper.st.t > win._probe.capacity
    win._auto_stopping = True              # exactly what _on_timer sets when loop.done
    win._run_btn.setChecked(False)         # -> _on_run_toggled(False), auto-stop path
    assert win._src_probe is win._probe    # scrub source stays LIVE (no eager reconstruct)
    assert win._recon_key is None          # reconstruct never ran -> no GUI freeze


def test_simapp_dock_maximize_toggle(qapp):
    win = SimApp(CHAMP)
    n0 = len(visible_docks(win._area))
    assert n0 >= 10 and win._maximized is None
    win._toggle_maximize("Road")                   # double-click title -> maximize
    assert win._maximized == "Road"
    assert visible_docks(win._area) == {"Road"}     # only that dock fills the area
    win._toggle_maximize("Road")                   # double-click again -> restore
    assert win._maximized is None
    assert len(visible_docks(win._area)) == n0      # previous arrangement restored


def test_simapp_feeds_episode_summary(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    assert win._episode.summary()["n_ticks"] == 0        # reset on scenario select
    win._advance(0.5)                                     # a few live ticks
    s = win._episode.summary()
    assert s["n_ticks"] >= 5 and s["min_gap"] < float("inf") and s["ann_pj"] > 0


def test_simapp_postrun_mode(qapp):
    win = SimApp(CHAMP)
    assert win._mode_stack.count() == 3                  # Live + Meso/Macro + Post-run
    win.select_scenario(0)
    win._advance(0.5)
    win.set_mode(2)                                       # Post-run
    assert win._mode_stack.currentIndex() == 2
    assert not win._run_btn.isChecked()                  # entering an analysis mode pauses live
    assert win._champ_name in win._postrun_page._header.text()
    assert win._postrun_page._values["min_gap"].text() not in ("—", "")   # report card populated


def test_simapp_export_csv_and_png(qapp, tmp_path):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    csv_p = tmp_path / "episode.csv"
    win._do_export_csv(str(csv_p))
    lines = csv_p.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("t,gap,v") and len(lines) >= 6      # header + >=5 rows
    win.resize(800, 600)
    png_p = tmp_path / "shot.png"
    win._do_export_png(str(png_p))
    assert png_p.exists() and png_p.stat().st_size > 0


def test_simapp_has_synops_dock(qapp):
    win = SimApp(CHAMP)
    assert "SynOps" in win._docks and len(win._docks) == 14
    assert win._synops._dims == (4, 32, 5, 8)
    assert abs(win._synops._ann_pj - (128 + 1024 + 160) * 4.6) < 1e-6          # R33 dense-ANN energy (pJ)
    win.select_scenario(0)
    win._advance(0.5)
    y = win._synops._total_c.getData()[1]
    assert y is not None and y.size > 0 and float(y[-1]) >= 128               # >= static floor
