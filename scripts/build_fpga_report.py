"""Genera il REPORT FPGA (Fase A pre-silicio) CF_FSNN — .md + .pdf da un'unica sorgente.

Terzo membro del trio di documenti v3 (con HOW_IT_WORKS_v3 = teoria e
VALIDATION_REPORT_v3 = risultati dell'evaluate). Questo documento e' la FPGA-evaluate
PROFONDA: 45 figure su 10 sezioni (readiness -> thermal), a dati reali sui 4 champion,
prodotte da scripts/fpga_figures.py (5 librerie Fase A) e salvate in
results/evaluate/FPGA/. Le figure 🟢 sono a dati reali; le 🟡/🔴 (HDL/board) sono STIME
di progetto marcate (validate solo su silicio nelle Fasi B/C).

Stile: emula scripts/build_validation_report_v3.py (reportlab, unica sorgente -> md+pdf,
font DejaVu, blocchi cover/h1/h2/p/callout/table/img).

Uso:  python scripts/build_fpga_report.py
Output: document/FPGA_REPORT.{md,pdf}, document/figures_fpga/*
Prerequisito: results/evaluate/FPGA/ popolata (render HB_AZURE) + CSV deliverable.
"""
import os
import glob
import shutil
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCDIR = os.path.join(ROOT, 'report')
FIGDIR = os.path.join(DOCDIR, 'figures_fpga')
EVAL = os.path.join(ROOT, 'results', 'evaluate', 'FPGA')
os.makedirs(FIGDIR, exist_ok=True)


EQ_DPI = 200  # equazioni: risoluzione fissa; nel PDF vanno a dimensione proporzionale al testo


def fig_eq(name, lines, fs=11, color='#12233a'):
    """Renderizza una o più righe di equazione (mathtext) in un PNG 'tight'.
    Nessun carattere accentato dentro la formula (le legende vanno in didascalia)."""
    n = len(lines)
    fig = plt.figure(figsize=(9.2, 0.52 * n + 0.22))
    for i, ln in enumerate(lines):
        fig.text(0.5, 1.0 - (i + 0.5) / n, '$' + ln + '$',
                 ha='center', va='center', fontsize=fs, color=color)
    p = os.path.join(FIGDIR, name)
    fig.savefig(p, dpi=EQ_DPI, bbox_inches='tight', pad_inches=0.08, facecolor='white')
    plt.close(fig)
    return p


CHAMP = ['Raffaello', 'Leonardo', 'Donatello', 'Michelangelo']
METHOD = {'Raffaello': 'BPTT', 'Leonardo': 'BPTT', 'Donatello': 'EventProp', 'Michelangelo': 'EventProp'}
CKPT = {'Raffaello': 'R33_C2_A1_T12_fix', 'Leonardo': 'LS3_PEAK_R0_launch_d03',
        'Donatello': 'PE_t05_gp0002', 'Michelangelo': 'A_lr1e2_t06_r16'}

SECTION_ORDER = ['00_Readiness', '01_Weights_po2', '02_FixedPoint', '03_Spiking', '04_Energy',
                 '05_Timing_WCET', '06_Resources_DSE', '07_SEU_ISO26262', '08_IO_HIL', '09_Thermal']

# --- CSV (numeri veri -> testo/tabelle riproducibili) ------------------------
def _csv(*p):
    fp = os.path.join(EVAL, *p)
    return pd.read_csv(fp) if os.path.isfile(fp) else None

SCORE = _csv('00_Readiness', 'scorecard.csv')
ENP = _csv('04_Energy', 'energy_power.csv')
WST = _csv('01_Weights_po2', 'weight_stats.csv')
if SCORE is not None:
    SCORE = SCORE.set_index('champion')
if ENP is not None:
    ENP = ENP.set_index('champion')


def sc(ch, col, fmt='%.2f'):
    try:
        return fmt % float(SCORE.loc[ch, col])
    except Exception:
        return 'n/d'


def en(ch, col, fmt='%.2f'):
    try:
        return fmt % float(ENP.loc[ch, col])
    except Exception:
        return 'n/d'


# derivati narrativi (robusti ad assenza csv)
def _rng(col, src):
    try:
        vals = [float(src.loc[c, col]) for c in CHAMP]
        return min(vals), max(vals)
    except Exception:
        return None, None

SPK_MIN, SPK_MAX = _rng('spike_rate_pct', SCORE) if SCORE is not None else (13.3, 19.0)
ADVW_MIN, ADVW_MAX = _rng('advantage_worstcase_x', ENP) if ENP is not None else (4.77, 6.01)
SPK_LO, SPK_HI = '%.0f' % SPK_MIN, '%.0f' % SPK_MAX
ADVW_LO, ADVW_HI = '%.2f' % ADVW_MIN, '%.2f' % ADVW_MAX
DON_RHO = sc('Donatello', 'rho_po2', '%.3f') if SCORE is not None else '0.05'
DON_SPK = en('Donatello', 'spike_rate_pct', '%.1f') if ENP is not None else '19.0'
DON_ADV = en('Donatello', 'advantage_worstcase_x', '%.2f') if ENP is not None else '4.77'


