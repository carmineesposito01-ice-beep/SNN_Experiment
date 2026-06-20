"""Dynamic_Study L1.6 — ri-validazione a SCALA del readout full-memoryless (no training).

L1/L1.5/L1c/L1d: il readout memoryless abbassa la NRMSE di a/b (bias-centering) ed e' piu' liscio;
la diagnosi e' chiusa. Prima di promuoverlo a modo di deploy ufficiale, lo ri-validiamo a scala
confrontando oracle / normal / memoryless sugli STESSI scenari, con enfasi su SICUREZZA e COMFORT
(priorita' utente: Safety > Comfort > Performance; b e' una decel di comfort, e le onde stop&go).

Riusa gli harness VALIDATI senza duplicare fisica:
  - utils/closed_loop_eval.simulate / build_scenarios / all_metrics / string_stability_gain  (MICRO)
  - utils/platoon_eval.simulate_platoon / platoon_metrics                                     (MESO plotone)
Il readout memoryless si ottiene con un MemorylessWrapper che resetta lo stato prima di ogni
forward_step -> simulate()/simulate_platoon() girano memoryless SENZA modifiche.

  MICRO   N_DRIVERS x 5 scenari avversari x 3 modi: sicurezza (collisioni+CI, min_gap, TTC, DRAC),
          comfort (rms_jerk, max_decel, rms_accel), string-stability (indice di smorzamento D su
          stop&go e sinusoidale), tracking (gap_error).
  MESO    plotone aperto (12 veicoli, perturbazione sinusoidale in testa): gain per veicolo,
          head-to-tail, amplificazione, comfort di catena -> attenuazione delle onde.

Genera Dynamic_Study_L1_6.ipynb. Checkpoint solo su Azure -> celle col modello saltano se assente.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cell(src, cid, ctype='code'):
    c = {'cell_type': ctype, 'id': cid, 'metadata': {}, 'source': src}
    if ctype == 'code':
        c['execution_count'] = None
        c['outputs'] = []
    return c


INTRO = """# Dynamic_Study L1.6 — ri-validazione a scala del readout full-memoryless

Niente training, solo `LS3_PEAK_R0_launch_d03`. Confronto **oracle / normal / memoryless** a scala,
con priorita' **Safety > Comfort > Performance** (b = decel di comfort; onde stop&go = comfort).

- **MICRO** — N_DRIVERS x 5 scenari x 3 modi: sicurezza (collisioni+CI, min_gap, TTC, DRAC),
  comfort (rms_jerk, max_decel, rms_accel), string-stability (smorzamento D su stop&go e sinusoidale).
- **MESO** — plotone (12 veicoli): gain per veicolo, head-to-tail, attenuazione delle onde.

