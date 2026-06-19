"""Loss_Study Eval — Validazione CLOSED-LOOP del controller ACC-IDM (param da SNN).

Carica i checkpoint (best_model.pt, solo su Azure), guida l'ego in scenari avversari
(cut-in, frenate forti, stop&go, sinusoidale) e calcola metriche oggettive di sicurezza/
comfort/tracking/string-stability. Confronto SNN vs ORACOLO (param veri) sugli stessi scenari.

Robusto: salta i checkpoint assenti; l'oracolo gira sempre. Preserva i checkpoint testati
nei results. Genera Loss_Study_Eval_ClosedLoop.ipynb.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_cell(ctype, src, cid):
    if isinstance(src, list):
        src = '\n'.join(src)
    c = {'cell_type': ctype, 'id': cid, 'metadata': {}, 'source': src}
    if ctype == 'code':
        c['execution_count'] = None
        c['outputs'] = []
    return c


def make_notebook(cells):
    return {'cells': cells,
            'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                         'language_info': {'name': 'python', 'version': '3.x'}},
            'nbformat': 4, 'nbformat_minor': 5}


MARKDOWN_INTRO = """# Loss_Study Eval — Validazione CLOSED-LOOP (sicurezza ACC)

La rete e' usata come **controller**: osservazioni -> SNN -> 5 param IDM -> acc_iidm_accel ->
l'ego GUIDA. Leader avversario (cut-in, frenate forti, stop&go, sinusoidale). Confronto
**SNN vs ORACOLO** (param veri) sugli stessi scenari.

**Domanda**: l'ego guidato dalla rete e' SICURO (zero collisioni, indipendentemente dal
leader) e si comporta come l'oracolo? Metriche: TTC/TET/TIT/DRAC/min-gap/headway (sicurezza),
RMS-accel/jerk/max-decel (comfort), gap-error/time-gap (tracking), gain (string stability).

