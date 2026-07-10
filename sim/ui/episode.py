"""EpisodeSummary -- incremental per-episode aggregator (O(1)/tick, independent of the ring buffer,
no reconstruct). Reads StepResult + per-tick spikes; exposes safety/comfort/network/energy aggregates
and per-tick rows for CSV export. Pure: no Qt."""
import csv

import numpy as np
import torch

from config import DT
from core.hardware import po2_quantize
from sim.ui.metrics import E_AC_PJ, E_MAC_PJ, ann_mac, synops_breakdown, ttc
from utils.closed_loop_eval import comfort_metrics, safety_metrics
from utils.net_diagnostics import _last_hidden


def spectral_radius_po2(model, iters=200):
    """ρ(U·V) of the po2 low-rank recurrence via power iteration. LAPACK-free: np.linalg.eigvals/svd
    (as in net_diagnostics.recurrence_spectral) abort with OMP #15 in cf_sim. None if not low-rank."""
    hid = _last_hidden(model)
    if hid is None or not (hasattr(hid, "rec_U") and hasattr(hid, "rec_V")):
        return None
    with torch.no_grad():
        W = (po2_quantize(hid.rec_U).detach().float() @ po2_quantize(hid.rec_V).detach().float())
        v = torch.ones(W.shape[0], dtype=torch.float32); v = v / v.norm()
        lam = 0.0
        for _ in range(int(iters)):
            w = W @ v
            lam = float(w.norm())
            if lam < 1e-30:
                return 0.0                       # strongly contractive
            v = w / lam
        return lam

CSV_HEADER = ("t", "gap", "v", "v_leader", "dv", "accel", "ttc",
              "v0", "T", "s0", "a", "b", "firing_pct")


_PARAM_NAMES = ("v0", "T", "s0", "a", "b")


