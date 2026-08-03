"""I grafici.

Un grafico non provato si rompe la prima volta che c'e' la scheda -- cioe' nel momento
peggiore, quando l'operatore ha la campagna in corso e non il tempo di aggiustare il codice.
Qui si prova che girino sulla forma ESATTA che produce `cli._stadio_c3`, ricostruita col codice
vero (`plan_sequence` + `aggregate` + `differenza_mW`) invece che scritta a mano: un artefatto
finto scritto a mano proverebbe che i grafici leggono l'artefatto che immagino io.
"""
import json
import os
import random

import matplotlib
matplotlib.use('Agg')                                   # headless, come nel notebook
import matplotlib.pyplot as plt                         # noqa: E402
import pytest                                           # noqa: E402

from phase_c import RESULTS, plots                      # noqa: E402
from phase_c.c3_power import (aggregate, differenza_mW, plan_sequence,      # noqa: E402
                              punti_di_misura)

TJ_WINDOW = (35.0, 60.0)


@pytest.fixture
def artefatto_c3(tmp_path):
    """Una campagna sintetica, costruita con lo STESSO codice che la eseguira' davvero."""
    rng = random.Random(0)
    base = {'blank/-': 380.0, 'x1/off': 402.0, 'x1/on': 395.0,
            'x2/off': 424.0, 'x2/on': 410.0}
    seq = plan_sequence(punti_di_misura(), repeats=8, seed=42)
    punti = []
    for i, (c, g) in enumerate(seq):
        tj = 44.0 + 0.004 * i + rng.uniform(-0.15, 0.15)         # deriva lenta, come la vera
        punti.append({'idx': i, 'cfg': c, 'gating': g, 'tj': tj, 'vccint': 0.998,
                      'mA': base['%s/%s' % (c, g)] + rng.gauss(0, 0.6),
                      'tj_dopo': tj, 'deriva_c': 0.0})
    agg = aggregate(punti, TJ_WINDOW)
    dati = {'punti': punti, 'seed': 42, 'tj_window': TJ_WINDOW, 'aggregato': agg,
            'differenze': {
                'logica (x1 - blank)': differenza_mW(agg, 'blank/-', 'x1/on'),
                'gating su x1 (on - off)': differenza_mW(agg, 'x1/off', 'x1/on'),
                'gating su x2 (on - off)': differenza_mW(agg, 'x2/off', 'x2/on', n_istanze=2)}}
    p = tmp_path / 'c3.json'
    p.write_text(json.dumps({'data': dati, 'prov': {}}), encoding='utf-8')
    return str(p)


def test_la_distribuzione_c3_si_disegna(artefatto_c3):
    ax = plots.c3_distribuzione(artefatto_c3)
    assert 'seme 42' in ax.get_title(), 'il seme deve restare leggibile SUL grafico'
    assert len(ax.get_xticklabels()) == 5, 'cinque condizioni, non tre configurazioni'
    plt.close('all')


def test_la_deriva_termica_si_disegna_nell_ordine_di_MISURA(artefatto_c3):
    """L'asse orizzontale e' l'ordine sorteggiato: se una condizione si raggruppasse in
    temperatura, la differenza fra condizioni conterrebbe anche la deriva."""
    ax = plots.c3_deriva_termica(artefatto_c3)
    assert 'SORTEGGIATO' in ax.get_xlabel()
    xs = ax.lines[0].get_xdata()
    assert len(xs) == 8 and list(xs) == sorted(xs)
    plt.close('all')


def test_la_tabella_c3_riporta_il_verso_giusto_e_la_separabilita(artefatto_c3):
    """Il gating acceso deve consumare MENO: un segno invertito qui sarebbe una conclusione
    ribaltata, e nessun altro controllo la prenderebbe."""
    r = {x['confronto']: x for x in plots.c3_tabella(artefatto_c3)}
    assert r['gating su x1 (on - off)']['delta_mW'] < 0
    assert r['logica (x1 - blank)']['delta_mW'] > 0
    assert all(x['esito'] in ('separabile', 'NON separabile') for x in r.values())


def test_una_differenza_dentro_il_rumore_si_LEGGE_come_non_separabile(tmp_path):
    """L'altro verso: la tabella deve saper dire "non separabile", altrimenti riporta sempre
    un numero e la colonna dell'esito non informa."""
    punti = [{'idx': i, 'cfg': c, 'gating': g, 'tj': 45.0, 'vccint': 0.998,
              'mA': 400.0 + (i % 7)}
             for i, (c, g) in enumerate([('x1', 'on'), ('x1', 'off')] * 10)]
    agg = aggregate(punti, TJ_WINDOW)
    dati = {'punti': punti, 'seed': 1, 'tj_window': TJ_WINDOW, 'aggregato': agg,
            'differenze': {'gating (on - off)': differenza_mW(agg, 'x1/off', 'x1/on')}}
    p = tmp_path / 'c3_rumore.json'
    p.write_text(json.dumps({'data': dati, 'prov': {}}), encoding='utf-8')
    assert plots.c3_tabella(str(p))[0]['esito'] == 'NON separabile'


# ------------------------------------------------------------------ P1, sull'artefatto vero

@pytest.mark.skipif(not os.path.isfile(os.path.join(RESULTS, 'p1.json')),
                    reason='results/p1.json non ancora prodotto')
def test_i_grafici_p1_girano_sull_artefatto_REALE():
    p1 = os.path.join(RESULTS, 'p1.json')
    righe = plots.p1_tabella(p1)
    assert righe and all('mediana' in r for r in righe)
    plots.p1_distribuzione(p1)
    plt.close('all')
