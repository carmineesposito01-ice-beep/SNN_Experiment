# CF_FSNN — Come Funziona

> ⚠️ **SUPERATO da `HOW_IT_WORKS_v3.md` / `.pdf` (2026-07-01).** Questa versione v1 è storica e contiene
> dettagli ORMAI OBSOLETI rispetto al codice attuale (es. F5 pre-scaling nel decode — rimosso; `s_safe=0.5`
> — ora 2.0; L_data SRMSE su energia — ora RMSE/N_valid; equazioni IIDM/CAH §11.2–11.3 diverse dal codice).
> Per la descrizione aggiornata e completa (incl. EventProp, ρ spettrale, i 4 champion) usa **v3**.

> **Versione**: 2026-05-29 (post commit `534c2af`)
> **Lettore atteso**: ingegnere/ricercatore che non conosce il progetto, vuole capire architettura, training e pipeline in mezz'ora.
> **Scope**: descrizione del codice attuale. Niente storia dei tentativi, niente decisioni passate (per quelle vedi `TIMELINE.md`, `P_S.md`, `GLOSSARY.md`).

---

## 1. Sommario in una pagina

**Cosa fa.** CF_FSNN è una rete neurale **spiking** che, osservando in tempo reale un veicolo follower (gap, velocità, Δv, velocità leader via V2X), **identifica i 5 parametri del modello ACC-IIDM** che meglio descrivono il driver: `[v0, T, s0, a, b]` (vedi Treiber & Kesting Ch12).

**Perché spiking e non MLP.** Target di deployment: **PYNQ-Z1 FPGA** (a basso costo). SNN + pesi power-of-two + bit-shift leak → tutti i moltiplicatori diventano shift register sull'FPGA. Ordine di grandezza di risparmio area/energia.

**Architettura in una riga.**
```
input(4) ─ Hidden ALIF(32 neur., rank-8 ricorrenza, max-delay 6) ─ Output LI(5) ─ sigmoid+bounds ─ [v0,T,s0,a,b]
```
864 parametri totali (baseline).

**Loss in una riga.** PINN a 5 componenti: `λ_data·RMSE + λ_phys·MSE_ACC_IDM + λ_OU·OU_residuo_T + λ_bc·crash + λ_sr·spike_rate_reg`.

**Dataset.** Sintetico ACC-IDM (Treiber+Kesting) — 4 scenari: highway, urban, truck, mixed. 100 s/traj, packet loss V2X 2%, T(t) stocastico (jump Markov τ=30s, banda [0.8, 1.6]s).

**Telemetria.** Per-epoca CSV (16 colonne) + per-batch CSV (20 colonne, ~190 KB/epoca) + 13 grafici diagnostici (G1–G13) generati a fine training.

---

## 2. Architettura della rete

### 2.1 Diagramma a blocchi

```
V2X input              HiddenLayer_ALIF                OutputLayer_LI       Decode fisico
[s,v,Δv,v_l]    →    32 neuroni spiking         →    5 LI integratori →   sigmoid +
(batch, 4)           (rank-8 recurrenza)              (lineari)            range physical
                     (max-delay 6 tick)               (batch, 5 raw)       → [v0,T,s0,a,b]

                     |── ricorrenza low-rank: U(32×8)·V(8×32) ──|
```

Il ciclo interno: **per ogni step temporale del dataset si eseguono `TICKS_PER_STEP=10` tick SNN** (BPTT depth reale = `seq_len × 10`).

### 2.2 ALIF cell (Adaptive Leaky Integrate-and-Fire)

Stato per neurone: potenziale `V` + adattamento di soglia (fatica) `F`.

```
# Membrana (bit-shift leak: leak = V/8)
V  ← V − (V >> 3) + I_input + I_rec

# Soglia adattativa
θ_eff = base_threshold + F
spike = surrogate_heaviside(V − θ_eff)
F     ← F − (F >> 3) + spike · thresh_jump   # spike-frequency adaptation

# Reset soft (sottrattivo, preserva eccesso)
V     ← V − spike · θ_eff
```

| Parametro per neurone | Init | Shape | Apprendibile |
|---|---|---|---|
| `base_threshold` | 1.5 | (32,) | sì |
| `thresh_jump` | 0.5 | (32,) | sì |

### 2.3 Surrogate gradient (forward Heaviside, backward smooth)

Necessario perché il gradiente di `H(V−θ)` è zero quasi ovunque → BPTT impossibile.

```
forward:   spike = (V ≥ θ).float()
backward:  ∂spike/∂V = 1 / (1 + γ·|V − θ|)²
```

