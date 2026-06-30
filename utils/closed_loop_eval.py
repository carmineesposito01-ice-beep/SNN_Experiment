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
# T0.6 — soglie ISO/comfort (ISO 15622:2018 ACC; comfort generico). Usate dai flag di comfort_metrics.
ISO_DECEL_LIMIT = 3.5  # decel max ACC confortevole [m/s^2] (ISO 15622)
ISO_ACCEL_LIMIT = 2.0  # accel max ACC [m/s^2] (ISO 15622)
JERK_COMFORT = 2.0     # |jerk| confortevole [m/s^3] (oltre = scomodo)
# T1.7/T1.8 — soglie SSM di letteratura
DRAC_STAR = 3.35       # DRAC critico (conflitto), Archer; AASHTO 3.40 [m/s^2]
MADR_MEAN = 8.45       # Maximum Available Decel Rate medio (per CPI), N(8.45,1.42) troncata [m/s^2]
TTC_THRESHOLDS = (1.0, 1.5, 2.0, 3.0)   # soglie TTC per la frazione-di-tempo-sotto


def _norm_obs(s, v, dv, vl):
    """Fisico -> input SNN normalizzato (1,4), come data/generator.normalize()."""
    s_n  = s / NORM_S_MAX
    v_n  = v / NORM_V_MAX
    dv_n = (float(np.clip(dv, -NORM_DV_MAX, NORM_DV_MAX)) + NORM_DV_MAX) / (2.0 * NORM_DV_MAX)
    vl_n = vl / NORM_VL_MAX
    return torch.tensor([[s_n, v_n, dv_n, vl_n]], dtype=torch.float32)


def _plant_step(a_cmd, v, st, cfg):
    """L4 — plant fisico EGO: lag attuatore 1° ordine (asimm. opz.), + grade + drag/rolling, jerk-limit,
    clip aderenza -mu*g. st = stato mutabile {'a_real'}. cfg dict (chiavi assenti = effetto off).
    Ritorna a_real (accelerazione REALIZZATA)."""
    a_prev = st.get('a_real', a_cmd)
    # lag attuatore (T2.1/T2.8: tau_brake quando si frena, tau_throttle altrimenti; fallback tau_act)
    tau = cfg.get('tau_brake' if a_cmd < a_prev else 'tau_throttle', cfg.get('tau_act', 0.0))
    a_real = a_cmd if not tau else (np.exp(-DT / tau) * a_prev + (1.0 - np.exp(-DT / tau)) * a_cmd)
    # disturbi additivi (T2.3 grade, T2.4 drag+rolling)
    theta = cfg.get('grade', 0.0)
    if theta:
        a_real += -9.81 * np.sin(theta)
    if cfg.get('drag'):
        rho = cfg.get('rho', 1.2); cd = cfg.get('Cd', 0.3); af = cfg.get('A', 2.2)
        m = cfg.get('m', 1500.0); crr = cfg.get('Crr', 0.01)
        if v > 0:
            a_real += -(0.5 * rho * cd * af * v * v) / m - crr * 9.81
    # jerk limiter (T2.7)
    jmax = cfg.get('jerk_max')
    if jmax:
        dj = float(np.clip(a_real - a_prev, -jmax * DT, jmax * DT))
        a_real = a_prev + dj
    # clip aderenza (T2.2): decel max ~ -mu*g (e accel max ~ +mu*g per trazione)
    mu = cfg.get('mu')
    if mu is not None:
        lim = mu * 9.81
        a_real = float(np.clip(a_real, -lim, lim))
    st['a_real'] = a_real
    return a_real


