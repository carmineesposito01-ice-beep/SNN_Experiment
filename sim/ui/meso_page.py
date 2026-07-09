"""MesoMacroPage -- batch platoon/ring analysis view (string stability, space-time, fundamental
diagram, per-vehicle params). Scaffold in T1; panels are wired in T3/T4. The analysis is on-demand
(press Run), distinct from the live single-vehicle cockpit."""
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget)
from pyqtgraph import GraphicsLayoutWidget


class MesoMacroPage(QWidget):
    def __init__(self):
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
        self._grid = GraphicsLayoutWidget()          # analysis panels added in T3/T4
        root.addWidget(self._grid, stretch=1)
        self._on_run_platoon = None
        self._on_run_ring = None
        self._run_platoon_btn.clicked.connect(lambda: self._on_run_platoon and self._on_run_platoon())
        self._run_ring_btn.clicked.connect(lambda: self._on_run_ring and self._on_run_ring())

    def n_vehicles(self):
        return int(self._n_spin.value())
