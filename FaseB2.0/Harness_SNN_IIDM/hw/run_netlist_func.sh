#!/usr/bin/env bash
# T7b — NETLIST (parte 2): la netlist POST-PLACE&ROUTE riproduce il blocco?
# Gira la netlist `funcsim` (post-impl, primitive UNISIM) col banco AXI gia' validato in Task 2, sullo STESSO
# golden. E' un CANCELLO DI CONFERMA su N DICHIARATO -- non la base di una metrica: la sim a livello di porte
# costa ~29x la comportamentale (misurato in T6b), sui 99 scenari sarebbero ~22 ore.
#
# args: ROOT NETLISTDIR HWDIR NSTEP GATEMODE CLKHALF "<lista scenari>"
#   ROOT deve contenere i .mem gia' generati da gen_axi_golden.m
#   CLKHALF = SEMI-periodo in ns dell'FCLK per cui la netlist e' stata implementata (40 MHz -> 12.5).
#
# ⚠️ TRE .mem per scenario, non due: il banco legge il numero di passi a RUNTIME da axi_len.mem. Gli scenari
#    che collidono sono piu' corti (N=307/308 invece di 600); senza axi_len il banco leggerebbe oltre la fine
#    del golden. E' il difetto gia' pagato nella cosim comportamentale -- non si ripete qui.
# ⚠️ `glbl` va COMPILATO oltre a passare -L unisims_ver: le primitive unisim lo referenziano (HDL_PHASE §9.3).
set -u
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
ROOT="$1"; NL="$2"; HWDIR="$3"; NSTEP="$4"; GM="$5"; CLKHALF="$6"; SCEN="$7"

[ -d "$NL" ] || { echo "NETLIST-ABORT: netlist inesistente: $NL"; exit 1; }
cd "$ROOT"
rm -rf xsim.dir nf; mkdir nf
cp "$NL/snniidm_axi_lite_func.v" nf/ || { echo "NETLIST-ABORT: manca snniidm_axi_lite_func.v"; exit 1; }
cp "$HWDIR/tb_snniidm_axi.v" nf/

# CANCELLO PRELIMINARE: i tre .mem di OGNI scenario dichiarato devono esserci PRIMA di compilare.
# Senza, la mancanza si scoprirebbe a meta' run -- ore dopo.
miss=0
for i in $SCEN; do
  for k in stim gold len; do
    [ -s "axi_${k}_$i.mem" ] || { echo "manca axi_${k}_$i.mem"; miss=1; }
  done
done
[ $miss -eq 0 ] || { echo "NETLIST-ABORT: stimoli/golden incompleti"; exit 1; }

# NETLIST_SIM: esclude dal banco i riferimenti GERARCHICI -- nella netlist post-route quei nomi non esistono
# piu'. Il cancello AXI-COSIM guarda solo le PORTE AXI (black-box), quindi resta valido.
printf '`define NSTEP %s\n`define GATEMODE %s\n`define NETLIST_SIM 1\n`define CLKHALF %s\n' \
  "$NSTEP" "$GM" "$CLKHALF" > axi_params.vh

GLBL="$VIV/../data/verilog/src/glbl.v"
"$VIV/xvlog.bat" -i . nf/snniidm_axi_lite_func.v nf/tb_snniidm_axi.v "$GLBL" > nf_vlog.out 2>&1 \
  || { echo "ERRORE xvlog (funcsim)"; tail -20 nf_vlog.out; exit 1; }
"$VIV/xelab.bat" -debug off -L unisims_ver -relax tb_snniidm_axi glbl -s snapNF > nf_el.out 2>&1 \
  || { echo "ERRORE xelab (funcsim)"; tail -20 nf_el.out; exit 1; }

tot=0; ntot=0; nscen=0
for i in $SCEN; do
  cp "axi_stim_$i.mem" axi_stim.mem; cp "axi_gold_$i.mem" axi_gold.mem; cp "axi_len_$i.mem" axi_len.mem
  o=$("$VIV/xsim.bat" snapNF -R 2>&1)
  printf '%s\n' "$o" | grep -E "^(DBG|ERROR|FATAL|TB-FATAL)" | head -10
  line=$(printf '%s\n' "$o" | grep -ao "AXI-COSIM nMismatch=[0-9]* n=[0-9]*" | head -1)
  # Un risultato ASSENTE non e' zero disallineamenti: e' un run fallito, e va detto.
  [ -n "$line" ] || { echo "NETLIST-ABORT: scenario $i senza risultato"; printf '%s\n' "$o" | tail -30; exit 1; }
  nm=$(echo "$line" | sed 's/.*nMismatch=\([0-9]*\).*/\1/')
  nn=$(echo "$line" | sed 's/.*n=\([0-9]*\).*/\1/')
  tot=$((tot + nm)); ntot=$((ntot + nn)); nscen=$((nscen + 1))
  echo "  scenario $i: nMismatch=$nm / $nn  [$(date +%H:%M:%S)]"
done
echo "NETLIST-FUNC-TOT nMismatch=$tot n=$ntot nscen=$nscen"
