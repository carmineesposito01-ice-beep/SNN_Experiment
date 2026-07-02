# FPGA_EVALUATE_DESIGN — Design della presentazione/notebook dell'FPGA-evaluate (CF_FSNN)

> **Data:** 2026-07-01 · **Branch:** `EventProp_Study` · **Stato:** design **LOCKED per la Fase A** (in attesa di build).
>
> Questo documento è il **DESIGN delle figure e del notebook** dell'FPGA-evaluate. È il complemento operativo di
> **[`FPGA_EVALUATION_FRAMEWORK.md`](FPGA_EVALUATION_FRAMEWORK.md)** (che è l'analisi + il catalogo esaustivo §2 dei dati
> estraibili + il piano a Tier F1–F6). Qui si decide COME MOSTRARE quella valutazione: struttura, figure, chart-type,
> principi di design, onestà. Nato da una sessione di brainstorming (superpowers) con prototipo visivo iterato.
>
> **Come riprendere da zero:** leggi §0 (decisioni) + §2 (struttura) + §3 (catalogo figure) + §6 (prossimi passi). Il
> prototipo visivo è `scripts/_fpga_eval_mockup.py` → rigenera con `python scripts/_fpga_eval_mockup.py` (46 figure,
> dati fittizi, 1 per pagina in `FPGA_evaluate_mockup.pdf`; NON usa checkpoint).

---

## 0. Decisioni di scope (dal brainstorming)

| Decisione | Scelta |
|---|---|
| **Copertura** | ESAUSTIVA — tutte le 9 categorie del catalogo (§2 del framework) → **10 sezioni** notebook (00 scorecard + 01–09). |
| **Modelli** | **Cross-champion**: i 4 champion v3.1 (Raffaello, Leonardo, Donatello, Michelangelo) + **oracolo** dove ha senso. Stile v3.1. |
| **Forma** | **Notebook** (come v3.1) che gira su Azure sui tensori `.pt`; output PNG + CSV. |
| **Fasi** | **Fase A (software_now) ORA** con dati reali. **Fase B (HDL) e C (board) RINVIATE** alla parte HDL (vedi §1). |
| **Struttura** | Specchio del catalogo (9 sezioni 1:1) + `00_Readiness` davanti + **tag di fattibilità** 🟢/🟡/🔴 in ogni figura. |
| **Principio cross-champion** | Ogni figura deve permettere il confronto tra più champion, in modo chiaro (dove è per-architettura, dichiararlo). |

