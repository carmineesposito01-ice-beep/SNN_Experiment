# FPGA Fase B — Power Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validare (confermare/correggere) le claim energetiche/risorse/timing del `FPGA_REPORT` con sintesi e `report_power` Vivado reali, al nodo 28nm, per Donatello B2, e produrre un addendum drop-in.

**Architecture:** Quattro gruppi. **A** = potenza di sistema del B2 (SAIF da stimolo reale → `report_power`). **B** = costanti per-op e_AC/e_MAC da micro-datapath isolati. **C** = baseline ANN densa matched time-mux. **D** = raccolta numeri + deliverable. Ogni RTL è generato via HDL Coder da sorgente MATLAB (VHDL mai a mano). Il core SNN non si tocca.

**Tech Stack:** MATLAB R2026a + HDL Coder (`coder.config('hdl')` + `codegen`), Vivado 2026.1 (`C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat`), xsim (SAIF), Python 3 (parsing `.rpt`). Part `xc7z020clg400-1`.

**Spec:** `docs/superpowers/specs/2026-07-10-fpga-phase-b-power-design.md`.

**Convenzioni:**
- Vivado headless: `"C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat" -mode batch -source <tcl>`, cwd corta (es. `/d/zrun`), progetti in ROOT corto `D:/zbd` (limite path 260-byte Windows).
- Commit **senza** `Co-Authored-By`. Push su `Simulink_Importer`.
- MATLAB headless: `matlab -batch "<fn>"` dalla cartella `matlab/`.
- **Gotcha HDL ricorrenti** (da `document/HDL_PHASE.md` §9): `double`/`log2` solo su costanti header (foldate, MAI in datapath → isnan/isinf); `bitshift` stesso-tipo TRONCA (usa tipo largo); ogni sorgente nuova deve passare `codegen` HDL prima di sintetizzare.

---

## File Structure

**Nuovi sorgenti MATLAB (single-source HDL Coder):**
- `matlab/micro_ac.m` — accumulatore po2 shift-add, 1 op/ciclo, operandi da LFSR interno (la "sinapsi" SNN).
- `matlab/micro_mac.m` — MAC fixed-point, 1 op/ciclo, LFSR interno (la "sinapsi" ANN → DSP48).
- `matlab/make_hdl_micro.m` — codegen VHDL di micro_ac + micro_mac (mirror di `make_hdl_b2fsm.m`).
- `matlab/ann_mlp.m` — MLP densa 4→32→32→5 time-multiplexata (1 MAC/ciclo, pesi ROM), la baseline ANN.
- `matlab/ann_rom.m` — pesi ANN random-in-range baked come `fi` (GENERATO da `gen_ann_rom.m`).
- `matlab/gen_ann_rom.m` — generatore di `ann_rom.m` (mirror di `gen_b2_rom.m`).
- `matlab/test_ann_mlp.m` — parità double-vs-fixed della ANN (che si comporti in modo deterministico).
- `matlab/make_hdl_ann.m` — codegen VHDL della ANN.

**Stimolo + testbench (in `matlab/axi/phase_b/`):**
- `matlab/axi/phase_b/gen_stimulus.m` — da `test_trajectories.mat`: normalizza (snn_normalize) → xn Q5.13 → `stim_typical.mem`/`stim_worst.mem` + `expected_params.csv`.
- `matlab/axi/phase_b/tb_b2_stream.v` — guida `snn_top_b2_flat` con N inferenze dallo stimolo (per SAIF).
- `matlab/axi/phase_b/tb_micro_ac.v`, `tb_micro_mac.v` — clockano i micro-datapath molti cicli (per SAIF).
- `matlab/axi/phase_b/tb_ann_stream.v` — guida la ANN con lo stimolo (per SAIF).

**Tcl + output (in `matlab/axi/build/phase_b/`):**
- `power_b2.tcl`, `power_micro.tcl`, `power_ann.tcl` — synth OOC + impl + sim SAIF + `report_power`.
- output `*.rpt`, `*.saif`, `results.csv`.
- `collect_results.py` — parse `.rpt` → `results.csv` + calcoli (pJ/inf, e_AC/e_MAC, rapporti, cross-check).

**Deliverable:**
- `document/FPGA_PHASE_B_POWER.md` — tabella claim con numeri reali + re-tag + appendice Fase C.

---

## Task 0: Orientamento e setup cartelle

**Files:**
- Create: `matlab/axi/phase_b/` (dir), `matlab/axi/build/phase_b/` (dir)

- [ ] **Step 1: Leggi i template da rispecchiare**

Leggi questi file (esistono, sono i pattern da seguire — NON reinventare):
`matlab/snn_b2_fsm.m`, `matlab/make_hdl_b2fsm.m`, `matlab/gen_b2_rom.m`, `matlab/snn_normalize.m`,
`matlab/axi/snn_top_b2_flat.vhd`, `matlab/axi/axi_tb.v`, `matlab/axi/build/bitstream_board.tcl`.
Nota: `snn_top_b2_flat` ha ingresso `xn` piatto `std_logic_vector(75:0)` (4×19b) + `start`, uscita
`params` `std_logic_vector(104:0)` (5×21b) + `valid`. È il DUT di potenza del gruppo A (SNN+decode, senza AXI).

- [ ] **Step 2: Crea le cartelle**

```bash
mkdir -p "matlab/axi/phase_b" "matlab/axi/build/phase_b"
```

