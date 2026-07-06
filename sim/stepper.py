"""SimStepper -- single-step closed-loop engine.

Structural refactor of utils.closed_loop_eval.simulate(): identical operations
and order, mutable state hoisted into SimState. Reuses simulate()'s helpers so
the result is bit-identical (tests/test_sim_stepper.py). The UI loop calls step()
per QTimer tick; run() is a batch convenience used by the golden test.

backend=None reproduces simulate()'s oracle path (constant params_gt).
"""
import numpy as np
import torch

from config import ACC_AL_TAU, ACC_COOLNESS, DT
from core.network import CF_FSNN_Net
from utils.closed_loop_eval import _channel_obs, _norm_obs, _plant_step

from .state import SimState, StepResult


class SimStepper:
    def __init__(self, backend, params_gt, v_leader, s_init, v_init,
                 cut_in=None, plant=None, channel=None, device="cpu"):
        self.backend = backend                     # None -> oracle
        self.params_gt = np.asarray(params_gt, dtype=np.float64)
        self.v_leader = np.asarray(v_leader, dtype=np.float64)
        self.s_init = float(s_init)
        self.v_init = float(v_init)
        self.cut_in = cut_in
        self.plant = plant
        self.channel = channel
        self.device = device
        self.N = len(self.v_leader)
        self.alpha_al = float(np.exp(-DT / ACC_AL_TAU))
        self.pg = torch.tensor(self.params_gt, dtype=torch.float32).view(1, 5)
        self.reset()

    def reset(self) -> None:
        self.st = SimState(t=0, s=self.s_init, v=self.v_init,
                           a_l_filt=0.0, vl_prev=float(self.v_leader[0]))
        self.ch_rng = (np.random.default_rng(self.channel.get("seed", 0))
                       if self.channel is not None else None)
        if self.backend is not None:
            self.backend.reset()

    @torch.no_grad()
    def step(self) -> StepResult:
        st = self.st
        t = st.t
        if self.cut_in is not None and t == int(self.cut_in[0]):
            st.s = float(self.cut_in[1])
        vl = float(self.v_leader[t])
        dv = st.v - vl
        if self.channel is not None:
            s_obs, vl_obs, _age = _channel_obs(st.s, vl, st.ch_state, self.channel,
                                               self.ch_rng, st.v)
        else:
            s_obs, vl_obs = st.s, vl
        dv_obs = st.v - vl_obs

        if self.backend is not None:
            params = self.backend.infer(_norm_obs(s_obs, st.v, dv_obs, vl_obs))
        else:
            params = self.pg

        a_l_raw = (vl_obs - st.vl_prev) / DT
        st.a_l_filt = self.alpha_al * st.a_l_filt + (1.0 - self.alpha_al) * a_l_raw
        st.vl_prev = vl_obs

        a_cmd = float(CF_FSNN_Net.acc_iidm_accel(
            torch.tensor([max(s_obs, 1e-3)]), torch.tensor([st.v]),
            torch.tensor([dv_obs]), torch.tensor([st.a_l_filt]),
            params, coolness=ACC_COOLNESS)[0])
        a_ego = _plant_step(a_cmd, st.v, st.pl_state, self.plant) if self.plant is not None else a_cmd

        # Peek the ballistic update so this step's result carries the collided flag.
        v_new = max(0.0, st.v + a_ego * DT)
        s_new = st.s + (vl - v_new) * DT           # physics uses TRUE vl (channel degrades only perception)
        collided = s_new <= 0.0

        res = StepResult(t=t, s=st.s, v=st.v, vl=vl, dv=dv, a_ego=a_ego,
                         params=params.view(-1).cpu().numpy(), collided=collided)

        st.v, st.s = v_new, s_new
        if collided:
            st.collided = True
            st.impact_dv = max(0.0, st.v - vl)
        st.t += 1
        return res

    def run(self) -> dict:
        """Replay all N steps -> same dict shape as simulate() (golden comparison)."""
        series = {k: [] for k in ("s", "v", "vl", "dv", "a_ego")}
        params_used = []
        for _ in range(self.N):
            r = self.step()
            series["s"].append(r.s); series["v"].append(r.v); series["vl"].append(r.vl)
            series["dv"].append(r.dv); series["a_ego"].append(r.a_ego)
            params_used.append(r.params)
            if r.collided:
                break
        out = {k: np.asarray(val, dtype=np.float64) for k, val in series.items()}
        out["params"] = np.asarray(params_used, dtype=np.float64)
        out["collided"] = self.st.collided
        out["min_gap"] = float(self.st.s) if self.st.collided else float(out["s"].min())
        out["impact_dv"] = float(self.st.impact_dv)
        return out
