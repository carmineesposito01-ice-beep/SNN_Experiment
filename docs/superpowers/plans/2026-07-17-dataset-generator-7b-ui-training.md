# Dataset generator 7b — Plan B2: the Training destination — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a **Training** destination to the Dataset mode — a mix over 4 families with a regime column,
train/val counts, a 3-mode validation selector, and Cancel+ETA — that writes the `.pt` cache `train.py` reads,
via the 7b engine already built.

**Architecture:** A destination toggle **Analisi | Training** on `DatasetPage` switches a `QStackedWidget`
between today's analysis content and a new **`TrainingPanel`** widget. `MixTable` gains a `with_regime=True`
mode (regime column + `cut_in` family + `TrainMixEntry` output + a live window-share column). The panel holds a
training `MixTable`, the training controls, and — only for validation mode "mix diverso" — a second `MixTable`
for the val mix. The app's `_run_dataset` routes analysis→`generate_dataset` (unchanged) and
training→`build_training_cache`; a Cancel button (kept out of the busy-disable set) makes the existing
`processEvents()` pump abortable.

**Tech Stack:** PySide6 (Qt), pyqtgraph, torch (the engine writes the `.pt`), pytest. No new deps.

**Spec:** `docs/superpowers/specs/2026-07-17-dataset-generator-7b-design.md` (approved) — §UI. **This is B2, the
last plan of 7b. B1 (the MixTable extraction) and Plan A (the engine) are landed.**

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
`test_custom_composer_refresh_fits_in_a_frame` asserts a wall-clock peak.
⚠️ **When reading the suite result, do NOT `pytest … 2>&1 | tail`** — the pipe reports *tail*'s exit code, not
pytest's, and a faulthandler shutdown dump (torch/OMP) can look like a failure. Redirect to a file, read the
summary + a separate `echo PYTEST_EXIT=$?`.

**Commits:** conventional, **no `Co-Authored-By`**. **Do not merge to main** (parked, behind Simulink_Importer).

