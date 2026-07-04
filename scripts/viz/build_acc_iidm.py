"""acc_iidm.gif -- which equation drives the follower's acceleration, moment to moment.

Dark instant-comprehension animation (matplotlib -> GIF via Pillow; no manim/ffmpeg).

TOP: a two-car strip (leader + follower) driving a scripted scenario
     (constant cruise -> leader brakes hard -> a cut-in vehicle appears).
BOTTOM-LEFT: a live acceleration bar whose colour = the ACTIVE ACC-IIDM regime
     - free-flow  (z<1)  : green-ish (v_free term dominates)
     - car-following (z>=1): teal (interaction term dominates)
     - CAH flash          : danger red when the constant-acceleration-heuristic
                            takes over during hard leader braking.
RIGHT: the FULL ACC-IIDM equation set as a static mono side-panel (model shown exhaustively).

The follower's motion is obtained by integrating the ACC-IIDM ODE against the
scripted leader profile.
"""
import pathlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.animation import FuncAnimation, PillowWriter

OUT = pathlib.Path(__file__).resolve().parents[2] / "presentation/cf_fsnn_thesis/assets/manim"
OUT.mkdir(parents=True, exist_ok=True)

# ---- dark palette -----------------------------------------------------------
BG      = "#15181D"
TEXT    = "#C7D0DA"
MUTED   = "#8A939D"
SPINE   = "#39424D"
BLUE    = "#56B4E9"   # membrane / follower body
GREEN   = "#2ECC71"   # free-flow regime / SAFE
AMBER   = "#F0B429"   # car-following regime / threshold
DANGER  = "#E0563B"   # CAH flash / hard braking

# ---- ACC-IIDM parameters (plausible) ---------------------------------------
V0 = 30.0     # desired speed (m/s)
T_ = 1.2      # desired time gap (s)
S0 = 2.0      # minimum jam distance (m)
A_ = 1.2      # comfortable acceleration (m/s^2)
B_ = 2.0      # comfortable deceleration (m/s^2)
C_ = 0.99     # CAH blend coefficient
A_MIN = -9.0  # physical accel clamp lower bound
DT = 0.1      # integration step (s)

def clamp(x, lo):
    return max(x, lo)

def acc_iidm_step(v, gap, v_lead, a_lead):
    """One ACC-IIDM acceleration evaluation.

    Returns (a_cmd, regime) where regime in {'free','follow','cah'} labels
    which term currently drives the acceleration.
    """
    dv = v - v_lead                      # closing speed (positive = approaching)
    # desired dynamic gap s*
    s_star = S0 + max(0.0, v * T_ + v * dv / (2.0 * np.sqrt(A_ * B_)))
    g = clamp(gap, 2.0)
    z = s_star / g                       # regime indicator

    a_free = A_ * (1.0 - (v / V0) ** 4)  # free-flow (desired-speed) term

    # IIDM regimes
    if v <= V0:
        if z >= 1.0:
            a_iidm = A_ * (1.0 - z * z)                       # car-following
        else:
            a_iidm = a_free * (1.0 - z ** (2.0 * A_ / max(a_free, 1e-6)))
    else:
        a_free = -B_ * (1.0 - (V0 / v) ** (A_ * 2.0)) if v > V0 else a_free
        if z >= 1.0:
            a_iidm = a_free + A_ * (1.0 - z * z)
        else:
            a_iidm = a_free

    # CAH -- constant-acceleration heuristic (kicks in on hard leader braking)
    denom = v * v - 2.0 * g * a_lead
    if v_lead * (v - v_lead) <= -2.0 * g * a_lead and abs(denom) > 1e-6:
        a_cah = (v * v * a_lead) / denom
    else:
        a_cah = a_lead - (max(0.0, dv) ** 2) / (2.0 * clamp(gap, 2.0))

    # blend IIDM with CAH
    if a_iidm >= a_cah:
        a = a_iidm
        driving = 'follow' if z >= 1.0 else 'free'
    else:
        a = (1.0 - C_) * a_iidm + C_ * (a_cah + B_ * np.tanh((a_iidm - a_cah) / B_))
        driving = 'cah'

    a = min(max(a, A_MIN), A_)
    return a, driving

