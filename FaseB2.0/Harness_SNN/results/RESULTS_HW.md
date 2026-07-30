# Harness_SNN — risultati HARDWARE (Fase B2.0 · T6b)

> ⚠️ **Documento IN COSTRUZIONE.** Completi: **M1** · **M2** (NETLIST-PAR funzionale verde; sim di timing non riuscita — §M2.3).
> Completo anche **M3** (misure valide; composizione energetica NON validata — §M3.4). Da fare: M4 (bitstream) · M5 (entry-point + doc).
> Riesecuzione dei probe: `bash hw/run_probes_t6b.sh` → `PROBES_T6B.md`.

**DUT:** `Donatello_Tier` @ TIER=BALANCED, NFRAC=13 — **lo stesso artefatto VHDL** validato bit-exact in T6a
(`matlab/hdlsrc_donatello_tier/rtlgen_mdl/`), avvolto nel wrapper AXI4-Lite `hw/tier_axi_lite.v`.
**Golden:** la **stessa cache** di T6a (`matlab/tier_golden_cache.m`) ⇒ prova e riferimento sugli identici dati.

---

## M1 — Wrapper AXI4-Lite e cosim funzionale ✅

### Cancelli

| Cancello | Perimetro | Esito |
|---|---|---|
| **AXI-COSIM** — i 5 parametri letti dal PS via AXI == blocco | **60 traiettorie × 1000 control-step** | **nMismatch = 0 / 300 000** |
| **AXI-COSIM con clock gating attivo** (configurazione di **deployment**) | idem | **nMismatch = 0 / 300 000** |
| **GATE-EQ** — il gating non altera un solo bit | 50 control-step, OFF vs ON | **identici** |
| **Sensibilità** — 1 LSB corrotto sul golden (`033737→033736`) | 50 control-step | **nMismatch = 1** (il cancello vede) |
| **SYNC** — un commit ⇒ una inferenza | 60 × 1000 | **59 797 / 60 000** (scarto spiegato ↓) |

Runtime: golden 36 s (cache) · full-60 gating OFF **46 min** · full-60 gating ON **51 min**.
Log: `results/axi_cosim_full60.log` (gitignorato, rigenerabile).

### Scarto SYNC — verificato, non giustificato a parole

`59 797 = 60 000 − 203`. Misurato sul dataset: **esattamente 203** control-step hanno i 4 ingressi
**bit-identici** al precedente (quantizzati a `fixdt(1,32,20)`), concentrati in **6/60** traiettorie di tipo
**stop&go** (peggiore: traj 2 `mixed/stop_and_go`, 79 ripetizioni). Il Tier è **edge-triggered**: ingressi
identici ⇒ nessun fronte ⇒ nessuna nuova inferenza (`HDL_PHASE §3.1.4`). **Non è un difetto**: i parametri
tenuti restano quelli corretti — e lo prova `nMismatch = 0`, perché un commit realmente perso darebbe valori
stantii che il confronto bit-exact rileverebbe.
➡️ **Rilevanza per T7**: nell'anello chiuso un'inferenza non rieseguita si propaga; da tenere presente.

### Progetto del wrapper — ogni scelta da un fatto misurato

