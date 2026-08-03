# STATO — Fase C

> **Aggiornato:** 2026-08-03 · **230 test verdi** · albero pulito
>
> Questo è il documento da cui si riparte. Dice **dove siamo**, **cosa è già provato**, **cosa
> manca** e **perché certe strade sono state chiuse**. La procedura operativa sta in
> [RUNBOOK.md](RUNBOOK.md); la mappa dei file in [README.md](README.md); gli strumenti Vivado in
> [hw/README.md](hw/README.md). I numeri vivono negli artefatti in `results/`, non qui: quelli
> riportati sotto sono citazioni, e in caso di divergenza **vince l'artefatto**.

---

## 0. In una frase

Tutto ciò che non richiede la scheda è **scritto, provato e chiuso**. Il codice per la scheda è
scritto e collaudato contro il mock, ma **non è mai girato su silicio**: la PYNQ-Z1 non è
disponibile. La prima cosa da fare quando arriva è il §1 qui sotto.

**Non manca codice.** Manca l'hardware.

---

## 1. Quando la scheda arriva — nell'ordine

1. **Accensione e cancelli di bring-up** — RUNBOOK §0. Verificano che l'XADC legga davvero e che
   il reset del DUT avvenga davvero. Entrambi falliscono in silenzio se non controllati.
2. **C0** — il bus risponde e i registri ritengono (RUNBOOK §1).
3. **C1** — replay bit-esatto dei 99 scenari (RUNBOOK §2). È il cancello che dice se il silicio
   fa la stessa cosa della simulazione.
4. **C2** — anello chiuso, preceduto da PLANT-PAR (RUNBOOK §3).
5. **C3 pre-flight** — `misura_dispersione()`: ~10 letture in una visita, dà l'IQR del multimetro
   e quindi **quante repliche** servono. Senza questo, `repeats` è un numero scelto a occhio e la
   campagna può durare da mezz'ora a due giorni.
6. **C3 campagna** — RUNBOOK §4, con il seme annotato.

Il §5 va fatto **prima** del §6 e richiede solo pochi minuti: è ciò che trasforma «vedremo se è
separabile» in una decisione presa in anticipo.

---

## 2. Stato per filone

