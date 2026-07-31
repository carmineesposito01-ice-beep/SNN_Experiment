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
FCLK="${1:-40}"; CLKHALF="${2:-12.5}"; STAGE="${3:-all}"
NL="$ROOT/netlist"
# Budget di calcolo per la sola P3 (duty reale). NON e' una preferenza estetica: 4.000.000 di clock a
# ritmo di fase ATTIVA costerebbero ~3 ore (dal costo netlist MISURATO in NETLIST.md). Il ritmo dell'IDLE
# e' molto piu' alto ma NON e' noto, quindi si MISURA con una sonda corta e si estrapola. Se
# l'estrapolazione supera il budget, lo script SI FERMA e porta i numeri: ridurre il perimetro e' una
# decisione dell'utente, non un ripiego preso in corsa.
P3_BUDGET_S="${P3_BUDGET_S:-5400}"      # 90 minuti
P3_PROBE_IDLE="${P3_PROBE_IDLE:-20000}" # clock di idle della sonda
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
# L'UNITA' DI %0t NON SI ASSUME: dipende da $timeformat, il cui default e' legato alla precisione del
# simulatore e non e' garantito fra versioni. Assumere "ps" e sbagliare darebbe una finestra attiva 1000x
# piu' piccola: IDLECYC cambierebbe dello 0,014% (invisibile) e il duty verrebbe stampato 0,0000%.
# Si provano quindi ENTRAMBE le letture e si tiene quella PLAUSIBILE.
# Le due non possono essere plausibili INSIEME: separazione 1000x contro una finestra larga 50x
# (servirebbe d>=1e7 e d<=5e5 insieme). Quindi il ramo di rifiuto significa sempre e solo
# "NESSUNA lettura plausibile" -- e va detto cosi', non "ambiguo": un messaggio che nomina la causa
# sbagliata manda a cercare nel posto sbagliato.
ACT_CLK=$(python -c "
d = ${TA} - ${TR}; per = 2*${CLKHALF}
cand = {'ps': d/1000.0/per, 'ns': d/per}
ok = {u: round(v) for u, v in cand.items() if 400 <= v <= 20000}   # un control-step: 555 di latenza + AXI
if len(ok) != 1:
    print('NONPLAUSIBILE d=%d ps->%.3f ns->%.3f' % (d, cand['ps'], cand['ns'])); raise SystemExit(0)
u, v = next(iter(ok.items())); print('%d %s' % (v, u))
" )
case "$ACT_CLK" in
  NONPLAUSIBILE*) echo "POWER-ABORT: finestra attiva fuori da ogni lettura sensata -- $ACT_CLK"
                  echo "  (attesi ~555 clock di latenza + protocollo AXI; controllare i marcatori del banco)"; exit 1 ;;
esac
TUNIT="${ACT_CLK##* }"; ACT_CLK="${ACT_CLK%% *}"
case "$ACT_CLK" in ''|*[!0-9]*) echo "POWER-ABORT: finestra attiva non numerica: '$ACT_CLK'"; exit 1 ;; esac
echo "  unita' di \$time DEDOTTA dai valori: ${TUNIT}"
TOT_CLK=$(python -c "print(int(round(${CTRL_STEP_S}*${FCLK}*1e6)))")
IDLECYC=$((TOT_CLK - ACT_CLK))
DUTY=$(python -c "print('%.4f' % (100.0*${ACT_CLK}/${TOT_CLK}))")
echo "  finestra attiva MISURATA = ${ACT_CLK} clock (latenza pura 555 + protocollo AXI)"
echo "  control-step a ${FCLK} MHz = ${TOT_CLK} clock  ->  IDLECYC = ${IDLECYC}  ->  duty = ${DUTY} %"
[ "$IDLECYC" -gt 0 ] || { echo "POWER-ABORT: IDLECYC non positivo"; exit 1; }

# ---------- P1: idle, convergenza + gating ----------
if [ "$STAGE" = "all" ] || [ "$STAGE" = "idle" ]; then
echo "=== P1 · idle: convergenza della finestra e confronto gating  [$(date +%H:%M:%S)] ==="
bash "$HERE/run_saif_idle.sh" "$WORK" "$NL" "$HERE" 0 "$CLKHALF" "200 1000 5000"
bash "$HERE/run_saif_idle.sh" "$WORK" "$NL" "$HERE" 1 "$CLKHALF" "200"
fi

# ---------- P2: attiva, 8 carichi reali ----------
if [ "$STAGE" = "all" ] || [ "$STAGE" = "active" ]; then
echo "=== P2 · attiva: $(echo $WLS | wc -w) carichi reali x ${NACT} control-step, gating ON  [$(date +%H:%M:%S)] ==="
bash "$HERE/run_saif_active.sh" "$WORK" "$NL" "$HERE" "$NACT" 1 "$CLKHALF" "$WLS"
fi

# ---------- P3: duty REALE, un control-step intero ----------
if [ "$STAGE" = "all" ] || [ "$STAGE" = "duty" ]; then
echo "=== P3 · duty REALE (1 control-step intero, ${IDLECYC} clock di idle)  [$(date +%H:%M:%S)] ==="
cd "$WORK"
rm -rf xsim.dir pd; mkdir pd
cp "$NL/snniidm_axi_lite_func.v" pd/
cp "$HERE/tb_power_duty.v"       pd/
cp "$WORK/axi_stim_1.mem" axi_stim.mem
duty_build() {   # $1 = IDLECYC ; compila UNA volta, poi si cambia solo il define e si ri-elabora
  printf '`define GATEMODE 1\n`define CLKHALF %s\n`define NSTEP 1\n`define IDLECYC %s\n`define HB 500000\n' \
    "$CLKHALF" "$1" > axi_params.vh
  "$VIV/xvlog.bat" -i . pd/snniidm_axi_lite_func.v pd/tb_power_duty.v "$VIV/../data/verilog/src/glbl.v" \
    > pd_vlog.out 2>&1 || { echo "POWER-ABORT: xvlog duty"; tail -20 pd_vlog.out; exit 1; }
  "$VIV/xelab.bat" -debug typical -L unisims_ver -relax tb_power_duty glbl -s snapDUTY > pd_el.out 2>&1 \
    || { echo "POWER-ABORT: xelab duty"; tail -20 pd_el.out; exit 1; }
}

