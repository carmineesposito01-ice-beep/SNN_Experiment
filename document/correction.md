# Correzioni per project_core_guidelines.md

---

## LEGGENDA VARIABILI

### Segnali di ingresso (V2X)

| Simbolo | Significato | Unità |
|---|---|---|
| s | Gap spaziale tra veicolo ego e leader (bumper-to-bumper) | m |
| v | Velocità del veicolo ego | m/s |
| Δv | Velocità relativa = v_ego − v_leader (positivo = ego più veloce) | m/s |
| v_l / v_leader | Velocità assoluta del veicolo leader | m/s |
| a_l | Accelerazione del veicolo leader (stimata da diff. finite + filtro OU) | m/s² |
| ā_l | Accelerazione del leader "cappata" = min(a_l, a) — evita assunzioni ottimistiche | m/s² |

### Parametri del modello CF (output della rete — 5 valori predetti)

| Simbolo | Significato | Unità |
|---|---|---|
| v₀ | Velocità desiderata in free flow | m/s |
| T | Time gap target (distanza temporale desiderata dal leader) | s |
| s₀ | Gap minimo a riposo (distanza di sicurezza a v=0) | m |
| a | Accelerazione massima confortevole | m/s² |
| b | Decelerazione confortevole (valore positivo) | m/s² |

### Variabili interne del modello ACC-IDM

| Simbolo | Significato | Note |
|---|---|---|
| s* | Gap desiderato: s₀ + max(0, v·T + v·Δv / (2√(a·b))) | Funzione di v, Δv e dei parametri predetti |
| a_IIDM | Accelerazione calcolata con IIDM (base del modello) | Regime free-flow separato da regime following |
| a_CAH | Accelerazione dalla Constant Acceleration Heuristic | Anticipa la frenata del leader |
| a_ACC | Accelerazione finale ACC-IDM (uscita del blocco fisico) | Blend pesato tra a_IIDM e a_CAH |
| c | Coolness factor = 0.99 (fisso — non predetto dalla rete) | Controlla il peso della CAH; c≈1 → quasi sempre CAH attiva |

### IDM-2D stocastico (estensione su T)

| Simbolo | Significato | Valore |
|---|---|---|
| T(t) | Time gap variabile nel tempo (processo OU) | Fluttua in [T₁, T₂] |
| T₁ | Limite inferiore del time gap | 0.8 s |
| T₂ | Limite superiore del time gap | 1.6 s |
| τ | Costante di tempo del processo OU su T | 30 s |
| τ_al | Costante di tempo del filtro OU sulla stima di a_l | 1 s |

### PINN loss

