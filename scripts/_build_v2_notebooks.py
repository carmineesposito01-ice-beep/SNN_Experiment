"""R30 (2026-06-12): Generatore notebook v2 ricalibrati su R24F_mixed_lr0.5_V08 baseline.

Genera 6 notebook in CF_FSNN/ (sopra il root):
  - Prodigy_Ablation_Study_R25_v2.ipynb   (18 run, 5 axes A/B/C/D/E)
  - Prodigy_Fusion_Study_R26_v2.ipynb     (6 run, A/B/C combinazioni)
  - Prodigy_Audit_R27_v2.ipynb            (script call audit_checkpoints.py)
  - Prodigy_Tuning_R28_v2.ipynb           (5 run, prodigy d0/steps/restart)
  - Prodigy_DecoderFix_R29_v2.ipynb       (12 run, init_shift+tau anneal)
  - Prodigy_Identifiability_R30.ipynb     (8 run, R30 ID-1: 4 lambdas aux)

Tutte queste partono dal R24F_mixed_lr0.5_V08 baseline (lr=0.5, no T_aux, seq_len=50,
mixed scenario) e usano --max_epoch_explosion_streak 2 + --epoch_explosion_threshold 100
come guard contro instabilita'.

Pattern comune: 8 celle stile R28/R29 (Bootstrap + GLOBALS + EXPERIMENTS + Cache +
Pre-flight + Sweep + Aggregator + Summary), tutti idempotenti + push per-run.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ============================================================
# Snippet riutilizzabili
# ============================================================

COMMON_HELPERS_CODE = '''# Helper riusabili (definiti qui per evitare duplicazione cross-cell)
import subprocess, sys, time, os, shutil, glob, datetime
import pandas as pd

def _robust_rmtree(path, max_retries=3):
    for attempt in range(max_retries):
        if not os.path.isdir(path): return True
        shutil.rmtree(path, ignore_errors=True)
        if not os.path.isdir(path): return True
        time.sleep(0.5 * (attempt + 1))
    shutil.rmtree(path, ignore_errors=True)
    return not os.path.isdir(path)

def _build_cli(e):
    cli = [sys.executable, "train.py",
        "--training_method", "baseline",
        "--epochs", str(e["epochs"]),
        "--max_steps_per_epoch", str(e["max_steps_per_epoch"]),
        "--batch_size", "8", "--val_batch_size", "32",
        "--seq_len", str(e["seq_len"]),
        "--cf_hidden_size", str(e["hidden_size"]),
        "--cf_rank", str(e["rank"]),
        "--cf_max_delay", str(e["max_delay"]),
        "--cf_bit_shift", str(e["bit_shift"]),
        # R29 decoder fix flags (default no-op)
        "--cf_init_bias_shift", str(e.get("init_bias_shift", 0)),
        "--cf_logit_tau_init",  str(e.get("tau_init", 1.0)),
        "--cf_logit_tau_final", str(e.get("tau_final", 1.0)),
        "--cf_logit_tau_schedule", e.get("tau_schedule", "const"),
        # R25 + R30 supervisione esplicita params
        "--lambda_data", "1.0", "--lambda_phys", "0.1", "--lambda_ou", "0.05",
        "--lambda_bc", "1.0", "--lambda_sr", str(e["lambda_sr"]),
        "--lambda_T_aux", str(e["lambda_T_aux"]),
        "--lambda_v0_aux", str(e.get("lambda_v0_aux", 0.0)),
        "--lambda_s0_aux", str(e.get("lambda_s0_aux", 0.0)),
        "--lambda_a_aux",  str(e.get("lambda_a_aux", 0.0)),
        "--lambda_b_aux",  str(e.get("lambda_b_aux", 0.0)),
        "--scenario_mix", e["scenario_mix"],
        "--cut_in_ratio", str(e["cut_in_ratio"]),
        "--noise_scale", "0.0", "--po2_enabled", str(e.get("po2_enabled", 1)),
        "--n_train", "1500", "--n_val", "300",
        "--max_inf_streak", "99999", "--early_stop_patience", "0",
        "--data_cache", e["cache_path"],
        "--optimizer", e["optimizer"],
        "--lr", str(e["lr"]), "--max_lr", str(e["lr"]),
        "--scheduler", e["scheduler"],
        "--T0", str(e["T0"]),
        "--prodigy_betas", "0.9,0.99",
        "--prodigy_d_coef", str(e["d_coef"]),
        "--prodigy_d0", str(e["d0"]),
        "--prodigy_weight_decay", "0.01",
        "--prodigy_use_bias_correction", "1",
        "--prodigy_safeguard_warmup", "1",
        "--prodigy_growth_rate", str(e["growth_rate"]),
        # R30 explosion guard (default ACTIVE per i v2)
        "--max_epoch_explosion_streak", str(e.get("max_epoch_explosion_streak", 2)),
        "--epoch_explosion_threshold",  str(e.get("epoch_explosion_threshold", 100.0)),
        "--tag", e["tag"]]
    if e.get("tau_per_channel"):
        cli.extend(["--cf_logit_tau_per_channel", e["tau_per_channel"]])
    return cli

def _dst_for(e, RESULTS_DIR):
    return f"{RESULTS_DIR}/{e['axis']}/{e['tag']}"

def _push_run(e, RESULTS_DIR, BRANCH, _TMP_MSG, study_name):
    tag = e["tag"]
    src = f"checkpoints/{tag}"
    dst = _dst_for(e, RESULTS_DIR)
    if not os.path.isdir(src):
        print(f"   [WARN push] {src} mancante")
        return False
    _robust_rmtree(dst)
    os.makedirs(f"{dst}/plots", exist_ok=True)
    for f in glob.glob(f"{src}/*.csv") + glob.glob(f"{src}/*.json"):
        shutil.copy2(f, dst)
    for f in glob.glob(f"{src}/plots/*.png"):
        shutil.copy2(f, f"{dst}/plots/")
    val_str = ""
    log_path = f"{dst}/training_log.csv"
    if os.path.isfile(log_path):
        try:
            edf = pd.read_csv(log_path)
            if len(edf) > 0:
                bi = int(edf.val_total.idxmin())
                tc  = edf.get("val_T_tracking_corr", pd.Series([float("nan")])).iloc[bi]
                tci = edf.get("val_T_intra_corr",   pd.Series([float("nan")])).iloc[bi]
                val_str = (f"best val={edf.val_total.min():.4f}  T_corr={tc:.3f}  "
                           f"T_intra={tci:.3f}  (E{bi+1}/{len(edf)})")
        except Exception as ex:
            val_str = f"(log read failed: {ex})"
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = (f"results ({study_name}): {tag} ({ts})\\n\\n{val_str}\\n"
           f"desc={e.get('desc','')}\\nAxis: {e['axis']}\\nBranch: {BRANCH}\\n")
    with open(_TMP_MSG, "w", encoding="utf-8") as fp:
        fp.write(msg)
    try:
        subprocess.run(["git","add",dst], check=True, capture_output=True)
        r = subprocess.run(["git","commit","-F",_TMP_MSG], capture_output=True, text=True)
        if r.returncode != 0:
            if "nothing to commit" in r.stdout or "nothing to commit" in r.stderr:
                return True
            print(f"   [push commit fail] {r.stderr[-300:]}"); return False
        subprocess.run(["git","pull","--no-rebase","--no-edit","origin",BRANCH],
                       capture_output=True, text=True)
        r2 = subprocess.run(["git","push","origin",BRANCH], capture_output=True, text=True)
        if r2.returncode != 0:
            print(f"   [push fail] {r2.stderr[-300:]}"); return False
        print(f"   [push OK]")
        return True
    finally:
        try: os.remove(_TMP_MSG)
        except: pass

def _run_sweep(EXPERIMENTS, RESULTS_DIR, BRANCH, _TMP_MSG, study_name, SKIP_IF_EXISTS=True):
    run_results = []
    t_start = time.time()
    total = len(EXPERIMENTS)
    for i, e in enumerate(EXPERIMENTS, 1):
        tag = e["tag"]
        dst = _dst_for(e, RESULTS_DIR)
        dst_log = f"{dst}/training_log.csv"
        if SKIP_IF_EXISTS and os.path.isfile(dst_log):
            try:
                edf = pd.read_csv(dst_log)
                v_str = f"val={edf.val_total.min():.4f} epochs={len(edf)}/{e['epochs']}"
                if len(edf) >= e["epochs"] * 0.8:
                    print(f"\\n[{i}/{total}] [SKIP] {tag}: {v_str}")
                    run_results.append({"tag": tag, "axis": e["axis"], "status":"skipped"})
                    continue
            except Exception:
                pass
        print(f"\\n{'='*78}\\n[{i}/{total}] {tag}  [axis={e['axis']}]\\n  {e.get('desc','')}\\n{'='*78}")
        t0 = time.time()
        r = subprocess.run(_build_cli(e), capture_output=False)
        el = time.time() - t0
        status = "ok" if r.returncode == 0 else f"fail({r.returncode})"
        el_tot = time.time() - t_start
        done_now = sum(1 for x in run_results if x["status"]!="skipped") + 1
        eta_min = (el_tot / max(done_now,1)) * (total - i) / 60
        print(f"\\n[{i}/{total}] {tag} -> {status}  ({el/60:.1f}min)  ETA={eta_min:.0f}min")
        pushed = _push_run(e, RESULTS_DIR, BRANCH, _TMP_MSG, study_name)
        run_results.append({"tag": tag, "axis": e["axis"], "status": status, "pushed": pushed})
    print(f"\\n{'='*78}\\nSWEEP DONE in {(time.time()-t_start)/60:.0f}min")
    return run_results
'''


COMMON_BASE_CONFIG_CODE = '''# === R24F_mixed_lr0.5_V08 BASELINE COMMON CONFIG ===
# Riferimento ufficiale: Arch_Tested/R24F_MIXED_lr0.5_V08_TRUE_CHAMPION/
# CHANGE rispetto a R25_B1 / R29_A3 (vecchi baseline lr=1.0 instabili):
#   lr 1.0 -> 0.5  (gradienti CLEAN gn_max 21.8 vs 10^5-10^17)
#   lambda_T_aux 0.1 -> 0.0  (no T-aux nel baseline, ablation testa varianti)
#   seq_len 100 -> 50  (config R24F originale)
#   AGGIUNTO --max_epoch_explosion_streak 2 + threshold 100 (R30 explosion guard)
R24F_BASELINE = {
    "optimizer": "prodigy", "lr": 0.5,                  # ← CHIAVE: 0.5 NOT 1.0
    "d0": 1e-6, "d_coef": 1.0, "growth_rate": "inf",
    "epochs": 10, "max_steps_per_epoch": 100,
    "seq_len": 50,                                      # ← CHIAVE: 50 NOT 100
    "hidden_size": 32, "rank": 8,
    "max_delay": 6, "bit_shift": 3,
    "lambda_sr": 0.5, "lambda_T_aux": 0.0,              # ← CHIAVE: 0.0 NOT 0.1
    "lambda_v0_aux": 0.0, "lambda_s0_aux": 0.0,
    "lambda_a_aux":  0.0, "lambda_b_aux":  0.0,
    "scenario_mix": "highway:0.4,urban:0.3,truck:0.2,mixed:0.1",
    "cut_in_ratio": 0.0,
    "scheduler": "cosine_no_restart",
    "T0": 5,
    "cache_path": "data/cache_1500_mixed_cut0.0_ou0.0.pt",
    "po2_enabled": 1,
    # R29 decoder fix opt-in (default no-op)
    "init_bias_shift": 0,
    "tau_init": 1.0, "tau_final": 1.0,
    "tau_schedule": "const",
    "tau_per_channel": None,
    # R30 explosion guard ATTIVO di default nei v2
    "max_epoch_explosion_streak": 2,
    "epoch_explosion_threshold":  100.0,
}

def _exp(tag, desc, axis, **overrides):
    e = {**R24F_BASELINE, "tag": tag, "desc": desc, "axis": axis}
    e.update(overrides)
    return e
'''


def make_cell(cell_type, source, cell_id):
    if isinstance(source, list):
        source = '\n'.join(source)
    cell = {
        'cell_type': cell_type,
        'id': cell_id,
        'metadata': {},
        'source': source if cell_type == 'markdown' else source,
    }
    if cell_type == 'code':
        cell['execution_count'] = None
        cell['outputs'] = []
    return cell


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


def std_cell_1_bootstrap(study_name, results_dir, msg_name):
    """Cell 1: bootstrap + globals + ENV check."""
    return f"""# Cell 1 -- Bootstrap + GLOBALS + ENV check
