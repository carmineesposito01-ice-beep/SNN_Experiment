"""F. low_rank.gif — the 32x32 -> U(32x8) . V(8x32) factorisation.

A full 32x32 recurrent weight grid (imshow, 1024 cells, "1024 pesi") SPLITS into a
tall U (32x8) and a wide V (8x32) sliding out; U.V reconstructs an approximation of
the 32x32; a counter animates 1024 -> 512; a bracket highlights the rank-8
"bottleneck" (the shared 8-wide waist).

Eq: W_rec = U . V,  U in R^{32x8},  V in R^{8x32},  2*32*8 = 512 < 1024.
"lo stato passa per un collo di bottiglia rango-8".

Dark palette. matplotlib -> GIF via Pillow. No manim/ffmpeg.
"""
import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import FancyBboxPatch

OUT = pathlib.Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/assets/manim"
OUT.mkdir(parents=True, exist_ok=True)

# ---- dark palette --------------------------------------------------------
BG    = "#15181D"
TEXT  = "#C7D0DA"
MUTED = "#8A939D"
SPINE = "#39424D"
BLUE  = "#56B4E9"   # W full
AMBER = "#F0B429"   # counter highlight / bracket
TEAL  = "#1FB6B6"   # SNN-spike teal -> use for U
PURPLE = "#D48AC0"  # V
GREEN = "#2ECC71"

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT, "axes.labelcolor": TEXT, "axes.edgecolor": SPINE,
    "xtick.color": MUTED, "ytick.color": MUTED, "font.size": 10,
})

N = 32          # full dim
R = 8           # rank / bottleneck

rng = np.random.default_rng(3)
# Build a genuinely rank-8 matrix so U.V reconstructs it well (visually honest).
U_true = rng.standard_normal((N, R)) * 0.9
V_true = rng.standard_normal((R, N)) * 0.9
W = U_true @ V_true
# normalize for a clean colormap range
W = W / np.abs(W).max()
U_show = U_true / np.abs(U_true).max()
V_show = V_true / np.abs(V_true).max()
Wapprox = (U_show @ V_show)
Wapprox = Wapprox / np.abs(Wapprox).max()

CMAP = "PuOr"       # diverging, reads well on dark
VMIN, VMAX = -1, 1


def lerp(a, b, s):
    return a + (b - a) * s


