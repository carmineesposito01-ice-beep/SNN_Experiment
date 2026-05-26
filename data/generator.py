"""
data/generator.py -- Generatore sintetico ACC-IDM (IIDM base) per CF_FSNN
==========================================================================
Implementa:
  - ACC-IDM con base IIDM  (Ch12 Sez. 12.4 -- modello fisico scelto)
  - IDM-2D stocastico su T (Ch12 Sez. 12.6 -- processo OU su time gap)
  - CAH (Constant Acceleration Heuristic) -- anticipa frenata del leader
  - Stima a_l con filtro OU da differenze finite V2X
  - Update balistico       (Ch11 -- piu' stabile di Eulero)
  - Rumore OU su segnali   (Ch13 -- errori stima gap/velocita')
  - Packet loss V2X        (simulazione link degradato UC14/UC15)
  - Profili leader:        (costante, sinusoidale, stop_and_go, free)
  - Scenari cut-in         (UC2 -- Abrupt Cut-In, 20% del dataset)

Output per ogni scenario, array (N_steps, 7):
  col 0: s        gap follower-leader [m]
  col 1: v        velocita' follower  [m/s]
  col 2: dv       velocita' relativa  [m/s]  (v_ego - v_leader)
  col 3: v_l      velocita' leader    [m/s]
  col 4: v_dot    accelerazione follower da ACC-IDM [m/s^2]
  col 5: T_true   valore reale T(t) in questo step [s]
  col 6: mask     1=frame V2X ricevuto, 0=packet lost

Col 0-3: segnali V2X -- input della SNN.
Col 4-5: ground truth fisica -- usata nel PINN loss.
Col 6:   fault tolerance V2X.

NOTA: a_l (accelerazione leader) e' derivata internamente nel generatore
e usata per calcolare v_dot tramite ACC-IDM. Nel training, a_l viene
ri-stimata in pinn_loss() da differenze finite su v_l + filtro OU.
"""

import numpy as np
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    DT, SIM_DURATION, WARMUP_DURATION,
    IDM_HWY, IDM_URB, IDM_TRK,
    IDM2D_T1, IDM2D_T2, IDM2D_TAU,
    ACC_COOLNESS, ACC_AL_TAU,
    CUT_IN_RATIO, CUT_IN_S_MIN, CUT_IN_S_MAX, CUT_IN_DV_MAX,
    NOISE_GAP_REL, NOISE_VEL_OPT, NOISE_ACCEL,
    NOISE_TAU_S, NOISE_TAU_V, NOISE_TAU_A,
    V2X_PACKET_LOSS, SCENARIO_MIX,
    N_SCENARIOS_TRAIN, N_SCENARIOS_VAL, N_SCENARIOS_TEST,
    NORM_S_MAX, NORM_V_MAX, NORM_DV_MAX, NORM_VL_MAX,
    SEED,
)


# ===========================================================
# 1. NUCLEO ACC-IDM CON BASE IIDM
# ===========================================================

