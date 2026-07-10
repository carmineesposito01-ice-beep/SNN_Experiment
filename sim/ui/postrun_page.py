"""PostRunPage v3 -- dark pyqtgraph 'dashboard' of the one episode just run: a verdict badge + a grid
of cards (per metric group), each with a bar/marker plot AND the values with '?' definition/formula
tooltips. Consistent with the rest of the simulator. Same set_summary signature; EpisodeSummary
unchanged (energy is display-rounded only; the summary is the single source)."""
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

_GREEN = "#2e8b57"; _RED = "#d1495b"; _BLUE = "#2a7fb8"; _AMBER = "#e8871e"; _PURPLE = "#8a6fb0"
_TTC_STAR = 1.5; _DRAC_STAR = 3.35        # safety limits (s, m/s²) — same as the live Safety dock
_BRAKE_SAFE_M = 20.0                       # display scale: a 20 m avoidability margin reads as fully safe (0 m = the limit)
_ISO_DECEL = 3.5; _ISO_JERK = 2.0         # comfort limits (m/s², m/s³) cited in the tooltips

_METRIC_HELP = {
    "id_accuracy": "<b>Accuratezza identificazione</b><br>Quanto la SNN indovina i 5 parametri ACC-IIDM veri.<br>"
                   "formula: 100·(1 − media_i(RMSE_i/|GT_i|)), RMSE_i = √⟨(pred_i−GT_i)²⟩",
    "param_rmse_v0": "<b>Errore v0</b> (velocità desiderata) — RMSE vs il valore vero. √⟨(v0_pred−v0_GT)²⟩",
    "param_rmse_T": "<b>Errore T</b> (time-gap) — RMSE vs il valore vero. √⟨(T_pred−T_GT)²⟩",
    "param_rmse_s0": "<b>Errore s0</b> (gap minimo) — RMSE vs il valore vero. √⟨(s0_pred−s0_GT)²⟩",
    "param_rmse_a": "<b>Errore a</b> (accel max) — RMSE vs il valore vero. √⟨(a_pred−a_GT)²⟩",
    "param_rmse_b": "<b>Errore b</b> (decel confortevole) — RMSE vs il valore vero. √⟨(b_pred−b_GT)²⟩",
    "esito": "<b>Esito</b> — collisione se il gap tocca 0 in questo episodio (altrimenti 'ok').",
    "min_gap": "<b>Gap minimo</b> [m] — distanza minima ego↔leader nell'episodio.",
    "min_ttc": "<b>Time-To-Collision minimo</b> [s].<br>TTC = gap/Δv (se Δv>0, avvicinamento); min sull'episodio.",
    "brake_margin_min": "<b>Margine di frenata</b> [m, con segno] — distanza dal confine di evitabilità fisica.<br>"
                        "brake_margin = s − max(0,Δv)²/(2·B_MAX), B_MAX=9 m/s²; &lt;0 = collisione inevitabile.",
    "max_DRAC": "<b>DRAC massimo</b> [m/s²] — decel richiesta per evitare l'urto. DRAC = Δv²/(2·gap) (soglia 3.35).",
    "TET": "<b>Time Exposed TTC</b> [s] — tempo totale con TTC sotto la soglia critica (TTC*=1.5 s).",
    "TIT": "<b>Time Integrated TTC</b> [s·s] — integrale di (TTC*−TTC) sotto soglia (severità × durata).",
    "impact_dv": "<b>Δv d'impatto</b> [m/s] — velocità relativa al contatto in caso di collisione (0 se nessuna).",
    "rms_accel": "<b>RMS accelerazione</b> [m/s²] — √⟨a²⟩ (proxy comfort ISO 2631).",
    "max_decel": "<b>Decelerazione massima</b> [m/s²] — la frenata più forte (= −min a).",
    "rms_jerk": "<b>RMS jerk</b> [m/s³] — √⟨(da/dt)²⟩; comfort (|jerk|>2 = scomodo).",
    "frac_decel_iso_viol": "<b>Frazione decel oltre ISO</b> — quota di tempo con a &lt; −3.5 m/s² (ISO 15622).",
    "frac_accel_iso_viol": "<b>Frazione accel oltre ISO</b> — quota di tempo con a &gt; +2.0 m/s² (ISO 15622).",
    "mean_firing_pct": "<b>Firing medio</b> [%] — quota media di neuroni hidden che sparano per passo.",
    "peak_firing_pct": "<b>Firing di picco</b> [%] — massimo per passo.",
    "dead_pct": "<b>Neuroni morti</b> [%] — hidden mai sparati in questo episodio (capacità inutilizzata).",
    "max_spikes_tick": "<b>Spike max per tick</b> — dimensiona la larghezza dell'albero di accumulo (AC) hardware.",
    "rho": "<b>ρ(U·V)</b> — raggio spettrale della ricorrenza low-rank (pesi po2).<br>"
           "ρ&lt;1 = contrattivo (stato limitato, sicuro in fixed-point); ρ&gt;1 = espansivo (rischio overflow). "
           "Power-iteration (no LAPACK).",
    "snn_pj": "<b>Energia SNN</b> [pJ] — Σ_passo SynOps · E_AC (E_AC=0.9 pJ, un accumulo).",
    "ann_pj": "<b>Energia ANN densa</b> [pJ] — n_passi · MAC_densi · E_MAC (E_MAC=4.6 pJ; baseline RNN densa H·H).",
    "advantage": "<b>Vantaggio energetico</b> ×.<br>= energia_ANN/energia_SNN. Da <b>AC&lt;MAC</b> (accumulo &lt; molt.-accum.), "
                 "<b>NON dalla sparsità</b> (la rete spara ~15%). Conteggio per passo (no doppia norm. n_ticks). Varia tipico↔worst.",
    "e_fc": "<b>Energia fc</b> [pJ] — ingresso sempre-on (IN·H) · E_AC.",
    "e_recV": "<b>Energia rec_V</b> [pJ] — ricorrenza spike-driven (Σ spike·rank) · E_AC.",
    "e_recU": "<b>Energia rec_U</b> [pJ] — ricorrenza (H·rank se c'è spike) · E_AC.",
    "e_out": "<b>Energia out</b> [pJ] — uscita spike-driven (Σ spike·OUT) · E_AC.",
}


