#!/usr/bin/env python3
"""T7a — metriche di car-following dal motore CANONICO, sulle serie prodotte dall'RTL.

Non riscrive alcuna metrica: usa `utils.closed_loop_eval`, lo stesso motore che ha prodotto
VALIDATION_REPORT_v3 e QUANTIZATION_STUDY_REPORT, quindi i numeri sono confrontabili con i report
pubblicati **per costruzione**.

CONTRATTO — NOVE chiavi:  s, v, vl, dv, a_ego, params, collided, min_gap, impact_dv
  * `params` (N x 5) serve a tracking_metrics per il gap desiderato s*; ometterla da' KeyError,
    quindi fallisce rumorosamente.
  * `impact_dv` ha un DEFAULT SILENZIOSO nel motore: `traj.get('impact_dv', 0.0)`
    (`closed_loop_eval.py:257`). Ometterla NON da' errore: restituisce 0.0, cioe' "collisione a
    severita' nulla" per una collisione reale. Misurato su aggressive_cut_in il valore vero e'
    5,39 m/s. Per questo le nove chiavi sono ASSERITE qui, invece di affidarsi al motore.

Uso:  python t7_metrics.py <series.mat> <out.json>
"""
import json
import sys

import numpy as np
import scipy.io as sio

sys.path.insert(0, '.')
from utils.closed_loop_eval import all_metrics, string_stability_gain

REQUIRED = ('s', 'v', 'vl', 'dv', 'a_ego', 'params', 'collided', 'min_gap', 'impact_dv')


def to_traj(e):
    """Costruisce il dict del motore, ASSERENDO le nove chiavi e la coerenza delle lunghezze.

    L'accesso e' per attributo: una chiave mancante da' AttributeError, cioe' fallisce rumorosamente
    invece di passare per un default silenzioso.
    """
    missing = [k for k in REQUIRED if not hasattr(e, k)]
    if missing:
        raise AssertionError(f'contratto violato: chiavi mancanti nelle serie: {missing}')
    t = {
        's': np.atleast_1d(e.s).astype(float),
        'v': np.atleast_1d(e.v).astype(float),
        'vl': np.atleast_1d(e.vl).astype(float),
        'dv': np.atleast_1d(e.dv).astype(float),
        'a_ego': np.atleast_1d(e.a_ego).astype(float),
        'params': np.atleast_2d(e.params).astype(float),
        'collided': bool(e.collided),
        'min_gap': float(e.min_gap),
        'impact_dv': float(e.impact_dv),
    }
    n = len(t['s'])
    for k in ('v', 'vl', 'dv', 'a_ego'):
        if len(t[k]) != n:
            raise AssertionError(f'{k}: lunghezza {len(t[k])} != {n}')
    if t['params'].shape != (n, 5):
        raise AssertionError(f"params: forma {t['params'].shape} != {(n, 5)}")
    if t['collided'] and t['impact_dv'] == 0.0 and t['min_gap'] > 0:
        raise AssertionError('collisione dichiarata ma impact_dv=0 e min_gap>0: serie incoerente')
    return t


def metrics_of(e):
    t = to_traj(e)
    m = dict(all_metrics(t))
    m['string_stability'] = string_stability_gain(t)
    m['N'] = len(t['s'])
    return m


def main(matfile, outfile):
    d = sio.loadmat(matfile, squeeze_me=True, struct_as_record=False)
    res = {}
    for tag in ('RTL', 'ORA'):
        arr = np.atleast_1d(d[tag])
        res[tag] = {str(e.name): metrics_of(e) for e in arr}

    names = sorted(res['RTL'])
    if sorted(res['ORA']) != names:
        raise AssertionError('RTL e oracolo non coprono gli stessi scenari')

    # T7-SAFE: collisioni AGGIUNTIVE rispetto all'oracolo — il cancello DURO (spec §7)
    extra = [k for k in names if res['RTL'][k]['collided'] and not res['ORA'][k]['collided']]
    res['_summary'] = {
        'n_scenari': len(names),
        'coll_rtl': sum(1 for k in names if res['RTL'][k]['collided']),
        'coll_oracolo': sum(1 for k in names if res['ORA'][k]['collided']),
        'coll_extra': len(extra),
        'coll_extra_scenari': extra,
        # 'N' e' metadato (lunghezza della serie), non una metrica: escluso dal conteggio
        'n_metriche': len(res['RTL'][names[0]]) - 1,
    }
    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=2, sort_keys=True, default=float)

    s = res['_summary']
    print(f"scenari={s['n_scenari']}  metriche/scenario={s['n_metriche']}")
    print(f"collisioni RTL={s['coll_rtl']}  oracolo={s['coll_oracolo']}  EXTRA={s['coll_extra']}")
    if extra:
        print(f"  scenari con collisione EXTRA: {extra}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
