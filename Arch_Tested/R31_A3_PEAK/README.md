# R31_A3_PEAK — Operational Peak Champion

> **Ruolo**: champion **OPERATIVO** (best peak achievable). Best per deployment quando T_intra è la metrica obiettivo.
> **T_intra=0.060, val_data=0.167, gn_max=4280** — il valore numerico più alto di T_intra mai osservato sul progetto.
> **Source**: `results/Prodigy_Study/R31_ChampionValidation/A_duration/R31_A3_C3_ep50_warmrestart`

## Perché questo snapshot

C3 + cosine warm restart T0=15 ep + 50 ep totali. Il restart a ep15 coincide ESATTAMENTE con il peak T_intra=0.0599 — la scoperta empirica fondamentale di R31: **il warm restart fornisce il meccanismo di escape post-peak che mancava**.

**Caveat operativo**: il run esplode (gn=4280) e viene abortito a ep32/50 dal guard. **Il valore champion è raggiunto al best checkpoint @ ep15**. Da deployare richiede early stop su gn_max>1000 o salvataggio esplicito di ep15.

## Metriche reali

| Metrica | Valore | Note |
|---|---:|---|
| **T_intra_corr peak** | **0.0599** | @ ep15 (= primo restart!) |
| T_tracking_corr | 0.547 | @ ep15 |
| **val_data best** | **0.167** | @ ep14 (RECORD assoluto del progetto) |
| spike_rate | 12.5% | ✅ IN RANGE |
| gn_max_preclip | 4280 | ⚠ ESPLOSO (transient ep20+) |
| Epochs run | 32/50 | abortito dal guard |
| Multi-obj hits | 3/4 | manca solo "clean" |

## Config esatta

Differenze rispetto a R29v2_C3_CLEAN:
```yaml
scheduler: cosine               # NON cosine_no_restart
T0: 15                          # restart ogni 15 epoche
epochs: 50                      # da 10 a 50

# (resto IDENTICO a R29v2_C3)
```

Setup completo:
```yaml
optimizer: prodigy
  lr: 0.5
  d0: 1e-6
  betas: (0.9, 0.99)
  weight_decay: 0.01

scheduler: cosine               # ⚠ KEY: warm restart
T0: 15

cf_hidden_size: 32
cf_rank: 8
cf_max_delay: 6
cf_bit_shift: 3
seq_len: 50
batch_size: 8
epochs: 50                      # ⚠ KEY: lungo
max_steps_per_epoch: 100

cf_init_bias_shift: 1
cf_logit_tau_per_channel: "10.0,3.0,10.0,3.0,3.0"
cf_logit_tau_schedule: const

lambda_data: 1.0
lambda_phys: 0.1
lambda_ou: 0.05
lambda_bc: 1.0
lambda_sr: 0.5
lambda_T_aux: 0.0

scenario_mix: "highway:0.4,urban:0.3,truck:0.2,mixed:0.1"
po2_enabled: 1
seed: 42

# Explosion guard ATTIVO (abortisce a ep32)
max_epoch_explosion_streak: 2
epoch_explosion_threshold: 100.0
```

## Cosa dimostra

1. **Warm restart funziona come escape post-peak**: il peak (0.060) avviene ESATTAMENTE al primo restart (ep15)
2. **Il LR salta 90×** al restart (lr_eff da 0.0002 a 0.018) → re-esplorazione locale → nuovo minimo migliore
3. **Trade-off chiaro**: +47% T_intra vs C3 CLEAN MA gradient instabile
4. Pattern temporale ep1-15: lr cala costantemente, T_intra cresce lento. Ep15 restart: NEW PEAK. Ep16-30: secondo ciclo (peak già passato). Ep30 restart: esplode entro ep32.

## Riproducibilità

Tag git: `pre_R32` (da creare) o HEAD post-R31. Setup deterministico (seed=42).
Per deployare in produzione: salvare esplicitamente checkpoint @ epoca del primo peak (early stop su val_T_intra_corr decay).
