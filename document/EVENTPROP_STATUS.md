# EventProp — Stato attuale + punto di ripresa (2026-06-30)

Branch `EventProp_Study`. **Documento-master di ripresa dello studio EventProp**: dove siamo, cosa funziona,
cosa è escluso e perché, le pratiche, e come continuare. Dettagli complementari: **`document/EVALUATE_UPGRADE.md`**
(upgrade evaluate 6-tier), **`results/EventProp_Study/combined/INDEX.md`** (studio combinato),
**`document/HOW_IT_WORKS_v3.md`/.pdf** (come funziona la rete — tecnico e aggiornato, gemello di
`VALIDATION_REPORT_v3`; supersede HOW_IT_WORKS.md v1/v2) + `GLOSSARY.md` (architettura/fisica). Le §1-§8 sono il record storico dello studio EventProp; la **§9** è
l'aggiornamento post-BigSweep3 (studio combinato + evaluate v3).

---

## 0. COME RIPRENDERE (leggere prima questo)

**Progetto CF_FSNN**: una SNN (ALIF + EventProp) che, osservata una traiettoria di car-following,
**identifica i 5 parametri ACC-IIDM** `[v0, T, s0, a, b]`. Target finale: deploy FPGA PYNQ-Z1 (pesi po2).

**Stato in una riga (2026-06-30)**: studio EventProp **mappato e chiuso** (BigSweep1→3 + **studio combinato**
su 102 arm). EventProp è su un **fronte di Pareto** col BPTT champion: il champion vince la fisica di ~5.5%,
EventProp vince NRMSE + stabilità (raggio spettrale 0.5 vs 22) + FPGA-friendliness (rank8), e **entrambi
guidano in SICUREZZA** (0 collisioni, min-gap preservato). Costruito un **evaluate v3 esaustivo (6-tier)** e
il **notebook champion `Eval_v3_TURTLE_POWER`** (4 champion + oracolo) — in attesa di girare su Azure.

**Per continuare (dal più fresco):**
1. `git pull origin EventProp_Study`.
2. **Evaluate v3 — COMPLETO (2026-07-01), 15/15 sezioni** in `results/evaluate/v3_TURTLE_POWER!!!/`
   (re-run post-fix eseguito su Azure; `python scripts/verify_eval_v3.py` OK).
   **Verdetto cross-champion**: fixed-point output trascurabile fino a 2 bit; QAT funziona (pesi po2 ≤ float su 3/4 champion,
   `delta_qat_absorbed` negativo); energia 22–30×; **ρ(U@V): EventProp contrattivo (Donatello 0.05, Michelangelo 0.39) vs BPTT
   >1 (Raffaello 2.99, Leonardo 1.16) → EventProp più FPGA-friendly** (corregge la stima preliminare ρ≈0.16 del framework);
   V2X **blind = 0.67 collisione** (hold-last maschera moltissimo; la rete da sola è insicura); ghiaccio ~60% coll. anche per
   l'oracolo (limite fisico del plant). **Candidato deploy FPGA: Donatello** (contrattivo + best accuracy).
   ✅ **RISOLTO**: meso(12)/macro(13)/showcase(14) + diagnostica-energia eventprop rigenerati dopo il fix `e42af18` (la
   variante `eventprop_alif_full` non fa `forward_step` per-step; identify→model=None per meso/macro, spike_raster diretto).
   **📄 Report di chiusura**: **`document/VALIDATION_REPORT_v3.md` / `.pdf`** (22 pag., 15 dimensioni, 4 champion + oracolo;
   builder riproducibile `scripts/build_validation_report_v3.py`; figure-chiave ricostruite dai CSV; verifica avversariale
   3-agenti superata — `e979ad1`).
3. **Caveat aperto (§9.4)**: i risultati closed-loop della famiglia **BPTT_champion** nello Stadio-2 combinato
   (figure F24/F38) sono **sospetti** — il loader del ckpt-pass caricava i baseline come `eventprop_alif_full`
   → readout random silenzioso. Fix (schema-detection) già nel notebook v3; da riportare nel ckpt-pass e
   ri-lanciare i soli arm baseline.
