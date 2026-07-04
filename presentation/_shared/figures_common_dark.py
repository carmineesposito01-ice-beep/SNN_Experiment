"""Shared DARK figure style for the CF_FSNN deck (antracite theme, colorblind-safe).

Every dark data figure imports this so the deck reads as one designed system.
"""
import matplotlib.pyplot as plt
import pandas as pd

# Panel background = the slide's .vis panel colour, so figures sit seamlessly on it.
BG = "#15181D"
INK = "#C7D0DA"       # axis labels / ticks
INK_MUTED = "#8A939D"
SPINE = "#39424D"
GRID = "#2C333C"
SAFE = "#2ECC71"      # ρ<1 safe zone / positive
DANGER = "#E0563B"    # danger / expansive
ACCENT = "#56B4E9"    # generic "look-here" (blue)

# Champion identity (brightened for the dark background) + redundant marker/linestyle.
_CHAMPION = {
    "Raffaello":       dict(color="#E06A2C", linestyle="--", marker="o", label="Raffaello (BPTT)"),
    "Leonardo":        dict(color="#4AA3E0", linestyle="-",  marker="s", label="Leonardo (BPTT)"),
    "Donatello":       dict(color="#D48AC0", linestyle="-",  marker="^", label="Donatello (EventProp)"),
    "Michelangelo":    dict(color="#F0AE3A", linestyle="-.", marker="D", label="Michelangelo (EventProp)"),
    "Master Splinter": dict(color="#9AA3AD", linestyle=":",  marker="X", label="Oracolo"),
}
# Okabe-Ito-ish categorical ramp (brightened) for non-champion series.
CAT = ["#56B4E9", "#2ECC71", "#F0AE3A", "#D48AC0", "#E06A2C", "#9AA3AD", "#7FD9A6"]


def champion_style(name: str) -> dict:
    return dict(_CHAMPION[name])


def apply_dark_style() -> None:
    """Dark rcParams for projected slides: dark panel, light text, de-junked."""
    plt.rcParams.update({
        "figure.figsize": (7.4, 4.4), "figure.dpi": 150, "savefig.dpi": 150,
        "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
        "text.color": INK, "axes.labelcolor": INK, "axes.titlecolor": "#EAF1F7",
        "xtick.color": INK, "ytick.color": INK,
        "axes.edgecolor": SPINE, "axes.linewidth": 0.8,
        "font.size": 15, "axes.titlesize": 16, "axes.labelsize": 14,
        "xtick.labelsize": 12, "ytick.labelsize": 12, "legend.fontsize": 12,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.alpha": 0.6,
        "lines.linewidth": 2.4, "lines.markersize": 9,
        "savefig.bbox": "tight", "figure.autolayout": True,
    })


def style_legend(ax, **kw):
    """A legend that reads on dark."""
    leg = ax.legend(facecolor=BG, edgecolor=SPINE, labelcolor=INK, framealpha=0.85, **kw)
    return leg


def load_csv(repo_root, rel_path: str) -> pd.DataFrame:
    import pathlib
    return pd.read_csv(pathlib.Path(repo_root) / rel_path)