def _acc_iidm_accel(s, v, v_l, a_l, params, c=ACC_COOLNESS):
    """
    Accelerazione ACC-IDM con base IIDM (Ch12, Sez. 12.4).

    Differenze rispetto all'IDM plain:
    - IIDM: separa il regime free-flow dal car-following con
      formula piu' precisa -> elimina il bias v0 di IDM.
    - CAH: Constant Acceleration Heuristic -> risposta anticipatoria
      al comportamento del leader -> no panic braking su cut-in.
    - Blend pesato da c: a_ACC = (1-c)*a_IIDM + c*(a_CAH + b*tanh(...))
      Con c=0.99 la CAH domina quando a_IIDM < a_CAH.

    Parametri:
        s, v, v_l: float  -- gap [m], vel ego [m/s], vel leader [m/s]
        a_l:       float  -- acc leader stimata (OU filtrata) [m/s^2]
        params:    dict   -- v0, T, s0, a, b, delta
        c:         float  -- coolness factor (0.99 fisso)

    Ritorna: float -- accelerazione ego [m/s^2], clampata in [-9, a]
    """
    v0    = params['v0']
    T     = params['T']
    s0    = params['s0']
    a     = params['a']
    b     = params['b']
    delta = params['delta']

    dv     = v - v_l
    s_safe = max(s, 0.01)

    # Gap desiderato s* (uguale a IDM)
    s_star = s0 + max(0.0, v * T + v * dv / (2.0 * np.sqrt(a * b + 1e-9)))

    # ── IIDM base (regime free-flow separato dal regime following) ──
    # v_free: decelerazione libera se non ci fosse il leader
    v_free = a * (1.0 - (v / max(v0, 1e-3)) ** delta)
    z      = s_star / s_safe
    if z < 1.0:
        # Regime free-flow dominante
        a_iidm = v_free * (1.0 - z ** 2)
    else:
        # Regime car-following dominante (z>=1 -> forte frenata)
        a_iidm = v_free - a * (z ** 2 - 1.0) / (1.0 + z) ** 2

    # ── CAH (Constant Acceleration Heuristic) ───────────────────────
    # ā_l = min(a_l, a) -- evita assunzioni ottimistiche sul leader
    a_l_bar = min(a_l, a)
    # Denominatore della CAH: v*ā_l/s + (v-v_l)^2/(2s)
    denom = v * a_l_bar / s_safe + dv ** 2 / (2.0 * s_safe + 1e-9)
    if abs(denom) > 1e-9:
        a_cah = v ** 2 * a_l_bar / (denom + 1e-9)
    else:
        a_cah = -9.0   # fallback conservativo
    a_cah = float(np.clip(a_cah, -9.0, a))

    # ── Blend ACC-IDM ────────────────────────────────────────────────
    if a_iidm >= a_cah:
        a_acc = a_iidm
    else:
        # Blend smooth: (1-c)*IIDM + c*(CAH + b*tanh((IIDM-CAH)/b))
        diff  = (a_iidm - a_cah) / (b + 1e-9)
        a_acc = (1.0 - c) * a_iidm + c * (a_cah + b * np.tanh(diff))

    return float(np.clip(a_acc, -9.0, a))


def _idm_accel(s, v, v_l, params):
    """
    Accelerazione IDM plain (mantenuto per riferimento/smoke test).
    Preferire _acc_iidm_accel() per il training effettivo.
    """
    v0    = params['v0']
    T     = params['T']
    s0    = params['s0']
    a     = params['a']
    b     = params['b']
    delta = params['delta']
    dv     = v - v_l
    s_star = s0 + max(0.0, v * T + v * dv / (2.0 * np.sqrt(a * b)))
    s_safe = max(s, 0.01)
    v_dot  = a * (1.0 - (v / v0) ** delta - (s_star / s_safe) ** 2)
    return float(np.clip(v_dot, -9.0, a))


# ===========================================================
# 2. UTILITY OU
# ===========================================================

def _ou_step(eta, tau, dt, rng):
    """
    Un passo OU discretizzato (Ch12 formula numerica).
    eta_{k+1} = exp(-dt/tau) * eta_k + sqrt(2*dt/tau) * xi
    """
    decay = np.exp(-dt / tau)
    noise = np.sqrt(2.0 * dt / tau) * rng.standard_normal()
    return decay * eta + noise


def _idm2d_T_step(T_cur, T1, T2, tau_2d, dt, rng):
    """
    Random walk di T per IDM-2D (Ch12 Sez. 12.6).
    p = dt/tau_2d: con questa probabilita' T <- U(T1, T2).
    """
    if rng.random() < dt / tau_2d:
        return rng.uniform(T1, T2)
    return T_cur


# ===========================================================
# 3. PROFILI LEADER
# ===========================================================

