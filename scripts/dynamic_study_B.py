"""Dynamic_Study — STUDIO B: separa le cause del tetto su a/b (locale, niente Azure).

Idea: confrontare la rete con un OTTIMIZZATORE CLASSICO (Levenberg-Marquardt) che fitta i 5
parametri IDM ai dati, sotto condizioni progressivamente piu' vicine a quelle che la rete
affronta. Cosi' isoliamo *perche'* a/b sono difficili.

  B1  Sensitivita'/Fisher sul modello GT  -> dove (in quale regime) ogni parametro e' osservabile.
  B2  Recovery LM in 4 condizioni:
        rich_clean   = tutti gli scenari, dati puliti, fit GLOBALE   (limite superiore)
        follow_only  = solo following stazionario, pulito            (niente transitori)
        local_window = fit su finestre corte ~ contesto della rete   (identificazione LOCALE)
        rich_noisy   = tutti gli scenari + rumore V2X realistico      (noise floor)
      Metrica identica alla rete: NRMSE = RMSE/range (train.py:757).
  B3  Coordinate [a, sqrt(ab), a/b] nella condizione local_window -> se sqrt(ab) e' buono e
      a/b no, e' un problema di COORDINATE (riparametrizzazione).

Output: document/figures_dynamic/*.png + dynB_results.json; verdetto stampato.
Uso:  python scripts/dynamic_study_B.py
"""
import os
import sys
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.optimize import least_squares

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from utils.closed_loop_eval import simulate, build_scenarios          # noqa: E402
from data.generator import _acc_iidm_accel                            # noqa: E402
from config import (DT, ACC_AL_TAU, ACC_COOLNESS,                     # noqa: E402
                    NOISE_GAP_REL, NOISE_ACCEL, V2X_PACKET_LOSS)

FIGDIR = os.path.join(ROOT, 'document', 'figures_dynamic')
os.makedirs(FIGDIR, exist_ok=True)

PNAME = ['v0', 'T', 's0', 'a', 'b']
LO = np.array([8.0, 0.5, 1.0, 0.3, 0.5])
HI = np.array([45.0, 2.5, 5.0, 2.5, 3.0])
RNG = HI - LO
DELTA = 4
ALPHA_AL = float(np.exp(-DT / ACC_AL_TAU))
NET_NRMSE = {'v0': 0.224, 'T': 0.251, 's0': 0.133, 'a': 0.262, 'b': 0.305}
EASY = ['v0', 'T', 's0']
DYN = ['a', 'b']


def accel(state, theta):
    s, v, vl, a_l = state
    p = {'v0': theta[0], 'T': theta[1], 's0': theta[2],
         'a': theta[3], 'b': theta[4], 'delta': DELTA}
    return _acc_iidm_accel(float(s), float(v), float(vl), float(a_l), p, c=ACC_COOLNESS)


def recompute_al(vl):
    a_l = 0.0; prev = float(vl[0]); out = np.empty(len(vl))
    for i, x in enumerate(vl):
        raw = (float(x) - prev) / DT
        a_l = ALPHA_AL * a_l + (1.0 - ALPHA_AL) * raw
        prev = float(x); out[i] = a_l
    return out


def driver_dataset(pg, rng, N=260, only=None, noise=False):
    """Rollout oracolo -> arrays (S,V,VL,AL,AGT,REG). only=set(nomi scenario) o None=tutti+launch."""
    scen = build_scenarios(pg, N=N, rng=rng)
    v0 = float(pg[0]); v_set = 0.7 * v0
    scen.append(('launch', np.full(N, v_set), 80.0, 0.10 * v0, None))
    if only is not None:
        scen = [s for s in scen if s[0] in only]
    S, V, VL, AL, AGT, REG = [], [], [], [], [], []
    for name, vl, s_i, v_i, cut in scen:
        tr = simulate(None, pg, vl, s_i, v_i, cut_in=cut)
        al = recompute_al(tr['vl']); n = len(tr['s'])
        S.append(tr['s']); V.append(tr['v']); VL.append(tr['vl'])
        AL.append(al[:n]); AGT.append(tr['a_ego']); REG += [name] * n
    S, V, VL, AL, AGT = (np.concatenate(x) for x in (S, V, VL, AL, AGT))
    REG = np.array(REG)
    if noise:
        keep = rng.random(len(S)) > V2X_PACKET_LOSS         # packet loss V2X
        S, V, VL, AL, AGT, REG = (x[keep] for x in (S, V, VL, AL, AGT, REG))
        S = S * (1.0 + NOISE_GAP_REL * rng.standard_normal(len(S)))   # 10% errore gap
        AGT = AGT + NOISE_ACCEL * rng.standard_normal(len(S))         # 0.1 m/s2 su accel
    return S, V, VL, AL, AGT, REG


