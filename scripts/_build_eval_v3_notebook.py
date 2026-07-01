"""Builder del notebook EVALUATE v3 — 'TURTLE POWER!!!' (4 champion + oracolo, evaluate 6-tier ESAUSTIVO).

Genera Eval_v3_TURTLE_POWER.ipynb. Gira su AZURE (Python 3.10, checkpoint in checkpoints/<tag>/best_model.pt).
Per OGNI dimensione produce DATI (csv) + FIGURE (png). Resiliente: ogni sezione SALTA se l'output esiste
(re-run multi-ora sicuro); cella col modello assente -> skip con grazia; push finale.

v3.1 (esaustivo): oracolo in tutte le sezioni closed-loop; metriche 6-tier complete (SSM estese, comfort ISO,
tracking, equifinality/PE/naturalisticity/calibration); quantizzazione fixed+po2 2-12 bit + per-parametro +
ablazione pesi PO2; V2X esaustivo (3 hold_mode + AoI + Gilbert/jitter/blackout); string a 3 nozioni + profilo
amplificazione; diagnostica rete (dead-neuron/eff_rank/raster reale/raggio spettrale); Reachability + Breakdown.
Viz variata (heatmap/scatter/box/spettro/line) per ridurre la monotonia dei bar-chart.

Cartelle in results/evaluate/v3_TURTLE_POWER!!!/ : 00_Scorecard, 01_Accuracy ... 09_Trajectories,
10_Reachability, 11_Breakdown; 08_Energy_Spiking/raster/ (per-champion), README.md.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def C(src, cid):
    return {'cell_type': 'code', 'id': cid, 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': src}


def MD(src, cid):
    return {'cell_type': 'markdown', 'id': cid, 'metadata': {}, 'source': src}


def resilient(body, name):
    # Avvolge una cella d'analisi: se lancia, scrive ERROR_<name>.txt e PROSEGUE (sotto nbconvert un'eccezione
    # non gestita fermerebbe TUTTE le celle successive + il push). RESULTS e' definito dalla cella ENV.
    indented = '\n'.join((('    ' + l) if l.strip() else l) for l in body.splitlines())
    return ('import traceback as _tb, os as _os\n'
            'try:\n' + indented + '\n'
            'except Exception:\n'
            '    _os.makedirs(RESULTS, exist_ok=True)\n'
            "    open(_os.path.join(RESULTS, 'ERROR_" + name + ".txt'), 'w', encoding='utf-8').write(_tb.format_exc())\n"
            "    print('[ERROR] " + name + " -> vedi ERROR_" + name + ".txt'); print(_tb.format_exc())\n")


INTRO = """# 🐢 EVALUATE v3 — TURTLE POWER!!! (esaustivo)

Validazione esaustiva (qualitativa + quantitativa) di **4 champion + oracolo** dello studio EventProp,
con l'evaluate 6-tier COMPLETO. Per ogni dimensione: **dati (csv) + figure (png)**.

| Alias | Tag | Colore | Carattere |
|---|---|---|---|
| **Master Splinter** | *oracolo* | grigio | riferimento (parametri veri) |
| **Raffaello** | `R33_C2_A1_T12_fix` | rosso | Prodigy baseline, aggressivo |
| **Leonardo** | `LS3_PEAK_R0_launch_d03` | azzurro | champion BPTT, conservativo (safety) |
| **Donatello** | `PE_t05_gp0002` | viola | best-NRMSE |
| **Michelangelo** | `A_lr1e2_t06_r16` | arancione | best-Adam (equilibrato) |

Dimensioni: Accuracy · Closed-loop sicurezza (SSM estese + comfort ISO + tracking, oracolo) · String stability
(3 nozioni + profilo amplificazione) · Identificabilità (FIM/equifinality/PE/naturalisticity/calibration) ·
Quantizzazione (fixed+po2, 2-12 bit, per-param, ablazione pesi) · Robustezza V2X (3 hold_mode + AoI + burst) ·
Dinamica veicolo · Energia/spiking + diagnostica rete · Traiettorie · **Reachability** · **Breakdown** · **Scorecard**.

**Resiliente**: ogni sezione salta se l'output esiste; celle col modello assente saltano con grazia; push finale.
"""

ENV = r"""# Cell 1 -- ENV + champion + loader robusto + helper figure/cartelle
import os, sys, json, glob, subprocess, importlib.util as _imu
sys.path.insert(0, os.getcwd())
for pkg in ['pandas', 'matplotlib', 'numpy', 'torch', 'scipy']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
import numpy as np, pandas as pd, torch
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
# stile figure (qualità/leggibilità uniforme su tutte le sezioni)
plt.rcParams.update({'savefig.dpi': 120, 'font.size': 10, 'axes.titlesize': 11, 'axes.titleweight': 'bold',
                     'axes.grid': True, 'grid.alpha': 0.25, 'axes.axisbelow': True, 'legend.frameon': False,
                     'figure.facecolor': 'white', 'axes.edgecolor': '#666'})
try:
    from IPython.display import display
except Exception:
    def display(*a, **k):
        for x in a:
            print(x)

RESULTS = 'results/evaluate/v3_TURTLE_POWER!!!'
BRANCH = 'EventProp_Study'
CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'   # eval set COMUNE a tutti (confronto equo)
N_DRIVERS = 25
PN = ['v0', 'T', 's0', 'a', 'b']

CHAMPIONS = [
    ('Master Splinter', '__oracle__',             '#7f7f7f', 'oracolo (param veri)',         None),
    ('Raffaello',       'R33_C2_A1_T12_fix',      '#d62728', 'Prodigy baseline, aggressivo', 'baseline'),
    ('Leonardo',        'LS3_PEAK_R0_launch_d03', '#1f9ed1', 'champion BPTT, conservativo',  'baseline'),
    ('Donatello',       'PE_t05_gp0002',          '#9467bd', 'best-NRMSE',                   'eventprop_alif_full'),
    ('Michelangelo',    'A_lr1e2_t06_r16',        '#ff7f0e', 'best-Adam, equilibrato',       'eventprop_alif_full'),
]
COLOR = {a: c for a, _, c, _, _ in CHAMPIONS}
ORACLE = 'Master Splinter'; OCOL = COLOR[ORACLE]
SNN_CHAMPS = [(a, t, c, v) for a, t, c, _, v in CHAMPIONS if t != '__oracle__']   # i 4 modelli (con variant)

os.makedirs(RESULTS, exist_ok=True)
assert os.path.isfile(CACHE), 'manca la cache eval: ' + CACHE
CACHE_DATA = torch.load(CACHE, map_location='cpu', weights_only=False)


def sub(d):
    p = os.path.join(RESULTS, d); os.makedirs(p, exist_ok=True); return p

def savefig(d, name):
    plt.savefig(os.path.join(sub(d), name), dpi=120, bbox_inches='tight'); plt.close()

def savecsv(d, name, rows):
    pd.DataFrame(rows).to_csv(os.path.join(sub(d), name), index=False)

def done(d, name):
    return os.path.isfile(os.path.join(RESULTS, d, name))


def robust_load(tag, variant='eventprop_alif_full', device='cpu'):
    # Loader robusto: variante dedotta dallo SCHEMA delle chiavi (autorevole), rank/hidden da rec_U, +
    # VALIDAZIONE che il readout (layer_out) sia caricato (altrimenti resterebbe random -> output spazzatura).
    from core.network import build_model
    p = os.path.join('checkpoints', tag, 'best_model.pt')
    if not os.path.isfile(p):
        return None
    ck = torch.load(p, map_location=device, weights_only=False)
    state = ck['model_state'] if 'model_state' in ck else ck
    if 'layer_hidden.rec_U' in state:
        hidden = int(state['layer_hidden.rec_U'].shape[0]); rank = int(state['layer_hidden.rec_U'].shape[1])
    else:
        hidden, rank = 32, 16
    if 'layer_out.fc_weight' in state:
        v = 'baseline'
    elif 'layer_out.weight' in state:
        v = 'eventprop_alif_full'
    else:
        v = variant or 'eventprop_alif_full'
    try:
        m = build_model(variant=v, hidden_size=hidden, rank=rank, max_delay=6, bit_shift=3)
        res = m.load_state_dict(state, strict=False)
    except Exception:
        return None
    if any('layer_out' in k for k in getattr(res, 'missing_keys', [])):
        print('   [WARN] %s: readout non caricato (variant=%s) -> scartato' % (tag, v))
        return None
    m.eval()
    m._loaded_variant = v
    return m

MODELS = {}
for alias, tag, _, variant in SNN_CHAMPS:
    try:
        m = robust_load(tag, variant)
        MODELS[alias] = m
        print('[OK] %-16s <- %-26s (variant=%s) %s' % (alias, tag, variant,
              'caricato' if m is not None else 'CHECKPOINT ASSENTE/load fallito'))
    except Exception as e:
        MODELS[alias] = None
        print('[FAIL] %-16s <- %-26s %s' % (alias, tag, str(e)[:80]))
AVAIL = [a for a, _, _, _ in SNN_CHAMPS if MODELS.get(a) is not None]
print('\nModelli disponibili:', AVAIL, '| oracolo sempre disponibile')

# helper box-plot da statistiche pre-calcolate (min/p5/p50/p95/max del rich) -> distribuzione senza sample grezzi
def box_from_summary(ax, summaries, labels, colors):
    stats = []
    for s in summaries:
        stats.append({'label': '', 'med': s.get('p50', s.get('mean', np.nan)),
                      'q1': s.get('p5', s.get('min', np.nan)), 'q3': s.get('p95', s.get('max', np.nan)),
                      'whislo': s.get('min', np.nan), 'whishi': s.get('max', np.nan), 'fliers': []})
    bp = ax.bxp(stats, showfliers=False, patch_artist=True)
    for patch, col in zip(bp['boxes'], colors):
        patch.set_facecolor(col); patch.set_alpha(0.55)
    ax.set_xticklabels(labels, rotation=20)

_readme = ['# Eval v3 — TURTLE POWER!!! (esaustivo)\n', '\n## Champion\n',
           '| alias | tag | colore | carattere |\n|---|---|---|---|\n']
