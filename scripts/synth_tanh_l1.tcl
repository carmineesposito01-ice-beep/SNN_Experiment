# synth L1 del DUT tanh-solo (I/O registrato). Uso:
#   vivado -mode batch -source synth_tanh_l1.tcl -tclargs <srcdir> <outdir> <label>
# Riporta il critpath registrato (ddl_reg -> tanh -> thl_reg) = Fmax intrinseco della variante.
set srcdir [lindex $argv 0]; set outdir [lindex $argv 1]; set label [lindex $argv 2]
file mkdir $outdir
create_project -in_memory -part xc7z020clg400-1
set files [concat [glob -nocomplain $srcdir/*_pkg.vhd] [glob -nocomplain $srcdir/*.vhd]]
foreach f $files { read_vhdl $f }
if {[llength $files] == 0} { error "nessun .vhd sotto $srcdir" }
synth_design -top DUT -part xc7z020clg400-1 -mode out_of_context
set clkport [get_ports -quiet clk]
if {[llength $clkport] == 0} { set clkport [lindex [get_ports -quiet *clk*] 0] }
create_clock -name c -period 125.0 $clkport
set u [report_utilization -return_string]
proc rpt_val {txt name} { if {[regexp "\\|\\s*${name}\\s*\\|\\s*(\[0-9.\]+)\\s*\\|" $txt -> v]} { return $v }; return "NA" }
set lut [rpt_val $u {Slice LUTs\*?}]; set ff [rpt_val $u {Slice Registers}]
set dsp [rpt_val $u {DSPs}]; set bram [rpt_val $u {Block RAM Tile}]
set wns [get_property SLACK [lindex [get_timing_paths -delay_type max -max_paths 1] 0]]
set fmax [expr {1000.0 / (125.0 - $wns)}]
puts "RESULT $label LUT=$lut FF=$ff DSP=$dsp BRAM=$bram WNS=$wns Fmax=$fmax"
set p [lindex [get_timing_paths -delay_type max -max_paths 1] 0]
puts "CRITPATH $label from=[get_property STARTPOINT_PIN $p] to=[get_property ENDPOINT_PIN $p] logic_levels=[get_property LOGIC_LEVELS $p] delay=[get_property DATAPATH_DELAY $p]"
