# Dynamic_Study — il tetto sui parametri dinamici a/b: cause e piano di attacco

> **Versione**: 2026-06-20  (branch `Dynamic_Study`, milestone aperta dopo il merge di `Loss_Study` in `main`)
> **Lettore atteso**: chi riprende il progetto (anche da chat nuova) e vuole capire *perché* `a` e `b`
> non scendono sotto un certo errore, *come* lo stiamo studiando, e *quali* soluzioni sono in gioco.
> **Prerequisiti**: `document/LOSS_STUDY_AND_EVALUATION.md` (storia S1–S3 + validazione),
> `document/VALIDATION_REPORT.md` (stato della rete S3), `document/HOW_IT_WORKS.md` (architettura/loss).
> **Fonti expert usate**: skill `car-follow-expert` (ch11/12/16/17), skill `SNN-expert` (ch06/08/09/22).

---

## 0. TL;DR (milestone)

Dopo la validazione (rete S3 = `LS3_PEAK_R0_launch_d03`, 0 collisioni, string-stable), l'unico
limite residuo netto è l'errore sui **parametri dinamici**: NRMSE `a=0.26`, `b=0.30` (peggiori),
contro `s0=0.13`, `v0=0.22`, `T=0.25`. Predetti `a=0.66` (vero 1.1, −40%), `b=1.95` (vero 1.5, +30%).

La tesi di questo studio: **non è un tetto solo, sono due tetti impilati** —
1. un **tetto fisico/di identificabilità** (a/b sono osservabili solo nei transitori, e si accoppiano
   via √(a·b)), e
2. un possibile **affamamento del gradiente specifico della SNN** (β^T, surrogate, encoding) che **non
   è mai stato testato**.

Lo **Studio B** separa empiricamente i due (più una terza causa "di coordinate") con un esperimento
economico e locale (nessun checkpoint Azure). L'esito decide quale **batch di soluzioni** ha senso.
Una conclusione già solida: alzare l'accuracy di a/b **non** sblocca né il micro (closed-loop) né il
macro (capacità) — serve per realismo dei transitori, comfort, classificazione del driver, e per il
mandato "tutti e 5 i parametri".

---

## 1. Il problema, in numeri

Al checkpoint validato (epoca 33, minimo `val_data`):

| Param | NRMSE | Predetto | Vero | Bias | Regime in cui è osservabile |
|---|---|---|---|---|---|
| s0 | 0.133 | 2.84 m | 2.5 m | +0.34 | spaziatura a bassa velocità / fermo (persistente) |
| v0 | 0.224 | 32.4 m/s | 33.3 | −0.88 | crociera libera (free-flow) |
| T  | 0.251 | 1.46 s | 1.2 | +0.26 | following stazionario |
| **a**  | **0.262** | **0.66 m/s²** | **1.1** | **−0.44** | **solo accel. forte da bassa v (transitorio breve)** |
| **b**  | **0.305** | **1.95 m/s²** | **1.5** | **+0.45** | **solo avvicinamento/frenata con Δv>0 (transitorio)** |

Il ranking `s0 < v0 < T < a < b` **non è casuale**: è esattamente l'ordine di osservabilità previsto
dalla teoria (vedi §2).

---

## 2. Diagnosi unificata: due (tre) cause

### 2.1 Causa 1 — tetto fisico / di identificabilità (car-follow ch12, ch17)

- **L'equilibrio di following non contiene a né b.** Il gap di equilibrio è
  `sₑ(v) = (s0 + v·T) / √(1 − (v/v0)^δ)` (ch12 "Equilibrium gap"). Dipende **solo** da `s0, T, v0, δ`.
  Quindi *ogni* segmento vicino allo stazionario porta **zero informazione** su a, b. Da qui il fatto
  che identifichiamo bene ciò che plasma l'equilibrio (s0, v0, T) e male il resto.
- **`b` vive solo nel termine di avvicinamento** `v·Δv / (2·√(a·b))` dentro `s* = s0 + max(0, v·T + …)`
  (ch12, IDM). Questo termine è non-nullo **solo** quando ci si avvicina a un leader più lento (Δv>0):
  a Δv=0 (following stazionario) `b` è **completamente non osservabile**.
