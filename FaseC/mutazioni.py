"""Analisi di MUTAZIONE sui moduli portanti di FaseC.

Rompe il codice in un punto alla volta e verifica che i test se ne accorgano. Una mutazione
SOPRAVVISSUTA e' un buco: quel comportamento non e' difeso da nessun test, e potrebbe cambiare
senza che nulla diventi rosso.

Ogni mutazione gira contro il SOLO file di test che dovrebbe coprirla. Se sopravvive li' ma
sarebbe presa altrove, e' comunque un'informazione: vuol dire che la corrispondenza
modulo -> file di test non regge -- ed e' successo davvero (vedi sotto).

ESITO 2026-08-03, prima passata: 92 mutazioni, 31 sopravvissute (66% prese). Le sopravvissute
NON erano sparse: quasi tutte erano condizioni al CONFINE -- `<=` che diventa `<` su una banda,
un dominio, una soglia di collisione. La suite provava il comportamento, quasi mai il bordo.
Aggiunte 18 prove al confine; le 14 mutazioni che cambiavano un RISULTATO sono ora tutte prese.

Restano vive per costruzione le mutazioni EQUIVALENTI (stringhe di avanzamento `i + 1`, rami di
diagnosi che cambiano quale messaggio esce ma non se il cancello scatta): non sono buchi.

Uso:  python mutazioni.py          (circa 12 minuti)
"""
import io
import os
import re
import subprocess
import sys

FASEC = r'D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulink_Importer\FaseC'

# modulo -> file di test che deve coprirlo
COPERTURA = {
    'regmap.py': 'test_regmap.py',
    'c0_liveness.py': 'test_c0.py',
    'c1_functional.py': 'test_c1.py',
    'c2_closedloop.py': 'test_c2.py',
    'plant_ps.py': 'test_c2.py',
    'c3_power.py': 'test_c3.py',
    'dmm.py': 'test_dmm.py',
    'xadc.py': 'test_xadc.py',
    'overlay_hw.py': 'test_overlay_hw.py',
    'artifacts.py': 'test_artifacts.py',
    'mock_overlay.py': 'test_mock_negative.py',
    'params.py': 'test_params.py',
}

# mutazioni testuali: (pattern, sostituzione, etichetta)
MUTAZIONI = [
    (r'(?<![<>=!])<=(?!=)', '<', '<= diventa <'),
    (r'(?<![<>=!])>=(?!=)', '>', '>= diventa >'),
    (r'(?<![<>=!])==(?!=)', '!=', '== diventa !='),
    (r'(?<![<>=!])!=(?!=)', '==', '!= diventa =='),
    (r'\bis not\b', 'is', 'is not diventa is'),
    (r'\bnot in\b', 'in', 'not in diventa in'),
    (r'(?<![\w.])True(?![\w])', 'False', 'True diventa False'),
    (r'(?<![\w.])and(?![\w])', 'or', 'and diventa or'),
    (r'(?<![\w.\d])\+ 1(?![\w\d])', '+ 0', '+1 diventa +0'),
]

MAX_PER_MODULO = 14


def righe_di_codice(src):
    """indici delle righe che contengono codice, non docstring/commenti."""
    fuori = []
    in_doc = False
    delim = None
    for i, r in enumerate(src.split('\n')):
        s = r.strip()
        if in_doc:
            if delim in s:
                in_doc = False
            continue
        if s.startswith('#') or not s:
            continue
        for d in ('"""', "'''"):
            if s.startswith(d):
                if s.count(d) == 1:
                    in_doc, delim = True, d
                break
        else:
            fuori.append(i)
    return fuori


def genera(src):
    """[(riga, colonna, etichetta, nuova_riga), ...]"""
    out = []
    linee = src.split('\n')
    for i in righe_di_codice(src):
        r = linee[i]
        if '#' in r:                                    # taglia il commento in coda
            r_cod = r[:r.index('#')]
        else:
            r_cod = r
        for pat, sub, etichetta in MUTAZIONI:
            for m in re.finditer(pat, r_cod):
                nuova = r[:m.start()] + sub + r[m.end():]
                out.append((i, m.start(), etichetta, nuova))
    return out


def main():
    os.chdir(FASEC)
    tot = sopravvissute = 0
    dettaglio = []

    for modulo, testfile in sorted(COPERTURA.items()):
        p = os.path.join('phase_c', modulo)
        originale = io.open(p, encoding='utf-8').read()
        mut = genera(originale)
        passo = max(1, len(mut) // MAX_PER_MODULO)
        scelte = mut[::passo][:MAX_PER_MODULO]
        print('%-20s %3d mutazioni possibili, ne provo %d  (contro %s)'
              % (modulo, len(mut), len(scelte), testfile), flush=True)

        for riga, col, etichetta, nuova in scelte:
            linee = originale.split('\n')
            linee[riga] = nuova
            io.open(p, 'w', encoding='utf-8', newline='').write('\n'.join(linee))
            try:
                r = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-x',
                                    os.path.join('tests', testfile)],
                                   capture_output=True, timeout=300)
                presa = r.returncode != 0
            except subprocess.TimeoutExpired:
                presa = True            # un test che non termina e' comunque un fallimento
            finally:
                io.open(p, 'w', encoding='utf-8', newline='').write(originale)

            tot += 1
            if not presa:
                sopravvissute += 1
                dettaglio.append((modulo, riga + 1, etichetta, nuova.strip()[:88]))
                print('   SOPRAVVISSUTA riga %d: %s' % (riga + 1, etichetta), flush=True)

    print()
    print('=' * 78)
    print('AUDIT D -- %d mutazioni, %d sopravvissute (%.0f%% prese)'
          % (tot, sopravvissute, 100.0 * (tot - sopravvissute) / tot if tot else 0))
    print('=' * 78)
    for modulo, riga, etichetta, testo in dettaglio:
        print('  %-18s riga %-4d %-24s  %s' % (modulo, riga, etichetta, testo))


if __name__ == '__main__':
    main()
