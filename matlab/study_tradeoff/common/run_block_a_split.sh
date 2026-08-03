#!/usr/bin/env bash
# Blocco A — campagna SPLIT: rimisura la matrice con SNN|decode in DUE entita' di sintesi.
#   run_block_a_split.sh [tag ...]
#
# Perche': lo split rompe il muro d'INTEGRAZIONE (RESULTS.md §6). p3+R5 e' passato 41,1 -> 56,4 MHz con
# MENO LUT. Le conclusioni sull'accoppiamento erano tratte sull'architettura `chart`, sub-ottimale ->
# vanno rifatte sull'architettura vera.
#
# PREVISIONE (scritta PRIMA): con lo split il collo diventa min(SNN, decode_isolato), non piu' il costo
# d'integrazione. Quindi:
#   sp_slow     fused R2  -> min(30,31) ~30
#   sp_balanced p3    R5  -> min(62,57) ~57   [gia' misurato: 56,4]
#   sp_fast     p5    R9  -> min(99,98) ~92   <- il candidato FAST vero: entrambi i pezzi >90
#   sp_p3r9     p3    R9  -> min(99,57) ~57   (verifica: R9 non aiuta se limita il decode p3)
#
# ⚠️ Snapshot SNN congelati, cache slprj azzerata, cancello strutturale su decode+SNN: come il driver
#    chart. Il file condiviso snn_b2_fsm.m non viene MAI toccato.
set -uo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
COMMON="$REPO/matlab/study_tradeoff/common"
MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"
VIV="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
OUT=/d/zbd_tradeoff/donatello_split
PTS="$REPO/matlab/study_tradeoff/donatello/points_split.tsv"

#      nome         decode  snapshot-SNN                  firma  arch
EXPS=( "sp_slow      fused  snn_variants/snn_b2_fsm_R2.m  R2   split"
       "sp_balanced  p3     snn_variants/snn_b2_fsm_R5.m  R5   split"
       "sp_fast      p5     snn_variants/snn_b2_fsm_R9.m  R9   split"
       "sp_p3r9      p3     snn_variants/snn_b2_fsm_R9.m  R9   split" )

# il cancello strutturale e' identico a quello del driver chart: si riusa la sua definizione
. <(sed -n '/^struct_gate() {/,/^}/p' "$COMMON/run_block_a_matrix.sh")

mkdir -p "$OUT"
[ -f "$PTS" ] || printf "tag\tsrcdir\tperiod_ns\tfmax_ooc\tnota\n" > "$PTS"

one() {
  local tag="$1" var="$2" com="$3" snn="$4" arch="$5"
  local d="$OUT/$tag"
  if [ -f "$d/src/Donatello_LUT64.vhd" ]; then echo "SKIP-GEN $tag"; else
    mkdir -p "$d/src"
    [ -f "$REPO/matlab/$com" ] || { echo "FALLITO $tag: snapshot SNN assente ($com)"; return 1; }
    echo "  $tag: SNN da $com, arch=$arch"
    ( cd "$REPO/matlab" && "$MATLAB" -batch \
        "addpath('study_tradeoff/common'); gen_donatello_point('D:\\zbd_tradeoff\\donatello_split\\$tag\\gen', '$var', '$com', '$arch')" ) \
        > "$d/gen.log" 2>&1
    local s; s=$(find "$d/gen" -name "Donatello_LUT64.vhd" 2>/dev/null | head -1)
    [ -n "$s" ] || { echo "FALLITO $tag: nessun VHDL (vedi $d/gen.log)"; return 1; }
    # ⚠️ verifica che la separazione sia ATTERRATA: due entity SNN e DEC (non re-inlinate)
    local nS nD
    nS=$(cat "$(dirname "$s")"/*.vhd | grep -c "^ENTITY SNN")
    nD=$(cat "$(dirname "$s")"/*.vhd | grep -c "^ENTITY DEC")
    if [ "$arch" = "split" ]; then
      [ "$nS" -ge 1 ] && [ "$nD" -ge 1 ] || { echo "FALLITO $tag: split non atterrato (SNN=$nS DEC=$nD)"; return 1; }
      echo "SPLIT-OK $tag: entity SNN=$nS DEC=$nD distinte"
    fi
    cp "$(dirname "$s")"/*.vhd "$d/src/" && rm -rf "$d/gen"
    echo "GEN $tag: $(ls "$d/src"/*.vhd | wc -l) file .vhd  [decode=$var arch=$arch]"
  fi

  struct_gate "$d/src" "$var" "$tag" "$snn" || return 1

  if grep -q "^${tag}$(printf '\t')" "$PTS"; then echo "SKIP-PER $tag"; else
    "$VIV" -mode batch -source "$COMMON/synth_point.tcl" \
       -tclargs "D:/zbd_tradeoff/donatello_split/$tag/src" "D:/zbd_tradeoff/donatello_split/$tag/free" \
                "${tag}_free" "" "Donatello_LUT64" > "$d/synth_free.log" 2>&1
    local wns; wns=$(grep -m1 "^SYNTH-RESULT" "$d/synth_free.log" | sed -E 's/.*WNS=([-0-9.]+).*/\1/')
    [ -n "$wns" ] || { echo "FALLITO $tag: sintesi libera (vedi $d/synth_free.log)"; return 1; }
    awk -v t="$tag" -v s="/d/zbd_tradeoff/donatello_split/$tag/src" -v w="$wns" -v v="$var" \
        'BEGIN{p=125.0-w; printf "%s\t%s\t%.3f\t%.3f\tDonatello LUT-64 decode=%s SPLIT\n", t,s,p,1000.0/p,v}' >> "$PTS"
    rm -f "$d/free/post_synth.dcp"
    echo "PER $tag: WNS=$wns -> periodo $(awk -v w="$wns" 'BEGIN{printf "%.3f", 125.0-w}') ns  (Fmax OOC $(awk -v w="$wns" 'BEGIN{printf "%.1f", 1000.0/(125.0-w)}'))"
  fi
}

SEL="$*"
for e in "${EXPS[@]}"; do
  set -- $e; tag="$1"; var="$2"; com="$3"; snn="$4"; arch="$5"
  if [ -n "$SEL" ] && ! echo " $SEL " | grep -q " $tag "; then continue; fi
  echo "--- $tag (decode=$var, SNN=$snn, arch=$arch) ---"
  one "$tag" "$var" "$com" "$snn" "$arch"
done

echo "=== snn_b2_fsm intatto: $(git -C "$REPO" diff --quiet matlab/snn_b2_fsm.m && echo OK || echo '⚠️ MODIFICATO') ==="
echo "=== points_split.tsv ==="; column -t -s$'\t' "$PTS" 2>/dev/null | cut -c1-120
