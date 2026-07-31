"""C3 - potenza differenziale a livello di scheda.

Il PL consuma 114 mW su 1,5-2,5 W di scheda: in assoluto e' invisibile a un multimetro da 9999
conteggi. Ma il numero cercato non e' assoluto. Stesso hardware, stesso stato del processore,
cambia SOLO il bitstream:

    (b) - (a)   isola il PL          a = blank, b = una istanza
    (b) - (c)   il guadagno del gating   c = una istanza col gating spento

Il consumo del processore, dei regolatori e della periferia si cancella nella differenza.

Tre condizioni perche' la differenza significhi qualcosa. Qui sono CODICE, non raccomandazioni:

  1. ordine RANDOMIZZATO, non alternato. Un A/B/A e' vulnerabile proprio alla deriva che
     pretende di cancellare, e il bias di misura vale +-10% -- abbastanza a invertire una
     conclusione (Mytkowicz et al., ASPLOS 2009).
  2. Tj registrata a ogni punto, punti fuori equilibrio SCARTATI. La statica e' 103 mW su 114
     ed e' esponenziale nella temperatura (WP221).
  3. il risultato e' una DISTRIBUZIONE con l'incertezza dichiarata, non un numero. Un valore
     singolo su una differenza di pochi mA non e' un risultato, e' un'illusione di precisione.
"""
import random
import statistics


class ThermalReject(RuntimeError):
    pass


def plan_sequence(configs, repeats, seed):
    """Sequenza di misura SORTEGGIATA.

    Non alternata: alternare A/B/A/B correla la configurazione con l'istante, ed e' esattamente
    il modo in cui una deriva termica lenta si travestre da differenza fra configurazioni.
    Il seme va DICHIARATO nell'artefatto: senza, la sequenza non e' ripetibile.
    """
    if repeats < 1:
        raise ValueError('repeats deve essere >= 1')
    seq = [c for c in configs for _ in range(repeats)]
    random.Random(seed).shuffle(seq)
    return seq


def _pct(vals, q):
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * len(s)))]


def aggregate(points, tj_window):
    """Da punti grezzi a distribuzione per configurazione.

    `points`: [{'cfg', 'mA', 'tj'}, ...]. `tj_window`: (min, max) in gradi Celsius.
    I punti fuori banda si SCARTANO e il conteggio degli scartati resta nell'artefatto: un
    punto scartato in silenzio e' un punto che nessuno potra' piu' rimettere in discussione.
    """
    lo, hi = tj_window
    out = {}
    for cfg in sorted({p['cfg'] for p in points}):
        tutti = [p for p in points if p['cfg'] == cfg]
        buoni = [float(p['mA']) for p in tutti if lo <= float(p['tj']) <= hi]
        if not buoni:
            raise ThermalReject(
                'configurazione %r: nessuno dei %d punti sta nella banda termica '
                '[%.1f, %.1f] degC. La misura non e\' utilizzabile: la dispersione statica e\' '
                'esponenziale in Tj e la statica domina il consumo del PL.'
                % (cfg, len(tutti), lo, hi))
        b = sorted(buoni)
        q1, q3 = _pct(b, 0.25), _pct(b, 0.75)
        out[cfg] = dict(mediana=statistics.median(b), minimo=b[0], massimo=b[-1],
                        p99=_pct(b, 0.99), iqr=q3 - q1,
                        n=len(b), n_scartati=len(tutti) - len(buoni),
                        tj_min=min(float(p['tj']) for p in tutti),
                        tj_max=max(float(p['tj']) for p in tutti))
    return out


def differenza_mW(agg, a, b, volt=5.0, n_istanze=1):
    """(b - a) in mW per istanza, con l'incertezza propagata dalla dispersione.

    L'incertezza non e' un ornamento: se e' dello stesso ordine della differenza, la
    conclusione e' "non separabile con questo strumento" -- e va scritta cosi'.
    """
    for k in (a, b):
        if k not in agg:
            raise KeyError('configurazione %r assente dall\'aggregato' % k)
    d_mA = agg[b]['mediana'] - agg[a]['mediana']
    unc_mA = (agg[a]['iqr'] + agg[b]['iqr']) / 2.0
    d_mW = d_mA * volt / n_istanze
    u_mW = unc_mA * volt / n_istanze
    return {'delta_mW_per_istanza': d_mW, 'incertezza_mW': u_mW,
            'n_istanze': n_istanze, 'volt': volt,
            'separabile': abs(d_mW) > 2.0 * u_mW,
            'nota': ('differenza maggiore del doppio dell\'incertezza: separabile'
                     if abs(d_mW) > 2.0 * u_mW else
                     'differenza dello stesso ordine dell\'incertezza: NON separabile con '
                     'questo strumento. Aumentare le repliche o le istanze, oppure dichiararlo '
                     'come limite invece di riportare un numero.')}
