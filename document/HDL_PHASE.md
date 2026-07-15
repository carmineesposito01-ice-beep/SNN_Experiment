# Fase ②-HDL — Metodologia, Stato e Procedura di Ripresa

> **Worktree separato:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulink_Importer`
> **Branch:** `Simulink_Importer` · **Base:** HEAD `9010d3d` (closed_loop_demo)
> `core/` PyTorch **congelato read-only** (letti solo i pesi). MATLAB **R2026a** gira headless
> (`C:\Program Files\MATLAB\R2026a\bin`). **Vivado 2026.1 È INSTALLATO** (aggiornato 2026-07-14):
> `C:\AMDDesignTools\2026.1\Vivado\bin\vivado.bat` — **NON** in `C:\Xilinx`. Include xsim (cosim).

---

## §0 RIPRESA RAPIDA (leggi prima questo)

> ## ⚠️ ARCHITETTURA DEPLOYATA = **B2 (time-mux)**. Tutto ciò che segue con "44% LUT" è **SUPERATO** (2026-07-14)
>
> | architettura | sorgente | LUT | stato |
> |---|---|---|---|
> | **B2 time-mux** (1 neurone/clock, `hdl.RAM`, FSM) | `snn_b2_fsm` → `snn_top_b2` | **4.223** (~7,9% dello Zynq-7020) · FF 1.584 · BRAM 1 · DSP 38 | ✅ **DEPLOYATA → bitstream PYNQ-Z1** |
> | parallela (tutti i neuroni srotolati) | `snn_hdl_<name>` (`make_hdl`) | **23.186 = 44%** · DSP 32 · Fmax ~5 MHz | ⛔ **SUPERATA** (~5,5× più grande) |
>
> **⚠️ AGGIORNAMENTO 2026-07-14 — il B2 è CAMBIATO due volte oggi; il bitstream è STALE:**
> 1. **Fix di `snn_b2_fsm`** (non era bit-exact a `snn_core`: 82,4 % dei control-step) → **§2.1**. Costo +5 LUT.
> 2. **Decode: 256 → 64 punti** (`snn_top_b2` usa `snn_decode_lut(raw,64)`; `snn_decode_hdl` è **legacy**) —
>    scelta dallo studio `DECODE_LUT_SWEEP.md` §5bis: accuratezza identica, **−288 LUT**.
>
> **Top attuale (post-fix, decode-64): 4342 LUT · FF 1584 · DSP 38 · BRAM 2** (Vivado OOC, `xc7z020clg400-1`).
> *(4630 con decode-256; i 4.223 di `results.csv` sono `util_b2_flat`, scopo diverso: non confrontabili.)*
> **Il bitstream su disco precede entrambi i cambi → va rigenerato.**
>
> Numeri B2 originali = grounded su `matlab/axi/build/phase_b/results.csv` (`synth-OOC`, `util_b2_flat`). La catena reale del
> bitstream è `snn_b2_fsm` → `snn_top_b2` → `snn_top_b2_flat` + `snn_b2_axi_lite` (vedi `axi/build/axi_synth.tcl`).
> **Regola:** l'architettura generata **segue il sorgente** — sorgente FSM ⇒ time-mux (4.2k LUT); sorgente parallelo
> ⇒ 23k LUT. L'auto-flow **non** serializza da solo (§9 "Streaming ÷32"). Interfaccia del deployato: §3.1.
>
> **Il blocco §0 qui sotto è del 2026-07-10 e descrive la fase PRE-B2** (numeri 44%, "Vivado non pronto",
> "non ancora cosim'd"): **conservato per storia, NON è lo stato attuale.** Cosim ③: **CHIUSA** (xsim, PASSED).

> **[STORICO PRE-B2] ✅ AGGIORNAMENTO 2026-07-10 — ④ SINTESI + P&R REALI (Vivado 2026.1, OOC su `xc7z020clg400-1`).**
> Donatello **entra e ROUTA** sullo Zynq-7020 (`Design State: Routed`, 0 ERROR). Numeri **VERI post-route**:
> **LUT 23.186 = 44%** · **slice occupati 53%** · **FF 3.386 = 3%** · **DSP 32 = 15%** · **BRAM 0** ·
> **Fmax ~5 MHz** (percorso critico 200 ns, **NON-vincolante**: control-step 0.1 s ⇒ margine ~50.000×). I 32 DSP
> = i mult residui previsti (`si·eth`/`si·tjump`) → **po2→shift confermato dal reale, nulla "sfuggito"**.
> `opt_design` toglie solo ~2% ⇒ **i LUT sono reali, non pessimismo di sintesi**; la STIMA HDL Coder li
> **sotto-contava** (≈17k op → 23k LUT + 4.6k CARRY). **Scarti vs §1:** DSP **32≠0**; LUT **44%/slice 53%** per UN
> champion ⇒ poco spazio per decode+AXI, zero per un 2° champion co-residente. **Fit ok ma LUT-bound → `streaming
> ÷32` (§8.2) è l'attacco d'area ora giustificato dai numeri.** Post-synth (pre-P&R): LUT 24.087/45%, Fmax 6.6 MHz.
> **③ COSIM CHIUSA (2026-07-10)**: TB auto in **xsim** → `**TEST COMPLETED (PASSED)**`, RTL **bit-esatto vs golden**
> (0 mismatch, 16 campioni × 5 out, sim 1640 ns) — anello ③ ora **misurato**, non solo garantito da HDL Coder.
> Artefatti: `scratchpad/impl_out/{util_impl,timing_impl}.rpt` + `donatello_routed.dcp`; script
> `scratchpad/{synth,impl}_donatello.tcl` (promuovibili in `matlab/synth/`).

**[STORICO PRE-B2 — superato: vedi banner sopra] Stato in una riga:** RTL VHDL **bit-accurato** (garanzia HDL Coder vs il fixed MATLAB — **NON ancora
cosim'd**) generato per Donatello, single-source da `snn_core`. **po2→shift FATTO** → moltiplicatori
**27.840 → 32 in STIMA** (premessa 0-DSP; **NON ancora sintetizzato**), comportamento preservato (parità
double 2e-6, errore fixed **≤0.028 = max sui 5 parametri**, v0 il peggiore). Resta il **lato LUT**
(adder/mux, alti in STIMA) e il **verdetto di sintesi VERO** (serve Vivado — che include il simulatore,
quindi UNA installazione sblocca sia la sintesi ④ sia la cosim ③).

**[STORICO — Vivado è installato e la sintesi è FATTA; il deployato è il B2, non questo] Prossima azione (quando Vivado è pronto):** sintetizzare l'RTL Donatello
(`matlab/codegen/snn_hdl_Donatello/hdlsrc/snn_hdl_Donatello.vhd` — rigenerabile) su **Zynq-7020
`xc7z020clg400-1`** per numeri DSP/LUT/FF/timing REALI. La resource-report di HDL Coder è solo una
STIMA (pessimista sui DSP). Se sta / è vicino → area OK. Se LUT troppo alti → streaming ÷32 (§8 punto 2).

**Comandi di verifica (dalla dir `matlab/`, MATLAB su PATH):**
```
matlab -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); run_parity_tests"                 % double vs golden PyTorch (~2e-6 — DEVE passare)
matlab -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); run_fixed_sweep"                  % errore fixed vs frac bits (convergenza a f=13)
matlab -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); gen_hdl_tops; run_hdl_verify"     % wrapper HDL vs golden (≤0.028)
matlab -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); make_hdl('Donatello')"            % rigenera RTL + report risorse
```

**Regola d'oro (cancello 1:1):** ogni modifica a `snn_core.m`/`snn_types.m` → rilancia
`run_parity_tests` (double DEVE restare ~2e-6) PRIMA di procedere. È così che è stato trovato il bug
leak-division e verificato ogni passo.

**Decisioni che SUPERANO `SIMULINK_IMPORT_DESIGN.md` (2026-07-06)** — quel doc precede questa fase:
- **Qm.n uniforme `f=13`** (non il floor `f=5` del design §1/§8). Uniforme e generoso su tutti i champion →
  **dissolve il prerequisito** «ri-profilare i range per-stato dell'eventprop prima del fixed-point» (design §7):
  il fixed-point su Donatello/Michelangelo (eventprop) è GIÀ fatto a f=13, errore ≤0.028. `snn_types('fixed',nfrac)`
  resta parametrico → il floor f=5 vale se un domani si vuole comprimere, ma NON è l'operating point attuale.
- **Generazione RTL via `make_hdl.m` → `codegen -config hdl`** sui wrapper `snn_hdl_<name>.m`, **NON** `makehdl`
  sul `.slx` (design §5.2/§7): il flow Simulink-HDL non aiuta con un MATLAB Function block (§9). Il blocco
  `snn_champions_lib.slx` resta l'**artefatto comportamentale** (double), non il sorgente HDL.

---

## §1 Obiettivo
Portare i 4 champion SNN (Donatello, Michelangelo, Raffaello, Leonardo) su FPGA **PYNQ-Z1 (Zynq-7020)**
come RTL **generato dallo STESSO codice** che ha la parità bit-accurata col PyTorch — non una
riscrittura a mano. Delivery finale = HDL sintetizzabile e 0-DSP (pesi potenza-di-2 → shift).

## §2 La catena 1:1 (5 anelli, ognuno con la sua garanzia)
```
PyTorch(fp32) ─①─ MATLAB double ─②─ MATLAB fixed (snn_core) ─②bis─ B2 serializzato (snn_b2_fsm) ─③─ VHDL/RTL ─④─ silicio
   parità 2e-6      quantizz. ≤0.028        serializzazione 1 neurone/clock      HDL Coder BIT-ESATTO     sintesi (Vivado)
