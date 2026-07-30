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
convenzione. Il control-step FISICO dura **0,1 s** (loop a 10 Hz): la latenza (341 clock) deve starci dentro →
serve un clock ≥ **~4 kHz**, soddisfatto con enorme margine da qualsiasi modello sensato. (A 8 MHz — il clock del
1° bitstream B2, `matlab/axi/README.md`, un RISULTATO non un requisito — 0,1 s = 800.000 clock e l'inferenza ne
usa **341 = 0,04 %**.) **Il rapporto col `FixedStep` non va più conosciuto.**
> **Limite noto dell'edge-trigger**: se due campioni consecutivi hanno tutti e 4 gli ingressi **bit-identici**, il blocco
> non vede il campione nuovo e salta un'inferenza (il sistema reale invece pulsa `start` a ogni control-step comunque).
> Con traiettorie reali a Q?.20 non accade; in uno scenario a ingresso **rigorosamente costante** sì. Se serve
> bulletproof: aggiungere un ingresso esplicito `new_sample`. `run_block_traj_test` verifica anche che su ingresso
> costante l'inferenza sia **una sola** (cioè che non sia tornato il free-running).

> **Low-power readiness:** lo stesso segnale idle dell'edge-trigger è l'enable per un futuro **clock-gating**
> (BUFGCE, `enable = ¬busy`) — il blocco è già clock-gating-ready. Razionale, drop-in e distinzione clock-gating
> (FPGA, solo dinamica) vs power-gating (solo ASIC, anche leakage) in
> `matlab/study_tradeoff/donatello/RESULTS.md` §12 "Predisposizione low-power".

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

### §3.1.5 Fmax INTERNO vs REALE + `splitpipe` (il muro del normalize) — 2026-07-22/23
⚠️ Il Fmax OOC reg-reg (studio trade-off §12-§14 in RESULTS.md) **NON è il Fmax deployabile**: esclude il
percorso ingresso→normalize→`go`, che con ingressi registrati (deployment) è reale e vale **~la METÀ**
(FAST 91→47, BAL 56→50, SLOW 30→29). Si misura col **5° arg `io`** di `impl_point.tcl`
(`set_input_delay/set_output_delay 0`). Al metro reale i tier si appiattiscono (BAL≈FAST, muro comune nel
normalize) → i 91 di FAST erano **illusori**.

