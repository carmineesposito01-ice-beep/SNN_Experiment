# P_S.md — Problemi & Soluzioni CF_FSNN

> 📌 **Per il quick-start con zero contesto**: leggi `SESSION_RESUME.md` prima.
> 📚 **Per decode acronimi P/A/B/F/T/PF/G/R/V/W**: vedi `GLOSSARY.md`.
> 🔧 **Per workflow Azure end-to-end**: vedi `WORKFLOW.md`.
> 🏛️ **Per storia decisioni + lessons learned**: vedi `TIMELINE.md`.
> 📖 **Per audit roadmap R1/R2/R3**: vedi `AUDIT_2026-06-02.md`.

> **Ultima modifica:** 2026-06-10 sera CET
> **Sessione:** R26 Fusion Study (in esecuzione su Azure)
> **Stato corrente:** **R26 IN CORSO** (6 run, ~1h Azure, HEAD `6075a96`). Tre fix sequenziali avanzati: (1) **BUGS_2026-06-03**: 4 bug strutturali risolti → tutti i ranking pregress invalidati. (2) **R24F**: rerun 93 esperimenti Prodigy MultiParam → V08 cosine_no_restart è il setup vincente (val 0.169/0.189/0.222 su highway/mixed/full, batte AdamW del 9-18%). Problema scoperto: **T predetto piatto intra-sample**. (3) **R25 Ablation causale** 18 run: **3 WIN INDIPENDENTI** trovati per T-tracking: A4 (max_delay 18, ΔT_corr +0.090), B1 (lambda_T_aux 0.1, ΔT_corr +0.147), C1 (lambda_sr 0, ΔT_corr +0.088). (4) **R26 Fusion** testa se i 3 win sommano → F1 TRIPLE atteso T_corr ~0.55-0.62 vs baseline 0.353. Branch `Prodigy_Deep_Study`. Vedi **P19** (T-tracking flat) per dettagli completi.

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

## P9 — Capacity insufficiency (diagnosi root) — **❌ FALSIFICATO 2026-05-29**

> ⚠️ **AGGIORNAMENTO 2026-05-29**: Sweep STEP 2B sui 5 valori di hidden_size (32, 48, 64, 96, 128) ha mostrato val_best ∈ [0.2789, 0.2802] (range 1.3 millesimi su 11× parametri). **Capacity NON è il bottleneck**. Plateau ~0.28 è strutturale, attribuibile ad altre cause (vedi P12). Sezione mantenuta per storico.

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

## P12 — Plateau val_loss ~0.28 non risolvibile da capacity (NUOVO — 2026-05-29)

### 12.1 Descrizione
Dopo il sweep STEP 2B su 5 capacità (h=32, 48, 64, 96, 128 con rank corrispondente
h/4), i val_best convergono in un range strettissimo:

| h | r | params totali | val_best (best epoca) |
|---|---|---|---|
| 32 | 8 | 869 | 0.2802 (E2) |
| 48 | 12 | 1685 | **0.2789** (E3) ★ best |
| 64 | 16 | 2757 | 0.2790 (E3) |
| 96 | 24 | 5669 | 0.2797 (E4) |
| 128 | 32 | 9605 | 0.2792 (E4) |

**Range**: 0.0013 su 8736 parametri di differenza tra il più piccolo e il più grande.

### 12.2 Firme diagnostiche
- **Tutti i runs si fermano a E4** per early-stop aggressivo (`delta=0.005, patience=2`)
- **OneCycleLR con `epochs=10`**: alla E4 siamo solo al 40% del ciclo, la decay phase
  profonda (E7-E10) non viene MAI raggiunta
- **Spike rate normale** (8-11%) per tutti — nessun dead-neuron collapse su highway
- **Zero inf grad batches** su tutti i 5 runs — landscape stabile su highway
- **Curva val tipo**: 0.288 → 0.280 → 0.279 → 0.282 (oscillation 1-3 millesimi)

### 12.3 Diagnosi al 2026-05-29

**Cause root candidate** (in ordine di probabilità):
1. **Minimi locali** + OneCycle troncato + early-stop aggressivo:
   - I 5 runs vedono solo la peak/early-decay phase del lr schedule
   - Le oscillazioni 0.279 ↔ 0.282 sono tipiche del sample SGD vicino a un minimo locale
   - **Da testare**: scheduler con warm restart (cosine), più epoche, early-stop tollerante
2. **Saturazione dataset** (n_train=500 highway-only):
   - Possibile che 500 trajs ≈ 50k finestre saturino l'informazione apprendibile
   - **Da testare**: n_train=1500 (3×)
