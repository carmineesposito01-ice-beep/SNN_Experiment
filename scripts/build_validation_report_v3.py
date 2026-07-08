"""Genera il REPORT DI VALIDAZIONE CF_FSNN v3 (.md + .pdf) da un'unica sorgente.

Chiusura dello studio EventProp: evaluate esaustivo a 6-tier / 15 dimensioni su
4 champion (2 BPTT + 2 EventProp) piu' l'oracolo, dalla run
`results/evaluate/v3_TURTLE_POWER!!!/`. Obiettivo: un documento tecnico chiaro,
esaustivo e ONESTO, leggibile da un ingegnere che non conosce il progetto, che dia
piena coscienza (a) dei 4 champion e del fronte di Pareto EventProp/BPTT,
(b) della loro validazione closed-loop micro/meso/macro, (c) del profilo FPGA
(quantizzazione, energia, discriminante di stabilita' rho), e (d) del candidato
al deploy.

Stile: emula scripts/build_validation_report.py (reportlab, unica sorgente -> md+pdf).
Le figure-CHIAVE (accuratezza, discriminante FPGA, sicurezza, quantizzazione, V2X)
sono RICOSTRUITE dai CSV dei risultati (riproducibili senza checkpoint); le figure
di dettaglio (identificabilita', traffico, raster, showcase) sono RIUSATE dai PNG
genuini prodotti dal notebook v3.

Uso:  python scripts/build_validation_report_v3.py
Output: document/VALIDATION_REPORT_v3.{md,pdf}, document/figures_validation_v3/*
"""
import os
import shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCDIR = os.path.join(ROOT, 'document')
FIGDIR = os.path.join(DOCDIR, 'figures_validation_v3')
EVAL = os.path.join(ROOT, 'results', 'evaluate', 'v3_TURTLE_POWER!!!')
os.makedirs(FIGDIR, exist_ok=True)

# --- champion / oracolo -----------------------------------------------------
CHAMP = ['Raffaello', 'Leonardo', 'Donatello', 'Michelangelo']
ORACLE = 'Master Splinter'
SRC = CHAMP + [ORACLE]
METHOD = {'Raffaello': 'BPTT', 'Leonardo': 'BPTT',
          'Donatello': 'EventProp', 'Michelangelo': 'EventProp'}
CKPT = {'Raffaello': 'R33_C2_A1_T12_fix', 'Leonardo': 'LS3_PEAK_R0_launch_d03',
        'Donatello': 'PE_t05_gp0002', 'Michelangelo': 'A_lr1e2_t06_r16'}
CHARACTER = {'Raffaello': 'Prodigy, aggressivo', 'Leonardo': 'BPTT, conservativo',
             'Donatello': 'EventProp, best-NRMSE', 'Michelangelo': 'EventProp, best-Adam'}
COLOR = {'Raffaello': '#d1495b', 'Leonardo': '#2a7fb8', 'Donatello': '#7b3fa0',
         'Michelangelo': '#e8871e', 'Master Splinter': '#7f7f7f'}
PN = ['v0', 'T', 's0', 'a', 'b']

# ---------------------------------------------------------------------------
# 0. Carica tutti i CSV una volta (numeri veri -> testo riproducibile)
# ---------------------------------------------------------------------------
def _csv(*p):
    return pd.read_csv(os.path.join(EVAL, *p))

ACC = _csv('01_Accuracy', 'accuracy.csv').set_index('champion')
SAF = _csv('02_Safety_ClosedLoop', 'safety.csv').set_index('champion')
SS = _csv('03_StringStability', 'string_stability.csv').set_index('champion')
STRAT = _csv('04_Identifiability', 'nrmse_stratified.csv')
NAT = _csv('04_Identifiability', 'naturalisticity_calibration.csv').set_index('champion')
_fim = _csv('04_Identifiability', 'fim.csv')
FIM = dict(zip(_fim['metric'], _fim['value']))


def _fimnum(k):
    return float(FIM[k])
QNT = _csv('05_Quantization', 'quantization.csv')
QAB = _csv('05_Quantization', 'quant_weight_ablation.csv').set_index('champion')
QPP = _csv('05_Quantization', 'quant_perparam.csv').set_index('champion')
V2X = _csv('06_V2X_Robustness', 'v2x.csv')
PLANT = _csv('07_VehicleDynamics', 'plant.csv').set_index('champion')
EN = _csv('08_Energy_Spiking', 'energy.csv').set_index('champion')
REACH = _csv('10_Reachability', 'reachability.csv')
BRK = _csv('11_Breakdown', 'breakdown.csv')
MESO = _csv('12_Mesoscopic', 'meso_summary.csv').set_index('source')
MACRO = _csv('13_Macroscopic', 'macro_summary.csv').set_index('source')

# derivati narrativi
ACC_MEAN_EP = np.mean([ACC.loc[c, 'accuracy_pct'] for c in ['Donatello', 'Michelangelo']])
ACC_MEAN_BP = np.mean([ACC.loc[c, 'accuracy_pct'] for c in ['Raffaello', 'Leonardo']])
MESO_GMIN = min(MESO.loc[c, 'head_to_tail_gain'] for c in CHAMP)
MESO_GMAX = max(MESO.loc[c, 'head_to_tail_gain'] for c in CHAMP)
SPK_MIN = min(EN.loc[c, 'mean_spike_rate_pct'] for c in CHAMP)
SPK_MAX = max(EN.loc[c, 'mean_spike_rate_pct'] for c in CHAMP)


def _v2x(ch, axis, val, col='collision_rate'):
    r = V2X[(V2X.champion == ch) & (V2X.axis == axis) & (V2X.val == val)]
    return float(r[col].iloc[0])


# ---------------------------------------------------------------------------
# 1. Figure-CHIAVE ricostruite dai CSV
# ---------------------------------------------------------------------------
def fig_accuracy():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 4.9))
    x = np.arange(len(PN)); w = 0.2
    for i, ch in enumerate(CHAMP):
        vals = [ACC.loc[ch, f'nrmse_{p}'] for p in PN]
        a1.bar(x + (i - 1.5) * w, vals, w, label=f'{ch} ({METHOD[ch]})', color=COLOR[ch])
    a1.set_xticks(x); a1.set_xticklabels(PN)
    a1.axhline(0.2, color='gray', ls=':', lw=1)
    a1.set_ylabel('NRMSE per canale  (più basso = meglio)')
    a1.set_title('Errore di identificazione per parametro')
    a1.legend(fontsize=7, ncol=2); a1.grid(alpha=0.3, axis='y')
    accs = [ACC.loc[ch, 'accuracy_pct'] for ch in CHAMP]
    bars = a2.bar(range(len(CHAMP)), accs, color=[COLOR[c] for c in CHAMP])
    a2.axhline(100, color='gray', ls='--', lw=1)
    a2.text(len(CHAMP) - 0.5, 100.5, 'oracolo (100%)', ha='right', fontsize=8, color='gray')
    a2.set_xticks(range(len(CHAMP)))
    a2.set_xticklabels([f'{c}\n{METHOD[c]}' for c in CHAMP], fontsize=8)
    a2.set_ylim(0, 108); a2.set_ylabel('accuratezza ~ (1 - NRMSE media)  [%]')
    a2.set_title('Accuratezza complessiva: EventProp > BPTT')
    for bb, v in zip(bars, accs):
        a2.text(bb.get_x() + bb.get_width() / 2, v + 1.5, f'{v:.1f}', ha='center', fontsize=9)
    a2.grid(alpha=0.3, axis='y')
    plt.tight_layout()
    p = os.path.join(FIGDIR, 'val_accuracy.png')
    plt.savefig(p, dpi=130); plt.close(fig)
    return p


def fig_fpga():
    fig, ax = plt.subplots(figsize=(10, 5.8))
    ax.axvspan(0, 1, color='#e8f5e9')
    ax.axvline(1.0, color='tab:red', ls='--', lw=1.2)
    for ch in CHAMP:
        rho = EN.loc[ch, 'spectral_radius']; acc = ACC.loc[ch, 'accuracy_pct']
        adv = EN.loc[ch, 'advantage_x']; dead = EN.loc[ch, 'dead_frac'] * 100
        mk = 'o' if METHOD[ch] == 'EventProp' else 's'
        ax.scatter(rho, acc, s=adv * 70, c=COLOR[ch], marker=mk,
                   edgecolor='k', linewidth=1.1, zorder=3, alpha=0.9)
        dx = 0.06 if rho < 1.5 else -0.06
        ha = 'left' if rho < 1.5 else 'right'
        ax.annotate(f'{ch} ({METHOD[ch]})\nrho={rho:.2f} | {dead:.0f}% neuroni morti | {adv:.0f}x energia',
                    (rho, acc), xytext=(rho + dx, acc - 2.4), fontsize=8, ha=ha,
                    color=COLOR[ch])
    ax.text(0.5, 71.5, 'ZONA CONTRATTIVA  ρ<1\n(stato limitato in fixed-point)',
            ha='center', fontsize=9, color='#2e7d32', style='italic')
    ax.text(2.1, 71.5, 'ZONA ESPANSIVA  ρ>1\n(rischio blow-up)',
            ha='center', fontsize=9, color='#c62828', style='italic')
    ax.set_xlabel('raggio spettrale ρ(U·V) della ricorrenza ALIF')
    ax.set_ylabel('accuratezza di identificazione [%]')
    ax.set_title('Discriminante FPGA: EventProp è contrattivo + più accurato. '
                 'Marker = area proporzionale al vantaggio energetico.\n'
                 'Cerchio = EventProp, quadrato = BPTT. In alto-a-sinistra = ideale per il deploy.',
                 fontsize=9.5)
    ax.set_xlim(-0.2, 3.3); ax.set_ylim(66, 88)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    p = os.path.join(FIGDIR, 'val_fpga_discriminant.png')
    plt.savefig(p, dpi=130); plt.close(fig)
    return p


