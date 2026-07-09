# Simulator Extension — Design Study (customizable cockpit + dashboards)

> Reasoning-phase design study. **No implementation.** Produced by a 6-agent research
> workflow (4 parallel scouts → synthesis → adversarial critique), then **narrowed by
> user decisions** (see §0). All proposed changes are scoped to `sim/ui/*`; the
> golden-tested headless core (`sim/state.py`, `sim/stepper.py`, `sim/backend.py`,
> `sim/events.py`, `sim/probe.py`, `sim/replay.py`, `sim/eventprop_stepper.py`) is a
> frozen contract.

---

## 0. USER DECISIONS & CORRECTIONS (2026-07-07) — read first

These override the raw study below where they conflict.

1. **Scope = LIVE only.** The simulator is a **live instrument** for one running episode
   (+ optionally a post-run summary of *that* episode). **No** offline/batch "Analysis
   mode", **no** report-browser over `results/evaluate/`. The offline analyses stay where
   they are. → Drop §4's OFFLINE dashboard family and the separate Analysis mode.
2. **The simulator is DECOUPLED from the FPGA.** The study's "CSV golden-vector export as
   an FPGA-validation contract" framing was wrong for this tool — that belongs to the
   Simulink_Importer / FPGA phase, not the sim. → If any export exists it is a **generic
   "save what you see"** (CSV/PNG), not an FPGA contract. (Open: does the user even want
   export? TBD — not a priority.)
3. **Parameter view = just show the 5 produced params clearly, live.** The network emits 5
   params → visualise them per-param in real time, legibly. Whether they differ from the
   "correct" (ground-truth) values because of non-identifiability is **a separate topic**,
   NOT something the live view must editorialise. → Drop the heavy identifiability-badge /
   "refuse to show an error number" machinery. A simple optional GT reference line is fine;
   identifiability analysis (a–b ellipse, FIM) is a *separate* concern, not the live panel's job.