**Invariants — empty `git diff`:** `sim/{state,stepper,backend,probe,events,eventprop_stepper}.py`,
`utils/closed_loop_eval.py`, `sim/scenario_spec.py`, `train.py`, `data/generator.py` (its gate is
`tests/test_sim_provenance.py` — **do not touch it**). No scipy/LAPACK/compiled deps (OMP #15).
`sim/train_mix.py` and `sim/train_gen.py` are the 7b engine — you MAY add to `train_gen.py` (Task 1's pure
helper) but do not change existing engine behaviour.

### The real code you build on (read it, do not trust this summary)

- **`sim/ui/mix_table.py`** — `MixTable(QWidget)`, `__init__(params_gt, strength, with_regime=False)` (True
  currently raises `NotImplementedError` — Task 2 implements it). Has `set_sources`, `set_count`, `specs()`,
  `mix()` (→ `MixEntry` 3-field), `total()`, `is_valid()`, `add_row()`, `remove_row(row)`, `show_preview(row)`,
  `hide_preview()`, `eventFilter`, `_rows` (dataclass `_Row(frame, family, source, eye, weight, quota, kill)`),
  `PREVIEW_SEED`, `_total_lbl`, `_popup`, `changed = Signal()`. Eye glyph `⊙`. Row header today is
  `("famiglia","sorgente","","peso %","→ traiettorie","")`.
- **`sim/ui/dataset_page.py`** (146 lines) — holds `self._mix = MixTable(params_gt, strength=self.strength)`,
  `_mix.changed → _refresh`; controls `_count`/`_seed`/`_jitter`/`_freq`/`_fmt_boxes`/`_size_lbl`/`_out_dir`/
  `_gen_btn`/`_progress`; getters `mix/count/seed/strength/k/formats/out_dir/estimated_bytes`; `_ticks_per_traj`
  reads `self._mix._rows` + `self._mix.specs()`; `_refresh` gates `_gen_btn` on `is_valid()` + sets `≈ MB`.
- **`sim/train_mix.py`** — `TrainMixEntry(family, source, regime, weight)`,
  `FAMILIES_TRAIN=("built","preset","generator","cut_in")`,
  `REGIMES=("highway","urban","truck","mixed","freeflow","launch")`, `validate_train_mix(mix)` (family+regime+
  source), `train_quotas(mix, count)`.
- **`sim/train_gen.py`** — `build_training_cache(mix, n_train, n_val, seed, strength, specs, path,
  val_mode=VAL_MODE_STANDARD, val_mix=None, on_progress=None) → manifest|None`
  (`on_progress(done, total)` returning `False` **cancels**, and a cancel writes NOTHING);
  `windows_per_traj(n_ticks, seq_len=100, stride=None)` (default stride `seq_len//2`);
  `VAL_MODE_STANDARD="standard"`, `VAL_MODE_NEW_SHAPES="new_shapes"`, `VAL_MODE_DIFFERENT_MIX="different_mix"`,
  `VAL_MODES`, `SECONDS_PER_TRAJ=0.061`, `WARMUP_STEPS=200`, `SEQ_LEN=100`, `MIN_TICKS=300`,
  `draw_training_sample`, `_PRESET_N` (from scenario_spec, =600). Measured `.pt` bytes/tick = **78.3**.
- **`sim/dataset_gen.py`** — `preview_sample(family, source, seed, strength, specs, params_gt) → v_leader`,
  built on `draw_scenario` which handles `built`/`preset`/`generator` and **raises `ValueError` for any other
  family** (so `cut_in` must be mapped — see Task 2). `GENERATOR_PROFILES`.
- **`sim/ui/app.py`** — `DatasetPage(params_gt=_PARAMS_GT)` at :189, `_dataset_page._on_generate =
  self._run_dataset` at :190, page 4 of `_mode_stack` at :196. `set_mode(4)` (:386-388) calls
  `self._dataset_page.set_sources(self._built_specs(), [...])`. `_busy_controls()` (:399-401) returns
  `(meso run, meso ring, _mode_sel, _dataset_page._gen_btn)`. `_busy`/`_done_busy` (:403-417) disable those +
  wait cursor. `_dataset_progress(i, total)` (:425-430) sets the progress bar + `QApplication.processEvents()`
  and **returns None**. `_run_dataset` (:432-441) calls `generate_dataset(page.mix(), page.count(), page.seed(),
  page.strength(), page.k(), page.formats(), page.out_dir(), self._built_specs(), _PARAMS_GT,
  on_progress=self._dataset_progress)` inside `_busy`/`try…finally _done_busy`. `_PARAMS_GT` is the app's params.
- **`sim/ui/theme.py`** — `apply_dark_theme(app)`.

### Churn — enumerated across ALL files (the B1 lesson: a missed file reddens the FULL suite)

Tests that reach into `DatasetPage`/app dataset internals — **both** must be checked when Tasks 5-6 touch the
page and the app:
- `tests/test_sim_dataset_page.py` — the page's own tests (mix via `p._mix._rows`, controls, size).
- `tests/test_sim_app_lifecycle.py` — reaches `win._dataset_page._mix.specs()` (:103,108) and
  `win._dataset_page._mix._rows[0]` (:121-123), plus `_gen_btn`, `_run_dataset`, `_busy_controls`. **B1's plan
  missed this file and the full suite caught it (2 reds).** Any change to `DatasetPage`'s structure or
  `_run_dataset` must keep these passing OR retarget them in the same task.
- `tests/test_sim_ui_smoke.py` — builds `SimApp` and drives the 5th mode through the app; the real integration
  proof.

### The approved mock

`scratchpad/mock_7b_training.png` is the agreed Training layout (Qt widgets + real dark theme). ⚠️ It **predates
the time constraint** and shows neither **Cancel** nor **ETA** — this plan adds both (Tasks 4 and 6). Otherwise
it is the target: destination toggle, regime column, `cut_in` family, window-share next to the quota, train/val
counts, validation selector, jitter caveat reworded, frequency disabled with its reason, `.pt`, size estimate,
the `python train.py --data_cache …` line.

---

## File structure

| File | Responsibility |
|---|---|
| `sim/train_gen.py` **(add 1 pure helper)** | `training_windows(family, source, specs, stride)` — the window count one training trajectory of this family/source yields, so the UI's honesty column can't drift from the engine's length rules. |
| `sim/ui/mix_table.py` **(modify)** | `with_regime=True`: a regime combo per row, the `cut_in` family, `mix()` → `TrainMixEntry`, a live **→ finestre** column, the eye mapping `cut_in`→`generator`. `with_regime=False` unchanged. |
| `sim/ui/training_panel.py` **(new)** | The Training destination: a training `MixTable` + controls (seed, train/val counts, validation selector + val `MixTable` for mode 3, jitter reworded, frequency disabled, `.pt`, size, command line, Generate + Cancel + progress + ETA). Getters the app reads. |
| `sim/ui/dataset_page.py` **(modify)** | A destination toggle + `QStackedWidget` of [analysis content (today), `TrainingPanel`]. Exposes `destination()` and the training getters. |
| `sim/ui/app.py` **(modify)** | `_run_dataset` routes by destination; a `_cancel_requested` flag; `_dataset_progress` returns the flag; Cancel stays out of `_busy_controls`; live ETA. |

**Design decisions (locked, with rationale):**
- **Three `MixTable` instances, not one shape-shifting table.** Analysis (`with_regime=False`, today's `self._mix`)
  and training (`with_regime=True`) are separate instances the toggle shows/hides; validation mode 3 adds a
  third (val, `with_regime=True`). Rationale: `with_regime` is fixed at construction (B1); separate instances
  are simpler than mutating a live table, and "train and val are two instances" is exactly why B1 extracted it.
- **`TrainingPanel` is its own widget** (like B1 extracted `MixTable`) — keeps `DatasetPage` a thin toggle+stack
  shell and makes the training controls testable alone.
- **The window-share length rule lives in the engine** (`training_windows`), not the UI — DRY, one source of
  truth for "how long is a training trajectory".

---

### Task 1: `training_windows` — the engine's length rule for the honesty column

**Files:**
- Modify: `sim/train_gen.py` (append a pure function)
- Modify: `tests/test_sim_train_gen.py` (append)

- [ ] **Step 0: Confirm the baseline**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulator"
git log --oneline -1 && git status --short
```
Expected: HEAD `7968b95f`, clean tree.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_sim_train_gen.py`)

```python
def test_training_windows_matches_the_real_length_rule():
    """The UI's 'window share' column must equal what training actually cuts. A generator trajectory is
    1200 ticks; after the 200-tick warmup strip, 1000; at the train stride (seq_len//2=50) that is 19 windows
    (windows_per_traj(1000, stride=50))."""
    from sim.train_gen import training_windows, windows_per_traj, WARMUP_STEPS
    # generator / cut_in: fixed 1200 - warmup
    assert training_windows("generator", "sinusoidal", {}, stride=50) == windows_per_traj(1200 - WARMUP_STEPS, stride=50)
    assert training_windows("cut_in", "sinusoidal", {}, stride=50) == windows_per_traj(1200 - WARMUP_STEPS, stride=50)


def test_training_windows_uses_the_built_scenario_length():
    from sim.train_gen import training_windows, windows_per_traj, WARMUP_STEPS
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    specs = {"mine": ScenarioSpec(name="mine", blocks=(Block("const", 600, {"v": 15.0}),),
                                  style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)}
    # built: sum(blocks)=600, minus warmup 200 = 400; preset: _PRESET_N=600 minus warmup = 400
    assert training_windows("built", "mine", specs, stride=50) == windows_per_traj(600 - WARMUP_STEPS, stride=50)
    assert training_windows("preset", "hard_brake", specs, stride=50) == windows_per_traj(600 - WARMUP_STEPS, stride=50)


def test_training_windows_is_zero_for_a_too_short_built_scenario():
    """A built scenario shorter than warmup+seq_len yields no windows -- the column must show 0, not a negative."""
    from sim.train_gen import training_windows
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    specs = {"tiny": ScenarioSpec(name="tiny", blocks=(Block("const", 250, {"v": 15.0}),),
                                  style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)}
    assert training_windows("built", "tiny", specs, stride=50) == 0
```

- [ ] **Step 2: Run — expect FAIL**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_train_gen.py -q -p no:cacheprovider
```
Expected: FAIL, `ImportError: cannot import name 'training_windows'`.

- [ ] **Step 3: Implement** — append to `sim/train_gen.py`:

```python
def training_windows(family, source, specs, stride=None):
    """How many CFDataset windows one training trajectory of this family/source yields, AFTER the warmup strip.

    The engine owns the length rule so the UI's 'window share' column cannot drift from what training cuts:
    generator/cut_in run the fixed SIM_DURATION path (1200 ticks); built is its blocks' sum; preset is _PRESET_N
    (600). All lose WARMUP_STEPS. Below one window the count is 0 (a too-short built scenario)."""
    if family == "built":
        raw = sum(int(b.ticks) for b in specs[source].blocks) if source in specs else 0
    elif family == "preset":
        raw = _PRESET_N
    else:                                   # generator / cut_in: the fixed-duration path
        raw = int(SIM_DURATION / DT)
    return windows_per_traj(max(raw - WARMUP_STEPS, 0), stride=stride)
```

Add `SIM_DURATION` to the `from config import ...` line at the top of `sim/train_gen.py` (it currently imports
`DT, WARMUP_DURATION` — add `SIM_DURATION`).

- [ ] **Step 4: Run — expect PASS**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_train_gen.py -q -p no:cacheprovider
```
Expected: all pass (17 prior + 3 new = 20).

- [ ] **Step 5: Prove the sabotage bites**

In `training_windows`, change `max(raw - WARMUP_STEPS, 0)` to `raw` (drop the warmup strip). Run:
`test_training_windows_matches_the_real_length_rule` must FAIL (1000-tick count vs 1200-tick count differ).
Revert and re-run green.

- [ ] **Step 6: Commit**

```bash
git add sim/train_gen.py tests/test_sim_train_gen.py
git commit -m "feat(sim): training_windows -- la regola di lunghezza per la colonna quota-finestre

Il conteggio finestre di una traiettoria di training (dopo lo strip del
warmup) vive nel motore, non nella UI: la colonna d'onesta' non puo'
divergere da cio' che il training taglia. built=somma blocchi, preset=600,
generator/cut_in=1200; tutti meno WARMUP_STEPS; <1 finestra -> 0."
```

---

### Task 2: `MixTable(with_regime=True)` — the regime column, `cut_in`, TrainMixEntry, window-share

**Files:**
- Modify: `sim/ui/mix_table.py`
- Modify: `tests/test_sim_mix_table.py` (append)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_sim_mix_table.py`)

```python
def _train_table(qapp, specs=None):
    t = MixTable(params_gt=_PG, strength=lambda: 0.25, with_regime=True)
    t.set_sources(specs if specs is not None else _specs(), ["following", "hard_brake"])
    return t


def test_with_regime_adds_the_cut_in_family_and_a_regime_column(qapp):
    from sim.train_mix import FAMILIES_TRAIN, REGIMES
    t = _train_table(qapp)
    r = t._rows[0]
    assert [r.family.itemText(i) for i in range(r.family.count())] == list(FAMILIES_TRAIN)   # cut_in is here
    assert r.regime is not None                                                              # the extra combo
    assert [r.regime.itemText(i) for i in range(r.regime.count())] == list(REGIMES)


def test_with_regime_mix_returns_TrainMixEntry(qapp):
    from sim.train_mix import TrainMixEntry, validate_train_mix
    t = _train_table(qapp)
    t._rows[0].family.setCurrentText("generator")
    t._rows[0].source.setCurrentText("sinusoidal")
    t._rows[0].regime.setCurrentText("launch")
    t._rows[0].weight.setValue(100.0)
    mix = t.mix()
    assert mix == [TrainMixEntry("generator", "sinusoidal", "launch", 100.0)]
    validate_train_mix(mix)                       # the engine accepts what the table produces


def test_the_window_share_column_is_live(qapp):
    from sim.train_gen import training_windows
    t = _train_table(qapp)
    t.set_count(100)
    t._rows[0].family.setCurrentText("generator")
    t._rows[0].source.setCurrentText("sinusoidal")
    t._rows[0].weight.setValue(100.0)
    # 100 trajectories * training_windows(generator) each
    expected = 100 * training_windows("generator", "sinusoidal", t.specs(), stride=50)
    assert t._rows[0].windows.text() == str(expected)


def test_the_analysis_table_has_no_regime_column(qapp):
    """with_regime=False rows carry no regime combo -- the 3-field mix is untouched."""
    t = _table(qapp)                              # the with_regime=False helper from earlier
    assert t._rows[0].regime is None


def test_the_eye_maps_cut_in_to_the_leader_profile(qapp):
    """preview_sample raises for family='cut_in' (draw_scenario knows only built/preset/generator). A cut_in row's
    source IS a generator leader profile (leader A), so the eye previews it as 'generator' and says so."""
    from sim.dataset_gen import preview_sample
    t = _train_table(qapp)
    r = t._rows[0]
    r.family.setCurrentText("cut_in")
    r.source.setCurrentText("sinusoidal")
    t.show_preview(r)                             # must NOT raise
    expected = preview_sample("generator", "sinusoidal", t.PREVIEW_SEED, 0.25, t._specs, t._params_gt)
    assert np.allclose(t._popup_panel._curve.getData()[1], expected)
    assert "leader A" in t._popup_title.text()
```

- [ ] **Step 2: Run — expect FAIL**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_mix_table.py -q -p no:cacheprovider
```
Expected: FAIL — `NotImplementedError: with_regime is B2...` (the constructor still refuses True).

- [ ] **Step 3: Implement** in `sim/ui/mix_table.py`. Read the file first. Make these edits with Edit:

**3a.** Extend the `_Row` dataclass to carry the optional regime combo and the window-share label:

```python
@dataclass
class _Row:
    frame: QFrame
    family: QComboBox
    source: QComboBox
    eye: QLabel
    weight: QDoubleSpinBox
    quota: QLabel
    kill: QPushButton
    regime: QComboBox = None      # only in with_regime mode
    windows: QLabel = None        # only in with_regime mode: the window-share column
```

**3b.** Remove the `NotImplementedError` guard and store the mode + the family/regime vocabularies:

```python
    def __init__(self, params_gt, strength, with_regime=False):
        super().__init__()
        self._params_gt = params_gt
        self._strength = strength
        self._with_regime = with_regime
        if with_regime:
            from sim.train_mix import FAMILIES_TRAIN, REGIMES
            self._families, self._regimes = list(FAMILIES_TRAIN), list(REGIMES)
        else:
            self._families, self._regimes = list(FAMILIES), None
        self._specs = {}
        ...
```

Replace every later use of the module-level `FAMILIES` in this class with `self._families`
(`_sync_family_enabled`'s `self._families.index("built")` and `add_row`'s `family.addItems(self._families)`).

**3c.** The header gains the regime + window columns in regime mode. Replace the header build:

```python
        head = QHBoxLayout()
        cols = (("famiglia", "sorgente", "", "regime", "peso %", "→ traiettorie", "→ finestre", "")
                if with_regime else ("famiglia", "sorgente", "", "peso %", "→ traiettorie", ""))
        for t in cols:
            lbl = QLabel(t); lbl.setStyleSheet("color:#8b949e"); head.addWidget(lbl)
```

**3d.** `add_row` builds the regime combo + the window label in regime mode:

```python
    def add_row(self):
        frame = QFrame()
        lay = QHBoxLayout(frame); lay.setContentsMargins(0, 0, 0, 0)
        family = QComboBox(); family.addItems(self._families)
        source = QComboBox()
        eye = QLabel(_EYE); eye.setToolTip("anteprima di un campione di questa sorgente")
        eye.setAttribute(Qt.WA_Hover, True); eye.installEventFilter(self)
        regime = QComboBox() if self._with_regime else None
        if regime is not None:
            regime.addItems(self._regimes)
        weight = QDoubleSpinBox(); weight.setRange(0.0, 100.0); weight.setDecimals(1)
        quota = QLabel("0")
        windows = QLabel("0") if self._with_regime else None
        if windows is not None:
            windows.setStyleSheet("color:#6e7681")
        kill = QPushButton("✕"); kill.setFixedWidth(28)
        widgets = ([family, source, eye, regime, weight, quota, windows, kill] if self._with_regime
                   else [family, source, eye, weight, quota, kill])
        for w in widgets:
            lay.addWidget(w)
        row = _Row(frame, family, source, eye, weight, quota, kill, regime, windows)
        self._rows.append(row)
        self._rows_box.addWidget(frame)
        family.currentTextChanged.connect(lambda _t, r=row: (self._reload_sources(r), self._refresh()))
        weight.valueChanged.connect(self._refresh)
        if regime is not None:
            regime.currentTextChanged.connect(self._refresh)
        kill.clicked.connect(lambda _c=False, r=row: self.remove_row(r))
        self._sync_family_enabled(row)
        self._reload_sources(row)
        self._refresh()
        return row
```

**3e.** `mix()` returns `TrainMixEntry` in regime mode:

```python
    def mix(self):
        if self._with_regime:
            from sim.train_mix import TrainMixEntry
            return [TrainMixEntry(r.family.currentText(), r.source.currentText(),
                                  r.regime.currentText(), float(r.weight.value())) for r in self._rows]
        return [MixEntry(r.family.currentText(), r.source.currentText(), float(r.weight.value()))
                for r in self._rows]
```

**3f.** `_refresh` fills the window column in regime mode (train stride = `SEQ_LEN//2`):

```python
    def _refresh(self):
        ok = self.is_valid()
        self._total_lbl.setText(f"totale {self.total():.0f}% {'✓' if ok else '✗'}")
        self._total_lbl.setStyleSheet(f"color:{'#2e8b57' if ok else '#d1495b'}")
        if ok:
            from sim.dataset_mix import quotas as _quotas
            fams = getattr(self, "_families", None)
            qs = _quotas(self.mix(), self._count, fams) if self._with_regime else _quotas(self.mix(), self._count)
            for r, q in zip(self._rows, qs):
                r.quota.setText(str(q))
                if r.windows is not None:
                    from sim.train_gen import training_windows
                    w = q * training_windows(r.family.currentText(), r.source.currentText(),
                                             self._specs, stride=self._TRAIN_STRIDE)
                    r.windows.setText(str(w))
        else:
            for r in self._rows:
                r.quota.setText("—")
                if r.windows is not None:
                    r.windows.setText("—")
        self.changed.emit()
```

Add the class constant near `PREVIEW_SEED`:
```python
    _TRAIN_STRIDE = 50          # train uses seq_len//2 (train.py:1467); the val table shows the val stride, set per instance
```

> Note: `quotas`/`train_quotas` both validate. In regime mode the mix is `TrainMixEntry` and needs the
> `FAMILIES_TRAIN` vocabulary — `_quotas(mix, count, self._families)` passes it (7a's `quotas` takes the additive
> `families=` param). `is_valid()` already only checks the total and non-empty sources, so it works for both.

**3g.** `is_valid` in regime mode must also accept `cut_in`'s empty-regime never happens (the combo always has a
value), so no change is needed there. But the family-source cascade must offer generator profiles for `cut_in`
too. In `_sources_for`, `cut_in` falls into the `else` branch (returns `GENERATOR_PROFILES`) — confirm the
existing `else: return list(GENERATOR_PROFILES)` covers it (it does, since only built/preset are special-cased).