4. Post-eval: quantizzazione/deploy FPGA, multi-seed esteso → `document/FUTURE_WORK.md`.
5. **FPGA-evaluate — design fatto (2026-07-01)**: la *presentazione* della valutazione FPGA è progettata e **bloccata
   per la Fase A software_now** → **`document/FPGA_EVALUATE_DESIGN.md`** (struttura 10 sezioni + catalogo 46 figure +
   principi + prototipo `scripts/_fpga_eval_mockup.py` a dati fittizi) e **`document/FPGA_EVALUATION_FRAMEWORK.md`**
   (analisi + catalogo dati). **Fase B/C (HDL/board) rinviate** — nodo aperto: import Simulink → HDL Coder per una SNN
   ALIF custom (nessun convertitore push-button; FINN/hls4ml non la gestiscono). Prossimo build:
   `scripts/_build_fpga_eval_notebook.py` (Fase A sui tensori reali, come v3.1) + librerie `weight_profiler`/
   `state_profiler`/`latency_model`/`seu_inject`.

**Workflow operativo**: training/eval pesanti su **Azure** (sandokan, `azureml_py38`, Python 3.10), **lanciati
dall'utente**; in locale pull/analisi/build-notebook. L'assistente NON ha accesso diretto ad Azure. Checkpoint
`.pt` **solo su Azure** (`checkpoints/<tag>/best_model.pt`, gitignorati). **Push solo quando Azure è fermo**
(i notebook fanno auto-push → evitare conflitti). Ogni sezione d'analisi **salta se l'output esiste**
(resiliente a crash/idle-shutdown multi-ora).

> **Stato LIVE del job Azure NON è nei documenti** (è runtime): l'assenza di risultati in locale NON distingue
> "mai lanciato" da "in corso" → **chiedere all'utente** lo stato reale prima di agire.

---

## 1. EventProp è risolto e competitivo — la catena di fix (tutti flag opt-in, backward-compat)

EventProp era **sempre instabile** (esplodeva/abortiva). Ora è stabile e convergente.

| Fix | Cosa | Esito |
|---|---|---|
| **C8 / C8b** | clamp adjoint (`jump_clamp`/`lv_clamp`) + gate denom | failsafe; **NON** meccanismo di stabilità |
| **C10** | correzione scala denom per il bit-shift leak | parziale, perturba il training → non usato |
| **C11 — vincolo spettrale** | `lambda*relu(sigma_max(U@V)-target)^2` nella loss | **LA CURA**: la causa era il raggio spettrale della ricorrenza che cresce (0.83→2.8) e fa divergere l'adjoint Rᵀ. Vincolarlo = stabile per costruzione |
| **C12 — ProdigyEvent loss-aware** | P&O bidirezionale su `d` guidato dal trend della LOSS + peso spike-rate | rende ProdigyEvent stabile, ma vedi §3: **non competitivo** |
| **C13 — adjoint completo del fatigue** | `lambda_fatigue` → `thresh_jump` si allena (era congelato) | tecnicamente corretto ma **neutro** sull'accuratezza → off |

**ALIF (soglia adattiva) = infrastruttura PORTANTE, già tarata.** Scan `thresh_jump {0,0.5,1,2}` = U con
minimo a 0.5; a `0` (no ALIF) **esplode** (è il regolatore di sparsità del firing); `1,2` underfit. C13
neutro perché 0.5 è già l'ottimo. **Non è una leva di accuratezza.**

---

## 2. Risultato chiave: il fronte di Pareto (BigSweep1 + BigSweep2, 24 arm, 50ep)

Tre famiglie, tre comportamenti — **nessuna domina l'altra**:

| famiglia | val_data (FISICA) | NRMSE (parametri) | stabilità (grad max) |
|---|---|---|---|
| **BPTT champion** (`LS3_PEAK_R0_launch_d03`) | **0.1926** ✓ | 0.258 | transitorio a **1e15** (recupera) |
| **AdamW + decode** (P2) | ~0.213–0.218 | ~0.20 | ~1 (pulito) |
| **ProdigyEvent + decode** (PE) | 0.23–0.35 | **0.15–0.19** ✓ | ~1 |

- **Miglior EventProp sulla fisica**: `P1_lr5e3_t05` = **0.2095** (decode-off, NRMSE 0.304). EventProp NON
  batte il champion sulla fisica (~8% sopra) **ma è molto più stabile** (grad ~1 vs 1e15 del champion).
- **Ottimo operating point AdamW**: lr alto (5e-3/3e-3) + **target spettrale basso** (0.5–0.8). Trend
  monotòno: target più basso = meglio; lr più alto = meglio finché target resta basso. lr alto + target
  ≥1.2 **esplode**. lr ≤1e-3 inutili.