def _leader_profile(profile, N, dt, rng, v0):
    """
    Genera il profilo di velocita' del veicolo leader v_l(t).

    profile:
      'constant'    -- velocita' costante con piccolo rumore
      'sinusoidal'  -- oscillazione sinusoidale attorno a v0
      'stop_and_go' -- ciclo accelerazione / decelerazione / stop
      'free'        -- IDM libero che accelera verso v0 da fermo
    """
    v_l = np.zeros(N)

    if profile == 'constant':
        base  = v0 * rng.uniform(0.7, 1.0)
        noise = rng.normal(0, base * 0.02, N)
        v_l   = np.clip(base + noise, 0.0, v0 * 1.1)

    elif profile == 'sinusoidal':
        base = v0 * rng.uniform(0.6, 0.95)
        amp  = base * rng.uniform(0.05, 0.20)
        freq = rng.uniform(0.01, 0.05)
        t    = np.arange(N) * dt
        v_l  = np.clip(base + amp * np.sin(2.0 * np.pi * freq * t), 0.0, v0 * 1.1)

    elif profile == 'stop_and_go':
        cycle_len = int(rng.uniform(20, 60) / dt)
        base = v0 * rng.uniform(0.5, 0.9)
        for i in range(N):
            phase = (i % cycle_len) / cycle_len
            if phase < 0.40:
                v_l[i] = base
            elif phase < 0.60:
                v_l[i] = base * (1.0 - (phase - 0.40) / 0.20)
            elif phase < 0.75:
                v_l[i] = 0.0
            else:
                v_l[i] = base * (phase - 0.75) / 0.25
        v_l = np.clip(v_l, 0.0, v0 * 1.1)

    elif profile == 'free':
        v_curr = 0.0
        for i in range(N):
            v_curr += 1.5 * (1.0 - (v_curr / max(v0, 1e-3)) ** 4) * dt
            v_curr  = float(np.clip(v_curr, 0.0, v0))
            v_l[i]  = v_curr

    return v_l.astype(np.float32)


# ===========================================================
# 4. SIMULATORE DI TRAIETTORIA (normale — no cut-in)
# ===========================================================

def simulate_trajectory(params, profile='sinusoidal', seed=None):
    """
    Simula una traiettoria follower-leader con ACC-IDM + rumore OU.
    Restituisce array (N_steps, 7) float32.

    Il modello fisico usato e' ACC-IDM con base IIDM:
    - IIDM: risolve il bias v0 di IDM plain
    - CAH:  anticipa la frenata del leader (no panic braking su UC2)
    - a_l e' stimata da differenze finite su v_l + filtro OU (tau=ACC_AL_TAU)
    """
    rng = np.random.default_rng(seed)
    N   = int(SIM_DURATION / DT)

    v_l_profile = _leader_profile(profile, N, DT, rng, params['v0'])

    # Condizioni iniziali
    T_cur = rng.uniform(IDM2D_T1, IDM2D_T2)
    v     = params['v0'] * 0.8
    s     = params['s0'] + v * T_cur + rng.uniform(-2.0, 2.0)

    # Processi OU per i rumori di percezione
    eta_s = 0.0
    eta_v = 0.0
    eta_a = 0.0

    # Stima a_l (filtro OU su differenze finite)
    alpha_al  = np.exp(-DT / ACC_AL_TAU)
    a_l_filt  = 0.0
    v_l_prev  = float(v_l_profile[0])

    traj = np.zeros((N, 7), dtype=np.float32)

    for i in range(N):
        v_l_true = float(v_l_profile[i])

        # IDM-2D: aggiorna T (processo OU su time gap)
        T_cur = _idm2d_T_step(T_cur, IDM2D_T1, IDM2D_T2, IDM2D_TAU, DT, rng)

        # Rumore OU sui segnali percepiti
        eta_s = _ou_step(eta_s, NOISE_TAU_S, DT, rng)
        eta_v = _ou_step(eta_v, NOISE_TAU_V, DT, rng)
        eta_a = _ou_step(eta_a, NOISE_TAU_A, DT, rng)

        # Segnali percepiti (con errori -- Ch13)
        s_perc  = s * np.exp(NOISE_GAP_REL * eta_s)
        vl_perc = v_l_true - s * NOISE_VEL_OPT * eta_v

        # Stima a_l da differenze finite + filtro OU
        a_l_raw  = (v_l_true - v_l_prev) / DT
        a_l_filt = alpha_al * a_l_filt + (1.0 - alpha_al) * a_l_raw
        v_l_prev = v_l_true

        # Accelerazione ACC-IDM con IIDM base
        p_step = dict(params, T=T_cur)
        v_dot  = _acc_iidm_accel(s_perc, v, vl_perc, a_l_filt, p_step) \
                 + NOISE_ACCEL * eta_a

        # Update balistico (Ch11)
        dv_true = v - v_l_true
        v_new   = float(np.clip(v + v_dot * DT, 0.0, params['v0'] * 1.2))
        s       = float(np.clip(s + (v_l_true - v) * DT, params['s0'] * 0.5, NORM_S_MAX))
        v       = v_new

        # Packet loss V2X
        mask = 0.0 if rng.random() < V2X_PACKET_LOSS else 1.0

        traj[i] = [s, v, dv_true, v_l_true, v_dot, T_cur, mask]

    return traj


