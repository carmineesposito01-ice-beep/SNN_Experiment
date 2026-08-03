# Sintesi OOC su xc7z020 del DUT indicato. Uso:
#   vivado -mode batch -source scripts/synth_acc_iidm.tcl -tclargs <srcdir> <outdir> <label>
#
# Registra LUT/FF/DSP/BRAM + WNS/Fmax + il PATH CRITICO. Non si ottimizza: si misura e si registra
# (baseline per lo sweep a slack minima, previsto ma non ora - spec SP3 §7).
# Clock 125 ns = 8 MHz: e' quello del bitstream della Fase B, cosi' i numeri sono confrontabili.
set srcdir [lindex $argv 0]
set outdir [lindex $argv 1]
set label  [lindex $argv 2]
file mkdir $outdir

create_project -in_memory -part xc7z020clg400-1
# RICORSIVO: makehdl annida i .vhd in una sottocartella col nome del modello (<srcdir>/g_*/...),
# quindi un glob piatto non trova nulla e synth_design fallisce con "No HDL sources found".
# DUT_pkg per primo: e' il package, le altre unita' lo usano.
set files [concat [glob -nocomplain $srcdir/*_pkg.vhd] [glob -nocomplain $srcdir/*/*_pkg.vhd] \
                  [glob -nocomplain $srcdir/*.vhd]     [glob -nocomplain $srcdir/*/*.vhd]]
set seen {}
foreach f $files {
  if {[lsearch -exact $seen $f] < 0} { lappend seen $f; read_vhdl $f }
}
if {[llength $seen] == 0} { error "nessun .vhd sotto $srcdir" }
puts "letti [llength $seen] file VHDL da $srcdir"
synth_design -top DUT -part xc7z020clg400-1 -mode out_of_context

# Il clock lo cerca fra le porte: HDL Coder lo chiama 'clk', ma non lo si assume.
set clkport [get_ports -quiet clk]
if {[llength $clkport] == 0} { set clkport [lindex [get_ports -quiet *clk*] 0] }
create_clock -name c -period 125.0 $clkport

report_utilization -file $outdir/util.rpt
report_timing_summary -file $outdir/timing.rpt
report_timing -max_paths 1 -nworst 1 -delay_type max -file $outdir/critpath.rpt

# Risorse dal report_utilization, NON da `get_cells -filter PRIMITIVE_GROUP==...`: quel filtro dava
# FF=0 e DSP=0 (valore/proprieta' sbagliati) e LUT sovrastimato (12076 vs 10846). Il report e' la
# fonte autorevole -- gli stessi numeri che report_utilization -file scrive su util.rpt.
proc rpt_val {txt name} {
  # riga: "| <name> | <int> | ..." -- prende la prima colonna dati (il totale "Used")
  if {[regexp "\\|\\s*${name}\\s*\\|\\s*(\[0-9.\]+)\\s*\\|" $txt -> v]} { return $v }
  return "NA"
}
set u [report_utilization -return_string]
set lut  [rpt_val $u {Slice LUTs\*?}]
set ff   [rpt_val $u {Slice Registers}]
set dsp  [rpt_val $u {DSPs}]
set bram [rpt_val $u {Block RAM Tile}]
set wns  [get_property SLACK [lindex [get_timing_paths -delay_type max -max_paths 1] 0]]
set fmax [expr {1000.0 / (125.0 - $wns)}]
puts "RESULT $label LUT=$lut FF=$ff DSP=$dsp BRAM=$bram WNS=$wns Fmax=$fmax"
# Il path critico in chiaro: se l'Fmax scende, serve sapere QUALE operazione lo domina (attesa: una
# divisione). E' un risultato da riportare, non un problema da inseguire in questo SP (spec §7).
set p [lindex [get_timing_paths -delay_type max -max_paths 1] 0]
puts "CRITPATH $label from=[get_property STARTPOINT_PIN $p] to=[get_property ENDPOINT_PIN $p] \
logic_levels=[get_property LOGIC_LEVELS $p] delay=[get_property DATAPATH_DELAY $p]"
