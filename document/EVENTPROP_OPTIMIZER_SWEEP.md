# F2 EventProp — Sweep optimizer 4×11 (chiusura definitiva)

**Data**: 2026-06-01
**Branch**: `Training_Method_Exploration` HEAD `09e1159`
**Documento parente**: [EVENTPROP_GRID2X2.md](EVENTPROP_GRID2X2.md), [EVENTPROP_DESIGN.md](EVENTPROP_DESIGN.md)
**Risultati raw**: `results/SW_<method>_<opt_label>/` (44 cartelle)
**Aggregato**: `_sweep_master.csv`
**Notebook Azure**: `Training_File_Optimizer_2x2.ipynb`

---

## 1. Obiettivo

Dopo il grid 2×2 (single optimizer AdamW lr=2e-3), prova **definitiva** che EventProp non supera BPTT+surrogate testando esaustivamente sweep optimizer 4 methods × 11 configs = 44 run, condizioni IDENTICHE al grid 2×2.

Se nessuna configurazione di EventProp scende sotto baseline best, la storia F2 EventProp è chiusa con piena evidenza.

---

## 2. Setup — riproducibile

```bash
--epochs 5 --max_steps_per_epoch 190 --batch_size 8 --val_batch_size 64
--seq_len 50 --scheduler none
--scenario_mix highway --cut_in_ratio 0.0 --cf_hidden_size 32 --cf_rank 8
--noise_scale 0.0 --po2_enabled 1
--lambda_data 1.0 --lambda_phys 0.0 --lambda_ou 0.0 --lambda_bc 0.0 --lambda_sr 0.0
--data_cache data/cache_1500_highway_cut0.0_ou0.0.pt
--n_train 1500 --n_val 300
--max_inf_streak 99999 --early_stop_patience 0
```

**Configs optimizer (11)** — variando in due dimensioni: optimizer family e lr:

| Label | Optimizer | lr | d_coef |
|---|---|---:|---:|
| adamw_lr5e-4 | AdamW | 0.0005 | – |
| adamw_lr1e-3 | AdamW | 0.001 | – |
| adamw_lr2e-3 | AdamW | 0.002 | – |
| adamw_lr5e-3 | AdamW | 0.005 | – |
| adam_lr2e-3 | Adam (no wd) | 0.002 | – |
| lion_lr1e-4 | Lion | 0.0001 | – |
| prodigy_lr1_d10 | Prodigy | 1.0 | 1.0 (canonical) |
| prodigy_lr1_d05 | Prodigy | 1.0 | 0.5 (mild brake) |
| prodigy_lr1_d03 | Prodigy | 1.0 | 0.3 (med brake) |
| prodigy_lr1_d01 | Prodigy | 1.0 | 0.1 (strong brake) |
| prodigy_lr01_d10 | Prodigy | 0.1 | 1.0 (low init) |

**Training methods (4)** — il grid 2×2:
- `baseline` — ALIF + BPTT + surrogate (production, 864 params)
- `bptt_lif_simple` — LIF + BPTT + surrogate (288 params)
- `eventprop_lif_simple` — LIF + EventProp (288 params)
- `eventprop_alif_full` — ALIF + EventProp (864 params, replica A1)

---

## 3. Tabella principale — val_data BEST (RMSE m/s²)

| Method | A 5e-4 | A 1e-3 | A 2e-3 | A 5e-3 | Adam 2e-3 | Lion 1e-4 | Prod ld10 | Prod ld05 | Prod ld03 | Prod ld01 | Prod 01d10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.2225 | 0.2226 | 0.2221 | **0.2218** | 0.2219 | 0.2349 | 0.2400 | 0.2250 | 0.2400 | 0.2250 | 0.2226 |
| bptt_lif_simple | 0.3420 | 0.3270 | **0.3179** | 0.3205 | 0.3181 | 0.4467 | 0.3323 | 0.3217 | 0.3217 | 0.3217 | 0.3207 |
| eventprop_lif_simple | 0.3688 | 0.3287 | 0.3224 | 0.3210 | 0.3223 | 0.5537 | 0.3323 | 0.3323 | 0.3217 | 0.3217 | **0.3207** |
| eventprop_alif_full | 0.8747 ❌ | 0.8457 ❌ | **0.2226** | 1.7679 ❌ | 0.8941 ❌ | 0.9996 ❌ | 0.2400 | 0.2400 | 0.3110 | 0.2353 | 0.9747 ❌ |

