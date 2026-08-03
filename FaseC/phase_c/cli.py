"""Entry-point CONDIVISO dalle due facciate. Qui vive la logica degli stadi; fuori no.

`run_phase_c.sh` e `notebook/phase_c.ipynb` chiamano entrambe `run_stage()`. Se una delle due
contenesse logica propria, il cancello di parita' (`c_frontend_parity.py`) non potrebbe essere
verde, e la ridondanza fra le due facciate diventerebbe rassicurante invece che informativa.

⚠️ La cosa che questo modulo rende impossibile sbagliare: un artefatto prodotto col MOCK non
puo' essere scambiato per uno prodotto sul SILICIO. La sorgente sta nella provenienza, non e'
un campo volatile, e il cancello di parita' la confronta.
"""
import os
import sys

from . import RESULTS, artifacts
from .regmap import IIDM, TIER

STADI = ('c0', 'c1', 'c2', 'c3', 'p1')

# Stadi che si possono eseguire senza scheda. Gli altri, col mock, danno un artefatto
# marcato `mock`: utile per collaudare la catena, MAI un risultato.
SENZA_SCHEDA = ('p1',)


class SchedaAssente(RuntimeError):
    pass


BITSTREAM = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bitstream')


def _overlay(regmap=IIDM, mock_golden=None, cfg='x1'):
    """(overlay, sorgente). Prova la scheda; se non c'e', usa il mock e lo DICHIARA.

    ⚠️ Il ripiego sul mock e' consentito SOLO quando manca PYNQ, cioe' quando non si e' su
    scheda per niente. Se PYNQ c'e' ma il bitstream no, l'errore si propaga: ripiegare sul mock
    lì produrrebbe un artefatto marcato `mock` proprio nella sessione in cui l'operatore crede
    di stare misurando il silicio, ed e' il momento in cui l'etichetta serve di piu'.
    """
    try:
        import pynq                                               # noqa: F401
    except ImportError:
        if mock_golden is None:
            raise SchedaAssente(
                'PYNQ non disponibile e nessun golden per il mock: questo stadio richiede la '
                'scheda. Vedi RUNBOOK.md.')
        from .mock_overlay import MockOverlay
        return MockOverlay(golden=mock_golden, regmap=regmap), 'mock'

    from .overlay_hw import OverlayScheda
    return OverlayScheda(os.path.join(BITSTREAM, '%s.bit' % cfg), regmap=regmap), 'silicio'


def run_stage(stage, frontend='script', out_dir=None, **kw):
    """Esegue uno stadio, SCRIVE l'artefatto, restituisce (dati, percorso).

    `frontend` finisce nella provenienza ed e' volatile: e' l'unica cosa che le due facciate
    hanno il diritto di avere diversa.
    """
    if stage not in STADI:
        raise ValueError('stadio %r sconosciuto; quelli validi sono %s' % (stage, list(STADI)))
    out_dir = out_dir or RESULTS
    path = os.path.join(out_dir, '%s.json' % stage)

    if stage == 'p1':
        from . import platoon
        dati = platoon.run_p1(**kw)
        sorgente, bit = 'simulazione', 'n/a (P1 e\' simulazione)'
    else:
        dati, sorgente, bit = _stadio_su_scheda(stage, **kw)

    artifacts.write(path, dati, frontend=frontend, bitstream_sig=bit, sorgente=sorgente)
    return dati, path


def _stadio_su_scheda(stage, scenari=None, cfg='x1', seed=None, repeats=8, dmm=None, **kw):
    """Gli stadi che vogliono il silicio. La sorgente finisce nella provenienza."""
    from . import artifacts as _a
    from .golden import carica_scenari

    indici = list(scenari) if scenari is not None else range(1, 100)

    if stage == 'c3':
        return _stadio_c3(cfg=cfg, seed=seed, repeats=repeats, dmm=dmm, **kw)

    ov, sorgente = _overlay(cfg=cfg, **({'mock_golden': kw['mock_golden']}
                                        if 'mock_golden' in kw else {}))
    bit = _a.file_sig(os.path.join(BITSTREAM, '%s.bit' % cfg)) if sorgente == 'silicio' else 'mock'

    if stage == 'c0':
        from .c0_liveness import run_c0
        return run_c0(ov), sorgente, bit

    from .driver import SnnIidmDriver
    drv = SnnIidmDriver(ov)

    if stage == 'c1':
        from .c1_functional import run_c1
        return run_c1(drv, carica_scenari(indici)), sorgente, bit

    from .c2_closedloop import run_c2
    from .plant_ps import plant_par
    # PLANT-PAR PRIMA dell'anello: se la pianta del PS non coincide con quella dell'oracolo,
    # ogni scostamento dell'anello chiuso sarebbe attribuito al DUT invece che alla pianta.
    return run_c2(drv, kw['scenari_c2'], plant_par()), sorgente, bit


