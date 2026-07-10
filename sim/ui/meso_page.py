"""MesoMacroPage -- batch platoon/ring analysis view (string stability, space-time, fundamental
diagram, per-vehicle params). Scaffold in T1; panels are wired in T3/T4. The analysis is on-demand
(press Run), distinct from the live single-vehicle cockpit."""
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from sim.ui.meso_panels import (FundamentalDiagramPanel, PlatoonParamsPanel, SpaceTimePanel,
                                StringStabilityPanel)


class MesoMacroPage(QWidget):
    def __init__(self, params_gt=None):
        super().__init__()
        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        self._n_spin = QSpinBox(); self._n_spin.setRange(3, 40); self._n_spin.setValue(12)
        self._run_platoon_btn = QPushButton("Run platoon")
        self._run_ring_btn = QPushButton("Run ring sweep")
        for w in (QLabel("N veicoli"), self._n_spin, self._run_platoon_btn, self._run_ring_btn):
            controls.addWidget(w)
        controls.addStretch(1)
        root.addLayout(controls)
        self._grid = QGridLayout()
        self.string_stability = StringStabilityPanel()    # meso: string stability |H|_i
        self.space_time = SpaceTimePanel()                 # meso: space-time waves
        self.fundamental_diagram = FundamentalDiagramPanel()   # macro: Q(rho)/V(rho)
        self.platoon_params = PlatoonParamsPanel(params_gt)    # meso: per-vehicle identified params
        self._grid.addWidget(self.string_stability, 0, 0)
        self._grid.addWidget(self.space_time, 0, 1)
        self._grid.addWidget(self.fundamental_diagram, 1, 0)
        self._grid.addWidget(self.platoon_params, 1, 1)
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
