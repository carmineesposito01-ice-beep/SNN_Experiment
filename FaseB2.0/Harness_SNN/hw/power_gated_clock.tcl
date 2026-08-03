# T6b · M3 — quantificare il guadagno del CLOCK GATING nonostante il limite di report_power.
#
# FATTO MISURATO (dai SAIF, non ipotesi): in idle il clock del Tier e' COMPLETAMENTE FERMO quando il gating
#   e' attivo -> saif_idle_g1: clk_tier (T0 tutta la finestra) (T1 0) (TC 0)
#   contro     saif_idle_g0: clk_tier (T0 meta') (T1 meta')   (TC 400)
# LIMITE DELLO STRUMENTO: report_power calcola la potenza dei net di CLOCK dal VINCOLO di frequenza, non
#   dall'attivita' del SAIF -> i due report risultano identici (0,007 W di "Clocks" in entrambi).
# QUI: si inietta esplicitamente nel modello l'attivita' nulla del clock gatato, cosi' il numero esce dal tool
#   invece di essere stimato a mano. Se la via non e' supportata, si ricade sulla stima dichiarata come tale.
#
# Uso: vivado -mode batch -source power_gated_clock.tcl -tclargs <XPR> <OUTDIR> <saif_idle_gatata>
set XPR  [lindex $argv 0]
set OUT  [lindex $argv 1]
set SAIF [lindex $argv 2]

open_project $XPR
open_run impl_1

puts "===== GATED-CLOCK POWER ====="
# 1) quali net di clock esistono e quanto pesano
set cnets [get_nets -quiet -hierarchical -filter {TYPE == CLOCK}]
puts "GC net di clock trovati: [llength $cnets]"
foreach n $cnets { puts "GC   $n" }

# 2) baseline: SAIF idle gatata (report_power non vede il gating)
reset_switching_activity -all
read_saif $SAIF
set txt [report_power -return_string]
foreach line [split $txt "\n"] {
  if {[regexp {Dynamic \(W\)\s*\|\s*([\d.]+)} $line -> v]}       { puts "GC baseline dynamic = $v" }
  if {[regexp {\|\s*Clocks\s*\|\s*([\d.<]+)} $line -> v]}        { puts "GC baseline clocks  = $v" }
}

# 3) inietta attivita' NULLA sul clock del Tier (il fatto misurato: TC=0)
set tnet [get_nets -quiet -hierarchical *clk_tier*]
puts "GC net del clock gatato: '[join $tnet {, }]'"
if {[llength $tnet] > 0} {
  if {[catch { set_switching_activity -toggle_rate 0 -static_probability 0 $tnet } m]} {
    puts "GC set_switching_activity FALLITA: $m"
  } else {
    set txt2 [report_power -return_string]
    report_power -file "$OUT/power_idle_gated_injected.rpt"
    foreach line [split $txt2 "\n"] {
      if {[regexp {Dynamic \(W\)\s*\|\s*([\d.]+)} $line -> v]}   { puts "GC con-gating dynamic = $v" }
      if {[regexp {\|\s*Clocks\s*\|\s*([\d.<]+)} $line -> v]}    { puts "GC con-gating clocks  = $v" }
    }
  }
} else {
  puts "GC net clk_tier NON trovato per nome: il gating va quantificato per stima dichiarata"
}
puts "===== GATED-CLOCK POWER FINE ====="
