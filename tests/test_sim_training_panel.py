import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from sim.ui.training_panel import TrainingPanel                 # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _panel(qapp):
    p = TrainingPanel(params_gt=_PG)
    p.set_sources({}, ["following", "hard_brake"])
    return p


def test_the_panel_exposes_the_engine_arguments(qapp):
    from sim.train_mix import TrainMixEntry
    p = _panel(qapp)
    p._mix._rows[0].family.setCurrentText("generator")
    p._mix._rows[0].source.setCurrentText("sinusoidal")
    p._mix._rows[0].regime.setCurrentText("highway")
    p._mix._rows[0].weight.setValue(100.0)
    p._n_train.setValue(5000); p._n_val.setValue(500); p._seed.setValue(7)
    assert p.mix() == [TrainMixEntry("generator", "sinusoidal", "highway", 100.0)]
    assert p.n_train() == 5000 and p.n_val() == 500 and p.seed() == 7
    assert 0.0 <= p.strength() <= 1.0


def test_the_frequency_is_shown_disabled_with_its_reason(qapp):
    p = _panel(qapp)
    assert not p._freq.isEnabled()                     # decimation is off for training
    assert "PINN" in p._freq_note.text() or "PINN" in p._freq.toolTip()


def test_the_format_is_pt(qapp):
    p = _panel(qapp)
    assert ".pt" in p._fmt_lbl.text()                  # the training destination writes the .pt cache, nothing else


def test_the_jitter_caveat_is_reworded_for_training(qapp):
    p = _panel(qapp)
    assert "LEADER" in p._jitter_note.text() and "params" in p._jitter_note.text()


def test_the_size_estimate_uses_the_pt_bytes_per_tick(qapp):
    p = _panel(qapp)
    p._mix._rows[0].family.setCurrentText("generator")
    p._mix._rows[0].source.setCurrentText("sinusoidal")
    p._mix._rows[0].regime.setCurrentText("highway")
    p._mix._rows[0].weight.setValue(100.0)
    p._n_train.setValue(10); p._n_val.setValue(2)
    assert "MB" in p._size_lbl.text()                  # a live estimate appears when the mix is valid


def test_the_command_line_names_the_cache(qapp):
    p = _panel(qapp)
    p._out_dir.setText(r"D:\ds\cache.pt")
    assert "train.py --data_cache" in p._cmd_lbl.text() and "cache.pt" in p._cmd_lbl.text()


def test_the_eta_is_shown_before_the_click(qapp):
    p = _panel(qapp)
    p._n_train.setValue(5000); p._n_val.setValue(500)
    # 5500 * SECONDS_PER_TRAJ ~ 335 s ~ 5-6 min: the label mentions minutes
    assert "min" in p._eta_lbl.text().lower()


# --- Task 4: the validation selector ---
def test_the_validation_selector_has_three_modes_and_maps_to_the_engine(qapp):
    from sim.train_gen import VAL_MODE_STANDARD, VAL_MODE_NEW_SHAPES, VAL_MODE_DIFFERENT_MIX
    p = _panel(qapp)
    assert p._val_sel.count() == 3
    p._val_sel.setCurrentIndex(0); assert p.val_mode() == VAL_MODE_STANDARD
    p._val_sel.setCurrentIndex(1); assert p.val_mode() == VAL_MODE_NEW_SHAPES
    p._val_sel.setCurrentIndex(2); assert p.val_mode() == VAL_MODE_DIFFERENT_MIX


def test_each_mode_shows_its_consequence(qapp):
    p = _panel(qapp)
    seen = set()
    for i in range(3):
        p._val_sel.setCurrentIndex(i)
        seen.add(p._val_note.text())
    assert len(seen) == 3                          # each mode states a different consequence
    p._val_sel.setCurrentIndex(2)
    assert "overfitting" in p._val_note.text().lower()   # mode 3's strong warning


def test_the_val_mix_table_appears_only_in_mode_3(qapp):
    # isHidden() reflects the explicit show/hide flag -- isVisible() is always False in an unshown offscreen panel
    p = _panel(qapp)
    p._val_sel.setCurrentIndex(0); assert p._val_mix.isHidden()
    p._val_sel.setCurrentIndex(2); assert not p._val_mix.isHidden()
    p._val_sel.setCurrentIndex(1); assert p._val_mix.isHidden()


def test_val_mix_is_returned_only_in_mode_3(qapp):
    p = _panel(qapp)
    p._val_sel.setCurrentIndex(0)
    assert p.val_mix() is None                     # standard/new_shapes reuse the train mix -> engine wants None
    p._val_sel.setCurrentIndex(2)
    assert p.val_mix() is not None                 # mode 3 supplies a separate mix