# ---- scripted leader profile & follower integration ------------------------
def simulate():
    steps = 150                          # 15 s scenario
    xs_l, xs_f, vs_l, vs_f = [], [], [], []
    accs, regimes, gaps = [], [], []
    cutin_flags = []

    # leader kinematics
    xl, vl = 45.0, 22.0                  # leader starts 45 m ahead at 22 m/s
    # follower kinematics
    xf, vf = 0.0, 22.0

    for k in range(steps):
        t = k * DT
        # --- scripted leader acceleration ---
        if t < 4.0:
            al = 0.0                                     # constant cruise
        elif t < 6.5:
            al = -6.0                                    # HARD brake -> triggers CAH
        elif t < 8.0:
            al = 0.0                                     # hold low speed
        else:
            al = 1.0                                     # gentle re-accel
        vl = max(0.0, vl + al * DT)
        xl += vl * DT

        # --- cut-in event: at t>=9s a slower car slots in, shrinking the gap ---
        cutin = t >= 9.0
        if cutin:
            eff_lead_x = xl - 11.0        # cut-in vehicle 11 m closer than leader
            eff_lead_v = min(vl, 16.0)    # and slower
            eff_lead_a = 0.0
        else:
            eff_lead_x, eff_lead_v, eff_lead_a = xl, vl, al

        gap = eff_lead_x - xf - 4.5       # bumper gap (4.5 m car length)
        a_f, reg = acc_iidm_step(vf, gap, eff_lead_v, eff_lead_a)

        # integrate follower
        vf = max(0.0, vf + a_f * DT)
        xf += vf * DT

        xs_l.append(xl); xs_f.append(xf); vs_l.append(vl); vs_f.append(vf)
        accs.append(a_f); regimes.append(reg); gaps.append(gap)
        cutin_flags.append(cutin)

    return dict(xl=xs_l, xf=xs_f, vl=vs_l, vf=vs_f,
                acc=accs, reg=regimes, gap=gaps, cutin=cutin_flags,
                cutin_x=[xl_ - 14.0 for xl_ in xs_l])

DATA = simulate()
N = len(DATA["acc"])

# ---- figure ----------------------------------------------------------------
fig = plt.figure(figsize=(11, 6.2), dpi=100)
fig.patch.set_facecolor(BG)
# layout: road strip (top wide), accel bar (bottom-left), equation panel (right)
gs = fig.add_gridspec(2, 2, width_ratios=[2.0, 1.15], height_ratios=[1.0, 1.15],
                      left=0.055, right=0.985, top=0.93, bottom=0.10,
                      wspace=0.16, hspace=0.34)
ax_road = fig.add_subplot(gs[0, 0])
ax_bar  = fig.add_subplot(gs[1, 0])
ax_eq   = fig.add_subplot(gs[:, 1])

for ax in (ax_road, ax_bar, ax_eq):
    ax.set_facecolor(BG)

# --- road strip axes ---
ROAD_W = 170.0
ax_road.set_xlim(0, ROAD_W)
ax_road.set_ylim(-1.6, 1.6)
ax_road.set_yticks([])
ax_road.set_xlabel("posizione lungo la corsia (m) — vista che segue il follower", color=MUTED, fontsize=9)
ax_road.tick_params(colors=MUTED, labelsize=8)
for s in ax_road.spines.values():
    s.set_color(SPINE)
# lane markings
ax_road.axhline(-1.0, color=SPINE, lw=1.2)
ax_road.axhline(1.0, color=SPINE, lw=1.2)
for xdash in range(0, int(ROAD_W), 12):
    ax_road.plot([xdash, xdash + 6], [0, 0], color=SPINE, lw=1.0, alpha=0.6)