- `γ = 1.0` (commit A3 del 2026-05-27, era 0.3). Kernel più stretto → meno neuroni che contribuiscono al sum-grad → minor rischio amplificazione catastrofica via U·V ricorrenza.

### 2.4 Low-rank recurrence (rank=8)

Invece di una matrice ricorrente piena `W_rec ∈ ℝ^{32×32}` (1024 pesi), si fattorizza:

```
I_rec(t) = (V · (U · spike(t−1)))  con U ∈ ℝ^{32×8}, V ∈ ℝ^{8×32}
                                   → 256+256 = 512 pesi (50%)
```

Inizializzazione: ortogonale gain 0.2 (stabilità BPTT).

### 2.5 Delays assonali (ring buffer)

Ogni sinapsi feedforward `fc_weight[i,j]` ha un ritardo intero `d ∈ [0, 5]` campionato all'init. Sul forward, l'input `j` contribuisce al neurone `i` solo dopo `d` tick → modella ritardo trasmissione FPGA (`6 × DT/TICKS = 0.06 s`).

### 2.6 Output layer LI (Leaky Integrate, no spike)

```
I_out = W_po2 · spike_hidden            # W_po2: matrice power-of-two quantizzata, 5×32
V_out ← V_out − (V_out >> 3) + I_out
return V_out                             # raw output, 5 numeri reali
```

### 2.7 Decoding nei 5 parametri fisici IDM

```
raw_eq = raw / decode_scale                                  # F5 pre-scaling
param  = lo + (hi − lo) · sigmoid(raw_eq)                    # bounded a (lo, hi)
```

**Bounds fisici** (da Treiber Ch12 tabella):

| Param | Lo | Hi | Range |
|---|---|---|---|
| v0 [m/s] | 8.0 | 45.0 | 37.0 |
| T [s] | 0.5 | 2.5 | 2.0 |
| s0 [m] | 1.0 | 5.0 | 4.0 |
| a [m/s²] | 0.3 | 2.5 | 2.2 |
| b [m/s²] | 0.5 | 3.0 | 2.5 |

**decode_scale** (F5 — gradient balancing): senza, il gradiente che arriva a `raw_v0` sarebbe `37/2 = 18.5×` quello a `raw_T` (perché i range differiscono). Con `decode_scale_i = (hi−lo)_i / max(hi−lo) = [1.0, 0.054, 0.108, 0.059, 0.068]`, tutti i parametri hanno la stessa sensibilità al gradiente → la rete impara `T, s0, a, b` alla stessa velocità di `v0`.

### 2.8 Conta dei parametri (baseline h=32, r=8)

| Tensore | Shape | Params |
|---|---|---|
| `layer_hidden.fc_weight` | (32, 4) | 128 |
| `layer_hidden.rec_U` | (32, 8) | 256 |
| `layer_hidden.rec_V` | (8, 32) | 256 |
| `layer_hidden.cell.base_threshold` | (32,) | 32 |
| `layer_hidden.cell.thresh_jump` | (32,) | 32 |
| `layer_out.fc_weight` | (5, 32) | 160 |
| **Totale** | | **864** |

(Lo sweep STEP 2B ha testato anche h=48/64/96/128 → 1685/2757/5669/9605 params.)

---

## 3. Loss PINN (Physics-Informed Neural Network)

`pinn_loss()` ritorna `L_total + dict componenti + spike_rate`.

```
L_total = λ_data·L_data + λ_phys·L_phys + λ_OU·L_OU + λ_bc·L_bc + λ_sr·L_sr
```

| λ | Default | Cosa fa | Formula |
|---|---|---|---|
| `λ_data` | 1.0 | **Fit dati**: l'accelerazione predetta dai parametri identificati matcha il ground truth ACC-IDM (mascherato sui pacchetti V2X effettivamente ricevuti) | `√(Σ mask·(â − ȧ_gt)² / N_valid + ε)` |
| `λ_phys` | 0.1 | **Coerenza fisica**: stessa cosa ma su TUTTI gli step (anche dove V2X è mancante) | `mean((â − ȧ_gt)²)` |
| `λ_OU` | 0.05 | **T(t) segue il processo OU**: la sequenza di T predetti rispetta la mean-reversion verso `T_mean=1.2s` con `α=exp(−Δt/τ_OU)=0.9967` | `mean((T_{t+1} − (α·T_t + (1−α)·T_mean))²)` |
| `λ_bc` | 1.0 | **No-crash**: penalizza se `s0_pred > s_observed` (la rete predice una distanza minima superiore al gap reale → crash) | `mean(ReLU(s0_pred − s_obs + 0.1)²)` |
| `λ_sr` | 0.5 | **Sparsity target**: forza la spike rate del hidden layer verso il 15% (B5 — antidoto a "dead network") | `(mean(spike_rate) − 0.15)²` |

