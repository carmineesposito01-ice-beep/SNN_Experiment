"""ScenarioPage -- the fourth mode: describe a scenario instead of picking one.

A timeline of blocks on the left, a COMPOSER on the right: you build one block while watching it,
then add it. The preview below is the REAL materialised v_leader, from the same function the sim
will run. Every decision is delegated to sim.scenario_spec: this file is Qt and nothing else.

Two things own state here, and only two:
* the WIDGETS own the composed block's params -- they are never mirrored into a dict beside them;
* the PAD owns the composed block's point, and the distance from the neutral IS its bias.
"""
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QListWidget,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)

from sim.scenario import scenario_library
from sim.scenario_spec import (A_MAX_RANGE, B_MAX_RANGE, _KINDS, Block, LeaderStyle, ScenarioSpec,
                               materialise)

# Labels for READING the plane, not modes: the point is continuous and may sit anywhere.
# Parked in the CORNERS with an outward anchor, not at the quadrant centres: the centre is exactly
# where you drop the point, and a 13 px dot sitting on the text hides it (seen in a render).
_QUADRANTS = [("placido", 1.05, 1.15, (0.0, 1.0)), ("guardingo", 1.05, 8.85, (0.0, 0.0)),
              ("spavaldo", 3.95, 1.15, (1.0, 1.0)), ("aggressivo", 3.95, 8.85, (1.0, 0.0))]


class StylePad(pg.PlotWidget):
    """The (a_max, b_max) plane. Acceleration and deceleration are INDEPENDENT, so a single slider
    would only walk the placido<->aggressivo diagonal and make the mixed quadrants unreachable.

    Two dots: the bright one is THIS block, the dim one is the driver's neutral. The distance
    between them is the bias.
    """
    sigStyleChanged = Signal(float, float)

    def __init__(self):
        super().__init__()
        self.setLabel("bottom", "accelerazione a_max", units="m/s²")
        self.setLabel("left", "decelerazione b_max", units="m/s²")
        self.setXRange(*A_MAX_RANGE)
        self.setYRange(*B_MAX_RANGE)
        self.setMouseEnabled(x=False, y=False)
        self.showGrid(x=True, y=True, alpha=0.2)
        for name, a, b, anchor in _QUADRANTS:
            t = pg.TextItem(name, color="#8a8a8a", anchor=anchor)
            t.setPos(a, b)
            self.addItem(t)
        self._neutral = (2.0, 4.0)
        self._neutral_dot = pg.ScatterPlotItem(size=9, brush=pg.mkBrush(120, 120, 120, 110),
                                               pen=pg.mkPen("#6a6a6a", width=1))
        self.addItem(self._neutral_dot)
        self._neutral_dot.setData([self._neutral[0]], [self._neutral[1]])
        self._dot = pg.ScatterPlotItem(size=13, brush=pg.mkBrush("#2a7fb8"),
                                       pen=pg.mkPen("#ffffff", width=2))
        self.addItem(self._dot)
        self._a, self._b = 2.0, 4.0
        self._dot.setData([self._a], [self._b])
        self.scene().sigMouseClicked.connect(self._on_click)

    def _on_click(self, ev):
        p = self.getPlotItem().vb.mapSceneToView(ev.scenePos())
        self.set_point(p.x(), p.y())

    def set_point(self, a, b, emit=True):
        """emit=False syncs the dot WITHOUT re-announcing: the page calls it when the point changed
        from elsewhere, so the dot never disagrees with the curve. Announcing there would loop.

        Clamped here, not at the callers: the point is now also placed by arithmetic (neutral+bias),
        and a bias that would leave the plane is pinned at the edge -- effective_style clamps
        identically, so the dot and the materialiser agree on what an off-plane bias means.
        """
        self._a = float(np.clip(a, *A_MAX_RANGE))
        self._b = float(np.clip(b, *B_MAX_RANGE))
        self._dot.setData([self._a], [self._b])
        if emit:
            self.sigStyleChanged.emit(self._a, self._b)

    def set_neutral(self, a, b):
        """The driver's character, drawn dimmer: the bright dot is where THIS block sits, and the
        distance between the two dots IS the bias."""
        self._neutral = (float(a), float(b))
        self._neutral_dot.setData([self._neutral[0]], [self._neutral[1]])


