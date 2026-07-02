"""tests/test_fpga_io.py -- integration key-check per io_hil (incr.4).

queue_overflow (analitico), aoi_max_surface + cold_start_deviation (cache val reale,
modello random). Run: python tests/test_fpga_io.py
"""
import os
import sys
import math

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.getcwd())

import numpy as np
import torch
from core.network import build_model
from utils.io_hil import aoi_max_surface, queue_overflow, cold_start_deviation

ok = fail = 0


def check(name, fn):
    global ok, fail
    try:
        fn(); print('  PASS', name); ok += 1
    except Exception as e:
        fail += 1
        import traceback
        print('  FAIL', name, '->', repr(e)); traceback.print_exc()


def _queue():
    rows = queue_overflow(depths=(1, 2, 4, 8, 16), rho=0.7)
    assert len(rows) == 5
    dr = [r['drop_rate'] for r in rows]
    assert all(0.0 <= d <= 1.0 for d in dr)
    assert dr[0] > dr[-1]                 # buffer piu' grande -> meno drop


check('queue_overflow (M/M/1/K analitico)', _queue)

CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'


def _io_realcache():
    assert os.path.isfile(CACHE), 'cache val assente: ' + CACHE
    cache = torch.load(CACHE, map_location='cpu', weights_only=False)
    m = build_model('baseline', hidden_size=32, rank=8, max_delay=6, bit_shift=3).eval()

    surf = aoi_max_surface(m, cache, gaps=(10.0, 30.0), dvs=(0.0, 10.0),
                           max_stale_steps=16, horizon=120, t_brake=30)
    g = surf['aoi_max_steps']
    assert g.shape == (2, 2), g.shape
    assert np.all(np.isfinite(g)) and np.all((g >= 0) & (g <= 16))
    assert np.allclose(surf['aoi_max_s'], g * 0.1)

    cs = cold_start_deviation(m, cache, ks=(2, 6, 25), n_drivers=2, seq_len=50)
    assert len(cs) == 3
    for r in cs:
        assert math.isfinite(r['rel_param_dev_mean']) and r['rel_param_dev_mean'] >= 0
    print('    AoI_max grid (step):', g.tolist(),
          '| cold-start dev k=2/25: %.3f/%.3f' %
          (cs[0]['rel_param_dev_mean'], cs[-1]['rel_param_dev_mean']))


check('aoi_max_surface + cold_start (cache reale)', _io_realcache)

print('\n==== fpga-io test: PASS=%d FAIL=%d ====' % (ok, fail))
sys.exit(1 if fail else 0)
