"""PostRunPage -- exhaustive 'report card' of the one episode just run (fed by EpisodeSummary v2).
Third mode (Live / Meso-Macro / Post-run). Every metric carries a '?' hover tooltip with its
definition + formula (grounded in HOW_IT_WORKS_v3 / VALIDATION_REPORT_v3 / FPGA_REPORT)."""
import pyqtgraph as pg
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

# (group title, [(display label, summary key, suffix)])
_GROUPS = [
    ("Identificazione", [("accuratezza", "id_accuracy", " %"), ("err v0", "param_rmse_v0", ""),
                         ("err T", "param_rmse_T", ""), ("err s0", "param_rmse_s0", ""),
                         ("err a", "param_rmse_a", ""), ("err b", "param_rmse_b", "")]),
    ("Sicurezza", [("esito", "esito", ""), ("min gap", "min_gap", " m"), ("min TTC", "min_ttc", " s"),
                   ("brake margin", "brake_margin_min", " m"), ("max DRAC", "max_DRAC", " m/s²"),
                   ("TET", "TET", " s"), ("TIT", "TIT", " s·s"), ("impact Δv", "impact_dv", " m/s")]),
    ("Comfort", [("RMS accel", "rms_accel", " m/s²"), ("max decel", "max_decel", " m/s²"),
                 ("RMS jerk", "rms_jerk", " m/s³"), ("frac decel ISO", "frac_decel_iso_viol", ""),
                 ("frac accel ISO", "frac_accel_iso_viol", "")]),
    ("Salute rete / FPGA", [("firing medio", "mean_firing_pct", " %"), ("firing picco", "peak_firing_pct", " %"),
                            ("neuroni morti", "dead_pct", " %"), ("spike max/tick", "max_spikes_tick", ""),
                            ("ρ(U·V)", "rho", "")]),
    ("Efficienza", [("energia SNN", "snn_pj", " pJ"), ("energia ANN", "ann_pj", " pJ"),
                    ("vantaggio", "advantage", "×"), ("  fc", "e_fc", " pJ"), ("  rec_V", "e_recV", " pJ"),
                    ("  rec_U", "e_recU", " pJ"), ("  out", "e_out", " pJ")]),
]

