# Scenario lifecycle (name + delete + export) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Name a built scenario, delete it from the live selector (user-built only), and export its leader
kinematics to `.csv` and `.mat` (scipy-free).

**Architecture:** Two PURE modules — `sim/mat_writer.py` (a tiny MAT v5 serialiser, no scipy) and
`sim/scenario_export.py` (leader kinematics + CSV + MAT, uses the writer) — then thin Qt wiring in
`scenario_page.py` (a name field) and `app.py` (a "⋯" menu on the selector: Export / Delete). The pure
modules carry all the risk and are tested without Qt; the causal test proves `x_leader` reproduces the
stepper's gap.

**Tech Stack:** Python, numpy (no scipy, no LAPACK), PySide6. Env: conda `cf_sim`.

**Runner (NEVER `conda run`):**
```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest <args> -p no:cacheprovider
```
**Suite scope — the sim glob only:** `tests/test_sim_*.py tests/test_champion_io.py`. Do **not** run
`pytest tests/` — `tests/test_fpga_io.py` calls `sys.exit()` at import and aborts collection
(`INTERNALERROR> SystemExit`). Full suite ~3 min → **≥420 s timeout or background**. Render/functional-verify
with `QT_QPA_PLATFORM=windows`. Commits conventional, **no `Co-Authored-By`**. Frozen core
(`sim/{state,stepper,backend,probe,events,eventprop_stepper}.py`), `utils/closed_loop_eval.py`, and
`sim/scenario_spec.py` `materialise` stay **untouched**.

**Baseline:** record it in Task 1 Step 0 (do not hard-code a magic number). Each task adds a few tests; the
gate is a GREEN suite, not a count.

**Test-design rules (non-negotiable):** compute expected values from the running code (the stepper, a probe),
never from memory; each task ends by **sabotaging the fix** and watching the guard test fail (the sabotage
must exercise the guarded property), then revert; use **Edit** (loud on mismatch), anchor to the shown lines;
check GREEN **before** committing, as a separate action.

**Grounded facts (verified 2026-07-16):** `Scenario` (`sim/scenario.py:14`, frozen): `name, params_gt(5),
v_leader(N), s_init, v_init, cut_in`. `DT` = `from config import DT` (= 0.1). Gap recurrence
`stepper.py:88`: `s_new = s + (vl - v_new)*DT` (forward Euler; `s` = pure IDM gap). `SimStepper.from_scenario(
None, sc)` = oracle (params = `sc.params_gt`). The selector `self._selector` (`app.py:127`); `_scenarios` =
`scenario_library(...)` (`:68`) + a manual (`:70`); `_on_scenario_built` appends (`:608`); the Meso page
selects scenarios **by index** into `_scenarios` (`:404`) and was built with the initial names (`:162`) →
protect the initial count. The existing `File → Export CSV` (`:208,231`) exports the EPISODE — do not reuse
its handler/name.

---

### Task 1: `sim/mat_writer.py` — a scipy-free MAT v5 writer (isolated)

**Files:**
- Create: `sim/mat_writer.py`
- Test: `tests/test_sim_mat_writer.py`

- [ ] **Step 0: Record the baseline**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -q -p no:cacheprovider
```
Expected: `B passed` (record B; ~294).

- [ ] **Step 1: Write the failing test** (round-trip via a paired reader + spec-byte assertions)

Create `tests/test_sim_mat_writer.py`:
```python
import os
import struct
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.mat_writer import write_mat   # noqa: E402


def _read_mat(path):
    """A minimal paired MAT v5 reader -- test-only, to round-trip the writer."""
    with open(path, "rb") as f:
        raw = f.read()
    assert raw[124:128] == struct.pack("<HH", 0x0100, 0x4D49)   # version + little-endian ('MI' read LE)
    out, off = {}, 128
    while off < len(raw):
        dtype, nbytes = struct.unpack("<II", raw[off:off + 8]); off += 8
        body = raw[off:off + nbytes]; off += nbytes + ((-nbytes) % 8)
        assert dtype == 14                                       # miMATRIX
        p = 0

        def take():
            nonlocal p
            t, n = struct.unpack("<II", body[p:p + 8]); p += 8
            d = body[p:p + n]; p += n + ((-n) % 8)
            return t, d

        _, flags = take(); cls = struct.unpack("<II", flags)[0] & 0xFF
        _, dims_b = take(); d0, d1 = struct.unpack("<ii", dims_b)
        _, name_b = take(); name = name_b.decode("ascii")
        _, real = take()
        out[name] = real.decode("utf-16-le") if cls == 4 else np.frombuffer(real, "<f8").reshape(d0, d1)
    return out


