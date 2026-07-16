"""DurationHandles -- x-draggable vertical edges on a pyqtgraph plot, one per block, that set a block's
duration by dragging its right edge.

COMMIT-ON-FINISH: on_resize fires on the drag RELEASE (sigPositionChangeFinished), not continuously.
That is deliberate -- re-placing the lines (clear + recreate) then happens with no drag active, so it
cannot destroy the line under the cursor, and the value->handle loop cannot form. During the drag only
the line moves (immediate feedback); the curve + boundaries snap on release.

Sibling to DragHandles. Same "no hit-testing, drive it from the signal" pattern; pg.InfiniteLine is used
as-is (subclassing it crashes, per the 4b lesson with TargetItem). setBounds clamps in place and the
signal reports the CLAMPED value (measured).
"""
import pyqtgraph as pg


class DurationHandles:
    def __init__(self, plot, on_resize):
        self._plot = plot
        self._on_resize = on_resize            # on_resize(id, new_ticks) -- once, on drag release
        self._lines = []
        self._placing = False

    def __len__(self):
        return len(self._lines)

    def set_edges(self, edges):
        """edges: list of (id, start, ticks, cap). A vertical line at start+ticks, bounded to
        [start+1, start+cap] so it cannot cross the block's start or exceed its cap. Silent."""
        self.clear()
        self._placing = True
        try:
            for eid, start, ticks, cap in edges:
                ln = pg.InfiniteLine(pos=start + ticks, angle=90, movable=True,
                                     pen=pg.mkPen("#8ab4d8", width=2))
                ln.setBounds([start + 1, start + cap])
                ln._id = eid
                ln._start = int(start)
                ln.sigPositionChangeFinished.connect(self._on_finish)
                self._plot.addItem(ln)
                self._lines.append(ln)
        finally:
            self._placing = False

    def clear(self):
        for ln in self._lines:
            self._plot.removeItem(ln)
        self._lines = []

    def _on_finish(self, line):
        if self._placing:
            return
        self._on_resize(line._id, max(1, int(round(line.value())) - line._start))
