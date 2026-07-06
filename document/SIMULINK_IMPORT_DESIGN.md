# SIMULINK_IMPORT_DESIGN — Fase ②: import dei champion in una libreria Simulink

> **Data:** 2026-07-06 · **Branch:** `Simulink_Importer` · **Stato:** **DESIGN APPROVATO — non ancora implementato.**
>
> Design della **prima sotto-fase di ② (Convertitore HDL)**: portare i 4 champion CF_FSNN in una **libreria
> Simulink** di blocchi riusabili, plug&play e interscambiabili. È il ponte verso l'HDL (fase ②-HDL) e verso la
> Fase ③ (FPGA-in-the-Loop). Prodotto da una sessione di brainstorming + ricerca a 4 agenti (spec interna ·
> idiomi HDL Coder · packaging/bridge/validazione · prior-art). **Prima di scrivere codice**, aprire una
> sessione writing-plans su questo doc.
>
> **Riferimenti di progetto:** `POST_FPGA_ROADMAP.md` §2 (decisioni fase ②) · `FPGA_REPORT.md` /
> `FPGA_EVALUATE_DESIGN.md` (profilo HW, Qm.n, golden) · `utils/champion_io.py` (loader champion, già fatto) ·
> `core/{network,neurons,eventprop,hardware}.py` (matematica da replicare) · `EVENTPROP_STATUS.md` §0 (stato).

---

## 0. Come riprendere (leggere prima questo)

**Cosa consegna la v1:** una **Libreria Simulink** `snn_champions_lib.slx` con **4 blocchi** — `Donatello`,
`Michelangelo`, `Raffaello`, `Leonardo` — ognuno un componente **plug&play e self-contained** che replica in
**inference** la rete SNN di quel champion: input = 4 osservazioni **fisiche** `[s, v, Δv, v_l]`, output = 5
parametri ACC-IIDM `[v0, T, s0, a, b]`. Si trascinano dalla libreria e girano, senza config esterna.

**Fedeltà v1 = comportamentale float**, con **parità numerica vs golden PyTorch** come test d'accettazione, e
**HDL-readiness PROVATA** (`coder.screener` + `checkhdl` verdi). Il fixed-point `fi`, `makehdl`/RTL e la cosim
sono il **build successivo (fase ②-HDL)** — un *refinement* dello stesso codice, non una riscrittura.

**Principio guida (north-star HDL):** il modello comportamentale **non è un modello a parte**, è l'architettura
HDL scritta in `double`. Il core è **type-parametrizzato**: lo stesso codice gira in `double` (parità) e in `fi`
Qm.n (HDL) cambiando solo un parametro di tipo → il passaggio a HDL è un flip di tipo, non una conversione che
perde il vantaggio FPGA-friendly (po2=shift, low-rank, 0 DSP).

**Prossima azione:** sessione writing-plans su questo doc. Toolbox disponibili (licenza accademica completa):
HDL Coder, Fixed-Point Designer, HDL Verifier, MATLAB Coder. MATLAB **R2026a** in locale. PyTorch in locale
(per il golden).

**Mappatura champion (da `EVENTPROP_STATUS.md:361-364`):**

| Blocco | Dir champion | Famiglia | rank | Note |
|---|---|---|---|---|
| **Donatello** | `PE_t05_gp0002` | `eventprop_alif_full` | 16 | best-NRMSE (0.152) · **candidato deploy FPGA** |
| **Michelangelo** | `A_lr1e2_t06_r16` | `eventprop_alif_full` | 16 | best-Adam (0.2031) |
| **Raffaello** | `R33_C2_A1_T12_fix` | `baseline` | 8 | Prodigy, aggressivo |
| **Leonardo** | `LS3_PEAK_R0_launch_d03` | `baseline` | 8 | champion BPTT, conservativo |

---

## 1. Architettura a 3 stadi + core type-parametrizzato

Ogni blocco = un **Subsystem** di libreria che contiene **un** MATLAB Function block con la pipeline a 3 stadi:

```
[obs fisici s,v,Δv,v_l] → NORMALIZE (affine) → SNN CORE (shift/low-rank) → DECODE (sigmoid) → [v0,T,s0,a,b]
```

- **SNN CORE** = il cuore HDL, **multiplier-free** (shift-add), puro. Deve stare in PL.
- **NORMALIZE** e **DECODE** = stadi I/O **isolati** (affine cheap / transcendentale). Il decode è l'unico punto
  "trascendentale" → isolarlo permette di scegliere dopo LUT-in-PL / CORDIC-in-PL / offload-al-PS senza toccare
  il core.

