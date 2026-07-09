# Meso/Macro Analysis Mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** A Live ↔ Meso/Macro mode toggle; the analysis page runs platoon (string stability, space-time) + ring (fundamental diagram, per-vehicle params) sims on-demand for all 4 champions, reusing `utils/platoon_eval.py`.

**Architecture:** `QStackedWidget` mode toggle in `SimApp`; a family-aware **batched forward** (`sim/ui/platoon.py`) injected into `platoon_eval` via an additive `forward=` hook (reports unaffected); 4 pyqtgraph analysis panels in `sim/ui/meso_panels.py`; a `MesoMacroPage` hosting controls + panels.

**Tech Stack:** PySide6 6.11, pyqtgraph 0.14, numpy, torch. Env `cf_sim`. Core frozen.

**Tests:** `conda run -n cf_sim python -m pytest <files> -v` (list explicitly). Renders via scratchpad scripts.

---

## Task 1: Mode toggle + `MesoMacroPage` scaffold

**Files:** Create `sim/ui/meso_page.py`; Modify `sim/ui/app.py`; Test `tests/test_sim_ui_smoke.py`.

- [ ] **Step 1 — failing test** (append `tests/test_sim_ui_smoke.py`):

```python
def test_simapp_mode_toggle(qapp):
    win = SimApp(CHAMP)
    assert win._mode_stack.count() == 2                 # Live + Meso/Macro
    assert win._mode_stack.currentIndex() == 0          # starts Live
    win._run_btn.setChecked(True)                        # start live
    win.set_mode(1)                                       # switch to analysis
    assert win._mode_stack.currentIndex() == 1
    assert not win._run_btn.isChecked()                  # switching to analysis pauses live
    win.set_mode(0)
    assert win._mode_stack.currentIndex() == 0
```

- [ ] **Step 2 — run → fail** (`AttributeError: _mode_stack`).

- [ ] **Step 3 — implement**

`sim/ui/meso_page.py`:
```python
"""MesoMacroPage -- batch platoon/ring analysis view (string stability, space-time, fundamental
diagram, per-vehicle params). Scaffold in T1; panels wired in T3/T4."""
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)
from pyqtgraph import GraphicsLayoutWidget


class MesoMacroPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        self._n_spin = QSpinBox(); self._n_spin.setRange(3, 40); self._n_spin.setValue(12)
        self._run_platoon_btn = QPushButton("Run platoon")
        self._run_ring_btn = QPushButton("Run ring sweep")
        for w in (QLabel("N veicoli"), self._n_spin, self._run_platoon_btn, self._run_ring_btn):
            controls.addWidget(w)
        controls.addStretch(1)
        root.addLayout(controls)
        self._grid = GraphicsLayoutWidget()      # panels added in T3/T4
        root.addWidget(self._grid, stretch=1)
        self._on_run_platoon = None
        self._on_run_ring = None
        self._run_platoon_btn.clicked.connect(lambda: self._on_run_platoon and self._on_run_platoon())
        self._run_ring_btn.clicked.connect(lambda: self._on_run_ring and self._on_run_ring())

    def n_vehicles(self):
        return int(self._n_spin.value())
```

