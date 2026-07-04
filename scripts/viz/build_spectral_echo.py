"""
D. spectral_echo.gif — the recurrent "echo": dies (rho<1) vs explodes (rho>1).

Inject ONE kick into a recurrent state x[t] = (U.V) x[t-1].
Track its amplitude tick-by-tick in TWO synced panels:
  rho<1 (green): ripple/envelope FADES to silence.
  rho>1 (red):   ripple GROWS until it hits a saturation ceiling and CLIPS
                 (fixed-point overflow, made visual).
Spectral radius rho = sigma_max(U.V).  ||x[t]|| ~ rho^t ||x0||.

END-HOLD frame: a small rho-axis scatter of the 4 champions in identity colours:
  Donatello 0.05 & Michelangelo 0.39 (green side), Leonardo 1.16 & Raffaello 2.99 (red side).
"""

import matplotlib
matplotlib.use("Agg")

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Rectangle
from pathlib import Path

# ---------------- palette ----------------
BG      = "#15181D"
TEXT    = "#C7D0DA"
MUTED   = "#8A939D"
SPINE   = "#39424D"
GREEN   = "#2ECC71"   # stable / decays
DANGER  = "#E0563B"   # explodes / clips
AMBER   = "#F0B429"

# champion identity colours
C_RAFF  = "#E06A2C"
C_LEO   = "#4AA3E0"
C_DON   = "#D48AC0"
C_MIC   = "#F0AE3A"

OUT = Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/assets/manim"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------- signals ----------------
N       = 64
RHO_LO  = 0.90
RHO_HI  = 1.075
CEIL    = 1.0          # saturation / fixed-point overflow ceiling (normalized)

t = np.arange(N)
# a damped/growing oscillation: kick at t=0, ringing carrier * rho^t envelope
carrier = np.sin(2 * np.pi * t / 7.5)

env_lo = RHO_LO ** t
env_hi = RHO_HI ** t

x_lo = env_lo * carrier
# explode side: grow then CLIP at the ceiling (overflow)
x_hi_raw = env_hi * carrier
x_hi = np.clip(x_hi_raw, -CEIL, CEIL)
clipped = np.abs(x_hi_raw) >= CEIL     # where fixed-point overflow occurs

YL = 1.18

# ---------------- figure ----------------
fig = plt.figure(figsize=(9.6, 5.4), dpi=100)
fig.patch.set_facecolor(BG)
gs = fig.add_gridspec(2, 1, left=0.085, right=0.965, top=0.92, bottom=0.11,
                      hspace=0.34)

def style_ax(ax, color, label):
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_color(SPINE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8.2)
    ax.set_xlim(0, N - 1)
    ax.set_ylim(-YL, YL)
    ax.axhline(0, color=SPINE, lw=0.9)
    ax.set_ylabel("‖x[t]‖", color=TEXT, fontsize=9.5)
    ax.text(0.012, 0.90, label, transform=ax.transAxes, color=color,
            fontsize=11.5, fontweight="bold", ha="left", va="top")

axL = fig.add_subplot(gs[0, 0])   # stable
axH = fig.add_subplot(gs[1, 0])   # explode
style_ax(axL, GREEN, "ρ < 1   →   l'eco si spegne")
style_ax(axH, DANGER, "ρ > 1   →   l'eco esplode e satura (overflow)")
axH.set_xlabel("tempo  (tick)", color=TEXT, fontsize=9.5)

# saturation ceiling lines on explode panel
axH.axhline(CEIL, color=DANGER, lw=1.3, ls=(0, (4, 3)), alpha=0.8)
axH.axhline(-CEIL, color=DANGER, lw=1.3, ls=(0, (4, 3)), alpha=0.8)
axH.text(N - 1, CEIL + 0.02, "  tetto fixed-point (clip)", color=DANGER,
         fontsize=8.0, ha="right", va="bottom")

# stems + envelope for each panel
stemL = axL.vlines([], [], [], color=GREEN, lw=2.0, alpha=0.75)
stemH = axH.vlines([], [], [], color=DANGER, lw=2.0, alpha=0.75)
envL_top, = axL.plot([], [], color=GREEN, lw=1.4, alpha=0.55)
envL_bot, = axL.plot([], [], color=GREEN, lw=1.4, alpha=0.55)
envH_top, = axH.plot([], [], color=DANGER, lw=1.4, alpha=0.55)
envH_bot, = axH.plot([], [], color=DANGER, lw=1.4, alpha=0.55)
headL, = axL.plot([], [], marker="o", ms=6, color=GREEN,
                  markeredgecolor=BG, markeredgewidth=1.0)
headH, = axH.plot([], [], marker="o", ms=6, color=DANGER,
                  markeredgecolor=BG, markeredgewidth=1.0)
# clip flash markers on explode panel
clipmk, = axH.plot([], [], linestyle="none", marker="_", ms=9, mew=1.8,
                   color=AMBER, alpha=0.85)

