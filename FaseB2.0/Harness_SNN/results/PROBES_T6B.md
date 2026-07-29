# Probe T6b — assunzioni HW trasformate in fatti (2026-07-29)

Eseguiti **prima** di scrivere il piano T6b (metodo *probe-first*, appreso in T6a dove 4 assunzioni non verificate
sono diventate 4 fix in esecuzione). Riproducibili: `bash hw/run_probes_t6b.sh` (work-dir `D:/zbd_tier_hw`).

| # | Assunzione dello spec | Verdetto | Conseguenza per il piano |
|---|---|---|---|
| **P1** | `ce_out` utilizzabile come **done/valid** | ❌ **FALSA** | wrapper AXI con **contatore di latenza** (364 clk), non `ce_out` |
| **P2** | wrapper **Verilog** su DUT **VHDL** sintetizzabile | ✅ **VERA** | wrapper in Verilog, nessun flat wrapper VHDL |
| **P3** | board preset **PYNQ-Z1** disponibile | ✅ **VERA** (con repoPaths) | `set_param board.repoPaths` **obbligatorio** prima di `get_board_parts` |
| **P4** | BD con **PS7** headless + **FCLK** parametrizzabile | ✅ **VERA** | clock del sistema via `CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ` |

## P1 — `ce_out` è un clock-enable, NON un done ⚠️

```
P1 CEOUT    @cyc 1,2,3,4,5,6,7,8,9,10,11,12 …   (alto a OGNI ciclo)
P1 PARAMCHG @cyc 364 (step 0) · @cyc 865 (step 1) · @cyc 1365 (step 2)
P1 TOTALI: ce_out alto 1500 volte su 1500 cicli | cambi di v0 = 3 (attesi 3 = 1/control-step)
```

`ce_out` è alto **1500/1500 cicli** ⇒ è il **clock-enable** del design multi-rate generato da HDL Coder, non un
segnale di fine-inferenza. Usarlo come `done` nel wrapper AXI avrebbe fatto leggere al PS parametri **non pronti**.

Il probe fornisce anche il **rimpiazzo, misurato**: le uscite cambiano **una volta per control-step**, a
`cyc 364 / 865 / 1365` — passo 500 (`HOLD`), **latenza 364 clock** (coerente con la LAT di T6a).
→ **Il wrapper AXI genera `done` con un contatore**: `done <= 1` dopo **364** clock dal commit degli ingressi
(margine consigliato: soglia parametrica `LAT_CLK`, default 364, verificata dal cancello di cosim).

## P2 — sintesi mixed-language riuscita

`probe_wrap.v` (Verilog) istanzia `Donatello_Tier` (VHDL) e **sintetizza** (`synth_design -mode out_of_context`).
Utilizzo post-synth OOC **indicativo** (non post-route): **4461 LUT · 2354 FF · 52 DSP · 1 BRAM**.
→ Nota: la **BRAM compare già qui** (1 tile) — il full-impl di T6b la catturerà (era il gap dei run OOC precedenti).

## P3 — board PYNQ-Z1 presente, ma il repo va impostato

Al primo giro il probe rispondeva "PYNQ non trovata": **difetto del probe**, non della macchina — non impostava il
repo. Con `set_param board.repoPaths [list "C:/AMDDesignTools/Boards_Drivers"]` (come `axi/build/bitstream_board.tcl`
della Fase B): **4 board parts**, fra cui `www.digilentinc.com:pynq-z1:part0:1.0`.
Riscontro indipendente: `matlab/axi/build/snn_b2_donatello.hwh` riporta `BOARD="www.digilentinc.com:pynq-z1:part0:1.0"`.

## P4 — block design PS7 headless, FCLK parametrizzabile

PS7 `xilinx.com:ip:processing_system7:5.5` istanziato, board part applicata, `validate_bd_design` OK **headless**.
`CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ` impostato e riletto a **8 / 50 / 100 MHz**.
⚠️ I valori FCLK reali sono quantizzati dai divisori della PLL: la ricerca dell'Fmax userà **candidati discreti**
(non una ricerca continua), verificando ogni volta il WNS.

## Nota di metodo

**2 probe su 4 erano difettosi al primo giro** (P2: `get_property` su una stringa; P3: repoPaths non impostato) e
davano verdetti *falsi ma plausibili* — «PYNQ non trovata» avrebbe portato a progettare un flusso senza board preset.
Vale anche per i probe la regola dei cancelli: **un probe che sbaglia in silenzio produce una conclusione falsa**;
prima di fidarsi del verdetto va controllato il meccanismo (qui: il confronto con ciò che la Fase B aveva già fatto).
