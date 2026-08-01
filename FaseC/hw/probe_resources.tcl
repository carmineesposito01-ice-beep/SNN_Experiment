# Sonda risorse del plotone: quante istanze del composto entrano nello Zynq-7020, e a che
# prezzo se si forzano i moltiplicatori in fabric.
#
# tclargs: <src_dir> <work_dir> <N istanze> <max_dsp> [unita]
#
#   unita = dut      (default) solo Donatello_SNN_IIDM -- la logica di calcolo
#         = wrapper            snniidm_axi_lite, che CONTIENE il DUT: l'unita' deployabile,
#                              con i registri AXI e la macchina a stati che nel deployment
#                              reale ci sono e nel `dut` no.
#
# ⚠️ Ogni istanza ha ingressi e uscite PROPRI, portati fuori dal top. N istanze con gli STESSI
# ingressi verrebbero fuse dal sintetizzatore in una sola, e la misura direbbe che il plotone
# e' quasi gratis. Il cancello a valle (LUT che scalano con N) serve a scoprirlo se accade.

set src     [lindex $argv 0]
set work    [lindex $argv 1]
set N       [lindex $argv 2]
set MAXDSP  [lindex $argv 3]
set UNITA   [expr {[llength $argv] > 4 ? [lindex $argv 4] : "dut"}]

set PART   xc7z020clg400-1
set TOP    platoon_top

file mkdir $work
cd $work

# ---------------------------------------------------------------- top generato con N istanze
set fh [open "$work/${TOP}.v" w]
puts $fh "// GENERATO da probe_resources.tcl -- N=$N istanze, unita=$UNITA"

if {$UNITA eq "wrapper"} {
    # snniidm_axi_lite: slave AXI4-Lite che contiene il DUT. Ogni istanza ha il PROPRIO bus,
    # come avrebbe nel block design (N slave con N intervalli d'indirizzo distinti).
    puts $fh "module ${TOP} ("
    puts $fh "  input wire S_AXI_ACLK, input wire S_AXI_ARESETN,"
    for {set i 0} {$i < $N} {incr i} {
        set c [expr {$i == $N-1 ? "" : ","}]
        puts $fh "  input  wire \[5:0\] awaddr_$i,  input wire \[2:0\] awprot_$i, input wire awvalid_$i,"
        puts $fh "  output wire awready_$i,"
        puts $fh "  input  wire \[31:0\] wdata_$i, input wire \[3:0\] wstrb_$i, input wire wvalid_$i,"
        puts $fh "  output wire wready_$i, output wire \[1:0\] bresp_$i, output wire bvalid_$i,"
        puts $fh "  input  wire bready_$i,"
        puts $fh "  input  wire \[5:0\] araddr_$i,  input wire \[2:0\] arprot_$i, input wire arvalid_$i,"
        puts $fh "  output wire arready_$i,"
        puts $fh "  output wire \[31:0\] rdata_$i, output wire \[1:0\] rresp_$i, output wire rvalid_$i,"
        puts $fh "  input  wire rready_$i$c"
    }
    puts $fh ");"
    for {set i 0} {$i < $N} {incr i} {
        puts $fh "  snniidm_axi_lite u_$i (.S_AXI_ACLK(S_AXI_ACLK), .S_AXI_ARESETN(S_AXI_ARESETN),"
        puts $fh "    .S_AXI_AWADDR(awaddr_$i), .S_AXI_AWPROT(awprot_$i), .S_AXI_AWVALID(awvalid_$i),"
        puts $fh "    .S_AXI_AWREADY(awready_$i), .S_AXI_WDATA(wdata_$i), .S_AXI_WSTRB(wstrb_$i),"
        puts $fh "    .S_AXI_WVALID(wvalid_$i), .S_AXI_WREADY(wready_$i), .S_AXI_BRESP(bresp_$i),"
        puts $fh "    .S_AXI_BVALID(bvalid_$i), .S_AXI_BREADY(bready_$i), .S_AXI_ARADDR(araddr_$i),"
        puts $fh "    .S_AXI_ARPROT(arprot_$i), .S_AXI_ARVALID(arvalid_$i), .S_AXI_ARREADY(arready_$i),"
        puts $fh "    .S_AXI_RDATA(rdata_$i), .S_AXI_RRESP(rresp_$i), .S_AXI_RVALID(rvalid_$i),"
        puts $fh "    .S_AXI_RREADY(rready_$i));"
    }
    puts $fh "endmodule"
} else {
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
}
close $fh

# ---------------------------------------------------------------------------------- sorgenti
set order [open "$src/compile_order.txt" r]
foreach f [split [string trim [read $order]] "\n"] {
    set f [string trim $f]
    if {$f ne ""} { read_verilog "$src/$f" }
}
close $order
if {$UNITA eq "wrapper"} {
    if {![file exists $::env(WRAPPER_V)]} {
        puts "PROBE-ABORT: wrapper non trovato: $::env(WRAPPER_V)"
        exit 1
    }
    # [list ...]: senza, un percorso CON SPAZI viene inteso da read_verilog come piu' file
    # ("D:/Project_MBSE/1.Reti" + "Neurali/...") e la sintesi fallisce.
    read_verilog [list $::env(WRAPPER_V)]
}
read_verilog "$work/${TOP}.v"

# ------------------------------------------------------------------------------------ sintesi
# -mode out_of_context: nessun buffer di I/O, si misura la logica e basta.
# -max_dsp: tetto ai DSP; sotto il tetto i moltiplicatori finiscono in LUT/FF.
set t0 [clock seconds]
synth_design -top $TOP -part $PART -mode out_of_context -max_dsp $MAXDSP

# --------------------------------------------------------------------------- implementazione
# FASE=impl: place & route VERI, con vincolo di clock. La sintesi da sola dice quante LUT
# servono, NON se il progetto si instrada. Al 94% di occupazione l'instradabilita' e' il
# rischio vero -- piu' dell'Fmax, che qui non e' il vincolo (il requisito e' il control-step da
# 0,1 s: 555 clock a 40 MHz sono 13,9 us, margine 7207x).
set FASE [expr {[info exists ::env(PROBE_FASE)] ? $::env(PROBE_FASE) : "synth"}]
set PER  [expr {[info exists ::env(PROBE_PERIOD_NS)] ? $::env(PROBE_PERIOD_NS) : 25.0}]
set wns "n/a" ; set routed "n/a"

if {$FASE eq "impl"} {
    set clkport [expr {$UNITA eq "wrapper" ? "S_AXI_ACLK" : "clk"}]
    create_clock -period $PER -name clk_probe [get_ports $clkport]
    if {[catch {
        opt_design
        place_design
        route_design
    } err]} {
        puts "PROBE-IMPL-FALLITA unita=$UNITA N=$N: $err"
        set routed "no"
    } else {
        set routed "si"
        set wns [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
    }
}
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
puts "PROBE unita=$UNITA N=$N max_dsp=$MAXDSP LUT=$lut FF=$ff DSP=$dsp BRAM=$bram FIT=[expr {$fits ? "si" : "no"}] FASE=$FASE ROUTED=$routed WNS=$wns SEC=$dt"

report_utilization -file "$work/util_${UNITA}_N${N}_dsp${MAXDSP}.rpt"
