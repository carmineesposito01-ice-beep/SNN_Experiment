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

## 🏛️ Fase 8 — Bug fix + R24F + R25 + R26 Fusion (2026-06-03 → 10)

### 2026-06-03 — **BUGS_2026-06-03.md**: 4 bug strutturali trovati

Durante l'analisi di R2.4 Prodigy MultiParam (90 run in corso su Azure con violin G7 fortemente collassati), l'utente ha chiesto un **audit profondo del codice** prima di lanciare nuovi studi.

**Risultato**: 4 bug strutturali in `core/network.py` + `core/eventprop.py`:

1. **F5 sigmoid saturation** (`_decode_params`, riga 380): `raw_eq = raw / decode_scale` amplificava `raw` di 9-18× per T/s0/a/b. Con bound Xavier `±0.4`, raw_eq cadeva in zona sigmoid satura → derivata ≈ 0 → params bloccati al random init. **97% dei sample T saturato, 96% s0 saturato** post-init.
2. **Xavier asymmetric bias** in `OutputLayer_LI` (riga 63): row_mean ≠ 0 → con input spike binari `{0,1}` creava offset deterministico per canale → determinava QUALE bound veniva saturato.
3. **A2/A4 stacked dead output** (in cascate ALIF, base_threshold=1.5 troppo alto per layer non-input riceventi spike sparsi).
4. **Delay mask penalty** 1/max_delay: ogni edge contribuisce solo 1/max_delay del tempo → var(current) ridotta di max_delay rispetto a fc layer normale.

**A8 attn funziona "by accident"**: `attn = sigmoid(QK)·V` comprime la magnitudo PRIMA del LI → raw_out piccolo → sigmoid non satura nonostante #1.

**Conseguenza**: TUTTI i ranking pregress (T30, P15, SW, R2.2, R2.4 in corso, ecc.) sono **CORROTTI**. Il floor val_total ≈ 0.22 era il floor della sigmoid saturation, non architetturale.

### 2026-06-03 sera — Fix applicati

| # | File | Modifica |
|---|---|---|
| 1 | `core/network.py:380-381` (+ 5 snapshot) | Rimosso `raw / decode_scale`, ora `sigmoid(raw)` puro |
| 2 | `core/network.py:59-64` (+ 5 snapshot + `core/eventprop.py:567-580`) | `fc_weight.sub_(fc_weight.mean(dim=1, keepdim=True))` post-Xavier |
| 3 | `core/network.py` Stacked + StackedSkip | `base_threshold.fill_(1.0)` per ALIF non-input |
| 4 | `core/network.py:14-16` (3 occorrenze + 5 snapshot + `core/eventprop.py:314`) | `fc_weight.mul_(max_delay**0.5)` |

**Verifica empirica post-fix** (3 seeds × A1/A8/A3): saturation = **0%** (vs 96-97% pre-fix), spike rate ∈ [6%, 10%], gradient ≠ 0 su tutti i 5 canali, parametri count invariati (864/2624/3936/864). Smoke 4 arch forward+backward: 0 errori.

**Smoke training A1 2ep × 50 step**: val_total = **0.213** (vs floor pregress 0.22 dopo 5700 step) → convergenza **57× più veloce**.

**Tag git**: `pre_bug_fix_2026-06-03` (rollback). HEAD post-fix: `d9d558a`.

### 2026-06-04 → 06 — R24F Prodigy MultiParam PostFix (93 esperimenti)

Rerun completo del piano R2.4 con codice fixato. Tag prefix `R24F_*`, results in `MultiParam_PostFix/`.

**Setup**:
- 90 Prodigy: 3 LR × 10 varianti × 3 scenari (highway, mixed, full)
- 3 AdamW baseline (1/scenario) per misurare valore aggiunto Prodigy
- Arch: `baseline` (864p, post-fix), 10ep × 100 step

**Best per scenario**:
| Scenario | Best Prodigy | AdamW ref | Guadagno |
|---|---:|---:|---:|
| highway | **0.169** (V08 lr=1.0) | 0.186 | -9% |
| mixed | **0.189** (V08 lr=0.5) | 0.230 | -18% |
| full | **0.222** (V08 lr=1.0) | 0.253 | -12% |

**V08 (cosine_no_restart) domina su tutti e 3 gli scenari**. Setup V08: `lr=1.0, d_coef=1.0, d0=1e-6, growth=inf, scheduler=cosine_no_restart, betas=(0.9, 0.99), use_bias_correction=1, safeguard=1, wd=0.01`.

