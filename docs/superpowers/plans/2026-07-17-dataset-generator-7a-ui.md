# Dataset generator 7a — Plan B: the 5th mode (the UI)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Put a 5th **"Dataset"** mode on top of the engine Plan A landed — a mix table over three families
with a hover preview, seed/count/jitter, decimation, format checkboxes read from the registry, a live size
estimate, and Generate with progress.

**Architecture:** One new Qt page (`sim/ui/dataset_page.py`) that owns the widgets and exposes getters; the
app owns the run and reuses the **existing** `_busy`/`processEvents` batch idiom. The enabling change comes
first: the built-scenario **specs must be retained** (today the signal throws them away), otherwise the
`built` family has nothing to jitter.

**Tech Stack:** PySide6, pyqtgraph. Env: conda `cf_sim`.

**Runner (NEVER `conda run`):**
```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest <args> -p no:cacheprovider
```
**Suite = the sim glob only:** `tests/test_sim_*.py tests/test_champion_io.py` — never `pytest tests/`
(`tests/test_fpga_io.py` `sys.exit()`s at import and aborts collection). ~3 min → **≥420 s or background**.
Render-verify with `QT_QPA_PLATFORM=windows`. Commits conventional, **no `Co-Authored-By`**.

**Baseline:** 325 green (verify it in Task 1 Step 0 — do not trust this number).

**Invariants:** frozen core, `utils/closed_loop_eval.py`, `materialise`, and **`data/generator.py`** untouched.

