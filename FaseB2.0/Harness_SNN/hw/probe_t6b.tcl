# PROBE T6b (P2/P3/P4) — trasforma in FATTI le assunzioni HW dello spec, prima di scrivere il piano.
#   P2  sintesi mixed-language: un wrapper Verilog che istanzia il Tier VHDL sintetizza?
#   P3  board preset PYNQ-Z1 disponibile in questa installazione Vivado?
#   P4  block design con PS7 creabile headless e FCLK parametrizzabile?
# Ogni probe e' in `catch`: un fallimento NON deve impedire agli altri di rispondere.
set HDL  [lindex $argv 0]
set HW   [lindex $argv 1]
set PART xc7z020clg400-1

puts "===== PROBE T6b ====="

# ---------- P3: board preset ----------
puts "\n--- P3: board preset PYNQ-Z1 ---"
if {[catch {
  # come bitstream_board.tcl della Fase B: il repo delle board va IMPOSTATO, non e' nel default
  set_param board.repoPaths [list "C:/AMDDesignTools/Boards_Drivers"]
  puts "P3 repoPaths impostato: [get_param board.repoPaths]"
  set bps [get_board_parts -quiet]
  puts "P3 board parts totali: [llength $bps]"
  set pynq [get_board_parts -quiet -filter {NAME =~ *pynq*}]
  if {[llength $pynq] > 0} {
    puts "P3 VERDETTO: PYNQ TROVATA -> [join $pynq {, }]"
  } else {
    puts "P3 VERDETTO: PYNQ NON trovata fra i board parts installati"
    puts "P3 repo paths: [get_param board.repoPaths]"
  }
} msg]} { puts "P3 ERRORE: $msg" }

# ---------- P2: sintesi mixed-language ----------
puts "\n--- P2: sintesi mixed-language (wrapper Verilog + DUT VHDL) ---"
if {[catch {
  create_project -in_memory -part $PART
  set ord [split [string trim [read [open "$HDL/compile_order.txt" r]]] "\n"]
  foreach f $ord { read_vhdl "$HDL/[string trim $f]" }
  read_verilog "$HW/probe_wrap.v"
  synth_design -top probe_wrap -part $PART -mode out_of_context
  puts "P2 VERDETTO: sintesi mixed-language RIUSCITA (top=probe_wrap Verilog, DUT Donatello_Tier VHDL istanziato dentro)"
  # utilizzo post-synth: si estrae dal TESTO del report (report_utilization -return_string ritorna una stringa,
  # NON un oggetto: passarla a get_property e' l'errore che ha fatto fallire questo probe al primo giro)
  set rpt [report_utilization -return_string]
  foreach line [split $rpt "\n"] {
    if {[regexp {\|\s*(Slice LUTs\*?|Slice Registers|DSPs|Block RAM Tile)\s*\|\s*(\d+)} $line -> nm val]} {
      puts "P2 utilizzo OOC (post-synth, indicativo): [string trim $nm] = $val"
    }
  }
} msg]} { puts "P2 ERRORE: $msg" }

# ---------- P4: block design con PS7 + FCLK ----------
puts "\n--- P4: block design PS7 headless + FCLK parametrizzabile ---"
if {[catch {
  close_project -quiet
  create_project -in_memory -part $PART
  set pynq [get_board_parts -quiet -filter {NAME =~ *pynq*}]
  if {[llength $pynq] > 0} {
    set_property board_part [lindex $pynq 0] [current_project]
    puts "P4 board_part impostata: [lindex $pynq 0]"
  } else {
    puts "P4 nessuna board part: procedo con PS7 generico (preset da applicare a mano)"
  }
  create_bd_design bdprobe
  set ps [create_bd_cell -type ip -vlnv [lindex [get_ipdefs -quiet *processing_system7*] 0] ps7]
  puts "P4 PS7 istanziato: [get_property VLNV $ps]"
  if {[llength $pynq] > 0} {
    catch { apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
              -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps }
  }
  # FCLK parametrizzabile? (il clock del sistema in T6b sara' l'Fmax trovato)
  foreach f {8 50 100} {
    set_property -dict [list CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $f] $ps
    set got [get_property CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $ps]
    puts "P4 FCLK richiesto ${f} MHz -> impostato: $got"
  }
  validate_bd_design -quiet
  puts "P4 VERDETTO: block design con PS7 creato e validato headless; FCLK impostabile via CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ"
} msg]} { puts "P4 ERRORE: $msg" }

puts "\n===== PROBE T6b FINE ====="
