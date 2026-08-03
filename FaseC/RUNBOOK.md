# RUNBOOK — Fase C con la scheda accesa

Procedura operativa per PYNQ-Z1 (Zynq-7020). Tutto il codice è già scritto e collaudato contro
il mock: **il giorno del bring-up non si scrive codice, si esegue.**

> **Regola che vale per ogni stadio:** se un cancello è rosso, **fermarsi e leggere la diagnosi**.
> Ogni stadio è costruito per dire *quale* guasto è più probabile dato il sintomo osservato, non
> soltanto «non funziona». Proseguire dopo un rosso significa misurare rumore e attribuirlo
> all'acceleratore.

---

## 0. Prima di accendere

| | |
|---|---|
| Bitstream, tutti e tre | `FaseC/bitstream/{blank,x1,x2}.{bit,hwh}` — è **da qui** che `overlay_hw.py` li carica |
| Bitstream SNN sola | 52 MHz — `FaseB2.0/Harness_SNN/bitstream/snn_tier_donatello.{bit,hwh}` |
| Golden bit-esatti | `$T7_WORK/axi_{stim,gold,len}_<i>.mem`, i = 1…99 (default `C:/t7bw`) |
| Strumenti | multimetro 9999 conteggi **in serie** all'alimentazione |

⚠️ I `.bit` **non sono versionati** (4 MB, rigenerabili). Se mancano:
`bash hw/build_bitstreams.sh tutti`. I `.hwh` invece sì — sono piccoli e senza di loro PYNQ non
sa nulla della mappa degli indirizzi.

**Copiare sulla scheda il `.bit` E il `.hwh` insieme**, con lo stesso nome base: PYNQ legge la
mappa degli indirizzi dal `.hwh`, e senza quello `Overlay()` fallisce prima ancora di C0. È il
primo blocco possibile del bring-up, ed è banale evitarlo.

```bash
cd FaseC && python -m pytest        # dev'essere tutto verde PRIMA di accendere
```

Se qui è rosso, il problema è nel codice o nell'ambiente: risolverlo adesso costa minuti,
scoprirlo a metà campagna costa la campagna.

### I due cancelli di accensione

Vanno **osservati**, non supposti. Entrambi falliscono in silenzio se nessuno li controlla, e
entrambi invalidano tutto ciò che viene dopo.

**1. L'XADC legge davvero.**

```python
from phase_c import xadc
tj, vcc = xadc.read_tj_sysfs(), xadc.read_vccint_sysfs()
xadc.verifica_plausibile(tj, vcc)          # solleva se fuori dai limiti FISICI
```

Una lettura fallita non dà errore: dà `0`, che nella eq. 2-9 di UG480 fa esattamente
**−273,15 °C**. È il numero che nessuno guarda, perché «è solo la temperatura» — finché i dati di
potenza non risultano inspiegabili. Se anche il percorso MMIO è disponibile, `confronta_percorsi`
li mette a confronto: **un percorso solo non può contraddirsi.**

**2. Il reset del DUT avviene.**

```python
from phase_c.overlay_hw import prova_firma_del_reset
prova_firma_del_reset(ov)                  # DOPO uno scenario completato
```

Non esiste un bit di reset software: `started` torna a zero solo riasserendo `ARESETN`, cioè
ri-scaricando il bitstream (`snniidm_axi_lite.v:152`). La firma osservabile è `done_lat` che passa
da **1 a 0**, e `prova_firma_del_reset` si rifiuta di girare se vale già 0 — lì non potrebbe
distinguere nulla. Senza questo controllo uno scenario partirebbe dallo stato del precedente, e la
Fase C chiamerebbe «silicio» dei numeri sbagliati.

---

## 1. C0 — il bus risponde

```bash
./run_phase_c.sh c0
```

Scrive e rilegge 5 pattern sui 4 registri d'ingresso: `00000000` e `FFFFFFFF` trovano le linee
incollate, `AAAAAAAA` e `55555555` i corti fra bit adiacenti, `0222CBBF` è un valore reale del
golden e prova il percorso, non solo i bit.

**Costo:** ~200 ms. **Artefatto:** `results/c0.json`.

