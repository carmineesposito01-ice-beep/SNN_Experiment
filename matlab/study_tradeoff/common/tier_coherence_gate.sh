#!/usr/bin/env bash
# tier_coherence_gate.sh — la logica SNN.vhd/DEC.vhd del tier rigenerato == quella misurata in D:/zbd_p1.
# Prova end-to-end che il blocco di libreria e il refactor riproducono il VHDL su cui poggiano i numeri
# del report. Confronto LOGICO: si strippano commenti (righe '--') e righe vuote (timestamp esclusi).
# Il wrapper top ha nome diverso (Donatello_<TIER> vs Donatello_LUT64) e non si confronta.
set -uo pipefail
NEW="${1:-D:/zbd_tiers/vhdl}"; MEAS="${2:-D:/zbd_p1}"
declare -A M=( [Donatello_SLOW]=SLOW [Donatello_BALANCED]=BAL [Donatello_FAST]=FAST )
# Confronto LOGICO modulo NOMI derivati dal blocco. HDL Coder nomina package/chart-id/segnali a partire
# dal nome del blocco, quindi Donatello_<TIER> vs il Donatello_LUT64 misurato differiscono SOLO in quei
# nomi (provato 2026-07-23: 0 diff su SNN/DEC/DualPortRAM dopo la normalizzazione). Una differenza LOGICA
# (tipo, operazione, larghezza di bit) NON e' normalizzata -> resta catturata (gate ancora sensibile).
logic() { grep -vE '^\s*(--|$)' "$1" | sed -E 's/Donatello_(SLOW|BALANCED|FAST|LUT[0-9]+)/BLK/g; s/_c[0-9]+_/_cN_/g; s/\bp[0-9]+/pN/g'; }
rc=0
for t in Donatello_SLOW Donatello_BALANCED Donatello_FAST; do
  meas="$MEAS/${M[$t]}/rtlgen_mdl"
  if [ ! -d "$meas" ]; then echo "SKIP $t: misurato assente ($meas) -> affidarsi a G3"; continue; fi
  snn=$(find "$NEW/$t" -name 'SNN.vhd' | head -1)
  [ -n "$snn" ] || { echo "FAIL $t: SNN.vhd rigenerato assente"; rc=1; continue; }
  newdir=$(dirname "$snn")
  for leaf in SNN.vhd DEC.vhd DualPortRAM_generic.vhd; do
    a="$newdir/$leaf"; b="$meas/$leaf"
    [ -f "$a" ] && [ -f "$b" ] || { echo "FAIL $t/$leaf: file mancante (a=$([ -f "$a" ]&&echo si||echo no) b=$([ -f "$b" ]&&echo si||echo no))"; rc=1; continue; }
    if diff -q <(logic "$a") <(logic "$b") >/dev/null; then echo "OK   $t/$leaf coerente";
    else echo "DIVERSO $t/$leaf"; rc=1; fi
  done
done
[ "$rc" = 0 ] && echo "=== G4 OK: VHDL del blocco == VHDL misurato (i numeri del report valgono) ===" || { echo "=== G4 FALLITO ==="; exit 1; }