def fig_safety():
    panels = [('collision_rate', 'tasso di collisione  (più basso = meglio)'),
              ('brake_margin_min', 'margine di frenata minimo [m]  (più alto = meglio)'),
              ('min_ttc', 'TTC minimo [s]  (più alto = meglio)'),
              ('impact_dv', 'delta-v d\'impatto [m/s]  (più basso = meglio)')]
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.4))
    for ax, (col, title) in zip(axes, panels):
        vals = [SAF.loc[s, col] for s in SRC]
        cols = [COLOR[s] for s in SRC]
        ax.bar(range(len(SRC)), vals, color=cols, alpha=0.9)
        ax.set_xticks(range(len(SRC)))
        ax.set_xticklabels([s.replace(' ', '\n') for s in SRC], rotation=0, fontsize=7)
        ax.set_title(title, fontsize=8.5); ax.grid(alpha=0.3, axis='y')
    fig.suptitle('Sicurezza closed-loop: i 4 champion (colore) sono allineati all\'oracolo (grigio, "Master Splinter"). '
                 'Le collisioni residue sono fisica (geometrie di cut-in inevitabili), non la rete.', fontsize=10)
    fig.tight_layout()
    p = os.path.join(FIGDIR, 'val_safety.png')
    plt.savefig(p, dpi=125); plt.close(fig)
    return p


def fig_quant():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 4.8))
    bits = [12, 8, 6, 4, 3, 2]
    for ch in CHAMP:
        sub = QNT[(QNT.champion == ch) & (QNT['mode'] == 'fixed')]
        y = [float(sub[sub.frac_bits == str(b)].id_err_mean.iloc[0]) for b in bits]
        a1.plot(bits, y, marker='o', color=COLOR[ch], label=f'{ch} (fixed)')
        po2 = QNT[(QNT.champion == ch) & (QNT['mode'] == 'po2') & (QNT.frac_bits == '2')]
        a1.scatter([2], [float(po2.id_err_mean.iloc[0])], marker='x', s=60,
                   color=COLOR[ch], zorder=4)
    a1.invert_xaxis()
    a1.set_xlabel('bit di parte frazionaria (fixed-point Qm.n)')
    a1.set_ylabel('errore medio di identificazione')
    a1.set_title('Fixed-point: piatto fino a 2 bit (nessuna perdita).\n'
                 'x = variante po2 a 2 bit (shift-add su FPGA)')
    a1.legend(fontsize=7); a1.grid(alpha=0.3)
    deltas = [QAB.loc[ch, 'delta_qat_absorbed'] for ch in CHAMP]
    cols = ['#2e7d32' if d <= 0 else '#c62828' for d in deltas]
    b = a2.bar(range(len(CHAMP)), deltas, color=cols, alpha=0.85)
    a2.axhline(0, color='k', lw=0.8)
    a2.set_xticks(range(len(CHAMP))); a2.set_xticklabels(CHAMP, fontsize=8)
    a2.set_ylabel('delta errore po2 (ON - OFF)')
    a2.set_title('QAT assorbe i pesi po2: delta <= 0 su 3/4 champion\n'
                 '(verde = po2 non peggiora; il peso-di-2 è già quello nativo)')
    for bb, d in zip(b, deltas):
        a2.text(bb.get_x() + bb.get_width() / 2, d, f'{d:+.2f}',
                ha='center', va='bottom' if d >= 0 else 'top', fontsize=8)
    a2.grid(alpha=0.3, axis='y')
    plt.tight_layout()
    p = os.path.join(FIGDIR, 'val_quant.png')
    plt.savefig(p, dpi=130); plt.close(fig)
    return p


def fig_v2x():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 4.8))
    modes = ['hold_last', 'dead_reckon', 'blind']
    mlabel = ['hold-last\n(ZOH, default)', 'dead-reckon', 'blind\n(nessun handler)']
    x = np.arange(len(modes)); w = 0.2
    for i, ch in enumerate(CHAMP):
        sub = V2X[(V2X.champion == ch) & (V2X.axis == 'hold_mode')]
        y = [float(sub[sub.val == m].collision_rate.iloc[0]) for m in modes]
        a1.bar(x + (i - 1.5) * w, y, w, color=COLOR[ch], label=ch)
    a1.set_xticks(x); a1.set_xticklabels(mlabel, fontsize=8)
    a1.set_ylabel('tasso di collisione')
    a1.set_title('Il "hold-last-CAM" MASCHERA la perdita di pacchetti:\n'
                 'senza handler (blind) la collisione esplode a ~0.67')
    a1.legend(fontsize=7); a1.grid(alpha=0.3, axis='y')
    stress = [('pdr', '1.0', 'nominale'), ('latency', '3', 'latenza 3'),
              ('gilbert', '0.40/0.40', 'canale pessimo'), ('blackout', '150-200', 'blackout')]
    xs = np.arange(len(stress)); w2 = 0.18
    for i, ch in enumerate(CHAMP):
        y = []
        for ax_name, val, _ in stress:
            r = V2X[(V2X.champion == ch) & (V2X.axis == ax_name) & (V2X.val == val)]
            y.append(float(r.collision_rate.iloc[0]))
        a2.bar(xs + (i - 1.5) * w2, y, w2, color=COLOR[ch], label=ch)
    a2.set_xticks(xs); a2.set_xticklabels([s[2] for s in stress], fontsize=8)
    a2.set_ylabel('tasso di collisione')
    a2.set_title('Degrado sotto stress di canale: PDR/latenza tollerati,\n'
                 'canale pessimo (Gilbert 0.4/0.4) e blackout costano cari')
    a2.legend(fontsize=7); a2.grid(alpha=0.3, axis='y')
    plt.tight_layout()
    p = os.path.join(FIGDIR, 'val_v2x.png')
    plt.savefig(p, dpi=130); plt.close(fig)
    return p


def copy_reused():
    reuse = {
        'radar.png': ('00_Scorecard', 'radar.png'),
        'nrmse_stratified.png': ('04_Identifiability', 'nrmse_stratified.png'),
        'fim.png': ('04_Identifiability', 'fim.png'),
        'causal.png': ('04_Identifiability', 'causal.png'),
        'naturalisticity.png': ('04_Identifiability', 'naturalisticity_calibration.png'),
        'safety_scorecard.png': ('02_Safety_ClosedLoop', 'safety_scorecard.png'),
        'delta_vs_oracle.png': ('02_Safety_ClosedLoop', 'delta_vs_oracle.png'),
        'ssm_distribution.png': ('02_Safety_ClosedLoop', 'ssm_distribution.png'),
        'per_scenario_min_gap.png': ('02_Safety_ClosedLoop', 'per_scenario_min_gap.png'),
        'comfort_iso.png': ('02_Safety_ClosedLoop', 'comfort_iso.png'),
        'traj_cut_in.png': ('09_Trajectories', 'traj_cut_in.png'),
        'traj_hard_brake.png': ('09_Trajectories', 'traj_hard_brake.png'),
        'plant.png': ('07_VehicleDynamics', 'plant.png'),
        'reachability.png': ('10_Reachability', 'reachability.png'),
        'breakdown.png': ('11_Breakdown', 'breakdown.png'),
        'string_stability.png': ('03_StringStability', 'string_stability.png'),
        'meso_gain.png': ('12_Mesoscopic', 'meso_gain.png'),
        'meso_spacetime.png': ('12_Mesoscopic', 'meso_spacetime.png'),
        'macro_fd.png': ('13_Macroscopic', 'macro_fundamental_diagram.png'),
        'v2x_holdmode.png': ('06_V2X_Robustness', 'v2x_holdmode.png'),
        'v2x_aoi.png': ('06_V2X_Robustness', 'v2x_aoi.png'),
        'energy.png': ('08_Energy_Spiking', 'energy.png'),
        'raster_Donatello.png': ('08_Energy_Spiking', 'raster', 'raster_Donatello.png'),
        'raster_Raffaello.png': ('08_Energy_Spiking', 'raster', 'raster_Raffaello.png'),
        'showcase_Donatello.png': ('14_Showcase', 'showcase_Donatello.png'),
    }
    out = {}
    for dst, src in reuse.items():
        srcp = os.path.join(EVAL, *src)
        dstp = os.path.join(FIGDIR, dst)
        if os.path.exists(srcp):
            shutil.copy2(srcp, dstp)
            out[dst] = dstp
        else:
            print('  [warn] manca', srcp)
    return out


def fig_eq(name, lines, fs=15, color='#12233a'):
    """Renderizza una o più righe di equazione (mathtext) in un PNG 'tight'.
    Nota: nessun carattere accentato dentro la formula (le legende vanno in didascalia)."""
    n = len(lines)
    fig = plt.figure(figsize=(9.2, 0.52 * n + 0.22))
    for i, ln in enumerate(lines):
        fig.text(0.5, 1.0 - (i + 0.5) / n, '$' + ln + '$',
                 ha='center', va='center', fontsize=fs, color=color)
    p = os.path.join(FIGDIR, name)
    fig.savefig(p, dpi=150, bbox_inches='tight', pad_inches=0.18, facecolor='white')
    plt.close(fig)
    return p


