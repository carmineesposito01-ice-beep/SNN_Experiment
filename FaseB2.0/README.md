# Fase B2.0 — validazione RTL + caratterizzazione esaustiva (pre-FPGA fisica)

Ultima fase prima della **Fase C** (FPGA fisica). Obiettivo: dimostrare che il **VHDL/Verilog generato**
(non il blocco Simulink) riproduce il blocco **bit-exact** in un simulatore HDL (Vivado **xsim**), e produrne
una **caratterizzazione completa** (funzionamento della rete e di rete+car-following) al livello dei report
in `../report/`.

> **Stato (2026-07-30):** T1–T4 · **T5** (deriva open-loop → [`common/DRIFT.md`](common/DRIFT.md)) · **T6a**
> (validazione RTL della SNN → [`Harness_SNN/results/RESULTS.md`](Harness_SNN/results/RESULTS.md)) · ✅ **T6b
> COMPLETO M1–M5** (caratterizzazione HW → [`Harness_SNN/results/RESULTS_HW.md`](Harness_SNN/results/RESULTS_HW.md))
> — tutti FATTI e committati. **Prossimo: T7** — `Harness_SNN_IIDM` (capitolato in
> [`Harness_SNN_IIDM/README.md`](Harness_SNN_IIDM/README.md)): blocco composto + i **99** scenari + metriche di
> car-following in anello chiuso. Poi **T8** (2 report `create-report`) e **T9** (allineamento doc).
> **▶ Riesecuzione HW:** `bash Harness_SNN/hw/run_harness_snn_hw.sh [stadio]` (`summary` = numeri in pochi secondi).
> Stato/azioni: `../document/SESSION_RESUME.md`.

### Sintesi dei numeri HW (T6b, dettaglio e provenienza in `Harness_SNN/results/RESULTS_HW.md`)
| Grandezza | Valore | Natura |
|---|---|---|
| Params letti dal **PS via AXI** == blocco | **0 / 300 000** (60 traj), gating ON e OFF | misurato |
| Netlist **post-place&route** == blocco | **0 / 15 000** (3 traj, funcsim) | misurato |
| **FCLK deployabile** / limite datapath | **52 MHz** (WNS +0,358) / **58,6 MHz** | misurato |
| Risorse post-route @52 MHz | 4473 LUT · 3199 FF · 52 DSP · **1 BRAM** | misurato |
| Latenza / margine sul control-step 0,1 s | 7,13 µs / **≈14 000×** (duty 0,0071 %) | derivato |
| **Energia dinamica per control-step** (duty **reale**) | **0,9 mJ** (0,009 W; 78 % clock tree) | misurato |
| Statica del device (pavimento del chip, **separata**) | 0,103 W → 10,3 mJ | misurato |
| **Clock gating**: clock del Tier fermo (`TC 400→0`), funzionalmente trasparente | attivo | misurato |
| Guadagno del gating in watt | **2–4×** atteso sulla dinamica | ⚠️ **stima** → Fase C |
| **Bitstream PYNQ-Z1** @52 MHz (`.bit`/`.hwh`/`.xsa`) | WNS +0,358 = quello dello sweep | prodotto |
| Worst-case sintetico come bound | ❌ invalidato (era il più basso) → si usa il **max osservato** 0,045 W | — |

## Requisiti di metodo (vincolanti — appresi in T6a, 2026-07-29)
1. **Riproducibilità:** ogni harness è **rilanciabile da chiunque con UN comando** e salva i numeri in **artefatti su
   disco** (`results/RESULTS.md` + `.mat`), insieme alla **configurazione misurata**. I report citano l'artefatto,
   non la console. *(T6a: `run_harness_snn`.)*
2. **Stesso perimetro per prova e metriche:** se le metriche sono su N traiettorie, la prova RTL è sulle **stesse** N.
   Un subset vale solo come **gate rapido di sviluppo**, mai come base dei numeri riportati (popolazioni diverse ⇒
   numeri non appaiabili ⇒ lo scostamento non è leggibile, nemmeno se è 0). → **golden calcolato una volta** e
   consumato sia dal confronto RTL sia dalle metriche.
