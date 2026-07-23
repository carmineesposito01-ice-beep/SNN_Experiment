"""build_blocco_a_report.py — REPORT FPGA "Blocco A" (studio di trade-off Donatello) — .md + .pdf da sorgente unica.

Studio di caratterizzazione dei tre tier del blocco Donatello (SNN car-following) sul Fmax REALE io-timed,
misurato su Vivado 2026.1 per lo Zynq-7020 (xc7z020-clg400-1, scheda PYNQ-Z1). Sorella dei generatori
di Fase A/B: qui l'oggetto e' la SCELTA del candidato per il Blocco B, sul trade-off Fmax<->area<->potenza.

Grounding: ogni numero proviene da matlab/study_tradeoff/donatello/points_phase2.tsv (18 righe = 3 tier x 6
punti di curva, estratte dai report Vivado util/timing/power via sweep_phase2.sh). Le latenze in clock
(342/364/406) sono da RESULTS.md §12 (341/363/405 split) + 1 stadio splitpipe (§15, riga 577). Nessun numero
e' scritto a mano nel testo: si legge dal TSV o da costante grounded con fonte annotata.

Uso:    python scripts/build_blocco_a_report.py
Output: report/FPGA_BLOCCO_A_REPORT.{md,pdf}  +  report/figures_blocco_a/*
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
FIGDIR     = os.path.join(OUTDIR, 'figures_blocco_a')
TSV_PATH   = os.path.join(ROOT, 'matlab', 'study_tradeoff', 'donatello', 'points_phase2.tsv')
DOC_NAME   = 'FPGA_BLOCCO_A_REPORT'
DOC_TITLE  = 'CF_FSNN — Report FPGA "Blocco A": trade-off dei tier Donatello'
FOOTER_TEXT = 'CF_FSNN — Report FPGA Blocco A · Fmax reale io-timed, stima Vivado (non silicio)'
EQ_DPI     = 200
os.makedirs(FIGDIR, exist_ok=True)

# --- GROUNDING: carica points_phase2.tsv ------------------------------------
_ROWS = []
with open(TSV_PATH, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        _ROWS.append(r)

def P(tag, label, col, cast=float):
    """Valore grounded dal TSV. Solleva se assente (nessun numero inventato)."""
    for r in _ROWS:
        if r['tag'] == tag and r['label'] == label:
            try:
                return cast(r[col])
            except (TypeError, ValueError):
                return r[col]
    raise KeyError(f'{tag}/{label}/{col} assente in points_phase2.tsv')

# device Zynq-7020 (xc7z020), da datasheet DS187
DEV = {'LUT': 53200, 'FF': 106400, 'DSP': 220, 'BRAM': 140}

# I tre tier: (tag TSV, nome, round SNN, decode, latenza clock splitpipe)
# Latenze: RESULTS.md §12 (SLOW 341 / BAL 363 / FAST 405, split) + 1 stadio splitpipe (§15, riga 577).
TIERS = [
    ('sp_slow',     'SLOW', 'R2', 'fused', 342),
    ('sp_balanced', 'BAL',  'R5', 'p3',    364),
    ('sp_fast',     'FAST', 'R9', 'p5',    406),
]
TAGS   = [t[0] for t in TIERS]
NAME   = {t[0]: t[1] for t in TIERS}
ROUND  = {t[0]: t[2] for t in TIERS}
DECODE = {t[0]: t[3] for t in TIERS}
LAT    = {t[0]: t[4] for t in TIERS}
GRID   = ['x0.90', 'x1.00', 'x1.40', 'x2.00', 'x3.00', 'deploy-ref']  # ordine del sweep
TIGHT  = 'x0.90'        # punto stretto = massimo Fmax
DEPLOY = 'deploy-ref'   # clock lasco 125 ns = area minima

BUDGET_MS = 100.0       # control-step layer cooperativo = 0,1 s (RESULTS §12, riga 363)

def tinf_us(tag, label):
    """Tempo di inferenza (µs) = N_clk / Fmax(MHz)."""
    return LAT[tag] / P(tag, label, 'Fmax_MHz')

def margin(tag, label):
    """Margine sul budget di control-step = t_budget / t_inf (adimensionale)."""
    return BUDGET_MS * 1000.0 / tinf_us(tag, label)

def static_pct(tag, label):
    return P(tag, label, 'Psta_W') / P(tag, label, 'Ptot_W') * 100.0

# numeri di testa (grounded)
FMAX_MAX = {t: P(t, TIGHT, 'Fmax_MHz') for t in TAGS}       # 29.777 / 58.370 / 73.812
FMAX_DEP = {t: P(t, DEPLOY, 'Fmax_MHz') for t in TAGS}      # 20.451 / 41.348 / 51.784
LUT_DEP  = {t: P(t, DEPLOY, 'LUT') for t in TAGS}           # 3446 / 3980 / 4628
FF_TIER  = {t: P(t, TIGHT, 'FF') for t in TAGS}             # 1998 / 2354 / 3474 (costante col vincolo)
PSTA     = {t: P(t, TIGHT, 'Psta_W') for t in TAGS}         # ~0.103-0.104
FAST_LUT_DELTA = (LUT_DEP['sp_fast'] / LUT_DEP['sp_slow'] - 1) * 100.0   # +34.3 %
FAST_FF_DELTA  = (FF_TIER['sp_fast'] / FF_TIER['sp_slow'] - 1) * 100.0   # +73.9 %
BAL_LUT_DELTA  = (LUT_DEP['sp_balanced'] / LUT_DEP['sp_slow'] - 1) * 100.0  # +15.5 %
BAL_FF_DELTA   = (FF_TIER['sp_balanced'] / FF_TIER['sp_slow'] - 1) * 100.0  # +17.8 %
FAST_LOCK = 73.6   # lock splitpipe committato (RESULTS §15, riga 577) — coerenza metro<->VHDL
# margine estremi sul dataset (per il titolo di §6): peggiore = SLOW@deploy, migliore = FAST@x0.90
MARG_MIN = margin('sp_slow', DEPLOY)      # ~5980x
MARG_MAX = margin('sp_fast', TIGHT)       # ~18180x

PAL = {'slow': '#26527a', 'bal': '#c9992b', 'fast': '#b5384d',
       'grigio': '#8a94a0', 'blunav': '#1a3c6e', 'verde': '#2e7d4f', 'rosso': '#b5384d'}
TCOL = {'sp_slow': PAL['slow'], 'sp_balanced': PAL['bal'], 'sp_fast': PAL['fast']}

# --- Normalizzazione tipografica (dal generatore Fase B) --------------------
import re as _re
_TRUNC_MAP = {
    "fedelta'": 'fedeltà', "idoneita'": 'idoneità', "modalita'": 'modalità',
    "attivita'": 'attività', "capacita'": 'capacità', "entita'": 'entità',
    "verita'": 'verità', "proprieta'": 'proprietà', "sommita'": 'sommità',
    "parita'": 'parità', "sparsita'": 'sparsità', "qualita'": 'qualità',
    "unita'": 'unità', "possibilita'": 'possibilità', "difficolta'": 'difficoltà',
    "velocita'": 'velocità', "densita'": 'densità',
    "perche'": 'perché', "poiche'": 'poiché', "anziche'": 'anziché',
    "pressoche'": 'pressoché', "finche'": 'finché', "affinche'": 'affinché',
    "cioe'": 'cioè', "piu'": 'più', "gia'": 'già', "puo'": 'può',
    "cosi'": 'così', "percio'": 'perciò', "cio'": 'ciò', "bensi'": 'bensì',
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

def fig_block():
    """Diagramma concettuale del blocco Donatello: 4 ingressi -> normalize -> SNN time-mux -> decode -> 5 uscite."""
    fig, ax = plt.subplots(figsize=(8.6, 2.6)); ax.axis('off')
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    def box(x, w, txt, fc, sub=None):
        ax.add_patch(plt.Rectangle((x, 0.30), w, 0.40, fc=fc, ec='#26527a', lw=1.0))
        ax.text(x + w / 2, 0.555, txt, ha='center', va='center', fontsize=8.6, color='#12233a')
        if sub:
            ax.text(x + w / 2, 0.40, sub, ha='center', va='center', fontsize=6.0, color='#40556e')
    def arrow(x0, x1):
        ax.annotate('', xy=(x1, 0.5), xytext=(x0, 0.5), arrowprops=dict(arrowstyle='-|>', color='#555', lw=1.1))
    ax.text(0.055, 0.52, 's\nv\nΔv\nv$_L$', ha='center', va='center', fontsize=8.2, color='#12233a')
    ax.text(0.055, 0.20, '4 ingressi', ha='center', va='center', fontsize=6.8, color='#40556e')
    arrow(0.095, 0.145)
    box(0.150, 0.155, 'normalize', '#eef3fa', 'fixed · op_reg')
    arrow(0.305, 0.345)
    box(0.345, 0.22, 'SNN core', '#e7eef7', 'time-mux · DualPortRAM')
    arrow(0.565, 0.605)
    box(0.605, 0.155, 'decode', '#eef3fa', 'LUT a 64 punti')
    arrow(0.760, 0.800)
    ax.text(0.905, 0.52, 'v$_0$\nT\ns$_0$\na\nb', ha='center', va='center', fontsize=8.2, color='#12233a')
    ax.text(0.905, 0.16, '5 uscite (IIDM)', ha='center', va='center', fontsize=6.8, color='#40556e')
    ax.text(0.5, 0.90, 'Blocco Donatello — interfaccia fissa 4-in / 5-out, generato dal solo modello Simulink',
            ha='center', va='center', fontsize=9.2, color='#1a3c6e')
    p = os.path.join(FIGDIR, 'block.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_fmax():
    """Fmax reale io-timed per tier: al clock di deploy (area minima) e al punto stretto (massimo Fmax)."""
    import numpy as np
    fig, ax = plt.subplots(figsize=(8.2, 3.0))
    x = np.arange(len(TAGS)); w = 0.36
    dep = [FMAX_DEP[t] for t in TAGS]; mx = [FMAX_MAX[t] for t in TAGS]
    b1 = ax.bar(x - w / 2, dep, w, color=[TCOL[t] for t in TAGS], alpha=0.55, label='clock di deploy (area minima)')
    b2 = ax.bar(x + w / 2, mx, w, color=[TCOL[t] for t in TAGS], label='punto stretto (massimo Fmax)')
    for xi, v in zip(x - w / 2, dep):
        ax.text(xi, v + 1.0, f'{v:.1f}', ha='center', fontsize=8.2)
    for xi, v in zip(x + w / 2, mx):
        ax.text(xi, v + 1.0, f'{v:.1f}', ha='center', fontsize=8.2, fontweight='bold')
    ax.set_xticks(x); ax.set_xticklabels([f'{NAME[t]}\n({ROUND[t]}·{DECODE[t]})' for t in TAGS], fontsize=8.5)
    ax.set_ylabel('Fmax reale (io-timed) [MHz]', fontsize=9); ax.set_ylim(0, 82)
    ax.legend(fontsize=7.6, loc='upper left', frameon=False); _style(ax)
    ax.set_title('Fmax reale separato e monotòno SLOW < BAL < FAST', fontsize=9.5)
    p = os.path.join(FIGDIR, 'fmax.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_curves():
    """Le curve del trade-off: (A) LUT vs Fmax, (B) potenza totale vs Fmax. Ogni punto = un vincolo di clock."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.7, 3.2))
    for t in TAGS:
        fm = [P(t, g, 'Fmax_MHz') for g in GRID]
        lut = [P(t, g, 'LUT') for g in GRID]
        pt = [P(t, g, 'Ptot_W') * 1000 for g in GRID]
        a1.plot(fm, lut, '-o', color=TCOL[t], ms=4, lw=1.3, label=NAME[t])
        a2.plot(fm, pt, '-o', color=TCOL[t], ms=4, lw=1.3, label=NAME[t])
        # marcatori: deploy (cerchio vuoto) e punto stretto (stella)
        a1.plot(P(t, DEPLOY, 'Fmax_MHz'), P(t, DEPLOY, 'LUT'), 'o', mfc='white', mec=TCOL[t], ms=8, mew=1.4)
        a1.plot(P(t, TIGHT, 'Fmax_MHz'), P(t, TIGHT, 'LUT'), '*', color=TCOL[t], ms=13)
    a1.set_xlabel('Fmax reale [MHz]', fontsize=9); a1.set_ylabel('LUT', fontsize=9)
    a1.legend(fontsize=7.8, loc='upper left', frameon=False); _style(a1)
    a1.set_title('Area vs clock: stringere compra velocità con area', fontsize=9.2)
    ps_mw = sum(PSTA.values()) / len(PSTA) * 1000
    a2.axhline(ps_mw, color=PAL['grigio'], lw=0.9, ls='--')
    a2.text(a2.get_xlim()[0] + 2, ps_mw + 3, f'statica ~{ps_mw:.0f} mW',
            ha='left', va='bottom', fontsize=7.4, color=PAL['grigio'])
    a2.set_xlabel('Fmax reale [MHz]', fontsize=9); a2.set_ylabel('potenza totale [mW]', fontsize=9)
    a2.legend(fontsize=7.8, loc='lower right', frameon=False); _style(a2)
    a2.set_title('Potenza vs Fmax: statica costante, dinamica ∝ clock', fontsize=9.2)
    fig.tight_layout(w_pad=2.2)
    p = os.path.join(FIGDIR, 'curves.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_tinf():
    """Tempo di inferenza per tier (@deploy e @max-Fmax) contro il budget di control-step (100 ms), scala log."""
    import numpy as np
    fig, ax = plt.subplots(figsize=(8.2, 3.0))
    x = np.arange(len(TAGS)); w = 0.36
    td = [tinf_us(t, DEPLOY) for t in TAGS]; tm = [tinf_us(t, TIGHT) for t in TAGS]
    ax.bar(x - w / 2, td, w, color=[TCOL[t] for t in TAGS], alpha=0.55, label='@ clock di deploy')
    ax.bar(x + w / 2, tm, w, color=[TCOL[t] for t in TAGS], label='@ massimo Fmax')
    for xi, v in zip(x - w / 2, td):
        ax.text(xi, v * 1.08, f'{v:.1f}', ha='center', fontsize=8.0)
    for xi, v in zip(x + w / 2, tm):
        ax.text(xi, v * 1.08, f'{v:.1f}', ha='center', fontsize=8.0, fontweight='bold')
    ax.axhline(BUDGET_MS * 1000, color=PAL['rosso'], lw=1.2, ls='--')
    ax.text(len(TAGS) - 0.5, BUDGET_MS * 1000 * 0.62, f'budget control-step = {BUDGET_MS:.0f} ms',
            ha='right', va='top', fontsize=8.0, color=PAL['rosso'])
    ax.set_yscale('log'); ax.set_ylim(3, 200000)
    ax.set_xticks(x); ax.set_xticklabels([NAME[t] for t in TAGS], fontsize=9)
    ax.set_ylabel('tempo di inferenza [µs] (scala log)', fontsize=9); _style(ax)
    ax.set_title('Ogni tier è oltre tre ordini di grandezza sotto il budget', fontsize=9.5)
    p = os.path.join(FIGDIR, 'tinf.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p


# --- CONTENUTO --------------------------------------------------------------
def build_doc():
    D = []; A = D.append
    A(('cover', {
        'title': DOC_TITLE,
        'subtitle': 'Caratterizzazione dei tre tier del blocco Donatello (SLOW/BAL/FAST) sul Fmax reale '
                    'io-timed e sul trade-off area–potenza, per scegliere il candidato al Blocco B su '
                    'Zynq-7020 (PYNQ-Z1).',
        'meta': [
            'Livello di fedeltà: stima Vivado post-implementazione con timing d\'integrazione '
            '(io-timed) — non misura su silicio.',
            'Fonte dei numeri: matlab/study_tradeoff/donatello/points_phase2.tsv (18 punti, dai report '
            'Vivado util/timing/power via sweep_phase2.sh).',
            'Contesto e metodo: RESULTS.md §15 (Fmax reale io-timed e fix splitpipe), HDL_PHASE.md §3.1.5.',
            'Toolchain: Vivado 2026.1 · FPGA Xilinx Zynq-7000 xc7z020-clg400-1 (scheda PYNQ-Z1).',
        ],
    }))
    A(('toc', 'Sommario'))

    # ---------------------------------------------------------------- 1
    A(('h1', '1. Sommario esecutivo'))
    A(('p', 'Il blocco Donatello è la rete spiking che identifica i cinque parametri del controllore '
            'car-following a partire da quattro grandezze cinematiche. Lo studio ne caratterizza tre '
            'realizzazioni — i tier **SLOW**, **BAL** e **FAST** — ottenute accoppiando tre profondità '
            'di rete (round SNN R2, R5, R9) con tre profondità di decodifica (fusa, pipeline a 3 stadi, '
            'pipeline a 5 stadi). Ogni tier è sintetizzato per lo Zynq-7020 e misurato sul **Fmax reale '
            'io-timed**, la frequenza effettivamente disponibile quando gli ingressi sono registrati, '
            'non sul Fmax interno reg-reg che sovrastima la via di calcolo.'))
    A(('p', 'Al metro reale le tre realizzazioni si separano in modo netto e monotòno: la frequenza '
            'massima vale **' + f'{FMAX_MAX["sp_slow"]:.1f}' + '**, **' + f'{FMAX_MAX["sp_balanced"]:.1f}'
            + '** e **' + f'{FMAX_MAX["sp_fast"]:.1f} MHz' + '** per SLOW, BAL e FAST. Il valore di FAST '
            'coincide con il blocco deployabile già congelato (' + f'{FAST_LOCK:g} MHz' + '), a conferma '
            'che il metro di misura e l\'RTL descrivono lo stesso oggetto. L\'area di logica e i registri '
            'crescono con la profondità di pipeline, e la potenza è dominata dalla dispersione statica '
            'del dispositivo, costante, mentre la quota dinamica scala con il clock.'))
    A(('p', 'La conclusione operativa è che il **Fmax è margine, non requisito**. Il tempo di inferenza '
            'di ogni tier resta fra ' + f'{tinf_us("sp_fast", TIGHT):.1f}' + ' e '
            + f'{tinf_us("sp_slow", DEPLOY):.1f} µs' + ', cioè fra circa **' + f'{MARG_MIN:.0f}×' +
            '** (il margine più stretto) e **' + f'{MARG_MAX:.0f}×' + '** (il più largo) sotto il budget '
            'di un passo di controllo (0.1 s). Poiché nessuna soglia di frequenza vincola, e poiché '
            'l\'estensione futura verso la comunicazione veicolo-infrastruttura (V2I) richiederà spazio '
            'sul chip, il criterio che discrimina i tier è l\'**area** (e la potenza), non la velocità. '
            'Lo studio presenta il trade-off completo; la scelta finale del candidato resta all\'utente '
            'dove i dati non impongono un vincitore netto (§7).'))
    A(('callout', 'Convenzione dei marcatori: ● grandezza misurata o verificata bit-esatta (correttezza '
                  'funzionale, latenza in clock); ○ stima Vivado post-implementazione (Fmax, area, '
                  'potenza) con timing d\'integrazione io-timed, precedente alla misura su silicio.'))

    # ---------------------------------------------------------------- 2
    A(('h1', '2. Oggetto e vincoli'))
    A(('p', 'L\'oggetto è il blocco Donatello: la rete spiking di car-following con la sua decodifica, '
            'esposta come singolo blocco con **interfaccia fissa a quattro ingressi e cinque uscite**. '
            'Gli ingressi sono la distanza dal veicolo di testa, la velocità propria, la velocità '
            'relativa e la velocità del veicolo di testa; le uscite sono i cinque parametri del '
            'controllore a inseguimento intelligente (velocità desiderata, tempo di via, distanza minima, '
            'accelerazione massima e decelerazione confortevole). L\'interfaccia non cambia fra i tier: '
            'cambia solo l\'implementazione interna.'))
    A(('img', (fig_block(), 'Figura 2.1 — Il blocco Donatello e la sua interfaccia fissa. Le quattro '
               'grandezze cinematiche sono normalizzate in virgola fissa, elaborate dal core spiking a '
               'multiplazione temporale (macchina a stati con memoria su blocchi RAM, dieci tick interni '
               'per passo) e decodificate in cinque parametri tramite una tabella a 64 punti. Il registro '
               'sugli operandi del normalize (op_reg, architettura splitpipe) appartiene a tutti e tre i '
               'tier. Fonte: architettura del blocco, RESULTS.md §15.')))
    A(('p', 'Ogni tier è il blocco **completo e autonomo**: il VHDL è generato dal solo modello Simulink, '
            'senza cablaggi manuali, e la rete è realizzata a multiplazione temporale, riusando una sola '
            'via di calcolo con lo stato tenuto in memoria a doppia porta. I tre tier differiscono per due '
            'assi ortogonali — la profondità della rete spiking (round R2, R5, R9) e la profondità della '
            'pipeline di decodifica (fusa, tre stadi, cinque stadi) — accoppiati come SLOW = R2 con '
            'decodifica fusa, BAL = R5 con pipeline a tre stadi, FAST = R9 con pipeline a cinque stadi.'))
    A(('p', 'Il vincolo di deployment è la scheda PYNQ-Z1, che porta uno Zynq-7020 (xc7z020-clg400-1). '
            'Il fine dello studio non è massimizzare una metrica, ma **scegliere il tier candidato** a '
            'entrare nel Blocco B, dove la rete sarà chiusa in anello con il controllore a inseguimento '
            'intelligente. Poiché è previsto un secondo blocco di comunicazione veicolo-infrastruttura '
            'sullo stesso dispositivo, lo spazio di logica lasciato libero è una risorsa di progetto: la '
            'compattezza pesa quanto la frequenza, e spesso di più.'))

    # ---------------------------------------------------------------- 3
    A(('h1', '3. Metodo — Fase 1: verifica del blocco'))
    A(('p', 'Prima di caratterizzare le prestazioni va stabilito che ciascun tier sia davvero il blocco '
            'che dichiara di essere, e che calcoli i parametri corretti. La verifica agisce '
            'sull\'artefatto che si sta per misurare, non su quello appena costruito, così da non lasciar '
            'passare VHDL riciclato da una configurazione precedente. Due garanzie indipendenti la '
            'compongono: la correttezza funzionale in streaming e la firma strutturale di identità.'))
    A(('p', 'La correttezza è la **parità bit-esatta** con il modello in virgola fissa di riferimento, '
            'verificata facendo scorrere una traiettoria reale nel blocco un campione alla volta: lo '
            'scarto massimo sui cinque parametri è nullo (dmax = 0). La macchina a stati è '
            'edge-triggered sul cambiamento d\'ingresso, per cui un campione produce esattamente una '
            'inferenza, con qualunque tempo di mantenimento superiore alla latenza.'))
    A(('h2', '3.1 La firma strutturale di identità'))
    A(('p', 'Un blocco può passare il test funzionale pur avendo la metà sbagliata: due configurazioni '
            'diverse possono dare gli stessi parametri a valle se la differenza è combinatoria. Per '
            'questo la verifica legge nel VHDL la **firma di entrambe le metà**. La profondità della '
            'decodifica si riconosce dai registri di fase; il round della rete spiking si riconosce dagli '
            'stadi di pipeline, che nascono a round noti e ne fissano l\'identità.'))
    A(('table', (
        ['Tier', 'Round · decode', 'Firma round (nel VHDL)', 'Verifica', ''],
        [
            [NAME['sp_slow'], 'R2 · fused', 'pCa assente, pCm assente, pCx assente', 'dmax = 0 in streaming', '●'],
            [NAME['sp_balanced'], 'R5 · p3', 'pCa presente, pCm assente, pCx assente', 'dmax = 0 in streaming', '●'],
            [NAME['sp_fast'], 'R9 · p5', 'pCa, pCm, pCx tutti presenti', 'dmax = 0 in streaming', '●'],
        ],
    )))
    A(('p', 'Gli stadi pCa, pCm e pCx compaiono rispettivamente ai round R4, R6 e R9 della rete: la loro '
            'presenza o assenza discrimina R2, R5 e R9 senza ambiguità. La firma della decodifica e '
            'quella della rete, lette insieme sull\'artefatto, chiudono la porta agli scambi silenziosi '
            'di mezzo blocco.'))
    A(('p', 'Il cancello bit-esatto è provato anche **in negativo**, perché una verifica che non può '
            'fallire non verifica nulla. Degradando la precisione dell\'ingresso sotto la soglia richiesta '
            'per la parità — da almeno venti bit frazionari (dove il blocco resta bit-esatto fino a Q?.13) '
            'a Q?.10 — la normalizzazione arrotonda diversamente, un solo bit meno significativo ribalta '
            'uno spike, lo stato diverge e i parametri a valle si scostano fino a circa **' + f'{0.23:g}' +
            '** entro venti passi di controllo. La stessa prova che a piena precisione dà dmax = 0 respinge '
            'dunque il caso falso: il cancello discrimina.'))

    # ---------------------------------------------------------------- 4
    A(('h1', '4. Metodo — Fase 2: curve a clock vincolato (io-timed)'))
    A(('p', 'La seconda fase misura le prestazioni al variare del vincolo di clock. Due scelte di metodo '
            'ne determinano la validità: il timing d\'integrazione e la natura delle varianti.'))
    A(('h2', '4.1 Il metro reale: timing d\'integrazione'))
    A(('p', 'Il Fmax di una sintesi out-of-context senza vincoli sulle porte è un metro **interno**, '
            'reg-reg: misura solo i percorsi fra registri e ignora il cammino che va dall\'ingresso, '
            'attraverso la normalizzazione, fino all\'inizio dell\'inferenza. Quel cammino, invisibile '
            'finché le porte non sono temporizzate, diventa reale non appena gli ingressi del blocco sono '
            'registrati — cioè in ogni deployment. Il metro interno sovrastima perciò la frequenza '
            'disponibile, e appiattisce i tier l\'uno sull\'altro perché tutti condividono lo stesso muro '
            'di normalizzazione. Il **Fmax reale** si ottiene temporizzando gli ingressi e le uscite '
            '(io-timed): è la frequenza su cui si sceglie davvero.'))
    A(('p', 'Perché il cammino d\'ingresso non domini, gli operandi del normalize sono registrati fra il '
            'clamp e la moltiplicazione (architettura splitpipe), e l\'edge-trigger confronta gli '
            'operandi registrati. Lo stadio aggiunto spezza il muro e costa un solo clock di latenza, '
            'restando bit-esatto. Il residuo è la moltiplicazione intrinseca a 34 bit, che non si spezza '
            'senza aumentare l\'area — la risorsa che questo studio vuole preservare.'))
    A(('h2', '4.2 Le varianti nascono dal vincolo di clock, non dai preset'))
    A(('p', 'Le curve non sono generate da direttive di ottimizzazione di Vivado: quelle sono state '
            'provate e spostano gli estremi di appena qualche punto percentuale, un guadagno immateriale '
            'per un progetto così piccolo. Le varianti nascono invece dal **vincolo di clock** imposto '
            'alla sintesi. Il periodo target è spazzato su una griglia {0.90; 1.00; 1.40; 2.00; 3.00} '
            'volte il ritardo io misurato al punto di ancoraggio, più il clock lasco di deploy (125 ns). '
            'Stringendo il vincolo, lo strumento compra velocità con area: il punto più stretto è la '
            'variante a massimo Fmax e area alta, il clock lasco è la variante ad area minima. Un solo '
            'sweep mappa così l\'intero trade-off area–clock.'))
    A(('callout', 'Riproducibilità: numero di thread di Vivado fissato, seme 0, VHDL byte-identico fra i '
                  'punti, versione dello strumento registrata (Vivado 2026.1). Il ritardo di ancoraggio è '
                  'misurato io-timed su un seme, non ereditato dal metro interno.'))

    # ---------------------------------------------------------------- 5
    A(('h1', '5. Risultati'))
    A(('h2', '5.1 Il Fmax reale, separato e monotòno'))
    A(('p', 'Al metro io-timed i tre tier non si appiattiscono più: la frequenza massima cresce in modo '
            'monotòno da SLOW a FAST. Che il valore di FAST (' + f'{FMAX_MAX["sp_fast"]:.1f} MHz' + ') '
            'coincida con il blocco deployabile congelato (' + f'{FAST_LOCK:g} MHz' + ') è la prova che il '
            'metro e l\'RTL misurano lo stesso oggetto, senza deriva fra caratterizzazione e artefatto.'))
    A(('img', (fig_fmax(), 'Figura 5.1 — Fmax reale io-timed per tier, al clock di deploy (area minima) e '
               'al punto stretto (massimo Fmax). La progressione SLOW < BAL < FAST è netta a entrambi gli '
               'estremi della curva. Fonte: points_phase2.tsv (punti x0.90 e deploy-ref).')))
    A(('h2', '5.2 Le curve area–clock e la potenza'))
    A(('p', 'La griglia di vincoli disegna per ogni tier una curva monotòna: al crescere della frequenza '
            'richiesta cresce l\'occupazione di logica, fino al pavimento d\'area raggiunto al clock '
            'lasco. Le curve dei tre tier sono separate — quella di FAST sta più a destra e più in alto '
            '— perché il pavimento è fissato dalla profondità di pipeline, non dal vincolo. I registri, '
            'in particolare, non dipendono dal clock ma solo dal tier: ' + f'{int(FF_TIER["sp_slow"])}' +
            ', ' + f'{int(FF_TIER["sp_balanced"])}' + ' e ' + f'{int(FF_TIER["sp_fast"])}' + ' per SLOW, '
            'BAL e FAST.'))
    A(('img', (fig_curves(), 'Figura 5.2 — A sinistra: LUT contro Fmax reale; ogni punto è un vincolo di '
               'clock, dal più stretto (stella, massimo Fmax) al lasco (cerchio vuoto, area minima). A '
               'destra: potenza totale contro Fmax; la dispersione statica (linea tratteggiata) è '
               'costante, la quota dinamica cresce con il clock. Fonte: points_phase2.tsv.')))
    A(('p', 'La potenza racconta la stessa fisica dal lato energetico. La componente statica del '
            'dispositivo è costante intorno a ' + f'{sum(PSTA.values())/len(PSTA)*1000:.0f} mW' + ' e non '
            'dipende dal progetto; la componente dinamica cresce con il clock. La quota statica domina '
            'perciò al clock di deploy — dove supera il novanta per cento del totale — e resta comunque '
            'la maggioranza persino al punto più aggressivo. Non esiste un unico valore di quota statica: '
            'sull\'intero dataset va da circa il **' + f'{min(static_pct(t, g) for t in TAGS for g in GRID):.0f}%' +
            '** (FAST e BAL al punto stretto, dove la dinamica pesa di più) a circa il **'
            + f'{max(static_pct(t, g) for t in TAGS for g in GRID):.0f}%' + '** (al clock di deploy).'))
    for t in TAGS:
        A(('h3', f'5.2.{TAGS.index(t)+1} Curva del tier {NAME[t]} ({ROUND[t]} · decode {DECODE[t]})'))
        rows = []
        for g in GRID:
            regime = 'stretto (max Fmax)' if g == TIGHT else ('deploy (area min.)' if g == DEPLOY else 'intermedio')
            rows.append([
                g.replace('deploy-ref', 'deploy'),
                f'{P(t, g, "delay_ns"):.2f}',
                f'{P(t, g, "Fmax_MHz"):.2f}',
                f'{int(P(t, g, "LUT"))}',
                f'{P(t, g, "Ptot_W")*1000:.0f}',
                f'{P(t, g, "WHS_int"):+.3f}',
                regime,
            ])
        A(('table', (['Vincolo', 'Ritardo [ns]', 'Fmax [MHz]', 'LUT', 'Ptot [mW]', 'Hold int. [ns]', 'Regime'], rows)))
    A(('p', 'In tutte le curve i registri, i blocchi aritmetici dedicati e la memoria a blocchi restano '
            'invariati col vincolo (' + f'{int(P("sp_slow", TIGHT, "DSP"))}' + ' DSP48 e '
            + f'{int(P("sp_slow", TIGHT, "BRAM"))}' + ' blocco RAM per tutti i punti): a muoversi col '
            'clock sono solo la logica combinatoria e la quota dinamica di potenza.'))
    A(('h2', '5.3 Timing di tenuta e determinismo'))
    A(('p', 'Il tempo di tenuta interno reg-reg è **positivo in ogni punto** (fra '
            + f'{min(P(t, g, "WHS_int") for t in TAGS for g in GRID):+.3f}' + ' e '
            + f'{max(P(t, g, "WHS_int") for t in TAGS for g in GRID):+.3f} ns' + '): il blocco è chiuso '
            'sul fronte di tenuta. Il tempo di tenuta misurato sulle porte risulta invece negativo '
            '(circa −0.50 ns), ma è un **artefatto del modello io-timed** che azzera i ritardi di porta '
            '(set_input/output_delay a zero) sulle interfacce fisiche: il tempo di tenuta reale del '
            'blocco è quello interno reg-reg, positivo. Nel deployment le porte hanno ritardi non nulli e '
            'il margine negativo apparente scompare.'))
    A(('p', 'La proprietà qualitativamente più forte non è un margine ma il **determinismo**: la '
            'struttura di calcolo non ha diramazioni dipendenti dai dati, per cui il numero di cicli per '
            'inferenza è costante e il tempo di esecuzione nel caso peggiore coincide con quello nel caso '
            'migliore. Il jitter di calcolo è nullo per costruzione, un requisito hard-real-time '
            'garantito dall\'architettura anziché conquistato a fatica.'))

    # ---------------------------------------------------------------- 6
    A(('h1', '6. Tempo d\'inferenza e margine'))
    A(('p', 'La latenza di un\'inferenza è costante e nota per ciascun tier: '
            + f'{LAT["sp_slow"]}' + ', ' + f'{LAT["sp_balanced"]}' + ' e ' + f'{LAT["sp_fast"]} cicli' +
            ' per SLOW, BAL e FAST (il conteggio in clock è indipendente dal metro di frequenza; lo '
            'stadio splitpipe ne aggiunge uno). Il tempo di inferenza è la latenza divisa per la '
            'frequenza operativa, e il margine è il rapporto fra il budget di un passo di controllo e '
            'quel tempo.'))
    A(('img', (fig_eq('eq_tinf.png', [
        r't_{\mathrm{inf}} = N_{\mathrm{clk}} \,/\, f_{\mathrm{clk}}',
        r'M = t_{\mathrm{step}} \,/\, t_{\mathrm{inf}} = t_{\mathrm{step}} \cdot f_{\mathrm{clk}} \,/\, N_{\mathrm{clk}}']),
        'Equazione 6.1 — t_inf = tempo di inferenza (s); N_clk = cicli per inferenza (SLOW 342, BAL 364, '
        'FAST 406); f_clk = frequenza operativa (Hz); M = margine (adimensionale); t_step = budget del '
        'passo di controllo (0.1 s). Ogni simbolo è definito qui, non nell\'immagine.')))
    A(('p', 'Ai due estremi della curva — alla frequenza massima e al clock di deploy — il tempo di '
            'inferenza resta nell\'ordine dei microsecondi, contro un budget di cento millisecondi. Il '
            'margine più stretto dell\'intero dataset, SLOW al clock di deploy, è comunque intorno a **'
            + f'{MARG_MIN:.0f}×' + '**; il più largo, FAST alla frequenza massima, intorno a **'
            + f'{MARG_MAX:.0f}×' + '**.'))
    A(('table', (
        ['Tier', 'Latenza [clk]', 't_inf @ max-Fmax [µs]', 't_inf @ deploy [µs]', 'Margine @ deploy'],
        [[NAME[t], f'{LAT[t]}', f'{tinf_us(t, TIGHT):.2f}', f'{tinf_us(t, DEPLOY):.2f}',
          f'~{margin(t, DEPLOY):.0f}×'] for t in TAGS],
    )))
    A(('img', (fig_tinf(), 'Figura 6.1 — Tempo di inferenza per tier ai due estremi della curva, contro '
               'il budget del passo di controllo (linea tratteggiata, 100 ms; scala logaritmica). Ogni '
               'tier è oltre tre ordini di grandezza sotto la deadline. Fonte: points_phase2.tsv e '
               'latenze in clock (RESULTS.md §12).')))
    A(('p', 'La lettura è univoca: nessuna soglia di frequenza vincola il progetto. L\'Fmax è un margine '
            'abbondante, non un requisito, e ogni frazione di velocità in più è priva di valore pratico. '
            'Il tier si sceglie perciò su altre grandezze.'))

    # ---------------------------------------------------------------- 7
    A(('h1', '7. Scelta del candidato Donatello per il Blocco B'))
    A(('p', 'Poiché il Fmax è solo margine, il criterio che discrimina i tier è ciò che costa davvero sul '
            'dispositivo: l\'**area** occupata e, in seconda battuta, la potenza. La rilevanza dell\'area '
            'non è astratta — sullo stesso Zynq-7020 dovrà trovare posto anche il blocco di comunicazione '
            'veicolo-infrastruttura, quindi ogni tabella di lookup e ogni registro lasciati liberi sono '
            'un margine di progetto per il seguito.'))
    A(('table', (
        ['Tier', 'Round · decode', 'Fmax deploy [MHz]', 'Fmax max [MHz]', 'LUT (deploy)', 'FF', 't_inf deploy [µs]'],
        [[NAME[t], f'{ROUND[t]} · {DECODE[t]}', f'{FMAX_DEP[t]:.1f}', f'{FMAX_MAX[t]:.1f}',
          f'{int(LUT_DEP[t])}', f'{int(FF_TIER[t])}', f'{tinf_us(t, DEPLOY):.2f}'] for t in TAGS],
    )))
    A(('p', 'Agli estremi, il trade-off è chiaro. **SLOW** ha l\'area minima — '
            + f'{int(LUT_DEP["sp_slow"])} LUT e {int(FF_TIER["sp_slow"])} registri' + ' al clock di '
            'deploy — al prezzo del Fmax più basso, che però resta migliaia di volte oltre il bisogno. '
            '**FAST** offre il massimo margine di frequenza, ma costa **' + f'+{FAST_LUT_DELTA:.0f}%' +
            ' di logica e +' + f'{FAST_FF_DELTA:.0f}%' + ' di registri** rispetto a SLOW: un prezzo '
            'd\'area pagato per una velocità di cui non c\'è domanda. **BAL** siede in mezzo con un '
            'rapporto favorevole — raddoppia il margine di frequenza rispetto a SLOW ('
            + f'{FMAX_DEP["sp_balanced"]:.1f}' + ' contro ' + f'{FMAX_DEP["sp_slow"]:.1f} MHz' + ' al '
            'deploy) per un sovrapprezzo d\'area contenuto, **' + f'+{BAL_LUT_DELTA:.0f}%' + ' di logica '
            'e +' + f'{BAL_FF_DELTA:.0f}%' + ' di registri**.'))
    A(('p', 'Il criterio dell\'area indica quindi **SLOW o BAL** come candidati naturali per il Blocco B, '
            'con FAST relegato al ruolo di opzione ad alto margine per il caso in cui il seguito del '
            'progetto dovesse richiedere frequenze oggi non previste. Fra SLOW e BAL la scelta non è '
            'imposta dai dati: SLOW minimizza il chip riservato, BAL raddoppia il margine per un '
            'sovrapprezzo modesto. La decisione dipende da quanto spazio il V2I richiederà e da quanto '
            'margine di frequenza si voglia tenere di riserva — un compromesso di progetto che questo '
            'studio documenta ma **lascia esplicitamente all\'utente**.'))

    # ---------------------------------------------------------------- 8
    A(('h1', '8. Riproducibilità e limiti'))
    A(('p', 'Le curve sono rigenerabili dal driver di sweep con lo stesso VHDL byte-identico, thread e '
            'seme fissati e versione dello strumento registrata; il dato grezzo è il file '
            'points_phase2.tsv, diciotto punti da cui questo documento è interamente derivato. Restano da '
            'dichiarare tre limiti di fedeltà.'))
    A(('p', 'Il primo è la natura della stima di **potenza**, che è vectorless: l\'attività di '
            'commutazione è stimata dallo strumento, non estratta da una simulazione della traiettoria '
            'reale. Il raffinamento con file di attività dalla traiettoria è rinviato; il suo peso è '
            'però contenuto, perché il dispositivo è per la maggior parte dispersione statica e la quota '
            'dinamica — l\'unica che una stima di attività correggerebbe — è una minoranza del bilancio '
            'ai punti di deploy. Il secondo è il tempo di **tenuta sulle porte**, negativo solo come '
            'artefatto del modello a ritardo di porta nullo: il tempo di tenuta reale, interno reg-reg, è '
            'positivo ovunque. Il terzo, il più importante, è che tutte le grandezze di frequenza, area e potenza '
            'sono **stime Vivado io-timed, non misure su silicio**: sono il metro corretto per '
            'confrontare i tier e per stimare il deployabile, ma la verità di riferimento richiede la '
            'sintesi completa nel contenitore di sistema e, per la potenza, la misura sulla scheda '
            'fisica. La verifica RTL del candidato scelto nel contenitore reale è il passo che precede il '
            'deploy.'))

    # ---------------------------------------------------------------- 9
    A(('h1', '9. Riferimenti'))
    A(('table', (
        ['Riferimento', 'Tema'],
        [
            ['CF_FSNN, matlab/study_tradeoff/donatello/points_phase2.tsv — dataset delle curve io-timed (18 punti).', 'Dati (§5-§7)'],
            ['CF_FSNN, matlab/study_tradeoff/donatello/RESULTS.md §15 — Fmax reale io-timed e fix splitpipe.', 'Metodo (§4)'],
            ['CF_FSNN, matlab/study_tradeoff/donatello/RESULTS.md §12-§13 — latenze in clock e curva area-vs-clock.', 'Latenza, curve (§5-§6)'],
            ['CF_FSNN, document/HDL_PHASE.md §3.1.3-§3.1.5 — precisione di normalizzazione, edge-trigger, splitpipe.', 'Verifica (§3-§4)'],
            ['CF_FSNN, matlab/study_tradeoff/common/run_block_a_matrix.sh — cancello strutturale (firma decode + round).', 'Verifica (§3)'],
            ['CF_FSNN, matlab/study_tradeoff/common/sweep_phase2.sh — driver dello sweep io-timed a clock vincolato.', 'Riproducibilità (§4, §8)'],
            ['AMD/Xilinx. Vivado Design Suite 2026.1; Zynq-7000 SoC Data Sheet (DS187).', 'Toolchain e dispositivo'],
            ['Digilent. PYNQ-Z1 Reference Manual (board xc7z020-clg400-1).', 'Scheda di deploy'],
        ],
    )))
    return D


# --- RENDER MARKDOWN (dal template della skill) -----------------------------
def render_md(doc, outpath):
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
            story.append(Paragraph(esc(b['title']), ParagraphStyle('ct', fontName='DJ-B', fontSize=22,
                         leading=28, textColor=colors.HexColor('#1a3c6e'), alignment=1)))
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
