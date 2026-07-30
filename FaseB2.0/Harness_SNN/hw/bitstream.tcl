# T6b · M4 — bitstream PYNQ-Z1 del sistema (PS7 + tier_axi_lite + SmartConnect) all'FCLK deployabile.
# Ricostruisce il block design come build_impl.tcl (stessa procedura, quindi stesso sistema misurato in M2/M3)
# e arriva fino a write_bitstream + handoff .hwh/.xsa.
# Uso: vivado -mode batch -source bitstream.tcl -tclargs <SRCDIR> <ROOT> <FCLK_MHz> <OUTDIR> [<JOBS>]
set SRC  [lindex $argv 0]
set ROOT [lindex $argv 1]
set FCLK [lindex $argv 2]
set OUT  [lindex $argv 3]
set JOBS [expr {[llength $argv] > 4 ? [lindex $argv 4] : 6}]
set PART xc7z020clg400-1

set_param board.repoPaths [list "C:/AMDDesignTools/Boards_Drivers"]   ;# senza questo la board PYNQ non si trova
file delete -force $ROOT
create_project sysbit $ROOT -part $PART -force
set bp [lindex [get_board_parts -quiet -filter {NAME =~ *pynq-z1*}] 0]
if {$bp eq ""} { puts "BIT ERRORE: board PYNQ-Z1 non trovata"; exit 1 }
set_property board_part $bp [current_project]
puts "BIT board_part: $bp"

foreach f [split [string trim [read [open "$SRC/compile_order.txt" r]]] "\n"] {
  add_files -norecurse [list "$SRC/[string trim $f]"]
}
add_files -norecurse [list "$SRC/tier_axi_lite.v"]
update_compile_order -fileset sources_1

create_bd_design sys
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7]
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
  -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps
set_property -dict [list CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $FCLK CONFIG.PCW_USE_M_AXI_GP0 {1}] $ps
puts "BIT FCLK impostato: [get_property CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $ps] MHz"
create_bd_cell -type module -reference tier_axi_lite tier0
apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
  -config { Master {/ps7/M_AXI_GP0} Clk {Auto} } [get_bd_intf_pins tier0/S_AXI]
validate_bd_design
set wrp [make_wrapper -files [get_files sys.bd] -top -force]
add_files -norecurse $wrp
set_property top sys_wrapper [current_fileset]
update_compile_order -fileset sources_1

# --- synth + impl + BITSTREAM ---
launch_runs synth_1 -jobs $JOBS
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} { puts "BIT SYNTH-FALLITA"; exit 1 }
launch_runs impl_1 -to_step write_bitstream -jobs $JOBS
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
  puts "BIT IMPL/BITSTREAM-FALLITO: [get_property STATUS [get_runs impl_1]]"; exit 1
}
open_run impl_1

# --- cancello TIMING: un bitstream che non chiude i tempi non e' deployabile ---
set wns "NA"
catch { set wns [get_property SLACK [lindex [get_timing_paths -max_paths 1 -nworst 1 -setup] 0]] }
puts "BIT WNS=$wns"
report_timing_summary -file "$OUT/timing_bitstream_fclk${FCLK}.rpt"
report_utilization    -file "$OUT/util_bitstream_fclk${FCLK}.rpt"

# --- artefatti: .bit + handoff .hwh/.xsa ---
file mkdir $OUT
set bit [glob -nocomplain "$ROOT/sysbit.runs/impl_1/*.bit"]
if {[llength $bit] == 0} { puts "BIT ERRORE: nessun .bit prodotto"; exit 1 }
file copy -force [lindex $bit 0] "$OUT/snn_tier_donatello.bit"
puts "BIT_OK: $OUT/snn_tier_donatello.bit"
set hwh [glob -nocomplain "$ROOT/sysbit.gen/sources_1/bd/sys/hw_handoff/*.hwh"]
if {[llength $hwh] == 0} { set hwh [glob -nocomplain "$ROOT/sysbit.srcs/sources_1/bd/sys/hw_handoff/*.hwh"] }
if {[llength $hwh] > 0} {
  file copy -force [lindex $hwh 0] "$OUT/snn_tier_donatello.hwh"
  puts "HWH_OK: $OUT/snn_tier_donatello.hwh"
} else { puts "BIT ATTENZIONE: .hwh non trovato" }
if {[catch { write_hw_platform -fixed -include_bit -force "$OUT/snn_tier_donatello.xsa" } m]} {
  puts "BIT ATTENZIONE: XSA non generata: $m"
} else { puts "XSA_OK: $OUT/snn_tier_donatello.xsa" }
puts "BIT-DONE"
