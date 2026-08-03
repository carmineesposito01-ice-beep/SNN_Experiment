#!/usr/bin/env bash
# [Quantizzation_Study] Sintesi io-timed (deploy 125 ns) su un INSIEME RIDOTTO di config per-campo.
# Config passate come righe "nome:nV,nfat,nacc,naccw,nraw,nw" da mp_synth_set.txt.
# tcl comuni (invariati): pin_determinism + synth_point (src,outdir,tag,P,TOP) + impl_point (dcp,PER,outdir,"",io).
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
REPO_WIN="$(cygpath -m "$REPO" 2>/dev/null || echo "$REPO" | sed -E 's|^/([A-Za-z])/|\U\1:/|')"
MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"
VIV="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
COMMON="$REPO/matlab/study_tradeoff/common"; PIN="$COMMON/pin_determinism.tcl"; SYNTH="$COMMON/synth_point.tcl"; IMPL="$COMMON/impl_point.tcl"
DEPLOY=125.000; TOP=Donatello; OUT=/d/zbd_qz/mp_sweep; mkdir -p "$OUT"
TSV="$REPO/matlab/Quantizzation_Study/mp_res.tsv"
printf "config\tnf\tWNS\tdelay_ns\tFmax_MHz\tLUT\tFF\tDSP\tBRAM\tPtot_W\tPdyn_W\tPsta_W\n" > "$TSV"
while IFS=: read -r name nf; do
  [ -z "$name" ] && continue
  case "$name" in \#*) continue;; esac
  echo ">>> $name ($nf) : gen VHDL ..."
  arr=$(echo "$nf" | tr ',' ' '); vd="D:/zbd_qz/mp_$name"; rm -rf "$vd"
  "$MATLAB" -batch "addpath('$REPO_WIN/matlab'); addpath('$REPO_WIN/matlab/Quantizzation_Study'); qz_gen_block_vhdl_mp([$arr],'$vd')" > "$OUT/gen_$name.log" 2>&1
  vhd=$(find "$vd" -name 'Donatello.vhd' 2>/dev/null | head -1)
  [ -n "$vhd" ] || { echo "$name: Donatello.vhd ASSENTE (gen fallita) - vedi $OUT/gen_$name.log"; continue; }
  src=$(dirname "$vhd"); mkdir -p "$OUT/$name"
  echo ">>> $name : synth ..."
  "$VIV" -mode batch -source "$PIN" -source "$SYNTH" -tclargs "$src" "$OUT/$name/synth" "$name" "$DEPLOY" "$TOP" > "$OUT/$name/synth.log" 2>&1
  dcp="$OUT/$name/synth/post_synth.dcp"; [ -f "$dcp" ] || { echo "$name: synth ERR - vedi $OUT/$name/synth.log"; continue; }
  echo ">>> $name : impl (io-timed) ..."
  "$VIV" -mode batch -source "$PIN" -source "$IMPL" -tclargs "$dcp" "$DEPLOY" "$OUT/$name/impl" "" "io" > "$OUT/$name/impl.log" 2>&1
  L="$OUT/$name/impl.log"; g(){ grep -m1 "$1" "$L" | sed -E "$2"; }
  wns=$(g '^IMPL: WNS=' 's/.*WNS=([-0-9.]+).*/\1/'); del=$(g '^IMPL: ritardo=' 's/.*ritardo=([0-9.]+).*/\1/'); fmx=$(g '^IMPL: ritardo=' 's/.*Fmax=([0-9.]+).*/\1/')
  lut=$(g '^IMPL-RES Slice LUTs' 's/.*= *//'); ff=$(g '^IMPL-RES Slice Registers' 's/.*= *//'); dsp=$(g '^IMPL-RES DSPs' 's/.*= *//'); bram=$(g '^IMPL-RES Block RAM Tile' 's/.*= *//')
  pt=$(g 'IMPL-POWER Total On-Chip' 's/.*= *//'); pd=$(g 'IMPL-POWER Dynamic' 's/.*= *//'); ps=$(g 'IMPL-POWER Device Static' 's/.*= *//')
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$name" "$nf" "${wns:-NA}" "${del:-NA}" "${fmx:-NA}" "${lut:-NA}" "${ff:-NA}" "${dsp:-NA}" "${bram:-NA}" "${pt:-NA}" "${pd:-NA}" "${ps:-NA}" | tee -a "$TSV"
done < "$REPO/matlab/Quantizzation_Study/mp_synth_set.txt"
echo "=== mp_res.tsv ==="; column -t -s$'\t' "$TSV"
