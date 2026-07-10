# FPGA Fase B — Power Analysis & Validazione del report FPGA (design)

> **Data:** 2026-07-10 · **Branch:** `Simulink_Importer` · **Stato:** design **LOCKED** (approvato)
> · **Target:** Donatello (EventProp `PE_t05_gp0002`) su PYNQ-Z1 (Zynq-7020 `xc7z020clg400-1`, **28nm**)
>
> Complemento operativo di `document/FPGA_EVALUATE_DESIGN.md` (che definisce Fase A/B/C) e di
> `document/FPGA_EVALUATION_FRAMEWORK.md` (catalogo metriche, righe HDL 166/230/231/232/249).
> La **Fase A** (`software_now`, ~80% del catalogo) è chiusa: deliverable `report/FPGA_REPORT.md`.
> Questo documento progetta la **Fase B** (`needs_hdl_synthesis`), sbloccata ora che il track
> Simulink_Importer ha prodotto RTL/sintesi/bitstream reali (il nodo Simulink→HDL Coder di §1
> di FPGA_EVALUATE_DESIGN era l'unico motivo del rinvio).

---

## 0. Decisioni di scope (dal brainstorming)

| Decisione | Scelta |
|---|---|
| **Ambizione** | **Chiusura Fase B piena**: potenza reale IP + costanti node-correct 28nm + baseline ANN vera + termica + attribuzione risorse, come addendum formale al report con re-tag figure 🟡→🟢. |
| **Champion** | **Solo Donatello** a livello di sistema (candidato deploy); gli altri 3 validati a livello di **formula** con le costanti node-correct × le loro SynOps già note (Fase A). |
| **Fase C (board)** | **Fuori scope ma predisposta**: ci si ferma alle stime Vivado; artefatti + protocollo lasciati pronti perché una misura su silicio futura si agganci senza rifare nulla. Resta 🔴 marcata. |
| **Approccio** | **A — Sistema + micro-benchmark isolati**: tre livelli di misura distinti (energia realizzata di sistema · costanti per-op pulite · rapporto da due sistemi veri). |

**Principio trasversale (onestà a 3 livelli):** ogni numero pubblicato porta il suo **tag di
fedeltà** e la sua **provenienza** (comando Vivado, stimolo, nodo). I tre livelli non si mescolano mai:
1. **op-count algoritmico** (Fase A, fatto) — *ciò che il modello implica*;
2. **stima Vivado post-impl con switching reale** (questa Fase B) — *ciò che la sintesi fedele produce*;
3. **misura su silicio** (Fase C, rinviata-predisposta) — *ciò che il chip misura*.

---

## 1. Architettura e claim sotto test

La Fase B è una **pipeline di misura** che prende l'RTL Donatello B2 realizzato, produce numeri
node-correct (stima-silicio), e **rimappa ogni numero a una claim della Fase A** come *confermata* o
*corretta*.

### 1.1 Tabella delle claim sotto test (spina dorsale del deliverable)

| Claim Fase A | Base Fase A | Strumento Fase B | Atteso |
|---|---|---|---|
| **DSP = 0** | po2 → shift-add | `report_utilization -hierarchical` → attribuisci i 38 DSP | **CORRETTA** (0→38); test: sono nel decode, non nello `snn_b2_fsm` |
| **<1 BRAM (<1%)** | footprint pesi | utilization reale | confermata (~1-2 tile) |
| **LUT/FF area** | stima parametrica | utilization reale | confermata (~4.5k LUT/8.5%) |
| **Fmax 100-200 MHz, WCET µs** | assunto | STA reale (già in mano) | **CORRETTA**: lane ~8.5 MHz (WNS +6.97 ns @ 8 MHz); margine WCET regge |
| **e_AC 0.9pJ / e_MAC 4.6pJ (45nm)** | Horowitz | micro-datapath `report_power` @28nm | da misurare; node-mismatch da correggere |
| **Energia/inf SNN** | SynOps × Horowitz | `report_power`(SAIF) × cicli/Fclk | realizzata ≫ algoritmica (overhead time-mux) |
| **Vantaggio 5.11–8.38× / ~15×** | formula | ANN matched `report_power` + formula node-correct | possibile **riduzione** su FPGA (DSP48) |
| **Termica (derating Tj)** | stima | `report_power` termico + Tj | confermata come non-problema (mW) |

### 1.2 Forma della pipeline

```
[Donatello B2 RTL] → impl ─┬─ report_utilization -hier → {DSP attribuiti, LUT/FF/BRAM reali}
                           ├─ report_timing            → {Fmax/WNS reali}
                           └─ SAIF(stimolo) → report_power → {P_din, P_stat} → pJ/inf realizzato
[micro-AC po2]   → impl → report_power → e_AC @28nm  ┐
[micro-MAC fix]  → impl → report_power → e_MAC @28nm ┼→ costanti node-correct
[ANN 4→32→5 matched] → impl → report_power → E_ann   ┘→ rapporto vero + cross-check formula
                                                       ↓
                       TABELLA DI VALIDAZIONE claim-by-claim (confermata/corretta) + CSV + addendum
```

---

## 2. I cinque componenti di misura

### (a) Verità su risorse e timing
Ri-impl di Donatello B2 con `KEEP_HIERARCHY` soft (per attribuzione per-modulo), poi
`report_utilization -hierarchical` + `report_timing_summary`.
**Test chiave — attribuzione dei 38 DSP:** se tutti nel decode (interp affine della σ-LUT:
`(raw-offset)·invtau`, `frac·(s1-s0)`, `hilo·s`) → la claim "0 DSP *sinapsi*" sopravvive ma "0 DSP
*design*" no. Se anche 1 DSP è nello `snn_b2_fsm` → una moltiplicazione po2 non è diventata shift =
**finding reale** (violazione della premessa po2). Timing reale già in mano.

### (b) Potenza di sistema del B2 — nodo concettuale centrale
Post-impl timing-sim (xsim) del netlist instradato, guidato da stimolo reale → **SAIF** →
`read_saif` + `report_power` → P_dinamica + P_statica. Due stimoli:
- **tipico**: traiettoria reale da `matlab/test_trajectories.mat` (firing ~20.8% di Donatello);
- **worst-case**: stimolo che massimizza il firing (upper bound di potenza).

**cicli/inf MISURATI dal segnale `done`** (non assunti; ~340). **E/inf = (P_din+P_stat)·cicli/Fclk.**

⚠️ **Finding atteso #1 — energia realizzata vs algoritmica.** Il B2 è time-multiplexato (~340 cicli,
a 8 MHz ≈ 42 µs/inf). L'op-count conta solo gli AC (~SynOps·e_AC, ordine 10²–10³ pJ: dal report ~400 pJ
tipico → ~1200 pJ worst). Il design realizzato brucia P_statica per 42 µs + overhead dinamico
FSM/RAM/clock-tree → **E_realizzata/inf verosimilmente ≫ dell'algoritmica**: il time-mux scambia area per
tempo, e il tempo lungo accumula leakage. Riportiamo **entrambe** (algoritmica invariante
e realizzata di sistema) + **sweep di Fclk** (più veloce → meno energia statica/inf, fino al limite timing).

