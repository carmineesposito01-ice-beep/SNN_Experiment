"""Path B — Calibra una LUT di decode per-|accel|-bin (fittata sui PARAMETRI), Simulink-friendly.

Calibrazione POST-training, disaccoppiata dal core (non tocca rete/training):
  1. carica un checkpoint decode-ON allenato (decode globale);
  2. fitta per-bin di |accel| una coppia (offset[5], tau[5]) che MINIMIZZA l'NRMSE sui parametri,
     usando SOLO le finestre di TRAIN;
  3. valuta su VAL (traiettorie DISGIUNTE da train) -> generalizzazione vera, zero leakage;
  4. ottimizza n_bins (1=refit globale, 4, 8, 16);
  5. salva la LUT auto-descrittiva (bordi + tabelle + iperparametri + formula) in JSON.

La LUT e' un blocco 1-D Lookup Table nativo in Simulink (+ decode sigmoid) e LUT+bit-shift su FPGA.
Uso: python scripts/decode_lut_calibrate.py [CKPT] [RANK]. Default ADEC_OFF_12 rank16. NO push.
"""
import sys
import os
sys.path.insert(0, os.getcwd())
import json
import numpy as np
import torch

from core.network import build_model
from scripts.decode_headroom_probe import extract_raw, decode, nrmse, fit_offtau

CKPT = sys.argv[1] if len(sys.argv) > 1 else 'checkpoints/ADEC_OFF_12/best_model.pt'
RANK = int(sys.argv[2]) if len(sys.argv) > 2 else 16
CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'
SEQ_LEN = 50
FIT_CAP = 8000   # finestre train max per il fit (2 param/canale/bin -> bastano)
PARAM_NAMES = ['v0', 'T', 's0', 'a', 'b']
GT_FROM_PGT = {'v0': 0, 's0': 1, 'a': 2, 'b': 3}
N_BINS_GRID = [1, 4, 8, 16]
torch.manual_seed(0)
_RNG = np.random.RandomState(0)


def load_model(ckpt, rank):
    m = build_model('eventprop_alif_full', hidden_size=32, rank=rank, max_delay=6, bit_shift=3)
    ck = torch.load(ckpt, map_location='cpu', weights_only=False)
    # strict=False: tollera chiavi extra (es. learnable_decode/adaptive_decode). Il refit
    # sovrascrive comunque offset/tau, quindi il floor dipende solo dal raw del core.
    m.load_state_dict(ck['model_state'], strict=False)
    m.eval()
    return m


def window_items(items, cap=None):
    """Finestre (seq_len/stride 50) con params_gt + nuisance |accel| (= |Δ velocita' ego|, osservabile)."""
    X, Y, MASK, PGT, NUIS = [], [], [], [], []
    for it in items:
        x, y, mask = it['x'], it['y'], it['mask']
        pd = it.get('params', {})
        pgt = np.array([pd.get('v0', 0.0), pd.get('s0', 0.0), pd.get('a', 0.0), pd.get('b', 0.0)],
                       dtype=np.float32)
        N = x.shape[0]
        s = 0
        while s + SEQ_LEN <= N:
            xw = x[s:s + SEQ_LEN]
            ego = xw[:, 1]                                   # velocita' ego (canale 1)
            NUIS.append(float(np.mean(np.abs(np.diff(ego)))))   # |accel| medio osservabile
            X.append(xw); Y.append(y[s:s + SEQ_LEN]); MASK.append(mask[s:s + SEQ_LEN]); PGT.append(pgt)
            s += SEQ_LEN
    X = np.array(X); Y = np.array(Y); MASK = np.array(MASK); PGT = np.array(PGT); NUIS = np.array(NUIS)
    if cap is not None and len(X) > cap:
        idx = _RNG.choice(len(X), cap, replace=False)
        X, Y, MASK, PGT, NUIS = X[idx], Y[idx], MASK[idx], PGT[idx], NUIS[idx]
    return (torch.tensor(X, dtype=torch.float32), torch.tensor(Y, dtype=torch.float32),
            torch.tensor(MASK, dtype=torch.float32), torch.tensor(PGT, dtype=torch.float32), NUIS)


def gt_mat(name, Y, PGT, N, T):
    if name == 'T':
        return Y[:, :, 1]
    return PGT[:, GT_FROM_PGT[name]].unsqueeze(1).expand(N, T)


def bin_edges(nuis, n_bins):
    if n_bins <= 1:
        return np.array([])
    qs = [k / n_bins for k in range(1, n_bins)]
    return np.quantile(nuis, qs)


