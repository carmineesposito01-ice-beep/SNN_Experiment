# MPC vs SNN Car-Following — Comparison Study (design spec)

> **Date:** 2026-07-13 · **Track:** `Simulink_Importer` · **Status:** DESIGN APPROVED via brainstorming —
> ready for `writing-plans` on **Phase A**. Produced by a one-question-at-a-time brainstorming session.
> This spec defines the **whole study** and the **contracts between its phases**; each phase then gets its
> own spec+plan cycle. **Purpose = a thesis/report-grade comparison** (maximum rigour on fairness,
> metrics, and reproducibility).

---

## 1. Objective & thesis

Compare two **fundamentally different** longitudinal car-following controllers — an **online MPC** and our
**SNN** — as a **cost–performance Pareto**, on **two planes**:

1. **Behavioural plane (Simulink + MATLAB)** — do they *drive* comparably, each with its own internal
   model, over the same plant and scenarios?
2. **Hardware plane (FPGA)** — what does each *paradigm cost in silicon* (resources, timing, latency,
   energy), realized on the same device class?

**Thesis under test:** *Donatello (our EventProp SNN, realized as the HDL-ready B2 architecture on a
sub-mW FPGA) achieves MPC-comparable closed-loop car-following behaviour at a fraction of the FPGA
cost/energy — and the two paradigms differ sharply in FPGA-implementability itself (fixed-latency
feed-forward vs iterative-QP).*

We are **not** forcing algorithmic equivalence. The MPC works by receding-horizon optimisation over its
own model; the SNN works by learned per-instant parameter identification. **We care about the outcomes**
(behaviour + hardware cost), precisely because the principles are different.

### Honest control-architecture framing

- **Our controller** = `SNN → 5 IIDM parameters (v0,T,s0,a,b) → ACC-IIDM acceleration law → a_cmd`. The
  SNN is a **parameter identifier**; the *controller* is SNN+IIDM. (ACC-IIDM coolness c≈0.99.)
- **MPC controller** = `state → online QP/NLP → a_cmd`.
- Both emit an **acceleration command** into the **same plant**. This is what makes the comparison fair.

---

## 2. Scope & non-goals (YAGNI)

**In scope:** longitudinal car-following only; single-follower + platoon + ring/density scenarios;
Donatello champion only (float reference + as-deployed B2 fixed); MPC in two information regimes
(±V2X leader preview); behavioural metrics + FPGA cost metrics; full MPC-on-FPGA realization.

**Out of scope:** lane-changing / multi-lane; re-training the SNN; building a *new* MPC (the user's
existing online MPC is the one under test); other champions (Raffaello/Leonardo/Michelangelo) — Donatello
is the chosen representative (EventProp, ρ≈0.057 contractive, 0 dead neurons, most neuromorphic-native).

---

## 3. The two comparison planes

| Plane | Environment | Question | Cost/quality axis |
|---|---|---|---|
| **1 — Behavioural** | Simulink closed-loop + MATLAB metrics | "Do they drive comparably?" | trajectory · safety · comfort · **string stability** · efficiency |
| **2 — Hardware** | FPGA synthesis (both realized) | "What does each cost in silicon?" | LUT/DSP/BRAM · Fmax · **latency/decision** · energy/power |

**Key consistency:** the Simulink block is now the **HDL-ready B2** network — the *same* artefact Plane 2
synthesizes. So Plane 1 tests exactly what Plane 2 realizes ("what you simulate is what you synthesize").

**FPGA-implementability is itself a first-class result**, not a detail: the SNN is a **fixed-latency,
deterministic feed-forward** pass (FPGA-friendly; already realized in Phase B: ~4.5k LUT, sub-mW,
timing-clean bitstream on PYNQ-Z1); the online MPC is an **iterative QP with data-dependent iteration
count** (FPGA-hard: variable latency, heavier resources, the solver is the bottleneck). This asymmetry is
expected to be the headline hardware finding.

---

## 4. Controllers under test (the matrix)

| Config | What runs | Source |
|---|---|---|
| **MPC−preview** | online MPC, leader assumed const-velocity/accel over the horizon (sees only current state) | user's Simulink MPC |
| **MPC+V2X** | online MPC + future leader trajectory preview over the horizon | user's Simulink MPC |
| **SNN-float** | `snn_core` in `double` → IIDM law → a_cmd (algorithmic reference, ~1e-6 vs PyTorch) | `matlab/snn_core.m` |
| **SNN-B2 (as-deployed)** | HDL-ready **B2** block (fixed-point, bit-exact to the FPGA) → IIDM law → a_cmd | `snn_champions_lib.slx` / `snn_b2_fsm.m` |

