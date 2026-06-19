"""Loss_Study S3 — osservabilita' forte di 'a' (scenario launch).

Diagnosi (da S1b + check gradiente): il freeflow ha TRIPLICATO il gradiente di v0 ma
lasciato 'a' INVARIATO (1.02x). Motivo fisico: 'a' si vede solo dove |a_pred| e' grande
(accelerazione forte), e il freeflow ha 1 transitorio + lunga crociera. Fix: scenario
'launch' = accelerazioni forti RIPETUTE (ego 63% tempo a |a|>1 vs freeflow 12%).

Esperimento: 1 run PEAK R0 su mix con launch ~35% (+freeflow 15% per non perdere v0).
Check decisivo: gn_decoded_a SALE? a_nrmse SCENDE e RESTA giu' (no ricollasso come S1b)?
Nessun aux (osservabilita' pura). Decoder invariato (sempre 5 param).

Genera Loss_Study_S3.ipynb. Pattern clonato da S1b.
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


MARKDOWN_INTRO = """# Loss_Study S3 — osservabilita' forte di `a` (scenario launch)

## Diagnosi

Il freeflow ha **triplicato il gradiente di v0** (-> v0 migliorato) ma lasciato `a`
**invariato** (1.02x). `a` si vede solo dove `|a_pred|` e' grande (accelerazione forte);
il freeflow ha 1 transitorio + lunga crociera -> poco segnale per `a`.

## Fix

Scenario **launch** = accelerazioni forti RIPETUTE (ego **63%** del tempo a `|a|>1` vs
freeflow 12%). Mix con launch ~35% + freeflow 15% (per non perdere v0). **Nessun aux**
(osservabilita' pura), **decoder invariato** (sempre 5 parametri).

## Check decisivo (Cell 4)

1. `gn_decoded_a` SALE rispetto a vecchia-data/freeflow? (-> `a` ora osservabile)
2. `a_nrmse` SCENDE e **RESTA giu'** (non ricollassa come in S1b dove saliva a 0.57 a ep20
   poi tornava a 0.35)?

Se si' -> osservabilita' e' la leva giusta per `a`. Bonus: ogni run ora ha **G20** (follow
x(t)) dove si vedono i lanci ripetuti.
"""


CELL_1_BOOTSTRAP = """# Cell 1 -- Bootstrap + ENV check
import sys, os, subprocess
import importlib.util as _imu

RESULTS_DIR = 'results/Loss_Study/S3'
BRANCH = 'Loss_Study'
LAUNCH_MIX = 'highway:0.20,urban:0.15,truck:0.10,mixed:0.05,freeflow:0.15,launch:0.35'
CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'
CHANS = ['v0', 'T', 's0', 'a', 'b']
_TMP_MSG = '/tmp/ls3_msg.txt' if os.path.isdir('/tmp') else 'ls3_msg.txt'
os.makedirs(RESULTS_DIR, exist_ok=True)

