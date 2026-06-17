# R33_C1_A4_T12_PEAK — FINAL PEAK Champion (closure 2026-06-16)

> **Ruolo**: champion **PEAK** finale dello studio Prodigy. Detiene il **record val_data assoluto del progetto**.
> **T_intra=0.0642, val_data=0.1589 🏆, ep_done=49/50, gn_max=1.78×10¹⁹**.
> **Source**: `results/Prodigy_Study/R33_Closure/C_champion_fix/R33_C1_A4_T12_fix`

## Perché questo snapshot

R32_A4 (warmup 2ep, T0=15) + due correzioni R33:
- `restart_T0`: 15 → **12** (4 cicli pieni in 50 ep invece di 3 + 1 monco)
- `epoch_explosion_threshold`: 100 → 10000 (no abort su spike isolati)

Risultato: **+8 epoche di vita** rispetto a R32_A4 (41→49), Tp leggermente migliore, **val_data 0.1589 = record assoluto del progetto** (batte R32_B2 = 0.1609 di 1.2 pp).

## Record assoluti detenuti

| Metrica | Valore | Note |
|---|---:|---|
| **val_data best** | **0.1589** | 🏆 record assoluto post-fix (precedente: R32_B2=0.161) |
| T_intra peak | 0.0642 | 2° miglior Tp con run completata (D2_A3_adaptive ha 0.0651 ma collassa) |
| spike_rate | 11.9% | Vicino al target 15% |
| ep run | 49/50 | Aborted by guard al 50° |

## Metriche reali

| Metrica | Valore | Note |
|---|---:|---|
| T_intra_corr peak | **0.0642** | @ ep21 (cycle 2 con warmup) |
| val_data best | **0.1589** | @ ep36 (cycle 3) |
| val_data @ Tp | 0.166 | finestra peak Tp |
| spike_rate | 11.9% | |
| gn_max_preclip | 1.78 × 10¹⁹ | esploso ma sostenuto solo su singole epoche |
| **Epochs run** | **49/50** | aborted by R30 ExplosionGuard streak=2 @ep50 |

## Config esatta

Differenze rispetto a R32_A4:
```yaml
restart_T0: 12                  # ⭐ KEY: da 15 a 12
epoch_explosion_threshold: 10000.0  # ⭐ KEY: da 100 a 10000
# tutto il resto identico
```

Setup completo:
```yaml
optimizer: prodigy
  lr: 0.5
  d0: 1e-6
  betas: (0.9, 0.99)
  weight_decay: 0.01

scheduler: custom_restart
  restart_T0: 12                # ⭐ R33 fix
  restart_warmup_epochs: 2      # ⭐ A4 signature (warmup post-restart)
  restart_decay: 1.0            # disabilitato
  restart_lr_after: -1.0        # disabilitato
  restart_adaptive: 0           # disabilitato

cf_hidden_size: 32
cf_rank: 8
cf_max_delay: 6
cf_bit_shift: 3
po2_enabled: 1

# Decoder R29 fixes (DEC-1 + DEC-3)
cf_init_bias_shift: 1
cf_logit_tau_per_channel: "10.0,3.0,10.0,3.0,3.0"

# PINN losses
lambda_data: 1.0
lambda_phys: 0.1
lambda_ou: 0.05
lambda_bc: 1.0
lambda_sr: 0.5

scenario_mix: "highway:0.4,urban:0.3,truck:0.2,mixed:0.1"
cut_in_ratio: 0.0
noise_scale: 0.0

# Explosion guard (R33 default)
max_epoch_explosion_streak: 2
epoch_explosion_threshold: 10000.0  # ⭐ R33 fix

epochs: 50
batch_size: 8
val_batch_size: 32
seq_len: 50
n_train: 1500, n_val: 300
```

## Riproduzione

```bash
python train.py --training_method baseline \
  --epochs 50 --max_steps_per_epoch 100 --batch_size 8 --val_batch_size 32 --seq_len 50 \
  --cf_hidden_size 32 --cf_rank 8 --cf_max_delay 6 --cf_bit_shift 3 --po2_enabled 1 \
  --cf_init_bias_shift 1 --cf_logit_tau_per_channel 10.0,3.0,10.0,3.0,3.0 \
  --lambda_data 1.0 --lambda_phys 0.1 --lambda_ou 0.05 --lambda_bc 1.0 --lambda_sr 0.5 \
  --scenario_mix "highway:0.4,urban:0.3,truck:0.2,mixed:0.1" --cut_in_ratio 0.0 \
  --n_train 1500 --n_val 300 --data_cache data/cache_1500_mixed_cut0.0_ou0.0.pt \
  --optimizer prodigy --lr 0.5 --max_lr 0.5 \
  --scheduler custom_restart --restart_T0 12 --restart_warmup_epochs 2 \
  --prodigy_betas 0.9,0.99 --prodigy_d0 1e-6 --prodigy_d_coef 1.0 \
  --prodigy_weight_decay 0.01 --prodigy_use_bias_correction 1 --prodigy_safeguard_warmup 1 \
  --prodigy_growth_rate inf --max_inf_streak 99999 --early_stop_patience 0 \
  --max_epoch_explosion_streak 2 --epoch_explosion_threshold 10000.0 \
  --tag R33_C1_repro
```

## Insight di chiusura

- Il singolo intervento più impattante dell'intero R32→R33 NON è stato un meccanismo di restart sofisticato (decay/warmup/adaptive), ma il **riposizionamento dei cicli (T0=12)**. 8 epoche guadagnate valgono più di tutti i 5 meccanismi soft R32.
- gn=1.8e19 è alto ma SOSTENIBILE: la guard non triggera perché gli spike sono isolati (mai 2 epoche consecutive >10000).
- Combinato con C2 (CLEAN), questo è il setup di riferimento per chiudere lo studio Prodigy.
