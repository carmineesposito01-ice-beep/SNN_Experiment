"""ALIF fatigue (dark theme) -> GIF. matplotlib + Pillow, no manim/ffmpeg."""
import pathlib, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

OUT = pathlib.Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/_proto/assets"
OUT.mkdir(parents=True, exist_ok=True)

BG = "#15181D"; MEM = "#56B4E9"; SPK = "#2ECC71"; THR = "#F0B429"; TXT = "#8A939D"


def simulate(T=140, base=1.0, jump=0.45, leak=0.875, fleak=0.965, drive=0.34):
    V = 0.0; fat = 0.0; mem = []; thr = []; spikes = []
    for t in range(T):
        theta = base + max(0.0, fat)
        V = leak * V + drive
        s = V >= theta
        mem.append(V + (theta if s else 0.0))  # show pre-reset peak touching threshold
        thr.append(theta)
        if s:
            spikes.append(t)
            V -= theta
        fat = fleak * fat + (jump if s else 0.0)
    return mem, thr, spikes


def main():
    mem, thr, spikes = simulate()
    T = len(mem); xs = np.arange(T)
    fig, ax = plt.subplots(figsize=(6.2, 3.4), dpi=150)
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    for sp in ax.spines.values():
        sp.set_color("#39424D")
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    ax.tick_params(colors=TXT, labelsize=8)
    ax.set_xlim(0, T); ax.set_ylim(0, max(thr) + 0.6)
    ax.set_xlabel("tempo (tick)", color=TXT, fontsize=9)
    ax.set_ylabel("potenziale V", color=TXT, fontsize=9)
    (lmem,) = ax.plot([], [], color=MEM, lw=2.2, label="V(t)")
    (lthr,) = ax.plot([], [], color=THR, lw=1.8, ls="--", label="soglia θ_eff")
    scat = ax.scatter([], [], color=SPK, s=55, zorder=5, label="spike")
    ax.legend(loc="upper right", fontsize=8, facecolor=BG, edgecolor="#39424D", labelcolor=TXT)

    def frame(i):
        k = i + 1
        lmem.set_data(xs[:k], mem[:k])
        lthr.set_data(xs[:k], thr[:k])
        sx = [s for s in spikes if s < k]; sy = [thr[s] for s in sx]
        scat.set_offsets(np.c_[sx, sy] if sx else np.empty((0, 2)))
        return lmem, lthr, scat

    # poster-first: frame 0 = the full trace (good static still / PDF fallback),
    # then replay the build-up, then hold.
    frames = [T - 1] * 8 + list(range(T)) + [T - 1] * 16
    anim = FuncAnimation(fig, frame, frames=frames, interval=55, blit=True)
    anim.save(OUT / "alif_fatigue_dark.gif", writer=PillowWriter(fps=18),
              savefig_kwargs={"facecolor": BG})
    print("OK", OUT / "alif_fatigue_dark.gif")


if __name__ == "__main__":
    main()