4. **A/B comparison priority = float vs fixed-point.** ⚠️ Note the tension with (2):
   float-vs-fixed is the *quantization* comparison ("does the quantized net still behave the
   same?"). It is SW-simulatable (not FPGA hardware) but requires a **fixed-point (Qm.n) SW
   forward path** that does not exist yet. Later-phase; confirm intent when we get there.
5. **"Must-have dashboards" (decision 5) meant:** of the ~20 candidate panels in §4, which to
   build in the first phases vs defer. Given (1)(3): the near-term set is small — legible
   per-param view + a few LIVE panels (trajectory, safety). See revised roadmap in §6.

**Net effect:** the ambition shrinks from a "grand cockpit + analysis suite" to a
**customizable live UI with legible per-param views and a handful of live panels** — closer
to what the user actually asked for. Recommended first step unchanged: **Phase 1 =
param-legibility drop-in** (§6), zero library risk, delivers the headline ask.

---

## 1. Guiding principle (as researched)

Current UI = fixed vertical stack (`app.py` QVBoxLayout) answering only "is the car driving?"
while richer signals the core already computes (`a_ego`, `dv`, `impact_dv`, `min_gap`,
`params_gt`, full `read_probe()`, `EventInjector._log` / `ReplayLog`) are discarded or crammed
onto shared axes. Target (narrowed per §0): a **customizable live workspace** — a dock-based,
rearrangeable, tear-out, layout-persistable set of panels on one global time index, backed by
the existing ring buffer (`probe.py`, cap 500) so you can pause/scrub and read event → spikes →
param at a frozen `t`.

## 2. Per-parameter visualization

Problem (`netpanel.py:66-69`): 5 different-unit quantities (`v0` m/s, `T` s, `s0` m, `a` m/s²,
`b` m/s²) min-max normalised onto one shared 0..1 axis; raw values only in the title; GT
(`params_gt`) never shown.

**Recommendation: 5 linked small-multiples** — one `pg.GraphicsLayoutWidget`, 5 stacked
`addPlot(row=i)`, each `setLabel("left", name, units=…)`, all `setXLink(plot[0])`; feed raw
`pm[:,i]` (no normalization). Each param regains its axis, units, and scale. Double-click →
float one param into its own dock. (Per §0.3: keep it a plain estimate trace; GT as an optional
thin reference; no editorialising badges.)

*Deferred, separate concern (not the live panel):* a–b confidence ellipse / FIM (why a,b don't
separate) — `SIMULATOR_DESIGN.md` §9 EstimationQuality (`least_squares` + JᵀJ + Cramér-Rao).
This is **new estimator code**, not UI.

## 3. Customizable / dockable architecture

**Recommendation: pyqtgraph `DockArea`** (not native `QDockWidget`). The app is pyqtgraph-dominant
(3 PlotWidgets + planned 5-param GraphicsLayoutWidget) + one QGraphicsView (`TopDownView`); there
is no natural "central widget" (road + plots are co-equal). `DockArea` is a QWidget → drops into
`setCentralWidget(...)`; `TopDownView` drops into a Dock unchanged.

Current 4 panels → 4 Docks:
```
QMainWindow
 ├ QToolBar (controls)                 ← controls row (signal wiring untouched)
 ├ setCentralWidget( DockArea )
 │    ├ Dock "Road"   → TopDownView        (unchanged)
 │    ├ Dock "Raster" → spike raster        (closable)
 │    ├ Dock "v_mem"  → v_mem + v_th         (closable)
 │    └ Dock "Params" → 5 linked plots (§2)  (closable)
 ├ menuBar "View" (lazy extra docks) + "Layout" (save/restore presets)
 └ statusBar (unchanged; outside DockArea, cannot be torn off)
```
Free: drag-rearrange, resize, tab-stack (`addDock(d,'above',n)`), tear-out (`dock.float()`),
closable. Layout persistence: `area.saveState()`/`restoreState()` (JSON); ship named presets.

**⚠️ Library risk (mandatory):** pyqtgraph 0.14 has known `restoreState` bugs — GH #2887 (sole-child
container silently drops docks, no exception) and #3125 (`TypeError` on tear-out-then-redock before
save). Mitigate: instantiate all docks *then* restore; unique/stable dock name strings; wrap
`restoreState` in try/except with fallback to a default layout; CI a save→restore round-trip; or pin
a verified-patched 0.14.x. `Dock(size=…)` is a stretch hint (tune with `setStretch()`), not pixels.
Do NOT use `QMdiArea`.

**Migration risk:** all changes in `sim/ui/` only; core untouched; golden `run()` test keeps passing.

## 4. LIVE panels to add (OFFLINE family dropped per §0.1)

The core already computes these but shows none of them:

| Panel | Data source | Note |
|---|---|---|
| **Trajectory: gap / v / a_ego / dv over time** | `StepResult.{s,v,vl,dv,a_ego}` | `a_ego`/`dv` currently shown NOWHERE |
| **Predicted params (5, linked)** | `traj['params']` (+ optional GT ref) | §2 — the headline view |
| **Safety strip: TTC, DRAC, time-headway, brake-margin** | `safety_metrics` formulas (`ttc=s/dv`, `drac=dv²/2s`, `th=s/v`) | TTC currently computed in `ttc_color` then discarded |
| **Comfort: a_ego, jerk vs ISO bands** | `comfort_metrics` (jerk=da/dt); ISO ±2.0/−3.5, |jerk|<2 | bands are constants |
| **Spike-sparsity / firing-% meter** | `read_probe()['spikes']` → firing % , SynOps | always-on network-activity number (the 15%-not-1.5% surprise) |
| **Per-neuron inspector (v_mem, v_th, rate, input current)** | `read_probe()['v_mem','v_th_eff']` (+ input current) | today only 4 of H neurons, cramped; add selection; find dead/saturated neurons |
| **Input-encoding view** (raw s,dv,v → spikes/current) | encoder input vs `read_probe` | where signal→SNN projects silently fail (critique C6) |
| **Event timeline / log (click → seek)** | `EventInjector._log` | fully captured, never displayed; click a brake → scrub to it |
| **Post-run seal (of THIS episode): min_gap, min_ttc, TET/TIT, RMS accel/jerk** | accumulate live, seal at `loop.done` | one-episode scorecard (still "live" tool, not batch) — `min_gap` needs accumulation logic in `sim/ui/loop.py` (not free) |

