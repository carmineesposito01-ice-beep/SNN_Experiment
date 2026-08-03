# power_ann_saif.tcl — legge il SAIF ANN sul routed.dcp -> report_power vettoriale.
# Radice del repository dalla POSIZIONE di questo script, mai cablata: cablarla farebbe
# leggere i sorgenti di un ALTRO albero (p.es. il worktree da cui e' nato il ramo) e
# attribuire i numeri al codice sbagliato, in silenzio.
set WT [file normalize [file join [file dirname [info script]] .. .. .. ..]]
if {![file isdirectory [file join $WT matlab]]} {
  puts "ABORT: radice ricavata $WT -- non contiene matlab/. Eseguire con 'source' dal repo."
  exit 1
}
set OUT "$WT/matlab/axi/build/phase_b"
open_checkpoint "D:/zbd_ann/routed.dcp"
read_saif "D:/zbd_ann/ann.saif"
report_power -file "$OUT/power_ann.rpt"
close_design
puts "DONE-ANN-SAIF-POWER"
