#!/usr/bin/env bash
# Harness B.2 PLANT-PAR: compila e gira il solo plant-nel-TB in xsim (nessun DUT RTL).
#   uso: run_xsim_plant_par.sh <K> [sens]
# I cl_*.mem (double bit-esatti) stanno accanto allo script. `KVAL / `SENS via cl_dims.vh (niente -d =).
set -e
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
K="$1"; SENS="$2"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="/d/zbd_plantpar"; rm -rf "$WORK"; mkdir -p "$WORK"
cp "$HERE/tb_plant_par.v" "$WORK/"; cp "$HERE"/cl_*.mem "$WORK/"
cd "$WORK"
printf '`define KVAL %s\n' "$K" > cl_dims.vh
[ "$SENS" = "sens" ] && printf '`define SENS 1\n' >> cl_dims.vh
"$VIV/xvlog.bat" -i . tb_plant_par.v
"$VIV/xelab.bat" -debug off tb_plant_par -s snap_pp
"$VIV/xsim.bat" snap_pp -R
