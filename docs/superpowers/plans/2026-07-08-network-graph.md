# Network Graph (node-link) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use checkbox (`- [ ]`) syntax.
> Runs in **`cf_sim`** (offscreen for Qt). Spec: `docs/superpowers/specs/2026-07-08-network-graph-design.md`. pyqtgraph 0.14 API pre-verified: `GraphItem.setData(pos, adj, pen=<per-edge record array>, size=0)` (edges-only), `pen=mkPen('#fff')` + empty `adj` for the active overlay, `ScatterPlotItem.setData(brush=[...], pen=[...])` (per-node fill+ring), `TextItem`.

**Goal:** Replace the heat-grid `NeuronStatePanel` with a **node-link graph** — layered colored circles, a faint weight-skeleton, and **white active pathways** out of firing neurons (the spike "tragitti"), plus input/output labels.

**Architecture:** additive `read_weights()` (family-aware) → `NeuronGraphPanel` with three items (skeleton `GraphItem` set once, active `GraphItem` per-tick, nodes `ScatterPlotItem` per-tick) + `TextItem` labels → app calls `set_topology` from the champion weights. No physics change; golden re-verified.

**Tech Stack:** PySide6 6.11, pyqtgraph 0.14 (`GraphItem`, `ScatterPlotItem`, `TextItem`, viridis LUT), NumPy, torch, pytest — `cf_sim`.

---

## File Structure

| File | Change |
|---|---|
| `sim/backend.py` | **Modify** (additive) — `SoftwareBackend.read_weights()` |
| `sim/eventprop_stepper.py` | **Modify** (additive) — `EventPropStepper.read_weights()` |
| `sim/ui/panels.py` | **Modify** — add `NeuronGraphPanel` + `_INPUT_NAMES`; remove `NeuronStatePanel` (+ heat helpers, `_GROUP_BORDERS`) |
| `sim/ui/app.py` | **Modify** — build `NeuronGraphPanel`; `set_topology` from `read_weights()` |
| `tests/test_sim_input_capture.py` | **Append** — `read_weights` shape assertions |
| `tests/test_sim_panels.py` | **Modify** — drop NeuronState tests; add NeuronGraph tests |

---

### Task 1: `read_weights()` — family-aware topology (additive)

**Files:** Modify `sim/backend.py`, `sim/eventprop_stepper.py`; append to `tests/test_sim_input_capture.py`.

- [ ] **Step 1: Write failing tests** (append to `tests/test_sim_input_capture.py`):

```python
def test_baseline_read_weights_shapes():
    b = SoftwareBackend(load_champion(BASELINE).model)
    b.reset()
    w = b.read_weights()
    assert w["w_in"].shape == (32, 4) and w["w_rec"].shape == (32, 32) and w["w_out"].shape == (5, 32)


def test_eventprop_read_weights_shapes():
    b = SoftwareBackend(load_champion(EVENTPROP).model)
    b.reset()
    w = b.read_weights()
    assert w["w_in"].shape == (32, 4) and w["w_rec"].shape == (32, 32) and w["w_out"].shape == (5, 32)
```

- [ ] **Step 2: Run — verify FAIL** (`AttributeError: 'SoftwareBackend' object has no attribute 'read_weights'`)

Run: `conda run -n cf_sim python -m pytest tests/test_sim_input_capture.py -q`

- [ ] **Step 3a: `sim/backend.py`** — add `read_weights` to `SoftwareBackend`:

```python
    def read_weights(self) -> dict:
        """Static topology for the node-link graph: input->hidden, recurrent, hidden->output.
        Baseline reads the layers; eventprop delegates to the stepper."""
        if self._eventprop:
            return self._stepper.read_weights()
        lh = self.model.layer_hidden
        return {
            "w_in": lh.fc_weight.detach().cpu().numpy(),
            "w_rec": (lh.rec_U @ lh.rec_V).detach().cpu().numpy(),
            "w_out": self.model.layer_out.fc_weight.detach().cpu().numpy(),
        }
```

- [ ] **Step 3b: `sim/eventprop_stepper.py`** — add `read_weights` (weights live on the stepper):

```python
    def read_weights(self) -> dict:
        w_in = sum(self._w_masked[d] for d in range(self.max_delay))
        return {
            "w_in": w_in.detach().cpu().numpy(),
            "w_rec": self._rec_full.detach().cpu().numpy(),
            "w_out": self._w_out.detach().cpu().numpy(),
        }
```

