# GLOSSARY.md — Decode degli acronimi usati nel progetto

> Tutti i codici usati in commit, log, plot, documenti. Aggiornare quando si introduce un nuovo prefisso.

---

## 🩺 P1-P14 — Problemi diagnosticati (vedi `P_S.md` per dettagli)

| Codice | Nome | Status |
|--------|------|--------|
| **P1** | Exploding gradient deterministico (originale, B1000/E01) | risolto parzialmente da A3+A1+A2+B5 |
| **P2** | Checkpoint pre-F5 manca `decode_scale` buffer | ✅ risolto da D2 (strict=False) |
| **P3** | Telemetria mancante (era impossibile diagnosticare post-crash) | ✅ risolto da T + grafici G8-G12 |
| **P4** | Rischio FULL senza preflight | ✅ risolto da PF (preflight obbligatorio) |
| **P5** | B4 incompatibile con `SurrogateSpike_Hardware` (rompe ALIF cell learning) | ✅ documentato + rollback |
| **P6** | Roadmap revisione post-P5 (Tier 1/2/3/4) | strategia: A1+A2+A3+B5 (Tier 3) |
| **P7** | Spike-rate saturation post-B5 (oscillazione 5%→25%→50%) | ⚠️ collegato a P14 |
| **P8** | Plateau val_loss ≈ 0.35 in tutti i run (osservazione utente, confermata matematicamente) | confermato (sostituito da P12 → P14) |
| **P9** | Capacity insufficiency (rete UNDERSIZED, 864 param insufficient per task) | ❌ **FALSIFICATO 2026-05-29** (sweep capacity Δval=1.3‰) |
| **P10** | Config drift: SCENARIO_MIX/CUT_IN_RATIO non controllabili da CLI | ✅ risolto (commit 3dedf51) |
| **P11** | Early stopping mancante (spreco compute + crash post-plateau) | ✅ risolto (commit 3dedf51) |
| **P12** | Plateau val~0.28 non-capacity (cause candidate: minimi locali, dataset saturation, Pareto PINN, Po2 floor) | ✅ chiuso da P14 (decomposizione 2026-05-31) |
| **P13** | Scenario crashes: urban dead-neurons + truck post-convergence grad explosion | ⏸️ aperto, basso priority (target post-STEP 2E) |
| **P14** | **Decomposizione floor val~0.28**: 19% OU + 0.2% Po2 + 0.2% SR + 78% architettura | ✅ **chiuso 2026-05-31** (sweep F1-F7, branch `Floor_Diagnostic`) |

---

## 🎛️ A1-A3 — Lever architetturali "soft" (Tier 1-2 del piano P6)

| Codice | Modifica | Status |
|--------|----------|--------|
| **A1** | `max_lr` da 5e-3 → 2e-3 (LR softer per OneCycleLR) | ✅ applicato in P6_T2+ |
| **A2** | `seq_len` da 100 → 50 (dimezza profondità BPTT) | ✅ applicato in P6_T2+ |
| **A3** | γ surrogate da 0.3 → 1.0 in `core/hardware.py` (kernel 3× più stretto) | ✅ applicato (commit `1eff0b0`) |

---

## 🏗️ B4-B6 — Lever strutturali "bigger" (Tier 2-3-4 del piano P6)

| Codice | Modifica | Status |
|--------|----------|--------|
| **B4** | `.detach()` sul reset path ALIF (spezza catena BPTT) | ❌ **SCARTATO** — vedi P5, rotto perché surrogate hw non propaga al threshold |
| **B5** | Spike-rate regularizer `λ_sr·(spike_rate − 0.15)²` in `pinn_loss()` | ✅ applicato (commit `a13afb6`) |
| **B6** | TBPTT (Truncated BPTT) — chunking della sequenza temporale | ⏸️ in stand-by come escalation finale |

---

## 🔬 F1-F12 — 12 Fix SNN-expert review (commit `4e01bcc`, 2026-05-26)

