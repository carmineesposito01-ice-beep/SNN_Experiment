#!/usr/bin/env bash
# =============================================================================================
# T7b · ENTRY-POINT UNICO della caratterizzazione HARDWARE del composto Donatello_SNN_IIDM
#   Uso:  bash run_harness_snniidm_hw.sh [stadio]
#   stadi: check | cosim | sweep | netlist | power | bitstream | summary | all
#          (default: summary — non lancia nulla, riestrae i numeri dagli artefatti esistenti)
#
# I numeri NON vivono qui ne' nella chat: stanno in ../results/*.md, GENERATI da script che parsano i
# report grezzi. Questo entry-point (a) riproduce gli artefatti, (b) li riestrae. Nessuna copia
# sincronizzata a mano.
#
# ⚠️ Costo per stadio, MISURATO su questo progetto (non ereditato):
#      cosim full-99  ~38 min/configurazione   ·  sweep      ~10 min/punto
#      netlist        ~14 min/scenario         ·  power      ~35 min
#      bitstream      ~15 min                  ·  summary    secondi
#    `all` = alcune ore: usare gli stadi.
# =============================================================================================
set -u
STAGE="${1:-summary}"
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
HERE="$(cd "$(dirname "$0")" && pwd)"
HARN="$(cd "$HERE/.." && pwd)"
RES="$HARN/results"
BITS="$HARN/bitstream"
HDLSRC="C:/t7hdlv/rtlgen_mdl"   # VERILOG del composto: cio' che T7a ha provato bit-esatto
WORK="C:/t7bw"                  # .mem validati di T7a
IMPL="C:/t7bimpl"               # work-dir dello sweep (contiene src/ pronta)
NLROOT="C:/t7bnl"               # progetto OOC + netlist funcsim
BITROOT="C:/t7bbit"
FCLK=40                         # frequenza DEPLOYABILE misurata dallo sweep (WNS +0,022 · WHS +0,033)
CLKHALF=12.5                    # semi-periodo a 40 MHz
JOBS=6                          # FISSO: risultati riproducibili
mkdir -p "$RES" "$BITS"

say() { echo "[$(date +%H:%M:%S)] $*"; }

