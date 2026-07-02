"""tests/test_fpga_seu.py -- integration key-check per seu_inject (incr.3).

Codec po2 4-bit, sensitivity_map (cheap), ripristino garantito della sessione, e un
collision_vs_flips MINIMALE sulla cache val reale. Modelli random (nessun checkpoint).
Run: python tests/test_fpga_seu.py
"""
import os
import sys
import math

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

import numpy as np
import torch
from core.network import build_model
from utils.seu_inject import (encode_po2, decode_bits, flip_bit, ZERO_CODE, SIGN_BIT,
                              InjectionSession, sensitivity_map, bit_criticality,
                              hidden_vs_readout, collision_vs_flips)
from utils.weight_profiler import PO2_EXP_MIN, PO2_EXP_MAX

ok = fail = 0


def check(name, fn):
    global ok, fail
    try:
        fn(); print('  PASS', name); ok += 1
    except Exception as e:
        fail += 1
        import traceback
        print('  FAIL', name, '->', repr(e)); traceback.print_exc()


def _codec():
    for exp in range(PO2_EXP_MIN, PO2_EXP_MAX + 1):
        for sign in (+1, -1):
            v = sign * (2.0 ** exp)
            assert decode_bits(encode_po2(v)) == v, (exp, sign, v)
    assert encode_po2(0.0) == ZERO_CODE and decode_bits(ZERO_CODE) == 0.0
    # flip del bit di segno inverte il segno
    c = encode_po2(0.5)
    assert decode_bits(flip_bit(c, SIGN_BIT)) == -0.5
    # flip di un bit dell'esponente cambia il valore (non resta 0.5)
    assert decode_bits(flip_bit(c, 0)) != 0.5


check('codec po2 4-bit (encode/decode/flip)', _codec)

for variant in ['baseline', 'eventprop_alif_full']:
    m = build_model(variant, hidden_size=32, rank=8, max_delay=6, bit_shift=3).eval()
    xw = torch.randn(1, 40, 4) * 0.5

    def _session_restores(m=m, variant=variant):
        # i pesi tornano identici e PO2_ENABLED viene ripristinato
        p = m.layer_hidden.fc_weight
        before = p.detach().clone()
        env_before = os.environ.get('PO2_ENABLED')
        with InjectionSession(m) as inj:
            inj.set_element('fc', 0, 999.0)                 # perturbazione grossolana
            assert os.environ.get('PO2_ENABLED') == '0'
        assert torch.allclose(p.detach(), before), variant
        assert os.environ.get('PO2_ENABLED') == env_before, variant

    def _sensitivity(m=m, variant=variant):
        env_before = os.environ.get('PO2_ENABLED')
        sens = sensitivity_map(m, xw, per_matrix_sample=3, seed=0)
        assert sens['heatmap'].shape == (12, 4), (variant, sens['heatmap'].shape)  # 4 matrici x 3
        assert np.all(np.isfinite(sens['heatmap']))
        bc = bit_criticality(sens); hr = hidden_vs_readout(sens)
        assert set(bc) and all(math.isfinite(v) for v in bc.values())
        assert math.isfinite(hr['hidden_mean'])
        assert os.environ.get('PO2_ENABLED') == env_before   # ripristinato anche dopo l'analisi

    check('%s: InjectionSession ripristina pesi+env' % variant, _session_restores)
    check('%s: sensitivity_map + aggregati' % variant, _sensitivity)

# collision_vs_flips MINIMALE sulla cache reale (solo baseline, per limitare il tempo)
CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'


def _collision():
    assert os.path.isfile(CACHE), 'cache val assente: ' + CACHE
    cache = torch.load(CACHE, map_location='cpu', weights_only=False)
    mb = build_model('baseline', hidden_size=32, rank=8, max_delay=6, bit_shift=3).eval()
    res = collision_vs_flips(mb, cache, n_flips_list=(1,), n_mc=1, n_drivers=2, seq_len=50, seed=0)
    assert 0.0 <= res['baseline_collision_rate'] <= 1.0, res['baseline_collision_rate']
    assert len(res['rows']) == 2
    for r in res['rows']:
        assert 0.0 <= r['collision_rate_mean'] <= 1.0 and math.isfinite(r['collision_rate_std'])
    print('    baseline collision_rate=%.3f, con 1 flip=%.3f' %
          (res['rows'][0]['collision_rate_mean'], res['rows'][1]['collision_rate_mean']))


check('collision_vs_flips minimale (cache reale, baseline)', _collision)

print('\n==== fpga-seu test: PASS=%d FAIL=%d ====' % (ok, fail))
sys.exit(1 if fail else 0)
