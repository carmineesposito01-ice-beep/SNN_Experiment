"""R31: Champion Validation — sweep esaustivo per validazione finale prima del merge.

Goals:
1. Verificare se R29v2_C3 (champion 4/4 obj a 10 ep) continua a salire o degrada con piu' epoche
2. Esplorare varianti per-channel tau ratios
3. Testare combo C3 + R25/R30 winners
4. Replicare D1/D2 a 30 ep per confermare degradazione post-peak
5. Provare warm restart come escape post-peak
6. Triple combo aggressivi a 50 ep

14 esperimenti totali, ~4-5h Azure CPU.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_cell(cell_type, source, cell_id):
    if isinstance(source, list):
        source = '\n'.join(source)
    c = {'cell_type': cell_type, 'id': cell_id, 'metadata': {}, 'source': source}
    if cell_type == 'code':
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
        'nbformat': 4,
        'nbformat_minor': 5,
    }


MARKDOWN_INTRO = """# R31 Champion Validation — sweep esaustivo per chiusura Prodigy

## Contesto

R29v2_C3 (init_bias_shift + per-channel τ [10,3,10,3,3]) è il champion **4/4 obiettivi** del sweep v2 con T_intra_peak=0.041 @ ep10. Ma:
- C3 a ep10 stava ANCORA SALENDO (training non completato)
- D1/D2 (20 ep) hanno mostrato peak T_intra=0.054 a ep14 e ep11 poi DEGRADANO
- Pattern T_intra: peak → decadimento post-peak (confermato su 30 ep di E3)

## Esperimenti (14 run)

**A — C3 duration scaling** (3 run): vedere se C3 estende il pattern di crescita o trova plateau
- A1: C3 + 30 ep
- A2: C3 + 50 ep
- A3: C3 + 50 ep + cosine warm restart T0=15 (escape mechanism)

**B — Per-channel τ variants @ 50 ep** (3 run): esplorare lo spazio τ
- B1: τ=[15,3,15,3,3] (più aggressivo su v0/s0)
- B2: τ=[10,5,10,5,5] (bilanciato)
- B3: τ=[5,3,5,3,3] (mild)

**C — Champion + R25/R30 winners @ 30 ep** (4 run): combo del champion con altri win
- C1: C3 + λ_sr=5 (R25_C2 winner per spike rate)
- C2: C3 + hidden=16, rank=4 (R25_D1 winner capacity ridotta)
- C3: C3 + λ_T_aux=0.1 (R25_B1 supervisione T)
- C4: C3 + λ_s0_aux=0.1 (R30_A2 unico positivo)

**D — Scalar τ long replica @ 30 ep** (2 run): confermare se D1/D2 esplosioni sono riproducibili
- D1: scalar init + τ 5→1 + 30 ep
- D2: scalar init + τ 10→1 + 30 ep

**E — Triple combo aggressive @ 50 ep** (2 run): combinazione di TUTTI i win possibili
- E1: C3 + hidden=16 + λ_sr=5 + 50 ep
- E2: C3 + hidden=16 + λ_T_aux=0.1 + 50 ep

## Sicurezza

Explosion guard ATTIVO: max_streak=2, threshold=100. Run instabili abortiti dopo 2 epoche.

## Output

`results/Prodigy_Study/R31_ChampionValidation/<axis>/<tag>/`
"""

CELL_1_BOOTSTRAP = """# Cell 1 -- Bootstrap + GLOBALS + ENV check
import sys, os, subprocess
import importlib.util as _imu

RESULTS_DIR = 'results/Prodigy_Study/R31_ChampionValidation'
AGGREGATE_CSV = f'{RESULTS_DIR}/_aggregate.csv'
BRANCH = 'Prodigy_Deep_Study'
_TMP_MSG = '/tmp/r31_msg.txt' if os.path.isdir('/tmp') else 'r31_msg.txt'
os.makedirs(RESULTS_DIR, exist_ok=True)

