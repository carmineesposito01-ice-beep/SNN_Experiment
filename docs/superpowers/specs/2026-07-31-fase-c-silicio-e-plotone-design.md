# Fase C — Validazione su silicio e chiusura mesoscopica — design

> **Data:** 2026-07-31 · **Branch:** `Simulink_Importer` · **Stato:** design approvato
> **Target:** PYNQ-Z1 (Zynq-7020) · **Oggetto:** `Donatello_SNN_IIDM` (composto) e `Donatello_Tier` (SNN sola)
>
> ⚠️ **SUPERA** `2026-07-11-fpga-phase-c-silicon-validation-design.md`, che puntava alla **SNN da sola in
> architettura B2**, precede tutta la Fase B2.0 e ha una mappa registri diversa. Quel documento resta come
> storia; questo è la spec valida.

---

## 0. Da dove si parte

La Fase B2.0 ha prodotto, per il composto: equivalenza RTL↔blocco in anello chiuso (**0 / 58 522** su 99
scenari), equivalenza dal processore via AXI (**0 / 58 522**, entrambi i gating), equivalenza della netlist
post-place&route (**0 / 1507**, sottoinsieme dichiarato), frequenza deployabile **40 MHz**, energia dinamica
**1,10 mJ** per control-step, e un **bitstream provato identico** al sistema caratterizzato. Per la SNN da
sola, la Fase T6 ha prodotto gli analoghi e un bitstream a **52 MHz**.

Restano dichiarati aperti, nei due report, tre punti — ed è da lì che questa fase prende gli obiettivi.

| Limite dichiarato | Perché è aperto |
|---|---|
| Guadagno in watt del clock gating | `report_power` deriva la potenza dei net di clock dal **vincolo di frequenza**, non dall'attività registrata (accertato anche in negativo) |
| Caso peggiore energetico | si riporta il massimo **osservato**; il worst sintetico fu smentito su misura |
| Comportamento su silicio | tutto B2.0 è simulazione, STA e implementazione: nessun numero viene da hardware acceso |

A questi se ne aggiunge un quarto, interno al set di metriche e documentato nel codice del motore canonico:
la **string stability** riportata è *«un proxy LOCALE = il caso N=1, NON la string stability del plotone»*.

## 1. Decisioni di scope

| Decisione | Scelta | Alternativa scartata, e perché |
|---|---|---|
| Disponibilità hardware | board presente ma non utilizzabile ora → **design-for-later**: harness e golden completi e verdi col mock **adesso**, esecuzione dopo | attendere la board per scrivere: perde il lavoro che non dipende da essa |
| Misura di potenza | **differenziale total-board**, senza modifiche alla scheda | shunt sul rail VCCINT: chiuderebbe anche il caso peggiore, ma richiede modifica hardware ed è sproporzionato |
| Amplificazione del segnale | **replicazione spaziale ×3** | time-multiplexing su una istanza: **impossibile**, la rete ha stato interno persistente e servire un secondo veicolo lo contaminerebbe (§6) |
| Orchestrazione | **doppia facciata** — notebook e script — sopra moduli condivisi, con cancello di parità | una sola facciata: si perde il termine di paragone che l'utente ha chiesto |
| Perimetro | **tre filoni** in una spec unica | spec separate: la conclusione del progetto si frammenta |

**Strumento disponibile:** ZOYI/ZOTEK **ZT-702S**, 2-in-1. Come oscilloscopio ha sensibilità verticale minima
**20 mV/div** — tre ordini di grandezza sopra il segnale utile su uno shunt, quindi **non utilizzabile** per
questa misura. Come **multimetro** ha 9999 conteggi, cioè ~0,1 mA di risoluzione in portata mA: è quello che
si usa, in serie all'alimentazione.

## 2. Perché la misura differenziale è l'unica che può funzionare

Il PL consuma **114 mW** (11 dinamica + 103 statica) contro **1,5–2,5 W** di scheda, dominati dai due core
ARM: lo 0,5 %, invisibile in assoluto. Ma il numero che interessa non è assoluto.

**Stesso hardware, stesso stato del processore, cambia solo il bitstream.** (a) PL vuoto · (b) design con
gating spento · (c) design con gating acceso. La differenza (b)−(a) isola il PL; (b)−(c) è il guadagno del
gating. Il consumo del processore **si cancella**.

A 5 V, 7 mW sono **1,4 mA**: con 0,1 mA di risoluzione sono **14 conteggi**. Con la replicazione ×3 diventano
**~4 mA, 40 conteggi**. Misurabile — a tre condizioni, che sono la parte non ovvia del disegno.

### 2.1 Le tre condizioni

