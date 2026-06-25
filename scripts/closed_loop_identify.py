"""Closed-loop di SICUREZZA con i parametri IDENTIFICATI (funziona anche per EventProp).

Aggira il problema per-step di EventProp: invece di guidare l'ego passo-passo via forward_step
(sequence-only -> rompe), si IDENTIFICANO i 5 parametri da una finestra (mean su T di forward_sequence)
e si guida l'IDM con quei parametri COSTANTI. E' il modo corretto di valutare l'identificazione PER IL
CONTROLLO: identifica offline, poi controlla coi parametri stimati. Confronto vs ORACOLO (parametri veri).

Domanda chiave: se controlli con i parametri identificati dalla SNN, e' sicuro come coi veri?
Uso anche per confrontare decode globale vs refit: il refit migliora l'NRMSE ma il controllo e' piu' o
meno sicuro? Riutilizzato dalla sezione closed-loop del BigSweep3.
"""
import sys
import os
sys.path.insert(0, os.getcwd())
import numpy as np
import torch

from utils.closed_loop_eval import simulate, safety_metrics, comfort_metrics, build_scenarios

PN = ['v0', 'T', 's0', 'a', 'b']


@torch.no_grad()
def identify(model, x_win):
    """Parametri identificati (5,) = media su T di forward_sequence su una finestra (1,T,4)."""
    ps = model.forward_sequence(x_win)            # (1, T, 5)
    return ps[0].mean(dim=0).cpu().numpy().astype(np.float32)


def _agg(records):
    arr = np.array(records, dtype=np.float64)
    return {'collision_rate': float(arr[:, 0].mean()), 'mean_min_gap': float(arr[:, 1].mean()),
            'mean_max_decel': float(arr[:, 2].mean()), 'mean_rms_jerk': float(arr[:, 3].mean()),
            'n': int(len(arr))}


def eval_safety(model, cache, n_drivers=20, seq_len=50, device='cpu'):
    """Sicurezza closed-loop: ORACOLO (param veri) vs SNN (param identificati), su scenari avversari.

    Per ogni driver: identifica i param dalla prima finestra, costruisce gli scenari avversari (coi param
    VERI), e guida l'IDM con param-veri (oracolo) e param-identificati (snn). Aggrega collisioni/min-gap/
    decel/jerk. Ritorna anche l'errore di identificazione medio per-canale.
    """
    rng = np.random.default_rng(0)
    rec = {'oracle': [], 'snn': []}
    id_err = {p: [] for p in PN}
    for it in cache['val'][:n_drivers]:
        pdct = it['params']
        true_pg = np.array([pdct[k] for k in PN], dtype=np.float32)
        x = torch.tensor(it['x'][:seq_len][None], dtype=torch.float32).to(device)
        id_pg = identify(model, x)
        for i, p in enumerate(PN):
            id_err[p].append(abs(id_pg[i] - true_pg[i]))
        for name, vl, s_i, v_i, cut in build_scenarios(true_pg, N=400, rng=rng):
            for key, ctrl in [('oracle', true_pg), ('snn', id_pg)]:
                tr = simulate(None, ctrl, vl, s_i, v_i, cut_in=cut, device=device)
                sm = safety_metrics(tr); cm = comfort_metrics(tr)
                rec[key].append((int(sm['collided']), sm['min_gap'], cm['max_decel'], cm['rms_jerk']))
    out = {k: _agg(v) for k, v in rec.items()}
    out['id_abs_err'] = {p: float(np.mean(id_err[p])) for p in PN}
    return out


if __name__ == '__main__':
    from scripts.decode_lut_calibrate import load_model
    ckpt_dir = sys.argv[1]
    rank = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    cache = torch.load('data/cache_1500_launch_cut0.0_ou0.0.pt', map_location='cpu', weights_only=False)
    model = load_model(os.path.join(ckpt_dir, 'best_model.pt'), rank)
    r = eval_safety(model, cache, n_drivers=15)
    print('=== closed-loop sicurezza (oracolo vs SNN-identificato) ===')
    for k in ['oracle', 'snn']:
        d = r[k]
        print('%-8s collision_rate=%.3f  min_gap=%.2f  max_decel=%.2f  jerk=%.2f  (%d sim)'
              % (k, d['collision_rate'], d['mean_min_gap'], d['mean_max_decel'], d['mean_rms_jerk'], d['n']))
    print('errore identificazione |Δ| medio:', {p: round(r['id_abs_err'][p], 3) for p in PN})
