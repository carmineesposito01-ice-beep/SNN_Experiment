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
    ax.text(0.98, 0.97, "zona verde: EventProp e contrattivo (rho<1); i BPTT no",
            transform=ax.transAxes, ha="right", va="top", fontsize=12,
            color=fc.OKABE_ITO["green"], fontweight="bold")
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
    ax.set_ylim(0, hold["collision_rate"].max() * 100 * 1.2)
    ax.legend(handles=handles, loc="upper left", frameon=False, fontsize=12,
              title="colore = champion; bordo rosso = 'blind'", title_fontsize=11)
    fig.savefig(OUT / "v2x.png"); plt.close(fig)

def fig_readiness_radar():
    """Small-multiples radar (2x2, uno per champion): 6 assi di idoneita FPGA su scala 0-1 (1=ideale).
    scorecard.csv ha le 6 colonne gia normalizzate 0-1 -> poligono riempito colore-champion, nessuna
    trasformazione necessaria oltre a chiudere il poligono (ripetere il primo valore in coda)."""
    import numpy as np
    df = fc.load_csv(REPO, "results/evaluate/FPGA/00_Readiness/scorecard.csv")
    axes_cols = ["ρ<1", "Fix-pt", "Sparsità", "Energia", "Timing", "SEU"]
    n = len(axes_cols)
    angles = [i / n * 2 * 3.141592653589793 for i in range(n)] + [0]
    fc.apply_stage_style()
    fig, subplots = plt.subplots(2, 2, subplot_kw=dict(polar=True), figsize=(11, 11))
    for ax, (_, r) in zip(subplots.flat, df.iterrows()):
        st = fc.champion_style(r["champion"])
        vals = [r[c] for c in axes_cols] + [r[axes_cols[0]]]
        ax.plot(angles, vals, color=st["color"], linewidth=2.5)
        ax.fill(angles, vals, color=st["color"], alpha=0.35)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(axes_cols, fontsize=12)
        ax.set_ylim(0, 1)
        ax.set_yticks([0.25, 0.5, 0.75, 1.0])
        ax.set_yticklabels(["0.25", "0.5", "0.75", "1"], fontsize=9)
        ax.set_title(st["label"], fontsize=15, pad=18)
    fig.savefig(OUT / "readiness_radar.png"); plt.close(fig)

def fig_resources():
    """Bar footprint_B (byte) per champion + annotazione headline: 0 DSP, <1% BRAM su 140.
    scorecard.csv ha footprint_B (400-656 B); dsp_snn=0 e confermato in energy_power.csv per tutti
    i 4 champion -> l'annotazione '0 DSP' e dato reale, non inventato."""
    df = fc.load_csv(REPO, "results/evaluate/FPGA/00_Readiness/scorecard.csv")
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    for i, (_, r) in enumerate(df.iterrows()):
        st = fc.champion_style(r["champion"])
        ax.bar(i, r["footprint_B"], color=st["color"], label=st["label"],
               edgecolor="black", linewidth=0.5, width=0.6)
        ax.annotate(f"{r['footprint_B']:.0f} B", xy=(i, r["footprint_B"]), xytext=(0, 6),
                    textcoords="offset points", ha="center", va="bottom", fontsize=13)
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels([fc.champion_style(c)["label"] for c in df["champion"]], rotation=15, ha="right")
    ax.set_ylabel("footprint di memoria (byte)")
    ax.set_ylim(0, df["footprint_B"].max() * 1.35)
    ax.text(0.5, 0.92, "0 DSP · <1 BRAM su 140", transform=ax.transAxes,
            ha="center", va="top", fontsize=19, fontweight="bold", color=fc.ACCENT,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=fc.ACCENT, linewidth=1.5))
    fig.savefig(OUT / "resources.png"); plt.close(fig)

def fig_quant():
    """Due pannelli: (sx) id_err_mean vs frac_bits in modalita fixed-point, per champion — errore piatto
    fino a poche bit; (dx) delta_qat_absorbed dell'ablation po2 per champion, linea a 0 (<=0 = QAT assorbe
    il rumore po2). frac_bits e stringa con valore 'float' non ordinabile numericamente -> ordine esplicito."""
    q = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/05_Quantization/quantization.csv")
    ab = fc.load_csv(REPO, "results/evaluate/v3_TURTLE_POWER!!!/05_Quantization/quant_weight_ablation.csv")
    bit_order = ["float", "12", "8", "6", "4", "3", "2"]
    fixed = q[q["mode"] == "fixed"]
    fc.apply_stage_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.6), layout="constrained")
    for champ in fixed["champion"].unique():
        st = fc.champion_style(champ)
        sub = fixed[fixed["champion"] == champ].set_index("frac_bits").reindex(bit_order)
        ax1.plot(range(len(bit_order)), sub["id_err_mean"], color=st["color"],
                 linestyle=st["linestyle"], marker=st["marker"], label=st["label"])
    ax1.set_xticks(range(len(bit_order)))
    ax1.set_xticklabels(bit_order)
    ax1.set_xlabel("bit di frazione (fixed-point)")
    ax1.set_ylabel("errore medio di identificazione")
    ax1.legend(loc="upper left", frameon=False, fontsize=11)

    for i, (_, r) in enumerate(ab.iterrows()):
        st = fc.champion_style(r["champion"])
        color = st["color"] if r["delta_qat_absorbed"] <= 0 else fc.OKABE_ITO["vermillion"]
        ax2.bar(i, r["delta_qat_absorbed"], color=color, edgecolor="black", linewidth=0.5, width=0.6)
    ax2.axhline(0, color="#888", linestyle="--", linewidth=1.5)
    ax2.set_xticks(range(len(ab)))
    ax2.set_xticklabels([fc.champion_style(c)["label"] for c in ab["champion"]], rotation=15, ha="right")
    ax2.set_ylabel("delta ablation po2")

    fig.savefig(OUT / "quant.png"); plt.close(fig)