def fit_lm(S, V, VL, AL, AGT):
    def resid(theta):
        return np.array([accel((S[i], V[i], VL[i], AL[i]), theta) - AGT[i]
                         for i in range(len(S))])
    sol = least_squares(resid, 0.5 * (LO + HI), bounds=(LO, HI), method='trf',
                        xtol=1e-12, ftol=1e-12, max_nfev=400)
    return sol.x


# ---------------------------------------------------------------------------
# B1
# ---------------------------------------------------------------------------
def grad_accel(state, theta, rel=1e-3):
    g = np.zeros(5)
    for k in range(5):
        h = rel * RNG[k]
        tp = theta.copy(); tp[k] += h
        tm = theta.copy(); tm[k] -= h
        g[k] = (accel(state, tp) - accel(state, tm)) / (2.0 * h)
    return g * RNG


def fisher_cond(G):
    F = G.T @ G / len(G)
    ev, evec = np.linalg.eigh(F)
    return float(ev[-1] / max(ev[0], 1e-30)), evec[:, 0], ev


def run_B1(pg):
    rng = np.random.default_rng(1)
    S, V, VL, AL, AGT, REG = driver_dataset(pg, rng)
    G = np.array([grad_accel((S[i], V[i], VL[i], AL[i]), pg) for i in range(len(S))])
    dv = V - VL
    masks = {'free_accel': AGT > 0.3, 'approach': dv > 0.5,
             'brake': AGT < -0.3, 'follow': (np.abs(AGT) <= 0.3) & (np.abs(dv) <= 0.5)}
    H = np.zeros((5, len(masks)))
    for j, (rn, m) in enumerate(masks.items()):
        H[:, j] = np.abs(G[m]).mean(0) if m.any() else 0.0
    cond_all, sloppy_all, _ = fisher_cond(G)
    fmask = masks['follow']
    cond_fol, sloppy_fol, _ = fisher_cond(G[fmask]) if fmask.sum() > 5 else (np.nan, np.zeros(5), None)
    return {'H': H, 'regimes': list(masks.keys()),
            'cond_all': cond_all, 'sloppy_all': sloppy_all,
            'cond_follow': cond_fol, 'sloppy_follow': sloppy_fol}


# ---------------------------------------------------------------------------
# B2
# ---------------------------------------------------------------------------
def sample_driver(rng):
    return np.array([rng.uniform(14, 38), rng.uniform(0.7, 2.2), rng.uniform(1.5, 4.0),
                     rng.uniform(0.6, 2.0), rng.uniform(0.8, 2.5)])


def nrmse_params(true, hat):
    return {PNAME[i]: float(np.sqrt(np.mean((hat[:, i] - true[:, i]) ** 2)) / RNG[i])
            for i in range(5)}


def coord_nrmse(true, hat):
    # normalizzazione CONSISTENTE: ogni quantita' su (max-min) della sua distribuzione vera
    def nc(tv, hv):
        return float(np.sqrt(np.mean((hv - tv) ** 2)) / (tv.max() - tv.min() + 1e-12))
    return {'a': nc(true[:, 3], hat[:, 3]),
            'sqrt(ab)': nc(np.sqrt(true[:, 3] * true[:, 4]), np.sqrt(hat[:, 3] * hat[:, 4])),
            'a/b': nc(true[:, 3] / true[:, 4], hat[:, 3] / hat[:, 4])}


