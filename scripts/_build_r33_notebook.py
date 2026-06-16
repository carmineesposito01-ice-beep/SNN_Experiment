"""R33: Closure study — replica dei 3 R32 champion con 2 correzioni:
  (a) epoch_explosion_threshold 100 -> 10000 (no abort prematuro su spike isolati)
  (b) restart_T0 15 -> 12 (4 cicli pieni in 50 ep, no ciclo monco)

Goal: verificare che A4 e A1 completino vicino a 50/50 ep e/o migliorino il peak.
Probabilmente non cambieranno molto i numeri, ma e' il modo rigoroso di chiudere
lo studio prima del merge su main.

5 esperimenti (~2.3h compute):
  R33_C1_A4_T12_fix    -- A4 (warmup 2) con T0=12 + threshold=10000
  R33_C2_A1_T12_fix    -- A1 (decay 0.3) con T0=12 + threshold=10000
  R33_C3_B5_T12_fix    -- B5 (E1 + decay + warmup) con T0=12 + threshold=10000
  R33_C4_A4_T15_fix    -- A4 con T0=15 (stesso del R32) + threshold=10000 (isola effetto soglia)
  R33_C5_A3v2_adaptive_fix -- A3 adaptive con threshold=10000 (vedi se peak Tp=0.065 era reale)
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


MARKDOWN_INTRO = """# R33 Closure — Champion replica con correzioni guard + T0

## Contesto

R32 ha identificato 3 champion (A4 WARMUP_PEAK, A1 DECAY_BALANCED, B5 STABLE), ma con
2 problemi nel setup:

1. **Explosion guard troppo sensibile**: `epoch_explosion_threshold=100` triggera abort
   su singoli spike isolati. Tutti i 7 abort R32 erano su 2 epoche realmente consecutive
   sopra soglia, ma con soglia cosi' bassa anche run "recuperabili" venivano interrotti.
2. **Restart_T0=15 sub-ottimale per 50 ep**: 3 cicli pieni + 1 ciclo monco di 5 ep
   (restart sprecato). T0=12 da' 4 cicli che chiudono a ep48.

R33 ripete i 3 champion con le correzioni + 2 controlli per isolare gli effetti.

## 5 esperimenti

| Tag | Champion replica | T0 | threshold | Goal |
|---|---|---:|---:|---|
| R33_C1_A4_T12_fix | A4 warmup 2ep | 12 | 10000 | Vedere se completiamo >45/50 ep |
| R33_C2_A1_T12_fix | A1 decay 0.3 | 12 | 10000 | Vedere se completiamo, val_data record |
| R33_C3_B5_T12_fix | B5 (E1+decay+warmup) | 12 | 10000 | Stability + Tp boost |
| R33_C4_A4_T15_fix | A4 con T0=15 originale | 15 | 10000 | Isolare effetto solo-soglia |
| R33_C5_A3_adapt_fix | A3 adaptive | 15 | 10000 | Era Tp=0.065 reale o transient? |

## Output atteso

- Se C1/C2 completano >45 ep -> il problema era la soglia, peak Tp dovrebbe rimanere
- Se C4 completa piu' di R32_A4 (41 ep) -> conferma che soglia=100 era il limite
- Se C5 Tp >= 0.065 e gn < 1e10 -> A3 adaptive potrebbe essere reale champion
- Aggregato finale: tabella R33 vs R32 champion side-by-side
"""


CELL_1_BOOTSTRAP = """# Cell 1 -- Bootstrap + GLOBALS + ENV check
import sys, os, subprocess
import importlib.util as _imu

RESULTS_DIR = 'results/Prodigy_Study/R33_Closure'
AGGREGATE_CSV = f'{RESULTS_DIR}/_aggregate.csv'
BRANCH = 'Prodigy_Deep_Study'
_TMP_MSG = '/tmp/r33_msg.txt' if os.path.isdir('/tmp') else 'r33_msg.txt'
os.makedirs(RESULTS_DIR, exist_ok=True)

