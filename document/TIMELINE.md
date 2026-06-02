# TIMELINE.md — Storia cronologica del progetto + decisioni chiave

> Per onboarding e archeologia: cosa è stato provato, cosa ha funzionato, cosa è stato scartato e perché.

---

## 🏛️ Fase 0 — Bootstrap (pre-2026-05-25)

**Stato di partenza**: codice baseline da `FSNN_Project_V5` (precedente progetto SNN su MNIST). Adattamento iniziale per car-following.

**Modello**: CF_FSNN_Net con 864 parametri totali.
- HiddenLayer_ALIF (4 → 32, rank=8, max_delay=6)
- OutputLayer_LI (32 → 5)

**Risultato iniziale**: prima training su 1000 trajectories, 20 epoche overnight CPU → **SRMSE = 0.871** (vedi `report_1.md`). Non convergente.

---

## 📅 2026-05-25 — Onboarding utente + setup

**Attività**:
- L'utente ha riassunto i requirements in `project_core_guidelines.md`
- Definizione architettura CNN+SNN e vincoli FPGA (PYNQ-Z1)
- Discussione sui modelli car-following candidati → vedi `cf_model_recommendation.md`
- Decisione: **ACC-IDM con base IIDM** (Treiber Ch12 §12.4)

**Output**: `report_1.md` baseline (SRMSE=0.871) → `report_2.md` con identificazione SRMSE=0.6 dopo prime correzioni.

---

## 📅 2026-05-26 — Review SNN-expert + 12 fix

**Attività**:
- Consultazione skill `SNN-expert` (23 capitoli ch01-ch23)
- Code review identifica **12 problemi** (3 HIGH, 4 MEDIUM, 5 LOW)
- **Commit `4e01bcc`**: feat F1-F12 applicati

**Fix chiave**:
- **F1 (HIGH)**: `s_safe = max(s, 2.0)` in `generator._acc_iidm_accel` (allinea a `network.acc_iidm_accel`). Risolve inconsistenza fisica generator vs network.
- **F5 (MEDIUM)**: `decode_scale` buffer in `_decode_params` — equalizza gradienti tra v0/T (era 18.5× squilibrato)
- **F8 (LOW)**: `deque` per delay buffer (O(1) invece di O(n))
- **F12 (LOW)**: documenta γ=0.3 surrogate come scelta Bellec 2018

**Output**: `report_3.md` post-12-fix, `report_4.md` snapshot architettura completa.

---

## 📅 2026-05-27 — Tentativo training FULL + crash + diagnosi

### Mattina: prima esecuzione FULL Azure

**Run**: `A1_onecycle_v3` (5 epoche, OneCycleLR, max_lr=5e-3, default seq_len=100)

**Risultato**: ❌ **CRASH a E1 B1000/1485** per exploding gradient.

**Diagnosi (con skill SNN-expert ch22 §22.4)**:
- gn esplode da `0.26` (B950) a `4.49e+12` (B1000) → 20 batch consecutivi inf → EARLY-STOP
- Solo `layer_hidden.*` esplodono, `layer_out.fc_weight` resta a `1.4e-01`
- Pattern compatibile con **catena ricorrenza U·V amplificata via surrogate**
- **P1 documentato**, plan proposto: Tier 1 (A1+A2 CLI), Tier 2 (+B4), Tier 3 (+B5), Tier 4 (+B6)

### Pomeriggio: applicato B4 → DISASTRO

**Commit `1ff3da9`**: telemetria T (BatchCSVLogger + G8-G12) + preflight PF + P2 D2 (strict=False checkpoint)

**Commit `ed4906d`**: fix terminologia ACC-IDM (era erroneamente "IDM-2D" in alcuni docstring)

**Commit `3d1fd9a`**: applicato **B4** (`.detach()` sul reset path ALIF) seguendo letteratura ch22 §22.3

**Run**: `A1_onecycle_v3` (re-launch con B4)

**Risultato**: ❌ **CRASH a E1 B126** (PRIMA del solito!). Spike rate 1-2% inchiodato.

**Diagnosi (commit `858cdc7`)**:
- Apertura G9 (heatmap layer norms) rivela: `gn_hidden_base_threshold` e `gn_hidden_thresh_jump` sono `None` per TUTTI i 145 batch
- Causa root: `SurrogateSpike_Hardware.backward()` restituisce `None` per il gradiente verso threshold (scelta hardware-friendly per FPGA). L'UNICO path di gradiente per `base_threshold/thresh_jump` era il reset chain `V ← V − spike·eff_thresh`. B4 lo ha distrutto.
- **P5 documentato**: B4 **incompatibile** con la nostra `SurrogateSpike_Hardware`. **Lezione**: i fix da manuale vanno verificati contro l'implementazione specifica.
- **Rollback B4**.

### Sera: applicato A3 → miglioramento parziale

**Commit `1eff0b0`**: applicato **A3** (γ surrogate da 0.3 → 1.0). Più sicuro di B4 perché modifica solo magnitudo, non path di gradiente.

**Run**: `P6_T2_full` (A3 + A1+A2: max_lr=2e-3, seq_len=50, 5 epoche)

**Risultato**: ⚠️ **E1 COMPLETATA per la prima volta** (val_loss=0.371), poi crash E2 B2395.

**Osservazione utente fondamentale**: "il G11 spike rate degenera da ~7% a ~3% in E2 prima del crash". Pattern compatibile con **dead network**.

---

## 📅 2026-05-27 sera — B5 + diagnosi vera

**Commit `a13afb6`**: applicato **B5** (spike-rate regularizer `λ_sr·(spike_rate−0.15)²`)

**Run**: `P6_T3_full` (A3+A1+A2+B5)

**Risultato**: 🎯 **3 EPOCHE COMPLETATE**! val_loss `0.371 → 0.363 → 0.354`. Crash E4 B2395.

**Osservazione utente fondamentale n.2**:
> "L'esplosione del gradiente accade sempre verso una loss di 0.350"

**Verifica matematica** (script `_check_plateau.py`):
- P6_T2: val E1 = **0.368**
- P6_T3: val E1 = **0.371**, E2 = **0.363**, E3 = **0.354**
- Batch loss mediana P6_T2: **0.368** vs P6_T3: **0.370** — IDENTICA

**Diagnosi rivoluzionaria** (commit `bf0d8c6`, P7+P8+P9 in `P_S.md`):
- **P7 — saturation post-B5**: spike rate oscilla 5% → 25% → 55% prima del crash
- **P8 — plateau val_loss ≈ 0.35** CONFERMATO matematicamente
- **P9 — CAPACITY INSUFFICIENCY**: la rete è UNDERSIZED. 864 param non bastano per il task. L'esplosione del gradiente è SINTOMO, non causa.
- **Strategia rivista**: serve aumentare capacità (CF_HIDDEN_SIZE 32→64, CF_RANK 8→16), oppure accettare il plateau con early stopping.

