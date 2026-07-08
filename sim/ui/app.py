"""SimApp -- main window: champion + scenario selector + run/pause/reset/step + brake-leader
+ speed, wiring SimLoop + TopDownView + NetPanel via a QTimer (fixed-timestep), with a status bar."""
import os

import numpy as np
from PySide6.QtCore import QElapsedTimer, Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QSlider, QVBoxLayout, QWidget)

from config import DT
from sim.backend import SoftwareBackend
from sim.events import EventInjector
from sim.probe import AttributeProbe
from sim.scenario import manual_scenario, scenario_library
from sim.stepper import SimStepper
from sim.ui.loop import SimLoop
from sim.ui.netpanel import NetPanel
from sim.ui.topdown import TopDownView
from utils.champion_io import load_champion

_UI_FPS_MS = 33
_PARAMS_GT = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


class SimApp(QMainWindow):
    def __init__(self, champion_path):
        super().__init__()
        self.setWindowTitle("CF_FSNN Simulator")
        self._champ_name = os.path.basename(os.path.dirname(champion_path))
        self._champ = load_champion(champion_path)
        self._scenarios = scenario_library(_PARAMS_GT, N=600,
                                            rng=np.random.default_rng(0), include_tail=True)
        self._scenarios.append(self._manual(_PARAMS_GT))
        self._current_idx = 0
        self._speed = 1
        self._last_result = None

        self._topdown = TopDownView()
        self._netpanel = NetPanel()

        self._selector = QComboBox()
        self._selector.addItems([s.name for s in self._scenarios])
        self._run_btn = QPushButton("Run")
        self._run_btn.setCheckable(True)
        self._run_btn.toggled.connect(self._on_run_toggled)
        self._step_btn = QPushButton("Step")
        self._step_btn.clicked.connect(self.step_once)
        self._reset_btn = QPushButton("Reset")
        self._reset_btn.clicked.connect(self.reset_run)
        self._brake_btn = QPushButton("Brake leader")
        self._brake_btn.clicked.connect(self.inject_brake)
        self._speed_slider = QSlider(Qt.Horizontal)
        self._speed_slider.setRange(1, 8)
        self._speed_slider.setValue(1)
        self._speed_slider.setFixedWidth(90)
        self._speed_slider.valueChanged.connect(self._on_speed)

        controls = QHBoxLayout()
        for w in (self._selector, self._run_btn, self._step_btn, self._reset_btn,
                  self._brake_btn, QLabel("speed"), self._speed_slider):
            controls.addWidget(w)

        self._header = QLabel()
        root = QVBoxLayout()
        root.addWidget(self._header)
        root.addLayout(controls)
        root.addWidget(self._topdown, stretch=1)
        root.addWidget(self._netpanel, stretch=1)
        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)
        self._status = self.statusBar()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)
        self._clock = QElapsedTimer()

        self.select_scenario(0)
        self._selector.currentIndexChanged.connect(self.select_scenario)

    @staticmethod
    def _manual(pg):
        v_set = 0.7 * float(pg[0])
        return manual_scenario(pg, np.full(600, v_set),
                               s_init=float(pg[2]) + v_set * float(pg[1]), v_init=v_set)

    def scenario_count(self) -> int:
        return len(self._scenarios)

    def select_scenario(self, idx: int):
        self._current_idx = int(idx)
        if self._selector.currentIndex() != self._current_idx:   # keep combobox in sync on programmatic select
            self._selector.blockSignals(True)
            self._selector.setCurrentIndex(self._current_idx)
            self._selector.blockSignals(False)
        sc = self._scenarios[self._current_idx]
        self._injector = EventInjector()
        self._probe = AttributeProbe(capacity=500, sample_every=1)
        backend = SoftwareBackend(self._champ.model)
        stepper = SimStepper.from_scenario(backend, sc, injector=self._injector)
        self.loop = SimLoop(stepper, self._probe, dt_fixed=DT)
        self._last_result = None
        self._header.setText(f"champion: {self._champ_name}    |    scenario: {sc.name}")
        self._netpanel.set_ground_truth(sc.params_gt)
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
            self._topdown.update_frame(results[-1])
            self._netpanel.update_frame(self._probe)
        self._refresh_status()

    def status_text(self) -> str:
        st = self.loop.stepper.st
        r = self._last_result
        ego = r.v if r is not None else st.v
        leader = r.vl if r is not None else float(self.loop.stepper.v_leader[0])
        gap = r.s if r is not None else st.s
        state = "COLLIDED" if st.collided else "ok"
        return (f"t={st.t} ({st.t * DT:.1f}s)   |   ego {ego:.1f} m/s   |   leader {leader:.1f} m/s"
                f"   |   gap {gap:.1f} m   |   {state}")

    def _refresh_status(self):
        self._status.showMessage(self.status_text())

    def _on_speed(self, v: int):
        self._speed = int(v)

    def _on_run_toggled(self, running: bool):
        if running:
            self._clock.restart()
            self._timer.start(_UI_FPS_MS)
        else:
            self._timer.stop()

    def _on_timer(self):
        self._advance(self._clock.restart() / 1000.0)
        if self.loop.done:
            self._run_btn.setChecked(False)
