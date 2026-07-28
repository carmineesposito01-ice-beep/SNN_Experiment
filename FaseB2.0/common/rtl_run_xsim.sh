#!/usr/bin/env bash
# Runner xsim generico (Fase B2.0, T6/T7): copia HDL + TB + .mem in ROOT corta (no spazi) e gira xsim.
# args: ROOT HDLSRC_DIR TB_FILE K HOLD STIM_MEM GOLD_MEM
#   (STIM/GOLD sono nomi file gia' presenti in ROOT; HDLSRC/TB possono avere spazi -> vengono copiati in ROOT)
# Motivo ROOT corta: il repo sta sotto ".../1.Reti Neurali/..." (spazio) e xsim/glob rompe su path con spazi.
set -e
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
ROOT="$1"; HDLSRC="$2"; TB="$3"; K="$4"; HOLD="$5"; STIM="$6"; GOLD="$7"
mkdir -p "$ROOT"; cd "$ROOT"
rm -rf xsim.dir *.jou *.log *.pb hdl; mkdir hdl
cp "$HDLSRC"/*.vhd hdl/
cp "$HDLSRC/compile_order.txt" hdl/
TBN="$(basename "$TB")"; cp "$TB" "./$TBN"
# macro via file (il -d NAME=val perde '=' in Git-Bash -> .bat)
printf '`define KVAL %s\n`define HOLD %s\n`define STIMF "%s"\n`define GOLDF "%s"\n' "$K" "$HOLD" "$STIM" "$GOLD" > tier_params.vh
mapfile -t ORD < hdl/compile_order.txt
for f in "${ORD[@]}"; do "$VIV/xvhdl.bat" "hdl/$f" >/dev/null; done
"$VIV/xvlog.bat" -i . "$TBN" >/dev/null
"$VIV/xelab.bat" -debug off "${TBN%.v}" -s snap >/dev/null
"$VIV/xsim.bat" snap -R
