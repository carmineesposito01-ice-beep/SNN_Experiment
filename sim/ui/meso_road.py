"""Platoon road view: the N vehicles on the carriageway, coloured by speed; a slider + Play scrub /
animate the RECORDED platoon run (the rec from run_platoon). Distinct from the live single-vehicle
TopDownView; it reuses that view's road constants + car shape."""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QGraphicsPolygonItem, QGraphicsRectItem, QGraphicsScene,
                               QGraphicsView, QHBoxLayout, QPushButton, QSlider, QVBoxLayout, QWidget)

from sim.ui.topdown import DASH_EVERY_M, LANE_H_M, PX_PER_M, VEH_LEN_M, VEH_W_M

_FPS_MS = 33          # ~30 fps playback


class PlatoonRoadView(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(170)
        self._lut = pg.colormap.get("viridis").getLookupTable(0.0, 1.0, 256)
        self._rec = None
        self._cars = []
        self._vmax = 1.0
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        self._view = QGraphicsView()
        self._view.setRenderHint(QPainter.Antialiasing)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setBackgroundBrush(QBrush(QColor("#3a3a3a")))
        self._scene = QGraphicsScene(); self._view.setScene(self._scene)
        root.addWidget(self._view, stretch=1)
        row = QHBoxLayout()
        self._play_btn = QPushButton("▶"); self._play_btn.setCheckable(True); self._play_btn.setFixedWidth(36)
        self._slider = QSlider(Qt.Horizontal); self._slider.setEnabled(False)
        row.addWidget(self._play_btn); row.addWidget(self._slider, stretch=1)
        root.addLayout(row)
        self._timer = QTimer(self); self._timer.setInterval(_FPS_MS)
        self._timer.timeout.connect(self._tick)
        self._play_btn.toggled.connect(self._on_play)
        self._slider.valueChanged.connect(self.render_frame)

    def _build_road(self, xlo, xhi):
        self._scene.clear(); self._cars = []
        top = -LANE_H_M / 2 * PX_PER_M
        h = LANE_H_M * PX_PER_M
        x0 = (xlo - 50.0) * PX_PER_M
        w = (xhi - xlo + 100.0) * PX_PER_M
        road = QGraphicsRectItem(QRectF(x0, top, w, h))
        road.setBrush(QBrush(QColor("#2b2b2b"))); road.setPen(QPen(Qt.NoPen))
        self._scene.addItem(road)
        for y in (top, top + h):
            self._scene.addLine(x0, y, x0 + w, y, QPen(QColor("#d0d0d0"), 2))
        n = int(w / (DASH_EVERY_M * PX_PER_M))
        for i in range(n):
            x = x0 + i * DASH_EVERY_M * PX_PER_M
            self._scene.addLine(x, 0, x + DASH_EVERY_M * 0.5 * PX_PER_M, 0, QPen(QColor("#f0c419"), 2))
        self._scene.setSceneRect(x0, top - 40, w, h + 80)

    def _car(self):
        w, h = VEH_LEN_M * PX_PER_M, VEH_W_M * PX_PER_M
        pts = QPolygonF([QPointF(-w / 2, -h / 2), QPointF(w * 0.28, -h / 2),
                         QPointF(w / 2, 0), QPointF(w * 0.28, h / 2), QPointF(-w / 2, h / 2)])
        item = QGraphicsPolygonItem(pts); item.setPen(QPen(QColor("#101010"), 1.0))
        self._scene.addItem(item)
        return item

    def set_run(self, rec):
        x = np.asarray(rec["x"]); v = np.asarray(rec["v"])
        if x.ndim != 2 or x.size == 0:
            return
        self._rec = {"x": x, "v": v}
        self._vmax = max(1.0, float(np.max(v)))
        self._build_road(float(np.min(x)), float(np.max(x)))
        self._cars = [self._car() for _ in range(x.shape[1])]
        self._slider.setEnabled(True); self._slider.setRange(0, x.shape[0] - 1)
        self._slider.blockSignals(True); self._slider.setValue(0); self._slider.blockSignals(False)
        self.render_frame(0)

    def render_frame(self, t):
        if self._rec is None:
            return
        x = self._rec["x"]; v = self._rec["v"]
        t = max(0, min(int(t), x.shape[0] - 1))
        for i, car in enumerate(self._cars):
            car.setPos(float(x[t, i]) * PX_PER_M, 0.0)
            frac = max(0.0, min(1.0, float(v[t, i]) / self._vmax))
            r, g, b = self._lut[int(frac * 255)][:3]
            car.setBrush(QBrush(QColor(int(r), int(g), int(b))))
        self._view.centerOn(float(np.mean(x[t])) * PX_PER_M, 0.0)

    def _tick(self):
        self._slider.setValue((self._slider.value() + 1) % (self._slider.maximum() + 1))

    def _on_play(self, playing):
        self._play_btn.setText("❚❚" if playing else "▶")
        if playing and self._rec is not None:
            self._timer.start()
        else:
            self._timer.stop()

    def stop(self):
        self._play_btn.setChecked(False)      # untoggling stops the timer via _on_play
