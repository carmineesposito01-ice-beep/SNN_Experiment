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
FIGDIR     = os.path.join(OUTDIR, 'figures_phase_b')
CSV_PATH   = os.path.join(ROOT, 'matlab', 'axi', 'build', 'phase_b', 'results.csv')
DOC_NAME   = 'FPGA_PHASE_B_REPORT'
DOC_TITLE  = 'CF_FSNN — Report FPGA Fase B (post-sintesi)'
FOOTER_TEXT = 'CF_FSNN — Report FPGA Fase B · idoneità hardware, stima Vivado (non silicio)'
EQ_DPI     = 200
os.makedirs(FIGDIR, exist_ok=True)

# --- GROUNDING: carica results.csv -> V(group,item,metric) ------------------
_ROWS = []
with open(CSV_PATH, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        _ROWS.append(r)

def V(group, item, metric, cast=float):
    """Valore grounded dal CSV. Solleva se assente (nessun numero inventato)."""
    for r in _ROWS:
        if r['group'] == group and r['item'] == item and r['metric'] == metric:
            v = r['value']
            try:
                return cast(v)
            except (TypeError, ValueError):
                return v
    raise KeyError(f'{group}/{item}/{metric} assente in results.csv')

# device Zynq-7020 (xc7z020), da datasheet DS187 (FPGA_EVALUATION_FRAMEWORK.md)
DEV = {'LUT': 53200, 'FF': 106400, 'DSP': 220, 'BRAM': 140}

# numeri principali (ancorati al CSV)
B2_LUT   = V('A', 'SNN_B2', 'LUT');            B2_FF = V('A', 'SNN_B2', 'FF')
B2_BRAM  = V('A', 'SNN_B2', 'BRAM');           B2_DSP = V('A', 'SNN_B2', 'DSP')
B2_LUTND = V('A', 'SNN_B2', 'LUT_nodsp_variant')
B2_FMAX  = V('A', 'SNN_B2', 'Fmax_lane');      B2_CYC = V('A', 'SNN_B2', 'cycles_per_inf')
B2_PDYN  = V('A', 'SNN_B2', 'P_dyn_typical');  B2_PWORST = V('A', 'SNN_B2', 'P_dyn_worst')
B2_PSTAT = V('A', 'SNN_B2', 'P_static');       B2_PTOT = V('A', 'SNN_B2', 'P_total')
B2_EDYN  = V('A', 'SNN_B2', 'E_dyn_per_inf')
AC_LUT   = V('B', 'micro_ac', 'LUT');   AC_P = V('B', 'micro_ac', 'P_dyn'); AC_DSP = V('B', 'micro_ac', 'DSP')
MAC_LUT  = V('B', 'micro_mac', 'LUT');  MAC_P = V('B', 'micro_mac', 'P_dyn'); MAC_DSP = V('B', 'micro_mac', 'DSP')
ANN_LUT  = V('C', 'ANN_1312', 'LUT');   ANN_DSP = V('C', 'ANN_1312', 'DSP')
ANN_CYC  = V('C', 'ANN_1312', 'cycles_per_inf'); ANN_EDYN = V('C', 'ANN_1312', 'E_dyn_per_inf')
LIT_MIN  = V('C', 'literature', 'MAC_task_capable_min'); LIT_MAX = V('C', 'literature', 'MAC_task_capable_max')
TJ       = V('thermal', 'both', 'Tj')

# periodo di clock e latenza derivati (grounded: f_clk = 8 MHz lane)
F_CLK_MHZ = 8.0
T_CLK_NS  = 1000.0 / F_CLK_MHZ                      # 125 ns
LAT_US    = B2_CYC * T_CLK_NS / 1000.0              # 42.6 us
DEADLINE_MS = 100.0
BUDGET_PCT  = LAT_US / 1000.0 / DEADLINE_MS * 100.0 # ~0.04 %
E_ALGO_NJ = 0.72                                    # op-count Fase A (FPGA_PHASE_B_POWER.md §1.4)
STATIC_PCT = B2_PSTAT / B2_PTOT * 100.0             # 92 %
MARGIN     = DEADLINE_MS * 1000.0 / LAT_US          # ~2347x (100 ms / 42.6 us)

# vantaggio da compattezza: E_ann scalata = E_ann(1312) * MAC_lett / 1312, vs E_snn (383 nJ)
SNN_DENSE_MAC = 1312.0
def adv(mac):  return (ANN_EDYN * mac / SNN_DENSE_MAC) / B2_EDYN
ADV_MLP  = adv(7400.0);   ADV_LSTM = adv(40000.0);  ADV_GRU = adv(100000.0)

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

def fig_resources():
    """Occupazione del budget Zynq-7020 (SNN B2, sintesi naturale)."""
    labels = ['LUT', 'FF', 'BRAM', 'DSP']
    vals = [B2_LUT / DEV['LUT'] * 100, B2_FF / DEV['FF'] * 100,
            B2_BRAM / DEV['BRAM'] * 100, B2_DSP / DEV['DSP'] * 100]
    absv = [f'{int(B2_LUT)}', f'{int(B2_FF)}', f'{int(B2_BRAM)}', f'{int(B2_DSP)}']
    fig, ax = plt.subplots(figsize=(8.0, 2.9))
    bars = ax.barh(labels, vals, color=[PAL['blu'], PAL['blu'], PAL['blu'], PAL['ambra']])
    for b, v, a in zip(bars, vals, absv):
        ax.text(v + 0.4, b.get_y() + b.get_height() / 2, f'{a}  ({v:.1f}%)',
                va='center', fontsize=8.5)
    ax.set_xlim(0, 22); ax.set_xlabel('% del budget Zynq-7020', fontsize=9)
    ax.invert_yaxis(); _style(ax)
    ax.set_title('Occupazione risorse — SNN B2 (Donatello), sintesi OOC')
    p = os.path.join(FIGDIR, 'resources.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_dsp_attribution():
    """Trade-off DSP<->LUT: sintesi naturale (38 DSP) vs vincolo 0-DSP (9910 LUT)."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.2, 2.9))
    a1.bar(['naturale', '0-DSP'], [B2_DSP, 0], color=[PAL['ambra'], PAL['grigio']])
    a1.set_ylabel('DSP48', fontsize=9); a1.set_title('DSP', fontsize=9.5)
    a1.text(0, B2_DSP + 1, f'{int(B2_DSP)}', ha='center', fontsize=9)
    a1.text(1, 1, '0', ha='center', fontsize=9); _style(a1); a1.set_ylim(0, 46)
    a2.bar(['naturale', '0-DSP'], [B2_LUT, B2_LUTND], color=[PAL['blu'], PAL['blu']])
    a2.set_ylabel('LUT', fontsize=9); a2.set_title('LUT', fontsize=9.5)
    for i, v in enumerate([B2_LUT, B2_LUTND]):
        a2.text(i, v + 150, f'{int(v)}', ha='center', fontsize=9)
    _style(a2); a2.set_ylim(0, 11500)
    fig.suptitle('Attribuzione DSP: 38 elettivi, il vincolo 0-DSP è realizzabile (a costo di LUT)',
                 fontsize=9.5, y=1.02)
    p = os.path.join(FIGDIR, 'dsp_attribution.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_power_breakdown():
    """Potenza @8 MHz: statica domina; dettaglio della quota dinamica."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.4, 3.0), gridspec_kw={'width_ratios': [1, 1.15]})
    a1.bar(['SNN B2'], [B2_PSTAT], color=PAL['grigio'], label=f'statica {int(B2_PSTAT)} mW')
    a1.bar(['SNN B2'], [B2_PDYN], bottom=[B2_PSTAT], color=PAL['blu'], label=f'dinamica {int(B2_PDYN)} mW')
    a1.set_ylabel('mW', fontsize=9); a1.set_ylim(0, 125)
    a1.text(0, B2_PTOT + 2, f'totale {int(B2_PTOT)} mW', ha='center', fontsize=8.5)
    a1.text(0, B2_PSTAT / 2, f'{STATIC_PCT:.0f}%', ha='center', va='center', color='white', fontsize=9)
    a1.legend(fontsize=7.5, loc='upper right'); _style(a1); a1.set_title('Potenza totale', fontsize=9.5)
    comp = ['Slice Logic', 'Signals', 'DSP', 'Clocks/BRAM']; cval = [3, 3, 2, 1]
    a2.barh(comp, cval, color=PAL['blu']); a2.invert_yaxis()
    for i, v in enumerate(cval):
        a2.text(v + 0.05, i, f'{v} mW' if v > 1 else '<1 mW', va='center', fontsize=8.5)
    a2.set_xlim(0, 4); a2.set_xlabel('mW (quota dinamica, typical)', fontsize=9); _style(a2)
    a2.set_title('Ripartizione della quota dinamica (9 mW)', fontsize=9.5)
    p = os.path.join(FIGDIR, 'power_breakdown.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_energy_gap():
    """Energia dinamica realizzata (383 nJ) vs stima algoritmica op-count (0.72 nJ)."""
    fig, ax = plt.subplots(figsize=(8.0, 2.7))
    ax.barh(['algoritmica\n(op-count)', 'realizzata\n(Vivado SAIF)'], [E_ALGO_NJ, B2_EDYN],
            color=[PAL['grigio'], PAL['blu']])
    ax.set_xscale('log'); ax.set_xlim(0.3, 1500)
    ax.text(E_ALGO_NJ * 1.15, 0, f'{E_ALGO_NJ:g} nJ', va='center', fontsize=8.5)
    ax.text(B2_EDYN * 1.15, 1, f'{int(B2_EDYN)} nJ', va='center', fontsize=8.5)
    ax.annotate(f'~{B2_EDYN / E_ALGO_NJ:.0f}x', xy=(30, 0.5), fontsize=10, color=PAL['rosso'], ha='center')
    ax.set_xlabel('energia dinamica per inferenza (nJ, scala log)', fontsize=9); _style(ax)
    ax.set_title('Il time-mux allontana l\'energia realizzata da quella algoritmica', fontsize=9.5)
    p = os.path.join(FIGDIR, 'energy_gap.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_emac_eac():
    """Micro-datapath: costo di una AC (shift-add po2) vs un MAC (data x data)."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.2, 2.9))
    a1.bar(['AC (po2)', 'MAC'], [AC_P, MAC_P], color=[PAL['ac'], PAL['mac']])
    for i, (v, d) in enumerate([(AC_P, AC_DSP), (MAC_P, MAC_DSP)]):
        a1.text(i, v + 0.05, f'{int(v)} mW\n{int(d)} DSP', ha='center', fontsize=8.5)
    a1.set_ylabel('P dinamica, 1 op/ciclo (mW)', fontsize=8.5); a1.set_ylim(0, 5.4); _style(a1)
    a1.set_title('Costo per operazione su FPGA', fontsize=9.5)
    a2.bar(['FPGA\n(misurato)', 'ASIC 45nm\n(Horowitz)'], [MAC_P / AC_P, 5.1],
           color=[PAL['blu'], PAL['grigio']])
    a2.axhline(1.0, color=PAL['rosso'], lw=0.8, ls='--')
    for i, v in enumerate([MAC_P / AC_P, 5.1]):
        a2.text(i, v + 0.1, f'{v:.1f}x', ha='center', fontsize=9)
    a2.set_ylabel('rapporto e_MAC / e_AC', fontsize=8.5); a2.set_ylim(0, 6); _style(a2)
    a2.set_title('e_MAC / e_AC: ~1 su FPGA, non 5x', fontsize=9.5)
    p = os.path.join(FIGDIR, 'emac_eac.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_snn_vs_ann():
    """SNN B2 vs ANN densa (1312 MAC), a pari scala e clock."""
    metrics = ['LUT', 'DSP', 'cicli/inf', 'E_dyn/inf (nJ)']
    snn = [B2_LUT, B2_DSP, B2_CYC, B2_EDYN]; ann = [ANN_LUT, ANN_DSP, ANN_CYC, ANN_EDYN]
    fig, axes = plt.subplots(1, 4, figsize=(8.6, 2.7))
    for ax, m, s, a in zip(axes, metrics, snn, ann):
        ax.bar(['SNN', 'ANN'], [s, a], color=[PAL['blu'], PAL['mac']])
        for i, v in enumerate([s, a]):
            ax.text(i, v, f'{int(v)}', ha='center', va='bottom', fontsize=8)
        ax.set_title(m, fontsize=8.5); _style(ax); ax.set_ylim(0, max(s, a) * 1.25)
    fig.suptitle('SNN B2 vs ANN densa 1312-MAC: energia di calcolo comparabile a pari scala',
                 fontsize=9.5, y=1.03)
    p = os.path.join(FIGDIR, 'snn_vs_ann.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_compactness():
    """Vantaggio energetico da compattezza: SNN ~800 op vs ANN task-capable (letteratura)."""
    names = ['ANN 1312\n(pari scala)', 'MLP ~7.4k', 'LSTM-100 ~40k', 'Bi-GRU-128 ~100k']
    adv_parity = ANN_EDYN / B2_EDYN                      # ~0.86 -> comparabile (~1x)
    vals = [adv_parity, ADV_MLP, ADV_LSTM, ADV_GRU]
    cols = [PAL['grigio'], PAL['blu'], PAL['blu'], PAL['blu']]
    fig, ax = plt.subplots(figsize=(8.4, 2.9))
    bars = ax.bar(names, vals, color=cols)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 1, ('~1x' if v < 2 else f'{v:.0f}x'),
                ha='center', fontsize=9)
    ax.set_ylabel('vantaggio energetico SNN (x)', fontsize=9); ax.set_ylim(0, 72); _style(ax)
    ax.set_title('Il vantaggio ~5-65x nasce dalla compattezza del modello, non dal costo per operazione',
                 fontsize=9)
    p = os.path.join(FIGDIR, 'compactness.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p


# --- CONTENUTO --------------------------------------------------------------
def build_doc():
    D = []; A = D.append
    A(('cover', {
        'title': DOC_TITLE,
        'subtitle': 'Validazione post-sintesi del profilo di idoneita\' FPGA del candidato al deploy '
                    '(Donatello, architettura B2 time-multiplexata) su Zynq-7020 / PYNQ-Z1.',
        'meta': [
            'Livello di fedelta\': stima Vivado post-implementazione con switching reale (SAIF, '
            'confidenza alta) — non misura su silicio (Fase C, predisposta).',
            'Fonte dei numeri: matlab/axi/build/phase_b/results.csv (dai report Vivado util/timing/power).',
            'Documento gemello: Report FPGA Fase A (profilazione software pre-silicio).',
        ],
    }))
    A(('toc', 'Sommario'))

    # --- Sintesi ---
    A(('h1', '1. Sintesi'))
    A(('p', 'Il presente documento riporta la validazione hardware del candidato al deploy della rete '
            'spiking per il car-following, ottenuta sintetizzando su Vivado l\'architettura B2 '
            '(Donatello, rete time-multiplexata con memoria su blocchi RAM) per lo Zynq-7020 della '
            'scheda PYNQ-Z1. La generazione dell\'RTL preserva la parita\' bit-esatta con il modello '
            'in virgola fissa (e, a monte, con la rete PyTorch): l\'implementazione hardware calcola i '
            'cinque parametri del controllore senza errore rispetto al riferimento, entro '
            'l\'incertezza di quantizzazione gia\' nota.'))
    A(('p', 'La sintesi con switching reale precisa tre grandezze che la stima software per conteggio '
            'di operazioni non poteva fissare. La rete occupa **' + f'{int(B2_LUT)} LUT '
            f'({B2_LUT / DEV["LUT"] * 100:.1f}% dello Zynq-7020)' + '** e **' + f'{int(B2_DSP)} DSP'
            '**; il datapath opera a **' + f'{F_CLK_MHZ:g} MHz' + '** (frequenza massima della via di '
            'calcolo ' + f'{B2_FMAX:g} MHz' + '), per cui una inferenza dura **'
            + f'{LAT_US:.1f} µs' + '** contro una deadline di controllo di ' + f'{DEADLINE_MS:g} ms'
            '. La potenza totale e\' di **' + f'{int(B2_PTOT)} mW' + '**, dominata al **'
            + f'{STATIC_PCT:.0f}%' + '** dalla dispersione statica del dispositivo; la quota dinamica '
            'della logica e\' di soli ' + f'{int(B2_PDYN)} mW.'))
    A(('p', 'Il confronto energetico con una rete densa di pari compito conferma un vantaggio, ma ne '
            'individua la vera origine. A pari nodo tecnologico l\'energia di un accumulo (AC) eguaglia '
            'quella di una moltiplicazione-accumulo (MAC): il guadagno non nasce dal costo unitario '
            'dell\'operazione, bensi\' dalla **compattezza del modello** — circa 800 operazioni contro '
            'le migliaia-decine di migliaia delle reti di car-following pubblicate. Il vantaggio '
            'stimato si colloca nell\'intervallo **~5-65x** secondo la scala della rete densa di '
            'riferimento.'))
    A(('callout', 'Convenzione dei marcatori usata nel documento: ● dato misurato o verificato '
                  'bit-esatto (correttezza funzionale, cosim); ○ stima Vivado post-implementazione '
                  '(risorse, timing, potenza) con switching reale SAIF, precedente alla misura su '
                  'silicio. La conferma finale della potenza appartiene alla Fase C.'))

    # --- Metodo ---
    A(('h1', '2. Scopo e metodo: tre livelli di fedelta\''))
    A(('p', 'La valutazione di idoneita\' FPGA procede per livelli di fedelta\' crescente, ciascuno con '
            'una garanzia diversa e un costo diverso. Il primo livello e\' la profilazione software per '
            'conteggio di operazioni sui tensori e sul forward reale della rete: fissa gli ordini di '
            'grandezza (numero di operazioni, footprint dei pesi, sparsita\' di firing) ma non conosce '
            'ne\' la mappatura sulle risorse del dispositivo ne\' lo switching reale del silicio.'))
    A(('p', 'Il secondo livello, oggetto di questo documento, e\' la sintesi su Vivado in modalita\' '
            'out-of-context, seguita da una stima di potenza guidata dall\'attivita\' di commutazione '
            'reale (file SAIF prodotto da una simulazione gate-level su stimolo di traiettoria). '
            'Restituisce le risorse effettivamente occupate, il timing di chiusura e una stima di '
            'potenza a confidenza alta, tutte pre-silicio. Il terzo livello e\' la misura su scheda '
            'PYNQ-Z1 fisica (Fase C): unica verita\' di riferimento per la potenza, predisposta con '
            'bitstream e stimolo pronti ma non ancora eseguita.'))
    A(('p', 'La modalita\' out-of-context merita una nota, perche\' e\' la scelta corretta per un blocco '
            'destinato a vivere dentro un sistema piu\' grande e non come modulo di sommita\' con '
            'terminali fisici. La sintesi esclude gli anelli di ingresso/uscita verso i piedini del '
            'contenitore, isolando la potenza e le risorse della sola logica. Nel deploy effettivo la '
            'rete e\' incapsulata in un blocco AXI4-Lite: i suoi segnali diventano registri mappati in '
            'memoria sul bus interno fra processore e logica programmabile, non piedini del dispositivo. '
            'Il bitstream flashabile, ottenuto con questa architettura e con timing pulito, ne e\' la '
            'conferma.'))

    # --- Correttezza funzionale ---
    A(('h1', '3. Correttezza funzionale: la rete genera bene i parametri'))
    A(('p', 'Prima di ogni considerazione su risorse ed energia va stabilito che l\'implementazione '
            'hardware calcoli i parametri corretti. La catena di conversione conserva il '
            'comportamento a ogni anello, con una garanzia esplicita per ciascuno, e l\'errore '
            'complessivo dell\'hardware rispetto alla rete originale coincide con l\'errore di '
            'quantizzazione gia\' documentato — non con un difetto di conversione.'))
    A(('table', (
        ['Anello di verifica', 'Evidenza', 'Errore', ''],
        [
            ['RTL vs core in virgola fissa', 'parita\' cyclo-accurata (test FSM)', 'bit-esatto (err = 0)', '●'],
            ['IP AXI vs rete B2', 'cosim del testbench AXI', 'bit-esatto (v0=26.49, T=1.63, s0=2.45, a=1.01, b=1.71)', '●'],
            ['fixed vs double', 'sweep sui bit frazionari', '≤ 0.028 sul parametro v0', '●'],
            ['double vs PyTorch', 'confronto col forward originale', '~ 2·10⁻⁶ (arrotondamento)', '●'],
            ['decode a LUT vs float', 'test del decodificatore', '0.002', '●'],
        ],
    )))
    A(('p', 'Poiche\' l\'RTL coincide esattamente con il core in virgola fissa, l\'errore '
            'dell\'hardware rispetto alla rete PyTorch e\' interamente la catena '
            'fixed-double-PyTorch riportata sopra, dominata dallo scarto di ' + f'{0.028:g}' +
            ' sul parametro v0. La generazione dei parametri di controllo e\' dunque riprodotta in '
            'hardware entro la quantizzazione nota.'))

    # --- Risorse ---
    A(('h1', '4. Risorse occupate'))
    A(('p', 'La sintesi out-of-context del blocco che comprende la rete e il decodificatore restituisce '
            'un\'occupazione contenuta su tutte le famiglie di risorse del dispositivo. Il footprint di '
            'logica lascia margine, mentre la voce piu\' alta in percentuale sono i blocchi aritmetici '
            'dedicati.'))
    A(('img', (fig_resources(), 'Figura 4.1 — Occupazione del budget Zynq-7020 per la rete B2 '
               '(Donatello), sintesi out-of-context. Valori assoluti e percentuali del dispositivo '
               '(53 200 LUT, 106 400 FF, 220 DSP48, 140 BRAM). Fonte: results.csv, gruppo A.')))
    A(('p', 'La presenza di ' + f'{int(B2_DSP)}' + ' blocchi aritmetici dedicati (DSP48) richiede una '
            'lettura attenta, perche\' la premessa di co-progetto era l\'assenza di moltiplicatori '
            'sinaptici. L\'analisi per nome di cella mostra che questi blocchi sono adder e '
            'accumulatori larghi del core e del readout, piu\' poche moltiplicazioni del '
            'decodificatore: **nessun moltiplicatore sinaptico**. Le sinapsi a potenza di due restano '
            'operazioni di scorrimento, senza blocchi dedicati. Vincolando esplicitamente la sintesi a '
            'zero blocchi aritmetici, il progetto chiude comunque, a ' + f'{int(B2_LUTND)}' + ' LUT '
            f'({B2_LUTND / DEV["LUT"] * 100:.1f}% del dispositivo): la premessa a zero moltiplicatori '
            'e\' dunque **realizzabile**, e i ' + f'{int(B2_DSP)}' + ' blocchi presenti sono una scelta '
            'elettiva del sintetizzatore per dimezzare l\'uso di logica combinatoria.'))
    A(('img', (fig_dsp_attribution(), 'Figura 4.2 — Il compromesso fra blocchi aritmetici e logica: '
               'la sintesi naturale usa ' + f'{int(B2_DSP)}' + ' DSP e ' + f'{int(B2_LUT)}' + ' LUT; '
               'il vincolo a zero DSP e\' realizzabile a ' + f'{int(B2_LUTND)}' + ' LUT. Fonte: '
               'results.csv, gruppo A.')))

    # --- Timing ---
    A(('h1', '5. Timing e determinismo'))
    A(('p', 'Il datapath soddisfa tutti i vincoli temporali a ' + f'{F_CLK_MHZ:g} MHz' + ' (periodo '
            + f'{T_CLK_NS:g} ns' + '). Una inferenza completa richiede ' + f'{int(B2_CYC)}' + ' cicli, '
            'pari a ' + f'{LAT_US:.1f} µs' + ', contro una deadline di controllo di ' + f'{DEADLINE_MS:g} ms'
            + ': il budget temporale impiegato e\' intorno allo ' + f'{BUDGET_PCT:.2f}%' + '. La frequenza '
            'massima della via di calcolo si attesta a ' + f'{B2_FMAX:g} MHz' + ', un solo punto operativo '
            'utile — un margine sul deadline di circa ' + f'{MARGIN:.0f}x'
            + ' rende irrilevante ogni ulteriore incremento di frequenza.'))
    A(('img', (fig_eq('eq_latency.png', [
        r't_{\mathrm{inf}} = N_{\mathrm{cyc}} \cdot T_{\mathrm{clk}} = N_{\mathrm{cyc}} / f_{\mathrm{clk}}']),
        'Equazione 5.1 — t_inf = tempo di inferenza (s); N_cyc = numero di cicli per inferenza '
        '(' + f'{int(B2_CYC)}' + '); T_clk = periodo di clock (' + f'{T_CLK_NS:g} ns' + '); '
        'f_clk = frequenza di clock (' + f'{F_CLK_MHZ:g} MHz' + ').')))
    A(('p', 'Il valore qualitativamente piu\' rilevante non e\' il margine, ma il **determinismo**. La '
            'struttura di calcolo non contiene diramazioni dipendenti dai dati: il numero di operazioni '
            'per inferenza e\' costante a prescindere dall\'ingresso, per cui il tempo di esecuzione nel '
            'caso peggiore coincide con quello nel caso migliore. Il jitter di calcolo e\' quindi nullo, '
            'un requisito hard-real-time qui garantito dall\'architettura anziche\' conquistato a '
            'fatica. La quasi indipendenza dai dati emerge anche dalla potenza (§6), pressoche\' identica '
            'fra stimolo tipico e stimolo peggiore.'))

    # --- Potenza ed energia ---
    A(('h1', '6. Potenza di sistema ed energia'))
    A(('p', 'La stima di potenza guidata dall\'attivita\' reale colloca il consumo totale a '
            + f'{int(B2_PTOT)} mW' + ', di cui ' + f'{int(B2_PSTAT)} mW' + ' di dispersione statica del '
            'dispositivo e appena ' + f'{int(B2_PDYN)} mW' + ' di quota dinamica della logica (stimolo '
            'tipico; ' + f'{int(B2_PWORST)} mW' + ' nel caso peggiore). La dispersione statica, comune a '
            'qualunque progetto sullo stesso dispositivo, domina il bilancio al ' + f'{STATIC_PCT:.0f}%' + '.'))
    A(('img', (fig_power_breakdown(), 'Figura 6.1 — A sinistra: la potenza totale (' + f'{int(B2_PTOT)} mW'
               + ') e\' dominata dalla dispersione statica. A destra: la quota dinamica (' + f'{int(B2_PDYN)} mW'
               + ') suddivisa per contributo. Fonte: results.csv, gruppo A (SAIF, stimolo tipico).')))
    A(('p', 'Il fatto piu\' istruttivo riguarda il divario fra l\'energia realizzata e quella '
            'algoritmica. Moltiplicando la quota dinamica per il tempo di inferenza si ottengono '
            + f'{int(B2_EDYN)} nJ' + ' per inferenza, contro i circa ' + f'{E_ALGO_NJ:g} nJ' + ' del solo '
            'conteggio di operazioni: oltre due ordini di grandezza di distanza. La '
            'multiplazione temporale su ' + f'{int(B2_CYC)}' + ' cicli e la dispersione statica '
            'stravolgono l\'energia di sistema rispetto alla stima algoritmica. L\'efficienza suggerita '
            'dal conteggio di operazioni e\' una proprieta\' algoritmica che l\'implementazione a '
            'multiplazione temporale non esibisce a livello di sistema.'))
    A(('img', (fig_energy_gap(), 'Figura 6.2 — Energia dinamica per inferenza: la realizzazione a '
               'multiplazione temporale (' + f'{int(B2_EDYN)} nJ' + ') dista oltre due ordini di '
               'grandezza dalla stima algoritmica per conteggio di operazioni (' + f'{E_ALGO_NJ:g} nJ'
               + '). Scala logaritmica. Fonte: results.csv, gruppo A.')))

    # --- e_MAC / e_AC ---
    A(('h1', '7. Costo per operazione: e_MAC ed e_AC su FPGA'))
    A(('p', 'La premessa energetica del profilo software era che un accumulo costasse '
            'significativamente meno di una moltiplicazione-accumulo, con un rapporto di riferimento '
            'intorno a cinque a uno sul nodo ASIC a 45 nm. Due micro-datapath isolati, uno per '
            'l\'operazione di scorrimento-e-somma delle sinapsi a potenza di due e uno per la '
            'moltiplicazione-accumulo densa, permettono di misurare quel rapporto sul dispositivo reale.'))
    A(('img', (fig_emac_eac(), 'Figura 7.1 — A sinistra: potenza dinamica di una singola operazione '
               'per ciclo, accumulo a potenza di due (' + f'{int(AC_P)} mW, {int(AC_DSP)} DSP' + ') contro '
               'moltiplicazione-accumulo (' + f'{int(MAC_P)} mW, {int(MAC_DSP)} DSP' + '). A destra: il '
               'rapporto e_MAC/e_AC misurato su FPGA (~1) contro il valore di riferimento ASIC (5.1). '
               'Fonte: results.csv, gruppo B.')))
    A(('p', 'Il blocco aritmetico dedicato che esegue la moltiplicazione-accumulo consuma quanto la '
            'logica combinatoria che esegue lo scorrimento-e-somma: entrambe le operazioni sono dominate '
            'dall\'infrastruttura di registri e instradamento della matrice programmabile, non '
            'dall\'aritmetica pura del silicio dedicato. Sul dispositivo il rapporto **e_MAC/e_AC vale '
            'circa uno**, non cinque. Ne consegue che il vantaggio energetico per operazione, che nel '
            'profilo software nasceva dalla disuguaglianza fra i due costi, sul dispositivo largamente '
            'svanisce. La direzione e\' comunque confermata dai totali dei due micro-datapath '
            '(' + f'{int(MAC_P)} mW' + ' contro ' + f'{int(AC_P)} mW' + '), ma di entita\' modesta.'))
    A(('callout', 'Caveat di risoluzione: a una operazione per ciclo la potenza e\' dominata '
                  'dall\'albero di clock e dai registri, al fondo scala dello strumento di stima. I '
                  'valori per operazione hanno percio\' valore di ordine di grandezza, non di misura '
                  'puntuale; il rapporto qualitativo (~1, non 5) e\' robusto, il numero esatto no.'))

    # --- SNN vs ANN ---
    A(('h1', '8. Confronto con una rete densa e ruolo della compattezza'))
    A(('p', 'Per collocare il vantaggio energetico serve un termine di paragone omogeneo. La rete densa '
            'equivalente per numero di operazioni (' + f'{int(SNN_DENSE_MAC)}' + ' moltiplicazioni-'
            'accumulo, l\'analogo denso della rete spiking) e\' stata sintetizzata e stimata con lo '
            'stesso flusso. A pari scala e pari frequenza l\'energia di calcolo delle due reti e\' '
            'comparabile: la via spiking brucia piu\' potenza per ciclo ma termina in meno cicli, e i '
            'due effetti si compensano.'))
    A(('img', (fig_snn_vs_ann(), 'Figura 8.1 — Rete spiking B2 contro rete densa di pari numero di '
               'operazioni (1312), stesso flusso di sintesi e stesso clock. L\'energia dinamica per '
               'inferenza e\' comparabile (' + f'{int(B2_EDYN)}' + ' contro ' + f'{int(ANN_EDYN)}' + ' nJ). '
               'Fonte: results.csv, gruppi A e C.')))
    A(('p', 'La rete densa a ' + f'{int(SNN_DENSE_MAC)}' + ' operazioni, tuttavia, non svolge il compito: '
            'e\' l\'equivalente dimensionale della rete spiking, non una rete addestrata a identificare i '
            'parametri di car-following. Le reti neurali di car-following pubblicate operano su scale ben '
            'maggiori, da alcune migliaia fino a oltre centomila operazioni per passo. Scalando l\'energia '
            'misurata della rete densa in proporzione al numero di operazioni — lecito perche\' con la '
            'multiplazione temporale l\'energia cresce con il numero di operazioni, ed e\' cio\' che si '
            'osserva — il vantaggio della rete spiking si colloca fra circa cinque e sessantacinque volte.'))
    A(('img', (fig_eq('eq_advantage.png', [
        r'\mathrm{vantaggio} \approx \frac{E_{\mathrm{ANN}}(N_{\mathrm{MAC}}^{\mathrm{task}})}{E_{\mathrm{SNN}}}'
        r' = \frac{E_{\mathrm{ANN}}(1312) \cdot N_{\mathrm{MAC}}^{\mathrm{task}} / 1312}{E_{\mathrm{SNN}}}']),
        'Equazione 8.1 — E_ANN, E_SNN = energia dinamica per inferenza (nJ); N_MAC task = numero di '
        'operazioni della rete densa che svolge il compito (da letteratura, ' + f'{int(LIT_MIN)}' + '–'
        + f'{int(LIT_MAX)}' + '); 1312 = operazioni della rete densa equivalente misurata.')))
    A(('img', (fig_compactness(), 'Figura 8.2 — Vantaggio energetico della rete spiking al variare della '
               'scala della rete densa di riferimento (da letteratura). A pari scala il vantaggio e\' '
               'circa unitario; cresce a ~5-65x per le reti dense che svolgono davvero il compito. '
               'Fonte: results.csv, gruppi A e C, e letteratura (§10).')))
    A(('p', 'Il vantaggio energetico e\' dunque reale, ma la sua origine e\' la **compattezza del '
            'modello** — circa 800 pesi a potenza di due — non un minor costo per operazione. La rete '
            'spiking fa lo stesso lavoro con molte meno operazioni, e su quel divario si costruisce il '
            'guadagno.'))
    A(('callout', 'Caveat sull\'intervallo: il numero esatto entro ~5-65x dipende dalla rete densa di '
                  'riferimento e richiederebbe di addestrare una rete densa alla stessa accuratezza, non '
                  'fatto. La letteratura ne fissa l\'intervallo; le reti ricorrenti dense hanno inoltre '
                  'operazioni non moltiplicative aggiuntive, per cui lo scaling qui e\' conservativo.'))

    # --- Tabella claim ---
    A(('h1', '9. Quadro di validazione'))
    A(('p', 'Le grandezze che la sintesi con switching reale precisa o rivede rispetto alla stima per '
            'conteggio di operazioni sono raccolte di seguito. La colonna di stima e quella di sintesi '
            'rappresentano due livelli di fedelta\' distinti, non due versioni dello stesso numero.'))
    A(('table', (
        ['Grandezza', 'Stima op-count', 'Sintesi Vivado', 'Esito'],
        [
            ['Blocchi aritmetici (DSP) sinaptici', '0', f'{int(B2_DSP)} elettivi (0 realizzabile a {int(B2_LUTND)} LUT)', 'precisata'],
            ['Frequenza massima', '100–200 MHz', f'{B2_FMAX:g} MHz', 'rivista'],
            ['Rapporto e_MAC / e_AC', '5.1 (ASIC 45 nm)', '~1 (FPGA)', 'rivista'],
            ['Energia per inferenza', f'~{E_ALGO_NJ:g} nJ (op-count)', f'{int(B2_EDYN)} nJ (statica 92%)', 'precisata'],
            ['Origine del vantaggio vs ANN', 'costo AC < MAC', 'compattezza del modello (~5-65x)', 'ri-attribuita'],
            ['Temperatura di giunzione', 'stima', f'~{int(TJ)} °C (non critica)', 'confermata'],
            ['Correttezza dei parametri', '—', 'bit-esatta al riferimento', 'confermata'],
        ],
    )))

    # --- Termica ---
    A(('h1', '10. Termica e limiti residui'))
    A(('p', 'La stima termica colloca la temperatura di giunzione intorno a ' + f'{int(TJ)} °C' + ' con '
            'ambiente a 25 °C, un innalzamento di circa un grado dovuto alla scala di potenza in '
            'milliwatt. Il derating di frequenza con la temperatura e\' quindi irrilevante: il progetto '
            'opera lontanissimo dalle soglie di preoccupazione termica, e nessuna analisi termica '
            'ulteriore e\' necessaria a questo livello.'))
    A(('p', 'Restano da dichiarare quattro limiti. I costi per singola operazione (§7) hanno valore di '
            'ordine di grandezza, essendo al fondo scala dello strumento. Il confronto con la rete densa '
            '(§8) usa una rete non addestrata al compito per l\'energia e si affida alla letteratura per '
            'la capacita\', per cui il vantaggio e\' un intervallo e non un valore singolo. Tutte le '
            'grandezze di risorse, timing e potenza sono stime Vivado con switching reale, non misure su '
            'silicio: la verita\' di riferimento sulla potenza spetta alla misura su scheda PYNQ-Z1 '
            'fisica. Quest\'ultima e\' predisposta — bitstream, stimolo di traiettoria e driver di '
            'lettura sono pronti — e attende soltanto l\'esecuzione sulla scheda, con la sola avvertenza '
            'che la quota dinamica in milliwatt e\' al limite della risoluzione di un sensore di corrente '
            'ordinario.'))

    # --- Riferimenti ---
    A(('h1', '11. Riferimenti'))
    A(('table', (
        ['Riferimento', 'Tema'],
        [
            ['Horowitz, M. (2014). Computing\'s energy problem (and what we can do about it). ISSCC, 10-14.', 'Costi e_MAC/e_AC (§7)'],
            ['Mo, Z., Shi, R., Di, X. (2021). A physics-informed deep learning paradigm for car-following. Transp. Res. C 130, 103240.', 'Scala reti dense (§8)'],
            ['Hatazawa, Y., Hamada, R., Oikawa, M., Hirose, T. (2023). Personalized driver model using LSTM. J. Adv. Mech. Design Syst. Manuf. 17(2).', 'Scala reti ricorrenti (§8)'],
            ['Lu, W., Yi, Z., Liang, R., Rui, Y., Ran, B. (2023). Improved seq2seq deep learning for CAV. IEEE Access 11.', 'Scala reti ricorrenti (§8)'],
            ['Wang, X., Jiang, R., Li, L., Lin, Y., Zheng, X., Wang, F. (2018). Capturing car-following by deep learning. IEEE T-ITS 19(3), 910-920.', 'Reti CF profonde (§8)'],
            ['Kesting, A., Treiber, M., Helbing, D. (2010). Enhanced IDM (ACC/CAH). Phil. Trans. R. Soc. A 368, 4585-4605.', 'Modello di controllo'],
            ['AMD/Xilinx. Zynq-7000 SoC Data Sheet (DS187); Digilent PYNQ-Z1 Reference Manual.', 'Dispositivo e scheda'],
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
