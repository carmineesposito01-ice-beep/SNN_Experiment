"""Builder del notebook EVALUATE v3 — 'TURTLE POWER!!!' (4 champion + oracolo, evaluate 6-tier completo).

Genera Eval_v3_TURTLE_POWER.ipynb. Gira su AZURE (Python 3.10, checkpoint in checkpoints/<tag>/best_model.pt).
Per OGNI dimensione produce DATI (csv) + FIGURE (png). Resiliente: ogni sezione SALTA se l'output esiste
(re-run multi-ora sicuro); cella col modello assente -> skip con grazia; push finale.

Champion (alias / tag / colore):
  Master Splinter  oracolo                  grigio   #7f7f7f   (riferimento, param veri)
  Raffaello        R33_C2_A1_T12_fix      rosso    #d62728   (Prodigy baseline, aggressivo)
  Leonardo         LS3_PEAK_R0_launch_d03   azzurro  #1f9ed1   (champion BPTT, conservativo)
  Donatello        PE_t05_gp0002            viola    #9467bd   (best-NRMSE, massimizza un asse)
  Michelangelo     A_lr1e2_t06_r16          arancione#ff7f0e   (best-Adam, equilibrato)

Output in results/evaluate/v3_TURTLE_POWER!!!/ : 00_Scorecard, 01_Accuracy ... 09_Trajectories (per-dimensione),
08_Energy_Spiking/raster/ (per-champion), README.md (legenda). I confronti cross-champion sono dentro ogni dimensione.
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


INTRO = """# 🐢 EVALUATE v3 — TURTLE POWER!!!

Validazione esaustiva (qualitativa + quantitativa) di **4 champion + oracolo** dello studio EventProp,
con l'evaluate 6-tier completo. Per ogni dimensione: **dati (csv) + figure (png)**.

