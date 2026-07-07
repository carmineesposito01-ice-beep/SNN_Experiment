"""Genera test_trajectories.mat: traiettorie car-following per testare i blocchi Simulink.

Le traiettorie sono generate con `data.generator.generate_dataset` (la STESSA distribuzione
su cui i champion sono stati validati: scenari reali, warmup rimosso), non con parametri
scelti a mano (che sarebbero fuori distribuzione). Struttura ispirata a 100m.mat: ogni
traiettoria ha `val` (4 x N) con righe = canali [s; v; dv; v_l] e colonne = campioni.
In piu': ground-truth dei parametri ACC-IIDM + riferimento Python di cosa ogni champion
identifica (per validare l'output del blocco Simulink).
"""
import os
import sys
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


def _identify(model, x_phys):
    """Riferimento Python: media dei 5 parametri identificati sulla 2a meta' (regime)."""
    xn = normalize(x_phys.astype(np.float64))
    with torch.no_grad():
        xt = torch.tensor(xn, dtype=torch.float32).unsqueeze(0)      # (1, N, 4)
        y = model.forward_sequence(xt)[0].cpu().numpy()              # (N, 5)
    return y[len(y) // 2:].mean(axis=0)                              # (5,)


def _pick_diverse(data, n_keep):
    """Prima occorrenza di ogni scenario distinto, poi riempi fino a n_keep (per indice)."""
    idx, seen = [], set()
    for i, d in enumerate(data):
        if d["scenario"] not in seen:
            seen.add(d["scenario"]); idx.append(i)
    for i in range(len(data)):
        if len(idx) >= n_keep:
            break
        if i not in idx:
            idx.append(i)
    return [data[i] for i in idx[:n_keep]]


def build(out_path, n_pool=60, base_seed=SEED + 2, n_keep=6):
    data = generate_dataset(n_pool, base_seed=base_seed)     # test-split, in-distribution
    picked = _pick_diverse(data, n_keep)
    models = {n: load_champion(os.path.join(REPO, "champions", CHAMPIONS[n], "best_model.pt")).model
              for n in CHAMP_ORDER}

    trajs = []
    print(f"{'#':2s} {'scenario':11s} {'ground truth [v0,T,s0,a,b]':30s}")
    for k, d in enumerate(picked):
        raw = np.asarray(d["raw"], dtype=np.float64)         # (N, 7) fisica, warmup rimosso
        val = raw[:, 0:4].T                                  # (4, N): s, v, dv, v_l
        p = d["params"]
        gt = np.array([p["v0"], p["T"], p["s0"], p["a"], p["b"]])
        ref = np.stack([_identify(models[n], raw[:, 0:4]) for n in CHAMP_ORDER])  # (4, 5)
        print(f"{k+1:2d} {d['scenario']:11s} {str(np.round(gt,2)):30s}")
        for i, n in enumerate(CHAMP_ORDER):
            print(f"     {n:13s} -> {np.round(ref[i], 2)}")
        trajs.append({
            "name": f"{k+1:02d}_{d['scenario']}",
            "scenario": d["scenario"],
            "profile": d["profile"],
            "val": val,                       # (4 x N), righe [s;v;dv;v_l], come 100m.mat
            "channels": CHANNELS,
            "dt": 0.1,
            "gt_params": gt,                  # (5,) verita' che ha generato la traiettoria
            "ref_params": ref,                # (4 x 5) riferimento Python per-champion
            "champion_order": CHAMP_ORDER,
        })
    savemat(out_path, {"trajectories": trajs}, format="5", oned_as="column", do_compression=True)
    print(f"\nWrote {out_path}  ({len(trajs)} traiettorie, N={val.shape[1]} campioni, dt=0.1s)")


if __name__ == "__main__":
    build(os.path.join(REPO, "matlab", "test_trajectories.mat"))