for pkg in ['prodigyopt', 'pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)

from data.generator import parse_scenario_mix
mix = parse_scenario_mix(LAUNCH_MIX)
assert mix.get('launch', 0) > 0, 'scenario launch assente nel generatore!'
assert abs(sum(mix.values()) - 1.0) < 1e-6, f'mix non somma a 1: {mix}'

br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
assert br == BRANCH, f'branch={br} != {BRANCH}'
print(f'[S3] ENV OK. branch={br}  mix={mix}')"""


CELL_2_CONFIG = '''# Cell 2 -- Config PEAK su mix launch (1 run R0, nessun aux)
PEAK_LAUNCH = {
    'optimizer': 'prodigy', 'lr': 0.5,
    'd0': 1e-6, 'd_coef': 1.0, 'growth_rate': 'inf',
    'epochs': 50, 'max_steps_per_epoch': 100, 'seq_len': 50,
    'hidden_size': 32, 'rank': 8, 'max_delay': 6, 'bit_shift': 3,
    'lambda_sr': 0.5,
    'lambda_T_aux': 0.0, 'lambda_v0_aux': 0.0, 'lambda_s0_aux': 0.0,
    'lambda_a_aux': 0.0, 'lambda_b_aux': 0.0,
    'scenario_mix': LAUNCH_MIX, 'cut_in_ratio': 0.0, 'cache_path': CACHE,
    'po2_enabled': 1, 'init_bias_shift': 1,
    'tau_init': 1.0, 'tau_final': 1.0, 'tau_schedule': 'const',
    'tau_per_channel': '10.0,3.0,10.0,3.0,3.0',
    'max_epoch_explosion_streak': 2, 'epoch_explosion_threshold': 10000.0,
    'epoch_explosion_frac': 0.5, 'grad_clip': 'none', 'agc_lambda': 0.01,
    'scheduler': 'custom_restart', 'T0': 5, 'restart_T0': 12,
    'restart_decay': 0.3, 'restart_lr_after': -1.0,   # Opzione 1+4 (decay 0.3 + warmup 2)
    'restart_warmup_epochs': 2, 'restart_adaptive': 0,
    'tag': 'LS3_PEAK_R0_launch_d03', 'axis': 'PEAK',
    'desc': 'PEAK R0 launch + restart decay 0.3 (Opz.1+4) - stessa data di LS3 launch',
}
EXPERIMENTS = [PEAK_LAUNCH]
print('S3 run:', PEAK_LAUNCH['tag'], '| launch mix | cache', CACHE)
print('NB: la cache launch verra generata al primo run se assente.')'''


CELL_3_RUN = '''# Cell 3 -- Run PEAK R0 launch + push
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
    tag = e['tag']; src = f'checkpoints/{tag}'; dst = f"{RESULTS_DIR}/{e['axis']}/{tag}"
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
        fp.write(f'results (Loss_Study S3 launch): {tag} ({ts})\\n\\n{vs}\\ndesc={e["desc"]}\\nBranch: {BRANCH}\\n')
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
dst_log = f"{RESULTS_DIR}/{e['axis']}/{e['tag']}/training_log.csv"
if os.path.isfile(dst_log) and len(pd.read_csv(dst_log)) >= e['epochs'] * 0.8:
    print(f"[SKIP] {e['tag']} gia presente")
else:
    print(f"[RUN] {e['tag']} (cache launch generata se assente)")
    t0 = time.time()
    r = subprocess.run(_build_cli(e), capture_output=False)
    print(f"-> rc={r.returncode} ({(time.time()-t0)/60:.1f}min)")
    print('pushed:', _push_run(e))'''


CELL_4_COMPARE = '''# Cell 4 -- Check decisivo: 'a' ora osservabile? (gradiente + NRMSE)
import os, csv, math
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

# (label, batch_log per gradiente, training_log per nrmse)
runs = [
    ('S1 vecchia',     'results/Loss_Study/S1/PEAK/LS1_PEAK_R0_obs'),
    ('S1b freeflow',   'results/Loss_Study/S2_Capacity/LS2_x1_h32_ff'),
    ('S3 launch d1.0', f'{RESULTS_DIR}/PEAK/LS3_PEAK_R0_launch'),
    ('S3 launch d0.3', f'{RESULTS_DIR}/PEAK/LS3_PEAK_R0_launch_d03'),
]

def gn_decoded_mean(folder):
    p = os.path.join(folder, 'training_batch_log.csv')
    if not os.path.isfile(p):
        return None
    acc = {c: [] for c in CHANS}
    for r in csv.DictReader(open(p, encoding='utf-8')):
        for c in CHANS:
            try:
                x = float(r[f'gn_decoded_{c}'])
                if math.isfinite(x):
                    acc[c].append(x)
            except Exception:
                pass
    return {c: (sum(v)/len(v) if v else float('nan')) for c, v in acc.items()}

rows = []
fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(18, 5))
for label, folder in runs:
    gd = gn_decoded_mean(folder)
    lp = os.path.join(folder, 'training_log.csv')
    if gd is None or not os.path.isfile(lp):
        print('manca', folder); continue
    e = pd.read_csv(lp)
    i = int(e['val_data'].idxmin())
    rows.append({'run': label, 'gn_decoded_a': gd['a'], 'gn_decoded_v0': gd['v0'],
                 'a_nrmse@best': round(float(e['val_a_nrmse'].iloc[i]), 3),
                 'a_pred@best': round(float(e['val_a_pred_mean'].iloc[i]), 3),
                 'min_val_data': round(float(e['val_data'].min()), 4), 'ep': len(e)})
    if 'val_a_nrmse' in e.columns:
        ax2.plot(e['epoch'], e['val_a_nrmse'], marker='.', label=label)
    ax3.plot(e['epoch'], e['val_data'], marker='.', label=label, alpha=0.8)
df = pd.DataFrame(rows)
# barre gradiente 'a' per run
if len(df):
    ax1.bar(df['run'], df['gn_decoded_a'], color='tab:green', alpha=0.8)
    ax1.set_ylabel('gn_decoded_a (gradiente medio su a)')
    ax1.set_title("Gradiente su 'a': il launch lo alza? (a osservabile)")
    ax1.grid(alpha=0.3, axis='y')
ax2.set_xlabel('epoch'); ax2.set_ylabel('a_nrmse'); ax2.set_ylim(bottom=0)
ax2.set_title("a_nrmse nel tempo: scende e RESTA giu'?"); ax2.legend(); ax2.grid(alpha=0.3)
ax3.set_xlabel('epoch'); ax3.set_ylabel('val_data')
ax3.set_title('val_data: i bump ai restart spariscono con decay 0.3?'); ax3.legend(fontsize=8); ax3.grid(alpha=0.3)
plt.tight_layout(); plt.savefig(f'{RESULTS_DIR}/S3_a_observability.png', dpi=120); plt.show()
display(Markdown("## S3 — `a` ora osservabile? (atteso: gn_decoded_a su, a_nrmse giu e stabile)"))
display(df)
print("vero a ~1.1 (highway base). a_pred@best dovrebbe avvicinarsi (era ~0.43 collassato).")'''


CELL_5_FINAL = """# Cell 5 -- Commit finale
import subprocess
subprocess.run(['git', 'add', RESULTS_DIR], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'Loss_Study S3: a-observability (launch) compare'],
                   capture_output=True, text=True)
print(r.stdout[-200:] if r.returncode == 0 else r.stderr[-200:])
subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
print('S3 pushed.')"""


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
    out = os.path.join(ROOT, 'Loss_Study_S3.ipynb')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