### Il pattern "types-table + entry-point" (meccanismo type-parametrizzato)
L'algoritmo del core **non nomina mai un tipo concreto**: usa solo `cast(x,'like',T.x)`, `zeros(...,'like',T.y)`.
I tipi vivono in una tabella:

```matlab
function T = snn_types(dt)
  switch dt
    case 'double'                      % parità vs golden PyTorch
      T.V = double([]); T.fatigue = double([]); T.acc = double([]); T.raw = double([]);
    case 'fixed'                       % HDL (Qm.n dai state_profiler, §8)
      T.V       = fi([], true, 11, 5);   % Q5.5
      T.fatigue = fi([], true,  9, 5);   % Q3.5
      T.acc     = fi([], true,  9, 5);   % rec/current accumulators Q3.5
      T.raw     = fi([], true, 13, 5);   % readout LI Q7.5
  end
end
```

L'**entry-point** fa il `cast` degli ingressi ai bordi e chiama il core. Golden (`'double'`) e HDL (`'fixed'`)
girano dallo **stesso** entry-point. Regola load-bearing: aggiornare lo stato con **`V(:) = expr`**
(subscripted assignment) per **preservare il numerictype** ed evitare bit-growth; `V = expr` ri-tipizza (bug).

---

## 2. Il core SNN — matematica esatta + forma HDL-idiomatica

### 2.1 Costanti architetturali (da `config.py`, uguali per tutti i champion)
`CF_INPUT_SIZE=4`, `CF_HIDDEN_SIZE=32`, `CF_OUTPUT_SIZE=5`, `CF_MAX_DELAY=6`, `TICKS_PER_STEP=10`, `DT=0.1 s`,
`bit_shift=3` → `leak_div=8` (α = 7/8). `rank ∈ {8,16}` per champion. Bound fisici:
`param_lo=[8, 0.5, 1.0, 0.3, 0.5]`, `param_hi=[45, 2.5, 5.0, 2.5, 3.0]`.

### 2.2 Forward per-tick (inference — riferimento autorevole: `neurons.py:49-88` + `network.py:494-507`; identico a `eventprop.py:410-447`)

Uno **step di controllo** (Δt=0.1 s) esegue `n_ticks=10` tick SNN interni con lo **stesso** `x_norm` replicato.
Stato (dim 32, LI dim 5) **persistente** tra tick e tra step; reset a inizio traiettoria.

```
per ogni step di controllo:
  x_norm = normalize(obs_fisico)                       # §3.1

  per k in [0, n_ticks=10):
    # 1. sinapsi ritardate (ring-buffer di 6 slot)
    push x_norm in x_buf (scarta la coda)
    I_input = Σ_{d=0..5}  (W_po2 ⊙ delay_masks[d]) · x_buf[d]      # peso·spike/x = shift (§2.3)

    # 2. ricorrenza LOW-RANK IN 2 PASSI (mai la densa 32×32)
    t   = V_po2 · s_prev          # (rank,)   — rank moltiplicazioni
    rec = U_po2 · t               # (32,)

    # 3. membrana ALIF (leak bit-shift, NESSUNA corrente sinaptica separata)
    drive = I_input + rec
    V(:)  = V - bitsra(V,3) + drive                      # = 7/8·V + drive

    # 4. soglia adattiva (fatigue del tick PRECEDENTE)
    eff_th = base_th + max(fatigue, 0)

    # 5. spike (comparatore hard, >=)
    s = (V >= eff_th)

    # 6. fatigue: leak bit-shift + salto allo spike
    fatigue(:) = fatigue - bitsra(fatigue,3) + s .* max(thresh_jump, 0)

    # 7. soft reset (sottrattivo, non azzeramento)
    V(:) = V - s .* eff_th
    s_prev = s

    # 8. output LI (leak bit-shift + readout)
    V_LI(:) = V_LI - bitsra(V_LI,3) + W_out_po2 · s      # = 7/8·V_LI + W_out·s

  raw = V_LI                                             # (5,) all'ultimo dei 10 tick
  p   = decode(raw)                                      # §3.2
```

**Punti critici (per la fedeltà):** niente corrente sinaptica `I` separata (la membrana integra `drive`
direttamente); `eff_th` usa il `fatigue` **pre-aggiornamento**; reset **soft**; decode **solo** sull'ultimo dei
10 tick; il `silent_repair` di `core/` è **solo training** → in inference ignorarlo (passo singolo).

