# Network State Map + Spike-Rate — Design Spec (network-viz redesign)

> Design phase (brainstorming output). **No implementation** — plan follows. Scoped to `sim/ui/*` plus a
> small **additive** capture of the network input in `sim/backend.py`, `sim/eventprop_stepper.py`,
> `sim/probe.py` (no physics change → golden bit-identity re-verified). Supersedes the time-raster dock.

**Goal:** Replace the spike-raster-over-time (illegible for 30+ neurons) with an **instantaneous
neuron-state map** (all neurons at the current tick, grouped input/hidden/output with coloured borders),
and recover the lost temporal view with a small **spike-rate trend** dock beside it.

**Motivation (user):** a raster of 32 neurons × time is hard to read; the per-tick *state* of every
neuron is more useful, and the firing *trend* is better shown as a single rate line than a raster.

**This is a focused redesign** between Phase 2 (dock shell) and the pending Phase 3a metric panels
(trajectory/safety). Runs in `cf_sim`.

---

## 1. Decisions (locked in brainstorming, 2026-07-08)

| # | Decision | Choice |
|---|---|---|
| D1 | The `Raster` dock | **Replaced** by a `NetState` dock (instantaneous map); the time-raster is dropped |
| D2 | New dock | `SpikeRate` — firing-rate (% of hidden neurons spiking) over time |
| D3 | Map groups | **input + hidden + output**, each a coloured-bordered, labelled section |
| D4 | Hidden colouring | **v_mem heat + white overlay on neurons that spiked this tick** |
| D5 | Input data | **Additive capture**: backend/eventprop store the last `x_norm`; `read_probe` returns `"input"`; `ProbeFrame` gains an optional `input` field. No physics change |
| D6 | Dock count | 8 → **9** (`Raster`→`NetState`, +`SpikeRate`); the 4 presets are updated to place both |

**Architecture (both families):** `4 inputs → H hidden ALIF (H=32 for R33) → 5 outputs`. `read_probe`
already exposes hidden (`spikes`/`v_mem`/`v_th_eff`, shape `(H,)`); outputs are the 5 `params` (already
in the probe); inputs (`x_norm`, shape `(4,)`) flow through `step()`/`infer()` but are not yet stored.

---

## 2. Data capture (additive, golden-preserving)

- **`SoftwareBackend`** (`sim/backend.py`): store `self._last_input = obs` in `infer()`; `read_probe()`
  adds `"input": self._last_input` (numpy `(in,)`), or a zero vector before the first step.
- **`EventPropStepper`** (`sim/eventprop_stepper.py`): store `self._last_x = x_norm` in `step()`;
  `read_probe()` adds `"input"` likewise.
- **`ProbeFrame`** (`sim/probe.py`): add field `input: np.ndarray = None` (optional). `record()` reads
  `probe.get("input")` and stores it (or an empty array). Existing callers that don't pass `"input"`
  keep working (backward compatible) → `test_sim_probe.py` unaffected.

**No step math changes.** The full golden suite is re-run to prove bit-identity (the input is data that
already flows; we only retain a reference to it).

## 3. Components

### 3.1 `NeuronStatePanel` (new, in `sim/ui/panels.py`) — the `NetState` dock

Instantaneous state of the latest probe frame, three vertically-stacked groups in one
`GraphicsLayoutWidget`, each a heat `ImageItem` with a coloured `ViewBox` border + a group title:

| Group | Cells | Heat source | Border |
|---|---|---|---|
| **input** | `len(frame.input)` (=4) in a 1×N strip | input value | blue |
| **hidden** | `H` (=32) in an auto-sized ~√H grid | `v_mem` (viridis) **+ white overlay where `spikes==1`** | purple |
| **output** | 5 in a 1×5 strip, labelled `v0…b` | param value | green |

- Grid arrangement is computed from `H` (`rows=int(√H)`, `cols=ceil(H/rows)`, pad the flat array to
  `rows*cols` with `NaN` → transparent) — **no hardcoded 32**.
- Hidden is two stacked `ImageItem`s: base = viridis(normalised `v_mem`), overlay = RGBA white where
  `spikes==1` (transparent elsewhere) → shows both sub-threshold charge and who fired.