- **a e b entrano in quel termine come prodotto √(a·b).** I dati vincolano la **media geometrica**
  √(a·b); `b` è recuperabile solo di seconda mano come `(√(a·b))² / a`. È la ragione strutturale per
  cui `b` è il parametro peggiore.
- **`a` entra anche come cap saturante** `min(·, a)` nel forward IIDM: `∂min/∂a = 1` **solo** quando
  `a` è il vincolo che morde (veicolo accel-limitato), `= 0` altrimenti. In guida normale `a` è quasi
  invisibile; si vede solo nella finestra stretta "accelerazione forte da bassa velocità".
- **Classe del problema**: il libro lo chiama **calibrazione di Tipo II** — minimo *non-unico*, valle
  piatta nello spazio dei parametri (ch17, "Objective Function Types"). Rimedio testuale: *restringere
  i parametri non identificabili* (fissarli/vincolarli), non combattere la valle piatta. Inoltre esiste
  un **floor di residuo ~20%** sotto cui nessun modello scende (variazione intra/inter-driver, ch17).

### 2.2 La prova diretta: l'errore è sulla direzione "molle"

Dai nostri numeri (a=0.66, b=1.95 vs a=1.1, b=1.5):

| Coordinata | Predetto | Vero | Errore |
|---|---|---|---|
| **√(a·b)** (osservabile) | 1.13 | 1.28 | **−12% (quasi giusto)** |
| **a/b** (NON osservabile) | 0.34 | 0.73 | **×2.2 (completamente sbagliato)** |

Cioè: **la rete impara bene la combinazione osservabile √(a·b) e scarica TUTTO l'errore lungo il
rapporto a/b che nei dati non c'è.** Questo spiega anche perché il closed-loop è a 0 collisioni: la
dinamica del gap dipende da √(a·b) (preservato), non da a, b separati. È la firma classica della
sloppiness (coppia molle v0↔a già provata in S1b con corr=−0.82).

### 2.3 Causa 2 — affamamento del gradiente lato SNN (SNN ch06/08/22) — MAI TESTATA

a/b sono il caso da manuale "target debole + segnale precoce nel tempo", che la SNN affama in **tre**
modi simultanei:
- **Gradiente temporale che svanisce (β^T).** Il segnale del transitorio di frenata sta a inizio
  finestra; il gradiente decade come β^T verso la lettura in uscita → è il più attenuato (ch08 §8.5,
  ch22 §22.3). Rischio aggravante: se la finestra BPTT taglia a metà la frenata, `b` non riceve
  proprio gradiente.
- **Surrogate troppo stretto.** Un output debolmente accoppiato agli spike riceve gradiente da
  pochissime coppie (t, neurone). Va **allargato** (arctan α, dampening più ampio), non stretto
  (ch22 §22.6, ch08 §8.2).
