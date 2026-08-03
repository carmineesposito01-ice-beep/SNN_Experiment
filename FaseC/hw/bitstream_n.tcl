# Fase C -- bitstream a N istanze per la misura differenziale di potenza (C3).
#
# Deriva da FaseB2.0/Harness_SNN_IIDM/hw/bitstream.tcl (T7b), che produce il sistema a UNA
# istanza. Qui la stessa procedura e' parametrica in N, perche' il differenziale ha bisogno di
# piu' configurazioni dello STESSO sistema:
#
#   N=0  `blank`  PS7 e basta, nessuna logica nel PL.  (b)-(a) isola il contributo del PL.
#   N=1  `x1`     una istanza -- deve RIPRODURRE il bitstream di T7b (cancello di taratura).
#   N=3  `x3`     tre istanze -- amplifica il segnale del clock gating.
#
# ⚠️ Perche' N=3 serve, e a cosa NON serve. Il guadagno del clock gating vale ~7 mW: a 5 V sono
# 1,4 mA, cioe' ~14 conteggi su un multimetro da 9999 -- troppo pochi perche' la misura sia
# credibile. Con tre istanze diventano ~42. Il PL intero (114 mW ~ 23 mA ~ 228 conteggi) si
# misurerebbe benissimo anche senza replicare: e' SOLO la parte del gating ad averne bisogno.
#
# ⚠️ Il gating NON e' un bitstream diverso: e' `slv_reg4[1]`, un bit di registro. Le due
# configurazioni girano sullo STESSO bitstream, stesso stato della scheda, e fra loro non cambia
# niente altro. E' cio' che rende quella differenza pulita.
#
# ⚠️ Il `blank` deve essere lo stesso sistema MENO la logica, non "un progetto vuoto": stessa
# board, stesso preset, stessa FCLK. Se cambiasse anche la configurazione del PS7, la differenza
# (b)-(a) non isolerebbe piu' il PL -- conterrebbe anche quella.
#
# Uso: vivado -mode batch -source bitstream_n.tcl -tclargs <SRC> <ROOT> <FCLK> <OUT> <N> <NOME> [JOBS]

set SRC  [lindex $argv 0]
set ROOT [lindex $argv 1]
set FCLK [lindex $argv 2]
set OUT  [lindex $argv 3]
set N    [lindex $argv 4]
set NOME [lindex $argv 5]
set JOBS [expr {[llength $argv] > 6 ? [lindex $argv 6] : 6}]
set PART xc7z020clg400-1

set_param board.repoPaths [list "C:/AMDDesignTools/Boards_Drivers"]
file delete -force $ROOT
create_project sysbit $ROOT -part $PART -force
set bp [lindex [get_board_parts -quiet -filter {NAME =~ *pynq-z1*}] 0]
if {$bp eq ""} { puts "BITN ERRORE: board PYNQ-Z1 non trovata"; exit 1 }
set_property board_part $bp [current_project]
puts "BITN board_part: $bp   N=$N   nome=$NOME"

# I sorgenti si caricano anche per N=0: costano nulla se nessuno li istanzia, e tenere UNA sola
# strada di caricamento evita che il `blank` diverga dagli altri per un motivo accidentale.
foreach f [split [string trim [read [open "$SRC/compile_order.txt" r]]] "\n"] {
  add_files -norecurse [list "$SRC/[string trim $f]"]
}
add_files -norecurse [list "$::env(WRAPPER_V)"]
update_compile_order -fileset sources_1

create_bd_design sys
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7]
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
  -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps

# M_AXI_GP0 resta ABILITATO anche nel blank: e' parte della configurazione del PS7, e spegnerlo
# renderebbe il blank un sistema diverso invece dello stesso senza la logica.
set_property -dict [list CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $FCLK CONFIG.PCW_USE_M_AXI_GP0 {1}] $ps
puts "BITN FCLK impostato: [get_property CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $ps] MHz"

for {set i 0} {$i < $N} {incr i} {
  create_bd_cell -type module -reference snniidm_axi_lite tier$i
  apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
    -config { Master {/ps7/M_AXI_GP0} Clk {Auto} } [get_bd_intf_pins tier$i/S_AXI]
  puts "BITN istanza tier$i collegata"
}

validate_bd_design
set wrp [make_wrapper -files [get_files sys.bd] -top -force]
add_files -norecurse $wrp
set_property top sys_wrapper [current_fileset]
update_compile_order -fileset sources_1

launch_runs synth_1 -jobs $JOBS
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} { puts "BITN SYNTH-FALLITA"; exit 1 }
launch_runs impl_1 -to_step write_bitstream -jobs $JOBS
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
  puts "BITN IMPL/BITSTREAM-FALLITO: [get_property STATUS [get_runs impl_1]]"; exit 1
}
open_run impl_1

# Cancello TIMING: un bitstream che non chiude i tempi non e' deployabile.
set wns "NA"
catch { set wns [get_property SLACK [lindex [get_timing_paths -max_paths 1 -nworst 1 -setup] 0]] }

proc used {name} {
  set r [report_utilization -return_string]
  foreach line [split $r "\n"] {
    if {[regexp "^\\|\\s+$name\\s+\\|\\s+(\\d+)\\s+\\|" $line -> n]} { return $n }
  }
  return -1
}
set lut [used "Slice LUTs\\*?"] ; set ff [used "Slice Registers"]
set dsp [used "DSPs"]           ; set bram [used "Block RAM Tile"]

file mkdir $OUT
report_timing_summary -file "$OUT/timing_${NOME}.rpt"
report_utilization    -file "$OUT/util_${NOME}.rpt"

set bit [glob -nocomplain "$ROOT/sysbit.runs/impl_1/*.bit"]
if {[llength $bit] == 0} { puts "BITN ERRORE: nessun .bit prodotto"; exit 1 }
file copy -force [lindex $bit 0] "$OUT/${NOME}.bit"
set hwh [glob -nocomplain "$ROOT/sysbit.gen/sources_1/bd/sys/hw_handoff/*.hwh"]
if {[llength $hwh] == 0} { set hwh [glob -nocomplain "$ROOT/sysbit.srcs/sources_1/bd/sys/hw_handoff/*.hwh"] }
if {[llength $hwh] > 0} {
  file copy -force [lindex $hwh 0] "$OUT/${NOME}.hwh"
} else { puts "BITN ATTENZIONE: .hwh non trovato -- PYNQ ne ha BISOGNO per la mappa indirizzi" }

puts "BITN nome=$NOME N=$N FCLK=$FCLK LUT=$lut FF=$ff DSP=$dsp BRAM=$bram WNS=$wns"
puts "BITN-DONE"
