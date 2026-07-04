"""E. training.gif  — HOW training works: BPTT+surrogate (LEFT) vs EventProp (RIGHT).

"Stessa salita, due corde": both panels show a weight w moving and a loss falling,
but via two very different gradient mechanisms.

LEFT  (BPTT + surrogate): the Heaviside step dS/dV = delta(V-theta) is a DEAD CLIFF
       (gradient 0 almost everywhere). A smooth surrogate bell 1/(1+gamma|V-theta|)^2
       bridges the cliff so a gradient "ball" can roll down the smoothed slope.
       The loss curve descends but WOBBLES (biased / approximate gradient).
RIGHT (EventProp): an adjoint variable lambda propagates BACKWARD in time, flat
       between events then taking EXACT vertical jumps precisely at spike instants.
       Its loss curve descends CLEANER.

Shared HUD (top): weight w STEPPING and loss COUNTING DOWN in both panels ->
       "addestrare = i pesi si muovono, la loss scende".

Dark palette. matplotlib -> GIF via Pillow. No manim/ffmpeg.
"""
import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

OUT = pathlib.Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/assets/manim"
OUT.mkdir(parents=True, exist_ok=True)

# ---- dark palette --------------------------------------------------------
BG       = "#15181D"
TEXT     = "#C7D0DA"
MUTED    = "#8A939D"
SPINE    = "#39424D"
BLUE     = "#56B4E9"   # membrane V(t)
GREEN    = "#2ECC71"   # spikes
AMBER    = "#F0B429"   # surrogate / threshold
PURPLE   = "#D48AC0"   # lambda adjoint (Donatello champion hue)
DANGER   = "#E0563B"   # dead cliff
BALLCOL  = "#E8A13C"   # rolling ball (ANN-continuous)

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": TEXT, "axes.labelcolor": TEXT, "axes.edgecolor": SPINE,
    "xtick.color": MUTED, "ytick.color": MUTED, "font.size": 10,
})

THETA = 0.0          # threshold offset (V - theta axis centered at 0)
GAMMA = 3.0          # surrogate sharpness
V     = np.linspace(-2.4, 2.4, 400)   # V - theta domain


# ---- gradient-landscape curves (LEFT panel) ------------------------------
def surrogate(v, gamma=GAMMA):
    """Smooth surrogate of dS/dV: bell 1/(1+gamma|v|)^2, peak 1 at v=0."""
    return 1.0 / (1.0 + gamma * np.abs(v)) ** 2


# A smooth "loss landscape" over the weight the ball rolls down (LEFT).
# We reuse a simple double-well-ish bowl so the ball visibly descends.
def landscape(w):
    return 0.55 * (w ** 2) + 0.12 * np.sin(3.1 * w) + 0.28


# ---- loss trajectories (both panels HUD) ---------------------------------
def make_losses(n):
    """Two descending loss curves over training steps.
    LEFT  wobbles (biased surrogate);  RIGHT is cleaner (exact EventProp)."""
    steps = np.arange(n)
    base = 1.0 * np.exp(-steps / (n * 0.42)) + 0.06
    rng = np.random.default_rng(7)
    wobble = 0.085 * np.exp(-steps / (n * 0.7)) * np.sin(steps * 0.9) \
        + 0.03 * np.exp(-steps / (n * 0.7)) * rng.standard_normal(n)
    loss_left = np.clip(base + wobble, 0.02, None)
    loss_right = np.clip(base * 0.96 + 0.012 * np.exp(-steps / (n * 0.9))
                         * np.sin(steps * 0.5), 0.02, None)
    return loss_left, loss_right


# ---- weight trajectory (HUD, both) ---------------------------------------
def make_weights(n):
    """Weight descends in visible SGD steps: w <- w - eta * dL/dw."""
    w = np.linspace(1.35, -0.05, n)          # smooth target
    # add discrete stair-stepping so the value visibly "steps"
    stepped = np.round(w * 6) / 6.0
    return w, stepped


