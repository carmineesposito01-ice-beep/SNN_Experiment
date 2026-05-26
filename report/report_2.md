# CF_FSNN — Report di Stato #2
> Allineamento del progetto: ACC-IDM con base IIDM, scenari cut-in, diagnostica completa.
> Data: 2026-05-25

---

## 1. OBIETTIVO DI QUESTO MILESTONE

Il training iniziale (report_1.md) ha evidenziato tre problemi critici:
1. **Best epoch = 1/20**: il ReduceLROnPlateau abbassa il LR troppo presto, bloccando la rete nel minimo locale del primo passo
2. **Bias v₀ (+16%)**: il modello fisico IDM plain non separa correttamente i regimi free-flow e car-following
3. **Varianza T compressa (4×)**: il λ_OU probabilmente troppo basso, più lo scheduler che penalizza l'esplorazione

Questo milestone interviene su tutti e tre i fronti aggiornando il codice di simulazione e training.

---

## 2. MODIFICHE EFFETTUATE

### 2.1 `config.py` — Parametri ACC-IDM e cut-in aggiunti

| Parametro nuovo | Valore | Significato |
|---|---|---|
| `ACC_COOLNESS` | 0.99 | Coolness factor CAH (fisso — non predetto dalla rete) |
| `ACC_AL_TAU`   | 1.0 s | Costante di tempo filtro OU stima a_l da V2X |
| `CUT_IN_RATIO` | 0.20 | 20% degli scenari sono cut-in (UC2 coverage) |
| `CUT_IN_S_MIN` | 5.0 m | Gap minimo subito dopo il cut-in |
| `CUT_IN_S_MAX` | 15.0 m | Gap massimo subito dopo il cut-in |
| `CUT_IN_DV_MAX`| 5.0 m/s | Differenza di velocità massima al cut-in |

### 2.2 `data/generator.py` — ACC-IDM sostituisce IDM plain

**Funzione rimossa** (mantenuta per riferimento come `_idm_accel()`):
- `_idm_accel()` → formula IDM pura, usata nel primo run

**Funzione aggiunta — nucleo fisico:**
- `_acc_iidm_accel(s, v, v_l, a_l, params, c)` → ACC-IDM con IIDM base
  - IIDM: regime free-flow (`z < 1`) separato dal car-following (`z >= 1`)
  - Formula IIDM: `a_ff = v_free*(1-z²)` vs `a_cf = v_free - a*(z²-1)/(1+z)²`
  - CAH: `a_CAH = v²·ā_l / (v·ā_l/s + Δv²/(2s))` con `ā_l = min(a_l, a)`
  - Blend: `a_ACC = (1-c)·a_IIDM + c·[a_CAH + b·tanh((a_IIDM-a_CAH)/b)]`

**Funzione aggiunta — stima a_l:**
- Nella simulazione, `a_l` è stimata da differenze finite su `v_l` con filtro OU (τ=1s): `a_l_filt[t] = α·a_l_filt[t-1] + (1-α)·(v_l[t]-v_l[t-1])/Δt`

**Funzione aggiunta — cut-in (UC2):**
- `simulate_cut_in_trajectory(params, profile, seed)`:
  - Leader A per [0, t_cutin): traiettoria normale
  - Evento cut-in a t_cutin: gap si imposta a s_cutin ∈ [5, 15] m
  - Leader B per [t_cutin, fine): veicolo più lento (test risposta CAH)

**`_sample_scenario()`** aggiornata: ogni scenario è marcato `cut_in=True` con probabilità `CUT_IN_RATIO`. Il dataset restituisce anche il campo `'cut_in': bool`.

### 2.3 `core/network.py` — Metodo `acc_iidm_accel()` aggiunto

Aggiunto metodo statico a `CF_FSNN_Net`:

```python
@staticmethod
def acc_iidm_accel(s, v, dv, a_l, params, coolness=0.99) -> Tensor
```

- Versione torch (differenziabile) di `_acc_iidm_accel()` del generatore
- Sostituisce `idm_accel()` nella `pinn_loss()` di train.py
- `idm_accel()` mantenuto per backward compatibility e confronto

### 2.4 `train.py` — Argparse completo, scheduler, CSV, diagnostica

**Argparse** — nuovi flag disponibili:

| Flag | Default | Note |
|---|---|---|
| `--scheduler` | `plateau` | `plateau` \| `onecycle` \| `cosine` |
| `--max_lr` | 5e-3 | Per `OneCycleLR` |
| `--T0` | 5 | Per `CosineAnnealingWarmRestarts` |
| `--lambda_data/phys/ou/bc` | config.py | Override lambda PINN a runtime |
| `--optimizer` | `adam` | `adam` \| `adamw` \| `lion` |
| `--tag` | `run` | Cartella `checkpoints/<tag>/` |
| `--batch_size` | 64 | Sostituisce il vecchio `--batch` |

