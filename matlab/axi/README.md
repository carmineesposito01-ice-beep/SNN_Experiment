# Wrapper AXI4-Lite — SNN Donatello B2 (Fase 2b)

IP AXI4-Lite che espone `snn_top_b2` (SNN B2 + decode) al PS della Zynq. Generato via strada
**Tcl headless** (Vivado `create_peripheral` per il protocollo AXI + logica registri custom),
sintetizzato e **verificato in cosim** (2026-07-10).

## File
- `snn_top_b2_flat.vhd` — wrapper VHDL: appiattisce le porte composite di `snn_top_b2`
  (`xn` 4×19b, `params` 5×21b) a `std_logic_vector` piatti (istanziabile da Verilog).
- `snn_b2_axi_lite.v` — slave AXI4-Lite (16 registri, protocollo dal template Vivado) con
  `snn_top_b2_flat` innestato, start-pulse (fronte del control) e read-mux dei params.
- `axi_tb.v` — testbench master AXI (write xn → start → poll done → read params → check).

## Mappa registri (offset dal base address AXI)
| offset | dir | contenuto |
|---|---|---|
| `0x00–0x0C` | W | `xn[0..3]` normalizzati (Q5.13, 19b nei bit[18:0]) |
| `0x10` | W | `control` — bit0 = **start** (pulse sul fronte di salita) |
| `0x10` | R | `status` — bit0 = **done** |
| `0x14–0x24` | R | `params[0..4]` = v0,s0,a,b,T (Q7.13, sign-ext a 32b) |

**Driver PS:** normalize in SW float → scrivi `xn[0..3]` → scrivi `control=1` poi `0` →
poll `status.done` → leggi `params[0..4]` → converti da Q7.13 (`/8192.0`).

## Risultati
- **Synth OOC** (xc7z020, SNN+decode+AXI): LUT 4.756 (8.9%), DSP 38 (17%), 2 BRAM. 0 errori.
- **Cosim AXI** (xsim): `AXI TEST PASSED` — params letti = bit-exact a `snn_top_b2` (v0=26.49, ...).
- Latenza: ~340 clock/inferenza (irrilevante: control-step 0.1 s).

## Riproduzione (headless) — script in `build/`
```
# 1. RTL SNN+decode: matlab -batch "make_hdl_top_b2"       (in matlab/)
# 2. IP AXI       : vivado -mode batch -source build/axi_gen.tcl   (create_peripheral)
# 3. synth-verify : vivado -mode batch -source build/axi_synth.tcl (0 errori, 8.9% LUT)
# 4. cosim        : xvhdl <snn> snn_top_b2_flat.vhd; xvlog snn_b2_axi_lite.v axi_tb.v; xelab work.axi_tb; xsim -R
# 5. bitstream    : vivado -mode batch -source build/bitstream2.tcl (package -> BD PS7 -> impl -> .bit)
#    (usa ROOT corto per evitare il limite 260-byte path Windows)
```

## Fase 3 — Bitstream (FATTO ✅)
Block design Zynq (**PS7 + questo IP + AXI SmartConnect**) → implementation → **`build/snn_b2_donatello.bit`**
(PYNQ-Z1, xc7z020, 3.9 MB). **Timing-clean** con **FCLK0 = 8 MHz** (WNS **+7 ns**; il path combinatorio della lane
SNN è ~118 ns → ~8.5 MHz Fmax — 8 MHz basta: servono ~kHz per control-step 0.1 s). Address base slave (M_AXI_GP0):
**`0x4000_0000`**. Utilizzo full-system: LUT 4.527 (8.5%), FF 2.288, DSP 38, 1 BRAM tile. **Nota:** senza board file
PYNQ-Z1 → config PS7 generica; per il deploy reale ri-generare con i board files della PYNQ-Z1 (DDR/MIO corretti).

## Chain completo
`PyTorch → snn_core (double, parità 2e-6) → fixed Q?.13 → snn_b2_fsm (hdl.RAM, bit-exact) → decode σ-LUT →
top → AXI4-Lite (cosim PASSED) → block design PS7 → bitstream PYNQ-Z1 (timing-clean)`. Tutto headless.
