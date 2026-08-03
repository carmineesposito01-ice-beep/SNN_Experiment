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
| Bitstream composto | 40 MHz — `FaseB2.0/Harness_SNN_IIDM/bitstream/donatello_snn_iidm.{bit,hwh}` |
| Bitstream SNN sola | 52 MHz — `FaseB2.0/Harness_SNN/bitstream/snn_tier_donatello.{bit,hwh}` |
| Golden bit-esatti | `$T7_WORK/axi_{stim,gold,len}_<i>.mem`, i = 1…99 (default `C:/t7bw`) |
| Strumenti | multimetro 9999 conteggi **in serie** all'alimentazione |

**Copiare sulla scheda il `.bit` E il `.hwh` insieme**, con lo stesso nome base: PYNQ legge la
mappa degli indirizzi dal `.hwh`, e senza quello `Overlay()` fallisce prima ancora di C0. È il
primo blocco possibile del bring-up, ed è banale evitarlo.

```bash
cd FaseC && python -m pytest        # dev'essere tutto verde PRIMA di accendere
```

Se qui è rosso, il problema è nel codice o nell'ambiente: risolverlo adesso costa minuti,
scoprirlo a metà campagna costa la campagna.

**Da scrivere al passo 1 del primo bring-up:** `phase_c/cli.py::_overlay()` solleva oggi
`NotImplementedError` sul ramo dell'overlay reale. È l'unico punto rimasto: caricare l'overlay
PYNQ e restituirlo. Driver, stadi e diagnosi sono già pronti.

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

#### Il collegamento fisico dello ZT-702S — **non è la USB-C**

Verificato per contrasto il 2026-08-03: con lo strumento collegato via USB-C il PC **non enumera
nulla** — nessuna porta COM, nessun dispositivo senza driver, nessun evento PnP. Non è un problema
di driver: è che quel percorso non esiste.

Secondo la documentazione ZOYI la USB-C fa **alimentazione e importazione dei file salvati**. Il
flusso live è un **UART sulla porta del generatore di segnale**, da abilitare con **F4 → serial
port output**, a **115200 baud** e **3 letture al secondo**.

Serve quindi un **adattatore USB-UART** (CH340 / CP2102 / FT232) fra quella porta e il PC, con la
massa in comune.

⚠️ Questi dettagli vengono dal manuale dello **ZT-703S** (3-in-1), dato per «modello simile». Il
702S è un 2-in-1 e potrebbe non avere quella porta. Sono un'**ipotesi di partenza**, non un fatto
verificato su questo esemplare — ed è esattamente il motivo per cui la procedura sotto guarda i
byte invece di dedurre il formato.

#### Ricavare il parser

⚠️ **Il parser seriale non è scritto, ed è deliberato.** Il formato del frame dello ZT-702S non è
documentato in modo affidabile e cambia fra revisioni dello stesso modello: uno scritto «da
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

### Come si legge il risultato

`differenza_mW` restituisce anche `separabile`. Se la differenza è dello stesso ordine
dell'incertezza, la risposta corretta è **«non separabile con questo strumento»** — e va scritta
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
