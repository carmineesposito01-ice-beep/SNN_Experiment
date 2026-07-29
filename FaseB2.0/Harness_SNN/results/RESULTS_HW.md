# Harness_SNN — risultati HARDWARE (Fase B2.0 · T6b)

> ⚠️ **Documento IN COSTRUZIONE.** Completo: **M1**. Da fare: M2 (block design, FCLK, utilizzo post-route,
> NETLIST-PAR) · M3 (studio energetico + clock gating) · M4 (bitstream) · M5 (entry-point unico + doc).
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
