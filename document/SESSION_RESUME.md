# SESSION_RESUME.md — Quick context for any new Claude session

> **Scopo**: in 5 minuti capire **dove siamo**, **cosa è stato fatto**, **cosa fare adesso**.
> Aggiornare ad ogni milestone (1 sezione "Stato attuale" sempre aggiornata, log storico in coda).

---

## 🎯 Stato attuale (2026-06-20 — **Dynamic_Study: il tetto sui parametri dinamici a/b**)

**Branch corrente**: `Dynamic_Study` (da `main`; `Loss_Study` è stato **merge in `main`** come milestone).
**Documenti maestri (leggere in quest'ordine per il contesto pieno)**:
1. `document/DYNAMIC_STUDY_PLAN.md` — diagnosi, disegno degli studi, batch di soluzioni, mappa skill/cassetto.
2. `document/DYNAMIC_STUDY_B_RESULTS.md` — risultati Studio B + L0 (la causa, con numeri e figure).
3. `document/VALIDATION_REPORT.md` (+ `.pdf`) — stato della rete S3 validata (micro/meso).

**Contesto**: chiuso `Loss_Study` (validazione SUPERATA — rete `LS3_PEAK_R0_launch_d03`, 0 collisioni,
string-stable; report in `VALIDATION_REPORT.md`). Unico residuo: errore sui parametri **dinamici** a/b
(NRMSE a=0.26, b=0.30). Aperto `Dynamic_Study` per capirne la causa e superarlo.

**Cosa è stato scoperto (Studio B + L0, locali, `scripts/dynamic_study_B.py` / `_L0.py`)**:
- Il tetto **NON è identificabilità di fondo**: un ottimizzatore classico (LM) su dati globali puliti
  recupera tutti e 5 i parametri **esattamente** (NRMSE 0). L'informazione è nei dati.
- Causa **dominante = LOCALITÀ**: la rete predice **per-istante** e nei tratti senza transitori a/b
  sono ciechi (Fisher cond 55→2748 togliendo i transitori; L0: curva a **soglia** — a/b crollano solo
  con contesto W≥160 ≈ 16 s, quando la finestra *cattura* un transitorio).
- **Gap-SNN recuperabile**: la rete (a 0.26/b 0.31) è peggio perfino del LM locale ideale (0.12/0.18)
  di ~+0.13 → margine SNN al contesto attuale, senza toccare la memoria.
- **Direzione molle = rapporto a/b**; a/b **non toccano** né micro (closed-loop dipende da √ab) né
  macro (l'equilibrio `sₑ` è a/b-free → capacità governata da T,v0,s0).

**Batch RIORDINATO** (in `DYNAMIC_STUDY_B_RESULTS.md` §4/§6): #1 **località** (loss per-regime S4 +
memoria/ritenzione + **incertezza dichiarata**); #2 **gap-SNN** (surrogate width / encoding Δv'·jerk /
TET loss); #3 **riparametrizzazione [a,√ab]→deriva b**; #6 cambio modello (Future-B) in frigo.

**L1 ESEGUITO (2026-06-20, `results/Dynamic_Study/L1/`)** — verdetto sorprendente: la memoria ricorrente
è **DANNOSA** per a/b, non solo inutile. Ablandola sul champion addestrato (stato resettato a ogni step):
a 0.331→**0.143**, b 0.178→**0.149** (≈ LM locale ideale 0.12/0.18), s0 0.135→0.082, v0 0.242→0.219,
T pareggio. Il path memoryless vince su 4/5 (gain_ab=−0.109). Decadimento NRMSE(a,b) **piatto** vs distanza
dal transitorio → NON è ritenzione leaky. **Esclude** le leve "ritenzione/canale-lento" e "allungare seq_len".

**Cosa fare adesso**:
1. Girare **`Dynamic_Study_L1p5.ipynb`** su Azure (niente training): conferma del readout **ibrido**
   (a/b memoryless, v0/T/s0 con memoria) PRIMA di L2. EXP A = ablazione statica su 3 seed freschi
   (robustezza del finding L1); EXP B = sanity closed-loop 4 modalità (oracle/normal/memoryless/hybrid),
   riusa `utils/closed_loop_eval.py`, con self-test anti-drift. Poi `git pull` e analisi (output in
   `results/Dynamic_Study/L1p5/`).