**Scheduler implementati:**
- `plateau`: `ReduceLROnPlateau(factor=0.5, patience=10)` — default conservativo
- `onecycle`: `OneCycleLR(max_lr, pct_start=0.3, div_factor=10)` — per Stage A (evita best=epoch1)
- `cosine`: `CosineAnnealingWarmRestarts(T_0)` — per run lunghi con restart

**Note OneCycleLR**: steppato per-batch (corretto), non per-epoca. `train_epoch()` riceve il scheduler e lo chiama dopo ogni `optimizer.step()`.

**Optimizer Lion** (`LionOptimizer`):
- Implementato inline in `train.py`
- Update sign-based: `θ -= lr · sign(β₁·m + (1-β₁)·g)`
- 3-4× meno memoria di Adam
- Hardware-friendly: se `lr` è power-of-2, l'update è un bit-shift su FPGA

**Physics in `pinn_loss()`**:
- Usa `CF_FSNN_Net.acc_iidm_accel()` invece di `idm_accel()`
- `a_l` stimata in-loop da diff. finite su `v_l` + EMA (alpha = exp(-Δt/τ_al))
- Loop esplicito sull'asse temporale (non vettorizzato) per correttezza OU

**Output strutturato per run:**
```
checkpoints/<tag>/
  ├── best_model.pt
  ├── last_model.pt
  ├── training_log.csv
  ├── config_snapshot.json
  └── plots/
      ├── G1_loss_curve.png
      ├── G2_components.png
      ├── G3_lr_schedule.png
      ├── G4_grad_norm.png
      ├── G6_spike_rate.png
      └── (G5/G7 se forniti i dati)
```

### 2.5 `utils/plot_diagnostics.py` — Sistema di diagnostica (nuovo)

Genera i 7 grafici standard:

| Grafico | Contenuto | Dati richiesti |
|---|---|---|
| G1 | Curva loss train/val | training_log.csv |
| G2 | Componenti loss (log-scale) | training_log.csv |
| G3 | Schedule LR per epoca | training_log.csv |
| G4 | Grad norm per epoca + linea clip=1.0 | training_log.csv |
| G5 | Scatter T_pred vs T_true + diagonale | array T_pred, T_true |
| G6 | Spike rate [%] + banda target 10-20% | training_log.csv |
| G7 | Violin plot 5 parametri con bound fisici | dict param_samples |

`matplotlib` è opzionale: se non installato, i grafici vengono saltati senza crash.

**CSV logging** (`training_log.csv`):
```
epoch, train_total, train_data, train_phys, train_ou, train_bc,
val_total, val_data, val_phys, val_ou, val_bc,
lr, grad_norm, spike_rate, time_s
```

---

## 3. STATO CORRENTE DEL TRAINING

### 3.1 Metriche — Risultato del run precedente (report_1.md)

| Metrica | Valore osservato | Target Stage A/B/C | Target full |
|---|---|---|---|
| SRMSE (test) | **0.871** | < 0.5 | < 0.3 |
| T bias | **+0.15 s** | < +0.08 s | < +0.03 s |
| T σ_pred / σ_true | **0.25 (compressa 4×)** | > 0.50 | > 0.80 |
| v₀ bias | **+16%** | < +8% | < +5% |
| Best epoch | **1/20** | > 3/5 | > 10/50 |
| Spike rate hidden | sconosciuto | 10–20% | 10–20% |

> **Nessun run è stato eseguito con la nuova configurazione.** I numeri sopra si riferiscono al run con IDM plain e ReduceLROnPlateau (patience=5). Il nuovo baseline andrà stabilito con Stage A.

### 3.2 Cause dei problemi (analisi confermata)

1. **Best epoch = 1**: ReduceLROnPlateau(patience=5) abbassa il LR già a epoca 5-6, bloccando l'ottimizzazione. → **Fix: OneCycleLR o CosineAnnealing per Stage A**
2. **Bias v₀ (+16%)**: IDM plain non separa i regimi → i veicoli non raggiungono esattamente v₀. → **Fix: IIDM base già implementato**
3. **Varianza T compressa**: λ_OU basso + LR basso troppo presto → la rete non esplora. → **Fix: OneCycleLR + sweep λ_OU in Stage C**
4. **No cut-in nel dataset**: rete non esposta a UC2 → generalizzazione limitata. → **Fix: 20% cut-in ora presente nel generatore**

---

## 4. PROSSIMI PASSI — PROCEDURA STAGE A/B/C

### Stage A — Fix scheduler (5 epoche, GPU locale)