**3h.** The eye maps `cut_in`→`generator` (preview_sample can't take cut_in):

```python
    def show_preview(self, row):
        fam, src = row.family.currentText(), row.source.currentText()
        if not src:
            return
        eye_fam = "generator" if fam == "cut_in" else fam
        v = preview_sample(eye_fam, src, self.PREVIEW_SEED, self._strength(), self._specs, self._params_gt)
        self._popup_panel.set_scenario(v)
        suffix = " — leader A" if fam == "cut_in" else ""
        self._popup_title.setText(f"{fam} · {src} — campione (seed {self.PREVIEW_SEED}){suffix}")
        self._popup.adjustSize()
        self._popup.move(row.eye.mapToGlobal(row.eye.rect().bottomLeft()))
        self._popup.show()
```

- [ ] **Step 4: Run — expect PASS**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_mix_table.py -q -p no:cacheprovider
```
Expected: all pass (the prior with_regime=False tests + the 5 new regime tests).

- [ ] **Step 5: Prove the sabotage bites**

In `mix()`, make the regime branch return `MixEntry(...)` (3-field, dropping the regime) instead of
`TrainMixEntry`. Run: `test_with_regime_mix_returns_TrainMixEntry` must FAIL (wrong type / missing regime).
Revert and re-run green.

- [ ] **Step 6: Commit**

```bash
git add sim/ui/mix_table.py tests/test_sim_mix_table.py
git commit -m "feat(sim-ui): MixTable with_regime -- colonna regime, famiglia cut_in, TrainMixEntry, quota-finestre

with_regime=True: una riga dice famiglia/sorgente/regime/peso e mix()
ritorna TrainMixEntry; la colonna '→ finestre' mostra, dal vero
training_windows del motore, cio' che la rete vedra' (train stride 50).
L'occhio del cut_in mappa su 'generator' (leader A) perche' preview_sample
non conosce cut_in. with_regime=False resta il mix a 3 campi del 7a."
```

---

### Task 3: `TrainingPanel` — the training destination widget (core)

**Files:**
- Create: `sim/ui/training_panel.py`, `tests/test_sim_training_panel.py`

- [ ] **Step 1: Write the failing tests** — create `tests/test_sim_training_panel.py`:

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

from sim.ui.training_panel import TrainingPanel                 # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _panel(qapp):
    p = TrainingPanel(params_gt=_PG)
    p.set_sources({}, ["following", "hard_brake"])
    return p


def test_the_panel_exposes_the_engine_arguments(qapp):
    from sim.train_mix import TrainMixEntry
    p = _panel(qapp)
    p._mix._rows[0].family.setCurrentText("generator")
    p._mix._rows[0].source.setCurrentText("sinusoidal")
    p._mix._rows[0].regime.setCurrentText("highway")
    p._mix._rows[0].weight.setValue(100.0)
    p._n_train.setValue(5000); p._n_val.setValue(500); p._seed.setValue(7)
    assert p.mix() == [TrainMixEntry("generator", "sinusoidal", "highway", 100.0)]
    assert p.n_train() == 5000 and p.n_val() == 500 and p.seed() == 7
    assert 0.0 <= p.strength() <= 1.0


def test_the_frequency_is_shown_disabled_with_its_reason(qapp):
    p = _panel(qapp)
    assert not p._freq.isEnabled()                     # decimation is off for training
    assert "PINN" in p._freq_note.text() or "PINN" in p._freq.toolTip()


def test_the_format_is_pt(qapp):
    p = _panel(qapp)
    assert ".pt" in p._fmt_lbl.text()                  # the training destination writes the .pt cache, nothing else


def test_the_jitter_caveat_is_reworded_for_training(qapp):
    p = _panel(qapp)
    assert "LEADER" in p._jitter_note.text() and "params" in p._jitter_note.text()


def test_the_size_estimate_uses_the_pt_bytes_per_tick(qapp):
    p = _panel(qapp)
    p._mix._rows[0].family.setCurrentText("generator")
    p._mix._rows[0].source.setCurrentText("sinusoidal")
    p._mix._rows[0].regime.setCurrentText("highway")
    p._mix._rows[0].weight.setValue(100.0)
    p._n_train.setValue(10); p._n_val.setValue(2)
    assert "MB" in p._size_lbl.text()                  # a live estimate appears when the mix is valid


def test_the_command_line_names_the_cache(qapp):
    p = _panel(qapp)
    p._out_dir.setText(r"D:\ds\cache.pt")
    assert "train.py --data_cache" in p._cmd_lbl.text() and "cache.pt" in p._cmd_lbl.text()


def test_the_eta_is_shown_before_the_click(qapp):
    p = _panel(qapp)
    p._n_train.setValue(5000); p._n_val.setValue(500)
    # 5500 * SECONDS_PER_TRAJ ~ 335 s ~ 5-6 min: the label mentions minutes
    assert "min" in p._eta_lbl.text().lower()
```

- [ ] **Step 2: Run — expect FAIL** (`ModuleNotFoundError: No module named 'sim.ui.training_panel'`)

- [ ] **Step 3: Create `sim/ui/training_panel.py`**

```python
"""The Training destination: a MixTable(with_regime) + the training controls -> the .pt cache train.py reads.

Its own widget (like B1 extracted MixTable) so DatasetPage stays a thin toggle+stack shell and the training
controls are testable alone. The panel owns WIDGETS and exposes getters; the APP owns the run and reaches
build_training_cache with them. The validation selector and the mode-3 val table are added in Task 4."""
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QSpinBox,
                               QSlider, QVBoxLayout, QWidget)
from PySide6.QtCore import Qt

from sim.train_gen import SECONDS_PER_TRAJ, training_windows
from sim.ui.mix_table import MixTable

_PT_BYTES_PER_TICK = 78.3        # measured at the engine's functional-verify (the .pt cache)


class TrainingPanel(QWidget):
    def __init__(self, params_gt):
        super().__init__()
        self._params_gt = params_gt
        self._on_generate = None

        self._mix = MixTable(params_gt, strength=self.strength, with_regime=True)
        self._mix.changed.connect(self._refresh)

        self._seed = QSpinBox(); self._seed.setRange(0, 2**31 - 1); self._seed.setValue(42)
        self._n_train = QSpinBox(); self._n_train.setRange(1, 1000000); self._n_train.setValue(5000)
        self._n_val = QSpinBox(); self._n_val.setRange(1, 1000000); self._n_val.setValue(500)
        for s in (self._n_train, self._n_val):
            s.valueChanged.connect(lambda _v: (self._mix.set_count(self._n_train.value()), self._refresh()))

        self._jitter = QSlider(Qt.Horizontal); self._jitter.setRange(0, 100); self._jitter.setValue(25)
        self._jitter.setFixedWidth(120)
        self._jitter_lbl = QLabel("25%")
        self._jitter.valueChanged.connect(lambda v: (self._jitter_lbl.setText(f"{v}%"), self._refresh()))
        self._jitter_note = QLabel("⚠ governa il LEADER (built/preset), non i params: quelli sono le etichette e li dà il regime")
        self._jitter_note.setStyleSheet("color:#e8a33d")

        self._freq = QComboBox(); self._freq.addItems(["10 Hz (fissa)"]); self._freq.setEnabled(False)
        self._freq.setToolTip("DT=0.1 s è dentro la fisica E dentro la PINN loss (a_l per differenze finite su DT).\n"
                              "Un training set decimato sarebbe sbagliato in silenzio.")
        self._freq_note = QLabel("bloccata: DT è dentro la PINN loss"); self._freq_note.setStyleSheet("color:#6e7681")
        self._fmt_lbl = QLabel(".pt (cache train.py)")

        self._size_lbl = QLabel()
        self._eta_lbl = QLabel(); self._eta_lbl.setStyleSheet("color:#6e7681")
        self._out_dir = QLineEdit(r"cache.pt")
        self._cmd_lbl = QLabel(); self._cmd_lbl.setStyleSheet("font-family:Consolas,monospace; color:#6e7681")
        self._out_dir.textChanged.connect(self._refresh)

        self._gen_btn = QPushButton("Genera")
        self._gen_btn.clicked.connect(lambda: self._on_generate() if self._on_generate else None)
        self._cancel_btn = QPushButton("Annulla"); self._cancel_btn.setEnabled(False)
        self._progress = QProgressBar(); self._progress.setRange(0, 100); self._progress.setValue(0)

        root = QVBoxLayout(self)
        root.addWidget(QLabel("MIX (training)"))
        root.addWidget(self._mix)
        c1 = QHBoxLayout()
        for w in (QLabel("seed"), self._seed, QLabel("train"), self._n_train, QLabel("val"), self._n_val,
                  QLabel("jitter"), self._jitter, self._jitter_lbl, self._jitter_note):
            c1.addWidget(w)
        c1.addStretch(1)
        c2 = QHBoxLayout()
        for w in (QLabel("frequenza"), self._freq, self._freq_note, QLabel("formato"), self._fmt_lbl):
            c2.addWidget(w)
        c2.addStretch(1); c2.addWidget(self._size_lbl)
        out = QHBoxLayout()
        for w in (QLabel("file"), self._out_dir):
            out.addWidget(w)
        run = QHBoxLayout()
        for w in (self._gen_btn, self._cancel_btn, self._progress, self._eta_lbl):
            run.addWidget(w)
        for lay in (c1, c2, out, run):
            root.addLayout(lay)
        root.addWidget(self._cmd_lbl)
        root.addStretch(1)
        self._refresh()

    # ---- sources / getters (the app reads these) ----
    def set_sources(self, specs, preset_names):
        self._mix.set_sources(specs, preset_names)

    def mix(self):
        return self._mix.mix()

    def n_train(self):
        return int(self._n_train.value())

    def n_val(self):
        return int(self._n_val.value())

    def seed(self):
        return int(self._seed.value())

    def strength(self):
        return self._jitter.value() / 100.0

    def out_path(self):
        return self._out_dir.text().strip()

    # ---- estimates ----
    def _estimate_bytes(self):
        """A rough .pt size. TICKS drive the file: each trajectory stores raw(N,7)+x+y+mask; the engine measured
        78.3 B per stored tick. Sum the post-warmup ticks across train + val at their quotas."""
        from sim.train_gen import WARMUP_STEPS, _PRESET_N
        from config import SIM_DURATION, DT
        specs = self._mix.specs()
        total_ticks = 0
        # train + val trajectories, at their quotas, each ~ (length - warmup) ticks stored
        for count in (self.n_train(), self.n_val()):
            from sim.train_mix import train_quotas
            for e, q in zip(self.mix(), train_quotas(self.mix(), count)):
                if e.family == "built":
                    raw = sum(int(b.ticks) for b in specs[e.source].blocks) if e.source in specs else 0
                elif e.family == "preset":
                    raw = _PRESET_N
                else:
                    raw = int(SIM_DURATION / DT)
                total_ticks += q * max(raw - WARMUP_STEPS, 0)
        return total_ticks * _PT_BYTES_PER_TICK

    def eta_seconds(self):
        return (self.n_train() + self.n_val()) * SECONDS_PER_TRAJ

    # ---- refresh ----
    def _refresh(self):
        ok = self._mix.is_valid()
        self._gen_btn.setEnabled(ok)
        eta = self.eta_seconds()
        self._eta_lbl.setText(f"≈ {eta / 60:.0f} min" if eta >= 60 else f"≈ {eta:.0f} s")
        path = self.out_path()
        self._cmd_lbl.setText(f"poi:  python train.py --data_cache {path}" if path else "")
        if ok:
            self._size_lbl.setText(f"dimensione stimata  ≈ {self._estimate_bytes() / 1e6:.0f} MB")
        else:
            self._size_lbl.setText("dimensione stimata  —")
```

> The default `_out_dir` text is `cache.pt` so `test_the_command_line_names_the_cache` and the `.pt` framing hold
> out of the box. `_fmt_lbl` is the fixed label `.pt (cache train.py)` — the training destination writes only the
> torch cache, so there are no format checkboxes here (that is the analysis destination).

- [ ] **Step 4: Run — expect PASS** (`7 passed`)

- [ ] **Step 5: Prove the sabotage bites**

In `eta_seconds`, return `0.0` always. Run: `test_the_eta_is_shown_before_the_click` must FAIL (`"min"` absent —
0 s shows as seconds). Revert and re-run green.

- [ ] **Step 6: Commit**

```bash
git add sim/ui/training_panel.py tests/test_sim_training_panel.py
git commit -m "feat(sim-ui): TrainingPanel -- il mix training + i controlli (senza validazione)

Widget a se' (come MixTable in B1): MixTable(with_regime) + seed, train/val,
jitter col caveat riformulato, frequenza DISABILITATA col motivo, formato
.pt, stima MB dai 78.3 B/tick misurati, riga comando, ETA da SECONDS_PER_TRAJ.
Il selettore di validazione a 3 modi arriva col Task 4."
```

---

### Task 4: The validation selector — 3 modes + live warning + the mode-3 val table

**Files:**
- Modify: `sim/ui/training_panel.py`
- Modify: `tests/test_sim_training_panel.py` (append)

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_the_validation_selector_has_three_modes_and_maps_to_the_engine(qapp):
    from sim.train_gen import VAL_MODE_STANDARD, VAL_MODE_NEW_SHAPES, VAL_MODE_DIFFERENT_MIX
    p = _panel(qapp)
    assert p._val_sel.count() == 3
    p._val_sel.setCurrentIndex(0); assert p.val_mode() == VAL_MODE_STANDARD
    p._val_sel.setCurrentIndex(1); assert p.val_mode() == VAL_MODE_NEW_SHAPES
    p._val_sel.setCurrentIndex(2); assert p.val_mode() == VAL_MODE_DIFFERENT_MIX


def test_each_mode_shows_its_consequence(qapp):
    from sim.train_gen import VAL_MODE_STANDARD, VAL_MODE_NEW_SHAPES, VAL_MODE_DIFFERENT_MIX
    p = _panel(qapp)
    seen = set()
    for i in range(3):
        p._val_sel.setCurrentIndex(i)
        seen.add(p._val_note.text())
    assert len(seen) == 3                          # each mode states a different consequence
    p._val_sel.setCurrentIndex(2)
    assert "overfitting" in p._val_note.text().lower()   # mode 3's strong warning


def test_the_val_mix_table_appears_only_in_mode_3(qapp):
    p = _panel(qapp)
    p._val_sel.setCurrentIndex(0); assert not p._val_mix.isVisible()
    p._val_sel.setCurrentIndex(2); assert p._val_mix.isVisible()
    p._val_sel.setCurrentIndex(1); assert not p._val_mix.isVisible()


def test_val_mix_is_returned_only_in_mode_3(qapp):
    p = _panel(qapp)
    p._val_sel.setCurrentIndex(0)
    assert p.val_mix() is None                     # standard/new_shapes reuse the train mix -> engine wants None
    p._val_sel.setCurrentIndex(2)
    assert p.val_mix() is not None                 # mode 3 supplies a separate mix
```

- [ ] **Step 2: Run — expect FAIL** (`AttributeError: 'TrainingPanel' object has no attribute '_val_sel'`)

- [ ] **Step 3: Implement** — in `sim/ui/training_panel.py`, add the selector + the val table. In `__init__`,
after the mix and before the run row, add:

```python
        from sim.train_gen import VAL_MODE_STANDARD, VAL_MODE_NEW_SHAPES, VAL_MODE_DIFFERENT_MIX
        self._val_modes = [VAL_MODE_STANDARD, VAL_MODE_NEW_SHAPES, VAL_MODE_DIFFERENT_MIX]
        self._val_sel = QComboBox()
        self._val_sel.addItems(["Standard (stesso mix, seed S+1)",
                                "Forme nuove (nessuna condivisa col train)",
                                "Mix diverso (sonda fuori-distribuzione)"])
        self._val_note = QLabel(); self._val_note.setWordWrap(True); self._val_note.setStyleSheet("color:#6e7681")
        self._val_mix = MixTable(self._params_gt, strength=self.strength, with_regime=True)
        self._val_mix.hide()
        self._val_sel.currentIndexChanged.connect(self._on_val_mode)
```

Add the val selector row + note + the (hidden) val table to the layout (place the `QLabel("validazione")` row and
`self._val_note` and `self._val_mix` after the `c1` jitter row, before `c2`):

```python
        val_row = QHBoxLayout()
        for w in (QLabel("validazione"), self._val_sel):
            val_row.addWidget(w)
        val_row.addStretch(1)
        # inserted into root after c1: root.addLayout(val_row); root.addWidget(self._val_note); root.addWidget(self._val_mix)
```

Wire the layout so `val_row`, `self._val_note`, `self._val_mix` are added to `root` right after `c1`. Add the
handler + the getters:

```python
    _VAL_NOTES = {
        0: "il divario train↔val misura overfitting (due campioni i.i.d., seed S e S+1).",
        1: "↳ cancello VERIFICATO: nessun v_leader del val è copia di uno del train; se il mix ne produce, "
           "la generazione si ferma e dice quale.",
        2: "⚠ il divario NON misura più overfitting: val_loss sceglie il checkpoint, guida l'early-stop e "
           "l'LR. È una sonda fuori-distribuzione, da scegliere sapendolo.",
    }

    def _on_val_mode(self, i):
        self._val_note.setText(self._VAL_NOTES[i])
        self._val_mix.setVisible(i == 2)
        self._refresh()

    def val_mode(self):
        return self._val_modes[self._val_sel.currentIndex()]

    def val_mix(self):
        from sim.train_gen import VAL_MODE_DIFFERENT_MIX
        return self._val_mix.mix() if self.val_mode() == VAL_MODE_DIFFERENT_MIX else None
```

Call `self._on_val_mode(0)` at the end of `__init__` (before the final `self._refresh()`) so the note starts
populated. Also route the val table's sources: in `set_sources`, add `self._val_mix.set_sources(specs, preset_names)`.

- [ ] **Step 4: Run — expect PASS** (`11 passed` in the file)

- [ ] **Step 5: Prove the sabotage bites**

In `val_mix()`, drop the mode check — always `return self._val_mix.mix()`. Run:
`test_val_mix_is_returned_only_in_mode_3` must FAIL (standard mode would return a mix instead of None, which the
engine reads as "different_mix"). Revert and re-run green.

- [ ] **Step 6: Commit**

```bash
git add sim/ui/training_panel.py tests/test_sim_training_panel.py
git commit -m "feat(sim-ui): il selettore di validazione a 3 modi + la tabella val del modo 3

standard/forme-nuove/mix-diverso, ognuno con la sua conseguenza a video;
val_mode() mappa sulle costanti del motore; il modo 3 mostra una SECONDA
MixTable e val_mix() la ritorna (None negli altri due -> il motore riusa
il train mix). Il modo 3 avvisa che il divario non misura piu' overfitting."
```

---

### Task 5: `DatasetPage` — the destination toggle + stack

**Files:**
- Modify: `sim/ui/dataset_page.py`
- Modify: `tests/test_sim_dataset_page.py` (append)

- [ ] **Step 0: Churn pre-check — enumerate EVERY test reaching the page/app dataset internals**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulator"
git grep -lnE "_dataset_page|DatasetPage|_run_dataset" -- 'tests/*.py'
```
Expected: `tests/test_sim_dataset_page.py` and `tests/test_sim_app_lifecycle.py`. **This task must keep BOTH
green** (Task 6 handles the app-lifecycle ones if `_run_dataset` changes; this task keeps the page's own tests
green by preserving the analysis getters). The B1 lesson: a missed test file reddens the FULL suite at the end.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_sim_dataset_page.py`)

```python
def test_the_destination_toggle_switches_analysis_and_training(qapp):
    from sim.ui.training_panel import TrainingPanel
    p = _page(qapp)
    assert p.destination() == "analisi"                    # default
    assert p._stack.currentIndex() == 0
    p._dest_training.setChecked(True)
    assert p.destination() == "training"
    assert p._stack.currentIndex() == 1
    assert isinstance(p._training, TrainingPanel)


def test_the_analysis_getters_still_work(qapp):
    """The analysis destination is unchanged -- the app's generate_dataset path must keep reading these."""
    p = _page(qapp)
    p._mix._rows[0].family.setCurrentText("preset")
    p._mix._rows[0].source.setCurrentText("hard_brake")
    p._mix._rows[0].weight.setValue(100.0)
    from sim.dataset_mix import MixEntry
    assert p.mix() == [MixEntry("preset", "hard_brake", 100.0)]
    assert p.count() >= 1 and 0.0 <= p.strength() <= 1.0


def test_set_sources_reaches_both_tables(qapp):
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    specs = {"mine": ScenarioSpec(name="mine", blocks=(Block("const", 400, {"v": 15.0}),),
                                  style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)}
    p = _page(qapp, specs=specs)
    assert "mine" in p._mix.specs()                        # analysis table
    assert "mine" in p._training._mix.specs()              # training table
```

- [ ] **Step 2: Run — expect FAIL** (`AttributeError: 'DatasetPage' object has no attribute 'destination'`)

- [ ] **Step 3: Implement** — modify `sim/ui/dataset_page.py`. Wrap today's analysis content into an "analysis"
container widget, add a training `TrainingPanel`, and put both in a `QStackedWidget` driven by a
`QRadioButton` pair. Read the file first. The change:

**3a.** New imports:
```python
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QProgressBar, QPushButton, QRadioButton, QSlider, QSpinBox, QStackedWidget,
                               QVBoxLayout, QWidget)
