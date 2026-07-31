#!/usr/bin/env bash
# T6b · M3 — SAIF della fase IDLE + PROBE DI CONVERGENZA della finestra.
# Gira tb_power_idle (1 inferenza, poi clock libero senza commit) e registra il SAIF SOLO sulla finestra idle,
# per piu' lunghezze di finestra: la finestra giusta e' la piu' corta oltre cui il valore non cambia piu' (~1%).
# ⚠️ Verifica anche la PREMESSA: se la potenza idle non si stabilizza (o e' alta), il design NON e' fermo in idle
#    (FSM che free-runna / contatori attivi) -> il gating avrebbe poco da spegnere. E' un finding, non un dettaglio.
# args: ROOT NETLISTDIR HWDIR GATEMODE CLKHALF "<lista finestre in cicli>"
set -u
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
ROOT="$1"; NL="$2"; HWDIR="$3"; GATEMODE="$4"; CLKHALF="$5"; WINS="${6:-200 1000 5000}"
cd "$ROOT"
rm -rf xsim.dir ps; mkdir ps
cp "$NL/snniidm_axi_lite_func.v" ps/
cp "$HWDIR/tb_power_idle.v"   ps/
printf '`define GATEMODE %s\n`define CLKHALF %s\n' "$GATEMODE" "$CLKHALF" > axi_params.vh

GLBL="C:/AMDDesignTools/2026.1/Vivado/data/verilog/src/glbl.v"
"$VIV/xvlog.bat" -i . ps/snniidm_axi_lite_func.v ps/tb_power_idle.v "$GLBL" > ps_vlog.out 2>&1 \
  || { echo "ERRORE xvlog (idle)"; tail -8 ps_vlog.out; exit 1; }
# ⚠️ -debug typical e' OBBLIGATORIO per il SAIF: con -debug off xsim risponde
#    "compiled without trace information" e open_saif/log_saif NON producono alcun file.
"$VIV/xelab.bat" -debug typical -L unisims_ver -relax tb_power_idle glbl -s snapIDLE > ps_el.out 2>&1 \
  || { echo "ERRORE xelab (idle)"; tail -10 ps_el.out; exit 1; }

# istante in cui il TB dichiara l'idle: 1 inferenza (371 clk) + AXI + margine -> attendiamo IDLE-READY
PER=$(awk -v h="$CLKHALF" 'BEGIN{printf "%.4f", 2*h}')
for W in $WINS; do
  WNS=$(awk -v w="$W" -v p="$PER" 'BEGIN{printf "%.1f", w*p}')
  cat > sim_idle.tcl <<EOF
# avanza fino a idle_flag (fine inferenza), POI apre la finestra SAIF: cosi' misura SOLO l'idle
run 60 us
open_saif "$ROOT/saif_idle_g${GATEMODE}_w${W}.saif"
log_saif [get_objects -r /tb_power_idle/dut/*]
run ${WNS} ns
close_saif
quit
EOF
  "$VIV/xsim.bat" snapIDLE -tclbatch sim_idle.tcl > ps_sim_${W}.out 2>&1
  # ⚠️ Si verifica l'ARTEFATTO (file .saif esistente e non vuoto), NON una riga di log: la prima versione di
  #    questo script controllava solo "IDLE-READY" e stampava "idle raggiunto" mentre NESSUN saif veniva creato
  #    (xelab era -debug off). Un controllo su una proxy assolve un fallimento reale.
  SF="saif_idle_g${GATEMODE}_w${W}.saif"
  if [ -s "$SF" ]; then
    SZ=$(stat -c%s "$SF" 2>/dev/null || echo "?")
    echo "  finestra ${W} cicli (${WNS} ns): SAIF OK (${SZ} byte) -> $SF"
  else
    echo "  finestra ${W} cicli (${WNS} ns): ❌ SAIF ASSENTE/VUOTO"
    grep -iE "^ERROR|not.*trace|without trace" ps_sim_${W}.out | head -3
  fi
done
echo "SAIF-IDLE-DONE gating=$GATEMODE"