# ---- EventProp adjoint lambda(t) (RIGHT lower) ---------------------------
SPIKE_T = [1.1, 2.6, 4.2, 5.6, 7.3, 8.7]
T_MAX = 10.0


def build_adjoint(n_pts=1400, base_decay=0.42, jump_frac=0.62):
    """lambda(t): flat-ish decay between spikes, EXACT downward jump at each spike,
    integrated BACKWARD in time (from T_MAX to 0)."""
    t = np.linspace(0, T_MAX, n_pts)
    lam = np.zeros(n_pts)
    boundaries = [T_MAX] + sorted(SPIKE_T, reverse=True) + [0.0]
    lam_right = 0.06
    for i in range(len(boundaries) - 1):
        seg_r, seg_l = boundaries[i], boundaries[i + 1]
        mask = (t >= seg_l) & (t <= seg_r)
        lam[mask] = lam_right * np.exp(base_decay * (seg_r - t[mask]))
        lam_right = lam_right * np.exp(base_decay * (seg_r - seg_l)) * jump_frac
    return t, lam


# ==========================================================================
def main():
    N = 46                                  # training steps
    loss_L, loss_R = make_losses(N)
    w_smooth, w_step = make_weights(N)
    t_adj, lam = build_adjoint()
    spikes = sorted(SPIKE_T)

    fig = plt.figure(figsize=(11, 6.6), dpi=125)
    fig.patch.set_facecolor(BG)

    # layout: HUD row (taller, to fit title + panel labels + numbers without
    # overlap) + two main columns (each with an upper mechanism axis and a
    # lower loss axis)
    gs = fig.add_gridspec(
        3, 2, height_ratios=[0.62, 1.5, 0.98], hspace=0.5, wspace=0.16,
        left=0.06, right=0.975, top=0.995, bottom=0.085,
    )

    # ---- HUD (spans both columns) ----------------------------------------
    ax_hud = fig.add_subplot(gs[0, :])
    ax_hud.axis("off")
    ax_hud.set_xlim(0, 1)
    ax_hud.set_ylim(0, 1)
    # big title on its own line at the very top
    ax_hud.text(0.5, 0.98, "addestrare = i pesi si muovono, la loss scende",
                ha="center", va="top", fontsize=13, color=TEXT, weight="bold")
    # panel labels below the title, well clear of it
    ax_hud.text(0.255, 0.52, "BPTT + surrogate", ha="center", va="center",
                fontsize=11.5, color=AMBER, weight="bold")
    ax_hud.text(0.755, 0.52, "EventProp (adjoint)", ha="center", va="center",
                fontsize=11.5, color=PURPLE, weight="bold")
    # live numbers below the panel labels
    hud_L = ax_hud.text(0.255, 0.12, "", ha="center", va="center",
                        fontsize=12, color=BALLCOL, family="monospace")
    hud_R = ax_hud.text(0.755, 0.12, "", ha="center", va="center",
                        fontsize=12, color=PURPLE, family="monospace")

    # =====================  LEFT  =====================
    # upper: gradient landscape (dead cliff + surrogate bell + rolling ball)
    axL = fig.add_subplot(gs[1, 0])
    axL.set_facecolor(BG)
    for s in ("top", "right"):
        axL.spines[s].set_visible(False)
    axL.set_xlim(-2.4, 2.4)
    axL.set_ylim(-0.05, 1.25)
    axL.set_xlabel(r"$V-\theta$", color=TEXT)
    axL.set_ylabel(r"$\partial S/\partial V$", color=TEXT)

    # Heaviside step dS/dV = delta(V-theta): draw as a DEAD flat line (0) with a
    # single spike-cliff at 0 -> "gradiente morto ovunque".
    axL.plot([-2.4, 0], [0, 0], color=DANGER, lw=2.6, zorder=3)
    axL.plot([0, 2.4], [0, 0], color=DANGER, lw=2.6, zorder=3)
    axL.annotate("", xy=(0, 1.12), xytext=(0, 0.0),
                 arrowprops=dict(arrowstyle="-", color=DANGER, lw=2.6))
    axL.text(-0.12, 0.62, r"$\delta(V-\theta)\approx 0$" + "\n(cliff morto)",
             color=DANGER, fontsize=9, va="center", ha="right")
    # surrogate bell bridging the cliff
    axL.plot(V, surrogate(V), color=AMBER, lw=2.8, zorder=4,
             label=r"surrogate $\dfrac{1}{(1+\gamma|V-\theta|)^2}$")
    axL.axvline(0, color=SPINE, lw=0.8, ls=":", zorder=1)
    axL.text(-2.3, 1.15, "salita levigata dal surrogato", color=AMBER,
             fontsize=9, va="top", ha="left", style="italic")
    axL.legend(loc="upper right", frameon=False, fontsize=8.5,
               labelcolor=TEXT)

    # rolling ball (rolls down the surrogate slope, right -> toward 0 peak)
    ball_x0, ball_x1 = 2.0, 0.18       # travels down the slope toward the peak
    (ball,) = axL.plot([], [], "o", color=BALLCOL, ms=15, zorder=8,
                       markeredgecolor="#1a1d22", markeredgewidth=1.2)
    ball_trail, = axL.plot([], [], color=BALLCOL, lw=1.4, alpha=0.35, zorder=6)

    # lower: LEFT loss curve (wobbles)
    axLb = fig.add_subplot(gs[2, 0])
    axLb.set_facecolor(BG)
    for s in ("top", "right"):
        axLb.spines[s].set_visible(False)
    axLb.set_xlim(0, N - 1)
    axLb.set_ylim(0, max(loss_L.max(), loss_R.max()) * 1.1)
    axLb.set_xlabel("passo di training", color=TEXT)
    axLb.set_ylabel("loss", color=TEXT)
    (lossL_line,) = axLb.plot([], [], color=AMBER, lw=2.4, zorder=5)
    (lossL_head,) = axLb.plot([], [], "o", color=AMBER, ms=6, zorder=6)
    axLb.text(0.97, 0.9, "scende ma WOBBLA (gradiente biased)", transform=axLb.transAxes,
              ha="right", va="top", fontsize=8.5, color=MUTED, style="italic")

    # =====================  RIGHT  =====================
    # upper: adjoint lambda(t) with exact jumps at spikes + spike train ticks
    axR = fig.add_subplot(gs[1, 1])
    axR.set_facecolor(BG)
    for s in ("top", "right"):
        axR.spines[s].set_visible(False)
    axR.set_xlim(0, T_MAX)
    axR.set_ylim(0, lam.max() * 1.18)
    axR.set_xlabel("tempo (indietro)  " + r"$\leftarrow$", color=TEXT)
    axR.set_ylabel(r"$\lambda(t)$", color=TEXT)
    # spike ticks
    for s in spikes:
        axR.axvline(s, color=GREEN, ls=":", lw=1.1, alpha=0.55, zorder=1)
        axR.plot([s], [lam.max() * 1.1], marker="|", color=GREEN, ms=12,
                 mew=2.2, zorder=4)
    axR.text(0.02, 0.985, "spike", transform=axR.transAxes, color=GREEN,
             fontsize=9, va="top", ha="left")
    (adj_line,) = axR.plot([], [], color=PURPLE, lw=2.7, zorder=5)
    jump_mk = axR.scatter([], [], color=PURPLE, s=70, marker="v", zorder=7,
                          edgecolor="#1a1d22", linewidths=0.8)
    # annotation placed in the empty lower-left region (curve lives upper/right)
    axR.text(0.03, 0.30, "salti ESATTI\nagli spike",
             transform=axR.transAxes, ha="left", va="center",
             fontsize=9.5, color=PURPLE, style="italic")

    # lower: RIGHT loss curve (cleaner)
    axRb = fig.add_subplot(gs[2, 1])
    axRb.set_facecolor(BG)
    for s in ("top", "right"):
        axRb.spines[s].set_visible(False)
    axRb.set_xlim(0, N - 1)
    axRb.set_ylim(0, max(loss_L.max(), loss_R.max()) * 1.1)
    axRb.set_xlabel("passo di training", color=TEXT)
    axRb.set_ylabel("loss", color=TEXT)
    (lossR_line,) = axRb.plot([], [], color=PURPLE, lw=2.4, zorder=5)
    (lossR_head,) = axRb.plot([], [], "o", color=PURPLE, ms=6, zorder=6)
    axRb.text(0.97, 0.9, "scende PULITA (gradiente esatto)", transform=axRb.transAxes,
              ha="right", va="top", fontsize=8.5, color=MUTED, style="italic")

    # small equation strip along the very bottom
    fig.text(0.06, 0.012,
             r"$w \leftarrow w - \eta\,\partial L/\partial w$", color=BALLCOL,
             fontsize=9.5, ha="left", va="bottom")
    fig.text(0.975, 0.012,
             r"$\Delta\lambda \propto (\partial L/\partial V)\,/\,(\mathrm{drive}-\theta)$",
             color=PURPLE, fontsize=9.5, ha="right", va="bottom")

    # ---- animation core --------------------------------------------------
    def render(step):
        """Draw the training state at integer `step` in [0, N-1]."""
        frac = step / (N - 1)

        # --- HUD numbers ---
        w_val = w_step[step]
        hud_L.set_text(f"w = {w_val:+.3f}    loss = {loss_L[step]:.3f}")
        hud_R.set_text(f"w = {w_val:+.3f}    loss = {loss_R[step]:.3f}")

        # --- LEFT: ball rolls down surrogate slope ---
        bx = ball_x0 + (ball_x1 - ball_x0) * frac
        by = surrogate(np.array([bx]))[0]
        ball.set_data([bx], [by])
        # trail from start to current
        tx = np.linspace(ball_x0, bx, 30)
        ball_trail.set_data(tx, surrogate(tx))

        # --- LEFT loss (revealed up to step, wobbly) ---
        xs = np.arange(step + 1)
        lossL_line.set_data(xs, loss_L[: step + 1])
        lossL_head.set_data([step], [loss_L[step]])

        # --- RIGHT: adjoint revealed backward in time (right -> left) ---
        reveal_t = T_MAX * (1 - frac)
        mask = t_adj >= reveal_t
        adj_line.set_data(t_adj[mask], lam[mask])
        revealed = [s for s in spikes if s >= reveal_t]
        if revealed:
            jx = revealed
            jy = [lam[min(np.searchsorted(t_adj, s), len(lam) - 1)] for s in revealed]
            jump_mk.set_offsets(np.c_[jx, jy])
        else:
            jump_mk.set_offsets(np.empty((0, 2)))

        # --- RIGHT loss (revealed up to step, clean) ---
        lossR_line.set_data(xs, loss_R[: step + 1])
        lossR_head.set_data([step], [loss_R[step]])

        return [ball, ball_trail, lossL_line, lossL_head, adj_line, jump_mk,
                lossR_line, lossR_head, hud_L, hud_R]

    # POSTER-FIRST: frame 0 is a meaningful mid-training pose.
    POSTER = int(N * 0.5)
    build = list(range(N))
    frames = [POSTER] * 8 + build + [N - 1] * 16

    def frame(idx):
        return render(frames[idx])

    anim = FuncAnimation(fig, frame, frames=len(frames), interval=62, blit=True)
    out = OUT / "training.gif"
    anim.save(out, writer=PillowWriter(fps=15),
              savefig_kwargs={"facecolor": BG})
    print("OK", out)


if __name__ == "__main__":
    main()
