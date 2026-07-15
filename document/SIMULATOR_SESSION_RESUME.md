# SIMULATOR_SESSION_RESUME.md — resume entry + STATE of the **Simulator** track

> **RUOLO DI QUESTO FILE.** Questo è il **punto d'ingresso di ripresa + lo STATO** del track *Simulator*
> (volatile: si aggiorna a ogni milestone / cambio di azione pendente). **NON è la procedura generale di
> ripresa** — quella vive nella skill `session-reprise`, non qui. Il `.claude` memory
> `cf-fsnn-parallel-tracks.md` copre le stesse tracce in più dettaglio, **ma può essere STALE e viene
> iniettata prima che tu legga qualsiasi doc**: se memoria e questo file divergono su stato o azioni,
> **vince questo file**. La memoria è un supplemento, non una dipendenza — **questo file deve bastare da solo**.

## 📍 DOVE SIAMO (verificato 2026-07-15)

- **Repo**: `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN` · **worktree**: `.worktrees/Simulator` ·
  **branch**: `Simulator`.
  ⚠️ **Non fidarti di uno SHA scritto qui**: un HEAD fissato in questo file si auto-stalizza (il commit che
  lo scrive lo cambia). **Verificalo tu**: `git log --oneline -1` + `git status` + `git rev-list --count
  origin/Simulator..HEAD`. **Atteso: working tree pulito, 0 commit non pushati.** Se non è così, capisci
  perché prima di lavorare.
- **Env/test**: conda `cf_sim`. **167 test sim verdi.** Core SNN **bit-identico** (congelato).
- **Altri track (NON confonderli con questo)**:
  - `main` → studio EventProp; ha il **suo** `document/SESSION_RESUME.md` (file diverso, altro track).
  - `Simulink_Importer` (`.worktrees/Simulink_Importer`) → FPGA/HDL, Fase B/C, B1.5 libreria champion +
    lo **studio MPC↔SNN parcheggiato (solo design)**. Ha il suo `document/SESSION_RESUME.md`.
  - `Presentation_NN` → già fuso in `main`.

## 🎯 STATO ATTUALE — 🏁 MILESTONE: cockpit feature-complete (dichiarata 2026-07-13)

Lo strumento a **3 modi** — **Live cockpit (13 dock)** + **Meso/Macro** + **Post-run dashboard** — è
feature-complete per il ciclo, temprato da un QC ciclico e documentato. Tutto committato e pushato.
Il dettaglio di com'è fatto e di cosa è stato costruito sta nelle sezioni sotto (§Architecture, §Phase history).

## ▶️ AZIONI PENDENTI (puntatori, non dump — le azioni 1-3 SUPERANO il "next = merge" della milestone)

> **Scope definito dall'utente il 2026-07-15** (4 richieste) e **decomposto in 3 cicli indipendenti**,
> ognuno con la sua spec+plan. I punti 3+4 dell'utente sono **una cosa sola** (ciclo 2): senza file
> browser l'adattività della vista è YAGNI, col file browser è obbligatoria.

1. **✅ FATTO — ciclo 1/3: oracolo (ghost) nel Live** *(2026-07-15)*. brainstorming → spec
   (`docs/superpowers/specs/2026-07-15-oracle-ghost-live-design.md`, `ea77edc`) → plan
   (`docs/superpowers/plans/2026-07-15-oracle-ghost-live.md`, `fb2d1bf`) → **TDD completo**
   (`5733b53`→`4584ee7`). **167 test verdi · core bit-identico (diff vuoto) · render-verificato.**
   **Cosa c'è ora**: toggle **"Oracolo"** in toolbar → ghost semi-trasparente sulla road + curve grigie
   punteggiate in **Trajectory** (gap/v/accel) e **Safety** (TTC/headway/DRAC). Secondo
   `SimStepper(backend=None)` in lockstep dentro `SimLoop`, **injector condiviso** (la sua `tick()` è
   idempotente — misurato) così rete e ghost vedono lo **stesso leader**; `_src_ghost_traj` commuta
   insieme a `_src_probe`/`_src_traj` nel deep-scrub. Il ghost non ha probe (niente rete → niente spike).
   ✅ **DECISO dall'utente (2026-07-15) — la compenetrazione RESTA ed è VOLUTA. NON è un bug.**
   Sulla road ego e ghost si compenetrano quando divergono meno della lunghezza di un'auto (divergenza
   tipica ~5 m, veicoli lunghi 5 m). **Motivo, con le parole dell'utente**: il ghost «è un qualcosa che
   non esiste, una traccia a cui confrontare il proprio funzionamento». Due auto vere non possono
   compenetrarsi: il fatto che queste lo facciano è precisamente ciò che comunica che una delle due
   **non è un veicolo**. L'alternativa scartata (offset verticale su una "corsia fantasma") avrebbe
   aggiunto una finzione — una corsia inesistente — per nascondere un fatto che invece informa.
   → **Niente offset verticale, niente separazione dei due sulla road.** Se un QC futuro lo segnala come
   difetto di leggibilità: è by-design, e questa riga è la risposta.
   ⚠️ **Avvertenza metodologica nella spec, non ri-cadervi**: la prima analisi usò la *mediana* e concluse
   (a torto) che il TTC dell'oracolo fosse invisibile — il TTC è saturo al clip di 30 s quasi sempre, va
   guardato il **picco** (75.87 px mediano, 88 su `hard_brake`).
