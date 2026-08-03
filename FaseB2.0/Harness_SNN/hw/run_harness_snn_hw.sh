#!/usr/bin/env bash
# =============================================================================================
# T6b · ENTRY-POINT UNICO della caratterizzazione HARDWARE dell'Harness_SNN
#   Uso:  bash run_harness_snn_hw.sh [stadio]
#   stadi: check | probe | cosim | sweep | netlist | power | bitstream | summary | all
#          (default: summary — non lancia nulla, riestrae i numeri dagli artefatti esistenti)
#
# I numeri interpretati vivono in ../results/RESULTS_HW.md (UNICA fonte, scritta a mano: contiene l'analisi).
# Questo script (a) riproduce gli artefatti, (b) riestrae i valori chiave e li stampa, cosi' un rilancio si
# CONFRONTA con quanto documentato invece di duplicarlo.  Nessuna copia sincronizzata a mano dei numeri.
#
# ⚠️ Costo indicativo per stadio (misurato): probe ~15 min · cosim full-60 ~50 min/config · sweep ~10 min/punto
#    netlist ~22 min/traiettoria · power ~30 min (13 run) · bitstream ~10 min. `all` = molte ore: usare gli stadi.
# =============================================================================================
set -u
STAGE="${1:-summary}"
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
MAT="C:/Program Files/MATLAB/R2026a/bin/matlab.exe"
HERE="$(cd "$(dirname "$0")" && pwd)"
HARN="$(cd "$HERE/.." && pwd)"
RES="$HARN/results"
BITS="$HARN/bitstream"
MROOT="$(cd "$HERE/../../../matlab" && pwd)"
HDLROOT="$MROOT/hdlsrc_donatello_tier"
HDLSRC="$HDLROOT/rtlgen_mdl"
ROOT="D:/zbd_tier_hw"          # work-dir CORTA senza spazi (il repo sta sotto ".../1.Reti Neurali/...")
SRC="$ROOT/src"
FCLK=52                        # FCLK deployabile determinato dallo sweep (M2)
CLKHALF=9.615                  # semi-periodo a 52 MHz: OBBLIGATORIO per la sim di timing/netlist
JOBS=6                         # FISSO: risultati riproducibili
mkdir -p "$RES" "$BITS" "$SRC"

say() { echo "[$(date +%H:%M:%S)] $*"; }

