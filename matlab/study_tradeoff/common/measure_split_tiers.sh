#!/usr/bin/env bash
# Blocco A split — LATENZA (clock) + bit-exactness (dmax) per-tier, sulla traiettoria reale.
#   measure_split_tiers.sh
#
# Perche': la Fmax da sola non basta (RESULTS.md §12). Il delay ha DUE facce:
#   - critical-path delay = 1/Fmax (periodo, gia' in points_split.tsv);
#   - latenza end-to-end = N_clock d'inferenza -> a 8 MHz (125 ns/clock) e' il tempo REALE per control-step.
# La latenza dipende da ENTRAMBI gli assi (round SNN + fasi decode): i tier accoppiano coppie diverse, quindi
# va MISURATA per coppia, non dedotta. run_block_traj_test la stampa ('latenza inferenza = N clock').
#
# ⚠️ Un processo -batch FRESCO per tier: lo swap dello snapshot SNN e' pulito solo senza cache slprj
#    ereditata dal tier precedente (stessa ragione per cui gen_donatello_point azzera slprj a ogni punto).
# ⚠️ hold=500 > latenza max attesa (~406): con hold < latenza il time-mux non fa in tempo e il test aborta.
set -uo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"

#      tier         decode  snapshot-SNN
TIERS=( "sp_slow      fused  snn_variants/snn_b2_fsm_R2.m"
        "sp_balanced  p3     snn_variants/snn_b2_fsm_R5.m"
        "sp_fast      p5     snn_variants/snn_b2_fsm_R9.m" )

printf "%-12s %-7s %-8s %-6s %s\n" tier decode lat_clk dmax "lat@8MHz(us)"
for t in "${TIERS[@]}"; do
  set -- $t; tag="$1"; var="$2"; snn="$3"
  log="/d/zbd_tradeoff/donatello_split/${tag}_lat.log"
  mkdir -p "$(dirname "$log")"
  ( cd "$REPO/matlab" && "$MATLAB" -batch \
      "build_hdl_variants('$var','$snn','shared','split'); d=run_block_traj_test(20,'Donatello_LUT64',500,1); fprintf('DMAX=%d\n',d)" ) \
      > "$log" 2>&1
  lat=$(grep -oE "latenza inferenza = [0-9]+" "$log" | grep -oE "[0-9]+" | head -1)
  dmax=$(grep -oE "DMAX=[0-9.eE+-]+" "$log" | sed 's/DMAX=//' | head -1)
  if [ -z "$lat" ] || [ -z "$dmax" ]; then
    echo "FALLITO $tag: lat='$lat' dmax='$dmax' (vedi $log)"; continue
  fi
  us=$(awk -v l="$lat" 'BEGIN{printf "%.1f", l*125.0/1000.0}')   # 8 MHz -> 125 ns/clock
  printf "%-12s %-7s %-8s %-6s %s\n" "$tag" "$var" "$lat" "$dmax" "$us"
done
