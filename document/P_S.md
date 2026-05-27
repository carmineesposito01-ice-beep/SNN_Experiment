# P_S.md — Problemi & Soluzioni CF_FSNN

> **Ultima modifica:** 2026-05-27 01:00 CET
> **Sessione:** post-commit `4e01bcc` (12 fix SNN-expert review)
> **Stato:** Smoke training Azure (5 epoche, OneCycleLR max_lr=5e-3) **ABORTITO** a E01 B1026 per exploding gradient.

Documento vivo: ogni problema ha (1) descrizione, (2) firma diagnostica, (3) causa root,
(4) soluzioni in ordine di impatto. Le soluzioni si marcano `[ ] proposta`,
`[~] in test`, `[x] applicata`, `[!] scartata`.

---

## P1 — Exploding gradient deterministico a B1000/1485 (E01)

### 1.1 Descrizione
Il training su Azure con `--epochs 5 --scheduler onecycle --max_lr 5e-3 --tag A1_onecycle`
si è abortito per 20 batch consecutivi con `grad_norm = inf` (`max_inf_streak=20`)
all'epoca 1, intorno al batch 1000/1485.

### 1.2 Firme diagnostiche dal log
| Firma | Valore osservato | Significato |
|-------|------------------|-------------|
| Crescita `gn` | `2.5e-1` (B950) → `4.5e+12` (B1000) → `inf` (B1002+) | Salto di 12 ordini di grandezza in 50 step |
| Distribuzione gradiente per-layer | `layer_hidden.*` tutti `inf`, `layer_out.fc_weight` `1.4e-01` | Esplosione **confinata all'ALIF**, NO al LI di output |
| Stato dei pesi | `all finite, global_max_abs=1.718e+00` | `clip_grad_norm_(max=1.0)` azzera tutto → pesi mai aggiornati durante l'inf |
| Spike rate prima del crash | 1.3% → 3.1% → 5.0% → 5.1% | **Sotto target 10–25%**, vicino al regime di "dead network" (ch22 §22.2) |
| Determinismo | Esplosione sempre allo stesso batch | `SEED=42` + `shuffle=True` → ordine batch fisso → punto critico riproducibile |
| LR al crash | `2.474e-03` | OneCycleLR in discesa dal picco, ancora alto |
| Loss prima del crash | `0.4596` con `data=0.42, phys=0.19` | Loss **sana e decrescente**: NON è la fisica che esplode |

### 1.3 Causa root (ch22 §22.4 — Exploding Gradient)
**Classico exploding gradient da BPTT in rete ricorrente con surrogate ampia**, reso
deterministico dall'ordine di shuffle fissato.

Bound teorico del gradiente:
```
|∂L/∂W|  ≤  C · ∏_{t=1}^{T·n_ticks}  |β_eff · σ'(V_t − θ_t)|
```
- `β_eff = 1 − 1/2³ = 0.875` (bit-shift leak >>3)
- `σ'_max = 1/(1+γ·0)² = 1.0` con γ=0.3 in V=θ esatto
- `T · n_ticks = 100 × 5 = 500` step di BPTT

Il prodotto in serie tende al vanishing (`0.875^500 ≈ 0`), ma **la somma su N neuroni
ricorrenti correlati cresce come N^T**. Con N=2 neuroni "near threshold" e T=500
si supera 3.4e38 (limite float32) → `inf`.

### 1.4 Concause in ordine di severità
| # | Causa | Severità | Meccanismo |
|---|-------|----------|------------|
| 1 | BPTT troppo lungo (500 tick) + ricorrenza U×V | 🔴 ALTA | Somma esponenziale di gradienti correlati |
| 2 | γ=0.3 (surrogate ampia, ~3.3 unità) | 🟠 MEDIA | Molti neuroni contribuiscono al sum-grad |
| 3 | OneCycleLR `max_lr=5e-3` | 🟠 MEDIA | Adam amplifica i drift al picco |
| 4 | Spike rate basso (5%) | 🟡 BASSA | I pochi neuroni attivi assorbono tutto il gradiente |
| 5 | rec_U·rec_V + po2 quant. | 🟡 BASSA | Quantizzazione può portare ρ(W_rec) > 1 localmente |

