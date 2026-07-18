# SESSION_RESUME.md — Quick context for any new Claude session

> **Scopo**: in 5 minuti capire **dove siamo**, **cosa è stato fatto**, **cosa fare adesso**.
> Aggiornare ad ogni milestone (1 sezione "Stato attuale" sempre aggiornata, log storico in coda).

---

## ▶ RIPRESA A FREDDO — LEGGERE QUESTO BLOCCO PER PRIMO (agg. 2026-07-18)

> **Ruolo di questo file:** punto d'ingresso + **STATO** del track `Simulink_Importer`. NON è la procedura
> generale (quella è la skill `session-reprise`). È un **guida ai documenti**: quando dice «leggi X», leggi X —
> non ricostruire a memoria.

**Repo/posizione:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulink_Importer`,
branch **`Simulink_Importer`**. **Tutto committato e pushato**, working tree pulito (restano solo file
dell'utente: `closed_loop_demo.slx` modificato-non-mio [`M`], `slblocks.m` + i `*.mexw64` untracked [`??`] — **NON
toccarli né stagearli**).
*(Esistono altri track/worktree — es. `Simulator`, `main`/EventProp — con LORO SESSION_RESUME: questo file vale
solo per `Simulink_Importer`.)*

**Stato in una riga:** SP2/SP3 chiusi, **debito Fase B risolto** (bitstream escluso), e **✅ SP4 CHIUSO
(2026-07-17)**: il blocco `Donatello_ACC_IIDM_M` porta il controllore completo da **2,0 a 9,30 MHz** con
**area −21%** (8614 LUT · 2134 FF · **71 DSP**; BRAM **non catturato** nel run OOC → si misura in Fase B2.0),
**`dmax = 0`** e **timing chiuso** @8 MHz. Il bersaglio 11,65 **non è raggiunto ed è dimostrato
irraggiungibile** per questa strada (era simmetria con la SNN, non un requisito: 358 clock su 800.000 per
control-step). Riferimento SP3 e **deployato intatti**. **Ri-verificato in questa sessione (2026-07-17) sulla
libreria committata**: il blocco è **aggiornato + self-contained + HDL-ready** — 13 funzioni-fase inlinate,
gate isolato `run_block_hdl_gate` PASSATO (4 VHDL, DualPortRAM presente, 0 errori) col path `matlab/` rimosso;
gate reso sensibile anche alle dipendenze di M (commit `ab232fc8`). ⚠️ Questi numeri sono **OOC + livello
Simulink**: la prova RTL (testbench HDL) è la Fase B2.0 qui sotto.

**✅ 2d CHIUSO (2026-07-18) — timing SNN→decode + pipelining del core SNN.** Dentro B2.0: **R1-R2** hanno
portato il controllore **10,58 → 15,84 MHz** (split readout↔decode + reci adder-tree) → il collo LASCIA la
SNN e diventa il **divisore IIDM**. Il **probe** ha misurato il tetto SNN (~29 pre-pipeline) e provato che il
controllore è cappato dalla LEGGE IIDM (divisore 15,84 + sqrt 17,30), NON dalla rete. Decisione utente:
esaurire prima la SNN → **R3-R9 hanno pipelinato il core SNN forward a 99,16 MHz (3,33×)** — 8 stadi
(`R→Cx→Cm→Ca→C1→C2i→C2a→C2b`), **bit-exact** (`run_b2_parity_dataset` 0/60000 OGNI round), **BANCATO** per
dopo l'IIDM. Convergenza a 99 (ogni stadio è già 1 op larga ~7-10ns = pavimento aritmetico; ~130 possibile
ma senza payoff: SNN già 6,3× il cap IIDM). **Controllore validato** con l'SNN 8-stadi: parity 0/60000 +
**B-1 0/3000**, Fmax **15,67** (invariata, IIDM-capped; −1% da +1069 FF). Dettaglio: **SP4 §Studio 2d** +
`matlab/hdl_snn/RESULTS.txt`. Harness: `run_2d_round.m`, `probe_snn_fwd.m`, `probe_snn_ceiling.m`. Core
8-stadi in `matlab/snn_b2_fsm.m`. **→ PROSSIMO FRONTE per alzare DAVVERO il controllore = pipeline
dell'IIDM (divisore + s_star/sqrt), fixed-point** — la SNN non è più il collo. (2c gate esaustivo full-60k
resta prima del deploy.)

**AZIONE PENDENTE — 🟢 FASE B2.0 APERTA (2026-07-17): validazione RTL della versione FPGA + report.**
Decisa dall'utente. SP4 ha *ottimizzato* il blocco; **B2.0 prova che l'RTL generato funziona davvero** e ne
scrive il report. La **Fase C** (test sull'FPGA *fisica*) resta separata e in attesa.

> **Perché B2.0 esiste — il gap, in una riga:** oggi è provato **a livello Simulink/MATLAB** (`dmax=0`: G2
> 0/60000, G3/G4 5/5; `makehdl` *genera* il VHDL) ma **NON a livello RTL**: il VHDL generato **non è mai stato
> simulato in un simulatore HDL** (xsim) contro il riferimento, sull'**intero dataset**, con metriche vere. Finché
> non lo è, "versione FPGA" è una claim Simulink travestita — **è l'errore Fase B** (report su traiettoria ridotta,
> poi corretto). B2.0 lo chiude.

**Piano (una fase alla volta):**
- **Fase 0 — allineamento doc:** ✅ in corso/fatto (questo blocco + HDL_PHASE §6/§8 + SP4 box + memoria).
- **Fase 1 — `/fpga-expert`:** ✅ FATTO. Audit: oltre 9,30 MHz c'è margine **bit-exact** (retiming/pipelining di
  `tanh`+SNN→decode) = lo Studio Timing, incluso in B2.0 per scelta utente. Studio RTL disegnato: 2 harness
  (SNN + controllore), closed-loop self-contained per il controllore. Spec `docs/…/2026-07-17-b2.0-rtl-validation-harness-design.md`.
- **Fase 2 — evidenza RTL (a DUE harness, plan `docs/…/2026-07-17-b2.0-2a-m1-core-harness-snn.md`):**
  - **2a-M1 (core + Harness A, SNN `Donatello_Champion`):** ✅ **FATTO 2026-07-18** — A-1 **0/15000** (RTL bit-exact
    al blocco su 3 traj), cancello sensibile, metriche param. Commit `c961bc85`. ⚠️ **Finding:** il golden r16 non
    è il blocco (diverge a step ~52: `local_normalize` fixed + pilotaggio a ingresso tenuto) → costruito golden
    **fedele al blocco** `snn_traj_champion` (== blocco, cross-check dmax=0). Dettaglio in `HDL_PHASE.md` §6.
  - **2a-M2 (Harness B, controllore `Donatello_ACC_IIDM_M`, open + closed-loop):** ✅ **FATTO 2026-07-18**
    (commit `f3847650` open, `c78872dc` closed). **B-1** RTL accel == blocco **0/3000** (open-loop, 3 traj);
    **PLANT-PAR** plant-nel-TB == riferimento **1800/1800** (sensibile); **B-LOOP** anello RTL == riferimento
    **2400/2400** + **BEHAV** gap>0 sempre (car-following corretto, non solo bit-exact). Golden-fedele
    (`acciidm_m_traj`, algoritmo estratto). ⚠️ **DUT in VERILOG** (il divisore combinatorio IIDM manda un
    indice-LUT a -1 a time-0 in xsim col VHDL, registri U; Verilog init a 0). Plan `docs/…/2026-07-18-…-m2-harness-b.md`.
    Resta (piccolo): caratterizzare l'impatto della deriva blocco-vs-deployato (local_normalize) sul car-following.
  - **2b (ottimizzazione timing `tanh`)** — **F1 (probe pipelining AUTOMATICO) = FAIL, provato in modo esaustivo
    (2026-07-18).** Il `tanh` fixed è un **monolite combinatorio** (path `st_dd_12 → thl_7`, **201-207 liv**,
    `IIDM_CTRL.vhd` = 984 KB tutto combinatorio): HDL Coder `DistributedPipelining`/`ClockRatePipelining` mettono i
    registri **all'uscita** (barriera *"delays not moved across due to non-zero/unknown initial value"* della
    chart-FSM) → **0%** (9,30); il retiming di **Vivado** (`synth_design -retiming`, op4/80ns **e** op8/40ns =
    **identici**) rialloca il solo registro `thl` di 6 liv → **+2,4% (9,52 MHz), tetto** (gli altri registri sono
    bloccati dietro lo stato `acc`). **Non è il periodo di clock** (il path ~107 ns è logica reale). Infra probe:
    `matlab/probe_pipe_tanh.m` (commit `983c4c33`); sintesi OOC via `scripts/synth_acc_iidm.tcl` da **work-dir
    SENZA spazi** `D:/zbd_pipe` (⚠️ la tcl con `glob` su path con spazi fallisce — copiare il VHDL lì e sintetizzare);
    `D:/zbd_pipe/retime_test.tcl` per il retiming; numeri in `matlab/hdl_pipe/RESULTS.txt` (gitignored). Dettaglio +
    tabella in `SP4_ACC_IIDM_FAST.md` §Studio 2b. Spec/plan `docs/…/2026-07-18-b2.0-2b-timing-*`.
    **Esp. A — reimplementazione `tanh` = ✅ CHIUSO (2026-07-18):** studio comparativo a 5 vie (native/LUT-piena/
    LUT-interp/poly/CORDIC), 2 livelli (L1 tanh-solo, L2 controllore). **Vince A1 = LUT PIENA bit-exact**
    (memoizza il `tanh` nativo, `gen_tanh_lut`): dmax=0 su 20000, L1 136 MHz / 8 liv / 0 DSP, più piccola del
    nativo. **A1 INTEGRATA** in `Donatello_ACC_IIDM_M` (`iidm_tanh`→`tanh_lut_full`, inlinata da
    `build_hdl_variants`; commit `2398d5d6`). **L2: controllore 9,30 → 10,58 MHz (+14%), bit-exact, area
    8614→7249 LUT (−16%), DSP 71→69; nuovo collo = `pR_idx→pv_3`, 172 liv = SNN→decode** (il `tanh` non è più il
    collo). Dettaglio+tabella: `SP4_ACC_IIDM_FAST.md §Studio 2b`; numeri in `matlab/hdl_tanh/RESULTS.txt`.
    Validazione fatta: dmax=0 + **B-1 ridotto 0/3000** + HDL 0 errori + L2. ⚠️ **Gate esaustivo RINVIATO**
    (B-1 full 0/60000 · A-1 · PLANT-PAR · B-LOOP · parity 0/240000): da eseguire prima del deploy finale.
    ⚠️ **Gotcha ambiente:** `bash`→WSL rotto (sospensione) → lanciare gli harness xsim con **Git Bash in testa al
    PATH** (`C:\Program Files\Git\bin`). (L'Esp. B "registri a mano nel netlist" non è stato fatto: A1 già risolve.)
    **→ [SUPERATO] il fronte SNN→decode = Studio 2d, ✅ CHIUSO 2026-07-18** (R1-R9): SNN forward pipelinato a
    99,16 MHz bit-exact; controllore 15,84→15,67 (cappato dal divisore IIDM). Vedi il box «2d CHIUSO» in cima.
  - **2c (validazione COMPLETA full-dataset 60k + gate-level)**: dopo il fronte SNN→decode / prima del deploy.
    Riusa gli harness A+B con `mode` full + il gate esaustivo rinviato sopra.
- **Fase 3 — `create-report`:** grounded sulla Fase 2 (tecniche: time-mux, FSM a stadi, registro-fra-stadi; drawback).

**Backlog (studi a sé, DOPO B2.0):** 1) **Timing study** (spingere lo slack → max Fmax); 2) **Quantization study**
(meno bit fixed → meno FPGA vs perdita accuracy, mappa non-lineare — grande); 3) **Fase C + confronto MPC↔SNN**
(design parcheggiato, `cf-fsnn-mpc-vs-snn-design`). Restano anche le opzioni di track: promuovere M a deploy · V2I
in Simulink · merge → main.

**Se si torna su SP4, LEGGI PRIMA** `document/SP4_ACC_IIDM_FAST.md` (in testa: il riquadro ✅ SP4 CHIUSO, poi
§Variante M-FSM #2a): contiene i numeri, le **quattro strade chiuse coi loro perché** (L approssima · M-v1
area esplosa · #1 dataflow/`tanh` · #2b e #2c escluse dal probe) e cosa si riusa. I vincoli della conversione
MATLAB-to-dataflow, che valgono **oltre SP4** per qualunque blocco bit-exact, sono in `document/HDL_PHASE.md` §9.

⚠️ **Non ripetere**: #2b (divisore sequenziale a mano) e #2c (tanh CORDIC) sono **esclusi dai dati**, non da
un'opinione — la divisione non compare in nessun path critico misurato, e col `tanh` a costo zero il tetto è
10,58 con il collo **fuori dall'IIDM** (SNN→decode = il deployato).

MATLAB: `"C:\Program Files\MATLAB\R2026a\bin\matlab.exe" -batch`. Vivado: `C:\AMDDesignTools\2026.1\Vivado\bin\vivado.bat`.

**MODI DI LAVORO (vincolanti — la sessione li ha pagati a caro prezzo):**
- **Verifica sul DATASET, mai su un caso singolo** — riporta *quanti su quanti* (es. 0/240.000, 5/5).
- **Un cancello che non può fallire non è un cancello**: deve `assert`, e va **provato sensibile** (rompilo apposta).
- **Una claim scritta in un doc/commit/Description è una claim da VERIFICARE**, non un ragionamento da dichiarare
  (in questa sessione 4-5 mie deduzioni plausibili sono risultate false alla misura).
- **Root cause prima del fix**; se un loop `fi` è lento → **MEXalo**, non ridurre il campione.
- Il messaggio VERO di un errore di chart si ha da `codegen('-config:lib',…,{a,a,a,a})` con `a=fi(0,1,32,20)`,
  non da Simulink. Gotcha fixed-point in `document/SP3_ACC_IIDM_HDL.md` §insidie.
- **Design prima del codice** (`brainstorming → spec → piano → esecuzione`). Doc aggiornati nei **doc di processo**,
  non solo qui. Commit **conventional SENZA `Co-Authored-By`**; push libero su `Simulink_Importer`.

**TONO:** italiano, deciso, **evidence-first**, onesto fino all'osso (ammetti gli errori, smaschera le claim non
verificate anche tue, niente compiacenza). Conciso; quando una scelta è dell'utente, chiedi con un'opzione
raccomandata; quando puoi decidere sui dati, decidi e mostralo.

**Dopo aver ricostruito lo stato: riporta (stato · azione pendente · modi di lavoro · tono) e ASPETTA il via.**

---

## 🔴 BUG DEL FORWARD DEPLOYATO — TROVATO E CORRETTO (2026-07-14) — LEGGERE PER PRIMO

> **`snn_b2_fsm` (il forward del bitstream) NON era bit-exact a `snn_core`**: divergeva sull'**82,4 %** dei
> control-step del dataset (60/60 traiettorie). Era invisibile perché i cancelli sono **profondi 16 campioni**
> (`run_b2_parity`) / **12 control-step** (`test_b2_fsm`) su un uso reale di **1000**, **non assertano** (stampano e
> basta) ed erano **dipendenti dall'ordine** (ROM globale non rigenerata).
> **Causa**: `snn_b2_fsm.m:77` castava `(Ii+reci)` da `accw` Q8.17 a `T.V` Q5.13 **prima del confronto di soglia**.
> **Corretto**: ora **0 / 240.000** control-step (4 champion × 60 traj × 1000). **Costo: +5 LUT (+0,1 %)**.
> **Impatto funzionale del bug: −0,007 punti** di accuratezza → Fase B e le sue conclusioni **reggono**.
> **⚠️ Il bitstream attuale è STALE** (costruito con l'FSM difettosa) → da rigenerare quando serve.
> **Storia, prove e numeri → `document/HDL_PHASE.md` §2 (anello ②bis) e §2.1.** Commit `1e779e1`.
>
> **Cancelli nuovi (assertano, girano sul dataset):** `run_b2_parity_dataset` (60×1000×4) ·
> `run_block_sync_check` (i blocchi inlinano i sorgenti: becca quelli rimasti indietro) ·
> `run_block_traj_test` · `run_block_hdl_gate`.
> **Aperto**: i cancelli storici **non assertano** — tutti verdi oggi, ma l'assert va aggiunto (decisione utente).

## ✅ Blocchi libreria HDL-ready — FATTI (2026-07-14)

> `snn_champions_lib.slx` ha ora **7 blocchi Donatello SELF-CONTAINED e HDL-ready** (`Donatello_Champion` +
> `Donatello_LUT{16..512}`), accanto ai 4 comportamentali: forward **B2 time-mux** (come il bitstream), **I/O fisico**
> `s,v,dv,v_l → v0,T,s0,a,b`, **niente start/done** (FSM free-running interna), ~341 clock/inferenza.
> **Dimostrato**, non promesso: cancello **`run_block_hdl_gate`** → copia solo il `.slx`, toglie `matlab/` dal path,
> `makehdl` **genera VHDL** (con `DualPortRAM_generic` ⇒ time-mux) su `Donatello_Champion` e `Donatello_LUT64`.
> Funzionale: **dmax = 0** (bit-exact vs norm-float + `snn_core` + `snn_decode_hdl`). Commit `e399572`.
>
> **Dettagli → `document/DECODE_LUT_SWEEP.md` §6** · **regole/lezioni → `document/HDL_PHASE.md`** (§3.1 contratto
> d'interfaccia, §3.1.1 *l'architettura segue il sorgente*, §3.1.2 `start` scollegato = fallimento silenzioso, §9) ·
> **mappa cartella → `matlab/README.md`**.

**SP2 — FATTO** (2026-07-15, `a9fb61b`…`c66cc5d`): blocco **`Donatello_ACC_IIDM`** in `snn_champions_lib`
(campione LUT-64 + ACC-IIDM open-loop, `s,v,dv,v_l → accel`, **sola simulazione**). Matematica IIDM a **fonte
unica** (`acc_iidm_open.m`, usata anche dal plant closed-loop). Dettagli → **`document/SP2_ACC_IIDM.md`**
(leggere quello: qui solo stato + puntatori).

Cancelli, tutti verdi al 2026-07-15: `run_block_acciidm_test` **dmax = 0 su 5/5 traiettorie**, **verificato
sensibile** (variante mis-gated → 0.1836 → fallisce) · `run_block_closed_loop_test` **dmax = 0 su 10/10**
(anello CHIUSO su Simulink, 5 traj × 2 convenzioni di `dv`) · `run_plant_parity` · `run_block_sync_check` (8
blocchi, 0 stale) · `run_block_traj_test` · `run_block_hdl_gate` (`Donatello_Champion`, `Donatello_LUT64`).

**«NON sintetizzabile» ora è MISURATO, non assunto** (`415e596`): HDL Coder rifiuta il blocco con **14 errori**.
Causa radice = l'IIDM in **double** → forza l'architettura *MATLAB Datapath* → `tanh` e `min(v/v0,10)^4` non
supportati in double e, **di rimbalzo**, viene rifiutato lo struct `snn_types` (che nei blocchi HDL-ready passa).
Chi vorrà l'ACC-IIDM su FPGA non deve inseguire lo struct: deve portare l'IIDM in fixed.

**Anello CHIUSO** (`c3edeff`, `c66cc5d`): dato il leader (`x_l`, `v_l`) l'anello calcola gap e `dv`, li passa al
blocco e integra l'ego. Semantica **misurata su 60k campioni**: ⚠️ `dv` del dataset **non** è `v − v_l` della
stessa riga, è `v[k−1] − v_l[k]`; il generatore **non ha posizioni assolute né lunghezza veicolo**;
`s ∈ [1.25, 150]` col clip attivo nel **6,06%** dei campioni. **Ma la convenzione non morde**: in anello aperto
sul dataset intero la `dv` istantanea non degrada la stima (20.64% vs 20.97%, **−0.33 pp**) ⇒ l'anello
realizzabile su strada è utilizzabile. Nuovo kernel `snn_cl_step` (+MEX): un control-step della catena di
riferimento — i MEX esistenti macinano una traiettoria *già nota*, in anello chiuso serve passo-passo.

**SP3 — ACC-IIDM HDL-Ready. ⇒ COMPLETO (2026-07-16).** Doc di processo: **`document/SP3_ACC_IIDM_HDL.md`**
(leggere quello; qui solo stato + numeri chiave). Spec `docs/superpowers/specs/2026-07-15-acc-iidm-hdl-ready-design.md`
· piano `docs/superpowers/plans/2026-07-15-acc-iidm-hdl-ready.md`.
*Scopo:* chiude un **buco di equità** del confronto MPC (la legge ACC-IIDM appartiene al *nostro* controllore, ma
con l'IIDM in double il Piano 2 conterebbe solo la rete e ometterebbe la legge che produce `a_cmd`).

`Donatello_ACC_IIDM` è **HDL-ready**: IIDM in fixed (`acc_types`, **`nfrac=8`**), HDL Coder genera VHDL dal solo
`.slx` con `DualPortRAM`. `acc_iidm_open` **type-parametrico** (double = riferimento, `run_plant_parity`
invariato bit per bit). Budget derivato: `E_iidm` 0.156/0.834 < `E_snn` 0.272/1.484 (margine 1,75×; a `nfrac=6`
non passa ⇒ discrimina). ⚠️ **HDL-ready ≠ deployato**: il bitstream resta la sola SNN.

**Premessa SMENTITA (misurata):** «serve una LUT come per la sigmoide» era **falso**. `sqrt`/`tanh`/`x^4` sono
nativi in HDL Coder; la divisione passa con **`RoundingMethod='Zero'`**. `exp` è l'unica non generabile — motivo
per cui la sigmoide (σ=1/(1+exp(−x))) richiese la LUT ma `tanh` no. **Corretta la claim in SP2_ACC_IIDM.md,
spec SP2 §7, README** (era «sola simulazione / non sintetizzabile»).

**Numeri OOC (xc7z020 @8 MHz) — l'IIDM in fixed è CARO:**
| | LUT | DSP | Fmax | liv.logici |
|---|---|---|---|---|
| SNN sola | 3 872 | 52 | **10,6 MHz** ✓ | 172 |
| catena SNN+IIDM | 10 846 | 69 | **2,0 MHz** ✗ (WNS −373 ns) | **1 077** |

Risorse ×2,8, Fmax ÷5,3, a 8 MHz **il timing non chiude**. Causa misurata: le 4 divisioni srotolate in array
combinatorio (path critico dentro l'IIDM). **Funzionalmente regge** (a 2 MHz un control-step dura 200k clock,
l'inferenza 341). **Via d'uscita già identificata (SP a sé): i 4 divisori sono costanti entro il control-step →
reciproci una volta + moltiplicazioni** (`fpga-expert` ch09). Lo sweep a slack minima è previsto ma non ora.

**Gotcha superati (dettaglio in SP3_ACC_IIDM_HDL.md §insidie):** la **fimath è parte del tipo** (va nei prototipi
di `acc_types`, non `setfimath` sparse) · niente riassegnazione di tipo (`v0f` non `v0`) · niente sovra-escape
apici nella chart. Diagnosi errori chart: `codegen('-config:lib','SNN_ACC','-args',{a,a,a,a})` con `a=fi(0,1,32,20)`.

---

## SP4 — ACC-IIDM fast (recuperare l'Fmax). L CHIUSA · M-v1 (resource sharing) NON basta → **prossimo = FSM esplicita**.
Doc di processo: **`document/SP4_ACC_IIDM_FAST.md`** (leggere quello). Spec/piano in `docs/superpowers/`.
Problema (SP3): IIDM fixed a **2,0 MHz**, timing non chiude @8 MHz — 1077 livelli, **76% carry** dalle 5
divisioni combinatorie incatenate. Bersaglio **≥ 11,65 MHz** (pari alla SNN).

**Variante L (reciproci a LUT) — costruita e SCARTATA sui dati (2026-07-16, `457aa6c4`…`e2cb8062`).** Sweep
MEXato (12 s vs ~6 h; `acc_sweep_kernel` + `build_acc_sweep_mex`, bit-identico all'interpretato) su 60 traj:
**nessuna N rispetta il budget** `E_snn` (p99<0.272, max<1.484) e l'errore **NON converge** (max piatto ~4 m/s²,
p99 bottoma 0.59 a N=64 poi peggiora). Saturazione di range **esclusa** (verificato: solo `2·sab` di 0.006,
innocuo). Root-cause non stabilita (baco fixed-point o amplificazione `1/s_safe`→`z²`), ma **irrilevante per la
decisione**: un reciproco approssimato che alimenta `z²` è fragile per costruzione. L'infrastruttura L resta
committata e riusabile (`acc_recip_lut`, `acc_types.recipN`, `acc_div`, sweep+MEX); **SP3 invariato** (recipN=0
byte-identico, `run_plant_parity` 0.00e+00). Review-catch: divisore costante `DT` resta `divide()` (`nargin>=6`).

**M-v1 (resource sharing) — make-or-break ESEGUITO (2026-07-16, probe `6db20b0a`). ESITO: config NON basta → FSM.**
Verifica empirica (`probe_acciidm_sharing.m` + 3 sintesi OOC su xc7z020 @8 MHz). Il resource sharing di HDL Coder
**si attiva** (clock 5× `DUT_tc` + moltiplicatori condivisi + le 5 divisioni incatenate sequenziate in UNA): timing
**chiude @8 MHz** (WNS −373 → +20 ns), livelli **1077 → 172**, DSP **69 → 38**, `baseline` riproduce SP3 al bit.
**MA**: Fmax **9,5 MHz < 11,65** (collo = singola divisione digit-recurrence non pipelinata) **e area ESPLOSA**
(LUT ×2,36, FF ×13,9 dal clock-rate pipelining) → **contro la visione "taglia le risorse"**. Tabella completa in
`document/SP4_ACC_IIDM_FAST.md` §Variante M.
- **M-FSM #1 (FSM + blocco `Divide` HDL) — ESEGUITO 2026-07-17. ESITO: bit-identità PROVATA, ma STRADA MORTA.**
  Verde tutto ciò che riguarda la correttezza: **G1** blocco `Divide` == `divide()`-SP3 **dmax=0 su 300.000
  coppie reali** (sensibile: 'Nearest' → 1 LSB) · **G2** model FSM == `acc_iidm_open` **0/60000 control-step**
  (sensibile: q2↔q3 → 1990/2000) · **G3/G4** blocco M == model == SP3 su **5/5 traiettorie**, latenza
  **misurata 509 clk**, edge-triggered · plant parity ALL PASS. Il blocco `Donatello_ACC_IIDM_M` **esiste,
  compila e simula bit-identico a SP3 con UN SOLO divisore**.
  **MA non genera VHDL**, per una ragione strutturale: il blocco `Divide` deve stare accanto alla chart (in HDL
  Coder il divisore pipelinato esiste solo come blocco) → quella convivenza impone la **conversione
  MATLAB-to-dataflow** → che **vieta `tanh` in fixed-point** → ma `tanh` è nel cuore dell'IIDM → aggirarla =
  LUT/float = **approssimare** = `dmax≠0` = ciò che M esiste per evitare. **Non è un bug da tappare.**
  Prove (non inferenze): la stessa chart **da sola** genera VHDL con 0 errori; `Architecture` era già
  `MATLAB Function` (verificato); `snn_types→fi(0)` risolveva l'"empty-typed" e faceva emergere subito `tanh`
  → **core ripristinato, mai committato**. ⚠️ **Il verdetto OOC non è mai stato raggiunto** (fermi alla
  generazione): Fmax/area della strada FSM restano **ignoti**.
  Esito completo + cosa si riusa: `document/SP4_ACC_IIDM_FAST.md` §Variante M-FSM. Vincoli dataflow (validi
  **oltre** SP4): `document/HDL_PHASE.md` §9. Commit: `e31c6b3d`, `a910934f`, `02813818`, `f430aad0`, `c32a9619`.
- **RESTA l'approccio #2** (divisore **dentro** la chart) = l'unico rimasto → vedi AZIONE PENDENTE in cima.
  Si riusano **identici**: funzioni-fase (`iidm_prep`/`iidm_nd`/`iidm_use`/`iidm_final`), model `acc_iidm_fsm`,
  G2, G3/G4, e l'infrastruttura di verifica (`probe_divide_bitexact` 300k in 44s).
- Spec/piano del config-based (superati come esecuzione, utili come record): `docs/superpowers/{specs,plans}/2026-07-16-acc-iidm-timemux*`.
- **L insegna a M:** divisioni **sequenziate, non approssimate**; **M-v1 insegna alla FSM:** il config esplode
  l'area → la FSM deve sequenziare **1 divisore** a mano (area bassa), non delegare al clock-rate pipelining.

**Debito Fase B — RISOLTO in parte (2026-07-16, `4298adf3`).** `report/FPGA_PHASE_B_REPORT` + `results.csv`
**ri-sintetizzati col campione corretto** (decode-64 + fix §2.1), stesso flusso Fase B: LUT 4223→3868, Fmax
8.5→**11.65 MHz** (la σ-LUT più piccola accorcia il path), power ~invariata (static 103 mW); conclusioni
qualitative immutate. Colmato il gap del SAIF: `gen_saif_b2.sh` (era non-scriptato). ⚠️ **Il `.bit` NON è stato
ricostruito** (scelta utente = sintesi+power+report): il file su disco precede la correzione — nota di
provenienza aggiunta nel report. Rigenerarlo se/quando servirà flashare.

**Prossimi:** **ottimizzazione ACC-IIDM Fmax = SP4, IN CORSO** (⚠️ NB: l'idea «reciproci-una-volta» qui accennata
= variante **L, poi SCARTATA sui dati**; SP4-M usa l'opposto, divisione sequenziale esatta — vedi il blocco ▶ in
cima e la sezione `## SP4`) · **`.bit` Fase B** da rigenerare quando si flasha · **riordino fisico di `matlab/`**
(21 file caricano i `.mat` via `fullfile(here,…)` → riscrivere i path + ri-verificare) · **report** della
digressione LUT (`DECODE_LUT_SWEEP.md`
pronto) · **asserzioni nei cancelli storici** (verdi, sicuro aggiungerle — decisione utente in sospeso).