from sim.ui.training_panel import TrainingPanel
```

**3b.** In `__init__`, build the destination toggle + stack. The analysis widgets stay exactly as they are, but
they go into an `_analysis` container instead of directly into `root`. Replace the layout-building tail
(from `root = QVBoxLayout(self)` onward) with:

```python
        # -- analysis container: today's content, unchanged --
        analysis = QWidget()
        aroot = QVBoxLayout(analysis)
        aroot.addWidget(QLabel("MIX"))
        aroot.addWidget(self._mix)
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
            aroot.addLayout(lay)
        aroot.addStretch(1)

        # -- training panel --
        self._training = TrainingPanel(self._params_gt)

        # -- destination toggle + stack --
        self._dest_analisi = QRadioButton("Analisi"); self._dest_analisi.setChecked(True)
        self._dest_training = QRadioButton("Training")
        grp = QButtonGroup(self); grp.addButton(self._dest_analisi); grp.addButton(self._dest_training)
        self._stack = QStackedWidget(); self._stack.addWidget(analysis); self._stack.addWidget(self._training)
        self._dest_training.toggled.connect(lambda on: self._stack.setCurrentIndex(1 if on else 0))

        root = QVBoxLayout(self)
        dest = QHBoxLayout()
        dest.addWidget(QLabel("<b>Destinazione</b>")); dest.addWidget(self._dest_analisi)
        dest.addWidget(self._dest_training); dest.addStretch(1)
        root.addLayout(dest)
        root.addWidget(self._stack)
        self._refresh()
