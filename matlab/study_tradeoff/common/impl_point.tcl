# Porta un punto dello studio da post-sintesi a POST-ROUTE con un vincolo di clock DICHIARATO,
# e ne riporta il ritardo raggiungibile con un flag di validita'.
#
#   vivado -mode batch -source scripts/impl_point.tcl -tclargs <dcp> <periodo_ns> <outdir>
#
# ============================================================================================
# PERCHE' IL VINCOLO E' IL PARAMETRO PIU' IMPORTANTE (misurato su R17, audit 2026-07-20)
#
#   vincolo 125.000 ns -> WNS +103.910 -> 21.090 ns -> 47.416 MHz  LUT  n/d   (nessuno sforzo)
#   vincolo  14.000 ns -> WNS   +0.269 -> 13.731 ns -> 72.828 MHz  LUT 7950   (limite INFERIORE)
#   vincolo  12.831 ns -> WNS   -0.055 -> 12.886 ns -> 77.604 MHz  LUT 7991   (VALIDA, la MIGLIORE)
#   vincolo  11.000 ns -> WNS   -2.346 -> 13.346 ns -> 74.929 MHz  LUT 8189   (SOVRA-VINCOLATA)
#
# Stesso netlist, quattro risposte. Placer e router ottimizzano i path con slack negativo o vicino a
# zero: con 103 ns di margine non hanno alcuna pressione e si fermano appena soddisfatto il vincolo.
# -> Un'Fmax post-route misurata con vincolo lasco NON e' una proprieta' del design.
# -> Anche le RISORSE dipendono dal vincolo (7950/7991/8189/8387 LUT sullo stesso netlist): i punti
#    vanno confrontati solo se misurati con lo STESSO protocollo.
#
# ⚠️ SOVRA-VINCOLARE PEGGIORA: chiedere 11 ns invece dei 12.831 raggiungibili ha dato un risultato
#    PEGGIORE (-3.6% Fmax, +2.5% LUT). Con un vincolo irraggiungibile il tool disperde lo sforzo su
#    troppi path falliti. -> "sovra-vincola e leggi periodo-WNS" NON e' sicuro.
#
# COME SI SCEGLIE IL PERIODO: si usa il ritardo stimato dalla sintesi OOC di QUEL punto (delay_OOC =
# 125 - WNS_OOC). La stima OOC e' molto vicina al vero, quindi lo slack atterra leggermente negativo
# senza sovra-vincolare. VERIFICATO su R17: vincolo 12.831 -> WNS -0.055, valido al primo colpo.
#
# ⚠️ COSA MISURA: implementazione OOC senza HD.PARTPIN_LOCS -> Vivado avverte che il timing DA/VERSO
#    LE PORTE non e' accurato (WARNING Route 35-198). Il numero e' il tetto INTERNO reg-reg del
#    blocco, buono per CONFRONTARE configurazioni; il timing d'integrazione si misura col wrapper.
#
# REGOLA DI VALIDITA': (periodo - WNS) e' il ritardo raggiungibile SOLO se WNS <= 0, cioe' se il tool
# ha spinto al massimo. Con WNS > 0 il valore e' un LIMITE INFERIORE: si stringe e si rifa. Lo script
# lo DICHIARA invece di lasciarlo dedurre a chi legge la tabella dopo sei mesi.
#
# NB: report_qor_assessment NON e' utilizzabile qui: richiede licenza > BASIC (ERROR Implflow 47-2944).
# ============================================================================================

set dcp    [lindex $argv 0]
set PER    [lindex $argv 1]
set outdir [lindex $argv 2]
set PROF   [lindex $argv 3]   ;# opzionale: "" (default storico) | "area" (ExploreArea) | "perf" (Explore + phys_opt)
set IODELAY [lindex $argv 4]  ;# opzionale: "io" -> set_input/output_delay 0 (tima anche i path DA/VERSO le porte)
if {$dcp eq "" || $PER eq "" || $outdir eq ""} {
  error "uso: -tclargs <dcp> <periodo_ns> <outdir>"
}
file mkdir $outdir

set t0 [clock seconds]
open_checkpoint $dcp

set cp [get_ports -quiet clk]
if {[llength $cp] == 0} { set cp [lindex [get_ports -quiet *clk*] 0] }
if {[llength $cp] == 0} { error "nessuna porta di clock trovata in $dcp" }
# in Vivado non esiste remove_clock (e' di un altro tool): create_clock con lo stesso nome RIDEFINISCE
create_clock -name c -period $PER $cp
# il periodo in vigore si RILEGGE, non si assume: altrimenti si misura un'altra cosa senza accorgersene
set perEff [get_property PERIOD [get_clocks c]]
if {abs($perEff - $PER) > 0.001} { error "clock non ridefinito: in vigore $perEff, atteso $PER" }
if {$IODELAY ne ""} {
  # tima i percorsi DA/VERSO le porte (input->reg, reg->output): in OOC senza questo le porte NON sono
  # timate e il percorso ingresso->normalize->go resta INVISIBILE. 0 ns = ingresso stabile al bordo del clock.
  set_input_delay  -clock c 0.000 [all_inputs]
  set_output_delay -clock c 0.000 [all_outputs]
  puts "IMPL-IODELAY: set_input/output_delay 0 su tutte le porte (percorsi I/O timati)"
}
puts "IMPL: dcp=$dcp vincolo=$perEff ns ([format %.2f [expr {1000.0/$perEff}]] MHz)"