**Nota su L_OU**: il generatore implementa T(t) come **processo di salto Markoviano** (`p=DT/τ=0.003/step`, jump uniforme in `[T1, T2]`), non un OU continuo. Quindi `L_OU` ha un floor irriducibile `≈ 1.8e-4` dovuto alla varianza dei salti.

---

## 4. Training loop

### 4.1 Pseudocodice

```
for epoch in range(epochs):
    for batch (x_seq, y_seq, mask_seq) in train_loader:
        # x_seq: (B, T, 4) input V2X normalizzato
        # y_seq: (B, T, 6) ground truth [v_dot, T_true, s, v, dv, v_l]

        params_seq = model.forward_sequence(x_seq)   # (B, T, 5)
        loss, comps, spike_rate = pinn_loss(params_seq, y_seq, mask_seq, x_seq)

        loss.backward()
        pre_norms = {name: p.grad.norm() for name, p in model.named_parameters()}
        gn_pre  = total_norm(pre_norms)
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        gn_post = total_norm(model.parameters())

        optimizer.step()
        batch_logger.log(epoch, batch_idx, comps, spike_rate, pre_norms, gn_pre, gn_post)
        if inf_streak >= max_inf_streak: EARLY_STOP_EXPLOSION

    val_loss = validate(model, val_loader)
    csv_logger.log(epoch, ..., val_loss, lr, grad_norm)
    scheduler.step()
    if val_loss < best - delta: save_checkpoint(); patience_counter = 0
    else: patience_counter += 1
    if patience_counter >= patience: EARLY_STOP_PLATEAU
```

### 4.2 Hyperparameter di training (default config.py)

| Cosa | Default | Override CLI | Note |
|---|---|---|---|
| Optimizer | Adam | `--optimizer adam|lion` | Lion = sign-based, 3-4× meno memoria, hardware-friendly |
| LR base | 1e-3 | `--lr` | |
| Scheduler | plateau | `--scheduler onecycle|cosine|plateau` | OneCycle: 1 ciclo super-conv. Cosine: warm restart. Plateau: riduce su val_loss stalla |
| `max_lr` (onecycle) | 5e-3 | `--max_lr` | |
| Gradient clip | 1.0 | hard-coded | Critico per BPTT con surrogate gradient |
| Early stop patience | 0 (disab.) | `--early_stop_patience` | Tipico STEP 2A: 2 |
| Early stop delta | 1e-4 | `--early_stop_delta` | STEP 2A: 0.005 (aggressivo) |
| `max_inf_streak` | 20 | `--max_inf_streak` | Aborto se 20 batch consecutivi hanno grad inf |

### 4.3 Quantizzazione Power-of-Two (forward only)

Sui pesi `fc_weight`, `rec_U`, `rec_V`, `feedback_w`:

```
forward:
  sign = sign(w)
  log2 = clamp(round(log2(|w|)), -4, 1)
  mask = (|w| > 2^-5).float()         # zera pesi sotto 1/32
  w_q  = sign · 2^log2 · mask

backward: ∂w_q/∂w = 1   (Straight-Through Estimator)
```

Gamut: 6 valori non nulli per polarità → 13 livelli totali (incluso zero). Sull'FPGA: ogni moltiplicazione = 1 bit-shift.

---

## 5. Dataset (data/generator.py)

### 5.1 Scenari ACC-IDM

| Scenario | v0 [m/s] | T [s] | s0 [m] | a [m/s²] | b [m/s²] | δ |
|---|---|---|---|---|---|---|
| highway | 33.3 (120 km/h) | 1.2 | 2.5 | 1.1 | 1.5 | 4 |
| urban | 15.0 (54 km/h) | 1.0 | 2.0 | 1.5 | 2.0 | 4 |
| truck | 22.2 (80 km/h) | 1.8 | 3.0 | 0.5 | 1.0 | 4 |
| mixed | (sample casuale) | | | | | |

`SCENARIO_MIX` default: `highway 50%, urban 30%, truck 10%, mixed 10%`.

### 5.2 Generazione di una traiettoria