```

**3c.** `set_sources` reaches both tables:
```python
    def set_sources(self, specs, preset_names):
        self._mix.set_sources(specs, preset_names)
        self._training.set_sources(specs, preset_names)
```

**3d.** Add `destination()`:
```python
    def destination(self):
        return "training" if self._dest_training.isChecked() else "analisi"
```

The analysis getters (`mix/count/seed/strength/k/formats/out_dir/estimated_bytes`) and `_gen_btn`/`_progress`
stay exactly as they are — the app's analysis path is untouched.

- [ ] **Step 4: Run the page + app tests — expect PASS**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_dataset_page.py tests/test_sim_training_panel.py tests/test_sim_app_lifecycle.py tests/test_sim_ui_smoke.py -q -p no:cacheprovider
```
Expected: all pass. The app-lifecycle tests still reach `_dataset_page._mix` (the analysis table) and `_gen_btn`
— both preserved — so they stay green even though `_run_dataset` is unchanged (this task does not touch the app).

- [ ] **Step 5: Prove the sabotage bites**

In `destination()`, always `return "analisi"`. Run `test_the_destination_toggle_switches_analysis_and_training`
— it must FAIL (training never selected). Revert and re-run green.

- [ ] **Step 6: Commit**

```bash
git add sim/ui/dataset_page.py tests/test_sim_dataset_page.py
git commit -m "feat(sim-ui): il toggle destinazione Analisi | Training + lo stack

DatasetPage diventa un guscio: un toggle a due radio commuta un
QStackedWidget tra il contenuto Analisi (invariato) e il TrainingPanel.
set_sources raggiunge entrambe le tabelle. Gli getter Analisi restano ->
il percorso generate_dataset dell'app non cambia."
```

