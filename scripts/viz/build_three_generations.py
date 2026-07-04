"""
three_generations.gif — instant contrast of the 3 neural-network generations.

Three side-by-side neuron "cards" on one dark canvas, driven by ONE shared moving
input needle sweeping left->right:
  - Perceptron: input crosses a threshold -> output snaps 0->1 (hard step). "binario".
  - ANN: same input -> a lamp/dot whose brightness varies CONTINUOUSLY 0..1 (amber). "graduato".
  - SNN: same input charges a membrane bar; when it fills, emit a discrete spike tick
         on a mini time-raster (teal), then reset. "eventi nel tempo".

Poster (frame 0) = a mid-sweep frame showing all three output states.
Dark palette per thesis spec. matplotlib -> GIF via Pillow. No manim/ffmpeg.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, Rectangle
from matplotlib.animation import FuncAnimation, PillowWriter
from pathlib import Path

# ----- palette -----
BG      = "#15181D"
TEXT    = "#C7D0DA"
MUTED   = "#8A939D"
SPINES  = "#39424D"
BLUE    = "#56B4E9"   # membrane
GREEN   = "#2ECC71"   # spike / safe
AMBER   = "#F0B429"   # threshold
ANN_AMB = "#E8A13C"   # ANN continuous
SNN_TL  = "#1FB6B6"   # SNN spike teal
DANGER  = "#E0563B"

OUT = Path("D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/presentation/cf_fsnn_thesis/assets/manim")
OUT.mkdir(parents=True, exist_ok=True)

# ----- shared input signal (needle position -> input value) -----
N = 64                       # number of build frames (one sweep)
sweep = np.linspace(0.0, 1.0, N)          # needle x position 0..1
# input value driven by the needle: a smooth rise with a bump, in [0,1]
def input_value(t):
    return 0.5 + 0.42 * np.sin(2 * np.pi * (t - 0.15)) * (0.4 + 0.6 * t)

THETA = 0.62                 # shared threshold on input value (perceptron & display)

# ----- SNN membrane integration precomputed over the sweep -----
# V[k+1] = beta*V + I - S*theta ; S = H(V - theta)
beta   = 0.88
V_th   = 1.0
I_gain = 0.34
Vtrace = np.zeros(N)
Strace = np.zeros(N, dtype=bool)
_V = 0.0
for k in range(N):
    I = I_gain * max(input_value(sweep[k]), 0.0) * 2.2
    _V = beta * _V + I
    if _V >= V_th:
        Strace[k] = True
        _V = _V - V_th          # reset by subtraction
    Vtrace[k] = min(_V, V_th)

# ----- figure layout -----
fig = plt.figure(figsize=(10.6, 4.6), dpi=100)
fig.patch.set_facecolor(BG)

# top strip: shared input needle track
ax_in = fig.add_axes([0.06, 0.80, 0.88, 0.14])
# three cards
ax_p  = fig.add_axes([0.055, 0.10, 0.27, 0.60])   # perceptron
ax_a  = fig.add_axes([0.375, 0.10, 0.27, 0.60])   # ANN
ax_s  = fig.add_axes([0.695, 0.10, 0.27, 0.60])   # SNN

for ax in (ax_in, ax_p, ax_a, ax_s):
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_color(SPINES)
    ax.tick_params(colors=MUTED, labelsize=7)

# --- shared input track ---
ax_in.set_xlim(0, 1); ax_in.set_ylim(0, 1)
ax_in.set_yticks([])
ax_in.set_xticks([])
xs = np.linspace(0, 1, 200)
ax_in.plot(xs, 0.25 + 0.5 * (input_value(xs)), color=MUTED, lw=1.4, alpha=0.55)
ax_in.axhline(0.25 + 0.5 * THETA, color=AMBER, lw=1.0, ls="--", alpha=0.7)
ax_in.text(0.005, 0.25 + 0.5 * THETA + 0.06, "soglia", color=AMBER, fontsize=7, va="bottom")
ax_in.text(0.005, 0.92, "INGRESSO CONDIVISO  w·x", color=TEXT, fontsize=8.5,
           va="top", ha="left", fontweight="bold")
needle_line = ax_in.axvline(sweep[0], color=TEXT, lw=1.8, alpha=0.9)
needle_dot, = ax_in.plot([sweep[0]], [0.25 + 0.5 * input_value(sweep[0])],
                         "o", color=GREEN, ms=8, zorder=5)

# --- card helpers: a rounded panel behind each axis ---
def card_title(ax, title, subtitle, color):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xticks([]); ax.set_yticks([])
    ax.text(0.5, 1.13, title, transform=ax.transAxes, ha="center", va="bottom",
            color=color, fontsize=12, fontweight="bold")
    ax.text(0.5, 1.02, subtitle, transform=ax.transAxes, ha="center", va="bottom",
            color=MUTED, fontsize=8, style="italic")

# ===== PERCEPTRON card: hard step output =====
card_title(ax_p, "PERCETTRONE", "binario  •  y = H(w·x − θ)", BLUE)
# a big lamp (circle) that is OFF (dark) or ON (green), plus a 0/1 readout
p_lamp = Circle((0.5, 0.58), 0.20, facecolor="#20252C", edgecolor=SPINES, lw=1.6, zorder=3)
ax_p.add_patch(p_lamp)
p_val = ax_p.text(0.5, 0.58, "0", ha="center", va="center", color=MUTED,
                  fontsize=26, fontweight="bold", zorder=4)
ax_p.text(0.5, 0.16, "scatto netto 0 → 1", ha="center", color=MUTED, fontsize=8)

# ===== ANN card: continuous brightness lamp =====
card_title(ax_a, "ANN", "graduato, sempre acceso  •  y = σ(w·x+b)", ANN_AMB)
a_lamp = Circle((0.5, 0.58), 0.20, facecolor=ANN_AMB, edgecolor=SPINES, lw=1.6,
                alpha=0.15, zorder=3)
ax_a.add_patch(a_lamp)
a_val = ax_a.text(0.5, 0.16, "y = 0.00", ha="center", va="center", color=MUTED,
                  fontsize=10, fontweight="bold")
# a small vertical bar showing the analog level
a_bar_bg = Rectangle((0.80, 0.30), 0.07, 0.56, facecolor="#20252C",
                     edgecolor=SPINES, lw=1.0, zorder=2)
ax_a.add_patch(a_bar_bg)
a_bar = Rectangle((0.80, 0.30), 0.07, 0.01, facecolor=ANN_AMB, edgecolor="none", zorder=3)
ax_a.add_patch(a_bar)

# ===== SNN card: membrane bar + spike raster =====
card_title(ax_s, "SNN", "eventi nel tempo  •  S=H(V−θ), V=βV+I−Sθ", SNN_TL)
# membrane fill bar (bottom-left), fills then resets
s_bar_bg = Rectangle((0.12, 0.30), 0.16, 0.50, facecolor="#20252C",
                     edgecolor=SPINES, lw=1.2, zorder=2)
ax_s.add_patch(s_bar_bg)
s_bar = Rectangle((0.12, 0.30), 0.16, 0.01, facecolor=BLUE, edgecolor="none", zorder=3)
ax_s.add_patch(s_bar)
ax_s.axhline(0.80, xmin=0.12, xmax=0.28, color=AMBER, lw=1.0)  # visual only
ax_s.text(0.20, 0.84, "V", ha="center", color=BLUE, fontsize=9, fontweight="bold")
ax_s.text(0.20, 0.235, "θ→reset", ha="center", color=MUTED, fontsize=6.5)
# mini time raster on the right: tick marks accumulate over time
ax_s.text(0.66, 0.84, "raster spikes", ha="center", color=MUTED, fontsize=7.5)
ax_s.plot([0.42, 0.42], [0.32, 0.78], color=SPINES, lw=1.0)   # raster baseline (time axis)
ax_s.plot([0.42, 0.92], [0.32, 0.32], color=SPINES, lw=1.0)
ax_s.text(0.67, 0.265, "tempo →", ha="center", color=MUTED, fontsize=6.5)
raster_ticks = []   # Line2D objects added as spikes occur
# spike flash sits just RIGHT of the V bar (bar spans x 0.12..0.28) so it never clutters it
s_flash = Circle((0.345, 0.55), 0.0, facecolor=SNN_TL, edgecolor="none", alpha=0.0, zorder=5)
ax_s.add_patch(s_flash)
s_flash_lbl = ax_s.text(0.345, 0.55, "", ha="center", va="center",
                        color=BG, fontsize=8, fontweight="bold", zorder=6)

# raster x mapping: frame k -> x in [0.44, 0.90]
def raster_x(k):
    return 0.44 + 0.46 * (k / max(N - 1, 1))

def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))

def draw(k):
    """Render state at build-frame index k (0..N-1)."""
    t = sweep[k]
    x = input_value(t)

    # shared needle
    needle_line.set_xdata([t, t])
    needle_dot.set_data([t], [0.25 + 0.5 * x])

    # perceptron: hard step on input vs threshold
    on = x >= THETA
    if on:
        p_lamp.set_facecolor(GREEN); p_lamp.set_edgecolor(GREEN)
        p_val.set_text("1"); p_val.set_color(BG)
    else:
        p_lamp.set_facecolor("#20252C"); p_lamp.set_edgecolor(SPINES)
        p_val.set_text("0"); p_val.set_color(MUTED)

    # ANN: continuous brightness
    y = sigmoid(6.0 * (x - THETA))     # smooth 0..1
    a_lamp.set_alpha(0.12 + 0.85 * y)
    a_val.set_text(f"y = {y:0.2f}")
    a_val.set_color(ANN_AMB if y > 0.15 else MUTED)
    a_bar.set_height(0.56 * y + 0.005)

    # SNN: membrane fill (0..V_th -> 0..0.50 height), reset shown by drop
    v = Vtrace[k] / V_th
    s_bar.set_height(0.50 * v + 0.005)
    s_bar.set_facecolor(BLUE)

    # spike flash + raster accumulation
    # clear dynamic flash each frame
    s_flash.set_alpha(0.0); s_flash.set_radius(0.0); s_flash_lbl.set_text("")
    if Strace[k]:
        s_flash.set_radius(0.085); s_flash.set_alpha(0.95)
        s_flash_lbl.set_text("S=1")
    # rebuild raster ticks up to k (cheap: N small)
    for ln in raster_ticks:
        ln.remove()
    raster_ticks.clear()
    for j in range(k + 1):
        if Strace[j]:
            xj = raster_x(j)
            ln, = ax_s.plot([xj, xj], [0.34, 0.74], color=SNN_TL, lw=2.0, alpha=0.95)
            raster_ticks.append(ln)

    return (needle_line, needle_dot, p_lamp, p_val, a_lamp, a_val, a_bar,
            s_bar, s_flash)

# ----- frame schedule: POSTER-FIRST -----
POSTER = 30  # a mid-sweep frame showing all three outputs meaningfully engaged
frames = [POSTER] * 8 + list(range(N)) + [N - 1] * 16

def update(fi):
    return draw(fi)

anim = FuncAnimation(fig, update, frames=frames, interval=62, blit=False)
out_path = OUT / "three_generations.gif"
anim.save(out_path, writer=PillowWriter(fps=16),
          savefig_kwargs={"facecolor": BG})
plt.close(fig)
print("WROTE", out_path)