**Test rules:** compute expected values from the real code; each task ends by **sabotaging the fix** and
watching the guard fail, then revert; use **Edit**; check GREEN **before** committing, as a separate action
(never chain `pytest | tail && git commit` — the pipe masks pytest's exit code).

**The engine is already built — these are its REAL APIs (do not invent):**
- `sim/dataset_mix.py`: `MixEntry(family, source, weight)` · `FAMILIES=("built","preset","generator")` ·
  `validate_mix(mix)` · `quotas(mix, count) -> list[int]`
- `sim/export_formats.py`: `FORMATS = {name: FormatSpec(writer, bytes_per_tick, available, reason)}` ·
  `available_formats()` · `estimate_bytes(ticks_per_traj, formats) -> float`
- `sim/dataset_gen.py`: `GENERATOR_PROFILES` · `draw_scenario(...)` ·
  `preview_sample(family, source, seed, strength, specs, params_gt) -> v_leader` · `decimate(kin, k, dt)` ·
  `generate_dataset(mix, count, seed, strength, k, formats, out_dir, specs, params_gt, on_progress=None) -> manifest`

**Grounded facts (verified 2026-07-17 — follow these patterns, don't invent):**
- `app.py:185-195`: `_mode_stack` pages are 0=Live container · 1=`_meso_page` · 2=`_postrun_page` ·
  3=`_scenario_page`; `_mode_sel.addItems(["Live","Meso/Macro","Post-run","Scenari"])`. **Dataset = page 4.**
- `app.py:369-383` `set_mode(idx)` already has per-mode hooks (`idx==2` refreshes the post-run). **`idx==4`
  refreshes the Dataset sources** — the built specs may have changed since.
- `app.py:174` `self._meso_page._on_run_platoon = self._run_platoon` — **the page exposes the button, the APP
  owns the run.** The Dataset page does the same via `_on_generate`.
- `app.py:385-408` — the batch idiom: `_busy(msg)` disables every re-entry control (`_busy_controls()`) + wait
  cursor + `repaint()`; the run is **synchronous on the GUI thread**; a progress callback calls
  `QApplication.processEvents()` — safe **precisely because** re-entry is disabled; `finally: _done_busy()`.
  **Reuse it.** Do not add a QThread.
- `app.py:198` `self._status = self.statusBar()`.
- The smoke tests drive a non-Live page with `win.set_mode(3)` (`test_sim_ui_smoke.py:664`).
- **The signal churn is 9 sites** (enumerated, Task 1).

---

### Task 1: spec retention — the signal carries the recipe

Without the `ScenarioSpec` there are no blocks to jitter, so the `built` family cannot exist. This is the
enabling change and it comes first.

**Files:**
- Modify: `sim/ui/scenario_page.py:103` (declaration), `:527` (emit)
- Modify: `sim/ui/app.py:184` (connect), `:642` (slot signature), `:70-72` (`_specs` init), `_delete_scenario`
- Test: `tests/test_sim_app_lifecycle.py` (new test + the `:29` churn), and the churn in
  `tests/test_sim_ui_smoke.py:653,1041` + `tests/test_sim_scenario_page_name.py:35,44`

- [ ] **Step 0: Verify the baseline**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -q -p no:cacheprovider
```
Expected: `B passed` (record the real B; ~325).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sim_app_lifecycle.py`:
```python
def test_the_app_retains_the_spec_of_a_built_scenario(qapp):
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    win = SimApp(CHAMP)
    protected = win._protected_count
    assert len(win._specs) == len(win._scenarios)            # parallel from the start
    assert all(s is None for s in win._specs[:protected])    # library + initial manual have no recipe
    spec = ScenarioSpec(name="mine", blocks=(Block("const", 120, {"v": 15.0}),),
                        style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)
    win._scenario_page.set_spec(spec)
    win._scenario_page._name_edit.setText("mine")
    win._scenario_page._on_use()                             # the real path: build -> emit -> append
    assert len(win._specs) == len(win._scenarios)
    assert win._specs[-1] is not None and win._specs[-1].blocks[0].kind == "const"


def test_delete_keeps_specs_aligned_with_scenarios(qapp):
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    win = SimApp(CHAMP)
    spec = ScenarioSpec(name="mine", blocks=(Block("const", 120, {"v": 15.0}),),
                        style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)
    win._scenario_page.set_spec(spec)
    win._scenario_page._on_use()
    n = len(win._scenarios)
    win._delete_scenario()                                   # the built one is selected
    assert len(win._specs) == len(win._scenarios) == n - 1   # both popped -> still aligned
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_app_lifecycle.py -q -p no:cacheprovider
```
Expected: FAIL — `AttributeError: 'SimApp' object has no attribute '_specs'`.

- [ ] **Step 3: Change the signal (source, 4 sites)**

`sim/ui/scenario_page.py:103`:
```python
    sigScenarioBuilt = Signal(object, object)   # emits (sim.scenario.Scenario, its ScenarioSpec)
```
`sim/ui/scenario_page.py:527` — emit the recipe alongside the artifact:
```python
        self.sigScenarioBuilt.emit(materialise(spec, self._params_gt, self._total_ticks()), spec)
```
`sim/ui/app.py:70-72` — the parallel list, created with the initial scenarios:
```python
        self._scenarios.append(self._manual(_PARAMS_GT))
        self._protected_count = len(self._scenarios)   # library presets + initial manual: Meso indexes these
        self._specs = [None] * len(self._scenarios)    # parallel to _scenarios: the built ones' recipes
        self._current_idx = 0
```
`sim/ui/app.py:642` — the slot takes the recipe:
```python
    def _on_scenario_built(self, scenario, spec=None):
```
and inside it, right where it appends the scenario, append the spec too (keep the two lists in lockstep):
```python
        self._scenarios.append(scenario)
        self._specs.append(spec)
```
`sim/ui/app.py` `_delete_scenario` — pop both:
```python
        self._scenarios.pop(idx)
        self._specs.pop(idx)
```
(`app.py:184`, the `connect`, needs no edit — Qt passes both args to the 2-param slot.)

- [ ] **Step 4: Fix the 5 test churn sites**

`tests/test_sim_ui_smoke.py:653` and `:1041` — the slot now receives 2 args:
```python
    page.sigScenarioBuilt.connect(lambda sc, sp: got.append(sc))
```
`tests/test_sim_scenario_page_name.py:35` and `:44`:
```python
    page.sigScenarioBuilt.connect(lambda sc, sp: got.append(sc))
```
`tests/test_sim_app_lifecycle.py:29` — the direct call needs the second arg (a synthetic append has no recipe):
```python
    win._on_scenario_built(manual_scenario(sc.params_gt, sc.v_leader, sc.s_init, sc.v_init, name=name), None)
```

- [ ] **Step 5: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_app_lifecycle.py tests/test_sim_scenario_page_name.py -q -p no:cacheprovider
```
Expected: all pass (5 lifecycle + 2 name).

- [ ] **Step 6: Sabotage, watch the guard fail, revert**

In `_delete_scenario`, delete the `self._specs.pop(idx)` line. Re-run
`tests/test_sim_app_lifecycle.py::test_delete_keeps_specs_aligned_with_scenarios`: expected FAIL (the lists
drift: `len(_specs) == n` but `len(_scenarios) == n-1`). This proves the test pins the alignment that every
`_specs[i]` lookup depends on. **Revert**; re-run → pass.

- [ ] **Step 7: Commit**

```bash
git add sim/ui/scenario_page.py sim/ui/app.py tests/test_sim_app_lifecycle.py tests/test_sim_scenario_page_name.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): the built-scenario signal carries its spec; the app retains it"
```

---

### Task 2: `sim/ui/dataset_page.py` — the mix table

**Files:**
- Create: `sim/ui/dataset_page.py`
- Test: `tests/test_sim_dataset_page.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sim_dataset_page.py`:
```python
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec   # noqa: E402
from sim.ui.dataset_page import DatasetPage                      # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _specs():
    return {"mine": ScenarioSpec(name="mine", blocks=(Block("const", 120, {"v": 15.0}),),
                                 style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)}


def _page(qapp, specs=None):
    p = DatasetPage(params_gt=_PG)
    p.set_sources(specs if specs is not None else _specs(), ["following", "hard_brake"])
    return p


def test_a_fresh_page_has_one_row_and_the_families(qapp):
    from sim.dataset_mix import FAMILIES
    p = _page(qapp)
    assert len(p._rows) == 1
    assert [p._rows[0].family.itemText(i) for i in range(p._rows[0].family.count())] == list(FAMILIES)


def test_the_source_combo_cascades_from_the_family(qapp):
    from sim.dataset_gen import GENERATOR_PROFILES
    p = _page(qapp)
    r = p._rows[0]
    r.family.setCurrentText("preset")
    assert [r.source.itemText(i) for i in range(r.source.count())] == ["following", "hard_brake"]
    r.family.setCurrentText("generator")
    assert [r.source.itemText(i) for i in range(r.source.count())] == list(GENERATOR_PROFILES)
    r.family.setCurrentText("built")
    assert [r.source.itemText(i) for i in range(r.source.count())] == ["mine"]


def test_the_built_family_is_disabled_when_no_scenario_was_built(qapp):
    p = _page(qapp, specs={})
    model = p._rows[0].family.model()
    assert not model.item(0).isEnabled()          # "built" is FAMILIES[0]
    assert "Scenari" in model.item(0).toolTip()   # says where to go build one


def test_the_quota_column_is_live_and_exact(qapp):
    p = _page(qapp)
    p._count.setValue(100)
    p._rows[0].weight.setValue(100.0)
    assert p._rows[0].quota.text() == "100"
    p.add_row(); p._rows[0].weight.setValue(40.0); p._rows[1].weight.setValue(60.0)
    assert [r.quota.text() for r in p._rows] == ["40", "60"]


def test_generate_is_gated_on_a_total_of_100(qapp):
    p = _page(qapp)
    p._rows[0].weight.setValue(40.0)
    assert not p._gen_btn.isEnabled() and "✗" in p._total_lbl.text()
    p._rows[0].weight.setValue(100.0)
    assert p._gen_btn.isEnabled() and "✓" in p._total_lbl.text()


def test_mix_returns_the_engines_MixEntry(qapp):
    from sim.dataset_mix import MixEntry, validate_mix
    p = _page(qapp)
    p._rows[0].family.setCurrentText("preset")
    p._rows[0].source.setCurrentText("hard_brake")
    p._rows[0].weight.setValue(100.0)
    mix = p.mix()
    assert mix == [MixEntry("preset", "hard_brake", 100.0)]
    validate_mix(mix)                              # the engine accepts what the page produces


def test_removing_a_row_keeps_the_page_consistent(qapp):
    p = _page(qapp)
    p.add_row()
    assert len(p._rows) == 2
    p.remove_row(p._rows[1])
    assert len(p._rows) == 1
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_dataset_page.py -q -p no:cacheprovider
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.ui.dataset_page'`.

- [ ] **Step 3: Implement the page + the mix table**

Create `sim/ui/dataset_page.py`:
```python
"""The Dataset mode (the 5th): a percentage mix over three scenario families -> N randomised trajectories.

The table is a list of ROW WIDGETS, not a QTableWidget with delegates: with a handful of rows it is simpler
and, more importantly, testable without simulating cell editing. Each row owns its own combos/spins; the page
owns the rows.

The page owns WIDGETS and exposes getters (mix/count/seed/strength/k/formats/out_dir); the APP owns the run --
the same split the Meso page uses (app.py:174 sets _on_run_platoon). That is why Generate here only calls
self._on_generate: the batch, the busy-guard and the progress pump live in the app, where _busy_controls can
disable every re-entry path."""
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from sim.dataset_gen import GENERATOR_PROFILES
from sim.dataset_mix import FAMILIES, MixEntry, quotas
from sim.export_formats import FORMATS

_K_CHOICES = [("10 Hz (nativa)", 1), ("5 Hz", 2), ("2 Hz", 5), ("1 Hz", 10)]


@dataclass
class _Row:
    frame: QFrame
    family: QComboBox
    source: QComboBox
    eye: QLabel
    weight: QDoubleSpinBox
    quota: QLabel
    kill: QPushButton


class DatasetPage(QWidget):
    def __init__(self, params_gt):
        super().__init__()
        self._params_gt = params_gt
        self._specs = {}
        self._preset_names = []
        self._rows = []
        self._on_generate = None            # the APP sets this (see the Meso idiom, app.py:174)

        self._rows_box = QVBoxLayout()
        self._add_btn = QPushButton("+ riga"); self._add_btn.clicked.connect(self.add_row)
        self._total_lbl = QLabel()
        self._count = QSpinBox(); self._count.setRange(1, 100000); self._count.setValue(100)
        self._seed = QSpinBox(); self._seed.setRange(0, 2**31 - 1); self._seed.setValue(42)
        self._gen_btn = QPushButton("Genera")
        self._gen_btn.clicked.connect(lambda: self._on_generate() if self._on_generate else None)
        self._progress = QProgressBar(); self._progress.setRange(0, 100); self._progress.setValue(0)

        head = QHBoxLayout()
        for t in ("famiglia", "sorgente", "", "peso %", "→ traiettorie", ""):
            lbl = QLabel(t); lbl.setStyleSheet("color:#8b949e"); head.addWidget(lbl)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("MIX"))
        root.addLayout(head)
        root.addLayout(self._rows_box)
        bottom = QHBoxLayout(); bottom.addWidget(self._add_btn); bottom.addWidget(self._total_lbl)
        bottom.addStretch(1)
        root.addLayout(bottom)
        root.addStretch(1)
        self.add_row()

    # ---- sources ----
    def set_sources(self, specs, preset_names):
        """Called by the app when entering the mode: the built scenarios may have changed."""
        self._specs = dict(specs)
        self._preset_names = list(preset_names)
        for r in self._rows:
            self._sync_family_enabled(r)
            self._reload_sources(r)
        self._refresh()

    def _sync_family_enabled(self, row):
        model = row.family.model()
        item = model.item(FAMILIES.index("built"))
        if self._specs:
            item.setEnabled(True); item.setToolTip("")
        else:
            item.setEnabled(False)
            item.setToolTip("nessuno scenario costruito: costruiscine uno nel modo Scenari")
            if row.family.currentText() == "built":
                row.family.setCurrentText("preset")

    def _sources_for(self, family):
        if family == "built":
            return sorted(self._specs)
        if family == "preset":
            return list(self._preset_names)
        return list(GENERATOR_PROFILES)

    def _reload_sources(self, row):
        row.source.blockSignals(True)
        row.source.clear()
        row.source.addItems(self._sources_for(row.family.currentText()))
        row.source.blockSignals(False)

    # ---- rows ----
    def add_row(self):
        frame = QFrame()
        lay = QHBoxLayout(frame); lay.setContentsMargins(0, 0, 0, 0)
        family = QComboBox(); family.addItems(FAMILIES)
        source = QComboBox()
        eye = QLabel("👁"); eye.setToolTip("anteprima di un campione di questa sorgente")
        weight = QDoubleSpinBox(); weight.setRange(0.0, 100.0); weight.setDecimals(1)
        quota = QLabel("0")
        kill = QPushButton("✕"); kill.setFixedWidth(28)
        for w in (family, source, eye, weight, quota, kill):
            lay.addWidget(w)
        row = _Row(frame, family, source, eye, weight, quota, kill)
        self._rows.append(row)
        self._rows_box.addWidget(frame)
        family.currentTextChanged.connect(lambda _t, r=row: (self._reload_sources(r), self._refresh()))
        weight.valueChanged.connect(self._refresh)
        kill.clicked.connect(lambda _c=False, r=row: self.remove_row(r))
        self._sync_family_enabled(row)
        self._reload_sources(row)
        self._refresh()
        return row

    def remove_row(self, row):
        if len(self._rows) <= 1:
            return                                   # always keep one row: an empty mix is not a state
        self._rows.remove(row)
        row.frame.setParent(None)
        self._refresh()

    # ---- getters (the app reads these; the Meso idiom) ----
    def mix(self):
        return [MixEntry(r.family.currentText(), r.source.currentText(), float(r.weight.value()))
                for r in self._rows]

    def count(self):
        return int(self._count.value())

    def seed(self):
        return int(self._seed.value())

    # ---- refresh ----
    def _refresh(self):
        total = sum(r.weight.value() for r in self._rows)
        ok = abs(total - 100.0) <= 0.01 and all(r.source.count() for r in self._rows)
        self._total_lbl.setText(f"totale {total:.0f}% {'✓' if ok else '✗'}")
        self._total_lbl.setStyleSheet(f"color:{'#2e8b57' if ok else '#d1495b'}")
        self._gen_btn.setEnabled(ok)
        if ok:
            for r, q in zip(self._rows, quotas(self.mix(), self.count())):
                r.quota.setText(str(q))
        else:
            for r in self._rows:
                r.quota.setText("—")
```

> `_count.valueChanged` must also refresh the quotas — wire it in `__init__` right after `self._count` is
> created: `self._count.valueChanged.connect(self._refresh)`.

- [ ] **Step 4: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_dataset_page.py -q -p no:cacheprovider
```
Expected: `7 passed`.

- [ ] **Step 5: Sabotage, watch the guard fail, revert**

In `_refresh`, replace `ok = abs(total - 100.0) <= 0.01 and ...` with `ok = True`. Re-run: expected FAIL on
`test_generate_is_gated_on_a_total_of_100` (Generate is enabled at 40%). This proves the test pins the gate.
**Revert**; re-run → `7 passed`.

- [ ] **Step 6: Commit**

```bash
git add sim/ui/dataset_page.py tests/test_sim_dataset_page.py
git commit -m "feat(sim): the Dataset page's mix table (row widgets, live exact quotas, 100% gate)"
```

---

### Task 3: the controls — jitter, frequency + "?", formats from the registry, size estimate

**Files:**
- Modify: `sim/ui/dataset_page.py`
- Test: `tests/test_sim_dataset_page.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sim_dataset_page.py`:
```python
def test_the_format_checkboxes_come_from_the_registry(qapp):
    from sim.export_formats import FORMATS
    p = _page(qapp)
    assert set(p._fmt_boxes) == set(FORMATS)                       # all six are shown
    assert not p._fmt_boxes["parquet"].isEnabled()                 # unavailable -> disabled
    assert "pyarrow" in p._fmt_boxes["parquet"].toolTip()          # ...and it says why
    assert p._fmt_boxes["csv"].isEnabled()


def test_formats_returns_only_the_checked_available_ones(qapp):
    p = _page(qapp)
    for b in p._fmt_boxes.values():
        b.setChecked(False)
    p._fmt_boxes["csv"].setChecked(True)
    p._fmt_boxes["mat"].setChecked(True)
    assert sorted(p.formats()) == ["csv", "mat"]


def test_the_frequency_combo_maps_to_k_and_explains_itself(qapp):
    p = _page(qapp)
    assert p.k() == 1                                   # 10 Hz native by default
    p._freq.setCurrentIndex(1)
    assert p.k() == 2                                   # 5 Hz
    assert "V2V" in p._freq_help.toolTip()              # the "?" says 10 Hz is the canonical V2V rate


def test_the_jitter_slider_states_its_own_limit(qapp):
    p = _page(qapp)
    assert 0.0 <= p.strength() <= 1.0
    assert "generator" in p._jitter_note.text()         # the caveat is inline, not buried in a doc


def test_the_size_estimate_matches_the_engines_formula(qapp):
    from sim.export_formats import estimate_bytes
    p = _page(qapp)
    p._count.setValue(10)
    p._rows[0].family.setCurrentText("preset")
    p._rows[0].source.setCurrentText("hard_brake")
    p._rows[0].weight.setValue(100.0)
    for b in p._fmt_boxes.values():
        b.setChecked(False)
    p._fmt_boxes["csv"].setChecked(True)
    p._freq.setCurrentIndex(1)                          # k=2 -> 600/2 = 300 ticks each
    expected = estimate_bytes([300] * 10, ["csv"])      # computed from the engine, not from memory
    assert abs(p.estimated_bytes() - expected) < 1.0
    assert "MB" in p._size_lbl.text()
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_dataset_page.py -q -p no:cacheprovider
```
Expected: FAIL — `AttributeError: 'DatasetPage' object has no attribute '_fmt_boxes'`.

- [ ] **Step 3: Implement the controls**

In `sim/ui/dataset_page.py`, add these imports if missing (`QSlider`): the import line becomes
```python
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QProgressBar, QPushButton, QSlider, QSpinBox,
                               QVBoxLayout, QWidget)