---

### Task 6: `app.py` — route by destination, wire Cancel + live ETA

**Files:**
- Modify: `sim/ui/app.py`
- Modify: `tests/test_sim_app_lifecycle.py` (append)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_sim_app_lifecycle.py`)

```python
def test_run_dataset_training_writes_a_pt_cache(qapp, tmp_path):
    import torch
    win = SimApp(CHAMP)
    win.set_mode(4)
    p = win._dataset_page
    p._dest_training.setChecked(True)
    tp = p._training
    tp._mix._rows[0].family.setCurrentText("generator")
    tp._mix._rows[0].source.setCurrentText("sinusoidal")
    tp._mix._rows[0].regime.setCurrentText("highway")
    tp._mix._rows[0].weight.setValue(100.0)
    tp._n_train.setValue(3); tp._n_val.setValue(2)
    path = str(tmp_path / "cache.pt"); tp._out_dir.setText(path)
    win._run_dataset()
    blob = torch.load(path, weights_only=False)
    assert len(blob["train"]) == 3 and len(blob["val"]) == 2
    assert tp._gen_btn.isEnabled()                         # _done_busy ran
    assert not tp._cancel_btn.isEnabled()                  # cancel back to idle


def test_the_cancel_button_is_not_a_busy_control_but_generate_is(qapp):
    """Cancel must stay clickable DURING the run -- the one control _busy does NOT disable. But the training
    Generate MUST be a busy control, or the processEvents pump could deliver a second click and nest a run."""
    win = SimApp(CHAMP)
    controls = win._busy_controls()
    assert win._dataset_page._training._cancel_btn not in controls
    assert win._dataset_page._training._gen_btn in controls


