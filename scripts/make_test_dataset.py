"""Genera test_dataset.mat: dataset di test VASTO e held-out per validare i blocchi.

Held-out: base_seed = SEED+777, diverso da train/val/test (SEED/+1/+2) -> traiettorie
mai viste in training, stessa distribuzione fisica (quindi valutativo). Copre tutti gli
scenari (highway/urban/truck/mixed/freeflow/launch) e profili (constant/sinusoidal/
stop_and_go/free/launch) + cut-in. Struttura tipo 100m.mat: ogni traiettoria ha `val`
(4 x N) con righe [s;v;dv;v_l] + gt_params + ref_params (riferimento Python per-champion).

Il riferimento Python e' calcolato BATCHATO: un solo forward_sequence per champion su
tutte le traiettorie (dim batch), non uno per traiettoria.
"""
import os
import sys
from collections import Counter

import numpy as np
import torch
from scipy.io import savemat

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from config import SEED
from data.generator import generate_dataset
from scripts.export_champions import normalize, CHAMPIONS
from utils.champion_io import load_champion

CHANNELS = ["s", "v", "dv", "v_l"]
CHAMP_ORDER = ["Donatello", "Michelangelo", "Raffaello", "Leonardo"]
MIX = {"highway": 0.25, "urban": 0.20, "truck": 0.15,
       "mixed": 0.15, "freeflow": 0.15, "launch": 0.10}     # somma 1.0, tutti i tipi
CUT_IN = 0.30
N_TRAJ = 60
BASE_SEED = SEED + 777                                      # held-out


def build(out_path):
    data = generate_dataset(N_TRAJ, base_seed=BASE_SEED, scenario_mix=MIX, cut_in_ratio=CUT_IN)
    models = {n: load_champion(os.path.join(REPO, "champions", CHAMPIONS[n], "best_model.pt")).model
              for n in CHAMP_ORDER}

    raws = [np.asarray(d["raw"], dtype=np.float64) for d in data]
    Ns = {r.shape[0] for r in raws}
    assert len(Ns) == 1, f"traiettorie di lunghezza diversa: {Ns}"
    N = raws[0].shape[0]

    # riferimento Python BATCHATO: 1 forward per champion su tutte le traiettorie
    xn = np.stack([normalize(r[:, 0:4]) for r in raws])          # (B, N, 4)
    xt = torch.tensor(xn, dtype=torch.float32)
    ref_all = {}
    for n in CHAMP_ORDER:
        with torch.no_grad():
            y = models[n].forward_sequence(xt).cpu().numpy()     # (B, N, 5)
        ref_all[n] = y[:, N // 2:, :].mean(axis=1)               # (B, 5)

    trajs = []
    cov_s, cov_p, n_cut = Counter(), Counter(), 0
    v0err_exc, v0err_con = [], []
    for k, d in enumerate(data):
        gt = np.array([d["params"][q] for q in ("v0", "T", "s0", "a", "b")])
        ref = np.stack([ref_all[n][k] for n in CHAMP_ORDER])     # (4, 5)
        cov_s[d["scenario"]] += 1; cov_p[d["profile"]] += 1; n_cut += int(d["cut_in"])
        v0e = float(np.mean(np.abs(ref[:, 0] - gt[0])))
        (v0err_exc if d["scenario"] in ("freeflow", "launch") else v0err_con).append(v0e)
        trajs.append({
            "name": f"{k+1:02d}_{d['scenario']}" + ("_cutin" if d["cut_in"] else ""),
            "scenario": d["scenario"], "profile": d["profile"], "cut_in": bool(d["cut_in"]),
            "val": raws[k][:, 0:4].T, "channels": CHANNELS, "dt": 0.1,
            "gt_params": gt, "ref_params": ref, "champion_order": CHAMP_ORDER,
        })

    savemat(out_path, {"trajectories": trajs}, format="5", oned_as="column", do_compression=True)
    me = np.mean(v0err_exc) if v0err_exc else float("nan")
    mc = np.mean(v0err_con) if v0err_con else float("nan")
    print(f"\nWrote {out_path}: {len(trajs)} traiettorie, N={N}, dt=0.1s")
    print(f"  scenari : {dict(cov_s)}")
    print(f"  profili : {dict(cov_p)}")
    print(f"  cut-in  : {n_cut}/{len(trajs)}")
    print(f"  |v0_id - v0_gt| medio: ECCITATI(freeflow/launch)={me:.2f}  VINCOLATI(altri)={mc:.2f}")


if __name__ == "__main__":
    build(os.path.join(REPO, "matlab", "test_dataset.mat"))