2. **L2** secondo l'esito di L1.5: **ibrido sicuro closed-loop** → win a/b a costo zero, L2 si riduce a
   **uncertainty head** (+ eventuale recupero v0/s0); **ibrido instabile** (jitter) → L2 training con
   **regolarizzatore di consistenza memoryless** + **loss per-regime** (leva #1) + uncertainty head.

---

## 🎯 Stato precedente (2026-06-19 — **Loss_Study + framework di EVALUATION completo**) — superseded da Dynamic_Study

**Branch**: `Loss_Study` (da `main` tag `R33_closure`), poi merge in `main`.
**Documento maestro**: `document/LOSS_STUDY_AND_EVALUATION.md` (record completo, auto-sufficiente).

**Cosa è stato fatto (in ordine)**:
1. **S1 — identificabilità**: i 5 parametri ACC-IDM NON sono congiuntamente identificabili
   dall'accelerazione. v0 e `a` = **coppia molle** (provato causalmente, corr −0.82). Aggiunto
   logging `val_*_nrmse` (Lente B) + plot G19/G20.
2. **Osservabilità (la leva)**: scenario **freeflow** sblocca v0 (NRMSE 0.50→0.39); scenario
   **launch** (accel forti ripetute) sblocca parzialmente `a` (0.43→0.65, NRMSE 0.34→0.26). Run
   consolidata `LS3_PEAK_R0_launch_d03` (restart Opzione 1+4, decay 0.3). Bias a/b sistematico in frenata → **S4 futuro**.
3. **Capacità (S2) — SOSPESA** (non esaustiva): modelli grandi esplodono in BPTT. Fix: guard v2
   (frazione + inf), **AGC** (`--grad_clip agc`). Future: LAMB, raggio spettrale, multi-seed.
4. **EVALUATION** (`Loss_Study_Validation_Full.ipynb`, ~6-9 min, un run): **micro** (sicurezza
   closed-loop), **meso** (plotone/string stability, CAM dal leader i−1), **macro** (diagramma
   fondamentale), **vetrina** (accuracy/raster/energia/GIF/dashboard). 15 grafici → `results/evaluate/<analisi>/`.

**Esito EVALUATION v1 (FATTO, `results/evaluate/v1_realistic_cutin/`) — VALIDAZIONE SUPERATA**:
- **MICRO**: **0 collisioni su TUTTI gli scenari** (100 sim/sorgente, cut-in realistico), SNN ≈ oracolo,
  più dolce + più string-stable. (Il 4% della 1ª run era SOLO il cut-in inevitabile, ora corretto.)
- **MESO**: plotone string-stable (head-to-tail <1), convettivo, 0 collisioni.
- **MACRO**: FD corretto; SNN capacità più alta (~2000 vs oracolo 1045) per **bias v0 alto**.
- Energia ~3.9× vs ANN (da AC<MAC). Accuracy 77%. Unico problema residuo: **bias parametri a/b/v0**.

**Cosa fare adesso**:
1. **S4** (lato training): ridurre il **bias a/b/v0** (margini frenata + capacità macro). È l'unico residuo.
2. Poi: EventProp (in pipeline) / deploy FPGA (modello consolidato `LS3_PEAK_R0_launch_d03`).

---

## 🎯 Stato precedente (2026-06-16 — **STUDIO PRODIGY CHIUSO. Merge → main**) — superseded da Loss_Study

**Fase corrente**: **Prodigy Study CLOSED**. R33 Closure ha prodotto 2 nuovi champion finali con record assoluti del progetto. Tutti i 5 branch di esplorazione (Architecture_Exploration, Floor_Diagnostic, Optimizer_Exploration, Training_Method_Exploration, Visualizer_Building) sono antenati di `Prodigy_Deep_Study` → un singolo merge `Prodigy_Deep_Study → main` integra l'intera storia (307 commit).

### Champion finali (4 entries attive in `Arch_Tested/`)

| Ruolo | Tag | Tp | val_data | ep | gn_max | Note |
|---|---|---:|---:|---:|---:|---|
| **PEAK** | `R33_C1_A4_T12_PEAK` | **0.0642** | **0.1589** 🏆 | 49/50 | 1.78e19 | Record val_data assoluto |
| **CLEAN** | `R33_C2_A1_T12_CLEAN` | 0.0518 | 0.1654 | **50/50** | **52** ✅ | 1° setup 50ep+gn<100 |
| **STABLE** | `R32_B5_E1_STABLE` | 0.0519 | 0.163 | 50/50 | 5.3e9 | h=16, 232 params, FPGA-friendly |
| **BASELINE** | `R24F_MIXED_lr0.5_V08` | 0.015 | 0.181 | 30/30 | 21.79 ✅ | Storico, certificato CLEAN |

### Cronologia ultimi 4 giorni (2026-06-13 → 2026-06-16)

1. **2026-06-13 R30 Identifiability** (10 esp.) — supervisione ausiliaria 4-tuple sblocca rank-collapse (rank≥3 in 8/10 run).
2. **2026-06-14 R31 Champion Validation** (14 esp.) — 3 champion candidati: C3 CLEAN, A3 PEAK, E1 STABLE.
3. **2026-06-15 R32 Restart Mechanisms** (10 esp.) — 5 meccanismi soft × 2 baseline. Soppianta R31_A3/E1. Identificato peak val_data record (B2=0.161). Bug A1≡A2 per cycle_max coincidenza.
4. **2026-06-16 mattina — R33 Closure preparato**: 2 correzioni in `train.py` (`epoch_explosion_threshold` 100→10000, `restart_T0` 15→12). 5 esp. (3 champion replica + 2 isolation controls).
5. **2026-06-16 pomeriggio — R33 eseguito**: scoperti 2 NUOVI champion:
   - **R33_C1** (A4 con T0=12): 49/50 ep, Tp=0.0642, **val_data=0.1589 RECORD ASSOLUTO**
   - **R33_C2** (A1 con T0=12): 50/50 ep, **gn=52 CLEAN**, primo setup mai osservato a combinare 50 ep + gn<100
   - Isolation controls (D1, D2) confermano che il guadagno viene SOLO da T0=12 (la soglia rilassata da sola non basta)

### Stato infrastruttura corrente (2026-06-16)

**Branch git**: `Prodigy_Deep_Study` HEAD `f7cbd73`. Tag: `pre_R27`, `pre_R28`, `pre_R29`, `pre_R30`, `pre_R31`, `pre_R32`, `pre_R33`. **Da creare**: `R33_closure` post-merge.

**Codice principale**:
- `train.py`: nuovi default R33 (`epoch_explosion_threshold=10000.0`, `restart_T0=12`)
- 5 nuovi CLI flag R32 invariati (`--restart_decay`, `--restart_lr_after`, `--restart_warmup_epochs`, `--restart_adaptive`, `--restart_T0`)
- `core/network.py`: decoder fix C3 opt-in (DEC-1 + DEC-3)
- `data/generator.py`: 4-tuple loader R30

**Results dir attive**:
- `results/Prodigy_Study/R31_ChampionValidation/` (14 run)
- `results/Prodigy_Study/R32_RestartMechanisms/` (10 run + diagnostic)
- `results/Prodigy_Study/R33_Closure/` (5 run + side-by-side)
- `results/Prodigy_Study/_COMPLETE_360_analysis.csv`, `_TRUE_Tintra_ranking.csv`

**Arch_Tested**: 14 entry totali (4 attive + 10 storiche/superseded)

### Cosa fare adesso (priorità)

1. **Merge `Prodigy_Deep_Study` → `main`** (no-ff per preservare storia 307 commit)
2. **Tag finale**: `R33_closure` su `main` post-merge
3. **Cleanup branch obsoleti**: i 5 branch ancestor (Architecture/Floor/Optimizer/Training_Method/Visualizer) sono sicuri da rimuovere — il merge li integra automaticamente
4. **Push `main` + delete remote dei 5 branch obsoleti**
5. **Fase successiva (post-merge)**: deployment/quantizzazione PYNQ-Z1 con R33_C2 come baseline (clean + 50ep complete + 864 params) o R33_C1 se serve max accuracy

### Verità chiave 2026-06-16 (closure)

- **T0=12 batte T0=15 sistematicamente**: 4 cicli pieni in 50 ep, no ciclo monco sprecato. +8 ep su A4, +25 ep su A1.
- **Decay 0.3 + T0=12 = combinazione CLEAN**: dopo 4 cicli lr lavora a ~1e-2, dinamica BPTT quasi lineare, gn pulito.
- **Warmup 2ep + T0=12 = combinazione PEAK**: smussa il restart abbastanza da mantenere il peak Tp ma porta a esplosioni tardive irrilevanti per la completion.
- **Lo studio è chiuso**: i 4 champion coprono tutti i ruoli operativi richiesti. Non ci sono motivi scientifici per ulteriori sweep prima del deploy.

---

## 🎯 Stato precedente (2026-06-15 — R30/R31 completati, R32 pronto su Azure) — superseded by R33 closure

**Fase corrente**: **3 champions validati** post-R31 (Champion Validation 14 esp.). R30 (Identifiability) confermato che la supervisione ausiliaria + decoder fix risolvono il rank-collapse. R31 ha identificato 3 trade-off ottimali distinti. R32 (Restart Mechanisms, 10 esp.) è **pronto su Azure** ma non ancora eseguito.

### I 3 champion attuali (snapshot in `Arch_Tested/`)

| Tag | Categoria | T_intra peak | val_data | gn_max | Note |
|---|---|---:|---:|---:|---|
| ⭐ `R29v2_C3_CLEAN` | **Scientific reference** | 0.0407 | 0.177 | **40.6** ✅ | 4/4 obiettivi, riproducibile, baseline pulito |
| ⭐ `R31_A3_PEAK` | **Operational best** | **0.0599** | **0.167** | 4280 ⚠ | Best val_data @ ep15 pre-explosion (cosine warm restart T0=15) |
| ⭐ `R31_E1_STABLE` | **Long-run stable** | 0.038 | 0.173 | 1.3e6 ⚠ | 50/50 ep completati, 232 params (h=16, rank=4), λ_sr=5 |

Tutti e 3 usano: Prodigy `lr=0.5`, DEC-1 (per-channel τ=[10,3,10,3,3]) + DEC-3 (init_bias_shift=1), R30 4-tuple loader (supervisione ausiliaria).

### Cronologia ultimi 3 giorni (2026-06-13 → 2026-06-15)

1. **2026-06-13 — R30 Identifiability (10 esp.)** — applicata supervisione ausiliaria su v0/s0/a/b (4-tuple loader) + decoder fix C3 (init_bias + per-ch τ). Rank-collapse risolto (rank_effective ≥ 3 in 8/10 run). Conferma: il bottleneck principale era identifiability, non capacità rete.

2. **2026-06-14 — R31 Champion Validation (14 esp.)** — sweep 50 ep su 4 dimensioni (decoder/scheduler/spike-pressure/capacity). Scoperti **3 champion** distinti:
   - **C3** (no restart, 10 ep): CLEAN reference scientifico
   - **A3** (cosine T0=15, 50 ep abort@32): peak operativo @ep15 prima dell'esplosione
   - **E1** (h=16, λ_sr=5): unico 50/50 ep completati senza abort

3. **2026-06-15 mattina — Analisi numerica 360°** su R31 (49 run totali aggregati con R28/R29/R30). Identificato pattern critico: **warm restart al primo trigger (ep15) genera SEMPRE il peak T_intra**, ma successivamente il loss landscape implode. → ipotesi: restart troppo violento (lr salta 90× istantaneamente).

4. **2026-06-15 pomeriggio — R32 Restart Mechanisms preparato**: implementati nel `train.py` 5 meccanismi soft per il restart:
   - **Opt 1 (decay)**: `cycle_max_lr *= restart_decay^cycle_num` (0.5 → 0.15 → 0.045)
   - **Opt 2 (2-tier)**: `restart_lr_after` per cicli successivi (lr fisso post-restart)
   - **Opt 3 (adaptive)**: trigger basato su T_intra↓×2 invece di T0 fisso
   - **Opt 4 (warmup)**: linear warmup di N epoche post-restart
   - **Opt 5 (combo 1+4)**: decay + warmup combinati
   - 10 esperimenti × 50 ep: 5 mech × {C3 base, E1 base}. Notebook `Prodigy_Restart_Mechanisms_R32.ipynb` audit Python 3.10 OK su tutte le 9 celle.

### Stato infrastruttura corrente (2026-06-15)

**Branch git**: `Prodigy_Deep_Study` HEAD `a552f55` (post-fix Python 3.10 Cell 3). Tag rollback: `pre_R27`, `pre_R28`, `pre_R29`, `pre_R30`, `pre_R31`, `pre_R32`.

**Codice principale** (cumulative state):
- `train.py`: + 5 nuovi CLI flag `--restart_T0`, `--restart_decay`, `--restart_lr_after`, `--restart_warmup_epochs`, `--restart_adaptive` (default no-op, backward-compat verificato)
- `train.py`: helper `_custom_restart_lr(epoch)` + `_check_restart_trigger()` (R32)
- `core/network.py`: decoder fix opt-in (DEC-1 + DEC-3) confermati nei 3 champion
- `data/generator.py`: 4-tuple loader R30 (x, y, mask, params_gt) attivo

**Results dir attive (aggiornate)**:
- `results/Prodigy_Study/R30_Identifiability/` — R30 (10 run, baseline pulito + supervisione)
- `results/Prodigy_Study/R31_ChampionValidation/` — R31 (14 run, sweep 50 ep su 4 dimensioni)
- `results/Prodigy_Study/_COMPLETE_360_analysis.csv` — 49 run totali aggregati
- `results/Prodigy_Study/_TRUE_Tintra_ranking.csv` — re-ranking per peak T_intra (non val_total)

**Arch_Tested aggiornato** (9 entry totali):
- 3 nuovi champion: `R29v2_C3_CLEAN`, `R31_A3_PEAK`, `R31_E1_STABLE`
- README master aggiornato con tabella T_intra + sezione "Note critiche"

### Cosa fare adesso (priorità)

1. **Eseguire R32 sweep su Azure** (~4.6h, 10 esp. × 50 ep). User trigger richiesto: notebook `Prodigy_Restart_Mechanisms_R32.ipynb`. Output atteso in `results/Prodigy_Study/R32_RestartMechanisms/`.
2. **Analisi post-R32**: confrontare i 5 meccanismi soft vs warm restart standard (R31_A3 baseline). Domanda: il decay/warmup permette di MANTENERE il peak T_intra senza l'esplosione successiva?
3. **Decisione strategica post-R32**: se almeno 1 meccanismo soft regge 50 ep con T_intra > 0.05 e gn_max < 1000 → nuovo champion. Altrimenti, accettare R31_A3_PEAK come definitivo e chiudere Prodigy Study.
4. **Merge `Prodigy_Deep_Study` → main** dopo chiusura Prodigy Study, con tag finale `R32_closure`.

### Verità chiave 2026-06-15

- **Warm restart standard (cosine T0=15) è una lama a doppio taglio**: il primo restart coincide quasi sempre con il peak T_intra ma la rete poi implode (gn esplode +3 OOM).
- **Capacity ridotta = stabilità**: E1 (232 params) è l'unico setup con 50/50 ep, ma a costo di T_intra inferiore (0.038 vs 0.060).
- **Identifiability era il vero bottleneck**: la supervisione ausiliaria R30 ha sbloccato il rank-collapse universale visto in R27.
- **R32 è l'ultimo esperimento prima della chiusura**: 5 meccanismi soft per capire se il peak R31_A3 è sostenibile o solo un evento di transizione.
- **Codice train.py è ora ricco di feature opt-in (R29 DEC-1/DEC-3, R30 4-tuple, R32 5 restart mech)**: tutti default no-op = backward-compat. Configurazione corrente attiva via CLI flag.

---

## 🎯 Stato precedente (2026-06-12 — **RESET strategico al vero baseline R24F_mixed_lr0.5_V08**)

**Fase corrente**: **VERO baseline identificato**: `R24F_mixed_lr0.5_V08` (val_data 0.181, val_total 0.189, gn_max 21.79 CLEAN). Snapshot salvato in `Arch_Tested/R24F_MIXED_lr0.5_V08_TRUE_CHAMPION/`. R27-R29 completati ma su baseline instabile (Prodigy lr=1.0 con gradienti esplosi mascherati dal clip). R30 (next step) parte da QUESTO baseline pulito.

### Cronologia ultimi 9 giorni post-fix (2026-06-03 → 2026-06-12)

1. **2026-06-03** — Audit codice + 4 bug fix in `core/network.py` + `core/eventprop.py` (vedi `BUGS_2026-06-03.md`). Tag git `pre_bug_fix_2026-06-03`.

2. **2026-06-04 → 06** — **R24F (Prodigy MultiParam PostFix, 93 esperimenti)**: sweep LR × variant × scenario. ⭐ **Best mixed: R24F_mixed_lr0.5_V08** = val_data 0.181, val_total 0.189, **gn_max 21.79 (CLEAN)**. Best highway: R24F_highway_lr1.0_V08 = 0.162 (con caveat 20% run esplosi).

3. **2026-06-07 → 09** — **R25 Ablation Study (18 esp.)** + **R26 Fusion (6 esp.)**. Errore strategico: baseline scelto `lr=1.0` (NON `lr=0.5`). Tutti i run con gn_max 10⁵-10¹⁷ (gradienti esplosi mascherati dal clip).

4. **2026-06-11** — **R27 Audit (24 run R25+R26)**: introdotte metriche `val_T_intra_corr` + `rank_effective`. Scoperto rank-collapse universale (rank=1 in 18/24). Fix bug LAYER_MAP (4/6 colonne gradient sempre NaN dal 2026-06-07).

5. **2026-06-11 → 12** — **R28 ProdigyTuning (5 esp.)** + **R29 DecoderFix (12 esp.)**. Confermato: Prodigy non era bottleneck (R28), decoder fix non aiutano (R29 disastrosi, init_shift annullato in 100 step, τ-anneal breaks training). Ma tutto ancora su baseline lr=1.0 instabile.

6. **2026-06-12 — RESET strategico**: utente solleva ipotesi instabilità baseline → verifica numerica conferma. **R24F_mixed_lr0.5_V08 è il SOLO setup post-fix con gradienti CLEAN** (gn_max 21.79 vs 10⁵-10¹⁷ degli altri). Snapshot fissato in Arch_Tested. R27-R29 mantengono valore informativo (rank-collapse confermato, Prodigy non colpevole) ma vanno re-misurati sul baseline vero.

### Stato infrastruttura corrente (2026-06-12)

**Branch git**: `Prodigy_Deep_Study` HEAD post-R29. Tag rollback: `pre_R27`, `pre_R28`, `pre_R29`.

**Codice principale** (post-fix 2026-06-03 + R27 LAYER_MAP fix + R27 val_T_intra_corr + R29 DEC-1/DEC-3 opt-in):
- `train.py`: full features ma R29 flags DEFAULT no-op (backward-compat verificato)
- `core/network.py`: decode_offset + logit_tau buffer opt-in (default 0/1 = identity)
- `data/generator.py`: invariato (y_phys = [v_dot, T_true] only)

**Vero baseline ufficiale**: `Arch_Tested/R24F_MIXED_lr0.5_V08_TRUE_CHAMPION/`
- Prodigy `lr=0.5` (NON 1.0), cosine_no_restart, seq_len=50, mixed scenario
- val_data 0.181, val_total 0.189, gn_max 21.79 CLEAN
- spike_rate 7.3% (basso ma stabile)
- `prodigy_d` arriva a 0.0192 (sano)

**Results dir attive**:
- `results/Prodigy_Study/MultiParam_PostFix/` — R24F (93 run originali, fonte verità)
- `results/Prodigy_Study/Ablation_R25/` — R25 (18 run, baseline lr=1.0 instabile)
- `results/Prodigy_Study/Fusion_R26/` — R26 (6 run, baseline lr=1.0 instabile)
- `results/Prodigy_Study/Audit_R27/` — R27 (24 run R25+R26 auditati)
- `results/Prodigy_Study/ProdigyTuning_R28/` — R28 (5 run, lr=1.0)
- `results/Prodigy_Study/DecoderFix_R29/` — R29 (12 run, lr=1.0 + R29 fixes)

### Cosa fare adesso (priorità)

1. **Sanity replica del baseline R24F_mixed_lr0.5_V08** con codice corrente → conferma val_data ≈ 0.181 e gn_max < 25
2. **Audit R30 sul baseline replicato** con metriche R27 (T_intra_corr, rank_effective) → verifica se i sintomi rank-collapse persistono anche con gradienti puliti
3. **R30 Identifiability**: supervisione ausiliaria su v0/s0/a/b (originale piano DEC-1) sopra il baseline R24F_mixed_lr0.5_V08, non più su R25_A3 instabile
4. **Decisione strategica post-R30**: se rank-collapse persiste anche con baseline pulito + supervisione → bottleneck è capacità rete 864p → considerare A8 attn 3936p re-testato post-fix

### Verità chiave 2026-06-12

- **lr=0.1 Prodigy NON funziona** (val_data 0.7-1.0, la rete non converge)
- **lr=1.0 Prodigy è instabile** (20-50% dei run esplodono, anche quelli "non esplosi" hanno gn 10⁵-10¹⁷)
- **lr=0.5 Prodigy V08 cosine_no_restart è l'UNICO setup CLEAN** post-fix
- **T30_A8 (val=0.166)** è stato un evento fortuito (lambda_sr=0, highway-only, NON riproducibile cross-scenario)
- **Tutti R25/R26/R28/R29 hanno gradienti esplosi mascherati**: metriche numeriche corrette ma dinamica corrotta
- **rank-collapse e identifiability sono problemi REALI** (visti da R27/R29) ma vanno re-misurati su baseline stabile

---

## 🎯 Stato precedente (2026-06-10 — R26 Fusion in esecuzione su Azure) — superato dalla scoperta lr=0.5 V08

**Fase corrente**: **R26 — Fusion Study Prodigy** (6 esperimenti). Costruito su R25 (18 ablation completati), che ha identificato 3 fattori indipendenti ortogonali. R26 testa se gli effetti **sommano** quando combinati.

**Fase corrente**: **R26 — Fusion Study Prodigy** (6 esperimenti). Costruito su R25 (18 ablation completati), che ha identificato 3 fattori indipendenti ortogonali. R26 testa se gli effetti **sommano** quando combinati.

### Stato cronologico ultimi 7 giorni (2026-06-03 → 2026-06-10)

1. **2026-06-03 mattina** — **Audit codice approfondito** post-R2.4 (Prodigy MultiParam 90 run): individuati **4 bug strutturali** in `core/network.py` + `core/eventprop.py` (vedi `BUGS_2026-06-03.md`). I ranking pregress (T30, P15, SW, R2.2, R2.4) sono **CORROTTI**.

2. **2026-06-03 pomeriggio** — **Fix applicati** (4 bug risolti):
   - **#1** F5 sigmoid saturation → rimosso `raw / decode_scale` in `_decode_params`
   - **#2** Xavier asymmetric bias → row-mean subtraction in `OutputLayer_LI` + `LILayer_BitShift_Po2`
   - **#3** ALIF cascade dead output → `base_threshold=1.0` per layer non-input in Stacked/StackedSkip
   - **#4** Delay mask 1/max_delay penalty → `fc_weight.mul_(sqrt(max_delay))` post-Xavier
   - Tag git: `pre_bug_fix_2026-06-03` (rollback se servisse)
   - **Verifica empirica**: saturation 0% (vs 96-97% pre-fix), spike rate 6-10%, gradient ≠ 0 su 5/5 canali

3. **2026-06-04 → 06** — **R2.4F — Prodigy MultiParam PostFix** (93 esperimenti, ~15h Azure):
   - 90 Prodigy (3 LR × 10 varianti × 3 scenari) + 3 AdamW baseline
   - **Best mixed**: V08 (cosine_no_restart) lr=0.5 → val_total **0.1887** (vs floor pregress 0.22)
   - V08 batte AdamW del 9-18% su tutti gli scenari
   - **Problema scoperto post-fix**: violin G7 mostra che `T` predetto è quasi PIATTO intra-sample (linea piatta intorno alla media), NON segue la dinamica `T_true(t)`. v0/s0 saturano ancora ai bound. `a` stuck al MIN.

4. **2026-06-07 → 09** — **R25 — Ablation Study causale** (18 esperimenti × 10ep, ~3h Azure):
   - 5 assi: A memoria temporale, B loss balancing (λ_T_aux), C spike rate regularizer, D capacity, E training duration
   - **R25 changes a `train.py`**: nuova `--lambda_T_aux` CLI + 11 colonne CSV tracking + 16 colonne batch CSV con gradient diagnostics per canale (3 livelli × 5 IDM params)
   - **R25 plot diagnostics**: G16 (gradient raw per channel), G17 (gradient decoded post-sigmoid), G18 (gradient direction sign mean)
   - **3 WIN INDIPENDENTI identificati** (ognuno migliora T_tracking_corr senza danneggiare val_total):
     - **A4**: `max_delay 6→18` → ΔT_corr = **+0.090**, Δval = -0.015
     - **B1**: `lambda_T_aux 0→0.1` → ΔT_corr = **+0.147**, Δval = -0.006 ⭐ BEST PURO
     - **C1**: `lambda_sr 0.5→0` → ΔT_corr = **+0.088**, Δval = -0.014 (lambda_sr regulariz era CONTROPRODUCENTE)
   - **D (capacity)**: NON è bottleneck. D3 large (128h) crasha (best_ep=1).
   - **E (training duration)**: SHOCKING — più training **PEGGIORA** T_corr. E2 (20ep) → T_corr 0.226 vs baseline 0.353. La rete "dimentica T" col tempo. **Early stop ≈ 10 ep è la scelta giusta.**

5. **2026-06-10 — R26 Fusion Study** (6 esperimenti, ~1h Azure, **IN ESECUZIONE**):
   - F0 baseline replica (sanity)
   - **F1 TRIPLE_win** = A4+B1+C1 (TOP candidato, atteso T_corr 0.55-0.62 se sommano)
   - F2 A4+B1 (no sr_off), F3 B1+C1 (no memoria), F4 A4+C1 (no T_aux) — controlli per isolare interazioni
   - F5 TRIPLE+epochs=5 (asse E)
   - Linearity test automatico in Cell 6: confronta F1 measured vs somma R25 predetta
   - Bug fix lungo la strada: `_robust_rmtree` per NFS Azure + tag univoco timestamp (race rmtree↔makedirs)

### Stato infrastruttura corrente

**Branch git**: `Prodigy_Deep_Study` HEAD **`6075a96`** (fix R26 NFS).

**File codice modificati post-2026-06-03**:
- `core/network.py` (4 fix + bit_shift kwarg)
- `core/eventprop.py` (fix #2 + #4)
- `train.py` (R25: pinn_loss + 4-tuple + CLI lambda_T_aux/cf_max_delay/cf_bit_shift + 27 colonne CSV totali)
- `utils/plot_diagnostics.py` (G16/G17/G18)
- `eval_report.py` (4-tuple compat)
- 5 snapshot in `Arch_Tested/` (4 fix replicati)

**Notebook attivi**:
- `Prodigy_MultiParam_Study_PostFix.ipynb` — R24F (93 run completate, archiviato)
- `Prodigy_Ablation_Study_R25.ipynb` — R25 (18 run completate, archiviato)
- `Prodigy_Fusion_Study_R26.ipynb` — R26 in esecuzione

**Results dir**:
- `results/Prodigy_Study/MultiParam_PostFix/` — 93 run R24F (3 scenari × 31 run = highway/mixed/full)
- `results/Prodigy_Study/Ablation_R25/` — 18 run R25 (5 assi)
  - `_aggregate_full.csv` — tabella sintesi con tutte le metriche tracking + delta vs baseline
- `results/Prodigy_Study/Fusion_R26/` — popolata progressivamente da R26

### Verdetto Prodigy (post R24F + R25)

- **Prodigy V08 (cosine_no_restart, lr=1.0, d_coef=1.0, d0=1e-6, growth=inf, safeguard=1, bias_corr=1, betas=0.9,0.99, wd=0.01)** è **chiaramente superiore ad AdamW** post-fix:
  - highway: Prodigy V08 0.169 vs AdamW 0.186 (-9%)
  - mixed: 0.189 vs 0.230 (-18%)
  - full: 0.222 vs 0.253 (-12%)
- **V08 vince su tutti i 3 scenari**. Cosine_no_restart è il scheduler ottimale.
- Verdetto Prodigy considerato STABILE per ora. R26 verifica se ulteriori miglioramenti sono ottenibili.

### Cosa fare adesso (priorità)

1. **Aspettare risultati R26 da Azure** (~1h, 6 run × ~10 min)
2. Quando completati:
   - `git pull` per sincronizzare risultati
   - Cell 6 del notebook fa il **Linearity Test automatico** (F1 measured vs somma R25 predetta)
   - Cell 7 mostra G7/G13/G16/G18 per F0/F1/F5
   - Cell 8 mostra il summary best per T-tracking e val_total
3. **Decisione operativa post-R26**:
   - Se F1 raggiunge T_corr > 0.55 → abbiamo un nuovo champion `R26_F1_TRIPLE_win`. Procedere a validazione su highway/full (scenari pregress R24F)
   - Se F5 batte F1 → confermare asse E (early stop = giusto)
   - Se F1 ≈ max(F2,F3,F4) → c'è saturazione; un fattore è dominante → scegliere quello + ulteriore esplorazione
   - Se F1 < max(F2,F3,F4) → interazione negativa (raro); investigare quale coppia è ottimale

### R3 — Studio EventProp (RIMANDATO)

Originariamente pianificato dopo R2, ora rimandato dopo R26+. Da iniziare quando il problema "T-tracking flat" sarà chiuso (R26 candidato risolutivo). Stessa logica R25: ablation lever-by-lever (clip, lr peak, warmup, init scaling, detach periodico, thresh_jump learnable, full λ_fatigue), trovare almeno UN setup stabile.

---

## 🎯 Stato precedente (2026-06-02 — R2 CHIUSO con caveat, R3 next) — SUPERATO da R24F+R25+R26

**Fase corrente**: **R2 — Studio Prodigy CAPIRE** ✅ chiuso (con caveat). PRODIGY_DEEP_STUDY.md ora ha parte 1+2+3 (~750 righe). Aspetta direzione utente per R3 (EventProp serio) o R4 (scenari misti).

### R2 verdetto (sintesi)

- **Prodigy NON è "broken"** (AUDIT §2.2 confutato): con `betas=(0.9, 0.99)` attivo (W1) pareggia BPTT+AdamW numericamente (val_total 0.228 vs F2 0.226, 10ep vs 15ep).
- **W1 è il singolo lever più impattante**: val_total da 0.303 (default) → 0.228 (W1). Conferma "dramatic improvement" madman404.
- **V2 (d0=1e-5)** ≈ W1: val_total 0.230. Conferma fix konstmish ufficiale.
- **Setup CANONICAL completo** (P-E) ≈ P-B singolo: gli altri lever (d_coef, use_bias, cosine) sono marginali in questo task.

### Caveat critico (Lezioni M1-M4)

⚠️ **TUTTI i 5 esperimenti hanno violin G7 collassati**: la rete predice CONSTANTS per i 5 params IDM, NON decodifica vero. Causa: highway-only training (tutti scenari hanno stessi IDM params target). 

**Implicazione**: val_total è INGANNEVOLE in highway-only. Tutti i ranking pregress (T30, SW, P15) sono confusi dallo stesso problema. **Verdetto Prodigy vs AdamW richiede R4 (scenari misti)** per essere conclusivo.

⚠️ La predizione "d frozen" era SBAGLIATA: d sale a 0.017-0.195 in tutti i 5 esperimenti R2 (era 0.001-0.003 in T30 forse per assestamento lungo). Caratterizzazione affrettata da single-metric per-epoch.

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
2. `ls results/P9/P9_S2A_fast_baseline/`
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