def main():
    model = load_model(CKPT, RANK)
    cache = torch.load(CACHE, map_location='cpu', weights_only=False)
    Xtr, Ytr, Mtr, Ptr, Ntr = window_items(cache['train'], cap=FIT_CAP)
    Xva, Yva, Mva, Pva, Nva = window_items(cache['val'])
    print('fit(train) finestre:', Xtr.size(0), '| eval(val) finestre:', Xva.size(0))
    raw_tr = extract_raw(model, Xtr)
    raw_va = extract_raw(model, Xva)
    lo, hi = model.param_lo, model.param_hi
    off_g, tau_g = model.decode_offset, model.logit_tau
    rng = hi - lo
    Ntr_t, Nva_t = Ntr, Nva

    # NRMSE globale (decode allenato del modello) su VAL = baseline
    base = {}
    for ci, nm in enumerate(PARAM_NAMES):
        gt = gt_mat(nm, Yva, Pva, Xva.size(0), Xva.size(1))
        m = Mva if nm == 'T' else torch.ones_like(gt)
        base[nm] = nrmse(decode(raw_va[:, :, ci], lo[ci], hi[ci], off_g[ci], tau_g[ci]), gt, m, rng[ci])
    base_mean = float(np.mean([base[n] for n in PARAM_NAMES]))
    print('\nGLOBALE (val): ' + '  '.join('%s=%.4f' % (n, base[n]) for n in PARAM_NAMES)
          + '  | MEDIA=%.4f' % base_mean)

    best = None
    for n_bins in N_BINS_GRID:
        edges = bin_edges(Ntr, n_bins)
        btr = np.digitize(Ntr, edges)
        bva = np.digitize(Nva, edges)
        lut_off = np.zeros((n_bins, 5), dtype=np.float32)
        lut_tau = np.ones((n_bins, 5), dtype=np.float32)
        res = {}
        for ci, nm in enumerate(PARAM_NAMES):
            gtr = gt_mat(nm, Ytr, Ptr, Xtr.size(0), Xtr.size(1))
            gva = gt_mat(nm, Yva, Pva, Xva.size(0), Xva.size(1))
            mtr = Mtr if nm == 'T' else torch.ones_like(gtr)
            mva = Mva if nm == 'T' else torch.ones_like(gva)
            pred_va = decode(raw_va[:, :, ci], lo[ci], hi[ci], off_g[ci], tau_g[ci]).clone()
            for b in range(n_bins):
                itr = torch.tensor(np.where(btr == b)[0])
                iva = torch.tensor(np.where(bva == b)[0])
                if len(itr) < 20:                      # bin troppo magro -> tieni globale
                    o, t = off_g[ci].clone(), tau_g[ci].clone()
                else:
                    o, t = fit_offtau(raw_tr[itr][:, :, ci], gtr[itr], mtr[itr],
                                      lo[ci], hi[ci], off_g[ci].item(), tau_g[ci].item())
                lut_off[b, ci] = float(o); lut_tau[b, ci] = float(t)
                if len(iva) > 0:
                    pred_va[iva] = decode(raw_va[iva][:, :, ci], lo[ci], hi[ci], o, t)
            res[nm] = nrmse(pred_va, gva, mva, rng[ci])
        mean = float(np.mean([res[n] for n in PARAM_NAMES]))
        tag = 'n_bins=%2d' % n_bins
        print('%s (val): ' % tag + '  '.join('%s=%.4f' % (n, res[n]) for n in PARAM_NAMES)
              + '  | MEDIA=%.4f (%+.1f%% vs globale)' % (mean, 100 * (mean - base_mean) / base_mean))
        if best is None or mean < best['mean']:
            best = {'n_bins': n_bins, 'mean': mean, 'edges': edges.tolist(),
                    'lut_off': lut_off.tolist(), 'lut_tau': lut_tau.tolist(), 'per_ch': res}

    # Salva LUT auto-descrittiva (primo pezzo dell'exporter Simulink)
    art = {
        'kind': 'decode_lut_per_accel_bin',
        'source_checkpoint': CKPT,
        'n_bins': best['n_bins'],
        'bin_edges_accel': best['edges'],          # bordi su |accel|=mean|Δ ego_speed| (input normalizzato)
        'nuisance_feature': 'mean(abs(diff(x[:,1])))  # |accel| medio = |Δ velocita ego|',
        'decode_formula': 'param = lo + (hi-lo)*sigmoid((raw - offset)/tau)',
        'lut_offset': best['lut_off'],             # (n_bins, 5) per [v0,T,s0,a,b]
        'lut_tau': best['lut_tau'],                # (n_bins, 5)
        'param_names': PARAM_NAMES,
        'param_lo': lo.tolist(), 'param_hi': hi.tolist(),
        'global_offset': off_g.tolist(), 'global_tau': tau_g.tolist(),
        'arch': {'hidden_size': model.hidden_size, 'rank': model.rank,
                 'max_delay': model.max_delay, 'n_ticks': model.n_ticks,
                 'alpha_m': 0.875, 'alpha_f': 0.875, 'po2': True, 'bit_shift': 3},
        'val_nrmse_global': base, 'val_nrmse_lut': best['per_ch'],
        'val_nrmse_mean_global': base_mean, 'val_nrmse_mean_lut': best['mean'],
    }
    out = 'results/decode_lut_%s.json' % os.path.basename(os.path.dirname(CKPT))
    os.makedirs('results', exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(art, f, indent=2)
    print('\nMigliore: n_bins=%d  MEDIA=%.4f (%+.1f%% vs globale)  -> %s'
          % (best['n_bins'], best['mean'], 100 * (best['mean'] - base_mean) / base_mean, out))


if __name__ == '__main__':
    main()
