# Sintesi OOC di un punto dello studio, con vincolo di clock OPZIONALE, e salvataggio del DCP.
#
#   vivado -mode batch -source scripts/synth_point.tcl -tclargs <srcdir> <outdir> <label> [periodo_ns]
#
# Differenze da synth_acc_iidm.tcl (che resta la fonte dei 17 numeri OOC storici):
#   1. SALVA il checkpoint post-sintesi -> l'implementazione non richiede di risintetizzare.
#      (synth_acc_iidm.tcl non lo faceva: esistono solo 3 DCP su 17 punti.)
#   2. Accetta un periodo: se dato, il clock e' definito via XDC PRIMA di synth_design, quindi la
#      sintesi e' timing-driven. Senza periodo il comportamento e' quello storico (sintesi LIBERA,
#      clock creato dopo) -- necessario per riprodurre i numeri gia' in RESULTS.txt.
#
# NB: il clock non si puo' creare con create_clock prima di synth_design, perche' le porte non
# esistono ancora come oggetti: va messo in un XDC, che Vivado applica dopo l'elaborazione.

set srcdir [lindex $argv 0]
set outdir [lindex $argv 1]
set label  [lindex $argv 2]
set PER    [lindex $argv 3]     ;# opzionale: vuoto = sintesi libera (comportamento storico)
set TOP    [lindex $argv 4]     ;# opzionale: default DUT
set SDIR   [lindex $argv 5]     ;# opzionale: -directive di synth_design (vuoto = default, comportamento storico)
if {$srcdir eq "" || $outdir eq "" || $label eq ""} {
  error "uso: -tclargs <srcdir> <outdir> <label> \[periodo_ns\] \[top\]"
}
# I punti IIDM hanno top `DUT` (modelli m_pipe_*); i punti Donatello hanno top `Donatello_LUT64`
# (rtl_gen_dut nomina il top come il blocco di libreria). Assumere DUT faceva fallire la sintesi con
# "ERROR: [Synth 8-439] module 'DUT' not found".
if {$TOP eq ""} { set TOP DUT }
file mkdir $outdir
set t0 [clock seconds]

create_project -in_memory -part xc7z020clg400-1
# RICORSIVO: makehdl annida i .vhd in una sottocartella col nome del modello. DUT_pkg per primo:
# e' il package, le altre unita' lo usano.
set files [concat [glob -nocomplain $srcdir/*_pkg.vhd] [glob -nocomplain $srcdir/*/*_pkg.vhd] \
                  [glob -nocomplain $srcdir/*.vhd]     [glob -nocomplain $srcdir/*/*.vhd]]
set seen {}
foreach f $files { if {[lsearch -exact $seen $f] < 0} { lappend seen $f; read_vhdl $f } }
if {[llength $seen] == 0} { error "nessun .vhd sotto $srcdir" }
puts "SYNTH: letti [llength $seen] file VHDL da $srcdir"

if {$PER ne ""} {
  set xdc $outdir/clk.xdc
  set fh [open $xdc w]
  puts $fh "create_clock -name c -period $PER \[get_ports clk\]"
  close $fh
  read_xdc $xdc
  puts "SYNTH: sintesi VINCOLATA a $PER ns (XDC letto prima di synth_design)"
} else {
  puts "SYNTH: sintesi LIBERA (nessun vincolo) - comportamento storico"
}

if {$SDIR ne ""} {
  puts "SYNTH: -directive $SDIR"
  synth_design -top $TOP -part xc7z020clg400-1 -mode out_of_context -directive $SDIR
} else {
  synth_design -top $TOP -part xc7z020clg400-1 -mode out_of_context
}

# se la sintesi era libera il clock si crea ora, per poter riportare il timing
if {[llength [get_clocks -quiet c]] == 0} {
  set cp [get_ports -quiet clk]
  if {[llength $cp] == 0} { set cp [lindex [get_ports -quiet *clk*] 0] }
  create_clock -name c -period 125.0 $cp
  set refPer 125.0
} else {
  set refPer [get_property PERIOD [get_clocks c]]
}

report_utilization    -file $outdir/util.rpt
report_timing_summary -file $outdir/timing.rpt
report_timing -max_paths 1 -nworst 1 -delay_type max -file $outdir/critpath.rpt

proc rpt_val {txt name} {
  # DOPPIO backslash: dentro "..." Tcl consuma il primo livello, quindi \\s arriva al regex come \s.
  if {[regexp "\\|\\s*${name}\\s*\\|\\s*(\[0-9.\]+)\\s*\\|" $txt -> v]} { return $v }
  return "NA"
}
set u [report_utilization -return_string]
set wns [get_property SLACK [lindex [get_timing_paths -delay_type max -max_paths 1] 0]]
set delay [expr {$refPer - $wns}]
puts "SYNTH-RESULT $label LUT=[rpt_val $u {Slice LUTs\*?}] FF=[rpt_val $u {Slice Registers}] DSP=[rpt_val $u {DSPs}] BRAM=[rpt_val $u {Block RAM Tile}] WNS=$wns delay=[format %.3f $delay] Fmax=[format %.3f [expr {1000.0/$delay}]]"
set p [lindex [get_timing_paths -delay_type max -max_paths 1] 0]
puts "SYNTH-CRITPATH $label from=[get_property STARTPOINT_PIN $p] to=[get_property ENDPOINT_PIN $p] liv=[get_property LOGIC_LEVELS $p] delay=[get_property DATAPATH_DELAY $p]"

write_checkpoint -force $outdir/post_synth.dcp
puts "SYNTH: DCP -> $outdir/post_synth.dcp   TOTALE [expr {[clock seconds]-$t0}] s"
