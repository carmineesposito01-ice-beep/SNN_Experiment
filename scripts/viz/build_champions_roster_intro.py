"""champions_roster_intro.png -- SPOILER-FREE Act-3 opener roster (dark, matplotlib).

Same 4 champions (+ oracle) as champions_roster.png, but WITHOUT the verdict
ribbons and superlative one-liners that crown Donatello. Introduces the four
contestants by fact only (method, rho, accuracy); the winner is developed by the
six tiers, not pre-revealed. The full verdict roster is a separate figure used at
the deploy slide.
"""
import pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = pathlib.Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/figures"
OUT.mkdir(parents=True, exist_ok=True)

BG="#15181D"; CARD="#1B1F26"; TEXT="#C7D0DA"; MUTED="#8A939D"; SPINE="#39424D"; GREEN="#2ECC71"
C_RAFF="#E06A2C"; C_LEON="#4AA3E0"; C_DONA="#D48AC0"; C_MICH="#F0AE3A"; C_ORAC="#9AA3AD"

# neutral, factual descriptors only — no ranking, no verdict
CHAMPS = [
    dict(name="Raffaello",   colour=C_RAFF, method="BPTT",      rho="ρ = 2.99", acc="accuratezza 69.34%",
         trait="ricorrenza espansiva (ρ>1)"),
    dict(name="Leonardo",    colour=C_LEON, method="BPTT",      rho="ρ = 1.16", acc="accuratezza 77.53%",
         trait="ricorrenza espansiva (ρ>1)"),
    dict(name="Donatello",   colour=C_DONA, method="EventProp", rho="ρ = 0.05", acc="accuratezza 84.75%",
         trait="ricorrenza contrattiva (ρ<1)"),
    dict(name="Michelangelo",colour=C_MICH, method="EventProp", rho="ρ = 0.39", acc="accuratezza 79.18%",
         trait="ricorrenza contrattiva (ρ<1)"),
]
ORACLE = dict(name="Master Splinter", colour=C_ORAC,
              method="oracolo — ACC-IIDM coi parametri veri",
              line="il riferimento: nessun apprendimento, verità di modello (v0=30, T=1.2, s0=2, a=1.2, b=2)")

fig = plt.figure(figsize=(13.2, 7.2), dpi=150)
fig.patch.set_facecolor(BG)
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off"); ax.set_facecolor(BG)

ax.text(3.2, 95.5, "I QUATTRO CANDIDATI", color=TEXT, fontsize=22, ha="left", va="top", fontweight="bold")
ax.text(3.4, 90.0, "quattro reti allenate, un oracolo di riferimento — chi guida meglio lo dicono i sei livelli",
        color=MUTED, fontsize=11.5, ha="left", va="top")
ax.text(97, 95.0, "BPTT", color=TEXT, fontsize=11, ha="right", va="top", fontweight="bold")
ax.text(97, 91.3, "EventProp", color=TEXT, fontsize=11, ha="right", va="top", fontweight="bold")
ax.text(88.4, 95.0, "■", color="#7A8590", fontsize=11, ha="right", va="top")
ax.text(88.4, 91.3, "■", color=GREEN, fontsize=11, ha="right", va="top")

n=len(CHAMPS); margin_l=margin_r=3.0; gap=2.0
card_top=84.0; card_bot=24.0; card_h=card_top-card_bot
card_w=(100-margin_l-margin_r-gap*(n-1))/n

def draw_card(x0, c):
    col=c["colour"]
    ax.add_patch(FancyBboxPatch((x0,card_bot),card_w,card_h,boxstyle="round,pad=0.15,rounding_size=1.2",
                                fc=CARD,ec=SPINE,lw=1.3,zorder=1))
    head_h=9.5
    ax.add_patch(FancyBboxPatch((x0,card_top-head_h),card_w,head_h,boxstyle="round,pad=0.15,rounding_size=1.2",
                                fc=col,ec="none",zorder=2))
    cx=x0+card_w/2
    ax.text(cx,card_top-head_h/2+1.6,c["name"],color="#15181D",fontsize=13.5,ha="center",va="center",fontweight="bold",zorder=3)
    ax.text(cx,card_top-head_h/2-2.4,c["method"],color="#15181D",fontsize=9.5,ha="center",va="center",fontweight="bold",zorder=3,alpha=0.85)
    y=card_top-head_h-6.5
    ax.text(cx,y,c["rho"],color=col,fontsize=18,ha="center",va="top",fontweight="bold",zorder=3)
    y-=8.0
    ax.text(cx,y,c["acc"],color=TEXT,fontsize=11.5,ha="center",va="top",zorder=3)
    y-=5.2
    ax.plot([x0+2.2,x0+card_w-2.2],[y,y],color=SPINE,lw=1.0,zorder=3)
    y-=5.0
    ax.text(cx,y,c["trait"],color=MUTED,fontsize=9.6,ha="center",va="top",zorder=3)

x=margin_l
for c in CHAMPS:
    draw_card(x,c); x+=card_w+gap

orx,orw=margin_l,100-margin_l-margin_r; ory,orh=6.0,12.0
ax.add_patch(FancyBboxPatch((orx,ory),orw,orh,boxstyle="round,pad=0.15,rounding_size=1.2",fc=CARD,ec=C_ORAC,lw=1.5,zorder=1))
badge_w=20.0
ax.add_patch(FancyBboxPatch((orx,ory),badge_w,orh,boxstyle="round,pad=0.15,rounding_size=1.2",fc=C_ORAC,ec="none",zorder=2))
ax.text(orx+badge_w/2,ory+orh/2+1.4,ORACLE["name"],color="#15181D",fontsize=12.5,ha="center",va="center",fontweight="bold",zorder=3)
ax.text(orx+badge_w/2,ory+orh/2-2.6,"ORACOLO",color="#15181D",fontsize=9.5,ha="center",va="center",fontweight="bold",zorder=3,alpha=0.85)
ax.text(orx+badge_w+3.0,ory+orh/2+1.8,ORACLE["method"],color=TEXT,fontsize=11.5,ha="left",va="center",fontweight="bold",zorder=3)
ax.text(orx+badge_w+3.0,ory+orh/2-2.4,ORACLE["line"],color=MUTED,fontsize=10,ha="left",va="center",zorder=3)

ax.text(3.2,2.4,"ρ = raggio spettrale della ricorrenza  ·  accuratezza a tolleranza fissata  ·  "
                "il verdetto arriva dopo i sei livelli",color=MUTED,fontsize=8.6,ha="left",va="center")

outpath=OUT/"champions_roster_intro.png"
fig.savefig(outpath,facecolor=BG,dpi=150)
print("OK",outpath)