def main():
    fig = plt.figure(figsize=(11, 5.4), dpi=125)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5.4)
    ax.axis("off")

    # Coordinate plan (data units on the 11 x 5.4 canvas):
    #  - Full W centered-left at rest, slides to the far left when split.
    #  - U appears as a tall block, V as a wide block, product to the right.
    # geometry of a 32x32 imshow "tile" (in data coords)
    full_c = (3.1, 2.9)     # center of full W (start)
    full_w, full_h = 2.4, 2.4

    # split targets
    W_left_c = (1.55, 2.9)
    U_c = (4.55, 2.9)       # tall (32x8): narrow width
    V_c = (6.7, 2.9)        # wide (8x32): short height
    prod_c = (9.05, 2.9)    # U.V reconstruction

    U_w, U_h = 0.62, 2.4    # 8/32 aspect for width
    V_w, V_h = 2.4, 0.62
    prod_w, prod_h = 2.0, 2.0

    def extent(c, w, h):
        return [c[0] - w / 2, c[0] + w / 2, c[1] - h / 2, c[1] + h / 2]

    im_full = ax.imshow(W, cmap=CMAP, vmin=VMIN, vmax=VMAX,
                        extent=extent(full_c, full_w, full_h), zorder=3,
                        aspect="auto", origin="upper")
    im_U = ax.imshow(U_show, cmap=CMAP, vmin=VMIN, vmax=VMAX,
                     extent=extent(U_c, U_w, U_h), zorder=3, aspect="auto",
                     origin="upper")
    im_V = ax.imshow(V_show, cmap=CMAP, vmin=VMIN, vmax=VMAX,
                     extent=extent(V_c, V_w, V_h), zorder=3, aspect="auto",
                     origin="upper")
    im_prod = ax.imshow(Wapprox, cmap=CMAP, vmin=VMIN, vmax=VMAX,
                        extent=extent(prod_c, prod_w, prod_h), zorder=3,
                        aspect="auto", origin="upper")

    # frames around each matrix
    def make_frame(c, w, h, color, lw=2.0):
        r = FancyBboxPatch((c[0] - w / 2, c[1] - h / 2), w, h,
                           boxstyle="round,pad=0.02,rounding_size=0.04",
                           fill=False, edgecolor=color, lw=lw, zorder=6)
        ax.add_patch(r)
        return r

    fr_full = make_frame(full_c, full_w, full_h, BLUE, 2.4)
    fr_U = make_frame(U_c, U_w, U_h, TEAL, 2.2)
    fr_V = make_frame(V_c, V_w, V_h, PURPLE, 2.2)
    fr_prod = make_frame(prod_c, prod_w, prod_h, GREEN, 2.0)

    # labels
    lbl_full = ax.text(*full_c, "", ha="center", va="center", zorder=8)
    lbl_full_top = ax.text(full_c[0], full_c[1] + full_h / 2 + 0.28,
                           "W  (32x32)", ha="center", va="bottom",
                           color=BLUE, fontsize=12, weight="bold", zorder=8)
    lbl_full_bot = ax.text(full_c[0], full_c[1] - full_h / 2 - 0.24,
                           "1024 pesi", ha="center", va="top",
                           color=TEXT, fontsize=11, zorder=8)

    lbl_U = ax.text(U_c[0], U_c[1] + U_h / 2 + 0.18, "U  32x8",
                    ha="center", va="bottom", color=TEAL, fontsize=11,
                    weight="bold", zorder=8)
    lbl_times = ax.text((U_c[0] + V_c[0]) / 2, 2.9, r"$\cdot$",
                        ha="center", va="center", color=TEXT, fontsize=22,
                        zorder=8)
    lbl_V = ax.text(V_c[0], V_c[1] + V_h / 2 + 0.30, "V   8x32",
                    ha="center", va="bottom", color=PURPLE, fontsize=11,
                    weight="bold", zorder=8)
    lbl_eq = ax.text((V_c[0] + prod_c[0]) / 2 + 0.05, 2.9, r"$\approx$",
                     ha="center", va="center", color=TEXT, fontsize=20, zorder=8)
    lbl_prod = ax.text(prod_c[0], prod_c[1] + prod_h / 2 + 0.28,
                       r"$U\cdot V$", ha="center", va="bottom", color=GREEN,
                       fontsize=12, weight="bold", zorder=8)

    # rank-8 bottleneck bracket (the shared 8-wide waist between U and V)
    waist_x = (U_c[0] + V_c[0]) / 2
    brack = ax.annotate("", xy=(V_c[0] - V_w / 2, 1.35),
                        xytext=(U_c[0] + U_w / 2, 1.35),
                        arrowprops=dict(arrowstyle="<->", color=AMBER, lw=2.2),
                        zorder=9)
    brack_lbl = ax.text(waist_x, 1.02, "collo di bottiglia rango-8",
                        ha="center", va="top", color=AMBER, fontsize=11,
                        weight="bold", zorder=9)

    # counter 1024 -> 512
    counter = ax.text(5.5, 4.95, "", ha="center", va="center",
                      fontsize=15, color=AMBER, family="monospace",
                      weight="bold", zorder=10)

    # equation strip
    eqn = ax.text(5.5, 0.34,
                  r"$W_{rec}=U\cdot V,\;\; U\in\mathbb{R}^{32\times8},\;"
                  r"V\in\mathbb{R}^{8\times32},\;\; 2\cdot32\cdot8=512<1024$",
                  ha="center", va="center", color=TEXT, fontsize=11.5, zorder=10)

    caption = ax.text(9.05, 4.62, "lo stato passa per un\ncollo di bottiglia rango-8",
                      ha="center", va="center", color=MUTED, fontsize=10,
                      style="italic", zorder=10)

    # ---- staged animation ------------------------------------------------
    # Stage progress s in [0,1]:
    #   0.00-0.10  full W only (poster region)
    #   0.10-0.55  W slides left; U and V slide out; product fades in
    #   0.55-1.00  counter ticks 1024 -> 512; bracket pulses
    def alpha_at(s, lo, hi):
        if s <= lo:
            return 0.0
        if s >= hi:
            return 1.0
        return (s - lo) / (hi - lo)

    def set_stage(s):
        # split motion 0.10..0.55
        split = np.clip((s - 0.10) / 0.45, 0, 1)
        # ease
        e = split * split * (3 - 2 * split)

        # full W slides from center to left
        fc = (lerp(full_c[0], W_left_c[0], e), full_c[1])
        im_full.set_extent(extent(fc, full_w, full_h))
        fr_full.set_x(fc[0] - full_w / 2)
        fr_full.set_y(fc[1] - full_h / 2)
        lbl_full_top.set_position((fc[0], fc[1] + full_h / 2 + 0.28))
        lbl_full_top.set_text("W  (32x32)" if e < 0.5 else "W")
        lbl_full_bot.set_position((fc[0], fc[1] - full_h / 2 - 0.24))
        lbl_full_bot.set_text("1024 pesi")

        # U, V, product appear (slide in from behind W by fading + small shift)
        a_uv = alpha_at(s, 0.12, 0.5)
        a_pr = alpha_at(s, 0.30, 0.62)
        for im, fr, a in ((im_U, fr_U, a_uv), (im_V, fr_V, a_uv),
                          (im_prod, fr_prod, a_pr)):
            im.set_alpha(a)
            fr.set_alpha(a)
        for lbl, a in ((lbl_U, a_uv), (lbl_V, a_uv), (lbl_times, a_uv),
                       (lbl_prod, a_pr), (lbl_eq, a_pr)):
            lbl.set_alpha(a)

        # bottleneck bracket 0.45..
        a_br = alpha_at(s, 0.45, 0.72)
        brack.set_alpha(a_br)
        brack_lbl.set_alpha(a_br)

        # counter ticks 1024 -> 512 as the split completes (done by s~0.62,
        # so the poster at s~0.7 reads the final 512, not an arbitrary value)
        a_cnt = alpha_at(s, 0.20, 0.55)
        counter.set_alpha(min(1.0, a_cnt + 0.0))
        tick = np.clip((s - 0.32) / 0.30, 0, 1)
        val = int(round(lerp(1024, 512, tick)))
        counter.set_text(f"parametri: {val}      (1024 -> 512, -50%)")

        # equation + caption appear late
        eqn.set_alpha(alpha_at(s, 0.6, 0.85))
        caption.set_alpha(alpha_at(s, 0.5, 0.78))

        return [im_full, im_U, im_V, im_prod, fr_full, fr_U, fr_V, fr_prod,
                lbl_full_top, lbl_full_bot, lbl_U, lbl_V, lbl_times, lbl_prod,
                lbl_eq, brack, brack_lbl, counter, eqn, caption]

    NF = 60
    # POSTER-FIRST: a representative frame showing U, V and the 1024->512 counter.
    POSTER_S = 0.7
    poster_idx = int(POSTER_S * (NF - 1))
    build = list(range(NF))
    seq = [poster_idx] * 8 + build + [NF - 1] * 16

    def frame(i):
        s = seq[i] / (NF - 1)
        return set_stage(s)

    anim = FuncAnimation(fig, frame, frames=len(seq), interval=62, blit=True)
    out = OUT / "low_rank.gif"
    anim.save(out, writer=PillowWriter(fps=15),
              savefig_kwargs={"facecolor": BG})
    print("OK", out)


if __name__ == "__main__":
    main()
