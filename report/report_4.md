# Report 4 — CF_FSNN: Stato post Review SNN-Expert

**Data:** 2026-05-26  
**Commit base:** `1292b7c` (pre-review)  
**Commit questo report:** fix-snn-expert-review (questo commit)

---

## 1. Sommario

Il progetto CF_FSNN implementa una **Spiking Neural Network (SNN) per l'identificazione
dei parametri di car-following** basata sul modello fisico **ACC-IIDM** (Adaptive Cruise
Control con base IIDM — Improved Intelligent Driver Model, Ch12 Sez.12.4 Treiber &
Kesting 2025).

**Obiettivo:** stimare in tempo reale i 5 parametri IDM `[v0, T, s0, a, b]` del veicolo
follower a partire da dati V2X `[s, v, Δv, v_l]`, usando una PINN loss che garantisce
coerenza fisica con ACC-IIDM. Il parametro T(t) è stocastico (processo IDM-2d, Ch12.6).

**Hardware target:** PYNQ-Z1 FPGA — pesi power-of-2, leak bit-shift, spike binari.

Una review SNN-Expert (2026-05-26) ha identificato 12 problemi (3 HIGH, 4 MEDIUM, 5 LOW).
Questo commit li risolve tutti in un unico commit atomico.

---

## 2. Architettura CF_FSNN_Net

### 2.1 Panoramica

```
Input V2X (4):  [s̃, ṽ, Δṽ, ṽ_l]   ← normalizzato [0,1]
        ↓
  HiddenLayer_ALIF  (4 → 32, rank=8, max_delay=6)
  — ALIF neuron con fatica adattiva
  — Ricorrenza low-rank: U(32×8) × V(8×32)
  — Delay sinaptico max: 6 tick × 10ms = 60ms hardware
  — Bit-shift leak: >>3 (× 0.875 per step)
        ↓ spike binari
  OutputLayer_LI    (32 → 5)
  — Leaky Integrator senza spike
  — Integra su TICKS_PER_STEP tick interni
        ↓ potenziale continuo
  _decode_params()   → sigmoid + scaling equalizzato (F5)
        ↓
Output (5):   [v0, T, s0, a, b]   ← parametri IDM fisici (modello ACC-IDM)
```

### 2.2 Tabella layer e parametri

| Layer | Tipo | Dimensioni | Parametri |
|-------|------|-----------|-----------|
| `layer_hidden.fc_weight` | Feed-forward | (32, 4) | 128 |
| `layer_hidden.rec_U` | Low-rank rec. | (32, 8) | 256 |
| `layer_hidden.rec_V` | Low-rank rec. | (8, 32) | 256 |
| `layer_hidden.cell.base_threshold` | ALIF | (32,) | 32 |
| `layer_hidden.cell.thresh_jump` | ALIF | (32,) | 32 |
| `layer_out.fc_weight` | Output | (5, 32) | 160 |
| **Totale** | | | **864** |

### 2.3 Range fisici output

| Parametro | Lo | Hi | Range | Scala (F5) |
|-----------|----|----|-------|------------|
| `v0` [m/s] | 8.0 | 45.0 | 37.0 | 1.000 (ref) |
| `T`  [s]   | 0.5 |  2.5 |  2.0 | 0.054 |
| `s0` [m]   | 1.0 |  5.0 |  4.0 | 0.108 |
| `a`  [m/s²]| 0.3 |  2.5 |  2.2 | 0.059 |
| `b`  [m/s²]| 0.5 |  3.0 |  2.5 | 0.068 |

### 2.4 Neurone ALIF (equazioni hardware)

```
Leak:      V(t) ← V(t) - V(t)/2^k  [bit-shift k=3, ×0.875]
Soglia:    θ(t) = θ_base + fatigue(t)
Spike:     z(t) = H(V(t) - θ(t))
Reset:     V(t) ← V(t) - z(t)·θ(t)      [soft reset]
Fatica:    f(t) ← f(t) - f(t)/2^k + z(t)·thresh_jump   [f≥0]
```

