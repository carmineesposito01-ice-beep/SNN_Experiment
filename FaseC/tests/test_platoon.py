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
        for k in ('head_to_tail_mediana', 'head_to_tail_p95', 'max_amplification_p95',
                  'n_string_stable', 'n_collisi', 'min_ttc_minimo',
                  'n_stabilita', 'n_sicurezza'):
            assert k in v
        assert v['n_sicurezza'] == 2


def test_la_stabilita_si_dichiara_in_modo_STRETTO():
    """Stabile solo se lo e' in OGNI scenario. Un plotone che amplifica in un caso su
    ottantotto amplifica: una mediana, o anche un p95, cancellerebbe proprio quel caso."""
    r = platoon.run_p1(n_vehicles=(2,), scenari=range(2))
    v = r['per_N'][2]
    assert v['string_stable'] == (v['n_string_stable'] == v['n_stabilita'])


# --------------------------------------------- il perimetro: gli scenari degeneri

def test_gli_scenari_a_leader_COSTANTE_sono_riconosciuti():
    """Sono gli 11 `static_target`: deviazione standard del leader ESATTAMENTE 0."""
    pert, degen = platoon.partiziona_scenari(range(99))
    assert len(degen) == 11 and len(pert) == 88
    assert [i + 1 for i in degen] == [7, 16, 25, 34, 43, 52, 61, 70, 79, 88, 97]


def test_p1_ESCLUDE_i_degeneri_dalla_stabilita_ma_li_TIENE_nella_sicurezza():
    r = platoon.run_p1(n_vehicles=(2,), scenari=[0, 6])       # 6 (base 0) = idx 7, static_target
    assert r['perimetro']['n_degeneri'] == 1
    assert r['perimetro']['idx_degeneri_base1'] == [7]
    v = r['per_N'][2]
    assert v['n_stabilita'] == 1, 'lo scenario degenere non deve entrare nella stabilita'
    assert v['n_sicurezza'] == 2, 'ma deve restare nelle metriche di sicurezza'


def test_un_degenere_che_trapelasse_ESPLODE_o_finge_di_essere_perfetto():
    """Il cancello, provato in negativo su ENTRAMBE le facce del difetto.

    Con leader costante, `head_to_tail = std[coda] / (std[testa] + 1e-9)` ha il denominatore
    a zero esatto. Cosa esce dipende dalla coda, e misurato sui 99 scenari fa due cose diverse:

      * 2 su 11 (regime `truck`, idx 61 e 70): il follower conserva un'oscillazione residua
        di ~9e-4 m/s -> 9e-4 / 1e-9 = 901 331. Avvelena la coda della distribuzione.
      * 9 su 11: anche il follower si ferma -> 0 / 1e-9 = 0, che passa il test `<= 1` e viene
        contato come STRING-STABLE. Piu' insidioso del primo: non si vede.

    Le due facce hanno la stessa radice -- il rapporto e' indefinito senza perturbazione --
    e per questo la partizione le toglie entrambe.
    """
    from phase_c.params import load_champion
    c = load_champion()
    esplode = platoon.run_one(c, 60, n_vehicles=2)['head_to_tail_gain']    # base 0 -> idx 61
    finge = platoon.run_one(c, 6, n_vehicles=2)['head_to_tail_gain']       # base 0 -> idx 7
    assert esplode > 1e3, 'la faccia esplosiva non si presenta piu: motore cambiato?'
    assert finge == 0.0 and finge <= 1.0, 'la faccia silenziosa non si presenta piu'

    r = platoon.run_p1(n_vehicles=(2,), scenari=[0, 6, 60])
    v = r['per_N'][2]
    assert v['n_stabilita'] == 1, 'entrambi i degeneri devono restare fuori'
    assert v['head_to_tail_max'] < 10.0, 'un degenere e trapelato nell aggregato'


def test_se_TUTTI_gli_scenari_sono_degeneri_la_stabilita_e_INDEFINITA():
    """None, non un numero qualsiasi: e' una grandezza che non esiste, non una che vale zero."""
    r = platoon.run_p1(n_vehicles=(2,), scenari=[6])
    v = r['per_N'][2]
    assert v['n_stabilita'] == 0
    assert v['string_stable'] is None and v['head_to_tail_max'] is None
    assert v['n_sicurezza'] == 1, 'la sicurezza resta misurabile anche li'


def test_l_artefatto_porta_la_provenienza_del_campione():
    r = platoon.run_p1(n_vehicles=(2,), scenari=range(1))
    c = r['campione']
    assert c['variante'] == 'eventprop_alif_full'
    assert c['topologia']['rank'] == 16


@pytest.fixture(scope='module')
def champ_e_scenario():
    from phase_c.params import load_champion
    return load_champion(), 0


def test_uno_scenario_ESATTAMENTE_alla_soglia_finisce_in_UNA_delle_due_liste():
    """`pert` usa `>` e `degen` usa `<=`: insieme coprono tutto. Trovato dall'analisi di
    mutazione che con `<` uno scenario con std esattamente alla soglia sparirebbe da ENTRAMBE,
    uscendo dall'analisi senza che nessun conteggio lo segnali."""
    from phase_c import platoon as P

    valori = {1: 0.0, 2: P.SOGLIA_PERTURBAZIONE, 3: P.SOGLIA_PERTURBAZIONE * 2}
    vero = P.leader_std
    P.leader_std = lambda i: valori[i]
    try:
        pert, degen = P.partiziona_scenari([1, 2, 3])
    finally:
        P.leader_std = vero
    assert sorted(pert + degen) == [1, 2, 3], 'nessuno scenario puo\' sparire dalla partizione'
    assert 2 in degen, 'esattamente alla soglia = NON perturbato'
    assert pert == [3] and 1 in degen


def test_le_chiavi_degli_scenari_nell_artefatto_sono_in_BASE_1():
    """`{str(i + 1): g for i, g in zip(pert, h2t)}`: con `+0` ogni guadagno verrebbe attribuito
    allo scenario SBAGLIATO -- un risultato con l'etichetta di un altro. Trovato dall'analisi di
    mutazione; i file dei golden e gli altri artefatti usano la base 1."""
    import io
    import json
    import os
    from phase_c import RESULTS
    p = os.path.join(RESULTS, 'p1.json')
    if not os.path.isfile(p):
        import pytest as _p
        _p.skip('results/p1.json non ancora prodotto')
    d = json.load(io.open(p, encoding='utf-8'))['data']
    for N, v in d['per_N'].items():
        chiavi = [int(k) for k in v['head_to_tail_per_scenario']]
        assert min(chiavi) >= 1, 'N=%s: c\'e una chiave < 1, quindi base 0' % N
        assert max(chiavi) <= d['perimetro']['n_totale']
    # e coincidono col perimetro dichiarato dei perturbati
    degeneri = set(d['perimetro']['idx_degeneri_base1'])
    prima = next(iter(d['per_N'].values()))['head_to_tail_per_scenario']
    assert not (set(int(k) for k in prima) & degeneri), \
        'uno scenario degenere e finito fra i perturbati: le basi non coincidono'