def test_write_mat_roundtrips_array_scalar_and_string(tmp_path):
    p = str(tmp_path / "x.mat")
    write_mat(p, {"v_leader": np.array([1.0, 2.0, 3.0]), "s_init": 12.5, "name": "myrun"})
    got = _read_mat(p)
    assert np.allclose(got["v_leader"].ravel(), [1.0, 2.0, 3.0])
    assert np.allclose(got["s_init"].ravel(), [12.5])
    assert got["name"] == "myrun"


def test_write_mat_matches_the_v5_spec_bytes(tmp_path):
    p = str(tmp_path / "y.mat")
    write_mat(p, {"v": np.array([1.0, 2.0])})
    raw = (tmp_path / "y.mat").read_bytes()
    assert len(raw) >= 128
    assert raw[124:128] == struct.pack("<HH", 0x0100, 0x4D49)    # version 0x0100 + endian 'IM'
    assert struct.unpack("<I", raw[128:132])[0] == 14           # first element tag = miMATRIX
    # first sub-element (array flags) carries the class byte: mxDOUBLE_CLASS = 6
    flags_val = struct.unpack("<I", raw[128 + 8 + 8:128 + 8 + 8 + 4])[0]
    assert (flags_val & 0xFF) == 6
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_mat_writer.py -q -p no:cacheprovider
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.mat_writer'`.

- [ ] **Step 3: Implement the writer**

Create `sim/mat_writer.py`:
```python
"""A minimal, dependency-free MAT-file Level-5 writer (scipy is absent in this env, and its LAPACK pull-in is
the OMP #15 abort we avoid). Serialises a flat {name: value} dict as top-level variables, so MATLAB
`load('f.mat')` binds each name in the workspace. Supports float64 arrays, real scalars, and strings -- the
only types a leader-kinematics export needs. Everything is little-endian; every element is 8-byte aligned."""
import struct

import numpy as np

_MI_INT8, _MI_INT32, _MI_UINT16, _MI_UINT32, _MI_DOUBLE, _MI_MATRIX = 1, 5, 4, 6, 9, 14
_MX_CHAR, _MX_DOUBLE = 4, 6


def _element(dtype, data):
    """An 8-byte tag [type, nbytes] + data padded up to an 8-byte boundary."""
    return struct.pack("<II", dtype, len(data)) + data + b"\x00" * ((-len(data)) % 8)


def _matrix(name, value):
    if isinstance(value, str):
        cls, dims, real = _MX_CHAR, (1, len(value)), _element(_MI_UINT16, value.encode("utf-16-le"))
    else:
        arr = np.asarray(value, dtype="<f8")
        cls = _MX_DOUBLE
        dims = (1, 1) if arr.ndim == 0 else (1, arr.size)
        real = _element(_MI_DOUBLE, arr.tobytes())
    flags = _element(_MI_UINT32, struct.pack("<II", cls, 0))         # array flags (class in the low byte)
    dim_e = _element(_MI_INT32, struct.pack("<ii", dims[0], dims[1]))
    name_e = _element(_MI_INT8, name.encode("ascii"))
    return _element(_MI_MATRIX, flags + dim_e + name_e + real)


def write_mat(path, variables):
    """Write {name: np.ndarray | float | int | str} to a Level-5 .mat file at `path`."""
    text = b"MATLAB 5.0 MAT-file, cf_sim scenario export"
    header = text.ljust(116, b" ") + b"\x00" * 8 + struct.pack("<HH", 0x0100, 0x4D49)
    with open(path, "wb") as f:
        f.write(header)
        for name, value in variables.items():
            f.write(_matrix(name, value))
```

