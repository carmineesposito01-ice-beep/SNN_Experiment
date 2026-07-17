"""The mix table: a list of ROW WIDGETS over the scenario families -> exact per-row quotas.

Extracted from the 7a Dataset page so it can be reused (B2 makes train and val two instances). Row widgets, not
a QTableWidget with delegates: with a handful of rows it is simpler and testable without simulating cell edits.

The table owns the rows, the family->source cascade, the eye preview, mix(), the quota column and the total-%
label; it emits `changed` on any edit. The page owns seed/count/jitter/formats/size and listens to `changed`.
`strength` is injected (the jitter slider lives on the page) so the eye can draw a representative sample."""
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from sim.dataset_gen import GENERATOR_PROFILES, preview_sample
from sim.dataset_mix import FAMILIES, MixEntry, quotas
from sim.ui.scenario_preview import ScenarioPreviewPanel

_EYE = "⊙"          # 7a's 👁 rendered as a reddish blob in Windows' default font; this reads as an aperture


@dataclass
class _Row:
    frame: QFrame
    family: QComboBox
    source: QComboBox
    eye: QLabel
    weight: QDoubleSpinBox
    quota: QLabel
    kill: QPushButton
    regime: QComboBox = None      # only in with_regime mode
    windows: QLabel = None        # only in with_regime mode: the window-share column