```
and add to `__init__`, before `self.add_row()`:
```python
        self._count.valueChanged.connect(self._refresh)
        self._jitter = QSlider(Qt.Horizontal); self._jitter.setRange(0, 100); self._jitter.setValue(25)
        self._jitter.setFixedWidth(120)
        self._jitter_lbl = QLabel("25%")
        self._jitter.valueChanged.connect(lambda v: (self._jitter_lbl.setText(f"{v}%"), self._refresh()))
        self._jitter_note = QLabel("⚠ non governa la famiglia «generator» (ha il jitter suo)")
        self._jitter_note.setStyleSheet("color:#6e7681")

        self._freq = QComboBox(); self._freq.addItems([t for t, _k in _K_CHOICES])
        self._freq.currentIndexChanged.connect(self._refresh)
        self._freq_help = QLabel("(?)"); self._freq_help.setStyleSheet("color:#6e7681")
        self._freq_help.setToolTip(
            "10 Hz è la frequenza CANONICA V2V (DT=0.1 s): la fisica gira sempre lì.\n"
            "Le altre scelte DECIMANO l'export (un campione ogni k) e ricalcolano a_leader a dt_out.\n"
            "Nessun upsampling: inventerebbe dati che la fisica non ha prodotto.")

        self._fmt_boxes = {}
        fmt_row = QHBoxLayout(); fmt_row.addWidget(QLabel("formato"))
        for name, spec in FORMATS.items():
            b = QCheckBox(name)
            b.setEnabled(spec.available)
            if not spec.available:
                b.setToolTip(spec.reason)
            b.setChecked(name in ("csv", "mat"))
            b.stateChanged.connect(self._refresh)
            self._fmt_boxes[name] = b
            fmt_row.addWidget(b)
        fmt_row.addStretch(1)

        self._size_lbl = QLabel()
        self._out_dir = QLineEdit()
        self._browse = QPushButton("Sfoglia…"); self._browse.clicked.connect(self._pick_dir)
