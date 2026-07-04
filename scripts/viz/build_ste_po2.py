"""
H. ste_po2.gif
Straight-Through Estimator on power-of-two weights.

LEFT panel:
  a po2 quantiser STAIRCASE over w in [-2.2, 2.2], with 13 levels
  {0, +/-1/16, +/-1/8, +/-1/4, +/-1/2, +/-1, +/-2} and a flat DEAD-BAND gap
  around 0 (|w| < 2^-5 -> 0). A raw-weight dot slides continuously along x;
  its quantised output SNAPS between the steps (the FORWARD pass).

  Then a ghost identity diagonal y = x lights up and the raw dot GLIDES
  smoothly along it (the BACKWARD pass sees identity).
    "forward: aggancia al po2  ·  backward: fa finta sia identità"

HUD: raw fp weight drifting continuously while the quantised value jumps in
discrete clicks.

Inset: "×2^k = shift (≈10 LUT)  vs  moltiplicazione (≈100 LUT)".

Eq:  w_q = sign(w)·2^round(log2|w|),  exp∈[-4,1],  0 se |w|<2^-5
     backward  ∂w_q/∂w ≈ 1

Poster (frame 0) = a pose with the staircase + a snapped dot + the identity
ghost visible.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.animation import FuncAnimation, PillowWriter
from pathlib import Path

# ------------------------------------------------------------------ palette
BG      = "#15181D"
TEXT    = "#C7D0DA"
MUTED   = "#8A939D"
SPINE   = "#39424D"
BLUE    = "#56B4E9"   # membrane / forward snapped value
GREEN   = "#2ECC71"   # safe / identity backward
AMBER   = "#F0B429"   # threshold
TEAL    = "#1FB6B6"   # SNN spike accent
DANGER  = "#E0563B"
ANNORNG = "#E8A13C"

OUT = Path("presentation/cf_fsnn_thesis/assets/manim")
OUT.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ po2 quantiser
EXP_MIN, EXP_MAX = -4, 1          # 2^-4 .. 2^1  => 1/16 .. 2
DEAD = 2.0 ** -5                  # |w| < 2^-5 -> 0

def quant_po2(w):
    """Vectorised power-of-two quantiser with dead-band and exponent clamp."""
    w = np.asarray(w, dtype=float)
    out = np.zeros_like(w)
    aw = np.abs(w)
    mask = aw >= DEAD
    e = np.round(np.log2(aw, where=mask, out=np.full_like(aw, EXP_MIN)))
    e = np.clip(e, EXP_MIN, EXP_MAX)
    out[mask] = np.sign(w[mask]) * (2.0 ** e[mask])
    return out

# the 13 discrete levels
LEVELS = sorted(set([0.0]
                    + [ 2.0 ** k for k in range(EXP_MIN, EXP_MAX + 1)]
                    + [-2.0 ** k for k in range(EXP_MIN, EXP_MAX + 1)]))
# -> [-2,-1,-0.5,-0.25,-0.125,-0.0625, 0, 0.0625,...,2]  (13 values)

XLIM = 2.35
xs = np.linspace(-XLIM, XLIM, 1400)
qs = quant_po2(xs)

# ------------------------------------------------------------------ figure
fig, (axL, axR) = plt.subplots(1, 2, figsize=(9.4, 4.9), dpi=116,
                               gridspec_kw={"width_ratios": [1.0, 0.72]})
fig.patch.set_facecolor(BG)
fig.subplots_adjust(left=0.085, right=0.975, top=0.86, bottom=0.13, wspace=0.28)

for ax in (axL, axR):
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_color(SPINE)
    ax.tick_params(colors=MUTED, labelsize=8)

# ---- LEFT: staircase ----------------------------------------------------
axL.set_xlim(-XLIM, XLIM)
axL.set_ylim(-XLIM, XLIM)
axL.set_xlabel("peso raw  w  (fp32)", color=TEXT, fontsize=10)
axL.set_ylabel("peso quantizzato  w_q", color=TEXT, fontsize=10)
axL.set_title("FORWARD: aggancia al power-of-two",
              color=BLUE, fontsize=10.5, pad=8, family="monospace")
axL.axhline(0, color=SPINE, lw=0.8, alpha=0.6)
axL.axvline(0, color=SPINE, lw=0.8, alpha=0.6)

# identity ghost diagonal (backward reference) — starts dim
(ident_line,) = axL.plot([-XLIM, XLIM], [-XLIM, XLIM], color=GREEN,
                         lw=1.6, ls="--", alpha=0.12, zorder=2)
ident_lbl = axL.text(1.35, 1.95, "y = x  (identità)", color=GREEN,
                     fontsize=8.5, alpha=0.12, rotation=39,
                     ha="center", va="center", family="monospace")

# staircase — plotted as flat treads (draw each level segment)
def draw_staircase():
    # find x-thresholds where quant changes
    edges = []
    prev = qs[0]
    for i in range(1, len(xs)):
        if qs[i] != prev:
            edges.append((xs[i], prev, qs[i]))
            prev = qs[i]
    # treads
    seg_x, seg_y = [], []
    start = -XLIM
    prev = qs[0]
    for (xe, before, after) in edges:
        axL.plot([start, xe], [before, before], color=AMBER, lw=2.4,
                 solid_capstyle="round", zorder=4)
        start = xe
        prev = after
    axL.plot([start, XLIM], [prev, prev], color=AMBER, lw=2.4,
             solid_capstyle="round", zorder=4)
    # dead-band highlight around 0
    axL.axvspan(-DEAD, DEAD, color=DANGER, alpha=0.10, zorder=1)
    axL.text(0.0, -2.12, "dead-band\n|w|<2⁻⁵→0", color=DANGER, fontsize=7.3,
             ha="center", va="center", family="monospace")

draw_staircase()

# level ticks on y-axis (thinned to key levels to avoid crowding near 0)
YT = [-2, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2]
def ylab(v):
    if abs(v) < 1e-6:
        return "0"
    if abs(v) >= 1:
        return f"{v:g}"
    s = "+" if v > 0 else "-"
    return f"{s}1/{int(round(1/abs(v)))}"
axL.set_yticks(YT)
axL.set_yticklabels([ylab(v) for v in YT], fontsize=7.2)
axL.set_xticks([-2, -1, 0, 1, 2])

# forward: vertical drop line raw->quant, snapped dot, raw dot on x-axis
(drop_line,) = axL.plot([], [], color=BLUE, lw=1.2, ls=":", alpha=0.7, zorder=5)
raw_dot_x  = axL.plot([], [], "o", color=TEXT, ms=7, zorder=7,
                      mec="white", mew=0.8)[0]     # raw weight on the diagonal-x
snap_dot   = axL.plot([], [], "o", color=BLUE, ms=11, zorder=8,
                      mec="white", mew=1.2)[0]      # snapped quantised value
# backward: glowing dot gliding on identity
back_dot   = axL.plot([], [], "o", color=GREEN, ms=10, zorder=8,
                      mec="white", mew=1.1, alpha=0.0)[0]

# ---- RIGHT: HUD + equation + cost inset ---------------------------------
axR.set_xlim(0, 1); axR.set_ylim(0, 1); axR.axis("off")

axR.text(0.5, 0.965, "STE  su  pesi  po2", color=TEXT, fontsize=12,
         fontweight="bold", ha="center", family="monospace")

# equation block
eq_box = FancyBboxPatch((0.03, 0.66), 0.94, 0.20,
                        boxstyle="round,pad=0.02,rounding_size=0.03",
                        facecolor="#1B1F26", edgecolor=SPINE, lw=1.2)
axR.add_patch(eq_box)
axR.text(0.5, 0.815, r"$w_q=\mathrm{sign}(w)\cdot 2^{\,\mathrm{round}(\log_2|w|)}$",
         color=AMBER, fontsize=11.5, ha="center", va="center")
axR.text(0.5, 0.735, r"$\exp\in[-4,1]$   ·   $0$ se $|w|<2^{-5}$",
         color=MUTED, fontsize=8.6, ha="center", va="center")
axR.text(0.5, 0.688, r"backward:  $\partial w_q/\partial w \approx 1$",
         color=GREEN, fontsize=9.2, ha="center", va="center", family="monospace")

# HUD: raw vs quant readout
hud_box = FancyBboxPatch((0.03, 0.40), 0.94, 0.20,
                         boxstyle="round,pad=0.02,rounding_size=0.03",
                         facecolor="#1B1F26", edgecolor=SPINE, lw=1.2)
axR.add_patch(hud_box)
axR.text(0.09, 0.545, "raw  w :", color=MUTED, fontsize=9.5,
         ha="left", va="center", family="monospace")
hud_raw = axR.text(0.93, 0.545, "", color=TEXT, fontsize=11,
                   ha="right", va="center", family="monospace", fontweight="bold")
axR.text(0.09, 0.455, "w_q    :", color=MUTED, fontsize=9.5,
         ha="left", va="center", family="monospace")
hud_q = axR.text(0.93, 0.455, "", color=BLUE, fontsize=12,
                 ha="right", va="center", family="monospace", fontweight="bold")

# phase caption (forward / backward)
phase_cap = axR.text(0.5, 0.335, "", color=TEXT, fontsize=9.3,
                     ha="center", va="center", family="monospace")

# cost inset
cost_box = FancyBboxPatch((0.03, 0.045), 0.94, 0.235,
                          boxstyle="round,pad=0.02,rounding_size=0.03",
                          facecolor="#1B1F26", edgecolor=TEAL, lw=1.3)
axR.add_patch(cost_box)
axR.text(0.5, 0.245, "perché po2 conviene su FPGA", color=TEAL,
         fontsize=8.8, ha="center", va="center", family="monospace",
         fontweight="bold")
axR.text(0.5, 0.165, "×2ᵏ  =  shift bit", color=GREEN, fontsize=10.5,
         ha="center", va="center", family="monospace")
axR.text(0.28, 0.093, "≈10 LUT", color=GREEN, fontsize=9.5,
         ha="center", va="center", family="monospace", fontweight="bold")
axR.text(0.5, 0.093, "vs", color=MUTED, fontsize=8.5, ha="center", va="center")
axR.text(0.74, 0.093, "≈100 LUT", color=DANGER, fontsize=9.5,
         ha="center", va="center", family="monospace", fontweight="bold")
axR.text(0.74, 0.045, "(moltiplic.)", color=MUTED, fontsize=6.8,
         ha="center", va="center")

# ------------------------------------------------------------------ animation
# Two phases:
#   FWD_FRAMES: raw dot sweeps x -> snapped value clicks along staircase
#   BWD_FRAMES: identity ghost lights up, raw glides smoothly on y=x
FWD_FRAMES = 40
BWD_FRAMES = 26
HOLD       = 16

# raw sweeps from -2.05 .. +2.05 (a gentle S so it lingers near the dead-band)
def raw_at_fwd(k):
    p = k / (FWD_FRAMES - 1)
    return -2.05 + 4.10 * p

def raw_at_bwd(k):
    p = k / (BWD_FRAMES - 1)
    # glide back and forth to emphasise smooth (continuous) motion
    return -1.6 + 3.2 * (0.5 - 0.5 * np.cos(p * np.pi))

def fmt(v):
    if abs(v) < 1e-9:
        return "0"
    return f"{v:+.3f}"

def draw(state):
    kind, k = state
    if kind == "fwd":
        w = raw_at_fwd(k)
        wq = float(quant_po2(w))
        # forward artists on
        raw_dot_x.set_data([w], [w])            # raw sits on identity x=y visually
        snap_dot.set_data([w], [wq])
        snap_dot.set_alpha(1.0)
        drop_line.set_data([w, w], [w, wq])
        drop_line.set_alpha(0.7)
        back_dot.set_alpha(0.0)
        # identity stays dim in forward
        ident_line.set_alpha(0.12); ident_lbl.set_alpha(0.12)
        axL.set_title("FORWARD: aggancia al power-of-two",
                      color=BLUE, fontsize=10.5, pad=8, family="monospace")
        phase_cap.set_text("forward → aggancia al po2")
        phase_cap.set_color(BLUE)
        hud_raw.set_text(fmt(w)); hud_raw.set_color(TEXT)
        hud_q.set_text(fmt(wq));  hud_q.set_color(BLUE)
    else:  # backward
        w = raw_at_bwd(k)
        # identity lights up
        p = k / (BWD_FRAMES - 1)
        a = 0.12 + 0.85 * np.clip(p * 2.5, 0, 1)
        ident_line.set_alpha(min(a, 0.95)); ident_lbl.set_alpha(min(a, 0.95))
        # forward artists fade but keep last snapped ghost faint
        snap_dot.set_alpha(0.22)
        drop_line.set_alpha(0.0)
        raw_dot_x.set_data([w], [w])
        back_dot.set_data([w], [w])             # glides on y=x
        back_dot.set_alpha(1.0)
        axL.set_title("BACKWARD: fa finta sia identità",
                      color=GREEN, fontsize=10.5, pad=8, family="monospace")
        phase_cap.set_text("backward → gradiente identità")
        phase_cap.set_color(GREEN)
        # HUD: raw drifts continuously, gradient passes through as if y=x
        hud_raw.set_text(fmt(w)); hud_raw.set_color(TEXT)
        hud_q.set_text(fmt(w));   hud_q.set_color(GREEN)  # backward sees w, not w_q
    return []

# ---- build frame list, poster-first --------------------------------------
# poster: a forward pose mid-sweep with a clean snapped step + identity faintly there
POSTER_K = int(0.62 * (FWD_FRAMES - 1))   # raw > 0, snapped to a clear level
seq = ([("fwd", POSTER_K)] * 8
       + [("fwd", k) for k in range(FWD_FRAMES)]
       + [("fwd", FWD_FRAMES - 1)] * 3
       + [("bwd", k) for k in range(BWD_FRAMES)]
       + [("bwd", BWD_FRAMES - 1)] * HOLD)

anim = FuncAnimation(fig, draw, frames=seq, interval=1000 / 15, blit=False)
out_path = OUT / "ste_po2.gif"
anim.save(out_path, writer=PillowWriter(fps=15),
          savefig_kwargs={"facecolor": BG})
plt.close(fig)
print("WROTE", out_path.resolve())
