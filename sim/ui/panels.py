"""Individual live network graphs as standalone dockable widgets: RasterPanel (spike raster),
VmemPanel (v_mem sample traces + effective threshold), ParamPanel (one identified param in physical
units with an optional dashed ground-truth reference line and the live value in the title)."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

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


_GROUP_BORDERS = [("input", "#2a7fb8"), ("hidden", "#7b3fa0"), ("output", "#2e8b57")]


class NeuronStatePanel(QWidget):
    """Instantaneous neuron-state map at the latest tick: input | hidden | output groups with
    coloured borders; hidden = v_mem heat (viridis) + white overlay on neurons that spiked this tick."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._glw = pg.GraphicsLayoutWidget()
        layout.addWidget(self._glw)
        self._cmap = pg.colormap.get("viridis")
        self._lut = self._cmap.getLookupTable(0.0, 1.0, 256)
        self._groups = {}     # name -> (plot, heat_img, overlay_img_or_None)
        for col, (name, color) in enumerate(_GROUP_BORDERS):
            p = self._glw.addPlot(row=0, col=col)   # groups side by side: input | hidden | output
            p.setTitle(name)
            p.hideAxis("left")
            p.hideAxis("bottom")
            p.getViewBox().setBorder(pg.mkPen(color, width=2))
            heat = pg.ImageItem()
            heat.setColorMap(self._cmap)
            p.addItem(heat)
            overlay = None
            if name == "hidden":
                overlay = pg.ImageItem()      # drawn on top of the heat
                p.addItem(overlay)
            self._groups[name] = (p, heat, overlay)
        for c, factor in enumerate((1, 4, 1)):   # give the 32-neuron hidden grid the width
            self._glw.ci.layout.setColumnStretchFactor(c, factor)

    def _set_strip(self, name, values):
        _, heat, _ = self._groups[name]
        heat.setImage(np.asarray(values, dtype=np.float64).reshape(1, -1), autoLevels=True)

    def _set_hidden(self, v_mem, spikes):
        _, heat, overlay = self._groups["hidden"]
        v = np.asarray(v_mem, dtype=np.float64).reshape(-1)
        H = v.size
        rows = max(1, int(np.floor(np.sqrt(H))))
        cols = int(np.ceil(H / rows))
        vmin, vmax = float(np.nanmin(v)), float(np.nanmax(v))
        idx = np.clip(((v - vmin) / (vmax - vmin + 1e-9) * 255).astype(int), 0, 255)
        base = np.zeros((rows * cols, 4), dtype=np.ubyte)
        base[:H, :3] = self._lut[idx][:, :3]
        base[:H, 3] = 255
        heat.setImage(base.reshape(rows, cols, 4))
        ov = np.zeros((rows * cols, 4), dtype=np.ubyte)
        spk = np.zeros(rows * cols, dtype=bool)
        spk[:H] = np.asarray(spikes, dtype=np.float64).reshape(-1)[:H] > 0
        ov[spk] = [255, 255, 255, 180]
        overlay.setImage(ov.reshape(rows, cols, 4))

    def update_frame(self, probe):
        frames = probe.frames()
        if not frames:
            return
        f = frames[-1]
        if f.input is not None and np.size(f.input):
            self._set_strip("input", f.input)
        self._set_hidden(f.v_mem, f.spikes)
        self._set_strip("output", f.params)


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