def _stadio_c3(cfg='x1', seed=None, repeats=8, dmm=None, csv_path=None, tj_window=(35.0, 60.0),
               **kw):
    """C3 non usa il driver: misura la scheda, non il DUT. Vuole il multimetro e l'XADC."""
    from .c3_power import esegui_campagna, aggregate, differenza_mW
    from .overlay_hw import BancoPynq
    from .xadc import read_tj_sysfs, read_vccint_sysfs, verifica_plausibile

    from .xadc import XadcAssente
    try:
        # Cancello PRIMA di partire: una lettura fallita non da' errore, da' un numero -- e una
        # Tj sbagliata non si vede nei dati di potenza, li rende solo inspiegabili.
        #
        # Questo controllo viene PRIMA di quello sul seme, e non per costo: senza scheda non c'e'
        # nessuna campagna, quindi il seme non e' ancora un errore. Cosi' `SchedaAssente` resta
        # l'esito UNIFORME di tutti gli stadi su silicio, che e' cio' che rende significativo
        # l'elenco SENZA_SCHEDA.
        verifica_plausibile(read_tj_sysfs(), read_vccint_sysfs())
    except XadcAssente as e:
        raise SchedaAssente('C3 richiede la scheda: %s' % e)

    if seed is None:
        raise ValueError(
            'C3 richiede un seed esplicito: e\' la decisione che rende la campagna ripetibile, '
            'e un default silenzioso darebbe una sequenza "sorteggiata" che nessuno ha scelto.')
    if dmm is None:
        from .dmm import PromptDMM
        dmm = PromptDMM()

    banco = BancoPynq(BITSTREAM, read_tj_sysfs, read_vccint_sysfs)
    r = esegui_campagna(dmm, banco, seed=seed, repeats=repeats,
                        csv_path=csv_path or os.path.join(RESULTS, 'c3_campagna.csv'), **kw)
    agg = aggregate(r['punti'], tj_window)
    r['aggregato'] = agg
    r['tj_window'] = tj_window
    r['differenze'] = {
        'logica (x1 - blank)': differenza_mW(agg, 'blank/-', 'x1/on'),
        'gating su x1 (on - off)': differenza_mW(agg, 'x1/off', 'x1/on'),
        'gating su x2 (on - off)': differenza_mW(agg, 'x2/off', 'x2/on', n_istanze=2),
    }
    return r, 'silicio', 'campagna su blank+x1+x2'


def _main(argv):
    import argparse
    ap = argparse.ArgumentParser(description='Fase C - entry-point condiviso dalle due facciate')
    ap.add_argument('stage', choices=list(STADI) + ['list'])
    ap.add_argument('--frontend', default='script')
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--seed', type=int, default=None,
                    help='seme della sequenza sorteggiata di C3. OBBLIGATORIO per c3: senza, '
                         'la campagna non e\' ripetibile.')
    ap.add_argument('--repeats', type=int, default=8, help='repliche per punto in C3')
    ap.add_argument('--cfg', default='x1', help='bitstream da caricare (c0/c1/c2)')
    ap.add_argument('--scenari', type=int, default=None,
                    help='usa solo i primi K scenari. Serve al cancello di parita\': su tutti '
                         'e 99 costerebbe mezz\'ora, e un cancello che costa mezz\'ora non '
                         'viene eseguito.')
    a = ap.parse_args(argv)

    if a.stage == 'list':
        for s in STADI:
            print('%-4s %s' % (s, 'senza scheda' if s in SENZA_SCHEDA else 'richiede la scheda'))
        return 0
    # ⚠️ `--scenari K` vuol dire "i primi K" per tutti gli stadi, ma la TRADUZIONE in indici
    # cambia, e non per una svista: sono due convenzioni reali, imposte dai dati.
    #
    #   p1   indicizza il DATASET, che e' un array          -> base 0, range(K)
    #   c*   indicizza i file dei golden `axi_stim_<i>.mem`, i = 1..99  -> base 1, range(1, K+1)
    #
    # Una traduzione sola non puo' essere giusta per entrambi: con base 1 su p1 si salta il
    # primo scenario e se ne prende uno in piu' in coda -- un perimetro diverso da quello
    # dichiarato, spostato di uno e silenzioso. (E' successo: vedi il test di parita' sotto.)
    kw = {}
    if a.scenari:
        kw['scenari'] = range(a.scenari) if a.stage == 'p1' else range(1, a.scenari + 1)
    if a.stage == 'c3':
        kw.update(seed=a.seed, repeats=a.repeats)
    else:
        kw.update(cfg=a.cfg)
    try:
        _, path = run_stage(a.stage, frontend=a.frontend, out_dir=a.out_dir, **kw)
    except SchedaAssente as e:
        print('SCHEDA-ASSENTE: %s' % e)
        return 3
    print('artefatto: %s' % path)
    return 0


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv[1:]))
