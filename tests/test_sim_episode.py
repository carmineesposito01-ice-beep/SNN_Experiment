import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.state import StepResult                              # noqa: E402
from sim.ui.episode import EpisodeSummary, write_episode_csv  # noqa: E402
from config import DT                                         # noqa: E402

DIMS = (4, 32, 5, 8)   # (n_in, n_hid, n_out, rank) == SynOpsPanel dims


def _step(t, s, v, dv, a, collided=False):
    return StepResult(t=t, s=s, v=v, vl=v - dv, dv=dv, a_ego=a, params=np.array([30., 1.5, 2., 1.5, 1.5]),
                      collided=collided)


def test_episode_summary_aggregates():
    acc = EpisodeSummary(DIMS)
    spikes = np.zeros(32); spikes[:4] = 1.0                   # 4/32 firing = 12.5%
    acc.update(_step(0, s=30.0, v=20.0, dv=0.0, a=0.0), spikes)
    acc.update(_step(1, s=10.0, v=20.0, dv=5.0, a=-3.0, collided=True), spikes)
    s = acc.summary()
    assert s["n_ticks"] == 2 and abs(s["duration_s"] - 2 * DT) < 1e-9
    assert s["collided"] is True
    v_new = max(0.0, 20.0 - 3.0 * DT)                        # collision min_gap = POST-update penetration (as the report)
    assert abs(s["min_gap"] - round(10.0 + (15.0 - v_new) * DT, 3)) < 1e-6
    assert abs(s["min_ttc"] - 2.0) < 1e-6                     # 10/5 at tick 1 (tick 0 not closing)
    assert s["max_decel"] == 3.0                             # -min(a) = 3
    assert abs(s["peak_firing_pct"] - 12.5) < 1e-6
    assert s["snn_pj"] > 0 and s["ann_pj"] > s["snn_pj"]      # AC energy < dense-MAC energy
    assert len(acc.rows()) == 2


def test_episode_summary_reset():
    acc = EpisodeSummary(DIMS)
    acc.update(_step(0, 30.0, 20.0, 0.0, 0.0), np.zeros(32))
    acc.reset()
    assert acc.summary()["n_ticks"] == 0 and acc.rows() == []


def test_write_episode_csv(tmp_path):
    acc = EpisodeSummary(DIMS)
    acc.update(_step(0, 30.0, 20.0, 0.0, 0.0), np.zeros(32))
    p = tmp_path / "ep.csv"
    write_episode_csv(acc.rows(), str(p))
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("t,gap,v,v_leader") and len(lines) == 2   # header + 1 row


def test_spectral_radius_matches_reports():
    from utils.champion_io import load_champion
    from sim.ui.episode import spectral_radius_po2
    REPO2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raff = spectral_radius_po2(load_champion(os.path.join(REPO2, "champions", "R33_C2_A1_T12_fix", "best_model.pt")).model)
    don = spectral_radius_po2(load_champion(os.path.join(REPO2, "champions", "PE_t05_gp0002", "best_model.pt")).model)
    assert abs(raff - 2.99) < 0.35      # VALIDATION §9.3 / FPGA §0: Raffaello ρ≈2.99 (expansive)
    assert 0.0 <= don < 0.5             # Donatello ρ≈0.05 (contractive)


def test_episode_summary_v2_rich():
    acc = EpisodeSummary(DIMS, params_gt=np.array([30., 1.5, 2., 1.5, 1.5]))
    sp = np.zeros(32); sp[:6] = 1.0
    dead_sp = np.zeros(32)
    for t in range(10):
        acc.update(_step(t, s=30.0 - t, v=20.0, dv=1.0 + t, a=-0.5 * t), sp if t % 2 else dead_sp)
    s = acc.summary()
    for k in ("min_ttc", "brake_margin_min", "max_DRAC", "TET", "TIT", "impact_dv",
              "rms_accel", "max_decel", "rms_jerk", "frac_decel_iso_viol"):
        assert k in s
    assert "param_rmse_v0" in s and s["param_rmse_v0"] == 0.0    # pred==GT here
    assert s["dead_pct"] > 0.0 and "max_spikes_tick" in s
    assert abs((s["e_fc"] + s["e_recV"] + s["e_recU"] + s["e_out"]) - s["snn_pj"]) < 1e-6
    assert s["advantage"] > 1.0


def test_episode_energy_matches_direct_synops():
    from sim.ui.metrics import synops as _syn, E_AC_PJ as _EAC
    acc = EpisodeSummary(DIMS)
    spk = [np.array([1.0 if (i + t) % 4 == 0 else 0.0 for i in range(32)]) for t in range(8)]
    for t in range(8):
        acc.update(_step(t, 30.0, 20.0, 0.0, 0.0), spk[t])
    direct = sum(sum(_syn(s, 4, 32, 5, 8)) for s in spk) * _EAC       # same path as the SynOps dock
    assert abs(acc.summary()["snn_pj"] - direct) < 1e-6              # ONE energy path, no re-derivation
