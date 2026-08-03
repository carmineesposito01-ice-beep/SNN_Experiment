#!/usr/bin/env bash
# T6b · M2 — NETLIST-PAR (parte 2): simulazione di TIMING della netlist post-place&route col TB AXI gia' validato.
# La netlist timesim usa primitive SIMPRIM (-L simprims_ver) e richiede glbl; l'SDF si annota sull'istanza del DUT.
# args: ROOT NETLISTDIR HWDIR NSTEP NTRAJ GATEMODE
#   I .mem stim_axi_<i>/gold_axi_<i> devono essere gia' in ROOT (generati da gen_axi_golden).
set -u
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
ROOT="$1"; NL="$2"; HWDIR="$3"; NSTEP="$4"; NTRAJ="$5"; GATEMODE="$6"; CLKHALF="${7:-9.615}"
cd "$ROOT"
rm -rf xsim.dir.np np_*.log; mkdir -p np
cp "$NL/tier_axi_lite_time.v" np/
cp "$HWDIR/tb_tier_axi.v" np/
# L'SDF va nella dir da cui gira xsim: la netlist generata da `write_verilog -sdf_anno true` contiene gia'
# $sdf_annotate("tier_axi_lite_time.sdf",...) con path RELATIVO -> niente opzione -sdfmax da riga di comando
# (che oltretutto perde l''=' passando dal wrapper .bat di Git-Bash, come il -d di xvlog).
cp "$NL/tier_axi_lite_time.sdf" ./
# NETLIST_SIM: esclude dal TB i riferimenti GERARCHICI (SYNC/DBG) -- nella netlist post-route quei nomi
# non esistono piu'. Il cancello AXI-COSIM guarda solo le porte AXI, quindi resta valido.
# CLKHALF: semi-periodo in ns dell'FCLK per cui la netlist e' stata IMPLEMENTATA (52 MHz -> 9.615 ns).
# ⚠️ In sim di TIMING il periodo NON e' arbitrario: pilotare la netlist piu' veloce del suo FCLK produce
#    violazioni di setup e quindi risultati sbagliati (100 MHz su una netlist da 52 MHz -> 250/250 mismatch).
printf '`define NSTEP %s\n`define GATEMODE %s\n`define NETLIST_SIM 1\n`define CLKHALF %s\n' \
  "$NSTEP" "$GATEMODE" "$CLKHALF" > axi_params.vh
# ⚠️ Git-Bash converte gli argomenti che iniziano con '/' in path Windows ("/tb_tier_axi/dut=" e' diventato
#    "C:/Program Files/Git/tb_tier_axi/dut="): MSYS2_ARG_CONV_EXCL disattiva la conversione per -sdfmax.
export MSYS2_ARG_CONV_EXCL="*"

GLBL="C:/AMDDesignTools/2026.1/Vivado/data/verilog/src/glbl.v"
"$VIV/xvlog.bat" -i . np/tier_axi_lite_time.v np/tb_tier_axi.v "$GLBL" > np_xvlog.out 2>&1 \
  || { echo "ERRORE xvlog (netlist)"; tail -8 np_xvlog.out; exit 1; }
# Glitch handling nella sim di timing: i limiti di reject sono -pulse_r (path) e -pulse_int_r (interconnect).
# ⚠️ NON esiste "-pulse_int": xelab rifiuta e stampa l'help (verificato con `xelab -help | grep pulse`).
"$VIV/xelab.bat" -debug off -L simprims_ver -relax -transport_int_delays -pulse_r 0 -pulse_int_r 0 \
  tb_tier_axi glbl -s snapNP > np_xelab.out 2>&1 \
  || { echo "ERRORE xelab (netlist)"; tail -12 np_xelab.out; exit 1; }

tot=0; ntot=0
for ((i=1; i<=NTRAJ; i++)); do
  cp "stim_axi_${i}.mem" axi_stim.mem
  cp "gold_axi_${i}.mem" axi_gold.mem
  o=$("$VIV/xsim.bat" snapNP -R 2>&1)
  # mostrare ANCHE le righe diagnostiche del TB: filtrare solo ERROR/FATAL lascia ciechi sui valori
  printf '%s\n' "$o" | grep -E "^(DBG|PROBE|ERROR|FATAL)" | head -20
  nm=$(printf '%s\n' "$o" | sed -n 's/.*AXI-COSIM nMismatch=\([0-9]*\) .*/\1/p' | head -1)
  nn=$(printf '%s\n' "$o" | sed -n 's/.*AXI-COSIM nMismatch=[0-9]* n=\([0-9]*\).*/\1/p' | head -1)
  tot=$((tot + ${nm:-0})); ntot=$((ntot + ${nn:-0}))
  echo "  traj $i: nMismatch=${nm:-?} / ${nn:-?}  [$(date +%H:%M:%S)]"
done
echo "NETLIST-PAR-TOT nMismatch=$tot n=$ntot"
