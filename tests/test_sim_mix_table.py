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
from sim.ui.mix_table import MixTable                            # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _specs():
    return {"mine": ScenarioSpec(name="mine", blocks=(Block("const", 120, {"v": 15.0}),),
                                 style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)}


def _table(qapp, specs=None):
    t = MixTable(params_gt=_PG, strength=lambda: 0.25)
    t.set_sources(specs if specs is not None else _specs(), ["following", "hard_brake"])
    return t


def test_a_fresh_table_has_one_row_and_the_families(qapp):
    from sim.dataset_mix import FAMILIES
    t = _table(qapp)
    assert len(t._rows) == 1
    assert [t._rows[0].family.itemText(i) for i in range(t._rows[0].family.count())] == list(FAMILIES)


def test_the_source_combo_cascades_from_the_family(qapp):
    from sim.dataset_gen import GENERATOR_PROFILES
    t = _table(qapp)
    r = t._rows[0]
    r.family.setCurrentText("preset")
    assert [r.source.itemText(i) for i in range(r.source.count())] == ["following", "hard_brake"]
    r.family.setCurrentText("generator")
    assert [r.source.itemText(i) for i in range(r.source.count())] == list(GENERATOR_PROFILES)
    r.family.setCurrentText("built")
    assert [r.source.itemText(i) for i in range(r.source.count())] == ["mine"]


def test_the_built_family_is_disabled_when_no_scenario_was_built(qapp):
    t = _table(qapp, specs={})
    model = t._rows[0].family.model()
    assert not model.item(0).isEnabled()          # "built" is FAMILIES[0]
    assert "Scenari" in model.item(0).toolTip()


def test_the_quota_column_is_live_and_exact(qapp):
    t = _table(qapp)
    t.set_count(100)
    t._rows[0].weight.setValue(100.0)
    assert t._rows[0].quota.text() == "100"
    t.add_row(); t._rows[0].weight.setValue(40.0); t._rows[1].weight.setValue(60.0)
    assert [r.quota.text() for r in t._rows] == ["40", "60"]


def test_mix_returns_the_engines_MixEntry(qapp):
    from sim.dataset_mix import MixEntry, validate_mix
    t = _table(qapp)
    t._rows[0].family.setCurrentText("preset")
    t._rows[0].source.setCurrentText("hard_brake")
    t._rows[0].weight.setValue(100.0)
    mix = t.mix()
    assert mix == [MixEntry("preset", "hard_brake", 100.0)]
    validate_mix(mix)


def test_removing_a_row_keeps_the_table_consistent(qapp):
    t = _table(qapp)
    t.add_row()
    assert len(t._rows) == 2
    t.remove_row(t._rows[1])
    assert len(t._rows) == 1


def test_is_valid_tracks_the_total(qapp):
    t = _table(qapp)
    t._rows[0].weight.setValue(40.0)
    assert not t.is_valid() and "✗" in t._total_lbl.text()
    t._rows[0].weight.setValue(100.0)
    assert t.is_valid() and "✓" in t._total_lbl.text()


def test_changed_fires_when_a_weight_moves(qapp):
    t = _table(qapp)
    seen = []
    t.changed.connect(lambda: seen.append(1))
    t._rows[0].weight.setValue(55.0)
    assert seen                                    # the page listens to this to re-gate + re-estimate


def test_the_eye_shows_the_engines_sample_and_calls_it_a_sample(qapp):
    from sim.dataset_gen import preview_sample
    t = _table(qapp)
    r = t._rows[0]
    r.family.setCurrentText("preset")
    r.source.setCurrentText("hard_brake")
    t.show_preview(r)
    expected = preview_sample("preset", "hard_brake", t.PREVIEW_SEED, 0.25, t._specs, t._params_gt)
    shown = t._popup_panel._curve.getData()[1]
    assert np.allclose(shown, expected)
    assert "campione" in t._popup_title.text()
    assert r.eye.text() != "👁"                     # the glyph that rendered as a blob is gone


def test_the_preview_is_hidden_until_asked_and_hides_again(qapp):
    t = _table(qapp)
    assert not t._popup.isVisible()
    t.show_preview(t._rows[0])
    assert t._popup.isVisible()
    t.hide_preview()
    assert not t._popup.isVisible()