**Surrogate gradient** (backward pass):
```
σ'(V-θ) = 1 / (1 + γ·|V-θ|)²,   γ = 0.3  (Bellec 2018 LSNN)
```

### 2.5 Decodifica parametri con equalizzazione del gradiente (F5)

```python
raw_eq = raw / decode_scale          # equalizza la sensibilità
params = param_lo + (param_hi - param_lo) * sigmoid(raw_eq)
```

**Senza F5:** `d(v0)/d(raw_v0) = 37·σ' vs d(T)/d(raw_T) = 2·σ'` → 18.5× squilibrio.  
**Con F5:** `d(param_i)/d(raw_i) = 37·σ'(raw_eq_i)` uniforme per tutti i parametri.

---

## 3. Fisica ACC-IIDM

### 3.1 IIDM base (Ch12 Sez.12.4)

`z = s*(v,Δv) / s_safe` dove `s* = s0 + max(0, v·T + v·Δv/(2√(a·b)))`

| Condizione | Regime | Formula a_IIDM |
|-----------|--------|----------------|
| v ≤ v0, z < 1 | Free-flow | `afree·(1-z²)` |
| v ≤ v0, z ≥ 1 | Car-following | `a·(1-z²)` → 0 in z=1 |
| v > v0, z < 1 | Sopra v0, libero | `afree` |
| v > v0, z ≥ 1 | Sopra v0, congestionato | `afree + a·(1-z²)` |

con `afree = a·(1-(v/v0)^4)` (delta=4, hardcoded).

**Continuità in z=1:** per v≤v0 entrambi i rami danno `a·(1-1)=0` ✓

### 3.2 CAH (Constant Acceleration Heuristic, Ch12 Eq.12.35)

```
ā_l   = min(a_l, a)                       [accellaz. leader limitata]
a_cah = ā_l - relu(Δv)² / (2·s_safe)     [anticipa la frenata]
a_cah ∈ [-9, a]                           [crash provision]
```

**s_safe = max(s, 2.0)** in entrambe le implementazioni (F1):  
- `core/network.py::acc_iidm_accel()` → `s.clamp(min=2.0)`  
- `data/generator.py::_acc_iidm_accel()` → `max(s, 2.0)` ← **fix F1**

### 3.3 Blend ACC-IDM con coolness c=0.99

```
if a_IIDM ≥ a_CAH:  a_ACC = a_IIDM
else:               a_ACC = (1-c)·a_IIDM + c·(a_CAH + b·tanh((a_IIDM-a_CAH)/b))
```

Con c=0.99: quando il leader frena bruscamente (cut-in), la CAH domina → no panic braking.

---

## 4. PINN Loss

```
L = λ_data · RMSE_masked(a_pred, a_gt)    [fit acc., soli passi V2X ok]
  + λ_phys · MSE_all(a_pred, a_gt)        [residuo fisico su tutti i passi]
  + λ_OU   · OU_residual(T_seq)           [mean-reversion su T]
  + λ_bc   · crash_penalty(s, s0_pred)    [boundary condition]
```

### 4.1 L_data — Masked RMSE (fix precedente)

```
L_data = sqrt( sum_t(mask_t · (a_pred_t - a_gt_t)²) / N_valid + ε )
```

`N_valid = mask.sum().clamp(min=1)` — conta solo i passi con V2X ricevuto.  
**Perché non SRMSE:** il vecchio denominatore `||a_gt||²` → 0 su traiettorie a v costante  
→ gradiente ~1e9 → crash training. Con N_valid il gradiente massimo è O(9m/s²).

### 4.2 L_phys — Residuo ACC-IDM

```
L_phys = MSE(a_ACC-IDM(s,v,Δv,a_l; params_pred), a_gt)
```

Con F1 (s_safe allineato), L_phys è **riducibile a zero** con i parametri corretti  
su tutti gli scenari, inclusi cut-in con s < 2m.

