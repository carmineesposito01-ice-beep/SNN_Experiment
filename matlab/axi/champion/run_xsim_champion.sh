#!/usr/bin/env bash
# Harness A (Fase B2.0-2a): compila il VHDL generato + il TB e gira in xsim.
#   uso: run_xsim_champion.sh <HDLSRC> <K> <HOLD> <STIMFILE> <GOLDFILE>
# HDLSRC = cartella col VHDL + compile_order.txt (info.outdir di rtl_gen_dut).
# Copia tutto in un PATH CORTO senza spazi (il path del progetto ha "1.Reti Neurali" + limite 260 char
# di Windows: Vivado xsim non li digerisce -> come la Fase B usava D:/zbd_pb2).
set -e
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
HDLSRC="$1"; K="$2"; HOLD="$3"; STIMF="$4"; GOLDF="$5"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="/d/zbd_champ"
rm -rf "$WORK"; mkdir -p "$WORK"
# copia i VHDL (basename) nell'ordine di compile_order.txt, il TB e gli stimoli a nome fisso
while IFS= read -r f; do [ -n "$f" ] && cp "$HDLSRC/$f" "$WORK/"; done < "$HDLSRC/compile_order.txt"
cp "$HERE/tb_champion_stream.v" "$WORK/"
cp "$STIMF" "$WORK/stim.mem"; cp "$GOLDF" "$WORK/gold.mem"
cd "$WORK"
printf '`define KVAL %s\n`define HOLD %s\n' "$K" "$HOLD" > tb_params.vh   # niente xvlog -d (l'= si perde)
FILES=$(tr '\n' ' ' < "$HDLSRC/compile_order.txt")     # basenames, ora in $WORK (nessuno spazio)
"$VIV/xvhdl.bat" $FILES
"$VIV/xvlog.bat" -i . tb_champion_stream.v
"$VIV/xelab.bat" -debug off tb_champion_stream -s snap_champ
"$VIV/xsim.bat" snap_champ -R