```
and add these rows to `root` (after the mix bottom row, before `root.addStretch(1)`):
```python
        ctl = QHBoxLayout()
        for w in (QLabel("seed"), self._seed, QLabel("traiettorie"), self._count,
                  QLabel("jitter"), self._jitter, self._jitter_lbl, self._jitter_note):
            ctl.addWidget(w)
        ctl.addStretch(1)
        freq = QHBoxLayout()
        for w in (QLabel("frequenza"), self._freq, self._freq_help):
            freq.addWidget(w)
        freq.addStretch(1); freq.addWidget(self._size_lbl)
        out = QHBoxLayout()
        for w in (QLabel("cartella"), self._out_dir, self._browse):
            out.addWidget(w)
        run = QHBoxLayout(); run.addWidget(self._gen_btn); run.addWidget(self._progress)
        for lay in (ctl, fmt_row, freq, out, run):
            root.addLayout(lay)
```
and add the getters + the estimate + the dir picker:
```python
    def strength(self):
        return self._jitter.value() / 100.0

    def k(self):
        return _K_CHOICES[self._freq.currentIndex()][1]

    def formats(self):
        return [n for n, b in self._fmt_boxes.items() if b.isChecked() and FORMATS[n].available]

    def out_dir(self):
        return self._out_dir.text().strip()

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Cartella del dataset", self._out_dir.text())
        if d:
            self._out_dir.setText(d)

    def _ticks_per_traj(self):
        """The length each drawn trajectory will have, AFTER decimation. built = its blocks' sum;
        preset/generator = the canonical 600. Mirrors dataset_gen.draw_scenario -- one truth, two readers."""
        from sim.scenario_spec import _PRESET_N
        out, k = [], self.k()
        for r, q in zip(self._rows, quotas(self.mix(), self.count())):
            fam, src = r.family.currentText(), r.source.currentText()
            if fam == "built" and src in self._specs:
                n = sum(int(b.ticks) for b in self._specs[src].blocks)
            else:
                n = _PRESET_N
            out.extend([len(range(0, n, k))] * q)
        return out

    def estimated_bytes(self):
        fmts = self.formats()
        if not fmts:
            return 0.0
        return estimate_bytes(self._ticks_per_traj(), fmts)
