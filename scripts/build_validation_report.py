"""Genera il REPORT DI VALIDAZIONE CF_FSNN (.md + .pdf) da un'unica sorgente di contenuto.

Obiettivo: un documento tecnico, chiaro ed esaustivo, leggibile da un ingegnere che non
conosce il progetto, che dia piena coscienza di (a) la rete S3 consolidata e (b) la sua
validazione closed-loop (micro + meso). Il livello MACRO e' ESCLUSO per incertezza del
simulatore ad anello (vedi nota nel report).

Stile: emula document/HOW_IT_WORKS.{md,pdf} (reportlab). Tutte le figure quantitative sono
RICOSTRUITE in locale dai CSV/JSON dei risultati (caption corrette), cosi' il report e'
riproducibile senza checkpoint. La sola figura qualitativa (raster spike) viene riusata dal
PNG esistente con caption corretta nel report.

Uso:  python scripts/build_validation_report.py
Output: document/VALIDATION_REPORT.md, document/VALIDATION_REPORT.pdf, document/figures_validation/*
"""
import os
import shutil
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCDIR = os.path.join(ROOT, 'document')
FIGDIR = os.path.join(DOCDIR, 'figures_validation')
EVAL = os.path.join(ROOT, 'results', 'evaluate', 'v1_realistic_cutin')
S3LOG = os.path.join(ROOT, 'results', 'Loss_Study', 'S3', 'PEAK',
                     'LS3_PEAK_R0_launch_d03', 'training_log.csv')
os.makedirs(FIGDIR, exist_ok=True)

CH = ['v0', 'T', 's0', 'a', 'b']
TRUE = {'v0': 33.3, 'T': 1.2, 's0': 2.5, 'a': 1.1, 'b': 1.5}
UNIT = {'v0': 'm/s', 'T': 's', 's0': 'm', 'a': 'm/s2', 'b': 'm/s2'}

# ---------------------------------------------------------------------------
# 0. Carica i dati una volta (numeri veri -> testo riproducibile)
# ---------------------------------------------------------------------------
e = pd.read_csv(S3LOG)
BEST = int(e['val_data'].idxmin())
BEST_EPOCH = int(e['epoch'].iloc[BEST])
nrmse = {c: float(e[f'val_{c}_nrmse'].iloc[BEST]) for c in CH}
pred = {c: float(e[f'val_{c}_pred_mean'].iloc[BEST]) for c in CH}
MEAN_NRMSE = float(np.mean(list(nrmse.values())))
MEAN_ACC = (1 - MEAN_NRMSE) * 100

safety = pd.read_csv(os.path.join(EVAL, 'Eval_ClosedLoop', 'safety_summary.csv'))
quality = pd.read_csv(os.path.join(EVAL, 'Eval_ClosedLoop', 'quality_summary.csv'))
collbys = pd.read_csv(os.path.join(EVAL, 'Eval_ClosedLoop', 'collision_by_scenario.csv'))
meso = pd.read_csv(os.path.join(EVAL, 'Meso', 'meso_summary.csv'))
energy = json.load(open(os.path.join(EVAL, 'Showcase', 'showcase_energy.json')))

# ordine sorgenti coerente: SNN primario prima, oracolo per ultimo
SRC_ORDER = ['S3 d0.3 (launch)', 'S3 d1.0 (launch)', 'R33_C2 CLEAN', 'oracle']


def _order(df, col='source'):
    df = df.copy()
    df['_o'] = df[col].apply(lambda s: SRC_ORDER.index(s) if s in SRC_ORDER else 99)
    return df.sort_values('_o').drop(columns='_o').reset_index(drop=True)


# ---------------------------------------------------------------------------
# 1. Figure ricostruite (caption corrette)
# ---------------------------------------------------------------------------
def fig_accuracy():
    acc = [max(0.0, 1 - nrmse[c]) * 100 for c in CH]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.6))
    cols = ['tab:green' if x > 75 else 'tab:orange' if x > 65 else 'tab:red' for x in acc]
    bars = a1.bar(CH, acc, color=cols)
    a1.set_ylim(0, 100); a1.axhline(75, color='gray', ls=':')
    a1.set_ylabel('accuratezza ~ (1 - NRMSE)  [%]')
    a1.set_title(f'Accuratezza di identificazione per parametro (media {MEAN_ACC:.0f}%)')
    for b, c in zip(bars, CH):
        a1.text(b.get_x() + b.get_width() / 2, b.get_height() + 1,
                f'NRMSE\n{nrmse[c]:.2f}', ha='center', fontsize=8)
    a1.grid(alpha=0.3, axis='y')
    x = np.arange(len(CH)); w = 0.36
    a2.bar(x - w / 2, [pred[c] for c in CH], w, label='predetto', color='tab:blue')
    a2.bar(x + w / 2, [TRUE[c] for c in CH], w, label='vero', color='tab:gray')
    a2.set_xticks(x); a2.set_xticklabels(CH); a2.set_yscale('log')
    a2.set_ylabel('valore (scala log)')
    a2.set_title('Predetto vs vero: a sottostimato, b sovrastimato (bias di frenata)')
    a2.legend(); a2.grid(alpha=0.3, axis='y')
    plt.tight_layout()
    p = os.path.join(FIGDIR, 'val_accuracy.png')
    plt.savefig(p, dpi=130); plt.close(fig)
    return p


