"""
sweep_optimizers.py -- Sweep optimizer 9 config × 4 training methods = 36 run
==============================================================================

Eseguito dopo grid 2x2 (vedi document/EVENTPROP_GRID2X2.md).
Obiettivo: prova DEFINITIVA che EventProp non supera BPTT su val_data,
neanche con sweep optimizer esteso (AdamW multi-lr, Adam, Lion, Prodigy
multi-d_coef compreso "freno" lr=1.0/d_coef<1 e "low init" lr<1.0).

Setup (matching grid 2x2):
  --epochs 5 --max_steps_per_epoch 190 --batch_size 8 --val_batch_size 64
  --seq_len 50 --scheduler none
  --scenario_mix highway --cut_in_ratio 0.0 --cf_hidden_size 32 --cf_rank 8
  --noise_scale 0.0 --po2_enabled 1
  --lambda_data 1.0 (puro) --max_inf_streak 99999 --early_stop_patience 0

Output: checkpoints/SW_<method>_<opt_label>/ per ogni run.

Tempi stimati (locale, CPU):
  - baseline (ALIF+BPTT):       224 s/ep x 5 = ~18 min/run
  - bptt_lif_simple:               7 s/ep x 5 = ~35 s/run
  - eventprop_lif_simple:          8 s/ep x 5 = ~40 s/run
  - eventprop_alif_full:         165 s/ep x 5 = ~14 min/run
  TOTALE: 9 * (18 + 14) min + 9 * (35+40) s = 288 min + 11 min = ~5h

Eseguire:
  python sweep_optimizers.py [--methods baseline,eventprop_alif_full]
  python sweep_optimizers.py --skip-existing  # salta run completati
"""

import argparse
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))

# ===============================================================
# Optimizer configs (9 totali — copertura ragionevole)
# ===============================================================
# Format: (label, optimizer, lr, prodigy_d_coef)
# prodigy_d_coef si applica SOLO se optimizer='prodigy', altrimenti ignorato.

OPTIMIZER_CONFIGS = [
    # ── AdamW multi-lr ─────────────────────────────────────────
    ('adamw_lr5e-4', 'adamw', 5e-4, 1.0),    # lower
    ('adamw_lr1e-3', 'adamw', 1e-3, 1.0),    # mid-low
    ('adamw_lr2e-3', 'adamw', 2e-3, 1.0),    # reference (grid 2x2 default)
    ('adamw_lr5e-3', 'adamw', 5e-3, 1.0),    # higher
    # ── Adam (no weight decay) ─────────────────────────────────
    ('adam_lr2e-3',  'adam',  2e-3, 1.0),
    # ── Lion (sign-based, vuole lr piccola) ────────────────────
    ('lion_lr1e-4',  'lion',  1e-4, 1.0),
    # ── Prodigy: canonico lr=1.0 + freno via d_coef ────────────
    ('prodigy_lr1_d10', 'prodigy', 1.0, 1.0),     # canonical, no brake
    ('prodigy_lr1_d05', 'prodigy', 1.0, 0.5),     # mild brake
    ('prodigy_lr1_d03', 'prodigy', 1.0, 0.3),     # medium brake
    ('prodigy_lr1_d01', 'prodigy', 1.0, 0.1),     # strong brake
    # ── Prodigy: lr ridotta + d_coef pieno ─────────────────────
    ('prodigy_lr01_d10', 'prodigy', 0.1, 1.0),    # low init (STEP 2C best)
]
# Nota: 11 configs (>9 originali). Lo studio sara' piu' completo.

# ===============================================================
# Training methods (4 — il grid 2x2)
# ===============================================================
TRAINING_METHODS = ['baseline', 'bptt_lif_simple',
                    'eventprop_lif_simple', 'eventprop_alif_full']


# ===============================================================
# Common CLI args (matching grid 2x2)
# ===============================================================
def _build_cli(method, opt_label, optimizer, lr, prodigy_d_coef):
    tag = f'SW_{method}_{opt_label}'
    args = [
        sys.executable, 'train.py',
        '--training_method',     method,
        '--epochs',              '5',
        '--max_steps_per_epoch', '190',
        '--batch_size',          '8',
        '--val_batch_size',      '64',
        '--seq_len',             '50',
        '--scheduler',           'none',
        '--lr',                  str(lr),
        '--optimizer',           optimizer,
        '--prodigy_d_coef',      str(prodigy_d_coef),
        '--scenario_mix',        'highway',
        '--cut_in_ratio',        '0.0',
        '--cf_hidden_size',      '32',
        '--cf_rank',             '8',
        '--noise_scale',         '0.0',
        '--po2_enabled',         '1',
        '--lambda_data',         '1.0',
        '--lambda_phys',         '0.0',
        '--lambda_ou',           '0.0',
        '--lambda_bc',           '0.0',
        '--lambda_sr',           '0.0',
        '--data_cache',          'data/cache_1500_highway_cut0.0_ou0.0.pt',
        '--n_train',             '1500',
        '--n_val',               '300',
        '--max_inf_streak',      '99999',
        '--early_stop_patience', '0',
        '--tag',                 tag,
    ]
    return args, tag


