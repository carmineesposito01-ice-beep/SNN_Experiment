"""EventProp Spectral Sweep — sweep 2D del vincolo spettrale (C11) su U@V.

Genera EventProp_Spectral_Sweep.ipynb. Causa dell'instabilita' EventProp confermata: il raggio
spettrale della ricorrenza U@V cresce senza limite (0.83->2.8) e l'adjoint Rᵀ esplode quando supera
~2.5-2.7. Cura = regolarizzatore spettrale lambda*relu(sigma_max(U@V)-target)^2 (C11). Primo test
(lambda 1.0, target 1.5, lr 2e-3): stabile, val 0.250. Questo sweep cerca l'operating point ottimale
(lambda x target) e leva il transitorio osservato. Output in results/EventProp_Spectral_Sweep/.

Tutto opt-in/backward-compat. Recipe: EventProp + AdamW lr 2e-3 (la piu' aggressiva, che senza vincolo
esplode a ep4-5: cosi' l'effetto del vincolo e' netto), mix launch, n1500.
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


INTRO = """# EventProp Spectral Sweep — vincolo spettrale C11 su U@V

Sweep 2D del regolarizzatore spettrale che stabilizza EventProp. Causa confermata: `rec_spectral_radius`
di `U@V` cresce 0.83->2.8 e l'adjoint esplode oltre ~2.5-2.7. Cura: `lambda*relu(sigma_max(U@V)-target)^2`.
Griglia `lambda x target` + un arm di **riferimento senza vincolo** (esplode). Recipe: EventProp+AdamW
lr 2e-3 (aggressiva), mix launch, n1500. Diagnostica: curve val, curve raggio spettrale, heatmap
min_val e max_grad su (lambda, target). Output `results/EventProp_Spectral_Sweep/`.
"""

ENV = """# Cell 1 -- ENV
import sys, os, subprocess
import importlib.util as _imu
RESULTS = 'results/EventProp_Spectral_Sweep'
BRANCH = 'EventProp_Study'
LAUNCH_MIX = 'highway:0.20,urban:0.15,truck:0.10,mixed:0.05,freeflow:0.15,launch:0.35'
CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'
_TMP_MSG = '/tmp/spec_msg.txt' if os.path.isdir('/tmp') else 'spec_msg.txt'
os.makedirs(RESULTS, exist_ok=True)
for pkg in ['pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
assert os.path.isfile('core/eventprop.py'), 'missing core/eventprop.py'
assert os.path.isfile(CACHE), 'missing cache: ' + CACHE + ' (rigenerala o git pull)'
br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
print('[SpectralSweep] ENV OK | branch =', br, '| cache OK')
"""

CONFIG = """# Cell 2 -- griglia sweep (lambda x target) + arm di riferimento (no vincolo)
EPOCHS = 25     # oltre la danger-zone (esplosione no-vincolo a ep4-5) per vedere la convergenza
COMMON = ['--max_steps_per_epoch', '100', '--batch_size', '8', '--val_batch_size', '32',
          '--seq_len', '50', '--cf_hidden_size', '32', '--cf_rank', '8', '--cf_max_delay', '6',
          '--cf_bit_shift', '3', '--lambda_data', '1.0', '--lambda_phys', '0.1', '--lambda_ou', '0.05',
          '--lambda_bc', '1.0', '--lambda_sr', '0.5', '--scenario_mix', LAUNCH_MIX, '--cut_in_ratio', '0.0',
          '--noise_scale', '0.0', '--po2_enabled', '1', '--n_train', '1500', '--n_val', '300',
          '--data_cache', CACHE, '--max_inf_streak', '99999', '--early_stop_patience', '0',
          '--max_epoch_explosion_streak', '3', '--epoch_explosion_threshold', '10000.0',
          '--epoch_explosion_frac', '0.5', '--grad_clip', 'agc', '--agc_lambda', '0.01']
# EventProp + AdamW 2e-3 (senza vincolo esplode -> isola l'effetto del regolarizzatore)
BASE = ['--optimizer', 'adamw', '--lr', '2e-3', '--max_lr', '2e-3', '--scheduler', 'cosine_no_restart']

LAMBDAS = [0.5, 1.0, 3.0, 10.0]
TARGETS = [1.2, 1.5, 2.0, 2.5]

def _fmt(x):
    return str(x).replace('.', '')

def tagname(l, t):
    return 'SPEC_l' + _fmt(l) + '_t' + _fmt(t)

# riferimento: nessun vincolo (lambda_spectral 0) -> deve esplodere ~ep4-5
ARMS = [('SPEC_REF_noconstraint', 'eventprop_alif_full', list(BASE))]
for _l in LAMBDAS:
    for _t in TARGETS:
        ov = list(BASE) + ['--eventprop_lambda_spectral', str(_l), '--eventprop_spectral_target', str(_t)]
        ARMS.append((tagname(_l, _t), 'eventprop_alif_full', ov))
print('Sweep:', len(ARMS), 'arm (1 ref + ' + str(len(LAMBDAS) * len(TARGETS)) + ' griglia)')
print([a[0] for a in ARMS])
"""

RUN = """# Cell 3 -- esegue gli arm (subprocess train.py) + push per-arm in results/EventProp_Spectral_Sweep/
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
        fp.write('spectral_sweep: ' + tag + ' (' + ts + ')\\n\\n' + vs +
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
print('SpectralSweep: tutti gli arm completati.')
"""

DIAG = """# Cell 4 -- diagnostica sweep: curve + heatmap (lambda x target) + verdetto
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

EXPL = 1000.0   # grad_norm sopra cui consideriamo l'arm "esploso"
TAGS = [a[0] for a in ARMS]

rows = []
fig1, ax1 = plt.subplots(1, 2, figsize=(15, 5))
for tag in TAGS:
    lp = RESULTS + '/' + tag + '/training_log.csv'
    if not os.path.isfile(lp):
        rows.append({'arm': tag, 'status': 'MISSING'}); continue
    d = pd.read_csv(lp)
    maxg = float(d.grad_norm.max())
    maxsr = float(d.rec_spectral_radius.max()) if 'rec_spectral_radius' in d.columns else float('nan')
    rows.append({'arm': tag, 'ep': len(d),
                 'min_val': round(float(d.val_data.min()), 4),
                 'final_val': round(float(d.val_data.iloc[-1]), 4),
                 'max_grad': round(maxg, 1),
                 'max_spectral': round(maxsr, 2),
                 'exploded': bool(maxg > EXPL)})
    ax1[0].plot(d.epoch, d.val_data, label=tag, alpha=0.7, lw=1)
    if 'rec_spectral_radius' in d.columns:
        ax1[1].plot(d.epoch, d.rec_spectral_radius, label=tag, alpha=0.7, lw=1)
ax1[0].set_title('val_data per arm'); ax1[0].set_xlabel('epoca'); ax1[0].set_ylabel('val_data')
ax1[0].set_ylim(0.15, 0.6); ax1[0].grid(alpha=0.3); ax1[0].legend(fontsize=5, ncol=2)
ax1[1].set_title('rec_spectral_radius per arm'); ax1[1].set_xlabel('epoca')
ax1[1].axhline(2.6, ls='--', c='r', lw=1, label='soglia esplosione ~2.6')
ax1[1].grid(alpha=0.3); ax1[1].legend(fontsize=5, ncol=2)
plt.tight_layout(); plt.savefig(RESULTS + '/sweep_curves.png', dpi=110); plt.show()

summ = pd.DataFrame(rows)
display(Markdown('### Riepilogo arm (ordinati per min_val tra gli stabili)'))
display(summ.sort_values('min_val'))
summ.to_csv(RESULTS + '/sweep_summary.csv', index=False)

# Heatmap min_val + log10(max_grad) sulla griglia lambda x target
Hv = np.full((len(LAMBDAS), len(TARGETS)), np.nan)
Hg = np.full((len(LAMBDAS), len(TARGETS)), np.nan)
for i, l in enumerate(LAMBDAS):
    for j, t in enumerate(TARGETS):
        lp = RESULTS + '/' + tagname(l, t) + '/training_log.csv'
        if os.path.isfile(lp):
            d = pd.read_csv(lp)
            Hv[i, j] = float(d.val_data.min())
            Hg[i, j] = float(d.grad_norm.max())
fig2, ax2 = plt.subplots(1, 2, figsize=(13, 4.5))
im0 = ax2[0].imshow(Hv, aspect='auto', cmap='viridis_r')
ax2[0].set_title('min_val (piu scuro = meglio)')
im1 = ax2[1].imshow(np.log10(Hg + 1.0), aspect='auto', cmap='Reds')
ax2[1].set_title('log10(max_grad+1) (chiaro = stabile)')
for ax in ax2:
    ax.set_xticks(range(len(TARGETS))); ax.set_xticklabels([str(t) for t in TARGETS]); ax.set_xlabel('target')
    ax.set_yticks(range(len(LAMBDAS))); ax.set_yticklabels([str(l) for l in LAMBDAS]); ax.set_ylabel('lambda')
for i in range(len(LAMBDAS)):
    for j in range(len(TARGETS)):
        if not np.isnan(Hv[i, j]):
            ax2[0].text(j, i, str(round(Hv[i, j], 3)), ha='center', va='center', fontsize=8)
plt.colorbar(im0, ax=ax2[0]); plt.colorbar(im1, ax=ax2[1])
plt.tight_layout(); plt.savefig(RESULTS + '/sweep_heatmap.png', dpi=110); plt.show()

# Verdetto: miglior arm stabile (max_grad < EXPL)
stable = summ[(summ.get('exploded') == False) & summ['min_val'].notna()] if 'exploded' in summ.columns else summ
if len(stable) > 0:
    best = stable.sort_values('min_val').iloc[0]
    display(Markdown('### Vincitore (stabile, min_val piu basso): **' + str(best['arm']) +
                     '**  | min_val=' + str(best['min_val']) + ' | max_grad=' + str(best['max_grad']) +
                     ' | max_spectral=' + str(best['max_spectral'])))
    display(Markdown('Prossimo: run pieno 50ep su questo arm per confermare la convergenza.'))
else:
    display(Markdown('### Nessun arm stabile trovato — rivedere la griglia.'))
"""

PUSH_DIAG = """# Cell 5 -- push dei grafici/summary dello sweep
import subprocess, os
for f in ['sweep_curves.png', 'sweep_heatmap.png', 'sweep_summary.csv']:
    p = RESULTS + '/' + f
    if os.path.isfile(p):
        subprocess.run(['git', 'add', p], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'spectral_sweep: diagnostica (curve + heatmap + summary)'],
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

out = os.path.join(ROOT, 'EventProp_Spectral_Sweep.ipynb')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print('Wrote', out)
