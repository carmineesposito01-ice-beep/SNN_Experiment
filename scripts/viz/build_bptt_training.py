"""bptt_training.gif — how the network is trained in the BPTT+surrogate pipeline.

Two clear ideas, one panel:
 (top)  the SNN is UNROLLED over T ticks; a forward wave passes L->R, then the
        BPTT gradient wave passes R->L (backprop through time).
 (bottom) the Heaviside step's derivative is a DEAD CLIFF (0 almost everywhere);
        a smooth SURROGATE bell bridges it so a gradient "ball" can roll down and
        the loss (inset) descends. Big legible labels, dark palette.
matplotlib -> GIF via Pillow (no manim/ffmpeg).
"""
import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.animation import FuncAnimation, PillowWriter

OUT = pathlib.Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/assets/manim"
OUT.mkdir(parents=True, exist_ok=True)

BG="#15181D"; TEXT="#DCE3EA"; MUTED="#8A939D"; EDGE="#39424D"
GREEN="#2ECC71"; AMBER="#F0B429"; BLUE="#56B4E9"; DANGER="#E0563B"; DIM="#20252C"

fig,(axt,axb)=plt.subplots(2,1,figsize=(7.6,4.3),dpi=150,
                           gridspec_kw=dict(height_ratios=[1,1.5],hspace=0.42))
fig.patch.set_facecolor(BG)
for a in (axt,axb): a.set_facecolor(BG); a.axis("off")

# ---------- TOP: unrolled ticks + forward/backward waves ----------
T=6; xs=np.linspace(0.10,0.90,T); yb=0.5
boxes=[]
for i,x in enumerate(xs):
    p=FancyBboxPatch((x-0.045,yb-0.16),0.09,0.32,boxstyle="round,pad=0.005,rounding_size=0.03",
                     lw=2,edgecolor=EDGE,facecolor=DIM,transform=axt.transAxes)
    axt.add_patch(p); boxes.append(p)
    axt.text(x,yb-0.34,f"t{i+1}",ha="center",va="center",color=MUTED,fontsize=11,transform=axt.transAxes)
for i in range(T-1):
    axt.annotate("",xy=(xs[i+1]-0.05,yb),xytext=(xs[i]+0.05,yb),xycoords=axt.transAxes,
                 textcoords=axt.transAxes,arrowprops=dict(arrowstyle="-|>",color=EDGE,lw=1.4))
axt.text(0.5,0.98,"BPTT: la rete è srotolata su T tick",ha="center",va="top",
         color=TEXT,fontsize=14,fontweight="bold",transform=axt.transAxes)
wave_txt=axt.text(0.5,-0.02,"",ha="center",va="bottom",color=TEXT,fontsize=12,
                  fontweight="bold",transform=axt.transAxes)

# ---------- BOTTOM: dead cliff + surrogate bell + rolling ball ----------
axb.set_xlim(-3,3); axb.set_ylim(-0.15,1.15)
v=np.linspace(-3,3,400)
axb.plot(v,(v>=0).astype(float),color=DANGER,lw=2.4)        # Heaviside step S
axb.plot(v[v<0],np.zeros_like(v[v<0]),color=DANGER,lw=5,alpha=0.55)  # dead flat (grad 0)
axb.plot(v[v>0],np.ones_like(v[v>0]),color=DANGER,lw=5,alpha=0.55)
bell=1/(1+1.4*np.abs(v))**2
axb.plot(v,bell,color=AMBER,lw=2.6)                          # surrogate bell
axb.text(-2.7,0.92,"gradino S = H(V−θ)",color=DANGER,fontsize=11.5,fontweight="bold")
axb.text(1.05,0.86,"surrogato σ′\n(colma il gradino)",color=AMBER,fontsize=11.5,fontweight="bold")
ball,=axb.plot([],[],"o",ms=15,color="#FFFFFF",zorder=6)

# loss inset
axl=fig.add_axes([0.68,0.09,0.24,0.20]); axl.set_facecolor(DIM)
for s in axl.spines.values(): s.set_color(EDGE)
axl.tick_params(colors=MUTED,labelsize=7); axl.set_xticks([]); axl.set_yticks([])
axl.set_title("loss",color=MUTED,fontsize=9,pad=2)
ep=np.arange(60); loss=0.9*np.exp(-ep/22)+0.12+0.03*np.sin(ep/2.2)*np.exp(-ep/30)
lline,=axl.plot([],[],color=GREEN,lw=2); axl.set_xlim(0,60); axl.set_ylim(0.08,1.05)

def surro(x): return 1/(1+1.4*abs(x))**2
def update(f):
    ph=f%40
    if ph<16:            # forward wave L->R
        k=int(ph/16*(T));
        for i,p in enumerate(boxes): p.set_facecolor(GREEN if i<=k else DIM); p.set_edgecolor(GREEN if i<=k else EDGE)
        wave_txt.set_text("forward →"); wave_txt.set_color(GREEN)
    else:                # backward gradient wave R->L
        k=int((ph-16)/16*(T))
        for i,p in enumerate(boxes): p.set_facecolor(AMBER if i>=T-1-k else DIM); p.set_edgecolor(AMBER if i>=T-1-k else EDGE)
        wave_txt.set_text("← gradiente indietro nel tempo"); wave_txt.set_color(AMBER)
    # ball rolling down the surrogate slope toward 0
    bx=2.4-4.8*((f%40)/40.0); bx=max(bx,0.02); ball.set_data([bx],[surro(bx)])
    n=min(60,3+f); lline.set_data(ep[:n],loss[:n])
    return [ball,lline,wave_txt]

seq=list(range(80))
anim=FuncAnimation(fig,update,frames=seq,interval=80)
anim.save(str(OUT/"bptt_training.gif"),writer=PillowWriter(fps=12))
plt.close(fig); print("wrote", OUT/"bptt_training.gif")