# ---------------------------------------------------------------------------------------------
# PROVENIENZA in forma di INTEGRITA' DEL FILE, non rigenera-e-confronta.
# ⚠️ `makehdl` NON e' deterministico sui nomi temporanei interni: un cancello che rigenera l'RTL e
#    confronta gli MD5 fallirebbe SEMPRE, anche a sorgenti identici (accertato in T7b). Si registra
#    quindi la firma dei sorgenti caratterizzati e la si CONFRONTA; una differenza e' un allarme.
# ---------------------------------------------------------------------------------------------
sig_src() { cat "$IMPL/src"/*.v "$IMPL/src/compile_order.txt" 2>/dev/null | md5sum | cut -d' ' -f1; }

stage_check() {
  say "CHECK prerequisiti e provenienza"
  local bad=0
  for d in "$HDLSRC" "$WORK" "$IMPL/src"; do
    [ -d "$d" ] || { echo "  MANCA la cartella $d"; bad=1; }
  done
  local nv; nv=$(ls "$IMPL/src"/*.v 2>/dev/null | wc -l)
  [ "$nv" -ge 11 ] || { echo "  solo $nv .v in $IMPL/src (attesi >=11: 10 del DUT + wrapper)"; bad=1; }
  local nm=0
  for i in $(seq 1 99); do
    for k in stim gold len; do [ -s "$WORK/axi_${k}_$i.mem" ] || nm=$((nm+1)); done
  done
  [ "$nm" -eq 0 ] || { echo "  mancano $nm file .mem su 297 (gen_axi_golden.m non e' stato eseguito?)"; bad=1; }
  [ $bad -eq 0 ] || { echo "CHECK-FALLITO: prerequisiti incompleti"; return 1; }
  local s; s=$(sig_src)
  echo "  firma dei sorgenti caratterizzati: $s"
  if [ -f "$RES/src.sig" ]; then
    if [ "$(cat "$RES/src.sig")" = "$s" ]; then
      echo "  provenienza OK: coincide con quella registrata"
    else
      echo "  ⚠️ ALLARME: la firma NON coincide con $RES/src.sig ($(cat "$RES/src.sig"))"
      echo "     i risultati in results/ si riferiscono a sorgenti DIVERSI da quelli presenti."
      return 1
    fi
  else
    printf '%s' "$s" > "$RES/src.sig"; echo "  firma registrata per la prima volta in results/src.sig"
  fi
  echo "  297 file .mem presenti · $nv sorgenti Verilog · FCLK $FCLK MHz"
}

stage_cosim()   { say "COSIM AXI sui 99 (gating ON = deployment)"
                  bash "$HERE/run_axi_cosim.sh" "$WORK" "$HDLSRC" "$HERE/snniidm_axi_lite.v" \
                       "$HERE/tb_snniidm_axi.v" 99 600 1; }

stage_sweep()   { say "SWEEP FCLK (utilizzo post-route + WNS/WHS)"
                  bash "$HERE/run_impl_sweep.sh" "15 20 25 30 35 40 45 50"
                  python "$HERE/gen_sweep_report.py"; }

stage_netlist() { say "NETLIST funcsim sul sottoinsieme dichiarato [1 4 9]"
                  bash "$HERE/run_netlist.sh" "$FCLK" "$CLKHALF" "1 4 9" | tee "$RES/netlist_func.log"
                  python "$HERE/gen_netlist_report.py"; }

stage_power()   { say "ENERGIA (idle + 8 carichi reali + duty REALE + report_power)"
                  bash "$HERE/run_power.sh" "$FCLK" "$CLKHALF" all | tee "$RES/power.log"
                  python "$HERE/gen_power_report.py"; }

stage_bit()     { say "BITSTREAM PYNQ-Z1 @${FCLK} MHz + handoff"
                  "$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog \
                    -source "$HERE/bitstream.tcl" -tclargs "$IMPL/src" "$BITROOT" "$FCLK" "$BITS" "$JOBS" \
                    2>&1 | grep -E "^(BIT|HWH|XSA|ERROR:)"
                  # CANCELLO: un .bit che non chiude i tempi non e' deployabile, e un .bit assente
                  # non e' "zero problemi" -- e' uno stadio fallito.
                  [ -s "$BITS/donatello_snn_iidm.bit" ] \
                    || { echo "BITSTREAM-FALLITO: nessun .bit prodotto"; return 1; }
                  say "  bitstream: $(stat -c%s "$BITS/donatello_snn_iidm.bit") byte"; }

stage_summary() {
  echo "================ SINTESI DAGLI ARTEFATTI ($(date +'%Y-%m-%d %H:%M')) ================"
  echo "Ogni riga e' RIGENERATA dai file in results/. Se un artefatto manca, lo dice: un numero"
  echo "assente non deve somigliare a un numero verde."
  local miss=0
  for f in SWEEP_FCLK.md NETLIST.md POWER.md COSIM_AXI.md RESULTS.md; do
    if [ -s "$RES/$f" ]; then printf '  [ok]      %s\n' "$f"; else printf '  [ASSENTE] %s\n' "$f"; miss=$((miss+1)); fi
  done
  echo "-------------------------------------------------------------------------------"
  grep -h "Frequenza deployabile\|Limite del cammino critico" "$RES/SWEEP_FCLK.md" 2>/dev/null | head -2
  grep -h "^| \*\*totale\*\*" "$RES/NETLIST.md" 2>/dev/null | head -1
  grep -h "Potenza al duty reale\|Copertura SAIF" "$RES/POWER.md" 2>/dev/null | head -2
  grep -h "COSIM-DONE\|0 / 58 522\|0/58 522" "$RES/COSIM_AXI.md" 2>/dev/null | head -2
  echo "-------------------------------------------------------------------------------"
  [ -f "$RES/src.sig" ] && echo "  provenienza dei risultati: $(cat "$RES/src.sig")"
  [ "$miss" -eq 0 ] && echo "  tutti gli artefatti presenti" || echo "  ⚠️ $miss artefatti MANCANTI: la sintesi e' parziale"
  echo "==============================================================================="
}

case "$STAGE" in
  check)     stage_check ;;
  cosim)     stage_check && stage_cosim ;;
  sweep)     stage_check && stage_sweep ;;
  netlist)   stage_check && stage_netlist ;;
  power)     stage_check && stage_power ;;
  bitstream) stage_check && stage_bit ;;
  summary)   stage_summary ;;
  all)       stage_check && stage_cosim && stage_sweep && stage_netlist && stage_power \
             && stage_bit && stage_summary ;;
  *) echo "stadio non riconosciuto: $STAGE"
     echo "usa: check | cosim | sweep | netlist | power | bitstream | summary | all"; exit 2 ;;
esac