- [ ] **Step 3: Commit dello scaffold**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add -f matlab/axi/phase_b/.gitkeep matlab/axi/build/phase_b/.gitkeep 2>/dev/null || true
touch matlab/axi/phase_b/.gitkeep matlab/axi/build/phase_b/.gitkeep
git add matlab/axi/phase_b/.gitkeep matlab/axi/build/phase_b/.gitkeep
git commit -m "chore(fase-b): scaffold cartelle phase_b"
```

---

## GRUPPO A — Potenza di sistema del B2

### Task A1: Generatore di stimolo (tipico + worst) da traiettorie reali

**Files:**
- Create: `matlab/axi/phase_b/gen_stimulus.m`
- Uses: `matlab/test_trajectories.mat`, `matlab/snn_normalize.m`, `matlab/snn_types.m`

- [ ] **Step 1: Scrivi `gen_stimulus.m`**

```matlab
function gen_stimulus()
%GEN_STIMULUS  Produce stimoli xn (Q5.13) per il SAIF del B2: tipico + worst.
%  Tipico  = una traiettoria reale normalizzata (firing rappresentativo).
%  Worst   = xn che massimizzano il firing (Δv grande, gap piccolo, alta v).
%  Scrive .mem (hex, 4 parole 19-bit/riga) + expected_params.csv (gate funzionale).
  here = fileparts(mfilename('fullpath'));
  mroot = fileparts(fileparts(here));            % .../matlab
  addpath(mroot);
  T = snn_types('fixed');                        % tabella tipi fixed-point
  d = load(fullfile(mroot, 'test_trajectories.mat'));
  traj = d.trajectories(1);                      % una traiettoria in-distribuzione
  X = double(traj.val);                          % 4×N  (s, v, dv, vl) fisici

  % ---- TIPICO: normalizza ogni colonna e impacchetta ----
  writeStim(fullfile(here, 'stim_typical.mem'), X, T, mroot);

  % ---- WORST: satura verso alto-firing (gap minimo, Δv massimo, v alta) ----
  N = size(X, 2);
  Xw = [repmat(2, 1, N);      % s piccolo (gap ~2 m)
        repmat(35, 1, N);     % v alta
        repmat(-15, 1, N);    % Δv fortemente negativo (chiusura rapida)
        repmat(20, 1, N)];    % vl
  writeStim(fullfile(here, 'stim_worst.mem'), Xw, T, mroot);
  fprintf('OK: stim_typical.mem + stim_worst.mem (%d righe)\n', N);
end

function writeStim(fname, X, T, mroot)
  N = size(X, 2);
  fid = fopen(fname, 'w');
  for i = 1:N
    xn = snn_normalize(X(:, i), T);              % 4×1 normalizzati (fixed)
    row = '';
    for j = 1:4
      v = fi(xn(j), 1, 19, 13);                  % Q5.13, 19-bit
      u = uint32(bitand(int32(v.int), int32(hex2dec('7FFFF'))));  % 19-bit due complementi
      row = [row sprintf('%05X ', u)];           %#ok<AGROW>
    end
    fprintf(fid, '%s\n', strtrim(row));
  end
  fclose(fid);
end
```

- [ ] **Step 2: Esegui**

Run: `cd matlab/axi/phase_b && matlab -batch "gen_stimulus"`
Expected: stampa `OK: stim_typical.mem + stim_worst.mem (N righe)`; i due `.mem` esistono, 4 esadecimali/riga.

- [ ] **Step 3: Verifica il formato**

Run: `head -3 matlab/axi/phase_b/stim_typical.mem`
Expected: 3 righe, ognuna 4 token esadecimali a 5 cifre (es. `01462 008A2 00150 00087`).
Se una parola supera `7FFFF` → il masking a 19-bit è rotto: investiga (non troncare a caso).

- [ ] **Step 4: Commit**

```bash
git add matlab/axi/phase_b/gen_stimulus.m matlab/axi/phase_b/stim_typical.mem matlab/axi/phase_b/stim_worst.mem
git commit -m "feat(fase-b): generatore stimolo xn (tipico+worst) per SAIF B2"
```

### Task A2: Testbench di streaming per `snn_top_b2_flat`

**Files:**
- Create: `matlab/axi/phase_b/tb_b2_stream.v`

- [ ] **Step 1: Scrivi il testbench**

```verilog
`timescale 1ns/1ps
// Guida snn_top_b2_flat con le righe di uno .mem: start, attende valid, next.
// Stampa i cicli/inferenza (per E/inf) e permette il dump SAIF.
module tb_b2_stream;
  localparam CLKP = 125;                // 8 MHz = Fclk REALE del B2 (lane ~8.5 MHz; a 100 MHz avrebbe X)
  localparam NROW = 512;                // righe di stimolo da consumare (>= righe .mem)
  reg clk = 0, rst = 0, start = 0;
  reg  [75:0] xn = 0;
  wire [104:0] params;
  wire valid;
  reg  [18:0] mem [0:NROW*4-1];
  integer r, c0, c1, i;

  snn_top_b2_flat dut (.clk(clk), .reset(rst), .xn(xn), .start(start),
                       .params(params), .valid(valid));

  always #62.5 clk = ~clk;              // mezzo periodo 62.5 ns -> 8 MHz

  initial begin
    $readmemh("stim_typical.mem_PLACEHOLDER", mem);  // sostituito dal Tcl (typical/worst)
    rst = 1; repeat (8) @(posedge clk); rst = 0;
    for (r = 0; r < NROW; r = r + 1) begin
      xn = {mem[r*4+0], mem[r*4+1], mem[r*4+2], mem[r*4+3]};
      @(posedge clk); start = 1; @(posedge clk); start = 0;
      c0 = $time;
      while (!valid) @(posedge clk);
      c1 = $time;
      if (r == 0) $display("CICLI_INF %0d", (c1 - c0) / CLKP);
    end
    $display("STREAM_DONE %0d inferenze", NROW);
    $finish;
  end
endmodule
```

Nota: il Tcl (Task A3) copia il `.mem` giusto sul nome atteso e sostituisce il placeholder, così lo
stesso TB serve tipico e worst. Verifica i nomi delle porte di `snn_top_b2_flat.vhd` (Task 0 Step 1) e
allineali se differiscono (`clk`/`reset`/`xn`/`start`/`params`/`valid`).

- [ ] **Step 2: Commit**

```bash
git add matlab/axi/phase_b/tb_b2_stream.v
git commit -m "feat(fase-b): TB streaming per snn_top_b2_flat (SAIF)"
```

### Task A3: Tcl potenza B2 (utilization-hier + timing + SAIF + report_power)

**Files:**
- Create: `matlab/axi/build/phase_b/power_b2.tcl`

- [ ] **Step 1: Scrivi il Tcl**

