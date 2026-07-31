"""XADC (UG480): temperatura di giunzione e tensioni dei rail. NON la corrente.

Non misura la potenza: serve a rendere CREDIBILE la misura di potenza fatta col multimetro.
La dispersione statica e' esponenziale nella temperatura (WP221), e nel nostro caso la statica
e' 103 mW su 114 -- cioe' la parte dominante. Una misura differenziale presa a temperature
diverse confronta due cose diverse e non se ne accorge.
"""

XADC_BASE = 0xF8007100
TEMP_OFF, VCCINT_OFF, VCCAUX_OFF = 0x00, 0x04, 0x08

# Criterio di equilibrio termico, DICHIARATO IN ANTICIPO (non scelto guardando i dati):
# la temperatura e' stabile se l'escursione sulle ultime EQ_N letture sta entro EQ_BAND.
EQ_BAND_C = 0.5
EQ_N = 12


def read_tj(mmio):
    """Temperatura di giunzione in gradi Celsius (UG480, eq. 2-9)."""
    raw = (mmio.read(XADC_BASE + TEMP_OFF) >> 4) & 0xFFF
    return raw * 503.975 / 4096.0 - 273.15


def read_vccint(mmio):
    """Tensione del rail VCCINT in volt (UG480, eq. 2-11)."""
    raw = (mmio.read(XADC_BASE + VCCINT_OFF) >> 4) & 0xFFF
    return raw * 3.0 / 4096.0


def at_equilibrium(tj_history, band_c=EQ_BAND_C, n=EQ_N):
    """True se la temperatura si e' stabilizzata secondo il criterio dichiarato sopra.

    Serve prima di iniziare a misurare: un punto preso mentre la scheda si scalda porta dentro
    una deriva che poi verrebbe attribuita alla configurazione sotto test.
    """
    if len(tj_history) < n:
        return False
    ultimi = list(tj_history)[-n:]
    return (max(ultimi) - min(ultimi)) <= band_c
