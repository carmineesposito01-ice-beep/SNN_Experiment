"""The Training destination: a MixTable(with_regime) + the training controls -> the .pt cache train.py reads.

Its own widget (like B1 extracted MixTable) so DatasetPage stays a thin toggle+stack shell and the training
controls are testable alone. The panel owns WIDGETS and exposes getters; the APP owns the run and reaches
build_training_cache with them. The validation selector and the mode-3 val table are added in Task 4."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QSlider,
                               QSpinBox, QVBoxLayout, QWidget)

from sim.train_gen import SECONDS_PER_TRAJ
from sim.ui.mix_table import MixTable

_PT_BYTES_PER_TICK = 78.3        # measured at the engine's functional-verify (the .pt cache)


class TrainingPanel(QWidget):
    def __init__(self, params_gt):
        super().__init__()
        self._params_gt = params_gt
        self._on_generate = None

        self._mix = MixTable(params_gt, strength=self.strength, with_regime=True)
        self._mix.changed.connect(self._refresh)

        self._seed = QSpinBox(); self._seed.setRange(0, 2**31 - 1); self._seed.setValue(42)
        self._n_train = QSpinBox(); self._n_train.setRange(1, 1000000); self._n_train.setValue(5000)
        self._n_val = QSpinBox(); self._n_val.setRange(1, 1000000); self._n_val.setValue(500)
        for s in (self._n_train, self._n_val):
            s.valueChanged.connect(lambda _v: (self._mix.set_count(self._n_train.value()), self._refresh()))

        self._jitter = QSlider(Qt.Horizontal); self._jitter.setRange(0, 100); self._jitter.setValue(25)
        self._jitter.setFixedWidth(120)
        self._jitter_lbl = QLabel("25%")
        self._jitter.valueChanged.connect(lambda v: (self._jitter_lbl.setText(f"{v}%"), self._refresh()))
        self._jitter_note = QLabel("⚠ governa il LEADER (built/preset), non i params: quelli sono le etichette e li dà il regime")
        self._jitter_note.setStyleSheet("color:#e8a33d")

        self._freq = QComboBox(); self._freq.addItems(["10 Hz (fissa)"]); self._freq.setEnabled(False)
        self._freq.setToolTip("DT=0.1 s è dentro la fisica E dentro la PINN loss (a_l per differenze finite su DT).\n"
                              "Un training set decimato sarebbe sbagliato in silenzio.")
        self._freq_note = QLabel("bloccata: DT è dentro la PINN loss"); self._freq_note.setStyleSheet("color:#6e7681")
        self._fmt_lbl = QLabel(".pt (cache train.py)")

        self._size_lbl = QLabel()
        self._eta_lbl = QLabel(); self._eta_lbl.setStyleSheet("color:#6e7681")
        self._out_dir = QLineEdit(r"cache.pt")
        self._cmd_lbl = QLabel(); self._cmd_lbl.setStyleSheet("font-family:Consolas,monospace; color:#6e7681")
        self._out_dir.textChanged.connect(self._refresh)

        self._gen_btn = QPushButton("Genera")
        self._gen_btn.clicked.connect(lambda: self._on_generate() if self._on_generate else None)
        self._cancel_btn = QPushButton("Annulla"); self._cancel_btn.setEnabled(False)
        self._progress = QProgressBar(); self._progress.setRange(0, 100); self._progress.setValue(0)

        root = QVBoxLayout(self)
        root.addWidget(QLabel("MIX (training)"))
        root.addWidget(self._mix)
        c1 = QHBoxLayout()
        for w in (QLabel("seed"), self._seed, QLabel("train"), self._n_train, QLabel("val"), self._n_val,
                  QLabel("jitter"), self._jitter, self._jitter_lbl, self._jitter_note):
            c1.addWidget(w)
        c1.addStretch(1)
        c2 = QHBoxLayout()
        for w in (QLabel("frequenza"), self._freq, self._freq_note, QLabel("formato"), self._fmt_lbl):
            c2.addWidget(w)
        c2.addStretch(1); c2.addWidget(self._size_lbl)
        out = QHBoxLayout()
        for w in (QLabel("file"), self._out_dir):
            out.addWidget(w)
        run = QHBoxLayout()
        for w in (self._gen_btn, self._cancel_btn, self._progress, self._eta_lbl):
            run.addWidget(w)
        for lay in (c1, c2, out, run):
            root.addLayout(lay)
        root.addWidget(self._cmd_lbl)
        root.addStretch(1)
        self._refresh()

    # ---- sources / getters (the app reads these) ----
    def set_sources(self, specs, preset_names):
        self._mix.set_sources(specs, preset_names)

    def mix(self):
        return self._mix.mix()

    def n_train(self):
        return int(self._n_train.value())

    def n_val(self):
        return int(self._n_val.value())

    def seed(self):
        return int(self._seed.value())

    def strength(self):
        return self._jitter.value() / 100.0

    def out_path(self):
        return self._out_dir.text().strip()

    # ---- estimates ----
    def _estimate_bytes(self):
        """A rough .pt size. TICKS drive the file: each trajectory stores raw(N,7)+x+y+mask; the engine measured
        78.3 B per stored tick. Sum the post-warmup ticks across train + val at their quotas."""
        from sim.train_gen import WARMUP_STEPS, _PRESET_N
        from sim.train_mix import train_quotas
        from config import SIM_DURATION, DT
        specs = self._mix.specs()
        total_ticks = 0
        for count in (self.n_train(), self.n_val()):
            for e, q in zip(self.mix(), train_quotas(self.mix(), count)):
                if e.family == "built":
                    raw = sum(int(b.ticks) for b in specs[e.source].blocks) if e.source in specs else 0
                elif e.family == "preset":
                    raw = _PRESET_N
                else:
                    raw = int(SIM_DURATION / DT)
                total_ticks += q * max(raw - WARMUP_STEPS, 0)
        return total_ticks * _PT_BYTES_PER_TICK

    def eta_seconds(self):
        return (self.n_train() + self.n_val()) * SECONDS_PER_TRAJ

    # ---- refresh ----
    def _refresh(self):
        ok = self._mix.is_valid()
        self._gen_btn.setEnabled(ok)
        eta = self.eta_seconds()
        self._eta_lbl.setText(f"≈ {eta / 60:.0f} min" if eta >= 60 else f"≈ {eta:.0f} s")
        path = self.out_path()
        self._cmd_lbl.setText(f"poi:  python train.py --data_cache {path}" if path else "")
        if ok:
            self._size_lbl.setText(f"dimensione stimata  ≈ {self._estimate_bytes() / 1e6:.0f} MB")
        else:
            self._size_lbl.setText("dimensione stimata  —")
