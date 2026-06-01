# EventProp vs BPTT — Ablation Grid 2×2

**Data**: 2026-06-01
**Branch**: `Training_Method_Exploration` HEAD post-cleanup
**Documento parente**: [EVENTPROP_DESIGN.md](EVENTPROP_DESIGN.md)
**Scopo**: confronto rigoroso 2 architetture × 2 training methods con condizioni IDENTICHE per stabilire se EventProp adjoint event-based offre miglioramenti vs BPTT+surrogate-gradient sull'architettura A1.

---

## 1. Setup — condizioni FAIR identiche per tutti i run

```bash
--epochs 5 --max_steps_per_epoch 190 --batch_size 8 --val_batch_size 64
--seq_len 50 --scheduler none --lr 2e-3 --optimizer adamw
--scenario_mix highway --cut_in_ratio 0.0 --cf_hidden_size 32 --cf_rank 8
--noise_scale 0.0 --po2_enabled 1
--lambda_data 1.0 --lambda_phys 0.0 --lambda_ou 0.0 --lambda_bc 0.0 --lambda_sr 0.0
--data_cache data/cache_1500_highway_cut0.0_ou0.0.pt
--n_train 1500 --n_val 300 --max_inf_streak 99999 --early_stop_patience 0
```

**Punti chiave del setup**:
- **`--scheduler none`** lr fissa 2e-3 (no OneCycle cool-down che falsava confronti precedenti)
- **Solo `lambda_data=1`**: misura PURA della capacità di predire l'accelerazione (no PINN multi-obj)
- **`po2_enabled=1`** (deploy-realistic): match condizioni produzione baseline
- **5 epoche** sufficienti perché tutti i metodi raggiungono il plateau entro 3 epoche

---

## 2. Architetture testate (2×2 grid)

| | **BPTT + SurrogateSpike** (production) | **EventProp adjoint** (sperimentale) |
|---|---|---|
| **ALIF (864 params, full A1)** | `baseline` (CF_FSNN_Net) | `eventprop_alif_full` (CF_FSNN_Net_EventProp_Full) |
| **LIF (288 params, simple)** | `bptt_lif_simple` (CF_FSNN_Net_BPTT_LIF_Simple) | `eventprop_lif_simple` (CF_FSNN_Net_EventProp_LIF_Simple) |

### Dettaglio architetturale "ALIF (864 params, full)"
- `fc_weight` (32×4=128) + `rec_U` (32×8=256) + `rec_V` (8×32=256)
  + `base_threshold` (32) + `thresh_jump` (32) + `W_out` (5×32=160) = **864 params**
- Po2 quantization su TUTTI i pesi (FPGA-deploy)
- `max_delay=6` delayed synapses (deque ring buffer)
- `TICKS_PER_STEP=10` internal ticks per sequence step (500 tick totali)
- Bit-shift leak α_m = 7/8 (= V/8 hardware)
- Adaptive threshold ALIF: V_th_eff = base_th + fatigue.clamp(0)
- Soft reset V -= s · V_th_eff
- Low-rank recurrence rec_U @ rec_V

### Dettaglio architetturale "LIF (288 params, simple)"
- `weight` (32×4=128) + `W_out` (5×32=160) = **288 params**
- NO Po2, NO delays, NO recurrence, NO adaptive threshold
- Synaptic current I separato (τ_s filter)
- Hard threshold V_th=1.0 fissa, hard reset V *= (1−s)
- n_ticks=1 (no internal expansion)

**Per ogni RIGA del grid, l'unica differenza è il training method** (BPTT+surrogate vs EventProp adjoint). Stesso modello, stesso forward, stessi hyperparameters di rete.

---

## 3. Risultati — val_data (RMSE m/s² su accelerazione)

### Tabella principale (val_data ep5)

| | **BPTT + surrogate** | **EventProp** | Δ (EventProp − BPTT) |
|---|---:|---:|---:|
| **ALIF (864 params)** | **0.2233** | 0.2239 | **+0.0006** (≈ pareggio) |
| **LIF (288 params)** | **0.3203** | 0.3226 | **+0.0023** (≈ pareggio) |
| **Δ (ALIF − LIF)** | **−0.0970** (−30%) | **−0.0987** (−31%) | — |