```
- **①** FATTO: `run_parity_tests` ~2e-6 (roundoff float).
- **②** quantizzazione INEVITABILE ma piccola (≤0.028 su v0 a f=13) — **non** è un fallimento di conversione.
- **②bis** ⚠️ **anello introdotto dal B2 e per mesi NON elencato qui** (era implicito in «l'FSM è un mirror bit-exact»):
  `snn_core` → `snn_b2_fsm`. Cancello corretto = **`run_b2_parity_dataset`** (60 traj × 1000 step × 4 champion →
  **0/240.000**). Il vecchio `run_b2_parity` (golden **16 campioni**) era **cieco** e ha lasciato passare un bug reale
  per mesi → **§2.1**. *Lezione: ogni anello aggiunto alla catena va (a) elencato qui e (b) dotato di un cancello
  profondo quanto l'uso reale.*
- **③** ✅ **verificato in cosim** (xsim, 2026-07-10): TB `raw_expected.dat` → `TEST COMPLETED (PASSED)`, RTL bit-esatto vs il fixed MATLAB. Non più solo garantito.
- **④** ✅ **synth + P&R REALI** (Vivado 2026.1, 2026-07-10, §0): LUT 44%/slice 53%, DSP 32, 0 BRAM, ~5 MHz. Resta solo la sintesi degli altri 3 champion.

## ✅ §2.1 L'anello mancante della catena: `snn_core` → `snn_b2_fsm` (BUG TROVATO E CORRETTO 2026-07-14)

> **In una riga**: il B2 ha aggiunto alla catena §2 un anello **non dichiarato** — la *serializzazione*
> `snn_core → snn_b2_fsm` — il cui cancello era profondo **16 campioni** su un uso reale di **1000**.
> Sotto quel velo, l'FSM **non era bit-exact**: 82,4 % dei control-step del dataset divergeva.
> **Causa trovata (1 riga), corretta, e verificata su 240.000 control-step: ora 0 divergenze.**

**Stato: RISOLTO.** `snn_b2_fsm.m:77` corretto; nuovo cancello `run_b2_parity_dataset` (60 traiettorie ×
1000 step × 4 champion → **0/240.000**); costo in area **+5 LUT (+0,1 %)**. Cronologia e prove sotto.

### Com'era (il velo)

**Il buco di copertura.** Il cancello `run_b2_parity` — quello che dichiara *«0 mismatch su tutti e 4 i champion»* —
gira sulla sequenza golden `c.x_phys`, che è lunga **16 campioni**. Anche la **cosim** di Fase B era su **16 campioni**.
Le traiettorie d'uso reale sono lunghe **1000**. L'intera verifica della catena B2 è quindi **profonda 16 passi**.

**Estensione misurata** (forward B2 vs core, **stesso `xn`**, intero `test_dataset.mat`, harness `snn_traj_b2` + MEX):

| metrica | valore |
|---|---|
| traiettorie con almeno una divergenza | **60 / 60 (100 %)** |
| control-step divergenti | **49.436 / 60.000 (82,4 %)** |
| divergenza massima (raw) | **2,543** |
| primo step divergente | da **1** a **362** (mediana ~100) → **oltre** i 16 del cancello |

`run_b2_parity('Donatello')` resta **verde (0 mismatch su 16 step)**: non è in contraddizione: semplicemente **non
arriva dove il problema vive**.

**Impatto funzionale: BENIGNO** (misurato sulle stesse 60 traiettorie, decode deployato, aggregazione del riferimento):

| forward | accuratezza params |
|---|---|
| `snn_core` (riferimento) | **83,971 %** |
| `snn_b2_fsm` (deployato) | **83,965 %** |
| differenza | **−0,007 punti** (rumore) |

`|params FSM − params core|` aggregati: **max 0,163 · mediana 0,042**. Cioè: l'82 % di divergenza sul `raw` **non**
si trasferisce all'uscita — il transitorio decade prima di contaminare la media della 2ª metà. **Il bitstream funziona;
ciò che è errata è la CLAIM di bit-exactness, non la rete.** *(Il che non chiude il caso: senza conoscere la causa non
si può escludere che in altri regimi/champion l'effetto sia peggiore.)*

**Conseguenze.**
1. La parità ③ della catena §2 è dimostrata **solo sui primi ~16 passi**, non in generale.
2. Il cancello va **esteso al dataset** (non a una sequenza corta): `scratchpad/parity_all_traj.m` è la misura;
   `matlab/snn_traj_b2.m` è il kernel MEX-abile del forward serializzato (senza MEX sarebbe ~20 M chiamate).
3. I blocchi di libreria `Donatello_*` **non c'entrano**: usano `snn_b2_fsm` fedelmente e stavano solo **propagando**
   una discrepanza già presente nella catena deployata.
4. **CAUSA RADICE — TROVATA E CONFERMATA** → `snn_b2_fsm.m:77`:
   ```matlab
   % snn_core.m:64    Vi = leaky(V(i), sh) + (Ii + reci);        % (Ii+reci) RESTA in T.accw = Q8.17
   % snn_b2_fsm.m:77  Vi = cast(...,'like',T.V) + cast(Ii + reci, 'like', T.V);   % <-- Q8.17 → Q5.13
   ```
   L'FSM **arrotonda la corrente sinaptica a 13 bit frazionari** prima di sommarla alla membrana, buttando i **4 bit
   extra di `accw`** che il core conserva **fino al confronto di soglia** `Vi >= eth`. Quando `Vi` cade entro ~2⁻¹⁴
   dalla soglia, i due **decidono lo spike in modo diverso** → lo stato diverge.
   *(Ironia: quei 4 bit esistono esattamente per la lezione §9 «bitshift nello stesso tipo TRONCA → serve il tipo
   LARGO accw». L'FSM li conquista e li scarta un'istruzione prima di usarli.)*

   **Prova** (una sola variabile): variante identica con **una riga** cambiata (`+ (Ii + reci)`, senza cast) →
   **0 / 60.000 control-step divergenti su 60/60 traiettorie**, contro 49.436/60.000 dell'originale.
   Ipotesi **escluse** lungo il percorso: quantizzazione ROM (pesi ≥ 0,0625, errore bake 0) · normalizzazione (stesso
   `xn` float del riferimento) · saturazione di `rec_V` (max |w| = 0,125 → 0 pesi saturati dal cast a `T.w`).
   Harness: `scratchpad/parity_wide.m`.

5. **Severità: limitata per costruzione.** Il meccanismo è **rumore di decisione ±1 LSB sulla soglia**, non un errore
   sistematico: uno spike flippa e il **leak lo dimentica** (misurato: 0,5 → 0,019 → 0,005 → … → 0). In regimi con `Vi`
   più spesso vicino alla soglia cresce la **frequenza** dei flip, non la **severità**. Coerente con l'impatto
   funzionale misurato (−0,007 punti). **Non può essere catastrofico**: non è divergente.

### La correzione (applicata 2026-07-14)
```matlab
% snn_b2_fsm.m:77 — PRIMA
Vi = cast(Vread - bitsra(Vread,sh),'like',T.V) + cast(Ii + reci, 'like', T.V);
% DOPO — (Ii+reci) resta in accw, come snn_core.m:64
Vi = cast(Vread - bitsra(Vread,sh),'like',T.V) + (Ii + reci);
```

| verifica | esito |
|---|---|
| **`run_b2_parity_dataset`** (NUOVO cancello: 60 traiettorie × 1000 step × **4 champion**) | **0 / 240.000** control-step divergenti · 0/60 traiettorie · max raw **0** |
| `run_b2_parity` (cancello originale, golden 16 campioni) | 0 mismatch su tutti e 4 — **nessuna regressione** |
| **Costo in area** (Vivado OOC, `xc7z020clg400-1`, stesso flusso) | `snn_top_b2` **4625 → 4630 LUT** = **+5 LUT (+0,1 %)** · FF 1584 = · DSP 38 = · BRAM 2 = · CARRY 545 → 543 |

**Perché costa così poco**: tenere 4 bit frazionari in più tocca solo sommatore e comparatore della membrana; le
moltiplicazioni (e quindi i DSP) non cambiano. *(Nota: i 4625 LUT non sono confrontabili con i 4223 di
`results.csv` Fase B, che misura `util_b2_flat` — scopo diverso. È valido il **delta** 4625→4630, stessa sessione.)*

### Conseguenze
- **Il bitstream esistente è STALE**: è stato costruito con l'FSM difettosa → va rigenerato quando serve.
- **Fase B regge**: +5 LUT è dentro il rumore; nessuna conclusione di potenza/area cambia.
- **La cosim ③ restava valida** anche prima: verificava *VHDL == MATLAB fixed*, ed entrambi avevano lo stesso difetto.
  L'anello rotto era **a monte**: `snn_core → snn_b2_fsm`, che §2 non elencava esplicitamente.
- **Cancello da usare d'ora in poi**: `run_b2_parity_dataset` (il golden a 16 campioni **non basta** e non deve più
  essere considerato una prova di equivalenza).

> **Lezione di metodo**: un cancello verde va letto insieme a **su cosa gira**. 16 campioni di una sequenza non sono
> una prova di equivalenza per un sistema con stato che evolve su 1000 passi.

## §3 I tre livelli (dove si agisce — regola)
1. **VHDL a mano → MAI.** Rompe la garanzia 1:1, non riproducibile, e ora **non verificabile** (niente simulatore).
2. **Config HDL Coder → SÌ (leva primaria).** Bit-preserving.
3. **Sorgente MATLAB → SÌ, chirurgico.** Solo modifiche behavior-preserving, gated dalla parità.

> Il blocco plug&play `snn_champions_lib.slx` è l'artefatto **COMPORTAMENTALE** (double, decode inline):
> resta com'è, **NON** è il sorgente HDL. Il sorgente HDL è `snn_core` (type-parametrizzato).

### §3.1 Contratto d'interfaccia: dov'è la normalizzazione, a cosa servono `start`/`done` (VERIFICATO 2026-07-14)

**La normalizzazione NON è in HDL** — il deployato riceve `xn` GIÀ normalizzato. Verificato su 3 fonti indipendenti:
1. `snn_b2_fsm` **non usa** `invS/invV/invVL/inv2DV`: quelle costanti esistono solo in `b2_rom_active.m` (scritte da
   `gen_b2_rom`) e sono **morte** — nessun consumatore.
2. Entity del VHDL sintetizzato (`codegen/snn_top_b2/hdlsrc/snn_top_b2.vhd`): `xn : IN sfix19_En13 [4]`,
   `start : IN`, `params : OUT sfix21_En13 [5]`, `done : OUT` — e **0 occorrenze** di costanti di normalizzazione.
3. `axi/phase_b/gen_stimulus.m:32` normalizza **in double/float**, poi quantizza a Q5.13 19-bit per l'HDL.

→ Catena reale: **PS (float): `s,v,dv,v_l` → `snn_normalize` → `xn` Q5.13 → PL (fixed): SNN → `params`.**
Motivo (commento in `snn_top_b2.m`): 1 LSB di `xn` può flippare uno spike → la normalizzazione si fa in float a
monte, non in fixed nel fabric.

**`start`/`done` = confine di transazione, non decorazione.** Il B2 è time-multiplexato (1 neurone/clock,
~341 clock/inferenza): dopo `start` i `params` **non esistono** per ~341 cicli. Il PS scrive `xn`, alza `start`,
attende `done`, legge `params`; senza `done` leggerebbe uno stato intermedio.

**I due livelli — NON mescolarli:**

| | livello **MODELLO** (`snn_champions_lib.slx`) | livello **RTL** (top deployato `snn_top_b2`) |
|---|---|---|
| 1 chiamata = | **1 inferenza** | **1 colpo di clock** |
| I/O | fisico `s,v,dv,v_l → v0,T,s0,a,b` (normalize **dentro**) | `xn` Q5.13 + `start` → `params` + `done` |
| `start`/`done` | **privi di senso** (servirebbero 341 passi/inferenza) | **essenziali** |

`snn_b2_fsm` è una **serializzazione bit-exact di `snn_core`** → un blocco a livello modello che inlinea `snn_core`
(fixed) in **una chiamata** produce **gli stessi numeri** del deployato senza handshake: si rinuncia solo allo
*scheduling* cycle-accurate. ⚠️ **Ma attenzione**: "stessi numeri" ≠ "stessa architettura HDL" — vedi sotto.

### §3.1.1 Cosa genera HDL Coder da un blocco — **l'architettura segue il SORGENTE** (verificato sugli artefatti)
| sorgente nella chart | HDL generato | LUT | note |
|---|---|---|---|
| chiama/inlinea **`snn_b2_fsm`** (FSM + `hdl.RAM`) | **time-mux** | **~4.2k** | classe **deployato** ✅ |
| inlinea **`snn_core`** ("1 chiamata = 1 inferenza", neuroni paralleli) | **parallelo srotolato** | **~23k** | l'architettura **SUPERATA** ⛔ |
| comportamentale **double + `exp`** (i 4 blocchi base) | **nessuno** | — | double/`exp` non sintetizzabili |

L'auto-flow **NON** converte il parallelo in time-mux (§9 "Streaming ÷32": `loopspec('stream')` ignorato sul loop
annidato, RAM-mapping fallito → per serializzare servono `hdl.RAM`/FSM **espliciti**).
> **Corollario (decide il design della libreria):** «blocco 1-chiamata-1-inferenza» e «logica time-mux del deployato»
> sono **mutuamente esclusivi**. Volere HDL comparabile al deployato ⇒ **l'FSM deve stare dentro il blocco** ⇒ il blocco
> lavora a **rate di clock** (~341 passi/inferenza). Il prezzo del 5,5× di area è la latenza multi-ciclo: è l'architettura, non un difetto.

### §3.1.2 `start` scollegato in Simulink = **fallimento SILENZIOSO** (verificato 2026-07-14)
| `start` | esito simulazione |
|---|---|
| **scollegato** | **nessun errore**: Simulink lo mette a 0 → FSM mai avviata → `done` mai, **`params=[0 0 0 0 0]` per sempre** |
| `=0` | idem: blocco morto, params all'init |
| `=1` | funziona: `done` a ~341 clock, params corretti |

→ Un blocco che espone `start` **può essere usato male senza accorgersene** (output zeri, zero diagnostica). Se l'FSM sta
dentro un blocco di libreria, **pilotare `start` internamente** — ma **non** in free-running: vedi §3.1.4.
Harness: `scratchpad/test_start_floating.m`.

### §3.1.4 Il blocco non deve FREE-RUNNARE: edge-trigger sul cambio d'ingresso (VERIFICATO 2026-07-14)
Un blocco di libreria che contiene l'FSM time-mux deve decidere **quando** iniziare un'inferenza:

| schema | comportamento | esito |
|---|---|---|
| **free-running** (riparte su `done`) | 1 inferenza ogni 341 clock, **a prescindere dall'ingresso** | ⛔ **SBAGLIATO**: con hold ≠ 341 fa più (o meno) inferenze per campione → **lo stato della rete evolve troppo in fretta**. E obbliga chi usa il blocco a conoscere il numero magico 341. |
| **edge-triggered sul cambio d'ingresso** | **1 campione = 1 inferenza** | ✅ funziona con **qualunque** hold ≥ latenza — verificato hold = 341/400/500/777/1000 → **dmax = 0** |

**Regola: 1 campione = 1 inferenza.** Il vincolo residuo (hold ≥ ~341 clock) è **fisica del time-mux**, non una
convenzione: sull'FPGA reale un control-step da 0.1 s dura **800.000 clock** e l'inferenza ne usa **341 (0,04 %)** →
soddisfatto con enorme margine da qualsiasi modello sensato. **Il rapporto col `FixedStep` non va più conosciuto.**
> **Limite noto dell'edge-trigger**: se due campioni consecutivi hanno tutti e 4 gli ingressi **bit-identici**, il blocco
> non vede il campione nuovo e salta un'inferenza (il sistema reale invece pulsa `start` a ogni control-step comunque).
> Con traiettorie reali a Q?.20 non accade; in uno scenario a ingresso **rigorosamente costante** sì. Se serve
> bulletproof: aggiungere un ingresso esplicito `new_sample`. `run_block_traj_test` verifica anche che su ingresso
> costante l'inferenza sia **una sola** (cioè che non sia tornato il free-running).

### §3.1.3 Normalizzazione dentro il blocco: la precisione è critica (VERIFICATO 2026-07-14)
I blocchi di libreria hanno I/O **fisico**, quindi normalizzano **in fixed** al proprio interno (il deployato la fa in
SW float e riceve `xn`, §3.1). Perché il risultato sia **identico** al path float servono **DUE** condizioni:
1. **Reciproci a Q?.30** (`fi(1/S, 1, 34, 30)`) — **non** Q?.20;
2. **ingressi con ≥ 20 bit frazionari** (es. `fixdt(1,32,20)`).

Quante volte `xn_fixed ≠ xn_float` su 25 control-step di traiettoria reale:

| ingresso | reciproci Q?.20 | reciproci Q?.30 |
|---|---|---|
| Q?.13 | 1 | 1 |
| Q?.20 | 1 | **0** |
| Q?.28 | 1 | **0** |

**Perché conta**: una singola deviazione di **1 LSB** (2⁻¹³) su `xn` **flippa uno spike** → lo stato diverge → i params
driftano. Misurato con reciproci Q?.20: esatto fino al control-step 14, poi deviazioni **0.01 → 0.23** entro 20 step.
È esattamente il fenomeno che il deployato evita normalizzando in float sul PS. Con **entrambe** le condizioni:
`run_block_traj_test` → **dmax = 0** su 20 control-step in streaming (Champion e LUT{16,64,512}).
> **Regola d'uso**: pilotare i blocchi con segnali a **≥20 bit frazionari**. Con meno, il blocco *funziona* ma non è
> bit-exact al riferimento SW (≈1 spike flippato ogni ~25 control-step).

## §4 Architettura del core (`matlab/snn_core.m`)
- **Type-parametrizzato** via `snn_types('double'|'fixed', nfrac)`: stesso codice per parità (double) e HDL (fi).
- 1 chiamata = 1 control-step = `nt=10` tick interni; stato `persistent` (V, fatigue, s_prev, V_LI, x_buf);
  `snn_core([],[],T,'reset')` azzera. `snn_entry(dt,x_phys,W)` = normalize → core → decode (double).
- **Per tick:** ring-buffer input → `t_lr = Vr·s_prev` (conditional-add, spike∈{0,1} → nessuna mult) →
  **loop per-neurone** { corrente sinaptica via `po2shift`, ricorrenza `U·t_lr` via `po2shift`, membrana
  leak-shift, spike `>=`, fatigue, soft-reset, readout `Wout` conditional-add } → LI leak-shift.
- **Helper chiave:**
  - `leaky(x,n)` — leak bit-shift (fi: `x - bitsra(x,n)`; double: `x - x/2^n`). **Sostituisce** la divisione
    fi `./ld` (causa del bug plateau, §9).
  - `po2shift(sgn,k,w,x,Tw)` — moltiplicazione per peso po2 come **SHIFT** (fi: `sgn·bitshift(cast(x,Tw),k)`
    nel tipo **LARGO** `T.accw`; double: `w·x`). Esponenti/segni `Kfc/Sfc/KU/SU` calcolati nell'header da
    COSTANTI (foldati da HDL Coder; **niente `log2` nel datapath**).
- **Comparatore spike `>=`** (`snn_core.m` §3c): baseline PyTorch usa `>=` (match esatto), eventprop usa
  `>` (deviazione misura-nulla in float; da rivalutare in fixed se i pareggi contano — §9).
- **Tipi fixed** (`snn_types.m`, default `nfrac=13`): V=Q5.13, fatigue=Q3.13, acc=Q5.13, **accw=Q8.17**
  (+4 frac per shift po2 esatti), raw=Q7.13, w=Q2.13 (po2 esatti).

## §5 Trajectory ottimizzazione area (Donatello, STIMA HDL Coder)
| step | mult | add | mux | clock |
|---|---|---|---|---|
| naive `makehdl` | 27.840 | 67.100 | 29.170 | 1× |
| +`LoopOptimization='StreamLoops'` (tick ÷10) | 2.752 | 7.084 | 3.472 | 10× |
| +refactor loop per-neurone | 1.344 | 3.476 | 3.472 | 10× |
| +conditional-adds (Vr, Wout gated) | 672 | 3.476 | 10.768 | 10× |
| **+po2→shift (ATTUALE)** | **32** | **5.524** | **11.536** | **10×** |

Config in `make_hdl.m`: `LoopOptimization='StreamLoops'`, `ConstantMultiplierOptimization='CSD'`,
`ResourceSharing=32`, `ShareAdders=true`, TargetLanguage VHDL, TB auto-generato.

## §6 Stato attuale (fatto / pendente)
- ✅ **po2→shift**: 32 moltiplicatori (i 32 residui = scalari gated `si·eth`/`si·tjump`, ≪ 220 DSP).
- ✅ RTL bit-accurato generato per **Donatello** (+ testbench auto vs golden), 0 errori codegen.
- ✅ Comportamento: parità double 2e-6; errore fixed ≤0.028 (v0) su tutti e 4 (Leonardo NON regredito).
- ✅/⏳ **Lato LUT**: **REALE post-route 23.186 LUT = 44% (slice 53%)**, 4.571 CARRY, 0 BRAM — la STIMA
  (adder 5.524 + mux 11.536) li **sotto-contava**. Fit ok ma **LUT-bound** ⇒ streaming ÷32 giustificato dai numeri.
- ⏳ **Streaming ÷32** dei neuroni: BLOCCATO da RAM-mapping (accessi non-scalari) — §8 punto 2 / §9.
- ✅ **Vivado 2026.1 + ④ synth & P&R REALI** (2026-07-10, vedi §0): Donatello routa, DSP 32/220, ~5 MHz
  (non-vincolante). **Cosim ③ ✅ PASSED** (xsim, `TEST COMPLETED (PASSED)`, bit-esatto vs golden, 2026-07-10).
- ✅ **Decode (sigmoid)**: implementato (`snn_decode_hdl.m`, σ-LUT, `test_decode` err 0.002) e **dentro `snn_top_b2_flat`** (`snn_top_b2` = `snn_b2_fsm` → `snn_decode_hdl`) → è nelle risorse Fase B e nel bitstream. *(Correzione 2026-07-13: la voce precedente "escluso / non implementato" era stale.)*
- ⏳ **Altri 3 champion**: wrapper generati; RTL prodotto solo per Donatello.

## §7 File (worktree)
- **Sorgente HDL:** `matlab/snn_core.m` (mod), `matlab/snn_types.m` (mod, +`accw`),
  `snn_normalize.m`, `snn_decode.m`, `snn_entry.m`.
- **Wrapper baked + `coder.const`:** `matlab/snn_hdl_<name>.m` (generati da `gen_hdl_tops.m`).
- **Driver HDL:** `matlab/make_hdl.m` (config + `codegen -config hdl` + TB + summary risorse).
- **Verifiche:** `run_parity_tests.m` (double), `run_fixed_parity.m` / `run_fixed_sweep.m` (fixed Qm.n),
  `run_hdl_verify.m` (wrapper HDL).
- **Diagnostica:** `diag_ranges.m` (range segnali interni), `diag_quant.m` (quantizzazione stato vs bug).
- **Export pesi:** `scripts/export_champions.py` → `matlab/champions_export.mat` (po2 reale, delays, golden).
- **Generato, NON versionato** (`matlab/.gitignore`): `matlab/codegen/` (RTL in `snn_hdl_<name>/hdlsrc/`). HDL Coder
  emette più file: top `snn_hdl_<name>.vhd`, stadio/i pipeline `snn_hdl_<name>p<N>.vhd` (dal delay-balancing del
  clock-rate), test-config `*_tc.vhd`, package `*_pkg.vhd`, testbench `*_tb.vhd` + vettori `xn.dat`/`raw_expected.dat`.

## §8 Prossimi passi
1. ✅ **[FATTO 2026-07-10] Sintesi + P&R reali** RTL Donatello su Zynq-7020 (`xc7z020clg400-1`): LUT 44%/slice 53%,
   DSP 32, 0 BRAM, ~5 MHz. + ③ **cosim xsim PASSED** (bit-esatto vs golden). Vedi §0 e `HDL_ARCHITECTURE_STUDY.md`.
2. ⛔ **[INVESTIGATO 2026-07-10 → NON PERSEGUITO] streaming ÷32.** Tentato (circular-buffer + `RAMThreshold` +
   `loopspec('stream')`): NON ingrana — `loopspec('stream')` è **top-level-only** (loop neuroni annidato) e il
   RAM-mapping fallisce ("accessed in a loop region" + "non-scalar sub-matrix access"). Servirebbe un
   rearchitecting esplicito (`hdl.RAM`/FSM time-multiplex), **senza retraining** ma sostanziale, per un guadagno
   **solo estetico** (target PYNQ-Z1 fisso, energia device-static-dominata, V2I piccolo). Analisi completa in
   **`HDL_ARCHITECTURE_STUDY.md`**. Riapribile se il target cambia.
3. ✅ **[FATTO] Decode → LUT** (`snn_decode_hdl.m`, σ-LUT): è già uno stadio dentro `snn_top_b2`; la Fase B ha sintetizzato `snn_top_b2_flat` = SNN+decode (parità decode `test_decode` 0.002).
4. **Altri 3 champion:** `make_hdl('Michelangelo'|'Raffaello'|'Leonardo')`.
5. **Cosim** (quando c'è un simulatore): il TB auto verifica RTL vs golden bit-esatto (anello ③).
6. **Registrazione custom-board PYNQ-Z1** + eventuale ri-profilazione Qm.n.

## §9 Gotcha / lezioni (FONDAMENTALI — non ri-sbatterci)
- **`log2`/`double` MAI nel datapath**: HDL Coder li sintetizza (via `isnan`/`isinf` → errore). OK **solo su
  COSTANTI nell'header** (foldati, come `sh`). `po2shift` usa `Kfc/Sfc` precalcolati, non `log2` nel loop.
- **Bug leak-division (RISOLTO):** `V./ld` in fi = divisione con auto-output-type → errore
  *precision-independent* (plateau ~3.5, non migliora coi bit). Fix = `leaky` bit-shift. → i leak in HW sono
  SHIFT, non divisioni. (Diagnosi: `diag_quant.m` convergeva a 0, `fi` no → non era quantizzazione.)
- **po2 NON riconosciuti da CSD**: attraverso `struct + cast`, HDL Coder non folda i po2 in shift → 1.312
  moltiplicatori. Fix = `po2shift` esplicito (esponenti baked). **Il tool non sfrutta i vantaggi FPGA da solo
  → vanno ESPRESSI esplicitamente** (come il leak-shift). La rete non si "sbrandella": si adatta l'espressione.
- **Precisione shift**: `bitshift` nello STESSO tipo TRONCA (Leonardo → 0.95). Fix = tipo LARGO `accw`
  (+4 frac) → shift esatto, precisione preservata.
- **Streaming ÷32 NON ottenibile con l'auto-flow (INVESTIGATO 2026-07-10 → `HDL_ARCHITECTURE_STUDY.md`)**: il loop
  neuroni è annidato → `coder.hdl.loopspec('stream')` è **top-level-only** e viene ignorato; il RAM-mapping di
  V/fatigue/x_buf fallisce ("accessed in a loop region" + "non-scalar sub-matrix access" dagli init `zeros`/
  `s_prev=s`/`V_LI(:)`), anche con `RAMThreshold` basso + `head` circular-buffer int8. `StreamLoops`+`ResourceSharing`
  (già nel baseline) sono il massimo dell'auto-flow. Per serializzare davvero serve `hdl.RAM`/FSM espliciti →
  **non perseguito** (guadagno solo estetico, vedi studio).
- **Simulink-HDL flow NON aiuta con MATLAB Function block**: dentro il block gira lo stesso motore
  MATLAB-to-HDL. Beneficio solo ricostruendo a blocchi (perde single-source) → **scartato**.
  > **Precisazione VERIFICATA 2026-07-14 — "non aiuta" ≠ "non funziona".** `makehdl` su un Subsystem con dentro un
  > MATLAB Function block che usa `hdl.RAM` + `persistent` + la FSM B2 **genera VHDL** (0 errori/warning), inclusa
  > `DualPortRAM_generic.vhd` ⇒ **time-mux**. È esattamente ciò che abilita i **blocchi di libreria HDL-ready**
  > (`Donatello_Champion`/`Donatello_LUT{N}`): il `.slx` da solo, su un altro PC, produce il VHDL. Per il **deployment**
  > resta valida la scelta `codegen -config hdl` da MATLAB (single-source); il flusso Simulink serve alla **libreria**.
- **Chart SELF-CONTAINED = funzioni locali (2026-07-14)**: un MATLAB Function block può contenere **funzioni locali**, e
  le locali **hanno precedenza sul path**. Quindi per rendere un blocco autosufficiente NON si copia codice a mano (deriva):
  il generatore **legge i sorgenti veri** (`b2_rom_active`+`snn_types`+`snn_b2_fsm`+decode) e li appende come locali.
  Cancello che lo dimostra: `run_block_hdl_gate` (copia solo il `.slx`, toglie `matlab/` dal path, lancia `makehdl`).
- **Larghezza dei `fi` costanti — controllare il range (2026-07-14)**: `fi(20, 1, 18, 13)` ha 18-1-13 = **4 bit interi**
  ⇒ range ±16 ⇒ **20 satura a ~15.999** (clamp sbagliato, silenzioso a parte un warning "overflow during constant
  folding"). I warning di quantizzazione di HDL Coder **vanno letti**: qui hanno scoperto un bug reale.
- **Resource report = STIMA, non sintesi**: ignora DSP-inference (mult piccoli → LUT), LUT-packing, retiming.
  **Verdetto vero solo da Vivado.**
- **Accumulatore a larghezza fissa (codegen)**: una variabile non può cambiare tipo tra iterazioni del loop →
  usare `x(:) = ...` per forzare il tipo dichiarato (I_input, wacc, t_lr).
- **loopspec factor**: `coder.hdl.loopspec('stream', N)` con N = trip-count NON serializza (interpretato come
  parallelismo). Semantica non chiarita in R2026a → per lo streaming affidarsi prima al RAM-mapping (§8 punto 2).
- **Costanti normalize nella ROM = MORTE (2026-07-14)**: `gen_b2_rom` bake `invS/invV/invVL/inv2DV` in
  `b2_rom_active.m`, ma **nessuno le consuma** (`snn_b2_fsm` prende `xn` già normalizzato). Non dedurre dalla loro
  presenza che l'HDL normalizzi: **non lo fa** (§3.1). Sono un residuo — o si usano davvero, o vanno rimosse.
- **Non mettere artefatti RTL nella libreria comportamentale (2026-07-14)**: i primi `Donatello_LUT{N}` esponevano
  `xn` + `start`/`done` dell'FSM cycle-accurate dentro `snn_champions_lib.slx` → a livello modello sono inusabili
  (341 passi di simulazione per 1 inferenza) e per giunta **non self-contained** (la chart chiamava `snn_b2_fsm`/
  `snn_decode_lut`/`snn_types`: col solo `.slx` non girano). La libreria è il livello MODELLO (§3, §3.1):
  1 chiamata = 1 inferenza, I/O fisico, tutto inline.
- **Verificare PRIMA di affermare com'è fatto il deployato (2026-07-14)**: un commento in un `.m` non è una prova.
  Le fonti che valgono: l'**entity del VHDL generato**, chi **consuma** le costanti, e il **generatore di stimoli**
  che alimenta l'HDL (§3.1). Affermare a memoria su questo ha già prodotto un errore.