# ===========================================================
# 5. SIMULATORE SCENARIO CUT-IN (UC2)
# ===========================================================

def simulate_cut_in_trajectory(params, profile='sinusoidal', seed=None):
    """
    Simula una traiettoria con evento di cut-in (UC2 -- Abrupt Cut-In).

    Struttura temporale:
        [0, t_cutin)    : following normale con leader A (lontano)
        t_cutin         : veicolo B taglia in — gap si riduce bruscamente
        [t_cutin, fine] : following con leader B (piu' vicino/diverso)

    Il gap post-cut-in e' campionato da U(CUT_IN_S_MIN, CUT_IN_S_MAX).
    La velocita' del veicolo B e' leggermente diversa dall'ego.

    Restituisce array (N_steps, 7) float32 (stesso formato di simulate_trajectory).
    """
    rng = np.random.default_rng(seed)
    N   = int(SIM_DURATION / DT)

    # Momento del cut-in: dopo il warmup, tra 30% e 70% della traiettoria
    warmup_steps = int(WARMUP_DURATION / DT)
    t_cutin = rng.integers(
        warmup_steps + int(0.10 * N),
        warmup_steps + int(0.60 * N)
    )

    # Profilo leader originale (A)
    v_l_A = _leader_profile(profile, N, DT, rng, params['v0'])

    # Leader dopo cut-in (B): velocita' leggermente inferiore all'ego
    v_cutin = float(params['v0']) * rng.uniform(0.55, 0.85)
    dv_cutin = rng.uniform(0.0, min(CUT_IN_DV_MAX, v_cutin))
    v_B_base = max(0.0, v_cutin - dv_cutin)
    # Leader B ha profilo sinusoidale lento dopo il taglio
    v_l_B = _leader_profile('sinusoidal', N, DT, rng, v_B_base)

    # Gap iniziale post-cut-in
    s_cutin = rng.uniform(CUT_IN_S_MIN, CUT_IN_S_MAX)

    # Condizioni iniziali
    T_cur = rng.uniform(IDM2D_T1, IDM2D_T2)
    v     = params['v0'] * 0.8
    s     = params['s0'] + v * T_cur + rng.uniform(-2.0, 2.0)

    # OU rumori
    eta_s = 0.0
    eta_v = 0.0
    eta_a = 0.0

    # a_l filter
    alpha_al = np.exp(-DT / ACC_AL_TAU)
    a_l_filt = 0.0
    v_l_prev = float(v_l_A[0])

    cut_in_done = False
    traj = np.zeros((N, 7), dtype=np.float32)

    for i in range(N):
        # Determina leader attivo
        if i < t_cutin:
            v_l_true = float(v_l_A[i])
        else:
            if not cut_in_done:
                # Evento cut-in: gap si imposta al valore campionato
                s = s_cutin
                v_l_prev = float(v_l_B[i])   # reset stima a_l
                a_l_filt = 0.0
                cut_in_done = True
            v_l_true = float(v_l_B[i])

        T_cur = _idm2d_T_step(T_cur, IDM2D_T1, IDM2D_T2, IDM2D_TAU, DT, rng)

        eta_s = _ou_step(eta_s, NOISE_TAU_S, DT, rng)
        eta_v = _ou_step(eta_v, NOISE_TAU_V, DT, rng)
        eta_a = _ou_step(eta_a, NOISE_TAU_A, DT, rng)

        s_perc  = s * np.exp(NOISE_GAP_REL * eta_s)
        vl_perc = v_l_true - s * NOISE_VEL_OPT * eta_v

        a_l_raw  = (v_l_true - v_l_prev) / DT
        a_l_filt = alpha_al * a_l_filt + (1.0 - alpha_al) * a_l_raw
        v_l_prev = v_l_true

        p_step = dict(params, T=T_cur)
        v_dot  = _acc_iidm_accel(s_perc, v, vl_perc, a_l_filt, p_step) \
                 + NOISE_ACCEL * eta_a

        dv_true = v - v_l_true
        v_new   = float(np.clip(v + v_dot * DT, 0.0, params['v0'] * 1.2))
        s       = float(np.clip(s + (v_l_true - v) * DT, params['s0'] * 0.5, NORM_S_MAX))
        v       = v_new

        mask = 0.0 if rng.random() < V2X_PACKET_LOSS else 1.0

        traj[i] = [s, v, dv_true, v_l_true, v_dot, T_cur, mask]

    return traj