def fig_nrmse_traj():
    ep = e['epoch'].values
    fig, ax = plt.subplots(figsize=(11, 4.6))
    palette = {'v0': 'tab:blue', 'T': 'tab:orange', 's0': 'tab:green',
               'a': 'tab:red', 'b': 'tab:purple'}
    for c in CH:
        ax.plot(ep, e[f'val_{c}_nrmse'].values, marker='.', ms=3,
                color=palette[c], label=c, alpha=0.9)
    ax.axvline(BEST_EPOCH, color='k', ls='--', alpha=0.6,
               label=f'best (ep {BEST_EPOCH})')
    ax.set_xlabel('epoca'); ax.set_ylabel('NRMSE per canale (val)')
    ax.set_title('Apprendimento per-canale (run S3, osservabilita gia attiva dal dato): '
                 'v0/s0 bassi e stabili, a/b derivano verso l\'alto')
    ax.legend(fontsize=8, ncol=6, loc='upper center'); ax.grid(alpha=0.3)
    ax.set_ylim(0, max(0.6, float(e[[f'val_{c}_nrmse' for c in CH]].values.max()) * 1.05))
    plt.tight_layout()
    p = os.path.join(FIGDIR, 'val_nrmse_trajectory.png')
    plt.savefig(p, dpi=130); plt.close(fig)
    return p


def fig_safety_scorecard():
    s = _order(safety); q = _order(quality)
    panels = [
        ('collision_rate', s, 'tasso collisioni (0 = sicuro)'),
        ('worst_min_gap', s, 'gap minimo peggiore [m]'),
        ('worst_min_ttc', s, 'TTC minimo peggiore [s]'),
        ('max_DRAC', s, 'DRAC massimo [m/s2]'),
        ('mean_TET', s, 'TET medio (tempo esposto)'),
        ('rms_accel', q, 'RMS accel [m/s2] (comfort)'),
        ('rms_jerk', q, 'RMS jerk [m/s3] (comfort)'),
        ('rms_gap_error', q, 'errore RMS gap [m] (tracking)'),
    ]
    fig, axes = plt.subplots(2, 4, figsize=(17, 8))
    for ax, (col, df, title) in zip(axes.ravel(), panels):
        colors = ['tab:green' if src != 'oracle' else 'tab:gray' for src in df['source']]
        ax.bar(range(len(df)), df[col].values, color=colors, alpha=0.85)
        ax.set_xticks(range(len(df)))
        ax.set_xticklabels(df['source'], rotation=25, ha='right', fontsize=7)
        ax.set_title(title, fontsize=9); ax.grid(alpha=0.3, axis='y')
    fig.suptitle('MICRO - sicurezza e comfort closed-loop (100 scenari x 5 tipi). '
                 'Verde = checkpoint SNN, grigio = oracolo (ground truth)', fontsize=11)
    fig.tight_layout()
    p = os.path.join(FIGDIR, 'val_micro_scorecard.png')
    plt.savefig(p, dpi=120); plt.close(fig)
    return p


def fig_meso_scorecard():
    m = _order(meso)
    panels = [
        ('head_to_tail_gain', 'gain testa->coda (<1 = stabile)'),
        ('max_amplification', 'amplificazione massima'),
        ('min_gap_platoon', 'gap minimo nel plotone [m]'),
        ('min_ttc_platoon', 'TTC minimo nel plotone [s]'),
        ('rms_accel_mean', 'RMS accel medio [m/s2]'),
        ('rms_jerk_mean', 'RMS jerk medio [m/s3]'),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(15, 7.5))
    for ax, (col, title) in zip(axes.ravel(), panels):
        colors = ['tab:green' if src != 'oracle' else 'tab:gray' for src in m['source']]
        ax.bar(range(len(m)), m[col].values, color=colors, alpha=0.85)
        ax.set_xticks(range(len(m)))
        ax.set_xticklabels(m['source'], rotation=25, ha='right', fontsize=7)
        ax.set_title(title, fontsize=9); ax.grid(alpha=0.3, axis='y')
        if col == 'head_to_tail_gain':
            ax.axhline(1.0, color='r', ls='--', alpha=0.7)
    fig.suptitle('MESO - plotone di 12 veicoli, string stability (perturbazione sinusoidale in testa)',
                 fontsize=11)
    fig.tight_layout()
    p = os.path.join(FIGDIR, 'val_meso_scorecard.png')
    plt.savefig(p, dpi=120); plt.close(fig)
    return p


def fig_energy():
    en = energy
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.6))
    a1.bar(['ANN-equiv\n(dense MAC)', 'SNN\n(event-driven)'],
           [en['E_ann_nJ'], en['E_snn_nJ']], color=['tab:gray', 'tab:green'])
    a1.set_ylabel('energia / inferenza [nJ]')
    a1.set_title(f"Energia: SNN {en['E_snn_nJ']:.0f} nJ vs ANN {en['E_ann_nJ']:.0f} nJ "
                 f"= {en['energy_advantage_x']:.1f}x")
    for i, v in enumerate([en['E_ann_nJ'], en['E_snn_nJ']]):
        a1.text(i, v, f'{v:.0f}', ha='center', va='bottom')
    a1.grid(alpha=0.3, axis='y')
    a2.bar(['SynOps\nSNN', 'MAC\nANN'], [en['snn_synops'], en['ann_macs']],
           color=['tab:purple', 'tab:gray'])
    a2.set_ylabel('operazioni / inferenza')
    a2.set_title('SynOps SNN >= MAC ANN: il vantaggio viene dal costo AC<MAC,\nNON dalla sparsita '
                 f"(spike rate {en['mean_spike_rate_pct']:.0f}%)")
    for i, v in enumerate([en['snn_synops'], en['ann_macs']]):
        a2.text(i, v, f'{v:,}', ha='center', va='bottom', fontsize=8)
    a2.grid(alpha=0.3, axis='y')
    plt.tight_layout()
    p = os.path.join(FIGDIR, 'val_energy.png')
    plt.savefig(p, dpi=130); plt.close(fig)
    return p