def run_B2(M=20, seed=7):
    rng = np.random.default_rng(seed)
    drivers = [sample_driver(rng) for _ in range(M)]
    out = {}

    # --- condizioni a fit GLOBALE ---
    for cond, kw in [('rich_clean', dict(only=None, noise=False)),
                     ('follow_only', dict(only={'following'}, noise=False)),
                     ('rich_noisy', dict(only=None, noise=True))]:
        true, hat = [], []
        for k, pg in enumerate(drivers):
            S, V, VL, AL, AGT, _ = driver_dataset(pg, np.random.default_rng(1000 + k),
                                                  N=240, **kw)
            if len(S) > 800:
                idx = np.random.default_rng(5000 + k).choice(len(S), 800, replace=False)
                S, V, VL, AL, AGT = (x[idx] for x in (S, V, VL, AL, AGT))
            true.append(pg); hat.append(fit_lm(S, V, VL, AL, AGT))
        true, hat = np.array(true), np.array(hat)
        out[cond] = {'nrmse': nrmse_params(true, hat), 'coord': coord_nrmse(true, hat)}
        print(f'  [B2 {cond}] a/b NRMSE = '
              f'{out[cond]["nrmse"]["a"]:.3f}/{out[cond]["nrmse"]["b"]:.3f}')

    # --- condizione LOCAL_WINDOW (identificazione per-finestra, come la rete) ---
    W = 40
    true_w, hat_w = [], []
    for k, pg in enumerate(drivers):
        S, V, VL, AL, AGT, _ = driver_dataset(pg, np.random.default_rng(2000 + k), N=240)
        wr = np.random.default_rng(6000 + k)
        for _ in range(8):
            st = int(wr.integers(0, max(1, len(S) - W)))
            sl = slice(st, st + W)
            true_w.append(pg)
            hat_w.append(fit_lm(S[sl], V[sl], VL[sl], AL[sl], AGT[sl]))
    true_w, hat_w = np.array(true_w), np.array(hat_w)
    out['local_window'] = {'nrmse': nrmse_params(true_w, hat_w),
                           'coord': coord_nrmse(true_w, hat_w)}
    print(f'  [B2 local_window] a/b NRMSE = '
          f'{out["local_window"]["nrmse"]["a"]:.3f}/{out["local_window"]["nrmse"]["b"]:.3f}')
    return out


# ---------------------------------------------------------------------------
# figure
# ---------------------------------------------------------------------------
def fig_B1(b1):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 5.2))
    im = a1.imshow(b1['H'], aspect='auto', cmap='viridis')
    a1.set_xticks(range(len(b1['regimes']))); a1.set_xticklabels(b1['regimes'])
    a1.set_yticks(range(5)); a1.set_yticklabels(PNAME)
    a1.set_title('B1 - Sensitivita |d(accel)/d(param)| per regime\n'
                 'a si vede solo in free_accel; b solo in approach/brake')
    for i in range(5):
        for j in range(len(b1['regimes'])):
            a1.text(j, i, f'{b1["H"][i, j]:.2f}', ha='center', va='center',
                    color='w' if b1['H'][i, j] < b1['H'].max() * 0.6 else 'k', fontsize=8)
    plt.colorbar(im, ax=a1, label='sensitivita media [m/s2 / full-range]')
    x = np.arange(5); w = 0.38
    a2.bar(x - w / 2, np.abs(b1['sloppy_all']), w,
           label=f'tutti gli scenari (cond={b1["cond_all"]:.0f})', color='tab:green')
    a2.bar(x + w / 2, np.abs(b1['sloppy_follow']), w,
           label=f'solo following (cond={b1["cond_follow"]:.0f})', color='tab:red')
    a2.set_xticks(x); a2.set_xticklabels(PNAME)
    a2.set_ylabel('|componente| direzione sloppy (Fisher)')
    a2.set_title('B1 - Direzione meno identificabile\n'
                 'con transitori: mite; solo following: esplode e carica su a,b')
    a2.legend(fontsize=9); a2.grid(alpha=0.3, axis='y')
    plt.tight_layout(); p = os.path.join(FIGDIR, 'dynB_sensitivity.png')
    plt.savefig(p, dpi=130); plt.close(fig); return p


