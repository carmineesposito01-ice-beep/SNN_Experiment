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


print('[1/4] genero diagrammi concettuali...')
F = {
    'inverse': fig_inverse(), 'ann_snn': fig_ann_vs_snn(), 'membrane': fig_membrane(),
    'hierarchy': fig_hierarchy(), 'coding': fig_coding_datapath(), 'why_bp': fig_why_backprop(),
    'surrogate': fig_surrogate(), 'eventprop': fig_eventprop(), 'sloppy': fig_sloppy(),
    'arch': fig_architecture(), 'spectral': fig_spectral(), 'pinn': fig_pinn(),
    'po2': fig_po2(), 'energy': fig_energy(), 'triangle': fig_triangle(),
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
        'subtitle': 'La rete spiega se stessa: SNN vs ANN, addestramento (BPTT, EventProp, STDP), '
                    'l\'architettura del progetto, l\'approccio PINN e il co-design per FPGA',
        'meta': [
            'Versione: 2026-07-01  (branch EventProp_Study) — supersede HOW_IT_WORKS.md (v1) e _v2',
            'Documento gemello: VALIDATION_REPORT_v3 spiega i RISULTATI; questo spiega LA RETE',
            'Fondato sul codice live (core/network.py, neurons.py, hardware.py, eventprop.py, train.py)',
            'Lettore atteso: ingegnere che parte da zero sulle SNN e vuole piena coscienza in ~45 minuti',
        ],
    }))

    # ===== PARTE I =====
    A(('h1', 'Parte I — Cos\'è una SNN e come si addestra'))

    A(('h2', '0. Bussola: il problema, i 3 concetti-chiave, i documenti gemelli'))
    A(('p', 'CF_FSNN risolve un PROBLEMA INVERSO. Non prevede dove andrà l\'auto: osserva una '
           'traiettoria di car-following (gap dal veicolo davanti, velocità propria, differenza di '
           'velocità Δv, velocità del leader — tutto via V2X) e ne IDENTIFICA i 5 numeri che la '
           'generano, cioè i parametri del modello di guida ACC-IIDM: [v0, T, s0, a, b]. Questa '
           'distinzione va tenuta a mente per tutto il documento: tutto ciò che segue (loss, '
           'identificabilità, metriche) ha senso solo alla luce del fatto che stimiamo PARAMETRI, '
           'non traiettorie.'))
    A(('img', (F['inverse'], 'Figura 0.1 — Il problema inverso. La SNN mappa la traiettoria osservata '
                             'nei 5 parametri; questi, immessi nel modello fisico ACC-IIDM, '
                             'ricostruiscono l\'accelerazione, che viene confrontata con quella '
                             'osservata per formare la loss.')))
    A(('p', 'Una SNN (Spiking Neural Network) ha 3 proprietà irriducibili che la distinguono da una '
           'rete classica (ANN): (1) DINAMICA TEMPORALE — ogni neurone ha uno stato interno che '
           'persiste e integra gli input nel tempo; (2) COMPUTAZIONE SPARSA A EVENTI — comunica con '
           'impulsi (spike) e l\'energia è proporzionale al numero di spike, non di moltiplicazioni; '
           '(3) ATTIVAZIONE NON DIFFERENZIABILE — lo spike è un gradino (0/1), la cui derivata è '
           'nulla quasi ovunque. Queste tre proprietà generano tutto il resto: la terza obbliga a '
           'reinventare l\'addestramento (Parte I), le prime due giustificano le scelte hardware '
           '(Parte II).'))
    A(('callout', 'Filo conduttore. Ogni decisione di progetto vive in un TRIANGOLO con tre vertici in '
                  'tensione: bio-realismo ↔ addestrabilità ↔ efficienza hardware. Guadagnare su un '
                  'vertice costa sugli altri. Torneremo su questo triangolo alla fine (§17) per '
                  'rileggere tutte le scelte come punti in questo spazio.'))
    A(('callout', 'Documenti gemelli. Questo documento (HOW_IT_WORKS_v3) spiega LA RETE. Il suo gemello '
                  'VALIDATION_REPORT_v3 spiega i RISULTATI (4 champion, verdetto di deploy, 15 dimensioni '
                  'di validazione). Quando qui incontri ρ(U·V), ALIF, po2, EventProp, sparsità — il '
                  'report li USA dando per scontato che tu li conosca; è qui che li fondiamo.'))

    A(('h2', '1. Le tre generazioni di reti neurali'))
    A(('p', 'Una SNN è la "terza generazione" di rete neurale (Maass, 1997). 1ª generazione: il '
           'percettrone (McCulloch-Pitts), unità a soglia con uscita binaria, nessuna nonlinearità '
           'continua. 2ª generazione: le ANN moderne (sigmoid, ReLU) — ogni unità emette un VALORE '
           'REALE ad ogni forward pass, ed è differenziabile ovunque, per questo si addestrano con '
           'la backpropagation. 3ª generazione: le SNN — l\'unità comunica con SPIKE (eventi discreti) '
           'nel TEMPO continuo; il tempo non è un semplice indice di layer ma parte della '
           'rappresentazione. Un singolo spike temporizzato può, in teoria, codificare più '
           'informazione di un valore rate-based, e su hardware neuromorfico l\'energia scala con '
           'gli eventi.'))
    A(('callout', 'Equivoco da evitare: "terza generazione" NON significa "più accurata". Significa un '
                  'ASSE DI OTTIMIZZAZIONE diverso — energia, latenza, idoneità al silicio — spesso '
                  'pagato con un po\' di accuratezza. Su una GPU, per questo stesso compito, un MLP '
                  'sarebbe più semplice e preciso; il valore della SNN sta nel target FPGA.'))

    A(('h2', '2. ANN vs SNN su assi multipli'))
    A(('p', 'Il confronto non va fatto su un solo asse ("le SNN sono più efficienti"): differiscono '
           'su almeno sei assi indipendenti, e ognuno ha una conseguenza concreta per CF_FSNN.'))
    A(('table', (
        ['Asse', 'ANN (2ª gen.)', 'SNN (3ª gen.)', 'Implicazione per CF_FSNN'],
        [
            ['Unità di comunicazione', 'valore reale per layer', 'treno di spike 0/1 nel tempo', 'output leggibile solo integrando i spike'],
            ['Stato / memoria', 'stateless per campione', 'potenziale di membrana persistente', 'nativamente adatta a serie temporali (traiettorie)'],
            ['Computazione', 'MAC densi sincroni', 'accumulo + confronto soglia, event-driven', 'energia ∝ spike; sparsità ~13-19%'],
            ['Differenziabilità', 'end-to-end', 'gradino di Heaviside (non diff.)', 'serve surrogate / EventProp (§6–8)'],
            ['Hardware ideale', 'GPU / TPU (matmul densa)', 'neuromorfico / FPGA (memoria-vicino-calcolo)', 'target PYNQ-Z1; pesi po2 → shift'],
            ['Dati nativi', 'tensori densi', 'eventi / serie temporali', 'input V2X sequenziale'],
        ],
    )))
    A(('img', (F['ann_snn'], 'Figura 2.1 — Neurone ANN vs neurone spiking. La differenza strutturale '
                             'non è "reale vs binario", ma la presenza di uno STATO che evolve nel '
                             'tempo e di una soglia non differenziabile.')))
    A(('p', 'Una precisazione che il report dà per scontata e che conviene anticipare qui: il '
           'vantaggio energetico delle SNN NON viene dalla sparsità in sé. Le operazioni sinaptiche '
           '(SynOps, l\'analogo spiking dei MAC) di questa rete eguagliano o superano i MAC di una ANN equivalente; a parità di '
           'costo per operazione la SNN sarebbe anzi peggiore. Il guadagno viene dal minor costo '
           'unitario di un ACCUMULO (AC) rispetto a una MOLTIPLICAZIONE-ACCUMULO (MAC) — e su FPGA '
           'con pesi potenze-di-due l\'AC diventa un semplice shift+add. Ne segue la regola: più '
           'sparsità = più vantaggio. Il payoff energetico misurato per champion vive nel gemello '
           'VALIDATION_REPORT_v3 §9.2, e il profilo hardware nel FPGA_REPORT.'))
    A(('img', (F['energy'], 'Figura 2.2 — Perché la SNN è più efficiente pur facendo lo stesso numero '
                            '(o più) di operazioni: il costo unitario AC < MAC. La sparsità amplifica '
                            'il margine, non lo crea.')))

    A(('h2', '3. Dal neurone biologico al neurone LIF'))
    A(('p', 'Il neurone artificiale spiking è un\'astrazione minimale del neurone biologico. In 5 '
           'fatti: la membrana si comporta come un condensatore che accumula carica; gli input '
           'sinaptici la caricano (integrazione); la membrana perde carica nel tempo (LEAK, con '
           'costante di tempo τ) — cioè il neurone "dimentica" gli input vecchi; al superamento di '
           'una SOGLIA emette un impulso (spike / potenziale d\'azione); dopo lo spike si RESETTA. '
           'Questo è il modello Integrate-and-Fire con leak (LIF). Non serve il realismo completo '
           'della biofisica (Hodgkin-Huxley, 4 equazioni differenziali per i canali ionici): '
           'l\'obiettivo è la computazione e l\'energia, non riprodurre l\'elettrofisiologia.'))
    A(('img', (F['membrane'], 'Figura 3.1 — Dinamica di un neurone LIF: l\'input carica il potenziale, '
                              'il leak lo fa decadere in assenza di stimolo, al superamento della soglia '
                              'si genera uno spike e il potenziale si riduce (reset sottrattivo).')))

    A(('h2', '4. La gerarchia dei modelli e perché CF_FSNN usa ALIF'))
    A(('p', 'I modelli di neurone formano una gerarchia di "spogliazione" progressiva: più si scende, '
           'meno dettaglio biologico e più addestrabilità/velocità. Dall\'alto: Hodgkin-Huxley (4 ODE) '
           '→ AdEx (2 ODE) → Izhikevich (2 ODE, 20 pattern di scarica) → ALIF (LIF + soglia adattiva) '
           '→ LIF (1 ODE + reset) → IF (integratore puro). La regola pratica: immagini statiche → LIF; '
           'compiti sequenziali/con memoria lunga → ALIF/LSNN; neuroscienza → Izhikevich/AdEx; '
           'biofisica → HH.'))
    A(('img', (F['hierarchy'], 'Figura 4.1 — Gerarchia dei neuroni (sx) e comportamento ALIF vs LIF (dx). '
                               'L\'ALIF alza la soglia a ogni spike (fatica) e poi la lascia decadere, '
                               'riducendo la frequenza di scarica nel tempo.')))
    A(('p', 'CF_FSNN usa ALIF (Adaptive Leaky Integrate-and-Fire): un LIF con una variabile di '
           'adattamento in più — una FATICA che alza temporaneamente la soglia effettiva a ogni spike '
           'e poi decade. Nel codice: soglia_effettiva = base_threshold + fatica, con base_threshold e '
           'thresh_jump (l\'incremento per spike) entrambi apprendibili, con init base_threshold=1.5 e thresh_jump=0.5. '
           'Perché ALIF e non LIF puro? Tre ragioni, tutte di addestrabilità/hardware, non ornamentali: '
           '(1) il car-following è un problema temporale che beneficia di una memoria a due scale '
           '(veloce = membrana, lenta = fatica); (2) la fatica REGOLA la sparsità del firing e '
           'stabilizza il training — è documentato che azzerando thresh_jump il training ESPLODE, che '
           'l\'ottimo è ~0.5 e che valori più alti causano underfit; (3) aggiunge solo 2 stati per '
           'neurone, resta economica su FPGA.'))
    A(('callout', 'Costo onesto di ALIF: complica sia l\'addestramento con EventProp (la soglia adattiva '
                  'aggiunge una dinamica di cui tenere conto nell\'adjoint) sia la conversione in HDL — '
                  'gli strumenti standard (FINN) non supportano il neurone ALIF (vedi §16). E un valore '
                  'di soglia iniziale troppo alto negli strati non-input può "spegnere" i neuroni: la '
                  'taratura conta.'))

    A(('h2', '5. Codifica neurale: input continuo, spiking interno (sezione ad alto rischio di equivoci)'))
    A(('p', 'Come entrano ed escono i numeri da una rete a impulsi? Esistono molti schemi di codifica '
           '(rate coding = conteggio spike in una finestra; temporale = i tempi precisi degli spike; '
           'time-to-first-spike; popolazione; fase; burst). MA — ed è l\'equivoco numero uno da '
           'prevenire — in CF_FSNN l\'INPUT NON è codificato in spike. I 4 segnali V2X, normalizzati '
           'in [0,1], entrano come CORRENTE DIRETTA (I = W·x): sono iniettati nel potenziale, non '
           'convertiti in treni di impulsi Poisson o a latenza. Solo lo strato nascosto ALIF spara; '
           'lo strato di uscita è un integratore continuo (LI = Leaky Integrator) SENZA spike. La rete è quindi IBRIDA: '
           'continuo → spiking → continuo.'))
    A(('img', (F['coding'], 'Figura 5.1 — Il percorso del segnale. Continuo in ingresso (corrente '
                            'diretta), spiking solo nell\'hidden ALIF, continuo in uscita (LI). '
                            'Ogni passo fisico da 0.1 s è elaborato con 10 tick SNN interni a input '
                            'costante — tempo di "assestamento", non nuova informazione.')))
    A(('p', 'Due conseguenze. (a) L\'output si legge dal POTENZIALE dell\'ultimo strato LI (voltage '
           'decoding), non da un conteggio di spike: a soli 10 tick il rate coding sarebbe troppo '
           'rumoroso, il voltage decoding è più stabile e a bassa latenza. (b) I 10 tick interni per '
           'ogni passo NON portano nuova informazione, ma decuplicano la profondità temporale reale '
           'vista dall\'addestramento (una traiettoria di 50 passi diventa una catena di 500 tick) — '
           'un aggravante per il problema che vediamo ora. Da evitare anche l\'equivoco opposto: non '
           'è "una ANN col leak", perché l\'hidden ha soglia vera, reset e non-differenziabilità.'))

    A(('h2', '6. Perché il backprop classico NON può funzionare'))
    A(('p', 'Addestrare significa calcolare come cambiare ogni peso per ridurre l\'errore — cioè il '
           'gradiente della loss rispetto ai pesi. Su una SNN, tre ostacoli DISTINTI lo impediscono, '
           'e ognuno richiede una soluzione diversa.'))
    A(('img', (F['why_bp'], 'Figura 6.1 — A sinistra: lo spike è un gradino di Heaviside, la cui '
                            'derivata è zero quasi ovunque (e infinita sulla soglia) → il gradiente '
                            'che torna indietro è nullo, la rete non impara. A destra: i tre ostacoli '
                            'e le tre soluzioni corrispondenti.')))
    A(('p', 'Ostacolo A — NON DIFFERENZIABILITÀ (spaziale): la derivata del gradino è nulla quasi '
           'ovunque, il gradiente si annulla e nessun peso si aggiorna. Ostacolo B — CREDIT '
           'ASSIGNMENT TEMPORALE: poiché lo stato V[t] dipende da V[t−1], per attribuire l\'errore '
           'bisogna propagarlo all\'indietro nel tempo (Backpropagation Through Time, BPTT), su una '
           'profondità reale di seq_len × 10 tick — con i noti rischi di gradiente che svanisce o '
           'esplode e un costo di memoria O(T·N). Ostacolo C — IMPLAUSIBILITÀ BIOLOGICA: il backprop '
           'richiede trasporto simmetrico dei pesi e un segnale d\'errore globale, assenti nel '
           'cervello (rilevante per l\'apprendimento on-chip). La mappa è: A → surrogate gradient (§7); '
           'B → BPTT ed alternative come EventProp (§8); C → STDP e regole locali (§9).'))
    A(('callout', 'Distinzione critica, spesso confusa: il surrogate gradient risolve SOLO l\'ostacolo '
                  'A (la non-differenziabilità), NON il B (il credit assignment temporale). Sono '
                  'ortogonali: si usa il surrogate DENTRO il BPTT.'))

    A(('h2', '7. Metodo 1 — Surrogate gradient + BPTT (l\'addestramento di produzione)'))
    A(('p', 'L\'idea è uno Straight-Through Estimator: nel FORWARD si usa lo spike vero (gradino di '
           'Heaviside), ma nel BACKWARD si finge che la funzione sia liscia, sostituendo la derivata '
           'inesistente con una curva a campana centrata sulla soglia. È lo stesso principio dello STE '
           'usato per i pesi po2 (§15). Nel codice la surrogata è 1/(1+γ|V−θ|)² con γ=1.0 (era 0.3): '
           'un kernel più stretto fa contribuire al gradiente meno neuroni vicini alla soglia, '
           'riducendo l\'amplificazione attraverso la ricorrenza U·V su 500–1000 tick (≈ seq_len 50–100 passi × 10 tick interni).'))
    A(('img', (F['surrogate'], 'Figura 7.1 — Il trucco del surrogate gradient: il forward resta un '
                               'gradino binario, il backward usa una campana liscia. Con γ=1.0 (verde) '
                               'il kernel è più stretto che con γ=0.3, quindi meno neuroni "near-soglia" '
                               'sommano il loro gradiente → meno rischio di esplosione.')))
    A(('callout', 'Fatto controintuitivo (dal codice): il backward della surrogata ritorna None per il '
                  'gradiente verso la soglia (scelta hardware-friendly). Conseguenza: base_threshold e '
                  'thresh_jump NON ricevono gradiente dallo spike; l\'UNICO canale attraverso cui '
                  'base_threshold impara è il soft reset (V −= spike·θ_eff). È il motivo per cui '
                  'staccare (detach) quel reset ha reso la rete non-addestrabile e va evitato.'))
    A(('p', 'Il surrogate produce un gradiente APPROSSIMATO (dipende dalla forma del kernel), quindi '
           'BIASED — ed è proprio questo il movente per studiare EventProp. La ricetta di produzione, '
           'con le patologie reali che previene: ALIF + soft reset + surrogate + Adam + GRADIENT '
           'CLIPPING a norma 1.0 (non negoziabile per BPTT su SNN) + poche epoche. Senza clipping il '
           'gradiente esplode; se lo spike rate collassa a zero (dead neurons) il gradiente sparisce '
           '(da qui il regolatore L_sr, §12). Segnale diagnostico chiave osservato: reti da 864 a 9605 '
           'parametri si fermano tutte sullo stesso plateau — indizio che il collo di bottiglia non è '
           'la capacità ma il gradiente/identificabilità.'))

    A(('h2', '8. Metodo 2 — EventProp (gradiente esatto via adjoint)'))
    A(('p', 'EventProp (Wunderlich & Pehle, 2021) tratta la SNN come un sistema dinamico con salti e '
           'calcola il gradiente ESATTO della loss vera (non smussata) risolvendo un\'equazione '
           'AGGIUNTA (adjoint) che si propaga all\'indietro nel tempo con salti SOLO agli istanti di '
           'spike. Niente surrogata. La memoria scala con il numero di spike, O(#spike), non con tutta '
           'la sequenza O(T·N). Il movente diretto nel progetto: se il plateau di errore è colpa del '
           'BIAS del surrogate, un gradiente esatto dovrebbe romperlo.'))
    A(('img', (F['eventprop'], 'Figura 8.1 — EventProp. A sinistra: memoria O(#spike) contro O(T·N) del '
                               'BPTT. A destra: la variabile aggiunta λ viene propagata all\'indietro e '
                               '"salta" solo agli istanti di spike; ai crossing marginali il termine '
                               '1/denom può esplodere.')))
    A(('p', 'La fragilità di EventProp è numerica: il salto dell\'adjoint contiene un fattore '
           '1/denom con denom ≈ (drive − soglia); se uno spike è "marginale" (il potenziale supera la '
           'soglia di pochissimo) denom→0 e il gradiente esplode. Nel progetto questo è governato non '
           'tanto dai clamp di sicurezza (jump_clamp, lv_clamp: le stabilizzazioni C8), quanto da un '
           'VINCOLO SPETTRALE (C11): un termine di loss che tiene il raggio spettrale della ricorrenza '
           'ρ(U·V) sotto controllo. La causa profonda dell\'instabilità era proprio ρ che cresceva e '
           'faceva divergere l\'adjoint; vincolarlo rende EventProp contrattivo PER COSTRUZIONE (§11). '
           'Nell\'implementazione, l\'adjoint completo della soglia adattiva (C13) è risultato '
           'corretto ma neutro, quindi thresh_jump è congelato di default.'))
    A(('callout', 'Cosa EventProp NON risolve: non tocca l\'identificabilità/equifinalità (§9) né '
                  'garantisce di uscire dai minimi locali. Dà il "gradiente giusto", non un "paesaggio '
                  'migliore". Stato: EventProp è oggetto di studio (branch EventProp_Study); '
                  'l\'addestramento di PRODUZIONE resta BPTT+surrogate. EventProp è un "ponte" '
                  'tra le regole locali (STDP) e il gradiente globale (BPTT).'))

    A(('h2', '9. Metodo 3 — STDP, e il limite strutturale dell\'identificabilità'))
    A(('p', 'STDP (Spike-Timing-Dependent Plasticity) è la regola di apprendimento biologica: il peso '
           'cambia in base al TIMING relativo tra spike pre- e post-sinaptico (se il pre precede il '
           'post → potenziamento; viceversa → depressione), con una finestra esponenziale. È LOCALE e '
           'NON SUPERVISIONATA (esistono varianti a tre fattori, R-STDP, che aggiungono un segnale di '
           'ricompensa/neuromodulatore per il reinforcement learning). Perché CF_FSNN NON usa STDP? '
           'Perché il compito è una REGRESSIONE SUPERVISIONATA a 5 uscite con una loss globale (PINN): '
           'STDP non ha modo di propagare l\'informazione "l\'accelerazione ricostruita è sbagliata di '
           '4.2 m/s²" fino ai pesi. Non è inutile — è ottima per feature unsupervised e apprendimento '
           'on-chip — è semplicemente fuori scopo qui.'))
    A(('p', 'Questa sezione è anche il posto giusto per il concetto più spesso trascurato, che il '
           'report dà per scontato: l\'IDENTIFICABILITÀ SLOPPY. Dai soli dati di car-following, i '
           'parametri a e b entrano quasi esclusivamente attraverso il prodotto √(a·b) nel gap '
           'desiderato s* = s0 + max(0, v·T + v·Δv/(2·√(a·b))). Il RAPPORTO a/b è quindi NON '
           'OSSERVABILE per costruzione: la rete impara bene √(a·b) (~−12% di errore) ma sbaglia a '
           '(~−40%) e b (~+30%) in modo che si compensano. È un limite del PROBLEMA, non della rete: '
           'ingrandire la rete (864→9605 parametri) non cambia nulla; il rimedio è sui DATI/scenari '
           '(aggiungere free-flow e launch ha portato v0 da NRMSE 0.50 a 0.22). NRMSE (Normalized '
           'Root-Mean-Square Error) è l\'errore quadratico medio normalizzato sul range del parametro '
           '(0 = perfetto, più basso = meglio); l\'obiettivo di riferimento di Treiber è ~0.20.'))
    A(('img', (F['sloppy'], 'Figura 9.1 — La "valle piatta" dell\'identificabilità. Nel piano (a, b) la '
                            'loss ha una valle lungo √(a·b)=costante: tutti quei punti spiegano '
                            'ugualmente bene la stessa guida. La rete scivola lungo la valle e non sa '
                            'distinguere il valore vero da una stima con lo stesso prodotto.')))
    A(('callout', 'Corollario cruciale (ponte col report): "sicura e stabile" NON implica "parametri '
                  'accurati". La rete è conservativa proprio perché il bias su a/b la rende prudente. '
                  'Per questo la metrica primaria è il comportamento fisico — val_data, cioè la '
                  'componente L_data (§12) valutata sul set di validazione, che misura l\'errore '
                  'sull\'ACCELERAZIONE (la guida) e non sui parametri — non la NRMSE '
                  'nuda: una NRMSE bassa non garantisce una guida sicura.'))
    A(('h3', '9-bis. La quarta via: conversione ANN→SNN (perché non qui)'))
    A(('p', 'Per completezza: si può anche addestrare una ANN classica e CONVERTIRLA in SNN (equivalenza '
           'tra ReLU e frequenza di scarica di un neurone IF, con calibrazione delle soglie). Dà '
           'ottima accuratezza su reti profonde ma richiede molti timestep (alta latenza) e non si '
           'applica qui: non abbiamo una ANN-target, serve la dinamica temporale nativa, e il '
           'co-design po2/PINN/FPGA richiede l\'addestramento diretto.'))

    # ===== PARTE II =====
    A(('h1', 'Parte II — La rete specifica del progetto'))

    A(('h2', '10. Architettura CF_FSNN, strato per strato'))
    A(('p', 'La pipeline: INPUT(4) → HiddenLayer_ALIF(32) → OutputLayer_LI(5) → decode → [v0,T,s0,a,b]. '
           'Totale 864 parametri. Ogni passo fisico è elaborato con 10 tick SNN interni.'))
    A(('img', (F['arch'], 'Figura 10.1 — Architettura baseline (864 parametri). Lo strato nascosto ALIF '
                          'combina pesi po2 con delay assonali e una ricorrenza a basso rango U·V; '
                          'l\'uscita è un integratore continuo, decodificato nei 5 parametri fisici.')))
    A(('p', 'Dettagli che contano. RICORRENZA LOW-RANK: invece di una matrice ricorrente piena 32×32 '
           '(1024 pesi), si fattorizza come U(32×8)·V(8×32) = 512 pesi (metà), init ortogonale gain '
           '0.2. È qui che vive il raggio spettrale ρ(U·V) (§11). DELAY ASSONALI: ogni sinapsi ha un '
           'ritardo intero campionato in [0,6) tick, realizzato con un ring-buffer O(1); attenzione, '
           'sono tick SNN interni (≈0.06 s), non il tempo di reazione biologico. OUTPUT LI: '
           'integratore leaky con leak bit-shift (7/8) e pesi po2, SENZA spike. DECODE: '
           'param = lo + (hi−lo)·sigmoid((raw − offset)/τ), con bound fisici per canale; offset e τ '
           'sono la calibrazione R29 (di default offset=0, τ=1). I 864 parametri: fc 128 + rec_U 256 '
           '+ rec_V 256 + base_threshold 32 + thresh_jump 32 + out_fc 160 — le 64 soglie (32 base_threshold + 32 thresh_jump) sono '
           'apprendibili ma NON quantizzate po2.'))
    A(('table', (
        ['Parametro fisico', 'Simbolo', 'Lo', 'Hi', 'Unità'],
        [['velocità desiderata', 'v0', '8.0', '45.0', 'm/s'],
         ['time headway', 'T', '0.5', '2.5', 's'],
         ['gap minimo fermo', 's0', '1.0', '5.0', 'm'],
         ['accel. massima', 'a', '0.3', '2.5', 'm/s²'],
         ['decel. confortevole', 'b', '0.5', '3.0', 'm/s²']],
    )))

    A(('h2', '11. Il raggio spettrale ρ(U·V): contrattivo vs espansivo'))
    A(('p', 'Il raggio spettrale ρ di una mappa lineare è il suo autovalore dominante in modulo: dice '
           'se applicare ripetutamente la mappa AMPLIFICA (ρ>1) o SMORZA (ρ<1) lo stato. Applicato '
           'alla ricorrenza U·V, ρ(U·V) misura se lo stato del neurone cresce o si smorza di tick in '
           'tick. Perché è IL discriminante per FPGA: in aritmetica a virgola fissa (pochi bit, senza '
           'il range dinamico del float) una ricorrenza contrattiva (ρ<1) mantiene lo stato limitato e '
           'gli errori di arrotondamento si smorzano; una espansiva (ρ>1) li amplifica fino a '
           'saturazione/overflow. (Nota tecnica: nel codice ρ è misurato come norma spettrale σ_max '
           'della matrice ricorrente — un limite superiore del vero raggio spettrale — riportata nei '
           'CSV come rec_spectral_radius.)'))
    A(('img', (F['spectral'], 'Figura 11.1 — A sinistra: con ρ<1 lo stato si smorza, con ρ>1 diverge. '
                              'A destra: i 4 champion (i quattro modelli migliori selezionati nel report '
                              'gemello: 2 BPTT, 2 EventProp) — i due EventProp (○) sono contrattivi '
                              '(ρ<1), i due BPTT (□) espansivi (ρ>1). I valori di ρ misurati sui champion '
                              'e il verdetto di deploy sono in VALIDATION_REPORT_v3 §9.3 e §10.')))
    A(('callout', 'Doppio ruolo di ρ. La stessa grandezza governa (a) la stabilità in hardware e '
                  '(b) la convergenza dell\'adjoint di EventProp (ρ che cresce fa divergere λ, §8). Il '
                  'vincolo spettrale C11 rende EventProp contrattivo per costruzione (confermato sui '
                  'champion in VALIDATION §9.3).'))

    A(('h2', '12. L\'approccio PINN: la loss a 5 componenti'))
    A(('p', 'PINN (Physics-Informed Neural Network) significa: la rete non fa un fitting cieco dei '
           'parametri (che non sono direttamente osservabili), ma li PREDICE, li immette nelle '
           'equazioni fisiche ACC-IIDM per RICOSTRUIRE l\'accelerazione, e confronta questa con quella '
           'osservata. La fisica è il ponte tra ciò che la rete produce (5 numeri) e ciò che possiamo '
           'misurare (il comportamento).'))
    A(('img', (F['pinn'], 'Figura 12.1 — Il ciclo PINN (sx) e i pesi dei 5 termini (dx). Punto chiave: '
                          'L_data misura l\'errore sull\'accelerazione ricostruita, non sui parametri — '
                          'ecco perché parametri diversi possono dare la stessa loss (equifinalità).')))
    A(('table', (
        ['Termine', 'λ', 'Cosa impone', 'Formula (dal codice)'],
        [
            ['L_data', '1.0', 'fit: accel. ricostruita ≈ vera, sui passi con V2X ricevuto', 'RMSE mascherato / N_valid'],
            ['L_phys', '0.1', 'coerenza fisica su TUTTI i passi (anche V2X mancante)', 'mean((â − a_gt)²)'],
            ['L_OU', '0.05', 'T(t) segue la mean-reversion realistica', 'residuo OU su T'],
            ['L_bc', '1.0', 'no-crash: s0 predetto non superi il gap reale', 'mean(relu(s0−s+0.1)²)'],
            ['L_sr', '0.5', 'sparsità: spike rate verso il 15% (anti dead-neuron)', '(spike_rate − 0.15)²'],
        ],
    )))
    A(('p', 'Alcune verità del codice che il vecchio documento riportava male: L_data NON è più una '
           'SRMSE normalizzata sull\'energia del target (formula che esplodeva quando l\'accelerazione '
           'vera è ~0 su un tratto a velocità costante), ma una RMSE normalizzata per il numero di '
           'campioni validi. L_OU ha un "floor" irriducibile (~1.8e-4) perché il generatore fa variare '
           'T con salti di Markov, non con un vero processo OU continuo. L\'accelerazione del leader '
           'a_l non è un input: è ri-stimata da differenze finite filtrate. Esistono anche termini '
           'ausiliari di supervisione DIRETTA sui parametri (aggiunti negli studi R25/R30) ma sono '
           'disattivati di default. Diagnosi importante: azzerare phys/ou/bc sposta la val in modo '
           'trascurabile → il PINN non è il collo di bottiglia; il grosso del plateau è architettura/'
           'gradiente (ablazioni quantitative in EVENTPROP_STATUS/VALIDATION).'))

    A(('h2', '13. Il modello fisico ACC-IIDM (il bersaglio del PINN)'))
    A(('p', 'La rete identifica i parametri di un controllore ACC basato su IIDM (Improved Intelligent '
           'Driver Model) con blend CAH (Treiber & Kesting, Cap. 12). Vale la pena conoscere le '
           'equazioni ATTUALI del codice — quelle del vecchio documento sono diverse.'))
    A(('p', 'Gap desiderato: s* = s0 + max(0, v·T + v·Δv/(2·√(a·b))), con Δv = v − v_leader (Δv>0 = '
           'ci si avvicina). IIDM (con δ=4 fisso): definito v_free = a·(1 − (v/v0)⁴) e z = s*/s_safe '
           '(dove s_safe = clamp(gap, min 2.0 m) è il gap al denominatore, vedi nota sotto), '
           'la rete distingue regime di free-flow (z<1) da car-following (z≥1) e i casi v≤v0 / v>v0 '
           '(in free-flow l\'accelerazione è governata da v_free, in car-following dal termine di '
           'interazione a·(1−z²)) — '
           'questo elimina il difetto dell\'IDM base vicino a v=v0. CAH (Constant-Acceleration '
           'Heuristic): a_cah = min(a_l, a) − relu(Δv)²/(2·s_safe), che anticipa la frenata del leader '
           'e riduce le sovra-reazioni nei cut-in lievi. Blend: se a_iidm ≥ a_cah si usa a_iidm, '
           'altrimenti (1−c)·a_iidm + c·(a_cah + b·tanh((a_iidm−a_cah)/b)), con COOLNESS c=0.99 FISSO. '
           'Provvista anti-crash: accelerazione limitata a [−9, a].'))
    A(('callout', 'Due dettagli del codice, spesso ignorati. (1) La rete predice solo 5 dei 7 parametri: '
                  'coolness (0.99) e δ (4) sono FISSI, non predetti. (2) s_safe = clamp(gap, min=2.0), '
                  'NON 0.5: è una scelta di controllo del gradiente (con 0.5 il termine v/s_safe '
                  'arrivava a ~76 e la grad-norm a ~8000 in autostrada; con 2.0 scende a ~19 e ~200), '
                  'allineata tra il simulatore e il generatore dati.'))

    A(('h2', '14. Il generatore di dati sintetici'))
    A(('p', 'Non usiamo dati reali di auto (costosi/complessi): generiamo traiettorie sintetiche con lo '
           'stesso modello ACC-IIDM. Ogni traiettoria dura 120 s (di cui 20 s di warmup esclusi dalla '
           'loss) → ~1000 passi utili da 0.1 s; 5000 traiettorie di training, 500 di validazione, 500 '
           'di test. Per ogni passo si registrano [s, v, Δv, v_leader, v̇, T_vero, mask]; dopo '
           'normalizzazione l\'input è (N,4) e il target di fisica è (N,2) = [accelerazione, T_vero]. '
           'Ingredienti realistici: T(t) varia con SALTI di Markov (non un OU continuo — da qui il '
           'floor di L_OU); mix di scenari (highway 50%, urban 30%, truck 10%, mixed 10%, più freeflow '
           'e launch per rendere osservabili v0 e a); profili del leader (costante/sinusoidale/'
           'stop-and-go/free/launch); cut-in nel 20% dei casi (un secondo veicolo si infila, gap → 5–15 m); '
           'perdita pacchetti V2X ~2% (i frame persi escono da L_data ma restano in L_phys); rumore OU '
           'su gap/velocità/accelerazione. La variante "wide" campiona uniformemente i 5 parametri per '
           'ampliare la copertura.'))

    A(('h2', '15. Quantizzazione Power-of-Two (po2) e Straight-Through Estimator'))
    A(('p', 'Il cuore del co-design hardware. I pesi sinaptici sono vincolati a potenze di due: '
           'w_q = sign(w)·2^(round(log2|w|)) con l\'esponente in [−4, 1] e i pesi sotto 2⁻⁵ azzerati → '
           '13 livelli totali {±1/16 … ±2, 0}. Su FPGA moltiplicare per 2ᵏ è un semplice BIT-SHIFT '
           '(1 ciclo, ~10 LUT) invece di una moltiplicazione vera (4 cicli, ~100 LUT).'))
    A(('img', (F['po2'], 'Figura 15.1 — I 13 livelli po2 con la banda morta |w|<2⁻⁵ (sx) e il risparmio '
                         'su FPGA: la moltiplicazione diventa uno shift (dx).')))
    A(('p', 'Come si addestra una rete con pesi così discreti? Con lo Straight-Through Estimator (STE), '
           'lo stesso principio del surrogate gradient (§7): nel FORWARD si usano i pesi quantizzati, '
           'nel BACKWARD il gradiente attraversa la quantizzazione come se fosse l\'identità e aggiorna '
           'i pesi RAW in virgola mobile. La quantizzazione è quindi forward-only durante il training: '
           'per questo — misura controintuitiva — il po2 pesa solo ~0.2% sul plateau di errore, e '
           'l\'affermazione "quantizzare rovina tutto" qui non regge. Coerenza hardware: anche il leak '
           'di membrana è un bit-shift (V·7/8) e il reset è sottrattivo (nessun divisore).'))

    # ===== PARTE III =====
    A(('h1', 'Parte III — Bilancio, hardware, stato'))

    A(('h2', '16. Il deployment su FPGA/HDL: il problema aperto'))
    A(('p', 'Onestà sul target hardware: il modello è addestrato e validato in PyTorch (in '
           'simulazione), ma il deploy su FPGA è un OBIETTIVO DI DESIGN, non un risultato raggiunto. '
           'Gli strumenti standard di conversione (FINN di AMD/Xilinx) NON supportano il neurone ALIF '
           'con soglia adattiva, né la ricorrenza low-rank custom, né i delay assonali: servirebbe HDL '
           'scritto a mano, o un percorso via Simulink + HDL Coder (nodo aperto, documentato in '
           'FPGA_EVALUATE_DESIGN.md). Le scelte hardware-aware (po2→shift, leak→shift, surrogata→LUT, '
           'delay→ring-buffer, reset sottrattivo) sono NECESSARIE ma non SUFFICIENTI: riducono '
           'l\'attrito, non lo eliminano. Il vantaggio energetico è una STIMA da modello '
           '(Horowitz 45 nm), non una misura su silicio (i valori per champion sono in VALIDATION §9.2, '
           'il profilo op-count nel FPGA_REPORT); restano da validare l\'utilizzo dei DSP, la '
           'banda di memoria e la quantizzazione dello STATO (V, fatica) oltre che dei pesi.'))

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

    A(('h2', '18. Sintesi end-to-end e rimando ai risultati'))
    A(('p', 'Un episodio completo: l\'input V2X normalizzato entra come corrente; per 10 tick lo strato '
           'ALIF integra, emette spike e si retroalimenta via U·V; lo strato LI accumula i spike; '
           'il potenziale finale viene decodificato (sigmoid + bound) nei 5 parametri; questi, dati al '
           'controllore ACC-IIDM, guidano un\'auto in anello chiuso confrontata con l\'oracolo. La mappa '
           'teoria → codice: ALIF (§4) → ALIFCell; codifica (§5) → corrente diretta + LI + 10 tick; '
           'surrogate (§7) → SurrogateSpike_Hardware; EventProp (§8) → ALIFLayer_EventProp_Full; po2 '
           '(§15) → PowerOf2Quantize; PINN (§12) → pinn_loss.'))
    A(('p', 'Stato reale, onesto: il plateau di validazione (val_data/fisica) è ~0.19-0.20, allineato al '
           'riferimento di Treiber (~0.20), con record a 0.1926 (il vecchio plateau highway ~0.28 è stato '
           'superato; valori esatti per-champion in VALIDATION_REPORT_v3 §4.1). Due cause strutturali '
           'diagnosticate — l\'identificabilità sloppy di a/b e la qualità del gradiente SNN; l\'esito del '
           'confronto BPTT vs EventProp (fronte di Pareto) e il verdetto di sicurezza sono nel report '
           'gemello (VALIDATION §1, §5, §10). '
           'Distinguere sempre ciò che è VALIDATO IN PRODUZIONE (BPTT+surrogate, checkpoint della '
           'famiglia Loss_Study) da ciò che è STUDIATO/roadmap (EventProp, deploy HDL).'))
    A(('callout', 'Hai capito COME funziona la rete. Per i RISULTATI — i 4 champion, il verdetto di '
                  'deploy (Donatello), le 15 dimensioni di validazione, sicurezza/traffico/energia — '
                  'vedi il documento gemello VALIDATION_REPORT_v3.'))

    A(('h2', '19. Mappa dei file e riferimenti'))
    A(('table', (
        ['Cosa', 'Dove'],
        [
            ['Rete, decode, fisica ACC-IIDM', 'core/network.py'],
            ['Neurone ALIF (leak, soglia adattiva, reset)', 'core/neurons.py'],
            ['Surrogate gradient + po2 (STE)', 'core/hardware.py'],
            ['EventProp adjoint (1/denom, C8–C13)', 'core/eventprop.py'],
            ['Loss PINN a 5 componenti', 'train.py (pinn_loss)'],
            ['Generatore dati (jump-Markov, cut-in, V2X)', 'data/generator.py'],
            ['Risultati e verdetto (documento gemello)', 'document/VALIDATION_REPORT_v3.md / .pdf'],
            ['Stato studio EventProp, vincolo spettrale', 'document/EVENTPROP_STATUS.md'],
            ['Glossario codici (P/A/B/F) e termini', 'document/GLOSSARY.md'],
            ['Questo documento (generatore)', 'scripts/build_how_it_works_v3.py'],
        ],
    )))
    A(('p', 'Riferimenti esterni: Maass 1997 (terza generazione); Gerstner, Neuronal Dynamics (LIF/ALIF); '
           'Bellec et al. 2018 (LSNN, ALIF); Neftci et al. 2019 (surrogate gradient); Wunderlich & Pehle '
           '2021 (EventProp); Treiber & Kesting, Traffic Flow Dynamics 2ª ed. (ACC-IIDM, Cap. 12). '
           'Tutti i diagrammi di questo documento sono ricostruiti eseguendo '
           '"python scripts/build_how_it_works_v3.py" — nessun checkpoint richiesto.'))
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