- [ ] **Step 4: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_mat_writer.py -q -p no:cacheprovider
```
Expected: `2 passed`.

- [ ] **Step 5: Sabotage, watch the guard fail, revert**

In `_matrix`, change `_MX_DOUBLE` in the double branch to `99` (an invalid class). Re-run: expected FAIL on
`test_write_mat_matches_the_v5_spec_bytes` (`(flags_val & 0xFF) == 6` now sees 99). This proves the test
checks the class byte against the spec. **Revert**; re-run → `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add sim/mat_writer.py tests/test_sim_mat_writer.py
git commit -m "feat(sim): a scipy-free MAT v5 writer for scenario export"
```

---

### Task 2: `sim/scenario_export.py` — leader kinematics + CSV + MAT

**Files:**
- Create: `sim/scenario_export.py`
- Test: `tests/test_sim_scenario_export.py`

- [ ] **Step 1: Write the failing tests** (kinematics + the causal gap check + CSV round-trip + MAT)

Create `tests/test_sim_scenario_export.py`:
```python
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from config import DT                                    # noqa: E402
from sim.scenario import scenario_library                # noqa: E402
from sim.stepper import SimStepper                       # noqa: E402
from sim.scenario_export import (                        # noqa: E402
    leader_kinematics, write_scenario_csv, write_scenario_mat)

_PG = np.array([30.0, 1.5, 5.0, 1.5, 2.0])               # v0, T, s0, a, b -- a reasonable IDM point


def test_leader_kinematics_shapes_and_formulas():
    sc = scenario_library(_PG, N=50)[0]                  # 'following'
    k = leader_kinematics(sc, DT)
    v = np.asarray(sc.v_leader, float)
    assert np.allclose(k["t"], np.arange(v.size) * DT)
    assert np.allclose(k["v_leader"], v)
    assert k["x_leader"][0] == sc.s_init                 # starts at the initial gap
    assert np.allclose(k["a_leader"], np.diff(v, prepend=v[0]) / DT)


def test_x_leader_reproduces_the_stepper_gap():
    sc = scenario_library(_PG, N=100)[0]                 # 'following': no collision
    stepper = SimStepper.from_scenario(None, sc)         # oracle
    res = [stepper.step() for _ in range(sc.v_leader.size)]
    s = np.array([r.s for r in res])                     # gap at each tick (pre-update)
    v_ego = np.array([r.v for r in res])                 # ego speed (pre-update)
    x_leader = leader_kinematics(sc, DT)["x_leader"]
    # integrate the ego with the SAME forward-Euler rule the stepper uses (x_ego[0]=0)
    x_ego = DT * np.concatenate(([0.0], np.cumsum(v_ego[1:])))
    assert np.allclose(x_leader - x_ego, s, atol=1e-6)   # gap == x_leader - x_ego, faithfully


def test_csv_roundtrips_the_four_columns(tmp_path):
    sc = scenario_library(_PG, N=40)[0]
    p = str(tmp_path / "s.csv")
    write_scenario_csv(sc, p, DT)
    data = np.genfromtxt(p, delimiter=",", comments="#", names=True)
    k = leader_kinematics(sc, DT)
    assert np.allclose(data["v_leader"], k["v_leader"])
    assert np.allclose(data["x_leader"], k["x_leader"])
    assert np.allclose(data["a_leader"], k["a_leader"])


def test_mat_export_writes_the_name_and_arrays(tmp_path):
    from tests.test_sim_mat_writer import _read_mat
    sc = scenario_library(_PG, N=30)[0]
    p = str(tmp_path / "s.mat")
    write_scenario_mat(sc, p, DT)
    got = _read_mat(p)
    assert got["name"] == sc.name
    assert np.allclose(got["v_leader"].ravel(), np.asarray(sc.v_leader, float))
    assert np.allclose(got["params_gt"].ravel(), _PG)
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_export.py -q -p no:cacheprovider
```
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.scenario_export'`.

- [ ] **Step 3: Implement the export module**