```tcl
# power_b2.tcl — OOC synth+impl di snn_top_b2_flat, utilization gerarchica, SAIF x2, report_power.
set ROOT "D:/zbd_pb2"
file delete -force $ROOT
set SNN "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/codegen/snn_top_b2/hdlsrc"
set AXI "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/axi"
set PB  "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/axi/phase_b"
set OUT "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/axi/build/phase_b"

create_project pb2 $ROOT -part xc7z020clg400-1 -force
add_files [list "$SNN/snn_top_b2_pkg.vhd" "$SNN/DualPortRAM_generic.vhd" "$SNN/snn_top_b2.vhd" "$AXI/snn_top_b2_flat.vhd"]
set_property top snn_top_b2_flat [current_fileset]
# preserva la gerarchia per attribuire i DSP per-modulo
set_property STEPS.SYNTH_DESIGN.ARGS.FLATTEN_HIERARCHY none [get_runs synth_1]
launch_runs synth_1 -jobs 6
wait_on_run synth_1
open_run synth_1
report_utilization -hierarchical -file "$OUT/util_b2_hier.rpt"
report_utilization -file "$OUT/util_b2_flat.rpt"

# impl (OOC): clock all'Fclk REALE del B2 = 8 MHz (period 125 ns); a 100 MHz non chiuderebbe.
set xdc "$ROOT/clk.xdc"
set f [open $xdc w]; puts $f "create_clock -name clk -period 125.000 \[get_ports clk\]"; close $f
add_files -fileset constrs_1 $xdc
launch_runs impl_1 -jobs 6
wait_on_run impl_1
open_run impl_1
report_timing_summary -file "$OUT/timing_b2.rpt"
report_power -file "$OUT/power_b2_vectorless.rpt"

# ---- SAIF-based per due stimoli ----
proc run_saif {label memfile PB OUT ROOT} {
  # copia lo stimolo sul nome atteso dal TB e patcha il placeholder
  file copy -force "$PB/$memfile" "$ROOT/stim.mem"
  set tb [read [open "$PB/tb_b2_stream.v" r]]
  set tb [string map [list "stim_typical.mem_PLACEHOLDER" "stim.mem"] $tb]
  set f [open "$ROOT/tb_run.v" w]; puts $f $tb; close $f
  # simulazione post-impl timing con dump SAIF
  set simtcl "$ROOT/sim_$label.tcl"
  set s [open $simtcl w]
  puts $s "open_saif \"$OUT/b2_$label.saif\""
  puts $s "log_saif \[get_objects -r /tb_b2_stream/dut/*\]"
  puts $s "run all"
  puts $s "close_saif"
  puts $s "quit"
  close $s
  add_files -fileset sim_1 [list "$ROOT/tb_run.v"]
  set_property top tb_b2_stream [get_filesets sim_1]
  set_property -name {xsim.simulate.custom_tcl} -value $simtcl -objects [get_filesets sim_1]
  launch_simulation -mode post-implementation -type timing
  close_sim
  read_saif "$OUT/b2_$label.saif"
  report_power -file "$OUT/power_b2_$label.rpt"
}
run_saif typical stim_typical.mem $PB $OUT $ROOT
run_saif worst   stim_worst.mem   $PB $OUT $ROOT
puts "DONE-POWER-B2"
```

Nota di fedeltà: `launch_simulation -mode post-implementation -type timing` richiede la sim-netlist; se
in questa versione di Vivado il flusso non-progetto la nega, usa il progetto `pb2` (già creato) — è il
motivo per cui qui si usa `create_project` e non il flusso non-progetto del bitstream. Se `log_saif` sui
path `dut/*` non copre abbastanza net → il gate copertura (Task A4) fallisce e vai più a fondo (estendi lo
stimolo / logga la gerarchia intera), NON accettare un SAIF magro.

- [ ] **Step 2: Esegui**

Run:
```bash
mkdir -p /d/zrun && cd /d/zrun && "C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat" -mode batch -journal /d/zrun/pb2.jou -log /d/zrun/pb2.log -source ".../matlab/axi/build/phase_b/power_b2.tcl"
```
(usa il percorso assoluto del Tcl). È lungo (~20-30 min): lancialo in background.
Expected (a fine): `DONE-POWER-B2`; esistono `power_b2_typical.rpt`, `power_b2_worst.rpt`, `util_b2_hier.rpt`.

- [ ] **Step 3: GATE — copertura e confidenza**

Run: `grep -iE "confidence|Total On-Chip|Dynamic|coverage" matlab/axi/build/phase_b/power_b2_typical.rpt | head`
Expected: `report_power` con **Confidence ≥ Medium**. Se "Low" → il SAIF non ha coperto abbastanza:
investiga (path `log_saif`, durata sim), NON pubblicare il numero. Blocca finché il gate non passa.

- [ ] **Step 4: GATE — correttezza funzionale**

Run: `grep -E "CICLI_INF|STREAM_DONE" /d/zrun/pb2.log`
Expected: `CICLI_INF <~340>` e `STREAM_DONE`. La correttezza **bit-exact** del datapath è già stabilita dal
cosim esistente (`matlab/axi/axi_tb.v`, `AXI TEST PASSED`, logica invariata); questo gate verifica solo che
il **netlist post-route giri** (valid asserisce, cicli sani). Se i cicli/inf sono assurdi o la sim non
completa → il netlist non funziona post-route: investiga prima di fidarti della potenza. (Opzionale: per una
verifica end-to-end nel power-sim, `gen_stimulus` può emettere `expected_row0` chiamando `snn_top_b2` in
MATLAB e il TB confrontarlo — non necessario dato il cosim autoritativo.)

- [ ] **Step 5: Commit**

```bash
git add matlab/axi/build/phase_b/power_b2.tcl matlab/axi/build/phase_b/util_b2_hier.rpt matlab/axi/build/phase_b/power_b2_*.rpt matlab/axi/build/phase_b/timing_b2.rpt
git commit -m "feat(fase-b): potenza di sistema B2 (utilization-hier + SAIF typical/worst + report_power)"
```

---

## GRUPPO B — Costanti node-correct e_AC / e_MAC

### Task B1: Micro-datapath `micro_ac` e `micro_mac`

**Files:**
- Create: `matlab/micro_ac.m`, `matlab/micro_mac.m`

- [ ] **Step 1: Scrivi `micro_ac.m`** (shift-add po2, 1 op/ciclo, LFSR interno)

