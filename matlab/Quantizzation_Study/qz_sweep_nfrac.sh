#!/usr/bin/env bash
# [Quantizzation_Study] Sweep di sintesi io-timed su nfrac (vincolo deploy 125 ns fisso, stesso protocollo
# per tutti i livelli -> confronto valido): risorse+potenza+Fmax per ogni nfrac.
#   uso: qz_sweep_nfrac.sh [nfrac ...]   (default: 2..13)
# Riusa AS-IS study_tradeoff/common/{pin_determinism,synth_point,impl_point}.tcl. VHDL generato da
# qz_gen_block_vhdl (forward Donatello splitpipe + decode p5, config FAST-like). TOP=Donatello.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# MATLAB su Windows NON capisce i path POSIX (/d/..): addpath('/d/x') -> D:\d\x (inesistente). Converti.
REPO_WIN="$(cygpath -m "$REPO" 2>/dev/null || echo "$REPO" | sed -E 's|^/([A-Za-z])/|\U\1:/|')"
MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"
VIV="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
COMMON="$REPO/matlab/study_tradeoff/common"
PIN="$COMMON/pin_determinism.tcl"; SYNTH="$COMMON/synth_point.tcl"; IMPL="$COMMON/impl_point.tcl"
DEPLOY=125.000 ; TOP=Donatello
OUT=/d/zbd_qz/sweep ; mkdir -p "$OUT"
TSV="$REPO/matlab/Quantizzation_Study/res_sweep.tsv"
LEVELS=("$@"); [ ${#LEVELS[@]} -eq 0 ] && LEVELS=(2 3 4 5 6 7 8 9 10 11 12 13)

printf "nfrac\tWNS\tdelay_ns\tFmax_MHz\tLUT\tFF\tDSP\tBRAM\tPtot_W\tPdyn_W\tPsta_W\n" > "$TSV"
for f in "${LEVELS[@]}"; do
  echo ">>> nfrac=$f : gen VHDL ..."
  vd="D:/zbd_qz/n$f"; rm -rf "$vd"     # niente VHDL stantio che mascheri una gen fallita
  "$MATLAB" -batch "addpath('$REPO_WIN/matlab'); addpath('$REPO_WIN/matlab/Quantizzation_Study'); qz_gen_block_vhdl($f,'$vd')" > "$OUT/gen_n$f.log" 2>&1
  vhd=$(find "$vd" -name 'Donatello.vhd' 2>/dev/null | head -1)
  [ -n "$vhd" ] || { echo "nfrac=$f: Donatello.vhd ASSENTE -> gen FALLITA (vedi $OUT/gen_n$f.log)"; continue; }
  src=$(dirname "$vhd")
  mkdir -p "$OUT/n$f"
  echo ">>> nfrac=$f : synth ..."
  "$VIV" -mode batch -source "$PIN" -source "$SYNTH" -tclargs "$src" "$OUT/n$f/synth" "n$f" "$DEPLOY" "$TOP" > "$OUT/n$f/synth.log" 2>&1
  dcp="$OUT/n$f/synth/post_synth.dcp"; [ -f "$dcp" ] || { echo "nfrac=$f: synth ERR (vedi $OUT/n$f/synth.log)"; continue; }
  echo ">>> nfrac=$f : impl io-timed ..."
  "$VIV" -mode batch -source "$PIN" -source "$IMPL" -tclargs "$dcp" "$DEPLOY" "$OUT/n$f/impl" "" "io" > "$OUT/n$f/impl.log" 2>&1
  L="$OUT/n$f/impl.log"
  g(){ grep -m1 "$1" "$L" | sed -E "$2"; }
  wns=$(g '^IMPL: WNS='      's/.*WNS=([-0-9.]+).*/\1/')
  del=$(g '^IMPL: ritardo='  's/.*ritardo=([0-9.]+).*/\1/')
  fmx=$(g '^IMPL: ritardo='  's/.*Fmax=([0-9.]+).*/\1/')
  lut=$(g '^IMPL-RES Slice LUTs'      's/.*= *//'); ff=$(g '^IMPL-RES Slice Registers' 's/.*= *//')
  dsp=$(g '^IMPL-RES DSPs'            's/.*= *//'); bram=$(g '^IMPL-RES Block RAM Tile' 's/.*= *//')
  pt=$(g 'IMPL-POWER Total On-Chip'   's/.*= *//'); pd=$(g 'IMPL-POWER Dynamic' 's/.*= *//'); ps=$(g 'IMPL-POWER Device Static' 's/.*= *//')
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$f" "${wns:-NA}" "${del:-NA}" "${fmx:-NA}" "${lut:-NA}" "${ff:-NA}" "${dsp:-NA}" "${bram:-NA}" "${pt:-NA}" "${pd:-NA}" "${ps:-NA}" | tee -a "$TSV"
done
echo "=== res_sweep.tsv ===" ; column -t -s$'\t' "$TSV"
