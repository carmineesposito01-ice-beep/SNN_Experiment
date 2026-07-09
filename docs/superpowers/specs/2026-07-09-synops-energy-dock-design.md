# SynOps / Energy Dock — Design Spec

**Date:** 2026-07-09
**Branch/worktree:** `Simulator`
**Status:** approved design → implementation plan next

## Goal

Add a live dock showing per-tick **synaptic operations (SynOps)**, split into the
**static** (input feedforward, always-on) and **dynamic** (spike-driven) parts, with
a **dense-MAC reference** line — faithful to the FPGA scorecard so it carries the
project's real energy message: the efficiency win is **AC < MAC** (0 DSP, po2
shift-add), **not** sparsity (the net is not hyper-sparse; SynOps are comparable to
MACs).

## The model (per tick)

Let `IN`, `H`, `OUT` = input/hidden/output sizes and `R` = low-rank recurrent rank
(`rec_U (H×R) @ rec_V (R×H)`). `s` = number of hidden neurons firing this tick.

- **static** (fc input→hidden, dense continuous input, every tick): `IN · H`
- **dynamic** (spike-driven): `s·R` (rec_V, stage-1 down-projection of the spike
  vector) `+ (H·R if s>0 else 0)` (rec_U, stage-2 up-projection, active only when
  there is spike activity) `+ s·OUT` (readout, AC on spikes)
- **dense-MAC reference** (a clock-driven dense accelerator computing every synapse
  every tick — the ANN-equivalent MAC count = the parameter count):
  `IN·H + 2·R·H + H·OUT`

For the baseline R33 champion (`IN=4, H=32, OUT=5, R=8`, verified from
`rec_V.shape = (8, 32)`): static = 128, dense-MAC = `128 + 512 + 160 = 800`.
`total = static + dynamic ≤ dense-MAC` (equality at full firing), so the plot's
y-range is `[0, dense-MAC]`.

## Rank source — `read_weights["rank"]`, NOT `matrix_rank`

**Critical env finding (2026-07-09):** `np.linalg.matrix_rank` (LAPACK SVD)
triggers **OMP Error #15** in `cf_sim` — it activates numpy's *own bundled* OpenMP
runtime, distinct from the Qt/`libomp.dll.disabled` shim, and clashes with torch's
Intel `libiomp5md`. The test suite never calls SVD so it stays green, but calling
`matrix_rank` at app startup would crash the GUI. **Do not use SVD/`matrix_rank` in
the app.**

Instead, the rank is read exactly from the factor shape. Extend `read_weights()`
with an additive `"rank"` field (read-only; the frozen behavioral core —
reset/infer/step — is untouched; golden bit-identity re-verified):
- `SoftwareBackend.read_weights` (baseline): `int(lh.rec_V.shape[0])`
- `EventPropStepper.read_weights`: `int(self.model.layer_hidden.rec_V.shape[0])`

Both families factorize the recurrent (`rec_U @ rec_V`), so both expose `rec_V`.

## Components

### `sim/ui/metrics.py` (extend — pure, no deps beyond numpy)

```python
def synops(spikes_row, n_in, n_hid, n_out, rank):
    """(static, dynamic) SynOps for one tick. static = fc (always-on);
    dynamic = spike-driven rec_V + rec_U + out."""

def synops_series(spikes_matrix, n_in, n_hid, n_out, rank):
    """Vectorised over frames -> (static[], dynamic[]) arrays."""

def dense_mac(n_in, n_hid, n_out, rank):
    """Clock-driven dense-MAC equivalent per tick (= parameter count)."""
```

### `sim/ui/panels.py` — `SynOpsPanel(QWidget)`

- Plot titled `SynOps / tick (AC)`; x = time (steps), y = SynOps.
- **static** curve filled to 0 (teal) + **dynamic** band = `FillBetweenItem(total,
  static)` (amber) + white **total** line on top.
- **dense-MAC** horizontal reference (dashed gray `InfiniteLine`); y-range fixed to
  `[0, dense·1.05]` so the reference and the gap are always visible.
- Carries a cursor line (added to `_ts_panels`).
- `set_model(n_in, n_hid, n_out, rank)` computes `dense`, sets the ref + y-range.
- `update_frame(probe)` reads `probe.spikes_matrix()`, computes the series, updates
  the curves, and writes the live readout into the title:
  `SynOps/tick = {total} · {pct}% del dense-MAC ({dense})`.

### App / layout wiring

- `DOCK_ORDER` → **14** (append `"SynOps"`).
- App builds `self._synops = SynOpsPanel()`; after `read_weights()`, calls
  `set_model(w_in.shape[1], w_in.shape[0], w_out.shape[0], _w["rank"])`; adds it to
  `widgets`, `_ts_panels`, and `_redraw_series` (reads the current source probe).
- Presets: `neuro_debug` foregrounds SynOps (near SpikeRate); `overview` places all
  14; `guida` hides it.

## Non-goals / invariants

- No picojoule estimate (would need hardware constants; SynOps/tick is the honest
  live primary; energy ∝ SynOps).
- No SVD / `matrix_rank` anywhere in the app.
- Behavioral core frozen; the only core touch is the additive `read_weights["rank"]`
  (read-only) — golden suite re-run to confirm bit-identity.

## Testing (TDD)

1. **metrics** — `synops` static/dynamic (known spikes), zero-firing → dynamic 0,
   `dense_mac` == param count (800 for 4/32/5/8), `synops_series` == scalar per row.
2. **read_weights rank** — baseline `read_weights()["rank"] == 8`; eventprop returns
   its rank (>0). Golden suite stays green.
3. **SynOpsPanel** — `set_model(4,32,5,8)` → ref at 800; `update_frame` with 5/32
   firing → total == `128 + (5·8 + 32·8 + 5·5)` = 449; y-range top ≈ 840.
4. **app integration** — 14 docks; `_synops` model set with rank 8; `_redraw_series`
   updates it; cursor works.
5. **Golden suite** re-run (core additive only).
6. **Render-verify** — real `windows` Qt, SynOps dock with static floor + dynamic
   band + dense-MAC line; PNG to user.

## Plan phases

- T1 `metrics` synops/dense_mac + tests.
- T2 `read_weights["rank"]` (backend + eventprop) + golden + test; `SynOpsPanel` + test.
- T3 app+layout wiring (14 docks) + integration test + render + golden suite + docs/memory.