| Scelta | Perché | Fonte |
|---|---|---|
| `done` da **contatore, attesa 370 clk** | `ce_out` è un **clock-enable sempre alto**, non un done | probe **P1** |
| attesa **370** = 365 misurati + 6 margine | latchare a 365 cattura il valore **precedente** (non-blocking sul fronte in cui l'uscita cambia) | probe di timing: commit@446→uscita@811, commit@852→@1217 |
| **buffer + commit sincrono** | il Tier è edge-triggered: ingressi scritti uno alla volta lancerebbero inferenze su dati **parziali** | `HDL_PHASE §9` + cancello SYNC |
| **Tier in reset fino al primo commit** | senza, all'uscita dal reset parte un'inferenza **spuria** a ingressi nulli che avanza lo stato e disallinea tutto | misurato: uscita a cyc 379 con reset a 16 (16+364) |
| **clock gating via bit di registro** (non parametro di compilazione) | gatato e non gatato sono **la stessa netlist** ⇒ il confronto di potenza isola l'effetto del gating, non differenze di sintesi | scelta di metodo |

### Difetti trovati e corretti in M1 (tutti nell'harness, nessuno nel DUT)

1. **`glbl` non compilato** — il modello di simulazione di `BUFGCE` lo referenzia: serve `xvlog` di
   `<vivado>/data/verilog/src/glbl.v` e `xelab … glbl -L unisims_ver`.
2. **Metrica SYNC sbagliata** — contava i cambi di `v0` (stima lenta: control-step consecutivi possono ripetere
   lo stesso valore ⇒ **sottoconta**). Sostituita col conteggio dei **fronti del bus d'ingresso committed**.
3. **Race sulla lettura AXI** — campionare `RDATA` subito dopo `wait(RVALID)` restituisce il dato
   dell'indirizzo **precedente** (mux combinatorio non ancora aggiornato): campionare sul **negedge**.
4. **Inferenza spuria al reset** (vedi tabella sopra).

I difetti 3 e 4 erano **silenziosi**: producevano parametri *plausibili*, numericamente vicini ai corretti.
Li ha presi il confronto **bit-exact contro un golden indipendente**, non un'ispezione dei valori.

---

## M2 — Sistema, clock e risorse reali ✅

**Sistema implementato:** Zynq **PS7** (board preset `www.digilentinc.com:pynq-z1:part0:1.0`) + `tier_axi_lite`
(module reference) + AXI SmartConnect su `M_AXI_GP0`. Riesecuzione: `bash hw/run_impl_sweep.sh "<lista FCLK>"`.
Il probe `hw/probe_bd.tcl` ha verificato **prima** di costruire che `S_AXI` fosse riconosciuta come interfaccia
(`/tier0/S_AXI`) e che `apply_bd_automation` + `validate_bd_design` funzionassero: nessun `ipx::package_project`.

### M2.1 — Sweep FCLK (6 punti, `-jobs 6` fisso per determinismo)

| FCLK [MHz] | T [ns] | **WNS [ns]** | ritardo ottenuto [ns] | LUT | FF | DSP | BRAM |
|---|---|---|---|---|---|---|---|
| 30 | 33,333 | **+10,892** | 22,441 | 4474 | 3199 | 52 | 1 |
| 40 | 25,000 | **+2,626** | 22,374 | 4472 | 3199 | 52 | 1 |
| 50 | 20,000 | **+0,335** | 19,665 | 4476 | 3199 | 52 | 1 |
| **52** | 19,231 | **+0,358** | 18,873 | **4473** | **3199** | **52** | **1** |
| 55 | 18,182 | −0,345 | 18,527 | 4524 | 3199 | 52 | 1 |
| 60 | 16,667 | −0,414 | **17,081** | 4613 | 3199 | 52 | 1 |

**Due numeri distinti, come da metodo dello slack minimo:**
- **FCLK deployato = 52 MHz** — il più alto **fra i testati** che chiude (WNS **+0,358 ns**). Il confine sta fra
  52 e 55 (che manca di 0,345 ns); non è stato ristretto oltre perché privo di valore informativo (§M2.2).
- **Limite del datapath = 58,6 MHz** — da `1/(ritardo minimo)` = `1/17,081 ns`, ottenuto **stringendo** il vincolo.
  Si legge **stringendo, non al crossover WNS=0**: a 30 e 40 MHz il tool si ferma a ~22,4 ns perché ha margine e
  non ottimizza oltre — l'effetto è visibile nella colonna "ritardo ottenuto".

⚠️ Entrambi sono **io-timed di sistema** (Tier + AXI + PS): **non confrontabili** né con i 77,9 MHz OOC reg-reg
dell'`ACC_IIDM_M` né con gli 8 MHz del bitstream della Fase B.

**Area quasi insensibile al vincolo:** +3,1 % di LUT da 40 a 60 MHz (4472 → 4613), FF/DSP/BRAM invariati.
**BRAM = 1 tile catturata** — è il dato che i run OOC precedenti non davano.

### M2.2 — Latenza, margine e duty cycle (all'FCLK deployato)

| Grandezza | Valore |
|---|---|
| Latenza di un'inferenza | 364 clk (Tier) · **371 clk** attesi dal wrapper |
| Tempo di inferenza @52 MHz | **7,13 µs** |
| Control-step richiesto | **0,1 s** (l'unico requisito temporale vero) |
| **Margine** | **≈ 14 000 ×** |
| **Duty cycle** | **≈ 0,0071 %** → il design è fermo per il 99,993 % del tempo |

➡️ **Il clock massimo è una caratterizzazione, non una scelta di deployment ottimale**: a 52 MHz il margine è già
~14 000×, quindi salire in frequenza non porta alcun beneficio funzionale mentre alza la potenza dinamica
(soprattutto quella della fase **idle**, se il clock non è gatato). Quanto convenga scendere lo dirà M3.

### M2.3 — NETLIST-PAR ✅ (funzionale) · sim di timing non riuscita

**Cosa prova:** che la netlist **piazzata e instradata** riproduca l'RTL — cioè che sintesi e place&route non
abbiano alterato il comportamento, e che il design parta da uno stato definito (X-propagation / GSR / init BRAM),
cose che l'RTL nasconde perché i suoi modelli comportamentali inizializzano a zero.

**Perimetro** (dichiarato fin dal progetto, non a posteriori): implementazione **OOC di `tier_axi_lite`+Tier**,
*non* dell'intero block design — simulare il BD post-impl richiederebbe il BFM/VIP del PS7. L'integrazione con
SmartConnect/PS7 resta coperta dall'**STA di sistema** (§M2.1) e, in Fase C, dalla board fisica.

| Verifica | Perimetro | Esito |
|---|---|---|
| **NETLIST-PAR funzionale** — netlist post-route (`funcsim`, primitive UNISIM) == blocco | **3 traiettorie × 1000 control-step** = 15 000 confronti, **gating ON** (deployment) | **nMismatch = 0 / 15 000** |
| **Firma del timing** | sistema completo @52 MHz | **STA**: WNS **+0,358 ns** (§M2.1) · OOC: **+0,355 ns** |
| **Sim di timing** (netlist + SDF) | — | ❌ **non riuscita** (§sotto) |

**N = 3 traiettorie, deciso dal costo MISURATO:** ~22 min/traiettoria (gate-level ≈ **15×** più lento del
comportamentale) ⇒ le 60 costerebbero **~12 ore**. Le 15 000 comparazioni sono un **cancello di conferma** con N
dichiarato; l'**esaustività** resta della cosim comportamentale su **60/60** (300 000 confronti, §M1).
Riesecuzione: `bash hw/run_netlist_func.sh <ROOT> <NETLISTDIR> <HWDIR> 1000 3 1 9.615`.

**Sim di timing (SDF): non riuscita, causa nel banco — non nel design.**
La netlist timesim restituisce **tutti i parametri a `000000`** (zero esatto, non `X` né valori corrotti), identico
con gating ON e OFF, al clock corretto. La **funcsim sulla stessa netlist implementata è verde**: quindi
- ✅ **escluso** un problema strutturale (X-propagation / GSR / init BRAM): se lo stato iniziale fosse indefinito,
  la funcsim avrebbe fallito allo stesso modo;
- ✅ **escluso** il BUFGCE (gating ON e OFF identici) e il clock (parametrizzato e corretto a 9,615 ns);
- ⇒ resta una **configurazione del banco di timing** (annotazione SDF / pulse handling / sequenza di reset con GSR
  in presenza di ritardi). Da indagare a sé; non blocca T6b.

**Perché questo non lascia un buco nella validazione:** la **firma del timing spetta all'STA**, non alla
simulazione — ed è pulita (+0,358 ns a 52 MHz). L'equivalenza logica della netlist implementata è provata dalla
funcsim. Con STA pulita la timing-sim si omette comunemente anche nella prassi industriale, proprio perché costosa
e non autoritativa in materia di timing. La differenza rispetto a "cancello rosso non spiegato" è che qui **si sa
cosa è escluso e cosa resta**.

---

## M3 — Studio energetico e clock gating ⚠️ (misure valide · composizione NON validata)

**Flusso:** SAIF da simulazione **post-implementation FUNZIONALE** (la timing-sim non è utilizzabile, §M2.3) sul
design **OOC `tier_axi_lite`+Tier** — il PS7 è hard-IP e il suo consumo non appartiene al nostro deployment.
⚠️ **Caveat dichiarato:** con SAIF funzionale i **glitch non sono catturati** ⇒ la dinamica è **leggermente
sottostimata**. Tutte le misure hanno **Confidence = High**. `-debug typical` è obbligatorio per il SAIF.
Riesecuzione: `hw/gen_power_workloads.m` → `hw/run_saif_active.sh` / `hw/run_saif_idle.sh` → `hw/power_report.tcl`.

### M3.1 — Finestra idle: convergenza verificata (sostituisce un numero scelto a naso)

| Finestra | total | dynamic | static | Confidence |
|---|---|---|---|---|
| 200 cicli | 0,111 W | 0,008 W | 0,103 W | High |
| 1000 cicli | 0,111 W | 0,008 W | 0,103 W | High |
| 5000 cicli | 0,111 W | 0,008 W | 0,103 W | High |

Valori **identici** ⇒ l'idle è **stazionario** e la finestra di **200 cicli** basta. Il probe ha anche **verificato la
premessa**: il design *è* davvero fermo in idle (se avesse avuto FSM/contatori attivi, il valore non si sarebbe
stabilizzato) — non era garantito, ed è la condizione perché il clock gating abbia qualcosa da spegnere.

### M3.2 — Fase attiva: 9 workload reali + 1 sintetico (duty ~100%)

Un workload per **combinazione scenario×profilo** (sono **9**), 50 control-step ciascuno, **gating ON**
(configurazione di deployment). Ogni run vale anche come conferma funzionale: **`nMismatch = 0 / 250`** su tutti e 9.

| Workload | Dinamica [W] | | Workload | Dinamica [W] |
|---|---|---|---|---|
| wl1 | 0,042 | | wl6 `mixed\|sinusoidal` (traj 8) | 0,043 |
| wl2 | 0,045 | | wl7 `truck\|constant` (traj 9) | 0,043 |
| wl3 | 0,043 | | wl8 `highway\|constant` (traj 15) | 0,044 |
| wl4 | 0,044 | | wl9 `urban\|stop_and_go` (traj 39) | 0,042 |
| wl5 | 0,044 | | **wl10 worst sintetico** | **0,041** |

**Dispersione fra i 9 reali: 0,042–0,045 W (≈7%)** ⇒ la potenza attiva è **poco sensibile al regime di guida**.
Breakdown tipico (wl1): Clocks 0,008 · Slice Logic 0,009 · Signals 0,012 · BRAM 0,002 · DSP 0,010.

⚠️ **Il "worst" sintetico NON è un limite superiore: è il più BASSO di tutti (0,041 W).** Il controllo che avevo
predisposto per validarlo **è fallito**: gli ingressi ad alto firing scelti (gap 2 m, `dv` −15, `v` 35, con
alternanza per garantire il fronte) **non** massimizzano la commutazione. **Non va usato come bound**; il vero
massimo osservato è un workload reale (wl2, 0,045 W). Trovare il regime peggiore richiederebbe uno studio a sé.

### M3.3 — Clock gating: FUNZIONA (misurato), ma il guadagno non è quantificabile con questo flusso

| Livello di osservazione | Esito |
|---|---|
| `report_power` (sommario) | idle gatata **0,008 W** = idle non gatata **0,008 W** → *sembra* «il gating non serve» |
| **SAIF, conteggi di commutazione** | `clk_tier`: **TC 400 → TC 0**, T1 → 0 (tenuto basso per tutta la finestra) |
| `gate_mode` nel SAIF | g0 basso · g1 alto ⇒ il bit di registro comanda correttamente |

➡️ **Il clock del Tier si ferma completamente quando il gating è attivo — misurato nell'artefatto.**
La causa dell'apparente non-effetto è un **limite dello strumento**: `report_power` deriva la potenza dei net di
**clock dal VINCOLO di frequenza** (`aclk` 19,2 ns), non dall'attività del SAIF. Verificato anche in negativo:
imporre `set_switching_activity -toggle_rate 0` sugli 8 net `clk_tier` **non cambia il risultato**
(`0,008 → 0,008`, `Clocks 0,007 → 0,007`).

**Conseguenza onesta:** il gating **è implementato e agisce**, ma **il suo guadagno in watt non è misurabile con
questo flusso**. Elementi di contesto (misurati): l'idle dinamica è **8 mW** di cui **7 mW di clock tree**, e il
Tier ospita la quasi totalità dei registri (≈2 900 dei 3 199 FF), tutti i 52 DSP e l'unica BRAM ⇒ la quota
gatabile è la parte dominante di quei 7 mW. Un numero preciso richiede un flusso diverso (es. misura su board in
Fase C, o modello di potenza che accetti attività per-net sui clock). **Nessuna stima viene qui spacciata per misura.**

### M3.4 — Cross-check della composizione: ❌ FALLITO (e ha impedito di pubblicare numeri sbagliati)

Simulati 5 control-step a **duty ridotto reale** (371 clk attivi + **10 000 clk di idle** ciascuno ⇒ duty **3,85 %**),
SAIF su tutta la finestra, e confronto fra energia **misurata** e **composta** dalle P misurate separatamente:

```
P_composta = 0,0435 · 0,0385 + 0,008 · 0,9615 ≈ 0,0094 W
P_MISURATA = 0,015 W                            ⇒ la composizione SOTTOSTIMA di ~1,6×
```

| Componente | idle | attiva | duty-mix **misurata** | composizione lineare |
|---|---|---|---|---|
| Clocks | 0,007 | 0,008 | 0,007 | ~0,007 ✅ |
| Slice Logic | <0,001 | 0,009 | 0,001 | ~0,0005 |
| Signals | <0,001 | 0,012 | 0,002 | ~0,0005 ⚠️ |
| BRAM | 0,001 | 0,002 | 0,001 | ~0,001 ✅ |
| **DSPs** | <0,001 | 0,010 | **0,004** | **~0,0005** ❌ (8×) |
| **Dinamica** | **0,008** | **0,042** | **0,015** | **0,0094** |

La discrepanza è **localizzata sui DSP**: consumano il 40 % del valore attivo pur essendo attivi il 3,85 % del tempo.
**Ipotesi** (dichiarata come tale, non verificata): il modello di potenza di Vivado dipende anche dalla *static
probability* dei segnali, non solo dal *toggle rate*; in idle gli ingressi dei DSP mantengono gli ultimi valori
calcolati, che nel modello non equivale a "spento" ⇒ la potenza **non compone linearmente** fra fasi.

➡️ **Conseguenza: la composizione lineare è ABBANDONATA.** Era la strada prevista per l'energia al duty reale, e il
suo stesso cancello di verifica l'ha invalidata: senza questo cross-check avrei pubblicato energie (e un guadagno
del gating) basate su una formula sbagliata — numeri plausibili e falsi.
✅ **Risolto in §M3.6 misurando DIRETTAMENTE al duty reale**, senza comporre.

### M3.5 — Cosa resta solido di M3

| Risultato | Natura |
|---|---|
| Potenza attiva per i 9 workload reali: **0,042–0,045 W** (disp. ~7 %), Confidence High | **misurato** |
| Potenza idle (clock libero): **0,008 W**, di cui **7 mW clock tree** | **misurato** |
| Statica del device: **0,103 W** — pavimento del chip, **tenuta separata** dal costo del design | **misurato** |
| Il clock gating **ferma completamente** il clock del Tier (`TC 400→0`) | **misurato (SAIF)** |
| Guadagno del gating: **stima 2–4×** sulla dinamica, da validare in Fase C | **stima dichiarata** (§M3.6) |
| **Energia dinamica per control-step: 0,9 mJ** (duty reale, misurata direttamente) | **misurato** (§M3.6) |
| Il worst sintetico come limite superiore | ❌ **invalidato** (è il più basso) |

### M3.6 — ✅ Energia al DUTY REALE: misurata direttamente (niente composizione)

Poiché la composizione lineare è invalida (§M3.4), il control-step **reale** è stato **simulato per intero**:
1 control-step = **416 clk attivi + 5 199 584 clk di idle** = 5,2 M cicli = **0,1 s a 52 MHz** ⇒ duty **0,008 %**.
SAIF su tutta la finestra, gating **OFF** (il caso in cui *tutte* le componenti sono modellate correttamente: col
gating il tool non vedrebbe la riduzione del clock, §M3.3, e restituirebbe lo stesso numero fingendo di misurarla).
Riesecuzione: `hw/tb_power_duty.v` con `IDLECYC=5199584` → `hw/power_report.tcl`. Costo reale: **12 min**.

**Serie di convergenza — tre punti, non un valore isolato:**

| duty | cicli di idle | Dinamica [W] | DSPs [W] | Signals [W] |
|---|---|---|---|---|
| 3,85 % | 10 000 | 0,015 | 0,004 | 0,002 |
| 0,37 % | 100 000 | 0,010 | — | — |
| **0,008 % (REALE)** | **5 199 584** | **0,009** | **<0,001** | **<0,001** |
| *idle puro (riferimento)* | — | *0,008* | *<0,001* | *<0,001* |

➡️ **La potenza converge al valore di idle** al ridursi del duty, come fisicamente deve essere: al control-step vero
la fase attiva è il 0,008 % del tempo e la sua quota è trascurabile. **L'anomalia sui DSP di §M3.4 svanisce**
(0,004 → <0,001): era un effetto **dipendente dal duty**, non un offset fisso — motivo per cui la composizione
lineare sbagliava e la misura diretta no.

**Energia per control-step (misurata, duty reale, gating OFF), Confidence High:**

| Voce | Potenza | Energia per control-step (0,1 s) |
|---|---|---|
| **Dinamica — il costo del NOSTRO design** | **0,009 W** | **≈ 0,9 mJ** |
| di cui clock tree | 0,007 W (78 %) | ≈ 0,7 mJ |
| Statica del device — pavimento del chip | 0,103 W | ≈ 10,3 mJ |
| Totale on-chip | 0,111 W | ≈ 11,1 mJ |

⚠️ Le due voci **non vanno sommate in un unico numero senza dirlo**: la statica è del dispositivo (c'è anche a
design spento), la dinamica è ciò che aggiunge il deployment. La dinamica è l'**8 %** del totale — coerente col
finding della Fase B (statica ~92 %).

**Stima del guadagno del clock gating** (⚠️ **stima**, non misura — il tool non la produce, §M3.3): il **78 %** della
dinamica è clock tree, e il Tier — la parte gatata — ospita ≈2 900 dei 3 199 FF, **tutti** i 52 DSP e l'unica BRAM.
Fermando il suo clock si rimuove la quota dominante di quei 7 mW ⇒ dinamica attesa nell'ordine di **2–4 mW**,
cioè un **fattore ~2–4×** sull'energia dinamica del deployment. **Va verificato in Fase C**, dove la misura è banale
grazie al progetto scelto: il gating è un **bit di registro**, quindi lo **stesso bitstream** consente di leggere la
corrente a riposo con bit=0 e bit=1 e ricavare il risparmio per differenza.

---

## M4 — Bitstream PYNQ-Z1 ✅

Sistema completo (PS7 + `tier_axi_lite` + AXI SmartConnect) all'**FCLK deployabile di 52 MHz**, costruito con la
**stessa procedura** di `build_impl.tcl` ⇒ il design che finisce sul `.bit` è **lo stesso** caratterizzato in M2/M3,
non una variante ricostruita a parte. Riesecuzione:
`vivado -mode batch -source hw/bitstream.tcl -tclargs <SRCDIR> <ROOT> 52 <OUTDIR> 6` — costo **9,5 min**.

| Cancello | Esito |
|---|---|
| **TIMING** sul run che produce il `.bit` | **WNS = +0,358 ns** ⇒ chiude |
| **Determinismo** — stesso WNS dello sweep M2 a 52 MHz | **+0,358 = +0,358** ✅ (con `-jobs 6` fisso) |
| **Artefatti presenti** (`glob` + copia, errore rumoroso se assenti) | `.bit` · `.hwh` · `.xsa` prodotti |
| **Provenienza** nel `.hwh` | `BOARD="www.digilentinc.com:pynq-z1:part0:1.0"` · `DEVICE="7z020"` · `PACKAGE="clg400"` |

**Artefatti** in `FaseB2.0/Harness_SNN/bitstream/` (tracciati in git, come il bitstream della Fase B):

| File | Dimensione | Uso |
|---|---|---|
| `snn_tier_donatello.bit` | 4,05 MB | flash su PYNQ-Z1 |
| `snn_tier_donatello.hwh` | 138 KB | handoff PYNQ (overlay) |
| `snn_tier_donatello.xsa` | 1,15 MB | handoff Vitis/XSCT |
| `timing_bitstream_fclk52.rpt` · `util_bitstream_fclk52.rpt` | — | timing e risorse **del run del bitstream** |

**Pronto per la Fase C.** L'esperimento sul clock gating è immediato e **non richiede un secondo bitstream**: il
gating è un **bit di registro** (`0x10` bit1), quindi si legge la corrente a riposo con bit=0 e poi bit=1 e si
ricava il risparmio **per differenza** — è la misura che qui non è ottenibile (§M3.3).