def copy_reused():
    reuse = {
        'val_micro_trajectories.png': (EVAL, 'Eval_ClosedLoop', 'eval_G1_trajectories.png'),
        'val_micro_ttc.png': (EVAL, 'Eval_ClosedLoop', 'eval_G2_ttc.png'),
        'val_micro_string.png': (EVAL, 'Eval_ClosedLoop', 'eval_G4_string_stability.png'),
        'val_meso_string.png': (EVAL, 'Meso', 'meso_string_stability.png'),
        'val_raster.png': (EVAL, 'Showcase', 'showcase_raster.png'),
    }
    out = {}
    for dst, (a, b, c) in reuse.items():
        src = os.path.join(a, b, c)
        dstp = os.path.join(FIGDIR, dst)
        shutil.copy2(src, dstp)
        out[dst] = dstp
    return out


print('[1/4] genero figure...')
F_ACC = fig_accuracy()
F_NRMSE = fig_nrmse_traj()
F_MICRO = fig_safety_scorecard()
F_MESO = fig_meso_scorecard()
F_ENERGY = fig_energy()
R = copy_reused()
print('  figure in', FIGDIR)


# ---------------------------------------------------------------------------
# 2. Contenuto del documento (UNICA sorgente -> md + pdf)
#    blocchi: ('h1'|'h2'|'h3', txt) ('p', txt) ('code', txt) ('hr',)
#             ('callout', txt) ('table', (headers, rows)) ('img', (path, caption))
# ---------------------------------------------------------------------------
def _row(df, src, cols, fmt):
    r = df[df['source'] == src].iloc[0]
    return [src] + [fmt(r[c]) for c in cols]