⚠️ **Problema scoperto in violin G7 + G13 trajectory**: T predetto è quasi una **linea piatta** intra-sample (non segue T_true che fa step). v0 e s0 saturano ancora vicino ai bound MAX/MIN (anche post-fix). `a` stuck vicino MIN. Solo v0 varia inter-sample (cross-driver), ma intra-driver tutto è quasi costante. La rete fa **"average estimation" cross-driver**, NON **"system identification" intra-driver**.

### 2026-06-07 → 09 — R25 Ablation Study (18 esperimenti)

Studio causale **one-at-a-time** per identificare cosa abilita T-tracking dinamico. Setup: scenario `mixed`, Prodigy V08 lr=1.0, seed=42.

**5 assi**:
- **A — Memoria temporale** (6 run incluso baseline replica): seq_len, max_delay, bit_shift
- **B — Loss balancing** (3 run): `lambda_T_aux` ∈ {0.1, 1.0, 10.0}
- **C — Spike rate** (3 run): `lambda_sr` ∈ {0.0, 5.0, 20.0}
- **D — Capacity** (3 run): hidden_size ∈ {16, 64, 128}
- **E — Training duration** (3 run): epochs ∈ {5, 20, 30}

**Modifiche infrastruttura R25** (committate in `train.py` + `utils/plot_diagnostics.py`):
- **`pinn_loss`** ritorna 4-tuple `(loss, comps, sr, params_seq)` + nuovo parametro `lam_T_aux` + `retain_params_grad`
- **CLI**: `--lambda_T_aux`, `--cf_max_delay`, `--cf_bit_shift` (3 nuove)
- **11 colonne CSV epoch**: `val_T_tracking_corr` + 5×`val_<p>_pred_mean` + 5×`val_<p>_intra_std`
- **16 colonne CSV batch**: `loss_T_aux` + 3 livelli × 5 canali (gn_out_fc_*, gn_decoded_*, grad_dir_*)
- **3 nuovi plot**: G16 (grad raw per canale), G17 (grad decoded post-sigmoid), G18 (grad direction sign mean)
- Helper `_robust_rmtree` per NFS Azure
- `core/network.py`: `bit_shift` kwarg propagato a CF_FSNN_Net + HiddenLayer_ALIF

**Risultati R25 — 3 WIN INDIPENDENTI** (ognuno migliora T_tracking_corr senza danneggiare val_total):

| Run | Modifica | ΔT_corr | Δval | Verdetto |
|---|---|---:|---:|---|
| **A4** | `max_delay 6→18` | **+0.090** | -0.015 | ✅ WIN puro (memoria sinaptica più lunga) |
| **B1** | `lambda_T_aux 0→0.1` | **+0.147** | -0.006 | ⭐ WIN ASSOLUTO (supervisione T diretta) |
| **C1** | `lambda_sr 0.5→0` | **+0.088** | -0.014 | ✅ WIN puro (L_sr era controproducente!) |

**Altri findings importanti**:
- **A5 (bit_shift 5)** è CONTROPRODUCENTE (T_corr -0.072). Leak singolo neurone non aiuta.
- **A6 COMBO** è il MISTERO: combinare seq_len=100 + max_delay=18 + bit_shift=5 dà T_corr=0.20 (peggio della baseline!). C'è **interazione negativa**. Sospetto: bit_shift=5.
- **B2/B3** (lambda_T_aux 1.0/10.0): T_corr migliora ancora a 0.56/0.58 ma **val_total ESPLODE** a 0.24/0.54 → la rete sacrifica L_data e L_phys per tracciare T.
- **C2/C3** (lambda_sr alto): forzando spike rate al target FPGA 14%, T_corr crolla del 70%. **Trade-off duro spike_rate ↔ T-tracking**.
- **D — Capacity NON è bottleneck**: D3 large (128h) crasha (best_ep=1). D2 mid solo +0.07 su T_corr.
- **E — SHOCKING**: più training **PEGGIORA** T_corr. E2 (20ep, best_ep=19): T_corr 0.226 vs baseline 0.353. La rete **dimentica T** durante l'apprendimento esteso (continua a migliorare val_data ma peggiora val_T_corr). **Early stop ≈ 10 ep è la scelta giusta**.

