"""EventPropStepper -- stateful per-step forward for the eventprop_alif_full family.

The eventprop layer processes a whole sequence in one custom-autograd _manual_forward
(for the EventProp *training* backward); it has no forward_step. This replicates the
per-tick INFERENCE dynamics statefully (O(1)/step) so eventprop champions (Donatello,
Michelangelo) run live in the simulator. Golden: per-step == model.forward_sequence
(tests/test_sim_eventprop.py). Reads the model's weights read-only; core/ stays frozen.

Bit-identity notes vs core.eventprop._manual_forward + LILayer_BitShift_Po2.forward:
  * po2-quantised weights precomputed once (constant -> identical values);
  * delayed input via a zero-initialised ring buffer: linear(0, W) == 0 exactly, so
    always summing all max_delay terms equals skipping the k-d<0 ones;
  * fatigue/threshold use the PREVIOUS tick's fatigue (updated after the spike);
  * LI applied inline per tick == the batch loop (same order).
"""
from collections import deque

import torch
import torch.nn.functional as F

from core.hardware import po2_quantize


class EventPropStepper:
    def __init__(self, model):
        self.model = model
        h = model.layer_hidden                       # ALIFLayer_EventProp_Full
        self.n_ticks = int(h.n_ticks)
        self.max_delay = int(h.max_delay)
        self.alpha_m = float(h.alpha_m)
        self.alpha_f = float(h.alpha_f)
        self.out_dim = int(h.out_features)
        self.in_dim = int(h.in_features)
        with torch.no_grad():
            w_po2 = po2_quantize(h.fc_weight)                                  # (out, in)
            self._w_masked = [w_po2 * h.delay_masks[d] for d in range(self.max_delay)]
            self._rec_full = po2_quantize(h.rec_U) @ po2_quantize(h.rec_V)     # (out, out)
            self._base_th = h.base_threshold.detach()                         # (out,)
            self._thresh_jump = h.thresh_jump.detach()                        # (out,)
            self._w_out = po2_quantize(model.layer_out.weight)                # (5, out)
            self._alpha_out = float(model.layer_out.alpha)
        self.reset(1, "cpu")

    def reset(self, batch=1, device="cpu"):
        self._B = int(batch)
        self._device = device
        z = torch.zeros(self._B, self.out_dim, device=device)
        self._V = z.clone()
        self._fatigue = z.clone()
        self._s_prev = z.clone()
        self._V_out = torch.zeros(self._B, self._w_out.shape[0], device=device)
        self._x_hist = deque([torch.zeros(self._B, self.in_dim, device=device)] * self.max_delay,
                             maxlen=self.max_delay)

    @torch.no_grad()
    def step(self, x_norm):
        """x_norm: (B, in) -> decoded params (B, 5). Runs n_ticks internal ticks with x_norm."""
        for _ in range(self.n_ticks):
            self._x_hist.append(x_norm)
            I = torch.zeros(self._B, self.out_dim, device=self._device)
            for d in range(self.max_delay):
                I = I + F.linear(self._x_hist[-1 - d], self._w_masked[d])
            drive = I + F.linear(self._s_prev, self._rec_full)
            V_pre = self.alpha_m * self._V + drive
            V_th = self._base_th + self._fatigue.clamp(min=0)
            fired = (V_pre > V_th).float()
            self._V = V_pre - fired * V_th
            self._fatigue = self.alpha_f * self._fatigue + fired * self._thresh_jump.clamp(min=0)
            self._s_prev = fired
            self._V_out = self._alpha_out * self._V_out + F.linear(fired, self._w_out)
        return self.model._decode_params(self._V_out)

    def read_probe(self):
        v_th = self._base_th + self._fatigue.clamp(min=0)
        return {
            "spikes": self._s_prev.detach().cpu().numpy().reshape(-1),
            "v_mem": self._V.detach().cpu().numpy().reshape(-1),
            "v_th_eff": v_th.detach().cpu().numpy().reshape(-1),
        }