# --- figure: copia le PNG della sezione in figures_fpga/ + caption -----------
# caption curate per nome-file (stem). Fallback: nome prettificato.
CAP = {
    'readiness_radar': 'Radar di FPGA-readiness per champion (small-multiples). Ogni asse 0-1 con ANCORA esplicita fra parentesi (1 = ideale FPGA): ρ<1 (contrattivo), Fix-pt (quant po2 senza errore), Sparsità (firing minore), Energia (≥15× vs ANN), Timing (util≈0), SEU (0 bit critici). I valori numerici reali sono nella tabella successiva.',
    'deploy_verdict': 'I numeri reali dietro il radar, una colonna per asse + footprint (la colonna energia usa il vantaggio nel caso tipico; la tabella in testa al report usa il worst-case). Colorazione per rango (verde = migliore dei 4 su quella metrica, nessuna soglia arbitraria). Candidato deploy: Donatello (ρ minimo 0.05, quant robusto).',
    'po2_alphabet': 'Alfabeto po2 dei pesi (13 valori sign·2^k) per champion. "pesi a 0 = sinapsi eliminabili" è la potatura strutturale del connettoma (sinapsi a peso 0), NON neuroni morti. Il moltiplicatore è UNO di 13 valori → barrel-shifter, 0 DSP.',
    'resource_occupancy': 'Occupazione stimata del budget Zynq-7020 (LUT/FF/BRAM/DSP) per champion. BRAM reale (footprint pesi); LUT/FF stima; DSP = 0 (po2 → shift-add).',
    'spectral_recurrence': 'Raggio spettrale ρ(U·V): pieno = po2, vuoto = float. ρ<1 (EventProp) = loop contrattivo, sicuro in fixed-point; ρ>1 (BPTT) = espansivo (rischio overflow). È IL discriminante di stabilità hardware.',
    'sparsity_mask': '% pesi a zero per matrice (fc / rec_U / rec_V / out), per champion: la sparsità strutturale del connettoma → sinapsi eliminabili in hardware.',
    'po2_exponent_range': 'Range di esponente po2 usato per matrice, per champion → numero di bit di esponente necessari.',
    'bit_allocation': 'Formato Qm.n per ogni stato interno (segno + interi dal RANGE MISURATO + frazionari). Solo baseline (gli stati non sono catturati per la variante EventProp — limite del profiler).',
    'state_ranges': 'Range dinamico min..max dei registri interni fixed-point (| rosso = p0.1/p99.9): il range fissa gli int_bits.',
    'quant_vs_bits': 'Errore di identificazione vs bit-width dei pesi, per champion (linea piena = fixed Qm.n, tratteggio = po2 di deploy). La rete tollera pochi bit; Leonardo ha l\'errore po2 più alto.',
    'per_param_fragility': 'Quale dei 5 parametri cede di più sotto quantizzazione po2, per champion.',
    'chattering': 'Accelerazione closed-loop: float (liscia) vs parametri quantizzati a 2 bit (nervosa), per champion — stress test dell\'instabilità da quantizzazione.',
    'leak_decay': 'Il leak di membrana è un bit-shift (V·7/8): con pochi frac_bits il potenziale va in sotto-flusso e resta BLOCCATO; con 8 bit ~ float.',
    'activity_map': 'Mappa di firing per neurone hidden, per champion: hotspot vs neuroni morti (rate 0).',
    'raster': f'Raster degli spike ordinato per firing-rate, tutti i champion (% attivi/tick fra parentesi). I champion sparano ~{SPK_LO}-{SPK_HI}% — NON sono iper-sparsi.',
    'sparsity_per_tick': 'Spike concorrenti per tick, per champion: il MAX simultaneo fissa la larghezza dell\'albero di accumulo (AC).',
    'isi_dist': 'Distribuzione degli inter-spike-interval, per champion: l\'ISI minimo dà il worst-case back-to-back.',
    'dead_saturated': 'Neuroni morti (rate 0) e saturi (rate ~1) per champion: gli EventProp hanno 0 morti, i BPTT ~31% — la salute della rete è un vantaggio del gradiente esatto.',
    'energy_vs_ann': 'Energia per inferenza: SNN tipico (sparso) vs SNN worst-case (denso) vs ANN densa (MAC), per champion, con il vantaggio ×. Il guadagno viene dal costo AC<MAC (0 DSP), NON dalla sparsità.',
    'energy_breakdown': 'Dove si spendono i pJ per champion (fc / rec_V / rec_U / out / non-sinaptiche).',
    'energy_vs_rate': f'Energia vs spike-rate: i pallini marcano il rate operativo reale (~{SPK_LO}-{SPK_HI}%) — i champion NON sono nel regime iper-sparso.',
    'synops_split': 'Parte statica (input, sempre-on) vs dinamica (spike-driven) delle SynOps per champion → dove conviene il clock-gating.',
    'op_count': 'Conteggio operazioni per tick (input del WCET), per champion: si vede la differenza rank-8 (baseline) vs rank-16 (EventProp) sui rami ricorrenti.',
    'wcet_cycles': 'Cicli e µs per inferenza secondo 4 architetture HW (esemplare: Donatello; datapath simile fra champion).',
    'latency_margin': 'Tempo di inferenza vs deadline di controllo 100 ms, per champion: margine enorme (util ~0.1-0.2%, variante seriale).',
    'jitter_proof': 'WCET == BCET: il numero di operazioni è costante a ogni spike-rate → jitter di calcolo = 0 (esemplare: Donatello).',
    'decode_criticalpath': 'STIMA del datapath del decode ACC-IIDM (sqrt/div/sigmoid/tanh) in PL: CORDIC iterativo (shift-add, DSP≈0) sul budget di 100 ms.',
    'op_by_celltype': 'Operazioni per tipo di cella (AC spike-driven vs shift-add po2) per champion: nessun moltiplicatore → 0 DSP.',
    'dse_pareto': 'Trade-off area↔latenza per grado di parallelismo, per champion (latenza reale, area STIMA).',
    'area_model': 'STIMA dell\'area (LUT/FF) al variare del parallelismo — da confermare in sintesi (Fase B).',
    'bram_dimensioning': 'Memoria pesi per champion: <1 BRAM su 140 (<1% del budget).',
    'concept_-_cosa_sono_i_bit-flip': 'Concetto: un Single Event Upset (SEU) inverte UN bit nella memoria dei pesi po2 → i 5 parametri cambiano → l\'accelerazione cambia → possibile collisione. Simulato via seu_inject (reale, no HW).',
    'sensitivity_map': 'Δ errore-di-identificazione invertendo 1 bit di un peso (heatmap), per champion: quali bit/pesi sono critici.',
    'bit_criticality': 'Quali bit (esponente-LSB/mid/MSB, segno) dominano il rischio SEU, per champion → ECC mirata.',
    'degrade_vs_flips': 'Collisione closed-loop vs numero di bit-flip accumulati, per champion: 0 collisioni fino a 8 flip (i 4 champion sovrapposti a 0) → periodo di scrubbing.',
    'perparam_shift': 'Spostamento per-parametro sotto SEU, per champion: quale parametro è più esposto.',
    'hidden_vs_readout': 'Criticità SEU media hidden (fc/rec) vs readout (out), per champion → dove concentrare il TMR (il readout è più critico?).',
    'tmr_overhead': 'STIMA del costo del Triple Modular Redundancy (TMR) selettivo sul readout vs protezione totale.',
    'aoi_max_surface': 'Età MAX tollerabile del CAM V2X (AoI) sul piano gap×Δv oltre cui la guida è insicura (verde = tollera di più; esemplare: Donatello).',
    'aoi_dist': 'Distribuzione dell\'Age-of-Information sotto perdita/ritardo dei pacchetti V2X.',
    'queue_overflow': 'Probabilità di drop su burst vs profondità della coda RX (M/M/1/K, STIMA): buffer minimo anti-burst dei messaggi CAM.',
    'holdmode': 'Confronto degli handler di pacchetti mancanti (hold-last / dead-reckon / blind): la robustezza V2X è dell\'HANDLER, non della rete.',
    'pdr_knee': 'Curva collisione vs Packet Delivery Ratio (PDR): il "ginocchio" oltre cui la perdita pacchetti diventa pericolosa.',
    'pdr_latency_knee': 'Curva collisione vs Packet Delivery Ratio / latenza V2X: il "ginocchio" oltre cui perdita e ritardo dei pacchetti CAM diventano pericolosi per la guida.',
    'derating_tj_fmax': 'STIMA: Fmax vs temperatura di giunzione Tj — a caldo il clock scende, resta headroom sul target a 100 °C?',
    'thermal_budget': 'STIMA del budget termico (potenza vs dissipazione) sullo Zynq-7020.',
}

