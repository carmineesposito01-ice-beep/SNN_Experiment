"""Le due facciate, sullo stesso stato, devono produrre artefatti IDENTICI.

Se divergono, una delle due contiene logica propria: e' un difetto, non una curiosita'. E'
questo che trasforma la ridondanza fra script e notebook da rassicurante a informativa.

La vista stabile esclude i campi che le facciate hanno il DIRITTO di avere diversi (orario,
nome della facciata, directory). Non esclude i dati, ne' la firma del bitstream, ne' la
sorgente: un numero prodotto col mock e uno prodotto sul silicio non sono lo stesso risultato,
anche quando coincidono.
"""
import sys

from phase_c.artifacts import read, stable_view


def compare(pa, pb):
    a, b = stable_view(read(pa)), stable_view(read(pb))
    if a == b:
        return {'ok': True, 'diff': None}
    diff_dati = sorted(k for k in set(a['data']) | set(b['data'])
                       if a['data'].get(k) != b['data'].get(k))
    diff_prov = sorted(k for k in set(a['prov']) | set(b['prov'])
                       if a['prov'].get(k) != b['prov'].get(k))
    return {'ok': False, 'diff': diff_dati, 'diff_prov': diff_prov,
            'msg': ('le facciate divergono su dati=%s prov=%s: una delle due contiene logica '
                    'propria, oppure gli artefatti vengono da esecuzioni diverse'
                    % (diff_dati, diff_prov))}


def _main(argv):
    if len(argv) != 2:
        print('uso: c_frontend_parity.py <artefatto_script.json> <artefatto_notebook.json>')
        return 2
    r = compare(argv[0], argv[1])
    print('PARITA-OK' if r['ok'] else 'PARITA-ROSSA: ' + r['msg'])
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(_main(sys.argv[1:]))
