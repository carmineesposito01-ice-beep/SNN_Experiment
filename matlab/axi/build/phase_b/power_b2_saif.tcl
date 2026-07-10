# power_b2_saif.tcl — legge i SAIF (da funcsim sim) sul routed.dcp e produce report_power vettoriale.
# Riapre il checkpoint tra typical e worst per non contaminare l'attivita'.
set OUT "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/axi/build/phase_b"
foreach lab {typical worst} {
  open_checkpoint "D:/zbd_pb2/routed.dcp"
  read_saif "D:/zbd_pb2/b2_$lab.saif"
  report_power -file "$OUT/power_b2_$lab.rpt"
  close_design
}
puts "DONE-SAIF-POWER"