## 5. Other completeness features (narrowed)

- **Record/replay + scrub** on one global time index (pause, seek to "the instant it braked",
  read event→spike→param). Substrate exists: ring buffer + `ReplayLog` (implemented, **unwired**)
  + `EventInjector._log`. The true unlock. Keyboard shortcuts (Space/←/→) come with it.
- **Champion A/B same-seed overlay** — priority **float-vs-fixed** (§0.4; needs a fixed-point SW path).
- **Live plant/V2X panels** — currently `SimApp` builds the stepper with `plant=None, channel=None`;
  showing a_ego-vs-a_cmd or AoI/packet-loss requires **wiring a plant/channel into the live stepper**
  first (in `sim/ui/app.py`, in-scope but unscoped in the raw study — critique).
- **GT parameter sliders** — drive a changing plant live and watch the net re-identify (good demo).
- **Car color-by-metric** (speed/TTC), generic **CSV/PNG export** (§0.2, not an FPGA contract).
- **Scenario editor = a form** (lead-speed profile, gap, noise, seed), NOT a SUMO/CARLA map editor.

## 6. Revised roadmap (post-decisions)

- **Phase 1 — ✅ DONE (2026-07-08, commits `10b8da4`+`d6200dd`). Param legibility (drop-in `NetPanel`
  replacement).** 5 linked small-multiples in physical units (+ optional GT reference) + a
  spike-sparsity/firing-% readout. Zero dock dependency, zero `restoreState` risk. Delivered exactly the
  headline ask (§0.3, §2). Plan: `docs/superpowers/plans/2026-07-07-simulator-param-legibility.md`;
  46 tests green in `cf_sim`, core golden untouched.
- **Phase 2 — ✅ DONE (2026-07-08, commits `fbb40da`→`24468ae`). Dockable shell.** Migrated `app.py` →
  pyqtgraph `DockArea`; NetPanel dissolved into `panels.py` (Raster/Vmem/Param); **8 docks** (per-param);
  X-link across docks; `layout.py` = 4 presets (Overview/Guida/Identificazione/Neuro-debug) +
  guarded save/restore (fallback Overview); View/Layout menus; firing-% → status bar. Spec
  `docs/superpowers/specs/2026-07-08-simulator-dockable-shell-design.md`, plan
  `docs/superpowers/plans/2026-07-08-simulator-dockable-shell.md`; 57 tests green in `cf_sim`, core golden untouched.
- **NetViz interludes — ✅ DONE (2026-07-08, between Ph2 and Ph3).** (a) Network **state map** (input/hidden/output
  groups, v_mem heat + spike overlay) + **SpikeRate** trend dock, replacing the illegible time-raster (spec
  `2026-07-08-network-state-map-design.md`); (b) that heat-grid then **replaced by a node-link graph** — ✅ **DONE** (commits up to `c4bdde7`)
  (`pg.GraphItem`: layered colored circles + faint weight-skeleton + per-tick **white active-pathway** highlighting
  of edges out of firing neurons — reveals sparse "tragitti" in the spiking net; input/output nodes labelled) —
  spec `2026-07-08-network-graph-design.md`, plan `2026-07-08-network-graph.md`.