| Codice | Modifica | File |
|--------|----------|------|
| **F1** | s_safe `0.01 → 2.0` in `_acc_iidm_accel` (allineamento generator ↔ network) | `data/generator.py` |
| **F2** | val_epoch NaN guard | `train.py` |
| **F3** | `plot_diagnostics` crash su CSV vuoto (training abortito) | `plot_diagnostics.py` |
| **F4** | `forward_sequence_with_stats` da monkey-patch a metodo di classe | `network.py` + `train.py` |
| **F5** | `_decode_params`: pre-scaling `decode_scale` per gradiente bilanciato (v0/T 18.5× squilibrio) | `network.py` |
| **F6** | OU floor irreducibile documentato (~1.8e-4) | `network.py` docstring |
| **F7** | delta=4 hardcoded documentato (coerente con config) | `network.py` |
| **F8** | `deque` invece di `list` per delay buffer (O(1) vs O(n)) | `network.py` |
| **F9** | `thresh_jump.clamp(min=0)` invece di `abs()` (più efficiente, gradiente simmetrico) | `neurons.py` |
| **F10** | `fatigue.clamp(min=0)` invece di `relu` (ridondante, gradiente equivalente) | `neurons.py` |
| **F11** | Docstring `max_delay`: 0.6s → 0.06s (era errato di un fattore 10) | `network.py` |
| **F12** | γ=0.3 surrogate documentato come scelta Bellec 2018 LSNN (poi rivisto in A3) | `hardware.py` |

---

## 📊 T — Telemetria estesa per-batch (commit `1ff3da9`, 2026-05-27)

- Nuovo file `training_batch_log.csv` per ogni run
- 20 colonne: epoch, batch_idx, loss components, spike_rate, gn per-layer, weight_max, flags inf/nan
- `BatchCSVLogger` classe che flusha ogni 50 righe (append-only, sopravvive a crash)
- Helper `_make_batch_row` riusato dai 3 path di `train_epoch` (normale/NaN/inf)
- Visibile in grafici **G8-G13**

---

## 🚦 PF — Pre-flight doppio smoke (commit `1ff3da9`)

- Script `scripts/preflight.py`
- Lancia 2 smoke consecutivi prima di ogni FULL training
- Verifica 7 criteri pass su ENTRAMBI: exit code 0, no `[EARLY-STOP]`, CSV >= righe minime, ≥5 PNG, best_model loadable, no `RuntimeError/Traceback`
- Costo ~2× ~2 min (CPU) / ~30s (GPU)
- ROI: 1 FULL salvato (~30 min) ripaga 100× il costo di tutti i preflight precedenti
- **Regola permanente**: obbligatorio prima di ogni training ≥3 epoche

---

## 🗝️ D1-D3 — Soluzioni a P2 (checkpoint compat)

| Codice | Soluzione | Status |
|--------|-----------|--------|
| **D1** | Cancellare manualmente `best_model.pt` stale | applicato una tantum |
| **D2** | `load_state_dict(..., strict=False)` (fix permanente) | ✅ applicato in `train.py` |
| **D3** | Print delle chiavi missing/unexpected per audit | ✅ incluso in D2 |

---

## 🚀 STEP 2A / 2B / 2C / 2D / 2E — Roadmap completa

Sequenza di esperimenti per identificare e affrontare la causa del plateau a val~0.28.

