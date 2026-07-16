# Scenario lifecycle — name + delete + export — Design Spec

**Date:** 2026-07-16 · **Branch/worktree:** `Simulator` · **Status:** ✅ **FINAL — approved.** Supersedes the
DRAFT (`2026-07-16-scenario-lifecycle-DRAFT.md`, removed). Grounded on a full read of the source on
2026-07-16 (every `file:line` verified, not recalled).

## Goal

Give a built scenario a name, and from the cockpit's live selector let the user delete it and export it in
**.csv** and **.mat**. The export is the **leader kinematics** — enough to drive an ego vehicle in closed
loop downstream (e.g. in MATLAB) and recompute Δv and gap.

User's item 2: *"vorrei la possibilità di dare un nome allo scenario e, dalla schermata live dove si
seleziona, la possibilità di cancellarlo, ma anche di esportarlo (diversi formati, tra cui prioritari .csv e
.mat)."* Export content (user, clarified): *"v_leader, posizione leader e accelerazione leader — le cose che
poi permettono di mettere l'ego in closed loop, per calcolarsi deltaV e gap."*

## Decisions (the forks, resolved)

- **① Export = the leader KINEMATICS, not the ego run.** Columns `t, v_leader, x_leader, a_leader` +
  metadata. The ego run RESULT is already exportable (`File → Export CSV`, the episode — `app.py:208,231`);
  item 2 is distinct, so the UI must not collide with it in naming.
- **② `x_leader` starts at `s_init`** (user-confirmed) so `gap = x_leader − x_ego` with `x_ego(0)=0`. `s_init`
  is also in the metadata, so the origin is recoverable either way.
- **③ Naming is session-only**, embedded in the export (persists on disk there). No save/load of the scenario
  list (that would be a separate item).
- **④ Delete is user-built only; library presets are protected.** Not cosmetic: the Meso page selects
  scenarios **by index** into `_scenarios` (`app.py:404`), so deleting a library preset would shift its
  indices and break Meso. Protecting indices `< library_count` keeps Meso valid.
- **⑤ The `.mat` writer is a tiny scipy-free MAT v5 serializer** (scipy is absent — verified
  `ModuleNotFoundError`; there is no `.mat` precedent in the repo). Top-level variables (MATLAB `load` drops
  them in the workspace). Isolated in its own module + tested alone.
- **⑥ UI: one "⋯" menu button** next to the selector → `Esporta…` / `Elimina`. The rename field lives in the
  builder. (The control row is already crowded — `app.py:149-154` — so one menu beats two more buttons.)

## Established facts (grounded, verified this session)

- **`Scenario`** (`sim/scenario.py:14-21`, frozen dataclass): `name` · `params_gt (5,)` · `v_leader (N,)` ·
  `s_init` · `v_init` · `cut_in: (t_cut, new_gap) | None`. That is the whole definition.
- **Naming today**: the builder threads `_spec.name` (hardcoded) through to the emitted `Scenario`
  (`scenario_page.py:519` `_on_use` → `:522` `sigScenarioBuilt.emit(materialise(self._spec, …))`;
  `materialise` passes `name=spec.name`). No name INPUT exists yet.
- **The selector** is `self._selector` (`QComboBox`, `app.py:127`), populated from `[s.name for s in
  self._scenarios]` (`:128`), wired to `select_scenario` (`:199`). `_scenarios` = `scenario_library(...)`
  (`:68`) **+** one appended manual (`:70`); built scenarios are appended via `_on_scenario_built`
  (`:608-617`, which does `_scenarios.append` + `_selector.addItem` + select). `scenario_count()` (`:332`).
- **Gap integration** (`stepper.py:88`): `s_new = st.s + (vl - v_new) * DT` — forward Euler, `s` is the pure
  IDM gap (no separate vehicle length). `DT = 0.1`. The leader acceleration the engine reads is
  `a_l_raw = (vl_obs - st.vl_prev) / DT` (`stepper.py:76`).
- **scipy is absent** in `cf_sim` (verified); `.csv` is trivial, `.mat` needs the scipy-free writer (⑤).

## Scope

**IN**
1. **Name** a scenario in the builder (a `QLineEdit`; empty → auto name; writes the emitted `Scenario.name`).
2. **Delete** the selected scenario from the live selector — user-built only, library protected.
3. **Export** the selected scenario's leader kinematics to `.csv` and `.mat`.

**OUT** — import; save/load of the scenario list (persistence); batch export; exporting the ego run result
(already `File → Export CSV`); rename from the selector (rename is builder-time only).

## Design

### The pure export core — `sim/scenario_export.py`

