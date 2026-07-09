"""Family-aware BATCHED forward + platoon/ring runners for the meso/macro analysis mode.

Reuses the validated utils.platoon_eval sims via their additive `forward=` hook, injecting a
batched forward that works for BOTH families: BPTT -> model.forward_step(N,4); EventProp ->
EventPropStepper.reset(N) + step(N,4). The frozen core is only read (EventPropStepper.step unchanged).
"""
from core.network import CF_FSNN_Net_EventProp_Full
from sim.eventprop_stepper import EventPropStepper
from utils.platoon_eval import (_norm_obs_batch, simulate_platoon, platoon_metrics,   # noqa: F401
                                simulate_ring, fundamental_diagram)


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
