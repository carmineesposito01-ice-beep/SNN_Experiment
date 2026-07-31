#!/usr/bin/env bash
# Cosim AXI del composto (T7b): per ogni scenario scrive i 4 ingressi via AXI, fa UN commit, attende
# `done` e legge l'accel, confrontandola col golden del BLOCCO. Una simulazione per scenario: lo stato
# SNN vive nella hdl.RAM e si azzera solo all'init (finding T6a).
#
# args: ROOT HDLSRC_DIR WRAPPER TB NSCEN NSTEP GATEMODE
#   ROOT deve essere SENZA SPAZI (il repo sta sotto ".../1.Reti Neurali/...": xsim/glob si spezzano).
#   In ROOT devono gia' esistere axi_stim_<i>.mem e axi_gold_<i>.mem per i=1..NSCEN (gen_axi_golden.m).
#
# ⚠️ `glbl` va COMPILATO oltre a passare -L unisims_ver: BUFGCE e' una primitiva unisim che lo referenzia,
#    altrimenti xelab fallisce con "'glbl' is not declared" (HDL_PHASE §9.3).
set -e
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
ROOT="$1"; HDLSRC="$2"; WRAP="$3"; TB="$4"; NSCEN="$5"; NSTEP="$6"; GM="$7"

[ -d "$HDLSRC" ] || { echo "HDLSRC inesistente: $HDLSRC"; exit 1; }
cd "$ROOT"
rm -rf xsim.dir *.jou hdl; mkdir hdl
cp "$HDLSRC"/*.v hdl/; cp "$HDLSRC/compile_order.txt" hdl/
WN="$(basename "$WRAP")"; cp "$WRAP" .
TBN="$(basename "$TB")";  cp "$TB" .

# CANCELLO PRELIMINARE: gli stimoli e i golden devono esserci TUTTI prima di iniziare.
# Senza, la mancanza si scoprirebbe a meta' run -- ore dopo.
miss=0
for ((i=1; i<=NSCEN; i++)); do
  [ -s "axi_stim_$i.mem" ] || { echo "manca axi_stim_$i.mem"; miss=1; }
  [ -s "axi_gold_$i.mem" ] || { echo "manca axi_gold_$i.mem"; miss=1; }
done
[ $miss -eq 0 ] || { echo "COSIM-ABORT: stimoli/golden incompleti"; exit 1; }

printf '`define NSTEP %s\n`define GATEMODE %s\n`define CLKHALF 5\n' "$NSTEP" "$GM" > axi_params.vh

mapfile -t ORD < hdl/compile_order.txt
for f in "${ORD[@]}"; do
  [ -n "$f" ] || continue
  "$VIV/xvlog.bat" "hdl/$f" > "c_$f.log" 2>&1 || { echo "xvlog FALLITO su $f:"; tail -30 "c_$f.log"; exit 1; }
done
"$VIV/xvlog.bat" "$WN" > w_xvlog.log 2>&1 || { echo "xvlog wrapper FALLITO:"; tail -30 w_xvlog.log; exit 1; }
"$VIV/xvlog.bat" "$VIV/../data/verilog/src/glbl.v" > g_xvlog.log 2>&1 || { tail -20 g_xvlog.log; exit 1; }
"$VIV/xvlog.bat" -i . "$TBN" > tb_xvlog.log 2>&1 || { echo "xvlog TB FALLITO:"; tail -30 tb_xvlog.log; exit 1; }
"$VIV/xelab.bat" -debug typical "${TBN%.v}" glbl -L unisims_ver -s cosim_g$GM > xelab.log 2>&1 \
  || { echo "xelab FALLITO:"; tail -40 xelab.log; exit 1; }

tot=0; nmis=0
for ((i=1; i<=NSCEN; i++)); do
  cp "axi_stim_$i.mem" axi_stim.mem; cp "axi_gold_$i.mem" axi_gold.mem
  "$VIV/xsim.bat" "cosim_g$GM" -R > "cos_${GM}_$i.log" 2>&1
  line=$(grep -ao "AXI-COSIM nMismatch=[0-9]* n=[0-9]*" "cos_${GM}_$i.log" | head -1)
  [ -n "$line" ] || { echo "SCENARIO $i (gm=$GM): nessun risultato"; tail -30 "cos_${GM}_$i.log"; exit 1; }
  m=$(echo "$line" | sed 's/.*nMismatch=\([0-9]*\).*/\1/')
  n=$(echo "$line" | sed 's/.*n=\([0-9]*\).*/\1/')
  nmis=$((nmis+m)); tot=$((tot+n))
  [ "$m" = "0" ] || echo "  scenario $i (gm=$GM): $m disallineamenti"
done
echo "COSIM-DONE gatemode=$GM nMismatch=$nmis n=$tot nscen=$NSCEN"