def test_a_shared_leader_in_val_mode_2_is_reported_not_crashed(qapp, tmp_path):
    """Mode 2 raises ValueError when a leader is shared (strength 0 + a const built spec). The app must SURFACE
    that in the status bar and restore the UI -- not let the exception escape the click handler."""
    from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
    win = SimApp(CHAMP)
    # give the app a built scenario so the built family is usable
    from sim.scenario import manual_scenario
    import numpy as np
    sc0 = win._scenarios[0]
    win._on_scenario_built(manual_scenario(sc0.params_gt, sc0.v_leader, sc0.s_init, sc0.v_init, name="flat"),
                           ScenarioSpec(name="flat", blocks=(Block("const", 600, {"v": 20.0}),),
                                        style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0))
    win.set_mode(4)
    p = win._dataset_page; p._dest_training.setChecked(True); tp = p._training
    tp._mix._rows[0].family.setCurrentText("built")
    tp._mix._rows[0].source.setCurrentText("flat")
    tp._mix._rows[0].regime.setCurrentText("highway")
    tp._mix._rows[0].weight.setValue(100.0)
    tp._jitter.setValue(0)                                 # strength 0 -> identity -> train and val share the leader
    tp._val_sel.setCurrentIndex(1)                         # new_shapes mode: the gate must fire
    tp._n_train.setValue(2); tp._n_val.setValue(2)
    path = str(tmp_path / "cache.pt"); tp._out_dir.setText(path)
    win._run_dataset()                                     # must NOT raise
    import os as _os
    assert not _os.path.exists(path)                       # nothing written
    assert tp._gen_btn.isEnabled()                         # UI restored


def test_cancelling_a_training_run_writes_nothing(qapp, tmp_path):
    win = SimApp(CHAMP)
    win.set_mode(4)
    p = win._dataset_page; p._dest_training.setChecked(True)
    tp = p._training
    tp._mix._rows[0].family.setCurrentText("generator")
    tp._mix._rows[0].source.setCurrentText("sinusoidal")
    tp._mix._rows[0].regime.setCurrentText("highway")
    tp._mix._rows[0].weight.setValue(100.0)
    tp._n_train.setValue(5); tp._n_val.setValue(2)
    path = str(tmp_path / "cache.pt"); tp._out_dir.setText(path)
    win._cancel_requested = True                           # simulate a cancel already pressed
    win._run_dataset()
    import os as _os
    assert not _os.path.exists(path)                       # a cancelled run writes nothing
    assert tp._gen_btn.isEnabled() and not tp._cancel_btn.isEnabled()
```

- [ ] **Step 2: Run — expect FAIL** (`AttributeError` on `_cancel_requested` / the training branch missing)

- [ ] **Step 3: Implement** in `sim/ui/app.py`. Read `_run_dataset`, `_dataset_progress`, `_busy`/`_done_busy`
first. The changes:

**3a.** Wire the panel's Cancel button + `_on_generate` (near where `_dataset_page._on_generate` is set, ~:190):
```python
        self._dataset_page._training._on_generate = self._run_dataset
        self._dataset_page._training._cancel_btn.clicked.connect(self._cancel_dataset)
        self._cancel_requested = False
```

**3a-bis.** Add the training Generate to `_busy_controls()` (so a second click cannot nest a run) — the Cancel
button is deliberately NOT added (it must stay live). Change `_busy_controls` (:399-401) to append it:
```python
    def _busy_controls(self):
        return (self._meso_page._run_platoon_btn, self._meso_page._run_ring_btn, self._mode_sel,
                self._dataset_page._gen_btn, self._dataset_page._training._gen_btn)
```

**3b.** `_dataset_progress` returns the cancel flag (so `build_training_cache` aborts):
```python
    def _dataset_progress(self, i, total):
        self._dataset_page._progress.setValue(int(100 * i / max(total, 1)))
        self._dataset_page._training._progress.setValue(int(100 * i / max(total, 1)))
        self._status.showMessage(f"dataset {i}/{total}…")
        QApplication.processEvents()
        return self._cancel_requested            # generate_dataset ignores the return; build_training_cache cancels on True
```

**3c.** `_cancel_dataset`:
```python
    def _cancel_dataset(self):
        self._cancel_requested = True
        self._status.showMessage("annullo…")