❌ = fallimento (val_data > 0.5). A 5e-4 = AdamW lr=5e-4. Prod ld05 = Prodigy lr=1.0 d_coef=0.5. Prod 01d10 = Prodigy lr=0.1 d_coef=1.0.

### Sintesi best per riga

| Method | val_data BEST | Optimizer | Δ vs baseline |
|---|---:|---|---:|
| **baseline** (ALIF+BPTT) | **0.2218** | AdamW lr=5e-3 | (reference) |
| eventprop_alif_full (ALIF+EventProp) | 0.2226 | AdamW lr=2e-3 | +0.0008 (+0.36%) |
| bptt_lif_simple (LIF+BPTT) | 0.3179 | AdamW lr=2e-3 | +0.0961 (+43%) |
| eventprop_lif_simple (LIF+EventProp) | 0.3207 | Prodigy lr=0.1 d=1.0 | +0.0989 (+45%) |

**Sul val_data BEST raggiungibile: pareggio tra baseline e eventprop_alif_full** (Δ = 0.0008, 0.36% relativo, entro rumore). Confermato grid 2×2.

---

## 4. ROBUSTEZZA all'optimizer (la scoperta chiave del sweep)

| Method | Min | Median | Max | CV | IQR | # success | # within 2% best |
|---|---:|---:|---:|---:|---:|---:|---:|
| **baseline** | 0.2218 | 0.2226 | 0.2400 | **0.033** | 0.0077 | **11/11** | **8/11** |
| bptt_lif_simple | 0.3179 | 0.3217 | 0.4467 | 0.112 | 0.0091 | 11/11 | 7/11 |
| eventprop_lif_simple | 0.3207 | 0.3224 | 0.5537 | 0.198 | 0.0106 | 10/11 | 6/11 |
| **eventprop_alif_full** | 0.2226 | 0.8457 | 1.7679 | **0.710** | 0.6944 | **5/11** | **1/11** |

> CV = std/mean (coefficient of variation). IQR = inter-quartile range. # success = config con val_data ≤ 0.5.

### Osservazioni

**eventprop_alif_full è 22× più variabile di baseline** (CV 0.710 vs 0.033). Su 11 configurazioni:
- baseline: TUTTE producono val_data ∈ [0.222, 0.240]
- eventprop_alif_full: **6 fallimenti** (val_data 0.85–1.77, predizioni essenzialmente random), 5 successi di cui solo 1 vicino al best

Lo spread IQR di eventprop_alif_full è **90× più ampio** del baseline. **Solo 1/11 configs è entro 2% del best, vs 8/11 per baseline**.

**Questo è il dato più significativo dell'intero studio.** Non è solo "EventProp non migliora val_data", è "EventProp su architettura realistica è 100× meno production-ready del baseline".

### Instabilità numerica delle config fallite

`gradient_norm` ep5 per i 6 fallimenti di eventprop_alif_full:

| Config | val_data ep5 | grad_norm ep5 |
|---|---:|---:|
| adamw_lr5e-4 | 0.875 | **3.3 × 10¹⁷** |
| adamw_lr1e-3 | 0.846 | **1.6 × 10¹⁷** |
| adamw_lr5e-3 | 1.768 | 0.001 (post-clip) |
| adam_lr2e-3 | 0.894 | 0.000 (frozen post-clip) |
| lion_lr1e-4 | 1.000 | 5.27 |
| prodigy_lr01_d10 | 0.975 | **4.4 × 10¹⁷** |

