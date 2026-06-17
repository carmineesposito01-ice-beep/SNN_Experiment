# Arch_Tested/ — Snapshot riproducibili delle architetture funzionanti

> **CHIUSURA STUDIO 2026-06-16**: R33 Closure ha prodotto 2 NUOVI champion finali: **R33_C1 PEAK** (Tp=0.064, val_data=0.159 RECORD ASSOLUTO, 49/50 ep) e **R33_C2 CLEAN** (Tp=0.052, **gn=52 ✅**, 50/50 ep). Soppiantano R32_A4 e R29v2_C3 nei rispettivi ruoli. Studio Prodigy chiuso. Merge → main.
> **Aggiornamento 2026-06-16**: aggiunte 3 entry post-R32 (restart mechanisms): A4 WARMUP_PEAK, A1 DECAY_BALANCED, B5 STABLE.
> **Aggiornamento 2026-06-15**: aggiunte 3 entry post-R31 (champion validation): C3 CLEAN, A3 PEAK, E1 STABLE.

Snapshot self-contained delle architetture CF_FSNN che hanno prodotto risultati significativi nel corso del progetto. Ogni sottocartella contiene il **codice minimale** (solo le classi necessarie), il **train.py con CLI ristretto**, lo **snapshot della run originale** (training_log.csv + config + plot G1-G13) e un **notebook di riproduzione** (`reproduce_training.ipynb`).

**Scopo**: non perdere il know-how + tracciare quali setup hanno gradienti effettivamente sani (non solo metriche "alle apparenze").

## Le 14 architetture / setup

