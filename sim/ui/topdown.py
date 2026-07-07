"""Top-down view: ego (pinned) + leader, camera follows ego. Positions are (x, y, heading)
with y=0/heading=0 in v1 (2D-ready for future lane changes, design §9)."""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsView

PX_PER_M = 6.0
VEH_LEN_M = 5.0
VEH_W_M = 2.0


class TopDownView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene()
        self.setScene(self._scene)
        self._ego = self._vehicle(QColor("#2a7fb8"))       # ego (blue)
        self._leader = self._vehicle(QColor("#d1495b"))    # leader (red)
        self._ego.setPos(0.0, 0.0)

    def _vehicle(self, color):
        w, h = VEH_LEN_M * PX_PER_M, VEH_W_M * PX_PER_M
        item = QGraphicsRectItem(QRectF(-w / 2, -h / 2, w, h))
        item.setBrush(QBrush(color))
        self._scene.addItem(item)
        return item

    def leader_x_px(self) -> float:
        return float(self._leader.x())

    def update_frame(self, r):
        self._leader.setX((r.s + VEH_LEN_M) * PX_PER_M)    # gap ahead of ego
        self.centerOn(self._ego)                            # follow ego