3. **PINN loss Pareto tradeoff**:
   - L_data + L_phys + L_ou + L_bc + L_sr formano un fronte di Pareto
   - Sotto val ~0.28 forse non si può scendere perché ridurre L_data costa troppo
     su L_phys/L_ou
   - **Da testare**: ablation pesi λ (e.g., lambda_phys=0.05, lambda_ou=0.01)
4. **Po2 quantization forward floor**:
   - Sub-set finito di pesi rappresentabili genera un "floor" strutturale
   - Coerente con eureka utente originale "Po2 dancing"
   - **Da testare**: confronto FP32 vs Po2 quantizzato (ablation)

### 12.4 Soluzioni proposte (STEP 2C)

#### Tier 1 — Costo zero, alto ROI
- [ ] **A1 (STEP 2C-α)**: AdamW (wd=1e-4) invece di Adam
- [ ] **A2 (STEP 2C-α)**: CosineAnnealingWarmRestarts (T_0=10, T_mult=2, eta_min=1e-5)
      invece di OneCycle troncato
- [ ] **A3 (STEP 2C-α)**: LR warmup 5 epoche lineare
- [ ] **A4 (STEP 2C-α)**: epochs=40, early_stop_patience=8, delta=5e-4
- [ ] **A5 (STEP 2C-α)**: SWA da epoca 75% (Stochastic Weight Averaging via
      `torch.optim.swa_utils`)

#### Tier 2 — Costo medio (SAM forza flat minima)
- [ ] **B1 (STEP 2C-β)**: SAM wrapper sopra AdamW (rho=0.05), 2× tempo per step
- [ ] **B2 (STEP 2C-β)**: snapshot ensemble (1 ckpt per warm restart, ensemble inference)

#### Tier 3 — R&D originale (opzionale)
- [ ] **C1 (STEP 2C-γ)**: SurrogateSAM — variante SAM che perturba anche γ del surrogate

### 12.5 Decision tree post-STEP-2C

| val_best STEP 2C-α | Diagnosi | Action |
|---|---|---|
| < 0.20 | **Minimi locali confermati** — ricetta SOTA risolve | Espandi a urban+truck con stessa ricetta + B2 |
| 0.20–0.27 | **Plateau ammorbidito** ma non eliminato | Tier 2 SAM o Tier 3 SurrogateSAM |
| ≥ 0.27 | **Plateau strutturale duro** | Ablation Po2 (FP32 vs quant.) + ablation λ PINN |

### 12.6 Relazione con altri P
- **Sostituisce P9 falsificato** come problema attivo
- **Compatibile con P13 (scenario crashes)**: i fix di P12 sono ortogonali

---

## P13 — Scenario-specific crashes (urban dead-neurons, truck post-converg.) (NUOVO — 2026-05-29)

### 13.1 Descrizione
Lo sweep STEP 2B ha mostrato che scenarios non-highway crashano in modi
DIVERSI a parità di h64_r16 + recipe identica:

| Scenario | E1 | best | epoche prima crash | spike% | gn_max | Modalità di crash |
|---|---|---|---|---|---|---|
| highway | 0.2878 | **0.2790** | n/a (early stop normale) | 10.5% | 2.4e+01 | ✅ OK |
| urban | 0.4769 | 0.3884 (E2) | **3** | **0.6%** ⚠️ | 1.56e+19 | Dead-neurons → grad inf |
| truck | 0.1807 | **0.1601** (E5) | **5** | 9.8% | 2.10e+19 | Post-convergence grad explosion |

### 13.2 Diagnosi differenziale

**Urban (Cause: dead neurons → vanishing → no gradient → explosion)**:
- Spike rate 0.6% → ~63 dei 64 hidden neurons sono morti
- I pochi che sparano concentrano TUTTO il gradiente → magnitude amplificate
- Velocità basse + stop&go aggressivi → input poco diversificati → surrogate
  attiva solo neuroni in regime molto specifico
- **Classica ch22 §22.2 "Dead Network" + §22.4 "Exploding Gradient"**

**Truck (Cause: oversconvergence → lr troppo alto in decay phase)**:
- Spike rate 9.8% → sano, no dead neurons
- val_best 0.1601 è ECCELLENTE (43% migliore di highway)
- Crash a E5 quando il modello ha "già imparato": il OneCycle è nella fase di
  decay ma `max_lr=2e-3` ancora troppo alto per i wide-flat minima trovati
- **NUOVO failure mode**: "trained too well" + scheduler troppo aggressivo

### 13.3 Soluzioni proposte (post-STEP 2C)

#### Urban (anti dead-neurons)
- [ ] **D1**: aumentare lambda_sr da 0.5 a 2.0 → forza sparsity 15% indipendentemente
- [ ] **D2**: threshold annealing iniziale (v_th=0.5 → 1.0 sui primi 5 epoch) per
      evitare dead-neurons iniziali
