"""SimApp -- main window: a dockable workspace (pyqtgraph DockArea) of 8 graphs (Road, Raster, v_mem,
and the 5 identified params) + champion/scenario controls + View/Layout menus (presets + persistence),
driven by a fixed-timestep QTimer loop, with a status bar (incl. network firing %)."""
import os

import numpy as np
from PySide6.QtCore import QElapsedTimer, QEvent, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QSlider, QStackedWidget, QVBoxLayout, QWidget)
from pyqtgraph.dockarea import Dock, DockArea

from config import DT
from sim.backend import SoftwareBackend
from sim.events import EventInjector
from sim.replay import ReplayLog
from sim.probe import AttributeProbe
from sim.scenario import manual_scenario, scenario_library
from sim.stepper import SimStepper
from sim.ui.layout import (DOCK_ORDER, LAYOUT_PATH, PRESETS, apply_overview, load_layout,
                           save_layout, visible_docks)
from sim.ui.loop import SimLoop
from sim.ui.panels import (PARAM_COLORS, PARAM_NAMES, PARAM_UNITS, EventTimelinePanel,
                           NeuronGraphPanel, NeuronInspectorPanel, ParamPanel, SafetyPanel,
                           SpikeRatePanel, SynOpsPanel, TrajectoryPanel, VmemPanel)
from sim.ui.meso_page import MesoMacroPage
from sim.ui.postrun_page import PostRunPage
from sim.ui.platoon import platoon_metrics, run_fundamental_diagram, run_platoon
from sim.ui.episode import EpisodeSummary, write_episode_csv
from sim.ui.reconstruct import reconstruct_spliced
from sim.ui.trajectory import TrajectoryBuffer
from sim.ui.topdown import TopDownView
from utils.champion_io import load_champion

_UI_FPS_MS = 33
_REDRAW_MS = 66           # throttle the heavy 14-panel repaint to ~15fps while running (physics/Road stay 30fps)
_MAX_FRAME_DT = 0.1        # clamp real-time elapsed so a lagged frame can't cascade into a huge step-batch
_PARAMS_GT = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
_CHAMPIONS = [            # (nickname, dir, method) — mapping from scripts/build_fpga_report.py
    ("Raffaello", "R33_C2_A1_T12_fix", "BPTT"),
    ("Leonardo", "LS3_PEAK_R0_launch_d03", "BPTT"),
    ("Donatello", "PE_t05_gp0002", "EventProp"),
    ("Michelangelo", "A_lr1e2_t06_r16", "EventProp"),
]


