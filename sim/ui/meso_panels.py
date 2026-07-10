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
        layout.addWidget(self._plot, stretch=1)      # T3 bug: was never added -> panel rendered blank

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
        # frame the data explicitly: with clipToView + downsampling the ViewBox auto-range never
        # fires when the panel is populated before its first show -> it stays at the default [0,1]
        # and the trajectories are drawn off-view (blank panel).
        self._plot.setXRange(0.0, float(max(T - 1, 1)), padding=0.02)
        self._plot.setYRange(float(np.min(x)), float(np.max(x)), padding=0.05)


_PARAM_NAMES = ("v0", "T", "s0", "a", "b")


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
        self._q_unstable = pg.ScatterPlotItem(symbol="x", size=13, pen=pg.mkPen("#e24b4a", width=2))
        self._v_unstable = pg.ScatterPlotItem(symbol="x", size=13, pen=pg.mkPen("#e24b4a", width=2))
        self._q.addItem(self._q_unstable); self._v.addItem(self._v_unstable)
        layout.addWidget(self._q, stretch=1); layout.addWidget(self._v, stretch=1)

    def set_points(self, pts):
        pts = sorted(pts, key=lambda p: p["rho_veh_km"])
        rho = np.array([p["rho_veh_km"] for p in pts], dtype=float)
        Q = np.array([p["Q_veh_h"] for p in pts], dtype=float)
        V = np.array([p["V_km_h"] for p in pts], dtype=float)
        un = np.array([bool(p["unstable"]) for p in pts])
        self._q_curve.setData(rho, Q); self._v_curve.setData(rho, V)
        self._q_unstable.setData(rho[un], Q[un]); self._v_unstable.setData(rho[un], V[un])


class PlatoonParamsPanel(QWidget):
    """MESO identification: the 5 ACC-IIDM params each vehicle's SNN produces, mean over the regime
    (post-warmup) -> dispersion along the platoon. 5 bar strips vs vehicle index + optional GT line."""
    def __init__(self, params_gt=None):
        super().__init__()
        self._gt = None if params_gt is None else np.asarray(params_gt, dtype=float)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self._glw = pg.GraphicsLayoutWidget()
        layout.addWidget(self._glw)
        self._bars = []; self._plots = []
        for r, name in enumerate(_PARAM_NAMES):
            plt = self._glw.addPlot(row=r, col=0)
            plt.setLabel("left", name)
            plt.showAxis("bottom", r == len(_PARAM_NAMES) - 1)   # only the bottom strip shows the x axis
            bar = pg.BarGraphItem(x=[0], height=[0], width=0.7, brush=pg.mkBrush("#8a6fb0"))
            plt.addItem(bar); self._bars.append(bar); self._plots.append(plt)
            if self._gt is not None:
                plt.addItem(pg.InfiniteLine(pos=float(self._gt[r]), angle=0,
                                            pen=pg.mkPen("#888", width=1, style=Qt.DashLine)))
        self._plots[-1].setLabel("bottom", "veicolo")

    def set_rec(self, rec, warmup_frac=0.3):
        params = np.asarray(rec["params"], dtype=float)          # (T, N, 5)
        if params.ndim != 3 or params.shape[2] != 5:
            return
        T, N, _ = params.shape
        w = int(T * warmup_frac)
        mean_pv = params[w:].mean(axis=0)                        # (N, 5) mean over the regime
        x = np.arange(N)
        for k in range(5):
            self._bars[k].setOpts(x=x, height=mean_pv[:, k], width=0.7)