```
for t in range(0, 1000):           # 1000 steps × 0.1 s = 100 s
    # Aggiorna T(t) stocastico (Ch12.6 IDM-2d)
    T_now = jump_markov(T_prev, p=DT/τ=0.003, band=[0.8, 1.6])

    # ACC-IDM (Treiber Ch12 §12.4):
    s_star = s0 + max(0, v·T + v·Δv / (2√(a·b)))
    a_idm  = a · (1 − (v/v0)^δ − (s_star/s)²)
    a_cah  = ... (Constant-Acceleration Heuristic)
    v_dot  = blend_acc_iidm(a_idm, a_cah, coolness=0.99)

    # Step ballistico (Treiber Ch11)
    v_new  = v + v_dot·DT
    s_new  = s − (v_leader − v)·DT

    # Packet loss V2X (2%)
    mask = 1 if rand() > 0.02 else 0

    traj[t] = [s, v, dv, v_l, v_dot, T_now, mask]
```

20 secondi iniziali di warmup vengono esclusi dalla loss (per evitare transient).

### 5.3 Cut-in (UC2)

`CUT_IN_RATIO=0.20` (default): il 20% delle traiettorie ha un cut-in event a un istante random. Il leader cambia bruscamente, gap si riduce a `U(5, 15)m` con `Δv` istantanea fino a 5 m/s. Stress test per ACC.

### 5.4 Cache

Le traiettorie generate sono cachate in `data/cache_<n_train>_<scenario>_cut<x>.pt` per riutilizzo cross-run con stesso dataset.

---

## 6. Hardware-aware design (FPGA PYNQ-Z1)

| Feature | Cosa | Beneficio FPGA |
|---|---|---|
| **Power-of-Two weights** | `w ∈ {±2^k, 0}`, k ∈ [−4, 1] | Moltiplicazione → shift register |
| **Bit-shift leak** | `V ← V − (V>>3)` | Decadimento esponenziale gratis |
| **Low-rank rank=8** | 50% pesi ricorrenti | Memoria DDR ridotta |
| **Soft reset sottrattivo** | `V ← V − spike·θ` | Reset senza divisore |
| **Surrogate hardware-friendly** | `1/(1+γ|V−θ|)²` con γ=1 | Approx LUT |
| **Delays come ring buffer** | `O(1)` insert | Memoria ciclica |
| **Sparsity 10–25%** | (target B5) | Energia ∝ spike count, non ∝ MAC |

---

## 7. Telemetria

### 7.1 `training_log.csv` (per-epoca, 16 colonne)

```
epoch, train_total, train_data, train_phys, train_ou, train_bc, train_sr,
       val_total,   val_data,   val_phys,   val_ou,   val_bc,   val_sr,
       lr, grad_norm, spike_rate, time_s
```

### 7.2 `training_batch_log.csv` (per-batch, 20 colonne, ~190 KB/epoca)

```
epoch, batch_idx,
loss_total, loss_data, loss_phys, loss_ou, loss_bc, loss_sr,
spike_rate,
gn_total_preclip, gn_total_postclip,
gn_hidden_fc, gn_hidden_recU, gn_hidden_recV,
gn_hidden_base_threshold, gn_hidden_thresh_jump, gn_out_fc,
weight_max_abs_global, lr,
is_nan_loss, is_inf_grad
```

Append-only, flush ogni 50 batch (~1 ms overhead). Costo trascurabile. Permette analisi post-mortem anche se il training crasha.

### 7.3 I 13 grafici diagnostici

**Per-epoca** (G1–G7):

| # | Titolo | Cosa diagnostica |
|---|---|---|
| G1 | Loss curve train/val | Convergenza, divergenza, generalizzazione |
| G2 | Componenti loss (log) | Quale dei 5 termini PINN domina o esplode |
| G3 | LR schedule | Se lo scheduler funziona come previsto |
| G4 | Gradient norm pre-clip | Exploding/vanishing gradient, soglia clip |
| G5 | Scatter T_pred vs T_true | Quanto bene la rete identifica T |
| G6 | Spike rate per epoca | Sparsity collapse (dead) o saturation |
| G7 | Violin params [v0,T,s0,a,b] | Distribuzioni predette dentro/fuori range fisico |

**Per-batch** (G8–G12):

| # | Titolo | Cosa diagnostica |
|---|---|---|
| G8 | grad_norm per batch (log) | Quando esattamente esplode il gradiente |
| G9 | Heatmap norme per-layer × batch | Quale layer è il primo a esplodere |
| G10 | Componenti loss per batch | Loss divergence in tempo reale |
| G11 | Spike rate per batch | Oscillazione/collasso sparsity |
| G12 | Weight max abs per batch | Sintomo precoce di esplosione |

**Validazione fisica** (G13):