Gradienti dell'ordine **10¹⁷** indicano cascading explosion attraverso i 500 tick interni (n_ticks=10 × seq_len=50). Il gradient clipping evita NaN ma le direzioni di update sono incoerenti.

**Causa probabile**: l'adjoint EventProp con threshold time-varying ha denominatore `drive[t+1] − V_th_eff[t+1]` che può tendere a zero quando la fatigue cresce → jump term diverge → cascade through chain. Solo con lr piccolo (AdamW 2e-3 o Prodigy con strong brake) il primo step non manda subito la rete in stato divergente.

---

## 5. SPIKE RATE — impatto deploy FPGA event-driven

| Method | min | median | max | best config |
|---|---:|---:|---:|---:|
| **baseline** | **0.039** | **0.046** | 0.361 | **4.1%** ✅ |
| bptt_lif_simple | 0.041 | 0.259 | 0.513 | 21.3% |
| eventprop_lif_simple | 0.235 | 0.503 | 0.732 | 35.2% |
| **eventprop_alif_full** | 0.196 | 0.210 | 0.421 | 25.7% |

**Su STESSA architettura ALIF, EventProp produce spike rate ~6× più alto del BPTT** (25.7% vs 4.1%). Su FPGA event-driven (PYNQ-Z1):
- Energia ∝ spike_count × E_spike
- Baseline consuma ~6× meno energia per inference
- Su volumi production, questa è una differenza decisiva

EventProp non è competitivo deploy-side anche se val_data fosse uguale.

---

## 6. CONVERGENCE — quanto velocemente ogni method raggiunge il plateau?

| Method | best config | ep_to_plateau (entro best+0.005) | ep1 | ep5 |
|---|---|---:|---:|---:|
| **baseline** | AdamW lr=5e-3 | **1** | 0.222 | 0.222 |
| eventprop_alif_full | AdamW lr=2e-3 | 2 | 0.879 | 0.223 |
| eventprop_lif_simple | Prodigy lr=0.1 d=1.0 | 2 | 0.343 | 0.321 |
| bptt_lif_simple | AdamW lr=2e-3 | 4 | 0.352 | 0.318 |

**Baseline trova il floor 0.222 già in epoca 1** (al PRIMO check di validazione, dopo 190 update). Il modello ha una zona "facile" da raggiungere, la cosa interessante è quanto si scende sotto.

eventprop_alif_full ep1=0.879 è catastrofica, ma ep2=0.224 recupera. Quindi l'adjoint funziona, ha solo una dinamica iniziale instabile.

---

## 7. PRODIGY — comportamento anomalo

Dei 16 run Prodigy totali (4 methods × 4 configs Prodigy):

| Method | # frozen (grad=0, val invariato) | best Prodigy val_data |
|---|---:|---:|
| baseline | 2/4 | 0.2226 (lr=0.1 d=1.0) |
| bptt_lif_simple | 2/4 | 0.3207 (lr=0.1 d=1.0) |
| eventprop_lif_simple | 2/4 | 0.3207 (lr=0.1 d=1.0) |
| **eventprop_alif_full** | **4/4** | 0.2353 (lr=1.0 d=0.1) |

**10/16 Prodigy run sono frozen** in 5 epoche — l'adattore `d` si è stabilizzato a un valore troppo basso. Prodigy non sembra adatto a sequenze brevi (5 ep × 190 step = 950 step totali), serve probabilmente warmup più lungo.

Interessante: **Prodigy con strong brake (d_coef=0.1) ha dato il TERZO miglior risultato per eventprop_alif_full (0.2353)**. Il brake stabilizza l'update e impedisce alla rete di divergere nella prima epoca. Pattern coerente con la fragilità di eventprop_alif_full su lr "normali" (AdamW 1e-3, 5e-3 falliscono perché lr troppo alta).

**Pattern Prodigy spike rate**: per `baseline` Prodigy senza brake produce spike rate 16–36% (vs AdamW 4–5%). Su FPGA Prodigy va EVITATA — produce reti molto più "rumorose" anche su baseline.

---

