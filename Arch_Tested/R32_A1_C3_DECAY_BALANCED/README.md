# R32_A1_C3_DECAY_BALANCED — Balanced T_intra/gn champion

> **Ruolo**: champion **BALANCED**. Miglior compromesso T_intra/val_data/stabilità tra i champion C3 base.
> **T_intra=0.0577, val_data=0.163, gn_max=6.5×10⁵ (14 OOM inferiore agli altri C3!), ep_done=25/50**.
> **Source**: `results/Prodigy_Study/R32_RestartMechanisms/A_C3_base/R32_A1_C3_decay03`

## Perché questo snapshot

C3 base + warm restart con **decay geometrico 0.3**: cycle_max_lr decresce 0.5 → 0.15 → 0.045 → ... Il decay smorza progressivamente l'ampiezza del restart, evitando il jump catastrofico. Risultato: gn_max **14 ordini di grandezza** più basso degli altri C3 (6.5e5 vs 1e13-1e19), val_data record per C3 base (0.163), Tp = 0.058 (sopra champion C3_CLEAN, sotto A4 warmup).

**Nota** — Per coincidenza A2 (2-tier lr_after=0.15) produce numeri IDENTICI: il primo ciclo decay 0.3 dà max_lr = 0.5×0.3 = 0.15, stesso valore del 2-tier. Esperimenti effettivi distinti = 4 (non 5). Tenere questo come "decay champion" (più generale del 2-tier statico).

## Metriche reali

| Metrica | Valore | Note |
|---|---:|---|
| T_intra_corr peak | **0.0577** | @ ep19 (cycle 1, lr ≈ 0.11) |
| T_tracking_corr | 0.542 | @ ep19 |
| val_data best | **0.163** | @ ep21 (record per C3 base) |
| val_data @ Tp | 0.169 | finestra peak Tp |
| spike_rate | 11.5% | sotto target 15% ma stabile |
| gn_max_preclip | **6.54 × 10⁵** | ⭐ 14 OOM sotto A3/A5 |
| **Epochs run** | 25/50 | abort guard streak=2 @ep25-26 |
| Multi-obj hits | 3/4 | manca solo "clean" e "complete" |

## Config esatta

Differenze rispetto a `R32_A4_C3_WARMUP_PEAK`:
```yaml
restart_decay: 0.3              # ⭐ KEY: decay geometrico
restart_warmup_epochs: 0        # NO warmup
```

Tutto il resto identico a A4 (vedi quel README per dettaglio C3 base).

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
  --scheduler custom_restart --restart_T0 15 --restart_decay 0.3 \
  --prodigy_betas 0.9,0.99 --prodigy_d0 1e-6 --prodigy_d_coef 1.0 \
  --prodigy_weight_decay 0.01 --prodigy_use_bias_correction 1 --prodigy_safeguard_warmup 1 \
  --prodigy_growth_rate inf --max_inf_streak 99999 --early_stop_patience 0 \
  --max_epoch_explosion_streak 2 --epoch_explosion_threshold 100.0 \
  --tag R32_A1_repro
```

## Criticità note

1. **Abort @ep25** prima del 2° restart programmato (ep30): l'esplosione avviene nella **prima** discesa cosine del 2° ciclo, non al jump del restart. Suggerisce che lr=0.15 con h=32 + λ_sr=0.5 sia ancora marginalmente troppo aggressivo nel regime post-prima discesa. Combinare con warmup (= R32_A5) NON migliora, anzi peggiora (gn=2e19): warmup riporta lr alto in modo lineare nel momento sbagliato.
2. **Soglia explosion=100 troppo bassa**: con gn_max=6.5e5 e soglia 1e4 il run avrebbe abortito comunque (R33 verifica).
