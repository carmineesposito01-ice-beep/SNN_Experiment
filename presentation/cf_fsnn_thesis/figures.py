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

def fig_plant():
    """Grouped bars: collision_rate per superficie (ideale/bagnato/ghiaccio), per champion incl. oracolo.
    plant.csv ha 3 triplette di colonne (min_gap,collision,brake_margin) x suffisso superficie -> estraggo
    solo collision_* e raggruppo per superficie sull'asse x, una barra per champion."""
    df = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/07_VehicleDynamics/plant.csv")
    surfaces = ["ideale", "bagnato", "ghiaccio"]
    surface_labels = ["asciutto", "bagnato", "ghiaccio"]
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    n_champ = len(df)
    width = 0.8 / n_champ
    x = range(len(surfaces))
    for i, (_, r) in enumerate(df.iterrows()):
        st = fc.champion_style(r["champion"])
        offsets = [xi + (i - (n_champ - 1) / 2) * width for xi in x]
        vals = [r[f"collision_{s}"] * 100 for s in surfaces]
        ax.bar(offsets, vals, width=width * 0.95,
               color=st["color"], label=st["label"], edgecolor="black", linewidth=0.5)
    ax.set_xticks(list(x))
    ax.set_xticklabels(surface_labels)
    ax.set_xlabel("condizione stradale")
    ax.set_ylabel("tasso di collisione (%)")
    ax.set_title("La collisione sale con la STRADA, non con la rete (il ghiaccio e un limite fisico)")
    ax.legend(loc="upper left", frameon=False, ncol=2, fontsize=13)
    fig.savefig(OUT / "plant.png"); plt.close(fig)

def fig_string_meso():
    """Grouped bars: due metriche di gain testa->coda affiancate per champion (linea a 1.0 = soglia stabilita).
    string_stability.csv da head_to_tail (1 riga/champion, teorico); meso_summary.csv da head_to_tail_gain
    (simulazione 12 veicoli). Sono due dataset/scale diverse -> due serie di barre affiancate, non fuse."""
    s = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/03_StringStability/string_stability.csv")
    m = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/12_Mesoscopic/meso_summary.csv")
    df = s[["champion", "head_to_tail"]].merge(
        m[["source", "head_to_tail_gain"]].rename(columns={"source": "champion"}), on="champion")
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    n_champ = len(df)
    width = 0.35
    x = range(len(df))
    for i, (_, r) in enumerate(df.iterrows()):
        st = fc.champion_style(r["champion"])
        ax.bar(i - width / 2, r["head_to_tail"], width=width * 0.95,
               color=st["color"], edgecolor="black", linewidth=0.5)
        ax.bar(i + width / 2, r["head_to_tail_gain"], width=width * 0.95,
               color=st["color"], alpha=0.55, edgecolor="black", linewidth=0.5, hatch="//")
    ax.axhline(1.0, color="#888", linestyle="--", linewidth=1.5, label="soglia di stabilita (gain=1)")
    ax.set_xticks(list(x))
    ax.set_xticklabels([fc.champion_style(c)["label"] for c in df["champion"]], rotation=15, ha="right")
    ax.set_ylabel("gain testa -> coda")
    ax.set_title("Nel plotone le perturbazioni si smorzano (gain testa->coda < 1)")
    ax.set_ylim(0, 1.15)
    from matplotlib.patches import Patch
    handles = [Patch(facecolor="white", edgecolor="black", label="string stability (teorico)"),
               Patch(facecolor="white", edgecolor="black", hatch="//", label="mesoscopico (12 veicoli)")]
    ax.legend(handles=handles, loc="upper center", frameon=False, fontsize=13, ncol=2)
    fig.savefig(OUT / "string_meso.png"); plt.close(fig)

