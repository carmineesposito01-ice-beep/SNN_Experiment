"""Dark data figures — identification & safety block (CF_FSNN thesis deck).

Each figure is a distinct visual form (heatmap / scatter-frontier / lollipop /
info-panel) tied to one message. No titles (the slide supplies them); axes are
labelled and a short on-plot takeaway is added where it helps.
Shared dark style: presentation/_shared/figures_common_dark.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "_shared"))
import figures_common_dark as fc
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent / "figures"; OUT.mkdir(exist_ok=True)

CHAMPIONS = ["Raffaello", "Leonardo", "Donatello", "Michelangelo"]
PARAMS = ["v0", "T", "s0", "a", "b"]
PARAM_LABELS = [r"$v_0$", r"$T$", r"$s_0$", r"$a$", r"$b$"]

# Dark sequential ramp: low NRMSE (good) = near-panel dark, high (bad) = warm.
_SEQ = LinearSegmentedColormap.from_list(
    "cf_dark_seq", ["#1A2733", "#1F5C6E", "#3E9B8A", "#C9A227", "#E0563B"])


def fig_accuracy_heatmap():
    """Per-parameter reconstruction error, 4 champions x 5 params. Lower=better."""
    df = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/01_Accuracy/accuracy.csv")
    df = df.set_index("champion").loc[CHAMPIONS]
    M = df[[f"nrmse_{p}" for p in PARAMS]].to_numpy()

    fc.apply_dark_style()
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    im = ax.imshow(M, cmap=_SEQ, aspect="auto", vmin=0.0, vmax=0.55)

    ax.set_xticks(range(len(PARAMS)), PARAM_LABELS)
    ax.set_yticks(range(len(CHAMPIONS)), CHAMPIONS)
    ax.set_xlabel("parametro CF stimato")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="#0E1216" if v > 0.30 else "#EAF1F7",
                    fontsize=12, fontweight="bold")
    # accuracy_pct annotation on the right margin
    for i, ch in enumerate(CHAMPIONS):
        ax.text(len(PARAMS) - 0.35, i, f"{df.loc[ch,'accuracy_pct']:.0f}%",
                ha="left", va="center", color=fc.SAFE, fontsize=11,
                fontweight="bold", transform=ax.transData)
    ax.text(len(PARAMS) - 0.35, -0.75, "acc.", ha="left", va="center",
            color=fc.INK_MUTED, fontsize=10)

    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.12)
    cb.set_label("NRMSE (scuro=meglio)", color=fc.INK, fontsize=12)
    cb.ax.tick_params(colors=fc.INK)
    cb.outline.set_edgecolor(fc.SPINE)
    ax.text(-0.02, -0.62, r"$s_0$ ovunque il piu facile · $v_0$ il piu ostico",
            transform=ax.transAxes, color=fc.INK_MUTED, fontsize=11)
    fig.savefig(OUT / "accuracy_heatmap.png")
    plt.close(fig)


def fig_nrmse_stratified():
    """param x scenario-family heatmap, averaged over champions.
    Dark cell = param NOT observable in that scenario (high NRMSE)."""
    df = fc.load_csv(REPO,
        "results/evaluate/v3_TURTLE_POWER!!!/04_Identifiability/nrmse_stratified.csv")
    scenarios = list(dict.fromkeys(df["scenario"]))  # preserve order
    # mean over the 4 champions -> param x scenario matrix
    piv = df.groupby("scenario")[[f"nrmse_{p}" for p in PARAMS]].mean()
    piv = piv.loc[scenarios]
    M = piv.to_numpy().T  # rows=params, cols=scenarios

    fc.apply_dark_style()
    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    # Here HIGH NRMSE = "not observable" -> we want that to read as the dark end.
    # Invert: dark = high error (unobservable), bright = low error (observable).
    seq = LinearSegmentedColormap.from_list(
        "cf_obs", ["#E0563B", "#C9A227", "#3E9B8A", "#1F5C6E", "#141A20"])
    im = ax.imshow(M, cmap=seq, aspect="auto", vmin=0.05, vmax=0.45)

    ax.set_yticks(range(len(PARAMS)), PARAM_LABELS)
    ax.set_xticks(range(len(scenarios)), scenarios, rotation=20, ha="right")
    ax.set_xlabel("famiglia di scenario")
    ax.set_ylabel("parametro")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                    color="#EAF1F7" if v > 0.34 else "#0E1216",
                    fontsize=11, fontweight="bold")
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
    cb.set_label("NRMSE (scuro=non osserv.)", color=fc.INK, fontsize=12)
    cb.ax.tick_params(colors=fc.INK)
    cb.outline.set_edgecolor(fc.SPINE)
    ax.text(0.0, 1.06, r"$s_0$ osservabile ovunque · $v_0$ dipende dallo scenario",
            transform=ax.transAxes, color=fc.INK_MUTED, fontsize=11)
    fig.savefig(OUT / "nrmse_stratified.png")
    plt.close(fig)


def fig_discriminant():
    """Frontier scatter: spectral radius rho(U.V) [x, log] vs accuracy [y].
    Marker area ~ energy advantage_x. Green span marks the stable rho<1 zone."""
    en = fc.load_csv(REPO,
        "results/evaluate/v3_TURTLE_POWER!!!/08_Energy_Spiking/energy.csv")
    ac = fc.load_csv(REPO,
        "results/evaluate/v3_TURTLE_POWER!!!/01_Accuracy/accuracy.csv")
    df = en.merge(ac[["champion", "accuracy_pct"]], on="champion")

    fc.apply_dark_style()
    fig, ax = plt.subplots(figsize=(7.6, 4.4))

    # stable contraction zone rho<1
    ax.axvspan(1e-2, 1.0, color=fc.SAFE, alpha=0.12, zorder=0)
    ax.axvline(1.0, color=fc.SAFE, linestyle="--", linewidth=1.6, alpha=0.8, zorder=1)
    ax.text(0.92, 71.0, "rho < 1\ncontrattivo", color=fc.SAFE, fontsize=11,
            ha="right", va="bottom", fontweight="bold")
    ax.text(1.08, 71.0, "rho > 1\nespansivo", color=fc.DANGER, fontsize=11,
            ha="left", va="bottom", fontweight="bold")

    for _, r in df.iterrows():
        st = fc.champion_style(r["champion"])
        size = 60 + (r["advantage_x"] ** 2) * 22  # area ~ advantage
        ax.scatter(r["spectral_radius"], r["accuracy_pct"], s=size,
                   color=st["color"], marker=st["marker"], edgecolor="#0E1216",
                   linewidth=1.3, alpha=0.92, zorder=3, label=st["label"])
        ax.annotate(r["champion"], (r["spectral_radius"], r["accuracy_pct"]),
                    textcoords="offset points", xytext=(0, 13), ha="center",
                    color=fc.INK, fontsize=10)

    ax.set_xscale("log")
    ax.set_xlim(0.03, 4.0)
    ax.set_ylim(66, 88)
    ax.set_xlabel(r"raggio spettrale  $\rho(U\cdot V)$   (log)")
    ax.set_ylabel("accuratezza  (%)")
    ax.text(0.02, 0.04, "area del marcatore ~ vantaggio energetico x",
            transform=ax.transAxes, color=fc.INK_MUTED, fontsize=10)
    fc.style_legend(ax, loc="lower left", bbox_to_anchor=(0.0, 0.14))
    fig.savefig(OUT / "discriminant.png")
    plt.close(fig)


def fig_safety_delta():
    """Lollipop of each champion's safety metrics as a RELATIVE deviation (%)
    from the oracle (Master Splinter). Using percent change puts three metrics
    of different units on one comparable, bounded axis. Near-zero => the
    champion behaves like the oracle."""
    df = fc.load_csv(REPO,
        "results/evaluate/v3_TURTLE_POWER!!!/02_Safety_ClosedLoop/safety.csv")
    df = df.set_index("champion")
    oracle = df.loc["Master Splinter"]

    # sign chosen so a positive % on the axis always means "safer than oracle".
    # min_ttc: higher safer            -> +(champ-oracle)/oracle
    # brake_margin_min: higher safer   -> +(champ-oracle)/oracle
    # collision_rate: lower safer      -> -(champ-oracle)/oracle
    metrics = [
        ("min_ttc",          "min TTC",              +1),
        ("brake_margin_min", "margine di frenata",   +1),
        ("collision_rate",   "tasso di collisione",  -1),
    ]

    fc.apply_dark_style()
    fig, ax = plt.subplots(figsize=(7.8, 4.4))

    group_gap = 1.2
    ylabels = []
    for mi, (col, lab, sign) in enumerate(metrics):
        for ci, ch in enumerate(CHAMPIONS):
            y = mi * (len(CHAMPIONS) + group_gap) + ci
            pct = 100.0 * sign * (df.loc[ch, col] - oracle[col]) / oracle[col]
            st = fc.champion_style(ch)
            stem_c = fc.SAFE if pct >= 0 else fc.DANGER
            ax.plot([0, pct], [y, y], color=stem_c, linewidth=2.4,
                    alpha=0.6, zorder=1, solid_capstyle="round")
            ax.scatter(pct, y, s=130, color=st["color"], marker=st["marker"],
                       edgecolor="#0E1216", linewidth=1.2, zorder=3,
                       label=st["label"] if mi == 0 else None)
        yc = mi * (len(CHAMPIONS) + group_gap) + (len(CHAMPIONS) - 1) / 2
        ylabels.append((yc, lab))

    ax.axvline(0.0, color=fc.INK, linewidth=1.6, linestyle="-", zorder=2, alpha=0.8)
    ax.set_xlim(-35, 35)
    ax.margins(y=0.10)
    ax.set_yticks([yc for yc, _ in ylabels], [lab for _, lab in ylabels])
    ax.invert_yaxis()
    ax.text(0.985, 1.03, "margine di frenata ~ oracolo; dove differiscono, i "
            "campioni sono piu sicuri (TTC ↑)", transform=ax.transAxes,
            color=fc.SAFE, fontsize=9.5, ha="right", va="bottom", fontweight="bold")
    ax.set_xlabel(r"scostamento dall'oracolo (%)   ($\rightarrow$ = piu sicuro; 0 = oracolo)")
    ax.grid(True, axis="x")
    ax.grid(False, axis="y")
    fc.style_legend(ax, loc="upper center", ncol=4, bbox_to_anchor=(0.5, -0.20),
                    columnspacing=1.2, handletextpad=0.4)
    fig.savefig(OUT / "safety_delta.png")
    plt.close(fig)


def fig_fim():
    """Clean dark info-panel of the Fisher Information Matrix summary."""
    df = fc.load_csv(REPO,
        "results/evaluate/v3_TURTLE_POWER!!!/04_Identifiability/fim.csv")
    m = dict(zip(df["metric"], df["value"]))
    cond = float(m["cond_mean"])
    rank = int(float(m["rank_FIM"]))
    n_eq = int(float(m["n_equivalent"]))
    least = str(m["least_identifiable"])
    most = str(m["most_identifiable"])

    fc.apply_dark_style()
    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    cards = [
        (r"cond$(\mathcal{F})$", f"{cond:.1e}".replace("e+0", "e"),
         "mal condizionata", fc.DANGER),
        ("rank FIM", f"{rank}/5", "pieno rango", fc.SAFE),
        ("insiemi\nequifinali", f"~{n_eq}", "parametrizzazioni\nindistinguibili", fc.ACCENT),
    ]
    x0, w, gap = 0.02, 0.30, 0.03
    for i, (title, big, sub, accent) in enumerate(cards):
        x = x0 + i * (w + gap)
        ax.add_patch(plt.Rectangle((x, 0.34), w, 0.60, transform=ax.transAxes,
                     facecolor="#1B2028", edgecolor=fc.SPINE, linewidth=1.0,
                     zorder=1, joinstyle="round"))
        ax.add_patch(plt.Rectangle((x, 0.90), w, 0.04, transform=ax.transAxes,
                     facecolor=accent, edgecolor="none", zorder=2))
        ax.text(x + w / 2, 0.845, title, transform=ax.transAxes, ha="center",
                va="top", color=fc.INK_MUTED, fontsize=13)
        ax.text(x + w / 2, 0.63, big, transform=ax.transAxes, ha="center",
                va="center", color=accent, fontsize=30, fontweight="bold")
        ax.text(x + w / 2, 0.415, sub, transform=ax.transAxes, ha="center",
                va="center", color=fc.INK, fontsize=11)

    # identifiability strip along the bottom
    ax.text(0.02, 0.20, "meno identificabile", transform=ax.transAxes,
            color=fc.INK_MUTED, fontsize=11, ha="left", va="center")
    ax.text(0.30, 0.20, f"${least}$", transform=ax.transAxes,
            color=fc.DANGER, fontsize=16, fontweight="bold", ha="left", va="center")
    ax.text(0.62, 0.20, "piu identificabile", transform=ax.transAxes,
            color=fc.INK_MUTED, fontsize=11, ha="left", va="center")
    ax.text(0.90, 0.20, f"${most}$", transform=ax.transAxes,
            color=fc.SAFE, fontsize=16, fontweight="bold", ha="left", va="center")
    ax.text(0.02, 0.05, "FIM di rango pieno ma quasi singolare: il modello e "
            "identificabile in teoria, equifinale in pratica",
            transform=ax.transAxes, color=fc.INK_MUTED, fontsize=10,
            ha="left", va="center")
    fig.savefig(OUT / "fim.png")
    plt.close(fig)


FIGS = [fig_accuracy_heatmap, fig_nrmse_stratified, fig_discriminant,
        fig_safety_delta, fig_fim]


def main():
    for f in FIGS:
        f()
        print("OK", f.__name__)


if __name__ == "__main__":
    main()
