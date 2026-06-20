"""Dynamic_Study — LOCALITA' L0: curva del "valore di memoria" (locale, niente Azure).

Estende lo Studio B: quanto scende l'errore su a/b se l'identificatore IDEALE (Levenberg-Marquardt)
ha a disposizione una finestra di contesto di lunghezza W crescente? E' il LIMITE SUPERIORE del
beneficio del contesto temporale. Confrontando con il seq_len della rete (~50) e con la NRMSE della
rete decidiamo se "allungare il contesto" e' una leva utile o se il collo e' altrove.

Output: document/figures_dynamic/dynL0_memory_curve.png + dynL0_results.json
Uso:  python scripts/dynamic_study_L0.py
"""
import os
import sys
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from scripts.dynamic_study_B import (driver_dataset, fit_lm, nrmse_params,    # noqa: E402
                                     sample_driver, PNAME, NET_NRMSE, FIGDIR, EASY, DYN)

# seq_len tipico della rete (BPTT window). HOW_IT_WORKS: 50-100; usiamo 50 come riferimento.
NET_SEQLEN = 50
WINDOWS = [5, 10, 20, 40, 80, 160, 320, 'full']
M = 16                      # driver
WPER = 6                    # finestre per driver per ogni W


def run_L0(seed=11):
    rng = np.random.default_rng(seed)
    drivers = [sample_driver(rng) for _ in range(M)]
    # precalcola un dataset ricco-pulito per driver (riusato per tutte le W)
    data = []
    for k, pg in enumerate(drivers):
        S, V, VL, AL, AGT, _ = driver_dataset(pg, np.random.default_rng(3000 + k), N=300)
        data.append((pg, S, V, VL, AL, AGT))

    curve = {}
    for W in WINDOWS:
        true, hat = [], []
        for k, (pg, S, V, VL, AL, AGT) in enumerate(data):
            n = len(S)
            if W == 'full':
                # un solo fit globale per driver (subsample per velocita')
                idx = np.random.default_rng(9000 + k).choice(n, min(n, 900), replace=False)
                true.append(pg); hat.append(fit_lm(S[idx], V[idx], VL[idx], AL[idx], AGT[idx]))
            else:
                wr = np.random.default_rng(7000 + k + 17 * W)
                for _ in range(WPER):
                    st = int(wr.integers(0, max(1, n - W)))
                    sl = slice(st, st + W)
                    true.append(pg); hat.append(fit_lm(S[sl], V[sl], VL[sl], AL[sl], AGT[sl]))
        true, hat = np.array(true), np.array(hat)
        nr = nrmse_params(true, hat)
        curve[str(W)] = nr
        print(f'  W={str(W):>4}  a={nr["a"]:.3f} b={nr["b"]:.3f} '
              f'easy={np.mean([nr[p] for p in EASY]):.3f}')
    return curve


def fig_L0(curve):
    xs = [w for w in WINDOWS if w != 'full']
    xv = np.array(xs, dtype=float)
    a = [curve[str(w)]['a'] for w in xs]
    b = [curve[str(w)]['b'] for w in xs]
    easy = [np.mean([curve[str(w)][p] for p in EASY]) for w in xs]
    full = curve['full']
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(xv, a, 'o-', color='tab:red', label='a (LM, finestra W)')
    ax.plot(xv, b, 's-', color='tab:purple', label='b (LM, finestra W)')
    ax.plot(xv, easy, '^-', color='tab:blue', label='media v0,T,s0 (LM, finestra W)')
    ax.set_xscale('log')
    ax.axvline(NET_SEQLEN, color='gray', ls='--', alpha=0.7,
               label=f'seq_len rete (~{NET_SEQLEN})')
    # linee orizzontali: NRMSE della rete e limite globale (full)
    ax.axhline(NET_NRMSE['a'], color='tab:red', ls=':', alpha=0.6)
    ax.axhline(NET_NRMSE['b'], color='tab:purple', ls=':', alpha=0.6)
    ax.text(xv[0], NET_NRMSE['a'] + 0.005, 'rete a', color='tab:red', fontsize=8)
    ax.text(xv[0], NET_NRMSE['b'] + 0.005, 'rete b', color='tab:purple', fontsize=8)
    ax.text(xv[-1], full['a'] + 0.005, f"full a={full['a']:.2f}", color='tab:red', fontsize=8, ha='right')
    ax.set_xlabel('lunghezza finestra di contesto W [step] (log)')
    ax.set_ylabel('NRMSE = RMSE / range')
    ax.set_title('L0 - Valore di memoria: NRMSE dell\'identificatore IDEALE vs contesto W\n'
                 '(limite superiore del beneficio del contesto; punteggiate = NRMSE della rete)')
    ax.legend(fontsize=9); ax.grid(alpha=0.3, which='both')
    ax.set_ylim(0, max(max(a), max(b), NET_NRMSE['b']) * 1.1)
    plt.tight_layout()
    p = os.path.join(FIGDIR, 'dynL0_memory_curve.png')
    plt.savefig(p, dpi=130); plt.close(fig); return p


def main():
    print('[L0] curva valore-di-memoria (LM, finestre crescenti)...')
    curve = run_L0()
    p = fig_L0(curve)
    json.dump(curve, open(os.path.join(FIGDIR, 'dynL0_results.json'), 'w'), indent=2)
    # lettura automatica
    a40 = curve['40']['a']; b40 = curve['40']['b']
    a160 = curve['160']['a']; b160 = curve['160']['b']
    print('\nLETTURA:')
    print(f'  a/b @ W~seq_len(40): {a40:.3f}/{b40:.3f}  |  @ W=160: {a160:.3f}/{b160:.3f}'
          f'  |  full: {curve["full"]["a"]:.3f}/{curve["full"]["b"]:.3f}')
    print(f'  rete: a={NET_NRMSE["a"]:.3f} b={NET_NRMSE["b"]:.3f}')
    slope = (a40 - a160) + (b40 - b160)
    if slope > 0.04:
        print('  -> la curva scende ancora oltre seq_len: ALLUNGARE il contesto paga (memoria utile).')
    else:
        print('  -> la curva e\' gia\' piatta a seq_len: il collo NON e\' la lunghezza del contesto')
        print('     ma COME viene usato (memoria/loss) + gap SNN. Allungare seq_len rende poco.')
    print('figura:', p)


if __name__ == '__main__':
    main()