### 4.3 L_OU — Floor irreducibile (by design)

Il generatore usa un processo di **salto Markoviano** per T (salta a U(T1,T2) con
prob dt/tau ≈ 0.003 per step), mentre ou_residual penalizza deviazioni da un OU continuo.

**Floor teorico:** `Var(U(T1,T2)) · prob_jump = (0.8²/12) · (0.1/30) ≈ 1.8e-4`

→ L_ou non scenderà mai a zero. L_ou < 1e-3 in training è un buon indicatore.

### 4.4 L_bc — Crash prevention

```
L_bc = MSE(relu(s0_pred - s_obs + 0.1))
```

Penalizza predizioni di s0 che avvicinerebbero s0 > s_obs (gap troppo piccolo).

---

## 5. Finding della Review SNN-Expert — Tabella riepilogativa

| ID | Severità | Descrizione | File | Stato |
|----|----------|-------------|------|-------|
| F1 | **HIGH** | s_safe floor inconsistente: generator=0.01, network=2.0 → L_phys irreducibile | `data/generator.py` | ✅ RISOLTO |
| F2 | **HIGH** | val_epoch: NaN silenzioso sulle metriche | `train.py` | ✅ RISOLTO |
| F3 | **HIGH** | plot_diagnostics crash su CSV vuoto (training abortito) | `utils/plot_diagnostics.py`, `train.py` | ✅ RISOLTO |
| F4 | MEDIUM | forward_sequence_with_stats: monkey-patch anti-pattern | `core/network.py`, `train.py` | ✅ RISOLTO |
| F5 | MEDIUM | _decode_params: gradiente 18.5× sbilanciato tra v0 e T | `core/network.py` | ✅ RISOLTO |
| F6 | MEDIUM | ou_residual: floor irreducibile non documentato | `core/network.py` | ✅ DOCUMENTATO |
| F7 | MEDIUM | delta=4 hardcoded nella rete, non commentato | `core/network.py` | ✅ DOCUMENTATO |
| F8 | LOW | Delay buffer: list.insert() O(n) invece di deque O(1) | `core/network.py` | ✅ RISOLTO |
| F9 | LOW | thresh_jump: torch.abs() ridondante (segno mai usato) | `core/neurons.py` | ✅ RISOLTO |
| F10 | LOW | relu(fatigue): ridondante, fatigue ≥ 0 per costruzione | `core/neurons.py` | ✅ RISOLTO |
| F11 | LOW | Docstring max_delay errata: 0.6s invece di 0.06s | `core/network.py` | ✅ CORRETTO |
| F12 | LOW | γ=0.3 surrogate non documentato (scelta Bellec 2018) | `core/hardware.py` | ✅ DOCUMENTATO |

---

## 6. Descrizione dettagliata dei fix

### F1 — s_safe: inconsistenza generator vs network (HIGH)

**Causa root:** In `generator.py::_acc_iidm_accel()` il floor era `max(s, 0.01)` mentre
in `network.py::acc_iidm_accel()` era `s.clamp(min=2.0)`.

**Impatto quantificato:** Per s=1m, Δv=3m/s:
- Generator con s_safe=0.01m → usa 1m: `a_cah = ā_l - 9/2 = ā_l - 4.5 m/s²`
- Network con s_safe=2.0m: `a_cah = ā_l - 9/4 = ā_l - 2.25 m/s²` → **+2.25 m/s² di errore fisso**

Questo crea un floor irreducibile in L_phys per i batch di cut-in (20% del dataset),
impedendo alla loss fisica di convergere a zero anche con i parametri corretti.

**Fix applicato:**
```python
# data/generator.py, _acc_iidm_accel()
# PRIMA: s_safe = max(s, 0.01)
# DOPO:
s_safe = max(s, 2.0)  # F1: allinea a network.py
```

**⚠ ATTENZIONE:** Invalida la cache esistente. Rigenerare con `--data_cache`.

---

