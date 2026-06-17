# R29v2_C3_CLEAN — Clean Champion (ground-truth riferimento)

> **Ruolo**: champion **CLEAN** del progetto. Best per riferimento scientifico/riproducibile.
> **T_intra=0.041, val_data=0.181, gn_max=40.6** — l'unica configurazione che raggiunge 4/4 obiettivi con gradienti certificati sotto il clip.
> **Source**: `results/Prodigy_Study/R29_DecoderFix_v2/C_combo/R29v2_C3_init_per_channel`

## Perché questo snapshot

Tra i 49 run dello sweep v2 + 14 di R31, è l'unico che raggiunge i 4 target operativi (T_intra>0.025, val_data<0.185, spike∈[10,25]%, gn<100) con `gn_max=40.6` — sotto la soglia 100 di esplosione. Tutti gli altri "champion" hanno gn ∈ [10⁴, 10¹⁹]. Questo è il **vero baseline scientifico** per il confronto con qualsiasi futuro setup.

## Metriche reali

| Metrica | Valore | Note |
|---|---:|---|
| T_intra_corr peak | 0.0407 | @ ep10 (ANCORA salendo a fine training) |
| T_tracking_corr | 0.497 | @ ep10 |
| val_data best | 0.177 | @ ep9 |
| val_total best | 0.189 | @ ep9 |
| spike_rate | 11.7% | ✅ IN RANGE [10%, 25%] |
| gn_max_preclip | **40.6** | ✅ CLEAN (sotto soglia 100) |
| Epochs run | 10/10 | training completo |
| Multi-obj hits | **4/4** | ⭐ |

## Config esatta

```yaml
optimizer: prodigy
  lr: 0.5  (R24F baseline)
  d0: 1e-6
  betas: (0.9, 0.99)
  use_bias_correction: True
  safeguard_warmup: True
  weight_decay: 0.01

scheduler: cosine_no_restart

cf_hidden_size: 32
cf_rank: 8
cf_max_delay: 6
cf_bit_shift: 3
seq_len: 50
batch_size: 8
epochs: 10
max_steps_per_epoch: 100

# R29 decoder fixes (la "magia")
cf_init_bias_shift: 1
cf_logit_tau_per_channel: "10.0,3.0,10.0,3.0,3.0"   # v0/s0 → τ=10, T/a/b → τ=3
cf_logit_tau_schedule: const

# Loss weights (baseline R24F)
lambda_data: 1.0
lambda_phys: 0.1
lambda_ou: 0.05
lambda_bc: 1.0
lambda_sr: 0.5
lambda_T_aux: 0.0          # no T supervision
lambda_v0_aux: 0.0         # no R30 aux
lambda_s0_aux: 0.0
lambda_a_aux: 0.0
lambda_b_aux: 0.0

scenario_mix: "highway:0.4,urban:0.3,truck:0.2,mixed:0.1"
po2_enabled: 1
seed: 42
```

## Cosa dimostra

1. **init_bias_shift + per-channel τ** è la combinazione che sblocca il rank-collapse
2. Per-channel τ [10,3,10,3,3] = sigmoid più piatta per canali a range grande (v0/s0)
3. **Saturazione di v0 NON è patologica** — la rete la usa come strategia di compressione
4. T_intra=0.041 (vs baseline 0.015) = **2.5× sopra baseline** con gradienti puliti

## Riproducibilità

Tag git: `pre_R31` su `Prodigy_Deep_Study` branch. Setup deterministico (seed=42).
Per replicare: `train.py` con i flag sopra + `--data_cache data/cache_1500_mixed_cut0.0_ou0.0.pt`.
