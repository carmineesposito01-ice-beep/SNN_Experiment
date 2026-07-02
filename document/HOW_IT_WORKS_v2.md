# CF_FSNN — Come Funziona (versione divulgativa)

> ⚠️ **SUPERATO da `HOW_IT_WORKS_v3.md` / `.pdf` (2026-07-01)**, che è tecnico ma ad apice di
> comprensibilità e aggiornato allo stato attuale (EventProp, ρ spettrale, PINN, po2, i 4 champion).
> Questa v2 divulgativa resta come lettura leggera introduttiva ma contiene dati datati (val≈0.28,
> sweep di dimensione pre-EventProp).

> **Versione**: 2026-05-29 (v2 — linguaggio semplificato)
> **Lettore atteso**: chiunque voglia capire il progetto senza essere un esperto di SNN o di traffic flow.
> **Scope**: spiegare cosa fa la rete, come è costruita e perché, con analogie e esempi.
> Per i dettagli più tecnici (formule, codice, riferimenti) vedi `HOW_IT_WORKS.md` / `.pdf` (versione v1).

---

## 1. Cosa fa CF_FSNN, in parole semplici

Immagina un'auto a guida assistita (ACC, Adaptive Cruise Control) che segue il veicolo davanti
a sé. Il **come** quest'auto reagisce — quanto spazio lascia, quanto frena bruscamente, quanto
accelera quando il leader accelera — dipende da **5 numeri** che caratterizzano il "carattere"
del guidatore (o del software ACC):

| Numero | Significato intuitivo |
|---|---|
| **v₀** | "A quale velocità mi piace andare se la strada è libera" |
| **T** | "Quanto tempo (in secondi) voglio tenere come distanza di sicurezza" |
| **s₀** | "Anche da fermo, quanto spazio voglio lasciare davanti (in metri)" |
| **a** | "Quanto sono brioso quando accelero" |
| **b** | "Quanto sono morbido quando freno (frenare comodo, non d'emergenza)" |

**CF_FSNN guarda l'auto guidare per qualche secondo e indovina questi 5 numeri.**

Più precisamente: la rete riceve in tempo reale 4 informazioni dal sistema V2X (l'auto che
parla con le auto vicine) — distanza dal leader, velocità propria, differenza di velocità col
leader, velocità del leader — e in uscita stima i 5 parametri del modello fisico ACC-IIDM
(quello del libro di Treiber & Kesting, lo standard nel settore).

### Perché serve?

Conoscere questi 5 numeri serve a:
- **Capire il tipo di guida** delle auto attorno → fluidità del traffico in autostrada
- **Predire le reazioni** di chi ti precede → maggiore sicurezza
- **Sintonizzare** un controller ACC su uno specifico veicolo o utente
- **Studiare la stabilità** del convoglio (string stability)

---

## 2. Glossario rapido (termini che useremo)

| Termine | Significato in parole semplici |
|---|---|
| **SNN** (Spiking Neural Network) | Una rete neurale che, invece di emettere numeri reali, emette **impulsi** (come i neuroni veri del cervello). Più efficiente da implementare su hardware dedicato. |
| **ALIF neuron** | Il tipo di neurone artificiale che usiamo. Si "stanca" se spara troppi impulsi di fila (come i neuroni biologici), e questo aiuta la stabilità della rete. |
| **Surrogate gradient** | Un trucco matematico per insegnare alla rete ad imparare anche se la funzione degli impulsi è "spigolosa" (matematicamente non derivabile). |
| **BPTT** | Modo standard per allenare reti che hanno memoria nel tempo. Propaga la correzione all'indietro attraverso tutta la sequenza temporale. |
| **Recurrence (low-rank)** | La rete riusa il proprio output del passo precedente. "Low-rank" = lo fa in modo compatto, risparmiando memoria. |
| **Po2 quantization** | I pesi della rete possono assumere solo valori speciali (1, 2, 4, 1/2, 1/4, ...). Su un chip FPGA, moltiplicare per questi valori = uno **shift di bit**, gratis. |
| **FPGA** | Un chip programmabile, più piccolo ed economico di una GPU. Il nostro target hardware è il **PYNQ-Z1** (~300 USD). |
| **V2X** | "Vehicle-to-everything": la comunicazione wireless tra l'auto e tutto il resto (altre auto, infrastruttura). |
| **PINN loss** | Una funzione di costo che obbliga la rete a essere **sia accurata sui dati** che **coerente con la fisica**. |
| **ACC-IIDM** | Il modello matematico standard di Adaptive Cruise Control (Treiber & Kesting 2025). Definisce come dovrebbe comportarsi un guidatore razionale. |
| **packet loss V2X** | Ogni tanto il messaggio wireless si perde (~2% delle volte). La rete deve essere robusta a questi buchi. |