def fig_macro_fd():
    """Bar velocita di free-flow (v0) per champion, oracolo incluso. macro_summary.csv non contiene punti
    flusso-densita (solo scalari capacity/rho_crit/v_free/rho_jam/first_unstable_rho) -> il grafico onesto
    e un bar chart di v_free_km_h con Raffaello evidenziato (outlier ~107 vs ~65-74 km/h degli altri)."""
    df = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/13_Macroscopic/macro_summary.csv")
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    oracle_v0 = df.loc[df["source"] == "Master Splinter", "v_free_km_h"].iloc[0]
    for i, (_, r) in enumerate(df.iterrows()):
        st = fc.champion_style(r["source"])
        is_outlier = r["source"] == "Raffaello"
        ax.bar(i, r["v_free_km_h"],
               color=fc.ACCENT if is_outlier else st["color"],
               edgecolor="black", linewidth=2.2 if is_outlier else 0.5, width=0.6)
        if is_outlier:
            ax.annotate("distorto", xy=(i, r["v_free_km_h"]), xytext=(0, 10),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=14, fontweight="bold", color=fc.OKABE_ITO["vermillion"])
    ax.axhline(oracle_v0, color=fc.champion_style("Master Splinter")["color"],
               linestyle=":", linewidth=2, label="oracolo (riferimento)")
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels([fc.champion_style(c)["label"] for c in df["source"]], rotation=15, ha="right")
    ax.set_ylabel("velocita di free-flow v0 (km/h)")
    ax.set_title("Diagramma fondamentale: solo Raffaello lo distorce (v0 sovrastimato)")
    ax.set_ylim(0, df["v_free_km_h"].max() * 1.3)
    ax.legend(loc="upper right", frameon=False, fontsize=13)
    fig.savefig(OUT / "macro_fd.png"); plt.close(fig)

def fig_v2x():
    """Bar collision_rate per strategia di gestione packet-loss (hold_last/dead_reckon/blind), champion Raffaello
    come riferimento illustrativo (pattern identico su tutti i champion). v2x.csv e long-format con colonna
    axis+val; filtro axis=='hold_mode' e uso val come categoria. Barra 'blind' in accent/rosso per il pericolo."""
    df = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/06_V2X_Robustness/v2x.csv")
    hold = df[df["axis"] == "hold_mode"]
    strategies = ["hold_last", "dead_reckon", "blind"]
    strategy_labels = ["hold-last", "dead-reckon", "blind"]
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    n_champ = hold["champion"].nunique()
    width = 0.8 / n_champ
    x = range(len(strategies))
    for i, champ in enumerate(hold["champion"].unique()):
        st = fc.champion_style(champ)
        sub = hold[hold["champion"] == champ].set_index("val")
        offsets = [xi + (i - (n_champ - 1) / 2) * width for xi in x]
        vals = [sub.loc[s, "collision_rate"] * 100 for s in strategies]
        colors = [fc.OKABE_ITO["vermillion"] if s == "blind" else st["color"] for s in strategies]
        edgecolors = ["black" if s != "blind" else fc.OKABE_ITO["vermillion"] for s in strategies]
        linewidths = [0.5 if s != "blind" else 2.0 for s in strategies]
        ax.bar(offsets, vals, width=width * 0.95, color=colors,
               edgecolor=edgecolors, linewidth=linewidths)
    ax.annotate("pericolo", xy=(2, hold[hold["val"] == "blind"]["collision_rate"].max() * 100),
                xytext=(0, 10), textcoords="offset points", ha="center", va="bottom",
                fontsize=14, fontweight="bold", color=fc.OKABE_ITO["vermillion"])
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=fc.champion_style(c)["color"], edgecolor="black", label=fc.champion_style(c)["label"])
               for c in hold["champion"].unique()]
    ax.set_xticks(list(x))
    ax.set_xticklabels(strategy_labels)
    ax.set_xlabel("strategia di gestione packet-loss")
    ax.set_ylabel("tasso di collisione (%)")
    ax.set_title("V2X: la robustezza e dell'handler «hold-last», non della rete (blind -> ~67%)")
    ax.set_ylim(0, hold["collision_rate"].max() * 100 * 1.2)
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=12,
              title="colore = champion; bordo rosso = 'blind'", title_fontsize=11)
    fig.savefig(OUT / "v2x.png"); plt.close(fig)

FIGURES = [fig_discriminant, fig_accuracy_perparam, fig_safety, fig_spike_dead, fig_fim,
           fig_plant, fig_string_meso, fig_macro_fd, fig_v2x]

def main():
    for f in FIGURES:
        f(); print("OK", f.__name__)

if __name__ == "__main__":
    main()
