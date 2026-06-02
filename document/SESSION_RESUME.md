# SESSION_RESUME.md — Quick context for any new Claude session

> **Scopo**: in 5 minuti capire **dove siamo**, **cosa è stato fatto**, **cosa fare adesso**.
> Aggiornare ad ogni milestone (1 sezione "Stato attuale" sempre aggiornata, log storico in coda).

---

## 🎯 Stato attuale (2026-06-02 — R2 esecuzione in corso su Azure)

**Fase corrente**: **R2 — Studio Prodigy CAPIRE** (5 esperimenti diagnostici in esecuzione su Azure).

**Doc radice**: [`document/AUDIT_2026-06-02.md`](AUDIT_2026-06-02.md) — bilancio onesto post-T30 che ha generato la roadmap R1+R2+R3.

### Cronologia recente

1. **8 run T30** (4 arch × 2 opt × 30 ep) → 5 affermazioni dichiarate ma non dimostrate (vedi AUDIT)
2. **AUDIT_2026-06-02.md** scritto → fermato la corsa in avanti
3. **R1 completato** → snapshot 4+1 architetture in `Arch_Tested/`
4. **R2 setup completato** → 5 esperimenti P-A..P-E pronti, ora in esecuzione Azure
5. **R3 pending** → studio EventProp serio (dopo R2)

### R1 — Arch_Tested/ (FATTO)

Snapshot self-contained delle 5 architetture funzionanti:
- ⭐ **`BASELINE_BPTT_864p_PRE_EVENTPROP`** (source P12_S2D_F2_no_ou, lambda_sr=0.5, **vera baseline pre-EventProp**)
- `A1_baseline_BPTT_864p` (source T30_A1_BASELINE_adamw, lambda_sr=0 — ⚠️ DEPRECATED)
- `A8_attn_BPTT_3936p` (source T30, 3936p, val_data 0.163 best architettonico ma overfit possibile)
- `A3_stacked_skip_BPTT_2624p` (source T30)
- `EVPROP_ALIF_full_864p` (source SW_eventprop_alif_full_adamw_lr2e-3 5ep sched=none)

Per ogni: `core/` cleanup (solo classi necessarie + build_model factory ristretta), `train.py` CLI ridotta, `snapshot_original/` READ-ONLY con 13 plot G + log, `reproduce_training.ipynb`, README.

### R2 — Studio Prodigy CAPIRE (IN ESECUZIONE)

**Branch**: `Prodigy_Deep_Study` HEAD `a29b354`.

**Doc completa**: `document/PRODIGY_DEEP_STUDY.md` (parte 1 math + parte 2 community wisdom da paper Mishchenko 2024 + 5 GitHub Issues konstmish/prodigy + OneTrainer Wiki + kohya-ss community).