| # | Titolo | Cosa diagnostica |
|---|---|---|
| G13 | Traiettoria val: signals vs params predetti (3 scenari) | La rete predice IDM params che, simulati, ricostruiscono la traiettoria? Confronto visivo con GT |

### 7.4 Crash/recovery

Se il training si abortisce per esplosione gradiente (`inf_streak ≥ max_inf_streak`):
1. Si salva `crash_model.pt` con lo state al momento del crash
2. Si salva `best_model.pt` con la migliore val_loss vista finora
3. CSV per-batch contiene già tutti i dati fino al crash → analisi post-mortem completa

---

## 8. Workflow di esecuzione

### 8.1 Esperimento singolo (Training_File.ipynb)

```
Cella 0  → bootstrap (dipendenze, status repo)
Cella 1  → CONFIG (l'unica da modificare): TAG, epochs, scheduler, scenario_mix, ecc.
Cella 2  → git pull + sanity check imports
Cella 3  → cache management
Cella 4  → preflight (2 smoke consecutivi, criteri pass/fail)
Cella 5  → FULL train (subprocess)
Cella 6  → display grafici G1–G13
Cella 7  → analisi numerica
Cella 8  → copia checkpoints → results/ + git commit + push
Cella 9  → comparazione cross-esperimenti
```

### 8.2 Sweep parametrico (Training_File_Sweep.ipynb)

```
Cella 0  → bootstrap (install matplotlib + nbstripout)
Cella 1  → SWEEP_PLAN: lista di N esperimenti come dict-override dei DEFAULTS
Cella 2  → helper (_cache_path, _build_cli_args, _push_results)
Cella 3  → loop: per ogni run → preflight → train → push results (per-run, robust)
Cella 4  → tabella summary (sweep_summary_<ts>.csv)
Cella 5  → 6 grafici cross-run (S1–S6)
Cella 6  → push aggregati (summary CSV + plots/) su git
```

### 8.3 Preflight (scripts/preflight.py)

Eseguito automaticamente dal notebook prima di ogni FULL ≥3 epochs. Lancia 2 smoke (1 epoca, ≤100 traj, ~2 min su CPU) consecutivi e verifica 7 criteri:

1. Exit code 0
2. Nessun `[EARLY-STOP]` esplosione
3. `training_log.csv` ≥ 1 riga
4. `training_batch_log.csv` ≥ 10 righe
5. ≥ 5 grafici PNG generati
6. `best_model.pt` ricaricabile (legge `cf_hidden_size`/`cf_rank` dal config_snapshot per evitare size mismatch)
7. Nessun `RuntimeError`/`Traceback` nello stdout

Se entrambi gli smoke passano → FULL safe. Altrimenti FULL non parte.

---

## 9. Riassunto config.py

```python
# Architettura
CF_INPUT_SIZE  = 4
CF_HIDDEN_SIZE = 32
CF_OUTPUT_SIZE = 5
CF_RANK        = 8
CF_MAX_DELAY   = 6
TICKS_PER_STEP = 10

# Fisica ACC-IDM
DT             = 0.1
ACC_COOLNESS   = 0.99
ACC_AL_TAU     = 1.0

# IDM-2d stocastico T(t)
IDM2D_T1       = 0.8
IDM2D_T2       = 1.6
IDM2D_TAU      = 30.0

# Loss weights
LAMBDA_DATA    = 1.0
LAMBDA_PHYS    = 0.1
LAMBDA_OU      = 0.05
LAMBDA_BC      = 1.0
LAMBDA_SR      = 0.5
SPIKE_RATE_TARGET = 0.15

# Training
BATCH_SIZE     = 64
LEARNING_RATE  = 0.001
EPOCHS         = 50

# Dataset
N_SCENARIOS_TRAIN = 5000
N_SCENARIOS_VAL   = 500
SIM_DURATION      = 120.0
WARMUP_DURATION   = 20.0
SCENARIO_MIX      = dict(highway=0.50, urban=0.30, truck=0.10, mixed=0.10)
CUT_IN_RATIO      = 0.20
V2X_PACKET_LOSS   = 0.02

# Normalizzazione input
NORM_S_MAX  = 150.0
NORM_V_MAX  = 40.0
NORM_DV_MAX = 20.0
NORM_VL_MAX = 40.0

# Hardware (core/hardware.py)
gamma          = 1.0    # surrogate (post A3)
bit_shift_leak = 3
po2_log2_range = (-4.0, 1.0)
po2_zero_thr   = 2**-5   # ~0.031
```

---

## 10. File principali

