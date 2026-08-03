#!/usr/bin/env bash
# ============================================================================================
# BLOCCO A — CAMPAGNA PHASE 2 (studio io-timed). Un driver per tier:
#   sweep_phase2.sh [tag ...]      (senza argomenti: tutti e 3 i tier)
#
# METODO = la CURVA a CLOCK VINCOLATO (come lo studio di ieri, RESULTS §13), MA misurata io-timed (§15).
# Le "varianti" Area/Performance NON vengono dai preset-directive di Vivado (quello era solo un TEST, §14,
# che non migliorava): vengono dal VINCOLO DI CLOCK. Stringendo il clock il tool compra velocita' con area
# -> il punto STRETTO (x0.90) = variante MAX-Fmax/area-alta; il clock LASCO (deploy-ref 125 ns) = variante
# AREA-minima. La curva mappa l'intero trade-off area-vs-clock in un colpo. Niente directive.
#
# COSA cambia dallo storico sweep_clock_curve.sh:
#   1. impl con IODELAY 'io' -> tima ingresso->normalize->go: Fmax REALE deployabile, non l'interno (§15).
#   2. VHDL = blocco splitpipe VERIFICATO in Phase 1 (D:/zbd_p1/<TIER>): 4/5, dmax=0, firma R2/R5/R9.
#   3. self-ANCHOR: P0 = ritardo io MISURATO su un seme (non l'interno). Per FAST io>interno.
#   4. POTENZA vectorless (report_power) su ogni punto: total/dynamic/static.
#   5. HOLD INTERNO reg-reg (esclude l'artefatto io-delay=0 sulle porte): il hold REALE del blocco.
#
# RIPRODUCIBILITA': maxThreads pinnato, seed 0, versione Vivado registrata, VHDL byte-identico.
# ⚠️ Vivado spezza gli argomenti sugli SPAZI: i path in -tclargs (src/outdir) sono su D:/ (no spazi).
# ============================================================================================
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
COMMON="$REPO/matlab/study_tradeoff/common"
VIV="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
PIN="$COMMON/pin_determinism.tcl"; SYNTH="$COMMON/synth_point.tcl"; IMPL="$COMMON/impl_point.tcl"
OUTROOT=/d/zbd_p2/sweep
TOP=Donatello_LUT64
PTS="$REPO/matlab/study_tradeoff/donatello/points_phase2.tsv"
DEPLOY_REF=125.000

#      tag          VHDL-dir (Phase 1)          P_seed_ns (interno, solo per l'anchor io)
TIERS=( "sp_slow      D:/zbd_p1/SLOW/rtlgen_mdl   32.739"
        "sp_balanced  D:/zbd_p1/BAL/rtlgen_mdl    17.718"
        "sp_fast      D:/zbd_p1/FAST/rtlgen_mdl   10.762" )

synth_one() { # <src> <P> <outdir> -> echo dcp | ""
  local src="$1" P="$2" od="$3"; mkdir -p "$od"
  "$VIV" -mode batch -source "$PIN" -source "$SYNTH" -tclargs "$src" "$od" "pt" "$P" "$TOP" > "$od/synth.log" 2>&1
  [ -f "$od/post_synth.dcp" ] && echo "$od/post_synth.dcp" || echo ""
}
impl_one() { # <dcp> <P> <outdir> <PROF> -> echo "wns whs whsint delay fmax lut ff dsp bram ptot pdyn psta" | "ERR"
  local dcp="$1" P="$2" od="$3" prof="$4"; mkdir -p "$od"
  "$VIV" -mode batch -source "$PIN" -source "$IMPL" -tclargs "$dcp" "$P" "$od" "$prof" "io" > "$od/impl.log" 2>&1
  local L="$od/impl.log"
  grep -q "^IMPL: WNS=" "$L" || { echo "ERR"; return 1; }
  local wns whs whsint delay fmax lut ff dsp bram ptot pdyn psta
  wns=$(   grep -m1 "^IMPL: WNS=" "$L" | sed -E 's/.*WNS=([-0-9.]+).*/\1/')
  whs=$(   grep -m1 "^IMPL: WNS=" "$L" | sed -E 's/.*WHS=([-0-9.]+).*/\1/')
  whsint=$(grep -m1 "^IMPL-HOLD-INT whs_interno=" "$L" | sed -E 's/.*whs_interno=([-0-9.]+).*/\1/')
  delay=$( grep -m1 "^IMPL: ritardo=" "$L" | sed -E 's/.*ritardo=([0-9.]+).*/\1/')
  fmax=$(  grep -m1 "^IMPL: ritardo=" "$L" | sed -E 's/.*Fmax=([0-9.]+).*/\1/')
  lut=$(  grep -m1 "^IMPL-RES Slice LUTs"      "$L" | sed -E 's/.*= *//')
  ff=$(   grep -m1 "^IMPL-RES Slice Registers" "$L" | sed -E 's/.*= *//')
  dsp=$(  grep -m1 "^IMPL-RES DSPs"            "$L" | sed -E 's/.*= *//')
  bram=$( grep -m1 "^IMPL-RES Block RAM Tile"  "$L" | sed -E 's/.*= *//')
  ptot=$( grep -m1 "IMPL-POWER Total On-Chip"  "$L" | sed -E 's/.*= *//')
  pdyn=$( grep -m1 "IMPL-POWER Dynamic"        "$L" | sed -E 's/.*= *//')
  psta=$( grep -m1 "IMPL-POWER Device Static"  "$L" | sed -E 's/.*= *//')
  echo "${wns:-NA} ${whs:-NA} ${whsint:-NA} ${delay:-NA} ${fmax:-NA} ${lut:-NA} ${ff:-NA} ${dsp:-NA} ${bram:-NA} ${ptot:-NA} ${pdyn:-NA} ${psta:-NA}"
}
write_row() { # <tag> <kind> <label> <P> <row(12 campi)>
  local valid hold
  valid=$(awk -v w="$5" 'BEGIN{print (w+0<=0)?"si":"lim-inf"}')
  hold=$( awk -v h="$7" 'BEGIN{print (h!="NA" && h+0>=0)?"ok":"NEG"}')
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
     "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9" "${10}" "${11}" "${12}" "${13}" "${14}" "${15}" "${16}" "$valid" "$hold" >> "$PTS"
}

