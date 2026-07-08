"""Genera HOW_IT_WORKS_v3 (.md + .pdf) da un'unica sorgente — documento didattico
definitivo su COME FUNZIONA la rete CF_FSNN.

Gemello di VALIDATION_REPORT_v3 (che spiega i RISULTATI): questo spiega LA RETE, al
massimo dettaglio ma ad apice di comprensibilita'. Copre: cos'e' una SNN e confronto
con le ANN; perche' il backprop classico non basta e i metodi di training (BPTT+
surrogate, EventProp, STDP); la rete specifica del progetto (ALIF, ricorrenza
low-rank, delay, decode, po2); l'approccio PINN; hardware/FPGA; pro/contro.

Stile: emula scripts/build_validation_report_v3.py (reportlab, unica sorgente -> md+pdf).
I diagrammi CONCETTUALI sono disegnati in matplotlib (riproducibili senza checkpoint).

FONDATO SUL CODICE LIVE (non sul vecchio HOW_IT_WORKS.md v1, obsoleto):
 - decode: param = lo + (hi-lo)*sigmoid((raw-offset)/tau)   [F5 rimosso, R29]
 - s_safe = clamp(s, min=2.0)  [non 0.5]
 - IIDM: v_free=a*(1-(v/v0)^4); regimi free/car-following; CAH=min(a_l,a)-relu(dv)^2/(2s)
 - loss L_data = RMSE mascherato / N_valid  [non SRMSE su energia]
 - gradiente a base_threshold SOLO via soft reset (surrogate ritorna None sulla soglia)
 - coolness=0.99 e delta=4 FISSI (rete predice 5 dei 7 parametri)

Uso:  python scripts/build_how_it_works_v3.py
Output: document/HOW_IT_WORKS_v3.{md,pdf}, document/figures_howitworks_v3/*
"""
import os
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCDIR = os.path.join(ROOT, 'document')
FIGDIR = os.path.join(DOCDIR, 'figures_howitworks_v3')
os.makedirs(FIGDIR, exist_ok=True)

# palette
BLUE = '#26527a'
BLUEL = '#eef3fa'
GREEN = '#2e7d32'
GREENL = '#e8f5e9'
RED = '#c62828'
REDL = '#fdeaea'
GRAY = '#7f7f7f'
ORANGE = '#e8871e'
PURPLE = '#7b3fa0'


# ---------------------------------------------------------------------------
# helper di disegno
# ---------------------------------------------------------------------------
def _box(ax, x, y, w, h, text, fc=BLUEL, ec=BLUE, fs=9, tc='#12233a', bold=False, lw=1.3):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle='round,pad=0.015,rounding_size=0.04',
                 fc=fc, ec=ec, lw=lw, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha='center', va='center', fontsize=fs,
            color=tc, fontweight='bold' if bold else 'normal', zorder=3)


def _arrow(ax, x1, y1, x2, y2, color='#555', lw=1.8, style='-|>'):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                 mutation_scale=16, color=color, lw=lw, zorder=1))


def _clean(ax, xlim, ylim):
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.axis('off')


def _save(fig, name):
    p = os.path.join(FIGDIR, name)
    fig.savefig(p, dpi=130, bbox_inches='tight'); plt.close(fig)
    return p


# ---------------------------------------------------------------------------
# DIAGRAMMI
# ---------------------------------------------------------------------------
def fig_inverse():
    fig, ax = plt.subplots(figsize=(12, 3.3))
    _clean(ax, (0, 12), (0, 3))
    _box(ax, 0.1, 1.0, 2.1, 1.1, 'Traiettoria V2X\n[gap s, v, Δv, v_leader]\nnel tempo', fc='#fff7e6', ec=ORANGE, fs=8.5)
    _box(ax, 3.0, 1.0, 2.0, 1.1, 'SNN\nCF_FSNN', fc=BLUEL, ec=BLUE, fs=11, bold=True)
    _box(ax, 5.8, 1.0, 2.1, 1.1, '5 parametri\n[v0, T, s0, a, b]', fc=GREENL, ec=GREEN, fs=9, bold=True)
    _box(ax, 8.7, 1.0, 2.1, 1.1, 'modello ACC-IIDM\n→ accelerazione\nricostruita', fc='#f3eef9', ec=PURPLE, fs=8.5)
    _arrow(ax, 2.2, 1.55, 3.0, 1.55)
    _arrow(ax, 5.0, 1.55, 5.8, 1.55)
    _arrow(ax, 7.9, 1.55, 8.7, 1.55)
    # loss feedback
    _box(ax, 4.7, 2.35, 4.0, 0.55, 'confronto con accelerazione OSSERVATA  →  loss (errore)', fc=REDL, ec=RED, fs=8.5)
    _arrow(ax, 9.75, 2.1, 6.7, 2.35, color=RED, lw=1.4)
    _arrow(ax, 4.7, 2.6, 4.0, 1.6, color=RED, lw=1.4, style='-|>')
    ax.text(6, 0.55, 'Problema INVERSO (system identification): NON prediciamo la traiettoria, '
            'stimiamo i 5 numeri che la generano.', ha='center', fontsize=8.5, style='italic', color=BLUE)
    ax.set_title('Cosa fa la rete: da una traiettoria osservata ai 5 parametri del guidatore',
                 fontsize=10.5, color=BLUE)
    return _save(fig, 'inverse_problem.png')


def fig_ann_vs_snn():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 3.8))
    # ANN neuron
    _clean(a1, (0, 10), (0, 10))
    a1.set_title('Neurone ANN (2ª gen.): senza tempo', fontsize=10, color=BLUE)
    for i, yy in enumerate([7.5, 5.5, 3.5]):
        _box(a1, 0.3, yy, 1.6, 1.0, f'x{i+1}', fc='#f0f0f0', ec=GRAY, fs=9)
        _arrow(a1, 1.9, yy + 0.5, 4.2, 5.3)
    _box(a1, 4.2, 4.3, 2.2, 2.0, 'Σ wᵢxᵢ\n+ ReLU', fc=BLUEL, ec=BLUE, fs=9.5, bold=True)
    _box(a1, 7.4, 4.8, 2.2, 1.0, 'valore\nreale', fc=GREENL, ec=GREEN, fs=9)
    _arrow(a1, 6.4, 5.3, 7.4, 5.3)
    a1.text(5, 1.9, 'Un forward = un numero reale.\nDifferenziabile ovunque → backprop diretta.\nNessuno stato tra un input e il successivo.',
            ha='center', fontsize=8.3, color='#333')
    # SNN neuron
    _clean(a2, (0, 10), (0, 10))
    a2.set_title('Neurone SNN/LIF (3ª gen.): con stato temporale', fontsize=10, color=BLUE)
    for i, yy in enumerate([7.5, 5.5, 3.5]):
        _box(a2, 0.3, yy, 1.6, 1.0, f'spike\nin(t)', fc='#f0f0f0', ec=GRAY, fs=8)
        _arrow(a2, 1.9, yy + 0.5, 4.0, 5.3)
    _box(a2, 4.0, 4.3, 2.6, 2.0, 'integra V(t)\nnel tempo\n(leak)', fc=BLUEL, ec=BLUE, fs=9, bold=True)
    _box(a2, 7.2, 5.2, 2.4, 1.1, 'spike 0/1\nse V>θ\n→ reset', fc='#fff7e6', ec=ORANGE, fs=8.5, bold=True)
    _arrow(a2, 6.6, 5.3, 7.2, 5.7)
    _arrow(a2, 5.3, 4.3, 5.3, 3.3, color=PURPLE, lw=1.6)
    _arrow(a2, 5.3, 3.3, 3.6, 4.6, color=PURPLE, lw=1.6)
    a2.text(4.4, 3.0, 'stato V persiste →', ha='right', fontsize=7.5, color=PURPLE)
    a2.text(5, 1.9, 'Comunica con IMPULSI nel tempo. Ha memoria (V).\nSoglia non-differenziabile → backprop classica NON basta.\nEnergia ∝ numero di spike, non di moltiplicazioni.',
            ha='center', fontsize=8.3, color='#333')
    fig.suptitle('La differenza strutturale non è "binario vs reale": è lo STATO TEMPORALE', fontsize=11, color=BLUE)
    fig.tight_layout()
    return _save(fig, 'ann_vs_snn.png')


def fig_membrane():
    T = 120
    V = np.zeros(T); th = 1.0; spikes = []
    I = np.zeros(T)
    I[10:] = 0.16  # corrente costante
    I[60:70] = 0.0  # pausa
    v = 0.0
    trace = []
    for t in range(T):
        v = v - v / 8.0 + I[t]
        if v > th:
            spikes.append(t); v = v - th
        trace.append(v)
    trace = np.array(trace)
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.plot(trace, color=BLUE, lw=1.8, label='potenziale di membrana V(t)')
    ax.axhline(th, color=RED, ls='--', lw=1.2, label='soglia θ')
    for i, s in enumerate(spikes):
        ax.plot([s, s], [th, th + 0.5], color=ORANGE, lw=2.2)
        if i == 0:
            ax.text(s, th + 0.56, 'spike', color=ORANGE, fontsize=8, ha='center')
    ax.annotate('carica (integrazione)', xy=(30, trace[30]), xytext=(30, 1.4),
                fontsize=8, color='#333', ha='center', arrowprops=dict(arrowstyle='->', color='#888'))
    ax.annotate('reset sottrattivo (V −= θ)', xy=(spikes[1], th), xytext=(52, 1.55),
                fontsize=8, color='#333', arrowprops=dict(arrowstyle='->', color='#888'))
    ax.annotate('leak: senza input, V decade', xy=(66, trace[66]), xytext=(72, 0.75),
                fontsize=8, color='#333', arrowprops=dict(arrowstyle='->', color='#888'))
    ax.set_xlabel('tempo (tick)'); ax.set_ylabel('V'); ax.set_ylim(-0.1, 1.75)
    ax.set_title('Il neurone Integrate-and-Fire: integra gli input, al superamento della soglia emette uno spike e si resetta',
                 fontsize=10, color=BLUE)
    ax.legend(loc='upper right', fontsize=8); ax.grid(alpha=0.25)
    fig.tight_layout()
    return _save(fig, 'membrane.png')


def fig_hierarchy():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={'width_ratios': [1.05, 1]})
    _clean(a1, (0, 10), (0, 10))
    a1.set_title('Gerarchia dei modelli di neurone', fontsize=10, color=BLUE)
    rows = [('HH — 4 ODE, ioni', '#fdeaea', 9.0, 6.0),
            ('AdEx — 2 ODE', '#fbeee0', 8.0, 5.4),
            ('Izhikevich — 2 ODE, 20 pattern', '#fef7e0', 7.0, 4.8),
            ('ALIF — LIF + soglia adattiva  ◄ CF_FSNN', GREENL, 6.0, 4.2),
            ('LIF — 1 ODE + reset', BLUEL, 5.0, 3.6),
            ('IF — integratore puro', '#f0f0f0', 4.0, 3.0)]
    y = 8.4
    for i, (txt, fc, w, _) in enumerate(rows):
        ec = GREEN if 'CF_FSNN' in txt else BLUE
        _box(a1, (10 - w) / 2, y, w, 1.05, txt, fc=fc, ec=ec, fs=8.2,
             bold=('CF_FSNN' in txt))
        y -= 1.28
    a1.annotate('più bio-realismo,\npiù costoso', xy=(5, 9.4), xytext=(5, 9.4), ha='center', fontsize=7.5, color=RED)
    a1.annotate('più semplice,\npiù addestrabile', xy=(5, 0.5), xytext=(5, 0.6), ha='center', fontsize=7.5, color=GREEN)
    # ALIF vs LIF trace
    Tn = 90
    def sim(adaptive):
        v = 0.0; f = 0.0; th0 = 1.0; tr = []; thr = []; sp = []
        for t in range(Tn):
            v = v - v / 8 + 0.22
            th = th0 + (f if adaptive else 0.0)
            if v > th:
                sp.append(t); v -= th; f += 0.35
            f = f - f / 8 if adaptive else 0.0
            tr.append(v); thr.append(th)
        return np.array(tr), np.array(thr), sp
    for adaptive, col, lab in [(False, GRAY, 'LIF (spara regolare)'), (True, PURPLE, 'ALIF (si "stanca")')]:
        tr, thr, sp = sim(adaptive)
        a2.plot(tr, color=col, lw=1.5, label=lab)
        if adaptive:
            a2.plot(thr, color=col, ls=':', lw=1.2)
        a2.plot(sp, [1.65] * len(sp) if adaptive else [1.75] * len(sp), '|', color=col, ms=10)
    a2.set_title('ALIF: la soglia sale a ogni spike (fatica) → frequenza cala', fontsize=9.5, color=BLUE)
    a2.set_xlabel('tick'); a2.set_ylabel('V / soglia'); a2.set_ylim(0, 1.9)
    a2.legend(fontsize=7.8, loc='lower right'); a2.grid(alpha=0.25)
    fig.tight_layout()
    return _save(fig, 'hierarchy.png')


