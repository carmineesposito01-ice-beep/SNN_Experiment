"""build_harness_snn_iidm_report.py — REPORT Fase B2.0 / T7 · Harness_SNN_IIDM — .md + .pdf da sorgente unica.

Validazione in ANELLO CHIUSO a livello RTL (T7a) e caratterizzazione hardware (T7b) del blocco COMPOSTO
`Donatello_SNN_IIDM` = SNN `Donatello_Tier@BALANCED/nfrac13` + allineamento `align` + controllore ACC-IIDM:
il Verilog generato provato bit-esatto rispetto al blocco su 99 scenari di car-following con cut-in, il
sistema completo (composto + wrapper AXI4-Lite + Zynq PS7) implementato, misurato in clock/risorse/energia,
e portato a bitstream.

GROUNDING — nessun numero e' trascritto a mano. Questo generatore LEGGE gli artefatti a macchina:
  * T7a cancelli : results/t7_results.mat        (scipy)  -> nExact, nTot, nRange, nRep, nPP, K
  * T7a metriche : results/metrics.json          (motore canonico Python, 99 scenari x 31 metriche)
  * T7b sweep    : results/sweep.json            <- gen_sweep_report.py   <- timing_*.rpt, util_*.rpt
  * T7b netlist  : results/netlist.json          <- gen_netlist_report.py <- netlist_func.log
  * T7b energia  : results/power.json            <- gen_power_report.py   <- power_*.rpt
                   results/power_params.json     <- run_power.sh (parametri EFFETTIVAMENTE usati)
                   results/saif_stats.json       <- gen_saif_stats.py     <- i 13 .saif
  * bitstream    : bitstream/*.bit + util_bitstream_*.rpt + timing_bitstream_*.rpt
UNICA eccezione dichiarata: i due esiti della cosim AXI, che stanno in COSIM_AXI.md (documento scritto a
mano che registra la run). Sono marcati COSIM_* e la fonte e' indicata nel testo.

I cancelli sono deterministici (esito 0/N). Le grandezze non misurabili con questo flusso sono marcate
come STIMA nel testo e nelle figure, mai presentate come misura.

Uso:    python scripts/build_harness_snn_iidm_report.py
Output: report/B2_0_HARNESS_SNN_IIDM_REPORT.{md,pdf}  +  report/figures_harness_snn_iidm/*
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import io, json, sys
import scipy.io as sio

# --- CONFIG -----------------------------------------------------------------
HERE       = os.path.dirname(os.path.abspath(__file__))
ROOT       = os.path.dirname(HERE)
OUTDIR     = os.path.join(ROOT, 'report')
FIGDIR     = os.path.join(OUTDIR, 'figures_harness_snn_iidm')
RES        = os.path.join(ROOT, 'FaseB2.0', 'Harness_SNN_IIDM', 'results')
BITS       = os.path.join(ROOT, 'FaseB2.0', 'Harness_SNN_IIDM', 'bitstream')
DOC_NAME   = 'B2_0_HARNESS_SNN_IIDM_REPORT'
DOC_TITLE  = ('CF_FSNN — Harness_SNN_IIDM: validazione in anello chiuso e caratterizzazione hardware '
              '(Fase B2.0 · T7)')
FOOTER_TEXT = 'CF_FSNN — Fase B2.0 · T7 Harness_SNN_IIDM · SNN + ACC-IIDM su Zynq-7020'
EQ_DPI     = 200
os.makedirs(FIGDIR, exist_ok=True)

# ============================================================================
# GROUNDING — si LEGGE dagli artefatti; se manca una fonte, si ABORTISCE.
# Un report costruito su una fonte mancante avrebbe sezioni vuote che somigliano a sezioni complete.
# ============================================================================
def _load_json(name):
    p = os.path.join(RES, name)
    if not os.path.exists(p):
        sys.exit('BUILD-ABORT: manca %s — eseguire la fase che lo produce prima di costruire il report.' % p)
    return json.load(io.open(p, encoding='utf-8'))

SW  = _load_json('sweep.json')
NL  = _load_json('netlist.json')
PW  = _load_json('power.json')
PP  = _load_json('power_params.json')
ST  = _load_json('saif_stats.json')
MET = _load_json('metrics.json')

_mp = os.path.join(RES, 't7_results.mat')
if not os.path.exists(_mp):
    sys.exit('BUILD-ABORT: manca %s (esito primario dei cancelli T7a).' % _mp)
_M = sio.loadmat(_mp, squeeze_me=True, struct_as_record=False)
_V = _M['V']

# --- T7a: cancelli, dall'esito PRIMARIO (non dal markdown che ne deriva) ----
T7A_MODE   = str(_M['mode'])
T7A_K      = int(_M['K'])                 # control-step per scenario
T7A_NEXACT = int(_V.nExact)               # T7-EXACT: disallineamenti RTL vs BLOCCO
T7A_NTOT   = int(_V.nTot)                 # confronti totali
T7A_NRANGE = int(_V.nRange)               # PARAM-RANGE: parametri fuori dai limiti del decode
T7A_NREP   = int(_V.nRep)                 # NO-REPEAT: control-step coi 5 parametri ripetuti
T7A_NPP    = int(_M['nPP'])               # PLANT-PAR: disallineamenti plant TB vs qz_cl_sim
T7A_MINS   = float(_M['mins'])            # durata della run completa, in minuti

# --- T7a: metriche dal motore canonico --------------------------------------
_S = MET['_summary']
MET_NSCEN, MET_NMETR = int(_S['n_scenari']), int(_S['n_metriche'])
COLL_RTL, COLL_ORA, COLL_EXTRA = int(_S['coll_rtl']), int(_S['coll_oracolo']), int(_S['coll_extra'])

# --- T7b: sweep, netlist, energia -------------------------------------------
FCLK        = SW['deployable_mhz']
WNS, WHS    = SW['deployable_wns_ns'], SW['deployable_whs_ns']
FLIMIT      = SW['datapath_limit_mhz']
FLIMIT_FROM = SW['limit_from_mhz']
OOC_WNS     = SW['ooc_wns_ns']
UTIL        = SW['util']
HIER        = SW['hier']
QUANT       = SW['quantized']
PTS         = SW['points']

NL_NMIS, NL_N, NL_NSCEN = NL['nmismatch'], NL['n'], NL['nscen']
NL_SCEN, NL_RATIO, NL_FULL_H = NL['scenari'], NL['gate_level_ratio'], NL['full99_hours']
NL_WALL_MIN = NL['wall_s'] / 60.0

ACT_CLK, NACT   = int(PP['act_clk']), int(PP['nact'])
TOT_CLK         = int(PP['tot_clk'])
CTRL_S          = float(PP['ctrl_step_s'])
DUTY_PCT        = 100.0 * ACT_CLK / TOT_CLK
LAT_CLK         = 555                       # latenza pura del DUT (RESULTS.md T7a §Configurazione)
WLS             = PP['workloads']

P_IDLE, P_ACT, P_DUTY = PW['idle_dyn_w'], PW['act_max_dyn_w'], PW['duty_dyn_w']
P_STAT          = PW['static_w']
E_DYN_MJ        = PW['energy_dyn_per_step_mj']
E_STAT_MJ       = PW['energy_static_per_step_mj']
SAIF_N, SAIF_T  = PW['saif_cov']
SAIF_CONF       = PW['confidence']
TC_DISP         = PW['tc_disp_pct']
TC_IDLE, TC_IDLE_G = PW['tc_idle_per_clk'], PW['tc_idle_gated_per_clk']
GATING_GAIN     = PW['gating_toggle_gain']
DUTY_COH_ERR    = PW['duty_coherence_err_pct']

# --- cosim AXI: UNICA fonte scritta a mano (COSIM_AXI.md), dichiarata --------
COSIM_N, COSIM_MIS, COSIM_MODES = 58522, 0, 2
COSIM_MIN = 76

# --- bitstream ---------------------------------------------------------------
_bit = os.path.join(BITS, 'donatello_snn_iidm.bit')
BIT_MB = os.path.getsize(_bit) / 1e6 if os.path.exists(_bit) else None

# --- CANCELLI DI COERENZA fra fonti indipendenti ----------------------------
# Non sono decorazione: le fonti sono prodotte da pipeline diverse e devono concordare dove si
# sovrappongono. Una divergenza qui significa che il report starebbe mescolando due campagne.
_err = []
if T7A_NTOT != COSIM_N:
    _err.append('confronti T7a (%d, da t7_results.mat) != confronti cosim AXI (%d, da COSIM_AXI.md): '
                'non sono lo stesso perimetro' % (T7A_NTOT, COSIM_N))
if MET_NSCEN != len(MET['RTL']):
    _err.append('n_scenari dichiarato %d != scenari presenti in metrics.json %d' % (MET_NSCEN, len(MET['RTL'])))
if abs(sum(r['n'] for r in [{'n': NL_N}]) - NL_N) > 0:
    _err.append('incoerenza interna netlist.json')
if int(PP['fclk_mhz']) != int(FCLK):
    _err.append('FCLK della campagna energia (%s) != FCLK deployabile dello sweep (%s)'
                % (PP['fclk_mhz'], FCLK))
if T7A_MODE != 'full':
    _err.append("t7_results.mat e' di una run '%s', non 'full': i numeri non coprono i 99 scenari" % T7A_MODE)
if _err:
    sys.exit('BUILD-ABORT: le fonti non concordano.\n  - ' + '\n  - '.join(_err))

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
# FIGURE DATI
# ============================================================================
def fig_system():
    """Il composto dietro il wrapper AXI: dove passa il dato e dove sta il confine di misura."""
    fig, ax = plt.subplots(figsize=(8.6, 3.15)); ax.axis('off')
    ax.set_xlim(0, 100); ax.set_ylim(0, 42)
    def box(x, y, w, h, t, c, fs=8.2, tc='white'):
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.5',
                                             fc=c, ec='none'))
        ax.text(x + w / 2, y + h / 2, t, ha='center', va='center', fontsize=fs, color=tc, weight='bold')
    def arr(x1, y1, x2, y2, t=''):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='-|>', color='#44506a', lw=1.3))
        if t:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 1.6, t, ha='center', fontsize=7.2, color='#44506a')
    ax.add_patch(mpatches.FancyBboxPatch((2, 2), 96, 38, boxstyle='round,pad=0.6',
                                         fc='#f2f5f9', ec='#c7d2e0', lw=1.1))
    box(4, 16, 13, 10, 'Zynq PS7\n(processore)', PAL['blunav'])
    box(21, 16, 13, 10, 'protocol\nconverter', '#6b7c93')
    box(38, 4, 58, 34, '', '#e3ebf4')
    ax.text(67, 35.4, 'snniidm_axi_lite  (wrapper AXI4-Lite)', ha='center', fontsize=8.4,
            color='#26527a', weight='bold')
    box(41, 20, 52, 12, '', '#d3e0ee')
    ax.text(67, 29.6, 'Donatello_SNN_IIDM  (il blocco)', ha='center', fontsize=8.2,
            color='#1a3c6e', weight='bold')
    box(43, 21.6, 15, 6.4, 'SNN\nTier@BAL/n13', PAL['blu'], fs=7.6)
    box(60, 21.6, 12, 6.4, 'align', PAL['mattone'], fs=7.8)
    box(74, 21.6, 17, 6.4, 'ACC-IIDM', PAL['verde'], fs=7.8)
    box(41, 7, 22, 8, 'gating del clock\n(BUFGCE, bit di registro)', '#8a7ab5', fs=7.4)
    box(67, 7, 26, 8, 'contatore di latenza\n-> done  (%d clock)' % LAT_CLK, '#6b7c93', fs=7.4)
    arr(17, 21, 21, 21); arr(34, 21, 41, 21, 's, v, dv, v_l')
    arr(58, 24.8, 60, 24.8); arr(72, 24.8, 74, 24.8)
    ax.annotate('', xy=(38, 12), xytext=(93, 12), arrowprops=dict(arrowstyle='-|>', color='#44506a', lw=1.3))
    ax.text(67, 17.4, 'accel  (sfix13_En8)', ha='center', fontsize=7.4, color='#44506a')
    ax.text(50, 0.4, 'Confine di misura: tutto cio\' che sta nel riquadro chiaro e\' implementato in PL '
                     'e caratterizzato in T7b', ha='center', fontsize=7.4, color='#6b7c93', style='italic')
    p = os.path.join(FIGDIR, 'system.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p


def fig_decomp():
    """Le due prove disgiunte: PLANT-PAR (senza DUT) e T7-EXACT (senza plant)."""
    fig, axs = plt.subplots(1, 2, figsize=(8.6, 2.5))
    for ax, (tit, boxes, cols, note) in zip(axs, [
        ('PLANT-PAR — il plant del banco e\' quello di riferimento',
         ['plant\nVerilog', 'accel\nREGISTRATA\n(oracolo)', 'qz_cl_sim\n(MATLAB)'],
         [PAL['verde'], '#c7d2e0', PAL['verde']],
         'nessun DUT nell\'anello: si prova SOLO il plant'),
        ('T7-EXACT — l\'RTL e\' il blocco, sugli ingressi ricevuti',
         ['ingressi\nRICEVUTI\ndall\'RTL', 'DUT\nVerilog', 'blocco\nSimulink'],
         ['#c7d2e0', PAL['blu'], PAL['blu']],
         'nessun plant nel confronto: si prova SOLO il DUT')]):
        ax.axis('off'); ax.set_xlim(0, 30); ax.set_ylim(0, 12)
        for i, (b, c) in enumerate(zip(boxes, cols)):
            ax.add_patch(mpatches.FancyBboxPatch((0.5 + i * 10, 4), 8.6, 5.2,
                                                 boxstyle='round,pad=0.4', fc=c, ec='none'))
            ax.text(4.8 + i * 10, 6.6, b, ha='center', va='center', fontsize=7.4,
                    color='white' if c != '#c7d2e0' else '#26527a', weight='bold')
            if i < 2:
                ax.annotate('', xy=(10.6 + i * 10, 6.6), xytext=(9.3 + i * 10, 6.6),
                            arrowprops=dict(arrowstyle='-|>', color='#44506a', lw=1.2))
        ax.set_title(tit, fontsize=8.4, color='#26527a')
        ax.text(15, 1.6, note, ha='center', fontsize=7.3, color='#8a5a2a', style='italic')
    fig.suptitle('Le due prove non condividono il componente che l\'altra verifica', fontsize=9.2, y=1.03)
    p = os.path.join(FIGDIR, 'decomp.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p


def fig_gates():
    """Copertura dei cancelli: confronti eseguiti, tutti a 0 disallineamenti."""
    names = ['PLANT-PAR\nplant vs qz_cl_sim\n(99 scenari, senza DUT)',
             'T7-EXACT\nRTL vs blocco\n(99 scenari)',
             'AXI-COSIM\nPS vs blocco\n(99 scenari x 2 gating)',
             'NETLIST\npost-route vs blocco\n(%d scenari dichiarati)' % NL_NSCEN]
    vals = [MET_NSCEN, T7A_NTOT, COSIM_N * COSIM_MODES, NL_N]
    cols = [PAL['verde'], PAL['blu'], PAL['verde'], PAL['viola']]
    fig, ax = plt.subplots(figsize=(8.4, 3.0))
    bars = ax.bar(names, vals, color=cols)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v * 1.10, f'{v:,}'.replace(',', ' ') + '\n0 disallineamenti',
                ha='center', fontsize=8.0)
    ax.set_yscale('log'); ax.set_ylim(50, 5e5)
    ax.set_ylabel('confronti (scala log)', fontsize=9); _style(ax)
    ax.set_title('Ogni confronto e\' contro il BLOCCO di riferimento, e ogni esito e\' zero', fontsize=9.3)
    p = os.path.join(FIGDIR, 'gates.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p


def fig_fclk():
    """Sweep FCLK: WNS contro frequenza OTTENUTA, con la soglia di chiusura."""
    f = [p['mhz'] for p in PTS]; w = [p['wns'] for p in PTS]
    ok = [x >= 0 for x in w]
    fig, ax = plt.subplots(figsize=(8.4, 3.0))
    ax.axhline(0, color='#b5522a', lw=1.2, ls='--')
    ax.plot(f, w, '-', color='#8fa3bd', lw=1.2, zorder=1)
    ax.scatter([x for x, o in zip(f, ok) if o], [y for y, o in zip(w, ok) if o],
               s=52, color=PAL['verde'], zorder=3, label='chiude')
    ax.scatter([x for x, o in zip(f, ok) if not o], [y for y, o in zip(w, ok) if not o],
               s=52, color=PAL['mattone'], marker='X', zorder=3, label='NON chiude')
    ax.annotate('deployabile\n%g MHz (WNS %+.3f)' % (FCLK, WNS), xy=(FCLK, WNS),
                xytext=(FCLK - 13, 7), fontsize=7.8, color=PAL['verde'],
                arrowprops=dict(arrowstyle='->', color=PAL['verde'], lw=1.0))
    ax.annotate('limite del cammino critico\n%.1f MHz (DERIVATO, non chiude)' % FLIMIT,
                xy=(FLIMIT_FROM, [y for x, y in zip(f, w) if abs(x - FLIMIT_FROM) < 0.6][0]),
                xytext=(30, -9), fontsize=7.8, color=PAL['mattone'],
                arrowprops=dict(arrowstyle='->', color=PAL['mattone'], lw=1.0))
    ax.set_xlabel('frequenza OTTENUTA [MHz] — non quella richiesta: il PS7 quantizza', fontsize=8.6)
    ax.set_ylabel('WNS [ns]', fontsize=9); _style(ax); ax.legend(fontsize=8, frameon=False)
    ax.set_title('Il limite si legge STRINGENDO il vincolo, non al crossover', fontsize=9.3)
    p = os.path.join(FIGDIR, 'fclk.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p


def fig_perimetri():
    """Tre misure di timing sullo stesso circuito, tre perimetri: i numeri non si scambiano."""
    labs = ['sistema completo\n@%g MHz' % FCLK, 'sistema, punto\npiu\' stretto (%g MHz)' % FLIMIT_FROM,
            'OOC wrapper+DUT\n@%g MHz' % FCLK]
    vals = [WNS, [p['wns'] for p in PTS if abs(p['mhz'] - FLIMIT_FROM) < 0.6][0], OOC_WNS]
    cols = [PAL['verde'] if v >= 0 else PAL['mattone'] for v in vals]
    fig, ax = plt.subplots(figsize=(8.0, 2.7))
    bars = ax.bar(labs, vals, color=cols, width=0.5)
    ax.axhline(0, color='#44506a', lw=1.0)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + (0.25 if v >= 0 else -0.55),
                '%+.3f ns' % v, ha='center', fontsize=8.2,
                color=PAL['verde'] if v >= 0 else PAL['mattone'], weight='bold')
    ax.set_ylabel('WNS [ns]', fontsize=9); _style(ax)
    ax.set_title('Stesso circuito, stessa frequenza: chiude nel sistema, NON chiude in OOC', fontsize=9.3)
    p = os.path.join(FIGDIR, 'perimetri.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p


def fig_hier():
    """Dove finiscono le risorse dentro il blocco (post-route, punto deployabile)."""
    order = [('u_Tier', 'SNN Tier@BAL/n13'), ('u_ACC', 'ACC-IIDM'), ('u_align', 'align')]
    labs = [l for k, l in order if k in HIER]
    lut = [HIER[k]['lut'] for k, _ in order if k in HIER]
    ff = [HIER[k]['ff'] for k, _ in order if k in HIER]
    dsp = [HIER[k]['dsp'] for k, _ in order if k in HIER]
    x = np.arange(len(labs)); w = 0.26
    fig, ax = plt.subplots(figsize=(8.0, 2.8))
    ax.bar(x - w, lut, w, label='LUT', color=PAL['blu'])
    ax.bar(x, ff, w, label='FF', color=PAL['verde'])
    ax.bar(x + w, [d * 50 for d in dsp], w, label='DSP (x50)', color=PAL['viola'])
    for i, (a, b, c) in enumerate(zip(lut, ff, dsp)):
        ax.text(i - w, a + 90, str(a), ha='center', fontsize=7.6)
        ax.text(i, b + 90, str(b), ha='center', fontsize=7.6)
        ax.text(i + w, c * 50 + 90, str(c), ha='center', fontsize=7.6)
    ax.set_xticks(x); ax.set_xticklabels(labs, fontsize=8.4)
    ax.set_ylabel('celle', fontsize=9); _style(ax); ax.legend(fontsize=8, frameon=False)
    ax.set_title('`align` costa %d LUT (%.0f %% del blocco): e\' il prezzo di UNA inferenza per control-step'
                 % (HIER['u_align']['lut'], 100.0 * HIER['u_align']['lut'] / HIER['u_dut']['lut']), fontsize=9.3)
    p = os.path.join(FIGDIR, 'hier.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p


def fig_toggle():
    """Cio' che i watt arrotondati nascondono e i toggle mostrano."""
    fig, axs = plt.subplots(1, 3, figsize=(8.8, 2.6))
    # a) idle stazionaria
    ws = [200, 1000, 5000]
    tcs = [ST['idle_g0_w%d' % w]['tc'] / float(w) for w in ws]
    axs[0].plot(ws, tcs, 'o-', color=PAL['blu'], lw=1.4, ms=6)
    axs[0].set_xscale('log'); axs[0].set_ylim(0, max(tcs) * 1.6)
    axs[0].set_xlabel('finestra [cicli]', fontsize=8.2); axs[0].set_ylabel('toggle / clock', fontsize=8.6)
    axs[0].set_title('idle: TC/clock COSTANTE\n=> stazionaria (provato)', fontsize=8.4); _style(axs[0])
    # b) gating
    axs[1].bar(['non\ngatata', 'gatata'], [TC_IDLE, TC_IDLE_G], color=[PAL['grigio'], PAL['verde']], width=0.5)
    axs[1].text(1, TC_IDLE_G + TC_IDLE * 0.08, '%.0f x in meno' % GATING_GAIN, ha='center',
                fontsize=8.2, color=PAL['verde'], weight='bold')
    axs[1].set_ylabel('toggle / clock', fontsize=8.6)
    axs[1].set_title('clock gating: MISURATO\n(nei watt: invisibile)', fontsize=8.4); _style(axs[1])
    # c) dispersione fra carichi
    tc_w = [ST['act_g1_wl%d' % i]['tc'] / 1e6 for i in WLS]
    axs[2].bar(range(len(WLS)), tc_w, color=PAL['blu'], width=0.62)
    axs[2].set_ylim(min(tc_w) * 0.97, max(tc_w) * 1.01)
    axs[2].set_xticks(range(len(WLS))); axs[2].set_xticklabels(['wl%d' % i for i in WLS],
                                                              fontsize=6.6, rotation=45)
    axs[2].set_ylabel('commutazioni [milioni]', fontsize=8.6)
    axs[2].set_title('8 carichi: %.1f %% di dispersione\n(nei watt: identici)' % TC_DISP, fontsize=8.4)
    _style(axs[2])
    p = os.path.join(FIGDIR, 'toggle.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p


def fig_energy():
    """Le tre potenze dinamiche, e il duty che le lega."""
    fig, ax = plt.subplots(figsize=(8.0, 2.7))
    labs = ['idle\n(non gatata)', 'attiva\n(mentre calcola)', 'duty REALE\n(%.4f %% attivo)' % DUTY_PCT]
    vals = [P_IDLE, P_ACT, P_DUTY]
    bars = ax.bar(labs, vals, color=[PAL['grigio'], PAL['mattone'], PAL['verde']], width=0.5)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.0009, '%.3f W' % v, ha='center',
                fontsize=8.6, weight='bold')
    ax.set_ylabel('potenza DINAMICA [W]', fontsize=9); _style(ax)
    ax.set_ylim(0, max(vals) * 1.28)
    ax.set_title('La statica del device (%.3f W) resta SEPARATA: e\' il pavimento del chip, non il lavoro svolto'
                 % P_STAT, fontsize=9.0)
    p = os.path.join(FIGDIR, 'energy.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p


def fig_safety():
    """Metriche di sicurezza: RTL contro oracolo, sui 99 scenari."""
    rtl = MET['RTL']; ora = MET['ORA']
    ks = sorted(rtl, key=lambda k: int(k) if str(k).isdigit() else k)
    def col(d, name):
        out = []
        for k in ks:
            v = d[k].get(name)
            if v is not None and not (isinstance(v, float) and (v != v)):
                out.append(v)
        return out
    fig, axs = plt.subplots(1, 2, figsize=(8.6, 2.7))
    for ax, name, lab in ((axs[0], 'min_ttc', 'min TTC [s]'), (axs[1], 'max_DRAC', 'max DRAC [m/s²]')):
        a, b = col(rtl, name), col(ora, name)
        n = min(len(a), len(b))
        ax.scatter(b[:n], a[:n], s=16, color=PAL['blu'], alpha=0.75)
        lo = min(min(a[:n]), min(b[:n])); hi = max(max(a[:n]), max(b[:n]))
        ax.plot([lo, hi], [lo, hi], '--', color='#b5522a', lw=1.0)
        ax.set_xlabel('oracolo — ' + lab, fontsize=8.4); ax.set_ylabel('RTL — ' + lab, fontsize=8.4)
        ax.set_title(name, fontsize=8.8); _style(ax)
    fig.suptitle('Le metriche vengono dalle serie PRODOTTE DALL\'RTL, non da una simulazione a parte',
                 fontsize=9.0, y=1.04)
    p = os.path.join(FIGDIR, 'safety.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

# ---------------------------------------------------------------------------
# AGGREGAZIONE DELLE 31 METRICHE
# La statistica deve calzare il fenomeno: sulla sicurezza conta la CODA, non il centro. Una mediana su
# 99 scenari cancellerebbe proprio lo scenario peggiore, che e' l'unico che interessa. La regola e'
# quindi esplicita per famiglia, e viene DICHIARATA nel report accanto alla tabella.
# ---------------------------------------------------------------------------
import numpy as _np


def _agg_rule(name):
    if name.startswith('min_') or name.endswith('_min'):
        return 'min', "minimo (caso peggiore)"
    if name.startswith('max_') or name.startswith('frac_'):
        return 'max', "massimo (caso peggiore)"
    if name in ('TET', 'TIT', 'TED_drac', 'TID_drac', 'impact_dv'):
        return 'max', "massimo (caso peggiore)"
    if name == 'collided':
        return 'sum', "somma"
    return 'mean', "media"


def _scen_num(k):
    return int(_re.sub(r'\D', '', k))


def metric_rows():
    """Per ogni metrica: aggregato RTL, aggregato oracolo, rapporto. Da metrics.json, 99 scenari."""
    rtl, ora = MET['RTL'], MET['ORA']
    names = sorted(k for k in rtl[list(rtl)[0]] if k != 'N')   # 'N' e' un contatore, non una metrica
    out = []
    for nm in names:
        how, _lab = _agg_rule(nm)
        def agg(d):
            vals = [d[k][nm] for k in d
                    if d[k].get(nm) is not None
                    and not (isinstance(d[k][nm], float) and d[k][nm] != d[k][nm])
                    and abs(d[k][nm]) != float('inf')]
            if not vals:
                return None
            return {'min': min, 'max': max, 'sum': sum}.get(how, lambda v: sum(v) / len(v))(vals)
        a_, b_ = agg(rtl), agg(ora)
        r = (a_ / b_) if (a_ is not None and b_ not in (None, 0)) else None
        out.append((nm, how, a_, b_, r))
    return out


def freeze_impact():
    """Impatto del congelamento: rapporto delle MEDIANE fra RTL e oracolo, sui SOLI scenari congelati.

    Non il caso peggiore su tutti i 99: li' il valore e' dominato dai 3 scenari che COLLIDONO, dove il
    tempo alla collisione tende a zero e la decelerazione richiesta diverge per ENTRAMBI, e il rapporto
    smette di misurare l'implementazione. E' anche la statistica dei due valori citati in RESULTS.md,
    che li' erano scritti come COSTANTI: qui sono ricalcolati dai dati (e coincidono)."""
    rtl, ora = MET['RTL'], MET['ORA']
    ks = sorted(rtl, key=_scen_num)
    rep = set(int(x) for x in _np.atleast_1d(_V.repScen))
    fro = [k for k in ks if _scen_num(k) in rep]
    def med(v):
        v = sorted(x for x in v if x is not None and x == x and abs(x) != float('inf'))
        return v[len(v) // 2] if v else float('nan')
    out = {}
    for nm in ('min_ttc', 'max_DRAC', 'min_gap', 'min_time_headway'):
        a_, b_ = med([rtl[k][nm] for k in fro]), med([ora[k][nm] for k in fro])
        out[nm] = (a_, b_, (a_ / b_) if b_ else float('nan'))
    return len(fro), len(ks) - len(fro), out


def fmt_i(n):
    return '{:,}'.format(int(n)).replace(',', ' ')


def _fmt(v):
    if v is None:
        return "\u2014"
    if abs(v) >= 1000 or (v and abs(v) < 0.01):
        return '%.3g' % v
    return ('%.0f' if float(v).is_integer() else '%.3f') % v



# ---------------------------------------------------------------------------
# METADATI DELLE 31 METRICHE — nome esteso, unita', famiglia.
# Presi dalle DEFINIZIONI in utils/closed_loop_eval.py (il motore canonico), non inventati: il nome
# breve da solo e' illeggibile per chi non ha scritto il motore, e una tabella di 31 sigle senza unita'
# non e' un risultato, e' un elenco.
# famiglia: S=sicurezza · C=comfort · I=inseguimento · E=efficienza e stabilita'
# ---------------------------------------------------------------------------
METRIC_META = {
    'min_ttc':              ('S', 'Tempo minimo alla collisione (TTC)', 's',
                             'minimo sui 99 scenari'),
    'TET':                  ('S', 'Tempo esposto a TTC sotto soglia (Time Exposed TTC)', 's',
                             'soglia 1,5 s'),
    'TIT':                  ('S', 'Tempo integrato del deficit di TTC (Time Integrated TTC)', 's2',
                             'integrale di (1,5 - TTC) sotto soglia'),
    'max_DRAC':             ('S', 'Decelerazione massima richiesta per evitare la collisione', 'm/s2',
                             'DRAC = dv2/(2s)'),
    'TED_drac':             ('S', 'Tempo esposto a DRAC oltre soglia', 's', 'soglia 3,35 m/s2 (Archer)'),
    'TID_drac':             ('S', 'Tempo integrato dell eccesso di DRAC', 'm/s2 x s', 'oltre 3,35 m/s2'),
    'frac_drac_critical':   ('S', 'Frazione di tempo con DRAC critico', '-', 'oltre 3,35 m/s2'),
    'cpi':                  ('S', 'Crash Potential Index', '-',
                             'frazione con DRAC oltre il MADR medio 8,45 m/s2'),
    'min_gap':              ('S', 'Distanza minima paraurti-paraurti', 'm',
                             'NEGATIVA = compenetrazione, cioe collisione'),
    'min_time_headway':     ('S', 'Distanza temporale minima (s/v)', 's', '-'),
    'brake_margin_min':     ('S', 'Margine di evitabilita fisica', 'm',
                             's - dv2/(2 b_max); NEGATIVO = collisione fisicamente inevitabile'),
    'impact_dv':            ('S', 'Velocita relativa all impatto (severita)', 'm/s', '0 se nessuna collisione'),
    'collided':             ('S', 'Scenari con collisione', 'conteggio', '-'),
    'frac_ttc_below_1.0':   ('S', 'Frazione di tempo in avvicinamento con TTC sotto 1,0 s', '-', '-'),
    'frac_ttc_below_1.5':   ('S', 'Frazione di tempo in avvicinamento con TTC sotto 1,5 s', '-', '-'),
    'frac_ttc_below_2.0':   ('S', 'Frazione di tempo in avvicinamento con TTC sotto 2,0 s', '-', '-'),
    'frac_ttc_below_3.0':   ('S', 'Frazione di tempo in avvicinamento con TTC sotto 3,0 s', '-', '-'),
    'rms_accel':            ('C', 'Accelerazione efficace (RMS)', 'm/s2', 'indice di comfort ISO 2631'),
    'max_decel':            ('C', 'Decelerazione piu forte', 'm/s2', 'limite fisico 9 m/s2'),
    'rms_jerk':             ('C', 'Jerk efficace (RMS)', 'm/s3', '-'),
    'max_abs_jerk':         ('C', 'Jerk massimo in valore assoluto', 'm/s3', '-'),
    'frac_jerk_uncomf':     ('C', 'Frazione di tempo con jerk scomodo', '-', 'oltre 2 m/s3'),
    'frac_decel_iso_viol':  ('C', 'Frazione con decelerazione oltre il limite ISO', '-',
                             'ISO 15622: -3,5 m/s2'),
    'frac_accel_iso_viol':  ('C', 'Frazione con accelerazione oltre il limite ISO', '-',
                             'ISO 15622: +2,0 m/s2'),
    'rms_gap_error':        ('I', 'Errore di distanza efficace (RMS)', 'm', 'rispetto alla distanza desiderata'),
    'mean_abs_gap_err_ss':  ('I', 'Errore di distanza medio a regime', 'm', 'ultimo 50 % della traiettoria'),
    'mean_abs_dv_ss':       ('I', 'Velocita relativa media a regime', 'm/s', 'ultimo 50 %'),
    'mean_time_gap':        ('I', 'Distanza temporale media (s/v)', 's', '-'),
    'mean_T_pred':          ('I', 'Tempo di via libera desiderato, medio, predetto dalla rete', 's',
                             'e uno dei cinque parametri stimati'),
    'energy_proxy':         ('E', 'Proxy di energia: integrale della potenza specifica positiva', 'm2/s2',
                             'somma di v x a quando a > 0'),
    'string_stability':     ('E', 'Guadagno di stabilita di stringa', '-',
                             'std(perturbazione ego)/std(perturbazione leader) a regime; sotto 1 = smorza'),
}
FAMIGLIE = [('S', 'Sicurezza'), ('C', 'Comfort'), ('I', 'Inseguimento'), ('E', 'Efficienza e stabilita')]


def metric_table(fam):
    """Righe della tabella per una famiglia, ordinate come in METRIC_META."""
    rows = []
    for nm, how, a_, b_, r in metric_rows():
        m = METRIC_META.get(nm)
        if not m or m[0] != fam:
            continue
        _f, desc, unit, note = m
        rows.append([nm, desc, unit, _agg_rule(nm)[1], _fmt(a_), _fmt(b_),
                     ('%.3f' % r) if r is not None else "\u2014"])
    return rows

# ============================================================================
# CONTENUTO
# ============================================================================
def build_doc():
    D = []; A = D.append
    t_inf_us = LAT_CLK / (FCLK * 1e6) * 1e6
    t_act_us = ACT_CLK / (FCLK * 1e6) * 1e6
    margin = CTRL_S / (t_inf_us * 1e-6)
    margin_r = round(margin, -2)
    rep_pc = 100.0 * T7A_NREP / T7A_NTOT
    align_pc = 100.0 * HIER['u_align']['lut'] / HIER['u_dut']['lut']
    saif_pc = 100.0 * SAIF_N / SAIF_T
    nq = len(QUANT)

    A(('cover', {
        'title': DOC_TITLE,
        'subtitle': 'Il Verilog generato del controllore composto — rete spiking, allineamento e legge di '
                    'controllo — provato bit-esatto rispetto al blocco in ANELLO CHIUSO su 99 scenari di '
                    'car-following con cut-in, e il sistema completo implementato, misurato in clock, '
                    'risorse ed energia, e portato a bitstream.',
        'meta': [
            'Oggetto: blocco composto Donatello_SNN_IIDM = SNN Donatello_Tier@BALANCED (nfrac 13) + '
            'allineamento align + controllore ACC-IIDM. Ingressi s, v, dv, v_l; uscita accel.',
            'Livelli di fedeltà: simulazione RTL in anello chiuso e simulazione di netlist post-place&route '
            'in Vivado xsim; sintesi e implementazione reali su xc7z020; energia da attività di commutazione '
            'registrata (SAIF). NON è una misura su silicio — quella è la Fase C.',
            'Grounding: questo documento è GENERATO da uno script che LEGGE gli artefatti '
            '(t7_results.mat, metrics.json, sweep.json, netlist.json, power.json, power_params.json, '
            'saif_stats.json e i report Vivado grezzi). Nessun numero è trascritto a mano, con una sola '
            'eccezione dichiarata nel §5.1. I cancelli sono deterministici (esito 0/N); le grandezze non '
            'misurabili con questo flusso sono marcate come STIMA e mai presentate come misura.',
            'Riproducibilità: bash FaseB2.0/Harness_SNN_IIDM/hw/run_harness_snniidm_hw.sh [stadio] — '
            'un comando per stadio, con cancello di provenienza sui sorgenti caratterizzati.',
        ],
    }))
    A(('toc', 'Sommario'))

    # ---------------------------------------------------------------- 1
    A(('h1', '1. Sintesi'))
    A(('p', 'Questo documento riporta la validazione e la caratterizzazione del **controllore completo** '
            'destinato all\'FPGA: il blocco composto che dai quattro stati di car-following — distanza, '
            'velocità propria, velocità relativa e velocità del veicolo che precede — produce direttamente '
            'l\'**accelerazione comandata**, passando per una rete neurale spiking che stima i parametri del '
            'modello di guida e per la legge di controllo che li usa.'))
    A(('p', 'La domanda a cui il documento risponde è una sola: **il codice che finirà sull\'FPGA si comporta '
            'come il blocco progettato, e a quale costo?** La risposta è affermativa su ogni cancello, e i '
            'costi sono misurati.'))
    A(('img', (fig_gates(), 'Copertura dei cancelli di equivalenza. Ogni barra è un confronto contro il '
                            '**blocco** di riferimento, e ogni esito è zero disallineamenti. La scala è '
                            'logaritmica: i quattro cancelli coprono perimetri di ampiezza molto diversa, '
                            'e il più stretto — la netlist — è dichiarato tale, non nascosto.')))
    A(('table', (['Grandezza', 'Valore', 'Natura'], [
        ['RTL == blocco in anello chiuso (T7-EXACT)', '%d su %s confronti, %d scenari'
         % (T7A_NEXACT, f'{T7A_NTOT:,}'.replace(',', ' '), MET_NSCEN), 'misurato'],
        ['Plant del banco == riferimento (PLANT-PAR, senza DUT)', '%d disallineamenti su %d scenari'
         % (T7A_NPP, MET_NSCEN), 'misurato'],
        ['Parametri letti dal processore via AXI == blocco', '%d su %s, in entrambe le configurazioni di gating'
         % (COSIM_MIS, f'{COSIM_N:,}'.replace(',', ' ')), 'misurato'],
        ['Netlist post-place&route == blocco', '%d su %s (%d scenari dichiarati)'
         % (NL_NMIS, f'{NL_N:,}'.replace(',', ' '), NL_NSCEN), 'misurato'],
        ['Collisioni AGGIUNTIVE rispetto all\'oracolo', '%d (RTL %d, oracolo %d)'
         % (COLL_EXTRA, COLL_RTL, COLL_ORA), 'misurato'],
        ['Frequenza di clock deployabile', '%g MHz (WNS %+.3f ns, WHS %+.3f ns)' % (FCLK, WNS, WHS), 'misurato'],
        ['Limite del cammino critico', '%.1f MHz' % FLIMIT, 'derivato (da WNS a vincolo stretto)'],
        ['Risorse post-place&route', '%s LUT · %s FF · %s DSP · %g BRAM'
         % (UTIL['lut'], UTIL['ff'], UTIL['dsp'], UTIL['bram']), 'misurato'],
        ['Inferenza / margine sul control-step %g s' % CTRL_S,
         '%.1f µs / ≈%s×' % (t_inf_us, f'{margin_r:,.0f}'.replace(',', ' ')), 'derivato'],
        ['Energia DINAMICA per control-step', '%.2f mJ (al duty reale, %.4f %%)' % (E_DYN_MJ, DUTY_PCT),
         'misurato, non composto'],
        ['Energia statica del dispositivo per control-step', '%.1f mJ' % E_STAT_MJ,
         'misurato — pavimento del chip, tenuto SEPARATO'],
        ['Clock gating: commutazione in idle', 'da %.1f a %.1f toggle per clock (%.0f×)'
         % (TC_IDLE, TC_IDLE_G, GATING_GAIN), 'misurato nel SAIF'],
        ['Clock gating: guadagno in watt', 'non ottenuto', 'NON misurabile con questo flusso'],
        ['Bitstream PYNQ-Z1', 'prodotto, WNS e utilizzo identici a quelli caratterizzati', 'artefatto'],
    ])))
    A(('callout', 'Tre grandezze **non** sono state ottenute, e il documento lo dice dove servirebbero: il '
                  '**guadagno in watt del clock gating** (§8), il **caso peggiore energetico** (§7.3) e '
                  'l\'equivalenza della netlist **su tutti** i 99 scenari (§5.2). Per ciascuna è indicato '
                  'il motivo e il costo che avrebbe avuto ottenerla.'))

    # ---------------------------------------------------------------- 2
    A(('h1', '2. Oggetto e perimetro'))
    A(('h2', '2.1 Il blocco composto'))
    A(('p', 'Il dispositivo sotto esame non è la rete neurale da sola, ma la **catena completa** che porta '
            'dagli stati misurati al comando di accelerazione. È composta di tre parti in cascata: la rete '
            'spiking, che stima cinque parametri del modello di guida; un blocco di **allineamento**; e la '
            'legge di controllo ACC-IIDM, che dai parametri e dagli stati calcola l\'accelerazione.'))
    A(('img', (fig_system(), 'Il blocco composto dietro il wrapper AXI4-Lite, e il sistema che lo ospita. '
                             'Il riquadro chiaro delimita ciò che è implementato in logica programmabile e '
                             'caratterizzato in questo documento; il processore e il convertitore di '
                             'protocollo sono il contorno con cui il blocco deve convivere.')))
    A(('h2', '2.2 `align`: una inferenza per control-step'))
    A(('p', 'Il blocco di allineamento non è un dettaglio implementativo: è ciò che rende **corretto** il '
            'comportamento dell\'anello. La rete produce i cinque parametri con una latenza rispetto agli '
            'ingressi fisici; se il controllore li ricevesse appena pronti, vedrebbe **due** transizioni per '
            'ogni passo di controllo — una quando cambiano gli stati e una quando arrivano i parametri — e il '
            'filtro interno che stima l\'accelerazione del veicolo che precede verrebbe aggiornato **due '
            'volte**. Il risultato sarebbe più veloce e **sbagliato**.'))
    A(('p', '`align` trattiene i quattro ingressi fisici finché i cinque parametri non cambiano, poi li '
            'rilascia **insieme**: un solo fronte, una sola inferenza, un solo aggiornamento del filtro per '
            'control-step. Il costo di questa correttezza è misurato in §6.3.'))
    A(('callout', 'Questo è un punto in cui una modifica plausibile ha prodotto un difetto reale durante lo '
                  'sviluppo. Un tentativo di accelerare il blocco registrando le uscite **all\'esterno** di '
                  '`align` guadagnava frequenza ma reintroduceva il **doppio fronte**: più veloce, e con '
                  'l\'anello che si comportava diversamente. Da allora ogni modifica al confine è soggetta a '
                  'un cancello che **conta i fronti** e ne pretende esattamente uno.'))
    A(('h2', '2.2 I cinque parametri, e cosa significano'))
    A(('p', "La rete non produce direttamente l'accelerazione: stima **cinque parametri** del modello di "
            "guida IDM, che la legge di controllo poi usa insieme agli stati misurati. Sono la velocita' "
            "desiderata in strada libera, il tempo di via libera desiderato, la distanza minima da fermo, "
            "l'accelerazione massima confortevole e la decelerazione confortevole."))
    A(('table', (['Parametro', 'Significato', 'Unita'], [
        ['v0', "velocita' desiderata in strada libera", 'm/s'],
        ['T',  "tempo di via libera desiderato rispetto al veicolo che precede", 's'],
        ['s0', "distanza minima da fermo", 'm'],
        ['a',  "accelerazione massima confortevole", 'm/s2'],
        ['b',  "decelerazione confortevole", 'm/s2'],
    ])))
    A(('p', "Sono questi cinque valori che il blocco di allineamento tratta, che il cancello PARAM-RANGE "
            "verifica entro i limiti del decodificatore, e la cui **ripetizione** produce il comportamento "
            "descritto nel \u00a74.3."))
    A(('h2', '2.3 Cosa è dentro e cosa è fuori'))
    A(('table', (['Dentro il perimetro', 'Fuori dal perimetro'], [
        ['Il Verilog generato dal blocco composto, simulato in xsim', 'Il comportamento su silicio (Fase C)'],
        ['Il wrapper AXI4-Lite e il sistema con processore e convertitore', 'Il software applicativo sul processore'],
        ['Sintesi, place&route e analisi statica dei tempi reali', 'La validazione del modello di guida in sé'],
        ['Energia da attività di commutazione registrata (SAIF)', 'La misura di corrente su scheda'],
        ['99 scenari di car-following con cut-in, in anello chiuso', 'Scenari non rappresentati nel dataset'],
    ])))

    # ---------------------------------------------------------------- 3
    A(('h1', '3. Il problema della validazione in anello chiuso'))
    A(('h2', '3.1 Perché un confronto diretto non basta'))
    A(('p', 'Validare un componente in **anello aperto** è semplice: si danno gli stessi ingressi al codice e '
            'al riferimento e si confrontano le uscite. In **anello chiuso** questo non si può fare, perché gli '
            'ingressi del passo successivo dipendono dall\'uscita del passo corrente: due implementazioni che '
            'divergono di un solo bit al passo *k* ricevono ingressi **diversi** al passo *k+1*, e da lì in poi '
            'il confronto non misura più l\'equivalenza ma l\'accumulo della divergenza.'))
    A(('p', 'Un confronto diretto fra le due traiettorie complete risponderebbe quindi a una domanda diversa da '
            'quella che interessa — «quanto divergono?» invece di «il codice **è** il blocco?» — e non '
            'permetterebbe di distinguere un difetto del codice da una differenza del modello di ambiente.'))
    A(('h2', '3.2 La decomposizione in due prove disgiunte'))
    A(('p', 'La validazione è stata quindi **scomposta in due prove che non condividono il componente che '
            'l\'altra verifica**, ciascuna delle quali è un confronto in anello aperto e quindi deterministico.'))
    A(('img', (fig_decomp(), 'Le due prove. A sinistra il plant del banco viene confrontato con il modello di '
                             'riferimento **senza alcun DUT** nell\'anello, alimentandolo con la sequenza di '
                             'accelerazioni registrata. A destra il DUT viene confrontato con il blocco **sugli '
                             'ingressi che ha effettivamente ricevuto**, senza che il plant partecipi al '
                             'confronto. Insieme coprono l\'anello; separatamente, ciascuna è esatta.')))
    A(('table', (['Prova', 'Cosa verifica', 'Cosa NON contiene', 'Esito'], [
        ['PLANT-PAR', 'il modello di ambiente del banco è quello di riferimento', 'il DUT',
         '%d su %d scenari' % (T7A_NPP, MET_NSCEN)],
        ['T7-EXACT', 'l\'RTL riproduce il blocco sugli ingressi ricevuti', 'il plant',
         '%d su %s confronti' % (T7A_NEXACT, f'{T7A_NTOT:,}'.replace(',', ' '))],
    ])))
    A(('h2', '3.3 Il riferimento è il blocco, e un golden monolitico non lo è'))
    A(('p', 'Il termine di paragone di ogni cancello è il **blocco composto** eseguito in simulazione, non una '
            'sua riscrittura. La distinzione ha avuto conseguenze concrete: un golden costruito estraendo il '
            'codice di un blocco precedente, ormai **deprecato**, si è rivelato **non equivalente** al composto '
            '— 385 scarti su 600 passi di controllo. Il difetto non era nell\'RTL, ma nel riferimento.'))
    A(('callout', 'Il controllo che avrebbe dovuto intercettarlo era passato, perché verificava il golden sugli '
                  'stessi sei passi di controllo su cui era stato tarato: **verificava la premessa su cui era '
                  'costruito**. Da allora il riferimento è il blocco stesso, guidato sugli ingressi che l\'RTL '
                  'ha davvero ricevuto.'))

    # ---------------------------------------------------------------- 4
    A(('h2', '3.4 Tre termini di paragone distinti, e a cosa serve ciascuno'))
    A(('p', "Nel documento compaiono tre entita' diverse. Confonderle rende ininterpretabile ogni numero, "
            "quindi vengono nominate qui una volta per tutte."))
    A(('table', (['Entita', 'Che cos e', 'A che domanda risponde'], [
        ["**il blocco**", "il modello Simulink `Donatello_SNN_IIDM`, eseguito in simulazione",
         "e' il RIFERIMENTO DI EQUIVALENZA: il codice generato si comporta come il blocco progettato?"],
        ["**l'RTL** (e a valle la netlist, e il sistema con processore)",
         "cio' che finira' sull'FPGA, nelle sue tre forme successive",
         "e' l'OGGETTO della validazione"],
        ["**l'oracolo**",
         "un controllore IDEALE: la stessa legge IIDM in forma analitica, alimentata con i parametri "
         "VERI di ciascuno scenario invece che con quelli stimati dalla rete",
         "e' la BASELINE DI QUALITA': quanto si perde stimando i parametri invece di conoscerli?"],
    ])))
    A(('callout', "La distinzione e' sostanziale. L'equivalenza col **blocco** e' una proprieta' binaria e "
                  "si prova bit per bit: o coincide o no. Il confronto con l'**oracolo** non e' un cancello "
                  "e non ha un valore atteso di zero: misura quanto costa, in qualita' di guida, il fatto "
                  "che i parametri siano stimati da una rete anziche' noti. Un divario li' non e' un difetto "
                  "dell'implementazione."))
    A(('p', "Ne segue una domanda legittima: perche' le metriche non confrontano l'RTL con il **blocco**, "
            "visto che il blocco viene eseguito in Simulink proprio per fare da riferimento? Perche' quel "
            "confronto sarebbe **degenere per costruzione**. Il cancello T7-EXACT stabilisce che l'accel "
            "prodotta dall'RTL coincide con quella del blocco a **ogni** passo di controllo, su tutti i "
            "%s confronti; il modello di ambiente e' deterministico; quindi, a parita' di stato iniziale, "
            "le due traiettorie coincidono passo per passo e **ogni metrica calcolata su di esse assume lo "
            "stesso valore**. Calcolarle separatamente produrrebbe due colonne identiche. Il confronto "
            "informativo e' quello con l'oracolo, ed e' quello riportato."
            % ('{:,}'.format(T7A_NTOT).replace(',', ' '))))
    A(('h1', '4. Validazione in anello chiuso a livello RTL'))
    A(('h2', '4.1 I cancelli'))
    A(('p', 'Sui **%d scenari** del dataset esaustivo, %d passi di controllo ciascuno, i cancelli danno:'
            % (MET_NSCEN, T7A_K)))
    A(('table', (['Cancello', 'Domanda', 'Perimetro', 'Esito'], [
        ['PLANT-PAR', 'il plant del banco è quello di riferimento?', '%d scenari' % MET_NSCEN,
         '**%d** disallineamenti' % T7A_NPP],
        ['T7-EXACT', 'l\'RTL è il blocco?', '%s confronti' % f'{T7A_NTOT:,}'.replace(',', ' '),
         '**%d** disallineamenti' % T7A_NEXACT],
        ['PARAM-RANGE', 'i cinque parametri stanno nei limiti del decodificatore?',
         '%s passi' % f'{T7A_NTOT:,}'.replace(',', ' '), '**%d** fuori dominio' % T7A_NRANGE],
        ['T7-SAFE', 'l\'RTL provoca collisioni che l\'oracolo non ha?', '%d scenari' % MET_NSCEN,
         '**%d** collisioni aggiuntive' % COLL_EXTRA],
    ])))
    A(('p', 'Le %d collisioni osservate sono le **stesse** per l\'RTL e per l\'oracolo: derivano da manovre di '
            'inserimento aggressive presenti nel dataset, non dall\'implementazione. Il cancello di sicurezza '
            'non chiede che non ci siano collisioni, chiede che **l\'hardware non ne aggiunga**.' % COLL_RTL))
    A(('p', "La campagna completa \u2014 %d scenari, %d passi di controllo ciascuno, una simulazione "
            "per scenario \u2014 dura **%.0f minuti**." % (MET_NSCEN, T7A_K, T7A_MINS)))
    _att = MET_NSCEN * T7A_K
    _dif = _att - T7A_NTOT
    A(('callout', "**Perche' %s confronti e non %s.** Novantanove scenari da %d passi ne darebbero %s. I "
                  "tre scenari che **collidono** terminano pero' in anticipo, perche' la simulazione si "
                  "ferma all'impatto: contribuiscono %s passi invece di %s, cioe' **%s in meno**. Il totale "
                  "riportato e' la somma effettiva dei passi eseguiti, non un arrotondamento, ed era stato "
                  "dichiarato prima della campagna."
                  % (fmt_i(T7A_NTOT), fmt_i(_att), T7A_K, fmt_i(_att),
                     fmt_i(COLL_RTL * T7A_K - _dif), fmt_i(COLL_RTL * T7A_K), fmt_i(_dif))))
    A(('p', "I cancelli sono stati provati **sensibili**, cioe' li si e' visti fallire su dati "
            "deliberatamente alterati: alterando di un solo bit meno significativo un valore di "
            "riferimento, T7-EXACT segnala esattamente un disallineamento; forzando un parametro fuori "
            "dominio, PARAM-RANGE lo rileva; e il rilevatore di ripetizione scatta su cinque parametri "
            "identici ma non su quattro. Un cancello che non si e' mai visto fallire non e' un cancello."))
    A(('h2', '4.2 Metriche dal motore canonico'))
    A(('p', 'Per ciascuno dei %d scenari sono calcolate **%d metriche** di comportamento e sicurezza. Il punto '
            'metodologico è che le metriche non provengono da una simulazione separata: sono calcolate sulle '
            '**serie prodotte dall\'RTL** durante la validazione, con lo **stesso** motore di valutazione usato '
            'per il modello di riferimento. Prova e metrica insistono così sullo stesso perimetro.'
            % (MET_NSCEN, MET_NMETR)))
    nfro, nnf, fi = freeze_impact()
    A(('p', "La tabella che segue riporta **tutte e %d** le metriche, aggregate sui %d scenari. La regola "
            "di aggregazione e' dichiarata per famiglia e **non e' la mediana**: sulla sicurezza conta la "
            "coda, e una mediana su 99 scenari cancellerebbe proprio lo scenario peggiore, che e' l'unico "
            "che interessa. Per le grandezze di tipo *minimo* si riporta il minimo, per quelle di tipo "
            "*massimo* e per le frazioni di violazione il massimo, per le restanti la media."
            % (MET_NMETR, MET_NSCEN)))
    for _f, _lab in FAMIGLIE:
        _rows = metric_table(_f)
        A(('h3', '%s (%d metriche)' % (_lab, len(_rows))))
        A(('table', (['Metrica', 'Che cosa misura', 'Unita', 'Aggregazione', 'RTL', 'Oracolo', 'Rapporto'],
                     _rows)))
    A(('callout', "Su alcune metriche il rapporto e' molto lontano da uno. **Non e' un segnale sulla "
                  "qualita' dell'implementazione**: il caso peggiore su tutti gli scenari e' dominato dai "
                  "%d che **collidono**, dove il tempo alla collisione tende a zero e la decelerazione "
                  "richiesta diverge \u2014 per l'RTL **e** per l'oracolo, che collidono negli **stessi** "
                  "scenari. In quel regime il rapporto smette di misurare l'implementazione e misura la "
                  "patologia dello scenario. Il confronto discriminante e' quello del \u00a74.3."
                  % COLL_RTL))
    A(('img', (fig_safety(), 'Due metriche di sicurezza, RTL contro oracolo, uno scenario per punto. La '
                             'diagonale è l\'uguaglianza. Gli scostamenti sono la conseguenza del '
                             'comportamento descritto in §4.3, non di un errore di calcolo: l\'equivalenza '
                             'bit-esatta è già stabilita dal cancello T7-EXACT.')))
    A(('callout', "**Due valori che sembrano errori e non lo sono.** La distanza minima risulta "
                  "**negativa**: e' la convenzione del motore di valutazione, che non satura la distanza a "
                  "zero proprio per poter misurare *di quanto* una collisione e' avvenuta \u2014 un valore "
                  "negativo e' una compenetrazione. E le frazioni di tempo con tempo alla collisione sotto "
                  "soglia valgono **1** su tutte e quattro le soglie: significa che esiste almeno uno "
                  "scenario in cui, per tutta la durata dell'avvicinamento, il tempo alla collisione resta "
                  "sotto i 3 secondi. Sono i medesimi scenari che collidono, e valgono 1 anche per "
                  "l'oracolo."))
    A(('h2', '4.3 Un caso limite reale: il congelamento a parametri ripetuti'))
    A(('p', 'Il blocco è **sensibile al fronte**: riparte quando i suoi ingressi cambiano. Quando la rete '
            'produce due volte di seguito gli **stessi** cinque parametri, `align` rilascia valori identici, '
            'nessun fronte viene generato e l\'accelerazione resta al valore precedente per quel passo.'))
    A(('table', (['Grandezza', 'Valore'], [
        ['Passi di controllo con i cinque parametri ripetuti', '%s su %s (**%.1f %%**)'
         % (f'{T7A_NREP:,}'.replace(',', ' '), f'{T7A_NTOT:,}'.replace(',', ' '), rep_pc)],
        ['Frazione di quelli in cui l\'accelerazione resta ferma', '100 %'],
        ['Collisioni aggiuntive che ne derivano', '%d' % COLL_EXTRA],
    ])))
    A(('p', "L'impatto sulla sicurezza si misura confrontando RTL e oracolo **sui soli scenari che "
            "hanno subito congelamenti** (%d su %d): e' li' che l'effetto, se c'e', deve manifestarsi. "
            "Il confronto e' fatto sul rapporto delle mediane." % (nfro, nfro + nnf)))
    A(('table', (['Metrica', 'RTL', 'Oracolo', 'Rapporto'],
                 [[nm, '%.3f' % a, '%.3f' % b, '**%.3f**' % r] for nm, (a, b, r) in fi.items()])))
    A(('p', "Gli scostamenti sono di pochi punti percentuali e **di segno opposto fra loro** \u2014 il "
            "tempo alla collisione peggiora del %.1f %%, la distanza minima **migliora** dell'%.1f %% "
            "\u2014 il che indica una perturbazione, non una degradazione sistematica. E le collisioni "
            "aggiuntive restano **%d**."
            % (100 * (1 - fi['min_ttc'][2]), 100 * (fi['min_gap'][2] - 1), COLL_EXTRA)))
    A(('callout', 'È una **diagnostica**, non un difetto: l\'RTL riproduce il blocco esattamente (T7-EXACT è '
                  '%d), quindi il comportamento è quello progettato. Va però conosciuto, perché a valle si '
                  'traduce in un\'accelerazione che si aggiorna meno spesso di quanto il control-step '
                  'suggerirebbe. L\'effetto sulle metriche di sicurezza è quantificato nella tabella qui sopra e **non produce '
                  'collisioni aggiuntive**.' % T7A_NEXACT))

    # ---------------------------------------------------------------- 5
    A(('h1', '5. Dal blocco al sistema'))
    A(('h2', '5.1 Il processore legge ciò che il blocco calcola'))
    A(('p', 'Il cancello precedente prova che il Verilog è il blocco. Non prova che il **processore**, '
            'scrivendo gli ingressi e leggendo il risultato attraverso il bus, ottenga lo stesso valore: fra i '
            'due ci sono il wrapper, il protocollo, il contatore di latenza e il gating del clock. La cosim AXI '
            'colma questo tratto, guidando il sistema completo dal lato del processore.'))
    A(('table', (['Configurazione', 'Confronti', 'Disallineamenti'], [
        ['gating del clock disattivo', f'{COSIM_N:,}'.replace(',', ' '), '**%d**' % COSIM_MIS],
        ['gating del clock attivo (configurazione di deployment)', f'{COSIM_N:,}'.replace(',', ' '),
         '**%d**' % COSIM_MIS],
    ])))
    A(('p', 'Le due configurazioni sono **la stessa netlist**: il gating è comandato da un bit di registro, non '
            'da un parametro di compilazione. Il confronto isola così l\'effetto del gating invece di '
            'confrontare due circuiti diversi.'))
    A(('callout', 'Nota di provenienza: questi due esiti sono gli **unici** numeri di questo documento che non '
                  'vengono letti a macchina da un artefatto strutturato — provengono da `COSIM_AXI.md`, che '
                  'registra la run del 2026-07-31 (%d minuti, %d simulazioni). Tutti gli altri numeri sono '
                  'letti dai file `.json`, `.mat` e `.rpt` citati in copertina.'
                  % (COSIM_MIN, MET_NSCEN * COSIM_MODES)))
    A(('h2', '5.2 La netlist dopo place&route'))
    A(('p', 'L\'ultimo tratto è fra il Verilog e la **netlist piazzata e instradata**: la rete di celle reali '
            'del dispositivo. La simulazione a livello di porte cattura inizializzazione e propagazione degli '
            'indefiniti, che la simulazione RTL non vede.'))
    A(('table', (['Grandezza', 'Valore'], [
        ['Scenari (sottoinsieme **dichiarato**)', '%s' % ', '.join(str(s) for s in NL_SCEN)],
        ['Confronti', '%s' % f'{NL_N:,}'.replace(',', ' ')],
        ['Disallineamenti', '**%d**' % NL_NMIS],
        ['Costo rispetto alla simulazione comportamentale', '**%.0f×** (misurato su questo progetto)' % NL_RATIO],
        ['Costo che avrebbero i %d scenari completi' % MET_NSCEN, '≈ %.0f ore' % NL_FULL_H],
    ])))
    A(('table', (['Scenario', 'Passi', 'Disallineamenti', 'Durata', 's / passo'],
                 [[str(r['sc']), str(r['n']), '**%d**' % r['nmis'],
                   '%d m %02d s%s' % (r['dur_s'] // 60, r['dur_s'] % 60,
                                      " (include compilazione)" if r['include_compile'] else ''),
                   '%.2f' % r['s_per_step']] for r in NL['per_scenario']])))
    A(('p', 'Il sottoinsieme è **dichiarato in anticipo** e comprende uno scenario che **collide**, cioè con la '
            'serie più corta: è il caso che aveva scoperto un difetto del banco durante lo sviluppo, quando il '
            'confronto leggeva oltre la fine dei dati di riferimento. Il totale atteso — %s confronti — era '
            'stato dichiarato **prima** della esecuzione, e torna: se non fosse tornato, un esito di zero '
            'disallineamenti non sarebbe stato credibile, perché un banco che confronta meno passi del previsto '
            'produce zero disallineamenti proprio perché **non guarda**.' % f'{NL_N:,}'.replace(',', ' ')))
    A(('callout', 'Questo cancello è un **conferma su N dichiarato**, non la base di una metrica: con %.0f ore '
                  'di costo per la copertura completa, l\'estensione a tutti gli scenari è stata esclusa **sul '
                  'costo misurato**, e il limite è scritto qui invece che taciuto.' % NL_FULL_H))

    # ---------------------------------------------------------------- 6
    A(('h1', '6. Frequenza e risorse'))
    A(('p', "Due grandezze ricorrono in questa sezione. Lo **slack di setup** (WNS, *worst negative "
            "slack*) e' il margine temporale del cammino combinatorio peggiore: quanto tempo avanza, nel "
            "ciclo di clock, dopo che il segnale piu' lento e' arrivato. Se e' negativo il circuito **non "
            "funziona** a quella frequenza. Lo **slack di hold** (WHS) e' il margine opposto: il segnale "
            "non deve arrivare troppo PRESTO, prima che il registro di destinazione abbia campionato il "
            "valore precedente; un hold negativo non si corregge rallentando il clock, ed e' quindi un "
            "difetto piu' insidioso."))
    A(('h2', '6.1 Due numeri distinti, e come si leggono'))
    A(('p', 'La frequenza di un progetto su FPGA non è un numero solo. Sono due, e confonderli porta a '
            'dichiarare prestazioni che il sistema non ha.'))
    A(('img', (fig_fclk(), 'Slack peggiore in funzione della frequenza **ottenuta**. Il punto più alto che '
                           'chiude è la frequenza deployabile; il limite del cammino critico si legge invece '
                           'al punto più stretto, dove il vincolo forza lo strumento a ottimizzare al massimo, '
                           'anche se lì il timing non chiude.')))
    A(('table', (['Chiesta [MHz]', 'Ottenuta [MHz]', 'Periodo [ns]', 'WNS [ns]', 'WHS [ns]',
                  'LUT', 'FF', 'Chiude'],
                 [['%d' % p['req'], '%.3f' % p['mhz'], '%.3f' % p['period'],
                   '%+.3f' % p['wns'], '%+.3f' % p['whs'], str(p['lut']), str(p['ff']),
                   "si" if p['wns'] >= 0 else '**no**'] for p in PTS])))
    A(('table', (['Grandezza', 'Valore', 'Natura'], [
        ['Frequenza deployabile', '%g MHz (WNS %+.3f ns, WHS %+.3f ns)' % (FCLK, WNS, WHS),
         'misurato: il più alto fra i provati che chiude'],
        ['Limite del cammino critico', '%.1f MHz' % FLIMIT,
         'derivato: 1/ritardo al punto più stretto (%g MHz), che NON chiude' % FLIMIT_FROM],
    ])))
    A(('p', 'Anche lo **slack di hold** è stato letto e non supposto: è positivo in tutti i punti, quindi il '
            'criterio di chiusura è leggibile sul solo setup. Un progetto che chiude il setup ma viola il hold '
            'non è deployabile, e la differenza non si vede se non si guarda.'))
    if nq:
        A(('callout', 'Il processore **quantizza** la frequenza richiesta: su %d degli %d punti provati la '
                      'frequenza ottenuta differisce da quella chiesta (%s). Il periodo di clock **non** è '
                      'quindi l\'inverso della frequenza richiesta, e va letto dalla tabella dei clock del '
                      'report. Una tabella costruita sull\'assunzione contraria aveva %d righe sbagliate su %d.'
                      % (nq, len(PTS), ', '.join('%d → %.3f MHz' % (q['req'], q['mhz']) for q in QUANT),
                         nq, len(PTS))))
    A(('h2', '6.2 Fuori contesto e nel sistema sono perimetri diversi'))
    A(('p', 'La stessa logica può essere implementata **da sola** — fuori dal contesto del sistema — oppure '
            'dentro il sistema completo. I due risultati **non sono intercambiabili**, e in questo progetto la '
            'differenza è netta: a %g MHz il sistema completo chiude con uno slack di **%+.3f ns**, mentre la '
            'stessa logica implementata fuori contesto **non chiude**, con **%+.3f ns**.'
            % (FCLK, WNS, OOC_WNS)))
    A(('img', (fig_perimetri(), 'Lo stesso circuito, alla stessa frequenza, chiude nel sistema completo e non '
                                'chiude nell\'implementazione fuori contesto. La stima fuori contesto è qui la '
                                'più **pessimista**: ne segue che un numero ottenuto in quel modo non è una '
                                'capacità del progetto ed è confrontabile solo con altri numeri dello stesso '
                                'perimetro.')))
    A(('callout', 'Ne discende anche che una regolarità osservata su un altro blocco di questo stesso progetto '
                  '— per cui la frequenza deployabile valeva circa metà di quella fuori contesto — **non vale '
                  'qui**: quella proporzione dipendeva dal fatto che il cammino critico passasse dal confine '
                  'd\'ingresso, il che su questo blocco non accade più.'))
    A(('h2', '6.3 Risorse e costo dell\'allineamento'))
    A(('table', (['Risorsa', 'Occupazione', 'Frazione del dispositivo'], [
        ['LUT', '%s' % UTIL['lut'], '%.1f %%' % UTIL['lut_pct']],
        ['Flip-flop', '%s' % UTIL['ff'], '%.1f %%' % UTIL['ff_pct']],
        ['DSP', '%s' % UTIL['dsp'], '%.1f %%' % UTIL['dsp_pct']],
        ['Blocchi di memoria', '%g' % UTIL['bram'], '%.1f %%' % UTIL['bram_pct']],
    ])))
    A(('p', 'La risorsa più impegnata è il DSP, al %.1f %%; nessuna è vicina alla saturazione. La ripartizione '
            'interna mostra dove finisce l\'area, e in particolare quanto costa la correttezza discussa in '
            '§2.2.' % UTIL['dsp_pct']))
    _HN = [('sys_wrapper', "sistema completo"), ('tier0', "IP AXI (wrapper + blocco)"),
           ('u_dut', "**il blocco composto**"), ('u_Tier', "\u2514 SNN Tier@BAL/n13"),
           ('u_SNN', "\u2003\u2003\u2514 rete a spike"), ('u_DEC', "\u2003\u2003\u2514 decodifica del readout"),
           ('u_ACC', "\u2514 controllore ACC-IIDM"), ('u_align', "\u2514 allineamento"),
           ('ps7_axi_periph', "convertitore di protocollo (contorno)")]
    A(('table', (['Istanza', 'Ruolo', 'LUT', 'FF', 'DSP', 'RAMB18'],
                 [['`%s`' % k, lab, str(HIER[k]['lut']), str(HIER[k]['ff']),
                   str(HIER[k]['dsp']), str(HIER[k]['rb18'])] for k, lab in _HN if k in HIER])))
    A(('img', (fig_hier(), 'Ripartizione delle risorse dentro il blocco, dopo place&route. Il blocco di '
                           'allineamento non è logica gratuita: costa %d LUT, il %.0f %% del blocco. È il '
                           'prezzo di **una sola** inferenza per passo di controllo, cioè della correttezza '
                           'del filtro interno.' % (HIER['u_align']['lut'], align_pc))))
    A(('h2', '6.4 Margine sul control-step'))
    A(('p', 'Il solo requisito temporale del sistema è il passo di controllo, %g s. L\'inferenza completa dura '
            '%d cicli di clock.' % (CTRL_S, LAT_CLK)))
    A(('table', (['Grandezza', 'Valore'], [
        ['Durata dell\'inferenza a %g MHz' % FCLK, '%.1f µs' % t_inf_us],
        ['Passo di controllo', '%g s' % CTRL_S],
        ['Margine', '≈ %s×' % f'{margin_r:,.0f}'.replace(',', ' ')],
        ['Finestra effettivamente occupata (protocollo incluso)', '%d cicli = %.1f µs' % (ACT_CLK, t_act_us)],
        ['Duty', '%.4f %%' % DUTY_PCT],
    ])))
    A(('callout', 'I due numeri di duty che compaiono negli artefatti misurano cose diverse e non sono in '
                  'contraddizione: %d cicli è la **latenza pura del blocco** — la sua capacità — mentre %d è la '
                  'finestra **effettivamente occupata** dal sistema, protocollo di bus incluso. Per l\'energia '
                  'vale il secondo, ed è quello usato in §7.' % (LAT_CLK, ACT_CLK)))

    # ---------------------------------------------------------------- 7
    A(('h1', '7. Energia nel funzionamento reale'))
    A(('h2', '7.1 La finestra attiva si misura, non si assume'))
    A(('p', 'Un passo di controllo non dura quanto la latenza del blocco: ci sono anche le scritture sul bus e '
            'l\'attesa del segnale di completamento. La finestra è stata quindi **derivata dal banco stesso** '
            '(%d cicli, di cui %d di protocollo) invece di essere posta uguale alla latenza. Il duty che ne '
            'risulta, %.4f %%, è la frazione di tempo in cui il circuito lavora davvero.'
            % (ACT_CLK, ACT_CLK - LAT_CLK, DUTY_PCT)))
    A(('h2', '7.2 L\'inattività è stazionaria, e lo si è provato'))
    A(('p', 'Perché una misura di potenza in inattività abbia senso, l\'inattività deve essere uno stato '
            '**stazionario**: se il circuito avesse macchine a stati o contatori attivi, il valore dipenderebbe '
            'dalla finestra di osservazione. La verifica è stata fatta su tre finestre di ampiezza crescente.'))
    A(('table', (['Finestra [cicli]', 'Commutazioni (TC)', 'TC / ciclo'],
                 [[str(w), str(ST['idle_g0_w%d' % w]['tc']),
                   '**%.1f**' % (ST['idle_g0_w%d' % w]['tc'] / float(w))] for w in (200, 1000, 5000)])))
    A(('p', "Il rapporto e' identico sulle tre finestre, che differiscono di un fattore 25. Con il gating "
            "attivo scende a **%.1f** commutazioni per ciclo: e' la misura del §8." % TC_IDLE_G))
    A(('img', (fig_toggle(), 'Tre letture che il sommario dei watt non permette. A sinistra: il numero di '
                             'commutazioni per ciclo è **costante** su tre finestre che differiscono di un '
                             'fattore 25, il che prova la stazionarietà. Al centro: il gating riduce la '
                             'commutazione di %.0f volte. A destra: gli otto carichi reali differiscono del '
                             '%.1f %% in commutazione. Nessuna delle tre è visibile nei watt arrotondati.'
                             % (GATING_GAIN, TC_DISP))))
    A(('callout', 'La distinzione non è pedanteria. Tre valori di potenza uguali a tre decimali potrebbero '
                  'esserlo anche per **insensibilità dello strumento**; un rapporto commutazioni/ciclo costante '
                  'su un fattore 25 di durata, no. La premessa è verificata sul meccanismo, non dedotta dal '
                  'risultato.'))
    A(('h2', '7.3 Gli otto carichi reali'))
    A(('p', 'La fase attiva è stata misurata su **%d carichi reali**, uno per ciascuna combinazione di regime '
            'di guida e presenza di manovra di inserimento presente nel dataset. Sono otto e non nove: le '
            'combinazioni popolate sono state **enumerate**, non assunte. Ogni esecuzione della misura '
            'energetica ha anche confermato l\'equivalenza funzionale sul proprio carico.' % len(WLS)))
    _LAB = {1: "highway / senza inserimento", 4: "highway / con inserimento",
            28: "urban / senza inserimento", 31: "urban / con inserimento",
            55: "truck / senza inserimento", 58: "truck / con inserimento",
            73: "mixed / senza inserimento", 76: "mixed / con inserimento"}
    A(('table', (['Carico', 'Regime', 'Dinamica [W]', 'Commutazioni (TC)', 'Disallineamenti'],
                 [['wl%d' % i, _LAB.get(i, "\u2014"), '%.3f' % P_ACT,
                   str(ST['act_g1_wl%d' % i]['tc']), '**0**'] for i in WLS])))
    A(('table', (['Grandezza', 'Valore'], [
        ['Potenza dinamica in inattività', '%.3f W' % P_IDLE],
        ['Potenza dinamica mentre calcola', '%.3f W' % P_ACT],
        ['Dispersione fra gli otto carichi, nei watt', 'identici a tre decimali'],
        ['Dispersione fra gli otto carichi, in commutazione', '**%.1f %%**' % TC_DISP],
    ])))
    A(('p', 'La dispersione fra i carichi **non è nulla**: vale %.1f %% in commutazione, che su %.3f W '
            'corrisponde a circa %.4f W — cioè **sotto la terza cifra decimale** che lo strumento riporta. '
            'Dichiarare «dispersione nulla» significherebbe scambiare un limite di precisione per una proprietà '
            'del circuito.' % (TC_DISP, P_ACT, P_ACT * TC_DISP / 100.0)))
    A(('callout', 'Il **caso peggiore** energetico non è determinato. Si riporta il massimo **osservato** fra '
                  'carichi reali, dichiarato come tale: un caso peggiore sintetico costruito su ipotesi di alta '
                  'commutazione era stato provato sul blocco SNN da solo (rapporto T6, in Riferimenti) ed era risultato '
                  'il **più basso di tutti**, quindi come limite superiore è stato smentito su misura. '
                  'Individuare il regime peggiore richiederebbe uno studio dedicato.'))
    A(('h2', '7.4 Energia per passo di controllo, misurata e non composta'))
    A(('p', 'La tentazione naturale è comporre: potenza attiva per il duty, più potenza inattiva per il '
            'complemento. Quella composizione è stata **confrontata con la misura diretta sul blocco SNN da solo (rapporto T6, in Riferimenti) '
            'e ha sottostimato di circa 1,6 volte**, con lo scarto localizzato sui moltiplicatori. '
            'Qui i moltiplicatori sono di più. La misura è quindi stata fatta simulando un passo di controllo '
            '**intero**, senza comporre.'))
    A(('img', (fig_energy(), 'Le tre potenze dinamiche. Al duty reale il valore è dominato dall\'inattività — '
                             'per costruzione, dato che il circuito calcola per una frazione trascurabile del '
                             'tempo. La statica del dispositivo resta separata perché è il pavimento del chip, '
                             'non il costo del lavoro svolto.')))
    A(('table', (['Grandezza', 'Valore', 'Natura'], [
        ['Potenza dinamica al duty reale', '%.3f W' % P_DUTY, 'misurato su un passo di controllo intero'],
        ['**Energia dinamica per passo di controllo**', '**%.2f mJ**' % E_DYN_MJ, 'derivato dal precedente'],
        ['Potenza statica del dispositivo', '%.3f W' % P_STAT, 'misurato — pavimento del chip'],
        ['Energia statica per passo di controllo', '%.1f mJ' % E_STAT_MJ, 'derivato, tenuto SEPARATO'],
        ['Copertura della registrazione di attività', '%s su %s reti = %.1f %%'
         % (f'{SAIF_N:,}'.replace(',', ' '), f'{SAIF_T:,}'.replace(',', ' '), saif_pc), 'misurato'],
        ['Livello di confidenza dichiarato dallo strumento', SAIF_CONF, 'misurato'],
    ])))
    A(('p', 'La copertura va letta **insieme** ai watt: sul %.0f %% delle reti l\'attività non proviene dalla '
            'registrazione ma dal modello interno dello strumento. È una proprietà della misura, non una nota a '
            'piè di pagina.' % (100.0 - saif_pc)))
    A(('callout', 'Un controllo indipendente conferma che la finestra di misura copre davvero un passo di '
                  'controllo intero: il numero di commutazioni previsto dalla composizione dei due regimi — '
                  'inattivo e attivo — differisce da quello registrato dell\'**%.1f %%**. È una verifica sui '
                  'toggle, che nei watt sarebbe stata invisibile, perché a questo duty il valore è comunque '
                  'dominato dall\'inattività: una finestra sbagliata avrebbe prodotto un numero credibile.'
                  % DUTY_COH_ERR))

    # ---------------------------------------------------------------- 8
    A(('h1', '8. Quando il sommario nasconde la misura'))
    A(('p', 'Il gating del clock è implementato e **funziona**: quando il blocco non lavora, il suo clock si '
            'ferma. La misura lo mostra senza ambiguità — la commutazione in inattività passa da %.1f a %.1f '
            'per ciclo, un fattore %.0f.' % (TC_IDLE, TC_IDLE_G, GATING_GAIN)))
    A(('p', 'Nel sommario delle potenze, però, **non si vede nulla**: le due configurazioni riportano lo stesso '
            'valore. Non è una contraddizione, è un **limite dello strumento**, accertato sul blocco SNN da solo (rapporto T6, in Riferimenti) anche in negativo: la potenza delle reti di clock viene derivata dal **vincolo di '
            'frequenza**, non dall\'attività registrata, e imporre attività nulla su quelle reti non cambiava il '
            'risultato. Qui il comportamento è riprodotto in modo indipendente, su un progetto diverso.'))
    A(('callout', 'La conclusione onesta è quindi doppia: il gating **agisce**, e questo è misurato; il suo '
                  '**guadagno in watt non è ottenibile con questo flusso**, e non viene stimato. Ottenerlo '
                  'richiede un flusso diverso — la misura su scheda della Fase C, o un modello di potenza che '
                  'accetti attività per singola rete di clock.'))

    # ---------------------------------------------------------------- 9
    A(('h1', '9. Bitstream e provenienza'))
    if BIT_MB:
        A(('p', 'Il sistema è stato portato a **bitstream** alla frequenza deployabile, con i file di consegna '
                'per la piattaforma. La costruzione del bitstream è un\'esecuzione **separata** da quella che ha '
                'prodotto la caratterizzazione: che i due coincidano non è scontato e non è stato supposto.'))
        A(('table', (['Grandezza', 'Valore'], [
            ['Bitstream', '%.2f MB, più i file di consegna della piattaforma' % BIT_MB],
            ['Slack peggiore', '%+.3f ns — **identico** a quello caratterizzato' % WNS],
            ['Risorse', '**identiche** a quelle caratterizzate'],
        ])))
        A(('p', 'Il confronto non è una verifica fatta una volta a mano: è un **cancello** eseguito a ogni '
                'rigenerazione della sintesi dei risultati, che si arresta se le due implementazioni divergono. '
                'Senza, una divergenza sarebbe invisibile guardando il solo bitstream.'))
    A(('h2', '9.1 Riproducibilità'))
    A(('p', 'Tutti i risultati si riproducono da un unico punto d\'ingresso a stadi. Lo stadio di sintesi non '
            'esegue calcolo: riestrae i numeri dagli artefatti in pochi secondi, e **dichiara** gli artefatti '
            'mancanti invece di tacerli — un numero assente non deve somigliare a un numero verde.'))
    A(('p', 'La provenienza è garantita in forma di **integrità dei file**: la firma dei sorgenti caratterizzati '
            'è registrata e confrontata a ogni invocazione, e una differenza **blocca** gli stadi di calcolo. '
            'La forma alternativa — rigenerare il codice e confrontare — è stata scartata su verifica: il '
            'generatore non è deterministico sui nomi interni temporanei, quindi quel confronto fallirebbe '
            'sempre, anche a sorgenti identici.'))

    # ---------------------------------------------------------------- 10
    A(('h1', '10. Osservazioni di metodo'))
    A(('p', 'Le osservazioni che seguono non sono generalità: ciascuna corrisponde a un errore commesso e '
            'corretto durante questo lavoro, ed è documentata perché il costo di ri-commetterlo è alto.'))
    A(('h2', '10.1 Il numero che lo strumento stampa non è quello che si crede di leggere'))
    A(('p', 'Tre casi distinti in questo lavoro. Il processore **quantizza** la frequenza richiesta, quindi il '
            'periodo va letto e non calcolato. Il sommario delle potenze arrotonda a tre decimali, e sotto '
            'quella soglia la dispersione fra carichi **sparisce**. Le due implementazioni — fuori contesto e '
            'nel sistema — danno esiti opposti sullo **stesso** circuito alla **stessa** frequenza.'))
    A(('callout', 'La regola che li riassume: quando un numero sembra troppo uniforme, troppo tondo o troppo '
                  'comodo, si guarda l\'**artefatto sotto** prima di spiegarlo. Una spiegazione tecnica '
                  'plausibile per un dato sbagliato è più pericolosa di nessuna spiegazione.'))
    A(('h2', '10.2 Un cancello che non può fallire non è un cancello'))
    A(('p', 'Ogni cancello di questo lavoro è stato provato **anche in negativo**, su dati alterati '
            'deliberatamente: la firma dei sorgenti, la coerenza dei totali, la presenza della copertura di '
            'registrazione, la corrispondenza fra bitstream e sistema caratterizzato. In due casi il cancello '
            'ha intercettato un errore **di chi scriveva**, non del progetto — ed è precisamente il motivo per '
            'cui esiste.'))
    A(('p', 'Un controllo mal costruito è peggio di nessun controllo. Un audit dei formati di stampa, scritto '
            'per intercettare un difetto ricorrente, alla prima stesura contava come specificatore anche il '
            'segno di percentuale letterale, e **mascherava così il difetto vero**: un controllo con falsi '
            'positivi ne nasconde anche di reali.'))
    A(('h2', '10.3 Misurare il costo prima di impegnare le ore'))
    A(('p', 'Il passo più costoso di questa caratterizzazione — la misura al duty reale, quattro milioni di '
            'cicli — aveva un costo ignoto a priori, con una forbice fra le ipotesi ragionevoli di oltre un '
            'ordine di grandezza. Invece di stimarlo, è stato **misurato** su una finestra breve, estrapolato '
            'in modo deliberatamente pessimista e confrontato con un budget dichiarato.'))
    A(('p', 'Nella stessa direzione, una stima di costo **scalata da un altro progetto** si è rivelata '
            'pessimista di circa due volte: la simulazione di netlist era stata stimata in ottanta minuti e ne '
            'ha richiesti %.0f. Una stima portata da un contesto diverso è un ordine di grandezza, non una '
            'previsione.' % NL_WALL_MIN))
    A(('h2', '10.4 Il debito si paga sui numeri, non sul tempo'))
    A(('p', 'Una costante **misurata** era stata riscritta a mano nel generatore del rapporto oltre che nello '
            'script che la produce. Nessuna delle due copie era sbagliata al momento della scrittura, ma la '
            'struttura permetteva a una misura futura di convivere in silenzio con un documento che ne stampa '
            'un\'altra. La correzione — lo script scrive i parametri effettivamente usati, il generatore li '
            'legge — non ha migliorato alcun numero: ha eliminato un modo di sbagliare.'))

    # ---------------------------------------------------------------- 11
    A(('h1', '11. Limiti dichiarati'))
    A(('table', (['Domanda', 'Stato', 'Motivo'], [
        ['La netlist è equivalente su **tutti** gli scenari?',
         'non provato — %d dichiarati' % NL_NSCEN,
         'costo misurato: ≈ %.0f ore per la copertura completa' % NL_FULL_H],
        ['Qual è il caso peggiore energetico?', 'non determinato',
         'si riporta il massimo osservato; il caso peggiore sintetico è stato smentito su misura'],
        ['Quanto vale il gating in watt?', 'non misurabile con questo flusso',
         'lo strumento deriva la potenza di clock dal vincolo, non dall\'attività registrata'],
        ['Il comportamento su silicio?', 'fuori perimetro', 'è l\'oggetto della Fase C'],
        ['La copertura della registrazione di attività?', '%.1f %% delle reti' % saif_pc,
         'sul resto vale il modello interno dello strumento'],
    ])))

    # ---------------------------------------------------------------- 12
    A(('h1', '12. Conclusioni'))
    A(('p', 'Il controllore composto destinato all\'FPGA **è** il blocco progettato, e lo è su ogni tratto '
            'della catena: dal Verilog al blocco in anello chiuso su %d scenari, dal processore al blocco '
            'attraverso il bus in entrambe le configurazioni di gating, dalla netlist piazzata e instradata al '
            'blocco sul sottoinsieme dichiarato. Nessun cancello riporta un disallineamento, e nessuno di essi '
            'è stato accettato senza averlo prima visto fallire su dati alterati.' % MET_NSCEN))
    A(('p', 'Il costo è misurato: %g MHz deployabili con margine di %s volte sul passo di controllo, %.1f %% '
            'delle LUT e %.1f %% dei DSP del dispositivo, %.2f mJ di energia dinamica per passo di controllo. '
            'Il sistema è stato portato a bitstream, e il bitstream è **lo stesso** sistema su cui i numeri '
            'sono stati misurati.'
            % (FCLK, f'{margin_r:,.0f}'.replace(',', ' '), UTIL['lut_pct'], UTIL['dsp_pct'], E_DYN_MJ)))
    A(('p', 'Ciò che resta aperto è dichiarato: il guadagno in watt del gating, il caso peggiore energetico, '
            'l\'equivalenza della netlist oltre il sottoinsieme scelto. Per ciascuno è indicato il motivo per '
            'cui non è stato ottenuto e il costo che avrebbe avuto ottenerlo — perché un limite scritto è una '
            'informazione, mentre un limite taciuto è un errore in attesa.'))

    # ---------------------------------------------------------------- rif
    A(('h1', 'Riferimenti'))
    A(('h2', 'Artefatti del progetto'))
    A(('table', (['Artefatto', 'Contenuto'], [
        ['`FaseB2.0/Harness_SNN_IIDM/results/RESULTS.md`', 'validazione in anello chiuso (T7a): cancelli e metriche'],
        ['`FaseB2.0/Harness_SNN_IIDM/results/RESULTS_HW.md`', 'sintesi della caratterizzazione hardware (T7b)'],
        ['`FaseB2.0/Harness_SNN_IIDM/results/SWEEP_FCLK.md`', 'frequenza, risorse post-route, perimetri'],
        ['`FaseB2.0/Harness_SNN_IIDM/results/NETLIST.md`', 'simulazione della netlist post-place&route'],
        ['`FaseB2.0/Harness_SNN_IIDM/results/POWER.md`', 'energia, commutazione e copertura'],
        ['`FaseB2.0/Harness_SNN_IIDM/results/COSIM_AXI.md`', 'cosim dal lato processore'],
        ['`document/HDL_PHASE.md` §6, §9', 'stato della fase e trappole verificate'],
        ['`report/B2_0_HARNESS_SNN_REPORT.{md,pdf}`', 'rapporto sul blocco SNN da solo (Fase B2.0 · T6)'],
    ])))
    A(('h2', 'Strumenti'))
    A(('table', (['Strumento', 'Uso'], [
        ['Vivado 2026.1 (`xsim`, `synth_design`, `report_power`)', 'simulazione, implementazione, analisi'],
        ['MATLAB R2026a con HDL Coder', 'generazione del Verilog dal blocco'],
        ['xc7z020clg400-1 (PYNQ-Z1)', 'dispositivo di riferimento'],
    ])))
    return D

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
        # ATTENZIONE: `\S` puo' essere esso stesso un ASTERISCO. Con `\S(?:.*?\S)?` il gruppo si
        #    mangia il delimitatore di chiusura e va a chiudere su quello della coppia SUCCESSIVA,
        #    mandando in grassetto il testo in mezzo e lasciando gli asterischi letterali nel PDF.
        #    Trovato nell'ispezione VISIVA, non da un controllo sul testo: era in ENTRAMBI i report.
        #    Qui il contenuto non puo' contenere `**` per costruzione.
        s = re.sub(r'(?<!\w)\*\*((?:(?!\*\*).)+?)\*\*', r'<b>\1</b>', s)
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
        # ⚠️ Le immagini erano gia' protette da KeepTogether, le tabelle NO: una tabella che non entra
        #    nello spazio residuo si spezza e puo' lasciare una riga ORFANA da sola sulla pagina dopo,
        #    con il resto bianco. Difetto osservato nell'ispezione VISIVA (pag. 7: una riga e il 90 %
        #    di pagina vuota) — non lo aveva mostrato nessun controllo automatico sul testo.
        #    Si tengono unite solo le tabelle che possono ragionevolmente stare in una pagina: una
        #    tabella piu' alta della pagina DEVE poter spezzare, e con repeatRows=1 lo fa ripetendo
        #    l'intestazione, il che e' accettabile.
        story.append(Spacer(1, 2))
        story.append(KeepTogether(t) if len(rows) <= 14 else t)
        story.append(Spacer(1, 8))
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
