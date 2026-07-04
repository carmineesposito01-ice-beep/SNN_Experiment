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

FIGURES = [fig_discriminant]

def main():
    for f in FIGURES:
        f(); print("OK", f.__name__)

if __name__ == "__main__":
    main()
