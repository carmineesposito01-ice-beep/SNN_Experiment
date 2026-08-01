"""P2 - esporta gli scenari del plotone per il testbench RTL, e il golden con cui confrontarlo.

Il golden NON e' un file nuovo: e' l'uscita di `sim.ui.platoon.run_platoon`, cioe' esattamente
il motore che ha prodotto P1. Cosi' P2 verifica che l'RTL riproduca **quello che P1 ha misurato**,
non un terzo riferimento inventato per l'occasione.

Formato dei .mem: una parola per riga, il bit pattern IEEE-754 a 64 bit in esadecimale --
la stessa convenzione dei testbench di T7a ($readmemh + $bitstoreal).

Attenzione al plant: quello del PLOTONE lavora sulle POSIZIONI

    gap = x_leader - x - VEH_LEN         (non l'integrazione del gap di qz_cl_sim)
    v   = max(0, v + a*DT);  x = x + v*DT

Non e' il plant di T7a, e per questo va provato a parte (PLATOON-PAR) prima di credere
all'anello chiuso.
"""
import argparse
import io
import os
import struct
import sys

import numpy as np

QUI = os.path.dirname(os.path.abspath(__file__))
FASEC = os.path.dirname(QUI)
sys.path.insert(0, FASEC)

from phase_c import PROJECT                                        # noqa: E402
from phase_c.params import load_champion, load_gt_params, load_leader  # noqa: E402
from phase_c import platoon as P                                   # noqa: E402

sys.path.insert(0, PROJECT)
from sim.ui.platoon import run_platoon                             # noqa: E402
from utils.platoon_eval import VEH_LEN, DT                         # noqa: E402


def _hex64(x):
    """double -> 16 cifre esadecimali (bit pattern IEEE-754), come si aspetta $readmemh."""
    return '%016X' % struct.unpack('<Q', struct.pack('<d', float(x)))[0]


def _scrivi_mem(path, valori):
    io.open(path, 'w', newline='').write('\n'.join(_hex64(v) for v in valori) + '\n')


def esporta(outdir, idx, n_vehicles):
    """Per ogni scenario scrive i .mem e accumula il golden. Ritorna il dict del golden."""
    os.makedirs(outdir, exist_ok=True)
    champ = load_champion()
    golden = {}

    for j, i in enumerate(idx, start=1):
        lead = load_leader(i)
        rec = run_platoon(champ, load_gt_params(i), n_vehicles, lead)
        K = len(lead)

        v_set = float(lead[0])
        v0, T, s0, a_p, b_p = [float(x) for x in load_gt_params(i)]
        gap_eq = s0 + v_set * T

        _scrivi_mem(os.path.join(outdir, 'plat_scen_%d.mem' % j), lead)
        # init: v_set, gap_eq, VEH_LEN, DT -- tutto cio' che serve al plant, niente di piu'
        _scrivi_mem(os.path.join(outdir, 'plat_init_%d.mem' % j), [v_set, gap_eq, VEH_LEN, DT])
        # accelerazioni REGISTRATE, in ordine [t][veicolo]: le usa PLATOON-PAR, senza DUT
        _scrivi_mem(os.path.join(outdir, 'plat_acc_%d.mem' % j), rec['a'].reshape(-1))

        # INCREMENTO DI VELOCITA' gia' arrotondato a float32.
        #
        # Misurato: in platoon_eval `_accel` torna da torch in float32 e numpy tiene `acc * DT`
        # in float32 (uno scalare Python non promuove un array float32). L'incremento del
        # plotone e' quindi in SINGOLA precisione, mentre l'anello chiuso (qz_cl_sim, plant_ps)
        # lavora in doppia.
        #
        # Si esporta gia' arrotondato invece di riprodurlo nel testbench per due motivi: xsim
        # non arrotonda con `shortreal` (verificato: `double == shortreal` da' 1), ed emulare
        # l'arrotondamento a bit in Verilog sarebbe codice delicato che andrebbe provato a sua
        # volta. Qui il valore nasce dalla STESSA espressione numpy del riferimento.
        incr = (rec['a'].astype(np.float32) * DT).astype(np.float64)
        _scrivi_mem(os.path.join(outdir, 'plat_dvi_%d.mem' % j), incr.reshape(-1))

        golden['scen_%d' % j] = {'idx_dataset': i + 1, 'K': K, 'N': n_vehicles,
                                 'v': rec['v'], 'x': rec['x'], 'gap': rec['gap'],
                                 'a': rec['a'], 'collided': bool(rec['collided'])}

    np.savez_compressed(os.path.join(outdir, 'p2_golden.npz'),
                        **{k: np.array([g[k] for g in golden.values()])
                           for k in ('v', 'x', 'gap', 'a')},
                        idx_dataset=np.array([g['idx_dataset'] for g in golden.values()]),
                        collided=np.array([g['collided'] for g in golden.values()]),
                        n_vehicles=n_vehicles, K=len(load_leader(idx[0])))
    return golden


def _main(argv):
    ap = argparse.ArgumentParser(description='P2 - export scenari plotone per il TB RTL')
    ap.add_argument('--out', default='C:/t7cp2', help='work-dir SENZA SPAZI (xsim si rompe)')
    ap.add_argument('--n', type=int, default=4, help='veicoli nel plotone')
    ap.add_argument('--scenari', type=int, default=None, help='solo i primi K perturbati')
    a = ap.parse_args(argv)

    pert, _ = P.partiziona_scenari(range(99))
    idx = pert[:a.scenari] if a.scenari else pert
    if ' ' in a.out:
        print('EXPORT-ABORT: la work-dir contiene spazi (%r): xsim si spezza.' % a.out)
        return 1

    g = esporta(a.out, idx, a.n)
    print('esportati %d scenari, N=%d veicoli, in %s' % (len(g), a.n, a.out))
    print('golden: %s' % os.path.join(a.out, 'p2_golden.npz'))
    return 0


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv[1:]))
