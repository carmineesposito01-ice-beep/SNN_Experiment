# Synth-verify dell'IP AXI integrato (SNN B2 + decode + AXI4-Lite slave) - mixed VHDL/Verilog
set PART "xc7z020clg400-1"
set TOP  "snn_b2_axi_lite"
set SNN  "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/codegen/snn_top_b2/hdlsrc"
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