- [ ] **D3**: surrogate γ annealing (1.0 → 5.0 lineare) → inizia larga,
      restringe verso fine. Più neuroni attivi all'inizio del training.

#### Truck (anti post-convergence explosion)
- [ ] **D4**: max_lr ridotto a 1e-3 (era 2e-3) per scenario truck
- [ ] **D5**: aggressive lr decay dopo prima convergenza
- [ ] **D6**: gradient clipping ridotto a 0.5 (era 1.0) per scenario truck

### 13.4 Implicazione architetturale
**Truck val=0.16 è la prova che la nostra rete a 864-2757 parametri PUÒ raggiungere
val < 0.20 su un task specifico**. Non è capacity-limited (vedi P9 falsificato),
è scenario-tuning limited. Il problema STEP 2C/D è far funzionare la stessa rete
su TUTTI gli scenari.

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
| 2026-05-29 00:00 | P9_S2A_fast_baseline completato (h32_r8 highway, n_train=500): val=0.2802 in 4 epoche, riproducendo `P9_S1_highway_v2` (0.2768) con 10× meno dati | ✅ STEP 2A validato |
| 2026-05-29 02:00 | STEP 2B sweep notebook creato: `Training_File_Sweep.ipynb` (7 celle, 9 runs pianificati: 5 capacity highway + 4 scenario diversity) | [x] applicato |
| 2026-05-29 04:00 | Sweep eseguito su Azure: 7 runs su 9 completati (h32, h48, h64, h96, h128 highway OK + urban CRASH E3 + truck CRASH E5). Mixed e hwcut15 mai partiti dopo crash _push_results | parziale |
| 2026-05-29 09:00 | Bug `_push_results` fixato (no import torch nel kernel Jupyter Azure) — commit `534c2af` | [x] applicato |
| 2026-05-29 09:30 | nbstripout setup: `.gitattributes` + install Cella 0 → mai più "would be overwritten by merge" | [x] applicato |
| 2026-05-29 10:00 | **Analisi cross-run STEP 2B**: capacity sweep val_best ∈ [0.2789, 0.2802] (Δ=1.3‰ su 11× param) → **P9 FALSIFICATO** | ✅ diagnosi |
| 2026-05-29 10:30 | **Truck val_best=0.16** rivela che la rete CAN raggiungere val < 0.20 su task specifici → problema non capacity, problema scenario-tuning | ✓ insight |
| 2026-05-29 10:30 | Apertura P12 (plateau non-capacity) + P13 (scenario crashes) | [x] aperti |
| 2026-05-29 11:00 | Osservazione utente: "molti test fermati prima → minimi locali?" | ✓ valida |
| 2026-05-29 11:30 | Studio approfondito ottimizzatori SOTA per SNN (skill + web): AdamW+CosineWR base, SAM/SAST(2026), Prodigy, Lion, Sophia, ADMM-SNN | ✓ catalogato |
| 2026-05-29 12:00 | Decision matrix: vincitori AdamW+SAM (21) e AdamW+SurrogateSAM R&D (21) | proposto |
| 2026-05-29 12:00 | STEP 2C-α design: AdamW + CosineWarmRestart(T_0=10) + warmup 5 + SWA + epochs=40 + n_train=1500 + h64_r16 highway | proposto |
| 2026-05-29 12:00 | STEP 2C-β condizionale: + SAM (rho=0.05) se 2C-α non scende sotto 0.20 | proposto |
| 2026-05-29 12:00 | STEP 2C-γ opzionale R&D: SurrogateSAM (originale, non in letteratura) | proposto |
| 2026-05-30 16:30 | STEP 2C eseguito (branch `Optimizer_Exploration`): Plan A Prodigy lr=1.0 b=1 → **COLLASSO/freezing** (178/200 batch inf grad E01, val congelato 0.5879 E2-E15) | ❌ Prodigy lr=1.0 incompatibile con BPTT-SNN |
| 2026-05-30 16:30 | Plan B AdamW lr=2e-3 b=8 OneCycle → **val=0.2805 @E14** (coerente baseline STEP 2A 0.2802) | ✅ AdamW conferma plateau ~0.28 |
| 2026-05-30 19:00 | Sweep calibrazione Prodigy (6 config: lr × batch × d_coef) eseguito | [x] applicato |
| 2026-05-30 20:30 | **Regola empirica scoperta**: `lr_effective = lr × d_coef` determina stabilità. ≤0.3 OK, >0.3 freeze | ✓ insight metodologico |
| 2026-05-30 20:30 | **Miglior Prodigy**: #1 (lr=0.1 b=1 dc=1.0) → val=0.2823 (vs AdamW 0.2805, Δ=+0.0018) | ✅ Prodigy ≈ AdamW |
| 2026-05-30 21:00 | Decisione: AdamW resta optimizer scelto. Prodigy archiviato in FUTURE_WORK F1 (re-test post-floor) | accettato utente |
| 2026-05-30 21:00 | **Conferma floor strutturale**: 9 setup diversi → 0.279-0.290 (range 11‰) | ✅ floor confermato |
| 2026-05-30 21:30 | Branch `Floor_Diagnostic` creato da Optimizer_Exploration. STEP 2D inizia: 3 plan F1/F2/F3 (Po2 differita) | [x] applicato |
| 2026-05-30 22:30 | F1 (no PINN): val=0.2738 (Δ=-0.0067) → PINN multi-obj NON è il colpevole | ✓ escluso |
| 2026-05-30 22:30 | **F2 (no OU): val=0.2262 (Δ=-0.0543 = -19.3%)** → 🏆 OU noise è UN colpevole | ✅ identificato |
| 2026-05-30 23:30 | F3 (n_train=5000): val=0.2802 (Δ=-0.0003) → dataset size NON è il colpevole | ✓ escluso |
| 2026-05-31 09:00 | STEP 2D-bis design: F5/F6/F7 per decomporre il residuo 0.226 (incl. Po2 con toggle reversibile) | [x] applicato |
| 2026-05-31 09:30 | `core/hardware.py` + `train.py`: aggiunto toggle `--po2_enabled {0,1}` LIVE via env var. Rollback istantaneo, validato. | [x] applicato |
| 2026-05-31 12:30 | **STEP 2D-bis completato**: decomposizione finale del floor. **Apertura P14**. | ✅ |

