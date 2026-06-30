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
                                    tracking_metrics, build_scenarios, TTC_STAR,
                                    _equilibrium_init, simulate_platoon,
                                    platoon_string_metrics, transfer_gain_fft)
from config import DT

PN = ['v0', 'T', 's0', 'a', 'b']
BRAKING_SCEN = {'hard_brake', 'panic_stop', 'cut_out', 'static_target'}   # scenari di arresto (braking-distance)


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


def _brake_dist(tr):
    """Spazio percorso dall'ego fino al quasi-arresto (v<0.5) o intera traiettoria [m]."""
    v = tr['v']
    below = np.where(v < 0.5)[0]
    end = int(below[0]) if below.size else len(v)
    return float(np.sum(v[:end]) * DT)


def _paired_rollout(tr_o, tr_s, name):
    """T1.10/T1.11 — confronto SNN-vs-oracolo sulla STESSA scena (rollout, non teacher-forcing):
    RMSE/MAE dell'accel + errore di spazio di frenata sugli scenari di arresto. Le traiettorie
    DIVERGONO (stati diversi) -> e' un RMSE su rollout, da interpretare come errore accumulato."""
    a_o = np.asarray(tr_o['a_ego']); a_s = np.asarray(tr_s['a_ego'])
    m = min(len(a_o), len(a_s))
    if m == 0:
        return None
    d = a_s[:m] - a_o[:m]
    out = {'scenario': name, 'rmse_accel': float(np.sqrt(np.mean(d ** 2))),
           'mae_accel': float(np.mean(np.abs(d)))}
    if name in BRAKING_SCEN:
        out['braking_dist_err'] = float(_brake_dist(tr_s) - _brake_dist(tr_o))
    return out


def _agg_rich(rec_full, id_intra, paired=None):
    """Aggregazione RICCA additiva: distribuzioni per metrica, Wilson sul collision, per-scenario +
    worst-case, Δ SNN-oracolo (appaiato) con CI bootstrap, intra_std, rollout RMSE/braking-dist."""
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

    # T1.10/T1.11 — rollout SNN-vs-oracolo: RMSE/MAE accel + errore spazio di frenata (per scenario di arresto)
    if paired:
        out['rollout'] = {'rmse_accel': _summarize([p['rmse_accel'] for p in paired]),
                          'mae_accel': _summarize([p['mae_accel'] for p in paired])}
        bd_scen = sorted(set(p['scenario'] for p in paired if 'braking_dist_err' in p))
        out['rollout']['braking_dist_err'] = {
            sc: _summarize([p['braking_dist_err'] for p in paired
                            if p['scenario'] == sc and 'braking_dist_err' in p]) for sc in bd_scen}
    return out


def eval_safety(model, cache, n_drivers=20, seq_len=50, device='cpu', rich=False, n_seeds=1, tail=False,
                plant=None, channel=None):
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
    paired = []                                     # rollout SNN-vs-oracolo per (driver,scenario) (solo rich)
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
            for name, vl, s_i, v_i, cut in build_scenarios(true_pg, N=400, rng=rng, include_tail=tail):
                trs = {}
                for key, ctrl in [('oracle', true_pg), ('snn', id_pg)]:
                    tr = simulate(None, ctrl, vl, s_i, v_i, cut_in=cut, device=device,
                                  plant=plant, channel=channel)
                    trs[key] = tr
                    sm = safety_metrics(tr); cm = comfort_metrics(tr)
                    rec[key].append((int(sm['collided']), sm['min_gap'], cm['max_decel'], cm['rms_jerk']))
                    if rich:
                        extra = {'aoi_mean': tr['aoi_mean']} if 'aoi_mean' in tr else {}
                        rec_full[key].append({**sm, **cm, **tracking_metrics(tr), **extra, 'scenario': name})
                if rich:
                    pr = _paired_rollout(trs['oracle'], trs['snn'], name)
                    if pr:
                        paired.append(pr)
    out = {k: _agg(v) for k, v in rec.items()}
    out['id_abs_err'] = {p: float(np.mean(id_err[p])) for p in PN}
    if rich:
        out['rich'] = _agg_rich(rec_full, id_intra, paired)
    return out


def make_ood_cache(n_drivers=20, profile='launch', beyond=1.2, seed=0, edge=True):
    """T1.5 — cache OoD: driver con i 5 param OLTRE/ai bordi di _PHYS_BOUNDS, finestre dal generatore.
    Si da' in pasto a eval_safety: eval_safety(model, make_ood_cache(...), rich=True, tail=True).
    beyond>1 estende il range (1.2 = +20% per lato); edge=True biasa verso i bordi estremi."""
    from data.generator import simulate_trajectory, _PHYS_BOUNDS, normalize
    from config import WARMUP_DURATION
    rng = np.random.default_rng(seed)
    warm = int(WARMUP_DURATION / DT)
    floors = {'v0': 3.0, 'T': 0.2, 's0': 0.3, 'a': 0.1, 'b': 0.2}   # clip difensivo (positivita' fisica)
    val = []
    for _ in range(n_drivers):
        p = {'delta': 4.0}
        for k, (lo, hi) in _PHYS_BOUNDS.items():
            ext = (beyond - 1.0) * (hi - lo) / 2.0
            lo2, hi2 = lo - ext, hi + ext
            if edge and rng.random() < 0.5:
                p[k] = float(lo2 if rng.random() < 0.5 else hi2)
            else:
                p[k] = float(rng.uniform(lo2, hi2))
            p[k] = max(p[k], floors[k])
        traj = simulate_trajectory(p, profile=profile, seed=int(rng.integers(0, 2 ** 31)), noise_scale=1.0)
        x, _y, _m = normalize(traj[warm:])
        val.append({'x': x, 'params': p})
    return {'val': val}


