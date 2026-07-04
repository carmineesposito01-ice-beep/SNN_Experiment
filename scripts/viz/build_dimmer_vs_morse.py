"""
dimmer_vs_morse.gif — "dimmer vs Morse" + energy meter.

Two horizontal wires over a shared time axis:
  TOP    = dimmer: a continuously glowing amber line tracking a smooth signal (always on).
  BOTTOM = the SAME signal encoded as discrete teal spikes, with a running spike-count
           "energy meter" that increments ONLY on spikes.
A playhead sweeps left->right.

Message (on-plot): "energia ∝ eventi (spike), non ∝ tempo".  Note E_AC < E_MAC.
Poster (frame 0) = a frame mid-sweep with the meter partway.

Dark palette per thesis spec. matplotlib -> GIF via Pillow. No manim/ffmpeg.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.collections import LineCollection
from matplotlib.animation import FuncAnimation, PillowWriter
from pathlib import Path

# ----- palette -----
BG      = "#15181D"
TEXT    = "#C7D0DA"
MUTED   = "#8A939D"
SPINES  = "#39424D"
GREEN   = "#2ECC71"
AMBER   = "#F0B429"
ANN_AMB = "#E8A13C"   # dimmer continuous amber
SNN_TL  = "#1FB6B6"   # spike teal
DANGER  = "#E0563B"

OUT = Path("D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/presentation/cf_fsnn_thesis/assets/manim")
OUT.mkdir(parents=True, exist_ok=True)

# ----- shared signal over time -----
N = 80
T = np.linspace(0.0, 1.0, N)
# a smooth analog signal in [0,1]: two humps
def signal(t):
    s = 0.55 + 0.40 * np.sin(2 * np.pi * (1.3 * t - 0.1)) * np.exp(-((t - 0.35) ** 2) / 0.14)
    s = s + 0.22 * np.sin(2 * np.pi * (2.1 * t)) * 0.5
    return np.clip(s, 0.02, 0.98)

S = signal(T)

# ----- spike encoding (bottom): threshold-crossing / rate-style events -----
# integrate signal; emit a spike each time accumulator passes a quantum -> rate ∝ amplitude
quantum = 0.9
acc = 0.0
spike_idx = []
for k in range(N):
    acc += S[k] * 1.15
    if acc >= quantum:
        spike_idx.append(k)
        acc -= quantum
spike_idx = np.array(spike_idx, dtype=int)
spike_t   = T[spike_idx]
N_SPIKES  = len(spike_idx)

# ----- figure -----
fig = plt.figure(figsize=(10.6, 4.9), dpi=100)
fig.patch.set_facecolor(BG)

ax_top = fig.add_axes([0.075, 0.545, 0.66, 0.300])   # dimmer wire
ax_bot = fig.add_axes([0.075, 0.135, 0.66, 0.300])   # spike wire
ax_meter = fig.add_axes([0.80, 0.135, 0.165, 0.710]) # energy meter panel

for ax in (ax_top, ax_bot, ax_meter):
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_color(SPINES)
    ax.tick_params(colors=MUTED, labelsize=7)

# --- TOP: dimmer (continuous amber glow) ---
ax_top.set_xlim(0, 1); ax_top.set_ylim(0, 1)
ax_top.set_yticks([]); ax_top.set_xticks([])
ax_top.text(0.005, 1.14, "DIMMER (analogico) — sempre acceso", transform=ax_top.transAxes,
            color=ANN_AMB, fontsize=10.5, fontweight="bold", va="bottom")
# faint full trace for reference
ax_top.plot(T, S, color=MUTED, lw=1.0, alpha=0.30)
# the glowing part (revealed by playhead) — set each frame
top_glow_layers = []
for lw, al in [(9, 0.10), (6, 0.16), (3.2, 0.55), (1.6, 1.0)]:
    ln, = ax_top.plot([], [], color=ANN_AMB, lw=lw, alpha=al, solid_capstyle="round")
    top_glow_layers.append(ln)
top_head, = ax_top.plot([], [], "o", color=ANN_AMB, ms=8, zorder=6)
ax_top.text(0.005, 0.06, "energia ∝ tempo acceso  (E_MAC)", transform=ax_top.transAxes,
            color=MUTED, fontsize=7.5, va="bottom")

# --- BOTTOM: spikes (discrete teal events) ---
ax_bot.set_xlim(0, 1); ax_bot.set_ylim(0, 1)
ax_bot.set_yticks([]); ax_bot.set_xticks([])
ax_bot.text(0.005, 1.14, "SPIKE (Morse) — eventi discreti", transform=ax_bot.transAxes,
            color=SNN_TL, fontsize=10.5, fontweight="bold", va="bottom")
ax_bot.axhline(0.18, color=SPINES, lw=1.0)   # wire baseline
# all spike stems drawn but revealed progressively via alpha
spike_stems = []
for st in spike_t:
    ln, = ax_bot.plot([st, st], [0.18, 0.86], color=SNN_TL, lw=2.6,
                      alpha=0.0, solid_capstyle="round")
    dot, = ax_bot.plot([st], [0.86], "o", color=SNN_TL, ms=5, alpha=0.0)
    spike_stems.append((ln, dot, st))
bot_head, = ax_bot.plot([], [], "o", color=SNN_TL, ms=8, zorder=6)
ax_bot.text(0.005, 0.03, "energia ∝ numero di eventi  (E_AC ≪ E_MAC)", transform=ax_bot.transAxes,
            color=GREEN, fontsize=7.5, va="bottom")
ax_bot.set_xlabel("tempo →", color=TEXT, fontsize=9)

# --- METER: energy = spike count ---
ax_meter.set_xlim(0, 1); ax_meter.set_ylim(0, 1)
ax_meter.set_xticks([]); ax_meter.set_yticks([])
ax_meter.text(0.5, 1.05, "ENERGIA", transform=ax_meter.transAxes, ha="center",
              color=TEXT, fontsize=10.5, fontweight="bold", va="bottom")
ax_meter.text(0.5, 0.985, "= n. di spike", transform=ax_meter.transAxes, ha="center",
              color=MUTED, fontsize=8, style="italic", va="bottom")
meter_bg = Rectangle((0.30, 0.10), 0.40, 0.72, facecolor="#20252C",
                     edgecolor=SPINES, lw=1.4)
ax_meter.add_patch(meter_bg)
meter_fill = Rectangle((0.30, 0.10), 0.40, 0.001, facecolor=SNN_TL, edgecolor="none")
ax_meter.add_patch(meter_fill)
meter_count = ax_meter.text(0.5, 0.045, "0", ha="center", va="center",
                            color=SNN_TL, fontsize=18, fontweight="bold")
# tick marks on meter for the dimmer's (much larger) continuous cost, as a ghost line
ax_meter.plot([0.30, 0.70], [0.82, 0.82], color=ANN_AMB, lw=1.4, ls="--", alpha=0.8)
ax_meter.text(0.72, 0.82, "MAC\n(analog.)", color=ANN_AMB, fontsize=6.8, va="center", ha="left")

# global on-plot message (top band, clear of the axis titles below)
fig.text(0.075, 0.985, "energia ∝ eventi (spike), non ∝ tempo",
         color=GREEN, fontsize=11.5, fontweight="bold", va="top")

METER_TOP = 0.82
def meter_height_for(count):
    frac = count / max(N_SPIKES, 1)
    return (METER_TOP - 0.10) * frac + 0.001

def draw(k):
    """Render playhead at build-frame index k (0..N-1)."""
    t = T[k]
    # TOP glow revealed up to k
    xr = T[:k + 1]; yr = S[:k + 1]
    for ln in top_glow_layers:
        ln.set_data(xr, yr)
    top_head.set_data([t], [S[k]])

    # BOTTOM spikes: reveal those with spike_t <= t
    n_shown = 0
    for ln, dot, st in spike_stems:
        if st <= t + 1e-9:
            ln.set_alpha(0.95); dot.set_alpha(0.95)
            n_shown += 1
        else:
            ln.set_alpha(0.0); dot.set_alpha(0.0)
    bot_head.set_data([t], [0.18])

    # METER: increments only on spikes (count of shown spikes)
    meter_fill.set_height(meter_height_for(n_shown))
    meter_count.set_text(str(n_shown))

    arts = top_glow_layers + [top_head, bot_head, meter_fill, meter_count]
    return arts

# ----- frame schedule: POSTER-FIRST -----
POSTER = 46  # mid-sweep, meter partway
frames = [POSTER] * 8 + list(range(N)) + [N - 1] * 16

def update(fi):
    return draw(fi)

anim = FuncAnimation(fig, update, frames=frames, interval=62, blit=False)
out_path = OUT / "dimmer_vs_morse.gif"
anim.save(out_path, writer=PillowWriter(fps=16),
          savefig_kwargs={"facecolor": BG})
plt.close(fig)
print("WROTE", out_path, "N_SPIKES=", N_SPIKES)
