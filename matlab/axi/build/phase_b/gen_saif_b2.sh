#!/usr/bin/env bash
# gen_saif_b2.sh — ricostruisce i SAIF (b2_typical.saif / b2_worst.saif) dal netlist funcsim.
#   Colma il GAP: la generazione SAIF non era in uno script committato (stava nel working dir perso
#   D:/zbd_pb2). Prende funcsim.v (post-route, da power_b2.tcl) + tb_b2_stream.v + gli stimoli, e
#   per ognuno {typical,worst} fa xvlog -> xelab -> xsim -R con log_saif -> write_saif.
# Uso: bash gen_saif_b2.sh    (dopo power_b2.tcl, che scrive D:/zbd_pb2/funcsim.v)
set -euo pipefail

ROOT="D:/zbd_pb2"                         # working dir corto, senza spazi (limite path Windows)
PB="D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/axi/phase_b"
XVLOG="C:/AMDDesignTools/2026.1/Vivado/bin/xvlog.bat"
XELAB="C:/AMDDesignTools/2026.1/Vivado/bin/xelab.bat"
XSIM="C:/AMDDesignTools/2026.1/Vivado/bin/xsim.bat"

test -f "$ROOT/funcsim.v" || { echo "!! manca $ROOT/funcsim.v (eseguire prima power_b2.tcl)"; exit 1; }
cp "$PB/stim_typical.mem" "$ROOT/stim_typical.mem"
cp "$PB/stim_worst.mem"   "$ROOT/stim_worst.mem"

cd "$ROOT"
for lab in typical worst; do
  # tb con __STIM__ sostituito dal path corto dello stimolo (readmemh non ama gli spazi)
  sed "s#__STIM__#stim_${lab}.mem#" "$PB/tb_b2_stream.v" > "tb_${lab}.v"
  # saif tcl: logga i toggle del solo DUT (attivita' interna), non il tb
  cat > "saif_${lab}.tcl" <<EOF
open_saif b2_${lab}.saif
log_saif [get_objects -r /tb_b2_stream/dut/*]
run all
close_saif
quit
EOF
  # funcsim.v e' un netlist GATE-LEVEL: istanzia primitive UNISIM (FDCE, LUT6, RAM...) non definite
  # nel file -> servono `-L unisims_ver` (+ secureip) e `glbl` come secondo top (GSR). Senza:
  # "instantiating unknown module FDCE" -> "Static elaboration ... failed".
  "$XVLOG" funcsim.v "tb_${lab}.v" >/dev/null
  "$XELAB" -debug typical -L unisims_ver -L secureip tb_b2_stream glbl -s "snap_${lab}" >/dev/null
  "$XSIM" "snap_${lab}" -R -tclbatch "saif_${lab}.tcl"
  test -f "b2_${lab}.saif" && echo "SAIF-OK $lab -> $ROOT/b2_${lab}.saif" || { echo "!! SAIF $lab non prodotto"; exit 1; }
done
echo "DONE-GEN-SAIF-B2"