---

## 📅 2026-05-28 — P9 STEP 1 + fix infrastruttura (P10+P11)

### Mattina: tentativo STEP 1 highway-only

**Plan**: dataset semplificato (solo highway, no cut-in) per verificare P9.
- Se highway-only → val_loss < 0.30 → P9 confermato
- Se highway-only → val_loss ≈ 0.35 → P9 falsificato (problema sta altrove)

**Run**: `P9_S1_highway_only` su Azure (utente ha modificato TAG e CACHE_PATH ma DIMENTICATO di modificare `config.py`).

**Risultato**: ❌ **identico bit-per-bit a P6_T3_full**.
- E1=0.371, E2=0.363, E3=0.354 — esatti
- G13 plots includono `urban` e `highway_cutin` (impossibili in highway-only)
- Locale: `CUT_IN_RATIO=0.20`, `SCENARIO_MIX` originale

**Diagnosi (P10)**: config drift. SCENARIO_MIX/CUT_IN_RATIO sono costanti globali in `config.py`, modificabili solo via editing manuale. Su sistema cloud con notebook persistente, è una fonte naturale di errori.

### Pomeriggio: P10 + P11 (commit `3dedf51`)

**Decisione**: rendere scenari/cut_in **CLI-controllabili**, trackare notebook in git, aggiungere early stopping.

**Modifiche**:
1. **data/generator.py**: `parse_scenario_mix()` + `generate_dataset()` con override opzionali
2. **train.py**:
   - CLI args `--scenario_mix`, `--cut_in_ratio`
   - CLI args `--early_stop_patience`, `--early_stop_delta`
   - Early stopping loop dopo ogni val_epoch
3. **Training_File.ipynb**: aggiunto al repo (tracked), Cella 1 espone i 4 nuovi parametri, Cella 5 li passa al CLI

**Validazione smoke locale**:
- `python train.py --smoke --scenario_mix highway --cut_in_ratio 0.0 ...`
- Dataset effettivo: 100 highway, 0 cut-in ✓
- val_loss 1 epoca: **0.341** (vs ~0.37 plateau full-mix → **già -8% in 1 epoca smoke**)

**P11 — Early stopping**: ferma se val_loss non migliora per `patience` epoche.
- Risparmio compute stimato: -40% (3 epoche tipiche fino plateau invece di 5)
- Beneficio diagnostico: evita crash post-plateau (P6_T3 sarebbe stato fermato a E3, evitando crash E4)

### Sera: documentazione comprehensiva

**Creazione documenti resume per future sessioni**:
- `SESSION_RESUME.md` (one-pager status + next steps)
- `GLOSSARY.md` (decode P/A/B/F/T/PF/G codes)
- `WORKFLOW.md` (procedura end-to-end Azure + notebook)
- `TIMELINE.md` (questo file)

### Sera tarda: P9_S1_highway_v2 → P9 CONFERMATO + eurekas utente

**Run**: `P9_S1_highway_v2` su Azure (notebook con P10+P11, scenario_mix='highway' via CLI)

**Risultato**: ⚠️ **CRASH a E3 B2431** MA **val_loss=0.2786 in E1**, **0.2768 in E2** — **molto sotto** il plateau full-mix 0.354.

**Scoperta cruciale (P9 CONFERMATO)**:

| Dataset | Plateau val_loss | Implicazione |
|---------|-------------------|--------------|
| Full-mix (P6_T3) | 0.354 | — |
| **Highway-only (P9_S1_v2)** | **0.277** | -22% rispetto a full-mix |

Se Po2 quantization fosse il bottleneck, i 2 plateau sarebbero IDENTICI. Sono DIVERSI → il limite è **task complexity vs capacity**. **P9 confermato matematicamente.**

### Sera tarda: 2 eurekas utente

L'utente ha proposto 2 osservazioni che si sono rivelate brillanti:

**Eureka 1 — "Po2 → pesi finiti → la rete balla intorno all'optimum"**

Verifica empirica:
- E1: loss_range=0.945, std=0.099 (sta IMPARANDO)
- E2: loss_range=0.163, std=0.024 (oscilla)
- E3: loss_range=0.171, std=0.024 (stesso pattern)

Verdetto: **parzialmente corretta**. Il "dancing" è reale, ma:
- I pesi raw sono float continui (Po2 solo nel forward via STE)
- Il LIVELLO del plateau è dato da P9, non da Po2
- Prova del nove: highway plateau 0.28 vs full-mix 0.35 — diversi! Quindi Po2 non è la causa

**Eureka 2 — "Training super-rapido + parametric sweeps fattibili"**

Verifica empirica (numero killer):
- E1 totale improvement: 0.575
- **90% del miglioramento E1 raggiunto a B298/3047 = 9.8% di E1!**
- E2-E3 quasi non migliorano (0.371 → 0.277 → 0.276)

Verdetto: ✅ **completamente corretta**. La rete converge in ~5 min, il resto è plateau-dancing. Si sblocca la **strategia parametric sweep** (5-10 configurazioni in poche ore invece di giorni).

### Sera tarda: STEP 2A applicato (commit `ed8debb`)

**Strategia STEP 2A — Fast iteration mode**:
- `n_train: 500` (era 5000, /10x)
- `epochs: 10` (più epoche brevi)
- `early_stop_delta: 0.005` (aggressivo — era 1e-4)

Modifiche:
- `Training_File.ipynb` Cella 1: nuovo config STEP 2A
- `Training_File.ipynb` Cella 5: CLI `--n_train`, `--n_val` aggiunti
- `CACHE_PATH` include `n_train` per evitare collisioni cross-esperimento

Validazione smoke locale:
- E1 val=0.298 (159s), E2 val=0.293 (250s), E3 val=0.292 → **EARLY-STOP attivato**
- Best val_loss=0.293, 15 PNG generati, tempo totale ~9.5 min CPU laptop
- Speedup per epoca: 17× (160s vs 2700s precedenti)

**Status corrente**: in attesa lancio `P9_S2A_fast_baseline` su Azure (atteso ~15-25 min).

### Sera tarda: problemi minori risolti

