"""L'overlay VERO: adatta PYNQ alla forma che `driver.py` si aspetta.

Il driver vuole tre cose e non deve sapere altro: `write(addr, val)`, `read(addr)`, `reset_dut()`.
PYNQ ne offre due gia' pronte sull'handle dell'IP (`overlay.tier0`), e la terza no.

⚠️ Il reset non e' un no-op da dare per scontato. Nel wrapper (`snniidm_axi_lite.v`) il DUT sta
in reset finche' non arriva il primo commit:

    started   <= 1'b0  su !S_AXI_ARESETN, poi 1 al primo commit e MAI PIU' zero   (riga 152)
    dut_rst    = ~S_AXI_ARESETN | ~started                                        (riga 154)
    done_lat  <= 1'b0  su !S_AXI_ARESETN                                          (riga 168)

Non esiste un bit di reset software: l'unico modo di riportare `started` a zero e' riasserire
ARESETN, cioe' ri-scaricare il bitstream. Costa ~0,3 s a scenario -- 30 s sui 99, accettabile.

E lascia una FIRMA OSSERVABILE: dopo il reset `done_lat` vale 0, e dopo uno scenario completato
vale 1. `reset_dut()` la controlla invece di fidarsi. Senza il controllo, un reset che non
avviene non darebbe errore: darebbe scenari che partono dallo stato del precedente, cioe' numeri
credibili e sbagliati -- e la Fase C intera li chiamerebbe "silicio".
"""
import os

from .regmap import IIDM


DONE_BIT = 0
IP_DEFAULT = 'tier0'        # nome dell'istanza nel block design (hw/bitstream_n.tcl, riga 77)


class OverlayNonCaricabile(RuntimeError):
    pass


class ResetNonAvvenuto(RuntimeError):
    pass


class OverlayScheda(object):
    """Handle sull'IP dietro un'interfaccia piatta, col reset PROVATO.

    `carica` e' iniettabile perche' l'adattatore sia collaudabile senza scheda: la logica che
    conta -- il controllo del reset -- non deve aspettare l'hardware per essere provata.
    """

    def __init__(self, bit_path, ip=IP_DEFAULT, regmap=IIDM, carica=None):
        if carica is None:
            def carica(p):
                from pynq import Overlay
                return Overlay(p)              # il download avviene qui
        if not os.path.isfile(bit_path):
            raise OverlayNonCaricabile(
                'bitstream assente: %s. Generarlo con hw/build_bitstreams.sh -- i .bit non sono '
                'versionati (4 MB, rigenerabili).' % bit_path)
        self.bit_path = bit_path
        self.regmap = regmap
        self._carica = carica
        self._ov = carica(bit_path)
        # ip=None: il bitstream `blank` ha il PL VUOTO, quindi nessuna istanza da agganciare.
        # Serve solo scaricarlo -- e' il riferimento della differenza, non un DUT.
        self.ip_nome = ip
        self._ip = None
        if ip is None:
            return
        if not hasattr(self._ov, ip):
            visti = sorted(getattr(self._ov, 'ip_dict', {}) or
                           [a for a in dir(self._ov) if not a.startswith('_')])
            raise OverlayNonCaricabile(
                'l\'overlay non espone %r; le istanze viste sono %s. Il nome viene dal block '
                'design (hw/bitstream_n.tcl:77, `tier$i`): se e\' cambiato la\', va cambiato '
                'anche qui -- e in un posto solo.' % (ip, visti))
        self._ip = getattr(self._ov, ip)

    # ---- l'interfaccia che il driver usa

    def _esigi_ip(self):
        if self._ip is None:
            raise OverlayNonCaricabile(
                'questo overlay e\' stato aperto senza IP (%s): il PL e\' vuoto e non c\'e\' '
                'niente su cui leggere o scrivere. E\' il riferimento della misura '
                'differenziale, non un DUT.' % os.path.basename(self.bit_path))
        return self._ip

    def write(self, addr, val):
        self._esigi_ip().write(addr, val)

    def read(self, addr):
        return self._esigi_ip().read(addr)

    def reset_dut(self, scenario=None):
        """Riasserisce ARESETN ri-scaricando il bitstream, e PROVA che sia successo.

        Il controllo e' sul meccanismo, non sull'intenzione: `done_lat` deve leggersi a zero.
        Un download che non ha resettato non darebbe errore da solo.
        """
        if self.ip_nome is None:
            raise OverlayNonCaricabile(
                'reset_dut su un overlay senza IP (%s): il PL e\' vuoto, non c\'e\' un DUT da '
                'resettare e il controllo su done_lat non avrebbe nulla da leggere.'
                % os.path.basename(self.bit_path))
        self._ov = self._carica(self.bit_path)
        self._ip = getattr(self._ov, self.ip_nome)
        ctrl = self.read(self.regmap.CTRL)
        if (ctrl >> DONE_BIT) & 1:
            raise ResetNonAvvenuto(
                'dopo il ricaricamento del bitstream done_lat vale ancora 1 (CTRL=0x%08x): il '
                'DUT non e\' stato resettato e lo scenario %s partirebbe dallo stato del '
                'precedente. Vedi snniidm_axi_lite.v:152,168.' % (ctrl, scenario))
        return {'ok': True, 'ctrl': ctrl, 'scenario': scenario}


