# EVPROP_ALIF_full_864p

**Classe Python**: `CF_FSNN_Net_EventProp_Full`
**Parametri totali**: 864
**Training method**: EventProp adjoint (Wunderlich&Pehle 2021)

## Descrizione

Architettura IDENTICA ad A1 baseline (ALIF 32, rank=8, max_delay=6, Po2, n_ticks=10), ma training method EventProp invece di BPTT+surrogate. Backward custom via torch.autograd.Function con adjoint loop event-based: λ_V, λ_I, λ_U calcolati esattamente nei punti di spike.

## Risultati run originale

**Source**: `results/SW_OptimizerSweep/SW_eventprop_alif_full_adamw_lr2e-3/` (snapshot copiato in `snapshot_original/`).

| Metric | Valore |
|---|---:|
| epochs totali | 5 |
| best epoch (val_total) | 4 |
| **val_total best** | **0.2226** |
| val_data al best | 0.2226 |
| spike_rate avg | 0.2485 (24.8%) |
| spike_rate last | 0.2572 (25.7%) |

13 plot G1-G13 in `snapshot_original/plots/` (loss curve, components, lr schedule, grad norm, T scatter, spike rate, violin params, gn per batch, layer norms heatmap, loss per batch, spike rate per batch, weight max per batch, trajectory highway).

## CLI per riprodurre la run originale

```bash
python train.py \
  --training_method eventprop_alif_full \
  --epochs 5 \
  --max_steps_per_epoch 190 \
  --batch_size 8 \
  --val_batch_size 64 \
  --seq_len 50 \
  --scheduler none \
  --max_lr 0.005 \
  --lr 0.002 \
  --optimizer adamw \
  --prodigy_d_coef 1.0 \
  --scenario_mix highway \
  --cut_in_ratio 0.0 \
  --cf_hidden_size 32 \
  --cf_rank 8 \
  --lambda_data 1.0 \
  --lambda_phys 0.0 \
  --lambda_ou 0.0 \
  --lambda_bc 0.0 \
  --lambda_sr 0.0 \
  --noise_scale 0.0 \
  --po2_enabled 1 \
  --max_inf_streak 99999 \
  --early_stop_patience 0 \
  --data_cache data/cache_1500_highway_cut0.0_ou0.0.pt \
  --tag EVPROP_ALIF_full_864p_reproduce
```

> ⚠️ La cache `data/cache_1500_highway_cut0.0_ou0.0.pt` deve essere disponibile in `data/`. Se manca, vedi `data/generator.py` per rigenerarla.

## Architettura

**Forward pipeline**: identico ad A1 baseline (stesse classi ALIFCell + LICell modificate con custom autograd).

**Backward pipeline** (custom adjoint):
- `_EventPropWrapperFull.backward()` calcola λ adjoint per ogni neurone
- Jump term al momento dello spike: `λ_V[t-1] = α_m · λ_V[t] + s[t] · (λ_V[t] + grad[t]) / (I[t-1] - V_th + ε)`
- Propagation backward nel tempo (T*n_ticks = 500 step)
- thresh_jump trattato come **frozen** (semplificazione)
- λ_fatigue propagation **semplificata** (non full)

## Criticità note

- **Setup vincente fragile**: solo 5 ep × 190 step con `scheduler=none`. Con OneCycleLR esplode (grad_norm 10^17 a ep5-6).
- **Solo lr=2e-3 funziona**: nel sweep, AdamW 5e-4/5e-3 + Adam 2e-3 + Lion = tutti falliti (6/11 config explosion)
- **NON testato con tuning serio**: clip aggressivo, warmup, init scaling, detach periodico, thresh_jump learnable. Tutto da fare in R3 (EventProp_Deep_Study)
- **spike rate ~25%**: dentro target FPGA (15-20%) per natura del metodo, ma non controllato
- Confronto vs BPTT è "best vs best" a 5 ep — sequenza più lunga (15-30 ep) **mai testata stabile**

## Criticità globali (da AUDIT_2026-06-02.md)

Vedi `../README.md` per la lista completa. In sintesi: highway-only training, lambda_sr=0 sistemico, single-seed, contraddizione A8 vs P14 (capacity bottleneck o no?).


## Notebook di riproduzione

Vedi `reproduce_training.ipynb`:
- Cell 0 (md): titolo + parametri CLI
- Cell 1 (code): ENV check + `build_model('eventprop_alif_full')` + count params
- Cell 2 (code): smoke 1 ep × 1 step + diff numerico vs snapshot
- Cell 3 (code, opzionale): full reproduction 30 ep

## File contenuti

- `core/network.py` (cleanup: SOLO le classi necessarie per `eventprop_alif_full`)
- `core/neurons.py`, `core/hardware.py` (copia integrale)
- `core/eventprop.py` (copia integrale, necessaria per EventProp adjoint)
- `data/generator.py`, `utils/plot_diagnostics.py`, `config.py` (shared)
- `train.py` (cleanup: argparse `--training_method choices=['eventprop_alif_full']`)
- `snapshot_original/` (READ-ONLY: training_log.csv + config_snapshot.json + plots/)
- `reproduce_training.ipynb`
