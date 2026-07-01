# FPGA_EVALUATION_FRAMEWORK — Catalogo dati & piano valutazione FPGA (CF_FSNN)

> **Data:** 2026-06-30 · **Branch:** `EventProp_Study` · **Repo:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN`
>
> **Documento-master della prossima fase.** Definisce (A) l'analisi critica del framework a 6 punti dell'utente e (B) il catalogo esaustivo di tutti i dati estraibili dalla rete per una evaluation specifica-FPGA sul target **Xilinx Zynq-7020 / PYNQ-Z1** (≈53.200 LUT, 106.400 FF, 220 DSP48E1, 140 BRAM da 36Kb ≈ 4,9 Mb on-chip, no UltraRAM, clock tipico 100–200 MHz, dual-core ARM Cortex-A9 PS).
>
> **Rete di riferimento (champion baseline):** SNN ricorrente ALIF `4→32→5`, ricorrenza low-rank `rank=8` (rec_U 32×8, rec_V 8×32), `max_delay=6` delay assonali, `TICKS_PER_STEP=10`, output `LICell` integratore, decode sigmoid→bound fisici `[v0∈8–45, T∈0.5–2.5, s0∈1–5, a∈0.3–2.5, b∈0.5–3]`. Pesi po2 (QAT in-the-loop), spike binari, leak bit-shift. **800 pesi sinaptici + 64 param ALIF = 864 param apprendibili** (verificato: 128+256+256+160 pesi; base_threshold 32 + thresh_jump 32). Branch `EventProp_Study`.
>
> **Stato HW:** nessun HDL, nessun bitstream, nessuna sintesi Vivado/Vitis. Tutto ciò che è `software_now` opera sui tensori/forward PyTorch in locale (checkpoint `.pt` presenti in locale, non solo su Azure).

---

## 0. TL;DR — la tesi centrale

- **po2 → shift-add → DSP≈0.** `PowerOf2Quantize` (core/hardware.py) mappa ogni peso in `sign·2^round(log2|w|)` con esponente clampato in `[-4,+1]` e mask sotto `2^-5`: alfabeto di **13 valori** `{±2^-4..±2^1}∪{0}` = **~4 bit** (1 segno + 3 esponente). Quindi il "moltiplicatore" sinaptico è un **barrel-shifter a 3 bit + adder**, non un DSP48E1.
- **Spike binari → l'operazione sinaptica è un ACCUMULATE condizionato (AC).** `SurrogateSpike_Hardware` produce `{0,1}` con `potential≥eff_thresh`. Le sinapsi spike-driven (recV 256 + LI 160 = 416 op/tick) sono AC event-driven; l'input FC (128) e recU (256) sono shift-add densi su operando non-binario.
- **La ricorrenza low-rank è una cascata a DUE stadi, non 512 op parallele.** `rec_int = V @ prev_spike` (8-dim, spike-driven AC) **poi** `rec_curr = U @ rec_int` (operando NON-binario → shift-add denso). Il vettore intermedio `rec_int` (8 accumulatori fixed-point) è uno stato nascosto con range proprio, e i due GEMV sono **sequenziali** (U non può partire prima di V) → il critical path del ramo ricorrente ha **profondità doppia** rispetto a input-FC e output.
- **Leak = bit-shift, reset = sottrazione.** `leak = potential >> bit_shift` (default `>>3`, leak 1/8); soft-reset `potential -= spikes·eff_thresh`; fatica omeostatica (`base_threshold=1.5`, `thresh_jump=0.5`). Tutto multiplier-free, single-cycle, incondizionato.
- **QAT in-the-loop, NON PTQ.** `po2_quantize` è nel forward di ogni layer (network.py) col toggle `PO2_ENABLED`: l'errore di quantizzazione dei pesi è già visto in training (BPTT/EventProp). Questo cambia radicalmente il senso del punto "quantizzazione" del framework utente.
- **Jitter di calcolo strutturalmente NULLO.** Il datapath non ha branch data-dependent: tick-loop a bound fisso (`n_ticks=10`), delay-loop a bound fisso (`max_delay=6`), ricorrenza low-rank densa, spike che condiziona il VALORE ma non il numero di cicli. È un'architettura naturalmente **WCET=BCET**.
- **Enorme slack real-time.** ~800 op sinaptiche/tick × 10 tick × 10 Hz = **80.000 op/s** contro ~10^7–10^8 cicli/s del fabric a 100–200 MHz: utilizzo ~0,08%, margine di ~3 ordini di grandezza sul budget di `Dt=0.1 s`.
- **Footprint memoria minuscolo.** 800 pesi × 4 bit = 3.200 bit ≈ 0,4 KB → **<1 BRAM da 36Kb** su 140 disponibili. Gli stati (~125 word) stanno nei FF. La rete è ~3 ordini di grandezza sotto il budget on-chip.
- **Cosa è GIÀ coperto dall'evaluate attuale.** Quantizzazione dell'**OUTPUT** (i 5 param, `utils/quantize.py` fake_quant Qm.n + quantize_po2 + `QuantParamModel`, Tier 5 T5.1/T5.2); stima energia da spike-rate (`energy_estimate`, E_MAC=4.6pJ/E_AC=0.9pJ Horowitz); canale V2X ricchissimo a livello step (`closed_loop_eval.py`: PDR, Gilbert-Elliott, latenza/jitter FIFO, hold-last-CAM, Age-of-Information, OU noise); safety SSM (`safety_metrics`: brake_margin_min, impact_dv, TTC/TET/TIT/DRAC); identificabilità (FIM/cond, PE); `param_chattering` FFT.
- **Cosa MANCA per un FPGA-eval completo.** (1) studio **QAT-vs-PTQ formale** + curve accuratezza/sicurezza vs bit-width dei PESI (con re-training onesto); (2) analisi **range/overflow degli stati intermedi fixed-point** — inclusi `rec_int` (8-dim) e l'accumulo LI su 10 tick — → Qm.n minimo; (3) **resource model** LUT/FF/DSP/BRAM + DSE pipeline-vs-unroll; (4) **modello di latenza cycle-accurate** con la cascata ricorrente a 2 stadi e prova di determinismo; (5) **bit-flip injection / SEU** su pesi (BRAM) **e sulla CRAM del datapath serial-reuse** con ranking per-bit + FIT/TMR/ECC + ASIL; (6) **potenza mW@clock** dinamica+statica + derating termico; (7) requisito I/O hard **AoI_max fisico** e failure-mode di **cold-start**. Tutto il "pre-silicio" è `software_now`; solo occupazione reale, timing STA, potenza reale e HIL richiedono sintesi/board.
- **Trappola di scopo del framework a 6 punti.** Il framework utente è orientato a CNN/MLP feed-forward (FINN, Vitis-AI DPU, hls4ml). Il CF_FSNN è una **SNN ALIF con ricorrenza low-rank interna** (`rec_U`/`rec_V` su `prev_spike`; NON la classe RSNN full-matrix `Deep_RSNN_V5`, verificata non usata da `build_model`) con delay, fatica, leak bit-shift, decode IDM: nessun tool push-button la modella nativamente (il DPU **non supporta nemmeno il Zynq-7020**). Realistico: RTL/HLS **custom** per il core, tool standard solo per i blocchi FF.

---

## 1. Analisi del framework a 6 punti dell'utente

### 1.1 — Aritmetica & sensibilità alla quantizzazione

**Cosa significa.** Studiare l'effetto della finitezza numerica (bit-width dei pesi, degli stati, dei prodotti/accumuli intermedi) sull'accuratezza dell'identificazione dei 5 param e sulla sicurezza closed-loop; distinguere QAT (errore visto in training) da PTQ (quantizzazione a posteriori).

**Perché conta PER NOI.** Il valore intero dell'architettura è la codifica po2: se i 4 bit/peso e gli stati fixed-point non degradano l'identificazione né la sicurezza, la rete è deployabile su fabric senza DSP. Il punto vero non è "quanto degrada la quantizzazione" ma "quanto il **nostro QAT** ha già assorbito quel degrado".

**Mapping sul po2-SNN.** Pesi po2 in `{±2^-4..±2^1}∪{0}` → ogni sinapsi = barrel-shifter + add, zero DSP. La sensibilità fisica passa per `acc_iidm_accel` (network.py 567-626): `s*=s0+relu(vT+v·Δv/2√(ab))` e `a_IIDM=a(1−(v/v0)^4−z^2)`; il jacobiano `∂a/∂param` è il moltiplicatore che trasforma il rumore di quantizzazione in chattering. Stati critici: `potential` ALIF (limitato da leak >>3 e soft-reset, base 1.5), l'accumulatore intermedio low-rank `rec_int` (8-dim, non-binario), e soprattutto l'accumulo **LICell su 10 tick senza reset** — lo stato a dinamica più ampia.

**Cosa abbiamo già.** `utils/quantize.py`: `fake_quant(x, frac_bits=8)` = Qm.n sui param, `quantize_po2(x)` = po2 sui param; `QuantParamModel` propaga il degrado nel closed-loop e nell'identificazione (Tier 5 T5.1 da solo, T5.2 combinato col degrado V2X). Il rumore di quantizzazione dei PESI è già visto in training (po2 nel forward). `param_chattering` (FFT >0.5 Hz) misura l'effetto finale. Toggle `PO2_ENABLED` per l'ablazione float-vs-po2.

**Cosa manca.** (a) studio QAT-vs-PTQ formale (controfattuale: allena float con `PO2_ENABLED=0`, quantizza a posteriori, confronta col QAT nominale) e curve accuratezza/sicurezza vs bit-width dei pesi — con l'avvertenza che la curva onesta richiede re-training QAT a ogni bit-width (§1.1 illusione); (b) jacobiano IIDM `∂a/∂param` analitico/numerico; (c) istogrammi/range degli STATI intermedi fixed-point (incluso `rec_int`) → Qm.n minimo (int_bits/frac_bits); (d) distribuzione d'errore di quantizzazione PER-PARAMETRO fisico [v0,T,s0,a,b]; (e) simulazione bit-true del datapath shift-add; (f) errore della sigmoid/scaling di `_decode_params` in fixed-point (LUT sigmoid, offset/tau quantizzati).

**Illusione / non-applicabile.** **Fare PTQ sopra i pesi già po2** misurerebbe rumore su rumore: il CF_FSNN NON è un modello float da quantizzare a posteriori. Il PTQ va costruito correttamente (allena in float, quantizza dopo) SOLO come controfattuale per misurare quanto il QAT recupera; usato ingenuamente è un errore metodologico. Inoltre "8 bit lossless" della letteratura SNN è già superato al ribasso dal nostro schema (~4 bit): la domanda giusta è se si può scendere sotto 4 bit, non se 8 bastano — e per rispondere onestamente serve un mini-sweep di **re-training QAT a 3/4/5 bit**, non un semplice ri-clamp dell'esponente sul checkpoint a 4 bit (che misura solo la sensibilità PTQ del modello già addestrato).

---

### 1.2 — Risorse / Design Space Exploration (occupazione logica)

**Cosa significa.** Tradurre il grafo in occupazione device (LUT/FF/DSP/BRAM) e mappare il trade-off area/throughput/latenza variando parallelismo (serializzazione ↔ full-unroll), bit-width, mapping shift-add vs DSP.

**Perché conta PER NOI.** Dimostrare che il CF_FSNN sta comodamente nel Zynq-7020 e che la scelta po2 libera i 220 DSP. Con lo slack temporale enorme, l'ottimizzazione dominante è **serial-reuse aggressivo** (poche unità shift-add riusate) per minimizzare l'area.

**Mapping sul po2-SNN.** Conteggio esatto: 800 op sinaptiche/tick = **FF 128 shift-add** (input analogico continuo) + **recV 256 AC** (spike-driven, primo stadio `V @ prev_spike`) + **recU 256 shift-add** (secondo stadio `U @ rec_int`, operando non-binario) + **LI 160 AC** (spike-driven). La ricorrenza low-rank NON è una full-matrix: è la cascata `U @ (V @ prev_spike)` che produce l'accumulatore intermedio `rec_int` (8-dim) — 512 pesi contro i 1024 di una 32×32 densa, ma con **2 stadi seriali** da contabilizzare separatamente nel critical path. Ring-buffer delay (`max_delay=6 × 4 = 24` word) + delay-mask. Il **blocco IDM analitico** (`sqrt(a·b)`, 2-3 divisioni, tanh del blend, `(v/v0)^4`) + sigmoid decode è l'UNICO punto che richiede DSP/CORDIC/LUT: lì si concentra il vero costo se sintetizzato on-fabric.

**Cosa abbiamo già.** `energy_estimate` dà il #AC effettivo (spike-driven) e il conteggio operazioni (ann_macs=800 MAC/step), ma NON traduce in LUT/FF/DSP/BRAM. Struttura del grafo completamente ispezionabile. Conteggio pesi noto (800 po2 + 64 ALIF).

**Cosa manca.** Resource model parametrico LUT/FF/DSP/BRAM; isolamento di `rec_int` (8 accumulatori) come registro fixed-point da dimensionare; DSE pipeline-vs-unroll (curve area/throughput/latenza); costo del blocco IDM+sigmoid on-fabric; dimensionamento BRAM (pesi + stati + buffer); Fmax/timing; confronto risorse baseline vs varianti (Stacked, StackedSkip, MultiRate, WTA, full-matrix); decisione partizionamento PS/PL (IDM sul Cortex-A9 vs sul fabric).

**Illusione / non-applicabile.** Il claim "zero DSP grazie a po2" vale SOLO per le sinapsi. Il datapath post-SNN (sigmoid, `(hi-lo)·sigmoid`, `sqrt(a·b)` nell'IDM) può richiedere DSP/LUT/BRAM: **contabilizzarlo o spostarlo sul PS ARM**. Riferimento device: un SNN LIF da 720 neuroni su Zynq-7020 usa 15.042 LUT (28%), 16.003 FF (15%), 113 BRAM (81%), 4 DSP (2%) — la nostra rete è ~22× più piccola in neuroni, quindi nettamente sotto; il vincolo dominante sarà LUT/routing, non DSP né BRAM.

---

### 1.3 — Analisi temporale e determinismo (STA concettuale, WCET, jitter)

**Cosa significa.** Modello di latenza in cicli (WCET), Fmax/slack, jitter, verifica del margine real-time contro il budget `Dt=0.1 s` (V2X 10 Hz) e latenza end-to-end CAM→5 param.

**Perché conta PER NOI.** Un controllore ACC automotive richiede determinismo hard-real-time. La tesi centrale è che il **jitter di calcolo è strutturalmente nullo** (WCET=BCET), la proprietà più preziosa per la certificazione — e va resa esplicita e misurata, perché oggi è implicita.

**Mapping sul po2-SNN.** `WCET_step = n_ticks·[ FF shift-add (128) + ricorrenza a 2 stadi (V-GEMV → U-GEMV, 512) + output (160) + update-neurone (32) ] + decode`. po2 shift-add → critical path corto (barrel-shifter+adder, non moltiplicatore). Spike AC gating → conteggio cicli costante = zero jitter. **Il ramo ricorrente domina il critical path del tick** perché è l'unico a 2 stadi seriali (V poi U), mentre input-FC e output sono a stadio singolo: la profondità del path ricorrente è `lat(V-tree) + lat(U-tree)`, non la dimensione bruta delle matrici. `TICKS_PER_STEP=10` e `max_delay=6` sono ritardi ALGORITMICI (warm-up del ring-buffer), ortogonali alla latenza HW per-inferenza.

**Warm-up: chiarimento critico.** Il `x_buffer` è `deque(maxlen=max_delay)` aggiornato **UNA VOLTA per `forward_step`** (per step `Dt`), non per tick interno: i 6 slot coprono 6 step = **0,6 s** di storia dell'INPUT (l'implementazione — deque per-step — vince sulla docstring di network.py che erroneamente indica 0,06 s; vedi §Correzioni). Dentro ogni step i 10 tick rileggono lo stesso `x_buffer`. Conseguenza HW: in deploy streaming continuo il ring-buffer non viene mai resettato dopo il warm-up iniziale → il costo warm-up è **una-tantum all'avvio del veicolo**, da ESCLUDERE dal WCET per-step ma da INCLUDERE nella latenza di cold-start (safety: nei primi 6 step dopo power-on i param girano su buffer parzialmente-zero — failure mode trattato in §1.5/F4).

**Cosa abbiamo già.** `energy_estimate` conta le SynOps per-step (backbone riusabile per il WCET) ma le monetizza in pJ, NON in cicli. `closed_loop_eval.py` modella jitter/latenza del **CANALE V2X** (FIFO, AoI, hold-last-CAM) — cioè il jitter del BUS, non quello di CALCOLO.

**Cosa manca.** Modello di latenza cycle-accurate (op-count → cicli con tabella latenza-per-op e fattore di parallelismo) che tratti la ricorrenza come **2 stadi seriali**; prova formale di jitter nullo (op-count invariante rispetto ai dati); analisi WCET vs BCET; critical path del decode isolato (sqrt/div/tanh); margine real-time quantificato (cicli/step vs 10^7 cicli @100 MHz); STA/Fmax reali (sintesi); latenza end-to-end CAM→5param (PS+AXI+PL); overhead warm-up cold-start; jitter multi-clock-domain (CDC PS 650/667 MHz-PL 100-200 MHz).

**Illusione / non-applicabile.** Un'implementazione **event-driven** che salta gli spike a 0 per risparmiare energia REINTRODURREBBE jitter (WCET a spike-rate max vs BCET a 0 divergono): il design tick-fisso (jitter 0) e l'event-driven (energia minima) sono un trade-off da dichiarare, non un free lunch. Il budget dominante non è il calcolo (tick << µs) ma la **latenza di comunicazione V2X** — l'analisi WCET deve includere la catena CAM→comando end-to-end, non solo i cicli di inferenza.

---

### 1.4 — HIL & I/O (bus automotive)

**Cosa significa.** La catena fisica: ricezione CAM V2X (GbE/PCIe/PS) → deserializzazione ASN.1 → inferenza SNN → emissione 5 param verso l'ECU powertrain (CAN-FD/Automotive-Ethernet), con buffering di burst e chiusura del loop su rig HIL (dSPACE SCALEXIO/Speedgoat a 1 kHz).

**Perché conta PER NOI.** Il SNN produce 1 vettore di 5 param ogni 100 ms consumando 10 tick shift-add: il carico I/O è minuscolo (≈8 B in, ≈10 B out, entrambi in UN frame CAN-FD da 64 B). Il collo di bottiglia HIL NON è la banda ma la **latenza end-to-end e il jitter di consegna** entro la deadline di 100 ms.

**Mapping sul po2-SNN.** `forward_step` chiamato 1 volta/step `Dt=0.1 s` allineato a V2X 10 Hz; 1 CAM in → 10 tick → 1 vettore out. Deadline hard = 100 ms per (ricezione + deserial + 10 tick + decode + emissione). Il canale esistente `_channel_obs` degrada già la percezione del leader con PDR/Gilbert-Elliott/latenza/jitter/AoI, ma a granularità di STEP (1 slot = 1 CAM), non di byte/frame/coda.

**Requisito hard mancante: AoI_max fisico.** Oggi l'AoI è una metrica **osservata a posteriori**. Il requisito di certificazione è invece **derivabile a priori**: data la cinematica (gap `s`, chiusura `dv`, decelerazione max leader `b_leader`), esiste un `AoI_max(s, dv, b_leader)` oltre il quale una CAM stantia rende il controllo non-sicuro **indipendentemente dalla rete** (l'informazione è troppo vecchia). Questa soglia lega direttamente `brake_margin_min` all'età del dato ed è il vero requisito I/O che il bus DEVE garantire ("consegna entro `AoI_max(scenario)` o il sistema è insicuro by design"), non una statistica raccolta dopo. È derivabile `software_now` da `safety_metrics` + cinematica worst-case (vedi F5 / §2.8).

**Cosa abbiamo già.** Canale V2X sorprendentemente ricco (`_channel_obs`, `simulate`): PDR Bernoulli, Gilbert-Elliott a burst, latenza+jitter con buffer FIFO, hold-last-CAM, blackout, OU sensor noise, **Age-of-Information** (aoi_mean/max in s). Proxy DCC `cbr_to_pdr` (density→CBR→PDR). Sweep robustezza `v2x_robustness_sweep` (PDR × latenza → collision_rate, p5 min_TTC). Latenza CAM iniettata nel plotone (T3.6). `param_chattering`.

**Cosa manca.** Modello d'arrivo dei pacchetti sub-DT; coda di ricezione a profondità finita + rischio overflow (oggi il buffer `buf` cresce illimitato); riassemblaggio CAM frammentate; saturazione bus in frame/s (curva DCC a soglia, non lineare); latenza deserializzazione ASN.1; WCET inferenza in cicli; timing fisico CAN-FD/Ethernet; loop HIL multi-rate 1 kHz plant / 10 Hz controller; ritardo di trasporto dei param verso l'ECU (ZOH); soglia `AoI_max` fisica; determinismo end-to-end certificato.

**Illusione / non-applicabile.** Presentare i numeri del **PYNQ-Z1 (commercial-grade)** come "pronti per la produzione" è fuorviante: un deploy ADAS reale userebbe un Zynq-7000 automotive/XA-grade. Assumere che la banda sia il vincolo è sbagliato — è ampiamente sovradimensionata; il vincolo è latenza/determinismo. La chiusura reale del loop richiede board+HIL; la sua SIMULAZIONE multi-rate è `software_now` (solo un cambio di scheduling attorno a `simulate()`).

---

### 1.5 — Affidabilità e ISO 26262 (SEU / TMR / ECC)

**Cosa significa.** Iniettare SEU/bit-flip su pesi po2 (BRAM) e stati (potential/fatigue/threshold/x_buffer), misurare la conseguenza fisica (brake_margin_min, impact_dv), ranking di criticità per-bit, curve safety/NRMSE vs #flip, dimensionare la mitigazione (TMR/ECC/scrubbing), stimare FIT-rate e motivare l'ASIL.

**Perché conta PER NOI.** L'INTERO esperimento di bit-flip è fattibile ORA in software perché la codifica po2 è deterministica e replicabile sui tensori, e `safety_metrics`/`eval_safety`/`identify` accettano già un modello corrotto. La struttura po2 è peculiare: superficie d'attacco per-peso **~8× più piccola** (4 bit vs 32) ma ogni bit molto più denso (un flip d'esponente = salto ≥2×).

**Mapping sul po2-SNN.** Peso in HW = 4 bit: `b3=segno`, `b2..b0=esponente` (offset). Gerarchia di criticità: **segno > exp-MSB (×16) > exp-mid (×4) > exp-LSB (×2)**. Un peso di `out_fc` (5×32) colpisce direttamente UN canale-parametro; un peso hidden si propaga a tutti e 5. Da parametro a fisica: shift di `a/b` cambia `sqrt(ab)` e `s*` → brake_margin_min<0 → collisione.

**Due tassonomie di fault distinte.**
1. **Peso in BRAM (1 peso).** Flip PERSISTENTE su un singolo peso finché non riscritto.
2. **Stato in registro (transiente).** Flip su `potential`/`fatigue` = TRANSIENTE (leak >>3 lo smorza in pochi tick, self-healing) — argomento a favore delle SNN.
3. **CRAM del datapath serial-reuse (N pesi).** In un design serial-reuse (raccomandato per lo slack ~1250×), UN barrel-shifter po2 è time-multiplexed su MOLTI pesi: un SEU sulla CRAM che configura quello shifter corrompe il **fattore-di-shift di TUTTI i pesi che lo attraversano** in quel ciclo (o altera il routing di un intero ramo). Qualitativamente diverso dal flip su un peso BRAM. **Tensione non banale:** più si serializza (meno unità), più ogni unità diventa un single-point-of-failure amplificato → esiste un trade-off dichiarato tra area-ottima (serial-reuse) e robustezza SEU, che è il vero collo per ASIL in un design serializzato. Il ranking per-bit dei PESI è necessario ma NON sufficiente: va affiancato dalla criticità CRAM del datapath condiviso.

**Cosa abbiamo già.** Tutta l'infrastruttura di conseguenza è pronta: `safety_metrics` (collided, min_gap, min_ttc, TET/TIT, max_DRAC, **brake_margin_min** T0.10, **impact_dv**); `eval_safety` (oracolo-vs-SNN su cut_in/hard_brake/panic_stop, Wilson UB, bootstrap CI); `breakdown_curve` (sweep severità→collision_rate, scheletro esatto della curva di degrado); `identify`; `QuantParamModel`; NRMSE per-canale (train.py). Manca solo il modulo di INJECTION + il layer statistico.

**Cosa manca.** Modulo bit-flip su pesi/stati; decodifica peso-po2 → 4 bit per iniettare a livello di bit; sensitivity map per-peso/per-bit; **modello SEU CRAM del datapath serial-reuse** (corruzione simultanea dei pesi che condividono un'unità); curve safety/NRMSE vs #flip (Monte Carlo multi-seed); frazione di bit critici (essential bits model-level); FIT-rate/cross-section del device; overhead area/timing di TMR/BRAM-ECC/scrubbing (sintesi); beam-test (board); classificazione ASIL + target SPFM/LFM/DC; meccanismo di plausibilità fail-safe a valle; **failure-mode di cold-start** (primi 6 step su buffer parzialmente-zero → param fuori regime a power-on).

**Illusione / non-applicabile.** **TMR pieno** (+100-200% area/potenza) può non stare nel Zynq-7020: la strada corretta è mitigazione **criticality-aware** (TMR selettivo sui top-critici — probabilmente i 160 pesi di `out_fc` — + ECC/scrubbing SEM IP sul resto, con attenzione prioritaria alla CRAM delle unità shift-add condivise). I BRAM 7-series hanno **ECC SECDED nativo** (correzione 1 bit / rilevazione 2 bit) → i single-bit-flip persistenti sui pesi si eliminano quasi gratis. Il decode (sigmoid + clamp ai bound fisici) è già un **safety-monitor implicito** (qualsiasi param fuori bound = fault rilevato): da valorizzare nella FMEDA. Un ACC longitudinale è tipicamente **ASIL B–C** (fino a D per accelerazione indesiderata verso veicolo fermo).

---

### 1.6 — Energia & termica

**Cosa significa.** Potenza dinamica (∝ switching activity ≈ spike-rate) e statica/leakage (∝ logica alimentata, cresce esponenzialmente con Tj), tradotte in mW@clock; derating termico Tj→Fmax e budget di una ECU a raffreddamento passivo.

**Perché conta PER NOI.** La SNN sparsa cattura DUE leve: (a) dinamica bassa (spike sparsi, AC-shift invece di MAC); (b) statica bassa (design minuscolo, 0 DSP → meno logica alimentata, meno leakage). L'ANN denso equivalente paga E_MAC su tutte le sinapsi ogni tick e accende i 220 DSP (hotspot termici concentrati).

**Mapping sul po2-SNN.** La "sinapsi" è barrel-shifter+add, non moltiplicatore → E_AC va sostituito con E_shift_add (frazione di E_AC FP32) e **zero DSP**. Energia dinamica ∝ #spike (`snn_dynamic_ac = total_spikes·(r+5)`), non #sinapsi. Leak >>3 = right-shift per-neurone. Confronto ANN denso (Simple_ANN_V5/MLP 4→32→5): baseline energetica (E_MAC) e termica (più DSP commutanti = hotspot).

**Cosa abbiamo già.** `energy_estimate` copre la leva DINAMICA a livello op-count: cattura spike per-neurone/timestep (hook), conta `ann_macs = T·(4H+2Hr+5H)`, `snn_static_ac = T·4H`, `snn_dynamic_ac = total_spikes·(r+5)`, applica Horowitz 45nm (E_MAC=4.6pJ, E_AC=0.9pJ) → E_ann/E_snn/energy_advantage_x per inferenza; esporta mean_spike_rate_pct, active_neuron_frac, raster. Etichettato "STIMA Horowitz 45nm, non misura HW".

**Cosa manca.** Ponte nJ/inferenza → **mW@clock** (P_dyn = E_per_inf · inf/s); op-model differenziato E_shift_add(po2) vs E_AC(FP32) vs E_MAC; termine STATICO/leakage; fattore di scala processo 45nm→28nm; analisi termica (Tj→Fmax, budget passivo, Rth, Tamb automotive); misura reale mW (power-rail sensing) e Tj (XADC on-die); conteggio esplicito dei bit-shift di leak/fatica/reset, del soft-reset, della doppia GEMV low-rank e dell'overhead delay-line (op non-sinaptiche oggi NON contate da `energy_estimate` — vedi §Correzioni).

**Illusione / non-applicabile.** Applicare direttamente i **pJ Horowitz 45nm** a un device **28nm** introduce un errore sistematico (~2-3× a favore del 28nm, STIMA da confermare con report_power). E_AC FP32=0.9pJ **sovrastima** lo shift-add po2 (nessuna mantissa da moltiplicare): sul TERMINE SINAPTICO l'energy_estimate attuale è CONSERVATIVO (upper-bound). MA lo stesso energy_estimate **SOTTOSTIMA** le op non-sinaptiche (leak-shift 32 ALIF + 5 LI/tick, fatica 32 add+shift/tick, soft-reset 32 sub/tick, cascata low-rank a 2 stadi): il netto conservativo-o-no dipende da quale termine domina e va contabilizzato, non assunto. La potenza reale (dinamica+statica, PS incluso, clock-tree, routing) esce solo da XPE/report_power (sintesi) e misura board.

---

## 2. Catalogo esaustivo dei dati estraibili

> Legenda feasibility: **SW** = `software_now` (tensori/forward PyTorch in locale); **HDL** = `needs_hdl_synthesis` (Vivado/Vitis); **BOARD** = `needs_board_hil`.
> Priorità: **H** alta, **M** media, **L** bassa.

### 2.1 — Struttura statica & pesi

| Dato | q/ql | Cosa rivela | Metodo di estrazione | Feas. | Pri |
|---|---|---|---|---|---|
| Inventario tensori peso (shape, count, ruolo) | quant | Superficie HW da mappare (#sinapsi → #AC/shift-add): fc 32×4, rec_U 32×8, rec_V 8×32, out 5×32 | `torch.load`, iterare state_dict, gestire ENTRAMBI i naming (layer_out.weight [checkpoint piatto] vs layer_out.fc_weight [live nested]; layer_hidden.base_threshold vs layer_hidden.cell.base_threshold) | SW | H |
| Istogramma livelli po2 per esponente k∈[-4,+1] | quant | Quanti stati esponente popolati → largh. campo esponente LUT + barrel-shifter | `po2_quantize`, `e=round(log2|w|)`, `np.unique`. Da RICONFERMARE al primo run: 2^-4≈30%..2^+1≈0.2%, zero≈21% (misura preliminare, da ri-verificare) | SW | H |
| Frazione a zero (sparsità mask 2^-5) | quant | Sinapsi FISICAMENTE eliminabili (nessun AC), comprimibili CSR/bitmap. Preliminare ~21% (da riconfermare) | `mask=(|w|>2^-5)`, `1-mask.mean()` per tensore e globale | SW | H |
| Bit-width effettivo (spec vs entropia) | quant | 4 bit spec vs ~2.58 bit entropia esponente (6 livelli usati) → ricodifica compatta possibile | `n_levels=unique(e)`, `bits=1+log2(n_levels)`, entropia di Shannon | SW | H |
| Distribuzione esponenti po2 SEPARATA per matrice (pre/post-scaling sqrt(max_delay)) | quant | `fc_weight` è scalato di `sqrt(max_delay)=2.449` (FIX-BUG-4) PRIMA della po2; rec_U/rec_V/out NO. L'istogramma aggregato mescola due distribuzioni. Separarle rivela se il pre-scaling spinge fc_weight verso il clamp +1 (saturazione) e come cambierebbe al variare di max_delay (accoppiamento nascosto max_delay→distribuzione po2) | po2_quantize per-matrice, istogramma separato fc (post-scaling) vs rec/out (raw); frazione al clamp +1; ripetere con max_delay simulato diverso | SW | H |
| Raggio spettrale ricorrenza U@V (po2 e float) | quant | ρ<1 → loop contrattivo stabile fixed-point, pochi bit di guardia. Preliminare ρ_po2≈0.16, ρ_float≈0.14 (da riconfermare) | `Weff=U@V`, `max|eigvals|`, confronto po2/float | SW | H |
| Norma spettrale ‖U@V‖₂ | quant | Gain worst-case/tick del ramo ricorrente → bit interi accumulatore. Preliminare ≈0.84 (da riconfermare) | `svd(Weff)[0]` | SW | H |
| Distribuzione delay assonali | quant | Se tutti i 6 stadi ring-buffer sono usati (potabilità). Preliminare quasi-uniforme {0:21..5:18} (da riconfermare) | `bincount(delays)`; se solo delay_masks 6×32×4, `argmax_d` | SW | H |
| Ridondanza delay_masks (6,32,4) vs delays (32,4) | quant | `delay_masks` (768 one-hot) è derivabile da `delays` (128 int): `mask[d]==(delays==d)` → 768 bit ridondanti. L'HW carica solo `delays` (32×4×3bit=384 bit) e genera le mask on-the-fly | verificare elemento-per-elemento su checkpoint (entrambe le chiavi presenti); se identiche, documentare compressione config | SW | L |
| Connettività effettiva post-mask (fan-in/out) | quant | Profondità albero AC + cicli/neurone in datapath seriale | `conn=(|w|>2^-5)`, `fan_in=conn.sum(1)`, `fan_out=conn.sum(0)` | SW | M |
| Statistiche soglia (base_threshold, thresh_jump) | quant | Se costanti → hard-code condiviso. Preliminare bt μ≈1.502 σ≈0.11, tj≈costante (da riconfermare) | `mean/std/min/max/hist` dei buffer | SW | M |
| Profilo bit_shift per-neurone (leak divisor) | quant | Conferma leak sempre potenza-di-2 (no divisore); #barrel-shifter leak (MultiRate [2,3,4]) | `log2(leak_div)` o config; per MultiRate ricostruire gruppi | SW | M |
| Costanti decode (param_lo/hi, decode_offset, logit_tau, decode_scale) | quant | Costanti fixed-point da congelare nel readout; `decode_scale` è dead constant (FIX-BUG-1) | leggere buffer shape (5,) dal state_dict | SW | M |
| Conteggio param totali (apprendibili vs buffer) | quant | 800 pesi + 64 soglie apprendibili = 864; buffer (delays 128, delay_masks 768 ridondanti, bounds/decode 25) | somma `numel()` distinguendo requires_grad/nomi | SW | M |
| Footprint memoria on-chip in bit | quant | 800×4=3200 bit sinapsi + delay + soglie + stati → <1 BRAM da 36Kb su 140 (headroom ~3 ordini) | `Σ numel·bits` per categoria vs 36864 bit/BRAM×140 | SW | H |
| Istogramma po2 cross-variante (skip, feedback, inh, Q/K/V) | quant | Costo HW aggiuntivo di ogni variante vs baseline 800 | stessa pipeline su checkpoint varianti | SW | L |
| Distribuzione pesi float pre-quant (dynamic range) | quant | Pesi vicini ai bordi clamp [-4,+1] (saturazione) o sotto mask (persi); se il range po2 taglia info | `log2|w|`, frazioni <-5, [-5,-4], >1 | SW | M |
| Errore quant peso-per-peso (float vs po2) | quant | Rumore iniettato per ramo (fc/rec_U/rec_V/out); dove po2 è più lossy | `err=w-po2(w)`, mean/max/RMS per tensore e per esponente | SW | M |
| Spettro valori singolari U@V (rank effettivo) | quant | Ricorrenza in sottospazio 8-dim; se <8 modi al 95% → rank riducibile | `svd`, energia cumulata; rank@95% | SW | L |
| Verifica idempotenza po2 (master float vs già-po2) | quali | Se l'HW deve applicare po2 al load o caricare esponenti diretti | verificare `po2(w)==w` su un tensore | SW | M |
| Grafo sinaptico effettivo esportabile | quali | Netlist logica (pre,post,esponente,segno,delay) per generatore HDL | iterare maschera, serializzare JSON/CSV | SW | M |
| Occupazione risorse post-sintesi (LUT/FF/BRAM/DSP reali) | quant | Verifica delle stime (sinapsi 0 DSP) contro place&route reale | sintesi Vivado, utilization report | HDL | M |

### 2.2 — Quantizzazione & range fixed-point (stati intermedi)

| Dato | q/ql | Cosa rivela | Metodo di estrazione | Feas. | Pri |
|---|---|---|---|---|---|
| QAT-vs-PTQ gap (recupero da training in-the-loop) | quant | Quanto il QAT batte un PTQ ingenuo → valore reale dello schema | (A) `PO2_ENABLED=1`; (B) `=0`; (C) allena float + po2 una volta; confronto MAE/collisioni | SW | H |
| Curva accuratezza & sicurezza vs bit-width / range esponente | quant | Bit-budget minimo dei pesi che non degrada identificazione né safety. **ONESTA solo con re-training QAT per ogni bit-width** (ri-clamp sul checkpoint a 4 bit misura solo sensibilità PTQ, non il recupero di un QAT-a-3-bit) | parametrizzare `PowerOf2Quantize` (exp_min/max/mask), sweep [-3,0]/[-4,+1]/[-5,+2] o uniforme 3/4/5/6 bit, **ri-allenare** + ri-valutare MAE + TTC | SW | H |
| Distribuzione errore quant per-matrice (fc/rec_U/rec_V/skip/feedback) | quant | Quali pesi cadono nella mask, massa d'errore per layer → candidato a più bit | `err=w-po2(w)`, media/std/max/hist, frazione azzerata | SW | H |
| Mappatura errore-peso → errore per-parametro fisico [v0,T,s0,a,b] | quant | Quale param fisico è più fragile → schema misto (più bit su pesi critici, es. 'b' frenata) | ablazione: po2 solo un layer/fetta alla volta, Δ MAE per canale | SW | M |
| Range e bit dell'accumulatore intermedio low-rank `rec_int` (8-dim) | quant | Stato NASCOSTO tra i 2 stadi della ricorrenza (`rec_int = V@prev_spike`): somma di spike binari pesati po2 su fan-in 32. Registro fixed-point a sé, mai isolato altrove, il cui range determina i bit dell'accumulatore 8-dim e la largh. del 2° GEMV `U@rec_int` | forward_hook tra `rec_int=linear(prev_spike,V)` e `rec_curr=linear(rec_int,U)` in HiddenLayer_ALIF; min/max/p99. Worst-case teorico = Σ|V_po2| per riga (statico, senza forward) | SW | H |
| Jacobiano IIDM ∂a/∂param | quant | Moltiplicatore fisico che trasforma rumore quant in chattering; per regime free-flow vs car-following | `acc_iidm_accel` differenziabile: `autograd.functional.jacobian` su stati campionati | SW | H |
| Propagazione errore-quant → chattering closed-loop (HF power) | quant | Aumento energia spettrale >0.5 Hz e jerk RMS dell'a_ego (float vs po2 vs QuantParam) | closed-loop nelle 3 condizioni + `param_chattering` + PSD jerk | SW | H |
| Range/istogramma potential ALIF (membrana hidden) | quant | int_bits per non saturare (base 1.5, soft-reset limitano ma i picchi pre-reset vanno misurati) | forward_hook su ALIFCell, min/max/p99/hist su batch reale | SW | H |
| Range corrente sinaptica in ingresso (somma shift-add) | quant | Largh. accumulatore fixed-point (FF su 4+rank+6-delay) per evitare overflow d'accumulo | hook su `current`/`rec_curr` in HiddenLayer_ALIF; worst-case = Σ|w_po2| attivi | SW | H |
| Range accumulo LI su n_ticks (stato output pre-sigmoid) | quant | Stato a dinamica più ampia (10 tick, no reset) → Qm.n readout e range raw pre-sigmoid | hook su `layer_out.cell.potential` e `raw_out`; posizione vs zona lineare sigmoid | SW | H |
| Range fatigue / eff_thresh (soglia adattiva) | quant | Bit della soglia adattiva; eff_thresh non deve saturare il comparatore. Equilibrio ~thresh_jump/(1-2^-3) | hook su `fatigue`/`eff_thresh`, max/p99/hist | SW | M |
| Qm.n minimo (int_bits/frac_bits) per stato senza saturazione/underflow | quant | Formato fixed-point per potential/fatigue/current/LI/rec_int (leak >>3, thresh_jump 0.5 fissano frac_bits) | `int_bits=ceil(log2 max|·|)+1`; sweep `fake_quant` finché non cambia spike/decisioni | SW | H |
| Leak-underflow: frac_bits minimo che preserva il decadimento per potential piccoli | quant | `leak = potential>>3`: in fixed-point, per `|potential| < 2^bit_shift·2^-frac_bits` il leak si azzera (underflow) → potential non decade più (stuck). Trova frac_bits min che tiene il leak vivo near-threshold | dai range potential (F2), simulare `potential>>3` in Qm.n a vari frac_bits, contare frazione step con leak-fixed=0 mentre float>0; soglia sotto cui l'ALIF non replica il float | SW | M |
| Simulazione bit-true del datapath (troncamento/rounding/ordine accumulo) | quant | Errore residuo dovuto SOLO all'aritmetica finita degli stati (non catturato da QuantParamModel) | forward NumPy con `fake_quant` dopo ogni op; confronto spike/param/collisioni | SW | M |
| Errore sigmoid + scaling `_decode_params` in fixed-point | quant | Errore di sigmoid tabellata (N=16/32/64) + offset/tau quantizzati sui 5 param | sostituire `torch.sigmoid` con LUT quantizzata, Δ param + closed-loop | SW | M |
| Errore delay-mask × pre-scaling sqrt(max_delay) sui pesi fc | quali/quant | Il peso effettivo per delay d è `w_po2·mask_d` (mask binaria → moltiplicazione esatta), MA lo scaling `fc_weight.mul_(sqrt(max_delay))` precede la po2 → verifica che sqrt(6)=2.449 non spinga pesi oltre 2^1 (saturazione clamp) | ricostruire `w_scaled=fc_float·2.449`, po2, contare frazione a clamp +1; incrocio con distribuzione esponenti fc | SW | M |
| Bit-exactness comparatore spike sotto fixed-point | quali | Un LSB può flippare uno spike e propagarsi → tasso di flip | comparatore fixed vs float su potential/eff_thresh catturati | SW | M |
| Sensibilità raster/param a quant fixed-point DEGLI STATI | quant | Estende Tier 5 (solo output) ai registri interni → bit minimi sufficienti | `fake_quant` su potential/fatigue/LI/rec_int dietro flag, sweep bit, Δ 5 param + closed-loop | SW | H |
| Verifica bit-esatta software-vs-HDL (co-simulazione) | quant | Spike e param identici a livello di bit tra golden fixed-point e RTL | esportare vettori test, confronto con sim Vivado/Vitis | HDL | L |
| Overflow/saturazione REALE accumulatori sul device | quali | Che gli accumulatori non saturino sul silicio nei casi limite | flag sticky overflow in PL, monitor via PS ARM in HIL | BOARD | L |

### 2.3 — Dinamica spiking & temporale

| Dato | q/ql | Cosa rivela | Metodo di estrazione | Feas. | Pri |
|---|---|---|---|---|---|
| Raster spike hidden per-neurone × TICK × step | quant | Dato madre: #eventi AC esatti + distribuzione temporale → energia + worst-case switching/ciclo | estendere `capture_run`: salvare `captured` intero (n_ticks,H) invece di `np.sum(axis=0)` | SW | H |
| Firing rate per-neurone (Hz e spike/step) | quant | Distribuzione attività fra neuroni; hotspot energetici vs quasi-inattivi | somma su tick/step / (T·n_ticks), aggregato multi-scenario | SW | H |
| Neuroni MORTI (mai sparano) | quant | Ridondanti: colonne fc_out/righe rec inerti → pruning statico (rimuove LUT/FF) | `(rate==0).sum()` su test-set ampio (attenzione persistent excitation) | SW | H |
| Neuroni SATURI (sparano ~ogni tick) | quant | Soglia mal tarata / bias costante → sostituibili con costante hardwired | `(rate>0.98)`, incrociare con fatigue | SW | M |
| Sparsità temporale per-tick (frazione attivi/tick) | quant | Il MAX = #spike concorrenti/tick → dimensiona albero AC e throughput per chiudere il tick | `raster.mean(axis=-1)`, max/p95/p99 | SW | H |
| Numero TOTALE eventi/spike per inferenza | quant | Energia dinamica diretta (#eventi × SynOps × E_AC) | `raster.sum()` (già in energy_estimate), ×(r+5)=13, aggregato scenari | SW | H |
| Distribuzione ISI (inter-spike interval, in tick) | quant | ISI min = max freq istantanea → worst-case accumulazione back-to-back; forma Poisson vs periodica (RLE) | `np.diff(where(spike==1))` per neurone; confronto esponenziale/gamma | SW | M |
| Sincronia / correlazione tra neuroni | quant | Alta sincronia = picchi concorrenti (peggio per accumulatore condiviso, meglio per time-mux) | `corrcoef(raster.T)`; indice = varianza di active_per_tick | SW | L |
| Traccia potential ALIF hidden (32) nel tempo | quant | Accumulatore ad alta precisione centrale → int_bits (overflow) + frac_bits (leak >>3) | hook/monkey-patch su ALIFCell.forward, salva potential post-update/post-reset | SW | H |
| Traccia accumulatore intermedio rec_int (8) nel tempo | quant | Stato nascosto della cascata low-rank; dinamica propria (somma spike pesati po2 su fan-in 32) → bit del 2° stadio | hook tra i due linear della ricorrenza, per componente 8-dim | SW | H |
| Traccia potential LI (5) = raw pre-sigmoid | quant | Ingresso del decode → fixed-point datapath decode + LUT sigmoid; canali che saturano | hook su LICell.forward o `raw_out` in forward_step, per canale | SW | H |
| Traiettoria 5 param RAW pre-sigmoid (per canale) | quant | Se un canale vive in zona lineare/satura della sigmoid → Q-format per-canale | raw per canale + confronto `_decode_params`, saturazione | SW | M |
| Dinamica fatigue ALIF (32) nel tempo | quant | Max fatigue → registro fatica; equilibrio ~thresh_jump/(1-2^-3)≈0.57 al firing sostenuto | hook su fatigue, max/p99 | SW | M |
| Dinamica eff_thresh = base+fatigue | quant | Comparatore (potential≥eff_thresh) + range sommatore; soglie 1.5/0.5 esatte in binario | salvare eff_thresh nello stesso hook | SW | M |
| SynOps statico/dinamico per inferenza | quant | Attività SEMPRE-ON (input fc 128/step) vs EVENT-DRIVEN → clock-gating selettivo | separare i termini di energy_estimate, aggregare scenari | SW | H |
| Curva rate vs tempo dentro lo step (transiente 10 tick) | quant | Se attività concentrata early/late → early-exit o profilo potenza non uniforme | media su T,H per indice di tick | SW | L |
| Curva energia/potenza vs spike-rate | quant | Sensibilità potenza al firing-rate; guadagno in mW dei spike-rate regularizer | `capture_run+energy_estimate` su più scenari/checkpoint, plot E vs rate | SW | M |
| Occupazione/istogramma delay usati + jitter indotto | quant/quali | Se slot ring-buffer inutilizzati (accorciabile); come i delay spostano il timing spike | `bincount(delays)`; ablation max_delay ridotto, Δ raster/accuratezza | SW | M/L |
| Latenza in cicli per step (dagli eventi concorrenti) | quant | Se serve pipeline o basta datapath seriale (conteggio SW, cicli richiedono HDL) | conteggio worst-case eventi/tick (SW) → cicli via modello HDL | HDL | M |
| Validazione raster/range su board (HIL) | quant | Che il dimensionamento fixed-point regga sul silicio (overflow/timing reali) | stessi input su PYNQ-Z1, leggere registri via PS, confronto bit-a-bit | BOARD | L |

### 2.4 — Energia & switching

| Dato | q/ql | Cosa rivela | Metodo di estrazione | Feas. | Pri |
|---|---|---|---|---|---|
| Potenza media stimata a clock dato (mW @ Fclk) SNN vs ANN | quant | Ponte nJ/inf → mW: `P_dyn = E_per_inf · Fclk/cicli_per_inf`; margine budget ECU | estendere energy_estimate con `fclk_hz` e modello cicli/inf; sweep 100/150/200 MHz | SW | H |
| Op-model differenziato E_shift_add(po2) vs E_AC(FP32) vs E_MAC | quant | Vero divario energetico (oggi sottostimato ~10-30×): sinapsi po2 = INT add + shift | costanti separate `E_SHIFT_ADD_PO2≈0.03-0.1pJ`, ricalcolo; versione conservativa + po2-realistica | SW | H |
| Conteggio op/inferenza decomposto per componente (incl. op non-sinaptiche) | quant | Dove si spende: **energy_estimate oggi NON conta** leak-shift (32 ALIF+5 LI/tick), fatica (32 add+shift/tick), soft-reset (32 sub/tick), né la cascata low-rank come 2 stadi → completare il breakdown | `op_breakdown(model)`: fc 4×32, rec_V 8×32 (stadio 1), rec_U 32×8 (stadio 2), out 32×5, leak/fatica/reset ALIF, delay-line, ×n_ticks | SW | H |
| Rapporto energetico/termico SNN-sparso vs ANN-denso | quant | Doppio vantaggio: meno energia/op × meno op; DSP=0 vs decine → densità potenza (hotspot) | estendere energy_estimate con dsp_used_ann vs 0, densità = P/area | SW | H |
| Fattore di scala processo 45nm→28nm | quant | Correzione stime Horowitz al nodo reale (errore sistematico) | parametro `scale_process` (default 1.0=45nm), ~2-3× STIMA d'ordine | SW | M |
| Energia di memoria (accessi pesi BRAM + stati) | quant | Se compute-bound o memory-bound; footprint minuscolo (kb, pochi BRAM) | Σ byte pesi (800·bit/8) + stati/tick × E_mem/byte (STIMA) | SW | M |
| Energia-per-identificazione end-to-end (nJ/step closed-loop) | quant | Metrica di missione (nJ per km di platooning) | Σ E_snn per-step su traiettoria; normalizzare per step/durata/distanza (series['s']) | SW | M |
| Sensibilità energetica alle varianti (Stacked/MultiRate/WTA) | quant | Trade-off accuratezza/energia; variante più sparsa preferibile sotto vincolo potenza | energy_estimate su ciascuna variante + checkpoint | SW | L |
| Energia dinamica AC in versione po2 shift-add reale | quant | Costo per-SynOp reale < FP32 (0.9pJ = upper-bound sinaptico); conteggio SW, costo/add richiede sintesi | conteggio SynOps (SW) × costo/add da report_power | HDL | M |
| Potenza dinamica reale PL da switching annotata (report_power) | quant | Ground-truth: clock-tree, routing, glitch non visti dall'op-model | sintesi + SAIF/VCD da testbench closed-loop + report_power | HDL | H |
| Potenza statica/leakage device vs Tj (XPE/report_power) | quant | Leva (b): SNN sparsa (0 DSP) minimizza logica alimentata; leakage esponenziale con Tj | XPE con utilizzo post-sintesi, sweep Tj 25/50/85/100°C; confronto ANN | HDL | H |
| Misura reale mW su board (power-rail sensing) | quant | Ground-truth finale (Vccint, PS, clock-tree, I/O) | shunt/INA sui rail idle vs inferenza su PYNQ-Z1 | BOARD | M |

### 2.5 — Timing & latenza

| Dato | q/ql | Cosa rivela | Metodo di estrazione | Feas. | Pri |
|---|---|---|---|---|---|
| Conteggio op/step (cycle-model backbone) parametrico | quant | Input primario del WCET: op_ff, op_rec (2 stadi), op_out, op_neuron × n_ticks | `op_count(model)` da H, rank, max_delay, n_ticks (valori già in energy_estimate) | SW | H |
| Latenza sequenziale del ramo ricorrente a 2 stadi (V poi U) | quant | `rec_curr = U @ (V @ prev_spike)` è cascata: U non parte prima che V finisca → il ramo ricorrente ha profondità 2× (V-tree + U-tree) mentre fc/out sono a stadio singolo → il critical path del tick è dominato dalla cascata, non dalla dimensione bruta | nel dependency-graph di `wcet_cycles`, marcare la ricorrenza come 2 stadi seriali `lat(V)+lat(U)` invece di 1; ricalcolo WCET/tick | SW | M |
| WCET in cicli (cycle-accurate parametrico su parallelismo) | quant | Latenza inferenza in cicli indipendenti dal clock; 3 profili (serial/per-neurone/pipeline) | `wcet_cycles(model, latency_table, parallelism)` consuma op_count + dependency-graph; STIMA pre-sintesi | SW | H |
| Prova jitter strutturalmente nullo (WCET==BCET) | quali | Op-count invariante rispetto ai dati → jitter di calcolo = 0 (proprietà HRT chiave) | forward su spike-rate 1% vs 30% + edge case, assert #AC identico bit-per-bit; avvertenza event-driven | SW | H |
| Latenza end-to-end (cicli e µs) @100/200/300 MHz vs Dt=0.1s | quant | Margine real-time (~3 ordini) e headroom; 300 MHz = limite ottimistico | `wcet_cycles/F`, margine = Dt/latenza; tabella e curva | SW | H |
| Critical-path del decode (sigmoid×5 + IIDM sqrt/div/tanh) isolato | quant | Unico blocco con mul/div reali → collo Fmax e consumatore DSP | conteggio op non-po2 in `_decode_params`+`acc_iidm_accel`; latenze CORDIC/LUT tipiche | SW | H |
| WCET-jitter vs spike-rate (event-driven counterfactual) | quant | Trade-off energia-vs-determinismo se si salta spike-0 | distribuzione empirica total_spikes; snn_dynamic_ac worst vs best → jitter reintrodotto | SW | M |
| Overhead warm-up (ring-buffer max_delay) = cold-start una-tantum | quant | Ritardo algoritmico (**6·Dt = 0.6 s** riempimento buffer) distinto dalla latenza HW/step; escluso dal WCET per-step, incluso nel cold-start | warm-up = max_delay·Dt = 0.6 s; n_ticks già nel WCET_step | SW | M |
| WCET per varianti (Stacked/StackedSkip/MultiRate/WTA) | quant | Costo temporale di ogni scelta (Stacked ×n_hidden, WTA +1 fanout, MultiRate latenza invariata) | parametrizzare op_count su isinstance, leggere attributi | SW | M |
| Modello latenza end-to-end CAM→5param (PS+AXI+PL) | quant | Latenza percepita dal loop di controllo (non solo kernel PL) | WCET_PL + stime PS/AXI (deserial CAM su A9, AXI-lite) marcate STIMA | SW | M |
| Timing closure: Fmax reale + slack setup/hold | quant | Conferma/smentisce 100-200 MHz, localizza critical path (decode + cascata ricorrente candidati) | sintesi+impl Vivado, report STA (WNS/TNS, slack) | HDL | H |
| Utilizzo DSP48E1 su decode + Fmax core CORDIC/LUT | quant | DSP liberi (sinapsi 0 DSP) → decode chiude a target con pipeline; DSP48E1 -1 ~464 MHz | utilization/timing post-sintesi del blocco decode (HLS/IP CORDIC) | HDL | M |
| Jitter di calcolo misurato sull'inferenza reale | quant | Conferma sperimentale jitter ~0 (solo clock/PLL, non datapath) | AXI Timer in PL timbra inizio/fine, migliaia di campioni, std | BOARD | H |
| Latenza end-to-end misurata + jitter CDC PS-PL | quant | Latenza reale CAM→param + jitter clock-domain-crossing vs budget 100 ms | timestamping su board (PS arrivo CAM, PL fine inferenza) | BOARD | M |
| Margine real-time sotto carico PS concorrente | quant | Che il 99.9-percentile regga con PS occupato (stack V2X, OS jitter) | stress-test HIL con task concorrenti sul PS | BOARD | L |

### 2.6 — Risorse / DSE

| Dato | q/ql | Cosa rivela | Metodo di estrazione | Feas. | Pri |
|---|---|---|---|---|---|
| Tabella op-count per tipo di cella HW (AC vs shift-add) | quant | #celle AC (recV 256 stadio-1 + LI 160 = 416/tick) vs shift-add (fc 128 + recU 256 stadio-2 = 384/tick) → base resource model | ispezione statica forward, distinguendo i 2 stadi low-rank | SW | H |
| Accumulatore intermedio rec_int (8-dim) come registro fixed-point dedicato | quant | 8 accumulatori nascosti tra i due GEMV → FF extra + largh. da dimensionare; il ramo ricorrente non è 1 GEMV ma 2 in serie | conteggio + range da §2.2 | SW | H |
| Conteggio esatto pesi po2 + bit-width per matrice | quant | BRAM/ROM pesi e largh. barrel-shifter; Σ bit = 800·4 = 3200 | `PowerOf2Quantize` su ogni param, contare esponenti distinti | SW | H |
| Istogramma esponente po2 per matrice (utilizzo livelli) | quant | Se livelli inutilizzati → bit-width <4 → meno BRAM, shifter più piccolo; fc separato per il pre-scaling | `log2|w|` round+clamp, `np.unique` per matrice | SW | H |
| Sparsità pesi po2 (frazione azzerata) | quant | Sinapsi eliminabili dal fabric → restringe connettività cablata | `mask==0` per matrice | SW | H |
| Throughput richiesto e slack temporale | quant | 800 op/tick, 8000/step, 80.000 op/s vs ~100M op/s → slack ~1250× → serial-reuse | `op/s = 800·10·10 Hz` vs `f_clk/cicli_per_op` | SW | H |
| Modello parametrico area SNN (LUT/FF) da grafo | quant | Stima occupazione PRE-sintesi: ~28 LUT/neurone, ~39 LUT/PoT-MAC, ~9 FF/neurone | coefficienti letteratura × conteggi; range min(serial)-max(unroll), marcare STIMA | SW | H |
| Dimensionamento BRAM (pesi + stati + buffer) | quant | pesi 400B + stati ~125 word (+8 rec_int) + delay-map → 1-3 BRAM su 140 (<2%) | Σ da grafo, bit-width stati parametro | SW | H |
| Range/dynamic-range stati (per bit-width accumulatori) | quant | int_bits/frac_bits → FF e largh. sommatori (potential, rec_int, LI, fatigue) | forward hook, `min/max/quantile` per tensore (riusa calibrate_decode_offset) | SW | H |
| Curva DSE pipeline-vs-unroll (area/throughput/latenza) | quant | Pareto: P0 1 unit=800 cicli/tick (area min), P1 32 unit ~25 cicli/tick, P2 +ticks | `cicli=ceil(800/#unità)`, `area~#unità·LUT/cella`, tabulare {1,4,8,32,64,800} | SW | H |
| Costo risorse blocco IDM analitico on-fabric | quant | DSP se sintetizzato: 1 sqrt, 2-3 div, 1 tanh, 1 pow, ~10 add/mul → range DSP {0 CORDIC/PWL, ~10-20 mul diretti} | conteggio statico `acc_iidm_accel`, mappa su ricette Vivado | SW | H |
| Costo sigmoid decode + LUT per-bin | quant | 5 canali sigmoid + LUT per-|accel|-bin → ROM = n_bins·5·2 word; sigmoid PWL 0 DSP | leggere `results/decode_lut_*.json`, conteggio `_decode_params` | SW | M |
| Numero e larghezza accumulatori richiesti | quant | Full-unroll: 32 (potential) + 8 (rec_int) + 5 (LI) = 45 accumulatori di stato; largh. da dynamic-range → FF datapath | 1 accumulatore/destinazione/ramo; largh. = int_bits + guard | SW | M |
| Confronto risorse baseline vs varianti | quant | Costo-area topologico (full-matrix 1024 vs low-rank 512 = +512 celle) | op_count su ogni classe + resource model | SW | M |
| Costo ring-buffer delay + delay-mask | quant | x_buffer 24 word + delay-map; se delay_masks derivate on-the-fly → solo delays (384 bit) | da network.py; 2 impl (shift-register vs BRAM circolare) + compressione mask | SW | L |
| Bit-width minima pesi po2 senza degrado (leva area) | quant | Se <6 livelli → esponente 2 bit → 3 bit/peso → BRAM -25% (onesto solo con re-training) | sweep clamp esponente, **ri-allenare**, ri-eseguire identify, NRMSE vs bit | SW | M |
| Partizionamento PS/PL (ARM vs fabric) — decisione MUTUAMENTE ESCLUSIVA | quali | Se IDM sul PS → DSP fabric ≈ 0 TOTALE. **Scegliere UNA narrazione**: IDM-su-PL (usa DSP) OPPURE IDM-su-PS (0 DSP), non entrambe | stimare cicli ARM per acc_iidm_accel vs deadline 100 ms; il claim "220 DSP liberi" è un NON-bisogno, non un asset attivo | SW | M |
| Roofline: quale risorsa satura per prima | quali | Collo di scaling: nel reference 720-neuroni BRAM 81%; per noi LUT/routing (non DSP/BRAM) | estrapolare resource model su hidden 32→720 | SW | L |
| Costo barrel-shifter po2 vs moltiplicatore (cella) | quant | Risparmio DSP: ~39 LUT PoT vs ~46 uniform, BAC ~1.4× | micro-benchmark HDL 1 cella vs MAC 8×8, o numeri pubblicati | HDL | M |
| Fmax/timing e slack del datapath | quant | Critical path (cascata ricorrente V→U o divisore IDM); add-tree log2(800)~10 livelli | STA post-sintesi | HDL | M |

### 2.7 — Affidabilità / SEU (ISO 26262)

| Dato | q/ql | Cosa rivela | Metodo di estrazione | Feas. | Pri |
|---|---|---|---|---|---|
| Sensitivity map per-peso (single-bit-flip exhaustive) | quant | Pesi single-point-of-failure → ECC/TMR selettiva mirata | loop: ogni peso × ogni bit, corrompi tensore po2, `eval_safety`, Δ vs baseline. 800×4×(20 driver×9 scenari) | SW | H |
| Ranking di criticità per-bit (segno>exp-MSB>exp-mid>exp-LSB) | quant | Bit-budget da proteggere: se 90% rischio in 2 bit su 4, ECC limitata a quelli | aggregare sensitivity map per posizione-bit, Δ-collision medio/p95 | SW | H |
| Criticità SEU della CRAM del datapath serial-reuse (shifter condiviso) | quant | In serial-reuse UN barrel-shifter è time-mux su MOLTI pesi: un SEU sulla sua CRAM corrompe lo shift di TUTTI i pesi che lo attraversano → molto più critico di un flip su 1 peso. Rivela la tensione area-vs-robustezza (più serializzo → ogni unità è single-point-of-failure amplificato) | modello SW: per fattore di serializzazione {1,8,32 unità}, mappare quali pesi condividono ciascuna unità; simulare corruzione SIMULTANEA di tutti i pesi che passano per un'unità (1 flip logico → N pesi con shift errato), misurare collision_rate/brake_margin con eval_safety; confronto con la map per-singolo-peso | SW | H |
| Distribuzione shift per-parametro [v0..b] sotto SEU | quant | Quale param più fragile (b/a → sqrt(ab)/frenata → sicurezza) | Monte Carlo: peso+bit uniformi, `identify` vs baseline per canale | SW | H |
| Curva degrado safety vs #flip (multi-flip MC) | quant | Graceful vs cliff: a quanti SEU accumulati il controllo è insicuro → periodo scrubbing | k=1,2,4,8,16; M~500 realizzazioni; `eval_safety` (pattern breakdown_curve) | SW | H |
| Curva degrado NRMSE per-canale vs #flip | quant | Separa degrado identificazione da controllo | come sopra, metrica NRMSE (accumulatori train.py) | SW | H |
| Confronto pesi-hidden vs pesi-readout (out_fc) | quant | Ipotesi: 160 pesi out_fc (1:1 su canale) >> critici dei 640 hidden → TMR su solo 20% | segmentare sensitivity map per layer | SW | H |
| Failure mode di cold-start (primi max_delay step su buffer parzialmente-zero) | quant | Nei primi 6 step (0.6 s) dopo power-on/reset_state, x_buffer contiene zeri iniziali: la rete produce 5 param su input storici incompleti → param fuori regime a power-on. Failure mode di safety NON coperto da SEU né timing | forward_step su traiettoria SENZA warm-up (subito dopo reset_state) vs stessa traiettoria a regime (buffer pre-riempito); max deviazione param/a_ego, se brake_margin<0 nel transitorio | SW | M |
| Fault persistente (peso BRAM) vs transiente (registro) | quant | Vantaggio SNN: stati self-healing (leak >>3, soft-reset) vs peso persistente | (a) corrompi registro a tick t, durata effetto; (b) corrompi peso intera traiettoria | SW | M |
| Sensibilità param ALIF appresi (base_threshold, thresh_jump) | quant | I 64 param NON-po2: SEU cambia eccitabilità → se proteggerli, codifica fixed | bit-flip su rappresentazione Qm.n, `eval_safety` | SW | M |
| Sensibilità delay-mask e delays interi | quant | SEU su delay cambia QUANDO un peso agisce (jitter assonale) | flip su `delays`, ri-eseguire forward/eval_safety | SW | L |
| Frazione bit critici sul totale (essential-bits model) | quant | % dei 3200 bit il cui flip singolo → collisione o brake_margin<0 → input al FIT effettivo | dalla map exhaustive, contare bit con Δ-collision>0 o margin<0 | SW | H |
| Worst-case brake_margin_min sotto SEU (safety envelope) | quant | Caso peggiore fisico da UN SEU (metri di inevitabilità) → argomento ASIL | `min` su tutta la map di `safety_metrics['brake_margin_min']` corrotto | SW | H |
| Degrado po2 vs float32 (ruolo quant su robustezza SEU) | quali | po2 riduce bit sensibili/peso (4 vs 32) ma amplifica conseguenza/bit (×2): netto favorevole? | ripetere injection con `PO2_ENABLED=0` (fp32), confronto vs po2 | SW | M |
| Bit di memoria del modello su BRAM (attack surface) | quant | 3200 bit sinaptici + ALIF + delays → input FIT; <1 KB → 1 BRAM, superficie minuscola | conteggio diretto | SW | M |
| FIT-rate stimato (BRAM/CRAM del Zynq-7020) | quant | ~22 FIT/Mbit atmosferici × 3200 bit ≈ 7e-5 FIT sui pesi grezzi: rischio bassissimo; **budget totale dominato dalla CRAM** che configura la logica (specie le poche unità shift-add condivise in serial-reuse) | conteggio bit-critici pesi × FIT/Mb + bit-critici CRAM del datapath × FIT/Mb da datasheet | SW | H |
| Protocollo Monte Carlo del bit-flip experiment | quali | Metodologia riproducibile (exhaustive single-bit + MC multi-flip + CRAM-shared + Wilson/CI) | documento + wrapper `eval_safety(rich, n_seeds)`/breakdown_curve | SW | H |
| Meccanismo plausibilità fail-safe a valle | quali | Clamp bound (sigmoid) + rate-limiter + monitor IDM (RSS/brake_margin) → SEU rilevabile/degradabile → alza DC senza TMR full | guardiano `brake_margin>0 && param entro bound`; quanti fault neutralizzati | SW | H |
| Classificazione ASIL + target SPFM/LFM/DC | quali | ACC longitudinale ASIL B-C (fino a D); SPFM ≥90/97/99% per B/C/D | HARA su scenari (impact_dv=Severity, collision_rate=esposizione) | SW | H |
| Overhead area TMR sui pesi/datapath | quant | Se TMR (+200-300%) sta nei 53200 LUT / 140 BRAM; TMR full vs selettivo (priorità shifter condivisi) | sintesi 2 varianti (baseline vs TMR+voter), utilization | HDL | H |
| Overhead BRAM-ECC + latenza correzione | quant | ECC SECDED nativo 7-series (1 bit correzione, 2 rilevazione) → elimina single-bit-flip persistenti sui pesi quasi gratis | abilitare ECC in RAMB36E1, BRAM extra + latenza | HDL | H |
| Intervallo di scrubbing necessario vs curva multi-flip | quant | Periodo max scrubbing (SEM IP) che tiene il rischio sotto ASIL (specie CRAM) | FIT × k-critico dalla curva multi-flip | SW | M |
| Cross-section SEU reale BRAM/CRAM sintetizzato | quant | Sezione d'urto misurata (cm²/bit) sotto neutroni → FIT reale | beam-test (LANSCE/TRIUMF/ChipIR) + SEM IP readback | BOARD | M |
| Efficacia reale scrubbing/ECC su board | quant | Tasso di correzione di SEU iniettati → baseline recuperata | SEM IP fault-injection su PYNQ-Z1, o PS riscrive pesi + CRC | BOARD | L |

### 2.8 — I/O & HIL (bus automotive)

| Dato | q/ql | Cosa rivela | Metodo di estrazione | Feas. | Pri |
|---|---|---|---|---|---|
| Soglia fisica AoI_max(s, dv, b_leader) legata a brake_margin | quant | Età MASSIMA tollerabile della CAM oltre cui, data la cinematica (gap s, chiusura dv, decel max leader), il controllo è non-sicuro INDIPENDENTEMENTE dalla rete: vero requisito hard di timing end-to-end che il bus DEVE garantire. Trasforma l'I/O da "misuriamo l'AoI" a "il bus DEVE consegnare entro AoI_max o insicuro by design" | per griglia di stati (s,v,dv) dai dataset, propagare cinematica worst-case (leader frena a b_max) durante k step di CAM stantia (hold-last), calcolare brake_margin_min al variare di k, trovare k* dove passa <0; AoI_max=k*·DT. Riusa safety_metrics + logica hold-last-CAM di _channel_obs → superficie AoI_max(scenario) | SW | H |
| Latenza end-to-end (glass-to-comando) in ms e step DT | quant | Se la deadline hard 100 ms è rispettata e con quale margine | budget = latency+jitter (`_channel_obs`) + 10 tick + AoI; serie `aoi_series` | SW | H |
| Age-of-Information distribuzione completa | quant | Quanto spesso il SNN gira su dati stantii (p50/p95/p99, coda) | estendere `simulate` per l'intera aoi_series, istogramma, incrociare collision_rate | SW | H |
| Occupazione coda RX + probabilità overflow su burst | quant | Dimensionamento minimo buffer FIFO + rischio overflow (Gilbert-Elliott) | sostituire buffer illimitato `buf` con coda profondità finita D, contare drop; sweep D | SW | H |
| Curva collision_rate / min_TTC(p5) vs PDR e latenza (knee) | quant | Punto di ginocchio (graceful vs catastrofico), PDR/latenza minimo tollerabile | GIÀ in `v2x_robustness_sweep`; estendere griglia + jitter + Gilbert | SW | H |
| Failure mode di cold-start I/O (primi 6 step post-power-on) | quant | Legato a §2.7: nei primi 0.6 s il ring-buffer è parzialmente-zero → i param possono essere fuori regime prima che arrivino/riempiano le CAM | closed_loop_eval con/senza pre-roll del buffer, deviazione param nei primi 6 step | SW | M |
| Sensibilità al jitter sub-DT (CAM in ritardo di frazione di step) | quant | Effetto jitter <100 ms su stabilità param e closed-loop | jitter continuo in `_channel_obs`, `param_chattering` + collision_rate | SW | M |
| Throughput I/O richiesto (byte/ciclo, frame/s) | quant | Ogni bus sovradimensionato (4 in, 5 out a 10 Hz) → collo non è la banda | calcolo diretto vs CAN-FD 5Mbit/s/64B, GEM 1Gbps | SW | M |
| Saturazione bus condiviso: density→CBR→PDR non lineare (soglia DCC) | quant | Robustezza in alta densità (ingorgo) | raffinare `cbr_to_pdr` (oggi lineare) con curva ETSI DCC/SAE J2945 a soglia | SW | M |
| Simulazione multi-rate HIL: plant 1 kHz vs controller 10 Hz | quant | Effetto ZOH dei param sul comportamento fine del veicolo | wrapper scheduling: plant `_plant_step` a 1 ms, `forward_step` ogni 100 ms | SW | M |
| Ritardo di trasporto 5 param verso l'ECU (1 ciclo bus) | quant | Effetto latenza bus (distinto dal lag attuatore fisico) su safety/comfort | ritardo di N step tra `forward_step` e uso in `acc_iidm_accel` | SW | M |
| Robustezza decode ai param stantii (chattering ECU) | quant | Quanto I/O ritardato/perso induce comandi nervosi (energia >0.5 Hz) | `param_chattering` su tutte le combo PDR/latency/jitter/Gilbert | SW | M |
| Sequenza byte esatta sul bus + mappa serializzazione | quali | Contratto I/O: layout Qm.n dei 4 input e 5 param (scala, segno, ordine, CRC) | da bound fisici + largh. fixed-point (`quantize.py`), tabella | SW | M |
| WCET inferenza SNN in cicli (10 tick, 4→32→5) | quant | Margine reale sulla deadline 100 ms | conteggio op (SW) → cicli via scheduling HDL (pipeline/II) | HDL | H |
| Latenza deserializzatore CAM (ASN.1 UPER) in cicli/µs | quant | Tempo decode CAM 300-400B nei 4 campi | HDL (PL) o profiling PS ARM reale (BOARD) | HDL | M |
| Latenza/throughput GEM→AXI-DMA→DDR→PL in cicli | quant | Costo CDC PS/PL + FIFO minima (tetto 81k frame/s) | modellabile dopo interconnessione AXI sintetizzata | HDL | M |
| Jitter CDC PS(667 MHz)/PL(100-200 MHz) + FIFO CDC | quant | Jitter attraversamento domini + FIFO minima per non perdere sample | schema CDC + sintesi, verifica STA | HDL | L |
| Timing fisico CAN-FD (frame time @5Mbit/s, jitter arbitraggio) | quant | Ritardo consegna reale all'ECU + jitter sotto carico | analyzer CAN (Vector/Kvaser) su bus fisico | BOARD | M |
| Timing fisico Automotive-Ethernet (100/1000BASE-T1) | quant | Latenza/jitter reale su PHY BASE-T1 | tap/analyzer su HW reale | BOARD | L |
| Chiusura loop HIL reale 1 kHz (dSPACE/Speedgoat) | quant | Latenza glass-to-comando reale, stabilità, sicurezza sotto canale degradato | board PYNQ-Z1 + bitstream + rig HIL | BOARD | H |
| Determinismo end-to-end: WCET(catena) < 100 ms sempre | quant | Garanzia real-time certificata (worst case jitter + riassemblaggio) | STA/WCET (HDL) + misura (BOARD) | BOARD | H |
| Contratto I/O + integrazione ECU (segnali, unità, watchdog) | quali | Interfaccia powertrain: quali param, scala, watchdog/fallback (hold-last / degrado sicuro) | documento da bound fisici + logica hold-last; validazione BOARD | SW | M |

### 2.9 — Termica

| Dato | q/ql | Cosa rivela | Metodo di estrazione | Feas. | Pri |
|---|---|---|---|---|---|
| Derating termico Tj→Fmax (headroom clock a caldo) | quant | Clock-headroom a Tj automotive (85-100°C) vs 100-200 MHz nominali | STIMA: modello `delay(Tj)` (~0.85× a 40°C → 1× a ~100°C) su Fmax; VERIFICA: STA a corner temperatura | HDL | M |
| Budget termico ECU raffreddamento passivo (Rth, Tj max) | quant | Se ECU senza ventola regge (Tj<85/100°C, Tamb fino 85-105°C); margine SNN vs ANN | `Tj = Tamb + P·Rth_ja`, loop autoconsistente P_static(Tj); confronto SNN/ANN | HDL | M |
| Distribuzione hotspot SNN-sparso vs ANN-denso | quali | ANN concentra commutazione nei DSP (hotspot); SNN po2 distribuisce su LUT, 0 DSP | argomentazione da op-breakdown (DSP=0 vs >0) + thermal map post-impl | HDL | L |
| Temperatura giunzione reale via XADC on-die | quant | Tj effettiva durante funzionamento continuo → valida modello termico + loop leakage | canale temperatura XADC via PYNQ (PS ARM) a vari Tamb | BOARD | L |

---

## 3. Gap vs evaluate attuale + struttura proposta del FPGA-evaluate a Tier

### 3.1 — Gap sintetico

L'evaluate attuale (Tier 0-5) copre: identificazione, closed-loop plant+canale V2X, safety SSM, string stability, identificabilità, reachability, e **quantizzazione dell'OUTPUT** (Tier 5) + **energia da spike-rate**. NON copre nessuna delle 6 dimensioni FPGA a livello di **peso/stato/silicio**: né quant dei pesi con QAT-vs-PTQ, né range/overflow degli stati fixed-point (incluso `rec_int`), né resource model, né latency-model in cicli con la cascata ricorrente a 2 stadi, né SEU/ISO 26262 (pesi + CRAM condivisa), né potenza mW/termica, né i requisiti hard AoI_max/cold-start.

La buona notizia: **~80% degli esperimenti FPGA rilevanti è `software_now`** perché la codifica po2 è deterministica, il forward PyTorch è strumentabile con hook, e l'infrastruttura di conseguenza (safety_metrics, eval_safety, breakdown_curve, QuantParamModel, param_chattering, energy_estimate) esiste già e accetta modelli corrotti/quantizzati. **Eccezione da tenere presente:** la curva accuratezza/sicurezza-vs-bit-width ONESTA (F1.2) richiede un mini-sweep di **re-training QAT** (ore-giorni GPU), quindi F1 NON è cheap come F2/F3.

### 3.2 — Struttura proposta a Tier (F1–F6), separati per feasibility

Propongo di estendere il sistema Tier esistente con un blocco **Tier-FPGA** diviso in tre fasi nette per feasibility.

#### FASE A — Pre-silicio (tutto `software_now`, nessun HDL/board)

**F1 — Quantizzazione dei PESI & QAT-vs-PTQ** *(dipende da: mini-sweep di re-training per la curva bit-width — NON a costo zero)*
- F1.1 QAT-vs-PTQ gap (toggle `PO2_ENABLED`; float ideale, PTQ controfattuale, QAT nominale) → MAE per-param + collisioni.
- F1.2 Curva accuratezza/sicurezza vs bit-width / range esponente — **con re-training QAT a ogni bit-width** (3/4/5/6), non solo ri-clamp del checkpoint a 4 bit.
- F1.3 Distribuzione errore quant per-matrice + istogramma po2 SEPARATO fc(post-scaling)/rec/out + sparsità mask.
- F1.4 Mappatura errore-peso → errore per-parametro fisico [v0,T,s0,a,b].
- F1.5 Jacobiano IIDM `∂a/∂param` (autograd su `acc_iidm_accel`).

**F2 — Range fixed-point degli STATI & Qm.n minimo** *(dipende da: hook infrastruttura)*
- F2.1 Istogrammi/range di potential ALIF, corrente sinaptica, **rec_int (8-dim)**, accumulo LI, fatigue/eff_thresh, raw pre-sigmoid (forward hook su ALIFCell/LICell/HiddenLayer).
- F2.2 Qm.n minimo (int_bits/frac_bits) via sweep `fake_quant` sugli stati loggati (bit-true replay) + verifica leak-underflow (frac_bits min che tiene il leak vivo).
- F2.3 Simulazione bit-true del datapath (golden model NumPy con rounding intermedio, cascata low-rank a 2 stadi).
- F2.4 Errore sigmoid+scaling `_decode_params` in fixed-point (LUT N-entry) + verifica delay-mask×pre-scaling (saturazione clamp fc).
- F2.5 Bit-exactness comparatore spike + sensibilità raster a quant stati (estende Tier 5 agli interni).

**F3 — Latency-model & determinismo** *(dipende da: F backbone op-count)*
- F3.1 `op_count(model)` parametrico (backbone da energy_estimate) decomposto per componente, **incluse le op non-sinaptiche** (leak/fatica/reset) e i **2 stadi** della ricorrenza.
- F3.2 `wcet_cycles(model, latency_table, parallelism)` (serial / per-neurone / pipeline) col **dependency-graph a cascata ricorrente** (V→U seriale).
- F3.3 Prova jitter strutturalmente nullo (op-count invariante rispetto ai dati).
- F3.4 Latenza end-to-end @100/200/300 MHz vs Dt=0.1s; critical path decode isolato; warm-up cold-start (0.6 s) escluso dal WCET per-step.
- F3.5 Curva DSE pipeline-vs-unroll (area/throughput/latenza), modello parametrico area LUT/FF.

**F4 — SEU / affidabilità pre-silicio** *(dipende da: F1 per la codifica po2→bit)*
- F4.1 Sensitivity map per-peso exhaustive (800×4 bit) + ranking per-bit (segno>exp).
- F4.2 **Criticità SEU CRAM del datapath serial-reuse** (corruzione simultanea dei pesi che condividono un'unità shift-add) — trade-off area-vs-robustezza.
- F4.3 Curve safety/NRMSE vs #flip (Monte Carlo multi-flip, pattern breakdown_curve).
- F4.4 Confronto criticità hidden vs out_fc; frazione bit critici; worst-case brake_margin; **failure-mode cold-start** (param fuori regime nei primi 6 step).
- F4.5 FIT-rate stimato (bit critici pesi + CRAM × FIT/Mb datasheet) + intervallo scrubbing; meccanismo plausibilità fail-safe (guardiano bound+rate-limiter+monitor IDM) + HARA/ASIL.

**F5 — Energia & I/O pre-silicio** *(dipende da: F3 op-count, canale V2X esistente)*
- F5.1 mW@clock (ponte nJ→mW) + op-model differenziato E_shift_add vs E_AC vs E_MAC + **conteggio op non-sinaptiche** (leak/fatica/reset/cascata) prima assenti.
- F5.2 Rapporto energetico/termico SNN-sparso vs ANN-denso (DSP=0 vs decine); scala 45→28nm.
- F5.3 **Soglia AoI_max fisica** (requisito bus hard) + coda RX profondità finita + overflow su burst; AoI distribuzione completa; latenza end-to-end (budget).
- F5.4 Curve robustezza estese (PDR × latenza × jitter × Gilbert); saturazione DCC a soglia; ritardo trasporto ECU.
- F5.5 Simulazione multi-rate HIL (plant 1 kHz / controller 10 Hz, ZOH param) + cold-start I/O.

#### FASE B — Sintesi HDL (`needs_hdl_synthesis`)

**F6-HDL — Silicio pre-board**
- Resource utilization reale (LUT/FF/DSP/BRAM) baseline vs varianti, con/senza IDM on-fabric (decisione PS/PL già fissata in F2/DSE).
- Timing closure / Fmax / slack (STA); DSP48E1 del decode; critical path (decode + cascata ricorrente).
- Potenza dinamica reale (report_power + SAIF) e statica/leakage (XPE vs Tj).
- Overhead TMR (2 varianti, priorità shifter condivisi) + BRAM-ECC + latenza correzione.
- Derating termico Tj→Fmax (STA a corner) + budget passivo (Rth, autoconsistenza leakage).
- Co-simulazione bit-esatta software golden vs RTL.

#### FASE C — Board / HIL (`needs_board_hil`)

**F6-BOARD — Validazione finale**
- Jitter di calcolo misurato (AXI Timer) → conferma jitter ~0.
- Latenza end-to-end CAM→param misurata + jitter CDC; margine sotto carico PS concorrente.
- Misura reale mW (power-rail) + Tj (XADC); overflow reale accumulatori.
- Cross-section SEU (beam-test) + efficacia scrubbing/ECC.
- Chiusura loop HIL 1 kHz (dSPACE/Speedgoat) su bus reale (CAN-FD/Ethernet); determinismo end-to-end certificato.

### 3.3 — Ordine consigliato

1. **F2 (range stati)** per primo: è la fondazione — fissa il Qm.n (incluso `rec_int` e leak-underflow) che tutti gli altri Tier assumono. Riusa `fake_quant`/hook esistenti, costo basso.
2. **F1 (quant pesi)** in parallelo per le parti cheap (F1.1/F1.3/F1.4/F1.5: gap PTQ, istogrammi, jacobiano), MA schedulare a parte il mini-sweep di **re-training** di F1.2 (costoso, GPU Azure): la curva bit-width-vs-safety onesta non è post-processing.
3. **F3 (latency-model)** subito dopo: dipende solo dal backbone op-count (già in energy_estimate) esteso alle op non-sinaptiche e alla cascata a 2 stadi; produce WCET/determinismo, argomento forte e a basso costo.
4. **F4 (SEU)** in parallelo a F3: dipende da F1 (codifica po2→bit) ma non da F3; riusa `eval_safety`/`breakdown_curve`; include la criticità CRAM (che dipende dal fattore di serializzazione scelto in F3/DSE).
5. **F5 (energia + I/O)** dopo F3 (per op-count → mW) e sfruttando il canale V2X già ricco; deriva la soglia AoI_max come requisito hard.
6. **FASE B (HDL)** solo dopo che F2-F5 hanno fissato Qm.n, parallelismo (che determina la criticità CRAM), bit critici e budget di potenza (evita ri-sintesi).
7. **FASE C (board/HIL)** ultima, come validazione dei modelli pre-silicio.

---

## 4. Raccomandazioni & prossimi passi concreti

### 4.1 — Cosa implementare per primo (2 moduli software)

1. **`utils/state_profiler.py`** (fondazione di F2): un set unificato di forward-hook / monkey-patch su `ALIFCell.forward`, `LICell.forward`, `HiddenLayer_ALIF.forward` che logga per-tick i tensori GIÀ calcolati (`potential`, `fatigue`, `eff_thresh`, `current`, `rec_curr`, **`rec_int`** — l'accumulatore intermedio low-rank —, `raw_out`, spike). Da questi raster + range, tutto il resto (Qm.n minimo, leak-underflow, istogrammi, ISI, energia AC, neuroni morti/saturi) è post-processing NumPy. È il collo di bottiglia che sblocca F2, F3, F4, F5. **Nota:** `rec_int` va catturato tra i due `linear` della ricorrenza, non alla fine.

2. **`utils/weight_profiler.py`** (fondazione di F1/F4): carica un checkpoint, applica `po2_quantize`, produce istogramma esponenti **separato per matrice** (fc post-scaling sqrt(6) vs rec/out raw), sparsità mask, bit-width entropico, raggio spettrale/norma U@V, distribuzione delay, footprint bit, verifica ridondanza `delay_masks==(delays==d)`, e la **decodifica peso→4 bit** (segno + esponente offset) necessaria per il bit-flip di F4. **Gestire ENTRAMBI i naming** del checkpoint (checkpoint PIATTO `layer_out.weight`/`layer_hidden.base_threshold` vs live NESTED `layer_out.fc_weight`/`layer_hidden.cell.base_threshold`) per evitare KeyError / statistiche silenziosamente vuote. **Riusare l'adattatore di rimappatura già esistente nel codice di load** (il checkpoint è uno state_dict piatto caricato via `load_state_dict` con un adattatore) invece di reimplementarlo.

Un terzo modulo, **`utils/latency_model.py`** (`op_count` + `wcet_cycles`), estende `energy_estimate` separando i conteggi grezzi dalla monetizzazione in pJ, contabilizza le op non-sinaptiche (leak/fatica/reset) e modella la **cascata ricorrente V→U come 2 stadi seriali**. Costo quasi-zero.

### 4.2 — Quale champion usare

Il **baseline 4→32→5** (`checkpoints/CAP_h32_r8/best_model.pt`, del branch `EventProp_Study`). **Verificati in questa sessione**: 800 pesi sinaptici (shape 128+256+256+160), 864 param apprendibili (base_threshold 32 + thresh_jump 32), naming CHECKPOINT piatto (`layer_hidden.base_threshold`, `layer_hidden.thresh_jump`, `layer_hidden.delays`, `layer_hidden.delay_masks (6,32,4)`, `layer_out.weight (5,32)`) vs LIVE nested. **DA RICONFERMARE al primo run di `weight_profiler`** (NON ancora ri-verificati numericamente): ρ(U@V)_po2≈0.16 / _float≈0.14, ‖U@V‖₂≈0.84, istogramma esponenti (2^-4≈30%…zero≈21%), soglie (bt μ≈1.502, tj≈0.5 costante) — trattarli come stime preliminari, non fatti pubblicabili. Le varianti (Stacked, StackedSkip, MultiRate, WTA, full-matrix) entrano solo nelle voci di confronto DSE/energia, non come modello primario.

### 4.3 — Quali figure/CSV produrre (deliverable minimi per la Fase A)

- **CSV** `weight_stats.csv`: per matrice (fc/rec_U/rec_V/out) → n_pesi, istogramma esponenti (fc separato post-scaling), %zero, bit entropia, mean/max errore quant, ρ e ‖·‖₂ per la ricorrenza, verifica ridondanza delay_masks.
- **CSV** `state_ranges.csv`: per stato (potential ALIF, **rec_int**, LI, fatigue, eff_thresh, current, rec_curr, raw pre-sigmoid) → min/max/p0.1/p99.9/std → int_bits/frac_bits proposti + frac_bits min anti-leak-underflow.
- **Figura** `qat_vs_ptq.png`: MAE per-param e collision_rate per {float, QAT-po2, PTQ} + curva accuratezza/sicurezza vs bit-width (con marker "re-training richiesto").
- **Figura** `seu_sensitivity.png`: heatmap sensitivity per-peso × posizione-bit + curva collision_rate vs #flip + istogramma bit critici; tabella hidden-vs-out_fc; **curva collision_rate vs fattore di serializzazione** (criticità CRAM condivisa).
- **Figura** `latency_dse.png`: Pareto area (LUT stimati) vs latenza (cicli/step) per {serial, 8-unit, 32-unit, full-unroll}, con la linea del budget 100 ms @100/200 MHz e il critical path della cascata ricorrente evidenziato.
- **CSV** `energy_power.csv`: E_snn/E_ann (nJ), mW@100/150/200 MHz, energy_advantage_x, DSP_snn=0 vs DSP_ann, con op-model conservativo (E_AC 0.9pJ) e po2-realistico affiancati, **op non-sinaptiche incluse**.
- **CSV** `io_hil.csv`: **AoI_max(scenario) fisico**, AoI osservato (p50/p95/p99), collision_rate vs PDR×latenza×jitter, occupazione coda / drop-rate vs profondità buffer, deviazione param cold-start.
- **Documento** `FMEDA_ASIL.md`: HARA sugli scenari (cut_in/panic_stop), ASIL proposto (B-C), target SPFM/LFM, ruolo del safety-monitor implicito (clamp bound) e del fail-safe a valle, criticità CRAM del datapath condiviso, failure-mode cold-start.

### 4.4 — Principi trasversali da rispettare

- **Non presentare stime come misure.** Ogni numero non-misurato va etichettato "STIMA" con la fonte (Horowitz 45nm, resource regression ese.washu.edu, FIT/Mb datasheet Zynq-7000). I valori spettrali/istogramma po2 del champion sono PRELIMINARI finché non riconfermati da `weight_profiler`.
- **Mantenere sempre il mapping sul design reale** (po2 shift-add, spike AC, leak bit-shift, cascata low-rank a 2 stadi, 4→32→5, ACC-IIDM): ogni voce del catalogo è ancorata a un file/riga del repo.
- **Decidere UNA volta il partizionamento IDM.** "IDM su PL con DSP" e "IDM su PS con 0 DSP" sono narrazioni MUTUAMENTE ESCLUSIVE: il claim "220 DSP liberi" è un NON-bisogno (nessun DSP usato), non un asset attivo — non tenere entrambe le storie.
- **Evitare le trappole:** non usare il DPU (non supporta il 7020), non fare PTQ-sopra-QAT ingenuo, non spacciare il ri-clamp del checkpoint per la curva bit-width onesta (serve re-training), non quantizzare solo l'output ignorando gli stati (incluso rec_int), non applicare TMR pieno, non ignorare la criticità CRAM del serial-reuse, non spacciare il PYNQ-Z1 commercial per production-ready, non assumere export SNN→FPGA push-button (le primitive custom vanno scritte a mano).
- **Sfruttare lo slack real-time** (utilizzo ~0,08%) come leva progettuale MA con consapevolezza del suo costo: il design ottimo è serial-reuse aggressivo (minimizza area, libera fabric), che però AMPLIFICA la criticità SEU della CRAM (poche unità condivise = ogni SEU corrompe molti pesi) — trade-off da bilanciare, non free lunch.

---

### Appendice — Numeri chiave di ancoraggio (con fonte)

| Grandezza | Valore | Fonte |
|---|---|---|
| Pesi po2: livelli distinti | 13 (`{±2^-4..±2^1}∪{0}`) = ~4 bit | core/hardware.py PowerOf2Quantize (clamp [-4,+1], mask 2^-5) |
| Op sinaptiche/tick | 800 (FF 128 + recV 256 AC [stadio 1] + recU 256 [stadio 2] + LI 160 AC) | conteggio grafo forward_step |
| Ricorrenza low-rank | cascata 2 stadi: `rec_int = V@prev_spike` (8-dim AC) → `rec_curr = U@rec_int` (shift-add); seriale, 512 pesi vs 1024 full-matrix | core/network.py HiddenLayer_ALIF |
| Op/step, op/s | 8.000 /step; 80.000 /s (×10 tick ×10 Hz) | grafo + config |
| ANN-equiv MAC/step | 800 (4H + 2Hr + 5H = 128+512+160) | snn_showcase.py energy_estimate |
| Op non-sinaptiche (NON in energy_estimate) | leak-shift 32 ALIF+5 LI/tick, fatica 32 add+shift/tick, soft-reset 32 sub/tick | core/network.py ALIFCell/LICell |
| Energia (STIMA Horowitz 45nm) | E_MAC=4.6 pJ, E_AC=0.9 pJ; INT add ~0.03-0.1 pJ | Horowitz ISSCC 2014 |
| Footprint pesi | 800×4 = 3.200 bit ≈ 0,4 KB → <1 BRAM/36Kb | conteggio |
| Param apprendibili | 864 (800 pesi + 32 base_threshold + 32 thresh_jump) | VERIFICATO shape checkpoint CAP_h32_r8 |
| ρ(U@V) po2 / float | ≈0.16 / ≈0.14; ‖U@V‖₂≈0.84 | checkpoint CAP_h32_r8 (PRELIMINARE, da riconfermare) |
| Istogramma esponenti | 2^-4≈30%, 2^-3≈24.6%, 2^-2≈12.2%, 2^-1≈7%, 2^0≈4.8%, 2^1≈0.2%, zero≈21.1% | checkpoint CAP_h32_r8 (PRELIMINARE, aggregato mescola fc post-scaling e rec/out raw) |
| Pre-scaling fc_weight | `fc_weight.mul_(sqrt(max_delay)=2.449)` PRIMA della po2 (FIX-BUG-4); NON tocca rec_U/rec_V/out | core/network.py |
| Soglie | base_threshold μ≈1.502 σ≈0.11; thresh_jump μ≈0.5 σ≈6e-8 (costante) | checkpoint CAP_h32_r8 (PRELIMINARE) |
| Warm-up ring-buffer | max_delay=6 × Dt = **0.6 s** (deque per-step; l'implementazione vince sulla docstring 0.06 s, errata) | core/network.py x_buffer=deque(maxlen=6) |
| Range param fisici | v0[8,45], T[0.5,2.5], s0[1,5], a[0.3,2.5], b[0.5,3] | network.py _PARAM_BOUNDS |
| Device Zynq-7020 | 53.200 LUT, 106.400 FF, 220 DSP48E1, 140 BRAM/36Kb (~4,9 Mb) | DS187 AMD/Xilinx |
| Reference SNN 720-neuroni Zynq-7020 | 15.042 LUT (28%), 16.003 FF (15%), 113 BRAM (81%), 4 DSP (2%) | ese.washu.edu |
| Spiker+ (baseline SNN-FPGA) | MNIST: 7.612 logic cell, 18 BRAM, 180 mW, 780 µs/img | arXiv 2401.01141 |
| PoT MAC 4b×8b | ~39 LUT vs ~46 uniform, DSP eliminati; speedup 2.1-4.1× su XC7Z020 | arXiv 2203.05025; Sensors 22:6618 |
| SEU Zynq-7000 (28nm) | cross-section ~9.2e-16 cm²/bit; ~12 FIT/Mb (heavy-ion), ~22 FIT/Mbit (neutron sea-level) | Electronics 12:2057, 2023; UG116 |
| CAM / CAN-FD | CAM 10 Hz (100 ms), ~300-400 B; CAN-FD 5 Mbit/s, 64 B/frame | ETSI EN 302 637-2; CiA CAN-FD |
| HIL rig | dSPACE SCALEXIO 1 kHz; rapporto plant/controller 100:1 | dSPACE SCALEXIO |
| ASIL ACC | B-C (fino a D); SPFM ≥90/97/99% per B/C/D | ISO 26262-5; SAE J2980 |

**Toolchain rilevanti** (con applicabilità): **Brevitas** (ALTA — quantizzatore po2 canonico + export QONNX per formalizzare il QAT esistente); **hls4ml** (MEDIO-ALTA — blocchi non-spiking, unroll pieno fattibile data la dimensione); **FINN** (ALTA come ispirazione, MEDIA come uso — nasce per MLP/CNN FF, la SNN ALIF ricorrente low-rank va custom); **Spiker+** (ALTA come riferimento architetturale/baseline risorse — LIF puro, il nostro ALIF è più ricco); **Vivado + Vitis HLS + SEM IP** (OBBLIGATORIA per Fase B/C); **Vitis-AI/DPU** (DA ESCLUDERE — non supporta il Zynq-7020, motore MAC INT8 generico che non sfrutta né sparsità né po2).

Il documento è salvato in `document/FPGA_EVALUATION_FRAMEWORK.md` (percorso relativo al repo `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN`).