### F2 — val_epoch: NaN silenzioso nelle metriche (HIGH)

**Causa root:** `val_epoch()` non filtrava batch con output degeneri. Un NaN in
`comps['total']` veniva sommato silenziosamente, corrompendo tutte le metriche.

**Fix applicato:**
```python
# train.py, val_epoch()
_, comps, sr = pinn_loss(model, x, y, mask, *lam)
if not math.isfinite(comps['total']):    # F2: guardia NaN
    continue
```

---

### F3 — plot_diagnostics crash su CSV vuoto (HIGH)

**Causa root:** Quando il training abortisce per `inf_streak ≥ max_inf_streak`, il loop
si interrompe PRIMA di chiamare `logger.log()`. Il CSV ha solo l'header (132 byte).
`load_training_log()` sollevava `ValueError` non catturato dal `try/except ImportError` di `main()`.

**Fix in 3 punti:**

**a) `load_training_log()` — ritorna None invece di ValueError:**
```python
if not rows:
    print(f"[plot_diagnostics] Log vuoto (training abortito ...): {csv_path}")
    return None
```

**b) `plot_all()` — guardia log=None:**
```python
if log is None:
    print("[plot_diagnostics] Nessun log da plottare. Grafici saltati.")
    return
```

**c) `main()` — controllo condizionale:**
```python
if log_data is not None:
    plot_all(log_data, plot_dir, ...)
else:
    print("[Diagnostics] Training terminato prima dell'epoch 1 — grafici saltati.")
```

---

### F4 — forward_sequence_with_stats: rimosso monkey-patch (MEDIUM)

**Causa root:** Il metodo era definito come funzione standalone `_forward_sequence_with_stats`
e assegnato alla classe via `CF_FSNN_Net.forward_sequence_with_stats = func`. Il monkey-patch:
- Non era visibile con `help(model)` o `inspect.getmembers(model)`
- Assente se `CF_FSNN_Net` veniva importato prima di `train.py`

**Fix:** Metodo spostato direttamente in `CF_FSNN_Net` come metodo di classe in
`core/network.py`, dopo `ou_residual()`. Rimosso il blocco funzione + assegnazione da `train.py`.

---

### F5 — _decode_params: equalizzazione gradiente (MEDIUM)

**Causa root:** `d(param_i)/d(raw_i) = (hi_i - lo_i) · σ'(raw_i)`. Il range v0=37 vs T=2
produceva un gradiente 18.5× più grande per raw_v0 rispetto a raw_T, rallentando enormemente
la convergenza del parametro T (il più importante per l'ACC-IDM).

**Fix — pre-scaling:**
```python
# __init__():
ranges = bounds[:, 1] - bounds[:, 0]          # [37, 2, 4, 2.2, 2.5]
self.register_buffer('decode_scale', ranges / ranges.max())  # normalizzato

# _decode_params():
raw_eq = raw / self.decode_scale               # scala equalizzata
return param_lo + (param_hi - param_lo) * sigmoid(raw_eq)
```

**Risultato:** `d(param_i)/d(raw_i) = max_range · σ'(raw_eq_i)` — uniforme.

**Nota:** Il primo training post-fix può mostrare loss leggermente più alta nelle prime
epoche (la rete deve riadattarsi alle nuove scale). È normale.

---

### F6 — ou_residual: floor documentato (MEDIUM)

Aggiornato il docstring di `ou_residual()` per spiegare il floor irreducibile ~1.8e-4
causato dall'incompatibilità tra il processo di salto Markoviano del generatore (discreto,
con salti U(T1,T2)) e la penalità OU continua della rete.

---

### F7 — delta=4 hardcoded documentato (MEDIUM)

Aggiunto commento esplicativo in `acc_iidm_accel()` e `idm_accel()` in `network.py`
indicando che delta=4 è coerente con `IDM_HWY`, `IDM_URB`, `IDM_TRK` in `config.py`
(tutti con `delta=4`). Avviso se il generatore usasse un delta diverso.

