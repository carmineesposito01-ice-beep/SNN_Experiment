"""C3 e' la misura che puo' ingannare: 114 mW dentro 2 W, letti con un multimetro da 9999
conteggi. Questi test non provano che il numero sia giusto -- non c'e' hardware -- ma che il
METODO impedisca i tre modi noti di ottenere un numero credibile e sbagliato.
"""
import pytest

from phase_c.c3_power import plan_sequence, aggregate, differenza_mW, ThermalReject
from phase_c.xadc import at_equilibrium, EQ_BAND_C, EQ_N


CFG = ('blank', 'g0', 'g1')


# --------------------------------------------------------------- 1. l'ordine e' sorteggiato

def test_l_ordine_e_RANDOMIZZATO_non_alternato():
    """Mytkowicz 2009: il bias di misura vale +-10%, abbastanza a invertire una conclusione.
    Un A/B/A alternato correla la configurazione con l'istante ed e' vulnerabile proprio alla
    deriva che pretende di cancellare."""
    seqs = {tuple(plan_sequence(CFG, repeats=6, seed=s)) for s in range(8)}
    assert len(seqs) > 1, 'la sequenza non cambia col seme: non e\' sorteggiata'
    alternata = tuple(list(CFG) * 6)
    assert alternata not in seqs


def test_ogni_configurazione_compare_lo_STESSO_numero_di_volte():
    for s in range(5):
        seq = plan_sequence(CFG, repeats=6, seed=s)
        assert len(seq) == 18
        assert all(seq.count(c) == 6 for c in CFG)


def test_lo_stesso_seme_da_la_stessa_sequenza():
    """Il seme sta nell'artefatto: senza, la sequenza non e' ripetibile e la misura nemmeno."""
    assert plan_sequence(CFG, 6, 42) == plan_sequence(CFG, 6, 42)


def test_repeats_a_zero_e_un_errore_non_una_sequenza_vuota():
    with pytest.raises(ValueError):
        plan_sequence(CFG, repeats=0, seed=0)


# ------------------------------------------------------------------ 2. Tj come cancello

def test_i_punti_fuori_equilibrio_termico_si_SCARTANO():
    pts = [{'cfg': 'g0', 'mA': 400.0, 'tj': 45.0},
           {'cfg': 'g0', 'mA': 402.0, 'tj': 45.2},
           {'cfg': 'g0', 'mA': 398.0, 'tj': 61.0}]
    r = aggregate(pts, tj_window=(40.0, 50.0))
    assert r['g0']['n'] == 2 and r['g0']['n_scartati'] == 1


def test_gli_scartati_RESTANO_nell_artefatto():
    """Uno scarto silenzioso e' uno scarto che nessuno potra' piu' rimettere in discussione."""
    pts = [{'cfg': 'g0', 'mA': 400.0, 'tj': 45.0}, {'cfg': 'g0', 'mA': 1.0, 'tj': 90.0}]
    r = aggregate(pts, tj_window=(40.0, 50.0))
    assert r['g0']['n_scartati'] == 1
    assert r['g0']['tj_max'] == 90.0, 'la Tj estrema deve restare visibile'


def test_scarta_TUTTO_se_nessun_punto_e_in_banda():
    with pytest.raises(ThermalReject, match='esponenziale in Tj'):
        aggregate([{'cfg': 'g0', 'mA': 400.0, 'tj': 70.0}], tj_window=(40.0, 50.0))


def test_il_criterio_di_equilibrio_e_DICHIARATO_e_funziona_nei_due_versi():
    assert at_equilibrium([45.0 + 0.01 * k for k in range(EQ_N)]) is True
    assert at_equilibrium([45.0 + 0.2 * k for k in range(EQ_N)]) is False   # deriva
    assert at_equilibrium([45.0] * (EQ_N - 1)) is False                     # troppo pochi
    assert EQ_BAND_C == 0.5 and EQ_N == 12


# ------------------------------------------------------ 3. distribuzione, non un numero

def test_il_risultato_e_una_DISTRIBUZIONE():
    pts = [{'cfg': 'g1', 'mA': 400.0 + 0.1 * i, 'tj': 45.0} for i in range(20)]
    r = aggregate(pts, tj_window=(40.0, 50.0))
    for k in ('mediana', 'p99', 'minimo', 'massimo', 'iqr', 'n', 'n_scartati'):
        assert k in r['g1']


def test_una_differenza_NETTA_e_dichiarata_separabile():
    pts = ([{'cfg': 'g0', 'mA': 400.0 + 0.05 * i, 'tj': 45.0} for i in range(20)] +
           [{'cfg': 'g1', 'mA': 380.0 + 0.05 * i, 'tj': 45.0} for i in range(20)])
    d = differenza_mW(aggregate(pts, (40.0, 50.0)), 'g0', 'g1')
    assert d['separabile'] and d['delta_mW_per_istanza'] < 0


def test_una_differenza_DENTRO_IL_RUMORE_e_dichiarata_NON_separabile():
    """E' l'esito che conta di piu': dire "non separabile" e' un risultato, inventare un
    numero dentro il rumore no."""
    pts = ([{'cfg': 'g0', 'mA': 400.0 + (i % 7), 'tj': 45.0} for i in range(20)] +
           [{'cfg': 'g1', 'mA': 399.8 + (i % 7), 'tj': 45.0} for i in range(20)])
    d = differenza_mW(aggregate(pts, (40.0, 50.0)), 'g0', 'g1')
    assert not d['separabile']
    assert 'NON separabile' in d['nota']


def test_la_differenza_e_PER_ISTANZA():
    """La replicazione x3 serve ad amplificare il segnale: il numero riportato torna a una."""
    pts = ([{'cfg': 'blank', 'mA': 400.0, 'tj': 45.0}] * 8 +
           [{'cfg': 'x3', 'mA': 430.0, 'tj': 45.0}] * 8)
    d = differenza_mW(aggregate(pts, (40.0, 50.0)), 'blank', 'x3', n_istanze=3)
    assert d['delta_mW_per_istanza'] == pytest.approx(30.0 * 5.0 / 3.0)


def test_configurazione_assente_e_un_errore_esplicito():
    pts = [{'cfg': 'g0', 'mA': 400.0, 'tj': 45.0}]
    with pytest.raises(KeyError, match='assente'):
        differenza_mW(aggregate(pts, (40.0, 50.0)), 'g0', 'mai_misurata')