1. **L'ordine delle configurazioni va RANDOMIZZATO, non alternato.** Mytkowicz et al. (ASPLOS 2009,
   *Producing Wrong Data Without Doing Anything Obviously Wrong*) documentano spostamenti del **±10 %** da
   cause estranee all'esperimento — abbastanza a **invertire una conclusione**. Un A/B/A alternato è
   vulnerabile proprio alla deriva che pretende di cancellare. Si sorteggia la sequenza e si ripete.
2. **La temperatura di giunzione va REGISTRATA a ogni punto.** La dispersione è **esponenziale nella
   temperatura** (WP221) e la statica è **103 mW su 114**, cioè la parte dominante. Senza `Tj` si misura il
   riscaldamento della scheda e lo si chiama gating. L'**XADC** (UG480) fornisce `Tj` e le tensioni dei rail
   — **non la corrente**: serve a questo, non alla misura di potenza. I punti presi fuori equilibrio termico
   si **scartano**, e il criterio di equilibrio è dichiarato prima.
3. **Il risultato è una distribuzione, non un numero.** Mediana, p99, dispersione, e l'incertezza dichiarata
   accanto al valore. Un singolo numero su una misura al limite della risoluzione non è un risultato.

### 2.2 Un'ipotesi verificabile, che è il risultato più informativo della fase

`ch22` del corpus FPGA documenta che la potenza misurata su scheda esce **1,5–2× il `report_power`** (o la
metà) quando SAIF e livello di confidenza non sono dichiarati. Noi li abbiamo dichiarati: **62,7 %** di
copertura, confidenza `High`. La Fase C **verifica quindi la stima di simulazione**, e l'esito è informativo
in entrambi i casi: se coincide, la catena di stima è validata end-to-end; se non coincide, si sa quale
assunzione ha ceduto e il numero di B2.0 va riletto alla luce di questo.

## 3. Struttura: quattro livelli, dal più certo al più incerto

Ogni livello è un cancello che, se rosso, dice **quale dei precedenti** indagare.

| Livello | Cosa prova | Esito atteso |
|---|---|---|
| **C0 — Vita** | il bus risponde e i registri ritengono | scrittura/rilettura sui 4 registri d'ingresso |
| **C1 — Funzionale** | il silicio riproduce la simulazione | accel **bit-esatta** al golden di T7a, 99 scenari |
| **C2 — Anello chiuso** | il sistema deployato guida | serie complete e **31 metriche** ricalcolate |
| **C3 — Energia** | la stima di simulazione regge | differenziale con `Tj` e ordine randomizzato |

**C0 prima di tutto.** Il corpus SoC prescrive un registro di identificazione come primo test di bring-up.
Il wrapper non ne ha uno, ma i quattro registri d'ingresso sono leggibili: la scrittura con rilettura è
l'equivalente, e va eseguita prima di qualunque inferenza. Un bus muto scoperto dopo una campagna è tempo
perso.

**Perché C1 è più forte di quanto sarebbe stato prima di B2.0.** T7a ha provato l'RTL bit-esatto al blocco su
58 522 confronti. Il silicio esegue **quello stesso RTL**, quindi **deve** riprodurre esattamente le stesse
serie — non «entro tolleranza». Una discrepanza non è un errore d'algoritmo: è un errore di **deployment**,
e §7 dice dove guardare.

**C2 porta con sé il proprio PLANT-PAR.** In C1 si replaya la sequenza d'ingressi **registrata**: è anello
aperto, quindi il confronto è esatto. In C2 il plant gira sul processore in Python, e se differisce di un ULP
dal riferimento le traiettorie divergono — lo stesso problema del §3 del report T7. Perciò **prima** si prova
che il plant sul processore riproduce il riferimento *senza* l'acceleratore, **poi** si chiude l'anello. È la
decomposizione in due prove disgiunte di T7a, applicata al silicio.

## 4. I tre filoni

### Filone A — Silicio, composto
C0 → C3 sul bitstream del composto (40 MHz), che è già **provato identico** al sistema caratterizzato.

### Filone B — Silicio, SNN da sola
La stessa scala sul bitstream di T6 (**52 MHz**), che esiste. Dà il quadro del singolo pezzo: la rete
`Tier@BALANCED` da sola sul silicio, e poi — con il filone A — la stessa rete *con* il controllore.

**Ogni bitstream si misura al proprio punto deployabile**, 52 MHz per la SNN e 40 per il composto. È il numero
che descrive come quel pezzo spedirebbe davvero; una build della SNN a 40 MHz sarebbe un artefatto che esiste
solo per una sottrazione e che nessuno metterebbe in campo. Questo mantiene anche la continuità con quanto già
caratterizzato in T6b e T7b, senza introdurre un punto di misura che non corrisponde a nulla.

