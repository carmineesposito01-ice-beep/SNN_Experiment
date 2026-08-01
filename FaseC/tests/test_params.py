"""Il campione e gli scenari.

Il valore di questi test e' impedire di misurare la rete SBAGLIATA: e' un errore che non si
manifesta come un crash ma come una tabella di numeri plausibili e senza valore.
"""
import pytest

from phase_c import params


# ------------------------------------------------------------------------- il campione

def test_il_campione_e_quello_dell_esportatore_non_uno_scelto_a_mano():
    """Il nome si legge da scripts/export_champions.py, non si ricopia."""
    assert params.champion_name() == 'PE_t05_gp0002'


def test_il_campione_caricato_ha_la_topologia_DEPLOYATA():
    h = params.load_champion()
    assert h.variant == 'eventprop_alif_full'
    assert h.topology == {'hidden': 32, 'input': 4, 'rank': 16, 'output': 5}


def test_il_cancello_sulla_topologia_PUO_fallire(monkeypatch):
    """Un cancello che non si e' mai visto fallire non e' un cancello."""
    monkeypatch.setattr(params, '_champ', None)
    monkeypatch.setattr(params, 'VARIANTE', 'baseline')
    with pytest.raises(RuntimeError, match='non e\' quello deployato'):
        params.load_champion()
    params._champ = None


def test_un_esportatore_di_forma_diversa_viene_segnalato(monkeypatch, tmp_path):
    p = tmp_path / 'fake.py'
    p.write_text('CHAMPIONS = {}\n', encoding='utf-8')
    monkeypatch.setattr(params, '_EXPORTER', str(p))
    with pytest.raises(RuntimeError, match='catena di provenienza'):
        params.champion_name()


# -------------------------------------------------------------------------- gli scenari

def test_ci_sono_99_scenari():
    assert params.n_scenarios() == 99


def test_gt_params_sono_cinque_e_positivi():
    p = params.load_gt_params(0)
    assert p.shape == (5,)
    assert (p > 0).all(), 'v0, T, s0, a, b devono essere tutti positivi'


def test_scenari_diversi_hanno_parametri_diversi():
    """Se fossero tutti uguali, P1 misurerebbe UN caso ripetuto 99 volte."""
    ps = [tuple(params.load_gt_params(i)) for i in range(10)]
    assert len(set(ps)) > 1


def test_il_leader_ha_600_campioni():
    assert params.load_leader(0).shape == (600,)


def test_lo_scenario_completo_ha_quel_che_serve_a_C2():
    sc = params.load_scenario(0)
    for k in ('idx', 'nome', 'regime', 's_init', 'v_init', 'vl', 'gt_params', 'cut_in'):
        assert k in sc
    assert sc['idx'] == 1, 'i file golden di T7a sono numerati in base 1'
    assert sc['s_init'] > 0 and sc['v_init'] > 0


def test_il_cut_in_e_None_quando_non_c_e_e_una_coppia_quando_c_e():
    """Un terzo del dataset ha il cut-in: se lo perdessimo, C2 divergerebbe su quegli scenari."""
    cuts = [params.load_scenario(i)['cut_in'] for i in range(params.n_scenarios())]
    con = [c for c in cuts if c is not None]
    assert con, 'nessuno scenario col cut-in: la lettura del campo e\' sbagliata'
    assert len(con) < len(cuts), 'tutti col cut-in: idem'
    k, gap = con[0]
    assert isinstance(k, int) and k >= 1 and gap > 0
