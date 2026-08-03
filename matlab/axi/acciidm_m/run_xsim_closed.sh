#!/usr/bin/env bash
# Harness B.2 anello live: compila il DUT Verilog + il TB closed-loop e gira in xsim.
#   uso: run_xsim_closed.sh <HDLSRC> <K> <HOLD>
set -e
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
HDLSRC="$1"; K="$2"; HOLD="$3"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="/d/zbd_closed"; rm -rf "$WORK"; mkdir -p "$WORK"
while IFS= read -r f; do [ -n "$f" ] && cp "$HDLSRC/$f" "$WORK/"; done < "$HDLSRC/compile_order.txt"
cp "$HERE/tb_acciidm_m_closed.v" "$WORK/"; cp "$HERE"/cl_*.mem "$WORK/"
cd "$WORK"
printf '`define KVAL %s\n`define HOLD %s\n' "$K" "$HOLD" > cl_dims.vh
FILES=$(tr '\n' ' ' < "$HDLSRC/compile_order.txt")
"$VIV/xvlog.bat" -i . $FILES tb_acciidm_m_closed.v
"$VIV/xelab.bat" -debug off tb_acciidm_m_closed -s snap_cl
"$VIV/xsim.bat" snap_cl -R
