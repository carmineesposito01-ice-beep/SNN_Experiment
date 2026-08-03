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


def test_i_rapporti_ASSENTI_si_scartano_prima_di_diagnosticare():
    """Trovato dall'analisi di mutazione: `if x is not None` con `is None` avrebbe tenuto solo
    i buchi. La diagnosi si basa sulla costanza dei rapporti: calcolarla su una lista di None
    solleverebbe, o peggio darebbe una diagnosi presa da niente."""
    from phase_c.c1_functional import diagnose
    misti = [2.0, None, 2.0, None, 2.0]
    d = diagnose(first={'k': 3, 'got': 8.0, 'exp': 4.0}, n=5, nmismatch=5, ratios=misti)
    assert isinstance(d, (str, list, dict)) and d, 'la diagnosi deve produrre qualcosa'
    solo_none = diagnose(first={'k': 3, 'got': 8.0, 'exp': 4.0}, n=5, nmismatch=5,
                         ratios=[None, None, None])
    assert isinstance(solo_none, (str, list, dict)), 'nessun rapporto utile: non deve rompersi'


# ------------------- la scaletta diagnostica, ORDINE COMPLETO (analisi di mutazione)
#
# I test qui sopra asseriscono solo CHI E' PRIMO. L'analisi di mutazione ha mostrato che non
# basta: cambiare `and` in `or` dentro `diagnose` sposta i pesi e riordina la scaletta senza
# sempre cambiarne la testa. Ma la scaletta INTERA e' cio' che l'operatore legge durante il
# bring-up: se il secondo sospettato e' sbagliato, si va a cercare nel posto sbagliato.

def _ordine(**kw):
    from phase_c.c1_functional import diagnose
    return [r.split(' -> ')[0] for r in diagnose(**kw)]


FORMATO = 'formato numerico al confine'
INDIRIZZI = 'mappa degli indirizzi'
START = 'START che non si auto-azzera'
RESET = 'polarita del reset'
PIPE = 'pipelining insufficiente'


def test_ordine_completo_firma_FORMATO():
    assert _ordine(first={'k': 0, 'got': 2.0, 'exp': 1.0}, n=600, nmismatch=600,
                   ratios=[2.0] * 600) == [FORMATO, INDIRIZZI, START, RESET, PIPE]


def test_ordine_completo_firma_INDIRIZZI():
    assert _ordine(first={'k': 0, 'got': 0.0, 'exp': -0.25}, n=600, nmismatch=600,
                   ratios=[0.0] * 600) == [INDIRIZZI, RESET, FORMATO, START, PIPE]


def test_ordine_completo_firma_START():
    assert _ordine(first={'k': 1, 'got': 0.5, 'exp': 0.1}, n=600, nmismatch=599,
                   ratios=[0.5 + 0.01 * i for i in range(599)]) == \
        [START, FORMATO, INDIRIZZI, RESET, PIPE]


def test_ordine_completo_firma_PIPELINING():
    assert _ordine(first={'k': 17, 'got': 0.5, 'exp': 0.4}, n=600, nmismatch=6,
                   ratios=[1.25, 1.4, 0.9, 1.1, 1.3, 0.8]) == \
        [PIPE, FORMATO, INDIRIZZI, START, RESET]


def test_errori_SPARSI_con_la_prima_lettura_a_zero_restano_pipelining():
    """`tutti = n > 0 and nmismatch == n`: con `or` sarebbe sempre vero, e una singola lettura
    nulla fra sei scarti sparsi accuserebbe gli INDIRIZZI -- mandando a controllare gli offset
    mentre il problema e' nei tempi."""
    assert _ordine(first={'k': 17, 'got': 0.0, 'exp': 0.4}, n=600, nmismatch=6,
                   ratios=[1.25, 1.4, 0.9, 1.1, 1.3, 0.8]) == \
        [PIPE, FORMATO, INDIRIZZI, START, RESET]


def test_un_rapporto_COSTANTE_ma_su_pochi_campioni_resta_formato():
    """`not costante and 0 < nmismatch < 0.2n`: con `or` il pipelining prenderebbe peso anche a
    rapporto costante, e supererebbe il formato. Un fattore di scala su pochi campioni resta un
    errore di esponente, non di tempi."""
    assert _ordine(first={'k': 17, 'got': 0.8, 'exp': 0.4}, n=600, nmismatch=6,
                   ratios=[2.0] * 6)[:2] == [FORMATO, PIPE]


def test_il_PRIMO_scarto_a_k1_NON_accusa_lo_START_se_gli_scarti_sono_pochi():
    """`nmismatch == n - 1 and first.k == 1`: con `or` basterebbe che il primo scarto capiti al
    secondo campione per accusare lo START, che invece ha una firma precisa -- TUTTE sbagliate
    tranne la prima."""
    o = _ordine(first={'k': 1, 'got': 0.5, 'exp': 0.4}, n=600, nmismatch=6,
                ratios=[1.25, 1.4, 0.9, 1.1, 1.3, 0.8])
    assert o[0] == PIPE, 'sei scarti su 600 non sono la firma dello START'
    assert o.index(START) > 1


def test_uno_scarto_dove_l_atteso_e_ZERO_non_divide_per_zero(golden_scen1):
    """`if exp != 0` prima di `got / exp`. In regime stazionario l'accelerazione attesa e'
    esattamente 0 su molti campioni: uno scarto proprio li' farebbe esplodere C1 sulla scheda,
    e l'analisi di mutazione ha mostrato che nessun test lo esercitava."""
    from phase_c.mock_overlay import MockOverlay
    from phase_c.driver import SnnIidmDriver
    from phase_c.c1_functional import run_c1

    zeri = [i for i, g in enumerate(golden_scen1.gold) if g == 0.0]
    if not zeri:
        import pytest as _p
        _p.skip('lo scenario 1 non contiene campioni con accelerazione attesa esattamente 0')
    ov = MockOverlay(golden=[golden_scen1], inject_at=zeri[0], inject_delta=0.5)
    r = run_c1(SnnIidmDriver(ov), [golden_scen1])
    assert r['bit_esatto'] is False and r['nmismatch'] >= 1
    assert 'diagnosi' in r, 'la diagnosi deve esserci comunque, senza divisioni per zero'