| Tag | Classe Python | Params | Training | val_total best | val_data | T_intra peak | gn_max | spike_rate | Note |
|---|---|---:|---|---:|---:|---:|---:|---:|---|
| ⭐⭐⭐ [`R33_C1_A4_T12_PEAK`](R33_C1_A4_T12_PEAK/) | `CF_FSNN_Net + DEC` | 864 | Prodigy lr=0.5 + restart T0=12 + warmup 2ep | 0.166 | **0.1589** 🏆 | **0.0642** | 1.78e+19 ⚠ | 11.9% | **FINAL PEAK CHAMPION 2026-06-16.** Record val_data assoluto. 49/50 ep. |
| ⭐⭐⭐ [`R33_C2_A1_T12_CLEAN`](R33_C2_A1_T12_CLEAN/) | `CF_FSNN_Net + DEC` | 864 | Prodigy lr=0.5 + restart T0=12 + decay 0.3 | 0.171 | 0.1654 | 0.0518 | **52.3** ✅ | 13.5% | **FINAL CLEAN CHAMPION 2026-06-16.** Primo 50/50 ep + gn<100. Soppianta R29v2_C3. |
| ⭐⭐ [`R32_B5_E1_STABLE`](R32_B5_E1_STABLE/) | `CF_FSNN_Net + DEC` | **232** | Prodigy lr=0.5 + h=16 + λ_sr=5 + decay 0.3 + warmup 2ep | 0.171 | 0.163 | 0.0519 | 5.3e+09 ⚠ | 14.8% | **STABILITY CHAMPION** (capacity ridotta, 232 params). 50/50 ep. |
| ⭐⭐ [`R24F_MIXED_lr0.5_V08_TRUE_CHAMPION`](R24F_MIXED_lr0.5_V08_TRUE_CHAMPION/) | `CF_FSNN_Net` | 864 | Prodigy lr=0.5 | 0.1887 | 0.1806 | 0.015 | 21.79 ✅ | 7.3% | Baseline pulito 2026-06-12 (storico) |
| ⚪ [`R29v2_C3_CLEAN`](R29v2_C3_CLEAN/) | `CF_FSNN_Net + DEC` | 864 | Prodigy lr=0.5 + init+per-ch τ | 0.1864 | 0.1771 | 0.0407 | 40.6 ✅ | 11.7% | Storico — soppiantato da R33_C2 |
| ⚪ [`R32_A4_C3_WARMUP_PEAK`](R32_A4_C3_WARMUP_PEAK/) | `CF_FSNN_Net + DEC` | 864 | Prodigy lr=0.5 + warm restart T0=15 + warmup 2ep | 0.166 | 0.165 | 0.0635 | 1.21e+13 ⚠ | 10.8% | Storico — soppiantato da R33_C1 (+8 ep) |
| ⚪ [`R32_A1_C3_DECAY_BALANCED`](R32_A1_C3_DECAY_BALANCED/) | `CF_FSNN_Net + DEC` | 864 | Prodigy lr=0.5 + restart decay 0.3 | 0.169 | 0.163 | 0.0577 | 6.5e+05 | 11.5% | Storico — soppiantato da R33_C2 |
| ⚪ [`R31_A3_PEAK`](R31_A3_PEAK/) | `CF_FSNN_Net + DEC` | 864 | warm restart standard | 0.1759 | 0.1667 | 0.0599 | 4280 ⚠ | 12.5% | Storico |
| ⚪ [`R31_E1_STABLE`](R31_E1_STABLE/) | `CF_FSNN_Net + DEC` | 232 | h=16 + λ_sr=5 | 0.1830 | 0.1731 | 0.0377 | 1.3e+06 ⚠ | 14.5% | Storico — soppiantato da R32_B5 |
| [`BASELINE_BPTT_864p_PRE_EVENTPROP`](BASELINE_BPTT_864p_PRE_EVENTPROP/) | `CF_FSNN_Net` | 864 | BPTT + surrogate (AdamW) | 0.2262 | 0.2211 | (basso) | (sano) | `P12_S2D_F2_no_ou` | Backup pre-EventProp con `lambda_sr=0.5`. Highway only. AdamW lr=2e-3 + OneCycleLR. |
| [`A1_baseline_BPTT_864p`](A1_baseline_BPTT_864p/) | `CF_FSNN_Net` | 864 | BPTT + surrogate | 0.2231 | 0.2177 | n/a | 4.8% | `T30_A1_BASELINE_adamw` | ⚠️ `lambda_sr=0` (errato). NON usare per R3. |
| [`A8_attn_BPTT_3936p`](A8_attn_BPTT_3936p/) | `CF_FSNN_Net_Attn` | 3,936 | BPTT + surrogate | 0.1665 | 0.1632 | n/a | 3.0% | `T30_A8_ATTN_adamw` | ⚠️ `lambda_sr=0` + highway-only + spike rate degenere. "Evento fortuito" (vedi AUDIT). NON è il vero champion. |
| [`A3_stacked_skip_BPTT_2624p`](A3_stacked_skip_BPTT_2624p/) | `CF_FSNN_Net_StackedSkip` | 2,624 | BPTT + surrogate | 0.2206 | 0.2149 | n/a | 2.9% | `T30_A3_STACKED_SKIP_adamw` | ⚠️ `lambda_sr=0`. |
| [`EVPROP_ALIF_full_864p`](EVPROP_ALIF_full_864p/) | `CF_FSNN_Net_EventProp_Full` | 864 | EventProp adjoint | 0.2226 | 0.2226 | n/a | 24.9% | `SW_eventprop_alif_full_adamw_lr2e-3` (5ep, sched=none) | Architetturalmente == BASELINE_PRE_EVENTPROP, training method diverso. |

### Note critiche

> ⭐ **Da 2026-06-12 il VERO baseline è `R24F_MIXED_lr0.5_V08_TRUE_CHAMPION`** (Prodigy lr=0.5, mixed scenario, gradienti certificati < 25). Tutti i baseline pre-2026-06-12 (R25_B1, R25_A3, R28_A0, R29_E0) erano basati su **Prodigy lr=1.0 con gradienti pre-clip 10⁵-10¹⁷** mascherati dal `clip_grad_norm_(1.0)`. Le metriche fini (T_intra_corr, rank_effective) introdotte da R27 erano misurate su sistema instabile.
>
> ⚠️ I 4 backup pre-R24F (A1/A8/A3/EVPROP) hanno **`lambda_sr=0`** (errore di setup ricorrente). Solo `BASELINE_BPTT_864p_PRE_EVENTPROP` e il nuovo `R24F_MIXED_lr0.5_V08_TRUE_CHAMPION` hanno `lambda_sr=0.5`.
>
> ⚠️ T30_A8_ATTN (val=0.166) era considerato top per la sua metrica val_data isolata, ma è stato declassato a "evento fortuito" perché: highway-only + lambda_sr=0 + spike rate degenere (3%) + setup non riproducibile cross-scenario.

