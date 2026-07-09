"""utils/platoon_eval.py — Valutazione MESO (plotone, string stability) e MACRO (anello,
diagramma fondamentale) del controller ACC-IDM guidato dalla SNN.

CAM (V2X): ogni veicolo i riceve il CAM dal veicolo che SEGUE (i-1, davanti) -> osservazione
(gap, v_own, dv = v_i - v_{i-1}, v_leader = v_{i-1}). Cablato esplicitamente.

Meso (stringa APERTA, criterio ACC, Treiber ch16.7): perturbazione sinusoidale in testa ->
transfer-function gain |H|_i = A_i/A_0 per veicolo. head-to-tail stabile se <= 1.
Macro (anello CHIUSO, ch16/ch9): densita' rho = N/L; diagramma fondamentale Q(rho) via Edie.

Forward SNN batchato: N veicoli = batch N (uno stato per veicolo). Oracolo: params veri.
"""
import numpy as np
import torch

from config import (NORM_S_MAX, NORM_V_MAX, NORM_DV_MAX, NORM_VL_MAX, DT,
                    ACC_AL_TAU, ACC_COOLNESS)
from core.network import CF_FSNN_Net

VEH_LEN = 5.0   # lunghezza veicolo [m]


def _norm_obs_batch(gap, v, dv, vl):
    """(N,) fisici -> (N,4) normalizzati come nel training."""
    x = np.stack([
        np.clip(gap, 0, NORM_S_MAX) / NORM_S_MAX,
        np.clip(v, 0, NORM_V_MAX) / NORM_V_MAX,
        (np.clip(dv, -NORM_DV_MAX, NORM_DV_MAX) + NORM_DV_MAX) / (2.0 * NORM_DV_MAX),
        np.clip(vl, 0, NORM_VL_MAX) / NORM_VL_MAX,
    ], axis=1).astype(np.float32)
    return torch.from_numpy(x)


def _accel(gap, v, dv, a_l, params):
    return CF_FSNN_Net.acc_iidm_accel(
        torch.tensor(np.maximum(gap, 1e-3), dtype=torch.float32),
        torch.tensor(v, dtype=torch.float32), torch.tensor(dv, dtype=torch.float32),
        torch.tensor(a_l, dtype=torch.float32), params, coolness=ACC_COOLNESS).numpy()


def _params_for(model, gap, v, dv, vl, pgt_t, n, device):
    if model is None:
        return pgt_t.unsqueeze(0).expand(n, 5)
    return model.forward_step(_norm_obs_batch(gap, v, dv, vl).to(device))


# ===========================================================
# MESO — plotone aperto (string stability ACC)
# ===========================================================
def simulate_platoon(model, params_gt, n_vehicles, v_leader_profile, device='cpu', forward=None):
    """N veicoli IN FILA. Veicolo 0 = testa (segue il profilo esterno); i segue i-1 (CAM da i-1).

    Ritorna dict: v,x,gap,a (T,N) + v_leader (T,) + collided.
    """
    pgt_t = torch.tensor(params_gt, dtype=torch.float32)
    v0, T, s0, a_p, b_p = [float(x) for x in params_gt]
    Tlen = len(v_leader_profile)
    v_set = float(v_leader_profile[0])
    gap_eq = s0 + v_set * T                                   # gap di equilibrio
    n = n_vehicles
    # posizioni: veicolo 0 a x=0; i-esimo dietro. Leader virtuale della testa davanti.
    x = -np.arange(n) * (gap_eq + VEH_LEN)
    v = np.full(n, v_set, dtype=float)
    x_head_leader = gap_eq + VEH_LEN
    alpha_al = float(np.exp(-DT / ACC_AL_TAU))
    a_l = np.zeros(n); vl_prev = np.full(n, v_set)
    if forward is not None:
        forward.reset(n, device)               # family-aware batched forward owns its state
    elif model is not None:
        model.eval(); model.reset_state(n, device)
    rec = {k: np.zeros((Tlen, n)) for k in ('v', 'x', 'gap', 'a')}
    collided = False
    with torch.no_grad():
        for t in range(Tlen):
            vlead = np.empty(n); vlead[0] = float(v_leader_profile[t]); vlead[1:] = v[:-1]
            xlead = np.empty(n); xlead[0] = x_head_leader; xlead[1:] = x[:-1]
            gap = xlead - x - VEH_LEN
            dv = v - vlead
            params = (forward.infer(gap, v, dv, vlead) if forward is not None
                      else _params_for(model, gap, v, dv, vlead, pgt_t, n, device))
            a_l_raw = (vlead - vl_prev) / DT
            a_l = alpha_al * a_l + (1.0 - alpha_al) * a_l_raw; vl_prev = vlead.copy()
            acc = _accel(gap, v, dv, a_l, params)
            rec['v'][t] = v; rec['x'][t] = x; rec['gap'][t] = gap; rec['a'][t] = acc
            v = np.maximum(0.0, v + acc * DT); x = x + v * DT
            x_head_leader += float(v_leader_profile[t]) * DT
            if (gap <= 0).any():
                collided = True
    rec['collided'] = collided
    rec['v_leader'] = np.asarray(v_leader_profile, dtype=float)
    return rec


