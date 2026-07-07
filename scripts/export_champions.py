"""Esporta i 4 champion in champions_export.mat per la libreria Simulink (fase 2).

Per ogni champion: pesi po2 (via la vera PowerOf2Quantize) + delays (esplicito!) +
soglie + leak_div + readout + decode + costanti di normalizzazione + GOLDEN
(input fisici, input normalizzati, output PyTorch dei 5 parametri).
"""
import os
import numpy as np
import torch
from scipy.io import savemat

from utils.champion_io import load_champion
from core.hardware import po2_quantize

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# nome blocco -> dir champion (document/SIMULINK_IMPORT_DESIGN.md §0)
CHAMPIONS = {
    "Donatello":    "PE_t05_gp0002",
    "Michelangelo": "A_lr1e2_t06_r16",
    "Raffaello":    "R33_C2_A1_T12_fix",
    "Leonardo":     "LS3_PEAK_R0_launch_d03",
}

# normalizzazione (config.py:110-113)
NORM = dict(S=150.0, V=40.0, DV=20.0, VL=40.0)
PHYS_LO = np.array([0.0, 0.0, -20.0, 0.0])      # range fisici plausibili di [s, v, dv, v_l]
PHYS_HI = np.array([150.0, 40.0, 20.0, 40.0])


def _np(t):
    return t.detach().cpu().numpy().astype(np.float64)


def _readout_key(sd):
    return "layer_out.weight" if "layer_out.weight" in sd else "layer_out.fc_weight"


def _thr_keys(sd):
    if "layer_hidden.base_threshold" in sd:      # eventprop (flat)
        return "layer_hidden.base_threshold", "layer_hidden.thresh_jump"
    return "layer_hidden.cell.base_threshold", "layer_hidden.cell.thresh_jump"


def normalize(x_phys):
    """x_phys (N,4) fisico -> (N,4) normalizzato [0,1]. Identico a data/generator.py."""
    s, v, dv, vl = x_phys[:, 0], x_phys[:, 1], x_phys[:, 2], x_phys[:, 3]
    return np.stack([
        s / NORM["S"],
        v / NORM["V"],
        (np.clip(dv, -NORM["DV"], NORM["DV"]) + NORM["DV"]) / (2 * NORM["DV"]),
        vl / NORM["VL"],
    ], axis=1)


def _leak_div(sd, hidden):
    for k in ("layer_hidden.cell.leak_div", "layer_hidden.leak_div"):
        if k in sd:
            return _np(sd[k]).reshape(-1)[:hidden]
    return np.full(hidden, 8.0)   # default 2^bit_shift, bit_shift=3


def export_champion(name, folder, n_test=16, seed=0):
    path = os.path.join(REPO, "champions", folder, "best_model.pt")
    h = load_champion(path)
    sd = h.model.state_dict()
    bufs = dict(h.model.named_buffers())
    hidden, rank = h.topology["hidden"], h.topology["rank"]
    rk = _readout_key(sd)
    thr_k, tj_k = _thr_keys(sd)

    # pesi po2 (applica la vera quantizzazione una volta)
    with torch.no_grad():
        fc = _np(po2_quantize(sd["layer_hidden.fc_weight"]))
        U = _np(po2_quantize(sd["layer_hidden.rec_U"]))
        V = _np(po2_quantize(sd["layer_hidden.rec_V"]))
        Wout = _np(po2_quantize(sd[rk]))

    # golden: input fisico deterministico -> normalizza -> forward PyTorch
    rng = np.random.default_rng(seed)
    x_phys = rng.uniform(PHYS_LO, PHYS_HI, size=(n_test, 4))
    x_norm = normalize(x_phys)
    with torch.no_grad():
        xt = torch.tensor(x_norm, dtype=torch.float32).unsqueeze(0)          # (1, N, 4)
        y = h.model.forward_sequence(xt)[0].cpu().numpy().astype(np.float64)  # (N, 5)

    def buf(key, default):
        return _np(bufs[key]) if key in bufs else default

    return {
        "name": name, "variant": h.variant,
        "hidden": np.int32(hidden), "rank": np.int32(rank),
        "n_ticks": np.int32(10), "max_delay": np.int32(6),
        "fc_weight": fc, "rec_U": U, "rec_V": V, "readout": Wout,
        "delays": _np(sd["layer_hidden.delays"]).astype(np.float64),
        "base_threshold": _np(sd[thr_k]).reshape(-1),
        "thresh_jump": _np(sd[tj_k]).reshape(-1),
        "leak_div": _leak_div(sd, hidden),
        "param_lo": buf("param_lo", np.array([8, 0.5, 1.0, 0.3, 0.5])),
        "param_hi": buf("param_hi", np.array([45, 2.5, 5.0, 2.5, 3.0])),
        "decode_offset": buf("decode_offset", np.zeros(5)),
        "logit_tau": buf("logit_tau", np.ones(5)),
        "norm": np.array([NORM["S"], NORM["V"], NORM["DV"], NORM["VL"]]),
        "x_phys": x_phys, "x_norm": x_norm, "y_params": y,
    }


def export_all(out_path, n_test=16, seed=0):
    champs = [export_champion(n, f, n_test, seed) for n, f in CHAMPIONS.items()]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    savemat(out_path, {"champions": champs}, format="5", oned_as="column", do_compression=True)
    return out_path


if __name__ == "__main__":
    p = export_all(os.path.join(REPO, "matlab", "champions_export.mat"))
    print(f"Wrote {p}")
