"""Scenarios for the simulator -- thin wrapper over utils.closed_loop_eval.build_scenarios.

A Scenario carries exactly the SimStepper constructor inputs (params_gt, v_leader,
s_init, v_init, cut_in), so the UI/tests can pick one and run it directly.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np

from utils.closed_loop_eval import build_scenarios


@dataclass(frozen=True)
class Scenario:
    name: str
    params_gt: np.ndarray            # (5,)
    v_leader: np.ndarray             # (N,)
    s_init: float
    v_init: float
    cut_in: Optional[tuple] = None   # (t_cut, new_gap) | None


def scenario_library(params_gt, N=600, rng=None, include_tail=False):
    """The v1 scenario set (following, stop_and_go, hard_brake, cut_in, sinusoidal)."""
    pg = np.asarray(params_gt, dtype=np.float64)
    return [
        Scenario(name=name, params_gt=pg,
                 v_leader=np.asarray(vl, dtype=np.float64),
                 s_init=float(s_i), v_init=float(v_i), cut_in=cut)
        for name, vl, s_i, v_i, cut in build_scenarios(pg, N=N, rng=rng, include_tail=include_tail)
    ]


def manual_scenario(params_gt, v_leader, s_init, v_init, cut_in=None, name="manual"):
    return Scenario(name=name, params_gt=np.asarray(params_gt, dtype=np.float64),
                    v_leader=np.asarray(v_leader, dtype=np.float64),
                    s_init=float(s_init), v_init=float(v_init), cut_in=cut_in)