### (c) Costanti al nodo — seconda insidia FPGA
Due micro-datapath isolati: `micro_ac` (accumulatore po2 shift-add = "sinapsi" SNN) e `micro_mac`
(MAC fixed-point = "sinapsi" ANN), sintetizzati singolarmente → `report_power` → **e_AC, e_MAC in
pJ/op nativi 28nm**.

⚠️ **Finding atteso #2 — MAC-su-DSP48 può correggere la claim.** Le costanti Horowitz sono da
standard-cell **ASIC** (MAC ~5× AC). Su FPGA il MAC va su un **DSP48 hard-block** efficientissimo, lo
shift-add po2 su **LUT+carry**: sul silicio FPGA reale il divario e_MAC/e_AC può **restringersi
drasticamente** → il vantaggio energetico SNN su FPGA potrebbe essere **più piccolo** del report
(numeri ASIC), e l'edge vero del SNN essere **"0 DSP + footprint minimo"**, non l'energia grezza. Se
emerge, è una correzione importante e onesta.

### (d) Baseline ANN matched
MLP densa 4→32→5 **time-multiplexata** (1 MAC/ciclo, pesi ROM), single-source via HDL Coder come
`snn_core` (stessa filosofia del B2 → confronto equo sull'architettura, non solo sull'algoritmo). Pesi
rappresentativi (random in-range; la potenza dipende dallo switching, non dall'accuratezza — dichiarato).
Synth+impl+`report_power` con lo stesso stimolo → **E_ann/inf reale**. Rapporto vero = E_ann/E_snn (due
sistemi), con **cross-check** vs formula (e_MAC·MAC / e_AC·SynOps node-correct).

### (e) Termica
Dalla potenza totale reale → `report_power` stima **Tj** (giunzione) all'ambiente dato. Alla nostra
scala (mW) l'innalzamento Tj è verosimilmente trascurabile → le figure termiche 🟡 del report si
validano come **non-problema** (confermato dal numero di potenza vero). Niente sweep XPE elaborato se la
potenza è banale — dichiarato.

---

## 3. Flusso dati, gestione errori, verifica

### 3.1 Flusso dati
```
test_trajectories.mat → xn reali → Q5.13 → AXI-TB streaming (molte inferenze)
      ├─ stimolo TIPICO ┐
      └─ stimolo WORST   ┼→ post-impl sim → SAIF → report_power → P_din/P_stat (×2)
cicli/inf MISURATI dal done → E/inf = (P_din+P_stat)·cicli/Fclk
micro_ac → e_AC ┐  micro_mac → e_MAC ┼→ formula: (MAC·e_MAC)/(SynOps·e_AC)
ANN → E_ann ┘→ rapporto di sistema E_ann/E_snn ═╗
                                                ╠═► CROSS-CHECK (sistema vs formula)
tutto → tabella claim-by-claim + CSV machine-readable
```
I due percorsi verso il rapporto (di-sistema e per-formula) devono concordare in ordine di grandezza;
**la loro differenza *è* l'overhead di architettura** → attribuita, non nascosta.

### 3.2 Gestione errori / trappole (disciplina "investiga la causa")
- **Copertura SAIF bassa** → `report_power` cala di confidenza. Leggiamo il *confidence level*
  dichiarato; se "Low", **estendiamo lo stimolo** — niente fallback vectorless spacciato per misura.
- **Trappola I/O-pad nei micro-benchmark:** un circuito minuscolo può avere ~90% della potenza nei pad
  di I/O → e_AC/e_MAC inquinati. Mitigazione: il micro-datapath fa **molte op interne per transazione
  I/O** (array/loop, I/O registrati) e nel breakdown prendiamo **logic+signal+DSP, escludendo I/O**.
- **Post-impl timing-sim** (SDF) fallisce/lenta → fallback a post-synth funzionale per il SAIF,
  **marcato a fedeltà minore** (non silenzioso).
- **Pesi random ANN** → toggle ~50%, possibile > del reale → **sovrastima P_ann** = conservativo per il
  vantaggio SNN; dichiarato (o distribuzioni rappresentative).
- **Divergenza cross-check** grande → non è errore da nascondere: è la misura dell'overhead, attribuita.

### 3.3 Verifica (che la validazione stessa sia solida)
- **Riproducibilità:** tutto in Tcl scriptato (come il flusso bitstream) + driver; ri-eseguibile.
- **Gate di sanità** prima di pubblicare qualsiasi numero: (1) copertura SAIF > soglia; (2) confidenza
  `report_power` ≥ Media; (3) il post-impl sim **produce ancora i param corretti** (bit-exact al cosim:
  v0=26.49, T=1.63, s0=2.45, a=1.008, b=1.71); (4) potenze in range sano (mW); (5) e_AC,e_MAC > 0 e
  e_MAC ≥ e_AC.
- **Core intatto:** non tocchiamo `snn_core`; ANN e micro-datapath sono nuovi, separati → golden SNN
  bit-exact preservato.

**Il gate SAIF/report_power è non-negoziabile:** senza switching reale, `report_power` è un placeholder,
e pubblicarlo come "misura" tradirebbe l'onestà a 3 livelli.

---

## 4. Deliverable, tag di onestà, predisposizione Fase C

### 4.1 Deliverable
Documento autonomo **`document/FPGA_PHASE_B_POWER.md`** (worktree Simulink_Importer), **progettato come
sezione drop-in** per `report/FPGA_REPORT.md` (fusione a Simulink_Importer→main; niente editing
cross-branch ora). Contenuto:
- **Tabella di validazione claim-by-claim** (§1.1) come spina dorsale: ogni riga = *confermata*/*corretta*
  + numero reale + provenienza.
- Numeri reali: utilization con attribuzione DSP, timing, potenza di sistema (tipico/worst, din/stat),
  pJ/inf realizzato vs algoritmico, e_AC/e_MAC @28nm, rapporto ANN (sistema + cross-check formula), Tj.
- **CSV machine-readable** di tutti i numeri.

**Artefatti** in `matlab/axi/build/phase_b/`: Tcl scriptati, SAIF, `.rpt` (report_power/utilization),
RTL micro-datapath + ANN, testbench di streaming.

### 4.2 Mappa di re-tag (onestà)
| Figura/claim report | Da → A | Nota |
|---|---|---|
| `resource_occupancy` (LUT/FF/DSP/BRAM) | 🟡→🟢 | **DSP 0→38 CORRETTA** + attribuzione |
| `decode_criticalpath`, `area_model`, `bram_dimensioning` | 🟡→🟢 | misurati |
| `energy_*` (breakdown, vs_ann, vs_rate) | 🟡→🟢 | **rapporto rivisto** al nodo FPGA reale |
| `derating_tj_fmax`, `thermal_budget` | 🟡→🟢 | Tj da potenza vera (non-problema) |
| mW reali su silicio, leakage vs Tj HW | resta 🔴 | **Fase C** |

Distinguiamo **confermata** da **corretta**: `DSP=0→38`, `Fmax 100-200→~8.5 MHz (questa architettura)`,
`vantaggio → rivisto per DSP48-su-FPGA`. Le correzioni **sono il valore** del lavoro: un report che si
auto-corregge con dati veri è più credibile.

### 4.3 Predisposizione Fase C (senza farla)
- La tabella claim ha una **colonna "Fase C misurato" vuota/TBD** pronta a ricevere i numeri board.
- **Appendice-protocollo**: come misurare la potenza PL su PYNQ-Z1 (delta idle-vs-inferenza via sensing
  sui rail / INA esterno), quale stimolo caricare (stesso `.bit` + stream tipico già pronto).
- Predisposizione = artefatti (`.bit`, stimolo realistico) + protocollo pronti; resta solo la misura fisica.

---

## 5. Criteri di successo

1. Ogni riga della tabella §1.1 ha un **numero reale Vivado** con provenienza, marcata *confermata* o
   *corretta*, oppure esplicitamente rinviata a Fase C.
2. I **38 DSP sono attribuiti** per modulo; la claim "0 DSP sinapsi" è confermata o smentita con evidenza.
3. **e_AC, e_MAC @28nm** misurati (con isolamento I/O-pad), confrontati con Horowitz-45nm; il **vantaggio
   è ricalcolato** al nodo giusto (sistema + formula), con la nota FPGA-DSP48.
4. **Energia realizzata vs algoritmica** del B2 riportata con sweep Fclk; la distinzione è esplicita.
5. Tutti i numeri passano i **gate di sanità** §3.3; nessun `report_power` a bassa confidenza pubblicato
   come misura.
6. Deliverable **drop-in** per il report + CSV + artefatti + protocollo Fase C, tutto riproducibile via Tcl.

## 6. Vincoli permanenti (dal progetto)
- **VHDL mai a mano** per i datapath: micro-AC/micro-MAC/ANN generati via HDL Coder da sorgente MATLAB
  (single-source), come `snn_core`.
- **Core SNN congelato**: parità double ~2e-6 dopo ogni modifica a `snn_core`/`snn_types` (qui non si
  tocca). ANN e micro-datapath vivono separati.
- **Niente work-around**: se un numero non torna, si investiga la causa (I/O-pad, copertura SAIF,
  attribuzione DSP), non si aggira.
- Commit **senza** `Co-Authored-By`.

## 7. Decisioni aperte (minori)
- Sweep Fclk: quali punti (8 / 25 / 50 MHz)? Default: 3 punti dentro il limite di timing per-blocco.
- ANN: pesi random-in-range vs distribuzione distillata dai target — default random, con nota.
- Formato micro-benchmark: N op/ciclo interne per soffocare l'I/O — N da tarare sul confidence SAIF.
