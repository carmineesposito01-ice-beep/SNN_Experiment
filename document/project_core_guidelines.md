# OBIETTIVO: Car-Following con segnali V2X
Realizzare un modello di car-following che utilizzi solo segnali V2X (nessun sensore interno) per controllare un veicolo a guida autonoma. L'obiettivo principale è realizzare un sistema (applicazione DSP) che presi i dati V2X generi un set di parametri, specifici di un modello di car-folowing selezionato.

> **Nota**: Gli Use-Case del progetto specifico sono contenuti nel file `use_cases.md`.

## Hardware
**FPGA - Xilinx PYNQ-Z1**: FPGA Xilinx con le seguenti caratteristiche:
- **Clock Frequency**: 100 MHz
- **Logic Elements**: 28800
- **DSP Block**: 220
- **BRAM**: 4.9 MB
- **IO Pins**: 100
- **Max Power**: 10 W
- **Voltage Core**: 1.0 V
- **Temperature Range**: [-40 °C : 85 °C]
- **Max Throughput**: 6 Gb/s
- **Latency**: 10 ns
- **Reconfiguration Time**: 0.5 s
- **Secure Boot**: true
- **Bitstream Encryption**: true
- **Tamper Detection**: true
- **MTBF**: 300000 h

# ARCHITETTURA SELEZIONATA
Utilizo di una rete neurale addestrata tramite paradigma PINN (Physics-Injected Neural Network) per generare i parametri del modello di car-following selezionato.
**Doppio Modulo**: Separazione del modulo di controllo longitudinale da quello laterale
1 - Modulo Logitudinale - ACC-IDM (con base IIDM)
2 - Modulo Laterale - ***Da selezionare*** (probabilmente un MOBIL con controllore PID o MPC)

## Modello di Car-Following — ACC-IDM con base IIDM

### Razionale della scelta
Il modello IDM puro fallisce su UC2 (Abrupt Cut-In): reagisce con decelerazione istantanea al taglio del gap → panic braking. L'ACC-IDM aggiunge la CAH (Constant Acceleration Heuristic) che rende la risposta anticipatoria e graduata. 
La base IIDM (invece di IDM plain) risolve la dispersione di v₀: in IDM i veicoli non raggiungono mai esattamente la velocità target; IIDM separa i regimi free-flow e car-following in modo più preciso.

> NOTA: Il documento di analisi completa è in `cf_model_recommendation.md`.

### Formula ACC-IDM

**a_IIDM** = base IIDM (regime free-flow separato dal regime following)
**a_CAH**  = v² · ā_l / (v · ā_l / s + (v − v_l)² / (2s))   con ā_l = min(a_l, a)

Se a_IIDM ≥ a_CAH:
    a_ACC = a_IIDM
Altrimenti:
    a_ACC = (1 − c) · a_IIDM + c · [a_CAH + b · tanh((a_IIDM − a_CAH) / b)]
    con c = 0.99  (fisso — non predetto dalla rete)

### Parametri predetti dalla rete

| Parametro | Significato                  |
|-----------|------------------------------|
| v₀        | Velocità desiderata          |
| T         | Time gap target              |
| s₀        | Gap minimo a riposo          |
| a         | Accelerazione massima        |
| b         | Decelerazione confortevole   |


## Rete neurale
**Spiking Neural Network**: Rete neurale che simula il funzionamento neuromorfico, lavorando tramite spikes binari, lanciati dai neuroni nel momento in cui il loro potenziale di membrana supera una certa soglia (concetto del Leaking-Integrate Neuron) 

### Full-Spiking Neural Network (FSNN)
Architettura specifica selezionata, ottimizzata per l'utilizzo su FPGA.

**Architettura**: 4 → 32 → 5

| Layer   | Tipo            | Dettagli                                                     |
|---------|-----------------|--------------------------------------------------------------|
| Input   | —               | 4 segnali V2X: [s, v, Δv, v_leader]                         |
| Hidden  | ALIF            | 32 neuroni, rank=8, max_delay=6 tick, soglia adattiva        |
| Output  | LI (Leaky Int.) | 5 neuroni, no spike — potenziale usato direttamente come output |

*Leggenda*:
| Simbolo | Significato | Unità |
|---|---|---|
| s | Gap spaziale tra veicolo ego e leader (bumper-to-bumper) | m |
| v | Velocità del veicolo ego | m/s |
| Δv | Velocità relativa = v_ego − v_leader (positivo = ego più veloce) | m/s |
| v_leader | Velocità assoluta del veicolo leader | m/s |

**Quantizzazione Po2:**
I pesi sono quantizzati in `{2⁻⁴, 2⁻³, 2⁻², 2⁻¹, 2⁰, 2¹}`.
Ogni moltiplicazione diventa un bit-shift → **zero DSP sul PYNQ-Z1**.
Questo è il motivo per cui la rete è compatibile con FPGA a basso consumo.

**Output della rete (parametri predetti):** `[v₀, T, s₀, a, b]`
Questi sono i parametri del modello di car-following (ACC-IDM con base IIDM).