```

**3d.** Route `_run_dataset` by destination:
```python
    def _run_dataset(self):
        page = self._dataset_page
        self._cancel_requested = False
        if page.destination() == "training":
            tp = page._training
            tp._cancel_btn.setEnabled(True)
            self._busy("genero training set…")
            try:
                from sim.train_gen import build_training_cache
                build_training_cache(tp.mix(), tp.n_train(), tp.n_val(), tp.seed(), tp.strength(),
                                     self._built_specs(), tp.out_path(), val_mode=tp.val_mode(),
                                     val_mix=tp.val_mix(), on_progress=self._dataset_progress)
            except ValueError as e:
                # the engine refuses loudly: a shared-leader val (mode 2), a too-short built scenario, an
                # invalid mix. Surface it in the status bar instead of letting it escape the click handler.
                self._status.showMessage(f"training non generato: {e}", 8000)
            finally:
                self._done_busy()
                tp._cancel_btn.setEnabled(False)
                tp._progress.setValue(0)
            return
        self._busy("genero dataset…")
        try:
            generate_dataset(page.mix(), page.count(), page.seed(), page.strength(), page.k(),
                             page.formats(), page.out_dir(), self._built_specs(), _PARAMS_GT,
                             on_progress=self._dataset_progress)
        finally:
            self._done_busy()
            page._progress.setValue(0)
```

> **Cancel stays clickable:** `_busy_controls()` is NOT changed — the Cancel button is never added to it, so
> `_busy` never disables it. The `processEvents()` pump in `_dataset_progress` delivers the Cancel click mid-run,
> which sets `_cancel_requested`, which the next `_dataset_progress` return aborts on. No threads.

- [ ] **Step 4: Run the app tests — expect PASS**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_app_lifecycle.py tests/test_sim_ui_smoke.py -q -p no:cacheprovider
```
Expected: all pass (the prior lifecycle tests + the 3 new training ones + ui-smoke).

- [ ] **Step 5: Prove the sabotage bites**

In `_run_dataset`'s training branch, pass `val_mix=None` unconditionally (ignore `tp.val_mix()`). This does NOT
break the 3 new tests (they use standard mode). Instead sabotage the cancel: in `_dataset_progress`, `return
False` always (never the flag). Run: `test_cancelling_a_training_run_writes_nothing` must FAIL (the run
completes and writes the file). Revert and re-run green.

- [ ] **Step 6: Commit**

```bash
git add sim/ui/app.py tests/test_sim_app_lifecycle.py
git commit -m "feat(sim-ui): _run_dataset instrada Analisi/Training + Cancel abortabile

Training -> build_training_cache (val_mode/val_mix dal pannello); Analisi
-> generate_dataset invariato. Il Cancel NON e' un _busy_control: resta
cliccabile, il pump processEvents() esistente consegna il click, e
_dataset_progress ritorna il flag -> build_training_cache torna None e non
scrive nulla. Nessun thread."
```

---

### Task 7: Full suite, render-verify, docs, push

**Files:**
- Modify: `document/SIMULATOR_ARCHITECTURE.md`, `document/SIMULATOR_SESSION_RESUME.md`

- [ ] **Step 1: Full suite — quiet machine, no pipe**

```bash
OUT="<a writable temp file>.txt"
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -rf -p no:cacheprovider > "$OUT" 2>&1; echo "PYTEST_EXIT=$?" >> "$OUT"
```
Read the summary + exit from `$OUT`. Expected: **all green** (373 baseline + the new tests: ~3 train_gen + 5
mix_table + 11 training_panel + 3 page + 3 app-lifecycle ≈ **398**; confirm the real number), `PYTEST_EXIT=0`.
Give it ≥420 s. **Do NOT run anything else while it runs.** If the composer budget test is the only red,
re-measure it alone before believing it (it is wall-clock; parallel load reddens it).

- [ ] **Step 2: Invariants empty**

```bash
git diff 7968b95f HEAD -- sim/state.py sim/stepper.py sim/backend.py sim/probe.py sim/events.py \
  sim/eventprop_stepper.py utils/closed_loop_eval.py sim/scenario_spec.py train.py data/generator.py
```
Expected: **empty**. `data/generator.py`'s gate is `tests/test_sim_provenance.py` (green in Step 1). If any is
non-empty, STOP — B2 must not touch the frozen core / provenance file.

- [ ] **Step 3: Render-verify — the Training destination**

Write a render script (`QT_QPA_PLATFORM=windows`, real dark theme via `apply_dark_theme`) that builds `SimApp`,
enters mode 4, toggles Training, sets a 3-row mix (built/preset/generator + a cut_in row), and grabs a PNG:

```python
import os, sys
os.environ["QT_QPA_PLATFORM"] = "windows"
REPO = r"D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator"
SP = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, REPO)
from PySide6.QtWidgets import QApplication
from sim.ui.theme import apply_dark_theme
from sim.ui.app import SimApp
app = QApplication.instance() or QApplication([]); apply_dark_theme(app)
win = SimApp(os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt"))
win.set_mode(4)
p = win._dataset_page; p._dest_training.setChecked(True); tp = p._training
tp._mix._rows[0].family.setCurrentText("generator"); tp._mix._rows[0].source.setCurrentText("sinusoidal")
tp._mix._rows[0].regime.setCurrentText("highway"); tp._mix._rows[0].weight.setValue(50.0)
r2 = tp._mix.add_row(); r2.family.setCurrentText("cut_in"); r2.source.setCurrentText("sinusoidal"); r2.regime.setCurrentText("urban"); r2.weight.setValue(50.0)
tp._val_sel.setCurrentIndex(1)
tp.resize(1000, 470); tp.show(); app.processEvents()
print("valido:", tp._mix.is_valid(), "| eta:", tp._eta_lbl.text(), "| stima:", tp._size_lbl.text())
print("cmd:", tp._cmd_lbl.text(), "| freq attiva:", tp._freq.isEnabled(), "| cancel:", tp._cancel_btn.isEnabled())
tp.grab().save(os.path.join(SP, "b2_training.png")); print("saved")
```

Run with `PYTHONIOENCODING=utf-8`. Read the PNG. Confirm: the regime column, the `cut_in` family, the
`→ finestre` column, train/val counts, the validation selector + its note, frequency disabled with its reason,
`.pt`, the size estimate, the ETA, Cancel present, and the `train.py --data_cache` line. It should match the
approved mock **plus** Cancel + ETA.

- [ ] **Step 4: Update the docs** — `document/SIMULATOR_ARCHITECTURE.md`: add a `sim/ui/training_panel.py` row;
update `sim/ui/mix_table.py` (now `with_regime` too) and `sim/ui/dataset_page.py` (now a destination toggle +
stack) rows; note `training_windows` in the `sim/train_gen.py` row; bump the test count to the real Step-1
number. `document/SIMULATOR_SESSION_RESUME.md`: mark **7b Plan B (UI) COMPLETE** — B1 (extraction) + B2 (the
Training destination) both landed; **the whole of item 7 (the dataset generator, 7a + 7b) is now DONE**; the
only remaining queued item is the **merge `Simulator`→`main`** (parked behind `Simulink_Importer`).

- [ ] **Step 5: Commit + push**

```bash
git add document/SIMULATOR_ARCHITECTURE.md document/SIMULATOR_SESSION_RESUME.md
git commit -m "docs(sim): 7b UI B2 completo -- la destinazione Training e' viva; item 7 chiuso"
git push origin Simulator
```

- [ ] **Step 6: Report — do NOT merge to main.** Report B2 complete + **item 7 (the whole dataset generator)
done**: the Training destination writes the `.pt` cache `train.py` reads, with the regime axis, the 3-mode
validation selector, the window-share honesty column, and Cancel+ETA. Real test count, invariants empty, the
render matches the mock + Cancel/ETA. **Merge → main stays parked**, sequenced behind `Simulink_Importer`.
