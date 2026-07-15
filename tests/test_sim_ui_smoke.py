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
    assert set(win._docks.keys()) == set(DOCK_ORDER)     # Road/NetState/SpikeRate/Trajectory/Safety/Events/Inspector/SynOps + 5 params
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
    win._set_dock_visible("Trajectory", False)
    assert "Trajectory" not in visible_docks(win._area)
    win._set_dock_visible("Trajectory", True)
    assert "Trajectory" in visible_docks(win._area)


def test_simapp_apply_preset(qapp):
    win = SimApp(CHAMP)
    win.apply_preset("Identificazione")
    assert "NetState" not in visible_docks(win._area)
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


# --- oracle ghost on the road ---
def test_topdown_ghost_x_integrates_and_resets(qapp):
    from config import DT
    view = TopDownView()
    for _ in range(10):
        view.update_ghost(_stepv(s=24.0, v=19.0))
    assert abs(view.ghost_x_m() - 10 * 19.0 * DT) < 1e-6
    view.reset()
    assert view.ghost_x_m() == 0.0               # else the ghost drives off across episodes


def test_topdown_ghost_hidden_by_default_and_toggleable(qapp):
    view = TopDownView()
    assert view._ghost.isVisible() is False
    view.set_ghost_visible(True)
    assert view._ghost.isVisible() is True
    view.set_ghost_visible(False)
    assert view._ghost.isVisible() is False


def test_topdown_render_ghost_at_reconstructs(qapp):
    from config import DT
    view = TopDownView()
    vs = [10.0, 12.0, 8.0, 15.0]
    tb = _traj_seq(vs, [30.0, 28.0, 26.0, 24.0])
    view.render_ghost_at(tb, 2)                  # x = sum of v*DT up to index 2 inclusive
    assert abs(view.ghost_x_m() - float(np.cumsum(vs)[2] * DT)) < 1e-6
    view.render_ghost_at(tb, -1)                 # head
    assert abs(view.ghost_x_m() - float(np.sum(vs) * DT)) < 1e-6


def test_topdown_ghost_is_independent_of_the_ego(qapp):
    """The two integrate separately: advancing one must not move the other."""
    view = TopDownView()
    view.update_frame(_stepv(s=30.0, v=20.0))
    ego_before = view.ego_x_m()
    view.update_ghost(_stepv(s=24.0, v=19.0))
    assert view.ego_x_m() == ego_before
    assert view.ghost_x_m() != ego_before


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
    assert len(win._docks) == 13     # 8 fixed docks + 5 param docks


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
    assert win._mode_stack.count() == 4                  # Live + Meso/Macro + Post-run + Scenari
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


def test_simapp_maximize_restores_exact_preset_set(qapp):
    # Regression (the "soft-lock"): under a preset that hides docks, maximize+restore must re-show
    # EXACTLY the pre-maximize set. The old restore re-added the FULL DOCK_ORDER, and restoreState
    # leaves docks it doesn't mention in place -> the hidden docks reappear (12 -> 14) and clutter the
    # layout so other title bars are hard to hit ("can only ever re-maximize that one"). The clean
    # restore keeps the layout intact, so a DIFFERENT dock still maximizes afterwards.
    win = SimApp(CHAMP)
    win.apply_preset("Neuro-debug")
    before = visible_docks(win._area)
    assert "Trajectory" not in before and "Safety" not in before   # preset hid these two
    win._toggle_maximize("Road")
    assert visible_docks(win._area) == {"Road"}
    win._toggle_maximize("Road")
    assert visible_docks(win._area) == before        # preset-hidden docks stay hidden (no drift)
    win._toggle_maximize("SpikeRate")                # a DIFFERENT dock still maximizes after restore
    assert visible_docks(win._area) == {"SpikeRate"}
    win._toggle_maximize("SpikeRate")
    assert visible_docks(win._area) == before


