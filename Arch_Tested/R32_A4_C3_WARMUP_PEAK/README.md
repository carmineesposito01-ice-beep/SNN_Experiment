# R32_A4_C3_WARMUP_PEAK — Peak T_intra Champion (high-completion)

> **Ruolo**: champion **PEAK** post-R32. Miglior peak T_intra tra i run che completano oltre l'80% delle epoche pianificate.
> **T_intra=0.0635 @ ep26, val_data=0.165, ep_done=41/50, gn_max=1.21e+13** — supera R31_A3_PEAK su tutti gli assi rilevanti (Tp +6%, val_data −1.2%, ep completate +28%).
> **Source**: `results/Prodigy_Study/R32_RestartMechanisms/A_C3_base/R32_A4_C3_warmup2ep`

## Perché questo snapshot

C3 base (h=32, λ_sr=0.5, decoder C3) + warm restart `T0=15` con **linear warmup di 2 epoche post-restart**. Il warmup smussa la transizione lr da bottom-of-cycle (≈0) a cycle_max (0.5), evitando il jump istantaneo di 90× che in R31_A3 generava il peak T_intra ma poi collassava in pochi step. Risultato: peak T_intra mantenuto, 9 epoche guadagnate rispetto a R31_A3 (32 → 41).

## Metriche reali (R32 aggregato)

| Metrica | Valore | Note |
|---|---:|---|
| T_intra_corr peak | **0.0635** | @ ep26 (post-1° restart @ep15) |
| T_tracking_corr | 0.521 | @ ep26 |
| val_data best | 0.165 | @ ep30 |
| val_data @ Tp | 0.166 | finestra peak Tp |
| spike_rate | 10.8% | sotto target 15% ma stabile |
| gn_max_preclip | 1.21 × 10¹³ | ⚠ esploso (abort streak 41→42) |
| **Epochs run** | **41/50** | aborted by R30 ExplosionGuard streak=2 |
| Multi-obj hits | 3/4 | manca solo "clean" |

## Config esatta

Differenze rispetto a `R29v2_C3_CLEAN`:
```yaml
# R32 custom_restart scheduler + warmup
scheduler: custom_restart
restart_T0: 15
restart_warmup_epochs: 2        # ⭐ KEY: smussa il restart
restart_decay: 1.0              # disabilitato (no decay)
restart_lr_after: -1.0          # disabilitato
restart_adaptive: 0             # disabilitato

epochs: 50                      # da 10 a 50
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
  restart_warmup_epochs: 2
  (altri restart_* = default no-op)

cf_hidden_size: 32              # baseline C3
cf_rank: 8
cf_max_delay: 6
cf_bit_shift: 3
po2_enabled: 1

# Decoder R29 fixes (DEC-1 + DEC-3)
cf_init_bias_shift: 1
cf_logit_tau_per_channel: "10.0,3.0,10.0,3.0,3.0"
cf_logit_tau_init/final: 1.0   # const

# PINN losses
lambda_data: 1.0
lambda_phys: 0.1
lambda_ou: 0.05
lambda_bc: 1.0
lambda_sr: 0.5
lambda_T_aux: 0.0               # nessuna supervisione ausiliaria R30

scenario_mix: "highway:0.4,urban:0.3,truck:0.2,mixed:0.1"
cut_in_ratio: 0.0
noise_scale: 0.0

# Explosion guard (R30)
max_epoch_explosion_streak: 2
epoch_explosion_threshold: 100.0  # ⚠ probabilmente troppo bassa, vedi R33

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
  --scheduler custom_restart --restart_T0 15 --restart_warmup_epochs 2 \
  --prodigy_betas 0.9,0.99 --prodigy_d0 1e-6 --prodigy_d_coef 1.0 \
  --prodigy_weight_decay 0.01 --prodigy_use_bias_correction 1 --prodigy_safeguard_warmup 1 \
  --prodigy_growth_rate inf --max_inf_streak 99999 --early_stop_patience 0 \
  --max_epoch_explosion_streak 2 --epoch_explosion_threshold 100.0 \
  --tag R32_A4_repro
```

## Criticità note

1. **Abort prematuro a ep41**: con `epoch_explosion_threshold=100` la guard è troppo sensibile. La maggioranza dei 7 epoche-spike >100 sono **isolate** (non causano abort), ma una coppia consecutiva basta. R33 alza la soglia a 10⁴.
2. **Restart T0=15 sub-ottimale per 50 ep**: 3 cicli + 5 ep monchi. R33 testa `T0=12` (4 cicli che chiudono esattamente a ep48).
3. **No auxiliary supervision**: questo run non usa il 4-tuple loader R30 (`lambda_T_aux=0`). Eventualmente combinare con supervisione aux per ulteriore guadagno.

## Da non perdere

- Il **warmup post-restart** è il singolo intervento che ha trasformato l'esplosione istantanea di R31_A3 in degradazione graduale → +9 epoche di vita utile, peak T_intra preservato.
- Pattern utilizzabile in qualunque sweep futuro con warm restart.
