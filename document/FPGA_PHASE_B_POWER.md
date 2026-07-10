# FPGA Fase B — Power Analysis (Donatello B2, PYNQ-Z1 28nm)

> **Addendum drop-in** per `report/FPGA_REPORT.md`. Livello di fedeltà: **stima Vivado post-impl con
> switching reale (SAIF)** — NON silicio (Fase C, rinviata-predisposta). Provenienza per ogni numero.
> Spec: `docs/superpowers/specs/2026-07-10-fpga-phase-b-power-design.md`. Piano:
> `docs/superpowers/plans/2026-07-10-fpga-phase-b-power.md`. **DOC VIVO — aggiornato durante l'esecuzione.**

**Stato:** Gruppo A (potenza B2) ✅ · Gruppo B (e_AC/e_MAC) ✅ · Gruppo C (ANN + letteratura) ✅ · Gruppo D (consolidamento) ✅ — **FASE B CHIUSA** (Fase C su silicio rinviata-predisposta)

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
- **Sweep Fclk (dichiarato):** la lane B2 chiude a **~8.5 MHz** → **un solo punto operativo** (8 MHz), niente
  headroom verso l'alto. Verso il basso: E_dyn/inf ~costante (switching, ~clock-independent) ma E_**statica**/inf
  **cresce** (leakage × tempo-inferenza più lungo) → clockare più lenti *peggiora* l'energia totale. Quindi
  8 MHz è anche l'ottimo pratico per il B2. (micro/ANN, più semplici, a 100 MHz; e_op ~clock-independent.)
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

## 3. Gruppo C — Confronto SNN vs ANN densa ✅ (ancorato a letteratura)

### 3.1 ANN densa 4→32→32→5 misurata (l'equivalente denso del report, 1312 MAC)
`ann_mlp` time-mux (1 MAC/ciclo, 1 DSP, pesi ROM, attivazioni in RAM), OOC @8 MHz, SAIF High:

| | LUT | DSP | BRAM | P_dyn | cicli/inf | **E_dyn/inf** | E_tot/inf @8MHz |
|---|---|---|---|---|---|---|---|
| **ANN 1312-MAC** | 708 | 1 | 1.5 | 1 mW | 2627 (RAM read-latency ≈2×1312) | **328 nJ** | 34 µJ |
| **SNN B2** | 4223 | 38 | 1 | 9 mW | 341 | **383 nJ** | 4.8 µJ |

A parità di scala e clock, l'**energia di calcolo è COMPARABILE** (ANN leggermente meno). Il datapath SNN
(38 DSP + ALIF) brucia 9× più potenza/ciclo dell'ANN (1 DSP seriale), ma finisce in 8× meno cicli → pari.
*(E_tot @8MHz vede la SNN 7× meglio, ma solo perché finisce prima → meno static; clock-dependent.)*

### 3.2 Ma l'ANN da 1312 MAC NON fa il task (pesi random) → si àncora alla letteratura
Il confronto a 1312 MAC è capacità-parity zoppo: non sappiamo se 1312 MAC bastino per car-following.
Ordini di grandezza tipici di **NN car-following task-capable** (letteratura):

| Modello | Architettura | ~MAC/step | Fonte |
|---|---|---|---|
| PIDL-CF (MLP) | 3 hidden × 60 (sweep → 256/512 × 5 layer) | **~7.4k** (fino 100k+) | Mo et al., arXiv:2012.13376 |
| LSTM personalized driver | **100 hidden units** (1 layer LSTM) | **~40k** | Hatazawa et al. 2023, JAMDSM |
| Seq2seq Bi-GRU + attention | **128 units** bidirezionale | **~50-100k** | Lu et al. 2023, IEEE Access |

