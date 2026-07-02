# POST_FPGA_ROADMAP — Le 3 fasi oltre l'FPGA-evaluate (decisioni di progetto)

> **Data:** 2026-07-02 · **Branch:** `EventProp_Study` · **Stato:** **fase di RAGIONAMENTO — decisioni bloccate, NON ancora implementate.**
>
> Questo documento registra le decisioni prese in una sessione di ragionamento sulle **tre fasi successive**
> all'FPGA-evaluate (che è la Fase A "software_now", già costruita e pronta per Azure — vedi
> `document/FPGA_EVALUATE_DESIGN.md`). Serve a **riprendere il discorso in modo agile e completo** in futuro.
> Le decisioni sono bloccate salvo revisione esplicita. **Prima di scrivere codice** per una qualunque delle tre,
> aprire una vera sessione di design (brainstorming) su quella fase.

---

## 0. Come riprendere (leggere prima questo)

**Le 3 fasi (tutte POST FPGA-evaluate Fase A):**
1. **Simulatore plug&play** — carichi un checkpoint, scegli scenari, lui simula mostrando le auto dall'alto in
   tempo reale + la rete in diretta. Desktop, interattivo, universale-per-la-nostra-famiglia, estensibile.
2. **Convertitore HDL** — porta la nostra rete (ALIF ricorrente po2) su RTL, via **Simulink + HDL Coder**,
   parametrizzato per la nostra famiglia ma espandibile.
3. **FPGA-in-the-Loop (FIL)** — testa l'hardware VERO in closed-loop col simulatore, host-in-the-loop, via
   harness **PYNQ** custom.

**Stato:** decise, non implementate. **Candidato naturale di partenza: ①** (indipendente dalle altre, alto
valore/riuso, ed è anche il *driver* di ③).

**Filo conduttore (il punto strategico):** le tre fasi **non sono progetti isolati, sono una pipeline di deploy**
che poggia su ciò che abbiamo già (simulatore SW + librerie Fase A + modello golden). Se ① nasce con un *seam*
`NetworkBackend` (SW oggi, FPGA domani), allora ③ è quasi uno *swap* dentro ①. E le librerie Fase A + il modello
SW fixed-point sono già la **specifica** e il **golden reference** per ② e ③.

