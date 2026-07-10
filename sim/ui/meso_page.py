"""MesoMacroPage -- batch platoon/ring analysis view (string stability, space-time, fundamental
diagram, per-vehicle params). Scaffold in T1; panels are wired in T3/T4. The analysis is on-demand
(press Run), distinct from the live single-vehicle cockpit."""
from PySide6.QtWidgets import (QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from sim.ui.meso_panels import (FundamentalDiagramPanel, SpaceTimePanel, SpeedWavePanel,
                                StringStabilityPanel)
from sim.ui.meso_road import PlatoonRoadView


class MesoMacroPage(QWidget):
    def __init__(self, scenario_names=None):
        super().__init__()
        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        self._scenario_sel = QComboBox(); self._scenario_sel.addItems(list(scenario_names or []))
        self._n_spin = QSpinBox(); self._n_spin.setRange(3, 40); self._n_spin.setValue(12)
        self._run_platoon_btn = QPushButton("Run platoon")
        self._run_ring_btn = QPushButton("Run ring sweep")
        for w in (QLabel("scenario"), self._scenario_sel, QLabel("N veicoli"), self._n_spin,
                  self._run_platoon_btn, self._run_ring_btn):
            controls.addWidget(w)
        controls.addStretch(1)
        root.addLayout(controls)
        self.road = PlatoonRoadView()                      # platoon road view (top strip)
        root.addWidget(self.road, stretch=0)
        self._grid = QGridLayout()
        self.string_stability = StringStabilityPanel()    # meso: string stability |H|_i
        self.speed_wave = SpeedWavePanel()                 # meso: velocity waves v(t)
        self.space_time = SpaceTimePanel()                 # meso: space-time x(t)
        self.fundamental_diagram = FundamentalDiagramPanel()   # macro: Q(rho)/V(rho)
        self._grid.addWidget(self.string_stability, 0, 0)
        self._grid.addWidget(self.speed_wave, 0, 1)
        self._grid.addWidget(self.space_time, 1, 0)
        self._grid.addWidget(self.fundamental_diagram, 1, 1)
        for c in (0, 1):
            self._grid.setColumnStretch(c, 1)              # split columns evenly (T3: panels weren't side-by-side)
        for r in (0, 1):
            self._grid.setRowStretch(r, 1)
        root.addLayout(self._grid, stretch=1)
        self._on_run_platoon = None
        self._on_run_ring = None
        self._run_platoon_btn.clicked.connect(lambda: self._on_run_platoon and self._on_run_platoon())
        self._run_ring_btn.clicked.connect(lambda: self._on_run_ring and self._on_run_ring())

    def n_vehicles(self):
        return int(self._n_spin.value())

    def selected_scenario_index(self):
        return int(self._scenario_sel.currentIndex())
