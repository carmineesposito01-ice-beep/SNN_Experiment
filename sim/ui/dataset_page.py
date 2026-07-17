"""The Dataset mode (the 5th): a percentage mix over three scenario families -> N randomised trajectories.

The table is a list of ROW WIDGETS, not a QTableWidget with delegates: with a handful of rows it is simpler
and, more importantly, testable without simulating cell editing.

The page owns WIDGETS and exposes getters (mix/count/seed/...); the APP owns the run -- the same split the
Meso page uses (app.py:174 sets _on_run_platoon). That is why Generate here only calls self._on_generate: the
batch, the busy-guard and the progress pump live in the app, where _busy_controls() can disable every
re-entry path."""
from dataclasses import dataclass

from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)

from sim.dataset_gen import GENERATOR_PROFILES
from sim.dataset_mix import FAMILIES, MixEntry, quotas

_K_CHOICES = [("10 Hz (nativa)", 1), ("5 Hz", 2), ("2 Hz", 5), ("1 Hz", 10)]


@dataclass
class _Row:
    frame: QFrame
    family: QComboBox
    source: QComboBox
    eye: QLabel
    weight: QDoubleSpinBox
    quota: QLabel
    kill: QPushButton


class DatasetPage(QWidget):
    def __init__(self, params_gt):
        super().__init__()
        self._params_gt = params_gt
        self._specs = {}
        self._preset_names = []
        self._rows = []
        self._on_generate = None            # the APP sets this (the Meso idiom, app.py:174)

        self._rows_box = QVBoxLayout()
        self._add_btn = QPushButton("+ riga"); self._add_btn.clicked.connect(self.add_row)
        self._total_lbl = QLabel()
        self._count = QSpinBox(); self._count.setRange(1, 100000); self._count.setValue(100)
        self._count.valueChanged.connect(self._refresh)
        self._seed = QSpinBox(); self._seed.setRange(0, 2**31 - 1); self._seed.setValue(42)
        self._gen_btn = QPushButton("Genera")
        self._gen_btn.clicked.connect(lambda: self._on_generate() if self._on_generate else None)
        self._progress = QProgressBar(); self._progress.setRange(0, 100); self._progress.setValue(0)

        head = QHBoxLayout()
        for t in ("famiglia", "sorgente", "", "peso %", "→ traiettorie", ""):
            lbl = QLabel(t); lbl.setStyleSheet("color:#8b949e"); head.addWidget(lbl)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("MIX"))
        root.addLayout(head)
        root.addLayout(self._rows_box)
        bottom = QHBoxLayout(); bottom.addWidget(self._add_btn); bottom.addWidget(self._total_lbl)
        bottom.addStretch(1)
        root.addLayout(bottom)
        run = QHBoxLayout(); run.addWidget(self._gen_btn); run.addWidget(self._progress)
        root.addLayout(run)
        root.addStretch(1)
        self.add_row()

    # ---- sources ----
    def set_sources(self, specs, preset_names):
        """Called by the app when entering the mode: the built scenarios may have changed since last time."""
        self._specs = dict(specs)
        self._preset_names = list(preset_names)
        for r in self._rows:
            self._sync_family_enabled(r)
            self._reload_sources(r)
        self._refresh()

    def _sync_family_enabled(self, row):
        item = row.family.model().item(FAMILIES.index("built"))
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
        family = QComboBox(); family.addItems(FAMILIES)
        source = QComboBox()
        eye = QLabel("👁"); eye.setToolTip("anteprima di un campione di questa sorgente")
        weight = QDoubleSpinBox(); weight.setRange(0.0, 100.0); weight.setDecimals(1)
        quota = QLabel("0")
        kill = QPushButton("✕"); kill.setFixedWidth(28)
        for w in (family, source, eye, weight, quota, kill):
            lay.addWidget(w)
        row = _Row(frame, family, source, eye, weight, quota, kill)
        self._rows.append(row)
        self._rows_box.addWidget(frame)
        family.currentTextChanged.connect(lambda _t, r=row: (self._reload_sources(r), self._refresh()))
        weight.valueChanged.connect(self._refresh)
        kill.clicked.connect(lambda _c=False, r=row: self.remove_row(r))
        self._sync_family_enabled(row)
        self._reload_sources(row)
        self._refresh()
        return row

    def remove_row(self, row):
        if len(self._rows) <= 1:
            return                                   # always keep one row: an empty mix is not a state
        self._rows.remove(row)
        row.frame.setParent(None)
        self._refresh()

    # ---- getters (the app reads these; the Meso idiom) ----
    def mix(self):
        return [MixEntry(r.family.currentText(), r.source.currentText(), float(r.weight.value()))
                for r in self._rows]

    def count(self):
        return int(self._count.value())

    def seed(self):
        return int(self._seed.value())

    # ---- refresh ----
    def _refresh(self):
        total = sum(r.weight.value() for r in self._rows)
        # This guard has two jobs: it gates Generate, AND it keeps quotas() -- which validates the mix and
        # raises -- from being called on an invalid mix during a live refresh.
        ok = abs(total - 100.0) <= 0.01 and all(r.source.count() for r in self._rows)
        self._total_lbl.setText(f"totale {total:.0f}% {'✓' if ok else '✗'}")
        self._total_lbl.setStyleSheet(f"color:{'#2e8b57' if ok else '#d1495b'}")
        self._gen_btn.setEnabled(ok)
        if ok:
            for r, q in zip(self._rows, quotas(self.mix(), self.count())):
                r.quota.setText(str(q))
        else:
            for r in self._rows:
                r.quota.setText("—")