- [ ] **Step 4: Run — verify PASS + golden**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_input_capture.py tests/test_sim_backend.py tests/test_sim_eventprop.py -q`
Expected: PASS (weights read; step math untouched → golden bit-identical).

- [ ] **Step 5: Commit**

```bash
git add sim/backend.py sim/eventprop_stepper.py tests/test_sim_input_capture.py
git commit -m "feat(sim): additive read_weights() (w_in/w_rec/w_out) for the network graph"
```

---

### Task 2: `NeuronGraphPanel` (replaces `NeuronStatePanel`)

**Files:** Modify `sim/ui/panels.py`; modify `tests/test_sim_panels.py`.

- [ ] **Step 1: Swap the panel tests** in `tests/test_sim_panels.py`:
  1. Import: `from sim.ui.panels import NeuronGraphPanel, ParamPanel, SpikeRatePanel, VmemPanel` (drop `NeuronStatePanel`).
  2. **Delete** `test_neuron_state_panel_groups_and_spike_overlay`.
  3. **Add**:

```python
def test_neuron_graph_topology_and_active_edges(qapp):
    import numpy as np
    H, IN, OUT = 6, 4, 5
    rng = np.random.default_rng(0)
    w_in = rng.standard_normal((H, IN)); w_rec = rng.standard_normal((H, H)); w_out = rng.standard_normal((OUT, H))
    panel = NeuronGraphPanel()
    panel.set_topology(w_in, w_rec, w_out)
    assert panel._pos.shape == (IN + H + OUT, 2)                       # 15 nodes
    exp_edges = IN * H + (H * H - H) + OUT * H                          # in + recurrent(no self) + out
    assert panel._skeleton.adjacency.shape[0] == exp_edges
    # a probe where hidden neurons 0 and 2 fired -> active edges only from those sources
    spikes = np.zeros(H); spikes[[0, 2]] = 1
    p = AttributeProbe(capacity=5)
    p.record(0, {"spikes": spikes, "v_mem": np.linspace(0, 1, H), "v_th_eff": np.ones(H),
                 "input": np.array([0.1, 0.2, 0.3, 0.4])}, np.arange(OUT, dtype=float))
    panel.update_frame(p)
    active = panel._active.adjacency
    assert active.shape[0] == int((panel._rec_out_src == 0).sum() + (panel._rec_out_src == 2).sum())
    assert active.shape[0] > 0
```

  4. `test_spike_rate_panel_series` stays.

- [ ] **Step 2: Run — verify FAIL** (`ImportError: NeuronGraphPanel`)

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -q`

- [ ] **Step 3: Edit `sim/ui/panels.py`** — remove `NeuronStatePanel` (and `_GROUP_BORDERS`), add:

```python
_INPUT_NAMES = ["s", "v", "Δv", "vl"]   # order from _norm_obs: gap, ego speed, closing speed, leader speed


class NeuronGraphPanel(QWidget):
    """Node-link view of the SNN (input | hidden | output): coloured circles (viridis(activation)),
    a faint weight-skeleton (opacity ~ |weight|), and WHITE active pathways out of firing neurons."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget()
        self._plot.hideAxis("left")
        self._plot.hideAxis("bottom")
        self._plot.setMenuEnabled(False)
        layout.addWidget(self._plot)
        self._lut = pg.colormap.get("viridis").getLookupTable(0.0, 1.0, 256)
        self._skeleton = pg.GraphItem()
        self._active = pg.GraphItem()
        self._nodes = pg.ScatterPlotItem()
        for it in (self._skeleton, self._active, self._nodes):
            self._plot.addItem(it)
        self._pos = None
        self._n_in = self._n_hid = self._n_out = 0
        self._rec_out_adj = None      # (E,2) recurrent + output edges (spike-carrying)
        self._rec_out_src = None      # (E,) source hidden index of each such edge

    def _brushes(self, vals):
        v = np.asarray(vals, dtype=np.float64).reshape(-1)
        vmin, vmax = float(np.nanmin(v)), float(np.nanmax(v))
        idx = np.clip(((v - vmin) / (vmax - vmin + 1e-9) * 255).astype(int), 0, 255)
        return [pg.mkBrush(int(r), int(g), int(b)) for r, g, b in self._lut[idx][:, :3]]

    def set_topology(self, w_in, w_rec, w_out):
        w_in = np.asarray(w_in, dtype=np.float64)
        w_rec = np.asarray(w_rec, dtype=np.float64)
        w_out = np.asarray(w_out, dtype=np.float64)
        H, IN = w_in.shape
        OUT = w_out.shape[0]
        self._n_in, self._n_hid, self._n_out = IN, H, OUT

        def yspread(n, span=32.0):
            return np.linspace(0.0, span, n) if n > 1 else np.array([span / 2])

        half = (H + 1) // 2
        pin = [(0.0, y) for y in yspread(IN)]
        phid = ([(1.0, y) for y in yspread(half)] + [(1.4, y) for y in yspread(H - half)])
        pout = [(2.6, y) for y in yspread(OUT)]
        self._pos = np.array(pin + phid + pout, dtype=float)
        bi, bh, bo = 0, IN, IN + H

        e_in = [(bi + i, bh + j) for j in range(H) for i in range(IN)]
        w_e_in = [abs(w_in[j, i]) for j in range(H) for i in range(IN)]
        e_rec = [(bh + i, bh + j) for i in range(H) for j in range(H) if i != j]
        w_e_rec = [abs(w_rec[j, i]) for i in range(H) for j in range(H) if i != j]
        src_rec = [i for i in range(H) for j in range(H) if i != j]
        e_out = [(bh + j, bo + k) for j in range(H) for k in range(OUT)]
        w_e_out = [abs(w_out[k, j]) for j in range(H) for k in range(OUT)]
        src_out = [j for j in range(H) for k in range(OUT)]

        all_adj = np.array(e_in + e_rec + e_out, dtype=int)
        all_w = np.array(w_e_in + w_e_rec + w_e_out, dtype=float)
        alpha = np.clip(all_w / (all_w.max() + 1e-9) * 55 + 6, 6, 61).astype(np.ubyte)
        pens = np.zeros(len(all_adj), dtype=[('red', np.ubyte), ('green', np.ubyte),
                                             ('blue', np.ubyte), ('alpha', np.ubyte), ('width', float)])
        pens['red'][:] = 150; pens['green'][:] = 150; pens['blue'][:] = 150
        pens['alpha'] = alpha; pens['width'] = 1.0
        self._skeleton.setData(pos=self._pos, adj=all_adj, pen=pens, size=0)

        self._rec_out_adj = np.array(e_rec + e_out, dtype=int)
        self._rec_out_src = np.array(src_rec + src_out, dtype=int)
        self._active.setData(pos=self._pos, adj=np.empty((0, 2), dtype=int),
                             pen=pg.mkPen("#ffffff", width=2.2), size=0)
        self._add_labels()

    def _text(self, s, x, y, anchor, color):
        t = pg.TextItem(s, color=color, anchor=anchor)
        t.setPos(float(x), float(y))
        self._plot.addItem(t)

    def _add_labels(self):
        for i in range(self._n_in):
            self._text(_INPUT_NAMES[i] if i < len(_INPUT_NAMES) else f"in{i}",
                       self._pos[i, 0], self._pos[i, 1], (1.2, 0.5), "#8fb7e0")
        for k in range(self._n_out):
            self._text(PARAM_NAMES[k] if k < len(PARAM_NAMES) else f"out{k}",
                       self._pos[self._n_in + self._n_hid + k, 0],
                       self._pos[self._n_in + self._n_hid + k, 1], (-0.2, 0.5), "#88d6a0")
        top = float(self._pos[:, 1].max()) + 2.5
        self._text("input · osservazione", 0.0, top, (0.5, 1.0), "#8fb7e0")
        self._text("hidden · 32 ALIF", 1.2, top, (0.5, 1.0), "#c9a0e8")
        self._text("output · parametri", 2.6, top, (0.5, 1.0), "#88d6a0")

    def update_frame(self, probe):
        frames = probe.frames()
        if not frames or self._pos is None:
            return
        f = frames[-1]
        inp = (np.asarray(f.input, dtype=np.float64).reshape(-1)
               if (f.input is not None and np.size(f.input)) else np.zeros(self._n_in))
        vals = np.concatenate([inp[:self._n_in],
                               np.asarray(f.v_mem, dtype=np.float64).reshape(-1)[:self._n_hid],
                               np.asarray(f.params, dtype=np.float64).reshape(-1)[:self._n_out]])
        spk = np.asarray(f.spikes, dtype=np.float64).reshape(-1)[:self._n_hid] > 0
        pens = [pg.mkPen(None)] * len(vals)
        for j in range(self._n_hid):
            if spk[j]:
                pens[self._n_in + j] = pg.mkPen("#ffffff", width=2.0)
        self._nodes.setData(pos=self._pos, brush=self._brushes(vals), pen=pens, size=13)
        mask = spk[self._rec_out_src]
        self._active.setData(pos=self._pos, adj=self._rec_out_adj[mask],
                             pen=pg.mkPen("#ffffff", width=2.2), size=0)
```

