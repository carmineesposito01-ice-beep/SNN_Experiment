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

RE = re.compile(r'^PROBE N=(\d+) max_dsp=(\d+) LUT=(\d+) FF=(\d+) DSP=(\d+) BRAM=(\d+) '
                r'FIT=(\w+) SEC=(\d+)')


def leggi(path=LOG):
    punti = []
    for riga in io.open(path, encoding='utf-8'):
        m = RE.match(riga.strip())
        if m:
            n, d, lut, ff, dsp, bram, fit, sec = m.groups()
            punti.append({'n_istanze': int(n), 'max_dsp': int(d), 'lut': int(lut),
                          'ff': int(ff), 'dsp': int(dsp), 'bram': int(bram),
                          'entra_dut_solo': fit == 'si', 'secondi': int(sec)})
    if not punti:
        raise RuntimeError('nessuna riga PROBE in %s: la sonda non ha prodotto misure' % path)
    return punti


def analizza(punti):
    per_dsp = {}
    for p in punti:
        per_dsp.setdefault(p['max_dsp'], []).append(p)
    for v in per_dsp.values():
        v.sort(key=lambda p: p['n_istanze'])

    ris = {'limiti_xc7z020': LIMITI, 'punti': punti, 'per_max_dsp': {}}

    for d, v in sorted(per_dsp.items()):
        entrano = [p['n_istanze'] for p in v if p['entra_dut_solo']]
        n_max = max(entrano) if entrano else 0
        vincolo = None
        # Il primo punto che NON entra dice QUALE risorsa e' il collo.
        fuori = [p for p in v if not p['entra_dut_solo']]
        if fuori:
            p = fuori[0]
            eccessi = {k: p[k] / float(LIMITI[k]) for k in ('lut', 'ff', 'dsp')}
            vincolo = max(eccessi, key=eccessi.get)
        ris['per_max_dsp'][str(d)] = {
            'n_max_dut_solo': n_max, 'vincolo': vincolo,
            'lut_al_massimo': next((p['lut'] for p in v if p['n_istanze'] == n_max), None),
        }

    # Linearita': se le istanze fossero state FUSE dal sintetizzatore, le LUT non scalerebbero.
    base = next((p for p in punti if p['n_istanze'] == 1 and p['max_dsp'] == 220), None)
    if base:
        lin = [{'n': p['n_istanze'], 'lut_su_lut1_per_n': round(p['lut'] / (base['lut'] * p['n_istanze']), 4)}
               for p in sorted(punti, key=lambda x: x['n_istanze'])
               if p['max_dsp'] == 220]
        ris['linearita'] = {
            'rapporto_per_n': lin,
            'nota': ('rapporto ~1 = le istanze NON sono state fuse. Si allontana da 1 quando il '
                     'tetto ai DSP obbliga a spostare moltiplicatori in fabric.')}

    # Il numero deployabile: la sonda misura il DUT SOLO. Va sottratto il contorno.
    d220 = ris['per_max_dsp'].get('220', {})
    n_dut = d220.get('n_max_dut_solo')
    if n_dut:
        lut_al_max = d220['lut_al_massimo']
        margine = LIMITI['lut'] - lut_al_max
        ris['deployabile'] = {
            'n_max_dut_solo': n_dut,
            'lut_usate': lut_al_max,
            'lut_margine': margine,
            'contorno_stimato_1_istanza': CONTORNO_1_ISTANZA,
            'avvertenza': (
                'la sonda misura il DUT DA SOLO: niente wrapper AXI, niente interconnessione. '
                'In T7b il contorno costava %d LUT e %d FF per una istanza. Con %d istanze il '
                'margine e\' %d LUT (%.1f%% del dispositivo): il numero deployabile va '
                'CONFERMATO con una sintesi che includa il wrapper, non dedotto da qui.'
                % (CONTORNO_1_ISTANZA['lut'], CONTORNO_1_ISTANZA['ff'], n_dut, margine,
                   100.0 * margine / LIMITI['lut'])),
        }
    return ris


def _main():
    ris = analizza(leggi())
    io.open(OUT, 'w', encoding='utf-8', newline='').write(
        json.dumps(ris, indent=1, ensure_ascii=False, sort_keys=True))
    print('punti: %d' % len(ris['punti']))
    for d, v in sorted(ris['per_max_dsp'].items(), key=lambda x: -int(x[0])):
        print('  max_dsp=%-4s  entrano fino a N=%-2s (DUT solo)  collo: %s'
              % (d, v['n_max_dut_solo'], v['vincolo']))
    dep = ris.get('deployabile')
    if dep:
        print()
        print('  margine a N=%d: %d LUT (%.1f%%)' %
              (dep['n_max_dut_solo'], dep['lut_margine'],
               100.0 * dep['lut_margine'] / LIMITI['lut']))
    print('artefatto: %s' % OUT)
    return 0


if __name__ == '__main__':
    raise SystemExit(_main())
