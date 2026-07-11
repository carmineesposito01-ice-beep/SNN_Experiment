"""Meso/macro analysis panels (fed by sim.ui.platoon runs). Read-only views over platoon_eval output."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
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


class _MultiCurvePanel(QWidget):
    """N viridis curves of rec[field][:, i] vs time (one per vehicle). Base for the space-time (x)
    and speed-wave (v) panels. Frames the data explicitly: clipToView + downsampling leave the
    ViewBox auto-range stuck at the default [0,1] when the panel is populated before its first show
    (-> blank panel), and the PlotWidget must be added to the layout (else it is an orphan).

    Curves are clickable: clicking a vehicle's curve emits sigVehicleClicked(i); highlight(i) then
    bold-whites that vehicle and dims the rest (the page routes the click to the road view + sibling
    panel so the selection stays in sync everywhere)."""
    sigVehicleClicked = Signal(int)

    def __init__(self, field, title, ylabel, y_units):
        super().__init__()
        self._field = field
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title=title)
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", ylabel, units=y_units)
        self._plot.setDownsampling(auto=True, mode="peak"); self._plot.setClipToView(True)
        self._lut = pg.colormap.get("viridis").getLookupTable(0.0, 1.0, 256)
        self._curves = []
        self._n = 0
        self._highlighted = None
        layout.addWidget(self._plot, stretch=1)

    def _base_rgb(self, i):
        r, g, b = self._lut[int(i / max(1, self._n - 1) * 255)][:3]
        return int(r), int(g), int(b)

    def _pen(self, i):
        r, g, b = self._base_rgb(i)
        if self._highlighted is None:
            return pg.mkPen(r, g, b, width=1)
        if i == self._highlighted:
            return pg.mkPen("#ffffff", width=2.5)     # selected vehicle: bold white
        return pg.mkPen(r, g, b, width=0.5)           # dim the rest

    def set_rec(self, rec):
        y = np.asarray(rec[self._field])            # (T, N)
        if y.ndim != 2 or y.size == 0:
            return
        T, N = y.shape
        self._n = N
        self._highlighted = None                    # new platoon -> clear any selection
        while len(self._curves) < N:
            c = self._plot.plot()
            c.setCurveClickable(True, width=10)      # 10 px hit margin around each thin curve
            i = len(self._curves)
            c.sigClicked.connect(lambda *a, idx=i: self.sigVehicleClicked.emit(idx))
            self._curves.append(c)
        t = np.arange(T)
        for i in range(N):
            self._curves[i].setData(t, y[:, i], pen=self._pen(i))
        for c in self._curves[N:]:
            c.setData([], [])
        self._plot.setXRange(0.0, float(max(T - 1, 1)), padding=0.02)
        self._plot.setYRange(float(np.min(y)), float(np.max(y)), padding=0.05)

    def highlight(self, i):
        """Bold-white vehicle i (dim the others); i=None or out of range clears the highlight."""
        self._highlighted = i if (i is not None and 0 <= i < self._n) else None
        for k in range(self._n):
            self._curves[k].setPen(self._pen(k))


class SpaceTimePanel(_MultiCurvePanel):
    """Space-time diagram: x(t) of each vehicle (viridis by index) -> stop-and-go waves visible."""
    def __init__(self):
        super().__init__("x", "spazio-tempo (traiettorie plotone)", "x", "m")


class SpeedWavePanel(_MultiCurvePanel):
    """Speed waves: v(t) of each vehicle (viridis by index) -> stop-and-go attenuation visible."""
    def __init__(self):
        super().__init__("v", "onde di velocità (attenuazione stop&go)", "v", "m/s")


class FundamentalDiagramPanel(QWidget):
    """MACRO: Q(rho) + V(rho) from the density sweep (X-linked); unstable points (wave_std>0.5) marked."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self._q = pg.PlotWidget(title="diagramma fondamentale — Q(ρ)")
        self._q.setLabel("bottom", "densità", units="veh/km"); self._q.setLabel("left", "flusso", units="veh/h")
        self._v = pg.PlotWidget(title="V(ρ)")
        self._v.setLabel("bottom", "densità", units="veh/km"); self._v.setLabel("left", "velocità", units="km/h")
        self._v.setXLink(self._q)
        self._q_curve = self._q.plot(pen=pg.mkPen("#2a7fb8", width=2), symbol="o",
                                     symbolSize=6, symbolBrush="#2a7fb8")
        self._v_curve = self._v.plot(pen=pg.mkPen("#2e8b57", width=2), symbol="o",
                                     symbolSize=6, symbolBrush="#2e8b57")
        # red × = density points where the ring is stop-and-go UNSTABLE; hover shows the wave amplitude.
        tip = lambda x, y, data: f"regime instabile (stop&go)\nρ = {x:.0f} veh/km\nwave_std = {data:.2f} (> 0.5)"
        self._q_unstable = pg.ScatterPlotItem(symbol="x", size=13, pen=pg.mkPen("#e24b4a", width=2),
                                              hoverable=True, tip=tip)
        self._v_unstable = pg.ScatterPlotItem(symbol="x", size=13, pen=pg.mkPen("#e24b4a", width=2),
                                              hoverable=True, tip=tip)
        self._q.addItem(self._q_unstable); self._v.addItem(self._v_unstable)
        layout.addWidget(self._q, stretch=1); layout.addWidget(self._v, stretch=1)
        self._legend = QLabel("<b>×</b> rosso = regime <b>instabile</b> — onde stop&go persistenti (wave_std > 0.5)")
        self._legend.setStyleSheet("color:#b8b8b8; font-size:11px;"); self._legend.setContentsMargins(6, 0, 6, 3)
        layout.addWidget(self._legend)

    def set_points(self, pts):
        pts = sorted(pts, key=lambda p: p["rho_veh_km"])
        rho = np.array([p["rho_veh_km"] for p in pts], dtype=float)
        Q = np.array([p["Q_veh_h"] for p in pts], dtype=float)
        V = np.array([p["V_km_h"] for p in pts], dtype=float)
        un = np.array([bool(p["unstable"]) for p in pts])
        ws = np.array([float(p.get("wave_std", 0.0)) for p in pts])
        self._q_curve.setData(rho, Q); self._v_curve.setData(rho, V)
        self._q_unstable.setData(rho[un], Q[un], data=ws[un])   # data = wave_std -> shown on hover
        self._v_unstable.setData(rho[un], V[un], data=ws[un])
