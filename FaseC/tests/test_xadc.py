"""XADC: la temperatura non e' il risultato, ma se e' sbagliata i risultati diventano
inspiegabili senza che nulla abbia dato errore.

I test qui non provano l'hardware. Provano che una lettura che NON arriva si veda come errore
invece che come numero -- che e' il solo modo in cui questo modulo puo' fare danno.
"""
import io
import os

import pytest

from phase_c.xadc import (TEMP_OFF, VCCINT_OFF, XADC_BASE, LetturaImplausibile, XadcAssente,
                          at_equilibrium, confronta_percorsi, read_tj, read_tj_sysfs,
                          read_vccint, read_vccint_sysfs, verifica_plausibile,
                          EQ_BAND_C, EQ_N)


class _MmioFinta(object):
    """Imita `pynq.MMIO` mappata su XADC_BASE: `read` prende un OFFSET dalla base."""

    def __init__(self, per_offset):
        self.per_offset = per_offset
        self.letti = []

    def read(self, off):
        self.letti.append(off)
        if off not in self.per_offset:
            raise AssertionError('letto l\'offset 0x%x, che non e\' nella finestra mappata' % off)
        return self.per_offset[off]


def _raw(v):
    return (v & 0xFFF) << 4


# --------------------------------------------------------- l'indirizzamento e' relativo

def test_si_legge_per_OFFSET_non_per_indirizzo_assoluto():
    """`MMIO.read` prende un offset dalla base. Passare XADC_BASE + off leggeva fuori dalla
    finestra: un difetto che si sarebbe visto solo sulla scheda, e come numero non come errore."""
    m = _MmioFinta({TEMP_OFF: _raw(2600), VCCINT_OFF: _raw(1365)})
    read_tj(m)
    read_vccint(m)
    assert m.letti == [TEMP_OFF, VCCINT_OFF]
    assert all(o < 0x10 for o in m.letti), 'offset fuori dalla finestra da 16 byte'


def test_le_conversioni_sono_quelle_di_UG480():
    m = _MmioFinta({TEMP_OFF: _raw(2600), VCCINT_OFF: _raw(1365)})
    assert read_tj(m) == pytest.approx(2600 * 503.975 / 4096.0 - 273.15, abs=1e-9)
    assert read_vccint(m) == pytest.approx(1365 * 3.0 / 4096.0, abs=1e-9)


# --------------------------------------------------------- il cancello di plausibilita'

def test_una_lettura_PLAUSIBILE_passa():
    assert verifica_plausibile(45.2, 0.999)['ok']


def test_il_registro_che_NON_risponde_si_vede():
    """E' il caso che conta: 0 grezzo da' esattamente lo zero assoluto, e nessuno guarda la
    colonna della temperatura finche' i dati di potenza non risultano inspiegabili."""
    m = _MmioFinta({TEMP_OFF: 0, VCCINT_OFF: 0})
    with pytest.raises(LetturaImplausibile, match='-273'):
        verifica_plausibile(read_tj(m), read_vccint(m))


def test_un_VCCINT_fuori_banda_accusa_il_registro_non_la_scheda():
    with pytest.raises(LetturaImplausibile, match='registro sbagliato'):
        verifica_plausibile(45.0, 2.20)


# --------------------------------------------------------- il confronto fra i due percorsi

def test_due_percorsi_che_CONCORDANO_passano():
    assert confronta_percorsi(45.10, 45.35, tolleranza_c=1.0)['ok']


def test_due_percorsi_che_DISCORDANO_sono_un_errore():
    """Un solo percorso non puo' contraddirsi: e' l'unico modo di accorgersi che uno dei due
    legge un registro diverso da quello che crede."""
    with pytest.raises(LetturaImplausibile, match='registro sbagliato'):
        confronta_percorsi(45.0, 61.0, tolleranza_c=1.0)


# --------------------------------------------------------- il percorso sysfs

def _finto_sysfs(tmp_path, **campi):
    for k, v in campi.items():
        io.open(str(tmp_path / k), 'w').write('%s\n' % v)
    return str(tmp_path)


def test_sysfs_applica_offset_e_scala(tmp_path):
    r = _finto_sysfs(tmp_path, in_temp0_raw=2600, in_temp0_offset=-2219, in_temp0_scale=123.040)
    assert read_tj_sysfs(r) == pytest.approx((2600 - 2219) * 123.040 / 1000.0, abs=1e-9)


def test_sysfs_vccint(tmp_path):
    r = _finto_sysfs(tmp_path, in_voltage0_vccint_raw=1365, in_voltage0_vccint_scale=0.732421875)
    assert read_vccint_sysfs(r) == pytest.approx(1365 * 0.732421875 / 1000.0, abs=1e-9)


def test_un_sysfs_assente_DICE_perche(tmp_path):
    with pytest.raises(XadcAssente, match='xadcps'):
        read_tj_sysfs(str(tmp_path / 'non_esiste'))


# --------------------------------------------------------- il criterio di equilibrio

def test_il_criterio_di_equilibrio_funziona_nei_due_versi():
    assert at_equilibrium([45.0 + 0.01 * k for k in range(EQ_N)]) is True
    assert at_equilibrium([45.0 + 0.2 * k for k in range(EQ_N)]) is False    # deriva
    assert at_equilibrium([45.0] * (EQ_N - 1)) is False                      # troppo poche
    assert EQ_BAND_C == 0.5 and EQ_N == 12


def test_la_banda_e_INCLUSIVA_al_confine():
    """Provato dall'analisi di mutazione: col solo test qui sopra, cambiare `<=` in `<` NON
    faceva fallire nulla in questo file -- le escursioni usate (0,11 e 2,2) stanno lontane dalla
    soglia 0,5. Il confine era difeso solo da test_dmm.py, cioe' da un ALTRO modulo: chi tocca
    xadc.py ed esegue il suo test non sarebbe stato avvisato."""
    esatta = [45.0, 45.0 + EQ_BAND_C] * EQ_N
    appena_sopra = [45.0, 45.0 + EQ_BAND_C * 1.0001] * EQ_N
    assert at_equilibrium(esatta) is True, 'escursione == banda: DENTRO (il confronto e\' <=)'
    assert at_equilibrium(appena_sopra) is False, 'appena oltre la banda: fuori'


def test_gli_ESTREMI_dei_limiti_fisici_sono_ammessi():
    """Trovato dall'analisi di mutazione: `lo <= tj <= hi` con `<` avrebbe respinto una lettura
    esattamente al limite. Il limite dichiarato e' incluso -- altrimenti la banda non e' quella
    scritta nel codice, ed e' una banda diversa a decidere."""
    from phase_c.xadc import TJ_PLAUSIBILE, VCCINT_PLAUSIBILE
    for tj in TJ_PLAUSIBILE:
        for v in VCCINT_PLAUSIBILE:
            assert verifica_plausibile(tj, v)['ok']


def test_appena_OLTRE_i_limiti_fisici_solleva():
    from phase_c.xadc import TJ_PLAUSIBILE, VCCINT_PLAUSIBILE
    with pytest.raises(LetturaImplausibile):
        verifica_plausibile(TJ_PLAUSIBILE[1] + 0.01, 1.0)
    with pytest.raises(LetturaImplausibile):
        verifica_plausibile(45.0, VCCINT_PLAUSIBILE[0] - 0.001)
