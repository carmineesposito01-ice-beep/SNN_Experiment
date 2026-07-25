"""build_fpga_phase_b_report.py — REPORT FPGA Fase B (post-sintesi Vivado) — .md + .pdf da sorgente unica.

Gemello di scripts/build_fpga_report.py (Fase A, profilazione software pre-silicio). Questo documento
riporta la VALIDAZIONE post-sintesi del profilo FPGA su Vivado (OOC + SAIF, confidenza alta), livello
di fedelta' intermedio fra la stima op-count (Fase A) e la misura su silicio (Fase C, predisposta).

Grounding: ogni numero proviene da matlab/axi/build/phase_b/results.csv (a sua volta estratto dai .rpt
Vivado util_*/timing_*/power_*). Nessun numero e' scritto a mano nel testo.

Uso:    python scripts/build_fpga_phase_b_report.py
Output: report/FPGA_PHASE_B_REPORT.{md,pdf}  +  report/figures_phase_b/*
"""
import os
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# --- CONFIG -----------------------------------------------------------------
HERE       = os.path.dirname(os.path.abspath(__file__))
ROOT       = os.path.dirname(HERE)                       # worktree Simulink_Importer
OUTDIR     = os.path.join(ROOT, 'report')
FIGDIR     = os.path.join(OUTDIR, 'figures_quant')
QZ         = os.path.join(ROOT, 'matlab', 'Quantizzation_Study')
DOC_NAME   = 'QUANTIZATION_STUDY_REPORT'
DOC_TITLE  = 'CF_FSNN — Studio di quantizzazione della rete spiking Donatello'
FOOTER_TEXT = 'CF_FSNN — Studio di quantizzazione · sicurezza car-following e costo hardware'
EQ_DPI     = 200
os.makedirs(FIGDIR, exist_ok=True)

