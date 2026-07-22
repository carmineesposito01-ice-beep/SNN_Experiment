# Spettro dei path: quanto vale DAVVERO togliere un collo, PRIMA di spendere il refactor.
#   vivado -mode batch -source scripts/spectrum_iidm.tcl -tclargs <srcdir> <outdir> <regex-collo>
#
# Il punto: l'Fmax dopo un'ottimizzazione non e' "infinito", e' il SECONDO path. Se il secondo path
# e' subito sotto il primo, il refactor compra il 3% e non vale il rischio (qui: cambiare iidm_prep,
# che e' single-source col model -> obbliga a rifare G2 sui 60k).
#
# Si escludono i path che FINISCONO sul collo (quelli che l'ottimizzazione elimina) e si tengono
# quelli che ne PARTONO (che l'ottimizzazione non tocca): il peggiore dei rimanenti e' il tetto vero.
set srcdir [lindex $argv 0]
set outdir [lindex $argv 1]
set collo  [lindex $argv 2]
file mkdir $outdir

create_project -in_memory -part xc7z020clg400-1
set files [concat [glob -nocomplain $srcdir/*_pkg.vhd] [glob -nocomplain $srcdir/*/*_pkg.vhd] \
                  [glob -nocomplain $srcdir/*.vhd]     [glob -nocomplain $srcdir/*/*.vhd]]
set seen {}
foreach f $files { if {[lsearch -exact $seen $f] < 0} { lappend seen $f; read_vhdl $f } }
if {[llength $seen] == 0} { error "nessun .vhd sotto $srcdir" }
synth_design -top DUT -part xc7z020clg400-1 -mode out_of_context

set clkport [get_ports -quiet clk]
if {[llength $clkport] == 0} { set clkport [lindex [get_ports -quiet *clk*] 0] }
create_clock -name c -period 125.0 $clkport

# Il checkpoint si salva: cosi' la PROSSIMA analisi non richiede un'altra sintesi da 15 minuti.
write_checkpoint -force $outdir/post_synth.dcp

set paths [get_timing_paths -delay_type max -max_paths 400 -nworst 400]
puts "=== SPETTRO ($outdir): [llength $paths] path ==="
puts [format "%-8s %-58s %6s %9s %8s" "rank" "endpoint" "liv" "delay" "Fmax"]

set rank 0
set best_wo ""
foreach p $paths {
  incr rank
  set ep  [get_property ENDPOINT_PIN $p]
  set sp  [get_property STARTPOINT_PIN $p]
  set d   [get_property DATAPATH_DELAY $p]
  set lv  [get_property LOGIC_LEVELS $p]
  set slk [get_property SLACK $p]
  set fm  [expr {1000.0 / (125.0 - $slk)}]
  if {$rank <= 25} { puts [format "%-8d %-58s %6s %9.3f %8.2f" $rank $ep $lv $d $fm] }
  # primo path che NON finisce sul collo = il tetto dopo l'ottimizzazione
  if {$best_wo eq "" && ![regexp $collo $ep]} {
    set best_wo [list $ep $lv $d $fm]
  }
}
puts ""
puts "COLLO-ATTUALE  Fmax=[format %.3f [expr {1000.0/(125.0-[get_property SLACK [lindex $paths 0]])}]]  ep=[get_property ENDPOINT_PIN [lindex $paths 0]]"
if {$best_wo ne ""} {
  puts "TETTO-DOPO-R2  Fmax=[format %.3f [lindex $best_wo 3]]  ep=[lindex $best_wo 0]  liv=[lindex $best_wo 1]  delay=[lindex $best_wo 2]"
} else {
  puts "TETTO-DOPO-R2  (tutti i [llength $paths] path finiscono sul collo: il premio e' grande, rifare con piu' path)"
}
