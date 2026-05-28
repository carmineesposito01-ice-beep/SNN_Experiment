# P_S.md — Problemi & Soluzioni CF_FSNN

> 📌 **Per il quick-start con zero contesto**: leggi `SESSION_RESUME.md` prima.
> 📚 **Per decode acronimi P/A/B/F/T/PF/G**: vedi `GLOSSARY.md`.
> 🔧 **Per workflow Azure end-to-end**: vedi `WORKFLOW.md`.
> 🏛️ **Per storia decisioni + lessons learned**: vedi `TIMELINE.md`.

> **Ultima modifica:** 2026-05-28 21:30 CET
> **Sessione:** post-P9_S1_highway_v2 (P9 CONFERMATO) + 2 eurekas utente + STEP 2A applicato
> **Stato corrente:** P9 (capacity insufficiency) CONFERMATO MATEMATICAMENTE: highway-only val=0.277 vs full-mix 0.354 (-22%). Entrambe le eurekas utente verificate: dancing reale ma Po2 non è il bottleneck (il livello del plateau è dato dalla capacity); training super-rapido confermato (90% miglioramento E1 in 10% di E1). STEP 2A (commit `ed8debb`) applicato: notebook con n_train=500, epochs=10, early_stop_delta=0.005. Smoke locale OK: 3 epoche, EARLY-STOP attivato, val=0.293, tempo ~9.5min CPU laptop (17× speedup per epoca). **NEXT: utente lancia P9_S2A_fast_baseline su Azure (~15-25 min atteso) per validare il regime fast-iteration prima di STEP 2B (parametric sweep capacity)**.

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
| **B5** [x] | Spike-rate regularizer `λ_sr·(spike_rate − 0.15)²` | **~85%** (rivisto post-P6_T2) | ~5 righe | Forza la rete a sparsity target 15% via loss. Non rompe nessun gradient path. **APPLICATA 2026-05-27** dopo che P6_T2_full ha confermato la firma "spike rate degenerante" (7%→3% in E2). |
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

## P7 — Spike-rate saturation (nuova firma post-B5)

### 7.1 Descrizione
Dopo l'applicazione di B5 (commit `a13afb6`), il training `P6_T3_full` ha mostrato un
nuovo pattern di crash: l'esplosione **NON è più graduale** (come in P6_T2_full senza B5),
ma **sporadica e correlata a saturation transitoria** della spike rate.

### 7.2 Firma diagnostica
- Spike rate medio E1-E3 **al target 12.55%** (B5 funziona)
- Picchi transitori di spike rate fino al **58%** (zona dead → saturated, ch22 §22.5)
- gn per batch normalmente 0.1-1.0, ma **picchi sporadici a 10⁹-10¹⁹** in coincidenza
  con i picchi di spike rate
- Esempio crash E3 B1466 (loss-batch 50 pre-crash = 0.40, vicino al plateau):
  ```
  B1463-1465: spike 56-58%, gn 0.7-1.0 (sopravvive)
  B1466: spike 56.2%, gn=INF  ← saturation prolungata + perturbation → cascade
  ```
- Streak fino a 88 inf consecutivi prima di EARLY-STOP (vs 47 in T2)

### 7.3 Causa root
L'esplosione in T3 NON è il problema diretto. La causa root è la **rete che oscilla**
attorno al plateau di capacità: quando i pesi sono saturi (vedi P9), piccole
perturbazioni (input difficili come cut-in) causano spike saturation → BPTT con tutti
i neuroni attivi → amplificazione catastrofica della catena ricorrenza U·V.

B5 ha risolto la "dead network degenerante" di T2 ma ha esposto questo nuovo regime
oscillatorio. **Aumentare LAMBDA_SR o asimmetria non è la soluzione vera**: la rete
è semplicemente troppo piccola per il task (vedi P9).

### 7.4 Decisione
- [!] Asimmetria/aumento LAMBDA_SR **NON consigliato come primo step** (trattamento
  sintomatico). Tenere in escalation se P9 non risolve.
- B5 da mantenere (rate target raggiunto, non degenera più verso 0%).

---

## P8 — Plateau val_loss ~0.35 (osservazione utente, confermata matematicamente)

### 8.1 Descrizione
Osservazione utente 2026-05-28: *"L'esplosione del gradiente accade sempre verso una
loss di 0.350. Che si arrivi più lentamente o meno, è sempre quel range."*

### 8.2 Verifica quantitativa
Analisi cross-run di **tutti** i training disponibili:

| Run | E1 val | E2 val | E3 val | Batch loss mediana | Stato |
|-----|--------|--------|--------|---------------------|-------|
| `A1_onecycle_v3` (B4 attivo) | — | — | — | 0.685 (50 batch) | crash precoce |
| `P6_T2_full` (A1+A2+A3) | **0.368** | crash | — | **0.368** | crash E2 |
| `P6_T3_full` (A1+A2+A3+B5) | **0.371** | **0.363** | **0.354** | **0.370** | crash E4 |

**Convergenza asintotica al plateau ~0.35-0.37 IDENTICA fra T2 e T3** — nonostante
B5 abbia modificato dinamiche interne (spike rate da 5% → 13%).

### 8.3 Significato
- La loss **non scende sotto 0.35** indipendentemente da:
  - Fix architetturali (A3 γ surrogate)
  - Fix parametrici (A1 max_lr, A2 seq_len)
  - Regolarizzatori (B5 spike rate)
- L'esplosione del gradiente NON è il problema da risolvere — è **conseguenza** del
  training oltre il plateau

### 8.4 Verifica osservazione "oltre causa instabilità"
Loss-batch std per epoca in P6_T3_full:
```
E1: std=0.19  (rete sta imparando attivamente)
E2: std=0.06  (assestata sul plateau)
E3: std=0.06  (sul plateau)
E4: std=0.05  (sul plateau MA con esplosioni periodiche → distruzione pesi)
```
Anche `spike_std`:
```
E1: 4.74%  (variabile, esploration)
E2: 1.86%  (stabile, sweet-spot)
E3: 5.44%  (rumore crescente)
E4: 3.19%  (rotture sporadiche)
```

**Pattern netto**: dopo E2, la rete è in un equilibrio meccanico. Il training continua
ad applicare gradient updates ma non c'è più segnale fisico da apprendere — solo
amplificazione di rumore.

### 8.5 Decodifica fisica del plateau
val_loss=0.35 corrisponde principalmente a:
- L_data (Masked RMSE accelerazione) ≈ 0.35 m/s²
- L_phys (residuo ACC-IDM) ≈ 0.12 m/s²

Stima del noise floor irreducibile del dataset:
- Rumore OU su s, v: σ ≈ 0.1 → contributo ad accelerazione ~ 0.10 m/s²
- Rumore OU su a (NOISE_ACCEL=0.1): σ = 0.10 m/s²
- Packet loss 2%: trascurabile (Masked RMSE esclude i frame mancanti)
- Stocasticità T (jump process IDM-2d): ~0.05 m/s²
- **Total noise floor stimato: ~0.15-0.18 m/s²**

Gap **0.35 - 0.15 = ~0.20 m/s² di errore "evitabile"** che la rete attuale non riesce
a ridurre → la rete non è limitata dal noise floor, ma dalla propria capacità.

---

## P9 — Capacity insufficiency (diagnosi root)

### 9.1 Descrizione
La rete CF_FSNN_Net attuale ha **864 parametri totali**:
```
layer_hidden.fc_weight        (32, 4)   = 128
layer_hidden.rec_U            (32, 8)   = 256
layer_hidden.rec_V            (8, 32)   = 256
layer_hidden.cell.base_thresh (32,)     =  32
layer_hidden.cell.thresh_jump (32,)     =  32
layer_out.fc_weight           (5, 32)   = 160
                                       -------
                                  TOTALE = 864
```

Per imparare 5 parametri IDM continui su:
- 4 scenari (highway, urban, truck, mixed)
- 20% cut-in events
- Rumore multiplo
- Sequenze temporali di 50-100 step

La rete è **sotto-dimensionata** rispetto al task. Confermato dall'osservazione di P8
(plateau a ~0.35 = 0.20 m/s² sopra noise floor).

### 9.2 Riferimento letteratura
ch22 SNN-expert §22.6 (underfitting/plateau): *"se la loss decresce ma stalla 5-10%
sopra ANN baseline → network too small, SNN typically needs ~1.5× ANN width for same
accuracy"*.

Nel nostro caso non abbiamo un ANN baseline, ma:
- Treiber Ch17 indica RMSE accelerazione "buona" come 0.1-0.2 m/s² per ACC reale
- Stiamo a 0.35 — circa **2× sopra** il target

### 9.3 Soluzioni proposte (Tier 4 — NUOVO rispetto a P6)

