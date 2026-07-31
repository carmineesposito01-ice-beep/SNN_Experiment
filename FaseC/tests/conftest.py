"""Fixture condivise: i golden bit-esatti prodotti da T7a.

Formato dei file, VERIFICATO (non dedotto):
  axi_stim_<i>.mem   parole da 8 cifre hex, QUATTRO per control-step: s, v, dv, v_l (sfix32_En20)
  axi_gold_<i>.mem   parole da 4 cifre hex, UNA per control-step: accel (sfix13_En8 in 16 bit)
  axi_len_<i>.mem    una parola: il numero di control-step (0x258 = 600 sullo scenario 1)
"""
import io
import os
from dataclasses import dataclass

import pytest

from phase_c import T7_WORK
from phase_c.regmap import from_fix, ACCEL_NFRAC, GOLD_WIDTH


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
        pytest.skip('golden assente: %s (impostare T7_WORK)' % path)
    return io.open(path).read().split()


def load_golden(idx):
    st = [int(h, 16) for h in _words(os.path.join(T7_WORK, 'axi_stim_%d.mem' % idx))]
    gw = _words(os.path.join(T7_WORK, 'axi_gold_%d.mem' % idx))
    n = len(gw)
    if len(st) != 4 * n:
        raise AssertionError('scenario %d incoerente: %d parole di stimolo per %d di golden '
                             '(attese %d). Il formato del file non e\' quello assunto.'
                             % (idx, len(st), n, 4 * n))
    return Golden(idx=idx,
                  stim=[tuple(st[k * 4:(k + 1) * 4]) for k in range(n)],
                  gold=[from_fix(int(h, 16), ACCEL_NFRAC, GOLD_WIDTH) for h in gw])


@pytest.fixture(scope='session')
def golden_scen1():
    return load_golden(1)


@pytest.fixture(scope='session')
def golden_pochi():
    """Tre scenari, per provare che il replay attraversa piu' di un file."""
    return [load_golden(i) for i in (1, 2, 3)]
