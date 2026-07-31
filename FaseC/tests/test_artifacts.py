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