- `update_frame(probe)` reads `probe.frames()[-1]` (current tick). With scrub (3b) this becomes the tick
  at the cursor — out of scope here.

### 3.2 `SpikeRatePanel` (new, in `sim/ui/panels.py`) — the `SpikeRate` dock

- Line plot, X = time (steps), Y = firing rate % = `spikes_matrix().mean(axis=1) * 100` per tick.
- Same perf config as the other line plots (`setDownsampling(auto, peak)`, `setClipToView(True)`).

### 3.3 Removed: `RasterPanel`

Superseded by `NeuronStatePanel` + `SpikeRatePanel`. Its tests (`test_raster_panel_updates`,
`test_raster_orientation_time_x_neuron_y`) are removed; replaced by the new panels' tests.

### 3.4 `sim/ui/app.py` + `sim/ui/layout.py`

- `DOCK_ORDER = ["Road", "NetState", "SpikeRate", "v_mem", "v0", "T", "s0", "a", "b"]` (9).
- App builds `NeuronStatePanel` + `SpikeRatePanel` instead of `RasterPanel`; `SpikeRate` joins the live
  panels + X-linked to the param master; `NetState` updates from the probe each paint.
- The 4 presets (`layout.py`) place both new docks — e.g. `Neuro-debug` = NetState + SpikeRate + v_mem
  prominent; `Overview` all 9; `Guida`/`Identificazione` compress the network docks.

## 4. Testing (headless, `cf_sim`)

- **Capture**: `SoftwareBackend.read_probe()` and `EventPropStepper.read_probe()` include `"input"` of
  the right length; `ProbeFrame.input` populated when passed, defaulted when not; **full golden suite green**.
- **NeuronStatePanel**: builds 3 group images; `update_frame` on a probe with known `input`/`spikes`/`params`
  sets image shapes = (in), (rows×cols≥H), (5); the spike overlay marks the right cells (a spiked neuron
  → white in the overlay array); no raise on H not a perfect rectangle.
- **SpikeRatePanel**: firing-rate series equals `spikes_matrix().mean(axis=1)*100` (exact on a known probe).
- **Docks/presets**: 9 docks present; `Neuro-debug`/`Overview` place NetState+SpikeRate; preset→Overview
  restores all 9.
- **Render**: real-platform inspect of NetState (3 groups, borders, spike overlay) + SpikeRate.

## 5. Error handling / edge cases

- Empty probe (no frames yet) → panels no-op (no crash).
- `frame.input` None/empty (old data / capture off) → input group shows an empty/zeroed strip, hidden+output
  still render.
- `H` not a perfect rectangle → NaN-pad to `rows*cols`, transparent cells.

## 6. Scope boundaries (OUT — later)

- **Scrub / time cursor** (NetState at an arbitrary tick) → Phase 3b.
- **Trajectory + Safety panels** → the pending Phase 3a proper (resumes after this).
- Per-neuron drill-down, input-encoding internals → later.

## 7. File structure

| File | Change |
|---|---|
| `sim/backend.py` | **Modify** (additive) — store + expose `"input"` in `read_probe` |
| `sim/eventprop_stepper.py` | **Modify** (additive) — store + expose `"input"` |
| `sim/probe.py` | **Modify** (additive) — optional `ProbeFrame.input` |
| `sim/ui/panels.py` | **Modify** — add `NeuronStatePanel`, `SpikeRatePanel`; remove `RasterPanel` |
| `sim/ui/layout.py` | **Modify** — `DOCK_ORDER` (9), presets place NetState+SpikeRate |
| `sim/ui/app.py` | **Modify** — build/wire the two new panels instead of raster |
| `tests/test_sim_panels.py` | **Modify** — drop raster tests; add NeuronState + SpikeRate tests |
| `tests/test_sim_probe.py`, `tests/test_sim_backend.py`, `tests/test_sim_eventprop.py` | **Append** — `"input"` capture assertions |
| `tests/test_sim_ui_smoke.py` | **Modify** — dock names/count (9), preset assertions |
