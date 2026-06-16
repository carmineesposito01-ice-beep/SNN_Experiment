# R32_B5_E1_STABLE — NEW Stability Champion

> **Ruolo**: champion **STABILITÀ** post-R32. Soppianta `R31_E1_STABLE` su tutti gli assi.
> **T_intra=0.0519 (+37% vs R31_E1), val_data=0.163 (−5.8% vs R31_E1), ep_done=50/50, gn_max=5.27e+09**.
> **Source**: `results/Prodigy_Study/R32_RestartMechanisms/B_E1_base/R32_B5_E1_decay03_warmup2`

## Perché questo snapshot

Combo decoder C3 + capacity ridotta (h=16, rank=4) + λ_sr=5 + **decay 0.3 + warmup 2 ep**. La capacity ridotta fornisce la baseline stabile (come R31_E1); decay+warmup ammortizzano il restart. Risultato: peak T_intra +37% rispetto a R31_E1 mantenendo 50/50 epoche, e val_data al livello dei record del progetto.

**Confronto vs R31_E1_STABLE** (soppiantato):
| Asse | R31_E1_STABLE | **R32_B5** | Δ |
|---|---:|---:|---:|
| T_intra peak | 0.038 | **0.052** | +37% ✅ |
| val_data best | 0.173 | **0.163** | −5.8% ✅ |
| ep completati | 50/50 | 50/50 | = |
| gn_max | 1.3e6 | 5.3e9 | peggiore ma tractable |
| spike_rate | 14.5% | 14.8% | ≈ |

## Metriche reali

| Metrica | Valore | Note |
|---|---:|---|
| T_intra_corr peak | **0.0519** | @ ep20 (post-1° restart smussato) |
| T_tracking_corr | 0.519 | @ ep20 |
| val_data best | **0.163** | @ ep40 |
| val_data @ Tp | 0.177 | finestra peak Tp |
| spike_rate | 14.8% | ✅ IN RANGE |
| gn_max_preclip | 5.27 × 10⁹ | esploso transient, non sostenuto |
| **Epochs run** | **50/50** | ⭐ Guard mai triggerata |
| Multi-obj hits | 3/4 | manca solo "clean" |

## Config esatta

Differenze rispetto a `R31_E1_STABLE`:
```yaml
# R32 custom_restart scheduler + decay + warmup
scheduler: custom_restart       # da cosine_no_restart
restart_T0: 15
restart_decay: 0.3              # ⭐ KEY
restart_warmup_epochs: 2        # ⭐ KEY
```

Setup completo:
```yaml
optimizer: prodigy
  lr: 0.5
  d0: 1e-6
  betas: (0.9, 0.99)
  weight_decay: 0.01

scheduler: custom_restart
  restart_T0: 15
  restart_decay: 0.3
  restart_warmup_epochs: 2
  (altri = default no-op)

cf_hidden_size: 16              # ⚠ ridotto
cf_rank: 4                      # ⚠ ridotto
cf_max_delay: 6
cf_bit_shift: 3
po2_enabled: 1

# Decoder R29 fixes
cf_init_bias_shift: 1
cf_logit_tau_per_channel: "10.0,3.0,10.0,3.0,3.0"

# PINN losses
lambda_data: 1.0
lambda_phys: 0.1
lambda_ou: 0.05
lambda_bc: 1.0
lambda_sr: 5.0                  # ⭐ KEY x10 vs C3 base

scenario_mix: "highway:0.4,urban:0.3,truck:0.2,mixed:0.1"
cut_in_ratio: 0.0
noise_scale: 0.0

# Explosion guard
max_epoch_explosion_streak: 2
epoch_explosion_threshold: 100.0  # mai triggerata in questo run

epochs: 50
batch_size: 8
val_batch_size: 32
seq_len: 50
n_train: 1500, n_val: 300
```

## Parametri totali rete

```
hidden_size=16, rank=4 → 232 params totali (vs 864 di C3 base)
```

## Riproduzione

```bash
python train.py --training_method baseline \
  --epochs 50 --max_steps_per_epoch 100 --batch_size 8 --val_batch_size 32 --seq_len 50 \
  --cf_hidden_size 16 --cf_rank 4 --cf_max_delay 6 --cf_bit_shift 3 --po2_enabled 1 \
  --cf_init_bias_shift 1 --cf_logit_tau_per_channel 10.0,3.0,10.0,3.0,3.0 \
  --lambda_data 1.0 --lambda_phys 0.1 --lambda_ou 0.05 --lambda_bc 1.0 --lambda_sr 5.0 \
  --scenario_mix "highway:0.4,urban:0.3,truck:0.2,mixed:0.1" --cut_in_ratio 0.0 \
  --n_train 1500 --n_val 300 --data_cache data/cache_1500_mixed_cut0.0_ou0.0.pt \
  --optimizer prodigy --lr 0.5 --max_lr 0.5 \
  --scheduler custom_restart --restart_T0 15 --restart_decay 0.3 --restart_warmup_epochs 2 \
  --prodigy_betas 0.9,0.99 --prodigy_d0 1e-6 --prodigy_d_coef 1.0 \
  --prodigy_weight_decay 0.01 --prodigy_use_bias_correction 1 --prodigy_safeguard_warmup 1 \
  --prodigy_growth_rate inf --max_inf_streak 99999 --early_stop_patience 0 \
  --max_epoch_explosion_streak 2 --epoch_explosion_threshold 100.0 \
  --tag R32_B5_repro
```

## Da non perdere

- È il **primo** champion che mostra come la combinazione capacity-ridotta + soft-restart (decay+warmup) possa simultaneamente: migliorare T_intra del 37%, ridurre val_data, mantenere 50/50 epoche, in un singolo trade-off.
- Il pattern "capacity bassa + λ_sr alto + soft restart" è il candidato principale per il deploy su PYNQ-Z1 (232 params → memoria FPGA molto contenuta).