for a, t, c, d, _ in CHAMPIONS:
    _readme.append('| %s | `%s` | %s | %s |\n' % (a, t, c, d))
_readme += ['\n## Cartelle (per dimensione)\n',
            '- `00_Scorecard` confronto cross-champion (radar + tabella master, incl. oracolo dove sensato)\n',
            '- `01_Accuracy` NRMSE per-canale / accuracy (heatmap + bar, oracolo=0 di riferimento)\n',
            '- `02_Safety_ClosedLoop` SSM estese (TTC/TET/TIT/DRAC/TED/TID/cpi/headway), comfort ISO, tracking, Δ-vs-oracolo\n',
            '- `03_StringStability` 3 nozioni: head-to-tail, peak |Γ(ω)|, frac_strict; profilo amplificazione lungo il plotone\n',
            '- `04_Identifiability` FIM (cond, spettro autovalori), equifinality, PE, causal, NRMSE strat, naturalisticity KS, calibration\n',
            '- `05_Quantization` fixed+po2, 2-12 bit, degrado per-parametro, ablazione pesi PO2 on/off\n',
            '- `06_V2X_Robustness` PDR/latenza/jitter/Gilbert/blackout + 3 hold_mode + AoI-vs-safety (oracolo sotto canale)\n',
            '- `07_VehicleDynamics` plant reale (ideale/bagnato/ghiaccio), oracolo di riferimento\n',
            '- `08_Energy_Spiking` energia SNN (nJ, ×vs ANN) + diagnostica rete (dead/sat/eff_rank/raggio spettrale) + raster reale\n',
            '- `09_Trajectories` traiettorie per scenario (champion + oracolo)\n',
            '- `10_Reachability` frontiera worst-case: gap minimo sicuro vs Δv (oracolo vs SNN)\n',
            '- `11_Breakdown` curva di rottura: collisione vs decel leader e vs gap cut-in (oracolo vs SNN)\n',
            '- `12_Mesoscopic` plotone 12 veicoli: string stability (gain per veicolo) + heatmap spazio-tempo + scorecard\n',
            '- `13_Macroscopic` anello: diagramma fondamentale Q(ρ)/V(ρ) + capacità + onde stop&go\n',
            '- `14_Showcase` VETRINA "come spara la rete": raster sincronizzato + phase-plane + energia + GIF in diretta\n',
            '\n`ERROR_<sez>.txt` (se presente) = quella sezione ha fallito; le altre proseguono.\n']
with open(os.path.join(RESULTS, 'README.md'), 'w', encoding='utf-8') as _f:
    _f.write(''.join(_readme))