| File | Cosa contiene |
|---|---|
| `core/network.py` | `CF_FSNN_Net`, `HiddenLayer_ALIF`, `OutputLayer_LI`, decode params |
| `core/neurons.py` | `ALIFCell` (membrana, soglia, reset) |
| `core/hardware.py` | `Po2Quantize`, `SpikeFn` (surrogate), `_decode_*` helpers |
| `data/generator.py` | Generazione ACC-IDM, jump-Markov T(t), cut-in, packet loss |
| `train.py` | Training loop, `pinn_loss`, `BatchCSVLogger`, CLI args |
| `utils/plot_diagnostics.py` | Generazione G1–G13 da CSV + model |
| `scripts/preflight.py` | Doppio smoke + 7 criteri pass/fail |
| `Training_File.ipynb` | Notebook esperimento singolo |
| `Training_File_Sweep.ipynb` | Notebook sweep parametrico |
| `config.py` | Tutti i default |

---

## 11. Il modello fisico ACC-IIDM (target del PINN)

La rete identifica i parametri di un controllore ACC (Adaptive Cruise Control) basato su **IIDM + CAH blend** (Treiber & Kesting Ch12 §12.4). Conoscere le equazioni è prerequisito per capire `L_data` e `L_phys`.

### 11.1 IDM base (Intelligent Driver Model)

```
v̇_IDM = a · [ 1 − (v / v₀)^δ  −  (s*(v, Δv) / s)² ]

s*(v, Δv) = s₀ + max(0,  v·T  +  v·Δv / (2·√(a·b)) )
```

con:
- `s`, `v`, `Δv = v − v_leader` = stato osservato
- `v₀, T, s₀, a, b` = i 5 parametri identificati dalla rete (δ=4 fissato)
- `s*` = "desired gap" — funzione di v e Δv

### 11.2 IIDM (Improved IDM)

Elimina la "dispersione" di IDM a v≈v₀ separando i due regimi (free vs interacting):

```
For v ≤ v₀:
    v̇ = a·(1 − z²)                       se z = s*/s ≥ 1   [interacting]
    v̇ = a_free·(1 − z^(2a/a_free))       se z < 1           [free]
For v > v₀:
    v̇ = a_free + a·(1 − z²)·[z≥1]
```

dove `a_free = a·(1 − (v/v₀)^δ)`.

### 11.3 CAH (Constant Acceleration Heuristic)

```
v_CAH = v²·v̇_l / (v_l² − 2·s·v̇_l)            se s > v_l(v−v_l)/(−2v̇_l) AND v̇_l < 0
      = v̇_l − (v−v_l)²·Θ(v−v_l) / (2·s)     altrimenti
```

Anticipa che `v_l` continui con la sua attuale `v̇_l` (non worst-case). Riduce le over-reazioni nei cut-in lievi.

### 11.4 Blend ACC-IIDM

```
v̇_ACC = v̇_IIDM                                                          se v̇_IIDM ≥ v_CAH
      = (1−c)·v̇_IIDM + c·[v_CAH − b·tanh((v_CAH − v̇_IIDM)/b)]            altrimenti
```

con **coolness c=0.99** (default Treiber per ACC commerciali). c=0 ⇒ IIDM puro.

Questo è il `v̇_gt` usato come target da `L_data` e `L_phys`.

---

## 12. Esempio numerico: un forward pass

Caso concreto per validare la comprensione end-to-end.

### 12.1 Setup

Driver "highway" (v₀=33.3, T=1.2, s₀=2.5, a=1.1, b=1.5, δ=4). Stato osservato:

```
s     = 30.0 m          (gap follower-leader)
v     = 25.0 m/s        (velocità follower)
v_l   = 28.0 m/s        (velocità leader)
Δv    = v − v_l = −3.0 m/s
```

### 12.2 Ground truth ACC-IIDM (target)

```
s*  = 2.5 + max(0, 25·1.2 + 25·(−3)/(2·√(1.1·1.5)))
    = 2.5 + max(0, 30 − 29.2)
    = 2.5 + 0.8 = 3.3 m
z   = s*/s = 3.3/30 = 0.11
v̇_IDM = 1.1·(1 − (25/33.3)⁴ − 0.11²) ≈ 1.1·(1 − 0.317 − 0.012) ≈ 0.738 m/s²
```

(blend con CAH trascurabile in regime free; v̇_gt ≈ 0.74 m/s²)

### 12.3 Input normalizzato alla rete

