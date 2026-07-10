# power_micro.tcl — NON-PROJECT OOC per micro_ac e micro_mac @100MHz. Synth+impl+vectorless power +
# funcsim.v + routed.dcp per il SAIF (step separato). OOC = niente I/O pad -> potenza pura logica/DSP.
set WT  "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
set OUT "$WT/matlab/axi/build/phase_b"

proc do_micro {name WT OUT} {
  set ROOT "D:/zbd_$name"
  file delete -force $ROOT
  file mkdir $ROOT
  read_vhdl -library work [glob "$WT/matlab/codegen/$name/hdlsrc/*.vhd"]
  synth_design -top $name -part xc7z020clg400-1 -mode out_of_context
  report_utilization -file "$OUT/util_$name.rpt"
  create_clock -name clk -period 10.000 [get_ports clk]
  opt_design
  place_design
  route_design
  report_timing_summary -file "$OUT/timing_$name.rpt"
  report_power -file "$OUT/power_${name}_vectorless.rpt"
  write_checkpoint -force "$ROOT/routed.dcp"
  write_verilog -mode funcsim -force "$ROOT/funcsim.v"
  close_design
  puts "MICRO-$name-DONE"
}
do_micro micro_ac  $WT $OUT
do_micro micro_mac $WT $OUT
puts "DONE-MICRO-SYNTH"
