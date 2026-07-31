"""Il formato al confine e' il guasto n.1 del bring-up: sbagliato, non produce un crash ma
risultati PLAUSIBILI. Per questo ha test propri, e per questo i valori attesi qui sotto sono
VERIFICATI contro i file golden di T7a, non dedotti.
"""
import pytest

from phase_c.regmap import (to_fix, from_fix, IIDM, TIER,
                            IN_NFRAC, IN_NBITS, ACCEL_NFRAC, ACCEL_NBITS,
                            GOLD_WIDTH, REG_WIDTH)


# --------------------------------------------------------------------------- ingressi (En20)

def test_ingresso_en20_corrisponde_al_golden_di_t7a():
    """Prima parola di axi_stim_1.mem = 0222CBBF, cioe' s = 34,174743 m. Verificato sul file."""
    assert to_fix(34.174743, IN_NFRAC, IN_NBITS) == 0x0222CBBF


def test_ingresso_negativo_e_in_complemento_a_due():
    """dv negativo: terza parola del secondo control-step di axi_stim_1.mem = FFFF3EEA.
    0xFFFF3EEA come intero a 32 bit con segno = -49430; -49430 / 2^20 = -0,04714012.
    Valore letto dal file, non dedotto."""
    assert from_fix(0xFFFF3EEA, IN_NFRAC, REG_WIDTH) == pytest.approx(-0.04714012, abs=1e-8)
    assert to_fix(-0.04714012, IN_NFRAC, IN_NBITS) == 0xFFFF3EEA      # andata e ritorno


# ------------------------------------------------------------------------ uscita (sfix13_En8)

def test_accel_in_sfix13_en8():
    assert to_fix(-1.0, ACCEL_NFRAC, ACCEL_NBITS) == 0x1F00
    assert from_fix(0x1F00, ACCEL_NFRAC, ACCEL_NBITS) == -1.0


def test_il_golden_su_file_si_legge_a_16_bit():
    """FFF6 in axi_gold_1.mem vale -0,0391 m/s2; 002C vale +0,1719. Letti dal file."""
    assert from_fix(0xFFF6, ACCEL_NFRAC, GOLD_WIDTH) == pytest.approx(-0.0390625)
    assert from_fix(0x002C, ACCEL_NFRAC, GOLD_WIDTH) == pytest.approx(0.171875)


def test_leggere_TROPPO_LARGO_ribalta_il_segno_ed_e_il_pericolo_vero():
    """Il rischio non e' leggere troppo stretto: 13 e 16 bit coincidono, perche' la maschera
    li rende equivalenti (verificato). Il rischio e' leggere TROPPO LARGO -- un campo golden a
    16 bit decodificato come registro a 32 mette il bit di segno nel posto sbagliato e
    restituisce +255,96 invece di -0,039. Da qui la larghezza obbligatoria e mai implicita."""
    assert from_fix(0xFFF6, ACCEL_NFRAC, ACCEL_NBITS) == from_fix(0xFFF6, ACCEL_NFRAC, GOLD_WIDTH)
    assert from_fix(0xFFF6, ACCEL_NFRAC, REG_WIDTH) == pytest.approx(255.9609375)


def test_accel_letta_dal_REGISTRO_a_32_bit_estende_il_segno():
    """Il wrapper emette {{19{accel[12]}}, accel}: dal registro arrivano 32 bit."""
    assert from_fix(0xFFFFFF00, ACCEL_NFRAC, REG_WIDTH) == -1.0


def test_le_tre_larghezze_danno_LO_STESSO_valore():
    """13 grezzi, 16 dal file, 32 dal registro: se divergono, il confronto di C1 e' rumore."""
    for raw13, wide16, wide32 in ((0x1F00, 0xFF00, 0xFFFFFF00),
                                  (0x0100, 0x0100, 0x00000100)):
        a = from_fix(raw13, ACCEL_NFRAC, ACCEL_NBITS)
        b = from_fix(wide16, ACCEL_NFRAC, GOLD_WIDTH)
        c = from_fix(wide32, ACCEL_NFRAC, REG_WIDTH)
        assert a == b == c


# ------------------------------------------------------------------------------ quantizzazione

def test_la_quantizzazione_e_FLOOR_non_round():
    """Convenzione del progetto: fi(..., 'Floor') ovunque. Con 'round' i confronti
    bit-esatti di C1 fallirebbero su meta' dei campioni."""
    assert to_fix(0.999, ACCEL_NFRAC, ACCEL_NBITS) == 255      # floor(255,744) = 255
    assert to_fix(-0.001, ACCEL_NFRAC, ACCEL_NBITS) == 0x1FFF  # floor(-0,256) = -1


# ----------------------------------------------------------------------------- mappe registri

def test_mappa_registri_composto():
    assert IIDM.INPUTS == (0x00, 0x04, 0x08, 0x0C)
    assert IIDM.CTRL == 0x10 and IIDM.ACCEL == 0x14
    assert IIDM.N_OUT == 1


def test_mappa_registri_snn_ha_CINQUE_uscite():
    """La SNN sola emette i 5 parametri IDM, non un'accelerazione."""
    assert TIER.N_OUT == 5
    assert TIER.OUTPUTS == (0x14, 0x18, 0x1C, 0x20, 0x24)


# -------------------------------------------------------------------- il cancello, in negativo

def test_fuori_dominio_solleva_invece_di_troncare_in_silenzio():
    with pytest.raises(ValueError, match='fuori dal dominio'):
        to_fix(20.0, ACCEL_NFRAC, ACCEL_NBITS)     # sfix13_En8 arriva a ~15,996


def test_fuori_dominio_anche_dal_lato_negativo():
    with pytest.raises(ValueError, match='fuori dal dominio'):
        to_fix(-17.0, ACCEL_NFRAC, ACCEL_NBITS)    # minimo = -16
