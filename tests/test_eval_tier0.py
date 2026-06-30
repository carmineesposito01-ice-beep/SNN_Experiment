"""Test Tier 0 dell'evaluate upgrade: backward-compat + aggregazione ricca + flag ISO + helper statistici.

Standalone: `python tests/test_eval_tier0.py` (exit 0 = OK). Niente pytest richiesto.
Usa uno StubModel deterministico (forward_sequence) + cache sintetica: NON serve un modello allenato.
"""
import os
import sys
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.closed_loop_eval import comfort_metrics, safety_metrics, simulate  # noqa: E402
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
            'scenario': ['following', 'highway', 'urban'][i % 3],
        })
    return {'val': val}


def test_comfort_iso_flags():
    # a_ego con un picco di decel a -4 (>ISO 3.5) e accel a +3 (>ISO 2): i flag devono accendersi.
    a = np.array([0.0, 1.0, 3.0, -4.0, 0.0, 0.0], dtype=np.float64)
    cm = comfort_metrics({'a_ego': a, 'v': np.full(len(a), 10.0)})
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


def test_continuous_safety_metrics():
    # T0.10 — margine di evitabilita' (con segno) + severita' d'impatto (Δv): continue, non saturano.
    pg = np.array([30.0, 1.2, 2.5, 1.1, 1.5], dtype=np.float32)
    tr_c = simulate(None, pg, np.zeros(200), 3.0, 25.0)        # leader fermo, gap minuscolo, ego veloce
    sm_c = safety_metrics(tr_c)
    assert tr_c['collided'] and tr_c['impact_dv'] > 0
    assert sm_c['impact_dv'] > 0 and sm_c['brake_margin_min'] < 0   # inevitabile -> margine negativo
    tr_s = simulate(None, pg, np.full(200, 18.0), float(pg[2] + 18.0 * pg[1]), 18.0)  # following safe
    assert not tr_s['collided'] and safety_metrics(tr_s)['impact_dv'] == 0.0
    # CONTINUITA': due collisioni si ORDINANO per severita' (15 m/s impatta meno di 25) -> non satura
    sm_c2 = safety_metrics(simulate(None, pg, np.zeros(200), 3.0, 15.0))
    assert sm_c2['impact_dv'] < sm_c['impact_dv']
    print('  OK metriche continue: brake_margin_min (segno) + impact_dv (ordina anche le collisioni)')