2. **CICLO 2/3 — identità del checkpoint + adattività della vista** *(= punti 3+4 dell'utente)*. Da
   brainstormare. **Deve reggere**: taglia (H/rank), **max_delay**, topologia (stacked/skip/attn).
   **OUT=5 e IN=4 restano INVARIANTI per decisione dell'utente** (sono il modello fisico ACC-IIDM, non la
   vista). ⚠️ Il cuore non è il `QFileDialog`: è che il `.pt` **non dice cosa contiene**
   (`{epoch,val_loss,model_state,optim_state}`, famiglia dedotta dalla firma dello state-dict) e che
   **`max_delay` non è inferibile** per la famiglia baseline (`delays` ha shape `(32,4)` qualunque esso sia
   → `strict=True` non può beccarlo) — e un run con `cf_max_delay:18` **esiste davvero** (12 run su 512).
   Il sidecar `results/<RUN>/config_snapshot.json` ha `cf_hidden_size`/`cf_rank` (506/512) ma `cf_max_delay`
   solo 258/512, `arch_variant` 8/512, e **accanto ai champion non c'è affatto**.
3. **CICLO 3/3 — costruttore di scenari personalizzati** *(= punto 2 dell'utente)*. Da brainstormare.
   Possiede **due debiti misurati**: (a) `sim/events.py:37-38` fa ripartire la rampa dal `v_leader[t]`
   **grezzo** → due `brake_leader` in fila fanno **saltare il leader da 5.00 a 21.00 m/s in un tick**
   (misurato); (b) `ReplayLog.seed` è alimentato con l'**indice di scenario** (`sim/ui/app.py:591`).
4. **RINVIATA — merge `Simulator`→`main`** (coordinare col track `Simulink_Importer`: entrambi rinviano il
   merge, vanno sequenziati per far atterrare in `main` uno stato coerente).
5. **STUDIO POST-MILESTONE — A/B float-vs-fixed** (unica idea di Fase 4 mai fatta). ⚠️ richiede un **forward
   fixed-point Qm.n SW** che nel simulatore **non esiste** — va scopato prima (candidato: portare la logica
   fixed-point dal track `Simulink_Importer`/HDL, che l'ha già fatta per l'FPGA). Design-before-code.
   Non blocca nulla.
6. 📋 **Backlog residuo** (non pre-deciso, l'utente sceglie): roadmap §6 "Phase 5"
   (`docs/superpowers/2026-07-07-simulator-extension-study.md`) — slider GT / UKF live (si sposa col ciclo 1),
   video/GIF, ellisse a–b, worker QThread. Più: **riconciliare/etichettare il dock energia** (caveat
   ASIC-vs-FPGA in §Architecture→Energy) e la lettura **"shadow"** dell'oracolo (errore di comando istantaneo
   teacher-forced: scartata da questo ciclo per YAGNI, costa una chiamata pura, zero debito a rimandarla).

## 🧭 MODI DI LAVORO (vincoli del progetto — dettaglio in §How to work + §GOTCHAS sotto)

- **Design-before-code**: brainstorming → spec (`docs/superpowers/specs/`) → plan (`docs/superpowers/plans/`)
  → TDD (RED→GREEN→commit). Niente codice prima del design su richieste non banali.
- **Niente workaround**: se qualcosa non va, **si trova la causa radice** (systematic-debugging), non si
  mette una pezza. Un test che non fallisce senza il fix non è un test di regressione.
- **Core congelato bit-identico**: `sim/{state,stepper,backend,events,probe,eventprop_stepper}.py`. Solo
  accessor additivi read-only. Dopo qualunque tocco: ri-eseguire tutta la suite.
- **Test**: i **20 `test_sim_*.py` elencati esplicitamente** in `cf_sim` (i test non-sim falliscono in
  quell'env). Runner affidabile in §How to work (⚠️ `conda run … pytest` crasha a intermittenza).
- **Render-verify**: le modifiche visive si verificano rendendo un PNG con `QT_QPA_PLATFORM=windows` e
  **guardandolo** (`offscreen` rende il testo come tofu — non è un difetto della UI).
- **Doc di processo sempre aggiornati** (questo file + i doc citati), non solo alla fine.
- **Commit**: conventional, **senza `Co-Authored-By`**. Push liberamente.

## 🗣️ TONO / STILE (perché la ripresa sia continua)

- **Italiano con l'utente**; inglese tecnico dentro doc/codice/commit. Registro diretto e collega-a-collega.
- **Onestà prima di tutto**: dire quando una cosa **non** è verificata; non vendere più di quanto misurato;
  se un test/una prova non conferma, dirlo con l'output alla mano. **Verificare eseguendo**, non asserire a
  memoria (l'utente lo apprezza e lo chiede: "verifica").
- **Decisi**: dare una raccomandazione motivata, non un catalogo di opzioni. Guidare, non scaricare scelte.
- **Guidare con l'esito**: prima cosa è successo, poi il dettaglio. Prosa, non frammenti telegrafici.

**What it is**: a live plug&play GUI "digital twin" of the SNN car-following controller (ALIF,
**4 inputs → 32 hidden → 5 params**, po2 weights, target FPGA PYNQ-Z1). **~800 weights** = the
connections (recurrent 32×32 factored low-rank dominates). **4 champions**:
Raffaello(`R33_C2_A1_T12_fix`, BPTT) · Leonardo(`LS3_PEAK_R0_launch_d03`, BPTT) ·
Donatello(`PE_t05_gp0002`, EventProp) · Michelangelo(`A_lr1e2_t06_r16`, EventProp).

**Phases 1–3 DONE + CLOSED**: **13-dock** live cockpit (Road · NetState node-link graph · SpikeRate ·
**SynOps→energy (pJ)** · Trajectory · Safety · Events · Inspector · 5 param docks), 4 presets,
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
- **COCKPIT POLISH → 🏁 MILESTONE (2026-07-13, commits `c381923`→`d9ee9c1`)**: 4 user-reported cockpit
  fixes + one reverted experiment.
  1. **Maximize soft-lock/drift fixed at root cause** (`c381923`): double-click-maximize then restore
     re-showed preset-hidden docks (12→14) and cluttered the layout so other titles were hard to hit.
     `restoreState` leaves pre-added docks that aren't in the saved state in place → restore now re-adds
     **only the pre-maximize visible set** (`_pre_max_visible`). (Diagnosed with a real `QTest` double-click
     probe; removed an unproven `_rewire_dock_labels` — `Dock.close()` keeps the same label, the filter
     never drops. Teeth-having regression test.)
  2. **Macro red-cross ×** on the fundamental diagram now carry their `wave_std` for a **hover tooltip** +
     an on-panel **legend** (were unexplained). 3. **Meso curves clickable** → click a vehicle's curve to
     **bold-white-highlight** it (dim the rest) in both space-time + velocity panels **and ring that car on
     the road** (`sigVehicleClicked`/`highlight`, `PlatoonRoadView.highlight`).
  4. **Input-dock experiment reverted** (`f07b191` add → `d9ee9c1` remove): briefly added a v_mem→Input dock
     (then 4 gap/ego/Δv/leader docks), but gap/ego/leader/Δv are **already in the Trajectory dock** →
     pure duplication that unbalanced the layout. Removed entirely; **the old v_mem dock is NOT restored**
     (it was itself redundant with the Inspector). **Cockpit is back to 13 docks.**
  **148 sim tests green; core bit-identical; render-verified on `windows`.** → **Simulator milestone reached.**

---

## ▶️ Cosa fare adesso

→ **Vedi §AZIONI PENDENTI in cima a questo file** (unica fonte). In una riga: **ciclo 1/3 = oracolo ghost,
spec approvata, tocca al plan**; i cicli 2 e 3 sono da brainstormare; merge e A/B restano rinviati.
Questa sezione non duplica più l'elenco per non farlo divergere.

**Meso page map** (reference): `sim/ui/meso_page.py` (scenario selector + road strip + 2×2 grid) ·
`sim/ui/meso_panels.py` (`_MultiCurvePanel` base → `SpaceTimePanel`/`SpeedWavePanel`, `StringStabilityPanel`,
`FundamentalDiagramPanel`) · `sim/ui/meso_road.py` (`PlatoonRoadView`) · `sim/ui/platoon.py` (family-aware
`run_platoon`/`run_ring`/`run_fundamental_diagram`). Launch: `conda run -n cf_sim python scripts/run_simulator.py [champion.pt]`.

---

## 🛠️ How to work (setup + discipline)

- **Env**: `cf_sim` (conda). Tests/GUI: `conda run -n cf_sim python ...`.
- **Tests**: run the 20 `test_sim_*.py` files **explicitly** (non-sim tests fail in cf_sim): `state
  backend stepper scenario events probe replay loop eventprop input_capture trajectory layout panels
  ui_smoke reconstruct platoon meso_panels meso_road episode postrun`. **167 verdi (2026-07-15, dopo il
  ciclo oracolo: erano 148 + 19 test del ghost).**
  ⚠️ **Numeri "diversi" che troverai in giro = istantanee datate, NON regressioni** (erano veri al loro
  commit): test **135**, **142** (roadmap ~righe 201/205, era Fase 3–4) e **148** (roadmap riga ~212 + spec/plan
  dell'oracolo, era il baseline pre-ghost) → **il numero buono è 167**. Dock **14** (roadmap §Fase 3, `phase3-qa-perf-report.md`) = era
  quando il 14° dock era **`v_mem`** (poi rimosso **senza sostituto**; il dock Input nacque dopo, come rename
  di v_mem, e fu a sua volta revertito) → **il numero buono è 13**. I plan datati citano anche **9** e **11**
  dock: idem, storici. **Non trattarli come discrepanze da investigare.**
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
  `app.py::SimApp` = **13-dock** DockArea + champion/scenario selectors + **3-mode toggle**
  (Live / Meso-Macro / Post-run); `panels.py` = all live panels (NeuronGraphPanel, SynOpsPanel=energy,
  ParamPanel, Trajectory/Safety, EventTimeline, NeuronInspector, SpikeRate).
  **ORACOLO (ghost)** = un secondo `SimStepper(backend=None)` avanzato **in lockstep da `SimLoop`**
  (`loop.py::_step_ghost`) con l'**injector condiviso** → rete e ghost vedono lo stesso leader;
  `_ghost_traj` (secondo `TrajectoryBuffer`) → `TrajectoryPanel/SafetyPanel.set_ghost()` +
  `topdown.update_ghost/render_ghost_at`; toggle `_ghost_toggle` in toolbar (off = non disegnato né
  calcolato). Niente probe per il ghost: non ha rete. **No standalone v_mem dock**
  — the selected-neuron v_mem scope lives inside `NeuronInspectorPanel` (which is why a v_mem dock was
  redundant). Post-run = `episode.py` (incremental `EpisodeSummary`) + `postrun_page.py` (dark card dashboard).
- **Meso/Macro**: `sim/ui/{meso_page,meso_panels,meso_road,platoon}.py` (`meso_road` = `PlatoonRoadView`).
  **Reuses `utils/platoon_eval.py`**
  (validated, report-grade): `simulate_platoon`/`platoon_metrics` (MESO string stability),
  `simulate_ring`/`fundamental_diagram` (MACRO fundamental diagram, Edie). `sim/ui/platoon.py` adds the
  family-aware **batched forward** (BPTT `forward_step` / EventProp `EventPropStepper.reset(N)+step`,
  both batch over N vehicles) injected via `platoon_eval`'s additive `forward=` hook (reports unaffected).
- **Energy** (`metrics.py`): `synops`/`synops_series`/`dense_mac` (op counts) + `ann_mac` (dense-RNN
  equivalent, full H·H) + `E_AC_PJ=0.9`, `E_MAC_PJ=4.6` (Horowitz 45nm). SynOps dock plots pJ:
  SNN (SynOps×E_AC) vs dense-ANN (ann_mac×E_MAC) → ~14.5× (Raffaello), ~7.9× (Donatello).
  > ⚠️ **CAVEAT DI ONESTÀ (discrepanza cross-track nota, NON ancora riconciliata).** Quei ×
  > usano le costanti **Horowitz 45nm — che sono ASIC**. La **Fase B del track `Simulink_Importer`
  > ha MISURATO su FPGA** (synth OOC + SAIF) che **e_MAC ≈ e_AC** (DSP48 ≈ shift-add): sull'FPGA —
  > cioè sul target dichiarato di questo simulatore — **il vantaggio per-operazione largamente
  > svanisce** (~1.3×, non ~5×), e il vantaggio SNN reale (~5-65×) viene dalla **compattezza del
  > modello** (letteratura NN car-following ~7k-100k MAC vs ~800 pesi), NON da "AC≪MAC".
  > Quindi il numero del dock è **framing di Fase A (ASIC-like)**, non la verità sull'FPGA.
  > Doc autoritativo: `document/FPGA_PHASE_B_POWER.md` **sul branch `Simulink_Importer`**
  > (⚠️ NON esiste in questo worktree: `git show Simulink_Importer:document/FPGA_PHASE_B_POWER.md`).
  > **Non citare il ~14.5× come vantaggio-su-FPGA senza questo caveat.** Riconciliare il dock (o
  > etichettarlo "ASIC-like") è un candidato naturale per l'azione 1.
- **Docs**: roadmap `docs/superpowers/2026-07-07-simulator-extension-study.md`; QA/perf report
  `docs/superpowers/2026-07-09-phase3-qa-perf-report.md`; spec+plan per fase in `specs/`+`plans/` (⚠️ **non
  è 1:1**: 11 spec vs 20 plan — alcune fasi hanno solo il plan, es. `plans/2026-07-10-postrun-dashboard.md`
  non ha spec).
- **⚠️ TRAPPOLA DI NOMI**: `document/SIMULATOR_FINDINGS.md` **NON riguarda questo simulatore** — è del
  2026-06-01, branch `Visualizer_Building`, e parla del **vecchio simulatore a notebook** (`utils/simulator/`,
  `Simulator_Visual.ipynb`). Record storico di un altro strumento: **ignoralo** per questo track. Idem
  `document/SIMULATOR_DESIGN.md` = design **iniziale** della Fase ① (implementato ed esteso ben oltre): la sua
  intestazione lo dichiara record storico, ma **le frasi al presente lì dentro** ("non implementato", "prima di
  scrivere codice…") vanno lette come *"al 2026-07-02"*.
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
  **Phase 4 post-run seal + export** (`aa656ef`→`3569017`, later a v2/v3 dark dashboard).
- **QC hardening + cockpit polish → 🏁 MILESTONE (2026-07-13)**: 5-round cyclic QC (`89987b8`→`c924147`,
  34 fixes, 142 tests) + cockpit polish (`c381923`→`d9ee9c1`: maximize-restore root-cause fix,
  macro red-cross legend+hover, clickable meso curves→highlight, and an input-dock experiment added
  then **reverted** as redundant with Trajectory → back to **13 docks**). **148 sim tests green.**
  → per il seguito vedi **§AZIONI PENDENTI in cima** (il merge è rinviato: prima si aggiungono funzionalità).

---

## 📋 PROMPT DI RIPRESA (copia-incolla in una chat nuova)

> Verificato con un agente a freddo (senza contesto): ricostruisce stato, azioni, modi e tono da soli i doc.
> Se cambiano stato o azioni pendenti, **riallinea anche questo blocco**.

```text
Riprendi il track Simulator del progetto CF_FSNN. Non hai contesto: ricostruiscilo LEGGENDO I DOCUMENTI,
non chiedendolo a me e non ricostruendolo a memoria.

- Repo: D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN
- Worktree/branch: .worktrees/Simulator sul branch Simulator (è un repo git a sé).
- Punto d'ingresso UNICO: document/SIMULATOR_SESSION_RESUME.md in quel worktree. Leggilo per intero, poi
  apri i documenti che indica (roadmap, spec/plan, gotcha, file map) per il dettaglio che ti serve.
  ATTENZIONE: non confonderlo con document/SESSION_RESUME.md, che è un ALTRO track (EventProp su main).

Da quel file ricostruisci: stato attuale, AZIONI PENDENTI (la n.1 è quella immediata), modi di lavoro e tono.
In breve, così sai cosa aspettarti: design-before-code (brainstorming -> spec -> plan -> TDD); core SNN
congelato bit-identico; test = i 20 test_sim_*.py elencati esplicitamente nell'env conda cf_sim; render-verify
con QT_QPA_PLATFORM=windows (offscreen rende il testo come tofu); niente workaround, si cerca la causa radice;
commit conventional SENZA Co-Authored-By; doc di processo sempre aggiornati.
Tono: italiano con me, diretto e collega-a-collega; onesto (dì quando una cosa NON è verificata, non vendere
più di quanto misurato); VERIFICA ESEGUENDO invece di asserire a memoria; sii deciso (raccomanda, non
elencare opzioni); guida con l'esito prima del dettaglio.

Cosa faremo: l'azione immediata è AGGIUNGERE/GENERALIZZARE FUNZIONALITÀ del simulatore. Lo scope NON è
ancora definito: te lo dirò io. Non indovinare e non iniziare a progettare da solo — quando te lo dico si
parte dal brainstorming.

Quando hai ricostruito: riportami in breve stato, azioni pendenti, modi di lavoro e tono, e ASPETTA il mio
via prima di toccare qualsiasi cosa.
```
