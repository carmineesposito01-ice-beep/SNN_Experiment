#!/usr/bin/env bash
# T7b — STUDIO ENERGETICO del composto, in quattro passi. Ogni numero nasce da un SAIF prodotto da una
# simulazione della netlist post-route; nessuno viene composto o stimato.
#
#   P0  derivazione della FINESTRA ATTIVA (quanti clock dura davvero un control-step, porte AXI incluse)
#   P1  idle: convergenza della finestra (200/1000/5000) + confronto gatato / non gatato
#   P2  attiva: gli 8 carichi reali, gating ON (configurazione di deployment)
#   P3  duty REALE: un control-step intero, misurato -- NON composto
#   P4  da SAIF a watt: una sola sessione Vivado, reset_switching_activity fra un SAIF e il successivo
#
# ⚠️ LA COMPOSIZIONE LINEARE E' INVALIDATA (T6b/M3.4): P_att·δ + P_idle·(1−δ) diede 0,0094 W contro
#    0,015 W misurati (1,6× di sottostima), con lo scarto localizzato sui DSP. Qui i DSP sono 69 invece
#    di 52: a maggior ragione si MISURA il duty, non lo si compone.
# ⚠️ IL WORST SINTETICO NON E' UN LIMITE SUPERIORE (T6b/M3.2: fu il PIU' BASSO di tutti). Non viene
#    prodotto: si riporta il MASSIMO OSSERVATO fra i carichi reali, dichiarato come tale.
#
# Uso: bash run_power.sh [FCLK] [CLKHALF]
set -u
VIV="C:/AMDDesignTools/2026.1/Vivado/bin"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../results"
ROOT="C:/t7bnl"                     # progetto OOC + netlist prodotti da run_netlist.sh
WORK="C:/t7bw"                      # .mem validati di T7a
FCLK="${1:-40}"; CLKHALF="${2:-12.5}"
NL="$ROOT/netlist"
# 8 CARICHI REALI = uno per combinazione regime x cut-in del dataset dei 99 (ENUMERATE: highway/urban/
# truck/mixed x no-cut-in/cut-in; 18+9+18+9+12+6+18+9 = 99). Sono OTTO, non nove: il "nove" del piano
# veniva dal dataset dei 60 di T6b, che ha altri campi.
WLS="1 4 28 31 55 58 73 76"
NACT=50                             # control-step per carico attivo
CTRL_STEP_S=0.1                     # il solo requisito temporale vero

[ -s "$NL/snniidm_axi_lite_func.v" ] || { echo "POWER-ABORT: manca la netlist funcsim ($NL)"; exit 1; }
[ -f "$ROOT/np.xpr" ] || { echo "POWER-ABORT: manca il progetto OOC $ROOT/np.xpr"; exit 1; }
mkdir -p "$OUT"

