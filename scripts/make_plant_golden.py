"""Genera plant_golden.mat: riferimento del plant ACC-IIDM (Python, deterministico).

Usato per validare il blocco Simulink ACC_IIDM: stessa formula (core.network.acc_iidm_accel),
stessa stima a_l (OU) e integrazione balistica, senza rumore di percezione. Per ogni caso:
`params` (5), profilo leader `v_l` (N,), e le traiettorie di riferimento `ref_s/ref_v/ref_a`.
"""
import os
import sys
import numpy as np
import torch
from scipy.io import savemat

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from core.network import CF_FSNN_Net    # acc_iidm_accel e' staticmethod

DT = 0.1
ACC_AL_TAU = 1.0
NORM_S_MAX = 150.0
COOLNESS = 0.99


def _accel(s, v, dv, a_l, params):
    # float64 -> parita' pulita col blocco MATLAB (double), indipendente dalla precisione
    p = torch.tensor([[float(x) for x in params]], dtype=torch.float64)
    out = CF_FSNN_Net.acc_iidm_accel(
        torch.tensor([s], dtype=torch.float64), torch.tensor([v], dtype=torch.float64),
        torch.tensor([dv], dtype=torch.float64), torch.tensor([a_l], dtype=torch.float64),
        p, coolness=COOLNESS)
    return float(out[0])


def clean_plant(params, v_l):
    """Plant ACC-IIDM deterministico. params=[v0,T,s0,a,b]; v_l=(N,). -> s,v,a (N,)."""
    v0, T, s0, a, b = [float(x) for x in params]
    N = len(v_l)
    alpha = np.exp(-DT / ACC_AL_TAU)
    v = 0.8 * v0
    s = s0 + v * T
    a_l_filt = 0.0
    vl_prev = float(v_l[0])
    S, V, A = np.zeros(N), np.zeros(N), np.zeros(N)
    for i in range(N):
        vl = float(v_l[i])
        a_l_filt = alpha * a_l_filt + (1.0 - alpha) * ((vl - vl_prev) / DT)
        vl_prev = vl
        dv = v - vl
        accel = _accel(s, v, dv, a_l_filt, params)
        v_old = v
        v = float(np.clip(v + accel * DT, 0.0, 1.2 * v0))
        s = float(np.clip(s + (vl - v_old) * DT, 0.5 * s0, NORM_S_MAX))
        S[i], V[i], A[i] = s, v, accel
    return S, V, A


def _leader(kind, N):
    t = np.arange(N) * DT
    if kind == "sinusoidal":
        return 22.0 + 4.0 * np.sin(2 * np.pi * 0.02 * t)
    if kind == "brake_step":
        vl = np.full(N, 20.0); vl[t >= 20] = 12.0; vl[t >= 40] = 18.0; return vl
    if kind == "constant":
        return np.full(N, 20.0)
    raise ValueError(kind)


CASES = [
    ("highway_sinus", [30.0, 1.5, 2.5, 1.0, 1.5], "sinusoidal"),
    ("urban_brake",   [15.0, 1.0, 2.0, 1.2, 2.0], "brake_step"),
    ("cruise_const",  [25.0, 1.2, 3.0, 0.8, 1.3], "constant"),
]
N = 600   # 60 s


def build(out_path):
    cases = []
    for name, params, lk in CASES:
        v_l = _leader(lk, N)
        s, v, a = clean_plant(params, v_l)
        print(f"{name:14s} params={params}  s[-1]={s[-1]:.2f} v[-1]={v[-1]:.2f}")
        cases.append({"name": name, "params": np.array(params), "leader_kind": lk,
                      "v_l": v_l, "ref_s": s, "ref_v": v, "ref_a": a, "dt": DT})
    savemat(out_path, {"cases": cases}, format="5", oned_as="column", do_compression=True)
    print(f"Wrote {out_path} ({len(cases)} casi, N={N})")


if __name__ == "__main__":
    build(os.path.join(REPO, "matlab", "plant_golden.mat"))
