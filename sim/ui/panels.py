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


class RasterPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="spike raster")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", "neuron")
        self._img = pg.ImageItem()
        self._plot.addItem(self._img)
        layout.addWidget(self._plot)

    def update_frame(self, probe):
        sm = probe.spikes_matrix()
        if sm.size:
            self._img.setImage(sm.T, autoLevels=False, levels=(0.0, 1.0))


class VmemPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="v_mem (sample neurons) + effective threshold (dashed)")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", "v_mem")
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