Create `sim/scenario_export.py`:
```python
"""Export a Scenario as the LEADER kinematics (t, v_leader, x_leader, a_leader) + metadata, in .csv and .mat.

This is the scenario DEFINITION expressed as a runnable leader trajectory -- enough to drive an ego in closed
loop downstream and recompute gap and closing speed. x_leader integrates v_leader with the SAME forward-Euler
rule the engine uses for the gap (stepper.py:88), anchored at s_init, so gap = x_leader - x_ego with
x_ego(0)=0. Pure (no Qt). The .mat path uses the dependency-free writer (scipy is absent)."""
import numpy as np

from config import DT
from sim.mat_writer import write_mat


def leader_kinematics(scenario, dt=DT):
    v = np.asarray(scenario.v_leader, dtype=float)
    t = np.arange(v.size) * dt
    x = float(scenario.s_init) + dt * np.concatenate(([0.0], np.cumsum(v)[:-1]))   # forward Euler, x[0]=s_init
    a = np.diff(v, prepend=v[0]) / dt                                              # backward diff, a[0]=0
    return {"t": t, "v_leader": v, "x_leader": x, "a_leader": a}


def scenario_metadata(scenario, dt=DT):
    v = np.asarray(scenario.v_leader, dtype=float)
    meta = {"name": scenario.name, "dt": float(dt), "N": int(v.size),
            "s_init": float(scenario.s_init), "v_init": float(scenario.v_init),
            "params_gt": np.asarray(scenario.params_gt, dtype=float)}
    if scenario.cut_in is not None:
        meta["cut_in"] = np.asarray(scenario.cut_in, dtype=float)
    return meta


def write_scenario_csv(scenario, path, dt=DT):
    k = leader_kinematics(scenario, dt)
    m = scenario_metadata(scenario, dt)
    pg = m["params_gt"]
    cols = np.column_stack([k["t"], k["v_leader"], k["x_leader"], k["a_leader"]])
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(f"# scenario: {m['name']}\n")
        f.write(f"# dt={m['dt']} N={m['N']} s_init={m['s_init']} v_init={m['v_init']}\n")
        f.write(f"# params_gt: v0={pg[0]} T={pg[1]} s0={pg[2]} a={pg[3]} b={pg[4]}\n")
        if "cut_in" in m:
            f.write(f"# cut_in: {m['cut_in'][0]},{m['cut_in'][1]}\n")
        f.write("t,v_leader,x_leader,a_leader\n")
        np.savetxt(f, cols, delimiter=",")


def write_scenario_mat(scenario, path, dt=DT):
    k = leader_kinematics(scenario, dt)
    m = scenario_metadata(scenario, dt)
    variables = {**k, "name": m["name"], "dt": m["dt"], "N": float(m["N"]),
                 "s_init": m["s_init"], "v_init": m["v_init"], "params_gt": m["params_gt"]}
    if "cut_in" in m:
        variables["cut_in"] = m["cut_in"]
    write_mat(path, variables)
```

- [ ] **Step 4: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_export.py -q -p no:cacheprovider
```
Expected: `4 passed`.

- [ ] **Step 5: Sabotage the x_leader formula, watch the causal test fail, revert**

In `leader_kinematics`, change `np.cumsum(v)[:-1]` to `np.cumsum(v)` (drop the one-step shift). Re-run
`tests/test_sim_scenario_export.py::test_x_leader_reproduces_the_stepper_gap`: expected FAIL (the gap no
longer reconstructs). This proves the test pins the exact Euler alignment. **Revert**; re-run → `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add sim/scenario_export.py tests/test_sim_scenario_export.py
git commit -m "feat(sim): export a scenario's leader kinematics to CSV/MAT (gap-faithful)"
```

---

### Task 3: name a scenario in the builder

**Files:**
- Modify: `sim/ui/scenario_page.py` (imports, `__init__` controls near `:134`, `_on_use` at `:519-522`)
- Test: `tests/test_sim_scenario_page_name.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sim_scenario_page_name.py`:
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

from sim.ui.scenario_page import ScenarioPage            # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _page_with_a_block(qapp):
    page = ScenarioPage(np.array([30.0, 1.5, 5.0, 1.5, 2.0]))
    page._on_add()                                        # add one block so _on_use will emit
    return page


def test_name_field_sets_the_emitted_scenario_name(qapp):
    page = _page_with_a_block(qapp)
    got = []
    page.sigScenarioBuilt.connect(lambda sc: got.append(sc))
    page._name_edit.setText("myrun")
    page._on_use()
    assert got and got[-1].name == "myrun"


def test_empty_name_autogenerates_a_unique_name(qapp):
    page = _page_with_a_block(qapp)
    got = []
    page.sigScenarioBuilt.connect(lambda sc: got.append(sc))
    page._name_edit.setText("")
    page._on_use()
    page._on_use()
    assert got[0].name == "scenario_1" and got[1].name == "scenario_2"
```

