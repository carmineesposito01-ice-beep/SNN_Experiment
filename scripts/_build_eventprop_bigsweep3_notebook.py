"""EventProp Big Sweep 3 — STUDIO ESAUSTIVO di chiusura (multi-giorno, ogni sezione con SKIP-se-fatto).

Chiude (verosimilmente) lo studio EventProp. Metrica PRIMARIA = val_data (fisica); NRMSE = lente
secondaria (e' una PINN). Lettura di Pareto vs champion, mai un "vincitore" su NRMSE da solo.

Arm: lr alto x target basso (+t0.4) x rank{8,16,24,32}, decode ON, + frontiera decode-OFF + MULTI-SEED
(robustezza) + BPTT_REF champion (riferimento). 50 ep, best-first, SKIP+RESUME.

Sezioni di analisi (OGNUNA salta se l'output esiste gia' -> resiliente a crash su run multi-giorno):
  DIAG        val_data (fisica) + NRMSE + heatmap + Pareto vs champion
  FULLLOSS    5 componenti PINN per-arm (data/phys/ou/bc/sr) dal log
  PARETO      scatter val_data vs NRMSE (la tensione, visualizzata)
  RANKCURVE   val_data vs rank + rank EFFETTIVO (U@V) -> plateau?
  SEEDVAR     varianza multi-seed (quanto e' robusto il risultato?)
  PERREGIME   val_data + NRMSE per scenario (dove sbaglia?)
  DIAGNOSTICS spectral radius, spike rate, neuroni morti, rank effettivo per-arm
  VALIDATE    Path B refit: NRMSE migliora MA degrada la fisica? (loss completa)
  CLOSEDLOOP  SICUREZZA: controllo coi parametri IDENTIFICATI vs oracolo (collisioni/min-gap)
  SYNTHESIS   tabella consolidata (val_data, NRMSE, loss, sicurezza) + verdetto Pareto
Output in results/EventProp_BigSweep3/.
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


INTRO = """# EventProp Big Sweep 3 — studio esaustivo di chiusura

