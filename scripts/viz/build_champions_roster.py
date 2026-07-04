"""champions_roster.png -- STATIC Act-3 opener roster card (dark, matplotlib).

A 4-card champion roster (+ oracle strip), each card headed in the champion's
identity colour, showing: name, method (BPTT/EventProp), rho, accuracy, and a
one-line PER-METRIC character (no bare "best").
"""
import pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = pathlib.Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/figures"
OUT.mkdir(parents=True, exist_ok=True)

# ---- dark palette -----------------------------------------------------------
BG     = "#15181D"
CARD   = "#1B1F26"
TEXT   = "#C7D0DA"
MUTED  = "#8A939D"
SPINE  = "#39424D"
GREEN  = "#2ECC71"
DANGER = "#E0563B"

# champion identity colours
C_RAFF = "#E06A2C"
C_LEON = "#4AA3E0"
C_DONA = "#D48AC0"
C_MICH = "#F0AE3A"
C_ORAC = "#9AA3AD"

# ---- roster data ------------------------------------------------------------
# each: name, subtitle, colour, method, rho, accuracy, deaths, then metric lines
CHAMPS = [
    dict(name="Raffaello", colour=C_RAFF, method="BPTT",
         rho="ρ = 2.99", acc="acc — (baseline)", deaths="31% neuroni morti",
         lines=[("baseline Prodigy aggressivo", TEXT),
                ("debole su v0", DANGER),
                ("il più instabile: ρ alto", MUTED)],
         verdict="BASELINE", verdict_col=MUTED),
    dict(name="Leonardo", colour=C_LEON, method="BPTT",
         rho="ρ = 1.16", acc="val_data = 0.1926", deaths="loss fisica migliore",
         lines=[("miglior loss fisica (val_data)", GREEN),
                ("il più «umano» nel guidare", TEXT),
                ("dinamica morbida, ρ contenuto", MUTED)],
         verdict="MIGLIOR FISICA", verdict_col=C_LEON),
    dict(name="Donatello", colour=C_DONA, method="EventProp",
         rho="ρ = 0.05", acc="accuratezza 84.75%", deaths="0 neuroni morti",
         lines=[("NRMSE minima 0.152", GREEN),
                ("accuratezza massima 84.75%", GREEN),
                ("0 morti · ρ minimo → deploy", GREEN)],
         verdict="CANDIDATO DEPLOY", verdict_col=GREEN),
    dict(name="Michelangelo", colour=C_MICH, method="EventProp",
         rho="ρ = 0.39", acc="runner-up EventProp", deaths="0 neuroni morti",
         lines=[("runner-up EventProp", TEXT),
                ("0 morti, ρ basso", GREEN),
                ("solido ma sotto Donatello", MUTED)],
         verdict="RUNNER-UP", verdict_col=C_MICH),
]

ORACLE = dict(name="Master Splinter", colour=C_ORAC,
              method="oracolo — ACC-IIDM coi parametri veri",
              line="il riferimento: nessun apprendimento, verità di modello "
                   "(v0=30, T=1.2, s0=2, a=1.2, b=2)")

# ---- figure ----------------------------------------------------------------
fig = plt.figure(figsize=(13.2, 7.2), dpi=150)
fig.patch.set_facecolor(BG)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")
ax.set_facecolor(BG)

# header band
ax.text(3.2, 95.5, "I QUATTRO CAMPIONI", color=TEXT, fontsize=22,
        ha="left", va="top", fontweight="bold")
ax.text(3.4, 90.0, "quattro reti allenate, un oracolo di riferimento — chi guida meglio?",
        color=MUTED, fontsize=11.5, ha="left", va="top")
# method legend (top-right)
ax.text(97, 95.0, "BPTT", color=TEXT, fontsize=11, ha="right", va="top", fontweight="bold")
ax.text(97, 91.3, "EventProp", color=TEXT, fontsize=11, ha="right", va="top", fontweight="bold")
ax.text(88.4, 95.0, "■", color="#7A8590", fontsize=11, ha="right", va="top")
ax.text(88.4, 91.3, "■", color=GREEN, fontsize=11, ha="right", va="top")

# ---- champion cards (4 across) ----
n = len(CHAMPS)
margin_l, margin_r = 3.0, 3.0
gap = 2.0
card_top = 84.0
card_bot = 22.0
card_h = card_top - card_bot
usable = 100 - margin_l - margin_r - gap * (n - 1)
card_w = usable / n

