"""P1 - il plotone.

Il rischio da cui questi test proteggono non e' un crash: e' misurare la rete SBAGLIATA, o
misurare la cosa giusta e poi dichiararla sulla statistica sbagliata.
"""
import inspect

import pytest

from phase_c import platoon


# ------------------------------------------------------ misura la rete giusta, col motore giusto

def test_usa_il_motore_CHE_REGGE_L_EVENTPROP():
    """utils.platoon_eval.simulate_platoon da solo chiama forward_step con un tensore 2D, che
    il layer eventprop rifiuta: reggeva solo la famiglia baseline. Il motore corretto e'
    sim.ui.platoon.run_platoon, che inietta EventPropStepper via l'hook additivo."""
    src = inspect.getsource(platoon)
    assert 'from sim.ui.platoon import run_platoon' in src
    assert 'from utils.platoon_eval import simulate_platoon' not in src


def test_il_motore_applica_la_quantizzazione_po2_dell_hardware():
    """P1 deve misurare la rete DEPLOYATA. EventPropStepper quantizza i pesi a potenze di due,
    come l'export che ha generato il blocco: se un giorno smettesse, P1 misurerebbe la rete
    float di training e nessuno se ne accorgerebbe dai numeri."""
    import sim.eventprop_stepper as st
    assert 'po2_quantize' in inspect.getsource(st.EventPropStepper.__init__)


# ------------------------------------------------------------------ le metriche sono quelle vere

def test_le_chiavi_attese_esistono_davvero(champ_e_scenario):
    champ, i = champ_e_scenario
    m = platoon.run_one(champ, i, n_vehicles=3)
    for k in platoon.CHIAVI:
        assert k in m


def test_se_il_motore_cambiasse_forma_lo_diremmo(monkeypatch, champ_e_scenario):
    champ, i = champ_e_scenario
    monkeypatch.setattr(platoon, 'CHIAVI', platoon.CHIAVI + ('metrica_inesistente',))
    with pytest.raises(KeyError, match='l\'aggregato sarebbe vuoto'):
        platoon.run_one(champ, i, n_vehicles=3)


# ------------------------------------------------------------------- l'aggregato e la coda

def test_p1_aggrega_per_N():
    r = platoon.run_p1(n_vehicles=(2, 3), scenari=range(2))
    assert set(r['per_N']) == {2, 3}
    for N in (2, 3):
        v = r['per_N'][N]
        for k in ('head_to_tail_mediana', 'head_to_tail_p99', 'max_amplification_p99',
                  'n_string_stable', 'n_collisi', 'min_ttc_minimo', 'n'):
            assert k in v
        assert v['n'] == 2


def test_la_stabilita_si_dichiara_sulla_CODA_non_sulla_mediana():
    """Nella sicurezza contano i casi peggiori, ed e' esattamente quelli che la mediana
    cancella. Se questo test cadesse, P1 potrebbe dichiarare stabile un plotone che amplifica
    nel 40% degli scenari."""
    r = platoon.run_p1(n_vehicles=(2,), scenari=range(2))
    v = r['per_N'][2]
    assert v['string_stable'] == (v['head_to_tail_p99'] <= 1.0)


def test_l_artefatto_porta_la_provenienza_del_campione():
    r = platoon.run_p1(n_vehicles=(2,), scenari=range(1))
    c = r['campione']
    assert c['variante'] == 'eventprop_alif_full'
    assert c['topologia']['rank'] == 16


@pytest.fixture(scope='module')
def champ_e_scenario():
    from phase_c.params import load_champion
    return load_champion(), 0