- **Phase 3 — Time backbone + live metric docks.**
  - **3a metric docks — ✅ DONE (2026-07-08, commits up to `da9ed27`):** `Trajectory` (gap/speeds/accel) +
    `Safety` (TTC/DRAC/time-headway, threshold refs), fed by a UI-layer `TrajectoryBuffer` of `StepResult`
    (probe untouched) + pure `metrics.py`; 11 docks, presets updated (Guida = driving story). Spec/plan
    `2026-07-08-trajectory-safety-panels*`. 72 tests green.
  - **3b.1 time-scrub core — ✅ DONE (2026-07-08, commits up to `0d09894`):** pause/scrub a global cursor
    over the ring buffer — cursor line on all time-series docks, `NeuronGraphPanel` at `t`, `TopDownView`
    reconstructed to `t`; slider + `Space`/`←`/`→`/`Home`/`End`. Spec/plan `2026-07-08-scrub-core*`. 77 tests green.
  - **3b.2 event-timeline + 3b.3 inspector + replay-beyond-buffer — ✅ DONE (2026-07-09, commits up to `5f05882`):**
    (1) `reconstruct_history` (`sim/ui/reconstruct.py`) deterministically re-runs the episode from the
    `ReplayLog` into full-length `AttributeProbe`/`TrajectoryBuffer` (same types → panels unchanged),
    **bit-identical** to the live run (golden-tested on the buffer overlap). On pause, if the ring buffer
    wrapped, the app swaps its `_src_probe/_src_traj` scrub source to the reconstructed full episode → scrub
    the whole 0..N run, not just the last 500 ticks. (2) `EventTimelinePanel` (dock "Events") — clickable
    `brake_leader` marks (store the absolute tick), click → pause+seek. (3) `NeuronInspectorPanel` (dock
    "Inspector") — selected neuron's `v_mem`/threshold/spike scope over the source + dominant-connection
    readout; `NeuronGraphPanel.sigNeuronClicked`/`highlight` colour its fan-in/out edges. 13 docks; presets
    updated (Neuro-debug foregrounds Inspector+Events). Spec/plan `2026-07-09-scrub-events-inspector*`. 83 sim tests green; core frozen (reconstruct read-only).
  - **BACKLOG (deferred, user 2026-07-08): instantaneous energy / SynOps dock.** Completes the SpikeRate
    view. Energy/tick ≈ Σ(fan-out of firing neurons) — derivable from `spikes` + the NetGraph topology
    (already extracted for the graph edges). TBD how to surface: a number in the SpikeRate dock, or its own
    small dock. Design when we get to Phase 3a/b.
- **Phase 4 — Post-run seal (one episode) + float-vs-fixed A/B + optional export.** Fixed-point SW
  model path; same-seed overlay; generic CSV/PNG.
- **Phase 5 (ambitions).** GT sliders / live UKF re-identification, video/GIF, scenario form editor,
  a–b ellipse (separate estimator module), optional QThread worker.

Each phase = its own design+plan cycle later.

---

## APPENDIX A — full synthesis (raw, pre-narrowing)

*(The synthesis assumed an FPGA-facing, analysis-mode-inclusive cockpit; §0 narrows it. Kept for
completeness.)*

Key points not already folded above: three modes on one time base (live / post-run seal / analysis);
the LIVE-vs-POST-RUN-vs-OFFLINE classification of every offline metric; "the sim generates one episode,
it must never pretend to render a batch it didn't run"; layout presets ("Driving", "Neuro-debug",
"Identification"); FIM/Cramér-Rao a–b ellipse as the identifiability payoff.

## APPENDIX B — adversarial critique (kept)

- **Missing (high value):** input-encoding visualizer; GT parameter sliders (interactive
  "track a changing plant"); live plant/V2X need wiring (`plant=None,channel=None` today);
  car color-by-metric; keyboard shortcuts (mandatory with scrub); per-neuron **input current**;
  live `min_gap`/`impact_dv` accumulation.
- **Weak/risky:** "UI-only" is overclaimed for a–b ellipse + UKF (new estimator code, not docks);
  energy-meter conflates SynOps (LIVE) with advantage-vs-ANN (POST-RUN, needs a fixed baseline);
  `min_gap` isn't in `StepResult` (needs new accumulation, not free surfacing); Phase 1 bundled
  too much (dock migration + param rewrite + badges + presets couples the certain win to the risky
  dependency); Option B / 4 presets are speculative (YAGNI).
- **Sequencing:** the study contradicts itself (dock-migration "first" vs scrub-backbone "the
  backbone, build first"). Fix (adopted in §6): **param-legibility rewrite first**, decoupled from
  the dock/restoreState gamble; scrub backbone is the true second unlock.
