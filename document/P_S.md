# P_S.md — Problemi & Soluzioni CF_FSNN

> **Ultima modifica:** 2026-05-27 19:00 CET
> **Sessione:** post-rollback B4 + applicazione A3 (γ=1.0)
> **Stato corrente:** Rollback B4 (commit `858cdc7`) + A3 applicata (questo commit). Prossimo step: FULL training su Azure con TAG `P6_T2_full` e CONFIG `max_lr=2e-3, seq_len=50` (Tier 2: A1+A2+A3). Smoke locale di A3 validato (61 batch, gn max 6.3, no inf).

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
**STATO 2026-05-27:** D2 applicato (commit `1ff3da9`). [x]

---

## P5 — Fallimento di B4: incompatibilità con SurrogateSpike_Hardware

### 5.1 Descrizione
Commit `3d1fd9a` applicava B4 (`.detach()` sul reset path ALIF). Il training successivo
`A1_onecycle_v3` (5 epoche, OneCycleLR `max_lr=5e-3`) si è abortito a **E01 B146/1485**
(primo `inf grad` a B126, EARLY-STOP a B146) — **PRIMA del solito** B1000.

### 5.2 Firme diagnostiche
| Firma | Valore | Significato |
|-------|--------|-------------|
| gn iniziale (B1) | `62.0` | vs ~`4.2` del run pre-B4 → ~15× più alto |
| Esplosione gn | B100 (gn~10²) → B125 (gn~10¹⁵) in 25 batch | crescita esponenziale rapidissima |
| `gn_hidden_base_threshold` | **NaN per tutti i 146 batch** | `p.grad is None` → parametro **non apprende** |
| `gn_hidden_thresh_jump` | **NaN per tutti i 146 batch** | come sopra |
| Spike rate | inchiodato a **1-2%** | rete dead network (target 10-25%, ch22 §22.2) |
| Layer esplosivi | `fc`, `rec_U`, `rec_V` insieme da B120 | catena ricorrenza (#3) attivata |

### 5.3 Causa root
File `core/hardware.py`, classe `SurrogateSpike_Hardware`:
```python
def backward(ctx, grad_output):
    # ...
    return grad_output * spike_pseudo_derivative, None   # ← None = NO grad to threshold
```
Il surrogate restituisce `None` per il gradiente verso threshold (scelta
hardware-friendly per FPGA: backward più semplice da implementare in VHDL/Verilog).

Conseguenza: l'**unico** path di gradiente per `base_threshold` e `thresh_jump`
era attraverso il **reset chain** `V ← V − spike·eff_thresh`. Detacharlo
con B4 ha completamente eliminato la possibilità di apprendere la soglia adattiva.

Senza fatigue learning:
1. Spike rate non si auto-regola → resta basso (1-2%)
2. I pochi neuroni che firano concentrano tutto il segnale → variance del gradiente alta
3. La catena ricorrenza U·V amplifica → esplosione **prima del solito** (B126 vs B1000)

### 5.4 Decisione
- [!] **B4 SCARTATO** — incompatibile con la nostra `SurrogateSpike_Hardware` custom.
- Commit di rollback: questo commit (vedi git log).
- Per spezzare la catena BPTT serve un approccio che NON tocchi il reset path,
  oppure modifica simultanea di `SurrogateSpike_Hardware.backward` per propagare
  anche al threshold (ma cambia il design hardware — scelta strutturale).

### 5.5 Lesson learned
La letteratura SNN (Bellec 2018, ch22 §22.3) consiglia detach reset assumendo un
surrogate gradient STANDARD (es. SLAYER, snnTorch fast-sigmoid) che propaga su
ENTRAMBI gli input. I fix da manuale vanno verificati contro l'implementazione
specifica del surrogate prima di applicarli.

---

## P6 — Nuovo plan diagnostico post-rollback (revisione del piano originale)

Dopo il rollback di B4, lo stato del codice è equivalente a `ed4906d` (post-fix
terminologico) + telemetria T + preflight PF già attivi. Tutte le **CLI-only**
soluzioni proposte nel piano originale (Tier 1) sono ancora valide e non
richiedono modifiche al codice.

### 6.1 Strategia rivista (in ordine di priorità)

| # | Soluzione | Prob. risoluz. | Costo | Razionale post-P5 |
|---|-----------|----------------|-------|-------------------|
| **A1+A2** | `max_lr=2e-3` + `seq_len=50` | **~75%** | 2 CLI flag | TESTATO già in Tier 1 del plan originale (preflight era PASS). Da rilanciare per validare su 5 epoche. Zero modifiche al codice → ZERO rischio di regressioni. **PRIMO da provare**. |
| **A3** [x] | γ surrogate `0.3` → `1.0` in `core/hardware.py` | **~50%** | 1 valore | Surrogate 3× più stretta → meno neuroni near-threshold contribuiscono al sum-grad. Sicura perché non tocca path di gradiente — solo magnitudo. NON propaga comunque al threshold (preservato il design HW). **APPLICATA 2026-05-27.** |
| **B5** | Spike-rate regularizer `λ_sr·(spike_rate − 0.15)²` | **~60%** | ~5 righe | Forza la rete a sparsity target 15% via loss. Non rompe nessun gradient path. Specialmente utile data la firma "spike rate troppo basso" che abbiamo visto in entrambi i run. |
| **B6** | Truncated BPTT (TBPTT-20) | **~85%** | ~20 righe | Hard cap matematico sulla profondità BPTT. Massima efficacia, ma cambiamento più invasivo. Da escalare solo se A+B falliscono. |
| ~~B4~~ | ~~detach reset~~ | — | — | [!] SCARTATO definitivamente (vedi P5) |

### 6.2 Combinazioni e prob composte rivedute

| Combinazione | Prob. fix | Razionale |
|--------------|-----------|-----------|
| **Tier 1**: A1+A2 (solo CLI) | **~75%** | ZERO modifiche codice. Da fare per primo. |
| **Tier 2 rivisto**: A1+A2 + A3 | **~88%** | Aggiunge γ=1.0 — modifica minima (1 valore in `core/hardware.py`). |
| **Tier 3 rivisto**: A1+A2 + A3 + B5 | **~94%** | Aggiunge il regularizer di sparsity. |
| **Tier 4**: + B6 (TBPTT) | **~98%** | Solo come escalation finale. |

### 6.3 Workflow iterativo (con stop ad ogni step)

```
Step 1  [A1+A2 — CLI only, no code changes]
        python scripts/preflight.py --base_tag P6_T1 --extra --max_lr 2e-3 --seq_len 50
        python train.py --epochs 5 --scheduler onecycle --max_lr 2e-3 --seq_len 50
                        --data_cache data/cache_1500.pt --tag P6_T1_full
        → checkpoint utente: condividere risultati

Step 2a [se Step 1 OK]
        ✅ Diagnosi BPTT confermata, modello converge. Continua con normale
        tuning (cosine, plateau, lambda weights).

Step 2b [se Step 1 KO]
        Applicare A3: gamma 0.3 → 1.0 in core/hardware.py
        python scripts/preflight.py --base_tag P6_T2 --extra --max_lr 2e-3 --seq_len 50
        python train.py --epochs 5 --scheduler onecycle --max_lr 2e-3 --seq_len 50
                        --data_cache data/cache_1500.pt --tag P6_T2_full
        → checkpoint utente

Step 3  [se Step 2b KO]
        Applicare B5 in train.py pinn_loss()
        + LAMBDA_SR = 0.01 in config.py
        Re-test
        → checkpoint utente

Step 4  [escalation finale]
        Implementare B6 (TBPTT-20)
```

---

## Log delle decisioni

| Data | Decisione | Stato |
|------|-----------|-------|
| 2026-05-27 01:00 | Documento creato a partire dalla diagnosi SNN-expert ch22 §22.4 | — |
| 2026-05-27 13:51 | Applicato B4 (commit `3d1fd9a`) seguendo plan originale | [x] applicato |
| 2026-05-27 16:00 | Training A1_onecycle_v3 abortito a B146 con B4 attivo | ❌ FAILED |
| 2026-05-27 18:30 | P5 documentato, B4 [!] SCARTATO, rollback eseguito | [x] rollback |
| 2026-05-27 18:30 | P6 nuovo plan: A1+A2 come prossimo step (zero modifiche codice) | proposto |
| 2026-05-27 19:00 | Revisione strategia: salto a Tier 2 (A1+A2+A3) per evitare fallimento prevedibile | accettato utente |
| 2026-05-27 19:00 | A3 applicato: γ surrogate 0.3 → 1.0 in core/hardware.py | [x] applicato |
| 2026-05-27 19:00 | Smoke locale A3 (max_lr=2e-3, seq_len=50): 61 batch, gn max 6.3, no inf | ✅ validato |

---

## Riferimenti

- **Commit base post-12-fix:** `4e01bcc`
- **Commit telemetria + preflight + P2 D2:** `1ff3da9`
- **Commit fix terminologia ACC-IDM:** `ed4906d`
- **Commit B4 (poi rollback):** `3d1fd9a`
- **Commit rollback B4:** vedi git log
- **Skill diagnostica:** `SNN-expert / ch22 §22.4` (Exploding Gradient), `§22.2` (Dead Network)
- **Crash log A1_onecycle_v3:** `results/A1_onecycle_v3/` (CSV + grafici G8-G12)