> `GraphItem.adjacency` holds the current `adj` array (used by the tests). `PARAM_NAMES` already exists in the module.

- [ ] **Step 4: Run — verify PASS**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -q`
Expected: PASS. If `GraphItem` exposes the adjacency under a different attribute than `.adjacency`, adjust the test to read `panel._skeleton.data['adj']` (verified at run time).

- [ ] **Step 5: Commit**

```bash
git add sim/ui/panels.py tests/test_sim_panels.py
git commit -m "feat(sim/ui): NeuronGraphPanel node-link (skeleton + white active pathways + labels); remove heat-grid"
```

---

### Task 3: Wire the graph into the app

**Files:** Modify `sim/ui/app.py`; possibly `tests/test_sim_ui_smoke.py`.

- [ ] **Step 1: Edit `sim/ui/app.py`**
  - Import: replace `NeuronStatePanel` with `NeuronGraphPanel` in the `from sim.ui.panels import (...)` line.
  - Build it: `self._netstate = NeuronGraphPanel()` (keep the attribute name `_netstate` + dock key `NetState` → no `DOCK_ORDER`/preset/widget-map churn).
  - After building it, feed the topology from the champion (once): right after the panel/X-link block, add:

```python
        _topo = SoftwareBackend(self._champ.model)
        _topo.reset()
        _w = _topo.read_weights()
        self._netstate.set_topology(_w["w_in"], _w["w_rec"], _w["w_out"])
```

  (`SoftwareBackend` is already imported.)

- [ ] **Step 2: Run — smoke + panels + layout**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py tests/test_sim_panels.py tests/test_sim_layout.py -q`
Expected: PASS (dock key `NetState` unchanged; `_netstate` now a graph panel).

- [ ] **Step 3: Full golden suite**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_state.py tests/test_sim_backend.py tests/test_sim_stepper.py tests/test_sim_scenario.py tests/test_sim_events.py tests/test_sim_probe.py tests/test_sim_replay.py tests/test_sim_loop.py tests/test_sim_input_capture.py tests/test_sim_panels.py tests/test_sim_layout.py tests/test_sim_ui_smoke.py tests/test_sim_eventprop.py tests/test_champion_io.py -q`
Expected: PASS (all).

- [ ] **Step 4: Render (real platform) + inspect + send**

Render the Neuro-debug preset (NetState prominent). Confirm: layered circles (input `s,v,Δv,vl` labelled, output `v0..b` labelled), faint grey skeleton, **white** active pathways out of the white-ringed firing neurons; press Run/Brake and watch the tragitti move. Send the PNG to the user.

- [ ] **Step 5: Commit + push**

```bash
git add sim/ui/app.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim/ui): wire NeuronGraphPanel + set_topology from champion weights"
git push
```

---

## Self-Review

**Spec coverage:** D1 node-link replaces heat-grid (T2 + T3) ✓ · D2 coloured circles + spike ring (T2 `_brushes` + ring pens) ✓ · D3 faint skeleton opacity∝|w| (T2 `pens` alpha) ✓ · D4 **white** active edges out of firing neurons (T2 `_active` + `_rec_out_src` mask) ✓ · D5 additive `read_weights` (T1, golden re-verified) ✓ · D6 energy deferred (not here) ✓ · D7 labels input `s,v,Δv,vl` / output `v0..b` + group titles (T2 `_add_labels`) ✓.

**Placeholder scan:** none — full code for every unit; the one runtime caveat (GraphItem adjacency attribute name) is called out with a fallback in T2 Step 4.

**Consistency:** `read_weights` (T1) → `set_topology(w_in,w_rec,w_out)` (T2) called by the app (T3). `_rec_out_src`/`_rec_out_adj` built in `set_topology`, consumed in `update_frame`. Dock key stays `NetState`, attribute `_netstate` → no churn in `DOCK_ORDER`/presets/smoke. `PARAM_NAMES` reused for output labels.

**Scope:** energy/SynOps dock deferred (study §6 backlog); input→hidden edges stay in the skeleton (not spike-highlighted); SpikeRate + input-capture unchanged.

---

## Execution Handoff

Inline execution (established), in `cf_sim`, TDD per task, render-inspect + send at Task 3 Step 4. Then resume the pending Phase 3a (trajectory + safety).