| Alias | Tag | Colore | Carattere |
|---|---|---|---|
| **Master Splinter** | *oracolo* | grigio | riferimento (parametri veri) |
| **Raffaello** | `R33_C2_A1_T12_fix` | rosso | Prodigy baseline, aggressivo |
| **Leonardo** | `LS3_PEAK_R0_launch_d03` | azzurro | champion BPTT, conservativo (safety) |
| **Donatello** | `PE_t05_gp0002` | viola | best-NRMSE (massimizza un asse, sacrifica il resto) |
| **Michelangelo** | `A_lr1e2_t06_r16` | arancione | best-Adam (equilibrato, l'alternativo) |

Dimensioni: Accuracy/identificazione · Closed-loop sicurezza (rich, scenari di coda, **margine continuo**) ·
String stability (plotone) · Identificabilità (FIM) · Quantizzazione FPGA · Robustezza V2X · Dinamica veicolo (plant) ·
Energia/spiking SNN · Traiettorie · **Scorecard** cross-champion.

**Resiliente**: ogni sezione salta se l'output esiste già (re-run multi-ora sicuro); le celle col modello
saltano con grazia se il checkpoint manca; push finale.
"""

ENV = r"""# Cell 1 -- ENV + champion + loader robusto + helper figure/cartelle
import os, sys, json, glob, subprocess, importlib.util as _imu
sys.path.insert(0, os.getcwd())
for pkg in ['pandas', 'matplotlib', 'numpy', 'torch']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
import numpy as np, pandas as pd, torch
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
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

# alias, tag, colore, descrizione, variant build_model (verificato sull'eval vecchio: R33/LS3 = 'baseline')
CHAMPIONS = [
    ('Master Splinter', '__oracle__',             '#7f7f7f', 'oracolo (param veri)',         None),
    ('Raffaello',       'R33_C2_A1_T12_fix',      '#d62728', 'Prodigy baseline, aggressivo', 'baseline'),
    ('Leonardo',        'LS3_PEAK_R0_launch_d03', '#1f9ed1', 'champion BPTT, conservativo',  'baseline'),
    ('Donatello',       'PE_t05_gp0002',          '#9467bd', 'best-NRMSE',                   'eventprop_alif_full'),
    ('Michelangelo',    'A_lr1e2_t06_r16',        '#ff7f0e', 'best-Adam, equilibrato',       'eventprop_alif_full'),
]
COLOR = {a: c for a, _, c, _, _ in CHAMPIONS}
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
    # Loader robusto: variante dedotta dallo SCHEMA delle chiavi del checkpoint (autorevole), rank/hidden da
    # rec_U, + VALIDAZIONE che il readout (layer_out) sia stato caricato (altrimenti resterebbe random in
    # silenzio con strict=False -> output spazzatura). 'baseline' usa layer_out.fc_weight, eventprop layer_out.weight.
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
    if any('layer_out' in k for k in getattr(res, 'missing_keys', [])):  # readout NON caricato -> non valido
        print('   [WARN] %s: readout non caricato (variant=%s) -> scartato' % (tag, v))
        return None
    m.eval()
    m._loaded_variant = v
    return m

# carica i 4 modelli (resiliente; variant per-champion)
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

# README leggibile dall'umano nella cartella risultati (legenda + mappa cartelle + direzione metriche)
_readme = ['# Eval v3 — TURTLE POWER!!!\n', '\n## Champion\n',
           '| alias | tag | colore | carattere |\n|---|---|---|---|\n']
for a, t, c, d, _ in CHAMPIONS:
    _readme.append('| %s | `%s` | %s | %s |\n' % (a, t, c, d))
_readme += ['\n## Cartelle (per dimensione)\n',
            '- `00_Scorecard` confronto cross-champion (radar + tabella master)\n',
            '- `01_Accuracy` NRMSE per-canale / accuracy (↓ meglio)\n',
            '- `02_Safety_ClosedLoop` min-gap ↑, brake_margin_min ↑ (margine continuo, <0=inevitabile), TTC ↑, decel ↓, jerk ↓\n',
            '- `03_StringStability` head-to-tail ↓ (≤1=stabile), peak |Γ(ω)| ↓\n',
            '- `04_Identifiability` FIM (cond, sensibilità), causal, NRMSE stratificato\n',
            '- `05_Quantization` degrado float→fixed-point (deploy FPGA)\n',
            '- `06_V2X_Robustness` degrado vs PDR/latenza\n',
            '- `07_VehicleDynamics` plant reale (μ bagnato + lag attuatore)\n',
            '- `08_Energy_Spiking` energia SNN (nJ, ×vs ANN) + raster\n',
            '- `09_Trajectories` traiettorie per scenario\n',
            '\n`ERROR_<sez>.txt` (se presente) = quella sezione ha fallito; le altre proseguono.\n']
with open(os.path.join(RESULTS, 'README.md'), 'w', encoding='utf-8') as _f:
    _f.write(''.join(_readme))
"""

ACCURACY = r"""# Cell 2 -- ACCURACY / identificazione: NRMSE per-canale per champion (identify su cache comune)
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
    x = np.arange(len(PN)); w = 0.8 / max(len(rows), 1)
    for k, r in enumerate(rows):
        ax[0].bar(x + k * w, [r['nrmse_' + c] for c in PN], w, label=r['champion'], color=COLOR[r['champion']])
    ax[0].set_xticks(x + 0.4); ax[0].set_xticklabels(PN); ax[0].set_ylabel('NRMSE per-canale')
    ax[0].set_title('Accuracy per-canale (più basso = meglio)'); ax[0].legend(fontsize=7)
    ax[1].bar([r['champion'] for r in rows], [r['accuracy_pct'] for r in rows],
              color=[COLOR[r['champion']] for r in rows])
    ax[1].axhline(75, color='gray', ls=':'); ax[1].set_ylabel('accuracy ~ (1-NRMSE) [%]')
    ax[1].set_title('Accuracy media'); ax[1].tick_params(axis='x', rotation=20)
    plt.suptitle('01 — Accuracy / identificazione'); savefig(D, 'accuracy.png')
    savecsv(D, 'accuracy.csv', rows); display(dfA)
"""

CLOSEDLOOP = r"""# Cell 3 -- CLOSED-LOOP sicurezza (rich, scenari di coda) per champion + oracolo. Metriche CONTINUE.
from scripts.closed_loop_identify import eval_safety
D = '02_Safety_ClosedLoop'
if done(D, 'safety.csv'):
    print('[SKIP] safety'); display(pd.read_csv(os.path.join(RESULTS, D, 'safety.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    KEYS = ['min_gap', 'brake_margin_min', 'min_ttc', 'max_DRAC', 'max_decel', 'rms_jerk', 'impact_dv', 'collision']
    rows = []; per_scen = {}
    oracle_done = False
    for alias in AVAIL:
        r = eval_safety(MODELS[alias], CACHE_DATA, n_drivers=N_DRIVERS, rich=True, tail=True)
        rc = r['rich']
        def grab(d):
            o = {}
            for k in KEYS[:-1]:
                o[k] = d[k]['mean'] if k in d and 'mean' in d[k] else float('nan')
            o['collision_rate'] = d['collision']['rate']; o['collision_ub95'] = d['collision']['wilson_ub95']
            return o
        rows.append({'champion': alias, **grab(rc['snn'])})
        per_scen[alias] = rc['per_scenario']
        if not oracle_done:
            rows.insert(0, {'champion': 'Master Splinter', **grab(rc['oracle'])}); oracle_done = True
    df = pd.DataFrame(rows)
    # fig 1: scorecard barre (min_gap, brake_margin_min, min_ttc, max_decel, rms_jerk)
    metr = [('min_gap', 'min-gap [m] ↑'), ('brake_margin_min', 'margine evitabilità [m] ↑'),
            ('min_ttc', 'min TTC [s] ↑'), ('max_decel', 'max decel [m/s²] ↓'), ('rms_jerk', 'rms jerk ↓')]
    fig, axes = plt.subplots(1, len(metr), figsize=(4 * len(metr), 4.2))
    for ax, (k, ttl) in zip(axes, metr):
        vals = [(r['champion'], r.get(k, np.nan)) for r in rows]
        ax.bar([a for a, _ in vals], [v for _, v in vals], color=[COLOR.get(a, '#333') for a, _ in vals])
        ax.set_title(ttl, fontsize=9); ax.tick_params(axis='x', rotation=90, labelsize=6)
    plt.suptitle('02 — Closed-loop sicurezza/comfort (oracolo = Master Splinter)')
    savefig(D, 'safety_scorecard.png')
    # fig 2: margine continuo brake_margin_min (la metrica che NON satura)
    fig, ax = plt.subplots(figsize=(7, 4.4))
    ax.bar(df['champion'], df['brake_margin_min'], color=[COLOR.get(a, '#333') for a in df['champion']])
    ax.axhline(0, color='red', ls='--', lw=1, label='confine inevitabile')
    ax.set_ylabel('brake_margin_min [m] (con segno)'); ax.legend()
    ax.set_title('Margine di evitabilità fisica (continuo, non satura) — <0 = collisione inevitabile')
    ax.tick_params(axis='x', rotation=20); savefig(D, 'brake_margin.png')
    # fig 3: per-scenario min_gap heatmap (champion x scenario)
    scen = sorted(next(iter(per_scen.values())).keys())
    M = np.array([[per_scen[a][s]['snn']['min_gap']['mean'] for s in scen] for a in AVAIL])
    fig, ax = plt.subplots(figsize=(max(8, 0.9 * len(scen)), 0.6 * len(AVAIL) + 2))
    im = ax.imshow(M, aspect='auto', cmap='RdYlGn')
    ax.set_xticks(range(len(scen))); ax.set_xticklabels(scen, rotation=40, fontsize=7)
    ax.set_yticks(range(len(AVAIL))); ax.set_yticklabels(AVAIL)
    for i in range(len(AVAIL)):
        for j in range(len(scen)):
            ax.text(j, i, '%.1f' % M[i, j], ha='center', va='center', fontsize=6)
    ax.set_title('min-gap [m] per scenario (verde=sicuro)'); plt.colorbar(im, ax=ax)
    savefig(D, 'per_scenario_min_gap.png')
    savecsv(D, 'safety.csv', rows); display(df)
"""

STRING = r"""# Cell 4 -- STRING STABILITY (plotone N) per champion: head-to-tail + |Γ(ω)| + con latenza CAM
from scripts.closed_loop_identify import eval_string_stability
D = '03_StringStability'
if done(D, 'string_stability.csv'):
    print('[SKIP] string stability'); display(pd.read_csv(os.path.join(RESULTS, D, 'string_stability.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    rows = []
    for alias in AVAIL:
        r0 = eval_string_stability(MODELS[alias], CACHE_DATA, N=8, n_platoons=5, hetero=True)
        rL = eval_string_stability(MODELS[alias], CACHE_DATA, N=8, n_platoons=5, hetero=True, latency_steps=2)
        rows.append({'champion': alias, 'head_to_tail': r0['head_to_tail_mean'],
                     'peak_gain': r0['peak_gain_mean'], 'frac_stable': r0['frac_strict_stable'],
                     'mean_T': r0['mean_T'], 'head_to_tail_lat': rL['head_to_tail_mean'],
                     'peak_gain_lat': rL['peak_gain_mean']})
    df = pd.DataFrame(rows)
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    xx = np.arange(len(df)); w = 0.35
    ax[0].bar(xx - w / 2, df['head_to_tail'], w, label='senza latenza', color=[COLOR[a] for a in df['champion']])
    ax[0].bar(xx + w / 2, df['head_to_tail_lat'], w, label='latenza CAM', alpha=0.55,
              color=[COLOR[a] for a in df['champion']])
    ax[0].axhline(1.0, color='red', ls='--', label='string-stable ≤1')
    ax[0].set_xticks(xx); ax[0].set_xticklabels(df['champion'], rotation=20)
    ax[0].set_ylabel('head-to-tail gain'); ax[0].set_title('Amplificazione testa→coda (≤1 = stabile)'); ax[0].legend(fontsize=7)
    ax[1].bar(df['champion'], df['peak_gain'], color=[COLOR[a] for a in df['champion']])
    ax[1].axhline(1.0, color='red', ls='--'); ax[1].set_ylabel('peak |Γ(ω)|')
    ax[1].set_title('Picco funzione di trasferimento (≤1 = stabile in banda)'); ax[1].tick_params(axis='x', rotation=20)
    plt.suptitle('03 — String stability (plotone 8 veicoli, eterogeneo)'); savefig(D, 'string_stability.png')
    savecsv(D, 'string_stability.csv', rows); display(df)
"""

IDENT = r"""# Cell 5 -- IDENTIFICABILITÀ: FIM (una volta, è proprietà dei dati) + causal/NRMSE-stratificato per champion
from utils.identifiability import (practical_identifiability, persistent_excitation,
                                   causal_sensitivity, nrmse_stratified)
D = '04_Identifiability'
if done(D, 'fim.csv'):
    print('[SKIP] identifiability'); display(pd.read_csv(os.path.join(RESULTS, D, 'fim.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    pi = practical_identifiability(CACHE_DATA, n=N_DRIVERS)
    pe = persistent_excitation(CACHE_DATA, n=N_DRIVERS)
    fim_rows = [{'metric': 'cond_mean', 'value': pi['cond_mean']},
                {'metric': 'cond_p95', 'value': pi['cond_p95']},
                {'metric': 'rank_FIM', 'value': pe['rank']},
                {'metric': 'least_identifiable', 'value': pi['least_identifiable']},
                {'metric': 'under_excited', 'value': ','.join(pe['under_excited']) or '(nessuno)'}]
    savecsv(D, 'fim.csv', fim_rows)
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.4))
    ax[0].bar(PN, [pi['sensitivity_mean'][c] for c in PN], color='slateblue')
    ax[0].set_title('Sensibilità FIM per-param (bassa = mal identificabile)'); ax[0].set_ylabel('||∂a/∂param||')
    ax[1].bar(PN, [pe['sensitivity'][c] for c in PN], color='teal')
    ax[1].set_title('FIM cumulata: eccitazione per-param (rank=%d)' % pe['rank'])
    plt.suptitle('04 — Identificabilità (FIM): cond=%.1e, meno identif.=%s' % (pi['cond_mean'], pi['least_identifiable']))
    savefig(D, 'fim.png')
    # causal + nrmse stratificato per champion
    crows = []; sframes = []
    for alias in AVAIL:
        cs = causal_sensitivity(MODELS[alias], CACHE_DATA, n=N_DRIVERS)
        crows.append({'champion': alias, **cs})
        ns = nrmse_stratified(MODELS[alias], CACHE_DATA, n=min(200, len(CACHE_DATA['val'])))
        for sc in ns:
            sframes.append({'champion': alias, 'scenario': sc, **{('nrmse_' + c): ns[sc][c] for c in PN}})
    savecsv(D, 'causal_sensitivity.csv', crows)
    savecsv(D, 'nrmse_stratified.csv', sframes)
    # FIGURA: heatmap NRMSE stratificato (champion x scenario, media canali)
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
        ax.set_title('NRMSE per scenario (media canali) per champion'); plt.colorbar(im, ax=ax)
        savefig(D, 'nrmse_stratified.png')
    # FIGURA: sensibilità causale per champion (var_vl->T atteso >0 = logica appresa)
    if crows:
        keys = [k for k in crows[0] if '->' in k]
        x = np.arange(len(keys)); w = 0.8 / max(len(crows), 1)
        fig, ax = plt.subplots(figsize=(10, 4.4))
        for k, r in enumerate(crows):
            ax.bar(x + k * w, [r.get(kk, np.nan) for kk in keys], w, label=r['champion'], color=COLOR.get(r['champion'], '#333'))
        ax.set_xticks(x + 0.4); ax.set_xticklabels(keys, rotation=40, fontsize=6); ax.axhline(0, color='k', lw=0.6)
        ax.set_ylabel('Spearman'); ax.set_title('Sensibilità causale stato-CAM → param'); ax.legend(fontsize=6)
        savefig(D, 'causal.png')
    display(pd.DataFrame(fim_rows)); display(pd.DataFrame(crows))
"""

QUANT = r"""# Cell 6 -- QUANTIZZAZIONE FPGA: float vs fixed-point Qm.n per champion (+ gemello V2X)
from scripts.closed_loop_identify import eval_quantization
D = '05_Quantization'
if done(D, 'quantization.csv'):
    print('[SKIP] quantization'); display(pd.read_csv(os.path.join(RESULTS, D, 'quantization.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    rows = []
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    for alias in AVAIL:
        q = eval_quantization(MODELS[alias], CACHE_DATA, frac_bits_list=(12, 8, 6, 4), n_drivers=15)
        xs = [str(c['frac_bits']) for c in q['curve']]
        ax[0].plot(xs, [c['id_err_mean'] for c in q['curve']], 'o-', color=COLOR[alias], label=alias)
        ax[1].plot(xs, [c['collision_rate'] for c in q['curve']], 's-', color=COLOR[alias], label=alias)
        for c in q['curve']:
            rows.append({'champion': alias, 'frac_bits': c['frac_bits'], 'id_err_mean': c['id_err_mean'],
                         'collision_rate': c['collision_rate'], 'min_ttc_p5': c['min_ttc_p5']})
    savecsv(D, 'quantization.csv', rows)
    ax[0].set_xlabel('frac_bits (← meno bit)'); ax[0].set_ylabel('errore identificazione'); ax[0].set_title('Degrado identificazione vs quantizzazione'); ax[0].legend(fontsize=7); ax[0].invert_xaxis()
    ax[1].set_xlabel('frac_bits'); ax[1].set_ylabel('collision_rate'); ax[1].set_title('Sicurezza vs quantizzazione'); ax[1].legend(fontsize=7); ax[1].invert_xaxis()
    plt.suptitle('05 — Quantizzazione fixed-point (deploy FPGA)'); savefig(D, 'quantization.png')
    display(pd.DataFrame(rows))
"""

V2X = r"""# Cell 7 -- ROBUSTEZZA V2X: degrado graceful-vs-catastrofico vs PDR e latenza, per champion
from scripts.closed_loop_identify import v2x_robustness_sweep
D = '06_V2X_Robustness'
if done(D, 'v2x.csv'):
    print('[SKIP] v2x'); display(pd.read_csv(os.path.join(RESULTS, D, 'v2x.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    rows = []
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    for alias in AVAIL:
        sw = v2x_robustness_sweep(MODELS[alias], CACHE_DATA, n_drivers=15)
        pdr = [r for r in sw if r['axis'] == 'pdr']; lat = [r for r in sw if r['axis'] == 'latency']
        ax[0].plot([r['val'] for r in pdr], [r['collision_rate'] for r in pdr], 'o-', color=COLOR[alias], label=alias)
        ax[1].plot([r['val'] for r in lat], [r['min_ttc_p5'] for r in lat], 's-', color=COLOR[alias], label=alias)
        for r in sw:
            rows.append({'champion': alias, **r})
    savecsv(D, 'v2x.csv', rows)
    ax[0].set_xlabel('PDR'); ax[0].set_ylabel('collision_rate'); ax[0].set_title('Degrado vs packet-delivery-ratio'); ax[0].legend(fontsize=7); ax[0].invert_xaxis()
    ax[1].set_xlabel('latenza [step]'); ax[1].set_ylabel('p5 min_TTC'); ax[1].set_title('Margine vs latenza CAM'); ax[1].legend(fontsize=7)
    plt.suptitle('06 — Robustezza rete V2X (graceful vs catastrofico)'); savefig(D, 'v2x.png')
    display(pd.DataFrame(rows))
"""

PLANT = r"""# Cell 8 -- DINAMICA VEICOLO (plant L4): ablation con/senza lag attuatore + μ aderenza, per champion
from scripts.closed_loop_identify import eval_safety
D = '07_VehicleDynamics'
if done(D, 'plant.csv'):
    print('[SKIP] plant'); display(pd.read_csv(os.path.join(RESULTS, D, 'plant.csv')))
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    PLANT_WET = {'tau_act': 0.4, 'mu': 0.5}     # asfalto bagnato + lag attuatore 0.4s
    rows = []
    for alias in AVAIL:
        base = eval_safety(MODELS[alias], CACHE_DATA, n_drivers=15, rich=True, tail=True)['rich']['snn']
        wet = eval_safety(MODELS[alias], CACHE_DATA, n_drivers=15, rich=True, tail=True, plant=PLANT_WET)['rich']['snn']
        rows.append({'champion': alias,
                     'min_gap_ideal': base['min_gap']['mean'], 'min_gap_wet': wet['min_gap']['mean'],
                     'collision_ideal': base['collision']['rate'], 'collision_wet': wet['collision']['rate'],
                     'brake_margin_ideal': base['brake_margin_min']['mean'], 'brake_margin_wet': wet['brake_margin_min']['mean']})
    df = pd.DataFrame(rows); xx = np.arange(len(df)); w = 0.38
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    ax[0].bar(xx - w / 2, df['min_gap_ideal'], w, label='ideale', color=[COLOR[a] for a in df['champion']])
    ax[0].bar(xx + w / 2, df['min_gap_wet'], w, label='bagnato+lag', alpha=0.55, color=[COLOR[a] for a in df['champion']])
    ax[0].set_xticks(xx); ax[0].set_xticklabels(df['champion'], rotation=20); ax[0].set_ylabel('min-gap [m]')
    ax[0].set_title('min-gap: ideale vs plant reale (bagnato μ0.5 + lag 0.4s)'); ax[0].legend(fontsize=7)
    ax[1].bar(xx - w / 2, df['brake_margin_ideal'], w, label='ideale', color=[COLOR[a] for a in df['champion']])
    ax[1].bar(xx + w / 2, df['brake_margin_wet'], w, label='bagnato+lag', alpha=0.55, color=[COLOR[a] for a in df['champion']])
    ax[1].axhline(0, color='red', ls='--'); ax[1].set_xticks(xx); ax[1].set_xticklabels(df['champion'], rotation=20)
    ax[1].set_ylabel('brake_margin_min [m]'); ax[1].set_title('Margine evitabilità sotto plant reale'); ax[1].legend(fontsize=7)
    plt.suptitle('07 — Dinamica veicolo reale (plant L4)'); savefig(D, 'plant.png')
    savecsv(D, 'plant.csv', rows); display(df)
"""

ENERGY = r"""# Cell 9 -- ENERGIA / SPIKING SNN. Fonte-spike UNIFORME = forward_sequence_with_stats (tutti i modelli);
# capture_run (vero raster per-neurone) solo dove compatibile (baseline), altrimenti la curva di spike-rate.
from utils.snn_showcase import energy_estimate
D = '08_Energy_Spiking'
if done(D, 'energy.png') or done(D, 'energy.csv'):
    print('[SKIP] energy')
elif not AVAIL:
    print('[skip] nessun champion disponibile')
else:
    rows = []
    xb = torch.tensor(np.array([it['x'][:50] for it in CACHE_DATA['val'][:8]]), dtype=torch.float32)  # input comune
    for alias in AVAIL:
        m = MODELS[alias]
        try:
            with torch.no_grad():
                rate = m.forward_sequence_with_stats(xb)[1].detach().cpu().numpy()   # (B,T) spike-rate medio/step
            H = int(getattr(m, 'hidden_size', 32)); Tt = rate.shape[1]
            spikes_TH = np.tile(rate.mean(0).reshape(-1, 1), (1, H))   # (T,H): somma = spike totali attesi
            en = energy_estimate(spikes_TH, m)
            rows.append({'champion': alias, 'E_snn_nJ': en['E_snn_nJ'], 'E_ann_nJ': en['E_ann_nJ'],
                         'advantage_x': en['energy_advantage_x'], 'mean_spike_rate_pct': en['mean_spike_rate_pct'],
                         'total_spikes': en['total_spikes']})
            # raster: capture_run se compatibile (baseline), altrimenti curva spike-rate
            fig, ax = plt.subplots(figsize=(10, 3.2)); true_raster = False
            try:
                from utils.snn_showcase import capture_run
                from utils.closed_loop_eval import _equilibrium_init
                it0 = CACHE_DATA['val'][0]; pgt = np.array([it0['params'][c] for c in PN], dtype=np.float32)
                vs = 0.7 * float(pgt[0]); N = 300; vl = np.full(N, vs); vl[N // 2:] = 0.45 * float(pgt[0])
                s_i, v_i = _equilibrium_init(pgt, vs)
                _, sp = capture_run(m, pgt, vl, s_i, v_i, cut_in=(N // 2, max(vs, 6.0)))
                if getattr(sp, 'ndim', 0) == 2 and sp.shape[0] > 2:
                    ys, xs = np.where(sp.T > 0); ax.scatter(xs * 0.1, ys, s=2, color=COLOR[alias])
                    ax.set_ylabel('neurone'); true_raster = True
            except Exception:
                pass
            if not true_raster:
                ax.plot(np.arange(Tt) * 0.1, rate.mean(0), color=COLOR[alias]); ax.set_ylabel('spike-rate medio')
            ax.set_xlabel('t [s]'); ax.set_title('%s — %s' % (alias, 'raster spike' if true_raster else 'spike-rate (eventprop)'))
            savefig(os.path.join(D, 'raster'), 'raster_%s.png' % alias.replace(' ', '_'))
        except Exception as e:
            print('[skip energia %s] %s' % (alias, str(e)[:90]))
    if rows:
        df = pd.DataFrame(rows)
        fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
        ax[0].bar(df['champion'], df['E_snn_nJ'], color=[COLOR[a] for a in df['champion']])
        ax[0].set_ylabel('energia SNN / inferenza [nJ]'); ax[0].set_title('Energia event-driven'); ax[0].tick_params(axis='x', rotation=20)
        ax[1].bar(df['champion'], df['advantage_x'], color=[COLOR[a] for a in df['champion']])
        ax[1].set_ylabel('× vantaggio vs ANN densa'); ax[1].set_title('Vantaggio energetico'); ax[1].tick_params(axis='x', rotation=20)
        plt.suptitle('08 — Energia / spiking SNN'); savefig(D, 'energy.png')
        savecsv(D, 'energy.csv', rows); display(df)   # csv come ULTIMA operazione (skip robusto)
    else:
        print('[energia] nessun champion ha prodotto spike utilizzabili')
"""

TRAJ = r"""# Cell 10 -- TRAIETTORIE: gap/vel/accel su scenari chiave, tutti i champion + oracolo sovrapposti
from scripts.closed_loop_identify import identify
from utils.closed_loop_eval import simulate, build_scenarios
D = '09_Trajectories'
if done(D, 'traj_hard_brake.png'):
    print('[SKIP] traiettorie')
else:
    it = CACHE_DATA['val'][0]; pgt = np.array([it['params'][c] for c in PN], dtype=np.float32)
    scen = {s[0]: s for s in build_scenarios(pgt, N=400, rng=np.random.default_rng(7), include_tail=True)}
    ids = {alias: identify(MODELS[alias], torch.tensor(it['x'][:50][None], dtype=torch.float32)) for alias in AVAIL}
    for sname in ['hard_brake', 'cut_in', 'panic_stop']:
        if sname not in scen:
            continue
        _, vl, s_i, v_i, cut = scen[sname]
        fig, axes = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
        tr_o = simulate(None, pgt, vl, s_i, v_i, cut_in=cut)
        tcommon = np.arange(len(tr_o['s'])) * 0.1
        axes[0].plot(tcommon, tr_o['s'], color='#7f7f7f', lw=2, label='Master Splinter')
        axes[1].plot(tcommon, tr_o['v'], color='#7f7f7f', lw=2)
        axes[2].plot(tcommon, tr_o['a_ego'], color='#7f7f7f', lw=2)
        for alias in AVAIL:
            tr = simulate(None, ids[alias], vl, s_i, v_i, cut_in=cut)
            t = np.arange(len(tr['s'])) * 0.1
            axes[0].plot(t, tr['s'], color=COLOR[alias], label=alias, alpha=0.85)
            axes[1].plot(t, tr['v'], color=COLOR[alias], alpha=0.85)
            axes[2].plot(t, tr['a_ego'], color=COLOR[alias], alpha=0.85)
        axes[0].axhline(0, color='red', ls=':'); axes[0].set_ylabel('gap [m]'); axes[0].legend(fontsize=7, ncol=3)
        axes[1].set_ylabel('vel ego [m/s]'); axes[2].set_ylabel('accel [m/s²]'); axes[2].set_xlabel('t [s]')
        plt.suptitle('09 — Traiettorie: %s' % sname); savefig(D, 'traj_%s.png' % sname)
    print('traiettorie salvate')
"""

SCORECARD = r"""# Cell 11 -- SCORECARD cross-champion: tabella consolidata + radar (chi vince su quale asse)
D = '00_Scorecard'
def _read(d, f):
    p = os.path.join(RESULTS, d, f); return pd.read_csv(p) if os.path.isfile(p) else None
acc = _read('01_Accuracy', 'accuracy.csv'); saf = _read('02_Safety_ClosedLoop', 'safety.csv')
strg = _read('03_StringStability', 'string_stability.csv'); en = _read('08_Energy_Spiking', 'energy.csv')
master = []
for alias in AVAIL:
    row = {'champion': alias}
    if acc is not None and (acc.champion == alias).any():
        row['accuracy_pct'] = float(acc[acc.champion == alias]['accuracy_pct'].iloc[0])
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
# radar: normalizza ogni asse a [0,1] (1=migliore), poi confronta
axes_r = [c for c in ['accuracy_pct', 'min_gap', 'brake_margin_min', 'head_to_tail', 'energy_adv_x'] if c in dfM.columns]
LBL = {'accuracy_pct': 'accuracy ↑', 'min_gap': 'min-gap ↑', 'brake_margin_min': 'margine ↑',
       'head_to_tail': 'string-stab ↑ (h2t↓)', 'energy_adv_x': 'energia × ↑'}
lower_better = {'head_to_tail'}   # head_to_tail piu' basso = meglio -> invertito (1 = migliore)
if len(axes_r) >= 3 and len(dfM) >= 1:
    ang = np.linspace(0, 2 * np.pi, len(axes_r), endpoint=False).tolist(); ang += ang[:1]
    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    bounds = {c: (float(dfM[c].astype(float).min()), float(dfM[c].astype(float).max())) for c in axes_r}
    for _, r in dfM.iterrows():
        vals = []
        for c in axes_r:
            v = r.get(c); lo, hi = bounds[c]
            if v is None or not np.isfinite(v):
                x = 0.5                       # dato mancante -> mezzo (non penalizza ne' premia)
            elif hi == lo:
                x = 0.5                       # un solo champion / asse costante -> mezzo (no collasso a 0)
            else:
                x = (float(v) - lo) / (hi - lo)
            vals.append(1 - x if c in lower_better else x)
        vals += vals[:1]
        ax.plot(ang, vals, color=COLOR[r['champion']], label=r['champion'])
        ax.fill(ang, vals, color=COLOR[r['champion']], alpha=0.08)
    ax.set_ylim(0, 1); ax.set_xticks(ang[:-1]); ax.set_xticklabels([LBL.get(c, c) for c in axes_r], fontsize=8)
    ax.set_title('00 — Scorecard (normalizzato per asse; 1=migliore)'); ax.legend(loc='upper right', fontsize=7, bbox_to_anchor=(1.28, 1.1))
    savefig(D, 'radar.png')
display(dfM)
"""

PUSH = r"""# Cell 12 -- push dei risultati v3 (robusto, retry; rieseguibile)
import subprocess, time
def _git(*a): return subprocess.run(['git', *a], capture_output=True, text=True)
_git('add', RESULTS)
r = _git('commit', '-m', 'eval v3 TURTLE POWER: 4 champion + oracolo (closed-loop/string/FIM/quant/V2X/plant/energia/scorecard)')
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
    C(resilient(TRAJ, 'traj'), 'traj'), C(resilient(SCORECARD, 'scorecard'), 'scorecard'),
    C(PUSH, 'push'),
]
nb = {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                                   'language_info': {'name': 'python', 'version': '3.10'},
                                   # CRITICO: disabilita il timeout per-cella di nbconvert (default 30s) — le
                                   # celle pesanti durano minuti/ore. Il CellTimeoutError e' sollevato fuori dal
                                   # try/except quindi 'resilient' non lo intercetterebbe -> il run morirebbe.
                                   'execution': {'timeout': -1, 'allow_errors': True}},
      'nbformat': 4, 'nbformat_minor': 5}

out = os.path.join(ROOT, 'Eval_v3_TURTLE_POWER.ipynb')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print('Wrote', out, '(%d celle)' % len(cells))
