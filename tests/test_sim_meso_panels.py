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

from PySide6.QtWidgets import QApplication          # noqa: E402
from sim.ui.meso_panels import SpaceTimePanel, StringStabilityPanel   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_string_stability_panel_bars(qapp):
    p = StringStabilityPanel()
    p.set_metrics({"gain_per_vehicle": [1.0, 0.8, 0.6], "string_stable_headtail": True,
                   "head_to_tail_gain": 0.6, "max_amplification": 1.0, "convective_upstream": False})
    assert list(p._bars.opts["height"]) == [1.0, 0.8, 0.6]
    assert "STRING-STABLE" in p._verdict.text()


def test_string_stability_panel_unstable_verdict(qapp):
    p = StringStabilityPanel()
    p.set_metrics({"gain_per_vehicle": [1.0, 1.4, 2.1], "string_stable_headtail": False,
                   "head_to_tail_gain": 2.1, "max_amplification": 2.1, "convective_upstream": True})
    assert "INSTABILE" in p._verdict.text()


def test_space_time_panel_curves(qapp):
    p = SpaceTimePanel()
    p.set_rec({"x": np.random.default_rng(0).standard_normal((20, 4))})
    active = [c for c in p._curves if c.getData()[0] is not None and len(c.getData()[0]) > 0]
    assert len(active) == 4