**Vincolo trasversale (deciso dall'utente):** questi tre strumenti devono essere **riutilizzabili anche da altri
progetti SNN futuri** → si investe nelle **astrazioni pulite** (interfacce, parametrizzazione), non in soluzioni
one-off.

**Sequenza consigliata:** ① subito · ② in parallelo/dopo (la fase più dura) · ③ dopo ②+board+Vivado.

```
[GIÀ COSTRUITO — fondamenta]
  Simulatore SW closed-loop (simulate · scenari · platoon · showcase)
  Librerie FPGA Fase A (weight/state/latency/seu/io → Qm.n · po2 · op-count · mappa-bit)
  Modello SW fixed-point = GOLDEN REFERENCE
        │ costruisce su          │ specifica + golden        │ golden/confronto
        ▼                        ▼                           ▼
  ① Simulatore plug&play ──► ② Convertitore HDL (ALIF) ──► ③ FPGA-in-the-Loop
     └─ seam "NetworkBackend"     (dipende: decisione         (dipende: ② + board + Vivado)
        (SW | FPGA) ◄──────────────  toolchain)  ──────────►  └─ si aggancia a ① come FpgaBackend
                                                                 → NUMERI DI SILICIO VERI
```

---

## 1. Fase ① — Simulatore di scenari plug&play

**Cos'è:** carichi un checkpoint, decidi gli scenari, lui va e simula, mostrando **(a)** l'andamento delle auto
dall'alto in tempo reale e **(b)** il comportamento della rete in diretta. Un simulatore "da sogno",
user-friendly, universale per reti SNN-PINN.

**Decisioni bloccate:**
- **Forma: desktop** (non web, non notebook).
- **Reti che identificano parametri** (l'identificatore → 5 param → controllore car-following). *Non* reti che
  emettono l'accelerazione diretta (per ora).
- **Interattività: sì** — poter iniettare eventi *durante* la simulazione (es. innescare una frenata live), non
  solo scegliere lo scenario a inizio run.
- **Universale-per-la-nostra-famiglia + estensibile**, non universale-da-subito.

**Cosa abbiamo GIÀ (il backend, tanto):** `utils/closed_loop_eval.py::simulate()` (closed-loop con plant + canale
V2X), `build_scenarios`, `utils/platoon_eval.py` (plotone 12 veicoli), `scripts/closed_loop_identify.py::identify()`,
`utils/snn_showcase.py` (raster + GIF + energia), `utils/net_diagnostics.py`.

**Cosa MANCA:** (a) rendering top-down animato in tempo reale, (b) pannello rete live (spike/param/membrana che si
aggiornano), (c) interfaccia plug&play (carica checkpoint + scegli scenari + inietta eventi), (d) l'astrazione
model-agnostic, (e) i *seam* per estensioni future.

**Architettura (il cuore dell'"universale + estensibile") — interfacce SOLID/DIP:**
- `Identifier` — checkpoint → 5 parametri (astrae il tipo di rete: SNN-PINN o altro).
- `CarFollowingModel` — (param + stato) → accelerazione (IDM / ACC-IIDM / Gipps / OVM / …). **Registry** di modelli.
- `Scenario` — genera lo scenario (riusa `build_scenarios`; + custom + platoon).
- `Renderer` — la vista top-down + i pannelli della rete.
- `NetworkBackend` (per ③) — `SoftwareBackend` (il modello Python) | `FpgaBackend` (la board via PYNQ).

Il loop di simulazione dipende **solo** dalle astrazioni. Conseguenze:
- **altri modelli car-following** = registri un `CarFollowingModel`;
- **controllo laterale** (estensione futura) = aggiungi un `LateralController` + stato 2D + un modello di
  cambio-corsia (es. MOBIL). L'architettura NON deve hardcodare l'1D longitudinale.
- **③ FIL** = scambi il `NetworkBackend`.

**Realizzabilità/difficoltà:** **MEDIA**, ~settimane. Il backend esiste; il lavoro è viz + UI + astrazione. Il
forward SNN per step è velocissimo → il collo è solo il rendering (banale per pochi veicoli). **Indipendente**
dalle altre due fasi. **Valore immediato altissimo** (usabile subito per demo/debug/tesi; è il driver di ③).

**Decisioni aperte (CHIUSE 2026-07-02 → vedi `document/SIMULATOR_DESIGN.md`):**
- Stack desktop: **DECISO = PySide6 + pyqtgraph** (scartati matplotlib/pygame/Dear PyGui — motivazioni nel design).
- Scope v1 = **MVP snello**; loop = **single-thread** (Fix-Your-Timestep); v_mem via attributi ALIF diretti.
  Il **design MVP v1 è approvato** (interfacce, `SimStepper`, seam `NetworkBackend`, pannello rete, replay) — manca
  solo l'implementazione (writing-plans).

---

## 2. Fase ② — Convertitore HDL (rete ALIF ricorrente po2)

**Cos'è:** portare la nostra rete su RTL, partendo dai convertitori esistenti ma **estendendo** per ALIF ricorrente.

**Decisioni bloccate:**
- **Toolchain primaria: Simulink + HDL Coder.** (Studiare gli altri per rubarne i pattern e "farlo meglio".)
- **Famiglia parametrizzata** (ALIF-lowrank-po2: hidden/rank/delay/bit_shift/tipo-neurone) **ma con espansione
  futura semplificata**. NON un convertitore universale any-SNN (sarebbe scala-ricerca).
- **Decode IIDM in PL** (nel fabric), con obiettivo **minimizzare i DSP** (non azzerarli) + **fallback al PS** se
  non ci sta o rende male.
- **Un solo core sintetizzabile riusabile + testbench in file separati** (vedi 2.3).
- **Licenze:** MATLAB completo (educational) disponibile; **Vivado da installare** (serve solo per il bitstream → ③).

### 2.1 Ricognizione tool (stato dell'arte, verificato 2026-07-02)

| Tool | Cosa fa | Gap per noi | Cosa rubare |
|---|---|---|---|
| **Spiker+** (PoliTo, open) | genera **VHDL da Python**, parametrizzato: neurone + memoria sinaptica + FSM controllo + testbench | solo LIF (I/II ord.), feedforward, MAC interi | **la struttura del generatore** (è il pattern "famiglia parametrizzata") |
| **hls4ml** | ora **RNN (LSTM/GRU)** + **Extension API** per layer custom; front-end PyTorch/ONNX | orientato DL, quant intera (no po2) | il pattern "custom layer" pulito |
| **FINN** | Finn-HLSlib **esteso con layer LIF ricorrente** (base Norse); FINN-GL per LSTM | interni complessi, Brevitas quant-intera | prova che **spiking ricorrente in HLS è fattibile** |
| **HDL Coder** (la nostra strada) | **MATLAB Function → RTL**: `persistent` fi → registri, loop stream/unroll, *nondirect feedthrough* per feedback+stato, funzioni **CORDIC** HDL-ottimizzate | — (general-purpose) | è **il percorso più diretto per il nostro neurone stateful** |

**Due riscontri chiave:**
1. **ALIF su FPGA non è terra vergine:** neuroni a **soglia adattiva ricorrenti** sono già implementati in digitale
   su FPGA (modello **DEXAT**, Nature Comms). Il nostro ALIF (soglia adattiva + fatica + bit-shift leak) è fattibile.
2. **Il nostro vantaggio che NESSUNO di loro sfrutta: pesi po2 → puro shift-add, DSP minimo.** Spiker+/FINN/hls4ml
   usano MAC interi (→ DSP). Noi il moltiplicatore lo eliminiamo. HDL Coder gestisce il po2 in modo banale
   (moltiplicare per 2^k su un `fi` = `bitshift`). Quindi Simulink+HDL Coder **preserva il nostro punto di forza**.

### 2.2 Strada consigliata

- **Cella ALIF come MATLAB Function block:** stato (`potential`, `fatigue`) in **`persistent fi`** → registri;
  loop dei tick streamato; **ricorrenza low-rank via *nondirect feedthrough***; peso po2 = **bitshift**.
- **Generatore parametrizzato à la Spiker+:** neurone + memoria + FSM + testbench, parametrizzato su
  hidden/rank/delay/bit_shift/tipo-neurone → **riusabile per SNN future**. Studiare l'Extension API di hls4ml per il
  pattern "custom layer".
- **Golden reference = il modello Python fixed-point.** Le librerie Fase A **sono già la specifica**:
  `state_profiler` dà i Qm.n per stato, `weight_profiler` il codec po2 e il footprint, `latency_model` il datapath/
  op-count, `seu_inject` la mappa-bit. **Verifica bit-true** dell'RTL contro il golden.
- **Nota licenze:** la **generazione RTL con HDL Coder NON richiede Vivado** (MATLAB emette VHDL/Verilog) → ② può
  iniziare subito. Vivado serve solo per **sintetizzare il bitstream** (③).

### 2.3 Decode IIDM in PL — minimizzare i DSP (decisione 7)

Il *decode* (dai 5 param all'accelerazione via ACC-IIDM) ha l'unica matematica "pesante": `sqrt(a·b)`, divisione
IDM, 5 `sigmoid` dei bound, `tanh` del CAH. Strategia:
- **La leva: il budget di 100 ms** (un'inferenza per passo di controllo, DT=0.1 s). Con quel margine si
  **ottimizza per AREA, non per velocità** → **CORDIC iterativo** (sqrt/div/exp→sigmoid/tanh), che è **shift-add,
  DSP≈0**, pagando in latenza (decine di cicli) **irrilevante** a 100 ms. In alternativa LUT/BRAM piccole per
  sigmoid/tanh piecewise. Dove un paio di DSP costano meno di un CORDIC, si usano liberamente.
- **HDL Coder aiuta gratis:** funzioni **CORDIC HDL-ottimizzate** (`sqrt`, `atan2`, trig, via Fixed-Point Designer)
  → RTL senza DSP.
- **Fallback PS gratis se progettato bene:** tenere il **decode come blocco separato con interfaccia netta**
  `(5 param + stato) → accel` → intercambiabile **PL-CORDIC ↔ PS-software** senza toccare il core della rete
  (stesso principio DIP di ① e ③). Obiettivo dichiarato: **minimo DSP per stare nell'hardware e ottimizzare le
  performance**, con la via di fuga al PS se non ci sta / rende male.

### 2.4 Architettura HDL: un core, testbench esterni (decisione dalla nota su 9)

Prassi HDL corretta, che guida tutto:
- **Un solo core sintetizzabile e riusabile** = il modulo della rete (il "progetto base").
- **I testbench sono file SEPARATI, non-sintetizzabili, che istanziano il core come DUT** — non "stanno dentro"
  il modulo/board. A più livelli, tutti attorno allo *stesso* core:
  1. **TB RTL** (sim ModelSim/Vivado): legge stimoli da file, confronta col golden (come fa Spiker+).
  2. **FIL host-in-the-loop** (③): il "testbench" è di fatto **l'host** che pilota il core reale via link.
- Questo dà **verifica a strati** sullo stesso modulo e rende il core una **scatola nera riusabile**.

**Realizzabilità/difficoltà:** **ALTA** — la fase più dura. Effort settimane→mesi. **Blocca** il deploy reale e ③.
**Rischi:** verifica bit-true (mismatch SW/HDL sugli edge fixed-point), il decode transcendentale (CORDIC vs LUT vs
pochi DSP — da tarare), timing closure.

**Decisioni aperte (design):** struttura del generatore; per ogni funzione del decode (sqrt/div/sigmoid/tanh) la
scelta CORDIC vs LUT vs DSP; harness di verifica bit-true SW↔HDL.

---

## 3. Fase ③ — FPGA-in-the-Loop (FIL)

**Cos'è:** co-simulazione con l'**FPGA vero nel loop di controllo**. Il simulatore SW gira scenario + fisica + viz;
a ogni passo manda l'osservazione alla board (che esegue la rete), la board calcola l'output, lo rimanda, il SW lo
applica e avanza. Valida l'**hardware reale** in closed-loop contro il modello SW.

**Decisioni bloccate:**
- **Topologia: host-in-the-loop.** Il simulatore (scenario+fisica+viz, = ①) gira sul **host**; **la board fa SOLO
  il suo** (il core della rete). Il testbench NON sta sulla board (vedi 2.4): il core è il modulo, l'host è il
  "testbench".
- **Realizzazione: harness PYNQ custom.** L'FPGA diventa un **`FpgaBackend` Python** dentro il simulatore ① →
  **un solo simulatore** guida sia software sia silicio (il *seam* `NetworkBackend`). Overlay PYNQ + AXI-Lite/DMA,
  pattern standard. (Alternativa scartata: MATLAB HDL Verifier FIL — farebbe di MATLAB il driver, *due* simulatori.)
- **Board fisica: disponibile.**

**Due scopi (distinti):** (a) **validazione funzionale** — l'HDL si comporta come il SW in closed-loop? (il valore
principale); (b) **misura timing/potenza reali**.

**È dove arrivano i NUMERI DI SILICIO VERI** (LUT/FF/DSP da Vivado, Fmax, potenza, latenza reale, SEU con
fault-injection reale) — quelli che la **Fase A ha solo STIMATO**.

**Timing favorevole:** periodo di controllo **100 ms** → anche un link lento (UART) basta per la validazione
funzionale.

**Dipendenze:** richiede **② fatto** (l'RTL) + la **board** (c'è) + **Vivado installato** (per il bitstream).
Topologia futura complementare: **on-board** (tutto sullo Zynq, PS-Python via PYNQ guida + PL esegue) per la
fedeltà di deployment finale — non è la scelta per la validazione, ma è l'end-state.

**Realizzabilità/difficoltà:** **MEDIA-ALTA**, ma **bloccata su ②** + hardware/toolchain.

---

## 4. Riepilogo decisioni bloccate

| # | Tema | Decisione | Perché |
|---|---|---|---|
| ① | forma | desktop | controllo real-time + interattività |
| ① | tipo rete | reti che identificano parametri | il nostro caso; astrazione `Identifier` |
| ① | interattività | sì, eventi live | "simulatore da sogno" |
| ① | universalità | famiglia + estensibile | riuso senza costo da ricerca |
| ② | toolchain | Simulink + HDL Coder | licenza disponibile, po2=bitshift, integra sistema + abilita FIL |
| ② | ambizione | famiglia parametrizzata, espandibile | settimane vs mesi; riusabile |
| ② | decode IIDM | **in PL**, min DSP, fallback PS | stare nell'hardware + performance; CORDIC/LUT; blocco isolato |
| ② | struttura | 1 core sintetizzabile + TB esterni separati | riuso + verifica a strati |
| ③ | topologia | host-in-the-loop | board fa solo la rete; ① è il driver |
| ③ | realizzazione | harness PYNQ custom (FpgaBackend Python) | un solo simulatore SW+HW; riusabile |
| — | trasversale | astrazioni pulite, riusabili per SNN future | vincolo esplicito dell'utente |

---

## 5. Domande ancora aperte (da chiudere in fase di design, non ora)

- ~~**①:** stack desktop~~ → **CHIUSA**: PySide6 + pyqtgraph (design MVP v1 approvato in `document/SIMULATOR_DESIGN.md`).
- **②:** struttura interna del generatore; per ogni transcendentale del decode CORDIC vs LUT vs DSP; harness di
  verifica bit-true SW↔HDL.
- **③:** protocollo host↔board (Ethernet vs UART vs JTAG); dettagli dell'overlay PYNQ + interfaccia AXI/DMA.
- **Trasversale:** quanto spingere le astrazioni per la riusabilità (costo vs generalità).

---

## 6. Riferimenti

**Fonti (ricognizione tool, 2026-07-02):**
- Spiker+ (generatore VHDL per SNN, PoliTo): https://arxiv.org/html/2401.01141v1 · https://github.com/smilies-polito/Spiker
- hls4ml RNN su FPGA: https://iopscience.iop.org/article/10.1088/2632-2153/acc0d7
- FINN-GL / Finn-HLSlib LIF ricorrente: https://arxiv.org/html/2506.20810v1
- HDL Coder — persistent + fi (MATLAB Function → RTL): https://www.mathworks.com/help/hdlcoder/ug/using-persistent-variables-inside-matlab-function-blocks-for-hdl-code-generation.html
- Neurone a soglia adattiva ricorrente su FPGA (DEXAT, Nature Comms): https://www.nature.com/articles/s41467-021-24427-8

**File del progetto rilevanti:**
- FPGA-evaluate Fase A (già fatta): `document/FPGA_EVALUATE_DESIGN.md`, `document/FPGA_EVALUATION_FRAMEWORK.md`
- Librerie Fase A (= specifica + golden per ②): `utils/{weight_profiler,state_profiler,latency_model,seu_inject,io_hil}.py`
- Simulatore SW (= backend di ①, golden per ②/③): `utils/closed_loop_eval.py`, `utils/platoon_eval.py`,
  `scripts/closed_loop_identify.py`, `utils/snn_showcase.py`, `utils/net_diagnostics.py`
- Architettura rete (ALIF/po2): `core/{network,neurons,eventprop,hardware}.py`
- Regola REST API SysML v2 (se servirà tracciabilità MBSE): `~/.claude/rules/sysml-v2-api-rest-expert.md`

> **Nota di ripresa:** quando si parte con una fase, aprire una sessione di **design** (brainstorming) su quella
> specifica fase prima di scrivere codice. Candidato di partenza consigliato: **①**.