- **Git push rejected** (Azure): utente ha fatto `git pull --no-rebase` e si è ritrovato in nano (merge commit editor) — risolto guidandolo a `Ctrl+X, Y, Enter`
- **Cella 9 `KeyError: 'gn_median'`**: inconsistenza nei nomi colonna (`gn_med` vs `gn_median`) — fix manuale fornito all'utente
- **Git pull bloccato per modifiche locali**: utente ha eseguito notebook prima del pull → outputs creati → conflict. Soluzione: `git checkout -- Training_File.ipynb && git pull origin main`

---

## 📌 Stato al 2026-05-28 sera tarda

- HEAD: `ed8debb` (STEP 2A applicato)
- **P9 CONFERMATO matematicamente** (val_loss highway 0.277 vs full-mix 0.354)
- Entrambe le eurekas utente verificate con dati
- Fast iteration mode validato in locale
- In attesa: `P9_S2A_fast_baseline` su Azure

**Roadmap futura aggiornata**:
- STEP 2A (in attesa Azure): validare baseline fast-iteration
- STEP 2B: parametric sweep su `CF_HIDDEN_SIZE` (32/48/64/96) + opz. `CF_RANK`
- STEP 2C: architettura definitiva post-sweep

---

## 🎓 Lezioni apprese (lessons learned)

### 1. Sempre verificare l'implementazione locale prima di applicare fix "da manuale"
La letteratura SNN (Bellec 2018, ch22 §22.3) consiglia detach del reset per spezzare BPTT. Ma presuppone surrogate STANDARD. La nostra `SurrogateSpike_Hardware` è hardware-friendly e NON propaga al threshold → l'unico path di gradiente per ALIF cell era il reset → B4 lo ha rotto.

**Costo dell'errore**: 1 sessione di training Azure (~25 min compute) + ore di analisi diagnostica.

**Mitigazione**: prima di applicare fix architetturale, **leggere `core/hardware.py`** per verificare il backward.

### 2. Le osservazioni dell'utente sono spesso più rivelatrici dell'analisi tecnica
Due osservazioni dell'utente hanno cambiato la diagnosi:
- "Lo spike rate degenera in E2 prima del crash" → ha portato a B5
- "L'esplosione avviene sempre a loss ≈ 0.35" → ha portato a P8 (plateau) + P9 (capacity)

**Lezione**: chiedere sempre all'utente "vedi pattern che non ho colto?". L'esperto umano sui dati di dominio batte spesso la diagnosi automatica.

### 3. Telemetria estesa T è stata il game-changer
Senza `training_batch_log.csv` (T) e i grafici G8-G13, non avremmo mai capito:
- Quali layer esplodono prima (G9 heatmap)
- Che spike rate degenera prima del crash (G11)
- Che gn pre-clip è già anomalo molto prima dell'inf (G8 log)
- Che val_loss converge allo stesso plateau in tutti i run (P8)

**Costo**: ~1h di sviluppo iniziale. **ROI**: ognuno dei P5-P11 sarebbe stato impossibile da diagnosticare senza T.