def fig_energy_ann():
    """Grouped bars: energia SNN (worst-case) vs ANN densa per champion, annotato con fattore di vantaggio.
    energy_power.csv ha gia advantage_worstcase_x pre-calcolato -> uso quello per l'annotazione invece di
    ricalcolarlo, evitando arrotondamenti incoerenti col dato sorgente."""
    df = fc.load_csv(REPO, "results/evaluate/FPGA/04_Energy/energy_power.csv")
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    width = 0.35
    x = range(len(df))
    for i, (_, r) in enumerate(df.iterrows()):
        st = fc.champion_style(r["champion"])
        ax.bar(i - width / 2, r["E_snn_worstcase_nJ"], width=width * 0.95,
               color=st["color"], edgecolor="black", linewidth=0.5)
        ax.bar(i + width / 2, r["E_ann_nJ"], width=width * 0.95,
               color=st["color"], alpha=0.4, edgecolor="black", linewidth=0.5, hatch="//")
        ax.annotate(f"{r['advantage_worstcase_x']:.1f}x", xy=(i, r["E_ann_nJ"]), xytext=(0, 6),
                    textcoords="offset points", ha="center", va="bottom", fontsize=13, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels([fc.champion_style(c)["label"] for c in df["champion"]], rotation=15, ha="right")
    ax.set_ylabel("energia per inferenza (nJ)")
    from matplotlib.patches import Patch
    handles = [Patch(facecolor="white", edgecolor="black", label="SNN (worst-case)"),
               Patch(facecolor="white", edgecolor="black", alpha=0.4, hatch="//", label="ANN densa")]
    ax.legend(handles=handles, loc="upper right", frameon=False, fontsize=13)
    fig.savefig(OUT / "energy_ann.png"); plt.close(fig)

def fig_seu():
    """Grouped bars: sensibilita al bit-flip (SEU) per posizione di bit (exp_LSB..readout_mean), raggruppate
    per champion. Il CSV e wide (1 riga/champion, colonne=posizioni di bit) -> nessun merge necessario,
    solo iterazione diretta sulle colonne per costruire le barre raggruppate."""
    df = fc.load_csv(REPO, "results/evaluate/FPGA/07_SEU_ISO26262/seu_sensitivity.csv")
    bit_cols = ["exp_LSB", "exp_mid", "exp_MSB", "segno", "hidden_mean", "readout_mean"]
    bit_labels = ["exp LSB", "exp mid", "exp MSB", "segno", "hidden", "readout"]
    fc.apply_stage_style()
    fig, ax = plt.subplots()
    n_champ = len(df)
    width = 0.8 / n_champ
    x = range(len(bit_cols))
    for i, (_, r) in enumerate(df.iterrows()):
        st = fc.champion_style(r["champion"])
        offsets = [xi + (i - (n_champ - 1) / 2) * width for xi in x]
        ax.bar(offsets, [r[c] for c in bit_cols], width=width * 0.95,
               color=st["color"], label=st["label"], edgecolor="black", linewidth=0.5)
    ax.set_xticks(list(x))
    ax.set_xticklabels(bit_labels, rotation=15, ha="right")
    ax.set_xlabel("posizione del bit / gruppo di neuroni")
    ax.set_ylabel("sensibilita al bit-flip (SEU)")
    ax.legend(loc="upper left", frameon=False, ncol=2, fontsize=13)
    fig.savefig(OUT / "seu.png"); plt.close(fig)

FIGURES = [fig_discriminant, fig_accuracy_perparam, fig_safety, fig_spike_dead, fig_fim,
           fig_plant, fig_string_meso, fig_macro_fd, fig_v2x,
           fig_readiness_radar, fig_resources, fig_quant, fig_energy_ann, fig_seu]

def main():
    for f in FIGURES:
        f(); print("OK", f.__name__)

if __name__ == "__main__":
    main()
