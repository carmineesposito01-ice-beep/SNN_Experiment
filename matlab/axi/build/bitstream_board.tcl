# Bitstream con board preset PYNQ-Z1 (DDR/MIO/clock reali) + XSA handoff. ROOT corto.
set ROOT "D:/zbd"
file delete -force $ROOT
file mkdir $ROOT
set SNN "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/codegen/snn_top_b2/hdlsrc"
set AXI "C:/Users/USERPO~1/AppData/Local/Temp/claude/D--Project-MBSE-0-Documenti-Platooning-Focus-Traffic-Flow-2025/63719052-fc3e-48ab-9cdd-20922bd2deb6/scratchpad/axi_ip/snn_b2_axi_1_0/hdl"
set IPREPO "$ROOT/ipr"
file mkdir $IPREPO
set_param board.repoPaths [list "C:/AMDDesignTools/Boards_Drivers"]

# --- package IP ---
create_project pkg "$ROOT/pkg" -part xc7z020clg400-1 -force
add_files [list "$SNN/snn_top_b2_pkg.vhd" "$SNN/DualPortRAM_generic.vhd" "$SNN/snn_top_b2.vhd" "$AXI/snn_top_b2_flat.vhd" "$AXI/snn_b2_axi_lite.v"]
set_property top snn_b2_axi_lite [current_fileset]
update_compile_order -fileset sources_1
ipx::package_project -root_dir $IPREPO -vendor user.org -library user -taxonomy /UserIP -import_files -set_current true
ipx::save_core [ipx::current_core]
close_project

# --- BD con board PYNQ-Z1 ---
set bpart [lindex [get_board_parts -filter {NAME =~ *pynq-z1*}] 0]
puts "BOARD_PART: $bpart"
create_project bd "$ROOT/bd" -part xc7z020clg400-1 -force
set_property board_part $bpart [current_project]
set_property ip_repo_paths $IPREPO [current_project]
update_ip_catalog
create_bd_design "d1"
set ps7v [lindex [get_ipdefs -all -filter {NAME == processing_system7}] 0]
set ps [create_bd_cell -type ip -vlnv $ps7v ps7]
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
  -config { apply_board_preset "1" make_external "FIXED_IO, DDR" Master "Disable" Slave "Disable" } $ps
# override FCLK0 = 8 MHz (il preset lo mette a 100 -> path lane ~118 ns non chiude)
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 {1} CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {8}] $ps
set snnv [lindex [get_ipdefs -all -filter {NAME == snn_b2_axi_lite}] 0]
create_bd_cell -type ip -vlnv $snnv snn0
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config { Master "/ps7/M_AXI_GP0" Clk "Auto" } [get_bd_intf_pins snn0/S_AXI]
validate_bd_design
save_bd_design
set wrap [make_wrapper -files [get_files d1.bd] -top]
add_files -norecurse $wrap
set_property top d1_wrapper [current_fileset]
update_compile_order -fileset sources_1

launch_runs impl_1 -to_step write_bitstream -jobs 6
wait_on_run impl_1
puts "IMPL STATUS: [get_property STATUS [get_runs impl_1]]  PROGRESS: [get_property PROGRESS [get_runs impl_1]]"
set bit [glob -nocomplain "$ROOT/bd/bd.runs/impl_1/*.bit"]
if { [llength $bit] > 0 } { puts "BITSTREAM_OK: [lindex $bit 0]" } else { puts "BITSTREAM: NON generato" }
if { [get_property PROGRESS [get_runs impl_1]] == "100%" } {
  open_run impl_1
  puts "TIMING_WNS: [get_property SLACK [lindex [get_timing_paths -max_paths 1 -nworst 1] 0]] ns"
  write_hw_platform -fixed -include_bit -force "$ROOT/snn_b2_donatello.xsa"
  puts "XSA_OK: $ROOT/snn_b2_donatello.xsa"
}
puts "DONE-BOARD"
