"""FPGA & energy DARK figures for the CF_FSNN dark-theme deck.

Five diverse, projector-legible figures (dumbbell / curves / radar / heatmap /
scatter) — deliberately NOT vertical bar charts. Each figure carries a single
message and a short on-plot takeaway; slide supplies the title.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "_shared"))
import figures_common_dark as fc  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)

# Champions present in the FPGA/energy CSVs (no Oracolo here), plot order.
CHAMPIONS = ["Raffaello", "Leonardo", "Donatello", "Michelangelo"]


# --------------------------------------------------------------------------- #
# 1. Energy: SNN vs dense-ANN — horizontal dumbbell with advantage annotated
# --------------------------------------------------------------------------- #
def fig_energy_ann():
    df = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/08_Energy_Spiking/energy.csv")
    df = df.set_index("champion").loc[CHAMPIONS].reset_index()

    fc.apply_dark_style()
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    y = np.arange(len(df))[::-1]  # top champion at top

    for yi, row in zip(y, df.itertuples()):
        st = fc.champion_style(row.champion)
        # connector
        ax.plot([row.E_snn_nJ, row.E_ann_nJ], [yi, yi],
                color=fc.SPINE, lw=3, zorder=1, solid_capstyle="round")
        # ANN endpoint (dense baseline) — hollow danger
        ax.scatter(row.E_ann_nJ, yi, s=150, facecolor=fc.BG,
                   edgecolor=fc.DANGER, linewidth=2.4, zorder=3)
        # SNN endpoint — champion colour, filled
        ax.scatter(row.E_snn_nJ, yi, s=150, color=st["color"],
                   edgecolor=fc.BG, linewidth=1.0, zorder=4)
        # advantage annotation at the midpoint, above the bar
        xm = (row.E_snn_nJ + row.E_ann_nJ) / 2
        ax.annotate(f"{row.advantage_x:.1f}×", (xm, yi),
                    xytext=(0, 9), textcoords="offset points",
                    ha="center", va="bottom", color=st["color"],
                    fontsize=13, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels([fc.champion_style(c)["label"] for c in df["champion"]])
    ax.set_xlabel("Energia per inferenza  (nJ)")
    ax.set_xlim(0, df["E_ann_nJ"].max() * 1.12)
    ax.grid(axis="y", visible=False)

    legend_elems = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=fc.INK,
               markeredgecolor=fc.BG, markersize=11, label="SNN (nostra)"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=fc.BG,
               markeredgecolor=fc.DANGER, markeredgewidth=2.2, markersize=11,
               label="ANN densa (baseline)"),
    ]
    ax.legend(handles=legend_elems, loc="upper right", facecolor=fc.BG,
              edgecolor=fc.SPINE, labelcolor=fc.INK, framealpha=0.9)

    ax.text(0.02, 1.02,
            "Il vantaggio viene da AC<MAC + 0 DSP, non dalla sparsità (~13–19%)",
            transform=ax.transAxes, ha="left", va="bottom",
            color=fc.INK_MUTED, fontsize=11, style="italic")

    fig.savefig(OUT / "energy_ann.png")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 2. Quantization: id_err vs frac_bits — curves per champion, fixed vs po2
# --------------------------------------------------------------------------- #
def fig_quant():
    df = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/05_Quantization/quantization.csv")

    # x-axis order: float (highest precision) then 12..2. Map to evenly spaced x.
    order = ["float", "12", "8", "6", "4", "3", "2"]
    xpos = {b: i for i, b in enumerate(order)}

    fc.apply_dark_style()
    fig, ax = plt.subplots(figsize=(7.6, 4.6))

    for champ in CHAMPIONS:
        st = fc.champion_style(champ)
        sub = df[df["champion"] == champ]
        for mode, ls, fillstyle in (("fixed", "-", "full"), ("po2", "--", "none")):
            m = sub[sub["mode"] == mode].copy()
            m["x"] = m["frac_bits"].map(xpos)
            m = m.sort_values("x")
            ax.plot(m["x"], m["id_err_mean"], color=st["color"], linestyle=ls,
                    marker=st["marker"], markersize=8, fillstyle=fillstyle,
                    markeredgecolor=st["color"], linewidth=2.2,
                    label=f"{champ} · {mode}")

    ax.set_xticks(list(xpos.values()))
    ax.set_xticklabels(order)
    ax.set_xlabel("Bit frazionari  (float → 2 bit)")
    ax.set_ylabel("Errore identificazione  (id_err)")

    # takeaway: fixed-point stays flat down to ~2 bit
    ax.text(0.02, 1.02,
            "Fixed-point piatto fino a ~2 bit; PO2 degrada oltre float",
            transform=ax.transAxes, ha="left", va="bottom",
            color=fc.INK_MUTED, fontsize=11, style="italic")

    # compact custom legend: champions (colour) + line-style meaning
    champ_handles = [Line2D([0], [0], color=fc.champion_style(c)["color"],
                            marker=fc.champion_style(c)["marker"], linestyle="-",
                            markersize=8, label=c) for c in CHAMPIONS]
    style_handles = [
        Line2D([0], [0], color=fc.INK, linestyle="-", label="fixed"),
        Line2D([0], [0], color=fc.INK, linestyle="--", label="po2"),
    ]
    leg1 = ax.legend(handles=champ_handles, loc="upper left",
                     bbox_to_anchor=(0.0, 0.98), facecolor=fc.BG,
                     edgecolor=fc.SPINE, labelcolor=fc.INK, framealpha=0.9,
                     fontsize=11)
    ax.add_artist(leg1)
    ax.legend(handles=style_handles, loc="lower left", facecolor=fc.BG,
              edgecolor=fc.SPINE, labelcolor=fc.INK, framealpha=0.9, fontsize=11)

    fig.savefig(OUT / "quant.png")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 3. Readiness: 2x2 small-multiple radars, 6 axes, filled in champion colour
# --------------------------------------------------------------------------- #
def fig_readiness_radar():
    df = fc.load_csv(REPO, "results/evaluate/FPGA/00_Readiness/scorecard.csv")
    df = df.set_index("champion")

    axes_labels = ["ρ<1", "Fix-pt", "Sparsità", "Energia", "Timing", "SEU"]
    n = len(axes_labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]  # close the loop

    fc.apply_dark_style()
    fig, axs = plt.subplots(2, 2, figsize=(7.8, 7.4),
                            subplot_kw=dict(polar=True))
    axs = axs.ravel()

    for ax, champ in zip(axs, CHAMPIONS):
        st = fc.champion_style(champ)
        vals = [float(df.loc[champ, lbl]) for lbl in axes_labels]
        vals += vals[:1]

        ax.plot(angles, vals, color=st["color"], linewidth=2.2)
        ax.fill(angles, vals, color=st["color"], alpha=0.28)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(axes_labels, fontsize=10, color=fc.INK)
        ax.set_ylim(0, 1)
        ax.set_yticks([0.25, 0.5, 0.75, 1.0])
        ax.set_yticklabels(["", "0.5", "", "1"], fontsize=8, color=fc.INK_MUTED)
        ax.set_facecolor(fc.BG)
        ax.grid(color=fc.GRID, alpha=0.7)
        ax.spines["polar"].set_color(fc.SPINE)
        ax.set_title(st["label"], color=st["color"], fontsize=13, pad=12)
        # nudge radial tick labels off the vertical axis
        ax.set_rlabel_position(15)

    fig.text(0.5, 0.005,
             "6 assi di readiness FPGA (0–1); Donatello domina ρ<1 e Fix-pt",
             ha="center", va="bottom", color=fc.INK_MUTED, fontsize=11,
             style="italic")
    fig.subplots_adjust(hspace=0.45, wspace=0.35, bottom=0.07, top=0.92)
    fig.savefig(OUT / "readiness_radar.png")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 4. SEU: heatmap champions x bit-positions (exp_LSB/mid/MSB)
# --------------------------------------------------------------------------- #
def fig_seu():
    df = fc.load_csv(REPO, "results/evaluate/FPGA/07_SEU_ISO26262/seu_sensitivity.csv")
    df = df.set_index("champion").loc[CHAMPIONS]

    cols = ["exp_LSB", "exp_mid", "exp_MSB"]
    col_labels = ["LSB", "mid", "MSB"]
    mat = df[cols].to_numpy(dtype=float)

    fc.apply_dark_style()
    fig, ax = plt.subplots(figsize=(6.6, 4.6))

    # perceptually-safe: dark BG -> danger for high criticality
    cmap = plt.colormaps["inferno"]
    im = ax.imshow(mat, aspect="auto", cmap=cmap, vmin=0, vmax=mat.max())

    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels)
    ax.set_yticks(range(len(CHAMPIONS)))
    ax.set_yticklabels([fc.champion_style(c)["label"] for c in CHAMPIONS])
    ax.set_xlabel("Posizione del bit colpito (SEU)")
    ax.grid(False)

    # annotate each cell with the value; contrast text by cell luminance
    thr = mat.max() * 0.55
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            ax.text(j, i, f"{v*100:.2f}%", ha="center", va="center",
                    color="#15181D" if v > thr else "#EAF1F7",
                    fontsize=11, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cbar.set_label("Δ criticità (id_err)", color=fc.INK, fontsize=11)
    cbar.ax.yaxis.set_tick_params(color=fc.INK)
    plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color=fc.INK)
    cbar.outline.set_edgecolor(fc.SPINE)

    ax.text(0.0, 1.04,
            "Il bit MSB domina; Leonardo il più fragile (0.42%)",
            transform=ax.transAxes, ha="left", va="bottom",
            color=fc.INK_MUTED, fontsize=11, style="italic")

    fig.savefig(OUT / "seu.png")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# 5. Spike health: scatter spike-rate % vs dead-neuron %, sized by rho
# --------------------------------------------------------------------------- #
def fig_spike_health():
    df = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/08_Energy_Spiking/energy.csv")
    df = df.set_index("champion").loc[CHAMPIONS].reset_index()

    fc.apply_dark_style()
    fig, ax = plt.subplots(figsize=(7.6, 4.6))

    # per-champion label offsets (pts) so overlapping BPTT points don't collide
    rho_offset = {
        "Raffaello": (12, 8), "Leonardo": (12, -12),
        "Donatello": (-12, 10), "Michelangelo": (12, 8),
    }
    for row in df.itertuples():
        st = fc.champion_style(row.champion)
        dead_pct = row.dead_frac * 100.0
        ax.scatter(row.mean_spike_rate_pct, dead_pct, s=340,
                   color=st["color"], marker=st["marker"],
                   edgecolor=fc.BG, linewidth=1.2, zorder=3,
                   label=st["label"])
        # annotate spectral radius rho next to each point
        dx, dy = rho_offset[row.champion]
        ax.annotate(f"ρ={row.spectral_radius:.2f}",
                    (row.mean_spike_rate_pct, dead_pct),
                    xytext=(dx, dy), textcoords="offset points",
                    color=st["color"], fontsize=10,
                    ha="left" if dx > 0 else "right", va="center")

    # highlight the two behavioural clusters
    ax.axhspan(-1.5, 3, color=fc.SAFE, alpha=0.08, zorder=0)
    ax.text(df["mean_spike_rate_pct"].min() + 1.2, 4.0,
            "EventProp: 0% neuroni morti",
            ha="left", va="bottom", color=fc.SAFE, fontsize=11)
    ax.text(df["mean_spike_rate_pct"].min() - 0.15, 27.5,
            "BPTT: ~31% morti",
            ha="left", va="top", color=fc.DANGER, fontsize=11)

    ax.set_xlabel("Spike-rate medio  (%)")
    ax.set_ylabel("Neuroni morti  (%)")
    ax.set_ylim(-1.5, df["dead_frac"].max() * 100 + 5)
    ax.set_xlim(df["mean_spike_rate_pct"].min() - 0.9,
                df["mean_spike_rate_pct"].max() + 0.7)
    fc.style_legend(ax, loc="center right")

    ax.text(0.02, 1.02,
            "Marker = ρ (raggio spettrale); EventProp usa più spike ma 0 neuroni morti",
            transform=ax.transAxes, ha="left", va="bottom",
            color=fc.INK_MUTED, fontsize=11, style="italic")

    fig.savefig(OUT / "spike_health.png")
    plt.close(fig)


FIGS = [fig_energy_ann, fig_quant, fig_readiness_radar, fig_seu, fig_spike_health]


def main():
    for f in FIGS:
        f()
        print("OK", f.__name__)


if __name__ == "__main__":
    main()
