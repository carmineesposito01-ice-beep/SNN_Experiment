# Simulator — EventProp live-stepping Implementation Plan

> Executes in `cf_sim`. TDD; the golden (per-step == `forward_sequence`) is the spec.

**Goal:** Run `eventprop_alif_full` champions (Donatello=`PE_t05_gp0002`, Michelangelo=`A_lr1e2_t06_r16`) live in the simulator by giving that family a stateful per-step forward that reproduces `CF_FSNN_Net_EventProp_Full.forward_sequence()`.

**Why needed:** the eventprop layer processes the whole sequence in one custom-autograd `_manual_forward` (for the EventProp *training* backward); it has no `forward_step`. Inference needs only the forward, which is standard ALIF + LI — fully stateful-izable.

**Architecture:**
- `sim/eventprop_stepper.py::EventPropStepper(model)` — reads the model's weights (read-only; `core/` stays frozen), pre-quantises (`po2_quantize` from `core.hardware`), and runs the per-tick dynamics statefully:
  - hidden (`_manual_forward` lines 410-447): `I=Σ_d linear(x[k-d], w_po2·mask_d) + linear(s_prev, U@V)`; `V=α_m·V+I`; `fired=(V>base_th+fatigue.clamp0)`; soft-reset `V-=fired·V_th`; `fatigue=α_f·fatigue+fired·tj.clamp0`. State: `V, fatigue, s_prev` + input ring-buffer (`max_delay`, zero-init ≡ skip k-d<0).
  - LI (line 676): `V_out=α_out·V_out+linear(fired, w_out_po2)`.
  - after `n_ticks` ticks per control step → `model._decode_params(V_out)`.
- `SoftwareBackend` becomes family-aware (`isinstance(model, CF_FSNN_Net_EventProp_Full)`): `forward_step` for baseline, `EventPropStepper` for eventprop; `read_probe` delegates to the stepper's state (the eventprop model has no `layer_hidden.cell`).

**Tech:** PyTorch (cf_sim), pytest. Reuses `core.hardware.po2_quantize`, `model._decode_params`.

---

### Task 1: EventPropStepper + golden
- Test `tests/test_sim_eventprop.py`: per-step over a random seq == `forward_sequence` (max |Δ| < 1e-3 on decoded params); champion detected eventprop.
- Impl `sim/eventprop_stepper.py`.

### Task 2: family-aware SoftwareBackend
- `SoftwareBackend` routes eventprop → stepper for `infer` + `read_probe`; baseline unchanged (Plan-1 golden must still pass).
- Test: eventprop `infer` → finite (1,5); `read_probe` → binary spikes (H,).

Verify: run a full sim + render with `champions/PE_t05_gp0002` (Donatello) in cf_sim.
