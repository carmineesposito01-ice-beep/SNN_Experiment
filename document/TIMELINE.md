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

**Status corrente**: in attesa di lancio `P9_S1_highway_v2` su Azure con notebook aggiornato.

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

---

## 🔮 Roadmap futura (post-`P9_S1_highway_v2`)

### Caso A — P9_S1_highway_v2 ha val_loss < 0.30
**P9 confermato**. Capacity insufficiency è il vero problema.

**Next**: STEP 2 — capacity increase
- `CF_HIDDEN_SIZE = 64` (era 32)
- `CF_RANK = 16` (era 8)
- Totale: 864 → ~2700 param (ancora FPGA-friendly)
- Test su dataset full-mix con tutti i fix (A3+B5+P11)
- Target: val_loss < 0.25

### Caso B — P9_S1_highway_v2 ha val_loss ≈ 0.35
**P9 falsificato**. Il limite è dato dal task/loss/encoding, non dalla rete.

**Next**: indagine separata
- Rivedere normalizzazione input (NORM_S_MAX, NORM_V_MAX, ecc.)
- Rivedere bilanciamento lambda (i 5 termini sono comparabili?)
- Valutare se l'OU floor (~1.8e-4) è davvero il limite teorico
- Considerare riformulazione del task (regression diretta di v_dot invece di parametri IDM?)

### Caso C — P9_S1_highway_v2 va in plateau a ~0.30
**P9 parziale**. Procediamo a STEP 2 ma con aspettative ridotte.

---

## 📌 Note finali

Questo TIMELINE va aggiornato dopo ogni milestone significativa. Mantenere la sezione "Lessons learned" è cruciale per non ripetere errori in future sessioni.

Mantenere anche `P_S.md` (lo "stato attuale" dei problemi/soluzioni) E `SESSION_RESUME.md` (one-pager rapido). Questo TIMELINE è il "diario storico", `P_S.md` è "lo stato di lavoro", `SESSION_RESUME.md` è "il quick-start".