def breakdown_curve(model, cache, n_drivers=15, seq_len=50, device='cpu',
                    decels=(5.0, 6.0, 7.0, 8.0, 9.0, 10.0), gaps=(8.0, 6.0, 5.0, 4.0, 3.0, 2.0)):
    """T1.6 — CURVA DI ROTTURA: sweep di severita' (decel del leader, gap di cut-in) -> collision_rate
    ORACOLO vs SNN. Risponde: a quale severita' il sistema inizia a collidere, e se SNN collassa PRIMA
    dell'oracolo (margine consumato dall'identificazione)."""
    N = 400
    ids = []
    for it in cache['val'][:n_drivers]:
        true_pg = np.array([it['params'][k] for k in PN], dtype=np.float32)
        x = torch.tensor(it['x'][:seq_len][None], dtype=torch.float32).to(device)
        ids.append((true_pg, identify(model, x)))

    def _rate(make_leader, sev):
        c = {'oracle': 0, 'snn': 0}
        for true_pg, id_pg in ids:
            vl, s_i, v_i, cut = make_leader(true_pg, sev)
            for key, ctrl in (('oracle', true_pg), ('snn', id_pg)):
                tr = simulate(None, ctrl, vl, s_i, v_i, cut_in=cut, device=device)
                c[key] += int(tr['collided'])
        n = len(ids)
        return c['oracle'] / n, c['snn'] / n

    def _panic(true_pg, decel):
        v_set = 0.7 * float(true_pg[0])
        vl = np.full(N, v_set); bs = N // 3
        for i in range(bs, N):
            vl[i] = max(0.0, vl[i - 1] - decel * DT)
        s_i, v_i = _equilibrium_init(true_pg, v_set)
        return vl, s_i, v_i, None

    def _cutin(true_pg, gap):
        v0 = float(true_pg[0]); v_set = 0.7 * v0
        vl = np.full(N, v_set); t_cut = N // 2; vl[t_cut:] = 0.30 * v0
        s_i, v_i = _equilibrium_init(true_pg, v_set)
        return vl, s_i, v_i, (t_cut, float(gap))

    panic = [dict(zip(('decel', 'oracle', 'snn'), (d,) + _rate(_panic, d))) for d in decels]
    cutin = [dict(zip(('gap', 'oracle', 'snn'), (g,) + _rate(_cutin, g))) for g in gaps]
    return {'panic': panic, 'cut_in': cutin, 'n_drivers': len(ids)}


def eval_string_stability(model, cache, N=8, n_platoons=5, seq_len=50, hetero=True,
                          amp=1.0, f0=0.01, f1=0.3, latency_steps=0, device='cpu', perturb_len=600):
    """T3 — string stability del PLOTONE coi parametri identificati dalla SNN.

    Identifica i 5 param da piu' driver, costruisce plotoni di N follower (omogenei = stesso param;
    hetero=True = param diversi per veicolo, robustezza realistica), con un leader a CHIRP (swept-sine,
    banda f0..f1) -> una sola simulazione copre la banda. Misura: head-to-tail gain (std coda/testa),
    strict string stability (A_i/A_{i-1}<=1 ovunque), peak |Γ(ω)| (criterio <=1), e mappa il T medio
    identificato. latency_steps>0 inietta la latenza CAM NEL plotone (T3.6): la comunicazione ritardata
    riduce il margine di string stability."""
    ids = []
    for it in cache['val'][:max(n_platoons * N, n_platoons)]:
        x = torch.tensor(it['x'][:seq_len][None], dtype=torch.float32).to(device)
        ids.append(identify(model, x))
    if not ids:
        return {}
    t = np.arange(perturb_len)
    f_inst = f0 + (f1 - f0) * t / perturb_len            # chirp lineare f0->f1
    phase = 2.0 * np.pi * np.cumsum(f_inst) * DT
    v_set = 0.7 * float(ids[0][0])
    leader = v_set + amp * np.sin(phase)
    channel = {'latency_steps': int(latency_steps), 'seed': 0} if latency_steps else None
    rng = np.random.default_rng(0)
    results = []
    for p in range(n_platoons):
        if hetero:
            plist = [ids[int(j)] for j in rng.integers(0, len(ids), N)]
        else:
            plist = [ids[p % len(ids)]] * N
        pl = simulate_platoon(plist, leader, device=device, channel=channel)
        m = platoon_string_metrics(pl['v_profiles'])
        tg = transfer_gain_fft(pl['v_profiles'][0], pl['v_profiles'][-1], band=(f0, f1))
        m['peak_gain'] = tg['peak_gain']; m['peak_freq'] = tg['peak_freq']
        m['any_collision'] = bool(any(pl['collided']))
        m['mean_T'] = float(np.mean([pv[1] for pv in plist]))    # T3.7 — T identificato medio
        results.append(m)
    h2t = [r['head_to_tail'] for r in results]
    pk = [r['peak_gain'] for r in results if r['peak_gain'] == r['peak_gain']]
    return {'N': N, 'n_platoons': len(results), 'hetero': hetero, 'latency_steps': int(latency_steps),
            'head_to_tail_mean': float(np.mean(h2t)), 'head_to_tail_ci95': _bootstrap_ci(h2t),
            'peak_gain_mean': float(np.mean(pk)) if pk else float('nan'),
            'peak_gain_max': float(np.max(pk)) if pk else float('nan'),
            'frac_strict_stable': float(np.mean([r['strict_string_stable'] for r in results])),
            'frac_collision': float(np.mean([r['any_collision'] for r in results])),
            'mean_T': float(np.mean([r['mean_T'] for r in results])), 'platoons': results}


