"""Live network panel: firing-% readout + spike raster + v_mem (with effective threshold)
+ the 5 identified params, each on its OWN plot in physical units (linked X axis), with an
optional dashed ground-truth reference line."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_PARAM_NAMES = ["v0", "T", "s0", "a", "b"]
_PARAM_UNITS = ["m/s", "s", "m", "m/s^2", "m/s^2"]
_PARAM_COLORS = ["#d1495b", "#2a7fb8", "#7b3fa0", "#e8871e", "#2e8b57"]
_N_SAMPLE = 4


class NetPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self._firing_label = QLabel("network firing: --")
        self._firing_label.setStyleSheet("color:#e0e0e0; padding:2px 4px;")
        layout.addWidget(self._firing_label)

        self._raster_plot = pg.PlotWidget(title="spike raster")
        self._raster_plot.setLabel("bottom", "time", units="steps")
        self._raster_plot.setLabel("left", "neuron")
        self._raster_img = pg.ImageItem()
        self._raster_plot.addItem(self._raster_img)
        layout.addWidget(self._raster_plot, stretch=2)

        self._vmem_plot = pg.PlotWidget(title="v_mem (sample neurons) + effective threshold (dashed)")
        self._vmem_plot.setLabel("bottom", "time", units="steps")
        self._vmem_plot.setLabel("left", "v_mem")
        self._vmem_curves = [self._vmem_plot.plot(pen=pg.mkPen("#8fd6ff", width=1))
                             for _ in range(_N_SAMPLE)]
        self._vth_curves = [self._vmem_plot.plot(pen=pg.mkPen("#e8871e", width=1, style=Qt.DashLine))
                            for _ in range(_N_SAMPLE)]
        layout.addWidget(self._vmem_plot, stretch=2)

        # 5 per-param plots, physical units, X-linked
        self._param_glw = pg.GraphicsLayoutWidget()
        self._param_plots, self._param_curves, self._gt_lines = [], [], []
        for i, (name, unit, color) in enumerate(zip(_PARAM_NAMES, _PARAM_UNITS, _PARAM_COLORS)):
            p = self._param_glw.addPlot(row=i, col=0)
            p.setLabel("left", name, units=unit)
            p.showGrid(x=False, y=True, alpha=0.2)
            if i < len(_PARAM_NAMES) - 1:
                p.getAxis("bottom").setStyle(showValues=False)
            else:
                p.setLabel("bottom", "time", units="steps")
            if self._param_plots:
                p.setXLink(self._param_plots[0])
            curve = p.plot(pen=pg.mkPen(color, width=2))
            gt = pg.InfiniteLine(angle=0, movable=False,
                                 pen=pg.mkPen("#9a9a9a", width=1, style=Qt.DashLine))
            gt.setVisible(False)
            p.addItem(gt)
            self._param_plots.append(p)
            self._param_curves.append(curve)
            self._gt_lines.append(gt)
        layout.addWidget(self._param_glw, stretch=5)

        self._last_params = None
        self._gt = None

    def n_params_curves(self) -> int:
        return len(self._param_curves)

    def current_param_labels(self):
        if self._last_params is None:
            return []
        return [f"{n}={v:.2f}" for n, v in zip(_PARAM_NAMES, self._last_params)]

    def set_ground_truth(self, params_gt):
        """Draw a dashed reference line per param at params_gt[i] (context only). None hides them."""
        self._gt = np.asarray(params_gt, dtype=float) if params_gt is not None else None
        for i, line in enumerate(self._gt_lines):
            if self._gt is not None:
                line.setPos(float(self._gt[i]))
                line.setVisible(True)
            else:
                line.setVisible(False)

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
            self._firing_label.setText(
                f"network firing: {float(sm[-1].mean()) * 100:.1f}%   (mean {float(sm.mean()) * 100:.1f}%)")
        pm = probe.params_matrix()          # (frames, 5)
        if pm.size:
            self._last_params = pm[-1]
            for i, curve in enumerate(self._param_curves):
                curve.setData(pm[:, i])     # RAW physical value (no normalization)
                self._param_plots[i].setTitle(f"{_PARAM_NAMES[i]} = {pm[-1, i]:.2f} {_PARAM_UNITS[i]}")