- **Champion config esatta** (da replicare come riferimento): Prodigy + `--scheduler custom_restart
  --restart_T0 12 --restart_decay 0.3 --restart_warmup_epochs 2 --prodigy_growth_rate inf
  --grad_clip none --cf_rank 8` + decode on. (Il BPTT_REF del BigSweep1 con `cosine_no_restart`+growth 1.05
  era SBAGLIATO → esplodeva.)

---

## 3. Cosa è stato ESCLUSO e perché (non ri-tentare senza motivo nuovo)

### 3a. Decode calibration — TENUTO (allenato end-to-end), buona leva
La variante EventProp non registrava `decode_offset`/`logit_tau` → i flag `--cf_init_bias_shift` /
`--cf_logit_tau_per_channel` erano **silenziosamente inefficaci**. Aggiunti (opt-in). Con decode-on allenato:
NRMSE per-canale molto migliore a ~parità di `val_data` (P1 decode-off NRMSE ~0.30 vs P2 decode-on ~0.20).
**Buon trade** (il core si adatta al decode in training). → si usa `--cf_init_bias_shift 1
--cf_logit_tau_per_channel 10.0,3.0,10.0,3.0,3.0`.

### 3b. ProdigyEvent loss-aware — ARCHIVIATO (non competitivo)
Plateau ~0.29 sulla fisica (vs AdamW 0.21); gli arm aggressivi esplodono. Con decode (BigSweep2) ha il
**miglior NRMSE (0.15) ma la PEGGIOR fisica (0.35)** — `PE_t05_gp0002` = NRMSE 0.152 / val_data 0.346. È la
prova plastica della **tensione NRMSE↔fisica**: identifica i parametri "bene" ma ricostruisce la dinamica
malissimo. **AdamW = ottimizzatore di produzione.**

