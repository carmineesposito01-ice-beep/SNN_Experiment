"""EpisodeSummary -- incremental per-episode aggregator (O(1)/tick, independent of the ring buffer,
no reconstruct). Reads StepResult + per-tick spikes; exposes safety/comfort/network/energy aggregates
and per-tick rows for CSV export. Pure: no Qt."""
import csv

import numpy as np

from config import DT
from sim.ui.metrics import E_AC_PJ, E_MAC_PJ, ann_mac, synops, ttc

CSV_HEADER = ("t", "gap", "v", "v_leader", "dv", "accel", "ttc",
              "v0", "T", "s0", "a", "b", "firing_pct")


class EpisodeSummary:
    def __init__(self, dims):
        self._dims = tuple(int(x) for x in dims)   # (n_in, n_hid, n_out, rank)
        self.reset()

    def reset(self):
        self._n = 0
        self._collided = False
        self._min_gap = float("inf")
        self._min_ttc = float("inf")
        self._max_decel = 0.0
        self._sum_a2 = 0.0
        self._sum_jerk2 = 0.0
        self._prev_a = None
        self._sum_fire = 0.0
        self._peak_fire = 0.0
        self._synops_total = 0.0
        self._rows = []

    def update(self, r, spikes):
        n_in, n_hid, n_out, rank = self._dims
        a = float(r.a_ego)
        gap = float(r.s)
        tval = float(ttc(gap, r.dv))
        fire = float(np.asarray(spikes).mean())
        self._n += 1
        self._collided = self._collided or bool(r.collided)
        self._min_gap = min(self._min_gap, gap)
        if np.isfinite(tval):
            self._min_ttc = min(self._min_ttc, tval)
        self._max_decel = max(self._max_decel, -a)
        self._sum_a2 += a * a
        if self._prev_a is not None:
            j = (a - self._prev_a) / DT
            self._sum_jerk2 += j * j
        self._prev_a = a
        self._sum_fire += fire
        self._peak_fire = max(self._peak_fire, fire)
        static, dynamic = synops(spikes, n_in, n_hid, n_out, rank)
        self._synops_total += static + dynamic
        p = np.asarray(r.params, dtype=float)
        self._rows.append((r.t, round(gap, 3), round(float(r.v), 3), round(float(r.vl), 3),
                           round(float(r.dv), 3), round(a, 3),
                           round(tval, 3) if np.isfinite(tval) else "",
                           *(round(float(x), 4) for x in p[:5]), round(fire * 100, 2)))

    def summary(self):
        n = self._n
        n_in, n_hid, n_out, rank = self._dims
        snn_pj = self._synops_total * E_AC_PJ
        ann_pj = n * ann_mac(n_in, n_hid, n_out) * E_MAC_PJ
        return {
            "n_ticks": n,
            "duration_s": round(n * DT, 2),
            "collided": self._collided,
            "min_gap": round(self._min_gap, 3) if n else 0.0,
            "min_ttc": (round(self._min_ttc, 3) if np.isfinite(self._min_ttc) else float("inf")),
            "max_decel": round(self._max_decel, 3),
            "rms_accel": round((self._sum_a2 / n) ** 0.5, 3) if n else 0.0,
            "rms_jerk": round((self._sum_jerk2 / (n - 1)) ** 0.5, 3) if n > 1 else 0.0,
            "mean_firing_pct": round(self._sum_fire / n * 100, 2) if n else 0.0,
            "peak_firing_pct": round(self._peak_fire * 100, 2),
            "snn_pj": round(snn_pj, 1),
            "ann_pj": round(ann_pj, 1),
            "advantage": round(ann_pj / snn_pj, 2) if snn_pj > 0 else 0.0,
        }

    def rows(self):
        return list(self._rows)


def write_episode_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        w.writerows(rows)