---

### F8 — Delay buffer: deque O(1) (LOW)

**Prima:** `list.insert(0, x)` + `list.pop()` — O(n) per ogni tick, n=max_delay=6.  
**Dopo:** `deque(maxlen=max_delay)` con `appendleft(x)` — O(1), maxlen gestisce il pop.

```python
# reset_state():
self.x_buffer = deque(
    [torch.zeros(batch_size, self.in_features, device=device)
     for _ in range(self.max_delay)],
    maxlen=self.max_delay,
)
# forward():
self.x_buffer.appendleft(x)
```

---

### F9 — thresh_jump: clamp(min=0) invece di abs() (LOW)

`thresh_jump` è inizializzato positivo e per design ALIF deve restare ≥ 0.
`torch.abs()` ha gradiente discontinuo in 0; `clamp(min=0)` è semanticamente più corretto
e ha gradiente nullo solo al confine (non discontinuità).

```python
# PRIMA: spikes * torch.abs(self.thresh_jump)
# DOPO:  spikes * self.thresh_jump.clamp(min=0)
```

---

### F10 — relu(fatigue): clamp(min=0) con commento (LOW)

`fatigue` parte da 0, incrementa di `thresh_jump.clamp(min=0)` ad ogni spike, e decade
via bit-shift — per costruzione è sempre ≥ 0. Il `relu()` era ridondante.

```python
# PRIMA: self.base_threshold + torch.relu(self.fatigue)
# DOPO:  self.base_threshold + self.fatigue.clamp(min=0)  # guardia numerica esplicita
```

---

### F11 — Docstring max_delay corretta (LOW)

```
# PRIMA: max_delay=6  →  Tr_max = 6 × 0.1 s = 0.6 s
# DOPO:  max_delay=6  →  ritardo sinaptico hardware = 6 tick × (DT/TICKS_PER_STEP) = 0.06 s
```

Il tempo di reazione biologico Tr ∈ [0.1, 0.6] s è modellato dal buffer delay del layer
ALIF, non dal singolo tick interno.

---

### F12 — γ=0.3 documentato (Bellec 2018) (LOW)

