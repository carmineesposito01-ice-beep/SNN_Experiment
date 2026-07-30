#!/usr/bin/env bash
# T6b · M2.3 — NETLIST-PAR (funzionale): la netlist POST-PLACE&ROUTE riproduce il blocco?
# Usa la netlist `funcsim` (post-impl, primitive UNISIM, senza ritardi) col TB AXI gia' validato in M1.
#
# PERCHE' funcsim e non timesim: la sim di TIMING con SDF non ha prodotto risultati validi (tutti zero) per una
# configurazione del banco tuttora non risolta; la funcsim risponde alla domanda che conta -- la netlist
# implementata e' logicamente equivalente all'RTL -- mentre la FIRMA DEL TIMING spetta comunque all'STA
# (report_timing: WNS +0,355 ns @52 MHz), non alla simulazione. E' anche la prassi industriale corrente.
#
# args: ROOT NETLISTDIR HWDIR NSTEP NTRAJ GATEMODE [CLKHALF]
set -u
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
ROOT="$1"; NL="$2"; HWDIR="$3"; NSTEP="$4"; NTRAJ="$5"; GATEMODE="$6"; CLKHALF="${7:-9.615}"
cd "$ROOT"
rm -rf xsim.dir nf; mkdir nf
cp "$NL/tier_axi_lite_func.v" nf/
cp "$HWDIR/tb_tier_axi.v" nf/
# NETLIST_SIM: esclude i riferimenti gerarchici (nella netlist quei nomi non esistono). Il cancello AXI-COSIM
# guarda solo le PORTE AXI (black-box) -> resta valido.
printf '`define NSTEP %s\n`define GATEMODE %s\n`define NETLIST_SIM 1\n`define CLKHALF %s\n' \
  "$NSTEP" "$GATEMODE" "$CLKHALF" > axi_params.vh

GLBL="C:/AMDDesignTools/2026.1/Vivado/data/verilog/src/glbl.v"
"$VIV/xvlog.bat" -i . nf/tier_axi_lite_func.v nf/tb_tier_axi.v "$GLBL" > nf_vlog.out 2>&1 \
  || { echo "ERRORE xvlog (funcsim)"; tail -8 nf_vlog.out; exit 1; }
"$VIV/xelab.bat" -debug off -L unisims_ver -relax tb_tier_axi glbl -s snapNF > nf_el.out 2>&1 \
  || { echo "ERRORE xelab (funcsim)"; tail -10 nf_el.out; exit 1; }

tot=0; ntot=0
for ((i=1; i<=NTRAJ; i++)); do
  cp "stim_axi_${i}.mem" axi_stim.mem
  cp "gold_axi_${i}.mem" axi_gold.mem
  o=$("$VIV/xsim.bat" snapNF -R 2>&1)
  printf '%s\n' "$o" | grep -E "^(DBG|ERROR|FATAL)" | head -10
  nm=$(printf '%s\n' "$o" | sed -n 's/.*AXI-COSIM nMismatch=\([0-9]*\) .*/\1/p' | head -1)
  nn=$(printf '%s\n' "$o" | sed -n 's/.*AXI-COSIM nMismatch=[0-9]* n=\([0-9]*\).*/\1/p' | head -1)
  tot=$((tot + ${nm:-0})); ntot=$((ntot + ${nn:-0}))
  echo "  traj $i: nMismatch=${nm:-?} / ${nn:-?}  [$(date +%H:%M:%S)]"
done
echo "NETLIST-FUNC-TOT nMismatch=$tot n=$ntot"
