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

from PySide6.QtWidgets import QApplication  # noqa: E402
from sim.state import StepResult            # noqa: E402
from sim.ui.topdown import TopDownView      # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _step(s):
    return StepResult(t=0, s=s, v=20.0, vl=20.0, dv=0.0, a_ego=0.0,
                      params=np.zeros(5), collided=False)


def test_topdown_instantiates_and_updates(qapp):
    view = TopDownView()
    view.update_frame(_step(30.0))
    x30 = view.leader_x_px()
    view.update_frame(_step(10.0))
    assert view.leader_x_px() < x30          # smaller gap -> leader closer


# --- Task 3: NetPanel ---
from sim.probe import AttributeProbe        # noqa: E402
from sim.ui.netpanel import NetPanel        # noqa: E402


def test_netpanel_instantiates_and_updates(qapp):
    probe = AttributeProbe(capacity=50)
    for t in range(5):
        probe.record(t, {"spikes": (np.arange(8) % 2).astype(float),
                          "v_mem": np.linspace(0, 1, 8),
                          "v_th_eff": np.ones(8)}, np.arange(5) + t)
    panel = NetPanel()
    panel.update_frame(probe)               # must not raise
    assert panel.n_params_curves() == 5