---

## 🗄️ STORICO — SUPERATO (era: RIPRESA Fase B/C, 2026-07-11). Il punto d'ingresso ATTUALE è il blocco ▶ in cima.

> **RUOLO DI QUESTO FILE:** è il **punto d'ingresso di ripresa + lo STATO** del track `Simulink_Importer` (NON la
> procedura generale — quella è la skill `session-reprise`). Chi riprende a freddo legge QUI e segue i puntatori.
> **Repo:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN` · **worktree/branch:** `Simulink_Importer` @
> `.worktrees/Simulink_Importer` · push libero su `origin`. (Il track ① Simulatore vive su `Simulator`, lo studio
> EventProp su `main` con master `EVENTPROP_STATUS.md` — QUESTO file copre SOLO il track ② HDL/Simulink_Importer.)

## 🗄️ STORICO — SUPERATO (era: RIPRESA B1.5 + Libreria champion, 2026-07-14). Punto d'ingresso ATTUALE = blocco ▶ in cima.

> **Stato più recente (in cima; il blocco Fase B/C sotto è il precedente).** ⚠️ Working tree: ci sono modifiche NON
> mie non committate (`matlab/closed_loop_demo.slx`, `matlab/slblocks.m`) + commit `mpc-vs-snn` di un altro filone —
> **non toccarli**. *(Cos'è quel filone: studio confronto **MPC↔SNN**, **solo fase di design, parcheggiato** —
> doc depositati qui ma non attivi: `docs/superpowers/specs/2026-07-13-mpc-vs-snn-comparison-design.md`
> (**Appendice A = record decisionale, leggere prima**) + `docs/superpowers/plans/2026-07-13-mpc-vs-snn-phase-a.md`.
> Eseguirà su un **suo worktree/branch**; le API del piano sono da ri-verificare dopo B1.5.)* Artefatti generati sono gitignored (`snn_traj_fixed_r*_mex.*`, `b2_rom_active.m`, `codegen/`, `slprj/`).

**B1.5 — validazione HW approfondita (Vivado/sim, pre-silicio).** Spec master (7 filoni → 4 sotto-studi a/b/c/d) =
`docs/superpowers/specs/2026-07-13-fase-b1.5-design.md`.
- **B1.5-a (fondamenta 4 champion + validazione funzionale)** — piano `docs/superpowers/plans/2026-07-13-fase-b1.5a-fondamenta.md`.
  **Task 0-4 FATTI:** `gen_b2_rom(name)`→`b2_rom_active`; `snn_b2_fsm` **rango-parametrico** (`rnk=coder.const(size(W.U,2))`;
  gate `run_b2_parity` = **0 mismatch su tutti e 4**, baseline rank-8 inclusi); validazione funzionale **via MEX**
  (`snn_traj_fixed.m`+`build_traj_mex.m` → `snn_traj_fixed_r{16,8}_mex`; `run_b15a_validate.m`; helper `champ_weights.m`).
  ⚠️ **GOTCHA: core `fi` interpretato = ~10h su 6 traj → OBBLIGO MEX.** `snn_core` reso codegen-safe (reset flag logico +
  init per-variabile `isempty` + assert bound), **parità 0 preservata**. Metriche 6-traj coerenti col SW (Donatello acc
  ~85%, Δfloat ≤0.09). **RESTA:** run completo **60-traj** (~24s), **Task Vivado 5-7** (sintesi/SAIF/cosim dei 4). Commit ~`0d759a7`.
- **B1.5-b/c/d** (quantizzazione post-hoc+1QAT / SEU 2-livelli registri+config / stabilità-fixed-in-loop·AXI-latency·PVT):
  solo nel master, **non ancora spec'd**.

**SP1 — Libreria champion, varianti di decode (LUT sweep).** Spec `docs/superpowers/specs/2026-07-14-champion-library-expansion-design.md`,
piano `docs/superpowers/plans/2026-07-14-sp1-decode-variants.md`. **Task 1-2 + sweep 60-traj + dimensionamento risorse FATTI:**
`snn_decode_lut(raw,N)` (N=256 **bit-identico** a `snn_decode_hdl`); `run_lut_sweep` (forward MEX + decode-LUT-N double,
**60 traj in 4.8s**). **Finding (definitivo, 60 traj):** accuratezza end-to-end **piatta ~84%** (83.97% da N≥64; N=16=84.06%
entro rumore) su N∈{16..512}; `dmax vs 512` converge **quadratico** (N=32→0.034, N=64→0.011); risorse = **N×16 bit** →
**< 1 BRAM18 anche a 512** → compromesso **soft**, LUT 32-64 basta (256 sovradimensionata ma economica). **Documento
sorgente per il futuro report = `document/DECODE_LUT_SWEEP.md`** (scopo+metodo+dati+risorse+onestà; commit `8f7f248`).
**Task 4 FATTO:** 6 blocchi streaming `Donatello_LUT{N}` (porte `xn`(4)+`start` → `params`(5)+`done`; interni
`snn_b2_fsm`+`snn_decode_lut`, **stile referenziato**) aggiunti a `snn_champions_lib.slx` via nuovo `build_hdl_variants.m`
(i 4 base invariati); **tutti e 6 simulano bit-exact** (dmax=0 vs `snn_core`+decode; l'`hdl.RAM` gira nella MATLAB
Function; done@≈341 clock). ROM Donatello via `gen_b2_rom('Donatello')`→`b2_rom_active` (gitignored, la rigenera il
builder). Commit `a4e8d15`. **Task 5 (HDL Coder) FATTO:** i 6 decode `snn_decode_lut(·,N)` generano VHDL (0 errori/warning,
conformance OK), sigmoide = **tabella costante (niente `exp`)**; tool `make_hdl_decode_lut.m`, commit `c888e86`.
**Task 3 (sintesi Vivado OOC) + Task 6 (figura) FATTI:** i 6 decode sintetizzati su xc7z020 (Vivado 2026.1) → **LUT
520→1732 con N, 0 BRAM, DSP=16, carry ~110** (la σ-LUT è logica distribuita, non BRAM); compromesso quantificato:
**LUT-64=734 vs LUT-256=1167 (~37% in meno) a pari accuratezza**. Figura `document/decode_lut_sweep.png`, script
`scripts/figs_lut_sweep.py`. **⇒ SP1 COMPLETO.** *(GOTCHA path: Vivado è in `C:\AMDDesignTools\2026.1\Vivado\bin\vivado.bat`,
NON in C:\Xilinx/AMD.)* Doc sorgente report = `document/DECODE_LUT_SWEEP.md`. Commit
`454327b`/`8f7f248`/`a4e8d15`/`c888e86`(+doc/figura). *(Skill `fpga-expert` disponibile. Prossimo: SP2 Donatello+ACC-IIDM open-loop.)*

**SP2 — Donatello + ACC-IIDM open-loop. ⇒ COMPLETO** (2026-07-15). Spec
`docs/superpowers/specs/2026-07-14-sp2-donatello-acc-iidm-design.md`, piano `docs/superpowers/plans/2026-07-14-sp2-*`,
**doc di processo `document/SP2_ACC_IIDM.md`** (leggere quello: qui solo il puntatore).

Blocco **`Donatello_ACC_IIDM`** in `snn_champions_lib`: `s,v,dv,v_l → accel`, campione **LUT-64** (non 256:
l'outline SP1 §5 precede la scelta del campione) + ACC-IIDM open-loop in **double**, loop velocità **aperto** come
richiesto. **Sola simulazione, NON sintetizzabile** (fixed+double): conseguenza accettata del blocco unico —
l'artefatto HDL-ready resta `Donatello_Champion`. Il `cf_plant_lib/ACC_IIDM` closed-loop **non è stato aperto**:
ora è `acc_iidm_open` + integrazione, cioè la stessa matematica a **fonte unica** (`run_plant_parity` invariato).

Cancelli: `run_block_acciidm_test` **dmax(accel) = 0 su 5/5 traiettorie**; latenza 340 ed edge-trigger **misurati**;
il test è **verificato sensibile** al mis-gating dell'IIDM (variante con l'IIDM a ogni clock → **0.1836 m/s²** →
fallisce). `run_block_sync_check` esteso: **8 blocchi, 0 stale**. Commit `a9fb61b`…`be19044`.

---

**FASE B (validazione del report FPGA) = CHIUSA.** Deliverable **`document/FPGA_PHASE_B_POWER.md`** (numeri +
tabella claim + re-tag + §9 protocollo Fase C + §8 fonti letteratura). Dati grezzi + CSV in
`matlab/axi/build/phase_b/` (`util_*`/`timing_*`/`power_*`.rpt, `results.csv`). Spec+piano:
`docs/superpowers/{specs,plans}/2026-07-10-fpga-phase-b-power*`. **Findings:** DSP 0→38 (elettivi, 0-DSP
realizzabile), Fmax 100-200→~8.5 MHz, **e_MAC≈e_AC su FPGA** (non 5× Horowitz), energia realizzata≫algoritmica
(static domina 92%), **vantaggio SNN ~5-65× ma da COMPATTEZZA modello** (letteratura NN car-following ~7k-100k MAC
vs SNN ~800), NON da AC≪MAC; termica non-problema (Tj~26°C). Bit-exact funzionale già provato (HDL phase, err=0).

**AZIONE 1 — Report Fase B (via skill `create-report`) — ✅ FATTA (2026-07-13).** Deliverable in **`report/`**
(scelta utente "sempre nella cartella report", NON in `document/` come ipotizzato sotto): `report/FPGA_PHASE_B_REPORT.{md,pdf}`
(14 pag) + `report/figures_phase_b/` (9 figure) + generatore `scripts/build_fpga_phase_b_report.py` (sorgente unica → md+pdf,
**deterministico**, ogni numero grounded su `matlab/axi/build/phase_b/results.csv`). Register impersonale, marker ●/○,
4 caveat onesti; audit indipendente superato (2 fix: §1 punto operativo 8 vs Fmax 8.5 MHz, Wang 2018); QC visivo + `.md`
byte-stabile. *(Specifica originale conservata sotto per tracciabilità.)*
- Sorgente = `document/FPGA_PHASE_B_POWER.md` (contenuto già assemblato) + `matlab/axi/build/phase_b/results.csv`.
- Template/stile = **`document/FPGA_REPORT.md`** + **`document/VALIDATION_REPORT_v3.md`** (⚠️ su QUESTO branch i
  report sono in `document/`; su `main` la documentazione è stata **riordinata** — i report spostati — e la
  **divergenza di layout si riconcilia al MERGE**. Qui, e per generare il report, leggi/scrivi in `document/`).
  Stessa procedura degli altri report.
- Contenuto atteso: scopo/metodo (3 livelli fedeltà) · correttezza funzionale · risorse/timing · potenza sistema
  (static 92%, E realizzata≫algoritmica) · costanti e_MAC≈e_AC · confronto SNN-vs-ANN + letteratura (compattezza
  ~5-65×) · tabella claim (3 correzioni + reframe) · termica · onestà+Fase C. Figure: breakdown potenza · attribuz.
  38 DSP + test 0-DSP · E realizzata-vs-algoritmica · e_MAC-vs-e_AC · SNN-vs-ANN + scaling letteratura · compattezza · tabella.
- **4 CAVEAT ONESTI da portare:** (a) costanti per-op order-of-magnitude (floor mW); (b) ANN random→energia del
  datapath, capacità dalla letteratura; (c) vantaggio = range 5-65×, numero esatto=training (non fatto); (d) tutto
  stima Vivado, non silicio (Fase C).

**AZIONE 2 — Eseguire l'harness Fase C (design-for-later, board PYNQ-Z1 in arrivo).** Ripartibile da qui.
- Piano (codice completo, 8 task) = `docs/superpowers/plans/2026-07-11-fpga-phase-c-silicon-validation.md`;
  spec = `docs/superpowers/specs/2026-07-11-fpga-phase-c-silicon-validation-design.md`.
- Eseguire via `superpowers:executing-plans` (o subagent-driven): scrive generatore riferimenti MATLAB
  (`gen_phase_c_reference.m`, rete fixed) + harness Python in `matlab/axi/phase_c/` (driver `SnnDonatello` + mock,
  plant ACC-IIDM **numpy** PS-friendly, sweep funzionale, closed-loop network-in-the-loop, potenza 3-stati) +
  unit-test col **MOCK** → tutto VERDE **senza board**. Test: `python -m pytest matlab/axi/phase_c/tests/ -v` (numpy, no torch).
- Esecuzione reale sulla board = runbook in `document/FPGA_PHASE_C_REPORT.md` (⚠️ **non ancora presente — lo crea
  l'AZIONE 2**) quando arriva la PYNQ-Z1 (solo total-board delta idle-vs-inferenza; i 9 mW PL < risoluzione →
  upper-bound + P_deploy totale).

> **Dopo le 2 azioni**, la prossima **fase di progetto** è l'**integrazione dei limiti/segnali V2I in Simulink**
> attorno alla rete (le menzioni "Prossimo: V2I" nel log storico sotto si riferiscono a QUESTA, non alle 2 azioni pendenti).

### 🛠️ MODI DI LAVORO (vincoli del track — rispettarli sempre)
- **NIENTE workaround:** se un numero/comportamento non torna si indaga la **CAUSA** (come il bug leak-division,
  la doppia /n_ticks, i 38 DSP elettivi) — non si aggira né si "aggiusta il numero".
- **Cura costante della documentazione:** ogni milestone aggiorna il deliverable + questo file + la memoria. I
  documenti del repo **devono bastare da soli** (la memoria dell'assistente è supplemento, non dipendenza).
- **Design prima del codice:** nuove funzionalità → `superpowers:brainstorming` → `writing-plans` →
  `executing-plans`. Non saltare all'implementazione.
- **VHDL mai a mano** per i datapath (HDL Coder single-source da `snn_core`, o port 1:1 come il plant). **Core SNN
  congelato:** parità double ~2e-6 dopo ogni modifica a `snn_core`/`snn_types`.
- **Lavoro lungo Vivado/HW = checkpoint-driven:** run in background, ci si ferma ai checkpoint per far validare
  all'utente prima di proseguire.
- **Commit** conventional e chiari, **senza `Co-Authored-By`**. Push libero (Azure dismesso).

### 🎙️ TONO / STILE (riprendere come se la chat non fosse mai finita)
Tecnico e rigoroso ma **onesto senza overclaiming**: numeri con provenienza, caveat espliciti, si dichiara cosa
è stima vs misura. **Decisi:** si agisce e si raccomanda un'opzione (niente survey infinite); si chiede solo
quando la scelta è genuinamente dell'utente. **In italiano.** Diretti sui findings scomodi (es. "il vantaggio del
report è giusto per il motivo sbagliato") senza addolcirli. Checkpoint espliciti sul lavoro lungo. L'utente è
competente (MBSE/SNN/FPGA): niente spiegazioni base non richieste.

### 🗄️ PROMPT DI RIPRESA — STORICO/SUPERATO (Fase B/C, 2026-07-11). NON usare: il prompt ATTUALE è nel blocco ▶ in cima.
> Volutamente una **guida a LEGGERE i documenti**, non un dump di informazioni.

```
Riprendi il progetto CF_FSNN, track HDL / Simulink_Importer. Non ho contesto in questa chat (post-clear):
NON chiedermi lo stato — ricostruiscilo dai documenti.

