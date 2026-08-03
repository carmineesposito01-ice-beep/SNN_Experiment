"""L'adattatore verso PYNQ.

Non c'e' scheda, quindi qui non si prova che PYNQ funzioni. Si prova la sola cosa che
l'adattatore aggiunge e che, sbagliata, farebbe passare per "silicio" dei numeri sbagliati:
che il reset venga CONTROLLATO invece che supposto.
"""
import pytest

from phase_c.overlay_hw import (OverlayScheda, OverlayNonCaricabile, ResetNonAvvenuto,
                                prova_firma_del_reset)
from phase_c.regmap import IIDM


class _IpFinto(object):
    """Imita l'handle PYNQ dell'IP: solo read/write su un dizionario."""

    def __init__(self, ctrl_dopo_reset=0):
        self.reg = {IIDM.CTRL: ctrl_dopo_reset}
        self.scritture = []

    def write(self, addr, val):
        self.scritture.append((addr, val))
        self.reg[addr] = val

    def read(self, addr):
        return self.reg.get(addr, 0)


class _OverlayFinto(object):
    def __init__(self, ip):
        self.tier0 = ip


def _carica_che_resetta(bit):
    return _OverlayFinto(_IpFinto(ctrl_dopo_reset=0))


def _carica_che_NON_resetta(bit):
    return _OverlayFinto(_IpFinto(ctrl_dopo_reset=1))       # done_lat resta a 1


@pytest.fixture
def bit(tmp_path):
    p = tmp_path / 'x1.bit'
    p.write_bytes(b'\x00' * 16)
    return str(p)


# ------------------------------------------------------------ caricamento

def test_un_bitstream_assente_dice_come_generarlo(tmp_path):
    """I .bit non sono versionati (4 MB, rigenerabili): l'errore deve dirlo, non lasciare
    l'utente a cercare un file che non esistera' mai nel repo."""
    with pytest.raises(OverlayNonCaricabile, match='build_bitstreams'):
        OverlayScheda(str(tmp_path / 'mai.bit'), carica=_carica_che_resetta)


def test_un_IP_col_nome_sbagliato_ELENCA_quelli_che_ci_sono(bit):
    with pytest.raises(OverlayNonCaricabile, match='tier0'):
        OverlayScheda(bit, ip='tierX', carica=_carica_che_resetta)


def test_write_e_read_arrivano_all_IP(bit):
    ov = OverlayScheda(bit, carica=_carica_che_resetta)
    ov.write(IIDM.INPUTS[0], 1234)
    assert ov.read(IIDM.INPUTS[0]) == 1234


# ------------------------------------------------------------ il reset, nei due versi

def test_il_reset_CONTROLLA_di_essere_avvenuto(bit):
    ov = OverlayScheda(bit, carica=_carica_che_resetta)
    assert ov.reset_dut(scenario=3)['ok']


def test_un_reset_NON_avvenuto_e_un_errore_non_un_silenzio(bit):
    """E' il caso che conta. Senza il controllo, uno scenario partirebbe dallo stato del
    precedente e darebbe numeri credibili e sbagliati, chiamati 'silicio'."""
    ov = OverlayScheda(bit, carica=_carica_che_NON_resetta)
    with pytest.raises(ResetNonAvvenuto, match='partirebbe dallo stato del'):
        ov.reset_dut(scenario=7)


def test_dopo_il_reset_l_handle_dell_IP_e_QUELLO_NUOVO(bit):
    """Ri-scaricare il bitstream invalida il vecchio handle: continuare a usarlo scriverebbe
    su un IP che non esiste piu'."""
    ov = OverlayScheda(bit, carica=_carica_che_resetta)
    vecchio = ov._ip
    ov.reset_dut()
    assert ov._ip is not vecchio


# ------------------------------------------------------------ il cancello di accensione

def test_la_firma_del_reset_si_prova_DOPO_uno_scenario_completato(bit):
    ov = OverlayScheda(bit, carica=_carica_che_resetta)
    ov.write(IIDM.CTRL, 1)                      # simula done_lat=1 a scenario finito
    r = prova_firma_del_reset(ov, scenario=0)
    assert r['ctrl_prima'] & 1 and not (r['ctrl_dopo'] & 1)


def test_provare_la_firma_a_done_GIA_zero_non_proverebbe_nulla(bit):
    """Un reset che non si e' mai visto distinguere il prima dal dopo e' un reset supposto."""
    ov = OverlayScheda(bit, carica=_carica_che_resetta)
    with pytest.raises(ResetNonAvvenuto, match='non potrebbe distinguersi'):
        prova_firma_del_reset(ov)


# ------------------------------------------------------------ il PL vuoto (blank)

def test_blank_si_carica_SENZA_agganciare_un_IP(bit):
    """Il PL e' vuoto: pretendere tier0 farebbe fallire proprio il riferimento della misura."""
    ov = OverlayScheda(bit, ip=None, carica=lambda p: _OverlayFinto(None))
    assert ov._ip is None


def test_leggere_o_scrivere_su_un_PL_vuoto_e_un_errore_esplicito(bit):
    ov = OverlayScheda(bit, ip=None, carica=lambda p: _OverlayFinto(None))
    with pytest.raises(OverlayNonCaricabile, match='PL e\' vuoto'):
        ov.write(IIDM.CTRL, 1)


# ------------------------------------------------------------ il banco per C3

from phase_c.overlay_hw import BancoPynq, GATING_BIT


def _banco(tmp_path, tj=45.0):
    for n in ('blank', 'x1', 'x2'):
        (tmp_path / ('%s.bit' % n)).write_bytes(b'\x00' * 16)
    return BancoPynq(str(tmp_path), lambda: tj, lambda: 0.998,
                     carica=_carica_che_resetta)


def test_il_bit_di_gating_si_scrive_SENZA_toccare_gli_altri(tmp_path):
    b = _banco(tmp_path)
    b.carica('x1')
    b.ov.write(IIDM.CTRL, 0b1101)                 # bit estranei accesi
    b.imposta_gating('off')
    assert b.ov.read(IIDM.CTRL) == 0b1101 & ~(1 << GATING_BIT)
    b.imposta_gating('on')
    assert b.ov.read(IIDM.CTRL) == 0b1101 | (1 << GATING_BIT)


def test_su_blank_scrivere_il_gating_e_un_errore(tmp_path):
    b = _banco(tmp_path)
    b.carica('blank')
    with pytest.raises(ValueError, match='PL e\' vuoto'):
        b.imposta_gating('on')


def test_uno_stato_di_gating_inventato_e_un_errore(tmp_path):
    b = _banco(tmp_path)
    b.carica('x1')
    with pytest.raises(ValueError, match='sconosciuto'):
        b.imposta_gating('acceso')


def test_ogni_punto_RI_SCARICA_il_bitstream(tmp_path):
    """Saltare il download 'perche' tanto e' lo stesso bitstream' reintrodurrebbe l'eredita'
    di stato che il sorteggio esiste per rompere."""
    caricati = []

    def spia(p):
        caricati.append(p)
        return _carica_che_resetta(p)

    b = _banco(tmp_path)
    b._carica = spia
    b.carica('x1')
    b.carica('x1')
    assert len(caricati) == 2
