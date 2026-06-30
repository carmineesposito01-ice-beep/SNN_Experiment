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

from utils.closed_loop_eval import (simulate, safety_metrics, comfort_metrics,
                                    tracking_metrics, build_scenarios, TTC_STAR)

PN = ['v0', 'T', 's0', 'a', 'b']


@torch.no_grad()
def identify(model, x_win):
    """Parametri identificati (5,) = media su T di forward_sequence su una finestra (1,T,4)."""
    ps = model.forward_sequence(x_win)            # (1, T, 5)
    return ps[0].mean(dim=0).cpu().numpy().astype(np.float32)


def _agg(records):
    """Aggregazione LEGACY (4 medie). INVARIATA — la leggono lo Stadio-2 ckpt-pass e il notebook BS3."""
    arr = np.array(records, dtype=np.float64)
    return {'collision_rate': float(arr[:, 0].mean()), 'mean_min_gap': float(arr[:, 1].mean()),
            'mean_max_decel': float(arr[:, 2].mean()), 'mean_rms_jerk': float(arr[:, 3].mean()),
            'n': int(len(arr))}


# ----------------------------------------------------------------------------
# T0 — helper statistici (distribuzioni / CI / Wilson) per l'aggregazione RICCA
# ----------------------------------------------------------------------------
def _summarize(vals):
    """mean/std/percentili/min/max su valori (ignora i non-finiti, es. TTC=inf su no-closing)."""
    arr = np.asarray(vals, dtype=np.float64)
    fin = arr[np.isfinite(arr)]
    if fin.size == 0:
        return {'mean': float('nan'), 'std': float('nan'), 'p5': float('nan'), 'p50': float('nan'),
                'p95': float('nan'), 'p99': float('nan'), 'min': float('nan'), 'max': float('nan'),
                'n': int(arr.size), 'n_finite': 0}
    return {'mean': float(fin.mean()), 'std': float(fin.std()),
            'p5': float(np.percentile(fin, 5)), 'p50': float(np.percentile(fin, 50)),
            'p95': float(np.percentile(fin, 95)), 'p99': float(np.percentile(fin, 99)),
            'min': float(fin.min()), 'max': float(fin.max()),
            'n': int(arr.size), 'n_finite': int(fin.size)}


def _wilson_ub(k, n, z=1.96):
    """Upper bound 95% (Wilson) della proporzione: il rischio di collisione onesto anche con 0 osservate."""
    if n == 0:
        return float('nan')
    p = k / n
    denom = 1.0 + z * z / n
    centre = p + z * z / (2.0 * n)
    margin = z * np.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return float((centre + margin) / denom)


def _bootstrap_ci(vals, n_boot=2000, seed=0):
    """CI 95% bootstrap della media (per il Δ SNN-oracolo = test di non-inferiorita')."""
    a = np.asarray([v for v in vals if np.isfinite(v)], dtype=np.float64)
    if a.size < 2:
        return [float('nan'), float('nan')]
    rng = np.random.default_rng(seed)
    means = a[rng.integers(0, a.size, size=(n_boot, a.size))].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def _numeric_keys(records):
    keys = set()
    for r in records:
        keys.update(k for k, v in r.items() if isinstance(v, (int, float)) and not isinstance(v, bool))
    return sorted(keys)


