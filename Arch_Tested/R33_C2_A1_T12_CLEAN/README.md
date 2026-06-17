# R33_C2_A1_T12_CLEAN — FINAL CLEAN Champion (closure 2026-06-16)

> **Ruolo**: champion **CLEAN** finale dello studio Prodigy. Primo setup a combinare 50/50 epoche complete + gradienti puliti (gn=52).
> **T_intra=0.0518, val_data=0.1654, ep_done=50/50, gn_max=52.3 ✅ CLEAN**.
> **Source**: `results/Prodigy_Study/R33_Closure/C_champion_fix/R33_C2_A1_T12_fix`

## Perché questo snapshot

R32_A1 (decay 0.3, T0=15) + due correzioni R33:
- `restart_T0`: 15 → **12**
- `epoch_explosion_threshold`: 100 → 10000

Risultato sorprendente: il run completa **50/50 ep** con **gn_max=52** (vicino a R29v2_C3_CLEAN che era 40.6 ma su soli 10 ep). Decay 0.3 riduce progressivamente l'amplitudine del restart: cycle_max_lr=0.5 → 0.15 → 0.045 → 0.0135. Il quarto ciclo lavora a lr~0.013, dinamiche praticamente lineari, niente esplosione.

## Record assoluti detenuti

| Metrica | Valore | Note |
|---|---:|---|
| **gn_max (50 ep completati)** | **52.3** | 🏆 unico setup nel progetto con 50 ep + gn<100 |
| ep run | **50/50** | nessun abort guard |
| spike_rate | 13.5% | quasi target |

## Confronto vs R29v2_C3_CLEAN

| Asse | R29v2_C3_CLEAN | **R33_C2** | Δ |
|---|---:|---:|---:|
| gn_max | 40.6 | 52.3 | +29% (entrambi <100 ✅) |
| ep run | 10/10 | **50/50** | **5×** ✅ |
| T_intra peak | 0.0407 | **0.0518** | **+27%** ✅ |
| val_data | 0.1771 | **0.1654** | **−6.6%** ✅ |
| spike_rate | 11.7% | 13.5% | più vicino al target |

C2 soppianta C3_CLEAN su **tutti** gli assi: più epoche, gn comparabile (entrambi clean), Tp e val_data migliori.

## Metriche reali

| Metrica | Valore | Note |
|---|---:|---|
| T_intra_corr peak | **0.0518** | @ ep47 (ciclo 4, fine training) |
| val_data best | 0.1654 | @ ep23 |
| val_data @ Tp | 0.173 | finestra peak Tp |
| spike_rate | 13.5% | |
| gn_max_preclip | **52.3** | ⭐ pulito |
| **Epochs run** | **50/50** | ⭐ nessun abort |

## Config esatta

Differenze rispetto a R32_A1:
```yaml
restart_T0: 12                  # ⭐ KEY: da 15 a 12
epoch_explosion_threshold: 10000.0  # da 100 a 10000 (irrilevante: gn mai sopra 52)
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
  restart_T0: 12
  restart_decay: 0.3            # ⭐ A1 signature (decay geometrico)
  restart_warmup_epochs: 0
  restart_lr_after: -1.0
  restart_adaptive: 0

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
epoch_explosion_threshold: 10000.0

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
  --scheduler custom_restart --restart_T0 12 --restart_decay 0.3 \
  --prodigy_betas 0.9,0.99 --prodigy_d0 1e-6 --prodigy_d_coef 1.0 \
  --prodigy_weight_decay 0.01 --prodigy_use_bias_correction 1 --prodigy_safeguard_warmup 1 \
  --prodigy_growth_rate inf --max_inf_streak 99999 --early_stop_patience 0 \
  --max_epoch_explosion_streak 2 --epoch_explosion_threshold 10000.0 \
  --tag R33_C2_repro
```

## Insight di chiusura

- Il decay geometrico **risolve** il problema dell'esplosione che ha tormentato R31-R32: dopo il 1° restart lr scende a 0.15, dopo il 2° a 0.045, ecc. Il 4° ciclo lavora in un regime di lr ≈ 1e-2, dove la dinamica BPTT è quasi lineare.
- Trade-off: i cicli successivi al 1° fanno poco lavoro effettivo (lr troppo basso) → Tp peak rimane a 0.052, sotto C1 (0.064). Ma se serve **stabilità + completion**, è IL setup.
- È il candidato naturale per il **deploy** su PYNQ-Z1: gradienti puliti + 864 params + 50 ep ripetibile.