> ⚠️ **Conseguenza dichiarata: l'energia incrementale del controllore NON è ottenibile da questa fase.**
> Verrebbe naturale ricavarla per differenza fra i due filoni, ma i bitstream differiscono anche in frequenza.
> La potenza dinamica scala con essa ed è dominata dall'albero del clock (~78 % secondo T6b): da 52 a 40 MHz
> sono +30 % su quella quota, **≈ 2,6 mW**. Con una risoluzione differenziale di ~0,5 mW per conteggio sono
> ~5 conteggi — non sotto la soglia, ma **dello stesso ordine del costo del controllore** che si vorrebbe
> isolare. I due effetti non sono quindi **separabili** da questa misura.
>
> La ripartizione dell'**area** fra rete, allineamento e controllore resta nota dalla gerarchia post-route
> (§6.3 del report T7). Quella dell'**energia** richiederebbe di equalizzare la frequenza, introducendo un
> punto di misura fittizio, oppure l'accesso al rail del PL. Passa fra i limiti dichiarati (§11).

### Filone C — Plotone
Chiude il proxy dichiarato nel motore canonico. L'infrastruttura **esiste già e non è mai stata usata**:
`simulate_platoon`, `platoon_string_metrics`, `transfer_gain_fft`.

| | Cosa risponde | Board |
|---|---|---|
| **P1 — simulazione** | il plotone smorza o amplifica? a quali frequenze? fino a che N? | no |
| **P2 — RTL** | l'RTL riproduce il plotone bit-esatto? (stessa decomposizione di T7a) | no |
| **P3 — silicio** | quanti nodi stanno, chiudono i tempi, quanto costa un nodo? | sì |

**La string stability la dà P1.** È una proprietà della legge di controllo, e poiché l'RTL è bit-esatto al
blocco, il numero mesoscopico non cambia sul silicio. P3 risponde alla domanda di **deployment**, che è
diversa e serve al V2I.

**Le risorse per P3 si MISURANO.** Il vincolo è il DSP (69 su 220 → 3 istanze). Vivado può forzare i
moltiplicatori in fabric (`-max_dsp`), ma un 25×18 costa nell'ordine delle centinaia di LUT: forzarli tutti
farebbe esplodere il budget, mentre un forcing **parziale** può ribilanciare. La curva non è nota e costa
~10 min per punto: è una **sonda**, con la stessa disciplina dello sweep FCLK, non un'assunzione.

## 5. Componenti — unità isolate

**Il notebook orchestra; la logica sta nei moduli.** È la forma che il progetto usa già
(`Loss_Study_Eval_ClosedLoop` importa i moduli e scrive artefatti). Il vincolo che la impone qui è preciso:
l'harness deve essere provabile **col mock adesso, senza scheda**, e la logica dentro una cella non si può
esercitare con un mock né condividere fra il processore e il PC.

| Unità | Responsabilità | Dipende da |
|---|---|---|
| `phase_c/pynq_snniidm.py` · `pynq_tier.py` | driver: mappa registri, commit, attesa `done`, lettura | overlay o mock |
| `phase_c/c0_liveness.py` | scrittura/rilettura sui registri, **primo di tutto** | driver |
| `phase_c/c1_functional.py` | replay dei 99 scenari sugli ingressi **registrati**, bit-esatto | driver, golden T7a |
| `phase_c/c2_closedloop.py` + `plant_ps.py` | PLANT-PAR del processore, poi anello chiuso | driver |
| `phase_c/c3_power.py` | differenziale randomizzato, `Tj` da XADC, distribuzione | driver, procedura guidata |
| `phase_c/platoon.py` | P1/P2/P3 sopra `simulate_platoon` | motore canonico |
| `phase_c/mock_overlay.py` | finge la scheda: test verdi **ora** | — |
| `run_phase_c.sh [stadio]` | facciata a stadi, headless | i moduli |
| `phase_c.ipynb` | facciata interattiva: **grafici**, nessun calcolo proprio | i moduli |
| `c_frontend_parity.py` | cancello: le due facciate producono artefatti identici | artefatti |

**Il golden non si rifà.** T7a ha già prodotto e validato stimoli e riferimenti per i 99 scenari, nel formato
che il wrapper consuma. Riusarli tiene prova e misura sullo stesso perimetro, ed evita la classe di errori
che il golden monolitico era costata (385 scarti su 600, §3.3 del report T7).

**Tre bitstream per il differenziale**, non uno: `blank` · `×1` (già esistente e provato identico) · `×3`.

### 5.1 Il cancello di parità fra le facciate
Le due facciate, sullo **stesso stato della scheda**, devono produrre artefatti **identici** (esclusi i campi
volatili: orario, percorsi assoluti). Se divergono, una delle due contiene logica propria: è un difetto, non
una curiosità. Gli artefatti portano la **provenienza** — quale facciata, quando, con quale firma del
bitstream — così «quali sono i numeri veri» non è mai una domanda.

## 6. Il time-multiplexing non è una via

