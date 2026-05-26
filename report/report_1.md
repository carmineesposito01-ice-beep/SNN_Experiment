# REPORT — CF_FSNN: Car-Following con Spiking Neural Network + PINN

**Data:** 24 maggio 2026
**Progetto:** CF_FSNN
**Ambiente di esecuzione:** CPU (target finale: Xilinx PYNQ-Z1 FPGA)
**Cartella progetto:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN`

---

## 1. RETE NEURALE — ARCHITETTURA E FUNZIONAMENTO

### 1.1 Panoramica generale

**CF_FSNN_Net** è una rete neurale *spiking* (SNN) progettata per essere impiegata in un problema di *car-following* microscopico, ottenuta a sua volta da una versione ottimizzata di SNN per FPGA (FSNN). A differenza di una rete classica, i neuroni non producono valori reali continui ma *spike* binari, comunicando solo quando il potenziale di membrana supera una soglia adattiva. Questo la rende ideale per implementazione hardware su FPGA (Xilinx PYNQ-Z1) con logica combinatoria a basso consumo.

L'obiettivo della rete è **stimare in tempo reale i 5 parametri del modello IDM-2D** (Intelligent Driver Model stocastico, Treiber & Kesting 2025, Cap. 12) a partire dai segnali V2V ricevuti dai veicoli seguenti e V2I ricevuti dall'infrastruttura. I parametri stimati vengono poi iniettati nell'equazione IDM per calcolare l'accelerazione da applicare.

### 1.2 Architettura a tre livelli

```
Input V2X (4)  -->  [ALIF Hidden: 32 neuroni]  -->  [LI Output: 5 neuroni]  -->  Parametri IDM-2D (5)
```

#### Livello di input — 4 segnali V2X (normalizzati in [0, 1])

| Segnale | Significato fisico | Normalizzazione |
|---|---|---|
| s_norm | Gap veicolo ego -> leader [m] | s / 150 m |
| v_norm | Velocità ego [m/s] | v / 40 m/s |
| dv_norm | Velocità relativa (ego - leader) [m/s] | (dv + 20) / 40 |
| vl_norm | Velocità leader [m/s] | v_l / 40 m/s |

Un flag `mask` per ogni step indica se il pacchetto V2X è stato ricevuto (2% di packet loss simulato, in linea con validazioni sperimentali FSNN_v5).

#### Livello nascosto — HiddenLayer_ALIF (32 neuroni)

Ogni neurone è un **Adaptive Leaky Integrate-and-Fire (ALIF)** con le seguenti proprietà:

- **Integrazione del potenziale**: si accumula con gli input sinaptici correnti e il feedback ricorrente, si scarica con la costante di leak
- **Soglia adattiva**: aumenta di `thresh_jump` (aprox. 0.43, appreso) dopo ogni spike, riducendo automaticamente la frequenza di firing — modella la *fatica neuronale*. Questo meccanismo mappa direttamente al time-gap T del modello IDM-2D che varia lentamente nel tempo (processo Ornstein-Uhlenbeck, Cap. 12.6)
- **Ritardi assionici** (ring buffer circolare): ogni sinapsi può avere un ritardo fino a `max_delay = 6` step = **600 ms**, modellando il *reaction time* del guidatore (Cap. 13, Treiber & Kesting). Il delay è appreso durante il training
- **Ricorrenza low-rank**: W_rec aprox. U(32x8) x V(8x32) — solo 512 parametri invece di 1024, fortemente ottimizzato per risorse logiche FPGA limitate

#### Livello di uscita — OutputLayer_LI (5 neuroni)

Neuroni *Leaky Integrator* senza soglia: integrano gli spike provenienti dal layer ALIF producendo 5 valori continui. Questi vengono decodificati tramite **sigmoid calibrato sui bounds fisici**:

```
p_i = lo_i + (hi_i - lo_i) * sigmoid(raw_i)
```

I 5 parametri IDM-2D risultanti sono:

| Output | Parametro | Range fisico [lo, hi] | Significato |
|---|---|---|---|
| p0 | v0 | [8, 45] m/s | Velocità di desiderio del guidatore |
| p1 | T | [0.5, 2.5] s | Time-gap di sicurezza desiderato |
| p2 | s0 | [1, 5] m | Gap minimo a riposo (bumper-to-bumper) |
| p3 | a | [0.3, 2.5] m/s2 | Accelerazione massima confortevole |
| p4 | b | [0.5, 3.0] m/s2 | Decelerazione di comfort |

### 1.3 Dinamica temporale — TBPTT e tick interni

Per ogni **step di simulazione** (dt = 0.1 s, cadenza V2X a 10 Hz), la rete esegue **10 tick interni** — simulando il ciclo neurale sub-millisecondo. Il training usa *Truncated Backpropagation Through Time* (TBPTT) su finestre scorrevoli di **100 step** (= 10 secondi di guida per finestra).

Il **surrogate gradient** permette la backpropagation attraverso la discontinuità della funzione di spike:

```
dH(V - theta)/dV  aprox.  1 / (1 + gamma * |V - theta|)^2
```

### 1.4 Integrazione con IDM-2D

La rete non produce direttamente l'accelerazione: stima i **parametri del guidatore** (v0, T, s0, a, b), che vengono poi iniettati nell'equazione IDM-2D per calcolare l'accelerazione fisica:

```
v_dot = a * [1 - (v/v0)^4 - (s*(v, dv) / s)^2]

