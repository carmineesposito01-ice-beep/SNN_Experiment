# FPGA Fase B — Power Analysis (Donatello B2, PYNQ-Z1 28nm)

> **Addendum drop-in** per `report/FPGA_REPORT.md`. Livello di fedeltà: **stima Vivado post-impl con
> switching reale (SAIF)** — NON silicio (Fase C, rinviata-predisposta). Provenienza per ogni numero.
> Spec: `docs/superpowers/specs/2026-07-10-fpga-phase-b-power-design.md`. Piano:
> `docs/superpowers/plans/2026-07-10-fpga-phase-b-power.md`. **DOC VIVO — aggiornato durante l'esecuzione.**

**Stato:** Gruppo A (potenza sistema B2) ✅ · Gruppo B (costanti e_AC/e_MAC) ⏳ · Gruppo C (ANN) ⏳ · Gruppo D (deliverable) ⏳

---

## 0. Correttezza funzionale — l'FPGA genera bene i parametri?

**Sì, ed è dimostrato a livello bit.** (Stabilito nella fase HDL; qui reso esplicito per tracciabilità.)

| Livello | Evidenza | Errore |
|---|---|---|
| RTL vs core fixed-point | `test_b2_fsm` (parità cyclo-accurata) | **err = 0 (bit-exact)** |
| IP (AXI) vs `snn_top_b2` | cosim `axi_tb.v` → `AXI TEST PASSED` | bit-exact (v0=26.49, T=1.63, s0=2.45, a=1.01, b=1.71) |
| core fixed vs core double | `run_fixed_sweep` | ≤ 0.028 su v0 |
| core double vs **PyTorch originale** | `run_parity_tests` vs `forward_sequence` | **~2e-6** |
| decode σ-LUT vs float | `test_decode` | 0.002 |

Poiché **RTL == core fixed esattamente**, l'errore FPGA-vs-rete-originale *è* la catena
fixed↔double↔PyTorch sopra (dominata da ≤0.028 su v0). L'FPGA riproduce la generazione dei parametri
della rete originale entro l'errore di quantizzazione noto. *(Figura fresca end-to-end sul netlist:
opzionale, ri-conferma questi numeri — vedi §7.)*

---

## 1. Gruppo A — Potenza di sistema del B2 ✅