| Codice | Significato | Status | Tempo |
|--------|-------------|--------|-------|
| **STEP 2A** | Fast iteration baseline: `n_train=500, epochs=10, early_stop_delta=0.005` con h=32 r=8 | ✅ completato (val=0.2802) | ~17 min |
| **STEP 2B** | Parametric sweep capacity (h=32→128) + scenario diversity | ✅ completato 7/9 → **P9 FALSIFICATO** | ~3h |
| **STEP 2C** | Optimizer Exploration (branch `Optimizer_Exploration`): AdamW vs Prodigy + sweep 6 config Prodigy | ✅ completato → AdamW marginalmente migliore, Prodigy in FUTURE_WORK F1 | ~6h |
| **STEP 2D** | Floor Diagnostic (branch `Floor_Diagnostic`): F1/F2/F3 (PINN/OU/dataset) + F5/F6/F7 (decomposizione residuo incl. Po2) | ✅ completato → **P14 chiuso** | ~5h |
| **STEP 2E** | Mitigation (post-decomposition): 4 opzioni in FUTURE_WORK (F2 EventProp, F3 curriculum, F4 arch mod, F5 accept&deploy) | 🟡 decisione utente | variabile |

**Pattern TAG**:
- `P9_S2A_*`, `P9_S2B_h<HIDDEN>_r<RANK>_<scen>` (legacy capacity sweep)
- `P12_S2C_planA|planB_*` (Optimizer_Exploration Plan A=Prodigy, Plan B=AdamW)
- `P12_S2Cb_*` (sweep Prodigy 6 config: lr × batch × d_coef)
- `P12_S2D_F<1-7>_*` (Floor Diagnostic ablation per fattore)

---

## 🔬 F1-F7 — Floor Diagnostic ablations (STEP 2D, branch `Floor_Diagnostic`)

| Codice | Tag | Override vs baseline AdamW | val_best | Conclusione |
|--------|-----|----------------------------|----------|-------------|
| **F1** | `P12_S2D_F1_no_pinn` | `lambda_phys=ou=bc=0` | 0.2738 | PINN multi-obj NON è il colpevole (Δ=-0.007) |
| **F2** | `P12_S2D_F2_no_ou` | `noise_scale=0.0` (cache fresh) | **0.2262** | 🎯 OU spiega 19.3% del floor |
| **F3** | `P12_S2D_F3_dataset_big` | `n_train=5000` (dataset 3.3×) | 0.2802 | Dataset size irrilevante (Δ≈0) |
| ~~F4~~ | _differita_ | ~~Po2 quantization OFF~~ | — | sostituita da F6 |
| **F5** | `P12_S2D_F5_no_ou_no_sr` | `noise_scale=0` + `lambda_sr=0` | 0.2256 | SR pesa 0.2% (vs F2) |
| **F6** | `P12_S2D_F6_no_ou_no_po2` | `noise_scale=0` + `po2_enabled=0` | 0.2256 | Po2 pesa 0.2% (vs F2) — sorprendente |
| **F7** | `P12_S2D_F7_no_ou_no_sr_no_po2` | tutti e 3 OFF | **0.2198** | Floor pulito = residuo architettura |

**Decomposizione**: vedi `P_S.md` §14.3.

---

## 🎚️ CLI flags introdotte in STEP 2C/2D (post-merge in main)

| Flag | Default | Branch origine | Scopo |
|------|---------|----------------|-------|
| `--max_steps_per_epoch N` | -1 (unlimited) | Optimizer_Exploration | Cap step training per epoca (budget control) |
| `--val_batch_size N` | -1 (fallback `--batch_size`) | Optimizer_Exploration | Disaccoppia val da train (utile per batch=1) |
| `--scheduler none` | — | Optimizer_Exploration | Nessun scheduler (per ottimizzatori auto-adattivi tipo Prodigy) |
| `--optimizer prodigy` | adam (default) | Optimizer_Exploration | Prodigy LR-free (lazy import `prodigyopt`) |
| `--prodigy_d_coef F` | 1.0 | Optimizer_Exploration | Scaler crescita parametro adattivo `d` di Prodigy |
| `--noise_scale F` | 1.0 | Floor_Diagnostic | Scaler ampiezza OU noise nel generator (0.0 = deterministico) |
| `--po2_enabled {0,1}` | 1 (legacy) | Floor_Diagnostic | Toggle Po2 quantization su pesi (LIVE via env var `PO2_ENABLED`) |