### 3c. Path A — modulatore decode PER-ISTANZA (FiLM-lite) — FALLITO
Idea utente: I/O adattiva alla singola traiettoria (fast-weights/FiLM su statistica nuisance `|accel|`).
Probe oracolo prometteva −36/45% NRMSE. Ma il modulatore appreso (allenato sull'accel-loss) **ridistribuisce**
(T/b meglio, v0/a peggio), NRMSE medio +4%. Flag rimossi.

### 3d. Path B — refit decode sui parametri (LUT / globale) — ARCHIVIATO (trade catastrofico)
Refit post-hoc del decode sui parametri: NRMSE −32/45% (train→val disgiunto, no leakage) **MA degrada la
FISICA**: `data` (accel) +24%, `phys` (residuo) +60%. Validato con `scripts/path_b_validate.py`. Su modello
imperfetto **NRMSE e fedeltà-fisica sono in tensione**: o sei vicino ai parametri "veri" O ricostruisci
l'accel, non entrambi. Per un controllore ACC = "parametri più veri che guidano peggio" → **scartato**.
(Anche sbloccare il decode globale via `--learnable_decode` → stesso problema: allenato sull'accel non
raggiunge l'ottimo-parametri; il refit-floor ~0.099 è raggiungibile da qualunque core → è un problema di
OBIETTIVO, non un artefatto rimovibile.)

### 3e. Rank / neuroni morti — CHIARITI
Cap-scan (decode-on): rank 16 batte rank 8 (val 0.240 vs 0.250); rank effettivo scala col rank dato → **rank
8 era sotto-dimensionato, rank 16 in config** (da verificare se 24/32 aiutano in BigSweep3). Con decode-on
**0 neuroni morti** (i 4 di prima erano artefatto decode-off); `h64` non aiuta → la rete **non** è limitata
dalla width.

---

## 4. Studio dataset (impostato in BigSweep3)

**Osservazione (violin)**: alcuni parametri non coprono il range fisico. Causa trovata nel generatore: **s0 e
b NON sono mai jitterati** (restano ai preset di scenario), v0/a parziali. Coverage del train attuale vs
range fisico:

| param | range fisico | coperto | valori unici |
|---|---|---|---|
| v0 | [8, 45] | 75% | molti |
| T | [0.5, 2.5] | 75% | molti |
| **s0** | [1, 5] | **25%** | **3** |
| a | [0.3, 2.5] | 45% | parziale |
| **b** | [0.5, 3] | **40%** | **3** |

**Fix/leva**: flag `wide_params` in `data/generator.py` (opt-in) → campiona i 5 parametri uniformemente
sull'intero range (s0/b: 3→~70 valori). BigSweep3 confronta `narrow` (attuale) vs `wide` (1500) vs `widebig`
(3000) **sullo stesso wide-val** → risponde: dati più vari/abbondanti migliorano l'identificazione sul range
pieno (verso un "dataset perfetto"), o l'attuale basta?

---

## 5. BigSweep3 — studio esaustivo di chiusura (PUSHATO, da lanciare)

`EventProp_BigSweep3.ipynb` (commit `94d5e26`). **22 arm, 17 celle, 50ep**, metrica **PRIMARIA = val_data
(fisica)**, NRMSE secondaria. Best-first, **SKIP+RESUME** sul training, **ogni sezione d'analisi salta se
l'output esiste** (resiliente a crash multi-giorno). Tutto in `results/EventProp_BigSweep3/`.

**Arm — 22 totali** (= 9+1+3+2+3+3+1): core decode-ON `lr{5e-3,7e-3,1e-2} × target{0.4,0.5,0.6} × rank16`
(9) + tetto `lr1.5e-2` (1) + sweep `rank{8,24,32}` a lr7e3/t05 (3) + frontiera decode-OFF (2) + **multi-seed**
`lr7e3/t05/r16 × seed{1,2,3}` (3, chiude il caveat single-seed via flag `--seed`) + **DS** narrow/wide/widebig
(3) + **BPTT_REF** champion (1). Il **BPTT_REF di BigSweep3 usa la config champion CORRETTA** (verificato:
`custom_restart` T0 12 / decay 0.3 / growth inf / grad_clip none / rank 8 — NON il `cosine_no_restart`
sbagliato di BigSweep1). Il flag `wide_params` è stato smoke-testato (coverage s0/b: 3→~70 valori).

**Sezioni d'analisi (ognuna produce un png visivo + csv backup):**

| sezione | png | cosa comunica |
|---|---|---|
| DIAG | `heatmap.png` + `ranking.png` | val_data lr×target + ranking di tutti gli arm vs champion |
| FULLLOSS | `fullloss.png` | barre impilate dei 5 componenti PINN per-arm |
| PARETO | `pareto.png` | scatter val_data vs NRMSE (la tensione) |
| RANKCURVE | `rankcurve.png` | val_data vs rank + rank effettivo → plateau? |
| SEEDVAR | `seedvar.png` | varianza multi-seed (robustezza) |
| PERREGIME | `perregime.png` | val_data + NRMSE per scenario (dove sbaglia) |
| DIAGNOSTICS | `diagnostics.png` | raggio spettrale, spike rate, neuroni morti, rank effettivo |
| VALIDATE | `validation.png` | Path B refit: NRMSE giù **ma** data/phys su (trade) |
| CLOSEDLOOP | `closedloop.png` | **sicurezza**: param identificati vs oracolo (collisioni, min-gap) |
| DATASET | `coverage.png` + `dataset.png` | coverage param + narrow/wide/widebig sul range pieno |
| SYNTHESIS | `synthesis.png` | best EventProp vs champion (consolidato) |

I 13 png + csv si pushano via la cella PUSH_DIAG (glob `bigsweep3_*`). **VALIDATE resta nella cartella dello
studio** (non in `evaluate/`, riservata alle validazioni dei champion).

---

## 6. METODOLOGIA / pratiche da seguire (NON violare)

1. **È una PINN**: la loss totale ha 5 componenti (`data, phys, ou, bc, sr`). La metrica **PRIMARIA è
   `val_data`** (ricostruzione accel = fisica); l'**NRMSE per-canale è una LENTE diagnostica, NON il
   bersaglio di training**. Mai ottimizzare/giudicare sull'NRMSE da solo — è catastrofico per safety
   (il caso PE/Path B lo dimostra).
2. **Validare sul SET COMPLETO**: ogni modifica decode/architettura si giudica su loss completa **+
   closed-loop** (sicurezza: collisioni/min-gap coi parametri identificati vs oracolo), non su una lente.
3. **Niente workaround per la stabilità**: i clamp sono failsafe, non meccanismo di stabilità (questa la dà
   il vincolo spettrale C11). Stesso principio delle lezioni Prodigy: trovare il regime CLEAN, non cappare.
4. **Tutti i flag nuovi opt-in / backward-compat** (default = comportamento attuale), come la catena C8–C13.
5. **Risultati nelle loro cartelle**: ogni studio in `results/<NomeStudio>/`; `evaluate/` è riservata alle
   validazioni dei champion. Push **per-arm** appena finito. Analisi **SKIP-se-fatta** (idempotente).
6. **Multi-seed** per le affermazioni di robustezza (flag `--seed`); il single-seed è un caveat noto.
7. **Risultati visivi**: ogni studio deve produrre png interpretabili dall'umano (non solo csv).

---

## 7. Infrastruttura

- **Notebook**: `EventProp_Spectral_Sweep.ipynb`, `EventProp_BigSweep.ipynb`, `EventProp_BigSweep2.ipynb`
  (conclusi), `EventProp_BigSweep3.ipynb` (da lanciare). Generati da `scripts/_build_eventprop_*_notebook.py`.
- **Tooling analisi** (`scripts/`): `path_b_validate.py` (refit vs loss-completa+closed-loop),
  `closed_loop_identify.py` (sicurezza coi param identificati — funziona per EventProp via
  `simulate(None, id_params)` perché la variante è sequence-only e non fa forward_step per-step),
  `decode_headroom_probe.py`, `decode_lut_calibrate.py` (Path B, archiviato; scrive
  `results/decode_lut_*.json` SOLO se lanciato a mano).
- **scout.sh**: run spuria → `results/_scratch/<tag>`.
- **Cache dati**: `data/cache_1500_launch_cut0.0_ou0.0.pt` (gitignored, rigenerabile); le cache DS
  (`data/cache_ds_*.pt`) si autogenerano alla prima cella del BigSweep3 (gitignored).
- **Diagnostica permanente nel training_log**: 5 componenti loss (`val_data/phys/ou/bc/sr`), NRMSE per-canale,
  `rec_spectral_radius`, `spike_rate`, `marginal_frac`, `mean_vth_at_spike`, pred_mean/intra_std per-canale.
- **Flag EventProp (opt-in)**: `--eventprop_lambda_spectral/_spectral_target` (C11), `--cf_init_bias_shift
  --cf_logit_tau_per_channel` (decode), `--cf_rank`, `--seed`, `--eventprop_full_threshold_adjoint` (C13, off),
  `--eventprop_thresh_jump_init/_alpha_f`, clamp; ProdigyEvent `--prodigy_loss_aware/_po_*`; generatore
  `wide_params` (via notebook).
- **Backup pre-pulizia workaround**: branch `backup/pre-cleanup-db592b7`.

---

## 8. Storico per-canale (riferimento)

Decode OFF vs ON (best-Adam, 10ep) — la conferma che il decode de-satura T/s0:

| canale | DEC_OFF | DEC_ON | champion (50ep) |
|---|---|---|---|
| v0 | 0.445 | 0.242 | 0.240 |
| T | 0.206 | 0.140 | 0.276 |
| s0 | 0.323 | 0.101 | 0.172 |
| a | 0.282 | 0.227 | 0.284 |
| b | 0.310 | 0.173 | 0.316 |
| val_min | 0.2563 | 0.2374 | 0.1926 |

---

## 9. Post-BigSweep3 — studio combinato + Evaluate v3 (2026-06-30)

### 9.1 Verdetto BigSweep3 (CHIUSO)
22 arm, 50ep. **Best EventProp** `A_lr1e2_t06_r16` val_data **0.2031** (gap **+5.5%** vs champion 0.1926; era
+8.8% in BS1/2). **rank8 sufficiente** (val_data peggiora monotòno col rank → ideale FPGA). **decode-ON
essenziale** (decode-OFF: val 0.217-0.231, NRMSE 0.30-0.38). **Multi-seed std 0.0011** → caveat single-seed
CHIUSO. **Sicurezza closed-loop**: 0 collisioni, min-gap preservato per champion ed EventProp. Dataset
full-range (`wide`/`widebig`): l'identificazione sul range fisico pieno resta dura (phys residuo domina) →
FUTURE_WORK, non un quick-win.

### 9.2 Studio combinato (`results/EventProp_Study/combined/`, 36 figure + INDEX.md)
Aggrega i **102 arm** delle 5 campagne (Study/Spectral/BigSweep/BS2/BS3) su **val-set comune**
(`cache_1500_launch`) → metrica confrontabile. **29 figure Stage-1** (dai `training_log.csv`) + **7 figure
Stage-2** (dai checkpoint, 100/100 arm). Builder: `scripts/_build_eventprop_study_combined.py` (Stage-1, locale)
+ `scripts/_eventprop_combined_ckpt_pass.py` (Stage-2, gira su Azure, resiliente+manifest). Backbone:
`combined_arm_index.csv` + `combined_epoch_long.csv`. **Findings chiave:**
- **La FISICA (val_data) governa la sicurezza, non l'NRMSE** (F24): arm a fisica migliore → min-gap vicino
  all'oracolo (12.6 m). **ProdigyEvent consuma −2.45 m di margine di gap** (vs −0.3/−0.5 AdamW, champion +0.25):
  paradosso "NRMSE bassa ≠ guida sicura" **confermato in closed-loop** (F38).
- Meccanismo stabilità (F12): raggio spettrale champion sale a **~22**, EventProp vincolato a **~0.5** (C11);
  `is_inf_grad` SOLO nella famiglia BPTT_champion, mai EventProp (F35).
- `lr` è la leva dominante (F32, |corr| 0.71). Champion: **11 neuroni morti** / eff_rank 1.75; EventProp: **0 morti**.

### 9.3 Evaluate v3 — upgrade 6-tier (`document/EVALUATE_UPGRADE.md`; tutto opt-in/backward-compat; 21 test verdi)
Da validazione *data-driven* a *physics/network-driven*. **T0** reporting (distribuzioni/Wilson/CI-bootstrap/
per-scenario+worst-case/flag-ISO/intra_std + **metriche-sicurezza CONTINUE** `brake_margin_min` con segno e
`impact_dv`, che NON saturano come collision_rate) · **T1** scenari di coda (cut_out/static/panic-9/aggressive)
+ soglie DRAC/TTC/CPI + efficienza + energia + curva-di-rottura · **T2** plant fisico L4 (lag attuatore/μ/
pendenza/drag) + canale V2X L3 (pdr/Gilbert/latenza/jitter/OU/AoI/chattering) dentro `simulate(plant,channel)` ·
**T3** string stability **plotone** (catena N, |Γ(ω)| via chirp, L2/Linf) · **T4** identificabilità **FIM**/
equifinalità/excitation/causal/calibrazione/reachability/naturalisticità · **T5** quantizzazione **FPGA** (Qm.n/po2).
File: `utils/closed_loop_eval.py`, `scripts/closed_loop_identify.py`, `utils/identifiability.py`,
`utils/quantize.py`, `tests/test_eval_tier0.py`.

### 9.4 Notebook champion v3 — "TURTLE POWER!!!" (`Eval_v3_TURTLE_POWER.ipynb`)
4 champion + oracolo, evaluate 6-tier completo, **figure + csv per ogni dimensione**, output in
`results/evaluate/v3_TURTLE_POWER!!!/` (00_Scorecard, 01_Accuracy … 09_Trajectories + README.md). Champion:

| alias | tag checkpoint | variant | colore | carattere |
|---|---|---|---|---|
| Master Splinter | *oracolo* (param veri) | — | grigio | riferimento |
| Raffaello | `R33_C2_A1_T12_fix` | baseline | rosso | Prodigy, aggressivo |
| Leonardo | `LS3_PEAK_R0_launch_d03` | baseline | azzurro | champion BPTT, conservativo |
| Donatello | `PE_t05_gp0002` | eventprop_alif_full | viola | best-NRMSE (0.152) |
| Michelangelo | `A_lr1e2_t06_r16` | eventprop_alif_full | arancione | best-Adam (0.2031) |

**Loader robusto**: variante dedotta dallo **schema chiavi** del checkpoint (`layer_out.fc_weight`=baseline vs
`layer_out.weight`=eventprop) + **validazione readout** (se non carica → scarta, niente output random silenzioso);
rank/hidden inferiti da `rec_U`. **Energia**: fonte-spike uniforme `forward_sequence_with_stats` (nJ per tutti;
raster per-neurone vero solo per i baseline). **Resiliente**: `resilient` per-cella + `timeout:-1` nei metadata
+ csv-salvato-per-ultimo + auto-push. Verificato: 13 celle compilano, smoke-test su cache reale, review
adversariale a 3 agenti.

> **⚠️ BUG STORICO da correggere**: il ckpt-pass dello Stadio-2 combinato (§9.2) NON aveva la fix
> schema-detection del loader → ha caricato i **baseline** (famiglia BPTT_champion: BPTT_REF, ecc.) come
> `eventprop_alif_full` → **readout random silenzioso** → i risultati closed-loop del *champion* nelle figure
> F24/F38 sono **artefatti** (gli arm EventProp, la maggioranza, sono corretti). Fix: portare lo schema-detection
> in `_eventprop_combined_ckpt_pass.py::build_and_load` e ri-lanciare i soli arm baseline su Azure.
