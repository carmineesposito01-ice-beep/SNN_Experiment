"""utils/io_hil.py -- Fase A FPGA (F6, sezione 08 IO_HIL): interfaccia I/O e Hardware-in-the-Loop.

Complementa lo sweep V2X gia' esistente (scripts.closed_loop_identify.v2x_robustness_sweep:
PDR/latenza/jitter/Gilbert/hold_mode/blackout) con le tre grandezze specifiche del deploy:
  * aoi_max_surface : eta' MASSIMA tollerabile del CAM (Age-of-Information) prima della
    collisione, su una griglia (gap x Delta-v). Requisito HARD sul bus: se il bus non
    garantisce freschezza < AoI_max, serve un fail-safe. Riusa simulate(channel=...).
  * queue_overflow  : buffer minimo anti-burst -> drop-rate vs profondita' coda (M/M/1/K,
    STIMA analitica).
  * cold_start_deviation : deviazione dei 5 param nei primi k step (poca storia) vs regime.

Tutto software-only sui simulatori/identify esistenti. I numeri di coda sono STIME (modello
di coda), non misure; AoI_max e cold-start sono ricavati dal closed-loop reale.
"""
import numpy as np
import torch

DT_S = 0.1
PARAM_SCALE = np.array([33.3, 1.2, 2.5, 1.1, 1.5], dtype=np.float64)   # [v0,T,s0,a,b]
_PN = ['v0', 'T', 's0', 'a', 'b']


def _brake_profile(vl0, t_brake, brake_accel, horizon):
    """Leader: crociera a vl0, poi frenata (brake_accel<0) da t_brake. Array (horizon,)."""
    vl = np.full(horizon, float(vl0), dtype=np.float32)
    for t in range(t_brake, horizon):
        vl[t] = max(0.0, vl[t - 1] + brake_accel * DT_S)
    return vl


def aoi_max_surface(model, cache, gaps=(8.0, 15.0, 25.0, 40.0), dvs=(0.0, 5.0, 10.0, 15.0),
                    driver_idx=0, v_ego=20.0, brake_accel=-6.0, t_brake=40, horizon=200,
                    max_stale_steps=40, seq_len=50, device='cpu'):
    """Griglia AoI_max(gap, Delta-v): max staleness del CAM (in step e in s) prima della collisione.

    Per ogni cella si costruisce un hard-brake del leader a t_brake e si cerca (ricerca binaria)
    la lunghezza massima di blackout da t_brake che NON causa collisione: quello e' l'AoI massimo
    tollerabile. Delta-v > 0 = ego piu' veloce (chiusura).

    Family-agnostic: i param di guida si IDENTIFICANO UNA VOLTA dal champion (forward_sequence,
    ok per baseline ed eventprop), poi si guida l'IDM con simulate(model=None) -> la staleness
    degrada la PERCEZIONE (s_obs/vl_obs), non serve il forward_step per-step (che eventprop non fa).
    model=None -> usa i param VERI del driver (superficie AoI dell'oracolo).
    """
    from utils.closed_loop_eval import simulate
    from scripts.closed_loop_identify import identify
    it = cache['val'][driver_idx]
    pg = np.array([it['params'][k] for k in _PN], dtype=np.float32)
    if model is None:
        drive_params = pg
    else:
        xwin = torch.tensor(it['x'][:seq_len][None], dtype=torch.float32).to(device)
        drive_params = np.asarray(identify(model, xwin), dtype=np.float32)
    grid = np.full((len(dvs), len(gaps)), np.nan)

    for i, dv in enumerate(dvs):
        vl0 = max(1.0, float(v_ego) - float(dv))
        vl = _brake_profile(vl0, t_brake, brake_accel, horizon)
        for j, gap in enumerate(gaps):
            def collides(L):
                ch = {'hold_mode': 'hold_last', 'blackout_steps': (t_brake, t_brake + int(L))}
                tr = simulate(None, drive_params, vl, float(gap), float(v_ego), channel=ch, device=device)
                col = tr.get('collided')
                return bool(col) if col is not None else bool(np.min(tr['s']) <= 0.05)
            if collides(0):                       # collide anche senza staleness
                grid[i, j] = 0.0; continue
            if not collides(max_stale_steps):     # tollera anche il massimo testato
                grid[i, j] = float(max_stale_steps); continue
            lo, hi = 0, max_stale_steps           # cerca il max L senza collisione
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if collides(mid):
                    hi = mid
                else:
                    lo = mid
            grid[i, j] = float(lo)
    return {'gaps': list(gaps), 'dvs': list(dvs), 'dt_s': DT_S,
            'aoi_max_steps': grid, 'aoi_max_s': grid * DT_S}


def queue_overflow(depths=(1, 2, 4, 8, 16, 32), rho=0.7):
    """Drop-rate vs profondita' buffer (M/M/1/K, STIMA analitica). rho = arrivo/servizio.

    P_block(K) = (1-rho) rho^K / (1 - rho^(K+1)); rho=1 -> 1/(K+1). Base della figura
    queue_overflow (buffer minimo anti-burst dei CAM). Numero = STIMA (modello di coda).
    """
    rows = []
    for K in depths:
        if abs(rho - 1.0) < 1e-9:
            pb = 1.0 / (K + 1)
        else:
            pb = ((1.0 - rho) * rho ** K) / (1.0 - rho ** (K + 1))
        rows.append({'buffer_depth': int(K), 'rho': float(rho), 'drop_rate': float(pb)})
    return rows


def cold_start_deviation(model, cache, ks=(2, 4, 6, 8, 10, 15, 25), n_drivers=8,
                         seq_len=50, device='cpu'):
    """Deviazione relativa dei 5 param stimati sui primi k step vs finestra piena (regime).

    Quantifica l'errore a freddo (poca storia) -> failure-mode di cold-start della FMEDA.
    Riusa identify() su prefissi crescenti. Ritorna una riga per k.
    """
    from scripts.closed_loop_identify import identify
    rows = []
    for k in ks:
        errs = []
        for it in cache['val'][:n_drivers]:
            x = torch.tensor(it['x'][:seq_len][None], dtype=torch.float32).to(device)
            if x.shape[1] < max(k, 2):
                continue
            p_full = np.asarray(identify(model, x), dtype=np.float64)
            p_k = np.asarray(identify(model, x[:, :int(k), :]), dtype=np.float64)
            errs.append(float(np.mean(np.abs(p_k - p_full) / PARAM_SCALE)))
        rows.append({'k_steps': int(k),
                     'rel_param_dev_mean': float(np.mean(errs)) if errs else float('nan'),
                     'rel_param_dev_std': float(np.std(errs)) if errs else float('nan')})
    return rows