---

## 🔬 Toggle env-var introdotti

| Env var | Valori | Effetto |
|---------|--------|---------|
| `PO2_ENABLED` | `0`/`1` (o `false`/`true`/`OFF`/`on`) | Letto LIVE in `core.hardware.PowerOf2Quantize.forward()`. Default `1` = quantization attiva (legacy). `0` = passthrough fp32. Reversibile istantaneamente. Settato da `train.py` dopo argparse. |

---

## 🧮 Ottimizzatori catalogati (riferimento STEP 2C, vedi SESSION_RESUME per matrice completa)

| Sigla | Nome esteso | Tier | Anno | Note per il nostro caso |
|---|---|---|---|---|
| **AdamW** | Adam with Decoupled Weight Decay | 1 | 2017 | Default skill SNN-expert. Stable, +regolarizzazione |
| **CosineAnnealingWarmRestarts (SGDR)** | Stochastic Gradient Descent with Restarts | 1 | 2017 | Warm restart ogni T_0 epochs → esce dai minimi locali |
| **SWA** | Stochastic Weight Averaging | 3 wrap | 2018 | Average weights ultime N epoche → minimi piatti gratis |
| **SAM** | Sharpness-Aware Minimization | 3 wrap | 2021 | 2 forward+backward per step. Forza flat minima |
| **SAST** | Sharpness Aware Surrogate Training | 1 | 2026 | SAM applicato a SNN. Paper recente che valida l'approccio per noi |
| **Lookahead** | k step fast + slow pull | 3 wrap | 2019 | Smooth oscillazioni |
| **Snapshot Ensemble** | Ensemble di snapshot ai warm restart | 3 wrap | 2017 | +1-2% gratis al test |
| **Lion** | EvoLved Sign Momentum (Google) | 1 | 2023 | Sign of momentum. Usato in Spyx (framework JAX SNN) |
| **Prodigy** | Parameter-free adaptive | 2 | ICML 2024 | No lr tuning. Non testato su SNN |
| **D-Adaptation** | Parameter-free predecessore di Prodigy | 2 | ICML 2023 | Sostituito da Prodigy |
| **Sophia** | Second-order with Hessian | 2 | Stanford 2023 | Hessian-aware, 2× speedup LLM. Costoso |
| **AdaBelief** | Adaptive belief in gradient | 2 | NeurIPS 2020 | +0.5% marginale vs Adam |
| **ADMM-SNN** | Alternating Direction Multipliers | 4 SNN | 2025 | Non SGD-derived, sperimentale |
| **Rate-based BP** | Rate-coding shortcut | 4 SNN | NeurIPS 2024 | Riduce complessità BPTT |
| **e-prop** | Eligibility-trace local BPTT | 4 SNN | Bellec 2020 | Biologicamente plausibile |
| **EventProp** | Adjoint exact gradient | 4 SNN | Wunderlich 2021 | O(spikes) memoria invece di O(T·N) |

---

## 💡 Concetti emersi dalle sessioni (eurekas + diagnosi)

