"""Filone C - il plotone. Chiude il proxy dichiarato nei report della Fase B2.0.

Nei report di B2.0 la "string stability" e', nel motore canonico stesso, un proxy LOCALE: il
caso N=1, cioe' un solo follower dietro un leader. Il numero mesoscopico vero -- che cosa
succede a una FILA di veicoli -- non e' mai entrato nei report.

Il motore non e' scritto qui. Vive in `sim/ui/platoon.py` (portato dal branch Simulator) e
regge entrambe le famiglie di rete: per l'eventprop usa `EventPropStepper`, che applica ai
pesi la stessa quantizzazione a potenze di due dell'hardware. P1 misura quindi la rete COME E'
DEPLOYATA, non quella float di training.

Perche' P1 si puo' fare senza scheda: la string stability e' una proprieta' della LEGGE DI
CONTROLLO. Poiche' l'RTL e' bit-esatto rispetto al blocco (provato in T7a su 58 522 confronti),
il numero non cambia sul silicio. P3 rispondera' a una domanda diversa -- quante istanze ci
stanno e quanto consumano -- che invece il silicio ce l'ha davvero.
"""
import os
import sys

import numpy as np

from . import PROJECT, RESULTS
from .params import load_champion, load_gt_params, load_leader, n_scenarios

if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)
from sim.ui.platoon import run_platoon                       # noqa: E402
from utils.platoon_eval import platoon_metrics               # noqa: E402

# Le chiavi che platoon_metrics restituisce davvero. Elencate perche' un refuso su un nome
# darebbe KeyError subito invece di un aggregato silenziosamente vuoto.
CHIAVI = ('head_to_tail_gain', 'max_amplification', 'string_stable_headtail',
          'strict_monotone_decay', 'convective_upstream', 'min_gap_platoon',
          'min_ttc_platoon', 'collided', 'rms_accel_mean', 'max_decel_platoon',
          'rms_jerk_mean')


def _pct(vals, q):
    s = sorted(vals)
    return float(s[min(len(s) - 1, int(q * len(s)))])


def run_one(champion, i, n_vehicles):
    """Un plotone di `n_vehicles` sullo scenario i, con le metriche complete."""
    rec = run_platoon(champion, load_gt_params(i), n_vehicles, load_leader(i))
    m = platoon_metrics(rec)
    mancanti = [k for k in CHIAVI if k not in m]
    if mancanti:
        raise KeyError('platoon_metrics non restituisce %s: il motore e\' cambiato di forma '
                       'e l\'aggregato sarebbe vuoto senza dirlo' % mancanti)
    return m


def run_p1(n_vehicles=(2, 4, 8, 16), scenari=None, device='cpu'):
    """P1 - string stability del plotone, su TUTTI gli scenari salvo indicazione diversa.

    Gli scenari sono quelli del dataset esaustivo: gli stessi su cui girano C1 e C2. Prova e
    metriche sullo stesso perimetro, altrimenti i numeri non sono confrontabili fra loro.
    """
    champ = load_champion(device=device)
    idx = list(range(n_scenarios())) if scenari is None else list(scenari)
    out = {'per_N': {}, 'n_scenari': len(idx), 'n_vehicles': list(n_vehicles),
           'campione': {'variante': champ.variant, 'topologia': champ.topology,
                        'epoch': champ.epoch, 'val_loss': champ.val_loss}}

    for N in n_vehicles:
        h2t, amp, ttc, gap, jerk = [], [], [], [], []
        stabili = monotoni = convettivi = collisi = 0
        for i in idx:
            m = run_one(champ, i, N)
            h2t.append(float(m['head_to_tail_gain']))
            amp.append(float(m['max_amplification']))
            ttc.append(float(m['min_ttc_platoon']))
            gap.append(float(m['min_gap_platoon']))
            jerk.append(float(m['rms_jerk_mean']))
            stabili += int(bool(m['string_stable_headtail']))
            monotoni += int(bool(m['strict_monotone_decay']))
            convettivi += int(bool(m['convective_upstream']))
            collisi += int(bool(m['collided']))
        out['per_N'][N] = {
            'head_to_tail_mediana': _pct(h2t, 0.5),
            'head_to_tail_p99': _pct(h2t, 0.99),
            'head_to_tail_max': max(h2t),
            'max_amplification_p99': _pct(amp, 0.99),
            'max_amplification_max': max(amp),
            'n_string_stable': stabili,
            'n_monotone_decay': monotoni,
            'n_convective_upstream': convettivi,
            'n_collisi': collisi,
            'min_ttc_minimo': min(ttc),
            'min_gap_minimo': min(gap),
            'rms_jerk_mediana': _pct(jerk, 0.5),
            'n': len(idx),
            # La stabilita' si dichiara sulla CODA, non sulla mediana: nella sicurezza contano
            # i casi peggiori, ed e' esattamente quelli che una mediana cancella.
            'string_stable': _pct(h2t, 0.99) <= 1.0,
        }
    return out


def _main(argv):
    import argparse
    from . import artifacts
    ap = argparse.ArgumentParser(description='P1 - string stability del plotone')
    ap.add_argument('--n', type=int, nargs='+', default=[2, 4, 8, 16])
    ap.add_argument('--scenari', type=int, default=None,
                    help='usa solo i primi K scenari (per una prova rapida)')
    ap.add_argument('--out', default=os.path.join(RESULTS, 'P1_platoon.json'))
    ap.add_argument('--frontend', default='script')
    a = ap.parse_args(argv)
    sc = range(a.scenari) if a.scenari else None
    r = run_p1(n_vehicles=tuple(a.n), scenari=sc)
    artifacts.write(a.out, r, frontend=a.frontend, bitstream_sig='n/a (P1 e\' simulazione)')
    for N in a.n:
        v = r['per_N'][N]
        print('N=%-3d  head-to-tail mediana %.3f  p99 %.3f  max %.3f | string-stable %d/%d | '
              'collisioni %d | TTC min %.2f s'
              % (N, v['head_to_tail_mediana'], v['head_to_tail_p99'], v['head_to_tail_max'],
                 v['n_string_stable'], v['n'], v['n_collisi'], v['min_ttc_minimo']))
    print('artefatto: %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv[1:]))