---

## P14 — Decomposizione finale del floor val~0.28 (NUOVO — 2026-05-31)

### 14.1 Descrizione

Il floor val ≈ 0.28 osservato in 9 setup diversi (capacity sweep STEP 2B + ottimizzatore sweep STEP 2C + Plan A/B Optimizer_Exploration) è stato **completamente decomposto** dal floor diagnostic STEP 2D + STEP 2D-bis (branch `Floor_Diagnostic`). 7 esperimenti F1-F7 hanno isolato il contributo quantitativo di ogni fattore candidato.

### 14.2 Risultati F1-F7 (tutti reproducibili da `results/P12_S2D_*/`)

| Plan | Config (vs baseline AdamW) | val_best | Δ vs REF | Conclusione |
|------|----------------------------|----------|----------|-------------|
| REF | AdamW b=8 OneCycle (tutto ON) | 0.2805 | — | floor totale |
| F1 | `lambda_phys=ou=bc=0` (no PINN multi-obj) | 0.2738 | -0.0067 | PINN ≈ trascurabile |
| F2 | `noise_scale=0` (no OU noise) | **0.2262** | **-0.0543** | 🎯 OU è 19.3% del floor |
| F3 | `n_train=5000` (dataset 3.3×) | 0.2802 | -0.0003 | dataset size irrilevante |
| F5 | `noise_scale=0 + lambda_sr=0` | 0.2256 | -0.0549 | SR ≈ 0% (solo 0.2% vs F2) |
| F6 | `noise_scale=0 + po2_enabled=0` | 0.2256 | -0.0549 | Po2 ≈ 0% (solo 0.2% vs F2) |
| F7 | `noise_scale=0 + lambda_sr=0 + po2_enabled=0` | **0.2198** | -0.0607 | "floor pulito" — residuo architettura |

### 14.3 Decomposizione quantitativa del floor 0.2805

```
Floor totale 0.2805 = 100% del problema
├─ OU noise              0.0543   ← 19.3%   (irriducibile in deploy: simula errori V2X)
├─ Spike-rate regularizer 0.0006   ← 0.2%   (trascurabile)
├─ Po2 quantization      0.0006   ← 0.2%   (TRASCURABILE — sorprendente)
├─ SR × Po2 interaction  0.0052   ← 1.9%   (piccola sinergia)
└─ Residuo architettura  0.2198   ← 78.4%  (DOMINANTE — limite SNN+data attuale)
                          ─────
                          0.2805   ✓ check (somma = floor totale)
```

### 14.4 Insight chiave

1. **Po2 è essenzialmente gratis** (0.2% del floor). Decisione utente di mantenere Po2 in deploy PYNQ-Z1 è confermata ottimale: zero costo, massima compatibilità FPGA.
2. **OU noise è il 51% del "riducibile"** ma è **irriducibile in produzione** (rappresenta errori V2X reali). In training si può rimuovere, ma in deploy gli errori esistono.
3. **78.4% del floor è limite architettura/dati**. Non si abbatte con: capacità (sweep 2B), ottimizzatore (sweep 2C), scheduler, dataset size (F3), rimozione PINN (F1), Po2/SR (F5/F6).
4. **F7 trajectory mostra trend DOWN @E15** (best 0.2198 ancora in miglioramento). Con più epoche potrebbe scendere a ~0.215. Ma il dominio architettura resta.
5. **Anomalia F7 `val_ou=0.010`** (vs 5e-6 negli altri): rimuovendo SR + Po2 insieme, la rete diventa "sloppy" sulla regressione di T. SR/Po2 agivano da regolarizzazione implicita su T.