---

## 3. Come è fatta la rete

### 3.1 In una frase

> *"Una piccola rete di 32 neuroni-impulso che ricevono 4 numeri dall'auto, ci pensano per 10 cicli interni, e producono in uscita 5 numeri (i parametri del guidatore)."*

### 3.2 Architettura a strati

```
   4 input            32 neuroni                5 uscite
[s, v, Δv, vₗ]   →   spiking ALIF        →     numeri grezzi    →   [v₀, T, s₀, a, b]
   da V2X            (con memoria              prima della           parametri fisici
                     a breve termine)          conversione
```

Ogni "passo" di tempo dell'auto (= 0.1 secondi nella realtà) viene elaborato facendo girare
la rete per **10 cicli interni**. Questo dà alla rete tempo di "ragionare" pur restando in
tempo reale.

### 3.3 Quanto è grande?

**864 parametri totali**. Per fare un confronto:
- Un MLP "tipico" per task simili: 10.000 – 100.000 parametri
- La nostra rete è ~ 100× più piccola
- Sta interamente nella memoria interna del chip FPGA (BRAM), senza accessi a RAM esterna
- Risultato: latenza di inferenza in microsecondi

---

## 4. I tre concetti chiave (con analogie)

### 4.1 Neurone "che si stanca" (ALIF)

I neuroni veri del cervello hanno un meccanismo di stanchezza: quando sparano molti impulsi
di fila, diventano temporaneamente meno reattivi. È un meccanismo di sicurezza che evita
attività epilettiche.

Il nostro **neurone ALIF** ha lo stesso comportamento: tiene memoria di quanto ha sparato di
recente, e alza temporaneamente la soglia di attivazione. Questo migliora la stabilità del
training.

> **Per chi vuole approfondire**: tecnicamente è un "Adaptive Leaky Integrate-and-Fire" con
> soglia adattativa F che decade nel tempo. Vedi v1 §3.1.

### 4.2 Surrogate gradient (il trucco per imparare)

Il problema: gli impulsi sono **0 oppure 1**, non c'è una "via di mezzo". Matematicamente,
la derivata di una funzione "0 oppure 1" è zero quasi ovunque → la rete non potrebbe mai
imparare con i metodi classici.

**Soluzione**: durante l'apprendimento (e *solo* in quella fase), fingiamo che la funzione
sia liscia. Sostituiamo la derivata "vera" (che non esiste) con una **curva smussata** centrata
sulla soglia. È un trucco di calcolo, ma funziona bene in pratica.

L'inferenza poi resta con impulsi 0/1 puri — il trucco serve solo per insegnare.

### 4.3 Pesi che sono potenze di 2 (per il chip)

Un chip FPGA è molto bravo a fare **shift di bit** (es. `× 2`, `× 4`, `× 0.5`) ma poco bravo
a fare moltiplicazioni generiche (è lento, occupa tanta area, consuma tanta energia).

**Allora**: limitiamo i pesi della rete a essere solo potenze di 2: ±1, ±2, ±4, ±0.5, ±0.25,
... oppure zero. Risultato: ogni moltiplicazione `peso × input` diventa **uno shift di bit**.