```
s_norm    = 30.0 / 150.0  = 0.200
v_norm    = 25.0 / 40.0   = 0.625
dv_norm   = (−3.0)/20.0   = −0.150
v_l_norm  = 28.0 / 40.0   = 0.700
→ x_in = [0.200, 0.625, −0.150, 0.700]   shape (4,)
```

### 12.4 Propagazione (1 step temporale = 10 tick SNN)

Per ogni tick:
1. `fc_weight · x_in` → 32 currenti synaptiche (con delays applicati)
2. ALIF integra → ~3–5 dei 32 neuroni sparano (spike rate ~10–15%)
3. `rec_U·rec_V · spike_prev` → ricorrenza low-rank
4. Output LI accumula → `raw_out ∈ ℝ⁵` (in `raw_eq` = `raw/decode_scale`)

Dopo 10 tick, `raw_out` viene decodato:

```
raw_eq  = [+0.5, +1.2, −0.3, +0.8, +0.4]      (esempio)
sig     = [0.622, 0.769, 0.426, 0.690, 0.599]
params  = lo + (hi − lo) · sig
        = [8 + 37·0.622, 0.5 + 2·0.769, 1 + 4·0.426, 0.3 + 2.2·0.690, 0.5 + 2.5·0.599]
        = [31.0, 2.04, 2.70, 1.82, 2.00]
```

### 12.5 Loss su questo step

Calcoliamo `v̇_pred` usando ACC-IIDM con i `params` predetti e lo stato `[s, v, Δv]`:

```
s*  = 2.70 + max(0, 25·2.04 + 25·(−3)/(2·√(1.82·2.00))) = 2.70 + (51.0 − 6.21) = 47.5 m
z   = 47.5/30 = 1.583   (>1 → interacting)
v̇_pred = 1.82·(1 − (25/31)⁴ − 1.583²) ≈ 1.82·(1 − 0.422 − 2.506) ≈ −3.51 m/s²
```

Confronto:
```
v̇_gt   = +0.74
v̇_pred = −3.51
residuo = 4.25 m/s²
L_data (su questo singolo step) ≈ 4.25² → contribuisce 18 al cumulativo SRMSE
```

→ la rete predice un decel a freno mentre la fisica dice di continuare ad accelerare. **Questo è ciò che l'allenamento corregge minimizzando `L_data` su milioni di step**.

---

## 13. Criteri quantitativi di "funziona bene"

Il valore di `val_loss` da solo non basta. Definiamo soglie per ogni metrica.

### 13.1 Soglie quantitative

| Metrica | Soglia "OK" | Soglia "Eccellente" | Razionale |
|---|---|---|---|
| `val_total` | < 0.20 | < 0.15 | Treiber Ch17: 20% residual floor per intra-driver variation |
| `L_data / L_total` | > 0.70 | > 0.80 | La rete deve risolvere il task, non barare con L_phys |
| **RMSE per-param** (vs ground truth IDM): | | | |
| — v₀ [m/s] | < 5.5 (15% range) | < 2.2 (6%) | Range fisico 37 m/s |
| — T [s] | < 0.30 (15%) | < 0.10 (5%) | Range 2 s |
| — s₀ [m] | < 0.60 (15%) | < 0.20 (5%) | Range 4 m |
| — a [m/s²] | < 0.33 (15%) | < 0.10 (5%) | Range 2.2 m/s² |
| — b [m/s²] | < 0.38 (15%) | < 0.13 (5%) | Range 2.5 m/s² |
| **Spike rate medio** | ∈ [5%, 30%] | ∈ [10%, 20%] | Sotto → dead neurons; sopra → no FPGA energy benefit |
| **Inf grad batches** | 0 per ≥ 5 epoche | 0 per intero training | BPTT stabile |
| **String stability** | `vₑ'(s) ≤ ½(fₗ−fᵥ)` (Treiber Ch16) | (idem) | Convoglio simulato non amplifica perturbazioni |
| **Po2 gap** (val FP32 vs Po2) | < 10% | < 3% | Hardware-aware quality |

### 13.2 Risultati attuali (baseline sweep STEP 2B, highway-only)

| Run | h | r | params | val_best | spike% | Stato |
|---|---|---|---|---|---|---|
| h32_r8 | 32 | 8 | **864** | 0.2802 | 8.4 | OK |
| h48_r12 | 48 | 12 | 1685 | 0.2789 | 9.1 | OK |
| h64_r16 | 64 | 16 | 2757 | 0.2790 | 10.5 | OK |
| h96_r24 | 96 | 24 | 5669 | 0.2797 | 7.7 | OK |
| h128_r32 | 128 | 32 | 9605 | 0.2792 | 10.3 | OK |