CAR_W, CAR_H = 8.5, 1.1
follower_car = FancyBboxPatch((0, -CAR_H / 2), CAR_W, CAR_H,
                              boxstyle="round,pad=0.02,rounding_size=0.4",
                              fc=BLUE, ec="white", lw=1.0, zorder=5)
leader_car = FancyBboxPatch((0, -CAR_H / 2), CAR_W, CAR_H,
                            boxstyle="round,pad=0.02,rounding_size=0.4",
                            fc=MUTED, ec="white", lw=1.0, zorder=5)
cutin_car = FancyBboxPatch((0, -CAR_H / 2), CAR_W, CAR_H,
                           boxstyle="round,pad=0.02,rounding_size=0.4",
                           fc=AMBER, ec="white", lw=1.0, zorder=6, alpha=0.0)
ax_road.add_patch(follower_car)
ax_road.add_patch(leader_car)
ax_road.add_patch(cutin_car)
lab_follower = ax_road.text(0, -1.35, "FOLLOWER (SNN)", color=BLUE, fontsize=8,
                            ha="center", va="top", fontweight="bold")
lab_leader = ax_road.text(0, 1.32, "LEADER", color=TEXT, fontsize=8,
                          ha="center", va="bottom", fontweight="bold")
lab_cutin = ax_road.text(0, 1.32, "CUT-IN", color=AMBER, fontsize=8,
                         ha="center", va="bottom", fontweight="bold", alpha=0.0)
# gap bracket + text
gap_line, = ax_road.plot([], [], color=TEXT, lw=1.2, alpha=0.8, zorder=4)
gap_txt = ax_road.text(0, 0.55, "", color=TEXT, fontsize=8, ha="center", va="bottom")

# --- acceleration bar axes ---
ax_bar.set_xlim(A_MIN - 0.5, A_ + 0.6)
ax_bar.set_ylim(-0.75, 0.75)
ax_bar.set_yticks([])
ax_bar.set_xlabel("accelerazione del follower  a  (m/s²)", color=TEXT, fontsize=10)
ax_bar.tick_params(colors=MUTED, labelsize=8)
for s in ax_bar.spines.values():
    s.set_color(SPINE)
ax_bar.spines["left"].set_visible(False)
ax_bar.spines["top"].set_visible(False)
ax_bar.axvline(0, color=MUTED, lw=1.0, ls=":")
# comfortable band markers
ax_bar.axvline(-B_, color=SPINE, lw=1.0, ls="--")
ax_bar.text(-B_, 0.62, "−b", color=MUTED, fontsize=8, ha="center")
ax_bar.text(A_, 0.62, "a", color=MUTED, fontsize=8, ha="center")
ax_bar.axvline(A_MIN, color=SPINE, lw=1.0, ls="--")
ax_bar.text(A_MIN, 0.62, "−9 (clamp)", color=MUTED, fontsize=7.5, ha="left")

accel_bar = Rectangle((0, -0.28), 0, 0.56, fc=GREEN, ec="none", zorder=3)
ax_bar.add_patch(accel_bar)
regime_txt = ax_bar.text(A_MIN - 0.35, -0.6, "", color=TEXT, fontsize=9.5,
                         ha="left", va="center", fontweight="bold")
accval_txt = ax_bar.text(A_ + 0.45, -0.6, "", color=TEXT, fontsize=9.5,
                         ha="right", va="center", family="monospace")
clock_txt = ax_road.text(ROAD_W - 2, -1.35, "", color=MUTED, fontsize=8.5, ha="right", va="top",
                         family="monospace")

# --- equation side-panel (static, exhaustive) ---
ax_eq.axis("off")
ax_eq.set_xlim(0, 1)
ax_eq.set_ylim(0, 1)
panel = FancyBboxPatch((0.01, 0.01), 0.98, 0.98,
                       boxstyle="round,pad=0.01,rounding_size=0.02",
                       fc="#1B1F26", ec=SPINE, lw=1.2, transform=ax_eq.transAxes, zorder=0)
