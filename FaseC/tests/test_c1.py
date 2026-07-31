"""C1 deve essere verde quando il silicio e' giusto, rosso a UN LSB di differenza, e quando e'
rosso deve dire da dove cominciare a guardare.

I tre guasti simulati qui sotto (fattore di scala, letture nulle, START non azzerato) sono i
tre che il corpus di bring-up indica come i piu' frequenti. Ognuno deve portare in cima il
sospettato giusto -- altrimenti la scaletta e' decorazione.
"""
import pytest

from phase_c.c1_functional import run_c1, diagnose
from phase_c.mock_overlay import MockOverlay
from phase_c.driver import SnnIidmDriver
from phase_c.regmap import ACCEL_NFRAC


class _Corto:
    """Uno scenario ridotto: stessi campi di Golden, meno campioni."""
    def __init__(self, g, n):
        self.idx, self.stim, self.gold = g.idx, g.stim[:n], g.gold[:n]

    def __len__(self):
        return len(self.gold)


# ------------------------------------------------------------------------------ verde e rosso

def test_c1_verde_su_piu_scenari(golden_pochi):
    corti = [_Corto(g, 40) for g in golden_pochi]
    r = run_c1(SnnIidmDriver(MockOverlay(golden=corti)), corti)
    assert r['bit_esatto'] and r['nmismatch'] == 0
    assert r['n'] == 120 and r['n_scenari'] == 3
    assert all(s['nmismatch'] == 0 for s in r['per_scenario'])


def test_SENZA_reset_fra_scenari_il_replay_NON_combacia(golden_pochi):
    """Il vincolo e' dell'hardware, non una precauzione: `started` si alza al primo commit e
    non torna basso senza reset AXI, quindi lo stato della rete resta quello dello scenario
    precedente. Ogni golden pero' e' stato prodotto con la rete azzerata a k=1 di QUEL scenario.

    Se questo test diventasse verde, vorrebbe dire che il reset non serve -- e allora sarebbe
    il modello a essere sbagliato, non il vincolo."""
    corti = [_Corto(g, 40) for g in golden_pochi]
    ov = MockOverlay(golden=corti)
    buono = run_c1(SnnIidmDriver(ov), corti, reset_between=True)
    assert buono['bit_esatto']

    ov2 = MockOverlay(golden=corti)
    cattivo = run_c1(SnnIidmDriver(ov2), corti, reset_between=False)
    assert not cattivo['bit_esatto'], 'senza reset il replay combacia: il modello e\' sbagliato'
    assert cattivo['per_scenario'][0]['nmismatch'] == 0, 'il PRIMO scenario deve restare pulito'
    assert cattivo['per_scenario'][1]['nmismatch'] > 0, 'la contaminazione parte dal secondo'


def test_reset_dut_su_un_overlay_che_non_lo_espone_e_esplicito(golden_scen1):
    class SenzaReset:
        write = staticmethod(lambda *a: None)
        read = staticmethod(lambda *a: 1)
    with pytest.raises(NotImplementedError, match='reset_dut'):
        SnnIidmDriver(SenzaReset()).reset_dut()


def test_c1_ROSSO_a_UN_LSB(golden_scen1):
    """1/256 = 0,0039 m/s2. Se un LSB passasse, C1 non sarebbe bit-esatto e la sua prova
    non varrebbe niente."""
    lsb = 1.0 / (1 << ACCEL_NFRAC)
    g = _Corto(golden_scen1, 30)
    drv = SnnIidmDriver(MockOverlay(golden=g, inject_at=3, inject_delta=lsb))
    r = run_c1(drv, [g])
    assert not r['bit_esatto'] and r['nmismatch'] == 1
    assert r['first']['k'] == 3 and r['first']['scen'] == 1
    assert r['campioni'][0]['k'] == 3


# -------------------------------------------------------------- la scaletta porta in cima il vero

def test_un_FATTORE_DI_SCALA_accusa_il_formato():
    """Rapporto got/exp costante e diverso da 1 = errore di esponente, cioe' di formato."""
    d = diagnose(first={'k': 0, 'got': 2.0, 'exp': 1.0}, n=600, nmismatch=600,
                 ratios=[2.0] * 600)
    assert 'formato numerico' in d[0]


def test_LETTURE_NULLE_accusano_gli_indirizzi():
    d = diagnose(first={'k': 0, 'got': 0.0, 'exp': -0.25}, n=600, nmismatch=600, ratios=[0.0] * 600)
    assert 'indirizzi' in d[0], 'con letture a zero il primo sospettato non e\' la mappa'


def test_SOLO_LA_PRIMA_GIUSTA_accusa_lo_START():
    """La firma piu' specifica che esista: n-1 discrepanze a partire dalla seconda."""
    d = diagnose(first={'k': 1, 'got': 0.5, 'exp': 0.1}, n=600, nmismatch=599,
                 ratios=[5.0, 3.0, 7.0])
    assert 'START' in d[0]


def test_ERRORI_SPARSI_accusano_il_pipelining():
    d = diagnose(first={'k': 17, 'got': 0.5, 'exp': 0.4}, n=600, nmismatch=6,
                 ratios=[1.25, 0.9, 1.4, 0.8, 1.1, 1.3])
    assert 'pipelining' in d[0]


def test_la_scaletta_elenca_SEMPRE_tutti_i_sospettati():
    """Ordinare non e' escludere: chi ripara deve vedere anche gli altri."""
    d = diagnose(first={'k': 0, 'got': 2.0, 'exp': 1.0}, n=10, nmismatch=10, ratios=[2.0] * 10)
    assert len(d) == 5
    testo = ' '.join(d)
    for atteso in ('formato', 'indirizzi', 'START', 'reset', 'pipelining'):
        assert atteso in testo
