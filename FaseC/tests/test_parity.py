"""Il cancello di parita' fra le due facciate, e la marcatura della sorgente.

Due difetti che questi test rendono impossibili:
  * una facciata che contiene logica propria (i numeri divergono e nessuno se ne accorge);
  * un artefatto prodotto col MOCK scambiato per uno prodotto sul SILICIO.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from c_frontend_parity import compare                             # noqa: E402

from phase_c import artifacts, cli                                # noqa: E402


def _scrivi(p, dati, frontend, sorgente='silicio', bit='abc'):
    artifacts.write(p, dati, frontend=frontend, bitstream_sig=bit, sorgente=sorgente)


# ------------------------------------------------------------------------ il cancello

def test_parita_verde_se_i_dati_coincidono(tmp_path):
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    _scrivi(a, {'nmismatch': 0, 'n': 600}, 'script')
    _scrivi(b, {'nmismatch': 0, 'n': 600}, 'notebook')
    assert compare(a, b)['ok']


def test_parita_ROSSA_se_un_numero_differisce(tmp_path):
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    _scrivi(a, {'nmismatch': 0}, 'script')
    _scrivi(b, {'nmismatch': 1}, 'notebook')
    r = compare(a, b)
    assert not r['ok'] and 'nmismatch' in r['diff']


def test_parita_ROSSA_se_una_facciata_ha_girato_sul_MOCK(tmp_path):
    """Numeri identici ma sorgenti diverse NON sono lo stesso risultato."""
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    _scrivi(a, {'nmismatch': 0}, 'script', sorgente='silicio')
    _scrivi(b, {'nmismatch': 0}, 'notebook', sorgente='mock')
    r = compare(a, b)
    assert not r['ok'] and 'sorgente' in r['diff_prov']


def test_parita_ROSSA_se_il_bitstream_e_diverso(tmp_path):
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    _scrivi(a, {'x': 1}, 'script', bit='AAA')
    _scrivi(b, {'x': 1}, 'notebook', bit='BBB')
    assert not compare(a, b)['ok']


# --------------------------------------------------------------------------- il cli

def test_gli_stadi_sono_dichiarati_e_p1_gira_senza_scheda():
    assert 'p1' in cli.SENZA_SCHEDA
    assert set(cli.STADI) == {'c0', 'c1', 'c2', 'c3', 'p1'}


def test_uno_stadio_sconosciuto_e_un_errore_esplicito():
    with pytest.raises(ValueError, match='sconosciuto'):
        cli.run_stage('c9')


def test_gli_stadi_su_silicio_dicono_CHE_SERVE_LA_SCHEDA_invece_di_fingere():
    """Il difetto peggiore sarebbe restituire numeri dal mock come se fossero misure."""
    for s in ('c0', 'c1', 'c2', 'c3'):
        with pytest.raises(cli.SchedaAssente, match='richiede la scheda'):
            cli.run_stage(s)


def test_p1_dal_cli_scrive_l_artefatto_con_la_sorgente(tmp_path):
    dati, path = cli.run_stage('p1', frontend='script', out_dir=str(tmp_path),
                               n_vehicles=(2,), scenari=range(2))
    assert os.path.basename(path) == 'p1.json'
    obj = json.load(open(path, encoding='utf-8'))
    assert obj['prov']['sorgente'] == 'simulazione'
    assert obj['prov']['frontend'] == 'script'
    assert obj['data']['per_N']['2']['n_sicurezza'] == 2 or dati['per_N'][2]['n_sicurezza'] == 2


def test_LE_DUE_FACCIATE_sullo_stesso_stadio_danno_lo_STESSO_artefatto(tmp_path):
    """Il cancello vero: stessa funzione, due facciate, artefatti identici a meno dei volatili."""
    da = tmp_path / 'script'
    db = tmp_path / 'notebook'
    da.mkdir(); db.mkdir()
    kw = dict(n_vehicles=(2,), scenari=range(2))
    _, pa = cli.run_stage('p1', frontend='script', out_dir=str(da), **kw)
    _, pb = cli.run_stage('p1', frontend='notebook', out_dir=str(db), **kw)
    r = compare(pa, pb)
    assert r['ok'], r.get('msg')
