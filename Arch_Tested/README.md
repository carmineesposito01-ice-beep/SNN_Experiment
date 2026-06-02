# Arch_Tested/ — Snapshot riproducibili delle architetture funzionanti

Snapshot self-contained delle 4 architetture CF_FSNN che hanno prodotto risultati significativi nel corso del progetto. Ogni sottocartella contiene il **codice minimale** (solo le classi necessarie), il **train.py con CLI ristretto**, lo **snapshot della run originale** (training_log.csv + config + plot G1-G13) e un **notebook di riproduzione** (`reproduce_training.ipynb`).

**Scopo**: non perdere il know-how dopo l'audit `document/AUDIT_2026-06-02.md`. Le architetture sono salvate prima di qualunque refactor / next-phase. Ogni cartella è ri-eseguibile in autonomia.

## Le 4 architetture

| Tag | Classe Python | Params | Training | val_total best | val_data | spike_rate avg | Source run |
|---|---|---:|---|---:|---:|---:|---|
| [`A1_baseline_BPTT_864p`](A1_baseline_BPTT_864p/) | `CF_FSNN_Net` | 864 | BPTT + surrogate | 0.2231 | 0.2177 | 4.8% | `T30_A1_BASELINE_adamw` |
| [`A8_attn_BPTT_3936p`](A8_attn_BPTT_3936p/) | `CF_FSNN_Net_Attn` | 3,936 | BPTT + surrogate | **0.1665** | **0.1632** | 3.0% | `T30_A8_ATTN_adamw` |
| [`A3_stacked_skip_BPTT_2624p`](A3_stacked_skip_BPTT_2624p/) | `CF_FSNN_Net_StackedSkip` | 2,624 | BPTT + surrogate | 0.2206 | 0.2149 | 2.9% | `T30_A3_STACKED_SKIP_adamw` |
| [`EVPROP_ALIF_full_864p`](EVPROP_ALIF_full_864p/) | `CF_FSNN_Net_EventProp_Full` | 864 | EventProp adjoint | 0.2226 | 0.2226 | 24.9% | `SW_eventprop_alif_full_adamw_lr2e-3` (5ep, sched=none) |

> ⚠️ Le metriche sono dalle run **highway-only** (setup canonico P15/T30). Non confrontabili con scenari misti, mai testati seriamente.

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
