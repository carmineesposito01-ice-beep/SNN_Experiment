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


# ------------------- lo SMISTAMENTO degli stadi (analisi di mutazione)
#
# Senza scheda ogni stadio solleva SchedaAssente qualunque ramo prenda, quindi i test qui sopra
# non distinguono la rotta. Col mock invece si distingue: e se la rotta fosse sbagliata,
# `c1.json` conterrebbe il risultato di C0 -- un risultato con l'ETICHETTA SBAGLIATA, che e' il
# difetto che questa Fase teme di piu'.

def test_lo_stadio_c0_produce_il_risultato_di_C0(golden_scen1, tmp_path):
    dati, path = cli.run_stage('c0', frontend='script', out_dir=str(tmp_path),
                               mock_golden=[golden_scen1])
    assert path.endswith('c0.json')
    assert 'pattern' in repr(dati).lower() or 'bad' in dati or 'ok' in dati, \
        'c0.json deve contenere l\'esito della prova dei registri, non altro'
    assert 'bit_esatto' not in dati, 'questo e\' il risultato di C1, non di C0'


def test_lo_stadio_c1_produce_il_risultato_di_C1(golden_scen1, tmp_path):
    dati, path = cli.run_stage('c1', frontend='script', out_dir=str(tmp_path),
                               mock_golden=[golden_scen1], scenari=[golden_scen1.idx])
    assert path.endswith('c1.json')
    assert 'bit_esatto' in dati and 'nmismatch' in dati, \
        'c1.json deve contenere il confronto bit-esatto'
    assert dati['n_scenari'] == 1


def test_la_provenienza_dichiara_MOCK_quando_e_il_mock(golden_scen1, tmp_path):
    """La rotta giusta non basta: l'artefatto deve dire da dove viene."""
    import json
    _, path = cli.run_stage('c0', frontend='script', out_dir=str(tmp_path),
                            mock_golden=[golden_scen1])
    prov = json.load(open(path, encoding='utf-8'))['prov']
    assert prov['sorgente'] == 'mock' and prov['bitstream_sig'] == 'mock'


# ------------------- gli argomenti della facciata 1 (analisi di mutazione)
#
# `cli._main` non era esercitato da nessun test: le mutazioni sullo smistamento degli argomenti
# sopravvivevano tutte. E una di queste -- `range(1, K + 1)` che diventa `+ 0` -- ridurrebbe la
# copertura DICHIARATA di uno scenario senza che nulla lo segnali.

def _cattura_run_stage(monkeypatch):
    visti = {}

    def finto(stage, **kw):
        visti['stage'] = stage
        visti.update(kw)
        return {}, 'finto.json'

    monkeypatch.setattr(cli, 'run_stage', finto)
    return visti


def test_scenari_K_da_K_scenari_in_ENTRAMBE_le_convenzioni(monkeypatch):
    """`--scenari K` = «i primi K» per tutti gli stadi, ma gli indici NON sono gli stessi:
    p1 indicizza il dataset (un array, base 0), c* indicizza i file `axi_stim_<i>.mem` (base 1).

    Una traduzione sola non puo' essere giusta per entrambi, e sbaglia in SILENZIO: con la base 1
    su p1 si salta il primo scenario e se ne prende uno in piu' in coda -- un perimetro diverso
    da quello dichiarato, spostato di uno. Era esattamente il caso finche' l'analisi di mutazione
    non ha portato a chiedersi cosa significasse davvero quell'indice."""
    visti = _cattura_run_stage(monkeypatch)
    cli._main(['p1', '--scenari', '6'])
    assert list(visti['scenari']) == [0, 1, 2, 3, 4, 5], 'p1: base 0, i primi sei del dataset'

    visti2 = _cattura_run_stage(monkeypatch)
    cli._main(['c1', '--scenari', '6'])
    assert list(visti2['scenari']) == [1, 2, 3, 4, 5, 6], 'c1: base 1, axi_stim_1..6.mem'


def test_le_DUE_facciate_traducono_scenari_allo_STESSO_modo(monkeypatch):
    """`./run_phase_c.sh p1` passa da `platoon._main`, il cancello di parita' da `cli._main`.
    Se traducessero diversamente, i due artefatti coprirebbero perimetri diversi e la parita'
    fallirebbe per un motivo che non c'entra nulla con le facciate."""
    from phase_c import platoon

    class _Basta(Exception):
        pass

    # Ci interessa la TRADUZIONE, non il riassunto che `platoon._main` stampa dopo. Ricostruire
    # la struttura del risultato solo per farlo stampare vorrebbe dire provare la stampa.
    visti = {}

    def finto(stage, **kw):
        visti.update(stage=stage, **kw)
        raise _Basta

    monkeypatch.setattr(cli, 'run_stage', finto)
    try:
        platoon._main(['--scenari', '6', '--n', '2'])
    except _Basta:
        pass
    da_platoon = list(visti['scenari'])

    visti2 = _cattura_run_stage(monkeypatch)
    cli._main(['p1', '--scenari', '6'])
    assert da_platoon == list(visti2['scenari']) == [0, 1, 2, 3, 4, 5]


def test_senza_scenari_non_si_limita_nulla(monkeypatch):
    visti = _cattura_run_stage(monkeypatch)
    cli._main(['p1'])
    assert 'scenari' not in visti


def test_solo_c3_riceve_seme_e_repliche(monkeypatch):
    visti = _cattura_run_stage(monkeypatch)
    cli._main(['c3', '--seed', '42', '--repeats', '5'])
    assert visti['seed'] == 42 and visti['repeats'] == 5 and 'cfg' not in visti
    visti2 = _cattura_run_stage(monkeypatch)
    cli._main(['c1', '--cfg', 'x2'])
    assert visti2['cfg'] == 'x2' and 'seed' not in visti2


def test_list_ELENCA_e_non_esegue_nulla(monkeypatch, capsys):
    visti = _cattura_run_stage(monkeypatch)
    assert cli._main(['list']) == 0
    assert not visti, 'list non deve eseguire nessuno stadio'
    out = capsys.readouterr().out
    for s in cli.STADI:
        assert s in out
    assert 'senza scheda' in out and 'richiede la scheda' in out
