"""Loss_Study S1 — quale parametro IDM "pesa di piu" su loss_data, e perche.

Studio a 3 lenti (triangolazione) sui 2 champion 864p/232p:
  Lente A (gradiente)  -> gn_decoded_* dalla run di osservazione R0   (gia nel codice)
  Lente B (residuo)    -> val_*_nrmse  dalla run di osservazione R0   (patch additivo)
  Lente C (ablation)   -> Delta(min val_data) supervisionando 1 canale (run R1-R5)

12 run = 2 basi x {R0 osservazione (aux=0) + R1-R5 leave-one-in (lambda_aux=0.1)}.
lambda_aux=0.1 allineato a R30 (R30_A1..A4 isolati a 0.1).

Genera Loss_Study_S1.ipynb alla root. Pattern (ENV/push/3.10) clonato da R33.
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


MARKDOWN_INTRO = """# Loss_Study S1 — peso per-canale di loss_data (triangolazione)

## Domanda

`loss_data` e UN scalare (RMSE su accelerazione `a_pred` vs `a_gt`); i 5 parametri
IDM `[v0, T, s0, a, b]` entrano TUTTI insieme nell'equazione fisica. "Quale pesa di
piu" si misura in 3 modi distinti (lenti), la cui (dis)concordanza e il risultato:

| Lente | Misura | Sorgente |
|---|---|---|
| **A — gradiente** | `mean|d(loss)/d(param_i)|` (sensibilita) | `gn_decoded_*` (batch log, R0) |
| **B — residuo** | `RMSE(param_i, GT)/range_i` (errore normalizzato) | `val_*_nrmse` (epoch log, R0) |
| **C — ablation** | `Delta(min val_data)` supervisionando il canale i | run R1-R5 vs R0 |

## Matrice (12 run, ~5.5h)

2 basi champion x 6 run:
- **R0** osservazione (aux=0, = champion replica fresca) -> serve Lente A + B
- **R1-R5** leave-one-in: lambda_<canale>_aux = 0.1 (allineato R30) -> Lente C

Basi: **PEAK** (R33_C1, 864p, A4 warmup2) e **STABLE** (R32_B5, 232p, h16 + decay03 + warmup2).

## Anteprima Lente A (gia nota dai champion, da riconfermare fresca)

Ranking gradiente decodificato: `T > a > b > s0 > v0`, identico su 864p/232p.
v0 ~2 ordini sotto (loss quasi cieca a v0). Ipotesi Lente C: supervisionare **T**
aiuta molto (collo di bottiglia "vuole-ma-non-puo"), **v0** quasi nulla (irrilevante).

> Nota: Lente A misura il gradiente della loss TOTALE; `bc` tocca s0 -> s0 possibile
> lieve sovrastima. T/a/v0/b puliti. Refinement data-only differito.
"""


CELL_1_BOOTSTRAP = """# Cell 1 -- Bootstrap + GLOBALS + ENV check
import sys, os, subprocess
import importlib.util as _imu

RESULTS_DIR = 'results/Loss_Study/S1'
TRIANG_CSV  = f'{RESULTS_DIR}/_triangulation.csv'
BRANCH = 'Loss_Study'
LAMBDA_AUX = 0.1
CHANS = ['v0', 'T', 's0', 'a', 'b']
_TMP_MSG = '/tmp/ls1_msg.txt' if os.path.isdir('/tmp') else 'ls1_msg.txt'
os.makedirs(RESULTS_DIR, exist_ok=True)

