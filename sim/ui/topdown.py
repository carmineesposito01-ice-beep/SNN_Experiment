"""Top-down road view: ego pinned centre-screen while a dashed road + leader scroll past.
Gap between ego and leader is drawn and coloured by time-to-collision (TTC)."""
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QGraphicsLineItem, QGraphicsPolygonItem,
                               QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem,
                               QGraphicsView)

from config import DT
from utils.closed_loop_eval import TTC_STAR as TTC_DANGER   # single source for the 1.5 s critical-TTC threshold

PX_PER_M = 8.0
VEH_LEN_M = 5.0
VEH_W_M = 2.2
LANE_H_M = 8.0
ROAD_X0_M = -200.0
ROAD_LEN_M = 5000.0
DASH_EVERY_M = 12.0

TTC_CAUTION = 4.0
_COL = {"safe": "#2e8b57", "caution": "#e8871e", "danger": "#d1495b"}

GHOST_COLOR = "#9a9a9a"      # oracle ("Master Splinter"), same reference grey as the panels
GHOST_OPACITY = 0.45


def ttc_color(s, dv):
    """'safe'|'caution'|'danger' from gap s [m] and closing speed dv [m/s] (>0 = closing)."""
    if dv <= 0.1:
        return "safe"
    ttc = s / dv
    if ttc < TTC_DANGER:
        return "danger"
    if ttc < TTC_CAUTION:
        return "caution"
    return "safe"