`sim/ui/app.py`: import `QStackedWidget` (from PySide6.QtWidgets) + `MesoMacroPage`. Where the central widget is built (`container = QWidget(); container.setLayout(root); self.setCentralWidget(container)`), replace with:
```python
        container = QWidget(); container.setLayout(root)
        self._meso_page = MesoMacroPage()
        self._meso_page._on_run_platoon = self._run_platoon
        self._meso_page._on_run_ring = self._run_ring
        self._mode_stack = QStackedWidget()
        self._mode_stack.addWidget(container)          # page 0: Live
        self._mode_stack.addWidget(self._meso_page)    # page 1: Meso/Macro
        self._mode_sel = QComboBox(); self._mode_sel.addItems(["Live", "Meso/Macro"])
        self._mode_sel.currentIndexChanged.connect(self.set_mode)
        outer = QVBoxLayout(); outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._mode_sel); outer.addWidget(self._mode_stack, stretch=1)
        shell = QWidget(); shell.setLayout(outer)
        self.setCentralWidget(shell)
```
Add methods (stubs for T3/T4 run hooks + the toggle):
```python
    def set_mode(self, idx):
        idx = int(idx)
        if idx == 1:
            self._run_btn.setChecked(False)            # pause live when entering analysis
        self._mode_stack.setCurrentIndex(idx)
        if self._mode_sel.currentIndex() != idx:
            self._mode_sel.blockSignals(True); self._mode_sel.setCurrentIndex(idx); self._mode_sel.blockSignals(False)

    def _run_platoon(self):
        pass        # wired in T3

    def _run_ring(self):
        pass        # wired in T4
```

- [ ] **Step 4 — run → pass**; also `tests/test_sim_ui_smoke.py` full → green.
- [ ] **Step 5 — commit**: `feat(sim/ui): Live<->Meso/Macro mode toggle + MesoMacroPage scaffold`

---

## Task 2: Family-aware batched forward + `platoon_eval` hook

**Files:** Create `sim/ui/platoon.py`; Modify `utils/platoon_eval.py`; Test `tests/test_sim_platoon.py`.

- [ ] **Step 1 — failing test** (`tests/test_sim_platoon.py`):

```python
import os, sys
import numpy as np
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path: sys.path.insert(0, REPO)
from utils.champion_io import load_champion            # noqa: E402
from sim.ui.platoon import batched_forward, run_platoon  # noqa: E402
import torch                                            # noqa: E402

BASE = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")
EVENT = os.path.join(REPO, "champions", "PE_t05_gp0002", "best_model.pt")
_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


def test_batched_forward_batch_independent_eventprop():
    fw = batched_forward(load_champion(EVENT), 3)
    fw.reset(3)
    gap = np.full(3, 20.0); v = np.full(3, 15.0); dv = np.zeros(3); vl = np.full(3, 15.0)
    out = fw.infer(gap, v, dv, vl).detach().numpy()      # identical obs -> identical rows
    assert out.shape == (3, 5)
    assert np.allclose(out[0], out[1]) and np.allclose(out[1], out[2])


def test_run_platoon_shapes_both_families():
    for path in (BASE, EVENT):
        rec = run_platoon(load_champion(path), _PG, n_vehicles=6,
                          v_leader_profile=np.full(60, 21.0))
        assert rec["v"].shape == (60, 6) and "gap" in rec and "v_leader" in rec
```

- [ ] **Step 2 — run → fail** (`ModuleNotFoundError sim.ui.platoon`).

- [ ] **Step 3 — implement**