**Numeri verificati direttamente dal CSV** (colonna 9 `val_data`, sqrt(mean(masked squared error))).

### Trajectory completa val_data per epoca

```
Ep | baseline (ALIF+BPTT) | bptt_lif | eventprop_lif | eventprop_alif_full
 1 |       0.2264          |  0.3522  |    0.3814     |       0.8785
 2 |       0.2226          |  0.3301  |    0.3474     |       0.2245
 3 |       0.2224          |  0.3250  |    0.3313     |       0.2228
 4 |       0.2225          |  0.3213  |    0.3243     |       0.2228
 5 |       0.2233          |  0.3203  |    0.3226     |       0.2239
```

**Osservazioni**:
- Baseline e EventProp ALIF convergono allo stesso plateau ~0.222-0.224 entro ep3
- LIF (entrambi i training) raggiungono plateau a ~0.32 entro ep4
- EventProp ALIF parte peggio (0.879 ep1) ma raggiunge baseline in ep2 — convergence trajectory diversa, stesso punto di arrivo

---

## 4. Risultati — spike rate (impatto deploy FPGA event-driven)

| | BPTT + surrogate | EventProp | Δ (EventProp − BPTT) |
|---|---:|---:|---:|
| **ALIF** | **3.7%** ✅ | 27.7% | **+24.0 pp** (peggio) |
| **LIF** | **20.3%** | 54.8% | **+34.5 pp** (peggio) |

**EventProp PRODUCE CONSISTENTEMENTE SPIKE RATE PIÙ ALTO** (factor 7× su ALIF, 2.7× su LIF). Causa probabile: l'adjoint event-based richiede eventi spike per assegnare credito → l'ottimizzazione spinge verso configurazioni con più spike per avere gradient signal più forte.

**Implicazione FPGA**: deploy event-driven beneficia di spike rate basso (energia ∝ spike count × E_spike). Baseline 3.7% → ~7× meno spike di EventProp 27.7% → ~7× meno energia consumed per inference. **Baseline vince nettamente su deploy.**

---

## 5. Risultati — tempo per epoca (perf computazionale)

| | BPTT | EventProp | Δ |
|---|---:|---:|---:|
| **ALIF** | 224 s | 164 s | EventProp **−27%** (più veloce) |
| **LIF** | 7 s | 8 s | comparabili |

EventProp ALIF è ~27% più veloce in training perché evita di mantenere il grafo computazionale di PyTorch (manual backward via state arrays). **Unico vantaggio operativo di EventProp osservato**, ma irrilevante per il deploy (entrambi i metodi producono pesi statici uguali).

---

## 6. Conclusioni rigorose

### 6.1 Training method (BPTT vs EventProp): NON HA EFFETTO SU val_data

In ENTRAMBE le architetture, BPTT+surrogate ed EventProp adjoint convergono allo **stesso val_data plateau** entro variazione < 1% relativo:
- ALIF: 0.2233 vs 0.2239 (Δ = 0.27%)
- LIF: 0.3203 vs 0.3226 (Δ = 0.72%)

**EventProp non è la cura, ma non è nemmeno bocciato — è EQUIVALENTE su val_data**.

### 6.2 L'architettura conta MOLTO

Passando da LIF a ALIF (con stesso training method) si guadagna **~30% su val_data**:
- BPTT: 0.3203 → 0.2233 (LIF → ALIF) = **−30.3%**
- EventProp: 0.3226 → 0.2239 = **−30.6%**

Le components che fanno la differenza (presenti in ALIF, assenti in LIF):
- Adaptive threshold + fatigue dynamics (auto-regolazione spike rate)
- Low-rank recurrence rec_U @ rec_V (memoria stato interno)
- max_delay=6 delayed synapses (memoria temporale extra)
- n_ticks=10 internal expansion (più computazione per step)
- Po2 quantization (HW-deploy compliant)

### 6.3 EventProp PEGGIORA il deploy FPGA

Spike rate ALIF: 3.7% (BPTT) vs 27.7% (EventProp). Stesso val_data, **7× più energia consumata** in deploy event-driven. Per use case FPGA-deploy (PYNQ-Z1) baseline è strettamente migliore.

