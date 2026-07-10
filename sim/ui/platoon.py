"""Family-aware BATCHED forward + platoon/ring runners for the meso/macro analysis mode.

Reuses the validated utils.platoon_eval sims via their additive `forward=` hook, injecting a
batched forward that works for BOTH families: BPTT -> model.forward_step(N,4); EventProp ->
EventPropStepper.reset(N) + step(N,4). The frozen core is only read (EventPropStepper.step unchanged).
"""
import numpy as np

from core.network import CF_FSNN_Net_EventProp_Full
from sim.eventprop_stepper import EventPropStepper
from utils.platoon_eval import (_norm_obs_batch, platoon_metrics, simulate_platoon,   # noqa: F401
                                simulate_ring)


class _BatchedForward:
    """Stateful batched forward over N vehicles (one hidden state per vehicle)."""
    def __init__(self, champion, device="cpu"):
        self.model = champion.model
        self.device = device
        self._eventprop = isinstance(self.model, CF_FSNN_Net_EventProp_Full)
        self._stepper = EventPropStepper(self.model) if self._eventprop else None

    def reset(self, n, device=None):
        dev = device or self.device
        if self._eventprop:
            self._stepper.reset(n, dev)
        else:
            self.model.eval()
            self.model.reset_state(n, dev)

    def infer(self, gap, v, dv, vl):
        x = _norm_obs_batch(gap, v, dv, vl).to(self.device)      # (N,4) physical -> normalised
        return self._stepper.step(x) if self._eventprop else self.model.forward_step(x)


def batched_forward(champion, n, device="cpu"):
    return _BatchedForward(champion, device)


def run_platoon(champion, params_gt, n_vehicles, v_leader_profile, device="cpu"):
    fw = _BatchedForward(champion, device)
    return simulate_platoon(champion.model, params_gt, n_vehicles, v_leader_profile,
                            device=device, forward=fw)


def run_ring(champion, params_gt, n_vehicles, ring_length, n_steps, device="cpu", perturb=0.1):
    fw = _BatchedForward(champion, device)
    return simulate_ring(champion.model, params_gt, n_vehicles, ring_length, n_steps,
                         device=device, perturb=perturb, forward=fw)


def run_fundamental_diagram(champion, params_gt, densities_veh_per_km, ring_length=1000.0,
                            n_steps=600, device="cpu", on_point=None):
    """Family-aware fundamental diagram: sweep densities -> Edie (rho, Q, V, wave) per point.

    Loops run_ring (which injects the family-aware batched forward, so BOTH BPTT and EventProp
    work) and reuses the Q/V/wave point formula of platoon_eval.fundamental_diagram. That function
    is NOT called directly: it hardwires the baseline forward and would break EventProp.
    LAPACK-free (mean/std only) -> safe in cf_sim. `on_point(i, total)` (optional) is called before
    each density point so a GUI can show bounded progress on this multi-second sweep.
    """
    pts = []
    total = len(densities_veh_per_km)
    for i, rho_km in enumerate(densities_veh_per_km):
        if on_point is not None:
            on_point(i, total)
        n = max(2, int(round(rho_km / 1000.0 * ring_length)))
        rec = run_ring(champion, params_gt, n, ring_length, n_steps, device=device)
        v = rec["v"]
        w = int(n_steps * 0.5)                                  # second half = regime
        V = float(v[w:].mean())                                 # space-time mean speed [m/s]
        rho = n / ring_length * 1000.0                          # veh/km
        Q = rho * V * 3.6                                       # veh/h
        wave = float(np.std(v[w:].mean(axis=1)))               # residual stop&go oscillation
        pts.append({"rho_veh_km": round(rho, 1), "Q_veh_h": round(Q, 1),
                    "V_m_s": round(V, 2), "V_km_h": round(V * 3.6, 1),
                    "n": n, "wave_std": round(wave, 3), "unstable": wave > 0.5})
    return pts