Il margine sul control-step è **7207×**, quindi verrebbe naturale servire molti veicoli con una sola istanza.
**Non funziona:** la rete ha stato interno persistente (`hdl.RAM`, filtro OU, stato dei neuroni), e servire un
secondo veicolo senza salvare e ripristinare quello stato lo contaminerebbe. Il banking dello stato sarebbe
una modifica al blocco **congelato**. Sul silicio l'unica strada per il plotone è la **replicazione spaziale**.

Registrato qui perché è una scorciatoia che sembra gratuita e costerebbe una campagna.

## 7. Errori: la scaletta diagnostica

Se C1 fallisce, il sospettato **non** è la rete — è già validata a monte con esito 0. Dal corpus SoC:

| Guasto | Sintomo | Prima cosa da controllare |
|---|---|---|
| **Formati numerici diversi ai due lati** | risultati **plausibili** ma sbagliati, errore che scala con la grandezza | En20 in ingresso, `sfix13_En8` in uscita, impacchettamento in Python |
| Indirizzi/offset sbagliati | letture a zero o spazzatura dal primo accesso | mappa registri contro l'assegnazione degli indirizzi |
| Polarità del reset invertita | l'acceleratore non esce dal reset | verso del reset al confine del wrapper |
| Clock dell'interconnessione assente | la transazione si blocca | configurazione dei clock del processore |
| `START` che non si auto-azzera | la prima inferenza riesce, la seconda mai | ritorno a idle della macchina a stati |
| Pipelining insufficiente | risultati sbagliati **intermittenti** | report di timing prima di incolpare l'algoritmo |

Il primo è il più insidioso perché **non si manifesta come guasto**. Ed è il nostro rischio più concreto.

Le grandezze non ottenibili restano **dichiarate**, come nei due report di B2.0.

## 8. Test adesso, senza scheda

`mock_overlay` implementa l'interfaccia dell'overlay PYNQ e risponde coi golden di T7a. Con esso tutti i
moduli hanno test verdi **ora**; solo l'esecuzione reale aspetta.

⚠️ **Il mock va provato anche in negativo.** Se gli si inietta un valore alterato, C1 **deve** fallire.
Un mock che non si è mai visto far fallire il cancello sta solo confermando sé stesso — è la stessa regola che
in B2.0 ha intercettato quattro errori di chi scriveva.

## 9. Criteri di successo

1. **C0** risponde · **C1** bit-esatto sui 99 scenari · **C2** un episodio completo stabile, con il PLANT-PAR
   del processore verde **prima**
2. Le **31 metriche** ricalcolate dalle serie del **silicio** coincidono con quelle di T7a
3. **C3**: guadagno del gating misurato, con incertezza e `Tj` dichiarate, e il confronto esplicito con la
   stima di simulazione (§2.2) — informativo in entrambi gli esiti
4. **Filone B**: la SNN da sola validata sul silicio al **proprio** punto deployabile (52 MHz), con la
   sua potenza di deployment. L'energia **incrementale** del controllore non fa parte dei criteri: e'
   dichiarata non separabile (§4, filone B)
5. **Filone C**: string stability **vera** che sostituisce il proxy nei report; per P3, la curva risorse
   misurata e il numero di nodi che chiudono i tempi
6. Tutto **rigenerabile da un comando**, con le due facciate in **parità**, e ogni decisione architetturale
   con la sua alternativa scartata scritta accanto

## 10. Vincoli permanenti

- **Core SNN congelato**: la Fase C non tocca RTL né blocco. Usa i **bitstream esistenti** così come sono;
  l'unica ri-implementazione è il `×3` del filone C, dagli stessi sorgenti e con firma di provenienza
  verificata.
- **Niente work-around**: un disallineamento si indaga fino alla causa, non si aggira.
- **I numeri vivono negli artefatti**, mai nella chat né nell'output di una cella.
- **Un cancello che non può fallire non è un cancello**: ognuno va visto fallire su dati alterati.
- Commit **senza** `Co-Authored-By`.

## 11. Cosa resta comunque fuori

| Domanda | Perché resta aperta |
|---|---|
| Caso peggiore energetico a risoluzione PL | richiede accesso al rail VCCINT, cioè modifica della scheda; e individuare il regime peggiore richiederebbe uno studio dedicato |
| **Energia incrementale del controllore** (ACC-IIDM + `align`) | i due bitstream sono misurati a frequenze diverse — ciascuno al proprio punto deployabile, per scelta — e l'effetto della frequenza (≈2,6 mW) è dello stesso ordine di quello da isolare. Equalizzare significherebbe misurare un punto che nessuno spedirebbe. L'area, invece, è nota dalla gerarchia |
| Collo di bottiglia `DEC → align → IIDM` | è una questione di micro-architettura, indipendente dal silicio; non blocca nulla (margine 7207×) |
| Confronto MPC-vs-SNN | design parcheggiato, spec già depositata |
