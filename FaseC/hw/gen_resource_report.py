"""Da P3_probe.log all'artefatto. LEGGE il log della sonda, non ricalcola nulla.

Il numero che serve al filone C e' uno solo: quante istanze del composto entrano nello
Zynq-7020. Ma va dato con la sua condizione al contorno, perche' la sonda misura il DUT DA
SOLO -- senza il wrapper AXI e senza l'interconnessione, che nel deployment reale ci sono.
"""
import io
import json
import os
import re
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
FASEC = os.path.dirname(QUI)
LOG = os.path.join(FASEC, 'results', 'P3_probe.log')
OUT = os.path.join(FASEC, 'results', 'P3_resources.json')

# xc7z020clg400-1
LIMITI = {'lut': 53200, 'ff': 106400, 'dsp': 220, 'bram': 140}

# Costo del contorno, misurato in T7b (sweep.json, gerarchia): top - u_dut, per UNA istanza.
# Wrapper AXI + glue + interconnessione. Non e' incluso nella sonda.
CONTORNO_1_ISTANZA = {'lut': 8453 - 7974, 'ff': 4556 - 3794}

# `unita=` e' stato aggiunto dopo i primi 11 punti: le righe vecchie non ce l'hanno e sono
# tutte `dut`. Il gruppo e' opzionale invece che obbligatorio, cosi' il log storico resta
# leggibile -- riscriverlo a mano sarebbe fabbricare una prova.
RE = re.compile(r'^PROBE (?:unita=(\w+) )?N=(\d+) max_dsp=(\d+) LUT=(\d+) FF=(\d+) DSP=(\d+) '
                r'BRAM=(\d+) FIT=(\w+) SEC=(\d+)')


def leggi(path=LOG):
    punti = []
    for riga in io.open(path, encoding='utf-8'):
        m = RE.match(riga.strip())
        if m:
            unita, n, d, lut, ff, dsp, bram, fit, sec = m.groups()
            punti.append({'unita': unita or 'dut',
                          'n_istanze': int(n), 'max_dsp': int(d), 'lut': int(lut),
                          'ff': int(ff), 'dsp': int(dsp), 'bram': int(bram),
                          'entra': fit == 'si', 'secondi': int(sec)})
    if not punti:
        raise RuntimeError('nessuna riga PROBE in %s: la sonda non ha prodotto misure' % path)
    return punti


def _per_unita(punti, unita):
    per_dsp = {}
    for p in punti:
        if p['unita'] == unita:
            per_dsp.setdefault(p['max_dsp'], []).append(p)
    for v in per_dsp.values():
        v.sort(key=lambda p: p['n_istanze'])

    out = {}
    for d, v in sorted(per_dsp.items()):
        entrano = [p['n_istanze'] for p in v if p['entra']]
        n_max = max(entrano) if entrano else 0
        vincolo = None
        fuori = [p for p in v if not p['entra']]      # il primo che non entra dice il collo
        if fuori:
            p = fuori[0]
            eccessi = {k: p[k] / float(LIMITI[k]) for k in ('lut', 'ff', 'dsp')}
            vincolo = max(eccessi, key=eccessi.get)
        lut_max = next((p['lut'] for p in v if p['n_istanze'] == n_max), None)
        out[str(d)] = {'n_max': n_max, 'vincolo': vincolo, 'lut_al_massimo': lut_max,
                       'lut_margine': (LIMITI['lut'] - lut_max) if lut_max else None,
                       'lut_margine_pct': (round(100.0 * (LIMITI['lut'] - lut_max) / LIMITI['lut'], 1)
                                           if lut_max else None)}
    return out


