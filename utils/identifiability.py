"""utils/identifiability.py — Tier 4 (metodologia): identificabilita' pratica dei 5 param ACC-IIDM.

FIM/Jacobiano dell'accelerazione rispetto ai param -> spiega il paradosso ProdigyEvent (NRMSE bassa ma
fisica peggiore = param lungo una valle NON identificabile, I/O-equivalenti). Piu':
  - equifinality_set     : insiemi di param che danno la STESSA accel (entro eps) -> non distinguibili dall'NRMSE
  - persistent_excitation: FIM cumulata sugli scenari -> quali param NON sono eccitati (identificazione impossibile)
  - causal_sensitivity   : la rete alza T quando il leader e' incerto? (logica appresa vs overfitting)
  - nrmse_stratified     : NRMSE per-canale per scenario (l'NRMSE globale maschera i param non identificabili)
  - naturalisticity      : distribuzioni time-gap/jerk dell'ego-SNN vs driver reali (KS)

Riusa CF_FSNN_Net.acc_iidm_accel (vettorizzato) e simulate(); nessuna dipendenza dal training loop.
"""
import numpy as np
import torch

from config import (NORM_S_MAX, NORM_V_MAX, NORM_DV_MAX, NORM_VL_MAX, DT,
                    ACC_AL_TAU, ACC_COOLNESS)
from core.network import CF_FSNN_Net
from utils.closed_loop_eval import simulate

PN = ['v0', 'T', 's0', 'a', 'b']
_BOUNDS = {'v0': (8.0, 45.0), 'T': (0.5, 2.5), 's0': (1.0, 5.0), 'a': (0.3, 2.5), 'b': (0.5, 3.0)}


# ---------------------------------------------------------------------------
# Stati fisici + accelerazione/Jacobiano
# ---------------------------------------------------------------------------
def states_from_item(it):
    """Stati fisici (s,v,dv,vl,a_l) da un item cache: usa 'raw' se presente, altrimenti de-normalizza 'x'.
    a_l = stima OU dell'accel leader da vl (come simulate/generator)."""
    raw = it.get('raw')
    if raw is not None and np.asarray(raw).ndim == 2 and np.asarray(raw).shape[1] >= 4:
        raw = np.asarray(raw, dtype=np.float64)
        s, v, dv, vl = raw[:, 0], raw[:, 1], raw[:, 2], raw[:, 3]
    else:
        x = np.asarray(it['x'], dtype=np.float64)
        s = x[:, 0] * NORM_S_MAX; v = x[:, 1] * NORM_V_MAX
        dv = x[:, 2] * 2.0 * NORM_DV_MAX - NORM_DV_MAX; vl = x[:, 3] * NORM_VL_MAX
    alpha = np.exp(-DT / ACC_AL_TAU)
    a_l = np.zeros_like(vl); f = 0.0; prev = vl[0]
    for i in range(len(vl)):
        f = alpha * f + (1.0 - alpha) * ((vl[i] - prev) / DT); a_l[i] = f; prev = vl[i]
    return {'s': s, 'v': v, 'dv': dv, 'vl': vl, 'a_l': a_l}


def _accel_traj(states, params, coolness=ACC_COOLNESS):
    """Accel ACC-IIDM vettorizzata sulla traiettoria (T,) con params costanti (5,)."""
    T = len(states['s'])
    p = torch.tensor(np.asarray(params, dtype=np.float64), dtype=torch.float32).view(1, 5).expand(T, 5).contiguous()
    a = CF_FSNN_Net.acc_iidm_accel(
        torch.tensor(states['s'], dtype=torch.float32), torch.tensor(states['v'], dtype=torch.float32),
        torch.tensor(states['dv'], dtype=torch.float32), torch.tensor(states['a_l'], dtype=torch.float32),
        p, coolness=coolness)
    return a.detach().cpu().numpy().astype(np.float64)


def accel_jacobian(states, params, rel_eps=1e-2):
    """J[t,i] = d a_ego / d param_i (differenze centrate). Riusa _accel_traj (10 valutazioni)."""
    params = np.asarray(params, dtype=np.float64)
    T = len(states['s']); J = np.zeros((T, 5))
    for i in range(5):
        eps = rel_eps * max(abs(params[i]), 1e-3)
        pp = params.copy(); pp[i] += eps
        pm = params.copy(); pm[i] -= eps
        J[:, i] = (_accel_traj(states, pp) - _accel_traj(states, pm)) / (2.0 * eps)
    return J


def fisher_information(states, params, sigma=0.1):
    """FIM = JᵀJ/σ². Ritorna cond, autovalori/vettori, sensitivity per-param (||colonna J||) e direzione piatta."""
    J = accel_jacobian(states, params)
    F = J.T @ J / (sigma ** 2)
    w, V = np.linalg.eigh(F)
    w = np.maximum(w, 0.0)
    cond = float(w[-1] / max(w[0], 1e-12))
    sens = np.linalg.norm(J, axis=0)
    return {'fim': F, 'eigvals': w.tolist(), 'eigvecs': V, 'cond': cond,
            'sensitivity': dict(zip(PN, sens.tolist())),
            'flat_direction': dict(zip(PN, V[:, 0].tolist()))}


