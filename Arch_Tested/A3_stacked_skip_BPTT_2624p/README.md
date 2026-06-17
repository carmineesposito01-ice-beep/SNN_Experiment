# A3_stacked_skip_BPTT_2624p

**Classe Python**: `CF_FSNN_Net_StackedSkip`
**Parametri totali**: 2,624
**Training method**: BPTT + SurrogateSpike (γ=1.0)

## Descrizione

2 layer ALIF stacked + skip connection MS-style. Estende baseline aggiungendo un secondo hidden ALIF (32×32, rank=8) e una skip weight (5×32) che bypassa il secondo layer e si somma al potenziale LI output.

## Risultati run originale

**Source**: `results/T30/T30_A3_STACKED_SKIP_adamw/` (snapshot copiato in `snapshot_original/`).

| Metric | Valore |
|---|---:|
| epochs totali | 30 |
| best epoch (val_total) | 29 |
| **val_total best** | **0.2206** |
| val_data al best | 0.2149 |
| spike_rate avg | 0.0293 (2.9%) |
| spike_rate last | 0.0274 (2.7%) |

13 plot G1-G13 in `snapshot_original/plots/` (loss curve, components, lr schedule, grad norm, T scatter, spike rate, violin params, gn per batch, layer norms heatmap, loss per batch, spike rate per batch, weight max per batch, trajectory highway).

## CLI per riprodurre la run originale

```bash
python train.py \
  --training_method stacked_2_skip \
  --epochs 30 \
  --max_steps_per_epoch 190 \
  --batch_size 8 \
  --val_batch_size 64 \
  --seq_len 50 \
  --scheduler onecycle \
  --max_lr 0.002 \
  --lr 0.002 \
  --optimizer adamw \
  --prodigy_d_coef 1.0 \
  --scenario_mix highway \
  --cut_in_ratio 0.0 \
  --cf_hidden_size 32 \
  --cf_rank 8 \
  --lambda_data 1.0 \
  --lambda_phys 0.1 \
  --lambda_ou 0.05 \
  --lambda_bc 1.0 \
  --lambda_sr 0.0 \
  --noise_scale 0.0 \
  --po2_enabled 1 \
  --max_inf_streak 99999 \
  --early_stop_patience 0 \
  --data_cache data/cache_1500_highway_cut0.0_ou0.0.pt \
  --tag A3_stacked_skip_BPTT_2624p_reproduce
```

> ⚠️ La cache `data/cache_1500_highway_cut0.0_ou0.0.pt` deve essere disponibile in `data/`. Se manca, vedi `data/generator.py` per rigenerarla.

## Architettura

**Forward pipeline** (per ogni dt sample, n_ticks=10):
1. Input (4) → HiddenLayer_ALIF_0 (32, rank=8) → output spike_0
2. spike_0 → HiddenLayer_ALIF_1 (32, rank=8) → output spike_1
3. spike_1 → OutputLayer_LI (32→5) → potential_LI
4. Skip path: spike_0 → skip_weight (5×32 Po2) → added to potential_LI
5. Decode → 5 params IDM

**Params breakdown**: ~864 (layer 0) + ~640 (layer 1, no fc input) + ~160 (skip 5×32) + ~960 (LI + decode) = 2624 totali.

## Criticità note

- **spike_rate sr_min=0.0006 in alcune epoche** → dead neurons signal! Specialmente layer 1, che riceve spike_0 sparsi
- **lambda_sr=0**: nessuna pressione contro dead neurons
- **Highway-only**: come tutte le altre
- **Trend val_data ancora in discesa a ep30** (best a ep29) → forse beneficerebbe di >30 ep, mai testato

## Criticità globali (da AUDIT_2026-06-02.md)

Vedi `../README.md` per la lista completa. In sintesi: highway-only training, lambda_sr=0 sistemico, single-seed, contraddizione A8 vs P14 (capacity bottleneck o no?).


## Notebook di riproduzione

Vedi `reproduce_training.ipynb`:
- Cell 0 (md): titolo + parametri CLI
- Cell 1 (code): ENV check + `build_model('stacked_2_skip')` + count params
- Cell 2 (code): smoke 1 ep × 1 step + diff numerico vs snapshot
- Cell 3 (code, opzionale): full reproduction 30 ep

## File contenuti

- `core/network.py` (cleanup: SOLO le classi necessarie per `stacked_2_skip`)
- `core/neurons.py`, `core/hardware.py` (copia integrale)

- `data/generator.py`, `utils/plot_diagnostics.py`, `config.py` (shared)
- `train.py` (cleanup: argparse `--training_method choices=['stacked_2_skip']`)
- `snapshot_original/` (READ-ONLY: training_log.csv + config_snapshot.json + plots/)
- `reproduce_training.ipynb`