def draw_card(x0, c):
    col = c["colour"]
    # card body
    body = FancyBboxPatch((x0, card_bot), card_w, card_h,
                          boxstyle="round,pad=0.15,rounding_size=1.2",
                          fc=CARD, ec=SPINE, lw=1.3, zorder=1)
    ax.add_patch(body)
    # coloured header stripe
    head_h = 9.5
    header = FancyBboxPatch((x0, card_top - head_h), card_w, head_h,
                            boxstyle="round,pad=0.15,rounding_size=1.2",
                            fc=col, ec="none", zorder=2)
    ax.add_patch(header)
    cx = x0 + card_w / 2
    # name
    ax.text(cx, card_top - head_h / 2 + 1.6, c["name"], color="#15181D",
            fontsize=13.5, ha="center", va="center", fontweight="bold", zorder=3)
    # method chip inside header
    m_is_ep = c["method"] == "EventProp"
    ax.text(cx, card_top - head_h / 2 - 2.4, c["method"], color="#15181D",
            fontsize=9.5, ha="center", va="center", fontweight="bold", zorder=3,
            alpha=0.85)

    # big metrics block
    y = card_top - head_h - 5.0
    ax.text(cx, y, c["rho"], color=col, fontsize=17, ha="center", va="top",
            fontweight="bold", zorder=3)
    y -= 6.5
    ax.text(cx, y, c["acc"], color=TEXT, fontsize=11, ha="center", va="top", zorder=3)
    y -= 4.6
    dcol = GREEN if c["deaths"].startswith("0") else (DANGER if "%" in c["deaths"] else MUTED)
    ax.text(cx, y, c["deaths"], color=dcol, fontsize=10, ha="center", va="top", zorder=3)

    # divider
    y -= 3.4
    ax.plot([x0 + 2.2, x0 + card_w - 2.2], [y, y], color=SPINE, lw=1.0, zorder=3)

    # per-metric character lines
    y -= 3.3
    for txt, lc in c["lines"]:
        ax.text(x0 + 2.4, y, "•", color=lc, fontsize=10, ha="left", va="top", zorder=3)
        ax.text(x0 + 4.6, y, txt, color=lc, fontsize=9.6, ha="left", va="top", zorder=3)
        y -= 4.2

    # verdict ribbon at the card bottom
    vy = card_bot + 2.2
    ribbon = FancyBboxPatch((x0 + 2.0, vy - 1.6), card_w - 4.0, 4.2,
                            boxstyle="round,pad=0.1,rounding_size=0.8",
                            fc="none", ec=c["verdict_col"], lw=1.4, zorder=3)
    ax.add_patch(ribbon)
    ax.text(cx, vy + 0.5, c["verdict"], color=c["verdict_col"], fontsize=10.5,
            ha="center", va="center", fontweight="bold", zorder=4)

x = margin_l
for c in CHAMPS:
    draw_card(x, c)
    x += card_w + gap

# ---- oracle strip (bottom, full width) ----
orx, orw = margin_l, 100 - margin_l - margin_r
ory, orh = 6.0, 12.0
ostrip = FancyBboxPatch((orx, ory), orw, orh,
                        boxstyle="round,pad=0.15,rounding_size=1.2",
                        fc=CARD, ec=C_ORAC, lw=1.5, zorder=1)
ax.add_patch(ostrip)
# left badge
badge_w = 20.0
badge = FancyBboxPatch((orx, ory), badge_w, orh,
                       boxstyle="round,pad=0.15,rounding_size=1.2",
                       fc=C_ORAC, ec="none", zorder=2)
ax.add_patch(badge)
ax.text(orx + badge_w / 2, ory + orh / 2 + 1.4, ORACLE["name"], color="#15181D",
        fontsize=12.5, ha="center", va="center", fontweight="bold", zorder=3)
ax.text(orx + badge_w / 2, ory + orh / 2 - 2.6, "ORACOLO", color="#15181D",
        fontsize=9.5, ha="center", va="center", fontweight="bold", zorder=3, alpha=0.85)
# right text
ax.text(orx + badge_w + 3.0, ory + orh / 2 + 1.8, ORACLE["method"], color=TEXT,
        fontsize=11.5, ha="left", va="center", fontweight="bold", zorder=3)
ax.text(orx + badge_w + 3.0, ory + orh / 2 - 2.4, ORACLE["line"], color=MUTED,
        fontsize=10, ha="left", va="center", zorder=3)

# footer note
ax.text(3.2, 2.4, "ρ = rapporto energetico SNN/ANN  ·  accuratezza a tolleranza fissata  ·  "
                  "«morti» = neuroni che non sparano mai",
        color=MUTED, fontsize=8.6, ha="left", va="center")

outpath = OUT / "champions_roster.png"
fig.savefig(outpath, facecolor=BG, dpi=150)
print("OK", outpath)

if __name__ == "__main__":
    pass
