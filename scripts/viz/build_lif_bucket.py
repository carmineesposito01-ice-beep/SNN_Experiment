"""
C. lif_bucket.gif — the LIF neuron as a LITERAL leaky bucket.

A bucket (rectangle) whose blue fill height = membrane potential V.
A small leak hole near the bottom => level decays when input stops (the leak, tau).
Input "pours" in as pulses => level rises.
An amber threshold line: when the level reaches it, the bucket FLASHES,
drops by theta (subtractive reset), and emits a green spike marker.
Beside the bucket, the classic V(t) trace draws in lockstep.

Dynamics: V = beta*V + I   (beta = 7/8),  spike if V >= theta, then V <- V - theta.
"""

import matplotlib
matplotlib.use("Agg")

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import FancyBboxPatch, Rectangle, Polygon
from pathlib import Path

# ---------------- palette ----------------
BG      = "#15181D"
TEXT    = "#C7D0DA"
MUTED   = "#8A939D"
SPINE   = "#39424D"
BLUE    = "#56B4E9"   # membrane / water
GREEN   = "#2ECC71"   # spike
AMBER   = "#F0B429"   # threshold
FLASH   = "#EAF6FF"   # flash overlay

OUT = Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/assets/manim"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------- simulate the LIF ----------------
BETA   = 7.0 / 8.0
THETA  = 1.0
N      = 60                      # sim steps

rng = np.random.default_rng(7)
# input current: bursts of "pours" then silence so the leak is visible
I = np.zeros(N)
I[2:14]  = 0.16          # first pour -> climbs to threshold, spikes
I[14:22] = 0.0           # silence -> leak decays (shows the hole)
I[22:40] = 0.20          # bigger pour -> multiple spikes
I[40:46] = 0.0           # silence -> leak again
I[46:58] = 0.14          # gentle pour -> one more spike

V = np.zeros(N)
spikes = np.zeros(N, dtype=bool)
v = 0.0
for t in range(N):
    v = BETA * v + I[t]
    if v >= THETA:
        spikes[t] = True
        v = v - THETA        # subtractive reset
    V[t] = v

# For the bucket we want the PRE-reset level too, so the flash shows the overflow.
V_pre = np.zeros(N)
v = 0.0
for t in range(N):
    v = BETA * v + I[t]
    V_pre[t] = v
    if v >= THETA:
        v = v - THETA

VMAX = 1.28  # bucket capacity for drawing (a bit above theta)

# ---------------- figure ----------------
fig = plt.figure(figsize=(9.6, 5.4), dpi=100)
fig.patch.set_facecolor(BG)
gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.55],
                      left=0.05, right=0.965, top=0.90, bottom=0.13, wspace=0.28)

# ---- left: the bucket ----
axB = fig.add_subplot(gs[0, 0])
axB.set_facecolor(BG)
axB.set_xlim(0, 1)
axB.set_ylim(0, 1)
axB.axis("off")

# bucket geometry (in axes 0..1 coords)
BX0, BX1 = 0.24, 0.76      # left / right inner walls
BY0, BYTOP = 0.10, 0.86    # floor / rim
BW = BX1 - BX0
BH = BYTOP - BY0           # full height maps to VMAX

def v_to_y(vv):
    return BY0 + (np.clip(vv, 0, VMAX) / VMAX) * BH

# bucket walls (draw as thick lines: two sides + floor, open top)
wall_kw = dict(color=TEXT, lw=3.2, solid_capstyle="round", zorder=5)
axB.plot([BX0, BX0], [BY0, BYTOP], **wall_kw)
axB.plot([BX1, BX1], [BY0, BYTOP], **wall_kw)
axB.plot([BX0, BX1], [BY0, BY0], **wall_kw)

# leak hole near the bottom (small notch on the right wall) + drip
HOLE_Y = BY0 + 0.06
axB.plot([BX1 - 0.005, BX1 + 0.05], [HOLE_Y, HOLE_Y - 0.015],
         color=SPINE, lw=3.0, solid_capstyle="round", zorder=6)
axB.annotate("il buco = leak (τ)",
             xy=(BX1 + 0.05, HOLE_Y - 0.01), xytext=(BX1 + 0.055, HOLE_Y + 0.02),
             color=MUTED, fontsize=8.5, ha="left", va="center",
             arrowprops=dict(arrowstyle="-", color=SPINE, lw=1.0))

# water rectangle (updated each frame)
water = Rectangle((BX0, BY0), BW, 0.0, facecolor=BLUE, edgecolor="none",
                  alpha=0.92, zorder=3)
axB.add_patch(water)
# subtle surface highlight line on the water
surf_line, = axB.plot([BX0, BX1], [BY0, BY0], color="#BFE6FA", lw=1.4, zorder=4)

# threshold line across the bucket
THY = v_to_y(THETA)
axB.plot([BX0 - 0.03, BX1 + 0.03], [THY, THY], color=AMBER, lw=2.0, ls=(0, (5, 3)),
         zorder=7)
axB.text(BX0 - 0.045, THY, "θ", color=AMBER, fontsize=12, ha="right",
         va="center", fontweight="bold")