for pkg in ['prodigyopt', 'pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)

for f in ['train.py', 'core/network.py']:
    assert os.path.isfile(f)

# Verifica CLI R32 + nuovi default R33 disponibili
help_txt = subprocess.run([sys.executable, 'train.py', '--help'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
for flag in ['--restart_T0', '--restart_decay', '--restart_warmup_epochs',
             '--restart_adaptive', '--epoch_explosion_threshold']:
    assert flag in help_txt, f'MISSING CLI: {flag}'
assert 'custom_restart' in help_txt

br = subprocess.run(['git','branch','--show-current'], capture_output=True, text=True).stdout.strip()
assert br == BRANCH
print(f'[R33] ENV OK. branch={br}')
print(f'  RESULTS_DIR={RESULTS_DIR}')"""


CELL_2_EXPERIMENTS = '''# Cell 2 -- R33 EXPERIMENTS: 3 champion replica + 2 controlli = 5 run

# Base C3 con CORREZIONI R33 (threshold 10000, T0 12)
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
    # R33 fix #1: soglia 100 -> 10000
    'max_epoch_explosion_streak': 2,
    'epoch_explosion_threshold': 10000.0,
    # R33 fix #2: T0 15 -> 12
    'scheduler': 'custom_restart',
    'T0': 5,  # legacy
    'restart_T0': 12,
    'restart_decay': 1.0,
    'restart_lr_after': -1.0,
    'restart_warmup_epochs': 0,
    'restart_adaptive': 0,
}

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
    # === Asse C — champion replica con BOTH fix (T0=12 + threshold=10000) ===
    _exp('R33_C1_A4_T12_fix',
         'R32_A4 (warmup 2ep) con T0=12 + threshold 10000',
         C3_BASE, 'C_champion_fix', restart_warmup_epochs=2),
    _exp('R33_C2_A1_T12_fix',
         'R32_A1 (decay 0.3) con T0=12 + threshold 10000',
         C3_BASE, 'C_champion_fix', restart_decay=0.3),
    _exp('R33_C3_B5_T12_fix',
         'R32_B5 (E1 + decay 0.3 + warmup 2) con T0=12 + threshold 10000',
         E1_BASE, 'C_champion_fix', restart_decay=0.3, restart_warmup_epochs=2),
    # === Asse D — controlli (isolano effetto singolo fix) ===
    _exp('R33_D1_A4_T15_thr10k',
         'A4 con T0=15 originale + threshold 10000 (isola effetto soglia)',
         C3_BASE, 'D_isolation', restart_T0=15, restart_warmup_epochs=2),
    _exp('R33_D2_A3_adaptive_thr10k',
         'A3 adaptive (Tp=0.065 R32) con threshold 10000 (era peak reale?)',
         C3_BASE, 'D_isolation', restart_T0=15, restart_adaptive=1),
]

print(f'R33 EXPERIMENTS: {len(EXPERIMENTS)}')
total_min = 0
for e in EXPERIMENTS:
    est = e['epochs'] * 0.55
    total_min += est
    parts = [f"T0={e['restart_T0']}"]
    if e['restart_decay'] != 1.0: parts.append(f"decay={e['restart_decay']}")
    if e['restart_warmup_epochs'] > 0: parts.append(f"warmup={e['restart_warmup_epochs']}ep")
    if e['restart_adaptive']: parts.append("adaptive")
    parts.append(f"h={e['hidden_size']}")
    parts.append(f"thr={int(e['epoch_explosion_threshold'])}")
    print(f"  [{e['axis']:<16}] {e['tag']:<28} ep={e['epochs']:<2} ~{est:>4.0f}min [{', '.join(parts)}]")
print(f"\\nTotale stimato: {total_min:.0f} min = {total_min/60:.1f}h (meno abort attesi vs R32)")'''


CELL_3_CACHE = """# Cell 3 -- Cache check (Python 3.10 compatible)
import os
cache = C3_BASE['cache_path']
if os.path.isfile(cache):
    sz_mb = os.path.getsize(cache) / 1e6
    print(f'  [OK] cache {cache}  ({sz_mb:.1f} MB)')
else:
    print(f'  [INFO] cache mancante: {cache} -- verra generata al primo run')"""


CELL_4_PREFLIGHT = """# Cell 4 -- Pre-flight 1ep x 3step (verifica nuovi default)
import sys, subprocess, time, shutil, os
tag = f'_R33_PREFLIGHT_{int(time.time())}'
cmd = [sys.executable,'train.py','--training_method','baseline',
    '--epochs','1','--max_steps_per_epoch','3','--batch_size','8','--val_batch_size','32',
    '--seq_len','50','--cf_hidden_size','32','--cf_rank','8','--cf_max_delay','6','--cf_bit_shift','3',
    '--cf_init_bias_shift','1','--cf_logit_tau_per_channel','10.0,3.0,10.0,3.0,3.0',
    '--lambda_data','1.0','--lambda_phys','0.1','--lambda_ou','0.05','--lambda_bc','1.0','--lambda_sr','0.5','--lambda_T_aux','0.0',
    '--scenario_mix',C3_BASE['scenario_mix'],'--cut_in_ratio','0.0','--noise_scale','0.0',
    '--n_train','80','--n_val','40',
    '--optimizer','prodigy','--lr','0.5','--max_lr','0.5',
    '--scheduler','custom_restart','--restart_T0','12','--restart_warmup_epochs','2',
    '--prodigy_betas','0.9,0.99','--prodigy_d_coef','1.0','--prodigy_d0','1e-6',
    '--prodigy_weight_decay','0.01','--prodigy_use_bias_correction','1','--prodigy_safeguard_warmup','1',
    '--prodigy_growth_rate','inf','--max_inf_streak','99999','--early_stop_patience','0',
    '--max_epoch_explosion_streak','2','--epoch_explosion_threshold','10000.0','--tag',tag]
r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
assert r.returncode == 0, f'preflight failed: {r.stderr[-500:]}'
assert '[R32 Custom Restart]' in r.stdout, 'R32 scheduler init message missing'
assert 'T0=12' in r.stdout, 'T0=12 not propagated'
print('  [OK] R33 smoke OK (T0=12, threshold=10000)')
def _rmt(p):
    if os.path.isdir(p): shutil.rmtree(p, ignore_errors=True)
_rmt(f'checkpoints/{tag}')"""


CELL_5_SWEEP = """# Cell 5 -- SWEEP loop (R32 pattern)
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
    msg = f'results (R33 Closure): {tag} ({ts})\\n\\n{val_str}\\ndesc={e["desc"]}\\nAxis: {e["axis"]}\\nBranch: {BRANCH}\\n'
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
print(f'\\n{"="*78}\\nSWEEP R33 DONE in {(time.time()-t_start)/60:.0f}min')"""


CELL_6_AGGREGATOR = """# Cell 6 -- Aggregator R33 + side-by-side vs R32 champion
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
        'vb_ep': iv+1, 'val_data@vb': float(edf['val_data'].iloc[iv]),
        'spike_train': float(sr), 'gn_max': float(gn),
        'hidden': cfg.get('cf_hidden_size'),
        'lambda_sr': cfg.get('lambda_sr', 0.5),
        'restart_T0': cfg.get('restart_T0', 12),
        'restart_decay': cfg.get('restart_decay', 1.0),
        'restart_warmup': cfg.get('restart_warmup_epochs', 0),
        'restart_adaptive': cfg.get('restart_adaptive', 0),
        'expl_thr': cfg.get('epoch_explosion_threshold', 10000.0),
    })
df = pd.DataFrame(rows).sort_values('Tp', ascending=False)
df.to_csv(AGGREGATE_CSV, index=False)
print(f'R33 runs: {len(df)}')
display(Markdown('## R33 sintesi (T_intra peak desc)'))
display(df[['tag','axis','n_ep','planned_ep','Tp_ep','Tp','val_data@Tp',
            'val_data@vb','spike_train','gn_max']].round(4))

# Side-by-side R32 vs R33 per i champion replicati
R32_AGG = 'results/Prodigy_Study/R32_RestartMechanisms/_aggregate.csv'
if os.path.isfile(R32_AGG):
    r32 = pd.read_csv(R32_AGG)
    pairs = [
        ('R32_A4_C3_warmup2ep', 'R33_C1_A4_T12_fix'),
        ('R32_A1_C3_decay03',   'R33_C2_A1_T12_fix'),
        ('R32_B5_E1_decay03_warmup2', 'R33_C3_B5_T12_fix'),
        ('R32_A3_C3_adaptive',  'R33_D2_A3_adaptive_thr10k'),
    ]
    display(Markdown('## Side-by-side R32 vs R33 (champion replica)'))
    comp_rows = []
    for r32_tag, r33_tag in pairs:
        a = r32[r32.tag == r32_tag]
        b = df[df.tag == r33_tag]
        if len(a) == 0 or len(b) == 0: continue
        a = a.iloc[0]; b = b.iloc[0]
        comp_rows.append({
            'pair': f'{r32_tag.replace("R32_","")} -> {r33_tag.replace("R33_","")}',
            'Tp_R32': round(float(a['Tp']),4), 'Tp_R33': round(float(b['Tp']),4),
            'Tp_delta': round(float(b['Tp']) - float(a['Tp']), 4),
            'ep_R32': int(a['n_ep']), 'ep_R33': int(b['n_ep']),
            'val_R32': round(float(a['val_data@vb']),4), 'val_R33': round(float(b['val_data@vb']),4),
            'gn_R32': float(a['gn_max']), 'gn_R33': float(b['gn_max']),
        })
    if comp_rows:
        display(pd.DataFrame(comp_rows))"""


CELL_7_PLOTS = """# Cell 7 -- Plots R33: lr trajectory (verify T0=12 vs T0=15) + Tp evolution
import os, pandas as pd, numpy as np
import matplotlib.pyplot as plt

if 'df' not in dir(): df = pd.read_csv(AGGREGATE_CSV)

fig, axes = plt.subplots(2, 2, figsize=(16, 10))

# Plot 1: lr trajectory per run (T0=12 visivo)
ax = axes[0,0]
for _, r in df.iterrows():
    log = f'{RESULTS_DIR}/{r["axis"]}/{r["tag"]}/training_log.csv'
    if not os.path.isfile(log): continue
    edf = pd.read_csv(log)
    if 'lr' not in edf.columns: continue
    label = r['tag'].replace('R33_','')[:24]
    ax.plot(edf['epoch'], edf['lr'], marker='.', alpha=0.7, label=label)
# Vertical lines at T0=12 multiples
for x in [12, 24, 36, 48]:
    ax.axvline(x, color='red', linestyle=':', alpha=0.3)
ax.set_xlabel('epoch'); ax.set_ylabel('lr')
ax.set_title('LR trajectory R33 (red dashes = T0=12 restart points)')
ax.legend(fontsize=7); ax.grid(alpha=0.3)
ax.set_yscale('log')

# Plot 2: T_intra evolution con riferimenti R32 champion
ax = axes[0,1]
for _, r in df.iterrows():
    log = f'{RESULTS_DIR}/{r["axis"]}/{r["tag"]}/training_log.csv'
    if not os.path.isfile(log): continue
    edf = pd.read_csv(log)
    if 'val_T_intra_corr' not in edf.columns: continue
    label = r['tag'].replace('R33_','')[:24]
    ax.plot(edf['epoch'], edf['val_T_intra_corr'], marker='.', alpha=0.7, label=label)
ax.axhline(0.0635, color='purple', linestyle=':', alpha=0.5, label='R32_A4 record')
ax.axhline(0.0599, color='blue', linestyle=':', alpha=0.5, label='R31_A3 record')
ax.axhline(0.0519, color='green', linestyle=':', alpha=0.5, label='R32_B5')
ax.set_xlabel('epoch'); ax.set_ylabel('val_T_intra_corr')
ax.set_title('T_intra R33 vs R32 champion records')
ax.legend(fontsize=7); ax.grid(alpha=0.3)

# Plot 3: gn distribution con soglia 10000
ax = axes[1,0]
df_sorted = df.sort_values('gn_max').reset_index(drop=True)
colors = ['green' if g < 1e4 else 'orange' if g < 1e8 else 'red' for g in df_sorted['gn_max']]
ax.barh(range(len(df_sorted)), np.log10(df_sorted['gn_max'].clip(1)), color=colors, alpha=0.7)
ax.set_yticks(range(len(df_sorted)))
ax.set_yticklabels([t.replace('R33_','')[:24] for t in df_sorted['tag']], fontsize=8)
ax.axvline(4, color='red', linestyle='--', alpha=0.5, label='new threshold 10^4')
ax.set_xlabel('log10(gn_max)')
ax.set_title('gn_max per run (vs nuova soglia)')
ax.legend(); ax.grid(alpha=0.3, axis='x')

# Plot 4: ep completed bar chart
ax = axes[1,1]
ax.barh(range(len(df)), df['n_ep'], alpha=0.7, color='steelblue')
ax.set_yticks(range(len(df)))
ax.set_yticklabels([t.replace('R33_','')[:24] for t in df['tag']], fontsize=8)
ax.axvline(50, color='green', linestyle='--', alpha=0.5, label='planned 50 ep')
ax.set_xlabel('epoch completate')
ax.set_title('Completion rate (R33 con guard rilassata)')
ax.legend(); ax.grid(alpha=0.3, axis='x')

plt.tight_layout()
plt.savefig(f'{RESULTS_DIR}/R33_summary.png', dpi=120)
plt.show()
print(f'Saved {RESULTS_DIR}/R33_summary.png')"""


CELL_8_FINAL = """# Cell 8 -- Final commit + tag
import subprocess
subprocess.run(['git','add', RESULTS_DIR], capture_output=True)
r = subprocess.run(['git','commit','-m', f'R33 closure: aggregate + plots'],
                    capture_output=True, text=True)
print(r.stdout[-300:] if r.returncode==0 else r.stderr[-300:])
subprocess.run(['git','push','origin', BRANCH], capture_output=True)
print('R33 closure pushed.')"""


def main():
    cells = [
        make_cell('markdown', MARKDOWN_INTRO, 'cell-intro'),
        make_cell('code', CELL_1_BOOTSTRAP, 'cell-1'),
        make_cell('code', CELL_2_EXPERIMENTS, 'cell-2'),
        make_cell('code', CELL_3_CACHE, 'cell-3'),
        make_cell('code', CELL_4_PREFLIGHT, 'cell-4'),
        make_cell('code', CELL_5_SWEEP, 'cell-5'),
        make_cell('code', CELL_6_AGGREGATOR, 'cell-6'),
        make_cell('code', CELL_7_PLOTS, 'cell-7'),
        make_cell('code', CELL_8_FINAL, 'cell-8'),
    ]
    nb = make_notebook(cells)
    out = os.path.join(ROOT, 'Prodigy_Closure_R33.ipynb')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