for pkg in ['prodigyopt', 'pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)

for f in ['train.py', 'core/network.py',
          'Arch_Tested/R24F_MIXED_lr0.5_V08_TRUE_CHAMPION/snapshot_original/training_log.csv']:
    assert os.path.isfile(f), f'MISSING: {f}'

sys.path.insert(0, '.')
for mod in ['train','core.network']:
    if mod in sys.modules: del sys.modules[mod]
from train import CSVLogger, pinn_loss
assert 'val_T_intra_corr' in CSVLogger.COLS

help_txt = subprocess.run([sys.executable, 'train.py', '--help'],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace').stdout
for flag in ['--max_epoch_explosion_streak', '--lambda_v0_aux', '--lambda_s0_aux',
             '--cf_init_bias_shift', '--cf_logit_tau_per_channel', '--scheduler', '--T0']:
    assert flag in help_txt, f'MISSING CLI: {flag}'

br = subprocess.run(['git','branch','--show-current'], capture_output=True, text=True).stdout.strip()
assert br == BRANCH
print(f'[R31] ENV check passed. branch={br}')
print(f'  RESULTS_DIR = {RESULTS_DIR}')"""


CELL_2_EXPERIMENTS = """# Cell 2 -- R31 EXPERIMENTS (14 run)
# Baseline R24F + R29 champion C3 setup
R24F_BASELINE = {
    'optimizer': 'prodigy', 'lr': 0.5,
    'd0': 1e-6, 'd_coef': 1.0, 'growth_rate': 'inf',
    'epochs': 10, 'max_steps_per_epoch': 100,
    'seq_len': 50,
    'hidden_size': 32, 'rank': 8,
    'max_delay': 6, 'bit_shift': 3,
    'lambda_sr': 0.5, 'lambda_T_aux': 0.0,
    'lambda_v0_aux': 0.0, 'lambda_s0_aux': 0.0,
    'lambda_a_aux':  0.0, 'lambda_b_aux':  0.0,
    'scenario_mix': 'highway:0.4,urban:0.3,truck:0.2,mixed:0.1',
    'cut_in_ratio': 0.0,
    'scheduler': 'cosine_no_restart',
    'T0': 5,
    'cache_path': 'data/cache_1500_mixed_cut0.0_ou0.0.pt',
    'po2_enabled': 1,
    'init_bias_shift': 0,
    'tau_init': 1.0, 'tau_final': 1.0,
    'tau_schedule': 'const',
    'tau_per_channel': None,
    # Explosion guard ON
    'max_epoch_explosion_streak': 2,
    'epoch_explosion_threshold':  100.0,
}

# Champion C3 setup (init_bias_shift + per-channel tau)
C3_SETUP = dict(R24F_BASELINE)
C3_SETUP.update({
    'init_bias_shift': 1,
    'tau_per_channel': '10.0,3.0,10.0,3.0,3.0',
    'tau_schedule': 'const',
})

def _exp(tag, desc, axis, **overrides):
    e = dict(C3_SETUP)  # Default = C3 champion
    e.update({'tag': tag, 'desc': desc, 'axis': axis})
    e.update(overrides)
    return e

EXPERIMENTS = [
    # A — C3 duration scaling
    _exp('R31_A1_C3_ep30', 'C3 a 30 ep (cresce o plateau?)',
         'A_duration', epochs=30),
    _exp('R31_A2_C3_ep50', 'C3 a 50 ep (definitivo)',
         'A_duration', epochs=50),
    _exp('R31_A3_C3_ep50_warmrestart', 'C3 50ep + cosine warm restart T0=15',
         'A_duration', epochs=50, scheduler='cosine', T0=15),

    # B — Per-channel tau variants @ 50 ep
    _exp('R31_B1_pc_aggressive_ep50', 'τ=[15,3,15,3,3] aggressivo + 50ep',
         'B_per_channel', epochs=50, tau_per_channel='15.0,3.0,15.0,3.0,3.0'),
    _exp('R31_B2_pc_balanced_ep50', 'τ=[10,5,10,5,5] bilanciato + 50ep',
         'B_per_channel', epochs=50, tau_per_channel='10.0,5.0,10.0,5.0,5.0'),
    _exp('R31_B3_pc_mild_ep50', 'τ=[5,3,5,3,3] mild + 50ep',
         'B_per_channel', epochs=50, tau_per_channel='5.0,3.0,5.0,3.0,3.0'),

    # C — Champion combos with prior winners @ 30 ep
    _exp('R31_C1_C3_plus_sr5_ep30', 'C3 + λ_sr=5 (R25 C2 winner)',
         'C_combos', epochs=30, lambda_sr=5.0),
    _exp('R31_C2_C3_plus_hidden16_ep30', 'C3 + hidden=16 rank=4 (R25 D1 winner)',
         'C_combos', epochs=30, hidden_size=16, rank=4),
    _exp('R31_C3_C3_plus_Taux_ep30', 'C3 + λ_T_aux=0.1 (R25 B1)',
         'C_combos', epochs=30, lambda_T_aux=0.1),
    _exp('R31_C4_C3_plus_s0aux_ep30', 'C3 + λ_s0_aux=0.1 (R30 A2 unico positivo)',
         'C_combos', epochs=30, lambda_s0_aux=0.1),

    # D — Scalar tau long replication @ 30 ep
    _exp('R31_D1_scalar_init_tau5_ep30', 'scalar init + τ 5→1 + 30 ep (replica D1)',
         'D_scalar_long', epochs=30, init_bias_shift=1,
         tau_per_channel=None, tau_init=5.0, tau_final=1.0, tau_schedule='linear'),
    _exp('R31_D2_scalar_init_tau10_ep30', 'scalar init + τ 10→1 + 30 ep (replica D2)',
         'D_scalar_long', epochs=30, init_bias_shift=1,
         tau_per_channel=None, tau_init=10.0, tau_final=1.0, tau_schedule='linear'),

    # E — Triple combo aggressive @ 50 ep
    _exp('R31_E1_triple_C3_h16_sr5_ep50', 'C3 + hidden=16 + λ_sr=5 + 50ep',
         'E_triple', epochs=50, hidden_size=16, rank=4, lambda_sr=5.0),
    _exp('R31_E2_triple_C3_h16_Taux_ep50', 'C3 + hidden=16 + λ_T_aux=0.1 + 50ep',
         'E_triple', epochs=50, hidden_size=16, rank=4, lambda_T_aux=0.1),
]

print(f'R31 EXPERIMENTS: {len(EXPERIMENTS)}')
print()
total_min = 0
for e in EXPERIMENTS:
    n_ep = e['epochs']
    est_min = n_ep * 0.6  # ~0.6 min/ep on Azure CPU
    total_min += est_min
    extras = []
    if e.get('init_bias_shift'): extras.append('init')
    if e.get('tau_per_channel'): extras.append(f"τ_pc={e['tau_per_channel']}")
    elif e.get('tau_init') != 1.0: extras.append(f"τ {e['tau_init']}→{e['tau_final']} {e['tau_schedule']}")
    if e.get('lambda_T_aux'): extras.append(f"λ_T={e['lambda_T_aux']}")
    if e.get('lambda_s0_aux'): extras.append(f"λ_s0={e['lambda_s0_aux']}")
    if e.get('lambda_sr') != 0.5: extras.append(f"λ_sr={e['lambda_sr']}")
    if e.get('hidden_size') != 32: extras.append(f"h={e['hidden_size']}")
    if e.get('scheduler') != 'cosine_no_restart': extras.append(f"sched={e['scheduler']} T0={e['T0']}")
    print(f"  [{e['axis']:<14}] {e['tag']:<36} ep={n_ep:<2}  ~{est_min:.0f}min  [{', '.join(extras)}]")
print(f"\\nTempo stimato totale: {total_min:.0f} min = {total_min/60:.1f}h Azure CPU")
print(f"(con guard abort early su esplosioni, atteso ~50-70% del tempo)")"""


CELL_3_CACHE = """# Cell 3 -- Cache check
import os
cache = R24F_BASELINE['cache_path']
if os.path.isfile(cache):
    print(f'  [OK] cache {cache}  ({os.path.getsize(cache)/1e6:.1f} MB)')
else:
    print(f'  [WARN] cache mancante, sara\\' generata dal primo run')"""


CELL_4_PREFLIGHT = """# Cell 4 -- Pre-flight smoke: C3 setup 1ep × 3step
import sys, subprocess, time, os, shutil
tag_smoke = f'_R31_PREFLIGHT_{int(time.time())}'
cmd = [sys.executable, 'train.py',
    '--training_method', 'baseline',
    '--epochs', '1', '--max_steps_per_epoch', '3',
    '--batch_size', '8', '--val_batch_size', '32',
    '--seq_len', '50',
    '--cf_hidden_size', '32', '--cf_rank', '8',
    '--cf_max_delay', '6', '--cf_bit_shift', '3',
    '--cf_init_bias_shift', '1',
    '--cf_logit_tau_per_channel', '10.0,3.0,10.0,3.0,3.0',
    '--lambda_data', '1.0', '--lambda_phys', '0.1', '--lambda_ou', '0.05',
    '--lambda_bc', '1.0', '--lambda_sr', '0.5', '--lambda_T_aux', '0.0',
    '--scenario_mix', R24F_BASELINE['scenario_mix'],
    '--cut_in_ratio', '0.0', '--noise_scale', '0.0',
    '--n_train', '80', '--n_val', '40',
    '--optimizer', 'prodigy', '--lr', '0.5', '--max_lr', '0.5',
    '--scheduler', 'cosine_no_restart',
    '--prodigy_betas', '0.9,0.99', '--prodigy_d_coef', '1.0', '--prodigy_d0', '1e-6',
    '--prodigy_weight_decay', '0.01', '--prodigy_use_bias_correction', '1',
    '--prodigy_safeguard_warmup', '1', '--prodigy_growth_rate', 'inf',
    '--max_inf_streak', '99999', '--early_stop_patience', '0',
    '--max_epoch_explosion_streak', '2', '--epoch_explosion_threshold', '100.0',
    '--tag', tag_smoke]
r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
assert r.returncode == 0, f'preflight failed: {r.stderr[-500:]}'
assert '[R29 DEC-3] decode_offset calibrato' in r.stdout
assert 'logit_tau per-channel init' in r.stdout
print('  [OK] C3 setup + R31 guard preflight passato')

def _robust_rmtree(path):
    if os.path.isdir(path):
        try: shutil.rmtree(path, ignore_errors=True)
        except: pass
_robust_rmtree(f'checkpoints/{tag_smoke}')"""


CELL_5_SWEEP = """# Cell 5 -- SWEEP loop (pattern R29_v2: stream stdout + idempotenza + push per-run)
import subprocess, sys, time, os, shutil, glob, datetime
import pandas as pd

SKIP_IF_EXISTS = True

def _robust_rmtree(path, max_retries=3):
    for attempt in range(max_retries):
        if not os.path.isdir(path): return True
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.isdir(path): return True
        time.sleep(0.5 * (attempt + 1))
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
        '--cf_logit_tau_init',  str(e['tau_init']),
        '--cf_logit_tau_final', str(e['tau_final']),
        '--cf_logit_tau_schedule', e['tau_schedule'],
        '--lambda_data', '1.0', '--lambda_phys', '0.1', '--lambda_ou', '0.05',
        '--lambda_bc', '1.0', '--lambda_sr', str(e['lambda_sr']),
        '--lambda_T_aux', str(e['lambda_T_aux']),
        '--lambda_v0_aux', str(e['lambda_v0_aux']),
        '--lambda_s0_aux', str(e['lambda_s0_aux']),
        '--lambda_a_aux',  str(e['lambda_a_aux']),
        '--lambda_b_aux',  str(e['lambda_b_aux']),
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
        '--prodigy_betas', '0.9,0.99',
        '--prodigy_d_coef', str(e['d_coef']),
        '--prodigy_d0', str(e['d0']),
        '--prodigy_weight_decay', '0.01',
        '--prodigy_use_bias_correction', '1',
        '--prodigy_safeguard_warmup', '1',
        '--prodigy_growth_rate', str(e['growth_rate']),
        '--max_epoch_explosion_streak', str(e['max_epoch_explosion_streak']),
        '--epoch_explosion_threshold',  str(e['epoch_explosion_threshold']),
        '--tag', e['tag']]
    if e.get('tau_per_channel'):
        cli.extend(['--cf_logit_tau_per_channel', e['tau_per_channel']])
    return cli

def _dst_for(e):
    return f"{RESULTS_DIR}/{e['axis']}/{e['tag']}"

def _push_run(e):
    tag = e['tag']
    src = f'checkpoints/{tag}'
    dst = _dst_for(e)
    if not os.path.isdir(src):
        print(f'   [WARN push] {src} mancante')
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
                bi = int(edf.val_total.idxmin())
                tc = edf.get('val_T_tracking_corr', pd.Series([float('nan')])).iloc[bi]
                tci = edf.get('val_T_intra_corr', pd.Series([float('nan')])).iloc[bi]
                # ALSO peak T_intra
                tp_idx = int(edf['val_T_intra_corr'].idxmax()) if 'val_T_intra_corr' in edf.columns else bi
                tp_val = edf['val_T_intra_corr'].max() if 'val_T_intra_corr' in edf.columns else float('nan')
                val_str = (f'best val={edf.val_total.min():.4f}  T_corr={tc:.3f}  '
                           f'T_intra={tci:.3f}  T_intra_PEAK={tp_val:.3f}@ep{tp_idx+1}  '
                           f'(E{bi+1}/{len(edf)})')
        except Exception as ex:
            val_str = f'(log read failed: {ex})'
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    msg = (f"results (R31 ChampionValidation): {tag} ({ts})\\n\\n{val_str}\\n"
           f"desc={e['desc']}\\nAxis: {e['axis']}\\nBranch: {BRANCH}\\n")
    with open(_TMP_MSG, 'w', encoding='utf-8') as fp:
        fp.write(msg)
    try:
        subprocess.run(['git','add',dst], check=True, capture_output=True)
        r = subprocess.run(['git','commit','-F',_TMP_MSG], capture_output=True, text=True)
        if r.returncode != 0:
            if 'nothing to commit' in r.stdout or 'nothing to commit' in r.stderr:
                return True
            print(f'   [push commit fail] {r.stderr[-300:]}'); return False
        subprocess.run(['git','pull','--no-rebase','--no-edit','origin',BRANCH],
                       capture_output=True, text=True)
        r2 = subprocess.run(['git','push','origin',BRANCH], capture_output=True, text=True)
        if r2.returncode != 0:
            print(f'   [push fail] {r2.stderr[-300:]}'); return False
        print(f'   [push OK]')
        return True
    finally:
        try: os.remove(_TMP_MSG)
        except: pass

if 'EXPERIMENTS' not in dir():
    raise RuntimeError('EXPERIMENTS non definito')

run_results = []
t_start = time.time()
total = len(EXPERIMENTS)

for i, e in enumerate(EXPERIMENTS, 1):
    tag = e['tag']
    dst = _dst_for(e)
    dst_log = f'{dst}/training_log.csv'
    if SKIP_IF_EXISTS and os.path.isfile(dst_log):
        try:
            edf = pd.read_csv(dst_log)
            v_str = f'val={edf.val_total.min():.4f} epochs={len(edf)}/{e["epochs"]}'
            if len(edf) >= e['epochs'] * 0.8:
                print(f'\\n[{i}/{total}] [SKIP] {tag}: {v_str}')
                run_results.append({'tag': tag, 'axis': e['axis'], 'status':'skipped'})
                continue
        except Exception: pass
    print(f'\\n{"="*78}\\n[{i}/{total}] {tag}  [axis={e["axis"]}]\\n  {e["desc"]}\\n{"="*78}')
    t0 = time.time()
    r = subprocess.run(_build_cli(e), capture_output=False)
    el = time.time() - t0
    status = 'ok' if r.returncode == 0 else f'fail({r.returncode})'
    el_tot = time.time() - t_start
    done_now = sum(1 for x in run_results if x['status']!='skipped') + 1
    eta_min = (el_tot / max(done_now,1)) * (total - i) / 60
    print(f'\\n[{i}/{total}] {tag} -> {status}  ({el/60:.1f}min)  ETA={eta_min:.0f}min')
    pushed = _push_run(e)
    run_results.append({'tag': tag, 'axis': e['axis'], 'status': status, 'pushed': pushed})

print(f'\\n{"="*78}\\nSWEEP R31 DONE in {(time.time()-t_start)/60:.0f}min')"""


CELL_6_AGGREGATOR = """# Cell 6 -- Aggregator + peak T_intra reporting
import os, json, math, pandas as pd, numpy as np
from IPython.display import display, Markdown

run_dirs = []
for root, _, files in os.walk(RESULTS_DIR):
    if 'training_log.csv' in files and 'config_snapshot.json' in files:
        run_dirs.append(root)
run_dirs = sorted(run_dirs)
print(f'Run R31 discovered: {len(run_dirs)}')

rows = []
for rd in run_dirs:
    cfg = json.load(open(os.path.join(rd, 'config_snapshot.json')))
    edf = pd.read_csv(os.path.join(rd, 'training_log.csv'))
    if len(edf) == 0: continue
    bi = int(edf['val_total'].idxmin())  # best by val_total
    ip = int(edf['val_T_intra_corr'].idxmax()) if 'val_T_intra_corr' in edf.columns else bi  # peak T_intra
    bdf_path = os.path.join(rd, 'training_batch_log.csv')
    sr_train = float('nan'); gn_max = float('nan')
    try:
        bdf = pd.read_csv(bdf_path)
        sr_train = bdf['spike_rate'].mean()
        gn = bdf['gn_total_preclip']; gn_f = gn[gn.apply(math.isfinite)]
        gn_max = gn_f.max() if len(gn_f) > 0 else float('nan')
    except: pass
    row = {
        'tag': cfg['tag'],
        'axis': os.path.basename(os.path.dirname(rd)),
        'n_ep': len(edf),
        'planned_ep': cfg.get('epochs'),
        # peak T_intra metrics
        'Tp_ep': ip + 1,
        'Tp': float(edf['val_T_intra_corr'].iloc[ip]) if 'val_T_intra_corr' in edf.columns else np.nan,
        'val_data@Tp': float(edf['val_data'].iloc[ip]),
        'T_track@Tp': float(edf.get('val_T_tracking_corr', pd.Series([np.nan])).iloc[ip]),
        # best val metrics
        'vb_ep': bi+1,
        'val_data@vb': float(edf['val_data'].iloc[bi]),
        'T_intra@vb': float(edf.get('val_T_intra_corr', pd.Series([np.nan])).iloc[bi]),
        # spike + gn
        'spike_train': float(sr_train),
        'gn_max': float(gn_max),
        # config snapshot
        'init_shift': int(cfg.get('cf_init_bias_shift', 0)),
        'tau_per_ch': cfg.get('cf_logit_tau_per_channel', None),
        'tau_init': float(cfg.get('cf_logit_tau_init', 1.0)),
        'tau_final': float(cfg.get('cf_logit_tau_final', 1.0)),
        'tau_sched': cfg.get('cf_logit_tau_schedule', 'const'),
        'hidden': cfg.get('cf_hidden_size'),
        'lambda_sr': cfg.get('lambda_sr', 0.5),
        'lambda_T_aux': cfg.get('lambda_T_aux', 0.0),
        'lambda_s0_aux': cfg.get('lambda_s0_aux', 0.0),
        'scheduler': cfg.get('scheduler', 'cosine_no_restart'),
    }
    rows.append(row)
df = pd.DataFrame(rows).sort_values('Tp', ascending=False)
df.to_csv(AGGREGATE_CSV, index=False)
print(f'Saved: {AGGREGATE_CSV}')

# Multi-objective scoring
df['hit_T'] = df['Tp'] > 0.025
df['hit_V'] = df['val_data@Tp'] < 0.185
df['hit_S'] = (df['spike_train'] >= 0.10) & (df['spike_train'] <= 0.25)
df['hit_C'] = df['gn_max'] < 100
df['n_hits'] = df[['hit_T','hit_V','hit_S','hit_C']].sum(axis=1)

display(Markdown('## R31 sintesi (ordine: T_intra PEAK desc)'))
show = ['tag','axis','n_ep','planned_ep','Tp_ep','Tp','val_data@Tp','T_track@Tp',
        'spike_train','gn_max','n_hits']
show = [c for c in show if c in df.columns]
display(df[show].round(4))

# Champion 4/4
champs = df[df.n_hits == 4].sort_values('Tp', ascending=False)
if len(champs) > 0:
    display(Markdown('## Champions 4/4 obiettivi'))
    display(champs[show].round(4))
else:
    display(Markdown('### ⚠ Nessun run R31 raggiunge 4/4 obiettivi'))"""


CELL_7_PLOTS = """# Cell 7 -- Plot suite: T_intra evolution + saturazione + gradient
import os, math, pandas as pd, numpy as np
import matplotlib.pyplot as plt

if 'df' not in dir():
    df = pd.read_csv(AGGREGATE_CSV)

fig, axes = plt.subplots(2, 2, figsize=(16, 11))

# Plot 1: T_intra evolution per axis
ax = axes[0,0]
for axis in ['A_duration','B_per_channel','C_combos','D_scalar_long','E_triple']:
    sub = df[df.axis==axis]
    for _, r in sub.iterrows():
        log = f'{RESULTS_DIR}/{r["axis"]}/{r["tag"]}/training_log.csv'
        if not os.path.isfile(log): continue
        edf = pd.read_csv(log)
        if 'val_T_intra_corr' not in edf.columns: continue
        label = r['tag'].replace('R31_','')[:24]
        ax.plot(edf['epoch'], edf['val_T_intra_corr'], marker='.', label=label, alpha=0.7)
ax.axhline(0.025, color='gray', linestyle=':', alpha=0.5, label='T target')
ax.axhline(0.041, color='green', linestyle=':', alpha=0.5, label='C3 v2 record')
ax.axhline(0.054, color='blue', linestyle=':', alpha=0.5, label='D1 v2 peak')
ax.set_xlabel('epoch'); ax.set_ylabel('val_T_intra_corr')
ax.set_title('R31: T_intra evolution per run')
ax.legend(fontsize=6, loc='upper left', ncol=2); ax.grid(alpha=0.3)

# Plot 2: val_data evolution
ax = axes[0,1]
for _, r in df.iterrows():
    log = f'{RESULTS_DIR}/{r["axis"]}/{r["tag"]}/training_log.csv'
    if not os.path.isfile(log): continue
    edf = pd.read_csv(log)
    label = r['tag'].replace('R31_','')[:24]
    ax.plot(edf['epoch'], edf['val_data'], marker='.', label=label, alpha=0.6)
ax.axhline(0.185, color='red', linestyle=':', alpha=0.5, label='target <0.185')
ax.axhline(0.181, color='gray', linestyle=':', alpha=0.5, label='baseline')
ax.set_xlabel('epoch'); ax.set_ylabel('val_data')
ax.set_title('val_data evolution')
ax.legend(fontsize=6, loc='upper right'); ax.grid(alpha=0.3)

# Plot 3: Multi-objective scatter (Tp vs val_data, colored by hits)
ax = axes[1,0]
for h in range(5):
    sub = df[df.n_hits == h]
    ax.scatter(sub['val_data@Tp'], sub['Tp'], s=80+h*30, alpha=0.7, label=f'{h}/4 hit')
ax.axvline(0.185, color='gray', linestyle=':', alpha=0.5)
ax.axhline(0.025, color='gray', linestyle=':', alpha=0.5)
for _, r in df.iterrows():
    ax.annotate(r['tag'].replace('R31_','')[:14], (r['val_data@Tp'], r['Tp']),
                fontsize=7, alpha=0.7)
ax.set_xlabel('val_data@Tp'); ax.set_ylabel('T_intra_PEAK')
ax.set_title('Multi-objective Pareto (lower val + higher T)')
ax.legend(); ax.grid(alpha=0.3)

# Plot 4: gn_max distribution
ax = axes[1,1]
df_sorted = df.sort_values('gn_max')
colors = ['green' if g < 100 else ('orange' if g < 1e6 else 'red') for g in df_sorted['gn_max']]
ax.barh(range(len(df_sorted)), [math.log10(g) if g > 0 and math.isfinite(g) else 0 for g in df_sorted['gn_max']],
        color=colors, alpha=0.7)
ax.set_yticks(range(len(df_sorted)))
ax.set_yticklabels([t.replace('R31_','')[:24] for t in df_sorted['tag']], fontsize=7)
ax.axvline(2, color='black', linestyle=':', alpha=0.5, label='log10(100)=2 (soglia)')
ax.set_xlabel('log10(gn_max_preclip)')
ax.set_title('Gradient stability per run')
ax.legend(); ax.grid(alpha=0.3, axis='x')

plt.tight_layout()
out_png = f'{RESULTS_DIR}/R31_diagnostic_plots.png'
plt.savefig(out_png, dpi=110)
plt.show()
print(f'Salvato: {out_png}')"""


CELL_8_SUMMARY = """# Cell 8 -- Verdetto finale + push aggregator
import os, subprocess, tempfile, pandas as pd
from IPython.display import display, Markdown

if 'df' not in dir():
    df = pd.read_csv(AGGREGATE_CSV)

display(Markdown('## R31 Verdetto finale'))

n4 = (df.n_hits == 4).sum()
best_pk = df.sort_values('Tp', ascending=False).iloc[0]
best_pk_clean = df[df.gn_max < 100].sort_values('Tp', ascending=False).iloc[0] if (df.gn_max < 100).any() else None

print(f'Tot run R31: {len(df)}')
print(f'Champions 4/4 obiettivi: {n4}')
print(f'\\nBest T_intra_PEAK (qualsiasi): {best_pk["tag"]} = {best_pk["Tp"]:.4f}  val_data={best_pk["val_data@Tp"]:.4f}  gn={best_pk["gn_max"]:.2e}')
if best_pk_clean is not None:
    print(f'Best T_intra_PEAK CLEAN:    {best_pk_clean["tag"]} = {best_pk_clean["Tp"]:.4f}  val_data={best_pk_clean["val_data@Tp"]:.4f}  gn={best_pk_clean["gn_max"]:.2f}')

# Compare with v2 records
print()
print(f'Confronto con v2 records:')
print(f'  v2 best T_intra CLEAN: R29v2_C3 = 0.041')
print(f'  v2 best T_intra peak:  R29v2_D1 = 0.054 (esploso)')
if best_pk['Tp'] > 0.054:
    display(Markdown(f'### ✅ R31 SUPERA il record v2 (0.054). New peak={best_pk["Tp"]:.4f}'))
elif best_pk_clean is not None and best_pk_clean['Tp'] > 0.041:
    display(Markdown(f'### ✅ R31 SUPERA il record clean v2 (0.041). New clean peak={best_pk_clean["Tp"]:.4f}'))
elif best_pk['Tp'] > 0.041:
    display(Markdown(f'### ⚠ R31 supera clean v2 ma con esplosione. New peak={best_pk["Tp"]:.4f}'))
else:
    display(Markdown(f'### ❌ R31 non supera v2. Validazione conferma C3 v2 come champion finale.'))

# Push aggregator
subprocess.run(['git','add', AGGREGATE_CSV, f'{RESULTS_DIR}/R31_diagnostic_plots.png'], check=False)
msg = f'R31 ChampionValidation: {len(df)} run, best T_intra_peak={best_pk["Tp"]:.4f}'
with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt', encoding='utf-8') as fp:
    fp.write(msg); msg_path = fp.name
r = subprocess.run(['git','diff','--cached','--name-only'], capture_output=True, text=True)
if r.stdout.strip():
    subprocess.run(['git','commit','-F',msg_path], check=True)
    subprocess.run(['git','pull','--no-rebase','--no-edit','origin',BRANCH], check=True)
    subprocess.run(['git','push','origin',BRANCH], check=True)
    print('\\n[OK] aggregator R31 pushato.')
else:
    print('\\n[SKIP] nothing to push.')
try: os.unlink(msg_path)
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
    out = os.path.join(ROOT, 'Prodigy_Champion_Validation_R31.ipynb')
    with open(out, 'w', encoding='utf-8') as fp:
        json.dump(nb, fp, indent=1, ensure_ascii=False)
    print(f'Created: Prodigy_Champion_Validation_R31.ipynb ({len(cells)} cells)')


if __name__ == '__main__':
    main()
