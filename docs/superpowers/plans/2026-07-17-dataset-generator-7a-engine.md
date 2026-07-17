# Dataset generator 7a — Plan A: the engine (pure, no Qt)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** The pure sampling engine behind the Dataset mode — a 3-family mix with exact quotas, seeded
type-preserving jitter, a format registry, decimation, and a batch loop that writes a reproducible dataset +
manifest. **No Qt.** Plan B (a later plan) puts the 5th mode on top of it.

**Architecture:** Four pure modules, each isolated and tested alone: `jitter` (the heart — structural
perturbation that keeps the type), `dataset_mix` (weights → exact counts), `export_formats` (the registry =
the single source of truth for formats + bytes/tick), `dataset_gen` (the 3-family sampler + the batch loop).
`data/generator.py` is **called read-only** for the generator family and never modified.

**Tech Stack:** Python, numpy (no scipy, no LAPACK, no new compiled deps). Env: conda `cf_sim`.

**Runner (NEVER `conda run`):**
```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest <args> -p no:cacheprovider
```
**Suite = the sim glob only:** `tests/test_sim_*.py tests/test_champion_io.py`. Never `pytest tests/` —
`tests/test_fpga_io.py` calls `sys.exit()` at import and aborts collection. Full suite ~3 min → **≥420 s or
background**. Commits conventional, **no `Co-Authored-By`**.

**Baseline:** 305 green (record it in Task 1 Step 0 — do not trust this number, verify it).