Metrica **PRIMARIA = `val_data`** (fisica, ricostruzione accel); NRMSE = lente **secondaria** (e' una PINN).
Lettura di **Pareto** vs champion `LS3_d03` (val_data 0.1926 / NRMSE 0.258). Arm: lr alto x target basso
(+t0.4) x rank{8,16,24,32} decode ON + frontiera decode-OFF + **multi-seed** + **BPTT_REF**.

**Ogni sezione di analisi SALTA se il suo output esiste gia'** -> un crash su run multi-giorno non fa
ripartire da zero. Sezioni: DIAG, FULLLOSS, PARETO, RANKCURVE, SEEDVAR, PERREGIME, DIAGNOSTICS,
VALIDATE (Path B refit vs fisica), CLOSEDLOOP (sicurezza coi param identificati), **DATASET** (coverage
parametri + narrow-vs-wide: s0/b sono sotto-coperti nel dataset attuale -> dati piu' vari aiutano?), SYNTHESIS.
"""

ENV = """# Cell 1 -- ENV + helper condivisi
import sys, os, re, subprocess
import importlib.util as _imu
RESULTS = 'results/EventProp_BigSweep3'
BRANCH = 'EventProp_Study'
LAUNCH_MIX = 'highway:0.20,urban:0.15,truck:0.10,mixed:0.05,freeflow:0.15,launch:0.35'
CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'
_TMP_MSG = '/tmp/bigsweep3_msg.txt' if os.path.isdir('/tmp') else 'bigsweep3_msg.txt'
os.makedirs(RESULTS, exist_ok=True)
for pkg in ['pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
assert os.path.isfile(CACHE), 'missing cache: ' + CACHE
PN = ['v0', 'T', 's0', 'a', 'b']

def arm_rank(tag):
    m = re.search(r'_r(\\d+)', tag)
    return int(m.group(1)) if m else 16

def load_arm(tag):
    from scripts.decode_lut_calibrate import load_model
    p = 'checkpoints/' + tag + '/best_model.pt'
    return load_model(p, arm_rank(tag)) if os.path.isfile(p) else None

def log_path(tag):
    return RESULTS + '/' + tag + '/training_log.csv'

br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
print('[BigSweep3] ENV OK | branch =', br)
"""

CONFIG = """# Cell 2 -- arm: sfruttamento decode-ON + decode-OFF + multi-seed + champion
EPOCHS = 50
COMMON = ['--max_steps_per_epoch', '100', '--batch_size', '8', '--val_batch_size', '32',
          '--seq_len', '50', '--cf_hidden_size', '32', '--cf_max_delay', '6',
          '--cf_bit_shift', '3', '--lambda_data', '1.0', '--lambda_phys', '0.1', '--lambda_ou', '0.05',
          '--lambda_bc', '1.0', '--lambda_sr', '0.5', '--scenario_mix', LAUNCH_MIX, '--cut_in_ratio', '0.0',
          '--noise_scale', '0.0', '--po2_enabled', '1', '--n_train', '1500', '--n_val', '300',
          '--data_cache', CACHE, '--max_inf_streak', '99999', '--early_stop_patience', '0',
          '--max_epoch_explosion_streak', '3', '--epoch_explosion_threshold', '10000.0',
          '--epoch_explosion_frac', '0.5', '--grad_clip', 'agc', '--agc_lambda', '0.01']
DECODE = ['--cf_init_bias_shift', '1', '--cf_logit_tau_per_channel', '10.0,3.0,10.0,3.0,3.0']
SPEC = lambda t: ['--eventprop_lambda_spectral', '1.0', '--eventprop_spectral_target', str(t)]
CHAMP_VAL = 0.1926
CHAMP_NRMSE = {'v0': 0.240, 'T': 0.276, 's0': 0.172, 'a': 0.284, 'b': 0.316}
BS2_BEST = {'name': 'BS2_lr2e3_t06_r16', 'val': 0.2177,
            'nrmse': {'v0': 0.186, 'T': 0.187, 's0': 0.159, 'a': 0.261, 'b': 0.204}}

def _f(x):
    return str(x).replace('.', '').replace('-', '')

def adam(lr, t, rank, decode=True, seed=None):
    tag = 'A_lr' + _f(lr) + '_t' + _f(t) + '_r' + str(rank) + ('' if decode else '_noDEC') \\
          + ('' if seed is None else '_s' + str(seed))
    ov = ['--optimizer', 'adamw', '--lr', lr, '--max_lr', lr, '--scheduler', 'cosine_no_restart',
          '--cf_rank', str(rank)] + SPEC(t)
    if decode:
        ov = ov + DECODE
    if seed is not None:
        ov = ov + ['--seed', str(seed)]
    return (tag, 'eventprop_alif_full', ov)

# Champion BPTT (riferimento) -- config esatta LS3_d03
CHAMP = ['--optimizer', 'prodigy', '--lr', '0.5', '--max_lr', '0.5', '--scheduler', 'custom_restart',
         '--restart_T0', '12', '--restart_decay', '0.3', '--restart_warmup_epochs', '2',
         '--restart_adaptive', '0', '--restart_lr_after', '-1.0', '--prodigy_growth_rate', 'inf',
         '--prodigy_betas', '0.9,0.99', '--prodigy_d_coef', '1.0', '--prodigy_d0', '1e-6',
         '--prodigy_weight_decay', '0.01', '--prodigy_use_bias_correction', '1',
         '--prodigy_safeguard_warmup', '1', '--grad_clip', 'none', '--cf_rank', '8'] + DECODE
BPTT_REF = ('BPTT_REF', 'baseline', CHAMP)

ARMS = []
_seen = set()
def _add(a):
    if a[0] not in _seen:
        _seen.add(a[0]); ARMS.append(a)

_add(BPTT_REF)                                      # riferimento champion
_add(adam('7e-3', 0.5, 16))                         # best-atteso, primo
# A -- core decode ON: lr x target (incluso 0.4) x rank16
for _lr in ['7e-3', '5e-3', '1e-2']:
    for _t in [0.5, 0.6, 0.4]:
        _add(adam(_lr, _t, 16))
# B -- tetto lr
_add(adam('1.5e-2', 0.5, 16))
# C -- sweep rank (lr7e3 t05): rank16 gia' presente
for _r in [8, 24, 32]:
    _add(adam('7e-3', 0.5, _r))
# E -- frontiera decode-OFF (metro val_data)
for _lr in ['7e-3', '1e-2']:
    _add(adam(_lr, 0.5, 16, decode=False))
# S -- multi-seed del best-atteso (robustezza)
for _s in [1, 2, 3]:
    _add(adam('7e-3', 0.5, 16, seed=_s))
# DS -- studio dataset: best config (lr7e3 t05 r16) su narrow/wide/widebig, valutato sul COMMON wide-val
for _nm, _cp, _ntr in [('DS_narrow', 'data/cache_ds_narrow.pt', 1500),
                       ('DS_wide', 'data/cache_ds_wide.pt', 1500),
                       ('DS_widebig', 'data/cache_ds_widebig.pt', 3000)]:
    _ov = (['--optimizer', 'adamw', '--lr', '7e-3', '--max_lr', '7e-3', '--scheduler', 'cosine_no_restart',
            '--cf_rank', '16'] + SPEC(0.5) + DECODE + ['--data_cache', _cp, '--n_train', str(_ntr), '--n_val', '400'])
    _add((_nm, 'eventprop_alif_full', _ov))

print('BigSweep3:', len(ARMS), 'arm |',
      sum(1 for a in ARMS if a[0].startswith('A_') and 'noDEC' not in a[0] and '_s' not in a[0]), 'core decode-ON,',
      sum(1 for a in ARMS if 'noDEC' in a[0]), 'decode-OFF,',
      sum(1 for a in ARMS if '_s' in a[0]), 'multi-seed,',
      sum(1 for a in ARMS if a[0].startswith('DS_')), 'dataset-study, 1 BPTT_REF')
print([a[0] for a in ARMS])
"""

DATASETGEN = """# Cell 3b -- DATASETGEN: genera le cache dello studio dataset (wide-coverage). SKIP se esistono.
# Osservazione: nel generatore s0 e b NON sono jitterati (restano ai preset -> 3 valori) e v0/a coprono
# parzialmente il range. wide_params=True campiona TUTTI e 5 i param sull'intero range fisico.
# I 3 arm condividono lo STESSO wide-val -> confronto equo dell'identificazione sul range pieno.
import os
import torch
from data.generator import generate_dataset, parse_scenario_mix
from config import SEED as _SEED
mix = parse_scenario_mix(LAUNCH_MIX)
caches = {'data/cache_ds_narrow.pt': ('narrow', 1500),
          'data/cache_ds_wide.pt': ('wide', 1500),
          'data/cache_ds_widebig.pt': ('wide', 3000)}
missing = [p for p in caches if not os.path.isfile(p)]
if not missing:
    print('[SKIP] cache DS gia presenti')
else:
    wide_val = generate_dataset(400, base_seed=_SEED + 99, scenario_mix=mix, cut_in_ratio=0.0,
                                noise_scale=0.0, wide_params=True)
    cur = torch.load(CACHE, map_location='cpu', weights_only=False)
    for p in missing:
        kind, n = caches[p]
        train = cur['train'] if kind == 'narrow' else generate_dataset(
            n, base_seed=_SEED + 100 + n, scenario_mix=mix, cut_in_ratio=0.0, noise_scale=0.0, wide_params=True)
        torch.save({'train': train, 'val': wide_val, 'seed': _SEED}, p)
        print('generato', p, '(train', len(train), '/ val', len(wide_val), ')')
"""

RUN = """# Cell 3 -- esegue gli arm + push per-arm. SKIP+RESUME: ri-esegui per continuare.
import subprocess, sys, time, os, shutil, glob, datetime
import pandas as pd

def build_cli(tag, method, override):
    return ([sys.executable, 'train.py', '--training_method', method, '--epochs', str(EPOCHS)]
            + COMMON + override + ['--tag', tag])

def push_arm(tag, override):
    src = 'checkpoints/' + tag
    dst = RESULTS + '/' + tag
    if not os.path.isdir(src):
        return False
    os.makedirs(dst + '/plots', exist_ok=True)
    for f in glob.glob(src + '/*.csv') + glob.glob(src + '/*.json'):
        shutil.copy2(f, dst)
    for f in glob.glob(src + '/plots/*.png'):
        shutil.copy2(f, dst + '/plots/')
    vs = ''
    lp = dst + '/training_log.csv'
    if os.path.isfile(lp):
        edf = pd.read_csv(lp)
        if len(edf) > 0:
            vs = 'min val_data=' + str(round(edf.val_data.min(), 4)) + ' (' + str(len(edf)) + 'ep)'
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    with open(_TMP_MSG, 'w', encoding='utf-8') as fp:
        fp.write('bigsweep3: ' + tag + ' (' + ts + ')\\n\\n' + vs +
                 '\\noverride=' + ' '.join(override) + '\\nBranch: ' + BRANCH + '\\n')
    try:
        subprocess.run(['git', 'add', dst], check=True, capture_output=True)
        r = subprocess.run(['git', 'commit', '-F', _TMP_MSG], capture_output=True, text=True)
        if r.returncode != 0 and 'nothing to commit' not in (r.stdout + r.stderr):
            print('commit fail', r.stderr[-200:]); return False
        subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True, text=True)
        r2 = subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True, text=True)
        print('push OK' if r2.returncode == 0 else 'push fail ' + r2.stderr[-200:])
        return r2.returncode == 0
    finally:
        try:
            os.remove(_TMP_MSG)
        except Exception:
            pass

for tag, method, override in ARMS:
    dst_log = RESULTS + '/' + tag + '/training_log.csv'
    if os.path.isfile(dst_log) and len(pd.read_csv(dst_log)) >= EPOCHS * 0.8:
        print('[SKIP] ' + tag + ' gia presente'); continue
    print('[RUN] ' + tag)
    t0 = time.time()
    r = subprocess.run(build_cli(tag, method, override), capture_output=False)
    print('-> rc=' + str(r.returncode) + ' (' + str(round((time.time() - t0) / 60, 1)) + 'min)')
    print('pushed:', push_arm(tag, override))
print('BigSweep3: passata completata (ri-esegui per gli arm mancanti).')
"""

DIAG = """# Cell 4 -- DIAG: val_data (FISICA, primaria) + NRMSE (secondaria), heatmap, Pareto vs champion
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

champ_nrmse = float(np.mean([CHAMP_NRMSE[c] for c in PN]))
rows = []
for tag, method, override in ARMS:
    lp = log_path(tag)
    if not os.path.isfile(lp):
        continue
    d = pd.read_csv(lp); last = d.iloc[-1]
    nr = {c: round(float(last.get('val_' + c + '_nrmse', float('nan'))), 3) for c in PN}
    valid = [nr[c] for c in PN if nr[c] == nr[c]]
    rows.append({'arm': tag, 'ep': len(d), 'val_data': round(float(d.val_data.min()), 4),
                 'final3': round(float(d.val_data.tail(3).mean()), 4),
                 'nrmse_mean': round(float(np.mean(valid)), 3) if valid else None, **nr})
df = pd.DataFrame(rows)
df.to_csv(RESULTS + '/bigsweep3_summary.csv', index=False)
pd.set_option('display.width', 240); pd.set_option('display.max_columns', 30)
display(Markdown('## Riferimenti: champion val_data **0.1926** / NRMSE %.3f' % champ_nrmse))
display(Markdown('## Arm ordinati per val_data (FISICA = primaria)'))
if len(df):
    display(df.sort_values('val_data')[['arm', 'ep', 'val_data', 'final3', 'nrmse_mean'] + PN].to_string(index=False))

LRS = ['5e-3', '7e-3', '1e-2']; TS = [0.5, 0.6, 0.4]
H = np.full((len(LRS), len(TS)), np.nan)
for i, lr in enumerate(LRS):
    for j, t in enumerate(TS):
        sub = df[df.arm == adam(lr, t, 16)[0]] if len(df) else df
        if len(sub):
            H[i, j] = float(sub['val_data'].iloc[0])
fig, ax = plt.subplots(figsize=(5.5, 4))
im = ax.imshow(H, aspect='auto', cmap='viridis_r')
ax.set_title('val_data (FISICA) - lr x target, rank16, decode ON')
ax.set_xticks(range(len(TS))); ax.set_xticklabels([str(t) for t in TS]); ax.set_xlabel('target')
ax.set_yticks(range(len(LRS))); ax.set_yticklabels(LRS); ax.set_ylabel('lr')
for i in range(len(LRS)):
    for j in range(len(TS)):
        if not np.isnan(H[i, j]):
            ax.text(j, i, str(round(H[i, j], 3)), ha='center', va='center', fontsize=9)
plt.colorbar(im, ax=ax); plt.tight_layout(); plt.savefig(RESULTS + '/bigsweep3_heatmap.png', dpi=110); plt.show()

# Ranking COMPLETO: val_data di TUTTI gli arm + linea champion
if len(df):
    s = df.sort_values('val_data')
    fig2, ax2 = plt.subplots(figsize=(7, max(4, 0.32 * len(s))))
    cols = ['crimson' if t == 'BPTT_REF' else ('teal' if t.startswith('DS_') else 'steelblue') for t in s['arm']]
    ax2.barh(s['arm'], s['val_data'], color=cols)
    ax2.axvline(CHAMP_VAL, color='red', ls='--', label='champion 0.1926')
    ax2.invert_yaxis(); ax2.set_xlabel('val_data (FISICA) -- piu corto = meglio'); ax2.set_title('Ranking arm per val_data')
    ax2.legend(); plt.tight_layout(); plt.savefig(RESULTS + '/bigsweep3_ranking.png', dpi=110); plt.show()

if len(df):
    bp = df.sort_values('val_data').iloc[0]
    display(Markdown('## Pareto: miglior fisica **%s** val_data %.4f (champion 0.1926) | NRMSE %.3f -- '
                     'trade-off, non dominanza; verdetto fisico = sezioni Validate/ClosedLoop'
                     % (bp['arm'], bp['val_data'], bp['nrmse_mean'])))
"""

FULLLOSS = """# Cell 5 -- FULLLOSS: 5 componenti PINN per-arm (dal log) + barre impilate. SKIP se gia' fatto.
import os
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown, Image
OUT = RESULTS + '/bigsweep3_fullloss.csv'; PNG = RESULTS + '/bigsweep3_fullloss.png'
if os.path.isfile(OUT) and os.path.isfile(PNG):
    print('[SKIP] fullloss gia fatto'); display(Image(PNG)); display(pd.read_csv(OUT))
else:
    rows = []
    for tag, method, override in ARMS:
        lp = log_path(tag)
        if not os.path.isfile(lp):
            continue
        l = pd.read_csv(lp).iloc[-1]
        rows.append({'arm': tag, 'val_total': round(float(l['val_total']), 4),
                     'data': round(float(l['val_data']), 4), 'phys': round(float(l['val_phys']), 4),
                     'ou': round(float(l['val_ou']), 4), 'bc': round(float(l['val_bc']), 4),
                     'sr': round(float(l['val_sr']), 4)})
    df = pd.DataFrame(rows)
    if len(df):
        df = df.sort_values('val_total'); df.to_csv(OUT, index=False)
        comp = ['data', 'phys', 'ou', 'bc', 'sr']
        fig, ax = plt.subplots(figsize=(max(7, 0.5 * len(df)), 4.5))
        bottom = [0.0] * len(df)
        for c in comp:
            ax.bar(df['arm'], df[c], bottom=bottom, label=c)
            bottom = [b + v for b, v in zip(bottom, df[c])]
        ax.set_ylabel('loss val (impilata)'); ax.set_title('Composizione PINN loss per-arm (ordinata per totale)')
        ax.legend(ncol=5, fontsize=8); plt.xticks(rotation=90, fontsize=7); plt.tight_layout()
        plt.savefig(PNG, dpi=110); plt.show()
        display(Markdown('## Loss PINN completa per-arm'))
        display(df.to_string(index=False))
    else:
        print('nessun arm ancora')
"""

PARETO = """# Cell 6 -- PARETO: scatter val_data vs NRMSE (la tensione, visualizzata). SKIP se png esiste.
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Image
OUT = RESULTS + '/bigsweep3_pareto.png'
if os.path.isfile(OUT):
    print('[SKIP] pareto gia fatto'); display(Image(OUT))
else:
    sp = RESULTS + '/bigsweep3_summary.csv'
    if not os.path.isfile(sp):
        print('serve DIAG prima')
    else:
        df = pd.read_csv(sp).dropna(subset=['nrmse_mean'])
        champ_nrmse = float(np.mean([CHAMP_NRMSE[c] for c in PN]))
        fig, ax = plt.subplots(figsize=(6.5, 5))
        ax.scatter(df.val_data, df.nrmse_mean, c='steelblue', label='BigSweep3 arm')
        for _, r in df.iterrows():
            ax.annotate(r['arm'].replace('A_', ''), (r.val_data, r.nrmse_mean), fontsize=6, alpha=0.7)
        ax.scatter([CHAMP_VAL], [champ_nrmse], c='red', marker='*', s=200, label='champion LS3_d03')
        ax.scatter([BS2_BEST['val']], [np.mean([BS2_BEST['nrmse'][c] for c in PN])], c='green', marker='D', label='BS2 best')
        ax.set_xlabel('val_data (FISICA) -> meglio a sinistra'); ax.set_ylabel('NRMSE medio -> meglio in basso')
        ax.set_title('Pareto: fisica vs identificazione parametri'); ax.legend(); ax.grid(alpha=0.3)
        plt.tight_layout(); plt.savefig(OUT, dpi=110); plt.show()
"""

RANKCURVE = """# Cell 7 -- RANKCURVE: val_data vs rank + rank EFFETTIVO (U@V). SKIP se csv esiste.
import os
import numpy as np
import pandas as pd
import torch
import matplotlib.pyplot as plt
from IPython.display import display
OUT = RESULTS + '/bigsweep3_rankcurve.csv'
if os.path.isfile(OUT):
    print('[SKIP] rankcurve gia fatto'); display(pd.read_csv(OUT))
else:
    rows = []
    for rk in [8, 16, 24, 32]:
        tag = adam('7e-3', 0.5, rk)[0]
        lp = log_path(tag)
        if not os.path.isfile(lp):
            continue
        vd = float(pd.read_csv(lp).val_data.min())
        eff = float('nan')
        ckp = 'checkpoints/' + tag + '/best_model.pt'
        if os.path.isfile(ckp):
            sd = torch.load(ckp, map_location='cpu', weights_only=False)['model_state']
            if 'layer_hidden.rec_U' in sd:
                R = (sd['layer_hidden.rec_U'] @ sd['layer_hidden.rec_V']).numpy()
                sv = np.linalg.svd(R, compute_uv=False)
                eff = float((sv.sum() ** 2) / (sv ** 2).sum())
        rows.append({'rank': rk, 'val_data': round(vd, 4), 'eff_rank': round(eff, 2)})
    df = pd.DataFrame(rows)
    if len(df):
        df.to_csv(OUT, index=False); display(df.to_string(index=False))
        fig, ax = plt.subplots(1, 2, figsize=(10, 4))
        ax[0].plot(df['rank'], df['val_data'], 'o-'); ax[0].set_xlabel('rank'); ax[0].set_ylabel('val_data'); ax[0].set_title('val_data vs rank (plateau?)'); ax[0].grid(alpha=0.3)
        ax[1].plot(df['rank'], df['eff_rank'], 's-', color='orange'); ax[1].plot(df['rank'], df['rank'], '--', alpha=0.4); ax[1].set_xlabel('rank dato'); ax[1].set_ylabel('rank effettivo'); ax[1].set_title('rank usato vs dato'); ax[1].grid(alpha=0.3)
        plt.tight_layout(); plt.savefig(RESULTS + '/bigsweep3_rankcurve.png', dpi=110); plt.show()
"""

SEEDVAR = """# Cell 8 -- SEEDVAR: varianza multi-seed (robustezza) + barre con errore. SKIP se csv esiste.
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown, Image
OUT = RESULTS + '/bigsweep3_seedvar.csv'; PNG = RESULTS + '/bigsweep3_seedvar.png'
if os.path.isfile(OUT) and os.path.isfile(PNG):
    print('[SKIP] seedvar gia fatto'); display(Image(PNG)); display(pd.read_csv(OUT))
else:
    tags = [adam('7e-3', 0.5, 16)[0]] + [adam('7e-3', 0.5, 16, seed=s)[0] for s in [1, 2, 3]]
    vals, nrs = [], []
    for tag in tags:
        lp = log_path(tag)
        if not os.path.isfile(lp):
            continue
        d = pd.read_csv(lp); l = d.iloc[-1]
        vals.append(float(d.val_data.min()))
        nrs.append(float(np.mean([float(l['val_%s_nrmse' % c]) for c in PN])))
    if len(vals) >= 2:
        df = pd.DataFrame([{'metric': 'val_data', 'mean': round(np.mean(vals), 4), 'std': round(np.std(vals), 4),
                            'min': round(min(vals), 4), 'max': round(max(vals), 4), 'n_seed': len(vals)},
                           {'metric': 'nrmse_mean', 'mean': round(np.mean(nrs), 3), 'std': round(np.std(nrs), 3),
                            'min': round(min(nrs), 3), 'max': round(max(nrs), 3), 'n_seed': len(nrs)}])
        df.to_csv(OUT, index=False)
        fig, ax = plt.subplots(1, 2, figsize=(8, 4))
        ax[0].bar(range(len(vals)), vals, color='steelblue'); ax[0].axhline(np.mean(vals), color='red', ls='--', label='media')
        ax[0].set_title('val_data per seed (std=%.4f)' % np.std(vals)); ax[0].set_xlabel('seed'); ax[0].set_ylabel('val_data'); ax[0].legend()
        ax[1].bar(range(len(nrs)), nrs, color='orange'); ax[1].axhline(np.mean(nrs), color='red', ls='--')
        ax[1].set_title('NRMSE medio per seed (std=%.3f)' % np.std(nrs)); ax[1].set_xlabel('seed'); ax[1].set_ylabel('NRMSE medio')
        plt.suptitle('Robustezza multi-seed (lr7e3 t05 r16)'); plt.tight_layout(); plt.savefig(PNG, dpi=110); plt.show()
        display(df.to_string(index=False))
    else:
        print('servono >=2 seed completati')
"""

PERREGIME = """# Cell 9 -- PERREGIME: val_data + NRMSE per scenario (best arm). SKIP se csv esiste.
import os
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from IPython.display import display, Markdown
OUT = RESULTS + '/bigsweep3_perregime.csv'
if os.path.isfile(OUT):
    print('[SKIP] perregime gia fatto'); display(pd.read_csv(OUT))
else:
    sp = RESULTS + '/bigsweep3_summary.csv'
    if not os.path.isfile(sp):
        print('serve DIAG prima')
    else:
        from train import CFDataset, val_epoch
        sdf = pd.read_csv(sp)
        best_tag = sdf.sort_values('val_data').iloc[0]['arm']
        model = load_arm(best_tag)
        if model is None:
            print('checkpoint mancante per', best_tag)
        else:
            cache = torch.load(CACHE, map_location='cpu', weights_only=False)
            LAM = (1.0, 0.1, 0.05, 1.0, 0.5)
            scen_set = sorted(set(it.get('scenario', 'NA') for it in cache['val']))
            rows = []
            for sc in scen_set:
                items = [it for it in cache['val'] if it.get('scenario', 'NA') == sc]
                if len(items) < 2:
                    continue
                loader = DataLoader(CFDataset(items, seq_len=50, stride=50), batch_size=32)
                with torch.no_grad():
                    a = val_epoch(model, loader, 'cpu', LAM)
                rows.append({'scenario': sc, 'n': len(items), 'data': round(float(a['data']), 4),
                             'phys': round(float(a['phys']), 4),
                             **{c: round(float(a['val_%s_nrmse' % c]), 3) for c in PN}})
            df = pd.DataFrame(rows)
            df.to_csv(OUT, index=False)
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
            ax[0].bar(df['scenario'], df['data'], color='teal'); ax[0].set_title('val_data per scenario'); ax[0].set_ylabel('data loss'); ax[0].tick_params(axis='x', rotation=45)
            import numpy as _np
            xs = _np.arange(len(df)); w = 0.15
            for k, c in enumerate(PN):
                ax[1].bar(xs + k * w, df[c], w, label=c)
            ax[1].set_xticks(xs + 2 * w); ax[1].set_xticklabels(df['scenario'], rotation=45)
            ax[1].set_title('NRMSE per-canale x scenario'); ax[1].set_ylabel('NRMSE'); ax[1].legend(fontsize=8, ncol=5)
            plt.suptitle('Per-regime (best arm = %s)' % best_tag); plt.tight_layout()
            plt.savefig(RESULTS + '/bigsweep3_perregime.png', dpi=110); plt.show()
            display(df.to_string(index=False))
"""

DIAGNOSTICS = """# Cell 10 -- DIAGNOSTICS: spectral radius, spike, neuroni morti, rank effettivo. SKIP se csv esiste.
import os
import numpy as np
import pandas as pd
import torch
from IPython.display import display, Markdown
OUT = RESULTS + '/bigsweep3_diagnostics.csv'
if os.path.isfile(OUT):
    print('[SKIP] diagnostics gia fatto'); display(pd.read_csv(OUT))
else:
    cache = torch.load(CACHE, map_location='cpu', weights_only=False)
    xval = torch.tensor(np.array([it['x'][:50] for it in cache['val'][:64]]), dtype=torch.float32)
    rows = []
    for tag, method, override in ARMS:
        lp = log_path(tag)
        if not os.path.isfile(lp):
            continue
        l = pd.read_csv(lp).iloc[-1]
        dead = float('nan'); eff = float('nan')
        ckp = 'checkpoints/' + tag + '/best_model.pt'
        if os.path.isfile(ckp):
            sd = torch.load(ckp, map_location='cpu', weights_only=False)['model_state']
            if 'layer_hidden.rec_U' in sd:
                R = (sd['layer_hidden.rec_U'] @ sd['layer_hidden.rec_V']).numpy()
                sv = np.linalg.svd(R, compute_uv=False)
                eff = float((sv.sum() ** 2) / (sv ** 2).sum())
            m = load_arm(tag)
            if m is not None:
                try:
                    with torch.no_grad():
                        sp = m.layer_hidden(xval)            # (B,K,hidden)
                    fr = sp.float().mean(dim=(0, 1))
                    dead = int((fr < 0.005).sum())
                except Exception:
                    pass
        rows.append({'arm': tag, 'spectral_radius': round(float(l.get('rec_spectral_radius', float('nan'))), 3),
                     'spike_rate': round(float(l.get('spike_rate', float('nan'))), 3),
                     'marginal_frac': round(float(l.get('marginal_frac', float('nan'))), 4),
                     'eff_rank': round(eff, 2) if eff == eff else None,
                     'dead_neurons': dead})
    df = pd.DataFrame(rows)
    if len(df):
        df.to_csv(OUT, index=False)
        import matplotlib.pyplot as plt
        metr = [('spectral_radius', 'raggio spettrale (stabilita)'), ('spike_rate', 'spike rate'),
                ('dead_neurons', 'neuroni morti'), ('eff_rank', 'rank effettivo')]
        fig, axes = plt.subplots(2, 2, figsize=(13, 7))
        for ax, (col, ttl) in zip(axes.ravel(), metr):
            sub = df.dropna(subset=[col])
            ax.bar(sub['arm'], sub[col], color='slateblue'); ax.set_title(ttl); ax.tick_params(axis='x', rotation=90, labelsize=6)
        plt.suptitle('Diagnostica per-arm: stabilita, sparsita, capacita'); plt.tight_layout()
        plt.savefig(RESULTS + '/bigsweep3_diagnostics.png', dpi=110); plt.show()
        display(df.to_string(index=False))
"""

VALIDATE = """# Cell 11 -- VALIDATE Path B: il refit migliora NRMSE ma degrada la fisica? (loss COMPLETA). SKIP se csv.
import os
import re
import pandas as pd
from IPython.display import display, Markdown
OUT = RESULTS + '/bigsweep3_pathb_validation.csv'
if os.path.isfile(OUT):
    print('[SKIP] validate gia fatto'); display(pd.read_csv(OUT))
else:
    from scripts.path_b_validate import validate
    sp = RESULTS + '/bigsweep3_summary.csv'
    summ = pd.read_csv(sp) if os.path.isfile(sp) else None
    sel = []
    if summ is not None:
        ev = summ[summ.arm.astype(str).str.startswith('A_')].dropna(subset=['nrmse_mean']).sort_values('nrmse_mean')
        sel = list(ev.arm.head(4))
    rows = []
    for tag in sel:
        if not os.path.isfile('checkpoints/' + tag + '/best_model.pt'):
            continue
        try:
            res = validate('checkpoints/' + tag, arm_rank(tag))
        except Exception as e:
            print('skip', tag, type(e).__name__, str(e)[:80]); continue
        g, r = res['global'], res['refit']
        rows.append({'arm': tag, 'nrmse_glob': round(g['nrmse_mean'], 3), 'nrmse_refit': round(r['nrmse_mean'], 3),
                     'data_glob': round(g['comps']['data'], 4), 'data_refit': round(r['comps']['data'], 4),
                     'phys_glob': round(g['comps']['phys'], 4), 'phys_refit': round(r['comps']['phys'], 4)})
    df = pd.DataFrame(rows)
    if len(df):
        df.to_csv(OUT, index=False)
        import numpy as _np
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
        xs = _np.arange(len(df)); w = 0.38
        for ax, (gc, rc, ttl) in zip(axes, [('nrmse_glob', 'nrmse_refit', 'NRMSE (giu = meglio)'),
                                            ('data_glob', 'data_refit', 'data/accel (FISICA)'),
                                            ('phys_glob', 'phys_refit', 'phys residuo (FISICA)')]):
            ax.bar(xs - w / 2, df[gc], w, label='globale', color='steelblue')
            ax.bar(xs + w / 2, df[rc], w, label='refit', color='indianred')
            ax.set_xticks(xs); ax.set_xticklabels(df['arm'], rotation=90, fontsize=6); ax.set_title(ttl); ax.legend(fontsize=8)
        plt.suptitle('Path B refit: NRMSE migliora (sx) ma la FISICA peggiora (centro/dx) = trade da scartare')
        plt.tight_layout(); plt.savefig(RESULTS + '/bigsweep3_validation.png', dpi=110); plt.show()
        display(df.to_string(index=False))
        for _, x in df.iterrows():
            ok = (x.nrmse_refit < x.nrmse_glob) and (x.data_refit <= x.data_glob * 1.02) and (x.phys_refit <= x.phys_glob * 1.02)
            print('  %-22s %s' % (x.arm, 'ADOTTABILE' if ok else 'TRADE-FISICA (no)'))
    else:
        print('nessun arm validabile ancora')
"""

CLOSEDLOOP = """# Cell 12 -- CLOSEDLOOP SICUREZZA: controllo coi parametri IDENTIFICATI vs oracolo. SKIP se csv.
import os
import pandas as pd
import torch
from IPython.display import display, Markdown
OUT = RESULTS + '/bigsweep3_closedloop.csv'
if os.path.isfile(OUT):
    print('[SKIP] closedloop gia fatto'); display(pd.read_csv(OUT))
else:
    from scripts.closed_loop_identify import eval_safety
    sp = RESULTS + '/bigsweep3_summary.csv'
    summ = pd.read_csv(sp) if os.path.isfile(sp) else None
    sel = []
    if summ is not None:
        sel = list(summ.sort_values('val_data').head(3)['arm'])
    cache = torch.load(CACHE, map_location='cpu', weights_only=False)
    rows = []
    for tag in sel:
        m = load_arm(tag)
        if m is None:
            continue
        r = eval_safety(m, cache, n_drivers=20)
        rows.append({'arm': tag, 'role': 'oracolo', **{k: round(r['oracle'][k], 3) for k in ['collision_rate', 'mean_min_gap', 'mean_max_decel', 'mean_rms_jerk']}})
        rows.append({'arm': tag, 'role': 'SNN-identif', **{k: round(r['snn'][k], 3) for k in ['collision_rate', 'mean_min_gap', 'mean_max_decel', 'mean_rms_jerk']}})
    df = pd.DataFrame(rows)
    if len(df):
        df.to_csv(OUT, index=False)
        import numpy as _np
        import matplotlib.pyplot as plt
        arms = list(df[df.role == 'oracolo']['arm'])
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        xs = _np.arange(len(arms)); w = 0.38
        for ax, (col, ttl) in zip(axes, [('collision_rate', 'collision rate (giu = sicuro)'),
                                         ('mean_min_gap', 'min-gap medio [m] (su = sicuro)')]):
            orc = [float(df[(df.arm == a) & (df.role == 'oracolo')][col].iloc[0]) for a in arms]
            snn = [float(df[(df.arm == a) & (df.role == 'SNN-identif')][col].iloc[0]) for a in arms]
            ax.bar(xs - w / 2, orc, w, label='oracolo (veri)', color='seagreen')
            ax.bar(xs + w / 2, snn, w, label='SNN (identif)', color='darkorange')
            ax.set_xticks(xs); ax.set_xticklabels(arms, rotation=30, fontsize=7); ax.set_title(ttl); ax.legend(fontsize=8)
        plt.suptitle('Sicurezza closed-loop: controllo coi parametri SNN vs oracolo')
        plt.tight_layout(); plt.savefig(RESULTS + '/bigsweep3_closedloop.png', dpi=110); plt.show()
        display(df.to_string(index=False))
        display(Markdown('Domanda: collision_rate SNN ~ oracolo? min_gap preservato? -> identificazione SICURA per il controllo.'))
    else:
        print('nessun checkpoint per closed-loop')
"""

SYNTHESIS = """# Cell 13 -- SYNTHESIS: tabella consolidata + verdetto Pareto. SKIP se csv esiste.
import os
import numpy as np
import pandas as pd
from IPython.display import display, Markdown
OUT = RESULTS + '/bigsweep3_synthesis.csv'
if os.path.isfile(OUT):
    print('[SKIP] synthesis gia fatto'); display(pd.read_csv(OUT))
else:
    sp = RESULTS + '/bigsweep3_summary.csv'
    if not os.path.isfile(sp):
        print('serve DIAG prima')
    else:
        df = pd.read_csv(sp)[['arm', 'val_data', 'nrmse_mean']].copy()
        fl = RESULTS + '/bigsweep3_fullloss.csv'
        if os.path.isfile(fl):
            df = df.merge(pd.read_csv(fl)[['arm', 'phys', 'val_total']], on='arm', how='left')
        cl = RESULTS + '/bigsweep3_closedloop.csv'
        if os.path.isfile(cl):
            snn = pd.read_csv(cl)
            snn = snn[snn.role == 'SNN-identif'][['arm', 'collision_rate', 'mean_min_gap']]
            df = df.merge(snn, on='arm', how='left')
        df = df.sort_values('val_data')
        df.to_csv(OUT, index=False)
        champ_nrmse = float(np.mean([CHAMP_NRMSE[c] for c in PN]))
        import matplotlib.pyplot as plt
        bpr = df.iloc[0]
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
        ax[0].bar(['champion', bpr['arm']], [CHAMP_VAL, bpr['val_data']], color=['crimson', 'steelblue'])
        ax[0].set_title('val_data (FISICA, giu = meglio)'); ax[0].set_ylabel('val_data')
        bn = float(bpr['nrmse_mean']) if bpr['nrmse_mean'] == bpr['nrmse_mean'] else 0
        ax[1].bar(['champion', bpr['arm']], [champ_nrmse, bn], color=['crimson', 'steelblue'])
        ax[1].set_title('NRMSE medio (giu = meglio)'); ax[1].set_ylabel('NRMSE')
        plt.suptitle('SINTESI: miglior EventProp vs champion (Pareto -- chi vince dipende dall asse)')
        plt.tight_layout(); plt.savefig(RESULTS + '/bigsweep3_synthesis.png', dpi=110); plt.show()
        display(Markdown('## SINTESI -- consolidato (fisica + NRMSE + loss + sicurezza)'))
        display(df.to_string(index=False))
        bp = df.iloc[0]
        beats = bp['val_data'] < CHAMP_VAL
        display(Markdown('### Verdetto'))
        display(Markdown('- Miglior FISICA: **%s** val_data %.4f vs champion 0.1926 (%s).' %
                         (bp['arm'], bp['val_data'], 'BATTE' if beats else 'sotto')))
        display(Markdown('- Champion 0.193/NRMSE %.3f. EventProp tipicamente: NRMSE migliore, fisica peggiore '
                         '= **Pareto, non dominanza**.' % champ_nrmse))
        display(Markdown('- Sicurezza: vedi closed_loop (SNN-identif vs oracolo). Path B refit: vedi validate '
                         '(NRMSE down ma fisica up = scartare).'))
"""

PUSH_DIAG = """# Cell 14 -- push tutti gli output dell'analisi
import subprocess, os, glob
for p in glob.glob(RESULTS + '/bigsweep3_*.csv') + glob.glob(RESULTS + '/bigsweep3_*.png'):
    subprocess.run(['git', 'add', p], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'bigsweep3: analisi esaustiva'], capture_output=True, text=True)