> Confirmed: `ScenarioPage(params_gt, N=600)` (`scenario_page.py:105`) and `_on_add()` (`:490`). If `_on_add`
> on a fresh page needs a kind/preset selected first, mirror the working setup in the existing builder tests
> in `tests/test_sim_ui_smoke.py` (grep `_on_add`). Do not invent an API.

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_page_name.py -q -p no:cacheprovider
```
Expected: FAIL — `AttributeError: 'ScenarioPage' object has no attribute '_name_edit'`.

- [ ] **Step 3: Add the name field + counter, and use it in `_on_use`**

In `sim/ui/scenario_page.py`, ensure `QLineEdit` is imported (add it to the existing
`from PySide6.QtWidgets import (...)` line) and `replace` is imported (`from dataclasses import replace` — it
is already present from builder-UX; confirm). In `__init__`, near the `self._use` button (`:134`), add:
```python
        self._name_edit = QLineEdit(); self._name_edit.setPlaceholderText("nome scenario")
        self._built_count = 0
```
and include `QLabel("nome"), self._name_edit` in the controls tuple that starts at `:136` (put them right
before `self._use`). Then replace `_on_use` (`:519-522`):
```python
    def _on_use(self):
        if self._spec is None or not self._spec.blocks:
            return
        self._built_count += 1
        name = self._name_edit.text().strip() or f"scenario_{self._built_count}"
        spec = replace(self._spec, name=name)
        self.sigScenarioBuilt.emit(materialise(spec, self._params_gt, self._total_ticks()))
```

- [ ] **Step 4: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_page_name.py -q -p no:cacheprovider
```
Expected: `2 passed`.

- [ ] **Step 5: Sabotage, watch the guard fail, revert**

In `_on_use`, replace `name = self._name_edit.text().strip() or ...` with `name = self._spec.name` (ignore the
field). Re-run: expected FAIL on `test_name_field_sets_the_emitted_scenario_name` (the emitted name is not
"myrun"). **Revert**; re-run → `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add sim/ui/scenario_page.py tests/test_sim_scenario_page_name.py
git commit -m "feat(sim): name a scenario in the builder (empty -> auto scenario_N)"
```

---

### Task 4: delete + export from the live selector

**Files:**
- Modify: `sim/ui/app.py` (imports `:11`, docstring `:2`, `__init__` scenario setup `:68-70` + controls
  `:149-154`, new handlers)
- Test: `tests/test_sim_app_lifecycle.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sim_app_lifecycle.py`:
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

from sim.ui.app import SimApp                             # noqa: E402
from sim.scenario import manual_scenario                  # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _append_user_scenario(win, name="mine"):
    sc = win._scenarios[0]
    win._on_scenario_built(manual_scenario(sc.params_gt, sc.v_leader, sc.s_init, sc.v_init, name=name))


def test_delete_removes_a_user_built_scenario_and_keeps_the_library(qapp):
    win = SimApp(CHAMP)
    protected = win._protected_count
    lib_names = [s.name for s in win._scenarios[:protected]]
    _append_user_scenario(win, "mine")
    assert win._current_idx >= protected                  # the new one is selected
    n_before = len(win._scenarios)
    win._delete_scenario()
    assert len(win._scenarios) == n_before - 1
    assert [s.name for s in win._scenarios[:protected]] == lib_names   # library slice untouched (Meso-safe)


def test_delete_refuses_a_protected_index(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)                                 # a library preset
    n = len(win._scenarios)
    win._delete_scenario()
    assert len(win._scenarios) == n                        # refused