| # | Soluzione | Modifiche | Prob. fix plateau | Costo HW |
|---|-----------|-----------|-------------------|----------|
| **E1** | Hidden: 32 → 64 ALIF | `CF_HIDDEN_SIZE=64` in config.py | **~70%** | x2 footprint FPGA |
| **E2** | Rank: 8 → 16 | `CF_RANK=16` in config.py | ~40% (solo ricorrenza) | x2 mult ricorrenti |
| **E3** | E1+E2 combinati | 2 valori in config.py | **~85%** | x2-x3 footprint |
| **F1** | Early stopping (`patience=2` su val_loss) | ~10 righe in train.py | 0% per il plateau, **100%** per evitare crash | Zero |
| **F2** | Cosine scheduler con `eta_min=1e-5` (forte decadimento finale) | 1 CLI flag | ~30% (riduce updates dopo plateau) | Zero |
| **G1** | Scope ridotto (solo `highway`, no `cut_in`) — debug | `SCENARIO_MIX={'highway':1.0}` + `CUT_IN_RATIO=0.0` | Diagnostico: conferma capacity | Zero per debug |

### 9.4 Sequenza raccomandata

**Step 1 — Diagnostico (zero modifiche al codice base)**:
- Lanciare `P6_T3_full` con **early stopping** e `SCENARIO_MIX={'highway':1.0}` per
  vedere se su task semplificato la rete scende sotto 0.35.
- Se SÌ → conferma capacity insufficiency, procedere E1+E2 (Step 2).
- Se NO → il problema è altrove (analisi più approfondita).

**Step 2 — Aumento capacità (modifica config)**:
- Applicare E3: `CF_HIDDEN_SIZE=64`, `CF_RANK=16`
- Mantenere tutti i fix attuali (A1+A2+A3+B5)
- Aggiungere F1 (early stopping) per sicurezza
- FULL training su Azure

**Step 3 — Tuning fisico** (se Step 2 OK):
- Cambiare scheduler (cosine vs onecycle)
- Bilanciare lambda weights
- Ottimizzare hyperparam del modello fisico

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
| 2026-05-27 20:30 | FULL P6_T2_full su Azure: E1 completa (val=0.37, miglior risultato!), esplode E2 B2395 | ⚠️ stabile poi degenera |
| 2026-05-27 20:30 | Diagnosi P6_T2: spike rate degenera (7%→3% in E2) → dead network → esplosione | ✓ identificato |
| 2026-05-27 21:00 | Applicato B5: spike-rate regularizer L_sr=(sr-0.15)², LAMBDA_SR=0.5 | [x] applicato |
| 2026-05-27 21:00 | Smoke locale B5 OK: L_sr correttamente calcolato (~0.019 per spike=1.3%) | ✅ validato |
| 2026-05-28 10:30 | FULL P6_T3_full Azure: 3 epoche complete (val 0.371→0.363→0.354), crash E4 | ⚠️ stabile poi degenera |
| 2026-05-28 11:00 | Osservazione utente: "esplosione SEMPRE verso loss ~0.35" | 🔍 verificata |
| 2026-05-28 11:00 | Osservazione utente: "oltre il sweet-spot c'è solo instabilità" | 🔍 verificata |
| 2026-05-28 11:00 | CONFERMA matematica plateau ~0.35: T2 mediana 0.368, T3 mediana 0.370 | ✓ confermato |
| 2026-05-28 11:00 | NUOVA DIAGNOSI: rete UNDERSIZED (864 param insufficienti per task multi-scenario) | ✓ identificato |

---

## Riferimenti

- **Commit base post-12-fix:** `4e01bcc`
- **Commit telemetria + preflight + P2 D2:** `1ff3da9`
- **Commit fix terminologia ACC-IDM:** `ed4906d`
- **Commit B4 (poi rollback):** `3d1fd9a`
- **Commit rollback B4:** vedi git log
- **Skill diagnostica:** `SNN-expert / ch22 §22.4` (Exploding Gradient), `§22.2` (Dead Network)
- **Crash log A1_onecycle_v3:** `results/A1_onecycle_v3/` (CSV + grafici G8-G12)

---

## P10 — Config drift: scenario_mix/cut_in non controllabili da CLI

### 10.1 Descrizione
Test `P9_S1_highway_only` (2026-05-28) lanciato con TAG e CACHE_PATH corretti, ma
`config.py` su Azure NON era stato modificato. Risultato: dataset generato con
distribuzione full-mix (highway 50%, urban 30%, truck 10%, mixed 10%, cut_in 20%),
training BIT-PER-BIT identico a P6_T3_full. Confermato:
- val_loss E1=0.371, E2=0.363, E3=0.354 identici a P6_T3
- G13 plots includono `urban` e `highway_cutin` (impossibili in highway-only)
- Locale: `CUT_IN_RATIO=0.20`, `SCENARIO_MIX` originale

### 10.2 Causa root
SCENARIO_MIX e CUT_IN_RATIO erano costanti globali in `config.py`, modificabili
solo via editing manuale del file. Su un sistema cloud con notebook persistente,
questa è una fonte naturale di errori (dimenticanza, modifica non salvata, ecc.).

