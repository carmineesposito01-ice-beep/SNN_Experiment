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

from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec   # noqa: E402
from sim.ui.dataset_page import DatasetPage                      # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _specs():
    return {"mine": ScenarioSpec(name="mine", blocks=(Block("const", 120, {"v": 15.0}),),
                                 style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)}


def _page(qapp, specs=None):
    p = DatasetPage(params_gt=_PG)
    p.set_sources(specs if specs is not None else _specs(), ["following", "hard_brake"])
    return p


def test_generate_is_gated_on_a_total_of_100(qapp):
    p = _page(qapp)
    p._mix._rows[0].weight.setValue(40.0)
    assert not p._gen_btn.isEnabled()
    p._mix._rows[0].weight.setValue(100.0)
    assert p._gen_btn.isEnabled()


# --- the controls ---
def test_the_format_checkboxes_come_from_the_registry(qapp):
    from sim.export_formats import FORMATS
    p = _page(qapp)
    assert set(p._fmt_boxes) == set(FORMATS)                       # all six are shown
    assert not p._fmt_boxes["parquet"].isEnabled()                 # unavailable -> disabled
    assert "pyarrow" in p._fmt_boxes["parquet"].toolTip()          # ...and it says why
    assert p._fmt_boxes["csv"].isEnabled()


def test_formats_returns_only_the_checked_available_ones(qapp):
    p = _page(qapp)
    for b in p._fmt_boxes.values():
        b.setChecked(False)
    p._fmt_boxes["csv"].setChecked(True)
    p._fmt_boxes["mat"].setChecked(True)
    assert sorted(p.formats()) == ["csv", "mat"]


def test_the_frequency_combo_maps_to_k_and_explains_itself(qapp):
    p = _page(qapp)
    assert p.k() == 1                                   # 10 Hz native by default
    p._freq.setCurrentIndex(1)
    assert p.k() == 2                                   # 5 Hz
    assert "V2V" in p._freq_help.toolTip()              # the "?" says 10 Hz is the canonical V2V rate


def test_the_jitter_slider_states_its_own_limit(qapp):
    p = _page(qapp)
    assert 0.0 <= p.strength() <= 1.0
    assert "generator" in p._jitter_note.text()         # the caveat is inline, not buried in a doc


def test_the_size_estimate_matches_the_engines_formula(qapp):
    from sim.export_formats import estimate_bytes
    p = _page(qapp)
    p._count.setValue(10)
    p._mix._rows[0].family.setCurrentText("preset")
    p._mix._rows[0].source.setCurrentText("hard_brake")
    p._mix._rows[0].weight.setValue(100.0)
    for b in p._fmt_boxes.values():
        b.setChecked(False)
    p._fmt_boxes["csv"].setChecked(True)
    p._freq.setCurrentIndex(1)                          # k=2 -> 600/2 = 300 ticks each
    expected = estimate_bytes([300] * 10, ["csv"])
    assert abs(p.estimated_bytes() - expected) < 1.0
    assert "MB" in p._size_lbl.text()
