"""Stile condiviso per le figure della presentazione CF_FSNN (palco + color-blind safe)."""
import matplotlib.pyplot as plt
import pandas as pd

OKABE_ITO = {
    "black": "#000000", "orange": "#E69F00", "sky": "#56B4E9", "green": "#009E73",
    "yellow": "#F0E442", "blue": "#0072B2", "vermillion": "#D55E00", "purple": "#CC79A7",
}
ACCENT = OKABE_ITO["green"]

_CHAMPION_STYLE = {
    "Raffaello":       dict(color=OKABE_ITO["vermillion"], linestyle="--", marker="X", label="Raffaello (BPTT)"),
    "Leonardo":        dict(color=OKABE_ITO["blue"],       linestyle="-",  marker="s", label="Leonardo (BPTT)"),
    "Donatello":       dict(color=OKABE_ITO["purple"],     linestyle="-",  marker="o", label="Donatello (EventProp)"),
    "Michelangelo":    dict(color=OKABE_ITO["orange"],     linestyle="-.", marker="^", label="Michelangelo (EventProp)"),
    "Master Splinter": dict(color=OKABE_ITO["black"],      linestyle=":",  marker="D", label="Oracolo"),
}

def champion_style(name: str) -> dict:
    return dict(_CHAMPION_STYLE[name])

def apply_stage_style() -> None:
    plt.rcParams.update({
        "figure.figsize": (10, 5.6), "figure.dpi": 140, "savefig.dpi": 140,
        "font.size": 18, "axes.titlesize": 20, "axes.labelsize": 18,
        "xtick.labelsize": 15, "ytick.labelsize": 15, "legend.fontsize": 15,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.25, "lines.linewidth": 2.5, "lines.markersize": 9,
        "savefig.bbox": "tight", "figure.autolayout": True,
    })

def load_csv(repo_root, rel_path: str) -> pd.DataFrame:
    import pathlib
    return pd.read_csv(pathlib.Path(repo_root) / rel_path)
