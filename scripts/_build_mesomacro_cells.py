"""Celle MESO (plotone/string-stability) e MACRO (diagramma fondamentale) per i notebook
di evaluation. Definisce CELL_MESO e CELL_MACRO (stringhe) riusate dal validation_full e da
un notebook standalone. Usano `models` (dict caricato) + MESO_DIR / MACRO_DIR.

Grafici leggibili (richiesta): gain-vs-indice (1 linea/variante) + heatmap spazio-tempo,
no spaghetti. Metriche esaustive (Treiber ch16/ch9) salvate in CSV.
"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CELL_MESO = '''# Cell MESO -- Plotone: string stability ACC (stringa aperta, Treiber ch16.7)
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from utils.platoon_eval import simulate_platoon, platoon_metrics
from IPython.display import display, Markdown

PGT0 = np.array([33.3, 1.2, 2.5, 1.1, 1.5], dtype=np.float32)   # driver highway rappresentativo
N_PLAT = 12                                                     # veicoli nel plotone
NSTEP = 500; t = np.arange(NSTEP); v_set = 0.7 * PGT0[0]
# perturbazione sinusoidale sostenuta in testa (criterio ACC: transfer function)
v_leader = v_set + 0.15 * v_set * np.sin(2 * np.pi * t / 100.0)
sources = [('oracle', None)] + [(lbl, m) for lbl, m in models.items()]

rows = []; recs = {}
for src, mdl in sources:
    rec = simulate_platoon(mdl, PGT0, N_PLAT, v_leader)
    mt = platoon_metrics(rec); mt['source'] = src
    rows.append(mt); recs[src] = rec
df_meso = pd.DataFrame(rows)
df_meso.drop(columns=['gain_per_vehicle']).to_csv(f'{MESO_DIR}/meso_summary.csv', index=False)

fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 5))
# G-meso-1: gain per veicolo (1 linea per variante -> leggibile, no spaghetti)
for r in rows:
    g = r['gain_per_vehicle']
    a1.plot(range(1, len(g) + 1), g, marker='o', alpha=0.85,
            label=f"{r['source']} (h2t={r['head_to_tail_gain']})")
a1.axhline(1.0, color='r', ls='--', label='soglia instabilita')
a1.set_xlabel('indice veicolo (1=testa -> coda)'); a1.set_ylabel('gain |H|_i = A_i / A_leader')
a1.set_title('String stability: gain per veicolo (<1 e decrescente = stabile)')
a1.legend(fontsize=8); a1.grid(alpha=0.3)
# G-meso-2: heatmap spazio-tempo velocita (1 variante primaria) -> mostra l'onda chiaramente
prim = list(recs.keys())[1] if len(recs) > 1 else list(recs.keys())[0]
im = a2.imshow(recs[prim]['v'].T, aspect='auto', origin='lower', cmap='viridis',
               extent=[0, NSTEP * 0.1, 1, recs[prim]['v'].shape[1]])
a2.set_xlabel('t [s]'); a2.set_ylabel('indice veicolo')
a2.set_title(f'Velocita spazio-tempo ({prim}): perturbazione che si smorza lungo la catena')
plt.colorbar(im, ax=a2, label='v [m/s]')
plt.tight_layout(); plt.savefig(f'{MESO_DIR}/meso_string_stability.png', dpi=120); plt.show()

# SCORECARD metriche scalari del plotone -> barre (tutto visibile senza CSV)
scal = ['head_to_tail_gain', 'max_amplification', 'min_gap_platoon', 'min_ttc_platoon',
        'rms_accel_mean', 'max_decel_platoon', 'rms_jerk_mean']
fig3, axes3 = plt.subplots(2, 4, figsize=(18, 8))
for ax, col in zip(axes3.ravel(), scal):
    ax.bar(range(len(df_meso)), df_meso[col].values, color='tab:green', alpha=0.8)
    ax.set_xticks(range(len(df_meso))); ax.set_xticklabels(df_meso['source'], rotation=25, ha='right', fontsize=7)
    ax.set_title(col, fontsize=9); ax.grid(alpha=0.3, axis='y')
axes3.ravel()[-1].axis('off')
fig3.suptitle('MESO — metriche scalari del plotone (head-to-tail, amplificazione, sicurezza catena, comfort)')
fig3.tight_layout(); fig3.savefig(f'{MESO_DIR}/meso_metrics_scorecard.png', dpi=120); plt.show()

display(Markdown('## MESO — string stability del plotone (verdetto: head-to-tail < 1?)'))
display(df_meso.drop(columns=['gain_per_vehicle']))
print('Metriche: gain per veicolo, head-to-tail, max amplificazione, monotonia (strict), convettivita a monte,')
print('         min gap/TTC nella catena, collisioni, comfort (rms accel/jerk, max decel).')'''


CELL_MACRO = '''# Cell MACRO -- Diagramma fondamentale (anello chiuso, Treiber ch9/ch16)
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from utils.platoon_eval import fundamental_diagram, simulate_ring
from IPython.display import display, Markdown

PGT0 = np.array([33.3, 1.2, 2.5, 1.1, 1.5], dtype=np.float32)
DENS = [8, 15, 25, 35, 45, 60, 80, 100, 120, 150]             # veh/km
sources = [('oracle', None)] + [(lbl, m) for lbl, m in models.items()]

fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 5))
allfd = {}; rows = []
for src, mdl in sources:
    fd = fundamental_diagram(mdl, PGT0, DENS, ring_length=1000.0, n_steps=600)
    allfd[src] = fd
    rho = [p['rho_veh_km'] for p in fd]; Q = [p['Q_veh_h'] for p in fd]; V = [p['V_km_h'] for p in fd]
    line, = a1.plot(rho, Q, marker='o', alpha=0.85, label=src)
    a2.plot(rho, V, marker='o', alpha=0.85, label=src)
    qmax = max(fd, key=lambda p: p['Q_veh_h'])
    a1.scatter([qmax['rho_veh_km']], [qmax['Q_veh_h']], marker='*', s=200, zorder=5,
               color=line.get_color(), edgecolor='k')
    a1.annotate(f"cap {qmax['Q_veh_h']:.0f}", (qmax['rho_veh_km'], qmax['Q_veh_h']),
                textcoords='offset points', xytext=(0, 9), fontsize=7, ha='center')
    jam = [p for p in fd if p['V_km_h'] < 3.0]
    rows.append({'source': src, 'capacity_veh_h': qmax['Q_veh_h'], 'rho_crit_veh_km': qmax['rho_veh_km'],
                 'v_free_km_h': fd[0]['V_km_h'],
                 'rho_jam_veh_km': (jam[0]['rho_veh_km'] if jam else float('nan')),
                 'first_unstable_rho': next((p['rho_veh_km'] for p in fd if p['unstable']), float('nan'))})
a1.set_xlabel('densita rho [veh/km]'); a1.set_ylabel('flusso Q [veh/h]')
a1.set_title('Diagramma fondamentale Q(rho): sale (libero) -> capacita -> scende (congestione)')
a1.legend(fontsize=8); a1.grid(alpha=0.3)
a2.set_xlabel('densita rho [veh/km]'); a2.set_ylabel('velocita V [km/h]')
a2.set_title('Relazione velocita-densita V(rho)'); a2.legend(fontsize=8); a2.grid(alpha=0.3)
plt.tight_layout(); plt.savefig(f'{MACRO_DIR}/macro_fundamental_diagram.png', dpi=120); plt.show()

df_macro = pd.DataFrame(rows)
df_macro.to_csv(f'{MACRO_DIR}/macro_summary.csv', index=False)

# SCORECARD macro scalari -> barre (tutto visibile senza CSV)
mcols = ['capacity_veh_h', 'rho_crit_veh_km', 'v_free_km_h', 'rho_jam_veh_km']
figm, axesm = plt.subplots(1, 4, figsize=(18, 4.5))
for ax, col in zip(axesm, mcols):
    ax.bar(range(len(df_macro)), df_macro[col].values, color='tab:purple', alpha=0.8)
    ax.set_xticks(range(len(df_macro))); ax.set_xticklabels(df_macro['source'], rotation=25, ha='right', fontsize=7)
    ax.set_title(col, fontsize=9); ax.grid(alpha=0.3, axis='y')
figm.suptitle('MACRO — metriche scalari (capacita, densita critica, v free-flow, densita di jam)')
figm.tight_layout(); figm.savefig(f'{MACRO_DIR}/macro_metrics_scorecard.png', dpi=120); plt.show()

display(Markdown('## MACRO — diagramma fondamentale + capacita (SNN vs oracolo)'))
display(df_macro)

# heatmap stop&go a densita congestionata (1 variante primaria)
prim_src, prim_mdl = (sources[1] if len(sources) > 1 else sources[0])
n_cong = int(60 / 1000.0 * 1000.0)
rec = simulate_ring(prim_mdl, PGT0, n_cong, 1000.0, 800)
fig2, axh = plt.subplots(figsize=(11, 4))
im = axh.imshow(rec['v'].T, aspect='auto', origin='lower', cmap='RdYlGn',
                extent=[0, 800 * 0.1, 0, rec['n']])
axh.set_xlabel('t [s]'); axh.set_ylabel('veicolo')
axh.set_title(f'Onde stop&go a rho=60 veh/km ({prim_src}): verde=veloce, rosso=fermo')
plt.colorbar(im, ax=axh, label='v [m/s]')
plt.tight_layout(); plt.savefig(f'{MACRO_DIR}/macro_stopandgo.png', dpi=120); plt.show()
print('Metriche: capacita Q_max, densita critica, v free-flow, densita di jam, soglia di instabilita (stop&go).')'''


def _standalone():
    """Notebook standalone meso+macro (oltre all'integrazione in validation_full)."""
    def cell(src, cid):
        return {'cell_type': 'code', 'id': cid, 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': src}
    ENV = """# Cell -- ENV meso/macro standalone
import os
MESO_DIR = 'results/evaluate/standalone/Meso'; MACRO_DIR = 'results/evaluate/standalone/Macro'
for d in (MESO_DIR, MACRO_DIR): os.makedirs(d, exist_ok=True)
import torch
from core.network import build_model
CKPT = 'checkpoints/LS3_PEAK_R0_launch_d03/best_model.pt'
models = {}
if os.path.isfile(CKPT):
    ck = torch.load(CKPT, map_location='cpu', weights_only=False)
    m = build_model(variant='baseline', hidden_size=32, rank=8, max_delay=6, bit_shift=3)
    m.load_state_dict(ck['model_state']); m.eval(); models['S3 d0.3'] = m
print('ENV OK, modelli:', list(models.keys()))"""
    PUSH = """# Cell -- push (meso + macro standalone)
import subprocess
subprocess.run(['git', 'add', 'results/evaluate/standalone'], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'Meso/Macro standalone results'], capture_output=True, text=True)
print(r.stdout[-200:] if r.returncode == 0 else r.stderr[-200:])
subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', 'Loss_Study'], capture_output=True)
subprocess.run(['git', 'push', 'origin', 'Loss_Study'], capture_output=True)
print('MesoMacro standalone pushed.')"""
    nb = {'cells': [cell(ENV, 'env'), cell(CELL_MESO, 'meso'), cell(CELL_MACRO, 'macro'), cell(PUSH, 'push')],
          'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                       'language_info': {'name': 'python', 'version': '3.x'}},
          'nbformat': 4, 'nbformat_minor': 5}
    out = os.path.join(ROOT, 'Loss_Study_MesoMacro.ipynb')
    json.dump(nb, open(out, 'w', encoding='utf-8'), indent=1)
    print(f'Wrote {out}')


if __name__ == '__main__':
    _standalone()
