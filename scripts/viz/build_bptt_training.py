"""bptt_training.gif — what actually happens in the BPTT REVERSE pass (the crux).

The unrolling is assumed understood; this animation answers "what is different in the
reverse vs a normal backprop?":
  FORWARD  (green, L->R): the recurrent state integrates tick by tick.
  BACKWARD (amber, R->L): the gradient flows back through EVERY tick, carried one step
    at a time by the recurrence (U*V)^T, and at each spike the dead Heaviside derivative
    (dS/dV = 0) is bridged by the surrogate sigma'(V-theta). The per-tick contributions
    are SUMMED into dL/dW -> memory grows with T.
Deterministic (fixed layout, fixed timing; no RNG). matplotlib -> GIF via Pillow.
"""
import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.animation import FuncAnimation, PillowWriter

OUT = pathlib.Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/assets/manim"
OUT.mkdir(parents=True, exist_ok=True)

BG="#15181D"; TEXT="#DCE3EA"; MUTED="#8A939D"; EDGE="#39424D"; DIM="#20252C"
GREEN="#2ECC71"; AMBER="#F0B429"; BLUE="#56B4E9"; DANGER="#E0563B"

N = 5
xs = np.linspace(0.11, 0.89, N)
yb = 0.52
CW, CH = 0.10, 0.20

fig, ax = plt.subplots(figsize=(7.6, 4.3), dpi=150)
fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

ax.text(0.5, 0.955, "BPTT: il gradiente torna indietro attraverso OGNI tick",
        ha="center", va="center", color=TEXT, fontsize=14.5, fontweight="bold")

# tick cells
cells = []
for i, x in enumerate(xs):
    p = FancyBboxPatch((x-CW/2, yb-CH/2), CW, CH, boxstyle="round,pad=0.006,rounding_size=0.02",
                       lw=2, edgecolor=EDGE, facecolor=DIM)
    ax.add_patch(p); cells.append(p)
    ax.text(x, yb-CH/2-0.05, f"t{i+1}", ha="center", va="center", color=MUTED, fontsize=11)

# forward (feed-forward) arrows below the recurrence
fwd_arrows = []
for i in range(N-1):
    ar = FancyArrowPatch((xs[i]+CW/2, yb-0.03), (xs[i+1]-CW/2, yb-0.03),
                         arrowstyle="-|>", mutation_scale=13, lw=1.6, color=EDGE)
    ax.add_patch(ar); fwd_arrows.append(ar)

# recurrence arcs (U*V) between consecutive ticks, above the cells
rec_arcs = []
for i in range(N-1):
    ar = FancyArrowPatch((xs[i], yb+CH/2), (xs[i+1], yb+CH/2),
                         arrowstyle="-|>", mutation_scale=12, lw=1.6, color=EDGE,
                         connectionstyle="arc3,rad=-0.55")
    ax.add_patch(ar); rec_arcs.append(ar)
ax.text(0.5, yb+CH/2+0.13, r"ricorrenza  $U\!\cdot\!V$", ha="center", va="center",
        color=MUTED, fontsize=10.5, style="italic")

# surrogate badges (appear on backward pass at each spike)
badges = []
for x in xs:
    t = ax.text(x, yb, r"$\sigma'$", ha="center", va="center", color=BG, fontsize=12,
                fontweight="bold", zorder=6, alpha=0.0,
                bbox=dict(boxstyle="circle,pad=0.18", fc=AMBER, ec="none"))
    badges.append(t)

pulse, = ax.plot([], [], "o", ms=17, color="#FFFFFF", zorder=8)
phase_txt = ax.text(0.5, 0.30, "", ha="center", va="center", color=TEXT, fontsize=12.5, fontweight="bold")
accum_txt = ax.text(0.5, 0.205, "", ha="center", va="center", color=AMBER, fontsize=12, family="monospace")
# static contrast caption
ax.text(0.5, 0.075,
        "vs backprop normale: qui il gradiente SOMMA su tutti i tick e passa per $(U\\!\\cdot\\!V)^{\\!\\top}$;",
        ha="center", va="center", color=MUTED, fontsize=10.2)
ax.text(0.5, 0.028, r"lo spike ($\partial S/\partial V = 0$) è attraversato dal surrogato $\sigma'$",
        ha="center", va="center", color=MUTED, fontsize=10.2)

FWD, BWD = 30, 40
def update(f):
    if f < FWD:                              # forward wave L->R
        frac = f/(FWD-1)
        px = xs[0] + (xs[-1]-xs[0])*frac     # continuous pulse position
        k = frac*N
        for i,p in enumerate(cells):
            on = i < k
            p.set_facecolor(GREEN if on else DIM); p.set_edgecolor(GREEN if on else EDGE)
        for b in badges: b.set_alpha(0.0)
        for a in rec_arcs: a.set_color(EDGE); a.set_linewidth(1.6)
        pulse.set_data([px],[yb]); pulse.set_color(GREEN)
        phase_txt.set_text("forward: lo stato integra  →"); phase_txt.set_color(GREEN)
        accum_txt.set_text("")
    else:                                    # backward wave R->L
        frac = (f-FWD)/(BWD-1)
        px = xs[-1] - (xs[-1]-xs[0])*frac
        k = frac*N; reached = int(k)
        for i,p in enumerate(cells):
            on = i >= N-1-k
            p.set_facecolor(AMBER if on else DIM); p.set_edgecolor(AMBER if on else EDGE)
        for i,b in enumerate(badges):
            b.set_alpha(1.0 if i >= N-1-k else 0.0)
        for i,a in enumerate(rec_arcs):
            hot = i >= N-1-k
            a.set_color(AMBER if hot else EDGE); a.set_linewidth(2.4 if hot else 1.6)
        pulse.set_data([px],[yb]); pulse.set_color(AMBER)
        phase_txt.set_text("←  gradiente indietro nel tempo"); phase_txt.set_color(AMBER)
        nterms = min(N, reached+1)
        accum_txt.set_text(r"$\partial L/\partial W = \sum$ " + "  +".join(["t%d"%(N-j) for j in range(nterms)]))
    return cells+badges+rec_arcs+[pulse, phase_txt, accum_txt]

seq = [0]*4 + list(range(FWD+BWD)) + [FWD+BWD-1]*8
anim = FuncAnimation(fig, update, frames=seq, interval=80)
anim.save(str(OUT/"bptt_training.gif"), writer=PillowWriter(fps=11))
plt.close(fig); print("wrote", OUT/"bptt_training.gif")
