"""SimApp -- main window: champion + scenario selector + run/pause + brake-leader,
wiring SimLoop + TopDownView + NetPanel via a QTimer (fixed-timestep)."""
import numpy as np
from PySide6.QtCore import QElapsedTimer, QTimer
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QMainWindow, QPushButton,
                               QVBoxLayout, QWidget)

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

_UI_FPS_MS = 33          # ~30 Hz UI refresh; the accumulator runs physics at DT
_PARAMS_GT = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


class SimApp(QMainWindow):
    def __init__(self, champion_path):
        super().__init__()
        self.setWindowTitle("CF_FSNN Simulator")
        self._champ = load_champion(champion_path)
        self._scenarios = scenario_library(_PARAMS_GT, N=600,
                                            rng=np.random.default_rng(0), include_tail=True)
        self._scenarios.append(self._manual(_PARAMS_GT))

        self._topdown = TopDownView()
        self._netpanel = NetPanel()
        self._selector = QComboBox()
        self._selector.addItems([s.name for s in self._scenarios])
        self._run_btn = QPushButton("Run")
        self._run_btn.setCheckable(True)
        self._run_btn.toggled.connect(self._on_run_toggled)
        self._brake_btn = QPushButton("Brake leader")
        self._brake_btn.clicked.connect(self.inject_brake)

        controls = QHBoxLayout()
        for w in (self._selector, self._run_btn, self._brake_btn):
            controls.addWidget(w)

        root = QVBoxLayout()
        root.addLayout(controls)
        root.addWidget(self._topdown, stretch=1)
        root.addWidget(self._netpanel, stretch=1)
        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

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
        sc = self._scenarios[int(idx)]
        self._injector = EventInjector()
        self._probe = AttributeProbe(capacity=500, sample_every=1)
        backend = SoftwareBackend(self._champ.model)
        stepper = SimStepper.from_scenario(backend, sc, injector=self._injector)
        self.loop = SimLoop(stepper, self._probe, dt_fixed=DT)

    def inject_brake(self):
        st = self.loop.stepper.st
        base_vl = float(self.loop.stepper.v_leader[min(st.t, self.loop.stepper.N - 1)])
        self._injector.enqueue(st.t, "brake_leader", target_v=max(0.3 * base_vl, 2.0), duration=20)

    def _advance(self, frame_dt: float):
        results = self.loop.tick(frame_dt)
        if results:
            self._topdown.update_frame(results[-1])
            self._netpanel.update_frame(self._probe)
        return results

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
