# CF_FSNN — Report di Stato #3
> Fix critici: GPU idle su Colab T4 + NaN cascade durante Stage A1.
> Data: 2026-05-26

---

## 1. CONTESTO

Questo report documenta i fix applicati prima del primo vero run su piattaforma cloud.
Il codice era già allineato allo stato di report_2.md (ACC-IDM, cut-in, diagnostica G1-G7, argparse completo).
Erano rimasti irrisolti due problemi emersi nel tentativo di eseguire Stage A1 su Google Colab T4.

---

## 2. PROBLEMA 1 — GPU idle su Colab T4

### Sintomo

GPU utilization ≈ 0-5% durante il training nonostante `device = cuda`. La T4 era rilevata ma non usata.

### Causa 1 — Loop Python per filtro OU

In `train.py`, la stima di `a_l` (accelerazione leader, necessaria per ACC-IDM nella `pinn_loss()`)
era implementata come loop Python esplicito:

```python
# VECCHIO — 99 chiamate GPU sequenziali per batch:
a_l_filt = torch.zeros_like(vl_diff)
a_l_filt[:, 0] = vl_diff[:, 0]
for t in range(1, T_len):
    a_l_filt[:, t] = alpha_al * a_l_filt[:, t - 1] + (1.0 - alpha_al) * vl_diff[:, t]
```

Ogni iterazione lancia un kernel CUDA da ~microsecondo. Con T_len=100 e batch frequenti,
la GPU eseguiva il kernel e restava in attesa del prossimo per ~1µs (overhead Python).
Risultato: GPU quasi sempre idle, CPU collo di bottiglia.

### Fix 1 — Filtro OU vettorizzato (soluzione chiusa)

Il filtro ricorsivo `y[t] = α·y[t-1] + β·x[t]`, con `y[0]=x[0]`, ha soluzione chiusa:

```
y[t] = α^t · (α·x[0] + β · cumsum(x[k] / α^k)[t])
```

Implementazione con 4 operazioni tensor (zero Python loop):

```python
alpha_al = math.exp(-DT / ACC_AL_TAU)
beta_al  = 1.0 - alpha_al
t_idx    = torch.arange(T_len, device=vl_diff.device, dtype=vl_diff.dtype)
inv_pow  = alpha_al ** (-t_idx)          # (T,)
fwd_pow  = alpha_al **   t_idx           # (T,)
x_sc     = vl_diff * inv_pow             # (B, T)  — normalizzazione
cs       = torch.cumsum(x_sc, dim=1)    # (B, T)  — una sola operazione
a_l_filt = fwd_pow * (alpha_al * vl_diff[:, :1] + beta_al * cs)  # (B, T)
```

Un solo kernel `cumsum` da GPU invece di 99. Atteso: GPU utilization 20-40%
(normale per un modello da 864 parametri su T4 da 8 TFLOPS).

### Causa 2 — `num_workers > 0` su Colab (CUDA + fork)

Su Linux (Colab), il DataLoader con `num_workers > 0` usa `fork()` per creare i worker.
Se CUDA è già stato inizializzato (da `model.to(device)`) prima del fork, i processi figli
possono andare in deadlock perché CUDA non è fork-safe.

### Fix 2 — Rilevamento automatico Colab

```python
if args.num_workers >= 0:
    _nw = args.num_workers          # valore esplicito dell'utente
elif os.name == 'nt':
    _nw = 0                         # Windows — fork non disponibile
else:
    try:
        import google.colab
        _nw = 0                     # Colab — CUDA inizializzato prima del fork
    except ImportError:
        _nw = min(4, os.cpu_count() or 1)
_pw = _nw > 0
```

Flag `--num_workers` aggiunto all'argparse (default=-1 → auto-detect).

### Fix 3 — `cudnn.benchmark`

```python
if device.type == 'cuda':
    torch.backends.cudnn.benchmark = True
```

Permette a cuDNN di selezionare automaticamente i kernel più veloci per le dimensioni fisse
di questo modello (una volta, al primo forward).

### Commit

`9b43054` — "fix: vectorize OU filter + colab-safe num_workers + cudnn.benchmark"

---

## 3. PROBLEMA 2 — NaN cascade durante Stage A1 (epoca 1, batch 1300)

### Sintomo

Training regolare fino a B1250, poi collasso totale da B1300:

```
[E01 | B1250/1485]  loss=1.2356  data=1.0972  phys=0.05944  ou=0.021138  spike=10.8%
[E01 | B1300/1485]  loss=nan  data=nan  phys=nan  ou=nan  spike=10.6%
[E01 | B1350/1485]  loss=nan  data=nan  phys=nan  ou=nan  spike=10.6%
...
> train=nan  val=nan  (data=nan  phys=nan  ou=nan)  spike=0.0%  lr=3.88e-03
```

Nota: `spike=10.6%` a B1300 indica che il layer ALIF è ancora funzionante — il NaN
non parte da ALIF ma dal layer di output LI.

### Analisi root cause (catena di 4 anelli)

**Anello 1 — Singolarità del gradiente SRMSE**

```python
# Formula originale:
L_data = torch.sqrt(sq_err.sum() / (v_dot_gt.pow(2).sum() + eps))
```

Quando un singolo batch (tra B1251 e B1299, non loggato per LOG_EVERY=50) produce
predizioni quasi perfette, `sq_err.sum() → 0`. La derivata `d(√u)/du = 1/(2√u)` diverge
a `+∞` quando `u → 0`, anche se il denominatore è finito. Se contemporaneamente
`a_pred - v_dot_gt → 0`, il prodotto in backward è `∞ × 0 = NaN`.

**Anello 2 — LI weight corrotto**

