# Genera scheletro IP AXI4-Lite slave via create_peripheral (template Vivado)
set SP "C:/Users/USERPO~1/AppData/Local/Temp/claude/D--Project-MBSE-0-Documenti-Platooning-Focus-Traffic-Flow-2025/63719052-fc3e-48ab-9cdd-20922bd2deb6/scratchpad"
set IPDIR "$SP/axi_ip"
file delete -force $IPDIR
file mkdir $IPDIR
create_project -in_memory -part xc7z020clg400-1
create_peripheral user.org user snn_b2_axi 1.0 -dir $IPDIR
set core [ipx::find_open_core user.org:user:snn_b2_axi:1.0]
add_peripheral_interface S00_AXI -interface_mode slave -axi_type lite $core
generate_peripheral $core
write_peripheral $core
puts "=== IPDIR tree (hdl) ==="
set hdldir "$IPDIR/snn_b2_axi_1.0/hdl"
if { [file isdirectory $hdldir] } {
  foreach f [lsort [glob -nocomplain -directory $hdldir *]] { puts "  [file tail $f]" }
} else {
  puts "  (hdl dir non trovata; contenuto IPDIR:)"
  foreach f [glob -nocomplain -directory "$IPDIR/snn_b2_axi_1.0" *] { puts "  $f" }
}
puts "DONE-AXIGEN"
