"""R27 — Audit retro-attivo dei checkpoint R25 + R26 con metriche estese.

Per ogni run dir trovata sotto `--results_root`:
  1. legge `config_snapshot.json` per ricostruire il modello (hidden_size, rank, max_delay, bit_shift)
  2. carica `checkpoints/<tag>/best_model.pt` (Azure NFS path)
  3. rilancia val_epoch con metriche estese:
       - val_T_tracking_corr (gia' R25, ricomputata per coerenza)
       - val_T_intra_corr    (NEW R27, Pearson mean-removed per-sample)
       - rank empirico Cov(decoded_params) + condition number
       - per-channel mean + intra_std (gia' R25)
  4. dumpa `<run_dir>/audit_metrics.json`
  5. aggrega tutto in `--output_csv` con 1 riga per run

Uso:
  python scripts/audit_checkpoints.py \
      --results_root results/Prodigy_Study \
      --output_csv results/Prodigy_Study/Audit_R27/audit_summary.csv \
      [--limit N]    # opzionale, audita solo i primi N (debug)

Backward-compat: script standalone, no side-effect sui run originali (write-once
JSON nuovo per run + nuovo CSV aggregato). Non modifica training_log.csv ne'
training_batch_log.csv.

R27 design choice: il dataset per la val viene rigenerato cache-key-coherent
con il config_snapshot di OGNI run. Questo evita di confrontare runs su
distribuzioni diverse di scenario_mix / cut_in_ratio / noise_scale.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, TensorDataset

# Path setup: lo script vive in scripts/, root e' una cartella sopra
_THIS = Path(__file__).resolve()
_ROOT = _THIS.parent.parent
sys.path.insert(0, str(_ROOT))

from core.network import CF_FSNN_Net
from data.generator import generate_dataset, parse_scenario_mix
from train import val_epoch, pinn_loss  # riusiamo val_epoch (R27-extended)
from config import (
    CF_HIDDEN_SIZE, CF_RANK, CF_MAX_DELAY,
    LAMBDA_DATA, LAMBDA_PHYS, LAMBDA_OU, LAMBDA_BC,
)


# ===========================================================
# Helper — discovery
# ===========================================================
def discover_runs(results_root: Path) -> list[Path]:
    """Walk results_root e ritorna le cartelle contenenti training_log.csv +
    config_snapshot.json. Skippa quelle senza entrambi.
    """
    found = []
    for root, _, files in os.walk(results_root):
        if 'training_log.csv' in files and 'config_snapshot.json' in files:
            found.append(Path(root))
    return sorted(found)


def find_checkpoint(tag: str, results_root: Path) -> Optional[Path]:
    """Cerca best_model.pt nei posti canonici (Azure: checkpoints/<tag>/).
    Ritorna Path se trovato, None altrimenti.
    """
    candidates = [
        _ROOT / 'checkpoints' / tag / 'best_model.pt',
        results_root / tag / 'best_model.pt',                       # legacy
        results_root.parent / 'checkpoints' / tag / 'best_model.pt',
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


# ===========================================================
# Helper — dataset
# ===========================================================
def build_val_loader(cfg: dict, device: str, n_val: int = 300, seq_len: int = 50) -> DataLoader:
    """Ricostruisce un val_loader coerente con la config originale del run.
    Usa cache se disponibile, altrimenti genera al volo.
    """
    scenario_mix = cfg.get('scenario_mix', 'highway:0.4,urban:0.3,truck:0.2,mixed:0.1')
    cut_in       = cfg.get('cut_in_ratio', 0.0)
    noise        = cfg.get('noise_scale', 0.0)
    seq_len      = cfg.get('seq_len', seq_len)
    n_val        = cfg.get('n_val', n_val)

    # cache key (mirror del pattern train.py)
    cache_dir = _ROOT / 'data'
    cache_name = f'cache_audit_{n_val}_{scenario_mix.replace(",","_").replace(":","-")}_cut{cut_in}_ou{noise}_seq{seq_len}.pt'
    cache_path = cache_dir / cache_name

    if cache_path.exists():
        x, y, mask = torch.load(cache_path, weights_only=False)
    else:
        mix = parse_scenario_mix(scenario_mix)
        # generate_dataset ritorna list[dict] con keys: 'x', 'y', 'mask', 'params', ...
        # x e y sono GIA' normalizzati (shape (1000, 4) e (1000, 2) per scenario).
        ds = generate_dataset(n_scenarios=n_val, base_seed=12345,
                              scenario_mix=mix, cut_in_ratio=cut_in,
                              noise_scale=noise)
        # Window con seq_len, stride pari a seq_len (no overlap, coerente con train)
        xs, ys, ms = [], [], []
        for sample in ds:
            x_n = sample['x']     # (1000, 4) np.ndarray
            y_p = sample['y']     # (1000, 2)
            m   = sample['mask']  # (1000,)
            n_full = len(x_n) // seq_len
            for i in range(n_full):
                s = i * seq_len
                e = s + seq_len
                xs.append(x_n[s:e]); ys.append(y_p[s:e]); ms.append(m[s:e])
        x = torch.from_numpy(np.stack(xs)).float()
        y = torch.from_numpy(np.stack(ys)).float()
        mask = torch.from_numpy(np.stack(ms)).float()
        cache_dir.mkdir(exist_ok=True)
        torch.save((x, y, mask), cache_path)

    ds = TensorDataset(x.to(device), y.to(device), mask.to(device))
    return DataLoader(ds, batch_size=32, shuffle=False)


# ===========================================================
# Audit core
# ===========================================================
def compute_rank_metrics(model: CF_FSNN_Net, loader: DataLoader, device: str) -> dict:
    """Raccoglie i 5 params decodificati su tutto il val set, calcola:
      - rank empirico (effective rank via singular values, threshold 1% del max)
      - condition number (sv_max / sv_min)
      - eigenvalue spectrum normalizzato
    """
    model.eval()
    all_params = []
    with torch.no_grad():
        for x, y, mask in loader:
            ps, _ = model.forward_sequence_with_stats(x)
            all_params.append(ps.detach().reshape(-1, 5).cpu())
    P = torch.cat(all_params, dim=0).numpy()  # (N_total, 5)
    P_centered = P - P.mean(axis=0, keepdims=True)
    cov = (P_centered.T @ P_centered) / max(P.shape[0] - 1, 1)
    sv = np.linalg.svd(cov, compute_uv=False)
    sv_normed = sv / max(sv[0], 1e-12)
    # Effective rank: numero di singular values > 1% del max
    eff_rank = int((sv_normed > 0.01).sum())
    cond_num = float(sv[0] / max(sv[-1], 1e-12))
    return {
        'rank_effective': eff_rank,
        'rank_threshold_pct': 1.0,
        'cond_number': cond_num,
        'singular_values': [float(s) for s in sv],
        'singular_values_normalized': [float(s) for s in sv_normed],
    }


def audit_single_run(run_dir: Path, results_root: Path, device: str) -> Optional[dict]:
    """Audita un singolo run dir. Ritorna dict o None se non auditabile."""
    cfg_path = run_dir / 'config_snapshot.json'
    cfg = json.loads(cfg_path.read_text())
    tag = cfg.get('tag', run_dir.name)

    ckpt_path = find_checkpoint(tag, results_root)
    if ckpt_path is None:
        print(f"  [SKIP] {tag}: best_model.pt non trovato")
        return None

    # Rebuild model con stessa config
    hs = cfg.get('cf_hidden_size', CF_HIDDEN_SIZE)
    rk = cfg.get('cf_rank', CF_RANK)
    md = cfg.get('cf_max_delay', CF_MAX_DELAY)
    bs = cfg.get('cf_bit_shift', 3)

    model = CF_FSNN_Net(hidden_size=hs, rank=rk, max_delay=md, bit_shift=bs).to(device)
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    model.load_state_dict(ckpt['model_state'])
    model.eval()

    # Val loader
    val_loader = build_val_loader(cfg, device)

    # Re-run val_epoch (R27-extended)
    lam = (cfg.get('lambda_data', LAMBDA_DATA),
           cfg.get('lambda_phys', LAMBDA_PHYS),
           cfg.get('lambda_ou',   LAMBDA_OU),
           cfg.get('lambda_bc',   LAMBDA_BC),
           cfg.get('lambda_sr',   0.0),
           cfg.get('lambda_T_aux', 0.0))
    val_m = val_epoch(model, val_loader, device, lam)

    # Rank metrics
    rank_m = compute_rank_metrics(model, val_loader, device)

    def _rel(p: Path) -> str:
        try:
            return str(p.resolve().relative_to(_ROOT))
        except ValueError:
            return str(p.resolve())
    out = {
        'tag': tag,
        'run_dir': _rel(run_dir),
        'checkpoint': _rel(ckpt_path),
        'ckpt_epoch': int(ckpt.get('epoch', -1)),
        'ckpt_val_loss': float(ckpt.get('val_loss', float('nan'))),
        'val_metrics': {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in val_m.items()},
        'rank_metrics': rank_m,
        'config': {
            'cf_hidden_size': hs, 'cf_rank': rk,
            'cf_max_delay': md, 'cf_bit_shift': bs,
            'lambda_T_aux': cfg.get('lambda_T_aux', 0.0),
            'lambda_sr': cfg.get('lambda_sr', 0.0),
            'scenario_mix': cfg.get('scenario_mix', ''),
            'optimizer': cfg.get('optimizer', ''),
            'epochs': cfg.get('epochs', 0),
        },
        'audited_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    # Dump JSON nel run dir originale
    out_json = run_dir / 'audit_metrics.json'
    out_json.write_text(json.dumps(out, indent=2))
    print(f"  [OK]   {tag}: val_data={val_m['data']:.4f} "
          f"T_corr={val_m['val_T_tracking_corr']:.3f} "
          f"T_intra={val_m['val_T_intra_corr']:.3f} "
          f"rank_eff={rank_m['rank_effective']}/5 "
          f"cond={rank_m['cond_number']:.1e}")
    return out


# ===========================================================
# Aggregator + CLI
# ===========================================================
def flatten_for_csv(audit: dict) -> dict:
    """Appiattisce un audit dict in una riga CSV friendly."""
    row = {
        'tag': audit['tag'],
        'run_dir': audit['run_dir'],
        'ckpt_epoch': audit['ckpt_epoch'],
        'ckpt_val_loss': audit['ckpt_val_loss'],
    }
    row.update({f'val_{k}': v for k, v in audit['val_metrics'].items() if isinstance(v, (int, float))})
    row['rank_effective'] = audit['rank_metrics']['rank_effective']
    row['cond_number']    = audit['rank_metrics']['cond_number']
    for i, sv in enumerate(audit['rank_metrics']['singular_values_normalized']):
        row[f'sv_norm_{i+1}'] = sv
    for k, v in audit['config'].items():
        row[f'cfg_{k}'] = v
    return row


def main():
    p = argparse.ArgumentParser(description='R27 — Audit retro-attivo dei checkpoint R25+R26')
    p.add_argument('--results_root', type=Path, default=_ROOT / 'results' / 'Prodigy_Study')
    p.add_argument('--output_csv', type=Path,
                   default=_ROOT / 'results' / 'Prodigy_Study' / 'Audit_R27' / 'audit_summary.csv')
    p.add_argument('--limit', type=int, default=-1,
                   help='Audita solo i primi N (per debug). -1 = tutti.')
    p.add_argument('--pattern', type=str, default=None,
                   help='Regex sul nome della cartella del run (es. "^R2[5-6]_" per R25+R26 only)')
    p.add_argument('--device', type=str, default='cpu')
    args = p.parse_args()

    runs = discover_runs(args.results_root)
    if args.pattern:
        import re
        rx = re.compile(args.pattern)
        runs = [r for r in runs if rx.search(r.name)]
    if args.limit > 0:
        runs = runs[:args.limit]
    print(f"[R27 Audit] Trovati {len(runs)} run sotto {args.results_root}"
          + (f" (filter: {args.pattern})" if args.pattern else ""))

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for run_dir in runs:
        try:
            audit = audit_single_run(run_dir, args.results_root, args.device)
            if audit is not None:
                rows.append(flatten_for_csv(audit))
        except Exception as e:
            print(f"  [FAIL] {run_dir.name}: {type(e).__name__}: {e}")

    df = pd.DataFrame(rows)
    df.to_csv(args.output_csv, index=False)
    print(f"\n[R27 Audit] {len(df)} run auditati. Output: {args.output_csv}")
    if len(df) > 0:
        print("\nTop 5 per val_T_intra_corr:")
        cols_show = ['tag', 'val_val_data', 'val_val_T_tracking_corr', 'val_val_T_intra_corr', 'rank_effective']
        cols_show = [c for c in cols_show if c in df.columns]
        print(df.sort_values('val_val_T_intra_corr', ascending=False)[cols_show].head().to_string(index=False))


if __name__ == '__main__':
    main()