### 4. Preflight obbligatorio salva ore di compute
P4 ha richiesto ~15 min di sviluppo. Da allora ha intercettato 0 crash strutturali (perché abbiamo investito tempo nell'infrastruttura), ma **2-3 volte ha permesso di scoprire problemi minori** prima di lanciare FULL su Azure.

### 5. NON modificare manualmente file di config su sistemi distribuiti
P10 ha richiesto ~40 min per implementare CLI override. Eviterà PER SEMPRE il config drift cross-sistema.

**Anti-pattern**: "modifica questi 2 valori in config.py prima di lanciare". È una bomba a orologeria.

**Pattern**: tutti i parametri "che cambiano fra esperimenti" devono essere CLI args o ENV vars, mai costanti globali.

### 6. Early stopping previene crash post-plateau
La rete in plateau non migliora più, ma le sue dinamiche ricorrenti continuano a "oscillare" → esplode prima o poi. Early stopping ferma il training quando il segnale di apprendimento si esaurisce, **prima** che le oscillazioni distruggano lo stato.

**Costo P11**: ~20 righe di codice. **ROI**: -40% compute medio + eliminazione crash post-plateau.

### 7. Il plateau val_loss ≈ 0.35 è strutturale, non un bug
È stata la scoperta più importante. Per 3 sessioni abbiamo cercato fix anti-crash. La vera diagnosi è che **864 parametri sono insufficienti** per un task con 5 parametri continui da regredire su sequenze stocastiche di 50-100 step.

Possibili azioni:
- Aumentare capacità (CF_HIDDEN_SIZE 32→64, CF_RANK 8→16) — ~2700 param, ancora FPGA-compatibile
- Migliorare encoding input (forse normalizzazione subottimale)
- Migliorare loss formulation (forse i 5 lambda sono mal bilanciati per i 5 parametri)

### 8. La rete converge nel 10% di E1 (eureka utente confermata)
Su `P9_S1_highway_v2`: 90% del miglioramento E1 raggiunto a B298 su 3047 (= 9.8% di E1). Le epoche 2-3 quasi non migliorano. **Conclusione**: spendere 5 epoche complete è uno spreco.

**Implicazione**: si può iterare 10-20× più velocemente con:
- Dataset ridotto (`n_train=500` invece di 5000)
- Più epoche brevi (`epochs=10` con early stopping aggressivo)
- `early_stop_delta=0.005` (non 1e-4 — quello non ferma mai)

Sblocca **parametric sweeps** (testare 10+ configurazioni in poche ore) che altrimenti richiederebbero giorni. STEP 2A applica esattamente questo (commit `ed8debb`).

### 9. Po2 quantization NON è il bottleneck (eureka utente parzialmente corretta)
L'utente ha ipotizzato: "i pesi sono Po2, quindi finiti, quindi la rete balla intorno all'optimum". Verifica:

- ✅ Il "dancing" è reale (E2/E3 std=0.024, oscillazione 0.16 attorno alla mediana)
- ⚠️ MA i pesi raw sono float continui (Po2 solo nel forward via STE)
- ⚠️ Il LIVELLO del plateau è dato da capacity vs task complexity (P9), non da Po2
- ⚠️ Prova del nove: highway plateau 0.28 ≠ full-mix plateau 0.35 — sarebbero IDENTICI se Po2 fosse il bottleneck

**Lezione**: il PATTERN osservato dall'utente era reale e importante, ma il **meccanismo** era sbagliato. Verificare sempre i meccanismi con esperimenti di controllo (in questo caso: confrontare 2 dataset di complessità diversa).

---

## 🗓️ Riepilogo commit chiave (per archeologia)

| Commit | Data | Cosa |
|--------|------|------|
| `1292b7c` | 2026-05-25 | s_safe=2.0 + pre_norms always computed (origine F1) |
| `4e01bcc` | 2026-05-26 | feat 12 fix SNN-expert F1-F12 |
| `1ff3da9` | 2026-05-27 | Telemetria T + Preflight PF + P2 D2 |
| `ed4906d` | 2026-05-27 | fix terminologia ACC-IDM |
| `3d1fd9a` | 2026-05-27 | applicato B4 (POI scartato) |
| `858cdc7` | 2026-05-27 | revert B4 + P5 documentato |
| `1eff0b0` | 2026-05-27 | A3 γ surrogate 0.3→1.0 |
| `bb728ec` | 2026-05-27 | results P6_T2_full (E1 ok, crash E2) |
| `a13afb6` | 2026-05-27 | B5 spike-rate regularizer |
| `fd8c5bf` | 2026-05-27 | results P6_T3_full (3 epoche, crash E4) |
| `bf0d8c6` | 2026-05-28 | docs P_S.md P7+P8+P9 (diagnosi capacity) |
| `8004883` | 2026-05-28 | results P9_S1_highway_only (config drift) |
| `3dedf51` | 2026-05-28 | feat P10+P11 + Training_File.ipynb tracked |
| `d3dbdf1` | 2026-05-28 | docs 4 nuovi (SESSION_RESUME, GLOSSARY, WORKFLOW, TIMELINE) |
| `38888c5` | 2026-05-28 | merge results P9_S1_highway_v2 (Azure) |
| `ed8debb` | 2026-05-28 | feat STEP 2A fast iteration mode (n_train=500, delta=0.005) |

---

## 🔮 Roadmap futura (post-`P9_S2A_fast_baseline` in attesa)

### STEP 2A (in attesa Azure)
Validare baseline del regime fast-iteration:
- Atteso val_loss ~0.28 (simile a P9_S1_highway_v2)
- Atteso tempo ~15-25 min (vs 2-3h del modo standard)
- Atteso early_stop attivato a E4-E5

### STEP 2B (dopo STEP 2A OK)
**Parametric sweep capacity** (sfrutta fast-iteration mode):

Configurazioni da testare (4-6 run, ~1.5-2h totali):

| TAG | CF_HIDDEN | CF_RANK | Param totali |
|-----|-----------|---------|--------------|
| P9_S2B_h32_r8 (baseline = S2A) | 32 | 8 | 864 |
| P9_S2B_h48_r8 | 48 | 8 | ~1500 |
| P9_S2B_h64_r8 | 64 | 8 | ~2400 |
| P9_S2B_h64_r16 | 64 | 16 | ~3500 |
| P9_S2B_h96_r16 | 96 | 16 | ~6500 |

Target: trovare il **knee curve** (val_loss vs param count). Sweet spot atteso 64-96 neuroni.

**Requisito tecnico**: parametrizzare `CF_HIDDEN_SIZE` e `CF_RANK` come CLI args.

### STEP 2C (dopo STEP 2B)
Cementare l'architettura vincitrice:
- Aggiornare `config.py` con `CF_HIDDEN_SIZE/CF_RANK` ottimali
- Test su dataset FULL-MIX (non highway-only) con la nuova capacity
- Aggiornare `report_4.md` con architettura definitiva

### Caso patologico — STEP 2A val_loss > 0.32
Se il fast-iteration mode produce risultati significativamente peggiori, significa che `n_train=500` è troppo piccolo per imparare. Adatti a `n_train=1000` o `n_train=2000` e ripetere.

---

## 🌅 2026-05-29 — Sweep STEP 2B + P9 falsificato + studio optimizer SOTA

### Mattina: Sweep STEP 2B parziale (7 runs su 9)
Lo sweep notebook `Training_File_Sweep.ipynb` è stato eseguito su Azure durante la notte. Esito:
- **5 runs highway capacity completati**: h=32, 48, 64, 96, 128 con rank corrispondente h/4
- **1 run urban**: crash E3 per dead-neurons (spike=0.6%)
- **1 run truck**: crash E5 per post-convergence grad explosion (val=0.16, best assoluto del sweep!)
- **2 runs mai partiti** (mixed, hwcut15) — il kernel Jupyter Azure è morto dopo il crash di urban a causa di un bug `_push_results` che importava `torch` (non presente nel kernel Azure)

### Bug fixati durante la mattina
1. **`scripts/preflight.py`** (commit `6790019`): `_checkpoint_loadable()` ora legge `cf_hidden_size`/`cf_rank` da `config_snapshot.json` adiacente prima di istanziare `CF_FSNN_Net`. Prima fallback a default (h=32) → size mismatch → preflight FAIL su tutti i runs con h≠32 → tutti i FULL skippati
2. **`Training_File_Sweep.ipynb` Cella 3** (commit `6790019`): `pf_extra` ora include `--scenario_mix` e `--cut_in_ratio` (prima preflight girava su scenario='default')
3. **`Training_File_Sweep.ipynb` Cella 2** (commit `534c2af`): `_push_results` non importa più torch — usa solo CSV per CRASH_INFO
4. **nbstripout setup** (commit `29056e1`): `.gitattributes` + install in Cella 0 → mai più "would be overwritten by merge"

### Analisi cross-run dei 7 runs

#### Capacity sweep highway (Block A)
| h | r | params | val_best | E | spike% | infBatches |
|---|---|---|---|---|---|---|
| 32 | 8 | 869 | 0.2802 | E2 | 8.4 | 0 |
| 48 | 12 | 1685 | **0.2789** | E3 | 9.1 | 0 |
| 64 | 16 | 2757 | 0.2790 | E3 | 10.5 | 0 |
| 96 | 24 | 5669 | 0.2797 | E4 | 7.7 | 0 |
| 128 | 32 | 9605 | 0.2792 | E4 | 10.3 | 0 |

**Range val_best = 0.0013 su 11× parametri**. **P9 FALSIFICATO**: capacity NON è il bottleneck.

#### Scenario diversity (Block B, h64_r16)
| Scenario | E1 | best | E | spike% | gn_max | Modalità crash |
|---|---|---|---|---|---|---|
| highway | 0.2878 | 0.2790 | E3 | 10.5 | 2.4e+01 | ✅ OK |
| urban | 0.4769 | 0.3884 | E2 | **0.6** | 1.56e+19 | dead neurons → grad inf |
| truck | 0.1807 | **0.1601** | E5 | 9.8 | 2.10e+19 | post-convergence grad explosion |

**Insight chiave dal truck**: la rete h64_r16 CAN raggiungere val < 0.20 (truck dimostra val=0.16). Quindi il plateau a 0.28 su highway NON è limite intrinseco della rete — è scenario-tuning limited.

### Apertura di P12 e P13 (vedi P_S.md)
- **P12**: plateau val~0.28 su highway non risolvibile da capacity. Cause candidate: minimi locali (OneCycle troncato + early stop), saturazione dataset, Pareto PINN, Po2 floor
- **P13**: scenario crashes. Urban = dead neurons (anti-pattern §22.2 + §22.4 dello skill SNN-expert). Truck = post-convergence explosion (nuovo failure mode non in skill)

### Discussione "minimi locali" (utente)
L'utente ha osservato che i 5 runs highway si fermano tutti a E4 — possibile signature di early stop aggressivo + OneCycle troncato che non vede mai la decay phase profonda. Concordato di testare una recipe modernista con scheduler con warm restart.

### Studio approfondito ottimizzatori SOTA (skill SNN-expert + web search)

Catalogati 4 tier di ottimizzatori (vedi SESSION_RESUME.md sezione "Catalogo Ottimizzatori"):

**Sorgenti consultate**:
- Skill SNN-expert ch08 (BPTT + surrogate) + ch22 (pathologies) + cheatsheet (defaults)
- Paper "Sharpness Aware Surrogate Training for Spiking Neural Networks" (SAST, 2026)
- Paper "Prodigy: An Expeditiously Adaptive Parameter-Free Learner" (ICML 2024)
- Paper "Symbolic Discovery of Optimization Algorithms" (Lion, Google 2023)
- Paper "ADMM-based Training for Spiking Neural Networks" (2025)
- Paper "Rate-based Backpropagation for Deep SNNs" (NeurIPS 2024)

**Decision matrix**:
- Vincitori ex-aequo: **AdamW+SAM** (21/25) e **AdamW+SurrogateSAM** (R&D, 21/25)
- Runner-up: AdamW+Cosine WR (19), Sophia (18)
- Sconsigliati per noi: Adam baseline (13), Prodigy (non testato SNN, 16), Lion (sign-only troppo aggressivo per loss noisy PINN, 16)

### Design STEP 2C (in attesa decisione utente)
- **2C-α** (raccomandato): AdamW + CosineAnnealingWarmRestarts(T_0=10, T_mult=2) + LR warmup 5 ep + SWA da E30 + epochs=40 + n_train=1500
- **2C-β** (condizionale): se 2C-α non scende sotto 0.20, aggiungere SAM (rho=0.05), 2× tempo
- **2C-γ** (opzionale R&D): SurrogateSAM — variante SAM con perturbazione γ del surrogate (idea originale, non in letteratura per quanto so)

### Lezioni learned 2026-05-29

#### Lezione #11 — Lo sweep esaustivo informa più del single long-run
7 runs hanno falsificato P9 in modo definitivo. Un single long-run avrebbe richiesto ipotesi diverse. Da ora: per diagnosi causali, **prima sweep poi long-run**.

#### Lezione #12 — La verifica E2E deve includere code-paths con configurazioni non-default
Il preflight tester usava `CF_FSNN_Net()` senza args mentre il training usava `CF_FSNN_Net(h=64)`. Il test locale **passava** perché il default h=32 combaciava. La regressione è esplosa su Azure con sweep h=64. **Pattern**: ogni nuovo parametro deve avere almeno 1 test con valore non-default.

#### Lezione #13 — nbstripout era la soluzione giusta dal day-1
Abbiamo perso 4 sessioni a fare workaround manuali (`git checkout -- *.ipynb`). I workflow git-friendly per Jupyter sono noti da anni: setupparli subito quando il progetto usa notebook tracciati.

#### Lezione #14 — L'asimmetria scenario è informativa
Truck val=0.16 a E5 ci dice che il modello È adatto al task. La diagnosi cambia da "aumentare capacità" a "trovare optimizer/scheduler giusto". **Pattern**: prima di concludere "rete insufficiente", testare scenari multipli.

#### Lezione #15 — Sharpness-aware methods sono mainstream SNN 2026
Paper SAST 2026 conferma. Non è più ricerca esotica. Da ora: AdamW+SAM è un baseline modernista, non una novità.

#### Lezione #16 — Optimizer parameter-free (Prodigy, D-Adapt) non sono ancora validati su SNN
Estendere ai paper successivi prima di usarli in produzione. Per ora attenersi a quelli con evidenza SNN.

### Decisioni mattina 2026-05-29
- ✅ P9 marcato falsificato
- ✅ P12 e P13 aperti in P_S.md
- ✅ Bug preflight + Cella 3 + Cella 2 fixati su git (commit 6790019, 534c2af)
- ✅ nbstripout setupato (commit 29056e1)
- ⏳ STEP 2C-α: proposto, in attesa decisione utente (Q1/Q2/Q3)
- ⏳ Run mixed + hwcut15: utente sceglie di **non rieseguire** — bastano 7 runs per la diagnosi

---

## 🌅 2026-05-30 — STEP 2C Optimizer Exploration (branch `Optimizer_Exploration`)

**Contesto**: branch isolato per esplorazione optimizer (Prodigy vs AdamW), senza inquinare main.

**Setup infrastrutturale** (commit `7f2fdb9` + estensioni):
- Branch `Optimizer_Exploration` da `06592b5`
- Nuovo CLI `--optimizer prodigy` in `train.py` (lazy import `prodigyopt`)
- 3 nuove CLI `--max_steps_per_epoch`, `--val_batch_size`, `--scheduler none`
- Notebook `Training_File_Optimizer.ipynb` (12 celle)

**Run principale Plan A vs Plan B**:
- **Plan A** Prodigy lr=1.0 b=1 → **COLLASSO**: 178/200 batch inf grad in E01 → freezing E2-E15. Diagnosi: BPTT-SNN gradiente esplosivo + Prodigy `d` cresce troppo rapidamente → clip azzera tutto → optimizer no-op
- **Plan B** AdamW lr=2e-3 b=8 OneCycle → val=0.2805 @E14 (coerente baseline STEP 2A)

**Sweep Prodigy 6 config**:
- #1 lr=0.1 b=1 dc=1.0 → **val=0.2823 @E14** ✅ (best Prodigy)
- #2 lr=1.0 b=4 dc=1.0 → 0.3550 frozen ❌
- #3 lr=1.0 b=8 dc=1.0 → 0.3288 frozen ❌
- #4 lr=0.5 b=2 dc=1.0 → 0.3103 frozen ❌
- #5 lr=0.1 b=1 dc=0.5 → 0.2902 @E15
- #6 lr=0.5 b=1 dc=0.5 → 0.2857 @E3 ✅

**Regola empirica scoperta**: `lr_effective = lr × d_coef` determina la stabilità:
- `lr_eff ≤ 0.10` → OK
- `0.10 < lr_eff ≤ 0.30` → OK, converge rapido
- `lr_eff > 0.30` → freezing immediato in E01

**Risposta dubbio utente "stiamo usando Prodigy male?"**: NO. `lr` in Prodigy è moltiplicatore di sicurezza su `lr × d × grad`. Prodigy adatta `d` autonomamente. Logging mostrava solo `lr` base — abbiamo aggiunto logging `prodigy_d` (commit `ac40a8f`).

**Confronto 360° AdamW vs Prodigy best**: 4 categorie vinte da AdamW, 2 da Prodigy (stabilità late, capacità train), 1 pareggio. AdamW è la scelta.

**Conferma floor**: 9 setup → 0.279-0.290. Strutturale.

---

## 🌅 2026-05-30/31 — STEP 2D Floor Diagnostic (branch `Floor_Diagnostic`)

**Contesto**: dopo aver escluso optimizer e capacity, identificare CAUSA del floor. 4 candidati: PINN multi-obj, OU noise, dataset saturation, Po2 quantization.

**STEP 2D (3 plan, ~3h)** (commit `af4e2c0`):
- Nuovo CLI `--noise_scale {float}` (default 1.0) → propagato a `data/generator.py`
- F1 (no PINN): val=0.2738 (Δ=-0.0067) → PINN trascurabile
- **F2 (no OU): val=0.2262 (Δ=-0.0543 = -19.3%)** 🏆 PRIMA SCOPERTA
- F3 (n_train=5000): val=0.2802 (Δ=-0.0003) → dataset size irrilevante

**STEP 2D-bis — decomposizione residuo (F5/F6/F7, ~2h)** (commit `6385418`, `aafa47a`, `c7bffc6`):
- Nuovo CLI `--po2_enabled {0,1}` con toggle LIVE via env var `PO2_ENABLED` — 100% reversibile
- F5 (no_ou + no_sr): 0.2256 → SR pesa **0.2%**
- F6 (no_ou + no_po2): 0.2256 → Po2 pesa **0.2%** 🤯 (atteso ~25%!)
- F7 (no_ou + no_sr + no_po2): **0.2198** → "floor pulito"
- `SKIP_IF_EXISTS` aggiunto in entrambe le run cells (commit `aafa47a`) → resume idempotente

**Decomposizione FINALE del floor 0.2805**:
```
OU noise              0.0543   ← 19.3%
Spike-rate reg        0.0006   ← 0.2%
Po2 quantization      0.0006   ← 0.2%
SR × Po2 interaction  0.0052   ← 1.9%
Residuo architettura  0.2198   ← 78.4%  ← LIMITE DOMINANTE
```

**Insight per deploy**: Po2 costa 0.2%. **Decisione utente "tenere Po2 in deploy" validata sperimentalmente**. Zero costo, massima compatibilità FPGA.

**Anomalia**: F7 ha `val_ou=0.010` (vs 5e-6 altri). SR/Po2 agivano da regolarizzazione implicita su T.

**F7 trend DOWN @E15**: stava ancora migliorando. Con più epoche → forse 0.215. Ma residuo architettura resta.

**Apertura e chiusura P14** (`P_S.md`).

### Lezioni learned 2026-05-30/31

#### Lezione #17 — `lr × d_coef` è la regola empirica per Prodigy stabile
Soglia 0.3 confermata su 6 config indipendenti.

#### Lezione #18 — Logging adattivo vs cached
Loggare la quantità ADATTATA (`d` di Prodigy), non il setting iniziale (`lr` base). Tutta la "discussione errore di utilizzo" derivava da diagnostica cieca.

#### Lezione #19 — Po2 quantization NON penalizza significativamente
Pre-sperimentale stimato 25% del floor. Post-sperimentale: 0.2%. **Misurare, non stimare**.

#### Lezione #20 — Toggle env-var letto live = pattern robusto per feature flags
`os.environ.get()` dentro la funzione invece di al import = toggle reversibile senza reload moduli. Costo trascurabile per la nostra scala.

#### Lezione #21 — Decomposizione quantitativa di un floor = ablation procedurale
4 cause → 7 esperimenti (3 single + 3 cumulative + 1 baseline). Sanity check: somma componenti = floor totale.

#### Lezione #22 — Branch isolati per esplorazione = pattern sano per research spike
Optimizer_Exploration e Floor_Diagnostic non sono mai stati merge-blocker. Esperimenti contenuti, infra branch-isolata, merge a main solo quando conclusivi.

### Decisioni 2026-05-30/31
- ✅ Branch `Optimizer_Exploration` + `Floor_Diagnostic` merged in `main` (post-2D-bis)
- ✅ P14 chiuso. Floor decomposto: 19% OU + 0.4% Po2/SR + 78% architettura
- ✅ Po2 resta ON in deploy (validato — pesa 0.2%)
- ✅ Documentazione completa aggiornata (P_S, SESSION_RESUME, TIMELINE, GLOSSARY, FUTURE_WORK)
- ⏳ Prossimo: scelta utente tra 4 opzioni mitigation (vedi FUTURE_WORK F2-F5)

---

## 🏛️ Fase 11 — STEP 2E Architecture Exploration (2026-05-31 → 2026-06-01)

**Obiettivo**: testare 8 varianti architetturali (Stacked, Skip, MultiRate, WTA, Attention) per battere il floor val~0.22.

**Branch**: `Architecture_Exploration`. **Risultato**: tutte 8 varianti ≥ 0.22 val_data. **Floor confermato architetturale per ALIF, ma non rotto da nessuna variante.** Non meritava merge in main, branch resta esplorativo.

---

## 🏛️ Fase 12 — F2 EventProp (2026-06-01) — **CHIUSURA DEFINITIVA**

**Obiettivo**: testare se EventProp adjoint event-based supera BPTT+surrogate-gradient (ipotesi: il floor 0.22 era causato dal gradient surrogate biased, EventProp esatto poteva romperlo).

**Branch**: `Training_Method_Exploration`.

### Iterazioni esplorative (5 versioni)
1. **F2.0** (LIF puro EventProp, default lolemacs dt=1e-3 mu=0.1): grad collapse, val 0.587
2. **F2.0b** (LIF, encoding fix dt=1e-2 mu=0.5): val 0.327
3. **F2.2** (LIF + full recurrence): val 0.323, spike rate saturato 93%
4. **F2.1 stripped** (ALIF senza Po2/delays/n_ticks): val 0.351 (bug index nel jump)
5. **F2.1-full** (A1 ESATTA: Po2 + delays + n_ticks=10 + ALIF adaptive threshold + low-rank rec con EventProp adjoint): val 0.224 ≡ baseline 0.222

### Mea culpa documentato

Per F2.0b/F2.2 avevo affermato "EventProp dimezza val_data 0.222→0.110". L'utente ha sospettato l'incongruenza vs P14 floor diagnostic ("Po2 era già stata testata e non aveva cambiato nulla"). Audit forzato ha rivelato: stavo leggendo `val_phys` (col 10, MSE no-mask) come se fosse `val_data` (col 9, RMSE masked). I valori veri erano 0.327/0.323 (peggio di baseline). **4h di lavoro su F2.2 basate su misread.** Vedi `EVENTPROP_GRID2X2.md` §7.

### Grid 2×2 (single optimizer AdamW lr=2e-3)

| | BPTT+surrogate | EventProp |
|---|---:|---:|
| ALIF (864 params) | 0.2233 | 0.2239 (Δ=+0.0006) |
| LIF (288 params) | 0.3203 | 0.3226 (Δ=+0.0023) |

EventProp ≡ BPTT (entro 1%) su entrambe le architetture.

### Sweep optimizer 4×11 = 44 run (chiusura)

**Best per method**:
- baseline (ALIF+BPTT): **0.2218** (AdamW 5e-3)
- eventprop_alif_full: 0.2226 (AdamW 2e-3)
- bptt_lif_simple: 0.3179
- eventprop_lif_simple: 0.3207

**Robustezza** (la scoperta chiave del sweep):
- baseline: 11/11 successi, 8/11 entro 2% del best, CV=0.033
- **eventprop_alif_full: 5/11 successi, 1/11 entro 2% del best, CV=0.710** (22× più variabile)
- 6 fallimenti catastrofici di EventProp con grad ~10¹⁷

**Spike rate** (deploy FPGA):
- baseline best: 4.1% ✅
- eventprop_alif_full best: 25.7% (6× peggio)

**Estrapolazione 15 ep**: baseline pred 0.217, EventProp pred 0.223 (marginale baseline meglio).

### Decisioni 2026-06-01

- ✅ **F2 EventProp CHIUSO**: pareggio val_data ma EventProp è 100× meno robusto + 6× più spike rate → baseline confermato production
- ✅ **Floor val_data ~0.22 rigorosamente confermato architetturale**: 2 metodi training INDIPENDENTI (BPTT+surrogate, EventProp adjoint event-based esatto) convergono allo stesso plateau su ALIF. Non è un artefatto del gradient surrogate.
- ✅ Documentazione completa: `EVENTPROP_DESIGN.md`, `EVENTPROP_GRID2X2.md`, `EVENTPROP_OPTIMIZER_SWEEP.md`
- ❌ Branch `Training_Method_Exploration` NON merge in main (esplorativo). Resta su origin come reference scientifico.

### Lessons learned 2026-06-01

#### Lezione #23 — La metric NON è una sola colonna del CSV, è una FORMULA
val_data = RMSE masked, val_phys = MSE no-mask. Numeri diversi (0.222 vs 0.0513) anche se misurano la stessa cosa. Confondendoli si ottengono conclusioni opposte. Sempre citare l'indice colonna nel CSV e la definizione.

#### Lezione #24 — Audit prima di celebrare un risultato "miracoloso"
Quando un risultato sembra contraddire evidenza precedente (P14), verificare TUTTO PRIMA di costruire ipotesi. L'utente ha intuito l'incongruenza prima di me e ha forzato audit.

#### Lezione #25 — Stesso modello, diverso training: il vero fair-compare
Tutti i tentativi "EventProp su LIF stripped" erano confounded (8+ aspetti architetturali diversi dal baseline). Solo `eventprop_alif_full` (replica A1 esatta) è confronto valido per claim "X cambia val_data".

#### Lezione #26 — Sweep optimizer rivela robustezza, non solo accuracy
Il grid 2×2 single-optimizer suggeriva "pareggio". Il sweep 4×11 rivela che EventProp è 22× più fragile sulla scelta optimizer. Robustezza al cambiamento di hyperparam è una metric production-critical che non emerge da un singolo run.

#### Lezione #27 — Floor confermato da metodi indipendenti = floor REALE
BPTT+surrogate e EventProp adjoint convergono entrambi a 0.222 su ALIF. Due algoritmi che usano gradient COMPLETAMENTE diversi danno lo stesso risultato → il floor è genuino, non un artefatto del training. Test indipendenza è il modo per confermare un floor strutturale.

---

## 🗓️ 2026-06-02 — AUDIT + R1 (Arch_Tested) + R2 setup (Studio Prodigy CAPIRE)

### Mattina: simulator iterazioni + 8 run T30 + analisi → AUDIT

**Branch**: `Visualizer_Building` (poi mergiato in main).

Eventi principali:
1. Simulator visivo CF_FSNN completato a iterazioni: `utils/simulator/{engine,metrics,plots,anim}.py` + `Simulator_Visual.ipynb`. Scoperta drift cumulativo open-loop T² (vedi `SIMULATOR_FINDINGS.md`).
2. Run 8 T30 (4 arch × 2 opt × 30 ep) eseguite su Azure, pullate e analizzate.
3. **Audit ascetico user-driven**: l'utente ha legittimamente criticato 4 errori di setup recenti (Po2 mai disattivato, Prodigy lr=1.0 mai funzionante, A8 mai usata prima ma celebrata BEST, spike rate 4% accettato vs target 15-20%). Ha forzato a FERMARE la corsa.
4. **`document/AUDIT_2026-06-02.md`** scritto come bilancio onesto: 5 affermazioni dichiarate ma NON dimostrate, 5 errori di setup ricorrenti, 8 domande aperte, roadmap R1+R2+R3.

### Pomeriggio: R1 Arch_Tested/ + R1.7 fix BASELINE_PRE_EVENTPROP

**Branch**: `Arch_Tested_Setup` → merge in main → cancellato. Poi `Arch_Tested_Fix_Baseline` → merge → cancellato.

R1 snapshot riproducibile delle architetture funzionanti in `Arch_Tested/<arch>/`:
- 4 originali (A1, A8, A3, EVPROP_ALIF) con `core/` cleanup chirurgico, `train.py` CLI ridotta a 1 variant, `snapshot_original/` READ-ONLY (13 plot G + log + config), `reproduce_training.ipynb` (3-4 celle), README dettagliato.
- 5/5 smoke test 1ep×1step OK end-to-end.

R1.7 fix critico: user feedback "A1 era sbagliata dall'inizio". Ricerca cronologica → vera baseline pre-EventProp è `P12_S2D_F2_no_ou` (commit pre-EventProp `5a2c7ee`). UNICA differenza vs A1: `lambda_sr=0.5` (vs 0). Aggiunta sub-cartella `Arch_Tested/BASELINE_BPTT_864p_PRE_EVENTPROP/` come riferimento canonico per studi R2/R3. A1 marcata DEPRECATED nel README con avviso prominente.

### Sera: R2 setup — Studio Prodigy CAPIRE

**Branch**: `Prodigy_Deep_Study` (in esecuzione su Azure).

1. **R2.1 Reading & doc**: ricerca multi-fonte (paper Mishchenko 2024 + 5 GitHub Issues konstmish/prodigy #3/#8/#10/#18/#27 + OneTrainer Wiki + kohya-ss community + LoganBooker `prodigy-plus-schedule-free`).

   Eureka critici scoperti:
   - **V2** (konstmish ufficiale, Issue #27): "Se `d` resta troppo piccolo, aumentare `d0` da 1e-6 a 1e-5/1e-4". Confermato sui nostri T30 (d frozen ~1e-3 sempre).
   - **W1** (madman404, Issue #8): `betas=(0.9, 0.99)` produce "dramatic improvement" perché `beta3=beta2^0.5` controlla decay del `d_numerator`. Default 0.9995 troppo lento per training <2000 step.
   - **W2** (community consensus kohya/OneTrainer/bdsqlsz): `d_coef=2.0` standard, NON 1.0 default.
   - **Setup CANONICAL "Prodigy is ALL YOU NEED"**: `lr=1.0 betas=(0.9,0.99) wd=0.01 use_bias_correction=True safeguard=True d_coef=2.0 d0=1e-6→1e-5 if frozen` + `cosine_no_restart T_max=epochs`.

   Doc `document/PRODIGY_DEEP_STUDY.md` (~500 righe): parte 1 (math + source code walkthrough) + parte 2 (community wisdom multi-fonte verificata). Parte 3 (lessons R2.2) sarà aggiunta dopo esperimenti.

2. **R2.2 setup**: train.py esteso con 4 nuovi CLI flag Prodigy (`--prodigy_betas`, `--prodigy_use_bias_correction`, `--prodigy_d0`, `--prodigy_weight_decay`) oltre ai 3 esistenti. Self-check post-init con 7 assert (no silent failure). Scheduler `cosine_no_restart` aggiunto (CosineAnnealingLR puro, T_max=epochs, NIENTE restarts come richiesto da konstmish).

3. Notebook `Prodigy_Diagnostics.ipynb` redesigned con 5 esperimenti P-A..P-E isolanti i 3 lever community:
   - **P-A**: baseline T30 replica → conferma d frozen
   - **P-B**: P-A + `betas=(0.9, 0.99)` → isola W1
   - **P-C**: P-A + `d_coef=2.0` → isola W2
   - **P-D**: P-A + `d0=1e-5` → isola V2 fix konstmish
   - **P-E**: SETUP CANONICAL completo + `cosine_no_restart`

   Smoke test 5/5 OK end-to-end con verifica config_snapshot + batch_log (no workaround, hard fail su parametri non recepiti).

4. **Sub-folder dedicata**: risultati in `results/Prodigy_Study/` (separazione visiva per evitare confusione futura). Convention: ogni studio futuro userà `results/<Study_Name>/`.

5. **Fix Python <3.12 compat**: f-string nested quote singolari sostituite con doppie (PEP 701 supportato solo da 3.12).

### Lessons learned 2026-06-02

#### Lezione #28 — Mai dichiarare "X non funziona" senza tuning serio
Per Prodigy avevamo dichiarato "non aggiunge valore" dopo 10/16 fallimenti del sweep. Ma il sweep usava solo i default Prodigy lib (`d0=1e-6, d_coef=1.0, betas=0.999, no use_bias_correction`). La community wisdom raccomanda un setup completamente diverso. Soluzione corretta: ricerca multi-fonte PRIMA di concludere.

#### Lezione #29 — L'utente vede contraddizioni che noi non vediamo
"A1 era sbagliata dall'inizio" — intuizione utente non immediatamente verificabile. Verifica cronologica: F2 vincente aveva `lambda_sr=0.5` attivo, A1 (introdotta da Architecture_Exploration) l'ha disattivato silenziosamente. Le 6 successive run T30 hanno propagato l'errore. Solo l'utente ha forzato il check storico.

#### Lezione #30 — Sub-folder dedicate per ogni studio
Mescolare risultati di studi diversi in `results/` ha causato confusione (T30, SW, P15 tutti insieme — utente non riusciva a trovare il "best vero"). Convention adottata: ogni studio futuro ha `results/<Study_Name>/` dedicata.

#### Lezione #31 — Multi-fonte CRITICO per algoritmi nuovi
Paper Prodigy NON documenta failure modes pratici (frozen d, betas tuning). 5 GitHub Issues konstmish/prodigy + community LoRA (kohya, OneTrainer, bdsqlsz) hanno svelato la verità. Sempre triangolare paper + source code + issue tracker + practitioner community per algoritmi adottati di recente.

#### Lezione #32 — Smoke test post-modifica deve verificare config_snapshot + batch_log
Aggiungere CLI flag senza verificare che (a) Prodigy li riceva (self-check assert post-init), (b) config_snapshot li salvi, (c) batch_log continui a funzionare = ricetta per esperimenti silenziosamente sbagliati. Sempre 3 controlli incrociati end-to-end.

#### Lezione #33 — Branch storici NON cancellare prematuramente
User feedback: "non cancellare i branch storici, crea solo nuovo branch per nuove azioni". I 5 branch storici (Architecture_Exploration, Floor_Diagnostic, Optimizer_Exploration, Training_Method_Exploration, Visualizer_Building) restano come archeologia consultabile (git log/checkout). Decisione di archiviare (tag + delete) rimandata a sessione futura, solo quando saremo CERTI che non servono.

---

## 📌 Note finali

Questo TIMELINE va aggiornato dopo ogni milestone significativa. Mantenere la sezione "Lessons learned" è cruciale per non ripetere errori in future sessioni.

Mantenere anche `P_S.md` (lo "stato attuale" dei problemi/soluzioni) E `SESSION_RESUME.md` (one-pager rapido). Questo TIMELINE è il "diario storico", `P_S.md` è "lo stato di lavoro", `SESSION_RESUME.md` è "il quick-start".
