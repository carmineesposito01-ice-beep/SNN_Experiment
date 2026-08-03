# power_b2_saif.tcl — legge i SAIF (da funcsim sim) sul routed.dcp e produce report_power vettoriale.
# Riapre il checkpoint tra typical e worst per non contaminare l'attivita'.
# Radice del repository dalla POSIZIONE di questo script, mai cablata: cablarla farebbe
# leggere i sorgenti di un ALTRO albero (p.es. il worktree da cui e' nato il ramo) e
# attribuire i numeri al codice sbagliato, in silenzio.
set WT [file normalize [file join [file dirname [info script]] .. .. .. ..]]
if {![file isdirectory [file join $WT matlab]]} {
  puts "ABORT: radice ricavata $WT -- non contiene matlab/. Eseguire con 'source' dal repo."
  exit 1
}
set OUT "$WT/matlab/axi/build/phase_b"
foreach lab {typical worst} {
  open_checkpoint "D:/zbd_pb2/routed.dcp"
  read_saif "D:/zbd_pb2/b2_$lab.saif"
  report_power -file "$OUT/power_b2_$lab.rpt"
  close_design
}
puts "DONE-SAIF-POWER"