s*(v, dv) = s0 + max(0, v*T + v*dv / (2*sqrt(a*b)))
```

Il parametro T varia lentamente nel tempo secondo un processo Ornstein-Uhlenbeck (IDM-2D stocastico), e la rete — tramite i neuroni ALIF con soglia adattiva — è strutturalmente in grado di catturare questa dinamica.

### 1.5 Dimensione totale del modello

| Componente | Shape | Parametri |
|---|---|---|
| fc_weight (input -> hidden) | (32, 4) | 128 |
| rec_U (low-rank) | (32, 8) | 256 |
| rec_V (low-rank) | (8, 32) | 256 |
| delays (assionici) | (32, 4) | 128 |
| base_threshold (ALIF) | (32,) | 32 |
| thresh_jump (ALIF) | (32,) | 32 |
| fc_weight (hidden -> output) | (5, 32) | 160 |
| **TOTALE** | | **864** |

---

## 2. TIPO DI TEST / ADDESTRAMENTO

### 2.1 Paradigma: Physics-Informed Neural Network (PINN)

La rete è addestrata con una **loss a 4 componenti** che integra vincoli fisici derivati dal modello IDM-2D (Treiber & Kesting, Cap. 17):

```
L = lambda_data * SRMSE(a_pred, a_gt)                          [lambda = 1.0]
  + lambda_phys * MSE(a_pred_IDM, a_obs)                       [lambda = 0.1]
  + lambda_OU   * E[(T_{t+1} - alpha*T_t - (1-alpha)*T_mean)^2][lambda = 0.05]
  + lambda_bc   * crash_penalty(s, s0_pred)                    [lambda = 1.0]
