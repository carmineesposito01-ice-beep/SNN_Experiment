#!/usr/bin/env python3
"""
run_on_pynq.py — driver PYNQ-Z1 per l'IP SNN Donatello B2 (AXI4-Lite).

Carica l'overlay (serve snn_b2_donatello.bit + snn_b2_donatello.hwh, stesso
basename, nello stesso path) e fa girare un'inferenza: scrive i 4 ingressi
normalizzati (Q5.13), pulsa start, aspetta done, legge i 5 parametri di
car-following (Q7.13).

Mappa registri (offset dal base 0x4000_0000):
  0x00..0x0C  W  xn[0..3]      ingressi normalizzati, Q5.13 (19 bit in [18:0])
  0x10        W  control       bit0 = start (pulse sul fronte di salita)
  0x10        R  status        bit0 = done
  0x14..0x24  R  params[0..4]  = v0, T, s0, a, b   (Q7.13, sign-extended a 32b)

Ordine params = quello di snn_decode_hdl.m (range lo/hi):
  p0 v0 [8..45] m/s · p1 T [0.5..2.5] s · p2 s0 [1..5] m · p3 a [0.3..2.5] m/s^2 · p4 b [0.5..3] m/s^2

NB: la NORMALIZZAZIONE fisico->normalizzato resta sul PS in float (scelta di
design: la normalize in hardware ribaltava gli spike). Le costanti sono quelle
di matlab/snn_normalize.m per il campione Donatello — riportale in `normalize()`.
"""
from pynq import Overlay

# --- mappa registri ---
REG_XN      = [0x00, 0x04, 0x08, 0x0C]
REG_CONTROL = 0x10
REG_STATUS  = 0x10
REG_PARAMS  = [0x14, 0x18, 0x1C, 0x20, 0x24]
PARAM_NAMES = ["v0", "T", "s0", "a", "b"]

FRAC_IN  = 13   # Q5.13 ingressi
FRAC_OUT = 13   # Q7.13 uscite


def to_fixed(x, frac=FRAC_IN):
    """float -> intero con segno in complemento a 2 su 32 bit (Q?.frac)."""
    return int(round(x * (1 << frac))) & 0xFFFFFFFF


def from_fixed(u, frac=FRAC_OUT, bits=32):
    """intero del registro -> float (Q?.frac), con sign-extension."""
    if u & (1 << (bits - 1)):
        u -= (1 << bits)
    return u / (1 << frac)


def normalize(s, v, dv, vl):
    """fisico -> normalizzato (Donatello). RIEMPIRE con le costanti di snn_normalize.m."""
    raise NotImplementedError(
        "Copia qui la normalize di matlab/snn_normalize.m per Donatello "
        "(scale/offset per s, v, dv, vl)."
    )


def infer(ip, xn_norm, timeout=100000):
    """Una inferenza. xn_norm = 4 float GIA' normalizzati (s, v, dv, vl)."""
    for reg, x in zip(REG_XN, xn_norm):
        ip.write(reg, to_fixed(x))
    ip.write(REG_CONTROL, 1)          # start (fronte di salita)
    ip.write(REG_CONTROL, 0)          # clear
    i = 0
    while (ip.read(REG_STATUS) & 1) == 0:   # poll done
        i += 1
        if i > timeout:
            raise TimeoutError("done non asserito entro il timeout")
    return {name: from_fixed(ip.read(reg))
            for name, reg in zip(PARAM_NAMES, REG_PARAMS)}


def main():
    ol = Overlay("snn_b2_donatello.bit")   # richiede snn_b2_donatello.hwh accanto
    ip = ol.snn0                            # IP AXI-Lite @ 0x4000_0000

    # Esempio con xn GIA' normalizzati (sostituisci con normalize(s, v, dv, vl)):
    xn_norm = [0.64, 0.27, 0.052, 0.30]
    p = infer(ip, xn_norm)
    print("  ".join(f"{k}={p[k]:.3f}" for k in PARAM_NAMES))
    # atteso ~ v0 26.5 m/s, T 1.63 s, s0 2.45 m, a 1.01, b 1.71 m/s^2 (cfr. cosim)


if __name__ == "__main__":
    main()