def _agg_rich(rec_full, id_intra):
    """Aggregazione RICCA additiva: distribuzioni per metrica, Wilson sul collision, per-scenario +
    worst-case, Δ SNN-oracolo (appaiato) con CI bootstrap, intra_std dell'identificazione."""
    metrics = _numeric_keys(rec_full['oracle'] + rec_full['snn'])
    out = {}
    for key in ('oracle', 'snn'):
        recs = rec_full[key]
        d = {m: _summarize([r.get(m, float('nan')) for r in recs]) for m in metrics}
        k = sum(1 for r in recs if r.get('collided'))
        d['collision'] = {'rate': (k / len(recs)) if recs else float('nan'),
                          'wilson_ub95': _wilson_ub(k, len(recs)), 'n_collided': int(k), 'n': len(recs)}
        out[key] = d

    # T0.5 — per-scenario + worst-case (no media trasversale che annacqua lo scenario critico)
    SCEN_METRICS = ['min_gap', 'min_ttc', 'max_DRAC', 'max_decel', 'rms_jerk', 'rms_gap_error']
    scen = sorted(set(r.get('scenario', 'NA') for r in rec_full['snn']))
    per = {}
    for sc in scen:
        per[sc] = {}
        for key in ('oracle', 'snn'):
            sub = [r for r in rec_full[key] if r.get('scenario') == sc]
            per[sc][key] = {m: _summarize([r.get(m, float('nan')) for r in sub]) for m in SCEN_METRICS}
            per[sc][key]['collision_rate'] = (float(np.mean([bool(r.get('collided')) for r in sub]))
                                              if sub else float('nan'))
    out['per_scenario'] = per
    out['worst_case_snn'] = {
        'min_ttc_p5': min((per[sc]['snn']['min_ttc']['p5'] for sc in scen), default=float('nan')),
        'min_gap': min((per[sc]['snn']['min_gap']['min'] for sc in scen), default=float('nan')),
        'max_DRAC_p95': max((per[sc]['snn']['max_DRAC']['p95'] for sc in scen), default=float('nan')),
        'max_collision_rate': max((per[sc]['snn']['collision_rate'] for sc in scen), default=float('nan')),
    }

    # T0.4/T0.7 — Δ SNN-oracolo appaiato (per indice = stesso driver/scenario) + CI bootstrap
    delta = {}
    n_pair = min(len(rec_full['oracle']), len(rec_full['snn']))
    for m in metrics:
        o = np.array([rec_full['oracle'][i].get(m, np.nan) for i in range(n_pair)], dtype=np.float64)
        s = np.array([rec_full['snn'][i].get(m, np.nan) for i in range(n_pair)], dtype=np.float64)
        d = s - o
        delta[m] = {'mean': float(np.nanmean(d)) if np.isfinite(d).any() else float('nan'),
                    'ci95': _bootstrap_ci(d)}
    out['delta_snn_minus_oracle'] = delta

    # T0.8 — intra_std dell'identificazione (std su T di forward_sequence): alto = stima instabile
    out['intra_std'] = {p: (float(np.mean(id_intra[p])) if id_intra[p] else float('nan')) for p in PN}
    out['ttc_star'] = TTC_STAR
    return out


def eval_safety(model, cache, n_drivers=20, seq_len=50, device='cpu', rich=False, n_seeds=1):
    """Sicurezza closed-loop: ORACOLO (param veri) vs SNN (param identificati), su scenari avversari.

    Per ogni driver: identifica i param dalla prima finestra, costruisce gli scenari avversari (coi param
    VERI), e guida l'IDM con param-veri (oracolo) e param-identificati (snn). Aggrega collisioni/min-gap/
    decel/jerk. Ritorna anche l'errore di identificazione medio per-canale.

    Backward-compat: con rich=False, n_seeds=1 (default) il percorso e il risultato sono IDENTICI alla
    versione precedente (chiavi legacy 'oracle'/'snn' a 4 metriche + 'id_abs_err'); lo Stadio-2 ckpt-pass
    e il notebook BS3 non cambiano. Con rich=True viene aggiunta la chiave 'rich' (T0): distribuzioni,
    Wilson, per-scenario+worst-case, Δ SNN-oracolo con CI, intra_std. n_seeds>1 (solo per CI) aggiunge
    realizzazioni rng degli scenari avversari.
    """
    rec = {'oracle': [], 'snn': []}
    rec_full = {'oracle': [], 'snn': []}            # dict completi per-traiettoria (solo rich)
    id_err = {p: [] for p in PN}
    id_intra = {p: [] for p in PN}                  # std su T dell'identificazione (solo rich)
    for seed in range(n_seeds):
        rng = np.random.default_rng(seed)           # seed=0 al primo giro => identico al legacy
        for it in cache['val'][:n_drivers]:
            pdct = it['params']
            true_pg = np.array([pdct[k] for k in PN], dtype=np.float32)
            x = torch.tensor(it['x'][:seq_len][None], dtype=torch.float32).to(device)
            id_pg = identify(model, x)
            if rich:
                with torch.no_grad():
                    id_sd = model.forward_sequence(x)[0].std(dim=0).cpu().numpy().astype(np.float32)
                for i, p in enumerate(PN):
                    id_intra[p].append(float(id_sd[i]))
            for i, p in enumerate(PN):
                id_err[p].append(abs(id_pg[i] - true_pg[i]))
            for name, vl, s_i, v_i, cut in build_scenarios(true_pg, N=400, rng=rng):
                for key, ctrl in [('oracle', true_pg), ('snn', id_pg)]:
                    tr = simulate(None, ctrl, vl, s_i, v_i, cut_in=cut, device=device)
                    sm = safety_metrics(tr); cm = comfort_metrics(tr)
                    rec[key].append((int(sm['collided']), sm['min_gap'], cm['max_decel'], cm['rms_jerk']))
                    if rich:
                        rec_full[key].append({**sm, **cm, **tracking_metrics(tr), 'scenario': name})
    out = {k: _agg(v) for k, v in rec.items()}
    out['id_abs_err'] = {p: float(np.mean(id_err[p])) for p in PN}
    if rich:
        out['rich'] = _agg_rich(rec_full, id_intra)
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