class TopDownView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene()
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QBrush(QColor("#3a3a3a")))
        self._ttc_colors = {k: QColor(v) for k, v in _COL.items()}          # 3 fixed TTC colours, once
        self._ttc_pens = {k: QPen(QColor(v), 2, Qt.DashLine) for k, v in _COL.items()}   # (no per-frame alloc)
        self._ego_x = 0.0
        self._last_s = 0.0
        self._build_road()
        self._ego = self._vehicle("#2a7fb8")
        self._leader = self._vehicle("#d1495b")
        self._ego_label = self._label("ego")
        self._leader_label = self._label("leader")
        self._ghost_x = 0.0
        self._ghost = self._vehicle(GHOST_COLOR)
        self._ghost.setOpacity(GHOST_OPACITY)
        self._ghost_label = self._label("oracolo")
        self._ghost_label.setDefaultTextColor(QColor(GHOST_COLOR))
        self._set_ghost_visible_items(False)          # off until the toggle asks for it
        self._gap_line = QGraphicsLineItem()
        self._scene.addItem(self._gap_line)
        self._gap_text = self._label("")

    def _build_road(self):
        top = -LANE_H_M / 2 * PX_PER_M
        h = LANE_H_M * PX_PER_M
        x0 = ROAD_X0_M * PX_PER_M
        w = ROAD_LEN_M * PX_PER_M
        road = QGraphicsRectItem(QRectF(x0, top, w, h))
        road.setBrush(QBrush(QColor("#2b2b2b")))
        road.setPen(QPen(Qt.NoPen))
        self._scene.addItem(road)
        for y in (top, top + h):
            e = QGraphicsLineItem(x0, y, x0 + w, y)
            e.setPen(QPen(QColor("#d0d0d0"), 2))
            self._scene.addItem(e)
        n = int(ROAD_LEN_M / DASH_EVERY_M)
        for i in range(n):
            x = (ROAD_X0_M + i * DASH_EVERY_M) * PX_PER_M
            d = QGraphicsLineItem(x, 0, x + DASH_EVERY_M * 0.5 * PX_PER_M, 0)
            d.setPen(QPen(QColor("#f0c419"), 2))
            self._scene.addItem(d)
        self._scene.setSceneRect(x0, top - 60, w, h + 120)

    def _vehicle(self, color):
        w, h = VEH_LEN_M * PX_PER_M, VEH_W_M * PX_PER_M
        pts = QPolygonF([QPointF(-w / 2, -h / 2), QPointF(w * 0.28, -h / 2),
                         QPointF(w / 2, 0), QPointF(w * 0.28, h / 2),
                         QPointF(-w / 2, h / 2)])          # arrow-nosed car (points +x)
        item = QGraphicsPolygonItem(pts)
        item.setBrush(QBrush(QColor(color)))
        item.setPen(QPen(QColor("#101010"), 1.5))
        self._scene.addItem(item)
        return item

    def _label(self, text):
        t = QGraphicsTextItem(text)
        t.setDefaultTextColor(QColor("#e6e6e6"))
        f = QFont()
        f.setPointSize(9)
        t.setFont(f)
        self._scene.addItem(t)
        return t

    def reset(self):
        """Reset the integrated ego position (called per episode). Without this the car drives off
        the finite road across successive runs, and live vs scrub (which recomputes x = Σv·DT from 0)
        would disagree from the 2nd episode on. Same reasoning for the ghost."""
        self._ego_x = 0.0
        self._last_s = 0.0
        self._ghost_x = 0.0
        self._place_ghost(0.0)

    def ego_x_m(self):
        return self._ego_x

    # ---- oracle ghost: integrated exactly like the ego, drawn only when the toggle is on ----
    def _set_ghost_visible_items(self, on):
        self._ghost.setVisible(bool(on))
        self._ghost_label.setVisible(bool(on))

    def set_ghost_visible(self, on):
        self._set_ghost_visible_items(on)

    def ghost_x_m(self):
        return self._ghost_x

    def _place_ghost(self, ghost_x):
        self._ghost_x = ghost_x
        px = self._ghost_x * PX_PER_M
        self._ghost.setPos(px, 0)
        self._ghost_label.setPos(px - 20, VEH_W_M * PX_PER_M + 18)

    def update_ghost(self, r):
        """Integrate the oracle's position exactly like the ego's (see update_frame)."""
        self._place_ghost(self._ghost_x + r.v * DT)

    def advance_ghost(self, r):
        """Integrate without rendering -- mirrors advance() for coalesced ticks at speed>1."""
        self._ghost_x += r.v * DT

    def render_ghost_at(self, traj, index):
        """Reconstruct the oracle's position at buffer position `index`: x = Σ v·DT up to index."""
        a = traj.arrays()
        if a["t"].size == 0:
            return
        n = a["t"].size
        i = index if index >= 0 else n + index
        i = max(0, min(i, n - 1))
        self._place_ghost(float(a["v"][:i + 1].sum() * DT))

    def leader_x_m(self):
        return self._ego_x + VEH_LEN_M + self._last_s

    def _place(self, ego_x, s, dv):
        self._ego_x = ego_x
        self._last_s = s
        ego_px = self._ego_x * PX_PER_M
        leader_px = self.leader_x_m() * PX_PER_M
        self._ego.setPos(ego_px, 0)
        self._leader.setPos(leader_px, 0)
        self._ego_label.setPos(ego_px - 12, -VEH_W_M * PX_PER_M - 8)
        self._leader_label.setPos(leader_px - 18, -VEH_W_M * PX_PER_M - 8)
        key = ttc_color(s, dv)                             # index the cached pens/colours (setPen/setColor copy)
        y = VEH_W_M * PX_PER_M + 4
        self._gap_line.setLine(ego_px + VEH_LEN_M / 2 * PX_PER_M, y,
                               leader_px - VEH_LEN_M / 2 * PX_PER_M, y)
        self._gap_line.setPen(self._ttc_pens[key])
        self._gap_text.setPlainText(f"s = {s:.1f} m")
        self._gap_text.setDefaultTextColor(self._ttc_colors[key])
        self._gap_text.setPos((ego_px + leader_px) / 2 - 22, y + 2)
        self.centerOn(ego_px, 0)                           # follow ego (pinned centre)

    def advance(self, r):
        """Integrate ego position WITHOUT rendering -- for intermediate ticks at speed>1, whose paint
        would be coalesced away anyway. Keeps _ego_x/_last_s identical to update_frame's accumulation."""
        self._ego_x += r.v * DT
        self._last_s = r.s

    def update_frame(self, r):
        self._place(self._ego_x + r.v * DT, r.s, r.dv)     # integrate ego position

    def render_at(self, traj, index):
        """Reconstruct ego/leader at buffer position `index` (for scrub): ego_x = Σ v·DT up to index."""
        a = traj.arrays()
        if a["t"].size == 0:
            return
        n = a["t"].size
        i = index if index >= 0 else n + index
        i = max(0, min(i, n - 1))
        self._place(float(a["v"][:i + 1].sum() * DT), float(a["s"][i]), float(a["dv"][i]))