# ===========================================================
# 6. NORMALIZZAZIONE
# ===========================================================

def normalize(traj):
    """
    Normalizza i 4 segnali di input in [0, 1].
    Restituisce:
      x_norm (N, 4)  -- input normalizzato per la SNN
      y_phys (N, 2)  -- [v_dot, T_true] ground truth PINN
      mask   (N,)    -- packet loss mask
    """
    s   = traj[:, 0] / NORM_S_MAX
    v   = traj[:, 1] / NORM_V_MAX
    # Clamp prima della normalizzazione: evita valori fuori [0,1] in
    # scenari estremi (cut-in + rumore OU) che causerebbero dv_obs
    # fuori range nella pinn_loss e valori fisici errati nella CAH.
    dv_phys = np.clip(traj[:, 2], -NORM_DV_MAX, NORM_DV_MAX)
    dv  = (dv_phys + NORM_DV_MAX) / (2.0 * NORM_DV_MAX)
    v_l = traj[:, 3] / NORM_VL_MAX

    x_norm = np.stack([s, v, dv, v_l], axis=1).astype(np.float32)
    y_phys = traj[:, [4, 5]].astype(np.float32)
    mask   = traj[:, 6].astype(np.float32)
    return x_norm, y_phys, mask


# ===========================================================
# 7. CAMPIONAMENTO SCENARIO
# ===========================================================