Riusa gli harness validati (closed_loop_eval, platoon_eval) via un MemorylessWrapper -> nessuna
duplicazione di fisica. Output in `results/Dynamic_Study/L1_6/`. Push automatico finale.
"""

ENV = """# Cell 1 -- ENV
import sys, os, subprocess
import importlib.util as _imu
RESULTS = 'results/Dynamic_Study/L1_6'
BRANCH = 'Dynamic_Study'
os.makedirs(RESULTS, exist_ok=True)
for pkg in ['pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
for f in ['utils/closed_loop_eval.py', 'utils/platoon_eval.py', 'core/network.py']:
    assert os.path.isfile(f), 'missing ' + f
br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
print('[L1.6] ENV OK | branch =', br)
"""

LOAD = """# Cell 2 -- checkpoint + MemorylessWrapper (reset stato prima di ogni forward_step)
import os, torch
from core.network import build_model

CKPT = 'checkpoints/LS3_PEAK_R0_launch_d03/best_model.pt'

class MemorylessWrapper:
    # Espone l'API usata dagli harness (eval/reset_state/forward_step) ma resetta lo stato
    # ricorrente PRIMA di ogni forward_step -> readout per-istante (nessuna memoria cross-step).
    def __init__(self, m):
        self.m = m
    def eval(self):
        self.m.eval(); return self
    def reset_state(self, batch, device):
        self.m.reset_state(batch, device)
    def forward_step(self, x):
        self.m.reset_state(x.shape[0], x.device)
        return self.m.forward_step(x)

model = None
if os.path.isfile(CKPT):
    ck = torch.load(CKPT, map_location='cpu', weights_only=False)
    model = build_model(variant='baseline', hidden_size=32, rank=8, max_delay=6, bit_shift=3)
    model.load_state_dict(ck['model_state']); model.eval()
    print('[OK] modello', sum(p.numel() for p in model.parameters()), 'param')
else:
    print('[skip] checkpoint assente:', CKPT, '-> esegui su Azure')

# modi confrontati: oracle (param veri), normal (memoria propagata), memoryless (reset/step)
MODES = [('oracle', None)]
if model is not None:
    MODES += [('normal', model), ('memoryless', MemorylessWrapper(model))]
print('Modi:', [m[0] for m in MODES])
"""

MICRO = """# Cell 3 -- MICRO: sicurezza + comfort + string-stability, N_DRIVERS x 5 scenari x modi
import numpy as np, pandas as pd
from data.generator import _sample_scenario, parse_scenario_mix
from utils.closed_loop_eval import simulate, build_scenarios, all_metrics, string_stability_gain
from IPython.display import display, Markdown

if model is not None:
    N_DRIVERS = 60          # 60 driver x 5 scenari = 300 sim/modo (CI Wilson stretta)
    N_STEPS = 600
    MIX = parse_scenario_mix('highway:0.4,urban:0.3,truck:0.2,mixed:0.1')
    _rd = np.random.default_rng(7)
    drivers = []
    for _ in range(N_DRIVERS):
        p, _, stype, _ = _sample_scenario(_rd, scenario_mix=MIX)
        drivers.append((stype, np.array([p['v0'], p['T'], p['s0'], p['a'], p['b']], dtype=np.float32)))

    rows = []
    for di, (dtype, pgt) in enumerate(drivers):
        scen = build_scenarios(pgt, N=N_STEPS, rng=np.random.default_rng(100 + di))
        for sname, vl, s_i, v_i, cut in scen:
            for mname, mdl in MODES:
                tr = simulate(mdl, pgt, vl, s_i, v_i, cut_in=cut)
                mt = all_metrics(tr)
                # indice di smorzamento D = std(v_ego)/std(v_leader) (comfort onde): stop&go + sinusoidale
                mt['damping_D'] = string_stability_gain(tr) if sname in ('stop_and_go', 'sinusoidal') else float('nan')
                mt.update({'mode': mname, 'scenario': sname, 'driver': di})
                rows.append(mt)
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS + '/l1_6_micro_raw.csv', index=False)
    order = [m[0] for m in MODES]

    def _wilson_hi(p, n, z=1.96):
        if n == 0: return float('nan')
        c = z*z/n
        return round(((p + c/2) + z*np.sqrt(p*(1-p)/n + c/(4*n))) / (1 + c), 4)

    # SICUREZZA
    safety = df.groupby('mode').agg(n=('collided', 'size'), collision_rate=('collided', 'mean'),
        worst_min_gap=('min_gap', 'min'),
        worst_min_ttc=('min_ttc', lambda x: float(np.min(x[np.isfinite(x)])) if np.isfinite(x).any() else np.inf),
        max_DRAC=('max_DRAC', 'max'), mean_TET=('TET', 'mean')).reindex(order).round(3)
    safety['collision_CI95hi'] = [_wilson_hi(p, n) for p, n in zip(safety['collision_rate'], safety['n'])]
    safety.to_csv(RESULTS + '/l1_6_safety.csv')
    # COMFORT (priorita' #2): jerk, max_decel, accel + smorzamento onde D (stop&go/sinusoidale)
    dgo = df[df['scenario'] == 'stop_and_go'].groupby('mode')['damping_D'].mean().reindex(order)
    dsin = df[df['scenario'] == 'sinusoidal'].groupby('mode')['damping_D'].mean().reindex(order)
    comfort = df.groupby('mode').agg(rms_jerk=('rms_jerk', 'mean'), max_decel=('max_decel', 'max'),
        rms_accel=('rms_accel', 'mean')).reindex(order).round(3)
    comfort['D_stopgo'] = dgo.round(3); comfort['D_sinus'] = dsin.round(3)
    comfort.to_csv(RESULTS + '/l1_6_comfort.csv')
    # PERFORMANCE (#3): tracking
    perf = df.groupby('mode').agg(rms_gap_error=('rms_gap_error', 'mean')).reindex(order).round(3)
    perf.to_csv(RESULTS + '/l1_6_perf.csv')
    coll = df.pivot_table(index='scenario', columns='mode', values='collided', aggfunc='mean').round(3)

    display(Markdown('## MICRO — SICUREZZA per modo (collisioni + CI95, margini)')); display(safety)
    display(Markdown('## MICRO — COMFORT per modo (jerk/decel/accel + smorzamento onde D<1)')); display(comfort)
    display(Markdown('## MICRO — PERFORMANCE (tracking)')); display(perf)
    display(Markdown('## Collisioni per scenario')); display(coll)
    print('N =', int(safety['n'].iloc[0]), 'sim/modo. D<1 = smorza le onde (stop&go/sinusoidale).')