```
and import the estimator at the top: `from sim.export_formats import FORMATS, estimate_bytes`.
Finally, in `_refresh`, after the quota loop, update the size label:
```python
        if ok:
            b = self.estimated_bytes()
            self._size_lbl.setText(f"dimensione stimata  ≈ {b / 1e6:.1f} MB")
        else:
            self._size_lbl.setText("dimensione stimata  —")
```

- [ ] **Step 4: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_dataset_page.py -q -p no:cacheprovider
```
Expected: `12 passed`.

- [ ] **Step 5: Sabotage, watch the guard fail, revert**

In `formats()`, drop the availability filter: `return [n for n, b in self._fmt_boxes.items() if b.isChecked()]`,
and in the checkbox loop remove `b.setEnabled(spec.available)`. Re-run: expected FAIL on
`test_the_format_checkboxes_come_from_the_registry` (parquet is enabled). This proves the UI really obeys the
registry rather than a hardcoded idea of what exists. **Revert**; re-run → `12 passed`.

- [ ] **Step 6: Commit**

```bash
git add sim/ui/dataset_page.py tests/test_sim_dataset_page.py
git commit -m "feat(sim): the Dataset page's controls -- jitter, decimation + '?', registry formats, size estimate"
```

---

### Task 4: the eye — a hover preview of one sample

