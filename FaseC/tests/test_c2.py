"""Il plant del processore e l'anello chiuso.

Il valore di questi test non e' mostrare che l'anello gira: e' fissare l'ORDINE DI UPDATE e il
teletrasporto del cut-in, cioe' i due punti in cui un port 1:1 smette di essere 1:1 producendo
traiettorie plausibili. E provare che C2 si rifiuta di partire su un plant rotto.
"""
import pytest

from phase_c.plant_ps import step_plant, run_plant, plant_par, DT
from phase_c.c2_closedloop import run_c2, check_plant_par, PlantParFailure, compare_trajectories


# ------------------------------------------------------------------- l'ordine di update

def test_il_gap_usa_la_velocita_NUOVA():
    """qz_cl_sim.m:26-27. Usare la v VECCHIA da 599 disallineamenti su 600 (misurato in T7a)."""
    s2, v2 = step_plant(s=30.0, v=20.0, vl=21.0, accel=1.0, dt=0.1)
    assert v2 == pytest.approx(20.1)
    assert s2 == pytest.approx(30.0 + (21.0 - 20.1) * 0.1)
    assert s2 != pytest.approx(30.0 + (21.0 - 20.0) * 0.1), 'ha usato la v vecchia'


def test_la_velocita_satura_a_zero():
    """max(0, v + acc*DT): una decelerazione forte non manda la velocita' sotto zero."""
    _, v2 = step_plant(s=30.0, v=0.5, vl=10.0, accel=-20.0, dt=0.1)
    assert v2 == 0.0


def test_il_gap_NON_e_clippato_in_basso():
    """Il commento in qz_cl_sim e' esplicito: il gap puo' andare sotto zero, ed e' cosi' che
    si rileva la collisione. Clipparlo nasconderebbe proprio l'evento che conta."""
    s2, _ = step_plant(s=0.05, v=10.0, vl=0.0, accel=0.0, dt=0.1)
    assert s2 < 0.0


# ----------------------------------------------------------------------- il cut-in

def test_il_cut_in_TELETRASPORTA_il_gap_al_passo_indicato():
    """Il gap viene sostituito di netto PRIMA di calcolare dv, non fatto evolvere."""
    visti = []

    def accel(s, v, dv, vl, first):
        visti.append(s)
        return 0.0

    run_plant(s_init=40.0, v_init=20.0, vl_all=[20.0] * 5,
              accel_fun=accel, cut_in=(3, 8.0))
    assert visti[:2] == [40.0, 40.0], 'prima del cut-in il gap e\' quello iniziale'
    assert visti[2] == 8.0, 'al passo 3 (base 1, come in MATLAB) il gap e\' quello nuovo'
    assert visti[3] == 8.0, 'dopo il cut-in evolve normalmente (qui vl==v: resta 8)'


def test_il_cut_in_e_in_BASE_1_come_in_matlab():
    """Sbagliare la base sposta il teletrasporto di un passo: traiettoria plausibile e diversa."""
    visti = []
    run_plant(40.0, 20.0, [20.0] * 5,
              lambda s, v, dv, vl, first: visti.append(s) or 0.0, cut_in=(1, 8.0))
    assert visti[0] == 8.0, 'cut_in=(1, ...) deve agire al PRIMO passo'


def test_senza_cut_in_il_gap_evolve_e_basta():
    visti = []
    run_plant(40.0, 20.0, [20.0] * 5,
              lambda s, v, dv, vl, first: visti.append(s) or 0.0, cut_in=None)
    assert all(abs(x - 40.0) < 1e-9 for x in visti)      # vl == v: gap costante


def test_first_e_vero_SOLO_al_primo_passo():
    firsts = []
    run_plant(40.0, 20.0, [20.0] * 4,
              lambda s, v, dv, vl, first: firsts.append(first) or 0.0)
    assert firsts == [True, False, False, False]


def test_la_collisione_ferma_l_anello():
    r = run_plant(0.5, 30.0, [0.0] * 100, lambda *a: 0.0)
    assert r['collided'] and r['n'] < 100
    assert r['impact_dv'] > 0


# ------------------------------------------------------------------------- PLANT-PAR

def _riferimento(n=50):
    """Riferimento generato DAL PLANT STESSO: se il PLANT-PAR non e' verde qui, e' rotto."""
    r = run_plant(40.0, 20.0, [20.0 + 0.5 * (k % 7) for k in range(n)],
                  lambda s, v, dv, vl, first: 0.3 - 0.02 * dv)
    return r


def test_plant_par_verde_sul_proprio_riferimento():
    assert plant_par(_riferimento())['bit_esatto']


def test_plant_par_ROSSO_se_il_riferimento_e_alterato():
    """Il cancello deve poter fallire, altrimenti non prova niente."""
    ref = _riferimento()
    ref['s'] = list(ref['s'])
    ref['s'][10] += 1e-9
    r = plant_par(ref)
    assert not r['bit_esatto'] and r['first']['k'] == 10


def test_c2_RIFIUTA_di_partire_se_il_plant_par_e_rosso():
    with pytest.raises(PlantParFailure, match='attribuirebbe all\'acceleratore'):
        run_c2(driver=None, scenari=[], plant_par_result={'nmismatch': 7, 'n': 600,
                                                          'first': {'k': 3, 'ds': 1e-9}})


def test_check_plant_par_passa_quando_e_verde():
    assert check_plant_par({'nmismatch': 0, 'n': 600, 'first': None})


# ------------------------------------------------------------- confronto delle traiettorie

def test_traiettorie_identiche_sono_bit_esatte():
    r = _riferimento()
    assert compare_trajectories(r, r)['bit_esatto']


def test_una_traiettoria_TRONCATA_non_e_bit_esatta():
    """Lunghezze diverse = collisione in un punto diverso: e' una differenza, non un dettaglio."""
    a = _riferimento()
    b = dict(a); b['s'] = a['s'][:-5]
    assert not compare_trajectories(a, b)['bit_esatto']
