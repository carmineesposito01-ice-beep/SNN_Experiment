# HDL_ARCHITECTURE_STUDY.md — Studio d'architettura FPGA e decisione sullo "streaming ÷32"

> **Data:** 2026-07-10 · **Worktree/branch:** `Simulink_Importer` · **Target:** PYNQ-Z1 (Zynq-7020 `xc7z020clg400-1`)
> **Esito:** rearchitecting d'area (streaming ÷32) **investigato e NON perseguito**. Donatello resta al baseline
> verificato (44% LUT). Contesto operativo in `HDL_PHASE.md`; questo doc è il **record del PERCHÉ**.

## 0. TL;DR
Donatello ci sta e funziona sul 7020 (anelli ③④ verificati, cosim PASSED). Il 44% di LUT infastidiva per una
promessa **estetica** di "rete piccola". Analisi su numeri **misurati**: (a) sull'energia l'area non conta su
device fisso (static domina, 82%); (b) nessun requisito impone meno area (V2I piccolo, stakeholder soddisfatti);
(c) il 44% è il **costo della resa 0-DSP**, non la dimensione del modello (<1k param, ~1.8 kbit stato). Il
rearchitecting per abbassare le LUT è **puro lavoro MATLAB/HDL, senza retraining**, ma sostanziale e con esito
HDL incerto, per un guadagno solo estetico → **non perseguito** (YAGNI). Disponibile come progetto futuro se il
target cambia.

## 1. Numeri misurati (2026-07-10, Vivado 2026.1)
### ④ Area — OOC synth + place&route, `xc7z020clg400-1`, routed
- LUT **23.186 = 44%** · slice **7.092 = 53%** · FF 3.386 = 3% · DSP **32 = 15%** · **BRAM 0 / 140** · CARRY8 4.571
- Fmax **~5 MHz** (path 200 ns) → control-step 0.1 s ⇒ **margine timing ~50.000×**
- Il 44% è dominato da **mux di resource-sharing 32:1** + accumulatori larghi (`accw` Q8.17), NON dai moltiplicatori.
### ③ Cosim — xsim
- TB auto vs `raw_expected.dat` → `TEST COMPLETED (PASSED)`; RTL **bit-esatto vs golden** (0 mismatch, 16 campioni × 5 out).
### Potenza — `report_power` sul routed DCP
- Totale **0.125 W** = **static 0.103 W (82%, fisso col device)** + dynamic 0.022 W @3.33 MHz (scala col clock → trascurabile a ~kHz reali).

## 2. Il tentativo streaming ÷32 (cosa provato, perché è fallito)
Piano §8.2: `x_buf` circular-buffer + `RAMThreshold` basso + `coder.hdl.loopspec('stream')` sul loop neuroni.
Risultato data-backed (parità SEMPRE bit-identica → il refactor era *corretto*, ma):
- `coder.hdl.loopspec('stream')` è **top-level-only**: il loop neuroni è **annidato** nel loop tick → HDL Coder lo ignora.
- **RAM-mapping fallisce**: `V`/`fatigue`/`x_buf`/`s` → *"accessed in a loop region"* (annidamento) + *"non-scalar
  sub-matrix access"* (init `zeros`, `s_prev=s`, `V_LI(:)`) → lo stato resta nei **registri**.
- `head` come indice runtime `double` → `RealsUnsupported` (risolto con `int8`, ma non sblocca il resto).
- Esito: clock ancora **10×** (non 320×), stima adder/mux **peggiorata** (6.387/12.181) ⇒ serializzazione **non avvenuta**. Reverted.

**Causa reale:** HDL Coder non auto-serializza questa struttura annidata; le leve globali che funzionavano
(`StreamLoops` + `ResourceSharing=32`) sono **già** quelle del baseline 44%.

## 3. L'asse di ottimizzazione (il punto chiave)
Il `po2→shift` "0-DSP" ha **speso la risorsa contesa (LUT) per risparmiare quelle libere** (DSP 85% idle, BRAM
100% idle). I due obiettivi estetici **si escludono** su questo chip:

| | Asse A (attuale) | Asse B |
|---|---|---|
| minimizza | **DSP** | **LUT** |
| pesi | shift baked in LUT | in **BRAM** |
| datapath | 32:1 sharing (mux LUT) | MAC serializzato (DSP+BRAM) |
| esito | 0-DSP, LUT-heavy (44%) | LUT-light, memory-based |

`0-DSP` **è la causa** delle LUT alte. Non si possono avere entrambi senza il rearchitecting.

## 4. Energia (perché l'area non aiuta qui)
Static (0.103 W) domina ed è **fisso col device** (leakage del 7020, indipendente dall'utilizzo LUT). Dynamic già
trascurabile e scala col clock (50.000× margine → clock bassissimo + gating). ⇒ ridurre LUT sul 7020 ≈ **0
risparmio energia**. L'unica leva reale è **un device più piccolo/basso-leakage** — rilevante solo se l'area
scende abbastanza da cambiare chip (NON il caso: PYNQ-Z1 fisso).

## 5. Cosa sarebbe il rearchitecting (per completezza)
**NIENTE retraining.** Il champion (pesi PyTorch, frozen in `champions_export.mat`) è **intoccato**: stessa
matematica, stesso comportamento **bit-esatto** (gated dalla stessa parità double ~2e-6). È **solo lavoro
MATLAB/HDL** sulla *resa*. Consiste in: riscrivere `snn_core` in forma **esplicitamente time-multiplexata** (1
lane-neurone/clock) con stato (e opz. pesi) in **RAM** via `hdl.RAM` System object + FSM di controllo, sostituendo
i mux 32:1 con indirizzamento RAM. Due varianti:
- **B1** (tiene 0-DSP): serializza il loop neuroni con stato in RAM; pesi ancora shift baked.
- **B2** (memory-based pieno): pesi in BRAM + MAC serializzato (pochi DSP); allineato all'istinto "pesi in BRAM" + low-rank recurrence.

**Effort/rischio:** MATLAB sostanziale; il rischio non è la correttezza (la parità la protegge) ma **convincere
HDL Coder** a produrre l'RTL RAM-mapped/serializzato voluto (inferenza capricciosa → probabile `hdl.RAM`
esplicito). Payoff: 44% → ~10-20% LUT, **solo estetico**. Modello e validazione **non toccati**.

## 6. Decisione
**Streaming ÷32 / rearchitecting d'area: NON perseguito** (2026-07-10). Motivi: (1) tutti i requisiti soddisfatti
su PYNQ-Z1; (2) V2I piccolo (condizionamento min/max sui parametri), stakeholder soddisfatti; (3) energia non
aiutata dall'area su device fisso; (4) "rete piccola" già vera a livello di modello; (5) rischio > guadagno
(estetico). **Riapribile** come progetto scoped (Asse B) se il target cambia (chip più piccolo / V2I grande /
consolidamento su 1 chip). **Prossimo lavoro reale:** decode→LUT, wrapper AXI-Lite + bitstream, integrazione V2I.
