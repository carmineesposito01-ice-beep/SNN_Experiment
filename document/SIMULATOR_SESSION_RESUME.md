# SIMULATOR_SESSION_RESUME.md — resume the Simulator track without prior context

> **Scope**: in 5 minutes, know **where we are**, **what's done**, **what to do next** on the CF_FSNN
> **Simulator** track. This is the in-repo, version-controlled resume master (the `.claude` memory
> `cf-fsnn-parallel-tracks.md` has the same story in more detail). Update the "Stato attuale" +
> "Cosa fare adesso" sections at each milestone; append to the history log at the bottom.
>
> **NB: this is the `Simulator` branch/worktree.** `document/SESSION_RESUME.md` is a *different*
> track (EventProp study on `main`) — do not confuse them.

---

## 🎯 Stato attuale (2026-07-10)

**Worktree/branch**: `.worktrees/Simulator` on branch **`Simulator`** (it IS a git repo). All work
committed + pushed to `origin/Simulator`. **142 sim tests green.** Core bit-identical.

**What it is**: a live plug&play GUI "digital twin" of the SNN car-following controller (ALIF,
**4 inputs → 32 hidden → 5 params**, po2 weights, target FPGA PYNQ-Z1). **~800 weights** = the
connections (recurrent 32×32 factored low-rank dominates). **4 champions**:
Raffaello(`R33_C2_A1_T12_fix`, BPTT) · Leonardo(`LS3_PEAK_R0_launch_d03`, BPTT) ·
Donatello(`PE_t05_gp0002`, EventProp) · Michelangelo(`A_lr1e2_t06_r16`, EventProp).

**Phases 1–3 DONE + CLOSED**: 14-dock live cockpit (Road · NetState node-link graph · SpikeRate ·
**SynOps→energy (pJ)** · v_mem · Trajectory · Safety · Events · Inspector · 5 param docks), 4 presets,
guarded persistence, **deep-scrub** (pause + global cursor + prefix-splice reconstruct), event-timeline
(click→seek), neuron-inspector (click a neuron → its scope + fan-in/out highlight), champion selector.
Then a **QA + optimization session**: fixed 2 real bugs (top-down speed>1 drift, scrub-source on Step);
perf via a 5-agent workflow — per-paint −30% (NetState freeze/LUT), redraw throttled to ~15fps
(physics/Road stay 30fps), probe getter memo, reconstruct **7.7s→0.74s** (~10×).

**Design phase (current)**:
- ① **Champion selector** — ✅ DONE (`5cd074f`): live-swap the 4 champions; rebuilds backend +
  topology + per-family energy (BPTT rank-8 / EventProp rank-16).
- ② **Meso/Macro analysis mode** — ✅ **DONE** (T1–T5 + **page v2**). Toggle Live↔Meso/Macro; the page =
  a **platoon road view** (N cars coloured by speed, slider + Play, animating the recorded run) on top
  + a 2×2 grid: **string-stability** · **velocity waves v(t)** (stop&go attenuation) · **space-time x(t)**
  · **fundamental diagram Q(ρ)/V(ρ)**. A **scenario selector** drives the platoon head with the chosen
  scenario's `v_leader`. Family-aware batched forward (all 4 champions) via `platoon_eval`'s additive
  `forward=` hook. Commits: T1 `4736b8b` · T2 `e94d10a` · T3 `628c20c` · **T4** `d9b16ff` (fundamental
  diagram; also fixed a latent SpaceTimePanel blank-panel bug) · **v2** `7fc4c2c`→`f003916`
  (`_MultiCurvePanel` base + SpeedWavePanel; params panel + `rec['params']` removed; scenario selector;
  `PlatoonRoadView`). Spec+plan `2026-07-09-meso-macro-analysis-mode*` + `2026-07-10-meso-page-v2*`.
