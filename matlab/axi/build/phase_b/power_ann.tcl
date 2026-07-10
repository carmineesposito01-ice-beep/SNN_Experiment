# power_ann.tcl — NON-PROJECT OOC ANN densa time-mux @8MHz (come B2, confronto E/inf equo).
# synth+util+impl+timing+vectorless power + funcsim.v + routed.dcp per il SAIF (step separato).
set ROOT "D:/zbd_ann"
file delete -force $ROOT
file mkdir $ROOT
set WT  "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
set ANN "$WT/matlab/codegen/ann_mlp/hdlsrc"
set AXI "$WT/matlab/axi"
set OUT "$WT/matlab/axi/build/phase_b"

read_vhdl -library work [list \
  "$ANN/ann_mlp_pkg.vhd" "$ANN/SimpleDualPortRAM_generic.vhd" "$ANN/ann_mlp_tc.vhd" \
  "$ANN/ann_mlp_enb_bypass.vhd" "$ANN/ann_mlp.vhd" "$AXI/ann_mlp_flat.vhd"]
synth_design -top ann_mlp_flat -part xc7z020clg400-1 -mode out_of_context -flatten_hierarchy none
report_utilization -file "$OUT/util_ann.rpt"
write_checkpoint -force "$ROOT/synth.dcp"
puts "SYNTH-UTIL-DONE"

create_clock -name clk -period 125.000 [get_ports clk]
opt_design
place_design
route_design
report_timing_summary -file "$OUT/timing_ann.rpt"
report_power -file "$OUT/power_ann_vectorless.rpt"
write_checkpoint -force "$ROOT/routed.dcp"
write_verilog -mode funcsim -force "$ROOT/funcsim.v"
puts "DONE-ANN-SYNTH"
