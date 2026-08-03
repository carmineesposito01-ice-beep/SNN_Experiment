"""C0 e' il primo test sul silicio, e deve fallire in modo UTILE: non "non funziona", ma
quale sia il guasto piu' probabile dato il quadro osservato.

Ogni guasto qui sotto e' simulato rompendo il mock in un modo specifico. Un cancello che non
si e' mai visto fallire non e' un cancello -- e uno che fallisce sempre allo stesso modo non
aiuta chi deve ripararlo.
"""
import pytest

from phase_c.c0_liveness import run_c0, C0Failure, PATTERNS
from phase_c.mock_overlay import MockOverlay
from phase_c.regmap import IIDM


def test_c0_passa_su_overlay_sano(golden_scen1):
    r = run_c0(MockOverlay(golden=golden_scen1))
    assert r['ok'] and r['n_bad'] == 0
    assert r['n_test'] == len(IIDM.INPUTS) * len(PATTERNS) == 20


def test_i_pattern_coprono_incollature_E_corti():
    """Senza gli alternati un corto fra bit adiacenti passa inosservato."""
    assert 0x00000000 in PATTERNS and 0xFFFFFFFF in PATTERNS      # incollature
    assert 0xAAAAAAAA in PATTERNS and 0x55555555 in PATTERNS      # corti adiacenti


def test_FALLISCE_se_un_registro_non_ritiene(golden_scen1):
    class Rotto(MockOverlay):
        def write(self, addr, val):
            super().write(addr, 0 if addr == 0x08 else val)
    with pytest.raises(C0Failure) as e:
        run_c0(Rotto(golden=golden_scen1))
    assert '0x08' in str(e.value)
    assert 'mappa degli indirizzi' in str(e.value), 'la diagnosi non isola il registro singolo'


def test_bus_MUTO_viene_riconosciuto_come_tale(golden_scen1):
    class Muto(MockOverlay):
        def read(self, addr):
            return 0
    with pytest.raises(C0Failure) as e:
        run_c0(Muto(golden=golden_scen1))
    assert 'il bus non arriva' in str(e.value)
    assert 'clock' in str(e.value) and 'reset' in str(e.value)


def test_un_CORTO_fra_bit_adiacenti_viene_TROVATO(golden_scen1):
    """I pattern alternati sono l'unica cosa che lo scopre. Non pretendiamo di CLASSIFICARLO:
    un corto produce piu' bit non costanti, e una diagnosi che gli desse un'etichetta sicura
    mentirebbe. Deve pero' emergere l'evidenza grezza."""
    class Corto(MockOverlay):
        def read(self, addr):
            v = super().read(addr)
            return (v | (v >> 1)) & 0xFFFFFFFF
    with pytest.raises(C0Failure) as e:
        run_c0(Corto(golden=golden_scen1))
    msg = str(e.value)
    assert 'nessuna firma inequivocabile' in msg and 'Evidenza grezza' in msg
    assert '0x55555555' in msg or '0xAAAAAAAA' in msg.upper(), \
        'l\'evidenza non mostra il pattern alternato, che e\' cio\' che ha trovato il guasto'


def test_una_LINEA_INCOLLATA_viene_riconosciuta_col_NUMERO_del_bit(golden_scen1):
    class Incollata(MockOverlay):
        def read(self, addr):
            return super().read(addr) | 0x00000001   # bit 0 sempre a 1
    with pytest.raises(C0Failure) as e:
        run_c0(Incollata(golden=golden_scen1))
    assert 'bit [0] incollati a 1' in str(e.value)


def test_riconosce_anche_l_incollatura_a_ZERO(golden_scen1):
    """Il cancello deve funzionare nei due versi, non solo in quello che ho provato per primo."""
    class Incollata(MockOverlay):
        def read(self, addr):
            return super().read(addr) & ~0x00000010  # bit 4 sempre a 0
    with pytest.raises(C0Failure) as e:
        run_c0(Incollata(golden=golden_scen1))
    assert 'bit [4] incollati a 0' in str(e.value)