def _channel_obs(s_true, vl_true, st, cfg, rng):
    """L3 — canale V2X: degrada l'osservazione del LEADER (gap+vel). packet-loss (hold-last-CAM),
    Gilbert-Elliott (burst), latenza+jitter (buffer), blackout forzato, rumore OU sensoriale.
    st = stato mutabile. Ritorna (s_obs, vl_obs, aoi_steps)."""
    buf = st.setdefault('buf', [])
    buf.append((s_true, vl_true))
    lat = int(cfg.get('latency_steps', 0)); jit = int(cfg.get('jitter_steps', 0))
    k = max(0, lat + (int(rng.integers(-jit, jit + 1)) if jit > 0 else 0))
    s_rx, vl_rx = buf[max(0, len(buf) - 1 - k)]
    t_now = len(buf) - 1
    bw = cfg.get('blackout_steps')
    if bw is not None and bw[0] <= t_now <= bw[1]:           # T2.15 — blackout avversario
        received = False
    elif 'gilbert' in cfg:                                    # T2.9 — burst (Gilbert-Elliott)
        p_bad, p_good = cfg['gilbert']
        bad = st.get('ge_bad', False)
        bad = (rng.random() > p_good) if bad else (rng.random() < p_bad)
        st['ge_bad'] = bad
        received = not bad
    else:
        received = rng.random() < cfg.get('pdr', 1.0)         # T2.9 — Bernoulli(PDR)
    if received or 'last' not in st:
        st['last'] = (s_rx, vl_rx); st['age'] = k
    else:
        st['age'] = st.get('age', 0) + 1                      # hold-last-CAM
    s_obs, vl_obs = st['last']
    ns = cfg.get('sensor_noise_scale', 0.0)                   # T2.11 — rumore OU su gap/vel
    if ns:
        from config import NOISE_GAP_REL, NOISE_VEL_OPT, NOISE_TAU_S, NOISE_TAU_V
        st['eta_s'] = np.exp(-DT / NOISE_TAU_S) * st.get('eta_s', 0.0) + np.sqrt(2 * DT / NOISE_TAU_S) * rng.standard_normal()
        st['eta_v'] = np.exp(-DT / NOISE_TAU_V) * st.get('eta_v', 0.0) + np.sqrt(2 * DT / NOISE_TAU_V) * rng.standard_normal()
        s_obs = s_obs * np.exp(ns * NOISE_GAP_REL * st['eta_s'])
        vl_obs = vl_obs - s_obs * ns * NOISE_VEL_OPT * st['eta_v']
    return float(s_obs), float(vl_obs), int(st.get('age', 0))


def param_chattering(traj, f_thr=0.5):
    """T2.13 — chattering dei param identificati: std per-canale + frazione energia spettrale > f_thr Hz.
    Significativo solo in modalita' forward_step (param variabili per-step; coi param costanti ~0)."""
    P = traj.get('params')
    PNL = ['v0', 'T', 's0', 'a', 'b']
    if P is None or len(P) < 4:
        return {}
    freqs = np.fft.rfftfreq(P.shape[0], d=DT)
    hi = freqs >= f_thr
    out = {}
    for i, nm in enumerate(PNL):
        x = P[:, i] - P[:, i].mean()
        spec = np.abs(np.fft.rfft(x)) ** 2
        out['chatter_std_' + nm] = float(P[:, i].std())
        out['chatter_hf_' + nm] = float(spec[hi].sum() / (spec.sum() + 1e-12))
    return out


