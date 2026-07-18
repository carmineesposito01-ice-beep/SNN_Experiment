import os
import sys

import pytest
import torch

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.fixed_backend import q                                  # noqa: E402


# ------------------------------- q primitive -------------------------------
def test_q_is_exact_for_representable_values():
    assert float(q(torch.tensor(0.0625), 2, 13)) == 0.0625     # 2^-4, exact at n>=4
    assert float(q(torch.tensor(-1.5), 5, 13)) == -1.5

def test_q_rounds_to_nearest_grid_point():
    # 0.1 at Q2.4 (step 1/16 = 0.0625): 0.1/0.0625 = 1.6 -> 2 -> 0.125
    assert abs(float(q(torch.tensor(0.1), 2, 4)) - 0.125) < 1e-6

def test_q_saturates_at_qmn_extremes():
    assert float(q(torch.tensor(5.0), 2, 4)) == 3.9375         # hi = 2^2 - 2^-4
    assert float(q(torch.tensor(-5.0), 2, 4)) == -4.0         # lo = -2^2

def test_q_kills_small_po2_at_low_nfrac():
    assert float(q(torch.tensor(0.0625), 2, 3)) == 0.0        # Q2.3 step 1/8: 0.5 -> half-to-even -> 0
    assert float(q(torch.tensor(0.0625), 2, 4)) == 0.0625     # survives at n=4
