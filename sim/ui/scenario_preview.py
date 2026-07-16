"""ScenarioPreviewPanel — a dockable static preview of the scenario's leader profile with a tick marker.

The whole v_leader is known up front (materialise runs before the sim), so the curve is drawn once via
set_scenario() and only the marker moves (set_marker()). Self-contained: its own InfiniteLine, no coupling to
panels.py internals. The app drives the marker with the current TICK (live: the last result's t; scrub:
frames[idx].t) -- deliberately NOT a member of _ts_panels, whose set_cursor() receives a buffer index."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

# A narrow-band scenario (e.g. "following" = v_set + N(0, 0.3)) would let the Y-axis autorange zoom onto a
# ~2 m/s window, blowing tiny jitter up to full plot height and reading as alarming noise. Floor the view
# span so such a leader reads as a near-flat cruise; wider scenarios still fit their own data.
_MIN_Y_SPAN = 15.0   # m/s


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
        """Draw the whole leader profile once. x = tick index (0..N-1), y = leader speed (m/s).

        The Y-range is floored to _MIN_Y_SPAN so a narrow-band scenario does not zoom in and amplify jitter;
        wider scenarios fit their own data with light padding. The bottom stays >= 0 (speed is non-negative)."""
        v = np.asarray(v_leader, dtype=float)
        self._curve.setData(v)
        if v.size:
            dmin, dmax = float(v.min()), float(v.max())
            span = dmax - dmin
            if span < _MIN_Y_SPAN:
                center = 0.5 * (dmin + dmax)
                lo, hi = center - _MIN_Y_SPAN / 2, center + _MIN_Y_SPAN / 2
            else:
                pad = 0.05 * span
                lo, hi = dmin - pad, dmax + pad
            if lo < 0.0:                       # shift up rather than clip -- keep the span, never show negative speed
                hi -= lo
                lo = 0.0
            self._plot.setYRange(lo, hi, padding=0)

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