def practical_identifiability(cache, n=20, sigma=0.1):
    """T4.1 — identificabilita' pratica aggregata: cond(FIM) medio/p95 + sensitivity media per-param +
    il param meno identificabile. cond alto => valle quasi-piatta => param I/O-equivalenti (ProdigyEvent)."""
    conds = []; sens = {p: [] for p in PN}
    for it in cache['val'][:n]:
        st = states_from_item(it); pg = [it['params'][p] for p in PN]
        fi = fisher_information(st, pg, sigma)
        conds.append(fi['cond'])
        for p in PN:
            sens[p].append(fi['sensitivity'][p])
    smean = {p: float(np.mean(sens[p])) for p in PN}
    return {'cond_mean': float(np.mean(conds)), 'cond_p95': float(np.percentile(conds, 95)),
            'sensitivity_mean': smean, 'least_identifiable': min(PN, key=lambda p: smean[p]),
            'most_identifiable': max(PN, key=lambda p: smean[p]), 'n': len(conds)}


def equifinality_set(states, params, nrmse_eps=0.05, span=0.4, n=400, seed=0):
    """T4.2 — cammina lungo le 2 direzioni FIM piu' piatte e raccoglie i param che danno l'accel di
    riferimento entro nrmse_eps. La DISPERSIONE fisica di questo insieme = ambiguita' irriducibile dall'NRMSE."""
    params = np.asarray(params, dtype=np.float64)
    a_ref = _accel_traj(states, params); scale = a_ref.std() + 1e-6
    fi = fisher_information(states, params)
    flat = fi['eigvecs'][:, :2]              # 2 autovettori a minor autovalore
    rng = np.random.default_rng(seed)
    kept = [params.copy()]
    for _ in range(n):
        cand = params + (flat @ rng.normal(0.0, span, flat.shape[1])) * params
        cand = np.maximum(cand, 1e-2)
        if np.sqrt(np.mean((_accel_traj(states, cand) - a_ref) ** 2)) / scale <= nrmse_eps:
            kept.append(cand)
    K = np.array(kept)
    return {'n_equivalent': len(kept),
            'param_rel_spread': {p: float((K[:, i].max() - K[:, i].min()) / (abs(params[i]) + 1e-9))
                                 for i, p in enumerate(PN)}}


def persistent_excitation(cache, n=20, sigma=0.1):
    """T4.3 — FIM CUMULATA su n driver: rango (param recuperabili) + param sotto-eccitati (sensitivity ~0).
    Se un param non e' eccitato, l'identificazione e' strutturalmente impossibile a prescindere dalla rete."""
    Fsum = np.zeros((5, 5))
    for it in cache['val'][:n]:
        st = states_from_item(it); pg = [it['params'][p] for p in PN]
        J = accel_jacobian(st, pg); Fsum += J.T @ J / (sigma ** 2)
    w = np.maximum(np.linalg.eigvalsh(Fsum), 0.0)
    rank = int(np.sum(w > 1e-6 * max(w[-1], 1e-12)))
    sens = np.sqrt(np.maximum(np.diag(Fsum), 0.0))
    thr = 0.05 * max(sens.max(), 1e-12)
    return {'rank': rank, 'full_rank': rank == 5, 'eigvals': w.tolist(),
            'sensitivity': dict(zip(PN, sens.tolist())),
            'under_excited': [PN[i] for i in range(5) if sens[i] < thr]}