### 2.3 Invarianti HDL (nel core da subito — il contratto "non perdere il vantaggio FPGA")
- **Pesi come esponenti-shift.** L'export salva per ogni peso `(segno, k, mask_zero)` con `k = log2|w_po2|`
  (non il float). Il core fa `bitsll(x, k)` (peso·attivazione) → in HDL è uno shift, **0 DSP**.
- **`peso · spike` = selezione (AND).** Gli spike sono binari {0,1} → il "prodotto" è addizione gated, non
  moltiplicatore.
- **Leak = shift aritmetico.** `V/8 = bitsra(V,3)` (aritmetico perché V ha segno; **mai** `bitsrl` su segnato,
  **mai** `bitshift`, **mai** divisione).
- **Ricorrenza low-rank in 2 passi** `U·(V·s)` — preserva l'op-count (32·r + r·32 vs 32·32) e il BRAM. Mai
  materializzare la densa `rec_full = U@V`.
- **Stato `persistent` read-before-write** (leggi in cima, scrivi in fondo → mappa a registro); loop ricorrente
  → **`AllowDirectFeedthrough = 0`** sulla MATLAB Function (rompe l'algebraic loop; i `dsp.Delay` NON vanno in
  feedback).
- **`fimath` = `hdlfimath`** (RoundingMethod=Floor, OverflowAction=Wrap) — no logica di saturazione/rounding
  extra per op.
- **Loop dei 10 tick interni = `coder.hdl.loopspec('stream')`** — un solo corpo hardware condiviso nel tempo
  (area minima; a DT=100 ms la latenza è irrilevante).
- **Ridondanza 0-DSP:** `bitsll`/`bitsra` espliciti **+** `DSPStyle='off'` sui blocchi (forza multiply→logica);
  `ConstMultiplierOptimization=CSD` come rete di sicurezza per eventuali costanti non-po2 residue.
- **Dimensioni statiche:** `n_ticks`, `max_delay`, `rank` costanti di compile; niente array a dim variabile,
  niente crescita dinamica, niente cell array, niente struct/matrici sulle **porte del DUT**.

---

## 3. Stadi I/O (plug&play — incorporati nel blocco)

### 3.1 NORMALIZE (input fisici → [0,1]) — `generator.py:447-467`, costanti `config.py:110-113`
```
s̃  = s   / 150
ṽ  = v   / 40
Δṽ = (clip(Δv, -20, +20) + 20) / 40        # min-max su [-20,20]; convenzione Δv = v - v_l
ṽ_l = v_l / 40
```
Affine per-canale, HDL-cheap (una moltiplicazione per costante po2-vicina → shift/CSD). Costanti bakate nel blocco.

### 3.2 DECODE (isolato) — `network.py:409-438`
```
p_i = param_lo_i + (param_hi_i - param_lo_i) · sigmoid( (raw_i - decode_offset_i) / logit_tau_i )
```
`decode_offset`/`logit_tau` sono per-champion (default 0/1 se non calibrati). **`decode_scale` (buffer F5) è
morto** — non usato, ignorare. In **v1** = `sigmoid` **esatta** in `double`. Per l'HDL (build successivo):
**default = LUT** (`coder.approximate`, un solo sigmoid → 1 BRAM, bassa latenza, range auto-dimensionato dal
testbench), con **CORDIC** (`cordicsigmoid`, 0-DSP/0-BRAM shift-add, coerente col datapath) o **offload PS** come
alternative swappabili grazie all'isolamento.

---

## 4. Le 4 famiglie → 1 datapath parametrizzato

I 4 champion si riducono a **un solo core**; le differenze sono parametri bakati:
- **`rank`** (8: Raffaello/Leonardo · 16: Donatello/Michelangelo) → dimensione di `rec_U`/`rec_V` (costante di
  compile per istanza).
- **`leak_div`** come **vettore** (32,): baseline lo salva come buffer (= 8), eventprop usa 8 uniforme →
  esportare sempre il vettore, il core fa `V - V/leak_div` (in fixed = shift per-neurone, tutti da 3 bit).
- **readout**: chiave `layer_out.fc_weight` (baseline) vs `layer_out.weight` (eventprop) — assorbita
  dall'export.
- **LI d'uscita IDENTICO** tra famiglie: `7/8·V_LI + W_out·s` (baseline `LICell` bit_shift=3 ≡ eventprop
  `LILayer_BitShift_Po2` α=7/8). Comparatore: baseline `>=`, eventprop `>` — differenza di misura nulla in
  float; in fixed si adotta **`>=`**.