3. **Niente ripieghi in corsa** per risparmiare tempo: un job corretto ma lungo si lancia in background e si lascia finire.
4. **Probe-first:** prima di scrivere il piano d'implementazione, verificare con **probe mirati** le assunzioni
   riusate da casi precedenti (in T6a i pattern di M1/Champion non valevano per il Tier → 4 fix in corsa).

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

## Copertura
- **T6a (SNN, FATTO)** — RTL in xsim **su tutte le 60** traiettorie (`T6-EXACT 0/300000`), **metriche sulle stesse
  60**: prova e numeri riportati hanno lo **stesso perimetro** (requisito 2). Costo reale ~75 min, non giorni:
  golden calcolato una volta (~7 min) + una simulazione xsim per traiettoria (~1 min ciascuna).
  ⚠️ *La stima iniziale «RTL solo su ~9 traiettorie, il resto per transitività» è stata superata: era proprio il
  ripiego che rende i numeri non appaiabili.*
- **T7 (SNN+IIDM, da fare)** — closed-loop sui **99 scenari** (`test_dataset_exhaustive.mat`, cut-in aggressivi):
  car-following e sicurezza. Stesso requisito: la prova RTL copra il perimetro dei numeri riportati.
- **Bitstream**: blocco *as-is* (normalize FIXED su FPGA, I/O fisico), uno per harness.

## Struttura
> ⚠️ Stato reale (2026-07-30): `common/` popolata da T5 (deriva) + T6a (utilità RTL condivise); **`Harness_SNN/`
> completa e funzionante** (T6a RTL + **T6b `hw/` hardware**, con `results/RESULTS.md`, `results/RESULTS_HW.md` e
> `bitstream/`); `Harness_SNN_IIDM/` contiene **il capitolato di T7** (`README.md`), nessun codice. I golden e il
> generatore HDL vivono in `../matlab/` (riusati, non copiati).
```
FaseB2.0/
├── common/            → materiale condiviso.
│                        ORA: DRIFT.md + drift_chosen.{m,mat} (deriva T5). I golden fedeli
│                        (acciidm_m_traj, snn_traj_b2, …) vivono in ../matlab/ (riusati, non copiati).
│                        DA POPOLARE (T6/T7): utilità RTL condivise (gen VHDL/Verilog, export vettori, run xsim, metriche).
├── Harness_SNN/       → COMPLETA.
│   │                    T6a (RTL): run_harness_snn (entry-point) + run_rtl_validate_tier + sensitivity_t6 +
│   │                    tier_rtl_metrics + tier_export_vectors + subset_diverse + tb_tier_stream.v
│   ├── hw/            → T6b (HARDWARE): run_harness_snn_hw.sh (ENTRY-POINT a stadi) + tier_axi_lite.v +
│   │                    tb_tier_axi/tb_power_idle/tb_power_duty + probe_*/bitstream/netlist_*/power_* tcl
│   ├── results/       → RESULTS.md (T6a) · RESULTS_HW.md (T6b) · PROBES_T6B.md · log
│   └── bitstream/     → snn_tier_donatello.{bit,hwh,xsa} @52 MHz + timing/utilizzo del run del bitstream
└── Harness_SNN_IIDM/  → SOLO CAPITOLATO (README.md = requisiti T7: composto + 99 + metriche car-following).
                         Nessun codice: da implementare in T7.
```
Ogni harness **avrà** il suo README con i comandi di esecuzione e la mappa dei prodotti (creato in T6/T7).

## Ambiente
- MATLAB: `"C:\Program Files\MATLAB\R2026a\bin\matlab.exe" -batch` — gli script fanno `addpath('../../matlab')` per
  raggiungere libreria e sorgenti.
- Vivado: `C:\AMDDesignTools\2026.1\Vivado\bin\vivado.bat`. **xsim/synth da work-dir SENZA spazi** (le tcl usano `glob`).
- I due report finali vanno in `../report/` (come gli altri della root).
