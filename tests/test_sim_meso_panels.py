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
from sim.ui.meso_panels import (FundamentalDiagramPanel, SpaceTimePanel,   # noqa: E402
                                SpeedWavePanel, StringStabilityPanel)


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


def test_speed_wave_panel_curves_and_view(qapp):
    p = SpeedWavePanel()
    v = np.abs(np.cumsum(np.full((30, 3), 1.0), axis=0)) + 5.0   # speeds 6..35, outside [0,1]
    p.set_rec({"v": v})
    active = [c for c in p._curves if c.getData()[0] is not None and len(c.getData()[0]) > 0]
    assert len(active) == 3                              # one curve per vehicle from rec['v']
    assert p.layout().indexOf(p._plot) >= 0              # plot is in the layout (else blank)
    _, y_range = p._plot.getViewBox().viewRange()
    assert y_range[1] > 10.0                             # view fits the data, not stuck at [0,1]


def test_fundamental_diagram_unstable_hover_data_and_legend(qapp):
    # Bug: the red x marks were unexplained. Each carries its wave_std for the hover tooltip, and an
    # on-panel legend states what the symbol means (stop-and-go unstable density point).
    p = FundamentalDiagramPanel()
    p.set_points([
        {"rho_veh_km": 20.0, "Q_veh_h": 1400.0, "V_m_s": 19.0, "V_km_h": 68.4,
         "n": 20, "wave_std": 0.1, "unstable": False},
        {"rho_veh_km": 60.0, "Q_veh_h": 1800.0, "V_m_s": 8.0, "V_km_h": 28.8,
         "n": 60, "wave_std": 0.9, "unstable": True},
    ])
    pts = p._q_unstable.points()
    assert len(pts) == 1 and abs(pts[0].data() - 0.9) < 1e-9   # wave_std attached -> shown on hover
    assert "instabile" in p._legend.text().lower()             # symbol explained on the panel


def test_meso_curve_click_emits_vehicle_index(qapp):
    # Feature: a vehicle's curve is clickable -> emits its index (so the page can highlight it).
    p = SpeedWavePanel()
    p.set_rec({"v": np.abs(np.cumsum(np.full((10, 4), 1.0), axis=0)) + 5.0})
    got = []
    p.sigVehicleClicked.connect(got.append)
    p._curves[2].sigClicked.emit(p._curves[2], None)     # the signal setCurveClickable fires on click
    assert got == [2]


def test_meso_curve_highlight_bolds_selected_dims_rest(qapp):
    p = SpaceTimePanel()
    p.set_rec({"x": np.cumsum(np.full((10, 4), 5.0), axis=0)})
    p.highlight(1)
    assert p._highlighted == 1
    sel = p._curves[1].opts["pen"]
    assert abs(sel.widthF() - 2.5) < 1e-9 and sel.color().name() == "#ffffff"   # selected: bold white
    assert abs(p._curves[0].opts["pen"].widthF() - 0.5) < 1e-9                   # the rest: dimmed
    p.highlight(None)
    assert p._highlighted is None
    assert abs(p._curves[0].opts["pen"].widthF() - 1.0) < 1e-9                   # back to normal width


def test_meso_page_click_syncs_road_and_both_panels(qapp):
    # Feature: clicking a curve in one meso panel highlights that vehicle on the road AND in both panels.
    from sim.ui.meso_page import MesoMacroPage
    page = MesoMacroPage(scenario_names=["a", "b"])
    rec = {"x": np.cumsum(np.full((10, 4), 5.0), axis=0), "v": np.full((10, 4), 10.0)}
    page.road.set_run(rec); page.speed_wave.set_rec(rec); page.space_time.set_rec(rec)
    page.speed_wave.sigVehicleClicked.emit(2)            # as if a speed-wave curve was clicked
    assert page.road._highlighted == 2
    assert page.speed_wave._highlighted == 2 and page.space_time._highlighted == 2