```bash
python train.py --epochs 5 --scheduler onecycle --max_lr 5e-3 --tag A1_onecycle
python train.py --epochs 5 --scheduler cosine   --T0 5        --tag A2_cosine
python train.py --epochs 5 --scheduler plateau  --lr 1e-3     --tag A3_plateau
```

**Criterio di successo**: val_loss scende monotonicamente dopo ep.1, pendenza negativa a ep.5.
→ Il vincitore viene usato in Stage B.

### Stage B — Sweep LR (5 epoche, scheduler vincitore di A)

```bash
python train.py --epochs 5 --scheduler <winner_A> --lr 3e-4 --tag B1_lr3e4
python train.py --epochs 5 --scheduler <winner_A> --lr 1e-3 --tag B2_lr1e3
python train.py --epochs 5 --scheduler <winner_A> --lr 3e-3 --tag B3_lr3e3
```

### Stage C — Sweep λ_OU (5 epoche, best A+B)

```bash
python train.py --epochs 5 --lambda_ou 0.05 --lambda_bc 1.0 --tag C1_baseline
python train.py --epochs 5 --lambda_ou 0.20 --lambda_bc 0.5 --tag C2_ou_up
python train.py --epochs 5 --lambda_data 2.0 --lambda_phys 0.05 --lambda_ou 0.20 --tag C3_data_first
python train.py --epochs 5 --lambda_phys 0.20 --lambda_ou 0.10 --tag C4_phys_up
```

### Full training (dopo A+B+C)

```bash
python train.py --epochs 50 --tag FULL_v1
# Con configurazione vincente (scheduler, lr, lambda)
```

---

## 5. CHECKLIST PRE-RUN

```bash
# 1. Verifica CUDA
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# Atteso: True  NVIDIA GeForce RTX 3060

# 2. Smoke test CPU (< 5 min)
python train.py --epochs 3 --n_train 200 --n_val 50 --batch_size 16 --tag SMOKE

# 3. Verifica grafici generati
# ls checkpoints/SMOKE/plots/
```

---

## 6. NOTE DI ARCHITETTURA

### Perché ACC-IDM con base IIDM (e non IDM plain)?

| Aspetto | IDM plain | ACC-IDM (IIDM base) |
|---|---|---|
| Bias v₀ | Presente (mai raggiunge esattamente v₀) | Assente (IIDM separa i regimi) |
| Risposta cut-in (UC2) | Panic braking istantaneo | Graduale (CAH anticipa il leader) |
| Stima a_l | Non usata | Stimata da diff. finite + OU |
| Complessità FPGA | ~3 DSP | ~5-10 DSP (< 5% dei 220 disponibili) |

### Perché OneCycleLR per Stage A?

Il "best=epoch 1" è causato da:
- LR iniziale troppo alto → instabilità nel primo batch
- Scheduler che abbassa il LR troppo presto → congelamento

OneCycleLR ha un **warmup** (30% epoche): LR cresce da `max_lr/10` a `max_lr`, poi decresce. Questo permette alla rete di "scaldarsi" prima di scendere steeply verso il minimo. Tipicamente porta best_epoch > 3/5 già a 5 epoche.

### Lion vs Adam

| Ottimizzatore | Stato memoria | Update | FPGA-friendly |
|---|---|---|---|
| Adam | 2× parametri | m/v adattivo | No (divisione fp) |
| AdamW | 2× parametri | m/v + wd | No |
| Lion | 1× parametri | sign-based | Sì (bit-shift se lr=Po2) |

Lion è preferito per il training finale (FULL_v1) data la compatibilità hardware.

---

## 7. FILE MODIFICATI IN QUESTO MILESTONE

| File | Tipo modifica |
|---|---|
| `config.py` | Aggiunto: ACC_COOLNESS, ACC_AL_TAU, CUT_IN_* |
| `data/generator.py` | Riscritto: ACC-IIDM, a_l OU, simulate_cut_in_trajectory() |
| `core/network.py` | Aggiunto: acc_iidm_accel() statico |
| `train.py` | Riscritto: full argparse, 3 scheduler, Lion, CSV logger, tag dir |
| `utils/__init__.py` | Nuovo |
| `utils/plot_diagnostics.py` | Nuovo: 7 grafici G1-G7 |
| `document/report_2.md` | Nuovo (questo file) |

---

> **Documenti correlati:**
> - `optimization_ideas.md` — analisi completa idee e razionale
> - `training_plan.md` — procedura esecutiva Stage A/B/C
> - `cf_model_recommendation.md` — analisi modello ACC-IDM
> - `project_core_guidelines.md` — core del progetto
> - `report_1.md` — risultati del primo run (baseline)
