# Fase B2.0 — validazione RTL + caratterizzazione esaustiva (pre-FPGA fisica)

Ultima fase prima della **Fase C** (FPGA fisica). Obiettivo: dimostrare che il **VHDL/Verilog generato**
(non il blocco Simulink) riproduce il blocco **bit-exact** in un simulatore HDL (Vivado **xsim**), e produrne
una **caratterizzazione completa** (funzionamento della rete e di rete+car-following) al livello dei report
in `../report/`.

> **Stato (2026-07-28):** T1–T4 (riordino `matlab/`, struttura `FaseB2.0/`, deprecazione `ACC_IIDM_M`, blocco
> composto `Donatello_SNN_IIDM`) + **T5 (deriva open-loop → [`common/DRIFT.md`](common/DRIFT.md))** FATTI e committati.
> ⏸ **Fermi prima del blocco harness (T6–T9)** su richiesta utente. Stato/prossime azioni: `../document/SESSION_RESUME.md`.

## I due banchi (blocchi SCELTI — per non confondersi)
| Harness | DUT | Cos'è |
|---|---|---|
| **Harness_SNN** | `Donatello_Tier` @ **BALANCED** / nfrac 13 | la SNN estimatrice scelta: `s,v,dv,v_l → v0,T,s0,a,b` |
| **Harness_SNN_IIDM** | **`Donatello_SNN_IIDM`** = Tier@BAL **+** `ACC-IIDM` (composti) | il controllore completo: `s,v,dv,v_l → accel` |

Il blocco composto `Donatello_SNN_IIDM` unisce la SNN (Tier@BAL) e il **controllore IIDM standalone R17**
(`ACC-IIDM`) con un **allineamento a ritardo-appaiato**: i 4 ingressi fisici vengono ritardati della latenza
nota della SNN (~406 clk) così che i 9 ingressi dell'ACC-IIDM cambino **sincroni** → 1 inferenza/control-step
(il filtro OU aggiorna una volta). Sostituisce il vecchio `Donatello_ACC_IIDM_M`, **DEPRECATO**.

## Dataset (due ruoli distinti)
- **Copertura car-following full-99 (T6/T7)** — `../matlab/Quantizzation_Study/test_dataset_exhaustive.mat`:
  99 **definizioni di scenario** / 9 famiglie (con cut-in/cut-out), riferimento closed-loop `mp_ref13_1_99.mat`.
  Sono definizioni (`v_leader, s_init, v_init, cut_in, gt_params`), **non** traiettorie `val` → **closed-loop-native**.
- **Deriva open-loop (T5, FATTA)** — `../matlab/test_dataset.mat` (60 traiettorie **con `val`**): l'open-loop
  confronta accel-blocco vs accel-ideale su `val` registrati, quindi serve un dataset con `val` (l'esaustivo non ne ha).
  Risultato in [`common/DRIFT.md`](common/DRIFT.md).

## Copertura (RTL mirato, funzionale esaustivo)
- **RTL (xsim)**: bit-exact su un **sottoinsieme rappresentativo** (~9 traiettorie, 1 per scenario) — xsim sul
  full-99 sarebbe giorni.
- **Funzionale (MEX)**: accuratezza, deriva, car-following, sicurezza sul **full-99** — bit-identico all'RTL
  già provato sul sottoinsieme, quindi la caratterizzazione è esaustiva sui dati.
- **Bitstream**: blocco *as-is* (normalize FIXED su FPGA, I/O fisico), uno per harness.

## Struttura
```
FaseB2.0/
├── common/            → utilità condivise: gen RTL (VHDL/Verilog), export vettori, run xsim, metriche, golden fedeli, deriva
├── Harness_SNN/       → run + tb + synth(tcl) · results/ · figures/ · bitstream/
└── Harness_SNN_IIDM/  → run + tb + synth(tcl) · results/ · figures/ · bitstream/
```
Ogni harness ha il suo README con i comandi di esecuzione e la mappa dei prodotti.

## Ambiente
- MATLAB: `"C:\Program Files\MATLAB\R2026a\bin\matlab.exe" -batch` — gli script fanno `addpath('../../matlab')` per
  raggiungere libreria e sorgenti.
- Vivado: `C:\AMDDesignTools\2026.1\Vivado\bin\vivado.bat`. **xsim/synth da work-dir SENZA spazi** (le tcl usano `glob`).
- I due report finali vanno in `../report/` (come gli altri della root).
