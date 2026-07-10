# Stage A: board check + package IP snn_b2_axi_lite (infer AXI4-Lite)
set SP  "C:/Users/USERPO~1/AppData/Local/Temp/claude/D--Project-MBSE-0-Documenti-Platooning-Focus-Traffic-Flow-2025/63719052-fc3e-48ab-9cdd-20922bd2deb6/scratchpad"
set SNN "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/codegen/snn_top_b2/hdlsrc"
set AXI "$SP/axi_ip/snn_b2_axi_1_0/hdl"

puts "=== BOARDS pynq/z1 disponibili ==="
set found 0
foreach b [get_board_parts -quiet] {
  if {[string match -nocase *pynq* $b] || [string match -nocase *z1* $b]} { puts "  $b"; incr found }
}
if {$found == 0} { puts "  (nessun board file PYNQ-Z1 -> user config PS7 manuale)" }

set IPREPO "$SP/ip_repo/snn_b2_axi"
file delete -force "$SP/ip_repo"
file mkdir $IPREPO
file delete -force "$SP/pkgprj"
create_project pkgprj "$SP/pkgprj" -part xc7z020clg400-1 -force
add_files [list "$SNN/snn_top_b2_pkg.vhd" "$SNN/DualPortRAM_generic.vhd" "$SNN/snn_top_b2.vhd" "$AXI/snn_top_b2_flat.vhd" "$AXI/snn_b2_axi_lite.v"]
set_property top snn_b2_axi_lite [current_fileset]
update_compile_order -fileset sources_1
ipx::package_project -root_dir $IPREPO -vendor user.org -library user -taxonomy /UserIP -import_files -set_current true
set core [ipx::current_core]
puts "=== bus interfaces inferite ==="
foreach bi [ipx::get_bus_interfaces -of_objects $core] {
  puts "  [get_property NAME $bi]  ->  [get_property BUS_TYPE_VLNV $bi]"
}
ipx::create_xgui_files $core
ipx::update_checksums $core
ipx::save_core $core
puts "IP salvato in: $IPREPO"
puts "DONE-PKG"
