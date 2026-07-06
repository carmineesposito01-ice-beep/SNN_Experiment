"""pinn_loop.gif — the PINN closed loop, animated.

Trajectory -> SNN -> 5 params -> ACC-IIDM -> a_hat -> (compare a_obs) -> Loss
-> gradient back to the SNN. A token travels the loop and lights up each stage.
Big legible labels, dark palette. matplotlib -> GIF via Pillow (no manim/ffmpeg).
"""
import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.animation import FuncAnimation, PillowWriter

OUT = pathlib.Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/assets/manim"
OUT.mkdir(parents=True, exist_ok=True)

BG="#15181D"; TEXT="#DCE3EA"; MUTED="#8A939D"; EDGE="#39424D"
GREEN="#2ECC71"; BLUE="#56B4E9"; AMBER="#F0B429"; PURPLE="#D48AC0"; DIM="#20252C"

# nodes: (x, y, w, h, label, color)
N = {
    "traj":  (0.10, 0.70, 0.16, 0.14, "traiettoria\n(V2X)", BLUE),
    "snn":   (0.42, 0.70, 0.16, 0.14, "SNN", GREEN),
    "par":   (0.74, 0.70, 0.20, 0.14, "5 parametri\n[v0,T,s0,a,b]", AMBER),
    "iidm":  (0.74, 0.42, 0.20, 0.14, "ACC-IIDM\n(fisica)", BLUE),
    "ahat":  (0.42, 0.42, 0.16, 0.14, r"$\hat a$  vs  $a_{obs}$", TEXT),
    "loss":  (0.10, 0.42, 0.16, 0.14, "Loss  L", PURPLE),
}
# directed edges along the loop (from center to center)
E = [("traj","snn"),("snn","par"),("par","iidm"),("iidm","ahat"),("ahat","loss"),("loss","snn")]
GRAD_EDGE = 5  # index of loss->snn (the gradient arrow)

def center(n): x,y,w,h,_,_=N[n]; return (x+w/2, y+h/2)

fig, ax = plt.subplots(figsize=(7.6,4.3), dpi=150)
fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
ax.set_xlim(0,1.06); ax.set_ylim(0.30,0.92); ax.axis("off")

ax.text(0.53,0.885,"L'anello PINN: la fisica chiude il ciclo",ha="center",
        va="center",color=TEXT,fontsize=15,fontweight="bold")

box_patches={}; label_txt={}
for k,(x,y,w,h,lab,col) in N.items():
    p=FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.008,rounding_size=0.02",
                     linewidth=2.2,edgecolor=col,facecolor=DIM,mutation_aspect=1)
    ax.add_patch(p); box_patches[k]=(p,col)
    label_txt[k]=ax.text(x+w/2,y+h/2,lab,ha="center",va="center",color=TEXT,
                         fontsize=12.5,fontweight="bold")

arrows=[]
for i,(a,b) in enumerate(E):
    xa,ya=center(a); xb,yb=center(b)
    col = PURPLE if i==GRAD_EDGE else MUTED
    style = "-|>"
    ar=FancyArrowPatch((xa,ya),(xb,yb),arrowstyle=style,mutation_scale=16,
                       linewidth=2.0 if i==GRAD_EDGE else 1.6,color=col,
                       shrinkA=42,shrinkB=42,
                       connectionstyle="arc3,rad=0" )
    ax.add_patch(ar); arrows.append(ar)
# label the gradient arrow
gx,gy=(center("loss")[0]+center("snn")[0])/2,(center("loss")[1]+center("snn")[1])/2
ax.text(gx,gy-0.055,r"$\nabla$  aggiorna la rete",ha="center",va="center",
        color=PURPLE,fontsize=12,fontweight="bold",style="italic")

token,=ax.plot([],[],"o",ms=15,color="#FFFFFF",zorder=6)
order=["traj","snn","par","iidm","ahat","loss"]

def bezier(a,b,t):
    xa,ya=center(a); xb,yb=center(b)
    return xa+(xb-xa)*t, ya+(yb-ya)*t

FR=len(order)*10
def update(f):
    seg=(f//10)%len(order); t=(f%10)/10.0
    a=order[seg]; b=order[(seg+1)%len(order)]
    x,y=bezier(a,b,t); token.set_data([x],[y])
    for k,(p,col) in box_patches.items():
        active = (k==a)
        p.set_linewidth(3.4 if active else 2.2)
        p.set_facecolor(col if active else DIM)
        label_txt[k].set_color(BG if active else TEXT)
    return [token]

seq=[0]*8+list(range(FR))+[FR-1]*6
anim=FuncAnimation(fig,update,frames=seq,interval=90)
anim.save(str(OUT/"pinn_loop.gif"),writer=PillowWriter(fps=11))
plt.close(fig); print("wrote", OUT/"pinn_loop.gif")