# "kick" annotation (placed low so it never collides with the heading)
axL.annotate("kick", xy=(0.4, x_lo[0]), xytext=(4.5, -0.62),
             color=MUTED, fontsize=8.5, ha="left", va="center",
             arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.0))
axH.annotate("kick", xy=(0.4, x_hi[0]), xytext=(4.5, -0.55),
             color=MUTED, fontsize=8.5, ha="left", va="center",
             arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.0))

# equation caption (top-right of upper panel)
axL.text(0.985, 0.90, "x[t] = (U·V) x[t−1]   ·   ρ = σmax(U·V)",
         transform=axL.transAxes, color=MUTED, fontsize=8.6,
         ha="right", va="top")

# ---------- champion scatter (revealed on end-hold) ----------
# placed as an opaque inset floating over the explode panel, hidden until the hold.
axS = fig.add_axes([0.545, 0.135, 0.415, 0.185], zorder=20)
axS.set_facecolor("#1B1F26")
axS.patch.set_alpha(1.0)
for s in axS.spines.values():
    s.set_color("#4A5560")
    s.set_linewidth(1.2)
axS.set_xlim(-0.15, 3.45)
axS.set_ylim(-0.75, 0.75)
axS.set_yticks([])
axS.set_xticks([0, 1, 2, 3])
axS.tick_params(colors=MUTED, labelsize=7.5)
axS.axvline(1.0, color=AMBER, lw=1.4, ls=(0, (4, 3)))
champs = [
    ("Donatello",     0.05, C_DON, GREEN),
    ("Michelangelo",  0.39, C_MIC, GREEN),
    ("Leonardo",      1.16, C_LEO, DANGER),
    ("Raffaello",     2.99, C_RAFF, DANGER),
]
scat_artists = []
for name, rho, col, side in champs:
    d = axS.plot(rho, 0.0, marker="o", ms=9, color=col,
                 markeredgecolor=BG, markeredgewidth=1.0, zorder=5)[0]
    yoff = 0.40 if name in ("Donatello", "Leonardo") else -0.44
    xtxt = rho - 0.28 if name == "Raffaello" else rho
    tx = axS.annotate(f"{name}\nρ={rho:.2f}", xy=(rho, 0.0),
                      xytext=(xtxt, yoff), color=col, fontsize=6.6,
                      ha="center", va="center",
                      arrowprops=dict(arrowstyle="-", color=col, lw=0.7, alpha=0.6))
    scat_artists += [d, tx]
axS_title = axS.text(0.015, 1.10, "ρ dei 4 champion   ·   ρ=1 = confine stabilità",
                     transform=axS.transAxes, color=TEXT, fontsize=7.8,
                     ha="left", va="bottom")
axS.text(1.0, 0.70, "1.0", transform=axS.transData, color=AMBER, fontsize=7.0,
         ha="center", va="bottom")

def set_scatter_visible(vis):
    axS.set_visible(vis)

# ---------------- animation ----------------
def draw_panel(t_idx):
    xs = np.arange(t_idx + 1)

    # stems
    global stemL, stemH
    stemL.remove()
    stemH.remove()
    stemL = axL.vlines(xs, 0, x_lo[:t_idx + 1], color=GREEN, lw=2.0, alpha=0.75)
    stemH.remove_flag = True
    stemH = axH.vlines(xs, 0, x_hi[:t_idx + 1], color=DANGER, lw=2.0, alpha=0.75)

    # envelopes
    envL_top.set_data(t, env_lo)
    envL_bot.set_data(t, -env_lo)
    envH_top.set_data(t, np.clip(env_hi, 0, CEIL))
    envH_bot.set_data(t, -np.clip(env_hi, 0, CEIL))

    headL.set_data([t_idx], [x_lo[t_idx]])
    headH.set_data([t_idx], [x_hi[t_idx]])

    cm = np.where(clipped[:t_idx + 1])[0]
    if cm.size:
        clipmk.set_data(cm, np.sign(x_hi_raw[cm]) * CEIL)
    else:
        clipmk.set_data([], [])

    return (stemL, stemH, envL_top, envL_bot, envH_top, envH_bot,
            headL, headH, clipmk)

def update(f):
    # f encodes phase: negative sentinel => end-hold with scatter
    if f == "HOLD":
        draw_panel(N - 1)
        set_scatter_visible(True)
        return []
    set_scatter_visible(False)
    draw_panel(f)
    return []

# POSTER-FIRST: a frame where BOTH envelopes are partly evolved (mid-run),
# stable already decaying, explode already growing but not yet fully clipped.
POSTER = 26

frames = ([POSTER] * 8 +
          list(range(N)) +
          ["HOLD"] * 20)          # end-hold reveals the champion scatter

anim = FuncAnimation(fig, update, frames=frames, interval=1000 / 16, blit=False)
anim.save(OUT / "spectral_echo.gif", writer=PillowWriter(fps=16),
          savefig_kwargs={"facecolor": BG})
plt.close(fig)
print("wrote", OUT / "spectral_echo.gif")