ax_eq.add_patch(panel)
ax_eq.text(0.5, 0.965, "MODELLO ACC-IIDM", color=TEXT, fontsize=10.5,
           ha="center", va="top", fontweight="bold", transform=ax_eq.transAxes)

eq_lines = [
    (r"$s^*=s_0+\max(0,\ vT+\frac{v\,\Delta v}{2\sqrt{ab}})$", TEXT),
    (r"$a_{free}=a\,(1-(v/v_0)^4)$", GREEN),
    (r"$z=s^*/\max(g,\,2)$   (indicatore regime)", TEXT),
    ("REGIMI IIDM:", MUTED),
    (r"$z<1:\ a_{free}\,[1-z^{2a/a_{free}}]$", GREEN),
    (r"$z\geq 1:\ a\,(1-z^2)$   (car-following)", AMBER),
    ("EURISTICA CAH (frenata forte):", MUTED),
    (r"$a_{CAH}=\min(a_\ell,a)-\frac{ReLU(\Delta v)^2}{2\max(g,2)}$", DANGER),
    (r"$a=(1-c)\,a_{IIDM}+c\,a_{CAH}$", DANGER),
    (r"clamp:  $a\in[-9,\ a]$", TEXT),
    ("PARAMETRI (Master Splinter):", MUTED),
    (r"$v_0=30 \quad T=1.2 \quad s_0=2$", TEXT),
    (r"$a=1.2 \quad b=2 \quad c=0.99$", TEXT),
]
y = 0.905
for txt, col in eq_lines:
    size = 8.6 if txt.startswith("$") else 8.0
    weight = "bold" if not txt.startswith("$") else "normal"
    ax_eq.text(0.055, y, txt, color=col, fontsize=size, ha="left", va="top",
               transform=ax_eq.transAxes, fontweight=weight)
    y -= 0.066 if txt.startswith("$") else 0.052

# small legend of regime colours in the panel (each square coloured separately)
ax_eq.text(0.055, 0.075, "■", color=GREEN, fontsize=8, ha="left", va="bottom",
           transform=ax_eq.transAxes)
ax_eq.text(0.085, 0.075, "flusso libero", color=TEXT, fontsize=7.6, ha="left", va="bottom",
           transform=ax_eq.transAxes)
ax_eq.text(0.36, 0.075, "■", color=AMBER, fontsize=8, ha="left", va="bottom",
           transform=ax_eq.transAxes)
ax_eq.text(0.39, 0.075, "car-following", color=TEXT, fontsize=7.6, ha="left", va="bottom",
           transform=ax_eq.transAxes)
ax_eq.text(0.70, 0.075, "■", color=DANGER, fontsize=8, ha="left", va="bottom",
           transform=ax_eq.transAxes)
ax_eq.text(0.73, 0.075, "CAH", color=TEXT, fontsize=7.6, ha="left", va="bottom",
           transform=ax_eq.transAxes)

fig.suptitle("", color=TEXT)  # no title inside; slide supplies it

REG_COLOR = {"free": GREEN, "follow": AMBER, "cah": DANGER}
REG_LABEL = {"free": "FLUSSO LIBERO  (z<1)",
             "follow": "CAR-FOLLOWING  (z≥1)",
             "cah": "⚡ CAH — FRENATA D'EMERGENZA"}

# camera follows the follower; leader/cut-in drawn relative
def camera_x(k):
    return DATA["xf"][k] - 20.0

