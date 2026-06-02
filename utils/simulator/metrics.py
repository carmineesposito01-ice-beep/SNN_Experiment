"""
utils/simulator/metrics.py -- Metriche operative per SimulationResult.

9 metriche organizzate per area:
  - Spaziale: gap_rmse, gap_max_err, pos_cum_err
  - Comfort: jerk_max_pred, jerk_p95_pred
  - Safety: ttc_min_pred (time-to-collision)
  - ML reference: accel_rmse_masked (= val_data semantica per scenario singolo)
  - Per-param: param_rmse[v0,T,s0,a,b] (RMSE predizione vs constants true)
  - Activity: spike_rate_avg
"""

from __future__ import annotations
from typing import List, Dict, Any
import numpy as np
import pandas as pd

from utils.simulator.engine import SimulationResult


# ============================================================
# Helper: numerical safety + masked operations
# ============================================================
_EPS = 1e-6


def _rmse(a: np.ndarray, b: np.ndarray) -> float:
    """RMSE pulito, no mask."""
    diff = (a - b).astype(np.float64)
    return float(np.sqrt(np.mean(diff * diff)))


def _rmse_masked(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    """RMSE con mask binaria (1=incluso, 0=escluso). Replica L_data train.py."""
    m = mask.astype(np.float64)
    diff = (a - b).astype(np.float64)
    sq_err = m * diff * diff
    n_valid = max(m.sum(), 1.0)
    return float(np.sqrt(sq_err.sum() / n_valid + 1e-8))


# ============================================================
# Single-scenario metrics
# ============================================================
def compute_operational_metrics(r: SimulationResult) -> Dict[str, Any]:
    """Computa 9+ metriche operative per uno SimulationResult.

    Returns dict di scalari (compatibili con DataFrame row).
    Tutti i nomi sono prefissati per area (gap_, pos_, jerk_, ttc_, accel_,
    param_, spike_) per leggibilita' nell'aggregato.
    """
    # === Spaziali ===
    gap_diff = r.gap_pred - r.gap_gt
    gap_rmse = _rmse(r.gap_pred, r.gap_gt)
    gap_max_err = float(np.abs(gap_diff).max())
    pos_cum_err = float(abs(r.x_ego_pred[-1] - r.x_ego_gt[-1]))

    # === Comfort (jerk = d(a)/dt) ===
    # jerk_pred[t] = (a_pred[t] - a_pred[t-1]) / DT
    jerk_pred = np.diff(r.a_pred) / r.DT
    jerk_max_pred = float(np.abs(jerk_pred).max()) if len(jerk_pred) > 0 else 0.0
    jerk_p95_pred = float(np.percentile(np.abs(jerk_pred), 95)) if len(jerk_pred) > 0 else 0.0

    # === Safety: TTC (time-to-collision) ===
    # TTC = gap / max(dv, eps_safe) when dv > 0 (avvicinamento)
    # Convention: dv = v_ego - v_lead > 0 means approaching
    # Per il simulatore: usiamo gap_pred (predetto) e dv_obs (osservato dello scenario)
    # Quando dv_obs <= 0 (allontanamento), TTC = +inf
    eps_safe = 0.1  # m/s
    closing = np.where(r.dv_obs > eps_safe, r.dv_obs, np.inf)
    ttc = r.gap_pred / closing
    ttc_valid = ttc[(np.isfinite(ttc)) & (r.gap_pred > 0)]
    ttc_min_pred = float(ttc_valid.min()) if len(ttc_valid) > 0 else float('inf')

    # === ML reference: accel RMSE ===
    # Match val_data semantics: RMSE masked a_pred vs a_gt
    accel_rmse_masked = _rmse_masked(r.a_pred, r.a_gt, r.mask)
    accel_rmse_unmasked = _rmse(r.a_pred, r.a_gt)

    # === Per-param accuracy (predicted seq vs true constant) ===
    # params: [v0, T, s0, a, b], shape (T, 5)
    param_names = ['v0', 'T', 's0', 'a', 'b']
    param_metrics = {}
    for i, name in enumerate(param_names):
        pred = r.params_pred[:, i]
        true_const = r.params_true.get(name, np.nan)
        if np.isnan(true_const):
            param_metrics[f'param_rmse_{name}'] = float('nan')
            param_metrics[f'param_mean_{name}'] = float(pred.mean())
        else:
            true_arr = np.full_like(pred, true_const)
            param_metrics[f'param_rmse_{name}'] = _rmse(pred, true_arr)
            param_metrics[f'param_mean_{name}'] = float(pred.mean())

    # === Activity ===
    spike_rate_avg = float(r.spike_rate.mean())
    spike_rate_p95 = float(np.percentile(r.spike_rate, 95))

    return {
        # ID
        'idx': r.idx,
        'scenario_type': r.scenario_type,
        'is_cut_in': r.is_cut_in,
        # Spaziali
        'gap_rmse_m':       gap_rmse,
        'gap_max_err_m':    gap_max_err,
        'pos_cum_err_m':    pos_cum_err,
        # Comfort
        'jerk_max_pred':    jerk_max_pred,
        'jerk_p95_pred':    jerk_p95_pred,
        # Safety
        'ttc_min_pred_s':   ttc_min_pred,
        # ML reference
        'accel_rmse_masked':   accel_rmse_masked,   # = val_data semantics
        'accel_rmse_unmasked': accel_rmse_unmasked,
        # Per-param
        **param_metrics,
        # Activity
        'spike_rate_avg':   spike_rate_avg,
        'spike_rate_p95':   spike_rate_p95,
    }


# ============================================================
# Aggregation across many scenarios
# ============================================================
def aggregate_metrics(metrics_list: List[Dict[str, Any]]) -> pd.DataFrame:
    """Aggrega metriche di una lista di SimulationResult.

    Returns DataFrame summary:
      - Overall: 1 riga con median/mean/std di ogni metric
      - Per scenario_type: 1 riga per tipo con stesse aggregazioni

    Le metric per-param vengono incluse ma solo come 'param_rmse_*_mean'.
    """
    if not metrics_list:
        return pd.DataFrame()
    df = pd.DataFrame(metrics_list)

    # Metric numeriche (escludi ID e categorical)
    skip_cols = {'idx', 'scenario_type', 'is_cut_in'}
    numeric_cols = [c for c in df.columns if c not in skip_cols]
    # Anche escludi non-numeric (es. NaN-only)
    numeric_cols = [c for c in numeric_cols if pd.api.types.is_numeric_dtype(df[c])]

    # Aggregati overall + per scenario_type
    summary_rows = []

    # Overall (all scenarios)
    overall = {'group': 'overall', 'count': len(df)}
    for c in numeric_cols:
        overall[f'{c}_med'] = float(df[c].median())
        overall[f'{c}_mean'] = float(df[c].mean())
        overall[f'{c}_std'] = float(df[c].std()) if len(df) > 1 else 0.0
    summary_rows.append(overall)

    # Per scenario_type
    for st in df['scenario_type'].unique():
        sub = df[df['scenario_type'] == st]
        row = {'group': f'scenario={st}', 'count': len(sub)}
        for c in numeric_cols:
            row[f'{c}_med'] = float(sub[c].median())
            row[f'{c}_mean'] = float(sub[c].mean())
            row[f'{c}_std'] = float(sub[c].std()) if len(sub) > 1 else 0.0
        summary_rows.append(row)

    # Per cut_in (se presente)
    if df['is_cut_in'].any():
        for ci in [False, True]:
            sub = df[df['is_cut_in'] == ci]
            if len(sub) == 0:
                continue
            row = {'group': f'cut_in={ci}', 'count': len(sub)}
            for c in numeric_cols:
                row[f'{c}_med'] = float(sub[c].median())
                row[f'{c}_mean'] = float(sub[c].mean())
                row[f'{c}_std'] = float(sub[c].std()) if len(sub) > 1 else 0.0
            summary_rows.append(row)

    return pd.DataFrame(summary_rows)
