"""Il cancello del notebook deve poter diventare rosso.

E' il caso in cui la tentazione di fidarsi dell'exit code e' piu' forte: `jupyter nbconvert`
su questa postazione esce con 0 senza eseguire NULLA (zeromq rotto -- fallisce anche un
notebook che contiene solo `print(1+1)`). Un controllo ancorato all'exit code sarebbe quindi
verde per costruzione. Questi test provano che il nostro guarda invece l'esito reale.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_notebook                                              # noqa: E402


def _scrivi_nb(path, sorgenti):
    nb = {'cells': [{'cell_type': 'code', 'execution_count': None, 'metadata': {},
                     'outputs': [], 'source': [s]} for s in sorgenti],
          'metadata': {'kernelspec': {'name': 'python3', 'display_name': 'Python 3',
                                      'language': 'python'},
                       'language_info': {'name': 'python', 'version': '3'}},
          'nbformat': 4, 'nbformat_minor': 5}
    io.open(str(path), 'w', encoding='utf-8').write(json.dumps(nb))
    return str(path)


def test_un_notebook_sano_passa(tmp_path):
    p = _scrivi_nb(tmp_path / 'ok.ipynb', ['x = 21\n', 'assert x * 2 == 42\n'])
    r = check_notebook.check_codice(p)
    assert r['ok'] and r['n_celle'] == 2


def test_una_cella_ROTTA_lo_fa_diventare_rosso(tmp_path):
    p = _scrivi_nb(tmp_path / 'ko.ipynb', ['x = 1\n', 'raise RuntimeError("rotta apposta")\n'])
    r = check_notebook.check_codice(p)
    assert not r['ok'] and r['returncode'] != 0
    assert 'rotta apposta' in r['stderr']


def test_le_celle_girano_IN_ORDINE_e_condividono_lo_stato(tmp_path):
    """Se ogni cella girasse isolata, un notebook che dipende dall'ordine passerebbe lo stesso
    e la prova di riproducibilita' non varrebbe niente."""
    p = _scrivi_nb(tmp_path / 'ord.ipynb', ['y = 7\n', 'print(y * 6)\n'])
    r = check_notebook.check_codice(p)
    assert r['ok'] and '42' in r['stdout']


def test_l_ordine_SBAGLIATO_fallisce(tmp_path):
    p = _scrivi_nb(tmp_path / 'inv.ipynb', ['print(y * 6)\n', 'y = 7\n'])
    assert not check_notebook.check_codice(p)['ok']


def test_il_notebook_VERO_della_fase_c_e_sano():
    r = check_notebook.check_codice()
    assert r['ok'], r['stderr']