# --- P3-SONDA: il ritmo dell'IDLE si MISURA, non si suppone ---
# In idle il simulatore a eventi ha pochissimo da fare, quindi va molto piu' veloce che in fase attiva --
# ma di quanto NON e' noto, e la forbice fra le ipotesi ragionevoli e' di ore. Si misura su una finestra
# corta e si estrapola in modo LINEARE (il costo per clock di idle e' costante: lo stato e' fermo).
echo "  P3-SONDA: ${P3_PROBE_IDLE} clock di idle, per misurare il ritmo  [$(date +%H:%M:%S)]"
duty_build "$P3_PROBE_IDLE"
t0=$(date +%s)
"$VIV/xsim.bat" snapDUTY -R > pd_probe.out 2>&1
t1=$(date +%s); TPROBE=$((t1-t0))
grep -aE "DUTY-CFG|DUTY-DONE" pd_probe.out | head -2
grep -aq "DUTY-DONE" pd_probe.out || { echo "POWER-ABORT: la sonda non e' arrivata in fondo"; tail -20 pd_probe.out; exit 1; }
EST=$(python -c "
tp=${TPROBE}; ip=${P3_PROBE_IDLE}; ir=${IDLECYC}
# tempo della sonda = costo fisso (elaborazione + fase attiva) + ip * costo_per_clock_idle.
# Non conoscendo il fisso, si usa il MAGGIORANTE: tutto il tempo attribuito all'idle -> stima PESSIMISTA.
per=tp/float(ip); print('%d %.6f' % (round(per*ir), per))
")
TFULL="${EST%% *}"; PERCLK="${EST##* }"
echo "  sonda: ${TPROBE} s per ${P3_PROBE_IDLE} clock  ->  ${PERCLK} s/clock (maggiorante)"
echo "  P3 completa (${IDLECYC} clock) STIMATA: ${TFULL} s = $((TFULL/60)) min   [budget ${P3_BUDGET_S} s]"
if [ "$TFULL" -gt "$P3_BUDGET_S" ]; then
  echo "POWER-STOP: la P3 al duty REALE supera il budget dichiarato."
  echo "  misurato: ${PERCLK} s per clock di idle · servono ${IDLECYC} clock · stima $((TFULL/60)) min contro $((P3_BUDGET_S/60)) min"
  echo "  NON riduco il perimetro di mia iniziativa: il duty NON composto e' il punto stesso di questo passo"
  echo "  (la composizione lineare fu INVALIDATA in T6b/M3.4). Opzioni, da decidere:"
  echo "    a) alzare il budget:  P3_BUDGET_S=<secondi> bash run_power.sh $FCLK $CLKHALF duty"
  echo "    b) misurare a duty RIDOTTO e dichiararlo tale (NON e' il duty reale)"
  echo "    c) rinunciare a P3 e riportare solo attiva e idle, dichiarando che il duty non e' misurato"
  exit 2
fi
echo "  entro budget: procedo con la P3 completa  [$(date +%H:%M:%S)]"
duty_build "$IDLECYC"
SFD="$WORK/saif_duty_g1.saif"; rm -f "$SFD"
# FINESTRA SAIF = TUTTA la simulazione (apertura a ~t0), NON dopo un preludio a tempo fisso.
# T6b usava `run 2 us` prima di aprire: a 40 MHz sono 80 clock, mentre il banco raggiunge DUTY-READY
# a ~25 (reset 20 + le scritture AXI) -- quel preludio taglierebbe ~55 clock DENTRO la fase attiva,
# cioe' proprio la parte che consuma. Aprendo da subito si includono invece i ~20 clock di reset su
# 4.000.000 (0,0005%): trascurabili, e nulla dell'attivo viene perso.
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
fi

# ---------- P4: da SAIF a watt ----------
if [ "$STAGE" = "all" ] || [ "$STAGE" = "report" ]; then
echo "=== P4 · report_power su tutti i SAIF  [$(date +%H:%M:%S)] ==="
SAIFS=$(ls "$WORK"/saif_*.saif 2>/dev/null)
[ -n "$SAIFS" ] || { echo "POWER-ABORT: nessun SAIF da elaborare"; exit 1; }
"$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog -source "$HERE/power_report.tcl" \
  -tclargs "$ROOT/np.xpr" "$OUT" $SAIFS 2>&1 | grep -E "^(PW|=====|ERROR:)"

# La copertura SAIF e la confidenza vanno NEL numero, non in nota a pie' di pagina.
echo "=== copertura e confidenza (dichiarate accanto ai watt) ==="
grep -h "Design Nets Matched" "$OUT"/power_*.rpt 2>/dev/null | sort -u | head -3
grep -hA3 "Confidence Level" "$OUT"/power_*.rpt 2>/dev/null | head -6
fi
echo "=== FINE (stadio: $STAGE)  [$(date +%H:%M:%S)] ==="
