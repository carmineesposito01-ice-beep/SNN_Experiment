#!/usr/bin/env bash
# Fase C -- costruisce i bitstream per la misura differenziale di potenza (C3).
#
# uso: ./build_bitstreams.sh [blank|x1|x3|tutti]
#
#   x1     UNA istanza. Non serve alla campagna (esiste gia' da T7b), serve come CANCELLO DI
#          TARATURA: deve riprodurre le risorse gia' misurate. Se non le riproduce, la procedura
#          parametrica non e' la stessa di T7b e nessuno degli altri due e' confrontabile.
#   blank  PS7 e basta. (x1)-(blank) isola il contributo del PL.
#   x3     tre istanze. Amplifica il guadagno del clock gating da ~14 a ~42 conteggi.
set -eu
QUI="$(cd "$(dirname "$0")" && pwd)"
FASEC="$(dirname "$QUI")"
REPO="$(dirname "$FASEC")"

VIV="${VIVADO_BIN:-C:/AMDDesignTools/2026.1/Vivado/bin}"
SRC="${BIT_SRC:-C:/t7bimpl/src}"
ROOT="${BIT_ROOT:-C:/t7cbit}"
OUT="${BIT_OUT:-$FASEC/bitstream}"
FCLK="${BIT_FCLK:-40}"
JOBS="${BIT_JOBS:-6}"
export WRAPPER_V="${WRAPPER_V:-$REPO/FaseB2.0/Harness_SNN_IIDM/hw/snniidm_axi_lite.v}"

# ---------------------------------------------------------- cancelli PRIMA di ore di sintesi
[ -f "$VIV/vivado.bat" ]        || { echo "BIT-ABORT: Vivado non trovato in $VIV"; exit 1; }
[ -f "$SRC/compile_order.txt" ] || { echo "BIT-ABORT: manca $SRC/compile_order.txt"; exit 1; }
[ -f "$WRAPPER_V" ]             || { echo "BIT-ABORT: wrapper non trovato: $WRAPPER_V"; exit 1; }
case "$ROOT" in *" "*) echo "BIT-ABORT: ROOT con spazi ($ROOT): Vivado si spezza"; exit 1;; esac
mkdir -p "$OUT"

costruisci() {
  local nome="$1" n="$2"
  echo "=== $nome (N=$n istanze, FCLK=$FCLK MHz) [avvio $(date +%H:%M:%S)] ==="
  "$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog \
    -source "$QUI/bitstream_n.tcl" \
    -tclargs "$SRC" "$ROOT/$nome" "$FCLK" "$OUT" "$n" "$nome" "$JOBS" \
    2>&1 | grep -E "^(BITN|ERROR:|CRITICAL WARNING:)"
}

case "${1:-tutti}" in
  blank) costruisci blank 0 ;;
  x1)    costruisci x1    1 ;;
  x3)    costruisci x3    3 ;;
  tutti)
    # Ordine deliberato: prima x1, che e' il cancello di taratura. Se non riproduce T7b non ha
    # senso spendere le ore successive.
    costruisci x1 1 && costruisci blank 0 && costruisci x3 3 ;;
  *) echo "uso: $0 [blank|x1|x3|tutti]"; exit 2 ;;
esac
