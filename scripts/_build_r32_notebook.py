"""R32: Restart Mechanisms — 5 opzioni × 2 baseline = 10 esperimenti.

Goal: trovare il meccanismo di restart migliore per evitare l'esplosione post-peak
osservata in R31_A3 (lr salta 90× istantaneo).

5 opzioni:
  1 — decaying restart (lr × 0.3 ad ogni ciclo)
  2 — 2-tier lr (first=0.5, rest=0.15)
  3 — adaptive trigger (restart su T_intra↓ × 2 epoche)
  4 — soft ramp warmup (2 ep ramp post-restart)
  1+4 — decay + warmup combo

2 baseline (champions distinti):
  C3 base = init+per-ch τ, h=32, λ_sr=0.5, 50 ep
  E1 base = init+per-ch τ, h=16, λ_sr=5.0, 50 ep
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_cell(ctype, src, cid):
    if isinstance(src, list): src = '\n'.join(src)
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


MARKDOWN_INTRO = """# R32 Restart Mechanisms — 5 opzioni × 2 baseline

## Contesto

R31_A3 ha mostrato che warm restart standard (T0=15, lr → 0.5 istantaneo) produce:
- Peak T_intra=0.060 al PRIMO restart (ep15)
- Esplosione al SECONDO restart (ep30) → guard abort

Lr salta 90× ad ogni restart. R32 prova 5 meccanismi più "soft":

| Opt | Meccanismo | Effetto atteso |
|---|---|---|
| 1 | Decaying restart (lr × 0.3 per ciclo) | Restart progressivamente più gentili |
| 2 | 2-tier lr (first=0.5, rest=0.15) | Solo il primo restart "forte" |
| 3 | Adaptive trigger (T_intra↓ × 2 ep) | Restart solo quando serve |
| 4 | Soft ramp warmup (2 ep) | Lr cresce gradualmente post-restart |
| 1+4 | Decay + warmup combo | Doppia protezione |

## 2 baseline distinti

| Base | h | λ_sr | Note |
|---|---:|---:|---|
| **C3** (R29v2_C3 / R31_A2) | 32 | 0.5 | Standard champion |
| **E1** (R31_E1_STABLE) | 16 | 5.0 | Capacity ridotta + spike forte |

A3 NON ha base distinta (= C3 + standard restart) → testarci 5 opzioni = REDUNDANTE.
"""


CELL_1_BOOTSTRAP = """# Cell 1 -- Bootstrap + GLOBALS + ENV check
import sys, os, subprocess, re
import importlib.util as _imu

RESULTS_DIR = 'results/Prodigy_Study/R32_RestartMechanisms'
AGGREGATE_CSV = f'{RESULTS_DIR}/_aggregate.csv'
BRANCH = 'Prodigy_Deep_Study'
_TMP_MSG = '/tmp/r32_msg.txt' if os.path.isdir('/tmp') else 'r32_msg.txt'
os.makedirs(RESULTS_DIR, exist_ok=True)