```matlab
function y = micro_ac() %#codegen
%MICRO_AC  1 accumulo po2 shift-add per ciclo; operando da LFSR interno (isola l'I/O).
%  Rappresenta la "sinapsi" SNN: operando << esponente po2 (moltiplicazione po2), poi somma.
  persistent lfsr acc cnt
  if isempty(lfsr)
    lfsr = uint16(43981);            % 0xABCD
    acc  = fi(0, 1, 32, 13);
    cnt  = uint8(0);
  end
  % LFSR 16-bit (taps 16,14,13,11) -> bit nuovo
  nb   = bitxor(bitxor(bitget(lfsr,16), bitget(lfsr,14)), bitxor(bitget(lfsr,13), bitget(lfsr,11)));
  lfsr = bitor(bitshift(lfsr, 1), uint16(nb));
  x    = reinterpretcast(lfsr, numerictype(1, 16, 13));   % bits -> fi con segno, toggla ogni ciclo
  k    = cnt;                                              % esponente po2 in [0,7]
  cnt  = mod(cnt + uint8(1), uint8(8));
  sh   = fi(bitsll(fi(x, 1, 32, 13), k), 1, 32, 13);       % x << k nel tipo largo (no troncamento)
  acc  = fi(acc + sh, 1, 32, 13);
  y    = acc;
end
```

- [ ] **Step 2: Scrivi `micro_mac.m`** (MAC fixed-point → DSP48)

```matlab
function y = micro_mac() %#codegen
%MICRO_MAC  1 MAC per ciclo; operandi da LFSR interno. La "sinapsi" ANN -> DSP48.
  persistent lfsr acc
  if isempty(lfsr)
    lfsr = uint16(4660);             % 0x1234
    acc  = fi(0, 1, 48, 26);
  end
  nb   = bitxor(bitxor(bitget(lfsr,16), bitget(lfsr,14)), bitxor(bitget(lfsr,13), bitget(lfsr,11)));
  lfsr = bitor(bitshift(lfsr, 1), uint16(nb));
  x    = reinterpretcast(lfsr,               numerictype(1, 18, 13));
  w    = reinterpretcast(bitshift(lfsr, -2), numerictype(1, 18, 13));
  acc  = fi(acc + fi(x * w, 1, 48, 26), 1, 48, 26);        % moltiplicazione data×data -> DSP
  y    = acc;
end
```

- [ ] **Step 3: Commit**

```bash
git add matlab/micro_ac.m matlab/micro_mac.m
git commit -m "feat(fase-b): micro-datapath micro_ac (shift-add) e micro_mac (DSP48)"
```

### Task B2: Codegen VHDL dei micro-datapath

**Files:**
- Create: `matlab/make_hdl_micro.m`

- [ ] **Step 1: Scrivi `make_hdl_micro.m`** (mirror di `make_hdl_b2fsm.m`)

```matlab
function make_hdl_micro()
%MAKE_HDL_MICRO  Codegen VHDL di micro_ac e micro_mac (nessun argomento: stato interno LFSR).
  here = fileparts(mfilename('fullpath')); addpath(here);
  cfg = coder.config('hdl');
  cfg.TargetLanguage = 'VHDL';
  cfg.GenerateHDLTestBench = false;
  cfg.SimulateGeneratedCode = false;
  try, cfg.HDLLintTool = 'None'; catch, end
  for fn = {'micro_ac', 'micro_mac'}
    fprintf('== codegen HDL: %s ==\n', fn{1});
    codegen('-config', cfg, fn{1}, '-args', {}, '-report');
    fprintf('OK: %s\n', fn{1});
  end
end
```

- [ ] **Step 2: Esegui + GATE HDL-readiness**

Run: `cd matlab && matlab -batch "make_hdl_micro"`
Expected: `OK: micro_ac` e `OK: micro_mac`; RTL in `matlab/codegen/micro_ac/hdlsrc/` e `.../micro_mac/hdlsrc/`.
Se `codegen` fallisce (isnan/isinf su double, bitshift troncante) → applica i gotcha HDL (§9 HDL_PHASE): il
`double` non deve entrare nel datapath; qui non c'è, ma se emerge, correggi la causa, non aggirare.

- [ ] **Step 3: Commit**

```bash
git add matlab/make_hdl_micro.m
git commit -m "feat(fase-b): codegen VHDL micro-datapath"
```

### Task B3: Testbench dei micro-datapath

**Files:**
- Create: `matlab/axi/phase_b/tb_micro_ac.v`, `matlab/axi/phase_b/tb_micro_mac.v`

- [ ] **Step 1: Scrivi `tb_micro_ac.v`**

