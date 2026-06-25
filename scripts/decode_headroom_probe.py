"""Probe: c'e' headroom per un decode ADATTIVO per-regime? (Idea 1 chiarita, upper-bound oracolo)

Carica un modello decode-ON allenato, estrae il raw pre-sigmoid per ogni finestra val, e confronta
l'NRMSE per-canale con:
  (A) decode GLOBALE (offset/tau del modello)                       <- baseline (= training_log)
  (B) decode rifittato PER-SCENARIO (oracolo, fit=eval)             <- upper bound, regime noto
  (C) decode rifittato PER-|accel|-quartile (oracolo, fit=eval)     <- upper bound, stat OSSERVABILE
  (D) decode rifittato PER-|accel|-quartile, SPLIT fit50/eval50     <- stima REALIZZABILE + leakage

Se B/C abbattono l'NRMSE -> headroom esiste -> vale costruire il modulatore FiLM.
Se ~nullo -> idea non paga, risparmiata la fatica. (D) dice quanto sopravvive fuori dal fit.
Nessuna modifica d'architettura, nessun retraining, nessun push.
"""
import sys
import os
sys.path.insert(0, os.getcwd())
import json
import numpy as np
import torch

from core.network import build_model

CKPT = 'checkpoints/CAP_h32_r16/best_model.pt'
CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'
SEQ_LEN = 50
PARAM_NAMES = ['v0', 'T', 's0', 'a', 'b']
# gt per canale: v0/s0/a/b costanti (params_gt col 0/1/2/3), T per-timestep (y[:,:,1])
GT_FROM_PGT = {'v0': 0, 's0': 1, 'a': 2, 'b': 3}

torch.manual_seed(0)


def load_model():
    m = build_model('eventprop_alif_full', hidden_size=32, rank=16, max_delay=6, bit_shift=3)
    ck = torch.load(CKPT, map_location='cpu', weights_only=False)
    m.load_state_dict(ck['model_state'])
    m.eval()
    return m


def window_val():
    """Finestre val (seq_len/stride 50) con scenario + nuisance |accel| medio per finestra."""
    cache = torch.load(CACHE, map_location='cpu', weights_only=False)
    X, Y, MASK, PGT, SCEN, NUIS = [], [], [], [], [], []
    for item in cache['val']:
        x, y, mask = item['x'], item['y'], item['mask']
        pd = item.get('params', {})
        pgt = np.array([pd.get('v0', 0.0), pd.get('s0', 0.0), pd.get('a', 0.0), pd.get('b', 0.0)],
                       dtype=np.float32)
        scen = item.get('scenario', 'NA')
        N = x.shape[0]
        s = 0
        while s + SEQ_LEN <= N:
            xw = x[s:s + SEQ_LEN]; yw = y[s:s + SEQ_LEN]; mw = mask[s:s + SEQ_LEN]
            X.append(xw); Y.append(yw); MASK.append(mw); PGT.append(pgt); SCEN.append(scen)
            NUIS.append(float(np.mean(np.abs(yw[:, 0]))))   # |v_dot| medio = stat di regime
            s += SEQ_LEN
    return (torch.tensor(np.array(X), dtype=torch.float32),
            torch.tensor(np.array(Y), dtype=torch.float32),
            torch.tensor(np.array(MASK), dtype=torch.float32),
            torch.tensor(np.array(PGT), dtype=torch.float32),
            np.array(SCEN), np.array(NUIS))


@torch.no_grad()
def extract_raw(model, X, batch=512):
    """raw pre-sigmoid (N,T,5). La variante EventProp chiama _decode_params UNA volta su
    raw.reshape(B*T,5) (ordine B-major) -> il raw catturato e' (B*T,5), rimodellato a (B,T,5)."""
    T = X.size(1)
    orig = model._decode_params
    outs = []
    for i in range(0, X.size(0), batch):
        buf = []
        model._decode_params = lambda raw, _b=buf: (_b.append(raw.detach().clone()), orig(raw))[1]
        model.forward_sequence_with_stats(X[i:i + batch])
        model._decode_params = orig
        b = X[i:i + batch].size(0)
        flat = torch.cat(buf, dim=0)              # (b*T, 5) (1 chiamata vettorizzata)
        outs.append(flat.reshape(b, T, flat.size(-1)))
    return torch.cat(outs, dim=0)


def gt_matrix(name, Y, PGT, N, T):
    """gt (N,T) per il canale."""
    if name == 'T':
        return Y[:, :, 1]
    return PGT[:, GT_FROM_PGT[name]].unsqueeze(1).expand(N, T)


def decode(raw_ch, lo, hi, off, tau):
    return lo + (hi - lo) * torch.sigmoid((raw_ch - off) / tau)


def nrmse(pred, gt, m, rng):
    se = (m * (pred - gt) ** 2).sum()
    n = m.sum().clamp(min=1)
    return float(torch.sqrt(se / n) / (rng + 1e-12))


