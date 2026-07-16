"""ScenarioPreviewPanel — a dockable static preview of the scenario's leader profile with a tick marker.

The whole v_leader is known up front (materialise runs before the sim), so the curve is drawn once via
set_scenario() and only the marker moves (set_marker()). Self-contained: its own InfiniteLine, no coupling to
panels.py internals. The app drives the marker with the current TICK (live: the last result's t; scrub:
frames[idx].t) -- deliberately NOT a member of _ts_panels, whose set_cursor() receives a buffer index."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget


class ScenarioPreviewPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="scenario")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", "v_leader", units="m/s")
        self._plot.setMouseEnabled(x=True, y=False)
        self._curve = self._plot.plot(pen=pg.mkPen("#e8871e", width=2))   # static, no downsampling: getData is exact
        self._marker = pg.InfiniteLine(angle=90, movable=False,
                                       pen=pg.mkPen("#ffffff", width=1, style=Qt.DashLine))
        self._marker.setVisible(False)
        self._plot.addItem(self._marker)
        layout.addWidget(self._plot)

    def set_scenario(self, v_leader):
        """Draw the whole leader profile once. x = tick index (0..N-1), y = leader speed (m/s)."""
        self._curve.setData(np.asarray(v_leader, dtype=float))

    def set_marker(self, tick):
        """Move the marker to `tick` (a sim tick); hide it when tick is None."""
        if tick is None:
            self._marker.setVisible(False)
        else:
            self._marker.setPos(float(tick))
            self._marker.setVisible(True)

    def clear(self):
        self._curve.setData([])
        self._marker.setVisible(False)