def fig_coding_datapath():
    fig, ax = plt.subplots(figsize=(12, 3.5))
    _clean(ax, (0, 12), (0, 3.2))
    _box(ax, 0.1, 1.1, 2.4, 1.2, 'Input V2X\nCONTINUO\n[s,v,Δv,vₗ] → I=W·x', fc='#fff7e6', ec=ORANGE, fs=8.3, bold=True)
    _box(ax, 3.4, 1.1, 3.0, 1.2, 'Hidden ALIF (32)\nSPIKING 0/1\n(l\'unico strato a impulsi)', fc=BLUEL, ec=BLUE, fs=8.5, bold=True)
    _box(ax, 7.3, 1.1, 2.3, 1.2, 'Output LI (5)\nCONTINUO\n(nessuno spike)', fc=GREENL, ec=GREEN, fs=8.5, bold=True)
    _box(ax, 10.3, 1.1, 1.6, 1.2, 'decode\nsigmoid\n+ bounds', fc='#f3eef9', ec=PURPLE, fs=8.3)
    _arrow(ax, 2.5, 1.7, 3.4, 1.7)
    _arrow(ax, 6.4, 1.7, 7.3, 1.7)
    _arrow(ax, 9.6, 1.7, 10.3, 1.7)
    ax.text(6, 0.5, 'La rete è IBRIDA continuo→spiking→continuo. L\'input NON è un treno di spike codificato: '
            'è corrente diretta. Solo l\'hidden spara.', ha='center', fontsize=8.3, style='italic', color=BLUE)
    ax.text(6, 2.95, '1 passo fisico (0.1 s) = 10 tick SNN interni con lo STESSO input (tempo di "settling", non nuova informazione)',
            ha='center', fontsize=8.3, color=RED)
    ax.set_title('Il percorso del segnale e la codifica', fontsize=10.5, color=BLUE)
    return _save(fig, 'coding_datapath.png')


def fig_why_backprop():
    x = np.linspace(-3, 3, 400)
    heavi = (x >= 0).astype(float)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 3.7))
    a1.plot(x, heavi, color=BLUE, lw=2, label='spike = H(V−θ)  (forward)')
    a1.plot([0, 0], [0, 1], color=RED, lw=2.4, label="derivata vera = δ di Dirac (∞ in 0)")
    a1.axhline(0, color='#bbb', lw=0.8)
    a1.text(-2.6, 0.5, 'derivata = 0\n→ nessun gradiente', color=RED, fontsize=8.5)
    a1.text(1.2, 0.5, 'derivata = 0\n→ nessun gradiente', color=RED, fontsize=8.5)
    a1.set_title('Perché il backprop classico si blocca', fontsize=10, color=BLUE)
    a1.set_xlabel('V − θ'); a1.set_ylim(-0.15, 1.2); a1.legend(fontsize=8, loc='upper left'); a1.grid(alpha=0.25)
    # obstacles table-ish
    _clean(a2, (0, 10), (0, 10))
    a2.set_title('3 ostacoli distinti → 3 soluzioni', fontsize=10, color=BLUE)
    obst = [('A. Spike non differenziabile\n(derivata 0 quasi ovunque)', 'Surrogate gradient (§7)', GREENL),
            ('B. Credit assignment temporale\n(V[t] dipende da V[t−1])', 'BPTT / EventProp (§7–8)', BLUEL),
            ('C. Implausibilità biologica\n(trasporto pesi, errore globale)', 'STDP / regole locali (§9)', '#f3eef9')]
    y = 7.6
    for txt, sol, fc in obst:
        _box(a2, 0.2, y, 5.4, 1.7, txt, fc=fc, ec=BLUE, fs=8)
        _arrow(a2, 5.6, y + 0.85, 6.3, y + 0.85)
        _box(a2, 6.3, y + 0.2, 3.5, 1.3, sol, fc='#f7f7f7', ec=GRAY, fs=8)
        y -= 2.5
    a2.text(5, 0.2, 'Il surrogate risolve SOLO A, non B: sono ortogonali.', ha='center', fontsize=8, style='italic', color=RED)
    fig.tight_layout()
    return _save(fig, 'why_backprop.png')


def fig_surrogate():
    x = np.linspace(-3, 3, 400)
    fig, ax = plt.subplots(figsize=(11, 3.7))
    ax.plot(x, (x >= 0).astype(float), color=BLUE, lw=2, label='FORWARD: spike vero H(V−θ)')
    for g, col, ls in [(0.3, '#f0a020', '--'), (1.0, GREEN, '-')]:
        surr = 1.0 / (1 + g * np.abs(x)) ** 2
        ax.plot(x, surr, color=col, lw=1.8, ls=ls, label=f'BACKWARD: surrogata 1/(1+γ|V−θ|)²,  γ={g}')
    ax.axvline(0, color='#bbb', lw=0.8)
    ax.set_title('Straight-Through Estimator: forward binario, backward liscio. γ=1.0 (progetto) → kernel stretto → meno amplificazione',
                 fontsize=9.5, color=BLUE)
    ax.set_xlabel('V − θ'); ax.set_ylim(-0.15, 1.2); ax.legend(fontsize=8.3, loc='upper right'); ax.grid(alpha=0.25)
    fig.tight_layout()
    return _save(fig, 'surrogate.png')


def fig_eventprop():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 3.8))
    # memory bars
    a1.bar(['BPTT\n(surrogate)', 'EventProp\n(adjoint)'], [500, 30], color=[BLUE, GREEN], alpha=0.85)
    a1.set_ylabel('memoria ∝ (unità)')
    a1.set_title('Memoria: BPTT O(T·N) vs EventProp O(#spike)', fontsize=9.5, color=BLUE)
    a1.text(0, 505, 'salva ogni tick', ha='center', fontsize=8)
    a1.text(1, 40, 'salva solo gli spike', ha='center', fontsize=8)
    a1.grid(alpha=0.25, axis='y')
    # adjoint jumps
    a2.set_title('EventProp: gradiente ESATTO, salti solo agli spike-time', fontsize=9.5, color=BLUE)
    t = np.linspace(0, 10, 200)
    lam = np.zeros_like(t)
    spikes_t = [8.0, 5.5, 3.0]
    val = 0.0
    for i in range(len(t) - 1, -1, -1):
        val *= 0.97
        for st in spikes_t:
            if abs(t[i] - st) < 0.03:
                val += 0.5
        lam[i] = val
    a2.plot(t, lam, color=PURPLE, lw=1.8, label='adjoint λ(t) (all\'indietro)')
    for st in spikes_t:
        a2.axvline(st, color=ORANGE, ls=':', lw=1.2)
    a2.text(3.0, lam.max() * 0.9, 'ai crossing marginali\ndenom→0 → 1/denom esplode\n(serve vincolo spettrale ρ<1)',
            fontsize=7.5, color=RED)
    a2.set_xlabel('tempo'); a2.set_ylabel('λ'); a2.legend(fontsize=8, loc='upper left'); a2.grid(alpha=0.25)
    fig.tight_layout()
    return _save(fig, 'eventprop.png')


def fig_sloppy():
    a = np.linspace(0.3, 2.5, 200)
    b = np.linspace(0.5, 3.0, 200)
    A, B = np.meshgrid(a, b)
    target = math.sqrt(1.1 * 1.5)
    L = (np.sqrt(A * B) - target) ** 2
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    cs = ax.contourf(A, B, L, levels=25, cmap='viridis_r')
    ax.contour(A, B, L, levels=[0.02, 0.1, 0.3], colors='white', linewidths=0.6, alpha=0.6)
    ax.plot(1.1, 1.5, 'o', color='white', ms=11, mec='k', label='valore VERO (a=1.1, b=1.5)')
    ax.plot(0.66, 1.95, 's', color=ORANGE, ms=11, mec='k', label='stima tipica (a≈0.66, b≈1.95)')
    ax.annotate('', xy=(0.66, 1.95), xytext=(1.1, 1.5), arrowprops=dict(arrowstyle='->', color='white', lw=1.3))
    ax.text(1.35, 2.6, 'valle piatta lungo √(a·b)=cost\n= direzione NON osservabile ("sloppy")',
            color='white', fontsize=8.5)
    ax.set_xlabel('a  [m/s²]'); ax.set_ylabel('b  [m/s²]')
    ax.set_title('Identificabilità: a e b entrano quasi solo come √(a·b).\nLa rete impara √(a·b) ma non sa separare a da b — limite del PROBLEMA, non della rete.',
                 fontsize=9, color=BLUE)
    ax.legend(fontsize=8, loc='lower right'); fig.colorbar(cs, ax=ax, label='loss (∝ errore su √(a·b))')
    fig.tight_layout()
    return _save(fig, 'sloppy_identifiability.png')


def fig_architecture():
    fig, ax = plt.subplots(figsize=(12.5, 5.0))
    _clean(ax, (0, 12.5), (0, 6))
    _box(ax, 0.1, 2.5, 1.9, 1.4, 'INPUT (4)\ns, v, Δv, vₗ\nnormalizzati', fc='#fff7e6', ec=ORANGE, fs=8.3, bold=True)
    _box(ax, 2.6, 2.1, 3.4, 2.2, 'HiddenLayer_ALIF (32 neuroni)\n• fc pesi po2 + delay assonali (≤6 tick)\n• ricorrenza low-rank U·V (rank 8)\n• leak bit-shift 7/8, soglia adattiva\n• soft reset  → SPIKE 0/1', fc=BLUEL, ec=BLUE, fs=7.8, bold=False)
    _box(ax, 6.6, 2.5, 2.4, 1.4, 'OutputLayer_LI (5)\npesi po2, leak 7/8\nintegra, NO spike', fc=GREENL, ec=GREEN, fs=8, bold=True)
    _box(ax, 9.5, 2.5, 2.9, 1.4, 'DECODE\nparam = lo+(hi−lo)·\nsigmoid((raw−off)/τ)\n→ [v0,T,s0,a,b]', fc='#f3eef9', ec=PURPLE, fs=7.8, bold=True)
    _arrow(ax, 2.0, 3.2, 2.6, 3.2)
    _arrow(ax, 6.0, 3.2, 6.6, 3.2)
    _arrow(ax, 9.0, 3.2, 9.5, 3.2)
    # recurrence loop
    _arrow(ax, 4.3, 2.1, 4.3, 1.4, color=PURPLE, lw=1.6)
    _arrow(ax, 4.3, 1.4, 3.0, 1.4, color=PURPLE, lw=1.6)
    _arrow(ax, 3.0, 1.4, 3.0, 2.1, color=PURPLE, lw=1.6)
    ax.text(4.5, 1.15, 'spike(t−1) → ricorrenza', fontsize=7, color=PURPLE)
    # ticks note
    ax.text(4.3, 4.55, '↻ 10 tick SNN interni per ogni passo fisico (0.1 s)', ha='center', fontsize=8, color=RED)
    # param count
    ax.text(6.25, 0.55, '864 parametri = fc 128 + rec_U 256 + rec_V 256 + base_threshold 32 + thresh_jump 32 + out_fc 160  '
            '(le 64 soglie sono apprendibili ma NON quantizzate po2)', ha='center', fontsize=7.8, color='#333',
            bbox=dict(boxstyle='round', fc='#f7f7f7', ec='#ccc'))
    ax.set_title('Architettura CF_FSNN (baseline, 864 parametri)', fontsize=11, color=BLUE)
    return _save(fig, 'architecture.png')


def fig_spectral():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 3.7))
    rng = np.random.RandomState(0)
    n = 60
    for rho, col, lab in [(0.5, GREEN, 'ρ=0.5 contrattivo'), (1.15, ORANGE, 'ρ=1.15'), (1.6, RED, 'ρ=1.6 espansivo')]:
        x = 0.1; tr = []
        pert = rng.randn(n) * 0.02
        for t in range(n):
            x = rho * x + pert[t]
            tr.append(x)
        a1.plot(tr, color=col, lw=1.7, label=lab)
    a1.axhline(0, color='#bbb', lw=0.8)
    a1.set_title('Stato ricorrente: ρ<1 si smorza, ρ>1 diverge', fontsize=9.5, color=BLUE)
    a1.set_xlabel('tick'); a1.set_ylabel('stato'); a1.legend(fontsize=8); a1.grid(alpha=0.25)
    # champions scatter
    champs = [('Raffaello', 2.99, 69.3, 's', RED), ('Leonardo', 1.16, 77.5, 's', BLUE),
              ('Michelangelo', 0.39, 79.2, 'o', ORANGE), ('Donatello', 0.05, 84.8, 'o', PURPLE)]
    a2.axvspan(0, 1, color=GREENL)
    a2.axvline(1, color=RED, ls='--', lw=1.1)
    for nm, rho, acc, mk, col in champs:
        a2.scatter(rho, acc, s=120, marker=mk, color=col, edgecolor='k', zorder=3)
        a2.annotate(nm, (rho, acc), xytext=(rho + 0.08, acc - 1.3), fontsize=7.8, color=col)
    a2.text(0.5, 71, 'contrattivo\nρ<1 (FPGA-safe)', ha='center', fontsize=8, color=GREEN, style='italic')
    a2.text(2.2, 82, 'espansivo ρ>1', ha='center', fontsize=8, color=RED, style='italic')
    a2.set_title('ρ(U·V) vs accuratezza: EventProp (○) contrattivo, BPTT (□) espansivo', fontsize=9, color=BLUE)
    a2.set_xlabel('raggio spettrale ρ(U·V)'); a2.set_ylabel('accuratezza [%]')
    a2.set_xlim(-0.2, 3.3); a2.grid(alpha=0.25)
    fig.tight_layout()
    return _save(fig, 'spectral_radius.png')