# flash overlay (full bucket flash on spike)
flash_patch = Rectangle((BX0, BY0), BW, BH, facecolor=FLASH, edgecolor="none",
                        alpha=0.0, zorder=8)
axB.add_patch(flash_patch)

# incoming "pour" pulses above the bucket
pour_lines = []
for k in range(4):
    xk = BX0 + BW * (0.30 + 0.13 * k)
    ln, = axB.plot([xk, xk], [BYTOP + 0.02, BYTOP + 0.02], color=BLUE, lw=2.6,
                   alpha=0.0, solid_capstyle="round", zorder=6)
    pour_lines.append(ln)

# spike marker (green burst) emitted at the rim on spike
spike_dot, = axB.plot([], [], marker="*", ms=0, color=GREEN, zorder=9,
                      markeredgecolor="#0B3A22", markeredgewidth=0.6)

# labels around bucket
axB.text((BX0 + BX1) / 2, BYTOP + 0.115, "input → versa (pour)",
         color=MUTED, fontsize=8.5, ha="center", va="bottom")
axB.text((BX0 + BX1) / 2, BY0 - 0.055,
         "livello acqua = V  ·  V = βV + I  (β = 7/8)",
         color=TEXT, fontsize=9.0, ha="center", va="top")

# ---- right: the V(t) trace ----
axT = fig.add_subplot(gs[0, 1])
axT.set_facecolor(BG)
for s in axT.spines.values():
    s.set_color(SPINE)
axT.spines["top"].set_visible(False)
axT.spines["right"].set_visible(False)
axT.tick_params(colors=MUTED, labelsize=8.5)
axT.set_xlim(0, N - 1)
axT.set_ylim(0, VMAX)
axT.set_xlabel("tempo  (tick)", color=TEXT, fontsize=9.5)
axT.set_ylabel("V(t)  membrana", color=TEXT, fontsize=9.5)
axT.axhline(THETA, color=AMBER, lw=1.6, ls=(0, (5, 3)))
axT.text(N - 1, THETA + 0.02, "  soglia θ", color=AMBER, fontsize=8.5,
         ha="right", va="bottom")

trace_line, = axT.plot([], [], color=BLUE, lw=2.2)
spike_marks, = axT.plot([], [], linestyle="none", marker="|", ms=16, mew=2.4,
                        color=GREEN)
head_dot, = axT.plot([], [], marker="o", ms=6, color=BLUE,
                     markeredgecolor=BG, markeredgewidth=1.0)

annot = axT.text(0.015, 0.965,
                 "overflow = spike  ·  caduta = reset (V ← V − θ)",
                 transform=axT.transAxes, color=MUTED, fontsize=8.8,
                 ha="left", va="top")

# ---------------- animation ----------------
def draw_frame(t):
    # bucket water level = pre-reset level (so it visibly touches theta on spike)
    lvl = V_pre[t]
    y = v_to_y(lvl)
    water.set_height(y - BY0)
    surf_line.set_data([BX0, BX1], [y, y])

    # water colour hint: warmer when near/over threshold
    if lvl >= THETA * 0.98:
        water.set_facecolor("#7CC8EE")
    else:
        water.set_facecolor(BLUE)

    # pour pulses visible while there is input
    pouring = I[t] > 0
    for k, ln in enumerate(pour_lines):
        if pouring:
            ln.set_alpha(0.55 + 0.15 * ((t + k) % 3 == 0))
            # animated dribble length
            drop = 0.02 + 0.04 * (((t + k) % 3) / 2.0)
            xk = ln.get_xdata()[0]
            ln.set_data([xk, xk], [BYTOP + 0.02, BYTOP + 0.02 + 0.10 - drop])
        else:
            ln.set_alpha(0.0)

    # spike flash + reset marker
    if spikes[t]:
        flash_patch.set_alpha(0.85)
        spike_dot.set_data([BX1 + 0.02], [BYTOP + 0.02])
        spike_dot.set_markersize(20)
    else:
        # decay the flash on following frames
        cur = flash_patch.get_alpha()
        flash_patch.set_alpha(max(0.0, cur * 0.35))
        spike_dot.set_markersize(0)

    # trace up to t (use the post-reset V for the honest sawtooth)
    xs = np.arange(t + 1)
    trace_line.set_data(xs, V[:t + 1])
    head_dot.set_data([t], [V[t]])
    sm = np.where(spikes[:t + 1])[0]
    spike_marks.set_data(sm, np.full_like(sm, THETA, dtype=float))

    return (water, surf_line, flash_patch, spike_dot, trace_line,
            head_dot, spike_marks, *pour_lines)

# POSTER-FIRST: frame 0 must be a complete/representative pose.
# Pick a frame right AFTER a spike so the bucket is flashing + trace shows a spike.
spike_ids = np.where(spikes)[0]
POSTER = int(spike_ids[0])          # first spike frame: bucket flashing, mark on trace

frames = [POSTER] * 8 + list(range(N)) + [N - 1] * 16

anim = FuncAnimation(fig, draw_frame, frames=frames, interval=1000 / 16, blit=False)
anim.save(OUT / "lif_bucket.gif", writer=PillowWriter(fps=16),
          savefig_kwargs={"facecolor": BG})
plt.close(fig)
print("wrote", OUT / "lif_bucket.gif")
