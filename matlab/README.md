# `matlab/` — mappa della cartella

> **Perché questo file**: nella root ci sono ~63 `.m` di **8 scopi diversi**. Questa è la mappa per orientarsi senza
> aprirli a caso. *(Il riordino in sottocartelle è un refactor pianificato a parte: 21 file caricano i `.mat` con
> `fullfile(here,…)` e si romperebbero con un semplice `mv` — vedi §Riordino.)*
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
`acc_iidm_open.m` (**unica fonte** della matematica ACC-IIDM: `accel = f(stato, params)`, non integra; la usano
il blocco SP2 e il plant `cf_plant_lib/ACC_IIDM`) · `champ_weights.m` (helper pesi).

### B2 — architettura deployata
`snn_b2_fsm.m` (FSM time-mux, `hdl.RAM`, serializzazione **bit-exact** di `snn_core`) · `snn_top_b2.m` (top del
bitstream: `xn`+`start` → `params`+`done`) · `snn_neuron_b2.m` · `gen_b2_rom.m` (genera `b2_rom_active.m` = pesi baked
del champion attivo; **il file generato è gitignored**).

### Parallela — SUPERATA (tenuta per storia/confronto)
`snn_hdl_Donatello|Leonardo|Michelangelo|Raffaello.m` · `gen_hdl_tops.m` · `make_hdl.m`.

### Generazione HDL
`make_hdl_top_b2.m` (**il top deployato**) · `make_hdl_b2.m` · `make_hdl_b2fsm.m` · `make_hdl_decode.m` (decode
deployato) · `make_hdl_decode_lut.m` (decode LUT-N, sweep) · `make_hdl_ann.m` · `make_hdl_micro.m` ·
`make_hdl_probe|probe2|ram_probe.m` (esperimenti) · `check_hdl.m`.

### Librerie Simulink (builder + `.slx`)
`build_library.m` → **`snn_champions_lib.slx`**: 4 blocchi champion **comportamentali** (double, self-contained,
1 chiamata = 1 inferenza — **non** sintetizzabili: double+`exp`) ·
`build_hdl_variants.m` → aggiunge alla stessa libreria i 7 blocchi **HDL-ready SELF-CONTAINED**
(`Donatello_Champion` + `Donatello_LUT{16..512}`) ·
`build_plant_lib.m` → `cf_plant_lib.slx` (ACC-IIDM) · `build_closed_loop_demo.m`.

Lo stesso builder aggiunge anche **`Donatello_ACC_IIDM`** (SP2): campione LUT-64 + ACC-IIDM **open-loop**,
`s,v,dv,v_l → accel`, per testare la rete dentro un modello di car-following. ⚠️ **Sola simulazione: NON
sintetizzabile** (mescola fixed e double) — l'artefatto HDL-ready resta `Donatello_Champion`.
Doc: `../document/SP2_ACC_IIDM.md`. Cancello: `run_block_acciidm_test.m`.

La matematica ACC-IIDM ha **una sola fonte**, `acc_iidm_open.m`: la usano sia il blocco SP2 sia il plant
closed-loop `cf_plant_lib/ACC_IIDM` (che aggiunge solo l'integrazione). Idem `local_normalize`
(`build_hdl_variants:normalize_code`), condivisa fra i blocchi HDL-ready e quello SP2.

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
`test_b2_fsm.m` · `test_top_b2.m` · `test_decode.m` · `test_ann_mlp.m` · `tb_b2_fsm.m` · `tb_hdl_Donatello.m`.

### Confronto ANN (Fase B)
`ann_mlp.m` · `ann_rom.m` · `gen_ann_rom.m` · `test_ann_mlp.m` · `make_hdl_ann.m`.

### Micro-benchmark energia (Fase B)
`micro_ac.m` · `micro_mac.m` · `make_hdl_micro.m`.

### Diagnostica / probe
`diag_quant.m` · `diag_ranges.m` · `snn_ram_probe.m` · `snn_tick_probe.m` · `snn_tick_probe2.m`.

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

## Riordino (pianificato, non ancora fatto)
Struttura target: `core/` · `b2/` · `hdl/` · `lib/` · `test/` · `ann/` · `micro/` · `diag/` · `data/`.
**Vincolo**: 36 file usano `fileparts(mfilename('fullpath'))` e **21 caricano i `.mat` via `fullfile(here,…)`** → lo
spostamento richiede di riscrivere quei path e **ri-verificare con `run_parity_tests` + `run_b2_parity`** (cancelli).
Da fare come refactor a sé, non insieme ad altro.