def fig_pinn():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 3.8), gridspec_kw={'width_ratios': [1.25, 1]})
    _clean(a1, (0, 12), (0, 6))
    a1.set_title('Come la loss PINN "chiude il cerchio"', fontsize=10, color=BLUE)
    _box(a1, 0.2, 3.7, 2.3, 1.2, 'params predetti\n[v0,T,s0,a,b]', fc=GREENL, ec=GREEN, fs=8)
    _box(a1, 3.2, 3.7, 2.7, 1.2, 'ACC-IIDM\n(equazioni fisiche)', fc='#f3eef9', ec=PURPLE, fs=8)
    _box(a1, 6.6, 3.7, 2.6, 1.2, 'accelerazione\nRICOSTRUITA', fc=BLUEL, ec=BLUE, fs=8)
    _box(a1, 9.6, 3.7, 2.2, 1.2, 'confronto con\nquella OSSERVATA', fc=REDL, ec=RED, fs=8)
    _arrow(a1, 2.5, 4.3, 3.2, 4.3); _arrow(a1, 5.9, 4.3, 6.6, 4.3); _arrow(a1, 9.2, 4.3, 9.6, 4.3)
    a1.text(6, 2.9, 'L_data misura l\'errore sull\'ACCELERAZIONE, non sui parametri:\nè la radice dell\'equifinalità (più set di parametri, stessa guida).',
            ha='center', fontsize=8, color=RED, style='italic')
    a1.text(6, 1.3, 'val_data = metrica PRIMARIA (sicurezza).  NRMSE per-canale = lente diagnostica.\nNRMSE bassa ≠ guida sicura.',
            ha='center', fontsize=8, color='#333', bbox=dict(boxstyle='round', fc='#f7f7f7', ec='#ccc'))
    # weights
    terms = ['L_data\n(fit)', 'L_phys\n(coerenza)', 'L_OU\n(T liscio)', 'L_bc\n(no-crash)', 'L_sr\n(sparsità)']
    w = [1.0, 0.1, 0.05, 1.0, 0.5]
    cols = [GREEN, BLUE, GRAY, RED, ORANGE]
    a2.bar(range(5), w, color=cols, alpha=0.85)
    a2.set_xticks(range(5)); a2.set_xticklabels(terms, fontsize=7.5)
    a2.set_ylabel('peso λ'); a2.set_title('I 5 termini della loss e i loro pesi', fontsize=9.5, color=BLUE)
    for i, v in enumerate(w):
        a2.text(i, v + 0.02, str(v), ha='center', fontsize=8)
    a2.grid(alpha=0.25, axis='y')
    fig.tight_layout()
    return _save(fig, 'pinn.png')


def fig_po2():
    ks = list(range(-4, 2))
    levels = [2.0 ** k for k in ks]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 3.6), gridspec_kw={'width_ratios': [1.3, 1]})
    allv = sorted([-x for x in levels] + [0.0] + levels)
    a1.stem(allv, [1] * len(allv), linefmt=BLUE, markerfmt='o', basefmt=' ')
    a1.axvspan(-2 ** -5, 2 ** -5, color=REDL)
    a1.text(0, 1.15, 'banda morta\n|w|<2⁻⁵ → 0', ha='center', fontsize=7.5, color=RED)
    a1.set_yticks([]); a1.set_xlabel('valore del peso')
    a1.set_title('Pesi Power-of-Two: 13 livelli {±2ᵏ, 0}, k∈[−4,1]', fontsize=9.3, color=BLUE)
    a1.set_ylim(0, 1.4); a1.grid(alpha=0.2, axis='x')
    # cost
    a2.bar(['MAC\n(ANN)', 'shift+add\n(po2)'], [100, 10], color=[GRAY, GREEN], alpha=0.85)
    a2.set_ylabel('costo relativo su FPGA (LUT)')
    a2.set_title('Moltiplicazione → bit-shift', fontsize=9.5, color=BLUE)
    a2.text(1, 13, '≈10× meno area\n≈20× meno energia\n1 ciclo vs 4', ha='center', fontsize=8, color=GREEN)
    a2.grid(alpha=0.25, axis='y')
    fig.tight_layout()
    return _save(fig, 'po2.png')


def fig_energy():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 3.6))
    a1.bar(['SynOps SNN\n(~304k)', 'MAC ANN\n(~302k... denso)'], [304, 302], color=[PURPLE, GRAY], alpha=0.85)
    a1.set_ylabel('operazioni / inferenza (×1000, indicativo)')
    a1.set_title('Le SynOps NON sono meno dei MAC', fontsize=9.5, color=BLUE)
    a1.grid(alpha=0.25, axis='y')
    a2.bar(['SNN (AC)\n~55 nJ', 'ANN (MAC)\n~302 nJ'], [55, 302], color=[GREEN, GRAY], alpha=0.85)
    a2.set_ylabel('energia / inferenza [nJ] (stima Horowitz 45nm)')
    a2.set_title('Il vantaggio (≈5-6×) viene dal COSTO UNITARIO AC<MAC', fontsize=9, color=BLUE)
    a2.grid(alpha=0.25, axis='y')
    fig.suptitle('Nota onesta: a parità di costo per operazione la SNN sarebbe peggiore → più sparsità = più vantaggio',
                 fontsize=9.5, color=RED)
    fig.tight_layout()
    return _save(fig, 'energy.png')


def fig_triangle():
    fig, ax = plt.subplots(figsize=(9.5, 6.2))
    _clean(ax, (0, 10), (0, 9))
    V = {'bio': (5, 8.2), 'train': (1.3, 1.2), 'hw': (8.7, 1.2)}
    ax.plot([V['bio'][0], V['train'][0], V['hw'][0], V['bio'][0]],
            [V['bio'][1], V['train'][1], V['hw'][1], V['bio'][1]], color='#bbb', lw=1.5, zorder=1)
    ax.text(*V['bio'], 'BIO-REALISMO', ha='center', va='bottom', fontsize=10, color=RED, fontweight='bold')
    ax.text(V['train'][0], V['train'][1] - 0.4, 'ADDESTRABILITÀ', ha='center', fontsize=10, color=GREEN, fontweight='bold')
    ax.text(V['hw'][0], V['hw'][1] - 0.4, 'EFFICIENZA HW', ha='center', fontsize=10, color=BLUE, fontweight='bold')
    pts = [('ALIF', 4.6, 4.6, PURPLE), ('surrogate\n+BPTT', 3.0, 3.2, GREEN),
           ('EventProp', 4.2, 3.6, PURPLE), ('po2', 6.6, 2.6, BLUE),
           ('low-rank U·V', 6.9, 3.4, BLUE), ('PINN', 3.6, 4.4, GREEN),
           ('bit-shift leak', 7.4, 2.0, BLUE)]
    for nm, x, y, col in pts:
        ax.plot(x, y, 'o', color=col, ms=9, mec='k', zorder=3)
        ax.annotate(nm, (x, y), xytext=(x + 0.15, y + 0.18), fontsize=8.3, color=col)
    ax.set_title('Ogni scelta di CF_FSNN è un compromesso nel triangolo bio-realismo / addestrabilità / efficienza-hardware',
                 fontsize=9.8, color=BLUE)
    return _save(fig, 'triangle.png')


# ---------------------------------------------------------------------------
# EQUAZIONI (typeset via mathtext -> PNG). Le formule semplici restano testo
# Unicode nel corpo; qui si rendono solo quelle con frazioni/radici/matrici,
# cosi' da risultare leggibili anche nel PDF (reportlab non supporta LaTeX).
# ---------------------------------------------------------------------------
def fig_eq(name, lines, fs=15, color='#12233a'):
    """Renderizza una o piu' righe di equazione (mathtext) in un PNG 'tight'."""
    n = len(lines)
    fig = plt.figure(figsize=(9.2, 0.52 * n + 0.22))
    for i, ln in enumerate(lines):
        fig.text(0.5, 1.0 - (i + 0.5) / n, '$' + ln + '$',
                 ha='center', va='center', fontsize=fs, color=color)
    p = os.path.join(FIGDIR, name)
    fig.savefig(p, dpi=150, bbox_inches='tight', pad_inches=0.18, facecolor='white')
    plt.close(fig)
    return p


print('[1/4] genero diagrammi concettuali...')
F = {
    'inverse': fig_inverse(), 'ann_snn': fig_ann_vs_snn(), 'membrane': fig_membrane(),
    'hierarchy': fig_hierarchy(), 'coding': fig_coding_datapath(), 'why_bp': fig_why_backprop(),
    'surrogate': fig_surrogate(), 'eventprop': fig_eventprop(), 'sloppy': fig_sloppy(),
    'arch': fig_architecture(), 'spectral': fig_spectral(), 'pinn': fig_pinn(),
    'po2': fig_po2(), 'energy': fig_energy(), 'triangle': fig_triangle(),
    # --- equazioni typeset (mathtext -> PNG) ---
    'eq_lif': fig_eq('eq_lif.png', [
        r'V_t = (1-2^{-p})\,V_{t-1} + I_{\mathrm{ff}} + I_{\mathrm{rec}}',
        r'p=3:\quad V_t = \frac{7}{8}\,V_{t-1} + I_{\mathrm{ff}} + I_{\mathrm{rec}}',
    ]),
    'eq_alif': fig_eq('eq_alif.png', [
        r'\theta^{\mathrm{eff}}_t = \theta_{\mathrm{base}} + \max(F_{t-1},\,0)',
        r'S_t = \mathbf{1}\,[\,V_t \geq \theta^{\mathrm{eff}}_t\,]',
        r'F_t = (1-2^{-p})\,F_{t-1} + S_t\cdot\max(\theta_{\mathrm{jump}},\,0)',
        r'V_t \leftarrow V_t - S_t\cdot\theta^{\mathrm{eff}}_t \quad (\mathrm{soft\ reset})',
    ]),
    'eq_surrogate': fig_eq('eq_surrogate.png', [
        r'\frac{\partial S}{\partial V} = \frac{1}{\left(1+\gamma\,|V-\theta^{\mathrm{eff}}|\right)^{2}}\,, \qquad \gamma = 1.0',
    ]),
    'eq_sstar': fig_eq('eq_sstar.png', [
        r's^{*} = s_0 + \max\left(0,\; v\,T + \frac{v\,\Delta v}{2\sqrt{a\,b}}\right)',
    ]),
    'eq_iidm': fig_eq('eq_iidm.png', [
        r's_{\mathrm{safe}} = \max(s,\,2.0)\,, \qquad z = \frac{s^{*}}{s_{\mathrm{safe}}}',
        r'a_{\mathrm{free}} = a\left(1-\left(\frac{v}{v_0}\right)^{4}\right)',
    ]),
    'eq_cah': fig_eq('eq_cah.png', [
        r'a_{\mathrm{CAH}} = \min(a_l,\,a) - \frac{\mathrm{relu}(\Delta v)^{2}}{2\,s_{\mathrm{safe}}}',
    ]),
    'eq_recur': fig_eq('eq_recur.png', [
        r'I_{\mathrm{rec},t} = S_{t-1}\,W_{\mathrm{rec}}^{\top}\,, \qquad W_{\mathrm{rec}} = Q(U)\,Q(V)',
        r'U\in\mathbb{R}^{32\times 8},\;\; V\in\mathbb{R}^{8\times 32} \;\Rightarrow\; \mathrm{rank}(W_{\mathrm{rec}})\leq 8',
    ]),
    'eq_decode': fig_eq('eq_decode.png', [
        r'p = p_{\mathrm{lo}} + (p_{\mathrm{hi}}-p_{\mathrm{lo}})\cdot\sigma\left(\frac{\mathrm{raw}-\mathrm{off}}{\tau}\right)\,, \qquad \sigma(x)=\frac{1}{1+e^{-x}}',
    ]),
    'eq_po2': fig_eq('eq_po2.png', [
        r'Q(w) = \mathrm{sign}(w)\cdot 2^{\,\mathrm{clip}(\mathrm{round}(\log_2|w|),\,-4,\,1)}\cdot \mathbf{1}[\,|w|>2^{-5}\,]',
        r'\frac{\partial Q}{\partial w} = 1 \;\;(\mathrm{STE})',
    ]),
    'eq_loss': fig_eq('eq_loss.png', [
        r'\mathcal{L} = \lambda_{\mathrm{data}}L_{\mathrm{data}} + \lambda_{\mathrm{phys}}L_{\mathrm{phys}} + \lambda_{\mathrm{OU}}L_{\mathrm{OU}} + \lambda_{\mathrm{bc}}L_{\mathrm{bc}} + \lambda_{\mathrm{sr}}L_{\mathrm{sr}}',
    ]),
    'eq_ou': fig_eq('eq_ou.png', [
        r'T_{t+1} = \mathcal{U}(T_1,\,T_2)\ \ \mathrm{con\ prob.}\ \frac{\Delta t}{\tau_{2d}}\,, \quad \mathrm{altrimenti}\ \ T_{t+1}=T_t',
        r'\eta_{t+1} = e^{-\Delta t/\tau}\,\eta_t + \sqrt{\frac{2\Delta t}{\tau}}\;\xi\,, \quad \xi\sim\mathcal{N}(0,1)',
    ]),
    'eq_norm': fig_eq('eq_norm.png', [
        r'\tilde s = \frac{s}{150},\ \ \tilde v = \frac{v}{40},\ \ \widetilde{\Delta v} = \frac{\mathrm{clip}(\Delta v,-20,20)+20}{40},\ \ \tilde v_l = \frac{v_l}{40}',
        r'I_{\mathrm{ff}} = \tilde{\mathbf{x}}\,Q(W_{\mathrm{fc}})^{\top}\,, \quad \tilde{\mathbf{x}} = [\,\tilde s,\ \tilde v,\ \widetilde{\Delta v},\ \tilde v_l\,] \in [0,1]^4',
    ]),
    'eq_li': fig_eq('eq_li.png', [
        r'y_t = (1-2^{-3})\,y_{t-1} + I^{\mathrm{out}}_t = \frac{7}{8}\,y_{t-1} + I^{\mathrm{out}}_t',
    ]),
}
print('  diagrammi in', FIGDIR)


