"""Hero #2: EventProp forward (spike train) + adjoint (salti solo agli spike) -> GIF.
matplotlib + Pillow, niente manim/ffmpeg. Reveal da destra a sinistra (propagazione all'indietro)."""
import pathlib, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

OUT = pathlib.Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/assets/manim"
OUT.mkdir(parents=True, exist_ok=True)

SPIKE_COLOR = "#009E73"
ADJOINT_COLOR = "#CC79A7"
JUMP_COLOR = "#D55E00"

T_MAX = 10.0
SPIKE_TIMES = [1.2, 2.8, 4.5, 5.7, 7.6, 8.8]  # ~5-6 spike-time istanti (hardcoded, chiari da leggere)


def build_adjoint(n_pts=2000, t_max=T_MAX, spike_times=SPIKE_TIMES, base_decay=0.55, jump_frac=0.6):
    """Costruisce lambda(t): PIECEWISE liscia tra gli spike, con un salto (discontinuita')
    esattamente in corrispondenza di ogni spike-time. L'adjoint si propaga all'indietro nel
    tempo (da t_max verso 0): parte da un valore piccolo a destra e CRESCE andando a sinistra,
    con un salto verso il basso ad ogni istante di spike attraversato (stile del reference
    plot statico eventprop.png: sawtooth che sale tra i salti, poi crolla allo spike)."""
    t = np.linspace(0, t_max, n_pts)
    lam = np.zeros(n_pts)

    # Confini dei segmenti piecewise: [0, s1, s2, ..., sk, t_max], integrazione da destra a sinistra.
    boundaries = [t_max] + sorted(spike_times, reverse=True) + [0.0]
    lam_at_right = 0.05  # valore di partenza a t_max (adjoint terminale piccolo)

    for seg_idx in range(len(boundaries) - 1):
        seg_right = boundaries[seg_idx]
        seg_left = boundaries[seg_idx + 1]
        mask = (t >= seg_left) & (t <= seg_right)
        # Dentro il segmento, integrando all'indietro (da destra verso sinistra) l'adjoint
        # CRESCE esponenzialmente man mano che ci si allontana dal bordo destro del segmento.
        local_t = seg_right - t[mask]
        lam[mask] = lam_at_right * np.exp(base_decay * local_t)
        # Valore raggiunto al bordo sinistro del segmento (prima del salto).
        seg_len = seg_right - seg_left
        lam_left_pre_jump = lam_at_right * np.exp(base_decay * seg_len)
        # Il prossimo segmento (a sinistra) riparte da un valore ridotto: il SALTO allo spike-time.
        lam_at_right = lam_left_pre_jump * jump_frac

    return t, lam


def main():
    t, lam = build_adjoint()
    spike_times = sorted(SPIKE_TIMES)

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(10, 6), dpi=130, sharex=True,
        gridspec_kw={"height_ratios": [1, 2.2]},
    )
    fig.suptitle("EventProp: gradiente esatto, propagato all'indietro nel tempo", fontsize=13)

    # --- Pannello superiore: treno di spike (forward) ---
    ax_top.set_title("forward: la rete spara", fontsize=11, loc="left", color="#333333")
    ax_top.set_xlim(0, T_MAX)
    ax_top.set_ylim(0, 1.2)
    ax_top.set_yticks([])
    for s in ("top", "right", "left"):
        ax_top.spines[s].set_visible(False)
    spike_lines = []
    for s in spike_times:
        (ln,) = ax_top.plot([s, s], [0, 1.0], color=SPIKE_COLOR, lw=2.5, alpha=0.0, zorder=5)
        spike_lines.append(ln)
    ax_top.axhline(0, color="#999999", lw=0.8)

    # --- Pannello inferiore: adjoint lambda(t) ---
    ax_bot.set_title("adjoint: salta SOLO agli istanti di spike", fontsize=11, loc="left", color="#333333")
    ax_bot.set_xlim(0, T_MAX)
    ax_bot.set_ylim(0, lam.max() * 1.15)
    ax_bot.set_xlabel("tempo")
    ax_bot.set_ylabel(r"$\lambda(t)$")
    for s in ("top", "right"):
        ax_bot.spines[s].set_visible(False)
    (adj_line,) = ax_bot.plot([], [], color=ADJOINT_COLOR, lw=2.5, zorder=4, label=r"adjoint $\lambda(t)$ (all'indietro)")
    jump_markers = ax_bot.scatter([], [], color=JUMP_COLOR, s=60, zorder=6, marker="v", label="salto allo spike-time")
    for s in spike_times:
        ax_bot.axvline(s, color=SPIKE_COLOR, linestyle=":", lw=1.2, alpha=0.5)
    ax_bot.legend(loc="upper right", frameon=False, fontsize=9)
    caption = ax_bot.text(
        0.02, 0.92, "gradiente esatto, costo O(#spike)",
        transform=ax_bot.transAxes, fontsize=10, color="#555555",
        style="italic", ha="left", va="top",
    )
    caption.set_alpha(0.0)

    n_frames = 150

    def frame(i):
        # Reveal da DESTRA a SINISTRA: la soglia di rivelazione parte da T_MAX e scende a 0.
        progress = i / (n_frames - 1)
        reveal_t = T_MAX * (1 - progress)

        # Adjoint: mostra solo la porzione con t >= reveal_t (curva "appare" da destra).
        mask = t >= reveal_t
        adj_line.set_data(t[mask], lam[mask])

        # Spike lines nel pannello top: appaiono quando il reveal le raggiunge (da destra).
        for s, ln in zip(spike_times, spike_lines):
            ln.set_alpha(1.0 if s >= reveal_t else 0.0)

        # Jump markers: mostra un triangolino sul salto per ogni spike gia' rivelato.
        revealed_spikes = [s for s in spike_times if s >= reveal_t]
        if revealed_spikes:
            jx, jy = [], []
            for s in revealed_spikes:
                idx = np.searchsorted(t, s)
                idx = min(idx, len(lam) - 1)
                jx.append(s)
                jy.append(lam[idx])
            jump_markers.set_offsets(np.c_[jx, jy])
        else:
            jump_markers.set_offsets(np.empty((0, 2)))

        # Caption compare verso la fine dell'animazione.
        caption.set_alpha(min(1.0, max(0.0, (progress - 0.7) / 0.3)))

        return [adj_line, jump_markers, caption] + spike_lines

    anim = FuncAnimation(fig, frame, frames=n_frames, interval=60, blit=True)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    anim.save(OUT / "eventprop_adjoint.gif", writer=PillowWriter(fps=18))
    print("OK", OUT / "eventprop_adjoint.gif")


if __name__ == "__main__":
    main()
