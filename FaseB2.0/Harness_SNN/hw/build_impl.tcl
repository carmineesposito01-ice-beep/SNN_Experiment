# T6b · M2 — costruisce il sistema (PS7 + tier_axi_lite + SmartConnect) a un dato FCLK, implementa e riporta.
# Un'invocazione Vivado = UN punto di sweep (isolamento e determinismo; niente stato che si trascina).
# Uso: vivado -mode batch -source build_impl.tcl -tclargs <SRCDIR> <ROOT> <FCLK_MHz> <OUTDIR> [<JOBS>]
#   SRCDIR = cartella CORTA senza spazi coi .vhd + compile_order.txt + tier_axi_lite.v (COPIATI dal chiamante:
#            add_files ri-parsa la stringa come lista e un path con spazi si spezza).
set SRC   [lindex $argv 0]
set ROOT  [lindex $argv 1]
set FCLK  [lindex $argv 2]
set OUT   [lindex $argv 3]
set JOBS  [expr {[llength $argv] > 4 ? [lindex $argv 4] : 6}]   ;# FISSO -> risultati deterministici
set PART  xc7z020clg400-1

set_param board.repoPaths [list "C:/AMDDesignTools/Boards_Drivers"]   ;# senza questo la board PYNQ non si trova
file delete -force $ROOT
create_project sys $ROOT -part $PART -force
set bp [lindex [get_board_parts -quiet -filter {NAME =~ *pynq-z1*}] 0]
if {$bp ne ""} { set_property board_part $bp [current_project] }

foreach f [split [string trim [read [open "$SRC/compile_order.txt" r]]] "\n"] {
  add_files -norecurse [list "$SRC/[string trim $f]"]
}
add_files -norecurse [list "$SRC/tier_axi_lite.v"]
update_compile_order -fileset sources_1

# ---- block design ----
create_bd_design sys
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7]
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
  -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps
set_property -dict [list CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $FCLK CONFIG.PCW_USE_M_AXI_GP0 {1}] $ps
set fclk_set [get_property CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $ps]
create_bd_cell -type module -reference tier_axi_lite tier0
apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
  -config { Master {/ps7/M_AXI_GP0} Clk {Auto} } [get_bd_intf_pins tier0/S_AXI]
validate_bd_design
set wrp [make_wrapper -files [get_files sys.bd] -top -force]
add_files -norecurse $wrp
set_property top sys_wrapper [current_fileset]
update_compile_order -fileset sources_1
puts "BUILD FCLK richiesto=$FCLK impostato=$fclk_set"

# ---- synth + impl ----
launch_runs synth_1 -jobs $JOBS
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
  puts "SWEEP FCLK=$FCLK SYNTH-FALLITA"
  puts [get_property STATUS [get_runs synth_1]]
  exit 1
}
launch_runs impl_1 -jobs $JOBS
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
  puts "SWEEP FCLK=$FCLK IMPL-FALLITA"
  puts [get_property STATUS [get_runs impl_1]]
  exit 1
}
open_run impl_1

# ---- report ----
file mkdir $OUT
report_utilization -hierarchical -file "$OUT/util_hier_fclk${FCLK}.rpt"
report_utilization              -file "$OUT/util_flat_fclk${FCLK}.rpt"
report_timing_summary           -file "$OUT/timing_fclk${FCLK}.rpt"

set wns "NA"
catch { set wns [get_property SLACK [lindex [get_timing_paths -max_paths 1 -nworst 1 -setup] 0]] }
if {$wns eq "NA" || $wns eq ""} {
  # fallback: dal report testuale
  set fh [open "$OUT/timing_fclk${FCLK}.rpt" r]; set t [read $fh]; close $fh
  regexp {WNS\(ns\)\s*[^\n]*\n[-\s]*\n\s*(-?[\d.]+)} $t -> wns
}

# utilizzo dal TESTO del report (report_utilization -return_string ritorna una stringa, non un oggetto)
set rpt [report_utilization -return_string]
set lut NA; set ff NA; set dsp NA; set bram NA
foreach line [split $rpt "\n"] {
  if {[regexp {\|\s*Slice LUTs\*?\s*\|\s*(\d+)}      $line -> v]} { set lut  $v }
  if {[regexp {\|\s*Slice Registers\s*\|\s*(\d+)}    $line -> v]} { set ff   $v }
  if {[regexp {\|\s*DSPs\s*\|\s*(\d+)}               $line -> v]} { set dsp  $v }
  if {[regexp {\|\s*Block RAM Tile\s*\|\s*([\d.]+)}  $line -> v]} { set bram $v }
}
puts "SWEEP FCLK=$fclk_set WNS=$wns LUT=$lut FF=$ff DSP=$dsp BRAM=$bram"
puts "BUILD-OK"
