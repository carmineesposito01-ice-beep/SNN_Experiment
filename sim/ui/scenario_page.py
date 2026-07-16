"""ScenarioPage -- the fourth mode: describe a scenario instead of picking one.

A timeline of blocks on the left, a COMPOSER on the right: you build one block while watching it,
then add it. The preview below is the REAL materialised v_leader, from the same function the sim
will run. Every decision is delegated to sim.scenario_spec: this file is Qt and nothing else.

Two things own state here, and only two:
* the WIDGETS own the composed block's params -- they are never mirrored into a dict beside them;
* the PAD owns the composed block's point, and the distance from the neutral IS its bias.
"""
from dataclasses import replace

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)

from sim.scenario import scenario_library
from sim.scenario_spec import (A_MAX_RANGE, B_MAX_RANGE, V_RANGE, MAX_BLOCK_TICKS, _KINDS,
                               _custom_node_ticks, Block, LeaderStyle, ScenarioSpec, block_of_sample,
                               materialise, physics_gap)
from sim.ui.drag_handles import DragHandles
from sim.ui.duration_handles import DurationHandles

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

    def setEnabled(self, on):
        """Dims the DOT too, not just the widget's chrome.

        Qt greys a disabled widget's own text, but the dot is a scene item and stays vivid -- and the
        dot IS the claim. A bright point sitting in "aggressivo" on a block that ignores it is
        exactly the lie being removed, so graphite is not decoration here.
        """
        super().setEnabled(on)
        self._dot.setBrush(pg.mkBrush("#2a7fb8" if on else "#3d3d3d"))
        self._dot.setPen(pg.mkPen("#ffffff" if on else "#5a5a5a", width=2))


