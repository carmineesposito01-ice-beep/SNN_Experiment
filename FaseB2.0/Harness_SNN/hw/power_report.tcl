# T6b · M3 — da SAIF a potenza: apre il progetto OOC implementato e, per ogni .saif, produce report_power.
# UNA sola sessione Vivado per tutti i workload (l'impl NON si ripete: cambia solo l'attivita' di commutazione).
# ⚠️ reset_switching_activity -all fra un SAIF e il successivo: senza, l'attivita' precedente resta e i numeri
#    si mescolano (il secondo report sarebbe una sovrapposizione, non una misura).
# Uso: vivado -mode batch -source power_report.tcl -tclargs <XPR> <OUTDIR> <saif1> [<saif2> ...]
set XPR  [lindex $argv 0]
set OUT  [lindex $argv 1]
set SAIFS [lrange $argv 2 end]

open_project $XPR
open_run impl_1
file mkdir $OUT

puts "===== POWER REPORT ====="
foreach sf $SAIFS {
  set tag [file rootname [file tail $sf]]
  if {![file exists $sf]} { puts "PW $tag ASSENTE"; continue }
  reset_switching_activity -all
  if {[catch { read_saif $sf } msg]} { puts "PW $tag READ-SAIF-ERRORE: $msg"; continue }
  set rpt "$OUT/power_${tag}.rpt"
  report_power -file $rpt
  # estrazione dal TESTO del report (report_power -return_string ritorna una stringa, non un oggetto)
  set txt [report_power -return_string]
  set tot NA; set dyn NA; set sta NA; set conf NA
  foreach line [split $txt "\n"] {
    if {[regexp {Total On-Chip Power \(W\)\s*\|\s*([\d.]+)}   $line -> v]} { set tot $v }
    if {[regexp {Dynamic \(W\)\s*\|\s*([\d.]+)}               $line -> v]} { set dyn $v }
    if {[regexp {Device Static \(W\)\s*\|\s*([\d.]+)}         $line -> v]} { set sta $v }
    if {[regexp {Confidence Level\s*\|\s*(\w+)}               $line -> v]} { set conf $v }
  }
  puts "PW $tag  total=$tot  dynamic=$dyn  static=$sta  confidence=$conf"
}
puts "===== POWER REPORT FINE ====="