else:
    print('[skip] modello assente'); df = None; safety = comfort = perf = None
"""

MESO = """# Cell 4 -- MESO: plotone (attenuazione delle onde lungo la catena) per modo
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from utils.platoon_eval import simulate_platoon, platoon_metrics
from IPython.display import display, Markdown

if model is not None:
    PGT0 = np.array([33.3, 1.2, 2.5, 1.1, 1.5], dtype=np.float32)   # driver highway rappresentativo
    N_PLAT = 12; NSTEP = 500; t = np.arange(NSTEP); v_set = 0.7 * PGT0[0]
    v_leader = v_set + 0.15 * v_set * np.sin(2 * np.pi * t / 100.0)
    rows = []; recs = {}
    for mname, mdl in MODES:
        rec = simulate_platoon(mdl, PGT0, N_PLAT, v_leader)
        mt = platoon_metrics(rec); mt['mode'] = mname
        rows.append(mt); recs[mname] = rec
    order = [m[0] for m in MODES]
    df_meso = pd.DataFrame(rows).set_index('mode').reindex(order)
    df_meso.drop(columns=['gain_per_vehicle']).to_csv(RESULTS + '/l1_6_meso.csv')
    fig, ax = plt.subplots(figsize=(9, 5))
    for r in rows:
        g = r['gain_per_vehicle']
        ax.plot(range(1, len(g) + 1), g, marker='o', alpha=0.85,
                label=r['mode'] + ' (h2t=' + str(r['head_to_tail_gain']) + ')')
    ax.axhline(1.0, color='r', ls='--', label='soglia instabilita')
    ax.set_xlabel('indice veicolo (1=testa -> coda)'); ax.set_ylabel('gain |H|_i = A_i / A_leader')
    ax.set_title('MESO - string stability per modo (<1 e decrescente = onde smorzate)')
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(RESULTS + '/l1_6_meso.png', dpi=130); plt.show()
    display(Markdown('## MESO — plotone per modo (head-to-tail < 1 = stabile)'))
    display(df_meso[['head_to_tail_gain', 'max_amplification', 'string_stable_headtail',
                     'min_gap_platoon', 'rms_jerk_mean', 'max_decel_platoon', 'collided']])
else:
    print('[skip] modello assente'); df_meso = None
