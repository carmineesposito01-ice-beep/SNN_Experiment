# EventProp Study — Risultati combinati (cross-sweep)

Aggregazione delle **5 campagne** dello studio EventProp su un'**unica metrica confrontabile**
(stesso val-set `cache_1500_launch_cut0.0_ou0.0.pt`, n_val 300, stesso scenario_mix). Generato da
`scripts/_build_eventprop_study_combined.py` (idempotente, solo da log già pushati).

Metrica **PRIMARIA = `val_data`** (fisica); **NRMSE = lente secondaria** (è una PINN).

## Backbone (dati)
| file | contenuto |
|---|---|
| `combined_arm_index.csv` | 1 riga/arm (102): sweep, famiglia, hyperparam, val_data/NRMSE finali, flag |
| `combined_epoch_long.csv` | arm × epoca (tidy) per le curve di dinamica/stabilità |

## Convenzioni anti-ambiguità
- **Namespace** `<sweep>/<arm>` (BPTT_REF esiste in 3 campagne con config diverse).
- **`common_val`**: confronti headline solo sugli arm sul val comune (99/102; i 3 `DS_*` di BS3 sono su
  wide-val → tenuti a parte).
- **`aborted` = ran_ep < budget_ep**: arm esplosi/troncati; inclusi nelle figure di *stabilità* (dove
  l'abort È il segnale), esclusi dai best headline.
- **`has_diag`**: la run logga `rec_spectral_radius`/`marginal_frac` (tutte tranne `Study`, 37 col).

## Famiglie
BPTT_champion (rif.), AdamW_decodeON (produzione), AdamW_decodeOFF, ProdigyEvent, Spectral_sweep,
AdamW_decodeON_seed (multi-seed), Dataset (DS narrow/wide/widebig).

## Figure — Stadio 1 (da log, locale)

### Tema 1 — Esiti
| fig | file | cosa mostra |
|---|---|---|
| F1 | `combined_F1_ranking.png` | ranking globale val_data (99 arm, colore=famiglia, // = aborted) |
| F2 | `combined_F2_pareto.png` | **Pareto** val_data↔NRMSE; anello verde = ProdigyEvent |
| F3 | `combined_F3_nrmse_heat.png` | NRMSE per-canale, media per famiglia |
| F4 | `combined_F4_pinn_composition.png` | composizione 5 componenti PINN, best per famiglia |

### Tema 2 — Progresso
| F5/F6 | `combined_F5_progress.png` | evoluzione del best EventProp per campagna (fisica+NRMSE) vs champion |

### Tema 3 — Dinamica & velocità
| F7/F8 | `combined_F7_dynamics.png` | convergenza val_data + gap train-val |
| F9/F10 | `combined_F9_speed.png` | epoche-a-90% + sec/epoca per famiglia |

### Tema 4 — Stabilità (core)
| F11 | `combined_F11_gradnorm.png` | grad_norm vs epoca (log) |
| F12 | `combined_F12_spectral.png` | **raggio spettrale vs epoca** — C11 lo vincola (~0.5) vs champion ~22 / no-constraint esplode |
| F13 | `combined_F13_aborted_map.png` | mappa stabilità target×lr (colore=frazione epoche completate) |
| F14 | `combined_F14_batch_stability.png` | grad per-batch pre/post-clip (stabile vs champion: picco 1e16 + recovery) |
| F15 | `combined_F15_grad_modules.png` | flusso gradiente per-modulo (recU/recV/fc/out) |

### Tema 5 — Meccanismo / correlazioni
| F16 | `combined_F16_target_stability.png` | spectral_target vs fisica (colore=raggio spettrale) |
| F17 | `combined_F17_lr_target_heat.png` | operating point lr×target → val_data |
| F18 | `combined_F18_efficiency.png` | val_data vs lr e vs gradiente medio |
| F19 | `combined_F19_sparsity.png` | spike_rate vs fisica |
| F20 | `combined_F20_prodigy_d.png` | traiettoria prodigy_d (PE + champion) |
| F21 | `combined_F21_lambda_effect.png` | spectral sweep λ×target → val_data |

### Tema 6 — Diagnostica
| F22 | `combined_F22_diagnostics.png` | raggio spettrale + spike_rate finali per-arm |

### Extra (colonne finora inutilizzate)
| F28 | `combined_F28_intra_std.png` | intra_std per-canale (confidenza identificazione) |
| F32 | `combined_F32_hyperparam.png` | importanza iperparametri (|corr| con val_data) |
| F33 | `combined_F33_compute_pareto.png` | Pareto compute-efficiency (accuratezza/minuto) |
| F34 | `combined_F34_decode_delta.png` | effetto decode on↔off per-canale |

### Tema 8 — Paradosso NRMSE ProdigyEvent
| F37 | `combined_F37_pe_dissection.png` | **PE: NRMSE più bassa di tutti MA fisica peggiore**; per-canale PE batte AdamW ovunque |

## In sospeso — Stadio 2 (passo Azure sui checkpoint)
Richiedono i pesi `.pt` (gitignorati, solo su Azure). Da rigenerare cross-sweep per tutti gli EventProp
+ BPTT_REF (resiliente + manifest):
- **F23** eff_rank / dead_neurons · **F24** closed-loop safety (oracolo vs SNN) · **F25** per-regime ·
  **F26** Path-B refit · **F27** rank→val_data→eff_rank · **F38-F40** PE closed-loop/per-regime/consistenza.

## Extra non ancora costruiti (cheap, su richiesta)
F29 T-tracking corr · F30 dinamica soglia ALIF (vth/margin) · F31 equalizzazione gradiente per-canale ·
F35 timeline eventi is_nan/is_inf · F36 settling di convergenza.
