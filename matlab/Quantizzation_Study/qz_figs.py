"""[Quantizzation_Study] Le curve dello studio di quantizzazione vs nfrac, in un'unica figura a pannelli:
accuratezza open-loop (max|d|), car-following (NRMSE + collisioni extra), risorse (LUT/FF), DSP, potenza, Fmax.
Grounded sui TSV (acc_sweep, cl_sweep, res_sweep). Ginocchio segnato a nfrac=4 (params). Solo matplotlib.
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures"); os.makedirs(FIG, exist_ok=True)
KNEE = 4


def load(name):
    with open(os.path.join(HERE, name), newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def arr(rows, key, filt=None):
    return np.array([float(r[key]) for r in rows if (filt is None or filt(r))])


# --- dati ---
acc = load("acc_sweep.tsv")
af = arr(acc, "nfrac", lambda r: r["champion"] == "Donatello")
ad = arr(acc, "maxd", lambda r: r["champion"] == "Donatello")
o = np.argsort(af); af, ad = af[o], ad[o]

cl = load("cl_sweep.tsv")
cf = arr(cl, "nfrac"); ce = arr(cl, "coll_extra"); cn = arr(cl, "NRMSE_mean")
o = np.argsort(cf); cf, ce, cn = cf[o], ce[o], cn[o]

res = load("res_sweep.tsv")
rf = arr(res, "nfrac"); o = np.argsort(rf)
rf = rf[o]
lut = arr(res, "LUT")[o]; ff = arr(res, "FF")[o]; dsp = arr(res, "DSP")[o]
fmax = arr(res, "Fmax_MHz")[o]; pt = arr(res, "Ptot_W")[o]
pd = arr(res, "Pdyn_W")[o]; ps = arr(res, "Psta_W")[o]

# --- figura ---
plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.3})
fig, ax = plt.subplots(2, 3, figsize=(15, 8))
fig.suptitle("Studio di quantizzazione — Donatello (config FAST-like, deploy 125 ns io-timed)", fontsize=13)


def knee(a):
    a.axvline(KNEE, color="crimson", ls="--", lw=1, alpha=0.7)
    a.annotate(f"ginocchio\nnfrac={KNEE}", (KNEE, a.get_ylim()[1]),
               color="crimson", fontsize=8, va="top", ha="left")


# 1. accuratezza open-loop
a = ax[0, 0]; a.plot(af, ad, "o-", color="#1f77b4")
a.set_title("Accuratezza open-loop (worst-case)"); a.set_xlabel("nfrac"); a.set_ylabel("max|d| param (fisico)")
knee(a)

# 2. car-following
a = ax[0, 1]; a.plot(cf, cn, "o-", color="#2ca02c", label="NRMSE param")
a.set_title("Car-following (anello chiuso, 99 scenari)"); a.set_xlabel("nfrac"); a.set_ylabel("NRMSE param (media)")
a2 = a.twinx(); a2.bar(cf, ce, width=0.5, color="crimson", alpha=0.4)
a2.set_ylabel("collisioni extra", color="crimson"); a2.set_ylim(0, max(1, ce.max() + 1)); a2.grid(False)
a.text(0.5, 0.9, "collisioni extra = 0 ovunque", transform=a.transAxes, color="crimson", fontsize=8, ha="center")
knee(a)

# 3. risorse LUT/FF
a = ax[0, 2]; a.plot(rf, lut, "o-", label="LUT", color="#ff7f0e"); a.plot(rf, ff, "s-", label="FF", color="#8c564b")
a.set_title("Risorse"); a.set_xlabel("nfrac"); a.set_ylabel("count"); a.legend()
knee(a)

# 4. DSP
a = ax[1, 0]; a.plot(rf, dsp, "o-", color="#9467bd")
a.set_title("DSP"); a.set_xlabel("nfrac"); a.set_ylabel("DSP48")
knee(a)

# 5. potenza
a = ax[1, 1]; a.plot(rf, pt, "o-", label="totale", color="#17becf")
a.plot(rf, pd, "s-", label="dinamica", color="#e377c2"); a.plot(rf, ps, "^-", label="statica", color="#7f7f7f")
a.set_title("Potenza (Zynq-7020, static-dominata)"); a.set_xlabel("nfrac"); a.set_ylabel("W"); a.legend()
knee(a)

# 6. Fmax
a = ax[1, 2]; a.plot(rf, fmax, "o-", color="#d62728")
a.set_title("Fmax io-timed @ deploy (margine)"); a.set_xlabel("nfrac"); a.set_ylabel("MHz")
knee(a)

fig.tight_layout(rect=[0, 0, 1, 0.96])
out = os.path.join(FIG, "quantization_curves.png")
fig.savefig(out, dpi=130)
print(f"scritto {out}")