### 6.4 Il floor val_data ~0.22 è ARCHITETTURALE, non training-dependent

DUE metodi di training indipendenti (BPTT+surrogate, EventProp adjoint) convergono allo stesso val_data plateau ~0.22 su ALIF. Combinato con i precedenti risultati P14 (no capacity issue, no data issue, no Po2 issue, no scheduler issue, no optimizer issue), questo è la **prova rigorosa** che il floor non è rompibile cambiando training method.

---

## 7. Mea culpa — errore di lettura precedente

**Confessione di errore (2026-06-01)**: nei tentativi F2.0b e F2.2 precedenti avevo claimato "EventProp dimezza val_data da 0.222 a 0.110". Questo era **sbagliato**: avevo letto la **colonna 10 (val_phys, MSE non-mascherato)** scambiandola per la **colonna 9 (val_data, RMSE mascherato)**.

I numeri VERI per F2.0b e F2.2 (verificati ora):
- F2.0b ep5: val_data = **0.327** (non 0.110), val_phys = 0.110
- F2.2 ep5: val_data = **0.323** (non 0.107), val_phys = 0.107

Quindi i "dimezzamenti" che avevano motivato i tentativi di EventProp recurrent + ALIF non erano reali. La verifica corretta confermava il sospetto dell'utente: "le rimozioni di Po2/delays/etc. erano state già testate in P14 e non avevano cambiato nulla".

**Lezione**: cite the column index when reading CSV. `val_data` (RMSE, primary metric, masked) e `val_phys` (MSE, no mask) hanno valori numerici molto diversi nonostante misurino la stessa cosa (errore accelerazione). Confondendoli si ottengono conclusioni opposte.

---

## 8. Stato file / artefatti

### Codice (branch `Training_Method_Exploration`)
- `core/eventprop.py`: 4 layer classes (LIFLayer_EventProp + LIFLayer_BPTT_Simple + ALIFLayer_EventProp_Full + LILayer_*)
- `core/network.py`: 4 wrapper (CF_FSNN_Net = baseline + 3 nuove)
- `train.py`: CLI `--training_method {baseline,bptt_lif_simple,eventprop_lif_simple,eventprop_alif_full}`

### Risultati locali grid 2×2
- `checkpoints/GRID2x2_baseline/`
- `checkpoints/GRID2x2_bptt_lif_simple/`
- `checkpoints/GRID2x2_eventprop_lif_simple/`
- `checkpoints/GRID2x2_eventprop_alif_full/`

Tutti con stesso CLI tag, log CSV per epoca, log per batch, plot G1-G13.

### Run precedenti (legacy F2.x, ora archiviati)
- `checkpoints/F20_eventprop_lif_smoke5/` (F2.0 broken — config sbagliato)
- `checkpoints/F20b_eventprop_lif_smoke5/` (F2.0b LIF EventProp puro, val_data 0.327)
- `checkpoints/F22_eventprop_lif_rec_smoke5/` (F2.2 LIF+rec, saturato 93% spike)
- `checkpoints/F21_eventprop_alif_smoke5/` (F2.1 ALIF stripped — grad esplosivo)
- `checkpoints/F21b_eventprop_alif_smoke5/` (F2.1b index fix, val_data 0.351)
- `checkpoints/F21full_smoke5/` (F2.1-full ALIF, val_data 0.224) ← stessa fisica di GRID2x2_eventprop_alif_full

---

## 9. Decisione operativa post-grid

**EventProp non è la cura** per il task CF_FSNN (evidenza grid 2x2 single-optimizer).

Prossimo passo: sweep optimizer 4×11 = **44 run su Azure** (notebook `Training_File_Optimizer_2x2.ipynb`) per chiusura scientifica definitiva. Se anche con Prodigy/Lion/AdamW-multi-lr nessuna config rompe baseline 0.222, la storia EventProp è chiusa con piena evidenza e si torna al baseline production.

**Tempi Azure stimati**: ~3h (44 run × ~4 min avg, baseline+ALIF lente ~9/7 min, LIF veloci ~20s).