"""

VERDICT = """# Cell 5 -- verdetto (Safety > Comfort > Performance) + push
import json, subprocess, numpy as np
if model is not None:
    def g(tbl, col, mode): return float(tbl.loc[mode, col])
    # SAFETY: memoryless non peggiore di normal (collisioni + margine)
    saf = (g(safety, 'collision_rate', 'memoryless') <= g(safety, 'collision_rate', 'normal') + 1e-9 and
           g(safety, 'worst_min_gap', 'memoryless') >= g(safety, 'worst_min_gap', 'normal') - 0.5)
    # COMFORT: jerk non peggiore (>10%), max_decel non peggiore, smorzamento onde non peggiore
    com = (g(comfort, 'rms_jerk', 'memoryless') <= 1.10 * g(comfort, 'rms_jerk', 'normal') and
           g(comfort, 'max_decel', 'memoryless') <= 1.10 * g(comfort, 'max_decel', 'normal') and
           g(comfort, 'D_stopgo', 'memoryless') <= g(comfort, 'D_stopgo', 'normal') + 0.05 and
           g(df_meso, 'head_to_tail_gain', 'memoryless') <= g(df_meso, 'head_to_tail_gain', 'normal') + 0.05)
    # PERFORMANCE: tracking non peggiore
    perf_ok = g(perf, 'rms_gap_error', 'memoryless') <= g(perf, 'rms_gap_error', 'normal') + 0.5
    v = []
    v.append('SAFETY: coll memoryless %.3f vs normal %.3f (CI95hi %.3f); worst min_gap %.2f vs %.2f -> %s'
             % (g(safety, 'collision_rate', 'memoryless'), g(safety, 'collision_rate', 'normal'),
                g(safety, 'collision_CI95hi', 'memoryless'), g(safety, 'worst_min_gap', 'memoryless'),
                g(safety, 'worst_min_gap', 'normal'), 'OK' if saf else 'REGRESSIONE'))
    v.append('COMFORT: jerk %.2f vs %.2f; max_decel %.2f vs %.2f; D_stopgo %.2f vs %.2f; '
             'plotone head-to-tail %.2f vs %.2f -> %s'
             % (g(comfort, 'rms_jerk', 'memoryless'), g(comfort, 'rms_jerk', 'normal'),
                g(comfort, 'max_decel', 'memoryless'), g(comfort, 'max_decel', 'normal'),
                g(comfort, 'D_stopgo', 'memoryless'), g(comfort, 'D_stopgo', 'normal'),
                g(df_meso, 'head_to_tail_gain', 'memoryless'), g(df_meso, 'head_to_tail_gain', 'normal'),
                'OK' if com else 'REGRESSIONE'))
    v.append('PERFORMANCE: gap_error %.2f vs %.2f -> %s'
             % (g(perf, 'rms_gap_error', 'memoryless'), g(perf, 'rms_gap_error', 'normal'),
                'OK' if perf_ok else 'peggiore'))
    if saf and com:
        v.append('=> PROMUOVI memoryless a readout di deploy: nessuna regressione su Safety ne Comfort '
                 '(le 2 priorita top)' + ('; Performance OK.' if perf_ok else '; Performance leggermente peggiore (#3, accettabile).'))
    elif saf and not com:
        v.append('=> NON promuovere ancora: Safety OK ma COMFORT regredisce -> il memoryless va bene per la '
                 'sicurezza ma peggiora comfort/onde. Rivedere prima del deploy.')
    else:
        v.append('=> NON promuovere: regressione di SAFETY -> blocco.')
    out = {'safety_ok': bool(saf), 'comfort_ok': bool(com), 'perf_ok': bool(perf_ok),
           'safety': json.loads(safety.to_json()), 'comfort': json.loads(comfort.to_json()),
           'perf': json.loads(perf.to_json()), 'meso': json.loads(df_meso.drop(columns=['gain_per_vehicle']).to_json()),
           'verdict': v}
    json.dump(out, open(RESULTS + '/l1_6_results.json', 'w'), indent=2)
    print('VERDETTO L1.6:')
    for s in v:
        print(' -', s)
    subprocess.run(['git', 'add', RESULTS], capture_output=True)
    r = subprocess.run(['git', 'commit', '-m', 'Dynamic_Study L1.6: ri-validazione a scala full-memoryless (Safety>Comfort>Performance) - micro + plotone'],
                       capture_output=True, text=True)
    print(r.stdout[-200:] if r.returncode == 0 else r.stderr[-200:])
    subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True)
    subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
    print('L1.6 pushed.')
else:
    print('[skip] niente da pushare (checkpoint assente)')
"""


def main():
    cells = [cell(INTRO, 'intro', 'markdown'),
             cell(ENV, 'env'), cell(LOAD, 'load'),
             cell(MICRO, 'micro'), cell(MESO, 'meso'), cell(VERDICT, 'verdict')]
    nb = {'cells': cells,
          'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                       'language_info': {'name': 'python', 'version': '3.x'}},
          'nbformat': 4, 'nbformat_minor': 5}
    out = os.path.join(ROOT, 'Dynamic_Study_L1_6.ipynb')
    json.dump(nb, open(out, 'w', encoding='utf-8'), indent=1)
    print('Wrote', out)


if __name__ == '__main__':
    main()