mkdir -p "$OUTROOT"
"$VIV" -version > "$OUTROOT/vivado_version.txt" 2>&1 || true
VIVVER=$(grep -m1 -oE "v[0-9]{4}\.[0-9]+" "$OUTROOT/vivado_version.txt" 2>/dev/null || echo "?")
echo "=== Vivado $VIVVER ; io-timed ; VHDL Phase1 verificato ; griglia {0.90,1.00,1.40,2.00,3.00}xP0_io + deploy-ref ==="
[ -f "$PTS" ] || printf "tag\tkind\tlabel\tP_ns\tWNS\tWHS_io\tWHS_int\tdelay_ns\tFmax_MHz\tLUT\tFF\tDSP\tBRAM\tPtot_W\tPdyn_W\tPsta_W\tvalid\thold_int\n" > "$PTS"

SEL="$*"
for entry in "${TIERS[@]}"; do
  set -- $entry; tag="$1"; src="$2"; pseed="$3"
  if [ -n "$SEL" ] && ! echo " $SEL " | grep -q " $tag "; then continue; fi
  [ -d "$src" ] || { echo "FALLITO $tag: VHDL assente in $src"; continue; }
  echo "--- $tag (src=$src) ---"
  grep -v "^${tag}$(printf '\t')" "$PTS" > "$PTS.tmp" 2>/dev/null && mv "$PTS.tmp" "$PTS" || true

  # 1) ANCHOR: synth+impl-io al seme interno -> ritardo io reale -> P0
  echo "  [anchor] synth+impl-io @ $pseed ns (seme interno)"
  dcp=$(synth_one "$src" "$pseed" "$OUTROOT/$tag/anchor/synth")
  [ -n "$dcp" ] || { echo "  FALLITO $tag: synth anchor (vedi $OUTROOT/$tag/anchor/synth/synth.log)"; continue; }
  arow=$(impl_one "$dcp" "$pseed" "$OUTROOT/$tag/anchor/impl" "")
  [ "$arow" != "ERR" ] || { echo "  FALLITO $tag: impl anchor"; continue; }
  set -- $arow; P0="$4"
  echo "  => P0_io = $P0 ns (Fmax_io seme = $5 MHz)"

  # 2) CURVA: griglia {0.90..3.00}xP0_io + deploy-ref, impl-io + potenza + hold interno
  for f in 0.90 1.00 1.40 2.00 3.00; do
    Pr=$(awk -v p="$P0" -v f="$f" 'BEGIN{printf "%.3f",p*f}')
    dcp=$(synth_one "$src" "$Pr" "$OUTROOT/$tag/x$f/synth")
    [ -n "$dcp" ] || { echo "  [x$f] synth ERR"; continue; }
    row=$(impl_one "$dcp" "$Pr" "$OUTROOT/$tag/x$f/impl" "")
    [ "$row" != "ERR" ] || { echo "  [x$f] impl ERR"; continue; }
    set -- $row
    printf "  [x%-4s P=%-8s] delay=%-7s Fmax=%-7s LUT=%-5s DSP=%-3s Ptot=%-6s WHSint=%s\n" "$f" "$Pr" "$4" "$5" "$6" "$8" "${10}" "$3"
    write_row "$tag" "curve" "x$f" "$Pr" $row
  done
  # deploy-ref (area minima, clock lasco)
  dcpd=$(synth_one "$src" "$DEPLOY_REF" "$OUTROOT/$tag/deploy/synth")
  if [ -n "$dcpd" ]; then
    row=$(impl_one "$dcpd" "$DEPLOY_REF" "$OUTROOT/$tag/deploy/impl_default" "")
    if [ "$row" != "ERR" ]; then set -- $row
      printf "  [deploy P=%-8s] delay=%-7s Fmax=%-7s LUT=%-5s Ptot=%s\n" "$DEPLOY_REF" "$4" "$5" "$6" "${10}"
      write_row "$tag" "curve" "deploy-ref" "$DEPLOY_REF" $row
    fi
  fi
  echo "  => $tag COMPLETO"
done

echo "=== points_phase2.tsv ==="
column -t -s$'\t' "$PTS" 2>/dev/null
