#!/usr/bin/env python3
"""figs_lut_sweep.py — figura SP1: accuratezza, errore d'interpolazione e risorse HW vs dimensione LUT.

Sorgenti (grounding):
  matlab/axi/build/lut_sweep/results_lut.csv     -> N, acc, dmax_vs_512   (Task 2, 60 traiettorie)
  matlab/axi/build/lut_sweep/results_lut_hw.csv  -> N, LUT, FF, DSP, ...   (Task 3/5, sintesi Vivado OOC)

La curva risorse si disegna solo se il CSV HW esiste (altrimenti figura a 2 pannelli). Niente np.linalg/LAPACK.
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SWEEP = os.path.join(ROOT, "matlab", "axi", "build", "lut_sweep")
ACC_CSV = os.path.join(SWEEP, "results_lut.csv")
HW_CSV = os.path.join(SWEEP, "results_lut_hw.csv")
OUT = os.path.join(ROOT, "document", "decode_lut_sweep.png")


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    acc_rows = read_csv(ACC_CSV)
    N = [int(r["N"]) for r in acc_rows]
    acc = [float(r["acc"]) for r in acc_rows]
    dmax = [float(r["dmax_vs_512"]) for r in acc_rows]

    hw = read_csv(HW_CSV) if os.path.isfile(HW_CSV) else None
    npanels = 3 if hw else 2

    plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.3})
    fig, ax = plt.subplots(1, npanels, figsize=(4.6 * npanels, 3.6))
    fig.patch.set_facecolor("white")

    # (1) accuratezza vs N — piatta
    ax[0].semilogx(N, acc, "o-", base=2, color="#1f77b4")
    ax[0].set_xlabel("dimensione LUT  N"); ax[0].set_ylabel("accuratezza  [%]")
    ax[0].set_title("Accuratezza params (60 traj)")
    ax[0].set_xticks(N); ax[0].set_xticklabels([str(n) for n in N])
    lo = min(acc); ax[0].set_ylim(lo - 0.3, max(acc) + 0.3)

    # (2) errore d'interpolazione dmax vs LUT-512 — convergenza quadratica
    dd = [(n, d) for n, d in zip(N, dmax) if d > 0]
    ax[1].loglog([n for n, _ in dd], [d for _, d in dd], "s-", base=2, color="#d62728")
    ax[1].set_xlabel("dimensione LUT  N"); ax[1].set_ylabel("dmax vs LUT-512")
    ax[1].set_title("Errore d'interpolazione")
    ax[1].set_xticks([n for n, _ in dd]); ax[1].set_xticklabels([str(n) for n, _ in dd])

    # (3) risorse HW vs N (se disponibili)
    if hw:
        hN = [int(r["N"]) for r in hw]
        lut = [int(r["LUT"]) for r in hw]
        ff = [int(r.get("FF", 0)) for r in hw]
        ax[2].semilogx(hN, lut, "o-", base=2, color="#2ca02c", label="LUT")
        if any(ff):
            ax[2].semilogx(hN, ff, "^--", base=2, color="#9467bd", label="FF")
        ax[2].set_xlabel("dimensione LUT  N"); ax[2].set_ylabel("celle (Zynq-7020, OOC)")
        ax[2].set_title("Risorse sintesi Vivado")
        ax[2].set_xticks(hN); ax[2].set_xticklabels([str(n) for n in hN])
        ax[2].legend()

    fig.tight_layout()
    fig.savefig(OUT, dpi=140, facecolor="white")
    print("scritto", OUT, "(%d pannelli)" % npanels)


if __name__ == "__main__":
    main()
