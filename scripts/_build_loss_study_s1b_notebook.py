"""Loss_Study S1b "excitation" — dato piu' ricco (scenario freeflow) per rendere
v0 e a identificabili, senza toccare il decoder (la rete predice sempre 5 param).

Esperimento minimale e decisivo:
  - cache nuova con freeflow ~20% (highway:0.35,urban:0.25,truck:0.15,mixed:0.05,freeflow:0.20)
  - 1 run PEAK R0 (nessun aux) su questa cache
  - confronto G19: NRMSE v0/a freeflow-R0 vs S1-R0 (vecchia cache)
Ipotesi: v0 NRMSE crolla da 0.50, a da 0.36, SENZA supervisione -> identificabilita'
recuperata dai dati. In piu': nuovi G13 freeflow + plot traiettorie x(t) spazio-tempo.

Genera Loss_Study_S1b.ipynb alla root. Pattern (ENV/push/3.10) clonato da S1.
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


MARKDOWN_INTRO = """# Loss_Study S1b — excitation (dato piu' ricco)

## Diagnosi (da S1)

Su accelerazione da sola, v0 e a NON sono identificabili: la rete parcheggia v0 al
bound alto (~41 vs vero ~33) e a al pavimento (~0.41 vs vero ~1.1), compensandosi su
un manifold molle (confermato causalmente). Causa radice trovata nel codice: nessuno
scenario usava il profilo `free` -> zero flusso libero -> v0 mai osservabile.

## Fix (questo studio)

Nuovo scenario **freeflow** (~20%, profilo `free`): l'ego accelera fino a v0 (eccita
v0 + a + b nel transitorio). **Il decoder NON cambia: la rete predice sempre 5
parametri.** Cambia solo cosa vede nei dati.

## Esperimento

1 run **PEAK R0** (no aux, 50 ep) su cache freeflow -> confronto NRMSE v0/a vs S1-R0.
**Ipotesi**: v0/a NRMSE crollano senza supervisione = identificabilita' dai dati.
"""


CELL_1_BOOTSTRAP = """# Cell 1 -- Bootstrap + ENV check
import sys, os, subprocess
import importlib.util as _imu

RESULTS_DIR = 'results/Loss_Study/S1b'
BRANCH = 'Loss_Study'
FREEFLOW_MIX = 'highway:0.35,urban:0.25,truck:0.15,mixed:0.05,freeflow:0.20'
CACHE = 'data/cache_1500_freeflow_cut0.0_ou0.0.pt'
CHANS = ['v0', 'T', 's0', 'a', 'b']
S1_R0 = 'results/Loss_Study/S1/PEAK/LS1_PEAK_R0_obs/training_log.csv'
_TMP_MSG = '/tmp/ls1b_msg.txt' if os.path.isdir('/tmp') else 'ls1b_msg.txt'
os.makedirs(RESULTS_DIR, exist_ok=True)