### 14.5 Implicazioni operative

- **Per il deploy**: Po2 ON resta (zero costo). Si accetta floor ~0.28 come prodotto del setup attuale.
- **Per la ricerca**: il margine di miglioramento è nel **residuo architettura** (78%). Servono interventi STRUTTURALI per scendere sotto 0.22.
- **Per il training BPTT**: F7=0.2198 con BPTT+surrogate+architettura attuale è plausibilmente vicino al limite di questo paradigma di training. Cambiare paradigma (es. **EventProp**) potrebbe sbloccare ulteriore margine.

### 14.6 Stato P14

🟢 **CHIUSO** — il floor è completamente caratterizzato. Le decisioni successive (STEP 2E e oltre) si basano su questa decomposizione consolidata. Vedi `FUTURE_WORK.md` per opzioni di mitigazione.

---

## Log delle decisioni (estensione 2026-05-31)

| Data | Decisione | Stato |
|------|-----------|-------|
| 2026-05-31 12:30 | Decomposizione floor consolidata. **P14 chiuso**. Po2 contribuisce 0.2% → resta ON in deploy. | ✅ |
| 2026-05-31 12:30 | Documentazione completa (P_S, SESSION_RESUME, TIMELINE, GLOSSARY, FUTURE_WORK) | [x] applicato |
| 2026-05-31 12:30 | Branch `Optimizer_Exploration` + `Floor_Diagnostic` merged → `main` | [x] applicato |

---

## P15 — A1 baseline ha `lambda_sr=0` (errato vs F2 vincente con `lambda_sr=0.5`)

### 15.1 Descrizione
Architecture_Exploration step P15_S2E ha introdotto A1 baseline come "default" della factory `build_model('baseline')`, ma con `lambda_sr=0.0`. Tutte le 6 run T30 successive hanno propagato l'errore. La vera baseline pre-EventProp (`P12_S2D_F2_no_ou`, commit `5a2c7ee`) aveva `lambda_sr=0.5` attivo.

### 15.2 Firma diagnostica
- T30 baseline run hanno spike rate medio 2.7-5.6% (target era 15-20% definito mesi fa)
- Nessuna pressione esplicita al target spike rate durante training
- Violin G7 collassati per 4/5 params (highway-only + nessun regolarizzatore)

### 15.3 Causa root
Architecture_Exploration → introduzione `--arch_variant baseline` come default factory, con CLI flags hardcoded `lambda_sr=0` invece di `lambda_sr=0.5`. Nessun audit dei lambdas vs run pre-existing.

### 15.4 Soluzioni applicate
- [x] R1.7 (2026-06-02): aggiunta sub-cartella `Arch_Tested/BASELINE_BPTT_864p_PRE_EVENTPROP/` con setup F2 corretto (`lambda_sr=0.5`) come **riferimento canonico** per studi R2/R3.
- [x] `A1_baseline_BPTT_864p/README.md` marcato DEPRECATED con avviso "NON usare per studi R2/R3".
- [x] `Arch_Tested/README.md` evidenzia BASELINE_PRE_EVENTPROP con ⭐ e tabella diff vs A1.

---

## P16 — AUDIT_2026-06-02: 5 affermazioni dichiarate ma non dimostrate

### 16.1 Descrizione
Audit ascetico user-driven post-8 run T30 ha identificato 5 conclusioni "celebrate" senza basi solide:

| # | Affermazione | Status |
|---|---|---|
| (a) | "EventProp non funziona / è fragile" | ❌ non dimostrato — mai testato con tuning serio (clip aggressivo, warmup, init scaling, detach periodico, thresh_jump learnable). Domanda R3. |
| (b) | "Prodigy non aggiunge valore vs AdamW" | ❌ non dimostrato — config testate erano default Prodigy lib, non setup canonical kohya/community (vedi V1-W7 in GLOSSARY). Domanda R2 in esecuzione. |
| (c) | "A8 attn è la migliore architettura" | ❌ non dimostrato — mai confrontato con A1 a parità capacity (~3500p, h=64 r=16). Possibile overfit di rumore in highway-only. |
| (d) | "Spike rate 4% va bene per FPGA" | ❌ contraddice target storico 15-20%. P15 root cause. |
| (e) | "Capacity non è bottleneck" (P14) | ❌ riaperto — P14 era a 4 ep, A8 a 30 ep. Non comparabile. |

