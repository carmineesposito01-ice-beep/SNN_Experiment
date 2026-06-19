"""utils/closed_loop_eval.py — Validazione CLOSED-LOOP del controller ACC-IDM.

L'ego e' guidato da CF_FSNN_Net.acc_iidm_accel con i 5 parametri IDM predetti dalla SNN
(forward_step, stato ricorrente mantenuto step-by-step) OPPURE dai parametri VERI (oracolo).
Il leader esegue scenari avversari (cut-in, frenate forti, stop&go, sinusoidale).

Rileva collisioni (gap <= 0) e calcola metriche oggettive di sicurezza (TTC/TET/TIT/DRAC),
comfort (RMS accel, jerk, max decel), tracking (gap error, time-gap) e string stability.
Riferimenti: Treiber & Kesting (IIDM/ACC ch12, stability ch16); SSM: Minderhoud & Bovy 2001.

Tutto su CPU, batch=1, torch.no_grad. Nessuna dipendenza dal training loop.
"""
import numpy as np
import torch

from config import (NORM_S_MAX, NORM_V_MAX, NORM_DV_MAX, NORM_VL_MAX, DT,
                    ACC_AL_TAU, ACC_COOLNESS)
from core.network import CF_FSNN_Net

VEH_LEN = 5.0          # lunghezza veicolo [m]: collisione se gap (bumper-to-bumper) <= 0
TTC_STAR = 1.5         # soglia TTC critica [s] (letteratura: 1.5-3 s)
B_MAX = 9.0            # decelerazione massima fisica [m/s^2]


def _norm_obs(s, v, dv, vl):
    """Fisico -> input SNN normalizzato (1,4), come data/generator.normalize()."""
    s_n  = s / NORM_S_MAX
    v_n  = v / NORM_V_MAX
    dv_n = (float(np.clip(dv, -NORM_DV_MAX, NORM_DV_MAX)) + NORM_DV_MAX) / (2.0 * NORM_DV_MAX)
    vl_n = vl / NORM_VL_MAX
    return torch.tensor([[s_n, v_n, dv_n, vl_n]], dtype=torch.float32)


def simulate(model, params_gt, v_leader, s_init, v_init, cut_in=None, device='cpu'):
    """Closed-loop. model=None -> ORACOLO (usa params_gt costanti).

    params_gt: array (5,) [v0,T,s0,a,b] veri dello scenario (per oracolo e tracking).
    v_leader:  array (N,) profilo velocita' leader [m/s].
    cut_in:    None | (t_cut:int, new_gap:float) — a t_cut il gap crolla (nuovo leader vicino).
    Ritorna dict con serie temporali + flag collided.
    """
    N = len(v_leader)
    alpha_al = float(np.exp(-DT / ACC_AL_TAU))
    pg = torch.tensor(params_gt, dtype=torch.float32).view(1, 5)
    if model is not None:
        model.eval()
        model.reset_state(1, device)

    s = float(s_init); v = float(v_init)
    a_l_filt = 0.0; vl_prev = float(v_leader[0])
    series = {k: [] for k in ('s', 'v', 'vl', 'dv', 'a_ego')}
    params_used = []
    collided = False

    with torch.no_grad():
        for t in range(N):
            if cut_in is not None and t == int(cut_in[0]):
                s = float(cut_in[1])              # nuovo leader piu' vicino
            vl = float(v_leader[t])
            dv = v - vl                            # >0 = avvicinamento

            if model is not None:
                params = model.forward_step(_norm_obs(s, v, dv, vl).to(device))
            else:
                params = pg

            a_l_raw  = (vl - vl_prev) / DT
            a_l_filt = alpha_al * a_l_filt + (1.0 - alpha_al) * a_l_raw
            vl_prev  = vl

            a_ego = float(CF_FSNN_Net.acc_iidm_accel(
                torch.tensor([max(s, 1e-3)]), torch.tensor([v]), torch.tensor([dv]),
                torch.tensor([a_l_filt]), params, coolness=ACC_COOLNESS)[0])

            series['s'].append(s); series['v'].append(v); series['vl'].append(vl)
            series['dv'].append(dv); series['a_ego'].append(a_ego)
            params_used.append(params.view(-1).cpu().numpy())

            # update balistico (Ch11). NB: gap NON clippato in basso -> collisione rilevabile.
            v = max(0.0, v + a_ego * DT)
            s = s + (vl - v) * DT
            if s <= 0.0:
                collided = True
                break

    out = {k: np.asarray(val, dtype=np.float64) for k, val in series.items()}
    out['params'] = np.asarray(params_used, dtype=np.float64)   # (M,5)
    out['collided'] = collided
    out['min_gap'] = float(s) if collided else float(out['s'].min())
    return out


# ============================================================
# Metriche
# ============================================================