Repo: D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN
Worktree/branch: .worktrees\Simulink_Importer  (branch Simulink_Importer)

1. git -C ".worktrees\Simulink_Importer" pull ; poi git status e git log --oneline -8 per lo stato reale.
2. Leggi PRIMA document/SESSION_RESUME.md -> blocco "RIPRESA A FREDDO - Fase B/C": e' il punto d'ingresso
   (stato, branch, le AZIONI pendenti coi puntatori, MODI DI LAVORO, TONO). Segui i puntatori che indica
   (deliverable FPGA_PHASE_B_POWER.md, spec/piani in docs/superpowers/, ecc.): LEGGI i doc, non ricostruire a memoria.
3. La tua memoria (MEMORY.md + memorie) e' gia' caricata: contesto supplementare, non dipendenza.

Poi, PRIMA di lavorare, dimmi in breve: (a) stato attuale, (b) le azioni pendenti (dovrebbero essere 2:
report Fase B via skill create-report, e/o esecuzione harness Fase C via superpowers:executing-plans),
(c) i modi di lavoro e il tono che adotterai - e ASPETTA la mia conferma su cosa fare.

Adotta i MODI DI LAVORO e il TONO descritti in SESSION_RESUME (in sintesi: niente workaround -> indaga la
CAUSA; cura costante della documentazione; design prima del codice via skill superpowers; VHDL mai a mano /
core SNN congelato; commit senza Co-Authored-By; tono tecnico, onesto senza overclaiming, decisi, in italiano).
```

---

## 🗄️ STORICO — Stato precedente (2026-07-10 — **B2 REALIZZATO, SNN 6.9% LUT bit-exact**). Stato ATTUALE = blocco ▶ in cima.

> **✅ B2 (SNN Donatello time-multiplexata, `hdl.RAM`) REALIZZATA E VERIFICATA (commit `f20e812`).** Da **44% → 6.9%
> LUT** (~6.3× meno), 22 DSP, 2 BRAM, **bit-exact** (`test_b2_fsm` err=0), **cosim xsim PASSED**. È l'architettura di
> deploy lean. File: `matlab/snn_b2_fsm.m` + `gen_b2_rom`/`b2_donatello_rom`/`test_b2_fsm`/`tb_b2_fsm`. Studio in
> `document/HDL_ARCHITECTURE_STUDY.md`. **decode + wrapper AXI-Lite + BITSTREAM PYNQ-Z1 (board reale) FATTI** (cosim
> `AXI TEST PASSED`; IP synth **8.9% LUT / 38 DSP / 2 BRAM**; **`.bit` timing-clean** @8 MHz WNS +6.97 ns, con **board
> preset Digilent PYNQ-Z1** DDR/MIO reali + handoff **`.hwh`/`.xsa`** per PYNQ `Overlay`/Vitis, in `matlab/axi/build/`).
> **CHAIN HDL COMPLETO** PyTorch→RTL→AXI→bitstream flashabile, tutto headless. **+ FASE B POWER ANALYSIS FATTA**
> (validazione report FPGA, deliverable `document/FPGA_PHASE_B_POWER.md` + `matlab/axi/build/phase_b/`): synth OOC +
> SAIF `report_power` High-confidence. **3 correzioni al report**: DSP 0→38 (elettivi, 0-DSP realizzabile), Fmax
> 100-200→~8.5 MHz, **e_MAC≈e_AC su FPGA** (non il 5× Horowitz); + energia realizzata ≫ algoritmica (static domina
> 92%). **Vantaggio SNN ri-inquadrato**: reale ~5-65× ma da **compattezza modello** (letteratura NN car-following
> ~7k-100k MAC vs SNN ~800), NON da AC≪MAC. Fase C (silicio) rinviata-predisposta. **Prossima FASE progetto (dopo le 2 azioni pendenti in testa al file):** integrazione V2I in Simulink.
> (Storia po2→shift/44% sotto.)

> ⚠️ **WORKTREE PARALLELO — NON è il track principale `main`.** Sei nel worktree
> `.worktrees/Simulink_Importer` (branch **`Simulink_Importer`**), **traccia ②** (import checkpoint → Simulink → HDL).
> Il track ① (Simulatore) vive in `.worktrees/Simulator`. Per il track principale (EventProp/training) vedi
> «Stato precedente» sotto + `EVENTPROP_STATUS.md`. Contesto tracce parallele: memoria `cf-fsnn-parallel-tracks`.

**➜ PUNTO D'INGRESSO HDL: leggi `document/HDL_PHASE.md` §0 (RIPRESA RAPIDA)** — stato, prossima azione, comandi di
verifica, e **§9 gotcha** (i tranelli da non ri-sbattere). Contesto libreria/blocchi: `document/SIMULINK_IMPORT_DESIGN.md`.

**Stato in una riga:** RTL VHDL **bit-accurato** generato per Donatello via HDL Coder, **single-source da `snn_core`**
(type-parametrizzato double/fi, NON riscrittura a mano). **po2→shift FATTO → moltiplicatori 27.840 → 32** (→ **32 DSP
REALI** post-synth+P&R 2026-07-10, **LUT 44% / slice 53%**, 0 BRAM, ~5 MHz — vedi `HDL_PHASE.md §0`), comportamento preservato (parità double **2e-6**, errore
fixed **≤0.028 = max sui 5 parametri** (v0 il peggiore), Leonardo NON regredito). "bit-accurato" = garanzia HDL Coder
vs il fixed MATLAB, **ora verificato in cosim xsim** (`TEST COMPLETED (PASSED)`, bit-esatto, 2026-07-10). **Bug leak-division RISOLTO** (`V./ld` fi = plateau ~3.5 → `leaky` bit-shift).

**Cosa fare adesso** — **[✅ Vivado 2026.1 installato; ④ SINTESI+P&R REALI fatti 2026-07-10]:**
1. ✅ **Donatello sintetizzato E routato** (OOC, `xc7z020clg400-1`): **LUT 23.186 = 44% (slice 53%), FF 3.386 = 3%,
   DSP 32 = 15%** (mult residui previsti — po2→shift confermato), **BRAM 0**, **Fmax ~5 MHz** (non-vincolante). Fit
   ok ma **LUT-bound**; la STIMA sotto-contava i LUT. **Decisione aperta:** area-opt **streaming ÷32** (§8.2, refactor
   `snn_core` gated-parità) **vs** ampiezza (decode→LUT + altri 3 champion + cosim). Dettaglio in `HDL_PHASE.md §0`.
2. Poi: **decode→LUT** (`coder.approximate` su σ), **altri 3 champion** (`make_hdl('Michelangelo'|...)`), **cosim**.

**Vincoli/modi (track ②):** niente workaround; **VHDL MAI a mano** (rompe la catena 1:1); ottimizzare via config
HDL Coder o sorgente MATLAB **behavior-preserving, gated dalla parità** (`run_parity_tests` double ~2e-6 dopo OGNI
modifica a `snn_core`/`snn_types`); metrica primaria = comportamento (gap), non i param grezzi; commit senza
`Co-Authored-By`. **Merge su `main` NON ancora fatto** (coordinare col track Simulator).

**File chiave (worktree):** sorgente HDL `matlab/snn_core.m`+`snn_types.m` (+`snn_normalize/decode/entry`); wrapper
`matlab/snn_hdl_<name>.m` (gen da `gen_hdl_tops.m`); driver `matlab/make_hdl.m`; verifiche `run_parity_tests.m`
(double), `run_fixed_{parity,sweep}.m` + `run_hdl_verify.m` (fixed); diagnostica `diag_{ranges,quant}.m`; export
`scripts/export_champions.py` → `matlab/champions_export.mat`. RTL generato in `matlab/codegen/` (gitignored,
rigenerabile con `make_hdl('Donatello')`). MATLAB **R2026a headless** (`C:\Program Files\MATLAB\R2026a\bin`).

**4 champion** (`champions/`): Donatello=`PE_t05_gp0002` + Michelangelo=`A_lr1e2_t06_r16` = **entrambi
`eventprop_alif_full` rank 16**; Raffaello=`R33_C2_A1_T12_fix` + Leonardo=`LS3_PEAK_R0_launch_d03` = **entrambi
`baseline` rank 8**. Traiettoria ottimizzazione area e
catena 1:1 (4 anelli) in `HDL_PHASE.md §5/§2`.

---

## 🎯 Stato precedente (2026-06-21 — **EventProp_Study: training a gradiente esatto**)

**Branch corrente**: `EventProp_Study` (da `main`). **`Dynamic_Study` e `Loss_Study` CHIUSI e mergiati in
`main`, poi eliminati** (locale + remoto). `main` @ `db9fbdb` contiene tutto il lavoro.

**Da dove veniamo (Dynamic_Study, chiuso 2026-06-21)**: indagato a fondo il tetto sui parametri dinamici
**a/b**. Esito conclusivo: **l'identificazione individuale di a/b è IRRIDUCIBILE** in questa architettura
(capacità 32h + geometria IIDM: `a`=cap `min(·,a)`, accoppiamento √(ab)). Due conferme indipendenti (L2
reparam/regime NEGATIVO = variance-collapse; L3 scout #2 encoding FALSIFICATO = non legge i transitori).
**a/b NON toccano la sicurezza** (closed-loop dipende da √ab, già ben appreso) → il champion **`normal`
`LS3_PEAK_R0_launch_d03`** (validato, 0 collisioni, string-stable) **resta il deploy**. Capacità aggiunte
(opt-in, backward-compat, verificate bit-identiche al pre-modifiche): `--cf_extra_channels` (#2 encoding 4→7),
`--uncertainty_head`+`--lambda_nll` (#5 head eteroschedastica, calibrata), `--lambda_geo/ratio_aux`+`--regime_gamma`
(L2). **Ricetta Prodigy canonica** scoperta: `cosine_no_restart + lr=0.5 + growth_rate 1.05` (single-cycle, più
semplice del custom_restart, ~15-20 ep; lr=1 esplode = raggio spettrale). Dettagli in `cf-fsnn-dynamic-study` (memoria).

**Perché EventProp ora**: è lo **Study 2 pianificato** post-Loss_Study. Ipotesi guida (utente): il tentativo
storico EventProp fallì per **misuso iperparametrico** (come accadde per Prodigy: lr=1.0 paper vs 0.5 CLEAN),
NON per limite reale. Domanda scientifica: il gradiente **esatto** (EventProp) batte BPTT+surrogate, isolando
la variabile "metodo di training"? Rilevante per FPGA (regola event-based, on-chip-friendly).

**Ragionamento + build COMPLETATI (2026-06-21)** — vedi `document/EVENTPROP_STUDY_PLAN.md` (maestro).
Sintesi: (1-2) EventProp = gradiente esatto (adjoint event-based) vs BPTT+surrogato; lo studio storico
(44-run) trovava pareggio + fragilità, ma con la stessa C8 mai fixata (non 2 conferme indipendenti).
(3) Traslato: **fix C8** (jump/lv clamp → EventProp stabile, val 0.267 AdamW); diagnosi "Prodigy si
congela su EventProp" (incoerenza gradiente esatto) → costruito **ProdigyEvent** (`core/prodigy_event.py`:
stima d su gradiente EMA + throttle adattivo trend-gradiente + decay morbido 0.99 + ProbeUp MPPT + gate
rate; tutti iper-parametri sweepabili) → ProdigyEvent+ProbeUp val 0.299 (parameter-free). + controllo
rate attivo (lambda_sr adattivo). Backward-compat bit-identico verificato.

**Cosa fare adesso**:
1. Girare **`EventProp_Study.ipynb`** su Azure (50 ep, 7 arm, EventProp PRIMI → pushati prima): EVP_ADAMW,
   EVP_PRODIGYEVENT, EVP_PRODIGYEVENT_PROBE, EVP_PE_PROBE_LSR, EVP_ADAMW_LSR, PEAK_BASELINE, PEAK_SINGLECYCLE.
   Output `results/EventProp_Study/`. Poi `git pull` e analisi (sintesi + viewpoint gradiente + r per-driver).
2. Esito atteso: due metodi di training ottimizzati + viewpoint sul floor/a/b. Se ProdigyEvent+ProbeUp
   conferma a 50ep → diventa il ProdigyEvent canonico.
**Capacità riusabili** (opt-in, train.py/network.py): `--cf_extra_channels`, `--uncertainty_head`/`--lambda_nll`,
`--lambda_geo/ratio_aux`/`--regime_gamma` (da Dynamic_Study); `--optimizer prodigy_event` + relativi flag,
`--lambda_sr_adapt_gamma`, fix C8 EventProp (EventProp_Study).

---

## 🗄️ Stato precedente (2026-06-20 — **Dynamic_Study: il tetto sui parametri dinamici a/b**) — CHIUSO, merged in main

**Branch corrente**: `Dynamic_Study` (da `main`; `Loss_Study` è stato **merge in `main`** come milestone).
**Documenti maestri (leggere in quest'ordine per il contesto pieno)**:
1. `document/DYNAMIC_STUDY_PLAN.md` — diagnosi, disegno degli studi, batch di soluzioni, mappa skill/cassetto.
2. `document/DYNAMIC_STUDY_B_RESULTS.md` — risultati Studio B + L0 (la causa, con numeri e figure).
3. `document/VALIDATION_REPORT.md` (+ `.pdf`) — stato della rete S3 validata (micro/meso).

**Contesto**: chiuso `Loss_Study` (validazione SUPERATA — rete `LS3_PEAK_R0_launch_d03`, 0 collisioni,
string-stable; report in `VALIDATION_REPORT.md`). Unico residuo: errore sui parametri **dinamici** a/b
(NRMSE a=0.26, b=0.30). Aperto `Dynamic_Study` per capirne la causa e superarlo.

**Cosa è stato scoperto (Studio B + L0, locali, `scripts/dynamic_study_B.py` / `_L0.py`)**:
- Il tetto **NON è identificabilità di fondo**: un ottimizzatore classico (LM) su dati globali puliti
  recupera tutti e 5 i parametri **esattamente** (NRMSE 0). L'informazione è nei dati.
- Causa **dominante = LOCALITÀ**: la rete predice **per-istante** e nei tratti senza transitori a/b
  sono ciechi (Fisher cond 55→2748 togliendo i transitori; L0: curva a **soglia** — a/b crollano solo
  con contesto W≥160 ≈ 16 s, quando la finestra *cattura* un transitorio).
- **Gap-SNN recuperabile**: la rete (a 0.26/b 0.31) è peggio perfino del LM locale ideale (0.12/0.18)
  di ~+0.13 → margine SNN al contesto attuale, senza toccare la memoria.
- **Direzione molle = rapporto a/b**; a/b **non toccano** né micro (closed-loop dipende da √ab) né
  macro (l'equilibrio `sₑ` è a/b-free → capacità governata da T,v0,s0).

**Batch RIORDINATO** (in `DYNAMIC_STUDY_B_RESULTS.md` §4/§6): #1 **località** (loss per-regime S4 +
memoria/ritenzione + **incertezza dichiarata**); #2 **gap-SNN** (surrogate width / encoding Δv'·jerk /
TET loss); #3 **riparametrizzazione [a,√ab]→deriva b**; #6 cambio modello (Future-B) in frigo.

**L1 ESEGUITO (2026-06-20, `results/Dynamic_Study/L1/`)** — verdetto sorprendente: la memoria ricorrente
è **DANNOSA** per a/b, non solo inutile. Ablandola sul champion addestrato (stato resettato a ogni step):
a 0.331→**0.143**, b 0.178→**0.149** (≈ LM locale ideale 0.12/0.18), s0 0.135→0.082, v0 0.242→0.219,
T pareggio. Il path memoryless vince su 4/5 (gain_ab=−0.109). Decadimento NRMSE(a,b) **piatto** vs distanza
dal transitorio → NON è ritenzione leaky. **Esclude** le leve "ritenzione/canale-lento" e "allungare seq_len".

**L1.5 ESEGUITO (2026-06-20, `results/Dynamic_Study/L1p5/`)** — finding L1 confermato ROBUSTO su 3 seed
freschi (memoryless batte memory su v0/s0/a/b, pareggio su T; a 0.33→0.15 ~20× la std). Closed-loop sanity
(60 sim/modalità): **0 collisioni in tutte e 4** (a/b non toccano la sicurezza). Twist: il readout migliore
è **FULL MEMORYLESS**, non l'ibrido (memoryless: miglior worst min_gap 2.22m + jerk più basso 1.54;
l'ibrido è il peggiore per jerk 2.03 perché mescola due regimi). **Il tetto a/b si risolve a costo ZERO di
training** col readout full memoryless.

**L1c ESEGUITO (2026-06-20, `results/Dynamic_Study/L1c/`)** — meccanismo del danno: **convergenza RAPIDA
dello stato a un operating-point "caldo" distorto** (entro ~4 step dal reset): a pos0 memory≡memoryless
(a_pred 0.97≈GT 1.19), in 4 step spike-rate 0.077→0.16 e a_pred COLLASSA a 0.51, poi plateau. NON accumulo
lento, NON creep ALIF, NON smoothing (le 3 ipotesi rigettate; l'auto-verdetto le ha mancate perché le finestre
early/late erano entrambe nel plateau). **D2**: in nessuna modalità la rete decodifica `a` dal transitorio
(risposta piatta al picco |accel|) → a/b sono una **quasi-costante operating-point-dipendente**. "Memoryless
vince" = prior meglio centrato (operating-point freddo), non identificazione per-istante.

**L1d ESEGUITO (2026-06-20, `results/Dynamic_Study/L1d/`)** — probe prior-vs-discriminazione (scatter
pred-vs-GT per-driver, 250 scenari). Memoryless: v0 r=0.86 (reale forte), s0 r=0.52 (moderata), **a r=0.39
(debole, perlopiù prior)**, **b r=−0.37 (ANTI-correlato — peggio di un prior)**. Sottigliezza: **memory ha |r|
più alto su tutti e 4** → conserva più segnale discriminativo ma mal centrato (NRMSE alta); il memoryless
ri-centra il bias (NRMSE bassa) ma sacrifica discriminazione e peggiora l'anti-correlazione di b. **Il win
memoryless è bias-centering** e la NRMSE è cieca all'anti-correlazione. **b è il vero problema irrisolto**
(non affidabile per-driver in entrambe le modalità; rafforza Studio B: √ab fissato, b dedotto inversamente).
**Diagnosi L1x COMPLETA.**

**PRIORITÀ UTENTE (2026-06-20)**: **Safety > Comfort > Performance** (tutte contano). `b` = decel di
**comfort** (priorità #2), legata all'attenuazione delle onde stop&go. Gerarchia usata nei verdetti.

**L1.6 ESEGUITO (2026-06-20, `results/Dynamic_Study/L1_6/`)** — 300 sim/modo micro + 1 plotone. Esito
SFUMATO (auto-verdetto "non promuovere" troppo binario). **Safety #1: memoryless STRETTAMENTE MEGLIO**
(0 coll, worst min_gap 2.22 vs 1.87, gap plotone 30.3 vs 24.3, TTC/TET migliori). **Comfort #2: MISTO** —
jerk MEGLIO (micro 1.64 vs 1.67; plotone 0.11 vs 0.22), max_decel pari, D single-vehicle ~pari (≪1), ma
**plotone head-to-tail 0.365 vs 0.145** → memoryless attenua le onde stop&go MENO (non-monotono, ~0.37,
comunque ≪1 = stabile). **Performance #3: memoryless MEGLIO** (gap_error 10.0 vs 13.2). CAVEAT: plotone è
**n=1** (un driver, una perturbazione) → meno robusto del micro; il D micro robusto mostra gap piccolo.

**PIVOT (2026-06-20, con l'utente)**: **memoryless SCARTATO** come deploy — è un workaround (non corregge la
rete), vantaggio marginale, e in plotone diverge dall'oracle mentre `normal` gli somiglia (h2t 0.145≈0.12 vs
0.365). **Resta `normal` come deploy** (champion validato). L'arco L1→L1.6 vale come **diagnosi conclusa**.
Principio ribadito: **niente workaround**.

**L2 TRAINING PRONTO — IN ATTESA su Azure** (run di ore, "nessun limite"). Scoperta chiave: il champion NON
supervisionava a/b → b anti-correlato (vincolato solo via √ab). Soluzione di principio: supervisionare
ESPLICITAMENTE log(a/b) (reparam in loss: geo-mean + log-ratio) concentrata ai transitori. `train.py` esteso
(4 flag opt-in, backward-compat, smoke OK); `Dynamic_Study_L2.ipynb` = ablazione 6 varianti + diagnostica
completa per-variante; plumbing end-to-end validato.

**L2 ESEGUITO (2026-06-21, `results/Dynamic_Study/L2/`) — NEGATIVO / workaround. FILONE a/b CHIUSO.**
6 varianti. Superficie: r_b −0.23→+0.62, NRMSE(a) 0.33→0.14. MA: (1) guadagno = **variance-collapse** del
range (prior meglio centrato, non identificazione); (2) **val_data (accel) PEGGIORA ~12%** (0.193→0.216) =
trade sbagliato per Safety>Comfort>Performance; (3) **s0 si rompe** (r_s0 0.578→−0.088) = whack-a-mole, rete
satura; (4) **r_ratio resta 0.12-0.33** → split a/b NON risolto (cavalca √ab); (5) per-regime inutile (non
legge i transitori); (6) le leve "intelligenti" non battono l'aux banale (V1). **Conclusione: lo split a/b è
IRRIDUCIBILE** (capacità + identificabilità strutturale IIDM); inseguirlo costa accel/s0. **Champion `normal`
resta il deploy** (validato, sicuro, oracle-like); a/b non toccano la sicurezza.

**L3 esplorato via SCOUT locali (2026-06-21) — conferma la chiusura.** Invece dell'ablazione full (ore Azure),
scout 5ep locali: **#2 encoding (Δv'/jerk/ṡ, input 4→7) FALSIFICATO** — r_b peggiora a −0.57, r_ratio 0.09,
per-regime ancora piatto (NON legge i transitori), `a` variance-collapsed. **2ª conferma: identificazione a/b
irriducibile.** **#5 uncertainty head** (eteroschedastica, output 5→10 + NLL): scout POSITIVO — calibrata
(corr(σ,|err|) 0.45-0.67), flagga correttamente `a` come param più incerto (NON `b`: errore puntuale piccolo,
l'anti-correlazione è di rango = Performance, non safety). **Capacità riusabili in train.py/network.py** (flag
opt-in, backward-compat): `--cf_extra_channels` (#2), `--uncertainty_head`+`--lambda_nll` (#5), `--lambda_geo_aux`/
`--lambda_ratio_aux`/`--regime_gamma` (L2). **Studio Prodigy** (utente): ricetta canonica **single-cycle**
`cosine_no_restart + lr=0.5 + growth_rate 1.05` validata locale (più semplice del custom_restart, stesso operating
point; lr=1 esplode = raggio spettrale, AGC peggiora; ~15-20 ep bastano).

**Cosa fare adesso** — filone a/b CHIUSO definitivamente, si torna alla scaletta `document/FUTURE_WORK.md`:
- **EventProp (Study 2 pianificato)**: rifarlo "come si deve" (ipotesi: fallì per misuso iperparametri come
  Prodigy). Gradiente esatto vs BPTT+surrogate; FPGA-rilevante. Docs: EVENTPROP_DESIGN/OPTIMIZER_SWEEP.
- **F6 multi-seed → F5 deploy FPGA PYNQ-Z1**: finire il progetto col champion validato (single-seed = rischio
  residuo principale).
- **v0-freeze (decoder 4-param)**: cheap win (S1: v0 non-identificabile, ~zero costo + meno param FPGA).
- **Future-B (cambio modello/loss)**: unico vero attacco strutturale ad a/b (S3_CONSOLIDATION_AND_FUTURE_B.md);
  C1 LAMB / C2 vincolo raggio spettrale → capacity sweep valido. Deep/rischioso. **DA DECIDERE con l'utente.**

---

## 🎯 Stato precedente (2026-06-19 — **Loss_Study + framework di EVALUATION completo**) — superseded da Dynamic_Study

**Branch**: `Loss_Study` (da `main` tag `R33_closure`), poi merge in `main`.
**Documento maestro**: `document/LOSS_STUDY_AND_EVALUATION.md` (record completo, auto-sufficiente).

**Cosa è stato fatto (in ordine)**:
1. **S1 — identificabilità**: i 5 parametri ACC-IDM NON sono congiuntamente identificabili
   dall'accelerazione. v0 e `a` = **coppia molle** (provato causalmente, corr −0.82). Aggiunto
   logging `val_*_nrmse` (Lente B) + plot G19/G20.
2. **Osservabilità (la leva)**: scenario **freeflow** sblocca v0 (NRMSE 0.50→0.39); scenario
   **launch** (accel forti ripetute) sblocca parzialmente `a` (0.43→0.65, NRMSE 0.34→0.26). Run
   consolidata `LS3_PEAK_R0_launch_d03` (restart Opzione 1+4, decay 0.3). Bias a/b sistematico in frenata → **S4 futuro**.
3. **Capacità (S2) — SOSPESA** (non esaustiva): modelli grandi esplodono in BPTT. Fix: guard v2
   (frazione + inf), **AGC** (`--grad_clip agc`). Future: LAMB, raggio spettrale, multi-seed.
4. **EVALUATION** (`Loss_Study_Validation_Full.ipynb`, ~6-9 min, un run): **micro** (sicurezza
   closed-loop), **meso** (plotone/string stability, CAM dal leader i−1), **macro** (diagramma
   fondamentale), **vetrina** (accuracy/raster/energia/GIF/dashboard). 15 grafici → `results/evaluate/<analisi>/`.

**Esito EVALUATION v1 (FATTO, `results/evaluate/v1_realistic_cutin/`) — VALIDAZIONE SUPERATA**:
- **MICRO**: **0 collisioni su TUTTI gli scenari** (100 sim/sorgente, cut-in realistico), SNN ≈ oracolo,
  più dolce + più string-stable. (Il 4% della 1ª run era SOLO il cut-in inevitabile, ora corretto.)
- **MESO**: plotone string-stable (head-to-tail <1), convettivo, 0 collisioni.
- **MACRO**: FD corretto; SNN capacità più alta (~2000 vs oracolo 1045) per **bias v0 alto**.
- Energia ~3.9× vs ANN (da AC<MAC). Accuracy 77%. Unico problema residuo: **bias parametri a/b/v0**.

**Cosa fare adesso**:
1. **S4** (lato training): ridurre il **bias a/b/v0** (margini frenata + capacità macro). È l'unico residuo.
2. Poi: EventProp (in pipeline) / deploy FPGA (modello consolidato `LS3_PEAK_R0_launch_d03`).

---

## 🎯 Stato precedente (2026-06-16 — **STUDIO PRODIGY CHIUSO. Merge → main**) — superseded da Loss_Study

**Fase corrente**: **Prodigy Study CLOSED**. R33 Closure ha prodotto 2 nuovi champion finali con record assoluti del progetto. Tutti i 5 branch di esplorazione (Architecture_Exploration, Floor_Diagnostic, Optimizer_Exploration, Training_Method_Exploration, Visualizer_Building) sono antenati di `Prodigy_Deep_Study` → un singolo merge `Prodigy_Deep_Study → main` integra l'intera storia (307 commit).

### Champion finali (4 entries attive in `Arch_Tested/`)

| Ruolo | Tag | Tp | val_data | ep | gn_max | Note |
|---|---|---:|---:|---:|---:|---|
| **PEAK** | `R33_C1_A4_T12_PEAK` | **0.0642** | **0.1589** 🏆 | 49/50 | 1.78e19 | Record val_data assoluto |
| **CLEAN** | `R33_C2_A1_T12_CLEAN` | 0.0518 | 0.1654 | **50/50** | **52** ✅ | 1° setup 50ep+gn<100 |
| **STABLE** | `R32_B5_E1_STABLE` | 0.0519 | 0.163 | 50/50 | 5.3e9 | h=16, 232 params, FPGA-friendly |
| **BASELINE** | `R24F_MIXED_lr0.5_V08` | 0.015 | 0.181 | 30/30 | 21.79 ✅ | Storico, certificato CLEAN |

### Cronologia ultimi 4 giorni (2026-06-13 → 2026-06-16)

1. **2026-06-13 R30 Identifiability** (10 esp.) — supervisione ausiliaria 4-tuple sblocca rank-collapse (rank≥3 in 8/10 run).
2. **2026-06-14 R31 Champion Validation** (14 esp.) — 3 champion candidati: C3 CLEAN, A3 PEAK, E1 STABLE.
3. **2026-06-15 R32 Restart Mechanisms** (10 esp.) — 5 meccanismi soft × 2 baseline. Soppianta R31_A3/E1. Identificato peak val_data record (B2=0.161). Bug A1≡A2 per cycle_max coincidenza.
4. **2026-06-16 mattina — R33 Closure preparato**: 2 correzioni in `train.py` (`epoch_explosion_threshold` 100→10000, `restart_T0` 15→12). 5 esp. (3 champion replica + 2 isolation controls).
5. **2026-06-16 pomeriggio — R33 eseguito**: scoperti 2 NUOVI champion:
   - **R33_C1** (A4 con T0=12): 49/50 ep, Tp=0.0642, **val_data=0.1589 RECORD ASSOLUTO**
   - **R33_C2** (A1 con T0=12): 50/50 ep, **gn=52 CLEAN**, primo setup mai osservato a combinare 50 ep + gn<100
   - Isolation controls (D1, D2) confermano che il guadagno viene SOLO da T0=12 (la soglia rilassata da sola non basta)

### Stato infrastruttura corrente (2026-06-16)

**Branch git**: `Prodigy_Deep_Study` HEAD `f7cbd73`. Tag: `pre_R27`, `pre_R28`, `pre_R29`, `pre_R30`, `pre_R31`, `pre_R32`, `pre_R33`. **Da creare**: `R33_closure` post-merge.

**Codice principale**:
- `train.py`: nuovi default R33 (`epoch_explosion_threshold=10000.0`, `restart_T0=12`)
- 5 nuovi CLI flag R32 invariati (`--restart_decay`, `--restart_lr_after`, `--restart_warmup_epochs`, `--restart_adaptive`, `--restart_T0`)
- `core/network.py`: decoder fix C3 opt-in (DEC-1 + DEC-3)
- `data/generator.py`: 4-tuple loader R30

**Results dir attive**:
- `results/Prodigy_Study/R31_ChampionValidation/` (14 run)
- `results/Prodigy_Study/R32_RestartMechanisms/` (10 run + diagnostic)
- `results/Prodigy_Study/R33_Closure/` (5 run + side-by-side)
- `results/Prodigy_Study/_COMPLETE_360_analysis.csv`, `_TRUE_Tintra_ranking.csv`

**Arch_Tested**: 14 entry totali (4 attive + 10 storiche/superseded)

### Cosa fare adesso (priorità)

1. **Merge `Prodigy_Deep_Study` → `main`** (no-ff per preservare storia 307 commit)
2. **Tag finale**: `R33_closure` su `main` post-merge
3. **Cleanup branch obsoleti**: i 5 branch ancestor (Architecture/Floor/Optimizer/Training_Method/Visualizer) sono sicuri da rimuovere — il merge li integra automaticamente
4. **Push `main` + delete remote dei 5 branch obsoleti**
5. **Fase successiva (post-merge)**: deployment/quantizzazione PYNQ-Z1 con R33_C2 come baseline (clean + 50ep complete + 864 params) o R33_C1 se serve max accuracy

### Verità chiave 2026-06-16 (closure)

- **T0=12 batte T0=15 sistematicamente**: 4 cicli pieni in 50 ep, no ciclo monco sprecato. +8 ep su A4, +25 ep su A1.
- **Decay 0.3 + T0=12 = combinazione CLEAN**: dopo 4 cicli lr lavora a ~1e-2, dinamica BPTT quasi lineare, gn pulito.
- **Warmup 2ep + T0=12 = combinazione PEAK**: smussa il restart abbastanza da mantenere il peak Tp ma porta a esplosioni tardive irrilevanti per la completion.
- **Lo studio è chiuso**: i 4 champion coprono tutti i ruoli operativi richiesti. Non ci sono motivi scientifici per ulteriori sweep prima del deploy.

---

## 🎯 Stato precedente (2026-06-15 — R30/R31 completati, R32 pronto su Azure) — superseded by R33 closure

**Fase corrente**: **3 champions validati** post-R31 (Champion Validation 14 esp.). R30 (Identifiability) confermato che la supervisione ausiliaria + decoder fix risolvono il rank-collapse. R31 ha identificato 3 trade-off ottimali distinti. R32 (Restart Mechanisms, 10 esp.) è **pronto su Azure** ma non ancora eseguito.

### I 3 champion attuali (snapshot in `Arch_Tested/`)

| Tag | Categoria | T_intra peak | val_data | gn_max | Note |
|---|---|---:|---:|---:|---|
| ⭐ `R29v2_C3_CLEAN` | **Scientific reference** | 0.0407 | 0.177 | **40.6** ✅ | 4/4 obiettivi, riproducibile, baseline pulito |
| ⭐ `R31_A3_PEAK` | **Operational best** | **0.0599** | **0.167** | 4280 ⚠ | Best val_data @ ep15 pre-explosion (cosine warm restart T0=15) |
| ⭐ `R31_E1_STABLE` | **Long-run stable** | 0.038 | 0.173 | 1.3e6 ⚠ | 50/50 ep completati, 232 params (h=16, rank=4), λ_sr=5 |

Tutti e 3 usano: Prodigy `lr=0.5`, DEC-1 (per-channel τ=[10,3,10,3,3]) + DEC-3 (init_bias_shift=1), R30 4-tuple loader (supervisione ausiliaria).

### Cronologia ultimi 3 giorni (2026-06-13 → 2026-06-15)

1. **2026-06-13 — R30 Identifiability (10 esp.)** — applicata supervisione ausiliaria su v0/s0/a/b (4-tuple loader) + decoder fix C3 (init_bias + per-ch τ). Rank-collapse risolto (rank_effective ≥ 3 in 8/10 run). Conferma: il bottleneck principale era identifiability, non capacità rete.

2. **2026-06-14 — R31 Champion Validation (14 esp.)** — sweep 50 ep su 4 dimensioni (decoder/scheduler/spike-pressure/capacity). Scoperti **3 champion** distinti:
   - **C3** (no restart, 10 ep): CLEAN reference scientifico
   - **A3** (cosine T0=15, 50 ep abort@32): peak operativo @ep15 prima dell'esplosione
   - **E1** (h=16, λ_sr=5): unico 50/50 ep completati senza abort

3. **2026-06-15 mattina — Analisi numerica 360°** su R31 (49 run totali aggregati con R28/R29/R30). Identificato pattern critico: **warm restart al primo trigger (ep15) genera SEMPRE il peak T_intra**, ma successivamente il loss landscape implode. → ipotesi: restart troppo violento (lr salta 90× istantaneamente).

4. **2026-06-15 pomeriggio — R32 Restart Mechanisms preparato**: implementati nel `train.py` 5 meccanismi soft per il restart:
   - **Opt 1 (decay)**: `cycle_max_lr *= restart_decay^cycle_num` (0.5 → 0.15 → 0.045)
   - **Opt 2 (2-tier)**: `restart_lr_after` per cicli successivi (lr fisso post-restart)
   - **Opt 3 (adaptive)**: trigger basato su T_intra↓×2 invece di T0 fisso
   - **Opt 4 (warmup)**: linear warmup di N epoche post-restart
   - **Opt 5 (combo 1+4)**: decay + warmup combinati
   - 10 esperimenti × 50 ep: 5 mech × {C3 base, E1 base}. Notebook `Prodigy_Restart_Mechanisms_R32.ipynb` audit Python 3.10 OK su tutte le 9 celle.

### Stato infrastruttura corrente (2026-06-15)

**Branch git**: `Prodigy_Deep_Study` HEAD `a552f55` (post-fix Python 3.10 Cell 3). Tag rollback: `pre_R27`, `pre_R28`, `pre_R29`, `pre_R30`, `pre_R31`, `pre_R32`.

**Codice principale** (cumulative state):
- `train.py`: + 5 nuovi CLI flag `--restart_T0`, `--restart_decay`, `--restart_lr_after`, `--restart_warmup_epochs`, `--restart_adaptive` (default no-op, backward-compat verificato)
- `train.py`: helper `_custom_restart_lr(epoch)` + `_check_restart_trigger()` (R32)
- `core/network.py`: decoder fix opt-in (DEC-1 + DEC-3) confermati nei 3 champion
- `data/generator.py`: 4-tuple loader R30 (x, y, mask, params_gt) attivo

**Results dir attive (aggiornate)**:
- `results/Prodigy_Study/R30_Identifiability/` — R30 (10 run, baseline pulito + supervisione)
- `results/Prodigy_Study/R31_ChampionValidation/` — R31 (14 run, sweep 50 ep su 4 dimensioni)
- `results/Prodigy_Study/_COMPLETE_360_analysis.csv` — 49 run totali aggregati
- `results/Prodigy_Study/_TRUE_Tintra_ranking.csv` — re-ranking per peak T_intra (non val_total)

**Arch_Tested aggiornato** (9 entry totali):
- 3 nuovi champion: `R29v2_C3_CLEAN`, `R31_A3_PEAK`, `R31_E1_STABLE`
- README master aggiornato con tabella T_intra + sezione "Note critiche"

### Cosa fare adesso (priorità)

1. **Eseguire R32 sweep su Azure** (~4.6h, 10 esp. × 50 ep). User trigger richiesto: notebook `Prodigy_Restart_Mechanisms_R32.ipynb`. Output atteso in `results/Prodigy_Study/R32_RestartMechanisms/`.
2. **Analisi post-R32**: confrontare i 5 meccanismi soft vs warm restart standard (R31_A3 baseline). Domanda: il decay/warmup permette di MANTENERE il peak T_intra senza l'esplosione successiva?
3. **Decisione strategica post-R32**: se almeno 1 meccanismo soft regge 50 ep con T_intra > 0.05 e gn_max < 1000 → nuovo champion. Altrimenti, accettare R31_A3_PEAK come definitivo e chiudere Prodigy Study.
4. **Merge `Prodigy_Deep_Study` → main** dopo chiusura Prodigy Study, con tag finale `R32_closure`.

### Verità chiave 2026-06-15

- **Warm restart standard (cosine T0=15) è una lama a doppio taglio**: il primo restart coincide quasi sempre con il peak T_intra ma la rete poi implode (gn esplode +3 OOM).
- **Capacity ridotta = stabilità**: E1 (232 params) è l'unico setup con 50/50 ep, ma a costo di T_intra inferiore (0.038 vs 0.060).
- **Identifiability era il vero bottleneck**: la supervisione ausiliaria R30 ha sbloccato il rank-collapse universale visto in R27.
- **R32 è l'ultimo esperimento prima della chiusura**: 5 meccanismi soft per capire se il peak R31_A3 è sostenibile o solo un evento di transizione.
- **Codice train.py è ora ricco di feature opt-in (R29 DEC-1/DEC-3, R30 4-tuple, R32 5 restart mech)**: tutti default no-op = backward-compat. Configurazione corrente attiva via CLI flag.

---

## 🎯 Stato precedente (2026-06-12 — **RESET strategico al vero baseline R24F_mixed_lr0.5_V08**)

**Fase corrente**: **VERO baseline identificato**: `R24F_mixed_lr0.5_V08` (val_data 0.181, val_total 0.189, gn_max 21.79 CLEAN). Snapshot salvato in `Arch_Tested/R24F_MIXED_lr0.5_V08_TRUE_CHAMPION/`. R27-R29 completati ma su baseline instabile (Prodigy lr=1.0 con gradienti esplosi mascherati dal clip). R30 (next step) parte da QUESTO baseline pulito.

### Cronologia ultimi 9 giorni post-fix (2026-06-03 → 2026-06-12)

1. **2026-06-03** — Audit codice + 4 bug fix in `core/network.py` + `core/eventprop.py` (vedi `BUGS_2026-06-03.md`). Tag git `pre_bug_fix_2026-06-03`.

2. **2026-06-04 → 06** — **R24F (Prodigy MultiParam PostFix, 93 esperimenti)**: sweep LR × variant × scenario. ⭐ **Best mixed: R24F_mixed_lr0.5_V08** = val_data 0.181, val_total 0.189, **gn_max 21.79 (CLEAN)**. Best highway: R24F_highway_lr1.0_V08 = 0.162 (con caveat 20% run esplosi).

3. **2026-06-07 → 09** — **R25 Ablation Study (18 esp.)** + **R26 Fusion (6 esp.)**. Errore strategico: baseline scelto `lr=1.0` (NON `lr=0.5`). Tutti i run con gn_max 10⁵-10¹⁷ (gradienti esplosi mascherati dal clip).

4. **2026-06-11** — **R27 Audit (24 run R25+R26)**: introdotte metriche `val_T_intra_corr` + `rank_effective`. Scoperto rank-collapse universale (rank=1 in 18/24). Fix bug LAYER_MAP (4/6 colonne gradient sempre NaN dal 2026-06-07).

5. **2026-06-11 → 12** — **R28 ProdigyTuning (5 esp.)** + **R29 DecoderFix (12 esp.)**. Confermato: Prodigy non era bottleneck (R28), decoder fix non aiutano (R29 disastrosi, init_shift annullato in 100 step, τ-anneal breaks training). Ma tutto ancora su baseline lr=1.0 instabile.

6. **2026-06-12 — RESET strategico**: utente solleva ipotesi instabilità baseline → verifica numerica conferma. **R24F_mixed_lr0.5_V08 è il SOLO setup post-fix con gradienti CLEAN** (gn_max 21.79 vs 10⁵-10¹⁷ degli altri). Snapshot fissato in Arch_Tested. R27-R29 mantengono valore informativo (rank-collapse confermato, Prodigy non colpevole) ma vanno re-misurati sul baseline vero.

### Stato infrastruttura corrente (2026-06-12)

**Branch git**: `Prodigy_Deep_Study` HEAD post-R29. Tag rollback: `pre_R27`, `pre_R28`, `pre_R29`.

**Codice principale** (post-fix 2026-06-03 + R27 LAYER_MAP fix + R27 val_T_intra_corr + R29 DEC-1/DEC-3 opt-in):
- `train.py`: full features ma R29 flags DEFAULT no-op (backward-compat verificato)
- `core/network.py`: decode_offset + logit_tau buffer opt-in (default 0/1 = identity)
- `data/generator.py`: invariato (y_phys = [v_dot, T_true] only)

**Vero baseline ufficiale**: `Arch_Tested/R24F_MIXED_lr0.5_V08_TRUE_CHAMPION/`
- Prodigy `lr=0.5` (NON 1.0), cosine_no_restart, seq_len=50, mixed scenario
- val_data 0.181, val_total 0.189, gn_max 21.79 CLEAN
- spike_rate 7.3% (basso ma stabile)
- `prodigy_d` arriva a 0.0192 (sano)

**Results dir attive**:
- `results/Prodigy_Study/MultiParam_PostFix/` — R24F (93 run originali, fonte verità)
- `results/Prodigy_Study/Ablation_R25/` — R25 (18 run, baseline lr=1.0 instabile)
- `results/Prodigy_Study/Fusion_R26/` — R26 (6 run, baseline lr=1.0 instabile)
- `results/Prodigy_Study/Audit_R27/` — R27 (24 run R25+R26 auditati)
- `results/Prodigy_Study/ProdigyTuning_R28/` — R28 (5 run, lr=1.0)
- `results/Prodigy_Study/DecoderFix_R29/` — R29 (12 run, lr=1.0 + R29 fixes)

### Cosa fare adesso (priorità)

1. **Sanity replica del baseline R24F_mixed_lr0.5_V08** con codice corrente → conferma val_data ≈ 0.181 e gn_max < 25
2. **Audit R30 sul baseline replicato** con metriche R27 (T_intra_corr, rank_effective) → verifica se i sintomi rank-collapse persistono anche con gradienti puliti
3. **R30 Identifiability**: supervisione ausiliaria su v0/s0/a/b (originale piano DEC-1) sopra il baseline R24F_mixed_lr0.5_V08, non più su R25_A3 instabile
4. **Decisione strategica post-R30**: se rank-collapse persiste anche con baseline pulito + supervisione → bottleneck è capacità rete 864p → considerare A8 attn 3936p re-testato post-fix

### Verità chiave 2026-06-12

- **lr=0.1 Prodigy NON funziona** (val_data 0.7-1.0, la rete non converge)
- **lr=1.0 Prodigy è instabile** (20-50% dei run esplodono, anche quelli "non esplosi" hanno gn 10⁵-10¹⁷)
- **lr=0.5 Prodigy V08 cosine_no_restart è l'UNICO setup CLEAN** post-fix
- **T30_A8 (val=0.166)** è stato un evento fortuito (lambda_sr=0, highway-only, NON riproducibile cross-scenario)
- **Tutti R25/R26/R28/R29 hanno gradienti esplosi mascherati**: metriche numeriche corrette ma dinamica corrotta
- **rank-collapse e identifiability sono problemi REALI** (visti da R27/R29) ma vanno re-misurati su baseline stabile

---

## 🎯 Stato precedente (2026-06-10 — R26 Fusion in esecuzione su Azure) — superato dalla scoperta lr=0.5 V08

**Fase corrente**: **R26 — Fusion Study Prodigy** (6 esperimenti). Costruito su R25 (18 ablation completati), che ha identificato 3 fattori indipendenti ortogonali. R26 testa se gli effetti **sommano** quando combinati.

**Fase corrente**: **R26 — Fusion Study Prodigy** (6 esperimenti). Costruito su R25 (18 ablation completati), che ha identificato 3 fattori indipendenti ortogonali. R26 testa se gli effetti **sommano** quando combinati.

### Stato cronologico ultimi 7 giorni (2026-06-03 → 2026-06-10)

1. **2026-06-03 mattina** — **Audit codice approfondito** post-R2.4 (Prodigy MultiParam 90 run): individuati **4 bug strutturali** in `core/network.py` + `core/eventprop.py` (vedi `BUGS_2026-06-03.md`). I ranking pregress (T30, P15, SW, R2.2, R2.4) sono **CORROTTI**.

2. **2026-06-03 pomeriggio** — **Fix applicati** (4 bug risolti):
   - **#1** F5 sigmoid saturation → rimosso `raw / decode_scale` in `_decode_params`
   - **#2** Xavier asymmetric bias → row-mean subtraction in `OutputLayer_LI` + `LILayer_BitShift_Po2`
   - **#3** ALIF cascade dead output → `base_threshold=1.0` per layer non-input in Stacked/StackedSkip
   - **#4** Delay mask 1/max_delay penalty → `fc_weight.mul_(sqrt(max_delay))` post-Xavier
   - Tag git: `pre_bug_fix_2026-06-03` (rollback se servisse)
   - **Verifica empirica**: saturation 0% (vs 96-97% pre-fix), spike rate 6-10%, gradient ≠ 0 su 5/5 canali

3. **2026-06-04 → 06** — **R2.4F — Prodigy MultiParam PostFix** (93 esperimenti, ~15h Azure):
   - 90 Prodigy (3 LR × 10 varianti × 3 scenari) + 3 AdamW baseline
   - **Best mixed**: V08 (cosine_no_restart) lr=0.5 → val_total **0.1887** (vs floor pregress 0.22)
   - V08 batte AdamW del 9-18% su tutti gli scenari
   - **Problema scoperto post-fix**: violin G7 mostra che `T` predetto è quasi PIATTO intra-sample (linea piatta intorno alla media), NON segue la dinamica `T_true(t)`. v0/s0 saturano ancora ai bound. `a` stuck al MIN.

4. **2026-06-07 → 09** — **R25 — Ablation Study causale** (18 esperimenti × 10ep, ~3h Azure):
   - 5 assi: A memoria temporale, B loss balancing (λ_T_aux), C spike rate regularizer, D capacity, E training duration
   - **R25 changes a `train.py`**: nuova `--lambda_T_aux` CLI + 11 colonne CSV tracking + 16 colonne batch CSV con gradient diagnostics per canale (3 livelli × 5 IDM params)
   - **R25 plot diagnostics**: G16 (gradient raw per channel), G17 (gradient decoded post-sigmoid), G18 (gradient direction sign mean)
   - **3 WIN INDIPENDENTI identificati** (ognuno migliora T_tracking_corr senza danneggiare val_total):
     - **A4**: `max_delay 6→18` → ΔT_corr = **+0.090**, Δval = -0.015
     - **B1**: `lambda_T_aux 0→0.1` → ΔT_corr = **+0.147**, Δval = -0.006 ⭐ BEST PURO
     - **C1**: `lambda_sr 0.5→0` → ΔT_corr = **+0.088**, Δval = -0.014 (lambda_sr regulariz era CONTROPRODUCENTE)
   - **D (capacity)**: NON è bottleneck. D3 large (128h) crasha (best_ep=1).
   - **E (training duration)**: SHOCKING — più training **PEGGIORA** T_corr. E2 (20ep) → T_corr 0.226 vs baseline 0.353. La rete "dimentica T" col tempo. **Early stop ≈ 10 ep è la scelta giusta.**

5. **2026-06-10 — R26 Fusion Study** (6 esperimenti, ~1h Azure, **IN ESECUZIONE**):
   - F0 baseline replica (sanity)
   - **F1 TRIPLE_win** = A4+B1+C1 (TOP candidato, atteso T_corr 0.55-0.62 se sommano)
   - F2 A4+B1 (no sr_off), F3 B1+C1 (no memoria), F4 A4+C1 (no T_aux) — controlli per isolare interazioni
   - F5 TRIPLE+epochs=5 (asse E)
   - Linearity test automatico in Cell 6: confronta F1 measured vs somma R25 predetta
   - Bug fix lungo la strada: `_robust_rmtree` per NFS Azure + tag univoco timestamp (race rmtree↔makedirs)

### Stato infrastruttura corrente

**Branch git**: `Prodigy_Deep_Study` HEAD **`6075a96`** (fix R26 NFS).

**File codice modificati post-2026-06-03**:
- `core/network.py` (4 fix + bit_shift kwarg)
- `core/eventprop.py` (fix #2 + #4)
- `train.py` (R25: pinn_loss + 4-tuple + CLI lambda_T_aux/cf_max_delay/cf_bit_shift + 27 colonne CSV totali)
- `utils/plot_diagnostics.py` (G16/G17/G18)
- `eval_report.py` (4-tuple compat)
- 5 snapshot in `Arch_Tested/` (4 fix replicati)

**Notebook attivi**:
- `Prodigy_MultiParam_Study_PostFix.ipynb` — R24F (93 run completate, archiviato)
- `Prodigy_Ablation_Study_R25.ipynb` — R25 (18 run completate, archiviato)
- `Prodigy_Fusion_Study_R26.ipynb` — R26 in esecuzione

**Results dir**:
- `results/Prodigy_Study/MultiParam_PostFix/` — 93 run R24F (3 scenari × 31 run = highway/mixed/full)
- `results/Prodigy_Study/Ablation_R25/` — 18 run R25 (5 assi)
  - `_aggregate_full.csv` — tabella sintesi con tutte le metriche tracking + delta vs baseline
- `results/Prodigy_Study/Fusion_R26/` — popolata progressivamente da R26

### Verdetto Prodigy (post R24F + R25)

- **Prodigy V08 (cosine_no_restart, lr=1.0, d_coef=1.0, d0=1e-6, growth=inf, safeguard=1, bias_corr=1, betas=0.9,0.99, wd=0.01)** è **chiaramente superiore ad AdamW** post-fix:
  - highway: Prodigy V08 0.169 vs AdamW 0.186 (-9%)
  - mixed: 0.189 vs 0.230 (-18%)
  - full: 0.222 vs 0.253 (-12%)
- **V08 vince su tutti i 3 scenari**. Cosine_no_restart è il scheduler ottimale.
- Verdetto Prodigy considerato STABILE per ora. R26 verifica se ulteriori miglioramenti sono ottenibili.

### Cosa fare adesso (priorità)

1. **Aspettare risultati R26 da Azure** (~1h, 6 run × ~10 min)
2. Quando completati:
   - `git pull` per sincronizzare risultati
   - Cell 6 del notebook fa il **Linearity Test automatico** (F1 measured vs somma R25 predetta)
   - Cell 7 mostra G7/G13/G16/G18 per F0/F1/F5
   - Cell 8 mostra il summary best per T-tracking e val_total
3. **Decisione operativa post-R26**:
   - Se F1 raggiunge T_corr > 0.55 → abbiamo un nuovo champion `R26_F1_TRIPLE_win`. Procedere a validazione su highway/full (scenari pregress R24F)
   - Se F5 batte F1 → confermare asse E (early stop = giusto)
   - Se F1 ≈ max(F2,F3,F4) → c'è saturazione; un fattore è dominante → scegliere quello + ulteriore esplorazione
   - Se F1 < max(F2,F3,F4) → interazione negativa (raro); investigare quale coppia è ottimale

### R3 — Studio EventProp (RIMANDATO)

Originariamente pianificato dopo R2, ora rimandato dopo R26+. Da iniziare quando il problema "T-tracking flat" sarà chiuso (R26 candidato risolutivo). Stessa logica R25: ablation lever-by-lever (clip, lr peak, warmup, init scaling, detach periodico, thresh_jump learnable, full λ_fatigue), trovare almeno UN setup stabile.

---

## 🎯 Stato precedente (2026-06-02 — R2 CHIUSO con caveat, R3 next) — SUPERATO da R24F+R25+R26

**Fase corrente**: **R2 — Studio Prodigy CAPIRE** ✅ chiuso (con caveat). PRODIGY_DEEP_STUDY.md ora ha parte 1+2+3 (~750 righe). Aspetta direzione utente per R3 (EventProp serio) o R4 (scenari misti).

### R2 verdetto (sintesi)

- **Prodigy NON è "broken"** (AUDIT §2.2 confutato): con `betas=(0.9, 0.99)` attivo (W1) pareggia BPTT+AdamW numericamente (val_total 0.228 vs F2 0.226, 10ep vs 15ep).
- **W1 è il singolo lever più impattante**: val_total da 0.303 (default) → 0.228 (W1). Conferma "dramatic improvement" madman404.
- **V2 (d0=1e-5)** ≈ W1: val_total 0.230. Conferma fix konstmish ufficiale.
- **Setup CANONICAL completo** (P-E) ≈ P-B singolo: gli altri lever (d_coef, use_bias, cosine) sono marginali in questo task.

### Caveat critico (Lezioni M1-M4)

⚠️ **TUTTI i 5 esperimenti hanno violin G7 collassati**: la rete predice CONSTANTS per i 5 params IDM, NON decodifica vero. Causa: highway-only training (tutti scenari hanno stessi IDM params target). 

**Implicazione**: val_total è INGANNEVOLE in highway-only. Tutti i ranking pregress (T30, SW, P15) sono confusi dallo stesso problema. **Verdetto Prodigy vs AdamW richiede R4 (scenari misti)** per essere conclusivo.

⚠️ La predizione "d frozen" era SBAGLIATA: d sale a 0.017-0.195 in tutti i 5 esperimenti R2 (era 0.001-0.003 in T30 forse per assestamento lungo). Caratterizzazione affrettata da single-metric per-epoch.

**Doc radice**: [`document/AUDIT_2026-06-02.md`](AUDIT_2026-06-02.md) — bilancio onesto post-T30 che ha generato la roadmap R1+R2+R3.

### Cronologia recente

1. **8 run T30** (4 arch × 2 opt × 30 ep) → 5 affermazioni dichiarate ma non dimostrate (vedi AUDIT)
2. **AUDIT_2026-06-02.md** scritto → fermato la corsa in avanti
3. **R1 completato** → snapshot 4+1 architetture in `Arch_Tested/`
4. **R2 setup completato** → 5 esperimenti P-A..P-E pronti, ora in esecuzione Azure
5. **R3 pending** → studio EventProp serio (dopo R2)

### R1 — Arch_Tested/ (FATTO)

Snapshot self-contained delle 5 architetture funzionanti:
- ⭐ **`BASELINE_BPTT_864p_PRE_EVENTPROP`** (source P12_S2D_F2_no_ou, lambda_sr=0.5, **vera baseline pre-EventProp**)
- `A1_baseline_BPTT_864p` (source T30_A1_BASELINE_adamw, lambda_sr=0 — ⚠️ DEPRECATED)
- `A8_attn_BPTT_3936p` (source T30, 3936p, val_data 0.163 best architettonico ma overfit possibile)
- `A3_stacked_skip_BPTT_2624p` (source T30)
- `EVPROP_ALIF_full_864p` (source SW_eventprop_alif_full_adamw_lr2e-3 5ep sched=none)

Per ogni: `core/` cleanup (solo classi necessarie + build_model factory ristretta), `train.py` CLI ridotta, `snapshot_original/` READ-ONLY con 13 plot G + log, `reproduce_training.ipynb`, README.

### R2 — Studio Prodigy CAPIRE (IN ESECUZIONE)

**Branch**: `Prodigy_Deep_Study` HEAD `a29b354`.

**Doc completa**: `document/PRODIGY_DEEP_STUDY.md` (parte 1 math + parte 2 community wisdom da paper Mishchenko 2024 + 5 GitHub Issues konstmish/prodigy + OneTrainer Wiki + kohya-ss community).

**Eureka critici emersi dalla ricerca multi-fonte**:
- **V2** (konstmish ufficiale, Issue #27): "Se `d` resta troppo piccolo, aumenta `d0` da 1e-6 a 1e-5/1e-4"
- **W1** (madman404, Issue #8): `betas=(0.9, 0.99)` → "dramatic improvement" (beta3=beta2^0.5)
- **W2** (community consensus): `d_coef=2.0` standard, non 1.0 default
- **Setup canonical "Prodigy is ALL YOU NEED"**: `lr=1.0 betas=(0.9,0.99) wd=0.01 use_bias_correction=True safeguard=True d_coef=2.0 d0=1e-6→1e-5 if frozen` + `cosine_no_restart T_max=epochs`

**5 esperimenti R2.2** (in esecuzione Azure, ~1.5h stima):
- **P-A**: replica T30 baseline (default Prodigy lib) → conferma d frozen
- **P-B**: P-A + betas=(0.9, 0.99) → isola W1
- **P-C**: P-A + d_coef=2.0 → isola W2
- **P-D**: P-A + d0=1e-5 → isola V2 (fix konstmish ufficiale)
- **P-E**: SETUP CANONICAL KOHYA completo + cosine_no_restart → vero benchmark "Prodigy in azione"

Setup comune: BASELINE_BPTT_864p_PRE_EVENTPROP, 10 ep × 100 step, results in `results/Prodigy_Study/`.

### R3 — Studio EventProp serio (PENDING)

Da iniziare dopo merge R2 in main. Stessa logica: leggere paper Wunderlich&Pehle 2021 + ref impl (Norse, snntorch), 7 lever isolati (clip, lr peak, warmup, init scaling, detach periodico, thresh_jump learnable, full λ_fatigue), trovare almeno UN setup stabile (grad_norm_max < 100), fair comparison vs BPTT.

### Stato branch git

```
main HEAD efa0639   ← R1 mergiato (Arch_Tested/ + BASELINE_PRE_EVENTPROP)
├── Prodigy_Deep_Study HEAD a29b354   ← R2 in esecuzione
├── Architecture_Exploration          ← branch storico (intatto)
├── Floor_Diagnostic                  ← branch storico (intatto)
├── Optimizer_Exploration             ← branch storico (intatto)
├── Training_Method_Exploration       ← branch storico (intatto)
└── Visualizer_Building               ← branch storico (intatto)
```

**Decisione utente**: i 5 branch storici NON vengono cancellati (rimangono come archeologia consultabile).

### Doc principali da leggere (priorità)

1. ⭐ [`AUDIT_2026-06-02.md`](AUDIT_2026-06-02.md) — bilancio onesto + roadmap R1/R2/R3
2. [`PRODIGY_DEEP_STUDY.md`](PRODIGY_DEEP_STUDY.md) — math + community wisdom Prodigy
3. [`../Arch_Tested/README.md`](../Arch_Tested/README.md) — overview 5 architetture salvate
4. [`SIMULATOR_FINDINGS.md`](SIMULATOR_FINDINGS.md) — drift T² + cut-in analysis simulator
5. [`EVENTPROP_OPTIMIZER_SWEEP.md`](EVENTPROP_OPTIMIZER_SWEEP.md) — sweep 4×11 origine SW_eventprop best

### Cosa fare adesso

- ⏳ **Aspettare risultati R2 da Azure** (~1.5h, 5 esperimenti × ~15-17 min)
- Quando finiti: pull `results/Prodigy_Study/`, analizzare via celle 4-5 notebook, scrivere PRODIGY_DEEP_STUDY.md parte 3 con verdetto
- Poi: merge R2 → main, iniziare R3 EventProp_Deep_Study

---

## 📜 STORIA PRECEDENTE (pre-R1, 2026-06-01)

> Sezione conservata per archeologia. **Le conclusioni qui sotto sono state riaperte dall'AUDIT_2026-06-02**.

### F2 EventProp chiuso (pre-audit, 2026-06-01)

Sweep 4×11 = 44 run aveva dato:
- val_data baseline 0.2218 vs eventprop_alif_full 0.2226 (pareggio, Δ < 0.4%)
- Robustezza optimizer: baseline 11/11 successi, EventProp 5/11
- Spike rate: baseline 4.1% vs EventProp 25.7%

**Conclusione del momento**: "baseline ALIF+BPTT+SurrogateSpike confermato production". 

⚠️ **Riaperto da AUDIT §2.1**: "EventProp non funziona" è dichiarazione non dimostrata (mai testato con tuning serio: clip aggressivo, warmup, init scaling, detach periodico). Lo studio R3 riparte da capo.

**🏆 STATO PRINCIPALE: P14 CHIUSO** — decomposizione completa del floor val~0.28:

```
Floor totale 0.2805 = 100%
├─ OU noise              0.0543   ← 19.3%   (irriducibile in deploy)
├─ Spike-rate regularizer 0.0006   ← 0.2%   (trascurabile)
├─ Po2 quantization      0.0006   ← 0.2%   (TRASCURABILE — Po2 resta ON deploy)
├─ SR × Po2 interaction  0.0052   ← 1.9%
└─ Residuo architettura  0.2198   ← 78.4%  (LIMITE DOMINANTE)
```

**Best assoluto raggiunto**: F7 val=0.2198 (no OU + no SR + no Po2, ancora in trend DOWN @E15).

**Architettura corrente**: CF_FSNN_Net parametrizzabile h=32, r=8 → 864 params. Baseline confermato sufficiente da sweep STEP 2B (capacity falsificata) e Plan B Optimizer_Exploration (val=0.2805 baseline AdamW).

**Optimizer scelto**: AdamW + OneCycleLR + h=32, r=8 + 15 ep × 190 step cap. Prodigy archiviato (≈ AdamW, vedi FUTURE_WORK F1 per re-test post-floor).

---

## 📊 Storia dei 9 setup convergenti al floor (range 0.279-0.290)

| Setup | val_best | Sorgente |
|-------|----------|----------|
| 5× capacity sweep (h=32→128) | 0.279-0.280 | STEP 2B (sweep), Optimizer_Exploration |
| AdamW b=8 OneCycle | 0.2805 | STEP 2C Plan B |
| Prodigy lr=0.1 b=1 dc=1.0 | 0.2823 | STEP 2C Plan A retry |
| Prodigy lr=0.5 b=1 dc=0.5 | 0.2857 | STEP 2C-bis #6 |
| Prodigy lr=0.1 b=1 dc=0.5 | 0.2902* | STEP 2C-bis #5 (* ancora migliorabile) |

**Conclusione robusta**: il floor è strutturale, indipendente da capacità/optimizer/scheduler/batch_size/d_coef/n_train.

---

## 🔬 Decomposizione validata da STEP 2D (Floor_Diagnostic)

7 esperimenti F1-F7 hanno isolato la causa di ogni fattore. **OU noise** (errori percezione V2X simulati nel generator) è la SOLA componente non-architetturale rilevante (19.3% del floor). Po2 e Spike-rate regularizer pesano insieme 0.4% — **decisione utente di mantenere Po2 in deploy è validata**.

**Repo HEAD storico** (per archeologia): `534c2af` — `fix: _push_results non importa torch (kernel Jupyter Azure non lo ha)`

**Progetto**: CF_FSNN — Spiking Neural Network per identificazione parametri car-following ACC-IDM (con base IIDM, Treiber Ch12 Sez.12.4). Target hardware: PYNQ-Z1 FPGA.

**Architettura rete corrente**: CF_FSNN_Net **parametrizzabile** (h=hidden_size, r=rank). Default config.py: h=32, r=8 → 864 params. Sweep STEP 2B testato: h∈{32, 48, 64, 96, 128}.

**🔥 DIAGNOSI ROVESCIATA — P9 FALSIFICATO 2026-05-29**:

Il capacity sweep STEP 2B (5 runs highway-only con h=32, 48, 64, 96, 128) ha mostrato:

| h | r | params | val_best | Spike% |
|---|---|---|---|---|
| 32 | 8 | 869 | 0.2802 | 8.4 |
| 48 | 12 | 1685 | **0.2789** ★ | 9.1 |
| 64 | 16 | 2757 | 0.2790 | 10.5 |
| 96 | 24 | 5669 | 0.2797 | 7.7 |
| 128 | 32 | 9605 | 0.2792 | 10.3 |

**Range val_best = 0.0013 (1.3 millesimi) su 11× parametri.** Aumentare la rete da 869 a 9605 parametri (+1004%) migliora val_best dello 0.46% — è rumore statistico, non miglioramento.

**P9 (capacity insufficiency) è FALSIFICATO**. Il plateau ≈ 0.28 NON è dovuto a capacity insufficiente.

**Nuovi problemi aperti (P12, P13)**:
- **P12** — Plateau non-capacity: causa rimane da identificare (ipotesi: minimi locali da OneCycle troncato + early stop aggressivo, saturazione dataset, Pareto PINN, Po2 floor)
- **P13** — Scenario crashes: **urban** crash E3 per dead-neurons (spike=0.6%), **truck** crash E5 per post-convergence grad explosion. Truck però raggiunge **val_best=0.1601 a E5** (43% migliore di highway!) — la rete CAN scendere sotto 0.20 su task specifici

**Eureka utente confermata + raffinata**: i runs si fermano in 4 epoche per early-stop aggressivo + OneCycleLR che a E4 è solo al 40% del ciclo (decay phase profonda mai raggiunta). Possibili minimi locali — da testare con scheduler con warm restart + più epoche.

**Hardware constraint**: tutti i fix devono mantenere compatibilità FPGA (pesi power-of-2, leak bit-shift, surrogate hardware-friendly senza propagation al threshold).

---

## 📍 Prossimo step — DECISIONE STRATEGICA UTENTE (2026-05-31)

Dopo STEP 2C+2D, sappiamo dove c'è margine e dove non c'è. 4 strade per il prossimo capitolo. Vedi `FUTURE_WORK.md` per dettagli ognuna.

### Opzioni (descritte in dettaglio in FUTURE_WORK.md)

| ID | Mossa | Costo | Potenziale | Rischio |
|----|-------|-------|------------|---------|
| **F2** | **Switch a EventProp** (paradigma training diverso) | alto (~2-3 settimane dev) | alto se BPTT è il vero limite | medio (cambio paradigma) |
| **F3** | Curriculum noise (training su noise_scale crescente) | basso (~1 giorno dev) | basso-medio (-0.05 forse) | basso |
| **F4** | Architettura modificata (più layer, attention, ALIF mod) | medio (~1 settimana dev) | alto sul residuo 78% | medio |
| **F5** | **Accettare floor 0.28 → procedere a deploy PYNQ-Z1** | minimo | conclusione progetto | nessuno |

**EventProp** (Wunderlich & Pehle 2021) è particolarmente interessante: invece di propagare gradienti continui via surrogate function attraverso il tempo (BPTT), calcola gradienti esatti event-based usando aggiunte (Hamiltonian backprop). Se il floor architettura è dovuto a errori di approssimazione del surrogate, EventProp potrebbe sbloccarlo.

**Reference EventProp**:
- Wunderlich & Pehle (2021), "Event-based backpropagation can compute exact gradients for spiking neural networks"
- snnTorch ha implementazione: `snntorch.functional.eventprop` (recente, da verificare versione)
- Riferimento skill: `SNN-expert` ch08 §Surrogate Gradient Learning

---

## 🎯 Criteri di successo (proposti 2026-05-29)

### Quantitativi — hard targets

| Criterio | Soglia | Razionale |
|---|---|---|
| **val_loss totale** | **< 0.15** competitivo, **< 0.20** buono, **< 0.10** SOTA | Treiber Ch17: residual error floor ~20% → 0.15 ≈ 10% inferiore = eccellente |
| **L_data / L_total** | > 0.80 | La rete deve risolvere il task, non barare con L_phys |
| **RMSE per-param** | < 15% del range fisico | v0±5.5 m/s, T±0.3s, s0±0.6m, a±0.33 m/s², b±0.4 m/s² |
| **Spike rate** | 10–25% | SNN-expert default. Sotto=dead, sopra=no sparsity gain FPGA |
| **0 inf grad batches** | per ≥10 epoche | Stabilità BPTT |
| **String stability** | vₑ'(s) ≤ ½(fₗ-fᵥ) | Treiber Ch16 |
| **FP32 vs Po2 gap** | < 10% | Funzionalità FPGA preservata |

### Qualitativi
- Cross-scenario robust: val_{highway, urban, truck} non divergono oltre 2× (oggi: 0.279 vs 0.388 vs 0.160 = range 2.4×, fuori soglia)
- G7 violin: 80%+ predizioni dentro range fisico IDM
- G13 trajectory: gap simulato segue ground-truth con MAE < 1m per ≥ 5s

---

## 🛣️ Roadmap aggiornata STEP 2

| Step | Stato | Obiettivo | Esito |
|------|-------|-----------|-------|
| **STEP 2A** (fast iteration) | ✅ completato | Validare regime fast-iteration | val=0.2802, 17 min |
| **STEP 2B** (capacity sweep) | ✅ completato 7/9 | Verificare se capacity è bottleneck | **P9 FALSIFICATO** |
| **STEP 2C** (Optimizer Exploration) | ✅ completato | Sweep AdamW vs Prodigy (6 config Prodigy) | AdamW vince marginale, Prodigy archiviato |
| **STEP 2D** (Floor Diagnostic) | ✅ completato | Decomporre il floor val~0.28 | **P14 CHIUSO**: 78% architettura, 19% OU, <1% Po2+SR |
| **STEP 2E** (mitigation) | 🟡 DECISIONE UTENTE | 4 opzioni: EventProp / curriculum / arch mod / accept-and-deploy | vedi FUTURE_WORK |

---

## 🗂️ Mappa dei documenti

| File | Quando consultarlo |
|------|---------------------|
| **SESSION_RESUME.md** (questo file) | Sempre per primo, in ogni nuova sessione |
| **GLOSSARY.md** | Decode acronimi P/A/B/F/T/PF/G/STEP usati nei commit/log |
| **WORKFLOW.md** | Come fare un nuovo esperimento end-to-end |
| **TIMELINE.md** | Storia decisioni + cosa è stato provato/scartato |
| **P_S.md** | **Living doc**: 11 problemi diagnosticati + soluzioni applicate/scartate |
| `report/report_4.md` | Snapshot architettura + 12 fix SNN-expert (storico) |
| `report/report_1.md`, `report_2.md`, `report_3.md` | Snapshots più vecchi |
| `cf_model_recommendation.md` | Analisi modelli candidati (IDM/IIDM/ACC-IDM) |
| `optimization_ideas.md` | Idee tuning a lungo termine |
| `training_plan.md` | Piano addestramento (potrebbe essere obsoleto) |
| `use_cases.md` | Use cases V2X (UC2 cut-in, ecc.) |
| `project_core_guidelines.md` | Vincoli hardware, design principles |

---

## ❓ Domande aperte (decisione utente per STEP 2C)

| ID | Domanda | Opzioni |
|---|---|---|
| **Q1** | Approccio STEP 2C | **A** = Compositional best-practice (AdamW+CosineWR+SWA, raccomandato) / **B** = Prodigy drop-in (parameter-free) / **C** = R&D SurrogateSAM (originale) |
| **Q2** | Granularità | 1 singolo run 2C-α / Sweep 2C-α + 2C-β a confronto |
| **Q3** | Criteri "funziona bene" | Conferma soglie val < 0.15 competitivo / < 0.20 buono / < 0.10 SOTA (vedi sezione criteri) |

**Default raccomandato in attesa di risposta**: Q1=A, Q2=1 run, Q3=confermato.

---

## 🧮 Catalogo Ottimizzatori (per riferimento STEP 2C)

### Tier 1 — Validati su SNN
| Ott. | Anno | Pro | Cons | Default skill SNN-expert |
|---|---|---|---|---|
| AdamW | 2017 | Decoupled wd, stabile | — | ✅ default consigliato |
| Cosine warm restart (SGDR) | 2017 | Esce dai minimi locali | 1 hyperparam T_0 | ✅ default scheduler |
| SAST (SAM applicato a SNN) | 2026 | Flat minima, +generalization | 2× tempo | recente |
| Lion (Google) | 2023 | Veloce, ½ memoria Adam | sign-only può essere troppo aggressivo | usato in Spyx |

### Tier 2 — Generalist potenti, non testati su SNN
| Ott. | Anno | Pro | Cons | Per noi |
|---|---|---|---|---|
| Prodigy | ICML 2024 | Parameter-free (no lr tuning) | Non testato SNN | ⚠️ rischio |
| Sophia (Stanford) | 2023 | Hessian-aware, 2× speedup LLM | Costo Hessian | ⚠️ ricerca |
| AdaBelief | NeurIPS 2020 | Stabile vs Adam | +0.5% marginale | low priority |
| D-Adaptation | ICML 2023 | Parameter-free predecessore | Sostituito da Prodigy | skip |

### Tier 3 — Wrapper (compongono su altro optimizer)
| Wrapper | Effetto | Costo | Per noi |
|---|---|---|---|
| **SAM** | Flat minima (2 forward+backward) | 2× tempo | ⭐ STEP 2C-β |
| **Lookahead** | Smooth oscillazioni (k fast + slow pull) | +5% memoria | medio |
| **SWA** | Average weights ultime N epoche | trascurabile | ✅ STEP 2C-α |
| **Snapshot ensemble** | Ensemble ai warm restart | trascurabile | future |

### Tier 4 — Specifici SNN (sperimentali, non in production)
| Metodo | Anno | Note |
|---|---|---|
| ADMM-based SNN training | 2025 | Alternating direction, non SGD-derived |
| Rate-based BP | NeurIPS 2024 | Sfrutta rate coding per ridurre BPTT |
| e-prop (Bellec) | 2020 | Eligibility traces locali |
| EventProp (Wunderlich) | 2021 | Adjoint exact, O(spikes) memoria |

### Decision matrix (h64_r16 highway target)
| Combinazione | Plateau escape | Stabilità BPTT | Po2-friendly | Dataset piccolo | Impl. | Total |
|---|---|---|---|---|---|---|
| Adam (attuale) | 1 | 3 | 2 | 2 | 5 | 13 |
| AdamW + Cosine WR | 4 | 4 | 3 | 4 | 4 | **19** ✓ |
| AdamW + SAM | 5 | 4 | 5 | 4 | 3 | **21** ⭐ |
| AdamW + SurrogateSAM (R&D) | 5 | 5 | 5 | 4 | 2 | **21** ⭐ |
| Prodigy | 4 | 3 | 2 | 3 | 4 | 16 |
| Lion | 3 | 3 | 3 | 3 | 4 | 16 |
| Sophia | 5 | 4 | 4 | 3 | 2 | 18 |

---

## ⚙️ Infrastruttura disponibile

### Codice principale (NON modificare senza tracking esplicito in P_S.md)
- `core/network.py` — `CF_FSNN_Net(hidden_size=None, rank=None)` + layers + funzioni fisica ACC-IDM (kwargs STEP 2B per sweep)
- `core/neurons.py` — `ALIFCell`, `LICell` (hardware-friendly)
- `core/hardware.py` — `SurrogateSpike_Hardware` (γ=1.0 A3), `PowerOf2Quantize`
- `train.py` — main + `pinn_loss` + `train_epoch` + `BatchCSVLogger` + early stopping + CLI scenario/cut_in/n_train/n_val/cf_hidden_size/cf_rank
- `data/generator.py` — generatore sintetico ACC-IDM, `parse_scenario_mix`
- `config.py` — costanti (NON modificare scenario/cut_in qui: usa CLI da Cella 1)
- `utils/plot_diagnostics.py` — G1-G13 grafici
- `scripts/preflight.py` — `_checkpoint_loadable` ora legge h/r da config_snapshot (fix STEP 2B)

### Workflow
- `scripts/preflight.py` — doppio smoke obbligatorio prima di FULL (legge h/r da config_snapshot per loadable test STEP 2B)
- `Training_File.ipynb` — notebook universale per singoli runs approfonditi (10 celle, tracciato in git)
- `Training_File_Sweep.ipynb` — orchestratore sweep parametrico (7 celle: sweep + summary + plot comparativi + push aggregati)
- `.gitattributes` — `*.ipynb filter=nbstripout` (one-shot setup, mai più "would be overwritten by merge")

### Cache & artefatti
- `data/cache_*.pt` — dataset persistenti (NON committati, .gitignore)
- `checkpoints/<TAG>/` — pesi modello + CSV + plots (NON committati)
- `results/<TAG>/` — CSV + plots **tracciati in git** (whitelist .gitignore)

---

## 🔧 Comandi quick reference

### Locale (Windows PowerShell)
```bash
# Sync stato
git pull origin main && git log --oneline -5