### 16.2 Firma diagnostica
Pattern ricorrente: "vedo numeri → dichiaro verdetto → vado avanti" senza:
- verifica che setup abbia testato l'ipotesi giusta
- chiusura onesta delle sotto-questioni aperte
- coerenza con conclusioni precedenti

### 16.3 Causa root
- `lambda_sr=0` sistemico (P15)
- Training highway-only sistemico → violin collassati universali
- Scheduler ad-hoc per metodo senza razionale
- Single-seed per ranking (rumore ≈ margini dichiarati)
- Mancanza di baseline canonical stabile

### 16.4 Soluzioni in corso
- [x] `AUDIT_2026-06-02.md` documenta tutte le 5 affermazioni con grado di confidenza
- [x] R1 (`Arch_Tested/`) — preserva architetture per riproduzione futura
- [x] R1.7 — fix BASELINE_PRE_EVENTPROP come canonical
- [x] R2.1 — `PRODIGY_DEEP_STUDY.md` ricerca multi-fonte (paper + 5 GitHub Issues + community)
- [⏳] R2.2 — 5 esperimenti diagnostici P-A..P-E in esecuzione Azure (~1.5h)
- [ ] R3 — Studio EventProp serio (pending, post R2)
- [ ] R4 (futuro) — scenari misti, sweep multi-seed, capacity sweep a 30ep, `lambda_sr` attivo

---

## P17 — Prodigy `d` frozen a ~1e-3 nei nostri T30 (failure mode F2 community-documentato)

### 17.1 Descrizione
Tutte le 4 run T30 Prodigy hanno `prodigy_d` valore stabile attorno a 1e-3 per tutte le 30 epoche. Prodigy NON sta facendo D-adaptation, sta degenerando in SGD a lr piccolo.

### 17.2 Firma diagnostica
- `prodigy_lr_eff` ~ 1e-3 plateau
- `prodigy_d` non sale dal valore iniziale
- val_data converge come AdamW lr=1e-4 (lento ma stabile)

### 17.3 Causa root (community wisdom, vedi `PRODIGY_DEEP_STUDY.md` §13)
Failure mode F2 documentato in `PRODIGY_DEEP_STUDY.md`:
- `d0=1e-6` (default) troppo conservativo vs scala dei gradient nostro BPTT chain 500 tick
- `betas=(0.9, 0.999)` (default) → `beta3=0.9995` decay troppo lento per 5700 step
- `d_coef=1.0` (default) — community raccomanda `2.0`
- `use_bias_correction=False` (default) — community raccomanda True
- `scheduler=none` — `cosine_no_restart T_max=epochs` raccomandato

### 17.4 Soluzioni in test (R2.2)
- [⏳] Esperimento P-D: bump `d0` da 1e-6 a 1e-5 (V2 fix konstmish ufficiale)
- [⏳] Esperimento P-B: `betas=(0.9, 0.99)` (W1 madman404 "dramatic improvement")
- [⏳] Esperimento P-C: `d_coef=2.0` (W2 community consensus)
- [⏳] Esperimento P-E: SETUP CANONICAL completo + `cosine_no_restart` (vero benchmark)
- [ ] Verdetto + parte 3 doc da scrivere post-Azure

---

---

## P18 — Highway-only confounder: `val_total` ingannevole, violin G7 collassati universalmente

### 18.1 Descrizione
R2.3 analisi dei 5 esperimenti Prodigy diagnostici ha rivelato pattern UNIVERSALE: tutti gli esperimenti hanno violin G7 con 4-5 params completamente collassati ai bounds (v0 max, T min, s0 max, a min, b min). La rete predice CONSTANTS, non sta veramente decodificando.

### 18.2 Firma diagnostica
- Cinque setup Prodigy diversi (default, W1, W2, V2, CANONICAL) → val_total range 0.228-0.303
- TUTTI hanno G7 violin collassati ai bounds
- val_total pareggia F2 baseline (0.226) per W1/V2/E ma è "fitting di costanti", non decoding parametrico vero
- Pattern già osservato in T30 baseline_adamw, A3_stacked_skip, EVPROP_ALIF — è un confounder pregress

### 18.3 Causa root
Training su `scenario_mix=highway` → tutti gli scenari hanno IDM_HIGHWAY identici (v0=33.3, T=1.2, s0=2.5, a=1.1, b=1.5). Una rete che predice valori CONSTANTS (qualunque) ottiene loss residua bassissima perché tutti i target sono uguali. Non c'è gradient informativo per imparare a decodificare la varianza scenario-specifica.

### 18.4 Implicazioni
- **`val_total` in highway-only NON è metric robusta per ranking optimizer/arch** (Lezione M1)
- **Tutti i ranking T30/SW/P15 sono confusi dallo stesso problema** — il "best" e il "worst" potrebbero essere reti che predicono medie diverse, non discriminative learning
- **Verdetto Prodigy vs AdamW richiede scenari misti** (R4) per essere conclusivo
- **VIOLIN G7 va sempre controllato** prima di celebrare un val_total (Lezione M2)