**Files:**
- Modify: `sim/ui/dataset_page.py`
- Test: `tests/test_sim_dataset_page.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sim_dataset_page.py`:
```python
def test_the_eye_shows_the_engines_sample_and_calls_it_a_sample(qapp):
    import numpy as np
    from sim.dataset_gen import preview_sample
    p = _page(qapp)
    r = p._rows[0]
    r.family.setCurrentText("preset")
    r.source.setCurrentText("hard_brake")
    p.show_preview(r)
    expected = preview_sample("preset", "hard_brake", p.PREVIEW_SEED, p.strength(), p._specs, p._params_gt)
    shown = p._popup_panel._curve.getData()[1]
    assert np.allclose(shown, expected)                 # the popup draws what the engine draws
    assert "campione" in p._popup_title.text()          # it says it is ONE sample, not "the" scenario


def test_the_preview_is_hidden_until_asked_and_hides_again(qapp):
    p = _page(qapp)
    assert not p._popup.isVisible()
    p.show_preview(p._rows[0])
    assert p._popup.isVisible()
    p.hide_preview()
    assert not p._popup.isVisible()
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_dataset_page.py -q -p no:cacheprovider
```
Expected: FAIL — `AttributeError: 'DatasetPage' object has no attribute 'show_preview'`.

- [ ] **Step 3: Implement the popup**

In `sim/ui/dataset_page.py`, import the engine's sampler and the preview panel at the top:
```python
from sim.dataset_gen import GENERATOR_PROFILES, preview_sample
from sim.ui.scenario_preview import ScenarioPreviewPanel
```
Add the class constant and build the popup in `__init__` (before `self.add_row()`):
```python
        self._popup = QFrame(self, Qt.ToolTip)          # a frameless floating panel
        self._popup_title = QLabel()
        self._popup_panel = ScenarioPreviewPanel()
        self._popup_panel.setFixedSize(280, 130)
        pl = QVBoxLayout(self._popup); pl.setContentsMargins(6, 6, 6, 6)
        pl.addWidget(self._popup_title); pl.addWidget(self._popup_panel)
        self._popup.hide()
```
with, at class level (right under `class DatasetPage(QWidget):`):
```python
    PREVIEW_SEED = 0            # a FIXED seed: the eye must show the same curve every time you hover
```
Add the two methods:
```python
    def show_preview(self, row):
        """Draw ONE sample of this source. For `generator` and for jittered `built` the scenario IS a
        distribution -- so this is a representative sample at a fixed seed, and the title says so."""
        fam, src = row.family.currentText(), row.source.currentText()
        if not src:
            return
        v = preview_sample(fam, src, self.PREVIEW_SEED, self.strength(), self._specs, self._params_gt)
        self._popup_panel.set_scenario(v)
        self._popup_title.setText(f"{fam} · {src} — campione (seed {self.PREVIEW_SEED})")
        self._popup.adjustSize()
        self._popup.move(row.eye.mapToGlobal(row.eye.rect().bottomLeft()))
        self._popup.show()

    def hide_preview(self):
        self._popup.hide()
```
Wire the hover in `add_row`, right after the `eye` label is created:
```python
        eye.setAttribute(Qt.WA_Hover, True)
        eye.installEventFilter(self)
```
and add the event filter to the class:
```python
    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        for r in self._rows:
            if obj is r.eye:
                if ev.type() == QEvent.Enter:
                    self.show_preview(r)
                elif ev.type() == QEvent.Leave:
                    self.hide_preview()
                break
        return super().eventFilter(obj, ev)
```