for pkg in ['prodigyopt', 'pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)

for f in ['train.py', 'data/generator.py']:
    assert os.path.isfile(f), f'missing {f}'

# Verifica che il generatore conosca lo scenario freeflow (patch S1b applicata)
from data.generator import parse_scenario_mix
mix = parse_scenario_mix(FREEFLOW_MIX)
assert mix.get('freeflow', 0) > 0, 'scenario freeflow non disponibile nel generatore!'
assert abs(sum(mix.values()) - 1.0) < 1e-6, f'mix non somma a 1: {mix}'

br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
assert br == BRANCH, f'branch={br} != {BRANCH}'
print(f'[S1b] ENV OK. branch={br}  mix={mix}')"""


CELL_2_CONFIG = '''# Cell 2 -- Config PEAK su cache freeflow (1 run R0, nessun aux)
PEAK_FF = {
    'optimizer': 'prodigy', 'lr': 0.5,
    'd0': 1e-6, 'd_coef': 1.0, 'growth_rate': 'inf',
    'epochs': 50, 'max_steps_per_epoch': 100,
    'seq_len': 50,
    'hidden_size': 32, 'rank': 8,
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
    'epoch_explosion_frac': 0.5,   # guard frazione-based (fix S1b): no abort su spike isolati
    'scheduler': 'custom_restart',
    'T0': 5, 'restart_T0': 12,
    'restart_decay': 1.0, 'restart_lr_after': -1.0,
    'restart_warmup_epochs': 2,   # PEAK = A4 warmup 2ep
    'restart_adaptive': 0,
    'tag': 'LS1b_PEAK_R0_ff', 'axis': 'PEAK',
    'desc': 'PEAK R0 su dataset freeflow (excitation v0/a), no aux',
}
EXPERIMENTS = [PEAK_FF]
print('S1b run:', PEAK_FF['tag'], '| epochs', PEAK_FF['epochs'], '| cache', CACHE)
print('NB: la cache verra generata al primo run (mix freeflow) se assente.')'''


CELL_3_TRAJ = '''# Cell 3 -- Plot traiettorie x(t) spazio-tempo (standalone, generatore in sola lettura)
# Sicuro: NON tocca il training. Genera scenari esempio e plotta posizione+velocita.
import numpy as np
import matplotlib.pyplot as plt
from data.generator import simulate_trajectory
from config import IDM_HWY, IDM_URB, DT

def _traj(profile, base, seed):
    p = dict(base); v0 = p['v0']
    tr = simulate_trajectory(p, profile=profile, seed=seed, noise_scale=0.0)
    s, v, dv, vl, vdot, T, mask = tr.T
    t = np.arange(len(v)) * DT
    x_ego = np.cumsum(v) * DT
    return dict(t=t, v=v, vl=vl, vdot=vdot, x_ego=x_ego, x_lead=x_ego + s, v0=v0, s=s)

examples = [
    ('freeflow (free)',   _traj('free',        IDM_HWY, 1)),
    ('highway (constant)', _traj('constant',    IDM_HWY, 1)),
    ('urban (stop&go)',   _traj('stop_and_go', IDM_URB, 1)),
]

fig, axes = plt.subplots(2, len(examples), figsize=(5.2 * len(examples), 8), sharex=True)
for j, (name, d) in enumerate(examples):
    ax = axes[0, j]
    ax.plot(d['t'], d['x_ego'], label='ego x(t)', lw=2)
    ax.plot(d['t'], d['x_lead'], label='leader x(t)', ls='--', lw=2)
    ax.fill_between(d['t'], d['x_ego'], d['x_lead'], alpha=0.12)
    ax.set_title(name)
    if j == 0:
        ax.set_ylabel('posizione [m]')
    ax.legend(loc='upper left', fontsize=8); ax.grid(alpha=0.3)
    ax2 = axes[1, j]
    ax2.plot(d['t'], d['v'], label='v_ego', lw=2)
    ax2.plot(d['t'], d['vl'], label='v_leader', ls='--', lw=2)
    ax2.axhline(d['v0'], color='r', ls=':', label=f"v0={d['v0']:.0f}")
    ax2.set_xlabel('t [s]')
    if j == 0:
        ax2.set_ylabel('velocita [m/s]')
    ax2.legend(loc='lower right', fontsize=8); ax2.grid(alpha=0.3)
fig.suptitle('Traiettorie x(t) spazio-tempo per scenario (area = gap). freeflow: ego raggiunge v0', y=1.0)
plt.tight_layout()
out = f'{RESULTS_DIR}/S1b_trajectories.png'
plt.savefig(out, dpi=120); plt.show()
print('saved', out)'''


CELL_4_RUN = '''# Cell 4 -- Run PEAK R0 su cache freeflow + push
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
    tag = e['tag']; src = f'checkpoints/{tag}'; dst = f"{RESULTS_DIR}/{e['axis']}/{tag}"
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
    msg = f'results (Loss_Study S1b): {tag} ({ts})\\n\\n{val_str}\\ndesc={e["desc"]}\\nBranch: {BRANCH}\\n'
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

e = EXPERIMENTS[0]
dst_log = f"{RESULTS_DIR}/{e['axis']}/{e['tag']}/training_log.csv"
if SKIP_IF_EXISTS and os.path.isfile(dst_log) and len(pd.read_csv(dst_log)) >= e['epochs'] * 0.8:
    print(f"[SKIP] {e['tag']} gia presente")
else:
    print(f"[RUN] {e['tag']} (la cache freeflow verra generata se assente)")
    t0 = time.time()
    r = subprocess.run(_build_cli(e), capture_output=False)
    print(f"-> returncode={r.returncode}  ({(time.time()-t0)/60:.1f}min)")
    print('pushed:', _push_run(e))'''


CELL_5_G19_COMPARE = '''# Cell 5 -- Confronto NRMSE v0/a: freeflow (S1b) vs vecchia cache (S1)
import os, pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

ff_log = f"{RESULTS_DIR}/PEAK/LS1b_PEAK_R0_ff/training_log.csv"
pairs = [('S1 (vecchia cache)', S1_R0), ('S1b (freeflow)', ff_log)]

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
summary = []
for label, path in pairs:
    if not os.path.isfile(path):
        print(f'  manca: {path}'); continue
    e = pd.read_csv(path)
    i = int(e['val_data'].idxmin())
    for ax, ch in zip(axes, ['v0', 'a']):
        col = f'val_{ch}_nrmse'
        if col in e.columns:
            ax.plot(e['epoch'], e[col], marker='.', label=label)
    summary.append({'dataset': label, 'min_val_data': round(float(e['val_data'].min()), 4),
                    'v0_nrmse@best': round(float(e['val_v0_nrmse'].iloc[i]), 3),
                    'a_nrmse@best': round(float(e['val_a_nrmse'].iloc[i]), 3),
                    'ep': len(e)})
for ax, ch in zip(axes, ['v0', 'a']):
    ax.set_title(f'NRMSE {ch}: identificabilita vs dataset')
    ax.set_xlabel('epoch'); ax.set_ylabel('NRMSE'); ax.set_ylim(bottom=0)
    ax.legend(); ax.grid(alpha=0.3)
plt.tight_layout(); plt.savefig(f'{RESULTS_DIR}/S1b_nrmse_compare.png', dpi=120); plt.show()

display(Markdown('## Verdetto S1b — il dato ricco rende v0/a identificabili?'))
display(pd.DataFrame(summary))
print('Atteso: v0_nrmse e a_nrmse MOLTO piu bassi su S1b se freeflow ha funzionato.')'''


CELL_6_FINAL = """# Cell 6 -- Commit finale (traiettorie + confronto)
import subprocess
subprocess.run(['git', 'add', RESULTS_DIR], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'Loss_Study S1b: trajectories + NRMSE compare (excitation)'],
                   capture_output=True, text=True)
print(r.stdout[-300:] if r.returncode == 0 else r.stderr[-300:])
subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
print('S1b pushed.')"""


def main():
    cells = [
        make_cell('markdown', MARKDOWN_INTRO, 'cell-intro'),
        make_cell('code', CELL_1_BOOTSTRAP, 'cell-1'),
        make_cell('code', CELL_2_CONFIG, 'cell-2'),
        make_cell('code', CELL_3_TRAJ, 'cell-3'),
        make_cell('code', CELL_4_RUN, 'cell-4'),
        make_cell('code', CELL_5_G19_COMPARE, 'cell-5'),
        make_cell('code', CELL_6_FINAL, 'cell-6'),
    ]
    nb = make_notebook(cells)
    out = os.path.join(ROOT, 'Loss_Study_S1b.ipynb')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
