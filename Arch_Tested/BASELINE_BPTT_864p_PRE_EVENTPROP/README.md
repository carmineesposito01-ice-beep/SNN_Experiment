# BASELINE_BPTT_864p_PRE_EVENTPROP

> **Questa è la VERA baseline pre-EventProp**, usata come reference quando è iniziato lo studio EventProp (commit `5a2c7ee`, branch `Training_Method_Exploration`). Architetturalmente identica ad `A1_baseline_BPTT_864p` ma con **`lambda_sr = 0.5`** (vs `0.0` in A1).
>
> **Usa questa cartella per gli studi R2 (Prodigy) e R3 (EventProp)**, NON A1.

**Classe Python**: `CF_FSNN_Net`
**Parametri totali**: 864
**Training method**: BPTT + SurrogateSpike (γ=1.0)

## Differenza vs A1_baseline_BPTT_864p (CRITICA)

| Field | F2 / **PRE_EVENTPROP (questa)** | A1_baseline_BPTT_864p |
|---|---|---|
| Classe Python | `CF_FSNN_Net` 864p | `CF_FSNN_Net` 864p (stessa) |
| optimizer / lr / scheduler / batch / epochs / steps / seq_len | adamw / 2e-3 / onecycle / 8 / 15 / 190 / 50 | identici |
| h / r / max_delay / Po2 / noise_scale / scenario_mix | 32 / 8 / 6 / ON / 0 / highway | identici |
| lambdas data/phys/ou/bc | 1.0 / 0.1 / 0.05 / 1.0 | identici |
| **lambda_sr** | **0.5** ✅ | **0.0** ❌ |

L'unica differenza è `lambda_sr`. F2 mantiene la pressione esplicita verso il target spike rate (15-20% via `SPIKE_RATE_TARGET` in `config.py`). A1 (introdotta da `Architecture_Exploration` step P15) l'ha disattivata, sintomo dell'errore di setup ricorrente #3.1 documentato in `document/AUDIT_2026-06-02.md`.

## Descrizione

Baseline production CF_FSNN_Net 864p, run pre-EventProp:
- ALIF 32 neuroni (rank=8, max_delay=6), Po2 quantization, bit-shift leak (V/8)
- PINN multi-objective con `lambda_sr=0.5` attivo (spike-rate regularizer)
- Highway-only, OU off (noise_scale=0), AdamW lr=2e-3 + OneCycleLR
- 15 epoche × 190 steps su cache F2 (`cache_1500_highway_cut0.0_ou0.0.pt`)

## Risultati run originale

**Source**: `results/P12_S2D_F2_no_ou/` (snapshot copiato in `snapshot_original/`).

| Metric | Valore |
|---|---:|
| epochs totali | 15 |
| best epoch (val_total) | 14 |
| **val_total best** | **0.2262** |
| val_data al best | 0.2211 |
| spike_rate avg | 0.1273 (12.7%) |
| spike_rate last | 0.1541 (15.4%) |

13 plot G1-G13 in `snapshot_original/plots/`.

## CLI per riprodurre

```bash
python train.py \
  --training_method baseline    # implicito al tempo di F2 (pre-Architecture_Exploration) \
  --epochs 15 \
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
  --lambda_sr 0.5 \
  --noise_scale 0.0 \
  --po2_enabled 1            # default a quel tempo (CLI po2_enabled aggiunta dopo) \
  --max_inf_streak 99999 \
  --early_stop_patience 0 \
  --data_cache data/cache_1500_highway_cut0.0_ou0.0.pt \
  --tag BASELINE_PRE_EVENTPROP_reproduce
```

## Architettura

Forward pipeline identico ad A1_baseline_BPTT_864p:
1. Input (4 features: s, v, Δv, vL) normalizzato → HiddenLayer_ALIF
2. ALIF cell: leak + integrate + spike + adaptive threshold + fatigue, low-rank recurrent U(32×8)·V(8×32)
3. delayed synapses via deque ring-buffer (O(1) update)
4. OutputLayer_LI: integratore passivo (no spike), 5 output (raw → params IDM)
5. Decode sigmoid → [v0, T, s0, a, b] fisici con bounds _PARAM_BOUNDS

**Loss training**:
```
L_total = 1.0·L_data + 0.1·L_phys + 0.05·L_ou + 1.0·L_bc + 0.5·L_sr
```

dove `L_sr = (mean(spike_rate) - SPIKE_RATE_TARGET)²` con target ~15-20%.

## Criticità note

- **Highway-only training**: violin G7 mostra collasso di 4/5 params (la rete impara mappa costante per highway)
- **single-seed**: 1 seed only
- **Mai testato scenari misti, mai sweep multi-seed**: confermato in AUDIT (Q4-Q7)

Vedi `../README.md` per criticità globali.

## Notebook di riproduzione

`reproduce_training.ipynb` — 4 celle (intro, ENV+build_model verify, smoke 1ep+diff, full opzionale).

## File contenuti

Copia esatta della struttura `A1_baseline_BPTT_864p/`:
- `core/network.py` (CF_FSNN_Net solo) + `neurons.py`, `hardware.py`
- `data/generator.py`, `utils/plot_diagnostics.py`, `config.py` (shared)
- `train.py` (CLI choices=['baseline'])
- `snapshot_original/` da `results/P12_S2D_F2_no_ou/` (NOT da T30!)
- `reproduce_training.ipynb`
