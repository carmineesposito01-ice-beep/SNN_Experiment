# Sonda risorse del plotone: quante istanze del composto entrano nello Zynq-7020, e a che
# prezzo se si forzano i moltiplicatori in fabric.
#
# tclargs: <src_dir> <work_dir> <N istanze> <max_dsp>
#
# ⚠️ Ogni istanza ha ingressi e uscite PROPRI, portati fuori dal top. N istanze con gli STESSI
# ingressi verrebbero fuse dal sintetizzatore in una sola, e la misura direbbe che il plotone
# e' quasi gratis. Il cancello a valle (LUT che scalano con N) serve a scoprirlo se accade.

set src     [lindex $argv 0]
set work    [lindex $argv 1]
set N       [lindex $argv 2]
set MAXDSP  [lindex $argv 3]

set PART   xc7z020clg400-1
set TOP    platoon_top

file mkdir $work
cd $work

# ---------------------------------------------------------------- top generato con N istanze
set fh [open "$work/${TOP}.v" w]
puts $fh "// GENERATO da probe_resources.tcl -- N=$N istanze di Donatello_SNN_IIDM"
puts $fh "module ${TOP} ("
puts $fh "  input wire clk, input wire reset, input wire clk_enable,"
for {set i 0} {$i < $N} {incr i} {
    puts $fh "  input  wire signed \[31:0\] s_$i, v_$i, dv_$i, vl_$i,"
    puts $fh "  output wire signed \[12:0\] accel_$i,"
    puts $fh "  output wire ce_out_$i[expr {$i == $N-1 ? "" : ","}]"
}
puts $fh ");"
for {set i 0} {$i < $N} {incr i} {
    puts $fh "  Donatello_SNN_IIDM u_$i (.clk(clk), .reset(reset), .clk_enable(clk_enable),"
    puts $fh "    .s(s_$i), .v(v_$i), .dv(dv_$i), .v_l(vl_$i),"
    puts $fh "    .accel(accel_$i), .ce_out(ce_out_$i));"
}
puts $fh "endmodule"
close $fh

# ---------------------------------------------------------------------------------- sorgenti
set order [open "$src/compile_order.txt" r]
foreach f [split [string trim [read $order]] "\n"] {
    set f [string trim $f]
    if {$f ne ""} { read_verilog "$src/$f" }
}
close $order
read_verilog "$work/${TOP}.v"

# ------------------------------------------------------------------------------------ sintesi
# -mode out_of_context: nessun buffer di I/O, si misura la logica e basta.
# -max_dsp: tetto ai DSP; sotto il tetto i moltiplicatori finiscono in LUT/FF.
set t0 [clock seconds]
synth_design -top $TOP -part $PART -mode out_of_context -max_dsp $MAXDSP
set dt [expr {[clock seconds] - $t0}]

# --------------------------------------------------------------------------------- risultati
proc used {name} {
    set r [report_utilization -return_string]
    foreach line [split $r "\n"] {
        if {[regexp "^\\|\\s+$name\\s+\\|\\s+(\\d+)\\s+\\|" $line -> n]} { return $n }
    }
    return -1
}

set lut  [used "Slice LUTs\\*?"]
set ff   [used "Slice Registers"]
set dsp  [used "DSPs"]
set bram [used "Block RAM Tile"]

# Limiti dello xc7z020clg400-1
set LUT_TOT 53200 ; set FF_TOT 106400 ; set DSP_TOT 220 ; set BRAM_TOT 140

set fits [expr {$lut <= $LUT_TOT && $ff <= $FF_TOT && $dsp <= $DSP_TOT}]
puts "PROBE N=$N max_dsp=$MAXDSP LUT=$lut FF=$ff DSP=$dsp BRAM=$bram FIT=[expr {$fits ? "si" : "no"}] SEC=$dt"

report_utilization -file "$work/util_N${N}_dsp${MAXDSP}.rpt"
