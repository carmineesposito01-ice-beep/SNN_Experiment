#!/usr/bin/env bash
# T7b (da T6b · M2) — sweep FCLK del COMPOSTO: un'invocazione Vivado per candidato (isolamento + determinismo).
# Copia i sorgenti nella work-dir CORTA (il path del repo contiene spazi e add_files li spezza), poi implementa
# a ciascun FCLK e stampa la riga SWEEP con WNS e utilizzo post-route.
# Uso: bash run_impl_sweep.sh "<lista FCLK>"      es.  bash run_impl_sweep.sh "30 40 50 60 75"
set -u
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
HERE="$(cd "$(dirname "$0")" && pwd)"
HDL="C:/t7hdlv/rtlgen_mdl"          # VERILOG del composto (cio' che T7a ha provato bit-esatto)
OUT="$HERE/../results"
ROOTB="C:/t7bimpl"                  # work-dir CORTA senza spazi
SRC="$ROOTB/src"
CANDS="${1:-15 20 25 30 35 40}"     # centrato sotto i 41,5 MHz OOC MISURATI sul composto
JOBS=6                     # FISSO: risultati riproducibili

mkdir -p "$SRC" "$OUT"
rm -f "$SRC"/*.vhd "$SRC"/*.v "$SRC"/compile_order.txt
cp "$HDL"/*.v "$HDL/compile_order.txt" "$SRC"/
cp "$HERE/snniidm_axi_lite.v" "$SRC"/

# CANCELLO: i sorgenti devono esserci PRIMA di lanciare implementazioni da ~15 min ciascuna.
nv=$(ls "$SRC"/*.v 2>/dev/null | wc -l)
[ "$nv" -ge 11 ] || { echo "SWEEP-ABORT: solo $nv .v in $SRC (attesi >=11: 10 del DUT + wrapper)"; exit 1; }
[ -s "$SRC/compile_order.txt" ] || { echo "SWEEP-ABORT: compile_order.txt mancante o vuoto"; exit 1; }

for f in $CANDS; do
  echo "--- FCLK ${f} MHz  [$(date +%H:%M:%S)] ---"
  "$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog \
    -source "$HERE/build_impl.tcl" -tclargs "$SRC" "$ROOTB/impl_${f}" "$f" "$OUT" "$JOBS" 2>&1 \
    | grep -E "^(BUILD|SWEEP)|^ERROR:" | head -20
done
echo "SWEEP-DONE [$(date +%H:%M:%S)]"
