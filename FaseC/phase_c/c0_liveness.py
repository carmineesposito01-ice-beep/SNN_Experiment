"""C0 - il bus risponde e i registri ritengono. PRIMA di qualunque inferenza.

Il corpus SoC prescrive un registro di identificazione come primo test del bring-up. Questo
wrapper non ne ha uno, ma i quattro registri d'ingresso sono leggibili (snniidm_axi_lite.v:192-195
restituisce slv_reg0..3): la scrittura con rilettura e' l'equivalente.

Un bus muto scoperto a meta' campagna e' tempo perso; scoperto qui costa 200 ms.

I pattern non sono casuali:
    00000000 / FFFFFFFF   linee incollate a 0 o a 1
    AAAAAAAA / 55555555   corti fra bit adiacenti (li trovano solo se alternati)
    0222CBBF              un valore reale del golden: prova il percorso, non solo i bit
"""
from .regmap import IIDM

PATTERNS = (0x00000000, 0xFFFFFFFF, 0xAAAAAAAA, 0x55555555, 0x0222CBBF)


class C0Failure(RuntimeError):
    pass


def _bit_incollati(bad):
    """I bit che differiscono SEMPRE e sempre nello stesso verso: la firma di un'incollatura.

    Si guarda il meccanismo, non quali pattern sono falliti: un bit incollato fa fallire i
    pattern in cui quel bit e' diverso dal valore incollato -- non i pattern "estremi".
    Classificare per pattern e' il modello sbagliato, ed e' il difetto che questo codice
    sostituisce.
    """
    sempre_uno = 0xFFFFFFFF     # bit che nella rilettura sono SEMPRE 1
    sempre_zero = 0xFFFFFFFF    # bit che nella rilettura sono SEMPRE 0
    diff_comune = 0xFFFFFFFF    # bit che differiscono in OGNI fallimento
    for _, w, g in bad:
        sempre_uno &= g
        sempre_zero &= ~g & 0xFFFFFFFF
        diff_comune &= (w ^ g)
    return diff_comune & sempre_uno, diff_comune & sempre_zero


def _diagnosi(bad, n_tot):
    """Il modo in cui fallisce dice quale sia la causa, e vale piu' del conteggio.

    Classifica SOLO quando la firma e' inequivocabile; altrimenti riporta l'evidenza grezza.
    Una diagnosi che pretende di riconoscere tutto e' una diagnosi che mente su qualcosa.
    """
    letti = {g for _, _, g in bad}
    if letti == {0} and len(bad) >= n_tot - len(PATTERNS):
        return ('ogni rilettura non nulla e\' tornata 0: il bus non arriva. Controllare per '
                'primi il clock dell\'interconnessione e la polarita\' del reset.')

    a1, a0 = _bit_incollati(bad)
    if a1 or a0:
        parti = []
        if a1:
            parti.append('bit %s incollati a 1' % sorted(i for i in range(32) if a1 >> i & 1))
        if a0:
            parti.append('bit %s incollati a 0' % sorted(i for i in range(32) if a0 >> i & 1))
        return '; '.join(parti) + '. Firma di linee incollate: sospettare il collegamento fisico.'

    indirizzi = {a for a, _, _ in bad}
    if len(indirizzi) == 1:
        return ('fallisce un solo registro (0x%02X) mentre gli altri ritengono: sospettare la '
                'mappa degli indirizzi, non il bus.' % indirizzi.pop())

    campioni = '; '.join('0x%02X: 0x%08X->0x%08X' % t for t in bad[:4])
    return ('nessuna firma inequivocabile (piu\' bit coinvolti, non costanti). Evidenza grezza, '
            'primi %d di %d: %s' % (min(4, len(bad)), len(bad), campioni))


def run_c0(overlay, regmap=IIDM):
    """Scrive e rilegge ogni pattern su ogni registro d'ingresso.

    Solleva C0Failure al primo quadro incoerente: proseguire dopo un bus muto significa
    misurare rumore e attribuirlo all'acceleratore.
    """
    bad = []
    for addr in regmap.INPUTS:
        for p in PATTERNS:
            overlay.write(addr, p)
            got = overlay.read(addr)
            if got != p:
                bad.append((addr, p, got))
    n_tot = len(regmap.INPUTS) * len(PATTERNS)
    if bad:
        a, w, g = bad[0]
        raise C0Failure('registro 0x%02X: scritto 0x%08X, riletto 0x%08X. %d pattern falliti su '
                        '%d. %s' % (a, w, g, len(bad), n_tot, _diagnosi(bad, n_tot)))
    return {'ok': True, 'n_patterns': len(PATTERNS), 'n_regs': len(regmap.INPUTS),
            'n_test': n_tot, 'n_bad': 0}
