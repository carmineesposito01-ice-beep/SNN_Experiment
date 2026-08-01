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
