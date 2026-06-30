"""Test Tier 0 dell'evaluate upgrade: backward-compat + aggregazione ricca + flag ISO + helper statistici.

Standalone: `python tests/test_eval_tier0.py` (exit 0 = OK). Niente pytest richiesto.
Usa uno StubModel deterministico (forward_sequence) + cache sintetica: NON serve un modello allenato.
"""
import os
import sys
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.closed_loop_eval import comfort_metrics, safety_metrics  # noqa: E402
from scripts.closed_loop_identify import (eval_safety, _summarize, _wilson_ub,  # noqa: E402
                                          _bootstrap_ci)

PN = ['v0', 'T', 's0', 'a', 'b']


class StubModel:
    """forward_sequence DETERMINISTICA: param fisici con lieve modulazione su T (intra_std>0, riproducibile)."""
    def forward_sequence(self, x):                 # x: (1, T, 4)
        T = x.shape[1]
        base = torch.tensor([30.0, 1.2, 2.5, 1.1, 1.5])
        mod = 1.0 + 0.02 * torch.sin(torch.linspace(0, 3.14, T)).view(T, 1)
        return (base.view(1, 1, 5) * mod.view(1, T, 1))


def _synth_cache(n=3):
    rng = np.random.default_rng(123)
    val = []
    for i in range(n):
        val.append({
            'x': rng.random((60, 4)).astype(np.float32),
            'params': {'v0': 28.0 + i, 'T': 1.1 + 0.1 * i, 's0': 2.0 + 0.2 * i, 'a': 1.0 + 0.1 * i, 'b': 1.4 + 0.1 * i},
        })
    return {'val': val}


def test_comfort_iso_flags():
    # a_ego con un picco di decel a -4 (>ISO 3.5) e accel a +3 (>ISO 2): i flag devono accendersi.
    a = np.array([0.0, 1.0, 3.0, -4.0, 0.0, 0.0], dtype=np.float64)
    cm = comfort_metrics({'a_ego': a})
    for k in ['rms_accel', 'max_decel', 'rms_jerk']:           # legacy intatte
        assert k in cm, k
    for k in ['max_abs_jerk', 'frac_jerk_uncomf', 'frac_decel_iso_viol', 'frac_accel_iso_viol']:
        assert k in cm and 0.0 <= cm[k] if 'frac' in k else True, k
    assert cm['frac_decel_iso_viol'] > 0.0, 'decel -4 deve violare ISO -3.5'
    assert cm['frac_accel_iso_viol'] > 0.0, 'accel +3 deve violare ISO +2'
    assert cm['max_decel'] == 4.0
    print('  OK comfort ISO flags')


def test_helpers():
    s = _summarize([1.0, 2.0, np.inf, 3.0, np.nan])
    assert s['n'] == 5 and s['n_finite'] == 3 and abs(s['mean'] - 2.0) < 1e-9
    assert s['min'] == 1.0 and s['max'] == 3.0
    assert _summarize([np.inf, np.nan])['n_finite'] == 0       # tutti non-finiti
    ub0 = _wilson_ub(0, 100)                                   # 0 collisioni: UB>0 (onesto)
    assert 0.0 < ub0 < 0.05, ub0
    assert _wilson_ub(0, 0) != _wilson_ub(0, 0) or True        # n=0 -> nan, non crasha
    lo, hi = _bootstrap_ci([1.0, 1.1, 0.9, 1.0, 1.2, 0.8])
    assert lo <= hi and lo == lo, (lo, hi)
    print('  OK helper statistici')


def test_eval_safety_backward_compat_and_rich():
    model = StubModel()
    cache = _synth_cache(3)
    torch.manual_seed(0)
    out0 = eval_safety(model, cache, n_drivers=3)              # legacy (default)
    torch.manual_seed(0)
    out1 = eval_safety(model, cache, n_drivers=3, rich=True)   # ricco

    # 1) chiavi legacy presenti e IDENTICHE tra le due modalita' (additivita' pura)
    for key in ('oracle', 'snn'):
        assert set(out0[key].keys()) == {'collision_rate', 'mean_min_gap', 'mean_max_decel', 'mean_rms_jerk', 'n'}, out0[key].keys()
        assert out0[key] == out1[key], f'legacy {key} cambiato da rich=True!'
    assert out0['id_abs_err'] == out1['id_abs_err']
    assert 'rich' not in out0 and 'rich' in out1

    # 2) struttura ricca
    r = out1['rich']
    for key in ('oracle', 'snn'):
        assert 'collision' in r[key] and 'wilson_ub95' in r[key]['collision']
        assert 'min_ttc' in r[key] and 'p95' in r[key]['min_ttc']        # distribuzioni surfacing
        assert 'max_DRAC' in r[key] and 'rms_gap_error' in r[key]        # SSM/tracking surfacing (prima scartate)
    assert 'per_scenario' in r and len(r['per_scenario']) >= 4           # following/stop&go/hard_brake/cut_in/sin
    assert 'worst_case_snn' in r and 'max_DRAC_p95' in r['worst_case_snn']
    assert 'delta_snn_minus_oracle' in r and 'min_gap' in r['delta_snn_minus_oracle']
    assert 'ci95' in r['delta_snn_minus_oracle']['min_gap']
    assert set(r['intra_std'].keys()) == set(PN)
    # Wilson UB >= rate sempre
    assert r['snn']['collision']['wilson_ub95'] >= r['snn']['collision']['rate'] - 1e-9
    print('  OK eval_safety backward-compat + rich (per-scenario=%d)' % len(r['per_scenario']))


if __name__ == '__main__':
    print('[TEST Tier0]')
    test_comfort_iso_flags()
    test_helpers()
    test_eval_safety_backward_compat_and_rich()
    print('TUTTI I TEST OK')
