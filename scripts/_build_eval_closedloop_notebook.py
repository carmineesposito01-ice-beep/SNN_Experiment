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


CELL_5_PLOTS = '''# Cell 5 -- Set completo: G1 traiettorie+accel, G2 TTC, G3 distribuzione margini, G4 string-stability
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from utils.closed_loop_eval import simulate, build_scenarios, TTC_STAR

sources = [('oracle', None)] + [(lbl, m) for lbl, m in models.items()]
dtype0, pgt0 = next((d for d in drivers if d[0] == 'highway'), drivers[0])
scen0 = {s[0]: s for s in build_scenarios(pgt0, N=N_STEPS, rng=np.random.default_rng(100))}

# G1: gap / velocita / accelerazione per gli scenari dinamici (come reagisce l'ego)
dyn = ['cut_in', 'hard_brake', 'stop_and_go']
fig, axes = plt.subplots(3, len(dyn), figsize=(5 * len(dyn), 11), sharex='col')
for col, sname in enumerate(dyn):
    _, vl, s_i, v_i, cut = scen0[sname]
    for src, mdl in sources:
        tr = simulate(mdl, pgt0, vl, s_i, v_i, cut_in=cut)
        t = np.arange(len(tr['s'])) * 0.1
        axes[0, col].plot(t, tr['s'], label=src, alpha=0.85)
        axes[1, col].plot(t, tr['v'], label=src, alpha=0.85)
        axes[2, col].plot(t, tr['a_ego'], label=src, alpha=0.85)
    axes[1, col].plot(np.arange(len(vl)) * 0.1, vl, 'k--', lw=1, alpha=0.5, label='leader')
    axes[0, col].axhline(0, color='r', lw=1.2); axes[0, col].set_title(sname)
    axes[2, col].axhline(-9, color='r', ls=':', lw=0.8)
    axes[0, col].set_ylabel('gap [m]'); axes[1, col].set_ylabel('v [m/s]'); axes[2, col].set_ylabel('a_ego [m/s2]')
    axes[2, col].set_xlabel('t [s]')
    for r in range(3):
        axes[r, col].grid(alpha=0.3); axes[r, col].legend(fontsize=6)
fig.suptitle('G1 — Traiettorie closed-loop: gap / velocita / accelerazione (rosso = collisione / -9 limite)')
fig.tight_layout(); fig.savefig(f'{RESULTS_DIR}/eval_G1_trajectories.png', dpi=120); plt.show()

# G2: TTC(t) negli scenari critici — il segnale di pericolo reale
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
for col, sname in enumerate(['cut_in', 'hard_brake']):
    _, vl, s_i, v_i, cut = scen0[sname]
    for src, mdl in sources:
        tr = simulate(mdl, pgt0, vl, s_i, v_i, cut_in=cut)
        ttc = np.where(tr['dv'] > 1e-3, tr['s'] / np.maximum(tr['dv'], 1e-6), np.nan)
        axes[col].plot(np.arange(len(ttc)) * 0.1, np.clip(ttc, 0, 8), label=src, alpha=0.85)
    axes[col].axhline(TTC_STAR, color='r', ls='--', label=f'TTC critico {TTC_STAR}s')
    axes[col].set_title(f'{sname}: TTC(t)'); axes[col].set_xlabel('t [s]'); axes[col].set_ylabel('TTC [s] (clip 8)')
    axes[col].legend(fontsize=7); axes[col].grid(alpha=0.3)
fig.suptitle('G2 — Time-To-Collision: sotto la linea rossa = pericolo')
fig.tight_layout(); fig.savefig(f'{RESULTS_DIR}/eval_G2_ttc.png', dpi=120); plt.show()

# G3: distribuzione margini su TUTTE le sim (la CODA = caso peggiore, conta per la safety)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5))
for src in df['source'].unique():
    sub = df[df['source'] == src]
    a1.scatter(sub['min_gap'], np.clip(sub['min_ttc'], 0, 10), label=src, alpha=0.6, s=28)
a1.axvline(0, color='r', lw=1); a1.axhline(TTC_STAR, color='r', ls='--')
a1.set_xlabel('min_gap [m] (0 = collisione)'); a1.set_ylabel('min_TTC [s] (clip 10)')
a1.set_title('Ogni punto = una sim. Basso-sx = pericoloso (la coda)'); a1.legend(fontsize=8); a1.grid(alpha=0.3)
df.pivot_table(index='scenario', columns='source', values='min_gap', aggfunc='min').plot(kind='bar', ax=a2)
a2.axhline(0, color='r', lw=1.2); a2.set_ylabel('worst min_gap [m]')
a2.set_title('Margine minimo per scenario'); a2.set_xticklabels(a2.get_xticklabels(), rotation=0)
a2.grid(alpha=0.3, axis='y')
fig.suptitle('G3 — Margini di sicurezza: distribuzione (coda) + worst-case per scenario')
fig.tight_layout(); fig.savefig(f'{RESULTS_DIR}/eval_G3_margins.png', dpi=120); plt.show()

# G4: string stability — l'ego smorza o amplifica le oscillazioni del leader?
_, vl, s_i, v_i, _ = scen0['sinusoidal']
fig, ax = plt.subplots(figsize=(11, 4.5))
ax.plot(np.arange(len(vl)) * 0.1, vl, 'k--', lw=1.6, label='leader')
for src, mdl in sources:
    tr = simulate(mdl, pgt0, vl, s_i, v_i)
    ax.plot(np.arange(len(tr['v'])) * 0.1, tr['v'], label=src, alpha=0.85)
ax.set_xlabel('t [s]'); ax.set_ylabel('v [m/s]')
ax.set_title('G4 — String stability: ampiezza ego < leader = stabile (smorza)')
ax.legend(fontsize=8); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(f'{RESULTS_DIR}/eval_G4_string_stability.png', dpi=120); plt.show()
print('Salvati 4 grafici: G1 traiettorie+accel, G2 TTC, G3 margini (scatter+barre), G4 string-stability')'''


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