class EpisodeSummary:
    def __init__(self, dims, params_gt=None, model=None):
        self._dims = tuple(int(x) for x in dims)           # (n_in, n_hid, n_out, rank)
        self._gt = None if params_gt is None else np.asarray(params_gt, dtype=float)
        self._rho = spectral_radius_po2(model) if model is not None else None
        self.reset()

    def reset(self):
        self._n = 0
        self._collided = False
        self._impact_dv = 0.0
        self._collision_gap = None                         # post-update gap at the first collision (penetration)
        self._s = []; self._v = []; self._vl = []; self._dv = []; self._a = []; self._params = []
        self._sum_fire = 0.0; self._peak_fire = 0.0; self._max_spk = 0
        self._fired = None                                 # (H,) ever-fired mask
        self._e_fc = 0.0; self._e_recV = 0.0; self._e_recU = 0.0; self._e_out = 0.0
        self._rows = []

    def update(self, r, spikes):
        n_in, n_hid, n_out, rank = self._dims
        sp = np.asarray(spikes, dtype=float)
        a = float(r.a_ego); gap = float(r.s)
        self._n += 1
        if bool(r.collided) and not self._collided:        # first collision: use POST-update v/gap (as closed_loop_eval;
            v_new = max(0.0, float(r.v) + a * DT)          # StepResult carries PRE-update v/s, so advance one step)
            self._impact_dv = max(0.0, v_new - float(r.vl))
            self._collision_gap = gap + (float(r.vl) - v_new) * DT
        self._collided = self._collided or bool(r.collided)
        self._s.append(gap); self._v.append(float(r.v)); self._vl.append(float(r.vl))
        self._dv.append(float(r.dv)); self._a.append(a); self._params.append(np.asarray(r.params, float)[:5])
        fire = float(sp.mean()); self._sum_fire += fire; self._peak_fire = max(self._peak_fire, fire)
        nsp = int(np.count_nonzero(sp > 0)); self._max_spk = max(self._max_spk, nsp)
        self._fired = (sp > 0) if self._fired is None else (self._fired | (sp > 0))
        # energy breakdown via the SINGLE metrics source (no n_ticks re-normalisation; == the SynOps dock)
        e_fc, e_recV, e_recU, e_out = synops_breakdown(nsp, n_in, n_hid, n_out, rank)
        self._e_fc += e_fc; self._e_recV += e_recV; self._e_recU += e_recU; self._e_out += e_out
        tval = float(ttc(gap, r.dv))
        self._rows.append((r.t, round(gap, 3), round(float(r.v), 3), round(float(r.vl), 3),
                           round(float(r.dv), 3), round(a, 3),
                           round(tval, 3) if np.isfinite(tval) else "",
                           *(round(float(x), 4) for x in np.asarray(r.params, float)[:5]),
                           round(fire * 100, 2)))

    def summary(self):
        n = self._n
        if n == 0:
            return {"n_ticks": 0}
        a = np.asarray(self._a); v = np.asarray(self._v)
        min_gap = (self._collision_gap if (self._collided and self._collision_gap is not None)
                   else float(np.min(self._s)))            # collision -> post-update penetration (matches the report)
        traj = {"s": np.asarray(self._s), "dv": np.asarray(self._dv), "v": v, "a_ego": a,
                "collided": self._collided, "min_gap": min_gap, "impact_dv": self._impact_dv}
        out = {"n_ticks": n, "duration_s": round(n * DT, 2), "collided": self._collided}
        sm = safety_metrics(traj); cm = comfort_metrics(traj)               # REUSED validated formulas
        for k in ("min_gap", "min_ttc", "brake_margin_min", "max_DRAC", "TET", "TIT", "impact_dv",
                  "TED_drac", "TID_drac"):
            out[k] = round(sm[k], 3) if np.isfinite(sm[k]) else sm[k]
        for k in ("rms_accel", "max_decel", "rms_jerk", "frac_decel_iso_viol", "frac_accel_iso_viol"):
            out[k] = round(cm[k], 3)
        params = np.asarray(self._params)                                  # (T, 5)
        rel = []
        for i, name in enumerate(_PARAM_NAMES):
            base = self._gt[i] if self._gt is not None else params[:, i].mean()
            rmse = float(np.sqrt(np.mean((params[:, i] - base) ** 2)))
            out[f"param_rmse_{name}"] = round(rmse, 4)
            if self._gt is not None and abs(self._gt[i]) > 1e-9:
                r = rmse / abs(self._gt[i])
                out[f"param_rel_{name}"] = round(r, 4)   # per-param relative error (the id bars read this, no re-derive)
                rel.append(r)
            else:
                out[f"param_rel_{name}"] = None
        out["id_accuracy"] = (round(100.0 * max(0.0, 1.0 - (np.mean(rel) if rel else 1.0)), 1)
                              if self._gt is not None else None)
        out["mean_firing_pct"] = round(self._sum_fire / n * 100, 2)
        out["peak_firing_pct"] = round(self._peak_fire * 100, 2)
        out["dead_pct"] = round(float(np.mean(~self._fired)) * 100, 1) if self._fired is not None else 0.0
        out["max_spikes_tick"] = int(self._max_spk)
        out["rho"] = round(self._rho, 3) if self._rho is not None else None
        # energy UNROUNDED (breakdown sums EXACTLY to snn_pj == the direct metrics.synops path); display rounds
        out["e_fc"] = self._e_fc * E_AC_PJ; out["e_recV"] = self._e_recV * E_AC_PJ
        out["e_recU"] = self._e_recU * E_AC_PJ; out["e_out"] = self._e_out * E_AC_PJ
        out["snn_pj"] = out["e_fc"] + out["e_recV"] + out["e_recU"] + out["e_out"]
        out["ann_pj"] = float(n * ann_mac(self._dims[0], self._dims[1], self._dims[2]) * E_MAC_PJ)
        out["advantage"] = round(out["ann_pj"] / out["snn_pj"], 2) if out["snn_pj"] > 0 else 0.0
        return out

    def rows(self):
        return list(self._rows)


def write_episode_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        w.writerows(rows)
