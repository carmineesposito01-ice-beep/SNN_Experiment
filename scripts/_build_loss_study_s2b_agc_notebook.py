"""Loss_Study S2b — test AGC su x10 (la taglia piu' esplosiva).

In S2 i modelli grandi esplodevano (x10 girava 50ep su gradienti inf = spazzatura).
Test: x10 (h=122) con --grad_clip agc (Adaptive Gradient Clipping) MANTENENDO Prodigy.
Ipotesi: AGC doma l'esplosione (gn resta basso) senza cambiare optimizer.

Confronto diretto: LS2_x10_h122_ff (no AGC, esplosa) vs LS2_x10_h122_agc (AGC).
Se gn resta basso e val_data/NRMSE migliorano -> AGC funziona -> rifacciamo lo sweep con AGC.

Genera Loss_Study_S2b_AGC.ipynb. Pattern clonato da S2.
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
    return {
        'cells': cells,
        'metadata': {
            'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
            'language_info': {'name': 'python', 'version': '3.x'},
        },
        'nbformat': 4, 'nbformat_minor': 5,
    }


MARKDOWN_INTRO = """# Loss_Study S2b — test AGC su x10

In S2 i modelli grandi esplodevano (x10 = 50ep su gradienti inf = spazzatura; guard
fallito al contrario). Fix applicati: **guard v2** (conta inf) + **AGC** opt-in
(clip per-unita relativo a ||w||, optimizer-agnostico -> mantiene Prodigy).

**Test**: x10 (h=122) con `--grad_clip agc`. Ipotesi: AGC doma l'esplosione (gn basso)
senza cambiare optimizer. Confronto vs la x10 esplosa (LS2_x10_h122_ff).

Se gn resta basso e NRMSE/val_data migliorano -> rifacciamo lo sweep con AGC.
"""


CELL_1_BOOTSTRAP = """# Cell 1 -- Bootstrap + ENV check
import sys, os, subprocess
import importlib.util as _imu

RESULTS_DIR = 'results/Loss_Study/S2_Capacity'
BRANCH = 'Loss_Study'
FREEFLOW_MIX = 'highway:0.35,urban:0.25,truck:0.15,mixed:0.05,freeflow:0.20'
CACHE = 'data/cache_1500_freeflow_cut0.0_ou0.0.pt'
CHANS = ['v0', 'T', 's0', 'a', 'b']
_TMP_MSG = '/tmp/ls2b_msg.txt' if os.path.isdir('/tmp') else 'ls2b_msg.txt'

