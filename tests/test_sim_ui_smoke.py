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


# --- Task 4: SimApp ---
from sim.ui.app import SimApp               # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


def test_simapp_loads_champion_and_advances(qapp):
    win = SimApp(CHAMP)
    assert win.scenario_count() >= 10        # 9 library (include_tail) + manual
    win.select_scenario(0)
    win._advance(0.5)                        # 5 fixed steps, headless (no timer)
    assert win.loop.stepper.st.t >= 5
    win.inject_brake()                       # enqueues a brake_leader at current tick
    win._advance(0.5)                        # must not raise