The two SNN configs share the **same downstream IIDM law + plant**; only the network representation
differs → this also settles the previously-deferred **float-vs-fixed A/B** as a by-product.

---

## 5. Fairness contract (both planes)

- **Shared plant.** Extract a clean **point-mass longitudinal integrator** from the current `ACC_IIDM`
  block: `a_cmd → (ballistic dt=0.1) → v,s`, with actuator limits `a ∈ [−9, a_max]` and crash provision
  `s<0 → a=−9`. The **IIDM acceleration law belongs to *our controller*** (SNN supplies its params), NOT
  to the plant — so MPC and SNN+IIDM drive **identical vehicle dynamics**.
- **Own internal models.** Each controller keeps its own model (MPC prediction model; SNN learned net).
  We do not equalize the control law — only the plant, scenarios, ICs, actuator limits, sample time, and
  metric definitions.
- **Information set.** Two MPC regimes (−preview / +V2X) isolate *information advantage* from *control
  advantage*. The SNN is reactive (current state + ALIF memory) in all runs.
- **Fair MPC tuning.** The MPC must be a *fairly tuned* controller (documented horizon, weights,
  constraints) — never a strawman. Tuning is recorded in the report.
- **Constraint semantics (documented, not equalized).** MPC enforces safety/comfort/actuator constraints
  *explicitly, by construction* (guaranteed); SNN+IIDM has *structural* safety (IIDM collision-free under
  its assumptions + crash provision) satisfied only *empirically*. The report states this difference.

---

## 6. Phase A — Behavioural comparison (single MATLAB pipeline)

**Environment decision:** everything in **MATLAB** (revised from a Simulink→Python split). One driver
script **runs the sims → computes metrics → runs comparisons → generates figures**, in one flow, so
multi-run sessions can never mix fresh sims with stale metrics/figures.

- **Harness** (`.slx`, extended from `closed_loop_demo.slx`): leader-profile source → **[Controller Under
  Test]** (variant/config: the 4 rows of §4) → **shared plant** (§5) → feedback bus `s,v,Δv,v_l`. Only the
  controller subsystem is swapped between configs.
- **Anti-drift safeguard.** The MATLAB metric functions are validated **once** in *parity* against the
  project's already-validated Python metric suite (`utils/closed_loop_eval.safety_metrics/comfort_metrics`,
  the simulator's string-stability / fundamental-diagram code). Reuses the existing parity infrastructure
  pattern (`run_parity_tests.m`, `run_plant_parity.m` + `plant_golden.mat`). After parity passes, MATLAB is
  the single source of truth for this study → integrated *and* consistent with the project's numbers.
- **Driver script** (`run_mpc_vs_snn.m`): iterates the config × scenario × K-realization matrix, logs raw
  trajectories to a **timestamped run folder** (never overwrites; figures reference their run folder), then
  computes metrics + comparison tables + figures from *that same run's* data.
- **Deliverable:** behavioural results (per-scenario trajectory overlays, safety/comfort tables,
  string-stability plots, fundamental diagram) + the behavioural half of the Pareto.

Phase A reuses: `cf_plant_lib.slx` (plant), `closed_loop_demo.slx` (network-in-the-loop template),
`snn_core.m` (float), the B2 block (as-deployed), the parity harness.

---

## 7. Phase B — MPC on FPGA (full realization)

The SNN already has real FPGA numbers (Phase B: B2 on PYNQ-Z1). The MPC does not — so we **realize the
online MPC on FPGA for real** and synthesize it, on the **same device class** (target **PYNQ-Z1** first —
if the online QP does not fit or does not close timing, *that is a result*: escalate the device and report
the size/timing gap).

- **First task = path feasibility** (research + prototype): choose the MPC→FPGA route among
  { **HDL Coder** from the online-QP Simulink model · **HLS** (C/C++ QP) · an **FPGA QP-solver library**
  (e.g. FiOrdOs / protoip / a hardware first-order or ADMM/interior-point solver) }. The choice hinges on
  the QP size, the iteration bound, and fixed-point feasibility. This task alone surfaces the *"online-QP
  is FPGA-hard"* finding.
- **Realization + synthesis:** implement the chosen route, verify functional parity vs the Simulink MPC,
  synthesize out-of-context (like Phase B for the SNN) + power (SAIF) → **LUT/DSP/BRAM, Fmax, latency per
  decision (worst-case iteration count), dynamic+static power/energy**.
- **Deliverable:** MPC FPGA numbers + the implementability findings (fit / timing / determinism).

