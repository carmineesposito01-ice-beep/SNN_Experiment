# `matlab/` — mappa della cartella

> **Perché questo file**: nella root ci sono **106 `.m`** di ~10 scopi diversi. Questa è la mappa per orientarsi
> senza aprirli a caso. *(Il riordino fisico in sottocartelle è stato VALUTATO e rimandato — 2026-07-18: 65 file
> caricano i dati con `fullfile(here,…)` e si romperebbero con un `mv`; si tiene la struttura flat + questa mappa.
> Vedi §Riordino.)*
>
> **Documenti di processo** (la verità sta lì, non qui): architettura/metodo HDL → `../document/HDL_PHASE.md`
> (§3.1 = contratto d'interfaccia, §3.1.1 = *l'architettura segue il sorgente*, §9 = gotcha) · studio decode LUT →
> `../document/DECODE_LUT_SWEEP.md` · Fase B → `../document/FPGA_PHASE_B_POWER.md`.

## ⚠️ Due architetture — non confonderle

| | sorgente | LUT | stato |
|---|---|---|---|
| **B2 time-mux** (1 neurone/clock, `hdl.RAM`) | `snn_b2_fsm.m` → `snn_top_b2.m` | **4.223** (~7,9%) | ✅ **DEPLOYATA** → bitstream PYNQ-Z1 |
| parallela (neuroni srotolati) | `snn_hdl_<name>.m` (via `make_hdl.m`) | **23.186 = 44%** | ⛔ **SUPERATA** (~5,5× più grande) |

**Regola:** l'architettura HDL generata **segue il sorgente** — chart che chiama `snn_b2_fsm` ⇒ time-mux;
chart che inlinea `snn_core` (1 chiamata = 1 inferenza) ⇒ parallela **superata**. L'auto-flow non serializza da solo.

## Cosa c'è, per scopo

### Core single-source (il cuore — non toccare senza rilanciare la parità)
`snn_core.m` (core type-parametrizzato: double **e** fixed) · `snn_types.m` (tipi `fi`) · `snn_normalize.m`
(fisico→`xn`; **gira in SW/PS, non in HDL** — §3.1) · `snn_decode.m` (double) · `snn_decode_lut.m` (fixed,
σ-LUT **parametrica in N**; **N=64 è il decode del campione** dal 2026-07-14 — `../document/DECODE_LUT_SWEEP.md`) ·
`snn_decode_hdl.m` (fixed, σ-LUT 256 — **LEGACY**: era il decode deployato *fino al* 2026-07-14; tenuto come
golden di regressione, `snn_decode_lut(.,256)` gli è bit-identico) · `snn_entry.m` (normalize→core→decode) ·
`acc_iidm_open.m` (**unica fonte** della matematica ACC-IIDM: `accel = f(stato, params)`, non integra;
**type-parametrico** come `snn_core` — `double` per il riferimento, `fixed` per il blocco HDL-ready; la usano
il blocco SP2/SP3 e il plant `cf_plant_lib/ACC_IIDM`) · `acc_types.m` (prototipi di tipo dell'IIDM: `double` e
`fixed`, `nfrac` sweepabile — modello `snn_types.m`) · `champ_weights.m` (helper pesi).

### B2 — architettura deployata
`snn_b2_fsm.m` (FSM time-mux, `hdl.RAM`, serializzazione **bit-exact** di `snn_core`) · `snn_top_b2.m` (top del
bitstream: `xn`+`start` → `params`+`done`) · `snn_neuron_b2.m` · `gen_b2_rom.m` (genera `b2_rom_active.m` = pesi baked
del champion attivo; **il file generato è gitignored**).

### Parallela — SUPERATA (tenuta per storia/confronto)
`snn_hdl_Donatello|Leonardo|Michelangelo|Raffaello.m` · `gen_hdl_tops.m` · `make_hdl.m`.

### Generazione HDL
`make_hdl_top_b2.m` (**il top deployato**) · `make_hdl_b2.m` · `make_hdl_b2fsm.m` · `make_hdl_decode.m` (decode
deployato) · `make_hdl_decode_lut.m` (decode LUT-N, sweep) · `make_hdl_ann.m` · `make_hdl_micro.m` · `check_hdl.m`.

### Librerie Simulink (builder + `.slx`)
`build_library.m` → **`snn_champions_lib.slx`**: 4 blocchi champion **comportamentali** (double, self-contained,
1 chiamata = 1 inferenza — **non** sintetizzabili: double+`exp`) ·
`build_hdl_variants.m` → aggiunge alla stessa libreria i 7 blocchi **HDL-ready SELF-CONTAINED**
(`Donatello_Champion` + `Donatello_LUT{16..512}`) ·
`build_plant_lib.m` → `cf_plant_lib.slx` (ACC-IIDM) · `build_closed_loop_demo.m`.

