# T6b · M2.3 — diagnosi NETLIST-PAR: esporta la netlist FUNCSIM (post-impl, SENZA ritardi) dal progetto OOC
# gia' implementato. Girandoci sopra lo stesso TB si separa in un colpo:
#   funcsim VERDE  -> il problema e' di TIMING (ritardi/SDF)
#   funcsim ZERO   -> il problema e' STRUTTURALE (X-propagation / GSR / init della BRAM nella netlist)
# Non si puo' ottenere lo stesso togliendo il file SDF: $sdf_annotate e' INCORPORATO nella netlist timesim
# e l'elaborazione fallisce senza di esso.
# Uso: vivado -mode batch -source netlist_funcsim.tcl -tclargs <XPR> <OUTDIR>
set XPR [lindex $argv 0]
set OUT [lindex $argv 1]
open_project $XPR
open_run impl_1
file mkdir $OUT
write_verilog -force -mode funcsim "$OUT/tier_axi_lite_func.v"
puts "FUNCSIM EXPORT-OK -> $OUT/tier_axi_lite_func.v"