# ---------------------------------------------------------------------------
# CONTENUTO
# ---------------------------------------------------------------------------
def build_doc():
    D = []
    A = D.append

    A(('cover', {
        'title': 'CF_FSNN — Come Funziona (v3)',
        'subtitle': 'Una rete neuronale spiking per l\'identificazione di un controllore di '
                    'car-following: teoria delle SNN, addestramento (BPTT+surrogate, EventProp, STDP), '
                    'architettura del progetto, approccio PINN e co-design per FPGA',
        'meta': [
            'Documento della terna CF_FSNN — gemello di VALIDATION_REPORT_v3 (i risultati) e FPGA_REPORT (il profilo hardware)',
            'Contenuto fondato sul codice sorgente: core/network.py, core/neurons.py, core/hardware.py, core/eventprop.py, train.py',
        ],
    }))

    A(('h2', 'Indice'))
    A(('table', (
        ['Sezione', 'Contenuto'],
        [
            ['Parte I', 'Cos\'è una SNN e come si addestra'],
            ['0', 'Bussola: il problema inverso, le tre proprietà, i documenti gemelli'],
            ['1', 'Le tre generazioni di reti neurali'],
            ['2', 'ANN vs SNN su assi multipli'],
            ['3', 'Dal neurone biologico al neurone LIF'],
            ['4', 'La gerarchia dei modelli e la scelta di ALIF'],
            ['5', 'Codifica neurale: input continuo, spiking interno'],
            ['6', 'Perché il backprop classico non è sufficiente'],
            ['7', 'Metodo 1 — Surrogate gradient + BPTT (addestramento di produzione)'],
            ['8', 'Metodo 2 — EventProp (gradiente esatto via adjoint)'],
            ['9', 'Metodo 3 — STDP e il limite di identificabilità sloppy'],
            ['Parte II', 'La rete specifica del progetto'],
            ['10', 'Architettura CF_FSNN, strato per strato'],
            ['11', 'Il raggio spettrale ρ(U·V): contrattivo vs espansivo'],
            ['12', 'L\'approccio PINN: la loss a cinque componenti'],
            ['13', 'Il modello fisico ACC-IIDM (il bersaglio del PINN)'],
            ['14', 'Il generatore di dati sintetici'],
            ['15', 'Quantizzazione Power-of-Two e Straight-Through Estimator'],
            ['Parte III', 'Bilancio, hardware, stato'],
            ['16', 'Il deployment su FPGA/HDL: il problema aperto'],
            ['17', 'Il triangolo: rileggere tutte le scelte'],
            ['18', 'Sintesi end-to-end'],
            ['19', 'Mappa dei file'],
            ['20', 'Riferimenti'],
        ],
    )))

    # ===== PARTE I =====
    A(('h1', 'Parte I — Cos\'è una SNN e come si addestra'))

    A(('h2', '0. Bussola: il problema inverso, le tre proprietà, i documenti gemelli'))
    A(('p', 'CF_FSNN risolve un problema inverso. Non prevede la traiettoria futura del veicolo: '
           'osserva una traiettoria di car-following — gap dal veicolo che precede, velocità propria, '
           'differenza di velocità Δv e velocità del leader, ricevuti via V2X — e ne identifica i cinque '
           'numeri che la generano, cioè i parametri del modello di guida ACC-IIDM [v0, T, s0, a, b]. '
           'Questa distinzione regge l\'intero documento: loss, identificabilità e metriche hanno senso '
           'solo alla luce del fatto che si stimano parametri, non traiettorie.'))
    A(('img', (F['inverse'], 'Figura 0.1 — Il problema inverso. La rete mappa la traiettoria osservata '
                             'nei cinque parametri; questi, immessi nel modello fisico ACC-IIDM, '
                             'ricostruiscono l\'accelerazione, confrontata con quella osservata per '
                             'formare la loss.')))
    A(('p', 'Una rete neuronale spiking (SNN) possiede tre proprietà che la distinguono da una rete '
           'classica (ANN) e da cui discende tutto il resto (Maass 1997; Gerstner et al. 2014): '
           '(1) dinamica temporale — ogni neurone ha uno stato interno che persiste e integra gli '
           'input nel tempo; (2) computazione sparsa a eventi — la comunicazione avviene per impulsi '
           '(spike) e l\'energia scala con il numero di spike, non di moltiplicazioni; '
           '(3) attivazione non differenziabile — lo spike è un gradino a valori {0,1}, con derivata '
           'nulla quasi ovunque. La terza proprietà obbliga a reinventare l\'addestramento (Parte I); '
           'le prime due giustificano le scelte hardware (Parte II).'))
    A(('callout', 'Filo conduttore. Ogni decisione di progetto vive in un triangolo con tre vertici in '
                  'tensione: bio-realismo, addestrabilità, efficienza hardware. Guadagnare su un vertice '
                  'costa sugli altri; la §17 rilegge tutte le scelte come punti in questo spazio.'))
    A(('callout', 'Documenti gemelli. Questo documento spiega la rete. VALIDATION_REPORT_v3 riporta i '
                  'risultati — i quattro champion, il verdetto di deploy, le dimensioni di validazione — '
                  'e FPGA_REPORT ne profila l\'implementazione hardware. Le grandezze introdotte qui '
                  '(ρ(U·V), ALIF, po2, EventProp, sparsità) sono usate là dandole per acquisite.'))

    A(('h2', '1. Le tre generazioni di reti neurali'))
    A(('p', 'La SNN è la "terza generazione" di rete neurale (Maass 1997). La prima generazione è il '
           'neurone a soglia di McCulloch & Pitts (1943): unità con uscita binaria, senza nonlinearità '
           'continua. La seconda generazione sono le ANN moderne (sigmoide, ReLU): ogni unità emette un '
           'valore reale a ogni forward pass ed è differenziabile ovunque, e per questo si addestra con '
           'la backpropagation. La terza generazione, le SNN, comunica con spike (eventi discreti) nel '
           'tempo continuo: il tempo non è un semplice indice di strato, ma parte della rappresentazione. '
           'Un singolo spike temporizzato può, in linea di principio, codificare più informazione di un '
           'valore rate-based, e su hardware neuromorfico l\'energia scala con gli eventi.'))
    A(('callout', 'Un equivoco da evitare: "terza generazione" non significa "più accurata", ma un asse '
                  'di ottimizzazione diverso — energia, latenza, idoneità al silicio — spesso pagato con '
                  'un po\' di accuratezza. Su GPU, per questo stesso compito, un MLP sarebbe più semplice '
                  'e preciso; il valore della SNN sta nel target FPGA.'))

    A(('h2', '2. ANN vs SNN su assi multipli'))
    A(('p', 'Il confronto non si riduce a un solo asse ("le SNN sono più efficienti"): le due famiglie '
           'differiscono su almeno sei assi indipendenti, ciascuno con una conseguenza concreta per '
           'CF_FSNN.'))
    A(('table', (
        ['Asse', 'ANN (2ª gen.)', 'SNN (3ª gen.)', 'Implicazione per CF_FSNN'],
        [
            ['Unità di comunicazione', 'valore reale per layer', 'treno di spike 0/1 nel tempo', 'output leggibile solo integrando gli spike'],
            ['Stato / memoria', 'stateless per campione', 'potenziale di membrana persistente', 'nativamente adatta a serie temporali (traiettorie)'],
            ['Computazione', 'MAC densi sincroni', 'accumulo + confronto soglia, event-driven', 'energia ∝ spike; spike rate ~13–21%'],
            ['Differenziabilità', 'end-to-end', 'gradino di Heaviside (non diff.)', 'serve surrogate / EventProp (§6–8)'],
            ['Hardware ideale', 'GPU / TPU (matmul densa)', 'neuromorfico / FPGA (memoria-vicino-calcolo)', 'target PYNQ-Z1; pesi po2 → shift'],
            ['Dati nativi', 'tensori densi', 'eventi / serie temporali', 'input V2X sequenziale'],
        ],
    )))
    A(('img', (F['ann_snn'], 'Figura 2.1 — Neurone ANN vs neurone spiking. La differenza strutturale '
                             'non è "reale vs binario", ma la presenza di uno stato che evolve nel '
                             'tempo e di una soglia non differenziabile.')))
    A(('p', 'Una precisazione che conviene anticipare: il vantaggio energetico delle SNN non nasce '
           'dalla sparsità in sé. Le operazioni sinaptiche (SynOps, l\'analogo spiking dei MAC) di '
           'questa rete eguagliano o superano i MAC di una ANN equivalente; a parità di costo per '
           'operazione la SNN sarebbe anzi in svantaggio. Il guadagno viene dal minor costo unitario '
           'di un accumulo (AC) rispetto a una moltiplicazione-accumulo (MAC) — un rapporto misurato '
           'a livello di circuito (Horowitz 2014) — e su FPGA, con pesi potenze-di-due, l\'AC si riduce '
           'a uno shift+add. La sparsità amplifica questo margine ma non lo crea. Il payoff energetico '
           'misurato per champion è in VALIDATION_REPORT_v3 §9.2 e il profilo op-count in FPGA_REPORT.'))
    A(('img', (F['energy'], 'Figura 2.2 — Perché la SNN è più efficiente pur facendo lo stesso numero '
                            '(o più) di operazioni: il costo unitario AC < MAC. La sparsità amplifica '
                            'il margine, non lo crea.')))

    A(('h2', '3. Dal neurone biologico al neurone LIF'))
    A(('p', 'Il neurone artificiale spiking è un\'astrazione minimale del neurone biologico. La membrana '
           'si comporta come un condensatore che accumula carica; gli input sinaptici la caricano '
           '(integrazione); in assenza di stimolo la membrana perde carica nel tempo (leak, con costante '
           'di tempo τ), cioè il neurone "dimentica" gli input vecchi; al superamento di una soglia '
           'emette un impulso (spike) e subito dopo si resetta. Questo è il modello Integrate-and-Fire '
           'con leak (LIF). Non serve il realismo completo della biofisica di Hodgkin & Huxley (1952) — '
           'quattro equazioni differenziali per i canali ionici — perché l\'obiettivo è la computazione '
           'e l\'energia, non l\'elettrofisiologia.'))
    A(('p', 'In tempo discreto, il potenziale di membrana V evolve per integrazione con perdita. Nel '
           'codice il leak non è una divisione ma uno spostamento di bit (bit-shift) di ordine p, cioè '
           'un fattore 1−2⁻ᵖ:'))
    A(('img', (F['eq_lif'], 'Equazione 3.1 — Aggiornamento del potenziale di membrana LIF '
                            '(core/neurons.py). V = potenziale; I_ff = corrente feedforward (ritardata); '
                            'I_rec = corrente ricorrente; p = ordine del bit-shift del leak '
                            '(default p=3, cioè fattore 7/8). La forma a bit-shift evita divisori in '
                            'hardware.')))
    A(('img', (F['membrane'], 'Figura 3.1 — Dinamica di un neurone LIF: l\'input carica il potenziale, '
                              'il leak lo fa decadere in assenza di stimolo, al superamento della soglia '
                              'si genera uno spike e il potenziale si riduce (reset sottrattivo).')))

    A(('h2', '4. La gerarchia dei modelli e la scelta di ALIF'))
    A(('p', 'I modelli di neurone formano una gerarchia di semplificazione progressiva: scendendo, si '
           'perde dettaglio biologico e si guadagna addestrabilità e velocità. Dall\'alto: '
           'Hodgkin-Huxley (quattro ODE; Hodgkin & Huxley 1952) → AdEx (due ODE; Brette & Gerstner 2005) '
           '→ Izhikevich (due ODE, molti pattern di scarica; Izhikevich 2003) → ALIF (LIF con soglia '
           'adattiva) → LIF (una ODE più reset) → IF (integratore puro). In pratica: immagini statiche '
           '→ LIF; compiti sequenziali con memoria → ALIF/LSNN (Bellec et al. 2018); neuroscienza '
           '→ Izhikevich/AdEx; biofisica → Hodgkin-Huxley.'))
    A(('img', (F['hierarchy'], 'Figura 4.1 — Gerarchia dei neuroni (sx) e comportamento ALIF vs LIF (dx). '
                               'L\'ALIF alza la soglia a ogni spike (fatica) e poi la lascia decadere, '
                               'riducendo la frequenza di scarica nel tempo.')))
    A(('p', 'CF_FSNN usa il neurone ALIF (Adaptive Leaky Integrate-and-Fire): un LIF con una variabile '
           'di adattamento — una fatica che alza temporaneamente la soglia a ogni spike e poi decade '
           '(Bellec et al. 2018). La soglia effettiva è la somma della soglia base e della fatica; la '
           'fatica decade con lo stesso bit-shift della membrana e cresce di thresh_jump a ogni spike; '
           'dopo lo spike il potenziale subisce un reset sottrattivo. Le equazioni implementate '
           '(core/neurons.py) sono:'))
    A(('img', (F['eq_alif'], 'Equazione 4.1 — Dinamica ALIF per tick. θ_base = soglia base '
                             '(apprendibile, init 1.5); F = fatica/adattamento; θ_jump = incremento di '
                             'soglia per spike (apprendibile, init 0.5); S ∈ {0,1} = spike; '
                             '𝟏[·] = indicatore (funzione a gradino). Il reset è sottrattivo: non azzera '
                             'il potenziale.')))
    A(('p', 'La scelta di ALIF rispetto al LIF puro poggia su tre ragioni, tutte di addestrabilità o '
           'hardware: (a) il car-following è un problema temporale che beneficia di una memoria a due '
           'scale — veloce nella membrana, lenta nella fatica; (b) la fatica regola la sparsità del '
           'firing e stabilizza l\'addestramento: nei test del progetto, azzerare thresh_jump porta il '
           'training a divergere, mentre valori troppo alti causano underfit, con un ottimo empirico '
           'intorno a 0.5 (da cui l\'inizializzazione); (c) aggiunge solo due stati per neurone, '
           'restando economica su FPGA.'))
    A(('callout', 'Il costo di ALIF, dichiarato: complica sia l\'addestramento con EventProp (la soglia '
                  'adattiva aggiunge una dinamica da trattare nell\'adjoint) sia la conversione in HDL, '
                  'perché gli strumenti standard di conversione (FINN; Umuroglu et al. 2017) non '
                  'supportano il neurone ALIF (§16). Inoltre una soglia iniziale troppo alta negli strati '
                  'non di ingresso può spegnere i neuroni: la taratura conta.'))

    A(('h2', '5. Codifica neurale: input continuo, spiking interno'))
    A(('p', 'Come entrano ed escono i numeri da una rete a impulsi? Esistono molti schemi di codifica '
           '(rate coding = conteggio di spike in una finestra; codifica temporale = tempi precisi degli '
           'spike; time-to-first-spike; popolazione; fase; burst). In CF_FSNN, però, l\'input non è '
           'codificato in spike — è l\'equivoco più frequente da prevenire. I quattro segnali V2X, '
           'normalizzati in [0,1], entrano come corrente diretta iniettata nel potenziale, non come '
           'treni di impulsi Poisson o a latenza. Solo lo strato nascosto ALIF genera spike; lo strato '
           'di uscita è un integratore continuo (LI, Leaky Integrator) senza spike. La rete è quindi '
           'ibrida: continuo → spiking → continuo.'))
    A(('p', 'La normalizzazione degli ingressi fisici e l\'iniezione di corrente nel primo strato sono '
           '(data/generator.py, core/network.py):'))
    A(('img', (F['eq_norm'], 'Equazione 5.1 — Normalizzazione degli ingressi in [0,1] e corrente '
                             'sinaptica del primo strato. s = gap [m]; v = velocità ego [m/s]; '
                             'Δv = v−v_leader [m/s]; v_l = velocità del leader [m/s]; Q(W_fc) = pesi '
                             'feedforward quantizzati po2 (mascherati per i ritardi). Non esiste alcun '
                             'encoder a spike: l\'ingresso è corrente.')))
    A(('img', (F['coding'], 'Figura 5.1 — Il percorso del segnale. Continuo in ingresso (corrente '
                            'diretta), spiking solo nell\'hidden ALIF, continuo in uscita (LI). '
                            'Ogni passo fisico da 0.1 s è elaborato con 10 tick SNN interni a ingresso '
                            'costante — tempo di assestamento della dinamica, non nuova informazione.')))
    A(('p', 'Ne discendono due conseguenze. Primo: l\'output si legge dal potenziale dell\'ultimo strato '
           'LI (voltage decoding), non da un conteggio di spike; con soli 10 tick il rate coding sarebbe '
           'troppo rumoroso, mentre il voltage decoding è più stabile e a bassa latenza. Secondo: i 10 '
           'tick interni per passo non aggiungono informazione, ma decuplicano la profondità temporale '
           'effettiva vista dall\'addestramento (una traiettoria di 50 passi diventa una catena di 500 '
           'tick), aggravando il problema di credit assignment discusso in §6. Il numero di tick è un '
           'compromesso: dieci bastano perché la dinamica ALIF si assesti a ingresso costante, senza '
           'moltiplicare oltre la profondità temporale. Va evitato anche l\'equivoco opposto: non è "una '
           'ANN con leak", perché lo strato nascosto ha soglia vera, reset e non differenziabilità.'))

    A(('h2', '6. Perché il backprop classico non è sufficiente'))
    A(('p', 'Addestrare significa calcolare come modificare ogni peso per ridurre l\'errore, cioè il '
           'gradiente della loss rispetto ai pesi. Su una SNN, tre ostacoli distinti lo impediscono, '
           'ciascuno con una soluzione diversa.'))
    A(('img', (F['why_bp'], 'Figura 6.1 — A sinistra: lo spike è un gradino di Heaviside, con derivata '
                            'nulla quasi ovunque (e non definita sulla soglia); il gradiente che '
                            'retropropaga è nullo e la rete non impara. A destra: i tre ostacoli e le '
                            'tre soluzioni corrispondenti.')))
    A(('p', 'Ostacolo A, non differenziabilità (spaziale): la derivata del gradino è nulla quasi '
           'ovunque, il gradiente si annulla e nessun peso si aggiorna. Ostacolo B, credit assignment '
           'temporale: poiché lo stato V[t] dipende da V[t−1], attribuire l\'errore richiede di '
           'propagarlo all\'indietro nel tempo (Backpropagation Through Time, BPTT; Werbos 1990), su una '
           'profondità reale di seq_len × 10 tick, con i noti rischi di gradiente che svanisce o esplode '
           'e un costo di memoria O(T·N). Ostacolo C, implausibilità biologica: il backprop richiede '
           'trasporto simmetrico dei pesi e un segnale d\'errore globale, assenti nel cervello '
           '(rilevante per l\'apprendimento on-chip). La mappa delle soluzioni è: A → surrogate gradient '
           '(§7); B → BPTT e alternative come EventProp (§8); C → STDP e regole locali (§9).'))
    A(('callout', 'Una distinzione spesso confusa: il surrogate gradient risolve solo l\'ostacolo A (la '
                  'non differenziabilità), non l\'ostacolo B (il credit assignment temporale). Sono '
                  'ortogonali: il surrogate si usa dentro il BPTT.'))

    A(('h2', '7. Metodo 1 — Surrogate gradient + BPTT (addestramento di produzione)'))
    A(('p', 'L\'idea è uno Straight-Through Estimator (STE; Bengio et al. 2013): nel forward si usa lo '
           'spike vero (gradino di Heaviside), mentre nel backward si finge che la funzione sia liscia, '
           'sostituendo la derivata inesistente con una curva a campana centrata sulla soglia '
           '(surrogate gradient; Neftci et al. 2019). È lo stesso principio dello STE usato per i pesi '
           'po2 (§15). Nel codice la derivata surrogata è una fast-sigmoid:'))
    A(('img', (F['eq_surrogate'], 'Equazione 7.1 — Derivata surrogata dello spike (core/hardware.py). '
                                  'V = potenziale; θ_eff = soglia effettiva; γ = ampiezza del kernel. '
                                  'Con γ = 1.0 il kernel è più stretto che con un γ minore (es. 0.3): '
                                  'meno neuroni vicini alla soglia sommano il proprio gradiente, riducendo '
                                  'l\'amplificazione attraverso la ricorrenza U·V su 500–1000 tick '
                                  '(≈ 50–100 passi × 10 tick interni).')))
    A(('img', (F['surrogate'], 'Figura 7.1 — Il meccanismo del surrogate gradient: il forward resta un '
                               'gradino binario, il backward usa una campana liscia. Con γ = 1.0 (verde) '
                               'il kernel è più stretto che con γ = 0.3, quindi meno neuroni vicini alla '
                               'soglia contribuiscono al gradiente, con minor rischio di esplosione.')))
    A(('callout', 'Un fatto controintuitivo, dal codice: il backward della surrogata restituisce None '
                  'per il gradiente verso la soglia (scelta hardware-friendly). Di conseguenza '
                  'base_threshold e thresh_jump non ricevono gradiente dallo spike; l\'unico canale '
                  'attraverso cui base_threshold impara è il soft reset (V −= spike·θ_eff). È il motivo '
                  'per cui distaccare (detach) quel reset rende la rete non addestrabile.'))
    A(('p', 'Il surrogate produce un gradiente approssimato — la sua forma dipende dal kernel — e quindi '
           'distorto (biased): è proprio questo il movente per studiare EventProp (§8). La ricetta di '
           'produzione, con le patologie che previene: ALIF + soft reset + surrogate + Adam '
           '(Kingma & Ba 2015) + gradient clipping a norma 1.0 (indispensabile per il BPTT su SNN) + '
           'poche epoche. Senza clipping il gradiente esplode; se lo spike rate collassa a zero (neuroni '
           'morti) il gradiente sparisce, da cui il regolatore L_sr (§12). Un segnale diagnostico '
           'ricorrente: reti da 864 a 9605 parametri si arrestano tutte sullo stesso plateau di errore, '
           'indizio che il collo di bottiglia non è la capacità ma il gradiente e l\'identificabilità.'))

    A(('h2', '8. Metodo 2 — EventProp (gradiente esatto via adjoint)'))
    A(('p', 'EventProp (Wunderlich & Pehle 2021) tratta la SNN come un sistema dinamico con salti e '
           'calcola il gradiente esatto della loss vera (non smussata) risolvendo un\'equazione '
           'aggiunta (adjoint) che si propaga all\'indietro nel tempo, con salti solo agli istanti di '
           'spike. Non usa alcuna surrogata. La memoria scala con il numero di spike, O(#spike), invece '
           'che con l\'intera sequenza, O(T·N). Il movente nel progetto è diretto: se il plateau di '
           'errore dipende dalla distorsione del surrogate, un gradiente esatto dovrebbe superarlo.'))
    A(('img', (F['eventprop'], 'Figura 8.1 — EventProp. A sinistra: memoria O(#spike) contro O(T·N) del '
                               'BPTT. A destra: la variabile aggiunta λ è propagata all\'indietro e '
                               '"salta" solo agli istanti di spike; ai crossing marginali il termine '
                               '1/denom può divergere.')))
    A(('p', 'La fragilità di EventProp è numerica: il salto dell\'adjoint contiene un fattore 1/denom '
           'con denom ≈ (drive − soglia); se uno spike è marginale (il potenziale supera la soglia di '
           'pochissimo) denom tende a zero e il gradiente diverge. Nel progetto questo è governato non '
           'tanto da clamp numerici di sicurezza, quanto da un vincolo spettrale: un termine di loss che '
           'mantiene il raggio spettrale della ricorrenza ρ(U·V) sotto una soglia (§11). La causa '
           'profonda dell\'instabilità era proprio ρ che cresceva facendo divergere l\'adjoint; '
           'vincolarlo rende EventProp contrattivo per costruzione. L\'adjoint completo della soglia '
           'adattiva è risultato corretto ma numericamente neutro, e per questo thresh_jump è congelato '
           'per default sotto EventProp.'))
    A(('callout', 'Cosa EventProp non risolve: non tocca l\'identificabilità/equifinalità (§9) né '
                  'garantisce di uscire dai minimi locali. Fornisce il gradiente giusto, non un '
                  'paesaggio migliore. In CF_FSNN è oggetto di uno studio dedicato (registrato in '
                  'EVENTPROP_STATUS.md); l\'addestramento di produzione resta BPTT+surrogate. '
                  'Concettualmente è un ponte tra le regole locali (STDP) e il gradiente globale (BPTT).'))

    A(('h2', '9. Metodo 3 — STDP e il limite di identificabilità sloppy'))
    A(('p', 'La STDP (Spike-Timing-Dependent Plasticity; Bi & Poo 1998) è una regola di apprendimento '
           'biologica: il peso cambia in base al timing relativo tra spike pre- e post-sinaptico (se il '
           'pre precede il post, potenziamento; viceversa, depressione), con una finestra esponenziale. '
           'È locale e non supervisionata; esistono varianti a tre fattori (R-STDP) che aggiungono un '
           'segnale di ricompensa per il reinforcement learning. CF_FSNN non la usa perché il compito è '
           'una regressione supervisionata a cinque uscite con una loss globale (PINN): la STDP non ha '
           'modo di propagare l\'informazione "l\'accelerazione ricostruita è errata di 4.2 m/s²" fino '
           'ai pesi. Non è inutile — è ottima per feature non supervisionate e apprendimento on-chip — '
           'ma è fuori scopo qui.'))
    A(('p', 'Questa è anche la sede naturale per un concetto spesso trascurato: l\'identificabilità '
           'sloppy. Dai soli dati di car-following, i parametri a e b entrano quasi esclusivamente '
           'attraverso il prodotto √(a·b) nel gap desiderato s*:'))
    A(('img', (F['eq_sstar'], 'Equazione 9.1 — Gap desiderato del modello (core/network.py, '
                              'data/generator.py). s0 = gap minimo da fermo [m]; v = velocità ego [m/s]; '
                              'T = time headway [s]; Δv = v−v_leader [m/s]; a, b = accelerazione massima '
                              'e decelerazione confortevole [m/s²]. a e b compaiono solo tramite √(a·b).')))
    A(('p', 'Il rapporto a/b è quindi non osservabile per costruzione: la rete apprende bene √(a·b) '
           '(errore ~−12%) ma sbaglia a (~−40%) e b (~+30%) in modo che si compensano. È un limite del '
           'problema, non della rete: ingrandirla (da 864 a 9605 parametri) non cambia nulla; il rimedio '
           'agisce sui dati e sugli scenari (aggiungere free-flow e launch ha portato l\'NRMSE di v0 da '
           '0.50 a 0.22). L\'NRMSE (Normalized Root-Mean-Square Error) è l\'errore quadratico medio '
           'normalizzato sul range del parametro (0 = perfetto): l\'obiettivo di riferimento per la '
           'calibrazione dei modelli di traffico è dell\'ordine di 0.20 (Treiber & Kesting 2013).'))
    A(('img', (F['sloppy'], 'Figura 9.1 — La valle piatta dell\'identificabilità. Nel piano (a, b) la '
                            'loss ha una valle lungo √(a·b) = costante: tutti quei punti spiegano '
                            'ugualmente bene la stessa guida. La rete scivola lungo la valle e non '
                            'distingue il valore vero da una stima con lo stesso prodotto.')))
    A(('callout', 'Un corollario che fa da ponte con il report dei risultati: "sicura e stabile" non '
                  'implica "parametri accurati". La rete è conservativa proprio perché il bias su a/b la '
                  'rende prudente. Per questo la metrica primaria è il comportamento fisico — val_data, '
                  'cioè la componente L_data (§12) valutata sul set di validazione, che misura l\'errore '
                  'sull\'accelerazione e non sui parametri — e non l\'NRMSE nuda: un\'NRMSE bassa non '
                  'garantisce una guida sicura.'))
    A(('h3', '9-bis. La quarta via: conversione ANN→SNN (perché non qui)'))
    A(('p', 'Per completezza, si può anche addestrare una ANN classica e convertirla in SNN, sfruttando '
           'l\'equivalenza tra ReLU e frequenza di scarica di un neurone IF con calibrazione delle '
           'soglie (Diehl et al. 2015; Rueckauer et al. 2017). Il metodo dà ottima accuratezza su reti '
           'profonde, ma richiede molti timestep (alta latenza) e non si applica qui: non esiste una '
           'ANN-target, serve la dinamica temporale nativa, e il co-design po2/PINN/FPGA richiede '
           'l\'addestramento diretto.'))

    # ===== PARTE II =====
    A(('h1', 'Parte II — La rete specifica del progetto'))

    A(('h2', '10. Architettura CF_FSNN, strato per strato'))
    A(('p', 'La pipeline è: INPUT(4) → HiddenLayer_ALIF(32) → OutputLayer_LI(5) → decode → [v0, T, s0, '
           'a, b], per un totale di 864 parametri. Ogni passo fisico (0.1 s) è elaborato con 10 tick SNN '
           'interni.'))
    A(('img', (F['arch'], 'Figura 10.1 — Architettura baseline (864 parametri). Lo strato nascosto ALIF '
                          'combina pesi po2, ritardi assonali e una ricorrenza a basso rango U·V; '
                          'l\'uscita è un integratore continuo, decodificato nei cinque parametri fisici.')))
    A(('p', 'Ricorrenza a basso rango. Invece di una matrice ricorrente piena 32×32 (1024 pesi), la '
           'ricorrenza è fattorizzata come prodotto di due matrici, U(32×8) e V(8×32), per 512 pesi '
           '(metà), con inizializzazione ortogonale (gain 0.2). Applicata al vettore di spike del tick '
           'precedente, produce la corrente ricorrente:'))
    A(('img', (F['eq_recur'], 'Equazione 10.1 — Corrente ricorrente (core/network.py). S = vettore di '
                              'spike dello strato nascosto (32) al tick precedente; U, V = fattori della '
                              'ricorrenza; Q(·) = quantizzazione po2 (U e V sono quantizzate '
                              'separatamente). La matrice efficace W_rec = Q(U)·Q(V) ha rango al più 8.')))
    A(('p', 'Il rango 8 è un compromesso di capacità: dimezza i pesi ricorrenti e limita il rango della '
           'dinamica di feedback, riducendo la spinta all\'espansione del raggio spettrale (§11) senza '
           'annullare la memoria. La ricorrenza è ritardata di un tick: il tick t vede gli spike del '
           'tick t−1. Al potenziale si somma anche la corrente feedforward con ritardi assonali: ogni '
           'sinapsi ha un ritardo intero campionato in [0, 6) tick, realizzato con un ring-buffer O(1), '
           'e i pesi feedforward sono ri-scalati di √6 all\'inizializzazione per compensare la varianza '
           'persa a causa della maschera dei ritardi. Sono tick interni (≈0.06 s), non tempi di reazione '
           'biologici.'))
    A(('p', 'Uscita e decode. Lo strato di uscita è un integratore leaky (leak bit-shift, fattore 7/8, '
           'pesi po2, senza spike):'))
    A(('img', (F['eq_li'], 'Equazione 10.2 — Strato di uscita LI (core/neurons.py). y = potenziale del '
                           'leaky integrator; I_out = corrente in ingresso. Il valore finale di y, dopo '
                           'i 10 tick, è il raw decodificato dall\'Equazione 10.3.')))
    A(('p', 'Il potenziale finale è mappato nei cinque parametri fisici tramite una sigmoide vincolata '
           'ai bound per canale:'))
    A(('img', (F['eq_decode'], 'Equazione 10.3 — Decode dei parametri (core/network.py). raw = '
                               'potenziale LI finale; p_lo, p_hi = bound fisici del parametro; off, τ = '
                               'calibrazione per canale (default off=0, τ=1); σ = sigmoide. La sigmoide '
                               'garantisce che ogni parametro resti entro i bound fisici della tabella '
                               'seguente.')))
    A(('p', 'I 864 parametri della baseline (rango 8) si ripartiscono così: fc 128 + rec_U 256 + rec_V '
           '256 + base_threshold 32 + thresh_jump 32 + out_fc 160. Le 64 soglie (32 base_threshold + 32 '
           'thresh_jump) sono apprendibili ma non quantizzate po2. Le varianti a rango 16 (usate da due '
           'dei champion del report gemello) raddoppiano i pesi ricorrenti, per ~1400 parametri. I bound '
           'fisici dei cinque parametri:'))
    A(('table', (
        ['Parametro fisico', 'Simbolo', 'Lo', 'Hi', 'Unità'],
        [['velocità desiderata', 'v0', '8.0', '45.0', 'm/s'],
         ['time headway', 'T', '0.5', '2.5', 's'],
         ['gap minimo fermo', 's0', '1.0', '5.0', 'm'],
         ['accel. massima', 'a', '0.3', '2.5', 'm/s²'],
         ['decel. confortevole', 'b', '0.5', '3.0', 'm/s²']],
    )))

    A(('h2', '11. Il raggio spettrale ρ(U·V): contrattivo vs espansivo'))
    A(('p', 'Il raggio spettrale ρ di una mappa lineare è il modulo del suo autovalore dominante, '
           'ρ(M) = max|λ_i(M)|: indica se applicare ripetutamente la mappa amplifica (ρ>1) o smorza '
           '(ρ<1) lo stato. Applicato alla ricorrenza, ρ(U·V) misura se lo stato del neurone cresce o '
           'si smorza di tick in tick. È il discriminante per l\'FPGA: in aritmetica a virgola fissa '
           '(pochi bit, senza il range dinamico del floating point) una ricorrenza contrattiva (ρ<1) '
           'mantiene lo stato limitato e smorza gli errori di arrotondamento, mentre una espansiva '
           '(ρ>1) li amplifica fino a saturazione o overflow. Nel codice ρ è stimato con la norma '
           'spettrale σ_max della matrice ricorrente (un limite superiore del raggio spettrale) e '
           'riportato nei CSV come rec_spectral_radius.'))
    A(('img', (F['spectral'], 'Figura 11.1 — A sinistra: con ρ<1 lo stato si smorza, con ρ>1 diverge. '
                              'A destra: i quattro champion (i modelli selezionati nel report gemello: '
                              'due BPTT, due EventProp) — i due EventProp (○) sono contrattivi (ρ<1), i '
                              'due BPTT (□) espansivi (ρ>1). I valori di ρ per champion e il verdetto di '
                              'deploy sono in VALIDATION_REPORT_v3 §9.3 e §10.')))
    A(('callout', 'Il doppio ruolo di ρ. La stessa grandezza governa la stabilità in hardware e la '
                  'convergenza dell\'adjoint di EventProp (§8): un ρ crescente fa divergere la variabile '
                  'aggiunta. Il vincolo spettrale usato in addestramento è un termine di loss '
                  'relu(σ_max(Q(U)·Q(V)) − σ*)² con soglia σ* ≈ 1.5 (il regime di esplosione osservato '
                  'inizia intorno a 2.5): rende EventProp contrattivo per costruzione, come confermano i '
                  'champion in VALIDATION_REPORT_v3 §9.3.'))

    A(('h2', '12. L\'approccio PINN: la loss a cinque componenti'))
    A(('p', 'In un approccio PINN (Physics-Informed Neural Network; Raissi et al. 2019) la rete non fa '
           'un fitting cieco dei parametri (che non sono direttamente osservabili): li predice, li '
           'immette nelle equazioni fisiche ACC-IIDM per ricostruire l\'accelerazione, e confronta '
           'questa con quella osservata. La fisica è il ponte tra ciò che la rete produce (cinque '
           'numeri) e ciò che è misurabile (il comportamento). La loss totale è la somma pesata di '
           'cinque termini:'))
    A(('img', (F['eq_loss'], 'Equazione 12.1 — Loss totale (train.py). Ogni L_i è un termine di errore, '
                             'ogni λ_i il suo peso. I pesi attivi sono λ_data = 1.0, λ_phys = 0.1, '
                             'λ_OU = 0.05, λ_bc = 1.0, λ_sr = 0.5.')))
    A(('img', (F['pinn'], 'Figura 12.1 — Il ciclo PINN (sx) e i pesi dei cinque termini (dx). L_data '
                          'misura l\'errore sull\'accelerazione ricostruita, non sui parametri: ecco '
                          'perché parametri diversi possono dare la stessa loss (equifinalità).')))
    A(('table', (
        ['Termine', 'λ', 'Cosa impone', 'Formula (dal codice)'],
        [
            ['L_data', '1.0', 'fit: accel. ricostruita ≈ vera, sui passi con V2X ricevuto', 'RMSE mascherato di (â − a_gt), / N_valid'],
            ['L_phys', '0.1', 'coerenza fisica su tutti i passi (anche V2X mancante)', 'mean((â − a_gt)²)'],
            ['L_OU', '0.05', 'T(t) segue la mean-reversion realistica', 'mean((T_{t+1} − (α·T_t + (1−α)·T̄))²)'],
            ['L_bc', '1.0', 'no-crash: s0 predetto non superi il gap reale', 'mean(relu(s0 − s + 0.1)²)'],
            ['L_sr', '0.5', 'sparsità: spike rate verso 0.15 (anti neuroni morti)', '(spike_rate − 0.15)²'],
        ],
    )))
    A(('p', 'Alcuni fatti di implementazione. L_data è una RMSE mascherata sull\'accelerazione, '
           'normalizzata per il numero di campioni validi (non una SRMSE sull\'energia del target, che '
           'divergerebbe sui tratti a velocità costante, dove l\'accelerazione vera è ~0). L_OU ha un '
           'floor irriducibile (~1.8·10⁻⁴) perché il generatore fa variare T con salti di Markov, non '
           'con un processo OU continuo (§14). L\'accelerazione del leader a_l non è un input: è '
           'ri-stimata da differenze finite filtrate. Esistono termini ausiliari di supervisione diretta '
           'sui parametri, ma sono disattivati per default.'))
    A(('callout', 'Da dove vengono i pesi λ. Sono una calibrazione empirica per bilanciamento d\'ordine '
                  'di grandezza: λ_data = 1 è l\'àncora e gli altri pesi sono scelti perché il contributo '
                  'di ciascun termine resti confrontabile (per esempio λ_phys·L_phys ≈ 0.1·0.2 ≈ 0.02). '
                  'L\'unico peso con una motivazione scritta è λ_sr = 0.5, calibrato su questo criterio '
                  'dopo un addestramento in cui la rete degenerava verso uno spike rate troppo basso; il '
                  'target 0.15 è il centro di una zona di firing sana (~10–25%) per una SNN. I valori '
                  'λ_phys, λ_OU, λ_bc non derivano da uno sweep completato né da un '
                  'valore di letteratura: uno sweep dedicato era pianificato ma non è stato eseguito, e '
                  'un\'ablazione mostra che azzerare i termini fisici sposta la validazione in modo '
                  'trascurabile — i termini PINN pesano poco sull\'accelerazione, pur restando utili '
                  'come vincoli di plausibilità.'))

    A(('h2', '13. Il modello fisico ACC-IIDM (il bersaglio del PINN)'))
    A(('p', 'La rete identifica i parametri di un controllore ACC costruito sull\'IIDM (Improved '
           'Intelligent Driver Model) con blend CAH (Constant-Acceleration Heuristic), nella '
           'formulazione di Treiber & Kesting (2013, cap. 11–12; cfr. Treiber et al. 2000 per l\'IDM di '
           'base e Kesting et al. 2010 per la variante ACC/CAH). Di seguito le equazioni come '
           'implementate nel codice (core/network.py, data/generator.py).'))
    A(('p', 'Il punto di partenza è il gap desiderato s* (Eq. 9.1). Da esso si definiscono il gap '
           'clampato s_safe, il rapporto adimensionale z e il termine di free-flow a_free:'))
    A(('img', (F['eq_iidm'], 'Equazione 13.1 — Grandezze IIDM (core/network.py). s = gap [m]; '
                             's_safe = gap clampato a un minimo di 2.0 m (vedi nota); z = s*/s_safe; '
                             'v = velocità ego [m/s]; v0 = velocità desiderata [m/s]; a = accelerazione '
                             'massima [m/s²]; l\'esponente δ = 4 è fisso.')))
    A(('p', 'L\'IIDM separa il regime di free-flow (z<1) da quello di car-following (z≥1), distinguendo '
           'anche v≤v0 da v>v0; questo elimina il difetto dell\'IDM di base in prossimità di v = v0. '
           'L\'accelerazione IIDM di base ha quattro rami:'))
    A(('table', (
        ['Condizione', 'a_IIDM'],
        [
            ['v ≤ v0,  z < 1', 'a_free·(1 − z²)'],
            ['v ≤ v0,  z ≥ 1', 'a·(1 − z²)'],
            ['v > v0,  z < 1', 'a_free'],
            ['v > v0,  z ≥ 1', 'a_free + a·(1 − z²)'],
        ],
    )))
    A(('p', 'Il termine CAH anticipa la frenata del leader e riduce le sovra-reazioni nei cut-in lievi, '
           'usando la stima dell\'accelerazione del leader a_l:'))
    A(('img', (F['eq_cah'], 'Equazione 13.2 — Constant-Acceleration Heuristic (core/network.py). '
                            'a_l = accelerazione stimata del leader [m/s²]; relu(Δv) = max(Δv, 0) '
                            'considera solo l\'avvicinamento. Il risultato è limitato all\'intervallo '
                            '[−9, a].')))
    A(('p', 'Infine il blend combina IIDM e CAH in modo continuo: quando l\'IIDM è già più prudente del '
           'CAH lo si usa direttamente, altrimenti i due si mescolano in modo morbido con peso di '
           'coolness c = 0.99 (fisso):'))
    A(('table', (
        ['Condizione', 'a_ACC'],
        [
            ['a_IIDM ≥ a_CAH', 'a_IIDM'],
            ['a_IIDM < a_CAH', '(1−c)·a_IIDM + c·(a_CAH + b·tanh((a_IIDM − a_CAH)/b))'],
        ],
    )))
    A(('p', 'A valle, una provvista anti-crash limita l\'accelerazione all\'intervallo [−9, a] m/s².'))
    A(('callout', 'Due dettagli del codice, spesso trascurati. Primo: la rete predice solo cinque dei '
                  'sette parametri — coolness (c = 0.99) e l\'esponente δ (= 4) sono fissi. Secondo: '
                  's_safe è il gap clampato a un minimo di 2.0 m, non 0.5 m; è una scelta di controllo '
                  'del gradiente (con 0.5, in autostrada, il termine v/s_safe raggiungeva ~76 e la '
                  'grad-norm ~8000; con 2.0 scendono a ~19 e ~200), coerente tra simulatore e generatore '
                  'di dati.'))

    A(('h2', '14. Il generatore di dati sintetici'))
    A(('p', 'I dati non provengono da auto reali (costose da strumentare): sono traiettorie sintetiche '
           'generate con lo stesso modello ACC-IIDM. Ogni traiettoria dura 120 s (di cui 20 s di warmup '
           'esclusi dalla loss), cioè circa 1000 passi utili da 0.1 s; il dataset comprende 5000 '
           'traiettorie di training, 500 di validazione, 500 di test. Per ogni passo si registrano '
           '[s, v, Δv, v_leader, v̇, T_vero, mask]; dopo normalizzazione l\'input è (N,4) e il target '
           'fisico è (N,2) = [accelerazione, T_vero].'))
    A(('p', 'Due sorgenti di variabilità meritano la forma esplicita. Il time headway T(t) non è '
           'costante ma segue un processo a salti di Markov (estensione stocastica IDM-2d), non un OU '
           'continuo — da qui il floor di L_OU (§12). Le grandezze percepite portano inoltre un rumore '
           'di Ornstein-Uhlenbeck:'))
    A(('img', (F['eq_ou'], 'Equazione 14.1 — Processo a salti per T(t) (sopra) e rumore OU sulle '
                           'grandezze percepite (sotto). U(T1,T2) = estrazione uniforme; τ_2d ≈ 30 s = '
                           'tempo di persistenza; τ = costante di tempo dell\'OU; ξ = rumore bianco '
                           'gaussiano. Il processo di T è a salti, mentre L_OU (§12) modella una '
                           'mean-reversion continua: da qui il suo floor.')))
    A(('p', 'Il resto della configurazione riproduce condizioni realistiche: un mix di scenari '
           '(highway 50%, urban 30%, truck 10%, mixed 10%, con l\'aggiunta di free-flow e launch per '
           'rendere osservabili v0 e a); profili del leader (costante, sinusoidale, stop-and-go, free, '
           'launch); cut-in nel 20% dei casi (un secondo veicolo si inserisce, gap → 5–15 m); perdita di '
           'pacchetti V2X ~2% (i frame persi escono da L_data ma restano in L_phys). Una variante "wide" '
           'campiona uniformemente i cinque parametri per ampliare la copertura. Le proporzioni degli '
           'scenari e le probabilità sono scelte di configurazione, calibrate per coprire i regimi che '
           'rendono osservabili i diversi parametri (§9), non derivate da un dataset naturalistico.'))

    A(('h2', '15. Quantizzazione Power-of-Two e Straight-Through Estimator'))
    A(('p', 'È il cuore del co-design hardware. I pesi sinaptici sono vincolati a potenze di due, con '
           'esponente clampato in [−4, 1] e i pesi sotto 2⁻⁵ azzerati, per 13 livelli complessivi '
           '{±1/16 … ±2, 0}. Su FPGA, moltiplicare per 2ᵏ è un semplice bit-shift (un ciclo, dell\'ordine '
           'di 10 LUT) invece di una moltiplicazione vera (più cicli, dell\'ordine di 100 LUT):'))
    A(('img', (F['eq_po2'], 'Equazione 15.1 — Quantizzatore po2 e suo gradiente (core/hardware.py). '
                            'w = peso in virgola mobile; l\'esponente arrotondato è clampato in [−4, 1]; '
                            '𝟏[|w| > 2⁻⁵] azzera i pesi piccoli (banda morta). In backward il gradiente '
                            'attraversa la quantizzazione come identità (STE).')))
    A(('img', (F['po2'], 'Figura 15.1 — I 13 livelli po2 con la banda morta |w| < 2⁻⁵ (sx) e il '
                         'risparmio su FPGA: la moltiplicazione diventa uno shift (dx).')))
    A(('p', 'Come si addestra una rete con pesi così discreti? Con lo Straight-Through Estimator (STE; '
           'Bengio et al. 2013), lo stesso principio del surrogate gradient (§7): nel forward si usano '
           'i pesi quantizzati, nel backward il gradiente attraversa la quantizzazione come se fosse '
           'l\'identità e aggiorna i pesi in virgola mobile. La quantizzazione è quindi forward-only '
           'durante l\'addestramento: per questo — in modo controintuitivo — il po2 pesa solo ~0.2% sul '
           'plateau di errore, e l\'affermazione "quantizzare rovina tutto" qui non regge. La coerenza '
           'hardware è totale: anche il leak di membrana è un bit-shift (fattore 7/8) e il reset è '
           'sottrattivo, senza divisori.'))

    # ===== PARTE III =====
    A(('h1', 'Parte III — Bilancio, hardware, stato'))

    A(('h2', '16. Il deployment su FPGA/HDL: il problema aperto'))
    A(('p', 'Una nota di onestà sul target hardware: il modello è addestrato e validato in PyTorch (in '
           'simulazione), ma il deploy su FPGA è un obiettivo di design, non un risultato raggiunto. '
           'Gli strumenti standard di conversione (FINN; Umuroglu et al. 2017) non supportano il '
           'neurone ALIF con soglia adattiva, né la ricorrenza low-rank custom, né i ritardi assonali: '
           'servirebbe HDL scritto a mano, oppure un percorso via Simulink + HDL Coder (nodo aperto, '
           'documentato in FPGA_EVALUATE_DESIGN.md). Le scelte hardware-aware (po2→shift, leak→shift, '
           'surrogata→LUT, ritardi→ring-buffer, reset sottrattivo) sono necessarie ma non sufficienti: '
           'riducono l\'attrito, non lo eliminano. Il vantaggio energetico è una stima da modello di '
           'circuito (Horowitz 2014), non una misura su silicio (i valori per champion sono in '
           'VALIDATION_REPORT_v3 §9.2, il profilo op-count in FPGA_REPORT); restano da validare '
           'l\'utilizzo dei DSP, la banda di memoria e la quantizzazione dello stato (V, fatica) oltre '
           'che dei pesi.'))

    A(('h2', '17. Il triangolo: rileggere tutte le scelte'))
    A(('p', 'Ogni decisione di CF_FSNN è un punto di equilibrio nel triangolo bio-realismo / '
           'addestrabilità / efficienza-hardware.'))
    A(('img', (F['triangle'], 'Figura 17.1 — Le scelte del progetto posizionate nel triangolo. ALIF sta '
                              'al centro (memoria+stabilità); surrogate e PINN spingono verso '
                              'l\'addestrabilità; po2, low-rank e bit-shift verso l\'hardware; EventProp '
                              'riguadagna esattezza al costo di complessità (vincolo spettrale).')))
    A(('table', (
        ['Aspetto', 'Vantaggio', 'Svantaggio / costo onesto'],
        [
            ['SNN vs ANN', 'energia (AC<MAC), temporale nativa, sparsa, piccola (864 par.)', 'più difficile da addestrare; su GPU un MLP sarebbe più preciso'],
            ['ALIF', 'memoria a 2 scale, regola la sparsità, stabilizza', 'complica EventProp e la conversione HDL'],
            ['Surrogate+BPTT', 'funziona, robusto in produzione', 'gradiente biased; richiede clipping; costo O(T·N)'],
            ['EventProp', 'gradiente esatto, contrattivo, memoria O(#spike)', 'fragile ai crossing marginali; ancora sperimentale'],
            ['po2 + STE', 'moltiplicazione → shift; ~0.2% di costo', 'gamut di pesi discreto'],
            ['PINN', 'usa la fisica per compensare la capacità ridotta', 'non risolve l\'identificabilità sloppy'],
        ],
    )))
    A(('callout', 'Queste distinzioni teoriche (il costo AC<MAC vs la sparsità, il ruolo dell\'handler '
                  'V2X "hold-last", NRMSE≠sicurezza, la salute della rete) diventano findings misurati '
                  'sui 4 champion nel report gemello — vedi VALIDATION_REPORT_v3 §9.2 (energia), §8.1 '
                  '(V2X hold-last), §1 e §9.3 (neuroni morti e ρ per champion).'))

    A(('h2', '18. Sintesi end-to-end'))
    A(('p', 'Un episodio completo: l\'input V2X normalizzato entra come corrente; per 10 tick lo strato '
           'ALIF integra, emette spike e si retroalimenta via U·V; lo strato LI accumula il segnale; il '
           'potenziale finale viene decodificato (sigmoide + bound) nei cinque parametri; questi, dati '
           'al controllore ACC-IIDM, guidano un\'auto in anello chiuso, confrontata con l\'oracolo. La '
           'mappa teoria → codice: ALIF (§4) → ALIFCell; codifica (§5) → corrente diretta + LI + 10 '
           'tick; surrogate (§7) → SurrogateSpike_Hardware; EventProp (§8) → ALIFLayer_EventProp_Full; '
           'po2 (§15) → PowerOf2Quantize; PINN (§12) → pinn_loss.'))
    A(('p', 'Lo stato attuale, in modo dichiarato: il plateau di validazione (val_data, l\'errore fisico '
           'sull\'accelerazione) è ~0.19–0.20, allineato al riferimento di calibrazione ~0.20 '
           '(Treiber & Kesting 2013), con un record a 0.1926; l\'accuratezza di identificazione per '
           'champion è riportata in VALIDATION_REPORT_v3 §4.1. Due cause strutturali sono diagnosticate — l\'identificabilità '
           'sloppy di a/b e la qualità del gradiente SNN; l\'esito del confronto BPTT vs EventProp '
           '(fronte di Pareto) e il verdetto di sicurezza sono nel report gemello (VALIDATION_REPORT_v3 '
           '§1, §5, §10). Va sempre distinto ciò che è validato in produzione (BPTT+surrogate, '
           'checkpoint della famiglia Loss_Study) da ciò che è oggetto di studio o roadmap (EventProp, '
           'deploy HDL).'))
    A(('callout', 'Questo documento copre il funzionamento della rete. Per i risultati — i quattro '
                  'champion, il verdetto di deploy (Donatello), le dimensioni di validazione, '
                  'sicurezza/traffico/energia — si veda il documento gemello VALIDATION_REPORT_v3.'))

    A(('h2', '19. Mappa dei file'))
    A(('table', (
        ['Cosa', 'Dove'],
        [
            ['Rete, decode, fisica ACC-IIDM', 'core/network.py'],
            ['Neurone ALIF (leak, soglia adattiva, reset)', 'core/neurons.py'],
            ['Surrogate gradient + po2 (STE)', 'core/hardware.py'],
            ['EventProp adjoint', 'core/eventprop.py'],
            ['Loss PINN a cinque componenti', 'train.py (pinn_loss)'],
            ['Generatore dati (jump-Markov, cut-in, V2X)', 'data/generator.py'],
            ['Risultati e verdetto (documento gemello)', 'document/VALIDATION_REPORT_v3.md'],
            ['Profilo hardware (documento gemello)', 'document/FPGA_REPORT.md'],
            ['Stato dello studio EventProp, vincolo spettrale', 'document/EVENTPROP_STATUS.md'],
            ['Questo documento (generatore)', 'scripts/build_how_it_works_v3.py'],
        ],
    )))
    A(('p', 'Tutti i diagrammi e le equazioni di questo documento sono ricostruiti eseguendo '
           '"python scripts/build_how_it_works_v3.py"; non è richiesto alcun checkpoint.'))

    A(('h2', '20. Riferimenti'))
    A(('table', (
        ['Riferimento', 'Tema'],
        [
            ['McCulloch, W.S., Pitts, W. (1943). A logical calculus of the ideas immanent in nervous activity. Bulletin of Mathematical Biophysics 5, 115–133.', 'Neurone a soglia (§1)'],
            ['Hodgkin, A.L., Huxley, A.F. (1952). A quantitative description of membrane current and its application to conduction and excitation in nerve. J. Physiology 117, 500–544.', 'Modello biofisico (§3, §4)'],
            ['Uhlenbeck, G.E., Ornstein, L.S. (1930). On the theory of the Brownian motion. Physical Review 36, 823–841.', 'Rumore OU (§12, §14)'],
            ['Werbos, P.J. (1990). Backpropagation through time: what it does and how to do it. Proceedings of the IEEE 78(10), 1550–1560.', 'BPTT (§6)'],
            ['Maass, W. (1997). Networks of spiking neurons: the third generation of neural network models. Neural Networks 10(9), 1659–1671.', 'Terza generazione (§1)'],
            ['Bi, G., Poo, M. (1998). Synaptic modifications in cultured hippocampal neurons: dependence on spike timing, synaptic strength, and postsynaptic cell type. J. Neuroscience 18(24), 10464–10472.', 'STDP (§9)'],
            ['Treiber, M., Hennecke, A., Helbing, D. (2000). Congested traffic states in empirical observations and microscopic simulations. Physical Review E 62, 1805–1824.', 'IDM (§13)'],
            ['Izhikevich, E.M. (2003). Simple model of spiking neurons. IEEE Trans. Neural Networks 14(6), 1569–1572.', 'Modello di neurone (§4)'],
            ['Brette, R., Gerstner, W. (2005). Adaptive exponential integrate-and-fire model as an effective description of neuronal activity. J. Neurophysiology 94, 3637–3642.', 'AdEx (§4)'],
            ['Kesting, A., Treiber, M., Helbing, D. (2010). Enhanced intelligent driver model to access the impact of driving strategies on traffic capacity. Phil. Trans. R. Soc. A 368, 4585–4605.', 'ACC / CAH (§13)'],
            ['Bengio, Y., Léonard, N., Courville, A. (2013). Estimating or propagating gradients through stochastic neurons for conditional computation. arXiv:1308.3432.', 'Straight-Through Estimator (§7, §15)'],
            ['Treiber, M., Kesting, A. (2013). Traffic Flow Dynamics: Data, Models and Simulation. Springer.', 'IIDM, CAH, calibrazione (§9, §13)'],
            ['Gerstner, W., Kistler, W.M., Naud, R., Paninski, L. (2014). Neuronal Dynamics: From Single Neurons to Networks and Models of Cognition. Cambridge University Press.', 'LIF / ALIF (§0, §3)'],
            ['Horowitz, M. (2014). Computing\'s energy problem (and what we can do about it). IEEE Int. Solid-State Circuits Conf. (ISSCC), 10–14.', 'Energia AC/MAC (§2, §16)'],
            ['Diehl, P.U., Neil, D., Binas, J., Cook, M., Liu, S.-C., Pfeiffer, M. (2015). Fast-classifying, high-accuracy spiking deep networks through weight and threshold balancing. IJCNN.', 'Conversione ANN→SNN (§9-bis)'],
            ['Kingma, D.P., Ba, J. (2015). Adam: a method for stochastic optimization. Int. Conf. on Learning Representations (ICLR).', 'Ottimizzatore Adam (§7)'],
            ['Rueckauer, B., Lungu, I.-A., Hu, Y., Pfeiffer, M., Liu, S.-C. (2017). Conversion of continuous-valued deep networks to efficient event-driven networks for image classification. Frontiers in Neuroscience 11, 682.', 'Conversione ANN→SNN (§9-bis)'],
            ['Umuroglu, Y., Fraser, N.J., Gambardella, G., et al. (2017). FINN: a framework for fast, scalable binarized neural network inference. ACM/SIGDA Int. Symp. on FPGAs, 65–74.', 'Conversione HDL (§4, §16)'],
            ['Bellec, G., Salaj, D., Subramoney, A., Legenstein, R., Maass, W. (2018). Long short-term memory and learning-to-learn in networks of spiking neurons. Advances in Neural Information Processing Systems (NeurIPS) 31.', 'ALIF / LSNN (§4)'],
            ['Neftci, E.O., Mostafa, H., Zenke, F. (2019). Surrogate gradient learning in spiking neural networks. IEEE Signal Processing Magazine 36(6), 51–63.', 'Surrogate gradient (§7)'],
            ['Raissi, M., Perdikaris, P., Karniadakis, G.E. (2019). Physics-informed neural networks: a deep learning framework for solving forward and inverse problems involving nonlinear PDEs. J. Computational Physics 378, 686–707.', 'PINN (§12)'],
            ['Wunderlich, T.C., Pehle, C. (2021). Event-based backpropagation can compute exact gradients for spiking neural networks. Scientific Reports 11, 12829.', 'EventProp (§8)'],
        ],
    )))
    return D