def simulate(model, params_gt, v_leader, s_init, v_init, cut_in=None, device='cpu',
             plant=None, channel=None):
    """Closed-loop. model=None -> ORACOLO (usa params_gt costanti).

    params_gt: array (5,) [v0,T,s0,a,b] veri dello scenario (per oracolo e tracking).
    v_leader:  array (N,) profilo velocita' leader [m/s].
    cut_in:    None | (t_cut:int, new_gap:float) — a t_cut il gap crolla (nuovo leader vicino).
    plant:     None (default) | dict — plant fisico EGO (L4): tau_act/tau_brake/tau_throttle, mu, grade,
               drag, jerk_max. None => accel comandata applicata istantaneamente (comportamento legacy).
    channel:   None (default) | dict — canale V2X (L3): pdr, gilbert, latency_steps/jitter_steps,
               blackout_steps, sensor_noise_scale, seed. None => osservazione esatta (legacy).
    Backward-compat: plant=None e channel=None => percorso e risultato IDENTICI alla versione precedente.
    Ritorna dict con serie temporali + flag collided (+ aoi_* se channel attivo).
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
    pl_state = {}                                              # stato plant (L4)
    ch_state = {}; aoi_series = []                             # stato canale V2X (L3)
    ch_rng = np.random.default_rng(channel.get('seed', 0)) if channel is not None else None

    with torch.no_grad():
        for t in range(N):
            if cut_in is not None and t == int(cut_in[0]):
                s = float(cut_in[1])              # nuovo leader piu' vicino
            vl = float(v_leader[t])
            dv = v - vl                            # >0 = avvicinamento (TRUE, per le serie/fisica)

            # --- canale V2X (opt-in): cosa OSSERVA il controllore del leader ---
            if channel is not None:
                s_obs, vl_obs, age = _channel_obs(s, vl, ch_state, channel, ch_rng)
                aoi_series.append(age)
            else:
                s_obs, vl_obs = s, vl
            dv_obs = v - vl_obs

            if model is not None:
                params = model.forward_step(_norm_obs(s_obs, v, dv_obs, vl_obs).to(device))
            else:
                params = pg

            a_l_raw  = (vl_obs - vl_prev) / DT
            a_l_filt = alpha_al * a_l_filt + (1.0 - alpha_al) * a_l_raw
            vl_prev  = vl_obs

            a_cmd = float(CF_FSNN_Net.acc_iidm_accel(
                torch.tensor([max(s_obs, 1e-3)]), torch.tensor([v]), torch.tensor([dv_obs]),
                torch.tensor([a_l_filt]), params, coolness=ACC_COOLNESS)[0])

            # --- plant fisico EGO (opt-in): accel REALIZZATA ---
            a_ego = _plant_step(a_cmd, v, pl_state, plant) if plant is not None else a_cmd

            series['s'].append(s); series['v'].append(v); series['vl'].append(vl)
            series['dv'].append(dv); series['a_ego'].append(a_ego)
            params_used.append(params.view(-1).cpu().numpy())

            # update balistico (Ch11). NB: gap NON clippato in basso -> collisione rilevabile.
            # La fisica usa vl VERO (non osservato): il canale degrada solo la PERCEZIONE.
            v = max(0.0, v + a_ego * DT)
            s = s + (vl - v) * DT
            if s <= 0.0:
                collided = True
                break

    out = {k: np.asarray(val, dtype=np.float64) for k, val in series.items()}
    out['params'] = np.asarray(params_used, dtype=np.float64)   # (M,5)
    out['collided'] = collided
    out['min_gap'] = float(s) if collided else float(out['s'].min())
    if channel is not None and aoi_series:                      # T2.14 — Age-of-Information
        out['aoi_mean'] = float(np.mean(aoi_series)) * DT
        out['aoi_max'] = float(np.max(aoi_series)) * DT
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
    # T1.7 — DRAC critico (soglia 3.35): tempo-esposto (TED) e tempo-integrato (TID) sopra soglia, frazione
    in_drac = drac > DRAC_STAR
    ted = float(in_drac.sum() * DT)
    tid = float(np.sum((drac[in_drac] - DRAC_STAR) * DT)) if in_drac.any() else 0.0
    out = {
        'collided': bool(traj['collided']),
        'min_gap': float(traj['min_gap']),
        'min_ttc': float(ttc.min()) if np.isfinite(ttc).any() else float('inf'),
        'TET': tet, 'TIT': tit,
        'max_DRAC': float(drac.max()),
        'min_time_headway': float(th[np.isfinite(th)].min()) if np.isfinite(th).any() else float('inf'),
        'frac_drac_critical': float(in_drac.mean()),   # frazione tempo DRAC>3.35
        'TED_drac': ted, 'TID_drac': tid,
        'cpi': float((drac > MADR_MEAN).mean()),        # Crash-Potential-Index (proxy: MADR medio 8.45)
    }
    # T1.8 — frazione di tempo con TTC sotto soglie multiple (solo sugli step in avvicinamento)
    ttc_c = ttc[closing & np.isfinite(ttc)]
    for thr in TTC_THRESHOLDS:
        out['frac_ttc_below_%.1f' % thr] = float((ttc_c < thr).mean()) if ttc_c.size else 0.0
    return out


def comfort_metrics(traj):
    a = traj['a_ego']; v = traj['v']
    jerk = np.diff(a) / DT if len(a) > 1 else np.array([0.0])
    return {
        'rms_accel': float(np.sqrt(np.mean(a ** 2))),
        'max_decel': float(-a.min()),                    # decel piu' forte (valore positivo)
        'rms_jerk': float(np.sqrt(np.mean(jerk ** 2))),
        # T0.6 — flag ISO/comfort (additivi; i lettori legacy usano le 3 chiavi sopra).
        'max_abs_jerk': float(np.abs(jerk).max()),
        'frac_jerk_uncomf': float(np.mean(np.abs(jerk) > JERK_COMFORT)),   # frazione tempo |jerk|>2
        'frac_decel_iso_viol': float(np.mean(a < -ISO_DECEL_LIMIT)),       # frazione decel oltre ISO -3.5
        'frac_accel_iso_viol': float(np.mean(a > ISO_ACCEL_LIMIT)),        # frazione accel oltre ISO +2
        # T1.12 — proxy energia load-based (integrale potenza specifica positiva v*a+); ISO2631 = rms_accel.
        'energy_proxy': float(np.sum(np.maximum(0.0, v * a)) * DT),
    }


def tracking_metrics(traj):
    """Errore vs gap desiderato IDM s* coi parametri usati, e time-gap reale."""
    s = traj['s']; v = traj['v']; dv = traj['dv']; p = traj['params']
    M = len(s)
    v0, T, s0, a, b = (p[:, i] for i in range(5))
    s_star = s0 + np.maximum(0.0, v * T + v * dv / (2.0 * np.sqrt(np.maximum(a * b, 1e-6))))
    gap_err = s - s_star
    th = np.where(v > 0.1, s / np.maximum(v, 1e-3), np.nan)
    # T1.9 — efficienza a REGIME (ultimo 50%): errore di velocita' Delta-v e gap (separati dai transitori).
    k = M // 2
    dv_ss = np.abs(dv[k:]); ge_ss = np.abs(gap_err[k:])
    return {
        'rms_gap_error': float(np.sqrt(np.mean(gap_err ** 2))),
        'mean_time_gap': float(np.nanmean(th)),
        'mean_T_pred': float(np.mean(T)),
        'mean_abs_dv_ss': float(dv_ss.mean()) if dv_ss.size else float('nan'),     # |Delta-v| a regime
        'mean_abs_gap_err_ss': float(ge_ss.mean()) if ge_ss.size else float('nan'),  # |gap error| a regime
    }


def string_stability_gain(traj, warmup_frac=0.3):
    """Guadagno = std(perturbazione v_ego) / std(perturbazione v_leader) a regime.
    < 1 = smorza. ATTENZIONE (T3.5): e' un proxy LOCALE = il caso N=1 (un solo follower, una frequenza),
    NON la string stability del plotone. Per il test vero usare simulate_platoon + platoon_string_metrics
    + transfer_gain_fft (catena N veicoli, sweep in frequenza)."""
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


def build_scenarios(params_gt, N=600, rng=None, include_tail=False):
    """Set di scenari avversari per un dato scenario-driver (params_gt).

    Default (include_tail=False): i 5 scenari storici (following, stop_and_go, hard_brake, cut_in,
    sinusoidal) — INVARIATO, cosi' eval_safety legacy non cambia. Con include_tail=True (T1) aggiunge
    4 scenari di CODA/OoD: cut_out, static_target, panic_stop (-9), aggressive_cut_in.
    """
    rng = rng or np.random.default_rng(0)
    v0 = float(params_gt[0])
    v_set = 0.7 * v0
    _v0p, _T, _s0, _a, _b = (float(x) for x in params_gt)
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

    if not include_tail:
        return scen

    # ---- T1: scenari di CODA / OoD (opt-in) ----
    s_eq, _ = _equilibrium_init(params_gt, v_set)

    # T1.1 cut_out: leader veloce ESCE -> ostacolo fermo (v=0) rivelato tardi (TTC~2s al gap residuo)
    vl = np.full(N, v_set)
    t_co = N // 2
    vl[t_co:] = 0.0
    gap_reveal = max(v_set * 2.0, 6.0)
    scen.append(('cut_out', vl, s_eq, v_set, (t_co, gap_reveal)))

    # T1.2 static_target: ostacolo fermo da subito (v_leader==0); ego in crociera con spazio di reazione
    vl = np.zeros(N)
    s_static = _s0 + v_set * _T + 2.0 * v_set       # gap iniziale = following + ~2s di margine
    scen.append(('static_target', vl, s_static, v_set, None))

    # T1.3 panic_stop: frenata del leader alla DECEL MASSIMA fisica (-B_MAX = -9), non -7
    vl = np.full(N, v_set)
    brake_start = N // 3
    for i in range(brake_start, N):
        vl[i] = max(0.0, vl[i - 1] - B_MAX * DT)
    scen.append(('panic_stop', vl, s_eq, v_set, None))

    # T1.4 aggressive_cut_in: gap al taglio < CUT_IN_S_MIN (training) e leader piu' lento -> DRAC -> B_MAX
    vl = np.full(N, v_set)
    t_cut = N // 2
    vl[t_cut:] = 0.30 * v0
    dv_cut = max(v_set - 0.30 * v0, 1.0)
    gap_cut = max(dv_cut * 0.5, 3.0)                 # TTC~0.5s, sotto la coda evitabile
    scen.append(('aggressive_cut_in', vl, s_eq, v_set, (t_cut, gap_cut)))

    return scen


# ============================================================
# L5 — String stability: catena plotone + funzione di trasferimento
# ============================================================

def simulate_platoon(params_list, leader_v, device='cpu', plant=None, channel=None):
    """T3.1 — plotone in CASCATA: veh0 = leader_v (profilo dato); il follower i segue il follower i-1
    coi propri parametri (params_list[i]). Riusa simulate() invariato. params_list: lista di array(5,).
    Ritorna {'v_profiles': (N+1, L), 'collided': [bool]*N}. L = lunghezza comune (tronca se collisione)."""
    v_prev = np.asarray(leader_v, dtype=np.float64)
    v_profiles = [v_prev]
    collided = []
    for pg in params_list:
        pg = np.asarray(pg, dtype=np.float32)
        v0 = float(v_prev[0])
        s_i, _ = _equilibrium_init(pg, v0)
        out = simulate(None, pg, v_prev, s_i, v0, device=device, plant=plant, channel=channel)
        v_profiles.append(out['v'])
        collided.append(bool(out['collided']))
        v_prev = out['v']
    L = min(len(v) for v in v_profiles)
    return {'v_profiles': np.array([v[:L] for v in v_profiles]), 'collided': collided}


def platoon_string_metrics(v_profiles, warmup_frac=0.3):
    """T3.1/T3.3 — amplificazione per-veicolo (std, L2, Linf) + head-to-tail + strict string stability.
    string-stable se ogni rapporto A_i/A_{i-1} <= 1 (l'oscillazione DECADE verso la coda)."""
    V = np.asarray(v_profiles, dtype=np.float64)
    k = int(V.shape[1] * warmup_frac)
    dev = V[:, k:] - V[:, k:].mean(axis=1, keepdims=True)
    eps = 1e-9
    std = dev.std(axis=1); l2 = np.linalg.norm(dev, axis=1); linf = np.abs(dev).max(axis=1)
    amp_ratio = (std[1:] / (std[:-1] + eps))
    return {
        'std_per_veh': std.tolist(),
        'amp_ratio': amp_ratio.tolist(),
        'l2_gain': (l2[1:] / (l2[:-1] + eps)).tolist(),
        'linf_gain': (linf[1:] / (linf[:-1] + eps)).tolist(),
        'head_to_tail': float(std[-1] / (std[0] + eps)),
        'strict_string_stable': bool(np.all(amp_ratio <= 1.0 + 1e-3)),
    }


def transfer_gain_fft(v_in, v_out, band=(0.01, 0.3)):
    """T3.2 — funzione di trasferimento empirica |Γ(ω)| = |FFT(v_out)|/|FFT(v_in)| sulla banda.
    Usare con leader a chirp (swept-sine): una sola simulazione copre la banda. peak_gain<=1 = stabile."""
    n = int(min(len(v_in), len(v_out)))
    xi = np.asarray(v_in[:n]) - np.mean(v_in[:n]); xo = np.asarray(v_out[:n]) - np.mean(v_out[:n])
    freqs = np.fft.rfftfreq(n, d=DT)
    Fi = np.abs(np.fft.rfft(xi)); Fo = np.abs(np.fft.rfft(xo))
    m = (freqs >= band[0]) & (freqs <= band[1]) & (Fi > 1e-6 * (Fi.max() + 1e-12))
    if not m.any():
        return {'peak_gain': float('nan'), 'peak_freq': float('nan'), 'freqs': [], 'gain': []}
    g = Fo[m] / Fi[m]
    return {'peak_gain': float(g.max()), 'peak_freq': float(freqs[m][g.argmax()]),
            'freqs': freqs[m].tolist(), 'gain': g.tolist()}
