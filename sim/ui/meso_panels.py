"""Meso/macro analysis panels (fed by sim.ui.platoon runs). Read-only views over platoon_eval output."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StringStabilityPanel(QWidget):
    """Bar of |H|_i = A_i/A_0 per vehicle (green <=1, red >1) + a y=1 reference + verdict."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="string stability — |H|_i = A_i/A_0")
        self._plot.setLabel("bottom", "veicolo"); self._plot.setLabel("left", "gain")
        self._bars = pg.BarGraphItem(x=[0], height=[0], width=0.7, brush=pg.mkBrush("#2a7fb8"))
        self._plot.addItem(self._bars)
        self._ref = pg.InfiniteLine(pos=1.0, angle=0, pen=pg.mkPen("#e24b4a", width=1.2, style=Qt.DashLine))
        self._plot.addItem(self._ref)
        self._verdict = QLabel(""); self._verdict.setContentsMargins(6, 0, 6, 4)
        layout.addWidget(self._plot, stretch=1); layout.addWidget(self._verdict)

    def set_metrics(self, m):
        gain = np.asarray(m["gain_per_vehicle"], dtype=float)
        x = np.arange(len(gain))
        brushes = [pg.mkBrush("#2e8b57" if g <= 1.0 else "#e24b4a") for g in gain]
        self._bars.setOpts(x=x, height=gain, width=0.7, brushes=brushes)
        self._verdict.setText(
            f"{'STRING-STABLE' if m['string_stable_headtail'] else 'INSTABILE'}  ·  "
            f"head→tail {m['head_to_tail_gain']}  ·  max amp {m['max_amplification']}  ·  "
            f"{'onda convettiva a monte' if m['convective_upstream'] else 'no onda a monte'}")


class SpaceTimePanel(QWidget):
    """Space-time diagram: x(t) of each vehicle (viridis by index) -> stop-and-go waves visible."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="spazio-tempo (traiettorie plotone)")
        self._plot.setLabel("bottom", "time", units="steps"); self._plot.setLabel("left", "x", units="m")
        self._plot.setDownsampling(auto=True, mode="peak"); self._plot.setClipToView(True)
        self._lut = pg.colormap.get("viridis").getLookupTable(0.0, 1.0, 256)
        self._curves = []

    def set_rec(self, rec):
        x = np.asarray(rec["x"])                    # (T, N) absolute positions
        if x.ndim != 2 or x.size == 0:
            return
        T, N = x.shape
        while len(self._curves) < N:
            self._curves.append(self._plot.plot())
        t = np.arange(T)
        for i in range(N):
            r, g, b = self._lut[int(i / max(1, N - 1) * 255)][:3]
            self._curves[i].setData(t, x[:, i], pen=pg.mkPen(int(r), int(g), int(b), width=1))
        for c in self._curves[N:]:
            c.setData([], [])
