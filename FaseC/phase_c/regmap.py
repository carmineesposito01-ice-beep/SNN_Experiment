"""Formati numerici e mappe registri. UNICO posto in cui vivono.

Il formato al confine e' il guasto numero uno del bring-up su silicio: sbagliato, non produce
un crash ma risultati PLAUSIBILI, con errore che scala con la grandezza. E' l'unico difetto di
questa classe che puo' attraversare l'intera campagna senza farsi notare -- da qui il modulo
dedicato, i test propri e la larghezza SEMPRE esplicita.

Lo stesso valore vive su tre larghezze diverse, ed e' bene averlo scritto:

    sfix13_En8 grezzo    13 bit    l'uscita del blocco
    campo su file        16 bit    axi_gold_*.mem -- segno gia' esteso
    registro AXI         32 bit    il wrapper emette {{19{accel[12]}}, accel}

Leggere un golden a 13 bit invece che a 16 restituisce +223,96 m/s2 invece di -0,039: qui
l'errore e' cosi' grosso da vedersi, ma e' fortuna, non una garanzia.
"""
import math
from dataclasses import dataclass

# --- formati -----------------------------------------------------------------------------
IN_NFRAC, IN_NBITS = 20, 32          # ingressi s, v, dv, v_l  (sfix32_En20)
ACCEL_NFRAC, ACCEL_NBITS = 8, 13     # uscita accel            (sfix13_En8, 1/256, +-16)
GOLD_WIDTH = 16                      # larghezza del campo nei file axi_gold_*.mem
REG_WIDTH = 32                       # larghezza del registro AXI

# --- bit di controllo (registro CTRL) ------------------------------------------------------
COMMIT_BIT, GATING_BIT, DONE_BIT = 0, 1, 0


def to_fix(x, nfrac, nbits):
    """float -> intero senza segno che rappresenta il campo a `nbits` in complemento a due.

    Quantizzazione FLOOR, non round: e' la convenzione del progetto (fi(..., 'Floor')).
    Con 'round' i confronti bit-esatti di C1 fallirebbero su meta' dei campioni.
    Fuori dominio SOLLEVA: troncare in silenzio darebbe un numero credibile e sbagliato.
    """
    q = math.floor(x * (1 << nfrac))
    lo, hi = -(1 << (nbits - 1)), (1 << (nbits - 1)) - 1
    if not (lo <= q <= hi):
        raise ValueError('valore %r fuori dal dominio sfix%d_En%d (ammesso [%.6f, %.6f])'
                         % (x, nbits, nfrac, lo / float(1 << nfrac), hi / float(1 << nfrac)))
    return q & ((1 << nbits) - 1)


def from_fix(u, nfrac, width):
    """intero letto da un campo largo `width` bit -> float.

    `width` e' la larghezza DEL CAMPO DA CUI SI LEGGE, non quella del tipo: 13 per il valore
    grezzo, GOLD_WIDTH per un file golden, REG_WIDTH per un registro AXI. Il segno gia' esteso
    rende le tre letture equivalenti -- ed e' un test, non un'assunzione.
    """
    u &= (1 << width) - 1
    if (u >> (width - 1)) & 1:
        u -= (1 << width)
    return u / float(1 << nfrac)


# --- mappe registri ------------------------------------------------------------------------
@dataclass(frozen=True)
class _Map:
    INPUTS: tuple
    CTRL: int
    OUTPUTS: tuple

    @property
    def N_OUT(self):
        return len(self.OUTPUTS)

    @property
    def ACCEL(self):
        return self.OUTPUTS[0]


# Composto Donatello_SNN_IIDM: una sola uscita, l'accelerazione.
IIDM = _Map(INPUTS=(0x00, 0x04, 0x08, 0x0C), CTRL=0x10, OUTPUTS=(0x14,))

# SNN sola (Donatello_Tier@BALANCED): cinque uscite, i parametri IDM [v0, T, s0, a, b].
TIER = _Map(INPUTS=(0x00, 0x04, 0x08, 0x0C), CTRL=0x10,
            OUTPUTS=(0x14, 0x18, 0x1C, 0x20, 0x24))
