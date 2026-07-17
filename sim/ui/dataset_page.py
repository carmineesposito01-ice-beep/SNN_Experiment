"""The Dataset mode (the 5th): a percentage mix over three scenario families -> N randomised trajectories.

The table is a list of ROW WIDGETS, not a QTableWidget with delegates: with a handful of rows it is simpler
and, more importantly, testable without simulating cell editing.

The page owns WIDGETS and exposes getters (mix/count/seed/...); the APP owns the run -- the same split the
Meso page uses (app.py:174 sets _on_run_platoon). That is why Generate here only calls self._on_generate: the
batch, the busy-guard and the progress pump live in the app, where _busy_controls() can disable every
re-entry path."""
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QProgressBar, QPushButton, QSlider, QSpinBox,
                               QVBoxLayout, QWidget)

from sim.dataset_gen import GENERATOR_PROFILES, preview_sample
from sim.dataset_mix import FAMILIES, MixEntry, quotas
from sim.export_formats import FORMATS, estimate_bytes
from sim.scenario_spec import _PRESET_N
from sim.ui.scenario_preview import ScenarioPreviewPanel

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
    PREVIEW_SEED = 0            # FIXED: the eye must show the same curve every time you hover the same source

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

        self._jitter = QSlider(Qt.Horizontal); self._jitter.setRange(0, 100); self._jitter.setValue(25)
        self._jitter.setFixedWidth(120)
        self._jitter_lbl = QLabel("25%")
        self._jitter.valueChanged.connect(lambda v: (self._jitter_lbl.setText(f"{v}%"), self._refresh()))
        self._jitter_note = QLabel("⚠ non governa la famiglia «generator» (ha il jitter suo)")
        self._jitter_note.setStyleSheet("color:#6e7681")

        self._freq = QComboBox(); self._freq.addItems([t for t, _k in _K_CHOICES])
        self._freq.currentIndexChanged.connect(self._refresh)
        self._freq_help = QLabel("(?)"); self._freq_help.setStyleSheet("color:#6e7681")
        self._freq_help.setToolTip(
            "10 Hz è la frequenza CANONICA V2V (DT=0.1 s): la fisica gira sempre lì.\n"
            "Le altre scelte DECIMANO l'export (un campione ogni k) e ricalcolano a_leader a dt_out:\n"
            "l'accelerazione a 0.2 s NON è quella a 0.1 s.\n"
            "Nessun upsampling: inventerebbe dati che la fisica non ha prodotto.")

        self._fmt_boxes = {}
        for name, spec in FORMATS.items():
            b = QCheckBox(name)
            b.setEnabled(spec.available)
            if not spec.available:
                b.setToolTip(spec.reason)
            b.setChecked(name in ("csv", "mat"))
            b.stateChanged.connect(self._refresh)
            self._fmt_boxes[name] = b

        self._size_lbl = QLabel()
        self._out_dir = QLineEdit()
        self._browse = QPushButton("Sfoglia…"); self._browse.clicked.connect(self._pick_dir)

        self._popup = QFrame(self, Qt.ToolTip)          # a frameless floating panel
        self._popup_title = QLabel()
        self._popup_panel = ScenarioPreviewPanel()
        self._popup_panel.setFixedSize(280, 130)
        pl = QVBoxLayout(self._popup); pl.setContentsMargins(6, 6, 6, 6)
        pl.addWidget(self._popup_title); pl.addWidget(self._popup_panel)
        self._popup.hide()

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
        ctl = QHBoxLayout()
        for w in (QLabel("seed"), self._seed, QLabel("traiettorie"), self._count,
                  QLabel("jitter"), self._jitter, self._jitter_lbl, self._jitter_note):
            ctl.addWidget(w)
        ctl.addStretch(1)
        fmt_row = QHBoxLayout(); fmt_row.addWidget(QLabel("formato"))
        for b in self._fmt_boxes.values():
            fmt_row.addWidget(b)
        fmt_row.addStretch(1)
        freq = QHBoxLayout()
        for w in (QLabel("frequenza"), self._freq, self._freq_help):
            freq.addWidget(w)
        freq.addStretch(1); freq.addWidget(self._size_lbl)
        out = QHBoxLayout()
        for w in (QLabel("cartella"), self._out_dir, self._browse):
            out.addWidget(w)
        run = QHBoxLayout(); run.addWidget(self._gen_btn); run.addWidget(self._progress)
        for lay in (ctl, fmt_row, freq, out, run):
            root.addLayout(lay)
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
        eye.setAttribute(Qt.WA_Hover, True)
        eye.installEventFilter(self)
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

    # ---- the eye ----
    def show_preview(self, row):
        """Draw ONE sample of this source. For `generator` and for jittered `built` the scenario IS a
        distribution -- so this is a representative sample at a FIXED seed, and the title says so. Only an
        un-jittered preset's curve is exactly what will come out."""
        fam, src = row.family.currentText(), row.source.currentText()
        if not src:
            return
        v = preview_sample(fam, src, self.PREVIEW_SEED, self.strength(), self._specs, self._params_gt)
        self._popup_panel.set_scenario(v)
        self._popup_title.setText(f"{fam} · {src} — campione (seed {self.PREVIEW_SEED})")
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

    # ---- getters (the app reads these; the Meso idiom) ----
    def mix(self):
        return [MixEntry(r.family.currentText(), r.source.currentText(), float(r.weight.value()))
                for r in self._rows]

    def count(self):
        return int(self._count.value())

    def seed(self):
        return int(self._seed.value())

    def strength(self):
        return self._jitter.value() / 100.0

    def k(self):
        return _K_CHOICES[self._freq.currentIndex()][1]

    def formats(self):
        return [n for n, b in self._fmt_boxes.items() if b.isChecked() and FORMATS[n].available]

    def out_dir(self):
        return self._out_dir.text().strip()

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Cartella del dataset", self._out_dir.text())
        if d:
            self._out_dir.setText(d)

    def _ticks_per_traj(self):
        """The length each drawn trajectory will have, AFTER decimation. built = its blocks' sum;
        preset/generator = the canonical 600 -- mirrors dataset_gen.draw_scenario."""
        out, k = [], self.k()
        for r, q in zip(self._rows, quotas(self.mix(), self.count())):
            fam, src = r.family.currentText(), r.source.currentText()
            n = (sum(int(b.ticks) for b in self._specs[src].blocks)
                 if fam == "built" and src in self._specs else _PRESET_N)
            out.extend([len(range(0, n, k))] * q)
        return out

    def estimated_bytes(self):
        fmts = self.formats()
        return estimate_bytes(self._ticks_per_traj(), fmts) if fmts else 0.0

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
            self._size_lbl.setText(f"dimensione stimata  ≈ {self.estimated_bytes() / 1e6:.1f} MB")
        else:
            for r in self._rows:
                r.quota.setText("—")
            self._size_lbl.setText("dimensione stimata  —")
