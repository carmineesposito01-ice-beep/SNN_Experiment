# PRODIGY_STUDY_CLOSURE.md — Executive summary post-merge 2026-06-16

> **READ THIS FIRST** se stai aprendo il progetto senza contesto. Fa da indice rapido a tutto il resto.

## TL;DR (60 secondi)

- **Progetto**: CF_FSNN — Spiking Neural Network per identificare parametri ACC-IDM car-following. Target hardware: PYNQ-Z1 FPGA.
- **Studio chiuso 2026-06-16**: il "Prodigy Deep Study" (R25→R33, 9 sessioni, ~350 esperimenti totali) è terminato con merge su `main`, tag `R33_closure`.
- **4 champion attivi** in `Arch_Tested/`, ognuno per un ruolo distinto.
- **Fase corrente**: post-merge, pre-deployment FPGA. Nessuna esplorazione in corso.
- **HEAD**: `main` @ `1e19296` (merge commit). Tutti i branch di esplorazione cancellati.

## Stato git

```
Branches:    solo `main` (locale + remoto). Tutti gli altri eliminati.
HEAD:        1e19296  Merge Prodigy_Deep_Study into main — R33 closure
Tags rollback per debugging:
  pre_bug_fix_2026-06-03  (prima dei 4 bug fix di network/eventprop)
  pre_R27, pre_R28, pre_R29, pre_R30, pre_R31, pre_R32, pre_R33  (rollback step-by-step)
Tag chiusura: R33_closure  (PROD-READY snapshot)
```

Per tornare a uno stato precedente: `git checkout pre_RXX`.
Per ripartire pulito da chiusura: `git checkout R33_closure`.

## I 4 champion attivi

Tutti in `Arch_Tested/<tag>/` con `README.md` + `snapshot_original/` (training_log.csv + config_snapshot.json + plots G1-G18).

| Ruolo | Tag | Params | Tp peak | val_data best | ep completate | gn_max | Quando usarlo |
|---|---|---:|---:|---:|---:|---:|---|
| **PEAK** | `R33_C1_A4_T12_PEAK` | 864 | **0.0642** | **0.1589** 🏆 | 49/50 | 1.78e19 | Max accuracy (val_data record). Accetti gn alto perché completa. |
| **CLEAN** | `R33_C2_A1_T12_CLEAN` | 864 | 0.0518 | 0.1654 | **50/50** | **52** ✅ | Baseline di deploy. Gradienti puliti garantiti, run riproducibile. |
| **STABLE** | `R32_B5_E1_STABLE` | **232** | 0.0519 | 0.163 | 50/50 | 5.3e9 | FPGA-friendly. 232 params (vs 864) = 4× footprint risparmiato. |
| **BASELINE storico** | `R24F_MIXED_lr0.5_V08` | 864 | 0.015 | 0.181 | 30/30 | 21.79 ✅ | Riferimento per certificare un nuovo setup come "almeno questo". |

**Per deployment FPGA: candidato naturale = CLEAN** (50/50 ep + gn pulito + 864 params standard). Fallback = STABLE se la memoria FPGA è critica.

## Configurazione codice attuale (defaults in train.py)

Codice rilevante per riprodurre i champion:

```python
# Optimizer
optimizer: prodigy
  lr: 0.5
  d0: 1e-6
  betas: (0.9, 0.99)
  weight_decay: 0.01
  growth_rate: inf
  use_bias_correction: 1
  safeguard_warmup: 1

# Scheduler R32 (custom_restart con 5 flag opt-in)
scheduler: custom_restart
  restart_T0: 12          # ⭐ DEFAULT R33: 4 cicli pieni in 50 ep
  restart_decay: 1.0      # 0.3 = champion CLEAN. 1.0 = no decay
  restart_lr_after: -1.0  # -1 = usa decay; 0.15 = 2-tier (= decay 0.3)
  restart_warmup_epochs: 0  # 2 = champion PEAK
  restart_adaptive: 0     # 1 = adaptive (sconsigliato: instabile)

# Explosion guard R30/R33
max_epoch_explosion_streak: 2
epoch_explosion_threshold: 10000.0  # ⭐ DEFAULT R33 (era 100, troppo sensibile)

# Decoder R29 fixes (DEC-1 + DEC-3)
cf_init_bias_shift: 1
cf_logit_tau_per_channel: "10.0,3.0,10.0,3.0,3.0"
cf_logit_tau_init/final: 1.0  # const

# Architettura (default config.py)
cf_hidden_size: 32   # 16 per STABLE
cf_rank: 8           # 4 per STABLE
cf_max_delay: 6
cf_bit_shift: 3
po2_enabled: 1

# PINN losses (champion C3 base)
lambda_data: 1.0
lambda_phys: 0.1
lambda_ou: 0.05
lambda_bc: 1.0
lambda_sr: 0.5   # 5.0 per STABLE (E1)
lambda_T_aux/v0_aux/s0_aux/a_aux/b_aux: 0.0  # R30 4-tuple non attivo per default

# Dataset
scenario_mix: "highway:0.4,urban:0.3,truck:0.2,mixed:0.1"
cut_in_ratio: 0.0
noise_scale: 0.0
seq_len: 50
batch_size: 8
val_batch_size: 32
n_train: 1500, n_val: 300
```