def fig_B2(b2):
    conds = ['rich_clean', 'follow_only', 'local_window', 'rich_noisy']
    labels = ['rich_clean\n(globale, pulito)', 'follow_only\n(no transitori)',
              'local_window\n(~ come la rete)', 'rich_noisy\n(rumore V2X)']
    easy = [np.mean([b2[c]['nrmse'][p] for p in EASY]) for c in conds] + \
           [np.mean([NET_NRMSE[p] for p in EASY])]
    dyn = [np.mean([b2[c]['nrmse'][p] for p in DYN]) for c in conds] + \
          [np.mean([NET_NRMSE[p] for p in DYN])]
    xl = labels + ['SNN\n(rete S3)']
    x = np.arange(len(xl)); w = 0.38
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15.5, 5.4))
    a1.bar(x - w / 2, easy, w, label='media v0,T,s0 (statici)', color='tab:blue')
    a1.bar(x + w / 2, dyn, w, label='media a,b (dinamici)', color='tab:red')
    a1.set_xticks(x); a1.set_xticklabels(xl, fontsize=8)
    a1.set_ylabel('NRMSE = RMSE / range')
    a1.set_title('B2 - L\'errore su a/b emerge solo quando l\'identificazione e LOCALE\n'
                 '(globale pulito = 0; finestra locale ~ rete)')
    a1.legend(); a1.grid(alpha=0.3, axis='y')
    cs = ['a', 'sqrt(ab)', 'a/b']; cv = [b2['local_window']['coord'][c] for c in cs]
    a2.bar(cs, cv, color=['tab:red', 'tab:green', 'tab:purple'])
    a2.set_ylabel('NRMSE (LM, condizione local_window)')
    a2.set_title('B3 - Coordinate (fit locale): sqrt(ab) osservabile vs a/b sloppy\n'
                 'sqrt(ab) basso & a/b alto -> riparametrizzare')
    a2.grid(alpha=0.3, axis='y')
    for i, v in enumerate(cv):
        a2.text(i, v, f'{v:.2f}', ha='center', va='bottom')
    plt.tight_layout(); p = os.path.join(FIGDIR, 'dynB_recovery.png')
    plt.savefig(p, dpi=130); plt.close(fig); return p


def main():
    from config import IDM_HWY
    pg = np.array([IDM_HWY[k] for k in PNAME])
    print('[B1] sensitivita/Fisher (driver highway)...')
    b1 = run_B1(pg)
    print(f'  cond(Fisher) tutti={b1["cond_all"]:.1f}  solo-following={b1["cond_follow"]:.1f}')
    print('[B2] recovery LM in 4 condizioni (puo richiedere ~2-3 min)...')
    b2 = run_B2()
    p1 = fig_B1(b1); p2 = fig_B2(b2)

    print('\n=== RISULTATI (NRMSE = RMSE/range) ===')
    for c in ['rich_clean', 'follow_only', 'local_window', 'rich_noisy']:
        print(f'  {c:14s}', {k: round(v, 3) for k, v in b2[c]['nrmse'].items()})
    print(f'  {"SNN (S3)":14s}', NET_NRMSE)
    print('  coord local_window:', {k: round(v, 3) for k, v in b2['local_window']['coord'].items()})

    lw = b2['local_window']
    lw_ab = np.mean([lw['nrmse'][p] for p in DYN])
    net_ab = np.mean([NET_NRMSE[p] for p in DYN])
    rc_ab = np.mean([b2['rich_clean']['nrmse'][p] for p in DYN])
    sab, rat = lw['coord']['sqrt(ab)'], lw['coord']['a/b']
    verdict = []
    if rc_ab < 0.05:
        verdict.append('Identificabilita PIENA su dati globali puliti (a/b NRMSE ~0): '
                       'l\'informazione e\' nei dati. Il tetto NON e\' identificabilita di fondo.')
    if lw_ab > 2 * rc_ab and lw_ab >= 0.5 * net_ab:
        verdict.append(f'Il problema emerge con l\'identificazione LOCALE/per-finestra '
                       f'(a/b {lw_ab:.2f} vs {rc_ab:.2f} globale; rete {net_ab:.2f}): '
                       f'la rete predice per-istante e nei tratti senza transitori a/b sono ciechi.')
    if sab < 0.6 * rat:
        verdict.append(f'Localmente sqrt(ab) ({sab:.2f}) e\' molto meglio di a/b ({rat:.2f}): '
                       f'l\'errore vive sulla direzione molle -> riparametrizzare [a, sqrt(ab)].')
    res = {'B1': {'cond_all': b1['cond_all'], 'cond_follow': b1['cond_follow'],
                  'sloppy_all': b1['sloppy_all'].tolist(),
                  'sloppy_follow': np.asarray(b1['sloppy_follow']).tolist(),
                  'regimes': b1['regimes'], 'H': b1['H'].tolist()},
           'B2': {c: b2[c] for c in b2}, 'B2_SNN': NET_NRMSE, 'verdict': verdict}
    json.dump(res, open(os.path.join(FIGDIR, 'dynB_results.json'), 'w'), indent=2)
    print('\nVERDETTO:')
    for v in verdict:
        print('  -', v)
    print('\nfigure:', p1, p2)


if __name__ == '__main__':
    main()
