"""build_harness_snn_report.py — REPORT Fase B2.0 / T6 · Harness_SNN — .md + .pdf da sorgente unica.

Validazione a livello RTL (T6a) e caratterizzazione hardware (T6b) del blocco SNN estimatore
`Donatello_Tier@BALANCED` destinato all'FPGA: il VHDL generato provato bit-esatto rispetto al blocco su
tutto il dataset, il sistema completo (Tier + wrapper AXI4-Lite + Zynq PS7) implementato, misurato in
clock/risorse/potenza, e portato a bitstream.

Grounding — nessun numero e' inventato; ogni costante di questo file cita la sua fonte:
  * T6a  : FaseB2.0/Harness_SNN/results/RESULTS.md            (generato da run_harness_snn)
  * probe: FaseB2.0/Harness_SNN/results/PROBES_T6B.md         (run_probes_t6b.sh)
  * T6b  : FaseB2.0/Harness_SNN/results/RESULTS_HW.md         + i 37 report Vivado grezzi in results/
  * log  : results/impl_sweep.log · m3_power.log · m3_duty_real.log · netlist_func.log ·
           axi_cosim_full60.log · m4_bitstream.log
  * doc  : document/HDL_PHASE.md §6 (stato) e §9 (gotcha/lezioni)
  * spec : docs/superpowers/specs/2026-07-28-b2.0-t6-harness-snn-design.md (varieta' del dataset:
           60/60 parametri distinti, 9 combinazioni scenario|profilo, corr. media 0.032 fra i v_l)
I cancelli sono deterministici (esito 0/N). Le grandezze non misurabili con questo flusso sono marcate
come STIMA nel testo e nelle figure, mai presentate come misura.

Uso:    python scripts/build_harness_snn_report.py
Output: report/B2_0_HARNESS_SNN_REPORT.{md,pdf}  +  report/figures_harness_snn/*
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# --- CONFIG -----------------------------------------------------------------
HERE       = os.path.dirname(os.path.abspath(__file__))
ROOT       = os.path.dirname(HERE)
OUTDIR     = os.path.join(ROOT, 'report')
FIGDIR     = os.path.join(OUTDIR, 'figures_harness_snn')
DOC_NAME   = 'B2_0_HARNESS_SNN_REPORT'
DOC_TITLE  = 'CF_FSNN — Harness_SNN: validazione RTL e caratterizzazione hardware (Fase B2.0 · T6)'
FOOTER_TEXT = 'CF_FSNN — Fase B2.0 · T6 Harness_SNN · SNN Donatello_Tier@BALANCED su Zynq-7020'
EQ_DPI     = 200
os.makedirs(FIGDIR, exist_ok=True)

# ============================================================================
# GROUNDING — costanti ancorate agli artefatti (fonte indicata per ciascuna)
# ============================================================================
# --- DUT (RESULTS.md §Configurazione misurata) ------------------------------
DUT_NAME, DUT_TIER, DUT_NFRAC = 'Donatello_Tier', 'BALANCED', 13
IN_BITS, IN_FRAC   = 32, 20          # ingressi fisici: fixdt(1,32,20)  (sfix32_En20 nell'ENTITY)
PAR_BITS, PAR_FRAC = 21, 13          # 5 parametri IDM: Q7.13           (sfix21_En13 nell'ENTITY)
LAT_BLK  = 364                       # latenza del blocco, MISURATA (tier_block_params: edge-trigger)
HOLD_RTL = 500                       # hold del TB di T6a (> latenza)
LAT_WRAP = 371                       # attesa del wrapper AXI = 370+1 (365 misurati + margine)
LAT_CMT  = 365                       # uscita valida a commit+365 (probe di timing: 446->811, 852->1217)

# --- T6a: cancelli e metriche (RESULTS.md) ----------------------------------
T6A_N      = 300000                  # 60 traj x 1000 control-step x 5 param
T6A_MIS    = 0
T6A_MIN    = 74.6                    # runtime totale [min]
T6A_GOLDEN = 7.3                     # golden 60 traj [min] (cache)
# accuratezza di stima: max / p99 per parametro (RESULTS.md §Accuratezza)
EST = {'v0': (15.01, 13.80), 'T': (1.125, 0.9127), 's0': (0.9368, 0.8435),
       'a': (0.9908, 0.8920), 'b': (1.003, 0.8670)}

# --- probe T6b (PROBES_T6B.md) ---------------------------------------------
P1_CE_HI, P1_CE_TOT = 1500, 1500     # ce_out alto 1500/1500 cicli => clock-enable, NON un done
# varieta' del dataset - fonte: docs/superpowers/specs/2026-07-28-b2.0-t6-harness-snn-design.md
DS_CORR = 0.032                      # correlazione media fra le forme d'onda v_l delle 60 traiettorie
# inferenza spuria al rilascio del reset (RESULTS_HW.md M1: 'uscita a cyc 379 con reset a 16')
SPUR_CYC, SPUR_RST = 379, 16         # 379-16 = 363 ~= LAT_BLK (364): 1 ciclo di convenzione di campionamento
P1_CHG = (364, 865, 1365)            # cicli in cui cambiano le uscite (passo 500 = HOLD)
P2_OOC = (4461, 2354, 52, 1)         # LUT, FF, DSP, BRAM  post-synth OOC del wrapper+Tier
BOARD  = 'www.digilentinc.com:pynq-z1:part0:1.0'
PS7_IP = 'xilinx.com:ip:processing_system7:5.5'

# --- T6b M1: cosim AXI (RESULTS_HW.md §M1 · axi_cosim_full60.log) ----------
AXI_N, AXI_MIS = 300000, 0           # identico gating OFF e ON
AXI_MIN_OFF, AXI_MIN_ON = 46, 51     # [min]
SYNC_OBS, SYNC_EXP = 59797, 60000    # scarto = 203 control-step con ingressi bit-identici
SYNC_REP, SYNC_TRAJ, SYNC_WORST = 203, 6, 79   # ripetizioni, traiettorie coinvolte, peggiore (traj 2)

# --- T6b M2: sweep FCLK (impl_sweep.log) -----------------------------------
# FCLK [MHz], WNS [ns], LUT ; FF/DSP/BRAM costanti = 3199/52/1 su tutti i punti
SWEEP = [(30, 10.892, 4474), (40, 2.626, 4472), (50, 0.335, 4476),
         (52, 0.358, 4473), (55, -0.345, 4524), (60, -0.414, 4613)]
FF_ALL, DSP_ALL, BRAM_ALL = 3199, 52, 1
FCLK_DEP   = 52                      # il piu' alto fra i testati che chiude
WNS_DEP    = 0.358
DELAY_MIN  = 17.081                  # ritardo minimo ottenuto (vincolo 60 MHz) -> limite del datapath
FMAX_PATH  = 1000.0 / DELAY_MIN      # = 58.55 MHz
T_STEP     = 0.1                     # control-step richiesto [s] (unico requisito temporale)

# --- T6b M2.3: netlist post-place&route (netlist_func.log) ------------------
NL_N, NL_MIS, NL_TRAJ = 15000, 0, 3  # 3 traj x 1000 control-step x 5 param, funcsim, gating ON
NL_WNS_OOC = 0.355                   # WNS dell'impl OOC a 52 MHz
NL_MIN_TRAJ = 22                     # costo misurato [min/traiettoria]  (netlist_func.log: 21m52s/20m41s/22m38s)
NL_H_ALL   = NL_MIN_TRAJ * 60 / 60.0 # = 22 h per l'intero dataset (60 traj, nessun parallelismo)
# rapporto di costo netlist/comportamentale, dai tempi MISURATI:
#   comportamentale = 46 min / 60 traj = 0.77 min/traj (axi_cosim_full60.log, gating OFF)
CB_MIN_TRAJ = AXI_MIN_OFF / 60.0
NL_SLOWDOWN = NL_MIN_TRAJ / CB_MIN_TRAJ   # ~= 29x

# --- T6b M3: potenza (m3_power.log · power_*.rpt) --------------------------
# 9 workload reali (uno per combinazione scenario|profilo) + 1 worst sintetico
WL = [(1, 1, 'mixed|stop_and_go', 0.042), (2, 3, 'launch|launch', 0.045),
      (3, 4, 'urban|sinusoidal', 0.043), (4, 5, 'freeflow|free', 0.044),
      (5, 6, 'highway|sinusoidal', 0.044), (6, 8, 'mixed|sinusoidal', 0.043),
      (7, 9, 'truck|constant', 0.043), (8, 15, 'highway|constant', 0.044),
      (9, 39, 'urban|stop_and_go', 0.042)]
WL_WORST = 0.041                     # worst sintetico: il PIU' BASSO => non e' un limite superiore
P_STATIC = 0.103                     # statica del device [W] (pavimento del chip)
P_IDLE   = 0.008                     # dinamica in idle, clock libero [W] (finestra convergente)
# breakdown [W]: (Clocks, SliceLogic, Signals, BRAM, DSP)  — '<0.001' reso come 0.0005
BD_IDLE  = (0.007, 0.0005, 0.0005, 0.001, 0.0005)
BD_ACT   = (0.008, 0.009, 0.012, 0.002, 0.010)      # wl1
BD_MIX   = (0.007, 0.001, 0.002, 0.001, 0.004)      # duty 3.85% (cross-check)
BD_REAL  = (0.007, 0.0005, 0.0005, 0.001, 0.0005)   # duty reale
# serie di convergenza: (duty [%], cicli di idle, dinamica [W])
DUTY = [(3.85, 10000, 0.015), (0.37, 100000, 0.010), (0.0080, 5199584, 0.009)]
P_DYN_REAL = 0.009                   # dinamica al duty reale [W]  -> energia = P * T_STEP
IDLE_WIN   = (200, 1000, 5000)       # finestre del probe di convergenza: valori identici
# cross-check della composizione (invalidata)
CC_MEAS, CC_COMP, CC_DUTY = 0.015, 0.0094, 3.85
# clock gating: conteggi di commutazione del clock del Tier nel SAIF
TC_UNGATED, TC_GATED = 400, 0
GAIN_LO, GAIN_HI = 2, 4              # STIMA del guadagno sulla dinamica (non misura)
# copertura del SAIF - IDENTICA su tutti i 18 report (power_*.rpt §1.3 'Design Nets Matched')
SAIF_NETS, SAIF_TOT = 6906, 12380
SAIF_COV = 100.0 * SAIF_NETS / SAIF_TOT              # = 55.8 % -> il tool riporta 56 %
# soglia che fa scattare la confidenza 'High' sui nodi interni (power_*.rpt §1.3): >25 %
SAIF_CONF_THR = 25
# statica: NON dal SAIF, ma dal modello di dispositivo alle condizioni dichiarate in testa al report
STAT_PROC, STAT_TJ, STAT_GRADE = 'typical', 26.3, 'commercial'
# perimetro dell'implementazione usata per netlist e potenza (RESULTS_HW.md M2.3/M3)
IMPL_SCOPE = 'OOC (tier_axi_lite + Donatello_Tier)'   # NON l'intero block design: il PS7 richiede il suo BFM/VIP

# --- T6b M4/M5: bitstream e riproducibilita' (m4_bitstream.log) -------------
BIT_WNS = 0.358                      # identico allo sweep a 52 MHz => il flashato e' il caratterizzato
BIT_SZ, HWH_SZ, XSA_SZ = 4045766, 138152, 1148507      # byte
VHDL_MD5 = 'dea2709dec57416cde9a22762d17afe0'
VHDL_MD5_ALT = '307c5e6c6ffd84adbd24946236d926fd'      # con una riga aggiunta a DEC.vhd (contro-prova)

PAL = {'blu': '#26527a', 'blunav': '#1a3c6e', 'verde': '#2e7d4f', 'mattone': '#b5522a',
       'grigio': '#8a94a0', 'ambra': '#c9992b', 'rosso': '#b5384d', 'viola': '#6b4a8a'}

# --- Normalizzazione tipografica (accenti veri) -----------------------------
import re as _re
_TRUNC_MAP = {
    "fedelta'": 'fedeltà', "idoneita'": 'idoneità', "modalita'": 'modalità', "attivita'": 'attività',
    "capacita'": 'capacità', "entita'": 'entità', "verita'": 'verità', "proprieta'": 'proprietà',
    "parita'": 'parità', "sparsita'": 'sparsità', "qualita'": 'qualità', "unita'": 'unità',
    "possibilita'": 'possibilità', "difficolta'": 'difficoltà', "identita'": 'identità',
    "linearita'": 'linearità', "riproducibilita'": 'riproducibilità', "sensibilita'": 'sensibilità',
    "probabilita'": 'probabilità', "granularita'": 'granularità', "esaustivita'": 'esaustività',
    "perche'": 'perché', "poiche'": 'poiché', "anziche'": 'anziché', "pressoche'": 'pressoché',
    "finche'": 'finché', "affinche'": 'affinché', "cioe'": 'cioè', "piu'": 'più', "gia'": 'già',
    "puo'": 'può', "cosi'": 'così', "percio'": 'perciò', "cio'": 'ciò', "bensi'": 'bensì',
    "ne'": 'né', "e'": 'è',
}
def norm_it(s):
    s = str(s)
    for a, b in _TRUNC_MAP.items():
        for aa, bb in ((a, b), (a[:1].upper() + a[1:], b[:1].upper() + b[1:])):
            if aa.rstrip("'").lower() in ('e', 'ne'):
                s = _re.sub(r"\b" + _re.escape(aa) + r"(?=[\s,.;:)]|$)", bb, s)
            else:
                s = _re.sub(r"\b" + _re.escape(aa), bb, s)
    return s

# --- EQUAZIONI: mathtext -> PNG ---------------------------------------------
def fig_eq(name, lines, fs=11, color='#12233a'):
    n = len(lines)
    fig = plt.figure(figsize=(9.2, 0.52 * n + 0.22))
    for i, ln in enumerate(lines):
        fig.text(0.5, 1.0 - (i + 0.5) / n, '$' + ln + '$', ha='center', va='center', fontsize=fs, color=color)
    p = os.path.join(FIGDIR, name)
    fig.savefig(p, dpi=EQ_DPI, bbox_inches='tight', pad_inches=0.08, facecolor='white')
    plt.close(fig); return p

def _style(ax):
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.tick_params(labelsize=8.5); ax.title.set_fontsize(9.5)

# ============================================================================
# FIGURE DATI
# ============================================================================
def fig_gates():
    """Copertura dei cancelli bit-exact: confronti eseguiti, tutti a 0 disallineamenti."""
    names = ['T6-EXACT\nRTL vs blocco\n(60 traj)', 'AXI-COSIM\nPS vs blocco\n(60 traj, gating OFF)',
             'AXI-COSIM\nPS vs blocco\n(60 traj, gating ON)', 'NETLIST-PAR\npost-route vs blocco\n(3 traj)']
    vals = [T6A_N, AXI_N, AXI_N, NL_N]
    cols = [PAL['blu'], PAL['verde'], PAL['verde'], PAL['viola']]
    fig, ax = plt.subplots(figsize=(8.4, 3.0))
    bars = ax.bar(names, vals, color=cols)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v * 1.06, f'{v:,}'.replace(',', ' ') + '\n0 disallineamenti',
                ha='center', fontsize=8.0)
    ax.set_yscale('log'); ax.set_ylim(5e3, 1.2e6)
    ax.set_ylabel('confronti bit-exact (scala log)', fontsize=9); _style(ax)
    ax.set_title('Copertura dei cancelli: ogni confronto contro il blocco di riferimento, zero disallineamenti',
                 fontsize=9.3)
    p = os.path.join(FIGDIR, 'gates.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_fclk():
    """Sweep FCLK: WNS (chi chiude) e ritardo ottenuto (il metodo dello slack minimo)."""
    f = [s[0] for s in SWEEP]; wns = [s[1] for s in SWEEP]; lut = [s[2] for s in SWEEP]
    delay = [1000.0 / fi - wi for fi, wi in zip(f, wns)]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.6, 3.1))
    cols = [PAL['verde'] if w >= 0 else PAL['rosso'] for w in wns]
    a1.bar([str(x) for x in f], wns, color=cols)
    a1.axhline(0, color='#33455a', lw=1.0)
    for i, w in enumerate(wns):
        a1.text(i, w + (0.6 if w >= 0 else -1.3), f'{w:+.3f}', ha='center', fontsize=8.0)
    a1.set_xlabel('FCLK richiesto [MHz]', fontsize=9); a1.set_ylabel('WNS [ns]', fontsize=9)
    a1.set_ylim(-2.2, 12.5); _style(a1)
    a1.set_title(f'Chiude fino a {FCLK_DEP} MHz (WNS {WNS_DEP:+.3f} ns)', fontsize=9.3)
    a2.plot(f, delay, 'o-', color=PAL['blu'], lw=1.6, ms=5)
    for fi, di in zip(f, delay):
        a2.annotate(f'{di:.2f}', (fi, di), textcoords='offset points', xytext=(0, 7), ha='center', fontsize=7.8)
    a2.axhline(DELAY_MIN, color=PAL['mattone'], ls='--', lw=1.0)
    a2.text(31, DELAY_MIN - 0.9, f'ritardo minimo {DELAY_MIN:.2f} ns  →  {FMAX_PATH:.1f} MHz',
            color=PAL['mattone'], fontsize=7.8)
    a2.set_xlabel('vincolo: FCLK richiesto [MHz]', fontsize=9)
    a2.set_ylabel('ritardo del cammino critico [ns]', fontsize=9); _style(a2)
    a2.set_title('Stringendo il vincolo il ritardo scende:\nil limite NON si legge al crossover WNS=0', fontsize=9.3)
    p = os.path.join(FIGDIR, 'fclk.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_duty():
    """Convergenza della potenza dinamica al ridursi del duty cycle verso il valore di idle."""
    d = [x[0] for x in DUTY]; p = [x[2] for x in DUTY]
    fig, ax = plt.subplots(figsize=(8.2, 3.0))
    ax.semilogx(d, p, 'o-', color=PAL['blu'], lw=1.8, ms=7, label='dinamica misurata')
    ax.axhline(P_IDLE, color=PAL['verde'], ls='--', lw=1.2, label=f'idle puro ({P_IDLE*1000:.0f} mW)')
    for di, pi in zip(d, p):
        ax.annotate(f'{pi*1000:.0f} mW', (di, pi), textcoords='offset points', xytext=(0, 9),
                    ha='center', fontsize=8.4)
    ax.annotate('duty REALE\n(control-step 0,1 s)', (d[-1], p[-1]), textcoords='offset points',
                xytext=(24, -20), fontsize=8.0, color=PAL['mattone'],
                arrowprops=dict(arrowstyle='->', color=PAL['mattone'], lw=0.9))
    ax.set_xlabel('duty cycle [%] — scala log', fontsize=9)
    ax.set_ylabel('potenza dinamica [W]', fontsize=9)
    ax.set_ylim(0.006, 0.017); ax.invert_xaxis(); _style(ax)
    ax.legend(fontsize=8, frameon=False, loc='upper left')
    ax.set_title('Al ridursi del duty la dinamica converge al valore di idle: al control-step vero\n'
                 'la fase attiva è energeticamente trascurabile', fontsize=9.3)
    p_ = os.path.join(FIGDIR, 'duty.png'); fig.savefig(p_, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p_

def fig_workloads():
    """Potenza attiva per i 9 workload reali + il worst sintetico (che NON e' un limite superiore)."""
    lbl = [f'wl{i}\n{n.replace("|", chr(10))}' for i, _, n, _ in WL] + ['wl10\nworst\nsintetico']
    val = [v for *_, v in WL] + [WL_WORST]
    cols = [PAL['blu']] * len(WL) + [PAL['rosso']]
    fig, ax = plt.subplots(figsize=(8.6, 3.5))
    bars = ax.bar(range(len(val)), val, color=cols)
    for i, (b, v) in enumerate(zip(bars, val)):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.0006, f'{v*1000:.0f}', ha='center', fontsize=8.0)
    mx = max(v for *_, v in WL)
    ax.axhline(mx, color=PAL['ambra'], ls='--', lw=1.0)
    ax.text(len(val) - 0.4, mx + 0.0011, f'max osservato {mx*1000:.0f} mW', color=PAL['ambra'],
            fontsize=7.8, ha='right')
    ax.set_xticks(range(len(val)))
    ax.set_xticklabels(lbl, fontsize=7.0, rotation=38, ha='right', rotation_mode='anchor')
    ax.set_ylabel('potenza dinamica, fase attiva [W]', fontsize=9)
    ax.set_ylim(0, 0.052); _style(ax)
    ax.set_title('Fase attiva: dispersione ~7 % fra i 9 regimi di guida.\n'
                 'Il worst sintetico (rosso) risulta il PIÙ BASSO: non è un limite superiore valido', fontsize=9.3)
    p = os.path.join(FIGDIR, 'workloads.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_gating():
    """Il meccanismo dice il contrario del sommario: clock fermo (SAIF) vs potenza invariata (report)."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.6, 3.0))
    a1.bar(['gating OFF', 'gating ON'], [TC_UNGATED, TC_GATED], color=[PAL['grigio'], PAL['verde']])
    a1.text(0, TC_UNGATED + 18, f'{TC_UNGATED}', ha='center', fontsize=9)
    a1.text(1, 14, f'{TC_GATED}', ha='center', fontsize=9, color=PAL['verde'])
    a1.set_ylabel('commutazioni del clock del Tier (SAIF, TC)', fontsize=9)
    a1.set_ylim(0, TC_UNGATED * 1.25); _style(a1)
    a1.set_title('MECCANISMO — il clock si ferma davvero', fontsize=9.3, color=PAL['verde'])
    a2.bar(['gating OFF', 'gating ON'], [P_IDLE, P_IDLE], color=[PAL['grigio'], PAL['grigio']])
    for i in (0, 1):
        a2.text(i, P_IDLE + 0.0004, f'{P_IDLE*1000:.0f} mW', ha='center', fontsize=9)
    a2.set_ylabel('dinamica in idle secondo report_power [W]', fontsize=9)
    a2.set_ylim(0, 0.012); _style(a2)
    a2.set_title('SOMMARIO — identico: lo strumento NON lo vede', fontsize=9.3, color=PAL['rosso'])
    p = os.path.join(FIGDIR, 'gating.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_energy():
    """Energia per control-step: dinamica (nostro design) vs statica (pavimento del chip)."""
    e_dyn = P_DYN_REAL * T_STEP * 1000.0      # mJ
    e_sta = P_STATIC * T_STEP * 1000.0        # mJ
    e_clk = BD_REAL[0] * T_STEP * 1000.0      # mJ (quota clock tree della dinamica)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.6, 3.0), gridspec_kw={'width_ratios': [1, 1.1]})
    a1.bar(['dinamica\n(il nostro design)', 'statica\n(pavimento del chip)'], [e_dyn, e_sta],
           color=[PAL['blu'], PAL['grigio']])
    for i, v in enumerate([e_dyn, e_sta]):
        a1.text(i, v + 0.25, f'{v:.1f} mJ', ha='center', fontsize=9)
    a1.set_ylabel('energia per control-step (0,1 s) [mJ]', fontsize=9)
    a1.set_ylim(0, e_sta * 1.25); _style(a1)
    a1.set_title('Le due voci NON vanno sommate\nsenza dirlo', fontsize=9.3)
    comp = ['Clocks', 'Slice Logic', 'Signals', 'BRAM', 'DSP']
    vals = [x * T_STEP * 1000.0 for x in BD_REAL]
    a2.barh(comp[::-1], vals[::-1], color=[PAL['grigio'], PAL['grigio'], PAL['grigio'],
                                           PAL['grigio'], PAL['ambra']][::-1])
    for i, v in enumerate(vals[::-1]):
        a2.text(v + 0.012, i, f'{v:.2f}', va='center', fontsize=8.2)
    a2.set_xlabel('energia per control-step [mJ]', fontsize=9); a2.set_xlim(0, 0.95); _style(a2)
    a2.set_title(f'Dentro la dinamica: il clock tree è il {100*e_clk/e_dyn:.0f} %\n'
                 '(è la quota che il clock gating aggredisce)', fontsize=9.3)
    p = os.path.join(FIGDIR, 'energy.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_system():
    """Schema del sistema: PS7 <-> wrapper AXI4-Lite <-> Tier, con commit sincrono e done da contatore."""
    fig, ax = plt.subplots(figsize=(8.6, 3.1)); ax.axis('off'); ax.set_xlim(0, 10.4); ax.set_ylim(0, 5.2)
    def box(x, y, w, h, text, col, fs=8.3):
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.05',
                     fc=col, ec='#33455a', lw=1.0))
        ax.text(x + w / 2, y + h / 2, text, ha='center', va='center', fontsize=fs, color='white')
    box(0.2, 2.9, 2.5, 1.5, 'Zynq PS7\n(board preset\nPYNQ-Z1)', PAL['grigio'])
    box(3.3, 2.9, 3.3, 1.5, 'wrapper AXI4-Lite\nbuffer + COMMIT sincrono\ndone da CONTATORE (371 clk)\nBUFGCE: clock gating', PAL['blu'], 7.8)
    box(7.2, 2.9, 3.0, 1.5, f'{DUT_NAME}\n@{DUT_TIER}, nfrac {DUT_NFRAC}\n(SNN estimatrice)', PAL['verde'])
    ax.annotate('', xy=(3.3, 3.9), xytext=(2.7, 3.9), arrowprops=dict(arrowstyle='-|>', color='#33455a', lw=1.4))
    ax.text(3.0, 4.15, 'AXI', ha='center', fontsize=7.5, color='#33455a')
    ax.annotate('', xy=(7.2, 4.05), xytext=(6.6, 4.05), arrowprops=dict(arrowstyle='-|>', color='#33455a', lw=1.3))
    ax.text(6.9, 4.3, 's,v,dv,v_l\n32 b', ha='center', fontsize=6.8, color='#33455a')
    ax.annotate('', xy=(6.6, 3.2), xytext=(7.2, 3.2), arrowprops=dict(arrowstyle='-|>', color=PAL['mattone'], lw=1.3))
    ax.text(6.9, 2.72, '5 param\nQ7.13', ha='center', fontsize=6.8, color=PAL['mattone'])
    box(1.4, 0.6, 7.6, 1.5,
        'Perché il wrapper non è banale:  ce_out del blocco è un CLOCK-ENABLE (alto 1500/1500 cicli), non un done →\n'
        'il done si genera con un contatore tarato sulla latenza MISURATA;  gli ingressi devono cambiare SINCRONI\n'
        '(scritti uno alla volta lancerebbero inferenze su dati parziali);  il blocco resta in reset fino al 1° commit\n'
        '(altrimenti all\'uscita dal reset parte un\'inferenza spuria che avanza lo stato della rete)', PAL['blunav'], 7.0)
    p = os.path.join(FIGDIR, 'system.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

# ============================================================================
# CONTENUTO
# ============================================================================
def build_doc():
    D = []; A = D.append
    e_dyn = P_DYN_REAL * T_STEP * 1000.0
    e_sta = P_STATIC * T_STEP * 1000.0
    t_inf_us = LAT_WRAP / (FCLK_DEP * 1e6) * 1e6
    margin = T_STEP / (t_inf_us * 1e-6)
    # arrotondato al migliaio: le cifre oltre non sono significative (dipendono dall'arrotondamento
    # di t_inf) e citarle darebbe una falsa precisione
    margin_r = round(margin, -3)
    duty_pc = 100.0 * (t_inf_us * 1e-6) / T_STEP

    A(('cover', {
        'title': DOC_TITLE,
        'subtitle': 'Il VHDL generato della SNN estimatrice provato bit-esatto rispetto al blocco su tutto '
                    'il dataset, e il sistema completo — rete, wrapper AXI4-Lite e Zynq PS7 — implementato, '
                    'misurato in clock, risorse ed energia, e portato a bitstream.',
        'meta': [
            'Oggetto: blocco %s @%s (nfrac %d), la SNN che stima i cinque parametri IDM '
            'dagli stati di car-following.' % (DUT_NAME, DUT_TIER, DUT_NFRAC),
            'Livelli di fedeltà: simulazione RTL e di netlist post-place&route in Vivado xsim; '
            'sintesi e implementazione reali su xc7z020; potenza da attività di commutazione registrata (SAIF). '
            'NON è una misura su silicio — quella è la Fase C.',
            'Grounding: ogni numero proviene dagli artefatti di FaseB2.0/Harness_SNN/results/ '
            '(RESULTS.md, RESULTS_HW.md, PROBES_T6B.md, i log di esecuzione e i report Vivado grezzi); '
            'i fatti sulla varietà del dataset provengono dalla spec di progetto del banco. I cancelli sono '
            'deterministici (esito 0/N); le grandezze non misurabili con questo flusso sono marcate come STIMA.',
            'Riproducibilità: bash FaseB2.0/Harness_SNN/hw/run_harness_snn_hw.sh [stadio] — un comando per '
            'stadio, con cancello di provenienza del DUT.',
        ],
    }))
    A(('toc', 'Sommario'))

    # ---------------------------------------------------------------- 1
    A(('h1', '1. Sintesi'))
    A(('p', 'Questo documento riporta la validazione e la caratterizzazione della **rete neurale spiking '
            'estimatrice** destinata all\'FPGA: il blocco **%s @%s**, che dai quattro stati di car-following '
            '(distanza, velocità propria, velocità relativa, velocità del leader) produce i **cinque parametri '
            'del modello IDM**. Il perimetro è la rete da sola; il controllore completo, che dai parametri '
            'ricava l\'accelerazione, è oggetto di un documento gemello.' % (DUT_NAME, DUT_TIER)))
    A(('p', 'La domanda a cui si risponde è duplice. Primo: **il codice RTL generato si comporta come il '
            'blocco di riferimento?** Secondo: **cosa costa in hardware** — quanto clock regge, quante risorse '
            'occupa, quanta energia consuma nel funzionamento reale. La prima domanda è chiusa con confronti '
            'bit-esatti su tutto il dataset; la seconda con sintesi e implementazione reali, e con misure di '
            'potenza ricavate dall\'attività di commutazione registrata in simulazione.'))
    A(('img', (fig_gates(), 'Copertura dei cancelli di equivalenza. Ogni barra è un confronto bit-esatto contro '
                            'il blocco di riferimento: il VHDL simulato in RTL, i parametri letti dal processore '
                            'attraverso il bus AXI nelle due configurazioni di clock gating, e la netlist dopo '
                            'place&route. In tutti i casi zero disallineamenti. Scala logaritmica.')))
    A(('p', 'Esito, in breve: **%s disallineamenti su %s confronti** fra il VHDL e il blocco su tutte le 60 '
            'traiettorie del dataset; **%s su %s** fra i parametri letti dal processore via AXI e il blocco, '
            'nelle due configurazioni di clock gating; **%s su %s** fra la netlist post-place&route e il blocco, '
            'su %d traiettorie. I cancelli di equivalenza RTL, di sistema e di provenienza del codice sono provati '
            '**sensibili** — alterando un valore di riferimento di un solo bit meno significativo, o una riga del '
            'VHDL, il confronto fallisce; per i restanti la sensibilità non è stata dimostrata (§3.3).'
            % (T6A_MIS, f'{T6A_N:,}'.replace(',', ' '), AXI_MIS, f'{AXI_N:,}'.replace(',', ' '),
               NL_MIS, f'{NL_N:,}'.replace(',', ' '), NL_TRAJ)))
    A(('table', (['Grandezza', 'Valore', 'Natura'], [
        ['Equivalenza RTL e sistema-AXI vs blocco (60 traj)', '0 disallineamenti', 'misurato'],
        ['Equivalenza netlist post-route vs blocco (%d traj)' % NL_TRAJ, '0 disallineamenti', 'misurato'],
        ['Frequenza di clock deployabile', f'{FCLK_DEP} MHz (WNS {WNS_DEP:+.3f} ns)', 'misurato'],
        ['Limite del cammino critico', f'{FMAX_PATH:.1f} MHz', 'derivato (da WNS a vincolo stretto)'],
        ['Risorse post-place&route', f'{SWEEP[3][2]} LUT · {FF_ALL} FF · {DSP_ALL} DSP · {BRAM_ALL} BRAM', 'misurato'],
        ['Tempo di inferenza / margine sul control-step', f'{t_inf_us:.2f} µs / ≈{margin_r:,.0f}×'.replace(',', ' '), 'derivato'],
        ['Energia dinamica per control-step', f'{e_dyn:.1f} mJ', 'misurato al duty reale, gating OFF'],
        ['Energia statica del dispositivo per control-step', f'{e_sta:.1f} mJ',
         f'stima del modello di dispositivo ({STAT_PROC}, Tj {STAT_TJ:.1f} °C)'],
        ['Clock gating: arresto del clock della rete', 'da %d a %d commutazioni' % (TC_UNGATED, TC_GATED), 'misurato'],
        ['Clock gating: guadagno in potenza', f'{GAIN_LO}–{GAIN_HI}× atteso', 'STIMA — non misurabile qui'],
        ['Bitstream PYNQ-Z1', f'prodotto, timing chiuso (WNS {BIT_WNS:+.3f} ns)', 'artefatto'],
    ])))
    A(('callout', 'Tre grandezze **non** sono state ottenute e sono dichiarate come tali: il **guadagno in watt '
                  'del clock gating** (lo strumento di analisi non lo rileva, §8), un **limite superiore** '
                  'validato della potenza attiva (§7.2), e la **simulazione di timing** della netlist (§6.3). '
                  'Nessuna di esse è stata sostituita da una stima presentata come misura. I numeri di potenza '
                  'poggiano su un\'attività registrata che copre il **%.0f %% dei collegamenti** del circuito, '
                  'il resto essendo stimato dallo strumento (§7.1); le implementazioni di netlist e potenza '
                  'hanno perimetro **%s**, non l\'intero sistema (§6.3).' % (SAIF_COV, IMPL_SCOPE)))

    # ---------------------------------------------------------------- 2
    A(('h1', '2. Oggetto, perimetro e catena di fiducia'))
    A(('h2', '2.1 Il blocco sotto esame'))
    A(('p', 'Il dispositivo sotto test è il blocco di libreria **%s** configurato sul livello **%s** con '
            '**%d** bit frazionari interni. Espone un\'interfaccia a **grandezze fisiche**: quattro ingressi in '
            'virgola fissa a %d bit con %d bit frazionari, e cinque uscite a %d bit in formato Q%d.%d. '
            'La normalizzazione degli ingressi avviene **dentro** il blocco, in aritmetica a virgola fissa: '
            'è la configurazione che va effettivamente su FPGA.'
            % (DUT_NAME, DUT_TIER, DUT_NFRAC, IN_BITS, IN_FRAC, PAR_BITS, PAR_BITS - 1 - PAR_FRAC, PAR_FRAC)))
    A(('p', 'Il blocco è **temporizzato a eventi**: una variazione degli ingressi innesca una singola inferenza, '
            'che si completa in **%d cicli di clock** misurati. Non è un circuito combinatorio né a flusso '
            'continuo: questa proprietà governa tutto il progetto del banco di prova e del wrapper.' % LAT_BLK))
    A(('h2', '2.2 Cosa è dentro e cosa è fuori'))
    A(('table', (['Dentro il perimetro', 'Fuori dal perimetro'], [
        ['Equivalenza del VHDL generato rispetto al blocco, su tutto il dataset',
         'Il controllore completo (rete + legge IDM): documento gemello'],
        ['Il sistema deployato: rete + wrapper AXI4-Lite + processore Zynq',
         'Metriche di car-following in anello chiuso: richiedono il controllore'],
        ['Errore di stima dei cinque parametri sulle stesse 60 traiettorie (§4.1)',
         'Qualità della rete come controllore in anello chiuso: documento gemello'],
        ['Clock, risorse post-place&route, energia nel funzionamento reale — su implementazione %s' % IMPL_SCOPE,
         'Implementazione e potenza dell\'intero block design (richiede il modello del processore)'],
        ['Bitstream e handoff per la board', 'Misura su silicio: è la Fase C, su board fisica'],
    ])))
    A(('h2', '2.3 La catena di fiducia: il riferimento è il blocco stesso'))
    A(('p', 'Un confronto bit-esatto vale quanto il riferimento con cui si confronta. Qui il riferimento è '
            '**il blocco stesso**, eseguito nel suo ambiente di modellazione e campionato ciclo per ciclo: '
            'l\'uguaglianza fra RTL e riferimento è quindi, per costruzione, uguaglianza fra RTL e blocco, '
            'senza anelli intermedi da giustificare.'))
    A(('p', 'Questa scelta corregge un errore documentato della fase precedente. Un riferimento software '
            '"veloce" usato in passato **non** coincide con il blocco: se ne discosta dopo alcune decine di '
            'control-step, perché la normalizzazione interna in virgola fissa devia di un bit meno '
            'significativo e perché il blocco pilota il proprio nucleo mantenendo l\'ingresso costante. '
            'Un riferimento sbagliato produce disallineamenti che sembrano difetti del codice generato: '
            'la catena di fiducia va quindi ancorata all\'oggetto reale, non a un suo surrogato.'))
    A(('p', 'Il riferimento è calcolato **una volta sola** e messo in cache, e la **stessa** cache alimenta sia '
            'il confronto bit-esatto sia le metriche di accuratezza. Non è solo un\'economia: garantisce che '
            'prova e numeri riportati si riferiscano agli **stessi identici dati**.'))

    # ---------------------------------------------------------------- 3
    A(('h1', '3. Metodo di verifica'))
    A(('h2', '3.1 Il dataset e il perimetro dei numeri'))
    A(('p', 'Il dataset di prova contiene **60 traiettorie** di car-following, ciascuna di 1000 control-step. '
            'La sua varietà è stata verificata sui dati e non assunta: i parametri-veicolo di riferimento sono '
            '**tutti distinti fra le 60 traiettorie**, gli scenari coprono **nove combinazioni** di contesto e '
            'profilo del veicolo che precede, e le forme d\'onda della velocità del leader risultano fra loro '
            'praticamente scorrelate — la correlazione media fra le velocità del leader è **%.3f**.' % DS_CORR))
    A(('p', 'Il perimetro della prova coincide con il perimetro dei numeri riportati: le **metriche** sono calcolate '
            'sulle **stesse** traiettorie su cui è dimostrata l\'equivalenza. Un sottoinsieme non è mai la base di '
            'una metrica pubblicata: su popolazioni diverse i valori non sono confrontabili e lo scostamento fra '
            'prova e riferimento diventa illeggibile — anche quando è nullo. Resta invece legittimo come '
            '**cancello di conferma**, purché il suo perimetro sia dichiarato accanto al risultato: è il caso del '
            'confronto sulla netlist (§6.3), dove la simulazione a livello di porte costa quasi **trenta volte** '
            'quella comportamentale.'))
    A(('h2', '3.2 Una simulazione per traiettoria'))
    A(('p', 'La rete mantiene uno **stato interno** in memoria su chip. Quello stato viene azzerato '
            'all\'inizializzazione di una simulazione, **non** dal segnale di reset a tempo di esecuzione. '
            'Concatenare più traiettorie in una sola simulazione produrrebbe quindi risultati corretti solo per '
            'la prima: il banco esegue **una simulazione per traiettoria**, compilando una volta e rilanciando '
            'la sola esecuzione. Il costo è trascurabile e il confronto resta valido su tutte.'))
    A(('h2', '3.3 Disciplina dei cancelli'))
    A(('p', 'Ogni cancello è un\'asserzione che **deve poter fallire**. Un cancello che non è mai stato visto '
            'fallire non è un cancello: la prova adottata è l\'alterazione di **un bit meno significativo** in un '
            'valore di riferimento — se il cancello resta verde, non sta misurando nulla.'))
    A(('p', 'La sensibilità è stata dimostrata, con questa prova, per **tre** cancelli: l\'equivalenza RTL, '
            'l\'equivalenza del sistema attraverso il bus, e la provenienza del codice sintetizzato (dove '
            'l\'alterazione è una riga aggiunta a un file VHDL, e la firma cambia di conseguenza). Per i cancelli '
            'sulla netlist, sulla sincronizzazione e sulla trasparenza del clock gating la sensibilità **non** è '
            'stata dimostrata: sono asserzioni sullo stesso meccanismo già provato sensibile a monte, ma questo '
            'resta un argomento di trasferimento, non una prova.'))
    A(('p', 'La stessa disciplina si applica agli **artefatti**: un cancello verifica il file prodotto — '
            'esistenza, dimensione non nulla, firma attesa — e non una riga di diario che ne annuncia '
            'l\'intenzione. Durante questo lavoro un controllo scritto in quel modo ha dichiarato successo tre '
            'volte mentre non veniva prodotto alcun file di attività: da lì si sarebbero generati numeri di '
            'potenza perfettamente plausibili e privi di fondamento.'))

    # ---------------------------------------------------------------- 4
    A(('h1', '4. Validazione a livello RTL'))
    A(('p', 'Il VHDL è generato dal blocco forzando la variante desiderata, così che il codice prodotto sia '
            'esattamente quello del livello e della precisione sotto esame. Un banco di prova pilota gli '
            'ingressi, li mantiene per un intervallo superiore alla latenza, campiona i cinque parametri a '
            'fine intervallo e li confronta con il riferimento.'))
    A(('table', (['Cancello', 'Che cosa dimostra', 'Perimetro', 'Esito'], [
        ['Equivalenza', 'i 5 parametri del VHDL coincidono col blocco',
         f'60 traj × 1000 control-step × 5 parametri = {T6A_N:,}'.replace(',', ' '), f'{T6A_MIS} disallineamenti'],
        ['Latenza', 'la latenza è misurata dal banco, non assunta', 'ogni simulazione',
         f'{LAT_BLK} cicli, costante, < {HOLD_RTL}'],
        ['Formato delle porte', 'le uscite sono interpretate nel formato corretto',
         'implicito nell\'equivalenza', 'coerente'],
        ['Sensibilità', 'il cancello fallisce quando deve', '1 bit alterato', 'rilevato'],
    ])))
    A(('p', 'Il cancello sul **formato delle porte** merita una nota di metodo: non è una verifica separata, ma '
            'una conseguenza dell\'equivalenza. Se il formato delle uscite fosse interpretato male, il '
            'disallineamento sarebbe **sistematico** su ogni control-step; poiché i disallineamenti sono zero, '
            'l\'interpretazione è necessariamente corretta. Dichiararlo esplicitamente evita di contare due '
            'volte la stessa evidenza.'))
    A(('h2', '4.1 Accuratezza di stima dei parametri'))
    A(('p', 'Poiché il codice generato è dimostrato equivalente al blocco, l\'accuratezza del blocco **è** '
            'l\'accuratezza della versione hardware. Le cifre seguenti sono l\'**errore assoluto** fra parametro '
            'stimato e parametro di riferimento del dataset, sulle stesse 60 traiettorie della prova di '
            'equivalenza, riportato come **massimo** e **99° percentile** — cioè la coda, non la mediana. '
            'Ogni riga è nell\'unità della grandezza corrispondente.'))
    A(('table', (['Parametro (unità)', 'errore max', 'errore p99', 'Lettura'], [
        ['v0 — velocità desiderata [m/s]', f'{EST["v0"][0]:.2f}', f'{EST["v0"][1]:.2f}',
         'errore elevato per **identificabilità**, non per difetto del codice'],
        ['T — tempo di reazione desiderato [s]', f'{EST["T"][0]:.3f}', f'{EST["T"][1]:.4f}', 'contenuto'],
        ['s0 — distanza minima [m]', f'{EST["s0"][0]:.4f}', f'{EST["s0"][1]:.4f}', 'contenuto'],
        ['a — accelerazione massima [m/s²]', f'{EST["a"][0]:.4f}', f'{EST["a"][1]:.3f}', 'contenuto'],
        ['b — decelerazione confortevole [m/s²]', f'{EST["b"][0]:.3f}', f'{EST["b"][1]:.3f}', 'contenuto'],
    ])))
    A(('callout', 'L\'errore su **v0** non è un difetto dell\'implementazione: quel parametro è osservabile solo '
                  'quando il veicolo viaggia a flusso libero, cioè in una frazione delle situazioni presenti nel '
                  'dataset. È un limite di **identificabilità** del problema di stima, non della sua realizzazione '
                  'in hardware — e come tale non si corregge con più bit o più cicli di clock. La qualità della '
                  'rete come controllore si valuta in anello chiuso, che è oggetto del documento gemello.'))

    # ---------------------------------------------------------------- 5
    A(('h1', '5. Il sistema hardware'))
    A(('p', 'Per portare la rete su FPGA servono due cose che il blocco da solo non ha: un\'interfaccia verso il '
            'processore e una politica di alimentazione del clock. Il sistema è quindi composto dal blocco, da un '
            'wrapper con bus **AXI4-Lite** e dal processore **Zynq** configurato col preset della board.'))
    A(('img', (fig_system(), 'Architettura del sistema deployato e le tre scelte non banali del wrapper, ciascuna '
                             'derivata da un fatto misurato anziché da un\'assunzione.')))
    A(('h2', '5.1 Tre scelte di progetto, tre fatti misurati'))
    A(('p', '**Il segnale di fine elaborazione non esiste.** Il blocco espone un\'uscita che, per convenzione '
            'del generatore di codice, si potrebbe interpretare come indicatore di completamento. La misura dice '
            'altro: quel segnale è alto in **%d cicli su %d**, cioè è un abilitatore di clock, non un '
            'completamento. Usarlo come tale farebbe leggere al processore parametri **non ancora pronti**. '
            'Il wrapper genera quindi il completamento con un **contatore**, tarato sulla latenza misurata.'
            % (P1_CE_HI, P1_CE_TOT)))
    A(('p', 'La taratura richiede attenzione: le uscite diventano valide a **commit + %d cicli** (misurato su '
            'control-step successivi), e campionare *esattamente* a quel ciclo cattura il valore **precedente**, '
            'perché l\'aggiornamento avviene sullo stesso fronte di clock su cui si campiona. Il wrapper attende '
            'quindi **%d cicli**, con un margine di pochi cicli che non costa nulla: il control-step reale è di '
            '%.1f s, cioè milioni di cicli.' % (LAT_CMT, LAT_WRAP, T_STEP)))
    A(('p', '**Gli ingressi devono cambiare insieme.** Essendo il blocco temporizzato a eventi, scrivere i '
            'quattro ingressi uno alla volta farebbe partire un\'inferenza sul **primo** cambiamento, con dati '
            'parziali. I registri del bus sono perciò un\'area di transito, e un comando di **commit** trasferisce '
            'i quattro valori **contemporaneamente**. Un cancello dedicato conta i fronti del bus interno e '
            'verifica che a ogni commit corrisponda una sola inferenza.'))
    A(('p', '**Il blocco resta in reset fino al primo commit.** Senza questa precauzione, all\'uscita dal reset '
            'gli ingressi passano da indefinito a zero: il rilevatore di fronte interpreta la transizione come '
            'un evento e avvia un\'inferenza **spuria** che avanza lo stato della rete, disallineando tutte le '
            'inferenze successive. La misura lo ha mostrato senza ambiguità — un cambiamento delle uscite '
            'compariva prima del primo commit, a **circa una latenza** dal rilascio del reset (uscita al ciclo '
            '%d, reset rilasciato al ciclo %d, cioè %d cicli: la latenza è %d, e la differenza di un ciclo dipende '
            'dalla convenzione di campionamento). Tenere l\'acceleratore fermo finché il processore non gli '
            'assegna lavoro è anche il comportamento corretto in campo.'
            % (SPUR_CYC, SPUR_RST, SPUR_CYC - SPUR_RST, LAT_BLK)))
    A(('h2', '5.2 Equivalenza del sistema completo'))
    A(('p', 'Un banco che si comporta da processore scrive i quattro ingressi, emette il commit, attende il '
            'completamento e legge i cinque parametri attraverso il bus, confrontandoli con il riferimento. '
            'L\'esito è **%s disallineamenti su %s** confronti, sull\'intero dataset, e **identico nelle due '
            'configurazioni di clock gating**: la gestione del clock non altera un solo bit del risultato.'
            % (AXI_MIS, f'{AXI_N:,}'.replace(',', ' '))))
    A(('h2', '5.3 Un caso limite reale: ingressi ripetuti'))
    A(('p', 'Il cancello sulla sincronia degli ingressi conta **%s** inferenze contro le %s attese. Lo scarto è '
            'stato verificato sul dataset e non giustificato a parole: esattamente **%d** control-step hanno i '
            'quattro ingressi **bit-identici** al precedente, concentrati in **%d** traiettorie su 60 di tipo '
            '"parti e fermati", con un massimo di %d ripetizioni in una singola traiettoria. Su ingressi identici '
            'il rilevatore di fronte non scatta e la rete non ricalcola.'
            % (f'{SYNC_OBS:,}'.replace(',', ' '), f'{SYNC_EXP:,}'.replace(',', ' '),
               SYNC_REP, SYNC_TRAJ, SYNC_WORST)))
    A(('callout', 'In anello aperto il fenomeno è **innocuo**: a ingressi identici corrispondono parametri '
                  'identici, e i valori mantenuti restano quelli corretti — lo dimostra l\'assenza di '
                  'disallineamenti, perché un commit realmente perso produrrebbe valori obsoleti che il confronto '
                  'bit-esatto rileverebbe. In **anello chiuso** la conclusione non si trasferisce: là gli ingressi '
                  'del passo successivo dipendono dall\'uscita, quindi un\'inferenza non rieseguita si propaga. '
                  'È un elemento da verificare nel documento gemello, proprio negli scenari dove il fenomeno si '
                  'concentra.'))

    # ---------------------------------------------------------------- 6
    A(('h1', '6. Clock, risorse e netlist'))
    A(('h2', '6.1 Frequenza: due numeri distinti'))
    A(('p', 'La frequenza di funzionamento è stata determinata con una scansione a punti discreti — il '
            'generatore di clock del processore produce valori quantizzati — implementando il sistema completo '
            'a ciascun punto con parametri di parallelismo **fissi**, così che i risultati siano riproducibili.'))
    A(('img', (fig_eq('eq_fmax.png', [r'f_{\mathrm{limite}}=\frac{1}{T_{\mathrm{vincolo}}-\mathrm{WNS}}',
                                      r'\mathrm{WNS}\geq 0 \;\Rightarrow\; \mathrm{il\;timing\;chiude}']),
               'Frequenza limite del cammino critico. **T_vincolo**: periodo richiesto in fase di implementazione; '
               '**WNS** (worst negative slack): margine peggiore riportato dall\'analisi statica dei tempi — '
               'positivo se il timing chiude. Il ritardo effettivamente ottenuto è la differenza fra i due.')))
    A(('img', (fig_fclk(), 'A sinistra: margine di timing per frequenza richiesta; il sistema chiude fino a '
                           '52 MHz e non chiude a 55. A destra: il ritardo del cammino critico effettivamente '
                           'ottenuto. A frequenze basse lo strumento si arresta intorno ai 22 ns perché il '
                           'margine è ampio e non ha motivo di ottimizzare; stringendo il vincolo il ritardo '
                           'scende fino a 17.08 ns. Il limite del circuito si legge quindi **stringendo**, non '
                           'al punto in cui il margine si annulla.')))
    A(('table', (['Grandezza', 'Valore', 'Significato'], [
        ['Frequenza deployabile', f'{FCLK_DEP} MHz, WNS {WNS_DEP:+.3f} ns',
         'la più alta fra quelle provate che chiude il timing; è quella del bitstream'],
        ['Ritardo minimo ottenuto', f'{DELAY_MIN:.3f} ns',
         'stringendo il vincolo oltre il punto di chiusura'],
        ['Limite del cammino critico', f'{FMAX_PATH:.1f} MHz',
         'grandezza **derivata** dal ritardo minimo; non concedibile dal generatore di clock'],
    ])))
    A(('callout', 'Entrambe le frequenze sono riferite al **sistema completo** con i suoi ingressi e uscite, non '
                  'a un nucleo isolato con i confini registrati. Non sono quindi confrontabili con misure '
                  'fuori contesto dello stesso progetto, che risultano sistematicamente più alte perché non '
                  'includono i cammini di interfaccia.'))
    A(('h2', '6.2 Risorse e margine temporale'))
    A(('p', 'Le risorse sono misurate **dopo place&route**, non stimate: è la differenza che permette di '
            'catturare anche la memoria su chip, assente dalle valutazioni fuori contesto condotte in passato.'))
    A(('table', (['FCLK [MHz]', 'WNS [ns]', 'LUT', 'FF', 'DSP', 'BRAM'],
                 [[str(f), f'{w:+.3f}', str(l), str(FF_ALL), str(DSP_ALL), str(BRAM_ALL)]
                  for f, w, l in SWEEP])))
    A(('p', 'L\'occupazione è **quasi insensibile** al vincolo temporale: fra 40 e 60 MHz le celle logiche '
            'crescono di circa il 3 %, mentre registri, moltiplicatori e memoria restano invariati. Il costo in '
            'area non è quindi la leva su cui agire per guadagnare frequenza.'))
    A(('img', (fig_eq('eq_duty.png', [r'\delta=\frac{t_{\mathrm{inf}}}{T_{\mathrm{step}}}'
                                      r'=\frac{N_{\mathrm{clk}}\,/\,f_{\mathrm{clk}}}{T_{\mathrm{step}}}',
                                      r'\mathrm{margine}=\frac{T_{\mathrm{step}}}{t_{\mathrm{inf}}}']),
               'Ciclo di lavoro e margine temporale. **N_clk**: cicli per inferenza; **f_clk**: frequenza di '
               'funzionamento; **T_step**: periodo del control-step richiesto dall\'applicazione. '
               'Il ciclo di lavoro è la frazione di tempo in cui il circuito calcola.')))
    A(('p', 'Con %d cicli per inferenza a %d MHz, un\'inferenza dura **%.2f µs** contro un control-step '
            'richiesto di **%.1f s**: il margine è di circa **%s volte** e il ciclo di lavoro è dello '
            '**%.4f %%**. Il circuito è dunque fermo per oltre il 99.99 %% del tempo.'
            % (LAT_WRAP, FCLK_DEP, t_inf_us, T_STEP, f'{margin_r:,.0f}'.replace(',', ' '), duty_pc)))
    A(('callout', 'Ne segue una conseguenza di progetto che vale la pena esplicitare: la frequenza massima è una '
                  '**caratterizzazione**, non necessariamente la scelta di funzionamento migliore. Salire in '
                  'frequenza non produce alcun beneficio applicativo — il margine è già di quattro ordini di '
                  'grandezza — mentre aumenta la potenza dinamica in modo proporzionale, soprattutto quella '
                  'spesa nei periodi di inattività se il clock non viene fermato.'))
    A(('h2', '6.3 La netlist dopo place&route'))
    A(('p', 'L\'equivalenza dimostrata a livello RTL non copre ciò che sintesi e place&route possono cambiare: '
            'in particolare l\'inizializzazione degli elementi di memoria, che i modelli comportamentali del '
            'livello RTL azzerano per convenzione. Il confronto è stato quindi ripetuto sulla **netlist '
            'implementata**, ottenendo **%s disallineamenti su %s** su %d traiettorie complete.'
            % (NL_MIS, f'{NL_N:,}'.replace(',', ' '), NL_TRAJ)))
    A(('callout', 'Perimetro dell\'implementazione: la netlist è quella dell\'implementazione **%s**, non '
                  'dell\'intero sistema. Simulare il block design completo richiederebbe il modello di bus del '
                  'processore, che non è parte di questo lavoro: l\'integrazione col processore è coperta '
                  'dall\'equivalenza attraverso il bus (§5.2) e dall\'analisi statica dei tempi sul sistema '
                  'completo (§6.1). Lo stesso perimetro vale per le misure di potenza (§7).' % IMPL_SCOPE))
    A(('p', 'Il numero di traiettorie è stato deciso **dal costo misurato**, non a priori: la simulazione della '
            'netlist costa **%d minuti per traiettoria** contro %.1f della comportamentale — circa **%.0f volte** '
            'tanto — cosicché l\'intero dataset richiederebbe oltre **%.0f ore** senza parallelismo. Le %d '
            'traiettorie costituiscono un cancello di **conferma** con perimetro dichiarato; l\'esaustività resta '
            'quella del confronto comportamentale sull\'intero dataset.'
            % (NL_MIN_TRAJ, CB_MIN_TRAJ, NL_SLOWDOWN, NL_H_ALL, NL_TRAJ)))
    A(('p', 'Una simulazione della netlist **con i ritardi annotati** non ha invece prodotto risultati '
            'utilizzabili. La causa è nel banco e non nel circuito, e lo dimostra il fatto che la simulazione '
            'funzionale sulla **stessa** netlist è corretta: se lo stato iniziale fosse indefinito, entrambe '
            'fallirebbero. Va inoltre ricordato che la firma del timing spetta all\'**analisi statica**, non '
            'alla simulazione — ed è pulita, con margine positivo alla frequenza scelta.'))

    # ---------------------------------------------------------------- 7
    A(('h1', '7. Energia nel funzionamento reale'))
    A(('p', 'La potenza è ricavata dall\'**attività di commutazione registrata** durante la simulazione della '
            'netlist implementata — nel perimetro **%s** di §6.3 — e non da stime a vuoto. Il perimetro fisico è '
            'la logica programmabile: il processore è un blocco fisso del dispositivo e il suo consumo non '
            'appartiene a questo progetto.' % IMPL_SCOPE))
    A(('callout', 'Due limiti dichiarati del metodo, entrambi nella direzione della **sottostima**. '
                  '**Primo:** l\'attività registrata copre **%.0f %% dei collegamenti** del circuito '
                  '(%s su %s); il consumo dei restanti è stimato dallo strumento con i suoi modelli statistici. '
                  'Il livello di confidenza «alto» che lo strumento dichiara non è un avallo di accuratezza: '
                  'sui nodi interni scatta quando l\'attività fornita supera il **%d %%**, soglia ampiamente '
                  'superata qui. **Secondo:** l\'attività proviene da una simulazione **funzionale**, poiché '
                  'quella con i ritardi annotati non è utilizzabile (§6.3), quindi i transitori spurii non sono '
                  'catturati.'
                  % (SAIF_COV, f'{SAIF_NETS:,}'.replace(',', ' '), f'{SAIF_TOT:,}'.replace(',', ' '),
                     SAIF_CONF_THR)))
    A(('h2', '7.1 La finestra di misura dell\'inattività'))
    A(('p', 'Nei periodi di inattività il circuito è in regime **stazionario**: gli ingressi non cambiano e '
            'commuta essenzialmente la rete di distribuzione del clock — %d dei %d mW dinamici, il resto essendo '
            'quasi tutto memoria su chip. La lunghezza della finestra di misura non è '
            'stata scelta a giudizio ma verificata: a **%d**, **%d** e **%d** cicli la potenza risulta '
            '**identica**, quindi la finestra più corta è sufficiente. Lo stesso controllo ha confermato la '
            '**premessa** — che il circuito sia davvero fermo quando non calcola — che non era garantita e '
            'senza la quale la gestione del clock non avrebbe nulla da spegnere.'
            % (round(BD_IDLE[0] * 1000), round(P_IDLE * 1000), IDLE_WIN[0], IDLE_WIN[1], IDLE_WIN[2])))
    A(('h2', '7.2 La fase attiva non dipende dal regime di guida'))
    A(('p', 'La potenza durante il calcolo è stata misurata su **nove** carichi di lavoro reali, uno per ciascuna '
            'combinazione di contesto e profilo presente nel dataset, più un carico sintetico costruito per '
            'massimizzare l\'attività.'))
    A(('img', (fig_workloads(), 'Potenza dinamica nella fase attiva. La dispersione fra i nove regimi reali è di '
                                'circa il 7 %: il consumo durante il calcolo è poco sensibile al tipo di guida. '
                                'Il carico sintetico costruito come caso peggiore (in rosso) risulta il più '
                                'basso di tutti e **non** costituisce quindi un limite superiore valido.')))
    A(('p', 'I nove valori reali stanno in **%d–%d mW** — una dispersione di circa il %.0f %% — e il massimo '
            'osservato è **%d mW**, nel regime «%s». Il carico sintetico misura **%d mW**, cioè meno di tutti '
            'i reali.'
            % (round(min(w[3] for w in WL) * 1000), round(max(w[3] for w in WL) * 1000),
               100.0 * (max(w[3] for w in WL) - min(w[3] for w in WL)) / min(w[3] for w in WL),
               round(max(w[3] for w in WL) * 1000),
               [w[2] for w in WL if w[3] == max(x[3] for x in WL)][0],
               round(WL_WORST * 1000))))
    A(('p', 'Il controllo predisposto per validare il carico sintetico **è fallito**: gli ingressi scelti '
            'a priori — distanza minima, forte velocità di avvicinamento, velocità elevata — non massimizzano '
            'la commutazione. Il valore non viene perciò riportato come limite superiore; il massimo utilizzabile '
            'è quello **osservato** fra i carichi reali, cioè **%d mW**. Individuare il regime effettivamente '
            'peggiore richiede uno studio dedicato.' % round(max(w[3] for w in WL) * 1000)))
    A(('h2', '7.3 Perché la potenza non si compone, e cosa si è fatto invece'))
    A(('p', 'La via naturale per ottenere l\'energia di un control-step reale sarebbe comporre le due fasi: '
            'potenza attiva per la durata del calcolo, più potenza di inattività per il resto. Questa '
            'composizione è stata **messa alla prova** e si è rivelata **non valida**.'))
    A(('img', (fig_eq('eq_comp.png', [r'\bar{P}\;=\;P_{\mathrm{att}}\,\delta\;+\;P_{\mathrm{idle}}\,(1-\delta)'
                                      r'\qquad(\mathrm{ipotesi})',
                                      r'\mathrm{misurato}\;%.3f\;\mathrm{W}\qquad\mathrm{composto}\;%.4f\;\mathrm{W}'
                                      % (CC_MEAS, CC_COMP)]),
               'Composizione lineare della potenza fra le due fasi, e suo esito sperimentale a ciclo di lavoro '
               'del %.2f %%. **P_att**: potenza durante il calcolo; **P_idle**: potenza in inattività; '
               '**δ**: ciclo di lavoro. La relazione sottostima di circa 1.6 volte.' % CC_DUTY)))
    A(('p', 'Lo scarto è **localizzato**: i moltiplicatori dedicati consumano, nella miscela, circa il 40 %% del '
            'valore che hanno in piena attività, pur essendo attivi solo per il %.2f %% del tempo. Una '
            'spiegazione plausibile — dichiarata come ipotesi, non verificata — è che il modello di potenza '
            'dipenda anche dalla probabilità statica dei segnali e non soltanto dalla loro frequenza di '
            'commutazione: in inattività gli ingressi dei moltiplicatori mantengono gli ultimi valori calcolati, '
            'che nel modello non equivale a "spento".' % CC_DUTY))
    A(('p', 'La composizione è stata quindi **abbandonata** e l\'energia è stata **misurata direttamente**, '
            'simulando un control-step reale per intero: oltre cinque milioni di cicli di clock, pari a %.1f s '
            'alla frequenza scelta. Il costo effettivo è stato di dodici minuti, perché in simulazione il costo '
            'è dato dagli eventi di clock e non dal tempo simulato.' % T_STEP))
    A(('img', (fig_duty(), 'Convergenza della potenza dinamica al ridursi del ciclo di lavoro. I tre punti '
                           'misurati tendono al valore di inattività: al control-step reale la fase di calcolo '
                           'è energeticamente trascurabile. Lo scostamento sui moltiplicatori osservato a ciclo '
                           'di lavoro elevato **svanisce**, confermando che dipendeva dal ciclo di lavoro e non '
                           'era uno scostamento fisso.')))
    A(('h2', '7.4 Energia per control-step'))
    A(('img', (fig_eq('eq_energy.png', [r'E_{\mathrm{step}}=\bar{P}\cdot T_{\mathrm{step}}']),
               'Energia per control-step. **P̄**: potenza media misurata al ciclo di lavoro reale; '
               '**T_step**: periodo del control-step. Le componenti dinamica e statica sono tenute distinte.')))
    A(('img', (fig_energy(), 'A sinistra: energia per control-step, con la componente dinamica — il costo del '
                             'progetto — distinta dalla componente statica del dispositivo, che è presente anche '
                             'a circuito inattivo. A destra: composizione della sola parte dinamica; la rete di '
                             'distribuzione del clock ne costituisce la quota dominante, ed è precisamente ciò '
                             'che la gestione del clock aggredisce.')))
    A(('table', (['Voce', 'Potenza', 'Energia per control-step', 'Natura'], [
        ['Dinamica — costo del progetto', f'{P_DYN_REAL*1000:.0f} mW', f'{e_dyn:.1f} mJ',
         'misurato al ciclo di lavoro reale, **gating OFF**'],
        ['di cui rete di distribuzione del clock', f'{BD_REAL[0]*1000:.0f} mW',
         f'{BD_REAL[0]*T_STEP*1000:.1f} mJ', f'{100*BD_REAL[0]/P_DYN_REAL:.0f} % della dinamica'],
        ['Statica del dispositivo', f'{P_STATIC*1000:.0f} mW', f'{e_sta:.1f} mJ',
         f'stima del modello ({STAT_PROC}, Tj {STAT_TJ:.1f} °C)'],
    ])))
    A(('p', 'La configurazione della misura va dichiarata: l\'energia dinamica è stata misurata con la gestione del '
            'clock **disattivata**, cioè col clock sempre libero. Non è la configurazione di deployment — le prove '
            'di equivalenza e i nove carichi di lavoro sono a gestione **attiva** — ed è una scelta prudente, '
            'perché lo strumento non sa contabilizzare il clock fermo (§8): attivarla non avrebbe cambiato il '
            'numero, e dichiararlo come misura «a clock gestito» ne avrebbe falsato il significato. Il valore va '
            'quindi letto come **limite superiore** dell\'energia dinamica del deployment.'))
    A(('callout', 'Le due voci **non vanno sommate in un unico numero senza dirlo**: la componente statica è del '
                  'dispositivo e c\'è anche a circuito spento, mentre la dinamica è ciò che il progetto aggiunge. '
                  'Sul totale la parte dinamica pesa circa l\'8 %, in linea con quanto osservato nella fase '
                  'precedente su questo stesso dispositivo.'))

    # ---------------------------------------------------------------- 8
    A(('h1', '8. Gestione del clock: quando il meccanismo contraddice il sommario'))
    A(('p', 'Poiché il circuito è inattivo per oltre il 99.99 % del tempo e la sua potenza dinamica è dominata '
            'dalla rete di distribuzione del clock, fermare il clock nei periodi di inattività è la leva '
            'naturale. Il sistema la implementa con una porta dedicata, comandata da un **bit di registro** — '
            'una scelta deliberata: così le due configurazioni condividono la **stessa** netlist e il confronto '
            'isola l\'effetto della gestione del clock, non differenze di sintesi.'))
    A(('img', (fig_gating(), 'A sinistra il meccanismo, a destra il sommario dello strumento. Le commutazioni '
                             'del clock della rete, registrate nel file di attività, passano da 400 a **zero**: '
                             'il clock si ferma completamente. La potenza riportata resta però **identica** '
                             'nelle due configurazioni.')))
    A(('p', 'La gestione del clock **funziona**, ed è provata su due piani indipendenti. Sul piano funzionale, '
            'l\'equivalenza col blocco resta perfetta con la porta attiva: **%s disallineamenti su %s**, cioè il '
            'circuito calcola correttamente pur avendo il clock fermato e riavviato a ogni control-step. Sul '
            'piano del meccanismo, le commutazioni del clock della rete passano da **%d a %d**.'
            % (AXI_MIS, f'{AXI_N:,}'.replace(',', ' '), TC_UNGATED, TC_GATED)))
    A(('p', 'Il **guadagno in potenza**, però, non è ottenibile da questo flusso di analisi. Lo strumento ricava '
            'la potenza delle reti di clock dal **vincolo di frequenza** dichiarato, non dall\'attività '
            'registrata: un clock fermo continua perciò a essere conteggiato come se commutasse. La cosa è stata '
            'verificata anche in negativo, imponendo esplicitamente attività nulla sulle reti interessate — '
            'il risultato non cambia di una cifra.'))
    A(('callout', 'Se ci si fosse fermati al sommario, la conclusione sarebbe stata "la gestione del clock non '
                  'serve": un\'affermazione **falsa**, e credibile, prodotta da uno strumento autorevole che '
                  'dichiara su quel report confidenza «alta» — etichetta che, come si è visto in §7.1, misura '
                  'quanta attività le è stata fornita, non quanto sia corretto il risultato. È la ragione per cui '
                  'un risultato va sempre confrontato col meccanismo che lo genera, e non accettato dal solo '
                  'valore riassuntivo.'))
    A(('p', 'Il guadagno atteso, dichiarato come **stima** e non come misura: la quota dominante della potenza '
            'dinamica è la rete di distribuzione del clock, e la parte spenta serve la quasi totalità dei '
            'registri, tutti i moltiplicatori e l\'unica memoria del progetto. Fermandola, la potenza dinamica '
            'dovrebbe ridursi di un fattore compreso fra **%d e %d**.' % (GAIN_LO, GAIN_HI)))
    A(('p', 'La verifica è rimandata alla misura su board, dove è **immediata** proprio grazie alla scelta '
            'progettuale iniziale: essendo la gestione del clock comandata da un bit di registro, **lo stesso '
            'bitstream** consente di leggere la corrente assorbita a riposo nelle due configurazioni e di '
            'ricavare il risparmio per differenza. Non serve un secondo bitstream né una ricompilazione.'))

    # ---------------------------------------------------------------- 9
    A(('h1', '9. Bitstream, riproducibilità e limiti'))
    A(('h2', '9.1 Il bitstream e la sua provenienza'))
    A(('p', 'Il bitstream è generato con la **stessa procedura** usata per la caratterizzazione, cosicché il '
            'circuito programmato sia quello misurato e non una variante ricostruita a parte. Il margine di '
            'timing del percorso che produce il bitstream — **%+.3f ns** — coincide con quello della scansione '
            'alla stessa frequenza, il che conferma anche la riproducibilità del flusso.' % BIT_WNS))
    A(('table', (['Artefatto', 'Dimensione', 'Destinazione'], [
        ['bitstream', f'{BIT_SZ/1e6:.2f} MB', 'programmazione della logica sulla board'],
        ['descrizione hardware', f'{HWH_SZ/1e3:.0f} kB', 'ambiente Python della board'],
        ['archivio di piattaforma', f'{XSA_SZ/1e6:.2f} MB', 'ambiente di sviluppo software'],
    ])))
    A(('p', 'La provenienza è verificata nell\'artefatto stesso: la descrizione hardware riporta la board '
            '`%s`, il dispositivo e il package attesi.' % BOARD))
    A(('h2', '9.2 Riproducibilità'))
    A(('p', 'L\'intera catena è eseguibile **da un comando per stadio** — verifica di provenienza, prove sulle '
            'assunzioni, equivalenza, scansione della frequenza, netlist, energia, bitstream — e uno stadio '
            'di sintesi riestrae i valori chiave **dagli artefatti su disco**, non da costanti nel programma. '
            'Un rilancio si **confronta** quindi con quanto documentato, invece di duplicarlo.'))
    A(('p', 'Un cancello dedicato verifica che il codice caratterizzato sia l\'artefatto validato: confronta '
            'l\'impronta dei sorgenti con quella registrata e, se il codice è assente, lo rigenera **e** '
            'ripete la prova di equivalenza prima di procedere. Anche questo cancello è provato sensibile: '
            'alterando una riga di un file, l\'impronta cambia e il cancello blocca.'))
    A(('callout', 'Il cancello di provenienza ha esso stesso contenuto, in prima stesura, il difetto che era '
                  'destinato a prevenire: una sostituzione di comando spezzava il percorso del progetto in '
                  'corrispondenza di uno spazio, cosicché non veniva letto alcun file e l\'impronta calcolata era '
                  'quella della stringa vuota — dichiarando successo. È il motivo per cui un cancello va provato '
                  '**anche in negativo**, e non soltanto visto passare.'))
    A(('h2', '9.3 Limiti dichiarati'))
    A(('table', (['Voce', 'Stato', 'Come si chiude'], [
        ['Guadagno in potenza della gestione del clock', 'non misurabile con questo flusso',
         'misura di corrente su board, stesso bitstream, due configurazioni'],
        ['Limite superiore della potenza attiva', 'carico sintetico invalidato',
         'studio dedicato sul regime che massimizza l\'attività'],
        ['Simulazione della netlist con ritardi annotati', 'non riuscita (causa nel banco)',
         'la funzionale è corretta e la firma del timing è dell\'analisi statica'],
        ['Composizione lineare della potenza fra fasi', 'invalidata dal proprio controllo',
         'superata: l\'energia è misurata direttamente al ciclo di lavoro reale'],
        ['Equivalenza della netlist sull\'intero dataset', f'confermata su {NL_TRAJ} traiettorie',
         'l\'esaustività è del confronto comportamentale su tutte e 60'],
    ])))

    # ---------------------------------------------------------------- 10
    A(('h1', '10. Osservazioni di metodo'))
    A(('p', 'Alcune delle difficoltà incontrate hanno valore oltre questo lavoro, e sono registrate nei '
            'documenti di processo perché non vengano ripercorse.'))
    A(('h2', '10.1 Verificare le assunzioni prima di pianificare'))
    A(('p', 'I modelli di banco ereditati da un blocco precedente si sono rivelati **non trasferibili** al '
            'blocco attuale, che è mascherato, gerarchico e con stato in memoria: quattro correzioni sono state '
            'necessarie in corso d\'opera. Nella fase successiva le assunzioni sono state invece verificate con '
            '**prove mirate prima** di scrivere il piano, e una di esse — il presunto segnale di fine '
            'elaborazione — si è rivelata falsa, con conseguenze dirette sul progetto del wrapper. '
            'Il costo delle prove è stato di minuti; quello delle correzioni in corsa, di ore.'))
    A(('h2', '10.2 Non filtrare la diagnostica'))
    A(('p', 'Tre volte, in questo lavoro, un programma di verifica ha nascosto l\'informazione necessaria a '
            'diagnosticare un fallimento: uscita reindirizzata al nulla, output catturato e mai stampato, filtro '
            'ristretto ai soli messaggi di errore. La causa comune è scrivere il filtro pensando al caso in cui '
            'tutto funziona, mentre serve nel caso opposto. Negli strumenti di verifica la diagnostica si '
            '**limita in lunghezza, non in contenuto**.'))
    A(('h2', '10.3 Guardare i valori, non gli indizi'))
    A(('p', 'Un primo tentativo di diagnosi si è appoggiato a una misura di temporizzazione compatibile con '
            'l\'ipotesi formulata — e anche con altre: la correzione applicata non ha cambiato nulla. Il quadro '
            'si è chiarito solo confrontando **i valori che discriminano**: quanto letto dal bus, quanto '
            'memorizzato dal wrapper, quanto prodotto dal blocco e quanto atteso dal riferimento. Quel confronto '
            'ha separato due difetti distinti in un solo passaggio.'))
    A(('h2', '10.4 Misurare il costo prima di impegnare ore'))
    A(('p', 'La regola è stata applicata con profitto in più punti — il costo del riferimento, il primo punto '
            'della scansione di frequenza, le verifiche preliminari alla simulazione del control-step completo — '
            'e violata una volta, lanciando tre simulazioni di netlist senza cronometrarne una. '
            'Le stime a priori si sono rivelate sbagliate in entrambe le direzioni: una volta troppo '
            'pessimistiche di un fattore dieci, perché dominate dal costo fisso di avvio dello strumento.'))

    # ---------------------------------------------------------------- 11
    A(('h1', '11. Conclusioni'))
    A(('p', 'La rete neurale spiking estimatrice è **validata a livello di codice generato, di netlist '
            'implementata e di sistema completo**, con confronti bit-esatti: su **tutto il dataset** per il codice '
            'generato e per il sistema attraverso il bus, su **%d traiettorie** con perimetro dichiarato per la '
            'netlist. È inoltre **caratterizzata in hardware**: frequenza deployabile e limite del circuito, '
            'risorse dopo place&route comprensive della memoria su chip, energia per control-step misurata al '
            'ciclo di lavoro reale. Il bitstream per la board è prodotto, con timing chiuso e provenienza '
            'verificata.' % NL_TRAJ))
    A(('p', 'Il quadro applicativo che ne emerge è netto: con un margine temporale di quattro ordini di '
            'grandezza sul control-step richiesto, il vincolo di questo progetto **non è la velocità**. '
            'L\'energia è dominata dai periodi di inattività, e in quei periodi dalla rete di distribuzione del '
            'clock: la leva utile è fermare il clock, non aumentarlo. La gestione del clock è implementata, '
            'funzionalmente trasparente e provata attiva; la quantificazione del suo beneficio è l\'oggetto '
            'naturale della misura su board.'))
    A(('p', 'Tre grandezze non sono state ottenute e sono dichiarate come tali, con l\'indicazione di come si '
            'chiudono. Preferire una lacuna dichiarata a una stima presentata come misura è una scelta '
            'deliberata: un numero plausibile e infondato è più dannoso di un numero assente, perché non si '
            'distingue da uno corretto.'))

    # ---------------------------------------------------------------- 12
    A(('h1', 'Riferimenti'))
    A(('p', 'Documentazione degli strumenti utilizzata per il flusso di implementazione, simulazione e analisi. '
            'I risultati interni al progetto sono rimandi ai propri artefatti, non citazioni.'))
    A(('table', (['Riferimento', 'Rilevanza per questo documento'], [
        ['AMD/Xilinx, *Vivado Design Suite User Guide: Power Analysis and Optimization* (UG907)',
         'metodo di analisi della potenza; ruolo dell\'attività di commutazione registrata e del vincolo di clock'],
        ['AMD/Xilinx, *Vivado Design Suite User Guide: Logic Simulation* (UG900)',
         'simulazione comportamentale, funzionale e di timing; registrazione dell\'attività di commutazione'],
        ['AMD/Xilinx, *Vivado Design Suite User Guide: Synthesis* (UG901)',
         'sintesi fuori contesto e sue differenze dal flusso di sistema'],
        ['AMD/Xilinx, *UltraFast Design Methodology Guide for FPGAs and SoCs* (UG949)',
         'ruolo dell\'analisi statica dei tempi come firma del timing'],
        ['AMD/Xilinx, *Zynq-7000 SoC Technical Reference Manual* (UG585)',
         'processore, generazione dei clock verso la logica programmabile e loro quantizzazione'],
        ['MathWorks, *HDL Coder User\'s Guide*',
         'generazione del codice da modello; semantica dei segnali di abilitazione del clock'],
        ['Digilent, *PYNQ-Z1 Reference Manual*',
         'board di destinazione e suo preset di configurazione'],
        ['Treiber, M., Hennecke, A., Helbing, D. (2000). *Congested traffic states in empirical observations '
         'and microscopic simulations.* Physical Review E 62(2), 1805–1824',
         'modello di car-following i cui parametri sono l\'uscita della rete'],
    ])))
    A(('h2', 'Artefatti del progetto (rimandi)'))
    A(('table', (['Artefatto', 'Contenuto'], [
        ['FaseB2.0/Harness_SNN/results/RESULTS.md', 'cancelli e metriche della validazione RTL'],
        ['FaseB2.0/Harness_SNN/results/RESULTS_HW.md', 'caratterizzazione hardware completa, con natura di ogni numero'],
        ['FaseB2.0/Harness_SNN/results/PROBES_T6B.md', 'esito delle prove sulle assunzioni hardware'],
        ['FaseB2.0/Harness_SNN/results/*.rpt', 'report grezzi di potenza, timing e utilizzo'],
        ['FaseB2.0/Harness_SNN/bitstream/', 'bitstream e artefatti di handoff'],
        ['document/HDL_PHASE.md §6, §9', 'stato della fase e gotcha tecnici e di metodo'],
    ])))
    return D

# ============================================================================
# RENDER
# ============================================================================
def render_md(doc, outpath):
    L = []; mdc = lambda x: str(x).replace('|', '\\|')
    for kind, *rest in doc:
        b = rest[0] if rest else None
        if kind == 'cover':
            L.append(f"# {b['title']}\n"); L.append(f"> **{b['subtitle']}**\n")
            for m in b['meta']: L.append(f"> {m}  ")
            L.append('\n---\n')
        elif kind == 'h1': L.append(f"\n## {b}\n")
        elif kind == 'h2': L.append(f"\n### {b}\n")
        elif kind == 'h3': L.append(f"\n#### {b}\n")
        elif kind == 'p': L.append(b + '\n')
        elif kind == 'callout': L.append(f"> **Nota.** {b}\n")
        elif kind == 'toc':
            title = b if isinstance(b, str) else b[0]
            L.append(f"\n## {title}\n"); L.append('| Sezione |'); L.append('|---|')
            for k2, *rr in doc:
                if k2 in ('h1', 'h2', 'h3'): L.append(f'| {mdc(rr[0]) if rr else ""} |')
            L.append('')
        elif kind == 'table':
            headers, rows = b
            L.append('| ' + ' | '.join(mdc(h) for h in headers) + ' |')
            L.append('|' + '|'.join(['---'] * len(headers)) + '|')
            for r in rows: L.append('| ' + ' | '.join(mdc(x) for x in r) + ' |')
            L.append('')
        elif kind == 'img':
            path, capt = b; rel = os.path.relpath(path, OUTDIR).replace('\\', '/')
            L.append(f"![{capt}]({rel})"); L.append(f"*{capt}*\n")
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(norm_it('\n'.join(L)))
    print('  scritto', outpath)

def render_pdf(doc, outpath):
    import re
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                    Table, TableStyle, PageBreak, HRFlowable, KeepTogether)
    from reportlab.platypus.tableofcontents import TableOfContents
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import ImageReader
    fdir = os.path.join(os.path.dirname(matplotlib.__file__), 'mpl-data', 'fonts', 'ttf')
    pdfmetrics.registerFont(TTFont('DJ', os.path.join(fdir, 'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('DJ-B', os.path.join(fdir, 'DejaVuSans-Bold.ttf')))
    body = ParagraphStyle('body', fontName='DJ', fontSize=9.5, leading=14, spaceAfter=6, alignment=4)
    h1 = ParagraphStyle('h1', fontName='DJ-B', fontSize=17, leading=21, spaceBefore=16, spaceAfter=9,
                        textColor=colors.HexColor('#1a3c6e'))
    h1toc = ParagraphStyle('h1toc', parent=h1)
    h2 = ParagraphStyle('h2', fontName='DJ-B', fontSize=12.5, leading=16, spaceBefore=10, spaceAfter=5,
                        textColor=colors.HexColor('#26527a'), keepWithNext=1)
    h3 = ParagraphStyle('h3', fontName='DJ-B', fontSize=10.5, leading=14, spaceBefore=7, spaceAfter=4,
                        textColor=colors.HexColor('#333333'), keepWithNext=1)
    cap = ParagraphStyle('cap', fontName='DJ', fontSize=8, leading=11,
                         textColor=colors.HexColor('#555555'), spaceAfter=12, alignment=4)
    callout = ParagraphStyle('callout', fontName='DJ', fontSize=9.5, leading=14, leftIndent=8,
                             borderPadding=6, backColor=colors.HexColor('#eef3fa'),
                             borderColor=colors.HexColor('#9bb8d8'), borderWidth=0.6, spaceBefore=4, spaceAfter=10)
    def esc(s):
        s = norm_it(str(s)).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        s = re.sub(r'(?<!\w)\*\*(\S(?:.*?\S)?)\*\*', r'<b>\1</b>', s)
        # Spazio INSECABILE fra un numero e la sua unita': impedisce che l'a-capo separi
        # "25" da "%" o "+0.358" da "ns". Solo nel PDF: il .md resta con spazi normali.
        return re.sub(r'(\d)\s+(%|mW|mJ|MHz|GHz|kHz|ns|µs|ms|LUT|FF|DSP|BRAM|W|V|°C|pt|bit)(?![\w])',
                      r'\1&nbsp;\2', s)
    usable_w = A4[0] - 3.6 * cm
    story = []
    def add_image(path, caption):
        import sys
        img = ImageReader(path); iw, ih = img.getSize()
        if os.path.basename(path).startswith('eq_'):
            w = iw * 72.0 / EQ_DPI; h = ih * 72.0 / EQ_DPI
            if w > usable_w:
                scale = usable_w / w; h *= scale; w = usable_w
                if scale < 0.85: print(f"  ATTENZIONE: equazione {os.path.basename(path)} ridotta al {scale:.0%}", file=sys.stderr)
            eqim = Image(path, width=w, height=h); eqim.hAlign = 'CENTER'
            story.append(KeepTogether([Spacer(1, 3), eqim, Paragraph(esc(caption), cap)])); return
        w = usable_w; h = w * ih / iw
        if h > 12.0 * cm: h = 12.0 * cm; w = h * iw / ih
        story.append(KeepTogether([Spacer(1, 4), Image(path, width=w, height=h), Paragraph(esc(caption), cap)]))
    def make_table(headers, rows):
        n = len(headers); fs = 8 if n <= 4 else 7.2 if n <= 5 else 6.4
        th = ParagraphStyle('th', fontName='DJ-B', fontSize=fs, leading=fs + 2, textColor=colors.white, wordWrap='CJK')
        data = [[Paragraph(f'<b>{esc(x)}</b>', th) for x in headers]]
        cell = ParagraphStyle('td', fontName='DJ', fontSize=fs, leading=fs + 2.5, wordWrap='CJK')
        for r in rows: data.append([Paragraph(esc(x), cell) for x in r])
        t = Table(data, repeatRows=1, colWidths=[usable_w / n] * n, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#26527a')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5fa')]),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#b9c6d6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
        story.append(Spacer(1, 2)); story.append(t); story.append(Spacer(1, 8))
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle('toc0', fontName='DJ-B', fontSize=10.5, leading=18, textColor=colors.HexColor('#1a3c6e')),
        ParagraphStyle('toc1', fontName='DJ', fontSize=9.5, leading=14, leftIndent=16),
        ParagraphStyle('toc2', fontName='DJ', fontSize=9, leading=13, leftIndent=32, textColor=colors.HexColor('#555555'))]
    class TOCDoc(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            if flowable.__class__.__name__ == 'Paragraph':
                lvl = {'h1': 0, 'h2': 1, 'h3': 2}.get(flowable.style.name)
                if lvl is not None:
                    txt = flowable.getPlainText().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    self.notify('TOCEntry', (lvl, txt, self.page))
    for kind, *rest in doc:
        b = rest[0] if rest else None
        if kind == 'cover':
            story.append(Spacer(1, 3.2 * cm))
            story.append(Paragraph(esc(b['title']), ParagraphStyle('ct', fontName='DJ-B', fontSize=23,
                         leading=29, textColor=colors.HexColor('#1a3c6e'), alignment=1)))
            story.append(Spacer(1, 0.5 * cm))
            story.append(Paragraph(esc(b['subtitle']), ParagraphStyle('cs', fontName='DJ', fontSize=11.5,
                         leading=16, textColor=colors.HexColor('#444444'), alignment=1)))
            story.append(Spacer(1, 1.4 * cm))
            story.append(HRFlowable(width='60%', thickness=1, color=colors.HexColor('#9bb8d8')))
            story.append(Spacer(1, 0.6 * cm))
            for m in b['meta']:
                story.append(Paragraph(esc(m), ParagraphStyle('cm', fontName='DJ', fontSize=10,
                             leading=15, alignment=1, textColor=colors.HexColor('#333333'))))
            story.append(PageBreak())
        elif kind == 'toc':
            title = b if isinstance(b, str) else b[0]
            story.append(Paragraph(esc(title), h1toc))
            story.append(HRFlowable(width='100%', thickness=0.9, color=colors.HexColor('#c5d3e2'), spaceAfter=8))
            story.append(toc)
        elif kind == 'h1':
            story.append(PageBreak()); story.append(Paragraph(esc(b), h1))
            story.append(HRFlowable(width='100%', thickness=0.9, color=colors.HexColor('#c5d3e2'), spaceAfter=6))
        elif kind == 'h2': story.append(Paragraph(esc(b), h2))
        elif kind == 'h3': story.append(Paragraph(esc(b), h3))
        elif kind == 'p': story.append(Paragraph(esc(b), body))
        elif kind == 'callout': story.append(Paragraph('<b>Nota.</b> ' + esc(b), callout))
        elif kind == 'table': make_table(*b)
        elif kind == 'img': add_image(*b)
    def footer(canvas, docx):
        canvas.saveState(); canvas.setFont('DJ', 7.5); canvas.setFillColor(colors.HexColor('#888888'))
        canvas.drawString(2 * cm, 1.1 * cm, FOOTER_TEXT)
        canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f'pag. {docx.page}')
        canvas.restoreState()
    pdf = TOCDoc(outpath, pagesize=A4, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                 leftMargin=1.8 * cm, rightMargin=1.8 * cm, title=DOC_TITLE)
    pdf.multiBuild(story, onFirstPage=footer, onLaterPages=footer)
    print('  scritto', outpath)

if __name__ == '__main__':
    os.makedirs(OUTDIR, exist_ok=True)
    print('[1/3] figure + contenuto...'); DOC = build_doc()
    print('[2/3] markdown...'); render_md(DOC, os.path.join(OUTDIR, DOC_NAME + '.md'))
    print('[3/3] pdf...');      render_pdf(DOC, os.path.join(OUTDIR, DOC_NAME + '.pdf'))
    print('fatto:', os.path.join(OUTDIR, DOC_NAME + '.{md,pdf}'))
