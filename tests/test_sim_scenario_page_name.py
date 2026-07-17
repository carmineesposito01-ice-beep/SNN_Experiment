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

from sim.ui.scenario_page import ScenarioPage            # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _page_with_a_block(qapp):
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    page = ScenarioPage(params_gt=np.array([30.0, 1.5, 2.0, 1.5, 1.5]), N=600)
    page.set_spec(ScenarioSpec(name="x", blocks=(Block("const", 100, {"v": 15.0}),),
                               style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0))   # a spec with a block
    return page


def test_name_field_sets_the_emitted_scenario_name(qapp):
    page = _page_with_a_block(qapp)
    got = []
    page.sigScenarioBuilt.connect(lambda sc, sp: got.append(sc))
    page._name_edit.setText("myrun")
    page._on_use()
    assert got and got[-1].name == "myrun"


def test_empty_name_autogenerates_a_unique_name(qapp):
    page = _page_with_a_block(qapp)
    got = []
    page.sigScenarioBuilt.connect(lambda sc, sp: got.append(sc))
    page._name_edit.setText("")
    page._on_use()
    page._on_use()
    assert got[0].name == "scenario_1" and got[1].name == "scenario_2"
