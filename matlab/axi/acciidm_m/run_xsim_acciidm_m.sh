#!/usr/bin/env bash
# Harness B.1 (Fase B2.0-2a-M2): compila il VHDL del controllore + il TB open-loop e gira in xsim.
#   uso: run_xsim_acciidm_m.sh <HDLSRC> <K> <HOLD> <STIMFILE> <GOLDFILE>
# Come run_xsim_champion.sh (path corto D:/zbd_accm per spazi/260-char; niente xvlog -d), DUT = controllore.
set -e
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
HDLSRC="$1"; K="$2"; HOLD="$3"; STIMF="$4"; GOLDF="$5"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="/d/zbd_accm"
rm -rf "$WORK"; mkdir -p "$WORK"
while IFS= read -r f; do [ -n "$f" ] && cp "$HDLSRC/$f" "$WORK/"; done < "$HDLSRC/compile_order.txt"
cp "$HERE/tb_acciidm_m_open.v" "$WORK/"
cp "$STIMF" "$WORK/stim.mem"; cp "$GOLDF" "$WORK/gold.mem"
cd "$WORK"
printf '`define KVAL %s\n`define HOLD %s\n' "$K" "$HOLD" > tb_params.vh
FILES=$(tr '\n' ' ' < "$HDLSRC/compile_order.txt")   # file .v del DUT (Verilog: registri init a 0 -> no U a time-0)
"$VIV/xvlog.bat" -i . $FILES tb_acciidm_m_open.v
"$VIV/xelab.bat" -debug off tb_acciidm_m_open -s snap_accm
"$VIV/xsim.bat" snap_accm -R