SNN Donatello: **~800 pesi po2** (equivalente denso = 1312 MAC). → una NN densa che *davvero* fa il task è
**~5× (MLP piccolo) fino a ~30-75× (LSTM/GRU ricorrenti, l'analogo equo della SNN ricorrente)** più grande.

### 3.3 Sintesi — il vantaggio è reale ma da COMPATTEZZA del modello, non da AC≪MAC
Poiché su FPGA `e_MAC ≈ e_AC` (Gruppo B) e per il time-mux `E ∝ MAC`, si scala la misura reale:
`E_ann(task-capable) ≈ E_ann(1312) × MAC_lett/1312`:

| ANN task-capable | MAC | E_dyn/inf (scalata) | **vantaggio SNN** (vs 383 nJ) |
|---|---|---|---|
| MLP piccolo | ~7.4k | ~1.9 µJ | **~5×** |
| LSTM-100 | ~40k | ~10 µJ | **~26×** |
| Bi-GRU-128 | ~100k | ~25 µJ | **~65×** |

**Conclusione:** vantaggio energetico SNN reale **~5-65×**, ma da **rete compatta** (~5-75× meno operazioni
per fare il task), NON dal costo-per-operazione (che su FPGA è ~uguale). **Il 5-15× del report è nel range
giusto per il motivo sbagliato**: doppio errore che quasi si compensa — compattezza reale (↑) × premessa
AC≪MAC falsa (↓).

### 3.4 Perché SCALIAMO invece di costruire la NN grande (decisione)
`E ∝ cicli ∝ MAC` è **misurato** (328 nJ / 2627 cicli; e_MAC≈e_AC), quindi scalare è grounded. Costruire un
LSTM/GRU 40-100k-MAC in HDL = sforzo grande + rischio iterazioni (gate/attivazioni/FSM/RAM/BRAM),
sproporzionato, e confermerebbe solo la linearità. **Caveat onesti:** (a) LSTM/GRU hanno op **non-MAC**
(gate, tanh/sigmoid) che aggiungono ~20-50% → lo scaling **sottostima** l'ANN → conservativo pro-SNN;
(b) il moltiplicatore *esatto* richiederebbe **addestrare** una NN densa alla stessa accuratezza (non fatto,
opzione estrema) — la letteratura lo **limita** a ~5-75×.

## 4. Termica ✅ (non-problema, confermato)
Da `report_power`: **Tj ≈ 26.3 °C** (SNN) / 26.2 °C (ANN) all'ambiente 25 °C → innalzamento **~1.3 °C**
(TJA 11.5 °C/W × ~114 mW). La sezione termica 🟡 del report è **confermata come non-problema**: a scala mW il
derating Tj/Fmax è irrilevante (lontanissimi dai 100 °C di preoccupazione). Nessuno sweep XPE necessario.

## 5. Tabella di validazione claim-by-claim (consolidata)

| Claim (Fase A) | Fase A | **Fase B (Vivado reale)** | Esito | **Fase C (silicio)** | Provenienza |
|---|---|---|---|---|---|
| **DSP = 0** | 0 | **38** (elettivi; 0-DSP realizzabile a 9910 LUT) | **CORRETTA** (sfumata) | — (B definitivo) | `util_b2_hier`/`nodsp` |
| BRAM <1% | <1 | 1 tile (0.71%) | confermata | — | `util_b2_flat` |
| LUT / FF | stima | 4223 LUT (7.9%) / 1584 FF | confermata | — | `util_b2_flat` |
| **Fmax 100-200 MHz** | assunto | **~8.5 MHz** lane (met @8) | **CORRETTA** | — | `timing_b2` |
| **e_AC / e_MAC** | 0.9 / 4.6 pJ (45nm) | **e_MAC ≈ e_AC** su FPGA (~10 pJ ordine) | **CORRETTA** (nodo+FPGA) | **TBD** (rail sensing) | `power_micro_*` |
| **Energia/inf** | ~0.4-1.2 nJ (op-count) | **383 nJ** dyn realizzata (static domina 92%) | **CORRETTA** | **TBD** (mW reali) | `power_b2_*` |
| **Vantaggio 5-15×** | da AC≪MAC | **~5-65× ma da COMPATTEZZA** modello, NON AC≪MAC | **RI-INQUADRATA** | **TBD** | `power_ann` + letteratura §3 |
| Termica (Tj) | stima | Tj ~26 °C (non-problema) | confermata | **TBD** (Tj su silicio) | `power_b2_*` |
| Correttezza param | — | bit-exact al riferimento (err=0), vedi §0 | confermata | — | HDL phase |

**Le 3 correzioni di sostanza** (DSP≠0, Fmax≪assunto, e_MAC≈e_AC) + **la ri-inquadratura del vantaggio**
(reale ma da compattezza-modello, non da costo-per-op) sono il valore della Fase B: un report che si
auto-corregge con dati veri è più credibile.

### 5.1 Mappa re-tag figure del report
| Figura/claim report | Da → A | Nota |
|---|---|---|
| `resource_occupancy` (DSP=0) | 🟡→🟢 | **CORRETTA**: 38 DSP elettivi (0-DSP realizzabile) |
| `energy_vs_ann`, `energy_breakdown` | 🟡→🟢 | **ri-inquadrata**: vantaggio da compattezza (~5-65×), non AC≪MAC |
| `decode_criticalpath`, `area_model`, `bram_dimensioning` | 🟡→🟢 | misurati |
| `derating_tj_fmax`, `thermal_budget` | 🟡→🟢 | Tj ~26°C (non-problema) |
| mW reali su silicio, leakage vs Tj HW | resta 🔴 | **Fase C** |

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

## 8. Riferimenti — dimensioni tipiche NN car-following (per §3, utili al report)

Modelli NN di car-following pubblicati e la loro **scala** (n. layer/neuroni → MAC/step), usati per ancorare
il fattore-compattezza del §3. La colonna MAC è stimata dall'architettura riportata.

| # | Riferimento | Architettura | Input → Output | ~MAC/step |
|---|---|---|---|---|
| [1] | **Mo, Shi, Di** — *A Physics-Informed Deep Learning Paradigm for Car-Following Models* (arXiv:2012.13376) | MLP (PUNN) hidden **(60,60,60)**, sweep neuroni {30,60,128,256,512} × layer {1..5} | spacing, Δv, v → accel | **~7.4k** (fino 100k+) |
| [2] | **Hatazawa, Hamada, Oikawa, Hirose** (2023) — *Personalized driver model … using LSTM*, J. Adv. Mech. Design Syst. Manuf. 17(2) | **LSTM 100 hidden units** (sweep 50-250) | Δv, gap, ln(gap) → accel | **~40k** |
| [3] | **Lu, Yi, Liang, Rui, Ran** (2023) — *Improved Seq2seq Deep Learning … CAV*, IEEE Access | **Bi-GRU 128 units** encoder + GRU decoder + attention | multi-preceding kinematics → v/accel | **~50-100k** |
| [4] | **Wang, Jiang, Li, Lin, Zheng, Wang** (2017) — *Capturing Car-Following Behaviors by Deep Learning*, IEEE T-ITS | deep NN, finestra temporale multi-step | v, Δv, Δx (storia) → accel | migliaia+ |
| [5] | **Kinoshita et al.** (2022) — *Data-driven Car-Following … Comparison of NN Structures*, Int. J. ITS Research | DNN/LSTM/1DCNN/2DCNN, ≥4 layer, molti input (10 front+3 rear+strada) | multi-veicolo + strada → accel | grande |

**Confronto:** SNN Donatello ≈ **800 pesi po2** (equivalente denso 1312 MAC). Le reti dense/ricorrenti
task-capable sopra sono **~5× (MLP piccolo [1]) … ~30-75× (LSTM/GRU ricorrenti [2][3], analogo equo della
SNN ricorrente)** più grandi in operazioni → base del vantaggio-compattezza (§3.3).

**URL:** [1] https://ar5iv.labs.arxiv.org/html/2012.13376 · [2] https://doi.org/10.1299/jamdsm.2023jamdsm0022 ·
[3] https://doi.org/10.1109/access.2023.3243620 · [4] https://doi.org/10.1109/tits.2017.2706963 ·
[5] https://link.springer.com/article/10.1007/s13177-022-00339-9 · CNN-LSTM (MDPI Sensors 23(2):660)
https://www.mdpi.com/1424-8220/23/2/660

## 9. Appendice — Protocollo Fase C (predisposto, non eseguito)

Fase C = misura di potenza reale su **PYNQ-Z1 fisica** (unica ground-truth silicio). Tutti gli artefatti sono
pronti; resta solo la misura fisica.

**Artefatti pronti:**
- Bitstream flashabile `matlab/axi/build/snn_b2_donatello.bit` (+ `.hwh` per `pynq.Overlay`).
- Stimolo realistico `matlab/axi/phase_b/stim_typical.mem` (traiettoria reale normalizzata Q5.13).
- Driver `matlab/axi/run_on_pynq.py` (write xn → start → poll done → read params).

**Protocollo (delta idle-vs-inferenza):**
1. **Sensing.** La corrente PL della PYNQ-Z1 non è esposta on-board con precisione → **INA219/shunt esterno** sul
   rail **VCCINT (1.0 V)** della logica PL, campionamento ≥1 kHz (o sensore board via PMBus se disponibile).
2. **Baseline (idle):** overlay caricato, nessuna inferenza → `P_idle = Vccint·Iccint` medio su ~10 s (static +
   clock-tree fermo).
3. **Attivo:** loop stretto di inferenze (stream `stim_typical.mem` → start → poll done) ~10 s → `P_active` medio.
4. **P_dyn reale = P_active − P_idle** → confronta con la stima Vivado SAIF (§1.4, ~9 mW); il gap = ciò che Vivado
   non cattura (glitch, routing, PMU).
5. **E/inf reale = P_dyn·cicli/Fclk** (341/8 MHz = 42.6 µs) → riempi la colonna **"Fase C"** della tabella §5.
6. *(Opz.)* ripeti con overlay ANN per il rapporto SNN/ANN su silicio.

**Attese:** `P_idle` domina (static ~103 mW + PS); il delta dinamico è ~mW → serve un sensore risoluto (INA219 al
limite a 1.0 V; meglio shunt dedicato + amplificatore). **Onestà:** la board conferma/corregge solo i numeri di
*potenza*; le conclusioni strutturali (DSP, Fmax, compattezza) sono già definitive dalla Fase B.