**Cosa NON è**: non è la sintesi HDL, non produce numeri di silicio. È la Fase A "pre-silicio" (l'~80% del catalogo).

---

## 1. Onestà / fattibilità (registrata — punto chiave)

**~80% (Fase A) è veritiero ORA, zero workaround** — si calcola dai tensori `.pt` + simulazioni closed-loop esistenti:
analisi pesi, range fixed-point (forward strumentato + **bit-true** numpy), dinamica spiking, **SEU via bit-flip REALE
sui tensori** + `eval_safety`, I/O (canale esistente), energia/WCET (conteggio op **esatto** dal grafo; pJ/µs = **stima
citata** Horowitz + Fmax assunto).

**Precisazione di onestà**: anche le figure Fase A sono *"ciò che il modello IMPLICA per una mappatura HW fedele"*, non
*"ciò che il silicio ha misurato"*. `DSP=0`, `<2% BRAM`, `WCET=X cicli` sono **claim di progetto corretti-per-costruzione**
(veri SE l'RTL segue il design), non misure. → etichettare con i tag; numeri non-misurati = STIMA.

**~20% (Fase B/C) richiede DAVVERO la sintesi** (LUT/FF/DSP reali, Fmax/timing-closure, potenza reale, TMR/ECC, termica,
jitter misurato). E qui il nodo:
- **Nessun convertitore push-button.** FINN / hls4ml / Vitis-AI nascono per reti **feedforward quantizzate** (CNN/MLP);
  NON gestiscono ricorrenza ALIF, soglia adattiva (fatica), delay assonali, il loop dei tick, il decode IIDM.
- **Il PINN NON è il problema** (è solo *training*); a deploy la rete è forward ALIF + blocco analitico IIDM. È l'**ALIF**
  a spiazzare i convertitori.
- **Percorso realistico**: RTL/HLS **custom** (rete minuscola, po2 = shift-add, 0 moltiplicatori → fattibile ma è
  ingegneria vera, settimane). Decode IIDM → CORDIC/LUT o sull'ARM (PS) del Zynq.

> **⚠️ PROBLEMA APERTO per la fase HDL (preoccupazione utente, 2026-07-01):** la rete andrebbe importata in **Simulink**
> per far parte di un sistema più grande e poi convertita in HDL con **HDL Coder**. Percorso NON ovvio per una SNN ALIF
> custom (ricorrenza + fatica + delay + tick-loop). Vie da studiare nella milestone-2: (a) incapsulare il forward
> fixed-point in un blocco **MATLAB Function** / **S-function** HDL-compatibile; (b) generare HDL custom del core e
> co-simularlo in Simulink come blocco black-box; (c) valutare toolchain SNN dedicate (Spiker+, FINN-forks) come
> ispirazione, adattando la cella ALIF. **Non risolto — da affrontare quando si passa all'HDL.**

**Scelta operativa presa**: procedere con **A** ora; **B/C** rimandate. Nel notebook Fase A le poche figure B/C che
restano (mockup) vanno tenute come **stime ancorate alla letteratura marcate "pending sintesi"** (Spiker+, paper
po2-MAC, datasheet Zynq-7000) — decisione di dettaglio da confermare quando si costruisce (default: tenerle marcate).

---

## 2. Struttura del notebook (10 sezioni)

`00_Readiness` (apertura, scorecard) · `01_Weights_po2` · `02_FixedPoint_Ranges` · `03_Spiking_Dynamics` ·
`04_Energy` · `05_Timing_WCET` · `06_Resources_DSE` · `07_SEU_ISO26262` · `08_IO_HIL` · `09_Thermal`.

Ogni sezione = figure **cross-champion** (dove sensato) + **tag fattibilità** 🟢 software_now / 🟡 needs-HDL(mockup) /
🔴 needs-board(mockup). `00_Readiness` aggrega le altre in un colpo d'occhio.

---

## 3. Catalogo figure per sezione (design LOCKED per la Fase A)

Legenda tipi: het=heatmap · lol=lollipop · bit=campo-di-bit · sca=scatter · box=range/box · line · psd · ts=time-series ·
bar/gbar=bar (raggruppato) · wf=waterfall · cont=contour · rad=radar · rast=raster+marginali.

### 00_Readiness (🟢)
- `readiness_matrix` (het RAG champion×9dim + verdetto) — chi è più FPGA-friendly e dove.
- `readiness_radar` (rad 6 assi, **1 = requisito assoluto soddisfatto**, non relativo) — profilo comparativo.
- `deploy_verdict` (tabella + **glossario colonne**) — champion eletto + motivazione.

### 01_Weights_po2 (🟢)
- `po2_alphabet` (lol, 13 livelli) — il moltiplicatore è 1 di 13 valori → barrel-shifter, 0 DSP.
- `resource_occupancy` (gbar cross-champion) — % LUT/FF/BRAM/**DSP=0** del Zynq-7020 (stessa topologia → quasi identici).
- `spectral_recurrence` (sca ρ vs ‖U@V‖₂, po2/float) — stabilità loop ricorrente fixed-point.
- `sparsity_mask` (gbar per matrice, **con legenda ruoli** fc/rec_U/rec_V/out) — sinapsi eliminabili.
- `po2_exponent_range` (range per matrice) — bit di esponente per matrice + saturazione fc (pre-scaling √6).

### 02_FixedPoint_Ranges (🟢, `quant_vs_bits` curva onesta = ⚙️ re-train)
- `bit_allocation` (bit, Qm.n per stato, **int_bits ← range misurato**) — formato fixed-point per stato.
- `state_ranges` (box per stato, **etichette col layer**: membrana/soglia ALIF, rec_int, LI, corrente) — dynamic range.
- `quant_vs_bits` (line acc+safety vs bit, fixed+po2, 2–12) — bit-budget minimo pesi (curva onesta = re-training QAT).
- `per_param_fragility` (het champion×[v0,T,s0,a,b]) — quale param cede prima ('b'/frenata).
- `chattering` (ts accel liscia-vs-nervosa + psd) — instabilità da quant *che si vede*.
- `leak_decay` (line, potenziale float vs fixed che *si incastra*) — leak-underflow: perché servono ≥6 frac_bits.

### 03_Spiking_Dynamics (🟢)
- `activity_map` (het firing-rate per-neurone, morti evidenziati) — hotspot vs morti.
- `raster` (rast ordinato + marginali; **1 pannello/strato**; opz. HTML interattivo) — struttura di attività.
- `sparsity_per_tick` (line, **picco = albero AC**) — max spike simultanei.
- `isi_dist` (istogramma) — ISI min → worst-case back-to-back.
- `dead_saturated` (gbar, **implicazione HW di entrambi**: morti→pruning, saturi→costante hardwired).

### 04_Energy (🟢)
- `energy_breakdown` (wf/bar pJ per componente, **incluse op non-sinaptiche**).
- `energy_vs_ann` (gbar **stack per tipo-op**: SNN=AC+shift, ANN=MAC).
- `energy_vs_rate` (line) — sensibilità al firing-rate.
- `synops_split` (gbar statico/dinamico) — dove conviene il clock-gating.

### 05_Timing_WCET (🟢)
- `op_count` (bar per componente) — input del WCET.
- `wcet_cycles` (bar orizz. **cicli + µs**, 3 profili) — leggibile.
- `latency_margin` (bar-budget log vs deadline 100 ms) — margine ~3 ordini *che si vede*.
- `jitter_proof` (bar "IDENTICO" per spike 1/15/30%) — jitter=0 (WCET==BCET).
- `decode_criticalpath` (bar) — decode = unico blocco mul/div (collo Fmax + unico DSP).

### 06_Resources_DSE (🟢; `bram_dimensioning` esatto)
- `op_by_celltype` (bar AC vs shift-add) — 0 moltiplicatori → 0 DSP.
- `dse_pareto` (sca area↔latenza, **sweet spot marcato, spiegato**) — pipeline-vs-unroll.
- `area_model` (gbar LUT/FF per blocco) — stima parametrica pre-sintesi.
- `bram_dimensioning` (bar) — 1–3 BRAM su 140.

### 07_SEU_ISO26262 (🟢; `tmr_overhead` 🟡)
- `seu_intro` (**pagina-concetto**: cosa sono i bit-flip / SEU).
- `sensitivity_map` (het peso×bit) — "se inverto 1 bit, di quanto sale il rischio?".
- `bit_criticality` (bar per posizione-bit) — 90% del rischio in 2 bit → ECC mirata.
- `degrade_vs_flips` (line safety vs #flip) — quanti SEU prima dell'insicurezza → scrubbing.
- `perparam_shift` (het) — quale param si sposta di più (a,b/frenata).
- `hidden_vs_readout` (gbar) — readout più critico → TMR su ~20%.
- `tmr_overhead` (bar) — 🟡 costo area mitigazioni (mockup, pending sintesi).

### 08_IO_HIL (🟢)
- `aoi_max_surface` (het/cont s×Δv + contorno latenza-bus) — età max del CAM tollerabile (requisito hard bus).
- `aoi_dist` (istogramma) — quanto spesso su dati stantii.
- `queue_overflow` (line vs profondità) — buffer minimo anti-burst.
- `holdmode` (gbar hold_last/dead_reckon/blind) — hold-last maschera?
- `pdr_latency_knee` (line) — graceful su PDR, crolla su latenza.

### 09_Thermal (🟡, tutte mockup pending sintesi)
- `derating_tj_fmax` (line) — clock a caldo (85–100 °C).
- `thermal_budget` (bar SNN vs ANN) — budget ECU passiva.

**Totale prototipo: 46 pagine** (43 🟢 Fase A + 3 🟡 HDL-mockup, più `seu_intro` come concept).

---

## 4. Principi di design (dalla sessione — vincoli per il builder reale)

1. **Varietà di grafici** contro la monotonia (no muri di barre): heatmap, lollipop, campo-di-bit, scatter, PSD,
   time-series, radar, waterfall, contour, raster+marginali, range/box.
2. **Ogni figura DEVE dire "cosa significa per l'hardware"**, non solo mostrare il dato (sottotitolo/annotazione HW).
3. **Cross-champion sempre possibile e chiaro** (per le figure per-architettura, dichiararlo esplicitamente).
4. **Legende/glossari** per ogni quantità non ovvia (SEU, ruoli delle matrici fc/rec/out, cosa vale "1" negli assi…).
5. **Onestà**: tag 🟢/🟡/🔴; numeri non-misurati = "STIMA" citata; claim-di-progetto ≠ misura (§1).
6. **Concetti difficili** (SEU, AoI, WCET) → pagina/nota **concetto in chiaro** prima delle figure tecniche.
7. Stile figure uniforme (rcParams: font/griglia/titoli in grassetto, dpi coerente), come nel prototipo.

---

## 5. Prototipo visivo (bloccato con l'utente)

- **`scripts/_fpga_eval_mockup.py`** — genera `FPGA_evaluate_mockup.pdf` (46 figure, **dati fittizi**, 1/pagina).
  Serve SOLO a bloccare *design e leggibilità* (chart-type, layout, messaggio). NON usa checkpoint. Iterato 3 volte
  sul feedback dell'utente (v1 firme singole → v2 riformulazioni "cosa-significa-per-HW" → v3 fix
  readiness_radar/deploy_verdict/resource_occupancy). Rigenera: `python scripts/_fpga_eval_mockup.py`.

---

## 6. Prossimi passi (build reale — Fase A)

> **✅ BUILD FATTO (2026-07-02).** Le 5 librerie software_now sono scritte, testate (17 check verdi:
> `tests/test_fpga_profilers.py` 8, `test_fpga_seu.py` 6, `test_fpga_io.py` 3) e verificate su **checkpoint
> REALI** (baseline+eventprop): ρ(U·V)=0.162 / ‖·‖₂=0.843 confermano il framework. Le **46 figure a dati reali**
> sono in `scripts/fpga_figures.py` (render locale 46/46 OK, 0 placeholder); il notebook `Eval_FPGA.ipynb`
> (builder `scripts/_build_fpga_eval_notebook.py`) le orchestra nelle 10 sezioni + 7 CSV deliverable, resiliente
> come il v3, **pronto per Azure** (integration key-check locale 46/46 figure + CSV OK). Verifica post-run:
> `scripts/verify_fpga_eval.py`. Lancio: `jupyter nbconvert --to notebook --execute --inplace
> --ExecutePreprocessor.timeout=-1 Eval_FPGA.ipynb` → poi `python scripts/verify_fpga_eval.py`.
> Bug catturato dal gate pre-notebook e corretto: `aoi_max_surface` era family-agnostic-non-safe (forward_step
> eventprop). Le figure 🟡/🔴 (HDL/board) restano stime marcate. **Restano da fare**: il report FPGA finale
> (dai risultati Azure, come `VALIDATION_REPORT_v3`), e le Fasi B/C.

Storico del piano (ora realizzato):

1. **Builder** `scripts/_build_fpga_eval_notebook.py` (analogo a `_build_eval_v3_notebook.py`): carica i champion `.pt`,
   calcola le figure **Fase A sui tensori/forward REALI**, salva PNG/CSV in `results/evaluate/FPGA/`. Gira su Azure.
   Resiliente (skip-se-esiste, ERROR_<sez>.txt), oracolo dove sensato, stile uniforme. + `scripts/verify_fpga_eval.py`.
2. **Librerie software_now da scrivere** (molte già previste in FRAMEWORK §4.1):
   - `utils/weight_profiler.py` — istogramma po2, footprint bit, ρ(U@V), sparsità mask, esponenti per matrice
     (gestire naming checkpoint piatto vs live-nested).
   - `utils/state_profiler.py` — forward-hook su ALIFCell/LICell/HiddenLayer → range/traccia di potential/rec_int/LI/
     fatigue/current/raw (base per fixed-point, energia, SEU, timing).
   - `utils/latency_model.py` — `op_count` + `wcet_cycles` (cascata ricorrente V→U a 2 stadi, op non-sinaptiche).
   - `utils/seu_inject.py` — decodifica peso→bit po2, single-bit-flip exhaustive + multi-flip MC, riusa `eval_safety`.
   - estensioni canale I/O (AoI_max surface, coda finita) su `closed_loop_eval.py`.
   - `utils/net_diagnostics.py` (già esiste): dead/sat/eff_rank/raster/raggio spettrale.
3. **Verifica**: compile-check celle + integration key-check (modello random + cache reale, come v3.1) + `verify_fpga_eval.py` post-run.
4. **Fase B/C** (HDL/board): **rinviate** — vedi §1 (nodo Simulink/HDL Coder da risolvere). Milestone dedicata.

---

## 7. Decisioni ancora aperte (minori)

- **Raster interattivo HTML** (selettore di strato + zoom) come artefatto extra oltre agli small-multiples statici — **sì/no** (da confermare).
- Figure B/C: tenerle come stime-marcate-pending (default) o toglierle finché non c'è la sintesi minima — **default: tenerle marcate**.

**Risolte**: scope = Fase A esaustiva · modelli = cross-champion · B/C = rinviate · struttura = 9 sezioni + scorecard + tag.
