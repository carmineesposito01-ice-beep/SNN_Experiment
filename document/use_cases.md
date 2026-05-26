# CF_FSNN — Use Cases (UC0–UC15)
> Estratti dal codice SysML v2 del progetto. Ogni UC riporta l'obiettivo funzionale
> e i requisiti comportamentali che il sistema di car-following deve soddisfare.
> I requisiti sono espressi in termini FUNZIONALI e COMPORTAMENTALI — indipendenti
> dalla scelta del modello CF specifico (da definirsi in fase di design).
> Aggiornato: 2026-05-25

---

## UC0 — CF_FSNN System (sistema complessivo)
**Obiettivo**: Realizzare un sistema di car-following basato su SNN/PINN capace di
adattarsi a contesti eterogenei (autostrada, urbano, veicoli pesanti) ricevendo segnali V2X
e rispettando i vincoli fisici del modello di car-following scelto.

**Requisiti comportamentali**:
- Predizione continua dei parametri del modello di car following selezionato, a partire dai segnali V2V del leader (V2X in generale)
- Compatibile con normativa V2X (ETSI ITS-G5, 10 Hz)
- Fallback funzionale in caso di packet loss ≥ 2%

---

## UC1 — CACC Synchronization
**Obiettivo**: Sincronizzare la velocità del veicolo ego con quella del leader tramite
V2V, mantenendo una distanza di sicurezza dinamica e garantendo la stabilità di stringa
nella colonna (platoon).

**Requisiti comportamentali**:
- Il sistema deve ridurre il time gap target in modalità CACC rispetto al following umano
- La risposta deve essere string-stable (perturbazioni non devono amplificarsi lungo la colonna)
- Il modello CF deve supportare la multi-anticipazione (uso di dati V2V dal 2° veicolo precedente, opzionale)

---

## UC2 — Abrupt Cut-In
**Obiettivo**: Rispondere in sicurezza a un veicolo che si inserisce abruptamente nella
corsia dell'ego con gap ridotto, senza causare frenate di panico o crash.

**Requisiti comportamentali** (**safety-critical**):
- La risposta alla riduzione improvvisa del gap deve essere **graduata e anticipatoria**, non istantanea
- Il sistema deve stimare o ricevere via V2X informazioni sulle intenzioni/accelerazione del cut-in vehicle
- Vincolo hard: la distanza minima di sicurezza non deve mai essere violata

---

## UC3 — Called Cut-In
**Obiettivo**: Gestire cooperativamente una manovra di cambio corsia concordata (il
veicolo che si inserisce segnala l'intenzione via V2V).

**Requisiti comportamentali**:
- La risposta deve essere più morbida di UC2 (cambio atteso e segnalato)
- Il segnale V2V "intenzione cambio corsia" è input al sistema; il modello CF riceve il gap già aggiornato
- Il sistema deve aumentare temporaneamente il time gap target per facilitare il merge

---

## UC4 — Shockwave Mitigation
**Obiettivo**: Smorzare le onde di stop-and-go propagandosi upstream nella colonna,
adattando la velocità dell'ego in anticipo usando i dati V2V.

**Requisiti comportamentali**:
- Il sistema deve anticipare la decelerazione del leader prima che si manifesti localmente
- In modalità CACC attiva, il time gap deve essere mantenuto costante (no variazione stocastica)
- Il modello CF deve soddisfare il criterio di string stability per tutte le frequenze operative

---

## UC5 — Adapting Following (classificazione veicolo)
**Obiettivo**: Adattare il comportamento di seguimento in base alla classe del veicolo
leader (auto, camion, autobus) ricevuta tramite V2V.

**Requisiti comportamentali**:
| Classe Leader | Comportamento atteso |
|---|---|
| Auto autostrada | Following aggressivo, gap ridotto, alta velocità |
| Auto urbana | Following moderato, bassa velocità, stop-and-go |
| Camion/bus | Following conservativo, gap aumentato, risposta lenta |
| Misto | Comportamento intermedio, appreso dal contesto |

- Il sistema deve produrre parametri CF diversi per ciascuna classe
- La rete apprende il mapping contesto V2X → parametri CF adeguati

---

## UC6 — Crossroad Adaptation (V2I / SPaT)
**Obiettivo**: Adattare il comportamento all'intersezione usando segnali V2I (SPaT =
Signal Phase and Timing) per decidere se fermarsi o attraversare.

**Requisiti comportamentali**:
- Il sistema deve essere capace di portare il veicolo a velocità zero in modo controllato (stop line)
- La velocità consigliata dalla fase del semaforo deve essere integrata nella pianificazione
- Gestione fluida delle fasi stop-and-go tipiche degli incroci semaforizzati

---

## UC7 — Speed Limits Adaptation (V2I)
**Obiettivo**: Rispettare i limiti di velocità variabili (VSL) ricevuti tramite V2I.

**Requisiti comportamentali**:
- Il sistema deve ridurre la velocità di crociera target in risposta a un VSL ricevuto
- Il profilo di decelerazione deve essere confortevole (no frenata brusca per VSL)
- La transizione al nuovo limite deve avvenire entro una distanza ragionevole

---

## UC8 — Road Hazard Warning (V2I)
**Obiettivo**: Rispondere a un warning V2I di pericolo sulla carreggiata (ostacolo,
incidente, detriti) con frenata controllata.