_METRIC_HELP = {
    "id_accuracy": "<b>Accuratezza identificazione</b><br>Quanto la SNN indovina i 5 parametri ACC-IIDM veri.<br>"
                   "formula: 100·(1 − media_i(RMSE_i/|GT_i|)), RMSE_i = √⟨(pred_i−GT_i)²⟩",
    "param_rmse_v0": "<b>Errore v0</b> (velocità desiderata) — RMSE della predizione vs il valore vero.<br>"
                     "RMSE = √⟨(v0_pred(t) − v0_GT)²⟩",
    "param_rmse_T": "<b>Errore T</b> (time-gap desiderato) — RMSE della predizione vs il valore vero.<br>"
                    "RMSE = √⟨(T_pred(t) − T_GT)²⟩",
    "param_rmse_s0": "<b>Errore s0</b> (gap minimo) — RMSE della predizione vs il valore vero.<br>"
                     "RMSE = √⟨(s0_pred(t) − s0_GT)²⟩",
    "param_rmse_a": "<b>Errore a</b> (accelerazione max) — RMSE della predizione vs il valore vero.<br>"
                    "RMSE = √⟨(a_pred(t) − a_GT)²⟩",
    "param_rmse_b": "<b>Errore b</b> (decelerazione confortevole) — RMSE della predizione vs il valore vero.<br>"
                    "RMSE = √⟨(b_pred(t) − b_GT)²⟩",
    "esito": "<b>Esito</b> — collisione se il gap tocca 0 in questo episodio (altrimenti 'ok').",
    "min_gap": "<b>Gap minimo</b> [m] — distanza minima ego↔leader nell'episodio.",
    "min_ttc": "<b>Time-To-Collision minimo</b> [s].<br>TTC = gap/Δv (se Δv>0, avvicinamento); min sull'episodio.",
    "brake_margin_min": "<b>Margine di frenata</b> [m, con segno] — distanza dal confine di evitabilità fisica.<br>"
                        "brake_margin = s − max(0,Δv)²/(2·B_MAX), B_MAX=9 m/s²; &lt;0 = collisione inevitabile.",
    "max_DRAC": "<b>DRAC massimo</b> [m/s²] — decelerazione richiesta per evitare l'urto.<br>"
                "DRAC = Δv²/(2·gap) (soglia critica 3.35 m/s²).",
    "TET": "<b>Time Exposed TTC</b> [s] — tempo totale con TTC sotto la soglia critica (TTC*=1.5 s).",
    "TIT": "<b>Time Integrated TTC</b> [s·s] — integrale di (TTC*−TTC) sotto soglia (severità × durata).",
    "impact_dv": "<b>Δv d'impatto</b> [m/s] — velocità relativa al contatto in caso di collisione (0 se nessuna).",
    "rms_accel": "<b>RMS accelerazione</b> [m/s²] — √⟨a²⟩ sull'episodio (proxy comfort ISO 2631).",
    "max_decel": "<b>Decelerazione massima</b> [m/s²] — la frenata più forte (= −min a).",
    "rms_jerk": "<b>RMS jerk</b> [m/s³] — √⟨(da/dt)²⟩; comfort (|jerk|>2 = scomodo).",
    "frac_decel_iso_viol": "<b>Frazione decel oltre ISO</b> — quota di tempo con a &lt; −3.5 m/s² (ISO 15622).",
    "frac_accel_iso_viol": "<b>Frazione accel oltre ISO</b> — quota di tempo con a &gt; +2.0 m/s² (ISO 15622).",
    "mean_firing_pct": "<b>Firing medio</b> [%] — quota media di neuroni hidden che sparano per passo.",
    "peak_firing_pct": "<b>Firing di picco</b> [%] — massimo per passo.",
    "dead_pct": "<b>Neuroni morti</b> [%] — hidden mai sparati in questo episodio (capacità inutilizzata).",
    "max_spikes_tick": "<b>Spike max per tick</b> — dimensiona la larghezza dell'albero di accumulo (AC) in hardware.",
    "rho": "<b>ρ(U·V)</b> — raggio spettrale della ricorrenza low-rank (pesi po2).<br>"
           "ρ&lt;1 = contrattivo (stato limitato, sicuro in fixed-point); ρ&gt;1 = espansivo (rischio overflow). "
           "Calcolato con power-iteration (no LAPACK).",
    "snn_pj": "<b>Energia SNN</b> [pJ] — Σ_passo SynOps · E_AC (E_AC = 0.9 pJ, costo di un accumulo).",
    "ann_pj": "<b>Energia ANN densa</b> [pJ] — n_passi · MAC_densi · E_MAC (E_MAC = 4.6 pJ; baseline = RNN densa "
              "con ricorrenza PIENA H·H).",
    "advantage": "<b>Vantaggio energetico</b> ×.<br>= energia_ANN / energia_SNN. Viene da <b>AC &lt; MAC</b> "
                 "(accumulo &lt; moltiplica-accumula), <b>NON dalla sparsità</b> (la rete spara ~15%). Conteggio per "
                 "passo reale (nessuna doppia normalizzazione per n_ticks). Varia tra caso tipico e worst-case.",
    "e_fc": "<b>Energia fc</b> [pJ] — ingresso sempre-on (IN·H) · E_AC.",
    "e_recV": "<b>Energia rec_V</b> [pJ] — ricorrenza spike-driven (Σ spike·rank) · E_AC.",
    "e_recU": "<b>Energia rec_U</b> [pJ] — ricorrenza (H·rank quando c'è almeno uno spike) · E_AC.",
    "e_out": "<b>Energia out</b> [pJ] — uscita spike-driven (Σ spike·OUT) · E_AC.",
}


def _fmt(val, suffix):
    if val is None:
        return "—"
    if isinstance(val, float):
        val = round(val, 1) if abs(val) >= 100 else round(val, 3)
    return f"{val}{suffix}"


class PostRunPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        self._header = QLabel("—"); self._header.setStyleSheet("font-weight: bold; font-size: 14px;")
        root.addWidget(self._header)
        grid = QGridLayout(); grid.setColumnStretch(3, 1); root.addLayout(grid)
        self._values = {}; self._help_labels = {}; self._suffix = {}
        row = 0
        for group, fields in _GROUPS:
            g = QLabel(group); g.setStyleSheet("font-weight: bold; color: #8a6fb0;")
            grid.addWidget(g, row, 0, 1, 4); row += 1
            for label, key, suffix in fields:
                grid.addWidget(QLabel(label), row, 0)
                v = QLabel("—"); self._values[key] = v; self._suffix[key] = suffix
                grid.addWidget(v, row, 1)
                q = QLabel("?"); q.setStyleSheet("color: #2a7fb8; font-weight: bold;")
                q.setToolTip(_METRIC_HELP.get(key, label))
                self._help_labels[key] = q
                grid.addWidget(q, row, 2)
                row += 1
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
                lbl.setText("∞"); continue
            if key == "rho" and val is not None:
                lbl.setText(f"{val}  ·  {'contrattivo' if val < 1.0 else 'espansivo'}")
                lbl.setStyleSheet("color: #2e8b57;" if val < 1.0 else "color: #d1495b;")
                continue
            lbl.setText(_fmt(val, self._suffix[key]))
        self._values["esito"].setStyleSheet(
            "color: #d1495b; font-weight: bold;" if s.get("collided") else "color: #2e8b57; font-weight: bold;")
        t = [r[0] for r in rows]; v = [r[2] for r in rows]; gap = [r[1] for r in rows]
        self._v_curve.setData(t, v); self._gap_curve.setData(t, gap)