---

## 5. Generazione (1 sorgente → 4 blocchi bakati)

Un **unico template** della matematica; l'export **genera** i 4 blocchi con le costanti sostituite → nessuna
duplicazione a mano, ma ogni blocco è self-contained.

### 5.1 `scripts/export_champions.py` (Python)
Per ogni champion, via `champion_io.load_champion`:
1. Applica `PowerOf2Quantize` (la vera `core/hardware.py`) ai pesi → per ciascun elemento salva
   `(segno, esponente k, mask_zero)`. **Parità garantita** (MATLAB non ri-deriva log2/round).
2. Estrae: `fc_weight`, **`delays` (esplicito!)**, `rec_U`, `rec_V`, `base_threshold`, `thresh_jump`,
   `leak_div`, `readout (W_out)`, `param_lo/hi`, `decode_offset`, `logit_tau`; scalari `n_ticks, max_delay,
   bit_shift, hidden, rank`; costanti di normalizzazione.
3. Genera i **vettori golden**: input **fisici** di test (traiettoria `val` o random deterministico) + output
   PyTorch di riferimento (via `champion_io`).
4. Scrive `champions_export.mat` (`scipy.io.savemat`, **formato v5**, `oned_as='column'`, struct per champion).

> **po2:** `sign · 2^clamp(round(log2|w|), -4, +1) · [|w| > 2⁻⁵]` (codec 4-bit = 1 segno + 3 esponente).
> **`delays`:** è un `register_buffer` rigenerato da `torch.randint` sotto `SEED=42` se assente dallo state_dict
> → **esportarlo esplicito** è l'unica via sicura (altrimenti l'export dipende dall'ordine RNG).
> **Import-rete PyTorch (`importNetworkFromPyTorch`/ONNX) = vicolo cieco** (nessun layer ALIF/po2/low-rank
> HDL-gen) → si esportano i **tensori**, confermato.

### 5.2 `matlab/build_library.m` (MATLAB)
```matlab
new_system('snn_champions_lib','Library'); ...
% per ogni champion:
add_block('built-in/Subsystem', ['snn_champions_lib/' name]);
mlfb = ['snn_champions_lib/' name '/SNN_Core'];
add_block('simulink/User-Defined Functions/MATLAB Function', mlfb);
chart = sfroot.find('-isa','Stateflow.EMChart','Path',mlfb);
chart.Script = render_template(champion_data);   % costanti bakate dal template unico
% Subsystem wrapper: porte in[4]->out[5], AllowDirectFeedthrough=0, mask informativa (nome/val_loss/topologia)
set_param('snn_champions_lib','EnableLBRepository','on'); save_system(...); set_param(...,'Lock','on');
```
La matematica del core è tradotta **una volta** (il template `.m`) e versionata. I 4 blocchi differiscono solo
nei numeri bakati. Pattern "config → libreria RTL" (à la E3NE).

> **⚠️ Da verificare 1 volta in R2026a** (test di 2 min): il formato atteso da `chart.Script` (funzione completa
> con firma vs senza la riga `function`). In alternativa usare `Simulink.MATLABFunctionConfiguration`.

---

## 6. Validazione (golden parità = vincolo "comportamento fisico")