**Interpretazione**: tutti dentro `< 0.20` no, ma in zona `[0.27, 0.30]` con range 1.3 millesimi tra capacity diverse. Plateau strutturale (causa probabile: minimi locali per early stop + OneCycle troncato; vedi STEP 2C in TIMELINE).

---

## 14. Costi computazionali

### 14.1 Inference (1 step temporale = 10 tick SNN)

Baseline h=32, r=8:

| Layer | Operazione | FLOPs (FP32 equiv.) | Su FPGA Po2 |
|---|---|---|---|
| `fc_weight` (4→32) | 1 MAC per tick × 10 tick | 4·32·10 = 1280 | shift+add (no MAC) |
| `rec_U·rec_V` (32→8→32) | 2 MAC per tick × 10 | (32·8 + 8·32)·10 = 5120 | shift+add |
| `ALIF` dinamica | leak + threshold + reset | ~3·32·10 = 960 | bit-shift + comparator |
| `OutputLayer_LI` (32→5) | 1 MAC per tick × 10 | 32·5·10 = 1600 | shift+add |
| Sigmoid+decode (output) | 1 per step | ~25 | LUT |
| **Totale per step (Δt=0.1s)** | ~9000 FLOP-equivalenti | ~8.7k shift/add |

A 10 Hz (controllo ACC real-time): **~90 kFLOPs/s** ≪ 1 MFLOPS. PYNQ-Z1 (Zynq-7020, 100+ DSP slice) ha margine 1000×.

### 14.2 Memoria (FP32 → Po2 4-bit)

| Tensore | FP32 (byte) | Po2 (byte) | Riduzione |
|---|---|---|---|
| `fc_weight` 128 params | 512 | 64 | 8× |
| `rec_U+V` 512 params | 2048 | 256 | 8× |
| `out fc_weight` 160 params | 640 | 80 | 8× |
| Threshold params (64) | 256 | 256 (FP32) | 1× |
| **Totale modello** | ~3.5 KB | ~0.66 KB | **5.3×** |

Stato runtime (potenziale + adattamento) per 32 neuroni: 256 byte. Totale memoria PYNQ ≈ **1 KB** → fit completo in BRAM senza DDR access.

### 14.3 Training

- Generazione dataset (5000 traj × 1000 step): ~30 s su CPU laptop
- 1 epoca con n_train=500, seq_len=50: ~60 s/epoca su Azure CPU (forward+backward+log)
- Sweep STEP 2B completo (9 runs × ~30 min): ~5h Azure CPU

---

## 15. Comparativa Po2 vs FP32

| Aspetto | FP32 reference | Po2 quantization (forward) | Note |
|---|---|---|---|
| Peso range | continuo | {±2^k} per k∈[−4,1] ∪ {0} | 13 livelli totali |
| Moltiplicazione | hardware MUL (4 cycles) | bit-shift (1 cycle) | 4× speedup |
| Area FPGA | ~100 LUT/MAC | ~10 LUT/shift | 10× area saving |
| Energia | ~1 nJ/MAC | ~0.05 nJ/shift | 20× energy |
| Accuracy gap (STE backward) | reference 0 | ~+3-8% loss (tipico) | accettabile |
| Training time | normale | normale (STE bypassa quantizzazione in backward) | — |

Decisione progettuale: **accettiamo penalità accuracy minore per moltiplicare l'efficienza FPGA**.

---

## 16. Per saperne di più

| Vuoi sapere... | Vedi |
|---|---|
| Storia delle decisioni (P1, A3, B5, F-fixes, ecc.) | `document/TIMELINE.md`, `document/P_S.md` |
| Decodificare codici (P/A/B/F/T/PF/G) | `document/GLOSSARY.md` |
| Procedura end-to-end su Azure | `document/WORKFLOW.md` |
| One-pager per riprendere dopo compaction | `document/SESSION_RESUME.md` |
| Modello ACC-IIDM teoria completa | Treiber & Kesting, *Traffic Flow Dynamics* 2nd ed., Ch12 §12.4 |
| String stability + Master Criterion | Treiber, Ch16 |
| SNN training (BPTT, surrogate) | SNN-expert skill, ch08, ch22 |
| Neftci surrogate gradient paper | Neftci et al. 2019, "Surrogate Gradient Learning in Spiking Neural Networks" |
| Power-of-two quantization | Vogel et al. 2019, "Efficient Hardware Acceleration of Sparse SNNs" |
| SNN training (BPTT, surrogate) | SNN-expert skill, ch08, ch22 |
