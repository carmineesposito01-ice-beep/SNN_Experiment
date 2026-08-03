#!/usr/bin/env bash
# Blocco A split — CURVA area-vs-clock per tier: dal MIN-SLACK (Fmax max) all'estremo LASCO (area min).
#   sweep_clock_curve.sh [tag ...]      (senza argomenti: tutti e 3 i tier)
#
# PERCHE' LA CURVA E NON UN SOLO PUNTO: l'Fmax post-route E le risorse dipendono dal VINCOLO imposto
# (misurato su R17, impl_point.tcl §header: stringendo il clock l'area SALE — il tool compra velocita'
# con area). Quindi non esiste "la configurazione ottima": esiste un TRADE-OFF. La curva lo mappa:
#   - MIN-SLACK (WNS~0): Fmax MASSIMA + l'area che costa  -> endpoint dell'HEADROOM;
#   - vincolo LASCO (deploy-ref 125 ns): area MINIMA alla velocita' che serve -> endpoint per il V2I.
#   - punti intermedi: la forma della curva.
#
# COME: GRIGLIA fissa di vincoli {0.90, 1.00, 1.40, 2.00, 3.00} x delay_OOC + 125 ns (deploy-ref).
#   synth TIMING-DRIVEN + impl a ogni periodo (la synth e' constraint-sensitive -> va rifatta a ogni P).
#   - MAX-FMAX = RITARDO RAGGIUNTO MINIMO (sta all'estremo STRETTO). NON si converge a WNS~0: misurato
#     che allentando il vincolo il ritardo PEGGIORA, quindi WNS~0 dava un'Fmax peggiore del punto stretto.
#   - MIN-AREA = deploy-ref 125 ns (clock lasco, il tool impacchetta al minimo).
#   Nessuna convergenza fragile: si campiona e si prende il min-delay. (verso confermato: stretto = piu'
#   Fmax E piu' area; allentando, entrambi calano fino al floor d'area.)
#
# RIPRODUCIBILITA': VHDL byte-identico (su disco, rigenerabile da gen_donatello_point); synth/impl
# pinnati da pin_determinism.tcl (maxThreads fisso, seed default 0) + versione Vivado registrata.
# Reuse: synth_point.tcl / impl_point.tcl NON modificati; struct_gate importato da run_block_a_matrix.sh.
#
# ⚠️ Vivado spezza gli argomenti sugli SPAZI: mai passargli un path del repo ("1.Reti Neurali").
set -uo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
COMMON="$REPO/matlab/study_tradeoff/common"
VIV="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
PIN="$COMMON/pin_determinism.tcl"
SYNTH="$COMMON/synth_point.tcl"
IMPL="$COMMON/impl_point.tcl"
OUTROOT=/d/zbd_tradeoff/donatello_split_sweep
TOP=Donatello_LUT64
PTS="$REPO/matlab/study_tradeoff/donatello/points_split_curve.tsv"

DEPLOY_REF=125.000   # ancora di area-minima (clock lasco; ~8 MHz, ben sopra il bisogno di deployment)

. <(sed -n '/^struct_gate() {/,/^}/p' "$COMMON/run_block_a_matrix.sh")

#      tag         decode  snn  P0 = delay OOC (ns)
TIERS=( "sp_slow      fused  R2  32.739"
        "sp_balanced  p3     R5  17.718"
        "sp_fast      p5     R9  10.762" )