def _spearman(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    if len(a) < 3 or np.std(a) < 1e-9 or np.std(b) < 1e-9:
        return float('nan')
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def causal_sensitivity(model, cache, n=20, seq_len=50, device='cpu'):
    """T4.4 — la rete ha appreso una LOGICA? Corr (Spearman) tra feature dello stato-CAM
    (varianza di vl, |dv| medio, |a_l| medio) e param predetti (T, s0, b). Atteso var_vl->T > 0."""
    feats = {'var_vl': [], 'mean_absdv': [], 'mean_absal': []}
    preds = {'T': [], 's0': [], 'b': []}
    for it in cache['val'][:n]:
        st = states_from_item(it)
        x = torch.tensor(it['x'][:seq_len][None], dtype=torch.float32).to(device)
        with torch.no_grad():
            p = model.forward_sequence(x)[0].mean(0).cpu().numpy()
        feats['var_vl'].append(np.var(st['vl'][:seq_len]))
        feats['mean_absdv'].append(np.mean(np.abs(st['dv'][:seq_len])))
        feats['mean_absal'].append(np.mean(np.abs(st['a_l'][:seq_len])))
        preds['T'].append(p[1]); preds['s0'].append(p[2]); preds['b'].append(p[4])
    return {'%s->%s' % (f, q): _spearman(feats[f], preds[q]) for f in feats for q in preds}


def nrmse_stratified(model, cache, n=200, seq_len=50, device='cpu'):
    """T4.6 — NRMSE per-canale STRATIFICATO per scenario: l'NRMSE globale maschera i param non
    identificabili in certi regimi (es. v0 non eccitato in following stazionario)."""
    from collections import defaultdict
    pred = defaultdict(lambda: {p: [] for p in PN}); tru = defaultdict(lambda: {p: [] for p in PN})
    for it in cache['val'][:n]:
        sc = it.get('scenario', 'NA')
        x = torch.tensor(it['x'][:seq_len][None], dtype=torch.float32).to(device)
        with torch.no_grad():
            p = model.forward_sequence(x)[0].mean(0).cpu().numpy()
        for i, pn in enumerate(PN):
            pred[sc][pn].append(p[i]); tru[sc][pn].append(it['params'][pn])
    out = {}
    for sc in pred:
        out[sc] = {}
        for pn in PN:
            pr = np.array(pred[sc][pn]); tr = np.array(tru[sc][pn])
            rng = _BOUNDS[pn][1] - _BOUNDS[pn][0]
            out[sc][pn] = float(np.sqrt(np.mean((pr - tr) ** 2)) / rng)
    return out


def _ks(a, b):
    a = np.sort(np.asarray(a, float)); b = np.sort(np.asarray(b, float))
    if len(a) == 0 or len(b) == 0:
        return float('nan')
    grid = np.concatenate([a, b])
    ca = np.searchsorted(a, grid, side='right') / len(a)
    cb = np.searchsorted(b, grid, side='right') / len(b)
    return float(np.max(np.abs(ca - cb)))


def naturalisticity(model, cache, n=15, seq_len=50, device='cpu'):
    """T4.8 — quanto e' 'umano' l'ego-SNN: distanza KS tra le distribuzioni di time-gap e jerk dell'ego
    guidato coi param identificati (closed-loop sul leader reale) vs il driver REALE (cache raw)."""
    tg_snn, tg_real, jk_snn, jk_real = [], [], [], []
    for it in cache['val'][:n]:
        st = states_from_item(it)
        x = torch.tensor(it['x'][:seq_len][None], dtype=torch.float32).to(device)
        with torch.no_grad():
            id_pg = model.forward_sequence(x)[0].mean(0).cpu().numpy().astype(np.float32)
        v0 = float(st['v'][0])
        tr = simulate(None, id_pg, st['vl'], float(st['s'][0]), v0, device=device)
        v = tr['v']; s = tr['s']; a = tr['a_ego']
        tg_snn.extend((s[v > 0.1] / np.maximum(v[v > 0.1], 1e-3)).tolist())
        jk_snn.extend((np.diff(a) / DT).tolist())
        vr = st['v']; sr = st['s']
        tg_real.extend((sr[vr > 0.1] / np.maximum(vr[vr > 0.1], 1e-3)).tolist())
        jk_real.extend((np.diff(np.gradient(vr, DT)) / DT).tolist())
    return {'ks_time_gap': _ks(tg_snn, tg_real), 'ks_jerk': _ks(jk_snn, jk_real),
            'mean_time_gap_snn': float(np.mean(tg_snn)) if tg_snn else float('nan'),
            'mean_time_gap_real': float(np.mean(tg_real)) if tg_real else float('nan')}


def calibration_validation(model, cache, n=20, seq_len=50, device='cpu', floor=(0.08, 0.12)):
    """T4.5 — protocollo di calibrazione rigoroso (Treiber ch17): identifica i param sui PRIMI seq_len
    step, valida sull'HOLDOUT (resto della traiettoria) confrontando il GAP predetto (Measure-of-Performance
    PRIMARIA, non l'accel) vs osservato -> RMSPE del gap. Confronto col FLOOR intra-driver (8-12%): sotto
    il floor = 'identificazione al livello del rumore umano' (claim forte, non over-fit/over-claim)."""
    rmspe = []
    for it in cache['val'][:n]:
        st = states_from_item(it)
        if len(st['s']) <= seq_len + 10:
            continue
        x = torch.tensor(it['x'][:seq_len][None], dtype=torch.float32).to(device)
        with torch.no_grad():
            id_pg = model.forward_sequence(x)[0].mean(0).cpu().numpy().astype(np.float32)
        vl_hold = st['vl'][seq_len:]
        tr = simulate(None, id_pg, vl_hold, float(st['s'][seq_len]), float(st['v'][seq_len]), device=device)
        s_pred = tr['s']; s_obs = st['s'][seq_len:seq_len + len(s_pred)]
        m = int(min(len(s_pred), len(s_obs)))
        if m < 5:
            continue
        e = (s_pred[:m] - s_obs[:m]) / np.maximum(s_obs[:m], 1e-3)
        rmspe.append(float(np.sqrt(np.mean(e ** 2))))
    if not rmspe:
        return {}
    mean_rmspe = float(np.mean(rmspe))
    return {'gap_rmspe_mean': mean_rmspe, 'gap_rmspe_p95': float(np.percentile(rmspe, 95)),
            'floor_intra_driver': list(floor), 'within_floor': bool(mean_rmspe <= floor[1]), 'n': len(rmspe)}