**Setup:** `snn_top_b2_flat` (SNN+decode) sintetizzato **OOC** (out-of-context, no I/O buffer → esclude
l'anello di I/O = potenza della sola logica) su `xc7z020clg400-1`, **@8 MHz** (Fclk reale, lane ~8.5 MHz).
Potenza via **SAIF** da sim funcsim gate-level su stimolo reale (16 inferenze di traiettoria test),
confidenza **HIGH**. Provenienza: `matlab/axi/build/phase_b/{util_b2_*,timing_b2,power_b2_*}.rpt`.

### 1.1 Risorse (OOC, reali)
| | valore | % Zynq-7020 |
|---|---|---|
| LUT as Logic | 4223 | 7.94% |
| Slice Registers (FF) | 1584 | 1.49% |
| Block RAM Tile | 1 | 0.71% |
| **DSP** | **38** | 17.27% |

### 1.2 Claim "DSP = 0" → CORRETTA (sfumata)
La sintesi naturale usa **38 DSP**, MA il test decisivo `-max_dsp 0` sintetizza a **0 DSP / 9910 LUT
(18.6%)** — il design *sta* senza DSP. L'attribuzione via nomi-cell mostra che i 38 DSP sono
**adder/accumulatori larghi** (`V_sub`, `fat_add` del core; `add_cast` del readout) + solo ~3
moltiplicazioni del decode — **nessun moltiplicatore sinaptico** (le sinapsi po2→shift *davvero* non
usano DSP). Verdetto: la premessa "0 DSP sinapsi" del report è **realizzabile**; i 38 DSP sono una scelta
*elettiva* di Vivado per dimezzare le LUT (4223 vs 9910). Provenienza: `util_b2_nodsp.rpt`.

### 1.3 Timing
`All user specified timing constraints are met` @ 8 MHz (period 125 ns). Conferma il margine WCET del
report (control-step 0.1 s ≫ 341 cicli × 125 ns = 42.6 µs/inf).

### 1.4 Potenza (SAIF, confidenza HIGH)
| stimolo | Total | Dynamic | Device Static |
|---|---|---|---|
| typical | 112 mW | **9 mW** | 103 mW |
| worst | 111 mW | **8 mW** | 103 mW |

Breakdown dinamico (typical): Slice Logic 3 mW · Signals 3 mW · DSP 2 mW · Clocks/BRAM <1 mW.

**Findings:**
- **Static domina al 92%** (103 mW = leakage del chip, comune a qualsiasi design sul 7020). Il dinamico
  della rete è appena 8-9 mW.
- **Energia realizzata ≫ algoritmica**: E_dyn/inf = 9 mW × 42.6 µs ≈ **384 nJ** (tot ~4.8 µJ), vs i
  **~0.72 nJ** dell'op-count del report (~530× sul dinamico). Il time-mux (341 cicli) + la leakage
  stravolgono l'energia rispetto alla stima algoritmica: l'efficienza del report è una proprietà
  *algoritmica* che l'implementazione time-mux **non esibisce a livello di sistema**.
- **Quasi data-independent** (worst 8 ≈ typical 9 mW): il time-mux fa lo stesso lavoro a prescindere
  dall'input → proprietà di determinismo (coerente col WCET=BCET del report).
- **Per il confronto SNN-vs-ANN (Gruppo C):** vivrà nella *fetta dinamica* (lo static è comune a
  entrambi); la ANN con 1312 MAC su DSP48 avrà un dinamico diverso.

---

## 2. Gruppo B — Costanti node-correct e_AC / e_MAC ✅ (con caveat di risoluzione)

Micro-datapath isolati **OOC** (niente I/O pad): `micro_ac` (shift-add po2 = "sinapsi" SNN) e `micro_mac`
(MAC data×data = "sinapsi" ANN), 1 op/ciclo @100 MHz, operandi da LFSR interno. Potenza via SAIF (High).

| | LUT | DSP | P_dyn | breakdown chiave |
|---|---|---|---|---|
| micro_ac | 83 | **0** | 3 mW | Slice Logic ~1 mW |
| micro_mac | 97 | **1** | 4 mW | DSP48 ~1 mW |

**Sanity confermata:** shift-add po2 → 0 DSP (LUT); MAC → 1 DSP48.

**⚠️ Caveat di risoluzione (onestà):** a 1 op/ciclo il P_dyn è dominato da clock-tree + registri
(LFSR+accumulatore) ed è al **floor mW** di `report_power` → l'e_op grezzo (P_dyn/Fclk ≈ 30-40 pJ)
sovrastima la singola operazione. Il tentativo N=64-parallelo per salire sopra il floor è fallito
(synthesis collassa i MAC correlati a 8 DSP + SAIF del netlist grande impraticabilmente lento). I valori
per-op restano quindi **order-of-magnitude**.

**Finding (robusto qualitativamente) — la seconda correzione al report:** dal breakdown, **DSP48 ~1 mW ≈
Slice-Logic ~1 mW → e_MAC ≈ e_AC su FPGA** (ordine ~10 pJ), contro il **5.1× di Horowitz (45nm ASIC)**.
Sul silicio FPGA il MAC su **DSP48 hard-block** è efficiente quanto lo shift-add po2 su LUT (entrambi
dominati dall'overhead di fabric: registri/routing, non l'aritmetica ASIC pura). → **il vantaggio
energetico per-operazione del report — che nasce da e_AC ≪ e_MAC — largamente SVANISCE su FPGA**
(ratio vera ≈ 1, non 5). Nota che i totali confermano la direzione: micro_mac 4 mW vs micro_ac 3 mW
(≈1.3×, non 5×).

**Implicazione:** unito al Gruppo A (static-dominated, energia realizzata ≫ algoritmica), il vantaggio
SNN-vs-ANN su FPGA è **molto minore** del ~5-15× del report. Il confronto robusto (sistema-vs-sistema,
insensibile alla precisione per-op) è il Gruppo C.

## 3. Gruppo C — Baseline ANN densa ⏳
*(in corso)*

## 4. Termica ⏳
*(dalla potenza reale: Tj all'ambiente — verosimilmente non-problema a mW)*

## 5. Tabella di validazione claim-by-claim
*(consolidata a fine Gruppi B/C/D)*

## 6. Onestà
Tutti i numeri sono **stime Vivado** con switching reale (confidenza HIGH nei `.rpt`), non misure su
silicio. Ground-truth finale = **Fase C** (misura su PYNQ-Z1 fisica, rinviata-predisposta): la tabella
avrà una colonna "Fase C misurato" (TBD) e un'appendice-protocollo.

## 7. Note
- Figura d'accuratezza fresca (netlist su tutte le traiettorie vs rete originale): opzionale, ri-conferma §0.
- Intoppi d'esecuzione risolti (tracciabilità): sintesi **OOC** obbligatoria (187 porte > 125 pin) in
  **flusso non-project** (`synth_design -mode out_of_context`); `xelab -debug typical` per il SAIF; sim
  gate-level lenta → 16 inferenze; correzioni al piano (firma `snn_normalize`, porte `done`/`clk_enable`,
  packing `xn`).
