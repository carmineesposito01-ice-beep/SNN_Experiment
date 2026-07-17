"""The Dataset mode (the 5th): a MixTable + the export controls.

The mix table (rows, cascade, eye, quota, total gate) is now sim/ui/mix_table.py, reused by the later training
destination. This page owns seed/count/jitter/frequency/formats/size/folder/generate and re-gates + re-estimates
whenever the table emits `changed`. The page owns WIDGETS and exposes getters; the APP owns the run (the Meso
idiom, app.py:174) -- Generate only calls self._on_generate."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QProgressBar, QPushButton, QRadioButton, QSlider, QSpinBox, QStackedWidget,
                               QVBoxLayout, QWidget)

from sim.export_formats import FORMATS, estimate_bytes
from sim.scenario_spec import _PRESET_N
from sim.ui.mix_table import MixTable
from sim.ui.training_panel import TrainingPanel

_K_CHOICES = [("10 Hz (nativa)", 1), ("5 Hz", 2), ("2 Hz", 5), ("1 Hz", 10)]


class DatasetPage(QWidget):
    PREVIEW_SEED = 0            # kept for back-compat; the eye's seed now lives on MixTable

    def __init__(self, params_gt):
        super().__init__()
        self._params_gt = params_gt
        self._on_generate = None

        self._mix = MixTable(params_gt, strength=self.strength)
        self._mix.changed.connect(self._refresh)

        self._count = QSpinBox(); self._count.setRange(1, 100000); self._count.setValue(100)
        self._count.valueChanged.connect(lambda v: (self._mix.set_count(v), self._refresh()))
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

        # -- analysis container: today's content, unchanged --
        analysis = QWidget()
        aroot = QVBoxLayout(analysis)
        aroot.addWidget(QLabel("MIX"))
        aroot.addWidget(self._mix)
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
            aroot.addLayout(lay)
        aroot.addStretch(1)

        # -- training panel --
        self._training = TrainingPanel(self._params_gt)

        # -- destination toggle + stack --
        self._dest_analisi = QRadioButton("Analisi"); self._dest_analisi.setChecked(True)
        self._dest_training = QRadioButton("Training")
        grp = QButtonGroup(self); grp.addButton(self._dest_analisi); grp.addButton(self._dest_training)
        self._stack = QStackedWidget(); self._stack.addWidget(analysis); self._stack.addWidget(self._training)
        self._dest_training.toggled.connect(lambda on: self._stack.setCurrentIndex(1 if on else 0))

        root = QVBoxLayout(self)
        dest = QHBoxLayout()
        dest.addWidget(QLabel("<b>Destinazione</b>")); dest.addWidget(self._dest_analisi)
        dest.addWidget(self._dest_training); dest.addStretch(1)
        root.addLayout(dest)
        root.addWidget(self._stack)
        self._refresh()

    # ---- destination ----
    def destination(self):
        return "training" if self._dest_training.isChecked() else "analisi"

    # ---- sources (delegated to both tables) ----
    def set_sources(self, specs, preset_names):
        self._mix.set_sources(specs, preset_names)
        self._training.set_sources(specs, preset_names)

    # ---- getters (the app reads these; the Meso idiom) ----
    def mix(self):
        return self._mix.mix()

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
        """Length each drawn trajectory will have AFTER decimation. built = its blocks' sum; preset/generator =
        the canonical 600 -- mirrors dataset_gen.draw_scenario."""
        from sim.dataset_mix import quotas
        out, k, specs = [], self.k(), self._mix.specs()
        for r, q in zip(self._mix._rows, quotas(self.mix(), self.count())):
            fam, src = r.family.currentText(), r.source.currentText()
            n = (sum(int(b.ticks) for b in specs[src].blocks)
                 if fam == "built" and src in specs else _PRESET_N)
            out.extend([len(range(0, n, k))] * q)
        return out

    def estimated_bytes(self):
        fmts = self.formats()
        return estimate_bytes(self._ticks_per_traj(), fmts) if fmts else 0.0

    # ---- refresh (a `changed` slot + the control edits) ----
    def _refresh(self):
        ok = self._mix.is_valid()
        self._gen_btn.setEnabled(ok)
        if ok:
            self._size_lbl.setText(f"dimensione stimata  ≈ {self.estimated_bytes() / 1e6:.1f} MB")
        else:
            self._size_lbl.setText("dimensione stimata  —")