- [ ] **Step 4: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_dataset_page.py -q -p no:cacheprovider
```
Expected: `14 passed`.

- [ ] **Step 5: Sabotage, watch the guard fail, revert**

In `show_preview`, change `self.PREVIEW_SEED` to `self.PREVIEW_SEED + 1` in the `preview_sample` call only
(leave the title). Re-run: expected FAIL on `test_the_eye_shows_the_engines_sample_and_calls_it_a_sample` (the
drawn curve is a different sample). This proves the test pins that the popup shows *the engine's* sample for
the seed it advertises, not just "a curve". **Revert**; re-run → `14 passed`.

- [ ] **Step 6: Commit**

```bash
git add sim/ui/dataset_page.py tests/test_sim_dataset_page.py
git commit -m "feat(sim): the mix table's eye -- a hover preview of one representative sample"
```

---

### Task 5: wire the 5th mode into the app (reusing the existing batch idiom)

**Files:**
- Modify: `sim/ui/app.py` (import, page + stack + selector `:180-195`, `set_mode` `:369`, `_busy_controls`
  `:385`, a new `_run_dataset`)
- Test: `tests/test_sim_app_lifecycle.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sim_app_lifecycle.py`:
```python
def test_the_app_has_a_fifth_dataset_mode(qapp):
    win = SimApp(CHAMP)
    assert [win._mode_sel.itemText(i) for i in range(win._mode_sel.count())] == [
        "Live", "Meso/Macro", "Post-run", "Scenari", "Dataset"]
    assert win._mode_stack.count() == 5
    win.set_mode(4)
    assert win._mode_stack.currentIndex() == 4


def test_entering_the_dataset_mode_refreshes_the_built_sources(qapp):
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    win = SimApp(CHAMP)
    win.set_mode(4)
    assert win._dataset_page._specs == {}                 # nothing built yet
    win._scenario_page.set_spec(ScenarioSpec(name="mine", blocks=(Block("const", 120, {"v": 15.0}),),
                                             style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0))
    win._scenario_page._name_edit.setText("mine")
    win._scenario_page._on_use()
    win.set_mode(4)                                       # re-entering must pick the new spec up
    assert "mine" in win._dataset_page._specs


def test_the_generate_button_is_a_busy_control(qapp):
    win = SimApp(CHAMP)
    assert win._dataset_page._gen_btn in win._busy_controls()   # so a click cannot nest a second batch


def test_run_dataset_writes_a_dataset_and_restores_the_ui(qapp, tmp_path):
    import json
    win = SimApp(CHAMP)
    win.set_mode(4)
    p = win._dataset_page
    p._rows[0].family.setCurrentText("preset")
    p._rows[0].source.setCurrentText("following")
    p._rows[0].weight.setValue(100.0)
    p._count.setValue(2)
    for b in p._fmt_boxes.values():
        b.setChecked(False)
    p._fmt_boxes["csv"].setChecked(True)
    p._out_dir.setText(str(tmp_path))
    win._run_dataset()
    with open(str(tmp_path / "manifest.json")) as f:
        man = json.load(f)
    assert man["count"] == 2 and len(man["trajectories"]) == 2
    assert win._dataset_page._gen_btn.isEnabled()          # _done_busy ran (try/finally)
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_app_lifecycle.py -q -p no:cacheprovider
```
Expected: FAIL — the selector has 4 items, not 5.

- [ ] **Step 3: Wire it**

`sim/ui/app.py` — add the imports next to the other sim imports:
```python
from sim.dataset_gen import generate_dataset
from sim.ui.dataset_page import DatasetPage
```
After `self._scenario_page.sigScenarioBuilt.connect(self._on_scenario_built)` (`:184`), build the page and set
the app-owned run callback (the Meso idiom):
```python
        self._dataset_page = DatasetPage(params_gt=_PARAMS_GT)
        self._dataset_page._on_generate = self._run_dataset
```
Add it to the stack (after the `_scenario_page` line, `:189`) and to the selector (`:191`):
```python
        self._mode_stack.addWidget(self._dataset_page)   # page 4: dataset generator
```
```python
        self._mode_sel.addItems(["Live", "Meso/Macro", "Post-run", "Scenari", "Dataset"])
```
In `set_mode`, add the refresh hook next to the `idx == 2` one:
```python
        if idx == 4:
            self._dataset_page.set_sources(self._built_specs(), [s.name for s in self._scenarios[:self._protected_count]])
```
Add the helper (next to `scenario_count`):
```python
    def _built_specs(self):
        """{name: spec} for the user-built scenarios -- the only family with blocks to jitter."""
        return {sc.name: sp for sc, sp in zip(self._scenarios, self._specs) if sp is not None}
```
Extend `_busy_controls` (`:385-386`) so a click cannot nest a second batch:
```python
    def _busy_controls(self):
        return (self._meso_page._run_platoon_btn, self._meso_page._run_ring_btn, self._mode_sel,
                self._dataset_page._gen_btn)
```
Add the run, using the SAME idiom as `_run_platoon`/`_run_ring` (synchronous + a pumped progress + try/finally):
```python
    def _dataset_progress(self, i, total):
        # bounded progress + a pump between trajectories; every re-entry control is disabled (see _busy)
        # so processEvents cannot nest a second batch -- it only lets the window repaint instead of hanging.
        self._dataset_page._progress.setValue(int(100 * i / max(total, 1)))
        self._status.showMessage(f"dataset {i}/{total}…")
        QApplication.processEvents()

    def _run_dataset(self):
        page = self._dataset_page
        self._busy("genero dataset…")
        try:
            generate_dataset(page.mix(), page.count(), page.seed(), page.strength(), page.k(),
                             page.formats(), page.out_dir(), self._built_specs(), _PARAMS_GT,
                             on_progress=self._dataset_progress)
        finally:
            self._done_busy()
            page._progress.setValue(0)