def _fmt(val, suffix):
    if val is None:
        return "—"
    if isinstance(val, float):
        val = round(val, 1) if abs(val) >= 100 else round(val, 3)
    return f"{val}{suffix}"


def _grad(x, maxv):
    """Green (low) -> red (high) brush, x normalised by maxv."""
    f = max(0.0, min(1.0, x / maxv)) if maxv > 0 else 0.0
    return pg.mkBrush(int(46 + f * 163), int(139 - f * 66), int(87 + f * 4))


class PostRunPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("QWidget{background:#1c1c1c;color:#e6e6e6;} "
                           "QFrame#card{background:#262626;border:1px solid #383838;border-radius:5px;} "
                           "QLabel{border:none;}")
        root = QVBoxLayout(self)
        head = QHBoxLayout()
        self._verdict = QLabel("—")
        self._subtitle = QLabel("—"); self._subtitle.setStyleSheet("color:#aaa;font-size:13px;")
        head.addWidget(self._verdict); head.addSpacing(12); head.addWidget(self._subtitle); head.addStretch(1)
        root.addLayout(head)
        grid = QGridLayout(); grid.setSpacing(8); root.addLayout(grid, stretch=1)
        self._values = {}; self._help_labels = {}; self._suffix = {}; self._cards = []; self._bars = {}

        c, plot = self._card("Identificazione", [("accuratezza", "id_accuracy", " %"),
            ("err v0", "param_rmse_v0", ""), ("err T", "param_rmse_T", ""), ("err s0", "param_rmse_s0", ""),
            ("err a", "param_rmse_a", ""), ("err b", "param_rmse_b", "")])
        self._bars["id"] = self._hbars(plot, ["v0", "T", "s0", "a", "b"])
        grid.addWidget(c, 0, 0); self._cards.append(c)

        c, plot = self._card("Sicurezza", [("esito", "esito", ""), ("min gap", "min_gap", " m"),
            ("min TTC", "min_ttc", " s"), ("brake margin", "brake_margin_min", " m"),
            ("max DRAC", "max_DRAC", " m/s²"), ("TET", "TET", " s"), ("TIT", "TIT", " s·s"),
            ("impact Δv", "impact_dv", " m/s")])
        self._bars["safe"] = self._hbars(plot, ["min TTC", "DRAC", "brake m."])
        plot.addLine(x=1.0, pen=pg.mkPen("#888", style=Qt.DashLine))   # danger index: 1.0 = the safety limit
        plot.setXRange(0.0, 2.0, padding=0)                            # fixed scale so the three bars are comparable
        self._safe_plot = plot
        grid.addWidget(c, 0, 1); self._cards.append(c)

        c, plot = self._card("Comfort", [("RMS accel", "rms_accel", " m/s²"), ("max decel", "max_decel", " m/s²"),
            ("RMS jerk", "rms_jerk", " m/s³"), ("frac decel ISO", "frac_decel_iso_viol", ""),
            ("frac accel ISO", "frac_accel_iso_viol", "")])
        self._bars["comf"] = self._hbars(plot, ["accel", "decel", "jerk"])
        grid.addWidget(c, 0, 2); self._cards.append(c)

        c, plot = self._card("Salute rete / FPGA", [("firing medio", "mean_firing_pct", " %"),
            ("firing picco", "peak_firing_pct", " %"), ("neuroni morti", "dead_pct", " %"),
            ("spike max/tick", "max_spikes_tick", ""), ("ρ(U·V)", "rho", "")])
        self._bars["rho"] = self._hbars(plot, ["ρ"])
        plot.addLine(x=1.0, pen=pg.mkPen("#888", style=Qt.DashLine))   # ρ=1 boundary (contractive|expansive)
        self._rho_plot = plot
        grid.addWidget(c, 1, 0); self._cards.append(c)

        c, plot = self._card("Efficienza", [("energia SNN", "snn_pj", " pJ"), ("energia ANN", "ann_pj", " pJ"),
            ("vantaggio", "advantage", "×"), ("fc", "e_fc", " pJ"), ("rec_V", "e_recV", " pJ"),
            ("rec_U", "e_recU", " pJ"), ("out", "e_out", " pJ")])
        self._bars["energy"] = self._hbars(plot, ["SNN", "ANN"])
        grid.addWidget(c, 1, 1); self._cards.append(c)

        card = QFrame(); card.setObjectName("card"); cv = QVBoxLayout(card)
        cv.addWidget(self._title("Andamento"))
        self._v_plot = pg.PlotWidget(title="v(t)"); self._v_plot.setBackground(None)
        self._gap_plot = pg.PlotWidget(title="gap(t)"); self._gap_plot.setBackground(None)
        self._v_plot.setXLink(self._gap_plot)
        self._v_curve = self._v_plot.plot(pen=pg.mkPen(_BLUE, width=2))
        self._gap_curve = self._gap_plot.plot(pen=pg.mkPen(_GREEN, width=2))
        cv.addWidget(self._v_plot); cv.addWidget(self._gap_plot)
        grid.addWidget(card, 1, 2); self._cards.append(card)

        for col in range(3):
            grid.setColumnStretch(col, 1)
        for r in range(2):
            grid.setRowStretch(r, 1)

    def _title(self, text):
        t = QLabel(text); t.setStyleSheet(f"font-weight:bold;color:{_PURPLE};")
        return t

    def _card(self, title, fields):
        card = QFrame(); card.setObjectName("card")
        v = QVBoxLayout(card); v.addWidget(self._title(title))
        plot = pg.PlotWidget(); plot.setBackground(None)
        v.addWidget(plot, stretch=1)   # plot absorbs the card's spare height; the value rows stay compact below
        rows = QGridLayout(); rows.setVerticalSpacing(1); r = 0
        for label, key, suffix in fields:
            lb = QLabel(label); lb.setStyleSheet("color:#bbb;")
            rows.addWidget(lb, r, 0)
            val = QLabel("—"); self._values[key] = val; self._suffix[key] = suffix
            rows.addWidget(val, r, 1)
            q = QLabel("?"); q.setStyleSheet(f"color:{_BLUE};font-weight:bold;")
            q.setToolTip(_METRIC_HELP.get(key, label)); self._help_labels[key] = q
            rows.addWidget(q, r, 2)
            r += 1
        rows.setColumnStretch(3, 1)
        v.addLayout(rows)
        return card, plot

    def _hbars(self, plot, ticks):
        plot.getAxis("left").setTicks([list(enumerate(ticks))])
        plot.setMouseEnabled(False, False); plot.hideButtons(); plot.showGrid(x=True, y=False, alpha=0.15)
        bar = pg.BarGraphItem(x0=0, y=list(range(len(ticks))), height=0.6, width=[0] * len(ticks), brush=_BLUE)
        plot.addItem(bar)
        return bar

    def set_summary(self, s, rows, champion, scenario):
        coll = bool(s.get("collided"))
        self._verdict.setText("  COLLISIONE  " if coll else "  ok  ")
        self._verdict.setStyleSheet(f"font-size:22px;font-weight:bold;padding:2px 12px;border-radius:4px;"
                                    f"background:{_RED if coll else _GREEN};color:#111;")
        self._subtitle.setText(f"{champion} · {scenario} · {s.get('duration_s', '—')} s "
                               f"({s.get('n_ticks', '—')} tick)")
        disp = dict(s); disp["esito"] = "COLLISIONE" if coll else "ok"
        for key, lbl in self._values.items():
            val = disp.get(key)
            if key == "min_ttc" and val == float("inf"):
                lbl.setText("∞"); continue
            if key == "rho" and val is not None:
                lbl.setText(f"{val} · {'contrattivo' if val < 1 else 'espansivo'}")
                lbl.setStyleSheet(f"color:{_GREEN if val < 1 else _RED};font-weight:bold;"); continue
            lbl.setText(_fmt(val, self._suffix[key]))
            if key == "esito":
                lbl.setStyleSheet(f"color:{_RED if coll else _GREEN};font-weight:bold;")

        def g(k, d=0.0):
            v = s.get(k)
            return float(v) if isinstance(v, (int, float)) and v != float("inf") else d

        idv = [g("param_rmse_v0"), g("param_rmse_T"), g("param_rmse_s0"), g("param_rmse_a"), g("param_rmse_b")]
        self._bars["id"].setOpts(width=idv, brushes=[_grad(x, max(idv + [1e-9])) for x in idv])
        # Sicurezza as a DANGER INDEX per metric (1.0 = the limit; green<1 safe / red>=1 violation) on a
        # fixed [0,2] scale -> the three different-unit metrics become visually comparable, and the safest
        # case (min_ttc = ∞) correctly reads as a short green bar instead of a red zero-length one.
        mttc = s.get("min_ttc")
        d_ttc = 0.0 if mttc == float("inf") else (_TTC_STAR / g("min_ttc") if g("min_ttc") > 0 else 2.0)
        d_drac = g("max_DRAC") / _DRAC_STAR
        d_brake = 1.0 - g("brake_margin_min") / _BRAKE_SAFE_M      # margin>=scale -> 0 safe; <=0 -> >=1 unavoidable
        danger = [min(d_ttc, 2.0), min(d_drac, 2.0), min(max(d_brake, 0.0), 2.0)]
        self._bars["safe"].setOpts(width=danger,
                                   brushes=[pg.mkBrush(_RED if d >= 1.0 else _GREEN) for d in danger])
        self._bars["comf"].setOpts(                               # ISO gates from the tooltips (accel has no hard gate)
            width=[g("rms_accel"), g("max_decel"), g("rms_jerk")],
            brushes=[pg.mkBrush(_AMBER),
                     pg.mkBrush(_GREEN if g("max_decel") < _ISO_DECEL else _RED),
                     pg.mkBrush(_GREEN if g("rms_jerk") < _ISO_JERK else _RED)])
        rho = g("rho")
        self._bars["rho"].setOpts(width=[rho], brushes=[pg.mkBrush(_GREEN if rho < 1 else _RED)])
        self._rho_plot.setXRange(0.0, max(2.0, rho * 1.15), padding=0)   # keep the ρ=1 boundary clearly in view
        self._bars["energy"].setOpts(width=[g("snn_pj"), g("ann_pj")],
                                     brushes=[pg.mkBrush(_GREEN), pg.mkBrush(_RED)])
        t = [r[0] for r in rows]; v = [r[2] for r in rows]; gap = [r[1] for r in rows]
        self._v_curve.setData(t, v); self._gap_curve.setData(t, gap)
