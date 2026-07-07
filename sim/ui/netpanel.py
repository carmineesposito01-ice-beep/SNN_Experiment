"""Live network panel: spike raster (ImageItem), v_mem trace, 5 identified params."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget

_PARAM_NAMES = ["v0", "T", "s0", "a", "b"]
_PARAM_COLORS = ["#d1495b", "#2a7fb8", "#7b3fa0", "#e8871e", "#2e8b57"]


class NetPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self._raster_plot = pg.PlotWidget(title="spike raster (neuron x time)")
        self._raster_img = pg.ImageItem()
        self._raster_plot.addItem(self._raster_img)
        layout.addWidget(self._raster_plot)

        self._vmem_plot = pg.PlotWidget(title="v_mem (sample neurons)")
        self._vmem_curves = [self._vmem_plot.plot(pen=pg.mkPen(width=1)) for _ in range(4)]
        layout.addWidget(self._vmem_plot)

        self._param_plot = pg.PlotWidget(title="identified params [v0,T,s0,a,b]")
        self._param_curves = [self._param_plot.plot(pen=pg.mkPen(c, width=2), name=n)
                              for n, c in zip(_PARAM_NAMES, _PARAM_COLORS)]
        layout.addWidget(self._param_plot)

    def n_params_curves(self) -> int:
        return len(self._param_curves)

    def update_frame(self, probe):
        frames = probe.frames()
        sm = probe.spikes_matrix()          # (frames, H)
        if sm.size:
            self._raster_img.setImage(sm.T, autoLevels=False, levels=(0.0, 1.0))
            vm = np.stack([f.v_mem for f in frames])   # (frames, H)
            for i, curve in enumerate(self._vmem_curves):
                if i < vm.shape[1]:
                    curve.setData(vm[:, i])
        pm = probe.params_matrix()          # (frames, 5)
        if pm.size:
            for i, curve in enumerate(self._param_curves):
                curve.setData(pm[:, i])
