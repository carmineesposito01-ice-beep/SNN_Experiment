"""Individual live network graphs as standalone dockable widgets: RasterPanel (spike raster),
VmemPanel (v_mem sample traces + effective threshold), ParamPanel (one identified param in physical
units with an optional dashed ground-truth reference line and the live value in the title)."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from sim.ui import metrics

PARAM_NAMES = ["v0", "T", "s0", "a", "b"]
PARAM_UNITS = ["m/s", "s", "m", "m/s^2", "m/s^2"]
PARAM_COLORS = ["#d1495b", "#2a7fb8", "#7b3fa0", "#e8871e", "#2e8b57"]
_N_SAMPLE = 4


def _add_cursor(plot):
    ln = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#ffffff", width=1, style=Qt.DashLine))
    ln.setVisible(False)
    plot.addItem(ln)
    return ln


def _set_cursor(cursors, x):
    for c in cursors:
        if x is None:
            c.setVisible(False)
        else:
            c.setPos(float(x))
            c.setVisible(True)


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
        self._cursors = [_add_cursor(self._plot.getPlotItem())]

    def set_cursor(self, x):
        _set_cursor(self._cursors, x)

    def update_frame(self, probe):
        sm = probe.spikes_matrix()          # (frames, H)
        if sm.size:
            self._curve.setData(sm.mean(axis=1) * 100.0)


class SynOpsPanel(QWidget):
    """Per-tick synaptic ops: static (fc, always-on) + dynamic (spike-driven), vs the dense-MAC
    equivalent (parameter count). SynOps ~ MACs (not sparse) -> the win is AC<MAC, not sparsity."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="SynOps / tick (AC)")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", "SynOps")
        self._plot.setDownsampling(auto=True, mode="peak")
        self._plot.setClipToView(True)
        self._static_c = self._plot.plot(pen=pg.mkPen("#1d9e75", width=1),
                                         fillLevel=0, brush=pg.mkBrush(29, 158, 117, 110))
        self._total_c = self._plot.plot(pen=pg.mkPen("#ffffff", width=1.5))
        self._fill_dyn = pg.FillBetweenItem(self._total_c, self._static_c,
                                            brush=pg.mkBrush(239, 159, 39, 100))
        self._plot.addItem(self._fill_dyn)
        self._ref = pg.InfiniteLine(angle=0, movable=False,
                                    pen=pg.mkPen("#9a9a9a", width=1.2, style=Qt.DashLine))
        self._ref.setVisible(False)
        self._plot.addItem(self._ref)
        self._cursors = [_add_cursor(self._plot.getPlotItem())]
        self._dims = None
        self._dense = None

    def set_cursor(self, x):
        _set_cursor(self._cursors, x)

    def set_model(self, n_in, n_hid, n_out, rank):
        self._dims = (int(n_in), int(n_hid), int(n_out), int(rank))
        self._dense = metrics.dense_mac(*self._dims)
        self._ref.setPos(self._dense)
        self._ref.setVisible(True)
        self._plot.setYRange(0, self._dense * 1.05)

    def update_frame(self, probe):
        if self._dims is None:
            return
        sm = probe.spikes_matrix()
        if not sm.size:
            return
        static, dynamic = metrics.synops_series(sm, *self._dims)
        total = static + dynamic
        self._static_c.setData(static)
        self._total_c.setData(total)
        cur = float(total[-1])
        pct = 100.0 * cur / self._dense if self._dense else 0.0
        self._plot.setTitle(f"SynOps/tick = {int(cur)} · {pct:.0f}% del dense-MAC ({self._dense})")