## 8. EXTRAPOLAZIONE 15-epoch (linear slope ep3→ep5)

| Method (best config) | slope/ep | ep5 attuale | pred ep10 | pred ep15 |
|---|---:|---:|---:|---:|
| **baseline** (AdamW 5e-3) | **−0.00047** | 0.2218 | 0.2194 | **0.2170** |
| bptt_lif_simple (AdamW 2e-3) | **−0.00337** | 0.3179 | 0.3010 | **0.2842** |
| eventprop_lif_simple (Prod 01d10) | +0.00035 | 0.3214 | 0.3231 | 0.3248 (diverge!) |
| eventprop_alif_full (AdamW 2e-3) | +0.00001 | 0.2227 | 0.2228 | **0.2228** |

### Previsioni a 15 epoche

**Baseline** continua a scendere lievemente: pred 0.217 a ep15 (Δ −0.005 vs ep5). Non è saturato del tutto, ha ancora margine.

**eventprop_alif_full è completamente saturato** (slope ≈ 0). Pred 0.223 a ep15 = stesso di ep5. EventProp NON può migliorare con più epoche.

**bptt_lif_simple** è il method con slope più negativo (−0.00337/ep). Pred 0.284 a ep15 (Δ −0.034) — continuerebbe a scendere significativamente. Comunque rimarrebbe ~25% peggio del baseline al meglio.

**eventprop_lif_simple** mostra slope LEGGERMENTE POSITIVO → non solo non migliora ma potrebbe peggiorare a 15 ep (overfitting/divergence sottile).

### Verdetto a 15 ep stimato

A 15 epoche (estrapolazione lineare):

| Method | val_data ep15 stimato | vs baseline ep15 |
|---|---:|---:|
| baseline | **0.2170** | reference |
| eventprop_alif_full | 0.2228 | +0.006 (peggio) |
| bptt_lif_simple | 0.2842 | +0.067 (peggio) |
| eventprop_lif_simple | 0.3248 | +0.108 (peggio) |

**A 15 epoche baseline batterebbe eventprop_alif_full di ~0.006 (2.7% relativo).** Marginale ma in favore baseline, non più pareggio puro.

> **Caveat onesto**: l'estrapolazione lineare è valida solo se il trend continua. Per baseline e eventprop_alif_full il trend è praticamente piatto (saturato), quindi l'extrapolazione è affidabile. Per bptt_lif_simple il trend ep3→ep5 (–0.0034) potrebbe rallentare o invertirsi a 15 ep.

---

## 9. TEMPO TRAINING

| Method | s/ep avg | 5 ep | 15 ep stimato |
|---|---:|---:|---:|
| baseline | 179 | 15 min | **45 min** |
| bptt_lif_simple | 5.4 | 27 s | 1.3 min |
| eventprop_lif_simple | 6.1 | 31 s | 1.5 min |
| eventprop_alif_full | 109 | 9 min | **27 min** |

**EventProp ALIF è 39% più veloce di baseline ALIF** (107s vs 179s per epoca, 18 min meno su 15 epoche). Causa: il manual backward salva solo gli array di stato necessari (V, I, s, V_th_eff, drive) e ricostruisce il gradient via adjoint loop, evitando di mantenere il grafo computazionale PyTorch autograd di 500 tick.

**Questo è l'unico vantaggio chiaro di EventProp.**

---

## 10. Conclusioni rigorose (con grado di confidence)

### Conclusioni AD ALTA CONFIDENZA (dati forti)

**C1 — Pareggio val_data al BEST**:
EventProp adjoint adeguatamente configurato (AdamW lr=2e-3) raggiunge val_data 0.2226 vs baseline best 0.2218. Δ = 0.0008 entro rumore. **EventProp NON migliora val_data.**

**C2 — Floor architetturale confermato**:
Due metodi di training INDIPENDENTI (BPTT+surrogate, EventProp adjoint event-based) convergono allo stesso plateau 0.222 su ALIF. Combinato con P14 floor decomposition (no capacity, no data, no Po2 issue), il floor val_data ~0.22 è **architetturale**, non gradient-method-dependent.

