"""Individual live network graphs as standalone dockable widgets: RasterPanel (spike raster),
VmemPanel (v_mem sample traces + effective threshold), ParamPanel (one identified param in physical
units with an optional dashed ground-truth reference line and the live value in the title)."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from sim.ui import metrics

PARAM_NAMES = ["v0", "T", "s0", "a", "b"]
PARAM_UNITS = ["m/s", "s", "m", "m/s^2", "m/s^2"]
PARAM_COLORS = ["#d1495b", "#2a7fb8", "#7b3fa0", "#e8871e", "#2e8b57"]
_N_SAMPLE = 4


class SpikeRatePanel(QWidget):
    """Firing-rate trend: % of hidden neurons spiking per tick, over the buffer."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="spike rate (% hidden firing)")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", "rate", units="%")
        self._plot.setDownsampling(auto=True, mode="peak")
        self._plot.setClipToView(True)
        self._curve = self._plot.plot(pen=pg.mkPen("#e8871e", width=2))
        layout.addWidget(self._plot)

    def update_frame(self, probe):
        sm = probe.spikes_matrix()          # (frames, H)
        if sm.size:
            self._curve.setData(sm.mean(axis=1) * 100.0)


_INPUT_NAMES = ["s", "v", "Δv", "vl"]   # order from _norm_obs: gap, ego speed, closing speed, leader speed


