"""ScenarioPage -- the fourth mode: describe a scenario instead of picking one.

A timeline of blocks + a 2-D style pad; the preview below is the REAL materialised v_leader, from
the same function the sim will run. Every decision is delegated to sim.scenario_spec: this file is
Qt and nothing else.
"""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QListWidget,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)

from sim.scenario_spec import (A_MAX_RANGE, B_MAX_RANGE, Block, LeaderStyle, ScenarioSpec,
                               materialise)

# Labels for READING the plane, not modes: the point is continuous and may sit anywhere.
_QUADRANTS = [("placido", 1.4, 1.6), ("guardingo", 1.4, 8.4),
              ("spavaldo", 3.6, 1.6), ("aggressivo", 3.6, 8.4)]


class StylePad(pg.PlotWidget):
    """The (a_max, b_max) plane. Acceleration and deceleration are INDEPENDENT, so a single slider
    would only walk the placido<->aggressivo diagonal and make the mixed quadrants unreachable."""
    sigStyleChanged = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.setLabel("bottom", "accelerazione a_max", units="m/s²")
        self.setLabel("left", "decelerazione b_max", units="m/s²")
        self.setXRange(*A_MAX_RANGE)
        self.setYRange(*B_MAX_RANGE)
        self.setMouseEnabled(x=False, y=False)
        self.showGrid(x=True, y=True, alpha=0.2)
        for name, a, b in _QUADRANTS:
            t = pg.TextItem(name, color="#8a8a8a", anchor=(0.5, 0.5))
            t.setPos(a, b)
            self.addItem(t)
        self._dot = pg.ScatterPlotItem(size=13, brush=pg.mkBrush("#2a7fb8"),
                                       pen=pg.mkPen("#ffffff", width=2))
        self.addItem(self._dot)
        self._a, self._b = 2.0, 4.0
        self._dot.setData([self._a], [self._b])
        self.scene().sigMouseClicked.connect(self._on_click)

    def _on_click(self, ev):
        p = self.getPlotItem().vb.mapSceneToView(ev.scenePos())
        self.set_point(float(np.clip(p.x(), *A_MAX_RANGE)), float(np.clip(p.y(), *B_MAX_RANGE)))

    def set_point(self, a, b):
        self._a, self._b = float(a), float(b)
        self._dot.setData([self._a], [self._b])
        self.sigStyleChanged.emit(self._a, self._b)


class ScenarioPage(QWidget):
    sigScenarioBuilt = Signal(object)          # emits a sim.scenario.Scenario

    def __init__(self, params_gt, N=600):
        super().__init__()
        self._params_gt = np.asarray(params_gt, dtype=np.float64)
        self._N = int(N)
        self._spec = None
        root = QVBoxLayout(self)

        controls = QHBoxLayout()
        self._kind = QComboBox()
        self._kind.addItems(["preset", "const", "ramp", "sine"])
        self._ticks = QSpinBox(); self._ticks.setRange(1, 600); self._ticks.setValue(150)
        self._value = QDoubleSpinBox(); self._value.setRange(0.0, 40.0); self._value.setValue(5.0)
        self._add = QPushButton("Aggiungi blocco"); self._add.clicked.connect(self._on_add)
        self._del = QPushButton("Rimuovi"); self._del.clicked.connect(self._on_del)
        self._use = QPushButton("Usa questo scenario"); self._use.clicked.connect(self._on_use)
        for w in (QLabel("blocco"), self._kind, QLabel("durata"), self._ticks,
                  QLabel("valore"), self._value, self._add, self._del, self._use):
            controls.addWidget(w)
        controls.addStretch(1)
        root.addLayout(controls)

        mid = QHBoxLayout()
        self._list = QListWidget()
        mid.addWidget(self._list, stretch=1)
        self._pad = StylePad()
        self._pad.sigStyleChanged.connect(self.set_style)
        mid.addWidget(self._pad, stretch=1)
        root.addLayout(mid, stretch=1)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("left", "v_leader", units="m/s")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.showGrid(x=False, y=True, alpha=0.2)
        self._curve = self._plot.plot(pen=pg.mkPen("#d1495b", width=2))
        root.addWidget(self._plot, stretch=1)

    # ---- state ----
    def set_spec(self, spec):
        self._spec = spec
        self._pad.set_point(spec.style.a_max, spec.style.b_max)   # emits -> set_style -> _refresh
        self._refresh_list()
        self._refresh()

    def set_style(self, a_max, b_max):
        """Called live while the pad is dragged. No throttle: measured 0/120 frames over the 60 fps
        budget (peak 14.18 ms of 16.7). The materialiser is vectorised precisely so this holds."""
        if self._spec is None:
            return
        self._spec = ScenarioSpec(name=self._spec.name, blocks=self._spec.blocks,
                                  style=LeaderStyle(float(a_max), float(b_max)),
                                  s_init=self._spec.s_init, v_init=self._spec.v_init)
        self._refresh()

    def _refresh(self):
        if self._spec is None or not self._spec.blocks:
            self._curve.setData([])
            return
        self._curve.setData(materialise(self._spec, self._params_gt, self._N).v_leader)

    def _refresh_list(self):
        self._list.clear()
        for b in (self._spec.blocks if self._spec else ()):
            self._list.addItem(f"{b.kind}  ·  {b.ticks} tick  ·  {b.params}")

    # ---- actions ----
    def _params_for(self, kind):
        v = float(self._value.value())
        return {"preset": {"name": "stop_and_go"}, "const": {"v": v}, "ramp": {"to_v": v},
                "sine": {"amp": 0.5 * v, "period": 80}}[kind]

    def _on_add(self):
        if self._spec is None:
            return
        kind = self._kind.currentText()
        blk = Block(kind, int(self._ticks.value()), self._params_for(kind))
        self._spec = ScenarioSpec(name=self._spec.name, blocks=self._spec.blocks + (blk,),
                                  style=self._spec.style, s_init=self._spec.s_init,
                                  v_init=self._spec.v_init)
        self._refresh_list()
        self._refresh()

    def _on_del(self):
        i = self._list.currentRow()
        if self._spec is None or i < 0:
            return
        blocks = self._spec.blocks[:i] + self._spec.blocks[i + 1:]
        self._spec = ScenarioSpec(name=self._spec.name, blocks=blocks, style=self._spec.style,
                                  s_init=self._spec.s_init, v_init=self._spec.v_init)
        self._refresh_list()
        self._refresh()

    def _on_use(self):
        if self._spec is None or not self._spec.blocks:
            return
        self.sigScenarioBuilt.emit(materialise(self._spec, self._params_gt, self._N))
