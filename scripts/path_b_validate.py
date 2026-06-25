"""Validazione Path B sul set COMPLETO di metriche (non solo NRMSE).

Per un checkpoint allenato, confronta decode GLOBALE vs REFIT-ai-parametri (n_bins=1) su:
  - i 5 componenti del PINN loss (data, phys, ou, bc, sr) via val_epoch  -> il refit preserva la fisica?
  - NRMSE per-canale (la lente del goal)
  - CLOSED-LOOP (simulate + safety/comfort): collisioni, min-gap, max-decel, jerk -> e' sicuro?

Il refit si applica sovrascrivendo decode_offset/logit_tau (i buffer) -> val_epoch E simulate lo usano
in automatico (forward_step -> _decode_params legge i buffer). Path B si ADOTTA solo se migliora l'NRMSE
SENZA degradare loss-fisica e closed-loop. Uso: python scripts/path_b_validate.py CKPT_DIR [RANK]. NO push.
"""
import sys
import os
sys.path.insert(0, os.getcwd())
import copy
import numpy as np
import torch
from torch.utils.data import DataLoader

from train import CFDataset, val_epoch
from utils.closed_loop_eval import simulate, safety_metrics, comfort_metrics, build_scenarios
from scripts.decode_headroom_probe import extract_raw, fit_offtau
from scripts.decode_lut_calibrate import load_model, window_items, gt_mat

CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'
LAM = (1.0, 0.1, 0.05, 1.0, 0.5)   # data, phys, ou, bc, sr (come nei sweep)
PARAM_NAMES = ['v0', 'T', 's0', 'a', 'b']
FIT_CAP = 8000
N_CL_DRIVERS = 12   # set di parametri-veri distinti su cui costruire scenari closed-loop


def fit_global_refit(model, cache, device):
    """Fitta (offset,tau) GLOBALI minimizzando l'NRMSE sui parametri (train) e li scrive nei buffer."""
    Xtr, Ytr, Mtr, Ptr, _ = window_items(cache['train'], cap=FIT_CAP)
    raw = extract_raw(model, Xtr)
    lo, hi = model.param_lo, model.param_hi
    for ci, nm in enumerate(PARAM_NAMES):
        gt = gt_mat(nm, Ytr, Ptr, Xtr.size(0), Xtr.size(1))
        m = Mtr if nm == 'T' else torch.ones_like(gt)
        o, t = fit_offtau(raw[:, :, ci], gt, m, lo[ci], hi[ci],
                          model.decode_offset[ci].item(), model.logit_tau[ci].item())
        with torch.no_grad():
            model.decode_offset[ci] = o
            model.logit_tau[ci] = t


def eval_full(model, val_loader, cache, device):
    """val_epoch (loss completa + NRMSE) + closed-loop aggregato."""
    with torch.no_grad():
        avg = val_epoch(model, val_loader, device, LAM)
    comps = {k: float(avg.get(k, float('nan'))) for k in ['total', 'data', 'phys', 'ou', 'bc', 'sr']}
    nrmse = {n: float(avg.get('val_%s_nrmse' % n, float('nan'))) for n in PARAM_NAMES}
    nrmse_mean = float(np.nanmean([nrmse[n] for n in PARAM_NAMES]))

    # closed-loop su N_CL_DRIVERS set di parametri veri (5 scenari avversari ciascuno).
    # NB: simulate() guida passo-passo via forward_step -> OK per baseline (per-step), FALLISCE per
    # EventProp (manual-forward sequence-only) -> in quel caso closed_loop=None (solo PINN+NRMSE).
    cl = None
    try:
        rng = np.random.default_rng(0)
        drivers = [it['params'] for it in cache['val'][:N_CL_DRIVERS]]
        n_coll = 0; n_tot = 0
        min_gaps = []; max_decels = []; rms_jerks = []
        for pd in drivers:
            pg = np.array([pd['v0'], pd['T'], pd['s0'], pd['a'], pd['b']], dtype=np.float32)
            for name, vl, s_i, v_i, cut in build_scenarios(pg, N=400, rng=rng):
                tr = simulate(model, pg, vl, s_i, v_i, cut_in=cut, device=device)
                sm = safety_metrics(tr); cm = comfort_metrics(tr)
                n_tot += 1; n_coll += int(sm['collided'])
                min_gaps.append(sm['min_gap']); max_decels.append(cm['max_decel']); rms_jerks.append(cm['rms_jerk'])
        cl = {'collision_rate': n_coll / max(n_tot, 1), 'mean_min_gap': float(np.mean(min_gaps)),
              'mean_max_decel': float(np.mean(max_decels)), 'mean_rms_jerk': float(np.mean(rms_jerks))}
    except Exception as e:
        cl = {'skipped': 'closed-loop non disponibile (modello sequence-only): ' + type(e).__name__}
    return {'comps': comps, 'nrmse': nrmse, 'nrmse_mean': nrmse_mean, 'closed_loop': cl}


def validate(ckpt_dir, rank, device='cpu'):
    ckpt = os.path.join(ckpt_dir, 'best_model.pt')
    cache = torch.load(CACHE, map_location='cpu', weights_only=False)
    val_ds = CFDataset(cache['val'], seq_len=50, stride=50)
    val_loader = DataLoader(val_ds, batch_size=32, shuffle=False)

    model = load_model(ckpt, rank).to(device)
    g = eval_full(model, val_loader, cache, device)        # GLOBALE
    fit_global_refit(model, cache, device)                 # applica refit ai buffer
    r = eval_full(model, val_loader, cache, device)        # REFIT
    return {'global': g, 'refit': r}


def _print(tag, res):
    g, r = res['global'], res['refit']
    print('\n===== %s =====' % tag)
    print('NRMSE medio: globale %.4f -> refit %.4f (%+.1f%%)'
          % (g['nrmse_mean'], r['nrmse_mean'], 100 * (r['nrmse_mean'] - g['nrmse_mean']) / g['nrmse_mean']))
    print('  per-canale refit:', {n: round(r['nrmse'][n], 3) for n in PARAM_NAMES})
    print('PINN loss (preservata?):')
    for k in ['total', 'data', 'phys', 'ou', 'bc', 'sr']:
        gv, rv = g['comps'][k], r['comps'][k]
        d = 100 * (rv - gv) / gv if gv not in (0.0,) and gv == gv else float('nan')
        print('  %-6s globale %.4f -> refit %.4f (%+.1f%%)' % (k, gv, rv, d))
    if isinstance(r['closed_loop'], dict) and 'skipped' in r['closed_loop']:
        print('CLOSED-LOOP: ' + r['closed_loop']['skipped'])
    else:
        print('CLOSED-LOOP (sicurezza):')
        for k in ['collision_rate', 'mean_min_gap', 'mean_max_decel', 'mean_rms_jerk']:
            print('  %-16s globale %.4f -> refit %.4f' % (k, g['closed_loop'][k], r['closed_loop'][k]))


if __name__ == '__main__':
    ckpt_dir = sys.argv[1]
    rank = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    res = validate(ckpt_dir, rank)
    _print(os.path.basename(ckpt_dir), res)
