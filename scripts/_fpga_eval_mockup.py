"""fpga_eval_mockup.py — prototipo FITTIZIO delle figure dell'FPGA-evaluate (dati dummy, nessun checkpoint).
v2: riformulate dopo il feedback (legende dei ruoli, messaggio HW esplicito, dominio-tempo dove piu chiaro).
Genera FPGA_evaluate_mockup.pdf: 1 figura per pagina.
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

plt.rcParams.update({'figure.dpi': 110, 'savefig.dpi': 110, 'font.size': 10, 'axes.titlesize': 12,
                     'axes.titleweight': 'bold', 'axes.grid': True, 'grid.alpha': 0.25, 'axes.axisbelow': True,
                     'legend.frameon': False, 'axes.spines.top': False, 'axes.spines.right': False})
CH = ['Raffaello', 'Leonardo', 'Donatello', 'Michelangelo']
COL = {'Raffaello': '#e34948', 'Leonardo': '#2a78d6', 'Donatello': '#4a3aa7', 'Michelangelo': '#eb6834'}
ORA, OCOL = 'Master Splinter', '#7f7f7f'
rng = np.random.default_rng(1)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'FPGA_evaluate_mockup.pdf')
pdf = PdfPages(OUT)
PG = [0]


def finish(fig, sec, name, feas, note=None):
    PG[0] += 1
    fig.suptitle('%s  ·  %s   [%s]' % (sec, name, feas), fontsize=13, fontweight='bold')
    if note:
        fig.text(0.5, 0.928, note, ha='center', fontsize=9, color='#444')
    fig.text(0.99, 0.01, 'mockup dati fittizi · pag %d' % PG[0], ha='right', fontsize=7, color='#999')
    fig.tight_layout(rect=[0, 0.02, 1, 0.90 if note else 0.95])
    pdf.savefig(fig); plt.close(fig)


def gbar(ax, cats, data, ylab):
    x = np.arange(len(cats)); w = 0.8 / len(CH)
    for i, c in enumerate(CH):
        ax.bar(x + i * w, data[c], w, color=COL[c], label=c)
    ax.set_xticks(x + 0.4 - w / 2); ax.set_xticklabels(cats); ax.set_ylabel(ylab)
    ax.legend(fontsize=7, ncol=4)


# ============================== 00 READINESS ==============================
def f_readiness_matrix():
    dims = ['Pesi', 'Fix-pt', 'Spike', 'Energia', 'Timing', 'Risorse', 'SEU', 'I/O', 'Termica']
    base = np.array([[.92, .86, .74, .80, .95, .90, .58, .82, .84],
                     [.93, .88, .82, .81, .95, .91, .66, .84, .85],
                     [.90, .84, .70, .78, .94, .89, .55, .80, .83],
                     [.91, .87, .78, .83, .95, .90, .62, .83, .84]])
    fig, ax = plt.subplots(figsize=(9, 4.2))
    im = ax.imshow(base, cmap='RdYlGn', vmin=0.4, vmax=1.0, aspect='auto')
    ax.set_xticks(range(len(dims))); ax.set_xticklabels(dims, rotation=20, fontsize=8)
    ax.set_yticks(range(4)); ax.set_yticklabels(CH)
    for i in range(4):
        for j in range(len(dims)):
            ax.text(j, i, '%.2f' % base[i, j], ha='center', va='center', fontsize=8)
    ax.grid(False); plt.colorbar(im, ax=ax, label='readiness (1 = FPGA-friendly)')
    finish(fig, '00', 'readiness_matrix', 'SW', 'colpo d occhio: chi e piu FPGA-friendly e dove (verde=pronto)')


def f_readiness_radar():
    axes_lbl = ['sparsita', 'footprint', 'DSP-free', 'WCET-margin', 'SEU-robust', 'energia x']
    ang = np.linspace(0, 2 * np.pi, len(axes_lbl), endpoint=False).tolist(); ang += ang[:1]
    fig, ax = plt.subplots(figsize=(7, 6.2), subplot_kw=dict(polar=True))
    for c in CH:
        v = (0.65 + 0.3 * rng.random(len(axes_lbl))).tolist(); v += v[:1]
        ax.plot(ang, v, color=COL[c], label=c); ax.fill(ang, v, color=COL[c], alpha=0.06)
    ax.set_xticks(ang[:-1]); ax.set_xticklabels(axes_lbl, fontsize=8); ax.set_ylim(0, 1)
    ax.legend(loc='upper right', bbox_to_anchor=(1.30, 1.12), fontsize=7)
    anc = ('ogni asse: 1 = REQUISITO di deploy soddisfatto, 0 = lontano\n'
           'sparsita 1=<2%  ·  footprint 1=<5% BRAM  ·  DSP-free 1=0 DSP\n'
           'WCET-margin 1=<1% deadline  ·  SEU-robust 1=0 bit critici  ·  energia 1=>20x')
    fig.text(0.02, 0.03, anc, fontsize=8, va='bottom', bbox=dict(boxstyle='round', fc='#f4f4f4', ec='#ccc'))
    finish(fig, '00', 'readiness_radar', 'SW', 'normalizzato su REQUISITI assoluti (non relativo tra champion) — legenda in basso a sx')


def f_deploy_verdict():
    fig, ax = plt.subplots(figsize=(9, 4.6)); ax.axis('off')
    rows = [['champion', 'sparsita', 'energia x', 'footprint', 'SEU crit.', 'verdetto'],
            ['Leonardo', '1.3%', '22x', '3.2 Kbit', 'medio', 'DEPLOY'],
            ['Michelangelo', '1.5%', '30x', '3.2 Kbit', 'medio', 'alt'],
            ['Raffaello', '1.4%', '22x', '3.2 Kbit', 'alto', 'ok'],
            ['Donatello', '1.9%', '26x', '3.2 Kbit', 'alto', 'rivedi']]
    t = ax.table(cellText=rows, loc='center', cellLoc='center')
    t.auto_set_font_size(False); t.set_fontsize(10); t.scale(1, 1.8)
    for j in range(6):
        t[0, j].set_facecolor('#eee'); t[0, j].set_text_props(weight='bold')
    t[1, 5].set_facecolor('#c9ecc9')
    gl = ('sparsita = % neuroni attivi/tick (meno = meno energia)   ·   energia x = risparmio vs ANN densa   ·   footprint = memoria pesi\n'
          'SEU crit. = quanto un bit-flip da radiazione (Single Event Upset) minaccia la sicurezza   ·   verdetto = raccomandazione di deploy')
    fig.text(0.5, 0.05, gl, ha='center', fontsize=8, color='#444')
    finish(fig, '00', 'deploy_verdict', 'SW', 'champion eletto + motivazione (legenda delle colonne in basso)')


# ============================== 01 WEIGHTS ==============================
def f_po2_alphabet():
    lv = ['-2', '-1', '-.5', '-.25', '-.13', '-.06', '0', '.06', '.13', '.25', '.5', '1', '2']
    cnt = [1, 19, 28, 49, 98, 120, 168, 120, 98, 49, 28, 19, 1]
    x = np.arange(len(lv))
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for i, cc in enumerate(cnt):
        col = OCOL if i == 6 else '#2a78d6'
        ax.plot([x[i], x[i]], [0, cc], color=col, lw=2); ax.plot(x[i], cc, 'o', color=col, ms=7)
    ax.set_xticks(x); ax.set_xticklabels(lv); ax.set_ylabel('# pesi (di 800)')
    ax.set_xlabel('valore sinaptico = sign*2^k, k in [-4,+1]')
    ax.annotate('0: 21% = eliminabili', (6, 168), textcoords='offset points', xytext=(6, 4), fontsize=8)
    finish(fig, '01', 'po2_alphabet', 'SW', 'il moltiplicatore sinaptico e UNO di 13 valori -> barrel-shifter, 0 DSP')


def f_resource_occupancy():
    res = ['LUT\n(53.2k)', 'FF\n(106.4k)', 'BRAM\n(140)', 'DSP\n(220)']
    base = {'Raffaello': [2.8, 0.9, 1.4, 0.0], 'Leonardo': [2.7, 0.9, 1.4, 0.0],
            'Donatello': [3.0, 1.0, 1.4, 0.0], 'Michelangelo': [2.9, 0.9, 1.4, 0.0]}
    fig, ax = plt.subplots(figsize=(9.2, 4.6)); x = np.arange(len(res)); w = 0.8 / len(CH)
    for i, c in enumerate(CH):
        b = ax.bar(x + i * w, base[c], w, color=COL[c], label=c)
        for j, v in enumerate(base[c]):
            ax.text(x[j] + i * w, v + 0.08, '%.1f' % v, ha='center', fontsize=6)
    ax.set_xticks(x + 0.4 - w / 2); ax.set_xticklabels(res); ax.set_ylabel('% del budget Zynq-7020 (budget pieno = 100%)')
    ax.set_ylim(0, 4.5); ax.legend(fontsize=7, ncol=4)
    finish(fig, '01', 'resource_occupancy', 'SW (LUT/FF stima, DSP/BRAM esatti)',
           'cross-champion: DSP 0% (po2=shift-add), tutto <3% del chip. Stessa topologia -> quasi identici; le VARIANTI d architettura divergerebbero')


def f_spectral():
    fig, ax = plt.subplots(figsize=(8.4, 5))
    for c in CH:
        b = 0.78 + 0.12 * rng.random(); r = 0.13 + 0.06 * rng.random()
        ax.scatter(b, r, s=70, color=COL[c], label=c, zorder=3)
        ax.scatter(b - 0.02, r - 0.02, s=70, facecolor='none', edgecolor=COL[c], zorder=3)
    ax.axhline(1.0, color='#e34948', ls='--', label='rho=1 confine stabilita')
    ax.set_xlim(0.7, 0.95); ax.set_ylim(0, 1.05); ax.set_xlabel('||U@V||_2 (gain worst-case/tick)')
    ax.set_ylabel('rho (raggio spettrale)'); ax.legend(fontsize=7)
    finish(fig, '01', 'spectral_recurrence', 'SW',
           'pieno=po2, vuoto=float · tutti rho<<1 -> loop contrattivo, pochi bit di guardia')


def f_sparsity_mask():
    mats = ['fc\n(in->hid 32x4)', 'rec_U\n(low-rank)', 'rec_V\n(low-rank)', 'out\n(readout ->5)']
    data = {c: [18 + 4 * rng.random(), 21 + 4 * rng.random(), 24 + 4 * rng.random(), 14 + 3 * rng.random()] for c in CH}
    fig, ax = plt.subplots(figsize=(9, 4.8)); gbar(ax, mats, data, '% pesi a zero (mask 2^-5)')
    finish(fig, '01', 'sparsity_mask', 'SW',
           'fc=feedforward input->hidden · rec_U,rec_V=ricorrenza low-rank · out=hidden->5 param · rec_V piu sparso -> piu eliminabili')


def f_po2_exponent_range():
    mats = ['fc (post-scaling √6)', 'rec_U', 'rec_V', 'out']
    lo = [-4, -4, -4, -4]; hi = [1, -1, -1, 0]; clamp = [8, 0, 0, 1]
    fig, ax = plt.subplots(figsize=(9, 4.4)); y = np.arange(len(mats))
    for i in range(len(mats)):
        ax.plot([lo[i], hi[i]], [y[i], y[i]], '-', color='#2a78d6', lw=6, solid_capstyle='round')
        ax.text(hi[i] + 0.15, y[i], '%d..%d -> %d bit esp.' % (lo[i], hi[i], max(1, int(np.ceil(np.log2(hi[i] - lo[i] + 1))))),
                va='center', fontsize=9)
        if clamp[i] > 0:
            ax.text(1.05, y[i] - 0.28, 'clamp +1: %d%%' % clamp[i], color='#e34948', fontsize=8)
    ax.set_yticks(y); ax.set_yticklabels(mats); ax.set_xlim(-5, 3); ax.set_xlabel('esponente k usato (2^k)')
    ax.axvline(1, color='#e34948', ls=':', lw=1)
    finish(fig, '01', 'po2_exponent_range', 'SW',
           'quanti bit di esponente servono per matrice; fc scalato di √6 tocca il clamp +1 (saturazione da verificare)')


# ============================== 02 FIXED-POINT ==============================
def f_bit_allocation():
    states = ['potential (memb. ALIF)', 'rec_int (ricorrenza)', 'LI (output raw)', 'fatigue (soglia ALIF)', 'corrente (sinaptica)']
    ints = [3, 2, 4, 1, 3]; fmt = ['Q4.8', 'Q3.8', 'Q5.8', 'Q2.8', 'Q4.8']; rng_s = [6.2, 3.1, 14.0, 1.4, 5.5]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    for i, s in enumerate(states):
        y = len(states) - 1 - i
        ax.barh(y, 1, left=0, color='#fab219', edgecolor='w')
        ax.barh(y, ints[i], left=1, color='#2a78d6', edgecolor='w')
        ax.barh(y, 8, left=1 + ints[i], color='#dfe8f5', edgecolor='#2a78d6')
        ax.text(1 + ints[i] + 4, y, 'x8 frac', ha='center', va='center', fontsize=8)
        ax.text(14.3, y, '%s' % fmt[i], va='center', fontsize=10, weight='bold')
        ax.text(17.2, y, 'range meas. +-%.1f' % rng_s[i], va='center', fontsize=8, color='#555')
    ax.set_yticks(range(len(states))); ax.set_yticklabels(states[::-1]); ax.set_xlim(0, 22)
    ax.set_xlabel('bit  (giallo=segno, blu=interi da RANGE, azzurro=frazionari x8 da leak)'); ax.grid(False)
    finish(fig, '02', 'bit_allocation', 'SW',
           'formato Qm.n per stato: gli int_bits vengono dal RANGE MISURATO (colonna a destra) -> +-6.2 = min/max osservato')


def f_state_ranges():
    states = ['potential\n(memb. ALIF)', 'rec_int\n(ricorrenza)', 'LI\n(output raw)', 'fatigue\n(soglia ALIF)', 'corrente\n(sinaptica)']
    lo = np.array([-6, -3, -14, 0, -5.5]); hi = np.array([6.2, 3.1, 14, 1.4, 5.5])
    fig, ax = plt.subplots(figsize=(9, 5)); y = np.arange(len(states))
    for c in CH:
        off = (CH.index(c) - 1.5) * 0.16
        ll = lo * (0.9 + 0.1 * rng.random()); hh = hi * (0.9 + 0.1 * rng.random())
        ax.hlines(y + off, ll, hh, color=COL[c], lw=3, alpha=0.75)
        ax.plot(ll * 0.7, y + off, '|', color=COL[c], ms=8); ax.plot(hh * 0.7, y + off, '|', color=COL[c], ms=8)
    ax.set_yticks(y); ax.set_yticklabels(states); ax.set_xlabel('range dinamico min..max  (| = p1/p99)')
    ax.legend([plt.Line2D([0], [0], color=COL[c], lw=3) for c in CH], CH, fontsize=7, ncol=4)
    finish(fig, '02', 'state_ranges', 'SW',
           'i 5 registri interni fixed-point (2 sono gli stati ALIF): l ampiezza del range fissa gli int_bits di bit_allocation')


def f_quant_vs_bits():
    bits = [12, 8, 6, 4, 3, 2]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.6))
    for c in CH:
        idf = 0.15 + 0.02 * rng.random() + np.array([0, 0, .002, .01, .06, .25])
        ax[0].plot(bits, idf, 'o-', color=COL[c], label=c + ' fix')
        ax[0].plot(bits, idf + 0.01, 's--', color=COL[c], alpha=0.6)
        ax[1].plot(bits, 0.07 + np.array([0, 0, 0, .002, .03, .12]) * (1 + rng.random()), 'o-', color=COL[c])
    ax[0].set_xlabel('bit-width pesi (<-)'); ax[0].set_ylabel('errore id.'); ax[0].invert_xaxis(); ax[0].legend(fontsize=6, ncol=2)
    ax[0].set_title('linea=fixed, tratteg.=po2'); ax[1].set_xlabel('bit-width'); ax[1].set_ylabel('collision_rate'); ax[1].invert_xaxis()
    ax[1].set_title('sicurezza vs bit')
    finish(fig, '02', 'quant_vs_bits', 'SW / re-train',
           'bit-budget minimo dei pesi (curva ONESTA solo con re-training QAT a ogni bit-width)')


def f_perparam_fragility():
    P = ['v0', 'T', 's0', 'a', 'b']
    M = np.array([[.02, .05, .01, .06, .09], [.01, .06, .02, .04, .11],
                  [.03, .04, .02, .05, .07], [.02, .05, .02, .05, .10]])
    fig, ax = plt.subplots(figsize=(8, 4.4)); im = ax.imshow(M, cmap='YlOrRd', aspect='auto')
    ax.set_xticks(range(5)); ax.set_xticklabels(P); ax.set_yticks(range(4)); ax.set_yticklabels(CH)
    for i in range(4):
        for j in range(5):
            ax.text(j, i, '%.2f' % M[i, j], ha='center', va='center', fontsize=8)
    ax.grid(False); plt.colorbar(im, ax=ax, label='|d param| a 4-bit vs float')
    finish(fig, '02', 'per_param_fragility', 'SW', "quale dei 5 param cede prima sotto quantizzazione: 'b' (frenata) il piu fragile")


def f_chattering():
    t = np.linspace(0, 20, 400)
    base = 0.6 * np.sin(t / 2)
    fig, ax = plt.subplots(2, 1, figsize=(9, 5.4))
    ax[0].plot(t, base, color='#888', label='float (liscio)')
    ax[0].plot(t, base + 0.15 * np.sin(t * 6) * (rng.random(len(t)) > 0.3), color='#2a78d6', label='po2', alpha=0.8)
    ax[0].plot(t, base + 0.45 * np.sin(t * 9) * (rng.random(len(t)) > 0.2), color='#e34948', label='quant 4b (nervoso)', alpha=0.8)
    ax[0].set_ylabel('a_ego [m/s2]'); ax[0].legend(fontsize=7, ncol=3); ax[0].set_title('comando: liscio (float) vs nervoso (quant) — si VEDE', fontsize=10)
    f = np.linspace(0.01, 5, 200)
    for lab, sc, cc in [('float', 1.0, '#888'), ('po2', 1.6, '#2a78d6'), ('quant 4b', 3.0, '#e34948')]:
        ax[1].semilogy(f, sc / (1 + (f / 0.3) ** 2) + 0.02 * sc * (f > 0.5), color=cc, label=lab)
    ax[1].axvspan(0.5, 5, color='#e34948', alpha=0.06); ax[1].set_xlabel('freq [Hz]'); ax[1].set_ylabel('PSD (log)')
    ax[1].set_title('quantificazione: energia nella banda >0.5 Hz (zona rossa) = chattering', fontsize=10)
    finish(fig, '02', 'chattering', 'SW', 'instabilita = accelerazione nervosa indotta dalla quantizzazione')


def f_leak_decay():
    tk = np.arange(0, 30)
    p0 = 4.0
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(tk, p0 * (7 / 8.0) ** tk, 'o-', color='#888', label='float (decade a ~0)')
    ax.plot(tk, np.maximum(p0 * (7 / 8.0) ** tk, 0.9), 's-', color='#e34948', label='fixed 4-bit (si INCASTRA a ~0.9)')
    ax.plot(tk, np.maximum(p0 * (7 / 8.0) ** tk, 0.06), '^-', color='#2a78d6', label='fixed 8-bit (~float)')
    ax.set_xlabel('tick (senza nuovo input)'); ax.set_ylabel('potential ALIF'); ax.legend(fontsize=8)
    finish(fig, '02', 'leak_decay', 'SW',
           'leak = potential>>3: a pochi frac_bits il decadimento sotto-flussa e il potenziale resta BLOCCATO (rosso)')


# ============================== 03 SPIKING ==============================
def f_activity_map():
    rate = np.clip(rng.exponential(0.08, (4, 32)), 0, 1)
    dead = rng.choice(32, 5, replace=False)
    rate[:, dead] = 0
    fig, ax = plt.subplots(figsize=(10, 3.6)); im = ax.imshow(rate, cmap='magma', aspect='auto', vmin=0, vmax=0.4)
    for d in dead:
        ax.add_patch(plt.Rectangle((d - 0.5, -0.5), 1, 4, fill=False, edgecolor='cyan', lw=1.2, ls=':'))
    ax.set_yticks(range(4)); ax.set_yticklabels(CH); ax.set_xlabel('neurone hidden (0..31)')
    ax.grid(False); plt.colorbar(im, ax=ax, label='firing rate')
    finish(fig, '03', 'activity_map', 'SW', 'hotspot energetici vs neuroni MORTI (ciano tratteggiato = rate 0, pruning)')


def f_raster():
    T = 300
    fig = plt.figure(figsize=(10, 4.6))
    gs = fig.add_gridspec(2, 2, width_ratios=[5, 1], height_ratios=[4, 1], hspace=0.05, wspace=0.03)
    axr = fig.add_subplot(gs[0, 0]); axr_r = fig.add_subplot(gs[0, 1], sharey=axr); axr_b = fig.add_subplot(gs[1, 0], sharex=axr)
    rates = np.sort(rng.exponential(0.06, 32))[::-1]
    R = (rng.random((32, T)) < rates[:, None]).astype(float)
    ys, xs = np.where(R > 0)
    axr.scatter(xs, ys, s=3, color='#2a78d6'); axr.axvline(150, color='#e34948', ls='--', alpha=0.5)
    axr.set_ylabel('neurone (ordinato per rate)'); axr.grid(False); axr.tick_params(labelbottom=False)
    axr_r.barh(np.arange(32), R.sum(1), color='#9467bd'); axr_r.grid(False); axr_r.tick_params(labelleft=False); axr_r.set_xlabel('tot/neur')
    axr_b.plot(np.arange(T), R.sum(0), color='#1baf7a'); axr_b.set_xlabel('tick'); axr_b.set_ylabel('att/tick'); axr_b.grid(False)
    finish(fig, '03', 'raster (1 strato: baseline)', 'SW',
           'ordinato per firing-rate + marginali (per-neurone e per-tick); per varianti multi-strato = 1 pannello/strato (o HTML interattivo)')


def f_sparsity_tick():
    t = np.arange(300); act = np.clip(2 + 1.5 * np.sin(t / 20) + rng.normal(0, 0.4, 300) + 3 * (t > 150) * np.exp(-(t - 150) / 40), 0, None)
    fig, ax = plt.subplots(figsize=(9, 4.4)); ax.plot(t, act, color='#9467bd')
    pk = act.max()
    ax.axhline(pk, color='#e34948', ls='--', label='picco concorrente -> dimensiona albero AC + throughput')
    ax.axvline(150, color='#888', ls=':', label='evento cut-in')
    ax.set_xlabel('tick'); ax.set_ylabel('# spike concorrenti / tick'); ax.legend(fontsize=8)
    finish(fig, '03', 'sparsity_per_tick', 'SW', 'il MAX di spike simultanei fissa la larghezza dell albero di accumulo')


def f_isi():
    isi = rng.exponential(9, 4000)
    fig, ax = plt.subplots(figsize=(9, 4.2)); ax.hist(isi, bins=40, color='#1baf7a', edgecolor='w')
    ax.set_xlabel('inter-spike interval [tick]'); ax.set_ylabel('conteggio')
    finish(fig, '03', 'isi_dist', 'SW', 'ISI minimo -> massima freq istantanea -> worst-case accumulazione back-to-back')


def f_dead_sat():
    data = {c: [rng.integers(8, 16), rng.integers(0, 3)] for c in CH}
    fig, ax = plt.subplots(figsize=(9, 4.6)); gbar(ax, ['morti (rate=0)', 'saturi (rate~1)'], data, '# neuroni (di 32)')
    ax.text(0.02, 0.92, 'morti -> PRUNING (rimuovi LUT/FF)\nsaturi -> output costante -> COSTANTE hardwired (rimuovi il neurone)',
            transform=ax.transAxes, fontsize=9, va='top', bbox=dict(boxstyle='round', fc='#f4f4f4', ec='#ccc'))
    finish(fig, '03', 'dead_saturated', 'SW', 'entrambe le categorie sono semplificabili in hardware, in modi diversi')


# ============================== 04 ENERGY ==============================
def f_energy_breakdown():
    comp = ['fc shift-add', 'rec_V AC', 'rec_U shift-add', 'out AC', 'leak/fatica/reset', 'decode+IDM']
    val = [40, 22, 60, 14, 18, 90]
    fig, ax = plt.subplots(figsize=(9, 4.6)); c = plt.cm.Blues(np.linspace(0.4, 0.9, len(comp)))
    ax.bar(comp, val, color=c); ax.set_ylabel('energia [pJ] (stima Horowitz)'); ax.tick_params(axis='x', rotation=20)
    finish(fig, '04', 'energy_breakdown', 'SW', 'dove si spendono i pJ (incluse le op non-sinaptiche: leak/fatica/reset)')


def f_energy_vs_ann():
    x = np.arange(len(CH)); w = 0.35
    fig, ax = plt.subplots(figsize=(9, 4.6))
    snn_shift = np.array([4 + rng.random() for _ in CH]); snn_ac = np.array([4 + rng.random() for _ in CH])
    ann_mac = np.array([180 + 120 * rng.random() for _ in CH])
    ax.bar(x - w / 2, snn_shift, w, color='#2a78d6', label='SNN: shift-add (po2)')
    ax.bar(x - w / 2, snn_ac, w, bottom=snn_shift, color='#1baf7a', label='SNN: AC (spike)')
    ax.bar(x + w / 2, ann_mac, w, color='#888', label='ANN: MAC')
    ax.set_yscale('log'); ax.set_xticks(x); ax.set_xticklabels(CH); ax.set_ylabel('energia/inferenza [nJ] (log)')
    ax.legend(fontsize=7, ncol=3)
    finish(fig, '04', 'energy_vs_ann', 'SW', 'non solo MENO energia ma un MIX diverso: SNN=0 MAC (solo AC+shift), ANN=tutto MAC')


def f_energy_vs_rate():
    rate = np.linspace(0.5, 5, 30)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for c in CH:
        ax.plot(rate, 4 + rate * (2 + rng.random()), color=COL[c], label=c)
    ax.set_xlabel('spike-rate [%]'); ax.set_ylabel('energia [nJ]'); ax.legend(fontsize=7)
    finish(fig, '04', 'energy_vs_rate', 'SW', 'quanto scende l energia se un regularizer abbassa il firing-rate')


def f_synops_split():
    data = {c: [3200, 900 + 300 * rng.random()] for c in CH}
    fig, ax = plt.subplots(figsize=(9, 4.4)); gbar(ax, ['statico (input fc, sempre-on)', 'dinamico (event-driven)'], data, 'SynOps / inferenza')
    finish(fig, '04', 'synops_split', 'SW', 'la parte sempre-on vs quella guidata da spike -> dove conviene il clock-gating')


# ============================== 05 TIMING ==============================
def f_op_count():
    comp = ['fc', 'rec_V (st.1)', 'rec_U (st.2)', 'out', 'leak/fat/reset']
    val = [128, 256, 256, 160, 111]
    fig, ax = plt.subplots(figsize=(9, 4.2)); ax.bar(comp, val, color='#2a78d6')
    ax.set_ylabel('op / tick')
    finish(fig, '05', 'op_count', 'SW', 'il conteggio operazioni e l INPUT del WCET: ~800 op/tick x10 tick = 8000/step')


def f_wcet_cycles():
    prof = ['serial\n(1 unita)', 'per-neurone\n(32 unita)', 'pipeline']
    cyc = [8000, 260, 90]; us200 = [c / 200.0 for c in cyc]
    fig, ax = plt.subplots(figsize=(9, 4.4)); y = np.arange(len(prof))
    ax.barh(y, cyc, color=['#8899aa', '#2a78d6', '#0ca30c'])
    for i, (cc, u) in enumerate(zip(cyc, us200)):
        ax.text(cc * 1.1, i, '%d cicli = %.2f us @200MHz' % (cc, u), va='center', fontsize=9)
    ax.set_yticks(y); ax.set_yticklabels(prof); ax.set_xscale('log'); ax.set_xlim(50, 30000)
    ax.set_xlabel('cicli per inferenza (log) — meno unita = piu cicli')
    finish(fig, '05', 'wcet_cycles', 'SW', 'come leggerlo: quanti cicli (e us) serve una inferenza secondo 3 architetture HW')


def f_latency_margin():
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.barh([0], [100000], color='#f2f2f2', edgecolor='#888')
    ax.barh([0], [1.3], color='#2a78d6')
    ax.set_yticks([0]); ax.set_yticklabels(['budget']); ax.set_xscale('log'); ax.set_xlim(0.1, 2e5)
    ax.set_xlabel('tempo [us] (log)')
    ax.annotate('inferenza ~1.3 us', (1.3, 0), xytext=(20, 0.3), fontsize=9, color='#2a78d6',
                arrowprops=dict(arrowstyle='->', color='#2a78d6'))
    ax.annotate('deadline 100 ms', (100000, 0), xytext=(3000, -0.35), fontsize=9,
                arrowprops=dict(arrowstyle='->'))
    finish(fig, '05', 'latency_margin', 'SW', 'l inferenza e un puntino rispetto alla deadline -> margine ~3 ordini di grandezza')


def f_jitter_proof():
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar([0, 1, 2], [8000, 8000, 8000], color='#2a78d6')
    ax.set_xticks([0, 1, 2]); ax.set_xticklabels(['input spike 1%', 'input spike 15%', 'input spike 30%'])
    ax.set_ylabel('# op / inferenza'); ax.set_ylim(0, 9000)
    ax.text(1, 8300, 'IDENTICO', ha='center', fontsize=11, weight='bold', color='#0ca30c')
    finish(fig, '05', 'jitter_proof', 'SW', 'stesso #op qualunque siano i dati -> tempo costante -> jitter di calcolo = 0 (WCET==BCET)')


def f_decode_cp():
    comp = ['sigmoid x5 (LUT)', 'sqrt(ab)', 'div', 'tanh CAH', 'add/mul']
    val = [12, 18, 22, 16, 8]
    fig, ax = plt.subplots(figsize=(9, 4.2)); ax.bar(comp, val, color='#eb6834')
    ax.set_ylabel('cicli (stima)'); ax.tick_params(axis='x', rotation=15)
    finish(fig, '05', 'decode_criticalpath', 'SW', 'il decode (sigmoid+IDM) e l unico blocco con mul/div reali -> collo di Fmax + unico uso di DSP')


# ============================== 06 RESOURCES ==============================
def f_op_celltype():
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.bar(['AC (spike-driven)', 'shift-add (denso, po2)'], [416, 384], color=['#1baf7a', '#2a78d6'])
    ax.set_ylabel('celle / tick')
    finish(fig, '06', 'op_by_celltype', 'SW', 'recV+LI = accumulate (AC) ; fc+recU = shift-add ; nessuna e un moltiplicatore -> 0 DSP')


def f_dse_pareto():
    units = [1, 4, 8, 32, 64, 800]
    area = [30, 120, 240, 900, 1800, 22000]; lat = [8000, 2000, 1000, 260, 130, 12]
    fig, ax = plt.subplots(figsize=(9, 4.8)); ax.plot(area, lat, 'o-', color='#4a3aa7')
    for u, a, l in zip(units, area, lat):
        ax.annotate('%d unita' % u, (a, l), textcoords='offset points', xytext=(6, 6), fontsize=8)
    ax.scatter([900], [260], s=200, facecolor='none', edgecolor='#0ca30c', lw=2)
    ax.annotate('sweet spot', (900, 260), textcoords='offset points', xytext=(10, -18), fontsize=9, color='#0ca30c')
    ax.set_xscale('log'); ax.set_yscale('log'); ax.set_xlabel('area (LUT stimati)  ->'); ax.set_ylabel('latenza (cicli/tick)  <-')
    finish(fig, '06', 'dse_pareto', 'SW',
           'ogni punto = una scelta HW (quante unita di calcolo in parallelo): piu unita = piu veloce ma piu area')


def f_area_model():
    parts = ['ALIF (32)', 'low-rank U/V', 'LI+decode', 'delay-line', 'controllo']
    lut = [900, 500, 700, 200, 300]; ff = [300, 100, 80, 240, 120]
    x = np.arange(len(parts))
    fig, ax = plt.subplots(figsize=(9, 4.4)); ax.bar(x, lut, 0.4, label='LUT', color='#2a78d6'); ax.bar(x + 0.4, ff, 0.4, label='FF', color='#1baf7a')
    ax.set_xticks(x + 0.2); ax.set_xticklabels(parts, rotation=15, fontsize=8); ax.set_ylabel('# (stima da grafo)'); ax.legend(fontsize=8)
    finish(fig, '06', 'area_model', 'SW', 'stima parametrica di LUT/FF per blocco, PRIMA della sintesi')


def f_bram_dim():
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.bar(['pesi', 'stati', 'delay-map', 'BUDGET 140'], [0.4, 0.5, 0.3, 140], color=['#2a78d6', '#1baf7a', '#eda100', '#ddd'])
    ax.set_yscale('log'); ax.set_ylabel('# BRAM (36Kb)')
    finish(fig, '06', 'bram_dimensioning', 'SW', 'memoria on-chip: 1-3 BRAM su 140 (<2%)')


# ============================== 07 SEU (ISO 26262) ==============================
def f_seu_intro():
    fig, ax = plt.subplots(figsize=(9, 4.4)); ax.axis('off')
    txt = ("07 — SEU (Single Event Upset)\n\n"
           "Un neutrone atmosferico puo invertire UN bit nella memoria che contiene i pesi\n"
           "della rete (0->1 o 1->0): un 'bit-flip'. Il peso corrotto cambia -> i 5 parametri\n"
           "cambiano -> l accelerazione comandata cambia -> possibile collisione.\n\n"
           "Domanda della sezione: quanto e pericoloso? quali bit vanno protetti (ECC/TMR)?\n"
           "Tutto simulabile ORA: corrompo i tensori .pt e rilancio eval_safety.")
    ax.text(0.03, 0.95, txt, va='top', fontsize=12, family='monospace')
    finish(fig, '07', 'concept — cosa sono i bit-flip', 'SW', None)


def f_seu_sensitivity():
    M = rng.random((16, 4)) ** 3
    M[15] *= 3; M[14] *= 2
    fig, ax = plt.subplots(figsize=(7.6, 5)); im = ax.imshow(M, cmap='inferno', aspect='auto')
    ax.set_xticks(range(4)); ax.set_xticklabels(['segno', 'exp-MSB', 'exp-mid', 'exp-LSB'])
    ax.set_ylabel('peso (campione di 800)'); ax.grid(False); plt.colorbar(im, ax=ax, label='aumento collision_rate se quel bit si inverte')
    finish(fig, '07', 'sensitivity_map', 'SW', 'se si inverte 1 bit di un peso, di quanto sale il rischio collisione? (chiaro=pericoloso)')


def f_bit_criticality():
    pos = ['segno', 'exp-MSB', 'exp-mid', 'exp-LSB']; val = [0.42, 0.31, 0.18, 0.09]
    fig, ax = plt.subplots(figsize=(8.4, 4.2)); ax.bar(pos, val, color='#d03b3b')
    ax.set_ylabel('rischio medio (aumento collisione)')
    finish(fig, '07', 'bit_criticality', 'SW', '90% del rischio in 2 bit su 4 -> proteggere con ECC solo quelli')


def f_degrade_flips():
    k = [0, 1, 2, 4, 8, 16]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for c in CH:
        ax.plot(k, (0.07 + 0.005 * rng.random()) + np.array([0, .01, .03, .07, .16, .32]) * (0.9 + 0.2 * rng.random()), 'o-', color=COL[c], label=c)
    ax.set_xlabel('# bit-flip accumulati (prima che lo scrubbing li ripari)'); ax.set_ylabel('collision_rate'); ax.legend(fontsize=7)
    finish(fig, '07', 'degrade_vs_flips', 'SW', 'quanti SEU puo accumulare la rete prima di diventare insicura -> fissa il periodo di scrubbing')


def f_perparam_shift():
    P = ['v0', 'T', 's0', 'a', 'b']
    M = np.abs(rng.normal(0, 1, (4, 5))) * np.array([0.5, 0.8, 0.4, 1.0, 1.3])
    fig, ax = plt.subplots(figsize=(8, 4.2)); im = ax.imshow(M, cmap='YlOrRd', aspect='auto')
    ax.set_xticks(range(5)); ax.set_xticklabels(P); ax.set_yticks(range(4)); ax.set_yticklabels(CH)
    ax.grid(False); plt.colorbar(im, ax=ax, label='spostamento medio del param sotto SEU')
    finish(fig, '07', 'perparam_shift', 'SW', 'quale parametro si sposta di piu quando un peso e corrotto: a,b (frenata) i piu fragili')


def f_hidden_vs_readout():
    data = {c: [rng.random() * 0.3, 0.6 + 0.3 * rng.random()] for c in CH}
    fig, ax = plt.subplots(figsize=(8.4, 4.2)); gbar(ax, ['hidden (640 pesi)', 'readout out_fc (160 pesi)'], data, 'criticita relativa')
    finish(fig, '07', 'hidden_vs_readout', 'SW', 'il readout (1:1 sui canali) e molto piu critico -> TMR su solo ~20% dei pesi')


def f_tmr_overhead():
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.bar(['baseline', 'TMR selettivo', 'TMR full', 'BRAM-ECC'], [100, 145, 300, 105], color=['#888', '#1baf7a', '#e34948', '#2a78d6'])
    ax.axhline(100, color='k', ls=':'); ax.set_ylabel('% area vs baseline')
    finish(fig, '07', 'tmr_overhead', 'HDL (mockup)', 'costo area delle mitigazioni: TMR full +200%, ECC quasi gratis')


# ============================== 08 I/O HIL ==============================
def f_aoi_surface():
    s = np.linspace(5, 60, 40); dv = np.linspace(0, 15, 30)
    S, DV = np.meshgrid(s, dv)
    aoi_max = np.clip((S - 5) / (DV + 1) * 0.08, 0, 1.2)
    fig, ax = plt.subplots(figsize=(9, 4.8)); im = ax.imshow(aoi_max, origin='lower', aspect='auto', cmap='RdYlGn',
                                                             extent=[5, 60, 0, 15])
    cs = ax.contour(S, DV, aoi_max, levels=[0.1], colors='k', linewidths=1.5)
    ax.clabel(cs, fmt='latenza bus reale 0.1s', fontsize=8)
    ax.set_xlabel('gap s [m]  (piccolo = pericoloso)'); ax.set_ylabel('Dv chiusura [m/s] (alto = pericoloso)')
    plt.colorbar(im, ax=ax, label='AoI_max tollerabile [s]'); ax.grid(False)
    finish(fig, '08', 'aoi_max_surface', 'SW',
           'in ogni stato: eta MAX del CAM oltre cui e insicuro. Rosso (gap piccolo+chiusura alta) = il bus DEVE essere velocissimo; sotto la linea nera = bus troppo lento')


def f_aoi_dist():
    aoi = np.abs(rng.normal(0.1, 0.08, 5000))
    fig, ax = plt.subplots(figsize=(9, 4.2)); ax.hist(aoi, bins=40, color='#eda100', edgecolor='w')
    ax.axvline(0.3, color='#e34948', ls='--', label='AoI_max (soglia hard di sicurezza)'); ax.set_xlabel('Age-of-Information [s]'); ax.set_ylabel('conteggio')
    ax.legend(fontsize=8)
    finish(fig, '08', 'aoi_dist', 'SW', 'quanto spesso la rete gira su dati vecchi: la coda a destra deve stare sotto la soglia rossa')


def f_queue_overflow():
    D = np.arange(1, 12)
    fig, ax = plt.subplots(figsize=(9, 4.2)); ax.plot(D, np.clip(np.exp(-(D - 1) / 2.0), 0, 1), 'o-', color='#e34948')
    ax.set_xlabel('profondita coda RX (# messaggi)'); ax.set_ylabel('prob. di perdere un CAM su un burst')
    finish(fig, '08', 'queue_overflow', 'SW', 'quanto deve essere profonda la coda dei CAM in arrivo per non perderne durante una raffica')


def f_holdmode():
    data = {c: [0.07 + 0.01 * rng.random(), 0.07 + 0.01 * rng.random(), 0.25 + 0.05 * rng.random()] for c in CH}
    fig, ax = plt.subplots(figsize=(9, 4.4)); gbar(ax, ['hold_last', 'dead_reckon', 'blind'], data, 'collision_rate (PDR=0.5)')
    finish(fig, '08', 'holdmode', 'SW', 'come gestire un CAM perso: blind (senza hold) scopre il crollo, dead_reckon lo compensa')


def f_pdr_knee():
    lat = [0, 1, 2, 3]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for c in CH:
        ax.plot(lat, 0.05 + np.array([0, .005, .01, .03]) * (1 + rng.random()), 'o-', color=COL[c], label=c)
    ax.set_xlabel('latenza CAM [step da 0.1s]'); ax.set_ylabel('p5 min_TTC (piu basso = piu pericoloso)'); ax.legend(fontsize=7)
    finish(fig, '08', 'pdr_latency_knee', 'SW', 'degrado graceful sulla perdita pacchetti, ma il margine crolla con la latenza')


# ============================== 09 THERMAL ==============================
def f_derating():
    tj = np.linspace(25, 125, 50)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(tj, 220 * (1 - (tj - 25) / 100 * 0.28), color='#e34948', label='Fmax(Tj)')
    ax.axhline(100, color='#2a78d6', ls='--', label='target 100 MHz'); ax.axvline(100, color='#888', ls=':', label='Tj automotive ~100C')
    ax.set_xlabel('temperatura giunzione Tj [C]'); ax.set_ylabel('Fmax [MHz] (stima)'); ax.legend(fontsize=8)
    finish(fig, '09', 'derating_tj_fmax', 'HDL (mockup)', 'a caldo il clock massimo scende: resta headroom sul target a 100C?')


def f_thermal_budget():
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.bar(['SNN (0 DSP)', 'ANN densa'], [0.35, 1.8], color=['#1baf7a', '#888'])
    ax.axhline(2.0, color='#e34948', ls='--', label='budget passivo ECU (senza ventola)')
    ax.set_ylabel('P stimata [W]'); ax.legend(fontsize=8)
    finish(fig, '09', 'thermal_budget', 'HDL (mockup)', 'la SNN sparsa (0 DSP) sta nel budget termico di una ECU raffreddata passivamente, l ANN no')


# ============================== RUN ==============================
for fn in [f_readiness_matrix, f_readiness_radar, f_deploy_verdict,
           f_po2_alphabet, f_resource_occupancy, f_spectral, f_sparsity_mask, f_po2_exponent_range,
           f_bit_allocation, f_state_ranges, f_quant_vs_bits, f_perparam_fragility, f_chattering, f_leak_decay,
           f_activity_map, f_raster, f_sparsity_tick, f_isi, f_dead_sat,
           f_energy_breakdown, f_energy_vs_ann, f_energy_vs_rate, f_synops_split,
           f_op_count, f_wcet_cycles, f_latency_margin, f_jitter_proof, f_decode_cp,
           f_op_celltype, f_dse_pareto, f_area_model, f_bram_dim,
           f_seu_intro, f_seu_sensitivity, f_bit_criticality, f_degrade_flips, f_perparam_shift, f_hidden_vs_readout, f_tmr_overhead,
           f_aoi_surface, f_aoi_dist, f_queue_overflow, f_holdmode, f_pdr_knee,
           f_derating, f_thermal_budget]:
    fn()
pdf.close()
print('OK: %d figure -> %s' % (PG[0], OUT))
