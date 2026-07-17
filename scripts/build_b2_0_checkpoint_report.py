"""build_b2_0_checkpoint_report.py — REPORT INTERMEDIO Fase B2.0 (validazione RTL) — .md + .pdf da sorgente unica.

Checkpoint della Fase B2.0: validazione a livello RTL (testbench in Vivado xsim) dei due blocchi del
controllore car-following — la SNN (Donatello_Champion) e il controllore completo SNN+ACC-IIDM
(Donatello_ACC_IIDM_M). NON e' il report finale (quello seguira' l'ottimizzazione 2b e la validazione
completa 2c sulla versione ottimizzata): fotografa lo stato della VERSIONE ATTUALE, validata sul dataset
ridotto, con la metodologia e i risultati reali.

Grounding: i numeri dei cancelli e della deriva provengono dai run di questa fase, riportati in
document/HDL_PHASE.md §6 e ancorati nel codice (le assert dei cancelli in matlab/run_rtl_validate*.m,
run_plant_par.m, run_closed_loop.m, characterize_drift.m). Le risorse OOC del controllore da
document/SP4_ACC_IIDM_FAST.md. Nessun numero e' inventato; i cancelli sono deterministici (esito 0/N).

Uso:    python scripts/build_b2_0_checkpoint_report.py
Output: report/B2_0_CHECKPOINT_REPORT.{md,pdf}  +  report/figures_b2_0/*
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# --- CONFIG -----------------------------------------------------------------
HERE       = os.path.dirname(os.path.abspath(__file__))
ROOT       = os.path.dirname(HERE)
OUTDIR     = os.path.join(ROOT, 'report')
FIGDIR     = os.path.join(OUTDIR, 'figures_b2_0')
DOC_NAME   = 'B2_0_CHECKPOINT_REPORT'
DOC_TITLE  = 'CF_FSNN — Validazione RTL del controllore (Fase B2.0, checkpoint)'
FOOTER_TEXT = 'CF_FSNN — Fase B2.0 · validazione RTL (xsim), versione attuale · checkpoint intermedio'
EQ_DPI     = 200
os.makedirs(FIGDIR, exist_ok=True)

# --- GROUNDING: costanti ancorate ai run e ai doc di processo ----------------
# Risorse OOC del controllore Donatello_ACC_IIDM_M (SP4_ACC_IIDM_FAST.md, riquadro CHIUSO; HDL_PHASE §6)
CTRL_LUT, CTRL_FF, CTRL_DSP = 8614, 2134, 71
CTRL_FMAX, CTRL_LAT = 9.30, 358          # MHz OOC @8 MHz target ; clock/inferenza
# Cancelli (esito 0/N; conteggi = control-step x grandezze; HDL_PHASE §6, assert in run_rtl_validate*.m)
A1_N   = 15000   # 3 traj x 1000 x 5 param   (run_rtl_validate: A-1)
B1_N   = 3000    # 3 traj x 1000 accel       (run_rtl_validate_b: B-1)
PP_N   = 1800    # 3 traj x 200 x 3 stati    (run_plant_par: PLANT-PAR)  ; sensibilita': 166 mismatch
PP_SENS = 166
BL_N   = 2400    # 3 traj x 200 x 4 grandezze (run_closed_loop: B-LOOP)  ; BEHAV: 0 collisioni
# Deriva blocco-fisico vs riferimento sull'accel (characterize_drift, 20k control-step; HDL_PHASE §6)
DR_MED, DR_MEAN, DR_P99, DR_MAX = 0.0, 0.0154, 0.1875, 0.9766     # m/s^2
E_SNN_P99, E_SNN_MAX = 0.2721, 1.4843                             # budget E_snn (acc_types.m)
# Tipi delle porte (dalle entita' generate, Task 1 di M1/M2)
IN_BITS, PARAM_BITS, ACCEL_BITS = 32, 21, 13                      # sfix32_En20 ; Q7.13 ; Q4.8

PAL = {'blu': '#26527a', 'blunav': '#1a3c6e', 'verde': '#2e7d4f', 'mattone': '#b5522a',
       'grigio': '#8a94a0', 'ambra': '#c9992b', 'rosso': '#b5384d'}

# --- Normalizzazione tipografica (accenti veri) -----------------------------
import re as _re
_TRUNC_MAP = {
    "fedelta'": 'fedeltà', "idoneita'": 'idoneità', "modalita'": 'modalità', "attivita'": 'attività',
    "capacita'": 'capacità', "entita'": 'entità', "verita'": 'verità', "proprieta'": 'proprietà',
    "parita'": 'parità', "sparsita'": 'sparsità', "qualita'": 'qualità', "unita'": 'unità',
    "possibilita'": 'possibilità', "difficolta'": 'difficoltà', "identita'": 'identità',
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

# --- FIGURE DATI ------------------------------------------------------------
def fig_gates():
    """Copertura di validazione: control-step confrontati per cancello, tutti a 0 mismatch."""
    names = ['A-1\n(SNN, 5 param)', 'B-1\n(ctrl, accel)', 'PLANT-PAR\n(plant)', 'B-LOOP\n(anello)']
    vals  = [A1_N, B1_N, PP_N, BL_N]
    fig, ax = plt.subplots(figsize=(8.2, 2.9))
    bars = ax.bar(names, vals, color=[PAL['blu'], PAL['blu'], PAL['verde'], PAL['verde']])
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + 200, f'{v}\n0 mismatch', ha='center', fontsize=8.2)
    ax.set_ylabel('confronti bit-exact (control-step × grandezze)', fontsize=9)
    ax.set_ylim(0, max(vals) * 1.22); _style(ax)
    ax.set_title('Copertura di validazione RTL (versione attuale, dataset ridotto): 0 disallineamenti', fontsize=9.3)
    p = os.path.join(FIGDIR, 'gates.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_drift():
    """Deriva blocco-fisico vs riferimento sull'accel: percentili vs budget E_snn."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.4, 3.0), gridspec_kw={'width_ratios': [1.15, 1]})
    lbl = ['mediana', 'media', 'p99', 'max']; val = [DR_MED, DR_MEAN, DR_P99, DR_MAX]
    bars = a1.bar(lbl, val, color=[PAL['grigio'], PAL['grigio'], PAL['ambra'], PAL['mattone']])
    for b, v in zip(bars, val):
        a1.text(b.get_x()+b.get_width()/2, v + 0.02, f'{v:.3f}', ha='center', fontsize=8.5)
    a1.set_ylabel('|Δaccel|  [m/s²]', fontsize=9); a1.set_ylim(0, 1.1); _style(a1)
    a1.set_title('Deriva sull\'accel (20k control-step)', fontsize=9.3)
    # confronto col budget E_snn
    a2.bar(['p99', 'max'], [100*DR_P99/E_SNN_P99, 100*DR_MAX/E_SNN_MAX], color=PAL['ambra'])
    a2.axhline(100, color=PAL['rosso'], lw=0.9, ls='--')
    a2.text(1.5, 103, 'budget E_snn', color=PAL['rosso'], fontsize=8, ha='right')
    for i, v in enumerate([100*DR_P99/E_SNN_P99, 100*DR_MAX/E_SNN_MAX]):
        a2.text(i, v + 2, f'{v:.0f}%', ha='center', fontsize=9)
    a2.set_ylabel('% del budget E_snn', fontsize=9); a2.set_ylim(0, 120); _style(a2)
    a2.set_title('Coda vs quantizzazione della rete', fontsize=9.3)
    p = os.path.join(FIGDIR, 'drift.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

def fig_closedloop():
    """Schema dell'anello chiuso self-contained in xsim: plant nel TB <-> controllore RTL."""
    fig, ax = plt.subplots(figsize=(8.4, 2.8)); ax.axis('off'); ax.set_xlim(0, 10); ax.set_ylim(0, 5)
    def box(x, y, w, h, text, col):
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.05',
                     fc=col, ec='#33455a', lw=1.0))
        ax.text(x+w/2, y+h/2, text, ha='center', va='center', fontsize=8.6, color='white')
    box(0.5, 2.7, 3.2, 1.4, 'PLANT EGO\n(nel testbench, real=double)\nintegra 1 volta/control-step', PAL['verde'])
    box(6.3, 2.7, 3.2, 1.4, 'CONTROLLORE RTL\n(Donatello_ACC_IIDM_M,\nVHDL→Verilog, DUT)', PAL['blu'])
    ax.annotate('', xy=(6.3, 3.7), xytext=(3.7, 3.7), arrowprops=dict(arrowstyle='-|>', color='#33455a', lw=1.3))
    ax.text(5.0, 3.95, 's, v, dv, v_l  (fixed)', ha='center', fontsize=8, color='#33455a')
    ax.annotate('', xy=(3.7, 3.0), xytext=(6.3, 3.0), arrowprops=dict(arrowstyle='-|>', color='#b5522a', lw=1.3))
    ax.text(5.0, 2.75, 'accel  (Q4.8)', ha='center', fontsize=8, color='#b5522a')
    box(2.8, 0.5, 4.4, 1.1, 'PLANT-PAR: il plant e\' verificato == riferimento\nPRIMA dell\'anello live (anti-divergenza)', PAL['grigio'])
    ax.annotate('', xy=(2.1, 2.7), xytext=(3.6, 1.6), arrowprops=dict(arrowstyle='-|>', color='#8a94a0', lw=1.0, ls=':'))
    p = os.path.join(FIGDIR, 'closedloop.png'); fig.savefig(p, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig); return p