| Concetto | Significato | Riferimento |
|----------|-------------|-------------|
| **Plateau val_loss** | Limite asintotico inferiore della val_loss. Highway-only ~0.28 (non capacity-related, vedi P12) | P8 → P12 |
| **Plateau dancing** | Pattern oscillatorio della loss quando la rete è a plateau. Std≈0.024 sul nostro modello | Eureka 1 |
| **Fast iteration mode** | n_train=500, epochs=10, early_stop_delta=0.005. Permette sweep in poche ore | STEP 2A |
| **Capacity insufficiency** | ❌ FALSIFICATO 2026-05-29 (sweep h=32→128, Δval=1.3‰) | P9 |
| **Po2 ≠ plateau** | Po2 quantization NON determina il plateau (i pesi raw sono float) | Eureka 1 corretta |
| **Convergenza in 10% di E1** | 90% miglioramento nei primi 10% dei batch dell'epoca 1 | Eureka 2 |
| **Minimi locali da OneCycle troncato** | OneCycle con epochs=10 + early stop aggressivo non vede la decay phase profonda → val=0.28 può essere minimo locale temporaneo | Discussione 2026-05-29 |
| **Scenario asimmetria informativa** | Truck val=0.16 dimostra che la rete CAN scendere sotto 0.20 → plateau highway non è limite intrinseco | Analisi P13 2026-05-29 |
| **Sharp landscape da Po2** | Quantization Po2 + low-rank recurrence creano landscape "a scalini" → SAM o SurrogateSAM particolarmente indicati | Studio optimizer 2026-05-29 |
| **Dead-neurons collapse (urban)** | Spike rate < 1% → niente gradiente effettivo → grad explosion. ch22 §22.2 + §22.4 dello skill SNN-expert | P13 |
| **Post-convergence explosion (truck)** | La rete "impara troppo bene" → trovati minimi profondi → lr=2e-3 in decay phase ancora troppo alto → step grandi → divergenza | P13 |
| **SAST (2026)** | Paper recente che applica SAM al training SNN. Valida AdamW+SAM come ricetta moderna SNN | STEP 2C catalogo |
| **SurrogateSAM** | Variante SAM (idea originale 2026-05-29): perturba (W, γ) insieme — flat sia nello spazio pesi sia nella forma surrogate. R&D opzionale | STEP 2C-γ |
| **"Funziona bene" (definizione 2026-05-29)** | val < 0.10 SOTA, < 0.15 competitivo con ANN classico, < 0.20 buono per FPGA deployment. Treiber Ch17 floor ~0.20 | SESSION_RESUME |

---

## ⚙️ CLI args di `train.py` (post-STEP 2A)

### Training base
| Arg | Default | Esempio |
|-----|---------|---------|
| `--epochs` | 50 (config) | `--epochs 10` |
| `--batch_size` | 64 | `--batch_size 128` |
| `--seq_len` | 100 | `--seq_len 50` |
| `--lr` | 0.001 | `--lr 1e-3` |
| `--scheduler` | plateau | `--scheduler onecycle` |
| `--max_lr` (per onecycle) | 5e-3 | `--max_lr 2e-3` |
| `--T0` (per cosine) | 5 | `--T0 5` |
| `--optimizer` | adam | `--optimizer adamw` |
| `--smoke` | False | `--smoke` (1 epoca, n≤100) |
| `--tag` | 'run' | `--tag P9_S2A_fast` |

### Dataset (P10)
| Arg | Default | Esempio |
|-----|---------|---------|
| `--n_train` | 5000 | `--n_train 500` |
| `--n_val` | 500 | `--n_val 100` |
| `--scenario_mix` | 'default' | `--scenario_mix highway` |
| `--cut_in_ratio` | None (= config) | `--cut_in_ratio 0.0` |
| `--data_cache` | None | `--data_cache data/cache_500_highway_cut0.0.pt` |

### PINN loss
| Arg | Default (config) | Esempio |
|-----|-----------------|---------|
| `--lambda_data` | 1.0 | `--lambda_data 1.0` |
| `--lambda_phys` | 0.1 | `--lambda_phys 0.1` |
| `--lambda_ou` | 0.05 | `--lambda_ou 0.05` |
| `--lambda_bc` | 1.0 | `--lambda_bc 1.0` |
| `--lambda_sr` (B5) | 0.5 | `--lambda_sr 0.5` |

### Early stopping (P11)
| Arg | Default | Esempio |
|-----|---------|---------|
| `--early_stop_patience` | 0 (disabled) | `--early_stop_patience 2` |
| `--early_stop_delta` | 1e-4 | `--early_stop_delta 0.005` (STEP 2A) |

