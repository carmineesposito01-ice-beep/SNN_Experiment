# power_micro_saif.tcl — legge i SAIF dei micro sul rispettivo routed.dcp -> report_power vettoriale.
# Radice del repository dalla POSIZIONE di questo script, mai cablata: cablarla farebbe
# leggere i sorgenti di un ALTRO albero (p.es. il worktree da cui e' nato il ramo) e
# attribuire i numeri al codice sbagliato, in silenzio.
set WT [file normalize [file join [file dirname [info script]] .. .. .. ..]]
if {![file isdirectory [file join $WT matlab]]} {
  puts "ABORT: radice ricavata $WT -- non contiene matlab/. Eseguire con 'source' dal repo."
  exit 1
}
set OUT "$WT/matlab/axi/build/phase_b"
foreach name {micro_ac micro_mac} {
  open_checkpoint "D:/zbd_$name/routed.dcp"
  read_saif "D:/zbd_$name/$name.saif"
  report_power -file "$OUT/power_$name.rpt"
  close_design
}
puts "DONE-MICRO-SAIF-POWER"