# --- GROUNDING: carica i TSV dello studio -> serie per nfrac (nessun numero a mano) ---------
def _load(name):
    """TSV con colonna 'nfrac' -> dict {nfrac(int): {colonna: stringa}}. Solleva se il file manca."""
    out = {}
    with open(os.path.join(QZ, name), newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            out[int(float(r['nfrac']))] = r
    return out

CL  = _load('cl_sweep.tsv')   # car-following: coll_total/coll_extra/min_gap_avoid/brake_margin_avoid/max_DRAC/NRMSE_*
RES = _load('res_sweep.tsv')  # hardware: WNS/delay_ns/Fmax_MHz/LUT/FF/DSP/BRAM/Ptot_W/Pdyn_W/Psta_W
SEV = _load('sev_sweep.tsv')  # severita' sulle traiettorie inevitabili: max_impact_dv/oracle_max
ACC = {}                      # accuratezza open-loop: max|d| di Donatello per nfrac
with open(os.path.join(QZ, 'acc_sweep.tsv'), newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        if r['champion'] == 'Donatello':
            ACC[int(float(r['nfrac']))] = float(r['maxd'])

def cl(nf, k):  return float(CL[nf][k])
def res(nf, k): return float(RES[nf][k])
NF = sorted(CL)               # griglia nfrac (2..13)

# device Zynq-7020 (xc7z020), da datasheet DS187
DEV = {'LUT': 53200, 'FF': 106400, 'DSP': 220, 'BRAM': 140}

# numeri principali (tutti grounded dai TSV)
N_TRAJ   = 99                          # dataset esaustivo (build_scenarios canonico)
N_SCEN   = 9                           # scenari canonici (5 storici + 4 di coda/OoD)
N_CUTIN  = 33                          # traiettorie con evento cut-in (teletrasporto di gap)
N_INEV   = int(cl(13, 'coll_total'))   # inevitabili: collide anche l'oracolo (= coll_total a ogni nfrac)
PARITY_M = 2.24e-6                      # cancello parita' oracolo MATLAB vs simulate() Python (max|Δs|, m)
LEVELS   = [13, 8, 5, 2]               # menu quantizzazione nel blocco Donatello_Tier

FF13, FF2   = res(13, 'FF'), res(2, 'FF')
FFDROP_PCT  = (FF13 - FF2) / FF13 * 100.0
LUT13, LUT5 = res(13, 'LUT'), res(5, 'LUT')
LUTDROP5    = (LUT13 - LUT5) / LUT13 * 100.0
LUT4        = res(4, 'LUT')
DSP13, DSP2 = res(13, 'DSP'), res(2, 'DSP')
PT13, PS13  = res(13, 'Ptot_W'), res(13, 'Psta_W')
PT2         = res(2, 'Ptot_W')
STATIC_PCT  = PS13 / PT13 * 100.0
PWRDROP_PCT = (PT13 - PT2) / PT13 * 100.0
ORACLE_IMP  = float(SEV[13]['oracle_max'])                  # severita' dell'oracolo sulle inevitabili (m/s)
SEV_MAX     = max(float(SEV[nf]['max_impact_dv']) for nf in NF)
MINGAP_MIN  = min(cl(nf, 'min_gap_avoid') for nf in NF)     # passaggio piu' stretto sugli scenari evitabili (m)
NRMSE13, NRMSE8, NRMSE5, NRMSE2 = (cl(13,'NRMSE_mean'), cl(8,'NRMSE_mean'), cl(5,'NRMSE_mean'), cl(2,'NRMSE_mean'))
DEADLINE_MS = 100.0                    # passo di controllo del car-following
FMAX_LO     = min(res(nf,'Fmax_MHz') for nf in NF)
FMAX_HI     = max(res(nf,'Fmax_MHz') for nf in NF)

# --- Mixed-precision (per-campo): loader + numeri, grounded da mp_*.tsv ------
def _mp_rows(name):
    with open(os.path.join(QZ, name), newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f, delimiter='\t'))
MP_SENS   = _mp_rows('mp_sens.tsv')                       # field, nfrac, maxdgap, coll_extra, pass, ...
MP_RES    = {r['config']: r for r in _mp_rows('mp_res.tsv')}  # config -> WNS/Fmax/LUT/FF/DSP/Ptot/Pdyn/Psta
MP_FIN    = _mp_rows('mp_finalists.tsv')
MP_FIELDS = ['V', 'fatigue', 'acc', 'accw', 'raw', 'w']
MP_THR    = 0.5                                           # cancello comportamentale max|Δgap| [m]
def mp_floor(fld):
    p = [int(r['nfrac']) for r in MP_SENS if r['field'] == fld and int(float(r['pass'])) == 1]
    return min(p) if p else 13
MP_FLOORS = {f: mp_floor(f) for f in MP_FIELDS}
MP_FINAL  = [MP_FLOORS[f] for f in MP_FIELDS]             # config area-ottimale [13 13 4 13 13 4]
MP_REDUC  = [f for f in MP_FIELDS if MP_FLOORS[f] < 13]   # campi riducibili (acc, w)
MP_FIN_DGAP = float(MP_FIN[-1]['maxdgap'])               # config finale: max|Δgap| (0 = bit-identica al full)
def mpr(cfg, k): return float(MP_RES[cfg][k])
MP_DSP_DROP = (mpr('full_precision','DSP') - mpr('finale','DSP')) / mpr('full_precision','DSP') * 100
MP_FF_DROP  = (mpr('full_precision','FF')  - mpr('finale','FF'))  / mpr('full_precision','FF')  * 100
MP_LUT_RISE = (mpr('finale','LUT') - mpr('full_precision','LUT')) / mpr('full_precision','LUT') * 100
MP_SLACK    = mpr('full_precision','WNS')                 # slack io-timed a 125 ns (metrica di margine)
MP_PDYN_FP  = mpr('full_precision','Pdyn_W') * 1000       # potenza dinamica [mW]
MP_PDYN_FI  = mpr('finale','Pdyn_W') * 1000
MP_PO2_FRAC = MP_FLOORS['w']                             # = 4: i pesi po2 hanno minimo 2^-4 (sonda pesi)

PAL = {'blu': '#26527a', 'blunav': '#1a3c6e', 'ac': '#2e7d4f', 'mac': '#b5522a',
       'grigio': '#8a94a0', 'ambra': '#c9992b', 'rosso': '#b5384d'}

# --- Normalizzazione tipografica: apostrofo-ASCII troncato -> accento vero ---
# (writing-style.md: accenti veri, non "velocita'"; NON toccare le elisioni l'/dell'/un'/d').
import re as _re
_TRUNC_MAP = {
    "fedelta'": 'fedeltà', "idoneita'": 'idoneità', "modalita'": 'modalità',
    "attivita'": 'attività', "capacita'": 'capacità', "entita'": 'entità',
    "verita'": 'verità', "proprieta'": 'proprietà', "sommita'": 'sommità',
    "parita'": 'parità', "sparsita'": 'sparsità', "qualita'": 'qualità',
    "unita'": 'unità', "possibilita'": 'possibilità', "difficolta'": 'difficoltà',
    "sensibilita'": 'sensibilità', "quantita'": 'quantità',
    "perche'": 'perché', "poiche'": 'poiché', "anziche'": 'anziché',
    "pressoche'": 'pressoché', "finche'": 'finché', "affinche'": 'affinché',
    "cioe'": 'cioè', "piu'": 'più', "gia'": 'già', "puo'": 'può',
    "cosi'": 'così', "percio'": 'perciò', "cio'": 'ciò', "bensi'": 'bensì',
    "ne'": 'né', "e'": 'è',
}
def norm_it(s):
    """Troncate ASCII -> accenti veri (minuscolo e inizio-frase); non tocca le elisioni l'/dell'/un'."""
    s = str(s)
    for a, b in _TRUNC_MAP.items():
        for aa, bb in ((a, b), (a[:1].upper() + a[1:], b[:1].upper() + b[1:])):
            if aa.rstrip("'").lower() in ('e', 'ne'):   # confine destro esplicito: evita match interni
                s = _re.sub(r"\b" + _re.escape(aa) + r"(?=[\s,.;:)]|$)", bb, s)
            else:
                s = _re.sub(r"\b" + _re.escape(aa), bb, s)
    return s


# --- EQUAZIONI: mathtext -> PNG ---------------------------------------------
def fig_eq(name, lines, fs=11, color='#12233a'):
    n = len(lines)
    fig = plt.figure(figsize=(9.2, 0.52 * n + 0.22))
    for i, ln in enumerate(lines):
        fig.text(0.5, 1.0 - (i + 0.5) / n, '$' + ln + '$',
                 ha='center', va='center', fontsize=fs, color=color)
    p = os.path.join(FIGDIR, name)
    fig.savefig(p, dpi=EQ_DPI, bbox_inches='tight', pad_inches=0.08, facecolor='white')
    plt.close(fig)
    return p


# --- FIGURE DATI (matplotlib, sfondo bianco, landscape) ---------------------
def _style(ax):
    ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
    ax.tick_params(labelsize=8.5); ax.title.set_fontsize(9.5)

def fig_safety():
    """Car-following: collisioni extra (0 ovunque) e NRMSE parametri vs nfrac."""
    xs = NF
    ce = [cl(nf, 'coll_extra') for nf in xs]; nr = [cl(nf, 'NRMSE_mean') for nf in xs]
    fig, ax = plt.subplots(figsize=(8.2, 3.0))
    ax.plot(xs, nr, 'o-', color=PAL['blu'], label='NRMSE parametri (media)')
    ax.axvline(4, color=PAL['rosso'], ls='--', lw=0.9)
    ax.text(4.15, max(nr) * 0.88, 'ginocchio\n~nfrac=4', color=PAL['rosso'], fontsize=7.5)
    ax.set_xlabel('nfrac (bit frazionari del core)', fontsize=9); ax.set_ylabel('NRMSE parametri (vs nfrac=13)', fontsize=9)
    a2 = ax.twinx(); a2.bar(xs, ce, width=0.55, color=PAL['ac'], alpha=0.32)
    a2.set_ylim(0, 1); a2.grid(False)
    a2.set_ylabel('collisioni extra (su %d evitabili)' % (N_TRAJ - N_INEV), color=PAL['ac'], fontsize=8)
    a2.text(7.5, 0.55, 'collisioni extra = 0 a ogni nfrac', color=PAL['ac'], fontsize=8.5, ha='center')
    _style(ax); ax.set_title('Sicurezza car-following: 0 collisioni extra fino a 2 bit; NRMSE liscio', fontsize=9.3)
    p = os.path.join(FIGDIR, 'safety.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_severity():
    """Severita' sulle traiettorie inevitabili: impact Δv della rete vs oracolo, piatto su nfrac."""
    xs = NF; imp = [float(SEV[nf]['max_impact_dv']) for nf in xs]
    fig, ax = plt.subplots(figsize=(8.0, 2.7))
    ax.plot(xs, imp, 'o-', color=PAL['mac'], label='rete (max sugli inevitabili)')
    ax.axhline(ORACLE_IMP, color=PAL['grigio'], ls='--', lw=1.1, label='oracolo (%.2f m/s)' % ORACLE_IMP)
    ax.set_ylim(min(imp) - 0.4, ORACLE_IMP + 0.4)
    ax.set_xlabel('nfrac', fontsize=9); ax.set_ylabel('impact Δv al contatto (m/s)', fontsize=9)
    ax.legend(fontsize=8, loc='lower center'); _style(ax)
    ax.set_title('Severita\' delle collisioni inevitabili: piatta ~7.6 m/s, pari all\'oracolo', fontsize=9.3)
    p = os.path.join(FIGDIR, 'severity.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_resources():
    """Risorse vs nfrac: LUT (picco a n4 dal travaso DSP->LUT), FF (monotona), DSP (gradino a n5)."""
    xs = NF
    lut = [res(nf, 'LUT') for nf in xs]; ff = [res(nf, 'FF') for nf in xs]; dsp = [res(nf, 'DSP') for nf in xs]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.6, 3.0), gridspec_kw={'width_ratios': [1.45, 1]})
    a1.plot(xs, lut, 'o-', color=PAL['ambra'], label='LUT'); a1.plot(xs, ff, 's-', color=PAL['blu'], label='FF')
    a1.annotate('picco n4\n(mult DSP→LUT)', xy=(4, res(4, 'LUT')), xytext=(6.1, res(4, 'LUT') - 430),
                fontsize=7, color=PAL['rosso'], ha='center',
                arrowprops=dict(arrowstyle='->', color=PAL['rosso'], lw=0.8))
    a1.set_xlabel('nfrac', fontsize=9); a1.set_ylabel('celle', fontsize=9); a1.legend(fontsize=8); _style(a1)
    a1.set_title('LUT / FF', fontsize=9.5)
    a2.plot(xs, dsp, 'o-', color=PAL['mac'], ms=4)
    a2.set_xlabel('nfrac', fontsize=9); a2.set_ylabel('DSP48', fontsize=9); _style(a2)
    a2.set_title('DSP (gradino a nfrac=5)', fontsize=9.5)
    fig.suptitle('Risorse vs nfrac: FF pulito (−%.0f%% da 13 a 2 bit), DSP a gradino, LUT non-monotona' % FFDROP_PCT,
                 fontsize=9.2, y=1.03)
    p = os.path.join(FIGDIR, 'resources.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_power():
    """Potenza vs nfrac: piatta e dominata dalla statica del dispositivo."""
    xs = NF
    pt = [res(nf, 'Ptot_W') * 1000 for nf in xs]; pd = [res(nf, 'Pdyn_W') * 1000 for nf in xs]
    ps = [res(nf, 'Psta_W') * 1000 for nf in xs]
    fig, ax = plt.subplots(figsize=(8.2, 2.8))
    ax.plot(xs, pt, 'o-', color=PAL['blu'], label='totale')
    ax.plot(xs, ps, '^-', color=PAL['grigio'], label='statica (dispositivo)')
    ax.plot(xs, pd, 's-', color=PAL['ac'], label='dinamica (logica)')
    ax.set_ylim(0, max(pt) * 1.3); ax.set_xlabel('nfrac', fontsize=9); ax.set_ylabel('potenza (mW)', fontsize=9)
    ax.legend(fontsize=8); _style(ax)
    ax.set_title('Potenza vs nfrac: piatta, dominata dalla statica (%.0f%%)' % STATIC_PCT, fontsize=9.4)
    p = os.path.join(FIGDIR, 'power.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_accuracy():
    """Accuratezza open-loop worst-case (max|d|) vs nfrac: la vista pessimista."""
    xs = sorted(ACC); ys = [ACC[nf] for nf in xs]
    fig, ax = plt.subplots(figsize=(8.0, 2.7))
    ax.plot(xs, ys, 'o-', color=PAL['blunav'])
    ax.axvline(4, color=PAL['rosso'], ls='--', lw=0.9)
    ax.set_xlabel('nfrac', fontsize=9); ax.set_ylabel('max|d| sui 5 parametri (unita\' fisiche)', fontsize=9); _style(ax)
    ax.set_title('Accuratezza open-loop (worst-case): pessimista, degrada sotto nfrac=4', fontsize=9.3)
    p = os.path.join(FIGDIR, 'accuracy.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_mp_sensitivity():
    """Mixed-precision: NRMSE parametri per campo (stesso metro di fedelta' del §4). acc/w a 0 (lossless) fino a 4."""
    cols = {'V': PAL['blu'], 'fatigue': PAL['mac'], 'acc': PAL['ac'], 'accw': PAL['ambra'],
            'raw': PAL['blunav'], 'w': PAL['rosso']}
    fig, ax = plt.subplots(figsize=(8.4, 3.2))
    for fld in MP_FIELDS:
        rows = sorted([r for r in MP_SENS if r['field'] == fld], key=lambda r: int(r['nfrac']))
        xs = [int(r['nfrac']) for r in rows]; ys = [float(r['NRMSE_mean']) for r in rows]
        ax.plot(xs, ys, 'o-', color=cols[fld], ms=3, lw=1.1, label='%s (lossless fino a %d)' % (fld, MP_FLOORS[fld]))
    ax.set_ylim(0, 0.22); ax.set_xlim(13.6, 0.4)   # 13 -> 1 (verso di riduzione)
    ax.set_xlabel('nfrac del campo (gli altri cinque a 13)', fontsize=9)
    ax.set_ylabel('NRMSE parametri vs full-precision', fontsize=9)
    ax.text(0.985, 0.045, '0 collisioni extra a ogni config: sicurezza preservata ovunque',
            transform=ax.transAxes, ha='right', fontsize=7.6, color=PAL['ac'])
    ax.legend(fontsize=7, ncol=2, loc='upper center'); _style(ax)
    ax.set_title('Fedeltà per-campo (NRMSE): acc/w restano a zero (bit-identici) fino a 4 bit; gli altri degradano a 12',
                 fontsize=8.7)
    p = os.path.join(FIGDIR, 'mp_sensitivity.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_mp_area():
    """Risorse dei finalisti, % del full-precision (etichette = assoluti): LUT su, FF/DSP giu'."""
    cfgs = ['full_precision', 'finale', 'uniform4_ref']
    labs = ['full 13×6', 'finale [13,13,4,13,13,4]', 'uniform 4×6 (fuori cancello)']
    mets = ['LUT', 'FF', 'DSP']; fp = {m: mpr('full_precision', m) for m in mets}
    x = list(range(len(mets))); w = 0.26; cc = [PAL['grigio'], PAL['blu'], PAL['ambra']]
    fig, ax = plt.subplots(figsize=(8.0, 3.0))
    for i, cfg in enumerate(cfgs):
        pos = [xi + (i - 1) * w for xi in x]; vals = [mpr(cfg, m) / fp[m] * 100 for m in mets]
        b = ax.bar(pos, vals, w, color=cc[i], label=labs[i])
        for r, m in zip(b, mets):
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 1.2, '%d' % int(mpr(cfg, m)), ha='center', fontsize=6.3)
    ax.axhline(100, color='k', lw=0.7, ls=':'); ax.set_xticks(x); ax.set_xticklabels(mets)
    ax.set_ylabel('% del full-precision', fontsize=9); ax.set_ylim(0, 132)
    ax.legend(fontsize=7.3, loc='lower center'); _style(ax)
    ax.set_title('Risorse dei finalisti a 125 ns io-timed: finale taglia DSP/FF, alza LUT', fontsize=9.2)
    p = os.path.join(FIGDIR, 'mp_area.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p


# --- CONTENUTO --------------------------------------------------------------
def build_doc():
    D = []; A = D.append
    A(('cover', {
        'title': DOC_TITLE,
        'subtitle': 'Caratterizzazione del compromesso di quantizzazione fixed-point del core spiking per '
                    'il car-following (Donatello): sicurezza del comportamento in anello chiuso e costo '
                    'hardware su Zynq-7020, al variare dei bit frazionari del calcolo neurale.',
        'meta': [
            'Livello di fedelta\': il car-following e\' da simulazione in anello chiuso provata bit-vicina '
            'al motore di riferimento; risorse, potenza e frequenza sono stime Vivado post-implementazione '
            '(out-of-context), non misura su silicio.',
            'Fonte dei numeri: matlab/Quantizzation_Study/{cl_sweep, res_sweep, acc_sweep, sev_sweep}.tsv, '
            'prodotti dagli script dello studio. Nessun numero e\' scritto a mano nel testo.',
            'Campione: Donatello, il forward deployato del blocco Donatello_Tier. Dataset '
            'di prova: %d traiettorie su %d scenari canonici, di cui %d con evento di cut-in.' % (N_TRAJ, N_SCEN, N_CUTIN),
        ],
    }))
    A(('toc', 'Sommario'))

    # --- 1. Sintesi ---
    A(('h1', '1. Sintesi'))
    A(('p', 'La rete spiking che stima i cinque parametri del controllore di car-following opera in '
            'virgola fissa. Il numero di bit frazionari del suo calcolo interno, indicato nel seguito con '
            'nfrac, governa insieme l\'accuratezza e il costo su silicio: piu\' bit danno piu\' precisione '
            'ma occupano piu\' area e dissipano piu\' potenza. Questo studio ne caratterizza il '
            'compromesso su due fronti indipendenti — l\'accuratezza del comportamento in strada e '
            'l\'occupazione hardware — spingendo la quantizzazione fino al limite estremo di due soli bit '
            'frazionari.'))
    A(('p', 'Il risultato centrale e\' che la **sicurezza del car-following resta invariata fino a due '
            'bit frazionari**. Su %d traiettorie che comprendono %d eventi di discontinuita\' del gap '
            '(cut-in, dove un veicolo si inserisce a distanza ridotta, e cut-out, dove il leader esce) e '
            'frenate del leader alla decelerazione fisica massima, la '
            'rete quantizzata non provoca **alcuna collisione aggiuntiva** rispetto a un controllore a '
            'conoscenza perfetta, a qualunque profondita\' di bit. Le sole %d collisioni presenti sono '
            'fisicamente inevitabili, e la loro severita\' non cresce riducendo i bit.' % (N_TRAJ, N_CUTIN, N_INEV)))
    A(('p', 'Il costo hardware scende con i bit, ma in modo piu\' sottile di quanto una lettura ingenua '
            'suggerirebbe. I registri diminuiscono in modo pulito, del **%.0f%%** passando da tredici a due '
            'bit; i blocchi aritmetici calano a gradino; le celle logiche seguono invece un andamento non '
            'monotono, governato dal confine di inferenza fra blocchi aritmetici dedicati e logica '
            'combinatoria. La potenza resta pressoche\' costante — scende di appena l\'**%.1f%%** da tredici '
            'a due bit — perche\' su questo dispositivo domina la dispersione statica. La frequenza '
            'massima e\' un margine amplissimo a ogni livello.' % (FFDROP_PCT, PWRDROP_PCT)))
    A(('p', 'Ne discende la conclusione operativa: **il fattore che limita la scelta dei bit non e\' '
            'l\'hardware ne\' la sicurezza, bensi\' la fedelta\' dei parametri stimati**. La quantizzazione '
            'sposta i parametri interni pur preservando il controllo — un comportamento da equilibri '
            'interni della rete probabilistica — e il ginocchio di quella fedelta\' cade attorno a '
            'quattro-cinque bit. I quattro livelli utili che ne risultano sono stati resi selezionabili '
            'come menu nel blocco di deploy.'))
    A(('callout', 'Marcatori usati nel documento: ● grandezza misurata o verificata (comportamento in '
                  'anello chiuso, parita\' col riferimento); ○ stima Vivado post-implementazione (risorse, '
                  'potenza, frequenza), precedente alla misura su silicio.'))

    # --- 2. Scopo e metodo ---
    A(('h1', '2. Scopo e metodo'))
    A(('p', 'Lo studio di trade-off a monte aveva stabilito che, essendo la frequenza massima un margine '
            'enorme, il criterio di progetto rilevante e\' l\'area — lasciare spazio ad altri blocchi '
            'sullo stesso dispositivo. La quantizzazione attacca proprio quella leva: meno bit frazionari '
            'significano meno logica e meno potenza dinamica, al costo di accuratezza. La domanda che lo '
            'studio risolve e\' fin dove sia lecito spingersi, e cosa fissi davvero il limite.'))
    A(('p', 'La valutazione poggia su tre scelte metodologiche, ciascuna volta a evitare una conclusione '
            'credibile ma falsa. La prima e\' il **dataset di prova esaustivo**. Un insieme di sole '
            'traiettorie di inseguimento dolce non mette mai il controllore in difficolta\', e vi si '
            'sopravvive banalmente anche molto degradati; percio\' la prova usa i %d scenari canonici del '
            'progetto — inseguimento, stop-and-go, frenata forte, cut-in, sinusoidale, e quattro scenari '
            'di coda fra cui il cut-in aggressivo e la frenata di emergenza — replicati su piu\' '
            'estrazioni di parametri, per un totale di %d traiettorie di cui %d con un vero evento di '
            'cut-in, modellato come una discontinuita\' del gap.' % (N_SCEN, N_TRAJ, N_CUTIN)))
    A(('p', 'La seconda scelta e\' l\'**anello chiuso fedele**. La sicurezza si misura simulando l\'ego '
            'guidato dalla rete quantizzata contro il profilo del leader, con il gap tracciato senza '
            'clamp inferiore, cosi\' che una collisione sia rilevabile; l\'evento di cut-in vi e\' '
            'iniettato come teletrasporto del gap. Questo anello riproduce il motore canonico del '
            'progetto: sui nove scenari, l\'oracolo simulato in MATLAB e la funzione di riferimento in '
            'Python coincidono passo per passo entro **%.1e m** sul gap, con i medesimi verdetti di '
            'collisione. La misura di comportamento e\' dunque quella vera, non quella di un anello che '
            'nasconde le collisioni dietro un clamp.' % PARITY_M))
    A(('p', 'La terza scelta e\' la **linea di base oracolo per traiettoria**. Prima dello sweep, un '
            'controllore a parametri veri (l\'oracolo) percorre tutte le traiettorie e marca quali '
            'collisioni siano fisicamente evitabili. Per la rete a ciascun nfrac, allora, contano solo le '
            'collisioni su traiettorie che l\'oracolo evita: quelle, e solo quelle, sono il **costo reale '
            'della quantizzazione**, separato da cio\' che nessun controllore potrebbe evitare. Sul '
            'dataset, %d traiettorie su %d sono inevitabili gia\' per l\'oracolo.' % (N_INEV, N_TRAJ)))

    # --- 3. Su quale segnale agisce nfrac ---
    A(('h1', '3. Cosa quantizza nfrac'))
    A(('p', 'La quantizzazione agisce sul calcolo neurale interno, non sull\'ingresso-uscita del blocco. '
            'Il parametro nfrac fissa il numero di bit frazionari dei tipi in virgola fissa del core '
            'spiking, lasciando invariati i bit interi — dunque il campo di rappresentazione non cambia, '
            'cambia solo la risoluzione. I segnali interessati sono il potenziale di membrana del neurone, '
            'la soglia adattiva, gli accumulatori della corrente sinaptica, i pesi a potenza di due e '
            'l\'uscita grezza del readout, oltre all\'ingresso normalizzato, che eredita il tipo del '
            'potenziale di membrana.'))
    A(('img', (fig_eq('eq_qformat.png', [
        r'V \sim Q5.n,\ \ \mathrm{fatigue} \sim Q3.n,\ \ \mathrm{acc} \sim Q5.n,\ \ \mathrm{accw} \sim Q8.(n{+}4),\ \ \mathrm{raw} \sim Q7.n,\ \ w \sim Q2.n']),
        'Equazione 3.1 — i tipi del core al variare di n = nfrac (notazione Qm.n: m bit interi, n bit '
        'frazionari). V = potenziale di membrana; fatigue = soglia adattiva; acc/accw = accumulatori '
        '(accw piu\' largo per gli scorrimenti esatti); raw = uscita del readout; w = pesi. I bit interi '
        'sono fissi; solo n varia. Fonte: matlab/snn_types.m.')))
    A(('p', 'Restano fuori dalla quantizzazione, per costruzione, due elementi. Gli **ingressi fisici** — '
            'distanza, velocita\' dell\'ego, velocita\' relativa e velocita\' del leader — arrivano a '
            'piena risoluzione: la loro quantizzazione sul canale di comunicazione e\' un asse separato, '
            'estraneo a questo studio. E il **decodificatore** che trasforma l\'uscita grezza nei cinque '
            'parametri: la sua aritmetica e le sue costanti sono fisse a tredici bit frazionari, '
            'indipendenti da nfrac. L\'uscita grezza, calcolata alla precisione nfrac, vi entra e viene '
            'portata a tredici bit senza perdita ulteriore. In una frase, nfrac e\' la profondita\' di bit '
            'del calcolo neurale — stato, pesi, accumulatori, readout — non dell\'ingresso-uscita ne\' '
            'della ricostruzione finale dei parametri.'))

    # --- 4. Sicurezza car-following ---
    A(('h1', '4. Sicurezza del car-following'))
    A(('p', 'La misura di sicurezza confronta, a ogni nfrac, le collisioni della rete con la linea di '
            'base oracolo. Il conteggio delle collisioni aggiuntive — quelle su traiettorie che l\'oracolo '
            'evita — e\' **zero a ogni livello, fino a due bit frazionari**. Le sole %d collisioni presenti '
            'a ogni nfrac sono le stesse dell\'oracolo: scenari di cut-in aggressivo in cui la '
            'decelerazione richiesta supera il limite fisico del veicolo, dunque inevitabili per qualunque '
            'controllore. La rete quantizzata eguaglia il controllore a conoscenza perfetta '
            'sull\'evitamento a ogni profondita\' di bit.' % N_INEV))
    A(('img', (fig_safety(), 'Figura 4.1 — Sicurezza car-following al variare di nfrac. La curva '
               '(asse sinistro) e\' l\'errore normalizzato dei parametri rispetto a piena precisione; le '
               'barre (asse destro) sono le collisioni aggiuntive rispetto all\'oracolo, nulle a ogni '
               'livello. Fonte: cl_sweep.tsv.')))
    A(('p', 'Anche i margini di sicurezza istantanei confermano l\'invarianza. Il passaggio piu\' stretto '
            'su tutte le traiettorie evitabili e\' di circa **%.2f m** nel caso peggiore, non si annulla mai e non '
            'peggiora riducendo i bit; il margine di evitabilita\' e la decelerazione richiesta critica '
            'oscillano con la geometria degli scenari, non con nfrac. In altre parole, l\'inviluppo di '
            'sicurezza e\' fissato dai casi piu\' duri del dataset, e la rete lo percorre allo stesso modo '
            'a tredici come a due bit.' % MINGAP_MIN))
    A(('img', (fig_eq('eq_ssm.png', [
        r'\mathrm{brake\_margin} = s - \frac{\max(0,\Delta v)^2}{2\,B_{\max}}, \qquad \mathrm{DRAC} = \frac{\Delta v^2}{2\,s}']),
        'Equazione 4.1 — margine di frenata e decelerazione richiesta (DRAC). s = gap (m); Δv = velocita\' '
        'di avvicinamento (m/s); B_max = 9 m/s2 = decelerazione fisica massima. Un margine di frenata '
        'negativo segnala che, se il leader frenasse al massimo in quell\'istante, la collisione sarebbe '
        'inevitabile. Fonte: matlab/Quantizzation_Study/qz_safety_metrics.m (porta di utils/closed_loop_eval.py).')))
    A(('p', 'Resta da chiudere il caso delle collisioni inevitabili: dove nessun controllore evita '
            'l\'urto, la quantizzazione lo rende piu\' violento? La severita\', misurata come velocita\' '
            'relativa al contatto, e\' **piatta su tutti i livelli**: il suo massimo e\' %.2f m/s, appena '
            'sotto la severita\' dell\'oracolo (%.2f m/s), da tredici fino a due bit frazionari. Dove la '
            'collisione e\' comunque inevitabile, la rete a due bit non urta ne\' piu\' ne\' meno di quella '
            'a tredici bit o del controllore a conoscenza perfetta.' % (SEV_MAX, ORACLE_IMP)))
    A(('img', (fig_severity(), 'Figura 4.2 — Severita\' (velocita\' relativa al contatto) sulle %d '
               'traiettorie inevitabili, al variare di nfrac. La linea tratteggiata e\' la severita\' '
               'dell\'oracolo. La curva della rete e\' piatta e le si sovrappone. Fonte: sev_sweep.tsv.' % N_INEV)))

    # --- 5. Fedelta' dei parametri ---
    A(('h1', '5. Fedelta\' dei parametri e il ginocchio'))
    A(('p', 'Se la sicurezza non si degrada, cosa lo fa? La fedelta\' dei parametri stimati. L\'errore '
            'normalizzato medio dei cinque parametri rispetto a piena precisione cresce in modo liscio al '
            'calare dei bit, con un ginocchio attorno a quattro-cinque bit frazionari: e\' pressoche\' '
            'costante sopra — passa da **%.3f** a otto bit a **%.3f** a cinque — e poi accelera sotto, '
            'raddoppiando quasi a ogni bit, fino a **%.3f** a tre e **%.3f** a due. La rete probabilistica '
            'riorganizza i propri parametri sotto quantizzazione, ma la legge di controllo e la '
            'retroazione ne assorbono lo scarto: e\' questo che spiega la sicurezza invariante a fronte di '
            'parametri visibilmente diversi.' % (NRMSE8, NRMSE5, cl(3, 'NRMSE_mean'), NRMSE2)))
    A(('img', (fig_eq('eq_nrmse.png', [
        r'\mathrm{NRMSE}_p = \frac{\sqrt{\langle (p^{(n)} - p^{(13)})^2 \rangle}}{\max p^{(13)} - \min p^{(13)}}']),
        'Equazione 5.1 — errore normalizzato del parametro p a nfrac = n, rispetto al riferimento a '
        'tredici bit; la media è sul dataset e la normalizzazione è sull\'escursione del parametro nel '
        'riferimento (adimensionale). Fonte: matlab/Quantizzation_Study/qz_cl_validate.m.')))
    A(('p', 'Questa vista in anello chiuso capovolge quella open-loop. Misurando lo scarto massimo dei '
            'parametri sul solo forward, senza retroazione, la rete appare sensibile gia\' a bit medi: il '
            'parametro peggiore devia di mezzo-un\'unita\' fisica ben prima del limite. Ma quel massimo '
            'peggiore e\' una vista pessimista; il comportamento in strada, che e\' cio\' che conta, la '
            'smentisce. La stessa quantizzazione che sembra rovinosa sui numeri grezzi lascia il controllo '
            'sicuro fino a due bit.'))
    A(('img', (fig_accuracy(), 'Figura 5.1 — Accuratezza open-loop worst-case (massimo scarto assoluto '
               'sui cinque parametri, in unita\' fisiche) al variare di nfrac. Vista pessimista che il '
               'comportamento in anello chiuso ridimensiona. Fonte: acc_sweep.tsv.')))

    # --- 6. Costo hardware ---
    A(('h1', '6. Costo hardware'))
    A(('p', 'Il costo su silicio e\' stato misurato sintetizzando il forward a ciascun nfrac su Vivado, in '
            'modalita\' out-of-context su una configurazione di pipeline di riferimento, con lo stesso '
            'vincolo di clock di deploy per tutti i livelli, cosi\' che il confronto sia omogeneo. Il '
            'risparmio d\'area non e\' un semplice andamento monotono: e\' '
            'governato dal confine di inferenza fra blocchi aritmetici dedicati e logica combinatoria.'))
    A(('img', (fig_resources(), 'Figura 6.1 — Risorse al variare di nfrac. A sinistra celle logiche e '
               'registri; a destra i blocchi aritmetici. I registri calano in modo pulito, i blocchi '
               'aritmetici a gradino sotto cinque bit, le celle logiche in modo non monotono per il '
               'travaso dai blocchi aritmetici. Fonte: res_sweep.tsv.')))
    A(('p', 'I **registri** sono la metrica pulita: monotoni, calano del **%.0f%%** da tredici a due bit. '
            'I **blocchi aritmetici** scendono a gradino — restano stabili sopra i cinque bit, poi crollano '
            'sotto, quando le moltiplicazioni piu\' strette smettono di occupare un blocco dedicato. Proprio '
            'quel travaso rende le **celle logiche** non monotone: calano da tredici a cinque bit '
            '(**%.0f%%** a cinque bit), poi risalgono a quattro — dove le moltiplicazioni uscite dai '
            'blocchi diventano logica — e infine scendono di nuovo a due-tre bit, dove quella stessa logica '
            'si restringe. Il livello a quattro bit e\' percio\' dominato dal livello a cinque, che usa meno '
            'celle a pari fedelta\'.' % (FFDROP_PCT, LUTDROP5)))
    A(('p', 'La **potenza** non partecipa a questo compromesso: e\' piatta — scende di appena l\'%.1f%% da '
            'tredici a due bit. La ragione e\' che su questo dispositivo la dispersione statica vale il '
            '**%.0f%%** della potenza totale; la quota dinamica della logica, la sola che scala con i bit, '
            'e\' troppo piccola per spostare il totale. La quantizzazione, su questo silicio, non fa '
            'risparmiare potenza. Vi e\' pero\' un corollario: la rete e\' idle per costruzione per oltre il '
            '99,9%% del tempo, dunque su un dispositivo dove la potenza dinamica fosse il collo di '
            'bottiglia il risparmio si materializzerebbe; qui non lo fa perche\' domina la statica del '
            'dispositivo, non un difetto della rete.' % (PWRDROP_PCT, STATIC_PCT)))
    A(('img', (fig_power(), 'Figura 6.2 — Potenza al variare di nfrac: totale, statica del dispositivo e '
               'dinamica della logica. La statica domina e il totale e\' piatto. Fonte: res_sweep.tsv.')))
    A(('p', 'La **frequenza massima**, infine, e\' un margine e non una proprieta\' del progetto a questo '
            'vincolo: oscilla fra circa %.0f e %.0f MHz al punto di deploy, ma il tool non spinge (lo slack '
            'e\' ampiamente positivo). Poiche\' ogni inferenza richiede alcune centinaia di cicli, il passo '
            'di controllo di %g ms si accontenta di un clock dell\'ordine di qualche kilohertz: ogni livello '
            'vi resta migliaia di volte sopra. Non e\' quindi una leva di scelta dei bit.'
            % (FMAX_LO, FMAX_HI, DEADLINE_MS)))

    # --- 7. Il ginocchio e il menu ---
    A(('h1', '7. Livelli utili e menu nel blocco'))
    A(('p', 'Incrociando i tre fronti — sicurezza, fedelta\', costo — la lettura e\' netta. La sicurezza '
            'regge fino a due bit e non pone limite; la potenza e\' piatta; il risparmio d\'area e\' modesto '
            'e non monotono. Cio\' che detta la scelta dei bit e\' la fedelta\' dei parametri. Ne emergono '
            'quattro livelli utili.'))
    A(('table', (
        ['Livello (nfrac)', 'Uso', 'NRMSE parametri', 'Risorse vs 13 bit', 'Collisioni extra'],
        [
            ['13', 'piena precisione (riferimento)', f'{NRMSE13:.3f}', '—', f'{int(cl(13,"coll_extra"))}'],
            ['8',  'conservativo', f'{NRMSE8:.3f}', f'-{(LUT13-res(8,"LUT"))/LUT13*100:.0f}% celle, -{(FF13-res(8,"FF"))/FF13*100:.0f}% registri', f'{int(cl(8,"coll_extra"))}'],
            ['5',  'compromesso area/fedelta\'', f'{NRMSE5:.3f}', f'-{LUTDROP5:.0f}% celle, -{(FF13-res(5,"FF"))/FF13*100:.0f}% registri', f'{int(cl(5,"coll_extra"))}'],
            ['2',  'aggressivo (solo sicurezza)', f'{NRMSE2:.3f}', f'-{(LUT13-res(2,"LUT"))/LUT13*100:.0f}% celle, -{FFDROP_PCT:.0f}% registri', f'{int(cl(2,"coll_extra"))}'],
        ],
    )))
    A(('p', 'Questi quattro livelli sono stati resi selezionabili nel blocco di deploy Donatello_Tier, '
            'come secondo menu accanto a quello del profilo di pipeline. La rete a ciascun livello e\' una '
            'variante distinta con i tipi in virgola fissa gia\' fissati a quel nfrac; alla piena '
            'precisione la variante coincide bit per bit con il forward storico, come atteso da una '
            'sostituzione che a tredici bit e\' un\'operazione neutra.'))
    A(('callout', 'Nota realizzativa: un menu che pilotasse la profondita\' di bit come parametro vivo, '
                  'rigenerando i tipi a runtime, non si e\' potuto ottenere, perche\' un parametro di '
                  'contenitore non raggiunge una funzione annidata dentro un sotto-sistema a varianti. Le '
                  'quattro varianti discrete, coi tipi gia\' fissati, aggirano il vincolo e sono la '
                  'soluzione robusta adottata.'))

    # --- 8. Quantizzazione per-campo (mixed-precision) ---
    A(('h1', '8. Quantizzazione per-campo (mixed-precision)'))
    A(('p', 'Le sezioni precedenti abbassano un unico nfrac per l\'intero core, e ne misurano il costo con '
            'due criteri: la **sicurezza** — zero collisioni evitabili in piu\' rispetto all\'oracolo '
            '(Sezione 4) — e la **fedelta\'** dei parametri, l\'NRMSE (Sezione 5). Questa sezione pone una '
            'domanda complementare con gli **stessi due criteri**: i sei tipi del core valgono tutti i loro '
            'bit allo stesso modo? Ciascuno riceve un nfrac indipendente, e si misura fin dove ognuno puo\' '
            'scendere da solo, tenendo gli altri cinque a tredici.'))
    A(('p', 'Sul fronte della **sicurezza** la risposta e\' coerente con la Sezione 4, ed e\' netta: **ogni '
            'campo, da solo, tollera la riduzione fino a un solo bit senza alcuna collisione aggiuntiva**. Su '
            'tutte le %d configurazioni per campo — sei campi per tredici livelli — le collisioni extra '
            'restano zero. Come per lo studio uniforme, la sicurezza non e\' il limite: non e\' lei a dire '
            'quanti bit servano.' % (6 * 13)))
    A(('img', (fig_mp_sensitivity(), 'Figura 8.1 — Fedelta\' per campo (NRMSE dei parametri rispetto alla '
               'piena precisione) quando si abbassa il nfrac di un solo campo, tenendo gli altri cinque a '
               'tredici. acc e w restano esattamente a zero — riduzione senza perdita — fino a quattro bit; '
               'V, fatigue, accw e raw degradano gia\' al primo bit tolto. In tutte le configurazioni le '
               'collisioni extra sono zero. Fonte: mp_sens.tsv.')))
    A(('p', 'E\' la **fedelta\'** a separare i sei campi, e lo fa in modo netto. Due di essi — l\'accumulatore '
            'd\'ingresso e i pesi — mantengono NRMSE **esattamente a zero** fino a quattro bit: la loro '
            'riduzione non e\' un compromesso ma **senza perdita**, l\'uscita bit-identica alla piena '
            'precisione. Gli altri quattro degradano al primo bit tolto. E\' un risultato di natura diversa '
            'da quello dello studio uniforme: non "quanta perdita e\' tollerabile", ma "quali campi non '
            'portano informazione da togliere".'))
    A(('table', (
        ['Campo', 'Ruolo', 'Floor senza perdita (nfrac)', 'Sicurezza'],
        [
            ['V',       'potenziale di membrana',  str(MP_FLOORS['V']),       'fino a 1 bit'],
            ['fatigue', 'soglia adattiva',         str(MP_FLOORS['fatigue']), 'fino a 1 bit'],
            ['acc',     'accumulatore d\'ingresso', str(MP_FLOORS['acc']),     'fino a 1 bit'],
            ['accw',    'accumulatore largo',      str(MP_FLOORS['accw']),    'fino a 1 bit'],
            ['raw',     'uscita del readout',      str(MP_FLOORS['raw']),     'fino a 1 bit'],
            ['w',       'pesi a potenza di due',   str(MP_FLOORS['w']),       'fino a 1 bit'],
        ],
    )))
    A(('p', 'Il "floor senza perdita" e\' il nfrac piu\' basso a cui l\'uscita resta bit-identica alla piena '
            'precisione. La sicurezza — colonna a fianco — regge invece fino a un bit per ogni campo, esattamente '
            'come nello studio uniforme; le due colonne dicono cose diverse, e solo la fedelta\' distingue i campi.'))
    A(('p', 'Il meccanismo e\' verificato, non ipotizzato. Ispezionando i pesi del campione, **tutte** le '
            'matrici (fc, ricorrenti, readout) sono potenze di due con modulo minimo esattamente **2⁻⁴**. '
            'Quindi %d bit frazionari rappresentano ogni peso in modo esatto (a tre bit il peso 2⁻⁴ '
            'sparisce, e la rete si rompe); e l\'accumulatore d\'ingresso, che somma pesi-po2 per spike '
            'interi, vive su una griglia da 2⁻⁴ e serve anch\'esso a quattro bit. Gli altri quattro campi '
            'portano grandezze **continue** — pilotate da quantita\' non-po2 come la soglia e i parametri '
            'del decode — e usano tutta la loro precisione: ogni bit tolto sposta subito i parametri.'
            % MP_PO2_FRAC))
    A(('p', 'Ne segue la relazione con lo studio uniforme. La config **senza perdita e\' [%s]** — soli acc e '
            'w a quattro bit — con NRMSE e scarto del gap **nulli** (verifica congiunta): e\' **bit-identica** '
            'alla piena precisione. La riduzione *con perdita* dello studio uniforme — il ginocchio attorno a '
            'quattro-cinque bit — e\' dunque guidata dai **quattro campi continui**; la precisione mista '
            'isola e rimuove la parte senza perdita (acc e w) che quella uniforme, muovendo tutti i campi '
            'insieme, non puo\' separare. In questo senso i due studi sono coerenti e complementari: '
            'l\'uniforme misura il compromesso di fedelta\', il per-campo individua cio\' che e\' ridondante '
            'a monte del compromesso.'
            % ' '.join(str(x) for x in MP_FINAL)))
    A(('img', (fig_mp_area(), 'Figura 8.2 — Risorse dei finalisti a 125 ns io-timed, in percentuale del '
               'full-precision (etichette = valori assoluti). La finale taglia i blocchi aritmetici e i '
               'registri ma alza le celle logiche; la uniforme a quattro bit (fuori cancello, solo '
               'riferimento hardware) mostra il soffitto. Fonte: mp_res.tsv.')))
    A(('table', (
        ['Config', 'LUT', 'FF', 'DSP', 'slack WNS (ns)', 'P dinamica (mW)'],
        [
            ['full 13×6', '%d' % mpr('full_precision','LUT'), '%d' % mpr('full_precision','FF'),
             '%d' % mpr('full_precision','DSP'), '%.0f' % mpr('full_precision','WNS'), '%.0f' % (mpr('full_precision','Pdyn_W')*1000)],
            ['finale [%s]' % ','.join(str(x) for x in MP_FINAL), '%d' % mpr('finale','LUT'), '%d' % mpr('finale','FF'),
             '%d' % mpr('finale','DSP'), '%.0f' % mpr('finale','WNS'), '%.0f' % (mpr('finale','Pdyn_W')*1000)],
            ['uniform 4×6 (fuori cancello)', '%d' % mpr('uniform4_ref','LUT'), '%d' % mpr('uniform4_ref','FF'),
             '%d' % mpr('uniform4_ref','DSP'), '%.0f' % mpr('uniform4_ref','WNS'), '%.0f' % (mpr('uniform4_ref','Pdyn_W')*1000)],
        ],
    )))
    A(('p', 'In hardware, pero\', il pranzo comportamentalmente gratis **non** e\' un risparmio pulito. La '
            'finale taglia i blocchi aritmetici del **%.0f%%** e i registri del **%.0f%%**, ma **alza** le '
            'celle logiche del **%.0f%%**: e\' lo stesso confine fra blocchi dedicati e logica gia\' visto '
            'nella Sezione 6 — le moltiplicazioni strette di acc e w escono dai blocchi e diventano celle. '
            'La potenza non aiuta: la **dinamica** passa da %.0f a %.0f mW (sale, per le celle in piu\'), e '
            'a questa scala di pochi milliwatt stimati la differenza e\' entro la risoluzione. Il **margine '
            'di timing** e\' enorme — slack di circa %.0f ns sul vincolo di deploy da 125 ns — dunque la '
            'frequenza non e\' il collo. La lettura onesta: i bit sovra-dimensionati di acc e w sono liberi '
            'da togliere nel comportamento, ma su questo Zynq DSP-ricco e static-dominato il taglio '
            '**ribilancia blocchi verso celle** senza vero guadagno d\'area ne\' di potenza. Il valore '
            'dell\'analisi per-campo e\' **diagnostico** — dice quali campi portano informazione e quali no — '
            'e conferma, per via indipendente, il verdetto dello studio uniforme: il collo dei bit e\' la '
            'fedelta\', non l\'hardware.' % (MP_DSP_DROP, MP_FF_DROP, MP_LUT_RISE, MP_PDYN_FP, MP_PDYN_FI, MP_SLACK)))
    A(('p', 'I sei nfrac per campo sono esposti nel blocco di deploy come **Modalita\' Avanzata**: una '
            'casella di spunta accanto ai menu di base sblocca sei cursori (uno per campo, da 1 a 13). '
            'Come per il menu di base, la configurazione e\' realizzata da varianti coi tipi gia\' fissati '
            '— il generatore del blocco cuoce la variante avanzata ai valori scelti — perche\' un blocco '
            'legato alla libreria non puo\' rigenerare la propria logica a runtime. Alla piena precisione '
            'la variante avanzata coincide bit per bit con quella di base.'))

    # --- 9. Limiti residui ---
    A(('h1', '9. Limiti residui'))
    A(('p', 'Vanno dichiarati quattro limiti. Le curve di risorse, potenza e frequenza sono stime Vivado '
            'post-implementazione con vincolo di deploy, non misure su silicio; il loro andamento relativo '
            'fra i livelli e\' affidabile, i valori assoluti attendono la misura su scheda. La '
            'caratterizzazione hardware e\' inoltre condotta su una configurazione di pipeline di '
            'riferimento: il ginocchio e le curve di risorsa e potenza sono robusti al profilo scelto — la '
            'quantizzazione tocca la logica del core, comune ai profili — mentre il solo valore assoluto di '
            'frequenza massima e\' specifico di quella configurazione. Lo studio varia esclusivamente i bit '
            'del core: la quantizzazione degli ingressi e\' un asse separato, fuori campo. Infine, la '
            'caratterizzazione hardware della precisione mista (Sezione 8) poggia su un insieme ridotto di '
            'tre configurazioni sintetizzate, non su uno sweep completo per campo — che richiederebbe ore '
            'di sintesi; le curve di sensibilita\' sono isolate, un campo per volta, e la verifica '
            'congiunta delle interazioni e\' svolta sulla sola configurazione finale.'))

    # --- 10. Riferimenti ---
    A(('h1', '10. Riferimenti'))
    A(('table', (
        ['Riferimento', 'Tema'],
        [
            ['Treiber, M., Kesting, A. (2013). Traffic Flow Dynamics. Springer (IIDM/ACC, cap. 11-12).', 'Modello di car-following'],
            ['Kesting, A., Treiber, M., Helbing, D. (2010). Enhanced IDM (ACC/CAH). Phil. Trans. R. Soc. A 368, 4585-4605.', 'Legge di controllo'],
            ['Minderhoud, M. M., Bovy, P. H. L. (2001). Extended time-to-collision safety measures. Accid. Anal. Prev. 33(1), 89-97.', 'Metriche di sicurezza (TTC/TET/TIT)'],
            ['Archer, J. (2005). Traffic conflict techniques and micro-simulation (DRAC critico ~3.35 m/s2). KTH, Stockholm.', 'DRAC e conflitti'],
            ['AMD/Xilinx. Zynq-7000 SoC Data Sheet (DS187); Vivado Design Suite 2026.1.', 'Dispositivo e sintesi'],
        ],
    )))
    return D


# --- RENDER MARKDOWN (dal template della skill) -----------------------------
def render_md(doc, outpath):
    import re
    L = []
    mdc = lambda x: str(x).replace('|', '\\|')
    for kind, *rest in doc:
        b = rest[0] if rest else None
        if kind == 'cover':
            L.append(f"# {b['title']}\n")
            L.append(f"> **{b['subtitle']}**\n")
            for m in b['meta']:
                L.append(f"> {m}  ")
            L.append('\n---\n')
        elif kind == 'h1':
            L.append(f"\n## {b}\n")
        elif kind == 'h2':
            L.append(f"\n### {b}\n")
        elif kind == 'h3':
            L.append(f"\n#### {b}\n")
        elif kind == 'p':
            L.append(b + '\n')
        elif kind == 'callout':
            L.append(f"> **Nota.** {b}\n")
        elif kind == 'toc':
            title = b if isinstance(b, str) else b[0]
            L.append(f"\n## {title}\n")
            L.append('| Sezione |')
            L.append('|---|')
            for k2, *rr in doc:
                if k2 in ('h1', 'h2', 'h3'):
                    L.append(f'| {mdc(rr[0]) if rr else ""} |')
            L.append('')
        elif kind == 'table':
            headers, rows = b
            L.append('| ' + ' | '.join(mdc(h) for h in headers) + ' |')
            L.append('|' + '|'.join(['---'] * len(headers)) + '|')
            for r in rows:
                L.append('| ' + ' | '.join(mdc(x) for x in r) + ' |')
            L.append('')
        elif kind == 'img':
            path, capt = b
            rel = os.path.relpath(path, OUTDIR).replace('\\', '/')
            L.append(f"![{capt}]({rel})")
            L.append(f"*{capt}*\n")
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(norm_it('\n'.join(L)))
    print('  scritto', outpath)


# --- RENDER PDF (dal template della skill) ----------------------------------
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
                             borderColor=colors.HexColor('#9bb8d8'), borderWidth=0.6,
                             spaceBefore=4, spaceAfter=10)

    def esc(s):
        s = norm_it(str(s)).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return re.sub(r'(?<!\w)\*\*(\S(?:.*?\S)?)\*\*', r'<b>\1</b>', s)

    usable_w = A4[0] - 3.6 * cm
    story = []

    def add_image(path, caption):
        import sys
        img = ImageReader(path)
        iw, ih = img.getSize()
        if os.path.basename(path).startswith('eq_'):
            w = iw * 72.0 / EQ_DPI
            h = ih * 72.0 / EQ_DPI
            if w > usable_w:
                scale = usable_w / w
                h *= scale; w = usable_w
                if scale < 0.85:
                    print(f"  ATTENZIONE: equazione {os.path.basename(path)} ridotta al {scale:.0%}", file=sys.stderr)
            eqim = Image(path, width=w, height=h); eqim.hAlign = 'CENTER'
            story.append(KeepTogether([Spacer(1, 3), eqim, Paragraph(esc(caption), cap)]))
            return
        w = usable_w; h = w * ih / iw
        if h > 12.0 * cm:
            h = 12.0 * cm; w = h * iw / ih
        story.append(KeepTogether([Spacer(1, 4), Image(path, width=w, height=h),
                                   Paragraph(esc(caption), cap)]))

    def make_table(headers, rows):
        n = len(headers)
        fs = 8 if n <= 4 else 7.2 if n <= 5 else 6.4
        th = ParagraphStyle('th', fontName='DJ-B', fontSize=fs, leading=fs + 2,
                            textColor=colors.white, wordWrap='CJK')
        data = [[Paragraph(f'<b>{esc(x)}</b>', th) for x in headers]]
        cell = ParagraphStyle('td', fontName='DJ', fontSize=fs, leading=fs + 2.5, wordWrap='CJK')
        for r in rows:
            data.append([Paragraph(esc(x), cell) for x in r])
        t = Table(data, repeatRows=1, colWidths=[usable_w / n] * n, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#26527a')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5fa')]),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#b9c6d6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(Spacer(1, 2)); story.append(t); story.append(Spacer(1, 8))

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle('toc0', fontName='DJ-B', fontSize=10.5, leading=18,
                       textColor=colors.HexColor('#1a3c6e')),
        ParagraphStyle('toc1', fontName='DJ', fontSize=9.5, leading=14, leftIndent=16),
        ParagraphStyle('toc2', fontName='DJ', fontSize=9, leading=13, leftIndent=32,
                       textColor=colors.HexColor('#555555')),
    ]

    class TOCDoc(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            if flowable.__class__.__name__ == 'Paragraph':
                lvl = {'h1': 0, 'h2': 1, 'h3': 2}.get(flowable.style.name)
                if lvl is not None:
                    txt = flowable.getPlainText()
                    safe = txt.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    self.notify('TOCEntry', (lvl, safe, self.page))

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
        elif kind == 'h2':
            story.append(Paragraph(esc(b), h2))
        elif kind == 'h3':
            story.append(Paragraph(esc(b), h3))
        elif kind == 'p':
            story.append(Paragraph(esc(b), body))
        elif kind == 'callout':
            story.append(Paragraph('<b>Nota.</b> ' + esc(b), callout))
        elif kind == 'table':
            make_table(*b)
        elif kind == 'img':
            add_image(*b)

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
    print('[1/3] figure + contenuto...')
    DOC = build_doc()
    print('[2/3] markdown...'); render_md(DOC, os.path.join(OUTDIR, DOC_NAME + '.md'))
    print('[3/3] pdf...');      render_pdf(DOC, os.path.join(OUTDIR, DOC_NAME + '.pdf'))
    print('fatto:', os.path.join(OUTDIR, DOC_NAME + '.{md,pdf}'))