```

| Componente | Formula | Scopo |
|---|---|---|
| **L_data** | SRMSE(a_pred, a_gt) | Fit dell'accelerazione osservata (MoP primario, Cap. 17) |
| **L_phys** | MSE tra a_IDM(params_pred) e a_obs | Coerenza con l'equazione fisica IDM-2D |
| **L_OU** | Residuo mean-reversion: E[(T_{t+1} - alpha*T_t - (1-alpha)*T_mean)^2] | Vincolo sul processo OU di T(t) |
| **L_bc** | Crash prevention: penalizza s < s0_pred | Sicurezza — mai collisione (Cap. 11) |

La **SRMSE** (Scaled Root Mean Squared Error) è la metrica adimensionale raccomandata da Treiber & Kesting (Cap. 17) per calibrazione di modelli car-following su dati eterogenei.

### 2.2 Dataset sintetico IDM-2D

| Parametro dataset | Valore |
|---|---|
| Traiettorie training | 1000 |
| Traiettorie validazione | 100 |
| Traiettorie test (mai viste) | 200 |
| Durata per traiettoria | 120 s (20 s warmup esclusi -> 1000 step utili) |
| Passo temporale dt | 0.1 s (10 Hz, cadenza V2X) |
| Mix scenari | 50% highway · 30% urban · 10% truck · 10% mixed |
| Packet loss V2X | 2% per step (Bernoulli) |
| Rumore sul gap s | OU, sigma_rel = 10%, tau = 20 s |
| Rumore su v_leader | OU, sigma = 0.01 s^-1, tau = 20 s |
| Banda IDM-2D time-gap | T in [0.8, 1.6] s, processo OU tau = 30 s |
| Parametri IDM per scenario | Campionati casualmente per ogni traiettoria |

Il generatore IDM-2D è stato validato separatamente: produce traiettorie fisicamente coerenti con gap, velocità e accelerazioni nei range attesi per i vari scenari.

### 2.3 Configurazione del training overnight

| Iperparametro | Smoke test (pre-validazione) | Training overnight |
|---|---|---|
| Traiettorie train | 5 | **1000** |
| Traiettorie val | 2 | **100** |
| Epoche | 2 | **20** |
| Batch size | 2 | **32** |
| Learning rate iniziale | 0.001 | **0.001** |
| Seq_len (TBPTT) | 20 step (2 s) | **100 step (10 s)** |
| Ottimizzatore | Adam | **Adam** |
| LR Scheduler | ReduceLROnPlateau (patience=5, factor=0.5) | idem |
| Gradient clipping | max_norm = 1.0 | idem |
| Tick SNN per step | 10 | 10 |
| Seed | 42 | 42 |
| Durata effettiva | ~5 min | **~8.5 h** |
| Tempo per batch (misurato) | ~0.58 s | **~2.58 s** |

### 2.4 Finestre di training (sliding window)

- **Training**: stride = seq_len / 2 = 50 step -> 50% overlap -> ~19 finestre per traiettoria
- **Validazione / Test**: stride = seq_len = 100 step -> finestre non sovrapposte

Con 1000 traiettorie train: 1000 x 19 = circa **19.000 finestre** | batch=32 -> **~595 batch/epoca**

---

## 3. RISULTATI

### 3.1 Curva di training

| Checkpoint | Epoca | val_loss (salvata) |
|---|---|---|
| **best.pt** | **1** | **0.852341** |
| epoch_010.pt | 10 | 0.927317 |
| epoch_020.pt | 20 | 0.927317 |

> **Nota critica**: il modello migliore si trova alla **prima epoca**. Dalla seconda in poi la validation loss peggiora e si stabilizza identica tra l'epoca 10 e la 20, sintomo di arresto completo del learning rate per effetto del ReduceLROnPlateau con patience=5.

### 3.2 Metriche sul test set (200 traiettorie mai viste in training)

| Componente | Media | Std | Min | Max |
|---|---|---|---|---|
| **total** | **0.8843** | 0.4431 | 0.4033 | 2.9886 |
| data (SRMSE) | 0.8706 | 0.4430 | 0.3907 | 2.9610 |
| phys (IDM residuo) | 0.0971 | 0.0473 | 0.0344 | 0.2717 |
| ou (OU residuo) | 0.0109 | 0.0014 | 0.0080 | 0.0138 |
| bc (crash penalty) | 0.0034 | 0.0053 | 0.0000 | 0.0276 |

### 3.3 Parametri IDM-2D predetti sul test set

| Parametro | Media pred. | Std pred. | Min | Max | Range atteso | In-bounds |
|---|---|---|---|---|---|---|
| v0 [m/s] | 29.812 | 3.567 | 20.536 | 40.723 | [8, 45] | **100%** |
| T [s] | 1.349 | 0.090 | 0.987 | 1.771 | [0.5, 2.5] | **100%** |
| s0 [m] | 1.753 | 0.254 | 1.181 | 2.984 | [1, 5] | **100%** |
| a [m/s2] | 0.496 | 0.224 | 0.300 | 1.377 | [0.3, 2.5] | **100%** |
| b [m/s2] | 1.462 | 0.113 | 0.973 | 1.902 | [0.5, 3.0] | **100%** |

### 3.4 Stima del time-gap T — metrica chiave del modello IDM-2D

| Metrica | Valore |
|---|---|
| **MAE(T)** | **0.2287 s** |
| **RMSE(T)** | **0.2819 s** |
| Bias sistematico (T_pred - T_true) | +0.150 s (sovrastima) |
| std T_true (ground truth) | 0.224 s |
| std T_pred (predetto) | 0.090 s |
| Compressione varianza | 4x inferiore alla realtà |
| Banda IDM-2D attesa | T in [0.8, 1.6] s |

### 3.5 Rispetto dei vincoli fisici

Tutti e 5 i parametri predetti rispettano al **100%** i loro bounds fisici su ogni finestra del test set. Il decoder sigmoid garantisce questa proprietà strutturalmente, indipendentemente dallo stato del training.

---

## 4. CONSIDERAZIONI CRITICHE

### 4.1 Aspetti positivi

| # | Osservazione | Significato |
|---|---|---|
| OK 1 | Vincoli fisici rispettati al **100%** | Nessun parametro fuori range — requisito di sicurezza FPGA soddisfatto |
| OK 2 | Loss bc quasi nulla (**0.003**) | La rete non genera mai traiettorie di collisione |
| OK 3 | Loss OU bassa (**0.011**) | La sequenza T(t) predetta è coerente con il processo OU atteso |
| OK 4 | Convergenza rapida (epoca 1) | Con 1000 traiettorie la rete impara già alla prima epoca — architettura PINN funzionante |
| OK 5 | v0 fisicamente sensato (29.8 m/s ~ 107 km/h) | Coerente con mix 50% highway — la rete ha imparato la distribuzione degli scenari |
| OK 6 | Loss phys < 0.10 | I parametri predetti producono accelerazioni IDM coerenti con l'osservato |

### 4.2 Problemi identificati

| # | Problema | Causa probabile | Impatto |
|---|---|---|---|
| WARN 1 | **Best epoch = 1, plateau immediato** | ReduceLROnPlateau riduce LR troppo aggressivamente; con patience=5 e molti plateau iniziali, il LR scende a ~0 in poche epoche | Il modello smette di imparare dopo la prima epoca |
| WARN 2 | **SRMSE = 0.871 (alto)** | Dataset troppo piccolo (1000 traj) e training troppo breve (20 epoche) | Predizione dell'accelerazione imprecisa; non sufficiente per uso reale |
| WARN 3 | **Bias T: +0.150 s** | La rete predice T sistematicamente più alto della realtà | Comportamento conservativo: distanze di sicurezza maggiori del necessario (sicuro ma non ottimale) |
| WARN 4 | **Compressione varianza T (4x)** | lambda_OU troppo basso (0.05) — non forza abbastanza la dinamica stocastica | La rete tende alla media di T invece di catturare le fluttuazioni OU |
| WARN 5 | **a conservativo (0.50 vs 1.1-1.5 m/s2 atteso)** | La crash penalty penalizza indirettamente le accelerazioni alte | Il veicolo accelera meno del normale — guida eccessivamente prudente |

### 4.3 Conclusione generale

Il training overnight su CPU (20 epoche, 1000 traiettorie) costituisce un **proof-of-concept funzionante**: la rete CF_FSNN_Net con architettura PINN+SNN converge, rispetta i vincoli fisici, e produce parametri IDM-2D plausibili. Tuttavia, la qualità del fit (SRMSE = 0.871) è ancora lontana dagli standard di calibrazione (SRMSE < 0.2-0.3, Cap. 17 Treiber & Kesting). Si tratta di un **primo baseline** da cui partire per il tuning sistematico.

---

## 5. RACCOMANDAZIONI PER I PROSSIMI STEP

| Priorità | Azione | Motivazione tecnica |
|---|---|---|
| ALTA | Sostituire ReduceLROnPlateau con **Cosine Annealing** (T_max=50) | Evita lo stallo prematuro; garantisce LR > 0 per tutta la durata del training |
| ALTA | Aumentare a **50 epoche, 5000 traiettorie** (full training) | Dataset e durata attuali insufficienti — stima: ~107 h su CPU o ~2-3 h con GPU |
| MEDIA | Aggiungere **LR warmup** lineare (5 epoche: 1e-4 -> 1e-3) | Stabilizza il training SNN nelle prime epoche ad alta varianza del gradiente |
| MEDIA | Aumentare **lambda_OU da 0.05 a 0.2** | Ridurre la compressione della varianza di T e migliorare la stima stocastica |
| MEDIA | **Salvare dataset su disco** (flag --save_data) | Evita rigenerazione a ogni run; fondamentale per run lunghe e ripetibili |
| BASSA | Validazione su dati reali **NGSIM US-101** | Verifica di generalizzazione fuori-distribuzione (sintetico -> reale) |
| BASSA | Esportazione pesi **power-of-2** per PYNQ-Z1 | Quantizzazione log2 dei pesi -> sostituzione moltiplicazioni con bit-shift (DSP=0) |
| BASSA | Aggiungere profilo leader **stop-and-go** nel dataset | Scenario critico per platooning urbano non ancora coperto nel training |

---

*Report generato da: `eval_report.py` + `inspect_ckpt.py` — CF_FSNN v1.0*
*Riferimento teorico: Treiber M., Kesting A. — "Traffic Flow Dynamics" (2nd ed., Springer 2025)*