# titolo umano di sezione
SEC_TITLE = {
    '00_Readiness': '0. Readiness: la scorecard di idoneità FPGA',
    '01_Weights_po2': '1. Pesi Power-of-Two: il moltiplicatore che sparisce',
    '02_FixedPoint': '2. Fixed-point: formato Qm.n e robustezza alla quantizzazione',
    '03_Spiking': '3. Dinamica spiking: sparsità reale e salute della rete',
    '04_Energy': '4. Energia: il vantaggio AC<MAC (e da dove NON viene)',
    '05_Timing_WCET': '5. Timing / WCET: margine sul deadline e jitter zero',
    '06_Resources_DSE': '6. Risorse e DSE: 0 DSP, <1% BRAM',
    '07_SEU_ISO26262': '7. SEU / ISO 26262: robustezza ai bit-flip e TMR mirato',
    '08_IO_HIL': '8. I/O e Hardware-in-the-Loop: canale V2X e code',
    '09_Thermal': '9. Termico: derating (stime pre-sintesi)',
}

# prosa curata per sezione (fondata sui numeri reali via f-string dove utile)
SEC_PROSE = {
    '00_Readiness': [
        'La sezione apre con il cruscotto: un radar per champion e una tabella di numeri reali. '
        'Le sei dimensioni della readiness sono tutte metriche misurate, non colonne costanti o '
        'etichette fuorvianti: ρ<1 (contrattività della ricorrenza), Fix-pt (robustezza alla '
        'quantizzazione po2), Sparsità (firing), Energia (vantaggio AC<MAC), Timing (margine sul '
        'deadline), SEU (robustezza al bit-flip). Il radar dà la forma d\'insieme; la tabella '
        'deploy_verdict dà i valori esatti confrontabili, colorati per rango.',
        f'Il candidato al deploy è **Donatello** (EventProp): ρ minimo ({DON_RHO}), errore di '
        f'quantizzazione po2 il più basso, 0 neuroni morti. Il rovescio onesto: spara di più '
        f'({DON_SPK}%) e ha quindi il vantaggio energetico più BASSO ({DON_ADV}×). **Leonardo** (BPTT) '
        f'è il più fragile (Fix-pt e SEU bassi). L\'edge FPGA di EventProp è ρ<1 + 0 morti, NON la '
        f'sparsità o l\'energia.',
    ],
    '01_Weights_po2': [
        'Il cuore del co-design è la quantizzazione po2 (schema e razionale in HOW_IT_WORKS_v3 §15; '
        'quantizzazione logaritmica dei pesi, Miyashita et al. 2016). Qui il lato hardware misurato: il '
        'moltiplicatore diventa un bit-shift → **0 DSP**; e '
        'l\'istogramma po2_alphabet mostra la sparsità dei pesi (sinapsi a valore 0 = eliminabili dal '
        'connettoma) — da non confondere coi neuroni morti (attività, §3): sono sinapsi che '
        'semplicemente non esisteranno in hardware.',
        'Il footprint dei pesi è di 400-656 byte per champion (rank-8 vs rank-16): trascurabile vs '
        'la BRAM (§6). Il raggio spettrale ρ(U·V) (definizione in HOW §11) separa EventProp '
        '(contrattivo, ρ<1) da BPTT (espansivo, ρ>1): è il discriminante che rende gli EventProp sicuri '
        'in aritmetica a virgola fissa.',
    ],
    '02_FixedPoint': [
        'Ogni registro interno (potenziale, fatica, corrente ricorrente, uscita LI) riceve un formato '
        'Qm.n con gli interi dal RANGE MISURATO e i frazionari dal budget di bit. La rete tollera una '
        'quantizzazione aggressiva: l\'errore di identificazione resta basso fino a pochi bit. Il '
        'punto fragile è la quantizzazione po2 di deploy: **Leonardo** ha l\'errore po2 più alto '
        '(quant-err ~15-16%), gli altri restano bassi (Donatello ~2%).',
        'Il caveat onesto: la curva quant_vs_bits è pienamente valida solo con re-training QAT; qui è '
        'una stima post-hoc. Il leak di membrana (bit-shift, cfr. HOW §15) con troppo pochi frac_bits '
        'manda il potenziale in sotto-flusso e lo blocca — un vincolo reale sul numero minimo di bit '
        'frazionari (figura leak_decay). Gli state-range sono catturati solo per i baseline (limite del '
        'profiler sulla variante EventProp, che non fa un forward per-step).',
    ],
    '03_Spiking': [
        f'La dinamica spiking sfata un equivoco: i champion **sparano ~{SPK_LO}-{SPK_HI}%** dei '
        f'neuroni per tick, non sono iper-sparsi (l\'1-2% talvolta attribuito alle SNN). Il raster e la '
        f'mappa di attività lo mostrano cross-champion. Questi spike-rate (profiler op-count, finestra '
        f'launch) differiscono di ~1-2 punti da VALIDATION_REPORT_v3 §9.2 (valutazione a 6-tier; es. '
        f'Donatello {DON_SPK}% qui vs 19.0% là): stessa realtà, finestre e metodo di misura diversi.',
        'Il picco di spike simultanei per tick dimensiona l\'albero di accumulo (AC) in hardware; '
        'l\'ISI minimo dà il worst-case back-to-back. La salute della rete è il vero discriminante: '
        'gli **EventProp hanno 0 neuroni morti**, i BPTT ~31% — la ricorrenza contrattiva e il '
        'gradiente esatto tengono viva l\'intera popolazione.',
    ],
    '04_Energy': [
        f'Il vantaggio energetico vs una ANN densa è **~{ADVW_LO}-{ADVW_HI}×** (worst-case; fino a '
        f'~15× nel caso tipico). Non viene dalla sparsità: le SynOps eguagliano o superano i MAC '
        f'dell\'ANN. Viene dal minor costo unitario di un accumulo (AC) rispetto a una '
        f'moltiplicazione-accumulo (MAC), amplificato su FPGA dai pesi po2 (AC = shift+add) e da 0 DSP.',
        f'Conseguenza contro-intuitiva: **Donatello**, il più contrattivo, spara di più (~{DON_SPK}%) '
        f'e ha quindi il vantaggio energetico più basso (~{DON_ADV}×). Il breakdown mostra dove si '
        f'spendono i pJ (la ricorrenza rec_V/rec_U domina nei rank-16); il grafico energy_vs_rate marca '
        f'il rate operativo reale, ben dentro il regime denso, non quello iper-sparso.',
        f'Coerenza col gemello: VALIDATION_REPORT_v3 §9.2 riporta una stima più grossolana (~4.77-6.01×) '
        f'dalla valutazione a 6-tier; qui il modello op-count distingue il worst-case '
        f'(~{ADVW_LO}-{ADVW_HI}×) dal tipico (~9-15×), dello stesso ordine di grandezza.',
    ],
    '05_Timing_WCET': [
        'Il conteggio operazioni per tick è l\'input del WCET e distingue rank-8 (baseline) da '
        'rank-16 (EventProp) sui rami ricorrenti. Il tempo di inferenza dipende dal grado di '
        'parallelismo: la variante seriale (minima in area) impiega ~120-171 µs, le varianti più '
        'parallele scendono a pochi µs — tutte contro un **deadline di controllo di 100 ms**. Anche la '
        'seriale usa quindi solo ~0.1-0.2% del budget: il margine è enorme, ed è proprio questo che permette '
        'di ottimizzare per area (CORDIC iterativo, DSP≈0) invece che per velocità.',
        'Proprietà preziosa per un sistema safety: **WCET == BCET**. Il numero di operazioni è '
        'costante a ogni spike-rate (worst-case), quindi il jitter di calcolo è nullo — un vantaggio '
        'di determinismo temporale rispetto a un\'esecuzione data-dependent.',
    ],
    '06_Resources_DSE': [
        'Il conto delle risorse è netto: **0 DSP** (ogni operazione è AC o shift-add, nessun '
        'moltiplicatore) e **<1 BRAM su 140** per la memoria pesi (<1% del budget). Lo spazio di '
        'design (DSE) mostra il trade-off area↔latenza al variare del parallelismo: con 100 ms di '
        'budget conviene la variante seriale, minima in area.',
        'Le stime di area LUT/FF (area_model) sono pre-sintesi e vanno confermate in Fase B (Vivado); '
        'la BRAM e il conteggio operazioni sono invece reali.',
    ],
    '07_SEU_ISO26262': [
        'La robustezza ai Single Event Upset (un neutrone atmosferico che inverte un bit nella memoria '
        'pesi) è profilata via fault-injection software: si decodifica il peso po2, si inverte un bit, '
        'si riesegue l\'identificazione. La mappa di sensibilità e la criticità per bit dicono quali '
        'bit dominano il rischio (l\'esponente-MSB e il segno) → ECC mirata invece che totale.',
        'La curva degrade_vs_flips mostra 0 collisioni fino a 8 bit-flip accumulati per tutti e 4 i '
        'champion → il periodo di scrubbing può essere rilassato. **Leonardo** è il più fragile ai '
        'SEU. Il confronto hidden vs readout indica dove concentrare il TMR (il readout, più critico). '
        'Le stime di overhead TMR sono di progetto (da validare in sintesi).',
    ],
    '08_IO_HIL': [
        'Il lato I/O modella il canale V2X e le code di ingresso. La superficie AoI (Age-of-Information) '
        'dà l\'età massima tollerabile di un CAM prima che la guida diventi insicura, sul piano gap×Δv. '
        'Il messaggio chiave, coerente col report di validazione: la robustezza alla perdita di '
        'pacchetti è dell\'HANDLER "hold-last", NON della rete — senza handler la collisione esplode.',
        'Il dimensionamento della coda RX (M/M/1/K) dà il buffer minimo anti-burst dei messaggi; la '
        'curva PDR mostra il "ginocchio" oltre cui la perdita pacchetti diventa pericolosa. Queste '
        'figure combinano dati reali (comportamento della rete) e stime di modello (coda).',
    ],
    '09_Thermal': [
        'La sezione termica è interamente di stima (🟡): il derating di Fmax con la temperatura di '
        'giunzione e il budget termico sullo Zynq-7020. Servono a impostare i margini, ma i numeri '
        'reali arriveranno solo dalla sintesi e dalla misura su board (Fasi B/C). Sono inclusi marcati '
        'come stime, non come risultati.',
    ],
}