def platoon_metrics(rec, warmup_frac=0.3):
    """Metriche MESO (string stability + sicurezza + comfort) dal plotone."""
    v = rec['v']; gap = rec['gap']; a = rec['a']; vlead = rec['v_leader']
    Tlen, n = v.shape
    w = int(Tlen * warmup_frac)
    # ampiezza perturbazione = std velocita' (dopo warmup), per veicolo + leader esterno
    amp_leader = float(np.std(vlead[w:]))
    amp = np.std(v[w:], axis=0)                                # (n,)
    gain = amp / (amp_leader + 1e-9)                           # |H|_i = A_i/A_0(leader)
    head_tail = float(gain[-1])                                # ultimo follower vs testa
    amplification = float(gain.max())                          # max lungo la catena
    monotone = bool(np.all(np.diff(gain) <= 1e-3))             # strict string stability?
    # convettivita': il minimo di velocita' (l'onda) si sposta verso indici crescenti (a monte)?
    tmin = np.argmin(v[w:], axis=0)                            # istante di min v per veicolo
    upstream = bool(np.polyfit(np.arange(n), tmin, 1)[0] > 0)  # ritardo cresce con l'indice = onda a monte
    return {
        'n_vehicles': n,
        'amp_leader': round(amp_leader, 3),
        'gain_per_vehicle': [round(float(x), 3) for x in gain],
        'head_to_tail_gain': round(head_tail, 3),
        'max_amplification': round(amplification, 3),
        'string_stable_headtail': head_tail <= 1.0,
        'strict_monotone_decay': monotone,
        'convective_upstream': upstream,
        'min_gap_platoon': round(float(gap.min()), 3),
        'min_ttc_platoon': round(_min_ttc(gap, v, vlead), 3),
        'collided': bool(rec['collided']),
        'rms_accel_mean': round(float(np.sqrt((a ** 2).mean())), 3),
        'max_decel_platoon': round(float(-a.min()), 3),
        'rms_jerk_mean': round(float(np.sqrt((np.diff(a, axis=0) / DT) ** 2).mean()), 3),
    }


def _min_ttc(gap, v, vlead):
    # TTC per il veicolo che segue il leader piu' lento; usa dv per-veicolo
    Tlen, n = v.shape
    dv = v.copy()
    dv[:, 0] -= vlead.reshape(-1)
    dv[:, 1:] -= v[:, :-1]
    closing = dv > 1e-3
    ttc = np.where(closing, gap / np.maximum(dv, 1e-6), np.inf)
    return float(np.min(ttc)) if np.isfinite(ttc).any() else np.inf