| Simbolo | Significato |
|---|---|
| λ_data | Peso del termine di fedeltà ai dati |
| λ_phys | Peso del residuo fisico (violazione dell'equazione ACC-IDM) |
| λ_OU | Peso del vincolo OU (T deve rimanere nel range [T₁, T₂]) |
| λ_bc | Peso della penalità di crash (boundary condition di sicurezza) |
| SRMSE | Symmetric Root Mean Square Error — errore normalizzato sulla traiettoria |
| v̇ | Accelerazione del veicolo ego (derivata di v rispetto al tempo) | m/s² |

### Rete neurale (FSNN — neuroni ALIF e LI)

| Simbolo | Significato | Valore/Note |
|---|---|---|
| V | Potenziale di membrana del neurone | Variabile di stato, si accumula tra i tick |
| θ | Soglia di spike (adattiva in ALIF — cresce quando il neurone spara) | Base: 1.5 |
| γ | Parametro di nitidezza del surrogate gradient | 0.3 — controlla quanto ampio è il "gradiente finto" attorno a θ |

---















## SEZIONE 1 — Errori da correggere (trova e sostituisci)

| Posizione | Testo attuale | Testo corretto |
|---|---|---|
| Sezione ARCHITETTURA, modulo laterale | `controllore PID o MCP` | `controllore PID o MPC` (Model Predictive Control) |
| Sezione Algoritmo di Training | `Physics-Injected Neural Network` | `Physics-Informed Neural Network` |

---

## SEZIONE 2 — Aggiunta: Architettura della rete neurale (sostituisce il blocco "Rete neurale")

Sostituire il blocco attuale con:

```
## Rete neurale
**Spiking Neural Network (FSNN v5.1 — adattata per car-following)**

Architettura: 4 → 32 → 5

| Layer   | Tipo            | Dettagli                                                     |
|---------|-----------------|--------------------------------------------------------------|
| Input   | —               | 4 segnali V2X: [s, v, Δv, v_leader]                         |
| Hidden  | ALIF            | 32 neuroni, rank=8, max_delay=6 tick, soglia adattiva        |
| Output  | LI (Leaky Int.) | 5 neuroni, no spike — potenziale usato direttamente come output |

**Output della rete (parametri predetti):** `[v₀, T, s₀, a, b]`
Questi sono i parametri del modello di car-following (ACC-IDM con base IIDM).

**Quantizzazione Po2:**
I pesi sono quantizzati in `{2⁻⁴, 2⁻³, 2⁻², 2⁻¹, 2⁰, 2¹}`.
Ogni moltiplicazione diventa un bit-shift → **zero DSP sul PYNQ-Z1**.
Questo è il motivo per cui la rete è compatibile con FPGA a basso consumo.

**Surrogate gradient:** `1 / (1 + γ|V − θ|)²` con γ = 0.3

**Temporizzazione:** 1 tick = 0.1 s (allineato a V2X 10 Hz, standard ETSI ITS-G5)

**TBPTT (Truncated Backprop Through Time):** seq_len = 100 tick, stride = 50 tick

> NOTA: Maggiori informazioni sull'architettura base nel file `FSNN_ Evoluzione delle Reti Neurali Spiking.pdf`
```

---

## SEZIONE 3 — Aggiunta: Modello CF (inserire dopo il paragrafo sull'architettura)

Aggiungere questa nuova sezione:

```
## Modello di Car-Following — ACC-IDM con base IIDM

### Razionale della scelta
Il modello IDM puro fallisce su UC2 (Abrupt Cut-In): reagisce con decelerazione
istantanea al taglio del gap → panic braking. L'ACC-IDM aggiunge la CAH (Constant
Acceleration Heuristic) che rende la risposta anticipatoria e graduata.
La base IIDM (invece di IDM plain) risolve la dispersione di v₀: in IDM i veicoli
non raggiungono mai esattamente la velocità target; IIDM separa i regimi free-flow
e car-following in modo più preciso.
Il documento di analisi completa è in `cf_model_recommendation.md`.

### Formula ACC-IDM

```
a_IIDM = base IIDM (regime free-flow separato dal regime following)
a_CAH  = v² · ā_l / (v · ā_l / s + (v − v_l)² / (2s))   con ā_l = min(a_l, a)

Se a_IIDM ≥ a_CAH:
    a_ACC = a_IIDM

Altrimenti:
    a_ACC = (1 − c) · a_IIDM + c · [a_CAH + b · tanh((a_IIDM − a_CAH) / b)]
    con c = 0.99  (fisso — non predetto dalla rete)
```

### Parametri predetti dalla rete

| Parametro | Significato                  |
|-----------|------------------------------|
| v₀        | Velocità desiderata          |
| T         | Time gap target              |
| s₀        | Gap minimo a riposo          |
| a         | Accelerazione massima        |
| b         | Decelerazione confortevole   |

### Estensione IDM-2D stocastica su T
T(t) fluttua nel tempo tramite processo Ornstein-Uhlenbeck:
`T(t) ∈ [T₁ = 0.8 s, T₂ = 1.6 s]`, costante di tempo τ = 30 s.
Cattura la variabilità intra-driver nel time gap.

### Stima di a_l
`a_l[t] ≈ (v_l[t] − v_l[t−1]) / Δt` filtrato con OU (τ = 1 s) per rimuovere rumore.
**Fallback degradato (UC14/UC15):** se il segnale V2X è parziale o assente, si usa
`a_l = 0` (stima conservativa: il leader mantiene velocità costante). In questo caso
ACC-IDM degenera a IIDM standard — comportamento più conservativo, come richiesto.
```

---

## SEZIONE 4 — Aggiunta: Struttura della PINN loss (inserire nella sezione Algoritmo di Training, prima della Fase 1)

Aggiungere prima di "Fase 1 - Surrogate Gradient":

```
### Loss Function PINN

La rete non è addestrata su una semplice MSE. La loss è composita:

```
Loss = λ_data · SRMSE  +  λ_phys · |v̇ − a_ACC|²  +  λ_OU · vincolo_OU(T)  +  λ_bc · crash_penalty
```

| Termine      | Significato                                                        |
|--------------|--------------------------------------------------------------------|
| λ_data·SRMSE | Fedeltà ai dati (errore normalizzato su traiettorie sintetiche)    |
| λ_phys·res.  | Residuo fisico: l'accelerazione predetta deve rispettare ACC-IDM   |
| λ_OU         | T predetto deve rimanere nel processo OU [T₁, T₂]                 |
| λ_bc         | Penalità di crash: gap < soglia di sicurezza viene fortemente penalizzato |

Il residuo fisico `|v̇ − a_ACC|²` è calcolato stimando `v̇` con differenze finite
sull'output della rete e confrontandolo con l'equazione ACC-IDM.
```

---

## SEZIONE 5 — Aggiunta: Protocollo V2X e dati (nuova sezione)

Aggiungere come sezione separata:

```
## Protocollo V2X e Dati

### Standard di comunicazione
- **ETSI ITS-G5**, frequenza 10 Hz (1 campione ogni 0.1 s)
- **Packet loss**: il sistema attiva il fallback conservativo se packet loss ≥ 2%
- In UC14 (Degraded V2X): comportamento solo su sensori locali, gap target aumentato
- In UC15 (Fragmented V2X): operatività con sottoinsieme degli input; training con input masking

### Segnali di input
| Segnale    | Descrizione                         |
|------------|-------------------------------------|
| s          | Gap spaziale dal veicolo leader     |
| v          | Velocità del veicolo ego            |
| Δv         | Velocità relativa (v_ego − v_leader)|
| v_leader   | Velocità assoluta del veicolo leader|

Tutti e 4 i segnali sono normalizzati prima dell'ingresso alla rete.

### Strategia dati di training
- **Training attuale**: traiettorie sintetiche generate con IDM-2D stocastico
- **Scenari richiesti**: aggiunta di scenari cut-in (necessario per coprire UC2/UC10)
- **Dataset reali disponibili** (non ancora usati nel training):
  - UrbanIng-V2X
  - DAIR-V2X-Seq
  - mixed-signals-devkit
```

---

## SEZIONE 6 — Aggiunta: Deployment FPGA (integrare nella sezione Hardware)

Aggiungere dopo la tabella hardware:

```
### Note sul deployment della rete su PYNQ-Z1

La catena di esecuzione in inferenza è:

```
[s, v, Δv, v_l]  →  SNN forward pass  →  [v₀, T, s₀, a, b]  →  ACC-IDM compute  →  accelerazione
```

| Blocco             | Risorse FPGA                                  |
|--------------------|-----------------------------------------------|
| SNN (Po2 weights)  | Zero DSP (bit-shift), BRAM per buffer delay   |
| ACC-IDM arithmetic | ~5–10 DSP48E1 su 220 disponibili (< 5%)       |
| Bottleneck         | Forward pass SNN — il blocco ACC-IDM è trascurabile |

Frequenza di inferenza: 10 Hz (1 tick per frame V2X).
Implementazione in fixed-point.
```

---

## SEZIONE 7 — Aggiunta: Stato corrente e problemi noti (nuova sezione)

Aggiungere come sezione separata:

```
## Stato Corrente e Problemi Noti

I risultati del primo ciclo di training completo sono in `report_1.md`.

| Metrica            | Valore osservato | Obiettivo       |
|--------------------|------------------|-----------------|
| SRMSE              | 0.871            | < 0.5           |
| Bias v₀            | +16%             | < 5%            |
| Varianza T         | compressa ~4×    | Fedele al range |

**Cause identificate:**
1. LR scheduler che abbassa il learning rate troppo presto (problema critico)
2. IDM plain come base del modello fisico → bias v₀ (risolto passando a IIDM)
3. Mancanza di scenari cut-in nel generatore → rete non esposta a UC2
4. λ_OU probabilmente troppo basso → T non rispetta il processo OU

Il piano di ottimizzazione è in `optimization_ideas.md`.
```

---

## SEZIONE 8 — Aggiornamento riferimenti incrociati

Aggiungere o aggiornare il blocco note finale:

```
## Documenti di riferimento del progetto

| File                          | Contenuto                                                  |
|-------------------------------|------------------------------------------------------------|
| `use_cases.md`                | UC0–UC15: requisiti funzionali e comportamentali           |
| `cf_model_recommendation.md`  | Analisi comparativa dei modelli CF candidati, scelta ACC-IDM |
| `optimization_ideas.md`       | Piano di ottimizzazione del training (Stage A/B, I1–I15)   |
| `report_1.md`                 | Risultati del training, problemi noti, metriche correnti   |
| `FSNN_ Evoluzione delle Reti Neurali Spiking.pdf` | Architettura dettagliata della rete base |
```