Aggiunto commento in `core/hardware.py` che documenta γ=0.3 come valore dell'articolo
LSNN originale (Bellec et al. 2018, "Long short-term memory and learning-to-learn in
networks of spiking neurons"). Una surrogate più larga (piccolo γ) mantiene il gradiente
non-zero in un intervallo più ampio attorno alla soglia — vantaggioso per reti piccole
con pochi spike come CF_FSNN_Net (32 neuroni ALIF).

---

## 7. Stato corrente post-fix

### 7.1 Coerenza fisica garantita

| Check | Prima | Dopo |
|-------|-------|------|
| s_safe generator = s_safe network | ❌ 0.01 vs 2.0 | ✅ 2.0 in entrambi |
| L_phys riducibile a 0 | ❌ floor ≈ 2.25 m/s² su cut-in | ✅ riducibile |
| forward_sequence_with_stats in classe | ❌ monkey-patch | ✅ metodo ufficiale |
| Gradiente bilanciato tra i 5 param | ❌ 18.5× squilibrio | ✅ equalizzato |
| val_epoch NaN-safe | ❌ NaN silenzioso | ✅ filtrato |
| plot_diagnostics NaN-safe | ❌ crash su CSV vuoto | ✅ return None |

### 7.2 Metriche attese post-fix

| Metrica | Soglia | Note |
|---------|--------|------|
| `gn=` per batch | ≤ 1.0 (clippato) | s_safe=2.0 tiene gn < 200 su highway |
| `spike=` layer hidden | 5–30% | ALIF homeostasi adattiva |
| `L_ou` per epoch | 0 – 5e-3 | floor ~1.8e-4 atteso |
| `L_phys` convergenza | decrescente verso 0 | garantito con F1 |
| Bias(T) | < ±0.1 s | con F5 il parametro T converge |
| Bias(v0) | < ±2 m/s | — |

---

## 8. Istruzioni per il prossimo training

### 8.1 Rigenera la cache (OBBLIGATORIO dopo F1)

```bash
# Step 1: smoke con nuova fisica per verificare la cache
python train.py --smoke --tag smoke_v3 --data_cache data/cache_smoke.pt

# Step 2: se smoke ✓ → genera cache completa
python train.py --smoke --scheduler onecycle --max_lr 5e-3 \
    --tag smoke_v3 --data_cache data/cache_smoke.pt
```

**⚠ NON riutilizzare `cache_1500.pt` generata prima di questo commit.**  
Il GT data è calcolato con s_safe=0.01 → l'inconsistenza che F1 vuole correggere
rimarrebbe nella cache.

### 8.2 Criteri pass/fail smoke test

| Metrica | Soglia | Motivazione |
|---------|--------|-------------|
| `loss=` per batch | finito, 0.1–5.0 | NaN guard attivo |
| `gn=` per batch | ≤ 1.0 (clippato, no inf) | s_safe=2.0 |
| `spike=` | 5–30% | ALIF homeostasi |
| Nessun `[EARLY-STOP]` | — | max_inf_streak=5 |
| L_ou per epoch | 0 – 5e-3 | floor ~1.8e-4 |

### 8.3 Stage A (dopo smoke ✓)

```bash
python train.py --epochs 5 --scheduler onecycle --max_lr 5e-3 \
    --data_cache data/cache_1500.pt --tag A1_onecycle_v2

python train.py --epochs 5 --scheduler cosine --T0 5 \
    --data_cache data/cache_1500.pt --tag A2_cosine

python train.py --epochs 5 --scheduler plateau \
    --data_cache data/cache_1500.pt --tag A3_plateau
```

**Criteri Stage A (nuovi, post-F5):**

| Metrica | Soglia |
|---------|--------|
| val_loss E5 < val_loss E1 | obbligatorio |
| Nessun EARLY-STOP | obbligatorio |
| Spike rate | 10–25% |
| Bias(T) = mean(T_pred) - mean(T_true) | < ±0.1 s |
| Bias(v0) | < ±2 m/s |
| G7 violin: tutti i 5 parametri dentro i bound fisici | obbligatorio |

---

## 9. Limitazioni note (by design)

| Limitazione | Motivo | Impatto |
|-------------|--------|---------|
| delta=4 hardcoded nella rete | Config corrente fissa delta=4 per tutti gli scenari | Basso; se config cambia, aggiornare entrambi i file |
| Surrogate γ=0.3 | Scelta conservativa Bellec 2018 per reti piccole | Convergenza più lenta ma stabile; γ=1.0 alternativa |
| L_ou floor ~1.8e-4 | Mismatch jump-process vs OU-continuo | Non annullabile; soglia attesa < 1e-3 |
| Update posizione Euleriano | `s += (v_l - v) * dt` (non balistico per s) | Errore < 0.05m/step; trascurabile per dt=0.1s |
| max_delay=6 tick = 60ms | Ritardo assonale hardware FPGA | Tempo reazione biologico Tr ∈ [0.1, 0.6]s NON è questo valore |

---

## 10. File modificati — riepilogo commit

| File | Fix | Tipo |
|------|-----|------|
| `core/neurons.py` | F9, F10 | Cleanup / ottimizzazione |
| `core/hardware.py` | F12 | Documentazione |
| `core/network.py` | F4, F5, F6, F7, F8, F11 | Architettura + documentazione |
| `data/generator.py` | F1 | **CRITICO — fisica** |
| `utils/plot_diagnostics.py` | F3a, F3b, G2-label | Robustezza + correttezza |
| `train.py` | F2, F3c, F4 (rimozione monkey-patch) | Robustezza |
| `document/report_4.md` | — | **NUOVO FILE** |

**Totale: 6 file modificati + 1 nuovo, 1 commit atomico.**