> Checkpoint solo su Azure (`checkpoints/`). Il notebook salta quelli assenti e li preserva nei results.
"""


CELL_1_BOOTSTRAP = """# Cell 1 -- Bootstrap + ENV
import sys, os, subprocess
import importlib.util as _imu
RESULTS_DIR = 'results/Loss_Study/Eval_ClosedLoop'
BRANCH = 'Loss_Study'
os.makedirs(RESULTS_DIR, exist_ok=True)
for pkg in ['pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
for f in ['utils/closed_loop_eval.py', 'core/network.py']:
    assert os.path.isfile(f), f'missing {f}'
br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
assert br == BRANCH, f'branch={br} != {BRANCH}'
print(f'[Eval] ENV OK. branch={br}')"""


CELL_2_CONFIG = '''# Cell 2 -- Checkpoint candidati + carica quelli presenti
import os, torch
from core.network import build_model

# (label, path checkpoint, hidden_size, rank). Tutti su Azure in checkpoints/.
CANDIDATES = [
    ('S3 d0.3 (launch)', 'checkpoints/LS3_PEAK_R0_launch_d03/best_model.pt', 32, 8),
    ('S3 d1.0 (launch)', 'checkpoints/LS3_PEAK_R0_launch/best_model.pt',     32, 8),
    ('R33_C2 CLEAN',     'checkpoints/R33_C2_A1_T12_fix/best_model.pt',       32, 8),
]

models = {}
for label, path, h, rk in CANDIDATES:
    if not os.path.isfile(path):
        print(f'  [skip] {label}: checkpoint assente ({path})')
        continue
    ck = torch.load(path, map_location='cpu', weights_only=False)
    m = build_model(variant='baseline', hidden_size=h, rank=rk, max_delay=6, bit_shift=3)
    m.load_state_dict(ck['model_state']); m.eval()
    models[label] = m
    # preserva il checkpoint nei results (per analisi locale/deploy futuro)
    dst = f'{RESULTS_DIR}/checkpoints/{label.replace(" ","_").replace("(","").replace(")","")}.pt'
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    import shutil; shutil.copy2(path, dst)
    print(f'  [OK] {label}: caricato + preservato ({sum(p.numel() for p in m.parameters())} param)')
assert models, 'Nessun checkpoint trovato! Verifica i path su Azure.'
print(f'Modelli da validare: {list(models.keys())} (+ oracolo)')'''


CELL_3_RUN = '''# Cell 3 -- Esegui validazione closed-loop: modelli (+oracolo) x driver x scenari
import numpy as np, pandas as pd
from data.generator import _sample_scenario, parse_scenario_mix
from utils.closed_loop_eval import simulate, build_scenarios, all_metrics, string_stability_gain

N_DRIVERS = 20          # scenari-guidatore campionati (params veri diversi)
N_STEPS = 600
MIX = parse_scenario_mix('highway:0.4,urban:0.3,truck:0.2,mixed:0.1')
rng = np.random.default_rng(42)

# campiona N_DRIVERS set di parametri veri (diversi tipi di guidatore)
drivers = []
_r = np.random.default_rng(7)
for _ in range(N_DRIVERS):
    p, prof, stype, ci = _sample_scenario(_r, scenario_mix=MIX)
    drivers.append((stype, np.array([p['v0'], p['T'], p['s0'], p['a'], p['b']], dtype=np.float32)))

sources = [('oracle', None)] + [(lbl, m) for lbl, m in models.items()]
rows = []
for di, (dtype, pgt) in enumerate(drivers):
    scen = build_scenarios(pgt, N=N_STEPS, rng=np.random.default_rng(100 + di))
    for sname, vl, s_i, v_i, cut in scen:
        for src, mdl in sources:
            tr = simulate(mdl, pgt, vl, s_i, v_i, cut_in=cut)
            mt = all_metrics(tr)
            mt['gain'] = string_stability_gain(tr) if sname == 'sinusoidal' else float('nan')
            mt.update({'source': src, 'scenario': sname, 'driver': di, 'driver_type': dtype})
            rows.append(mt)
df = pd.DataFrame(rows)
df.to_csv(f'{RESULTS_DIR}/closedloop_metrics_raw.csv', index=False)
print(f'Simulazioni: {len(df)} ({len(sources)} sorgenti x {N_DRIVERS} driver x 5 scenari)')'''


CELL_4_SUMMARY = '''# Cell 4 -- Sintesi sicurezza + confronto SNN vs oracolo
import pandas as pd, numpy as np
from IPython.display import display, Markdown

display(Markdown('## Verdetto SICUREZZA per sorgente (su tutti gli scenari)'))
safety = df.groupby('source').agg(
    n=('collided', 'size'),
    collision_rate=('collided', 'mean'),
    worst_min_gap=('min_gap', 'min'),
    worst_min_ttc=('min_ttc', lambda x: np.min(x[np.isfinite(x)]) if np.isfinite(x).any() else np.inf),
    worst_min_headway=('min_time_headway', lambda x: np.min(x[np.isfinite(x)]) if np.isfinite(x).any() else np.inf),
    max_DRAC=('max_DRAC', 'max'),
    mean_TET=('TET', 'mean'), mean_TIT=('TIT', 'mean'),
).round(3)
safety.to_csv(f'{RESULTS_DIR}/safety_summary.csv')
display(safety)
print('CRITERIO: collision_rate DEVE essere 0. worst_min_ttc > 1.5s ideale. DRAC < ~9 (>9=inevitabile).')

display(Markdown('## Collision rate per scenario (dove la rete cede?)'))
coll = df.pivot_table(index='scenario', columns='source', values='collided', aggfunc='mean').round(3)
coll.to_csv(f'{RESULTS_DIR}/collision_by_scenario.csv')
display(coll)

display(Markdown('## Comfort + tracking + string stability (medie)'))
qual = df.groupby('source').agg(
    rms_accel=('rms_accel', 'mean'), max_decel=('max_decel', 'max'),
    rms_jerk=('rms_jerk', 'mean'), rms_gap_error=('rms_gap_error', 'mean'),
    string_gain=('gain', 'mean'),
).round(3)
qual.to_csv(f'{RESULTS_DIR}/quality_summary.csv')
display(qual)
print('string_gain < 1 = string-stable (smorza le perturbazioni del leader).')
print('Sintesi salvate: safety_summary.csv, collision_by_scenario.csv, quality_summary.csv')'''


CELL_5_PLOTS = '''# Cell 5 -- Traiettorie esempio (cut-in, hard_brake) + barre sicurezza
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from utils.closed_loop_eval import simulate, build_scenarios

# usa il primo driver highway per gli esempi
dtype0, pgt0 = next((d for d in drivers if d[0] == 'highway'), drivers[0])
scen0 = {s[0]: s for s in build_scenarios(pgt0, N=N_STEPS, rng=np.random.default_rng(100))}
sources = [('oracle', None)] + [(lbl, m) for lbl, m in models.items()]

fig, axes = plt.subplots(2, 2, figsize=(15, 9))
for col, sname in enumerate(['cut_in', 'hard_brake']):
    _, vl, s_i, v_i, cut = scen0[sname]
    for src, mdl in sources:
        tr = simulate(mdl, pgt0, vl, s_i, v_i, cut_in=cut)
        t = np.arange(len(tr['s'])) * 0.1
        axes[0, col].plot(t, tr['s'], label=src, alpha=0.85)
        axes[1, col].plot(t, tr['v'], label=f'{src} ego', alpha=0.85)
    axes[1, col].plot(np.arange(len(vl)) * 0.1, vl, 'k--', lw=1, label='leader', alpha=0.6)
    axes[0, col].axhline(0, color='r', lw=1.2, label='COLLISIONE')
    axes[0, col].set_title(f'{sname}: gap [m]'); axes[0, col].set_ylabel('gap [m]')
    axes[0, col].legend(fontsize=7); axes[0, col].grid(alpha=0.3)
    axes[1, col].set_title(f'{sname}: velocita'); axes[1, col].set_xlabel('t [s]')
    axes[1, col].set_ylabel('v [m/s]'); axes[1, col].legend(fontsize=7); axes[1, col].grid(alpha=0.3)
plt.tight_layout(); plt.savefig(f'{RESULTS_DIR}/closedloop_trajectories.png', dpi=120); plt.show()

# barre: worst min_gap per scenario x sorgente
piv = df.pivot_table(index='scenario', columns='source', values='min_gap', aggfunc='min')
piv.plot(kind='bar', figsize=(11, 5)); plt.axhline(0, color='r', lw=1.2)
plt.ylabel('worst min_gap [m] (0 = collisione)'); plt.title('Margine minimo di sicurezza per scenario')
plt.xticks(rotation=0); plt.grid(alpha=0.3, axis='y'); plt.tight_layout()
plt.savefig(f'{RESULTS_DIR}/closedloop_min_gap.png', dpi=120); plt.show()
print('saved trajectories + min_gap plots')'''


CELL_6_FINAL = """# Cell 6 -- Commit finale (metriche + plot + checkpoint preservati)
import subprocess
subprocess.run(['git', 'add', RESULTS_DIR], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'Eval closed-loop: safety metrics + trajectories'],
                   capture_output=True, text=True)
print(r.stdout[-200:] if r.returncode == 0 else r.stderr[-200:])
subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
print('Eval pushed.')"""


def main():
    cells = [
        make_cell('markdown', MARKDOWN_INTRO, 'cell-intro'),
        make_cell('code', CELL_1_BOOTSTRAP, 'cell-1'),
        make_cell('code', CELL_2_CONFIG, 'cell-2'),
        make_cell('code', CELL_3_RUN, 'cell-3'),
        make_cell('code', CELL_4_SUMMARY, 'cell-4'),
        make_cell('code', CELL_5_PLOTS, 'cell-5'),
        make_cell('code', CELL_6_FINAL, 'cell-6'),
    ]
    nb = make_notebook(cells)
    out = os.path.join(ROOT, 'Loss_Study_Eval_ClosedLoop.ipynb')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