if r.returncode == 0 or 'nothing to commit' in (r.stdout + r.stderr):
    subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True, text=True)
    r2 = subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True, text=True)
    print('push analisi:', 'OK' if r2.returncode == 0 else r2.stderr[-200:])
else:
    print('commit fail', r.stderr[-200:])
"""

DATASET = """# Cell -- DATASET: coverage param vs range fisico + confronto narrow/wide/widebig (val comune). SKIP.
import os
import numpy as np
import pandas as pd
import torch
import matplotlib.pyplot as plt
from IPython.display import display, Markdown, Image
BOUNDS = {'v0': (8, 45), 'T': (0.5, 2.5), 's0': (1, 5), 'a': (0.3, 2.5), 'b': (0.5, 3.0)}

# (1) Coverage: distribuzione param veri per-canale (attuale vs wide) sul range fisico
covpng = RESULTS + '/bigsweep3_coverage.png'
if os.path.isfile(covpng):
    print('[SKIP] coverage gia fatto'); display(Image(covpng))
else:
    def _params(path):
        if not os.path.isfile(path):
            return None
        c = torch.load(path, map_location='cpu', weights_only=False)
        return np.array([[d['params'][k] for k in PN] for d in c['train']])
    cur = _params(CACHE); wide = _params('data/cache_ds_wide.pt')
    if cur is not None:
        rows = []
        fig, axes = plt.subplots(1, 5, figsize=(15, 3))
        for i, k in enumerate(PN):
            lo, hi = BOUNDS[k]
            axes[i].axhspan(lo, hi, color='lightgray', alpha=0.5)
            data = [cur[:, i]] + ([wide[:, i]] if wide is not None else [])
            axes[i].violinplot(data, showmeans=True)
            axes[i].set_title(k); axes[i].set_xticks(range(1, len(data) + 1))
            axes[i].set_xticklabels(['attuale'] + (['wide'] if wide is not None else []))
            rows.append({'param': k, 'phys_range': '[%g,%g]' % (lo, hi),
                         'cur_span': '[%.2f,%.2f]' % (cur[:, i].min(), cur[:, i].max()),
                         'cur_coverage_%': round(100 * (cur[:, i].max() - cur[:, i].min()) / (hi - lo), 1),
                         'cur_n_uniq': int(len(np.unique(np.round(cur[:, i], 2))))})
        plt.tight_layout(); plt.savefig(covpng, dpi=110); plt.show()
        cdf = pd.DataFrame(rows); cdf.to_csv(RESULTS + '/bigsweep3_coverage.csv', index=False)
        display(Markdown('## Coverage parametri (attuale) vs range fisico -- s0/b sotto-coperti?'))
        display(cdf.to_string(index=False))

