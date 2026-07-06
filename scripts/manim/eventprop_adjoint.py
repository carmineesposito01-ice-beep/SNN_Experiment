"""eventprop_adjoint.gif — EventProp: exact gradient via an adjoint integrated BACKWARD in time.

Answers the natural question "why is the plot traversed right-to-left?": because the adjoint
variable lambda(t) is initialized at the final time T (from the loss) and integrated BACKWARD in
time (T -> 0) — the continuous analog of backprop. Crucially it JUMPS only at spike times
(event-driven), leaking smoothly between them, so its cost is O(#spikes), not O(T).
Dark theme to match the deck. Deterministic (fixed spike times; no RNG).
matplotlib + Pillow, no manim/ffmpeg.
"""
import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

OUT = pathlib.Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/assets/manim"
OUT.mkdir(parents=True, exist_ok=True)

BG="#15181D"; TEXT="#DCE3EA"; MUTED="#8A939D"; EDGE="#39424D"
GREEN="#2ECC71"; ADJ="#D48AC0"; JUMP="#F0B429"

T_MAX = 10.0
SPIKE_TIMES = [1.2, 2.8, 4.5, 5.7, 7.6, 8.8]


def build_adjoint(n_pts=2000, t_max=T_MAX, spikes=SPIKE_TIMES, decay=0.55, jump_frac=0.6):
    """lambda(t): smooth (leaky) between spikes, with a downward jump exactly at each spike-time.
    Built by integrating from t_max toward 0 (backward in time)."""
    t = np.linspace(0, t_max, n_pts); lam = np.zeros(n_pts)
    bounds = [t_max] + sorted(spikes, reverse=True) + [0.0]
    lam_right = 0.05
    for k in range(len(bounds)-1):
        r, l = bounds[k], bounds[k+1]
        m = (t >= l) & (t <= r)
        lam[m] = lam_right * np.exp(decay * (r - t[m]))
        lam_right = lam_right * np.exp(decay * (r - l)) * jump_frac
    return t, lam


def main():
    t, lam = build_adjoint(); spikes = sorted(SPIKE_TIMES)
    fig, (axt, axb) = plt.subplots(2, 1, figsize=(7.6, 4.3), dpi=150, sharex=True,
                                   gridspec_kw={"height_ratios": [1, 2.0]})
    fig.patch.set_facecolor(BG)
    fig.suptitle("EventProp: gradiente esatto, integrato all'indietro nel tempo",
                 fontsize=13.5, color=TEXT, fontweight="bold", y=0.99)
    for a in (axt, axb):
        a.set_facecolor(BG)
        for s in a.spines.values(): s.set_color(EDGE)
        a.tick_params(colors=MUTED, labelsize=8)

    # top: forward spike train
    axt.set_title("forward: la rete spara", fontsize=10.5, loc="left", color=MUTED)
    axt.set_xlim(0, T_MAX); axt.set_ylim(0, 1.25); axt.set_yticks([])
    for s in ("top","right","left"): axt.spines[s].set_visible(False)
    spike_lines = [axt.plot([s,s],[0,1.0], color=GREEN, lw=2.6, alpha=0.0)[0] for s in spikes]
    axt.axhline(0, color=EDGE, lw=0.8)

    # bottom: adjoint lambda(t)
    axb.set_title(r"adjoint $\lambda(t)$: salta SOLO agli spike (costo $\propto$ #spike)",
                  fontsize=10.5, loc="left", color=MUTED)
    axb.set_xlim(0, T_MAX); axb.set_ylim(0, lam.max()*1.18)
    axb.set_xlabel("tempo", color=MUTED); axb.set_ylabel(r"$\lambda(t)$", color=TEXT)
    for s in ("top","right"): axb.spines[s].set_visible(False)
    for s in spikes: axb.axvline(s, color=GREEN, ls=":", lw=1.1, alpha=0.4)
    (adj_line,) = axb.plot([], [], color=ADJ, lw=2.8, zorder=4)
    jumps = axb.scatter([], [], color=JUMP, s=70, zorder=6, marker="v")

    # explicit backward-direction indicator (answers "why right-to-left?")
    axb.annotate("", xy=(0.6, lam.max()*1.05), xytext=(T_MAX-0.6, lam.max()*1.05),
                 arrowprops=dict(arrowstyle="-|>", color=ADJ, lw=2.2))
    axb.text(T_MAX/2, lam.max()*1.12, "integrazione all'indietro:  da  T  →  0",
             ha="center", va="bottom", color=ADJ, fontsize=10.5, fontweight="bold")

    N = 150
    def frame(i):
        reveal = T_MAX * (1 - i/(N-1))          # threshold sweeps T -> 0 (backward)
        m = t >= reveal
        adj_line.set_data(t[m], lam[m])
        for s, ln in zip(spikes, spike_lines):
            ln.set_alpha(1.0 if s >= reveal else 0.0)
        rs = [s for s in spikes if s >= reveal]
        if rs:
            jy = [lam[min(np.searchsorted(t, s), len(lam)-1)] for s in rs]
            jumps.set_offsets(np.c_[rs, jy])
        else:
            jumps.set_offsets(np.empty((0, 2)))
        return [adj_line, jumps] + spike_lines

    anim = FuncAnimation(fig, frame, frames=N, interval=60, blit=True)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    anim.save(OUT / "eventprop_adjoint.gif", writer=PillowWriter(fps=18))
    print("OK", OUT / "eventprop_adjoint.gif")


if __name__ == "__main__":
    main()