def safety_metrics(traj):
    """SSM di sicurezza: collision, min gap, TTC/TET/TIT, DRAC, time-headway."""
    s = traj['s']; dv = traj['dv']; v = traj['v']
    closing = dv > 1e-3
    ttc = np.where(closing, s / np.maximum(dv, 1e-6), np.inf)
    in_danger = closing & (ttc < TTC_STAR) & (ttc > 0)
    tet = float(in_danger.sum() * DT)
    tit = float(np.sum((TTC_STAR - ttc[in_danger]) * DT)) if in_danger.any() else 0.0
    drac = np.where(closing, dv ** 2 / (2.0 * np.maximum(s, 1e-3)), 0.0)
    th = np.where(v > 0.1, s / np.maximum(v, 1e-3), np.inf)
    return {
        'collided': bool(traj['collided']),
        'min_gap': float(traj['min_gap']),
        'min_ttc': float(ttc.min()) if np.isfinite(ttc).any() else float('inf'),
        'TET': tet, 'TIT': tit,
        'max_DRAC': float(drac.max()),
        'min_time_headway': float(th[np.isfinite(th)].min()) if np.isfinite(th).any() else float('inf'),
    }


def comfort_metrics(traj):
    a = traj['a_ego']
    jerk = np.diff(a) / DT if len(a) > 1 else np.array([0.0])
    return {
        'rms_accel': float(np.sqrt(np.mean(a ** 2))),
        'max_decel': float(-a.min()),                    # decel piu' forte (valore positivo)
        'rms_jerk': float(np.sqrt(np.mean(jerk ** 2))),
    }


def tracking_metrics(traj):
    """Errore vs gap desiderato IDM s* coi parametri usati, e time-gap reale."""
    s = traj['s']; v = traj['v']; dv = traj['dv']; p = traj['params']
    M = len(s)
    v0, T, s0, a, b = (p[:, i] for i in range(5))
    s_star = s0 + np.maximum(0.0, v * T + v * dv / (2.0 * np.sqrt(np.maximum(a * b, 1e-6))))
    gap_err = s - s_star
    th = np.where(v > 0.1, s / np.maximum(v, 1e-3), np.nan)
    return {
        'rms_gap_error': float(np.sqrt(np.mean(gap_err ** 2))),
        'mean_time_gap': float(np.nanmean(th)),
        'mean_T_pred': float(np.mean(T)),
    }


def string_stability_gain(traj, warmup_frac=0.3):
    """Guadagno = std(perturbazione v_ego) / std(perturbazione v_leader) a regime.
    < 1 = string-stable (smorza). Usare su scenario sinusoidale."""
    v = traj['v']; vl = traj['vl']
    k = int(len(v) * warmup_frac)
    vl_s = vl[k:]; v_s = v[k:]
    if vl_s.std() < 1e-6:
        return float('nan')
    return float(v_s.std() / vl_s.std())


def all_metrics(traj):
    m = {}
    m.update(safety_metrics(traj)); m.update(comfort_metrics(traj)); m.update(tracking_metrics(traj))
    return m


# ============================================================
# Scenari avversari (leader) — ritornano (nome, v_leader, s_init, v_init, cut_in)
# ============================================================

def _equilibrium_init(params_gt, v_set):
    """Gap di equilibrio IDM per partire in following stazionario."""
    v0, T, s0, a, b = params_gt
    return s0 + max(0.0, v_set * T), v_set


def build_scenarios(params_gt, N=600, rng=None):
    """Set completo di scenari avversari per un dato scenario-driver (params_gt)."""
    rng = rng or np.random.default_rng(0)
    v0 = float(params_gt[0])
    v_set = 0.7 * v0
    t = np.arange(N)
    scen = []

    # 1. Following stazionario (leader ~costante con rumore lieve)
    vl = np.clip(v_set + rng.normal(0, 0.3, N), 0, v0)
    s_i, v_i = _equilibrium_init(params_gt, v_set)
    scen.append(('following', vl, s_i, v_i, None))

    # 2. Stop & go (cicli accel/decel a 0)
    vl = np.clip(v_set * (0.5 + 0.5 * np.sin(2 * np.pi * t / 120.0)), 0, v0)
    scen.append(('stop_and_go', vl, *_equilibrium_init(params_gt, v_set), None))

    # 3. Frenata forte / emergenza: cruise poi -7 m/s^2 a 0
    vl = np.full(N, v_set)
    brake_start = N // 3
    for i in range(brake_start, N):
        vl[i] = max(0.0, vl[i - 1] - 7.0 * DT)
    scen.append(('hard_brake', vl, *_equilibrium_init(params_gt, v_set), None))

    # 4. Cut-in (UC2): ego in crociera, auto piu' lenta taglia a meta'. FISICA REALISTICA:
    # gap al taglio = TTC~1s sulla Deltav nominale -> DRAC ~4 m/s2 (<< b_max 9) = difficile ma
    # EVITABILE da un buon controller (prima era 4m/DRAC~8 = oltre il limite, collideva anche l'oracolo).
    vl = np.full(N, v_set)
    t_cut = N // 2
    vl[t_cut:] = 0.45 * v0               # cut-in piu' lento (Deltav nominale = v_set - 0.45*v0 = 0.25*v0)
    dv_cut = max(v_set - 0.45 * v0, 1.0)
    gap_cut = max(dv_cut * 1.0, 6.0)     # TTC ~1s al taglio: evitabile con frenata ferma (~4 m/s2)
    s_i, v_i = _equilibrium_init(params_gt, v_set)
    scen.append(('cut_in', vl, s_i, v_i, (t_cut, gap_cut)))

    # 5. Sinusoidale (per string stability)
    vl = np.clip(v_set + 0.20 * v_set * np.sin(2 * np.pi * t / 80.0), 0, v0)
    scen.append(('sinusoidal', vl, *_equilibrium_init(params_gt, v_set), None))

    return scen
