# Diagnostica: da dove viene la cascata BUFG-BUFG a N=3?
#
# Si ferma dopo la SINTESI e riporta la struttura del clock. Costa ~3 min invece dei ~12 di
# un'implementazione completa, e risponde alla domanda invece di farmela indovinare una seconda
# volta.
#
# Uso: vivado -mode batch -source diag_clock.tcl -tclargs <SRC> <ROOT> <FCLK> <N>

set SRC  [lindex $argv 0]
set ROOT [lindex $argv 1]
set FCLK [lindex $argv 2]
set N    [lindex $argv 3]
set PART xc7z020clg400-1

set_param board.repoPaths [list "C:/AMDDesignTools/Boards_Drivers"]
file delete -force $ROOT
create_project diag $ROOT -part $PART -force
set bp [lindex [get_board_parts -quiet -filter {NAME =~ *pynq-z1*}] 0]
set_property board_part $bp [current_project]

foreach f [split [string trim [read [open "$SRC/compile_order.txt" r]]] "\n"] {
  add_files -norecurse [list "$SRC/[string trim $f]"]
}
add_files -norecurse [list "$::env(WRAPPER_V)"]
update_compile_order -fileset sources_1

create_bd_design sys
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7]
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
  -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps
set_property -dict [list CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $FCLK CONFIG.PCW_USE_M_AXI_GP0 {1}] $ps

set pins {}
for {set i 0} {$i < $N} {incr i} {
  create_bd_cell -type module -reference snniidm_axi_lite tier$i
  lappend pins [get_bd_intf_pins tier$i/S_AXI]
}
apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
  -config { Master {/ps7/M_AXI_GP0} Clk {Auto} } $pins

validate_bd_design

# --- che celle ha creato l'automazione? ---
puts "DIAG celle del block design (N=$N):"
foreach c [get_bd_cells] {
  puts "DIAG   [get_property NAME $c]  vlnv=[get_property VLNV $c]"
}

set wrp [make_wrapper -files [get_files sys.bd] -top -force]
add_files -norecurse $wrp
set_property top sys_wrapper [current_fileset]
update_compile_order -fileset sources_1

launch_runs synth_1 -jobs 6
wait_on_run synth_1
open_run synth_1

# --- la struttura del clock DOPO la sintesi: chi guida chi ---
puts "DIAG BUFG istanziati:"
foreach b [get_cells -hier -filter {REF_NAME =~ BUFG*}] {
  set inet [get_nets -quiet -of [get_pins -quiet $b/I]]
  set drv  [get_pins -quiet -of $inet -filter {DIRECTION == OUT}]
  puts "DIAG   [get_property NAME $b] (ref [get_property REF_NAME $b])  <- [get_property NAME $drv]"
}
puts "DIAG reti di clock:"
report_clock_networks -file "$ROOT/clock_networks.rpt"
puts "DIAG report in $ROOT/clock_networks.rpt"
puts "DIAG-DONE"