class NeuronGraphPanel(QWidget):
    """Node-link view of the SNN (input | hidden | output): coloured circles (viridis(activation)),
    a faint weight-skeleton (opacity ~ |weight|), and WHITE active pathways out of firing neurons."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget()
        self._plot.hideAxis("left")
        self._plot.hideAxis("bottom")
        self._plot.setMenuEnabled(False)
        layout.addWidget(self._plot)
        self._lut = pg.colormap.get("viridis").getLookupTable(0.0, 1.0, 256)
        self._skeleton = pg.GraphItem()
        self._active = pg.GraphItem()
        self._nodes = pg.ScatterPlotItem()
        for it in (self._skeleton, self._active, self._nodes):
            self._plot.addItem(it)
        self._pos = None
        self._n_in = self._n_hid = self._n_out = 0
        self._rec_out_adj = None      # (E,2) recurrent + output edges (spike-carrying)
        self._rec_out_src = None      # (E,) source hidden index of each such edge

    def _brushes(self, vals):
        v = np.asarray(vals, dtype=np.float64).reshape(-1)
        vmin, vmax = float(np.nanmin(v)), float(np.nanmax(v))
        idx = np.clip(((v - vmin) / (vmax - vmin + 1e-9) * 255).astype(int), 0, 255)
        return [pg.mkBrush(int(r), int(g), int(b)) for r, g, b in self._lut[idx][:, :3]]

    def set_topology(self, w_in, w_rec, w_out):
        w_in = np.asarray(w_in, dtype=np.float64)
        w_rec = np.asarray(w_rec, dtype=np.float64)
        w_out = np.asarray(w_out, dtype=np.float64)
        H, IN = w_in.shape
        OUT = w_out.shape[0]
        self._n_in, self._n_hid, self._n_out = IN, H, OUT

        def yspread(n, span=32.0):
            return np.linspace(0.0, span, n) if n > 1 else np.array([span / 2])

        half = (H + 1) // 2
        pin = [(0.0, y) for y in yspread(IN)]
        phid = ([(1.0, y) for y in yspread(half)] + [(1.4, y) for y in yspread(H - half)])
        pout = [(2.6, y) for y in yspread(OUT)]
        self._pos = np.array(pin + phid + pout, dtype=float)
        bi, bh, bo = 0, IN, IN + H

        e_in = [(bi + i, bh + j) for j in range(H) for i in range(IN)]
        w_e_in = [abs(w_in[j, i]) for j in range(H) for i in range(IN)]
        e_rec = [(bh + i, bh + j) for i in range(H) for j in range(H) if i != j]
        w_e_rec = [abs(w_rec[j, i]) for i in range(H) for j in range(H) if i != j]
        src_rec = [i for i in range(H) for j in range(H) if i != j]
        e_out = [(bh + j, bo + k) for j in range(H) for k in range(OUT)]
        w_e_out = [abs(w_out[k, j]) for j in range(H) for k in range(OUT)]
        src_out = [j for j in range(H) for k in range(OUT)]

        all_adj = np.array(e_in + e_rec + e_out, dtype=int)
        all_w = np.array(w_e_in + w_e_rec + w_e_out, dtype=float)
        alpha = np.clip(all_w / (all_w.max() + 1e-9) * 55 + 6, 6, 61).astype(np.ubyte)
        pens = np.zeros(len(all_adj), dtype=[('red', np.ubyte), ('green', np.ubyte),
                                             ('blue', np.ubyte), ('alpha', np.ubyte), ('width', float)])
        pens['red'][:] = 150
        pens['green'][:] = 150
        pens['blue'][:] = 150
        pens['alpha'] = alpha
        pens['width'] = 1.0
        self._skeleton.setData(pos=self._pos, adj=all_adj, pen=pens, size=0)

        self._rec_out_adj = np.array(e_rec + e_out, dtype=int)
        self._rec_out_src = np.array(src_rec + src_out, dtype=int)
        self._active.setData(pos=self._pos, adj=np.empty((0, 2), dtype=int),
                             pen=pg.mkPen("#ffffff", width=2.2), size=0)
        self._add_labels()

    def _text(self, s, x, y, anchor, color):
        t = pg.TextItem(s, color=color, anchor=anchor)
        t.setPos(float(x), float(y))
        self._plot.addItem(t)

    def _add_labels(self):
        for i in range(self._n_in):
            self._text(_INPUT_NAMES[i] if i < len(_INPUT_NAMES) else f"in{i}",
                       self._pos[i, 0], self._pos[i, 1], (1.2, 0.5), "#8fb7e0")
        for k in range(self._n_out):
            j = self._n_in + self._n_hid + k
            self._text(PARAM_NAMES[k] if k < len(PARAM_NAMES) else f"out{k}",
                       self._pos[j, 0], self._pos[j, 1], (-0.2, 0.5), "#88d6a0")
        top = float(self._pos[:, 1].max()) + 2.5
        self._text("input · osservazione", 0.0, top, (0.5, 1.0), "#8fb7e0")
        self._text("hidden · 32 ALIF", 1.2, top, (0.5, 1.0), "#c9a0e8")
        self._text("output · parametri", 2.6, top, (0.5, 1.0), "#88d6a0")

    def update_frame(self, probe):
        frames = probe.frames()
        if not frames or self._pos is None:
            return
        f = frames[-1]
        inp = (np.asarray(f.input, dtype=np.float64).reshape(-1)
               if (f.input is not None and np.size(f.input)) else np.zeros(self._n_in))
        vals = np.concatenate([inp[:self._n_in],
                               np.asarray(f.v_mem, dtype=np.float64).reshape(-1)[:self._n_hid],
                               np.asarray(f.params, dtype=np.float64).reshape(-1)[:self._n_out]])
        spk = np.asarray(f.spikes, dtype=np.float64).reshape(-1)[:self._n_hid] > 0
        pens = [pg.mkPen(None)] * len(vals)
        for j in range(self._n_hid):
            if spk[j]:
                pens[self._n_in + j] = pg.mkPen("#ffffff", width=2.0)
        self._nodes.setData(pos=self._pos, brush=self._brushes(vals), pen=pens, size=13)
        mask = spk[self._rec_out_src]
        self._active.setData(pos=self._pos, adj=self._rec_out_adj[mask],
                             pen=pg.mkPen("#ffffff", width=2.2), size=0)


class VmemPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="v_mem (sample neurons) + effective threshold (dashed)")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", "v_mem")
        self._plot.setDownsampling(auto=True, mode="peak")   # render only what's visible/needed
        self._plot.setClipToView(True)
        self._vmem_curves = [self._plot.plot(pen=pg.mkPen("#8fd6ff", width=1)) for _ in range(_N_SAMPLE)]
        self._vth_curves = [self._plot.plot(pen=pg.mkPen("#e8871e", width=1, style=Qt.DashLine))
                            for _ in range(_N_SAMPLE)]
        layout.addWidget(self._plot)

    def update_frame(self, probe):
        frames = probe.frames()
        if not frames:
            return
        vm = np.stack([f.v_mem for f in frames])
        vth = np.stack([f.v_th_eff for f in frames])
        for i in range(min(_N_SAMPLE, vm.shape[1])):
            self._vmem_curves[i].setData(vm[:, i])
            self._vth_curves[i].setData(vth[:, i])


class ParamPanel(QWidget):
    def __init__(self, index, name, unit, color):
        super().__init__()
        self._index = index
        self._name = name
        self._unit = unit
        self._last = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title=f"{name} ({unit})")
        self._plot.setDownsampling(auto=True, mode="peak")   # render only what's visible/needed
        self._plot.setClipToView(True)
        self._plot.showGrid(x=False, y=True, alpha=0.2)
        self._curve = self._plot.plot(pen=pg.mkPen(color, width=2))
        self._gt = pg.InfiniteLine(angle=0, movable=False,
                                   pen=pg.mkPen("#9a9a9a", width=1, style=Qt.DashLine))
        self._gt.setVisible(False)
        self._plot.addItem(self._gt)
        layout.addWidget(self._plot)

    @property
    def plot_item(self):
        return self._plot.getPlotItem()

    def current_value(self):
        return self._last

    def set_ground_truth(self, value):
        if value is None:
            self._gt.setVisible(False)
        else:
            self._gt.setPos(float(value))
            self._gt.setVisible(True)

    def update_frame(self, probe):
        pm = probe.params_matrix()
        if pm.size:
            self._last = float(pm[-1, self._index])
            self._curve.setData(pm[:, self._index])
            self._plot.setTitle(f"{self._name} = {self._last:.2f} {self._unit}")


class TrajectoryPanel(QWidget):
    """gap / speeds (ego, leader, Δv) / accel over time — 3 X-linked sub-plots."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._glw = pg.GraphicsLayoutWidget()
        layout.addWidget(self._glw)
        self._pg = self._glw.addPlot(row=0, col=0)
        self._pv = self._glw.addPlot(row=1, col=0)
        self._pa = self._glw.addPlot(row=2, col=0)
        self._pg.setLabel("left", "gap", units="m")
        self._pv.setLabel("left", "speed", units="m/s")
        self._pa.setLabel("left", "accel", units="m/s^2")
        self._pa.setLabel("bottom", "time", units="steps")
        for p in (self._pg, self._pv, self._pa):
            p.setDownsampling(auto=True, mode="peak")
            p.setClipToView(True)
            p.showGrid(x=False, y=True, alpha=0.2)
        self._pv.setXLink(self._pg)
        self._pa.setXLink(self._pg)
        self._c_s = self._pg.plot(pen=pg.mkPen("#2e8b57", width=2))
        self._c_v = self._pv.plot(pen=pg.mkPen("#2a7fb8", width=2))
        self._c_vl = self._pv.plot(pen=pg.mkPen("#d1495b", width=2))
        self._c_dv = self._pv.plot(pen=pg.mkPen("#e8871e", width=1, style=Qt.DashLine))
        self._c_a = self._pa.plot(pen=pg.mkPen("#7b3fa0", width=2))

    def update_frame(self, traj):
        a = traj.arrays()
        if a["t"].size == 0:
            return
        self._c_s.setData(a["s"])
        self._c_v.setData(a["v"])
        self._c_vl.setData(a["vl"])
        self._c_dv.setData(a["dv"])
        self._c_a.setData(a["a_ego"])


