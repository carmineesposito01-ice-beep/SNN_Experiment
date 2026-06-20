"""Loss_Study S2 — Capacity sweep su dato freeflow.

Teoria (utente): in S1b la NRMSE converge allo STESSO valore per tutti e 5 i canali
-> la rete bilancia l'errore -> forse il collo di bottiglia e' la CAPACITA' (non solo
l'identificabilita'). Rifiuto passato (P9_S2B) era a 4 ep -> non confrontabile. Ritest a 50ep.

Disegno: dataset freeflow FISSO (= approccio A, osservabilita'), unica variabile la
capacita'. ratio params x1/x2/x4/x8/x10. x1 = S1b R0 gia' fatto (copiato come baseline).
4 run nuove (x2,x4,x8,x10).

Lettura: NRMSE per-canale vs capacita'. Scende -> capacita' era il limite (teoria OK).
Plateau -> manifold/identificabilita' (capacita' non e' la risposta).

Genera Loss_Study_S2_Capacity.ipynb alla root. Pattern (ENV/push/3.10) clonato da S1b.
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


MARKDOWN_INTRO = """# Loss_Study S2 — Capacity sweep (dato freeflow fisso)

## Teoria

In S1b la NRMSE converge allo **stesso valore (~0.35) per tutti e 5 i canali** -> la rete
bilancia l'errore su tutti. Ipotesi: il collo di bottiglia e' la **CAPACITA'**, non solo
l'identificabilita'. (Il rifiuto passato P9_S2B era a 4 ep -> non confrontabile; qui 50 ep.)

## Disegno (1 variabile)

