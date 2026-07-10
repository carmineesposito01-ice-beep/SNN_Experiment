"""PostRunPage -- aggregate 'report card' of the one episode just run (fed by EpisodeSummary).
Third mode of the simulator (Live / Meso-Macro / Post-run)."""
import pyqtgraph as pg
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

_GROUPS = [
    ("Esito", [("esito", "esito", ""), ("durata", "duration_s", " s")]),
    ("Sicurezza", [("min gap", "min_gap", " m"), ("min TTC", "min_ttc", " s"),
                   ("max decel", "max_decel", " m/s²")]),
    ("Comfort", [("RMS accel", "rms_accel", " m/s²"), ("RMS jerk", "rms_jerk", " m/s³")]),
    ("Efficienza", [("energia SNN", "snn_pj", " pJ"), ("energia ANN", "ann_pj", " pJ"),
                    ("vantaggio", "advantage", "×")]),
    ("Rete", [("firing medio", "mean_firing_pct", " %"), ("firing picco", "peak_firing_pct", " %")]),
]


class PostRunPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        self._header = QLabel("—"); self._header.setStyleSheet("font-weight: bold; font-size: 14px;")
        root.addWidget(self._header)
        grid = QGridLayout(); root.addLayout(grid)
        self._values = {}
        self._suffix = {}
        row = 0
        for group, fields in _GROUPS:
            g = QLabel(group); g.setStyleSheet("font-weight: bold; color: #8a6fb0;")
            grid.addWidget(g, row, 0, 1, 2); row += 1
            for label, key, suffix in fields:
                grid.addWidget(QLabel(label), row, 0)
                v = QLabel("—"); self._values[key] = v; self._suffix[key] = suffix
                grid.addWidget(v, row, 1); row += 1
        self._v_plot = pg.PlotWidget(title="velocità v(t)")
        self._v_plot.setLabel("bottom", "time", units="steps"); self._v_plot.setLabel("left", "v", units="m/s")
        self._gap_plot = pg.PlotWidget(title="gap(t)")
        self._gap_plot.setLabel("bottom", "time", units="steps"); self._gap_plot.setLabel("left", "gap", units="m")
        self._v_plot.setXLink(self._gap_plot)
        self._v_curve = self._v_plot.plot(pen=pg.mkPen("#2a7fb8", width=2))
        self._gap_curve = self._gap_plot.plot(pen=pg.mkPen("#2e8b57", width=2))
        root.addWidget(self._v_plot, stretch=1); root.addWidget(self._gap_plot, stretch=1)

    def set_summary(self, s, rows, champion, scenario):
        self._header.setText(f"{champion} · {scenario}")
        disp = dict(s)
        disp["esito"] = "COLLISIONE" if s.get("collided") else "ok"
        for key, lbl in self._values.items():
            val = disp.get(key)
            if key == "min_ttc" and val == float("inf"):
                text = "∞"
            else:
                text = f"{val}{self._suffix[key]}"
            lbl.setText(text)
        self._values["esito"].setStyleSheet(
            "color: #d1495b; font-weight: bold;" if s.get("collided") else "color: #2e8b57; font-weight: bold;")
        t = [r[0] for r in rows]; v = [r[2] for r in rows]; gap = [r[1] for r in rows]
        self._v_curve.setData(t, v); self._gap_curve.setData(t, gap)
