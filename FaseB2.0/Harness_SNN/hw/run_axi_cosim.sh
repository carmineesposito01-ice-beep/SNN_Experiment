#!/usr/bin/env bash
# Cosim AXI di tier_axi_lite: compila UNA volta, poi rifa xsim -R per OGNI traiettoria
# (la hdl.RAM del Tier si azzera solo all'init della simulazione -> una traiettoria per simulazione).
# args: ROOT HDLSRC HWDIR NSTEP NTRAJ GATEMODE
#   ROOT     = work-dir corta senza spazi (es. D:/zbd_tier_hw); i .mem stim_axi_<i>/gold_axi_<i> stanno qui
#   GATEMODE = 0 (clock libero, riferimento) | 1 (clock gating attivo)
set -u
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
ROOT="$1"; HDLSRC="$2"; HWDIR="$3"; NSTEP="$4"; NTRAJ="$5"; GATEMODE="$6"
cd "$ROOT"
rm -rf xsim.dir *.jou *.log *.pb hdl hw; mkdir hdl hw
cp "$HDLSRC"/*.vhd hdl/
cp "$HDLSRC/compile_order.txt" hdl/
cp "$HWDIR"/tier_axi_lite.v "$HWDIR"/tb_tier_axi.v hw/
printf '`define NSTEP %s\n`define GATEMODE %s\n' "$NSTEP" "$GATEMODE" > axi_params.vh

while read -r f; do
  [ -z "$f" ] && continue
  "$VIV/xvhdl.bat" "hdl/$f" > /dev/null 2>&1 || { echo "ERRORE xvhdl su $f"; exit 1; }
done < hdl/compile_order.txt
# glbl.v: il modello unisim di BUFGCE referenzia `glbl` (global set/reset Xilinx) -> va COMPILATO nella work,
# altrimenti xelab fallisce con "'glbl' is not declared" / "Cannot find design unit work.glbl".
GLBL="C:/AMDDesignTools/2026.1/Vivado/data/verilog/src/glbl.v"
"$VIV/xvlog.bat" -i . hw/tier_axi_lite.v hw/tb_tier_axi.v "$GLBL" > xvlog.out 2>&1 || { echo "ERRORE xvlog"; tail -5 xvlog.out; exit 1; }
# -L unisims_ver: primitive Xilinx (BUFGCE) · glbl come secondo top
"$VIV/xelab.bat" -debug off -L unisims_ver tb_tier_axi glbl -s snapAXI > xelab.out 2>&1 || { echo "ERRORE xelab"; tail -8 xelab.out; exit 1; }

tot=0; ntot=0; inf=0; infexp=0
for ((i=1; i<=NTRAJ; i++)); do
  cp "stim_axi_${i}.mem" axi_stim.mem
  cp "gold_axi_${i}.mem" axi_gold.mem
  o=$("$VIV/xsim.bat" snapAXI -R 2>&1)
  # stampa le righe diagnostiche del TB (PROBE/errori): NON vanno ingoiate, servono a diagnosticare i fallimenti
  printf '%s\n' "$o" | grep -E "^(PROBE|DBG|ERROR|FATAL)" | head -30
  nm=$(printf '%s\n' "$o" | sed -n 's/.*AXI-COSIM nMismatch=\([0-9]*\) .*/\1/p' | head -1)
  nn=$(printf '%s\n' "$o" | sed -n 's/.*AXI-COSIM nMismatch=[0-9]* n=\([0-9]*\).*/\1/p' | head -1)
  ii=$(printf '%s\n' "$o" | sed -n 's/.*SYNC inferenze=\([0-9]*\) .*/\1/p' | head -1)
  ie=$(printf '%s\n' "$o" | sed -n 's/.*SYNC inferenze=[0-9]* attese=\([0-9]*\).*/\1/p' | head -1)
  tot=$((tot + ${nm:-0})); ntot=$((ntot + ${nn:-0}))
  inf=$((inf + ${ii:-0})); infexp=$((infexp + ${ie:-0}))
done
echo "AXI-COSIM-TOT nMismatch=$tot n=$ntot"
echo "SYNC-TOT inferenze=$inf attese=$infexp"