Dataset **freeflow FISSO** (approccio A = osservabilita'); varia SOLO la capacita':

| ratio | h | rank | params |
|---|---|---|---|
| x1 | 32 | 8 | 864 (= S1b R0, gia' fatto) |
| x2 | 50 | 12 | 1750 |
| x4 | 74 | 18 | 3478 |
| x8 | 108 | 27 | 7020 |
| x10 | 122 | 30 | 8662 |

x1 e' copiato da S1b R0. **4 run nuove** (x2,x4,x8,x10), ~5h.

## Lettura (Cell 4)

NRMSE per-canale **vs capacita'**:
- linee **scendono** -> capacita' era il limite (teoria CONFERMATA, il bilanciamento si rompe);
- **plateau** -> non e' capacita', e' il manifold/identificabilita';
- se alcuni canali scendono piu' di altri -> quali la capacita' sbloccava.
"""


CELL_1_BOOTSTRAP = """# Cell 1 -- Bootstrap + ENV check
import sys, os, subprocess
import importlib.util as _imu

RESULTS_DIR = 'results/Loss_Study/S2_Capacity'
BRANCH = 'Loss_Study'
FREEFLOW_MIX = 'highway:0.35,urban:0.25,truck:0.15,mixed:0.05,freeflow:0.20'
CACHE = 'data/cache_1500_freeflow_cut0.0_ou0.0.pt'
CHANS = ['v0', 'T', 's0', 'a', 'b']
_TMP_MSG = '/tmp/ls2_msg.txt' if os.path.isdir('/tmp') else 'ls2_msg.txt'
os.makedirs(RESULTS_DIR, exist_ok=True)

for pkg in ['prodigyopt', 'pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)

from data.generator import parse_scenario_mix
mix = parse_scenario_mix(FREEFLOW_MIX)
assert mix.get('freeflow', 0) > 0, 'scenario freeflow assente!'

x1 = f'{RESULTS_DIR}/LS2_x1_h32_ff/training_log.csv'
print('  x1 (S1b R0) presente:', os.path.isfile(x1))

br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
assert br == BRANCH, f'branch={br} != {BRANCH}'
print(f'[S2] ENV OK. branch={br}  RESULTS_DIR={RESULTS_DIR}')"""


CELL_2_CONFIG = '''# Cell 2 -- Config sweep capacita' (PEAK freeflow, varia solo h/rank)
PEAK_FF = {
    'optimizer': 'prodigy', 'lr': 0.5,
    'd0': 1e-6, 'd_coef': 1.0, 'growth_rate': 'inf',
    'epochs': 50, 'max_steps_per_epoch': 100,
    'seq_len': 50,
    'max_delay': 6, 'bit_shift': 3,
    'lambda_sr': 0.5,
    'lambda_T_aux': 0.0, 'lambda_v0_aux': 0.0, 'lambda_s0_aux': 0.0,
    'lambda_a_aux': 0.0, 'lambda_b_aux': 0.0,
    'scenario_mix': FREEFLOW_MIX,
    'cut_in_ratio': 0.0,
    'cache_path': CACHE,
    'po2_enabled': 1,
    'init_bias_shift': 1,
    'tau_init': 1.0, 'tau_final': 1.0, 'tau_schedule': 'const',
    'tau_per_channel': '10.0,3.0,10.0,3.0,3.0',
    'max_epoch_explosion_streak': 2,
    'epoch_explosion_threshold': 10000.0,
    'epoch_explosion_frac': 0.5,   # guard frazione-based (fix S1b)
    'scheduler': 'custom_restart',
    'T0': 5, 'restart_T0': 12,
    'restart_decay': 1.0, 'restart_lr_after': -1.0,
    'restart_warmup_epochs': 2,
    'restart_adaptive': 0,
}

# (ratio, hidden_size, rank). x1 = gia' fatto (copia S1b R0) -> NON rilanciato.
CAPS = [
    ('x1',   32,  8),   # 864  (esistente)
    ('x2',   50, 12),   # 1750
    ('x4',   74, 18),   # 3478
    ('x8',  108, 27),   # 7020
    ('x10', 122, 30),   # 8662
]

EXPERIMENTS = []
for ratio, h, r in CAPS:
    if ratio == 'x1':
        continue   # baseline gia' presente
    e = dict(PEAK_FF)
    e.update({'hidden_size': h, 'rank': r,
              'tag': f'LS2_{ratio}_h{h}_ff', 'axis': 'cap',
              'desc': f'capacity {ratio} (h={h}, rank={r}) su freeflow, no aux'})
    EXPERIMENTS.append(e)

print(f'S2 run NUOVE: {len(EXPERIMENTS)} (x1 riusa S1b R0)')
for e in EXPERIMENTS:
    print(f"  {e['tag']:<16} h={e['hidden_size']:<4} rank={e['rank']}")'''


CELL_3_RUN = '''# Cell 3 -- Sweep loop + push per run
import subprocess, sys, time, os, shutil, glob, datetime
import pandas as pd

SKIP_IF_EXISTS = True

def _robust_rmtree(path, n=3):
    for i in range(n):
        if not os.path.isdir(path):
            return True
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.isdir(path):
            return True
        time.sleep(0.5 * (i + 1))
    return not os.path.isdir(path)

def _build_cli(e):
    cli = [sys.executable, 'train.py',
        '--training_method', 'baseline',
        '--epochs', str(e['epochs']),
        '--max_steps_per_epoch', str(e['max_steps_per_epoch']),
        '--batch_size', '8', '--val_batch_size', '32',
        '--seq_len', str(e['seq_len']),
        '--cf_hidden_size', str(e['hidden_size']),
        '--cf_rank', str(e['rank']),
        '--cf_max_delay', str(e['max_delay']),
        '--cf_bit_shift', str(e['bit_shift']),
        '--cf_init_bias_shift', str(e['init_bias_shift']),
        '--cf_logit_tau_init', str(e['tau_init']),
        '--cf_logit_tau_final', str(e['tau_final']),
        '--cf_logit_tau_schedule', e['tau_schedule'],
        '--lambda_data', '1.0', '--lambda_phys', '0.1', '--lambda_ou', '0.05',
        '--lambda_bc', '1.0', '--lambda_sr', str(e['lambda_sr']),
        '--lambda_T_aux', str(e['lambda_T_aux']),
        '--lambda_v0_aux', str(e['lambda_v0_aux']),
        '--lambda_s0_aux', str(e['lambda_s0_aux']),
        '--lambda_a_aux', str(e['lambda_a_aux']),
        '--lambda_b_aux', str(e['lambda_b_aux']),
        '--scenario_mix', e['scenario_mix'],
        '--cut_in_ratio', str(e['cut_in_ratio']),
        '--noise_scale', '0.0', '--po2_enabled', str(e['po2_enabled']),
        '--n_train', '1500', '--n_val', '300',
        '--max_inf_streak', '99999', '--early_stop_patience', '0',
        '--data_cache', e['cache_path'],
        '--optimizer', e['optimizer'],
        '--lr', str(e['lr']), '--max_lr', str(e['lr']),
        '--scheduler', e['scheduler'],
        '--T0', str(e['T0']),
        '--restart_T0', str(e['restart_T0']),
        '--restart_decay', str(e['restart_decay']),
        '--restart_lr_after', str(e['restart_lr_after']),
        '--restart_warmup_epochs', str(e['restart_warmup_epochs']),
        '--restart_adaptive', str(e['restart_adaptive']),
        '--prodigy_betas', '0.9,0.99',
        '--prodigy_d_coef', str(e['d_coef']),
        '--prodigy_d0', str(e['d0']),
        '--prodigy_weight_decay', '0.01',
        '--prodigy_use_bias_correction', '1',
        '--prodigy_safeguard_warmup', '1',
        '--prodigy_growth_rate', str(e['growth_rate']),
        '--max_epoch_explosion_streak', str(e['max_epoch_explosion_streak']),
        '--epoch_explosion_threshold', str(e['epoch_explosion_threshold']),
        '--epoch_explosion_frac', str(e['epoch_explosion_frac']),
        '--tag', e['tag']]
    if e.get('tau_per_channel'):
        cli.extend(['--cf_logit_tau_per_channel', e['tau_per_channel']])
    return cli

def _push_run(e):
    tag = e['tag']; src = f'checkpoints/{tag}'; dst = f"{RESULTS_DIR}/{tag}"
    if not os.path.isdir(src):
        return False
    _robust_rmtree(dst)
    os.makedirs(f'{dst}/plots', exist_ok=True)
    for f in glob.glob(f'{src}/*.csv') + glob.glob(f'{src}/*.json'):
        shutil.copy2(f, dst)
    for f in glob.glob(f'{src}/plots/*.png'):
        shutil.copy2(f, f'{dst}/plots/')
    val_str = ''
    lp = f'{dst}/training_log.csv'
    if os.path.isfile(lp):
        try:
            edf = pd.read_csv(lp)
            if len(edf) > 0:
                val_str = f'min val_data={edf.val_data.min():.4f} ({len(edf)}ep)'
        except Exception as ex:
            val_str = f'(log err: {ex})'
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    msg = f'results (Loss_Study S2 capacity): {tag} ({ts})\\n\\n{val_str}\\ndesc={e["desc"]}\\nBranch: {BRANCH}\\n'
    with open(_TMP_MSG, 'w', encoding='utf-8') as fp:
        fp.write(msg)
    try:
        subprocess.run(['git', 'add', dst], check=True, capture_output=True)
        r = subprocess.run(['git', 'commit', '-F', _TMP_MSG], capture_output=True, text=True)
        if r.returncode != 0:
            if 'nothing to commit' in r.stdout or 'nothing to commit' in r.stderr:
                return True
            print(f'   [commit fail] {r.stderr[-300:]}'); return False
        subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True, text=True)
        r2 = subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True, text=True)
        if r2.returncode != 0:
            print(f'   [push fail] {r2.stderr[-300:]}'); return False
        print('   [push OK]'); return True
    finally:
        try:
            os.remove(_TMP_MSG)
        except Exception:
            pass

t_start = time.time()
total = len(EXPERIMENTS)
for i, e in enumerate(EXPERIMENTS, 1):
    dst_log = f"{RESULTS_DIR}/{e['tag']}/training_log.csv"
    if SKIP_IF_EXISTS and os.path.isfile(dst_log) and len(pd.read_csv(dst_log)) >= e['epochs'] * 0.8:
        print(f"\\n[{i}/{total}] [SKIP] {e['tag']}")
        continue
    print(f"\\n{'='*70}\\n[{i}/{total}] {e['tag']}  ({e['desc']})\\n{'='*70}")
    t0 = time.time()
    r = subprocess.run(_build_cli(e), capture_output=False)
    el = time.time() - t0
    eta = ((time.time() - t_start) / max(i, 1)) * (total - i) / 60
    print(f"\\n[{i}/{total}] {e['tag']} -> rc={r.returncode} ({el/60:.1f}min) ETA={eta:.0f}min")
    print('pushed:', _push_run(e))
print(f"\\nSWEEP S2 DONE in {(time.time()-t_start)/60:.0f}min")'''


CELL_4_COMPARE = '''# Cell 4 -- NRMSE per-canale vs CAPACITA' (legge tutte le run S2, incl. x1 copiato)
import os, json, glob, pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

rows = []
for d in sorted(glob.glob(f'{RESULTS_DIR}/LS2_*')):
    cfg_p = os.path.join(d, 'config_snapshot.json')
    log_p = os.path.join(d, 'training_log.csv')
    if not (os.path.isfile(cfg_p) and os.path.isfile(log_p)):
        continue
    cfg = json.load(open(cfg_p))
    e = pd.read_csv(log_p)
    if len(e) == 0:
        continue
    i = int(e['val_data'].idxmin())
    h = cfg.get('cf_hidden_size'); rk = cfg.get('cf_rank')
    row = {'tag': os.path.basename(d), 'h': h, 'rank': rk,
           'min_val_data': float(e['val_data'].min()), 'ep': len(e)}
    for c in CHANS:
        col = f'val_{c}_nrmse'
        row[f'nrmse_{c}'] = float(e[col].iloc[i]) if col in e.columns else float('nan')
    rows.append(row)

df = pd.DataFrame(rows)
# params ~ h*(10+2*rank); ordina per capacita'
df['params'] = df['h'] * (10 + 2 * df['rank'])
df = df.sort_values('params').reset_index(drop=True)
df.to_csv(f'{RESULTS_DIR}/_capacity_compare.csv', index=False)
display(Markdown('## NRMSE per-canale vs capacita'))
display(df[['tag', 'h', 'rank', 'params', 'min_val_data'] + [f'nrmse_{c}' for c in CHANS]].round(4))

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
for c in CHANS:
    ax1.plot(df['params'], df[f'nrmse_{c}'], marker='o', label=c)
ax1.set_xlabel('parametri rete'); ax1.set_ylabel('NRMSE @ best val_data')
ax1.set_title('NRMSE per-canale vs capacita (scende=capacita era il limite; plateau=manifold)')
ax1.set_xscale('log'); ax1.set_ylim(bottom=0); ax1.legend(); ax1.grid(alpha=0.3)
# media + spread (il "bilanciamento" si rompe?)
nrmse_cols = [f'nrmse_{c}' for c in CHANS]
ax2.plot(df['params'], df[nrmse_cols].mean(axis=1), marker='s', color='k', label='media 5 canali')
ax2.fill_between(df['params'], df[nrmse_cols].min(axis=1), df[nrmse_cols].max(axis=1),
                 alpha=0.15, label='min-max (spread)')
ax2.set_xlabel('parametri rete'); ax2.set_ylabel('NRMSE'); ax2.set_xscale('log')
ax2.set_title('Media e spread NRMSE vs capacita'); ax2.set_ylim(bottom=0); ax2.legend(); ax2.grid(alpha=0.3)
plt.tight_layout(); plt.savefig(f'{RESULTS_DIR}/_capacity_compare.png', dpi=120); plt.show()
print(f'Saved {RESULTS_DIR}/_capacity_compare.csv + .png')'''


CELL_5_FINAL = """# Cell 5 -- Commit finale
import subprocess
subprocess.run(['git', 'add', RESULTS_DIR], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'Loss_Study S2: capacity sweep compare'],
                   capture_output=True, text=True)
print(r.stdout[-300:] if r.returncode == 0 else r.stderr[-300:])
subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
print('S2 pushed.')"""


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
    out = os.path.join(ROOT, 'Loss_Study_S2_Capacity.ipynb')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
