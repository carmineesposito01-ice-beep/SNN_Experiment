"""Hero #1: dinamica LIF (secchio che perde) -> GIF. matplotlib + Pillow, niente manim/ffmpeg."""
import pathlib, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

OUT = pathlib.Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/assets/manim"
OUT.mkdir(parents=True, exist_ok=True)

def simulate(T=120, thr=1.0, leak=0.875, drive=0.35):
    V, out = 0.0, []
    for t in range(T):
        V = leak * V + drive
        spike = V >= thr
        if spike: V -= thr
        out.append((V + (thr if spike else 0), spike))
    return out

def main():
    data = simulate()
    xs = list(range(len(data)))
    fig, ax = plt.subplots(figsize=(10, 5), dpi=130)
    ax.axhline(1.0, color="#D55E00", linestyle="--", label="soglia")
    (line,) = ax.plot([], [], color="#0072B2", lw=2.5, label="potenziale V")
    spikes = ax.scatter([], [], color="#009E73", s=80, zorder=5, label="spike")
    ax.set_xlim(0, len(data)); ax.set_ylim(0, 1.4)
    ax.set_xlabel("tempo (tick)"); ax.set_ylabel("potenziale di membrana")
    ax.set_title("Il neurone LIF: un secchio che perde"); ax.legend(loc="upper right", frameon=False)
    for s in ("top", "right"): ax.spines[s].set_visible(False)

    def frame(i):
        line.set_data(xs[:i + 1], [d[0] for d in data[:i + 1]])
        sx = [x for x, d in zip(xs[:i + 1], data[:i + 1]) if d[1]]
        sy = [1.05 for _ in sx]
        spikes.set_offsets(np.c_[sx, sy] if sx else np.empty((0, 2)))
        return line, spikes

    anim = FuncAnimation(fig, frame, frames=len(data), interval=50, blit=True)
    anim.save(OUT / "lif_spike.gif", writer=PillowWriter(fps=20))
    print("OK", OUT / "lif_spike.gif")

if __name__ == "__main__":
    main()