| Su FPGA, una moltiplicazione costa... | Con pesi potenze di 2... |
|---|---|
| ~100 LUT (logic units) | ~10 LUT (10× meno area) |
| ~1 nJ di energia | ~0.05 nJ (20× meno energia) |
| 4 cicli di clock | 1 ciclo |

Il trade-off: la rete è un po' meno precisa (~3–8% in più di errore) ma sta su un chip
che costa qualche centinaio di dollari invece di migliaia. Per noi è un buon affare.

---

## 5. Come la rete impara: la "loss" PINN

Quando si allena una rete, le diciamo *quanto* ha sbagliato tramite un **numero unico** (la
"loss"). Più è basso, meglio è. Il modo in cui calcoliamo questo numero determina cosa la
rete impara.

La nostra loss combina **5 ingredienti**:

| Ingrediente | A cosa serve (intuitivamente) | Peso (importanza) |
|---|---|---|
| **L_data** | "I parametri che predici, riproducono correttamente l'accelerazione osservata?" | 1.0 (massima) |
| **L_phys** | "Anche quando perdo qualche dato V2X, la fisica deve continuare a tornare." | 0.1 |
| **L_OU** | "Il parametro T che predici deve variare nel tempo in modo realistico (non a sbalzi assurdi)." | 0.05 |
| **L_bc** | "Mai e poi mai predire una distanza minima di sicurezza maggiore della distanza reale (= crash)." | 1.0 |
| **L_sr** | "I neuroni devono sparare nella misura giusta: né morti, né saturi. Target 15% di attività." | 0.5 |

I primi due sono "imparare dai dati"; gli ultimi tre sono **vincoli di buon senso fisico** che
imponiamo. Il nome "PINN" sta per *Physics-Informed Neural Network* proprio per questo: la
rete non impara solo dai dati, ma anche dalle leggi della fisica.

> **Perché L_sr è importante?** Senza questo vincolo, la rete a volte "spegne" tutti i
> neuroni (li rende silenziosi). Sembra una buona soluzione perché abbassa la loss... ma in
> realtà rompe completamente il training poco dopo, perché senza impulsi non c'è gradient
> flow. L_sr la tiene "sveglia" alla giusta intensità.

---

## 6. Il modello fisico ACC-IIDM (in versione discorsiva)

Tutto il progetto ruota attorno al modello ACC-IIDM di Treiber & Kesting. È un modello che
descrive come un guidatore razionale dovrebbe comportarsi in *car-following* (seguendo un
veicolo davanti). Funziona così:

### 6.1 Distanza desiderata

> **Domanda**: dato che vado a velocità v, qual è la distanza minima che voglio dal leader?

Il modello risponde:

$$\text{distanza\_voluta} = s_0 + v \cdot T + (\text{correzione per } \Delta v)$$