Il NaN nel gradiente di `L_data` si propaga via backprop al layer `OutputLayer_LI`
e Adam applica NaN a `fc_weight` (i pesi rimangono NaN da quel batch in poi).

**Anello 3 — `po2_quantize` propaga NaN**

```python
class PowerOf2Quantize(torch.autograd.Function):
    @staticmethod
    def forward(ctx, weight):
        sign = torch.sign(weight)          # sign(NaN) = 0 o NaN
        w_abs = torch.abs(weight).clamp(min=1e-5)
        log2_w = torch.clamp(torch.round(torch.log2(w_abs)), min=-4.0, max=1.0)
        mask = (w_abs > 2 ** (-5)).float()
        return sign * (2.0 ** log2_w) * mask  # NaN × finite = NaN
```

`po2_quantize(NaN_weight)` = NaN output. Tutti i forward pass da B1300 in poi producono
`params_seq` = NaN, quindi tutte le componenti di loss = NaN.

**Anello 4 — Invarianza di ALIF**

ALIF usa spike hard-reset e non dipende direttamente dai pesi LI → la spike rate
rimane a ~10% anche mentre tutto il resto è NaN. Questo è il marker diagnostico
che ha permesso di individuare il layer LI come punto di origine.

### Fix 1 — eps dentro il sqrt

```python
# NUOVO:
denom  = v_dot_gt.pow(2).sum() + eps
L_data = torch.sqrt(sq_err.sum() / denom + eps)
```

Aggiungere `eps` dentro il `sqrt` garantisce che l'argomento non sia mai esattamente 0,
eliminando la singolarità della derivata. La perdita numerica è trascurabile
(eps ≈ 1e-8 su valori tipici dell'ordine di 0.5-1.5).

### Fix 2 — NaN loss guard (prima di `backward`)

```python
if not loss.isfinite():
    print(f"  [NaN-Guard E{epoch} B{batch_idx+1:04d}]"
          f" loss={loss.item()} — skip backward")
    if step_per_batch and scheduler is not None:
        scheduler.step()
    spike_acc += sr
    n_batches  += 1
    continue
```

Se il Fix 1 non fosse sufficiente, il backward viene saltato prima di corrompere i pesi.

### Fix 3 — NaN gradient guard (dopo `clip_grad_norm_`)

```python
gn = nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

if not math.isfinite(float(gn)):
    print(f"  [NaN-Grad E{epoch} B{batch_idx+1:04d}]"
          f" grad_norm={float(gn):.2e} — zero grad, skip step")
    optimizer.zero_grad()
    if step_per_batch and scheduler is not None:
        scheduler.step()
    spike_acc += sr
    n_batches  += 1
    continue
```

Linea di difesa finale: azzera i gradienti e salta `optimizer.step()` se il grad_norm
è `inf` o `NaN`, impedendo che pesi corrotti vengano scritti.

### Commit

`f85dd5c` — "fix: prevent NaN cascade in SRMSE backward + add loss/grad guards"

---

## 4. STATO CORRENTE DEL CODICE

### Commit history rilevante

| Commit | Descrizione |
|--------|-------------|
| 9b43054 | fix: vectorize OU filter + colab-safe num_workers + cudnn.benchmark |
| f85dd5c | fix: prevent NaN cascade in SRMSE backward + add loss/grad guards |

### File modificati in questa sessione

| File | Modifiche |
|------|-----------|
| `train.py` | Filtro OU vettorizzato; auto-detect num_workers; cudnn.benchmark; eps in sqrt L_data; NaN loss guard; NaN grad guard |

### File non modificati (stabili)

| File | Stato |
|------|-------|
| `config.py` | Stabile — parametri ACC-IDM confermati |
| `data/generator.py` | Stabile — ACC-IDM+IIDM+cut-in operativo |
| `core/network.py` | Stabile — ACC-IDM torch differenziabile presente |
| `core/neurons.py` | Stabile — ALIF e LI confermati |
| `core/hardware.py` | Stabile — po2_quantize confermato |
| `utils/plot_diagnostics.py` | Stabile — G1-G7 pronti |

---

## 5. PROSSIMI RUN PIANIFICATI

Stage A/B/C invariato da report_2.md. Da eseguire su Colab T4 dopo `git pull`:

### Stage A (5 epoche × 3 run)

```bash
python train.py --epochs 5 --scheduler onecycle --max_lr 5e-3 --tag A1_onecycle
python train.py --epochs 5 --scheduler cosine   --T0 5        --tag A2_cosine
python train.py --epochs 5 --scheduler plateau  --patience 10 --tag A3_plateau
```

**Criteri di successo Stage A:**
- Nessun NaN (garantito dai fix di questa sessione)
- GPU utilization > 15% su T4 (garantito dalla vettorizzazione OU)
- val_loss scende monotonicamente dopo ep.1

---

## 6. METRICHE TARGET

Invariate da report_2.md:

| Metrica | Baseline (report_1) | Target Stage A/B/C | Target full |
|---------|--------------------|--------------------|-------------|
| SRMSE (test) | 0.871 | < 0.5 | < 0.3 |
| T bias | +0.15 s | < +0.08 s | < +0.03 s |
| T σ_pred / σ_true | 0.25 | > 0.50 | > 0.80 |
| v₀ bias | +16% | < +8% | < +5% |
| Best epoch | 1/20 | > 3/5 | > 10/50 |
| Spike rate | sconosciuto | 10–20% | 10–20% |

---

> **Documenti correlati:**
> - `report_2.md` — allineamento ACC-IDM, cut-in, argparse
> - `training_plan.md` — procedura esecutiva Stage A/B/C
> - `optimization_ideas.md` — analisi completa idee e razionale