## Verità chiave dello studio (lezioni #41-#52)

Cosa sappiamo con certezza alla chiusura:

1. **`gn_total_preclip` è l'UNICA metrica di stabilità affidabile** (#41). `clip_grad_norm_(1.0)` maschera l'instabilità nel `gn_postclip` che è sempre 1.0. Senza misurare `gn_preclip` si lavora su sistemi corrotti.
2. **Per Prodigy: lr=0.5 è l'unico setup CLEAN per il nostro regime SNN+BPTT** (#42-43). lr=1.0 esplode (10⁵-10¹⁷), lr=0.1 non converge. La convenzione paper (lr=1.0) NON vale per SNN+surrogate.
3. **Identifiability era il bottleneck primario, non capacità** (#45). Supervisione ausiliaria 4-tuple (R30) ha sbloccato il rank-collapse universale visto in R27.
4. **Warm restart è lama a doppio taglio** (#46): il primo restart fa sempre il peak Tp, ma il lr-jump di 90× implode la rete poco dopo. Soft restart (decay, warmup) mitiga.
5. **Champion ≠ uno; pareto multi-asse** (#47): T_intra, val_data, stabilità, gn_max sono assi distinti. Forzare un singolo vincitore perde informazione.
6. **T_intra peak ≠ val_total best epoch** (#48): aggregatori standard (idxmin val_total) perdono il peak T_intra. Per Prodigy_Study tutti i ranking sono stati ricalcolati con `T_intra_corr.idxmax()` per run.
7. **Python 3.10 compat check obbligatorio prima di push su Azure** (#49). `\'` in f-string expression rejected. Step: `ast.parse(src, feature_version=(3,10))` su tutte le celle code.
8. **Il posizionamento dei cicli batte i meccanismi di restart sofisticati** (#50). `T0=12` (4 cicli pieni in 50 ep) ha portato +8 ep su A4 e +25 ep su A1, più di tutti i 5 meccanismi soft R32 messi insieme.
9. **Default conservativi delle guard sono critici** (#51). Soglia 100 era troppo bassa per Prodigy regime: spike transienti non sono divergenza vera. 10000 distingue.
10. **Studio rigoroso ≠ studio infinito** (#52). 5 esp. R33 ben mirati hanno sbloccato 2 nuovi record che 30+ esp. R28-R31 avevano mancato.

## Roadmap chiusura → next phase

Lo studio Prodigy è chiuso. Le opzioni successive (vedi `document/FUTURE_WORK.md`):

| Opzione | Costo | Razionale |
|---|---|---|
| **F5 — Deploy FPGA** (PYNQ-Z1) | medio | Procedere con R33_C2_CLEAN come baseline. Setup minimum-risk per hardware. |
| **F4 — Architettura modificata** (StackedSkip, Attn) | medio | Solo se il floor 0.16 val_data è inaccettabile. Già fatto pre-RESET; ora vale riprovarlo con baseline pulito. |
| **F6 — Multi-seed validation** | basso | Tutti i champion sono single-seed. Confermare 3-5 seed prima del deploy ridurrebbe il rischio di evento fortuito. **CONSIGLIATO prima di F5**. |

**Raccomandazione neutra**: F6 (multi-seed sui 4 champion, ~6h compute totale) → poi F5 (deploy CLEAN su PYNQ-Z1) → F4 solo se accuracy insufficiente in-target.

## File essenziali per orientarsi (in ordine di lettura)

1. **`document/PRODIGY_STUDY_CLOSURE.md`** ← questo file (orientamento generale)
2. **`document/SESSION_RESUME.md`** ← stato attuale dettagliato (sezione "Stato attuale 2026-06-16")
3. **`Arch_Tested/README.md`** ← roster champion completo (14 entries: 4 attive + 10 storiche)
4. **`document/TIMELINE.md`** ← storia cronologica (per archeologia di scelte specifiche)
5. **`document/P_S.md`** ← problemi/soluzioni P1-P52 (per debug di pattern noti)
6. **`document/FUTURE_WORK.md`** ← opzioni di proseguimento (F2/F3/F4/F5/F6)
7. **`document/AUDIT_2026-06-02.md`** ← bilancio onesto pre-RESET (riferimento storico)

## Glossario rapido sigle

- **R24F**: Prodigy MultiParam PostFix (93 run). Generazione che ha prodotto `R24F_MIXED_lr0.5_V08_TRUE_CHAMPION`.
- **R25-R29**: studi su baseline INSTABILE lr=1.0 (mantenuti per pattern, non per metriche).
- **R30**: Identifiability (4-tuple loader + auxiliary supervision).
- **R31**: Champion Validation (3 champion candidati identificati).
- **R32**: Restart Mechanisms (5 meccanismi soft × 2 baseline).
- **R33**: Closure (2 correzioni mirate + 2 nuovi champion finali).
- **C3 decoder**: DEC-1 (per-channel τ-annealing) + DEC-3 (init_bias_shift). Tutti i champion post-R29 lo usano.
- **DEC-1/2/3**: tre ipotesi decoder fix R29. DEC-2 (τ-annealing) bocciato. DEC-1+DEC-3 attivi.
- **T_intra_corr**: Pearson(T_pred, T_true) dopo rimozione media per-sample. Misura "tracking del T" depurato da bias cross-driver.
- **gn_total_preclip**: norma gradiente totale PRIMA del `clip_grad_norm_(1.0)`. Vera metrica di stabilità.
- **Po2**: Power-of-2 quantization (per FPGA bit-shift instead of multiply).
- **PINN**: Physics-Informed Neural Network (loss multi-componente: data + phys + ou + bc + sr).

## Come riprodurre un champion

Ogni champion ha il proprio CLI completo nella sezione "Riproduzione" del suo README:
- `Arch_Tested/R33_C1_A4_T12_PEAK/README.md` (PEAK)
- `Arch_Tested/R33_C2_A1_T12_CLEAN/README.md` (CLEAN)
- `Arch_Tested/R32_B5_E1_STABLE/README.md` (STABLE)
- `Arch_Tested/R24F_MIXED_lr0.5_V08_TRUE_CHAMPION/README.md` (BASELINE storico)

Esempio CLEAN (deploy candidate):

```bash
cd Arch_Tested/R33_C2_A1_T12_CLEAN/
cat README.md   # vedi sezione "Riproduzione"
# Riproduzione full (50 ep):
python ../../train.py --training_method baseline \
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

Risultato atteso (entro tolleranza seed): Tp ≈ 0.052, val_data ≈ 0.165, 50/50 ep, gn_max < 100.

## In caso di problemi noti

| Sintomo | Causa | Fix |
|---|---|---|
| `SyntaxError: f-string ... backslash` Python 3.10 | `\'` in f-string (vietato fino a 3.12) | Split ternary in if/else (cf. Cell 3 di tutti gli R32+ notebooks) |
| Run abortisce a ep<30 con gn_max~10⁵-10¹⁹ | Setup instabile (lr troppo alto, T0 errato) | Verifica `restart_T0=12`, `lr=0.5`, e cfr. R32_A1 base |
| `T_intra_corr ≈ 0` epoche iniziali | Rank-collapse (vedi R27) | Attivare supervisione ausiliaria 4-tuple (lambda_T_aux > 0) |
| `gn_postclip` sempre = 1.0 ma val_loss oscilla | `gn_preclip` esploso ma mascherato | Misura `max_gn_preclip` da `training_batch_log.csv` |
| Notebook fallisce su Azure ma OK locale | Python 3.13 vs Azure 3.10 | `python -c "import ast; ast.parse(open('X.ipynb').read(), feature_version=(3,10))"` |

## Repository

- **Remote**: `https://github.com/carmineesposito01-ice-beep/SNN_Experiment.git`
- **Owner**: carmineesposito01-ice-beep
- **Branch protetto**: `main` (push diretto richiede approvazione esplicita)
- **Cluster Azure**: `sandokan` (ML compute, Python 3.10)
- **Path Azure**: `/mnt/batch/tasks/shared/LS_root/mounts/clusters/sandokan/code/SNN_Experiment/`
