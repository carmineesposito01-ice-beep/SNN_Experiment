# Harness_SNN — risultati HARDWARE (Fase B2.0 · T6b)

> ⚠️ **Documento IN COSTRUZIONE.** Completi: **M1** · **M2** (tranne NETLIST-PAR, **aperto** — §M2.3).
> Da fare: M3 (studio energetico + clock gating) · M4 (bitstream) · M5 (entry-point unico + doc).
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

## M2 — Sistema, clock e risorse reali ✅ (NETLIST-PAR aperto)

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

### M2.3 — NETLIST-PAR ⚠️ APERTO (non completato)

**Cosa doveva provare:** che la netlist **piazzata e instradata** (con ritardi SDF) riproduca l'RTL, catturando
problemi di inizializzazione e X-propagation che l'RTL nasconde.
**Perimetro previsto** (dichiarato fin dal progetto): implementazione **OOC di `tier_axi_lite`+Tier**, *non*
dell'intero block design — simulare il BD post-impl richiederebbe il BFM/VIP del PS7. L'integrazione con
SmartConnect/PS7 resta coperta dall'**STA di sistema** (§M2.1) e, in Fase C, dalla board fisica.

**Fatto:** implementazione OOC a 52 MHz riuscita (**WNS +0,355 ns**), netlist di timing + SDF esportate
(`write_verilog -mode timesim -sdf_anno true`, 2,8 MB + 12 MB).
**Non riuscito:** la simulazione di timing restituisce **tutti i parametri a `000000`** (non valori errati: zero),
identico con clock gating ON e OFF, al clock corretto di 52 MHz.

**Stato della diagnosi (fatti, non ipotesi):**
- `done` **scatta** e il polling AXI termina ⇒ il commit arriva, il contatore gira, il dominio AXI funziona
  (è sul clock **non** gatato).
- Gating ON e OFF danno lo **stesso** risultato ⇒ il BUFGCE **non** è la causa.
- Le letture sono **zero esatto**, non `X` e non valori plausibili ⇒ compatibile con Tier fermo o tenuto in reset,
  **non** con violazioni di timing sparse (che darebbero valori corrotti, non nulli).
- Il clock era inizialmente sbagliato (TB a 100 MHz su netlist da 52 MHz): **corretto** e parametrizzato
  (`CLKHALF`), ma **non era la causa** — il sintomo è rimasto.

**Prossimo passo diagnostico** (non eseguito): esportare una netlist **`funcsim`** (senza SDF) e rigirare lo stesso
TB. Separa in un colpo **struttura** (X-propagation / GSR / init della BRAM) da **timing**. Non si può ottenere
togliendo il file SDF: `$sdf_annotate` è **incorporato** nella netlist timesim e l'elaborazione fallisce senza di esso.

**Onestà sul verdetto:** l'RTL è bit-exact su **300 000** confronti (M1); qui la stessa logica, implementata, non
produce nulla in simulazione. È **un finding**, non un dettaglio da archiviare — ed è esattamente la classe di
problemi per cui questo cancello esiste. Va indagato a sé, non in coda a una milestone.