# ---------- P0: la finestra attiva si MISURA, non si copia ----------
# Un control-step non dura LAT_CLK clock: ci sono anche le scritture AXI e il polling del done. T6b uso'
# 416 clock contro 371 di latenza pura. Qui il valore si deriva dal banco stesso, sull'RTL (veloce): la
# durata e' una proprieta' del PROTOCOLLO del wrapper, identica in RTL e in netlist.
echo "=== P0 · finestra attiva (derivata dal banco, non assunta)  [$(date +%H:%M:%S)] ==="
cd "$WORK"
rm -rf xsim.dir p0; mkdir p0
cp C:/t7bimpl/src/*.v C:/t7bimpl/src/compile_order.txt p0/
cp "$HERE/tb_power_duty.v" p0/
printf '`define GATEMODE 1\n`define CLKHALF %s\n`define NSTEP 1\n`define IDLECYC 100\n`define HB 1000000\n' \
  "$CLKHALF" > axi_params.vh
cp "$WORK/axi_stim_1.mem" axi_stim.mem
( cd p0 && while read -r f; do [ -n "$f" ] || continue; "$VIV/xvlog.bat" "$f" > "c_$f.log" 2>&1 \
    || { echo "xvlog FALLITO su $f"; tail -20 "c_$f.log"; exit 1; }; done < compile_order.txt \
  && "$VIV/xvlog.bat" snniidm_axi_lite.v > w.log 2>&1 \
  && "$VIV/xvlog.bat" "$VIV/../data/verilog/src/glbl.v" > g.log 2>&1 \
  && "$VIV/xvlog.bat" -i .. tb_power_duty.v > t.log 2>&1 \
  && "$VIV/xelab.bat" -debug off -L unisims_ver -relax tb_power_duty glbl -s snapP0 > e.log 2>&1 ) \
  || { echo "POWER-ABORT: P0 non compila"; exit 1; }
( cd p0 && cp ../axi_params.vh ../axi_stim.mem . 2>/dev/null; "$VIV/xsim.bat" snapP0 -R > p0.out 2>&1 )
TR=$(grep -ao "DUTY-READY t=[0-9]*" "$WORK/p0/p0.out" | head -1 | sed 's/.*t=//')
TA=$(grep -ao "DUTY-ACT step=0 done t=[0-9]*" "$WORK/p0/p0.out" | head -1 | sed 's/.*t=//')
[ -n "${TR:-}" ] && [ -n "${TA:-}" ] || { echo "POWER-ABORT: P0 non ha prodotto i marcatori"; tail -20 "$WORK/p0/p0.out"; exit 1; }
# I tempi sono in ps (timescale 1ns/1ps); un periodo = 2*CLKHALF ns
ACT_CLK=$(python -c "print(int(round((${TA}-${TR})/1000.0/(2*${CLKHALF}))))")
TOT_CLK=$(python -c "print(int(round(${CTRL_STEP_S}*${FCLK}*1e6)))")
IDLECYC=$((TOT_CLK - ACT_CLK))
DUTY=$(python -c "print('%.4f' % (100.0*${ACT_CLK}/${TOT_CLK}))")
echo "  finestra attiva MISURATA = ${ACT_CLK} clock (latenza pura 555 + protocollo AXI)"
echo "  control-step a ${FCLK} MHz = ${TOT_CLK} clock  ->  IDLECYC = ${IDLECYC}  ->  duty = ${DUTY} %"
[ "$IDLECYC" -gt 0 ] || { echo "POWER-ABORT: IDLECYC non positivo"; exit 1; }

# ---------- P1: idle, convergenza + gating ----------
echo "=== P1 · idle: convergenza della finestra e confronto gating  [$(date +%H:%M:%S)] ==="
bash "$HERE/run_saif_idle.sh" "$WORK" "$NL" "$HERE" 0 "$CLKHALF" "200 1000 5000"
bash "$HERE/run_saif_idle.sh" "$WORK" "$NL" "$HERE" 1 "$CLKHALF" "200"

# ---------- P2: attiva, 8 carichi reali ----------
echo "=== P2 · attiva: $(echo $WLS | wc -w) carichi reali x ${NACT} control-step, gating ON  [$(date +%H:%M:%S)] ==="
bash "$HERE/run_saif_active.sh" "$WORK" "$NL" "$HERE" "$NACT" 1 "$CLKHALF" "$WLS"

# ---------- P3: duty REALE, un control-step intero ----------
echo "=== P3 · duty REALE (1 control-step intero, ${IDLECYC} clock di idle)  [$(date +%H:%M:%S)] ==="
cd "$WORK"
rm -rf xsim.dir pd; mkdir pd
cp "$NL/snniidm_axi_lite_func.v" pd/
cp "$HERE/tb_power_duty.v"       pd/
printf '`define GATEMODE 1\n`define CLKHALF %s\n`define NSTEP 1\n`define IDLECYC %s\n`define HB 500000\n' \
  "$CLKHALF" "$IDLECYC" > axi_params.vh
cp "$WORK/axi_stim_1.mem" axi_stim.mem
"$VIV/xvlog.bat" -i . pd/snniidm_axi_lite_func.v pd/tb_power_duty.v "$VIV/../data/verilog/src/glbl.v" \
  > pd_vlog.out 2>&1 || { echo "POWER-ABORT: xvlog duty"; tail -20 pd_vlog.out; exit 1; }
"$VIV/xelab.bat" -debug typical -L unisims_ver -relax tb_power_duty glbl -s snapDUTY > pd_el.out 2>&1 \
  || { echo "POWER-ABORT: xelab duty"; tail -20 pd_el.out; exit 1; }
SFD="$WORK/saif_duty_g1.saif"; rm -f "$SFD"
cat > sim_duty.tcl <<EOF
run 1 ns
open_saif "$SFD"
log_saif [get_objects -r /tb_power_duty/dut/*]
run all
close_saif
quit
EOF
"$VIV/xsim.bat" snapDUTY -tclbatch sim_duty.tcl > pd_sim.out 2>&1
grep -aE "DUTY-CFG|DUTY-ACT|DUTY-DONE" pd_sim.out | head -5
[ -s "$SFD" ] || { echo "POWER-ABORT: SAIF duty ASSENTE"; grep -iaE "^ERROR|without trace" pd_sim.out | head -3; exit 1; }
echo "  SAIF duty OK ($(stat -c%s "$SFD") B)  [$(date +%H:%M:%S)]"

# ---------- P4: da SAIF a watt ----------
echo "=== P4 · report_power su tutti i SAIF  [$(date +%H:%M:%S)] ==="
SAIFS=$(ls "$WORK"/saif_*.saif 2>/dev/null)
[ -n "$SAIFS" ] || { echo "POWER-ABORT: nessun SAIF da elaborare"; exit 1; }
"$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog -source "$HERE/power_report.tcl" \
  -tclargs "$ROOT/np.xpr" "$OUT" $SAIFS 2>&1 | grep -E "^(PW|=====|ERROR:)"

# La copertura SAIF e la confidenza vanno NEL numero, non in nota a pie' di pagina.
echo "=== copertura e confidenza (dichiarate accanto ai watt) ==="
grep -h "Design Nets Matched" "$OUT"/power_*.rpt 2>/dev/null | sort -u | head -3
grep -hA3 "Confidence Level" "$OUT"/power_*.rpt 2>/dev/null | head -6
echo "=== FINE STUDIO ENERGETICO  [$(date +%H:%M:%S)] ==="
