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
# 5. bitstream    : vivado -mode batch -source build/bitstream_board.tcl (board preset PYNQ-Z1 -> .bit + .xsa)
#    (usa ROOT corto D:/zbd per evitare il limite 260-byte path Windows; board files in
#     C:/AMDDesignTools/Boards_Drivers; bitstream2.tcl = variante vecchia con PS7 generica)
```

## Fase 3 — Bitstream (FATTO ✅, board PYNQ-Z1 reale)
Block design Zynq con **board preset PYNQ-Z1** (`www.digilentinc.com:pynq-z1:part0:1.0` — DDR3/MIO/clock reali
della board) **+ questo IP + AXI SmartConnect** → implementation → deliverable in `build/`:
- **`snn_b2_donatello.bit`** — bitstream flashabile (4.0 MB)
- **`snn_b2_donatello.hwh`** — hardware handoff (mappa indirizzi/IP; richiesto da PYNQ `Overlay`, stesso basename del `.bit`)
- **`snn_b2_donatello.xsa`** — platform handoff completo per Vitis (contiene `.bit` + `.hwh`)

**Timing-clean**: FCLK0 = **8 MHz**, WNS **+6.97 ns** ("All constraints met"). Path combinatorio lane SNN ~118 ns
→ ~8.5 MHz Fmax; 8 MHz basta (servono ~kHz per control-step 0.1 s). Base slave (M_AXI_GP0): **`0x4000_0000`**.
Util full-system: LUT ~4.5k (8.5%), FF ~2.3k, DSP 38, 1 BRAM tile. Build: `build/bitstream_board.tcl`.

### Uso su PYNQ-Z1 (Python)
```python
from pynq import Overlay
ol = Overlay("snn_b2_donatello.bit")     # richiede snn_b2_donatello.hwh nello stesso path
ip = ol.snn0                             # IP AXI-Lite @ 0x4000_0000
# normalizza xn in float sul PS -> Q?.13 interi con segno, poi:
for i, x in enumerate(xn_fixed):
    ip.write(0x00 + 4*i, int(x) & 0xFFFFFFFF)   # xn0..xn3
ip.write(0x10, 1); ip.write(0x10, 0)     # pulse start (fronte)
while ip.read(0x10) & 1 == 0:            # poll done
    pass
params = [ip.read(0x14 + 4*i) for i in range(5)]   # p0..p4 in Q7.13 -> /8192
```

## Chain completo
`PyTorch → snn_core (double, parità 2e-6) → fixed Q?.13 → snn_b2_fsm (hdl.RAM, bit-exact) → decode σ-LUT →
top → AXI4-Lite (cosim PASSED) → block design PS7 → bitstream PYNQ-Z1 (timing-clean)`. Tutto headless.
