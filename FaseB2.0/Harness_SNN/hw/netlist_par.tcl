# T6b · M2 — NETLIST-PAR (parte 1): implementa OOC il wrapper+Tier all'FCLK scelto ed esporta la netlist
# post-place&route + SDF, per la simulazione di timing.
#
# PERIMETRO (dichiarato, non implicito): si implementa `tier_axi_lite` (wrapper + Donatello_Tier) OUT-OF-CONTEXT,
# NON l'intero block design. Il BD ha il PS7 come top: simularlo post-impl richiederebbe il BFM/VIP del
# processing system. Cio' che NETLIST-PAR deve provare -- che la netlist PIAZZATA E INSTRADATA si comporti come
# l'RTL, catturando inizializzazione e X-propagation -- riguarda la logica PL, ed e' coperto qui.
# L'integrazione con SmartConnect/PS7 resta verificata dall'STA di sistema (sweep FCLK) e, in Fase C, dalla board.
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
add_files -norecurse [list "$SRC/tier_axi_lite.v"]
update_compile_order -fileset sources_1
set_property top tier_axi_lite [current_fileset]

# vincolo di clock all'FCLK scelto (stesso periodo del sistema implementato)
set xdc "$ROOT/clk.xdc"
set fh [open $xdc w]
puts $fh "create_clock -name aclk -period [format %.3f $PER] \[get_ports S_AXI_ACLK\]"
close $fh
add_files -fileset constrs_1 [list $xdc]

set_property -name {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} -value {-mode out_of_context} -objects [get_runs synth_1]
launch_runs synth_1 -jobs $JOBS
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} { puts "NETLIST-PAR SYNTH-FALLITA"; exit 1 }
launch_runs impl_1 -jobs $JOBS
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { puts "NETLIST-PAR IMPL-FALLITA"; exit 1 }
open_run impl_1

file mkdir $OUT
report_timing_summary -file "$OUT/timing_ooc_fclk${FCLK}.rpt"
set wns "NA"
catch { set wns [get_property SLACK [lindex [get_timing_paths -max_paths 1 -nworst 1 -setup] 0]] }
puts "NETLIST-PAR OOC FCLK=$FCLK WNS=$wns"

# netlist di timing + SDF per xsim
file mkdir "$ROOT/netlist"
write_verilog -force -mode timesim -sdf_anno true "$ROOT/netlist/tier_axi_lite_time.v"
write_sdf     -force                              "$ROOT/netlist/tier_axi_lite_time.sdf"
puts "NETLIST-PAR EXPORT-OK -> $ROOT/netlist"