def test_delete_action_is_disabled_on_a_protected_index(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._sync_scn_menu()
    assert not win._act_delete.isEnabled()
    _append_user_scenario(win, "mine")                     # selects the user-built one
    win._sync_scn_menu()
    assert win._act_delete.isEnabled()
```

- [ ] **Step 2: Run to verify it fails**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_app_lifecycle.py -q -p no:cacheprovider
```
Expected: FAIL — `AttributeError: 'SimApp' object has no attribute '_protected_count'`.

- [ ] **Step 3: Wire the imports, the protected count, the menu, and the handlers**

In `sim/ui/app.py`:

(a) line 11-13 — add `QMenu, QToolButton` to the QtWidgets import (keep the others):
```python
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
                               QMainWindow, QMenu, QMessageBox, QPushButton, QSlider, QStackedWidget,
                               QToolButton, QVBoxLayout, QWidget)
```

(b) after the panels import block, add:
```python
from sim.scenario_export import write_scenario_csv, write_scenario_mat
```

(c) line 2 docstring — fix the stale dock name (item 1 renamed it): change `Safety, Events, Inspector` to
`Safety, Scenario, Inspector`.

(d) after the manual append (`:70`), capture the protected count (library + the initial manual, i.e. exactly
the set the Meso page was built from):
```python
        self._protected_count = len(self._scenarios)   # library presets + initial manual: Meso indexes these
```

(e) in the controls area (near `:149`, where the row is assembled), build the menu button and add it right
after `self._selector` in the `for w in (...)` tuple:
```python
        self._scn_menu_btn = QToolButton(); self._scn_menu_btn.setText("⋯")
        self._scn_menu_btn.setToolTip("scenario: esporta / elimina")
        self._scn_menu_btn.setPopupMode(QToolButton.InstantPopup)
        _scn_menu = QMenu(self._scn_menu_btn)
        self._act_export = _scn_menu.addAction("Esporta…"); self._act_export.triggered.connect(self._export_scenario)
        self._act_delete = _scn_menu.addAction("Elimina"); self._act_delete.triggered.connect(self._delete_scenario)
        _scn_menu.aboutToShow.connect(self._sync_scn_menu)
        self._scn_menu_btn.setMenu(_scn_menu)
```
(add `self._scn_menu_btn` to the controls tuple right after `self._selector`.)

(f) add the three handlers (anywhere among the methods, e.g. after `select_scenario`):
```python
    def _sync_scn_menu(self):
        self._act_delete.setEnabled(self._current_idx >= self._protected_count)

    def _delete_scenario(self):
        idx = self._current_idx
        if idx < self._protected_count:
            return                                         # library + initial manual: Meso selects these by index
        self._scenarios.pop(idx)
        self._selector.blockSignals(True)
        self._selector.removeItem(idx)
        self._selector.blockSignals(False)
        self.select_scenario(min(idx, len(self._scenarios) - 1))

    def _export_scenario(self):
        sc = self._scenarios[self._current_idx]
        path, _ = QFileDialog.getSaveFileName(self, "Esporta scenario", f"{sc.name}.csv",
                                              "CSV (*.csv);;MATLAB (*.mat)")
        if not path:
            return
        if path.lower().endswith(".mat"):
            write_scenario_mat(sc, path)
        else:
            write_scenario_csv(sc, path)
```

- [ ] **Step 4: Run to verify it passes**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_app_lifecycle.py -q -p no:cacheprovider
```
Expected: `3 passed`.

- [ ] **Step 5: Sabotage the delete guard, watch it fail, revert**

In `_delete_scenario`, change `if idx < self._protected_count:` to `if False:`. Re-run
`tests/test_sim_app_lifecycle.py::test_delete_refuses_a_protected_index`: expected FAIL (a library preset gets
deleted). This proves the guard protects the Meso-indexed set. **Revert**; re-run → `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add sim/ui/app.py tests/test_sim_app_lifecycle.py
git commit -m "feat(sim): delete + export a scenario from the live selector"
```

---

### Task 5: full suite, functional-verify, docs

**Files:**
- Modify: `document/SIMULATOR_ARCHITECTURE.md`, `document/SIMULATOR_SESSION_RESUME.md`

- [ ] **Step 1: Full suite + invariants untouched**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -q -p no:cacheprovider
git diff --stat 5bb3c56d -- sim/state.py sim/stepper.py sim/backend.py sim/probe.py sim/events.py sim/eventprop_stepper.py utils/closed_loop_eval.py sim/scenario_spec.py
```
Expected: `B+~11 passed` (baseline + the new tests); the diff-stat prints **nothing** (frozen core +
closed_loop_eval + scenario_spec untouched). ≥420 s or background.

- [ ] **Step 2: Functional-verify the export (and the MATLAB caveat)**

Write a throwaway scratchpad script (`QT_QPA_PLATFORM=windows`) that builds `SimApp(CHAMP)`, exports scenario
0 to a temp `.csv` and `.mat`, prints the CSV's first ~6 lines, and round-trips the `.mat` via
`tests.test_sim_mat_writer._read_mat` (confirm `name`, `v_leader`, `params_gt`). **Automated validation is
structural + round-trip only** — there is no MATLAB/scipy in this env, so the `.mat` is not checked against a
real MATLAB reader here. The user has MATLAB; a one-line `load('scenario.mat')` on their side is the final
confirmation (note this in the report). Delete the script after.

- [ ] **Step 3: Update the docs**

`document/SIMULATOR_ARCHITECTURE.md`: add `sim/scenario_export.py` and `sim/mat_writer.py` rows to the
scenario-stack module map (pure, no Qt; the MAT writer is the isolated binary-format unit); note the
selector's "⋯" menu (export/delete, protected count) in the app.py line; bump the test count to the real
number. `document/SIMULATOR_SESSION_RESUME.md`: mark item 2 done with the real count and commits; note export
= leader kinematics (`x_leader` gap-faithful), naming session-only, delete user-built only (Meso-safe), the
scipy-free MAT writer; leave item 7 (dataset generator) as the last queued draft.

- [ ] **Step 4: Commit + push**

```bash
git add document/SIMULATOR_SESSION_RESUME.md document/SIMULATOR_ARCHITECTURE.md
git commit -m "docs(sim): resume + map -- scenario lifecycle (item 2) done"
git push origin Simulator
```

- [ ] **Step 5: Report — do NOT merge to main**

Report cycle complete. Merge → main stays **parked** (sequenced behind Simulink_Importer). Per
executing-plans, invoke finishing-a-development-branch only to present options — do not auto-merge.

---

## Self-review (against the spec)

- **Spec §Design "pure export core"** → Task 2 (`leader_kinematics`/`scenario_metadata`/CSV/MAT, exact
  formulas). ✓
- **Spec §Design "scipy-free MAT v5 writer"** → Task 1 (concrete encoding + spec-byte assertions + paired
  reader). ✓
- **Spec §Design "UI wiring" naming** → Task 3 (`_name_edit`, `_built_count`, `replace(spec, name=…)`). ✓
- **Spec §Design "UI wiring" delete/export** → Task 4 (`⋯` menu, `_protected_count`, guarded delete, suffix
  dispatch). ✓
- **Spec §Decisions ② `x_leader` from `s_init`** → Task 2 formula + the causal test. ✓
- **Spec §Decisions ④ delete user-built only / Meso-safe** → Task 4 tests (refuse protected, library slice
  preserved). ✓
- **Spec §Testing "x_leader reproduces the gap"** → Task 2 `test_x_leader_reproduces_the_stepper_gap`
  (computed from a real stepper run). ✓
- **Spec §Testing ".mat round-trip + spec bytes"** → Task 1 both tests. ✓
- **Spec §Invariants** → Task 5 Step 1 diff-stat gate (base `5bb3c56d` = the last item-1 commit). ✓
- **Placeholder scan:** none — every code step is complete. The one soft spot (Task 3's `ScenarioPage`
  constructor) has an explicit "mirror the existing builder tests, don't invent an API" instruction. ✓
- **Type/name consistency:** `leader_kinematics`/`write_scenario_csv`/`write_scenario_mat`/`write_mat`/
  `_protected_count`/`_act_delete`/`_sync_scn_menu`/`_delete_scenario`/`_export_scenario`/`_name_edit`/
  `_built_count` are identical across tasks and their tests. ✓