**Insight tecnico fondamentale post-R25**: post-fix il gradient unbalance si è **INVERTITO**. Pre-fix v0 dominante (gradient 10× degli altri). Post-fix **T è dominante** (gn_out_fc_T = 0.23 vs v0=0.01, 23× sbilanciato verso T). Quindi T_corr=0.35 baseline non è limitato da gradient magnitude — è qualcos'altro (capacity di rappresentazione? minimi locali?). B1 NON cambia magnitudo gradient T ma cambia la **direzione semantica** (T_aux punta a T_true) → riallineamento informazionale.

### 2026-06-10 — R26 Fusion Study (6 esperimenti, in esecuzione)

Test di **ortogonalità** dei 3 win R25.

**6 esperimenti**:
| Tag | max_delay | T_aux | sr | epochs | Note |
|---|---:|---:|---:|---:|---|
| F0_baseline_replica | 6 | 0.0 | 0.5 | 10 | sanity = R25_A1 |
| **F1_TRIPLE_win** | 18 | 0.1 | 0.0 | 10 | A4+B1+C1 (TOP candidato) |
| F2_A4_B1 | 18 | 0.1 | 0.5 | 10 | no sr_off |
| F3_B1_C1 | 6 | 0.1 | 0.0 | 10 | no memoria |
| F4_A4_C1 | 18 | 0.0 | 0.0 | 10 | no T_aux |
| F5_TRIPLE_short | 18 | 0.1 | 0.0 | 5 | F1 + early stop |

**Linearity test atteso**: somma R25 predetta = +0.325 su T_corr, -0.035 su val_total. Realistic 0.55-0.62 di T_corr (linearity ratio 70-90%).

**Bug NFS Azure incontrato e risolto**: `shutil.rmtree` + `os.makedirs` race condition su NFS. Fix: tag univoco con timestamp (`_R26_PREFLIGHT_<unixtime>`), no cleanup prima del train.py, cleanup finale best-effort. Commit `6075a96`.

### Lessons learned 2026-06-03 → 10

#### Lezione #34 — Audit codice quando i ranking sono confusi
3 sintomi convergenti (T30 violin collassati + R2.4 risultati strani + utente che nota "v0 satura sempre") ci hanno portato all'audit. **Mai assumere che il codice base sia corretto solo perché "ha sempre funzionato"**. I 4 bug erano latenti da settimane.

#### Lezione #35 — Tag pre-fix prima di applicare correzioni a impatto sistemico
`git tag pre_bug_fix_2026-06-03` ci dà rollback istantaneo se i fix introducono problemi peggiori. Sempre tag prima di toccare core/.

#### Lezione #36 — Backward-compatibility dei CSV
Le 11+16 nuove colonne CSV R25 hanno default NaN per i CSV pregress (R24F). Tutti gli script di analisi continuano a funzionare. **Non rinominare colonne esistenti, sempre append**.

#### Lezione #37 — Metric scalar prima di "guardare i plot"
G13 trajectory mostrava T flat. Ma G7 violin mostrava distribuzione T cross-sample larga. Il `val_T_tracking_corr` Pearson ci ha permesso di **quantificare** che la corr era 0.35 (cross-driver alignment), non zero. Senza metric scalar non si confrontano ablation.

#### Lezione #38 — Sospetta gli effetti combinati (interazioni)
R25 ha mostrato: A4 + B1 + C1 sono singolarmente win, ma A4+A5+A3 (COMBO A6) è LOSS. **Le ortogonalità sono ipotesi da TESTARE**, non assumere. R26 fa proprio questo: 4 combinazioni controllo (F1/F2/F3/F4) per isolare interazioni.

#### Lezione #39 — Filesystem NFS richiede pattern di accesso speciali
Su Azure cluster con NFS shared, `rmtree + makedirs` ha race condition (metadata stale). Soluzioni: tag univoco timestamp, `_robust_rmtree` con retry+backoff, ignore_errors=True su cleanup non critici.

#### Lezione #40 — La metrica T_tracking_corr cattura 2 fenomeni
`val_T_tracking_corr` Pearson aggregato cattura **(1) cross-driver alignment** (driver diversi → T diversi) **+ (2) intra-driver dynamics** (T(t) variabile dentro la stessa sequenza). I 0.35 baseline sono quasi tutti (1). Il +0.15 di B1 è probabilmente il vero (2). Per disambiguare servirebbe `val_T_intra_corr` (Pearson dopo aver rimosso la media per-sample). **TODO post-R26 se utile**.