def analizza(punti):
    unita = sorted({p['unita'] for p in punti})
    ris = {'limiti_xc7z020': LIMITI, 'punti': punti,
           'unita_misurate': unita,
           'per_unita': {u: _per_unita(punti, u) for u in unita}}

    # Compatibilita' con la forma precedente dell'artefatto: `dut` resta in `per_max_dsp`.
    ris['per_max_dsp'] = {d: {'n_max_dut_solo': v['n_max'], 'vincolo': v['vincolo'],
                              'lut_al_massimo': v['lut_al_massimo']}
                          for d, v in ris['per_unita'].get('dut', {}).items()}

    # Linearita': se le istanze fossero state FUSE dal sintetizzatore, le LUT non scalerebbero.
    for u in unita:
        base = next((p for p in punti
                     if p['unita'] == u and p['n_istanze'] == 1 and p['max_dsp'] == 220), None)
        if not base:
            continue
        lin = [{'n': p['n_istanze'],
                'lut_su_lut1_per_n': round(p['lut'] / (base['lut'] * p['n_istanze']), 4)}
               for p in sorted(punti, key=lambda x: x['n_istanze'])
               if p['unita'] == u and p['max_dsp'] == 220]
        ris.setdefault('linearita_per_unita', {})[u] = {
            'rapporto_per_n': lin,
            'nota': ('rapporto ~1 = le istanze NON sono state fuse. Si allontana da 1 quando il '
                     'tetto ai DSP obbliga a spostare moltiplicatori in fabric.')}
    if 'dut' in ris.get('linearita_per_unita', {}):
        ris['linearita'] = ris['linearita_per_unita']['dut']

    # ------------------------------------------------------------------ il numero deployabile
    dut = ris['per_unita'].get('dut', {}).get('220')
    wrp = ris['per_unita'].get('wrapper', {}).get('220')
    dep = {}
    if dut:
        dep['n_max_dut_solo'] = dut['n_max']
        dep['lut_margine_dut'] = dut['lut_margine']
    if wrp:
        # Misurato: l'unita' deployabile include il wrapper AXI. Questo e' IL numero.
        dep['n_max_wrapper'] = wrp['n_max']
        dep['lut_usate_wrapper'] = wrp['lut_al_massimo']
        dep['lut_margine_wrapper'] = wrp['lut_margine']
        dep['lut_margine_wrapper_pct'] = wrp['lut_margine_pct']
        dep['nota'] = (
            'MISURATO col wrapper AXI incluso: %d istanze, margine %d LUT (%.1f%%). Resta fuori '
            'la sola interconnessione AXI del block design (in T7b: 352 LUT e 426 FF per UNO '
            'slave; con piu\' slave cresce).'
            % (wrp['n_max'], wrp['lut_margine'], wrp['lut_margine_pct']))
    else:
        dep['contorno_stimato_1_istanza'] = CONTORNO_1_ISTANZA
        dep['nota'] = (
            'la sonda ha misurato SOLO il DUT: niente wrapper AXI, niente interconnessione. In '
            'T7b il contorno costava %d LUT e %d FF per una istanza. Il numero deployabile va '
            'CONFERMATO con `./hw/probe_resources.sh "<N>" "220" wrapper`, non dedotto da qui.'
            % (CONTORNO_1_ISTANZA['lut'], CONTORNO_1_ISTANZA['ff']))
    ris['deployabile'] = dep
    return ris


def _main():
    ris = analizza(leggi())
    io.open(OUT, 'w', encoding='utf-8', newline='').write(
        json.dumps(ris, indent=1, ensure_ascii=False, sort_keys=True))
    print('punti: %d   unita misurate: %s' % (len(ris['punti']), ris['unita_misurate']))
    for u in ris['unita_misurate']:
        print('  --- %s ---' % u)
        for d, v in sorted(ris['per_unita'][u].items(), key=lambda x: -int(x[0])):
            print('    max_dsp=%-4s  entrano fino a N=%-2s  collo: %-4s  margine LUT: %s'
                  % (d, v['n_max'], v['vincolo'],
                     ('%d (%.1f%%)' % (v['lut_margine'], v['lut_margine_pct'])
                      if v['lut_margine'] is not None else '-')))
    print()
    print('  %s' % ris['deployabile'].get('nota', ''))
    print('artefatto: %s' % OUT)
    return 0


if __name__ == '__main__':
    raise SystemExit(_main())
