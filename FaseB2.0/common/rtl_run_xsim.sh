#!/usr/bin/env bash
# Runner xsim generico (Fase B2.0, T6/T7): copia HDL + TB in ROOT corta (no spazi), COMPILA UNA VOLTA, poi rifa
# xsim -R per OGNI traiettoria (RAM/DualPortRAM azzerata all'init della simulazione, come il golden).
# args: ROOT HDLSRC_DIR TB_FILE K HOLD NTRAJ STIM_PREFIX GOLD_PREFIX
#   K = control-step di UNA traiettoria; i .mem per traiettoria sono <PREFIX>_<i>.mem (i=1..NTRAJ) in ROOT.
# Motivo ROOT corta: il repo sta sotto ".../1.Reti Neurali/..." (spazio) -> xsim/glob rompe su path con spazi.
set -e
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
ROOT="$1"; HDLSRC="$2"; TB="$3"; K="$4"; HOLD="$5"; NTRAJ="$6"; STIMP="$7"; GOLDP="$8"
cd "$ROOT"
rm -rf xsim.dir *.jou *.log *.pb hdl; mkdir hdl
cp "$HDLSRC"/*.vhd hdl/
cp "$HDLSRC/compile_order.txt" hdl/
TBN="$(basename "$TB")"; cp "$TB" "./$TBN"
# macro compile-time (una volta): il TB legge stim.mem/gold.mem, aggiornati per traiettoria prima di ogni xsim
printf '`define KVAL %s\n`define HOLD %s\n`define STIMF "stim.mem"\n`define GOLDF "gold.mem"\n' "$K" "$HOLD" > tier_params.vh
mapfile -t ORD < hdl/compile_order.txt
for f in "${ORD[@]}"; do "$VIV/xvhdl.bat" "hdl/$f" >/dev/null; done
"$VIV/xvlog.bat" -i . "$TBN" >/dev/null
"$VIV/xelab.bat" -debug off "${TBN%.v}" -s snap >/dev/null
tot=0; ntot=0; lat=""
for ((i=1; i<=NTRAJ; i++)); do
  cp "${STIMP}_${i}.mem" stim.mem
  cp "${GOLDP}_${i}.mem" gold.mem
  o=$("$VIV/xsim.bat" snap -R 2>&1)
  nm=$(printf '%s\n' "$o" | sed -n 's/.*RTLRES nMismatch=\([0-9]*\) .*/\1/p' | head -1)
  nn=$(printf '%s\n' "$o" | sed -n 's/.*RTLRES nMismatch=[0-9]* n=\([0-9]*\).*/\1/p' | head -1)
  if [ -z "$lat" ]; then lat=$(printf '%s\n' "$o" | sed -n 's/.*LAT_RTL \([0-9]*\).*/\1/p' | head -1); fi
  tot=$((tot + ${nm:-0}))
  ntot=$((ntot + ${nn:-0}))
done
echo "LAT_RTL ${lat:-0}"
echo "RTLRES nMismatch=$tot n=$ntot"
