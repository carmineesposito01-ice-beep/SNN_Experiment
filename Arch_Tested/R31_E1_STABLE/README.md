# R31_E1_STABLE — Long-Run Stability Champion

> **Ruolo**: champion **STABILITÀ**. Best per training prolungati che non terminano per esplosione.
> **T_intra=0.038, val_data=0.173, gn_max=1.3e+06** — l'unico setup che completa 50/50 ep senza abort del guard.
> **Source**: `results/Prodigy_Study/R31_ChampionValidation/E_triple/R31_E1_triple_C3_h16_sr5_ep50`

## Perché questo snapshot

Triple combo C3 + hidden=16 + λ_sr=5: **unico run R31 a completare 50 epoche pianificate**. Pur avendo gradienti esplosi transitori (max 1.3M), il pattern è oscillatorio e non sostenuto → guard NON triggera. La capacità ridotta (16 neuroni) + regularizer spike alto rendono il sistema dinamico ma non divergente.

## Metriche reali

| Metrica | Valore | Note |
|---|---:|---|
| T_intra_corr peak | 0.0377 | @ ep28 |
| T_tracking_corr | 0.462 | @ ep28 |
| val_data best | 0.173 | @ ep≈40 |
| spike_rate | 14.5% | ✅ IN RANGE (al target 15%) |
| gn_max_preclip | 1.3 × 10⁶ | ⚠ esploso transient |
| **Epochs run** | **50/50** | ⭐ UNICO completato |
| Multi-obj hits | 3/4 | manca solo "clean" |

## Config esatta

Differenze rispetto a R29v2_C3_CLEAN:
```yaml
# Capacity ridotta (R25_D1 winner)
cf_hidden_size: 16              # ⚠ da 32 a 16 (rete più piccola!)
cf_rank: 4                      # da 8 a 4

# Spike regularizer 10× (R25_C2 winner)
lambda_sr: 5.0                  # da 0.5 a 5.0

epochs: 50                      # da 10 a 50
```

Setup completo:
```yaml
optimizer: prodigy
  lr: 0.5
  d0: 1e-6
  betas: (0.9, 0.99)
  weight_decay: 0.01

scheduler: cosine_no_restart    # NON warm restart

cf_hidden_size: 16              # ⚠ KEY
cf_rank: 4
cf_max_delay: 6
cf_bit_shift: 3
seq_len: 50
batch_size: 8
epochs: 50
max_steps_per_epoch: 100

cf_init_bias_shift: 1
cf_logit_tau_per_channel: "10.0,3.0,10.0,3.0,3.0"
cf_logit_tau_schedule: const

lambda_data: 1.0
lambda_phys: 0.1
lambda_ou: 0.05
lambda_bc: 1.0
lambda_sr: 5.0                  # ⚠ KEY: 10× R24F
lambda_T_aux: 0.0

scenario_mix: "highway:0.4,urban:0.3,truck:0.2,mixed:0.1"
po2_enabled: 1
seed: 42
max_epoch_explosion_streak: 2
epoch_explosion_threshold: 100.0
```

Param count: ~232 parametri (vs 864 baseline) — **27% del modello standard**.

## Cosa dimostra

1. **Capacity RIDOTTA aiuta la stabilità** — meno parametri = meno explosion modes
2. **λ_sr=5 stabilizza la dinamica spike** mantenendo spike rate al target 14.5%
3. **Triple combo** = sacrificio T_intra (0.038 vs 0.060 di A3) per stabilità long-run
4. Esplosioni transienti (max 10⁶) → guard NON triggera grazie a streak<2 (non consecutivi)

## Riproducibilità

Tag git: `pre_R32` (HEAD post-R31). Setup deterministico (seed=42).
**Strength**: completa training senza intervento. Ideal per pipeline batch automatizzati.
