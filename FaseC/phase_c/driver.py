"""Driver AXI: scrive i quattro ingressi, da' UN commit, attende `done`, legge l'uscita.

Uno solo per i due wrapper: il composto (una uscita, l'accelerazione) e la SNN sola (cinque
uscite, i parametri IDM). Cambia la mappa, non il protocollo.

Il commit e' un FRONTE, non un livello (`commit = slv_reg4[0] & ~reg4_d0`): tenerlo alto non
rilancia l'inferenza. E' il difetto del doppio fronte gia' pagato in B2.0.
"""
import time

from .regmap import (IIDM, TIER, COMMIT_BIT, GATING_BIT, DONE_BIT,
                     ACCEL_NFRAC, REG_WIDTH, from_fix)


class DoneTimeout(RuntimeError):
    """`done` non e' arrivato. Non si legge il registro d'uscita: conterrebbe il valore
    precedente, che e' plausibile e sbagliato -- il modo peggiore di fallire."""


class _Base:
    regmap = IIDM

    def __init__(self, overlay, gating=True, timeout_s=1.0):
        self.ov = overlay
        self.gating = gating
        self.timeout_s = timeout_s
        self._ctrl_base = (1 << GATING_BIT) if gating else 0
        self.ov.write(self.regmap.CTRL, self._ctrl_base)

    def reset_dut(self, scenario=None):
        """Riporta l'acceleratore allo stato iniziale. OBBLIGATORIO a ogni nuovo scenario.

        Vincolo dell'hardware, non una precauzione: nel wrapper
        `dut_rst = ~S_AXI_ARESETN | ~started`, e `started` si alza al PRIMO commit e non torna
        piu' basso se non con un reset AXI. Lo stato interno della rete (hdl.RAM) non e' quindi
        azzerabile dalla mappa registri.

        Ogni golden e' stato prodotto con la rete azzerata a k=1 di QUEL scenario (qz_cl_sim
        chiama stepFun(..., k==1)). Concatenare due scenari senza reset fa partire il secondo
        con lo stato lasciato dal primo: le uscite restano plausibili e non combaciano piu'.
        Su PYNQ il reset e' `overlay.download()`; qui si delega all'overlay.
        """
        if not hasattr(self.ov, 'reset_dut'):
            raise NotImplementedError(
                'l\'overlay %s non espone reset_dut(). Senza, gli scenari dal secondo in poi '
                'partono con lo stato del precedente e C1 non puo\' essere bit-esatto.'
                % type(self.ov).__name__)
        self.ov.reset_dut(scenario)
        self._prev_commit = 0
        self.ov.write(self.regmap.CTRL, self._ctrl_base)

    def _write_inputs(self, s, v, dv, vl):
        for addr, raw in zip(self.regmap.INPUTS, (s, v, dv, vl)):
            self.ov.write(addr, raw)

    def _commit_and_wait(self):
        self.ov.write(self.regmap.CTRL, self._ctrl_base)                        # commit basso
        self.ov.write(self.regmap.CTRL, self._ctrl_base | (1 << COMMIT_BIT))    # FRONTE
        t0 = time.time()
        while not (self.ov.read(self.regmap.CTRL) >> DONE_BIT) & 1:
            if time.time() - t0 > self.timeout_s:
                raise DoneTimeout(
                    'done non arrivato entro %.3f s. Controllare, in ordine: clock '
                    'dell\'interconnessione, polarita\' del reset, START che non si auto-azzera.'
                    % self.timeout_s)
        self.ov.write(self.regmap.CTRL, self._ctrl_base)                        # commit basso

    def infer_raw(self, s, v, dv, vl):
        """Gli interi grezzi letti dai registri d'uscita. Nessuna conversione."""
        self._write_inputs(s, v, dv, vl)
        self._commit_and_wait()
        return [self.ov.read(a) for a in self.regmap.OUTPUTS]


class SnnIidmDriver(_Base):
    """Composto Donatello_SNN_IIDM: s, v, dv, v_l -> accel."""
    regmap = IIDM

    def infer(self, s, v, dv, vl):
        return from_fix(self.infer_raw(s, v, dv, vl)[0], ACCEL_NFRAC, REG_WIDTH)


class SnnTierDriver(_Base):
    """SNN sola Donatello_Tier@BALANCED: s, v, dv, v_l -> [v0, T, s0, a, b].

    I cinque parametri escono grezzi: la loro scala non e' quella dell'accelerazione e va
    letta dal contratto del blocco, non assunta uguale.
    """
    regmap = TIER

    def infer(self, s, v, dv, vl):
        return self.infer_raw(s, v, dv, vl)