def main():
    p = argparse.ArgumentParser(description='Sweep optimizer per grid 2x2')
    p.add_argument('--methods', type=str, default=','.join(TRAINING_METHODS),
                   help=f'Subset di metodi (comma-sep). Default: tutti i 4.')
    p.add_argument('--configs', type=str, default='all',
                   help='Subset di optimizer config (comma-sep label). Default: all.')
    p.add_argument('--skip-existing', action='store_true',
                   help='Salta run con checkpoints/<tag>/training_log.csv esistente.')
    p.add_argument('--dry-run', action='store_true',
                   help='Stampa solo i CLI, non esegue.')
    args = p.parse_args()

    methods = [m.strip() for m in args.methods.split(',') if m.strip()]
    for m in methods:
        if m not in TRAINING_METHODS:
            print(f'[ERR] method "{m}" non valido. Use: {TRAINING_METHODS}')
            sys.exit(1)

    configs_to_run = (OPTIMIZER_CONFIGS if args.configs == 'all'
                      else [c for c in OPTIMIZER_CONFIGS
                            if c[0] in args.configs.split(',')])

    total = len(methods) * len(configs_to_run)
    print(f'='*72)
    print(f'SWEEP OPTIMIZERS — {len(methods)} methods x {len(configs_to_run)} configs = {total} run')
    print(f'='*72)
    print(f'Methods: {methods}')
    print(f'Configs: {[c[0] for c in configs_to_run]}')
    print(f'Skip existing: {args.skip_existing}  Dry run: {args.dry_run}')

    # Stima tempo (per run, in secondi)
    time_estimates = {
        'baseline':              18*60,   # ~18 min
        'bptt_lif_simple':       40,
        'eventprop_lif_simple':  45,
        'eventprop_alif_full':   14*60,   # ~14 min
    }
    total_seconds = sum(time_estimates.get(m, 600) * len(configs_to_run)
                        for m in methods)
    print(f'\nStima tempo: {total_seconds/3600:.1f} h ({total_seconds/60:.0f} min)')
    print(f'='*72)

    if args.dry_run:
        print('\n[DRY RUN] commands that WOULD run:\n')
        for m in methods:
            for label, opt, lr, dc in configs_to_run:
                cli, tag = _build_cli(m, label, opt, lr, dc)
                print(f'# tag={tag}')
                print('  ' + ' '.join(cli[2:]))
                print()
        return

    results = []
    t_start = time.time()
    run_idx = 0

    for m in methods:
        for label, opt, lr, dc in configs_to_run:
            run_idx += 1
            cli, tag = _build_cli(m, label, opt, lr, dc)
            ckpt = os.path.join(_HERE, 'checkpoints', tag, 'training_log.csv')

            if args.skip_existing and os.path.isfile(ckpt):
                print(f'\n[{run_idx}/{total}] SKIP {tag} (already exists)')
                results.append({'tag': tag, 'method': m, 'opt': label,
                                'status': 'skipped', 'elapsed': 0.0})
                continue

            print(f'\n{"="*72}')
            print(f'[{run_idx}/{total}] {tag}')
            print(f'   method={m}  optimizer={opt}  lr={lr}  d_coef={dc}')
            print(f'{"="*72}')

            t0 = time.time()
            res = subprocess.run(cli, capture_output=False)
            elapsed = time.time() - t0
            status = 'ok' if res.returncode == 0 else f'fail({res.returncode})'

            print(f'\n[{run_idx}/{total}] {tag} -> {status} in {elapsed/60:.1f} min')
            elapsed_total = time.time() - t_start
            eta_min = (elapsed_total / run_idx) * (total - run_idx) / 60
            print(f'   total elapsed: {elapsed_total/60:.0f} min   ETA: {eta_min:.0f} min')

            results.append({'tag': tag, 'method': m, 'opt': label,
                            'status': status, 'elapsed': elapsed})

    # ── Final summary ────────────────────────────────────
    print(f'\n{"="*72}')
    print(f'SWEEP COMPLETATO in {(time.time()-t_start)/60:.0f} min')
    print(f'{"="*72}')
    n_ok   = sum(1 for r in results if r['status'] == 'ok')
    n_fail = sum(1 for r in results if r['status'].startswith('fail'))
    n_skip = sum(1 for r in results if r['status'] == 'skipped')
    print(f'OK: {n_ok}  FAIL: {n_fail}  SKIP: {n_skip}')

    # CSV summary
    summary_path = os.path.join(_HERE, 'sweep_optimizers_results.csv')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write('tag,method,optimizer,status,elapsed_min\n')
        for r in results:
            f.write(f'{r["tag"]},{r["method"]},{r["opt"]},'
                    f'{r["status"]},{r["elapsed"]/60:.2f}\n')
    print(f'Summary CSV: {summary_path}')


if __name__ == '__main__':
    main()