### 1.5 Soluzioni proposte (ordine di implementazione)

#### A — Lower-hanging fruit (1 linea ciascuno, smoke rapido)
- [ ] **A1**: ridurre `max_lr` da `5e-3` a `2e-3` (o `1e-3` su prima prova)
- [ ] **A2**: ridurre `seq_len` da `100` a `50` → dimezza la profondità BPTT da 500 a 250
- [ ] **A3**: aumentare γ da `0.3` a `1.0` in `core/hardware.py` → kernel surrogate 3× più stretto, 3× meno neuroni che contribuiscono al sum-grad

#### B — Strutturali (più sicuri, richiedono test)
- [ ] **B4**: `detach()` sul reset path nell'ALIF (ch22 §22.3 fix #5): spezza la catena di gradiente attraverso `V ← V − z·θ_eff`
- [ ] **B5**: spike-rate regularizer: aggiungere `λ_sr · (spike_rate − 0.15)²` al loss per spingere sparsity verso 15% (target sano)
- [ ] **B6**: Truncated BPTT (TBPTT-20): backprop solo su chunk di 20 step invece dell'intera sequenza

#### C — Robustezza generale
- [ ] **C7**: warning soft quando `gn > 100` (anche se finito): segnalare prossimità all'overflow
- [ ] **C8**: monitorare ρ(rec_U·rec_V) post-quantizzazione; se > 0.95, rescalare init

### 1.6 Raccomandazione operativa
Smoke A1+A2 combinati: `max_lr=2e-3` + `seq_len=50`. Se elimina l'esplosione →
diagnosi confermata → applicare B4+B5 come cura strutturale.

---

## P2 — Checkpoint incompatibile: `Missing key "decode_scale"`

### 2.1 Descrizione
Dopo l'abort di P1, il blocco di raccolta dati G5/G7 ha tentato di caricare
`best_model.pt` per fare un pass finale sul val set, sollevando:
```
RuntimeError: Error(s) in loading state_dict for CF_FSNN_Net:
    Missing key(s) in state_dict: "decode_scale".
```

### 2.2 Causa root
Il commit `4e01bcc` (fix F5) ha aggiunto `decode_scale` come buffer registrato in
`CF_FSNN_Net.__init__()`. Il `best_model.pt` presente nella directory
`checkpoints/A1_onecycle/` è residuo di un run precedente al fix (commit `1292b7c`
o anteriore) e non contiene questa chiave.

Il training corrente si è abortito a metà E01, prima del primo `val_epoch` → nessun
**nuovo** `best_model.pt` è stato salvato → quello che viene caricato è il vecchio.

### 2.3 Soluzioni
- [ ] **D1**: cancellare manualmente `checkpoints/A1_onecycle/best_model.pt` (e simili
      stale) prima di rilanciare il training
- [ ] **D2**: caricare il checkpoint con `strict=False` in `train.py` riga ~813:
      ```python
      model.load_state_dict(best_ck['model_state'], strict=False)
      ```
      Sicuro perché `decode_scale` è un buffer derivato deterministicamente dai bounds
      nel costruttore (non è un parametro appreso). Il valore di default è corretto.
- [ ] **D3** (preferita a lungo termine): aggiungere un check di compatibilità
      `if 'decode_scale' not in best_ck['model_state']: print('[Compat] Old checkpoint, ignoring'); skip` per loggare il caso esplicitamente.

### 2.4 Raccomandazione operativa
Applicare D2 (1 riga di codice) come fix permanente + D1 una tantum per pulire
i residui sul cluster Azure.

---

## Log delle decisioni

| Data | Decisione | Stato |
|------|-----------|-------|
| 2026-05-27 01:00 | Documento creato a partire dalla diagnosi SNN-expert ch22 §22.4 | — |

---

## Riferimenti

- **Commit base:** `4e01bcc` (fix snn-expert review — 12 fix, 7 file)
- **Commit precedente stabile:** `1292b7c` (pre-review)
- **Skill diagnostica:** `SNN-expert / chapters/ch22-pathologies.md §22.4` (Exploding Gradient)
- **Report stato:** `document/report_4.md` (post-review)
- **Log Azure crash:** raccolto inline da console utente, sessione 2026-05-27