### Diagnostica
| Arg | Default | Esempio |
|-----|---------|---------|
| `--max_inf_streak` | 20 | `--max_inf_streak 20` |
| `--log_every` | 50 | `--log_every 50` |

### Da implementare per STEP 2B (NON ancora presenti)
| Arg | Significato |
|-----|-------------|
| `--cf_hidden_size` | Sovrascrive `CF_HIDDEN_SIZE` (default 32) — TBD STEP 2B |
| `--cf_rank` | Sovrascrive `CF_RANK` (default 8) — TBD STEP 2B |

---

## 🖼️ G1-G13 — Grafici diagnostici (in `plots/<TAG>/`)

### Per-epoca (G1-G7) — letti da `training_log.csv`
| Codice | Cosa mostra | Quando utile |
|--------|-------------|--------------|
| **G1** | Train/val total loss vs epoch | Visione globale convergenza |
| **G2** | Componenti loss val (data, phys, OU, bc, sr) | Capire quale termine domina |
| **G3** | LR schedule | Verifica scheduler (onecycle/cosine/plateau) |
| **G4** | grad_norm medio per epoca | Trend instabilità |
| **G5** | Scatter T_pred vs T_true (sul val set) | Quanto la rete riconosce il T |
| **G6** | Spike rate per epoca | Trend dead network vs saturation |
| **G7** | Violin plot dei 5 parametri predetti | Distribuzione vs bound fisici |

### Per-batch (G8-G12) — letti da `training_batch_log.csv` (T)
| Codice | Cosa mostra | Quando utile |
|--------|-------------|--------------|
| **G8** | gn pre/post clip per batch (scala log) | Vedere ESATTAMENTE quando esplode |
| **G9** | Heatmap log10(gn) per-layer × batch | Quale layer esplode PRIMA |
| **G10** | Componenti loss per batch (4-5 linee) | Quale termine diverge prima del totale |
| **G11** | Spike rate per batch (oscillazioni rapide) | Pattern saturazione vs degenerazione |
| **G12** | Max\|w\| globale per batch | Conferma che il clip mantiene pesi finiti |

### Per-trajectory (G13) — 3 PNG per scenario
| Codice | Cosa mostra |
|--------|-------------|
| **G13_traj_<scenario>.png** | Triplo subplot: V2V signals (TOP) / T_pred vs T_true (MID) / v0,s0,a,b predetti vs scenario constants (BOT). 3 traiettorie: highway, urban, highway_cutin |

---

## 🏷️ TAG dei run (convenzioni)

| Pattern | Significato |
|---------|-------------|
| `<NAME>_preflight_1` / `_2` | I 2 smoke del preflight (auto-generati da `scripts/preflight.py`) |
| `<NAME>_validation` | Smoke esteso post-preflight per validare config |
| `A1`, `A2`, `A3` (storici) | Run di confronto fra scheduler (onecycle/cosine/plateau) |
| `P6_T*` | Tier-N del piano P6 (T1=tier1, T2=tier2, ...) |
| `P9_S*` | Step-N del piano P9 (S1=highway-only, S2=capacity-increase) |
| `local_*` | Smoke locale per validazione, non per analisi |

---

## 🧮 Altri termini

- **ACC-IDM**: modello fisico = Adaptive Cruise Control IDM con base IIDM + CAH blend (Treiber Ch12 §12.4)
- **IDM**: 5 parametri `[v0, T, s0, a, b]` (free speed, time gap, min gap, accel max, decel max)
- **IDM-2d** (minuscolo): processo OU stocastico su T (Treiber Ch12 §12.6), NON un modello complessivo
- **IIDM**: Improved IDM (Treiber Ch12 §12.4), base del nostro ACC-IDM
- **CAH**: Constant Acceleration Heuristic (Treiber Eq.12.35), anticipa frenata leader
- **ALIF**: Adaptive Leaky Integrate-and-Fire neuron (con soglia adattiva via fatigue)
- **LI**: Leaky Integrator (output layer, no spike)
- **BPTT**: Backpropagation Through Time
- **Surrogate gradient**: derivata sostitutiva del Heaviside (la nostra è hardware-friendly, no propagation al threshold)
- **V2X**: Vehicle-to-Everything (i 4 segnali input: gap s, vel ego v, Δv = v−v_l, vel leader v_l)
- **PYNQ-Z1**: target FPGA hardware (Xilinx Zynq-7020)
- **PINN**: Physics-Informed Neural Network (loss = data + physics constraints)
- **OU**: Ornstein-Uhlenbeck (processo stocastico per T)