| Filone | Stato | Nota |
|---|---|---|
| **A — silicio composto (C0–C3)** | codice completo, provato col mock. **Mai su silicio** | serve la scheda |
| **B — SNN da sola** | driver e mappa registri pronti (`TIER`, 5 registri d'uscita) | serve la scheda |
| **C — plotone** | **P1 e P2 chiusi in software/RTL. P3 su silicio CANCELLATO** | vedi §5 |

---

## 3. Cosa è misurato — e dove

### Bitstream (`results/bitstream_set.json`)

| | LUT | FF | DSP | BRAM | WNS a 40 MHz | uso |
|---|---|---|---|---|---|---|
| `blank` | 0 | 0 | 0 | 0 | — | riferimento: `(x1) − (blank)` isola la logica |
| `x1` | 8 453 | 4 556 | 69 | 1 | **+0,022 ns** | configurazione funzionale |
| `x2` | 16 688 | 8 856 | 138 | 2 | **−1,060 ns** | **solo potenza a riposo** |

- `x1` è **byte-identico** al bitstream di T7b tranne 8 byte fra gli offset 180 e 195 (data e CRC
  dell'header). Non è equivalente: è lo stesso bitstream.
- `x2` costa **meno del doppio** di `x1` (16 688 contro 16 906): interconnessione e reset sono
  condivisi, non duplicati.
- ⚠️ **`x3` non esiste, e non è un'omissione.** Il clock gate è un `BUFGCTRL`, e lo Zynq-7020
  impone che la cascata BUFG→BUFGCTRL sia **adiacente**. Con tre gate sullo stesso BUFG il
  piazzatore fallisce (`rule_cascaded_bufg`, misurato). **Ciò che impedisce di replicare è il gate
  stesso, cioè la funzione da misurare**: l'amplificazione massima è ×2. `CLOCK_DEDICATED_ROUTE
  FALSE`, che Vivado suggerisce, è **escluso**: instraderebbe il clock sulla logica generale
  cambiando proprio la potenza della rete di clock che va misurata.
- ⚠️ `x2` non chiude i tempi (94 endpoint su 15 549, cammino DEC→IIDM, lo stesso collo già noto da
  T7b). Va usato **solo** per la potenza a riposo, dove nessun dato commuta e quindi nessuna
  violazione di setup si verifica. **Mai** per C1/C2.

### Risorse del plotone (`results/P3_resources.json`)

Con place & route **veri**, non con un conteggio: **4 istanze si instradano, 5 no.** Il conteggio
LUT da solo diceva 5 e **sopravvalutava** — a 5 le LUT «entrano» ma il piazzatore fallisce, perché
una slice ha 4 LUT e 8 FF e il packing è limitato dai control set (Vivado: «6040 slice disponibili,
le non piazzate ne richiedono 7964»).

### P1 — plotone in software (`results/p1.json`)

88 scenari perturbati; 11 `static_target` esclusi dalla stabilità perché il leader ha velocità
costante e la string stability è un **rapporto** con quel denominatore.

| N | mediana head-to-tail | p95 | string-stable | collisioni |
|---|---|---|---|---|
| 2 | 1,037 | 1,313 | 35/88 | 3/99 |
| 4 | 1,108 | 1,621 | 30/88 | 3/99 |
| 8 | 1,355 | 2,520 | 23/88 | 3/99 |
| 16 | 1,458 | 6,974 | 28/88 | 3/99 |

**Ogni collisione misurata è un `aggressive_cut_in`** (`results/p1_collisioni_per_tipo.json`), e
quella manovra porta il gap a 6,3 m di colpo: è un'emergenza per costruzione, collidere lì non è un
fallimento del controllore.

**Il canale V2X non crea modalità di guasto nuove: allarga quella che già c'è.** Senza latenza il
taglio aggressivo cede solo in autostrada (3 casi); con 300 ms cede a tutte le velocità (10 su 11).
PDR e Gilbert non spostano nulla.

⚠️ Il conteggio degli stabili **non è monotono** in N. Non è rumore: al crescere di N la fascia
attorno a 1 si svuota e la massa si polarizza. Il conteggio da solo è una statistica che **nasconde
il fenomeno**; il grafico della distribuzione lo mostra.

### P2 — plotone in RTL (`results/p2_exact.json`, `p2_platoon_par.json`)

- **PLANT-PAR**: 844 800 confronti, **bit-esatto**.
- **P2-EXACT**: 211 200 confronti su 88 scenari a N=4, **bit-esatto**.

La decomposizione è **non circolare** per costruzione: PLANT-PAR non usa il DUT, P2-EXACT non usa
la pianta del PS. Nessuno dei due può essere verde perché confronta una cosa con sé stessa.

### Costo della quantizzazione (`results/p2_costo_quantizzazione.json`)

Scarto di picco per scenario, RTL (`accel` a 1/256) contro il riferimento float32:

| campo | mediana | p95 | massimo |
|---|---|---|---|
| a (m/s²) | 0,559 | 1,445 | 1,759 |
| v (m/s) | 0,208 | 0,486 | 0,615 |
| gap (m) | 0,534 | 1,084 | 1,149 |

**Collisioni identiche: 3 e 3.** La differenza parte sotto l'LSB, cresce nei primi ~100
control-step e **si stabilizza**: l'anello amplifica l'errore di quantizzazione fino a un livello
limitato, non lo fa scappare. L'esito di sicurezza non cambia.

> Verifica incrociata: quelle 3 collisioni sono le stesse 3 di `p1.json` a N=4. Due catene diverse
> (Python e RTL) sullo stesso perimetro danno lo stesso numero.

---

## 4. Cosa manca

### Richiede la scheda — tutto qui

C0, C1, C2, C3 e il filone B. Il codice c'è ed è collaudato contro il mock; non è mai girato su
silicio.

### Non richiede la scheda — nulla di bloccante

| Cosa | Stato |
|---|---|
| Generatori versionati di `p1_canale.json` e `p1_collisioni_per_tipo.json` | ⚠️ **mancanti** — vedi §7 |
| Parser seriale del multimetro | **chiuso**, vedi §5 |

---

## 5. Decisioni prese — e perché

Queste non vanno rimesse in discussione senza un fatto nuovo. Sono costate tempo una volta.

### Il plotone su hardware è **cancellato**

N istanze su una scheda **simulano** un plotone, e le risorse limitano a 4 — troppo corto per
essere mesoscopico. È un comportamento che si simula ugualmente in software, con meno difficoltà e
senza il vincolo delle 4 istanze. Restano P1 (software) e P2 (RTL), che sono chiusi.

### L'amplificazione massima è ×2, non ×3

Non è una scelta: è il `BUFGCTRL` del clock gate che limita la propria replicazione (§3). È anche
un **risultato**, non solo un limite del banco: un sistema reale con più acceleratori gatati sullo
stesso clock incontrerebbe lo stesso muro.

### `x2` resta a 40 MHz nonostante WNS −1,060

Deciso esplicitamente. `x2` serve **solo** alla potenza a riposo, dove nessun dato commuta: nessuna
violazione di setup si verifica, e la potenza della rete di clock non dipende dallo slack sui
percorsi dati. Abbassare la frequenza avrebbe cambiato proprio la grandezza da misurare.

### Nessun canale dati verso il PC per il multimetro — **chiuso**

Indagato il 2026-08-03 ed esaurito: cavo in dotazione, **cavo dati certo**, porte USB diverse,
scollega/ricollega con rilevatore attivo. Mai un'enumerazione, zero porte COM, nessun dispositivo
in errore. Il rilevatore **non** è in dubbio — nella stessa sessione ha registrato eventi reali (un
dongle sparito e ritornato, 158 → 156 → 159 dispositivi). Il manuale contiene **solo** la frase
«Communicate with the computer and charge the battery through the TYPE-C data cable»: nessuna
procedura, nessun software, nessuna modalità.

L'acquisizione è **`PromptDMM`** — l'operatore trascrive quando il runner chiede. Va bene così:
anche un canale funzionante andava poi verificato per un requisito che nessuna fonte gli
attribuisce, cioè la lettura **live nell'istante richiesto** invece dell'esportazione di
registrazioni salvate.

⚠️ Cambia il **dimensionamento**, non il metodo: ogni replica costa un'attesa di equilibrio
termico. Vedi la tabella delle repliche nel RUNBOOK §4.

### La separabilità si decide sull'**errore standard**, non sulla dispersione

Una prima versione dichiarava separabile una differenza solo se superava il doppio dell'**IQR**,
cioè la dispersione di una **singola lettura**. Quell'incertezza non scende con `n`: le repliche
non servivano a niente, e il guadagno atteso del gating (~7 mW = 1,4 mA su un fondo di ~400)
sarebbe stato dichiarato «non separabile» con **qualunque** numero di letture — un limite
dell'aritmetica spacciato per un limite dello strumento.

Il numero riportato è la **mediana**, quindi decide il suo errore standard
(≈ IQR/1,349 × 1,253 / √n). La dispersione resta riportata accanto: serve a dimensionare `n`.

⚠️ Ciò che **licenzia** il √n è l'ordine **sorteggiato** — solo letture scambiabili convergono. Se
un giorno il sorteggio venisse tolto, questa formula va tolta con lui. Sta scritto accanto al
codice.

---

## 6. Trappole già pagate

Ognuna è costata tempo o una conclusione sbagliata. Sono elencate perché il modo di sbagliare si
ripete, non il singolo errore.

| Trappola | Cosa succedeva | Come è stata chiusa |
|---|---|---|
| **`done` sempre alto nel mock** | commit (scrittura) e done (lettura) condividevano il bit 0 → **ogni cancello di Fase C sarebbe stato verde** | percorsi separati, verificati contro `snniidm_axi_lite.v:196/174/135/139` |
| **`simulate_platoon` non applicava il `cut_in`** | 33 scenari su 99 vedevano un leader che si ferma istantaneamente senza il gap compensativo. Il titolo di P1 era **rovesciato** sui 55 ben rappresentati | corretto in `utils/platoon_eval.py`; artefatti pre-correzione rigenerati o ritirati |
| **`nbconvert --execute` esce 0 senza eseguire nulla** | zeromq rotto su questa postazione: falliva anche `print(1+1)`, e un cancello ancorato all'exit code era **verde per costruzione** | `check_notebook.py` guarda l'**artefatto**, non l'exit code |
| **XADC letto per indirizzo assoluto** | `MMIO.read` vuole un **offset**: si leggeva fuori finestra, e 0 grezzo dà **−273,15 °C** — un numero che nessuno guarda | offset relativi + `verifica_plausibile()` con limiti fisici |
| **Reset del DUT dato per scontato** | non esiste un bit software: solo ri-scaricando il bitstream. Un reset mancato dà scenari che partono dallo stato del precedente | `reset_dut()` **controlla** `done_lat` 1 → 0 |
| **LUT usate come prova di deployabilità** | il conteggio diceva 5 istanze, il piazzatore ne instrada 4 | misura con place & route veri |
| **Conteggio degli stabili non monotono** | sembrava rumore; è il fenomeno | si guarda la **distribuzione**, non il conteggio |
| **`git add` su un file gitignored** | abortiva l'intera catena e **il commit non avveniva in silenzio** | `!FaseC/results/*.log` in `.gitignore` |
| **Sostituzione di stringa che non combacia** | fallisce **in silenzio**: è successo tre volte in una sessione, e una volta ha lasciato un test che chiedeva *meno* repliche di quelle già fatte | usare `Edit` ancorato, e **rieseguire** — `py_compile` non basta |
| **Tabella scritta a mano nel RUNBOOK** | divergeva dalla formula; due righe erano già sbagliate (un `4` che veniva dal ciclo di prova, non dalla matematica) | generata da `repliche_necessarie()`, e un test la ricontrolla riga per riga |
| **Artefatti stantii che sembrano vivi** | due artefatti precedevano la correzione del `cut_in` e **contraddicevano** quelli nuovi | rigenerato uno, ritirato l'altro; il confronto si fa sui **timestamp di provenienza** contro la data della correzione |
| **I confini non erano provati** | l'analisi di mutazione ha trovato che `<=` → `<` su bande, domini e soglia di collisione **non faceva fallire nulla**: la suite provava il comportamento, quasi mai il bordo | 18 prove al confine; `mutazioni.py` rende la verifica rilanciabile |

---

## 7. Debiti noti

Onestà sullo stato, non un elenco di desideri.

1. **Generatori non versionati.** `results/p1_canale.json` e `results/p1_collisioni_per_tipo.json`
   sono stati prodotti da script ad hoc non committati. Gli artefatti hanno la provenienza e i
   numeri, ma **non si rilanciano da uno script**. Chi li deve rifare, li deve riscrivere.
   `phase_c/platoon.py` contiene già `run_channel_sweep` e `partiziona_scenari`, che sono i mattoni.
2. **`p1_canale_collisioni.json` è stato ritirato** (2026-08-03): precedeva la correzione del
   `cut_in` e concludeva `cut_out`/highway, mentre il dato post-correzione dice `aggressive_cut_in`.
   Un artefatto sbagliato che sembra vivo è peggio di un artefatto assente. La versione precedente
   resta nella storia git.
3. **Il notebook non è verificabile a livello di kernel** su questa postazione (zeromq). Il
   controllo `CODICE` di `check_notebook.py` — che esegue le celle di codice in un processo pulito
   — resta la prova di riproducibilità. Vedi RUNBOOK §8.

---

## 8. Controlli di sicurezza — come si rifanno

Oltre alla suite, tre verifiche che **non** sono test e vanno rilanciate a mano quando si tocca
qualcosa di sostanziale.

```bash
cd FaseC && python mutazioni.py
```

**Analisi di mutazione** (~12 minuti). Rompe il codice in un punto alla volta e controlla che i
test se ne accorgano. Una mutazione sopravvissuta è un comportamento che nessun test difende.
**Prima passata** (12 moduli, 92 mutazioni): **31 sopravvissute**, e non sparse — quasi tutte
**condizioni al confine**. Aggiunte 18 prove al bordo.

**Seconda passata**, sui 29 punti che la prima non aveva mai toccato — `cli.py`, `driver.py`,
`golden.py`, `platoon.py`, `plots.py` non erano nella mappa, e `c1_functional` era campionato:
altre **20 sopravvissute**. Fra queste, tre che cambiavano un risultato senza segnalarlo
(`gating=True` del driver, la soglia della partizione, la chiave dello scenario nell'artefatto) e
l'intero smistamento degli stadi in `cli.py`, invisibile perché senza scheda **ogni** rotta
solleva `SchedaAssente`.

Restano vive per costruzione le mutazioni **equivalenti** (contatori nelle stringhe di
avanzamento, opzioni grafiche, rami di diagnosi che cambiano il messaggio ma non l'esito): non
sono buchi.

⚠️ La seconda passata ha fatto emergere un difetto **introdotto in questa stessa sessione**:
`--scenari K` veniva tradotto in indici base 1 per tutti gli stadi, ma `p1` indicizza il dataset
(un array, **base 0**) mentre `c*` indicizza i file `axi_stim_<i>.mem` (**base 1**). Il perimetro
di P1 risultava spostato di uno — primo scenario saltato, uno in più in coda — in silenzio. Le due
convenzioni sono reali; è la traduzione che deve cambiare, e ora un test la difende in entrambi
i versi.

```bash
cd FaseC && python -m pytest tests/test_documentazione.py -q
```

**Coerenza dei documenti**: le tabelle di STATO.md sono confrontate riga per riga con gli
artefatti, e il conteggio dei test con quelli che esistono davvero.

**Staleness degli artefatti**: confrontare il `prov.timestamp` di ogni artefatto con la data
dell'ultimo commit del codice da cui dipende. È così che sono emersi i due artefatti
pre-correzione del `cut_in` (§6). Non è automatizzato: la mappa artefatto → dipendenze non esiste
in forma eseguibile, ed è un debito noto (§7).

---

## 9. Come rilanciare tutto

```bash
cd FaseC && python -m pytest -q
```

230 test. Nessuno richiede la scheda; quelli che la richiederebbero verificano invece che il
codice **dichiari** che serve, invece di restituire numeri dal mock come se fossero misure.

```bash
cd FaseC && ./run_phase_c.sh list
```

Elenca gli stadi e dice quali girano senza scheda. `./run_phase_c.sh parity` confronta l'artefatto
prodotto dallo script con quello prodotto dal notebook: devono coincidere a meno dei campi
volatili (orario, nome della facciata, directory). **La sorgente e la firma del bitstream non sono
volatili**: un numero prodotto col mock e uno prodotto sul silicio non sono lo stesso risultato,
nemmeno quando coincidono.