def prova_firma_del_reset(ov, scenario=None):
    """CANCELLO di accensione: il reset si vede nei DUE versi.

    Da eseguire una volta al bring-up, DOPO uno scenario completato. Un reset che non si e' mai
    visto distinguere lo stato "prima" dallo stato "dopo" non e' un reset provato: e' un reset
    supposto, e la supposizione qui vale l'intera Fase C.
    """
    prima = ov.read(ov.regmap.CTRL)
    if not (prima >> DONE_BIT) & 1:
        raise ResetNonAvvenuto(
            'la prova va fatta DOPO uno scenario completato: done_lat vale gia\' 0 '
            '(CTRL=0x%08x), quindi il reset non potrebbe distinguersi da nessun reset.' % prima)
    dopo = ov.reset_dut(scenario=scenario)
    return {'ok': True, 'ctrl_prima': prima, 'ctrl_dopo': dopo['ctrl'],
            'nota': 'done_lat 1 -> 0: il reset e\' osservato, non supposto'}


# --------------------------------------------------------------------- il banco per C3

GATING_BIT = 1          # slv_reg4[1] (snniidm_axi_lite.v:139) -- un BIT, non un bitstream diverso


class BancoPynq(object):
    """`c3_power.BancoDiMisura` sulla scheda vera.

    Tiene fuori da `c3_power` ogni riferimento all'hardware: il METODO (ordine sorteggiato,
    equilibrio, scarto) resta provabile senza scheda, e questo strato resta abbastanza sottile
    da non aver bisogno di essere provato con una.

    ⚠️ `carica` ri-scarica il bitstream a OGNI punto, anche quando la configurazione non cambia.
    Non e' uno spreco: la sequenza e' sorteggiata proprio perche' nessuna condizione erediti lo
    stato della precedente, e un download saltato "perche' tanto e' lo stesso bitstream"
    reintrodurrebbe l'eredita' che il sorteggio esiste per rompere.
    """

    def __init__(self, bitstream_dir, leggi_tj, leggi_vccint, ip=IP_DEFAULT, regmap=IIDM,
                 carica=None):
        self.dir = bitstream_dir
        self._leggi_tj, self._leggi_vccint = leggi_tj, leggi_vccint
        self.ip, self.regmap, self._carica = ip, regmap, carica
        self.ov = None
        self.cfg = None

    def carica(self, cfg):
        # blank ha il PL vuoto: niente IP da agganciare.
        self.ov = OverlayScheda(os.path.join(self.dir, '%s.bit' % cfg),
                                ip=None if cfg == 'blank' else self.ip,
                                regmap=self.regmap, carica=self._carica)
        self.cfg = cfg
        return self.ov

    def imposta_gating(self, stato):
        if stato not in ('on', 'off'):
            raise ValueError('stato del gating %r sconosciuto: solo "on" o "off"' % stato)
        if self.cfg == 'blank':
            raise ValueError('il gating non si scrive su blank: il PL e\' vuoto e il bit non '
                             'comanda nulla (c3_power.punti_di_misura lo marca "-")')
        v = self.ov.read(self.regmap.CTRL)
        acceso = v | (1 << GATING_BIT)
        spento = v & ~(1 << GATING_BIT)
        self.ov.write(self.regmap.CTRL, acceso if stato == 'on' else spento)

    def leggi_tj(self):
        return self._leggi_tj()

    def leggi_vccint(self):
        return self._leggi_vccint()
