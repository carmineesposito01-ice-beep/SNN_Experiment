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

## Riproduzione (headless)
```
# 1. RTL SNN+decode: matlab -batch "make_hdl_top_b2"  (in matlab/)
# 2. IP AXI: vivado -mode batch -source axi_gen.tcl   (create_peripheral)
# 3. synth : vivado -mode batch -source axi_synth.tcl
# 4. cosim : xvhdl <snn sources> snn_top_b2_flat.vhd; xvlog snn_b2_axi_lite.v axi_tb.v; xelab work.axi_tb; xsim -R
```

## Prossimo (Fase 3)
Block design Zynq (PS + questo IP + AXI interconnect) → implementation → `.bit` per PYNQ-Z1.
