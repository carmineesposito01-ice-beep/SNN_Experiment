#!/usr/bin/env bash
# Sonda risorse del plotone. Un punto = una sintesi out-of-context.
#
# uso:  ./probe_resources.sh "<lista N>" "<lista max_dsp>"
#       ./probe_resources.sh "1"  "220"          un punto solo, per misurare il costo
#       ./probe_resources.sh "1 2 3 4" "220 100 0"
set -u
QUI="$(cd "$(dirname "$0")" && pwd)"
SRC="${PROBE_SRC:-C:/t7bimpl/src}"
WORK="${PROBE_WORK:-C:/t7cprobe}"
VIV="${VIVADO_BIN:-C:/AMDDesignTools/2026.1/Vivado/bin}"

# ------------------------------------------------------------- cancelli PRIMA di ore di lavoro
nv=$(ls "$SRC"/*.v 2>/dev/null | wc -l)
if [ "$nv" -lt 11 ]; then
  echo "PROBE-ABORT: solo $nv file .v in $SRC (attesi almeno 11). Sorgenti RTL assenti o incompleti."
  exit 1
fi
if [ ! -f "$SRC/compile_order.txt" ]; then
  echo "PROBE-ABORT: manca $SRC/compile_order.txt"; exit 1
fi
if [ ! -f "$VIV/vivado.bat" ]; then
  echo "PROBE-ABORT: Vivado non trovato in $VIV (impostare VIVADO_BIN)"; exit 1
fi
mkdir -p "$WORK"

NS="${1:-1}"
DSPS="${2:-220}"
UNITA="${3:-dut}"

# `dut`     = Donatello_SNN_IIDM da solo: la logica di calcolo.
# `wrapper` = snniidm_axi_lite, che CONTIENE il DUT -- e' l'unita' DEPLOYABILE, con i registri
#             AXI e la macchina a stati che nel deployment ci sono e nel `dut` no. Misurare solo
#             il dut SOTTOSTIMA quante istanze entrano davvero.
export WRAPPER_V="${WRAPPER_V:-$(cd "$QUI/../.." && pwd)/FaseB2.0/Harness_SNN_IIDM/hw/snniidm_axi_lite.v}"
if [ "$UNITA" = "wrapper" ] && [ ! -f "$WRAPPER_V" ]; then
  echo "PROBE-ABORT: wrapper non trovato: $WRAPPER_V (impostare WRAPPER_V)"; exit 1
fi

echo "sonda: unita=$UNITA  N in [$NS] x max_dsp in [$DSPS]   sorgenti=$SRC   lavoro=$WORK"
echo "--- ogni punto e' una sintesi out-of-context; il costo del primo dice quello di tutti ---"

for N in $NS; do
  for D in $DSPS; do
    echo "=== unita=$UNITA N=$N max_dsp=$D  [avvio $(date +%H:%M:%S)] ==="
    "$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog \
      -source "$QUI/probe_resources.tcl" \
      -tclargs "$SRC" "$WORK/${UNITA}_N${N}_d${D}" "$N" "$D" "$UNITA" \
      2>&1 | grep -E "^(PROBE|ERROR:|CRITICAL WARNING:)"
  done
done