### 18.5 Soluzioni proposte
- [ ] R4 (futuro, prerequisito): training su scenari MISTI (highway+urban+truck+cut-in) con IDM params variabili — sarà il primo training "non-degenere" del progetto
- [ ] Workflow update: ogni report di esperimento DEVE includere screenshot violin G7 (non solo numero val_total)
- [x] Doc parte 3 PRODIGY_DEEP_STUDY.md (Lezioni M1-M4) documenta il pattern

---

## P19 — 4 bug strutturali in core/network.py (BUGS_2026-06-03)

### 19.1 Descrizione
Audit codice profondo richiesto dall'utente dopo aver notato che TUTTI i run R2.4 mostravano violin G7 con saturazione universale dei params (T fisso a 2.5 o 0.5, s0 al MAX/MIN, ecc.). 4 bug strutturali trovati in `core/network.py` + `core/eventprop.py`.

### 19.2 Firma diagnostica
- Random init (no training): saturation **96-97%** per T/s0 (`(|raw_eq|>5).mean()` post-`sigmoid`)
- Gradient s0/b ≈ **0.00004** (5000× più piccoli di a)
- 78% dei pesi LI con gradient zero
- A8 (attn) funziona "by accident" perché `attn=sigmoid(QK)·V` comprime magnitudo PRIMA del LI → raw_out piccolo → sigmoid non satura

### 19.3 Cause + Fix (dettagli in BUGS_2026-06-03.md)

| # | File | Sintomo | Fix applicato |
|---|---|---|---|
| 1 | `core/network.py:380-381` `_decode_params` | `raw_eq = raw / decode_scale` amplifica 9-18× per T/s0/a/b → sigmoid satura | Rimosso, ora `sigmoid(raw)` puro |
| 2 | `core/network.py:59-64` `OutputLayer_LI` | `xavier_uniform_` ha row_mean ≠ 0 → con spike binari, bias deterministico | `fc_weight.sub_(fc_weight.mean(dim=1, keepdim=True))` post-Xavier |
| 3 | `CF_FSNN_Net_Stacked`, `_StackedSkip` | base_threshold=1.5 troppo alto per ALIF non-input riceventi spike sparsi | `base_threshold.fill_(1.0)` per layer i>0 |
| 4 | `HiddenLayer_ALIF` + `ALIFLayer_EventProp_Full` | Delay mask 1/max_delay → var(current) ridotta di max_delay | `fc_weight.mul_(max_delay**0.5)` post-Xavier |

### 19.4 Soluzioni
- [x] **Fix 1+2+3+4 applicati** (commit `d9d558a`, tag `pre_bug_fix_2026-06-03`)
- [x] Verifica empirica post-fix: saturation **0%** (vs 96-97%), spike rate 6-10%, gradient ≠ 0 su 5/5 canali
- [x] Smoke A1 2ep × 50 step: val_total = **0.213** in 100 step (vs floor pregress 0.22 dopo 5700 step) → convergenza 57× più veloce
- [x] R24F rerun completo 93 esperimenti su codice fixato (commit successivi)

### 19.5 Conseguenze
- **TUTTI i ranking pregress** (T30, P15, SW, R2.2, R2.4 highway, **R24 multiparam pre-fix**) sono CORROTTI
- Il floor val_total ≈ 0.22 NON era architetturale — era il floor della sigmoid saturation
- A8 era best "by accident" — pre-fix solo A8 imparava davvero (compensava il bug)

---

## P20 — T-tracking flat: la rete fa "average estimation" non "system identification"

### 20.1 Descrizione
Post-fix BUGS_2026-06-03, R24F (93 esperimenti, scenario mixed, Prodigy V08 cosine) ha rivelato: la rete impara MOLTO meglio (val_total da 0.22 → 0.169-0.189), MA visualmente in G13 il `T_pred(t)` è una **linea piatta intra-sample** che NON segue `T_true(t)` quando fa step. La rete predice valore costante = media globale, non identifica il T del driver corrente.

### 20.2 Firma diagnostica
- G13 trajectory: T_predicted = costante con rumore (~1.1-1.2), T_true fa step 1.0↔1.5 ignorati
- G7 violin: distribuzione T larga (cross-driver OK) → la rete distingue driver diversi
- ma intra-driver: T predetto è quasi costante (std intra-seq bassa)
- val_T_tracking_corr Pearson aggregato baseline ≈ **0.35** (intermedio, non zero)
- Anche v0/s0 saturano vicino ai bound (v0 → 30-45, s0 → 1.2-5 con peak vicino al MAX)
- `a` sempre vicino al MIN (0.3-0.4) cross-scenario

