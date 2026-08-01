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


# Soglia di perturbazione del leader. Non e' scelta a occhio: nel dataset gli scenari
# `static_target` hanno deviazione standard ESATTAMENTE 0, e il successivo vale 0,279 m/s.
# Lo stacco e' netto, quindi qualunque valore in mezzo da' la stessa partizione.
SOGLIA_PERTURBAZIONE = 1e-6
WARMUP_FRAC = 0.3


def _pct(vals, q):
    """Percentile vero (interpolazione lineare), non `elemento in posizione floor(q*n)`.

    La versione ingenua, con n=99 e q=0,99, restituisce l'indice 98 -- cioe' il MASSIMO.
    "p99" e "max" diventavano due colonne con lo stesso numero: una statistica che non
    distingue nulla, e che non si vede finche' non si guardano i due valori affiancati.
    """
    return float(np.percentile(np.asarray(vals, dtype=np.float64), 100.0 * q))


def leader_std(i):
    """Ampiezza della perturbazione del leader, a regime."""
    vl = load_leader(i)
    return float(np.std(vl[int(len(vl) * WARMUP_FRAC):]))


def partiziona_scenari(idx):
    """(perturbati, degeneri).

    La string stability e' il rapporto fra l'oscillazione in coda e quella in testa: senza
    oscillazione in testa il denominatore e' rumore numerico (`std[0] + 1e-9`) e il rapporto
    esplode a 10^5-10^7. Non e' un plotone instabile -- e' una grandezza INDEFINITA.

    Sono gli scenari `static_target`: leader a velocita' costante per costruzione. Restano
    validi per le metriche di sicurezza (collisioni, gap, TTC), dove un leader fermo e' un
    caso di car-following legittimo; escono solo dalla string stability.
    """
    pert = [i for i in idx if leader_std(i) > SOGLIA_PERTURBAZIONE]
    degen = [i for i in idx if leader_std(i) <= SOGLIA_PERTURBAZIONE]
    return pert, degen


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
    pert, degen = partiziona_scenari(idx)

    out = {'per_N': {}, 'n_vehicles': list(n_vehicles),
           'perimetro': {
               'n_totale': len(idx),
               'n_perturbati': len(pert),
               'n_degeneri': len(degen),
               'idx_degeneri_base1': [i + 1 for i in degen],
               'perche': ('gli scenari `static_target` hanno il leader a velocita\' costante: '
                          'la string stability e\' il rapporto fra l\'oscillazione in coda e '
                          'quella in testa, e senza oscillazione in testa e\' INDEFINITA (il '
                          'denominatore diventa rumore numerico). Restano nelle metriche di '
                          'sicurezza, escono da quelle di stabilita\'.')},
           'campione': {'variante': champ.variant, 'topologia': champ.topology,
                        'epoch': champ.epoch, 'val_loss': champ.val_loss}}

    for N in n_vehicles:
        h2t, amp = [], []
        stabili = monotoni = convettivi = 0
        ttc_sani, gap, jerk = [], [], []
        collisi = 0
        for i in idx:
            m = run_one(champ, i, N)
            gap.append(float(m['min_gap_platoon']))
            jerk.append(float(m['rms_jerk_mean']))
            coll = bool(m['collided'])
            collisi += int(coll)
            if not coll:
                # Il TTC di uno scenario che collide e' negativo (gap < 0): aggregarlo col
                # minimo farebbe leggere "peggior TTC" dove in realta' c'e' una collisione,
                # che e' gia' contata a parte.
                ttc_sani.append(float(m['min_ttc_platoon']))
            if i in pert:
                h2t.append(float(m['head_to_tail_gain']))
                amp.append(float(m['max_amplification']))
                stabili += int(bool(m['string_stable_headtail']))
                monotoni += int(bool(m['strict_monotone_decay']))
                convettivi += int(bool(m['convective_upstream']))

        # Senza nemmeno uno scenario perturbato la stabilita' non e' "vera" ne' "falsa":
        # e' INDEFINITA, e va scritto None invece di un numero qualsiasi.
        ha_stab = bool(h2t)
        out['per_N'][N] = {
            # --- stabilita': SOLO sugli scenari con una perturbazione da propagare
            'n_stabilita': len(h2t),
            'head_to_tail_mediana': _pct(h2t, 0.5) if ha_stab else None,
            'head_to_tail_p95': _pct(h2t, 0.95) if ha_stab else None,
            'head_to_tail_max': max(h2t) if ha_stab else None,
            'max_amplification_p95': _pct(amp, 0.95) if ha_stab else None,
            'max_amplification_max': max(amp) if ha_stab else None,
            'n_string_stable': stabili,
            'n_monotone_decay': monotoni,
            'n_convective_upstream': convettivi,
            # Dichiarazione STRETTA: stabile solo se lo e' in OGNI scenario. Nella sicurezza
            # conta la coda, e un plotone che amplifica in un caso su ottantotto amplifica.
            'string_stable': (stabili == len(h2t)) if ha_stab else None,
            # --- sicurezza e comfort: su TUTTI gli scenari
            'n_sicurezza': len(idx),
            'n_collisi': collisi,
            'min_ttc_minimo': (min(ttc_sani) if ttc_sani else float('inf')),
            'min_gap_minimo': min(gap),
            'rms_jerk_mediana': _pct(jerk, 0.5),
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
    pm = r['perimetro']
    print('perimetro: %d scenari, di cui %d con perturbazione del leader; %d degeneri esclusi '
          'dalla stabilita (static_target): %s'
          % (pm['n_totale'], pm['n_perturbati'], pm['n_degeneri'], pm['idx_degeneri_base1']))
    for N in a.n:
        v = r['per_N'][N]
        print('N=%-3d | stabilita su %d: h2t mediana %.3f  p95 %.3f  max %.3f | '
              'string-stable %d/%d | sicurezza su %d: collisioni %d  TTC min %.2f s  gap min %.2f m'
              % (N, v['n_stabilita'], v['head_to_tail_mediana'], v['head_to_tail_p95'],
                 v['head_to_tail_max'], v['n_string_stable'], v['n_stabilita'],
                 v['n_sicurezza'], v['n_collisi'], v['min_ttc_minimo'], v['min_gap_minimo']))
    print('artefatto: %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv[1:]))