DOC = build_doc()


# ---------------------------------------------------------------------------
# render md
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
# render pdf (reportlab) — stesso motore del validation report
# ---------------------------------------------------------------------------
def render_pdf(doc, outpath):
    import re
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
    h1 = ParagraphStyle('h1', fontName='DJ-B', fontSize=17, leading=21, spaceBefore=16,
                        spaceAfter=9, textColor=colors.HexColor('#1a3c6e'))
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

    def esc(s):
        s = str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
        return s

    usable_w = A4[0] - 3.6 * cm
    story = []

    def add_image(path, caption):
        img = ImageReader(path)
        iw, ih = img.getSize()
        w = usable_w
        h = w * ih / iw
        max_h = 12.0 * cm
        if h > max_h:
            h = max_h; w = h * iw / ih
        story.append(Spacer(1, 4))
        story.append(Image(path, width=w, height=h))
        story.append(Paragraph(esc(caption), cap))

    def make_table(headers, rows):
        ncol = len(headers)
        fs = 8 if ncol <= 4 else 7.2 if ncol <= 5 else 6.4
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
                         fontSize=11.5, leading=16, textColor=colors.HexColor('#444444'), alignment=1)))
            story.append(Spacer(1, 1.4 * cm))
            story.append(HRFlowable(width='60%', thickness=1, color=colors.HexColor('#9bb8d8')))
            story.append(Spacer(1, 0.6 * cm))
            for m in b['meta']:
                story.append(Paragraph(esc(m), ParagraphStyle('cm', fontName='DJ', fontSize=10,
                             leading=15, alignment=1, textColor=colors.HexColor('#333333'))))
            story.append(PageBreak())
        elif kind == 'h1':
            story.append(PageBreak())
            story.append(Paragraph(esc(b), h1))
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
        canvas.saveState()
        canvas.setFont('DJ', 7.5)
        canvas.setFillColor(colors.HexColor('#888888'))
        canvas.drawString(2 * cm, 1.1 * cm, 'CF_FSNN — Come Funziona (v3)')
        canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f'pag. {docx.page}')
        canvas.restoreState()

    pdf = SimpleDocTemplate(outpath, pagesize=A4, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm, title='CF_FSNN Come Funziona v3')
    pdf.build(story, onFirstPage=footer, onLaterPages=footer)
    print('  scritto', outpath)


print('[2/4] render markdown...')
render_md(DOC, os.path.join(DOCDIR, 'HOW_IT_WORKS_v3.md'))
print('[3/4] render pdf...')
render_pdf(DOC, os.path.join(DOCDIR, 'HOW_IT_WORKS_v3.pdf'))
print('[4/4] fatto.')
