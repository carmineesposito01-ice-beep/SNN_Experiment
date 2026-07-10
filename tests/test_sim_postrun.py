import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6.QtWidgets import QApplication          # noqa: E402
from sim.ui.postrun_page import PostRunPage          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_postrun_page_populates(qapp):
    p = PostRunPage()
    s = {"n_ticks": 3, "duration_s": 0.3, "collided": False, "min_gap": 12.5, "min_ttc": 4.0,
         "max_decel": 2.1, "rms_accel": 0.5, "rms_jerk": 1.2, "mean_firing_pct": 9.4,
         "peak_firing_pct": 15.0, "snn_pj": 400.0, "ann_pj": 6000.0, "advantage": 15.0}
    rows = [(0, 30.0, 20.0, 20.0, 0.0, 0.0, "", 30, 1.5, 2, 1.5, 1.5, 9.4),
            (1, 28.0, 20.0, 21.0, -1.0, 0.5, "", 30, 1.5, 2, 1.5, 1.5, 9.4),
            (2, 26.0, 20.5, 21.0, -0.5, 0.3, "", 30, 1.5, 2, 1.5, 1.5, 9.4)]
    p.set_summary(s, rows, "Raffaello", "following")
    assert "Raffaello" in p._subtitle.text() and "following" in p._subtitle.text()
    assert "12.5" in p._values["min_gap"].text()
    assert "ok" in p._values["esito"].text().lower()
    assert len(p._v_curve.getData()[0]) == 3          # speed plot has the episode length


def test_postrun_page_v2_groups_and_tooltips(qapp):
    from sim.ui.postrun_page import _METRIC_HELP
    p = PostRunPage()
    s = {"n_ticks": 5, "duration_s": 0.5, "collided": False, "min_gap": 12.5, "min_ttc": 4.0,
         "brake_margin_min": 8.1, "max_DRAC": 2.2, "TET": 0.0, "TIT": 0.0, "impact_dv": 0.0,
         "rms_accel": 0.5, "max_decel": 2.0, "rms_jerk": 1.2, "frac_decel_iso_viol": 0.0,
         "frac_accel_iso_viol": 0.0, "param_rmse_v0": 1.2, "param_rmse_T": 0.1, "param_rmse_s0": 0.1,
         "param_rmse_a": 0.2, "param_rmse_b": 0.3, "id_accuracy": 84.0, "mean_firing_pct": 15.0,
         "peak_firing_pct": 40.0, "dead_pct": 0.0, "max_spikes_tick": 12, "rho": 0.05,
         "snn_pj": 400.0, "ann_pj": 6000.0, "advantage": 15.0, "e_fc": 100.0, "e_recV": 150.0,
         "e_recU": 100.0, "e_out": 50.0}
    rows = [(t, 30.0 - t, 20.0, 20.0, 0.0, 0.0, "", 30, 1.5, 2, 1.5, 1.5, 15.0) for t in range(5)]
    p.set_summary(s, rows, "Donatello", "cut_in")
    assert "0.05" in p._values["rho"].text()
    assert "84" in p._values["id_accuracy"].text()
    assert p._help_labels["rho"].toolTip() and "ρ" in p._help_labels["rho"].toolTip()
    assert "min_ttc" in _METRIC_HELP and "advantage" in _METRIC_HELP


def test_postrun_page_v3_cards(qapp):
    p = PostRunPage()
    assert len(p._cards) >= 5                    # dashboard is card-based
    assert p._verdict is not None                # big verdict badge exists


def _safe_summary(**over):
    s = {"n_ticks": 5, "duration_s": 0.5, "collided": False, "min_gap": 20.0,
         "min_ttc": float("inf"), "brake_margin_min": 15.0, "max_DRAC": 1.0, "TET": 0.0, "TIT": 0.0,
         "impact_dv": 0.0, "rms_accel": 0.5, "max_decel": 2.0, "rms_jerk": 1.0,
         "frac_decel_iso_viol": 0.0, "frac_accel_iso_viol": 0.0, "param_rmse_v0": 1.0,
         "param_rmse_T": 0.1, "param_rmse_s0": 0.1, "param_rmse_a": 0.1, "param_rmse_b": 0.1,
         "id_accuracy": 84.0, "mean_firing_pct": 15.0, "peak_firing_pct": 40.0, "dead_pct": 0.0,
         "max_spikes_tick": 12, "rho": 0.05, "snn_pj": 400.0, "ann_pj": 6000.0, "advantage": 15.0,
         "e_fc": 100.0, "e_recV": 150.0, "e_recU": 100.0, "e_out": 50.0}
    s.update(over)
    return s


def test_postrun_safety_danger_index_and_comfort_colours(qapp):
    from sim.ui.postrun_page import _GREEN, _RED
    p = PostRunPage()
    rows = [(t, 30.0, 20.0, 20.0, 0.0, 0.0, "", 30, 1.5, 2, 1.5, 1.5, 15.0) for t in range(5)]

    p.set_summary(_safe_summary(), rows, "Donatello", "following")
    d = list(p._bars["safe"].opts["width"])
    assert d[0] == 0.0                                       # min_ttc=∞ -> zero danger (NOT a red full bar)
    assert all(x < 1.0 for x in d)                           # all below the limit line
    assert p._bars["safe"].opts["brushes"][0].color().name() == _GREEN
    assert p._bars["comf"].opts["brushes"][1].color().name() == _GREEN   # max_decel 2.0 < ISO 3.5

    coll = _safe_summary(collided=True, min_ttc=0.8, max_DRAC=5.0, brake_margin_min=-2.0,
                         max_decel=9.0, rms_jerk=3.0, rho=2.99)
    p.set_summary(coll, rows, "Raffaello", "cut_in")
    assert "COLLISIONE" in p._verdict.text() and _RED in p._verdict.styleSheet()
    d = list(p._bars["safe"].opts["width"])
    assert all(x >= 1.0 for x in d)                          # all three past the safety limit
    assert all(b.color().name() == _RED for b in p._bars["safe"].opts["brushes"])
    cbr = p._bars["comf"].opts["brushes"]
    assert cbr[1].color().name() == _RED and cbr[2].color().name() == _RED   # decel 9>3.5, jerk 3>2
    assert p._rho_plot.getViewBox().viewRange()[0][1] >= 2.99 * 1.15 - 1e-6   # ρ>1 scale crosses the boundary