def _sample_scenario(rng):
    """
    Campiona parametri, profilo e tipo di scenario dalla distribuzione SCENARIO_MIX.
    Con probabilita' CUT_IN_RATIO lo scenario e' marcato come cut-in (UC2).
    """
    types  = list(SCENARIO_MIX.keys())
    probs  = list(SCENARIO_MIX.values())
    stype  = types[rng.choice(len(types), p=probs)]

    if stype == 'highway':
        p = dict(IDM_HWY)
        p['v0'] *= rng.uniform(0.85, 1.15)
        p['T']   = rng.uniform(IDM2D_T1, IDM2D_T2)
        p['a']  *= rng.uniform(0.80, 1.20)
        prof = rng.choice(['constant', 'sinusoidal'])

    elif stype == 'urban':
        p = dict(IDM_URB)
        p['v0'] *= rng.uniform(0.80, 1.10)
        p['T']   = rng.uniform(0.70, 1.30)
        prof = rng.choice(['stop_and_go', 'sinusoidal'])

    elif stype == 'truck':
        p = dict(IDM_TRK)
        p['v0'] *= rng.uniform(0.90, 1.05)
        p['T']   = rng.uniform(1.40, 2.20)
        prof = 'constant'

    else:  # mixed
        p = dict(IDM_HWY)
        p['v0'] *= rng.uniform(0.40, 0.70)
        p['T']   = rng.uniform(IDM2D_T1, IDM2D_T2)
        prof = rng.choice(['stop_and_go', 'sinusoidal'])

    # Marcatura cut-in (UC2)
    is_cut_in = rng.random() < CUT_IN_RATIO

    return p, str(prof), stype, bool(is_cut_in)


# ===========================================================
# 8. GENERAZIONE DEL DATASET COMPLETO
# ===========================================================

def generate_dataset(n_scenarios, base_seed=SEED):
    """
    Genera n_scenarios traiettorie ACC-IDM.
    Il 20% (CUT_IN_RATIO) include un evento di cut-in (UC2).
    Restituisce lista di dict: x, y, mask, raw, params, profile, scenario, cut_in.
    """
    rng          = np.random.default_rng(base_seed)
    dataset      = []
    warmup_steps = int(WARMUP_DURATION / DT)
    n_cutin      = 0

    for i in range(n_scenarios):
        seed_i             = int(rng.integers(0, 2**31))
        p, prof, stype, is_cutin = _sample_scenario(rng)

        if is_cutin:
            traj = simulate_cut_in_trajectory(p, profile=prof, seed=seed_i)
            n_cutin += 1
        else:
            traj = simulate_trajectory(p, profile=prof, seed=seed_i)

        traj       = traj[warmup_steps:]
        x, y, mask = normalize(traj)

        dataset.append({
            'x'       : x,
            'y'       : y,
            'mask'    : mask,
            'raw'     : traj,
            'params'  : p,
            'profile' : prof,
            'scenario': stype,
            'cut_in'  : is_cutin,
        })

        if (i + 1) % 500 == 0:
            print(f"  Generati {i + 1}/{n_scenarios} scenari "
                  f"(cut-in: {n_cutin}/{i+1} = "
                  f"{n_cutin/(i+1)*100:.1f}%)...")

    return dataset


def generate_all_splits(save_dir=None):
    """Genera train/val/test e opzionalmente li salva come .pkl."""
    print("[ACC-IDM Generator] Generazione dataset sintetico CF_FSNN")
    print(f"  Train: {N_SCENARIOS_TRAIN} | Val: {N_SCENARIOS_VAL} | Test: {N_SCENARIOS_TEST}")
    print(f"  Durata per traiettoria: {SIM_DURATION}s (warmup {WARMUP_DURATION}s escluso)")
    print(f"  Scenari: {SCENARIO_MIX}  |  Cut-in ratio: {CUT_IN_RATIO*100:.0f}%\n")

    print("[1/3] Training set...")
    train = generate_dataset(N_SCENARIOS_TRAIN, base_seed=SEED)
    print("[2/3] Validation set...")
    val   = generate_dataset(N_SCENARIOS_VAL,   base_seed=SEED + 1)
    print("[3/3] Test set...")
    test  = generate_dataset(N_SCENARIOS_TEST,  base_seed=SEED + 2)

    if save_dir is not None:
        import pickle
        import pathlib
        pathlib.Path(save_dir).mkdir(parents=True, exist_ok=True)
        for name, data in [('train', train), ('val', val), ('test', test)]:
            path = os.path.join(save_dir, f'{name}.pkl')
            with open(path, 'wb') as f:
                pickle.dump(data, f)
            print(f"  Salvato: {path}")

    return train, val, test


