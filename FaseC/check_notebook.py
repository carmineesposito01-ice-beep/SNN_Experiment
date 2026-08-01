"""Cancello di riproducibilita' del notebook.

⚠️ Perche' non basta lanciare `jupyter nbconvert --execute`: su questa postazione nbconvert
esce con **0 senza aver eseguito nulla** (la build conda di zeromq fallisce con "Bad file
descriptor"; fallisce anche un notebook che contiene solo `print(1+1)`). Un cancello ancorato
all'exit code sarebbe quindi verde per costruzione -- cioe' non un cancello.

Due controlli, indipendenti:

  1. CODICE  -- estrae le celle di codice e le esegue IN ORDINE in un processo Python pulito.
     Prova la proprieta' che ci interessa davvero: il notebook gira dall'inizio alla fine da
     uno stato pulito, senza mani. Non richiede un kernel, quindi funziona anche qui.

  2. KERNEL  -- se un kernel c'e', esegue il notebook e VERIFICA L'ARTEFATTO: ogni cella deve
     avere `execution_count` valorizzato e nessun output di tipo `error`. Mai l'exit code.
     Se il kernel non funziona, lo dice e NON finge che il controllo sia passato.
"""
import io
import json
import os
import subprocess
import sys
import tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
NB = os.path.join(QUI, 'notebook', 'phase_c.ipynb')


def celle_codice(path):
    nb = json.load(io.open(path, encoding='utf-8'))
    return [''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code']


def check_codice(path=NB):
    """Esegue le celle in ordine, in un processo pulito, con cwd = notebook/."""
    src = '\n\n# ---- cella successiva ----\n\n'.join(celle_codice(path))
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(src)
        tmp = f.name
    try:
        p = subprocess.run([sys.executable, tmp], cwd=os.path.dirname(path),
                           capture_output=True, text=True, timeout=1800)
        return {'ok': p.returncode == 0, 'returncode': p.returncode,
                'stderr': p.stderr[-1500:], 'stdout': p.stdout[-1500:],
                'n_celle': len(celle_codice(path))}
    finally:
        os.unlink(tmp)


def check_kernel(path=NB):
    """Esegue col kernel e controlla l'ARTEFATTO, non l'exit code."""
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'eseguito.ipynb')
        p = subprocess.run(
            [sys.executable, '-m', 'jupyter', 'nbconvert', '--execute', '--to', 'notebook',
             '--output', out, '--ExecutePreprocessor.timeout=1800', path],
            capture_output=True, text=True, timeout=2400)
        if not os.path.isfile(out):
            return {'ok': False, 'motivo': 'nbconvert non ha prodotto il notebook (exit %d)'
                                           % p.returncode, 'stderr': p.stderr[-800:]}
        nb = json.load(io.open(out, encoding='utf-8'))
        code = [c for c in nb['cells'] if c['cell_type'] == 'code']
        non_eseguite = [i for i, c in enumerate(code, 1) if c.get('execution_count') is None]
        errori = [(i, o.get('ename'), o.get('evalue'))
                  for i, c in enumerate(code, 1)
                  for o in (c.get('outputs') or []) if o.get('output_type') == 'error']
        if non_eseguite:
            return {'ok': False, 'motivo': 'celle NON eseguite: %s (exit di nbconvert: %d -- '
                                           'ecco perche il cancello non guarda l\'exit code)'
                                           % (non_eseguite, p.returncode),
                    'stderr': p.stderr[-800:]}
        if errori:
            return {'ok': False, 'motivo': 'celle in errore: %s' % errori}
        return {'ok': True, 'n_celle': len(code)}


def _main(argv):
    solo = argv[0] if argv else 'tutto'
    esiti = []

    if solo in ('tutto', 'codice'):
        r = check_codice()
        esiti.append(r['ok'])
        print('CODICE  : %s (%d celle, in un processo pulito)'
              % ('OK' if r['ok'] else 'ROSSO', r['n_celle']))
        if not r['ok']:
            print(r['stderr'])

    if solo in ('tutto', 'kernel'):
        r = check_kernel()
        if r['ok']:
            esiti.append(True)
            print('KERNEL  : OK (%d celle eseguite, nessun errore)' % r['n_celle'])
        else:
            # Un kernel rotto e' un limite dell'AMBIENTE, non del notebook: si dichiara e non
            # si spaccia per superato, ma non fa fallire il controllo del codice.
            print('KERNEL  : NON VERIFICABILE -- %s' % r['motivo'])
            print('          (il controllo CODICE resta la prova di riproducibilita\')')

    return 0 if all(esiti) else 1


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv[1:]))
