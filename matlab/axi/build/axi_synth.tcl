# Synth-verify dell'IP AXI integrato (SNN B2 + decode + AXI4-Lite slave) - mixed VHDL/Verilog
set PART "xc7z020clg400-1"
set TOP  "snn_b2_axi_lite"
# Radice del repository dalla POSIZIONE di questo script, mai cablata: cablarla farebbe
# leggere i sorgenti di un ALTRO albero (p.es. il worktree da cui e' nato il ramo) e
# attribuire i numeri al codice sbagliato, in silenzio.
set WT [file normalize [file join [file dirname [info script]] .. .. ..]]
if {![file isdirectory [file join $WT matlab]]} {
  puts "ABORT: radice ricavata $WT -- non contiene matlab/. Eseguire con 'source' dal repo."
  exit 1
}
set SNN  "$WT/matlab/codegen/snn_top_b2/hdlsrc"
set AXI  "C:/Users/USERPO~1/AppData/Local/Temp/claude/D--Project-MBSE-0-Documenti-Platooning-Focus-Traffic-Flow-2025/63719052-fc3e-48ab-9cdd-20922bd2deb6/scratchpad/axi_ip/snn_b2_axi_1_0/hdl"
set SP   "C:/Users/USERPO~1/AppData/Local/Temp/claude/D--Project-MBSE-0-Documenti-Platooning-Focus-Traffic-Flow-2025/63719052-fc3e-48ab-9cdd-20922bd2deb6/scratchpad"
set OUT  "$SP/axi_synth_out"
file mkdir $OUT
read_vhdl [list "$SNN/snn_top_b2_pkg.vhd"]
read_vhdl [list "$SNN/DualPortRAM_generic.vhd"]
read_vhdl [list "$SNN/snn_top_b2.vhd"]
read_vhdl [list "$AXI/snn_top_b2_flat.vhd"]
read_verilog [list "$AXI/snn_b2_axi_lite.v"]
synth_design -top $TOP -part $PART -mode out_of_context
catch { create_clock -name clk -period 20.000 [get_ports S_AXI_ACLK] }
report_utilization -file "$OUT/util.rpt"
set nDSP  [llength [get_cells -hier -filter {REF_NAME =~ DSP48*}]]
set nLUT  [llength [get_cells -hier -filter {REF_NAME =~ LUT*}]]
set nFF   [llength [get_cells -hier -filter {REF_NAME =~ FD*}]]
set nB18  [llength [get_cells -hier -filter {REF_NAME =~ RAMB18*}]]
set nB36  [llength [get_cells -hier -filter {REF_NAME =~ RAMB36*}]]
puts "======================================================"
puts "KEYAXI DSP=$nDSP LUT=$nLUT FF=$nFF BRAM18=$nB18 BRAM36=$nB36"
puts "======================================================"
