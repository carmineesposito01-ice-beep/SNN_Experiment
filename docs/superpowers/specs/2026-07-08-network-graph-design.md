# Network Graph (node-link) — Design Spec

> Design phase (brainstorming output). **No implementation** — plan follows. Scoped to `sim/ui/*` plus a
> small **additive** weight read in `sim/backend.py` / `sim/eventprop_stepper.py` (no physics change →
> golden re-verified). Replaces the heat-grid `NeuronStatePanel` with a node-link graph.

**Goal:** Show the small SNN (`4 → 32 → 5`) as a **node-link graph of "pallini"** whose per-tick colouring and
edge-highlighting reveal the **active spike pathways** — the sparse "tragitti" that carry signal at each tick.

**Motivation (user):** the heat-grid was cramped and couldn't show all 32 clearly. As a *spiking* net it is
never all-active at once; a graph where the **routes out of firing neurons light up** shows *where* signal
flows now — the single most useful thing this dock can convey. (All 32 were in fact rendered in the grid — 32
opaque cells + 3 padding — the grid was just illegible.)

---

## 1. Decisions (locked in brainstorming, 2026-07-08)

| # | Decision | Choice |
|---|---|---|
| D1 | Viz | **Node-link graph** (`pg.GraphItem` + `ScatterPlotItem`), replacing the heat-grid `NeuronStatePanel` |
| D2 | Nodes | 4 input · 32 hidden · 5 output circles, coloured by activation (v_mem heat + white ring on spiking) |
| D3 | Edges | **Full connectivity** (input→hidden, recurrent hidden→hidden 32×32, hidden→output) as a **faint static skeleton**, opacity ∝ \|weight\| (weak edges vanish → no solid block) |
| D4 | Active pathways | Per tick, **edges out of firing hidden neurons** (recurrent + to output) are **highlighted white** → the sparse spike routes. **Headline behaviour.** |
| D7 | Labels | Group titles carry the **type**; input/output nodes carry the **quantity name** — input `s,v,Δv,vl` (`input · osservazione`), hidden (`hidden · 32 ALIF`), output `v0,T,s0,a,b` (`output · parametri (readout)`). Hidden nodes unlabelled (32) |
| D5 | Topology | Weights read **family-aware, additively** (`read_weights()` on the backend); golden bit-identity re-verified |
| D6 | Energy dock | **DEFERRED** to Phase 3a/b backlog (study §6) — not in this spec |

**Architecture recap:** `layer_hidden.fc_weight (32,4)` = input→hidden; `rec_U(32,8)@rec_V(8,32)` = recurrent
(32,32); `layer_out.fc_weight (5,32)` = hidden→output. Eventprop: `_w_masked` (sum over delays), `_rec_full`,
`_w_out`.

---

## 2. Topology extraction (additive, golden-preserving)

`SoftwareBackend.read_weights() -> {"w_in": (H,in), "w_rec": (H,H), "w_out": (out,H)}`, family-aware:
- **baseline:** `w_in = layer_hidden.fc_weight`; `w_rec = rec_U @ rec_V`; `w_out = layer_out.fc_weight`.
- **eventprop:** delegate to `EventPropStepper.read_weights()`: `w_in = Σ_d _w_masked[d]`, `w_rec = _rec_full`,
  `w_out = _w_out`.

All read-only (`.detach().cpu().numpy()`); **no step math touched** → full golden suite re-run to prove
bit-identity. Called **once** by the app after loading the champion; passed to the panel via `set_topology`.

## 3. `NeuronGraphPanel` (new, replaces `NeuronStatePanel`)

One `pg.PlotWidget` (axes hidden, aspect free) holding three stacked items, bottom→top:

1. **`_skeleton`** (`pg.GraphItem`, symbols off): all edges, pen per-edge with **opacity ∝ |weight|** (normalised
   per matrix), thin, cool grey. Built **once** in `set_topology(w_in, w_rec, w_out)`. Recurrent **self-edges
   (i==i) skipped**.
2. **`_active`** (`pg.GraphItem`, symbols off): only the **active edges** this tick — the outgoing recurrent +
   output edges of hidden neurons that **spiked** — **white** pen, thicker. Rebuilt each `update_frame`
   (sparse → cheap). Input→hidden stays in the skeleton (continuous drive, not a spike event).
3. **`_nodes`** (`pg.ScatterPlotItem`): the 41 nodes; per-node **brush = viridis(activation)** (input value /
   v_mem / param value), and a **white ring pen** on hidden nodes that spiked. Updated each frame (41 points →
   cheap). White = the "firing/active" language, shared by the spike rings and the active edges.

