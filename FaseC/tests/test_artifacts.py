"""Ogni numero porta con se' da dove viene.

Serve a due cose distinte: (a) un risultato senza provenienza non e' verificabile a posteriori;
(b) il cancello di parita' fra le due facciate confronta gli artefatti, e puo' essere verde solo
se i campi volatili sono SEPARABILI invece che sparsi nel file.
"""
import json

import pytest

from phase_c import artifacts


def test_artefatto_porta_la_provenienza(tmp_path):
    p = tmp_path / 'c1.json'
    artifacts.write(p, {'nmismatch': 0, 'n': 600}, frontend='script', bitstream_sig='abc123')
    d = artifacts.read(p)
    assert d['data']['nmismatch'] == 0
    assert d['prov']['frontend'] == 'script'
    assert d['prov']['bitstream_sig'] == 'abc123'
    assert 'timestamp' in d['prov']


def test_stable_view_esclude_i_campi_volatili(tmp_path):
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    artifacts.write(a, {'x': 1}, frontend='script', bitstream_sig='s')
    artifacts.write(b, {'x': 1}, frontend='notebook', bitstream_sig='s')
    assert artifacts.stable_view(artifacts.read(a)) == artifacts.stable_view(artifacts.read(b))


def test_ma_NON_esclude_il_bitstream(tmp_path):
    """Due numeri identici ottenuti da bitstream diversi NON sono lo stesso risultato."""
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    artifacts.write(a, {'x': 1}, frontend='script', bitstream_sig='AAA')
    artifacts.write(b, {'x': 1}, frontend='notebook', bitstream_sig='BBB')
    assert artifacts.stable_view(artifacts.read(a)) != artifacts.stable_view(artifacts.read(b))


def test_una_differenza_nei_DATI_sopravvive_alla_vista_stabile(tmp_path):
    """Il cancello deve poter fallire: se stable_view appiattisse anche i dati, la parita'
    sarebbe verde per costruzione e non direbbe nulla."""
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    artifacts.write(a, {'nmismatch': 0}, frontend='script', bitstream_sig='s')
    artifacts.write(b, {'nmismatch': 1}, frontend='notebook', bitstream_sig='s')
    assert artifacts.stable_view(artifacts.read(a)) != artifacts.stable_view(artifacts.read(b))


def test_la_firma_e_il_CONTENUTO_non_il_nome(tmp_path):
    """Rinominare un file non ne cambia la firma; cambiarne un byte si."""
    x, y = tmp_path / 'uno.bit', tmp_path / 'due.bit'
    x.write_bytes(b'\x00\x01\x02' * 100)
    y.write_bytes(b'\x00\x01\x02' * 100)
    assert artifacts.file_sig(x) == artifacts.file_sig(y)
    y.write_bytes(b'\x00\x01\x03' * 100)
    assert artifacts.file_sig(x) != artifacts.file_sig(y)


def test_firma_di_un_file_assente_e_esplicita(tmp_path):
    with pytest.raises(FileNotFoundError):
        artifacts.file_sig(tmp_path / 'non_esiste.bit')


def test_l_artefatto_e_json_leggibile_a_mano(tmp_path):
    p = tmp_path / 'c1.json'
    artifacts.write(p, {'n': 3}, frontend='script', bitstream_sig='s')
    assert json.loads(p.read_text(encoding='utf-8'))['data']['n'] == 3


def test_le_chiavi_dell_artefatto_sono_ORDINATE(tmp_path):
    """Trovato dall'analisi di mutazione: togliere `sort_keys=True` non faceva fallire nulla.
    Senza, due esecuzioni identiche producono file diversi byte per byte -- il diff diventa
    illeggibile e il cancello di determinismo perde ogni significato."""
    import io as _io
    import json as _json
    p = str(tmp_path / 'a.json')
    artifacts.write(p, {'zeta': 1, 'alfa': 2, 'mu': {'y': 1, 'x': 2}},
                    frontend='script', bitstream_sig='s')
    testo = _io.open(p, encoding='utf-8').read()
    assert testo.index('"alfa"') < testo.index('"mu"') < testo.index('"zeta"')
    assert testo.index('"x"') < testo.index('"y"'), 'anche i livelli annidati'


def test_due_scritture_degli_STESSI_dati_danno_lo_stesso_file(tmp_path):
    """Il determinismo e' la ragione dell'ordinamento: cio' che cambia deve essere solo la
    provenienza volatile, non la disposizione delle chiavi."""
    import io as _io
    import json as _json
    dati = {'b': [3, 1, 2], 'a': {'q': 1, 'p': 0}}
    a, b = str(tmp_path / 'a.json'), str(tmp_path / 'b.json')
    artifacts.write(a, dati, frontend='script', bitstream_sig='s')
    artifacts.write(b, dati, frontend='script', bitstream_sig='s')
    ta = [r for r in _io.open(a, encoding='utf-8') if 'timestamp' not in r]
    tb = [r for r in _io.open(b, encoding='utf-8') if 'timestamp' not in r]
    assert ta == tb
