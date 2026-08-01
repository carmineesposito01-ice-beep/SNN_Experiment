#!/usr/bin/env bash
# P2 -- runner xsim per il plotone RTL.
#
# uso: ./run_p2.sh <work> <NSCEN> <N veicoli> <K> <HOLD> [par]
#      l'ultimo argomento `par` compila in modalita' PLATOON-PAR (plant senza DUT).
#
# Compila UNA volta, poi rilancia xsim per ogni scenario: cosi' la RAM del DUT riparte azzerata
# a ogni scenario, come nel golden -- e' lo stesso vincolo di reset che vale su hardware.
set -eu
VIV="${VIVADO_BIN:-C:/AMDDesignTools/2026.1/Vivado/bin}"
SRC="${P2_SRC:-C:/t7bimpl/src}"
QUI="$(cd "$(dirname "$0")" && pwd)"

WORK="$1"; NSCEN="$2"; NVEH="$3"; K="$4"; HOLD="$5"; MODO="${6:-loop}"

case "$WORK" in *" "*) echo "P2-ABORT: work-dir con spazi ($WORK): xsim si spezza"; exit 1;; esac
[ -f "$VIV/xvlog.bat" ] || { echo "P2-ABORT: Vivado non trovato in $VIV"; exit 1; }
[ -f "$SRC/compile_order.txt" ] || { echo "P2-ABORT: manca $SRC/compile_order.txt"; exit 1; }
[ -f "$WORK/plat_scen_1.mem" ] || { echo "P2-ABORT: scenari non esportati in $WORK (p2_export.py)"; exit 1; }

cd "$WORK"
rm -rf xsim.dir *.jou *.log *.pb hdl; mkdir -p hdl ser
cp "$SRC"/*.v hdl/ 2>/dev/null || true
cp "$QUI/tb_platoon.v" .

{
  printf '`define KVAL %s\n`define NVEH %s\n`define HOLDV %s\n' "$K" "$NVEH" "$HOLD"
  printf '`define SCENF "scen.mem"\n`define INITF "init.mem"\n'
  printf '`define ACCF  "acc.mem"\n`define OUTF  "ser.txt"\n'
  [ "$MODO" = "par" ] && printf '`define PLATOON_PAR 1\n'
} > p2_params.vh

echo "P2: compilo (modo=$MODO, N=$NVEH, K=$K, HOLD=$HOLD)"
while read -r f; do
  [ -n "$f" ] && "$VIV/xvlog.bat" "hdl/$f" > /dev/null
done < "$SRC/compile_order.txt"
"$VIV/xvlog.bat" -sv -i . tb_platoon.v > /dev/null   # -sv: serve shortreal per riprodurre il float32 del riferimento
"$VIV/xelab.bat" -debug off tb_platoon -s p2snap > /dev/null

for ((i = 1; i <= NSCEN; i++)); do
  cp "plat_scen_${i}.mem" scen.mem
  cp "plat_init_${i}.mem" init.mem
  [ "$MODO" = "par" ] && cp "plat_acc_${i}.mem" acc.mem || cp "plat_scen_${i}.mem" acc.mem
  o=$("$VIV/xsim.bat" p2snap -R 2>&1)
  echo "$o" | grep -E "^P2(RES|-FATAL)" || { echo "P2-ABORT: scenario $i senza P2RES"; echo "$o" | tail -5; exit 1; }
  mv ser.txt "ser/ser_${i}.txt"
done
echo "P2-DONE $NSCEN scenari, serie in $WORK/ser/"