import sys, os, subprocess
import importlib.util as _imu

RESULTS_DIR = '{results_dir}'
AGGREGATE_CSV = f'{{RESULTS_DIR}}/_aggregate.csv'
BRANCH = 'Prodigy_Deep_Study'
_TMP_MSG = '/tmp/{msg_name}.txt' if os.path.isdir('/tmp') else '{msg_name}.txt'
os.makedirs(RESULTS_DIR, exist_ok=True)

for pkg in ['prodigyopt', 'pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)

for f in ['train.py', 'core/network.py',
          'Arch_Tested/R24F_MIXED_lr0.5_V08_TRUE_CHAMPION/snapshot_original/training_log.csv']:
    assert os.path.isfile(f), f'MISSING: {{f}}'

sys.path.insert(0, '.')
for mod in ['train','core.network']:
    if mod in sys.modules: del sys.modules[mod]
from train import CSVLogger, BatchCSVLogger, pinn_loss
assert 'val_T_intra_corr' in CSVLogger.COLS
print(f'  [OK] CSVLogger has val_T_intra_corr')

help_txt = subprocess.run([sys.executable, 'train.py', '--help'],
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace').stdout
for flag in ['--max_epoch_explosion_streak', '--epoch_explosion_threshold',
             '--lambda_v0_aux', '--lambda_s0_aux', '--lambda_a_aux', '--lambda_b_aux',
             '--cf_init_bias_shift', '--cf_logit_tau_init']:
    assert flag in help_txt, f'MISSING CLI: {{flag}}'
print(f'  [OK] all R29+R30 CLI flags present')

br = subprocess.run(['git','branch','--show-current'], capture_output=True, text=True).stdout.strip()
assert br == BRANCH, f'Branch errato: {{br}}'
print(f'  [OK] branch={{br}}')
print(f'\\n[{study_name}] ENV check passed.')
print(f'  RESULTS_DIR = {{RESULTS_DIR}}')"""


def std_cell_cache_check():
    return """# Cell 3 -- Cache check (riuso R24F mixed cache)
import os
cache = R24F_BASELINE['cache_path']
if os.path.isfile(cache):
    sz_mb = os.path.getsize(cache) / 1e6
    print(f'  [OK] cache esistente: {cache}  ({sz_mb:.1f} MB)')
else:
    print(f'  [INFO] cache mancante: {cache} -- verra\\' generata dal primo run')"""


def std_cell_preflight():
    return """# Cell 4 -- Pre-flight smoke 1ep × 3step (validare CLI + R24F baseline config)
import torch, time, shutil, sys, subprocess
sys.path.insert(0, '.')
if 'core.network' in sys.modules: del sys.modules['core.network']
from core.network import CF_FSNN_Net

torch.manual_seed(42)
m = CF_FSNN_Net(hidden_size=32, rank=8, max_delay=6, bit_shift=3)
n_params = sum(p.numel() for p in m.parameters())
assert n_params == 864, f'Param count: {n_params}'
print(f'  [OK] CF_FSNN_Net: {n_params} param')

tag_smoke = f'_PREFLIGHT_v2_{int(time.time())}'
cmd_smoke = [sys.executable, 'train.py',
    '--training_method', 'baseline',
    '--epochs', '1', '--max_steps_per_epoch', '3',
    '--batch_size', '8', '--val_batch_size', '32',
    '--seq_len', '50',
    '--cf_hidden_size', '32', '--cf_rank', '8',
    '--cf_max_delay', '6', '--cf_bit_shift', '3',
    '--lambda_data', '1.0', '--lambda_phys', '0.1', '--lambda_ou', '0.05',
    '--lambda_bc', '1.0', '--lambda_sr', '0.5', '--lambda_T_aux', '0.0',
    '--scenario_mix', R24F_BASELINE['scenario_mix'],
    '--cut_in_ratio', '0.0', '--noise_scale', '0.0',
    '--n_train', '80', '--n_val', '40',
    '--optimizer', 'prodigy', '--lr', '0.5',  # R24F LR
    '--scheduler', 'cosine_no_restart',
    '--prodigy_betas', '0.9,0.99', '--prodigy_d_coef', '1.0',
    '--prodigy_d0', '1e-6', '--prodigy_weight_decay', '0.01',
    '--prodigy_use_bias_correction', '1', '--prodigy_safeguard_warmup', '1',
    '--prodigy_growth_rate', 'inf',
    '--max_inf_streak', '99999', '--early_stop_patience', '0',
    '--max_epoch_explosion_streak', '2', '--epoch_explosion_threshold', '100.0',
    '--tag', tag_smoke]
r = subprocess.run(cmd_smoke, capture_output=True, text=True, encoding='utf-8', errors='replace')
if r.returncode != 0:
    print('STDERR:', r.stderr[-500:])
    raise RuntimeError(f'preflight failed: {r.returncode}')

import pandas as pd, math
bdf = pd.read_csv(f'checkpoints/{tag_smoke}/training_batch_log.csv')
gn = bdf['gn_total_preclip']
gn_f = gn[gn.apply(math.isfinite)]
print(f'  [OK] Pre-flight gn_max={gn_f.max():.3f} (clean if < 25)')

import os
import shutil as _shutil
def _robust_rmtree(path, max_retries=3):
    for attempt in range(max_retries):
        if not os.path.isdir(path): return True
        _shutil.rmtree(path, ignore_errors=True)
        if not os.path.isdir(path): return True
        time.sleep(0.5 * (attempt + 1))
    return not os.path.isdir(path)
_robust_rmtree(f'checkpoints/{tag_smoke}')
print(f'\\n  PRE-FLIGHT v2 passed.')"""


def std_cell_sweep_runner(study_name):
    return f"""# Cell 5 -- SWEEP runner (idempotente + stream stdout + push per-run)
{COMMON_HELPERS_CODE}
if 'EXPERIMENTS' not in dir():
    raise RuntimeError('EXPERIMENTS non definito')
run_results = _run_sweep(EXPERIMENTS, RESULTS_DIR, BRANCH, _TMP_MSG, '{study_name}')
print('\\nSWEEP {study_name} completato.')"""


def std_cell_aggregator():
    return """# Cell 6 -- Aggregator (raccoglie tutte le run + tabella sintesi)
import os, json, pandas as pd, numpy as np
from IPython.display import display, Markdown

run_dirs = []
for root, _, files in os.walk(RESULTS_DIR):
    if 'training_log.csv' in files and 'config_snapshot.json' in files:
        run_dirs.append(root)
run_dirs = sorted(run_dirs)
print(f'Run discovered: {len(run_dirs)}')

rows = []
for rd in run_dirs:
    cfg = json.load(open(os.path.join(rd, 'config_snapshot.json')))
    edf = pd.read_csv(os.path.join(rd, 'training_log.csv'))
    if len(edf) == 0: continue
    bi = int(edf['val_total'].idxmin())
    bdf = pd.read_csv(os.path.join(rd, 'training_batch_log.csv'))
    import math
    gn_f = bdf['gn_total_preclip'][bdf['gn_total_preclip'].apply(math.isfinite)]
    row = {
        'tag': cfg['tag'],
        'axis': os.path.basename(os.path.dirname(rd)),
        'n_ep': len(edf),
        'best_ep': bi+1,
        'val_total': float(edf['val_total'].iloc[bi]),
        'val_data':  float(edf['val_data'].iloc[bi]),
        'T_tracking_corr': float(edf.get('val_T_tracking_corr', pd.Series([np.nan])).iloc[bi]),
        'T_intra_corr':    float(edf.get('val_T_intra_corr',   pd.Series([np.nan])).iloc[bi]),
        'v0_pred_best':    float(edf.get('val_v0_pred_mean',   pd.Series([np.nan])).iloc[bi]),
        's0_pred_best':    float(edf.get('val_s0_pred_mean',   pd.Series([np.nan])).iloc[bi]),
        'gn_max_preclip':  float(gn_f.max()) if len(gn_f)>0 else np.nan,
        'lr': float(cfg.get('lr', np.nan)),
        'lambda_T_aux': float(cfg.get('lambda_T_aux', 0.0)),
    }
    rows.append(row)
df = pd.DataFrame(rows).sort_values('T_intra_corr', ascending=False)
df.to_csv(AGGREGATE_CSV, index=False)
print(f'Saved: {AGGREGATE_CSV}')
display(Markdown('## Tabella (ordine: T_intra_corr desc)'))
display(df.round(4))"""


def std_cell_summary_push():
    return """# Cell 7 -- Summary + push aggregator
import os, subprocess, tempfile, pandas as pd
if 'df' not in dir():
    df = pd.read_csv(AGGREGATE_CSV)
print(f'\\n# Run analizzati: {len(df)}')
print(f'# Run con gn_max < 25 (clean): {(df.gn_max_preclip < 25).sum()}/{len(df)}')
print(f'# Run con T_intra > 0.1: {(df.T_intra_corr > 0.1).sum()}/{len(df)}')
print(f'# Run con T_intra > 0.058 (top R27 historic): {(df.T_intra_corr > 0.058).sum()}/{len(df)}')
best = df.sort_values('T_intra_corr', ascending=False).iloc[0]
print(f'\\nBest T_intra: {best.tag} = {best.T_intra_corr:.3f}  (gn_max={best.gn_max_preclip:.2f})')

# Push aggregator
subprocess.run(['git','add', AGGREGATE_CSV], check=False)
msg = f'aggregator: {len(df)} run, best T_intra={best.T_intra_corr:.3f}'
with tempfile.NamedTemporaryFile('w', delete=False, suffix='.txt', encoding='utf-8') as fp:
    fp.write(msg); msg_path = fp.name
r = subprocess.run(['git','diff','--cached','--name-only'], capture_output=True, text=True)
if r.stdout.strip():
    subprocess.run(['git','commit','-F',msg_path], check=True)
    subprocess.run(['git','pull','--no-rebase','--no-edit','origin',BRANCH], check=True)
    subprocess.run(['git','push','origin',BRANCH], check=True)
    print('[OK] aggregator pushato.')
else:
    print('[SKIP] niente da pushare.')
try: os.unlink(msg_path)
except: pass"""


# ============================================================
# Definizione esperimenti per ogni notebook v2
# ============================================================

# R25_v2 — Ablation 5 assi (replica R25 originale, ma su R24F baseline)
R25_V2_EXPERIMENTS = '''EXPERIMENTS = [
    # Baseline replica (sanity check)
    _exp('R25v2_A1_baseline', 'A3 replica sopra R24F baseline', 'BASELINE'),
    # Asse A — Memoria temporale (seq_len, max_delay, bit_shift)
    _exp('R25v2_A2_seq_len_short',   'seq_len=25 (vs 50 baseline)',   'A_memory', seq_len=25),
    _exp('R25v2_A3_seq_len_long',    'seq_len=100',                   'A_memory', seq_len=100),
    _exp('R25v2_A4_delay_long',      'max_delay=18',                  'A_memory', max_delay=18),
    _exp('R25v2_A5_leak_slow',       'bit_shift=5 (slower leak)',     'A_memory', bit_shift=5),
    _exp('R25v2_A6_combo_memory',    'seq_len=100 + delay=18',        'A_memory', seq_len=100, max_delay=18),
    # Asse B — Loss balancing (T_aux)
    _exp('R25v2_B1_T_aux_low',       'lambda_T_aux=0.1',              'B_loss',   lambda_T_aux=0.1),
    _exp('R25v2_B2_T_aux_mid',       'lambda_T_aux=1.0',              'B_loss',   lambda_T_aux=1.0),
    _exp('R25v2_B3_T_aux_high',      'lambda_T_aux=10.0',             'B_loss',   lambda_T_aux=10.0),
    # Asse C — Spike rate regularization
    _exp('R25v2_C1_sr_off',          'lambda_sr=0 (no regularization)', 'C_spike_rate', lambda_sr=0.0),
    _exp('R25v2_C2_sr_high',         'lambda_sr=5.0',                 'C_spike_rate', lambda_sr=5.0),
    _exp('R25v2_C3_sr_very_high',    'lambda_sr=20.0',                'C_spike_rate', lambda_sr=20.0),
    # Asse D — Capacity (hidden_size)
    _exp('R25v2_D1_small',           'hidden=16',                     'D_capacity', hidden_size=16, rank=4),
    _exp('R25v2_D2_mid',             'hidden=64',                     'D_capacity', hidden_size=64, rank=16),
    _exp('R25v2_D3_large',           'hidden=128',                    'D_capacity', hidden_size=128, rank=32),
    # Asse E — Training duration
    _exp('R25v2_E1_short',           'epochs=5',                      'E_duration', epochs=5),
    _exp('R25v2_E2_long',            'epochs=20',                     'E_duration', epochs=20),
    _exp('R25v2_E3_very_long',       'epochs=30',                     'E_duration', epochs=30),
]'''


R26_V2_EXPERIMENTS = '''EXPERIMENTS = [
    # F0 sanity
    _exp('R26v2_F0_baseline_replica', 'R24F baseline replica', 'BASELINE'),
    # F1 TRIPLE win (A4+B1+C1: delay18 + T_aux=0.1 + sr=0)
    _exp('R26v2_F1_TRIPLE_win', 'A4+B1+C1 fusion', 'F_fusion',
         max_delay=18, lambda_T_aux=0.1, lambda_sr=0.0),
    # F2 A4+B1 (no sr=0)
    _exp('R26v2_F2_A4_B1', 'A4+B1 (no sr_off)', 'F_fusion',
         max_delay=18, lambda_T_aux=0.1),
    # F3 B1+C1 (no memoria)
    _exp('R26v2_F3_B1_C1', 'B1+C1 (no memory)', 'F_fusion',
         lambda_T_aux=0.1, lambda_sr=0.0),
    # F4 A4+C1 (no T_aux)
    _exp('R26v2_F4_A4_C1', 'A4+C1 (no T_aux)', 'F_fusion',
         max_delay=18, lambda_sr=0.0),
    # F5 TRIPLE + short epochs
    _exp('R26v2_F5_TRIPLE_short', 'F1 + early stop epochs=5', 'F_fusion',
         max_delay=18, lambda_T_aux=0.1, lambda_sr=0.0, epochs=5),
]'''


R28_V2_EXPERIMENTS = '''EXPERIMENTS = [
    _exp('R28v2_A0_baseline_lr05', 'R24F baseline replica (sanity)',
         'A_d0'),  # d0=1e-6 default
    _exp('R28v2_A1_d0_1e-5', 'd0=1e-5 fix konstmish Issue #27',
         'A_d0', d0=1e-5),
    _exp('R28v2_B1_steps_300', 'max_steps=300 (3x budget)',
         'B_steps', max_steps_per_epoch=300),
    _exp('R28v2_C1_d0_steps_combo', 'd0=1e-5 + steps=300',
         'C_combo', d0=1e-5, max_steps_per_epoch=300),
    _exp('R28v2_D1_warm_restart', 'cosine warm restart T0=5 + d0 + steps',
         'D_warm_restart', d0=1e-5, max_steps_per_epoch=300, scheduler='cosine'),
]'''


R29_V2_EXPERIMENTS = '''EXPERIMENTS = [
    _exp('R29v2_E0_baseline', 'R24F baseline replica', 'E_control'),
    _exp('R29v2_E1_no_po2', 'No Po2 quantization', 'E_control', po2_enabled=0),
    _exp('R29v2_A1_init_shift', 'DEC-3 init bias shift isolated', 'A_init', init_bias_shift=1),
    _exp('R29v2_B1_tau3to1_lin', 'tau 3->1 lineare', 'B_tau', tau_init=3.0, tau_final=1.0, tau_schedule='linear'),
    _exp('R29v2_B2_tau5to1_lin', 'tau 5->1 lineare', 'B_tau', tau_init=5.0, tau_final=1.0, tau_schedule='linear'),
    _exp('R29v2_B3_tau10to1_lin','tau 10->1 lineare', 'B_tau', tau_init=10.0, tau_final=1.0, tau_schedule='linear'),
    _exp('R29v2_B4_tau5to1_exp', 'tau 5->1 esponenziale', 'B_tau', tau_init=5.0, tau_final=1.0, tau_schedule='exp'),
    _exp('R29v2_C1_init_tau5',  'init_shift + tau 5->1', 'C_combo', init_bias_shift=1, tau_init=5.0, tau_final=1.0, tau_schedule='linear'),
    _exp('R29v2_C2_init_tau10', 'init_shift + tau 10->1', 'C_combo', init_bias_shift=1, tau_init=10.0, tau_final=1.0, tau_schedule='linear'),
    _exp('R29v2_C3_init_per_channel', 'init + per-channel tau', 'C_combo',
         init_bias_shift=1, tau_per_channel='10.0,3.0,10.0,3.0,3.0', tau_schedule='const'),
    _exp('R29v2_D1_C1_epochs20', 'C1 prolungato 20 ep', 'D_long',
         init_bias_shift=1, tau_init=5.0, tau_final=1.0, tau_schedule='linear', epochs=20),
    _exp('R29v2_D2_C2_epochs20', 'C2 prolungato 20 ep', 'D_long',
         init_bias_shift=1, tau_init=10.0, tau_final=1.0, tau_schedule='linear', epochs=20),
]'''


R30_EXPERIMENTS = '''EXPERIMENTS = [
    # Baseline R24F (sanity, no aux supervision)
    _exp('R30_A0_baseline', 'R24F baseline (no aux)', 'A_isolated'),
    # Asse A — supervisione isolata per canale (lambda=0.1 cadauno)
    _exp('R30_A1_v0_aux', 'lambda_v0_aux=0.1 isolato', 'A_isolated', lambda_v0_aux=0.1),
    _exp('R30_A2_s0_aux', 'lambda_s0_aux=0.1 isolato (top candidato CV 55%)', 'A_isolated', lambda_s0_aux=0.1),
    _exp('R30_A3_a_aux',  'lambda_a_aux=0.1 isolato', 'A_isolated', lambda_a_aux=0.1),
    _exp('R30_A4_b_aux',  'lambda_b_aux=0.1 isolato', 'A_isolated', lambda_b_aux=0.1),
    # Asse B — full stack (tutti i 4 canali)
    _exp('R30_B1_full_aux_lam01', 'tutti 4 lambdas=0.1', 'B_full',
         lambda_v0_aux=0.1, lambda_s0_aux=0.1, lambda_a_aux=0.1, lambda_b_aux=0.1),
    _exp('R30_B2_full_aux_lam05', 'tutti 4 lambdas=0.5', 'B_full',
         lambda_v0_aux=0.5, lambda_s0_aux=0.5, lambda_a_aux=0.5, lambda_b_aux=0.5),
    # Asse C — full + T_aux (mossa massima: 5 channel supervisione)
    _exp('R30_C1_full_aux_plus_T', 'full + lambda_T_aux=0.1', 'C_full_plus_T',
         lambda_v0_aux=0.1, lambda_s0_aux=0.1, lambda_a_aux=0.1, lambda_b_aux=0.1,
         lambda_T_aux=0.1),
]'''


# ============================================================
# Build notebooks
# ============================================================

NOTEBOOKS = [
    ('Prodigy_Ablation_Study_R25_v2.ipynb', 'R25_v2 Ablation',
     'results/Prodigy_Study/R25_Ablation_v2', 'r25v2_msg',
     'R25 Ablation v2 (su R24F baseline)', R25_V2_EXPERIMENTS,
     '5 assi su R24F baseline (lr=0.5 stabile). 18 esperimenti: A_memory, B_loss, C_spike_rate, D_capacity, E_duration.'),
    ('Prodigy_Fusion_Study_R26_v2.ipynb', 'R26_v2 Fusion',
     'results/Prodigy_Study/R26_Fusion_v2', 'r26v2_msg',
     'R26 Fusion v2 (su R24F baseline)', R26_V2_EXPERIMENTS,
     '6 esperimenti: baseline replica + 4 fusion controlli + F5 short.'),
    ('Prodigy_Tuning_R28_v2.ipynb', 'R28_v2 ProdigyTuning',
     'results/Prodigy_Study/R28_ProdigyTuning_v2', 'r28v2_msg',
     'R28 Prodigy tuning v2 (su R24F baseline)', R28_V2_EXPERIMENTS,
     '5 esperimenti: d0 fix, step budget 3x, warm restart, su lr=0.5 stable.'),
    ('Prodigy_DecoderFix_R29_v2.ipynb', 'R29_v2 DecoderFix',
     'results/Prodigy_Study/R29_DecoderFix_v2', 'r29v2_msg',
     'R29 Decoder fix v2 (su R24F baseline)', R29_V2_EXPERIMENTS,
     '12 esperimenti: init_shift + tau anneal + combo + long. Su baseline pulita.'),
    ('Prodigy_Identifiability_R30.ipynb', 'R30 Identifiability',
     'results/Prodigy_Study/R30_Identifiability', 'r30_msg',
     'R30 Identifiability ID-1 (4 lambdas su v0/s0/a/b)', R30_EXPERIMENTS,
     '9 esperimenti: 4 isolated + 2 full + 1 combo full+T_aux. NUOVO sblocco rank.'),
]


def build_notebook(filename, study_name, results_dir, msg_name, desc_md, exp_code, extended_desc):
    md_intro = f"""# {study_name} — ricalibrato su R24F_mixed_lr0.5_V08

## Contesto

Tutti i baseline pre-2026-06-12 (R25_B1, R25_A3, R28_A0, R29_E0) avevano gradienti `gn_total_preclip` ∈ [10⁵, 10¹⁷] mascherati dal `clip_grad_norm_(1.0)`. R24F_mixed_lr0.5_V08 è l'UNICO setup post-fix CLEAN (gn_max 21.8). Tutti i v2 partono da quel baseline.

## Setup chiave

- Optimizer: Prodigy `lr=0.5` (NON 1.0)
- Scheduler: cosine_no_restart
- seq_len: 50 (NON 100)
- λ_T_aux: 0.0 nel baseline (varianti testate)
- Explosion guard ATTIVO: `--max_epoch_explosion_streak 2 --epoch_explosion_threshold 100`

## Sweep

{extended_desc}

## Output

`{results_dir}/<axis>/<tag>/`"""

    cells = [
        make_cell('markdown', md_intro, 'cell-0'),
        make_cell('code', std_cell_1_bootstrap(study_name, results_dir, msg_name), 'cell-1'),
        make_cell('code', f"# Cell 2 -- {study_name} experiments\n{COMMON_BASE_CONFIG_CODE}\n\n{exp_code}\n\nprint(f'EXPERIMENTS: {{len(EXPERIMENTS)}}')\nfor e in EXPERIMENTS:\n    print(f\"  [{{e['axis']:<14}}] {{e['tag']:<32}} -- {{e.get('desc','')}}\")", 'cell-2'),
        make_cell('code', std_cell_cache_check(), 'cell-3'),
        make_cell('code', std_cell_preflight(), 'cell-4'),
        make_cell('code', std_cell_sweep_runner(study_name), 'cell-5'),
        make_cell('code', std_cell_aggregator(), 'cell-6'),
        make_cell('code', std_cell_summary_push(), 'cell-7'),
    ]
    nb = make_notebook(cells)
    out = os.path.join(ROOT, filename)
    with open(out, 'w', encoding='utf-8') as fp:
        json.dump(nb, fp, indent=1, ensure_ascii=False)
    print(f'  Created: {filename} ({len(cells)} cells)')
    return out


# Audit R27 v2 has different structure (it's a script call, not a sweep)
def build_audit_r27_v2():
    md_intro = """# R27_v2 — Observability Audit dei v2 (R25_v2 + R26_v2 + R28_v2 + R29_v2)

Audit retro-attivo dei run v2 con metriche estese (T_intra_corr + rank_effective + cond_number). Stessa logica di R27 originale ma su run con baseline R24F stabile (gn_max < 25).

Output: `results/Prodigy_Study/R27_Audit_v2/audit_summary.csv` + JSON per run."""

    bootstrap = """# Cell 1 -- Bootstrap + GLOBALS
import sys, os, subprocess
RESULTS_DIR = 'results/Prodigy_Study/R27_Audit_v2'
OUTPUT_CSV = f'{RESULTS_DIR}/audit_summary.csv'
BRANCH = 'Prodigy_Deep_Study'
os.makedirs(RESULTS_DIR, exist_ok=True)
sys.path.insert(0, '.')
from scripts.audit_checkpoints import discover_runs, find_checkpoint
br = subprocess.run(['git','branch','--show-current'], capture_output=True, text=True).stdout.strip()
assert br == BRANCH
print(f'  [OK] branch={br}')"""

    run_audit = """# Cell 2 -- Audit (idempotente: skip se CSV con righe gia' esistente)
import os, pandas as pd, subprocess, sys
FORCE_RERUN = False
if os.path.isfile(OUTPUT_CSV) and not FORCE_RERUN:
    try:
        _df = pd.read_csv(OUTPUT_CSV)
        if len(_df) > 0:
            print(f'[SKIP] CSV gia\\' esistente con {len(_df)} righe. FORCE_RERUN=True per riprocessare.')
            skip = True
        else: skip = False
    except: skip = False
else:
    skip = False
if not skip:
    cmd = [sys.executable, '-u', 'scripts/audit_checkpoints.py',
           '--results_root', 'results/Prodigy_Study',
           '--output_csv', OUTPUT_CSV,
           '--pattern', r'^R(25v2|26v2|28v2|29v2)_',
           '--device', 'cpu']
    print(f'\\nRunning: {" ".join(cmd)}\\n')
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace', bufsize=1)
    for line in proc.stdout: print(line, end='', flush=True)
    proc.wait()
    assert proc.returncode == 0
df = pd.read_csv(OUTPUT_CSV)
print(f'\\n[DONE] {len(df)} run auditati.')"""

    summary = """# Cell 3 -- Summary
import pandas as pd
df = pd.read_csv(OUTPUT_CSV)
print(f'Tot: {len(df)}')
print(f'Best T_intra: {df.sort_values("val_val_T_intra_corr", ascending=False).iloc[0]["tag"]}')
print(f'Best val_data: {df.sort_values("val_data", ascending=True).iloc[0]["tag"]}')
print(df.sort_values('val_val_T_intra_corr', ascending=False)[
    ['tag','val_data','val_val_T_tracking_corr','val_val_T_intra_corr','rank_effective']
].round(4).to_string(index=False))"""

    cells = [
        make_cell('markdown', md_intro, 'cell-0'),
        make_cell('code', bootstrap, 'cell-1'),
        make_cell('code', run_audit, 'cell-2'),
        make_cell('code', summary, 'cell-3'),
    ]
    nb = make_notebook(cells)
    out = os.path.join(ROOT, 'Prodigy_Audit_R27_v2.ipynb')
    with open(out, 'w', encoding='utf-8') as fp:
        json.dump(nb, fp, indent=1, ensure_ascii=False)
    print(f'  Created: Prodigy_Audit_R27_v2.ipynb (4 cells)')


# MASTER orchestrator
def build_master():
    md_intro = """# Prodigy_Master_RERUN_v2 — Orchestrator finale

Esegue in sequenza i 6 sub-notebook v2 (R25→R26→R27→R28→R29→R30) su Azure. Ogni sub-notebook è idempotente: skippa run già completati. In caso di kernel timeout, basta rilanciare Cell 2.

## Sub-notebook eseguiti

1. `Prodigy_Ablation_Study_R25_v2.ipynb` (18 run)
2. `Prodigy_Fusion_Study_R26_v2.ipynb` (6 run)
3. `Prodigy_Audit_R27_v2.ipynb` (audit di v2 sopra)
4. `Prodigy_Tuning_R28_v2.ipynb` (5 run)
5. `Prodigy_DecoderFix_R29_v2.ipynb` (12 run)
6. `Prodigy_Identifiability_R30.ipynb` (9 run)

Totale: 50 run + 1 audit, ~5-8h Azure CPU.

## Meta-analisi finale

Cell 3 consolida i 6 aggregator CSV e fornisce verdetto su:
- Quale run ha T_intra > 0.1 (sblocco rank-collapse)?
- Quale combinazione (ablation × decoder × identifiability) è il nuovo champion?"""

    bootstrap = """# Cell 1 -- ENV check + sub-notebook list
import sys, os, subprocess
BRANCH = 'Prodigy_Deep_Study'
SUB_NOTEBOOKS = [
    'Prodigy_Ablation_Study_R25_v2.ipynb',
    'Prodigy_Fusion_Study_R26_v2.ipynb',
    'Prodigy_Audit_R27_v2.ipynb',
    'Prodigy_Tuning_R28_v2.ipynb',
    'Prodigy_DecoderFix_R29_v2.ipynb',
    'Prodigy_Identifiability_R30.ipynb',
]
for nb in SUB_NOTEBOOKS:
    assert os.path.isfile(nb), f'MISSING: {nb}'
print(f'  [OK] {len(SUB_NOTEBOOKS)} sub-notebook presenti')
br = subprocess.run(['git','branch','--show-current'], capture_output=True, text=True).stdout.strip()
assert br == BRANCH
print(f'  [OK] branch={br}')"""

    runner = """# Cell 2 -- Esegue i 6 sub-notebook in sequenza (via nbconvert)
import subprocess, sys, time, os

t_total = time.time()
for nb in SUB_NOTEBOOKS:
    print(f'\\n{"="*78}\\nEXECUTING: {nb}\\n{"="*78}')
    t0 = time.time()
    cmd = [sys.executable, '-m', 'jupyter', 'nbconvert', '--to', 'notebook',
           '--execute', '--inplace', nb,
           '--ExecutePreprocessor.timeout=-1',
           '--ExecutePreprocessor.kernel_name=python3']
    r = subprocess.run(cmd, capture_output=False)
    el = time.time() - t0
    if r.returncode != 0:
        print(f'\\n[FAIL] {nb} exit={r.returncode}. Verifica output e rilancia.')
        break
    print(f'\\n[OK] {nb} done in {el/60:.1f} min')

print(f'\\n{"="*78}\\nMASTER RERUN done in {(time.time()-t_total)/60:.0f} min')"""

    meta_analysis = """# Cell 3 -- META-ANALISI cross-studies + verdetto finale
import os, pandas as pd, numpy as np
from IPython.display import display, Markdown

STUDIES = [
    ('R25 Ablation v2',    'results/Prodigy_Study/R25_Ablation_v2/_aggregate.csv'),
    ('R26 Fusion v2',      'results/Prodigy_Study/R26_Fusion_v2/_aggregate.csv'),
    ('R28 ProdigyTuning v2','results/Prodigy_Study/R28_ProdigyTuning_v2/_aggregate.csv'),
    ('R29 DecoderFix v2',  'results/Prodigy_Study/R29_DecoderFix_v2/_aggregate.csv'),
    ('R30 Identifiability','results/Prodigy_Study/R30_Identifiability/_aggregate.csv'),
]

all_dfs = []
for name, p in STUDIES:
    if not os.path.isfile(p):
        print(f'  [MISSING] {p}')
        continue
    df = pd.read_csv(p)
    df['study'] = name
    all_dfs.append(df)
big = pd.concat(all_dfs, ignore_index=True)
print(f'Total run analizzati: {len(big)}')
print(f'Clean runs (gn_max < 25): {(big.gn_max_preclip < 25).sum()}/{len(big)}')

display(Markdown('## Top 10 cross-studies per T_intra_corr'))
top10 = big.sort_values('T_intra_corr', ascending=False).head(10)
display(top10[['study','tag','val_data','T_tracking_corr','T_intra_corr','gn_max_preclip']].round(4))

display(Markdown('## Verdetto sblocco T-tracking'))
n_intra_strong = (big.T_intra_corr > 0.10).sum()
n_intra_med    = (big.T_intra_corr > 0.058).sum()
print(f'Run con T_intra > 0.10: {n_intra_strong}')
print(f'Run con T_intra > 0.058 (top R27 historic): {n_intra_med}')
if n_intra_strong > 0:
    best = big.sort_values('T_intra_corr', ascending=False).iloc[0]
    display(Markdown(f'### ✅ SBLOCCO T-tracking: {best.study} {best.tag} = T_intra {best.T_intra_corr:.3f}. NUOVO CHAMPION.'))
elif n_intra_med > 0:
    display(Markdown(f'### ⚠ Miglioramento moderato. {n_intra_med} run > 0.058 (top historic).'))
else:
    display(Markdown('### ❌ Nessun sblocco. Identifiability rimane problema strutturale -- forse 864p insufficiente.'))

# Save consolidated
big.to_csv('results/Prodigy_Study/_FINAL_v2_consolidated.csv', index=False)
print(f'\\nSalvato: results/Prodigy_Study/_FINAL_v2_consolidated.csv')"""

    cells = [
        make_cell('markdown', md_intro, 'cell-0'),
        make_cell('code', bootstrap, 'cell-1'),
        make_cell('code', runner, 'cell-2'),
        make_cell('code', meta_analysis, 'cell-3'),
    ]
    nb = make_notebook(cells)
    out = os.path.join(ROOT, 'Prodigy_Master_RERUN_v2.ipynb')
    with open(out, 'w', encoding='utf-8') as fp:
        json.dump(nb, fp, indent=1, ensure_ascii=False)
    print(f'  Created: Prodigy_Master_RERUN_v2.ipynb (4 cells)')


def main():
    print(f'Building 5 v2 sweep notebooks + 1 audit + 1 master in {ROOT}/')
    for nb_data in NOTEBOOKS:
        build_notebook(*nb_data)
    build_audit_r27_v2()
    build_master()
    print(f'\\nDONE: 7 notebooks generated.')


if __name__ == '__main__':
    main()