def build_doc():
    f2 = lambda v: f'{float(v):.2f}'
    f3 = lambda v: f'{float(v):.3f}'

    D = []
    A = D.append

    # ---- COVER ----
    A(('cover', {
        'title': 'CF_FSNN - Report di Validazione',
        'subtitle': 'Identificatore SNN di parametri car-following (ACC-IIDM) -- '
                    'rete S3 consolidata e validazione closed-loop micro/meso',
        'meta': [
            'Versione: 2026-06-20  (branch Loss_Study)',
            'Checkpoint validato: LS3_PEAK_R0_launch_d03  (864 parametri)',
            'Analisi sorgente: results/evaluate/v1_realistic_cutin',
            'Lettore atteso: ingegnere che non conosce il progetto e vuole piena',
            'coscienza dello stato in ~30 minuti (rete + validazione).',
        ],
    }))

    # ---- 1. SOMMARIO ESECUTIVO ----
    A(('h1', '1. Sommario esecutivo'))
    A(('p', 'CF_FSNN è una rete neurale spiking (SNN, 864 parametri, target FPGA '
           'PYNQ-Z1) che osserva un veicolo follower via V2X (gap, velocità, '
           'Δv, velocità leader) e ne identifica i 5 parametri del modello di '
           'car-following ACC-IIDM: [v0, T, s0, a, b] (Treiber & Kesting, Ch.12). Questo '
           'documento valida la rete consolidata "S3" in un contesto di guida chiuso '
           '(la rete guida davvero un’auto), su scenari avversari.'))
    A(('p', 'Verdetto: la rete è VALIDATA per la sicurezza. Su 100 scenari per '
           'ciascuna delle 5 tipologie (following, stop&go, hard-brake, cut-in realistico, '
           'sinusoidale) e per tutti e 3 i checkpoint testati, il tasso di collisione è '
           'ZERO, identico all’oracolo (il modello ground-truth). A livello di plotone '
           '(12 veicoli) la catena è string-stable (le perturbazioni si smorzano). '
           'Esiste un solo limite residuo, netto e già diagnosticato: un bias '
           'sistematico sui parametri di frenata (a sottostimato, b sovrastimato) che '
           'rende la rete più conservativa del dovuto -- benevolo per la sicurezza, '
           'ma da correggere per realismo/prestazioni.'))
    A(('table', (
        ['Asse', 'Risultato', 'Lettura'],
        [
            ['Sicurezza (micro)', '0 collisioni / 500 scenari (per checkpoint)', 'come l’oracolo'],
            ['Margini (micro)', f'gap min peggiore {f2(safety[safety.source!="oracle"].worst_min_gap.min())} m, '
                                f'TTC min {f2(safety[safety.source!="oracle"].worst_min_ttc.min())} s', 'più cauta dell’oracolo'],
            ['String stability (meso)', f'gain testa->coda {f2(meso[meso.source!="oracle"].head_to_tail_gain.min())}-'
                                        f'{f2(meso[meso.source!="oracle"].head_to_tail_gain.max())} (<1)', 'plotone stabile'],
            ['Identificazione', f'NRMSE media {MEAN_NRMSE:.2f} (~{MEAN_ACC:.0f}% accuratezza)', 's0/v0/T buoni'],
            ['Limite residuo', f'a: {pred["a"]:.2f} vs 1.10 (-40%);  b: {pred["b"]:.2f} vs 1.50 (+30%)', 'bias di frenata -> S4'],
            ['Energia', f"{energy['energy_advantage_x']:.1f}x vs ANN equivalente", 'da costo AC<MAC, non da sparsità'],
        ],
    )))
    A(('callout', 'Scope. Questo report copre i livelli MICRO (1 veicolo, scenari avversari) '
                  'e MESO (plotone, string stability). Il livello MACRO (diagramma fondamentale '
                  'su anello chiuso) è ESCLUSO: la curva dell’oracolo prodotta dal '
                  'simulatore ad anello è anomala (capacità e velocità di '
                  'free-flow implausibilmente basse), segno di un artefatto del simulatore macro '
                  'più che di una proprietà della rete. Finché non è '
                  'chiarito, i numeri macro non sono affidabili e non vengono riportati.'))

    # ---- 2. LA RETE VALIDATA (S3) ----
    A(('h1', '2. La rete sotto test: il checkpoint S3 consolidato'))
    A(('h2', '2.1 CF_FSNN in una pagina'))
    A(('p', 'Architettura: input(4) -> Hidden ALIF (32 neuroni spiking, ricorrenza low-rank '
           'rank-8, ritardi assonali) -> Output LI (5) -> sigmoid + bounds fisici -> '
           '[v0, T, s0, a, b]. Ogni passo temporale reale (0.1 s) viene elaborato con 10 '
           'tick SNN interni; l’addestramento è BPTT con surrogate gradient. I pesi '
           'sono quantizzati a potenze-di-due (moltiplicazione -> bit-shift su FPGA) e il leak '
           'di membrana è un bit-shift. La loss è PINN (physics-informed): un '
           'termine dati (l’accelerazione ricostruita dai parametri predetti deve '
           'matchare quella ground-truth ACC-IIDM) più termini di coerenza fisica. '
           'Per i dettagli completi di architettura, neurone ALIF, quantizzazione e loss '
           'vedi document/HOW_IT_WORKS.md (questo report non li ripete).'))
    A(('callout', 'Punto chiave per leggere il resto: la rete non predice una traiettoria, '
                  'ma i 5 NUMERI che caratterizzano lo stile di guida. La validazione verifica '
                  'che, usando quei numeri per GUIDARE un’auto in anello chiuso, il '
                  'comportamento sia sicuro e realistico.'))

    A(('h2', '2.2 Perché "S3": da non-identificabilità a osservabilità'))
    A(('p', 'Il problema centrale scoperto prima della validazione: dai soli segnali di '
           'car-following i 5 parametri NON sono congiuntamente identificabili. In '
           'particolare v0 e a formano una coppia "molle" (sloppy manifold): si compensano a '
           'vicenda (correlazione misurata -0.82 lungo il training; forzando v0 in basso, a '
           'sale, e viceversa). La causa-radice è fisica/osservativa, non un difetto di '
           'capacità della rete:'))
    A(('table', (
        ['Parametro', 'Dove diventa osservabile', 'Conseguenza pratica'],
        [
            ['v0', 'in crociera libera (free-flow), quando v -> v0', 'serve uno scenario "freeflow"'],
            ['a', 'solo nei transitori di accelerazione forte', 'serve uno scenario "launch"'],
            ['T, s0', 'nel regime di inseguimento normale', 'già ben coperti'],
            ['b', 'nelle frenate', 'osservabile ma accoppiato (vedi 2.3)'],
        ],
    )))
    A(('p', 'S3 è il punto di arrivo di tre interventi, tutti sul DATO (decoder a 5 '
           'parametri mai toccato): (1) aggiunta dello scenario freeflow -> rende v0 '
           'osservabile; (2) aggiunta dello scenario launch (cicli di accelerazione forte) -> '
           'eccita a; (3) scheduler con restart a learning-rate decrescente (Opzione 1+4) -> '
           'elimina i "bump" di loss ai restart e migliora l’identificabilità '
           'congiunta. Il risultato è il checkpoint LS3_PEAK_R0_launch_d03, che porta '
           'v0 da NRMSE ~0.50 a ~0.22 senza degradare gli altri canali.'))

    A(('h2', '2.3 Stato di identificazione per-parametro (al checkpoint validato)'))
    A(('p', f'Al miglior epoca (epoca {BEST_EPOCH}, minimo di val_data), l’identificazione '
           f'per canale è la seguente. La NRMSE media è {MEAN_NRMSE:.3f} '
           f'(~{MEAN_ACC:.0f}% di accuratezza). Importante: la NRMSE da sola nasconde la '
           'natura dell’errore -- per a e b l’errore non è rumore ma un BIAS '
           'sistematico orientato.'))
    A(('table', (
        ['Parametro', 'NRMSE', 'Predetto (media)', 'Vero', 'Bias', 'Giudizio'],
        [[c, f'{nrmse[c]:.3f}', f'{pred[c]:.3f} {UNIT[c]}', f'{TRUE[c]} {UNIT[c]}',
          f'{pred[c]-TRUE[c]:+.2f}',
          ('ottimo' if nrmse[c] < 0.18 else 'buono' if nrmse[c] < 0.26 else 'bias sistematico')]
         for c in CH],
    )))
    A(('img', (F_ACC, 'Figura 2.1 - Accuratezza per parametro (sx) e confronto predetto-vs-vero '
                      '(dx, scala log). s0/v0/T sono centrati; a è sottostimato (~0.66 vs '
                      '1.10) e b sovrastimato (~1.95 vs 1.50). I due errori si compensano in '
                      'gran parte nella combinazione sqrt(a*b) -- l unica osservabile -- '
                      'che resta vicina al vero (~-12%); l effetto netto di guida e '
                      'dominato dal moltiplicatore a piu debole.')))
    A(('p', 'Perche il closed-loop resta sicuro nonostante errori grandi su a e b: nel '
           'modello IIDM a e b entrano nel gap desiderato SOLO come prodotto sqrt(a*b) -- '
           'l unica direzione osservabile. La rete impara bene sqrt(a*b) (1.13 vs 1.28 vero, '
           '-12%) e scarica l errore lungo il rapporto a/b, che nei dati di following non e '
           'osservabile; cosi la dinamica del gap resta quasi preservata. ATTENZIONE al verso: '
           'sovrastimare b da solo RIDUCE il gap desiderato (margini piu stretti), non li '
           'allarga; ma l effetto e dominato dal moltiplicatore a piu debole (accelerazioni '
           'piu dolci, gap leggermente piu ampi), per cui l aggregato e piu conservativo -- '
           'coerente con i margini osservati nel micro. Causa strutturale del tetto: a entra '
           'come termine saturante (cap min(.,a), gradiente nullo fuori dalla saturazione) e '
           'a/b sono scambiabili in sqrt(a*b) -- finestra di osservabilita stretta per '
           'costruzione del modello (oggetto dello studio sui parametri dinamici).'))

    A(('h2', '2.4 Traiettoria di apprendimento per-canale'))
    A(('img', (F_NRMSE, 'Figura 2.2 - NRMSE per canale lungo le 50 epoche di QUESTA run S3 '
                        '(che include gia freeflow+launch). v0 (blu) parte gia basso (~0.20) e '
                        'resta basso: il confronto col valore pre-fix (~0.50) e cross-run, non '
                        'visibile qui. s0 (verde) e il migliore. a (rosso) e b (viola) DERIVANO '
                        'verso l alto durante il training -- il manifold molle ricollassa a/b -- '
                        f'percio il checkpoint e scelto all epoca {BEST_EPOCH} (tratteggio) sul '
                        'minimo di val_data, prima che peggiorino oltre. E la firma del tetto '
                        'strutturale di a/b.')))

    A(('h2', '2.5 I checkpoint messi sotto test'))
    A(('p', 'La validazione confronta 3 checkpoint SNN più l’oracolo. Tutti hanno la '
           'stessa architettura (864 parametri); differiscono per ricetta di training. '
           'L’oracolo NON è una rete: è il modello ACC-IIDM con i parametri '
           'veri (ground truth), e serve da limite superiore di riferimento.'))
    A(('table', (
        ['Sorgente', 'Cos’è', 'Ruolo nel report'],
        [
            ['S3 d0.3 (launch)', 'checkpoint consolidato (restart decay 1.0->0.3)', 'PRIMARIO (vetrina, raster, energia)'],
            ['S3 d1.0 (launch)', 'variante con restart non decrescente', 'confronto'],
            ['R33_C2 CLEAN', 'champion pre-osservabilità (stabile)', 'confronto/baseline'],
            ['oracle', 'ACC-IIDM coi parametri veri (non è una rete)', 'limite superiore di riferimento'],
        ],
    )))

    # ---- 3. METODOLOGIA ----
    A(('h1', '3. Metodologia di validazione'))
    A(('h2', '3.1 I due livelli riportati'))
    A(('p', 'MICRO (1 veicolo): la rete guida un ego che insegue un leader avversario; si '
           'misurano sicurezza e comfort. MESO (plotone di 12 veicoli): perturbazione in '
           'testa, si misura se l’onda si amplifica o si smorza lungo la catena (string '
           'stability). Il livello MACRO è escluso (vedi callout in 1).'))
    A(('h2', '3.2 Il simulatore closed-loop'))
    A(('p', 'A ogni passo (Dt=0.1 s) la rete riceve lo stato osservato dell’ego, predice '
           '[v0, T, s0, a, b], e questi parametri vengono dati in pasto al controllore '
           'ACC-IIDM che calcola l’accelerazione dell’ego; l’ego avanza, lo '
           'stato si aggiorna, e il ciclo si ripete (guida a anello chiuso, non '
           'identificazione offline). L’oracolo gira lo stesso loop ma con i parametri '
           'veri. Confrontare i due isola l’effetto dell’errore di identificazione '
           'sul comportamento di guida.'))
    A(('h2', '3.3 Scenari e la correzione del cut-in (v0 -> v1)'))
    A(('p', '5 tipologie di scenario, 100 istanze randomizzate ciascuna (driver e condizioni '
           'iniziali variati): following (inseguimento nominale), stop_and_go (leader '
           'oscillante), hard_brake (frenata di emergenza del leader), cut_in (taglio di '
           'corsia), sinusoidal (velocità leader sinusoidale). Il cut-in è lo '
           'scenario critico: nella prima versione (v0) il taglio era così severo '
           '(gap 4 m, DRAC ~8) da essere fisicamente inevitabile -- anche l’oracolo '
           'collideva. È stato corretto a una geometria realistica e EVITABILE '
           '(TTC ~1 s, DRAC ~4): così lo scenario misura la rete, non un artefatto. '
           'Tutti i risultati di questo report sono sulla versione v1 (cut-in realistico).'))
    A(('h2', '3.4 Metriche definite'))
    A(('table', (
        ['Metrica', 'Definizione', 'Cosa cattura'],
        [
            ['collision_rate', 'frazione di scenari con gap -> 0', 'sicurezza assoluta'],
            ['min_gap / TTC', 'distanza e time-to-collision minimi', 'prossimità al pericolo'],
            ['DRAC', 'decelerazione richiesta per evitare collisione', 'severità della manovra'],
            ['TET / TIT', 'tempo (e integrale) sotto soglia TTC critica', 'esposizione al rischio'],
            ['rms_accel / rms_jerk', 'RMS di accelerazione / strappo', 'comfort'],
            ['rms_gap_error', 'errore RMS sul gap desiderato', 'qualità di tracking'],
            ['head_to_tail_gain', 'ampiezza coda / ampiezza testa (plotone)', 'string stability (<1 = stabile)'],
        ],
    )))

    # ---- 4. RISULTATI MICRO ----
    A(('h1', '4. Risultati MICRO (sicurezza e comfort)'))
    A(('h2', '4.1 Verdetto: zero collisioni'))
    A(('p', 'Nessuna collisione in alcuno scenario, per nessun checkpoint, identico '
           'all’oracolo. La tabella per-tipologia (frazione di collisioni) è nulla '
           'ovunque:'))
    A(('table', (
        ['Scenario'] + [s for s in SRC_ORDER],
        [[row['scenario']] + [f"{float(row[s]):.0f}" for s in SRC_ORDER]
         for _, row in collbys.iterrows()],
    )))
    A(('p', 'Riepilogo sicurezza aggregato (su tutti i 500 scenari per sorgente). Si noti che '
           'i checkpoint SNN hanno gap minimo MAGGIORE e TET/TIT MINORE dell’oracolo: '
           'guidano in modo più cauto, non meno.'))
    A(('table', (
        ['Sorgente', 'collisioni', 'gap min', 'TTC min', 'DRAC max', 'TET med', 'TIT med'],
        [_row(_order(safety), s, ['collision_rate', 'worst_min_gap', 'worst_min_ttc',
                                  'max_DRAC', 'mean_TET', 'mean_TIT'], f3)
         for s in SRC_ORDER],
    )))
    A(('h2', '4.2 Comfort e qualità di tracking'))
    A(('p', 'Il comfort della SNN è paragonabile (anzi accelerazioni più dolci) '
           'rispetto all’oracolo; l’errore di gap è leggermente maggiore, '
           'coerente con il profilo conservativo.'))
    A(('table', (
        ['Sorgente', 'RMS accel', 'max decel', 'RMS jerk', 'errore gap', 'string gain'],
        [_row(_order(quality), s, ['rms_accel', 'max_decel', 'rms_jerk',
                                   'rms_gap_error', 'string_gain'], f3)
         for s in SRC_ORDER],
    )))
    A(('img', (F_MICRO, 'Figura 4.1 - Scorecard MICRO: ogni metrica come barre per sorgente '
                        '(verde = SNN, grigio = oracolo). Tutte le metriche di sicurezza sono '
                        'allineate o migliori dell’oracolo.')))
    A(('img', (R['val_micro_trajectories.png'],
               'Figura 4.2 - Traiettorie closed-loop (gap / velocità / accelerazione) per '
               'cut-in, hard-brake, stop&go. Nel cut-in il gap crolla al taglio e tutte le '
               'varianti SNN lo recuperano dolcemente senza toccare la linea di collisione.')))
    A(('img', (R['val_micro_ttc.png'],
               'Figura 4.3 - Time-to-collision nel tempo: i minimi restano sopra le soglie '
               'critiche per tutte le varianti.')))

    # ---- 5. RISULTATI MESO ----
    A(('h1', '5. Risultati MESO (string stability del plotone)'))
    A(('p', 'Plotone di 12 veicoli in catena (ogni veicolo riceve il CAM dal predecessore che '
           'effettivamente segue), perturbazione sinusoidale sostenuta in testa. Tutte le '
           'varianti sono string-stable: il gain testa->coda è <1 e l’onda si '
           'smorza lungo la catena. R33_C2 ha il gain migliore; le varianti S3 restano stabili '
           'pur non essendo strettamente monotone come l’oracolo.'))
    A(('table', (
        ['Sorgente', 'gain testa->coda', 'amplif. max', 'gap min', 'TTC min', 'stabile?'],
        [_row(_order(meso), s, ['head_to_tail_gain', 'max_amplification',
                                'min_gap_platoon', 'min_ttc_platoon'], f3)
         + ['sì' if bool(meso[meso.source == s].string_stable_headtail.iloc[0]) else 'no']
         for s in SRC_ORDER],
    )))
    A(('img', (R['val_meso_string.png'],
               'Figura 5.1 - Gain per veicolo (tutte le curve <1 e decrescenti = stabile) e '
               'heatmap spazio-tempo della velocità: la perturbazione si smorza lungo la '
               'catena.')))
    A(('img', (F_MESO, 'Figura 5.2 - Scorecard MESO: metriche scalari del plotone per sorgente. '
                       'La linea rossa nel pannello del gain è la soglia di '
                       'instabilità (=1).')))

    # ---- 6. ENERGIA ----
    A(('h1', '6. Profilo neuromorfico ed energia'))
    A(('p', f"Stima per-inferenza (modello di Horowitz 45nm: E_MAC=4.6 pJ, E_AC=0.9 pJ). "
           f"La SNN consuma {energy['E_snn_nJ']:.0f} nJ contro {energy['E_ann_nJ']:.0f} nJ di "
           f"una ANN equivalente densa = {energy['energy_advantage_x']:.1f}x. NOTA ONESTA: le "
           f"operazioni sinaptiche della SNN ({energy['snn_synops']:,} SynOps) SUPERANO i MAC "
           f"dell’ANN ({energy['ann_macs']:,}); quindi il vantaggio NON deriva dalla "
           f"sparsità degli spike (spike rate {energy['mean_spike_rate_pct']:.0f}%), ma "
           f"dal minor costo unitario di un accumulo rispetto a un MAC. A parità di "
           f"costo/operazione la SNN sarebbe peggiore: più sparsità = più "
           f"vantaggio. Su FPGA con pesi potenze-di-due il margine cresce (l’AC diventa un "
           f"semplice shift+add)."))
    A(('img', (F_ENERGY, 'Figura 6.1 - Energia per inferenza (sx) e conteggio operazioni (dx). '
                         'Il pannello destro chiarisce che SynOps >= MAC: il guadagno è '
                         'sul costo unitario, non sul numero di operazioni.')))
    A(('img', (R['val_raster.png'],
               'Figura 6.2 - Raster degli spike durante un cut-in (rete S3 d0.3). NOTA: il '
               'titolo interno alla figura ("spara più fitto nei transitori") è '
               'SUPERATO -- la lettura corretta è questa didascalia. Il pannello centrale '
               'mostra che il rate totale CALA dopo il cut-in (da ~75 a ~65 spike/step): la '
               'rete non spara di più nel transitorio, ma RICONFIGURA quali neuroni sono '
               'attivi (alcuni si accendono, altri si spengono). Il codice è stato '
               'corretto: i run futuri produrranno la caption giusta.')))

    # ---- 7. VERDETTO ----
    A(('h1', '7. Verdetto e limite residuo'))
    A(('p', 'La rete S3 è validata per la sicurezza: guida senza incidenti su tutti gli '
           'scenari avversari, con margini pari o superiori all’oracolo, ed è '
           'string-stable a livello di plotone. Non è una rete "timida che evita '
           'guidando piano": insegue, recupera i cut-in e segue le oscillazioni come '
           'l’oracolo, ma con un margine di sicurezza extra.'))
    A(('p', 'Il limite residuo è uno e ben definito: il bias di frenata (a sottostimato '
           '~ -40%, b sovrastimato ~ +30%). È benevolo per la safety ma degrada il '
           'realismo e potenzialmente le prestazioni (accelerazioni sotto-brillanti). È '
           'la causa-radice già diagnosticata strutturalmente: la finestra di '
           'osservabilità di a è stretta per costruzione del modello IIDM. La '
           'prossima leva (studio S4) è lato training/loss: pesare il residuo PINN sulla '
           'fase di decelerazione e/o penalizzare esplicitamente il bias di b, per stringere '
           'a/b senza toccare l’identificabilità di v0/T/s0 già acquisita.'))
    A(('callout', 'In una frase: SICURA E STABILE oggi; il prossimo lavoro è rendere '
                  'ACCURATA la frenata (a, b), non la sicurezza.'))

    # ---- 8. RIPRODUCIBILITA' ----
    A(('h1', '8. Riproducibilità e mappa dei file'))
    A(('table', (
        ['Cosa', 'Dove'],
        [
            ['Checkpoint validato', 'checkpoints/LS3_PEAK_R0_launch_d03/ (solo su Azure)'],
            ['Log training S3 (per-canale)', 'results/Loss_Study/S3/PEAK/LS3_PEAK_R0_launch_d03/training_log.csv'],
            ['Risultati validazione', 'results/evaluate/v1_realistic_cutin/{Eval_ClosedLoop,Meso,Showcase}'],
            ['Simulatore micro', 'utils/closed_loop_eval.py'],
            ['Simulatore meso', 'utils/platoon_eval.py'],
            ['Vetrina (raster/energia)', 'utils/snn_showcase.py'],
            ['Notebook di validazione', 'Loss_Study_Validation_Full.ipynb'],
            ['Questo report (generatore)', 'scripts/build_validation_report.py'],
            ['Dettagli architettura/loss', 'document/HOW_IT_WORKS.md / .pdf'],
            ['Storia identificabilità/S3', 'document/LOSS_STUDY_AND_EVALUATION.md'],
        ],
    )))
    A(('p', 'Le figure quantitative di questo report (accuratezza, NRMSE, scorecard micro/meso, '
           'energia) sono RICOSTRUITE dai CSV/JSON dei risultati eseguendo '
           '"python scripts/build_validation_report.py" -- nessun checkpoint richiesto. Le '
           'figure di traiettoria, TTC, string-stability e raster sono riusate dai PNG '
           'prodotti dal notebook di validazione.'))
    return D