- ③ **Phase 4** — **PARTLY DONE**: **post-run seal + CSV/PNG export** ✅ (`aa656ef`→`3569017`, spec+plan
  `2026-07-10-postrun-mode-export*`). Third mode (Live/Meso-Macro/**Post-run**) with a report card
  (esito·sicurezza·comfort·efficienza·rete) fed by an **incremental `EpisodeSummary`** accumulator
  (`sim/ui/episode.py`, O(1)/tick, no reconstruct) + `PostRunPage` (`sim/ui/postrun_page.py`); **File →
  Export…** (episode CSV + window PNG). The report card is now **EXHAUSTIVE** (spec+plan
  `2026-07-10-postrun-metrics-tooltips*`, commits `578d32f`→`f554896`): identification vs GT · extended
  SSM (brake-margin/DRAC/TET/TIT/impact-Δv, reusing `closed_loop_eval.safety_metrics`/`comfort_metrics`)
  · dead% · **ρ(U·V) via power-iteration** (LAPACK-free) · energy + breakdown — each metric with a **'?'
  definition+formula tooltip**. Reproduces the report verdicts (ρ 2.99/0.05, dead 18.8%/0%, EventProp
  identifies better) with energy **consistent with the SynOps dock** (tested invariant; no n_ticks bug).
  The post-run page is now a **dark pyqtgraph dashboard (v3, `227f46d`)** — a verdict badge + a 3×2 grid
  of cards (Identificazione · Sicurezza · Comfort · Salute rete/FPGA · Efficienza · Andamento), each a
  bold bar/gauge plot that fills the card + the '?'-tooltipped values; ρ gauge on a `[0,max(2,ρ·1.15)]`
  scale with the ρ=1 boundary line (render-verified on both champions: green sliver 0.057 vs red 2.99
  crossing the line). Replaces the bland white columnar card. `set_summary` signature unchanged.
  **REMAINS: float-vs-fixed A/B** (⚠️ needs a fixed-point Qm.n SW forward that does NOT exist yet — maybe
  port from the Simulink_Importer/HDL track).
- **Distribution** ✅ (`48b0333`): **conda `environment.yml` + `run_simulator.bat`** (creates `cf_sim`,
  applies the OMP #15 libomp rename, launches) — the proven plug&play path; `README_SIM.md`;
  `requirements-sim.txt` reclassified as a pip **fallback** (conda-forge PySide6 bundles the MSVC runtime,
  the pip wheel needs a system vc_redist). **PyInstaller .exe deferred** ("dopo").
- **Bug/polish (post-v2)**: end-of-episode **freeze fixed** (`d0a70ec`, auto-stop no longer does the eager
  reconstruct → 784ms→11ms) + **dock maximize** on title double-click (`d4c24fa`).
- **QC HARDENING — 5-round cyclic review+fix** ✅: a deep
  perf/UX/correctness/quality review run as a 4-lens workflow (find + adversarial verify, ≤4 agents), fixed,
  re-reviewed until dry (`89987b8`→`c924147`). **34 confirmed findings fixed**, trend **11→13→6→3→1** (converged). Highlights:
  Meso Run no longer silently freezes (wait cursor + disabled re-entry controls + `ring sweep i/N` progress);
  **Reset/swap now blank the cockpit** (`clear()` per panel) and reset the road ego (no drive-off, no
  scrub-jump); the post-run cards use **honest comparable scales** — Sicurezza/Comfort as a **danger index**
  `[0,2]` with the limit line (min_ttc=∞ reads green, not red), Identificazione as **absolute relative error**
  (matches `id_accuracy`, comparable across champions); **empty episode** shows "nessun episodio" not a fake
  ok; **impact_dv + collision min_gap** recomputed post-update (match the report); energy via **one path**
  (`metrics.synops_breakdown`) with thousands separators; TTC*/DRAC*/ISO imported from the frozen core (DRY);
  **hidden docks skip redraw** (visibility-gated); pen/brush LUTs; shortcut/dock tooltips. Core bit-identical
  throughout; **142 sim tests green** (was 136).

---

## ▶️ Cosa fare adesso (RESUME — pick up at the float-vs-fixed A/B)

Meso/Macro DONE + v2; freeze fixed; dock-maximize added; **Phase 4 post-run seal + export DONE**. Only
one Phase-4 piece remains, then merge:

1. `git -C "<worktree>" status` — must be clean on `Simulator` (pull if a remote is ahead).
2. **Float-vs-fixed A/B** (the last Phase-4 piece): ⚠️ needs a **fixed-point Qm.n SW forward** that does
   NOT exist in the simulator yet — scope it first (maybe port the fixed-point logic from the
   `Simulink_Importer`/HDL track, which already did it for the FPGA). Design-before-code.
3. Then **merge `Simulator`→`main`** (coordinate with the `Simulink_Importer` track).

**Meso page map** (reference): `sim/ui/meso_page.py` (scenario selector + road strip + 2×2 grid) ·
`sim/ui/meso_panels.py` (`_MultiCurvePanel` base → `SpaceTimePanel`/`SpeedWavePanel`, `StringStabilityPanel`,
`FundamentalDiagramPanel`) · `sim/ui/meso_road.py` (`PlatoonRoadView`) · `sim/ui/platoon.py` (family-aware
`run_platoon`/`run_ring`/`run_fundamental_diagram`). Launch: `conda run -n cf_sim python scripts/run_simulator.py [champion.pt]`.

---

## 🛠️ How to work (setup + discipline)

- **Env**: `cf_sim` (conda). Tests/GUI: `conda run -n cf_sim python ...`.
- **Tests**: run the 20 `test_sim_*.py` files **explicitly** (non-sim tests fail in cf_sim): `state
  backend stepper scenario events probe replay loop eventprop input_capture trajectory layout panels
  ui_smoke reconstruct platoon meso_panels meso_road episode postrun`. **136 green at 2026-07-10.**
- **Test runner gotcha**: `conda run -n cf_sim python -m pytest …` **intermittently crashes conda's
  plugin system**. Reliable bypass — call the env python directly with `Library/bin` on PATH:
  `ENV=C:/Miniconda/envs/cf_sim; PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m
  pytest tests/test_sim_postrun.py -q`.
- **Render**: write a scratchpad script with `os.environ["QT_QPA_PLATFORM"]="windows"`, build `SimApp`,
  drive it, `win.grab().save(png)`, then Read the png. Use `offscreen` for headless tests.
- **Do NOT** `conda run -n cf_sim python -c "..."` inline (plugin/quoting crash) → write a script file.
- **Design-before-code**: brainstorming → spec (`docs/superpowers/specs/`) → plan
  (`docs/superpowers/plans/`) → TDD (RED→GREEN→commit). Commits **without** `Co-Authored-By`. Push freely.

---

## ⚠️ GOTCHAS (cf_sim environment)

- **OMP Error #15 (hard abort)**: two OpenMP runtimes (Intel `libiomp5md` from torch/MKL vs LLVM
  `libomp`). Permanent fix in place: `C:\Miniconda\envs\cf_sim\Library\bin\libomp.dll` renamed
  `libomp.dll.disabled`. If a conda op restores it, the GUI crashes → rename it again.