def reachability_frontier(model, cache, n_drivers=10, seq_len=50,
                          gaps=(5.0, 8.0, 12.0, 18.0, 25.0, 35.0, 50.0), dvs=(0.0, 5.0, 10.0, 15.0),
                          worst_decel=9.0, device='cpu'):
    """T4.7 — sicurezza WORST-CASE (Monte-Carlo avversario): per ogni (gap0, dv0) iniziale il leader frena
    alla decel massima ammissibile; l'ego coi param SNN collide? Ritorna la FRONTIERA = gap minimo SENZA
    collisione per ogni dv0 (e la differenza SNN vs oracolo = margine consumato dall'identificazione)."""
    ids = []
    for it in cache['val'][:n_drivers]:
        true_pg = np.array([it['params'][k] for k in PN], dtype=np.float32)
        x = torch.tensor(it['x'][:seq_len][None], dtype=torch.float32).to(device)
        ids.append((true_pg, identify(model, x)))
    N = 400

    def _collides(ctrl, gap0, dv0):
        v0 = 0.7 * float(ctrl[0]); v_lead0 = max(v0 - dv0, 0.0)
        vl = np.full(N, v_lead0); bs = N // 5
        for i in range(bs, N):
            vl[i] = max(0.0, vl[i - 1] - worst_decel * DT)
        return simulate(None, ctrl, vl, float(gap0), v0, device=device)['collided']

    out = {'worst_decel': worst_decel, 'min_safe_gap': {}}
    for key in ('oracle', 'snn'):
        out['min_safe_gap'][key] = {}
        for dv0 in dvs:
            mins = []
            for true_pg, id_pg in ids:
                ctrl = true_pg if key == 'oracle' else id_pg
                mg = next((g for g in sorted(gaps) if not _collides(ctrl, g, dv0)), max(gaps) + 10.0)
                mins.append(mg)
            out['min_safe_gap'][key][float(dv0)] = float(np.mean(mins))
    return out


def cbr_to_pdr(density, cbr_max=0.6):
    """T2.16 — proxy DCC: densita' veicolare -> Channel Busy Ratio -> PDR (piu' densita' = piu' CBR = meno PDR).
    Mapping lineare semplice (raffinabile con modelli ETSI DCC / SAE J2945). density in veic/km circa."""
    cbr = min(cbr_max, 0.02 * float(density))
    return max(0.3, 1.0 - cbr)


def v2x_robustness_sweep(model, cache, n_drivers=15, device='cpu',
                         pdrs=(1.0, 0.9, 0.7, 0.5), latencies=(0, 1, 2, 3)):
    """T2.12 — sweep robustezza V2X in closed-loop: per ogni PDR e per ogni latenza (in step DT),
    misura collision_rate (SNN) e p5 di min_TTC -> degrado graceful vs catastrofico (knee-point).
    Riusa eval_safety(channel=...). Usa scenari di coda (tail=True) per stressare i margini."""
    rows = []
    for pdr in pdrs:
        r = eval_safety(model, cache, n_drivers=n_drivers, device=device, rich=True, tail=True,
                        channel={'pdr': float(pdr), 'seed': 0})
        rows.append({'axis': 'pdr', 'val': float(pdr),
                     'collision_rate': r['snn']['collision_rate'],
                     'min_ttc_p5': r['rich']['snn']['min_ttc']['p5'],
                     'aoi': None})
    for lat in latencies:
        r = eval_safety(model, cache, n_drivers=n_drivers, device=device, rich=True, tail=True,
                        channel={'latency_steps': int(lat), 'seed': 0})
        rows.append({'axis': 'latency', 'val': int(lat),
                     'collision_rate': r['snn']['collision_rate'],
                     'min_ttc_p5': r['rich']['snn']['min_ttc']['p5'],
                     'aoi': None})
    return rows


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