`utils/platoon_eval.py`: add an optional `forward=None` to `simulate_platoon` and `simulate_ring`. In each, replace the reset + `_params_for` calls:
- reset: `if forward is not None: forward.reset(n, device)` else the existing `if model is not None: model.reset_state(n, device)`.
- inference: `params = forward.infer(gap, v, dv, vlead) if forward is not None else _params_for(model, gap, v, dv, vlead, pgt_t, n, device)` (use the loop's own `gap,v,dv,vlead`).

`sim/ui/platoon.py`:
```python
"""Family-aware BATCHED forward + platoon/ring runners for the meso/macro analysis mode.
Reuses utils.platoon_eval (validated); the frozen core is only read."""
from core.network import CF_FSNN_Net_EventProp_Full
from sim.eventprop_stepper import EventPropStepper
from utils.platoon_eval import (_norm_obs_batch, simulate_platoon, platoon_metrics,
                                simulate_ring, fundamental_diagram)


class _BatchedForward:
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
            self.model.eval(); self.model.reset_state(n, dev)

    def infer(self, gap, v, dv, vl):
        x = _norm_obs_batch(gap, v, dv, vl).to(self.device)
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
```

(For `fundamental_diagram`, T4 adds a `run_fundamental_diagram` that loops densities calling `run_ring` + the Edie Q/V from `platoon_eval.fundamental_diagram`'s point formula — or extend `fundamental_diagram` with a `forward_factory`.)

- [ ] **Step 4 — run → pass**; golden: `conda run -n cf_sim python -m pytest tests/test_sim_platoon.py tests/test_sim_eventprop.py -q` green (eventprop step untouched).
- [ ] **Step 5 — commit**: `feat(sim/ui): family-aware batched forward + platoon_eval forward hook (all 4 champions)`

---

## Task 3: String-stability + space-time panels + Run platoon

**Files:** Create `sim/ui/meso_panels.py`; Modify `sim/ui/meso_page.py`, `sim/ui/app.py`; Test `tests/test_sim_meso_panels.py`.

- [ ] **Step 1 — failing test**: `StringStabilityPanel().update(metrics)` sets a bar per vehicle == `gain_per_vehicle`; `SpaceTimePanel().update(rec)` creates N curves.
- [ ] **Step 2 — run → fail.**
- [ ] **Step 3 — implement** `StringStabilityPanel` (bar `pg.BarGraphItem` of `gain_per_vehicle` + a `y=1` `InfiniteLine` + a verdict `QLabel`) and `SpaceTimePanel` (N `plot` curves `x[:, i]` vs time, coloured by mean speed via viridis LUT). Add both to `MesoMacroPage._grid`. `SimApp._run_platoon`: `rec = run_platoon(self._champ, _PARAMS_GT, self._meso_page.n_vehicles(), <perturbed head profile>); m = platoon_metrics(rec)`; feed the panels.
- [ ] **Step 4 — run → pass.**
- [ ] **Step 5 — commit**: `feat(sim/ui): string-stability + space-time panels (Run platoon)`

---

## Task 4: Fundamental-diagram + per-vehicle params + Run ring sweep

**Files:** Modify `sim/ui/meso_panels.py`, `sim/ui/platoon.py`, `sim/ui/meso_page.py`, `sim/ui/app.py`; Test `tests/test_sim_meso_panels.py`.

- [ ] **Step 1 — failing test**: `FundamentalDiagramPanel().update(points)` plots Q(ρ)/V(ρ); `PlatoonParamsPanel().update(rec_params)` shows 5×N.
- [ ] **Step 2 — run → fail.**
- [ ] **Step 3 — implement** `run_fundamental_diagram(champion, params_gt, densities, ...)` (family-aware, via `run_ring` per density + the Edie formula from `platoon_eval.fundamental_diagram`), `FundamentalDiagramPanel` (Q vs ρ + V vs ρ, unstable points marked), `PlatoonParamsPanel` (mean of the 5 params per vehicle over the regime — needs the platoon `rec` to also record params; extend `simulate_platoon`'s rec with `params` (T,N,5) additively). Wire `SimApp._run_ring`.
- [ ] **Step 4 — run → pass.**
- [ ] **Step 5 — commit**: `feat(sim/ui): fundamental-diagram + per-vehicle params (Run ring sweep)`

---

## Task 5: Render-verify + golden + docs

- [ ] Golden suite (full sim list) green; single-vehicle bit-identical.
- [ ] Render the analysis page for Raffaello (BPTT) + Donatello (EventProp); PNG to user.
- [ ] Docs (study §6, this plan banner) + memory. Commit + push.

---

## Self-review

- **Coverage:** mode toggle (T1) · batched forward + hook (T2) · meso panels (T3) · macro panels (T4) · verify (T5). All spec sections mapped.
- **Types:** `batched_forward(champion,n)`/`run_platoon(champion,params_gt,n,profile)` used identically in tests + app; `platoon_eval` `forward=` hook additive (default path preserved). `MesoMacroPage.n_vehicles()`/`set_mode(idx)` consistent.
- **Core:** frozen; `platoon_eval` gains only an optional param; batched forward reuses `EventPropStepper.step`.