**Fix = archStyle `splitpipe`** in `build_hdl_variants`: registra gli **OPERANDI** del normalize (`op_reg`)
fra clamp e moltiplicazione, edge-trigger sugli operandi registrati → spezza il percorso → FAST reale
47→**73,6 MHz**, bit-exact (dmax=0), **+1 latenza (406)**, **4-in/5-out**, fuori dal core `snn_b2_fsm`
congelato. `local_normalize` splittata in `local_normalize_ops`+`local_normalize_mul` (composizione
**bit-identica** per i chiamanti condivisi). ⚠️ init del persistente a **COSTANTE 0** (non `=op`: un init
combinatorio crea un bypass ingresso→mul→xbuf che NON spezza → 60 invece di 73,6).
Residuo = moltiplicazione 34-bit **intrinseca** (2 DSP cascati, ~13,5 ns, ~2 ns sopra il pavimento SNN);
phys_opt / AdaptivePipelining / 2-stadi NON la spezzano; i 91 richiederebbero decomposizione **2×2**
(+~25% FF → contro l'obiettivo area/V2I) → **scartata**. **Record completo + piano ripresa: RESULTS.md §15.**

> **✅ 2026-07-23 — i 3 tier splitpipe sono ora BLOCCHI di libreria.** `Donatello_SLOW` (R2·fused),
> `Donatello_BALANCED` (R5·p3), `Donatello_FAST` (R9·p5) aggiunti a `snn_champions_lib.slx` da
> **`build_tier_blocks.m`** (che riusa i mount estratti da `build_hdl_variants` in file condivisi):
> self-contained, HDL-ready, `dmax=0`, latenze 342/364/406. Gate G1–G4 verdi (dettaglio in SESSION_RESUME).
> ⚠️ Nel VHDL il marker splitpipe è **`op_reg`/`op_prev`** — i nomi di funzione (`local_normalize_ops`) NON
> sopravvivono a HDL Coder. La coerenza col VHDL misurato è provata **modulo-nomi** (package, chart-id `c<n>`,
> segnali `p<n>`, tutti derivati dal nome del blocco → 0 diff logiche). VHDL archiviato in
> `study_tradeoff/donatello/vhdl_tiers.tar.gz`.
>
> **✅ 2026-07-24 — blocco UNICO configurabile `Donatello_Tier`** (Variant Subsystem + mask TIER,
> `build_tier_configurable.m`): con `VariantActivationTime='update diagram'` HDL Coder genera **solo la variante
> scelta dal menu**, bit-identica (modulo nomi) al blocco separato per tutti e 3 i tier + self-contained + `dmax=0`.
> ⚠️ Le variant condition NON accettano funzioni → `TIER` numerico (mask popup `Evaluate=on`) e `TIER==k`.

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
- ✅ **Controllore completo `Donatello_ACC_IIDM_M`** (SNN-decode + ACC-IIDM, **SP4 CHIUSO 2026-07-17**): OOC
  xc7z020 @8 MHz = **8614 LUT · 2134 FF · 71 DSP · 9,30 MHz** (WNS +17,4 ns, latenza 358 clk), `dmax=0` vs SP3,
  **self-contained + HDL-ready** (gate `run_block_hdl_gate` PASSED, 2026-07-17). **BRAM non catturato** nel run
  OOC. Tecnica: time-mux dell'IIDM via FSM a stadi (1 divisore condiviso). Doc: `SP4_ACC_IIDM_FAST.md`.
  - ⚠️ **SUPERATO da R17 (2026-07-19, `hdl_iidm/RESULTS.txt`)**: divisore E radice (s_star) resi **SEQUENZIALI**
    (digit-recurrence 1-2 bit/ciclo) → il blocco corrente è **R17**: OOC **77,9 MHz** (R0 15,7 → R17, +397%),
    8387 LUT / 4069 FF / 68 DSP, collo `st_a_iidm` (14 liv), bit-exact ogni round. Il **9,30 MHz** sopra è la
    variante SP4 combinatoria (predecessore). ⚠️ 77,9 = **OOC reg-reg** (non io-timed): il deployabile è inferiore.
    Ri-verificato **self-contained + HDL-ready 2026-07-27** (`run_milestone_hdl_gates` 5/5, DualPortRAM, 0 err/warn).
    **Ri-sintesi OOC 2026-07-27** (Vivado xc7z020, 125 ns, `synth_acc_iidm.tcl` su VHDL fresco) **CONFERMA**:
    **77,936 MHz · 8387 LUT · 4069 FF · 68 DSP · 1 BRAM**, collo `st_a_iidm` 14 liv — identica a R17. Il 9,30 è chiuso.
- ⏳ **[FASE B2.0 — aperta 2026-07-17] Validazione RTL del blocco M**: il VHDL generato è solo *generato*, **mai
  simulato in xsim** vs riferimento sul **dataset intero** (anello ③ = cosim, finora fatto per la sola SNN B2, non
  per il controllore). Da fare: testbench HDL full-dataset con metriche vere (non traiettoria ridotta — lezione
  Fase B) + utilizzo post-route completo (incl. BRAM). Vedi §8 e `SESSION_RESUME.md` §AZIONE PENDENTE.
- ✅ **[FASE B2.0-2a M1 — 2026-07-18] Harness A (SNN `Donatello_Champion`) validato a livello RTL**: il VHDL
  generato è **bit-exact al blocco Simulink** su 3 traj × 1000 × 5 param (**A-1: 0/15000**), cancello provato
  sensibile (1 LSB → nMismatch=1). Tre implementazioni concordi: blocco == golden MEX == RTL VHDL. Harness in
  `run_rtl_validate`/`rtl_export_vectors`/`tb_champion_stream.v` (commit `c961bc85`).
- ✅ **[FASE B2.0 T6a — 2026-07-29] Harness_SNN (`Donatello_Tier@BALANCED`) validato a livello RTL, sui 60**: il
  VHDL generato è **bit-exact al blocco** — **T6-EXACT 0 / 300 000** (60 traiettorie × 1000 control-step × 5 param),
  cancello **provato sensibile** (1 LSB → nMismatch=1), **latenza RTL 364 clock = latenza blocco** (< HOLD 500),
  PORT-TYPE coperto. **Accuratezza di stima sugli stessi 60**: `v0` max 15.01 / p99 13.8 (**identificabilità**, non
  difetto RTL) · `T` 1.125/0.913 · `s0` 0.937/0.844 · `a` 0.991/0.892 · `b` 1.003/0.867.
  **Golden = il BLOCCO stesso** (oracolo `tier_block_params`, in cache `tier_golden_cache` → prova RTL e metriche
  sugli **stessi identici dati**); ⚠️ il riferimento MEX `r16` NON è il blocco e `snn_traj_champion` è **stale**.
  **Rilanciabile con UN comando**: `run_harness_snn` (in `FaseB2.0/Harness_SNN/`, ~75 min) → `results/RESULTS.md`
  = **fonte dei numeri per i report**. Struttura: golden/gen-HDL in `matlab/`, utilità condivise in
  `FaseB2.0/common/`, banco in `FaseB2.0/Harness_SNN/`, xsim in `D:/zbd_tier` (work-dir corta). **HW = T6b.**
- ✅ **[FASE B2.0 T6b — 2026-07-30] Caratterizzazione HARDWARE del sistema (Tier + wrapper AXI4-Lite + Zynq PS7)**
  — numeri in **`FaseB2.0/Harness_SNN/results/RESULTS_HW.md`** (fonte per i report), script in `Harness_SNN/hw/`:
  - **Funzionale**: i 5 parametri letti dal **PS via AXI** == blocco, **0/300 000** su 60 traiettorie, **sia** con
    clock gating attivo **sia** senza; cancello provato sensibile (1 LSB → mismatch). Wrapper: **commit sincrono**
    (buffer + fronte) e **`done` da contatore 371 clk** (`ce_out` è un clock-enable, §9).
  - **Netlist post-place&route** == blocco: **0/15 000** (3 traj, funcsim, gating ON). La sim di *timing* con SDF
    non è utilizzabile (causa nel banco: la funcsim verde esclude X-prop/GSR/init-BRAM); la **firma del timing è
    dell'STA**, pulita.
  - **Clock (sweep 6 punti, `-jobs` fisso)**: **FCLK deployabile 52 MHz** (WNS **+0,358 ns**; 55 non chiude a
    −0,345) e **limite del datapath 58,5 MHz** (derivato) (ritardo min 17,08 ns **stringendo**, non al crossover WNS=0).
    ⚠️ io-timed **di sistema**: non confrontabili coi 77,9 MHz OOC dell'`ACC_IIDM_M` né con gli 8 MHz della Fase B.
  - **Risorse post-route (incl. BRAM, il gap dei run OOC)**: **4473 LUT · 3199 FF · 52 DSP · 1 BRAM** @52 MHz;
    area quasi insensibile al vincolo (+3,1 % da 40 a 60 MHz).
  - **Latenza e margine**: 371 clk = **7,13 µs** contro un control-step di **0,1 s** ⇒ margine **≈14 000×**,
    **duty 0,0071 %**. Il clock massimo è una *caratterizzazione*, non la scelta di deployment ottimale.
  - **Energia (misurata al DUTY REALE**, un control-step intero simulato, 5,2 M cicli, 12 min, **gating OFF**):
    dinamica **0,009 W → 0,9 mJ per control-step** (78 % clock tree) — da leggere come **limite superiore** della
    dinamica del deployment, che gira a gating ON; statica del device 0,103 W → 10,3 mJ, **tenuta separata** e
    classificata **stima** (modello `typical`, Tj 26,3 °C — non viene dal SAIF).
    Serie di convergenza 3,85 %→0,37 %→0,008 % = 0,015→0,010→**0,009 W**. ⚠️ La **composizione
    lineare** `P_att·d + P_idle·(1−d)` è stata **invalidata** dal suo cross-check (§9): si misura al duty reale.
  - ⚠️ **Copertura del SAIF = 56 % dei net** (`6906/12380`, identico su tutti i 18 report): il 44 % è **stimato
    vectorless**. E **`Confidence = High` non è un avallo di accuratezza** — sui nodi interni scatta con
    «>25 % of internal nodes specified», è una soglia di copertura. Citare la copertura accanto ai watt.
  - **Clock gating**: **implementato e provato attivo** (`clk_tier` `TC 400→0` nel SAIF) e **funzionalmente
    trasparente** (0/300 000); ⚠️ il **guadagno in watt NON è quantificabile** con questo flusso (§9) — **stima
    2–4×** sulla dinamica, da **validare in Fase C** (il gating è un **bit di registro**: stesso bitstream,
    risparmio per differenza di corrente a riposo).
  - ⚠️ Il **worst-case sintetico non è un limite superiore** (risultò il *più basso*): si riporta il massimo
    **osservato** fra i 9 workload reali (0,045 W). Il vero regime peggiore richiede uno studio a sé.
  - **Bitstream PYNQ-Z1** @52 MHz: `.bit` + `.hwh` + `.xsa` in `FaseB2.0/Harness_SNN/bitstream/` (tracciati),
    **WNS +0,358 identico allo sweep** ⇒ il design flashato È quello caratterizzato; provenienza verificata nel
    `.hwh` (`BOARD=…pynq-z1…`, `DEVICE=7z020`).
  - **▶ RIPRODUCIBILITÀ — un comando per stadio:**
    `bash FaseB2.0/Harness_SNN/hw/run_harness_snn_hw.sh [check|probe|cosim|sweep|netlist|power|bitstream|summary|all]`.
    `summary` **riestrae i numeri dagli artefatti** (non da costanti nello script) → un rilancio si *confronta* con
    il documentato. `check` = **cancello di provenienza del DUT** (MD5 dei sorgenti VHDL vs `hw/vhdl_ref.md5`;
    se il VHDL manca lo rigenera **e rilancia il gate T6a**) — provato sensibile alterando un file.
  - ⚠️ **FINDING (golden):** il riferimento `snn_traj_fixed_r16` **NON è il blocco** — diverge a step ~52. Cause
    misurate: (1) la `local_normalize` **fixed** del blocco (fisico→xn) devia 1 LSB da `snn_normalize` (xn diverge
    a step 85); (2) il blocco pilota il forward a **ingresso tenuto**, `snn_traj_b2` con **zeri** (param divergono
    già a 52). Il forward inlinato **== `snn_b2_fsm.m`** (0 diff, non stale). **`run_block_traj_test` lo mascherava
    girando a K=20<52** (lezione §2.1 — gate corto; la sua comparazione vs r16 vale solo fino a K~50, da rivedere).
    Fix: golden **fedele al blocco** `snn_traj_champion` (algoritmo esatto della chart, guidato clock-per-clock a
    ingresso tenuto), verificato **== blocco** (cross-check dmax=0). ⚠️ **[2026-07-28] ORA STALE**: estrae da
    `Donatello_Champion`, **rimosso** nel riordino 8-blocchi (2026-07-27) → non più usabile; per il bench solo-SNN
    (T6) usare **parità RTL vs blocco reale** `Donatello_Tier@BALANCED`.
  - ⚠️ **Metrica param:** accuratezza param vs `gt_params` mostra `v0` err ~15 = **identificabilità** (v0 osservabile
    solo a flusso libero; Dynamic_Study), NON RTL. La qualità SNN vera è il **closed-loop (Harness B)**.
- ✅ **[FASE B2.0-2a M2 — 2026-07-18] Harness B (controllore `Donatello_ACC_IIDM_M`) validato a livello RTL**:
  **B-1** accel RTL == blocco **0/3000** (open-loop) · **PLANT-PAR** plant-nel-TB == riferimento **1800/1800**
  (sensibile) · **B-LOOP** anello RTL == riferimento **2400/2400** · **BEHAV** gap>0 sempre (car-following
  corretto in anello chiuso vero, non solo bit-exact). Golden-fedele `acciidm_m_traj`; anello self-contained
  in xsim (plant EGO nel TB in `real`, double bit-esatti). Commit `f3847650`/`c78872dc`.
  - ⚠️ **DUT in VERILOG** (non VHDL): il divisore combinatorio dell'IIDM manda un indice-LUT a **-1 a time-0**
    in xsim col VHDL (registri partono `U` → metavalue); Verilog inizializza i registri a 0. La SNN (M1) resta
    VHDL (no divisore). `rtl_gen_dut` ha ora il parametro lingua.
  - ✅ **[2026-07-18] Deriva blocco-fisico vs riferimento CARATTERIZZATA** (`characterize_drift`, 20k control-step):
    `|Δaccel|` **mediana 0** (identica sulla maggioranza degli step), **media 0.015**, **p99 0.188**, **max 0.977**
    [m/s²] = **69% / 66% del budget E_snn**. Cioe' **sparsa** (solo spike-flip) ma con **coda significativa** —
    stesso ordine della quantizzazione che la rete gia' si porta. **Non trascurabile in coda**; e' la differenza
    tra il blocco fisico (local_normalize) e il riferimento software (snn_normalize), da tenere per il confronto MPC.
    ✅ **[T5 — 2026-07-28] RI-ESEGUITA sul CONTROLLORE SCELTO** `Donatello_SNN_IIDM` (composto, non il deprecato
    `ACC_IIDM_M`), su **tutto** `test_dataset.mat` (60 traj / **60k** control-step), **open-loop** (decisione utente:
    deriva semplice, non la divergenza closed-loop). **Fase 0 cross-check:** golden `acciidm_m_traj` == blocco REALE
    della libreria (streaming Simulink) → **dmax=0**. Numeri **coincidenti** col 2026-07-18 (max 0.9766 · p99 0.1875 ·
    mediana 0 · media 0.0168 = 65.8% / 68.9% E_snn) → **riproducibile** e ora ancorato al blocco scelto. Committato
    `715b75b7`, doc `FaseB2.0/common/DRIFT.md`. ⚠️ `snn_traj_champion` (golden 5-param) è **STALE** (estrae da
    `Donatello_Champion`, **rimosso** nel riordino 8-blocchi) → non usato. Divergenza CLOSED-LOOP (accumula/smorza?)
    demandata al **car-following full-99 in T7**.
  - **PROSSIMO grande:** report intermedio (checkpoint) → riordino file matlab → 2b (ottimizzazione `tanh`) → 2c.
- ✅ **[MILESTONE 2026-07-27] Libreria consolidata a 8 blocchi, tutti verificati sul dataset.** Riordino **18→8**
  (4 Campioni double + `Donatello_LUT` combinato + `Donatello_Tier` + `ACC-IIDM` + `Donatello_ACC_IIDM_M`;
  `reorg_library.m` rimuove i singoli assorbiti). **Combine gate** `run_lut_combine_gate`: LUT combinato@N bit-exact
  ai singoli storici (`dmax=0`, 6 N × 25 control-step), discrimina N. **Test consolidato** `snn_lib_dataset_test.slx`
  + `run_lib_dataset_test`: **8/8 PASS** sul dataset (Campioni vs `ref_params`; HDL vs MEX+decode / `acc_iidm_open`,
  `dmax=0`). **Gate HDL self-contained** `run_milestone_hdl_gates`: **5/5 PASS** (LUT N=64 e N=16, Tier, ACC_IIDM_M,
  ACC-IIDM). Report QC'd (create-report, 6 fix, rebuild deterministico). Finding composizione + workflow libreria: §9.
  Stato completo: `SESSION_RESUME.md` §MILESTONE 2026-07-27.

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

> **🟢 PRIORITÀ ATTUALE — FASE B2.0 (validazione RTL della versione FPGA del controllore + report).** SP4 ha
> ottimizzato il blocco `Donatello_ACC_IIDM_M` (9,30 MHz, `dmax=0`, self-contained); B2.0 **prova che l'RTL
> generato funziona davvero** a livello di simulatore HDL, con metriche vere sul **dataset intero**, e ne scrive
> il report. Sequenza: **Fase 1** `/fpga-expert` (disegno studio RTL + audit headroom) → **Fase 2** testbench HDL
> full-dataset + utilizzo post-route completo (incl. BRAM) → **Fase 3** `create-report`. La **Fase C** (test
> sull'FPGA *fisica*) resta separata. Backlog dopo B2.0: timing study · quantization study · MPC. Stato/dettaglio
> completo in `SESSION_RESUME.md` §AZIONE PENDENTE.

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
- **⚠️ WRAPPER AXI + POTENZA + SIM DI NETLIST — 10 trappole verificate in T6b (2026-07-30).** Chi rifà un harness
  hardware (T7, Fase C) le trova tutte:
  1. **`ce_out` di HDL Coder è un CLOCK-ENABLE, non un `done`.** Misurato: alto **1500/1500 cicli**. Usarlo come
     valid fa leggere al PS parametri **non pronti**. Il `done` si fa con un **contatore di latenza** tarato sul
     valore MISURATO (Tier@BAL: uscita valida a **commit+365**; si latcha a +371 per margine).
     ⚠️ Latchare *esattamente* alla latenza cattura il valore **precedente** (il non-blocking legge il pre-fronte,
     e l'uscita si aggiorna su quel fronte): sintomo = **100 % di mismatch** con valori *plausibili*.
  2. **Il blocco va tenuto IN RESET fino al primo commit.** Senza, all'uscita dal reset gli ingressi passano da
     indefinito a 0, l'edge-detector vede un fronte e parte un'**inferenza spuria** che avanza lo stato (`hdl.RAM`)
     e disallinea tutto. Misurato: uscita a cyc 379 con reset a 16 (= 16+364), *prima* del commit. È anche il
     comportamento corretto in campo: l'acceleratore sta fermo finché il PS non gli dà lavoro.
  3. **`BUFGCE` in simulazione richiede `glbl` COMPILATO** (`xvlog <vivado>/data/verilog/src/glbl.v`) oltre a
     `-L unisims_ver`; altrimenti *"'glbl' is not declared"* / *"Cannot find design unit work.glbl"*.
  4. **La sim di TIMING va girata al clock per cui la netlist è stata IMPLEMENTATA.** Pilotarla più veloce produce
     violazioni di setup ⇒ risultati sbagliati che sembrano un difetto del design (100 MHz su netlist da 52 MHz →
     250/250 mismatch). Il periodo deve essere un **parametro esplicito** (`CLKHALF`), non una costante nel TB.
  5. **`-debug typical` è OBBLIGATORIO per il SAIF.** Con `-debug off`: *"compiled without trace information"* e
     `open_saif`/`log_saif` **non producono alcun file** — silenziosamente, se non si controlla l'artefatto.
  6. **`report_power` calcola la potenza dei net di CLOCK dal VINCOLO di frequenza, non dall'attività del SAIF.**
     ⇒ un clock **gatato** risulta invisibile: gatato e non gatato danno numeri **identici**. Verificato anche in
     negativo: imporre `set_switching_activity -toggle_rate 0` sui net del clock **non cambia nulla**.
     Il gating si prova guardando i **conteggi nel SAIF** (`clk_tier`: `TC 400 → TC 0`), non il sommario.
  7. **La potenza NON compone linearmente fra fasi.** `P_media ≠ P_att·d + P_idle·(1−d)`: misurato 0,015 W contro
     0,0094 W composti a duty 3,85 %, con lo scarto **localizzato sui DSP** (probabile dipendenza dalla *static
     probability*, non solo dal toggle rate). **Rimedio: misurare al duty REALE** simulando un control-step intero
     (5,2 M cicli ≈ 12 min) — l'anomalia svanisce e il numero è diretto, senza formule.
  8. **La netlist post-place&route PERDE i nomi gerarchici interni**: i riferimenti `dut.u_x.segnale` nel TB vanno
     esclusi con un `ifdef` per la sim di netlist. I cancelli black-box (sulle sole porte) restano validi.
  9. **Git-Bash → wrapper `.bat`: due mutilazioni degli argomenti.** Un argomento che inizia con `/` viene
     convertito in path Windows (`/tb/dut=x` → `C:/Program Files/Git/tb/dut=x`) — si disattiva con
     `MSYS2_ARG_CONV_EXCL="*"`; e l'`=` **si perde** (stesso motivo per cui le macro del TB si passano via file
     `.vh` e non con `-d NAME=val`).
  10bis. **Un TB Verilog NON puo' leggere segnali interni di un DUT VHDL: `xelab` CRASHA** (Vivado 2026.1).
     Sintomo: `ERROR: [XSIM 43-3294] Signal EXCEPTION_ACCESS_VIOLATION received` con stack in
     `ISIMC::VlogCompiler` — un **crash**, non un errore diagnostico: non dice che cosa non gli piace.
     Isolato in T7a con tre prove: (A) `-debug typical` crasha uguale ⇒ non e' il livello di debug;
     (B) lo stesso TB con i riferimenti gerarchici esclusi da un `ifdef` elabora ⇒ la causa sono i
     riferimenti; (C) lo **stesso** TB su DUT generato in **Verilog** elabora e gira.
     ⇒ **Se il TB deve leggere segnali interni, generare il DUT in Verilog** (`rtl_gen_dut(...,'Verilog')`),
     cosi' l'accesso e' Verilog→Verilog. Le porte del top restano identiche nei due linguaggi.
     *(Conclusione coincidente con l'avviso nel docstring di `rtl_gen_dut` — «il controllore con l'IIDM va
     in Verilog» — ma per una ragione DIVERSA: la' erano i metavalue a time-0, qui l'accesso gerarchico
     cross-language.)*
  10. **`add_files` nel Tcl ri-parsa la stringa come LISTA** ⇒ un path con spazi si spezza (*"File or Directory
     'D:/Project_MBSE/1.Reti' does not exist"*). Rimedio: **copiare i sorgenti in una work-dir corta** e usare
     `[list "$dir/$f"]`. Corollario: `write_verilog -mode timesim -sdf_anno true` **incorpora già**
     `$sdf_annotate` nella netlist → **niente `-sdfmax`**, basta che l'SDF sia nella dir da cui gira xsim.
- **⚠️ LEZIONI DI PROCESSO da T6b (2026-07-30) — costate un ciclo ciascuna, valgono per ogni harness:**
  - **Negli script di verifica NON si filtra l'output diagnostico del testbench.** Tre volte in una milestone ho
    perso un giro per `> /dev/null`, per una variabile catturata e mai stampata, e per un `grep` limitato a
    `ERROR|FATAL`: scrivo il filtro pensando al caso VERDE, mentre serve nel caso ROSSO. Si limita la lunghezza
    (`head -20`), non il contenuto.
  - **Un cancello verifica l'ARTEFATTO, non una proxy.** Il mio runner stampava «idle raggiunto» 3 volte su 3
    mentre **nessun SAIF veniva creato**: controllava una riga di log invece dell'esistenza del file. Da lì si
    sarebbero generati report di potenza da SAIF inesistenti, con Vivado che ricade su stime *vectorless* e numeri
    perfettamente plausibili.
  - **Per diagnosticare, guardare i VALORI che discriminano, non indizi indiretti.** La prima ipotesi
    (off-by-one) era supportata da una misura di *timing* compatibile con essa **e con altre**: la correzione non
    cambiò nulla. Il dump di `letto / latch / uscita-DUT / golden` separò le due cause reali in un colpo.
  - **Misurare il costo prima di impegnare ore** — regola scritta nel piano e violata una volta (3 traiettorie
    post-route lanciate senza cronometrarne una: 22 min/traiettoria scoperti dopo). Applicata bene altrove
    (probe del golden, punto singolo dello sweep FCLK, pre-flight della run a duty reale).
  - **☠️ OGNI BLOCCO DICHIARATO «PRESCELTO» DEVE AVERE UNA PROPRIA SINTESI. L'idoneità HDL NON si eredita
    dai componenti.**
    **Il fatto:** `Donatello_SNN_IIDM` è stato creato il **2026-07-28** (T4) e dichiarato il controllore
    prescelto. Dalla sua creazione fino al **2026-07-30 (T7b)** **non è mai stato sintetizzato una volta**:
    verificato, **zero** occorrenze di quel top in tutti gli script `.tcl` del repo. La sua idoneità era
    ereditata dai componenti.
    **Il costo:** il suo cammino critico va dal registro del decoder del Tier, **attraverso `align`**, fino a
    un registro dentro l'IIDM — **27,5 ns = 36,4 MHz**, contro i ~50 del Tier e i ~78 dell'ACC-IIDM
    **presi singolarmente**. Un cammino che **nessuno dei due componenti aveva**: l'ha creato la composizione.
    Rimosso con un registro di pipeline sul confine → **61,8 MHz** (+70 %), e il cammino critico si è spostato
    **dentro la SNN**, cioè dove deve stare. Costo: +233 FF e +1 clock di latenza (554 → 555); valori
    invariati (un registro di pipeline sposta i tempi, non i numeri).
    ⚠️ **Il registro va su TUTTI i rami che devono restare sincroni** (qui 9: 4 fisici allineati + 5
    parametri). Ritardarne una parte li desincronizza di un clock — che è esattamente il doppio-fronte che
    `align` esiste per impedire.

    **Perché nessuna verifica precedente poteva vederlo — e perché NON è una scusa:**
    lo studio di quantizzazione **ha** sintetizzato, ed è per questo che le sue metriche di risorse sono
    valide: ma ha sintetizzato i **componenti** (`Donatello_Tier`, ACC-IIDM standalone), e quando girava
    (fino al 2026-07-27) **il composto non esisteva ancora** (creato il 28). T7a, dal canto suo, ha fatto
    **58 522 confronti bit-esatti tutti verdi**: un cammino combinatorio lungo non altera **un solo bit**,
    sposta solo i tempi, quindi nessuna verifica funzionale — per quanto esaustiva — può rilevarlo.
    **La sintesi è l'unico livello che lo vede.**

    ⇒ **REGOLA.** Quando un blocco viene dichiarato prescelto/deployato — e a maggior ragione se è una
    **composizione** — la sua caratterizzazione va rifatta **su di lui**, non ereditata:
    1. **sintesi OOC del blocco stesso** (~5 min) al momento della dichiarazione;
    2. **confronto dell'Fmax col MINIMO di quelle dei componenti**: se è sensibilmente più bassa, il confine
       fra i componenti non è registrato — è il sintomo, e va inseguito col `report_timing` del cammino
       critico, che dice **attraverso quali moduli** passa;
    3. il numero va nella scheda del blocco, così che «prescelto» significhi «caratterizzato», non
       «assemblato da pezzi caratterizzati».
    *(Trovato in T7b il 2026-07-30, due fasi dopo la composizione. Con la libreria a 8 blocchi e più
    versioni dello stesso componente, caratterizzare i pezzi al posto del prescelto non è ammissibile.)*
  - **L'etichetta di qualità di uno strumento non è una prova di qualità.** `RESULTS_HW.md` riportava
    «Confidence = High» come se avallasse i watt; è invece una **soglia di copertura** (>25 % dei nodi interni
    forniti), e il SAIF copriva il **56 %** dei net — il 44 % era stimato dal tool. Il caveat mancava del tutto
    nella fonte, e da lì era passato nel report. **Leggere che cosa *misura* l'indicatore di qualità**, non
    accontentarsi del suo valore. *(Trovato dall'audit avversariale del report, 2026-07-30.)*
  - **L'aritmetica nei documenti di sintesi va RICALCOLATA, non ricopiata.** `RESULTS_HW.md` conteneva
    «22 min/traj ⇒ ~12 ore per 60» (sono **22 ore**) e un «≈15× più lento» mai ricavato dai tempi misurati
    (sono **~29×**); e «58,6 MHz» dove `1/17,081 ns` = **58,5**. Tre errori in una riga di prosa, ereditati
    dal report perché la fonte è considerata affidabile. **Un audit del report deve verificare contro gli
    artefatti grezzi, non contro il documento di sintesi** — altrimenti conferma l'errore invece di trovarlo.
- **⚠️ Generare HDL da un blocco MASCHERATO (Variant Subsystem) — 4 trappole, verificate su `Donatello_Tier` in
  T6a (2026-07-29).** I pattern che funzionavano per `Donatello_Champion` (chart singola, gerarchia piatta) **NON
  valgono** per un blocco mascherato e gerarchico. Le quattro, in ordine di scoperta:
  1. **`find_system` non guarda sotto la mask** → contare gli Inport/Outport così dà numeri sbagliati (ingressi non
     collegati → *"Simulink is unable to determine sizes and/or types"* dalla chart). Usare **`get_param(blk,'Ports')`**
     e **`save_system` PRIMA di `set_param(mdl,'SimulationCommand','update')`** (l'update risolve la variante).
     Per selezionare la variante: `set_param(sub,'TIER','BALANCED','NFRAC','13')` prima di `makehdl`
     (con `VariantActivationTime='update diagram'` genera **solo** quella).
  2. **Ordine di compilazione VHDL = BOTTOM-UP, non alfabetico.** Con gerarchia profonda
     (`Donatello_Tier → VS → BALANCED_n13 → {SNN → DualPortRAM, DEC}`) l'ordine alfabetico fa fallire `xvhdl`
     (*"'snn' is not compiled in library 'work'"*) e poi `xelab` (*"Module not found"*). L'ordine giusto si legge
     dal **log di `makehdl`** (`Working on … as X.vhd` è già foglie→top); ordinare per `datenum` **non funziona**
     (i file hanno timestamp identici).
  3. **Lo stato SNN vive nella `hdl.RAM` (DualPortRAM): il `reset` a runtime NON la azzera** — solo l'**init di una
     simulazione**. Conseguenza per i testbench: concatenare più traiettorie in **una** simulazione dà risultati
     corretti solo per la prima (misurato: 49948/55000 mismatch); serve **una simulazione xsim per traiettoria**
     (compilare una volta, poi `xsim -R` in loop → costo trascurabile).
  4. **Fix senza root cause = tempo perso**: il "reset per-traiettoria" è stato applicato *prima* di aver capito (3)
     e non ha funzionato (4996/10000). Prima il **meccanismo**, poi il fix.
  **Metodo che ne segue**: prima di scrivere un piano d'implementazione HDL, **verificare con probe mirati** le
  assunzioni riusate da un caso precedente (il generatore regge il NUOVO blocco? il TB regge mask/gerarchia/stato?).
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
- **⚠️ Conversione MATLAB-to-dataflow: una MATLAB Function che CONVIVE con blocchi Simulink cambia le regole
  (VERIFICATO 2026-07-17, SP4-M-FSM)**. Se nel *subsystem* c'è **solo** la chart (tutti i blocchi
  `Donatello_*`, `Donatello_ACC_IIDM`), HDL Coder usa il flusso `MATLAB Function` e genera. Se la chart
  **convive con altri blocchi** (SP4-M: chart + `HDLMathLib/Divide` + Unit Delay), HDL Coder applica la
  **conversione MATLAB-to-dataflow** per ottimizzare attraverso il confine chart↔blocchi — e quel flusso ha
  vincoli **molto più stretti**, che il flusso normale non ha:
  | vincolo dataflow | messaggio | nel flusso normale |
  |---|---|---|
  | struct di prototipi con campi **vuoti** (`fi([])`, come `snn_types`/`acc_types`) | *"Struct in expression 'T' has an empty-typed field"* | OK (basta `fi(0,…)` per aggirarlo: equivalente, `cast 'like'` usa solo numerictype+fimath) |
  | `persistent` in funzione **non-entry-point** chiamata >1 volta o in un condizionale | *"Non-top-level functions with persistent variables may be invoked only once"* | OK (lo stato può stare nella funzione) |
  | `divide()` con argomenti **variabili** | *"not supported unless all of its input arguments are constant"* | OK (è ciò che usa SP3) |
  | **`tanh` in fixed-point** | *"not supported for 'numerictype(1,19,8)' inputs. Provide a floating-point input"* | **OK — SP3 genera `tanh` fixed nativamente** |
  **NON dipende dall'architettura del blocco**: `hdlget_param(chart,'Architecture')` dava già `MATLAB Function`
  (il default del fixed-point) e la conversione avveniva lo stesso → non si disattiva da lì.
  **Prova della causa** (non inferenza): la STESSA chart, messa **da sola** in un subsystem con soli
  Inport/Outport, genera VHDL con **0 errori**; col `Divide` accanto, fallisce.
  **Conseguenza di design**: un blocco che deve restare **bit-exact** e usa `tanh`/`divide` fixed **non può**
  convivere con blocchi Simulink nello stesso subsystem. Se serve un'unità HDL esterna (es. un divisore
  pipelinato), o si rinuncia alla bit-esattezza (LUT/float = approssimare) o si porta quell'unità **dentro**
  la chart. È ciò che ha ucciso l'approccio "FSM + blocco Divide" di SP4-M
  (`document/SP4_ACC_IIDM_FAST.md` §Variante M-FSM).
- **⚠️ Composizione estimatore→controllore: gli ingressi del controllore devono cambiare SINCRONI
  (VERIFICATO 2026-07-27, banco `snn_lib_dataset_test`)**. `ACC-IIDM` è edge-triggered (`go = any(x≠xprev)`):
  1 cambio d'ingresso = 1 inferenza, e l'OU (stima `a_l`) aggiorna **una volta** per inferenza. Se lo si compone
  DAL VIVO con `Donatello_Tier`/`Donatello_LUT` (estimatore→params), i 4 ingressi FISICI cambiano a inizio
  control-step ma i 5 PARAMS arrivano ~405 clock dopo (quando l'estimatore time-mux finisce) → **DOPPIO edge** →
  l'OU aggiorna **due volte**/control-step → diverge da `acc_iidm_open` (che aggiorna una volta), in silenzio.
  Per **testare** il blocco si sincronizzano tutti i 9 ingressi (params precalcolati, held come i fisici) = l'uso
  previsto dell'interfaccia (banco: `dmax=0` vs `acc_iidm_open`). Per **comporre** estimatore+controllore sull'FPGA
  serve un handshake "params pronti" (un `valid` dell'estimatore che triggera il controllore) **non presente nei
  blocchi attuali** → candidato di design per il sistema in anello (V2I).
- **Workflow della libreria dopo il riordino (2026-07-27)**: `build_hdl_variants.m` costruisce TUTTI i blocchi
  Donatello (Champion + LUT{16..512} + ACC_IIDM + ACC_IIDM_M); `reorg_library.m` poi RIMUOVE i singoli assorbiti
  (Champion, LUT{N}, SLOW/BALANCED/FAST, SP3) lasciando il set-milestone di 8 blocchi. **Ri-eseguire
  `build_hdl_variants` RI-AGGIUNGE i singoli** → va sempre seguito da `reorg_library`. Il blocco `Donatello_LUT`
  combinato (popup NLUT) lo costruisce `build_lut_configurable.m` (architettura **splitpipe** attuale, non lo
  `split` degli studi LUT; bit-exact al riferimento — `run_lut_ref_gate`); i tier li combina `build_tier_configurable.m`.