class ScenarioPage(QWidget):
    sigScenarioBuilt = Signal(object)          # emits a sim.scenario.Scenario

    def __init__(self, params_gt, N=600):
        super().__init__()
        self._params_gt = np.asarray(params_gt, dtype=np.float64)
        self._N = int(N)
        self._spec = None
        self._loading = False        # re-entrancy guard: setValue() fires valueChanged
        self._composer_row = None    # the timeline row being edited, or None for a new block
        root = QVBoxLayout(self)

        controls = QHBoxLayout()
        self._kind = QComboBox()
        self._kind.addItems(list(_KINDS))
        self._ticks = QSpinBox(); self._ticks.setRange(1, 600); self._ticks.setValue(150)
        self._value = QDoubleSpinBox(); self._value.setRange(0.0, 40.0); self._value.setValue(5.0)
        self._preset = QComboBox()
        self._preset.addItems(sorted(s.name for s in scenario_library(
            self._params_gt, N=self._N, rng=np.random.default_rng(0), include_tail=True)))
        self._period = QSpinBox(); self._period.setRange(4, 600); self._period.setValue(80)
        self._neu_a = QDoubleSpinBox(); self._neu_a.setRange(*A_MAX_RANGE)
        self._neu_b = QDoubleSpinBox(); self._neu_b.setRange(*B_MAX_RANGE)
        self._neu_a.setSingleStep(0.1); self._neu_b.setSingleStep(0.1)
        self._neu_a.setValue(2.0); self._neu_b.setValue(4.0)
        for w in (self._neu_a, self._neu_b):
            w.setToolTip("il neutro del guidatore: il pad muove il bias di QUESTO blocco")
        self._add = QPushButton("Aggiungi blocco"); self._add.clicked.connect(self._on_add)
        self._del = QPushButton("Rimuovi"); self._del.clicked.connect(self._on_del)
        self._use = QPushButton("Usa questo scenario"); self._use.clicked.connect(self._on_use)
        self._value_lbl, self._period_lbl = QLabel("valore"), QLabel("periodo")
        for w in (QLabel("blocco"), self._kind, QLabel("durata"), self._ticks,
                  self._preset, self._value_lbl, self._value, self._period_lbl, self._period,
                  QLabel("neutro a/b"), self._neu_a, self._neu_b,
                  self._add, self._del, self._use):
            controls.addWidget(w)
        controls.addStretch(1)
        root.addLayout(controls)

        mid = QHBoxLayout()
        self._list = QListWidget()
        mid.addWidget(self._list, stretch=1)
        self._pad = StylePad()
        self._pad.sigStyleChanged.connect(self.set_style)
        mid.addWidget(self._pad, stretch=1)
        self._composer_plot = pg.PlotWidget()
        self._composer_plot.setLabel("left", "blocco", units="m/s")
        self._composer_plot.setLabel("bottom", "tick del blocco")
        self._composer_plot.showGrid(x=False, y=True, alpha=0.2)
        self._composer_curve = self._composer_plot.plot(pen=pg.mkPen("#e8871e", width=2))
        mid.addWidget(self._composer_plot, stretch=1)
        root.addLayout(mid, stretch=1)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("left", "v_leader", units="m/s")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.showGrid(x=False, y=True, alpha=0.2)
        self._curve = self._plot.plot(pen=pg.mkPen("#d1495b", width=2))
        root.addWidget(self._plot, stretch=1)

        # every input is live: "build the piece while you see it" is false if only the pad redraws
        self._kind.currentTextChanged.connect(self._on_kind_changed)
        for sig in (self._ticks.valueChanged, self._value.valueChanged,
                    self._period.valueChanged, self._preset.currentTextChanged):
            sig.connect(self._refresh_composer)
        for sig in (self._neu_a.valueChanged, self._neu_b.valueChanged):
            sig.connect(self._on_neutral_changed)
        self._list.currentRowChanged.connect(self._on_row_selected)
        self._on_kind_changed(self._kind.currentText())

    # ---- state ----
    def set_spec(self, spec):
        self._spec = spec
        self._loading = True
        self._neu_a.setValue(spec.style.a_max)
        self._neu_b.setValue(spec.style.b_max)
        self._loading = False
        self._pad.set_neutral(spec.style.a_max, spec.style.b_max)
        self._refresh_list()
        self._refresh()
        kind = self._kind.currentText()
        self.compose_new(kind, int(self._ticks.value()), self._params_for(kind))

    def set_style(self, a_max, b_max):
        """The pad moved: that is THIS BLOCK's point, so only the composer redraws. The scenario's
        neutral is unchanged -- it has its own control."""
        self._pad.set_point(a_max, b_max, emit=False)   # the dot must never disagree with the state
        self._refresh_composer()

    def _refresh(self):
        if self._spec is None or not self._spec.blocks:
            self._curve.setData([])
            return
        self._curve.setData(materialise(self._spec, self._params_gt, self._N).v_leader)

    def _refresh_list(self):
        self._list.clear()
        for b in (self._spec.blocks if self._spec else ()):
            bias = "" if b.bias is None else f"  ·  bias {b.bias[0]:+.1f}/{b.bias[1]:+.1f}"
            self._list.addItem(f"{b.kind}  ·  {b.ticks} tick  ·  {b.params}{bias}")

    # ---- the composed block: the widgets are its only owner ----
    def _params_for(self, kind):
        """The params of the block being composed, DERIVED from the widgets.

        The widgets are the only owner. A shadow dict beside them was tried and it did what two
        owners always do: it crashed (new kind + old params) and it silently rewrote a reopened
        block's params on Apply.
        """
        v = float(self._value.value())
        return {"preset": {"name": self._preset.currentText()},
                "const": {"v": v},
                "ramp": {"to_v": v},
                "sine": {"amp": v, "period": int(self._period.value())}}[kind]

    def _on_kind_changed(self, kind):
        """Show only the inputs this kind actually has: an input that does nothing is a lie."""
        is_preset, is_sine = kind == "preset", kind == "sine"
        self._preset.setVisible(is_preset)
        for w in (self._value_lbl, self._value):
            w.setVisible(not is_preset)
        for w in (self._period_lbl, self._period):
            w.setVisible(is_sine)
        self._value_lbl.setText("ampiezza" if is_sine else "valore")
        self._refresh_composer()

    def _load_into_widgets(self, kind, ticks, params, bias):
        """Write a block INTO the widgets -- they are the owner, so this is how a block is opened.

        Guarded: each setValue/setCurrentText fires its signal, and refreshing four times while the
        widgets are half-written is waste, not a bug (every intermediate state is still VALID,
        because the params are derived, never stored).
        """
        self._loading = True
        try:
            self._kind.setCurrentText(kind)
            self._ticks.setValue(int(ticks))
            if kind == "preset":
                self._preset.setCurrentText(str(params["name"]))
            elif kind == "sine":
                self._value.setValue(float(params["amp"]))
                self._period.setValue(int(params["period"]))
            else:
                self._value.setValue(float(params["v" if kind == "const" else "to_v"]))
            na, nb = self._pad._neutral
            self._pad.set_point(na + (bias[0] if bias else 0.0),
                                nb + (bias[1] if bias else 0.0), emit=False)
        finally:
            self._loading = False
        self._on_kind_changed(kind)          # visibility + one refresh, once, at the end

    def _composer_kind(self):
        return self._kind.currentText()

    def _composer_bias(self):
        """The pad holds an ABSOLUTE point; the model stores the distance from the neutral. Showing
        the absolute is what one reasons about ("this block brakes at 7"); storing the difference is
        what keeps ONE driver ("...which is 3 more than his usual")."""
        na, nb = self._pad._neutral
        da, db = round(self._pad._a - na, 6), round(self._pad._b - nb, 6)
        return None if (da == 0.0 and db == 0.0) else (da, db)

    def _composer_block(self):
        kind = self._composer_kind()
        return Block(kind, int(self._ticks.value()), self._params_for(kind),
                     bias=self._composer_bias())

    def _start_speed(self, upto):
        """The speed the first `upto` blocks leave behind -- the composer's only coupling to the
        timeline, and what makes the small preview honest instead of decorative."""
        if self._spec is None:
            return 21.0
        if upto <= 0:
            return float(self._spec.v_init)
        prefix = ScenarioSpec(name="_", blocks=self._spec.blocks[:upto], style=self._spec.style,
                              s_init=self._spec.s_init, v_init=self._spec.v_init)
        used = sum(b.ticks for b in prefix.blocks)
        return float(materialise(prefix, self._params_gt,
                                 max(1, min(used, self._N))).v_leader[-1])

    def compose_new(self, kind, ticks, params, bias=None):
        """Open a NEW block in the composer. Nothing reaches the timeline until Add."""
        self._composer_row = None
        self._load_into_widgets(kind, ticks, params, bias)

    def _refresh_composer(self, *_):
        """Materialise a ONE-block spec starting from the speed the previous blocks leave behind."""
        if self._loading or self._spec is None:
            return
        blk = self._composer_block()
        upto = self._composer_row if self._composer_row is not None else len(self._spec.blocks)
        one = ScenarioSpec(name="_", blocks=(blk,), style=self._spec.style,
                           s_init=self._spec.s_init, v_init=self._start_speed(upto))
        self._composer_curve.setData(materialise(one, self._params_gt, blk.ticks).v_leader)

    def _on_row_selected(self, i):
        if self._spec is None or i < 0 or i >= len(self._spec.blocks):
            return
        b = self._spec.blocks[i]
        self._composer_row = i
        self._load_into_widgets(b.kind, b.ticks, b.params, b.bias)

    def _on_neutral_changed(self, *_):
        """The driver's character moved. The bias is a DIFFERENCE, so every block moves with him --
        that is exactly what having one driver means, and it is why the block's absolute point on
        the pad has to follow rather than stay put.
        """
        if self._loading or self._spec is None:
            return
        bias = self._composer_bias()                       # read BEFORE the neutral moves under it
        a, b = float(self._neu_a.value()), float(self._neu_b.value())
        self._spec = ScenarioSpec(name=self._spec.name, blocks=self._spec.blocks,
                                  style=LeaderStyle(a, b), s_init=self._spec.s_init,
                                  v_init=self._spec.v_init)
        self._pad.set_neutral(a, b)
        self._pad.set_point(a + (bias[0] if bias else 0.0),
                            b + (bias[1] if bias else 0.0), emit=False)
        self._refresh()
        self._refresh_composer()

    # ---- actions ----
    def _on_add(self):
        if self._spec is None:
            return
        blk = self._composer_block()
        blocks = list(self._spec.blocks)
        if self._composer_row is None:
            blocks.append(blk)
        else:
            blocks[self._composer_row] = blk          # Add acts as Apply on an open row
        self._spec = ScenarioSpec(name=self._spec.name, blocks=tuple(blocks),
                                  style=self._spec.style, s_init=self._spec.s_init,
                                  v_init=self._spec.v_init)
        self._composer_row = None
        self._refresh_list()
        self._refresh()
        self._refresh_composer()                      # the start speed moved

    def _on_del(self):
        i = self._list.currentRow()
        if self._spec is None or i < 0:
            return
        blocks = self._spec.blocks[:i] + self._spec.blocks[i + 1:]
        self._spec = ScenarioSpec(name=self._spec.name, blocks=blocks, style=self._spec.style,
                                  s_init=self._spec.s_init, v_init=self._spec.v_init)
        self._composer_row = None
        self._refresh_list()
        self._refresh()
        self._refresh_composer()

    def _on_use(self):
        if self._spec is None or not self._spec.blocks:
            return
        self.sigScenarioBuilt.emit(materialise(self._spec, self._params_gt, self._N))
