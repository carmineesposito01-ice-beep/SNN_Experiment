# SynOps / Energy Dock — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A live "SynOps" dock — static (fc) + dynamic (spike-driven) synaptic ops per tick, with a dense-MAC reference — faithful to the FPGA scorecard (message: AC<MAC, not sparsity).

**Architecture:** Pure metrics in `sim/ui/metrics.py`; `SynOpsPanel` in `panels.py`; rank exposed via an additive `read_weights["rank"]` (from `rec_V.shape[0]`, NOT `np.linalg.matrix_rank` — SVD triggers OMP Error #15 in `cf_sim`). Behavioral core frozen.

**Tech Stack:** PySide6 6.11, pyqtgraph 0.14, numpy, pytest. Env `cf_sim`.

**Test invocation:** `conda run -n cf_sim python -m pytest <file> -v` (list files explicitly). Real-window renders via a scratchpad script.

---

## Task 1: `metrics` — synops / dense_mac

**Files:** Modify `sim/ui/metrics.py`; Test `tests/test_sim_trajectory.py` (metrics live here already) — or a new block; use `tests/test_sim_metrics*`? Metrics tests currently sit in `tests/test_sim_trajectory.py`. Append there.

- [ ] **Step 1: Failing test** — append to `tests/test_sim_trajectory.py`:

```python
# --- SynOps / energy metrics ---
def test_synops_static_dynamic():
    row = np.zeros(32); row[[0, 1, 2]] = 1
    static, dynamic = metrics.synops(row, 4, 32, 5, 8)
    assert static == 128                                  # IN*H
    assert dynamic == 3 * 8 + 32 * 8 + 3 * 5              # rec_V + rec_U + out = 24+256+15 = 295


def test_synops_zero_firing_no_dynamic():
    static, dynamic = metrics.synops(np.zeros(32), 4, 32, 5, 8)
    assert static == 128 and dynamic == 0                # no spike -> rec_U gate off too


def test_dense_mac_is_param_count():
    assert metrics.dense_mac(4, 32, 5, 8) == 128 + 512 + 160     # 800


def test_synops_series_matches_scalar():
    sm = np.array([[0, 0, 0], [1, 0, 1]])                # H=3
    st, dy = metrics.synops_series(sm, 2, 3, 1, 2)
    assert list(st) == [6, 6]                            # IN*H = 2*3
    assert dy[0] == 0
    assert dy[1] == 2 * 2 + 3 * 2 + 2 * 1                # s=2: rec_V 4 + rec_U 6 + out 2 = 12
```

(`metrics` is already imported in `test_sim_trajectory.py`; if not, add `from sim.ui import metrics`.)

- [ ] **Step 2: Run → fail** — `conda run -n cf_sim python -m pytest tests/test_sim_trajectory.py -k synops -v` → AttributeError.

- [ ] **Step 3: Implement** — append to `sim/ui/metrics.py`:

```python
def synops(spikes_row, n_in, n_hid, n_out, rank):
    """(static, dynamic) SynOps for one tick. static = fc input (always-on);
    dynamic = spike-driven rec_V (s*rank) + rec_U (H*rank if any spike) + out (s*OUT)."""
    s = int(np.count_nonzero(np.asarray(spikes_row) > 0))
    static = int(n_in * n_hid)
    dynamic = int(s * rank + (n_hid * rank if s else 0) + s * n_out)
    return static, dynamic


def synops_series(spikes_matrix, n_in, n_hid, n_out, rank):
    """Vectorised over frames -> (static[], dynamic[])."""
    sm = np.asarray(spikes_matrix)
    if sm.size == 0:
        return np.empty(0), np.empty(0)
    s = np.count_nonzero(sm > 0, axis=1).astype(float)
    static = np.full(s.shape, float(n_in * n_hid))
    dynamic = s * rank + np.where(s > 0, float(n_hid * rank), 0.0) + s * n_out
    return static, dynamic


def dense_mac(n_in, n_hid, n_out, rank):
    """Clock-driven dense-MAC equivalent per tick (every synapse every tick = param count)."""
    return int(n_in * n_hid + 2 * rank * n_hid + n_hid * n_out)
```

- [ ] **Step 4: Run → pass**. `-k synops` → 4 passed.
- [ ] **Step 5: Commit** — `git add sim/ui/metrics.py tests/test_sim_trajectory.py && git commit -m "feat(sim/ui): metrics.synops/dense_mac — static/dynamic SynOps model"`

---

## Task 2: `read_weights["rank"]` + `SynOpsPanel`

**Files:** Modify `sim/backend.py`, `sim/eventprop_stepper.py`, `sim/ui/panels.py`; Test `tests/test_sim_backend.py`, `tests/test_sim_panels.py`.

- [ ] **Step 1: Failing tests**

Append to `tests/test_sim_backend.py` (find how it builds a backend/champion; mirror existing tests — it already loads `CHAMP`/`load_champion`):

```python
def test_read_weights_exposes_rank(qapp_or_none=None):
    import os
    from utils.champion_io import load_champion
    from sim.backend import SoftwareBackend
    REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    champ = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")
    b = SoftwareBackend(load_champion(champ).model); b.reset()
    w = b.read_weights()
    assert w["rank"] == 8                                 # rec_V (8,32) -> rank 8
    assert w["w_in"].shape == (32, 4) and w["w_out"].shape == (5, 32)
```

(Match the import style already used in `tests/test_sim_backend.py`; it already imports these — adapt the boilerplate to the file's existing fixtures.)

Append to `tests/test_sim_panels.py`:

```python
# --- Phase 3 close: SynOps / energy dock ---
from sim.ui.panels import SynOpsPanel   # noqa: E402


def test_synops_panel_ref_and_total(qapp):
    panel = SynOpsPanel()
    panel.set_model(4, 32, 5, 8)
    assert abs(panel._ref.value() - 800) < 1e-6
    p = AttributeProbe(capacity=10)
    for t in range(3):
        spk = np.zeros(32); spk[:5] = 1                  # 5 firing
        p.record(t, {"spikes": spk, "v_mem": np.zeros(32), "v_th_eff": np.ones(32)}, np.zeros(5))
    panel.update_frame(p)
    y = panel._total_c.getData()[1]
    assert float(y[-1]) == 128 + (5 * 8 + 32 * 8 + 5 * 5)      # 128 + 321 = 449


def test_synops_panel_cursor(qapp):
    panel = SynOpsPanel()
    panel.set_cursor(6)
    assert panel._cursors[0].isVisible() and abs(panel._cursors[0].value() - 6.0) < 1e-6
```

- [ ] **Step 2: Run → fail** — `-k "rank or synops_panel"`.

- [ ] **Step 3: Implement**

3a. `sim/backend.py` — add `"rank"` to the baseline `read_weights` dict:

```python
        return {
            "w_in": lh.fc_weight.detach().cpu().numpy(),
            "w_rec": (lh.rec_U @ lh.rec_V).detach().cpu().numpy(),
            "w_out": self.model.layer_out.fc_weight.detach().cpu().numpy(),
            "rank": int(lh.rec_V.shape[0]),
        }
```

3b. `sim/eventprop_stepper.py` — add `"rank"` to `read_weights`:

```python
        return {
            "w_in": w_in.detach().cpu().numpy(),
            "w_rec": self._rec_full.detach().cpu().numpy(),
            "w_out": self._w_out.detach().cpu().numpy(),
            "rank": int(self.model.layer_hidden.rec_V.shape[0]),
        }
```

3c. `sim/ui/panels.py` — add `SynOpsPanel` (after `SpikeRatePanel`; `metrics`, `Qt`, `_add_cursor` already imported):

```python
class SynOpsPanel(QWidget):
    """Per-tick synaptic ops: static (fc, always-on) + dynamic (spike-driven), vs the dense-MAC
    equivalent (parameter count). SynOps ≈ MACs (not sparse) — the win is AC<MAC, not sparsity."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="SynOps / tick (AC)")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", "SynOps")
        self._plot.setDownsampling(auto=True, mode="peak")
        self._plot.setClipToView(True)
        self._static_c = self._plot.plot(pen=pg.mkPen("#1d9e75", width=1),
                                         fillLevel=0, brush=pg.mkBrush(29, 158, 117, 110))
        self._total_c = self._plot.plot(pen=pg.mkPen("#ffffff", width=1.5))
        self._fill_dyn = pg.FillBetweenItem(self._total_c, self._static_c,
                                            brush=pg.mkBrush(239, 159, 39, 100))
        self._plot.addItem(self._fill_dyn)
        self._ref = pg.InfiniteLine(angle=0, movable=False,
                                    pen=pg.mkPen("#9a9a9a", width=1.2, style=Qt.DashLine))
        self._ref.setVisible(False)
        self._plot.addItem(self._ref)
        self._cursors = [_add_cursor(self._plot.getPlotItem())]
        self._dims = None
        self._dense = None

    def set_cursor(self, x):
        _set_cursor(self._cursors, x)

    def set_model(self, n_in, n_hid, n_out, rank):
        self._dims = (int(n_in), int(n_hid), int(n_out), int(rank))
        self._dense = metrics.dense_mac(*self._dims)
        self._ref.setPos(self._dense)
        self._ref.setVisible(True)
        self._plot.setYRange(0, self._dense * 1.05)

    def update_frame(self, probe):
        if self._dims is None:
            return
        sm = probe.spikes_matrix()
        if not sm.size:
            return
        static, dynamic = metrics.synops_series(sm, *self._dims)
        total = static + dynamic
        self._static_c.setData(static)
        self._total_c.setData(total)
        cur = float(total[-1])
        pct = 100.0 * cur / self._dense if self._dense else 0.0
        self._plot.setTitle(f"SynOps/tick = {int(cur)} · {pct:.0f}% del dense-MAC ({self._dense})")
```

- [ ] **Step 4: Run → pass**; then golden re-run of the additive-core files:
`conda run -n cf_sim python -m pytest tests/test_sim_backend.py tests/test_sim_eventprop.py tests/test_sim_panels.py -q` → all green (read_weights additive; infer/step untouched).

- [ ] **Step 5: Commit** — `git add sim/backend.py sim/eventprop_stepper.py sim/ui/panels.py tests/ && git commit -m "feat(sim): read_weights['rank'] (additive) + SynOpsPanel"`

---

## Task 3: App + layout wiring (14 docks) + render + docs

**Files:** Modify `sim/ui/layout.py`, `sim/ui/app.py`; Test `tests/test_sim_ui_smoke.py`; docs + memory.

- [ ] **Step 1: Failing integration test** — append to `tests/test_sim_ui_smoke.py`:

```python
def test_simapp_has_synops_dock(qapp):
    win = SimApp(CHAMP)
    assert "SynOps" in win._docks and len(win._docks) == 14
    assert win._synops._dims == (4, 32, 5, 8) and win._synops._dense == 800
    win.select_scenario(0)
    win._advance(0.5)
    y = win._synops._total_c.getData()[1]
    assert y is not None and y.size > 0 and float(y[-1]) >= 128     # >= static floor
```

- [ ] **Step 2: Run → fail** — `KeyError: 'SynOps'`.

- [ ] **Step 3a: `sim/ui/layout.py`** — `DOCK_ORDER` append `"SynOps"` (14 total); in `apply_overview` append `_show(area, docks, "SynOps", "bottom", "SpikeRate")`; in `apply_guida` add `"SynOps"` to the hide tuple; in `apply_identificazione` add `"SynOps"` to the hide tuple; in `apply_neuro_debug` add `_show(area, docks, "SynOps", "bottom", "SpikeRate")` after SpikeRate is shown.

- [ ] **Step 3b: `sim/ui/app.py`** — import `SynOpsPanel`; build `self._synops = SynOpsPanel()` (near the other panels); after the topology block add
  `self._synops.set_model(_w["w_in"].shape[1], _w["w_in"].shape[0], _w["w_out"].shape[0], _w["rank"])`;
  append `self._synops` to `_ts_panels`; add `"SynOps": self._synops` to `widgets`; add `self._synops.update_frame(probe)` to `_redraw_series`.

- [ ] **Step 4: Run → pass** — `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py tests/test_sim_layout.py -q`.

- [ ] **Step 5: Full golden suite** — the 15-file list + `test_sim_reconstruct.py` (from the 3b-rest plan) all green; core bit-identical.

- [ ] **Step 6: Render-verify** — scratchpad script: run scenario, advance, apply "Neuro-debug", grab; PNG to user (keep file, `display="render"`).

- [ ] **Step 7: Docs + memory** — study §6 (energy/SynOps backlog → DONE, Phase 3 closed); this plan Status banner; memory `cf-fsnn-parallel-tracks.md` (SynOps dock + the `matrix_rank`→OMP#15 gotcha). Commit + push.

- [ ] **Step 8: Commit** — `git add ... && git commit -m "feat(sim/ui): SynOps energy dock wired (14 docks) — close Phase 3"`

---

## Self-review

- **Coverage:** metrics (T1) · rank source + panel (T2) · wiring + render + docs (T3). Rank via `rec_V.shape` (not SVD) — the OMP#15 finding is captured in spec + memory.
- **Types:** `synops`/`synops_series`/`dense_mac(n_in,n_hid,n_out,rank)` used identically in tests/panel/app; `set_model` args order matches `read_weights` outputs (`w_in.shape[1]=IN`, `w_in.shape[0]=H`, `w_out.shape[0]=OUT`, `rank`).
- **Core:** only additive `read_weights["rank"]`; golden re-run gates it.