print('[1/4] genero figure-chiave...')
F_ACC = fig_accuracy()
F_FPGA = fig_fpga()
F_SAFE = fig_safety()
F_QUANT = fig_quant()
F_V2X = fig_v2x()
R = copy_reused()
EQ_NRMSE = fig_eq('eq_nrmse.png', [
    r'\mathrm{NRMSE}(p) = \frac{\sqrt{\frac{1}{N}\sum_{i}(\hat p_i - p_i)^2}}{p_{\max}-p_{\min}}',
])
EQ_FIM = fig_eq('eq_fim.png', [
    r'\mathrm{FIM} = J^{\top} J\,, \qquad \kappa(\mathrm{FIM}) = \frac{\sigma_{\max}}{\sigma_{\min}}',
])
EQ_SSM = fig_eq('eq_ssm.png', [
    r'\mathrm{TTC} = \frac{s}{\Delta v}\;(\Delta v>0)\,, \quad \mathrm{DRAC} = \frac{\Delta v^{2}}{2\,s}\,, \quad \mathrm{TET} = \sum_t \Delta t\cdot\mathbf{1}[\,\mathrm{TTC}_t < \tau\,]',
])
EQ_KS = fig_eq('eq_ks.png', [
    r'D_{\mathrm{KS}} = \sup_x\, \left|\,F_{\mathrm{rete}}(x) - F_{\mathrm{umano}}(x)\,\right|',
])
EQ_STRING = fig_eq('eq_string.png', [
    r'G_{\mathrm{h2t}} = \frac{\max_t \left|\,s_N(t)-\bar s_N\,\right|}{\max_t \left|\,s_1(t)-\bar s_1\,\right|}',
    r'G_{\mathrm{h2t}} < 1 \ \ \Rightarrow \ \ \mathrm{string\ stable}',
])
EQ_FD = fig_eq('eq_fd.png', [
    r'q(\rho) = \rho \cdot v(\rho)',
])
print('  figure in', FIGDIR)


# ---------------------------------------------------------------------------
# 2. Contenuto (unica sorgente -> md + pdf)
# ---------------------------------------------------------------------------
def f2(v):
    return f'{float(v):.2f}'


def f3(v):
    return f'{float(v):.3f}'


def pct(v):
    return f'{float(v) * 100:.1f}%'