```

- [ ] **Step 4: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_app_lifecycle.py -q -p no:cacheprovider
```
Expected: `9 passed`.

- [ ] **Step 5: Sabotage, watch the guard fail, revert**

In `_busy_controls`, drop `self._dataset_page._gen_btn` from the returned tuple. Re-run
`tests/test_sim_app_lifecycle.py::test_the_generate_button_is_a_busy_control`: expected FAIL. This proves the
test pins the anti-re-entry property that makes the whole `processEvents` pump safe — without Generate in
`_busy_controls`, the pump could let a second click nest a second batch, which is exactly the hazard
`app.py:389-391` documents. **Revert**; re-run → `9 passed`.

- [ ] **Step 6: Commit**

```bash
git add sim/ui/app.py tests/test_sim_app_lifecycle.py
git commit -m "feat(sim): wire the 5th Dataset mode, reusing the existing busy/progress batch idiom"
```

---

### Task 6: full suite, render-verify, docs

**Files:**
- Modify: `document/SIMULATOR_ARCHITECTURE.md`, `document/SIMULATOR_SESSION_RESUME.md`

- [ ] **Step 1: Full suite + the invariants are untouched**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -q -p no:cacheprovider
git diff --stat 621120b8 -- sim/state.py sim/stepper.py sim/backend.py sim/probe.py sim/events.py sim/eventprop_stepper.py utils/closed_loop_eval.py sim/scenario_spec.py data/generator.py
```
Expected: `B+~19 passed` (baseline + 2 retention + 14 page + 4 app, minus none removed); the diff-stat prints
**nothing**. ≥420 s or background.

- [ ] **Step 2: Render-verify the 5th mode**

Write a throwaway scratchpad script (`QT_QPA_PLATFORM=windows`) that builds `SimApp(CHAMP)`, builds one
scenario through the builder (so the `built` family has a source), calls `set_mode(4)`, sets a 3-family mix
(40/30/30), grabs the page to a PNG, and prints `page.mix()`, `page.k()`, `page.formats()`,
`page.estimated_bytes()`. Confirm by eye: three rows with the three families, the live quota column, the
`totale 100% ✓` badge green, parquet/hdf5 greyed, the size estimate in MB, the "?" next to the frequency.
Delete the script after; keep the PNG for the report.

- [ ] **Step 3: Update the docs**

`document/SIMULATOR_ARCHITECTURE.md`: add a `sim/ui/dataset_page.py` row (Qt only — row widgets not a
QTableWidget and why; the getters + the app-owned run, mirroring the Meso idiom; the eye's fixed PREVIEW_SEED
and the "campione" honesty; the registry-driven checkboxes); note the app is now **5 modes** and that
`sigScenarioBuilt` carries `(scenario, spec)` with `_specs` parallel to `_scenarios`; bump the test count to
the real number.
`document/SIMULATOR_SESSION_RESUME.md`: mark 7a **complete** (Plan A engine + Plan B UI) with the real count
and commits; note the spec-retention change and its 9-site churn as done; leave the **7b draft (the training
sink) as the last queued item**.

- [ ] **Step 4: Commit + push**

```bash
git add document/SIMULATOR_SESSION_RESUME.md document/SIMULATOR_ARCHITECTURE.md
git commit -m "docs(sim): resume + map -- the Dataset mode (7a) complete"
git push origin Simulator
```

- [ ] **Step 5: Report — do NOT merge to main**

Report 7a complete (engine + UI). Merge → main stays **parked**. The only queued item left is the **7b draft**
(the training sink), whose fork ① is a risk decision for its own brainstorming.

---

## Self-review (against the spec)

- **Spec §2 spec retention** → Task 1 (signal → 2 args, `_specs` parallel, pop-both, the 9 churn sites). ✓
- **Spec §3 the mix table + exact quota display + empty-built edge case** → Task 2. ✓
- **Spec §4 decimation UI + the "?"** → Task 3 (`_freq`, `k()`, `_freq_help` tooltip). ✓
- **Spec §5 registry-driven checkboxes + disabled with reason** → Task 3 (+ its sabotage). ✓
- **Spec §6 size estimate** → Task 3 (`estimated_bytes` computed via the engine's `estimate_bytes`). ✓
- **Spec §7 the eye + the "campione" caveat** → Task 4. ✓
- **Spec §9 the page + app wiring + no-freeze** → Task 5 (the Meso idiom + `_busy_controls` + try/finally). ✓
- **Spec §1 the strength caveat surfaced in the UI** → Task 3 (`_jitter_note`, pinned by a test). ✓
- **Spec §8 manifest / §Design engine** → already delivered by Plan A; this plan only calls it. ✓
- **Placeholder scan:** none — every step shows the code, and every sabotage breaks a test rather than asking
  for a hand-check. ✓
- **Type/name consistency:** `set_sources`/`mix`/`count`/`seed`/`strength`/`k`/`formats`/`out_dir`/
  `estimated_bytes`/`show_preview`/`hide_preview`/`add_row`/`remove_row`/`_rows`/`_gen_btn`/`_fmt_boxes`/
  `_freq`/`_freq_help`/`_jitter_note`/`_size_lbl`/`_popup`/`_popup_panel`/`_popup_title`/`PREVIEW_SEED` are
  used identically across tasks and tests; `_built_specs()` is the single producer of the `specs` dict. ✓
