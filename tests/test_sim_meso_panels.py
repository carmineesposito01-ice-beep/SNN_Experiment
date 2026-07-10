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
from sim.ui.meso_panels import (FundamentalDiagramPanel, PlatoonParamsPanel,   # noqa: E402
                                SpaceTimePanel, StringStabilityPanel)


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


def test_space_time_panel_plot_in_layout(qapp):
    # the plot must be added to the panel layout, else it is an orphan widget -> never shown (blank panel)
    p = SpaceTimePanel()
    assert p.layout().indexOf(p._plot) >= 0


def test_space_time_panel_view_fits_data(qapp):
    # clipToView + downsampling leave the ViewBox stuck at the default [0,1] range (auto-range never
    # fires when populated before first show) -> blank panel. set_rec must frame the data explicitly.
    p = SpaceTimePanel()
    x = np.cumsum(np.full((30, 3), 5.0), axis=0)     # positions 5..150, well outside default [0,1]
    p.set_rec({"x": x})
    _, y_range = p._plot.getViewBox().viewRange()
    assert y_range[1] > 100.0                         # view fits the data, not stuck at [0,1]


def test_fundamental_diagram_panel_plots(qapp):
    p = FundamentalDiagramPanel()
    p.set_points([
        {"rho_veh_km": 20.0, "Q_veh_h": 1400.0, "V_m_s": 19.0, "V_km_h": 68.4,
         "n": 20, "wave_std": 0.1, "unstable": False},
        {"rho_veh_km": 60.0, "Q_veh_h": 1800.0, "V_m_s": 8.0, "V_km_h": 28.8,
         "n": 60, "wave_std": 0.9, "unstable": True},
    ])
    qx, qy = p._q_curve.getData()
    assert len(qx) == 2 and list(qy) == [1400.0, 1800.0]
    assert len(p._q_unstable.getData()[0]) == 1          # the one unstable point is marked


def test_platoon_params_panel_means(qapp):
    T, N = 20, 4
    params = np.random.default_rng(0).random((T, N, 5))
    p = PlatoonParamsPanel(params_gt=[30.0, 1.5, 2.0, 1.5, 1.5])
    p.set_rec({"params": params}, warmup_frac=0.0)       # 5 param strips, mean over the regime
    assert len(p._bars) == 5
    assert np.allclose(p._bars[0].opts["height"], params[:, :, 0].mean(axis=0))
