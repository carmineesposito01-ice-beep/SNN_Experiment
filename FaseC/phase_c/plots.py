"""Grafici. LEGGONO gli artefatti, non rieseguono nulla.

E' la regola che tiene onesto il notebook: se un grafico ricalcolasse per conto suo, mostrerebbe
numeri che non stanno in nessun artefatto, e la figura direbbe una cosa mentre il file ne dice
un'altra. Qui si disegna solo cio' che e' gia' stato misurato e scritto.
"""
import json

import numpy as np


def _dati(sorgente):
    if isinstance(sorgente, (str, bytes)):
        return json.load(open(sorgente, encoding='utf-8'))['data']
    return sorgente.get('data', sorgente)


def accel_vs_traiettoria(traj, ax=None, titolo=None):
    """Accelerazione e traiettoria di uno scenario, sullo stesso asse dei tempi.

    `traj`: dict con 's', 'v', 'a' (e opzionalmente 'vl'), cioe' cio' che C2 produce.
    """
    import matplotlib.pyplot as plt
    if ax is None:
        _, ax = plt.subplots(3, 1, sharex=True, figsize=(9, 7))
    t = np.arange(len(traj['a'])) * 0.1

    ax[0].plot(t, traj['s'], lw=1.2)
    ax[0].set_ylabel('gap  s  [m]')
    ax[0].axhline(0, color='crimson', lw=0.8, ls='--')       # sotto zero = collisione
    ax[0].grid(alpha=0.3)

    ax[1].plot(t, traj['v'], lw=1.2, label='ego')
    if 'vl' in traj:
        ax[1].plot(t, traj['vl'], lw=1.0, ls='--', label='leader')
        ax[1].legend(fontsize=8)
    ax[1].set_ylabel('velocita  [m/s]')
    ax[1].grid(alpha=0.3)

    ax[2].plot(t, traj['a'], lw=1.2, color='darkorange')
    ax[2].set_ylabel('accel  [m/s2]')
    ax[2].set_xlabel('tempo [s]')
    ax[2].grid(alpha=0.3)
    # Il dominio del formato di uscita: sfix13_En8 arriva a +-16 m/s2.
    ax[2].axhline(16, color='grey', lw=0.6, ls=':')
    ax[2].axhline(-16, color='grey', lw=0.6, ls=':')

    if titolo:
        ax[0].set_title(titolo)
    return ax


def p1_distribuzione(sorgente, ax=None):
    """La distribuzione di head-to-tail per ogni N: e' il grafico che spiega perche' il
    conteggio degli stabili non e' monotono -- la fascia attorno a 1 si svuota."""
    import matplotlib.pyplot as plt
    d = _dati(sorgente)
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 5))
    for N in sorted(d['per_N'], key=int):
        g = np.array(list(d['per_N'][N]['head_to_tail_per_scenario'].values()))
        ax.hist(np.log10(g), bins=30, histtype='step', lw=1.6, label='N=%s' % N)
    ax.axvline(0.0, color='crimson', lw=1.0, ls='--')        # log10(1) = 0: la soglia
    ax.set_xlabel('log10( head-to-tail gain )   -- a destra della linea il plotone AMPLIFICA')
    ax.set_ylabel('scenari')
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_title('P1 - %d scenari perturbati (%d degeneri esclusi)'
                 % (d['perimetro']['n_perturbati'], d['perimetro']['n_degeneri']))
    return ax


def p1_tabella(sorgente):
    """Le righe di P1 come lista di dict, per stamparle o metterle in un DataFrame."""
    d = _dati(sorgente)
    righe = []
    for N in sorted(d['per_N'], key=int):
        v = d['per_N'][N]
        righe.append({'N': int(N), 'mediana': v['head_to_tail_mediana'],
                      'p95': v['head_to_tail_p95'], 'max': v['head_to_tail_max'],
                      'stabili': '%d/%d' % (v['n_string_stable'], v['n_stabilita']),
                      'collisioni': '%d/%d' % (v['n_collisi'], v['n_sicurezza']),
                      'TTC_min_s': v['min_ttc_minimo'], 'gap_min_m': v['min_gap_minimo']})
    return righe


def c3_distribuzione(sorgente, ax=None):
    """La corrente per CONDIZIONE, come distribuzione.

    E' un box plot e non un istogramma perche' il numero di punti e' piccolo (repliche, non
    campioni): un istogramma su 8 valori disegnerebbe una forma che i dati non sostengono.
    E non e' una barra sola, perche' su una differenza di pochi mA un valore singolo non e' un
    risultato -- e' un'illusione di precisione.
    """
    import matplotlib.pyplot as plt
    d = _dati(sorgente)
    per_cond = {}
    for p in d['punti']:
        per_cond.setdefault('%s/%s' % (p['cfg'], p['gating']), []).append(float(p['mA']))
    etichette = sorted(per_cond)
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 5))
    ax.boxplot([per_cond[k] for k in etichette], tick_labels=etichette, showmeans=True)
    ax.set_ylabel('corrente di scheda [mA]')
    ax.set_xlabel('condizione (bitstream / gating)')
    ax.grid(alpha=0.3, axis='y')
    lo, hi = d['tj_window']
    ax.set_title('C3 - %d punti, banda termica [%.0f, %.0f] degC, seme %s'
                 % (len(d['punti']), lo, hi, d['seed']))
    return ax


def c3_tabella(sorgente):
    """Le differenze di C3 come righe leggibili, con la separabilita' DICHIARATA.

    `separabile=False` non e' un fallimento della misura: e' il risultato. Sostituirlo con un
    numero preso dentro il rumore lo sarebbe.
    """
    d = _dati(sorgente)
    righe = []
    for nome, v in sorted(d['differenze'].items()):
        righe.append({'confronto': nome,
                      'delta_mW': v['delta_mW_per_istanza'],
                      'incertezza_mW': v['incertezza_mW'],
                      'n_istanze': v['n_istanze'],
                      'esito': 'separabile' if v['separabile'] else 'NON separabile'})
    return righe


def c3_deriva_termica(sorgente, ax=None):
    """Tj a ogni punto, nell'ordine in cui i punti sono stati MISURATI.

    Serve a vedere se la deriva termica e' rimasta scorrelata dalla condizione. Se le
    condizioni si allineassero con la temperatura, la differenza fra loro conterrebbe anche
    la deriva -- ed e' esattamente cio' che il sorteggio esiste per impedire.
    """
    import matplotlib.pyplot as plt
    d = _dati(sorgente)
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4))
    punti = sorted(d['punti'], key=lambda p: p['idx'])
    cond = sorted({'%s/%s' % (p['cfg'], p['gating']) for p in punti})
    for k in cond:
        xs = [p['idx'] for p in punti if '%s/%s' % (p['cfg'], p['gating']) == k]
        ys = [p['tj'] for p in punti if '%s/%s' % (p['cfg'], p['gating']) == k]
        ax.plot(xs, ys, 'o', ms=5, label=k)
    lo, hi = d['tj_window']
    ax.axhspan(lo, hi, color='green', alpha=0.07)
    ax.set_xlabel('ordine di misura (SORTEGGIATO)')
    ax.set_ylabel('Tj [degC]')
    ax.legend(fontsize=8, ncol=3)
    ax.grid(alpha=0.3)
    ax.set_title('C3 - se una condizione si raggruppasse in temperatura, la differenza '
                 'conterrebbe la deriva')
    return ax