- **Encoding che butta via la derivata.** La firma di `b` sta nella modulazione della frenata in
  funzione di Δv e del **jerk**; un encoding rate-style perde il *quando* del cambiamento (ch06
  §6.5/6.11). Servono canali derivata (Δv', jerk, ṡ) e/o encoding temporale/popolazione sui transitori.

### 2.4 Perché "EventProp pareggia BPTT" NON chiude la questione

Lo sweep EventProp ha concluso "floor architetturale, indipendente dal metodo di gradiente". Ma quel
verdetto è su **`val_data`** = RMSE di **accelerazione complessiva**, **non** sulla NRMSE per-canale di
a/b. Non dimostra affatto che il gradiente *di a/b* non sia affamato dal surrogate/encoding/finestra.
È un **buco aperto**, ed è esattamente ciò che lo Studio B chiude.

---

## 3. Studio B — separare le cause (decisivo, economico, locale)

Obiettivo: dire **quale** dei tre serbatoi domina, prima di scrivere soluzioni. Tutto locale (dati +
modello GT + un baseline classico + i numeri già nel log S3). Nessun Azure.

### B1 — Sensitività / Fisher information (quanta informazione c'è nei dati)
Per ogni tipo di scenario (incluso `launch`), calcola `∂(traiettoria di accelerazione)/∂θ` del modello
GT IDM lungo le traiettorie reali; aggrega in una **mappa sensibilità per-parametro × per-regime**.
- Atteso: sensibilità di `b` ≈ 0 ovunque tranne avvicinamenti forti; di `a` ≈ 0 tranne accel forte.
- Lettura: se la sensibilità è davvero ~0 → il tetto è **nei dati** (Causa 1).

### B2 — Baseline con ottimizzatore "perfetto" (l'informazione è recuperabile?)
Fitta i 5 parametri IDM agli **stessi** trajectory con un ottimizzatore classico non-SNN
(`scipy.optimize.least_squares`, Levenberg-Marquardt), obiettivo one-step su accelerazione (ch17:
local/one-step espone al massimo a e il termine di b).
- Se **nemmeno LM** recupera a/b → limite di **identificabilità** (Causa 1).
- Se LM li recupera ma la SNN no → il gap è **SNN-specifico** (Causa 2), **recuperabile a basso costo**.

### B3 — Check delle coordinate (l'errore è sulla direzione molle?)
Esprimi l'errore in `[a, √(a·b), a/b]` sia per la SNN (numeri già nel log S3) sia per LM.
- Se √(a·b) è buono e a/b è pessimo (come già visto in §2.2) → la cura è di **coordinate**
  (riparametrizzazione), non di dati.

### Matrice di decisione

| Esito B | Causa dominante | Soluzioni indicate |
|---|---|---|
| LM fallisce su a/b + sensibilità ~0 | 1 (identificabilità) | #1 riparam [a,√ab]+log, #5 incertezza; #6 modello solo se serve a valle |
| LM recupera a/b, SNN no | 2 (affamamento SNN) | #2 encoding derivata, #3 surrogate/TET/finestra, #4 S4 |
| √(ab) ok & a/b no (entrambi) | 3 (coordinate) | #1 riparametrizzazione |

Deliverable: `scripts/dynamic_study_B.py` (+ figure) e `document/DYNAMIC_STUDY_B_RESULTS.md`.

---

## 4. Il batch di soluzioni (mappato a cassetto + skill, condizionato a B)

| # | Leva | Cosa | Origine | Quando |
|---|---|---|---|---|
| 1 | **Riparametrizzazione [a, √(ab)] → derivo b** (+log-space per a,b,s0) | Cambia le *coordinate* di regressione verso le direzioni identificabili; **la fisica NON cambia** | car-follow ch17 + SNN; **NUOVO (non in cassetto)** | quasi sempre — basso rischio, attacca la radice geometrica |
| 2 | **Canali derivata + encoding del transitorio** | Aggiungi Δv', jerk, ṡ; encoding population/latency sui canali transitori (no rate-flatten) | SNN ch06 | se B → Causa 2 |
| 3 | **Surrogate sweep (arctan α, γ largo) + TET loss (loss a ogni tick) + finestra BPTT che copre l'intera frenata** | Sblocca il gradiente affamato di a/b | SNN ch08/22 | se B → Causa 2 |
| 4 | **S4: reweight PINN per-regime** | Residuo decel pesa b, accel pesa a (loss dove il param è osservabile) | cassetto **S4** + car-follow ch17 | complementare a 1–3 |
| 5 | **Propagazione dell'incertezza** | Uncertainty weighting omoschedastica; **dichiarare b a bassa confidenza** → il layer SLOW lo comunica e il controllore a valle è conservativo | multi-task; allineato al ruolo SLOW V2X | se B → Causa 1 (tetto vero) |
| 6 | **Future-B: smooth caps / decouple √(ab)** | Cambio di modello IIDM (rischioso) | cassetto **B-1/B-2** | solo se a/b servono a valle (oggi no) |

**Distinzione critica**: la riparametrizzazione (#1) **NON è aux**. L'aux per-canale su a/b è già stato
**rifiutato** in S3 come "aux travestito" (inietta la verità che vogliamo evitare). #1 non inietta
verità: cambia solo *cosa* la rete regredisce. Sono cose diverse.

**Scartati con motivo**:
- **Capacità (S2)**: non è la leva (il limite è il *manifold molle*, non la capacità; e comunque a/b
  non toccano l'equilibrio → vedi §5).
- **Rollout differenziabile multi-step**: ch17 avverte che l'integrazione globale *spalma* l'errore e
  **peggiora** a/b; il nostro `loss_data` è già one-step su accelerazione, che è l'ottimo per esporre
  a/b. Quindi NON andare verso il rollout multi-step.
- **EventProp**: non mira all'identificabilità di a/b (testa il *meccanismo* di gradiente, già
  falsificato come causa del floor `val_data`).

---

## 5. "Ne vale la pena?" — dove a/b contano davvero

Da tenere a mente per non ottimizzare un numero che non sblocca nulla a valle:
- **Micro / closed-loop**: **insensibile** a a/b (dipende da √(ab), già appreso) → 0 collisioni.
- **Macro / capacità**: l'equilibrio `sₑ(v)` **non contiene a né b** → migliorare a/b **non muove** il
  diagramma fondamentale. Il ~2× macro va attaccato su **T, v0, s0** (e/o il simulatore ad anello).

Quindi a/b servono per: **realismo dei transitori, comfort/jerk, fuel & emissions, classificazione
fine del driver, e il mandato di safety "tutti e 5 i parametri"** — non per le prestazioni micro/macro
odierne. Per questo **#5 (dichiarare l'incertezza)** è in alto: per un layer SLOW, "stimo b con bassa
confidenza e lo dico" può valere più di "stimo b al 75%".

---

## 6. Cosa il progetto già sa di a/b (carry-forward dal cassetto)

- **Decoder sempre a 5 parametri** (a/b mai droppati — safety).
- **Tetto di `a` ~0.65** (vero 1.1, NRMSE 0.26): portato da 0.43 collassato a 0.65 con il `launch`,
  poi si ferma. **Strutturale, non scarsità di dati** ("finestra limitata per costruzione del modello").
- **`a` invisibile in guida normale** (cap `min(·,a)` con gradiente nullo fuori dalla saturazione).
- **a/b accoppiati solo via √(a·b)** in `s_star`; v0↔a coppia molle (corr=−0.82).
- **launch** ha alzato il gradiente di `a` (1.23×) e a_pred 0.43→0.65, senza ricollasso; **freeflow**
  ha triplicato il gradiente di v0 ma lasciato a invariato (1.02×).
- **Aux su canali deboli rifiutato** come fix vero (destabilizza BPTT + "aux travestito").
- **Capacità (S2) sospesa**: modelli grandi esplodono in BPTT; root cause = manifold molle, non capacità.
- **Floor `val_data` ~0.22 architetturale** e indipendente dal metodo di gradiente (EventProp pareggia
  BPTT) — ma su accelerazione complessiva, **non** sulla NRMSE di a/b (vedi §2.4).

---

## 7. Stato e prossimi passi

- [x] Merge `Loss_Study` → `main` (milestone), apertura branch `Dynamic_Study`.
- [x] Report di validazione corretto (verso del bias `b`, intuizione √(ab)).
- [x] Questo piano documentato.
- [ ] **Studio B** (`scripts/dynamic_study_B.py`): B1 sensitività + B2 baseline LM + B3 coordinate →
      `document/DYNAMIC_STUDY_B_RESULTS.md`.
- [ ] In base a B: implementare il batch (probabile partenza da **#1 riparametrizzazione**, eventuale
      **#4 S4**; **#6** cambio modello resta in frigo finché un task a valle non lo richiede).

---

## 8. Riferimenti rapidi alle skill

| Tema | Skill / capitolo |
|---|---|
| Ruoli dei parametri IDM, equilibrio, √(a·b) | car-follow ch12 (strategy-based), ch11 (elementary) |
| Identificabilità, Tipo II, floor 20%, GoF, segmenti, riparametrizzazione | car-follow ch17 (calibration & validation) |
| String stability (dove a/b contano davvero) | car-follow ch16 |
| Surrogate width, BPTT/β^T, TET loss | SNN ch08, ch09 |
| Encoding derivata/transitori (Δv', jerk) | SNN ch06 (neural coding) |
| Patologie: vanishing/exploding, dead neurons | SNN ch22 |