_SAFETY_CAP = 30.0


class SafetyPanel(QWidget):
    """TTC + time-headway (s) / DRAC (m/s^2), with dashed threshold reference lines."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._glw = pg.GraphicsLayoutWidget()
        layout.addWidget(self._glw)
        self._pt = self._glw.addPlot(row=0, col=0)
        self._pd = self._glw.addPlot(row=1, col=0)
        self._pt.setLabel("left", "time", units="s")
        self._pd.setLabel("left", "DRAC", units="m/s^2")
        self._pd.setLabel("bottom", "time", units="steps")
        for p in (self._pt, self._pd):
            p.setDownsampling(auto=True, mode="peak")
            p.setClipToView(True)
            p.showGrid(x=False, y=True, alpha=0.2)
        self._pd.setXLink(self._pt)
        self._c_ttc = self._pt.plot(pen=pg.mkPen("#d1495b", width=2))
        self._c_th = self._pt.plot(pen=pg.mkPen("#2a7fb8", width=1, style=Qt.DashLine))
        self._c_drac = self._pd.plot(pen=pg.mkPen("#e8871e", width=2))
        self._ttc_ref = pg.InfiniteLine(pos=1.5, angle=0, pen=pg.mkPen("#9a9a9a", style=Qt.DashLine))
        self._drac_ref = pg.InfiniteLine(pos=3.35, angle=0, pen=pg.mkPen("#9a9a9a", style=Qt.DashLine))
        self._pt.addItem(self._ttc_ref)
        self._pd.addItem(self._drac_ref)

    def update_frame(self, traj):
        a = traj.arrays()
        if a["t"].size == 0:
            return
        self._c_ttc.setData(np.clip(metrics.ttc(a["s"], a["dv"]), 0, _SAFETY_CAP))
        self._c_th.setData(np.clip(metrics.time_headway(a["s"], a["v"]), 0, _SAFETY_CAP))
        self._c_drac.setData(metrics.drac(a["s"], a["dv"]))