---

## 📋 Convenzioni di status nelle tabelle

| Marker | Significato |
|--------|-------------|
| `[ ]` | proposta, non implementata |
| `[~]` | in test |
| `[x]` | applicata |
| `[!]` | scartata definitivamente |
| ✅ | completato/funzionante |
| ⚠️ | warning/parziale |
| ❌ | fallito/scartato |
| ⏸️ | in stand-by / pianificato per futuro |
| ⏳ | in esecuzione |
| ⭐ | canonical/preferito |

---

## 🆕 R1-R3 — Roadmap audit-driven (post 2026-06-02 AUDIT)

| Codice | Nome | Status | Branch git |
|--------|------|--------|------------|
| **R1** | `Arch_Tested/` snapshot riproducibile architetture funzionanti | ✅ chiuso 2026-06-02 | `Arch_Tested_Setup` (mergiato + cancellato) |
| **R1.7** | Aggiunta `BASELINE_BPTT_864p_PRE_EVENTPROP` (vera baseline pre-EventProp, lambda_sr=0.5) | ✅ chiuso 2026-06-02 | `Arch_Tested_Fix_Baseline` (mergiato + cancellato) |
| **R2** | Studio Prodigy CAPIRE (paper + community wisdom + 5 esperimenti) | ⏳ in esecuzione Azure | `Prodigy_Deep_Study` |
| **R2.1** | Reading + doc (`PRODIGY_DEEP_STUDY.md` parte 1 + 2) | ✅ chiuso 2026-06-02 | idem |
| **R2.2** | 5 esperimenti diagnostici P-A..P-E (`Prodigy_Diagnostics.ipynb`) | ⏳ run Azure | idem |
| **R2.2.fix** | Sub-folder `results/Prodigy_Study/` + Python <3.12 f-string fix | ✅ chiuso 2026-06-02 | idem |
| **R3** | Studio EventProp serio (paper + 7 lever isolati + fair comparison) | ⏸️ pending (dopo R2) | `EventProp_Deep_Study` (da creare) |

### V1-V4 + W1-W7 — Lever Prodigy emersi da ricerca multi-fonte (R2.1)

Vedi `PRODIGY_DEEP_STUDY.md` parte 2 sezioni 10 e 11 per dettagli + fonti.