DOC = build_doc()


# ---------------------------------------------------------------------------
# 3. Render Markdown
# ---------------------------------------------------------------------------
def render_md(doc, outpath):
    L = []
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
        elif kind == 'code':
            L.append('```\n' + b + '\n```\n')
        elif kind == 'hr':
            L.append('\n---\n')
        elif kind == 'table':
            headers, rows = b
            L.append('| ' + ' | '.join(headers) + ' |')
            L.append('|' + '|'.join(['---'] * len(headers)) + '|')
            for r in rows:
                L.append('| ' + ' | '.join(str(x) for x in r) + ' |')
            L.append('')
        elif kind == 'img':
            path, cap = b
            rel = os.path.relpath(path, DOCDIR).replace('\\', '/')
            L.append(f"![{cap}]({rel})")
            L.append(f"*{cap}*\n")
    txt = '\n'.join(L)
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(txt)
    print('  scritto', outpath)


# ---------------------------------------------------------------------------
# 4. Render PDF (reportlab)
# ---------------------------------------------------------------------------
def render_pdf(doc, outpath):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                    Table, TableStyle, PageBreak, HRFlowable)
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import ImageReader

    fdir = os.path.join(os.path.dirname(matplotlib.__file__), 'mpl-data', 'fonts', 'ttf')
    pdfmetrics.registerFont(TTFont('DJ', os.path.join(fdir, 'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('DJ-B', os.path.join(fdir, 'DejaVuSans-Bold.ttf')))
    pdfmetrics.registerFont(TTFont('DJ-M', os.path.join(fdir, 'DejaVuSansMono.ttf')))

    ss = getSampleStyleSheet()
    body = ParagraphStyle('body', parent=ss['Normal'], fontName='DJ', fontSize=9.5,
                          leading=14, spaceAfter=6, alignment=4)
    h1 = ParagraphStyle('h1', fontName='DJ-B', fontSize=16, leading=20, spaceBefore=14,
                        spaceAfter=8, textColor=colors.HexColor('#1a3c6e'))
    h2 = ParagraphStyle('h2', fontName='DJ-B', fontSize=12.5, leading=16, spaceBefore=10,
                        spaceAfter=5, textColor=colors.HexColor('#26527a'))
    h3 = ParagraphStyle('h3', fontName='DJ-B', fontSize=10.5, leading=14, spaceBefore=7,
                        spaceAfter=4, textColor=colors.HexColor('#333333'))
    cap = ParagraphStyle('cap', parent=body, fontName='DJ', fontSize=8, leading=11,
                         textColor=colors.HexColor('#555555'), spaceAfter=12, alignment=4)
    callout = ParagraphStyle('callout', parent=body, fontName='DJ', fontSize=9.5,
                             leading=14, leftIndent=8, borderPadding=6,
                             backColor=colors.HexColor('#eef3fa'),
                             borderColor=colors.HexColor('#9bb8d8'), borderWidth=0.6,
                             spaceBefore=4, spaceAfter=10)
    mono = ParagraphStyle('mono', parent=body, fontName='DJ-M', fontSize=8, leading=11)

    def esc(s):
        return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))

    usable_w = A4[0] - 3.6 * cm
    story = []

    def add_image(path, caption):
        img = ImageReader(path)
        iw, ih = img.getSize()
        w = usable_w
        h = w * ih / iw
        max_h = 12.5 * cm
        if h > max_h:
            h = max_h; w = h * iw / ih
        story.append(Spacer(1, 4))
        story.append(Image(path, width=w, height=h))
        story.append(Paragraph(esc(caption), cap))

    def make_table(headers, rows):
        ncol = len(headers)
        fs = 8 if ncol <= 5 else 7 if ncol <= 7 else 6.3
        data = [[Paragraph(f'<b>{esc(h)}</b>', ParagraphStyle('th', fontName='DJ-B',
                 fontSize=fs, leading=fs + 2, textColor=colors.white)) for h in headers]]
        cell = ParagraphStyle('td', fontName='DJ', fontSize=fs, leading=fs + 2.5)
        for r in rows:
            data.append([Paragraph(esc(x), cell) for x in r])
        t = Table(data, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#26527a')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
             [colors.white, colors.HexColor('#f1f5fa')]),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#b9c6d6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(Spacer(1, 2)); story.append(t); story.append(Spacer(1, 8))

    for kind, *rest in doc:
        b = rest[0] if rest else None
        if kind == 'cover':
            story.append(Spacer(1, 3.5 * cm))
            story.append(Paragraph(esc(b['title']), ParagraphStyle('ct', fontName='DJ-B',
                         fontSize=24, leading=30, textColor=colors.HexColor('#1a3c6e'),
                         alignment=1)))
            story.append(Spacer(1, 0.5 * cm))
            story.append(Paragraph(esc(b['subtitle']), ParagraphStyle('cs', fontName='DJ',
                         fontSize=12, leading=17, textColor=colors.HexColor('#444444'),
                         alignment=1)))
            story.append(Spacer(1, 1.4 * cm))
            story.append(HRFlowable(width='60%', thickness=1,
                         color=colors.HexColor('#9bb8d8')))
            story.append(Spacer(1, 0.6 * cm))
            for m in b['meta']:
                story.append(Paragraph(esc(m), ParagraphStyle('cm', fontName='DJ', fontSize=10,
                             leading=15, alignment=1, textColor=colors.HexColor('#333333'))))
            story.append(PageBreak())
        elif kind == 'h1':
            story.append(Paragraph(esc(b), h1))
            story.append(HRFlowable(width='100%', thickness=0.8,
                         color=colors.HexColor('#c5d3e2'), spaceAfter=6))
        elif kind == 'h2':
            story.append(Paragraph(esc(b), h2))
        elif kind == 'h3':
            story.append(Paragraph(esc(b), h3))
        elif kind == 'p':
            story.append(Paragraph(esc(b), body))
        elif kind == 'callout':
            story.append(Paragraph('<b>Nota.</b> ' + esc(b), callout))
        elif kind == 'code':
            for line in b.split('\n'):
                story.append(Paragraph(line.replace(' ', '&nbsp;') or '&nbsp;', mono))
            story.append(Spacer(1, 8))
        elif kind == 'hr':
            story.append(HRFlowable(width='100%', thickness=0.6,
                         color=colors.HexColor('#cccccc'), spaceBefore=6, spaceAfter=6))
        elif kind == 'table':
            make_table(*b)
        elif kind == 'img':
            add_image(*b)

    def footer(canvas, docx):
        canvas.saveState()
        canvas.setFont('DJ', 7.5)
        canvas.setFillColor(colors.HexColor('#888888'))
        canvas.drawString(2 * cm, 1.1 * cm, 'CF_FSNN - Report di Validazione')
        canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f'pag. {docx.page}')
        canvas.restoreState()

    pdf = SimpleDocTemplate(outpath, pagesize=A4, topMargin=1.8 * cm,
                            bottomMargin=1.8 * cm, leftMargin=1.8 * cm,
                            rightMargin=1.8 * cm, title='CF_FSNN Report di Validazione')
    pdf.build(story, onFirstPage=footer, onLaterPages=footer)
    print('  scritto', outpath)


print('[2/4] render markdown...')
render_md(DOC, os.path.join(DOCDIR, 'VALIDATION_REPORT.md'))
print('[3/4] render pdf...')
render_pdf(DOC, os.path.join(DOCDIR, 'VALIDATION_REPORT.pdf'))
print('[4/4] fatto.')