"""

ACCURACY = r"""# Cell 2 -- ACCURACY / identificazione: NRMSE per-canale (heatmap + accuracy). Oracolo = 0 di riferimento.
from scripts.closed_loop_identify import identify
D = '01_Accuracy'
if done(D, 'accuracy.csv'):
    print('[SKIP] accuracy'); display(pd.read_csv(os.path.join(RESULTS, D, 'accuracy.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    BOUNDS = {'v0': (8, 45), 'T': (0.5, 2.5), 's0': (1, 5), 'a': (0.3, 2.5), 'b': (0.5, 3)}
    rows = []
    for alias in AVAIL:
        m = MODELS[alias]
        err = {c: [] for c in PN}
        for it in CACHE_DATA['val'][:N_DRIVERS]:
            x = torch.tensor(it['x'][:50][None], dtype=torch.float32)
            pg = identify(m, x); true = [it['params'][c] for c in PN]
            for i, c in enumerate(PN):
                err[c].append((pg[i] - true[i]) ** 2)
        row = {'champion': alias}
        for c in PN:
            rng = BOUNDS[c][1] - BOUNDS[c][0]
            row['nrmse_' + c] = float(np.sqrt(np.mean(err[c])) / rng)
        row['nrmse_mean'] = float(np.mean([row['nrmse_' + c] for c in PN]))
        row['accuracy_pct'] = max(0.0, 1 - row['nrmse_mean']) * 100
        rows.append(row)
    dfA = pd.DataFrame(rows)
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    # sinistra: HEATMAP champion x canale (piu' informativa dei bar raggruppati)
    M = np.array([[r['nrmse_' + c] for c in PN] for r in rows])
    im = ax[0].imshow(M, aspect='auto', cmap='YlOrRd')
    ax[0].set_xticks(range(len(PN))); ax[0].set_xticklabels(PN)
    ax[0].set_yticks(range(len(rows))); ax[0].set_yticklabels([r['champion'] for r in rows])
    for i in range(len(rows)):
        for j in range(len(PN)):
            ax[0].text(j, i, '%.2f' % M[i, j], ha='center', va='center', fontsize=7)
    ax[0].set_title('NRMSE per-canale (↓ meglio)'); plt.colorbar(im, ax=ax[0])
    # destra: accuracy media + linea oracolo (100%)
    ax[1].bar([r['champion'] for r in rows], [r['accuracy_pct'] for r in rows],
              color=[COLOR[r['champion']] for r in rows])
    ax[1].axhline(100, color=OCOL, ls='--', label='oracolo (param veri) = 100%'); ax[1].axhline(75, color='gray', ls=':')
    ax[1].set_ylabel('accuracy ~ (1-NRMSE) [%]'); ax[1].set_title('Accuracy media'); ax[1].legend(fontsize=7)
    ax[1].tick_params(axis='x', rotation=20)
    plt.suptitle('01 — Accuracy / identificazione (oracolo NRMSE=0 per costruzione)'); savefig(D, 'accuracy.png')
    savecsv(D, 'accuracy.csv', rows); display(dfA)
"""

CLOSEDLOOP = r"""# Cell 3 -- CLOSED-LOOP sicurezza ESAUSTIVA: SSM estese + comfort ISO + tracking, oracolo + Δ-vs-oracolo.
from scripts.closed_loop_identify import eval_safety
D = '02_Safety_ClosedLoop'
if done(D, 'safety.csv'):
    print('[SKIP] safety'); display(pd.read_csv(os.path.join(RESULTS, D, 'safety.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    # tutte le metriche RICH da esporre (media della distribuzione), + collision separato
    MK = ['min_gap', 'brake_margin_min', 'min_ttc', 'TET', 'TIT', 'max_DRAC', 'TED_drac', 'TID_drac',
          'cpi', 'frac_drac_critical', 'min_time_headway', 'frac_ttc_below_1.5', 'impact_dv',
          'max_decel', 'rms_jerk', 'rms_accel', 'max_abs_jerk', 'frac_jerk_uncomf',
          'frac_decel_iso_viol', 'energy_proxy', 'rms_gap_error', 'mean_time_gap', 'mean_abs_gap_err_ss']
    rows = []; per_scen = {}; rich_by = {}
    def grab(d):
        o = {}
        for k in MK:
            o[k] = d[k]['mean'] if (k in d and isinstance(d[k], dict) and 'mean' in d[k]) else float('nan')
        o['collision_rate'] = d['collision']['rate']; o['collision_ub95'] = d['collision']['wilson_ub95']
        return o
    oracle_rich = None
    for alias in AVAIL:
        r = eval_safety(MODELS[alias], CACHE_DATA, n_drivers=N_DRIVERS, rich=True, tail=True)
        rc = r['rich']; rich_by[alias] = rc
        rows.append({'champion': alias, **grab(rc['snn'])})
        per_scen[alias] = rc['per_scenario']
        if oracle_rich is None:
            oracle_rich = rc['oracle']; rows.insert(0, {'champion': ORACLE, **grab(oracle_rich)})
    df = pd.DataFrame(rows); savecsv(D, 'safety.csv', rows)
    order = [r['champion'] for r in rows]
    cols = [COLOR.get(a, '#333') for a in order]
    # fig 1: scorecard chiave (bars)
    metr = [('min_gap', 'min-gap [m] ↑'), ('brake_margin_min', 'margine evitab. [m] ↑'),
            ('min_ttc', 'min TTC [s] ↑'), ('max_decel', 'max decel ↓'), ('rms_jerk', 'rms jerk ↓')]
    fig, axes = plt.subplots(1, len(metr), figsize=(4 * len(metr), 4.2))
    for ax, (k, ttl) in zip(axes, metr):
        ax.bar(order, [dict(zip(order, df[k]))[a] for a in order], color=cols)
        ax.set_title(ttl, fontsize=9); ax.tick_params(axis='x', rotation=90, labelsize=6)
    plt.suptitle('02 — Closed-loop sicurezza/comfort (oracolo = Master Splinter)'); savefig(D, 'safety_scorecard.png')
    # fig 2: brake_margin continuo
    fig, ax = plt.subplots(figsize=(7, 4.4))
    ax.bar(df['champion'], df['brake_margin_min'], color=cols)
    ax.axhline(0, color='red', ls='--', lw=1, label='confine inevitabile'); ax.legend()
    ax.set_ylabel('brake_margin_min [m] (con segno)'); ax.set_title('Margine di evitabilità fisica (continuo, <0=inevitabile)')
    ax.tick_params(axis='x', rotation=20); savefig(D, 'brake_margin.png')
    # fig 3: per-scenario min_gap heatmap (con riga oracolo)
    scen = sorted(next(iter(per_scen.values())).keys())
    rowsH = [ORACLE] + AVAIL
    Mg = np.array([[per_scen[AVAIL[0]][s]['oracle']['min_gap']['mean'] if a == ORACLE
                    else per_scen[a][s]['snn']['min_gap']['mean'] for s in scen] for a in rowsH])
    fig, ax = plt.subplots(figsize=(max(8, 0.9 * len(scen)), 0.6 * len(rowsH) + 2))
    im = ax.imshow(Mg, aspect='auto', cmap='RdYlGn')
    ax.set_xticks(range(len(scen))); ax.set_xticklabels(scen, rotation=40, fontsize=7)
    ax.set_yticks(range(len(rowsH))); ax.set_yticklabels(rowsH)
    for i in range(len(rowsH)):
        for j in range(len(scen)):
            ax.text(j, i, '%.1f' % Mg[i, j], ha='center', va='center', fontsize=6)
    ax.set_title('min-gap [m] per scenario (verde=sicuro)'); plt.colorbar(im, ax=ax); savefig(D, 'per_scenario_min_gap.png')
    # fig 4: DISTRIBUZIONE (box da summary) di min_ttc e brake_margin per champion+oracolo
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    box_from_summary(ax[0], [(oracle_rich if a == ORACLE else rich_by[a]['snn'])['min_ttc'] for a in order], order, cols)
    ax[0].set_title('Distribuzione min_TTC [s] (box da p5/p50/p95/min/max)'); ax[0].set_ylabel('min_TTC [s]')
    box_from_summary(ax[1], [(oracle_rich if a == ORACLE else rich_by[a]['snn'])['brake_margin_min'] for a in order], order, cols)
    ax[1].axhline(0, color='red', ls='--'); ax[1].set_title('Distribuzione brake_margin_min [m]')
    plt.suptitle('02 — Distribuzioni SSM (non solo la media)'); savefig(D, 'ssm_distribution.png')
    # fig 5: Δ SNN-oracolo (costo di sicurezza dell'identificazione) con CI bootstrap
    dmetr = ['min_gap', 'brake_margin_min', 'min_ttc', 'max_decel']
    fig, ax = plt.subplots(figsize=(9, 4.4)); xx = np.arange(len(dmetr)); w = 0.8 / max(len(AVAIL), 1)
    for k, a in enumerate(AVAIL):
        dd = rich_by[a]['delta_snn_minus_oracle']
        vals = [dd[mm]['mean'] for mm in dmetr]
        lo = np.clip(np.nan_to_num([dd[mm]['mean'] - dd[mm]['ci95'][0] for mm in dmetr]), 0, None)
        hi = np.clip(np.nan_to_num([dd[mm]['ci95'][1] - dd[mm]['mean'] for mm in dmetr]), 0, None)
        ax.bar(xx + k * w, vals, w, yerr=[lo, hi], capsize=2, label=a, color=COLOR[a])
    ax.axhline(0, color='k', lw=0.6); ax.set_xticks(xx + 0.4); ax.set_xticklabels(dmetr, rotation=15)
    ax.set_ylabel('Δ (SNN − oracolo)'); ax.set_title('Costo di sicurezza dell’identificazione (Δ vs oracolo, CI95)')
    ax.legend(fontsize=7); savefig(D, 'delta_vs_oracle.png')
    # fig 6: comfort ISO (violazioni)
    civ = ['frac_decel_iso_viol', 'frac_jerk_uncomf']
    fig, ax = plt.subplots(figsize=(8, 4.2)); xx = np.arange(len(AVAIL)); w = 0.38
    for j, k in enumerate(civ):
        ax.bar(xx + (j - 0.5) * w, [df[df.champion == a][k].iloc[0] for a in AVAIL], w, label=k)
    ax.set_xticks(xx); ax.set_xticklabels(AVAIL, rotation=20); ax.set_ylabel('frazione tempo')
    ax.set_title('Violazioni comfort/ISO (decel<-3.5 ; |jerk|>2)'); ax.legend(fontsize=8); savefig(D, 'comfort_iso.png')
    display(df)
"""

STRING = r"""# Cell 4 -- STRING STABILITY: 3 nozioni (head-to-tail, peak|Γ|, frac_strict) + profilo amplificazione + oracolo.
from scripts.closed_loop_identify import eval_string_stability
from utils.closed_loop_eval import simulate_platoon, platoon_string_metrics, transfer_gain_fft
D = '03_StringStability'
if done(D, 'string_stability.csv'):
    print('[SKIP] string stability'); display(pd.read_csv(os.path.join(RESULTS, D, 'string_stability.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    def _chirp(v0ref, n=600, f0=0.01, f1=0.3):
        t = np.arange(n); f = f0 + (f1 - f0) * t / n
        return 0.7 * v0ref + 1.0 * np.sin(2 * np.pi * np.cumsum(f) * 0.1)
    # ORACOLO: plotone coi param VERI (riferimento) — stessa costruzione chirp di eval_string_stability
    tp = [np.array([it['params'][c] for c in PN], np.float32) for it in CACHE_DATA['val'][:8]]
    lead = _chirp(float(tp[0][0]))
    plo = simulate_platoon(tp, lead)
    mo = platoon_string_metrics(plo['v_profiles'])
    tgo = transfer_gain_fft(plo['v_profiles'][0], plo['v_profiles'][-1], band=(0.01, 0.3))
    oracle_ref = {'champion': ORACLE, 'head_to_tail': mo['head_to_tail'], 'peak_gain': tgo['peak_gain'],
                  'frac_strict_stable': float(mo['strict_string_stable']), 'mean_T': float(np.mean([p[1] for p in tp])),
                  'head_to_tail_lat': float('nan'), 'peak_gain_lat': float('nan')}
    rows = [oracle_ref]; amp_prof = {ORACLE: mo['amp_ratio']}
    for alias in AVAIL:
        r0 = eval_string_stability(MODELS[alias], CACHE_DATA, N=8, n_platoons=5, hetero=True)
        rL = eval_string_stability(MODELS[alias], CACHE_DATA, N=8, n_platoons=5, hetero=True, latency_steps=2)
        rows.append({'champion': alias, 'head_to_tail': r0['head_to_tail_mean'], 'peak_gain': r0['peak_gain_mean'],
                     'frac_strict_stable': r0['frac_strict_stable'], 'mean_T': r0['mean_T'],
                     'head_to_tail_lat': rL['head_to_tail_mean'], 'peak_gain_lat': rL['peak_gain_mean']})
        # profilo amplificazione: media degli amp_ratio sui plotoni
        prof = np.mean([p['amp_ratio'] for p in r0['platoons']], axis=0) if r0.get('platoons') else []
        amp_prof[alias] = list(prof)
    df = pd.DataFrame(rows); savecsv(D, 'string_stability.csv', rows)
    # fig 1: SCATTER head_to_tail (x) vs peak_gain (y) — le 3 nozioni in un colpo (quadrante stabile in basso-a-sx)
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    for _, r in df.iterrows():
        a = r['champion']; ax.scatter(r['head_to_tail'], r['peak_gain'], s=120, color=COLOR.get(a, OCOL),
                                      edgecolor='k', zorder=3, label=a)
        ax.annotate(a, (r['head_to_tail'], r['peak_gain']), fontsize=7, xytext=(4, 4), textcoords='offset points')
    ax.axhline(1.0, color='red', ls='--'); ax.axvline(1.0, color='red', ls='--')
    ax.set_xlabel('head-to-tail gain (end-to-end)'); ax.set_ylabel('peak |Γ(ω)| (frequenza)')
    ax.set_title('String stability: 2 nozioni (≤1 entrambe = stabile). frac_strict in tabella')
    savefig(D, 'string_stability.png')
    # fig 2: PROFILO amplificazione lungo il plotone (spiega perche' frac_strict puo' essere 0)
    fig, ax = plt.subplots(figsize=(8, 4.4))
    for a, prof in amp_prof.items():
        if len(prof):
            ax.plot(range(1, len(prof) + 1), prof, 'o-', color=COLOR.get(a, OCOL), label=a, alpha=0.85)
    ax.axhline(1.0, color='red', ls='--', label='soglia locale =1')
    ax.set_xlabel('coppia veicolo i / i-1'); ax.set_ylabel('amp_ratio (std_i / std_{i-1})')
    ax.set_title('Amplificazione LOCALE lungo il plotone (>1 in qualche coppia ⇒ frac_strict=0)'); ax.legend(fontsize=7)
    savefig(D, 'amp_profile.png')
    # fig 3: head_to_tail con/senza latenza
    fig, ax = plt.subplots(figsize=(8, 4.4)); dch = [r for r in rows if r['champion'] in AVAIL]
    xx = np.arange(len(dch)); w = 0.35
    ax.bar(xx - w / 2, [r['head_to_tail'] for r in dch], w, label='senza latenza', color=[COLOR[r['champion']] for r in dch])
    ax.bar(xx + w / 2, [r['head_to_tail_lat'] for r in dch], w, alpha=0.55, label='latenza CAM',
           color=[COLOR[r['champion']] for r in dch])
    ax.axhline(1.0, color='red', ls='--'); ax.set_xticks(xx); ax.set_xticklabels([r['champion'] for r in dch], rotation=20)
    ax.set_ylabel('head-to-tail'); ax.set_title('Effetto della latenza CAM sul margine string-stability'); ax.legend(fontsize=7)
    savefig(D, 'string_latency.png')
    display(df)
"""

IDENT = r"""# Cell 5 -- IDENTIFICABILITA': FIM (spettro) + equifinality + PE + causal (heatmap) + NRMSE strat + naturalisticity + calibration
from utils.identifiability import (practical_identifiability, persistent_excitation, causal_sensitivity,
                                   nrmse_stratified, fisher_information, equifinality_set,
                                   naturalisticity, calibration_validation, states_from_item)
D = '04_Identifiability'
if done(D, 'fim.csv'):
    print('[SKIP] identifiability'); display(pd.read_csv(os.path.join(RESULTS, D, 'fim.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    pi = practical_identifiability(CACHE_DATA, n=N_DRIVERS)
    pe = persistent_excitation(CACHE_DATA, n=N_DRIVERS)
    # FIM su un driver rappresentativo -> spettro autovalori + equifinality
    it0 = CACHE_DATA['val'][0]; st0 = states_from_item(it0); p0 = np.array([it0['params'][c] for c in PN], np.float32)
    fi = fisher_information(st0, p0); eq = equifinality_set(st0, p0)
    fim_rows = [{'metric': 'cond_mean', 'value': pi['cond_mean']}, {'metric': 'cond_p95', 'value': pi['cond_p95']},
                {'metric': 'rank_FIM', 'value': pe['rank']}, {'metric': 'least_identifiable', 'value': pi['least_identifiable']},
                {'metric': 'most_identifiable', 'value': pi['most_identifiable']},
                {'metric': 'under_excited', 'value': ','.join(pe['under_excited']) or '(nessuno)'},
                {'metric': 'n_equivalent', 'value': eq['n_equivalent']}]
    savecsv(D, 'fim.csv', fim_rows)
    # fig 1: SPETTRO autovalori FIM (log) — mostra le direzioni piatte (autovalori piccoli = mal identificabili)
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.4))
    ev = np.array(sorted(fi['eigvals'], reverse=True)); ev = np.clip(ev, 1e-12, None)
    ax[0].semilogy(range(1, len(ev) + 1), ev, 'o-', color='slateblue')
    ax[0].set_xlabel('modo (autovalore FIM)'); ax[0].set_ylabel('autovalore (log)')
    ax[0].set_title('Spettro FIM (cond=%.1e): coda piatta = direzioni mal identificabili' % pi['cond_mean'])
    ax[1].bar(PN, [eq['param_rel_spread'].get(c, 0.0) for c in PN], color='teal')
    ax[1].set_title('Equifinality: spread relativo per-param (n_equiv=%d)' % eq['n_equivalent']); ax[1].set_ylabel('spread rel.')
    plt.suptitle('04 — Identificabilità (FIM + equifinality)'); savefig(D, 'fim.png')
    # per-champion: causal, nrmse strat, naturalisticity, calibration
    crows = []; sframes = []; ncrows = []
    for alias in AVAIL:
        cs = causal_sensitivity(MODELS[alias], CACHE_DATA, n=N_DRIVERS); crows.append({'champion': alias, **cs})
        ns = nrmse_stratified(MODELS[alias], CACHE_DATA, n=min(200, len(CACHE_DATA['val'])))
        for sc in ns:
            sframes.append({'champion': alias, 'scenario': sc, **{('nrmse_' + c): ns[sc][c] for c in PN}})
        nat = naturalisticity(MODELS[alias], CACHE_DATA, n=15) or {}
        cal = calibration_validation(MODELS[alias], CACHE_DATA, n=N_DRIVERS) or {}
        ncrows.append({'champion': alias, 'ks_time_gap': nat.get('ks_time_gap', float('nan')),
                       'ks_jerk': nat.get('ks_jerk', float('nan')),
                       'gap_rmspe_mean': cal.get('gap_rmspe_mean', float('nan')),
                       'within_floor': cal.get('within_floor', None)})
    savecsv(D, 'causal_sensitivity.csv', crows); savecsv(D, 'nrmse_stratified.csv', sframes)
    savecsv(D, 'naturalisticity_calibration.csv', ncrows)
    # fig 2: HEATMAP causal (champion x edge) — sostituisce i bar raggruppati
    if crows:
        keys = [k for k in crows[0] if '->' in k]
        Mc = np.array([[r.get(k, np.nan) for k in keys] for r in crows])
        fig, ax = plt.subplots(figsize=(max(8, 0.7 * len(keys)), 0.6 * len(crows) + 2))
        im = ax.imshow(Mc, aspect='auto', cmap='coolwarm', vmin=-1, vmax=1)
        ax.set_xticks(range(len(keys))); ax.set_xticklabels(keys, rotation=45, fontsize=6, ha='right')
        ax.set_yticks(range(len(crows))); ax.set_yticklabels([r['champion'] for r in crows])
        ax.set_title('Sensibilità causale stato-CAM → param (Spearman; >0 = logica appresa)'); plt.colorbar(im, ax=ax)
        savefig(D, 'causal.png')
    # fig 3: HEATMAP NRMSE stratificato
    sdf = pd.DataFrame(sframes)
    if len(sdf):
        sdf['nrmse_mean'] = sdf[['nrmse_' + c for c in PN]].mean(axis=1)
        piv = sdf.pivot_table(index='champion', columns='scenario', values='nrmse_mean')
        fig, ax = plt.subplots(figsize=(max(7, 0.9 * piv.shape[1]), 0.6 * piv.shape[0] + 2))
        im = ax.imshow(piv.values, aspect='auto', cmap='YlOrRd')
        ax.set_xticks(range(piv.shape[1])); ax.set_xticklabels(piv.columns, rotation=40, fontsize=7)
        ax.set_yticks(range(piv.shape[0])); ax.set_yticklabels(list(piv.index))
        for i in range(piv.shape[0]):
            for j in range(piv.shape[1]):
                ax.text(j, i, '%.2f' % piv.values[i, j], ha='center', va='center', fontsize=6)
        ax.set_title('NRMSE per scenario (media canali)'); plt.colorbar(im, ax=ax); savefig(D, 'nrmse_stratified.png')
    # fig 4: naturalisticity (KS) + calibration (gap RMSPE)
    if ncrows:
        fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
        ax[0].bar([r['champion'] for r in ncrows], [r['ks_time_gap'] for r in ncrows], color=[COLOR[r['champion']] for r in ncrows])
        ax[0].set_title('Naturalisticity: KS time-gap (↓ = più umano)'); ax[0].tick_params(axis='x', rotation=20)
        ax[1].bar([r['champion'] for r in ncrows], [r['gap_rmspe_mean'] for r in ncrows], color=[COLOR[r['champion']] for r in ncrows])
        ax[1].axhspan(0.08, 0.12, color='green', alpha=0.12, label='floor rumore umano')
        ax[1].set_title('Calibration: gap RMSPE (↓ meglio)'); ax[1].legend(fontsize=7); ax[1].tick_params(axis='x', rotation=20)
        plt.suptitle('04 — Naturalisticity + Calibration'); savefig(D, 'naturalisticity_calibration.png')
    display(pd.DataFrame(fim_rows)); display(pd.DataFrame(ncrows))
"""

QUANT = r"""# Cell 6 -- QUANTIZZAZIONE ESAUSTIVA: fixed+po2, 2-12 bit, degrado per-parametro, ablazione pesi PO2 on/off
from scripts.closed_loop_identify import eval_quantization, identify
from utils.quantize import QuantParamModel
D = '05_Quantization'
if done(D, 'quantization.csv'):
    print('[SKIP] quantization'); display(pd.read_csv(os.path.join(RESULTS, D, 'quantization.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    BITS = (12, 8, 6, 4, 3, 2)
    rows = []; pp_rows = []; abl_rows = []
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    for alias in AVAIL:
        m = MODELS[alias]
        for mode, ls in [('fixed', '-'), ('po2', '--')]:
            q = eval_quantization(m, CACHE_DATA, frac_bits_list=BITS, n_drivers=15, mode=mode)
            xs = [str(c['frac_bits']) for c in q['curve']]
            ax[0].plot(xs, [c['id_err_mean'] for c in q['curve']], 'o', ls=ls, color=COLOR[alias],
                       label='%s(%s)' % (alias, mode), alpha=0.85)
            ax[1].plot(xs, [c['collision_rate'] for c in q['curve']], 's', ls=ls, color=COLOR[alias], alpha=0.85)
            for c in q['curve']:
                rows.append({'champion': alias, 'mode': mode, 'frac_bits': c['frac_bits'],
                             'id_err_mean': c['id_err_mean'], 'collision_rate': c['collision_rate'],
                             'min_ttc_p5': c['min_ttc_p5']})
        # degrado PER-PARAMETRO a 4-bit fixed (vs float)
        Xs = [torch.tensor(it['x'][:50][None], dtype=torch.float32) for it in CACHE_DATA['val'][:15]]
        pf = np.array([identify(m, x) for x in Xs])
        q4 = QuantParamModel(m, frac_bits=4, mode='fixed'); pq = np.array([identify(q4, x) for x in Xs])
        pp = {'champion': alias}
        for i, c in enumerate(PN):
            pp['dparam_' + c] = float(np.mean(np.abs(pq[:, i] - pf[:, i])))
        pp_rows.append(pp)
        # ablazione pesi PO2 on(nominale QAT) vs off(float): quanto il QAT ha assorbito la quant dei pesi
        import os as _o
        prev = _o.environ.get('PO2_ENABLED')
        errs = {}
        for tagn, envv in [('po2_on', '1'), ('po2_off', '0')]:
            _o.environ['PO2_ENABLED'] = envv
            pw = np.array([identify(m, x) for x in Xs])
            true = np.array([[it['params'][c] for c in PN] for it in CACHE_DATA['val'][:15]])
            errs[tagn] = float(np.mean(np.abs(pw - true)))
        if prev is None:
            _o.environ.pop('PO2_ENABLED', None)
        else:
            _o.environ['PO2_ENABLED'] = prev
        abl_rows.append({'champion': alias, **errs, 'delta_qat_absorbed': errs['po2_on'] - errs['po2_off']})
    savecsv(D, 'quantization.csv', rows); savecsv(D, 'quant_perparam.csv', pp_rows); savecsv(D, 'quant_weight_ablation.csv', abl_rows)
    ax[0].set_xlabel('frac_bits (← meno bit)'); ax[0].set_ylabel('errore identificazione')
    ax[0].set_title('Degrado id. vs bit (linea piena=fixed, tratteg.=po2)'); ax[0].legend(fontsize=6, ncol=2); ax[0].invert_xaxis()
    ax[1].set_xlabel('frac_bits'); ax[1].set_ylabel('collision_rate'); ax[1].set_title('Sicurezza vs bit'); ax[1].invert_xaxis()
    plt.suptitle('05 — Quantizzazione (fixed + po2, 2-12 bit)'); savefig(D, 'quantization.png')
    # fig 2: degrado per-parametro a 4-bit (heatmap)
    if pp_rows:
        Mp = np.array([[r['dparam_' + c] for c in PN] for r in pp_rows])
        fig, ax = plt.subplots(figsize=(8, 0.6 * len(pp_rows) + 2))
        im = ax.imshow(Mp, aspect='auto', cmap='YlOrRd')
        ax.set_xticks(range(len(PN))); ax.set_xticklabels(PN); ax.set_yticks(range(len(pp_rows)))
        ax.set_yticklabels([r['champion'] for r in pp_rows])
        for i in range(len(pp_rows)):
            for j in range(len(PN)):
                ax.text(j, i, '%.3f' % Mp[i, j], ha='center', va='center', fontsize=7)
        ax.set_title('|Δparam| a 4-bit fixed (vs float) — per parametro'); plt.colorbar(im, ax=ax)
        savefig(D, 'quant_perparam.png')
    # fig 3: ablazione pesi PO2 on/off
    if abl_rows:
        fig, ax = plt.subplots(figsize=(8, 4.2)); xx = np.arange(len(abl_rows)); w = 0.38
        ax.bar(xx - w / 2, [r['po2_off'] for r in abl_rows], w, label='pesi float (PO2 off)', color='#4c72b0')
        ax.bar(xx + w / 2, [r['po2_on'] for r in abl_rows], w, label='pesi po2 (nominale QAT)', color='#dd8452')
        ax.set_xticks(xx); ax.set_xticklabels([r['champion'] for r in abl_rows], rotation=20)
        ax.set_ylabel('errore identificazione |Δ| vs veri'); ax.set_title('Ablazione pesi PO2: il QAT ha già assorbito la quant.?')
        ax.legend(fontsize=8); savefig(D, 'quant_weight_ablation.png')
    display(pd.DataFrame(rows))
"""

V2X = r"""# Cell 7 -- ROBUSTEZZA V2X ESAUSTIVA: PDR/latenza/jitter/Gilbert/blackout + 3 hold_mode + AoI (oracolo sotto canale)
from scripts.closed_loop_identify import v2x_robustness_sweep
D = '06_V2X_Robustness'
if done(D, 'v2x.csv'):
    print('[SKIP] v2x'); display(pd.read_csv(os.path.join(RESULTS, D, 'v2x.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    rows = []; sweeps = {}
    for alias in AVAIL:
        sw = v2x_robustness_sweep(MODELS[alias], CACHE_DATA, n_drivers=15)
        sweeps[alias] = sw
        for r in sw:
            rows.append({'champion': alias, **r})
    savecsv(D, 'v2x.csv', rows)
    def _ax(sw, axis):
        return [r for r in sw if r['axis'] == axis]
    # fig 1: PDR e latenza (SNN + oracolo di riferimento)
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    for alias in AVAIL:
        pdr = _ax(sweeps[alias], 'pdr'); lat = _ax(sweeps[alias], 'latency')
        ax[0].plot([r['val'] for r in pdr], [r['collision_rate'] for r in pdr], 'o-', color=COLOR[alias], label=alias)
        ax[1].plot([r['val'] for r in lat], [r['min_ttc_p5'] for r in lat], 's-', color=COLOR[alias], label=alias)
    # oracolo (media sui champion, stesso canale) come banda di riferimento
    orc = _ax(sweeps[AVAIL[0]], 'pdr')
    ax[0].plot([r['val'] for r in orc], [r['collision_rate_oracle'] for r in orc], 'k--', label='oracolo', alpha=0.7)
    ax[0].set_xlabel('PDR'); ax[0].set_ylabel('collision_rate'); ax[0].set_title('Degrado vs packet-delivery-ratio'); ax[0].legend(fontsize=7); ax[0].invert_xaxis()
    ax[1].set_xlabel('latenza [step]'); ax[1].set_ylabel('p5 min_TTC'); ax[1].set_title('Margine vs latenza CAM'); ax[1].legend(fontsize=7)
    plt.suptitle('06 — Robustezza V2X (graceful vs catastrofico)'); savefig(D, 'v2x.png')
    # fig 2: HOLD_MODE — la figura che risponde al masking di hold-last (dead_reckon vs hold_last vs blind)
    fig, ax = plt.subplots(figsize=(8.5, 4.4)); modes = ['hold_last', 'dead_reckon', 'blind']
    xx = np.arange(len(modes)); w = 0.8 / max(len(AVAIL), 1)
    for k, alias in enumerate(AVAIL):
        hm = {r['val']: r['collision_rate'] for r in _ax(sweeps[alias], 'hold_mode')}
        ax.bar(xx + k * w, [hm.get(mo, np.nan) for mo in modes], w, label=alias, color=COLOR[alias])
    ax.set_xticks(xx + 0.4); ax.set_xticklabels(modes); ax.set_ylabel('collision_rate (PDR=0.5)')
    ax.set_title('Gestione del pacchetto perso: hold_last maschera, blind lo scopre, dead_reckon lo compensa')
    ax.legend(fontsize=7); savefig(D, 'v2x_holdmode.png')
    # fig 3: AoI-vs-safety (staleness -> rischio) su TUTTI i punti con aoi definito
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for alias in AVAIL:
        pts = [(r['aoi'], r['collision_rate']) for r in sweeps[alias] if r.get('aoi') is not None]
        if pts:
            xs, ys = zip(*sorted(pts)); ax.scatter(xs, ys, color=COLOR[alias], label=alias, alpha=0.8)
    ax.set_xlabel('Age-of-Information media [s]'); ax.set_ylabel('collision_rate')
    ax.set_title('Rischio vs staleness dell’informazione (AoI) — ciò che PDR i.i.d. mascherava'); ax.legend(fontsize=7)
    savefig(D, 'v2x_aoi.png')
    # fig 4: burst (Gilbert/jitter/blackout)
    fig, ax = plt.subplots(figsize=(9, 4.4))
    stress = []
    for alias in AVAIL:
        for r in sweeps[alias]:
            if r['axis'] in ('gilbert', 'jitter', 'blackout'):
                stress.append((alias, '%s:%s' % (r['axis'], r['val']), r['collision_rate']))
    if stress:
        labels = sorted(set(l for _, l, _ in stress)); xx = np.arange(len(labels)); w = 0.8 / max(len(AVAIL), 1)
        for k, alias in enumerate(AVAIL):
            dd = {l: c for a, l, c in stress if a == alias}
            ax.bar(xx + k * w, [dd.get(l, np.nan) for l in labels], w, label=alias, color=COLOR[alias])
        ax.set_xticks(xx + 0.4); ax.set_xticklabels(labels, rotation=30, fontsize=7, ha='right')
        ax.set_ylabel('collision_rate'); ax.set_title('Stress a raffica (Gilbert / jitter / blackout)'); ax.legend(fontsize=7)
        savefig(D, 'v2x_burst.png')
    display(pd.DataFrame(rows))
"""

PLANT = r"""# Cell 8 -- DINAMICA VEICOLO (plant L4): ideale / bagnato / ghiaccio, con oracolo di riferimento
from scripts.closed_loop_identify import eval_safety
D = '07_VehicleDynamics'
if done(D, 'plant.csv'):
    print('[SKIP] plant'); display(pd.read_csv(os.path.join(RESULTS, D, 'plant.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    CONDS = [('ideale', None), ('bagnato', {'tau_act': 0.4, 'mu': 0.5}), ('ghiaccio', {'tau_act': 0.5, 'mu': 0.3})]
    rows = []; oracle_row = {'champion': ORACLE}
    for alias in AVAIL:
        row = {'champion': alias}
        for cname, pl in CONDS:
            r = eval_safety(MODELS[alias], CACHE_DATA, n_drivers=15, rich=True, tail=True, plant=pl)
            row['min_gap_' + cname] = r['rich']['snn']['min_gap']['mean']
            row['collision_' + cname] = r['rich']['snn']['collision']['rate']
            row['brake_margin_' + cname] = r['rich']['snn']['brake_margin_min']['mean']
            oracle_row['min_gap_' + cname] = r['rich']['oracle']['min_gap']['mean']
            oracle_row['collision_' + cname] = r['rich']['oracle']['collision']['rate']
            oracle_row['brake_margin_' + cname] = r['rich']['oracle']['brake_margin_min']['mean']
        rows.append(row)
    allrows = [oracle_row] + rows; savecsv(D, 'plant.csv', allrows)
    order = [ORACLE] + AVAIL; cols = [COLOR.get(a, OCOL) for a in order]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6)); cnames = [c for c, _ in CONDS]; xx = np.arange(len(order)); w = 0.8 / len(cnames)
    lut = {r['champion']: r for r in allrows}
    for j, cname in enumerate(cnames):
        ax[0].bar(xx + j * w, [lut[a]['min_gap_' + cname] for a in order], w, label=cname, alpha=0.8)
        ax[1].bar(xx + j * w, [lut[a]['brake_margin_' + cname] for a in order], w, label=cname, alpha=0.8)
    for a in (ax[0], ax[1]):
        a.set_xticks(xx + 0.3); a.set_xticklabels(order, rotation=20)
    ax[0].set_ylabel('min-gap [m]'); ax[0].set_title('min-gap vs aderenza (ideale/bagnato/ghiaccio)'); ax[0].legend(fontsize=7)
    ax[1].axhline(0, color='red', ls='--'); ax[1].set_ylabel('brake_margin_min [m]'); ax[1].set_title('Margine evitabilità vs plant'); ax[1].legend(fontsize=7)
    plt.suptitle('07 — Dinamica veicolo reale (plant L4)'); savefig(D, 'plant.png')
    display(pd.DataFrame(allrows))
"""

ENERGY = r"""# Cell 9 -- ENERGIA + DIAGNOSTICA RETE: energy_estimate + dead/sat/eff_rank/raggio spettrale + RASTER reale
from utils.snn_showcase import energy_estimate
from utils.net_diagnostics import net_diagnostics
D = '08_Energy_Spiking'
if done(D, 'energy.csv'):
    print('[SKIP] energy'); display(pd.read_csv(os.path.join(RESULTS, D, 'energy.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    rows = []
    xb = torch.tensor(np.array([it['x'][:50] for it in CACHE_DATA['val'][:8]]), dtype=torch.float32)
    xr = torch.tensor(CACHE_DATA['val'][0]['x'][:60][None], dtype=torch.float32)   # 1 seq per il raster
    for alias in AVAIL:
        m = MODELS[alias]
        try:
            with torch.no_grad():
                rate = m.forward_sequence_with_stats(xb)[1].detach().cpu().numpy()   # (B,T) spike-rate
            H = int(getattr(m, 'hidden_size', 32)); Tt = rate.shape[1]
            spikes_TH = np.tile(rate.mean(0).reshape(-1, 1), (1, H))
            en = energy_estimate(spikes_TH, m)
            diag, raster = net_diagnostics(m, xr, max_steps=60)   # raster reale per-neurone
            rows.append({'champion': alias, 'E_snn_nJ': en['E_snn_nJ'], 'E_ann_nJ': en['E_ann_nJ'],
                         'advantage_x': en['energy_advantage_x'], 'mean_spike_rate_pct': en['mean_spike_rate_pct'],
                         'total_spikes': en['total_spikes'], 'dead_frac': diag['dead_frac'], 'sat_frac': diag['sat_frac'],
                         'eff_rank_activity': diag['eff_rank_activity'], 'spectral_radius': diag.get('spectral_radius', float('nan')),
                         'spectral_norm': diag.get('spectral_norm', float('nan')), 'eff_rank_W': diag.get('eff_rank_W', float('nan'))})
            # RASTER reale (scatter) per OGNI champion
            fig, ax = plt.subplots(figsize=(10, 3.2))
            if raster.size and raster.shape[0] > 2:
                ys, xs = np.where(raster.T > 0.5); ax.scatter(xs, ys, s=2, color=COLOR[alias])
            ax.set_ylabel('neurone'); ax.set_xlabel('tick'); ax.set_title('%s — raster spike (dead=%.0f%%, eff_rank=%.1f)'
                                                                          % (alias, 100 * diag['dead_frac'], diag['eff_rank_activity']))
            savefig(os.path.join(D, 'raster'), 'raster_%s.png' % alias.replace(' ', '_'))
        except Exception as e:
            print('[skip energia %s] %s' % (alias, str(e)[:90]))
    if rows:
        df = pd.DataFrame(rows)
        fig, ax = plt.subplots(1, 3, figsize=(16, 4.4))
        ax[0].bar(df['champion'], df['E_snn_nJ'], color=[COLOR[a] for a in df['champion']]); ax[0].set_title('Energia SNN [nJ]'); ax[0].tick_params(axis='x', rotation=20)
        ax[1].bar(df['champion'], df['advantage_x'], color=[COLOR[a] for a in df['champion']]); ax[1].set_title('× vantaggio vs ANN'); ax[1].tick_params(axis='x', rotation=20)
        w = 0.38; xx = np.arange(len(df))
        ax[2].bar(xx - w / 2, df['dead_frac'], w, label='dead', color='#888'); ax[2].bar(xx + w / 2, df['sat_frac'], w, label='sat', color='#c44')
        ax[2].set_xticks(xx); ax[2].set_xticklabels(df['champion'], rotation=20); ax[2].set_title('Neuroni morti / saturi'); ax[2].legend(fontsize=7)
        plt.suptitle('08 — Energia + diagnostica rete'); savefig(D, 'energy.png')
        savecsv(D, 'energy.csv', rows); display(df)
    else:
        print('[energia] nessun champion ha prodotto spike utilizzabili')
"""

TRAJ = r"""# Cell 10 -- TRAIETTORIE: gap/vel/accel su scenari chiave (coda inclusi), champion + oracolo sovrapposti
from scripts.closed_loop_identify import identify
from utils.closed_loop_eval import simulate, build_scenarios
D = '09_Trajectories'
if done(D, 'traj_hard_brake.png'):
    print('[SKIP] traiettorie')
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    it = CACHE_DATA['val'][0]; pgt = np.array([it['params'][c] for c in PN], dtype=np.float32)
    scen = {s[0]: s for s in build_scenarios(pgt, N=400, rng=np.random.default_rng(7), include_tail=True)}
    ids = {alias: identify(MODELS[alias], torch.tensor(it['x'][:50][None], dtype=torch.float32)) for alias in AVAIL}
    for sname in ['hard_brake', 'cut_in', 'panic_stop', 'aggressive_cut_in', 'stop_and_go']:
        if sname not in scen:
            continue
        _, vl, s_i, v_i, cut = scen[sname]
        fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
        tr_o = simulate(None, pgt, vl, s_i, v_i, cut_in=cut); tc = np.arange(len(tr_o['s'])) * 0.1
        axes[0].plot(tc, tr_o['s'], color=OCOL, lw=2, label='Master Splinter')
        axes[1].plot(tc, tr_o['v'], color=OCOL, lw=2); axes[2].plot(tc, tr_o['a_ego'], color=OCOL, lw=2)
        for alias in AVAIL:
            tr = simulate(None, ids[alias], vl, s_i, v_i, cut_in=cut); t = np.arange(len(tr['s'])) * 0.1
            axes[0].plot(t, tr['s'], color=COLOR[alias], label=alias, alpha=0.85)
            axes[1].plot(t, tr['v'], color=COLOR[alias], alpha=0.85); axes[2].plot(t, tr['a_ego'], color=COLOR[alias], alpha=0.85)
        axes[0].axhline(0, color='red', ls=':'); axes[0].set_ylabel('gap [m]'); axes[0].legend(fontsize=7, ncol=3)
        axes[1].set_ylabel('vel ego [m/s]'); axes[2].set_ylabel('accel [m/s²]'); axes[2].set_xlabel('t [s]')
        plt.suptitle('09 — Traiettorie: %s' % sname); savefig(D, 'traj_%s.png' % sname)
    print('traiettorie salvate')
"""

REACH = r"""# Cell 11 -- REACHABILITY: frontiera worst-case (gap minimo sicuro vs Δv) — oracolo vs SNN (margine consumato)
from scripts.closed_loop_identify import reachability_frontier
D = '10_Reachability'
if done(D, 'reachability.csv'):
    print('[SKIP] reachability'); display(pd.read_csv(os.path.join(RESULTS, D, 'reachability.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    rows = []; fig, ax = plt.subplots(figsize=(8, 5))
    for alias in AVAIL:
        rf = reachability_frontier(MODELS[alias], CACHE_DATA, n_drivers=10)
        dvs = sorted(rf['min_safe_gap']['snn'].keys())
        ax.plot(dvs, [rf['min_safe_gap']['snn'][d] for d in dvs], 'o-', color=COLOR[alias], label='%s (SNN)' % alias)
        for d in dvs:
            rows.append({'champion': alias, 'dv0': d, 'min_safe_gap_snn': rf['min_safe_gap']['snn'][d],
                         'min_safe_gap_oracle': rf['min_safe_gap']['oracle'][d], 'worst_decel': rf['worst_decel']})
    # oracolo (uguale per tutti: dipende dai param veri) come riferimento
    rf0 = reachability_frontier(MODELS[AVAIL[0]], CACHE_DATA, n_drivers=10)
    dvs = sorted(rf0['min_safe_gap']['oracle'].keys())
    ax.plot(dvs, [rf0['min_safe_gap']['oracle'][d] for d in dvs], 'k--', lw=2, label='oracolo (param veri)')
    ax.set_xlabel('Δv iniziale [m/s]'); ax.set_ylabel('gap minimo SENZA collisione [m]')
    ax.set_title('Reachability worst-case (leader frena a %.0f m/s²): gap SNN > oracolo = margine consumato' % rf0['worst_decel'])
    ax.legend(fontsize=7); savefig(D, 'reachability.png')
    savecsv(D, 'reachability.csv', rows); display(pd.DataFrame(rows))
"""

BREAKDOWN = r"""# Cell 12 -- BREAKDOWN: curva di rottura (collisione vs severita' leader-decel e vs gap cut-in) — oracolo vs SNN
from scripts.closed_loop_identify import breakdown_curve
D = '11_Breakdown'
if done(D, 'breakdown.csv'):
    print('[SKIP] breakdown'); display(pd.read_csv(os.path.join(RESULTS, D, 'breakdown.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    rows = []; fig, ax = plt.subplots(1, 2, figsize=(13, 4.6)); oracle_drawn = False
    for alias in AVAIL:
        bd = breakdown_curve(MODELS[alias], CACHE_DATA, n_drivers=15)
        ax[0].plot([p['decel'] for p in bd['panic']], [p['snn'] for p in bd['panic']], 'o-', color=COLOR[alias], label=alias)
        ax[1].plot([p['gap'] for p in bd['cut_in']], [p['snn'] for p in bd['cut_in']], 's-', color=COLOR[alias], label=alias)
        if not oracle_drawn:
            ax[0].plot([p['decel'] for p in bd['panic']], [p['oracle'] for p in bd['panic']], 'k--', label='oracolo', alpha=0.7)
            ax[1].plot([p['gap'] for p in bd['cut_in']], [p['oracle'] for p in bd['cut_in']], 'k--', alpha=0.7); oracle_drawn = True
        for p in bd['panic']:
            rows.append({'champion': alias, 'axis': 'panic_decel', 'val': p['decel'], 'collision_snn': p['snn'], 'collision_oracle': p['oracle']})
        for p in bd['cut_in']:
            rows.append({'champion': alias, 'axis': 'cut_in_gap', 'val': p['gap'], 'collision_snn': p['snn'], 'collision_oracle': p['oracle']})
    ax[0].set_xlabel('decel leader [m/s²]'); ax[0].set_ylabel('collision_rate'); ax[0].set_title('Rottura vs frenata leader'); ax[0].legend(fontsize=7)
    ax[1].set_xlabel('gap cut-in [m]'); ax[1].set_ylabel('collision_rate'); ax[1].set_title('Rottura vs cut-in ravvicinato'); ax[1].legend(fontsize=7); ax[1].invert_xaxis()
    plt.suptitle('11 — Breakdown (dove la sicurezza cede)'); savefig(D, 'breakdown.png')
    savecsv(D, 'breakdown.csv', rows); display(pd.DataFrame(rows))
"""

MESO = r"""# Cell -- MESO: plotone (12 veicoli) string stability + heatmap spazio-tempo + scorecard scalare (oracolo + champion)
from utils.platoon_eval import simulate_platoon as sim_plat_meso, platoon_metrics
from scripts.closed_loop_identify import identify
D = '12_Mesoscopic'
if done(D, 'meso_summary.csv'):
    print('[SKIP] meso'); display(pd.read_csv(os.path.join(RESULTS, D, 'meso_summary.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    it0 = CACHE_DATA['val'][0]; PGT0 = np.array([it0['params'][c] for c in PN], dtype=np.float32)
    xwin = torch.tensor(it0['x'][:50][None], dtype=torch.float32)
    N_PLAT = 12; NSTEP = 500; t = np.arange(NSTEP); v_set = 0.7 * PGT0[0]
    v_leader = v_set + 0.15 * v_set * np.sin(2 * np.pi * t / 100.0)   # perturbazione sinusoidale in testa
    # eventprop-safe: param IDENTIFICATI (forward_sequence) + model=None; forward_step per-step non regge l eventprop
    sources = [(ORACLE, PGT0)] + [(a, np.asarray(identify(MODELS[a], xwin), dtype=np.float32)) for a in AVAIL]
    rows = []; recs = {}
    for src, params in sources:
        rec = sim_plat_meso(None, params, N_PLAT, v_leader); mt = platoon_metrics(rec); mt['source'] = src
        rows.append(mt); recs[src] = rec
    dfm = pd.DataFrame(rows)
    dfm.drop(columns=['gain_per_vehicle']).to_csv(os.path.join(sub(D), 'meso_summary.csv'), index=False)
    # fig1: gain per veicolo (1 linea per fonte = leggibile, no spaghetti)
    fig, ax = plt.subplots(figsize=(8.5, 5))
    for r in rows:
        g = r['gain_per_vehicle']
        ax.plot(range(1, len(g) + 1), g, 'o-', color=COLOR.get(r['source'], OCOL),
                label='%s (h2t=%.2f)' % (r['source'], r['head_to_tail_gain']))
    ax.axhline(1.0, color='r', ls='--', label='soglia instabilità')
    ax.set_xlabel('indice veicolo (1=testa → coda)'); ax.set_ylabel('gain |H|_i = A_i / A_leader')
    ax.set_title('MESO — string stability: gain per veicolo (<1 e decrescente = stabile)'); ax.legend(fontsize=7)
    savefig(D, 'meso_gain.png')
    # fig2: heatmap spazio-tempo velocità (small multiples oracolo+champion) -> l'onda
    fig, axes = plt.subplots(1, len(sources), figsize=(3.6 * len(sources), 4), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, (src, _) in zip(axes, sources):
        im = ax.imshow(recs[src]['v'].T, aspect='auto', origin='lower', cmap='viridis', extent=[0, NSTEP * 0.1, 1, N_PLAT])
        ax.set_title(src, fontsize=9); ax.set_xlabel('t [s]'); ax.grid(False)
    axes[0].set_ylabel('indice veicolo'); fig.colorbar(im, ax=list(axes), label='v [m/s]', fraction=0.02)
    plt.suptitle('MESO — velocità spazio-tempo: perturbazione lungo la catena'); savefig(D, 'meso_spacetime.png')
    # fig3: scorecard scalare (bars per fonte)
    scal = ['head_to_tail_gain', 'max_amplification', 'min_gap_platoon', 'min_ttc_platoon', 'rms_accel_mean', 'max_decel_platoon']
    fig, axes = plt.subplots(2, 3, figsize=(15, 7))
    for ax, col in zip(axes.ravel(), scal):
        ax.bar(range(len(dfm)), dfm[col].values, color=[COLOR.get(s, OCOL) for s in dfm['source']])
        ax.set_xticks(range(len(dfm))); ax.set_xticklabels(dfm['source'], rotation=25, ha='right', fontsize=7); ax.set_title(col, fontsize=9)
    plt.suptitle('MESO — metriche scalari del plotone (string stability + sicurezza catena + comfort)'); savefig(D, 'meso_scorecard.png')
    display(dfm.drop(columns=['gain_per_vehicle']))
"""

MACRO = r"""# Cell -- MACRO: diagramma fondamentale Q(ρ)/V(ρ) + capacità + onde stop&go su anello (oracolo + champion)
from utils.platoon_eval import fundamental_diagram, simulate_ring
D = '13_Macroscopic'
if done(D, 'macro_summary.csv'):
    print('[SKIP] macro'); display(pd.read_csv(os.path.join(RESULTS, D, 'macro_summary.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    from scripts.closed_loop_identify import identify
    it0 = CACHE_DATA['val'][0]; PGT0 = np.array([it0['params'][c] for c in PN], dtype=np.float32)
    xwin = torch.tensor(it0['x'][:50][None], dtype=torch.float32)
    DENS = [8, 15, 25, 35, 45, 60, 80, 100, 120, 150]   # veh/km
    # eventprop-safe: param IDENTIFICATI + model=None
    sources = [(ORACLE, PGT0)] + [(a, np.asarray(identify(MODELS[a], xwin), dtype=np.float32)) for a in AVAIL]
    fig, ax = plt.subplots(1, 2, figsize=(14, 5)); rows = []
    for src, params in sources:
        fd = fundamental_diagram(None, params, DENS, ring_length=1000.0, n_steps=600)
        c = COLOR.get(src, OCOL)
        rho = [p['rho_veh_km'] for p in fd]; Q = [p['Q_veh_h'] for p in fd]; V = [p['V_km_h'] for p in fd]
        ax[0].plot(rho, Q, 'o-', color=c, label=src); ax[1].plot(rho, V, 'o-', color=c, label=src)
        qmax = max(fd, key=lambda p: p['Q_veh_h'])
        ax[0].scatter([qmax['rho_veh_km']], [qmax['Q_veh_h']], marker='*', s=180, color=c, edgecolor='k', zorder=5)
        jam = [p for p in fd if p['V_km_h'] < 3.0]
        rows.append({'source': src, 'capacity_veh_h': qmax['Q_veh_h'], 'rho_crit_veh_km': qmax['rho_veh_km'],
                     'v_free_km_h': fd[0]['V_km_h'], 'rho_jam_veh_km': (jam[0]['rho_veh_km'] if jam else float('nan')),
                     'first_unstable_rho': next((p['rho_veh_km'] for p in fd if p['unstable']), float('nan'))})
    ax[0].set_xlabel('densità ρ [veh/km]'); ax[0].set_ylabel('flusso Q [veh/h]')
    ax[0].set_title('Diagramma fondamentale Q(ρ): libero → ★capacità → congestione'); ax[0].legend(fontsize=7)
    ax[1].set_xlabel('densità ρ [veh/km]'); ax[1].set_ylabel('velocità V [km/h]'); ax[1].set_title('Relazione V(ρ)'); ax[1].legend(fontsize=7)
    plt.suptitle('MACRO — diagramma fondamentale (SNN vs oracolo)'); savefig(D, 'macro_fundamental_diagram.png')
    dfM = pd.DataFrame(rows); dfM.to_csv(os.path.join(sub(D), 'macro_summary.csv'), index=False)
    # scorecard scalare
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    for ax_, col in zip(axes, ['capacity_veh_h', 'rho_crit_veh_km', 'v_free_km_h', 'rho_jam_veh_km']):
        ax_.bar(range(len(dfM)), dfM[col].values, color=[COLOR.get(s, OCOL) for s in dfM['source']])
        ax_.set_xticks(range(len(dfM))); ax_.set_xticklabels(dfM['source'], rotation=25, ha='right', fontsize=7); ax_.set_title(col, fontsize=9)
    plt.suptitle('MACRO — capacità / densità critica / v-free / densità di jam'); savefig(D, 'macro_scorecard.png')
    # onde stop&go a densità congestionata (small multiples)
    fig, axes = plt.subplots(1, len(sources), figsize=(3.6 * len(sources), 4), sharey=True); axes = np.atleast_1d(axes)
    n_cong = max(2, int(60 / 1000.0 * 1000.0))
    for ax_, (src, params) in zip(axes, sources):
        rec = simulate_ring(None, params, n_cong, 1000.0, 800)
        im = ax_.imshow(rec['v'].T, aspect='auto', origin='lower', cmap='RdYlGn', extent=[0, 800 * 0.1, 0, rec['n']])
        ax_.set_title(src, fontsize=9); ax_.set_xlabel('t [s]'); ax_.grid(False)
    axes[0].set_ylabel('veicolo'); fig.colorbar(im, ax=list(axes), label='v [m/s]', fraction=0.02)
    plt.suptitle('MACRO — onde stop&go a ρ=60 veh/km (verde=veloce, rosso=fermo)'); savefig(D, 'macro_stopandgo.png')
    display(dfM)
"""

SHOWCASE = r"""# Cell -- VETRINA "come spara la rete": raster + scenario + phase-plane + GIF (eventprop-safe)
from utils.snn_showcase import capture_run
from utils.net_diagnostics import spike_raster
from scripts.closed_loop_identify import identify
from utils.closed_loop_eval import simulate, build_scenarios
D = '14_Showcase'
if not AVAIL:
    print('[skip] nessun champion disponibile')
elif done(D, 'showcase_%s.png' % AVAIL[0].replace(' ', '_')):
    print('[SKIP] showcase')
else:
    it0 = CACHE_DATA['val'][0]; pgt = np.array([it0['params'][c] for c in PN], dtype=np.float32)
    xwin = torch.tensor(it0['x'][:60][None], dtype=torch.float32)
    scen = {s[0]: s for s in build_scenarios(pgt, N=400, rng=np.random.default_rng(1), include_tail=True)}
    _, vl, s_i, v_i, cut = scen['cut_in']
    for alias in AVAIL:
        try:
            m = MODELS[alias]
            raster = spike_raster(m, xwin, max_steps=60)                        # (K,H), eventprop-safe (no forward_step)
            idp = np.asarray(identify(m, torch.tensor(it0['x'][:50][None], dtype=torch.float32)), dtype=np.float32)
            traj = simulate(None, idp, vl, s_i, v_i, cut_in=cut)               # traiettoria closed-loop (param identificati)
            T = len(traj['s']); tt = np.arange(T) * 0.1
            H = raster.shape[1] if raster.size else int(getattr(m, 'hidden_size', 32))
            spr = float(raster.mean() * 100) if raster.size else float('nan')
            nact = int((raster.sum(0) > 0).sum()) if raster.size else 0
            fig = plt.figure(figsize=(15, 9)); gs = fig.add_gridspec(3, 2, height_ratios=[2, 1, 1])
            axr = fig.add_subplot(gs[0, :]); axr.grid(False)
            if raster.size:
                ys, xs = np.where(raster.T > 0.5); axr.scatter(xs, ys, s=2, color=COLOR[alias])
            axr.set_ylabel('neurone hidden'); axr.set_xlabel('tick interno')
            axr.set_title('%s — RASTER spike (sparsità %.1f%%, %d/%d neuroni attivi)' % (alias, spr, nact, H))
            a1 = fig.add_subplot(gs[1, 0])
            if raster.size: a1.plot(np.arange(raster.shape[0]), raster.sum(1), color=COLOR[alias])
            a1.set_ylabel('spike/tick'); a1.set_title('Attività totale (sparsità reale)')
            a2 = fig.add_subplot(gs[1, 1]); a2.plot(tt, traj['s'], label='gap [m]'); a2.plot(tt, traj['a_ego'], label='a_ego')
            a2.legend(fontsize=7); a2.set_title('Scenario cut-in: gap + accel')
            if cut: a2.axvline(cut[0] * 0.1, color='r', ls='--', alpha=0.6)
            a3 = fig.add_subplot(gs[2, 0]); a3.plot(tt, traj['v'], label='v ego'); a3.plot(tt, traj['vl'], label='v leader')
            a3.legend(fontsize=7); a3.set_xlabel('t [s]'); a3.set_title('Velocità ego vs leader')
            a4 = fig.add_subplot(gs[2, 1]); a4.plot(traj['dv'], traj['s'], color=COLOR[alias])
            a4.set_xlabel('Δv = v−vl [m/s]'); a4.set_ylabel('gap [m]'); a4.set_title('Phase-plane (traiettoria negli stati)')
            plt.suptitle('14 — Vetrina "come spara la rete": %s' % alias, fontweight='bold')
            savefig(D, 'showcase_%s.png' % alias.replace(' ', '_'))
        except Exception as e:
            print('[skip showcase %s] %s' % (alias, str(e)[:100]))
    # GIF "in diretta" (best-effort) per il primo champion: auto in moto + cursore sincronizzato sul raster
    try:
        import importlib.util as _imu, sys as _sys, subprocess as _sp
        if _imu.find_spec('PIL') is None:
            _sp.run([_sys.executable, '-m', 'pip', 'install', '-q', 'pillow'], check=True)
        from matplotlib import animation
        alias = AVAIL[0]; traj, spikes = capture_run(MODELS[alias], pgt, vl, s_i, v_i, cut_in=cut)
        x_ego = np.cumsum(traj['v']) * 0.1; x_lead = x_ego + traj['s']; Tn = len(x_ego); step = max(1, Tn // 120)
        fig, (axc, axs) = plt.subplots(2, 1, figsize=(11, 5), gridspec_kw={'height_ratios': [1, 2]}); axc.grid(False); axs.grid(False)
        axc.set_ylim(-1, 1); axc.set_yticks([]); axc.set_xlabel('posizione [m]')
        (ego,) = axc.plot([], [], 's', ms=15, color=COLOR[alias], label='ego (SNN)')
        (lead,) = axc.plot([], [], 's', ms=15, color='tab:red', label='leader'); axc.legend(loc='upper right', fontsize=8)
        txt = axc.text(0.02, 0.8, '', transform=axc.transAxes, fontsize=9)
        axs.imshow(spikes.T, aspect='auto', origin='lower', cmap='Greys', extent=[0, Tn * 0.1, 0, spikes.shape[1]])
        (cur,) = axs.plot([], [], color='r', lw=1.3); axs.set_xlabel('t [s]'); axs.set_ylabel('neurone')
        def _frame(k):
            i = min(k * step, Tn - 1)
            ego.set_data([x_ego[i]], [0]); lead.set_data([x_lead[i]], [0]); axc.set_xlim(x_ego[i] - 12, x_lead[i] + 22)
            txt.set_text('t=%.1fs  gap=%.1fm  v=%.1f m/s' % (i * 0.1, traj['s'][i], traj['v'][i]))
            cur.set_data([i * 0.1, i * 0.1], [0, spikes.shape[1]]); return ego, lead, txt, cur
        anim = animation.FuncAnimation(fig, _frame, frames=Tn // step, blit=True)
        anim.save(os.path.join(sub(D), 'showcase_live_%s.gif' % alias.replace(' ', '_')), writer=animation.PillowWriter(fps=15))
        plt.close(fig); print('GIF vetrina salvata per', alias)
    except Exception as e:
        print('[skip GIF]', str(e)[:120])
    print('vetrina completata')
"""

SCORECARD = r"""# Cell 13 -- SCORECARD cross-champion: tabella consolidata + radar (oracolo incluso sugli assi closed-loop)
D = '00_Scorecard'
def _read(d, f):
    p = os.path.join(RESULTS, d, f); return pd.read_csv(p) if os.path.isfile(p) else None
acc = _read('01_Accuracy', 'accuracy.csv'); saf = _read('02_Safety_ClosedLoop', 'safety.csv')
strg = _read('03_StringStability', 'string_stability.csv'); en = _read('08_Energy_Spiking', 'energy.csv')
master = []
for alias in [ORACLE] + AVAIL:
    row = {'champion': alias}
    if acc is not None and (acc.champion == alias).any():
        row['accuracy_pct'] = float(acc[acc.champion == alias]['accuracy_pct'].iloc[0])
    elif alias == ORACLE:
        row['accuracy_pct'] = 100.0
    if saf is not None and (saf.champion == alias).any():
        s = saf[saf.champion == alias].iloc[0]
        row['min_gap'] = float(s['min_gap']); row['brake_margin_min'] = float(s['brake_margin_min'])
        row['collision_rate'] = float(s['collision_rate'])
    if strg is not None and (strg.champion == alias).any():
        row['head_to_tail'] = float(strg[strg.champion == alias]['head_to_tail'].iloc[0])
    if en is not None and (en.champion == alias).any():
        row['energy_adv_x'] = float(en[en.champion == alias]['advantage_x'].iloc[0])
    master.append(row)
savecsv(D, 'master_scorecard.csv', master)
dfM = pd.DataFrame(master)
axes_r = [c for c in ['accuracy_pct', 'min_gap', 'brake_margin_min', 'head_to_tail', 'energy_adv_x'] if c in dfM.columns]
LBL = {'accuracy_pct': 'accuracy ↑', 'min_gap': 'min-gap ↑', 'brake_margin_min': 'margine ↑',
       'head_to_tail': 'string-stab ↑ (h2t↓)', 'energy_adv_x': 'energia × ↑'}
lower_better = {'head_to_tail'}
if len(axes_r) >= 3 and len(dfM) >= 1:
    ang = np.linspace(0, 2 * np.pi, len(axes_r), endpoint=False).tolist(); ang += ang[:1]
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    bounds = {c: (float(dfM[c].astype(float).min()), float(dfM[c].astype(float).max())) for c in axes_r}
    for _, r in dfM.iterrows():
        vals = []
        for c in axes_r:
            v = r.get(c); lo, hi = bounds[c]
            if v is None or not np.isfinite(v):
                x = 0.5
            elif hi == lo:
                x = 0.5
            else:
                x = (float(v) - lo) / (hi - lo)
            vals.append(1 - x if c in lower_better else x)
        vals += vals[:1]
        ls = '--' if r['champion'] == ORACLE else '-'
        ax.plot(ang, vals, ls, color=COLOR.get(r['champion'], OCOL), label=r['champion'])
        ax.fill(ang, vals, color=COLOR.get(r['champion'], OCOL), alpha=0.06)
    ax.set_ylim(0, 1); ax.set_xticks(ang[:-1]); ax.set_xticklabels([LBL.get(c, c) for c in axes_r], fontsize=8)
    ax.set_title('00 — Scorecard (normalizzato per asse; 1=migliore; oracolo tratteggiato)')
    ax.legend(loc='upper right', fontsize=7, bbox_to_anchor=(1.28, 1.1)); savefig(D, 'radar.png')
display(dfM)
"""

PUSH = r"""# Cell 14 -- push dei risultati v3 (robusto, retry; rieseguibile)
import subprocess, time
def _git(*a): return subprocess.run(['git', *a], capture_output=True, text=True)
_git('add', RESULTS)
r = _git('commit', '-m', 'eval v3 TURTLE POWER (esaustivo): SSM estese+comfort+tracking, string 3-nozioni, quant fixed+po2+ablazione, V2X hold_mode+AoI+burst, diagnostica rete, reachability, breakdown, oracolo esteso')
if r.returncode != 0 and 'nothing to commit' in (r.stdout + r.stderr):
    print('niente da committare')
else:
    for k in range(5):
        _git('pull', '--no-rebase', '--no-edit', 'origin', BRANCH)
        p = _git('push', 'origin', BRANCH)
        if p.returncode == 0:
            print('push OK'); break
        print('push retry', k, p.stderr[-160:]); time.sleep(3)
"""

cells = [
    MD(INTRO, 'intro'), C(ENV, 'env'),
    C(resilient(ACCURACY, 'accuracy'), 'accuracy'), C(resilient(CLOSEDLOOP, 'closedloop'), 'closedloop'),
    C(resilient(STRING, 'string'), 'string'), C(resilient(IDENT, 'ident'), 'ident'),
    C(resilient(QUANT, 'quant'), 'quant'), C(resilient(V2X, 'v2x'), 'v2x'),
    C(resilient(PLANT, 'plant'), 'plant'), C(resilient(ENERGY, 'energy'), 'energy'),
    C(resilient(TRAJ, 'traj'), 'traj'), C(resilient(REACH, 'reach'), 'reach'),
    C(resilient(BREAKDOWN, 'breakdown'), 'breakdown'),
    C(resilient(MESO, 'meso'), 'meso'), C(resilient(MACRO, 'macro'), 'macro'),
    C(resilient(SHOWCASE, 'showcase'), 'showcase'),
    C(resilient(SCORECARD, 'scorecard'), 'scorecard'),
    C(PUSH, 'push'),
]
nb = {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                                   'language_info': {'name': 'python', 'version': '3.10'},
                                   'execution': {'timeout': -1, 'allow_errors': True}},
      'nbformat': 4, 'nbformat_minor': 5}

out = os.path.join(ROOT, 'Eval_v3_TURTLE_POWER.ipynb')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print('Wrote', out, '(%d celle)' % len(cells))