| Codice | Origine | Cosa dice |
|--------|---------|-----------|
| **V1** | konstmish (Issue #3) | Senza scheduler, Prodigy agnostico al numero step |
| **V2** | konstmish (Issue #27, fix ufficiale) | Se `d` frozen, bump `d0` da 1e-6 a 1e-5/1e-4 |
| **V3** | konstmish (Issue #8, #10) | Cosine annealing T_max=total_steps, NIENTE restarts |
| **V4** | konstmish (Issue #18) | Prodigy = Adam/AdamW + D-adaptation |
| **W1** | madman404 (Issue #8) | `betas=(0.9, 0.99)` "dramatic improvement" (beta3=beta2^0.5) |
| **W2** | community kohya/OneTrainer/bdsqlsz | `d_coef=2.0` standard (non 1.0 default) |
| **W3** | community + README diffusion | `use_bias_correction=True` (boost early steps) |
| **W4** | konstmish (Issue #3) + OneTrainer | `weight_decay=0.01` AdamW default |
| **W5** | LoganBooker (`prodigy-plus-schedule-free` FAQ) | Monitorare `d` + norma pesi insieme |
| **W6** | LoganBooker (Issue #27) | Min 200-300 step warmup naturale, 1000+ stabile |
| **W7** | community discrepanza | `safeguard_warmup` True se warmup/restarts |

### P-A..P-E — 5 esperimenti diagnostici R2.2

| ID | Setup | Lever isolato |
|----|-------|---------------|
| **P-A** | baseline T30 replica (default Prodigy lib + safeguard ON) | conferma d frozen |
| **P-B** | P-A + `betas=(0.9, 0.99)` | W1 |
| **P-C** | P-A + `d_coef=2.0` | W2 |
| **P-D** | P-A + `d0=1e-5` | V2 (fix konstmish) |
| **P-E** | SETUP CANONICAL KOHYA completo + `cosine_no_restart` | tutti i lever insieme |

### Arch_Tested/ — Snapshot architetture funzionanti (R1)

| Cartella | Source run | Status |
|----------|------------|--------|
| ⭐ `BASELINE_BPTT_864p_PRE_EVENTPROP` | `P12_S2D_F2_no_ou` (lambda_sr=0.5) | **Canonical per R2/R3** |
| `A1_baseline_BPTT_864p` | `T30_A1_BASELINE_adamw` (lambda_sr=0) | ⚠️ DEPRECATED |
| `A8_attn_BPTT_3936p` | `T30_A8_ATTN_adamw` | 3936p, best architettonico ma overfit possibile |
| `A3_stacked_skip_BPTT_2624p` | `T30_A3_STACKED_SKIP_adamw` | 2624p |
| `EVPROP_ALIF_full_864p` | `SW_eventprop_alif_full_adamw_lr2e-3` (5ep sched=none) | EventProp adjoint |

### `results/<Study>/` — Convention sub-folder dedicata (post 2026-06-02)

Ogni studio futuro ha sub-folder dedicata in `results/`:
- `results/Prodigy_Study/` — R2 (in corso)
- `results/EventProp_Study/` — R3 (futuro)
- `results/<Run_Tag>/` — run storiche restano nel root di `results/` per archeologia

### Scheduler `cosine_no_restart` — nuovo (R2.2)

Aggiunto in train.py. `CosineAnnealingLR` puro con `T_max=epochs`. Da NON confondere con `cosine` esistente che usa `CosineAnnealingWarmRestarts` (sconsigliato per Prodigy da konstmish Issue #8).

### CLI flag Prodigy aggiunti (R2.2)

- `--prodigy_betas STR` (default `'0.9,0.999'`) — formato `'b1,b2'`
- `--prodigy_use_bias_correction {0,1}` (default 0, raccomandato 1)
- `--prodigy_d0 FLOAT` (default 1e-6, bump a 1e-5 se d frozen)
- `--prodigy_weight_decay FLOAT` (default -1 = sentinel `1e-4` hardcoded storico, raccomandato 0.01)
- `--prodigy_safeguard_warmup {0,1}` (default 1, era hardcoded True)
- `--prodigy_growth_rate FLOAT` (default inf, era hardcoded inf)
- `--prodigy_d_coef FLOAT` (default 1.0, esistente da STEP 2C)

---

## 📚 Documenti recenti (post 2026-06-02)

| Doc | Scopo |
|-----|-------|
| ⭐ `AUDIT_2026-06-02.md` | Bilancio onesto + roadmap R1/R2/R3 (radice di tutto) |
| `PRODIGY_DEEP_STUDY.md` | Parte 1 math + Parte 2 community wisdom (ricerca multi-fonte) |
| `SIMULATOR_FINDINGS.md` | Drift T² + cut-in analysis simulator |
| `Arch_Tested/README.md` | Overview 5 architetture snapshot |