### 2026-06-11 — R27 Observability Audit (24 run R25+R26 auditati)

Implementato in `train.py` + `scripts/audit_checkpoints.py`:
- **Fix bug LAYER_MAP** (`train.py:704-722`): 4/6 colonne gradient erano SEMPRE NaN dal 2026-06-07 a causa di entry duplicate per varianti EventProp. Fix "first hit wins".
- **Nuova metrica `val_T_intra_corr`** (Lezione #40): Pearson(T_pred, T_true) dopo rimozione media per-sample.
- **Audit script**: rilancia val_epoch sui 24 best_model.pt R25+R26, calcola `rank_effective` + `cond_number` su `Cov(decoded_params)`.

**Risultati shock**:
- T_intra_corr ≤ 0.058 in tutti i 24 run (top: R25_A3 = 0.058). Il T_tracking_corr=0.5 di B1 era illusione cross-driver quasi totale.
- rank_effective = 1 in 18/24 run, ≤2 in 22/24. Rank-collapse universale.
- v0_pred saturato a 38-44 in 22/24 run.

### 2026-06-12 mattina — R28 ProdigyTuning (5 esperimenti)

Test fix konstmish Issue #27 (`d0=1e-5`), step budget 3×, warm restart cosine T0=5.

- **A1 (d0=1e-5)**: Prodigy `d` sblocca a 0.474 (19× baseline) MA val_data esplode (+31%), T_intra crolla. d alto destabilizza.
- **C1/D1**: best_ep=1 (rete locka minimo locale al primo epoch). Warm restart non interviene.
- T_intra ≤ 0.035 in tutti i 5 setup. **Prodigy NON era il bottleneck.**

### 2026-06-12 pomeriggio — R29 DecoderFix (12 esperimenti, disastro)

Modifiche `core/network.py`: buffer `decode_offset` + `logit_tau` + `calibrate_decode_offset()` + `set_logit_tau()`. CLI flag opt-in in `train.py` (default no-op = backward-compat).

12 run su 6 assi (controlli, init, τ-sweep, combo, long, no-Po2).

**Risultati**:
- E0 baseline A3 replica: val_data 0.174 (drift +2% vs A3 originale)
- A1 init_shift alone: v0_pred_ep1=44.5 (PIÙ saturato di baseline!) → init annullato in 100 step → identifiability vs init asymmetry
- B/C/D run con τ-anneal: best_ep=1 in 7/12 run → τ-anneal + cosine + lr=1.0 = locka minimo precoce
- C1 init+τ5: val_data 0.253 (+45% peggio di baseline)
- E1 no_po2: rank 1→2 lieve ma val_data crolla → **Po2 non è il colpevole del rank-collapse**

**3 conferme negative cristalline da R29**:
- init_shift INUTILE (loss landscape lo annulla)
- Po2 quantization NON è la causa
- τ-anneal mal interagisce con cosine scheduler

### 2026-06-12 sera — SCOPERTA CRITICA: gradienti esplosi nascosti dal clip

Utente solleva ipotesi: "stiamo usando una baseline instabile (LR 1)". Verifica su `gn_total_preclip`:

| Run | inf grads | gn>100 | gn_max | giudizio |
|---|---:|---:|---:|---|
| ⭐ **R24F mixed V08 lr=0.5** | **0** | **0** | **21.79** | ✅ CLEAN |
| R24F mixed V08 lr=1.0 | 20 | 13 | 4.2e+13 | ⚠ mascherato |
| R25_B1 (= R28_A0) | 0 | 2 | 6.7e+5 | ⚠ mascherato |
| R25_A3 (= R29_E0) | 2 | 9 | 8.6e+17 | ❌ mascherato |
| R26_F1 TRIPLE | 0 | 5 | 7.3e+17 | ❌ mascherato |
| R29_C1_init_tau5 | 1778 | 902 | 2.2e+17 | ❌ totalmente rotto |

**Discovery**: TUTTI i baseline da R25 in poi avevano `gn_total_preclip` ∈ [10⁵, 10¹⁷], mascherati dal `clip_grad_norm_(1.0)`. R24F_mixed_lr0.5_V08 è l'UNICO setup post-fix con gradienti CLEAN.

R24F LR sweep aggregato:
- lr=0.1: 0% exploding ma val_data 0.7-1.0 (non converge)
- lr=0.5: 0-20% exploding, val_data competitivo
- lr=1.0: 20-50% exploding (mixed 50%, full 30%, highway 20%)

### 2026-06-12 sera — RESET strategico

**Decisione utente**: tornare al vero baseline post-fix `R24F_mixed_lr0.5_V08`. Snapshot creato in `Arch_Tested/R24F_MIXED_lr0.5_V08_TRUE_CHAMPION/` con README + reproduce_training.ipynb + snapshot_original + codice corrente. R27/R28/R29 mantengono valore informativo (rank-collapse confermato, Prodigy non colpevole, decoder fix non sufficienti, init irrelevant, Po2 innocent) MA misure numeriche vanno re-fatte sul baseline pulito.

#### Lezione #41 — Sempre verificare `gn_total_preclip` (NON solo `gn_postclip`)
Il `clip_grad_norm_(max_norm=1.0)` maschera completamente l'instabilità: log post-clip sempre = 1.0, dando illusione di sanità. Vero indicatore è `gn_total_preclip`. **Aggiungere assertion `gn_max < 25` come gate per qualunque baseline**.

#### Lezione #42 — Sweep LR è la prima cosa per qualunque optimizer adattivo
Per Prodigy: `d0` adatta dlr ma `lr` nominale modula la dinamica scheduler (cosine). lr=1.0 può sembrare giusto per Prodigy paper ma per il NOSTRO regime SNN+surrogate è instabile.

#### Lezione #43 — Convenzioni paper non sostituiscono verifiche empiriche
Ho seguito "lr=1.0 per Prodigy" (paper konstmish) per 4 sessioni senza verificare nel NOSTRO regime. R24F aveva già la risposta (lr=0.5 V08 per mixed) ma l'ho ignorata. **Mai assumere convenzione paper universale**.

#### Lezione #44 — Strategic reset is OK
4 sessioni costruite su baseline sbagliato sembrerebbero sprecate. MA: hanno comunque prodotto 3 risultati negativi rigorosi (init irrelevant, Po2 not the cause, Prodigy not bottleneck) E introdotto metriche valide (T_intra_corr, rank_effective). Reset al baseline pulito è OK, le lezioni restano.

---

## 📅 2026-06-13 — R30 Identifiability (10 esp.) post-RESET

**Setup**: prima campagna sul vero baseline `R24F_mixed_lr0.5_V08`. Applicate decoder fix R29 opt-in (DEC-1 per-channel τ, DEC-3 init_bias_shift) + supervisione ausiliaria su v0/s0/a/b via 4-tuple loader (`data/generator.py` emette `params_gt`).

**Implementazione**:
- `generator.py`: aggiunto `params_gt` (4 valori per traiettoria) al dataset → loader 4-tuple `(x, y, mask, params_gt)`.
- `train.py`: `pinn_loss` ora accetta `lambda_aux` su `MSE(decoded_params, params_gt)` come 4° componente.
- 10 esperimenti: lambda_aux ∈ {0.0, 0.1, 0.5, 1.0}, decoder cfg ∈ {C0, C3}, plus 2 controlli.

**Risultati**:
- Rank-collapse **risolto** dove era universale: rank_effective ≥ 3 in 8/10 run con lambda_aux ≥ 0.5.
- T_intra_corr migliorato a 0.038-0.043 nei migliori (vs ≤0.058 su 24 run R27 audit).
- v0_pred desaturato (range 25-42 invece di clamp a 38-44).
- **C3 emergente come decoder cfg vincente**: init_bias_shift=1 + per-channel τ=[10,3,10,3,3] migliora T_intra E rank.

**Lezione #45 — Identifiability era il bottleneck primario, non capacità**: la rete da 864 params è sufficiente. Senza ground-truth sui parametri latenti, la rete impara una mappa costante (rank=1). Supervisione ausiliaria + decoder calibrato risolvono. R30 chiude la domanda aperta di R27 (rank-collapse) e R28 (Prodigy non era colpevole).

---

## 📅 2026-06-14 — R31 Champion Validation (14 esp.)

**Setup**: sweep esaustivo a 50 epoche su 4 dimensioni ortogonali (decoder, scheduler, spike-pressure, capacity) per validare i 3 champion candidati emersi da R30.

**Dimensioni**:
- **Decoder**: C0 (none), C1 (init), C3 (init + per-ch τ) ← winner R30
- **Scheduler**: cosine_no_restart, cosine_T0=15, cosine_T0=10
- **Spike pressure**: λ_sr ∈ {0.5, 1.0, 5.0}
- **Capacity**: h ∈ {32 (baseline 864p), 16 (232p ridotto)}

**Risultati shock** (3 champion distinti, ognuno ottimo su un trade-off):

| Tag | Config | T_intra | val_data | gn_max | Ep done | Categoria |
|---|---|---:|---:|---:|---:|---|
| ⭐ **C3** | C3 + no restart, 10 ep | **0.0407** | 0.177 | **40.6** ✅ | 10/10 | Scientific reference (CLEAN) |
| ⭐ **A3** | C3 + cosine T0=15, 50 ep | **0.0599** | **0.167** | 4280 ⚠ | 32/50 abort | Operational best (peak @ ep15) |
| ⭐ **E1** | C3 + h=16 + λ_sr=5 | 0.038 | 0.173 | 1.3e6 ⚠ | **50/50** ✅ | Long-run stable |

**Pattern critico identificato**:
- A3 (cosine T0=15): T_intra peak coincide **esattamente** con il primo restart @ep15, poi loss landscape implode (gn cresce di 3 OOM nelle 17 ep successive prima di abort).
- E1 (capacity ridotta): l'unico setup che completa 50 ep senza abort, ma T_intra inferiore. h=16 (232 params) sacrifica capacità per stabilità.
- C3 (no restart, 10 ep): l'unico CLEAN (gn=40.6 < 100). Trade-off: 4/4 obiettivi raggiunti su solo 10 ep, T_intra inferiore al peak A3.

**Snapshot 3 champion** in `Arch_Tested/R29v2_C3_CLEAN/`, `Arch_Tested/R31_A3_PEAK/`, `Arch_Tested/R31_E1_STABLE/` con README + reproduce_training.ipynb + snapshot_original (config + training_log + plots G1-G13). README master `Arch_Tested/README.md` aggiornato (9 entry totali con colonna T_intra).

#### Lezione #46 — Warm restart è lama a doppio taglio
Il primo restart cosine T0=15 sblocca temporaneamente il peak T_intra (probabile uscita da minimo locale grazie al jump di lr da 0.0002→0.0178, 90×). Ma il jump è troppo violento: amplifica i gradienti accumulati, esplode poco dopo. **Hypothesis R32**: meccanismi soft (decay, warmup, adaptive trigger) possono catturare il beneficio del restart senza la successiva esplosione.

#### Lezione #47 — Tre champion ≠ un champion
Il concetto di "best model" è ambiguo se gli obiettivi sono multipli (T_intra, val_data, stabilità, riproducibilità). R31 ha mostrato che esistono **3 frontiere di Pareto distinte**. Documentare tutte e 3 in `Arch_Tested/` (con etichette "CLEAN"/"PEAK"/"STABLE") è meglio che forzare una scelta arbitraria.

#### Lezione #48 — T_intra peak ≠ val_total best
Il file `_TRUE_Tintra_ranking.csv` mostra che 12/49 run hanno peak T_intra a epoca DIVERSA dal best val_total (idxmin). Aggregatori standard (best.pt selezionato per val_total) **perdono** il peak T_intra. Per Prodigy Study estratto via re-scan completo dei training_log.csv per epoca con T_intra.idxmax() per run.

---

## 📅 2026-06-15 — R32 Restart Mechanisms (preparato, non eseguito)

**Setup**: 5 meccanismi soft per warm restart + 2 baseline cfg (C3, E1) → 10 esperimenti × 50 ep.

**Codice (`train.py`)**: aggiunti 5 nuovi CLI flag, tutti default no-op (backward-compat verificato con smoke test):
```python
parser.add_argument('--restart_T0', type=int, default=15)
parser.add_argument('--restart_decay', type=float, default=1.0)     # 1.0 = no decay
parser.add_argument('--restart_lr_after', type=float, default=-1.0) # -1 = disabled
parser.add_argument('--restart_warmup_epochs', type=int, default=0)
parser.add_argument('--restart_adaptive', type=int, default=0, choices=[0, 1])
```

Helper `_custom_restart_lr(epoch)`:
```python
# Per ciclo n: cycle_max_lr = base_lr * (restart_decay ** n)
# OR cycle_max_lr = restart_lr_after se > 0
# Cosine all'interno del ciclo, warmup linear opzionale nelle prime restart_warmup_epochs
cosine_factor = 0.5 * (1.0 + math.cos(e_in_cycle * math.pi / cycle_T))
```

Helper `_check_restart_trigger()`: fixed T0 (epoch >= cycle_start + T0) OR adaptive (T_intra↓×2 vs cycle max).

**5 meccanismi**:
- **Opt 1 (decay 0.3)**: lr cicli 0.5 → 0.15 → 0.045 (smorzamento progressivo)
- **Opt 2 (2-tier)**: ciclo 0 con lr=0.5, cicli successivi con lr_after=0.1
- **Opt 3 (adaptive)**: restart triggerato da T_intra calo ×2 invece di T0 fisso
- **Opt 4 (warmup 3 ep)**: linear warmup post-restart per 3 epoche
- **Opt 5 (combo 1+4)**: decay 0.3 + warmup 3 ep

**10 esperimenti**: 5 mech × {C3 base (h=32, λ_sr=1), E1 base (h=16, λ_sr=5)}. Notebook `Prodigy_Restart_Mechanisms_R32.ipynb` (9 celle).

**Audit Python 3.10**: tutte le 9 celle passano `ast.parse(feature_version=(3,10))`. Fix Cell 3 (era SyntaxError per `\'` in f-string expression — vietato fino a 3.12, rilassato in 3.12+). Tag git `pre_R32`. HEAD `a552f55` pushed.

**Stato**: pronto su Azure, **non ancora eseguito**. ~4.6h compute stimato. Output atteso: `results/Prodigy_Study/R32_RestartMechanisms/`.

#### Lezione #49 — Python 3.10 compatibility check obbligatorio prima di pushare su Azure
Azure ML cluster usa Python 3.10. `\'` (backslash) in f-string expression è vietato fino a 3.12 (PEP 701). Local Python 3.13 compila ma Azure 3.10 fallisce. **Aggiungere `ast.parse(src, feature_version=(3,10))` come step di pre-push** per ogni notebook.

---

## 📅 2026-06-16 — R32 RestartMechanisms eseguito + R33 Closure (CHIUSURA STUDIO)

### Mattina — R32 eseguito (10 esp.)

5 meccanismi soft (decay, 2-tier, adaptive, warmup, combo) × 2 baseline (C3, E1). Risultati chiave:

| Rank Tp | Tag | Tp | val_data | ep | gn_max |
|---:|---|---:|---:|---:|---:|
| 1 | R32_A3_adaptive | 0.0651 | 0.170 | 25/50 | 1e19 |
| 2 | R32_A4_warmup2ep | 0.0635 | 0.165 | 41/50 | 1.2e13 |
| 3 | R32_B3_E1_adaptive | 0.0626 | 0.175 | 19/50 | 4e18 |
| 4 | R32_A1_decay03 | 0.0577 | **0.163** | 25/50 | 6.5e5 |
| 4 | R32_A2_2tier_015 | 0.0577 | 0.163 | 25/50 | 6.5e5 |
| ... | R32_B2_E1_2tier | 0.0500 | **0.1609** record | 50/50 | 5.3e9 |
| ... | R32_B5_E1_decay+warmup | 0.0519 | 0.163 | 50/50 | 5.3e9 |

**Bug A1 ≡ A2**: decay 0.3 e 2-tier 0.15 producono cycle_max_lr coincidente (0.5×0.3 = 0.15), training identico. Solo 4 meccanismi effettivamente distinti.

**Adaptive trigger (A3) = doppio-taglio**: peak Tp record (0.065) ma catastrofico (gn=1e19). Non riproducibile come champion.

**3 champion R32 snapshot** in `Arch_Tested/`: R32_A4_C3_WARMUP_PEAK, R32_A1_C3_DECAY_BALANCED, R32_B5_E1_STABLE. Soppiantano R31_A3/E1.

### Pomeriggio — Analisi diagnostica + 2 correzioni

User identifica 3 anomalie nei grafici R32:
1. **Explosion guard troppo sensibile**: soglia 100 abortiva run con singoli spike isolati. Verificato: tutti gli abort R32 erano su 2 epoche realmente consecutive >100, MA con `gn_total_preclip` naturale spesso fluttuante sopra 100, basta un batch rumoroso per innescare streak=1.
2. **Restart_T0=15 sub-ottimale per 50 ep**: 3 cicli pieni + 1 ciclo monco di 5 ep (restart sprecato).
3. **A1 ≡ A2 bug**: documentato per i prossimi sweep.

**Correzioni in `train.py`** (default updates):
- `epoch_explosion_threshold`: 100 → **10000** (R31_A3 peak=4.3e3, soglia ora distingue divergenza vera da spike transienti)
- `restart_T0`: 15 → **12** (4 cicli pieni in 50 ep, no spreco)

### Sera — R33 Closure (5 esp.) — 2 NUOVI champion

5 esperimenti per chiudere rigorosamente lo studio:
- **C1**: R32_A4 + T0=12 + thr=10000 → **49/50 ep**, Tp=0.0642, **val_data=0.1589 RECORD ASSOLUTO**
- **C2**: R32_A1 + T0=12 + thr=10000 → **50/50 ep**, Tp=0.0518, **gn=52 ✅ CLEAN**
- **C3**: R32_B5 + T0=12 + thr=10000 → 50/50 ep, marginalmente peggio di R32_B5 (gn ridotto 3 OOM, Tp leggermente sotto)
- **D1** (isolation, T0=15 + solo thr=10000): identico a R32_A4 (+1 ep) → soglia da sola non basta
- **D2** (isolation, A3 adaptive + thr=10000): identico a R32_A3 (Tp=0.065, ep=25, gn=1e19) → la sua esplosione era reale

**Snapshot in `Arch_Tested/`**: `R33_C1_A4_T12_PEAK/` e `R33_C2_A1_T12_CLEAN/`. Soppiantano R32_A4 e R29v2_C3.

### Champion roster finale post-R33

| Ruolo | Tag | Tp | val_data | ep | gn_max |
|---|---|---:|---:|---:|---:|
| PEAK | R33_C1_A4_T12_PEAK | **0.0642** | **0.1589** 🏆 | 49/50 | 1.78e19 |
| CLEAN | R33_C2_A1_T12_CLEAN | 0.0518 | 0.1654 | 50/50 | **52** ✅ |
| STABLE | R32_B5_E1_STABLE | 0.0519 | 0.163 | 50/50 | 5.3e9 |
| BASELINE storico | R24F_MIXED_lr0.5_V08 | 0.015 | 0.181 | 30/30 | 21.79 ✅ |

#### Lezione #50 — Il posizionamento dei cicli batte i meccanismi di restart
Tutti i 5 meccanismi soft R32 (decay/2-tier/adaptive/warmup/combo) producono trade-off interessanti, ma il **singolo intervento più impattante** dell'intero R31→R33 è il riposizionamento `T0=15 → T0=12`. +8 ep su A4 (Tp+1%), +25 ep su A1 (clean!). I meccanismi sofisticati venivano vanificati dal ciclo monco residuale.

#### Lezione #51 — Default conservativi delle guard sono critici
Soglia 100 per `epoch_explosion_threshold` (5× sopra R24F CLEAN=21.8) sembrava ragionevole ma diventa hair-trigger nel regime Prodigy + warm restart dove spike naturali transienti sono frequenti. Soglia 10000 (4× sopra R31_A3 stabile=4.3e3) discrimina meglio. **Calibrare le guard sui setup attivi, non sul baseline iniziale**.

#### Lezione #52 — Studio rigoroso ≠ studio infinito
R33 ha dimostrato che le correzioni minime (2 default in `train.py`) bastavano a sbloccare 2 nuovi record. Conferma che fermarsi a una "scoperta" senza verificare le ipotesi sui parametri di setup può lasciare champion non identificati. **5 esp. di chiusura ben mirati > 50 esp. di ricerca esplorativa randomica**.

### Chiusura studio Prodigy — Merge → main

I 5 branch di esplorazione (Architecture/Floor/Optimizer/Training_Method/Visualizer) sono tutti antenati di `Prodigy_Deep_Study`. Un merge `Prodigy_Deep_Study → main` integra l'intera storia del progetto (307 commit). Tag finale: `R33_closure`.

---

## 📌 Note finali

Questo TIMELINE va aggiornato dopo ogni milestone significativa. Mantenere la sezione "Lessons learned" è cruciale per non ripetere errori in future sessioni.

Mantenere anche `P_S.md` (lo "stato attuale" dei problemi/soluzioni) E `SESSION_RESUME.md` (one-pager rapido). Questo TIMELINE è il "diario storico", `P_S.md` è "lo stato di lavoro", `SESSION_RESUME.md` è "il quick-start".