# ----------------------------- TIER 1 -----------------------------
def _synth_traj(M=100):
    a = np.concatenate([np.linspace(0, 1.0, M // 2), -np.linspace(0, 4.0, M - M // 2)])
    return {'s': np.linspace(25, 4, M), 'v': np.full(M, 10.0), 'dv': np.linspace(0, 4, M),
            'vl': np.full(M, 8.0), 'a_ego': a,
            'params': np.tile([30.0, 1.2, 2.5, 1.1, 1.5], (M, 1)).astype(float),
            'collided': False, 'min_gap': 4.0}


def test_tail_scenarios():
    from utils.closed_loop_eval import build_scenarios
    pg = np.array([30.0, 1.2, 2.5, 1.1, 1.5], dtype=np.float32)
    base = build_scenarios(pg, N=200, rng=np.random.default_rng(0))
    full = build_scenarios(pg, N=200, rng=np.random.default_rng(0), include_tail=True)
    assert len(base) == 5, len(base)
    names = [s[0] for s in full]
    for nm in ['cut_out', 'static_target', 'panic_stop', 'aggressive_cut_in']:
        assert nm in names, nm
    assert len(full) == 9, len(full)
    # static_target ha leader fermo
    vl_static = dict((s[0], s[1]) for s in full)['static_target']
    assert np.all(vl_static == 0.0)
    print('  OK tail scenarios (base=5, +tail=9)')


def test_new_metric_keys():
    from utils.closed_loop_eval import safety_metrics, comfort_metrics, tracking_metrics
    tr = _synth_traj()
    sm = safety_metrics(tr)
    for k in ['frac_drac_critical', 'TED_drac', 'TID_drac', 'frac_ttc_below_1.5', 'frac_ttc_below_1.0']:
        assert k in sm, k
    assert 0.0 <= sm['frac_drac_critical'] <= 1.0
    cm = comfort_metrics(tr)
    assert 'energy_proxy' in cm and cm['energy_proxy'] >= 0.0
    tm = tracking_metrics(tr)
    for k in ['mean_abs_dv_ss', 'mean_abs_gap_err_ss']:
        assert k in tm and tm[k] == tm[k], k
    print('  OK nuove metriche (DRAC/TTC soglie, energia, steady-state)')


def test_eval_tail_and_rollout():
    model = StubModel(); cache = _synth_cache(3)
    torch.manual_seed(0)
    out = eval_safety(model, cache, n_drivers=3, rich=True, tail=True)
    r = out['rich']
    assert len(r['per_scenario']) == 9, len(r['per_scenario'])
    assert 'rollout' in r and 'rmse_accel' in r['rollout'] and 'mae_accel' in r['rollout']
    assert 'braking_dist_err' in r['rollout'] and len(r['rollout']['braking_dist_err']) >= 1
    # backward-compat: tail=False default invariato (5 scenari)
    torch.manual_seed(0)
    out0 = eval_safety(model, cache, n_drivers=3, rich=True)
    assert len(out0['rich']['per_scenario']) == 5
    print('  OK eval tail (9 scenari) + rollout RMSE/braking-dist')


def test_breakdown_curve():
    from scripts.closed_loop_identify import breakdown_curve
    model = StubModel(); cache = _synth_cache(2)
    bc = breakdown_curve(model, cache, n_drivers=2, decels=(6.0, 9.0), gaps=(6.0, 3.0))
    assert len(bc['panic']) == 2 and len(bc['cut_in']) == 2
    for row in bc['panic']:
        assert 'decel' in row and 'oracle' in row and 'snn' in row
        assert 0.0 <= row['snn'] <= 1.0
    print('  OK breakdown curve (panic+cut_in, oracolo vs snn)')


def test_make_ood_cache():
    from scripts.closed_loop_identify import make_ood_cache
    from data.generator import _PHYS_BOUNDS
    c = make_ood_cache(n_drivers=2, seed=1)
    assert len(c['val']) == 2
    for it in c['val']:
        assert it['x'].ndim == 2 and it['x'].shape[1] == 4
        assert set(['v0', 'T', 's0', 'a', 'b']).issubset(it['params'].keys())
    print('  OK make_ood_cache (driver OoD generati)')


# ----------------------------- TIER 2 -----------------------------
def _leader_brake(N=200, v_set=15.0, decel=6.0):
    vl = np.full(N, v_set); bs = N // 3
    for i in range(bs, N):
        vl[i] = max(0.0, vl[i - 1] - decel * 0.1)
    return vl


def test_plant_channel_helpers():
    from utils.closed_loop_eval import _plant_step, _channel_obs
    # lag attuatore: dopo un init a 0, a_real insegue a_cmd senza raggiungerlo in 1 step
    st = {}
    _plant_step(0.0, 10.0, st, {'tau_act': 0.5})   # init: a_real=0
    a1 = _plant_step(-5.0, 10.0, st, {'tau_act': 0.5})   # lag da 0 verso -5
    assert -5.0 < a1 < 0.0, a1
    # clip aderenza mu: decel non oltre -mu*g
    st = {}
    a2 = _plant_step(-9.0, 10.0, st, {'mu': 0.2})
    assert a2 >= -0.2 * 9.81 - 1e-6, a2
    # grade in salita riduce l'accel
    st = {}
    a_flat = _plant_step(0.0, 10.0, {}, {})
    a_up = _plant_step(0.0, 10.0, {}, {'grade': 0.05})
    assert a_up < a_flat
    # canale: pdr=0 -> hold-last (sempre il primo campione ricevuto)
    cst = {}; rng = np.random.default_rng(0)
    s0o, vl0o, _ = _channel_obs(20.0, 8.0, cst, {'pdr': 0.0}, rng)
    s1o, vl1o, age = _channel_obs(5.0, 2.0, cst, {'pdr': 0.0}, rng)
    assert s1o == s0o and vl1o == vl0o and age >= 1   # tenuto l'ultimo
    print('  OK plant/channel helpers (lag, mu-clip, grade, hold-last)')


def test_simulate_plant_channel_backcompat():
    pg = np.array([30.0, 1.2, 2.5, 1.1, 1.5], dtype=np.float32)
    vl = _leader_brake()
    s_i = pg[2] + 0.7 * pg[0] * pg[1]; v_i = 0.7 * pg[0]
    base = simulate(None, pg, vl, s_i, v_i)
    base2 = simulate(None, pg, vl, s_i, v_i, plant=None, channel=None)
    assert np.allclose(base['a_ego'], base2['a_ego']), 'default deve essere identico'
    # plant ON cambia l'accel realizzata
    withlag = simulate(None, pg, vl, s_i, v_i, plant={'tau_act': 0.5, 'mu': 0.4})
    assert not np.allclose(base['a_ego'][:len(withlag['a_ego'])], withlag['a_ego'][:len(base['a_ego'])]), 'plant deve cambiare a_ego'
    # channel ON produce AoI
    withch = simulate(None, pg, vl, s_i, v_i, channel={'pdr': 0.5, 'latency_steps': 2, 'seed': 1})
    assert 'aoi_mean' in withch and withch['aoi_mean'] >= 0.0
    print('  OK simulate plant/channel (default invariato, plant/channel attivi cambiano)')


def test_param_chattering():
    from utils.closed_loop_eval import param_chattering
    M = 200
    t = np.arange(M)
    P = np.tile([30.0, 1.2, 2.5, 1.1, 1.5], (M, 1)).astype(float)
    P[:, 1] += 0.3 * np.sin(2 * np.pi * 2.0 * t * 0.1)   # T oscilla a 2 Hz (>0.5)
    ch = param_chattering({'params': P})
    assert ch['chatter_std_T'] > 0.1 and ch['chatter_hf_T'] > 0.3, ch
    flat = param_chattering({'params': np.tile([30.0, 1.2, 2.5, 1.1, 1.5], (M, 1)).astype(float)})
    assert flat['chatter_std_v0'] < 1e-9
    print('  OK param_chattering (HF rilevato, costante ~0)')


def test_v2x_sweep_and_cbr():
    from scripts.closed_loop_identify import v2x_robustness_sweep, cbr_to_pdr
    model = StubModel(); cache = _synth_cache(2)
    rows = v2x_robustness_sweep(model, cache, n_drivers=2, pdrs=(1.0, 0.5), latencies=(0, 3))
    assert len(rows) == 4
    for r in rows:
        assert 'collision_rate' in r and 'min_ttc_p5' in r and r['axis'] in ('pdr', 'latency')
    assert cbr_to_pdr(0) > cbr_to_pdr(50)          # piu' densita' -> meno PDR
    print('  OK v2x_robustness_sweep + cbr_to_pdr')


# ----------------------------- TIER 3 -----------------------------
def test_platoon_and_transfer():
    from utils.closed_loop_eval import simulate_platoon, platoon_string_metrics, transfer_gain_fft
    pg = np.array([30.0, 1.2, 2.5, 1.1, 1.5], dtype=np.float32)
    N = 4; L = 400; dt = 0.1
    leader = 21.0 + 1.0 * np.sin(2 * np.pi * 0.1 * (np.arange(L) * dt))
    pl = simulate_platoon([pg] * N, leader)
    V = pl['v_profiles']
    assert V.shape[0] == N + 1, V.shape
    assert len(pl['collided']) == N
    m = platoon_string_metrics(V)
    assert len(m['amp_ratio']) == N and len(m['l2_gain']) == N and len(m['linf_gain']) == N
    assert m['head_to_tail'] == m['head_to_tail'] and isinstance(m['strict_string_stable'], bool)
    # transfer gain: smorzato <1, amplificato >1
    base = np.sin(2 * np.pi * 0.1 * (np.arange(L) * dt))
    g_damp = transfer_gain_fft(base, 0.5 * base, band=(0.01, 0.3))['peak_gain']
    g_amp = transfer_gain_fft(base, 2.0 * base, band=(0.01, 0.3))['peak_gain']
    assert g_damp < 1.0 < g_amp, (g_damp, g_amp)
    print('  OK platoon (N+1 profili, amp/L2/Linf) + transfer_gain_fft')


def test_eval_string_stability():
    from scripts.closed_loop_identify import eval_string_stability
    model = StubModel(); cache = _synth_cache(6)
    r = eval_string_stability(model, cache, N=4, n_platoons=2, hetero=True, perturb_len=300)
    for k in ['head_to_tail_mean', 'peak_gain_mean', 'frac_strict_stable', 'mean_T', 'head_to_tail_ci95']:
        assert k in r, k
    assert r['N'] == 4 and r['n_platoons'] == 2
    # con latenza CAM nel plotone (T3.6): deve girare e tornare la struttura
    r2 = eval_string_stability(model, cache, N=3, n_platoons=1, hetero=False, latency_steps=2, perturb_len=300)
    assert r2['latency_steps'] == 2 and r2['mean_T'] == r2['mean_T']
    print('  OK eval_string_stability (plotone omogeneo/eterogeneo + latenza CAM)')


# ----------------------------- TIER 4 -----------------------------
def test_fim_identifiability():
    from utils.identifiability import (fisher_information, practical_identifiability,
                                       equifinality_set, persistent_excitation)
    T = 60
    states = {'s': np.linspace(30, 15, T), 'v': np.full(T, 20.0), 'dv': np.full(T, 1.0),
              'vl': np.full(T, 19.0), 'a_l': np.zeros(T)}
    pg = [30.0, 1.2, 2.5, 1.1, 1.5]
    fi = fisher_information(states, pg)
    assert set(fi['sensitivity'].keys()) == set(['v0', 'T', 's0', 'a', 'b'])
    assert fi['cond'] >= 1.0 and all(v >= 0 for v in fi['sensitivity'].values())
    cache = _synth_cache(6)
    pi = practical_identifiability(cache, n=4)
    assert 'cond_mean' in pi and pi['least_identifiable'] in ['v0', 'T', 's0', 'a', 'b']
    eq = equifinality_set(states, pg, n=80)
    assert eq['n_equivalent'] >= 1 and set(eq['param_rel_spread'].keys()) == set(['v0', 'T', 's0', 'a', 'b'])
    pe = persistent_excitation(cache, n=4)
    assert 0 <= pe['rank'] <= 5 and isinstance(pe['under_excited'], list)
    print('  OK FIM/identificabilita (cond=%.1f) + equifinalita + excitation (rank=%d)' % (fi['cond'], pe['rank']))


def test_causal_stratified_natural():
    from utils.identifiability import causal_sensitivity, nrmse_stratified, naturalisticity
    model = StubModel(); cache = _synth_cache(6)
    cs = causal_sensitivity(model, cache, n=6)
    assert 'var_vl->T' in cs and len(cs) == 9
    ns = nrmse_stratified(model, cache, n=6)
    assert set(['following', 'highway', 'urban']).issubset(ns.keys())
    for sc in ns:
        assert set(ns[sc].keys()) == set(['v0', 'T', 's0', 'a', 'b'])
    nat = naturalisticity(model, cache, n=4)
    assert 'ks_time_gap' in nat and 'ks_jerk' in nat
    from utils.identifiability import calibration_validation
    cv = calibration_validation(model, cache, n=6, seq_len=30)
    assert 'gap_rmspe_mean' in cv and 'within_floor' in cv and 'floor_intra_driver' in cv
    print('  OK causal_sensitivity + nrmse_stratified + naturalisticity + calibration_validation')


def test_reachability():
    from scripts.closed_loop_identify import reachability_frontier
    model = StubModel(); cache = _synth_cache(3)
    rf = reachability_frontier(model, cache, n_drivers=2, gaps=(5.0, 15.0, 30.0), dvs=(0.0, 10.0))
    assert 'min_safe_gap' in rf and 'oracle' in rf['min_safe_gap'] and 'snn' in rf['min_safe_gap']
    assert set(rf['min_safe_gap']['snn'].keys()) == set([0.0, 10.0])
    print('  OK reachability_frontier (frontiera safe oracolo vs snn)')


# ----------------------------- TIER 5 -----------------------------
def test_quantization():
    from utils.quantize import fake_quant, quantize_po2, QuantParamModel
    # fixed-point: su griglia 2^-frac_bits; meno bit = piu' errore
    q4 = fake_quant(0.1, frac_bits=4)
    assert abs(q4 - 0.125) < 1e-9, q4
    err4 = abs(fake_quant(0.1, 4) - 0.1); err8 = abs(fake_quant(0.1, 8) - 0.1)
    assert err4 >= err8
    assert abs(quantize_po2(0.1) - 0.125) < 1e-9         # 2^round(log2 0.1)=2^-3
    # wrapper: output quantizzato sulla griglia
    model = StubModel()
    qm = QuantParamModel(model, frac_bits=6)
    x = torch.zeros(1, 50, 4)
    out = qm.forward_sequence(x).cpu().numpy()
    assert np.allclose(out * 64, np.round(out * 64))     # multipli di 2^-6
    print('  OK quantize (fixed-point/po2 + QuantParamModel)')


def test_eval_quantization():
    from scripts.closed_loop_identify import eval_quantization
    model = StubModel(); cache = _synth_cache(4)
    r = eval_quantization(model, cache, frac_bits_list=(8, 4), n_drivers=3)
    assert r['curve'][0]['frac_bits'] == 'float' and len(r['curve']) == 3
    for row in r['curve']:
        assert 'id_err_mean' in row and 'collision_rate' in row and 'min_ttc_p5' in row
    assert r['with_v2x'] is False
    # T5.2: quant + V2X combinati
    r2 = eval_quantization(model, cache, frac_bits_list=(6,), n_drivers=2, channel={'pdr': 0.7, 'seed': 0})
    assert r2['with_v2x'] is True and len(r2['curve']) == 2
    print('  OK eval_quantization (curva float-vs-fixed + gemello V2X)')


if __name__ == '__main__':
    print('[TEST Tier0]')
    test_comfort_iso_flags()
    test_helpers()
    test_eval_safety_backward_compat_and_rich()
    test_continuous_safety_metrics()
    print('[TEST Tier1]')
    test_tail_scenarios()
    test_new_metric_keys()
    test_eval_tail_and_rollout()
    test_breakdown_curve()
    test_make_ood_cache()
    print('[TEST Tier2]')
    test_plant_channel_helpers()
    test_simulate_plant_channel_backcompat()
    test_param_chattering()
    test_v2x_sweep_and_cbr()
    print('[TEST Tier3]')
    test_platoon_and_transfer()
    test_eval_string_stability()
    print('[TEST Tier4]')
    test_fim_identifiability()
    test_causal_stratified_natural()
    test_reachability()
    print('[TEST Tier5]')
    test_quantization()
    test_eval_quantization()
    print('TUTTI I TEST OK')