# --- CONTENUTO --------------------------------------------------------------
def build_doc():
    D = []; A = D.append
    A(('cover', {
        'title': DOC_TITLE,
        'subtitle': 'Validazione a livello RTL (testbench in Vivado xsim) del controllore car-following '
                    'spiking: la rete SNN e il controllore completo SNN+ACC-IIDM, provati bit-esatti '
                    'rispetto al blocco di riferimento, in anello aperto e in anello chiuso.',
        'meta': [
            'Livello di fedeltà: simulazione RTL comportamentale (Vivado xsim) del VHDL/Verilog generato '
            'da HDL Coder — non stima di risorse (Fase B) né misura su silicio (Fase C).',
            'Stato: CHECKPOINT INTERMEDIO. Versione ATTUALE dei blocchi (pre-ottimizzazione 2b), validata '
            'sul dataset RIDOTTO (3 traiettorie). Il report finale seguirà 2b (ottimizzazione) e 2c '
            '(validazione completa sul dataset intero).',
            'Grounding: i cancelli sono deterministici (esito 0/N) dai run in document/HDL_PHASE.md §6, '
            'ancorati nelle assert del codice (matlab/run_rtl_validate*.m, run_plant_par.m, run_closed_loop.m).',
            'Documenti gemelli: Report FPGA Fase B (risorse/potenza post-sintesi) · SP4_ACC_IIDM_FAST.md '
            '(ottimizzazione del controllore).',
        ],
    }))
    A(('toc', 'Sommario'))

    # 1. Sintesi
    A(('h1', '1. Sintesi'))
    A(('p', 'Questo documento riporta la **validazione a livello RTL** del controllore car-following '
            'spiking destinato all\'FPGA. L\'obiettivo non è misurare risorse o potenza — già coperti dal '
            'Report FPGA Fase B — ma **dimostrare che il codice RTL generato si comporta come deve**, '
            'simulandolo in Vivado xsim contro un riferimento software, e non su una singola traiettoria '
            'ridotta ma con metriche vere su migliaia di control-step (l\'errore che rese fragile il primo '
            'report di Fase B, qui deliberatamente evitato).'))
    A(('p', 'Sono stati costruiti **due harness di validazione**, entrambi self-contained in xsim: uno per '
            'la **rete SNN** (Donatello_Champion, che stima i cinque parametri IDM) e uno per il '
            '**controllore completo** (Donatello_ACC_IIDM_M, SNN+decodifica+ACC-IIDM, che produce '
            'l\'accelerazione). Il secondo è validato sia in **anello aperto** sia in **anello chiuso** — '
            'con il plant del veicolo riprodotto nel testbench e la retroazione sull\'accelerazione — così '
            'da provare non solo l\'uguaglianza bit-a-bit ma il **funzionamento car-following corretto**.'))
    A(('p', 'Esito: su tutti i cancelli, **zero disallineamenti** rispetto al riferimento bit-esatto del '
            'blocco, con i cancelli provati **sensibili** (falliscono quando un valore è alterato di 1 LSB). '
            'La caratterizzazione della deriva del blocco fisico rispetto al riferimento software è '
            'quantificata (§7) e ne definisce il limite noto.'))
    A(('img', (fig_gates(), 'Copertura di validazione della versione attuale sul dataset ridotto: per ogni '
               'cancello, il numero di confronti bit-esatti (control-step × grandezze) e l\'esito (0 '
               'disallineamenti). A-1: rete SNN (5 parametri). B-1: controllore (accel), anello aperto. '
               'PLANT-PAR: fedeltà del plant nel testbench. B-LOOP: anello chiuso completo.')))

    # 2. Oggetto e livello di fedelta'
    A(('h1', '2. Oggetto, livello di fedeltà, limiti dichiarati'))
    A(('p', 'I due blocchi validati provengono dalla libreria `snn_champions_lib` e sono l\'esito della '
            'fase di ottimizzazione SP4 (documento SP4_ACC_IIDM_FAST.md). Il controllore completo '
            'Donatello_ACC_IIDM_M — rete B2 time-multiplexata, decodifica a LUT a 64 punti, ACC-IIDM con '
            'macchina a stati che condivide un solo divisore — occupa in sintesi out-of-context sullo '
            f'Zynq-7020 **{CTRL_LUT} LUT · {CTRL_FF} FF · {CTRL_DSP} DSP** e chiude il timing a '
            f'**{CTRL_FMAX:.2f} MHz** (latenza {CTRL_LAT} clock per inferenza).'))
    A(('callout', 'Cosa NON è questo report. Non è una misura di risorse/potenza (Fase B), non è una misura '
               'su hardware (Fase C), e non è il report finale. È un checkpoint della VERSIONE ATTUALE, '
               'validata sul dataset RIDOTTO (3 traiettorie per gli anelli, 20 per la deriva). La '
               'validazione sul dataset intero (60k control-step) e a livello gate-level è la Fase 2c, che '
               'riuserà questi stessi harness sulla versione ottimizzata da 2b.'))
    A(('p', 'Il livello di fedeltà è la **simulazione RTL comportamentale** del codice generato da HDL '
            'Coder: si esercita esattamente il VHDL/Verilog che andrebbe in sintesi, con i tipi e le '
            'larghezze reali delle porte (ingressi a virgola fissa a 32 bit, parametri a 21 bit in formato '
            'Q7.13, accelerazione a 13 bit in Q4.8, lette dalle entità generate).'))

    # 3. Il problema
    A(('h1', '3. Il problema: che cosa significa "il riferimento"'))
    A(('p', 'Validare un blocco RTL significa confrontarne l\'uscita con un **golden** — un riferimento di '
            'cui ci si fida. La scelta del golden è il punto delicato, e in questa fase ha prodotto il '
            'risultato più istruttivo. Il riferimento software "naturale" della rete (il forward `r16`, '
            'basato sulla normalizzazione `snn_normalize`) **non coincide con il blocco**: le due catene '
            'divergono attorno al 52° control-step. La causa è duplice e misurata: il blocco fisico usa una '
            '**normalizzazione interna in virgola fissa** (`local_normalize`, per avere ingressi in unità '
            'fisiche) che devia di 1 LSB dal riferimento, e **pilota il forward tenendo l\'ingresso** '
            'mentre il riferimento lo alimenta con zeri durante l\'inferenza.'))
    A(('p', 'Il forward della rete inlinato nel blocco è, invece, **identico** al sorgente corrente (zero '
            'righe diverse): il blocco non è "vecchio". A nascondere la divergenza era il cancello '
            'preesistente `run_block_traj_test`, che girava di default su **20 control-step soltanto** — '
            'meno del punto di divergenza. È la stessa lezione del bug §2.1 documentato in HDL_PHASE: un '
            'cancello troppo poco profondo dà falsa fiducia.'))
    A(('img', (fig_eq('eq_chain.png', [
        r'\mathrm{blocco\ Simulink}\;\equiv\;\mathrm{golden\ MEX}\;\equiv\;\mathrm{RTL}\ (\mathrm{VHDL/Verilog})']),
        'La catena di fedeltà che gli harness stabiliscono: tre implementazioni indipendenti — il blocco '
        'Simulink, il golden software (MEX MATLAB Coder) e l\'RTL (HDL Coder) — devono dare risultati '
        'bit-identici. Legenda: ≡ = uguaglianza bit-a-bit su ogni control-step del dataset provato.')))
    A(('h2', '3.1  Il golden fedele al blocco'))
    A(('p', 'La soluzione è un golden **fedele al blocco**: si estrae verbatim l\'algoritmo esatto della '
            'chart (normalizzazione fixed + rete + decodifica + ACC-IIDM), lo si compila in MEX e lo si '
            '**guida clock-per-clock tenendo l\'ingresso**, esattamente come il blocco. Questo golden — a '
            'differenza del riferimento `r16` — riproduce il blocco per costruzione, ed è stato verificato '
            'uguale al blocco Simulink su una prova incrociata indipendente (differenza massima nulla). È '
            'lo stesso metodo per entrambi gli harness.'))

    # 4. Harness A
    A(('h1', '4. Harness A — la rete SNN (anello aperto)'))
    A(('p', 'Il primo harness valida `Donatello_Champion`, la rete che dai quattro ingressi fisici '
            f'(s, v, Δv, v_lead) stima i cinque parametri IDM (v₀, T, s₀, a, b), a {PARAM_BITS} bit ciascuno '
            '(Q7.13). Il testbench in Verilog pilota il VHDL generato con gli stimoli del dataset, campiona '
            'i cinque parametri a fine control-step e li confronta con il golden fedele.'))
    A(('p', f'**Cancello A-1**: su 3 traiettorie × 1000 control-step × 5 parametri = **{A1_N} confronti**, '
            '**zero disallineamenti**. Il cancello è provato **sensibile**: alterando di 1 LSB un solo '
            'parametro del golden, il testbench riporta il disallineamento (non è cieco). L\'RTL della rete '
            'riproduce dunque il blocco in modo bit-esatto.'))
    A(('callout', 'Perché la SNN va in VHDL e il controllore in Verilog. La rete da sola non contiene il '
               'divisore dell\'IIDM e simula correttamente in VHDL. Il controllore no (vedi §5).'))

    # 5. Harness B
    A(('h1', '5. Harness B — il controllore completo (anello aperto e chiuso)'))
    A(('p', 'Il secondo harness valida `Donatello_ACC_IIDM_M`, il controllore completo che produce '
            f'l\'accelerazione (13 bit, Q4.8). L\'anello aperto (**cancello B-1**) confronta l\'accel RTL '
            f'col golden fedele: **{B1_N} confronti, zero disallineamenti**, cancello sensibile a 1 LSB.'))
    A(('h2', '5.1  Il DUT in Verilog, non in VHDL'))
    A(('p', 'Il controllore, in VHDL, **non simula a time-0** in xsim: il divisore combinatorio dell\'IIDM '
            'indicizza una LUT con un indice che, prima che il reset asincrono si propaghi, vale −1 (i '
            'registri VHDL partono a `U`, metavalue). Generando il DUT in **Verilog**, HDL Coder inizializza '
            'i registri a 0 (`initial`): niente `U`, niente indice −1. È una scelta di simulazione, non di '
            'progetto — l\'RTL è lo stesso; per questo `rtl_gen_dut` ha ora un parametro lingua.'))
    A(('h2', '5.2  L\'anello chiuso self-contained'))
    A(('p', 'La prova che conta per il car-following è l\'**anello chiuso**: il controllore RTL guida un '
            '**plant del veicolo riprodotto dentro il testbench** (in `real`, cioè double, con i valori '
            'trasferiti bit-esatti via rappresentazione IEEE-754), che integra la dinamica una volta per '
            'control-step e retroaziona sull\'accelerazione. L\'intero anello gira in xsim, senza cosim '
            'esterna (HDL Verifier è stato sondato e scartato: setup fragile headless e runtime per-clock '
            'sfavorevole).'))
    A(('img', (fig_closedloop(), 'L\'anello chiuso self-contained: il plant EGO vive nel testbench (real), '
               'il controllore RTL è il DUT; la retroazione è sull\'accelerazione. Il cancello PLANT-PAR '
               'verifica il plant SEPARATAMENTE, contro il riferimento, prima di accendere l\'anello live.')))
    A(('p', 'La disciplina anti-divergenza è il cuore del metodo. Un anello chiuso amplifica ogni errore: '
            'se il plant nel testbench non fosse fedele, la traiettoria divergerebbe e non si saprebbe se la '
            'colpa è del plant o del controllore. Per questo le due metà sono verificate **separatamente e a '
            'buon mercato** prima di unirle:'))
    A(('table', (['Cancello', 'Cosa prova', 'Conteggio', 'Esito', 'Sensibilità'], [
        ['PLANT-PAR', 'plant-nel-TB == riferimento (senza RTL)', f'{PP_N}', '0 mismatch', f'ordine v invertito → {PP_SENS}'],
        ['B-LOOP', 'anello RTL == traiettoria di riferimento', f'{BL_N}', '0 mismatch', '(protetto da B-1 + PLANT-PAR)'],
        ['BEHAV', 'gap sempre > 0 (nessuna collisione)', f'{BL_N//4} step', '0 collisioni', 'gap ≤ 0 → conteggiato'],
    ])))
    A(('p', 'Con PLANT-PAR e B-1 verdi, se l\'anello live divergesse la colpa sarebbe **solo** '
            'nell\'integrazione (conversioni fixed↔real, temporizzazione) — una superficie stretta e '
            'diagnosticabile. L\'anello, su 3 traiettorie, riproduce la traiettoria di riferimento '
            'bit-esatta e mantiene sempre il gap positivo: il controllore RTL **guida correttamente**, non '
            'solo produce numeri identici.'))

    # 6. Tecniche
    A(('h1', '6. Tecniche e loro compromessi'))
    A(('h2', '6.1  Time-mux e FSM a stadi (dall\'ottimizzazione SP4)'))
    A(('p', 'Il controllore elabora un neurone per ciclo (time-multiplexing) e sequenzia le cinque '
            'divisioni dell\'IIDM su **un solo divisore** con una macchina a stati a stadi. Il time-mux '
            'taglia l\'area; il registro fra gli stadi dà la frequenza. Compromesso: la latenza sale a '
            f'{CTRL_LAT} clock per inferenza — irrilevante (su un control-step da 0,1 s a 8 MHz sono 800.000 '
            'clock disponibili, margine ~2200×), ma è il motivo per cui il rate d\'ingresso del blocco è '
            'più lento di un blocco puramente combinatorio.'))
    A(('h2', '6.2  Golden fedele al blocco (§3.1)'))
    A(('p', 'Vantaggio: elimina l\'ambiguità sul riferimento e riproduce il blocco per costruzione. '
            'Compromesso: il golden va **rigenerato** quando il blocco cambia (l\'algoritmo è estratto dalla '
            'chart), e la sua fedeltà va ri-verificata — un passo in più, ma a buon mercato.'))
    A(('h2', '6.3  Verilog per il controllore (§5.1)'))
    A(('p', 'Vantaggio: risolve il metavalue a time-0 senza toccare il progetto. Compromesso: l\'harness usa '
            'due lingue (VHDL per la rete, Verilog per il controllore) — coerente, perché sono DUT distinti, '
            'ma va ricordato.'))
    A(('h2', '6.4  Anello self-contained + PLANT-PAR (§5.2)'))
    A(('p', 'Vantaggio: tutto in xsim, veloce, senza cosim esterna; l\'anti-divergenza isola i guasti. '
            'Compromesso: il plant va **riprodotto** nel testbench in `real`; mitigato dal cancello '
            'PLANT-PAR che ne prova la fedeltà prima dell\'anello live.'))

    # 7. Deriva
    A(('h1', '7. Caratterizzazione della deriva blocco-fisico vs riferimento'))
    A(('p', 'Il blocco fisico validato usa la normalizzazione interna in virgola fissa; il sistema '
            'deployato sull\'FPGA normalizza in software (float). La differenza fra i due è la **deriva** — '
            'il limite noto della versione fisica. È stata quantificata sull\'accelerazione confrontando il '
            'blocco (normalizzazione fixed, ingresso tenuto) col riferimento (normalizzazione software, '
            'serializzato) su 20.000 control-step.'))
    A(('img', (fig_drift(), 'Deriva sull\'accelerazione fra blocco fisico e riferimento software. A '
               'sinistra i percentili di |Δaccel|; a destra il rapporto della coda (p99, max) col budget '
               'E_snn, cioè il footprint in accel della quantizzazione che la rete già si porta.')))
    A(('p', f'La deriva è **sparsa**: mediana **{DR_MED:.3f}**, media **{DR_MEAN:.4f}** m/s² — sulla '
            f'maggioranza dei control-step il blocco e il riferimento danno accel identica. Ma la **coda è '
            f'significativa**: p99 = **{DR_P99:.4f}**, max = **{DR_MAX:.4f}** m/s², cioè '
            f'**{100*DR_P99/E_SNN_P99:.0f}% / {100*DR_MAX/E_SNN_MAX:.0f}%** del budget E_snn. Verdetto '
            'onesto: trascurabile in media, **non trascurabile in coda** — sugli eventi di spike-flip la '
            'normalizzazione fixed aggiunge un errore dello stesso ordine della quantizzazione della rete. '
            'È la differenza reale fra il blocco fisico (che questi harness validano) e il riferimento '
            'software, da tenere presente per il futuro confronto con MPC.'))
    A(('callout', 'La misura qui è in anello APERTO. Se in anello chiuso questi picchi sparsi si smorzino '
               '(sistema car-following stabile) o si accumulino è una misura ancora da fare, dichiarata come '
               'nota aperta.'))

    # 8. Risultati
    A(('h1', '8. Quadro dei risultati'))
    A(('table', (['Harness / cancello', 'Grandezza', 'Confronti', 'Disallineamenti', 'Sensibile'], [
        ['A-1 (SNN, anello aperto)', '5 parametri IDM', f'{A1_N}', '0', 'sì (1 LSB)'],
        ['B-1 (controllore, anello aperto)', 'accel', f'{B1_N}', '0', 'sì (1 LSB)'],
        ['PLANT-PAR (plant nel TB)', 's, v, Δv', f'{PP_N}', '0', f'sì ({PP_SENS})'],
        ['B-LOOP (anello chiuso)', 's, v, Δv, accel', f'{BL_N}', '0', '(transitivo)'],
        ['BEHAV (comportamento)', 'gap', f'{BL_N//4}', '0 collisioni', 'sì (gap≤0)'],
    ])))
    A(('p', 'Tutti i cancelli sono deterministici (esito 0/N) e provati sensibili. Le tre implementazioni '
            'indipendenti — blocco Simulink, golden MEX, RTL — concordano bit-a-bit.'))

    # 9. Limiti e prossimi passi
    A(('h1', '9. Limiti dichiarati e prossimi passi'))
    A(('p', '**Limiti di questo checkpoint.** (1) La validazione è sul dataset **ridotto** (3 traiettorie '
            'per gli anelli, 20 per la deriva), non sui 60k control-step interi — è la Fase 2c. (2) La '
            'deriva del blocco fisico non è trascurabile in coda (§7). (3) La misura in anello chiuso della '
            'deriva è ancora da fare. (4) Le risorse/timing sono la sintesi OOC di SP4, non post-route '
            'completo (manca il BRAM), coperto in Fase 2c/report finale.'))
    A(('p', '**Prossimi passi.** 2b — ottimizzazione del timing (pipelining bit-esatto del `tanh`, il collo '
            'del percorso critico) per spingere oltre 9,30 MHz. 2c — validazione **completa** sul dataset '
            'intero e a gate-level (post-route con SDF), riusando **questi stessi harness** con la modalità '
            '"full". Poi il report finale, che sostituirà questo checkpoint con la versione ottimizzata e '
            'validata al completo.'))

    # Riferimenti
    A(('h1', 'Riferimenti (fonti interne)'))
    A(('table', (['Fonte', 'Contenuto'], [
        ['document/HDL_PHASE.md §6', 'Stato e risultati dei cancelli (A-1, B-1, PLANT-PAR, B-LOOP, BEHAV) e della deriva'],
        ['document/SP4_ACC_IIDM_FAST.md', 'Ottimizzazione del controllore: time-mux, FSM a stadi, risorse OOC 9,30 MHz'],
        ['matlab/run_rtl_validate.m · run_rtl_validate_b.m', 'Orchestratori e assert dei cancelli A-1 / B-1'],
        ['matlab/run_plant_par.m · run_closed_loop.m', 'Cancelli PLANT-PAR / B-LOOP / BEHAV (anello chiuso)'],
        ['matlab/cl_ref_acciidm_m.m', 'Anello di riferimento block-faithful (golden della traiettoria)'],
        ['matlab/characterize_drift.m', 'Caratterizzazione della deriva blocco-vs-riferimento sull\'accel'],
        ['matlab/axi/acciidm_m/tb_*.v', 'Testbench Verilog: anello aperto, plant-parity, anello chiuso'],
        ['docs/superpowers/specs+plans 2026-07-17/18', 'Spec dei due harness e piani d\'esecuzione M1/M2'],
    ])))
    return D

# --- RENDER (identici al generatore di Fase B) ------------------------------
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
        return re.sub(r'(?<!\w)\*\*(\S(?:.*?\S)?)\*\*', r'<b>\1</b>', s)
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