No Qt. Given a `Scenario` (and `dt=DT`):
- `leader_kinematics(scenario, dt) -> dict` with 1-D float arrays, all length N:
  - `t = arange(N) * dt`
  - `v_leader = asarray(scenario.v_leader, float)`
  - `x_leader = scenario.s_init + dt * concatenate(([0.0], cumsum(v_leader)[:-1]))` — forward Euler, so
    `x_leader[0] = s_init` and `x_leader[k] = x_leader[k-1] + v_leader[k-1]*dt` (faithful to `stepper.py:88`).
  - `a_leader = diff(v_leader, prepend=v_leader[0]) / dt` — backward difference, `a_leader[0]=0` (= `a_l_raw`).
- `scenario_metadata(scenario, dt) -> dict`: `name (str)`, `dt`, `N`, `s_init`, `v_init`,
  `params_gt (5,)`, and `cut_in` as `(t_cut, new_gap)` when present (user-built scenarios have `None`).
- `write_scenario_csv(scenario, path, dt)`: a `#`-commented header (name, dt/N/s_init/v_init, the 5 named
  params, cut_in) + a `t,v_leader,x_leader,a_leader` column header + the rows (`np.savetxt`).
- `write_scenario_mat(scenario, path, dt)`: composes the kinematics + metadata into a flat `{var: value}`
  dict and calls the MAT writer.

### The scipy-free MAT v5 writer — `sim/mat_writer.py`

No Qt, no scipy. `write_mat(path, variables: dict)` serialises a Level-5 MAT-file:
- 128-byte header (descriptive text + version `0x0100` + endian `"MI"`).
- One `miMATRIX` element per variable, top-level, so MATLAB `load('f.mat')` binds each name.
- Value types supported: `np.ndarray` (float64 → `mxDOUBLE_CLASS`, dims from shape, 1-D stored as `[1, n]` or
  `[n, 1]`), python `float`/`int` (1×1 double), `str` (`mxCHAR_CLASS`, UTF-16LE). Each sub-element
  (array-flags, dimensions, name, real-part) is `miXX`-tagged and 8-byte aligned per the spec.
- **The measured-risk piece** (a binary format) → isolated, tested alone: a round-trip through a **minimal
  paired reader** in the test **plus** spot-checks of spec constants (the header magic, `miMATRIX` tag,
  class byte, dimensions) so the round-trip cannot be self-consistently wrong.

### The UI wiring (thin)

- **`scenario_page.py`**: a `QLineEdit` in the controls; `_on_use` reads it → the emitted `Scenario` carries
  that name. Empty → `scenario_<n>`, where `n` is the builder's own build counter (`self._built_count`,
  incremented per `_on_use`) — no app-side knowledge needed, one owner.
- **`app.py`**: a `QToolButton` "⋯" next to `self._selector` with a menu — `Esporta…`
  (`QFileDialog.getSaveFileName` with `CSV (*.csv);;MATLAB (*.mat)`, dispatch on the chosen suffix) and
  `Elimina`. Delete: refuse when `index < library_count` (guard), else pop from `_scenarios` + `_selector`
  and select a valid neighbour. `library_count` is captured once at construction (the initial
  `scenario_library` length, before the manual append).

## Testing

- **`scenario_page`**: the name field writes the emitted `Scenario.name`; empty → the auto name.
- **`scenario_export`** (pure, no Qt): `leader_kinematics` returns the expected `t/v/x/a`;
  **`x_leader` reproduces the sim's gap** — run a real `SimStepper` on the scenario, integrate the ego with
  the same Euler rule, and assert `x_leader − x_ego ≈ s` from the stepper (the causal check, computed from
  the engine, not memorised). `write_scenario_csv` round-trips the four columns.
- **`mat_writer`** (pure): `write_mat` then the paired reader round-trips arrays + a scalar + a string;
  separately assert the header magic and one `miMATRIX`'s class/dims bytes against the MAT v5 spec.
- **`app`**: delete removes only a user-built index, **refuses a library index**, keeps the selector
  consistent, and **Meso still resolves** its by-index scenarios afterwards.
- Core + `utils/closed_loop_eval.py` + `sim/scenario_spec.py` `materialise` untouched.

## Invariants

- Frozen core (`sim/{state,stepper,backend,probe,events,eventprop_stepper}.py`) untouched.
- `utils/closed_loop_eval.py` and `materialise` untouched.
- Runner: the env's python directly (never `conda run`). **Suite = the sim glob**
  (`pytest tests/test_sim_*.py tests/test_champion_io.py`), NOT `pytest tests/` (FPGA scripts abort
  collection). Full suite ~3 min (≥420 s or background).
- No LAPACK / no scipy in `cf_sim`. Render-verify with `QT_QPA_PLATFORM=windows`.
- Commits conventional, **no `Co-Authored-By`**. Merge → main stays parked.