def fit_offtau(raw_ch, gt, m, lo, hi, off0, tau0, steps=500):
    """Rifitta (off,tau) per minimizzare MSE(decode(raw),gt) sui punti pesati da m."""
    off = torch.tensor(float(off0), requires_grad=True)
    logtau = torch.tensor(float(np.log(max(tau0, 1e-3))), requires_grad=True)
    opt = torch.optim.Adam([off, logtau], lr=0.05)
    for _ in range(steps):
        opt.zero_grad()
        pred = decode(raw_ch, lo, hi, off, torch.exp(logtau))
        loss = (m * (pred - gt) ** 2).sum() / m.sum().clamp(min=1)
        loss.backward(); opt.step()
    return off.detach(), torch.exp(logtau).detach()


def main():
    model = load_model()
    X, Y, MASK, PGT, SCEN, NUIS = window_val()
    N, T = X.size(0), X.size(1)
    print('finestre val:', N, '| scenari:', {s: int((SCEN == s).sum()) for s in sorted(set(SCEN))})
    raw = extract_raw(model, X)   # (N,T,5)
    lo = model.param_lo; hi = model.param_hi
    off_g = model.decode_offset; tau_g = model.logit_tau
    rng = (hi - lo)

    # bins
    scen_bins = {s: np.where(SCEN == s)[0] for s in sorted(set(SCEN))}
    q = np.quantile(NUIS, [0.25, 0.5, 0.75])
    acc_lab = np.digitize(NUIS, q)   # 0..3
    acc_bins = {('|a|q' + str(k)): np.where(acc_lab == k)[0] for k in range(4)}
    rng2 = np.random.RandomState(0)

    res = {k: {} for k in ['A_global', 'B_scenario', 'C_accq', 'D_accq_split']}
    for ci, name in enumerate(PARAM_NAMES):
        rc = raw[:, :, ci]; gt = gt_matrix(name, Y, PGT, N, T)
        m = MASK if name == 'T' else torch.ones(N, T)
        L, H, O, Tau, R = lo[ci], hi[ci], off_g[ci], tau_g[ci], rng[ci]

        # A global
        res['A_global'][name] = nrmse(decode(rc, L, H, O, Tau), gt, m, R)

        # B per-scenario oracolo (fit=eval su tutto il bin)
        pred_b = decode(rc, L, H, O, Tau).clone()
        for s, idx in scen_bins.items():
            ii = torch.tensor(idx)
            o, t = fit_offtau(rc[ii], gt[ii], m[ii], L, H, O.item(), Tau.item())
            pred_b[ii] = decode(rc[ii], L, H, o, t)
        res['B_scenario'][name] = nrmse(pred_b, gt, m, R)

        # C per-|accel|-quartile oracolo (fit=eval)
        pred_c = decode(rc, L, H, O, Tau).clone()
        for s, idx in acc_bins.items():
            ii = torch.tensor(idx)
            o, t = fit_offtau(rc[ii], gt[ii], m[ii], L, H, O.item(), Tau.item())
            pred_c[ii] = decode(rc[ii], L, H, o, t)
        res['C_accq'][name] = nrmse(pred_c, gt, m, R)

        # D per-|accel|-quartile SPLIT (fit 50% / eval 50%) -> realizzabile + leakage
        pred_d = decode(rc, L, H, O, Tau).clone()
        eval_mask = torch.zeros(N, T)
        for s, idx in acc_bins.items():
            perm = rng2.permutation(idx)
            half = len(perm) // 2
            fit_i = torch.tensor(perm[:half]); ev_i = torch.tensor(perm[half:])
            o, t = fit_offtau(rc[fit_i], gt[fit_i], m[fit_i], L, H, O.item(), Tau.item())
            pred_d[ev_i] = decode(rc[ev_i], L, H, o, t)
            eval_mask[ev_i] = 1.0
        res['D_accq_split'][name] = nrmse(pred_d, gt, (m * eval_mask), R)

    # report
    print()
    hdr = 'canale     ' + ''.join('%14s' % k for k in res)
    print(hdr); print('-' * len(hdr))
    for name in PARAM_NAMES:
        print('%-10s' % name + ''.join('%14.4f' % res[k][name] for k in res))
    print('-' * len(hdr))
    print('%-10s' % 'MEDIA' + ''.join('%14.4f' % np.mean([res[k][n] for n in PARAM_NAMES]) for k in res))
    print()
    g = np.mean([res['A_global'][n] for n in PARAM_NAMES])
    for k in ['B_scenario', 'C_accq', 'D_accq_split']:
        mk = np.mean([res[k][n] for n in PARAM_NAMES])
        print('%s: NRMSE medio %.4f  (delta vs globale %.4f = %.1f%%)'
              % (k, mk, mk - g, 100 * (mk - g) / g))


if __name__ == '__main__':
    main()