`matlab/run_parity_tests.m`, eseguibile headless: **`matlab -batch "run_parity_tests"`** (exit code ≠0 su
fallimento → CI-friendly).
1. **Prima** valida la funzione pura `snn_core(x)` (in `double`) vs golden PyTorch → isola bug di
   **matematica** e di **trasposizione** (`[out,in]` PyTorch ↔ column-major MATLAB — causa #1 di mismatch).
2. **Poi** valida il **blocco Simulink** sullo stesso input.
- **Tol float** stretta (max-abs < 1e-5 sui 5 param). **Tol fixed** (build HDL) predetta dal Qm.n di
  `utils/quantize.py`.
- Metodologia **"QAT-matches-hardware"** (hls4ml): i modi rounding/overflow `fi` = quelli del quantizzatore.
- Determinismo: seed fissato a monte in PyTorch per il golden; stato `persistent` resettato tra champion.

---

## 7. Percorso HDL (progettato — build successivo, fase ②-HDL)

Non in v1, ma il design v1 lo abilita come *refinement*:
- **Float → fixed:** `fxpopt` (auto, con vincolo di tolleranza + Lookup Table Optimizer) **o** types-table
  manuale (§1) con i Qm.n di §8. `buildInstrumentedMex`/`showInstrumentationResults` per proporre i range.
- **Gate (già in v1):** `coder.screener('snn_entry')` → nessun costrutto non supportato; `checkhdl(subsystem)` →
  zero Errors (report `hdlsrc/*_report.html`). *(`coder.checkHDLCompatibility` non esiste — usare questi.)*
- **Generazione RTL:** `hdlsetup` + `makehdl('snn_champions_lib/<champion>')`; `DefaultParameterBehavior=Inlined`
  → **1 core sintetizzabile riusabile**. La MATLAB Function → file `*_ML_Block.vhd`.
- **Verifica bit-true:** cosim **HDL Verifier** (float / fixed / HDL sullo stesso stimolo; ULP/rel-err); Vivado
  Simulator basta (no Questa/VCS).
- **⚠️ PYNQ-Z1 NON è board built-in** → registrazione **custom-board + reference design** (stesso feature-set
  della ZedBoard una volta registrata); AXI4-Lite per registri di controllo, stream per gli spike.
- **⚠️ Gap Qm.n eventprop:** i range fixed-point misurati esistono **solo per baseline** (Raffaello/Leonardo);
  **Donatello/Michelangelo (eventprop) NON hanno state-range** — e **Donatello è il candidato deploy**. Prima
  del fixed-point serve uno step di **ri-profilazione eventprop** (estendere `state_profiler` a girare il
  forward eventprop). Non tocca la parità **float** di v1.
- **Verifica finale 0-DSP** nel `*_report.html` di sintesi (l'unica prova che gli shift non sono diventati
  moltiplicatori).

---

## 8. Target Qm.n (per il build HDL) — da `results/evaluate/FPGA/02_FixedPoint/state_ranges.csv`

`total_bits = 1 (segno) + int_bits + frac_bits`, `frac_bits = 5` (min anti-underflow = bit_shift+2). Misurati
**solo baseline** (copertura conservativa su Raffaello/Leonardo):

| Stato | Qm.n (conservativo) | total bit |
|---|---|---|
| current / rec (accumulatori) | Q3.5 | 9 |
| **membrana V** | **Q5.5** | 11 |
| **fatigue** | Q3.5 | 9 |
| eff_thresh | Q3.5 | 9 |
| **raw_out (V_LI)** | **Q7.5** | 13 (range molto champion-dipendente: ±17…±52) |
| pesi (fc/U/V/W_out) | po2: segno + esponente ∈{−4..+1} | 4 |

I Qm.n eventprop vanno **ri-profilati** (§7). Il word-length del readout va dimensionato sul champion deployato.

---

## 9. Prior-art & novità (cosa rubiamo)
- **Spiker+** (PoliTo, **MIT**, stesso chip **XC7Z020**): datapath, FSM start/ready a 3 livelli, `β=1−2⁻ᵏ`
  come shift, pesi in BRAM letti in parallelo, quantization-aware training. Riferimento d'architettura +
  budget (MNIST 7.6k LUT/18 BRAM/180 mW).
- **ALIF-FPGA neuron** (Mishra 2025, IEEE): l'unico ALIF hardware **multiplier-free** — conferma fattibilità
  soglia adattiva a costo basso; decomposizione a fasi come template FSM del neurone.
- **Brevitas** (BSD-3): `PowerOfTwoRestrictValue`/`LogFloatRestrictValue` → esporta l'**esponente log2** =
  shift-amount (adottato nell'export §5.1).
- **FINN** (BSD-3): `MultiThreshold` (lo spike `V≥eff_th` è un MultiThreshold a 1 soglia) + streamlining (fold
  affine/BN in soglie intere) — utile per il threshold fixed-point.
- **hls4ml-SNN** (Apache-2.0): pattern `LIFNeuron` stateful (stato `static` partizionato, soglia per-neurone
  vettoriale), metodologia "QAT-matches-hardware".
- **E3NE** (MIT): pattern "config-package → libreria RTL" (= mask/struct → HDL Coder). **FireFly** (MIT):
  idea Psum-Vmem unified buffer (BRAM-saving) — utile contro il collo BRAM.

> **Novità nostra (nessuno la fa insieme):** ALIF-adattivo + ricorrenza **low-rank U·V** + pesi **po2** dentro
> **MATLAB HDL Coder** con DSP≈0. La low-rank attacca proprio il collo BRAM che limita la ricorrenza di Spiker+.

---

## 10. Deliverable (branch `Simulink_Importer`)

```
scripts/
  export_champions.py        # champion_io -> po2(sign,exp,mask) + delays + golden -> champions_export.mat
matlab/
  snn_core.m                 # la matematica, %#codegen, type-agnostica (cast 'like', persistent, bitsll/bitsra, loopspec stream)
  snn_types.m                # types-table 'double' | 'fixed' (Qm.n §8)
  snn_entry.m                # entry-point: cast ai bordi -> snn_core
  build_library.m            # template -> snn_champions_lib.slx (4 blocchi bakati)
  run_parity_tests.m         # matlab -batch: funzione pura, poi blocco, vs golden
  check_hdl.m                # coder.screener + checkhdl sui subsystem (gate v1)
  snn_champions_lib.slx      # LA LIBRERIA: Donatello / Michelangelo / Raffaello / Leonardo
document/
  SIMULINK_IMPORT_DESIGN.md  # questo doc
```

**Criterio di "fatto" v1:** i 4 blocchi caricano/girano; `run_parity_tests` **verde** (parità float sui 5 param
per tutti e 4); `check_hdl` **verde** (screener + checkhdl senza Errors) → HDL-readiness provata.

---

## 11. Decisioni bloccate + rischi

**Decisioni (salvo revisione esplicita):** 4 blocchi distinti self-contained, generati da 1 template · core
type-parametrizzato (types-table) · v1 = float + parità + gate checkhdl · pesi come esponenti-shift · ricorrenza
low-rank in 2 passi · decode isolato (LUT default per l'HDL) · loop interno in stream · nomi = TMNT.

**Rischi/caveat aperti:** (1) Qm.n eventprop non misurati (Donatello!) → ri-profilazione prima del fixed-point;
(2) formato `chart.Script` da verificare in R2026a; (3) trasposizione pesi PyTorch↔MATLAB (catturata dal test
sulla funzione pura); (4) `checkhdl` verde ≠ RTL garantito → verifica 0-DSP nel report di sintesi; (5) range
readout LI molto champion-dipendente → word-length sul champion deployato.

---

## 12. Riferimenti (doc verificate durante la ricerca)
- HDL Coder — persistent + fi: mathworks.com/help/hdlcoder/ug/using-persistent-variables-inside-matlab-function-blocks-for-hdl-code-generation.html
- Fixed-point best practices (types-table): mathworks.com/help/fixedpoint/ug/manual-fixed-point-conversion-best-practices.html
- Bitwise per HDL (bitsll/bitsra): mathworks.com/help/hdlcoder/ug/shift-and-rotate-without-saturation-or-rounding-logic.html
- Constant multiplier optimization (CSD): mathworks.com/help/hdlcoder/ug/constant-multiplier-optimization-to-reduce-area.html
- coder.hdl.loopspec: mathworks.com/help/hdlcoder/ref/coder.hdl.loopspec.html
- coder.screener / checkhdl: mathworks.com/help/simulink/slref/coder.screener.html · mathworks.com/help/hdlcoder/ref/checkhdl.html
- cordicsigmoid / coder.approximate LUT: mathworks.com/help/fixedpoint/ref/cordicsigmoid.html · mathworks.com/help/hdlcoder/ug/generate-hdl-compatible-lookup-table-function-replacements-using-coder-approximate.html
- fxpopt (NN → fixed → HDL): mathworks.com/help/fixedpoint/ug/fixed-point-conversion-of-regression-neural-networks-using-fxpopt.html
- makehdl / IP core Zynq / custom board: mathworks.com/help/hdlcoder/ref/makehdl.html · mathworks.com/help/hdlcoder/ug/define-and-register-custom-board-and-reference-design-for-zynq-workflow.html
- HDL Verifier auto-verification: mathworks.com/help/hdlverifier/ug/test-bench-automatic-verification-with-simulink.html
- Simulink.Mask / MATLAB Function programmatica: mathworks.com/help/simulink/slref/simulink.mask-class.html · mathworks.com/help/simulink/ug/configure-matlab-function-blocks-programmatically.html
- Prior-art: Spiker+ github.com/smilies-polito/Spiker (MIT) · Brevitas github.com/Xilinx/brevitas (BSD-3) · FINN github.com/Xilinx/finn (BSD-3) · hls4ml github.com/fastmachinelearning/hls4ml (Apache-2.0) · E3NE github.com/DanielGerlinghoff/radix-encoding (MIT) · FireFly github.com/adamgallas/FireFly-v1 (MIT) · ALIF-FPGA ieeexplore.ieee.org/document/10994369