```verilog
`timescale 1ns/1ps
// Clocka micro_ac per molti cicli (1 shift-add/ciclo) per il SAIF. Nome top VHDL = micro_ac.
module tb_micro_ac;
  reg clk = 0, rst = 0;
  wire [31:0] y;
  micro_ac dut (.clk(clk), .reset(rst), .clk_enable(1'b1), .y(y));  // adegua ai nomi porta RTL
  always #5 clk = ~clk;                                             // 100 MHz
  initial begin
    rst = 1; repeat (8) @(posedge clk); rst = 0;
    repeat (20000) @(posedge clk);                                  // 20k op
    $display("MICRO_AC_DONE y=%h", y);
    $finish;
  end
endmodule
```

- [ ] **Step 2: Scrivi `tb_micro_mac.v`** (identico, top `micro_mac`, uscita 48-bit)

```verilog
`timescale 1ns/1ps
module tb_micro_mac;
  reg clk = 0, rst = 0;
  wire [47:0] y;
  micro_mac dut (.clk(clk), .reset(rst), .clk_enable(1'b1), .y(y));  // adegua ai nomi porta RTL
  always #5 clk = ~clk;
  initial begin
    rst = 1; repeat (8) @(posedge clk); rst = 0;
    repeat (20000) @(posedge clk);
    $display("MICRO_MAC_DONE y=%h", y);
    $finish;
  end
endmodule
```

Nota: i nomi/larghezze delle porte del top VHDL generato (`clk`, `reset`/`clk_enable`, `y`) vanno letti da
`matlab/codegen/micro_*/hdlsrc/micro_*.vhd` e allineati. HDL Coder genera tipicamente `clk, reset,
clk_enable, <out>, <out>_valid`.

- [ ] **Step 3: Commit**

```bash
git add matlab/axi/phase_b/tb_micro_ac.v matlab/axi/phase_b/tb_micro_mac.v
git commit -m "feat(fase-b): TB micro-datapath per SAIF"
```

### Task B4: Tcl potenza micro → e_AC, e_MAC

**Files:**
- Create: `matlab/axi/build/phase_b/power_micro.tcl`

- [ ] **Step 1: Scrivi il Tcl** (una proc riusata per i due micro)

```tcl
# power_micro.tcl — synth+impl OOC di micro_ac e micro_mac, SAIF, report_power (breakdown per isolare I/O).
set BASE "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
set OUT  "$BASE/matlab/axi/build/phase_b"

proc power_one {name topfile tbfile part BASE OUT} {
  set ROOT "D:/zbd_$name"
  file delete -force $ROOT
  create_project $name $ROOT -part $part -force
  add_files [glob "$BASE/matlab/codegen/$name/hdlsrc/*.vhd"]
  set_property top $name [current_fileset]
  set xdc "$ROOT/clk.xdc"
  set f [open $xdc w]; puts $f "create_clock -name clk -period 10.000 \[get_ports clk\]"; close $f
  add_files -fileset constrs_1 $xdc
  launch_runs impl_1 -jobs 6
  wait_on_run impl_1
  open_run impl_1
  report_utilization -file "$OUT/util_$name.rpt"
  report_timing_summary -file "$OUT/timing_$name.rpt"
  # SAIF
  add_files -fileset sim_1 "$BASE/matlab/axi/phase_b/$tbfile"
  set_property top tb_$name [get_filesets sim_1]
  set simtcl "$ROOT/sim.tcl"
  set s [open $simtcl w]
  puts $s "open_saif \"$OUT/$name.saif\""
  puts $s "log_saif \[get_objects -r /tb_$name/dut/*\]"
  puts $s "run all"; puts $s "close_saif"; puts $s "quit"
  close $s
  set_property -name {xsim.simulate.custom_tcl} -value $simtcl -objects [get_filesets sim_1]
  launch_simulation -mode post-implementation -type timing
  close_sim
  read_saif "$OUT/$name.saif"
  report_power -file "$OUT/power_$name.rpt"
  puts "DONE-$name"
}
power_one micro_ac  micro_ac.vhd  tb_micro_ac.v  xc7z020clg400-1 $BASE $OUT
power_one micro_mac micro_mac.vhd tb_micro_mac.v xc7z020clg400-1 $BASE $OUT
puts "DONE-POWER-MICRO"
```

- [ ] **Step 2: Esegui** (background, ~20 min)

Run: `cd /d/zrun && "C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat" -mode batch -source ".../power_micro.tcl"`
Expected: `DONE-POWER-MICRO`; `power_micro_ac.rpt`, `power_micro_mac.rpt`, `util_micro_*.rpt`.

- [ ] **Step 3: GATE — I/O-pad e confidenza**

Run: `grep -iE "confidence|I/O|Signals|Logic|DSP|Dynamic" matlab/axi/build/phase_b/power_micro_mac.rpt | head -20`
Expected: confidenza ≥ Media; nel breakdown la potenza **NON** deve essere dominata da I/O. Se >50% è I/O →
il micro è troppo piccolo: aumenta il lavoro interno (più op/ciclo o più registri) e rifai. e_op = (Logic+
Signals+DSP dynamic) / Fclk (100 MHz), 1 op/ciclo. Annota e_AC (da micro_ac) e e_MAC (da micro_mac).

- [ ] **Step 4: Verifica coerenza**

Controllo di sanità: `micro_mac` deve mostrare **DSP ≥ 1** (nel `util_micro_mac.rpt`); `micro_ac` deve
mostrare **DSP = 0**. Se `micro_ac` usa un DSP → lo shift po2 non è mappato a LUT: investiga (è lo stesso
rischio della claim "0 DSP sinapsi").

- [ ] **Step 5: Commit**

```bash
git add matlab/axi/build/phase_b/power_micro.tcl matlab/axi/build/phase_b/power_micro_*.rpt matlab/axi/build/phase_b/util_micro_*.rpt
git commit -m "feat(fase-b): potenza micro-datapath -> e_AC ed e_MAC @28nm"
```

---

## GRUPPO C — Baseline ANN densa matched

### Task C1: ROM pesi ANN + sorgente ANN

**Files:**
- Create: `matlab/gen_ann_rom.m`, `matlab/ann_mlp.m`

- [ ] **Step 1: Scrivi `gen_ann_rom.m`** (pesi random-in-range baked, mirror di `gen_b2_rom.m`)

```matlab
function gen_ann_rom()
%GEN_ANN_ROM  Genera ann_rom.m con pesi random-in-range baked (fi). La potenza dipende dallo
%  switching, non dall'accuratezza: pesi rappresentativi in [-1,1], deterministici (seed fisso).
  here = fileparts(mfilename('fullpath'));
  rng(42);                                   % deterministico
  W1 = 2*rand(32, 4)  - 1;                   % input fc 4->32
  Wh = 2*rand(32, 32) - 1;                   % hidden denso 32->32 (equivalente alla ricorrenza)
  Wo = 2*rand(5, 32)  - 1;                   % out 32->5
  fid = fopen(fullfile(here, 'ann_rom.m'), 'w');
  w = @(varargin) fprintf(fid, varargin{:});
  w('function A = ann_rom() %%#codegen\n');
  w('%%ANN_ROM  Pesi ANN densa random-in-range baked. GENERATO da gen_ann_rom.\n');
  w('  A.W1 = fi(%s, 1, 18, 13);\n', mat2str(W1, 17));
  w('  A.Wh = fi(%s, 1, 18, 13);\n', mat2str(Wh, 17));
  w('  A.Wo = fi(%s, 1, 18, 13);\n', mat2str(Wo, 17));
  w('end\n');
  fclose(fid);
  fprintf('scritto ann_rom.m (4->32->32->5, %d MAC/inf)\n', 4*32 + 32*32 + 32*5);
end
```

- [ ] **Step 2: Scrivi `ann_mlp.m`** (dense time-mux; per semplicità di sintesi, layer-parallelo ma MAC-espliciti)

```matlab
function [out, valid] = ann_mlp(xn, start) %#codegen
%ANN_MLP  MLP densa 4->32->32->5 (equivalente denso della ricorrenza SNN, ann_mac=1312).
%  Interfaccia come snn_top_b2: [out,valid]=ann_mlp(xn,start). Fixed-point, HDL-ready.
%  Nota: baseline di POTENZA/AREA (usa i DSP), non un modello addestrato.
  persistent A busy
  if isempty(A); A = ann_rom(); busy = false; end
  Ta = numerictype(1, 40, 26);
  out = fi(zeros(5, 1), 1, 21, 13);
  valid = false;
  if start
    h1 = relu_layer(A.W1, xn, 32, 4,  Ta);    % 4->32
    h2 = relu_layer(A.Wh, h1, 32, 32, Ta);    % 32->32
    o  = lin_layer(A.Wo, h2, 5, 32, Ta);      % 32->5
    out = fi(o, 1, 21, 13);
    valid = true;
    busy = ~busy;                             % tocca stato per non farlo ottimizzare via
  end
end

function y = relu_layer(W, x, no, ni, Ta)
  y = fi(zeros(no, 1), numerictype(x));
  for i = 1:no
    acc = fi(0, Ta);
    for j = 1:ni
      acc = fi(acc + fi(W(i, j) * x(j), Ta), Ta);
    end
    if acc < fi(0, Ta); acc = fi(0, Ta); end   % ReLU
    y(i) = fi(acc, numerictype(x));
  end
end

function y = lin_layer(W, x, no, ni, Ta)
  y = fi(zeros(no, 1), numerictype(x));
  for i = 1:no
    acc = fi(0, Ta);
    for j = 1:ni
      acc = fi(acc + fi(W(i, j) * x(j), Ta), Ta);
    end
    y(i) = fi(acc, numerictype(x));
  end
end
```

Nota: questa forma è combinatoria (unrolled) → molti moltiplicatori. Se l'area esplode oltre il 7020,
converti al pattern time-mux (1 MAC/ciclo con FSM + `hdl.RAM`) come `snn_b2_fsm` — ma prova prima così: il
`report_power` con SAIF misura comunque l'energia; se la sintesi non chiude, allora time-mux (Task C1 bis).

- [ ] **Step 3: Commit**

```bash
git add matlab/gen_ann_rom.m matlab/ann_mlp.m
git commit -m "feat(fase-b): sorgente ANN densa 4-32-32-5 + generatore ROM pesi"
```

### Task C2: Parità ANN (determinismo double-vs-fixed)

**Files:**
- Create: `matlab/test_ann_mlp.m`

- [ ] **Step 1: Scrivi il test**

```matlab
function test_ann_mlp()
%TEST_ANN_MLP  La ANN produce un'uscita finita e deterministica; fixed ~ double (sanity, non golden).
  here = fileparts(mfilename('fullpath')); addpath(here);
  if ~isfile(fullfile(here, 'ann_rom.m')); gen_ann_rom(); end
  xn = fi([0.6; 0.3; 0.05; 0.3], 1, 19, 13);
  [o1, v1] = ann_mlp(xn, true);
  assert(v1, 'valid deve essere true su start');
  assert(all(isfinite(double(o1))), 'uscita non finita');
  [~, v0] = ann_mlp(xn, false);
  assert(~v0, 'valid deve essere false senza start');
  fprintf('TEST_ANN_MLP OK: out=%s\n', mat2str(double(o1)', 4));
end
```

- [ ] **Step 2: Esegui**

Run: `cd matlab && matlab -batch "test_ann_mlp"`
Expected: `TEST_ANN_MLP OK: out=[...]` con 5 valori finiti.

- [ ] **Step 3: Commit**

```bash
git add matlab/test_ann_mlp.m matlab/ann_rom.m
git commit -m "test(fase-b): sanity/determinismo ANN densa"
```

### Task C3: Codegen VHDL della ANN

**Files:**
- Create: `matlab/make_hdl_ann.m`

- [ ] **Step 1: Scrivi `make_hdl_ann.m`**

```matlab
function make_hdl_ann()
%MAKE_HDL_ANN  Codegen VHDL della ANN densa (mirror make_hdl_b2fsm).
  here = fileparts(mfilename('fullpath')); addpath(here);
  xn = fi(zeros(4, 1), 1, 19, 13);
  start = false;
  cfg = coder.config('hdl');
  cfg.TargetLanguage = 'VHDL';
  cfg.GenerateHDLTestBench = false;
  cfg.SimulateGeneratedCode = false;
  try, cfg.HDLLintTool = 'None'; catch, end
  fprintf('== codegen HDL ANN ==\n');
  codegen('-config', cfg, 'ann_mlp', '-args', {xn, start}, '-report');
  fprintf('OK: ann_mlp RTL generato\n');
end
```

- [ ] **Step 2: Esegui + GATE**

Run: `cd matlab && matlab -batch "make_hdl_ann"`
Expected: `OK: ann_mlp RTL generato`; RTL in `matlab/codegen/ann_mlp/hdlsrc/`. Se codegen fallisce → gotcha HDL.

- [ ] **Step 3: Commit**

```bash
git add matlab/make_hdl_ann.m
git commit -m "feat(fase-b): codegen VHDL ANN densa"
```

### Task C4: TB + Tcl potenza ANN → E_ann

**Files:**
- Create: `matlab/axi/phase_b/tb_ann_stream.v`, `matlab/axi/build/phase_b/power_ann.tcl`

- [ ] **Step 1: Scrivi `tb_ann_stream.v`** (guida ann_mlp con lo stimolo tipico)

```verilog
`timescale 1ns/1ps
module tb_ann_stream;
  localparam NROW = 512;
  reg clk = 0, rst = 0, start = 0;
  reg  [75:0] xn = 0;
  wire [104:0] out;
  wire valid;
  reg  [18:0] mem [0:NROW*4-1];
  integer r;
  ann_mlp dut (.clk(clk), .reset(rst), .clk_enable(1'b1),
               .xn(xn), .start(start), .out(out), .out_valid(valid));  // adegua ai nomi RTL
  always #5 clk = ~clk;
  initial begin
    $readmemh("stim_typical.mem", mem);
    rst = 1; repeat (8) @(posedge clk); rst = 0;
    for (r = 0; r < NROW; r = r + 1) begin
      xn = {mem[r*4+0], mem[r*4+1], mem[r*4+2], mem[r*4+3]};
      @(posedge clk); start = 1; @(posedge clk); start = 0;
      while (!valid) @(posedge clk);
    end
    $display("ANN_STREAM_DONE"); $finish;
  end
endmodule
```

Nota: i nomi porta del top ANN (`xn`, `start`, `out`, `out_valid`, più `clk/reset/clk_enable`) vanno letti
dal VHDL generato e allineati.

- [ ] **Step 2: Scrivi `power_ann.tcl`** (stessa struttura di `power_micro.tcl`, top `ann_mlp`)

```tcl
# power_ann.tcl — synth+impl OOC ANN densa, SAIF, report_power.
set BASE "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
set OUT  "$BASE/matlab/axi/build/phase_b"
set ROOT "D:/zbd_ann"
file delete -force $ROOT
create_project ann $ROOT -part xc7z020clg400-1 -force
add_files [glob "$BASE/matlab/codegen/ann_mlp/hdlsrc/*.vhd"]
set_property top ann_mlp [current_fileset]
set xdc "$ROOT/clk.xdc"
set f [open $xdc w]; puts $f "create_clock -name clk -period 10.000 \[get_ports clk\]"; close $f
add_files -fileset constrs_1 $xdc
launch_runs impl_1 -jobs 6
wait_on_run impl_1
open_run impl_1
report_utilization -file "$OUT/util_ann.rpt"
report_timing_summary -file "$OUT/timing_ann.rpt"
file copy -force "$BASE/matlab/axi/phase_b/stim_typical.mem" "$ROOT/stim_typical.mem"
add_files -fileset sim_1 "$BASE/matlab/axi/phase_b/tb_ann_stream.v"
set_property top tb_ann_stream [get_filesets sim_1]
set simtcl "$ROOT/sim.tcl"
set s [open $simtcl w]
puts $s "open_saif \"$OUT/ann.saif\""
puts $s "log_saif \[get_objects -r /tb_ann_stream/dut/*\]"
puts $s "run all"; puts $s "close_saif"; puts $s "quit"
close $s
set_property -name {xsim.simulate.custom_tcl} -value $simtcl -objects [get_filesets sim_1]
launch_simulation -mode post-implementation -type timing
close_sim
read_saif "$OUT/ann.saif"
report_power -file "$OUT/power_ann.rpt"
puts "DONE-POWER-ANN"
```

- [ ] **Step 3: Esegui** (background)

Run: `cd /d/zrun && "C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat" -mode batch -source ".../power_ann.tcl"`
Expected: `DONE-POWER-ANN`; `power_ann.rpt`, `util_ann.rpt`. `util_ann.rpt` deve mostrare **molti DSP**
(l'ANN usa i DSP48 per i MAC) — è il contrasto architetturale col B2.

- [ ] **Step 4: GATE** — confidenza ≥ Media; se la sim ANN non chiude timing/area, converti al time-mux (nota Task C1 Step 2) e rifai.

- [ ] **Step 5: Commit**

```bash
git add matlab/axi/phase_b/tb_ann_stream.v matlab/axi/build/phase_b/power_ann.tcl matlab/axi/build/phase_b/power_ann.rpt matlab/axi/build/phase_b/util_ann.rpt
git commit -m "feat(fase-b): potenza ANN densa matched -> E_ann"
```

---

## GRUPPO D — Raccolta e deliverable

### Task D1: Collector dei risultati

**Files:**
- Create: `matlab/axi/build/phase_b/collect_results.py`

- [ ] **Step 1: Scrivi il collector**

```python
#!/usr/bin/env python3
"""collect_results.py — parse i .rpt Vivado -> results.csv + calcoli Fase B.
Uso: python collect_results.py <dir con i .rpt>  (default: cartella dello script)."""
import re, sys, os, csv

FCLK = 100e6            # Hz, clock dei micro/ANN (piccoli -> chiudono a 100 MHz)
FCLK_B2 = 8e6          # Hz, Fclk REALE del B2 (lane ~8.5 MHz)
E_AC_HOROWITZ = 0.9     # pJ (45nm)
E_MAC_HOROWITZ = 4.6    # pJ (45nm)

def read(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()

def total_dynamic_w(txt):
    m = re.search(r"Dynamic\s*\(W\)\s*\|\s*([\d.]+)", txt) or \
        re.search(r"Total On-Chip Power \(W\)\s*\|\s*([\d.]+)", txt)
    return float(m.group(1)) if m else None

def confidence(txt):
    m = re.search(r"Confidence[^\|]*\|\s*(\w+)", txt)
    return m.group(1) if m else "Unknown"

def dsp_count(txt):
    m = re.search(r"DSP48[^\|]*\|\s*(\d+)", txt) or re.search(r"\bDSPs?\b[^\|]*\|\s*(\d+)", txt)
    return int(m.group(1)) if m else None

def main():
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    rows = []
    def grab(tag, power_rpt, util_rpt=None):
        pp = os.path.join(d, power_rpt)
        if not os.path.isfile(pp):
            rows.append({"item": tag, "note": "MANCANTE " + power_rpt}); return None
        t = read(pp)
        pw = total_dynamic_w(t)
        row = {"item": tag, "P_dyn_W": pw, "confidence": confidence(t)}
        if util_rpt and os.path.isfile(os.path.join(d, util_rpt)):
            row["DSP"] = dsp_count(read(os.path.join(d, util_rpt)))
        rows.append(row); return pw

    # micro -> e_op = P_dyn / Fclk (1 op/ciclo), in pJ
    p_ac  = grab("micro_ac",  "power_micro_ac.rpt",  "util_micro_ac.rpt")
    p_mac = grab("micro_mac", "power_micro_mac.rpt", "util_micro_mac.rpt")
    e_ac = e_mac = None
    if p_ac:  e_ac  = p_ac  / FCLK * 1e12
    if p_mac: e_mac = p_mac / FCLK * 1e12

    # B2 sistema (typical/worst) -> E/inf = P_dyn * cicli/Fclk ; cicli letti dal log (default 340)
    cycles = int(os.environ.get("CICLI_INF", "340"))
    for lab in ("typical", "worst"):
        p = grab("B2_" + lab, f"power_b2_{lab}.rpt", "util_b2_flat.rpt")
        if p: rows[-1]["E_inf_pJ"] = p * cycles / FCLK_B2 * 1e12   # B2 gira a 8 MHz

    # ANN
    grab("ANN", "power_ann.rpt", "util_ann.rpt")

    print("=== costanti node-correct (28nm) ===")
    if e_ac and e_mac:
        print(f"e_AC  = {e_ac:.4f} pJ/op  (Horowitz 45nm: {E_AC_HOROWITZ})")
        print(f"e_MAC = {e_mac:.4f} pJ/op  (Horowitz 45nm: {E_MAC_HOROWITZ})")
        print(f"rapporto e_MAC/e_AC = {e_mac/e_ac:.2f}  (Horowitz: {E_MAC_HOROWITZ/E_AC_HOROWITZ:.2f})")

    out = os.path.join(d, "results.csv")
    keys = sorted({k for r in rows for k in r})
    with open(out, "w", newline="") as f:
        wcsv = csv.DictWriter(f, fieldnames=keys); wcsv.writeheader(); wcsv.writerows(rows)
    print("scritto", out)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Esegui**

Run: `python matlab/axi/build/phase_b/collect_results.py matlab/axi/build/phase_b`
Expected: stampa e_AC/e_MAC @28nm + rapporto vs Horowitz; scrive `results.csv`.
Se un `.rpt` è "MANCANTE" → quel Tcl non è stato eseguito: torna al gruppo relativo.

- [ ] **Step 3: Commit**

```bash
git add matlab/axi/build/phase_b/collect_results.py matlab/axi/build/phase_b/results.csv
git commit -m "feat(fase-b): collector .rpt -> results.csv + costanti node-correct"
```

### Task D2: Deliverable `FPGA_PHASE_B_POWER.md`

**Files:**
- Create: `document/FPGA_PHASE_B_POWER.md`

- [ ] **Step 1: Scrivi il deliverable** — riempi con i numeri REALI da `results.csv`/`.rpt` (niente placeholder nei valori)

Struttura (compila ogni `<...>` con i numeri veri; le righe restano solo se il numero esiste):

```markdown
# FPGA Fase B — Power Analysis (Donatello B2, PYNQ-Z1 28nm)

> Addendum drop-in per `report/FPGA_REPORT.md`. Livello di fedeltà: **stima Vivado post-impl con switching
> reale (SAIF)** — NON silicio (Fase C, rinviata-predisposta). Provenienza per ogni numero in tabella.

## Tabella di validazione claim-by-claim
| Claim Fase A | Fase A | Fase B (reale) | Esito | Provenienza |
|---|---|---|---|---|
| DSP = 0 | 0 | <n> (di cui decode <n>, snn_core <n>, AXI <n>) | <CONFERMATA/CORRETTA> | util_b2_hier.rpt |
| BRAM <1% | <1 | <n> tile | <...> | util_b2_flat.rpt |
| Fmax 100-200 MHz | assunto | <n> MHz (lane) | CORRETTA | timing_b2.rpt |
| e_AC / e_MAC | 0.9 / 4.6 pJ (45nm) | <e_ac> / <e_mac> pJ (28nm) | CORRETTA (nodo) | power_micro_*.rpt |
| Energia/inf SNN | ~<400-1200> pJ (algoritmica) | <E_inf> pJ (realizzata) | <...> | power_b2_*.rpt |
| Vantaggio SNN/ANN | 5.11-8.38× / ~15× | <sistema>× · <formula>× | <...> | power_ann.rpt + results.csv |
| Termica Tj | stima | <Tj> °C (non-problema) | CONFERMATA | power_b2_*.rpt |

## Findings
1. **Energia realizzata vs algoritmica** (§2b spec): <numeri + sweep Fclk se fatto>.
2. **MAC-su-DSP48** (§2c spec): rapporto e_MAC/e_AC reale = <x> vs Horowitz 5.1 → <commento sul vantaggio>.
3. **Attribuzione 38 DSP**: <dove stanno; claim "0 DSP sinapsi" confermata/smentita>.

## Mappa di re-tag (per il merge nel report)
<le righe della §4.2 della spec, con l'esito reale>

## Appendice — Protocollo Fase C (predisposto, non eseguito)
Misura su PYNQ-Z1 fisica: delta potenza rail idle-vs-inferenza. Carica `matlab/axi/build/snn_b2_donatello.bit`,
stream tipico = `matlab/axi/phase_b/stim_typical.mem`. Colonna "Fase C misurato" della tabella = TBD.

## Onestà
Tutti i numeri sopra sono **stime Vivado** con switching reale (confidenza ≥ Media nei .rpt), non misure su
silicio. Ground-truth finale = Fase C.
```

- [ ] **Step 2: Verifica assenza placeholder nei valori**

Run: `grep -nE "<[a-z]|TBD|TODO" document/FPGA_PHASE_B_POWER.md`
Expected: solo il `TBD` **intenzionale** della colonna Fase C. Ogni `<...>` di valore va sostituito con un
numero reale. Se restano `<...>` di valore → il deliverable è incompleto.

- [ ] **Step 3: Commit**

```bash
git add document/FPGA_PHASE_B_POWER.md
git commit -m "docs(fase-b): deliverable power analysis con numeri reali + re-tag + protocollo Fase C"
```

### Task D3: Aggiorna documentazione di stato + push

**Files:**
- Modify: `document/SESSION_RESUME.md`, `document/HDL_ARCHITECTURE_STUDY.md`

- [ ] **Step 1: Aggiungi una riga di stato** in `SESSION_RESUME.md` e `HDL_ARCHITECTURE_STUDY.md`: "Fase B power analysis FATTA — vedi `document/FPGA_PHASE_B_POWER.md` (e_AC/e_MAC @28nm, DSP attribuiti, vantaggio rivisto, Tj non-problema)".

- [ ] **Step 2: Commit + push**

```bash
git add document/SESSION_RESUME.md document/HDL_ARCHITECTURE_STUDY.md
git commit -m "docs(fase-b): stato aggiornato con la power analysis completata"
git push origin Simulink_Importer
```

- [ ] **Step 3: Aggiorna la memoria di ripresa** `cf-fsnn-parallel-tracks.md` (sezione Simulink_Importer) con "Fase B power FATTA".

---

## Note di rischio (leggi prima di eseguire)
- **SAIF plumbing**: `launch_simulation -mode post-implementation -type timing` + `open_saif/log_saif/close_saif` è il flusso previsto; se questa build di Vivado differisce, il gate copertura lo cattura — investiga, non accettare vectorless.
- **ANN combinatoria**: `ann_mlp` unrolled può non chiudere su 7020 → fallback time-mux (nota Task C1). La potenza si misura comunque; conta solo che sintetizzi e usi i DSP.
- **Nomi porta RTL**: HDL Coder genera `clk/reset/clk_enable/<out>/<out>_valid`; ogni TB va allineato leggendo il VHDL generato (passo esplicito in ogni task TB).
- **Path 260-byte**: progetti sempre in `D:/zbd_*` corti.
