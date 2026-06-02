# A1_baseline_BPTT_864p

> ⚠️ **NON USARE PER STUDI R2/R3 (Prodigy, EventProp)**. Questa run ha `lambda_sr=0`, ovvero la pressione esplicita verso il target spike rate è disattivata (errore di setup ricorrente #3.1 documentato in `document/AUDIT_2026-06-02.md`). È stata introdotta da `Architecture_Exploration` step P15 ma **non è la vera baseline production pre-EventProp**.
>
> **Per studi seri usa [`../BASELINE_BPTT_864p_PRE_EVENTPROP/`](../BASELINE_BPTT_864p_PRE_EVENTPROP/)** (source P12_S2D_F2_no_ou, `lambda_sr=0.5`, architetturalmente identica ma con il regolarizzatore spike-rate attivo).
>
> Questa cartella è preservata come archeologia post-Architecture_Exploration per non perdere l'evidenza dell'errore (utile per documentazione storica).

**Classe Python**: `CF_FSNN_Net`
**Parametri totali**: 864
**Training method**: BPTT + SurrogateSpike (γ=1.0)

## Descrizione

Baseline production: ALIF 32 neuroni (rank=8, max_delay=6) + LI(32→5). Po2 quantization on all weights, bit-shift leak (V/8) sul LI output. Architettura di riferimento PYNQ-Z1.

## Risultati run originale

**Source**: `results/T30_A1_BASELINE_adamw/` (snapshot copiato in `snapshot_original/`).

| Metric | Valore |
|---|---:|
| epochs totali | 30 |
| best epoch (val_total) | 28 |
| **val_total best** | **0.2231** |
| val_data al best | 0.2177 |
| spike_rate avg | 0.0484 (4.8%) |
| spike_rate last | 0.0559 (5.6%) |

13 plot G1-G13 in `snapshot_original/plots/` (loss curve, components, lr schedule, grad norm, T scatter, spike rate, violin params, gn per batch, layer norms heatmap, loss per batch, spike rate per batch, weight max per batch, trajectory highway).

## CLI per riprodurre la run originale

```bash
python train.py \
  --training_method baseline \
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
  --tag A1_baseline_BPTT_864p_reproduce
```

> ⚠️ La cache `data/cache_1500_highway_cut0.0_ou0.0.pt` deve essere disponibile in `data/`. Se manca, vedi `data/generator.py` per rigenerarla.

## Architettura

**Forward pipeline** (per ogni dt sample, n_ticks=10 micro-tick interni):
1. Input (4 features: s, v, Δv, vL) normalizzato → HiddenLayer_ALIF
2. ALIF cell: leak + integrate + spike + adaptive threshold + fatigue, low-rank recurrent U(32×8)·V(8×32)
3. delayed synapses via deque ring-buffer (O(1) update)
4. OutputLayer_LI: integratore passivo (no spike), 5 output (raw → params IDM)
5. Decode sigmoid → [v0, T, s0, a, b] fisici con bounds _PARAM_BOUNDS

## Criticità note

- **Highway-only training**: violin G7 mostra 4/5 params collassati al min/max
- **lambda_sr=0**: spike rate 4-5% non vincolato (target 15-20%)
- **single-seed**: run sorgente con 1 seed only
- **Mai testato scenari misti**, mai sweep multi-seed

## Criticità globali (da AUDIT_2026-06-02.md)

Vedi `../README.md` per la lista completa. In sintesi: highway-only training, lambda_sr=0 sistemico, single-seed, contraddizione A8 vs P14 (capacity bottleneck o no?).


## Notebook di riproduzione

Vedi `reproduce_training.ipynb`:
- Cell 0 (md): titolo + parametri CLI
- Cell 1 (code): ENV check + `build_model('baseline')` + count params
- Cell 2 (code): smoke 1 ep × 1 step + diff numerico vs snapshot
- Cell 3 (code, opzionale): full reproduction 30 ep

## File contenuti

- `core/network.py` (cleanup: SOLO le classi necessarie per `baseline`)
- `core/neurons.py`, `core/hardware.py` (copia integrale)

- `data/generator.py`, `utils/plot_diagnostics.py`, `config.py` (shared)
- `train.py` (cleanup: argparse `--training_method choices=['baseline']`)
- `snapshot_original/` (READ-ONLY: training_log.csv + config_snapshot.json + plots/)
- `reproduce_training.ipynb`