**Requisiti comportamentali**:
- Il sistema deve decelerare con un profilo di emergenza verso una distanza di sicurezza aumentata
- Il virtual target (pericolo) deve essere trattato come un ostacolo a velocità zero
- In caso di perdita del segnale V2I durante la manovra, mantenere l'ultima stima sicura

---

## UC9 — Road Condition Warning (V2I)
**Obiettivo**: Adattare i parametri di following in base alle condizioni stradali
(ghiaccio, pioggia, nebbia) segnalate via V2I.

**Requisiti comportamentali**:
- In presenza di bassa aderenza: aumentare il gap target e ridurre l'accelerazione/decelerazione massima
- Il sistema deve ricevere un indice di aderenza da V2I e scalare i parametri CF proporzionalmente
- La risposta deve essere graduale (nessuna variazione brusca di parametri)

---

## UC10 — Signal Violation Protection
**Obiettivo**: Proteggersi da un veicolo che brucia un semaforo rosso all'intersezione.

**Requisiti comportamentali**:
- Scenarialmente identico a UC2 (Abrupt Cut-In) ma in contesto urbano/intersezione
- Il warning V2I segnala il veicolo violatore prima che sia visibile → risposta anticipatoria obbligatoria
- La risposta deve essere equivalente a UC2 per safety-criticality

---

## UC11 — Wrong Way Driver Protection (V2I)
**Obiettivo**: Rilevare e rispondere a un veicolo contromano segnalato da V2I.

**Requisiti comportamentali**:
- Il sistema deve innescare una decelerazione di emergenza massima entro 1 tick dal warning
- Gestione solo longitudinale (il modello CF non gestisce la manovra laterale di evitamento)
- Comportamento fail-safe: dopo la frenata, mantenere velocità molto bassa fino a conferma sicurezza

---

## UC12 — Special Vehicle (veicolo di emergenza)
**Obiettivo**: Cedere precedenza a un veicolo di emergenza (ambulanza, polizia)
segnalato da V2I.

**Requisiti comportamentali**:
- Il sistema deve aumentare temporaneamente il gap target per creare spazio al veicolo di emergenza
- Rallentamento graduale e controllato (no freno brusco che generi tamponamento a catena)
- Dopo il passaggio del mezzo di emergenza: ritorno graduale ai parametri nominali

---

## UC13 — Pedestrian Protection (V2I + sensori)
**Obiettivo**: Rilevare un pedone che attraversa o è in prossimità della carreggiata
e fermarsi in sicurezza.

**Requisiti comportamentali**:
- Il pedone deve essere trattato come un target stazionario a velocità zero
- Il gap di sicurezza verso il pedone deve essere aumentato rispetto al normale following
- Il sistema deve portare il veicolo a velocità zero se necessario, con decelerazione confortevole

---

## UC14 — Degraded Signal Management (fallback sensori)
**Obiettivo**: Mantenere un comportamento sicuro quando il segnale V2X è parzialmente
o totalmente assente.

**Requisiti comportamentali**:
- In assenza di V2V/V2I: il sistema passa a un comportamento conservativo basato solo su sensori locali
- Il gap target deve essere aumentato automaticamente in modalità degradata
- Il sistema deve tollerare incertezza nella stima del gap e della velocità del leader
- Gli errori di stima devono essere modellati durante il training per robustezza

---

## UC15 — Fragmented Signal Management (V2X parziale)
**Obiettivo**: Gestire scenari in cui solo parte dell'informazione V2X è disponibile
(es. solo v_leader senza s, o solo s senza Δv).

**Requisiti comportamentali**:
- Il sistema deve operare in modo degradato ma sicuro con qualsiasi sottoinsieme degli input disponibili
- La rete deve essere addestrata con masking degli input per apprendere strategie robuste
- Il comportamento con input parziali deve essere più conservativo di quello con input completi

---

## Mappa UC → Requisiti sul Modello CF

| Use Case | Requisito chiave sul modello CF | Criticità |
|---|---|---|
| UC1 CACC | String stability, anticipazione multi-veicolo | ALTA |
| **UC2 Cut-In abrupt** | **Risposta graduata e anticipatoria al gap cut** | **CRITICA** |
| UC3 Cut-In called | Risposta ammorbidita, gestione merge cooperativo | MEDIA |
| UC4 Shockwave | String stability, time gap stabile in CACC | ALTA |
| UC5 Classificazione | Parametri CF adattivi per classe veicolo | MEDIA |
| UC6 Crossroad | Gestione velocità zero, compatibilità stop-line | MEDIA |
| UC7 Speed Limit | Velocità di crociera adattiva a VSL | BASSA |
| UC8 Hazard | Decelerazione emergenza, virtual target a v=0 | ALTA |
| UC9 Road Condition | Scaling conservativo dei parametri CF | BASSA |
| UC10 Semaforo rosso | Come UC2, in contesto intersezione | ALTA |
| UC11 Contromano | Frenata emergenza massima | ALTA |
| UC12 Emergenza | Gap target aumentato temporaneamente | MEDIA |
| UC13 Pedone | Virtual target a v=0, gap di sicurezza esteso | ALTA |
| UC14 Degraded V2X | Comportamento conservativo con incertezza input | MEDIA |
| UC15 Fragmented V2X | Robustezza a input parziali, masking training | BASSA |

> **Nota**: La scelta del modello CF specifico (e la sua formula matematica)
> è documentata separatamente in `cf_model_recommendation.md`.
> Questo file descrive SOLO i requisiti funzionali degli use case.
