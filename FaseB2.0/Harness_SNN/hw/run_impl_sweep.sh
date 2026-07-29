#!/usr/bin/env bash
# T6b · M2 — sweep FCLK: un'invocazione Vivado per candidato (isolamento + determinismo).
# Copia i sorgenti nella work-dir CORTA (il path del repo contiene spazi e add_files li spezza), poi implementa
# a ciascun FCLK e stampa la riga SWEEP con WNS e utilizzo post-route.
# Uso: bash run_impl_sweep.sh "<lista FCLK>"      es.  bash run_impl_sweep.sh "30 40 50 60 75"
set -u
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
HERE="$(cd "$(dirname "$0")" && pwd)"
HDL="$HERE/../../../matlab/hdlsrc_donatello_tier/rtlgen_mdl"
OUT="$HERE/../results"
ROOTB="D:/zbd_tier_hw"
SRC="$ROOTB/src"
CANDS="${1:-30 40 50 60 75}"
JOBS=6                     # FISSO: risultati riproducibili

mkdir -p "$SRC" "$OUT"
rm -f "$SRC"/*.vhd "$SRC"/*.v "$SRC"/compile_order.txt
cp "$HDL"/*.vhd "$HDL/compile_order.txt" "$SRC"/
cp "$HERE/tier_axi_lite.v" "$SRC"/

for f in $CANDS; do
  echo "--- FCLK ${f} MHz  [$(date +%H:%M:%S)] ---"
  "$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog \
    -source "$HERE/build_impl.tcl" -tclargs "$SRC" "$ROOTB/impl_${f}" "$f" "$OUT" "$JOBS" 2>&1 \
    | grep -E "^(BUILD|SWEEP)|^ERROR:" | head -20
done
echo "SWEEP-DONE [$(date +%H:%M:%S)]"