# (2) Confronto narrow/wide/widebig sul COMMON wide-val (dai training_log degli arm DS)
OUT = RESULTS + '/bigsweep3_dataset.csv'
if os.path.isfile(OUT):
    print('[SKIP] dataset-study gia fatto'); display(pd.read_csv(OUT))
else:
    rows = []
    for tag in ['DS_narrow', 'DS_wide', 'DS_widebig']:
        lp = log_path(tag)
        if not os.path.isfile(lp):
            continue
        d = pd.read_csv(lp); l = d.iloc[-1]
        rows.append({'arm': tag, 'val_data': round(float(d.val_data.min()), 4),
                     **{c: round(float(l['val_%s_nrmse' % c]), 3) for c in PN}})
    if rows:
        df = pd.DataFrame(rows); df.to_csv(OUT, index=False)
        xs = np.arange(len(PN)); w = 0.25
        fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
        for k, tag in enumerate(df['arm']):
            r = df[df.arm == tag].iloc[0]
            ax[0].bar(xs + k * w, [r[c] for c in PN], w, label=tag)
        ax[0].set_xticks(xs + w); ax[0].set_xticklabels(PN); ax[0].set_ylabel('NRMSE (wide-val)')
        ax[0].set_title('Identificazione per-canale (range PIENO) -- guarda s0/b'); ax[0].legend(fontsize=8)
        ax[1].bar(df['arm'], df['val_data'], color='teal'); ax[1].set_title('val_data sul wide-val'); ax[1].tick_params(axis='x', rotation=20)
        plt.suptitle('Studio dataset: narrow vs wide vs widebig'); plt.tight_layout()
        plt.savefig(RESULTS + '/bigsweep3_dataset.png', dpi=110); plt.show()
        display(df.to_string(index=False))
        display(Markdown('Se wide/widebig battono narrow (specie su **s0/b**) -> dati piu\\' vari aiutano '
                         '= verso il "dataset perfetto". Se no -> l\\'attuale e\\' sufficiente.'))
    else:
        print('arm DS non ancora pronti')
"""

cells = [
    cell(INTRO, 'intro', 'markdown'),
    cell(ENV, 'env'),
    cell(CONFIG, 'config'),
    cell(DATASETGEN, 'datasetgen'),
    cell(RUN, 'run'),
    cell(DIAG, 'diag'),
    cell(FULLLOSS, 'fullloss'),
    cell(PARETO, 'pareto'),
    cell(RANKCURVE, 'rankcurve'),
    cell(SEEDVAR, 'seedvar'),
    cell(PERREGIME, 'perregime'),
    cell(DIAGNOSTICS, 'diagnostics'),
    cell(VALIDATE, 'validate'),
    cell(CLOSEDLOOP, 'closedloop'),
    cell(DATASET, 'dataset'),
    cell(SYNTHESIS, 'synthesis'),
    cell(PUSH_DIAG, 'pushdiag'),
]

nb = {
    'cells': cells,
    'metadata': {
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python', 'version': '3.10'},
    },
    'nbformat': 4,
    'nbformat_minor': 5,
}

out = os.path.join(ROOT, 'EventProp_BigSweep3.ipynb')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print('Wrote', out)