class SimApp(QMainWindow):
    def __init__(self, champion_path, layout_path=None):
        super().__init__()
        self.setWindowTitle("CF_FSNN Simulator")
        self._champ_root = os.path.dirname(os.path.dirname(champion_path))
        self._champions = [(nick, d) for nick, d, _ in _CHAMPIONS
                           if os.path.isfile(os.path.join(self._champ_root, d, "best_model.pt"))]
        _launched = os.path.basename(os.path.dirname(champion_path))
        self._champ_idx = next((i for i, (_, d) in enumerate(self._champions) if d == _launched), 0)
        self._champ = load_champion(champion_path)
        self._champ_name = self._champions[self._champ_idx][0] if self._champions else _launched
        self._scenarios = scenario_library(_PARAMS_GT, N=600,
                                            rng=np.random.default_rng(0), include_tail=True)
        self._scenarios.append(self._manual(_PARAMS_GT))
        self._current_idx = 0
        self._speed = 1
        self._last_result = None
        self._cursor = None

        self._topdown = TopDownView()
        self._netstate = NeuronGraphPanel()
        self._spikerate = SpikeRatePanel()
        self._vmem = VmemPanel()
        self._trajectory = TrajectoryPanel()
        self._safety = SafetyPanel()
        self._timeline = EventTimelinePanel()
        self._inspector = NeuronInspectorPanel()
        self._synops = SynOpsPanel()
        self._params = [ParamPanel(i, n, u, c)
                        for i, (n, u, c) in enumerate(zip(PARAM_NAMES, PARAM_UNITS, PARAM_COLORS))]
        for p in self._params[1:]:
            p.plot_item.setXLink(self._params[0].plot_item)
        # NB: SpikeRate is intentionally NOT X-linked to the params — in tab-stacked presets a linked
        # param can be a hidden tab, whose stale range would corrupt SpikeRate's axis. A unified time
        # cursor is a Phase-3b (scrub) concern; here each time-series autoranges to its own data.
        self._ts_panels = [*self._params, self._vmem, self._spikerate, self._trajectory,
                           self._safety, self._timeline, self._inspector, self._synops]
        self._apply_champion_topology()              # topology into NetState/Inspector/SynOps (re-run on swap)
        self._timeline.set_on_seek(self._seek_to)
        self._netstate.sigNeuronClicked.connect(self._on_neuron_selected)
        self._src_probe = None
        self._src_traj = None
        self._recon_key = None      # cache key for the last deep-scrub reconstruction
        self._auto_stopping = False  # set when the episode ends on its own -> stop WITHOUT eager reconstruct

        widgets = {"Road": self._topdown, "NetState": self._netstate, "SpikeRate": self._spikerate,
                   "v_mem": self._vmem, "Trajectory": self._trajectory, "Safety": self._safety,
                   "Events": self._timeline, "Inspector": self._inspector, "SynOps": self._synops,
                   "v0": self._params[0], "T": self._params[1],
                   "s0": self._params[2], "a": self._params[3], "b": self._params[4]}
        self._area = DockArea()
        self._docks = {}
        for name in DOCK_ORDER:
            d = Dock(name, closable=True)
            d.addWidget(widgets[name])
            d.sigClosed.connect(lambda *_, n=name: self._on_dock_closed(n))
            d.label.installEventFilter(self)      # double-click the title bar -> maximize / restore
            self._docks[name] = d
        self._maximized = None                    # name of the currently maximized dock, or None
        self._pre_max_state = None                # DockArea state saved before maximizing (for restore)
        apply_overview(self._area, self._docks)   # place all docks so restoreState can find them
        self._episode = EpisodeSummary(self._synops._dims)   # per-episode aggregator (post-run seal + CSV)

        self._champ_selector = QComboBox()
        self._champ_selector.addItems([nick for nick, _ in self._champions])
        if self._champions:
            self._champ_selector.setCurrentIndex(self._champ_idx)
        self._champ_selector.currentIndexChanged.connect(self.select_champion)
        self._selector = QComboBox()
        self._selector.addItems([s.name for s in self._scenarios])
        self._run_btn = QPushButton("Run"); self._run_btn.setCheckable(True)
        self._run_btn.toggled.connect(self._on_run_toggled)
        self._step_btn = QPushButton("Step"); self._step_btn.clicked.connect(self.step_once)
        self._reset_btn = QPushButton("Reset"); self._reset_btn.clicked.connect(self.reset_run)
        self._brake_btn = QPushButton("Brake leader"); self._brake_btn.clicked.connect(self.inject_brake)
        self._speed_slider = QSlider(Qt.Horizontal); self._speed_slider.setRange(1, 8)
        self._speed_slider.setValue(1); self._speed_slider.setFixedWidth(90)
        self._speed_slider.valueChanged.connect(self._on_speed)
        self._cursor_slider = QSlider(Qt.Horizontal); self._cursor_slider.setEnabled(False)
        self._cursor_slider.setFixedWidth(160)
        self._cursor_slider.valueChanged.connect(self._on_cursor)
        self._cursor_readout = QLabel("live")
        controls = QHBoxLayout()
        for w in (QLabel("champion"), self._champ_selector, self._selector,
                  self._run_btn, self._step_btn, self._reset_btn,
                  self._brake_btn, QLabel("speed"), self._speed_slider,
                  QLabel("t"), self._cursor_slider, self._cursor_readout):
            controls.addWidget(w)

        self._header = QLabel()
        root = QVBoxLayout()
        root.addWidget(self._header)
        root.addLayout(controls)
        root.addWidget(self._area, stretch=1)
        container = QWidget(); container.setLayout(root)
        self._meso_page = MesoMacroPage([s.name for s in self._scenarios])
        self._meso_page._scenario_sel.setCurrentIndex(self._current_idx)
        self._meso_page._on_run_platoon = self._run_platoon
        self._meso_page._on_run_ring = self._run_ring
        self._sweep_densities = np.linspace(10.0, 120.0, 12)   # veh/km — macro ring-sweep grid
        self._sweep_ring_len = 1000.0                          # m
        self._sweep_steps = 600
        self._postrun_page = PostRunPage()
        self._mode_stack = QStackedWidget()
        self._mode_stack.addWidget(container)          # page 0: Live cockpit
        self._mode_stack.addWidget(self._meso_page)    # page 1: Meso/Macro analysis
        self._mode_stack.addWidget(self._postrun_page) # page 2: Post-run report card
        self._mode_sel = QComboBox(); self._mode_sel.addItems(["Live", "Meso/Macro", "Post-run"])
        self._mode_sel.currentIndexChanged.connect(self.set_mode)
        outer = QVBoxLayout(); outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._mode_sel)
        outer.addWidget(self._mode_stack, stretch=1)
        shell = QWidget(); shell.setLayout(outer)
        self.setCentralWidget(shell)
        self._status = self.statusBar()

        self._build_menus()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._clock = QElapsedTimer()
        self._redraw_clock = QElapsedTimer()
        self._redraw_clock.start()

        self.select_scenario(0)
        self._selector.currentIndexChanged.connect(self.select_scenario)

        if layout_path:
            load_layout(self._area, self._docks, layout_path)
        self._sync_view_actions()

    # ---- menus / docks ----
    def _build_menus(self):
        view = self.menuBar().addMenu("View")
        self._view_actions = {}
        for name in DOCK_ORDER:
            a = QAction(name, self, checkable=True)
            a.setChecked(True)
            a.toggled.connect(lambda vis, n=name: self._set_dock_visible(n, vis))
            view.addAction(a)
            self._view_actions[name] = a
        layout_menu = self.menuBar().addMenu("Layout")
        for name in PRESETS:
            a = QAction(name, self)
            a.triggered.connect(lambda _=False, n=name: self.apply_preset(n))
            layout_menu.addAction(a)
        layout_menu.addSeparator()
        a_save = QAction("Save layout", self); a_save.triggered.connect(self._save_layout)
        a_reset = QAction("Reset to saved", self); a_reset.triggered.connect(self._load_saved)
        layout_menu.addAction(a_save); layout_menu.addAction(a_reset)

    def apply_preset(self, name):
        self._maximized = None                # a preset redefines the layout -> clear any maximize state
        PRESETS[name](self._area, self._docks)
        self._sync_view_actions()

    def _set_dock_visible(self, name, visible):
        present = name in visible_docks(self._area)
        if visible and not present:
            self._area.addDock(self._docks[name], "right")
        elif not visible and present:
            self._docks[name].close()
        self._sync_view_actions()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonDblClick:
            for name, d in self._docks.items():
                if d.label is obj:                        # double-click on a dock title bar
                    self._toggle_maximize(name)
                    return True
        return super().eventFilter(obj, event)

    def _toggle_maximize(self, name):
        """Fill the whole area with one dock (double-click its title); double-click again to restore."""
        if self._maximized is None:
            self._pre_max_state = self._area.saveState()
            self._maximized = name
            for other in list(visible_docks(self._area)):
                if other != name:
                    self._docks[other].close()
        else:
            self._maximized = None
            for other in DOCK_ORDER:                       # re-add closed docks so restoreState can find them
                if other not in visible_docks(self._area):
                    self._area.addDock(self._docks[other], "right")
            try:
                self._area.restoreState(self._pre_max_state)
            except Exception:                              # pyqtgraph 0.14 restoreState bug -> safe fallback
                apply_overview(self._area, self._docks)
            self._sync_view_actions()

    def _on_dock_closed(self, name):
        a = getattr(self, "_view_actions", {}).get(name)
        if a is not None:
            a.blockSignals(True); a.setChecked(False); a.blockSignals(False)

    def _sync_view_actions(self):
        vis = visible_docks(self._area)
        for name, a in getattr(self, "_view_actions", {}).items():
            a.blockSignals(True); a.setChecked(name in vis); a.blockSignals(False)

    def _save_layout(self):
        try:
            save_layout(self._area, LAYOUT_PATH)
            self._status.showMessage(f"layout saved to {LAYOUT_PATH}", 3000)
        except OSError as e:
            self._status.showMessage(f"save failed: {e}", 5000)

    def _load_saved(self):
        load_layout(self._area, self._docks, LAYOUT_PATH)
        self._sync_view_actions()

    # ---- scenario / loop ----
    @staticmethod
    def _manual(pg):
        v_set = 0.7 * float(pg[0])
        return manual_scenario(pg, np.full(600, v_set),
                               s_init=float(pg[2]) + v_set * float(pg[1]), v_init=v_set)

    def scenario_count(self) -> int:
        return len(self._scenarios)

    def _apply_champion_topology(self):
        """Push the current champion's weights into the topology-driven docks (NetState / Inspector /
        SynOps). Re-run on every champion swap: families differ (BPTT rank-8, EventProp rank-16)."""
        topo = SoftwareBackend(self._champ.model)
        topo.reset()
        w = topo.read_weights()
        self._netstate.set_topology(w["w_in"], w["w_rec"], w["w_out"])
        self._inspector.set_topology(w["w_in"], w["w_rec"], w["w_out"])
        self._synops.set_model(w["w_in"].shape[1], w["w_in"].shape[0], w["w_out"].shape[0], w["rank"])

    def select_champion(self, idx: int):
        if not self._champions:
            return
        self._champ_idx = max(0, min(int(idx), len(self._champions) - 1))
        nick, dirname = self._champions[self._champ_idx]
        self._champ = load_champion(os.path.join(self._champ_root, dirname, "best_model.pt"))
        self._champ_name = nick
        if self._champ_selector.currentIndex() != self._champ_idx:
            self._champ_selector.blockSignals(True)
            self._champ_selector.setCurrentIndex(self._champ_idx)
            self._champ_selector.blockSignals(False)
        self._apply_champion_topology()
        self.select_scenario(self._current_idx)   # rebuild stepper/probe with the new backend + refresh header

    def set_mode(self, idx: int):
        idx = int(idx)
        if idx != 0:
            self._auto_stopping = True             # leaving Live is not a scrub -> skip the eager reconstruct
            self._run_btn.setChecked(False)        # pause the live sim when entering an analysis mode
        if idx != 1:
            self._meso_page.road.stop()            # road playback only lives on the Meso page
        if idx == 2:
            self._postrun_page.set_summary(self._episode.summary(), self._episode.rows(),
                                           self._champ_name, self._scenarios[self._current_idx].name)
        self._mode_stack.setCurrentIndex(idx)
        if self._mode_sel.currentIndex() != idx:
            self._mode_sel.blockSignals(True)
            self._mode_sel.setCurrentIndex(idx)
            self._mode_sel.blockSignals(False)

    def _run_platoon(self):
        n = self._meso_page.n_vehicles()
        sc = self._scenarios[self._meso_page.selected_scenario_index()]
        rec = run_platoon(self._champ, _PARAMS_GT, n, sc.v_leader)
        m = platoon_metrics(rec)
        self._meso_page.string_stability.set_metrics(m)
        self._meso_page.space_time.set_rec(rec)
        self._meso_page.speed_wave.set_rec(rec)
        self._meso_page.road.set_run(rec)

    def _run_ring(self):
        pts = run_fundamental_diagram(self._champ, _PARAMS_GT, self._sweep_densities,
                                      ring_length=self._sweep_ring_len, n_steps=self._sweep_steps)
        self._meso_page.fundamental_diagram.set_points(pts)

    def select_scenario(self, idx: int):
        self._current_idx = int(idx)
        if self._selector.currentIndex() != self._current_idx:
            self._selector.blockSignals(True)
            self._selector.setCurrentIndex(self._current_idx)
            self._selector.blockSignals(False)
        sc = self._scenarios[self._current_idx]
        self._injector = EventInjector()
        self._probe = AttributeProbe(capacity=500, sample_every=1)
        self._traj = TrajectoryBuffer()
        self._src_probe = self._probe                     # scrub source: live buffer while running
        self._src_traj = self._traj
        self._recon_key = None                            # invalidate the reconstruction cache
        self._episode = EpisodeSummary(self._synops._dims)   # fresh per-scenario summary (refreshes dims on swap)
        backend = SoftwareBackend(self._champ.model)
        stepper = SimStepper.from_scenario(backend, sc, injector=self._injector)
        self.loop = SimLoop(stepper, self._probe, dt_fixed=DT)
        self._last_result = None
        self._header.setText(f"champion: {self._champ_name}    |    scenario: {sc.name}")
        for i, p in enumerate(self._params):
            p.set_ground_truth(float(sc.params_gt[i]))
        self._inspector.set_neuron(None)                  # clear selection + graph highlight on scenario change
        self._netstate.highlight(None)
        self._refresh_status()

    def reset_run(self):
        self.select_scenario(self._current_idx)

    def step_once(self):
        self._paint(self.loop.tick(DT))

    def inject_brake(self):
        st = self.loop.stepper.st
        base_vl = float(self.loop.stepper.v_leader[min(st.t, self.loop.stepper.N - 1)])
        self._injector.enqueue(st.t, "brake_leader", target_v=max(0.3 * base_vl, 2.0), duration=20)

    def _advance(self, frame_dt: float):
        results = self.loop.tick(frame_dt * self._speed)
        self._paint(results)
        return results

    def _paint(self, results):
        if results:
            self._last_result = results[-1]
            self._src_probe, self._src_traj = self._probe, self._traj   # live advanced -> scrub source = live
            for r in results:                                           # integrate EVERY tick (speed>1 -> many)
                self._topdown.update_frame(r)                           # Road stays smooth at full rate
                self._traj.record(r)
            for r, f in zip(results, self._probe.frames()[-len(results):]):
                self._episode.update(r, f.spikes)                       # feed the post-run summary
            running = self._run_btn.isChecked()
            if (not running) or self._redraw_clock.elapsed() >= _REDRAW_MS:   # throttle the heavy repaint while live
                self._redraw_series(self._probe, self._traj)
                self._redraw_clock.restart()
                if running:                               # live: slider tracks the head
                    self._cursor_slider.blockSignals(True)
                    self._cursor_slider.setRange(0, max(0, self._buf_len() - 1))
                    self._cursor_slider.setValue(max(0, self._buf_len() - 1))
                    self._cursor_slider.blockSignals(False)
        self._refresh_status()

    def _redraw_series(self, probe, traj):
        for p in self._params:
            p.update_frame(probe)
        self._vmem.update_frame(probe)
        self._spikerate.update_frame(probe)
        self._synops.update_frame(probe)
        self._trajectory.update_frame(traj)
        self._safety.update_frame(traj)
        self._netstate.update_frame(probe)                # head; scrub overrides via _render_at_cursor
        self._timeline.update_events(self._injector.log(), probe.frames())
        if self._inspector.neuron is not None:
            self._inspector.update_frame(probe)

    def status_text(self) -> str:
        st = self.loop.stepper.st
        r = self._last_result
        ego = r.v if r is not None else st.v
        leader = r.vl if r is not None else float(self.loop.stepper.v_leader[0])
        gap = r.s if r is not None else st.s
        state = "COLLIDED" if st.collided else "ok"
        frames = self._probe.frames()          # O(1) tail read (memoized) instead of stacking the buffer
        firing = f"{float(frames[-1].spikes.mean()) * 100:.1f}%" if frames else "--"
        return (f"t={st.t} ({st.t * DT:.1f}s)   |   ego {ego:.1f} m/s   |   leader {leader:.1f} m/s"
                f"   |   gap {gap:.1f} m   |   firing {firing}   |   {state}")

    def _refresh_status(self):
        self._status.showMessage(self.status_text())

    def _on_speed(self, v: int):
        self._speed = int(v)

    def _on_run_toggled(self, running: bool):
        if running:                                       # live: hide cursors, disable slider
            self._auto_stopping = False
            self._cursor = None
            self._src_probe, self._src_traj = self._probe, self._traj
            self._cursor_slider.setEnabled(False)
            for p in self._ts_panels:
                p.set_cursor(None)
            self._cursor_readout.setText("live")
            self._clock.restart()
            self._timer.start(_UI_FPS_MS)
        else:                                             # paused: scrub over the whole episode
            self._timer.stop()
            frames = self._probe.frames()
            auto = self._auto_stopping                    # episode ended on its own -> don't freeze on an eager reconstruct
            self._auto_stopping = False
            if (not auto) and frames and frames[-1].t + 1 > self._probe.capacity:   # manual pause + buffer wrapped -> reconstruct
                self._src_probe, self._src_traj = self._reconstruct(frames[-1].t)
            else:
                self._src_probe, self._src_traj = self._probe, self._traj
            self._redraw_series(self._src_probe, self._src_traj)
            n = len(self._src_probe.frames())
            self._cursor_slider.setEnabled(n > 0)
            self._cursor_slider.blockSignals(True)
            self._cursor_slider.setRange(0, max(0, n - 1))
            self._cursor_slider.setValue(max(0, n - 1))
            self._cursor_slider.blockSignals(False)

    def _buf_len(self):
        return len(self._src_probe.frames()) if self._src_probe is not None else 0

    def _render_at_cursor(self, idx):
        frames = self._src_probe.frames()
        if not frames:
            return
        idx = max(0, min(int(idx), len(frames) - 1))
        self._cursor = idx
        for p in self._ts_panels:
            p.set_cursor(idx)
        self._netstate.update_frame(self._src_probe, idx)
        self._topdown.render_at(self._src_traj, idx)
        self._cursor_readout.setText(f"t={frames[idx].t} ({frames[idx].t * DT:.1f}s)")

    def _seek_to(self, tick):
        if self._run_btn.isChecked():
            self._run_btn.setChecked(False)               # pause -> builds the scrub source
        frames = self._src_probe.frames()
        idx = next((i for i, f in enumerate(frames) if f.t == tick), None)
        if idx is None:
            return
        self._render_at_cursor(idx)
        self._cursor_slider.blockSignals(True)
        self._cursor_slider.setValue(idx)
        self._cursor_slider.blockSignals(False)

    def _on_neuron_selected(self, i):
        self._inspector.set_neuron(i)
        self._netstate.highlight(i)
        self._inspector.update_frame(self._src_probe)
        if self._cursor is not None:
            self._inspector.set_cursor(self._cursor)

    def _reconstruct(self, upto):
        """Cached full-episode reconstruction for deep-scrub. Re-running the SNN is ~10 ms/step
        (frozen core) so a whole episode costs seconds; cache by (scenario, tick, #events) so
        repeated pause/resume is instant, and flag the one-off compute in the status bar."""
        key = (self._current_idx, int(upto), len(self._injector.log()))
        if self._recon_key == key:
            return self._recon_probe, self._recon_traj
        self._status.showMessage("ricostruzione episodio…")
        self._status.repaint()
        rlog = ReplayLog.from_injector(self._current_idx, self._injector)
        probe, traj = reconstruct_spliced(self._champ, self._scenarios[self._current_idx], rlog, upto,
                                          self._probe, self._traj)
        self._recon_key, self._recon_probe, self._recon_traj = key, probe, traj
        return probe, traj

    def _on_cursor(self, v):
        if not self._run_btn.isChecked():
            self._render_at_cursor(v)

    def _step_cursor(self, d):
        if self._run_btn.isChecked() or self._buf_len() == 0:
            return
        cur = self._cursor if self._cursor is not None else self._buf_len() - 1
        new = max(0, min(cur + d, self._buf_len() - 1))
        self._render_at_cursor(new)
        self._cursor_slider.blockSignals(True)
        self._cursor_slider.setRange(0, max(0, self._buf_len() - 1))
        self._cursor_slider.setValue(new)
        self._cursor_slider.blockSignals(False)

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key_Space:
            self._run_btn.toggle()
        elif k == Qt.Key_Left:
            self._step_cursor(-1)
        elif k == Qt.Key_Right:
            self._step_cursor(1)
        elif k == Qt.Key_Home and not self._run_btn.isChecked():
            self._cursor_slider.setValue(0)                       # setValue -> valueChanged -> render + syncs slider
        elif k == Qt.Key_End and not self._run_btn.isChecked():
            self._cursor_slider.setValue(self._buf_len() - 1)
        else:
            super().keyPressEvent(event)

    def _clamp_frame_dt(self, elapsed: float) -> float:
        return min(float(elapsed), _MAX_FRAME_DT)   # avoid the spiral of death under load

    def _on_timer(self):
        self._advance(self._clamp_frame_dt(self._clock.restart() / 1000.0))
        if self.loop.done:
            self._auto_stopping = True        # episode ended on its own: stop without the eager-reconstruct freeze
            self._run_btn.setChecked(False)