# PROFILO opzionale: "" = default storico (invariato); "area" = opt ExploreArea; "perf" = Explore + phys_opt.
if {$PROF eq "area"} {
  set t1 [clock seconds] ; opt_design -directive ExploreArea ; set t_opt   [expr {[clock seconds]-$t1}]
  set t1 [clock seconds] ; place_design                      ; set t_place [expr {[clock seconds]-$t1}]
  set t1 [clock seconds] ; route_design                      ; set t_route [expr {[clock seconds]-$t1}]
  puts "IMPL-PROFILO: area (opt_design -directive ExploreArea)"
} elseif {$PROF eq "perf"} {
  set t1 [clock seconds] ; opt_design   -directive Explore   ; set t_opt   [expr {[clock seconds]-$t1}]
  set t1 [clock seconds] ; place_design -directive Explore   ; set t_place [expr {[clock seconds]-$t1}]
  phys_opt_design
  set t1 [clock seconds] ; route_design -directive Explore   ; set t_route [expr {[clock seconds]-$t1}]
  phys_opt_design
  puts "IMPL-PROFILO: perf (Explore + phys_opt_design post-place e post-route)"
} else {
  set t1 [clock seconds] ; opt_design   ; set t_opt   [expr {[clock seconds]-$t1}]
  set t1 [clock seconds] ; place_design ; set t_place [expr {[clock seconds]-$t1}]
  set t1 [clock seconds] ; route_design ; set t_route [expr {[clock seconds]-$t1}]
}
puts "IMPL-TEMPI opt=$t_opt place=$t_place route=$t_route s"

set ps [lindex [get_timing_paths -delay_type max -max_paths 1] 0]
set ph [lindex [get_timing_paths -delay_type min -max_paths 1] 0]
set wns [get_property SLACK $ps]
set whs [get_property SLACK $ph]
set ach [expr {$PER - $wns}]
puts "IMPL: WNS=$wns WHS=$whs"
puts "IMPL: ritardo=[format %.3f $ach] ns  Fmax=[format %.3f [expr {1000.0/$ach}]] MHz"
if {$wns > 0} {
  puts "IMPL-VALIDITA' LIMITE-INFERIORE: WNS positivo -> il tool si e' FERMATO al vincolo. Stringere."
} else {
  puts "IMPL-VALIDITA' VALIDA: WNS negativo -> massimo sforzo, il ritardo e' quello raggiungibile."
}
# hold: senza WHS positivo il design non e' valido a questo vincolo, per quanto buono sia il setup
if {$whs < 0} {
  puts "IMPL-HOLD ⚠️ WHS NEGATIVO ($whs): design NON valido a questo vincolo."
} else {
  puts "IMPL-HOLD ok ($whs)"
}
puts "IMPL-CRITPATH-SETUP from=[get_property STARTPOINT_PIN $ps] to=[get_property ENDPOINT_PIN $ps] liv=[get_property LOGIC_LEVELS $ps] delay=[get_property DATAPATH_DELAY $ps]"
puts "IMPL-CRITPATH-HOLD  from=[get_property STARTPOINT_PIN $ph] to=[get_property ENDPOINT_PIN $ph] liv=[get_property LOGIC_LEVELS $ph] delay=[get_property DATAPATH_DELAY $ph]"

report_utilization      -file $outdir/util_routed.rpt
report_timing_summary   -file $outdir/timing_routed.rpt
report_timing -max_paths 1 -nworst 1 -delay_type max -file $outdir/critpath_routed.rpt

# TNS/THS dal riepilogo: danno la DIFFUSIONE del problema, non solo il path peggiore.
# Il report NON scrive "TNS: valore" ma una TABELLA: riga di intestazione, riga di trattini, riga dati
#   WNS  TNS  TNSfail  TNStot  WHS  THS  THSfail  THStot  WPWS ...
# quindi si prende la 2a riga dopo l'intestazione e si leggono i campi per posizione.
set ts [report_timing_summary -return_string]
set lines [split $ts "\n"]
set got 0
for {set i 0} {$i < [llength $lines]} {incr i} {
  if {[string match "*WNS(ns)*TNS(ns)*" [lindex $lines $i]]} {
    set d [lindex $lines [expr {$i+2}]]
    if {[llength $d] >= 6} {
      puts "IMPL-TNS = [lindex $d 1]"
      puts "IMPL-THS = [lindex $d 5]"
      # coerenza col path peggiore: se divergono, uno dei due e' letto male
      if {abs([lindex $d 0] - $wns) > 0.01} {
        puts "IMPL-⚠️ WNS da tabella ([lindex $d 0]) != WNS da get_timing_paths ($wns)"
      }
      set got 1
    }
    break
  }
}
if {!$got} { puts "IMPL-TNS = NON AGGANCIATO ; IMPL-THS = NON AGGANCIATO" }

# Risorse: DOPPIO backslash. Dentro una stringa "..." Tcl consuma il primo livello, quindi \\s arriva
# al motore regex come \s. Con UN solo backslash \s diventa la lettera 's' e non aggancia nulla:
# era la causa dei valori vuoti in calib_impl.tcl, NON il formato del report post-route.
set u [report_utilization -return_string]
foreach n {{Slice LUTs\*?} {LUT as Memory} {Slice Registers} {DSPs} {Block RAM Tile}} {
  if {[regexp "\\|\\s*${n}\\s*\\|\\s*(\[0-9.\]+)\\s*\\|" $u -> v]} {
    puts "IMPL-RES $n = $v"
  } else {
    puts "IMPL-RES $n = NON AGGANCIATO"
  }
}

write_checkpoint -force $outdir/routed.dcp
puts "IMPL: TOTALE [expr {[clock seconds]-$t0}] s"
