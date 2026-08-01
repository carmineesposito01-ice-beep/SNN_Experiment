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


def _overlay(regmap=IIDM, mock_golden=None):
    """(overlay, sorgente). Prova la scheda; se non c'e', usa il mock e lo DICHIARA."""
    try:
        from pynq import Overlay                                  # noqa: F401
    except ImportError:
        if mock_golden is None:
            raise SchedaAssente(
                'PYNQ non disponibile e nessun golden per il mock: questo stadio richiede la '
                'scheda. Vedi RUNBOOK.md.')
        from .mock_overlay import MockOverlay
        return MockOverlay(golden=mock_golden, regmap=regmap), 'mock'
    raise NotImplementedError(
        'caricamento dell\'overlay reale: da scrivere quando la scheda e\' accendibile '
        '(RUNBOOK.md, passo 1). Il driver e tutti gli stadi sono gia\' pronti e collaudati '
        'contro il mock.')


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
        raise SchedaAssente(
            'lo stadio %r richiede la scheda accendibile. Il codice e\' pronto e collaudato '
            'contro il mock (%d test); la procedura di esecuzione e\' in RUNBOOK.md.'
            % (stage, 102))

    artifacts.write(path, dati, frontend=frontend, bitstream_sig=bit, sorgente=sorgente)
    return dati, path


def _main(argv):
    import argparse
    ap = argparse.ArgumentParser(description='Fase C - entry-point condiviso dalle due facciate')
    ap.add_argument('stage', choices=list(STADI) + ['list'])
    ap.add_argument('--frontend', default='script')
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--scenari', type=int, default=None,
                    help='usa solo i primi K scenari. Serve al cancello di parita\': su tutti '
                         'e 99 costerebbe mezz\'ora, e un cancello che costa mezz\'ora non '
                         'viene eseguito.')
    a = ap.parse_args(argv)

    if a.stage == 'list':
        for s in STADI:
            print('%-4s %s' % (s, 'senza scheda' if s in SENZA_SCHEDA else 'richiede la scheda'))
        return 0
    kw = {'scenari': range(a.scenari)} if a.scenari else {}
    try:
        _, path = run_stage(a.stage, frontend=a.frontend, out_dir=a.out_dir, **kw)
    except SchedaAssente as e:
        print('SCHEDA-ASSENTE: %s' % e)
        return 3
    print('artefatto: %s' % path)
    return 0


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv[1:]))
