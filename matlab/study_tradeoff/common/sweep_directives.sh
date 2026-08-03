#!/usr/bin/env bash
# Blocco A split — esperimento MIRATO di ottimizzazione Vivado (directive + phys_opt) sui due endpoint.
#   sweep_directives.sh [tag ...]
#
# La curva §13 e' a flusso DEFAULT (nessuna directive, nessun phys_opt). Qui si misura di quanto la
# spostano le directive mirate, sui due punti che contano:
#   - AREA   @ 125 ns (deploy-ref): synth AreaOptimized_high + impl ExploreArea -> il floor cala?
#   - PERF   @ x0.90 (punto max-Fmax): synth PerformanceOptimized + impl Explore + phys_opt -> Fmax sale?
# Confronto col baseline default (points_split_curve.tsv): deploy-ref LUT e x0.90 Fmax.
#
# Reuse: synth_point.tcl (6o arg = synth directive) + impl_point.tcl (4o arg = profilo) + pin + struct_gate.
# Nessuna modifica al comportamento default dei due tcl (profilo/directive vuoti = flusso storico).
set -uo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
COMMON="$REPO/matlab/study_tradeoff/common"
VIV="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
PIN="$COMMON/pin_determinism.tcl"
SYNTH="$COMMON/synth_point.tcl"
IMPL="$COMMON/impl_point.tcl"
OUTROOT=/d/zbd_tradeoff/donatello_split_dir
TOP=Donatello_LUT64
PTS="$REPO/matlab/study_tradeoff/donatello/points_directives.tsv"
AREA_P=125.000

. <(sed -n '/^struct_gate() {/,/^}/p' "$COMMON/run_block_a_matrix.sh")

#      tag         decode  snn  P_tight (= x0.90 = 0.90*delay_OOC)
TIERS=( "sp_slow      fused  R2  29.465"
        "sp_balanced  p3     R5  15.946"
        "sp_fast      p5     R9  9.686" )

# run_exp <src> <P> <outdir> <synth_directive> <impl_profile> : stdout "WNS WHS delay Fmax LUT FF DSP BRAM" o "ERR"
run_exp() {
  local src="$1" P="$2" od="$3" sdir="$4" prof="$5"
  mkdir -p "$od"
  "$VIV" -mode batch -source "$PIN" -source "$SYNTH" \
     -tclargs "$src" "$od/synth" "exp" "$P" "$TOP" "$sdir" > "$od/synth.log" 2>&1
  local dcp="$od/synth/post_synth.dcp"
  [ -f "$dcp" ] || { echo "ERR synth (vedi $od/synth.log)"; return 1; }
  "$VIV" -mode batch -source "$PIN" -source "$IMPL" \
     -tclargs "$dcp" "$P" "$od/impl" "$prof" > "$od/impl.log" 2>&1
  local wl; wl=$(grep -m1 "^IMPL: WNS=" "$od/impl.log" || true)
  [ -n "$wl" ] || { echo "ERR impl (vedi $od/impl.log)"; return 1; }
  local wns whs lut ff dsp bram ach fmax
  wns=$(echo "$wl" | sed -E 's/.*WNS=([-0-9.]+).*/\1/')
  whs=$(echo "$wl" | sed -E 's/.*WHS=([-0-9.]+).*/\1/')
  lut=$( grep -m1 "^IMPL-RES Slice LUTs"      "$od/impl.log" | sed -E 's/.*= *//')
  ff=$(  grep -m1 "^IMPL-RES Slice Registers" "$od/impl.log" | sed -E 's/.*= *//')
  dsp=$( grep -m1 "^IMPL-RES DSPs"            "$od/impl.log" | sed -E 's/.*= *//')
  bram=$(grep -m1 "^IMPL-RES Block RAM Tile"  "$od/impl.log" | sed -E 's/.*= *//')
  ach=$( awk -v p="$P" -v w="$wns" 'BEGIN{printf "%.3f", p-w}')
  fmax=$(awk -v a="$ach" 'BEGIN{printf "%.3f", (a>0)?1000.0/a:0}')
  echo "$wns $whs $ach $fmax $lut $ff $dsp $bram"
}

mkdir -p "$OUTROOT"
[ -f "$PTS" ] || printf "tag\texp\tP_ns\tsynth_dir\timpl_prof\tWNS\tWHS\tdelay_ns\tFmax_MHz\tLUT\tFF\tDSP\tBRAM\n" > "$PTS"

SEL="$*"
for entry in "${TIERS[@]}"; do
  set -- $entry; tag="$1"; var="$2"; sig="$3"; Ptight="$4"
  if [ -n "$SEL" ] && ! echo " $SEL " | grep -q " $tag "; then continue; fi
  src="/d/zbd_tradeoff/donatello_split/$tag/src"
  echo "--- $tag (decode=$var, SNN=$sig) ---"
  struct_gate "$src" "$var" "$tag" "$sig" || { echo "FALLITO $tag: struct_gate"; continue; }
  grep -v "^${tag}$(printf '\t')" "$PTS" > "$PTS.tmp" 2>/dev/null && mv "$PTS.tmp" "$PTS" || true

  # AREA @ 125 ns
  if r=$(run_exp "$src" "$AREA_P" "$OUTROOT/$tag/area" "AreaOptimized_high" "area"); then
    set -- $r; wns="$1"; whs="$2"; ach="$3"; fmax="$4"; lut="$5"; ff="$6"; dsp="$7"; bram="$8"
    printf "  [AREA @%-8s] LUT=%s (WNS=%s Fmax=%s)\n" "$AREA_P" "$lut" "$wns" "$fmax"
    printf "%s\tarea\t%s\tAreaOptimized_high\tarea\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
       "$tag" "$AREA_P" "$wns" "$whs" "$ach" "$fmax" "$lut" "$ff" "$dsp" "$bram" >> "$PTS"
  else echo "  AREA: $r"; fi

  # PERF @ x0.90
  if r=$(run_exp "$src" "$Ptight" "$OUTROOT/$tag/perf" "PerformanceOptimized" "perf"); then
    set -- $r; wns="$1"; whs="$2"; ach="$3"; fmax="$4"; lut="$5"; ff="$6"; dsp="$7"; bram="$8"
    printf "  [PERF @%-8s] Fmax=%s LUT=%s (WNS=%s WHS=%s)\n" "$Ptight" "$fmax" "$lut" "$wns" "$whs"
    printf "%s\tperf\t%s\tPerformanceOptimized\tperf\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
       "$tag" "$Ptight" "$wns" "$whs" "$ach" "$fmax" "$lut" "$ff" "$dsp" "$bram" >> "$PTS"
  else echo "  PERF: $r"; fi
done

echo "=== points_directives.tsv ==="
column -t -s$'\t' "$PTS" 2>/dev/null