# --- equazioni (mathtext -> PNG), iniettate dopo la prosa della sezione ------
EQ_QMN = fig_eq('eq_qmn.png', [
    r'x_{Qm.n} = \frac{k}{2^{n}}\,, \quad k \in \mathbb{Z}\,, \ \ x \in [\,-2^{\,m-1},\ 2^{\,m-1}-2^{-n}\,]',
])
EQ_ENERGY = fig_eq('eq_energy.png', [
    r'\frac{E_{\mathrm{ANN}}}{E_{\mathrm{SNN}}} = \frac{N_{\mathrm{MAC}}\, e_{\mathrm{MAC}}}{\mathrm{SynOps}\cdot e_{\mathrm{AC}}}',
])
EQ_WCET = fig_eq('eq_wcet.png', [
    r'\mathrm{WCET} = N_{\mathrm{cicli}}\cdot T_{\mathrm{clk}}\,, \qquad \mathrm{util} = \frac{\mathrm{WCET}}{T_{\mathrm{deadline}}}',
])
EQ_IOHIL = fig_eq('eq_iohil.png', [
    r'P_K = \frac{(1-a)\,a^{K}}{1-a^{K+1}}\,, \quad a = \lambda/\mu',
    r'\mathrm{AoI}:\ \ \Delta(t) = t - u(t)',
])
SEC_EQ = {
    '02_FixedPoint': [(EQ_QMN, 'Equazione 2.1 — Formato fixed-point Qm.n. m = bit interi (con segno), '
                              'n = bit frazionari; il valore è un intero k scalato di 2⁻ⁿ. Gli int_bits '
                              'derivano dal range misurato dello stato, i frac_bits dal budget di bit '
                              '(qui m include il bit di segno; la figura bit_allocation lo mostra separato).')],
    '04_Energy': [(EQ_ENERGY, 'Equazione 4.1 — Vantaggio energetico. N_MAC = moltiplicazioni-accumulo '
                             'della ANN equivalente; SynOps = Σ (spike × fan-out); e_MAC ≈ 4.6 pJ, '
                             'e_AC ≈ 0.9 pJ (modello Horowitz 2014, 45 nm). Il guadagno viene da '
                             'e_AC < e_MAC e dallo 0 DSP, non dalla sparsità.')],
    '05_Timing_WCET': [(EQ_WCET, 'Equazione 5.1 — WCET e utilizzo. N_cicli = conteggio operazioni per '
                                'inferenza; T_clk = periodo di clock; T_deadline = 100 ms (10 Hz, ciclo '
                                'di controllo/V2X). WCET == BCET perché il conteggio è data-indipendente.')],
    '08_IO_HIL': [(EQ_IOHIL, 'Equazione 8.1 — Coda RX M/M/1/K (sopra) e Age-of-Information (sotto). '
                            'P_K = probabilità di blocco (drop a buffer pieno); K = profondità della coda; '
                            'a = λ/μ = intensità di traffico; Δ(t) = età dell\'ultimo CAM ricevuto '
                            '(t meno l\'istante u(t) di generazione).')],
}


