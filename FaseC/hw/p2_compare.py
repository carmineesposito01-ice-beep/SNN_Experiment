"""P2 -- confronta le serie del testbench RTL col golden di P1.

Due cancelli, con la stessa decomposizione di T7a e per la stessa ragione (non e' circolare:
il primo non usa il DUT, il secondo non usa il plant):

  PLATOON-PAR   il plant Verilog, alimentato con le accelerazioni REGISTRATE, riproduce le
                traiettorie di P1. Se e' rosso, il difetto e' nel plant.
  P2-EXACT      l'accelerazione di ogni DUT RTL coincide con quella di P1 sugli STESSI ingressi.

Il confronto e' BIT-ESATTO su `a` (l'uscita dell'hardware, in sfix13_En8) e sulle traiettorie:
il plant e' aritmetica in double da entrambi i lati, e una tolleranza nasconderebbe proprio la
classe di difetti che questi cancelli esistono per trovare.
"""
import argparse
import io
import os
import struct
import sys

import numpy as np


def _real(h):
    return struct.unpack('<d', struct.pack('<Q', int(h, 16)))[0]


def leggi_serie(path):
    """ser_<i>.txt -> (gap, v, x, a) di forma (K, N), piu' collided."""
    righe = [r.split() for r in io.open(path) if r.strip()]
    dati = [r for r in righe if r[0] != 'END']
    fine = [r for r in righe if r[0] == 'END']
    if not fine:
        raise RuntimeError('%s: manca la riga END -- la simulazione si e\' interrotta' % path)
    K, collided = int(fine[0][1]), bool(int(fine[0][2]))
    N = max(int(r[1]) for r in dati) + 1
    out = {k: np.zeros((K, N)) for k in ('gap', 'v', 'x', 'a')}
    for r in dati:
        t, i = int(r[0]), int(r[1])
        out['gap'][t, i] = _real(r[2]); out['v'][t, i] = _real(r[3])
        out['x'][t, i] = _real(r[4]);   out['a'][t, i] = _real(r[5])
    return out, collided


def confronta(serie_dir, golden_npz, nscen, campi):
    g = np.load(golden_npz)
    ris = {'n_scenari': nscen, 'per_campo': {}, 'primo_scarto': None, 'scenari_rossi': []}
    tot = {c: {'n': 0, 'nmis': 0, 'max_abs': 0.0} for c in campi}

    for j in range(1, nscen + 1):
        p = os.path.join(serie_dir, 'ser_%d.txt' % j)
        if not os.path.isfile(p):
            raise RuntimeError('serie mancante: %s' % p)
        rtl, _ = leggi_serie(p)
        rosso = False
        for c in campi:
            ref = np.asarray(g[c][j - 1])
            got = rtl[c]
            n = min(ref.shape[0], got.shape[0])
            d = np.abs(got[:n] - ref[:n])
            nmis = int((d != 0).sum())
            tot[c]['n'] += int(d.size)
            tot[c]['nmis'] += nmis
            tot[c]['max_abs'] = max(tot[c]['max_abs'], float(d.max()) if d.size else 0.0)
            if nmis and ris['primo_scarto'] is None:
                t, i = np.unravel_index(int(np.argmax(d != 0)), d.shape)
                ris['primo_scarto'] = {'scenario': j, 'campo': c, 't': int(t), 'veicolo': int(i),
                                       'rtl': float(got[t, i]), 'golden': float(ref[t, i])}
            rosso = rosso or bool(nmis)
        if rosso:
            ris['scenari_rossi'].append(j)

    ris['per_campo'] = tot
    ris['bit_esatto'] = all(v['nmis'] == 0 for v in tot.values())
    return ris


def _main(argv):
    ap = argparse.ArgumentParser(description='P2 - confronto RTL vs golden di P1')
    ap.add_argument('--work', default='C:/t7cp2')
    ap.add_argument('--nscen', type=int, required=True)
    ap.add_argument('--campi', nargs='+', default=['gap', 'v', 'x', 'a'])
    a = ap.parse_args(argv)

    r = confronta(os.path.join(a.work, 'ser'), os.path.join(a.work, 'p2_golden.npz'),
                  a.nscen, a.campi)
    for c, v in sorted(r['per_campo'].items()):
        print('  %-4s  %d/%d disallineati   scarto max %.3e' % (c, v['nmis'], v['n'], v['max_abs']))
    if r['bit_esatto']:
        print('BIT-ESATTO su %d scenari' % r['n_scenari'])
    else:
        print('ROSSO su %d scenari: %s' % (len(r['scenari_rossi']), r['scenari_rossi'][:10]))
        print('primo scarto: %s' % r['primo_scarto'])
    return 0 if r['bit_esatto'] else 1


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv[1:]))