# Lista esperimenti pushati
ls results/

# Analisi rapida di un run
python -c "import pandas as pd; df = pd.read_csv('results/<TAG>/training_log.csv'); print(df)"

# Smoke locale fast iteration (~9 min CPU laptop)
python train.py --tag local_check --scenario_mix highway --cut_in_ratio 0.0 \
                --n_train 200 --n_val 50 --epochs 3 \
                --early_stop_patience 1 --early_stop_delta 0.005 \
                --max_lr 2e-3 --seq_len 50
```

### Azure (Jupyter)
```bash
# Sync codice + notebook
git pull origin main

# Se git lamenta "Your local changes would be overwritten by merge":
git checkout -- Training_File.ipynb && git pull origin main

# Solo Cella 1 va modificata per nuovo esperimento
# Run All esegue: pull → preflight → FULL → display → push results

# Cleanup storage (se compute instance pieno)
!find checkpoints -name "best_model.pt" -delete   # mantiene CSV/PNG
!rm -rf checkpoints/<old_tag>                      # cancella un esperimento intero
```

### Commit di results (fatto automaticamente da Cella 8)
```bash
git add results/<TAG>/
git commit -F /tmp/commit_msg.txt   # messaggio generato auto da Cella 8
git push origin main
```

---

## 🚨 Lezioni cardinali (per non ripetere errori)

1. **NON applicare fix SNN "da manuale" senza verificare l'implementazione specifica del surrogate** (errore B4: detach reset rotto perché `SurrogateSpike_Hardware` non propaga al threshold). Vedi P5.

2. **NON modificare config.py manualmente su Azure** (errore P9_S1_highway_only: identico a P6_T3_full perché config.py non modificato). Vedi P10. Usa CLI/Cella 1.

3. **NON sprecare compute su training oltre il plateau** (P6_T3 ha sprecato ~2h girando E4 destinato al crash). Usa `early_stop_delta` adeguato. Su nostro plateau, `0.005` è giusto (`1e-4` è troppo sensibile, non ferma mai). Vedi P11 + STEP 2A.

4. **Il plateau val_loss ≈ 0.35 (full-mix) o 0.28 (highway-only) è strutturale** (capacity insufficiency). Non insistere con fix anti-crash: aumenta capacità o accetta il plateau. Vedi P8, P9.

5. **L'esplosione del gradiente è SINTOMO, non causa**: rete satura → spike rate degenera → catena ricorrenza U·V amplifica → boom. Vedi P7, P8.

6. **Tutti i fix devono mantenere compatibilità FPGA**: pesi power-of-2, leak bit-shift, surrogate hw-friendly. Vedi `project_core_guidelines.md`.

7. **Cache invalidate vanno rigenerate**: se cambi fisica (es. F1 s_safe=2.0) o scenario, cancella `data/cache_*.pt` o usa nome diverso. Il `CACHE_PATH` in Cella 1 ora include `n_train` + `scenario_mix` + `cut_in_ratio` → collisioni evitate.

8. **Telemetria T è sacra**: i CSV per-batch (`training_batch_log.csv`) sono l'unico modo per diagnosticare run abortiti. Non disabilitarli.

9. **La rete converge nel 10% di E1** (osservazione utente confermata dai dati). Non aspettare 5 epoche: usa fast-iteration con `n_train` ridotto + early stopping aggressivo per **iterare 10-20× più velocemente**. Vedi STEP 2A.

10. **Po2 quantization NON è il plateau**: i pesi raw sono float continui (STE). Il bottleneck è capacity vs task complexity (prova: highway plateau 0.28 ≠ full-mix plateau 0.35 — sarebbe stato lo stesso se Po2 fosse il bottleneck).

---

## 📊 Risultati storici principali

| TAG | Config chiave | E completate | val_loss best | Esito |
|-----|---------------|--------------|---------------|-------|
| (pre-F1) | seq=100, lr=5e-3, no fix | 0 | — | ❌ crash B1000 |
| `A1_onecycle_v3` | + B4 (poi rollback) | 0 | — | ❌ crash B126 (B4 incompatibile) |
| `P6_T2_full` | A3+A1+A2 | 1 | 0.371 | ❌ crash E2 B2395 |
| `P6_T3_full` | + B5 | 3 | **0.354** | ❌ crash E4 (47 inf grad) |
| `P9_S1_highway_only` | (=P6_T3, config.py drift) | 3 | 0.354 | ❌ identico a P6_T3 |
| `P9_S1_highway_v2` | + P10 + P11 + scenario CLI | 2 | **0.277** | ❌ crash E3 — **P9 CONFERMATO!** (-22% vs full-mix) |
| **`P9_S2A_fast_baseline`** | + STEP 2A (n_train=500, delta=0.005, h32_r8, highway) | 4 | **0.2802** | ✅ confermata fast-iteration |
| **`P9_S2B_h32_r8_hw`** | sweep STEP 2B (h=32, r=8) | 4 | 0.2802 | ✅ baseline replicato |
| **`P9_S2B_h48_r12_hw`** | sweep STEP 2B (h=48, r=12) | 4 | **0.2789** ★ | ✅ best del sweep |
| **`P9_S2B_h64_r16_hw`** | sweep STEP 2B (h=64, r=16) | 4 | 0.2790 | ✅ sweet spot |
| **`P9_S2B_h96_r24_hw`** | sweep STEP 2B (h=96, r=24) | 4 | 0.2797 | ✅ |
| **`P9_S2B_h128_r32_hw`** | sweep STEP 2B (h=128, r=32) | 4 | 0.2792 | ✅ |
| **`P9_S2B_h64_r16_urban`** | sweep STEP 2B (urban) | 2 | 0.3884 | ⚠️ crash E3 (dead neurons) |
| **`P9_S2B_h64_r16_truck`** | sweep STEP 2B (truck) | 5 | **0.1601** ★ | ⚠️ crash E5 (best assoluto!) |

**Pattern aggiornato 2026-05-29**: 
- Capacity highway: tutti i 5 valori (h=32→128) hanno val_best ∈ [0.279, 0.280] → **P9 FALSIFICATO**
- Scenario diversity: highway 0.279 ok, urban 0.388 crash (dead neurons), truck 0.160 best ma crash post-converg
- **Insight chiave**: la rete CAN scendere sotto 0.20 (truck dimostra), il limite è scenario-specific, non capacity.

---

## 🎯 Cosa fare adesso (per un nuovo agente / sessione)

### Se l'utente dice "ho lanciato STEP 2A, ecco i risultati":
1. `git pull origin main`
2. `ls results/P9/P9_S2A_fast_baseline/`
3. Analizza `training_log.csv` per val_loss
4. Confronto con `P9_S1_highway_v2` (val=0.277)
5. Applica decision tree sopra → propone STEP 2B

### Se l'utente dice "non ho ancora lanciato":
- Ricorda che il notebook è già pronto (commit `ed8debb`)
- Verifica che lui faccia `git pull` su Azure
- Spiega cosa atteso: ~15-25 min, val_loss ≈ 0.28-0.30 atteso

### Se l'utente dice "nuova diagnosi/problema":
1. Leggi `P_S.md` per stato problemi correnti
2. Leggi `TIMELINE.md` per capire perché siamo qui
3. Consulta skill `SNN-expert` (ch22 §22.x) se è diagnosi tecnica
4. Propone fix tracciandolo come nuovo `P<N>` in `P_S.md`

### Se l'utente vuole STEP 2B:
- Discuti con lui quali variabili sweep (HIDDEN_SIZE / RANK / scheduler)
- Implementa CLI `--cf_hidden_size` e `--cf_rank` in `train.py`
- Aggiorna notebook Cella 1 con `'cf_hidden_size': 64`, ecc.
- Crea N esperimenti con TAG `P9_S2B_h<N>_r<R>` (es. `P9_S2B_h64_r16`)
- Mostra tabella confronto risultati

---

## 🔗 Esterno

- **GitHub**: https://github.com/carmineesposito01-ice-beep/SNN_Experiment
- **Skill diagnostica**: `SNN-expert` (locale, 23 capitoli, ch22 §22.2-22.4 critici)
- **Skill car-following**: `car-follow-expert` (Treiber & Kesting 2025, ch12 ACC-IDM)
- **Hardware target**: PYNQ-Z1 FPGA (Xilinx Zynq-7020)

---

## 📝 Log aggiornamenti questo file

| Data | Cambio | Autore |
|------|--------|--------|
| 2026-05-28 18:00 | Creato (post commit `3dedf51`) | claude (session 28/05) |
| 2026-05-28 21:00 | Aggiornato post `ed8debb` (STEP 2A) + P9 confermato + eurekas utente | claude (session 28/05) |
| 2026-05-29 12:00 | Aggiornato post `534c2af` (sweep STEP 2B 7/9 + analisi optimizer + design STEP 2C). **P9 FALSIFICATO**, apertura P12+P13, decision matrix optimizers, ricetta modernista AdamW+CosineWR+SWA+SAM proposta | claude (session 29/05) |