Reuses the SNN's FPGA methodology: OOC synth + SAIF power flow, HDL Coder single-source discipline,
double-parity after each core change (from the HDL phase), and the dense-ANN baseline assets already built
(`ann_rom.m`, `make_hdl_ann.m`) as an extra reference point.

---

## 8. Phase C — Hardware Pareto + final report

- Combine the SNN FPGA numbers (Phase B, existing) with the MPC FPGA numbers (Phase B of this study) into
  the **cost axis**; join with Phase A's behavioural axis into the **full two-plane Pareto**.
- **Report** via the **create-report** skill (impersonal, publication-grade): the Pareto figure, per-scenario
  trajectory overlays, safety/comfort/string-stability tables, the FPGA resource/timing/energy table, the
  implementability discussion, and the threats-to-validity section.
- **Deliverable:** report (`.md` + `.pdf`) in `report/`, all data + scripts committed.

---

## 9. Metrics (definitions & sources)

**Behavioural (Plane 1)** — computed in MATLAB, parity-checked vs Python:
- **Trajectory** — gap `s(t)` (primary MoP), `v(t)`, `Δv(t)`; RMSE/RMSPE where a reference exists.
- **Safety** — min gap, min TTC (`s/Δv`), DRAC (`Δv²/2s`), time-headway (`s/v`), TET/TIT (TTC* threshold),
  brake-margin, collision rate.
- **Comfort** — RMS acceleration, RMS jerk, ISO-2631 bands.
- **String stability** — platoon head→tail amplification `|H|_i`, convective character (reuse the
  simulator's meso/macro tooling ported/parity-checked to MATLAB).
- **Efficiency** — time-headway, fundamental diagram `Q(ρ)/V(ρ)` (Edie).

**Hardware (Plane 2)** — from synthesis:
- Resources (LUT/DSP/BRAM), Fmax, **latency per control decision** (SNN = fixed; MPC = worst-case
  iterations), dynamic + static power, energy per decision.

---

## 10. Scenarios & protocol

- **Single follower:** following · stop&go · hard-brake · cut-in · sinusoidal leader (the simulator's bank).
- **Platoon (string stability):** N-vehicle platoon, **Ornstein-Uhlenbeck** head perturbation (not white
  noise), K realizations, head→tail amplification.
- **Ring / density sweep (fundamental diagram):** `Q(ρ)/V(ρ)`, stability regime.
- Deterministic ICs; stochastic runs averaged over K realizations. Run matrix = 4 configs × scenarios × K.

---

## 11. Threats to validity (declared in the report)

- Fair MPC tuning (no strawman); shared plant guaranteed identical; the two preview regimes isolate the
  information advantage; **guaranteed constraints (MPC) vs empirical structural safety (SNN+IIDM)**;
  OOD / model-mismatch robustness (test both outside their comfort zone); float-vs-fixed quantization
  (both SNN configs run); **FPGA device parity** (same PYNQ-Z1 target; any escalation reported as a result).

---

## 12. Deliverables & reproducibility

- Phase A: `run_mpc_vs_snn.m` + harness `.slx` + MATLAB metric library (parity-checked) + timestamped run
  folders + behavioural figures.
- Phase B: MPC-on-FPGA sources + synth/power scripts + results.
- Phase C: the comparison report (`report/…`, create-report) + the combined dataset.
- All committed to the `Simulink_Importer` track. Deterministic re-runs; figures always tied to their run
  folder (no stale-data risk).

---

## 13. Phase decomposition (each → its own spec+plan)

- **Phase A — Behavioural comparison (MATLAB pipeline).** ← `writing-plans` starts here.
- **Phase B — MPC on FPGA (feasibility → realization → synthesis).**
- **Phase C — Hardware Pareto + create-report.**

The phases are sequenced but loosely coupled: A yields behaviour; B yields MPC silicon cost; C synthesizes.
A can start immediately (SNN + plant + parity infra exist); B is the largest/riskiest (online-QP on FPGA).

---

## 14. Open questions / risks

- **MPC→FPGA route** — resolved by Phase B's feasibility task (not pre-decided here).
- **Does the online MPC fit PYNQ-Z1 / close timing?** Unknown — an intended *finding*, with device
  escalation as the fallback (reported).
- **MATLAB metric parity** — must pass before Phase A results are trusted; if a metric cannot be matched
  bit-close, document the (small) definitional difference.
- **MPC availability** — the study assumes the user's existing online MPC (Simulink) is the artefact under
  test; its formulation (horizon, cost, constraints, solver) is recorded at Phase A start.