**Labels (D7):** three group titles (`input · osservazione`, `hidden · 32 ALIF`, `output · parametri (readout)`);
per-node text at the input nodes (`s`, `v`, `Δv`, `vl` — order from `_norm_obs`: gap, ego speed, closing speed,
leader speed) and at the output nodes (`v0`, `T`, `s0`, `a`, `b` = `PARAM_NAMES`). Hidden nodes are unlabelled
(32 dots). Text as `pg.TextItem`s placed beside each I/O node + `PlotItem` titles or a small header row.

**Layout (`pos`, computed once):** input at `x=0`, hidden at `x=1`, output at `x=2`; each group's nodes spread
evenly on `y`. Node index map: `0..3` input, `4..35` hidden, `36..40` output. `adj` built once from the three
weight matrices.

**`set_topology(w_in, w_rec, w_out)`:** compute `pos`, `adj`, per-edge skeleton pens (by |weight|); store the
adjacency split so `update_frame` can pick "edges whose source hidden neuron fired".

**`update_frame(probe)`:** read `frames()[-1]`; set node brushes/rings from `input`/`v_mem`/`spikes`/`params`;
set `_active` adjacency = recurrent+output edges whose source hidden index is in `spikes>0`.

## 4. Perf

Splitting into three items keeps per-frame work cheap: the 1312-edge **skeleton is drawn once**; per frame only
the **41 node brushes** and the **sparse active-edge set** (~15% firing → a few hundred at most, usually fewer)
are updated. If `GraphItem` per-edge pen updates still prove heavy, fall back to a single warm colour for all
active edges (no per-edge alpha) — verified in the plan's render step.

## 5. Testing (headless, `cf_sim`)

- **read_weights**: baseline + eventprop return `w_in (H,in)`, `w_rec (H,H)`, `w_out (out,H)` of the right
  shapes; **full golden suite green** (bit-identity preserved).
- **NeuronGraphPanel**: `set_topology` builds `pos` of 41 nodes and an `adj` of the expected edge count
  (`in*H + (H*H - H) + out*H`, self-edges removed); `update_frame` with a known probe sets 41 node brushes and
  an `_active` adjacency whose edges all originate from a spiking hidden neuron (count matches Σ fan-out of
  firing neurons over recurrent+output).
- **Docks/app**: the `NetState` dock now hosts `NeuronGraphPanel`; app calls `set_topology` from the champion;
  9 docks unchanged; smoke tests pass.
- **Render**: real-platform inspect — faint skeleton + bright active pathways from firing neurons; press
  Brake/Run and watch the tragitti move.

## 6. Error handling / edge cases

- Empty probe → no-op. `frame.input` None → input nodes drawn neutral, hidden/output still coloured.
- `H`/`in`/`out` read from the weight shapes (no hardcode 32/4/5).
- No spikes this tick → `_active` empty (only the faint skeleton shows).

## 7. Scope boundaries (OUT)

- **Energy/SynOps dock** → Phase 3a/b backlog (study §6).
- Input→hidden edges are not spike-highlighted (continuous drive); only hidden-out edges form the active set.
- Trajectory/Safety (Phase 3a) and scrub (Phase 3b) unchanged/pending.
- SpikeRate dock + input capture stay as-is.

## 8. File structure

| File | Change |
|---|---|
| `sim/backend.py` | **Modify** (additive) — `read_weights()` (baseline path) |
| `sim/eventprop_stepper.py` | **Modify** (additive) — `read_weights()` |
| `sim/ui/panels.py` | **Modify** — add `NeuronGraphPanel`; remove `NeuronStatePanel` (+ `_GROUP_BORDERS`, heat helpers) |
| `sim/ui/app.py` | **Modify** — build `NeuronGraphPanel`, call `set_topology` from the champion weights |
| `tests/test_sim_input_capture.py` | **Append** — `read_weights` shape assertions (rename or extend file) |
| `tests/test_sim_panels.py` | **Modify** — drop NeuronState tests; add NeuronGraph tests |
| `tests/test_sim_ui_smoke.py` | Unchanged dock names (dock key stays `NetState`); may add a topology-wired assertion |

> Dock key stays **`NetState`** (network-state dock) to avoid churn in `DOCK_ORDER`/presets; only the panel
> class changes (heat-grid → graph). Rename to `NetGraph` is optional and deferred.
