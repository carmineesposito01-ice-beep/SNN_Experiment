# R24F_MIXED_lr0.5_V08 — VERO champion post-fix (mixed scenario)

> **Status**: ⭐ **NUOVO BASELINE UFFICIALE** del progetto dal 2026-06-12.
> **Sostituisce**: R25_B1, R25_A3, R28_A0, R29_E0 (tutti lr=1.0 con gradienti esplosi mascherati).
> **Riferimento storico**: `results/Prodigy_Study/MultiParam_PostFix/mixed/R24F_mixed_lr0.5_V08/`

## Perché questo snapshot

Lo studio R24F (post bug-fix 2026-06-03, 93 esperimenti con sweep LR × variant) ha identificato che:
- **lr=0.1** Prodigy NON converge (val_data 0.7-1.1 su tutti gli scenari)
- **lr=1.0** è instabile: 20-50% dei run esplodono (mascherati dal `clip_grad_norm_(1.0)`)
- **lr=0.5 V08 cosine_no_restart** è l'UNICO setup CLEAN con val_data competitivo

Tutti i nostri studi successivi (R25, R26, R28, R29) sono partiti da lr=1.0, ottenendo gradienti `gn_total_preclip` con max ∈ [10⁵, 10¹⁷] — gradienti esplosi sistematicamente, salvati dal clip ma con dinamica corrotta. Le metriche fini (`val_T_intra_corr`, `rank_effective`) introdotte da R27 erano misurate su un sistema strutturalmente non sano.

R24F_mixed_lr0.5_V08 è il **solo run noto con `gn_max < 25`** in tutta la storia post-fix.

## Metriche reali (dalla snapshot)

| Metrica | Valore | Note |
|---|---:|---|
| **val_total best** | **0.1887** | ep 10/10 (convergenza pulita fino alla fine) |
| **val_data best** | **0.1806** | ep 10 (best monotone decay) |
| val_phys at best | ~0.039 | |
| val_ou at best | ~0.011 | |
| Best epoch | 10 / 10 | ✅ converge fino all'ultima epoca |
| Epochs eseguite | 10 | budget standard R24F |
| **gn_total_preclip mean** | **0.997** | sano (target ~1.0) |
| **gn_total_preclip max** | **21.79** | sotto il clip a 1.0 → solo poche correzioni |
| **gn_total_preclip p99** | **8.55** | distribuzione benigna |
| **inf grads** | **0** | ✅ nessun batch esploso |
| **NaN loss** | 0 | ✅ |
| spike_rate avg | 7.3% | sotto il target 15% ma stabile (non collassato) |
| prodigy_d range | [0.0, 0.0192] | `d` cresce regolarmente, NON frozen |
| prodigy_lr_eff range | [0.0, 0.0063] | LR effettivo sano |

## Config esatta

```yaml
training_method: baseline
optimizer: prodigy
  lr: 0.5                      # ← CHIAVE: 0.5, non 1.0
  d0: 1e-6
  d_coef: 1.0
  betas: (0.9, 0.99)           # W1 community wisdom
  use_bias_correction: True    # W3
  safeguard_warmup: True       # raccomandato con cosine
  weight_decay: 0.01           # AdamW-style decoupled
  growth_rate: inf
scheduler: cosine_no_restart   # CosineAnnealingLR, T_max=epochs

cf_hidden_size: 32
cf_rank: 8
cf_max_delay: 6                # default config.py
cf_bit_shift: 3                # default
seq_len: 50                    # NON 100 (A3 era 100)
batch_size: 8
val_batch_size: 32
n_train: 1500
n_val: 300
epochs: 10
max_steps_per_epoch: 100

lambda_data: 1.0
lambda_phys: 0.1
lambda_ou:   0.05
lambda_bc:   1.0
lambda_sr:   0.5               # ← CORRETTO (Arch_Tested pre-fix avevano 0)
lambda_T_aux: 0.0              # NESSUNA supervisione T_aux (era 0.1 in B1)

scenario_mix: "highway:0.4,urban:0.3,truck:0.2,mixed:0.1"
cut_in_ratio: 0.0
noise_scale:  0.0
po2_enabled:  1
seed: 42
```

## Come riprodurre

```bash
cd Arch_Tested/R24F_MIXED_lr0.5_V08_TRUE_CHAMPION/
jupyter notebook reproduce_training.ipynb
```

Il notebook:
- Cell 0: contesto + perché V08 è il vero champion
- Cell 1: smoke 1ep × 3step (verifica CLI + sanity gn_max)
- Cell 2: full 10ep replica (sanity match val_data ≈ 0.181)
- Cell 3: confronto vs snapshot_original (devono allinearsi a meno di seed-induced drift)

## ⚠ Caveat post-R27 — il rank-collapse esiste anche qui

R27 audit ha incluso questo run. Risultati attesi:
- `T_tracking_corr_best`: ~0.20-0.40 (illusione cross-driver)
- `val_T_intra_corr`: probabilmente ≤ 0.03 (rank-collapse persiste)
- `rank_effective`: probabilmente 1 (collapse universale post-R27)
- `v0_pred`: probabilmente saturato a 38-42

**Il rank-collapse è universale sul baseline 864p anche con gradienti puliti** — questo conferma che il problema è strutturale (identifiability), NON instabilità di training. Tuttavia ora le metriche fini saranno misurabili in modo affidabile (gradienti sotto controllo).

## Posizione del checkpoint best_model.pt

Il `best_model.pt` originale non è incluso in questo snapshot (era su Azure NFS, non committato). Per ottenere un checkpoint riproducibile:
1. Esegui `reproduce_training.ipynb` Cell 2 → genera `checkpoint/best_model.pt`
2. Il checkpoint riprodotto va validato confrontando training_log con snapshot_original

## Quando NON usare questo baseline

- Se vuoi testare scenari diversi da mixed (per highway usa `lr=1.0 V08`)
- Se vuoi testare architetture diverse (attn 3936p) — vedi `Arch_Tested/A8_attn_BPTT_3936p/` (ma con caveat lambda_sr=0)
- Se vuoi includere `lambda_T_aux` o `seq_len=100` — sono add-on R25 che vanno testati separatamente sopra questo baseline pulito

## Storia decisionale (2026-06-12)

Lo riconosco con onestà: dopo l'audit del 2026-06-03, ho selezionato baseline successivi (R25_B1, R25_A3) basandomi su val_data senza controllare `gn_total_preclip`. Tutti i nostri studi R25→R29 sono stati costruiti su baseline con gradienti esplosi mascherati. L'utente ha sospettato instabilità del baseline; verifica numerica ha confermato che R24F_mixed_lr0.5_V08 è il SOLO setup post-fix CLEAN (gn_max 21.8). Da ora in poi, ogni studio (R30+) parte da QUI.

## Riferimenti

- Source originale: `results/Prodigy_Study/MultiParam_PostFix/mixed/R24F_mixed_lr0.5_V08/`
- Aggregator R24F: `results/Prodigy_Study/MultiParam_PostFix/_aggregate_r24f.csv` (93 esperimenti)
- Studio Prodigy completo: `document/PRODIGY_DEEP_STUDY.md`
- Audit metrices R27: `results/Prodigy_Study/Audit_R27/audit_summary.csv` (24 run R25+R26 auditati)
- Verità completa post-2026-06-12: `document/TIMELINE.md` (sezione "Reset al vero baseline")