def _figs(section):
    """(path_dest, caption) per ogni PNG della sezione, in ordine di SECTIONS."""
    out = []
    for p in sorted(glob.glob(os.path.join(EVAL, section, '*.png'))):
        stem = os.path.splitext(os.path.basename(p))[0]
        dest = os.path.join(FIGDIR, '%s__%s.png' % (section, stem))
        shutil.copy(p, dest)
        cap = CAP.get(stem, stem.replace('_', ' '))
        out.append((dest, cap))
    return out


# ---------------------------------------------------------------------------
# DOC
# ---------------------------------------------------------------------------
def build_doc():
    D = []
    A = D.append
    A(('cover', {
        'title': 'CF_FSNN — Report FPGA (Fase A)',
        'subtitle': 'Profilo di idoneità FPGA (Zynq-7020 / PYNQ-Z1) dei 4 champion, pre-silicio — 45 figure su 10 sezioni (dati reali dove 🟢, stime dove 🟡/🔴)',
        'meta': [
            'Documento della terna CF_FSNN: HOW_IT_WORKS_v3 (teoria) · VALIDATION_REPORT_v3 (risultati) e questo.',
            'Fase A "software_now": profilazione software pre-silicio (le Fasi B/C = HDL/board)',
            'Sorgente figure: scripts/fpga_figures.py (librerie weight/state/latency/seu/io) · risultati: results/evaluate/FPGA/',
        ],
    }))

    A(('toc', (
        'Sommario',
        ['Sezione', 'Contenuto'],
        [
            ['0', 'Readiness: la scorecard di idoneità FPGA'],
            ['1', 'Pesi Power-of-Two: il moltiplicatore che sparisce'],
            ['2', 'Fixed-point: formato Qm.n e robustezza alla quantizzazione'],
            ['3', 'Dinamica spiking: sparsità reale e salute della rete'],
            ['4', 'Energia: il vantaggio AC<MAC'],
            ['5', 'Timing / WCET: margine sul deadline e jitter zero'],
            ['6', 'Risorse e DSE: 0 DSP, <1% BRAM'],
            ['7', 'SEU / ISO 26262: robustezza ai bit-flip e TMR mirato'],
            ['8', 'I/O e Hardware-in-the-Loop: canale V2X e code'],
            ['9', 'Termico: derating (stime pre-sintesi)'],
            ['—', 'Verdetto e prossimi passi · Riferimenti · Mappa dei file'],
        ],
    )))

    # Intro
    A(('h1', 'In una pagina: cos\'è e come si legge'))
    A(('p', 'Questo report è la valutazione di idoneità FPGA dei 4 champion (2 BPTT: Raffaello, '
            'Leonardo; 2 EventProp: Donatello, Michelangelo) PRIMA di toccare il silicio. È la Fase A '
            '"software_now": ogni numero 🟢 è calcolato dai tensori e dal forward reali della rete. '
            'Le figure marcate 🟡/🔴 '
            '(datapath HDL, area, termico) sono STIME di progetto, da confermare con la sintesi '
            'Vivado e la misura su board (Fasi B/C).'))
    A(('p', 'Come si legge: la sezione 0 è il cruscotto (radar + tabella di numeri reali) con il '
            'verdetto di deploy; le sezioni 1-8 lo fondano dimensione per dimensione (pesi po2, '
            'fixed-point, spiking, energia, timing, risorse, SEU, I/O); la 9 è termica (stime). '
            'Contesto e teoria della rete: HOW_IT_WORKS_v3 §16. I risultati di validazione della guida '
            '(sicurezza, traffico, accuratezza): VALIDATION_REPORT_v3 (di cui §9 è il sommario FPGA che '
            'rimanda qui).'))
    A(('callout', f'Due verità che attraversano tutto il report: (1) i champion sparano '
                  f'~{SPK_LO}-{SPK_HI}%, non sono iper-sparsi; (2) il vantaggio energetico '
                  f'(~{ADVW_LO}-{ADVW_HI}×) viene dal costo AC<MAC e da 0 DSP, non dalla sparsità. '
                  f'L\'edge FPGA degli EventProp è ρ<1 (contrattivo) + 0 neuroni morti.'))

    # Tabella riassuntiva dei champion (dai CSV)
    if SCORE is not None and ENP is not None:
        rows = []
        for c in CHAMP:
            rows.append([c, METHOD[c], CKPT[c], sc(c, 'rho_po2', '%.2f'),
                         en(c, 'spike_rate_pct', '%.1f') + '%',
                         en(c, 'advantage_worstcase_x', '%.2f') + '×',
                         sc(c, 'footprint_B', '%.0f') + ' B'])
        A(('table', (['Champion', 'Metodo', 'Checkpoint', 'ρ(U·V)', 'spike %', 'energia × (worst)', 'footprint'], rows)))

    # Sezioni
    for section in SECTION_ORDER:
        A(('h1', SEC_TITLE.get(section, section)))
        for para in SEC_PROSE.get(section, []):
            A(('p', para))
        for eqp, eqc in SEC_EQ.get(section, []):
            A(('img', (eqp, eqc)))
        for dest, cap in _figs(section):
            A(('img', (dest, cap)))

    # Verdetto
    A(('h1', 'Verdetto e prossimi passi'))
    A(('p', f'Sul profilo pre-silicio il candidato al deploy è **Donatello** (EventProp): ricorrenza '
            f'contrattiva (ρ≈{DON_RHO} → fixed-point sicuro), quantizzazione po2 robusta, 0 neuroni morti, '
            f'timing e risorse soddisfatti con margine enorme (0 DSP, <1% BRAM, µs vs 100 ms). Il '
            f'rovescio onesto: essendo il più attivo (~{DON_SPK}% firing) ha il vantaggio energetico più '
            f'basso (~{DON_ADV}×); e **Leonardo** resta il più fragile su quantizzazione e SEU.'))
    A(('callout', 'Cosa è REALE e cosa è STIMA. Reali (🟢): readiness, pesi po2, spiking, energia (modello '
                  'Horowitz), op-count/timing, footprint/BRAM, SEU (fault-injection SW). Stime (🟡/🔴): '
                  'area LUT/FF, datapath del decode, overhead TMR, coda RX, termico. Le stime si '
                  'confermano solo in Fase B (sintesi Vivado → LUT/FF/DSP/Fmax reali) e Fase C '
                  '(FPGA-in-the-Loop → potenza/latenza/SEU su silicio).'))

    # Riferimenti
    A(('h1', 'Riferimenti'))
    A(('table', (
        ['Riferimento', 'Tema'],
        [
            ['Volder, J.E. (1959). The CORDIC trigonometric computing technique. IRE Trans. Electronic Computers EC-8(3), 330–334.', 'CORDIC per il decode (§5)'],
            ['Kleinrock, L. (1975). Queueing Systems, Volume 1: Theory. Wiley.', 'Coda M/M/1/K (§8)'],
            ['JEDEC JESD89A (2006). Measurement and Reporting of Alpha Particle and Terrestrial Cosmic Ray-Induced Soft Errors in Semiconductor Devices. JEDEC.', 'Soft error / SEU (§7)'],
            ['Kaul, S., Yates, R., Gruteser, M. (2012). Real-time status: how often should one update? IEEE INFOCOM, 2731–2735.', 'Age-of-Information (§8)'],
            ['Treiber, M., Kesting, A. (2025). Traffic Flow Dynamics: Data, Models and Simulation. Springer.', 'Controllore ACC-IIDM (§5)'],
            ['Horowitz, M. (2014). Computing\'s energy problem (and what we can do about it). IEEE Int. Solid-State Circuits Conf. (ISSCC), 10–14.', 'Energia AC/MAC (§4)'],
            ['Miyashita, D., Lee, E.H., Murmann, B. (2016). Convolutional neural networks using logarithmic data representation. arXiv:1603.01025.', 'Quantizzazione logaritmica / po2 (§1, §2)'],
            ['Xilinx (2018). Zynq-7000 SoC Data Sheet: Overview (DS190). Xilinx.', 'Budget Zynq-7020: BRAM, Tj (§6, §9)'],
            ['ISO 26262 (2018). Road vehicles — Functional safety. ISO, Ginevra.', 'Sicurezza funzionale (§7)'],
            ['Neftci, E.O., Mostafa, H., Zenke, F. (2019). Surrogate gradient learning in spiking neural networks. IEEE Signal Processing Magazine 36(6), 51–63.', 'Champion BPTT'],
            ['ETSI EN 302 637-2 (2019). Intelligent Transport Systems; Cooperative Awareness Basic Service (CAM). ETSI.', 'V2X / CAM (§8)'],
            ['Wunderlich, T.C., Pehle, C. (2021). Event-based backpropagation can compute exact gradients for spiking neural networks. Scientific Reports 11, 12829.', 'Champion EventProp'],
        ],
    )))

    # Mappa file
    A(('h1', 'Riproducibilità e mappa dei file'))
    A(('table', (['Cosa', 'Dove'], [
        ['Figure e CSV FPGA (45 figure, 10 sez.)', 'results/evaluate/FPGA/'],
        ['Generatore figure (dati reali)', 'scripts/fpga_figures.py'],
        ['Librerie Fase A', 'utils/{weight_profiler,state_profiler,latency_model,seu_inject,io_hil}.py'],
        ['Notebook FPGA-evaluate', 'Eval_FPGA.ipynb'],
        ['Verifica manifest post-run', 'scripts/verify_fpga_eval.py'],
        ['Questo report (generatore)', 'scripts/build_fpga_report.py'],
        ['Design e framework della valutazione', 'document/FPGA_EVALUATE_DESIGN.md / FPGA_EVALUATION_FRAMEWORK.md'],
        ['Teoria della rete (gemello)', 'document/HOW_IT_WORKS_v3.md'],
        ['Risultati di validazione (gemello)', 'document/VALIDATION_REPORT_v3.md (§9 = sommario FPGA)'],
    ])))
    return D


