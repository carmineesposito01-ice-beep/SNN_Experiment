# Dataset generator 7b — Plan B1: extract the MixTable — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Extract the 7a Dataset page's row-widget mix table into a reusable `sim/ui/mix_table.py` widget, with
**zero behaviour change** — the 5th "Dataset" mode looks and works exactly as before.

**Architecture:** A behaviour-preserving refactor. `MixTable(QWidget)` owns the rows, the family→source cascade,
the eye preview, `mix()`, the quota column, and the total-percent gate; it emits a `changed` signal. `DatasetPage`
keeps seed/count/jitter/frequency/formats/size/folder/generate and listens to `changed`. This is the seam the
later B2 plan needs (train and val become two `MixTable` instances), landed first and separately so the risky
part — moving code the 7a green tests reach into — is one isolated, reviewable commit.

**Tech Stack:** PySide6 (Qt), pyqtgraph, pytest. No new deps.

**Spec:** `docs/superpowers/specs/2026-07-17-dataset-generator-7b-design.md` (approved) — §UI, the MixTable
extraction. **This plan is B1 (the refactor only). B2 (the Training destination, the validation selector,
Cancel+ETA) is a separate plan, written after this lands.**

---

## Read before you start

**Runner — never `conda run`:**
```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest <target> -q -p no:cacheprovider
```

**Suite = SIM glob** — `pytest tests/test_sim_*.py tests/test_champion_io.py`, **NEVER `pytest tests/`**
(`tests/test_fpga_io.py` calls `sys.exit()` at import → `INTERNALERROR`).

⚠️ **Full suite ~3 min → ≥420 s or background, and run NOTHING else meanwhile.**
`test_custom_composer_refresh_fits_in_a_frame` asserts a wall-clock peak and reddens under parallel load.
⚠️ **When checking the suite result, do NOT `pytest … 2>&1 | tail`** — the pipe reports *tail*'s exit code, not
pytest's, and a faulthandler shutdown dump (torch/OMP) can look like a failure. Redirect to a file and read the
summary + a separate `echo PYTEST_EXIT=$?`.

**Commits:** conventional, **no `Co-Authored-By`**. **Do not merge to main** (parked).