| Se è rosso, dice… | Guardare per primo |
|---|---|
| «il bus non arriva» (tutte le riletture a 0) | clock dell'interconnessione, polarità del reset |
| «bit *N* incollati a 1/0» | il collegamento fisico di quelle linee |
| «fallisce un solo registro» | la mappa degli indirizzi, non il bus |
| «nessuna firma inequivocabile» + evidenza grezza | allegare la tabella; più bit coinvolti |

---

## 2. C1 — bit-esatto sui 99 scenari

```bash
./run_phase_c.sh c1
```

Rigioca gli ingressi **registrati** da T7a e confronta l'accelerazione **bit per bit**. Non
«entro tolleranza»: T7a ha provato l'RTL bit-esatto al blocco su 58 522 confronti e il silicio
esegue quello stesso RTL, quindi una discrepanza è un errore di *deployment*, non d'algoritmo.

> ⚠️ **L'acceleratore va resettato a ogni scenario.** Non è una precauzione: nel wrapper
> `dut_rst = ~S_AXI_ARESETN | ~started` e `started` si alza al primo commit senza mai tornare
> basso ([snniidm_axi_lite.v:150-153](../FaseB2.0/Harness_SNN_IIDM/hw/snniidm_axi_lite.v)). Lo
> stato interno della rete **non è azzerabile dalla mappa registri**. Ogni golden è stato però
> prodotto con la rete azzerata all'inizio di *quello* scenario. Su PYNQ il reset è
> `overlay.download()`; `run_c1` lo chiama da sé.

**Costo:** 99 × 600 inferenze + 99 reset. **Artefatto:** `results/c1.json`.

Se è rosso, la scaletta diagnostica è ordinata per compatibilità col sintomo:

1. **formato numerico** — valori plausibili ma sbagliati, errore che *scala* con la grandezza
2. **mappa indirizzi** — letture a zero o costanti dal primo campione
3. **START non si auto-azzera** — la *prima* inferenza è giusta, tutte le altre no
4. **polarità del reset** — stato sempre nullo
5. **pipelining insufficiente** — errori *intermittenti*: guardare il timing prima dell'algoritmo

---

## 3. C2 — anello chiuso

Il plant gira sul processore, quindi una sua divergenza si presenterebbe come un errore del
silicio. Per questo il **PLANT-PAR viene prima e da solo**, e `run_c2` si **rifiuta** di partire
finché non è verde.

```bash
./run_phase_c.sh c2      # esegue PLANT-PAR, poi l'anello
```

**Artefatto:** `results/c2.json` (le traiettorie; il notebook le disegna).

Se il PLANT-PAR è rosso, il difetto è nel plant del PS, non nell'acceleratore. I due punti in
cui un port 1:1 smette di esserlo:
- **ordine di update** — prima `v` nuova, poi `s` con la `v` nuova ([qz_cl_sim.m:26-27](../matlab/Quantizzation_Study/qz_cl_sim.m)). Invertirlo dà 599 disallineamenti su 600.
- **teletrasporto del cut-in** — al passo indicato (base 1) il gap è **sostituito**, prima di calcolare `dv`. Un terzo del dataset ha il cut-in.

---

## 4. C3 — potenza differenziale

Il PL consuma 114 mW dentro 1,5–2,5 W di scheda: in assoluto è invisibile a un multimetro da
9999 conteggi. Ma il numero cercato **non è assoluto**. Stesso hardware, stesso stato del
processore, cambia solo il bitstream:

```
(b) − (a)   isola il PL              a = blank, b = una istanza
(b) − (c)   il guadagno del gating   c = una istanza col gating spento
```

Il consumo del processore, dei regolatori e della periferia **si cancella nella differenza**.

### Procedura, passo per passo

1. **Multimetro in serie** all'alimentazione della scheda.
2. **Equilibrio termico prima di iniziare.** Criterio dichiarato in anticipo, non scelto
   guardando i dati: `Tj` stabile entro **±0,5 °C su 12 letture consecutive** (`xadc.at_equilibrium`).
   Un punto preso mentre la scheda si scalda porta dentro una deriva che verrebbe poi attribuita
   alla configurazione sotto test.