Lo stesso builder aggiunge anche **`Donatello_ACC_IIDM`** (SP2/SP3): campione LUT-64 + ACC-IIDM **open-loop**,
`s,v,dv,v_l → accel`, la catena completa stato→azione. **HDL-Ready dal 2026-07-16** (SP3): l'IIDM è in
fixed-point (`acc_types`) e HDL Coder ne genera il VHDL. ⚠️ **HDL-ready ≠ deployato**: il bitstream resta la
sola SNN, e l'IIDM in fixed è **caro** (OOC: +6974 LUT, Fmax 10,6→2,0 MHz per le 4 divisioni srotolate — il
recupero via reciproci-una-volta è un SP a sé). Doc: `../document/SP3_ACC_IIDM_HDL.md`. Cancelli:
`run_block_acciidm_test.m` · `run_block_closed_loop_test.m` · `run_acc_fixed_sweep.m` · `run_block_hdl_gate.m`.

La matematica ACC-IIDM ha **una sola fonte**, `acc_iidm_open.m`: la usano sia il blocco SP2 sia il plant
closed-loop `cf_plant_lib/ACC_IIDM` (che aggiunge solo l'integrazione). Idem `local_normalize`
(`build_hdl_variants:normalize_code`), condivisa fra i blocchi HDL-ready e quello SP2.

### ACC-IIDM — controllore VELOCE `Donatello_ACC_IIDM_M` (SP4) + varianti
`build_hdl_variants` aggiunge anche **`Donatello_ACC_IIDM_M`** (SP4, doc `../document/SP4_ACC_IIDM_FAST.md`): la
variante veloce del controllore, con le 5 divisioni dell'IIDM **sequenziate su UN divisore** da una FSM a stadi
(OOC **8614 LUT · 2134 FF · 71 DSP · 9,30 MHz**, `dmax=0` vs SP3; SP3 era 2,0 MHz per le 4 divisioni srotolate).
Funzioni-fase (single-source col model, inlinate nella chart): `iidm_prep.m` (guardie/sqrt/filtro OU) ·
`iidm_nd.m` (operandi della divisione k) · `iidm_use.m` (consumo del quoziente) · `iidm_tanh.m` (stadio `tanh`
a sé, il collo) · `iidm_final.m` (blend+clamp→accel) · `fsm_div.m` (la **UNICA** `divide()` → 1 divisore in HW).
Model + MEX: `acc_iidm_fsm.m` (model FSM) · `fsm_step.m`/`collect_step.m` (step MEX: FSM / riferimento SP3) ·
`build_acc_iidm_fsm_mex.m`. Variante L (reciproci a LUT, **scartata** ma committata per storia):
`acc_recip_lut.m` · `acc_sweep_kernel.m` · `build_acc_sweep_mex.m`.

#### Come si usano i blocchi HDL-ready (`Donatello_Champion`, `Donatello_LUT{N}`)
*(ogni blocco porta la stessa spiegazione nella propria **Description**, visibile in Block Properties)*

| | |
|---|---|
| **I/O** | fisico: `s, v, dv, v_l` → `v0, T, s0, a, b` — niente `start`/`done` |
| **Tipi** | ingressi **fixed con ≥20 bit frazionari** (es. `fixdt(1,32,20)`). **Il `double` non compila**: per sorgenti double (es. `test_dataset.mat`) interporre un **Data Type Conversion** |
| **Semantica** | **1 campione = 1 inferenza** (edge-triggered sul cambio d'ingresso); le uscite tengono l'ultimo valore |
| **Rate** | ogni ingresso va tenuto **≥ ~341 passi** (il time-mux elabora 1 neurone/clock). Il valore esatto **non conta**: qualunque hold ≥341 è corretto |
| **Architettura** | forward **B2 time-mux** = quella del bitstream → `makehdl` genera time-mux (con `DualPortRAM`) |
| **Self-contained** | zero dipendenze `.m`: il `.slx` genera VHDL anche su un altro PC |

Verifiche: **`run_block_hdl_gate.m`** (isola il `.slx` e lancia `makehdl`) · **`run_block_traj_test.m`** (pilota il
blocco con le traiettorie di `test_dataset.mat` → `dmax = 0`). Dettagli e prove: `../document/DECODE_LUT_SWEEP.md` §6,
`../document/HDL_PHASE.md` §3.1.3-§3.1.4.

### Test / verifica (i cancelli)

> ⚠️ **Due trappole scoperte il 2026-07-14 — leggere prima di fidarsi di un "verde"** (`../document/HDL_PHASE.md` §2.1):
> 1. **Nessuno dei cancelli storici asserta**: stampano `>> BIT-EXACT MATCH` o `>> MISMATCH (da debuggare)` e
>    **ritornano comunque**. In un run automatico passano **sempre**: bisogna *leggere* l'output.
> 2. **Sono poco profondi**: `run_b2_parity` gira su **16 campioni**, `test_b2_fsm` su **12 control-step**, l'uso reale
>    è **1000**. Con questo velo un bug reale dell'FSM è sopravvissuto mesi a cancello verde.
>
> I cancelli **nuovi** (`run_b2_parity_dataset`, `run_block_*`) **assertano** e girano sul **dataset intero**.

**`run_b2_parity_dataset.m`** ⭐ (FSM B2 vs core su **60 traiettorie × 1000 step × 4 champion** → atteso **0/240.000**;
richiede i MEX) · **`run_block_sync_check.m`** ⭐ (i blocchi self-contained **inlinano** i sorgenti: verifica che non
siano rimasti indietro; se fallisce → `build_hdl_variants`) ·
`run_parity_tests.m` (**cancello 1:1**: double vs golden PyTorch ~2e-6) · `run_b2_parity.m` (FSM B2 vs core su 16 campioni golden — **non è una prova di equivalenza**) ·
`run_fixed_parity.m` · `run_fixed_sweep.m` (errore vs bit di frazione) · `run_hdl_verify.m` · `run_block_parity.m` ·
`run_plant_parity.m` · `run_b15a_validate.m` (validazione funzionale via MEX) · `run_lut_sweep.m` (accuratezza vs N) ·
**`run_block_hdl_gate.m`** (cancello "altro PC": copia il solo `.slx`, toglie `matlab/` dal path, `makehdl` deve
generare VHDL time-mux) · **`run_block_traj_test.m`** (blocchi pilotati con le traiettorie di `test_dataset.mat`:
`dmax` vs riferimento **deve essere 0**; verifica anche che su ingresso costante l'inferenza sia UNA) ·
**`run_block_acciidm_test.m`** ⭐ (SP2: la catena `s,v,dv,v_l → accel` del blocco `Donatello_ACC_IIDM` vs
riferimento MEX + decode-64 + `acc_iidm_open`, **`dmax = 0`** sul dataset. Verificato **sensibile**: la variante
con l'IIDM mis-gated lo fa fallire — `../document/SP2_ACC_IIDM.md`) ·
**`run_block_closed_loop_test.m`** ⭐ (SP2 in **anello CHIUSO**: dato il leader (`x_l`, `v_l`) l'anello calcola gap
e `dv`, li passa al blocco e integra l'ego con l'`accel` che ne esce; vs riferimento `snn_cl_step_mex`,
**`dmax = 0`**. ⚠️ `dv` del dataset **non** è `v - v_l` della stessa riga: è `v[k-1] - v_l[k]` — vedi
`../document/SP2_ACC_IIDM.md` §Anello chiuso, che riporta anche perché la convenzione **non** cambia i risultati) ·
`test_b2_fsm.m` · `test_top_b2.m` · `test_decode.m` · `test_ann_mlp.m` · `tb_b2_fsm.m` · `tb_hdl_Donatello.m`.

### Harness RTL — Fase B2.0 (validazione in Vivado xsim del VHDL/Verilog GENERATO)

> Validano che l'**RTL generato** (non il blocco Simulink) riproduca il blocco **bit-exact** in xsim, sul dataset,
> in anello aperto e chiuso. Report: `../report/B2_0_CHECKPOINT_REPORT.pdf`. Metodo chiave: golden **fedele al
> blocco** — il riferimento `r16` NON è il blocco (diverge a step ~52 per la `local_normalize` fixed + il
> pilotaggio a ingresso tenuto), quindi si estrae l'algoritmo esatto della chart e lo si guida clock-per-clock.

**Generazione + I/O:** `rtl_gen_dut.m` (blocco → VHDL/**Verilog**, avvolge in subsystem, legge l'entità; param
lingua) · `rtl_export_vectors.m` (stim/gold `.mem` dal golden fedele) · `rtl_run_xsim.m` (invoca il runner + parse
`RTLRES`) · `test_rtl_export.m` (round-trip `.mem`).
**Golden fedele al blocco:** `extract_champion_algo.m` / `extract_acciidm_m_algo.m` (estraggono l'algoritmo della
chart) · `snn_traj_champion.m` / `acciidm_m_traj.m` (driver clock-per-clock = il blocco) · `build_champion_golden.m`
/ `build_acciidm_m_golden.m` (estrai + codegen MEX).
**Harness A — SNN (`Donatello_Champion`, VHDL):** `run_rtl_validate.m` (cancello **A-1**: 5 param RTL == blocco,
**0/15000**) · `sensitivity_A1.m` · `rtl_metrics.m` (accuratezza param, metriche SNN RTL-grounded).
**Harness B — controllore (`Donatello_ACC_IIDM_M`, VERILOG):** `run_rtl_validate_b.m` (**B-1**: accel, **0/3000**) ·
`sensitivity_B1.m` · `cl_ref_acciidm_m.m` (anello di riferimento block-faithful) · `cl_export_plant_par.m` (vettori
anello, double bit-esatti IEEE-754) · `run_plant_par.m` (**PLANT-PAR**: plant-nel-TB == riferimento, **1800/1800**) ·
`run_closed_loop.m` (**B-LOOP** + **BEHAV**: anello RTL == riferimento **2400/2400**, gap>0). Testbench Verilog in
`axi/champion/` e `axi/acciidm_m/`.
**Caratterizzazione:** `characterize_drift.m` (deriva blocco-fisico vs riferimento sull'accel: **sparsa** —
mediana 0 — ma coda ~69% del budget `E_snn`).
⚠️ Il controllore va in **Verilog** (in VHDL il divisore combinatorio dell'IIDM manda un indice-LUT a −1 a
time-0 in xsim, registri `U`); la SNN resta VHDL. Dettagli e numeri: `../document/HDL_PHASE.md` §6.

### Confronto ANN (Fase B)
`ann_mlp.m` · `ann_rom.m` · `gen_ann_rom.m` · `test_ann_mlp.m` · `make_hdl_ann.m`.

### Micro-benchmark energia (Fase B)
`micro_ac.m` · `micro_mac.m` · `make_hdl_micro.m`.

### Diagnostica / probe
`diag_quant.m` (quantizzazione stato vs bug) · `diag_ranges.m` (range segnali interni) ·
`probe_divide_bitexact.m` (G1 di SP4: blocco `Divide` == `divide()`, 300k coppie) ·
`probe_acciidm_sharing.m` (probe resource-sharing SP4). *(I probe di serializzazione B2 —
`snn_tick_probe*`/`snn_ram_probe`/`make_hdl_probe*` — rimossi il 2026-07-18: dead, chiusi da tempo.)*

### MEX (accelerazione)
`snn_traj_fixed.m` (kernel: normalize + core, traiettoria intera) · `build_traj_mex.m` (genera
`snn_traj_fixed_r{16,8}_mex`). ⚠️ **Il `fi` interpretato è ~10h su 6 traiettorie → per gli sweep usare il MEX.**

### Dati (`.mat`)
`champions_export.mat` (pesi + golden dei 4 champion — usato da ~20 script) · `test_dataset.mat` (60 traiettorie) ·
`test_trajectories.mat` (6) · `plant_golden.mat`.

### Generati (gitignored, ricreabili)
`codegen/` · `slprj/` · `*.mexw64` · `b2_rom_active.m`.

### Non gestiti da qui
`closed_loop_demo.slx` · `slblocks.m` — **file dell'utente, non toccare**.

## Riordino (VALUTATO e rimandato — 2026-07-18: si tiene flat + questa mappa)
Il riordino fisico in sottocartelle è stato **valutato e deciso NO** (per ora). Motivo, coi numeri: **65 file su
106** usano `fileparts(mfilename('fullpath'))` per caricare i dati (`test_dataset.mat`, `champions_export.mat`) e
raggiungere le sottocartelle (`axi/`, `hdlsrc_*`); un `mv` gli **romperebbe i path relativi**. Per spostarli in
sicurezza servirebbe un helper `mldir()` (matlab-root robusta) + un `startup.m` con `addpath(genpath)` — che
introduce una **fragilità**: se MATLAB parte da un'altra cartella senza quell'`addpath`, le funzioni spostate
spariscono dal path. Rapporto costo/valore sfavorevole → **struttura flat** (convenzione tipica MATLAB) + **questa
mappa** tenuta aggiornata. **Fatto** il 2026-07-18: pulizia del dead-code (6 probe di serializzazione B2, commit
`8d040dd8`) + aggiornamento di questa mappa. Se un domani il riordino fisico diventasse necessario, la struttura
target resta `core/ · b2/ · hdl/ · lib/ · acc_iidm/ · harness_rtl/ · test/ · ann/ · diag/ · data/`, da fare con
`mldir()` + non-regressione (rilanciare A-1/B-1/PLANT-PAR/B-LOOP + `run_b2_parity_dataset`).
Da fare come refactor a sé, non insieme ad altro.
