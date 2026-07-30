#!/usr/bin/env bash
# Runner xsim CLOSED-LOOP (Fase B2.0, T7). Gemello di rtl_run_xsim.sh, che resta di T6: quello e'
# open-loop con stim/gold PRECALCOLATI, qui lo stimolo NON esiste a priori -- lo genera il plant dentro
# il testbench, in retroazione sull'uscita del DUT. Responsabilita' diverse => file diversi.
#
# Copia HDL + TB in ROOT corta (il repo sta sotto ".../1.Reti Neurali/...": xsim/glob si spezzano sullo
# spazio), COMPILA UNA VOLTA, poi un xsim per scenario: lo stato SNN vive nella hdl.RAM e si azzera solo
# all'init della simulazione, non dal reset a runtime (finding T6a).
#
# args: ROOT HDLSRC_DIR TB_FILE K HOLD NSCEN
#   HDLSRC_DIR deve contenere i sorgenti + compile_order.txt (scritto da rtl_gen_dut).
#   Il linguaggio si deduce dall'estensione dei file elencati in compile_order.txt: .vhd -> xvhdl, .v -> xvlog.
set -e
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
ROOT="$1"; HDLSRC="$2"; TB="$3"; K="$4"; HOLD="$5"; NSCEN="$6"

[ -d "$HDLSRC" ] || { echo "HDLSRC inesistente: $HDLSRC"; exit 1; }
[ -f "$HDLSRC/compile_order.txt" ] || { echo "manca $HDLSRC/compile_order.txt"; exit 1; }
cd "$ROOT"
rm -rf xsim.dir hdl *.jou; mkdir hdl
cp "$HDLSRC"/*.vhd hdl/ 2>/dev/null || true
cp "$HDLSRC"/*.v   hdl/ 2>/dev/null || true
cp "$HDLSRC/compile_order.txt" hdl/
TBN="$(basename "$TB")"; cp "$TB" "./$TBN"

# macro via FILE .vh: il wrapper Git-Bash -> .bat mangia l'`=` di `-d NOME=val` (HDL_PHASE §9).
printf '`define KVAL %s\n`define HOLDV %s\n`define SCENF "scen.mem"\n`define INITF "init.mem"\n`define OUTF "ser.txt"\n' \
       "$K" "$HOLD" > t7_params.vh

mapfile -t ORD < hdl/compile_order.txt
for f in "${ORD[@]}"; do
  [ -n "$f" ] || continue
  case "$f" in
    *.vhd) TOOL=xvhdl ;;
    *.v)   TOOL=xvlog ;;
    *) echo "estensione non gestita in compile_order.txt: $f"; exit 1 ;;
  esac
  "$VIV/$TOOL.bat" "hdl/$f" > "c_$f.log" 2>&1 || { echo "$TOOL FALLITO su $f:"; tail -30 "c_$f.log"; exit 1; }
done

"$VIV/xvlog.bat" -i . "$TBN" > tb_xvlog.log 2>&1 || { echo "xvlog TB FALLITO:"; tail -30 tb_xvlog.log; exit 1; }
"$VIV/xelab.bat" -debug off "${TBN%.v}" -s t7snap > xelab.log 2>&1 || { echo "xelab FALLITO:"; tail -40 xelab.log; exit 1; }

for ((i=1; i<=NSCEN; i++)); do
  cp "scen_$i.mem" scen.mem; cp "init_$i.mem" init.mem
  rm -f ser.txt
  "$VIV/xsim.bat" t7snap -R > "xsim_$i.log" 2>&1
  if ! grep -q "T7RES" "xsim_$i.log"; then
    echo "SCENARIO $i: nessun T7RES nel log"; tail -30 "xsim_$i.log"; exit 1
  fi
  [ -s ser.txt ] || { echo "SCENARIO $i: ser.txt vuoto o assente"; exit 1; }
  mv ser.txt "ser_$i.txt"
  echo "  scenario $i/$NSCEN: $(grep -o 'T7RES.*' "xsim_$i.log")"
done
echo "RUNCLOSED-OK nscen=$NSCEN"
