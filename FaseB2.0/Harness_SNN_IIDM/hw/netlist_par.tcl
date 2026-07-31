# T7b — NETLIST (parte 1): implementa OOC `snniidm_axi_lite` (wrapper + Donatello_SNN_IIDM) alla frequenza
# DEPLOYABILE ed esporta la netlist post-place&route in modo FUNCSIM per la simulazione.
#
# PERIMETRO (dichiarato, non implicito): si implementa il wrapper OUT-OF-CONTEXT, NON l'intero block design.
# Il BD ha il PS7 come top: simularlo post-impl richiederebbe il BFM/VIP del processing system. Cio' che questo
# passo deve provare -- che la netlist PIAZZATA E INSTRADATA si comporti come l'RTL, catturando inizializzazione
# e X-propagation -- riguarda la logica PL, ed e' coperto qui. L'integrazione con protocol converter/PS7 resta
# verificata dall'STA di sistema (sweep FCLK: WNS +0,022 ns @40 MHz) e, in Fase C, dalla board.
#
# ⚠️ FUNCSIM e NON TIMESIM, per un motivo MISURATO in T6b: la sim di timing con SDF non produsse risultati
#    validi (tutti zero) per una configurazione del banco mai risolta. La domanda che conta -- la netlist
#    implementata e' logicamente equivalente all'RTL? -- e' risposta dalla funcsim; la FIRMA DEL TIMING spetta
#    all'STA (report_timing), non alla simulazione. E' anche la prassi industriale corrente. L'approccio
#    timesim NON viene riportato qui: codice morto che somiglia a codice vivo e' una trappola.
#
# Uso: vivado -mode batch -source netlist_par.tcl -tclargs <SRCDIR> <ROOT> <FCLK_MHz> <OUTDIR> [<JOBS>]
set SRC  [lindex $argv 0]
set ROOT [lindex $argv 1]
set FCLK [lindex $argv 2]
set OUT  [lindex $argv 3]
set JOBS [expr {[llength $argv] > 4 ? [lindex $argv 4] : 6}]
set PART xc7z020clg400-1
set PER  [expr {1000.0 / $FCLK}]

file delete -force $ROOT
create_project np $ROOT -part $PART -force
foreach f [split [string trim [read [open "$SRC/compile_order.txt" r]]] "\n"] {
  add_files -norecurse [list "$SRC/[string trim $f]"]
}
add_files -norecurse [list "$SRC/snniidm_axi_lite.v"]
update_compile_order -fileset sources_1
set_property top snniidm_axi_lite [current_fileset]

# vincolo di clock alla frequenza deployabile (lo stesso periodo del sistema implementato)
set xdc "$ROOT/clk.xdc"
set fh [open $xdc w]
puts $fh "create_clock -name aclk -period [format %.3f $PER] \[get_ports S_AXI_ACLK\]"
close $fh
add_files -fileset constrs_1 [list $xdc]

set_property -name {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} -value {-mode out_of_context} -objects [get_runs synth_1]
launch_runs synth_1 -jobs $JOBS
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} { puts "NETLIST SYNTH-FALLITA"; exit 1 }
launch_runs impl_1 -jobs $JOBS
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { puts "NETLIST IMPL-FALLITA"; exit 1 }
open_run impl_1

file mkdir $OUT
report_timing_summary -file "$OUT/timing_ooc_nl_fclk${FCLK}.rpt"
set wns "NA"
catch { set wns [get_property SLACK [lindex [get_timing_paths -max_paths 1 -nworst 1 -setup] 0]] }
puts "NETLIST OOC FCLK=$FCLK WNS=$wns"

# netlist funzionale post-place&route (primitive UNISIM, senza ritardi) per xsim
file mkdir "$ROOT/netlist"
write_verilog -force -mode funcsim "$ROOT/netlist/snniidm_axi_lite_func.v"
puts "NETLIST EXPORT-OK -> $ROOT/netlist/snniidm_axi_lite_func.v"