def test_simapp_feeds_episode_summary(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    assert win._episode.summary()["n_ticks"] == 0        # reset on scenario select
    win._advance(0.5)                                     # a few live ticks
    s = win._episode.summary()
    assert s["n_ticks"] >= 5 and s["min_gap"] < float("inf") and s["ann_pj"] > 0


def test_simapp_postrun_mode(qapp):
    win = SimApp(CHAMP)
    assert win._mode_stack.count() == 4                  # Live + Meso/Macro + Post-run + Scenari
    win.select_scenario(0)
    win._advance(0.5)
    win.set_mode(2)                                       # Post-run
    assert win._mode_stack.currentIndex() == 2
    assert not win._run_btn.isChecked()                  # entering an analysis mode pauses live
    assert win._champ_name in win._postrun_page._subtitle.text()
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


def test_simapp_episode_has_gt_and_rho(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    s = win._episode.summary()
    assert "id_accuracy" in s and s["rho"] is not None      # GT + model wired into the accumulator


def test_simapp_has_synops_dock(qapp):
    win = SimApp(CHAMP)
    assert "SynOps" in win._docks and len(win._docks) == 13
    assert win._synops._dims == (4, 32, 5, 8)
    assert abs(win._synops._ann_pj - (128 + 1024 + 160) * 4.6) < 1e-6          # R33 dense-ANN energy (pJ)
    win.select_scenario(0)
    win._advance(0.5)
    y = win._synops._total_c.getData()[1]
    assert y is not None and y.size > 0 and float(y[-1]) >= 128               # >= static floor


def _empty(curve):
    x = curve.getData()[0]
    return x is None or len(x) == 0


def test_simapp_reset_clears_cockpit_panels(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(2.0)                                        # populate the param/trajectory curves
    assert not _empty(win._params[0]._curve)                # (sanity: they DID fill)
    win.reset_run()                                         # Reset must visibly blank the plots
    assert _empty(win._params[0]._curve)                    # param curve cleared
    assert _empty(win._trajectory._c_s)                     # trajectory cleared
    assert _empty(win._spikerate._curve)                    # spike-rate cleared
    assert win._topdown.ego_x_m() == 0.0                    # road ego integrator reset


def test_simapp_topdown_resets_across_scenarios(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(3.0)
    assert win._topdown.ego_x_m() > 0.0                     # ego advanced down the road
    win.select_scenario(1)                                  # swapping scenario resets the integrator
    assert win._topdown.ego_x_m() == 0.0                    # ...so the car never drives off the finite road


def test_simapp_run_platoon_reenables_button(qapp):
    win = SimApp(CHAMP)
    win.set_mode(1); win._meso_page._n_spin.setValue(4)
    win._run_platoon()
    assert win._meso_page._run_platoon_btn.isEnabled()      # busy-guard restores the button in finally


def test_simapp_hidden_dock_skips_redraw(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._set_dock_visible("SpikeRate", False)              # hide the spike-rate dock
    win._advance(1.0)
    assert _empty(win._spikerate._curve)                  # hidden -> its plot data is NOT recomputed
    win._set_dock_visible("SpikeRate", True)              # re-show it
    win._advance(1.0)
    assert not _empty(win._spikerate._curve)              # visible again -> updates


# --- oracle ghost: app wiring + toggle ---
def test_app_builds_a_ghost_and_toggle_is_off_by_default(qapp):
    win = SimApp(CHAMP)
    assert win.loop.ghost is not None
    assert win.loop.ghost.backend is None            # it IS the oracle, not a second net
    assert win._ghost_toggle.isChecked() is False
    assert win._topdown._ghost.isVisible() is False


def test_app_toggle_shows_ghost_on_road_and_panels(qapp):
    win = SimApp(CHAMP)
    win._advance(1.0)
    win._ghost_toggle.setChecked(True)
    assert win._topdown._ghost.isVisible() is True
    assert len(win._trajectory._g_s.getOriginalDataset()[1]) > 0
    assert len(win._safety._g_ttc.getOriginalDataset()[1]) > 0
    win._ghost_toggle.setChecked(False)
    assert win._topdown._ghost.isVisible() is False
    d = win._trajectory._g_s.getOriginalDataset()[1]
    assert d is None or len(d) == 0


def test_app_ghost_and_net_stay_in_lockstep_while_running(qapp):
    win = SimApp(CHAMP)
    win._advance(2.0)
    assert win.loop.ghost.st.t == win.loop.stepper.st.t
    assert len(win._ghost_traj) == len(win._traj)


def test_app_ghost_scrub_source_swaps_with_the_others(qapp):
    """TEETH: if _src_ghost_traj is not swapped together with _src_probe/_src_traj, a deep scrub
    renders the oracle from the live tail against a past net state -- a plausible-looking lie."""
    win = SimApp(CHAMP)
    win._ghost_toggle.setChecked(True)
    win._advance(70.0)                               # > 500 ticks -> the ring buffer wraps
    win._run_btn.setChecked(True)
    win._run_btn.setChecked(False)                   # manual pause -> deep reconstruct
    assert win._src_traj is not win._traj            # reconstruction really happened
    assert win._src_ghost_traj is not win._ghost_traj
    assert len(win._src_ghost_traj.arrays()["t"]) == len(win._src_traj.arrays()["t"])


def test_app_reset_blanks_the_ghost(qapp):
    win = SimApp(CHAMP)
    win._ghost_toggle.setChecked(True)
    win._advance(1.0)
    win.reset_run()
    d = win._trajectory._g_s.getOriginalDataset()[1]
    assert d is None or len(d) == 0
    assert win._topdown.ghost_x_m() == 0.0


# --- checkpoint identity: file browser + honest header ---
def test_app_header_states_the_real_identity_not_a_guess(qapp):
    win = SimApp(CHAMP)
    h = win._header.text()
    assert "Raffaello" in h                       # this one really IS Raffaello
    assert "baseline" in h and "32" in h          # family + topology stated
    assert "max_delay" in h and "inferito" in h   # and the PROVENANCE of max_delay


def test_app_open_champion_from_an_arbitrary_path(qapp, tmp_path):
    """A .pt outside champions/ must load AND leave the selector usable -- today
    _champ_root = dirname(dirname(path)) empties it."""
    import shutil
    p = tmp_path / "altrove" / "best_model.pt"
    p.parent.mkdir(parents=True)
    shutil.copy(CHAMP, p)
    win = SimApp(CHAMP)
    ok, msg = win.open_champion_path(str(p))
    assert ok is True, msg
    assert win._champ_selector.count() >= 5       # 4 bundled + the opened one
    win._advance(0.2)                             # and it runs


def test_app_bad_checkpoint_leaves_the_cockpit_standing(qapp, tmp_path):
    """Today load_champion has no try/except (app.py:58): a bad .pt kills the GUI."""
    bad = tmp_path / "rubbish.pt"
    bad.write_bytes(b"not a torch file")
    win = SimApp(CHAMP)
    before = win._champ_name
    ok, msg = win.open_champion_path(str(bad))
    assert ok is False and msg                    # reason reported, no exception
    assert win._champ_name == before              # the running champion is untouched
    win._advance(0.2)                             # and the cockpit still runs


def test_app_unsupported_variant_is_refused_by_name(qapp, tmp_path):
    import torch
    from core.network import build_model
    p = tmp_path / "attn.pt"
    torch.save({"epoch": 0, "val_loss": 0.0, "model_state": build_model("attn").state_dict(),
                "optim_state": {}}, p)
    win = SimApp(CHAMP)
    ok, msg = win.open_champion_path(str(p))
    assert ok is False and "attn" in msg          # named, not "unknown", not "Raffaello"


# --- scenario builder: the fourth mode ---
def test_app_has_a_fourth_mode(qapp):
    win = SimApp(CHAMP)
    assert win._mode_sel.count() == 4
    assert win._mode_sel.itemText(3) == "Scenari"
    win.set_mode(3)                                   # must not raise
    assert win._mode_stack.currentIndex() == 3


def test_scenario_page_preview_is_the_real_materialised_profile(qapp):
    """The preview must come from the same function the sim will run -- not a sketch."""
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec, materialise
    from sim.ui.scenario_page import ScenarioPage
    page = ScenarioPage(params_gt=np.array([30.0, 1.5, 2.0, 1.5, 1.5]), N=600)
    spec = ScenarioSpec(name="x", blocks=(Block("ramp", 600, {"to_v": 2.0}),),
                        style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)
    page.set_spec(spec)
    shown = page._curve.getOriginalDataset()[1]
    expected = materialise(spec, page._params_gt, page._N).v_leader
    np.testing.assert_array_equal(shown, expected)


def test_scenario_page_style_pad_redraws_the_preview(qapp):
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    from sim.ui.scenario_page import ScenarioPage
    page = ScenarioPage(params_gt=np.array([30.0, 1.5, 2.0, 1.5, 1.5]), N=600)
    page.set_spec(ScenarioSpec(name="x", blocks=(Block("ramp", 600, {"to_v": 2.0}),),
                               style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0))
    before = page._curve.getOriginalDataset()[1].copy()
    page.set_style(4.0, 9.0)                          # what dragging the pad calls
    after = page._curve.getOriginalDataset()[1]
    assert not np.array_equal(before, after)          # live: the curve really moved


def test_scenario_page_emits_the_built_scenario(qapp):
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    from sim.ui.scenario_page import ScenarioPage
    page = ScenarioPage(params_gt=np.array([30.0, 1.5, 2.0, 1.5, 1.5]), N=600)
    got = []
    page.sigScenarioBuilt.connect(got.append)
    page.set_spec(ScenarioSpec(name="mio", blocks=(Block("const", 600, {"v": 15.0}),),
                               style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0))
    page._on_use()
    assert len(got) == 1 and got[0].name == "mio"
    assert got[0].v_leader.shape == (600,)


def test_app_use_scenario_appends_it_to_the_live_selector(qapp):
    win = SimApp(CHAMP)
    before = win._selector.count()
    win.set_mode(3)
    win._scenario_page.set_style(4.0, 9.0)
    win._scenario_page._on_use()
    assert win._selector.count() == before + 1
    assert win.scenario_count() == before + 1
    win._advance(0.2)                                 # and the built scenario actually runs


def test_scenario_page_pad_never_disagrees_with_the_curve(qapp):
    """TEETH: the dot and the spec are two views of one state. set_style used to redraw the curve
    WITHOUT moving the dot, so a programmatic style change left the pad pointing at the old
    quadrant -- caught by looking at a render, not by a test: the old test only checked the curve."""
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    from sim.ui.scenario_page import ScenarioPage
    page = ScenarioPage(params_gt=np.array([30.0, 1.5, 2.0, 1.5, 1.5]), N=600)
    page.set_spec(ScenarioSpec(name="x", blocks=(Block("ramp", 600, {"to_v": 2.0}),),
                               style=LeaderStyle(1.4, 8.4), s_init=33.5, v_init=21.0))
    page.set_style(3.6, 1.6)
    assert (page._pad._a, page._pad._b) == (3.6, 1.6)          # the dot followed
    assert (page._spec.style.a_max, page._spec.style.b_max) == (3.6, 1.6)
