# PROBE M2 — l'unico punto di T6b non coperto dai probe iniziali: il wrapper Verilog, aggiunto al block design
# come MODULE REFERENCE, espone S_AXI come INTERFACCIA AXI riconosciuta (necessaria per apply_bd_automation)?
# Se no -> serve impacchettarlo come IP (ipx::package_project) o annotare le X_INTERFACE_INFO.
# Uso: vivado -mode batch -source probe_bd.tcl -tclargs <SRCDIR> <ROOT>
#   SRCDIR = cartella CORTA (senza spazi) con dentro i .vhd + compile_order.txt + tier_axi_lite.v.
#   ⚠️ I path NON devono contenere spazi: `add_files` ri-parsa la stringa come LISTA e la spezza
#      ("File or Directory 'D:/Project_MBSE/1.Reti' does not exist"). I sorgenti vanno COPIATI qui
#      dal chiamante (stessa convenzione del runner xsim).
set HDL  [lindex $argv 0]
set HW   [lindex $argv 0]
set ROOT [lindex $argv 1]
set PART xc7z020clg400-1

puts "===== PROBE BD (M2) ====="
set_param board.repoPaths [list "C:/AMDDesignTools/Boards_Drivers"]

if {[catch {
  file delete -force $ROOT
  create_project bdprobe $ROOT -part $PART -force
  set bp [lindex [get_board_parts -quiet -filter {NAME =~ *pynq-z1*}] 0]
  if {$bp ne ""} { set_property board_part $bp [current_project]; puts "BD board_part: $bp" }

  foreach f [split [string trim [read [open "$HDL/compile_order.txt" r]]] "\n"] {
    add_files -norecurse [list "$HDL/[string trim $f]"]
  }
  add_files -norecurse [list "$HW/tier_axi_lite.v"]
  update_compile_order -fileset sources_1
  puts "BD sorgenti aggiunti; top rilevato: [get_property top [current_fileset]]"

  create_bd_design sys
  set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7]
  apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps
  set_property -dict [list CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {50} CONFIG.PCW_USE_M_AXI_GP0 {1}] $ps
  puts "BD PS7 configurato (FCLK 50, M_AXI_GP0 on)"

  # ---- il punto in verifica ----
  set ip [create_bd_cell -type module -reference tier_axi_lite tier0]
  puts "BD module reference creato: [get_property NAME $ip]"
  set ifs [get_bd_intf_pins -quiet tier0/*]
  puts "BD interfacce esposte da tier0: '[join $ifs {, }]'"
  set clks [get_bd_pins -quiet tier0/*ACLK*]
  puts "BD pin di clock: '[join $clks {, }]'"
  if {[llength [get_bd_intf_pins -quiet tier0/S_AXI]] > 0} {
    puts "PROBE-BD VERDETTO: S_AXI RICONOSCIUTA come interfaccia -> apply_bd_automation utilizzabile"
    if {[catch {
      apply_bd_automation -rule xilinx.com:bd_rule:axi4 \
        -config { Master {/ps7/M_AXI_GP0} Clk {Auto} } [get_bd_intf_pins tier0/S_AXI]
      validate_bd_design
      puts "PROBE-BD AUTOMATION: connessione riuscita e BD VALIDATO"
    } m2]} { puts "PROBE-BD AUTOMATION FALLITA: $m2" }
  } else {
    puts "PROBE-BD VERDETTO: S_AXI NON riconosciuta -> serve ipx::package_project (o X_INTERFACE_INFO)"
  }
} msg]} { puts "PROBE-BD ERRORE: $msg" }

puts "===== PROBE BD FINE ====="
