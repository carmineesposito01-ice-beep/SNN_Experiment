"""XADC (UG480): temperatura di giunzione e tensioni dei rail. NON la corrente.

Non misura la potenza: serve a rendere CREDIBILE la misura di potenza fatta col multimetro.
La dispersione statica e' esponenziale nella temperatura (WP221), e nel nostro caso la statica
e' 103 mW su 114 -- cioe' la parte dominante. Una misura differenziale presa a temperature
diverse confronta due cose diverse e non se ne accorge.

⚠️ Due modi di leggere lo stesso sensore, e non e' un lusso.

  sysfs   /sys/bus/iio/devices/iio:device0/ -- il percorso SUPPORTATO su PYNQ Linux, esposto dal
          driver `xadcps`. E' anche il motivo per cui l'altro puo' fallire: se il driver ha preso
          la regione, la mappatura diretta non e' garantita.
  mmio    XADCIF del PS a 0xF800_7100, letto con `pynq.MMIO(XADC_BASE, 0x10)`.

Quando ci sono entrambi si CONFRONTANO. Non e' ridondanza rassicurante: una lettura sbagliata
qui non da' errore, da' un numero -- e un numero sbagliato di temperatura non si vede nei dati
di potenza, li rende solo inspiegabili.
"""
import io
import os


XADC_BASE = 0xF8007100
TEMP_OFF, VCCINT_OFF, VCCAUX_OFF = 0x00, 0x04, 0x08

SYSFS = '/sys/bus/iio/devices/iio:device0'

# Criterio di equilibrio termico, DICHIARATO IN ANTICIPO (non scelto guardando i dati):
# la temperatura e' stabile se l'escursione sulle ultime EQ_N letture sta entro EQ_BAND.
EQ_BAND_C = 0.5
EQ_N = 12

# Limiti FISICI, non statistici: servono a smascherare la lettura fallita in silenzio.
# Un registro che non risponde legge 0, e 0 in eq. 2-9 da' -273,15 degC -- lo zero assoluto,
# che e' esattamente il tipo di numero che nessuno guarda perche' "e' solo la temperatura".
TJ_PLAUSIBILE = (-20.0, 125.0)          # -40..125 e' il grado industriale; la Z1 e' commerciale
VCCINT_PLAUSIBILE = (0.90, 1.10)        # nominale 1,00 V +-5% (DS187)


class LetturaImplausibile(RuntimeError):
    pass


class XadcAssente(RuntimeError):
    pass


# ------------------------------------------------------------------ conversioni (UG480)

def _tj_da_raw(raw):
    """UG480 eq. 2-9. `raw` sono i 12 bit gia' allineati a destra."""
    return raw * 503.975 / 4096.0 - 273.15


def _volt_da_raw(raw):
    """UG480 eq. 2-11."""
    return raw * 3.0 / 4096.0


def read_tj(mmio):
    """Temperatura di giunzione in gradi Celsius.

    ⚠️ `mmio` dev'essere mappato SU XADC_BASE (`pynq.MMIO(XADC_BASE, 0x10)`), perche' `MMIO.read`
    prende un OFFSET dalla base, non un indirizzo assoluto. Passare l'indirizzo assoluto leggeva
    fuori dalla finestra: un difetto che si sarebbe visto solo sulla scheda, e sotto forma di
    numero invece che di errore.
    """
    return _tj_da_raw((mmio.read(TEMP_OFF) >> 4) & 0xFFF)


def read_vccint(mmio):
    """Tensione del rail VCCINT in volt."""
    return _volt_da_raw((mmio.read(VCCINT_OFF) >> 4) & 0xFFF)


# ------------------------------------------------------------------ il percorso sysfs

def _sysfs_num(nome, radice=SYSFS):
    p = os.path.join(radice, nome)
    if not os.path.isfile(p):
        raise XadcAssente('%s non esiste: il driver xadcps non e\' caricato, oppure il numero '
                          'del dispositivo iio non e\' 0.' % p)
    return float(io.open(p).read().strip())


def read_tj_sysfs(radice=SYSFS):
    """Tj dal driver iio: (raw + offset) * scale, in millesimi di grado."""
    raw = _sysfs_num('in_temp0_raw', radice)
    off = _sysfs_num('in_temp0_offset', radice)
    scale = _sysfs_num('in_temp0_scale', radice)
    return (raw + off) * scale / 1000.0


def read_vccint_sysfs(radice=SYSFS):
    raw = _sysfs_num('in_voltage0_vccint_raw', radice)
    scale = _sysfs_num('in_voltage0_vccint_scale', radice)
    return raw * scale / 1000.0


# ------------------------------------------------------------------ i cancelli

def verifica_plausibile(tj, vccint):
    """CANCELLO: una lettura fallita non da' errore, da' un numero.

    Zero letto da un registro che non risponde diventa -273,15 degC -- e nessuno guarda la
    colonna della temperatura finche' i dati di potenza non risultano inspiegabili.
    """
    lo, hi = TJ_PLAUSIBILE
    if not lo <= tj <= hi:
        raise LetturaImplausibile(
            'Tj = %.2f degC, fuori da [%.0f, %.0f]. Non e\' una scheda calda: e\' una lettura '
            'che non sta arrivando (0 grezzo da\' esattamente -273,15). Controllare quale '
            'percorso XADC e\' in uso.' % (tj, lo, hi))
    lo, hi = VCCINT_PLAUSIBILE
    if not lo <= vccint <= hi:
        raise LetturaImplausibile(
            'VCCINT = %.4f V, fuori da [%.2f, %.2f]. Il rail e\' nominale a 1,00 V: un valore '
            'fuori banda dice che si sta leggendo il registro sbagliato, non che la scheda e\' '
            'guasta.' % (vccint, lo, hi))
    return {'ok': True, 'tj': tj, 'vccint': vccint}


def confronta_percorsi(tj_a, tj_b, tolleranza_c=1.0, nome_a='sysfs', nome_b='mmio'):
    """Quando entrambi i percorsi sono disponibili, devono dire la stessa cosa.

    Non e' ridondanza rassicurante: e' l'unico modo di accorgersi che uno dei due sta leggendo
    un registro diverso da quello che crede. Un solo percorso non puo' contraddirsi.
    """
    if abs(tj_a - tj_b) > tolleranza_c:
        raise LetturaImplausibile(
            '%s legge %.2f degC e %s legge %.2f: differiscono di %.2f (tolleranza %.2f). Uno dei '
            'due sta leggendo il registro sbagliato, e da solo non se ne accorgerebbe.'
            % (nome_a, tj_a, nome_b, tj_b, abs(tj_a - tj_b), tolleranza_c))
    return {'ok': True, nome_a: tj_a, nome_b: tj_b, 'delta_c': abs(tj_a - tj_b)}


def at_equilibrium(tj_history, band_c=EQ_BAND_C, n=EQ_N):
    """True se la temperatura si e' stabilizzata secondo il criterio dichiarato sopra.

    Serve prima di iniziare a misurare: un punto preso mentre la scheda si scalda porta dentro
    una deriva che poi verrebbe attribuita alla configurazione sotto test.
    """
    if len(tj_history) < n:
        return False
    ultimi = list(tj_history)[-n:]
    return (max(ultimi) - min(ultimi)) <= band_c
