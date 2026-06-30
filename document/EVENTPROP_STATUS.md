# EventProp — Stato attuale + punto di ripresa (2026-06-26)

Branch `EventProp_Study`. **Questo è il documento-master di ripresa dello studio EventProp**: dove siamo,
cosa funziona, cosa è stato escluso e perché, le pratiche da seguire, e come continuare.

---

## 0. COME RIPRENDERE (leggere prima questo)

**Progetto CF_FSNN**: una Spiking Neural Network (ALIF + EventProp) che, osservata una traiettoria di
car-following, **identifica i 5 parametri ACC-IIDM** `[v0, T, s0, a, b]`. Target finale: deploy su FPGA
PYNQ-Z1 (pesi quantizzati po2). Architettura e fisica: vedi `document/HOW_IT_WORKS_v2.md` + `GLOSSARY.md`.

**Stato in una riga**: EventProp è stato reso stabile/convergente e mappato a fondo (BigSweep1+2). È su un
**fronte di Pareto** con il BPTT champion (lui vince la fisica, EventProp+decode vince i parametri). Lo
**studio si chiude (verosimilmente) con BigSweep3**, un notebook esaustivo già pushato e pronto da lanciare.

**Per continuare:**
1. `git pull origin EventProp_Study`.
2. Se `results/EventProp_BigSweep3/` NON ha i risultati → il BigSweep3 va ancora lanciato su Azure
   (`jupyter nbconvert --to notebook --execute --inplace EventProp_BigSweep3.ipynb`), ~24h.
3. Se i risultati ci sono → analizzarli **secondo la metodologia in §6** (fisica primaria, non NRMSE),
   leggendo le sezioni/png in `results/EventProp_BigSweep3/` (vedi §5 per cosa contengono).
4. Verdetto di chiusura: confronto Pareto vs champion su fisica + parametri + sicurezza closed-loop.
   La chiusura è una **decisione dell'utente** sul quadro complessivo (non c'è soglia go/no-go hardcoded);
   direzione post-chiusura (quantizzazione/deploy FPGA, multi-seed esteso) in `document/FUTURE_WORK.md`.

**Workflow operativo**: il training gira **su Azure** (macchina "sandokan", conda env `azureml_py38`,
Python 3.10), **lanciato dall'utente** (l'assistente prepara i notebook e analizza i risultati pullati, non
ha accesso diretto ad Azure). In locale (Windows) si fa pull, analisi e build notebook. Ogni arm si **pusha
appena finito**; ogni sezione d'analisi **salta se l'output esiste già** (resiliente a crash multi-giorno).

> **Stato LIVE del job Azure NON è nei documenti** (è runtime). L'assenza di `results/EventProp_BigSweep3/`
> in locale NON distingue "mai lanciato" da "in corso senza arm completati" → **chiedere all'utente** lo stato
> reale (mai lanciato / in corso / crashato / completato) prima di agire. È l'unica cosa che i doc non danno.

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