# ===========================================================
# MACRO — anello chiuso (diagramma fondamentale)
# ===========================================================
def simulate_ring(model, params_gt, n_vehicles, ring_length, n_steps, device='cpu', perturb=0.1,
                  forward=None):
    """N veicoli su ANELLO di lunghezza L (m). i segue i-1; veicolo 0 segue N-1 (+L, wrap).

    Densita' rho = N/L. Stato iniziale uniforme + piccola perturbazione. Ritorna v,x (T,N).
    """
    pgt_t = torch.tensor(params_gt, dtype=torch.float32)
    v0, T, s0, a_p, b_p = [float(x) for x in params_gt]
    n = n_vehicles; L = float(ring_length)
    spacing = L / n
    gap_eq = spacing - VEH_LEN
    # velocita' di equilibrio per quel gap (inversa IDM approssimata): v t.c. s*(v)=gap
    v_eq = max(0.0, min(v0, (gap_eq - s0) / max(T, 0.1)))
    x = (np.arange(n) * spacing) % L
    v = np.full(n, v_eq, dtype=float)
    rng = np.random.default_rng(0)
    v += rng.normal(0, perturb * max(v_eq, 1.0), n)            # perturbazione
    alpha_al = float(np.exp(-DT / ACC_AL_TAU))
    a_l = np.zeros(n); vl_prev = v.copy()
    if forward is not None:
        forward.reset(n, device)               # family-aware batched forward owns its state
    elif model is not None:
        model.eval(); model.reset_state(n, device)
    rec_v = np.zeros((n_steps, n)); rec_x = np.zeros((n_steps, n))
    with torch.no_grad():
        for t in range(n_steps):
            order = np.argsort(-x)                              # ordine spaziale (davanti->dietro)
            lead = np.roll(order, 1)                            # il leader di ciascuno (davanti, wrap)
            xlead = x[lead].copy(); xlead[order[0]] += L        # il primo ha il leader oltre il giro
            # rimappa per indice veicolo
            gap = np.empty(n); vlead = np.empty(n)
            gap[order] = (xlead - x[order] - VEH_LEN)
            vlead[order] = v[lead]
            gap = np.maximum(gap, 0.1)
            dv = v - vlead
            params = (forward.infer(gap, v, dv, vlead) if forward is not None
                      else _params_for(model, gap, v, dv, vlead, pgt_t, n, device))
            a_l_raw = (vlead - vl_prev) / DT
            a_l = alpha_al * a_l + (1.0 - alpha_al) * a_l_raw; vl_prev = vlead.copy()
            acc = _accel(gap, v, dv, a_l, params)
            rec_v[t] = v; rec_x[t] = x
            v = np.maximum(0.0, v + acc * DT); x = (x + v * DT) % L
    return {'v': rec_v, 'x': rec_x, 'L': L, 'n': n, 'density': n / L}


def fundamental_diagram(model, params_gt, densities_veh_per_km, ring_length=1000.0,
                        n_steps=600, device='cpu'):
    """Sweep densita' -> (rho, Q, V) via Edie sull'anello. Ritorna lista di dict per punto."""
    pts = []
    for rho_km in densities_veh_per_km:
        n = max(2, int(round(rho_km / 1000.0 * ring_length)))
        rec = simulate_ring(model, params_gt, n, ring_length, n_steps, device)
        v = rec['v']
        w = int(n_steps * 0.5)                                 # meta' seconda = regime
        V = float(v[w:].mean())                                # velocita' media spazio-tempo
        rho = n / ring_length * 1000.0                         # veh/km
        Q = rho * V * 3.6                                      # veh/h (V in m/s -> *3.6 km/h * rho/km)
        # instabilita': oscillazione residua della velocita' (stop&go spontaneo)
        wave = float(np.std(v[w:].mean(axis=1)))              # std della velocita' media nel tempo
        pts.append({'rho_veh_km': round(rho, 1), 'Q_veh_h': round(Q, 1),
                    'V_m_s': round(V, 2), 'V_km_h': round(V * 3.6, 1),
                    'n': n, 'wave_std': round(wave, 3),
                    'unstable': wave > 0.5})
    return pts
