# Scenario lifecycle — name + delete + export — Design Spec (**DRAFT**)

**Date:** 2026-07-16 · **Branch/worktree:** `Simulator` · **Status:** 🟡 **DRAFT — captured intent, NOT
finalised.** Written now so the design is not lost; to be reviewed and completed via proper brainstorming
when this cycle is implemented (after builder-UX). The forks below are **open**.

## Goal

Give a built scenario a name, and from the cockpit's live selector let the user delete it and export it
(priority formats **.csv** and **.mat**).

The user's item 2: *"vorrei la possibilità di dare un nome allo scenario e oltre a quello, dalla schermata
live dove si seleziona, la possibilità di cancellarlo, ma anche di esportarlo (diversi formati, tra cui
prioritari .csv e .mat)"*.

## Established facts (grounded now)

- **`ScenarioSpec.name` already exists** and flows to the `Scenario` (`materialise` passes `name=spec.name`);
  the builder currently hardcodes `"nuovo"` / `"mio"`. Naming = a text field wired to `spec.name`.
- **The cockpit selector is `self._selector`** (a `QComboBox` of scenario names, `app.py:127`); built
  scenarios are appended via `_on_scenario_built` (`app.py:605`). The first ≥9 are the **library presets**
  (the invariant set the Meso page also lists) — deleting those would break other modes.
- **⚠️ scipy is NOT installed in `cf_sim`** (`ModuleNotFoundError`, checked). `.csv` is trivial
  (`csv`/`np.savetxt`). **`.mat` needs a LAPACK-free path** — scipy pulls in `scipy.linalg` → LAPACK →
  the OMP #15 abort this env avoids. See fork ③.

## Scope (provisional)

**IN**
1. **Name** a scenario in the builder (a text field; defaults to a generated name; writes `spec.name`).
2. **Delete** a scenario from the live selector — **user-built only** (library presets protected).
3. **Export** the selected scenario to **.csv** and **.mat**.

**OUT (provisional)** — import; batch export; exporting the run RESULT vs the scenario (see fork ②).

## Recommended design (provisional)

- **Name**: a `QLineEdit` in the builder's controls, next to "Usa questo scenario"; on Use, the emitted
  `Scenario` carries that name. Empty → an auto name (`scenario_1`, …).
- **Delete/Export**: two buttons (or a right-click menu) next to `self._selector`. Delete removes the
  scenario from `_scenarios` + the selector (guarded: index ≥ library count). Export opens a `QFileDialog`
  with `.csv` / `.mat` filters and writes the current scenario.

## Open forks (DECIDE AT IMPLEMENTATION)

- **① What does "export" contain?** The **scenario definition** (the leader profile `v_leader` + `s_init`,
  `v_init`, `params_gt`, `name`) — OR the **run result** (the ego trajectory after running: `s, v, vl,
  a_ego, params` over time). The word "esportarlo" points at the scenario; `.mat` for MATLAB analysis hints
  at the run. *Lean: the scenario definition; the run-result export is a separate later item.*
- **② Delete of a library preset** — protected (recommended), or allowed-but-restorable? *Lean: protected;
  only user-built scenarios are deletable.*
- **③ The `.mat` writer** — scipy is absent and LAPACK-risky. Options: **(a)** a small pure-Python .mat v5
  writer (~60 lines, LAPACK-free, writes a 1-D array + a few scalars — enough for a leader profile);
  **(b)** install scipy after first PROVING `savemat` does not trigger OMP #15 in this env (risky — the
  whole point of the env is no-LAPACK). *Lean: (a), a tiny writer, isolated + tested (a MATLAB round-trip
  fixture).*
- **④ CSV shape** — one column (`v_leader`) with a header, or columns for the full definition? *Lean:
  `tick, v_leader` two columns + a comment header with `s_init/v_init/params_gt/name`.*

## Rough testing sketch

- naming writes `spec.name`; export .csv round-trips the leader profile; the .mat writer produces a file a
  MATLAB reader (or the pure-Python reader) reads back byte-faithfully; delete removes only user-built and
  refuses a library index; the selector stays consistent after delete.