for pkg in ['prodigyopt', 'pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)

for f in ['train.py', 'core/network.py']:
    assert os.path.isfile(f), f'missing {f}'

help_txt = subprocess.run([sys.executable, 'train.py', '--help'],
                          capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
for flag in ['--lambda_T_aux', '--lambda_v0_aux', '--lambda_s0_aux',
             '--lambda_a_aux', '--lambda_b_aux', '--restart_T0', '--cf_logit_tau_per_channel']:
    assert flag in help_txt, f'MISSING CLI: {flag}'

br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
assert br == BRANCH, f'branch={br} != {BRANCH}'
print(f'[LS1] ENV OK. branch={br}  RESULTS_DIR={RESULTS_DIR}  lambda_aux={LAMBDA_AUX}')"""


CELL_2_EXPERIMENTS = '''# Cell 2 -- EXPERIMENTS: 2 basi x (R0 obs + R1-R5 leave-one-in) = 12 run

# Base comune (champion C3 setup R33, mixed, 50 ep)
C3_BASE = {
    'optimizer': 'prodigy', 'lr': 0.5,
    'd0': 1e-6, 'd_coef': 1.0, 'growth_rate': 'inf',
    'epochs': 50, 'max_steps_per_epoch': 100,
    'seq_len': 50,
    'hidden_size': 32, 'rank': 8,
    'max_delay': 6, 'bit_shift': 3,
    'lambda_sr': 0.5, 'lambda_T_aux': 0.0,
    'lambda_v0_aux': 0.0, 'lambda_s0_aux': 0.0,
    'lambda_a_aux': 0.0, 'lambda_b_aux': 0.0,
    'scenario_mix': 'highway:0.4,urban:0.3,truck:0.2,mixed:0.1',
    'cut_in_ratio': 0.0,
    'cache_path': 'data/cache_1500_mixed_cut0.0_ou0.0.pt',
    'po2_enabled': 1,
    'init_bias_shift': 1,
    'tau_init': 1.0, 'tau_final': 1.0, 'tau_schedule': 'const',
    'tau_per_channel': '10.0,3.0,10.0,3.0,3.0',
    'max_epoch_explosion_streak': 2,
    'epoch_explosion_threshold': 10000.0,
    'scheduler': 'custom_restart',
    'T0': 5,
    'restart_T0': 12,
    'restart_decay': 1.0,
    'restart_lr_after': -1.0,
    'restart_warmup_epochs': 0,
    'restart_adaptive': 0,
}

# PEAK = R33_C1 (A4): C3 + warmup 2ep, 864p
PEAK_BASE = dict(C3_BASE)
PEAK_BASE.update({'restart_warmup_epochs': 2})

# STABLE = R33_C3 / R32_B5 (E1): h=16, rank=4, lambda_sr=5, decay 0.3, warmup 2ep, 232p
STABLE_BASE = dict(C3_BASE)
STABLE_BASE.update({'hidden_size': 16, 'rank': 4, 'lambda_sr': 5.0,
                    'restart_decay': 0.3, 'restart_warmup_epochs': 2})

BASES = [('PEAK', PEAK_BASE), ('STABLE', STABLE_BASE)]

# leave-one-in: (suffix run, override aux). R0 = osservazione (nessun aux).
AUX_RUNS = [
    ('R0_obs',   {}),
    ('R1_Taux',  {'lambda_T_aux':  LAMBDA_AUX}),
    ('R2_v0aux', {'lambda_v0_aux': LAMBDA_AUX}),
    ('R3_s0aux', {'lambda_s0_aux': LAMBDA_AUX}),
    ('R4_aaux',  {'lambda_a_aux':  LAMBDA_AUX}),
    ('R5_baux',  {'lambda_b_aux':  LAMBDA_AUX}),
]

EXPERIMENTS = []
for bname, bbase in BASES:
    for rname, ov in AUX_RUNS:
        e = dict(bbase)
        e.update(ov)
        e['tag']  = f'LS1_{bname}_{rname}'
        e['axis'] = bname
        e['desc'] = f'{bname} base + {rname} (aux={ov})'
        EXPERIMENTS.append(e)

print(f'LS1 EXPERIMENTS: {len(EXPERIMENTS)}')
tot = 0.0
for e in EXPERIMENTS:
    est = e['epochs'] * 0.55
    tot += est
    print(f"  {e['tag']:<20} ep={e['epochs']} h={e['hidden_size']} ~{est:.0f}min")
print(f"Totale stimato: {tot:.0f} min = {tot/60:.1f}h")'''


CELL_3_CACHE = """# Cell 3 -- Cache check (Python 3.10 compatible)
import os
cache = C3_BASE['cache_path']
if os.path.isfile(cache):
    sz_mb = os.path.getsize(cache) / 1e6
    print(f'  [OK] cache {cache}  ({sz_mb:.1f} MB)')
else:
    print(f'  [INFO] cache mancante: {cache} -- verra generata al primo run')"""


CELL_4_PREFLIGHT = '''# Cell 4 -- Pre-flight 1ep x 3step + verifica colonne Lente A/B presenti
import sys, subprocess, time, shutil, os
import pandas as pd
tag = f'_LS1_PREFLIGHT_{int(time.time())}'
cmd = [sys.executable, 'train.py', '--training_method', 'baseline',
    '--epochs', '1', '--max_steps_per_epoch', '3', '--batch_size', '8', '--val_batch_size', '32',
    '--seq_len', '50', '--cf_hidden_size', '32', '--cf_rank', '8', '--cf_max_delay', '6', '--cf_bit_shift', '3',
    '--cf_init_bias_shift', '1', '--cf_logit_tau_per_channel', '10.0,3.0,10.0,3.0,3.0',
    '--lambda_data', '1.0', '--lambda_phys', '0.1', '--lambda_ou', '0.05', '--lambda_bc', '1.0', '--lambda_sr', '0.5',
    '--scenario_mix', C3_BASE['scenario_mix'], '--cut_in_ratio', '0.0', '--noise_scale', '0.0',
    '--n_train', '80', '--n_val', '40',
    '--optimizer', 'prodigy', '--lr', '0.5', '--max_lr', '0.5',
    '--scheduler', 'custom_restart', '--restart_T0', '12',
    '--prodigy_betas', '0.9,0.99', '--prodigy_d_coef', '1.0', '--prodigy_d0', '1e-6',
    '--prodigy_weight_decay', '0.01', '--prodigy_use_bias_correction', '1', '--prodigy_safeguard_warmup', '1',
    '--prodigy_growth_rate', 'inf', '--max_inf_streak', '99999', '--early_stop_patience', '0',
    '--max_epoch_explosion_streak', '2', '--epoch_explosion_threshold', '10000.0', '--tag', tag]
r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
assert r.returncode == 0, f'preflight failed: {r.stderr[-500:]}'
elog = pd.read_csv(f'checkpoints/{tag}/training_log.csv')
blog = pd.read_csv(f'checkpoints/{tag}/training_batch_log.csv')
miss_b = [f'val_{c}_nrmse' for c in CHANS if f'val_{c}_nrmse' not in elog.columns]
miss_a = [f'gn_decoded_{c}' for c in CHANS if f'gn_decoded_{c}' not in blog.columns]
assert not miss_b, f'Lente B colonne mancanti: {miss_b}'
assert not miss_a, f'Lente A colonne mancanti: {miss_a}'
print('  [OK] preflight: Lente A (gn_decoded) + Lente B (val_nrmse) presenti')
if os.path.isdir(f'checkpoints/{tag}'):
    shutil.rmtree(f'checkpoints/{tag}', ignore_errors=True)'''


CELL_5_SWEEP = '''# Cell 5 -- SWEEP loop (R33 pattern) + git push per run
import subprocess, sys, time, os, shutil, glob, datetime
import pandas as pd

SKIP_IF_EXISTS = True

def _robust_rmtree(path, max_retries=3):
    for i in range(max_retries):
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
        '--tag', e['tag']]
    if e.get('tau_per_channel'):
        cli.extend(['--cf_logit_tau_per_channel', e['tau_per_channel']])
    return cli

def _dst_for(e):
    return f"{RESULTS_DIR}/{e['axis']}/{e['tag']}"

def _push_run(e):
    tag = e['tag']; src = f'checkpoints/{tag}'; dst = _dst_for(e)
    if not os.path.isdir(src):
        return False
    _robust_rmtree(dst)
    os.makedirs(f'{dst}/plots', exist_ok=True)
    for f in glob.glob(f'{src}/*.csv') + glob.glob(f'{src}/*.json'):
        shutil.copy2(f, dst)
    for f in glob.glob(f'{src}/plots/*.png'):
        shutil.copy2(f, f'{dst}/plots/')
    val_str = ''
    log_path = f'{dst}/training_log.csv'
    if os.path.isfile(log_path):
        try:
            edf = pd.read_csv(log_path)
            if len(edf) > 0:
                val_str = f'min val_data={edf.val_data.min():.4f} ({len(edf)}ep)'
        except Exception as ex:
            val_str = f'(log err: {ex})'
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    msg = f'results (Loss_Study S1): {tag} ({ts})\\n\\n{val_str}\\ndesc={e["desc"]}\\nBranch: {BRANCH}\\n'
    with open(_TMP_MSG, 'w', encoding='utf-8') as fp:
        fp.write(msg)
    try:
        subprocess.run(['git', 'add', dst], check=True, capture_output=True)
        r = subprocess.run(['git', 'commit', '-F', _TMP_MSG], capture_output=True, text=True)
        if r.returncode != 0:
            if 'nothing to commit' in r.stdout or 'nothing to commit' in r.stderr:
                return True
            print(f'   [push commit fail] {r.stderr[-300:]}'); return False
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

if 'EXPERIMENTS' not in dir():
    raise RuntimeError('EXPERIMENTS non definito (esegui Cell 2)')

run_results = []
t_start = time.time()
total = len(EXPERIMENTS)
for i, e in enumerate(EXPERIMENTS, 1):
    dst = _dst_for(e); dst_log = f'{dst}/training_log.csv'
    if SKIP_IF_EXISTS and os.path.isfile(dst_log):
        try:
            edf = pd.read_csv(dst_log)
            if len(edf) >= e['epochs'] * 0.8:
                print(f'\\n[{i}/{total}] [SKIP] {e["tag"]}: ep={len(edf)}/{e["epochs"]}')
                run_results.append({'tag': e['tag'], 'status': 'skipped'})
                continue
        except Exception:
            pass
    print(f'\\n{"="*78}\\n[{i}/{total}] {e["tag"]}\\n  {e["desc"]}\\n{"="*78}')
    t0 = time.time()
    r = subprocess.run(_build_cli(e), capture_output=False)
    el = time.time() - t0
    status = 'ok' if r.returncode == 0 else f'fail({r.returncode})'
    eta = ((time.time() - t_start) / max(i, 1)) * (total - i) / 60
    print(f'\\n[{i}/{total}] {e["tag"]} -> {status} ({el/60:.1f}min) ETA={eta:.0f}min')
    run_results.append({'tag': e['tag'], 'status': status, 'pushed': _push_run(e)})
print(f'\\n{"="*78}\\nSWEEP LS1 DONE in {(time.time()-t_start)/60:.0f}min')'''


CELL_6_LENS_A = '''# Cell 6 -- Lente A: ranking gradiente decodificato per-canale (run R0)
import os, pandas as pd
from IPython.display import display, Markdown

def lens_a(base):
    p = f'{RESULTS_DIR}/{base}/LS1_{base}_R0_obs/training_batch_log.csv'
    if not os.path.isfile(p):
        return None
    b = pd.read_csv(p)
    return {c: float(b[f'gn_decoded_{c}'].dropna().mean()) for c in CHANS}

lensA = {}
display(Markdown('## Lente A — gradiente decodificato medio per-canale (R0)'))
for base, _ in BASES:
    m = lens_a(base)
    if m is None:
        print(f'  [{base}] R0 mancante'); continue
    lensA[base] = m
    rank = sorted(CHANS, key=lambda c: m[c], reverse=True)
    print(f'  [{base}] ' + '  '.join(f'{c}={m[c]:.2e}' for c in CHANS))
    print(f'         ranking: ' + ' > '.join(rank))'''


CELL_7_LENS_B = '''# Cell 7 -- Lente B: NRMSE per-canale al best epoch (run R0)
import os, pandas as pd
from IPython.display import display, Markdown

def lens_b(base):
    p = f'{RESULTS_DIR}/{base}/LS1_{base}_R0_obs/training_log.csv'
    if not os.path.isfile(p):
        return None
    e = pd.read_csv(p)
    i = int(e['val_data'].idxmin())
    return {c: float(e[f'val_{c}_nrmse'].iloc[i]) for c in CHANS}

lensB = {}
display(Markdown('## Lente B — NRMSE per-canale (residuo normalizzato, R0 @ best val_data)'))
for base, _ in BASES:
    m = lens_b(base)
    if m is None:
        print(f'  [{base}] R0 mancante'); continue
    lensB[base] = m
    rank = sorted(CHANS, key=lambda c: m[c], reverse=True)
    print(f'  [{base}] ' + '  '.join(f'{c}={m[c]:.3f}' for c in CHANS))
    print(f'         peggiore->migliore: ' + ' > '.join(rank))'''


CELL_8_LENS_C = '''# Cell 8 -- Lente C: ablation Delta(min val_data) supervisionando 1 canale
import os, pandas as pd
from IPython.display import display, Markdown

AUX_TAG = {'T': 'R1_Taux', 'v0': 'R2_v0aux', 's0': 'R3_s0aux', 'a': 'R4_aaux', 'b': 'R5_baux'}

def _min_vd(base, run_suffix):
    p = f'{RESULTS_DIR}/{base}/LS1_{base}_{run_suffix}/training_log.csv'
    if not os.path.isfile(p):
        return float('nan')
    return float(pd.read_csv(p)['val_data'].min())

lensC = {}
display(Markdown('## Lente C — Delta(min val_data) = baseline R0 - run con aux (positivo = aiuta)'))
for base, _ in BASES:
    vd0 = _min_vd(base, 'R0_obs')
    m = {c: vd0 - _min_vd(base, AUX_TAG[c]) for c in CHANS}
    lensC[base] = m
    rank = sorted(CHANS, key=lambda c: (m[c] if m[c] == m[c] else -9), reverse=True)
    print(f'  [{base}] R0 min val_data={vd0:.4f}')
    print(f'         ' + '  '.join(f'{c}:{m[c]:+.4f}' for c in CHANS))
    print(f'         piu-utile->meno: ' + ' > '.join(rank))'''


CELL_9_TRIANG = '''# Cell 9 -- Triangolazione A/B/C + salvataggio + plot
import os, pandas as pd, numpy as np
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

rows = []
for base, _ in BASES:
    for c in CHANS:
        rows.append({
            'base': base, 'canale': c,
            'A_grad':   lensA.get(base, {}).get(c, float('nan')),
            'B_nrmse':  lensB.get(base, {}).get(c, float('nan')),
            'C_delta':  lensC.get(base, {}).get(c, float('nan')),
        })
tri = pd.DataFrame(rows)
# rank per base (1 = piu importante secondo ciascuna lente)
for base, _ in BASES:
    mask = tri.base == base
    tri.loc[mask, 'rankA'] = tri.loc[mask, 'A_grad'].rank(ascending=False)
    tri.loc[mask, 'rankB'] = tri.loc[mask, 'B_nrmse'].rank(ascending=False)
    tri.loc[mask, 'rankC'] = tri.loc[mask, 'C_delta'].rank(ascending=False)
tri.to_csv(TRIANG_CSV, index=False)
display(Markdown('## Triangolazione A/B/C per-canale'))
display(tri.round(4))

# Plot: per base, 3 pannelli (A grad log, B nrmse, C delta)
fig, axes = plt.subplots(len(BASES), 3, figsize=(15, 4 * len(BASES)))
if len(BASES) == 1:
    axes = axes.reshape(1, 3)
for r, (base, _) in enumerate(BASES):
    sub = tri[tri.base == base].set_index('canale').reindex(CHANS)
    axes[r, 0].bar(CHANS, sub['A_grad']); axes[r, 0].set_yscale('log')
    axes[r, 0].set_title(f'{base} | Lente A: gradiente (log)')
    axes[r, 1].bar(CHANS, sub['B_nrmse'], color='tab:orange')
    axes[r, 1].set_title(f'{base} | Lente B: NRMSE')
    colors = ['tab:green' if v >= 0 else 'tab:red' for v in sub['C_delta'].fillna(0)]
    axes[r, 2].bar(CHANS, sub['C_delta'], color=colors)
    axes[r, 2].axhline(0, color='k', lw=0.6)
    axes[r, 2].set_title(f'{base} | Lente C: Delta val_data (aux)')
    for a in axes[r]:
        a.grid(alpha=0.3, axis='y')
plt.tight_layout()
plt.savefig(f'{RESULTS_DIR}/LS1_triangulation.png', dpi=120)
plt.show()
print(f'Saved {TRIANG_CSV} + {RESULTS_DIR}/LS1_triangulation.png')'''


CELL_10_FINAL = """# Cell 10 -- Final commit + push (triangolazione)
import subprocess
subprocess.run(['git', 'add', RESULTS_DIR], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'Loss_Study S1: triangulation A/B/C + plot'],
                   capture_output=True, text=True)
print(r.stdout[-300:] if r.returncode == 0 else r.stderr[-300:])
subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
print('LS1 triangulation pushed.')"""


def main():
    cells = [
        make_cell('markdown', MARKDOWN_INTRO, 'cell-intro'),
        make_cell('code', CELL_1_BOOTSTRAP, 'cell-1'),
        make_cell('code', CELL_2_EXPERIMENTS, 'cell-2'),
        make_cell('code', CELL_3_CACHE, 'cell-3'),
        make_cell('code', CELL_4_PREFLIGHT, 'cell-4'),
        make_cell('code', CELL_5_SWEEP, 'cell-5'),
        make_cell('code', CELL_6_LENS_A, 'cell-6'),
        make_cell('code', CELL_7_LENS_B, 'cell-7'),
        make_cell('code', CELL_8_LENS_C, 'cell-8'),
        make_cell('code', CELL_9_TRIANG, 'cell-9'),
        make_cell('code', CELL_10_FINAL, 'cell-10'),
    ]
    nb = make_notebook(cells)
    out = os.path.join(ROOT, 'Loss_Study_S1.ipynb')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