**Invariants — untouched, verified by an empty diff in Task 5:** frozen core
(`sim/{state,stepper,backend,probe,events,eventprop_stepper}.py`), `utils/closed_loop_eval.py`,
`sim/scenario_spec.py` `materialise`, and **`data/generator.py`** (we CALL it — it is the frozen provenance of
the champions' training data; a copy is archived in `Arch_Tested/R24F_MIXED_.../data/generator.py`).

**Test rules (non-negotiable):** compute expected values from the real code, never from memory; every task ends
by **sabotaging the fix** and watching the guard fail (the sabotage must exercise the guarded property), then
revert; use **Edit** (loud on mismatch); check GREEN **before** committing, as a separate action.

**Grounded facts (verified 2026-07-17):**
- `sim/scenario_spec.py:22-36`: `A_MAX_RANGE=(1.0,4.0)`, `B_MAX_RANGE=(1.0,9.0)`, `V_RANGE=(0.0,40.0)`,
  `MAX_BLOCK_TICKS=6000`, `_KINDS=("preset","const","ramp","sine","custom")`, `_PRESET_N=600`.
- `:39-66`: `Block(kind, ticks, params, bias=None)` · `LeaderStyle(a_max, b_max)` ·
  `ScenarioSpec(name, blocks, style, s_init, v_init)` — all frozen dataclasses.
- Per-kind params: `const={"v"}` · `ramp={"to_v"}` · `sine={"amp","period"}` · `custom={"nodes": tuple}` ·
  `preset={"name"}` → **a preset has no numeric knob; only `ticks` moves it**.
- `sim/scenario_spec.py:100-104` `_preset_samples` returns `lib[name].v_leader[:n]` verbatim with a hardcoded
  `rng=default_rng(0)` → the preset family is jittered through **`params_gt`** (`v_set=0.7·v0`).
- `data/generator.py:179-245` `_leader_profile(profile, N, dt, rng, v0)` — pure, parametric, returns float32
  of length N. Profiles: `constant, sinusoidal, stop_and_go, free, launch`.
- `data/generator.py:595` `_PHYS_BOUNDS = {'v0':(8.0,45.0),'T':(0.5,2.5),'s0':(1.0,5.0),'a':(0.3,2.5),'b':(0.5,3.0)}`
  (its comment: `= CF_FSNN_Net._PARAM_BOUNDS`) — import it, don't duplicate it.
- Measured sizes (item 2, N=600): CSV **60 438 B**, MAT **20 072 B**.
- `cf_sim` deps: `json` ✓; `openpyxl/xlsxwriter/pyarrow/fastparquet/h5py/tables/pandas` **all absent**.

---

### Task 1: `sim/jitter.py` — seeded, type-preserving jitter

**Files:**
- Create: `sim/jitter.py`
- Test: `tests/test_sim_jitter.py`

- [ ] **Step 0: Record the baseline**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -q -p no:cacheprovider
```
Expected: `B passed` (record the real B; ~305).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sim_jitter.py`:
```python
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.scenario_spec import (A_MAX_RANGE, B_MAX_RANGE, V_RANGE, Block, LeaderStyle,  # noqa: E402
                               ScenarioSpec)
from sim.jitter import jitter_params_gt, jitter_spec                                    # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


def _spec():
    return ScenarioSpec(
        name="x",
        blocks=(Block("const", 100, {"v": 15.0}),
                Block("ramp", 120, {"to_v": 25.0}),
                Block("sine", 140, {"amp": 3.0, "period": 60.0}),
                Block("custom", 80, {"nodes": (12.0, 18.0, 9.0)}),
                Block("preset", 200, {"name": "hard_brake"})),
        style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)


def test_same_seed_gives_an_identical_spec():
    a = jitter_spec(_spec(), np.random.default_rng(7), 0.3)
    b = jitter_spec(_spec(), np.random.default_rng(7), 0.3)
    assert a == b                                        # frozen dataclasses compare by value


def test_zero_strength_is_the_identity():
    s = _spec()
    assert jitter_spec(s, np.random.default_rng(1), 0.0) == s   # the degenerate case: jitter is the ONLY variation


def test_the_type_is_preserved_and_the_knobs_stay_in_range():
    s = _spec()
    j = jitter_spec(s, np.random.default_rng(3), 0.5)
    assert [b.kind for b in j.blocks] == [b.kind for b in s.blocks]      # a sine stays a sine
    assert all(b.ticks >= 1 for b in j.blocks)
    assert j.blocks[4].params["name"] == "hard_brake"                    # a preset has no numeric knob
    assert V_RANGE[0] <= j.blocks[0].params["v"] <= V_RANGE[1]
    assert V_RANGE[0] <= j.blocks[1].params["to_v"] <= V_RANGE[1]
    assert j.blocks[2].params["period"] > 0.0
    assert all(V_RANGE[0] <= v <= V_RANGE[1] for v in j.blocks[3].params["nodes"])
    assert A_MAX_RANGE[0] <= j.style.a_max <= A_MAX_RANGE[1]
    assert B_MAX_RANGE[0] <= j.style.b_max <= B_MAX_RANGE[1]


def test_a_nonzero_strength_actually_moves_something():
    s = _spec()
    j = jitter_spec(s, np.random.default_rng(3), 0.5)
    assert j != s                                        # otherwise the "identity" test above proves nothing


def test_params_gt_jitter_is_seeded_and_bounded():
    from data.generator import _PHYS_BOUNDS
    a = jitter_params_gt(_PG, np.random.default_rng(5), 0.2)
    b = jitter_params_gt(_PG, np.random.default_rng(5), 0.2)
    assert np.allclose(a, b)
    assert np.allclose(jitter_params_gt(_PG, np.random.default_rng(5), 0.0), _PG)   # identity at 0
    for i, k in enumerate(("v0", "T", "s0", "a", "b")):
        lo, hi = _PHYS_BOUNDS[k]
        assert lo <= a[i] <= hi
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_jitter.py -q -p no:cacheprovider
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.jitter'`.

- [ ] **Step 3: Implement**

Create `sim/jitter.py`:
```python
"""Seeded, type-preserving jitter: of a ScenarioSpec (the built family) and of params_gt (the preset family).

STRUCTURAL, not a blur. It nudges each block's OWN knobs (v, to_v, amp, period, nodes, ticks) and the neutral
style, so the scenario keeps its shape and its TYPE -- a sine stays a sine, a hard_brake stays a hard_brake.
Blurring the 600-float v_leader would not preserve either. A `preset` block has NO numeric knob
(scenario_spec.py:100-104 returns the library profile verbatim) -- only its `ticks` slot moves; the preset
family's real variety comes from jitter_params_gt (v_set = 0.7*v0 scales the whole profile).

strength=0 is the IDENTITY: the multiplier is exactly 1.0 and the clips are no-ops for in-range knobs, so the
spec comes back byte-identical. That degenerate case is what proves jitter is the only source of variation."""
from dataclasses import replace

import numpy as np

from data.generator import _PHYS_BOUNDS   # read-only: the canonical param bounds (= CF_FSNN_Net._PARAM_BOUNDS)
from sim.scenario_spec import (A_MAX_RANGE, B_MAX_RANGE, MAX_BLOCK_TICKS, V_RANGE, LeaderStyle, _PRESET_N)

_PARAM_KEYS = ("v0", "T", "s0", "a", "b")


def _rel(x, rng, strength, lo, hi):
    """x scaled by 1 +/- strength, clipped to [lo, hi]. strength=0 -> exactly x."""
    return float(np.clip(float(x) * (1.0 + rng.uniform(-strength, strength)), lo, hi))


def jitter_spec(spec, rng, strength):
    """A new ScenarioSpec of the SAME type with its knobs nudged. strength in [0,1]; 0 = identity."""
    blocks = []
    for b in spec.blocks:
        cap = _PRESET_N if b.kind == "preset" else MAX_BLOCK_TICKS
        ticks = int(np.clip(round(b.ticks * (1.0 + rng.uniform(-strength, strength))), 1, cap))
        p = dict(b.params)
        if b.kind == "const":
            p["v"] = _rel(p["v"], rng, strength, *V_RANGE)
        elif b.kind == "ramp":
            p["to_v"] = _rel(p["to_v"], rng, strength, *V_RANGE)
        elif b.kind == "sine":
            p["amp"] = _rel(p["amp"], rng, strength, 0.0, V_RANGE[1])
            p["period"] = _rel(p["period"], rng, strength, 1.0, float(MAX_BLOCK_TICKS))
        elif b.kind == "custom":
            p["nodes"] = tuple(_rel(v, rng, strength, *V_RANGE) for v in p["nodes"])
        # "preset": params = {"name": ...} -- verbatim, no numeric knob; only `ticks` moves it
        blocks.append(replace(b, ticks=ticks, params=p))
    style = LeaderStyle(_rel(spec.style.a_max, rng, strength, *A_MAX_RANGE),
                        _rel(spec.style.b_max, rng, strength, *B_MAX_RANGE))
    return replace(spec, blocks=tuple(blocks), style=style)


def jitter_params_gt(params_gt, rng, strength):
    """The PRESET family's only knob: v_set = 0.7*v0 scales the whole verbatim profile, s_init shifts with it.
    Bounded by the project's physical param bounds, imported (never duplicated)."""
    pg = np.asarray(params_gt, dtype=float).copy()
    for i, k in enumerate(_PARAM_KEYS):
        lo, hi = _PHYS_BOUNDS[k]
        pg[i] = _rel(pg[i], rng, strength, lo, hi)
    return pg
```

- [ ] **Step 4: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_jitter.py -q -p no:cacheprovider
```
Expected: `5 passed`.

- [ ] **Step 5: Sabotage, watch the guard fail, revert**

In `jitter_spec`, change the `sine` branch to also rewrite the kind: `blocks.append(replace(b, kind="const", ticks=ticks, params=p))`. Re-run: expected FAIL on
`test_the_type_is_preserved_and_the_knobs_stay_in_range` (the kind list no longer matches). This proves the
test pins type preservation, not just "it returns a spec". **Revert**; re-run → `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add sim/jitter.py tests/test_sim_jitter.py
git commit -m "feat(sim): seeded type-preserving jitter of a ScenarioSpec and params_gt"
```

---

### Task 2: `sim/dataset_mix.py` — the mix + exact quotas

**Files:**
- Create: `sim/dataset_mix.py`
- Test: `tests/test_sim_dataset_mix.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sim_dataset_mix.py`:
```python
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.dataset_mix import MixEntry, quotas, validate_mix   # noqa: E402


def test_quotas_are_exact_not_expected():
    mix = [MixEntry("built", "mine", 40.0), MixEntry("preset", "hard_brake", 30.0),
           MixEntry("generator", "stop_and_go", 30.0)]
    q = quotas(mix, 100)
    assert q == [40, 30, 30]                 # exactly, not "in expectation"
    assert sum(q) == 100


def test_largest_remainder_absorbs_the_leftovers():
    mix = [MixEntry("preset", "a", 1 / 3 * 100), MixEntry("preset", "b", 1 / 3 * 100),
           MixEntry("preset", "c", 1 / 3 * 100)]
    q = quotas(mix, 100)
    assert sum(q) == 100                      # no trajectory lost to rounding
    assert sorted(q) == [33, 33, 34]


def test_validate_rejects_a_total_that_is_not_100():
    with pytest.raises(ValueError):
        validate_mix([MixEntry("preset", "a", 60.0), MixEntry("preset", "b", 30.0)])
    validate_mix([MixEntry("preset", "a", 60.0), MixEntry("preset", "b", 40.0)])   # ok, no raise


def test_validate_rejects_an_empty_mix_and_a_bad_family():
    with pytest.raises(ValueError):
        validate_mix([])
    with pytest.raises(ValueError):
        validate_mix([MixEntry("nonsense", "a", 100.0)])
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_dataset_mix.py -q -p no:cacheprovider
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.dataset_mix'`.

- [ ] **Step 3: Implement**

Create `sim/dataset_mix.py`:
```python
"""The dataset mix: which scenarios, from which family, at what percentage -- and the EXACT counts that follow.

Exact quotas, not a multinomial draw: "30%" for a controlled dataset means exactly 30 trajectories out of 100,
not 30 in expectation. The leftovers from rounding go to the largest remainders, so the counts always sum to N
and no trajectory is lost."""
from dataclasses import dataclass

FAMILIES = ("built", "preset", "generator")


@dataclass(frozen=True)
class MixEntry:
    family: str      # one of FAMILIES
    source: str      # a built scenario's name | a library preset name | a generator profile name
    weight: float    # percent; the mix must total 100


def validate_mix(mix):
    """Raise ValueError unless the mix is non-empty, every family is known, and the weights total 100."""
    if not mix:
        raise ValueError("mix vuoto")
    for e in mix:
        if e.family not in FAMILIES:
            raise ValueError(f"famiglia sconosciuta: {e.family!r} (valide: {FAMILIES})")
        if e.weight < 0:
            raise ValueError(f"peso negativo: {e.weight}")
    total = sum(e.weight for e in mix)
    if abs(total - 100.0) > 0.01:
        raise ValueError(f"i pesi non sommano a 100 (somma={total:.2f})")


def quotas(mix, count):
    """Exact per-entry counts summing to `count` (largest remainder for the leftovers)."""
    validate_mix(mix)
    raw = [e.weight / 100.0 * count for e in mix]
    base = [int(x) for x in raw]
    left = count - sum(base)
    order = sorted(range(len(mix)), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[:left]:
        base[i] += 1
    return base
```

- [ ] **Step 4: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_dataset_mix.py -q -p no:cacheprovider
```
Expected: `4 passed`.

- [ ] **Step 5: Sabotage, watch the guard fail, revert**

In `quotas`, drop the largest-remainder pass (delete the `for i in order[:left]: base[i] += 1` line). Re-run:
expected FAIL on `test_largest_remainder_absorbs_the_leftovers` (`sum(q) == 99`, not 100). This proves the test
pins "no trajectory lost to rounding". **Revert**; re-run → `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add sim/dataset_mix.py tests/test_sim_dataset_mix.py
git commit -m "feat(sim): the dataset mix model + exact largest-remainder quotas"
```

---

### Task 3: `sim/export_formats.py` — the registry (+ json, + a hand-rolled xlsx)

**Files:**
- Create: `sim/export_formats.py`
- Test: `tests/test_sim_export_formats.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sim_export_formats.py`:
```python
import json
import os
import sys
import zipfile

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from config import DT                                    # noqa: E402
from sim.scenario import scenario_library                # noqa: E402
from sim.export_formats import FORMATS, available_formats, estimate_bytes   # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


def test_the_registry_knows_all_six_and_flags_the_unavailable_ones():
    assert set(FORMATS) == {"csv", "mat", "json", "xlsx", "parquet", "hdf5"}
    assert set(available_formats()) == {"csv", "mat", "json", "xlsx"}
    assert FORMATS["parquet"].available is False and "pyarrow" in FORMATS["parquet"].reason
    assert FORMATS["hdf5"].available is False and "h5py" in FORMATS["hdf5"].reason


def test_every_available_writer_produces_a_readable_file(tmp_path):
    sc = scenario_library(_PG, N=60)[0]
    for name in available_formats():
        p = str(tmp_path / f"s.{name}")
        FORMATS[name].writer(sc, p, DT)
        assert os.path.getsize(p) > 0
    # json round-trips its four columns
    with open(str(tmp_path / "s.json")) as f:
        d = json.load(f)
    assert len(d["v_leader"]) == 60 and set(["t", "v_leader", "x_leader", "a_leader"]) <= set(d)
    # xlsx is a real zip with a sheet in it
    with zipfile.ZipFile(str(tmp_path / "s.xlsx")) as z:
        assert "xl/worksheets/sheet1.xml" in z.namelist()


def test_bytes_per_tick_matches_a_measured_sample(tmp_path):
    """The estimate must not silently drift from what the writers actually produce."""
    sc = scenario_library(_PG, N=600)[0]
    for name in available_formats():
        p = str(tmp_path / f"m.{name}")
        FORMATS[name].writer(sc, p, DT)
        measured = os.path.getsize(p) / 600.0
        claimed = FORMATS[name].bytes_per_tick
        assert abs(measured - claimed) / measured < 0.10, f"{name}: claimed {claimed}, measured {measured:.1f}"


def test_estimate_sums_over_ticks_and_formats():
    one = estimate_bytes([600], ["csv"])
    assert abs(one - 600 * FORMATS["csv"].bytes_per_tick) < 1.0
    both = estimate_bytes([600, 300], ["csv", "mat"])
    assert abs(both - (900 * FORMATS["csv"].bytes_per_tick + 900 * FORMATS["mat"].bytes_per_tick)) < 1.0


def test_an_unavailable_format_refuses_to_write(tmp_path):
    sc = scenario_library(_PG, N=10)[0]
    with pytest.raises(RuntimeError):
        FORMATS["parquet"].writer(sc, str(tmp_path / "x.parquet"), DT)
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_export_formats.py -q -p no:cacheprovider
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.export_formats'`.

- [ ] **Step 3: Implement**

Create `sim/export_formats.py`:
```python
"""The export-format registry: the SINGLE source of truth for which formats exist, who writes them, how big
they are, and -- when unavailable -- why.

The UI renders its checkboxes FROM this registry, so no hardcoded list elsewhere can diverge from reality.

parquet and hdf5 are registered but unavailable: pyarrow/h5py are COMPILED libraries and this env has a known
OpenMP fragility (the OMP #15 abort is duplicate OMP runtimes; torch already brings one). Risking a green suite
for a format no consumer has asked for is a bad trade -- so they are declared, disabled, and explained.
Enabling one later = install the dep + a small writer + flip `available`.

bytes_per_tick is calibrated against REAL measurements (CSV 60438 B and MAT 20072 B for N=600) and pinned by a
test that re-measures it -- the estimate cannot drift in silence."""
import json
import zipfile
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from config import DT
from sim.scenario_export import leader_kinematics, scenario_metadata, write_scenario_csv, write_scenario_mat


@dataclass(frozen=True)
class FormatSpec:
    writer: Callable          # (scenario, path, dt) -> None
    bytes_per_tick: float     # calibrated; pinned by test_bytes_per_tick_matches_a_measured_sample
    available: bool
    reason: Optional[str] = None


def _write_json(scenario, path, dt=DT):
    k = leader_kinematics(scenario, dt)
    m = scenario_metadata(scenario, dt)
    payload = {**{key: [float(x) for x in arr] for key, arr in k.items()},
               "name": m["name"], "dt": m["dt"], "N": m["N"],
               "s_init": m["s_init"], "v_init": m["v_init"],
               "params_gt": [float(x) for x in m["params_gt"]]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)


_CT = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
       '<Default Extension="xml" ContentType="application/xml"/>'
       '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.'
       'spreadsheetml.sheet.main+xml"/>'
       '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-'
       'officedocument.spreadsheetml.worksheet+xml"/></Types>')
_RELS = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
         'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
         'relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
_WB = ('<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
       '<sheet name="scenario" sheetId="1" r:id="rId1"/></sheets></workbook>')
_WB_RELS = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')


def _col(i):
    """0 -> A, 1 -> B, ... (only 4 columns here, but keep it general)."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _write_xlsx(scenario, path, dt=DT):
    """A minimal .xlsx: a zip of XML parts (stdlib only -- openpyxl/xlsxwriter are absent).

    Same school as the hand-rolled MAT v5 writer, and easier: this is text, not binary tags. Header row +
    one row per tick, inline numbers (no sharedStrings needed for a numeric sheet)."""
    k = leader_kinematics(scenario, dt)
    cols = ["t", "v_leader", "x_leader", "a_leader"]
    rows = [f'<row r="1">' + "".join(
        f'<c r="{_col(j)}1" t="inlineStr"><is><t>{c}</t></is></c>' for j, c in enumerate(cols)) + "</row>"]
    n = len(k["t"])
    for i in range(n):
        cells = "".join(f'<c r="{_col(j)}{i + 2}"><v>{float(k[c][i]):.6g}</v></c>' for j, c in enumerate(cols))
        rows.append(f'<row r="{i + 2}">{cells}</row>')
    sheet = ('<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/'
             'main"><sheetData>' + "".join(rows) + "</sheetData></worksheet>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("xl/workbook.xml", _WB)
        z.writestr("xl/_rels/workbook.xml.rels", _WB_RELS)
        z.writestr("xl/worksheets/sheet1.xml", sheet)


def _unavailable(dep):
    def _refuse(scenario, path, dt=DT):
        raise RuntimeError(f"formato non disponibile: richiede {dep}")
    return _refuse


FORMATS = {
    "csv":     FormatSpec(write_scenario_csv, 100.7, True),    # measured: 60438 B / 600 ticks
    "mat":     FormatSpec(write_scenario_mat, 33.5, True),     # measured: 20072 B / 600 ticks
    "json":    FormatSpec(_write_json, 92.0, True),            # re-measured by the calibration test
    "xlsx":    FormatSpec(_write_xlsx, 40.0, True),            # zipped XML -- compresses well
    "parquet": FormatSpec(_unavailable("pyarrow"), 12.0, False, "richiede pyarrow"),
    "hdf5":    FormatSpec(_unavailable("h5py"), 33.0, False, "richiede h5py"),
}


def available_formats():
    return [k for k, v in FORMATS.items() if v.available]


def estimate_bytes(ticks_per_traj, formats):
    """Sum over trajectories x selected formats. An estimate: float formatting varies."""
    total_ticks = float(sum(ticks_per_traj))
    return sum(total_ticks * FORMATS[f].bytes_per_tick for f in formats)
```

> The `json`/`xlsx` `bytes_per_tick` above are first guesses. `test_bytes_per_tick_matches_a_measured_sample`
> will FAIL if they are off by >10% — read the measured value from the failure message and pin it. That is the
> point of the test: the constant must come from the writer, not from a guess.

- [ ] **Step 4: Run to verify it passes (calibrate if needed)**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_export_formats.py -q -p no:cacheprovider
```
Expected: `5 passed`. If the calibration test fails, update `json`/`xlsx` `bytes_per_tick` to the measured
value it reports, then re-run.

- [ ] **Step 5: Sabotage, watch the guard fail, revert**

Change `FORMATS["csv"]`'s `bytes_per_tick` from `100.7` to `10.0`. Re-run: expected FAIL on
`test_bytes_per_tick_matches_a_measured_sample` (claimed 10.0 vs measured ~100.7). This proves the estimate is
pinned to what the writer really produces. **Revert**; re-run → `5 passed`.

- [ ] **Step 6: Commit**

```bash
git add sim/export_formats.py tests/test_sim_export_formats.py
git commit -m "feat(sim): the export-format registry (+ json, + a hand-rolled xlsx)"
```

---

### Task 4: `sim/dataset_gen.py` — the 3-family sampler + decimation + the batch loop

**Files:**
- Create: `sim/dataset_gen.py`
- Test: `tests/test_sim_dataset_gen.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sim_dataset_gen.py`:
```python
import json
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from config import DT                                       # noqa: E402
from sim.dataset_mix import MixEntry                        # noqa: E402
from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec   # noqa: E402
from sim.dataset_gen import decimate, draw_scenario, generate_dataset, preview_sample   # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


def _specs():
    return {"mine": ScenarioSpec(name="mine", blocks=(Block("const", 120, {"v": 15.0}),),
                                 style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)}


def test_the_generator_family_is_the_REAL_training_randomisation():
    """It must BE _leader_profile with the same seed -- not a re-interpretation of it."""
    from data.generator import _leader_profile
    sc = draw_scenario("generator", "stop_and_go", seed=11, strength=0.4, specs={}, params_gt=_PG)
    expected = _leader_profile("stop_and_go", 600, DT, np.random.default_rng(11), float(_PG[0]))
    assert np.allclose(sc.v_leader, expected)


def test_each_family_yields_a_valid_scenario():
    for fam, src in (("built", "mine"), ("preset", "hard_brake"), ("generator", "constant")):
        sc = draw_scenario(fam, src, seed=3, strength=0.3, specs=_specs(), params_gt=_PG)
        assert sc.v_leader.ndim == 1 and sc.v_leader.size > 0
        assert np.isfinite(sc.v_leader).all()
        assert sc.s_init > 0.0


def test_the_built_family_uses_its_spec_length_and_the_jitter_moves_it():
    a = draw_scenario("built", "mine", seed=1, strength=0.0, specs=_specs(), params_gt=_PG)
    b = draw_scenario("built", "mine", seed=1, strength=0.5, specs=_specs(), params_gt=_PG)
    assert a.v_leader.size == 120                     # strength=0 -> the spec's own length
    assert not np.allclose(a.v_leader, b.v_leader)    # jitter actually moves the profile


def test_preview_sample_is_deterministic():
    a = preview_sample("preset", "hard_brake", seed=9, strength=0.3, specs={}, params_gt=_PG)
    b = preview_sample("preset", "hard_brake", seed=9, strength=0.3, specs={}, params_gt=_PG)
    assert np.allclose(a, b)


def test_decimate_subsamples_and_recomputes_acceleration():
    k = {"t": np.arange(10) * DT, "v_leader": np.arange(10, dtype=float),
         "x_leader": np.arange(10, dtype=float), "a_leader": np.zeros(10)}
    d = decimate(k, 2, DT)
    assert d["v_leader"].size == 5
    assert np.allclose(d["t"], np.arange(5) * (2 * DT))               # dt_out = k*DT
    assert np.allclose(d["a_leader"], np.diff(d["v_leader"], prepend=d["v_leader"][0]) / (2 * DT))


def test_generate_dataset_is_reproducible_and_writes_a_manifest(tmp_path):
    mix = [MixEntry("preset", "hard_brake", 50.0), MixEntry("generator", "constant", 50.0)]
    out_a, out_b = str(tmp_path / "a"), str(tmp_path / "b")
    for out in (out_a, out_b):
        generate_dataset(mix, count=4, seed=5, strength=0.3, k=1, formats=["csv"],
                         out_dir=out, specs={}, params_gt=_PG)
    names = sorted(os.listdir(out_a))
    assert "manifest.json" in names and len([n for n in names if n.endswith(".csv")]) == 4
    with open(os.path.join(out_a, "manifest.json")) as f:
        man = json.load(f)
    assert man["seed"] == 5 and man["count"] == 4 and man["dt_out"] == DT and man["k"] == 1
    assert len(man["trajectories"]) == 4
    assert {t["family"] for t in man["trajectories"]} == {"preset", "generator"}
    # same seed -> byte-identical dataset
    for n in [x for x in names if x.endswith(".csv")]:
        assert open(os.path.join(out_a, n), "rb").read() == open(os.path.join(out_b, n), "rb").read()
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_dataset_gen.py -q -p no:cacheprovider
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.dataset_gen'`.

- [ ] **Step 3: Implement**

Create `sim/dataset_gen.py`:
```python
"""The dataset engine: a 3-family sampler + decimation + the reproducible batch loop.

One product, three families -- each randomises its own way, all yield a Scenario, so nothing downstream knows
the origin:
  built     -> jitter the spec's blocks + neutral, then materialise (its own length)
  preset    -> jitter params_gt (a preset is verbatim; v_set = 0.7*v0 is its only real knob), then materialise
               a one-preset-block spec (600 = the canonical library length)
  generator -> _leader_profile(...) from data/generator.py, CALLED READ-ONLY: that module is the frozen
               provenance of the champions' training data (a copy is archived with the champion). Its own
               seeded jitter (base/amp/freq/cycle_len) IS the training randomisation -- so the strength slider
               deliberately does NOT govern this family; re-interpreting it would make the dataset a lie.

Frequency: the physics is ALWAYS 10 Hz (DT=0.1 is the V2X rate, hardcoded into the frozen core,
closed_loop_eval and materialise -- not a knob). The export may be DECIMATED by an integer k; a_leader is
recomputed at dt_out because the 0.2 s acceleration is not the 0.1 s one. Upsampling is not offered: it would
invent data the physics never produced."""
import json
import os

import numpy as np

from config import DT
from data.generator import _leader_profile          # read-only: the real training randomisation
from sim.dataset_mix import quotas, validate_mix
from sim.export_formats import FORMATS
from sim.jitter import jitter_params_gt, jitter_spec
from sim.scenario import manual_scenario
from sim.scenario_export import leader_kinematics, scenario_metadata
from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec, _PRESET_N, materialise

GENERATOR_PROFILES = ("constant", "sinusoidal", "stop_and_go", "free", "launch")


def draw_scenario(family, source, seed, strength, specs, params_gt):
    """(family, source, seed) -> a Scenario. The one entry point every family funnels through."""
    rng = np.random.default_rng(seed)
    if family == "built":
        spec = specs[source]
        j = jitter_spec(spec, rng, strength)
        n = sum(int(b.ticks) for b in j.blocks)
        return materialise(j, params_gt, n)
    if family == "preset":
        pg = jitter_params_gt(params_gt, rng, strength)
        spec = ScenarioSpec(name=source, blocks=(Block("preset", _PRESET_N, {"name": source}),),
                            style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)
        return materialise(spec, pg, _PRESET_N)
    if family == "generator":
        v0 = float(params_gt[0])
        v_l = _leader_profile(source, _PRESET_N, DT, rng, v0)
        return manual_scenario(params_gt, np.asarray(v_l, dtype=float),
                               s_init=33.5, v_init=0.8 * v0, name=source)
    raise ValueError(f"famiglia sconosciuta: {family!r}")


def preview_sample(family, source, seed, strength, specs, params_gt):
    """The v_leader the eye shows. For `generator` and for jittered `built` this is ONE representative sample
    (the scenario there IS a distribution), not 'the' scenario -- the popup says so."""
    return draw_scenario(family, source, seed, strength, specs, params_gt).v_leader


def decimate(kin, k, dt=DT):
    """Take every k-th sample; a_leader is RECOMPUTED at dt_out (it is a different quantity there)."""
    k = int(k)
    if k <= 1:
        return kin
    dt_out = k * dt
    v = kin["v_leader"][::k]
    return {"t": np.arange(v.size) * dt_out, "v_leader": v, "x_leader": kin["x_leader"][::k],
            "a_leader": np.diff(v, prepend=v[0]) / dt_out}


def generate_dataset(mix, count, seed, strength, k, formats, out_dir, specs, params_gt, on_progress=None):
    """Write `count` trajectories + manifest.json into out_dir. Same seed -> identical dataset."""
    validate_mix(mix)
    qs = quotas(mix, count)
    os.makedirs(out_dir, exist_ok=True)
    root = np.random.default_rng(seed)
    seeds = [int(s) for s in root.integers(0, 2**31 - 1, size=count)]
    plan = [(e.family, e.source) for e, q in zip(mix, qs) for _ in range(q)]

    records = []
    for i, ((family, source), tseed) in enumerate(zip(plan, seeds)):
        sc = draw_scenario(family, source, tseed, strength, specs, params_gt)
        kin = decimate(leader_kinematics(sc, DT), k, DT)
        meta = scenario_metadata(sc, DT)
        for fmt in formats:
            path = os.path.join(out_dir, f"traj_{i:04d}.{fmt}")
            FORMATS[fmt].writer(_as_scenario(sc, kin, k), path, k * DT)
        records.append({"index": i, "family": family, "source": source, "seed": tseed,
                        "N": int(kin["v_leader"].size), "params_gt": [float(x) for x in meta["params_gt"]],
                        "s_init": meta["s_init"], "v_init": meta["v_init"]})
        if on_progress is not None:
            on_progress(i + 1, count)

    manifest = {"seed": seed, "count": count, "strength": strength, "k": k, "dt_out": k * DT,
                "decimated_from": DT, "formats": list(formats),
                "mix": [{"family": e.family, "source": e.source, "weight": e.weight} for e in mix],
                "quotas": qs, "trajectories": records}
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def _as_scenario(sc, kin, k):
    """The writers take a Scenario and re-derive the kinematics at the dt they are given. When k>1 the decimated
    v_leader IS the scenario at dt_out, so hand them that -- one path, no second kinematics implementation."""
    if k <= 1:
        return sc
    return manual_scenario(sc.params_gt, kin["v_leader"], s_init=sc.s_init, v_init=sc.v_init, name=sc.name)
```

- [ ] **Step 4: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_dataset_gen.py -q -p no:cacheprovider
```
Expected: `6 passed`.

- [ ] **Step 5: Sabotage, watch the guard fail, revert**

In `draw_scenario`'s `generator` branch, replace `_leader_profile(source, _PRESET_N, DT, rng, v0)` with
`np.full(_PRESET_N, v0 * 0.7)` (a plausible-looking constant profile). Re-run: expected FAIL on
`test_the_generator_family_is_the_REAL_training_randomisation`. This proves the test pins the *reuse* of the
training randomisation, not merely "a profile came out". **Revert**; re-run → `6 passed`.

- [ ] **Step 6: Commit**

```bash
git add sim/dataset_gen.py tests/test_sim_dataset_gen.py
git commit -m "feat(sim): the dataset engine -- 3-family sampler, decimation, reproducible batch"
```

---

### Task 5: full suite, headless functional-verify, docs

**Files:**
- Modify: `document/SIMULATOR_ARCHITECTURE.md`, `document/SIMULATOR_SESSION_RESUME.md`

- [ ] **Step 1: Full suite + the invariants are untouched**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -q -p no:cacheprovider
git diff --stat 621120b8 -- sim/state.py sim/stepper.py sim/backend.py sim/probe.py sim/events.py sim/eventprop_stepper.py utils/closed_loop_eval.py sim/scenario_spec.py data/generator.py
```
Expected: `B+20 passed` (baseline + 5 jitter + 4 mix + 5 formats + 6 gen); the diff-stat prints **nothing** —
in particular **`data/generator.py` is untouched** (we call it, we never modify it). ≥420 s or background.

- [ ] **Step 2: Headless functional-verify (the engine is real software on its own)**

Write a throwaway scratchpad script that builds a 3-family mix (one built spec, one preset, one generator
profile), calls `generate_dataset(count=6, seed=1, strength=0.3, k=2, formats=["csv","mat","json","xlsx"])`
into a temp dir, then prints: the file list, the manifest's `quotas`/`dt_out`/`k`, the per-trajectory families,
and — the honest check — the **estimated vs actual** total bytes (`estimate_bytes` vs the summed file sizes).
Confirm the estimate is within ~10%. Delete the script after; keep the numbers for the report.

- [ ] **Step 3: Update the docs**

`document/SIMULATOR_ARCHITECTURE.md`: add `sim/jitter.py`, `sim/dataset_mix.py`, `sim/export_formats.py`,
`sim/dataset_gen.py` rows to the scenario-stack map (all PURE); state that `data/generator.py` is **called
read-only** for the generator family and why; bump the test count to the real number.
`document/SIMULATOR_SESSION_RESUME.md`: mark 7a-Plan-A (the engine) done with the real count + commits; note
the three families and their different jitter semantics, the exact quotas, the registry (parquet/hdf5
registered-but-disabled and why), decimation (physics stays 10 Hz), and that **Plan B (the 5th-mode UI) is
next**; leave the 7b draft as the last queued item.

- [ ] **Step 4: Commit + push**

```bash
git add document/SIMULATOR_SESSION_RESUME.md document/SIMULATOR_ARCHITECTURE.md
git commit -m "docs(sim): resume + map -- dataset engine (7a plan A) done"
git push origin Simulator
```

- [ ] **Step 5: Report — do NOT merge to main**

Report Plan A complete; Plan B (the UI) is the next plan to write. Merge → main stays **parked**.

---

## Self-review (against the spec)

- **Spec §1 three families** → Task 4 `draw_scenario` (+ the test that pins the generator family to
  `_leader_profile`). ✓
- **Spec §1 jitter targets + the slider caveat** → Task 1 (`jitter_spec` per-kind knobs; the generator family
  never receives `strength` in its profile call — documented in Task 4's module docstring). ✓
- **Spec §3 exact quota** → Task 2 (`quotas`, largest remainder). ✓
- **Spec §4 decimation** → Task 4 (`decimate`, a_leader recomputed, manifest fields; no upsampling — `k<=1`
  returns unchanged). ✓
- **Spec §5 registry** → Task 3 (all six, parquet/hdf5 disabled with reason, `available_formats`). ✓
- **Spec §6 size estimate + anti-drift test** → Task 3 (`estimate_bytes` + the calibration test). ✓
- **Spec §7 preview_sample pure** → Task 4 (`preview_sample`, deterministic test). ✓
- **Spec §8 manifest** → Task 4 (`generate_dataset` writes it; the test asserts its fields). ✓
- **Spec §2 spec retention, §9 dataset_page + app wiring** → **Plan B** (deliberately out of this plan). ✓
- **Placeholder scan:** none — every code step is complete. The `json`/`xlsx` `bytes_per_tick` are explicitly
  first guesses that the calibration test forces to real measured values in Task 3 Step 4 (that is the
  mechanism, not a TODO). ✓
- **Type/name consistency:** `jitter_spec`/`jitter_params_gt`/`MixEntry`/`quotas`/`validate_mix`/`FORMATS`/
  `FormatSpec`/`available_formats`/`estimate_bytes`/`draw_scenario`/`preview_sample`/`decimate`/
  `generate_dataset` are used identically across tasks and their tests. ✓
