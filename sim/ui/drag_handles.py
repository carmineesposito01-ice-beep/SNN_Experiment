"""DragHandles -- a row of vertically-draggable nodes on a pyqtgraph plot.

Isolated on purpose: the drag is the one piece of the scenario builder with a measured risk (mouse
interaction), so it lives behind a small interface and is tested alone. Two measured facts shape it:
pg.TargetItem is a ready draggable handle (no hit-testing to write), and constraining it to vertical
by reconnecting x in sigPositionChanged converges in 2 calls -- while subclassing setPos crashes
inside TargetItem.__init__, which passes a tuple.
"""
import numpy as np
import pyqtgraph as pg

from sim.scenario_spec import V_RANGE


class DragHandles:
    def __init__(self, plot, on_change):
        self._plot = plot
        self._on_change = on_change            # called once per user drag, never during set_speeds
        self._items = []
        self._placing = False                  # guard: set_speeds must not look like a user edit

    def __len__(self):
        return len(self._items)

    def speeds(self):
        return [float(h.pos().y()) for h in self._items]

    def set_speeds(self, ticks, speeds):
        """Place one handle per (tick, speed). Silent: placement is not a user edit."""
        self.clear()
        self._placing = True
        try:
            for x, y in zip(ticks, speeds):
                h = pg.TargetItem(pos=(float(x), float(np.clip(y, *V_RANGE))), movable=True, size=11,
                                  symbol="o", pen=pg.mkPen("#ffffff", width=2),
                                  brush=pg.mkBrush("#2a7fb8"))
                h._tick = float(x)
                h.sigPositionChanged.connect(self._constrain)
                self._plot.addItem(h)
                self._items.append(h)
        finally:
            self._placing = False

    def clear(self):
        for h in self._items:
            self._plot.removeItem(h)
        self._items = []

    def _constrain(self, item):
        """Lock x to the node's tick and clamp y to V_RANGE. Re-snapping x re-emits, but the second
        pass is a no-op (x already == tick, y already clamped), so it converges in 2 calls (measured).
        The return after the corrective setPos lets the re-entrant call be the one that fires
        on_change, so a drag notifies ONCE, not twice."""
        y_clamped = float(np.clip(item.pos().y(), *V_RANGE))
        if item.pos().x() != item._tick or item.pos().y() != y_clamped:
            item.setPos(item._tick, y_clamped)             # re-enters _constrain once, then converges
            return
        if not self._placing:
            self._on_change()
