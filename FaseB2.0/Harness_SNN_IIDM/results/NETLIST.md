# T7b · NETLIST post-place&route — la netlist implementata riproduce il blocco

> Rigenerabile: `bash hw/run_netlist.sh`; questa tabella: `python hw/gen_netlist_report.py`, che **parsa**
> `results/netlist_func.log`. Nessuna cifra trascritta dalla console.
> La **fase 1** (impl OOC + export) e' stata **saltata** dal cancello di provenienza sulla firma md5 dei
> sorgenti: la netlist era gia' quella giusta. `NETLIST_DRYRUN=1` mostra la decisione senza lanciare Vivado.

## Perimetro, dichiarato

Si simula la netlist **funcsim** (post-place&route, primitive UNISIM) di `snniidm_axi_lite` implementato
**out-of-context**, col banco AXI gia' validato in Task 2 e contro lo **stesso golden**.

⚠️ **funcsim e NON timesim**, per un motivo misurato in T6b: la sim di timing con SDF non produsse
risultati validi per una configurazione del banco mai risolta. La domanda a cui questo passo risponde —
*la netlist implementata e' logicamente equivalente all'RTL?* — e' coperta dalla funcsim; la **firma del
timing spetta all'STA** (`SWEEP_FCLK.md`: WNS +0,022 ns @40 MHz), non alla simulazione. E' anche la
prassi industriale corrente.

⚠️ In funcsim le primitive sono a **ritardo zero**: il periodo di clock non prova nulla sul timing. E'
allineato al punto deployabile solo per coerenza.

## Esito sul sottoinsieme DICHIARATO

| Scenario | Ruolo | Passi | Disallineamenti | Durata |
|---|---|---|---|---|
| 1 | nominale (primo del dataset) | 600 | **0** | 16 m 31 s *(include compilazione ed elaborazione)* |
| 4 | nominale, altra combinazione regime/cut-in | 600 | **0** | 15 m 43 s |
| 9 | **COLLIDE** — serie troncata a 307 | 307 | **0** | 10 m 15 s |
| **totale** | | **1507** | **0** | **42 m 29 s** |

Lo scenario **9 collide**: e' quello che aveva scoperto il difetto di `axi_len` nella cosim
comportamentale (il banco leggeva oltre la fine del golden sugli scenari piu' corti). Includerlo e' il
punto del sottoinsieme, non un dettaglio.

## Il totale e' auto-verificante

**600 + 600 + 307 = 1507** confronti, **dichiarati PRIMA della run**; il log riporta `nMismatch=0 n=1507 nscen=3`.
Il totale torna. Se non fosse tornato, `nMismatch=0` non sarebbe stato credibile: un banco che confronta
meno passi del previsto produce zero disallineamenti proprio perche' **non guarda**.

## Costo — MISURATO su T7b, non piu' ereditato

| Scenario | s / control-step |
|---|---|
| 4 | 1.57 |
| 9 | 2.00 |

Dispersione 1.57–2.00 s: attesa, il simulatore e' a eventi e scenari con commutazione diversa costano
diversamente.

**Penalizzazione gate-level = 44×** rispetto alla cosim comportamentale sullo STESSO banco e sugli STESSI
scenari (0.0390 s/passo, da `COSIM_AXI.md`: 58522 confronti x 2 modalita' in 76 min). T6b aveva misurato ~29×
sul proprio progetto: qui il numero e' **misurato su questo**, non ereditato.

⇒ i **99 scenari** completi costerebbero **~28 ore**. E' la ragione per cui N=3 e' un **cancello di
conferma su N dichiarato**, non la base di una metrica.

⚠️ **La stima a priori era ~80 minuti, il misurato e' 42.** Veniva da T6b scalata per il rapporto dei clock
per passo (560/371): **pessimistica di circa 2×**. Una stima scalata da un altro progetto e' un ordine di
grandezza, non una previsione.

## Cosa e' provato, e cosa no

| Domanda | Risposta | Da cosa |
|---|---|---|
| La netlist piazzata e instradata calcola come il blocco? | **si**, 0/1507 | questa run |
| ...su tutti i 99 scenari? | **non provato** — N=3 dichiarato | costo (~28 h) |
| Il timing chiude? | **si** a 40 MHz | STA, non simulazione (`SWEEP_FCLK.md`) |
| L'integrazione con PS7 / protocol converter? | STA di sistema; board in Fase C | perimetro OOC, dichiarato sopra |