**Invariants — empty `git diff`:** `sim/{state,stepper,backend,probe,events,eventprop_stepper}.py`,
`utils/closed_loop_eval.py`, `sim/scenario_spec.py`, `train.py`. `data/generator.py`'s gate is
`tests/test_sim_provenance.py` — **do not touch it in this plan** (B1 is UI-only). No scipy/LAPACK/compiled deps
(OMP #15).

**This is a REFACTOR: behaviour must not change.** The proof is that the whole SIM suite stays **371 green**, the
Analysis-mode render is unchanged, and the app still wires the 5th mode the same way.

### The real 7a code you are restructuring (read it, do not trust this summary)

`sim/ui/dataset_page.py` (281 lines) today holds BOTH the mix table and the controls in one class. The mix-table
parts (to move) and the control parts (to keep) are:

| Moves to `MixTable` | Stays on `DatasetPage` |
|---|---|
| `_Row` dataclass; `_rows`; `_rows_box`; `_add_btn` ("+ riga") | `_count`, `_seed`, `_jitter`+`_jitter_lbl`+`_jitter_note` |
| `add_row`, `remove_row` | `_freq`+`_freq_help`, `_fmt_boxes` |
| `_sync_family_enabled`, `_sources_for`, `_reload_sources`, `set_sources` | `_size_lbl`, `_out_dir`+`_browse`, `_gen_btn`, `_progress` |
| the eye: `_popup`/`_popup_title`/`_popup_panel`, `show_preview`, `hide_preview`, `eventFilter`, `PREVIEW_SEED` | `_pick_dir`, `_ticks_per_traj`, `estimated_bytes`, `formats`, `k`, `count`, `seed`, `strength`, `out_dir` |
| `mix()`, the quota `QLabel`s, `_total_lbl` + the total-percent computation | `_on_generate`, the "MIX" header wiring |

**The dependency knots (why the seam is where it is):**
- `show_preview` calls `self.strength()` (a PAGE control) and `preview_sample(fam, src, PREVIEW_SEED,
  strength, self._specs, self._params_gt)`. So `MixTable` needs `params_gt` (constructor) + `_specs`
  (`set_sources`) + **strength injected as a callable** (the page owns the jitter slider).
- `_ticks_per_traj` (a PAGE method, feeds the size estimate) reaches into `self._specs[src].blocks` for `built`
  rows. After extraction the specs live on the `MixTable`; the page reads them via `self._mix.specs()` /
  `self._mix.mix()`.
- `_refresh` today does BOTH: the mix gate (total==100 → enable `_gen_btn`, fill quotas) AND the size estimate.
  After extraction: `MixTable` owns the quota fill + total label + `is_valid()`, and emits `changed`;
  `DatasetPage._refresh` (a `changed` slot) does the gate (`_gen_btn.setEnabled(mix.is_valid())`) + the size.

### The 7a tests — the churn, enumerated BEFORE touching (this is the lesson)

`tests/test_sim_dataset_page.py` (170 lines) has **14 tests**. After extraction they split cleanly by what they
actually test — **8 move, 6 stay**:

**MOVE to a new `tests/test_sim_mix_table.py`** (they test rows/cascade/eye/mix — now `MixTable`'s job):
- `test_a_fresh_page_has_one_row_and_the_families`
- `test_the_source_combo_cascades_from_the_family`
- `test_the_built_family_is_disabled_when_no_scenario_was_built`
- `test_the_quota_column_is_live_and_exact`
- `test_mix_returns_the_engines_MixEntry`
- `test_removing_a_row_keeps_the_page_consistent`
- `test_the_eye_shows_the_engines_sample_and_calls_it_a_sample`
- `test_the_preview_is_hidden_until_asked_and_hides_again`

**STAY in `tests/test_sim_dataset_page.py`** (they test page controls / the page↔table integration):
- `test_generate_is_gated_on_a_total_of_100` (page `_gen_btn` reacts to the table's total → drives `p._mix`)
- `test_the_format_checkboxes_come_from_the_registry`
- `test_formats_returns_only_the_checked_available_ones`
- `test_the_frequency_combo_maps_to_k_and_explains_itself`
- `test_the_jitter_slider_states_its_own_limit`
- `test_the_size_estimate_matches_the_engines_formula` (drives `p._mix` rows + page count/freq)

**The eye glyph fix (spec-noted):** 7a used `👁`, which renders as a reddish blob in Windows' default font. Change
it to **`"⊙"`** (a ring-with-dot: reads as an eye/aperture and renders in the default font). `test_the_eye_...`
asserts on the popup content and title, not the glyph, so it is unaffected; add one assertion that the eye label
is not the old `👁`.

---

## File structure

| File | Responsibility |
|---|---|
| `sim/ui/mix_table.py` **(new)** | `MixTable(QWidget)` — the reusable mix table: rows, cascade, eye, `mix()`, quota column, total gate, `changed` signal. `with_regime=False` here (the 4-field regime column is B2). |
| `sim/ui/dataset_page.py` **(modify)** | Drops the inlined rows/eye/cascade; holds a `MixTable` instance + the controls; `_refresh` becomes a `changed` slot. Behaviour identical. |
| `tests/test_sim_mix_table.py` **(new)** | The 8 moved tests, retargeted at `MixTable` directly. |
| `tests/test_sim_dataset_page.py` **(modify)** | Keeps the 6 control/integration tests, retargeted through `p._mix` where they touch rows. |

**Not touched:** `sim/ui/app.py` (it calls `DatasetPage.set_sources`, `mix`, `count`, ... — all preserved as
delegating methods, so the app needs no change; confirm in Task 2 Step 0).

---

### Task 1: `MixTable` — the reusable widget, tested alone

**Files:**
- Create: `sim/ui/mix_table.py`, `tests/test_sim_mix_table.py`

- [ ] **Step 0: Confirm the baseline**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulator"
git log --oneline -1 && git status --short
```
Expected: HEAD `77eb99b6`, clean tree. (The full suite is 371 green from B-plan-A; you do not need to re-run it
here — Task 3 does the full run.)

- [ ] **Step 1: Write the failing tests** — create `tests/test_sim_mix_table.py`:

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
from sim.ui.mix_table import MixTable                            # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _specs():
    return {"mine": ScenarioSpec(name="mine", blocks=(Block("const", 120, {"v": 15.0}),),
                                 style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)}


def _table(qapp, specs=None):
    t = MixTable(params_gt=_PG, strength=lambda: 0.25)
    t.set_sources(specs if specs is not None else _specs(), ["following", "hard_brake"])
    return t


def test_a_fresh_table_has_one_row_and_the_families(qapp):
    from sim.dataset_mix import FAMILIES
    t = _table(qapp)
    assert len(t._rows) == 1
    assert [t._rows[0].family.itemText(i) for i in range(t._rows[0].family.count())] == list(FAMILIES)


def test_the_source_combo_cascades_from_the_family(qapp):
    from sim.dataset_gen import GENERATOR_PROFILES
    t = _table(qapp)
    r = t._rows[0]
    r.family.setCurrentText("preset")
    assert [r.source.itemText(i) for i in range(r.source.count())] == ["following", "hard_brake"]
    r.family.setCurrentText("generator")
    assert [r.source.itemText(i) for i in range(r.source.count())] == list(GENERATOR_PROFILES)
    r.family.setCurrentText("built")
    assert [r.source.itemText(i) for i in range(r.source.count())] == ["mine"]


def test_the_built_family_is_disabled_when_no_scenario_was_built(qapp):
    t = _table(qapp, specs={})
    model = t._rows[0].family.model()
    assert not model.item(0).isEnabled()          # "built" is FAMILIES[0]
    assert "Scenari" in model.item(0).toolTip()


def test_the_quota_column_is_live_and_exact(qapp):
    t = _table(qapp)
    t.set_count(100)
    t._rows[0].weight.setValue(100.0)
    assert t._rows[0].quota.text() == "100"
    t.add_row(); t._rows[0].weight.setValue(40.0); t._rows[1].weight.setValue(60.0)
    assert [r.quota.text() for r in t._rows] == ["40", "60"]


def test_mix_returns_the_engines_MixEntry(qapp):
    from sim.dataset_mix import MixEntry, validate_mix
    t = _table(qapp)
    t._rows[0].family.setCurrentText("preset")
    t._rows[0].source.setCurrentText("hard_brake")
    t._rows[0].weight.setValue(100.0)
    mix = t.mix()
    assert mix == [MixEntry("preset", "hard_brake", 100.0)]
    validate_mix(mix)


def test_removing_a_row_keeps_the_table_consistent(qapp):
    t = _table(qapp)
    t.add_row()
    assert len(t._rows) == 2
    t.remove_row(t._rows[1])
    assert len(t._rows) == 1


def test_is_valid_tracks_the_total(qapp):
    t = _table(qapp)
    t._rows[0].weight.setValue(40.0)
    assert not t.is_valid() and "✗" in t._total_lbl.text()
    t._rows[0].weight.setValue(100.0)
    assert t.is_valid() and "✓" in t._total_lbl.text()


def test_changed_fires_when_a_weight_moves(qapp):
    t = _table(qapp)
    seen = []
    t.changed.connect(lambda: seen.append(1))
    t._rows[0].weight.setValue(55.0)
    assert seen                                    # the page listens to this to re-gate + re-estimate


def test_the_eye_shows_the_engines_sample_and_calls_it_a_sample(qapp):
    from sim.dataset_gen import preview_sample
    t = _table(qapp)
    r = t._rows[0]
    r.family.setCurrentText("preset")
    r.source.setCurrentText("hard_brake")
    t.show_preview(r)
    expected = preview_sample("preset", "hard_brake", t.PREVIEW_SEED, 0.25, t._specs, t._params_gt)
    shown = t._popup_panel._curve.getData()[1]
    assert np.allclose(shown, expected)
    assert "campione" in t._popup_title.text()
    assert r.eye.text() != "👁"                     # the glyph that rendered as a blob is gone


def test_the_preview_is_hidden_until_asked_and_hides_again(qapp):
    t = _table(qapp)
    assert not t._popup.isVisible()
    t.show_preview(t._rows[0])
    assert t._popup.isVisible()
    t.hide_preview()
    assert not t._popup.isVisible()
```

- [ ] **Step 2: Run — expect FAIL**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_mix_table.py -q -p no:cacheprovider
```
Expected: collection error, `ModuleNotFoundError: No module named 'sim.ui.mix_table'`.

- [ ] **Step 3: Create `sim/ui/mix_table.py`**

This is the 7a row/cascade/eye/mix code, lifted verbatim from `dataset_page.py` into a `QWidget` with a
`changed` signal and a `set_count` (the count lives on the page, but the table needs it to compute quotas — the
page pushes it in via `set_count` and the table caches it). `with_regime` is accepted now but only `False` is
implemented (the regime column is B2); a `True` value raises `NotImplementedError` so a premature B2 wiring
fails loudly instead of silently dropping the regime.

```python
"""The mix table: a list of ROW WIDGETS over the scenario families -> exact per-row quotas.

Extracted from the 7a Dataset page so it can be reused (B2 makes train and val two instances). Row widgets, not
a QTableWidget with delegates: with a handful of rows it is simpler and testable without simulating cell edits.

The table owns the rows, the family->source cascade, the eye preview, mix(), the quota column and the total-%
label; it emits `changed` on any edit. The page owns seed/count/jitter/formats/size and listens to `changed`.
`strength` is injected (the jitter slider lives on the page) so the eye can draw a representative sample."""
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from sim.dataset_gen import GENERATOR_PROFILES, preview_sample
from sim.dataset_mix import FAMILIES, MixEntry, quotas
from sim.ui.scenario_preview import ScenarioPreviewPanel

_EYE = "⊙"          # 7a's 👁 rendered as a reddish blob in Windows' default font; this reads as an aperture


@dataclass
class _Row:
    frame: QFrame
    family: QComboBox
    source: QComboBox
    eye: QLabel
    weight: QDoubleSpinBox
    quota: QLabel
    kill: QPushButton


class MixTable(QWidget):
    PREVIEW_SEED = 0            # FIXED: the eye must show the same curve every time you hover the same source
    changed = Signal()

    def __init__(self, params_gt, strength, with_regime=False):
        super().__init__()
        if with_regime:
            raise NotImplementedError("with_regime is B2; B1 ships the 3-field mix only")
        self._params_gt = params_gt
        self._strength = strength           # callable -> float in [0,1] (the page's jitter slider)
        self._with_regime = with_regime
        self._specs = {}
        self._preset_names = []
        self._rows = []
        self._count = 100                   # the page pushes the real count via set_count()

        self._rows_box = QVBoxLayout()
        self._add_btn = QPushButton("+ riga"); self._add_btn.clicked.connect(self.add_row)
        self._total_lbl = QLabel()

        self._popup = QFrame(self, Qt.ToolTip)
        self._popup_title = QLabel()
        self._popup_panel = ScenarioPreviewPanel()
        self._popup_panel.setFixedSize(280, 130)
        pl = QVBoxLayout(self._popup); pl.setContentsMargins(6, 6, 6, 6)
        pl.addWidget(self._popup_title); pl.addWidget(self._popup_panel)
        self._popup.hide()

        head = QHBoxLayout()
        for t in ("famiglia", "sorgente", "", "peso %", "→ traiettorie", ""):
            lbl = QLabel(t); lbl.setStyleSheet("color:#8b949e"); head.addWidget(lbl)
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        root.addLayout(head)
        root.addLayout(self._rows_box)
        bottom = QHBoxLayout(); bottom.addWidget(self._add_btn); bottom.addWidget(self._total_lbl)
        bottom.addStretch(1)
        root.addLayout(bottom)
        self.add_row()

    # ---- sources ----
    def set_sources(self, specs, preset_names):
        self._specs = dict(specs)
        self._preset_names = list(preset_names)
        for r in self._rows:
            self._sync_family_enabled(r)
            self._reload_sources(r)
        self._refresh()

    def set_count(self, count):
        self._count = int(count)
        self._refresh()

    def specs(self):
        return self._specs

    def _sync_family_enabled(self, row):
        item = row.family.model().item(FAMILIES.index("built"))
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
        eye = QLabel(_EYE); eye.setToolTip("anteprima di un campione di questa sorgente")
        eye.setAttribute(Qt.WA_Hover, True)
        eye.installEventFilter(self)
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
            return
        self._rows.remove(row)
        row.frame.setParent(None)
        self._refresh()

    # ---- the eye ----
    def show_preview(self, row):
        fam, src = row.family.currentText(), row.source.currentText()
        if not src:
            return
        v = preview_sample(fam, src, self.PREVIEW_SEED, self._strength(), self._specs, self._params_gt)
        self._popup_panel.set_scenario(v)
        self._popup_title.setText(f"{fam} · {src} — campione (seed {self.PREVIEW_SEED})")
        self._popup.adjustSize()
        self._popup.move(row.eye.mapToGlobal(row.eye.rect().bottomLeft()))
        self._popup.show()

    def hide_preview(self):
        self._popup.hide()

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

    # ---- the mix ----
    def mix(self):
        return [MixEntry(r.family.currentText(), r.source.currentText(), float(r.weight.value()))
                for r in self._rows]

    def total(self):
        return sum(r.weight.value() for r in self._rows)

    def is_valid(self):
        return abs(self.total() - 100.0) <= 0.01 and all(r.source.count() for r in self._rows)

    # ---- refresh ----
    def _refresh(self):
        ok = self.is_valid()
        self._total_lbl.setText(f"totale {self.total():.0f}% {'✓' if ok else '✗'}")
        self._total_lbl.setStyleSheet(f"color:{'#2e8b57' if ok else '#d1495b'}")
        if ok:
            for r, q in zip(self._rows, quotas(self.mix(), self._count)):
                r.quota.setText(str(q))
        else:
            for r in self._rows:
                r.quota.setText("—")
        self.changed.emit()
```

- [ ] **Step 4: Run — expect PASS**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_mix_table.py -q -p no:cacheprovider
```
Expected: `10 passed`.

- [ ] **Step 5: Prove the sabotage bites**

In `MixTable._refresh`, change `self.changed.emit()` to nothing (delete the line). Run: `test_changed_fires...`
must FAIL. Restore it and re-run green. (A value-level check that the signal — which the page relies on to
re-gate — actually fires.)

- [ ] **Step 6: Commit**

```bash
git add sim/ui/mix_table.py tests/test_sim_mix_table.py
git commit -m "feat(sim-ui): estrai MixTable -- il mix a righe-widget come unita' riusabile

Righe + cascata + occhio + mix() + quota + gate 100% spostati dalla
DatasetPage in un widget con un segnale `changed`. strength iniettato (la
slider vive sulla pagina). with_regime accettato ma NotImplementedError
finche' non arriva il B2. L'occhio non e' piu' la U+1F441 (rendeva come un
pallino nel font di Windows). Comportamento invariato: e' un refactor."
```

---

### Task 2: `DatasetPage` uses the `MixTable` — behaviour identical

**Files:**
- Modify: `sim/ui/dataset_page.py`, `tests/test_sim_dataset_page.py`

- [ ] **Step 0: Enumerate the app's use of DatasetPage (churn pre-check)**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" - <<'PY'
import subprocess
for pat in ("_dataset_page.", "DatasetPage("):
    print("==", pat)
    print(subprocess.run(["git","grep","-n",pat,"--","sim/ui/app.py"],capture_output=True,text=True).stdout)
PY
```
Confirm the app touches only the PUBLIC surface `set_sources`, `mix`, `count`, `seed`, `strength`, `k`,
`formats`, `out_dir`, `estimated_bytes`, `_on_generate`, `_gen_btn`, `_progress`. **All of these must survive on
`DatasetPage` as-is** (the page keeps its getters; only the row internals move). If the app reaches a row
internal (`_rows`, `add_row`, `show_preview`), STOP and report — the seam is wrong.

- [ ] **Step 1: Rewrite `sim/ui/dataset_page.py`** to hold a `MixTable` and delegate. Read the real file first,
then replace it with (behaviour identical — same widgets, same layout order, same getters):

```python
"""The Dataset mode (the 5th): a MixTable + the export controls.

The mix table (rows, cascade, eye, quota, total gate) is now sim/ui/mix_table.py, reused by the later training
destination. This page owns seed/count/jitter/frequency/formats/size/folder/generate and re-gates + re-estimates
whenever the table emits `changed`. The page owns WIDGETS and exposes getters; the APP owns the run (the Meso
idiom, app.py:174) -- Generate only calls self._on_generate."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QProgressBar, QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget)

from sim.export_formats import FORMATS, estimate_bytes
from sim.scenario_spec import _PRESET_N
from sim.ui.mix_table import MixTable

_K_CHOICES = [("10 Hz (nativa)", 1), ("5 Hz", 2), ("2 Hz", 5), ("1 Hz", 10)]


class DatasetPage(QWidget):
    PREVIEW_SEED = 0            # kept for back-compat; the eye's seed now lives on MixTable

    def __init__(self, params_gt):
        super().__init__()
        self._params_gt = params_gt
        self._on_generate = None

        self._mix = MixTable(params_gt, strength=self.strength)
        self._mix.changed.connect(self._refresh)

        self._count = QSpinBox(); self._count.setRange(1, 100000); self._count.setValue(100)
        self._count.valueChanged.connect(lambda v: (self._mix.set_count(v), self._refresh()))
        self._seed = QSpinBox(); self._seed.setRange(0, 2**31 - 1); self._seed.setValue(42)
        self._gen_btn = QPushButton("Genera")
        self._gen_btn.clicked.connect(lambda: self._on_generate() if self._on_generate else None)
        self._progress = QProgressBar(); self._progress.setRange(0, 100); self._progress.setValue(0)

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
            "Le altre scelte DECIMANO l'export (un campione ogni k) e ricalcolano a_leader a dt_out:\n"
            "l'accelerazione a 0.2 s NON è quella a 0.1 s.\n"
            "Nessun upsampling: inventerebbe dati che la fisica non ha prodotto.")

        self._fmt_boxes = {}
        for name, spec in FORMATS.items():
            b = QCheckBox(name)
            b.setEnabled(spec.available)
            if not spec.available:
                b.setToolTip(spec.reason)
            b.setChecked(name in ("csv", "mat"))
            b.stateChanged.connect(self._refresh)
            self._fmt_boxes[name] = b

        self._size_lbl = QLabel()
        self._out_dir = QLineEdit()
        self._browse = QPushButton("Sfoglia…"); self._browse.clicked.connect(self._pick_dir)

        root = QVBoxLayout(self)
        root.addWidget(QLabel("MIX"))
        root.addWidget(self._mix)
        ctl = QHBoxLayout()
        for w in (QLabel("seed"), self._seed, QLabel("traiettorie"), self._count,
                  QLabel("jitter"), self._jitter, self._jitter_lbl, self._jitter_note):
            ctl.addWidget(w)
        ctl.addStretch(1)
        fmt_row = QHBoxLayout(); fmt_row.addWidget(QLabel("formato"))
        for b in self._fmt_boxes.values():
            fmt_row.addWidget(b)
        fmt_row.addStretch(1)
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
        root.addStretch(1)
        self._refresh()

    # ---- sources (delegated to the table) ----
    def set_sources(self, specs, preset_names):
        self._mix.set_sources(specs, preset_names)

    # ---- getters (the app reads these; the Meso idiom) ----
    def mix(self):
        return self._mix.mix()

    def count(self):
        return int(self._count.value())

    def seed(self):
        return int(self._seed.value())

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
        """Length each drawn trajectory will have AFTER decimation. built = its blocks' sum; preset/generator =
        the canonical 600 -- mirrors dataset_gen.draw_scenario."""
        from sim.dataset_mix import quotas
        out, k, specs = [], self.k(), self._mix.specs()
        for r, q in zip(self._mix._rows, quotas(self.mix(), self.count())):
            fam, src = r.family.currentText(), r.source.currentText()
            n = (sum(int(b.ticks) for b in specs[src].blocks)
                 if fam == "built" and src in specs else _PRESET_N)
            out.extend([len(range(0, n, k))] * q)
        return out

    def estimated_bytes(self):
        fmts = self.formats()
        return estimate_bytes(self._ticks_per_traj(), fmts) if fmts else 0.0

    # ---- refresh (a `changed` slot + the control edits) ----
    def _refresh(self):
        ok = self._mix.is_valid()
        self._gen_btn.setEnabled(ok)
        if ok:
            self._size_lbl.setText(f"dimensione stimata  ≈ {self.estimated_bytes() / 1e6:.1f} MB")
        else:
            self._size_lbl.setText("dimensione stimata  —")
```

- [ ] **Step 2: Retarget the 8 moved tests OUT of `tests/test_sim_dataset_page.py`**

Delete these 8 test functions from `tests/test_sim_dataset_page.py` (they now live in `test_sim_mix_table.py`
from Task 1): `test_a_fresh_page_has_one_row_and_the_families`, `test_the_source_combo_cascades_from_the_family`,
`test_the_built_family_is_disabled_when_no_scenario_was_built`, `test_the_quota_column_is_live_and_exact`,
`test_mix_returns_the_engines_MixEntry`, `test_removing_a_row_keeps_the_page_consistent`,
`test_the_eye_shows_the_engines_sample_and_calls_it_a_sample`, `test_the_preview_is_hidden_until_asked_and_hides_again`.

- [ ] **Step 3: Retarget the 2 integration tests that touch rows** — in `tests/test_sim_dataset_page.py`, the
gate test and the size test reach into rows; point them at `p._mix._rows`. Replace those two functions with:

```python
def test_generate_is_gated_on_a_total_of_100(qapp):
    p = _page(qapp)
    p._mix._rows[0].weight.setValue(40.0)
    assert not p._gen_btn.isEnabled()
    p._mix._rows[0].weight.setValue(100.0)
    assert p._gen_btn.isEnabled()


def test_the_size_estimate_matches_the_engines_formula(qapp):
    from sim.export_formats import estimate_bytes
    p = _page(qapp)
    p._count.setValue(10)
    p._mix._rows[0].family.setCurrentText("preset")
    p._mix._rows[0].source.setCurrentText("hard_brake")
    p._mix._rows[0].weight.setValue(100.0)
    for b in p._fmt_boxes.values():
        b.setChecked(False)
    p._fmt_boxes["csv"].setChecked(True)
    p._freq.setCurrentIndex(1)                          # k=2 -> 600/2 = 300 ticks each
    expected = estimate_bytes([300] * 10, ["csv"])
    assert abs(p.estimated_bytes() - expected) < 1.0
    assert "MB" in p._size_lbl.text()
```

The other 4 stayed tests (`test_the_format_checkboxes...`, `test_formats_returns...`,
`test_the_frequency_combo...`, `test_the_jitter_slider...`) touch only page controls (`p._fmt_boxes`, `p._freq`,
`p._freq_help`, `p._jitter`, `p._jitter_note`, `p.strength`, `p.k`, `p.formats`) — leave them unchanged.

- [ ] **Step 4: Run both UI test files — expect PASS**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_mix_table.py tests/test_sim_dataset_page.py tests/test_sim_ui_smoke.py -q -p no:cacheprovider
```
Expected: all pass (10 mix-table + 6 page + the ~90 ui-smoke, which build `SimApp` and exercise the 5th mode
through the app — this is the real proof the app still drives the page).

- [ ] **Step 5: Prove the refactor preserves behaviour (sabotage)**

In `DatasetPage.set_sources`, change `self._mix.set_sources(specs, preset_names)` to `pass` (drop the
delegation). Run the command above: `test_sim_ui_smoke.py`'s dataset tests and the page tests must FAIL (the
built family never populates). Restore it and re-run green. This proves the delegation is load-bearing.

- [ ] **Step 6: Commit**

```bash
git add sim/ui/dataset_page.py tests/test_sim_dataset_page.py
git commit -m "refactor(sim-ui): la DatasetPage usa la MixTable estratta -- comportamento invariato

La pagina tiene seed/count/jitter/frequenza/formati/size/cartella e
ri-gate + ri-stima quando la tabella emette `changed`. I test del mix
(righe/cascata/occhio/quota) sono in test_sim_mix_table.py; qui restano
i test dei controlli e dell'integrazione pagina<->tabella. Nessun cambio
di comportamento: il 5o modo Analisi e' identico."
```

---

### Task 3: Full suite, render-verify (identical), docs, push

**Files:**
- Modify: `document/SIMULATOR_ARCHITECTURE.md`

- [ ] **Step 1: Full suite — quiet machine, no pipe**

```bash
OUT="<scratchpad>/suite_b1.txt"
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -rf -p no:cacheprovider > "$OUT" 2>&1; echo "PYTEST_EXIT=$?" >> "$OUT"
```
Then read the summary + exit from `$OUT`. Expected: **371 passed** (unchanged — 8 tests moved file, 2 new
mix-table tests `test_is_valid...`/`test_changed_fires...` added, so the count is 371 + 2 = **373**; confirm the
real number), `PYTEST_EXIT=0`. Give it ≥420 s. **Do NOT run anything else while it runs.**

- [ ] **Step 2: Invariants empty**

```bash
git diff 77eb99b6 HEAD -- sim/state.py sim/stepper.py sim/backend.py sim/probe.py sim/events.py \
  sim/eventprop_stepper.py utils/closed_loop_eval.py sim/scenario_spec.py train.py data/generator.py sim/ui/app.py
```
Expected: **empty** — B1 is a UI refactor that touches only `dataset_page.py` + the new `mix_table.py` + tests.
`sim/ui/app.py` MUST be empty (the delegation kept the page's public surface). If `app.py` is non-empty, the
seam was wrong — investigate.

- [ ] **Step 3: Render-verify — the Analysis mode is UNCHANGED**

Write `<scratchpad>/render_b1.py` (real dark theme, real widgets) that builds `SimApp`, enters the Dataset mode,
sets a 2-row mix, and grabs a PNG:

```python
import os, sys
os.environ["QT_QPA_PLATFORM"] = "windows"
REPO = r"D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator"
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
from PySide6.QtWidgets import QApplication
from sim.ui.theme import apply_dark_theme
from sim.ui.app import SimApp
app = QApplication.instance() or QApplication([]); apply_dark_theme(app)
win = SimApp(os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt"))
win.set_mode(4)
p = win._dataset_page
p._mix._rows[0].family.setCurrentText("preset"); p._mix._rows[0].source.setCurrentText("hard_brake")
p._mix._rows[0].weight.setValue(60.0)
r2 = p._mix.add_row(); r2.family.setCurrentText("generator"); r2.source.setCurrentText("stop_and_go"); r2.weight.setValue(40.0)
p.resize(900, 460); p.show(); app.processEvents()
print("valido:", p._mix.is_valid(), "| totale:", p._mix._total_lbl.text(), "| stima:", p._size_lbl.text())
print("occhio:", repr(p._mix._rows[0].eye.text()))
p.grab().save(os.path.join(SP, "b1_dataset.png")); print("saved")
```

Run with `PYTHONIOENCODING=utf-8`. Read the PNG. Confirm: two rows, `totale 100% ✓`, a size estimate, the eye
glyph is the new `⊙` not `👁`. It must look like the 7a Dataset mode (this is a refactor).

- [ ] **Step 4: Update the map** — `document/SIMULATOR_ARCHITECTURE.md`: add a `sim/ui/mix_table.py` row
(the extracted reusable mix table — rows/cascade/eye/mix()/quota/total + `changed`; `with_regime` reserved for
B2); update the `sim/ui/dataset_page.py` description to "holds a MixTable + the export controls, re-gates on
`changed`"; bump the test count to the real number from Step 1; note the eye glyph changed from `👁` to `⊙`.

- [ ] **Step 5: Commit + push**

```bash
git add document/SIMULATOR_ARCHITECTURE.md
git commit -m "docs(sim): la mappa -- MixTable estratta (7b UI B1), comportamento invariato"
git push origin Simulator
```

- [ ] **Step 6: Report — do NOT merge to main.** Report B1 complete: the MixTable is extracted, the suite is
green at the real count, invariants (incl. `app.py`) empty, the Analysis mode render is unchanged. **Next: Plan
B2** (the Training destination — the toggle, the training controls, the validation selector, Cancel+ETA, the
app routing), written after this lands.