for pkg in ['prodigyopt', 'pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)

for f in ['train.py', 'core/network.py']:
    assert os.path.isfile(f)

# Verifica R32 CLI presente
help_txt = subprocess.run([sys.executable, 'train.py', '--help'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
for flag in ['--restart_T0', '--restart_decay', '--restart_lr_after',
             '--restart_warmup_epochs', '--restart_adaptive']:
    assert flag in help_txt, f'MISSING CLI: {flag}'
# Verifica scheduler choice custom_restart
assert 'custom_restart' in help_txt, 'scheduler choice custom_restart MISSING'

br = subprocess.run(['git','branch','--show-current'], capture_output=True, text=True).stdout.strip()
assert br == BRANCH
print(f'[R32] ENV OK. branch={br}')
print(f'  RESULTS_DIR={RESULTS_DIR}')"""


CELL_2_EXPERIMENTS = '''# Cell 2 -- R32 EXPERIMENTS: 5 opzioni × 2 baseline (C3, E1) = 10 run

# Base config C3 (R29v2_C3 + 50 ep)
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
    # Champion R29 fixes
    'init_bias_shift': 1,
    'tau_init': 1.0, 'tau_final': 1.0, 'tau_schedule': 'const',
    'tau_per_channel': '10.0,3.0,10.0,3.0,3.0',
    # R30 guard
    'max_epoch_explosion_streak': 2,
    'epoch_explosion_threshold': 100.0,
    # R32 scheduler (default custom_restart)
    'scheduler': 'custom_restart',
    'T0': 5,  # legacy field ignored by custom_restart
    'restart_T0': 15,        # ogni 15 ep
    'restart_decay': 1.0,    # default: no decay (Opt 0)
    'restart_lr_after': -1.0,  # default: usa decay
    'restart_warmup_epochs': 0,  # default: no warmup
    'restart_adaptive': 0,   # default: no adaptive
}

# Base config E1 (R31_E1 + restart mechanisms)
E1_BASE = dict(C3_BASE)
E1_BASE.update({
    'hidden_size': 16, 'rank': 4,
    'lambda_sr': 5.0,
})

def _exp(tag, desc, base, axis, **overrides):
    e = dict(base)
    e.update({'tag': tag, 'desc': desc, 'axis': axis})
    e.update(overrides)
    return e

EXPERIMENTS = [
    # === Asse A — C3 base (h=32, λ_sr=0.5) ===
    _exp('R32_A1_C3_decay03', 'Opzione 1 — decay=0.3 (geometric)',
         C3_BASE, 'A_C3_base', restart_decay=0.3),
    _exp('R32_A2_C3_2tier_015', 'Opzione 2 — first lr=0.5, restart lr=0.15',
         C3_BASE, 'A_C3_base', restart_lr_after=0.15),
    _exp('R32_A3_C3_adaptive', 'Opzione 3 — adaptive trigger (T_intra↓×2)',
         C3_BASE, 'A_C3_base', restart_adaptive=1),
    _exp('R32_A4_C3_warmup2ep', 'Opzione 4 — warmup 2 ep + restart standard',
         C3_BASE, 'A_C3_base', restart_warmup_epochs=2),
    _exp('R32_A5_C3_decay03_warmup2', 'Opzione 1+4 — decay 0.3 + warmup 2 ep',
         C3_BASE, 'A_C3_base', restart_decay=0.3, restart_warmup_epochs=2),

    # === Asse B — E1 base (h=16, λ_sr=5.0) ===
    _exp('R32_B1_E1_decay03', 'Opzione 1 — decay=0.3 su E1',
         E1_BASE, 'B_E1_base', restart_decay=0.3),
    _exp('R32_B2_E1_2tier_015', 'Opzione 2 — 2-tier su E1',
         E1_BASE, 'B_E1_base', restart_lr_after=0.15),
    _exp('R32_B3_E1_adaptive', 'Opzione 3 — adaptive su E1',
         E1_BASE, 'B_E1_base', restart_adaptive=1),
    _exp('R32_B4_E1_warmup2ep', 'Opzione 4 — warmup 2 ep su E1',
         E1_BASE, 'B_E1_base', restart_warmup_epochs=2),
    _exp('R32_B5_E1_decay03_warmup2', 'Opzione 1+4 — combo su E1',
         E1_BASE, 'B_E1_base', restart_decay=0.3, restart_warmup_epochs=2),
]

print(f'R32 EXPERIMENTS: {len(EXPERIMENTS)}')
total_min = 0
for e in EXPERIMENTS:
    est = e['epochs'] * 0.55  # ~0.55 min/ep su Azure CPU
    total_min += est
    parts = [f"T0={e['restart_T0']}"]
    if e['restart_decay'] != 1.0: parts.append(f"decay={e['restart_decay']}")
    if e['restart_lr_after'] > 0: parts.append(f"lr_after={e['restart_lr_after']}")
    if e['restart_warmup_epochs'] > 0: parts.append(f"warmup={e['restart_warmup_epochs']}ep")
    if e['restart_adaptive']: parts.append("adaptive")
    parts.append(f"h={e['hidden_size']}")
    parts.append(f"λsr={e['lambda_sr']}")
    print(f"  [{e['axis']:<10}] {e['tag']:<32} ep={e['epochs']:<2} ~{est:>4.0f}min [{', '.join(parts)}]")
print(f"\\nTotale stimato: {total_min:.0f} min = {total_min/60:.1f}h (con guard abort: ~50-70%)")'''


CELL_3_CACHE = """# Cell 3 -- Cache check
import os
cache = C3_BASE['cache_path']
print(f'Cache {cache}: {"OK ("+str(os.path.getsize(cache)/1e6)+" MB)" if os.path.isfile(cache) else "VERRA\\' GENERATA"}')"""


CELL_4_PREFLIGHT = """# Cell 4 -- Pre-flight: C3 base + Opt1 (decay 0.3) 1ep×3step
import sys, subprocess, time, shutil, os
tag = f'_R32_PREFLIGHT_{int(time.time())}'
cmd = [sys.executable,'train.py','--training_method','baseline',
    '--epochs','1','--max_steps_per_epoch','3','--batch_size','8','--val_batch_size','32',
    '--seq_len','50','--cf_hidden_size','32','--cf_rank','8','--cf_max_delay','6','--cf_bit_shift','3',
    '--cf_init_bias_shift','1','--cf_logit_tau_per_channel','10.0,3.0,10.0,3.0,3.0',
    '--lambda_data','1.0','--lambda_phys','0.1','--lambda_ou','0.05','--lambda_bc','1.0','--lambda_sr','0.5','--lambda_T_aux','0.0',
    '--scenario_mix',C3_BASE['scenario_mix'],'--cut_in_ratio','0.0','--noise_scale','0.0',
    '--n_train','80','--n_val','40',
    '--optimizer','prodigy','--lr','0.5','--max_lr','0.5',
    '--scheduler','custom_restart','--restart_T0','15','--restart_decay','0.3',
    '--prodigy_betas','0.9,0.99','--prodigy_d_coef','1.0','--prodigy_d0','1e-6',
    '--prodigy_weight_decay','0.01','--prodigy_use_bias_correction','1','--prodigy_safeguard_warmup','1',
    '--prodigy_growth_rate','inf','--max_inf_streak','99999','--early_stop_patience','0',
    '--max_epoch_explosion_streak','2','--epoch_explosion_threshold','100.0','--tag',tag]
r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
assert r.returncode == 0, f'preflight failed: {r.stderr[-500:]}'
assert '[R32 Custom Restart]' in r.stdout, 'R32 scheduler init message missing'
assert '[R32 CustomRestart] ep1' in r.stdout, 'R32 per-epoch lr update missing'
print('  [OK] R32 custom_restart smoke OK')
def _rmt(p):
    if os.path.isdir(p): shutil.rmtree(p, ignore_errors=True)
_rmt(f'checkpoints/{tag}')"""


CELL_5_SWEEP = """# Cell 5 -- SWEEP loop (R29_v2 / R31 pattern)
import subprocess, sys, time, os, shutil, glob, datetime
import pandas as pd

SKIP_IF_EXISTS = True

def _robust_rmtree(path, max_retries=3):
    for i in range(max_retries):
        if not os.path.isdir(path): return True
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.isdir(path): return True
        time.sleep(0.5*(i+1))
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
        '--lambda_data','1.0','--lambda_phys','0.1','--lambda_ou','0.05',
        '--lambda_bc','1.0','--lambda_sr', str(e['lambda_sr']),
        '--lambda_T_aux', str(e['lambda_T_aux']),
        '--lambda_v0_aux', str(e['lambda_v0_aux']),
        '--lambda_s0_aux', str(e['lambda_s0_aux']),
        '--lambda_a_aux', str(e['lambda_a_aux']),
        '--lambda_b_aux', str(e['lambda_b_aux']),
        '--scenario_mix', e['scenario_mix'],
        '--cut_in_ratio', str(e['cut_in_ratio']),
        '--noise_scale','0.0','--po2_enabled', str(e['po2_enabled']),
        '--n_train','1500','--n_val','300',
        '--max_inf_streak','99999','--early_stop_patience','0',
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
        '--prodigy_betas','0.9,0.99',
        '--prodigy_d_coef', str(e['d_coef']),
        '--prodigy_d0', str(e['d0']),
        '--prodigy_weight_decay','0.01',
        '--prodigy_use_bias_correction','1',
        '--prodigy_safeguard_warmup','1',
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
    if not os.path.isdir(src): return False
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
                bi = int(edf.val_total.idxmin())
                tc = edf.get('val_T_tracking_corr', pd.Series([float('nan')])).iloc[bi]
                tci = edf.get('val_T_intra_corr', pd.Series([float('nan')])).iloc[bi]
                tp_val = edf['val_T_intra_corr'].max() if 'val_T_intra_corr' in edf.columns else float('nan')
                tp_ep = int(edf['val_T_intra_corr'].idxmax())+1 if 'val_T_intra_corr' in edf.columns else bi+1
                val_str = (f'best val={edf.val_total.min():.4f} T_corr={tc:.3f} '
                           f'T_intra={tci:.3f} T_intra_PEAK={tp_val:.3f}@ep{tp_ep} '
                           f'(E{bi+1}/{len(edf)})')
        except Exception as ex: val_str = f'(log err: {ex})'
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    msg = f'results (R32 RestartMechanisms): {tag} ({ts})\\n\\n{val_str}\\ndesc={e["desc"]}\\nAxis: {e["axis"]}\\nBranch: {BRANCH}\\n'
    with open(_TMP_MSG, 'w', encoding='utf-8') as fp: fp.write(msg)
    try:
        subprocess.run(['git','add',dst], check=True, capture_output=True)
        r = subprocess.run(['git','commit','-F',_TMP_MSG], capture_output=True, text=True)
        if r.returncode != 0:
            if 'nothing to commit' in r.stdout or 'nothing to commit' in r.stderr: return True
            print(f'   [push commit fail] {r.stderr[-300:]}'); return False
        subprocess.run(['git','pull','--no-rebase','--no-edit','origin',BRANCH], capture_output=True, text=True)
        r2 = subprocess.run(['git','push','origin',BRANCH], capture_output=True, text=True)
        if r2.returncode != 0:
            print(f'   [push fail] {r2.stderr[-300:]}'); return False
        print(f'   [push OK]'); return True
    finally:
        try: os.remove(_TMP_MSG)
        except: pass

if 'EXPERIMENTS' not in dir(): raise RuntimeError('EXPERIMENTS non definito')

run_results = []
t_start = time.time()
total = len(EXPERIMENTS)
for i, e in enumerate(EXPERIMENTS, 1):
    dst = _dst_for(e); dst_log = f'{dst}/training_log.csv'
    if SKIP_IF_EXISTS and os.path.isfile(dst_log):
        try:
            edf = pd.read_csv(dst_log)
            if len(edf) >= e['epochs']*0.8:
                print(f'\\n[{i}/{total}] [SKIP] {e["tag"]}: ep={len(edf)}/{e["epochs"]} val={edf.val_total.min():.4f}')
                run_results.append({'tag':e['tag'],'axis':e['axis'],'status':'skipped'})
                continue
        except: pass
    print(f'\\n{"="*78}\\n[{i}/{total}] {e["tag"]} [axis={e["axis"]}]\\n  {e["desc"]}\\n{"="*78}')
    t0 = time.time()
    r = subprocess.run(_build_cli(e), capture_output=False)
    el = time.time()-t0
    status = 'ok' if r.returncode == 0 else f'fail({r.returncode})'
    done = sum(1 for x in run_results if x['status']!='skipped')+1
    eta = ((time.time()-t_start)/max(done,1))*(total-i)/60
    print(f'\\n[{i}/{total}] {e["tag"]} -> {status} ({el/60:.1f}min) ETA={eta:.0f}min')
    run_results.append({'tag':e['tag'],'axis':e['axis'],'status':status,'pushed':_push_run(e)})
print(f'\\n{"="*78}\\nSWEEP R32 DONE in {(time.time()-t_start)/60:.0f}min')"""


CELL_6_AGGREGATOR = """# Cell 6 -- Aggregator (T_intra peak + lr trajectory + gn analysis)
import os, json, math, pandas as pd, numpy as np
from IPython.display import display, Markdown

rows = []
for root, _, files in os.walk(RESULTS_DIR):
    if 'training_log.csv' not in files or 'config_snapshot.json' not in files: continue
    cfg = json.load(open(os.path.join(root, 'config_snapshot.json')))
    edf = pd.read_csv(os.path.join(root, 'training_log.csv'))
    if len(edf) == 0 or 'val_T_intra_corr' not in edf.columns: continue
    ip = edf['val_T_intra_corr'].idxmax()
    iv = edf['val_total'].idxmin()
    bdf_path = os.path.join(root, 'training_batch_log.csv')
    sr = float('nan'); gn = float('nan')
    try:
        bdf = pd.read_csv(bdf_path)
        sr = bdf['spike_rate'].mean()
        gns = bdf['gn_total_preclip']; gns_f = gns[gns.apply(math.isfinite)]
        gn = gns_f.max() if len(gns_f)>0 else float('nan')
    except: pass
    rows.append({
        'tag': cfg['tag'],
        'axis': os.path.basename(os.path.dirname(root)),
        'n_ep': len(edf), 'planned_ep': cfg.get('epochs'),
        'Tp_ep': ip+1, 'Tp': float(edf['val_T_intra_corr'].iloc[ip]),
        'val_data@Tp': float(edf['val_data'].iloc[ip]),
        'T_track@Tp': float(edf.get('val_T_tracking_corr', pd.Series([np.nan])).iloc[ip]),
        'vb_ep': iv+1, 'val_data@vb': float(edf['val_data'].iloc[iv]),
        'spike_train': float(sr), 'gn_max': float(gn),
        'hidden': cfg.get('cf_hidden_size'),
        'lambda_sr': cfg.get('lambda_sr', 0.5),
        'restart_T0': cfg.get('restart_T0', 15),
        'restart_decay': cfg.get('restart_decay', 1.0),
        'restart_lr_after': cfg.get('restart_lr_after', -1),
        'restart_warmup': cfg.get('restart_warmup_epochs', 0),
        'restart_adaptive': cfg.get('restart_adaptive', 0),
    })
df = pd.DataFrame(rows).sort_values('Tp', ascending=False)
df['hit_T'] = df['Tp'] > 0.025
df['hit_V'] = df['val_data@Tp'] < 0.185
df['hit_S'] = (df['spike_train'] >= 0.10) & (df['spike_train'] <= 0.25)
df['hit_C'] = df['gn_max'] < 100
df['n_hits'] = df[['hit_T','hit_V','hit_S','hit_C']].sum(axis=1)
df.to_csv(AGGREGATE_CSV, index=False)
print(f'R32 runs: {len(df)}, saved {AGGREGATE_CSV}')
display(Markdown('## R32 sintesi (T_intra peak desc)'))
display(df[['tag','axis','n_ep','planned_ep','Tp_ep','Tp','val_data@Tp',
            'spike_train','gn_max','n_hits']].round(4))"""


CELL_7_PLOTS = """# Cell 7 -- Plots: lr trajectory + T_intra evolution per opzione
import os, pandas as pd, numpy as np
import matplotlib.pyplot as plt

if 'df' not in dir(): df = pd.read_csv(AGGREGATE_CSV)

fig, axes = plt.subplots(2, 2, figsize=(16, 10))

# Plot 1: lr trajectory per run (vediamo come ogni opzione modula lr)
ax = axes[0,0]
for _, r in df.iterrows():
    log = f'{RESULTS_DIR}/{r["axis"]}/{r["tag"]}/training_log.csv'
    if not os.path.isfile(log): continue
    edf = pd.read_csv(log)
    if 'lr' not in edf.columns: continue
    label = r['tag'].replace('R32_','')[:24]
    ax.plot(edf['epoch'], edf['lr'], marker='.', alpha=0.7, label=label)
ax.set_xlabel('epoch'); ax.set_ylabel('lr')
ax.set_title('LR trajectory per opzione')
ax.legend(fontsize=6, loc='upper right'); ax.grid(alpha=0.3)
ax.set_yscale('log')

# Plot 2: T_intra evolution
ax = axes[0,1]
for _, r in df.iterrows():
    log = f'{RESULTS_DIR}/{r["axis"]}/{r["tag"]}/training_log.csv'
    if not os.path.isfile(log): continue
    edf = pd.read_csv(log)
    if 'val_T_intra_corr' not in edf.columns: continue
    label = r['tag'].replace('R32_','')[:24]
    ax.plot(edf['epoch'], edf['val_T_intra_corr'], marker='.', alpha=0.7, label=label)
ax.axhline(0.060, color='blue', linestyle=':', alpha=0.5, label='R31_A3 record')
ax.axhline(0.041, color='green', linestyle=':', alpha=0.5, label='R29v2_C3 CLEAN')
ax.set_xlabel('epoch'); ax.set_ylabel('val_T_intra_corr')
ax.set_title('T_intra evolution per opzione')
ax.legend(fontsize=6, loc='upper left'); ax.grid(alpha=0.3)

# Plot 3: Pareto T_intra vs val_data
ax = axes[1,0]
for h in range(5):
    sub = df[df.n_hits == h]
    ax.scatter(sub['val_data@Tp'], sub['Tp'], s=80+h*40, alpha=0.7, label=f'{h}/4 hit')
ax.axvline(0.185, color='gray', linestyle=':', alpha=0.5)
ax.axhline(0.025, color='gray', linestyle=':', alpha=0.5)
ax.axhline(0.060, color='blue', linestyle=':', alpha=0.5, label='R31_A3')
for _, r in df.iterrows():
    ax.annotate(r['tag'].replace('R32_','')[:14], (r['val_data@Tp'], r['Tp']), fontsize=7, alpha=0.7)
ax.set_xlabel('val_data@Tp'); ax.set_ylabel('T_intra_PEAK')
ax.set_title('Pareto')
ax.legend(fontsize=8); ax.grid(alpha=0.3)

# Plot 4: gn distribution
ax = axes[1,1]
import math
df_sorted = df.sort_values('gn_max')
colors = ['green' if g<100 else ('orange' if g<1e6 else 'red') for g in df_sorted['gn_max']]
ax.barh(range(len(df_sorted)),
        [math.log10(g) if g>0 and math.isfinite(g) else 0 for g in df_sorted['gn_max']],
        color=colors, alpha=0.7)
ax.set_yticks(range(len(df_sorted)))
ax.set_yticklabels([t.replace('R32_','')[:24] for t in df_sorted['tag']], fontsize=8)
ax.axvline(2, color='black', linestyle=':', alpha=0.5, label='log10(100) soglia')
ax.set_xlabel('log10(gn_max)'); ax.set_title('Gradient stability')
ax.legend(fontsize=8); ax.grid(alpha=0.3, axis='x')

plt.tight_layout()
out_png = f'{RESULTS_DIR}/R32_diagnostic_plots.png'
plt.savefig(out_png, dpi=110); plt.show()
print(f'Salvato: {out_png}')"""


CELL_8_SUMMARY = """# Cell 8 -- Verdetto + push aggregator
import os, subprocess, tempfile, pandas as pd
from IPython.display import display, Markdown

if 'df' not in dir(): df = pd.read_csv(AGGREGATE_CSV)

display(Markdown('## R32 Verdetto'))
n4 = (df.n_hits == 4).sum()
best_pk = df.sort_values('Tp', ascending=False).iloc[0]
clean = df[df.gn_max < 100]
best_clean = clean.sort_values('Tp', ascending=False).iloc[0] if len(clean) > 0 else None

print(f'Tot run R32: {len(df)}')
print(f'Champions 4/4 obj: {n4}')
print(f'\\nBest T_intra peak (any): {best_pk["tag"]} = {best_pk["Tp"]:.4f} '
      f'val_data={best_pk["val_data@Tp"]:.4f} gn={best_pk["gn_max"]:.2e}')
if best_clean is not None:
    print(f'Best T_intra peak CLEAN: {best_clean["tag"]} = {best_clean["Tp"]:.4f} '
          f'val_data={best_clean["val_data@Tp"]:.4f} gn={best_clean["gn_max"]:.2f}')

print()
print(f'Riferimenti pregress:')
print(f'  R31_A3 (standard restart, peak): T_intra=0.060, gn=4280')
print(f'  R29v2_C3 (no restart, CLEAN):    T_intra=0.041, gn=40')
print(f'  R31_E1 (no restart on E1):       T_intra=0.038, gn=1.3e+06')

if best_pk['Tp'] > 0.060:
    display(Markdown(f'### ✅ R32 SUPERA il record R31_A3 (0.060). New peak={best_pk["Tp"]:.4f}'))
elif best_clean is not None and best_clean['Tp'] > 0.041:
    display(Markdown(f'### ✅ R32 SUPERA il CLEAN record (0.041). New clean={best_clean["Tp"]:.4f}'))
else:
    display(Markdown(f'### ⚠ R32 non supera i record. Restart mechanism non sblocca.'))

subprocess.run(['git','add', AGGREGATE_CSV, f'{RESULTS_DIR}/R32_diagnostic_plots.png'], check=False)
msg = f'R32 RestartMechanisms: {len(df)} run, best T_intra={best_pk["Tp"]:.4f}'
with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt', encoding='utf-8') as fp:
    fp.write(msg); mp = fp.name
r = subprocess.run(['git','diff','--cached','--name-only'], capture_output=True, text=True)
if r.stdout.strip():
    subprocess.run(['git','commit','-F',mp], check=True)
    subprocess.run(['git','pull','--no-rebase','--no-edit','origin',BRANCH], check=True)
    subprocess.run(['git','push','origin',BRANCH], check=True)
    print('[OK] R32 aggregator pushato')
else:
    print('[SKIP] no changes')
try: os.unlink(mp)
except: pass"""


def main():
    cells = [
        make_cell('markdown', MARKDOWN_INTRO, 'cell-0'),
        make_cell('code', CELL_1_BOOTSTRAP, 'cell-1'),
        make_cell('code', CELL_2_EXPERIMENTS, 'cell-2'),
        make_cell('code', CELL_3_CACHE, 'cell-3'),
        make_cell('code', CELL_4_PREFLIGHT, 'cell-4'),
        make_cell('code', CELL_5_SWEEP, 'cell-5'),
        make_cell('code', CELL_6_AGGREGATOR, 'cell-6'),
        make_cell('code', CELL_7_PLOTS, 'cell-7'),
        make_cell('code', CELL_8_SUMMARY, 'cell-8'),
    ]
    nb = make_notebook(cells)
    out = os.path.join(ROOT, 'Prodigy_Restart_Mechanisms_R32.ipynb')
    with open(out, 'w', encoding='utf-8') as fp:
        json.dump(nb, fp, indent=1, ensure_ascii=False)
    print(f'Created: Prodigy_Restart_Mechanisms_R32.ipynb')


if __name__ == '__main__':
    main()
