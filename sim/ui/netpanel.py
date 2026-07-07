"""Live network panel: spike raster + v_mem (with effective threshold) + the 5 identified
params normalised to their physical range (so all are visible), current values in the title."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

_PARAM_NAMES = ["v0", "T", "s0", "a", "b"]
_PARAM_COLORS = ["#d1495b", "#2a7fb8", "#7b3fa0", "#e8871e", "#2e8b57"]
_BOUNDS = [(8.0, 45.0), (0.5, 2.5), (1.0, 5.0), (0.3, 2.5), (0.5, 3.0)]
_N_SAMPLE = 4


class NetPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self._raster_plot = pg.PlotWidget(title="spike raster")
        self._raster_plot.setLabel("bottom", "time", units="steps")
        self._raster_plot.setLabel("left", "neuron")
        self._raster_img = pg.ImageItem()
        self._raster_plot.addItem(self._raster_img)
        layout.addWidget(self._raster_plot)

        self._vmem_plot = pg.PlotWidget(title="v_mem (sample neurons) + effective threshold (dashed)")
        self._vmem_plot.setLabel("bottom", "time", units="steps")
        self._vmem_plot.setLabel("left", "v_mem")
        self._vmem_curves = [self._vmem_plot.plot(pen=pg.mkPen("#8fd6ff", width=1))
                             for _ in range(_N_SAMPLE)]
        self._vth_curves = [self._vmem_plot.plot(pen=pg.mkPen("#e8871e", width=1, style=Qt.DashLine))
                            for _ in range(_N_SAMPLE)]
        layout.addWidget(self._vmem_plot)

        self._param_plot = pg.PlotWidget(title="identified params (normalised)")
        self._param_plot.setLabel("bottom", "time", units="steps")
        self._param_plot.setLabel("left", "0..1 of physical range")
        self._param_plot.setYRange(-0.05, 1.05)
        self._param_plot.addLegend(offset=(-10, 10))
        self._param_curves = [self._param_plot.plot(pen=pg.mkPen(c, width=2), name=n)
                              for n, c in zip(_PARAM_NAMES, _PARAM_COLORS)]
        layout.addWidget(self._param_plot)
        self._last_params = None

    def n_params_curves(self) -> int:
        return len(self._param_curves)

    def current_param_labels(self):
        if self._last_params is None:
            return []
        return [f"{n}={v:.2f}" for n, v in zip(_PARAM_NAMES, self._last_params)]

    def update_frame(self, probe):
        frames = probe.frames()
        sm = probe.spikes_matrix()          # (frames, H)
        if sm.size:
            self._raster_img.setImage(sm.T, autoLevels=False, levels=(0.0, 1.0))
            vm = np.stack([f.v_mem for f in frames])
            vth = np.stack([f.v_th_eff for f in frames])
            for i in range(min(_N_SAMPLE, vm.shape[1])):
                self._vmem_curves[i].setData(vm[:, i])
                self._vth_curves[i].setData(vth[:, i])
        pm = probe.params_matrix()          # (frames, 5)
        if pm.size:
            self._last_params = pm[-1]
            for i, curve in enumerate(self._param_curves):
                lo, hi = _BOUNDS[i]
                curve.setData(np.clip((pm[:, i] - lo) / (hi - lo), -0.05, 1.05))
            self._param_plot.setTitle("params (norm):  " + "   ".join(self.current_param_labels()))