# ---------------------------------------------------------------------------------------------
# PROVENIENZA DEL DUT: il VHDL caratterizzato deve essere l'artefatto validato in T6a.
# Se manca -> lo rigenera E rilancia il gate T6a (non si caratterizza in HW un RTL non validato).
# Se presente -> confronta il checksum con quello registrato; una differenza e' un ALLARME, non un dettaglio.
# ---------------------------------------------------------------------------------------------
stage_check() {
  say "CHECK provenienza del VHDL del DUT"
  if [ ! -s "$HDLSRC/Donatello_Tier.vhd" ]; then
    say "  VHDL assente -> rigenero e RILANCIO IL GATE T6a (obbligatorio prima di caratterizzare)"
    "$MAT" -sd "$MROOT" -batch "rtl_gen_dut('Donatello_Tier',[],'VHDL',{'TIER','BALANCED','NFRAC','13'})" \
      2>&1 | grep -E "VHDL generato|ERROR|Errore" | head -5
    "$MAT" -sd "$HARN" -batch "r=run_harness_snn('smoke'); assert(r.rtl.nMismatch==0,'GATE T6a FALLITO'); fprintf('GATE-T6a OK %d/%d\n', r.rtl.nMismatch, r.rtl.n)" \
      2>&1 | grep -E "GATE-T6a|FALLITO|ERROR" | head -5
  fi
  # ⚠️ NON usare `cat $(ls "$dir"/*.vhd)`: la command substitution spezza sugli spazi e il path del repo contiene
  #    "1.Reti Neurali" -> cat non legge nulla e md5sum restituisce l'hash della stringa VUOTA
  #    (d41d8cd98f00b204e9800998ecf8427e), cioe' un cancello che PASSA senza verificare niente.
  #    La forma corretta e' il glob diretto: bash lo espande in parole non ulteriormente splittate.
  SUM=$(cat "$HDLSRC"/*.vhd | md5sum | cut -d' ' -f1)
  if [ "$SUM" = "d41d8cd98f00b204e9800998ecf8427e" ]; then
    say "  ❌ checksum = hash della stringa vuota: nessun file letto. Controllare \$HDLSRC ($HDLSRC)"
    return 1
  fi
  REF="$HERE/vhdl_ref.md5"
  if [ -s "$REF" ]; then
    if [ "$SUM" = "$(cat "$REF")" ]; then
      say "  OK  checksum VHDL invariato ($SUM) -> e' l'artefatto caratterizzato"
    else
      say "  ⚠️  CHECKSUM VHDL DIVERSO! atteso $(cat "$REF") trovato $SUM"
      say "      Il DUT NON e' quello dei numeri in RESULTS_HW.md: rilanciare il gate T6a e ri-caratterizzare."
      return 1
    fi
  else
    echo "$SUM" > "$REF"
    say "  checksum VHDL registrato per la prima volta: $SUM"
  fi
  say "  sincronizzo i sorgenti nella work-dir corta $SRC"
  cp "$HDLSRC"/*.vhd "$HDLSRC/compile_order.txt" "$SRC"/ && cp "$HERE/tier_axi_lite.v" "$SRC"/
}

stage_probe()   { say "PROBE assunzioni HW (P1 ce_out · P2 mixed-language · P3 board · P4 BD/FCLK)"
                  bash "$HERE/run_probes_t6b.sh" 2>&1 | tee "$RES/probes_t6b.log" | grep -E "^(P1|P2|P3|P4)"; }

stage_cosim()   { say "COSIM AXI full-60 (gating ON = deployment)"
                  "$MAT" -sd "$HERE" -batch "gen_axi_golden([],[],'$ROOT')" 2>&1 | tail -2
                  bash "$HERE/run_axi_cosim.sh" "$ROOT" "$HDLSRC" "$HERE" 1000 60 1 | tee -a "$RES/axi_cosim_full60.log" | grep -E "TOT"; }

stage_sweep()   { say "SWEEP FCLK (utilizzo post-route + WNS)"
                  bash "$HERE/run_impl_sweep.sh" "30 40 50 52 55 60" 2>&1 | tee -a "$RES/impl_sweep.log" | grep -E "^SWEEP"; }

stage_netlist() { say "NETLIST-PAR funzionale (netlist post-route == blocco)"
                  "$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog -source "$HERE/netlist_par.tcl" \
                    -tclargs "$SRC" "$ROOT/np_impl" $FCLK "$RES" $JOBS 2>&1 | grep -E "^NETLIST-PAR"
                  "$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog -source "$HERE/netlist_funcsim.tcl" \
                    -tclargs "$ROOT/np_impl/np.xpr" "$ROOT/np_impl/netlist" 2>&1 | grep -E "FUNCSIM"
                  bash "$HERE/run_netlist_func.sh" "$ROOT" "$ROOT/np_impl/netlist" "$HERE" 1000 3 1 $CLKHALF \
                    2>&1 | tee "$RES/netlist_func.log" | grep -E "TOT|traj"; }

stage_power()   { say "STUDIO ENERGETICO (9 workload + worst · idle gatata/non · duty REALE)"
                  "$MAT" -sd "$HERE" -batch "gen_power_workloads(50,'$ROOT')" 2>&1 | tail -3
                  bash "$HERE/run_saif_active.sh" "$ROOT" "$ROOT/np_impl/netlist" "$HERE" 50 10 1 $CLKHALF | grep -E "wl "
                  bash "$HERE/run_saif_idle.sh"   "$ROOT" "$ROOT/np_impl/netlist" "$HERE" 0 $CLKHALF "200 1000 5000" | grep finestra
                  bash "$HERE/run_saif_idle.sh"   "$ROOT" "$ROOT/np_impl/netlist" "$HERE" 1 $CLKHALF "200" | grep finestra
                  say "  duty REALE: 1 control-step intero (5.199.584 clk di idle = 0,1 s @52 MHz)"
                  ( cd "$ROOT" && printf '`define GATEMODE 0\n`define CLKHALF %s\n`define NSTEP 1\n`define IDLECYC 5199584\n`define HB 500000\n' "$CLKHALF" > axi_params.vh
                    "$VIV/xvlog.bat" -i . pd/tier_axi_lite_func.v pd/tb_power_duty.v \
                      "C:/AMDDesignTools/2026.1/Vivado/data/verilog/src/glbl.v" >/dev/null 2>&1
                    "$VIV/xelab.bat" -debug typical -L unisims_ver -relax tb_power_duty glbl -s snapREAL >/dev/null 2>&1
                    printf 'run 2 us\nopen_saif "%s/saif_duty_REAL.saif"\nlog_saif [get_objects -r /tb_power_duty/dut/*]\nrun all\nclose_saif\nquit\n' "$ROOT" > sim_real.tcl
                    "$VIV/xsim.bat" snapREAL -tclbatch sim_real.tcl 2>&1 | grep -E "DUTY-(CFG|DONE)" )
                  say "  SAIF -> potenza (una sessione Vivado, reset_switching_activity fra i workload)"
                  "$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog -source "$HERE/power_report.tcl" \
                    -tclargs "$ROOT/np_impl/np.xpr" "$RES" \
                    $(for i in $(seq 1 10); do echo -n "$ROOT/saif_act_g1_wl${i}.saif "; done) \
                    "$ROOT/saif_idle_g0_w200.saif" "$ROOT/saif_idle_g1_w200.saif" "$ROOT/saif_duty_REAL.saif" \
                    2>&1 | tee "$RES/m3_power.log" | grep -E "^PW "; }

stage_bit()     { say "BITSTREAM PYNQ-Z1 @${FCLK} MHz + handoff"
                  "$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog -source "$HERE/bitstream.tcl" \
                    -tclargs "$SRC" "$ROOT/bit_impl" $FCLK "$BITS" $JOBS 2>&1 | tee "$RES/m4_bitstream.log" \
                    | grep -E "^(BIT|HWH_OK|XSA_OK)"; }

# ---------------------------------------------------------------------------------------------
# SUMMARY: riestrae i valori chiave DAGLI ARTEFATTI (non da valori scritti a mano nello script),
# per confrontarli con quanto documentato in RESULTS_HW.md. Un valore mancante si dice "assente",
# non si inventa.
# ---------------------------------------------------------------------------------------------
stage_summary() {
  echo
  echo "================ SINTESI DAGLI ARTEFATTI ($(date +%Y-%m-%d\ %H:%M)) ================"
  printf "%-46s %s\n" "AXI-COSIM full-60 (gating ON):" "$(grep -h 'AXI-COSIM-TOT' "$RES/axi_cosim_full60.log" 2>/dev/null | tail -1 || echo assente)"
  printf "%-46s %s\n" "NETLIST-PAR funzionale:"        "$(grep -h 'NETLIST-FUNC-TOT' "$RES/netlist_func.log" 2>/dev/null | tail -1 || echo assente)"
  echo "--- sweep FCLK (WNS e risorse post-route) ---"
  grep -h '^SWEEP' "$RES/impl_sweep.log" 2>/dev/null | sort -u || echo "  assente"
  echo "--- potenza (Confidence deve essere High su OGNI riga) ---"
  grep -h '^PW ' "$RES/m3_power.log" 2>/dev/null || echo "  assente"
  echo "--- bitstream ---"
  grep -hE '^(BIT WNS|BIT_OK|HWH_OK|XSA_OK)' "$RES/m4_bitstream.log" 2>/dev/null || echo "  assente"
  for f in snn_tier_donatello.bit snn_tier_donatello.hwh snn_tier_donatello.xsa; do
    if [ -s "$BITS/$f" ]; then printf "  %-32s %s byte\n" "$f" "$(stat -c%s "$BITS/$f")"; else echo "  $f ASSENTE"; fi
  done
  grep -ho 'BOARD="[^"]*"' "$BITS"/*.hwh 2>/dev/null | head -1
  echo "==============================================================================="
  echo "I numeri INTERPRETATI (con natura misurato/derivato/stima e caveat) sono in:"
  echo "  $RES/RESULTS_HW.md      <-- unica fonte per i report"
  echo "==============================================================================="
}

case "$STAGE" in
  check)     stage_check ;;
  probe)     stage_check && stage_probe ;;
  cosim)     stage_check && stage_cosim ;;
  sweep)     stage_check && stage_sweep ;;
  netlist)   stage_check && stage_netlist ;;
  power)     stage_check && stage_power ;;
  bitstream) stage_check && stage_bit ;;
  summary)   stage_summary ;;
  all)       stage_check && stage_probe && stage_cosim && stage_sweep && stage_netlist \
             && stage_power && stage_bit && stage_summary ;;
  *) echo "stadio non riconosciuto: $STAGE"; echo "usa: check|probe|cosim|sweep|netlist|power|bitstream|summary|all"; exit 2 ;;
esac
say "FINE stadio '$STAGE'"