# run_point <src> <P> <outdir> : synth+impl a P; su stdout "WNS WHS delay Fmax LUT FF DSP BRAM" o "ERR ..."
run_point() {
  local src="$1" P="$2" od="$3"
  mkdir -p "$od"
  "$VIV" -mode batch -source "$PIN" -source "$SYNTH" \
     -tclargs "$src" "$od/synth" "pt" "$P" "$TOP" > "$od/synth.log" 2>&1
  local dcp="$od/synth/post_synth.dcp"
  [ -f "$dcp" ] || { echo "ERR synth (vedi $od/synth.log)"; return 1; }
  "$VIV" -mode batch -source "$PIN" -source "$IMPL" \
     -tclargs "$dcp" "$P" "$od/impl" > "$od/impl.log" 2>&1
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

write_row() {  # write_row tag decode snn kind P wns whs delay fmax lut ff dsp bram
  local valid hold
  valid=$(awk -v w="$6" 'BEGIN{print (w<=0)?"si":"lim-inf"}')
  hold=$( awk -v h="$7" 'BEGIN{print (h>=0)?"ok":"NEG"}')
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
     "$1" "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9" "${10}" "${11}" "${12}" "${13}" "$valid" "$hold" >> "$PTS"
}

mkdir -p "$OUTROOT"
"$VIV" -version > "$OUTROOT/vivado_version.txt" 2>&1 || true
VIVVER=$(grep -m1 -oE "v[0-9]{4}\.[0-9]+" "$OUTROOT/vivado_version.txt" 2>/dev/null || echo "?")
echo "=== Vivado $VIVVER ; griglia {0.90,1.00,1.40,2.00,3.00}xP0 + deploy-ref=$DEPLOY_REF ns ; maxThreads pinnato ==="
# append-safe: header solo se assente; le righe di un tier si sostituiscono a tier-start (idempotente).
[ -f "$PTS" ] || printf "tag\tdecode\tsnn\tkind\tP_ns\tWNS\tWHS\tdelay_ns\tFmax_MHz\tLUT\tFF\tDSP\tBRAM\tvalid\thold\n" > "$PTS"

SEL="$*"
for entry in "${TIERS[@]}"; do
  set -- $entry; tag="$1"; var="$2"; sig="$3"; P0="$4"
  if [ -n "$SEL" ] && ! echo " $SEL " | grep -q " $tag "; then continue; fi
  src="/d/zbd_tradeoff/donatello_split/$tag/src"
  echo "--- $tag (decode=$var, SNN=$sig) ---"
  [ -f "$src/Donatello_LUT64.vhd" ] || { echo "FALLITO $tag: VHDL assente in $src"; continue; }
  struct_gate "$src" "$var" "$tag" "$sig" || { echo "FALLITO $tag: struct_gate"; continue; }
  # idempotenza: rimuovo righe precedenti di QUESTO tier (l'header inizia con "tag\t", non con "$tag\t")
  grep -v "^${tag}$(printf '\t')" "$PTS" > "$PTS.tmp" 2>/dev/null && mv "$PTS.tmp" "$PTS" || true

  # --- GRIGLIA di vincoli (tight -> loose): mappa la curva area-vs-clock in un solo passaggio ---
  # ⚠️ NIENTE convergenza a WNS=0. Misurato su SLOW (2026-07-22): allentando il vincolo il router
  # ottimizza MENO il percorso critico -> il ritardo raggiunto PEGGIORA (32,7ns->33,76 delay vs
  # 34,6ns->34,71). Convergere a WNS~0 trovava quindi un'Fmax PEGGIORE del punto stretto. Il max-Fmax
  # vero e' il RITARDO RAGGIUNTO MINIMO, che sta all'estremo STRETTO. Si campiona una griglia fissa e
  # si prende il min-delay; l'estremo lasco (deploy-ref) da' l'area minima. (Il verso e' confermato dai
  # dati: piu' stretto = piu' Fmax E piu' area.)
  best_ach=999999; best_desc=""; dep_lut=""
  for f in 0.90 1.00 1.40 2.00 3.00; do
    Pr=$(awk -v p="$P0" -v f="$f" 'BEGIN{printf "%.3f",p*f}')
    r=$(run_point "$src" "$Pr" "$OUTROOT/$tag/x${f}") || { echo "  [x$f P=$Pr] $r"; continue; }
    set -- $r; wns="$1"; whs="$2"; ach="$3"; fmax="$4"; lut="$5"; ff="$6"; dsp="$7"; bram="$8"
    printf "  [x%-4s] P=%-8s WNS=%-9s WHS=%-7s delay=%-7s Fmax=%-7s LUT=%s\n" "$f" "$Pr" "$wns" "$whs" "$ach" "$fmax" "$lut"
    write_row "$tag" "$var" "$sig" "x$f" "$Pr" "$wns" "$whs" "$ach" "$fmax" "$lut" "$ff" "$dsp" "$bram"
    [ "$(awk -v a="$ach" -v b="$best_ach" 'BEGIN{print (a+0<b+0)?1:0}')" = "1" ] && { best_ach="$ach"; best_desc="x$f (P=$Pr): Fmax=$fmax MHz, LUT=$lut, WHS=$whs"; }
  done
  # deploy-ref: area minima al clock lasco
  if r=$(run_point "$src" "$DEPLOY_REF" "$OUTROOT/$tag/deployref"); then
    set -- $r; wns="$1"; whs="$2"; ach="$3"; fmax="$4"; lut="$5"; ff="$6"; dsp="$7"; bram="$8"
    printf "  [deploy] P=%-8s WNS=%-9s Fmax=%-7s LUT=%s\n" "$DEPLOY_REF" "$wns" "$fmax" "$lut"
    write_row "$tag" "$var" "$sig" "deploy-ref" "$DEPLOY_REF" "$wns" "$whs" "$ach" "$fmax" "$lut" "$ff" "$dsp" "$bram"
    dep_lut="$lut"
  fi
  echo "  => $tag: MAX-FMAX (min-delay) = $best_desc | MIN-AREA (deploy-ref) LUT=$dep_lut"
done

echo "=== points_split_curve.tsv ==="
column -t -s$'\t' "$PTS" 2>/dev/null