for pkg in ['prodigyopt', 'pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)

# verifica che train.py conosca --grad_clip agc (patch S2b applicata)
help_txt = subprocess.run([sys.executable, 'train.py', '--help'],
                          capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
assert '--grad_clip' in help_txt and '--agc_lambda' in help_txt, 'patch AGC non presente in train.py!'

br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
assert br == BRANCH, f'branch={br} != {BRANCH}'
print(f'[S2b] ENV OK. branch={br}  AGC disponibile')"""


CELL_2_CONFIG = '''# Cell 2 -- Config x10 + AGC (mantiene Prodigy)
X10_AGC = {
    'optimizer': 'prodigy', 'lr': 0.5,
    'd0': 1e-6, 'd_coef': 1.0, 'growth_rate': 'inf',
    'epochs': 50, 'max_steps_per_epoch': 100,
    'seq_len': 50,
    'hidden_size': 122, 'rank': 30,   # x10 (~8662 params)
    'max_delay': 6, 'bit_shift': 3,
    'lambda_sr': 0.5,
    'lambda_T_aux': 0.0, 'lambda_v0_aux': 0.0, 'lambda_s0_aux': 0.0,
    'lambda_a_aux': 0.0, 'lambda_b_aux': 0.0,
    'scenario_mix': FREEFLOW_MIX, 'cut_in_ratio': 0.0, 'cache_path': CACHE,
    'po2_enabled': 1, 'init_bias_shift': 1,
    'tau_init': 1.0, 'tau_final': 1.0, 'tau_schedule': 'const',
    'tau_per_channel': '10.0,3.0,10.0,3.0,3.0',
    'max_epoch_explosion_streak': 2,
    'epoch_explosion_threshold': 10000.0, 'epoch_explosion_frac': 0.5,
    'grad_clip': 'agc', 'agc_lambda': 0.01,   # <-- AGC attivo (Prodigy invariato)
    'scheduler': 'custom_restart', 'T0': 5, 'restart_T0': 12,
    'restart_decay': 1.0, 'restart_lr_after': -1.0,
    'restart_warmup_epochs': 2, 'restart_adaptive': 0,
    'tag': 'LS2_x10_h122_agc', 'desc': 'x10 (h=122) + AGC, Prodigy invariato',
}
EXPERIMENTS = [X10_AGC]
print('S2b run:', X10_AGC['tag'], '| AGC lambda', X10_AGC['agc_lambda'], '| optimizer', X10_AGC['optimizer'])'''


CELL_3_RUN = '''# Cell 3 -- Run x10+AGC + push
import subprocess, sys, time, os, shutil, glob, datetime
import pandas as pd

def _build_cli(e):
    cli = [sys.executable, 'train.py', '--training_method', 'baseline',
        '--epochs', str(e['epochs']), '--max_steps_per_epoch', str(e['max_steps_per_epoch']),
        '--batch_size', '8', '--val_batch_size', '32', '--seq_len', str(e['seq_len']),
        '--cf_hidden_size', str(e['hidden_size']), '--cf_rank', str(e['rank']),
        '--cf_max_delay', str(e['max_delay']), '--cf_bit_shift', str(e['bit_shift']),
        '--cf_init_bias_shift', str(e['init_bias_shift']),
        '--cf_logit_tau_init', str(e['tau_init']), '--cf_logit_tau_final', str(e['tau_final']),
        '--cf_logit_tau_schedule', e['tau_schedule'],
        '--lambda_data', '1.0', '--lambda_phys', '0.1', '--lambda_ou', '0.05',
        '--lambda_bc', '1.0', '--lambda_sr', str(e['lambda_sr']),
        '--lambda_T_aux', str(e['lambda_T_aux']), '--lambda_v0_aux', str(e['lambda_v0_aux']),
        '--lambda_s0_aux', str(e['lambda_s0_aux']), '--lambda_a_aux', str(e['lambda_a_aux']),
        '--lambda_b_aux', str(e['lambda_b_aux']),
        '--scenario_mix', e['scenario_mix'], '--cut_in_ratio', str(e['cut_in_ratio']),
        '--noise_scale', '0.0', '--po2_enabled', str(e['po2_enabled']),
        '--n_train', '1500', '--n_val', '300',
        '--max_inf_streak', '99999', '--early_stop_patience', '0',
        '--data_cache', e['cache_path'], '--optimizer', e['optimizer'],
        '--lr', str(e['lr']), '--max_lr', str(e['lr']), '--scheduler', e['scheduler'],
        '--T0', str(e['T0']), '--restart_T0', str(e['restart_T0']),
        '--restart_decay', str(e['restart_decay']), '--restart_lr_after', str(e['restart_lr_after']),
        '--restart_warmup_epochs', str(e['restart_warmup_epochs']),
        '--restart_adaptive', str(e['restart_adaptive']),
        '--prodigy_betas', '0.9,0.99', '--prodigy_d_coef', str(e['d_coef']),
        '--prodigy_d0', str(e['d0']), '--prodigy_weight_decay', '0.01',
        '--prodigy_use_bias_correction', '1', '--prodigy_safeguard_warmup', '1',
        '--prodigy_growth_rate', str(e['growth_rate']),
        '--max_epoch_explosion_streak', str(e['max_epoch_explosion_streak']),
        '--epoch_explosion_threshold', str(e['epoch_explosion_threshold']),
        '--epoch_explosion_frac', str(e['epoch_explosion_frac']),
        '--grad_clip', e['grad_clip'], '--agc_lambda', str(e['agc_lambda']),
        '--tag', e['tag']]
    if e.get('tau_per_channel'):
        cli.extend(['--cf_logit_tau_per_channel', e['tau_per_channel']])
    return cli

def _push_run(e):
    tag = e['tag']; src = f'checkpoints/{tag}'; dst = f"{RESULTS_DIR}/{tag}"
    if not os.path.isdir(src):
        return False
    if os.path.isdir(dst):
        shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(f'{dst}/plots', exist_ok=True)
    for f in glob.glob(f'{src}/*.csv') + glob.glob(f'{src}/*.json'):
        shutil.copy2(f, dst)
    for f in glob.glob(f'{src}/plots/*.png'):
        shutil.copy2(f, f'{dst}/plots/')
    vs = ''
    lp = f'{dst}/training_log.csv'
    if os.path.isfile(lp):
        edf = pd.read_csv(lp)
        if len(edf) > 0:
            vs = f'min val_data={edf.val_data.min():.4f} ({len(edf)}ep)'
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    with open(_TMP_MSG, 'w', encoding='utf-8') as fp:
        fp.write(f'results (Loss_Study S2b AGC): {tag} ({ts})\\n\\n{vs}\\ndesc={e["desc"]}\\nBranch: {BRANCH}\\n')
    try:
        subprocess.run(['git', 'add', dst], check=True, capture_output=True)
        r = subprocess.run(['git', 'commit', '-F', _TMP_MSG], capture_output=True, text=True)
        if r.returncode != 0 and 'nothing to commit' not in (r.stdout + r.stderr):
            print('commit fail', r.stderr[-200:]); return False
        subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True, text=True)
        r2 = subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True, text=True)
        print('push OK' if r2.returncode == 0 else f'push fail {r2.stderr[-200:]}')
        return r2.returncode == 0
    finally:
        try: os.remove(_TMP_MSG)
        except Exception: pass

e = EXPERIMENTS[0]
print(f"[RUN] {e['tag']} (h={e['hidden_size']}, AGC lambda={e['agc_lambda']})")
t0 = time.time()
r = subprocess.run(_build_cli(e), capture_output=False)
print(f"-> rc={r.returncode} ({(time.time()-t0)/60:.1f}min)")
print('pushed:', _push_run(e))'''


CELL_4_COMPARE = '''# Cell 4 -- Confronto AGC vs no-AGC su x10: gn domato? NRMSE migliore?
import os, csv, math, json
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown
from collections import defaultdict

pairs = [('x10 NO-AGC (esplosa)', 'LS2_x10_h122_ff'),
         ('x10 + AGC', 'LS2_x10_h122_agc')]

def gn_med_per_ep(tag):
    p = f"{RESULTS_DIR}/{tag}/training_batch_log.csv"
    if not os.path.isfile(p):
        return None
    byep = defaultdict(list)
    for r in csv.DictReader(open(p, encoding='utf-8')):
        try:
            g = float(r['gn_total_preclip'])
            if math.isfinite(g):
                byep[int(r['epoch'])].append(g)
        except Exception:
            pass
    return {ep: sorted(v)[len(v)//2] for ep, v in byep.items() if v}

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
summ = []
for label, tag in pairs:
    lp = f"{RESULTS_DIR}/{tag}/training_log.csv"
    if not os.path.isfile(lp):
        print('manca', lp); continue
    e = pd.read_csv(lp)
    gm = gn_med_per_ep(tag)
    if gm:
        ax1.plot(list(gm.keys()), list(gm.values()), marker='.', label=label)
    ax2.plot(e['epoch'], e['val_data'], marker='.', label=label)
    i = int(e['val_data'].idxmin())
    row = {'run': label, 'ep': len(e), 'min_val_data': round(float(e['val_data'].min()), 4)}
    for c in CHANS:
        row[f'nrmse_{c}'] = round(float(e[f'val_{c}_nrmse'].iloc[i]), 3)
    summ.append(row)
ax1.set_yscale('log'); ax1.set_xlabel('epoch'); ax1.set_ylabel('gn mediana (log)')
ax1.set_title('Gradiente domato? (AGC dovrebbe restare basso)'); ax1.legend(); ax1.grid(alpha=0.3)
ax2.set_xlabel('epoch'); ax2.set_ylabel('val_data'); ax2.set_title('val_data')
ax2.legend(); ax2.grid(alpha=0.3)
plt.tight_layout(); plt.savefig(f'{RESULTS_DIR}/_agc_vs_noagc_x10.png', dpi=120); plt.show()
display(Markdown('## AGC vs no-AGC su x10'))
display(pd.DataFrame(summ))
print('Atteso con AGC: gn mediana bassa e stabile, NRMSE/val_data sensati (non spazzatura).')'''


CELL_5_FINAL = """# Cell 5 -- Commit finale
import subprocess
subprocess.run(['git', 'add', RESULTS_DIR], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'Loss_Study S2b: AGC vs no-AGC x10 compare'],
                   capture_output=True, text=True)
print(r.stdout[-200:] if r.returncode == 0 else r.stderr[-200:])
subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
print('S2b pushed.')"""


def main():
    cells = [
        make_cell('markdown', MARKDOWN_INTRO, 'cell-intro'),
        make_cell('code', CELL_1_BOOTSTRAP, 'cell-1'),
        make_cell('code', CELL_2_CONFIG, 'cell-2'),
        make_cell('code', CELL_3_RUN, 'cell-3'),
        make_cell('code', CELL_4_COMPARE, 'cell-4'),
        make_cell('code', CELL_5_FINAL, 'cell-5'),
    ]
    nb = make_notebook(cells)
    out = os.path.join(ROOT, 'Loss_Study_S2b_AGC.ipynb')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