3. **Sequenza SORTEGGIATA**, non alternata: `plan_sequence(punti, repeats, seed)` col **seme
   annotato**. Alternare A/B/A/B correla la condizione con l'istante ed è vulnerabile proprio
   alla deriva che pretende di cancellare — il bias di misura vale ±10%, abbastanza a invertire
   una conclusione.

   Il sorteggio copre i **punti**, non le sole configurazioni. I punti sono 5, non 3
   (`punti_di_misura()`): `blank/-`, `x1/on`, `x1/off`, `x2/on`, `x2/off`. Il gating si cambia
   con una scrittura di registro invece che con un bitstream, quindi verrebbe naturale visitarlo
   sempre nello stesso ordine dentro ogni configurazione — e sarebbe di nuovo una condizione
   correlata all'istante. Su `blank` il PL è vuoto e il bit non comanda nulla: **un punto solo**,
   marcato `-`, altrimenti sarebbero due repliche della stessa cosa spacciate per due condizioni.
4. **A ogni punto** si registra `(cfg, gating, mA, Tj, VCCINT, Tj_dopo)`. Almeno **6 ripetizioni
   per punto**. `Tj` si legge **subito prima** della corrente e `Tj_dopo` **subito dopo**: la
   trascrizione manuale dura secondi, e se la temperatura si è mossa nel frattempo la `Tj`
   registrata non descrive l'istante della corrente. La deriva viene contata e finisce
   nell'artefatto (`n_deriva_durante_lettura`).
5. I punti fuori dalla banda termica dichiarata si **scartano**, e il conteggio degli scartati
   **resta nell'artefatto**: uno scarto silenzioso è uno scarto che nessuno potrà più rimettere
   in discussione.

L'intera procedura è `c3_power.esegui_campagna(dmm, banco, seed=…, repeats=…)`. Il `seed` **non
ha default**: un default silenzioso darebbe una sequenza «sorteggiata» che nessuno ha scelto.
Il foglio si scrive **riga per riga con flush** — una campagna dura ore e un'interruzione a metà
non deve costare i punti già misurati.

### Da dove arriva il numero di corrente

Tre sorgenti dietro la stessa interfaccia (`phase_c/dmm.py`), e la scelta finisce nella
provenienza dell'artefatto: una misura letta a mano e una letta dallo strumento **non sono lo
stesso dato**.

| Sorgente | Quando |
|---|---|
| `PromptDMM` | ripiego che funziona sempre. L'operatore trascrive **quando il runner chiede** — l'istante non lo sceglie lui |
| `SerialDMM` | ZT-702S via seriale. **Richiede un parser esplicito** (vedi sotto) |
| `ReplayDMM` | ri-aggregare una campagna già fatta, p.es. cambiando la banda termica. **Non** è un modo di raccogliere dati |

#### Il collegamento fisico dello ZT-702S

Dal **manuale dello strumento** (pagina delle porte, letta direttamente — fonte primaria, non
ricerca sul web). Sotto l'alettina ci sono tre cose:

| Porta | Cosa dice il manuale |
|---|---|
| **USB-C** | «Communicate with the computer and charge the battery through the TYPE-C data cable» — è il canale col PC **e** la ricarica |
| tonda | terminale di **massa** |
| quadra | terminale di **segnale**, «constant output 3V/1KHZ» |

⚠️ La porta quadra è un'uscita di **calibrazione a onda quadra fissa**, non una seriale
configurabile. Una versione precedente di questo runbook proponeva di prenderci un UART con un
adattatore USB-UART, sulla base del manuale del **ZT-703S** trovato in rete: **non è sostenuto dal
manuale di questo strumento**. Non comprare l'adattatore su quella base. Resta da verificare se
esista una voce di menu (F4 → *serial port output*) che ne cambi la funzione; finché non è vista
sullo strumento, è un'ipotesi.

#### Esito: **nessun canale dati verso il PC. Chiuso.**

Indagato il 2026-08-03 ed esaurito. Non riaprirlo senza un fatto nuovo.

| Provato | Esito |
|---|---|
| USB-C, cavo in dotazione | nessuna enumerazione |
| USB-C, **cavo dati certo** | nessuna enumerazione |
| Porte USB diverse | nessuna enumerazione |
| Scollega/ricollega con rilevatore attivo | nessun evento |
| `pyserial`, porte COM | zero |
| Dispositivi in errore o senza driver | nessuno |

Il rilevatore **non** è in dubbio: nella stessa sessione ha registrato eventi reali — un dongle
USB sparito e ritornato — e il conteggio dei dispositivi lo ha seguito in tempo reale
(158 → 156 → 159). Vede gli arrivi; il multimetro non ne genera.

