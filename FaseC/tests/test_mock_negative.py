"""Il mock e il driver, provati INSIEME e soprattutto IN NEGATIVO.

Un mock che non si e' mai visto far fallire un cancello sta confermando se stesso. Questi test
non servono a mostrare che il confronto e' verde: servono a mostrare che puo' essere rosso.
"""
import pytest

from phase_c.driver import SnnIidmDriver, SnnTierDriver, DoneTimeout
from phase_c.mock_overlay import MockOverlay
from phase_c.regmap import IIDM, TIER, ACCEL_NFRAC, ACCEL_NBITS


# --------------------------------------------------------------- il mock riproduce il golden

def test_il_mock_riproduce_il_golden(golden_scen1):
    drv = SnnIidmDriver(MockOverlay(golden=golden_scen1))
    for k in range(20):
        assert drv.infer(*golden_scen1.stim[k]) == golden_scen1.gold[k]


def test_riproduce_anche_i_valori_NEGATIVI(golden_scen1):
    """Il segno esteso a 32 bit e' dove il formato sbaglia in silenzio: va attraversato."""
    drv = SnnIidmDriver(MockOverlay(golden=golden_scen1))
    vals = [drv.infer(*s) for s in golden_scen1.stim[:200]]
    neg = [v for v in vals if v < 0]
    assert neg, 'nessun valore negativo nei primi 200: il test non sta provando il segno'
    assert vals == golden_scen1.gold[:200]


# ------------------------------------------------------------------- IL CANCELLO PUO' FALLIRE

def test_INIETTANDO_un_errore_il_confronto_FALLISCE(golden_scen1):
    """Un LSB di differenza (1/256 = 0,0039 m/s2) deve bastare a far fallire il confronto."""
    lsb = 1.0 / (1 << ACCEL_NFRAC)
    drv = SnnIidmDriver(MockOverlay(golden=golden_scen1, inject_at=7, inject_delta=lsb))
    vals = [drv.infer(*s) for s in golden_scen1.stim[:12]]
    assert vals[7] != golden_scen1.gold[7], 'il cancello NON si accorge di un LSB: non e\' bit-esatto'
    assert vals[7] == pytest.approx(golden_scen1.gold[7] + lsb)
    assert vals[:7] == golden_scen1.gold[:7]        # gli altri restano intatti
    assert vals[8:12] == golden_scen1.gold[8:12]


# --------------------------------------------------------------------- protocollo, non valori

def test_il_commit_e_un_FRONTE_non_un_livello(golden_scen1):
    """Tenere il bit alto non deve produrre una seconda inferenza."""
    ov = MockOverlay(golden=golden_scen1)
    ov.write(IIDM.CTRL, 0b11)                       # 0 -> 1: fronte, una inferenza
    assert ov.k == 1
    ov.write(IIDM.CTRL, 0b11)                       # resta alto: nessun fronte
    ov.write(IIDM.CTRL, 0b11)
    assert ov.k == 1, 'il livello alto ha rilanciato l\'inferenza: doppio fronte'
    ov.write(IIDM.CTRL, 0b10)                       # ricade
    ov.write(IIDM.CTRL, 0b11)                       # nuovo fronte: seconda inferenza
    assert ov.k == 2


def test_su_CTRL_lettura_e_scrittura_sono_percorsi_DIVERSI(golden_scen1):
    """commit (scrittura) e done (lettura) occupano lo stesso bit 0. Se il mock restituisse
    il valore scritto, done risulterebbe sempre alto: l'attesa non attenderebbe mai e ogni
    cancello sarebbe verde per costruzione. E' il difetto che questo test impedisce."""
    ov = MockOverlay(golden=golden_scen1)
    assert ov.read(IIDM.CTRL) & 1 == 0, 'done alto prima di qualunque inferenza'
    ov.write(IIDM.CTRL, 0b11)
    assert ov.read(IIDM.CTRL) & 1 == 1, 'done basso dopo un\'inferenza completata'


def test_timeout_se_done_non_arriva(golden_scen1):
    class Muto(MockOverlay):
        def _step(self):
            pass                                    # calcola, ma non alza mai done
    with pytest.raises(DoneTimeout, match='done non arrivato'):
        SnnIidmDriver(Muto(golden=golden_scen1), timeout_s=0.05).infer(*golden_scen1.stim[0])


def test_indirizzo_fuori_mappa_solleva(golden_scen1):
    with pytest.raises(KeyError):
        MockOverlay(golden=golden_scen1).write(0x40, 0)


# --------------------------------------------------------------------------- la SNN sola

def test_il_driver_tier_legge_CINQUE_uscite(golden_scen1):
    ov = MockOverlay(golden=golden_scen1, regmap=TIER)
    drv = SnnTierDriver(ov)
    out = drv.infer(*golden_scen1.stim[0])
    assert drv.regmap.N_OUT == 5 and len(out) == 5


# ----------------------------- confini del mock (analisi di mutazione)

def test_l_ULTIMO_passo_dello_scenario_NON_e_contaminato(golden_scen1):
    """Trovato dall'analisi di mutazione: `self.k >= n` con `>` avrebbe marcato contaminato
    l'ultimo passo legittimo. Se il mock si dichiarasse contaminato su uno scenario intero e
    corretto, il cancello che ne dipende diventerebbe rumore."""
    from phase_c.mock_overlay import MockOverlay
    from phase_c.driver import SnnIidmDriver
    ov = MockOverlay(golden=[golden_scen1])
    drv = SnnIidmDriver(ov)
    ov.reset_dut(golden_scen1.idx)
    for s, v, dv, vl in golden_scen1.stim:
        drv.infer(s, v, dv, vl)
    assert ov.contaminato is False, 'lo scenario completo e legittimo non e\' contaminato'


def test_UN_passo_oltre_la_fine_SI_contamina(golden_scen1):
    """L'altro verso, ed e' il caso che il mock esiste per modellare: l'hardware non solleva,
    continua a produrre valori plausibili e sbagliati."""
    from phase_c.mock_overlay import MockOverlay
    from phase_c.driver import SnnIidmDriver
    ov = MockOverlay(golden=[golden_scen1])
    drv = SnnIidmDriver(ov)
    ov.reset_dut(golden_scen1.idx)
    for s, v, dv, vl in golden_scen1.stim:
        drv.infer(s, v, dv, vl)
    drv.infer(*golden_scen1.stim[0])                 # un passo di troppo
    assert ov.contaminato is True