- **NO numpy LAPACK in cf_sim**: `np.linalg.matrix_rank`, `np.polyfit`, `lstsq`, SVD → **OMP #15 abort**
  (numpy's *own* bundled OpenMP, distinct from the Qt/libomp shim). The test suite never calls LAPACK so
  it stays green, but these crash the app at runtime. Use LAPACK-free alternatives (rank from
  `rec_V.shape[0]`; a degree-1 slope computed by hand — both already done in the code).
- **Golden bit-identity**: the frozen core must stay byte-identical. After any additive core touch,
  re-run the full sim suite.

---

## 🧱 Architecture (file map)

- **FROZEN CORE** (golden bit-identical): `sim/{state,stepper,backend,events,probe,eventprop_stepper}.py`.
  Only additive READ-ONLY accessors were added (`read_weights["rank"]`, probe version-memo,
  `AttributeProbe.from_frames`, `TrajectoryBuffer.results/from_results`). `record()`/`step()`/`infer()`
  bodies untouched.
- **Live UI**: `sim/ui/{app,panels,layout,topdown,trajectory,metrics,reconstruct,loop,theme}.py`.
  `app.py::SimApp` = 14-dock DockArea + champion/scenario selectors + mode toggle; `panels.py` = all
  live panels (NeuronGraphPanel, SynOpsPanel=energy, ParamPanel, Trajectory/Safety, EventTimeline,
  NeuronInspector, SpikeRate, Vmem).
- **Meso/Macro**: `sim/ui/{meso_page,meso_panels,platoon}.py`. **Reuses `utils/platoon_eval.py`**
  (validated, report-grade): `simulate_platoon`/`platoon_metrics` (MESO string stability),
  `simulate_ring`/`fundamental_diagram` (MACRO fundamental diagram, Edie). `sim/ui/platoon.py` adds the
  family-aware **batched forward** (BPTT `forward_step` / EventProp `EventPropStepper.reset(N)+step`,
  both batch over N vehicles) injected via `platoon_eval`'s additive `forward=` hook (reports unaffected).
- **Energy** (`metrics.py`): `synops`/`synops_series`/`dense_mac` (op counts) + `ann_mac` (dense-RNN
  equivalent, full H·H) + `E_AC_PJ=0.9`, `E_MAC_PJ=4.6` (Horowitz 45nm). SynOps dock plots pJ:
  SNN (SynOps×E_AC) vs dense-ANN (ann_mac×E_MAC) → ~14.5× (Raffaello), ~7.9× (Donatello).
- **Docs**: roadmap `docs/superpowers/2026-07-07-simulator-extension-study.md`; QA/perf report
  `docs/superpowers/2026-07-09-phase3-qa-perf-report.md`; one spec+plan per phase in `specs/`+`plans/`.
- **Launch GUI**: `conda run -n cf_sim python scripts/run_simulator.py [champion.pt]`.

---

## 📜 Phase history (Simulator track)

- **MVP (Plans 1–4, 2026-07-06/07)**: `sim/` headless core + `SimStepper` (bit-identical refactor of
  `closed_loop_eval.simulate`) + `SoftwareBackend` (family-aware) + `AttributeProbe`/`ReplayLog` + UI
  (topdown, panels, DockArea app).
- **EventProp live (2026-07-07)**: `EventPropStepper` (stateful per-tick, golden == `forward_sequence`);
  all 4 champions run live.
- **Extension**: Ph1 param legibility · Ph2 dockable shell (presets + persistence) · Ph3a.0 raster/perf ·
  NetViz (state map → node-link graph) · Ph3a Trajectory+Safety · Ph3b.1 scrub · **3b-rest** deep-scrub
  + event-timeline + inspector · **SynOps→energy dock** · **QA + optimization** · **champion selector**.
- **Meso/Macro mode** ✅ (T1–T5 `4736b8b`→`628c20c`,`d9b16ff` + **page v2** `7fc4c2c`→`f003916`:
  `_MultiCurvePanel` base + velocity-wave `v(t)` panel replacing params, scenario selector driving the
  platoon head, `PlatoonRoadView` N-car road with slider+Play) + freeze-fix + dock-maximize +
  **Phase 4 post-run seal + export** (`aa656ef`→`3569017`) → **NOW: Phase 4 float-vs-fixed A/B** → **merge to main**.