class MixTable(QWidget):
    PREVIEW_SEED = 0            # FIXED: the eye must show the same curve every time you hover the same source
    _TRAIN_STRIDE = 50         # the window-share column uses the train stride (seq_len//2, train.py:1467)
    changed = Signal()

    def __init__(self, params_gt, strength, with_regime=False):
        super().__init__()
        self._params_gt = params_gt
        self._strength = strength           # callable -> float in [0,1] (the page's jitter slider)
        self._with_regime = with_regime
        if with_regime:
            from sim.train_mix import FAMILIES_TRAIN, REGIMES
            self._families, self._regimes = list(FAMILIES_TRAIN), list(REGIMES)
        else:
            self._families, self._regimes = list(FAMILIES), None
        self._specs = {}
        self._preset_names = []
        self._rows = []
        self._count = 100                   # the page pushes the real count via set_count()

        self._rows_box = QVBoxLayout()
        self._add_btn = QPushButton("+ riga"); self._add_btn.clicked.connect(self.add_row)
        self._total_lbl = QLabel()

        self._popup = QFrame(self, Qt.ToolTip)
        self._popup_title = QLabel()
        self._popup_panel = ScenarioPreviewPanel()
        self._popup_panel.setFixedSize(280, 130)
        pl = QVBoxLayout(self._popup); pl.setContentsMargins(6, 6, 6, 6)
        pl.addWidget(self._popup_title); pl.addWidget(self._popup_panel)
        self._popup.hide()

        head = QHBoxLayout()
        cols = (("famiglia", "sorgente", "", "regime", "peso %", "→ traiettorie", "→ finestre", "")
                if with_regime else ("famiglia", "sorgente", "", "peso %", "→ traiettorie", ""))
        for t in cols:
            lbl = QLabel(t); lbl.setStyleSheet("color:#8b949e"); head.addWidget(lbl)
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        root.addLayout(head)
        root.addLayout(self._rows_box)
        bottom = QHBoxLayout(); bottom.addWidget(self._add_btn); bottom.addWidget(self._total_lbl)
        bottom.addStretch(1)
        root.addLayout(bottom)
        self.add_row()

    # ---- sources ----
    def set_sources(self, specs, preset_names):
        self._specs = dict(specs)
        self._preset_names = list(preset_names)
        for r in self._rows:
            self._sync_family_enabled(r)
            self._reload_sources(r)
        self._refresh()

    def set_count(self, count):
        self._count = int(count)
        self._refresh()

    def specs(self):
        return self._specs

    def _sync_family_enabled(self, row):
        item = row.family.model().item(self._families.index("built"))
        if self._specs:
            item.setEnabled(True); item.setToolTip("")
        else:
            item.setEnabled(False)
            item.setToolTip("nessuno scenario costruito: costruiscine uno nel modo Scenari")
            if row.family.currentText() == "built":
                row.family.setCurrentText("preset")

    def _sources_for(self, family):
        if family == "built":
            return sorted(self._specs)
        if family == "preset":
            return list(self._preset_names)
        return list(GENERATOR_PROFILES)

    def _reload_sources(self, row):
        row.source.blockSignals(True)
        row.source.clear()
        row.source.addItems(self._sources_for(row.family.currentText()))
        row.source.blockSignals(False)

    # ---- rows ----
    def add_row(self):
        frame = QFrame()
        lay = QHBoxLayout(frame); lay.setContentsMargins(0, 0, 0, 0)
        family = QComboBox(); family.addItems(self._families)
        source = QComboBox()
        eye = QLabel(_EYE); eye.setToolTip("anteprima di un campione di questa sorgente")
        eye.setAttribute(Qt.WA_Hover, True)
        eye.installEventFilter(self)
        regime = QComboBox() if self._with_regime else None
        if regime is not None:
            regime.addItems(self._regimes)
        weight = QDoubleSpinBox(); weight.setRange(0.0, 100.0); weight.setDecimals(1)
        quota = QLabel("0")
        windows = QLabel("0") if self._with_regime else None
        if windows is not None:
            windows.setStyleSheet("color:#6e7681")
        kill = QPushButton("✕"); kill.setFixedWidth(28)
        widgets = ([family, source, eye, regime, weight, quota, windows, kill] if self._with_regime
                   else [family, source, eye, weight, quota, kill])
        for w in widgets:
            lay.addWidget(w)
        row = _Row(frame, family, source, eye, weight, quota, kill, regime, windows)
        self._rows.append(row)
        self._rows_box.addWidget(frame)
        family.currentTextChanged.connect(lambda _t, r=row: (self._reload_sources(r), self._refresh()))
        weight.valueChanged.connect(self._refresh)
        if regime is not None:
            regime.currentTextChanged.connect(self._refresh)
        kill.clicked.connect(lambda _c=False, r=row: self.remove_row(r))
        self._sync_family_enabled(row)
        self._reload_sources(row)
        self._refresh()
        return row

    def remove_row(self, row):
        if len(self._rows) <= 1:
            return
        self._rows.remove(row)
        row.frame.setParent(None)
        self._refresh()

    # ---- the eye ----
    def show_preview(self, row):
        fam, src = row.family.currentText(), row.source.currentText()
        if not src:
            return
        eye_fam = "generator" if fam == "cut_in" else fam
        v = preview_sample(eye_fam, src, self.PREVIEW_SEED, self._strength(), self._specs, self._params_gt)
        self._popup_panel.set_scenario(v)
        suffix = " — leader A" if fam == "cut_in" else ""
        self._popup_title.setText(f"{fam} · {src} — campione (seed {self.PREVIEW_SEED}){suffix}")
        self._popup.adjustSize()
        self._popup.move(row.eye.mapToGlobal(row.eye.rect().bottomLeft()))
        self._popup.show()

    def hide_preview(self):
        self._popup.hide()

    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        for r in self._rows:
            if obj is r.eye:
                if ev.type() == QEvent.Enter:
                    self.show_preview(r)
                elif ev.type() == QEvent.Leave:
                    self.hide_preview()
                break
        return super().eventFilter(obj, ev)

    # ---- the mix ----
    def mix(self):
        if self._with_regime:
            from sim.train_mix import TrainMixEntry
            return [TrainMixEntry(r.family.currentText(), r.source.currentText(),
                                  r.regime.currentText(), float(r.weight.value())) for r in self._rows]
        return [MixEntry(r.family.currentText(), r.source.currentText(), float(r.weight.value()))
                for r in self._rows]

    def total(self):
        return sum(r.weight.value() for r in self._rows)

    def is_valid(self):
        return abs(self.total() - 100.0) <= 0.01 and all(r.source.count() for r in self._rows)

    # ---- refresh ----
    def _refresh(self):
        ok = self.is_valid()
        self._total_lbl.setText(f"totale {self.total():.0f}% {'✓' if ok else '✗'}")
        self._total_lbl.setStyleSheet(f"color:{'#2e8b57' if ok else '#d1495b'}")
        if ok:
            qs = quotas(self.mix(), self._count, self._families) if self._with_regime else quotas(self.mix(), self._count)
            for r, q in zip(self._rows, qs):
                r.quota.setText(str(q))
                if r.windows is not None:
                    from sim.train_gen import training_windows
                    r.windows.setText(str(q * training_windows(r.family.currentText(), r.source.currentText(),
                                                               self._specs, stride=self._TRAIN_STRIDE)))
        else:
            for r in self._rows:
                r.quota.setText("—")
                if r.windows is not None:
                    r.windows.setText("—")
        self.changed.emit()
