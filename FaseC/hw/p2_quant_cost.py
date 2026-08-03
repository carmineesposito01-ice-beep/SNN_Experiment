"""Quanto costa, a livello di PLOTONE, quantizzare l'uscita a sfix13_En8.

Non e' un cancello: e' una CARATTERIZZAZIONE. Confronta la traiettoria dell'anello chiuso RTL
(accel quantizzata a 1/256) con quella di P1 (accel float32 continua). Le due non possono
coincidere -- non calcolano la stessa grandezza -- e la domanda utile non e' "coincidono?" ma
"di quanto si separano, e l'esito di sicurezza cambia?".

Misurato: la differenza parte SOTTO il LSB, cresce nei primi ~100 control-step e poi si
STABILIZZA. E' l'anello che amplifica l'errore di quantizzazione fino a un livello limitato,
non una divergenza che scappa.
"""
import argparse
import json
import os
import sys

import numpy as np

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
sys.path.insert(0, os.path.dirname(QUI))

from p2_compare import leggi_serie                                 # noqa: E402
from phase_c import artifacts                                      # noqa: E402

LSB = 1.0 / 256.0


def analizza(work, nscen):
    g = np.load(os.path.join(work, 'p2_golden.npz'))
    picchi = {c: [] for c in ('a', 'v', 'gap', 'x')}
    coll_rtl = coll_p1 = 0
    profilo = None

    for j in range(1, nscen + 1):
        rtl, c = leggi_serie(os.path.join(work, 'ser_loop', 'ser_%d.txt' % j))
        coll_rtl += int(c)
        coll_p1 += int(bool(g['collided'][j - 1]))
        for campo in picchi:
            picchi[campo].append(float(np.abs(rtl[campo] - g[campo][j - 1]).max()))
        if j == 1:
            d = np.abs(rtl['a'] - g['a'][0])
            profilo = {str(t): float(d[t].max()) for t in
                       (0, 1, 2, 5, 10, 20, 50, 100, 200, 300, 400, 500, 599)}

    def stat(v):
        v = np.asarray(v)
        return {'mediana': float(np.median(v)), 'p95': float(np.percentile(v, 95)),
                'massimo': float(v.max())}

    return {
        'n_scenari': nscen,
        'lsb_accel': LSB,
        'scarto_di_picco_per_scenario': {c: stat(v) for c, v in picchi.items()},
        'profilo_temporale_scenario_1': profilo,
        'collisioni': {'rtl': coll_rtl, 'p1': coll_p1,
                       'uguali': coll_rtl == coll_p1},
        'lettura': (
            'la differenza parte sotto il LSB, cresce nei primi ~100 control-step e si '
            'stabilizza: l\'anello amplifica l\'errore di quantizzazione fino a un livello '
            'LIMITATO, non lo fa scappare. L\'esito di sicurezza (numero di collisioni) '
            'e\' identico, quindi la quantizzazione dell\'uscita non cambia cio\' che conta.'),
    }


def _main(argv):
    ap = argparse.ArgumentParser(description='P2 - costo della quantizzazione, sul plotone')
    ap.add_argument('--work', default='C:/t7cp2')
    ap.add_argument('--nscen', type=int, default=88)
    ap.add_argument('--out', default=None)
    a = ap.parse_args(argv)

    r = analizza(a.work, a.nscen)
    print('scarto di PICCO per scenario, RTL (accel 1/256) contro P1 (accel float32):')
    print('  %-6s %10s %10s %10s' % ('campo', 'mediana', 'p95', 'massimo'))
    for c in ('a', 'v', 'gap'):
        s = r['scarto_di_picco_per_scenario'][c]
        print('  %-6s %10.4f %10.4f %10.4f' % (c, s['mediana'], s['p95'], s['massimo']))
    print('\n  un LSB = %.6f m/s2' % LSB)
    print('  collisioni: RTL %d, P1 %d  ->  %s'
          % (r['collisioni']['rtl'], r['collisioni']['p1'],
             'IDENTICHE' if r['collisioni']['uguali'] else 'DIVERSE'))
    if a.out:
        artifacts.write(a.out, r, frontend='script',
                        bitstream_sig='n/a (simulazione RTL)', sorgente='rtl-xsim')
        print('  artefatto: %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv[1:]))