# ---------------------------------------------------------------------------
# Render Markdown
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
        elif kind == 'toc':
            title, headers, rows = b
            L.append(f"\n## {title}\n")
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
# Render PDF (reportlab)
# ---------------------------------------------------------------------------
def render_pdf(doc, outpath):
    import matplotlib
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                    Table, TableStyle, PageBreak, HRFlowable)
    from reportlab.platypus.tableofcontents import TableOfContents
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import ImageReader

    fdir = os.path.join(os.path.dirname(matplotlib.__file__), 'mpl-data', 'fonts', 'ttf')
    pdfmetrics.registerFont(TTFont('DJ', os.path.join(fdir, 'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('DJ-B', os.path.join(fdir, 'DejaVuSans-Bold.ttf')))

    ss = getSampleStyleSheet()
    body = ParagraphStyle('body', parent=ss['Normal'], fontName='DJ', fontSize=9.5, leading=14, spaceAfter=6)
    h1 = ParagraphStyle('h1', fontName='DJ-B', fontSize=16, leading=20, spaceBefore=14, spaceAfter=2,
                        textColor=colors.HexColor('#1a3c6e'))
    h2 = ParagraphStyle('h2', fontName='DJ-B', fontSize=12.5, leading=16, spaceBefore=10, spaceAfter=2,
                        textColor=colors.HexColor('#26527a'))
    cap = ParagraphStyle('cap', parent=body, fontName='DJ', fontSize=8, leading=11,
                         textColor=colors.HexColor('#555555'), spaceAfter=10)
    callout = ParagraphStyle('callout', parent=body, fontName='DJ', fontSize=9.5, leading=14,
                             backColor=colors.HexColor('#eef4fb'), borderColor=colors.HexColor('#9bb8d8'),
                             borderWidth=0.6, spaceBefore=4, spaceAfter=10, borderPadding=5)

    def esc(s):
        import re
        s = str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
        return s

    usable_w = A4[0] - 3.6 * cm
    story = []

    def add_image(path, caption):
        img = ImageReader(path)
        iw, ih = img.getSize()
        if os.path.basename(path).startswith('eq_'):
            # equazioni: dimensione naturale (proporzionale al testo), centrate, non a piena pagina
            w = iw * 72.0 / EQ_DPI
            h = ih * 72.0 / EQ_DPI
            if w > usable_w:
                h *= usable_w / w; w = usable_w
            story.append(Spacer(1, 3))
            eqim = Image(path, width=w, height=h); eqim.hAlign = 'CENTER'
            story.append(eqim)
            story.append(Paragraph(esc(caption), cap))
            return
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
        data = [[Paragraph(f'<b>{esc(h)}</b>', ParagraphStyle('th', fontName='DJ-B', fontSize=fs,
                 leading=fs + 2, textColor=colors.white)) for h in headers]]
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
                txt = flowable.getPlainText()
                if txt in ('Sommario', 'Indice'):
                    return
                lvl = {'h1': 0, 'h2': 1, 'h3': 2}.get(flowable.style.name)
                if lvl is not None:
                    safe = txt.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    self.notify('TOCEntry', (lvl, safe, self.page))

    for kind, *rest in doc:
        b = rest[0] if rest else None
        if kind == 'cover':
            story.append(Spacer(1, 3.2 * cm))
            story.append(Paragraph(esc(b['title']), ParagraphStyle('ct', fontName='DJ-B', fontSize=23,
                         leading=29, textColor=colors.HexColor('#1a3c6e'), alignment=1)))
            story.append(Spacer(1, 0.5 * cm))
            story.append(Paragraph(esc(b['subtitle']), ParagraphStyle('cs', fontName='DJ', fontSize=12,
                         leading=17, textColor=colors.HexColor('#444444'), alignment=1)))
            story.append(Spacer(1, 1.4 * cm))
            story.append(HRFlowable(width='60%', thickness=1, color=colors.HexColor('#9bb8d8')))
            story.append(Spacer(1, 0.6 * cm))
            for m in b['meta']:
                story.append(Paragraph(esc(m), ParagraphStyle('cm', fontName='DJ', fontSize=10,
                             leading=15, alignment=1, textColor=colors.HexColor('#333333'))))
            story.append(PageBreak())
        elif kind == 'h1':
            story.append(Paragraph(esc(b), h1))
            story.append(HRFlowable(width='100%', thickness=0.8, color=colors.HexColor('#c5d3e2'), spaceAfter=6))
        elif kind == 'h2':
            story.append(Paragraph(esc(b), h2))
        elif kind == 'p':
            story.append(Paragraph(esc(b), body))
        elif kind == 'callout':
            story.append(Paragraph('<b>Nota.</b> ' + esc(b), callout))
        elif kind == 'table':
            make_table(*b)
        elif kind == 'toc':
            title, headers, rows = b
            story.append(Paragraph(esc(title), h1))
            story.append(HRFlowable(width='100%', thickness=0.9, color=colors.HexColor('#c5d3e2'), spaceAfter=8))
            story.append(toc)
        elif kind == 'img':
            add_image(*b)

    def footer(canvas, docx):
        canvas.saveState()
        canvas.setFont('DJ', 7.5)
        canvas.setFillColor(colors.HexColor('#888888'))
        canvas.drawString(2 * cm, 1.1 * cm, 'CF_FSNN — Report FPGA (Fase A)')
        canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f'pag. {docx.page}')
        canvas.restoreState()

    pdf = TOCDoc(outpath, pagesize=A4, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm, title='CF_FSNN Report FPGA Fase A')
    pdf.multiBuild(story, onFirstPage=footer, onLaterPages=footer)
    print('  scritto', outpath)


if __name__ == '__main__':
    assert os.path.isdir(EVAL), 'manca results/evaluate/FPGA/ — esegui prima il render (HB_AZURE)'
    n_png = len(glob.glob(os.path.join(EVAL, '*', '*.png')))
    print('[1/3] figure trovate:', n_png)
    DOC = build_doc()
    print('[2/3] render markdown...')
    render_md(DOC, os.path.join(DOCDIR, 'FPGA_REPORT.md'))
    print('[3/3] render pdf...')
    render_pdf(DOC, os.path.join(DOCDIR, 'FPGA_REPORT.pdf'))
    print('fatto.')
