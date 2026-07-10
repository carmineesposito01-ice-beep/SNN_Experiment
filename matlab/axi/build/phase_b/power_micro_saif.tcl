# power_micro_saif.tcl — legge i SAIF dei micro sul rispettivo routed.dcp -> report_power vettoriale.
set OUT "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/axi/build/phase_b"
foreach name {micro_ac micro_mac} {
  open_checkpoint "D:/zbd_$name/routed.dcp"
  read_saif "D:/zbd_$name/$name.saif"
  report_power -file "$OUT/power_$name.rpt"
  close_design
}
puts "DONE-MICRO-SAIF-POWER"