## Setup comune (tutte le arch BPTT)

- `cache: data/cache_1500_highway_cut0.0_ou0.0.pt` (highway-only, noise=0, no cut-in)
- `batch=8 val_batch=64 seq_len=50 cf_hidden_size=32 cf_rank=8`
- `lambda_data=1.0 lambda_phys=0.1 lambda_ou=0.05 lambda_bc=1.0 lambda_sr=0.0`
- `po2_enabled=1 noise_scale=0.0`
- AdamW lr=2e-3 + OneCycleLR (A1/A3/A8); AdamW lr=2e-3 + scheduler=none (EVPROP)

## Criticità globali (da AUDIT_2026-06-02.md)

1. **Highway-only persistente**: tutti i training su `scenario_mix=highway`. Violin G7 mostra collasso di 4/5 params (la rete impara mappa costante). I confronti arch sono in setup degenere.
2. **lambda_sr = 0** ovunque: nessuna pressione esplicita verso target spike rate (15-20%). I valori 3-5% osservati sono side-effect, non risultato.
3. **single-seed**: tutti i ranking basati su 1 seed. Rumore intra-seed ≈ margini dichiarati.
4. **A8 vs P14 contraddizione**: A8 con 3936p batte A1 864p, ma P9_S2B aveva concluso che capacity non è bottleneck (sweep h32→h128, 4 ep). Lo studio non è confrontabile (4 ep vs 30 ep). Domanda aperta.

## Struttura cartella standard

```
<arch>/
├── README.md                          # dettagli arch + CLI riproduzione + criticità
├── core/                              # implementazione (cleanup chirurgico)
│   ├── network.py                     # solo classi necessarie + build_model ristretta
│   ├── neurons.py                     # ALIFCell + LICell (intero)
│   ├── hardware.py                    # Po2 quant + spike_fn (intero)
│   └── eventprop.py                   # solo per EVPROP_ALIF
├── data/generator.py                  # shared (intero)
├── utils/plot_diagnostics.py          # shared (intero, 13 plot G1-G13)
├── config.py                          # shared (intero)
├── train.py                           # cleanup CLI choices ristrette a 1 variant
├── reproduce_training.ipynb           # 3-4 celle per smoke + full reproduction
├── snapshot_original/                 # READ-ONLY, dalla run originale
│   ├── config_snapshot.json
│   ├── training_log.csv
│   ├── training_batch_log.csv
│   └── plots/                         # 13 G plot
└── checkpoint/best_model.pt           # (se disponibile)
```

## Come riprodurre una run

```bash
cd Arch_Tested/<arch>/
jupyter notebook reproduce_training.ipynb
# Cell 0-1: ENV check + build_model + count params
# Cell 2: smoke 1 ep × 1 step + diff vs snapshot
# Cell 3 (opzionale): full 30 ep reproduction
```

## Come aggiungere una nuova arch (futuro)

1. Crea sottocartella `Arch_Tested/<new_arch>/`
2. Copia layout standard (vedi sopra)
3. `core/network.py`: includi SOLO le classi necessarie + `build_model` factory ristretta
4. `train.py`: cleanup `argparse --training_method choices=['<new_variant>']`
5. Riempi `snapshot_original/` con i risultati della run originale
6. Compila README con metriche reali + criticità note
7. Verifica: smoke 1 ep × 1 step + import build_model OK

## Reference

- `document/AUDIT_2026-06-02.md` — bilancio onesto pre-roadmap
- `document/EVENTPROP_OPTIMIZER_SWEEP.md` — sweep 4x11 (origine EVPROP best)
- `document/P_S.md` — storia cronologica problemi/soluzioni
- `results/T30_*` — risultati run sorgenti A1/A8/A3
- `results/SW_eventprop_alif_full_adamw_lr2e-3/` — risultato run sorgente EVPROP