cioè: una distanza fissa minima (s₀) + una distanza proporzionale alla velocità (= "tempo di
reazione" T moltiplicato per velocità) + una correzione se il leader sta rallentando.

### 6.2 Accelerazione

> **Domanda**: dato che voglio andare a v₀ ma sto a v, e che la distanza voluta è s* ma sto
> a distanza s reale, quale accelerazione applico?

Il modello combina due "spinte":
- una **spinta avanti** se v < v₀ (voglio andare più veloce)
- una **spinta indietro** se s < s* (sono troppo vicino al leader)

I parametri **a** e **b** decidono quanto bruscamente: a per accelerare, b per frenare.

### 6.3 Il blend "ACC con CAH"

C'è un dettaglio fine: il modello IIDM standard sarebbe troppo prudente in caso di "cut-in"
(un'auto che si infila davanti). Per evitare frenate inutilmente brusche, si **blenda** con
un altro modello (CAH, Constant Acceleration Heuristic) che assume che il leader continui
con la sua attuale accelerazione. Il blend è governato da un parametro chiamato **coolness**
(c=0.99): 99% si fida del CAH, 1% si tiene la sicurezza IIDM.

Questo è esattamente ciò che fanno gli ACC commerciali (vedi Treiber Ch.12 §12.4).

---

## 7. Da dove vengono i dati per allenarla?

Non abbiamo dati reali di auto vere (sarebbe complicato/costoso). Generiamo **dati sintetici**
realistici secondo il modello stesso. Per ogni "traiettoria sintetica" (di 100 secondi):

1. Scegliamo uno **scenario** casualmente:
   - **highway** (50% — autostrada, 120 km/h)
   - **urban** (30% — città, 54 km/h)
   - **truck** (10% — camion, 80 km/h, frenata morbida)
   - **mixed** (10% — mix dei tre)
2. **Simuliamo l'auto** con il modello ACC-IIDM passo per passo, ogni 0.1 secondi
3. Aggiungiamo **rumore realistico**: il 2% delle volte il messaggio V2X si perde
4. Ogni tanto (20% delle traiettorie) introduciamo un **cut-in**: un'auto che si infila
   davanti, gap che si riduce bruscamente

La rete viene allenata su 500–5000 di queste traiettorie. Ogni traiettoria contiene 1000
"fotogrammi" (passi temporali da 0.1s).

---

## 8. Esempio numerico: un singolo fotogramma

Per fissare le idee, vediamo cosa succede in un singolo passo temporale.

### Situazione

Un'auto sta seguendo un leader in autostrada:

| Cosa osservo | Valore |
|---|---|
| Distanza dal leader (gap) | 30 metri |
| Velocità mia | 25 m/s (~90 km/h) |
| Velocità leader | 28 m/s (~100 km/h) |
| Differenza Δv | −3 m/s (il leader va più veloce di me) |

### Ground truth (cosa farebbe un guidatore "perfetto")

Il driver in autostrada ha parametri (v₀=33.3 m/s, T=1.2 s, s₀=2.5 m, a=1.1 m/s², b=1.5 m/s²).
Applicando le formule ACC-IIDM, otteniamo:

> Accelerazione corretta = **+0.74 m/s²** (sta accelerando per recuperare il leader).

### Cosa fa la rete

Se la rete predice i 5 parametri sbagliati — per esempio mette T più alto e a più basso —
ricalcolando l'accelerazione con quei parametri otterremmo magari un'accelerazione di
**−3.5 m/s²** (cioè una frenata) invece di **+0.7 m/s²**.

L'errore è di circa 4.2 m/s². Questo errore viene incorporato in **L_data**, che propaga
la correzione attraverso la rete e aggiusta i pesi.

Ripetendo su milioni di passi temporali, la rete impara a riprodurre il comportamento
corretto.

---

## 9. Quando possiamo dire che "funziona bene"?

Ci sono due tipi di criteri.

### 9.1 Quantitativi (numeri da osservare)

| Cosa guardare | Valore di "funziona bene" | Valore "eccellente" |
|---|---|---|
| **val_loss totale** | sotto 0.20 | sotto 0.15 |
| Errore tipico su **v₀** | meno di 5.5 m/s (~15% del range) | meno di 2.2 m/s (~6%) |
| Errore tipico su **T** | meno di 0.30 s | meno di 0.10 s |
| Errore tipico su **s₀** | meno di 60 cm | meno di 20 cm |
| **Spike rate dei neuroni** | tra 5% e 30% | tra 10% e 20% |
| **Stabilità del training** | nessuna esplosione del gradiente per 5+ epoche | nessuna esplosione mai |

### 9.2 Pratici (cosa controllare visivamente nei grafici)

- **G5 (scatter T predetto vs vero)**: i punti devono stare vicini alla diagonale
- **G7 (violino dei 5 parametri)**: tutte le distribuzioni devono essere dentro le linee rosse/verdi (range fisico)
- **G13 (traiettorie ricostruite)**: simulando un'auto con i parametri che la rete predice, la traiettoria deve assomigliare a quella vera per almeno 5 secondi

### 9.3 Riferimento di paragone

Non esiste un benchmark "ufficiale" per questo task, ma in letteratura:
- Un **MLP classico** ben calibrato (con metodi tradizionali tipo Levenberg-Marquardt) raggiunge val ~ 0.10–0.15
- Per la nostra **SNN su FPGA** è ragionevole puntare a val ~ 0.15–0.20 (un po' peggio del MLP per la quantizzazione, ma accettabile)
- Stato attuale: siamo a **val ≈ 0.28** — ancora lavoro da fare (vedi §11)

---

## 10. Come si lavora con la rete in pratica

### 10.1 Esperimento singolo

C'è un notebook Jupyter chiamato **Training_File.ipynb**. Si modifica solo la **Cella 1**
(la configurazione: nome esperimento, numero di epoche, scenario...), poi si fa "Run All".
Il notebook fa tutto da solo:
1. Sincronizza il codice col repository
2. Esegue un "**preflight**" (due test mini-veloci da ~1 min ciascuno: se passano, ok)
3. Lancia il training vero
4. Mostra i 13 grafici diagnostici
5. Mette tutto su Git e fa il push automatico

### 10.2 Sweep parametrico

Per testare tante configurazioni in batch: **Training_File_Sweep.ipynb**. Stesso schema,
ma in Cella 1 si scrive una **lista** di configurazioni da provare in sequenza. Anche qui
preflight + train + push, per ogni config.

### 10.3 Telemetria

Ogni training produce:
- Un CSV "per epoca" (16 colonne con metriche principali)
- Un CSV "per batch" (20 colonne, ~190 KB per epoca: ogni singolo batch tracciato)
- 13 grafici PNG diagnostici

Il "per batch" è importantissimo: anche se il training crasha a metà, abbiamo un audit
completo di cosa è successo fino al momento del crash.

---

## 11. Cosa abbiamo scoperto finora (stato attuale)

Durante lo sweep STEP 2B abbiamo testato **5 reti di dimensioni diverse** (da 864 a 9605
parametri) sullo stesso scenario (highway). Risultato:

| Dimensione rete | val_loss best |
|---|---|
| 864 params (baseline) | 0.2802 |
| 1.685 params | 0.2789 |
| 2.757 params | 0.2790 |
| 5.669 params | 0.2797 |
| 9.605 params | 0.2792 |

Tutte le reti, indipendentemente dalle dimensioni, convergono allo stesso valore (~0.279).
Questo vuol dire che **ingrandire la rete non aiuta più**: il limite è altrove.

### Cosa stiamo investigando ora

- **Minimi locali**: forse il training si ferma troppo presto. Da testare con più epoche e
  scheduler "warm restart" (cosine).
- **Saturazione dati**: forse 500 traiettorie sono troppo poche. Da testare con 1500.
- **Quantizzazione**: forse i pesi potenze-di-2 stanno mettendo un tetto strutturale.

### Su altri scenari

Abbiamo provato anche **urban** e **truck**:

| Scenario | val_loss best | Note |
|---|---|---|
| highway | 0.279 | OK, ma plateau |
| urban | 0.388 | Crash a epoca 3 (neuroni morti) |
| truck | 0.160 | Crash a epoca 5 (dopo aver imparato bene) |

Truck è curiosamente **più facile** di highway: i parametri di un camion sono più "ristretti"
(meno variabilità) → la rete ha meno da imparare. Urban è il più difficile perché ha
stop-and-go imprevedibili.

---

## 12. Per saperne di più

| Vuoi sapere... | Dove guardare |
|---|---|
| Tutti i dettagli tecnici, formule e codice | `HOW_IT_WORKS.md` / `.pdf` (versione v1, completa) |
| Storia delle decisioni passate (perché abbiamo scelto X invece di Y) | `TIMELINE.md`, `P_S.md` |
| Cosa significano i codici "P9", "B5", "F12" ecc. | `GLOSSARY.md` |
| Come si esegue un training su Azure | `WORKFLOW.md` |
| Il libro di traffic flow di riferimento | Treiber & Kesting, *Traffic Flow Dynamics*, 2nd ed. (2025) |
