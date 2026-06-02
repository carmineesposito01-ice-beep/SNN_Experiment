# A8_attn_BPTT_3936p

**Classe Python**: `CF_FSNN_Net_Attn`
**Parametri totali**: 3,936
**Training method**: BPTT + SurrogateSpike (γ=1.0)

## Descrizione

Variante con spike attention "lite". Estende A1 baseline con 3 matrici Q/K/V (32×32 caduna, Po2 quantizzate, n_heads=2) inframezzate tra hidden ALIF e LI output. Score attention via sigmoid (non softmax — più HW friendly).

## Risultati run originale

**Source**: `results/T30_A8_ATTN_adamw/` (snapshot copiato in `snapshot_original/`).

| Metric | Valore |
|---|---:|
| epochs totali | 30 |
| best epoch (val_total) | 23 |
| **val_total best** | **0.1665** |
| val_data al best | 0.1632 |
| spike_rate avg | 0.0301 (3.0%) |
| spike_rate last | 0.0404 (4.0%) |

13 plot G1-G13 in `snapshot_original/plots/` (loss curve, components, lr schedule, grad norm, T scatter, spike rate, violin params, gn per batch, layer norms heatmap, loss per batch, spike rate per batch, weight max per batch, trajectory highway).

## CLI per riprodurre la run originale

```bash
python train.py \
  --training_method attn \
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
  --tag A8_attn_BPTT_3936p_reproduce
```

> ⚠️ La cache `data/cache_1500_highway_cut0.0_ou0.0.pt` deve essere disponibile in `data/`. Se manca, vedi `data/generator.py` per rigenerarla.

## Architettura

**Forward pipeline** (per ogni dt sample, n_ticks=10):
1. Input (4) → HiddenLayer_ALIF (32 neuroni, rank=8, max_delay=6) — identica a A1
2. Spike Attention block: Q, K, V matrici Po2 (32×32 cad.)
   - Q·K element-wise → sigmoid score → moltiplicato V → output 32
3. OutputLayer_LI (32→5)
4. Decode → 5 params IDM

**Differenze vs A1**: aggiunge 3×1024=3072 params (Q/K/V) ai 864 baseline = 3936 totali.

## Criticità note

- **A8 vince probabilmente per capacity, NON per attention**: mai testato A1 con h=64 r=16 (~3500p) per confronto fair
- **Pattern violin "più vivo" può essere overfit di rumore**: con 4.5× params su highway-only la rete può memorizzare anche varianza spuria
- **Attention richiede MAC non-Po2 cross-channel**: vincolo PYNQ-Z1 mai verificato (BRAM/DSP)
- **Highway-only + single-seed + lambda_sr=0**: come tutte le altre

## Criticità globali (da AUDIT_2026-06-02.md)

Vedi `../README.md` per la lista completa. In sintesi: highway-only training, lambda_sr=0 sistemico, single-seed, contraddizione A8 vs P14 (capacity bottleneck o no?).


## Notebook di riproduzione

Vedi `reproduce_training.ipynb`:
- Cell 0 (md): titolo + parametri CLI
- Cell 1 (code): ENV check + `build_model('attn')` + count params
- Cell 2 (code): smoke 1 ep × 1 step + diff numerico vs snapshot
- Cell 3 (code, opzionale): full reproduction 30 ep

## File contenuti

- `core/network.py` (cleanup: SOLO le classi necessarie per `attn`)
- `core/neurons.py`, `core/hardware.py` (copia integrale)

- `data/generator.py`, `utils/plot_diagnostics.py`, `config.py` (shared)
- `train.py` (cleanup: argparse `--training_method choices=['attn']`)
- `snapshot_original/` (READ-ONLY: training_log.csv + config_snapshot.json + plots/)
- `reproduce_training.ipynb`