### 20.3 Causa
Più ipotesi (R25 ablation 18 run ha indagato):
- **Memoria temporale insufficiente**: max_delay=6 → 60ms memoria sinaptica, troppo corta per identificare dinamica T che cambia ogni ~5-10s
- **Mancanza di supervisione diretta su T**: `L_data` lavora sull'output ACC-IDM (accelerazione), non direttamente sui params decoded. La rete non riceve gradient esplicito "T deve essere X"
- **L_sr regularizer**: la pressione su spike rate altera la dinamica della rete in modo dannoso per T-tracking
- **Più training PEGGIORA T**: la rete continua a affinare la fisica (val_data ↓) ma deprime T-tracking (corr ↓)

### 20.4 Soluzioni testate in R25 — 3 WIN INDIPENDENTI

| ID R25 | Modifica | ΔT_corr | Δval | Note |
|---|---|---:|---:|---|
| **A4** | `max_delay 6→18` | **+0.090** | -0.015 | ✅ memoria sinaptica più lunga sblocca T |
| **B1** | `--lambda_T_aux 0.1` (nuovo flag) | **+0.147** | -0.006 | ⭐ supervisione diretta T, NESSUN trade-off |
| **C1** | `--lambda_sr 0.0` | **+0.088** | -0.014 | ✅ L_sr era controproducente per T |

**Diminishing returns + trade-off**:
- B2 (T_aux=1.0): T_corr +0.21 ma val_total +0.04 (rete sacrifica fisica per T)
- B3 (T_aux=10): T_corr +0.22 ma val_total ESPLODE a 0.54 (10× il gradient su T schiaccia gli altri)
- C2/C3 (sr alto): spike rate raggiunge 14% target FPGA, MA T_corr crolla del 70%

**Insight tecnico**: gradient unbalance INVERTITO post-fix. Pre-fix v0 dominante. Post-fix T è il canale dominante (gn_out_fc_T=0.23 vs v0=0.01, 23× sbilanciato). Quindi T_corr=0.35 non è limitato da gradient magnitude ma dalla **direzione semantica**: B1 NON cambia magnitudo ma fa puntare il gradient T verso T_true GT.

### 20.5 R26 Fusion (in corso)
Test ortogonalità: F1=A4+B1+C1 (TOP candidato). Atteso T_corr ~0.55-0.62 se sommano linearmente.
- F2/F3/F4 = coppie controllo per isolare interazioni
- F5 = F1 + epochs=5 (E asse R25 suggerisce meno training)
- Linearity test automatico in Cell 6: ratio F1_measured/R25_predicted

### 20.6 Caveat sulla metrica
`val_T_tracking_corr` cattura 2 fenomeni mescolati:
1. **Cross-driver alignment**: driver con T_true=1.2 → T_pred basso; T_true=2 → T_pred alto
2. **Intra-driver dynamics**: T_pred(t) segue T_true(t) dentro la stessa sequenza

I 0.35 baseline sono quasi tutti (1). Il +0.15 di B1 è probabilmente (2). Per disambiguare servirebbe `val_T_intra_corr` (Pearson dopo aver rimosso la media per-sample). TODO post-R26.

---

## Log delle decisioni (estensione 2026-06-02)

| Data | Decisione | Stato |
|------|-----------|-------|
| 2026-06-02 mattina | AUDIT_2026-06-02 scritto come radice della nuova roadmap | ✅ |
| 2026-06-02 pomeriggio | R1 Arch_Tested/ creato (4 arch + smoke 1ep×1step) | ✅ |
| 2026-06-02 pomeriggio | R1.7 fix: BASELINE_PRE_EVENTPROP aggiunto (vera baseline F2, lambda_sr=0.5) | ✅ |
| 2026-06-02 sera | R2.1 PRODIGY_DEEP_STUDY.md parte 1+2 (ricerca multi-fonte) | ✅ |
| 2026-06-02 sera | R2.2 setup: 4 nuovi CLI flag Prodigy + scheduler cosine_no_restart + notebook 5 esperimenti redesigned | ✅ |
| 2026-06-02 sera | Sub-folder convention `results/<Study>/` adottata | ✅ |
| 2026-06-02 sera | Azure esecuzione R2.2 in corso (~1.5h, 5 esperimenti × ~15-17 min) | ⏳ |
| 2026-06-02 notte | R2 verdetto + PRODIGY_DEEP_STUDY.md parte 3 (post-Azure) | pending |
| TBD | R3 EventProp serio (paper + 7 lever isolati) | pending |
| TBD | Decisione utente: i 5 branch storici (Architecture_Exploration, Floor_Diagnostic, Optimizer_Exploration, Training_Method_Exploration, Visualizer_Building) restano intatti per ora; archive (tag+delete) rimandato | in attesa utente |