def build_doc():
    D = []
    A = D.append

    # ---- COVER ----
    A(('cover', {
        'title': 'CF_FSNN - Report di Validazione (v3)',
        'subtitle': 'Chiusura dello studio EventProp: 4 champion (2 BPTT + 2 EventProp) '
                    'a confronto con l\'oracolo, su un evaluate esaustivo a 6-tier',
        'meta': [
            'Champion validati: Raffaello, Leonardo (BPTT) · Donatello, Michelangelo (EventProp)',
            'Riferimento: Master Splinter (oracolo = ACC-IIDM coi parametri veri)',
            'Sorgente dei dati: results/evaluate/v3_TURTLE_POWER!!! (15 dimensioni)',
            'Documento della terna CF_FSNN — gemello di HOW_IT_WORKS_v3 (la rete) e FPGA_REPORT (il profilo hardware)',
        ],
    }))

    A(('h1', 'Indice'))
    A(('table', (
        ['Sezione', 'Contenuto'],
        [
            ['1', 'Sommario esecutivo'],
            ['2', 'Il contesto: lo studio EventProp e i 4 champion'],
            ['3', 'Metodologia: la valutazione a 6-tier'],
            ['4', 'Identificazione dei parametri (accuratezza, osservabilità, FIM)'],
            ['5', 'Sicurezza closed-loop'],
            ['6', 'Robustezza fisica e curva di rottura'],
            ['7', 'Traffico: micro, meso, macro'],
            ['8', 'Robustezza V2X'],
            ['9', 'Profilo FPGA (sommario)'],
            ['10', 'Verdetto consolidato e raccomandazione di deploy'],
            ['11', 'Limiti residui e prossimi passi'],
            ['12', 'Riproducibilità e mappa dei file'],
            ['13', 'Riferimenti'],
        ],
    )))

    # ---- 1. SOMMARIO ESECUTIVO ----
    A(('h1', '1. Sommario esecutivo'))
    A(('p', 'CF_FSNN è una rete neurale spiking (SNN, ~860-1400 parametri secondo il rango della ricorrenza, target FPGA PYNQ-Z1) '
           'che osserva un veicolo follower via V2X (gap, velocità, delta-v, velocità leader) '
           'e ne identifica i 5 parametri del modello di car-following ACC-IIDM: [v0, T, s0, a, b] '
           '(Treiber & Kesting, Ch.12). Questo documento è il report di CHIUSURA dello studio '
           'EventProp: mette a confronto i 4 champion emersi dallo studio - due addestrati con '
           'BPTT+surrogate gradient (Raffaello, Leonardo) e due con EventProp, il gradiente '
           'aggiunto esatto (Donatello, Michelangelo) - più l\'oracolo, su una validazione '
           'closed-loop esaustiva a 6 livelli (15 dimensioni: dall\'accuratezza alla sicurezza, '
           'al traffico, al profilo hardware FPGA).'))
    A(('p', 'Verdetto. Tutti e 4 i champion guidano in sicurezza: in anello chiuso il loro tasso '
           'di collisione è allineato a quello dell\'oracolo, con TTC pari o superiori e margini '
           'di frenata comparabili (guidano più cauti, non meno). Le collisioni residue non sono un difetto '
           'della rete ma un limite fisico: geometrie di cut-in inevitabili e fondo ghiacciato '
           'fanno collidere anche l\'oracolo. Sul piano hardware emerge un discriminante netto: '
           'i due champion EventProp sono contrattivi (raggio spettrale della ricorrenza ρ<1) e '
           'non hanno neuroni morti, mentre i due BPTT sono espansivi (ρ>1) con ~31% di neuroni '
           'morti. Contrattivo = stato limitato in aritmetica a virgola fissa = sicuro su FPGA. '
           'Sommato alla migliore accuratezza, questo indica '
           + '**Donatello (EventProp)** come candidato al deploy: ρ=' + f2(EN.loc['Donatello', 'spectral_radius'])
           + ', accuratezza ' + f2(ACC.loc['Donatello', 'accuracy_pct']) + '%, 0 neuroni morti. '
           + 'Avvertenza importante: tutti i risultati qui riportati sono in SIMULAZIONE closed-loop '
           + '(plant e oracolo simulati); il deploy su FPGA è progettato ma NON ancora validato in '
           + 'hardware - la conversione in HDL è un problema aperto (sezione 11).'))
    A(('table', (
        ['Asse', 'Risultato', 'Lettura'],
        [
            ['Accuratezza (identificazione)',
             f'EventProp {ACC_MEAN_EP:.0f}% vs BPTT {ACC_MEAN_BP:.0f}% (media); best Donatello {f2(ACC.loc["Donatello","accuracy_pct"])}%',
             'EventProp identifica meglio'],
            ['Sicurezza (closed-loop)',
             f'collisione champion {f2(SAF.loc["Raffaello","collision_rate"]*100)}-{f2(SAF.loc["Donatello","collision_rate"]*100)}% ~ oracolo {f2(SAF.loc[ORACLE,"collision_rate"]*100)}%',
             'come l\'oracolo (residuo = fisica)'],
            ['Traffico (meso plotone)',
             f'string-stable: gain testa->coda {f2(MESO_GMIN)}-{f2(MESO_GMAX)} (<1)',
             'plotone di 12 stabile'],
            ['Stabilità FPGA (discriminante)',
             f'ρ EventProp {f2(EN.loc["Donatello","spectral_radius"])}/{f2(EN.loc["Michelangelo","spectral_radius"])} (<1) vs BPTT {f2(EN.loc["Leonardo","spectral_radius"])}/{f2(EN.loc["Raffaello","spectral_radius"])} (>1)',
             'EventProp contrattivo -> fixed-point sicuro'],
            ['Quantizzazione',
             'fixed-point trascurabile fino a 2 bit; po2 assorbito dal QAT (delta<=0 su 3/4)',
             'pronto per pesi potenze-di-due'],
            ['Energia',
             f'{f2(min(EN.loc[c,"advantage_x"] for c in CHAMP))}x-{f2(max(EN.loc[c,"advantage_x"] for c in CHAMP))}x vs ANN densa; spike rate {f2(SPK_MIN)}-{f2(SPK_MAX)}% (NON sparso)',
             'da costo AC (accumulo) < MAC (molt.-accum.), non da sparsità'],
            ['V2X (perdita pacchetti)',
             f'blind = {f2(_v2x("Donatello","hold_mode","blind")*100)}% collisione; con hold-last ~{f2(_v2x("Donatello","hold_mode","hold_last")*100)}%',
             'robustezza data dall\'handler, non dalla rete'],
            ['Candidato deploy', 'Donatello (contrattivo + best accuracy + 0 morti)', 'runner-up Michelangelo'],
        ],
    )))
    A(('callout', 'Una lezione trasversale dello studio, confermata qui in closed-loop: la fisica '
                  '(errore sul dato/comportamento di guida) governa la sicurezza, non la sola NRMSE. '
                  'Un champion con NRMSE più bassa non è automaticamente più sicuro; per questo '
                  'il report privilegia le metriche di comportamento e i margini di sicurezza rispetto '
                  'all\'accuratezza nuda.'))

    # ---- 2. CONTESTO ----
    A(('h1', '2. Il contesto: lo studio EventProp e i 4 champion'))
    A(('h2', '2.1 CF_FSNN in una pagina'))
    A(('p', 'Architettura: input(4) -> strato nascosto ALIF (neuroni spiking con soglia adattiva, '
           'ricorrenza a basso rango, ritardi assonali) -> output LI (5) -> sigmoide + bounds fisici '
           '-> [v0, T, s0, a, b]. Ogni passo reale (0.1 s) è elaborato con più tick SNN interni; '
           'i pesi sono destinati a essere quantizzati a potenze-di-due (moltiplicazione -> bit-shift '
           'su FPGA) e il leak di membrana è un bit-shift. La loss è PINN (physics-informed): un '
           'termine dati (l\'accelerazione ricostruita dai parametri predetti deve combaciare con '
           'quella ACC-IIDM vera) più termini di coerenza fisica. La rete non predice una '
           'traiettoria ma i 5 NUMERI che caratterizzano lo stile di guida. Dettagli completi di '
           'architettura, neurone ALIF e loss in document/HOW_IT_WORKS_v3.md e GLOSSARY.md.'))
    A(('h2', '2.2 EventProp vs BPTT: un fronte di Pareto'))
    A(('p', 'Lo studio ha mappato e chiuso il confronto tra due modi di calcolare il gradiente '
           'attraverso i tick della SNN: BPTT con surrogate gradient (si "ammorbidisce" la soglia '
           'non-differenziabile dello spike) contro EventProp (adjoint esatto sugli istanti di '
           'spike). Il risultato è un fronte di Pareto, non un vincitore secco: il champion BPTT '
           'vince di poco sulla fisica pura (~5.5%), ma EventProp vince su NRMSE, su STABILITA\' '
           '(raggio spettrale ρ 0.05-0.39 negli EventProp contro 1.16-2.99 nei BPTT champion — le '
           'famiglie BPTT storiche scartate toccavano ~22) e '
           'su FPGA-friendliness; ed entrambi guidano in sicurezza. Il presente evaluate quantifica '
           'quel fronte su tutte le dimensioni che contano per un deploy neuromorfico.'))
    A(('callout', 'ρ(U·V) è il raggio spettrale della ricorrenza low-rank: ρ<1 = mappa contrattiva '
                  '(stato limitato, quantizzazione sicura in virgola fissa), ρ>1 = espansiva (rischio '
                  'saturazione/overflow). I FONDAMENTI teorici sono in HOW_IT_WORKS_v3 §11; qui il '
                  'RISULTATO: EventProp produce reti contrattive per costruzione (confermato sui champion, '
                  '§9.3) - un vantaggio strutturale sul silicio.'))
    A(('h2', '2.3 I 4 champion e l\'oracolo'))
    A(('p', 'Il confronto usa 4 champion più l\'oracolo. Tutti i champion condividono la stessa '
           'struttura (input(4) → ALIF(32) → LI(5)); differiscono per metodo e ricetta di addestramento '
           'e per il rango della ricorrenza (8 nei BPTT, 16 negli EventProp). L\'oracolo (nome in codice '
           '"Master Splinter") NON è una rete: è il modello ACC-IIDM con i parametri veri, e '
           'serve da limite superiore di riferimento. I nomi sono un tema (le Tartarughe Ninja); '
           'la run porta l\'etichetta "TURTLE POWER!!!".'))
    A(('table', (
        ['Champion', 'Checkpoint', 'Metodo', 'Accuratezza', 'ρ(U·V)', 'Carattere'],
        [[ch, CKPT[ch], METHOD[ch], f'{f2(ACC.loc[ch,"accuracy_pct"])}%',
          f2(EN.loc[ch, 'spectral_radius']), CHARACTER[ch]] for ch in CHAMP]
        + [[ORACLE, 'parametri veri', 'oracolo (ACC-IIDM)', '100%', '-', 'riferimento']],
    )))

    # ---- 3. METODOLOGIA ----
    A(('h1', '3. Metodologia: l\'evaluate a 6-tier'))
    A(('p', 'L\'evaluate è passato da validazione "data-driven" a "physics/network-driven": '
           'misura non solo quanto la rete indovina i numeri, ma come si comporta quando quei '
           'numeri GUIDANO davvero un\'auto, sotto plant fisico realistico e canale V2X imperfetto, '
           'e che aspetto ha la rete come futuro circuito. Le 15 dimensioni sono organizzate in '
           '6 tier:'))
    A(('table', (
        ['Tier', 'Dimensioni (sezioni della run)', 'Cosa misura'],
        [
            ['T0 reporting', '00 Scorecard, 01 Accuratezza', 'identificazione, distribuzioni, metriche continue'],
            ['T1 sicurezza+coda', '02 Sicurezza, 09 Traiettorie, 10 Reachability, 11 Breakdown',
             'SSM estese, scenari di coda, curva di rottura'],
            ['T2 plant+canale', '06 V2X, 07 VehicleDynamics', 'attuatore/attrito/pendenza, PDR/latenza/AoI'],
            ['T3 traffico', '03 String, 12 Mesoscopico, 13 Macroscopico', 'string stability, plotone, diagramma fondamentale'],
            ['T4 identificabilità', '04 Identifiability', 'FIM, equifinalità, causale, naturalisticità'],
            ['T5 FPGA', '05 Quantizzazione, 08 Energia/Spiking', 'Qm.n/po2, energia, salute della rete, ρ'],
        ],
    )))
    A(('h2', '3.1 Il simulatore closed-loop e l\'oracolo'))
    A(('p', 'A ogni passo (Dt=0.1 s) la rete riceve lo stato osservato dell\'ego, predice '
           '[v0, T, s0, a, b], e questi parametri alimentano il controllore ACC-IIDM che calcola '
           'l\'accelerazione; l\'ego avanza e il ciclo si ripete (guida ad anello chiuso, non '
           'identificazione offline). L\'oracolo gira lo stesso loop coi parametri veri: '
           'confrontarli isola l\'effetto dell\'errore di identificazione sul comportamento.'))
    A(('h2', '3.2 Scenari e metriche'))
    A(('p', 'Scenari avversari: following, stop&go, hard-brake, cut-in (realistico ed evitabile), '
           'aggressive cut-in, panic-stop, sinusoidale; l\'accuratezza è inoltre stratificata su '
           '6 famiglie (highway, urban, launch, freeflow, truck, mixed). Le metriche di sicurezza '
           'usano indicatori CONTINUI (surrogate safety measures) che non saturano come il solo '
           'tasso di collisione:'))
    A(('table', (
        ['Metrica', 'Definizione', 'Cosa cattura'],
        [
            ['collision_rate', 'frazione di scenari con gap -> 0', 'sicurezza assoluta'],
            ['brake_margin_min', 'margine di decelerazione residuo (con segno)', 'quanto vicino al limite di frenata'],
            ['min_ttc / min_gap', 'time-to-collision e distanza minimi', 'prossimità al pericolo'],
            ['DRAC / TET / TIT', 'decel. richiesta; tempo e integrale sotto soglia TTC', 'severità ed esposizione'],
            ['impact_dv', 'delta-v ipotetico d\'impatto', 'gravità potenziale'],
            ['rms_jerk / frac_iso', 'strappo RMS; frazione fuori soglia ISO', 'comfort'],
            ['head_to_tail_gain', 'ampiezza coda / testa nel plotone', 'string stability (<1 = stabile)'],
            ['ρ(U·V), dead_frac', 'raggio spettrale ricorrenza; neuroni morti', 'salute e stabilità hardware'],
        ],
    )))
    A(('img', (EQ_SSM, 'Equazione 3.1 — Principali surrogate safety measures (indicatori continui di '
                       'rischio). s = gap [m]; Δv = velocità di avvicinamento (v−v_leader) [m/s]; '
                       'τ = soglia di time-to-collision; 𝟏[·] = indicatore. TTC = time-to-collision; '
                       'DRAC = deceleration rate to avoid a crash; TET = tempo esposto a TTC sotto soglia.')))

    # ---- 4. IDENTIFICAZIONE ----
    A(('h1', '4. Identificazione dei parametri (Tier 0/4)'))
    A(('h2', '4.1 Accuratezza per champion e per parametro'))
    A(('p', f'Donatello (EventProp) è il più accurato ({f2(ACC.loc["Donatello","accuracy_pct"])}%, '
           f'NRMSE media {f3(ACC.loc["Donatello","nrmse_mean"])}), seguito da Michelangelo '
           f'({f2(ACC.loc["Michelangelo","accuracy_pct"])}%) e Leonardo ({f2(ACC.loc["Leonardo","accuracy_pct"])}%). '
           f'Raffaello è l\'anello debole ({f2(ACC.loc["Raffaello","accuracy_pct"])}%): la sua NRMSE '
           f'su v0 è {f3(ACC.loc["Raffaello","nrmse_v0"])}, cioè sbaglia grossolanamente la '
           f'velocità desiderata - un difetto che riemerge nel diagramma fondamentale macro (sezione 7). '
           f'In media EventProp batte BPTT ({ACC_MEAN_EP:.0f}% vs {ACC_MEAN_BP:.0f}%). Il canale più '
           f'facile è s0 per quasi tutti; i più ostici sono v0 e b.'))
    A(('img', (EQ_NRMSE, 'Equazione 4.1 — NRMSE per parametro. p̂ = valore predetto, p = valore vero, '
                         'N = numero di campioni; il denominatore (p_max − p_min) normalizza sul range '
                         'fisico del parametro (0 = perfetto). L\'accuratezza riportata è 1 − NRMSE media.')))
    A(('table', (
        ['Champion', 'NRMSE v0', 'NRMSE T', 'NRMSE s0', 'NRMSE a', 'NRMSE b', 'media', 'accur.'],
        [[ch, f3(ACC.loc[ch, 'nrmse_v0']), f3(ACC.loc[ch, 'nrmse_T']), f3(ACC.loc[ch, 'nrmse_s0']),
          f3(ACC.loc[ch, 'nrmse_a']), f3(ACC.loc[ch, 'nrmse_b']), f3(ACC.loc[ch, 'nrmse_mean']),
          f'{f2(ACC.loc[ch,"accuracy_pct"])}%'] for ch in CHAMP],
    )))
    A(('img', (F_ACC, 'Figura 4.1 - Errore per parametro (sx) e accuratezza complessiva (dx). '
                      'I due champion EventProp (Donatello viola, Michelangelo arancione) hanno NRMSE '
                      'per-canale più uniforme e bassa; Raffaello (rosso) crolla su v0. '
                      'La linea tratteggiata a 100% è l\'oracolo.')))
    A(('h2', '4.2 Dove ogni parametro diventa osservabile (stratificazione)'))
    A(('p', 'La NRMSE stratificata per famiglia di scenario mostra QUANDO ciascun parametro è '
           'osservabile: v0 richiede tratti di free-flow/highway (Raffaello lo sbaglia proprio in '
           'urban, dove v0 non è eccitato), a emerge nei transitori di accelerazione (launch), b '
           'nelle frenate. È la firma della stessa non-identificabilità strutturale del modello '
           'car-following già nota dallo studio.'))
    A(('img', (R['nrmse_stratified.png'],
               'Figura 4.2 - NRMSE per parametro x famiglia di scenario, per ciascun champion. '
               'Le celle più scure segnano dove un parametro resta poco osservabile (es. v0 in '
               'urban per Raffaello, b in freeflow per quasi tutti).')))
    A(('h2', '4.3 Identificabilità strutturale (FIM ed equifinalità)'))
    A(('p', f'La matrice di Fisher (FIM) ha rango pieno ({int(_fimnum("rank_FIM"))} su 5): tutti i '
           f'parametri sono in linea di principio identificabili, nessuno "sotto-eccitato". Ma il '
           f'numero di condizionamento è enorme (~{_fimnum("cond_mean")/1e9:.1f} miliardi): il problema '
           f'è fortemente mal-condizionato ("sloppy"), con un insieme di equifinalità stimato in '
           f'~{int(_fimnum("n_equivalent"))} combinazioni di parametri che producono traiettorie quasi '
           f'indistinguibili. Il parametro localmente meno identificabile risulta {FIM["least_identifiable"]}, '
           f'il più identificabile {FIM["most_identifiable"]}. In pratica: più set di parametri '
           f'spiegano ugualmente bene la stessa guida - ecco perché due champion possono avere '
           f'NRMSE diverse e comportamenti di guida simili.'))
    A(('img', (EQ_FIM, 'Equazione 4.2 — Matrice di Fisher e numero di condizionamento. J = jacobiano '
                       'delle predizioni rispetto ai 5 parametri; σ_max, σ_min = valori singolari '
                       'estremi della FIM. κ grande = problema mal-condizionato (sloppy): molti set di parametri '
                       'producono traiettorie quasi indistinguibili.')))
    A(('img', (R['fim.png'], 'Figura 4.3 - Analisi di identificabilità via FIM: sensibilità per '
                             'parametro e struttura di correlazione (il mal-condizionamento è la '
                             'ragione fisica dell\'equifinalità).')))
    A(('h2', '4.4 Sensibilità causale e naturalisticità'))
    A(('p', f'La sensibilità causale (risposta delle predizioni a interventi controllati sul '
           f'leader) conferma che T reagisce alla variazione di velocità del leader in tutti i '
           f'champion; le risposte di a/b differiscono per champion (Donatello mostra una firma '
           f'causale distinta su s0/b). Sul realismo, il test di naturalisticità (distanza KS tra '
           f'le distribuzioni di time-gap e jerk della rete e quelle umane) incorona Leonardo come '
           f'il più "umano" (KS time-gap {f3(NAT.loc["Leonardo","ks_time_gap"])}, KS jerk '
           f'{f3(NAT.loc["Leonardo","ks_jerk"])}); nessun champion, però, rientra pienamente nella '
           f'banda naturalistica di riferimento (within_floor = falso per tutti) - un limite residuo, '
           f'non un difetto di sicurezza.'))
    A(('img', (EQ_KS, 'Equazione 4.3 — Distanza di Kolmogorov-Smirnov tra la distribuzione della rete e '
                      'quella umana (per time-gap e jerk). F = funzione di ripartizione empirica; '
                      'D_KS ∈ [0,1], con 0 = distribuzioni identiche.')))
    A(('img', (R['causal.png'], 'Figura 4.4 - Sensibilità causale: quanto la stima di ciascun '
                                'parametro risponde a interventi su velocità leader, |delta-v| e '
                                '|accelerazione|.')))
    A(('img', (R['naturalisticity.png'], 'Figura 4.5 - Naturalisticità/calibrazione: distanza dalle '
                                         'distribuzioni umane di time-gap e jerk. Leonardo è il più '
                                         'naturale; nessuno è ancora dentro la banda di riferimento.')))

    # ---- 5. SICUREZZA ----
    A(('h1', '5. Sicurezza closed-loop (Tier 0/1)'))
    A(('h2', '5.1 Verdetto: sicuri come l\'oracolo'))
    A(('p', f'In anello chiuso i 4 champion collidono quanto l\'oracolo: il tasso di collisione va '
           f'da {f2(SAF.loc["Raffaello","collision_rate"]*100)}% (Raffaello) a '
           f'{f2(SAF.loc["Donatello","collision_rate"]*100)}% (Donatello), contro '
           f'{f2(SAF.loc[ORACLE,"collision_rate"]*100)}% dell\'oracolo. Il residuo non è la rete: '
           f'deriva da geometrie di cut-in fisicamente inevitabili (vedi curva di rottura, 6.3) in '
           f'cui anche l\'oracolo collide. Sul TTC minimo tutti e 4 i champion sono pari o superiori '
           f'all\'oracolo ({f3(SAF.loc[ORACLE,"min_ttc"])} s), quindi più cauti. Sul margine di '
           f'frenata minimo Leonardo ({f2(SAF.loc["Leonardo","brake_margin_min"])} m) e Michelangelo '
           f'({f2(SAF.loc["Michelangelo","brake_margin_min"])} m) superano l\'oracolo '
           f'({f2(SAF.loc[ORACLE,"brake_margin_min"])} m), mentre Raffaello '
           f'({f2(SAF.loc["Raffaello","brake_margin_min"])} m) e Donatello '
           f'({f2(SAF.loc["Donatello","brake_margin_min"])} m) restano appena sotto: differenza '
           f'piccola, che non intacca il tasso di collisione (allineato all\'oracolo). Nota: Leonardo '
           f'mostra un picco isolato di DRAC ({f2(SAF.loc["Leonardo","max_DRAC"])} m/s2) in un singolo '
           f'scenario - un caso-limite da tenere d\'occhio, non un pattern.'))
    A(('table', (
        ['Sorgente', 'collis.', 'brake margin', 'min TTC', 'min gap', 'impact dv', 'max DRAC', 'rms jerk'],
        [[s, f'{f2(SAF.loc[s,"collision_rate"]*100)}%', f3(SAF.loc[s, 'brake_margin_min']),
          f3(SAF.loc[s, 'min_ttc']), f3(SAF.loc[s, 'min_gap']), f3(SAF.loc[s, 'impact_dv']),
          f2(SAF.loc[s, 'max_DRAC']), f3(SAF.loc[s, 'rms_jerk'])] for s in SRC],
    )))
    A(('img', (F_SAFE, 'Figura 5.1 - Sicurezza cross-champion. I 4 champion (colore) sono allineati '
                       'o migliori dell\'oracolo (grigio) su collisione, margine di frenata, TTC e '
                       'delta-v d\'impatto.')))
    A(('img', (R['delta_vs_oracle.png'], 'Figura 5.2 - Delta di ciascuna metrica di sicurezza rispetto '
                                         'all\'oracolo: valori dal lato "più sicuro" confermano il '
                                         'profilo conservativo dei champion.')))
    A(('img', (R['ssm_distribution.png'], 'Figura 5.3 - Distribuzioni delle surrogate safety measures '
                                          '(non solo la media): le code restano lontane dalle soglie '
                                          'critiche.')))
    A(('img', (R['per_scenario_min_gap.png'], 'Figura 5.4 - Gap minimo per tipologia di scenario: il '
                                              'cut-in è il più stressante, ma il gap resta sopra la '
                                              'linea di collisione tranne nelle geometrie impossibili.')))
    A(('img', (R['comfort_iso.png'], 'Figura 5.5 - Comfort ISO (accelerazione/jerk): i champion sono '
                                     'comparabili all\'oracolo, con accelerazioni tendenzialmente più dolci.')))
    A(('h2', '5.2 Traiettorie closed-loop'))
    A(('p', 'Il modo più diretto di osservare la guida è la traiettoria in anello chiuso: gap, '
           'velocità e accelerazione dell\'ego nel tempo, per ciascun champion sovrapposto '
           'all\'oracolo. La run produce le tracce per i 5 scenari (cut-in, hard-brake, stop&go, '
           'panic-stop, aggressive cut-in) in results/evaluate/v3_TURTLE_POWER!!!/09_Trajectories/. '
           'Se ne riportano due rappresentative: nel cut-in il gap crolla al taglio e tutte le varianti '
           'lo recuperano dolcemente senza toccare la linea di collisione; nell\'hard-brake l\'ego '
           'insegue la decelerazione del leader mantenendo il margine.'))
    A(('img', (R['traj_cut_in.png'], 'Figura 5.6 - Traiettorie closed-loop nel cut-in: gap, velocità '
                                     'e accelerazione. Il gap si recupera senza collisione (salvo le '
                                     'geometrie impossibili, dove collide anche l\'oracolo).')))
    A(('img', (R['traj_hard_brake.png'], 'Figura 5.7 - Traiettorie closed-loop nell\'hard-brake: '
                                         'l\'ego segue la frenata del leader mantenendo il margine di '
                                         'sicurezza.')))

    # ---- 6. ROBUSTEZZA FISICA ----
    A(('h1', '6. Robustezza fisica e curva di rottura (Tier 1)'))
    A(('h2', '6.1 Plant: asciutto, bagnato, ghiaccio'))
    A(('p', f'Ripetendo gli scenari sotto attrito degradato, la collisione sale con la strada, non '
           f'con la rete: da ~{f2(PLANT.loc["Donatello","collision_ideale"]*100)}% su asciutto a '
           f'~{f2(PLANT.loc["Donatello","collision_bagnato"]*100)}% su bagnato fino a '
           f'~{f2(PLANT.loc["Donatello","collision_ghiaccio"]*100)}% su ghiaccio - e l\'oracolo si '
           f'comporta uguale ({f2(PLANT.loc[ORACLE,"collision_ghiaccio"]*100)}% su ghiaccio). Il '
           f'~60% di collisioni su ghiaccio è un limite fisico (coefficiente d\'attrito troppo basso '
           f'per fermarsi in tempo), non un errore della SNN; anzi, su ghiaccio i champion mantengono '
           f'un margine di frenata leggermente migliore dell\'oracolo.'))
    A(('img', (R['plant.png'], 'Figura 6.1 - Collisione e margine di frenata su asciutto/bagnato/ghiaccio. '
                              'La degradazione è guidata dall\'attrito ed è identica tra champion e oracolo.')))
    A(('h2', '6.2 Reachability e curva di rottura'))
    A(('p', 'L\'analisi di reachability (gap minimo di sicurezza al variare del delta-v iniziale) '
           'mostra un inviluppo praticamente sovrapposto a quello dell\'oracolo, marginalmente più '
           'conservativo ai delta-v alti (es. a delta-v=15 m/s i champion chiedono ~17-18 m contro i '
           '16.7 m dell\'oracolo). La curva di rottura conferma il punto centrale sulla sicurezza: '
           'sotto panic-braking fino a 10 m/s2 la collisione resta a zero per tutti; nel cut-in la '
           'collisione cresce al restringersi del gap ESATTAMENTE come per l\'oracolo. La rete si '
           'rompe solo dove si rompe la fisica.'))
    A(('img', (R['reachability.png'], 'Figura 6.2 - Inviluppo di gap-sicuro vs delta-v iniziale: '
                                      'champion (colore) ~ oracolo (grigio), leggermente più cauti.')))
    A(('img', (R['breakdown.png'], 'Figura 6.3 - Curva di rottura: collisione vs severità '
                                   '(panic-decel e gap di cut-in). La frontiera dei champion coincide '
                                   'con quella dell\'oracolo.')))

    # ---- 7. TRAFFICO ----
    A(('h1', '7. Traffico: micro -> meso -> macro (Tier 3)'))
    A(('h2', '7.1 String stability (singolo veicolo)'))
    A(('p', f'Il guadagno testa->coda è <1 per tutti i champion (da '
           f'{f2(SS.loc["Leonardo","head_to_tail"])} a {f2(SS.loc["Donatello","head_to_tail"])}), '
           f'quindi le perturbazioni si smorzano. Nessuno è strettamente monotono come l\'ideale; '
           f'Michelangelo mostra un picco di amplificazione transitoria a certe frequenze '
           f'(peak_gain {f2(SS.loc["Michelangelo","peak_gain"])}) pur restando globalmente stabile.'))
    A(('img', (EQ_STRING, 'Equazione 7.1 — Guadagno testa→coda (string stability). s_1, s_N = '
                          'perturbazione del gap del primo e dell\'ultimo veicolo del plotone; il '
                          'plotone è string-stable se G_h2t < 1 (le perturbazioni si smorzano lungo la '
                          'catena).')))
    A(('h2', '7.2 Mesoscopico: plotone di 12 veicoli'))
    A(('p', f'In un plotone in catena di 12 veicoli, tutti i champion sono string-stable a livello '
           f'testa->coda (gain {f2(MESO_GMIN)}-'
           f'{f2(MESO_GMAX)}, tutti <1) e nessuno collide; l\'onda in '
           f'testa si smorza lungo la catena. È il risultato di traffico più importante: i 5 '
           f'numeri predetti, propagati su una fila di veicoli, non generano stop-and-go artificiali.'))
    A(('img', (R['meso_gain.png'], 'Figura 7.1 - Guadagno per veicolo lungo il plotone: tutte le curve '
                                   '<1 e decrescenti = catena stabile.')))
    A(('img', (R['meso_spacetime.png'], 'Figura 7.2 - Heatmap spazio-tempo della velocità nel plotone: '
                                        'la perturbazione iniziale si attenua a valle.')))
    A(('h2', '7.3 Macroscopico: diagramma fondamentale'))
    A(('p', f'Sul livello macro (simulazione ad anello -> diagramma fondamentale flusso-densità) '
           f'emerge in modo netto l\'effetto dell\'errore di identificazione. Michelangelo, Leonardo '
           f'e Donatello producono velocità di free-flow plausibili '
           f'({f2(MACRO.loc["Leonardo","v_free_km_h"])}-{f2(MACRO.loc["Michelangelo","v_free_km_h"])} km/h, '
           f'vicine ai {f2(MACRO.loc[ORACLE,"v_free_km_h"])} km/h dell\'oracolo), mentre Raffaello - '
           f'che sbaglia v0 - gonfia la free-flow a {f2(MACRO.loc["Raffaello","v_free_km_h"])} km/h e '
           f'con essa la capacità ({int(MACRO.loc["Raffaello","capacity_veh_h"])} veic/h contro i '
           f'~{int(MACRO.loc[ORACLE,"capacity_veh_h"])} dell\'oracolo): il diagramma fondamentale ne '
           f'esce distorto. L\'insorgenza dell\'instabilità stop-and-go (densità critica) è '
           f'invece uniforme tra i modelli. Il livello macro è riportato con l\'avvertenza '
           f'sull\'artefatto v0 di Raffaello.'))
    A(('img', (EQ_FD, 'Equazione 7.2 — Diagramma fondamentale del traffico. ρ = densità [veicoli/km]; '
                      'v(ρ) = velocità media in funzione della densità; q = flusso [veicoli/h]. La '
                      'curva q(ρ) sintetizza capacità e densità critica.')))
    A(('img', (R['macro_fd.png'], 'Figura 7.3 - Diagramma fondamentale (flusso vs densità). La curva '
                                  'di Raffaello è spostata in alto per la sovrastima di v0; gli altri '
                                  'champion seguono l\'oracolo.')))

    # ---- 8. V2X ----
    A(('h1', '8. Robustezza V2X (Tier 2)'))
    A(('h2', '8.1 Il "hold-last-CAM" maschera la perdita di pacchetti'))
    A(('p', f'Il canale V2X è modellato in modo realistico: probabilità di consegna (PDR), '
           f'latenza, jitter, perdite a raffica (Gilbert-Elliott), blackout, con tracciamento '
           f'dell\'Age-of-Information (AoI). Quando un pacchetto CAM manca, la strategia di default '
           f'"hold-last" mantiene l\'ultimo stato ricevuto (zero-order hold). Confrontando le '
           f'strategie: con hold-last (o dead-reckoning) la collisione resta al livello nominale '
           f'(~{f2(V2X[(V2X.champion=="Donatello")&(V2X.axis=="hold_mode")&(V2X.val=="hold_last")].collision_rate.iloc[0]*100)}%); '
           f'ma in modalità "blind" - la rete lasciata sola, senza alcun handler di perdita - la '
           f'collisione ESPLODE a ~'
           f'{f2(V2X[(V2X.champion=="Donatello")&(V2X.axis=="hold_mode")&(V2X.val=="blind")].collision_rate.iloc[0]*100)}%. '
           f'Lettura onesta: la robustezza alla perdita di pacchetti osservata NON è una proprietà '
           f'intrinseca della SNN, ma dell\'handler hold-last che le sta davanti. La rete da sola non '
           f'è robusta al packet-loss; il livello di canale la protegge.'))
    A(('img', (F_V2X, 'Figura 8.1 - Sinistra: collisione per strategia di gestione perdita '
                      '(hold-last/dead-reckon/blind); "blind" rivela la fragilità della rete nuda. '
                      'Destra: degrado sotto stress di canale (PDR/latenza tollerati, canale pessimo e '
                      'blackout costosi).')))
    A(('img', (R['v2x_holdmode.png'], 'Figura 8.2 - Dettaglio per champion delle tre strategie di '
                                      'gestione della perdita.')))
    A(('img', (R['v2x_aoi.png'], 'Figura 8.3 - Age-of-Information: l\'età dell\'ultimo dato ricevuto '
                                 'cresce con latenza e blackout, spiegando il degrado.')))

    # ---- 9. PROFILO FPGA ----
    A(('h1', '9. Profilo FPGA: quantizzazione, energia, salute della rete (Tier 5)'))
    A(('callout', 'Questa sezione è il SOMMARIO del profilo FPGA nel contesto dell\'evaluate a 6-tier: '
                  'i tre findings chiave (quantizzazione fixed-point, energia, discriminante di stabilità). '
                  'Il profilo hardware COMPLETO — readiness/scorecard, pesi po2, fixed-point, spiking, energia, '
                  'timing/WCET, risorse/DSE, SEU, I/O-HIL, thermal (45 figure su 10 sezioni) — è nel documento '
                  'dedicato FPGA_REPORT (Fase A pre-silicio).'))
    A(('h2', '9.1 Quantizzazione: fixed-point e potenze-di-due'))
    A(('p', f'La rete tollera una quantizzazione aggressiva. In virgola fissa l\'errore di '
           f'identificazione resta praticamente invariato fino a 2 bit di parte frazionaria '
           f'(es. Donatello: {f3(QNT[(QNT.champion=="Donatello")&(QNT["mode"]=="fixed")&(QNT.frac_bits=="float")].id_err_mean.iloc[0])} '
           f'in float -> {f3(QNT[(QNT.champion=="Donatello")&(QNT["mode"]=="fixed")&(QNT.frac_bits=="2")].id_err_mean.iloc[0])} '
           f'a 2 bit). Con pesi a potenze-di-due (po2, che trasformano la moltiplicazione in uno '
           f'shift-add) l\'errore è insensibile al numero di bit (dipende dall\'esponente, non dalla '
           f'mantissa) e, soprattutto, viene ASSORBITO dal training: il "peso di 2" è già quello '
           f'nativo. L\'ablazione dei pesi mostra delta_qat_absorbed <= 0 per 3 champion su 4 '
           f'(accendere po2 non peggiora, anzi migliora), mentre Raffaello subisce un piccolo '
           f'aumento (+{f2(QAB.loc["Raffaello","delta_qat_absorbed"])}).'))
    A(('img', (F_QUANT, 'Figura 9.1 - Sinistra: errore vs bit in fixed-point (piatto fino a 2 bit); '
                        'le x segnano la variante po2. Destra: il QAT assorbe i pesi po2 (barre verdi '
                        '= po2 non peggiora l\'errore).')))
    A(('h2', '9.2 Energia'))
    A(('p', f'Il vantaggio energetico per inferenza è modesto: da '
           f'{f2(min(EN.loc[c,"advantage_x"] for c in CHAMP))}x a '
           f'{f2(max(EN.loc[c,"advantage_x"] for c in CHAMP))}x rispetto a una ANN densa equivalente. '
           f'Il vantaggio non deriva dalla sparsità: queste reti sparano ~{f2(SPK_MIN)}-{f2(SPK_MAX)}%, '
           f'non l\'1-2% talvolta attribuito alle SNN, e le operazioni sinaptiche (SynOps) eguagliano o '
           f'superano i MAC dell\'ANN. A parità di costo per operazione la SNN sarebbe in svantaggio; il '
           f'guadagno viene dal minor costo unitario di un accumulo (AC) rispetto a un MAC (modello di '
           f'Horowitz 2014), amplificato su FPGA dai pesi po2 (AC = shift+add) e dallo 0 DSP. Gli '
           f'EventProp non vincono sull\'energia: Donatello (il più contrattivo) ha anzi il vantaggio più '
           f'basso ({f2(EN.loc["Donatello","advantage_x"])}x) perché spara di più '
           f'({f2(EN.loc["Donatello","mean_spike_rate_pct"])}%); il loro vantaggio FPGA sta altrove, in '
           f'ρ<1 e 0 neuroni morti (§9.3). Il profilo op-count dettagliato e la stima energetica per '
           f'architettura sono in FPGA_REPORT.'))
    A(('img', (R['energy.png'], 'Figura 9.2 - Energia per inferenza e conteggio operazioni per champion.')))
    A(('h2', '9.3 Salute della rete e il discriminante di stabilità'))
    A(('p', f'Qui si consuma la differenza hardware tra le due famiglie. I champion EventProp hanno '
           f'ZERO neuroni morti e una ricorrenza CONTRATTIVA (ρ '
           f'{f2(EN.loc["Donatello","spectral_radius"])} per Donatello, '
           f'{f2(EN.loc["Michelangelo","spectral_radius"])} per Michelangelo); i champion BPTT hanno '
           f'~{f2(EN.loc["Raffaello","dead_frac"]*100)}% di neuroni morti e una ricorrenza ESPANSIVA '
           f'(ρ {f2(EN.loc["Leonardo","spectral_radius"])} per Leonardo, '
           f'{f2(EN.loc["Raffaello","spectral_radius"])} per Raffaello). Su FPGA, ρ<1 garantisce '
           f'uno stato limitato in aritmetica a virgola fissa (l\'errore di quantizzazione si smorza), '
           f'mentre ρ>1 espone al rischio di amplificazione/overflow e richiederebbe guardband e '
           f'saturazione esplicita. È il motivo tecnico per cui EventProp è più "FPGA-friendly", '
           f'e per cui Donatello - contrattivo al massimo e più accurato - è il candidato naturale '
           f'al deploy.'))
    A(('img', (F_FPGA, 'Figura 9.3 - Il discriminante FPGA in un solo grafico: raggio spettrale (x) vs '
                       'accuratezza (y), area del marker ~ vantaggio energetico. La zona verde (ρ<1) '
                       'è quella sicura in fixed-point; Donatello e Michelangelo (cerchi) ci stanno, i '
                       'BPTT (quadrati) no.')))
    A(('img', (R['raster_Donatello.png'], 'Figura 9.4a - Raster/attività di Donatello (EventProp): '
                                          'attività distribuita su tutti i neuroni, NESSUN neurone spento '
                                          '(0 morti) -- nota: non è iper-sparsa, spara ~19%.')))
    A(('img', (R['raster_Raffaello.png'], 'Figura 9.4b - Raster di Raffaello (BPTT): ~31% di neuroni MAI '
                                          'attivi (capacità sprecata) -- la differenza con EventProp è '
                                          'l\'utilizzo dei neuroni, non il tasso di spike.')))
    A(('img', (R['showcase_Donatello.png'], 'Figura 9.5 - Vetrina di Donatello: identificazione, guida '
                                            'closed-loop e spiking su un episodio reale. La run contiene '
                                            'la vetrina per tutti e 4 i champion più una GIF "in diretta" '
                                            '(14_Showcase/showcase_*.png e showcase_live_Raffaello.gif).')))

    # ---- 10. VERDETTO ----
    A(('h1', '10. Verdetto consolidato e raccomandazione di deploy'))
    A(('table', (
        ['Champion', 'Sicurezza', 'Accuratezza', 'FPGA (ρ, morti)', 'Sintesi'],
        [
            ['Raffaello (BPTT)', 'ok (~oracolo)', f'{f2(ACC.loc["Raffaello","accuracy_pct"])}% (v0 mal-id)',
             f'ρ {f2(EN.loc["Raffaello","spectral_radius"])}, 31% morti', 'sconsigliato (instabile + v0)'],
            ['Leonardo (BPTT)', 'ok, più umano', f'{f2(ACC.loc["Leonardo","accuracy_pct"])}%',
             f'ρ {f2(EN.loc["Leonardo","spectral_radius"])}, 31% morti', 'ottimo software, ma espansivo'],
            ['Donatello (EventProp)', 'ok (~oracolo)', f'{f2(ACC.loc["Donatello","accuracy_pct"])}% (best)',
             f'ρ {f2(EN.loc["Donatello","spectral_radius"])}, 0 morti', 'CANDIDATO DEPLOY'],
            ['Michelangelo (EventProp)', 'ok', f'{f2(ACC.loc["Michelangelo","accuracy_pct"])}%',
             f'ρ {f2(EN.loc["Michelangelo","spectral_radius"])}, 0 morti', 'runner-up deploy'],
        ],
    )))
    A(('p', 'Raccomandazione. Per il deploy FPGA la scelta è Donatello: unisce la migliore '
           'accuratezza, una ricorrenza fortemente contrattiva (ρ~0.05, la più sicura in '
           'fixed-point), zero neuroni morti e sicurezza pari all\'oracolo. Michelangelo è il '
           'runner-up (contrattivo, buona accuratezza). Leonardo resta il migliore sul piano '
           'software (più umano/naturale) ma la sua ricorrenza espansiva (ρ>1) imporrebbe '
           'guardband in hardware. Raffaello è sconsigliato: mis-identifica v0 (distorce il macro), '
           'è il più espansivo (ρ~3) e ha il 31% di neuroni morti.'))
    A(('callout', 'In una frase: lo studio EventProp si chiude confermando il fronte di Pareto - '
                  'BPTT vince di poco sulla fisica, EventProp vince su accuratezza, stabilità e '
                  'idoneità al silicio - e indica Donatello (EventProp) come la rete da portare su FPGA.'))

    # ---- 11. LIMITI E PROSSIMI PASSI ----
    A(('h1', '11. Limiti residui e prossimi passi'))
    A(('p', 'Limiti onesti di questa validazione: (1) nessun champion rientra ancora pienamente nella '
           'banda naturalistica umana (within_floor falso); (2) il problema resta mal-condizionato '
           '(cond ~1.6e9, equifinalità ~29 set) - più parametri spiegano la stessa guida; '
           '(3) i champion BPTT hanno neuroni morti e ricorrenza espansiva; (4) le collisioni su '
           'ghiaccio e nei cut-in impossibili sono limiti fisici del plant, non correggibili dalla '
           'rete; (5) la robustezza V2X osservata dipende dall\'handler hold-last, non dalla rete '
           'nuda. Il livello macro è ora riportato ma con l\'avvertenza sull\'artefatto v0 di '
           'Raffaello.'))
    A(('p', 'Prossimi passi (fase FPGA). La presentazione della valutazione hardware è già '
           'progettata e bloccata per la Fase A "software_now" (pre-silicio) in '
           'document/FPGA_EVALUATE_DESIGN.md (il progetto) e il quadro tecnico in '
           'document/FPGA_EVALUATION_FRAMEWORK.md; il deliverable ESEGUITO di quella Fase A — la '
           'FPGA-evaluate profonda (45 figure su 10 sezioni) — è il FPGA_REPORT. Restano aperte la Fase B (HDL) e la Fase C '
           '(board): la conversione della SNN in HDL non è immediata (i tool tipo FINN non '
           'supportano il neurone ALIF-PINN; la strada probabile è import in Simulink + HDL Coder), '
           'ed è documentata come problema aperto. Su questo evaluate, il candidato Donatello è il '
           'punto di partenza del percorso di deploy.'))

    # ---- 12. RIPRODUCIBILITA' ----
    A(('h1', '12. Riproducibilità e mappa dei file'))
    A(('table', (
        ['Cosa', 'Dove'],
        [
            ['Risultati evaluate v3 (15 sezioni, csv+png)', 'results/evaluate/v3_TURTLE_POWER!!!/'],
            ['Notebook champion', 'Eval_v3_TURTLE_POWER.ipynb'],
            ['Builder del notebook', 'scripts/_build_eval_v3_notebook.py'],
            ['Verifica manifest post-run', 'scripts/verify_eval_v3.py'],
            ['Questo report (generatore)', 'scripts/build_validation_report_v3.py'],
            ['Simulatore closed-loop + plant/canale', 'utils/closed_loop_eval.py'],
            ['Identificazione closed-loop + V2X sweep', 'scripts/closed_loop_identify.py'],
            ['Identificabilità (FIM/causale/...)', 'utils/identifiability.py'],
            ['Quantizzazione (Qm.n/po2)', 'utils/quantize.py'],
            ['Diagnostica rete (dead/ρ/raster)', 'utils/net_diagnostics.py'],
            ['Documento-master dello studio', 'document/EVENTPROP_STATUS.md'],
            ['Design valutazione FPGA (progetto)', 'document/FPGA_EVALUATE_DESIGN.md / FPGA_EVALUATION_FRAMEWORK.md'],
            ['Profilo FPGA profondo — Fase A (45 figure, 10 sez.)', 'document/FPGA_REPORT.md / .pdf'],
            ['Architettura/fisica (come funziona)', 'document/HOW_IT_WORKS_v3.md / GLOSSARY.md'],
        ],
    )))
    A(('p', 'Le figure-chiave di questo report (accuratezza, discriminante FPGA, sicurezza, '
           'quantizzazione, V2X) sono RICOSTRUITE dai CSV eseguendo '
           '"python scripts/build_validation_report_v3.py". Le figure di dettaglio (stratificazione, '
           'FIM, causale, naturalisticità, traiettorie, plant, reachability, breakdown, string/meso/'
           'macro, raster, showcase) sono RIUSATE dai PNG genuini prodotti dal notebook v3. La run '
           'completa contiene 46 figure; qui ne è riportato un sottoinsieme curato - il resto è '
           'nelle 15 sottocartelle dei risultati.'))

    # ---- 13. RIFERIMENTI ----
    A(('h1', '13. Riferimenti'))
    A(('table', (
        ['Riferimento', 'Tema'],
        [
            ['Greenshields, B.D. (1935). A study of traffic capacity. Highway Research Board Proceedings 14, 448–477.', 'Diagramma fondamentale (§7.3)'],
            ['Massey, F.J. (1951). The Kolmogorov-Smirnov test for goodness of fit. J. American Statistical Association 46(253), 68–78.', 'Distanza di Kolmogorov-Smirnov (§4.4)'],
            ['Gilbert, E.N. (1960). Capacity of a burst-noise channel. Bell System Technical Journal 39, 1253–1265.', 'Modello Gilbert-Elliott (§8.1)'],
            ['Hayward, J.C. (1972). Near-miss determination through use of a scale of danger. Highway Research Record 384, 24–34.', 'Time-to-collision / SSM (§3.2)'],
            ['ISO 2631-1 (1997). Mechanical vibration and shock — Evaluation of human exposure to whole-body vibration. ISO, Ginevra.', 'Soglia comfort/jerk (§5.1)'],
            ['Transtrum, M.K., Machta, B.B., Sethna, J.P. (2011). Geometry of nonlinear least squares with applications to sloppy models and optimization. Physical Review E 83, 036701.', 'FIM, modelli sloppy (§4.3)'],
            ['Kaul, S., Yates, R., Gruteser, M. (2012). Real-time status: how often should one update? IEEE INFOCOM, 2731–2735.', 'Age-of-Information (§8.1)'],
            ['Treiber, M., Kesting, A. (2013). Traffic Flow Dynamics: Data, Models and Simulation. Springer.', 'ACC-IIDM, calibrazione, string stability (§1, §4, §7)'],
            ['Horowitz, M. (2014). Computing\'s energy problem (and what we can do about it). IEEE Int. Solid-State Circuits Conf. (ISSCC), 10–14.', 'Energia AC/MAC (§9.2)'],
            ['Bellec, G., Salaj, D., Subramoney, A., Legenstein, R., Maass, W. (2018). Long short-term memory and learning-to-learn in networks of spiking neurons. Advances in Neural Information Processing Systems (NeurIPS) 31.', 'Neurone ALIF (§2.1)'],
            ['Neftci, E.O., Mostafa, H., Zenke, F. (2019). Surrogate gradient learning in spiking neural networks. IEEE Signal Processing Magazine 36(6), 51–63.', 'BPTT+surrogate (§2.2)'],
            ['Raissi, M., Perdikaris, P., Karniadakis, G.E. (2019). Physics-informed neural networks: a deep learning framework for solving forward and inverse problems involving nonlinear PDEs. J. Computational Physics 378, 686–707.', 'Loss PINN (§2.1)'],
            ['ETSI EN 302 637-2 (2019). Intelligent Transport Systems; Cooperative Awareness Basic Service (CAM). ETSI.', 'V2X / CAM (§8.1)'],
            ['Wunderlich, T.C., Pehle, C. (2021). Event-based backpropagation can compute exact gradients for spiking neural networks. Scientific Reports 11, 12829.', 'EventProp (§2.2)'],
            ['Mishchenko, K., Defazio, A. (2023). Prodigy: an expeditiously adaptive parameter-free learner. arXiv:2306.06101.', 'Ottimizzatore Prodigy (§2.3)'],
        ],
    )))
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
        elif kind == 'p':
            L.append(b + '\n')
        elif kind == 'callout':
            L.append(f"> **Nota.** {b}\n")
        elif kind == 'table':
            headers, rows = b
            L.append('| ' + ' | '.join(headers) + ' |')
            L.append('|' + '|'.join(['---'] * len(headers)) + '|')
            for r in rows:
                L.append('| ' + ' | '.join(str(x) for x in r) + ' |')
            L.append('')
        elif kind == 'img':
            path, capt = b
            rel = os.path.relpath(path, DOCDIR).replace('\\', '/')
            L.append(f"![{capt}]({rel})")
            L.append(f"*{capt}*\n")
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))
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

    ss = getSampleStyleSheet()
    body = ParagraphStyle('body', parent=ss['Normal'], fontName='DJ', fontSize=9.5,
                          leading=14, spaceAfter=6, alignment=4)
    h1 = ParagraphStyle('h1', fontName='DJ-B', fontSize=16, leading=20, spaceBefore=14,
                        spaceAfter=8, textColor=colors.HexColor('#1a3c6e'))
    h2 = ParagraphStyle('h2', fontName='DJ-B', fontSize=12.5, leading=16, spaceBefore=10,
                        spaceAfter=5, textColor=colors.HexColor('#26527a'))
    cap = ParagraphStyle('cap', parent=body, fontName='DJ', fontSize=8, leading=11,
                         textColor=colors.HexColor('#555555'), spaceAfter=12, alignment=4)
    callout = ParagraphStyle('callout', parent=body, fontName='DJ', fontSize=9.5,
                             leading=14, leftIndent=8, borderPadding=6,
                             backColor=colors.HexColor('#eef3fa'),
                             borderColor=colors.HexColor('#9bb8d8'), borderWidth=0.6,
                             spaceBefore=4, spaceAfter=10)

    def esc(s):
        s = str(s)
        # grassetto markdown -> tag reportlab, poi escape del resto
        import re
        s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
        return s

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
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5fa')]),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#b9c6d6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(Spacer(1, 2)); story.append(t); story.append(Spacer(1, 8))

    for kind, *rest in doc:
        b = rest[0] if rest else None
        if kind == 'cover':
            story.append(Spacer(1, 3.2 * cm))
            story.append(Paragraph(esc(b['title']), ParagraphStyle('ct', fontName='DJ-B',
                         fontSize=23, leading=29, textColor=colors.HexColor('#1a3c6e'), alignment=1)))
            story.append(Spacer(1, 0.5 * cm))
            story.append(Paragraph(esc(b['subtitle']), ParagraphStyle('cs', fontName='DJ',
                         fontSize=12, leading=17, textColor=colors.HexColor('#444444'), alignment=1)))
            story.append(Spacer(1, 1.4 * cm))
            story.append(HRFlowable(width='60%', thickness=1, color=colors.HexColor('#9bb8d8')))
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
        elif kind == 'p':
            story.append(Paragraph(esc(b), body))
        elif kind == 'callout':
            story.append(Paragraph('<b>Nota.</b> ' + esc(b), callout))
        elif kind == 'table':
            make_table(*b)
        elif kind == 'img':
            add_image(*b)

    def footer(canvas, docx):
        canvas.saveState()
        canvas.setFont('DJ', 7.5)
        canvas.setFillColor(colors.HexColor('#888888'))
        canvas.drawString(2 * cm, 1.1 * cm, 'CF_FSNN — Report di Validazione (v3)')
        canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f'pag. {docx.page}')
        canvas.restoreState()

    pdf = SimpleDocTemplate(outpath, pagesize=A4, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            title='CF_FSNN Report di Validazione v3')
    pdf.build(story, onFirstPage=footer, onLaterPages=footer)
    print('  scritto', outpath)


print('[2/4] render markdown...')
render_md(DOC, os.path.join(DOCDIR, 'VALIDATION_REPORT_v3.md'))
print('[3/4] render pdf...')
render_pdf(DOC, os.path.join(DOCDIR, 'VALIDATION_REPORT_v3.pdf'))
print('[4/4] fatto.')