# ===========================================================
# 9. STATISTICHE DI SANITY CHECK
# ===========================================================

def print_dataset_stats(dataset, name='dataset'):
    """Stampa statistiche di controllo (range fisici, T, packet loss, cut-in)."""
    from collections import Counter
    all_s   = np.concatenate([d['raw'][:, 0] for d in dataset])
    all_v   = np.concatenate([d['raw'][:, 1] for d in dataset])
    all_T   = np.concatenate([d['raw'][:, 5] for d in dataset])
    all_pk  = np.concatenate([d['mask']      for d in dataset])
    counts  = Counter(d['scenario'] for d in dataset)
    n_cutin = sum(1 for d in dataset if d['cut_in'])

    print(f"\n{'='*56}")
    print(f" STATS: {name}")
    print(f"{'='*56}")
    print(f" Traiettorie       : {len(dataset)}")
    print(f" Steps per traj    : {dataset[0]['raw'].shape[0]}")
    print(f" Scenari           : {dict(counts)}")
    print(f" Cut-in            : {n_cutin} ({n_cutin/len(dataset)*100:.1f}%)")
    print(f" Gap s      [m]    : {all_s.min():.1f} / {all_s.mean():.1f} / {all_s.max():.1f}")
    print(f" Vel v   [m/s]     : {all_v.min():.1f} / {all_v.mean():.1f} / {all_v.max():.1f}")
    print(f" T_true   [s]      : {all_T.min():.2f} / {all_T.mean():.2f} / {all_T.max():.2f}")
    print(f" Packet loss        : {(1-all_pk.mean())*100:.1f}%  (atteso ~{V2X_PACKET_LOSS*100:.0f}%)")
    print(f"{'='*56}\n")


# ===========================================================
# MAIN -- test rapido
# ===========================================================

if __name__ == '__main__':
    print("Test generatore ACC-IDM (scenario singolo)...\n")
    rng = np.random.default_rng(SEED)
    p, prof, stype, is_cutin = _sample_scenario(rng)
    print(f"  Scenario : {stype}  |  Profilo leader: {prof}  |  Cut-in: {is_cutin}")
    print(f"  Parametri: {p}\n")

    if is_cutin:
        traj = simulate_cut_in_trajectory(p, profile=prof, seed=SEED)
    else:
        traj = simulate_trajectory(p, profile=prof, seed=SEED)

    warmup = int(WARMUP_DURATION / DT)
    traj   = traj[warmup:]
    x, y, mask = normalize(traj)

    print(f"  Shape traiettoria (dopo warmup) : {traj.shape}")
    print(f"  Shape input normalizzato        : {x.shape}")
    print(f"  Shape ground truth (v_dot, T)   : {y.shape}")
    print(f"  Packet loss effettivo           : {(1-mask.mean())*100:.1f}%")
    print(f"\n  Primi 5 step [s, v, dv, vl, vdot, T, mask]:")
    hdr = f"  {'s':>7} {'v':>7} {'dv':>7} {'vl':>7} {'vdot':>7} {'T':>6} {'mask':>5}"
    print(hdr)
    for row in traj[:5]:
        print(f"  {row[0]:7.2f} {row[1]:7.2f} {row[2]:7.2f} {row[3]:7.2f}"
              f" {row[4]:7.3f} {row[5]:6.3f} {int(row[6]):5d}")

    # Test cut-in esplicito
    print("\n  Test cut-in esplicito:")
    traj_ci = simulate_cut_in_trajectory(p, profile=prof, seed=SEED)
    print(f"  s_min durante cut-in (tutti gli step): {traj_ci[:, 0].min():.2f} m")
    print(f"  (atteso >= {p['s0']*0.5:.1f} m per crash provision)")

    print("\nTest completato. Usa generate_all_splits() per il dataset completo.")