Il manuale, dal canto suo, contiene **soltanto** la frase «Communicate with the computer and
charge the battery through the TYPE-C data cable»: nessuna procedura di collegamento, nessun
software, nessuna modalità da attivare. Una promessa senza istruzioni, e senza enumerazione
osservata in nessuna configurazione.

**Conseguenza operativa:** l'acquisizione è `PromptDMM`, e va bene così. Anche un canale
funzionante andava verificato per un requisito che nessuna fonte gli attribuisce — la lettura
**live nell'istante richiesto**, non l'esportazione di registrazioni salvate — quindi il costo
atteso di continuare a inseguirlo era alto e il beneficio incerto.

⚠️ Questo cambia il **dimensionamento**, non il metodo: con la lettura manuale ogni replica costa
un'attesa di equilibrio termico. Vedi la tabella delle repliche più sotto — è lì che questa
decisione si paga.

#### Se un giorno una porta comparisse — come si ricava il parser

Questa procedura **non va eseguita adesso**: non c'è nessuna porta. È qui perché il giorno in cui
comparisse (altro strumento, adattatore, firmware diverso) il modo giusto di procedere non vada
riscoperto da capo.

⚠️ **Il parser seriale non è scritto, ed è deliberato.** Il formato del frame di questi strumenti
non è documentato in modo affidabile e cambia fra revisioni dello stesso modello: uno scritto «da
manuale» non darebbe errore, darebbe numeri **plausibili**. Procedura per ricavarlo:

```bash
python hw/dmm_discover.py --lista
```

```bash
python hw/dmm_discover.py --porta COM3 --secondi 10
```

(display su un valore **noto e stabile**; `pip install pyserial` se manca)

Si cerca la lunghezza del frame (dal periodo con cui si ripete un byte fisso), i byte costanti
(delimitatori, unità) contro quelli che cambiano (le cifre), e il valore del display dentro i byte
— in ASCII, BCD o intero binario. Poi **si ripete con un secondo valore noto**: un formato
indovinato su uno solo è quasi sempre sbagliato.

Ricavato il parser, `verifica_contro_display(atteso_mA)` è il cancello obbligatorio prima della
campagna: `esegui_campagna` **si rifiuta di partire** con una seriale non validata, e lo fa
*prima* di toccare l'hardware. Un fallimento della verifica **revoca** la validazione.

### Quante repliche per punto — e quanto costano

`repeats=8` era un numero scelto a occhio. Quello giusto dipende dalla **dispersione dello
strumento**, e si misura *prima*: `misura_dispersione(dmm, banco)` fa ~10 letture in **una sola
visita** e restituisce l'IQR insieme al numero di repliche suggerito.

⚠️ Quelle 10 letture **non sono repliche** e non vanno mai messe nella campagna: condividono la
stessa visita — stesso bitstream appena caricato, stesso stato termico. Usarle come punti
indipendenti gonfierebbe `n` e restringerebbe l'errore standard senza che nulla di reale sia stato
ripetuto: **pseudo-replicazione**, cioè precisione inventata. Ed è proprio perché non sono repliche
che costano poco — una sola attesa di equilibrio invece di dieci.

L'effetto cercato è ~7 mW per istanza = **1,4 mA** a 5 V, su un fondo di ~400 mA.

<!-- generata da repliche_necessarie(); non modificare a mano -->

| dispersione (IQR, mA) | n con `x1` | n con `x2` | visite totali | ore a 3 min/visita |
|---|---|---|---|---|
| 0,5 | 2 | 2 | 10 | 0,5 |
| 1,0 | 4 | 2 | 20 | 1,0 |
| 2,0 | 15 | 4 | 75 | 3,8 |
| 4,0 | **57** | 15 | 285 | **14,2** |
| 8,0 | 226 | 57 | 1130 | 56,5 |

**Le ore contano perché la lettura è manuale.** Una *visita* è: ricarica del bitstream + attesa
dell'equilibrio termico + lettura trascritta. L'attesa domina — il resto sono secondi — e si paga
a ogni visita, perché il cambio di bitstream sposta la potenza dissipata e quindi la temperatura.

`x2` esiste per questo: raddoppia il segnale misurato lasciando invariato il rumore dello
strumento, quindi abbassa `n` **col quadrato**. Con IQR = 4 mA sono 57 visite contro 15.

