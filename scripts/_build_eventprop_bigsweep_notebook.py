"""EventProp Big Sweep — 2 parti, 50 epoche: trovare la config EventProp <= BPTT (~0.20).

Genera EventProp_BigSweep.ipynb. Due esplorazioni esaustive sulla STESSA arch ALIF A1, mix launch,
n1500, 50 ep, con il vincolo spettrale C11 (stabilizza l'adjoint):

  Parte A — AdamW: griglia lr x spectral_target (l'optimizer a lr fisso, gia' funzionante).
  Parte B — ProdigyEvent LOSS-AWARE (C12): griglia dei knob del P&O (po_bad_decay x po_good_probe)
            + sonde d'asse (growth_rate, po_period, lr) — l'optimizer parameter-free.

Riferimento BPTT (single-cycle champion) come target da battere. Arm ordinati BEST-FIRST: se lo sweep
non finisce in nottata, i piu' informativi sono gia' fatti; scout-style SKIP+RESUME (ri-eseguire la
cella RUN continua dagli arm mancanti). Output in results/EventProp_BigSweep/.
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


INTRO = """# EventProp Big Sweep — AdamW vs ProdigyEvent loss-aware (50 epoche)

Esplorazione esaustiva in 2 parti per trovare la config EventProp **paragonabile o migliore del BPTT**
(champion ~0.20). Vincolo spettrale C11 attivo (stabilizza l'adjoint). **Parte A**: AdamW, griglia
`lr x spectral_target`. **Parte B**: ProdigyEvent loss-aware (C12), griglia knob P&O
`po_bad_decay x po_good_probe` + sonde d'asse. Arm ordinati best-first; RUN con SKIP+RESUME (se non
finisce, ri-esegui la cella e continua). Output `results/EventProp_BigSweep/`.
"""

ENV = """# Cell 1 -- ENV
import sys, os, subprocess
import importlib.util as _imu
RESULTS = 'results/EventProp_BigSweep'
BRANCH = 'EventProp_Study'
LAUNCH_MIX = 'highway:0.20,urban:0.15,truck:0.10,mixed:0.05,freeflow:0.15,launch:0.35'
CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'
_TMP_MSG = '/tmp/bigsweep_msg.txt' if os.path.isdir('/tmp') else 'bigsweep_msg.txt'
os.makedirs(RESULTS, exist_ok=True)
for pkg in ['pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
assert os.path.isfile('core/eventprop.py'), 'missing core/eventprop.py'
assert os.path.isfile('core/prodigy_event.py'), 'missing core/prodigy_event.py'
assert os.path.isfile(CACHE), 'missing cache: ' + CACHE
br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
print('[BigSweep] ENV OK | branch =', br, '| cache OK')
"""

CONFIG = """# Cell 2 -- definizione arm: Parte A (AdamW lr x target) + Parte B (ProdigyEvent P&O knobs)
EPOCHS = 50
COMMON = ['--max_steps_per_epoch', '100', '--batch_size', '8', '--val_batch_size', '32',
          '--seq_len', '50', '--cf_hidden_size', '32', '--cf_rank', '8', '--cf_max_delay', '6',
          '--cf_bit_shift', '3', '--lambda_data', '1.0', '--lambda_phys', '0.1', '--lambda_ou', '0.05',
          '--lambda_bc', '1.0', '--lambda_sr', '0.5', '--scenario_mix', LAUNCH_MIX, '--cut_in_ratio', '0.0',
          '--noise_scale', '0.0', '--po2_enabled', '1', '--n_train', '1500', '--n_val', '300',
          '--data_cache', CACHE, '--max_inf_streak', '99999', '--early_stop_patience', '0',
          '--max_epoch_explosion_streak', '3', '--epoch_explosion_threshold', '10000.0',
          '--epoch_explosion_frac', '0.5', '--grad_clip', 'agc', '--agc_lambda', '0.01']

def _f(x):
    return str(x).replace('.', '').replace('-', '')

# ---- Parte A: AdamW spectral + lr ----
ADAM_LRS = ['5e-4', '1e-3', '2e-3', '3e-3']
ADAM_TARGETS = [0.8, 1.0, 1.2, 1.4]
ADAM_LAMBDA = '1.0'   # lambda secondario (sweep precedente): fisso, si varia lr e target

def adam_arm(lr, t):
    tag = 'ADAM_lr' + _f(lr) + '_t' + _f(t)
    ov = ['--optimizer', 'adamw', '--lr', lr, '--max_lr', lr, '--scheduler', 'cosine_no_restart',
          '--eventprop_lambda_spectral', ADAM_LAMBDA, '--eventprop_spectral_target', str(t)]
    return (tag, 'eventprop_alif_full', ov)

# ---- Parte B: ProdigyEvent loss-aware ----
PE_BASE = ['--optimizer', 'prodigy_event', '--lr', '0.5', '--max_lr', '0.5', '--scheduler', 'cosine_no_restart',
           '--prodigy_growth_rate', '1.02', '--prodigy_betas', '0.9,0.99', '--prodigy_d0', '1e-6',
           '--prodigy_weight_decay', '0.01', '--prodigy_use_bias_correction', '1', '--prodigy_safeguard_warmup', '1',
           '--prodigy_ema_beta', '0.9', '--prodigy_rate_band', '0.10,0.25',
           '--prodigy_loss_aware', '1', '--prodigy_po_period', '25',
           '--eventprop_lambda_spectral', '0.5', '--eventprop_spectral_target', '1.2']

def pe_arm(tag, extra):
    return (tag, 'eventprop_alif_full', list(PE_BASE) + extra)

PE_BD = [('0.3', '03'), ('0.5', '05'), ('0.7', '07')]          # po_bad_decay (ritirata su finestra cattiva)
PE_GP = [('0.0', '0'), ('0.005', '0005'), ('0.02', '002')]     # po_good_probe (esplora su finestra buona)

# ---- Riferimento BPTT (single-cycle champion) ----
BPTT_DECODE = ['--cf_init_bias_shift', '1', '--cf_logit_tau_per_channel', '10.0,3.0,10.0,3.0,3.0']
PRODIGY_STD = ['--optimizer', 'prodigy', '--lr', '0.5', '--prodigy_betas', '0.9,0.99', '--prodigy_d_coef', '1.0',
               '--prodigy_d0', '1e-6', '--prodigy_weight_decay', '0.01', '--prodigy_use_bias_correction', '1',
               '--prodigy_safeguard_warmup', '1']
BPTT_REF = ('BPTT_REF', 'baseline', BPTT_DECODE + PRODIGY_STD +
            ['--scheduler', 'cosine_no_restart', '--max_lr', '0.5', '--prodigy_growth_rate', '1.05'])

# ---- Assemblaggio: BEST-FIRST, poi le griglie (dedup per tag) ----
ARMS = []
_seen = set()

def _add(arm):
    if arm[0] not in _seen:
        _seen.add(arm[0]); ARMS.append(arm)

_add(BPTT_REF)                                                  # riferimento BPTT
_add(adam_arm('2e-3', 1.2))                                     # best AdamW noto
_add(pe_arm('PE_bd05_gp0', ['--prodigy_po_bad_decay', '0.5', '--prodigy_po_good_probe', '0.0']))  # PE v1 (pulito)
# Parte A: griglia lr x target
for _lr in ADAM_LRS:
    for _t in ADAM_TARGETS:
        _add(adam_arm(_lr, _t))
# Parte B: griglia bad_decay x good_probe
for _bd, _bdl in PE_BD:
    for _gp, _gpl in PE_GP:
        _add(pe_arm('PE_bd' + _bdl + '_gp' + _gpl,
                    ['--prodigy_po_bad_decay', _bd, '--prodigy_po_good_probe', _gp]))
# Parte B: sonde d'asse (variano UN knob dalla base bd0.5/gp0005; l'ultimo flag vince in argparse)
_PE_AXIS = list(PE_BASE) + ['--prodigy_po_bad_decay', '0.5', '--prodigy_po_good_probe', '0.005']
_add(('PE_axis_gr101', 'eventprop_alif_full', _PE_AXIS + ['--prodigy_growth_rate', '1.01']))
_add(('PE_axis_gr105', 'eventprop_alif_full', _PE_AXIS + ['--prodigy_growth_rate', '1.05']))
_add(('PE_axis_pp15',  'eventprop_alif_full', _PE_AXIS + ['--prodigy_po_period', '15']))
_add(('PE_axis_pp40',  'eventprop_alif_full', _PE_AXIS + ['--prodigy_po_period', '40']))
_add(('PE_axis_lr03',  'eventprop_alif_full', _PE_AXIS + ['--lr', '0.3', '--max_lr', '0.3']))
_add(('PE_axis_lr10',  'eventprop_alif_full', _PE_AXIS + ['--lr', '1.0', '--max_lr', '1.0']))

print('BigSweep:', len(ARMS), 'arm |',
      sum(1 for a in ARMS if a[0].startswith('ADAM')), 'AdamW,',
      sum(1 for a in ARMS if a[0].startswith('PE')), 'ProdigyEvent, 1 BPTT-ref')
print([a[0] for a in ARMS])
"""

RUN = """# Cell 3 -- esegue gli arm (subprocess train.py) + push per-arm. SKIP+RESUME: ri-esegui per continuare.
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
        fp.write('bigsweep: ' + tag + ' (' + ts + ')\\n\\n' + vs +
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
print('BigSweep: passata completata (ri-esegui per gli arm eventualmente mancanti).')
"""

DIAG = """# Cell 4 -- diagnostica: summary per gruppo + heatmap + verdetto vs BPTT
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

def _group(tag):
    if tag.startswith('ADAM'):
        return 'AdamW'
    if tag.startswith('PE'):
        return 'ProdigyEvent'
    return 'BPTT'

rows = []
for tag, method, override in ARMS:
    lp = RESULTS + '/' + tag + '/training_log.csv'
    if not os.path.isfile(lp):
        rows.append({'arm': tag, 'group': _group(tag), 'status': 'MISSING'}); continue
    d = pd.read_csv(lp)
    n = len(d)
    final3 = float(d.val_data.tail(3).mean())
    rows.append({'arm': tag, 'group': _group(tag), 'ep': n,
                 'min_val': round(float(d.val_data.min()), 4),
                 'final3_val': round(final3, 4),
                 'max_grad': round(float(d.grad_norm.max()), 1),
                 'completed': bool(n >= EPOCHS * 0.8)})
summ = pd.DataFrame(rows)
summ.to_csv(RESULTS + '/bigsweep_summary.csv', index=False)

bptt = summ[summ.group == 'BPTT']
bptt_val = float(bptt['min_val'].iloc[0]) if len(bptt) and 'min_val' in bptt.columns and bptt['min_val'].notna().any() else float('nan')
display(Markdown('## Riferimento BPTT: min_val = **' + str(bptt_val) + '** (target da battere)'))

for grp in ['AdamW', 'ProdigyEvent']:
    sub = summ[(summ.group == grp) & summ.get('min_val').notna()] if 'min_val' in summ.columns else summ[summ.group == grp]
    if len(sub) == 0:
        continue
    display(Markdown('### ' + grp + ' (ordinati per min_val)'))
    display(sub.sort_values('min_val')[['arm', 'ep', 'min_val', 'final3_val', 'max_grad', 'completed']])

# Curve val: migliori 8 arm complessivi
fig1, ax1 = plt.subplots(1, 2, figsize=(15, 5))
done = summ[summ.get('min_val').notna()] if 'min_val' in summ.columns else summ
best8 = list(done.sort_values('min_val')['arm'].head(8)) if len(done) else []
for tag in best8 + (['BPTT_REF'] if 'BPTT_REF' not in best8 else []):
    lp = RESULTS + '/' + tag + '/training_log.csv'
    if os.path.isfile(lp):
        d = pd.read_csv(lp)
        ax1[0].plot(d.epoch, d.val_data, label=tag, alpha=0.8, lw=1)
        if 'rec_spectral_radius' in d.columns:
            ax1[1].plot(d.epoch, d.rec_spectral_radius, label=tag, alpha=0.8, lw=1)
ax1[0].set_title('val_data (migliori 8 + BPTT)'); ax1[0].set_xlabel('epoca'); ax1[0].set_ylim(0.15, 0.5)
ax1[0].axhline(bptt_val, ls='--', c='k', lw=1, label='BPTT'); ax1[0].grid(alpha=0.3); ax1[0].legend(fontsize=6)
ax1[1].set_title('rec_spectral_radius'); ax1[1].set_xlabel('epoca'); ax1[1].grid(alpha=0.3); ax1[1].legend(fontsize=6)
plt.tight_layout(); plt.savefig(RESULTS + '/bigsweep_curves.png', dpi=110); plt.show()

# Heatmap A: AdamW lr x target (min_val)
Ha = np.full((len(ADAM_LRS), len(ADAM_TARGETS)), np.nan)
for i, lr in enumerate(ADAM_LRS):
    for j, t in enumerate(ADAM_TARGETS):
        lp = RESULTS + '/' + adam_arm(lr, t)[0] + '/training_log.csv'
        if os.path.isfile(lp):
            Ha[i, j] = float(pd.read_csv(lp).val_data.min())
# Heatmap B: ProdigyEvent bad_decay x good_probe (min_val)
Hp = np.full((len(PE_BD), len(PE_GP)), np.nan)
for i, (bd, bdl) in enumerate(PE_BD):
    for j, (gp, gpl) in enumerate(PE_GP):
        lp = RESULTS + '/PE_bd' + bdl + '_gp' + gpl + '/training_log.csv'
        if os.path.isfile(lp):
            Hp[i, j] = float(pd.read_csv(lp).val_data.min())
fig2, ax2 = plt.subplots(1, 2, figsize=(13, 4.5))
im0 = ax2[0].imshow(Ha, aspect='auto', cmap='viridis_r')
ax2[0].set_title('AdamW min_val (lr x target)')
ax2[0].set_xticks(range(len(ADAM_TARGETS))); ax2[0].set_xticklabels([str(t) for t in ADAM_TARGETS]); ax2[0].set_xlabel('target')
ax2[0].set_yticks(range(len(ADAM_LRS))); ax2[0].set_yticklabels(ADAM_LRS); ax2[0].set_ylabel('lr')
im1 = ax2[1].imshow(Hp, aspect='auto', cmap='viridis_r')
ax2[1].set_title('ProdigyEvent min_val (po_bad_decay x po_good_probe)')
ax2[1].set_xticks(range(len(PE_GP))); ax2[1].set_xticklabels([g[0] for g in PE_GP]); ax2[1].set_xlabel('po_good_probe')
ax2[1].set_yticks(range(len(PE_BD))); ax2[1].set_yticklabels([b[0] for b in PE_BD]); ax2[1].set_ylabel('po_bad_decay')
for ax, H in [(ax2[0], Ha), (ax2[1], Hp)]:
    for i in range(H.shape[0]):
        for j in range(H.shape[1]):
            if not np.isnan(H[i, j]):
                ax.text(j, i, str(round(H[i, j], 3)), ha='center', va='center', fontsize=8)
plt.colorbar(im0, ax=ax2[0]); plt.colorbar(im1, ax=ax2[1])
plt.tight_layout(); plt.savefig(RESULTS + '/bigsweep_heatmaps.png', dpi=110); plt.show()

# Verdetto
if 'min_val' in summ.columns:
    ev = summ[(summ.group != 'BPTT') & summ.completed.fillna(False) & summ.min_val.notna()]
    if len(ev):
        best = ev.sort_values('min_val').iloc[0]
        verdetto = 'BATTE' if best['min_val'] < bptt_val else ('PAREGGIA' if best['min_val'] <= bptt_val + 0.01 else 'sotto')
        display(Markdown('## Miglior EventProp stabile: **' + str(best['arm']) + '** min_val=' +
                         str(best['min_val']) + ' (' + verdetto + ' il BPTT ' + str(bptt_val) + ')'))
"""

PUSH_DIAG = """# Cell 5 -- push diagnostica
import subprocess, os
for f in ['bigsweep_curves.png', 'bigsweep_heatmaps.png', 'bigsweep_summary.csv']:
    p = RESULTS + '/' + f
    if os.path.isfile(p):
        subprocess.run(['git', 'add', p], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'bigsweep: diagnostica (curve + heatmap + summary)'],
                   capture_output=True, text=True)
if r.returncode == 0 or 'nothing to commit' in (r.stdout + r.stderr):
    subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True, text=True)
    r2 = subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True, text=True)
    print('push diagnostica:', 'OK' if r2.returncode == 0 else r2.stderr[-200:])
else:
    print('commit fail', r.stderr[-200:])
"""

cells = [
    cell(INTRO, 'intro', 'markdown'),
    cell(ENV, 'env'),
    cell(CONFIG, 'config'),
    cell(RUN, 'run'),
    cell(DIAG, 'diag'),
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

out = os.path.join(ROOT, 'EventProp_BigSweep.ipynb')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print('Wrote', out)
