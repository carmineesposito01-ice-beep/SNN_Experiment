"""Traffic & robustness DARK figures for the CF_FSNN dark-theme deck.

Message of the module: the champions' driving behaviour tracks the PHYSICS
(the road, the geometry, the comms handler) rather than any quirk of the net.
Each figure is a distinct visual type (slope / frontier / curve / dot-line /
fundamental diagram / dot) to avoid bar-chart monotony.
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "_shared"))
import figures_common_dark as fc  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)

DATA = "results/evaluate/v3_TURTLE_POWER!!!"
CHAMPIONS = ["Raffaello", "Leonardo", "Donatello", "Michelangelo"]
ORACLE = "Master Splinter"


# ---------------------------------------------------------------------------
# 1. Plant / road surface — SLOPE plot: collision vs surface friction.
#    Degradation tracks the ROAD, not the net (all lines climb together).
# ---------------------------------------------------------------------------
def fig_plant():
    df = fc.load_csv(REPO, f"{DATA}/07_VehicleDynamics/plant.csv")
    surfaces = ["ideale", "bagnato", "ghiaccio"]
    xlabels = ["Asciutto", "Bagnato", "Ghiaccio"]
    x = np.arange(len(surfaces))
    cols = [f"collision_{s}" for s in surfaces]

    fc.apply_dark_style()
    fig, ax = plt.subplots()

    for name in CHAMPIONS + [ORACLE]:
        row = df[df["champion"] == name]
        if row.empty:
            continue
        y = [row.iloc[0][c] * 100 for c in cols]
        st = fc.champion_style(name)
        lw = 3.2 if name == ORACLE else 2.4
        z = 5 if name == ORACLE else 3
        ax.plot(x, y, color=st["color"], linestyle=st["linestyle"],
                marker=st["marker"], label=st["label"], linewidth=lw, zorder=z,
                markersize=10)

    ax.set_xticks(x)
    ax.set_xticklabels(xlabels)
    ax.set_xlabel("Superficie stradale (attrito decrescente →)")
    ax.set_ylabel("Tasso di collisione (%)")
    ax.set_xlim(-0.25, len(surfaces) - 0.75)
    ax.annotate("La degradazione segue la STRADA,\nnon la rete: le tracce sono sovrapposte",
                xy=(0.02, 0.97), xycoords="axes fraction", va="top", ha="left",
                fontsize=12, color=fc.INK_MUTED)
    fc.style_legend(ax, loc="upper left", bbox_to_anchor=(0.0, 0.86))
    fig.savefig(OUT / "plant.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 2. Reachability — FRONTIER: minimum safe gap vs initial closing speed.
#    Oracle drawn as the reference frontier; champions sit on/above it.
# ---------------------------------------------------------------------------
def fig_reachability():
    df = fc.load_csv(REPO, f"{DATA}/10_Reachability/reachability.csv")

    fc.apply_dark_style()
    fig, ax = plt.subplots()

    # Oracle reference frontier = min_safe_gap_oracle (identical across champions).
    ref = df.groupby("dv0")["min_safe_gap_oracle"].mean().sort_index()
    ax.plot(ref.index, ref.values, color=fc.champion_style(ORACLE)["color"],
            linestyle=":", marker="X", linewidth=3.4, markersize=11,
            label="Oracolo (frontiera di rif.)", zorder=6)
    ax.fill_between(ref.index, ref.values, ref.values.max() + 3,
                    color=fc.SAFE, alpha=0.07, zorder=0)

    for name in CHAMPIONS:
        sub = df[df["champion"] == name].sort_values("dv0")
        st = fc.champion_style(name)
        ax.plot(sub["dv0"], sub["min_safe_gap_snn"], color=st["color"],
                linestyle=st["linestyle"], marker=st["marker"],
                label=st["label"], linewidth=2.3, zorder=3)

    ax.set_xlabel("Δv iniziale di avvicinamento (m/s)")
    ax.set_ylabel("Gap minimo di sicurezza (m)")
    ax.annotate("Zona sicura\n(gap ≥ frontiera)", xy=(8.4, 12.5),
                fontsize=11, color=fc.SAFE, ha="center")
    ax.annotate("Le frontiere SNN aderiscono\nall'oracolo (scarto ≤ 1.3 m)",
                xy=(0.97, 0.05), xycoords="axes fraction", va="bottom",
                ha="right", fontsize=12, color=fc.INK_MUTED)
    fc.style_legend(ax, loc="upper left")
    fig.savefig(OUT / "reachability.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 3. Breakdown — CURVE: collision vs cut-in gap severity.
#    (panic_decel collision is all-zero, so cut_in_gap is the informative axis.)
#    Champions' frontier lands on the oracle curve.
# ---------------------------------------------------------------------------
def fig_breakdown():
    df = fc.load_csv(REPO, f"{DATA}/11_Breakdown/breakdown.csv")
    sub = df[df["axis"] == "cut_in_gap"]

    fc.apply_dark_style()
    fig, ax = plt.subplots()

    # Oracle curve (shared reference).
    orc = sub.groupby("val")["collision_oracle"].mean().sort_index()
    ax.plot(orc.index, orc.values * 100, color=fc.champion_style(ORACLE)["color"],
            linestyle=":", marker="X", linewidth=3.4, markersize=11,
            label="Oracolo", zorder=6)

    for name in CHAMPIONS:
        s = sub[sub["champion"] == name].sort_values("val")
        st = fc.champion_style(name)
        ax.plot(s["val"], s["collision_snn"] * 100, color=st["color"],
                linestyle=st["linestyle"], marker=st["marker"],
                label=st["label"], linewidth=2.3, zorder=3)

    ax.set_xlabel("Gap del taglio-corsia (m) — più stretto = più severo")
    ax.set_ylabel("Tasso di collisione (%)")
    ax.invert_xaxis()  # severity increases to the right
    ax.annotate("Severità crescente →", xy=(0.62, 0.40),
                xycoords="axes fraction", ha="left", fontsize=11,
                color=fc.INK_MUTED)
    ax.annotate("Le curve SNN coincidono con l'oracolo:\nlimite fisico dello scenario, non della rete",
                xy=(0.55, 0.10), xycoords="axes fraction", va="bottom",
                ha="center", fontsize=12, color=fc.INK_MUTED)
    fc.style_legend(ax, loc="upper left", bbox_to_anchor=(0.0, 1.0))
    fig.savefig(OUT / "breakdown.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 4. String stability — DOT/LINE: head-to-tail gain per champion, with the
#    stability threshold at 1.0 (all below = string-stable). Overlay 12-veh
#    mesoscopic gain from the same platoons.
# ---------------------------------------------------------------------------
def fig_string():
    ss = fc.load_csv(REPO, f"{DATA}/03_StringStability/string_stability.csv")
    meso = fc.load_csv(REPO, f"{DATA}/12_Mesoscopic/meso_summary.csv")
    meso_map = dict(zip(meso["source"], meso["head_to_tail_gain"]))

    order = CHAMPIONS + [ORACLE]
    y = np.arange(len(order))[::-1]  # oracle at bottom

    fc.apply_dark_style()
    fig, ax = plt.subplots()

    # Threshold line at gain = 1.0.
    ax.axvline(1.0, color=fc.DANGER, linestyle="--", linewidth=1.8, zorder=1)
    ax.axvspan(0, 1.0, color=fc.SAFE, alpha=0.06, zorder=0)

    for yi, name in zip(y, order):
        st = fc.champion_style(name)
        row = ss[ss["champion"] == name]
        g_pair = float(row.iloc[0]["head_to_tail"]) if not row.empty else np.nan
        # stem from 0 to the 2-vehicle gain
        ax.hlines(yi, 0, g_pair, color=st["color"], linewidth=2.2, zorder=2)
        ax.plot(g_pair, yi, color=st["color"], marker=st["marker"],
                markersize=13, zorder=4,
                label="2 veicoli (H→T)" if name == order[0] else None)
        # 12-vehicle meso gain as a hollow diamond overlay
        g_meso = meso_map.get(name, np.nan)
        ax.plot(g_meso, yi, marker="D", markersize=11, markerfacecolor="none",
                markeredgecolor=st["color"], markeredgewidth=2.2, zorder=5,
                label="12 veicoli (meso)" if name == order[0] else None)

    ax.set_yticks(y)
    ax.set_yticklabels([fc.champion_style(n)["label"] for n in order])
    ax.set_xlabel("Guadagno head-to-tail  (< 1 ⇒ string-stable)")
    ax.set_xlim(0, 1.12)
    ax.grid(axis="y", visible=False)
    ax.annotate("soglia = 1.0", xy=(1.0, y.max() + 0.35), color=fc.DANGER,
                fontsize=11, ha="center")
    ax.annotate("Tutti i platoon sotto 1: le perturbazioni\nsi smorzano a valle (12 veh ≈ 2 veh)",
                xy=(0.55, 0.93), xycoords="axes fraction", va="top",
                ha="center", fontsize=12, color=fc.INK_MUTED)
    fc.style_legend(ax, loc="center right")
    fig.savefig(OUT / "string.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 5. Macroscopic fundamental diagram — TRIANGULAR Q(rho) curve per champion,
#    reconstructed from the scalar summary: free-flow slope = v_free, congested
#    branch back to (rho_jam, 0). Raffaello's inflated v_free distorts the curve.
# ---------------------------------------------------------------------------
def fig_macro_fd():
    df = fc.load_csv(REPO, f"{DATA}/13_Macroscopic/macro_summary.csv")

    fc.apply_dark_style()
    fig, ax = plt.subplots()

    for _, r in df.iterrows():
        name = r["source"]
        if name not in CHAMPIONS + [ORACLE]:
            continue
        v_free = r["v_free_km_h"]
        rho_crit = r["rho_crit_veh_km"]
        rho_jam = r["rho_jam_veh_km"]
        cap = r["capacity_veh_h"]
        # Triangular FD: free branch v_free*rho up to (rho_crit, cap); then
        # congested branch straight down to (rho_jam, 0).
        rho = np.linspace(0, rho_jam, 200)
        w = cap / (rho_jam - rho_crit)  # congestion wave slope magnitude
        q_free = v_free * rho
        q_cong = w * (rho_jam - rho)
        q = np.minimum(q_free, q_cong)
        st = fc.champion_style(name)
        lw = 3.3 if name == ORACLE else 2.3
        z = 6 if name == ORACLE else 3
        ax.plot(rho, q, color=st["color"], linestyle=st["linestyle"],
                linewidth=lw, zorder=z,
                label=f"{st['label']}  (v$_f$={v_free:.0f})")
        ax.plot(rho_crit, cap, color=st["color"], marker=st["marker"],
                markersize=9, zorder=z + 1)

    ax.set_xlabel(r"Densità  $\rho$  (veic/km)".replace(r"à", "à"))
    ax.set_ylabel(r"Flusso  $Q$  (veic/h)")
    ax.set_xlim(0, 122)
    ax.set_ylim(0, None)
    ax.annotate("v$_f$ gonfiato di Raffaello (≈107 km/h)\ndeforma il ramo di flusso libero",
                xy=(0.30, 0.12), xycoords="axes fraction", va="bottom",
                ha="left", fontsize=12,
                color=fc.champion_style("Raffaello")["color"])
    fc.style_legend(ax, loc="upper right")
    fig.savefig(OUT / "macro_fd.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 6. V2X robustness — DOT plot: collision under each comms hold-mode handler.
#    'blind' explodes (~67%) regardless of champion; the failure is the
#    HANDLER's, not the net's.
# ---------------------------------------------------------------------------
def fig_v2x():
    df = fc.load_csv(REPO, f"{DATA}/06_V2X_Robustness/v2x.csv")
    sub = df[df["axis"] == "hold_mode"]

    modes = ["hold_last", "dead_reckon", "blind"]
    mode_labels = ["hold_last", "dead_reckon", "blind"]
    y = np.arange(len(modes))[::-1]

    fc.apply_dark_style()
    fig, ax = plt.subplots()

    # nominal safe band: oracle baseline from the working handlers only
    # (exclude 'blind', whose oracle also collapses ~68% and would skew it).
    nominal = sub[sub["val"] != "blind"]
    oracle_base = nominal["collision_rate_oracle"].mean() * 100
    ax.axvline(oracle_base, color=fc.champion_style(ORACLE)["color"],
               linestyle=":", linewidth=2.0, zorder=1,
               label=f"Oracolo nominale (≈{oracle_base:.0f}%)")
    ax.axvspan(0, 15, color=fc.SAFE, alpha=0.06, zorder=0)

    for yi, mode, lab in zip(y, modes, mode_labels):
        rows = sub[sub["val"] == mode]
        vals = rows["collision_rate"].values * 100
        is_blind = (mode == "blind")
        dot_color = fc.DANGER if is_blind else fc.SAFE
        # spread champions vertically a touch so dots don't fully overlap
        jitter = np.linspace(-0.16, 0.16, len(vals))
        ax.scatter(vals, yi + jitter, s=150, color=dot_color,
                   edgecolor=fc.BG, linewidth=1.2, zorder=4)
        mean_v = vals.mean()
        ax.annotate(f"{mean_v:.0f}%", xy=(mean_v, yi + 0.34), ha="center",
                    fontsize=12, color=dot_color)

    ax.set_yticks(y)
    ax.set_yticklabels(mode_labels)
    ax.set_ylabel("Handler di hold-mode")
    ax.set_xlabel("Tasso di collisione (%)  — 4 champion per riga")
    ax.set_xlim(0, 80)
    ax.set_ylim(-0.7, len(modes) - 0.3)
    ax.grid(axis="y", visible=False)
    ax.annotate("'blind' collassa (≈67%) per TUTTI i champion:\nla robustezza è dell'handler, non della rete",
                xy=(0.60, 0.60), xycoords="axes fraction", va="center",
                ha="center", fontsize=12, color=fc.DANGER)
    fc.style_legend(ax, loc="upper right", bbox_to_anchor=(1.0, 0.92))
    fig.savefig(OUT / "v2x.png")
    plt.close(fig)


FIGS = [fig_plant, fig_reachability, fig_breakdown, fig_string,
        fig_macro_fd, fig_v2x]


def main():
    for f in FIGS:
        f()
        print("OK", f.__name__)


if __name__ == "__main__":
    main()
