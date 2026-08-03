"""I golden bit-esatti prodotti da T7a: UN SOLO posto dove vive il loro formato.

Stava in `tests/conftest.py`, ma serve anche a `cli.py` per gli stadi su scheda. Copiarlo
avrebbe dato due posti dove cambiare il formato dei file, e la copia dimenticata sarebbe stata
quella che legge davvero i dati.

Formato dei file, VERIFICATO (non dedotto):
  axi_stim_<i>.mem   parole da 8 cifre hex, QUATTRO per control-step: s, v, dv, v_l (sfix32_En20)
  axi_gold_<i>.mem   parole da 4 cifre hex, UNA per control-step: accel (sfix13_En8 in 16 bit)
  axi_len_<i>.mem    una parola: il numero di control-step (0x258 = 600 sullo scenario 1)
"""
import io
import os
from dataclasses import dataclass

from . import T7_WORK
from .regmap import from_fix, ACCEL_NFRAC, GOLD_WIDTH


class GoldenAssente(FileNotFoundError):
    pass


@dataclass
class Golden:
    """Uno scenario: gli stimoli grezzi come li ha ricevuti l'RTL, e le uscite attese."""
    idx: int
    stim: list          # [(s, v, dv, vl), ...] interi grezzi, gia' in formato registro
    gold: list          # [accel, ...] float, decodificati a GOLD_WIDTH bit

    def __len__(self):
        return len(self.gold)


def _words(path):
    if not os.path.isfile(path):
        raise GoldenAssente(
            'golden assente: %s. Impostare la variabile T7_WORK sulla cartella prodotta da '
            'T7a (default %s).' % (path, T7_WORK))
    return io.open(path).read().split()


def load_golden(idx, work=None):
    w = work or T7_WORK
    st = [int(h, 16) for h in _words(os.path.join(w, 'axi_stim_%d.mem' % idx))]
    gw = _words(os.path.join(w, 'axi_gold_%d.mem' % idx))
    n = len(gw)
    if len(st) != 4 * n:
        raise AssertionError('scenario %d incoerente: %d parole di stimolo per %d di golden '
                             '(attese %d). Il formato del file non e\' quello assunto.'
                             % (idx, len(st), n, 4 * n))
    return Golden(idx=idx,
                  stim=[tuple(st[k * 4:(k + 1) * 4]) for k in range(n)],
                  gold=[from_fix(int(h, 16), ACCEL_NFRAC, GOLD_WIDTH) for h in gw])


def carica_scenari(indici, work=None):
    """Carica gli scenari richiesti, in ordine. Un indice mancante SOLLEVA.

    Saltarlo in silenzio darebbe una copertura minore di quella dichiarata nell'artefatto --
    e sarebbe visibile solo contando le righe, cioe' mai.
    """
    return [load_golden(i, work=work) for i in indici]
