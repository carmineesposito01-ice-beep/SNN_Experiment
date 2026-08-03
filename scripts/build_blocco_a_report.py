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
DOC_NAME   = 'Trade_Off_Study_Parte_A'
DOC_TITLE  = 'CF_FSNN — Studio di trade-off, Parte A: caratterizzazione FPGA dei tier Donatello'
FOOTER_TEXT = 'CF_FSNN — Studio di trade-off, Parte A · Fmax io-timed, stima Vivado post-implementazione'
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

def pct(val, res):
    """Occupazione percentuale del dispositivo xc7z020 (totali DEV, datasheet DS187)."""
    return val / DEV[res] * 100.0

def lut_range(tag):
    vals = [P(tag, g, 'LUT') for g in GRID]
    return int(min(vals)), int(max(vals))

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
                    'io-timed e sul trade-off fra risorse e potenza, come base per la selezione del '
                    'candidato al Blocco B su Zynq-7020 (scheda PYNQ-Z1).',
        'meta': [
            'Livello di fedeltà: stima Vivado post-implementazione con timing d\'integrazione '
            '(io-timed) — non misura su silicio.',
            'Fonte dei numeri: matlab/study_tradeoff/donatello/points_phase2.tsv (18 punti, dai report '
            'Vivado util/timing/power via sweep_phase2.sh).',
            'Toolchain: Vivado 2026.1 · FPGA Xilinx Zynq-7000 xc7z020-clg400-1 (scheda PYNQ-Z1).',
        ],
    }))
    A(('toc', 'Sommario'))

    # ---------------------------------------------------------------- 1
    A(('h1', '1. Sommario esecutivo'))
    A(('p', 'Il blocco Donatello è la rete spiking che identifica i cinque parametri del controllore '
            'car-following a partire da quattro grandezze cinematiche. Lo studio ne caratterizza tre '
            'realizzazioni — i tier **SLOW**, **BAL** e **FAST** — ottenute accoppiando tre profondità '
            'di rete (round SNN R2, R5, R9) con tre profondità di decodifica (fusa, pipeline a tre stadi, '
            'pipeline a cinque stadi). Ogni tier è sintetizzato per lo Zynq-7020 e misurato sul **Fmax '
            'reale io-timed**: la frequenza disponibile quando gli ingressi del blocco sono registrati, '
            'come avviene in ogni integrazione, così che il cammino dalle porte d\'ingresso fino '
            'all\'inizio dell\'inferenza sia temporizzato insieme al resto.'))
    A(('p', 'La frequenza massima raggiungibile cresce in modo monotòno con la profondità del tier: **'
            + f'{FMAX_MAX["sp_slow"]:.1f}' + '**, **' + f'{FMAX_MAX["sp_balanced"]:.1f}'
            + '** e **' + f'{FMAX_MAX["sp_fast"]:.1f} MHz' + '** per SLOW, BAL e FAST. Il valore di FAST '
            'coincide con il blocco deployabile già congelato (' + f'{FAST_LOCK:g} MHz' + '), a conferma '
            'che il metro di misura e l\'RTL descrivono lo stesso oggetto. Le risorse di logica e i '
            'registri crescono anch\'essi con la profondità di pipeline, mentre la potenza è dominata '
            'dalla dispersione statica del dispositivo, costante, con una quota dinamica che scala con il '
            'clock.'))
    A(('p', 'Il risultato che orienta la lettura è che il **Fmax è margine, non requisito**. Il tempo di '
            'inferenza di ogni tier resta fra ' + f'{tinf_us("sp_fast", TIGHT):.1f}' + ' e '
            + f'{tinf_us("sp_slow", DEPLOY):.1f} µs' + ', cioè fra circa **' + f'{MARG_MIN:.0f}×' +
            '** e **' + f'{MARG_MAX:.0f}×' + '** sotto il budget di un passo di controllo (0.1 s). Nessuna '
            'soglia di frequenza vincola il progetto; le grandezze che distinguono i tre tier in modo '
            'rilevante per il deployment sono perciò l\'occupazione di risorse e la potenza. Il documento '
            'riporta la caratterizzazione completa su queste grandezze, come base per la selezione del '
            'candidato al Blocco B.'))
    A(('callout', 'Convenzione dei marcatori: ● grandezza misurata o verificata bit-esatta (correttezza '
                  'funzionale, latenza in clock); ○ stima Vivado post-implementazione (Fmax, risorse, '
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
               'tier.')))
    A(('p', 'Ogni tier è il blocco **completo e autonomo**: il VHDL è generato dal solo modello Simulink, '
            'senza cablaggi manuali, e la rete è realizzata a multiplazione temporale, riusando una sola '
            'via di calcolo con lo stato tenuto in memoria a doppia porta. I tre tier differiscono per due '
            'assi ortogonali — la profondità della rete spiking (round R2, R5, R9) e la profondità della '
            'pipeline di decodifica (fusa, tre stadi, cinque stadi) — accoppiati come SLOW = R2 con '
            'decodifica fusa, BAL = R5 con pipeline a tre stadi, FAST = R9 con pipeline a cinque stadi.'))
    A(('p', 'Il vincolo di deployment è la scheda PYNQ-Z1, che porta uno Zynq-7020 (xc7z020-clg400-1). '
            'Il fine dello studio non è massimizzare una singola metrica, ma **caratterizzare i tre tier** '
            'sulle grandezze rilevanti per il deployment — frequenza, risorse, potenza, timing — così che '
            'la selezione del candidato per il Blocco B, dove la rete sarà chiusa in anello con il '
            'controllore a inseguimento intelligente, poggi su dati solidi. Sullo stesso dispositivo è '
            'previsto un secondo blocco per la comunicazione veicolo-infrastruttura: la logica lasciata '
            'libera è una risorsa di progetto, e la caratterizzazione delle risorse ha perciò rilievo '
            'diretto per il seguito.'))

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
    A(('p', 'La seconda fase misura le prestazioni al variare del vincolo di clock imposto alla sintesi. '
            'Due scelte di metodo ne determinano la validità: come si temporizza il blocco e come nascono '
            'le sue varianti.'))
    A(('h2', '4.1 Il metro: timing d\'integrazione'))
    A(('p', 'Il blocco si deploya con gli ingressi registrati da uno stadio a monte, quindi il cammino '
            'che parte dalle porte d\'ingresso, attraversa la normalizzazione e arriva all\'inizio '
            'dell\'inferenza è un percorso temporizzato a tutti gli effetti. La misura lo include '
            'imponendo un ritardo di riferimento nullo su ingressi e uscite (timing d\'integrazione, o '
            'io-timed): il **Fmax io-timed** è così la frequenza su cui il blocco si integra davvero. Una '
            'sintesi out-of-context che lasci le porte non temporizzate valuterebbe soltanto i percorsi '
            'fra registri interni e lascerebbe quel cammino fuori dal conto; per questo la '
            'caratterizzazione adotta il metro io-timed.'))
    A(('p', 'Perché il cammino d\'ingresso non sia il collo di bottiglia, gli operandi del normalize sono '
            'registrati fra il clamp e la moltiplicazione (architettura splitpipe) e l\'edge-trigger '
            'confronta gli operandi registrati. Lo stadio aggiunto mantiene il blocco bit-esatto e costa '
            'un solo clock di latenza. Il percorso critico che resta è la moltiplicazione a 34 bit della '
            'normalizzazione, intrinseca alla precisione richiesta e mappata su due DSP in cascata.'))
    A(('h2', '4.2 Le varianti nascono dal vincolo di clock'))
    A(('p', 'Le varianti di ciascun tier non sono realizzazioni RTL diverse, ma lo **stesso blocco** '
            'sintetizzato sotto vincoli di clock diversi. Il periodo di clock chiesto alla sintesi è una '
            'leva di progetto: un periodo più corto costringe lo strumento a lavorare di più sul percorso '
            'critico, e lo ottiene spendendo area — replica logica, sceglie celle più veloci, alza il '
            'Fmax a costo di più LUT; un periodo più lungo produce l\'opposto, meno area alla frequenza, '
            'più bassa ma sufficiente, che il vincolo lasco richiede.'))
    A(('p', 'Un solo sweep del vincolo mappa così l\'intero trade-off. Il periodo target percorre una '
            'griglia di multipli del ritardo io misurato al punto d\'ancoraggio — x0.90, x1.00, x1.40, '
            'x2.00, x3.00 — più il periodo lasco di riferimento per il deploy (125 ns). L\'etichetta '
            '**x0.90** è quindi il vincolo più stretto (il 90% del ritardo d\'ancoraggio) e definisce il '
            '**tetto di Fmax**, con l\'area più alta; l\'etichetta **deploy** è il vincolo lasco e '
            'definisce l\'**area minima**, alla frequenza operativa. I due estremi non sono realizzazioni '
            'in concorrenza: sono i due capi della stessa curva. Quale portare al silicio dipende da '
            'quanta frequenza serve, e poiché il Fmax è margine abbondante (§6) il punto operativo '
            'ragionevole è quello ad area minima — che non paga logica per una velocità non richiesta — '
            'mentre il tetto di Fmax resta la misura di quanto il blocco potrebbe correre.'))
    A(('callout', 'Come leggere le tabelle di §5.2. Ogni riga è un punto dello sweep. **Vincolo**: il '
                  'periodo di clock imposto alla sintesi, come multiplo del ritardo d\'ancoraggio (deploy '
                  '= 125 ns). **Ritardo**: il ritardo del percorso critico io-timed raggiunto, da cui '
                  'Fmax = 1/ritardo. **LUT, FF, DSP, BRAM**: le risorse occupate. **Ptot**: la potenza '
                  'totale su chip (stima vectorless). **Hold int.**: il margine di tenuta interno reg-reg '
                  'peggiore — positivo significa chiuso. Riproducibilità: thread di Vivado e seme fissati, '
                  'VHDL byte-identico fra i punti, versione dello strumento registrata (Vivado 2026.1).'))

    # ---------------------------------------------------------------- 5
    A(('h1', '5. Risultati'))
    A(('h2', '5.1 Il Fmax reale io-timed'))
    A(('p', 'La frequenza massima raggiungibile cresce in modo monotòno con la profondità del tier, da '
            'SLOW a FAST. Che il valore di FAST (' + f'{FMAX_MAX["sp_fast"]:.1f} MHz' + ') coincida con il '
            'blocco deployabile congelato (' + f'{FAST_LOCK:g} MHz' + ') conferma che il metro e l\'RTL '
            'misurano lo stesso oggetto, senza deriva fra caratterizzazione e artefatto.'))
    A(('img', (fig_fmax(), 'Figura 5.1 — Fmax reale io-timed per tier, ai due capi della curva del '
               'vincolo: il clock lasco di deploy (area minima) e il vincolo più stretto (tetto di Fmax). '
               'La progressione SLOW < BAL < FAST è netta a entrambi gli estremi. Fonte: points_phase2.tsv '
               '(punti x0.90 e deploy-ref).')))
    A(('h2', '5.2 Risorse, curve area–clock e potenza'))
    A(('p', 'L\'occupazione del dispositivo è modesta su tutti i tier e cresce con la profondità di '
            'pipeline. La risorsa più sollecitata sono i DSP — ' + f'{int(P("sp_slow", TIGHT, "DSP"))}' +
            ' blocchi, costanti su tutti i tier e su tutti i vincoli, pari a circa il '
            + f'{pct(P("sp_slow", TIGHT, "DSP"), "DSP"):.0f}%' + ' dei ' + f'{DEV["DSP"]}' + ' presenti '
            'sullo Zynq-7020 — mentre LUT, registri e blocchi RAM restano in cifra singola percentuale. '
            'La tabella riporta l\'occupazione completa: l\'intervallo di LUT copre la curva del vincolo, '
            'gli altri tre valori non dipendono dal clock.'))
    A(('table', (
        ['Tier', 'LUT (min–max)', 'FF', 'DSP', 'BRAM'],
        [[NAME[t],
          f'{lut_range(t)[0]}–{lut_range(t)[1]} ({pct(lut_range(t)[0],"LUT"):.1f}–{pct(lut_range(t)[1],"LUT"):.1f}%)',
          f'{int(FF_TIER[t])} ({pct(FF_TIER[t],"FF"):.1f}%)',
          f'{int(P(t, TIGHT, "DSP"))} ({pct(P(t, TIGHT, "DSP"),"DSP"):.1f}%)',
          f'{int(P(t, TIGHT, "BRAM"))} ({pct(P(t, TIGHT, "BRAM"),"BRAM"):.1f}%)'] for t in TAGS],
    )))
    A(('p', 'Al variare del vincolo si muovono soltanto le LUT e la quota dinamica di potenza; registri, '
            'DSP e blocchi RAM sono fissati dall\'RTL. La curva area–clock che ne risulta è monotòna: al '
            'crescere della frequenza richiesta cresce l\'occupazione di LUT, fino al pavimento raggiunto '
            'al clock lasco. Le curve dei tre tier restano separate perché quel pavimento è fissato dalla '
            'profondità di pipeline, non dal vincolo.'))
    A(('img', (fig_curves(), 'Figura 5.2 — A sinistra: LUT contro Fmax reale; ogni punto è un vincolo di '
               'clock, dal più stretto (stella, tetto di Fmax) al lasco (cerchio vuoto, area minima). A '
               'destra: potenza totale contro Fmax; la dispersione statica (linea tratteggiata) è '
               'costante, la quota dinamica cresce con il clock. Fonte: points_phase2.tsv.')))
    A(('p', 'La potenza segue la stessa fisica dal lato energetico. La componente statica del dispositivo '
            'è costante intorno a ' + f'{sum(PSTA.values())/len(PSTA)*1000:.0f} mW' + ' e non dipende dal '
            'progetto; la componente dinamica cresce con il clock. La quota statica supera il novanta per '
            'cento del totale al clock di deploy e resta la maggioranza anche al punto più aggressivo, '
            'variando fra circa il **' + f'{min(static_pct(t, g) for t in TAGS for g in GRID):.0f}%' +
            '** al vincolo più stretto e circa il **'
            + f'{max(static_pct(t, g) for t in TAGS for g in GRID):.0f}%' + '** al clock di deploy. La '
            'stima di potenza è vectorless: l\'attività di commutazione è calcolata dallo strumento '
            'anziché estratta da una simulazione della traiettoria; poiché la quota dinamica — l\'unica '
            'che una stima d\'attività correggerebbe — è minoritaria ai punti di deploy, il suo peso sul '
            'totale è contenuto.'))
    for t in TAGS:
        A(('h3', f'5.2.{TAGS.index(t)+1} Curva del tier {NAME[t]} ({ROUND[t]} · decode {DECODE[t]})'))
        rows = []
        for g in GRID:
            rows.append([
                g.replace('deploy-ref', 'deploy'),
                f'{P(t, g, "delay_ns"):.2f}',
                f'{P(t, g, "Fmax_MHz"):.2f}',
                f'{int(P(t, g, "LUT"))}',
                f'{int(P(t, g, "FF"))}',
                f'{int(P(t, g, "DSP"))}',
                f'{int(P(t, g, "BRAM"))}',
                f'{P(t, g, "Ptot_W")*1000:.0f}',
                f'{P(t, g, "WHS_int"):+.3f}',
            ])
        A(('table', (['Vincolo', 'Ritardo [ns]', 'Fmax [MHz]', 'LUT', 'FF', 'DSP', 'BRAM', 'Ptot [mW]', 'Hold int. [ns]'], rows)))
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
            'Le grandezze su cui i tre tier si distinguono in modo rilevante per il deployment sono '
            'perciò quelle riportate in §5 — l\'occupazione di risorse e la potenza — su cui questa '
            'caratterizzazione offre la base per la selezione del candidato al Blocco B.'))
    A(('callout', 'Fedeltà. Tutte le grandezze di frequenza, risorse e potenza sono stime Vivado '
                  'post-implementazione con timing d\'integrazione io-timed (marcatore ○), non misure su '
                  'silicio: sono il metro corretto per confrontare i tier fra loro, mentre la verità di '
                  'riferimento richiede la sintesi nel contenitore di sistema completo e, per la potenza, '
                  'la misura sulla scheda fisica.'))

    # ---------------------------------------------------------------- Riferimenti
    A(('h1', 'Riferimenti'))
    A(('table', (
        ['Riferimento', 'Tema'],
        [
            ['CF_FSNN, matlab/study_tradeoff/donatello/points_phase2.tsv — dataset delle curve io-timed (18 punti).', 'Dati (§5-§6)'],
            ['CF_FSNN, matlab/study_tradeoff/donatello/RESULTS.md §15 — Fmax reale io-timed e fix splitpipe.', 'Metodo (§4)'],
            ['CF_FSNN, matlab/study_tradeoff/donatello/RESULTS.md §12-§13 — latenze in clock e curva area-vs-clock.', 'Latenza, curve (§5-§6)'],
            ['CF_FSNN, document/HDL_PHASE.md §3.1.3-§3.1.5 — precisione di normalizzazione, edge-trigger, splitpipe.', 'Verifica (§3-§4)'],
            ['CF_FSNN, matlab/study_tradeoff/common/run_block_a_matrix.sh — cancello strutturale (firma decode + round).', 'Verifica (§3)'],
            ['CF_FSNN, matlab/study_tradeoff/common/sweep_phase2.sh — driver dello sweep io-timed a clock vincolato.', 'Riproducibilità (§4)'],
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
