# CF_FSNN Simulator — how to run

A live "digital twin" GUI of the SNN car-following controller: **Live** cockpit (14 docks) ·
**Meso/Macro** analysis (platoon string-stability, fundamental diagram, road view) · **Post-run**
report card (identification, safety, energy, ρ — with '?' formula tooltips).
Stack: PySide6 6.11 + pyqtgraph 0.14 + torch (CPU) + numpy.

## Quick start (Windows) — recommended: conda

1. Install **Miniconda** if you don't have it: <https://docs.conda.io/en/latest/miniconda.html>
2. Double-click **`run_simulator.bat`**.
   - First run creates the `cf_sim` conda env from `environment.yml` (a few minutes) and launches.
   - Subsequent runs start immediately.
3. Optional: `run_simulator.bat path\to\champion.pt` to launch a specific champion
   (default: `champions\R33_C2_A1_T12_fix\best_model.pt`).

**Why conda, not a plain pip venv:** on Windows the *pip* PySide6 wheel fails to load Qt6Core
(`DLL load failed`) unless a recent **Microsoft Visual C++ redistributable** is installed system-wide;
*conda-forge* PySide6 bundles its own Qt + runtime, so it works out of the box. The launcher also
disables a redundant `libomp.dll` to avoid the OpenMP **Error #15** clash (torch/MKL already ship
Intel's OpenMP runtime).

## pip fallback (only if the VC++ redistributable is already installed)

    python -m venv .venv-sim
    .venv-sim\Scripts\pip install -r requirements-sim.txt
    .venv-sim\Scripts\python scripts\run_simulator.py

If you hit `ImportError: DLL load failed while importing QtCore`, install the **Microsoft Visual C++
Redistributable (x64)** and retry — or use the conda path above.

## Manual launch (env already created)

    conda run -n cf_sim python scripts/run_simulator.py [champion.pt]

## Tests

    conda run -n cf_sim python -m pytest tests/test_sim_state.py tests/test_sim_ui_smoke.py tests/test_sim_episode.py tests/test_sim_postrun.py -q
    # (list the test_sim_*.py files explicitly; non-sim tests aren't meant to run in this env)