class ScenarioPage(QWidget):
    sigScenarioBuilt = Signal(object)          # emits a sim.scenario.Scenario

    def __init__(self, params_gt, N=600):
        super().__init__()
        self._params_gt = np.asarray(params_gt, dtype=np.float64)
        self._N = int(N)             # the preset-library length ONLY (for the dropdown); the SCENARIO's
                                     # length is _total_ticks() = the sum of its blocks, not this.
        self._spec = None
        self._loading = False        # re-entrancy guard: setValue() fires valueChanged
        self._composer_row = None    # the timeline row being edited, or None for a new block
        root = QVBoxLayout(self)

        controls = QHBoxLayout()
        self._kind = QComboBox()
        self._kind.addItems(list(_KINDS))
        self._ticks = QSpinBox(); self._ticks.setRange(1, MAX_BLOCK_TICKS); self._ticks.setValue(150)
        self._value = QDoubleSpinBox(); self._value.setRange(0.0, 40.0); self._value.setValue(5.0)
        self._preset = QComboBox()
        self._preset.addItems(sorted(s.name for s in scenario_library(
            self._params_gt, N=self._N, rng=np.random.default_rng(0), include_tail=True)))
        self._period = QSpinBox(); self._period.setRange(4, 600); self._period.setValue(80)
        self._nodes = QSpinBox(); self._nodes.setRange(1, 25); self._nodes.setValue(5)
        self._nodes_lbl = QLabel("nodi")
        self._neu_a = QDoubleSpinBox(); self._neu_a.setRange(*A_MAX_RANGE)
        self._neu_b = QDoubleSpinBox(); self._neu_b.setRange(*B_MAX_RANGE)
        self._neu_a.setSingleStep(0.1); self._neu_b.setSingleStep(0.1)
        self._neu_a.setValue(2.0); self._neu_b.setValue(4.0)
        for w in (self._neu_a, self._neu_b):
            w.setToolTip("il neutro del guidatore: il pad muove il bias di QUESTO blocco")
        self._add = QPushButton("Aggiungi blocco"); self._add.clicked.connect(self._on_add)
        self._del = QPushButton("Rimuovi"); self._del.clicked.connect(self._on_del)
        self._use = QPushButton("Usa questo scenario"); self._use.clicked.connect(self._on_use)
        self._name_edit = QLineEdit(); self._name_edit.setPlaceholderText("nome scenario")
        self._built_count = 0
        self._value_lbl, self._period_lbl = QLabel("valore"), QLabel("periodo")
        for w in (QLabel("blocco"), self._kind, QLabel("durata"), self._ticks,
                  self._preset, self._value_lbl, self._value, self._period_lbl, self._period,
                  self._nodes_lbl, self._nodes,
                  QLabel("neutro a/b"), self._neu_a, self._neu_b,
                  self._add, self._del, QLabel("nome"), self._name_edit, self._use):
            controls.addWidget(w)
        controls.addStretch(1)
        root.addLayout(controls)

        mid = QHBoxLayout()
        self._list = QListWidget()
        mid.addWidget(self._list, stretch=1)
        pad_col = QVBoxLayout()
        self._pad = StylePad()
        self._pad.sigStyleChanged.connect(self.set_style)
        pad_col.addWidget(self._pad, stretch=1)
        self._pad_note = QLabel("il preset è verbatim: il bias non lo tocca")
        self._pad_note.setStyleSheet("color: #8a8a8a; font-style: italic;")
        self._pad_note.hide()
        pad_col.addWidget(self._pad_note)
        mid.addLayout(pad_col, stretch=1)
        self._composer_plot = pg.PlotWidget()
        self._composer_plot.setLabel("left", "blocco", units="m/s")
        self._composer_plot.setLabel("bottom", "tick del blocco")
        self._composer_plot.showGrid(x=False, y=True, alpha=0.2)
        self._composer_curve = self._composer_plot.plot(pen=pg.mkPen("#e8871e", width=2))
        self._composer_red = self._composer_plot.plot(pen=pg.mkPen("#ff2d2d", width=4), connect="finite")
        self._composer_edge = DurationHandles(self._composer_plot, on_resize=self._on_composer_edge)
        self._handles = DragHandles(self._composer_plot,
                                    on_change=lambda: self._refresh_composer(refit=False))
        mid.addWidget(self._composer_plot, stretch=1)
        root.addLayout(mid, stretch=1)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("left", "v_leader", units="m/s")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.showGrid(x=False, y=True, alpha=0.2)
        # base curve ORANGE (matches the composer), so the red advisory reads as danger on a neutral
        # profile rather than as one crimson among another. A safety cue must not look like the profile.
        self._curve = self._plot.plot(pen=pg.mkPen("#e8871e", width=2))
        self._scenario_red = self._plot.plot(pen=pg.mkPen("#ff2d2d", width=4), connect="finite")
        self._boundaries = DurationHandles(self._plot, on_resize=self._on_boundary_resize)
        root.addWidget(self._plot, stretch=1)

        # every input is live: "build the piece while you see it" is false if only the pad redraws
        self._kind.currentTextChanged.connect(self._on_kind_changed)
        for sig in (self._ticks.valueChanged, self._value.valueChanged,
                    self._period.valueChanged, self._preset.currentTextChanged):
            sig.connect(self._refresh_composer)
        self._nodes.valueChanged.connect(self._on_node_count_changed)
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

    def _neutral(self):
        return self._spec.style if self._spec else LeaderStyle(2.0, 4.0)

    def _total_ticks(self):
        """The scenario's length IS the sum of its blocks' ticks -- one owner, no fixed N to overflow.
        So a block added past the old 600-tick cap is no longer silently dropped."""
        return sum(int(b.ticks) for b in self._spec.blocks) if self._spec else 0

    @staticmethod
    def _red_from_mask(v, seg_mask):
        """A curve that is NaN on the physical samples and equals v on both endpoints of each bad
        segment; connect='finite' then draws ONLY the impossible stretches (verified by render)."""
        red = np.full(len(v), np.nan)
        idx = np.flatnonzero(seg_mask)                     # segment k -> samples k and k+1
        if idx.size:
            red[idx] = v[idx]
            red[idx + 1] = v[idx + 1]
        return red

    def _refresh(self):
        if self._spec is None or not self._spec.blocks:
            self._curve.setData([])
            self._scenario_red.setData([])
            return
        n = self._total_ticks()
        v = materialise(self._spec, self._params_gt, n).v_leader
        self._curve.setData(v)
        mask, _ = physics_gap(v, self._neutral())          # over n-1 segments
        owner = block_of_sample(self._spec, n)
        custom_idx = [i for i, b in enumerate(self._spec.blocks) if b.kind == "custom"]
        # segment k is red iff sample k+1 is owned by a custom block (owner of the produced sample)
        seg_custom = np.isin(owner[1:], custom_idx) if custom_idx else np.zeros(n - 1, bool)
        self._scenario_red.setData(self._red_from_mask(v, mask & seg_custom))
        self._place_boundaries()

    def _place_boundaries(self):
        """One edge per block at its right edge (its cumulative boundary), capped by kind. Re-placed
        on every _refresh; a drag commits on release, so this never runs mid-drag."""
        if self._spec is None or not self._spec.blocks:
            self._boundaries.clear()
            return
        edges, cum = [], 0
        for i, b in enumerate(self._spec.blocks):
            cap = 600 if b.kind == "preset" else MAX_BLOCK_TICKS
            edges.append((i, cum, int(b.ticks), cap))
            cum += int(b.ticks)
        self._boundaries.set_edges(edges)

    def _on_boundary_resize(self, i, new_ticks):
        """Block i's boundary was released: resize block i (the total grows), sync the composer if
        that row is open, then refresh (which re-places all boundaries at the new cumulative sums)."""
        if self._spec is None or i >= len(self._spec.blocks):
            return
        blocks = list(self._spec.blocks)
        blocks[i] = replace(blocks[i], ticks=int(new_ticks))
        self._spec = ScenarioSpec(name=self._spec.name, blocks=tuple(blocks),
                                  style=self._spec.style, s_init=self._spec.s_init,
                                  v_init=self._spec.v_init)
        if self._composer_row == i:                        # the open working copy must not diverge
            self._loading = True
            self._ticks.setValue(int(new_ticks))
            self._loading = False
        self._refresh_list()
        self._refresh()

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
                "sine": {"amp": v, "period": int(self._period.value())},
                "custom": {"nodes": tuple(self._handles.speeds())}}[kind]

    def _on_kind_changed(self, kind):
        """Show only the inputs this kind actually has: an input that does nothing is a lie.

        The pad dies on preset AND custom -- both ignore the style (a preset is verbatim, a custom is
        hand-drawn) -- so a live pad there is a lie. custom shows the node-count and a row of handles;
        the handles are created BEFORE the trailing refresh so _params_for('custom') never reads an
        empty row (the lifecycle constraint, spec 6).
        """
        is_preset, is_sine, is_custom = kind == "preset", kind == "sine", kind == "custom"
        self._preset.setVisible(is_preset)
        for w in (self._value_lbl, self._value):
            w.setVisible(not (is_preset or is_custom))
        for w in (self._period_lbl, self._period):
            w.setVisible(is_sine)
        for w in (self._nodes_lbl, self._nodes):
            w.setVisible(is_custom)
        self._value_lbl.setText("ampiezza" if is_sine else "valore")
        self._pad.setEnabled(not (is_preset or is_custom))
        self._pad_note.setVisible(is_preset or is_custom)
        self._pad_note.setText("il preset è verbatim: il bias non lo tocca" if is_preset
                               else "il profilo disegnato non segue un rate: trascina i nodi")
        if is_custom:
            # setCurrentText fires this while _load_into_widgets is mid-write (loading=True); skip the
            # flat seed then -- the custom branch there places the real nodes. When the user picks
            # custom from the combo (not loading), seed a flat line to bend.
            if not self._loading:
                self._place_custom_handles(self._handles.speeds() or None)
        else:
            self._handles.clear()
        self._refresh_composer()

    def _place_custom_handles(self, speeds):
        """Position the handles on the current tick grid. speeds=None seeds a flat line at the start
        speed (a fresh custom you then bend); otherwise re-place the given speeds."""
        n = int(self._ticks.value())
        count = int(self._nodes.value())
        ticks = _custom_node_ticks(n, count)
        if speeds is None:
            speeds = [self._start_speed(self._composer_row
                                        if self._composer_row is not None
                                        else len(self._spec.blocks))] * count
        self._handles.set_speeds(ticks, speeds)

    def _on_node_count_changed(self, count):
        """Re-sample the current drawing at the new grid instead of discarding it."""
        if self._loading or self._composer_kind() != "custom":
            return
        n = int(self._ticks.value())
        old_ticks = _custom_node_ticks(n, len(self._handles))
        old_speeds = self._handles.speeds()
        v0 = self._start_speed(self._composer_row if self._composer_row is not None
                               else len(self._spec.blocks))
        new_ticks = _custom_node_ticks(n, int(count))
        new_speeds = np.interp(new_ticks, np.concatenate(([0.0], old_ticks)),
                               np.concatenate(([v0], old_speeds))).tolist()
        self._handles.set_speeds(new_ticks, new_speeds)
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
            elif kind == "custom":
                self._nodes.setValue(len(params["nodes"]))
                self._place_custom_handles(list(params["nodes"]))
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
        # A preset is verbatim, so it cannot obey a bias -- and the pad keeps its point across a kind
        # change, so composing a ramp, moving the pad and switching to preset would RECORD one.
        # materialise ignoring it is not enough: the timeline would print a bias the block has not.
        bias = None if kind in ("preset", "custom") else self._composer_bias()
        return Block(kind, int(self._ticks.value()), self._params_for(kind), bias=bias)

    def _start_speed(self, upto):
        """The speed the first `upto` blocks leave behind -- the composer's only coupling to the
        timeline, and what makes the small preview honest instead of decorative."""
        if self._spec is None:
            return 21.0
        if upto <= 0:
            return float(self._spec.v_init)
        prefix = ScenarioSpec(name="_", blocks=self._spec.blocks[:upto], style=self._spec.style,
                              s_init=self._spec.s_init, v_init=self._spec.v_init)
        used = sum(int(b.ticks) for b in prefix.blocks)     # the prefix's own length, uncapped
        return float(materialise(prefix, self._params_gt, max(1, used)).v_leader[-1])

    def compose_new(self, kind, ticks, params, bias=None):
        """Open a NEW block in the composer. Nothing reaches the timeline until Add."""
        self._composer_row = None
        self._load_into_widgets(kind, ticks, params, bias)

    def _refresh_composer(self, *_, refit=True):
        """Materialise a ONE-block spec starting from the speed the previous blocks leave behind.

        `refit` re-fits the view and re-places the composer edge; a NODE drag passes refit=False so the
        view does not jump (the item-3 fix) while a kind/params/duration change still re-frames it.
        """
        if self._loading or self._spec is None:
            return
        blk = self._composer_block()
        upto = self._composer_row if self._composer_row is not None else len(self._spec.blocks)
        one = ScenarioSpec(name="_", blocks=(blk,), style=self._spec.style,
                           s_init=self._spec.s_init, v_init=self._start_speed(upto))
        v = materialise(one, self._params_gt, blk.ticks).v_leader
        self._composer_curve.setData(v)
        if blk.kind == "custom":                           # one block: every bad segment is eligible
            mask, _ = physics_gap(v, self._neutral())
            self._composer_red.setData(self._red_from_mask(v, mask))
        else:
            self._composer_red.setData([])
        if refit:
            self._refit_composer()
            self._place_composer_edge()

    def _refit_composer(self):
        """Fix the composer's Y to the block's range (+pad) and X to the block's length. Fixing them
        disables pyqtgraph's autorange, so a subsequent node-drag redraw does NOT move the view."""
        v = self._composer_curve.getOriginalDataset()[1]
        if v is None or not len(v):
            return
        lo, hi = float(np.min(v)), float(np.max(v))
        pad = max(0.5, 0.05 * (hi - lo))
        self._composer_plot.setYRange(lo - pad, hi + pad)
        self._composer_plot.setXRange(0, max(1, int(self._ticks.value())))

    def _on_composer_edge(self, _id, new_ticks):
        """The composer edge was released: write the duration to its single owner, the spinbox."""
        self._ticks.setValue(int(new_ticks))

    def _place_composer_edge(self):
        """One edge at x = ticks, capped by kind (a preset stops at its 600-sample library length).
        A drag is committed on release, so re-placing here never runs mid-drag."""
        if self._spec is None:
            return
        cap = 600 if self._composer_kind() == "preset" else MAX_BLOCK_TICKS
        self._composer_edge.set_edges([("composed", 0, int(self._ticks.value()), cap)])

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
        self._built_count += 1
        name = self._name_edit.text().strip() or f"scenario_{self._built_count}"
        spec = replace(self._spec, name=name)
        self.sigScenarioBuilt.emit(materialise(spec, self._params_gt, self._total_ticks()))
