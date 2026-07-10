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
    assert s["min_gap"] == 10.0
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
