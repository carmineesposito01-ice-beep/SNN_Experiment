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


def test_a_fresh_page_has_one_row_and_the_families(qapp):
    from sim.dataset_mix import FAMILIES
    p = _page(qapp)
    assert len(p._rows) == 1
    assert [p._rows[0].family.itemText(i) for i in range(p._rows[0].family.count())] == list(FAMILIES)


def test_the_source_combo_cascades_from_the_family(qapp):
    from sim.dataset_gen import GENERATOR_PROFILES
    p = _page(qapp)
    r = p._rows[0]
    r.family.setCurrentText("preset")
    assert [r.source.itemText(i) for i in range(r.source.count())] == ["following", "hard_brake"]
    r.family.setCurrentText("generator")
    assert [r.source.itemText(i) for i in range(r.source.count())] == list(GENERATOR_PROFILES)
    r.family.setCurrentText("built")
    assert [r.source.itemText(i) for i in range(r.source.count())] == ["mine"]


def test_the_built_family_is_disabled_when_no_scenario_was_built(qapp):
    p = _page(qapp, specs={})
    model = p._rows[0].family.model()
    assert not model.item(0).isEnabled()          # "built" is FAMILIES[0]
    assert "Scenari" in model.item(0).toolTip()   # says where to go build one


def test_the_quota_column_is_live_and_exact(qapp):
    p = _page(qapp)
    p._count.setValue(100)
    p._rows[0].weight.setValue(100.0)
    assert p._rows[0].quota.text() == "100"
    p.add_row(); p._rows[0].weight.setValue(40.0); p._rows[1].weight.setValue(60.0)
    assert [r.quota.text() for r in p._rows] == ["40", "60"]


def test_generate_is_gated_on_a_total_of_100(qapp):
    p = _page(qapp)
    p._rows[0].weight.setValue(40.0)
    assert not p._gen_btn.isEnabled() and "✗" in p._total_lbl.text()
    p._rows[0].weight.setValue(100.0)
    assert p._gen_btn.isEnabled() and "✓" in p._total_lbl.text()


def test_mix_returns_the_engines_MixEntry(qapp):
    from sim.dataset_mix import MixEntry, validate_mix
    p = _page(qapp)
    p._rows[0].family.setCurrentText("preset")
    p._rows[0].source.setCurrentText("hard_brake")
    p._rows[0].weight.setValue(100.0)
    mix = p.mix()
    assert mix == [MixEntry("preset", "hard_brake", 100.0)]
    validate_mix(mix)                              # the engine accepts what the page produces


def test_removing_a_row_keeps_the_page_consistent(qapp):
    p = _page(qapp)
    p.add_row()
    assert len(p._rows) == 2
    p.remove_row(p._rows[1])
    assert len(p._rows) == 1