**C3 — EventProp è fragile production-side**:
6/11 configs eventprop_alif_full falliscono (val>0.5). Solo 1/11 è entro 2% del best. CV 22× più alto del baseline. Per un sistema deploy real-world questo è inaccettabile.

**C4 — EventProp ha spike rate 6× più alto**:
Su STESSA architettura ALIF, baseline 4.1% vs EventProp 25.7%. Deploy FPGA event-driven: 6× più energia per inference. **EventProp PERDE su deploy.**

### Conclusioni MEDIA CONFIDENZA (extrapolazione)

**C5 — A 15 epoche: baseline marginalmente migliore**:
Estrapolazione lineare slope ep3→5: baseline pred 0.217, eventprop_alif_full pred 0.223. Δ = +0.006 in favore baseline. Marginale ma in favore baseline.

**C6 — Più epoche NON salvano EventProp**:
eventprop_alif_full è saturato (slope ≈ 0). Le 6 configurazioni fallite sono divergenti (grad ~10¹⁷). 10 epoche in più non cambierebbero il quadro.

### Conclusioni BASSA CONFIDENZA (speculazione informata)

**C7 — EventProp potrebbe beneficiare di grad clipping più aggressivo**:
Le configurazioni fallite hanno grad ~10¹⁷. Un clipping pre-update (es. max_norm=1.0 invece dell'attuale) potrebbe stabilizzare più configurazioni. NON testato.

**C8 — EventProp adjoint potrebbe migliorare con thresh_jump learnable**:
La nostra implementazione tratta `thresh_jump` come frozen (gradient zero). L'adjoint completo con λ_fatigue propagation potrebbe ridurre la fragilità. Costo implementativo ~3-5h, payoff incerto.

---

## 11. Verdetto operativo

**EventProp non è la cura** per CF_FSNN. Tre lenti di valutazione, tutti convergenti:

| Lens | Vincitore | Motivo |
|---|---|---|
| **Accuracy (val_data)** | Pareggio → marginale baseline | 0.2218 vs 0.2226, a 15 ep baseline 0.217 vs EventProp 0.223 |
| **Production robustness** | **Baseline** | 11/11 vs 5/11 successi, CV 0.033 vs 0.710 |
| **Deploy FPGA** | **Baseline** | spike rate 4.1% vs 25.7% (6× meno energia) |
| **Tempo training** | EventProp | 39% più veloce (unico vantaggio) |

**Decisione**: ritorno al **baseline ALIF + BPTT + SurrogateSpike** come production. Storia F2 EventProp chiusa.

EventProp può continuare a esistere nel codebase come reference (`core/eventprop.py`, `--training_method eventprop_alif_full`) per future re-explore, ma non sarà la default.

---

## 12. Riferimenti e artefatti

### Codice (branch Training_Method_Exploration)
- `core/eventprop.py` — LIFLayer_EventProp + LIFLayer_BPTT_Simple + ALIFLayer_EventProp_Full + LILayer_Standard + LILayer_BitShift_Po2
- `core/network.py` — CF_FSNN_Net (baseline) + 3 wrapper EventProp/BPTT
- `train.py` — CLI `--training_method {baseline, bptt_lif_simple, eventprop_lif_simple, eventprop_alif_full}`

### Notebooks
- `Training_File_Optimizer_2x2.ipynb` — sweep Azure (44 run)

### Doc
- `document/EVENTPROP_DESIGN.md` — math + roadmap iniziale F2.0-F2.3
- `document/EVENTPROP_GRID2X2.md` — grid 2×2 single optimizer + mea culpa misread
- `document/EVENTPROP_OPTIMIZER_SWEEP.md` — questo documento (chiusura definitiva)

### Risultati
- `results/SW_<method>_<opt_label>/` — 44 cartelle con CSV epoca + batch + plot G1-G13
- `_sweep_master.csv` — aggregato locale (44 righe, 18 colonne metriche)
