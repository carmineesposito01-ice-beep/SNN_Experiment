#!/usr/bin/env bash
# Esegue i 4 probe di T6b (P1 xsim + P2/P3/P4 Vivado) e stampa tutto su stdout.
# Uso: bash run_probes_t6b.sh    (dalla cartella hw/). Work-dir: D:/zbd_tier_hw (corta, senza spazi).
set -u
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
HERE="$(cd "$(dirname "$0")" && pwd)"
HDL_SRC="$HERE/../../../matlab/hdlsrc_donatello_tier/rtlgen_mdl"
ROOT="D:/zbd_tier_hw"

mkdir -p "$ROOT"; cd "$ROOT"
rm -rf xsim.dir *.jou *.log *.pb hdl hw; mkdir hdl hw
cp "$HDL_SRC"/*.vhd hdl/
cp "$HDL_SRC/compile_order.txt" hdl/
cp "$HERE"/probe_ceout_tb.v "$HERE"/probe_wrap.v hw/

echo "########## P1 — semantica di ce_out (xsim) ##########"
while read -r f; do
  [ -z "$f" ] && continue
  "$VIV/xvhdl.bat" "hdl/$f" > /dev/null 2>&1 || echo "P1 ERRORE xvhdl su $f"
done < hdl/compile_order.txt
"$VIV/xvlog.bat" hw/probe_ceout_tb.v > /dev/null 2>&1 || echo "P1 ERRORE xvlog"
"$VIV/xelab.bat" -debug off probe_ceout_tb -s snapP1 > /dev/null 2>&1 || echo "P1 ERRORE xelab"
"$VIV/xsim.bat" snapP1 -R 2>&1 | grep -E "^P1 "

echo
echo "########## P2/P3/P4 — Vivado (mixed-language synth, board preset, BD+PS7) ##########"
"$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog \
  -source "$HERE/probe_t6b.tcl" -tclargs "$ROOT/hdl" "$ROOT/hw" 2>&1 \
  | grep -E "^(P2|P3|P4|=====)"
echo
echo "PROBES-DONE"