def render(k):
    cx = camera_x(k)
    xf = DATA["xf"][k] - cx
    xl = DATA["xl"][k] - cx
    xc = DATA["cutin_x"][k] - cx
    follower_car.set_x(xf - CAR_W / 2)
    leader_car.set_x(xl - CAR_W / 2)
    lab_follower.set_x(xf); lab_leader.set_x(xl)

    cutin_on = DATA["cutin"][k]
    if cutin_on:
        cutin_car.set_alpha(0.95); lab_cutin.set_alpha(1.0)
        cutin_car.set_x(xc - CAR_W / 2); lab_cutin.set_x(xc)
        # dim the real leader when cut-in is the active obstacle; nudge its label
        # rightward so it never collides with the CUT-IN label to its left
        leader_car.set_alpha(0.35); lab_leader.set_alpha(0.45)
        lab_leader.set_y(1.32); lab_leader.set_x(xl + 9)
    else:
        cutin_car.set_alpha(0.0); lab_cutin.set_alpha(0.0)
        leader_car.set_alpha(1.0); lab_leader.set_alpha(1.0)
        lab_leader.set_y(1.32)

    # gap bracket between follower nose and the active obstacle rear
    obst_x = xc if cutin_on else xl
    fx_nose = xf + CAR_W / 2
    ox_rear = obst_x - CAR_W / 2
    gap_line.set_data([fx_nose, ox_rear], [0.42, 0.42])
    gap_txt.set_position(((fx_nose + ox_rear) / 2, 0.5))
    gap_txt.set_text(f"gap ≈ {max(DATA['gap'][k],0):.1f} m")

    a = DATA["acc"][k]; reg = DATA["reg"][k]
    col = REG_COLOR[reg]
    if a >= 0:
        accel_bar.set_x(0); accel_bar.set_width(a)
    else:
        accel_bar.set_x(a); accel_bar.set_width(-a)
    accel_bar.set_fc(col)
    # CAH flash: pulse edge + brighter face on emergency frames
    if reg == "cah":
        accel_bar.set_ec("white"); accel_bar.set_linewidth(2.2)
    else:
        accel_bar.set_ec("none"); accel_bar.set_linewidth(0)
    regime_txt.set_text(REG_LABEL[reg]); regime_txt.set_color(col)
    accval_txt.set_text(f"a = {a:+.2f} m/s²")

    clock_txt.set_text(f"t = {k*DT:4.1f} s   v_f={DATA['vf'][k]:4.1f}  v_l={DATA['vl'][k]:4.1f} m/s")

    return (follower_car, leader_car, cutin_car, accel_bar, gap_line, gap_txt,
            regime_txt, accval_txt, clock_txt, lab_follower, lab_leader, lab_cutin)

# poster frame: during the cut-in with CAH flashing. Find first CAH-during-cutin
# else first CAH; guarantees a meaningful static fallback at frame 0.
poster = next((i for i in range(N) if DATA["reg"][i] == "cah" and DATA["cutin"][i]), None)
if poster is None:
    poster = next((i for i in range(N) if DATA["reg"][i] == "cah"), N // 2)

# frame order: POSTER-FIRST hold, then build-up (every 2nd sim step for size),
# but keep the CAH/cut-in window dense so the emergency reads clearly.
build = []
for i in range(N):
    dense = (35 <= i <= N - 1)          # keep braking+cut-in window full-rate
    if dense or i % 2 == 0:
        build.append(i)
frames = [poster] * 8 + build + [N - 1] * 14

def frame(fi):
    return render(frames[fi])

anim = FuncAnimation(fig, frame, frames=len(frames), interval=62, blit=False)
outpath = OUT / "acc_iidm.gif"
anim.save(outpath, writer=PillowWriter(fps=16), savefig_kwargs={"facecolor": BG})

# Re-encode toward the 1-2 MB target: quantize to a compact adaptive palette
# and let Pillow diff frames (optimize) with in-place disposal.
from PIL import Image, ImageSequence
im = Image.open(outpath)
dur = im.info.get("duration", 62)
base = None
fr = []
for f in ImageSequence.Iterator(im):
    rgb = f.convert("RGB")
    if base is None:
        base = rgb.convert("P", palette=Image.ADAPTIVE, colors=64)
    fr.append(rgb.quantize(palette=base, dither=Image.NONE))
fr[0].save(outpath, save_all=True, append_images=fr[1:], loop=0,
           duration=dur, optimize=True, disposal=1)
print("OK", outpath, "poster_frame_idx", poster, "regime_at_poster", DATA["reg"][poster],
      "n_frames", len(frames))

if __name__ == "__main__":
    pass
