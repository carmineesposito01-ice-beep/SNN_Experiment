"""Rigenera/ri-stila TUTTE le figure della presentazione dai CSV reali. 100% locale."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "_shared"))
import figures_common as fc
import matplotlib.pyplot as plt

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)

def fig_discriminant():
    """rho(U.V) [x] vs accuratezza [y], area marker prop. vantaggio energetico. Zona verde rho<1."""
    e = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/08_Energy_Spiking/energy.csv")
    a = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/01_Accuracy/accuracy.csv")
    df = e.merge(a[["champion", "accuracy_pct"]], on="champion")
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    ax.axvspan(0, 1, color=fc.OKABE_ITO["green"], alpha=0.08)
    ax.axvline(1, color="#888", linestyle="--", linewidth=1)
    for _, r in df.iterrows():
        st = fc.champion_style(r["champion"])
        ax.scatter(r["spectral_radius"], r["accuracy_pct"],
                   s=60 * r["advantage_x"], color=st["color"], marker=st["marker"],
                   edgecolor="black", linewidth=0.6, zorder=3, label=st["label"])
    ax.set_xscale("log")
    ax.set_xlabel("raggio spettrale rho(U.V)  —  <1 = contrattivo (sicuro in fixed-point)")
    ax.set_ylabel("accuratezza identificazione (%)")
    ax.set_title("EventProp e contrattivo (rho<1); i BPTT no")
    ax.legend(loc="lower left", frameon=False)
    fig.savefig(OUT / "discriminant.png"); plt.close(fig)

def fig_accuracy_perparam():
    """Grouped bars: NRMSE per parametro (v0,T,s0,a,b), raggruppate per champion. Piu basso = meglio."""
    df = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/01_Accuracy/accuracy.csv")
    params = ["nrmse_v0", "nrmse_T", "nrmse_s0", "nrmse_a", "nrmse_b"]
    param_labels = ["v0", "T", "s0", "a", "b"]
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    n_champ = len(df)
    width = 0.8 / n_champ
    x = range(len(params))
    for i, (_, r) in enumerate(df.iterrows()):
        st = fc.champion_style(r["champion"])
        offsets = [xi + (i - (n_champ - 1) / 2) * width for xi in x]
        ax.bar(offsets, [r[p] for p in params], width=width * 0.95,
               color=st["color"], label=st["label"], edgecolor="black", linewidth=0.5)
    ax.set_xticks(list(x))
    ax.set_xticklabels(param_labels)
    ax.set_xlabel("parametro identificato")
    ax.set_ylabel("NRMSE (piu basso = meglio)")
    ax.set_title("Identifichiamo bene i 5 parametri (NRMSE per canale)")
    ax.legend(loc="upper right", frameon=False, ncol=2)
    fig.savefig(OUT / "accuracy_perparam.png"); plt.close(fig)

def fig_safety():
    """Bar collision_rate per champion + linea oracolo (Master Splinter). Messaggio: sicuri come l'oracolo."""
    df = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/02_Safety_ClosedLoop/safety.csv")
    oracle_rate = df.loc[df["champion"] == "Master Splinter", "collision_rate"].iloc[0]
    champs = df[df["champion"] != "Master Splinter"]
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    for i, (_, r) in enumerate(champs.iterrows()):
        st = fc.champion_style(r["champion"])
        ax.bar(i, r["collision_rate"] * 100, color=st["color"], label=st["label"],
               edgecolor="black", linewidth=0.5, width=0.6)
    ax.axhline(oracle_rate * 100, color=fc.champion_style("Master Splinter")["color"],
               linestyle=":", linewidth=2.5, label="Oracolo (riferimento)")
    ax.set_xticks(range(len(champs)))
    ax.set_xticklabels([fc.champion_style(c)["label"] for c in champs["champion"]], rotation=15, ha="right")
    ax.set_ylabel("tasso di collisione (%)")
    ax.set_title("In closed-loop: sicuri come l'oracolo (0 collisioni evitabili)")
    ax.set_ylim(0, max(oracle_rate * 100, champs["collision_rate"].max() * 100) * 1.6)
    ax.legend(loc="upper center", ncol=2, frameon=False, fontsize=13)
    fig.savefig(OUT / "safety.png"); plt.close(fig)

def fig_spike_dead():
    """Bar mean_spike_rate_pct per champion, annotato con dead_frac e rho. Messaggio: EventProp = 0 morti."""
    df = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/08_Energy_Spiking/energy.csv")
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    for i, (_, r) in enumerate(df.iterrows()):
        st = fc.champion_style(r["champion"])
        ax.bar(i, r["mean_spike_rate_pct"], color=st["color"], label=st["label"],
               edgecolor="black", linewidth=0.5, width=0.6)
        ax.annotate(f"morti: {r['dead_frac']*100:.0f}%\nrho: {r['spectral_radius']:.2f}",
                    xy=(i, r["mean_spike_rate_pct"]), xytext=(0, 8), textcoords="offset points",
                    ha="center", va="bottom", fontsize=13)
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels([fc.champion_style(c)["label"] for c in df["champion"]], rotation=15, ha="right")
    ax.set_ylabel("tasso medio di spike (%)")
    ax.set_ylim(0, df["mean_spike_rate_pct"].max() * 1.35)
    ax.set_title("Salute della rete: EventProp = 0 neuroni morti (BPTT ~31%)")
    fig.savefig(OUT / "spike_dead.png"); plt.close(fig)

def fig_fim():
    """Scorecard delle metriche FIM: cond. number, rank, parametro meno/piu identificabile, n_equivalent.
    fim.csv e una tabella scalare metric,value (non una matrice per-parametro) -> il grafico onesto e
    un pannello riassuntivo annotato, non un bar/imshow che implicherebbe dati per-parametro assenti dal CSV."""
    df = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/04_Identifiability/fim.csv")
    v = dict(zip(df["metric"], df["value"]))
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    ax.axis("off")
    lines = [
        f"Condizionamento FIM (media):  {float(v['cond_mean']):.2e}",
        f"Condizionamento FIM (p95):    {float(v['cond_p95']):.2e}",
        f"Rango FIM:                    {v['rank_FIM']} / 5 parametri",
        f"Parametro meno identificabile:  {v['least_identifiable']}",
        f"Parametro piu identificabile:   {v['most_identifiable']}",
        f"Parametri sotto-eccitati:        {v['under_excited']}",
        f"Combinazioni equivalenti:        {v['n_equivalent']}",
    ]
    ax.text(0.03, 0.5, "\n\n".join(lines), transform=ax.transAxes,
            ha="left", va="center", fontsize=17, family="monospace")
    ax.set_title("Equifinalita: 29 combinazioni di parametri spiegano ugualmente bene i dati")
    fig.savefig(OUT / "fim.png"); plt.close(fig)

FIGURES = [fig_discriminant, fig_accuracy_perparam, fig_safety, fig_spike_dead, fig_fim]

def main():
    for f in FIGURES:
        f(); print("OK", f.__name__)

if __name__ == "__main__":
    main()