Se la dispersione risultasse alta, la via d'uscita **non** è misurare di più: è riportare il solo
guadagno su `x2` — che è anche il numero più solido — e dichiarare quello su `x1` non separabile
con questo strumento. Con IQR = 4 mA sono 45 visite invece di 285.

### Come si legge il risultato

`differenza_mW` restituisce **due** incertezze, e la distinzione decide se C3 può produrre il suo
numero:

- `dispersione_mW` — quanto balla una **singola lettura**. Non scende con le repliche: è una
  proprietà dello strumento, e serve a scegliere `n` con la tabella qui sopra.
- `incertezza_mW` — quanto è incerta la **mediana** (≈ IQR/1,349 × 1,253 / √n). Scende con le
  repliche, ed è su questa che si decide `separabile`.

⚠️ Ciò che **licenzia** il √n è l'ordine sorteggiato: solo se le letture sono scambiabili la loro
mediana converge. Con un ordine alternato una deriva sistematica non si media via e dividere per
√n sarebbe una promessa non mantenuta. Le due decisioni stanno in piedi insieme — se un giorno il
sorteggio venisse tolto, questa formula andrebbe tolta con lui.

Se la differenza è dello stesso ordine dell'errore standard, la risposta corretta è **«non
separabile con questi dati»** — e la nota dice **quante repliche servirebbero**. Se quel numero è
impraticabile, allora la risposta è che lo strumento non distingue questa differenza, e va scritta
così. Inventare un numero dentro il rumore non è un risultato.

Riportare sempre una **distribuzione** (mediana, p95, IQR, minimo, massimo, n, n scartati), mai
un numero solo.

---

## 5. Filone B — la SNN da sola

Stessi stadi, bitstream della SNN a **52 MHz** e `SnnTierDriver` (cinque registri d'uscita
`0x14–0x24`: i parametri IDM, non un'accelerazione).

> **Limite dichiarato in anticipo:** la SNN non viene reimplementata a 40 MHz. L'effetto della
> frequenza sulla potenza è ≈2,6 mW, cioè lo stesso ordine di ciò che si vorrebbe isolare —
> quindi il consumo incrementale del solo controllore IIDM **non è separabile**, e questo va
> detto invece di riportare una differenza.

---

## 6. Parità fra le due facciate

```bash
./run_phase_c.sh parity c1
```

Esegue lo **stesso stadio** dallo script e dal notebook e confronta gli artefatti. Devono
coincidere a meno dei campi volatili (orario, nome della facciata, directory).

**Non** sono volatili: i dati, la firma del bitstream, la **sorgente**. Un numero prodotto col
mock e uno prodotto sul silicio non sono lo stesso risultato, nemmeno quando coincidono.

Se è rosso: una delle due facciate contiene logica propria. È un difetto, non una curiosità.

---

## 7. Ordine e costi

| Stadio | Costo | Scheda |
|---|---|---|
| `test` | ~2 min | no |
| `p1` | ~15 min | no |
| `notebook` | ~1 min | no |
| `c0` | ~200 ms | **sì** |
| `c1` | 99 × 600 inferenze | **sì** |
| `c2` | come C1, più il plant | **sì** |
| `c3` | ore (equilibrio termico + ripetizioni) | **sì** |

`./run_phase_c.sh summary` elenca gli artefatti prodotti con la loro provenienza.

---

## 8. Note d'ambiente, verificate su questa postazione

- **`jupyter nbconvert --execute` esce con 0 senza eseguire nulla** (build conda di zeromq,
  `Bad file descriptor` in `epoll.cpp`; fallisce anche un notebook con solo `print(1+1)`). Per
  questo `./run_phase_c.sh notebook` usa `check_notebook.py`, che guarda l'**artefatto** e in più
  esegue le celle in un processo pulito. **Non fidarsi mai dell'exit code di nbconvert.**
- Il dataset dei 99 scenari sta in `matlab/Quantizzation_Study/`, **non** in `data/`.
- I pesi del campione nel `.pt` **non** coincidono con quelli in `champions_export.mat`: l'export
  li quantizza a potenze di due per l'hardware. Non è un altro checkpoint, è la quantizzazione
  voluta — e il motore del plotone applica la stessa, quindi P1 misura la rete *come è deployata*.
