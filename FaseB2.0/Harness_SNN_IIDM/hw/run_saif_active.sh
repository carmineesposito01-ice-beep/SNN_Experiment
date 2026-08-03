#!/usr/bin/env bash
# T7b — SAIF della fase ATTIVA: un file per carico reale.
#
# CARICHI REALI: si RIUSANO gli stimoli e i golden gia' generati e VALIDATI in T7a (axi_stim/gold_<i>.mem in
# WORK), invece di generarne di nuovi. Prova e misura restano cosi' sullo STESSO perimetro, e il confronto
# funzionale che il banco fa durante la run di potenza e' contro un golden gia' provato bit-esatto (0/58522).
#
# ⚠️ N. DI CARICHI = 8, non 9. Il piano diceva 9 perche' il dataset dei 60 di T6b ha 9 combinazioni
#    scenario x profilo; il dataset dei 99 usato qui ha altri campi (`regime` x `cut_in`) e le combinazioni
#    popolate sono OTTO (18+9+18+9+12+6+18+9 = 99, enumerate, non supposte).
#
# ⚠️ Gli stimoli di T7a sono da 600 control-step: per la potenza ne bastano 50. Invece di rigenerare gli
#    stimoli si scrive un axi_len LOCALE a 50 -- il banco legge il numero di passi a runtime da li'. I primi
#    50 passi di una traiettoria reale restano un carico reale.
#
# ⚠️ -debug typical e' OBBLIGATORIO: con -debug off xsim e' "compiled without trace information" e
#    open_saif/log_saif non producono NULLA, in silenzio. Si verifica l'ARTEFATTO (.saif non vuoto), non una
#    riga di log: in T6b un controllo scritto sulla riga di log dichiaro' successo 3 volte su 3 mentre nessun
#    SAIF veniva creato.
#
# args: ROOT NETLISTDIR HWDIR NSTEP GATEMODE CLKHALF "<lista carichi>"
set -u
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
ROOT="$1"; NL="$2"; HWDIR="$3"; NSTEP="$4"; GM="$5"; CLKHALF="$6"; WLS="$7"

[ -s "$NL/snniidm_axi_lite_func.v" ] || { echo "SAIF-ABORT: manca la netlist funcsim"; exit 1; }
cd "$ROOT"

# CANCELLO PRELIMINARE: stimoli e golden di OGNI carico prima di compilare.
miss=0
for i in $WLS; do
  for k in stim gold; do
    [ -s "axi_${k}_$i.mem" ] || { echo "manca axi_${k}_$i.mem"; miss=1; }
  done
done
[ $miss -eq 0 ] || { echo "SAIF-ABORT: stimoli/golden incompleti"; exit 1; }

rm -rf xsim.dir pa; mkdir pa
cp "$NL/snniidm_axi_lite_func.v" pa/
cp "$HWDIR/tb_snniidm_axi.v"     pa/
printf '`define NSTEP %s\n`define GATEMODE %s\n`define NETLIST_SIM 1\n`define CLKHALF %s\n' \
  "$NSTEP" "$GM" "$CLKHALF" > axi_params.vh
# axi_len LOCALE: tronca ogni carico a NSTEP control-step (esadecimale, come lo legge $readmemh)
printf '%08X\n' "$NSTEP" > axi_len.mem

GLBL="$VIV/../data/verilog/src/glbl.v"
"$VIV/xvlog.bat" -i . pa/snniidm_axi_lite_func.v pa/tb_snniidm_axi.v "$GLBL" > pa_vlog.out 2>&1 \
  || { echo "ERRORE xvlog (active)"; tail -20 pa_vlog.out; exit 1; }
"$VIV/xelab.bat" -debug typical -L unisims_ver -relax tb_snniidm_axi glbl -s snapACT > pa_el.out 2>&1 \
  || { echo "ERRORE xelab (active)"; tail -20 pa_el.out; exit 1; }

nbad=0
for i in $WLS; do
  cp "axi_stim_$i.mem" axi_stim.mem
  cp "axi_gold_$i.mem" axi_gold.mem
  SF="$ROOT/saif_act_g${GM}_wl${i}.saif"
  rm -f "$SF"
  cat > sim_act.tcl <<EOF
open_saif "$SF"
log_saif [get_objects -r /tb_snniidm_axi/dut/*]
run all
close_saif
quit
EOF
  "$VIV/xsim.bat" snapACT -tclbatch sim_act.tcl > "pa_sim_$i.out" 2>&1
  nm=$(grep -aoE "AXI-COSIM nMismatch=[0-9]+ n=[0-9]+" "pa_sim_$i.out" | head -1)
  if [ -s "$SF" ]; then
    SZ=$(stat -c%s "$SF" 2>/dev/null || echo "?")
    echo "  wl $i: SAIF OK (${SZ} B) | ${nm:-'(nessuna riga cosim)'}  [$(date +%H:%M:%S)]"
  else
    echo "  wl $i: SAIF ASSENTE | ${nm:-'-'}"
    grep -iaE "^ERROR|without trace" "pa_sim_$i.out" | head -3
    nbad=$((nbad+1))
  fi
done
# Un SAIF mancante non e' un dettaglio: la misura di potenza che ne seguirebbe userebbe l'attivita' di
# DEFAULT del tool, producendo un numero credibile e sbagliato.
[ $nbad -eq 0 ] || { echo "SAIF-ACTIVE-FALLITO: $nbad carichi senza SAIF"; exit 1; }
echo "SAIF-ACTIVE-DONE gating=$GM carichi=$(echo $WLS | wc -w)"