*Legenda*:
| Simbolo | Significato | Unità |
|---|---|---|
| v₀ | Velocità desiderata in free flow | m/s |
| T | Time gap target (distanza temporale desiderata dal leader) | s |
| s₀ | Gap minimo a riposo (distanza di sicurezza a v=0) | m |
| a | Accelerazione massima confortevole | m/s² |
| b | Decelerazione confortevole (valore positivo) | m/s² |


> NOTA: Maggiori informazioni sulla specifica rete neurale nel file `FSNN_ Evoluzione delle Reti Neurali Spiking.pdf`

## Algoritmo di Training
**Loss Function PINN**
Loss composita:
***Loss*** = λ_data · SRMSE  +  λ_phys · |v̇ − a_ACC|²  +  λ_OU · vincolo_OU(T)  +  λ_bc · crash_penalty


| Termine      | Significato                                                        |
|--------------|--------------------------------------------------------------------|
| λ_data·SRMSE | Fedeltà ai dati (errore normalizzato su traiettorie sintetiche)    |
| λ_phys·res.  | Residuo fisico: l'accelerazione predetta deve rispettare ACC-IDM   |
| λ_OU         | T predetto deve rimanere nel processo OU [T₁, T₂]                 |
| λ_bc         | Penalità di crash: gap < soglia di sicurezza viene fortemente penalizzato |

Il residuo fisico `|v̇ − a_ACC|²` è calcolato stimando `v̇` con differenze finite sull'output della rete e confrontandolo con l'equazione ACC-IDM.

### Fase 1 - Surrogate Gradient + BPTT (Back-Propagation Through Time)
Per loro funzionamento intrinseco (utilizzo di spikes, non differenziabili) le SNN non possono far uso dei classici algoritmi di back-propagation. Si fa uso di una **funzione surrogata** che emula una funzione derivabile, tuttavia il gradiente calcolato non sarà il vero gradiente della loss (è un'approssimazione)
**Problematiche**
1 - ***Dead Neurons***: se un neurone non spara mai, il suo surrogate gradient è prossimo allo 0 -> non riceve aggiornamenti -> rimane 'silente'.
2 - ***Mismatch di Approssimazione***: essendo la soluzione un'approssimazione, la loss è ottimizzata per qualcosa che non è 'la verità'


**Alternativa**
Fondamento teorico dell'**EventProp** (Nowotny et al). Si calcolano i gradienti degli spikes tramite il metodo dell'*aggiunto continuo*.
- Limite: attualmente è dimostrato solo per topologie SNN semplici (LIF, non ALIF)
- Estensione: possibilità, in linea terorica, di estenderlo ad ALIF. Tuttavia, l'applicazione ALIF+PINN è totalmente inesplorata.

### Fase 2 - Algoritmo di Addestramento per la specifica SNN (FSNN)
Esistono 3 direzioni possibili:
**Direzione A (Breve termine)**: Ottimizzazione del Surrogate Gradient
Applicare ottimizzazioni al paradigma attuale per renderlo più stabile:
1 - Homeostatic Regulation: aggiunta di un termine di loss che penalizza il firing rate fuori dal range target imposto dal PINN (es. del 10% o 30%)
	***Effetto***
	Previene dead neurons e neuroni saturi

2 - Scheduled gradient: partire con un gradiente alto e andare a ridurlo durante il training
	***Effetto***
	Addestramento più fedele alla funzione reale
	
3 - Two-Phase Training: Fase 1 focalizzata sulla loss dati; Fase 2 sull'introduzione della fisica

> NOTA: Ulteriori informazioni sulle ottimizzazioni nel file `optimization_ideas.md`

**Direzione B (medio termine/ricerca)**: Sfruttamento della fisica del Training
Lo stesso paradigma PINN può fornire informazioni per strutturare una soluzione al training (es. l'output viola la fisica in questo modo). Questo potrebbe essere usato per guidare il training a imporre gradienti più forti a neuroni che contribuiscono alla violazione.
- *Problema*: non esiste alcun metodo formalizzato per far ciò (completamente sperimentale)

**Direzione C (lungo termine)**: EventProp per ALIF+PINN
Derivare il *metodo aggiunto* corretto per ALIF e integrarlo con la PINN loss. Necessità:
1 - Estensione del formalismo EventProp ad una soglia adattiva
2 - Necessità di implementarlo in modo efficiente (altrimenti si rompono i vantaggi dell'SNN)
3 - Validazione comparativa con la tecnica del Surrogate Gradient

### Fase Extra - STDP (Spike-Timing Dependent Plasticity)
Tecnica di addestramento non-supervisionato, basata sull'osservazione locale dei neuroni vicini e la differenza di fire tra essi. Si basa sul principio neuromorfico secondo il quale le sinapsi del cervello si rafforzano se vengono usate molto e indeboliscono per l'opposto, andando di conseguenza a emulare memoria e adattamento.
**Problematiche**
- Tecnica sperimentale e con risultati ancora lontani dalla surrogate Gradient
- Difficoltà di interfacciamento con paradigma PINN








## Piattaforma di addestramento disponibili
1) CPU
2) GPU - RTX3060, 12 Gb GDDR7
3) Piattaforma Microsoft Azure (tramite pacchetto Git Educational)








> NOTA
File non modificabile, eccetto che per espressa richiesta dell'utente.