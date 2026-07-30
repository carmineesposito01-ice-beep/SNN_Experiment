#!/usr/bin/env bash
# PLANT-PAR (Fase B2.0, T7a): esegue tb_plant_only (NESSUN DUT) su ogni scenario. Isola i difetti del
# plant del testbench prima dell'anello live -- senza, un difetto del plant si traveste da difetto del DUT.
# Non compila VHDL: il TB non istanzia il DUT.
# args: ROOT TB_FILE K NSCEN
#   ROOT deve essere una dir SENZA SPAZI (il repo sta sotto ".../1.Reti Neurali/...": xsim/glob si spezzano)
set -e
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
ROOT="$1"; TB="$2"; K="$3"; NSCEN="$4"
cd "$ROOT"
TBN="$(basename "$TB")"; cp "$TB" "./$TBN"
# macro via FILE .vh: il wrapper Git-Bash -> .bat mangia l'`=` di `-d NOME=val` (HDL_PHASE §9)
printf '`define KVAL %s\n`define SCENF "scen.mem"\n`define INITF "init.mem"\n`define ACCF "acc.mem"\n`define OUTF "plant.txt"\n' "$K" > t7_params.vh
"$VIV/xvlog.bat" -i . "$TBN" > pp_xvlog.log 2>&1 || { echo "xvlog FALLITO:"; tail -30 pp_xvlog.log; exit 1; }
"$VIV/xelab.bat" -debug off "${TBN%.v}" -s ppsnap > pp_xelab.log 2>&1 || { echo "xelab FALLITO:"; tail -30 pp_xelab.log; exit 1; }
for ((i=1; i<=NSCEN; i++)); do
  cp "scen_$i.mem" scen.mem; cp "init_$i.mem" init.mem; cp "acc_$i.mem" acc.mem
  "$VIV/xsim.bat" ppsnap -R > "pp_xsim_$i.log" 2>&1
  if ! grep -q PLANTPAR "pp_xsim_$i.log"; then
    echo "PLANT-PAR scenario $i: nessun output PLANTPAR"; tail -30 "pp_xsim_$i.log"; exit 1
  fi
  [ -s plant.txt ] || { echo "PLANT-PAR scenario $i: plant.txt vuoto o assente"; exit 1; }
  mv plant.txt "plant_$i.txt"
done
echo "PLANTPAR-RUN-OK nscen=$NSCEN"
