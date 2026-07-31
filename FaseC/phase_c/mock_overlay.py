"""Overlay finto: stessa interfaccia dell'MMIO di PYNQ (write/read), risposte dai golden di T7a.

Serve a scrivere e collaudare TUTTA la Fase C prima che la scheda sia accendibile, cosi' che il
giorno del bring-up non si scriva codice: si esegua.

`inject_at` / `inject_delta` esistono per PROVARE I CANCELLI IN NEGATIVO. Senza, il mock
confermerebbe soltanto se stesso: un cancello che non si e' mai visto fallire non e' un cancello.
"""
from .regmap import IIDM, COMMIT_BIT, DONE_BIT, ACCEL_NFRAC, ACCEL_NBITS, REG_WIDTH, to_fix


class MockOverlay:
    """Riproduce il protocollo del wrapper AXI, non solo i suoi valori.

    In particolare riproduce il COMMIT A FRONTE: il wrapper riparte su `slv_reg4[0] & ~reg4_d0`,
    quindi tenere il bit alto non rilancia l'inferenza. E' il difetto del doppio fronte gia'
    pagato in B2.0 (aveva alterato 1575 metriche), e il mock deve poterlo esporre.
    """

    def __init__(self, golden, regmap=IIDM, inject_at=None, inject_delta=0.0):
        self.g = golden
        self.m = regmap
        self.inject_at = inject_at
        self.inject_delta = inject_delta
        self.regs = {a: 0 for a in tuple(regmap.INPUTS) + tuple(regmap.OUTPUTS)}
        self.k = 0                      # quante inferenze sono state eseguite
        self._ctrl_w = 0                # cio' che e' stato SCRITTO su CTRL
        self._done = 0                  # cio' che si legge da CTRL: percorso DIVERSO
        self._prev_commit = 0

    # --- interfaccia MMIO di PYNQ ---------------------------------------------------------
    def write(self, addr, val):
        val &= 0xFFFFFFFF
        if addr == self.m.CTRL:
            self._ctrl_w = val
            commit = (val >> COMMIT_BIT) & 1
            if commit and not self._prev_commit:        # FRONTE di salita, non livello
                self._done = 0                          # done cade all'avvio, come in hardware
                self._step()
            self._prev_commit = commit
            return
        if addr not in self.regs:
            raise KeyError('indirizzo 0x%02X fuori dalla mappa' % addr)
        self.regs[addr] = val

    def read(self, addr):
        if addr == self.m.CTRL:
            # CRITICO: su CTRL lettura e scrittura sono percorsi DIVERSI. In scrittura il bit 0
            # e' `commit`, in lettura e' `done`. Restituire qui il valore scritto farebbe
            # apparire done sempre alto (commit e done occupano lo stesso bit): l'attesa non
            # attenderebbe mai, e ogni cancello sarebbe verde per costruzione.
            return self._done << DONE_BIT
        if addr not in self.regs:
            raise KeyError('indirizzo 0x%02X fuori dalla mappa' % addr)
        return self.regs[addr]

    # --- il "calcolo" ----------------------------------------------------------------------
    def _step(self):
        if self.k >= len(self.g.gold):
            raise IndexError('richiesta inferenza %d ma lo scenario ne ha %d'
                             % (self.k + 1, len(self.g.gold)))
        v = self.g.gold[self.k]
        if self.inject_at is not None and self.k == self.inject_at:
            v = v + self.inject_delta
        raw = to_fix(v, ACCEL_NFRAC, ACCEL_NBITS)
        # il wrapper emette {{19{accel[12]}}, accel}: sul registro arrivano 32 bit con segno esteso
        if (raw >> (ACCEL_NBITS - 1)) & 1:
            raw |= ((1 << (REG_WIDTH - ACCEL_NBITS)) - 1) << ACCEL_NBITS
        self.regs[self.m.OUTPUTS[0]] = raw
        self._done = 1
        self.k += 1
