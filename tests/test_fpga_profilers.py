"""tests/test_fpga_profilers.py -- integration key-check per weight_profiler + latency_model.

Come per l'evaluate v3: verifica su MODELLI RANDOM (build_model, nessun checkpoint) che le
librerie Fase A girino e restituiscano la struttura giusta su ENTRAMBE le famiglie
(baseline e eventprop_alif_full). I numeri sono casuali; qui contano forma/chiavi/finitezza.
Run: python tests/test_fpga_profilers.py
"""
import os
import sys
import math

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

import numpy as np
import torch
from core.network import build_model
from utils.weight_profiler import profile_weights, weight_stats_rows, PO2_EXP_MIN, PO2_EXP_MAX
from utils.latency_model import op_count, wcet_cycles, dse_profiles, model_shapes
from utils.state_profiler import (profile_states, state_ranges_rows, leak_underflow_curve,
                                  isi_stats)
from utils.net_diagnostics import spike_raster

ok = fail = 0


def check(name, fn):
    global ok, fail
    try:
        fn()
        print('  PASS', name)
        ok += 1
    except Exception as e:
        fail += 1
        import traceback
        print('  FAIL', name, '->', repr(e))
        traceback.print_exc()


def _finite(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


for variant in ['baseline', 'eventprop_alif_full']:
    m = build_model(variant, hidden_size=32, rank=8, max_delay=6, bit_shift=3)
    m.eval()

    def _weights(m=m, variant=variant):
        prof = profile_weights(m)
        names = [s['matrix'] for s in prof['matrices']]
        assert names == ['fc', 'rec_U', 'rec_V', 'out'], (variant, names)
        # 800 pesi sinaptici attesi per 4->32(r8,d6)->5: 128+256+256+160
        assert prof['total_synaptic_weights'] == 800, (variant, prof['total_synaptic_weights'])
        for s in prof['matrices']:
            assert set(s['exp_hist']) == set(range(PO2_EXP_MIN, PO2_EXP_MAX + 1)), s['exp_hist']
            assert 0.0 <= s['frac_zero'] <= 1.0
            assert _finite(s['qerr_mean']) and _finite(s['qerr_max'])
            assert s['footprint_bits'] == s['n_weights'] * 4
        rec = prof['recurrence']
        assert 'spectral_radius' in rec and _finite(rec['spectral_radius']), rec
        assert _finite(prof['thresholds'].get('base_threshold_mean', float('nan')))
        assert prof['delays'].get('max_delay', 0) >= 1

    def _weight_rows(m=m, variant=variant):
        rows = weight_stats_rows(m)
        assert len(rows) == 4
        for r in rows:
            for e in range(PO2_EXP_MIN, PO2_EXP_MAX + 1):
                assert f'exp_{e}' in r, (variant, list(r))
            assert 'x' in r['shape']

    def _latency(m=m, variant=variant):
        s = model_shapes(m)
        assert s['IN'] == 4 and s['H'] == 32 and s['R'] == 8 and s['O'] == 5, (variant, s)
        assert s['n_ticks'] >= 1
        c = op_count(m, spike_rate=0.02)
        assert c['synaptic_ac_per_step_worstcase'] > 0
        assert c['synaptic_ac_per_step_typical'] <= c['synaptic_ac_per_step_worstcase']
        # serial deve essere piu' lento di full-unroll, entrambi dentro la deadline
        w_serial = wcet_cycles(c, 1, fmax_mhz=100.0)
        w_full = wcet_cycles(c, None, fmax_mhz=100.0)
        assert w_serial['cycles_per_step'] > w_full['cycles_per_step']
        assert w_serial['margin_x'] > 1.0, w_serial['margin_x']   # rientra nei 100 ms
        assert _finite(w_serial['us_per_step'])
        dse = dse_profiles(m, spike_rate=0.02, fmax_mhz=100.0)
        assert len(dse['profiles']) == 4
        assert all(_finite(p['us_per_step']) for p in dse['profiles'])

    def _state(m=m, variant=variant):
        xb = torch.randn(3, 12, 4) * 0.5
        prof = profile_states(m, xb)
        assert 'raw_out' in prof['states'], (variant, list(prof['states']))
        assert np.isfinite(prof['states']['raw_out']['absmax'])
        base_ok, rows = state_ranges_rows(m, xb)
        assert base_ok == prof['baseline']
        if variant == 'baseline':
            assert prof['baseline'] is True
            for k in ('potential', 'fatigue', 'eff_thresh', 'current', 'rec_curr', 'rec_int'):
                assert k in prof['states'], (variant, k, list(prof['states']))
            for r in rows:
                assert {'state', 'int_bits', 'frac_bits', 'total_bits'} <= set(r), list(r)
        else:
            assert prof['baseline'] is False           # eventprop: solo readout/spike
        # leak-underflow: il float decade sotto il valore iniziale; il fixed 4b si "incastra"
        lk = leak_underflow_curve(v0=2.0, bit_shift=3, frac_bits_list=(4, 8))
        assert lk['float'][-1] < lk['float'][0]
        assert lk['fixed_4b'][-1] >= lk['fixed_8b'][-1]   # meno frac_bits -> si ferma piu' in alto
        # ISI dal raster reale
        rr = spike_raster(m, xb[0], max_steps=12)
        isi = isi_stats(rr)
        assert 'min_isi' in isi

    check('%s: profile_weights' % variant, _weights)
    check('%s: weight_stats_rows' % variant, _weight_rows)
    check('%s: latency op_count/wcet/dse' % variant, _latency)
    check('%s: state_profiler ranges/leak/isi' % variant, _state)

# stampa un esempio leggibile per ispezione manuale
print('\n--- esempio (baseline) ---')
mb = build_model('baseline', hidden_size=32, rank=8, max_delay=6, bit_shift=3).eval()
pb = profile_weights(mb)
print('pesi sinaptici totali:', pb['total_synaptic_weights'],
      '| footprint:', pb['total_footprint_bytes'], 'byte')
print('rho(U@V) po2:', round(pb['recurrence']['spectral_radius'], 4),
      '| ||U@V||2:', round(pb['recurrence']['spectral_norm'], 4))
for s in pb['matrices']:
    print('  %-6s n=%-4d %%zero=%.2f exp_hist=%s' %
          (s['matrix'], s['n_weights'], s['frac_zero'], s['exp_hist']))
dse = dse_profiles(mb, spike_rate=0.02)
for p in dse['profiles']:
    print('  DSE %-11s cicli/step=%-7d us/step=%.2f margine=%.0fx' %
          (p['profile'], p['cycles_per_step'], p['us_per_step'], p['margin_x']))

print('\n==== fpga-profilers test: PASS=%d FAIL=%d ====' % (ok, fail))
sys.exit(1 if fail else 0)
