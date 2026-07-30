#!/usr/bin/env bash
# T6b · M3 — SAIF della fase ATTIVA: un file per workload (9 reali + 1 worst).
# Riusa tb_tier_axi (che confronta anche col golden: la run di potenza vale pure come conferma funzionale).
# ⚠️ -debug typical e' OBBLIGATORIO per il SAIF (con -debug off: "compiled without trace information").
# ⚠️ Si verifica l'ARTEFATTO (.saif non vuoto), non una riga di log.
# args: ROOT NETLISTDIR HWDIR NSTEP NWL GATEMODE CLKHALF
set -u
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
ROOT="$1"; NL="$2"; HWDIR="$3"; NSTEP="$4"; NWL="$5"; GATEMODE="$6"; CLKHALF="${7:-9.615}"
cd "$ROOT"
rm -rf xsim.dir pa; mkdir pa
cp "$NL/tier_axi_lite_func.v" pa/
cp "$HWDIR/tb_tier_axi.v"     pa/
printf '`define NSTEP %s\n`define GATEMODE %s\n`define NETLIST_SIM 1\n`define CLKHALF %s\n' \
  "$NSTEP" "$GATEMODE" "$CLKHALF" > axi_params.vh

GLBL="C:/AMDDesignTools/2026.1/Vivado/data/verilog/src/glbl.v"
"$VIV/xvlog.bat" -i . pa/tier_axi_lite_func.v pa/tb_tier_axi.v "$GLBL" > pa_vlog.out 2>&1 \
  || { echo "ERRORE xvlog (active)"; tail -8 pa_vlog.out; exit 1; }
"$VIV/xelab.bat" -debug typical -L unisims_ver -relax tb_tier_axi glbl -s snapACT > pa_el.out 2>&1 \
  || { echo "ERRORE xelab (active)"; tail -10 pa_el.out; exit 1; }

for ((i=1; i<=NWL; i++)); do
  cp "stim_pw_${i}.mem" axi_stim.mem
  cp "gold_pw_${i}.mem" axi_gold.mem
  SF="$ROOT/saif_act_g${GATEMODE}_wl${i}.saif"
  cat > sim_act.tcl <<EOF
open_saif "$SF"
log_saif [get_objects -r /tb_tier_axi/dut/*]
run all
close_saif
quit
EOF
  "$VIV/xsim.bat" snapACT -tclbatch sim_act.tcl > pa_sim_${i}.out 2>&1
  nm=$(grep -oE "AXI-COSIM nMismatch=[0-9]+ n=[0-9]+" pa_sim_${i}.out | head -1)
  if [ -s "$SF" ]; then
    SZ=$(stat -c%s "$SF" 2>/dev/null || echo "?")
    echo "  wl ${i}: SAIF OK (${SZ} B) | ${nm:-'(no cosim line)'}  [$(date +%H:%M:%S)]"
  else
    echo "  wl ${i}: ❌ SAIF ASSENTE | ${nm:-'-'}"
    grep -iE "^ERROR|without trace" pa_sim_${i}.out | head -3
  fi
done
echo "SAIF-ACTIVE-DONE gating=$GATEMODE"