### 10.3 Soluzione applicata (questo commit)
- [x] `data/generator.py`: `parse_scenario_mix()` + `_sample_scenario()` e
      `generate_dataset()` accettano override opzionali per scenario/cut_in
- [x] `train.py`: nuovi CLI args `--scenario_mix` (es. 'highway', 'highway:0.7,urban:0.3')
      e `--cut_in_ratio` (float). Sanity check warning se cache esistente ha
      scenari inattesi.
- [x] `Training_File.ipynb`: aggiunti `scenario_mix` e `cut_in_ratio` al CONFIG,
      cache path include lo scenario per evitare collisioni cross-esperimento.
- [x] Notebook ora **tracciato in git**: sync via pull, zero modifica manuale.

### 10.4 Validazione smoke
`python train.py --smoke --scenario_mix highway --cut_in_ratio 0.0 ...`
- "Scenari: {'highway': 100}, Cut-in: 0 (0.0%)" ✓
- "[Dataset config] scenario_mix={'highway': 1.0, ...}" ✓
- val_loss 0.341 in 1 epoca smoke (vs 0.37 plateau full-mix)

---

## P11 — Early stopping: prevenire crash post-plateau + risparmio compute

### 11.1 Descrizione
Tutti i FULL run precedenti hanno mostrato la stessa firma (vedi P8):
1. Training migliora val_loss fino a ~0.35 in 2-3 epoche
2. Oltre il plateau, training continua a girare ma NON migliora
3. Eventualmente esplode (P6_T2 in E2, P6_T3 in E4) o satura (P7)

Su Azure CPU, una epoca costa ~2700s (~45min). Far girare 5 epoche oltre il
plateau spreca compute E aumenta la probabilità di crash. Senza early stopping,
ogni nuovo esperimento rischia di crashare nel finale.

### 11.2 Soluzione applicata (questo commit)
- [x] `train.py`: nuovi CLI args `--early_stop_patience` e `--early_stop_delta`
- [x] Loop epoche: conta epoche consecutive senza miglioramento di
      `val_loss > delta`. Quando raggiunge `patience`, interrompe il training.
- [x] `Training_File.ipynb`: `early_stop_patience=2` e `delta=1e-4` di default
      nel CONFIG.

### 11.3 Impatto stimato
Su 5 epoche con plateau a E3 (caso P6_T3):
- Senza early stop: 5 epoche × 2700s = 13500s = **3.75 ore**, alto rischio crash
- Con early stop patience=2: training si ferma a E3 (E2 e E3 non migliorano oltre
  delta) = 3 epoche × 2700s = **2.25 ore**, no crash post-plateau
- **Risparmio: ~40% compute + eliminazione rischio crash su run plateau-saturi**

### 11.4 Relazione con altri P
- **Risolve P7 (saturation post-B5)**: ferma prima che la rete saturi
- **Mitiga P8 (plateau val~0.35)**: non spreca compute oltre il plateau
- **Compatibile con P9 (capacity insufficiency)**: per aumentare il plateau servirà
  cap. increase strutturale, ma early stop ci protegge nel frattempo

---

## Log delle decisioni (aggiornato)

| Data | Decisione | Stato |
|------|-----------|-------|
| 2026-05-28 16:53 | Run P9_S1_highway_only fallito (config.py drift) | ❌ identico a P6_T3 |
| 2026-05-28 17:15 | Decisione: rendere scenario/cut_in CLI-controllabili (P10) | accettato utente |
| 2026-05-28 17:15 | Decisione: aggiungere early stopping (P11) per evitare plateau crash | accettato utente |
| 2026-05-28 17:15 | Decisione: trackare Training_File.ipynb in git | accettato utente |
| 2026-05-28 17:30 | P10 + P11 implementati, smoke locale OK (val=0.341 highway-only) | [x] applicato |
| 2026-05-28 17:30 | NEXT: ri-eseguire P9_S1 con TAG `P9_S1_highway_v2` | in attesa utente |
| 2026-05-28 20:05 | P9_S1_highway_v2 completato: val=0.2768 (-22% vs full-mix plateau 0.354) | ✅ P9 CONFERMATO |
| 2026-05-28 20:30 | Osservazione utente: 90% miglioramento E1 in ~10% di E1 → fast-iteration mode | accettato |
| 2026-05-28 20:30 | STEP 2A applicato: notebook con n_train=500, epochs=10, early_stop_delta=0.005 | [x] applicato |
| 2026-05-28 20:30 | Smoke locale STEP 2A: 3 epoche × ~160s, EARLY-STOP attivato a E3, val=0.292 | ✅ validato |