**Eureka critici emersi dalla ricerca multi-fonte**:
- **V2** (konstmish ufficiale, Issue #27): "Se `d` resta troppo piccolo, aumenta `d0` da 1e-6 a 1e-5/1e-4"
- **W1** (madman404, Issue #8): `betas=(0.9, 0.99)` → "dramatic improvement" (beta3=beta2^0.5)
- **W2** (community consensus): `d_coef=2.0` standard, non 1.0 default
- **Setup canonical "Prodigy is ALL YOU NEED"**: `lr=1.0 betas=(0.9,0.99) wd=0.01 use_bias_correction=True safeguard=True d_coef=2.0 d0=1e-6→1e-5 if frozen` + `cosine_no_restart T_max=epochs`

**5 esperimenti R2.2** (in esecuzione Azure, ~1.5h stima):
- **P-A**: replica T30 baseline (default Prodigy lib) → conferma d frozen
- **P-B**: P-A + betas=(0.9, 0.99) → isola W1
- **P-C**: P-A + d_coef=2.0 → isola W2
- **P-D**: P-A + d0=1e-5 → isola V2 (fix konstmish ufficiale)
- **P-E**: SETUP CANONICAL KOHYA completo + cosine_no_restart → vero benchmark "Prodigy in azione"

Setup comune: BASELINE_BPTT_864p_PRE_EVENTPROP, 10 ep × 100 step, results in `results/Prodigy_Study/`.

### R3 — Studio EventProp serio (PENDING)

Da iniziare dopo merge R2 in main. Stessa logica: leggere paper Wunderlich&Pehle 2021 + ref impl (Norse, snntorch), 7 lever isolati (clip, lr peak, warmup, init scaling, detach periodico, thresh_jump learnable, full λ_fatigue), trovare almeno UN setup stabile (grad_norm_max < 100), fair comparison vs BPTT.

### Stato branch git

```
main HEAD efa0639   ← R1 mergiato (Arch_Tested/ + BASELINE_PRE_EVENTPROP)
├── Prodigy_Deep_Study HEAD a29b354   ← R2 in esecuzione
├── Architecture_Exploration          ← branch storico (intatto)
├── Floor_Diagnostic                  ← branch storico (intatto)
├── Optimizer_Exploration             ← branch storico (intatto)
├── Training_Method_Exploration       ← branch storico (intatto)
└── Visualizer_Building               ← branch storico (intatto)
```

**Decisione utente**: i 5 branch storici NON vengono cancellati (rimangono come archeologia consultabile).

### Doc principali da leggere (priorità)

1. ⭐ [`AUDIT_2026-06-02.md`](AUDIT_2026-06-02.md) — bilancio onesto + roadmap R1/R2/R3
2. [`PRODIGY_DEEP_STUDY.md`](PRODIGY_DEEP_STUDY.md) — math + community wisdom Prodigy
3. [`../Arch_Tested/README.md`](../Arch_Tested/README.md) — overview 5 architetture salvate
4. [`SIMULATOR_FINDINGS.md`](SIMULATOR_FINDINGS.md) — drift T² + cut-in analysis simulator
5. [`EVENTPROP_OPTIMIZER_SWEEP.md`](EVENTPROP_OPTIMIZER_SWEEP.md) — sweep 4×11 origine SW_eventprop best

### Cosa fare adesso

- ⏳ **Aspettare risultati R2 da Azure** (~1.5h, 5 esperimenti × ~15-17 min)
- Quando finiti: pull `results/Prodigy_Study/`, analizzare via celle 4-5 notebook, scrivere PRODIGY_DEEP_STUDY.md parte 3 con verdetto
- Poi: merge R2 → main, iniziare R3 EventProp_Deep_Study

---

## 📜 STORIA PRECEDENTE (pre-R1, 2026-06-01)

> Sezione conservata per archeologia. **Le conclusioni qui sotto sono state riaperte dall'AUDIT_2026-06-02**.

### F2 EventProp chiuso (pre-audit, 2026-06-01)

Sweep 4×11 = 44 run aveva dato:
- val_data baseline 0.2218 vs eventprop_alif_full 0.2226 (pareggio, Δ < 0.4%)
- Robustezza optimizer: baseline 11/11 successi, EventProp 5/11
- Spike rate: baseline 4.1% vs EventProp 25.7%

**Conclusione del momento**: "baseline ALIF+BPTT+SurrogateSpike confermato production". 

⚠️ **Riaperto da AUDIT §2.1**: "EventProp non funziona" è dichiarazione non dimostrata (mai testato con tuning serio: clip aggressivo, warmup, init scaling, detach periodico). Lo studio R3 riparte da capo.

**🏆 STATO PRINCIPALE: P14 CHIUSO** — decomposizione completa del floor val~0.28:

```
Floor totale 0.2805 = 100%
├─ OU noise              0.0543   ← 19.3%   (irriducibile in deploy)
├─ Spike-rate regularizer 0.0006   ← 0.2%   (trascurabile)
├─ Po2 quantization      0.0006   ← 0.2%   (TRASCURABILE — Po2 resta ON deploy)
├─ SR × Po2 interaction  0.0052   ← 1.9%
└─ Residuo architettura  0.2198   ← 78.4%  (LIMITE DOMINANTE)
```

**Best assoluto raggiunto**: F7 val=0.2198 (no OU + no SR + no Po2, ancora in trend DOWN @E15).

**Architettura corrente**: CF_FSNN_Net parametrizzabile h=32, r=8 → 864 params. Baseline confermato sufficiente da sweep STEP 2B (capacity falsificata) e Plan B Optimizer_Exploration (val=0.2805 baseline AdamW).

**Optimizer scelto**: AdamW + OneCycleLR + h=32, r=8 + 15 ep × 190 step cap. Prodigy archiviato (≈ AdamW, vedi FUTURE_WORK F1 per re-test post-floor).

---

## 📊 Storia dei 9 setup convergenti al floor (range 0.279-0.290)

| Setup | val_best | Sorgente |
|-------|----------|----------|
| 5× capacity sweep (h=32→128) | 0.279-0.280 | STEP 2B (sweep), Optimizer_Exploration |
| AdamW b=8 OneCycle | 0.2805 | STEP 2C Plan B |
| Prodigy lr=0.1 b=1 dc=1.0 | 0.2823 | STEP 2C Plan A retry |
| Prodigy lr=0.5 b=1 dc=0.5 | 0.2857 | STEP 2C-bis #6 |
| Prodigy lr=0.1 b=1 dc=0.5 | 0.2902* | STEP 2C-bis #5 (* ancora migliorabile) |

**Conclusione robusta**: il floor è strutturale, indipendente da capacità/optimizer/scheduler/batch_size/d_coef/n_train.

---

## 🔬 Decomposizione validata da STEP 2D (Floor_Diagnostic)

7 esperimenti F1-F7 hanno isolato la causa di ogni fattore. **OU noise** (errori percezione V2X simulati nel generator) è la SOLA componente non-architetturale rilevante (19.3% del floor). Po2 e Spike-rate regularizer pesano insieme 0.4% — **decisione utente di mantenere Po2 in deploy è validata**.

**Repo HEAD storico** (per archeologia): `534c2af` — `fix: _push_results non importa torch (kernel Jupyter Azure non lo ha)`

**Progetto**: CF_FSNN — Spiking Neural Network per identificazione parametri car-following ACC-IDM (con base IIDM, Treiber Ch12 Sez.12.4). Target hardware: PYNQ-Z1 FPGA.

**Architettura rete corrente**: CF_FSNN_Net **parametrizzabile** (h=hidden_size, r=rank). Default config.py: h=32, r=8 → 864 params. Sweep STEP 2B testato: h∈{32, 48, 64, 96, 128}.

**🔥 DIAGNOSI ROVESCIATA — P9 FALSIFICATO 2026-05-29**:

Il capacity sweep STEP 2B (5 runs highway-only con h=32, 48, 64, 96, 128) ha mostrato:

| h | r | params | val_best | Spike% |
|---|---|---|---|---|
| 32 | 8 | 869 | 0.2802 | 8.4 |
| 48 | 12 | 1685 | **0.2789** ★ | 9.1 |
| 64 | 16 | 2757 | 0.2790 | 10.5 |
| 96 | 24 | 5669 | 0.2797 | 7.7 |
| 128 | 32 | 9605 | 0.2792 | 10.3 |

**Range val_best = 0.0013 (1.3 millesimi) su 11× parametri.** Aumentare la rete da 869 a 9605 parametri (+1004%) migliora val_best dello 0.46% — è rumore statistico, non miglioramento.

**P9 (capacity insufficiency) è FALSIFICATO**. Il plateau ≈ 0.28 NON è dovuto a capacity insufficiente.

**Nuovi problemi aperti (P12, P13)**:
- **P12** — Plateau non-capacity: causa rimane da identificare (ipotesi: minimi locali da OneCycle troncato + early stop aggressivo, saturazione dataset, Pareto PINN, Po2 floor)
- **P13** — Scenario crashes: **urban** crash E3 per dead-neurons (spike=0.6%), **truck** crash E5 per post-convergence grad explosion. Truck però raggiunge **val_best=0.1601 a E5** (43% migliore di highway!) — la rete CAN scendere sotto 0.20 su task specifici

**Eureka utente confermata + raffinata**: i runs si fermano in 4 epoche per early-stop aggressivo + OneCycleLR che a E4 è solo al 40% del ciclo (decay phase profonda mai raggiunta). Possibili minimi locali — da testare con scheduler con warm restart + più epoche.

**Hardware constraint**: tutti i fix devono mantenere compatibilità FPGA (pesi power-of-2, leak bit-shift, surrogate hardware-friendly senza propagation al threshold).

---

## 📍 Prossimo step — DECISIONE STRATEGICA UTENTE (2026-05-31)

Dopo STEP 2C+2D, sappiamo dove c'è margine e dove non c'è. 4 strade per il prossimo capitolo. Vedi `FUTURE_WORK.md` per dettagli ognuna.

### Opzioni (descritte in dettaglio in FUTURE_WORK.md)

| ID | Mossa | Costo | Potenziale | Rischio |
|----|-------|-------|------------|---------|
| **F2** | **Switch a EventProp** (paradigma training diverso) | alto (~2-3 settimane dev) | alto se BPTT è il vero limite | medio (cambio paradigma) |
| **F3** | Curriculum noise (training su noise_scale crescente) | basso (~1 giorno dev) | basso-medio (-0.05 forse) | basso |
| **F4** | Architettura modificata (più layer, attention, ALIF mod) | medio (~1 settimana dev) | alto sul residuo 78% | medio |
| **F5** | **Accettare floor 0.28 → procedere a deploy PYNQ-Z1** | minimo | conclusione progetto | nessuno |

**EventProp** (Wunderlich & Pehle 2021) è particolarmente interessante: invece di propagare gradienti continui via surrogate function attraverso il tempo (BPTT), calcola gradienti esatti event-based usando aggiunte (Hamiltonian backprop). Se il floor architettura è dovuto a errori di approssimazione del surrogate, EventProp potrebbe sbloccarlo.

**Reference EventProp**:
- Wunderlich & Pehle (2021), "Event-based backpropagation can compute exact gradients for spiking neural networks"
- snnTorch ha implementazione: `snntorch.functional.eventprop` (recente, da verificare versione)
- Riferimento skill: `SNN-expert` ch08 §Surrogate Gradient Learning

---

## 🎯 Criteri di successo (proposti 2026-05-29)

### Quantitativi — hard targets

| Criterio | Soglia | Razionale |
|---|---|---|
| **val_loss totale** | **< 0.15** competitivo, **< 0.20** buono, **< 0.10** SOTA | Treiber Ch17: residual error floor ~20% → 0.15 ≈ 10% inferiore = eccellente |
| **L_data / L_total** | > 0.80 | La rete deve risolvere il task, non barare con L_phys |
| **RMSE per-param** | < 15% del range fisico | v0±5.5 m/s, T±0.3s, s0±0.6m, a±0.33 m/s², b±0.4 m/s² |
| **Spike rate** | 10–25% | SNN-expert default. Sotto=dead, sopra=no sparsity gain FPGA |
| **0 inf grad batches** | per ≥10 epoche | Stabilità BPTT |
| **String stability** | vₑ'(s) ≤ ½(fₗ-fᵥ) | Treiber Ch16 |
| **FP32 vs Po2 gap** | < 10% | Funzionalità FPGA preservata |

### Qualitativi
- Cross-scenario robust: val_{highway, urban, truck} non divergono oltre 2× (oggi: 0.279 vs 0.388 vs 0.160 = range 2.4×, fuori soglia)
- G7 violin: 80%+ predizioni dentro range fisico IDM
- G13 trajectory: gap simulato segue ground-truth con MAE < 1m per ≥ 5s

---

## 🛣️ Roadmap aggiornata STEP 2

| Step | Stato | Obiettivo | Esito |
|------|-------|-----------|-------|
| **STEP 2A** (fast iteration) | ✅ completato | Validare regime fast-iteration | val=0.2802, 17 min |
| **STEP 2B** (capacity sweep) | ✅ completato 7/9 | Verificare se capacity è bottleneck | **P9 FALSIFICATO** |
| **STEP 2C** (Optimizer Exploration) | ✅ completato | Sweep AdamW vs Prodigy (6 config Prodigy) | AdamW vince marginale, Prodigy archiviato |
| **STEP 2D** (Floor Diagnostic) | ✅ completato | Decomporre il floor val~0.28 | **P14 CHIUSO**: 78% architettura, 19% OU, <1% Po2+SR |
| **STEP 2E** (mitigation) | 🟡 DECISIONE UTENTE | 4 opzioni: EventProp / curriculum / arch mod / accept-and-deploy | vedi FUTURE_WORK |

---

## 🗂️ Mappa dei documenti

| File | Quando consultarlo |
|------|---------------------|
| **SESSION_RESUME.md** (questo file) | Sempre per primo, in ogni nuova sessione |
| **GLOSSARY.md** | Decode acronimi P/A/B/F/T/PF/G/STEP usati nei commit/log |
| **WORKFLOW.md** | Come fare un nuovo esperimento end-to-end |
| **TIMELINE.md** | Storia decisioni + cosa è stato provato/scartato |
| **P_S.md** | **Living doc**: 11 problemi diagnosticati + soluzioni applicate/scartate |
| `report/report_4.md` | Snapshot architettura + 12 fix SNN-expert (storico) |
| `report/report_1.md`, `report_2.md`, `report_3.md` | Snapshots più vecchi |
| `cf_model_recommendation.md` | Analisi modelli candidati (IDM/IIDM/ACC-IDM) |
| `optimization_ideas.md` | Idee tuning a lungo termine |
| `training_plan.md` | Piano addestramento (potrebbe essere obsoleto) |
| `use_cases.md` | Use cases V2X (UC2 cut-in, ecc.) |
| `project_core_guidelines.md` | Vincoli hardware, design principles |

---

## ❓ Domande aperte (decisione utente per STEP 2C)

| ID | Domanda | Opzioni |
|---|---|---|
| **Q1** | Approccio STEP 2C | **A** = Compositional best-practice (AdamW+CosineWR+SWA, raccomandato) / **B** = Prodigy drop-in (parameter-free) / **C** = R&D SurrogateSAM (originale) |
| **Q2** | Granularità | 1 singolo run 2C-α / Sweep 2C-α + 2C-β a confronto |
| **Q3** | Criteri "funziona bene" | Conferma soglie val < 0.15 competitivo / < 0.20 buono / < 0.10 SOTA (vedi sezione criteri) |

**Default raccomandato in attesa di risposta**: Q1=A, Q2=1 run, Q3=confermato.

---

## 🧮 Catalogo Ottimizzatori (per riferimento STEP 2C)

### Tier 1 — Validati su SNN
| Ott. | Anno | Pro | Cons | Default skill SNN-expert |
|---|---|---|---|---|
| AdamW | 2017 | Decoupled wd, stabile | — | ✅ default consigliato |
| Cosine warm restart (SGDR) | 2017 | Esce dai minimi locali | 1 hyperparam T_0 | ✅ default scheduler |
| SAST (SAM applicato a SNN) | 2026 | Flat minima, +generalization | 2× tempo | recente |
| Lion (Google) | 2023 | Veloce, ½ memoria Adam | sign-only può essere troppo aggressivo | usato in Spyx |

### Tier 2 — Generalist potenti, non testati su SNN
| Ott. | Anno | Pro | Cons | Per noi |
|---|---|---|---|---|
| Prodigy | ICML 2024 | Parameter-free (no lr tuning) | Non testato SNN | ⚠️ rischio |
| Sophia (Stanford) | 2023 | Hessian-aware, 2× speedup LLM | Costo Hessian | ⚠️ ricerca |
| AdaBelief | NeurIPS 2020 | Stabile vs Adam | +0.5% marginale | low priority |
| D-Adaptation | ICML 2023 | Parameter-free predecessore | Sostituito da Prodigy | skip |

### Tier 3 — Wrapper (compongono su altro optimizer)
| Wrapper | Effetto | Costo | Per noi |
|---|---|---|---|
| **SAM** | Flat minima (2 forward+backward) | 2× tempo | ⭐ STEP 2C-β |
| **Lookahead** | Smooth oscillazioni (k fast + slow pull) | +5% memoria | medio |
| **SWA** | Average weights ultime N epoche | trascurabile | ✅ STEP 2C-α |
| **Snapshot ensemble** | Ensemble ai warm restart | trascurabile | future |

### Tier 4 — Specifici SNN (sperimentali, non in production)
| Metodo | Anno | Note |
|---|---|---|
| ADMM-based SNN training | 2025 | Alternating direction, non SGD-derived |
| Rate-based BP | NeurIPS 2024 | Sfrutta rate coding per ridurre BPTT |
| e-prop (Bellec) | 2020 | Eligibility traces locali |
| EventProp (Wunderlich) | 2021 | Adjoint exact, O(spikes) memoria |

### Decision matrix (h64_r16 highway target)
| Combinazione | Plateau escape | Stabilità BPTT | Po2-friendly | Dataset piccolo | Impl. | Total |
|---|---|---|---|---|---|---|
| Adam (attuale) | 1 | 3 | 2 | 2 | 5 | 13 |
| AdamW + Cosine WR | 4 | 4 | 3 | 4 | 4 | **19** ✓ |
| AdamW + SAM | 5 | 4 | 5 | 4 | 3 | **21** ⭐ |
| AdamW + SurrogateSAM (R&D) | 5 | 5 | 5 | 4 | 2 | **21** ⭐ |
| Prodigy | 4 | 3 | 2 | 3 | 4 | 16 |
| Lion | 3 | 3 | 3 | 3 | 4 | 16 |
| Sophia | 5 | 4 | 4 | 3 | 2 | 18 |

---

## ⚙️ Infrastruttura disponibile

### Codice principale (NON modificare senza tracking esplicito in P_S.md)
- `core/network.py` — `CF_FSNN_Net(hidden_size=None, rank=None)` + layers + funzioni fisica ACC-IDM (kwargs STEP 2B per sweep)
- `core/neurons.py` — `ALIFCell`, `LICell` (hardware-friendly)
- `core/hardware.py` — `SurrogateSpike_Hardware` (γ=1.0 A3), `PowerOf2Quantize`
- `train.py` — main + `pinn_loss` + `train_epoch` + `BatchCSVLogger` + early stopping + CLI scenario/cut_in/n_train/n_val/cf_hidden_size/cf_rank
- `data/generator.py` — generatore sintetico ACC-IDM, `parse_scenario_mix`
- `config.py` — costanti (NON modificare scenario/cut_in qui: usa CLI da Cella 1)
- `utils/plot_diagnostics.py` — G1-G13 grafici
- `scripts/preflight.py` — `_checkpoint_loadable` ora legge h/r da config_snapshot (fix STEP 2B)

### Workflow
- `scripts/preflight.py` — doppio smoke obbligatorio prima di FULL (legge h/r da config_snapshot per loadable test STEP 2B)
- `Training_File.ipynb` — notebook universale per singoli runs approfonditi (10 celle, tracciato in git)
- `Training_File_Sweep.ipynb` — orchestratore sweep parametrico (7 celle: sweep + summary + plot comparativi + push aggregati)
- `.gitattributes` — `*.ipynb filter=nbstripout` (one-shot setup, mai più "would be overwritten by merge")

### Cache & artefatti
- `data/cache_*.pt` — dataset persistenti (NON committati, .gitignore)
- `checkpoints/<TAG>/` — pesi modello + CSV + plots (NON committati)
- `results/<TAG>/` — CSV + plots **tracciati in git** (whitelist .gitignore)

---

## 🔧 Comandi quick reference

### Locale (Windows PowerShell)
```bash
# Sync stato
git pull origin main && git log --oneline -5

# Lista esperimenti pushati
ls results/

# Analisi rapida di un run
python -c "import pandas as pd; df = pd.read_csv('results/<TAG>/training_log.csv'); print(df)"

# Smoke locale fast iteration (~9 min CPU laptop)
python train.py --tag local_check --scenario_mix highway --cut_in_ratio 0.0 \
                --n_train 200 --n_val 50 --epochs 3 \
                --early_stop_patience 1 --early_stop_delta 0.005 \
                --max_lr 2e-3 --seq_len 50
```

### Azure (Jupyter)
```bash
# Sync codice + notebook
git pull origin main

# Se git lamenta "Your local changes would be overwritten by merge":
git checkout -- Training_File.ipynb && git pull origin main

# Solo Cella 1 va modificata per nuovo esperimento
# Run All esegue: pull → preflight → FULL → display → push results

# Cleanup storage (se compute instance pieno)
!find checkpoints -name "best_model.pt" -delete   # mantiene CSV/PNG
!rm -rf checkpoints/<old_tag>                      # cancella un esperimento intero
```

### Commit di results (fatto automaticamente da Cella 8)
```bash
git add results/<TAG>/
git commit -F /tmp/commit_msg.txt   # messaggio generato auto da Cella 8
git push origin main
```

---

## 🚨 Lezioni cardinali (per non ripetere errori)

1. **NON applicare fix SNN "da manuale" senza verificare l'implementazione specifica del surrogate** (errore B4: detach reset rotto perché `SurrogateSpike_Hardware` non propaga al threshold). Vedi P5.

2. **NON modificare config.py manualmente su Azure** (errore P9_S1_highway_only: identico a P6_T3_full perché config.py non modificato). Vedi P10. Usa CLI/Cella 1.

3. **NON sprecare compute su training oltre il plateau** (P6_T3 ha sprecato ~2h girando E4 destinato al crash). Usa `early_stop_delta` adeguato. Su nostro plateau, `0.005` è giusto (`1e-4` è troppo sensibile, non ferma mai). Vedi P11 + STEP 2A.

4. **Il plateau val_loss ≈ 0.35 (full-mix) o 0.28 (highway-only) è strutturale** (capacity insufficiency). Non insistere con fix anti-crash: aumenta capacità o accetta il plateau. Vedi P8, P9.

5. **L'esplosione del gradiente è SINTOMO, non causa**: rete satura → spike rate degenera → catena ricorrenza U·V amplifica → boom. Vedi P7, P8.

6. **Tutti i fix devono mantenere compatibilità FPGA**: pesi power-of-2, leak bit-shift, surrogate hw-friendly. Vedi `project_core_guidelines.md`.

7. **Cache invalidate vanno rigenerate**: se cambi fisica (es. F1 s_safe=2.0) o scenario, cancella `data/cache_*.pt` o usa nome diverso. Il `CACHE_PATH` in Cella 1 ora include `n_train` + `scenario_mix` + `cut_in_ratio` → collisioni evitate.

8. **Telemetria T è sacra**: i CSV per-batch (`training_batch_log.csv`) sono l'unico modo per diagnosticare run abortiti. Non disabilitarli.

9. **La rete converge nel 10% di E1** (osservazione utente confermata dai dati). Non aspettare 5 epoche: usa fast-iteration con `n_train` ridotto + early stopping aggressivo per **iterare 10-20× più velocemente**. Vedi STEP 2A.

10. **Po2 quantization NON è il plateau**: i pesi raw sono float continui (STE). Il bottleneck è capacity vs task complexity (prova: highway plateau 0.28 ≠ full-mix plateau 0.35 — sarebbe stato lo stesso se Po2 fosse il bottleneck).

---

## 📊 Risultati storici principali

| TAG | Config chiave | E completate | val_loss best | Esito |
|-----|---------------|--------------|---------------|-------|
| (pre-F1) | seq=100, lr=5e-3, no fix | 0 | — | ❌ crash B1000 |
| `A1_onecycle_v3` | + B4 (poi rollback) | 0 | — | ❌ crash B126 (B4 incompatibile) |
| `P6_T2_full` | A3+A1+A2 | 1 | 0.371 | ❌ crash E2 B2395 |
| `P6_T3_full` | + B5 | 3 | **0.354** | ❌ crash E4 (47 inf grad) |
| `P9_S1_highway_only` | (=P6_T3, config.py drift) | 3 | 0.354 | ❌ identico a P6_T3 |
| `P9_S1_highway_v2` | + P10 + P11 + scenario CLI | 2 | **0.277** | ❌ crash E3 — **P9 CONFERMATO!** (-22% vs full-mix) |
| **`P9_S2A_fast_baseline`** | + STEP 2A (n_train=500, delta=0.005, h32_r8, highway) | 4 | **0.2802** | ✅ confermata fast-iteration |
| **`P9_S2B_h32_r8_hw`** | sweep STEP 2B (h=32, r=8) | 4 | 0.2802 | ✅ baseline replicato |
| **`P9_S2B_h48_r12_hw`** | sweep STEP 2B (h=48, r=12) | 4 | **0.2789** ★ | ✅ best del sweep |
| **`P9_S2B_h64_r16_hw`** | sweep STEP 2B (h=64, r=16) | 4 | 0.2790 | ✅ sweet spot |
| **`P9_S2B_h96_r24_hw`** | sweep STEP 2B (h=96, r=24) | 4 | 0.2797 | ✅ |
| **`P9_S2B_h128_r32_hw`** | sweep STEP 2B (h=128, r=32) | 4 | 0.2792 | ✅ |
| **`P9_S2B_h64_r16_urban`** | sweep STEP 2B (urban) | 2 | 0.3884 | ⚠️ crash E3 (dead neurons) |
| **`P9_S2B_h64_r16_truck`** | sweep STEP 2B (truck) | 5 | **0.1601** ★ | ⚠️ crash E5 (best assoluto!) |

**Pattern aggiornato 2026-05-29**: 
- Capacity highway: tutti i 5 valori (h=32→128) hanno val_best ∈ [0.279, 0.280] → **P9 FALSIFICATO**
- Scenario diversity: highway 0.279 ok, urban 0.388 crash (dead neurons), truck 0.160 best ma crash post-converg
- **Insight chiave**: la rete CAN scendere sotto 0.20 (truck dimostra), il limite è scenario-specific, non capacity.

---

## 🎯 Cosa fare adesso (per un nuovo agente / sessione)

### Se l'utente dice "ho lanciato STEP 2A, ecco i risultati":
1. `git pull origin main`
2. `ls results/P9_S2A_fast_baseline/`
3. Analizza `training_log.csv` per val_loss
4. Confronto con `P9_S1_highway_v2` (val=0.277)
5. Applica decision tree sopra → propone STEP 2B

### Se l'utente dice "non ho ancora lanciato":
- Ricorda che il notebook è già pronto (commit `ed8debb`)
- Verifica che lui faccia `git pull` su Azure
- Spiega cosa atteso: ~15-25 min, val_loss ≈ 0.28-0.30 atteso

### Se l'utente dice "nuova diagnosi/problema":
1. Leggi `P_S.md` per stato problemi correnti
2. Leggi `TIMELINE.md` per capire perché siamo qui
3. Consulta skill `SNN-expert` (ch22 §22.x) se è diagnosi tecnica
4. Propone fix tracciandolo come nuovo `P<N>` in `P_S.md`

### Se l'utente vuole STEP 2B:
- Discuti con lui quali variabili sweep (HIDDEN_SIZE / RANK / scheduler)
- Implementa CLI `--cf_hidden_size` e `--cf_rank` in `train.py`
- Aggiorna notebook Cella 1 con `'cf_hidden_size': 64`, ecc.
- Crea N esperimenti con TAG `P9_S2B_h<N>_r<R>` (es. `P9_S2B_h64_r16`)
- Mostra tabella confronto risultati

---

## 🔗 Esterno

- **GitHub**: https://github.com/carmineesposito01-ice-beep/SNN_Experiment
- **Skill diagnostica**: `SNN-expert` (locale, 23 capitoli, ch22 §22.2-22.4 critici)
- **Skill car-following**: `car-follow-expert` (Treiber & Kesting 2025, ch12 ACC-IDM)
- **Hardware target**: PYNQ-Z1 FPGA (Xilinx Zynq-7020)

---

## 📝 Log aggiornamenti questo file

| Data | Cambio | Autore |
|------|--------|--------|
| 2026-05-28 18:00 | Creato (post commit `3dedf51`) | claude (session 28/05) |
| 2026-05-28 21:00 | Aggiornato post `ed8debb` (STEP 2A) + P9 confermato + eurekas utente | claude (session 28/05) |
| 2026-05-29 12:00 | Aggiornato post `534c2af` (sweep STEP 2B 7/9 + analisi optimizer + design STEP 2C). **P9 FALSIFICATO**, apertura P12+P13, decision matrix optimizers, ricetta modernista AdamW+CosineWR+SWA+SAM proposta | claude (session 29/05) |
