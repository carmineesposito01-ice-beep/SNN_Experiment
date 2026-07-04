"""
G. architecture_flow.gif
The CF-FSNN network drawn as coloured "balls", with an animated signal pulse
flowing left -> right through the layers.

Layout (fixed):
  4 INPUT balls (grey, continuous)  ->  32 HIDDEN ALIF balls (amber, spiking, ~15% light per tick)
  ->  5 OUTPUT LI balls (blue, smooth integrators)  ->  5 decoded param chips [v0,T,s0,a,b] (green)

Animated:
  - a signal PULSE travels left->right,
  - input balls glow steadily (direct current I = W.x),
  - hidden balls BLINK as sparse spikes (~15% per tick),
  - a recurrent U.V arc loops the hidden block back on itself and pulses,
  - output balls FILL smoothly (no spikes),
  - the 5 outputs label into the params with their ranges,
  - a "tick 1->10" counter shows the 10 internal ticks per step.

Dark palette per house spec. Poster (frame 0) = a mid-flow pose with hidden
spikes visible + recurrent arc glowing.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Arc
from matplotlib.collections import LineCollection
from matplotlib.animation import FuncAnimation, PillowWriter
from pathlib import Path

# ------------------------------------------------------------------ palette
BG      = "#15181D"
TEXT    = "#C7D0DA"
MUTED   = "#8A939D"
SPINE   = "#39424D"
BLUE    = "#56B4E9"   # output LI / membrane
GREEN   = "#2ECC71"   # decoded params / safe
AMBER   = "#F0AE3A"   # hidden ALIF spiking
GREY    = "#9AA3AD"   # input continuous
DANGER  = "#E0563B"

OUT = Path("presentation/cf_fsnn_thesis/assets/manim")
OUT.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ geometry
N_IN, N_HID, N_OUT = 4, 32, 5
N_TICKS = 10

# x positions of the four columns
X_IN, X_HID, X_OUT, X_PAR = 1.2, 3.9, 6.6, 8.9

# input ball y-positions (4 spread)
y_in = np.linspace(2.4, 5.6, N_IN)
# hidden balls: 8 rows x 4 cols grid inside a rounded block
hid_rows, hid_cols = 8, 4
hx = np.linspace(X_HID - 0.55, X_HID + 0.55, hid_cols)
hy = np.linspace(1.15, 6.45, hid_rows)
HXY = np.array([(x, y) for y in hy for x in hx])  # 32 points, row-major top-down
# output ball y-positions (5)
y_out = np.linspace(2.0, 6.0, N_OUT)
# param chips
PARAMS = [("v0", "8-45"), ("T", "0.5-2.5"), ("s0", "1-5"),
          ("a", "0.3-2.5"), ("b", "0.5-3")]
y_par = np.linspace(2.0, 6.0, N_OUT)

R_IN, R_HID, R_OUT = 0.30, 0.20, 0.32

# deterministic sparse spike pattern per tick (~15% of 32 = ~5 neurons)
rng = np.random.default_rng(7)
SPIKES = []  # boolean mask per tick
for t in range(N_TICKS):
    m = np.zeros(N_HID, dtype=bool)
    k = max(3, int(round(0.15 * N_HID)))  # ~5
    idx = rng.choice(N_HID, size=k, replace=False)
    m[idx] = True
    SPIKES.append(m)

# ------------------------------------------------------------------ helper colour math
def blend(c1, c2, t):
    """Linear blend of two hex colours; t in [0,1]."""
    a = np.array(matplotlib.colors.to_rgb(c1))
    b = np.array(matplotlib.colors.to_rgb(c2))
    return tuple(a + (b - a) * np.clip(t, 0, 1))


# ------------------------------------------------------------------ figure
fig, ax = plt.subplots(figsize=(9.2, 5.0), dpi=118)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0.2, 10.2)
ax.set_ylim(0.4, 7.6)
ax.axis("off")

# ---- static synapse lines (drawn once, dim) -----------------------------
def dim_lines():
    segs = []
    # input -> hidden (sample: each input to each hidden col-top representative)
    for (xi, yi) in zip([X_IN] * N_IN, y_in):
        for (xh, yh) in HXY[::3]:  # subsample so it's not a solid wall
            segs.append([(xi + R_IN, yi), (xh - R_HID, yh)])
    # hidden -> output
    for (xh, yh) in HXY[::4]:
        for yo in y_out:
            segs.append([(xh + R_HID, yh), (X_OUT - R_OUT, yo)])
    lc = LineCollection(segs, colors=SPINE, linewidths=0.5, alpha=0.28, zorder=1)
    ax.add_collection(lc)

dim_lines()

# ---- column captions ----------------------------------------------------
ax.text(X_IN, 7.15, "INPUT", color=GREY, fontsize=11, fontweight="bold",
        ha="center", family="monospace")
ax.text(X_IN, 6.78, "continuo", color=MUTED, fontsize=8, ha="center")
ax.text(X_HID, 7.25, "HIDDEN  ALIF", color=AMBER, fontsize=11, fontweight="bold",
        ha="center", family="monospace")
ax.text(X_HID, 7.00, "spiking (sparso ~15%)", color=MUTED, fontsize=8, ha="center")
ax.text(X_OUT, 7.15, "OUTPUT  LI", color=BLUE, fontsize=11, fontweight="bold",
        ha="center", family="monospace")
ax.text(X_OUT, 6.78, "integratore (continuo)", color=MUTED, fontsize=8, ha="center")
ax.text(X_PAR, 7.15, "decode  σ", color=GREEN, fontsize=11, fontweight="bold",
        ha="center", family="monospace")
ax.text(X_PAR, 6.78, "parametri IDM", color=MUTED, fontsize=8, ha="center")

# ---- edge labels --------------------------------------------------------
ax.text((X_IN + X_HID) / 2, 1.02, "I = W·x", color=GREY, fontsize=9,
        ha="center", style="italic")
ax.text((X_HID + X_OUT) / 2, 1.02, "spike → integra", color=BLUE,
        fontsize=9, ha="center", style="italic")

# ---- recurrent arc (U.V) around the hidden block ------------------------
rec_arc = FancyArrowPatch(
    (X_HID + 0.75, 6.15), (X_HID + 0.75, 1.45),
    connectionstyle="arc3,rad=-0.95",
    arrowstyle="-|>", mutation_scale=14,
    color=AMBER, lw=2.0, alpha=0.35, zorder=2)
ax.add_patch(rec_arc)
rec_label = ax.text(X_HID + 1.62, 4.0, "U·V\nricorrente", color=AMBER,
                    fontsize=8.5, ha="center", va="center", alpha=0.55,
                    family="monospace")

# ---- create artist objects ---------------------------------------------
in_balls = [Circle((X_IN, y), R_IN, facecolor=BG, edgecolor=GREY, lw=2.0, zorder=4)
            for y in y_in]
for c in in_balls:
    ax.add_patch(c)
in_labels = ["gap", "Δv", "v", "a_lead"]
for y, lab in zip(y_in, in_labels):
    ax.text(X_IN - 0.55, y, lab, color=MUTED, fontsize=8, ha="right", va="center")

hid_balls = [Circle((x, y), R_HID, facecolor=BG, edgecolor=AMBER, lw=1.3, zorder=4)
             for (x, y) in HXY]
for c in hid_balls:
    ax.add_patch(c)

out_balls = [Circle((X_OUT, y), R_OUT, facecolor=BG, edgecolor=BLUE, lw=2.0, zorder=4)
             for y in y_out]
for c in out_balls:
    ax.add_patch(c)
# inner "fill" wedge for output integrators, drawn as a scaled circle
out_fill = [Circle((X_OUT, y), 0.001, facecolor=BLUE, edgecolor="none",
                   alpha=0.9, zorder=5) for y in y_out]
for c in out_fill:
    ax.add_patch(c)

# param chips (rounded boxes) + arrows out->param
par_boxes = []
for (name, rng_txt), yo, yp in zip(PARAMS, y_out, y_par):
    box = FancyBboxPatch((X_PAR - 0.62, yp - 0.24), 1.24, 0.48,
                         boxstyle="round,pad=0.02,rounding_size=0.10",
                         facecolor=BG, edgecolor=GREEN, lw=1.6, alpha=0.25,
                         zorder=4)
    ax.add_patch(box)
    par_boxes.append(box)
    ax.text(X_PAR - 0.30, yp + 0.005, name, color=GREEN, fontsize=10.5,
            fontweight="bold", ha="center", va="center", family="monospace")
    ax.text(X_PAR + 0.22, yp + 0.005, rng_txt, color=MUTED, fontsize=7.3,
            ha="center", va="center", family="monospace")
    # connector out-ball -> chip
    arr = FancyArrowPatch((X_OUT + R_OUT, yo), (X_PAR - 0.64, yp),
                          arrowstyle="-|>", mutation_scale=9,
                          color=SPINE, lw=1.0, alpha=0.35, zorder=2)
    ax.add_patch(arr)

# ---- moving pulse marker ------------------------------------------------
pulse = Circle((X_IN, 4.0), 0.12, facecolor=BLUE, edgecolor="white",
               lw=1.2, alpha=0.0, zorder=8)
ax.add_patch(pulse)
pulse_glow = Circle((X_IN, 4.0), 0.26, facecolor=BLUE, edgecolor="none",
                    alpha=0.0, zorder=7)
ax.add_patch(pulse_glow)

# ---- tick counter -------------------------------------------------------
tick_txt = ax.text(9.9, 0.75, "", color=TEXT, fontsize=11, ha="right",
                   va="center", family="monospace", fontweight="bold")
phase_txt = ax.text(0.35, 0.75, "", color=MUTED, fontsize=9.5, ha="left",
                    va="center", family="monospace")

# ------------------------------------------------------------------ animation
# Timeline: the pulse sweeps x from X_IN..X_PAR over the sequence.
# We map a "progress" p in [0,1] to x, and derive which stage is active.
FLOW_FRAMES = 46  # frames for one full L->R sweep


def stage_progress(p):
    """Return x of pulse and per-stage activation levels for progress p in [0,1]."""
    x = X_IN + (X_PAR - X_IN) * p
    # activation ramps: input full first, then hidden, then output, then params
    in_act  = np.clip((p - 0.00) / 0.18, 0, 1)
    hid_act = np.clip((p - 0.18) / 0.30, 0, 1)
    out_act = np.clip((p - 0.48) / 0.30, 0, 1)
    par_act = np.clip((p - 0.78) / 0.22, 0, 1)
    return x, in_act, hid_act, out_act, par_act


def draw(frame_idx):
    # frame_idx maps into the flow sweep (0..FLOW_FRAMES-1); tick counter
    # advances across the whole sweep 1..10.
    p = frame_idx / (FLOW_FRAMES - 1)
    x, in_act, hid_act, out_act, par_act = stage_progress(p)

    # current internal tick (1..10)
    tick = int(np.clip(np.floor(p * N_TICKS) + 1, 1, N_TICKS))
    tick_txt.set_text(f"tick {tick:2d} / {N_TICKS}")

    # phase label
    if p < 0.18:
        phase = "corrente in ingresso"
    elif p < 0.48:
        phase = "spike sparsi nel layer nascosto"
    elif p < 0.78:
        phase = "integrazione (nessuno spike)"
    else:
        phase = "decodifica → parametri IDM"
    phase_txt.set_text(phase)

    # --- input balls: steady glow proportional to in_act ---
    for c in in_balls:
        c.set_facecolor(blend(BG, GREY, 0.15 + 0.6 * in_act))
        c.set_alpha(1.0)
        c.set_linewidth(2.0 + 1.0 * in_act)

    # --- hidden balls: sparse blink for current tick, gated by hid_act ---
    mask = SPIKES[tick - 1]
    for i, c in enumerate(hid_balls):
        if hid_act > 0.05 and mask[i]:
            c.set_facecolor(AMBER)
            c.set_edgecolor("white")
            c.set_linewidth(1.6)
            c.set_radius(R_HID * (1.0 + 0.35 * hid_act))
            c.set_alpha(1.0)
        else:
            c.set_facecolor(BG)
            c.set_edgecolor(AMBER)
            c.set_linewidth(1.1)
            c.set_radius(R_HID)
            c.set_alpha(0.55 + 0.25 * hid_act)

    # --- recurrent arc glow pulses while hidden active ---
    glow = 0.30 + 0.55 * hid_act * (0.6 + 0.4 * np.sin(p * 12))
    rec_arc.set_alpha(np.clip(glow, 0.15, 0.9))
    rec_arc.set_linewidth(1.8 + 1.6 * hid_act)
    rec_label.set_alpha(np.clip(0.4 + 0.5 * hid_act, 0.4, 0.9))

    # --- output balls: smooth fill (integrator) ---
    fill_levels = np.clip(out_act - np.linspace(0, 0.15, N_OUT), 0, 1)
    for c, f, lvl in zip(out_balls, out_fill, fill_levels):
        c.set_edgecolor(BLUE)
        c.set_linewidth(2.0 + 1.0 * out_act)
        f.set_radius(R_OUT * 0.92 * lvl)
        f.set_alpha(0.85 * (lvl ** 0.5) if lvl > 0.02 else 0.0)

    # --- param chips light up green ---
    for box in par_boxes:
        box.set_alpha(0.25 + 0.7 * par_act)
        box.set_linewidth(1.6 + 1.2 * par_act)

    # --- moving pulse ---
    # pulse y drifts gently to feel alive
    py = 4.0 + 0.6 * np.sin(p * 6.0)
    pulse.center = (x, py)
    pulse_glow.center = (x, py)
    a = 1.0 if 0.02 < p < 0.98 else 0.0
    pulse.set_alpha(0.9 * a)
    pulse_glow.set_alpha(0.35 * a)
    # pulse colour shifts grey->amber->blue->green as it crosses stages
    if p < 0.30:
        pc = blend(GREY, AMBER, p / 0.30)
    elif p < 0.60:
        pc = blend(AMBER, BLUE, (p - 0.30) / 0.30)
    else:
        pc = blend(BLUE, GREEN, (p - 0.60) / 0.40)
    pulse.set_facecolor(pc)
    pulse_glow.set_facecolor(pc)

    return []


# poster-first frame list: a meaningful mid-flow pose, then the build-up, then hold
POSTER = int(0.40 * (FLOW_FRAMES - 1))  # mid-flow: hidden spikes + arc glowing
frames = [POSTER] * 8 + list(range(FLOW_FRAMES)) + [FLOW_FRAMES - 1] * 16

anim = FuncAnimation(fig, draw, frames=frames, interval=1000 / 15, blit=False)
out_path = OUT / "architecture_flow.gif"
anim.save(out_path, writer=PillowWriter(fps=15),
          savefig_kwargs={"facecolor": BG})
plt.close(fig)
print("WROTE", out_path.resolve())
