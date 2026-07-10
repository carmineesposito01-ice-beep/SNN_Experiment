# power_ann_saif.tcl — legge il SAIF ANN sul routed.dcp -> report_power vettoriale.
set OUT "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/axi/build/phase_b"
open_checkpoint "D:/zbd_ann/routed.dcp"
read_saif "D:/zbd_ann/ann.saif"
report_power -file "$OUT/power_ann.rpt"
close_design
puts "DONE-ANN-SAIF-POWER"
