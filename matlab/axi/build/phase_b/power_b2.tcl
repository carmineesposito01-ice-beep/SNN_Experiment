# power_b2.tcl — NON-PROJECT: synth OOC (no I/O buffer) di snn_top_b2_flat @8MHz, utilization
# gerarchica (attribuzione DSP), impl, timing, report_power vectorless. Scrive funcsim.v + routed.dcp
# per il SAIF (step separato power_b2_saif.tcl). OOC = anche giusto per la potenza (no anello I/O).
set ROOT "D:/zbd_pb2"
file delete -force $ROOT
file mkdir $ROOT
set WT  "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
set SNN "$WT/matlab/codegen/snn_top_b2/hdlsrc"
set AXI "$WT/matlab/axi"
set OUT "$WT/matlab/axi/build/phase_b"
set part xc7z020clg400-1

read_vhdl -library work [list "$SNN/snn_top_b2_pkg.vhd" "$SNN/DualPortRAM_generic.vhd" "$SNN/snn_top_b2.vhd" "$AXI/snn_top_b2_flat.vhd"]
synth_design -top snn_top_b2_flat -part $part -mode out_of_context -flatten_hierarchy none
report_utilization -hierarchical -file "$OUT/util_b2_hier.rpt"
report_utilization -file "$OUT/util_b2_flat.rpt"
write_checkpoint -force "$ROOT/synth.dcp"
puts "SYNTH-UTIL-DONE"

create_clock -name clk -period 125.000 [get_ports clk]
opt_design
place_design
route_design
report_timing_summary -file "$OUT/timing_b2.rpt"
report_power -file "$OUT/power_b2_vectorless.rpt"
write_checkpoint -force "$ROOT/routed.dcp"
write_verilog -mode funcsim -force "$ROOT/funcsim.v"
puts "IMPL-TIMING-POWER-DONE"
puts "DONE-POWER-B2-CORE"