class EventTimelinePanel(QWidget):
    """Injected events (injector.log()) as clickable marks on the source-index axis.
    Marks store the ABSOLUTE tick; clicking calls the seek callback with that tick."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="events")
        self._plot.hideAxis("left")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setMouseEnabled(x=True, y=False)
        self._plot.setYRange(-1, 1)
        layout.addWidget(self._plot)
        self._marks = pg.ScatterPlotItem(symbol="t", size=14, brush=pg.mkBrush("#EF9F27"),
                                         pen=pg.mkPen("#0e1116"), hoverable=True)
        self._marks.sigClicked.connect(self._on_click)
        self._plot.addItem(self._marks)
        self._labels = []
        self._on_seek = None
        self._cursors = [_add_cursor(self._plot.getPlotItem())]

    def set_cursor(self, x):
        _set_cursor(self._cursors, x)

    def set_on_seek(self, cb):
        self._on_seek = cb

    def _clear_labels(self):
        for t in self._labels:
            self._plot.removeItem(t)
        self._labels = []

    def update_events(self, log, frames):
        self._clear_labels()
        tick_to_idx = {f.t: i for i, f in enumerate(frames)}
        spots = []
        for e in log:
            idx = tick_to_idx.get(e["tick"])
            if idx is None:
                continue                                   # scrolled out of the source -> skip
            spots.append({"pos": (idx, 0.0), "data": e["tick"]})
            lbl = pg.TextItem(e["verb"], color="#EF9F27", anchor=(0.5, 1.4))
            lbl.setPos(float(idx), 0.0)
            self._plot.addItem(lbl)
            self._labels.append(lbl)
        self._marks.setData(spots)

    def _on_click(self, scatter, points):
        if points and self._on_seek is not None:
            self._on_seek(int(points[0].data()))


_INPUT_NAMES = ["s", "v", "Δv", "vl"]   # order from _norm_obs: gap, ego speed, closing speed, leader speed


class NeuronGraphPanel(QWidget):
    """Node-link view of the SNN (input | hidden | output): coloured circles (viridis(activation)),
    a faint weight-skeleton (opacity ~ |weight|), and WHITE active pathways out of firing neurons."""
    sigNeuronClicked = Signal(int)

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
        self._highlight = pg.GraphItem()
        self._active = pg.GraphItem()
        self._nodes = pg.ScatterPlotItem()
        for it in (self._skeleton, self._highlight, self._active, self._nodes):
            self._plot.addItem(it)
        self._nodes.sigClicked.connect(self._on_node_click)
        self._pos = None
        self._last_vals = None
        self._n_in = self._n_hid = self._n_out = 0
        self._rec_out_adj = None      # (E,2) recurrent + output edges (spike-carrying)
        self._rec_out_src = None      # (E,) source hidden index of each such edge
        self._e_in = self._e_rec = self._e_out = None    # raw edge arrays for highlight()

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
        self._e_in = np.array(e_in, dtype=int)
        self._e_rec = np.array(e_rec, dtype=int)
        self._e_out = np.array(e_out, dtype=int)
        self._active.setData(pos=self._pos, adj=np.empty((0, 2), dtype=int),
                             pen=pg.mkPen("#ffffff", width=2.2), size=0)
        self._add_labels()
        self.highlight(None)

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

    def update_frame(self, probe, index=-1):
        frames = probe.frames()
        if not frames or self._pos is None:
            return
        n = len(frames)
        i = index if index >= 0 else n + index
        f = frames[max(0, min(i, n - 1))]
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
        self._last_vals = vals
        self._nodes.setData(pos=self._pos, brush=self._brushes(vals), pen=pens, size=13)
        mask = spk[self._rec_out_src]
        self._active.setData(pos=self._pos, adj=self._rec_out_adj[mask],
                             pen=pg.mkPen("#ffffff", width=2.2), size=0)

    def _on_node_click(self, scatter, points):
        if not points:
            return
        node = points[0].index()
        if self._n_in <= node < self._n_in + self._n_hid:
            self.sigNeuronClicked.emit(node - self._n_in)

    def highlight(self, i):
        if i is None or self._pos is None or self._e_in is None:
            self._highlight.setData(pos=(self._pos if self._pos is not None else np.zeros((1, 2))),
                                    adj=np.empty((0, 2), dtype=int), pen=pg.mkPen(None), size=0)
            return
        node = self._n_in + int(i)
        allin = np.vstack([self._e_in, self._e_rec])
        allout = np.vstack([self._e_rec, self._e_out])
        fanin = allin[allin[:, 1] == node]
        fanout = allout[allout[:, 0] == node]
        adj = np.vstack([fanin, fanout]).astype(int)
        pens = np.zeros(len(adj), dtype=[('red', np.ubyte), ('green', np.ubyte),
                                         ('blue', np.ubyte), ('alpha', np.ubyte), ('width', float)])
        ni = len(fanin)
        pens['red'][:ni], pens['green'][:ni], pens['blue'][:ni] = 0x8f, 0xb7, 0xe0   # fan-in blue
        pens['red'][ni:], pens['green'][ni:], pens['blue'][ni:] = 0x88, 0xd6, 0xa0   # fan-out green
        pens['alpha'][:] = 255
        pens['width'][:] = 2.0
        self._highlight.setData(pos=self._pos, adj=adj, pen=pens, size=0)


class NeuronInspectorPanel(QWidget):
    """Selected hidden neuron: v_mem + effective threshold + spike marks over the source
    history, plus a readout of its dominant input/output connections (from topology weights)."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel("Inspector · (nessun neurone)")
        self._title.setContentsMargins(6, 3, 6, 0)
        self._plot = pg.PlotWidget()
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", "v_mem")
        self._plot.setDownsampling(auto=True, mode="peak")
        self._plot.setClipToView(True)
        self._vmem = self._plot.plot(pen=pg.mkPen("#8fd6ff", width=2))
        self._vth = self._plot.plot(pen=pg.mkPen("#e8871e", width=1, style=Qt.DashLine))
        self._spk = pg.ScatterPlotItem(symbol="t", size=8, brush=pg.mkBrush("#ffffff"),
                                       pen=pg.mkPen(None))
        self._plot.addItem(self._spk)
        self._conn = QLabel("")
        self._conn.setContentsMargins(6, 0, 6, 4)
        layout.addWidget(self._title)
        layout.addWidget(self._plot, stretch=1)
        layout.addWidget(self._conn)
        self._cursors = [_add_cursor(self._plot.getPlotItem())]
        self._w_in = self._w_out = None
        self._i = None

    @property
    def neuron(self):
        return self._i

    def set_cursor(self, x):
        _set_cursor(self._cursors, x)

    def set_topology(self, w_in, w_rec, w_out):
        self._w_in = np.asarray(w_in, dtype=np.float64)      # (H, IN)
        self._w_out = np.asarray(w_out, dtype=np.float64)    # (OUT, H)

    def set_neuron(self, i):
        if i is None:
            self._i = None
            self._title.setText("Inspector · (nessun neurone)")
            self._conn.setText("")
            self._vmem.setData([]); self._vth.setData([]); self._spk.setData([])
            return
        self._i = int(i)
        self._title.setText(f"Inspector · hidden #{self._i}")
        self._conn.setText(self._dominant_text(self._i))

    def _dominant_text(self, i, k=2):
        if self._w_in is None:
            return ""
        win, wout = np.abs(self._w_in[i]), np.abs(self._w_out[:, i])
        ins = ", ".join(f"{_INPUT_NAMES[j] if j < len(_INPUT_NAMES) else j}·{win[j]:.2f}"
                        for j in np.argsort(win)[::-1][:k])
        outs = ", ".join(f"{PARAM_NAMES[j] if j < len(PARAM_NAMES) else j}·{wout[j]:.2f}"
                         for j in np.argsort(wout)[::-1][:k])
        return f"in: {ins}   →   out: {outs}"

    def update_frame(self, probe):
        if self._i is None:
            return
        frames = probe.frames()
        if not frames:
            return
        vm = np.array([f.v_mem[self._i] for f in frames])
        vth = np.array([f.v_th_eff[self._i] for f in frames])
        spk = np.array([f.spikes[self._i] for f in frames]) > 0
        self._vmem.setData(vm)
        self._vth.setData(vth)
        idx = np.nonzero(spk)[0]
        self._spk.setData([{"pos": (float(x), float(vm[x]))} for x in idx])


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
        self._cursors = [_add_cursor(self._plot.getPlotItem())]

    def set_cursor(self, x):
        _set_cursor(self._cursors, x)

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
        self._cursors = [_add_cursor(self._plot.getPlotItem())]

    def set_cursor(self, x):
        _set_cursor(self._cursors, x)

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
        self._cursors = [_add_cursor(p) for p in (self._pg, self._pv, self._pa)]

    def set_cursor(self, x):
        _set_cursor(self._cursors, x)

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
        self._cursors = [_add_cursor(p) for p in (self._pt, self._pd)]

    def set_cursor(self, x):
        _set_cursor(self._cursors, x)

    def update_frame(self, traj):
        a = traj.arrays()
        if a["t"].size == 0:
            return
        self._c_ttc.setData(np.clip(metrics.ttc(a["s"], a["dv"]), 0, _SAFETY_CAP))
        self._c_th.setData(np.clip(metrics.time_headway(a["s"], a["v"]), 0, _SAFETY_CAP))
        self._c_drac.setData(metrics.drac(a["s"], a["dv"]))
