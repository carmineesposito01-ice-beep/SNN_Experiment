"""
train.py -- Training loop PINN per CF_FSNN (ACC-IDM con base IIDM)
===================================================================
Addestra la rete CF_FSNN_Net su dati ACC-IDM sintetici con loss PINN:

    L = λ_data * RMSE_masked(a_pred, a_gt)  [fit accelerazione, Ch17 MoP]
      + λ_phys * MSE(a_ACC-IDM, a_gt)        [residuo ACC-IDM con IIDM base]
      + λ_OU   * OU_residual(T_seq)          [mean-reversion su T, Ch12]
      + λ_bc   * crash_penalty(s, s0_pred)   [boundary condition Ch17]

Dataset: sintetico ACC-IDM da data/generator.py (20% scenari cut-in UC2).
Architettura: CF_FSNN_Net (ALIF 4→32→5, rank=8, max_delay=6).
Hardware target: PYNQ-Z1 (pesi power-of-2, bit-shift leak).

Uso:
    python train.py                                        # genera dataset + allena
    python train.py --load_data data/                      # usa .pkl pre-generati
    python train.py --epochs 5 --scheduler onecycle --tag A1_onecycle
    python train.py --epochs 50 --scheduler cosine --lr 3e-4 --optimizer lion --tag FULL_v1
"""

import argparse
import csv
import json
import math
import os
import pickle
import sys
import time

import numpy as np  # R25: per metriche val tracking_corr / pred_mean / intra_std

# Percorso assoluto della directory del file — usato per save_dir
# Evita il problema del CWD diverso su Azure (SLURM, container, ecc.)
_HERE = os.path.dirname(os.path.abspath(__file__))

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DEVICE, SEED, set_seed,
    BATCH_SIZE, LEARNING_RATE, EPOCHS,
    LAMBDA_DATA, LAMBDA_PHYS, LAMBDA_OU, LAMBDA_BC,
    LAMBDA_SR, SPIKE_RATE_TARGET,                # B5
    NORM_S_MAX, NORM_V_MAX, NORM_DV_MAX, NORM_VL_MAX,
    ACC_COOLNESS, ACC_AL_TAU,
    N_SCENARIOS_TRAIN, N_SCENARIOS_VAL,
    DT,
)
from core.network import CF_FSNN_Net, build_model


# ===========================================================
# Lion optimizer (Chen et al. 2023 — sign-based, hardware-friendly)
# Ogni moltiplicazione lr e' power-of-2 → bit-shift su FPGA
# Analogo biologico: plasticita' sinaptica binaria (Hebb)
# ===========================================================

class LionOptimizer(torch.optim.Optimizer):
    """
    Lion: EvoLved Sign Momentum (Chen et al. 2023).
    Update rule:
        c_t = β2 * m_{t-1} + (1 − β2) * g_t
        θ_t = θ_{t-1} − lr * (sign(β1 * m_{t-1} + (1 − β1) * g_t) + wd * θ_{t-1})
        m_t = c_t
    Vantaggi: 3-4× meno memoria degli stati di Adam, gradiente costante.
    """
    def __init__(self, params, lr=1e-3, betas=(0.9, 0.99), weight_decay=0.0):
        defaults = dict(lr=lr, betas=betas, weight_decay=weight_decay)
        super().__init__(params, defaults)

    @torch.no_grad()
    def step(self, closure=None):
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        for group in self.param_groups:
            lr = group['lr']
            beta1, beta2 = group['betas']
            wd = group['weight_decay']
            for p in group['params']:
                if p.grad is None:
                    continue
                g = p.grad
                state = self.state[p]
                if 'exp_avg' not in state:
                    state['exp_avg'] = torch.zeros_like(p)
                m = state['exp_avg']
                # Update
                update = beta1 * m + (1.0 - beta1) * g
                p.add_(torch.sign(update), alpha=-lr)
                if wd != 0.0:
                    p.mul_(1.0 - lr * wd)
                # Momentum update
                m.mul_(beta2).add_(g, alpha=1.0 - beta2)

        return loss


# ===========================================================
# Dataset
# ===========================================================

class CFDataset(Dataset):
    """
    Dataset car-following su finestre temporali di lunghezza seq_len.

    Ogni elemento restituisce (4-tuple):
        x         (seq_len, 4)  -- input normalizzato [s̃, ṽ, Δṽ, ṽ_l]
        y         (seq_len, 2)  -- ground truth [v_dot [m/s²], T_true [s]]
        mask      (seq_len,)    -- V2X packet mask (1=ricevuto, 0=lost)
        params_gt (4,)          -- R30: GT [v0, s0, a, b] constante per scenario
                                   (T_true e' gia' in y[:,1] per supervisione T_aux).
                                   Estratto dal dict 'params' di generate_dataset().
                                   Default zeros se 'params' non disponibile (backward-compat).

    R30 (2026-06-12): aggiunto params_gt come 4-tuple element. Tutti i v2 notebook usano
    questa interfaccia. Backward-compat: se lambdas v0/s0/a/b_aux=0 (default), params_gt
    e' ignorato in pinn_loss → comportamento identico al pre-R30.
    """

    def __init__(self, dataset_list, seq_len=100, stride=50, extra_channels=False):
        self.seq_len = seq_len
        # L3 #2 (encoding): se True, __getitem__ aggiunge 3 canali derivata temporale
        # [ṡ, accel_obs, Δv'] = diff(s), diff(v), diff(Δv) -> input 4->7. Danno alla rete
        # la FIRMA del transitorio (oggi assente dal singolo step: causa L1c). Default False.
        self.extra_channels = extra_channels
        self.windows = []

        # R30 — indice canali in CF_FSNN_Net._PARAM_BOUNDS: 0=v0, 1=T, 2=s0, 3=a, 4=b
        # params_gt salva i 4 NON-temporali: v0, s0, a, b (T e' dinamico in y).
        for item in dataset_list:
            x    = item['x']
            y    = item['y']
            mask = item['mask']
            # Estrai GT params se presenti; fallback zeros per backward-compat.
            p_dict = item.get('params', None)
            if p_dict is None:
                params_gt = np.zeros(4, dtype=np.float32)
            else:
                params_gt = np.array([
                    p_dict.get('v0', 0.0),
                    p_dict.get('s0', 0.0),
                    p_dict.get('a',  0.0),
                    p_dict.get('b',  0.0),
                ], dtype=np.float32)
            N     = x.shape[0]
            start = 0
            while start + seq_len <= N:
                self.windows.append((
                    x[start:start + seq_len],
                    y[start:start + seq_len],
                    mask[start:start + seq_len],
                    params_gt,
                ))
                start += stride

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, idx):
        x, y, mask, params_gt = self.windows[idx]
        if self.extra_channels:
            # canali derivata su s,v,Δv (col 0,1,2): diff temporale, prima riga = 0 (causale).
            d = np.zeros((x.shape[0], 3), dtype=np.float32)
            d[1:, :] = x[1:, :3] - x[:-1, :3]
            x = np.concatenate([x, d], axis=1)   # (seq_len, 7)
        return (
            torch.from_numpy(x),
            torch.from_numpy(y),
            torch.from_numpy(mask),
            torch.from_numpy(params_gt),
        )


# ===========================================================
# PINN Loss (ACC-IDM con base IIDM)
# ===========================================================

def pinn_loss(model, x_seq, y_seq, mask_seq,
              lam_data, lam_phys, lam_ou, lam_bc, lam_sr=0.0,
              lam_T_aux=0.0,
              lam_v0_aux=0.0, lam_s0_aux=0.0, lam_a_aux=0.0, lam_b_aux=0.0,
              lam_geo_aux=0.0, lam_ratio_aux=0.0, regime_gamma=0.0, regime_thr=0.5,
              lam_nll=0.0,
              params_gt=None,
              spike_target=SPIKE_RATE_TARGET,
              retain_params_grad=False):
    """
    Loss PINN a cinque componenti con ACC-IDM (IIDM base).

    x_seq:    (batch, T, 4)  -- input normalizzato
    y_seq:    (batch, T, 2)  -- [v_dot [m/s²], T_true [s]]
    mask_seq: (batch, T)     -- V2X mask

    Physics: usa CF_FSNN_Net.acc_iidm_accel() con a_l stimata da
    differenze finite su v_l + filtro OU (tau=ACC_AL_TAU).

    B5 — Spike-rate regularizer: L_sr = (avg_spike_rate - spike_target)^2.
    Penalizza degenerazione verso dead network (firma di P6_T2_full).
    Quando lam_sr=0.0 il termine è disattivo (backward-compatibile pre-B5).

    R25 — lam_T_aux > 0 abilita supervisione diretta su T usando y_seq[:, :, 1].
    L_T_aux = masked MSE tra params_seq[:, :, 1] e y_seq[:, :, 1]. Default 0
    (backward-compatibile pre-R25).

    R25 — retain_params_grad=True chiama .retain_grad() su params_seq prima del
    return, permettendo a train_epoch di leggere params_seq.grad dopo backward
    (per gradient diagnostics per-canale). Default False (no overhead in val).

    Ritorna: (loss_scalare, dict_componenti, spike_rate_media, params_seq)
    """
    batch, T_len, _ = x_seq.shape

    # ── Forward SNN ────────────────────────────────────────────────
    params_seq, spike_rates = model.forward_sequence_with_stats(x_seq)
    # params_seq: (batch, T, 5)  spike_rates: (batch, T) — hidden layer

    # R25 — retain grad su params_seq per estrarre d(loss)/d(decoded_i) post backward
    if retain_params_grad and params_seq.requires_grad:
        params_seq.retain_grad()

    # ── Denormalizza input ─────────────────────────────────────────
    s_obs   = x_seq[:, :, 0] * NORM_S_MAX
    v_obs   = x_seq[:, :, 1] * NORM_V_MAX
    dv_obs  = x_seq[:, :, 2] * (2.0 * NORM_DV_MAX) - NORM_DV_MAX
    vl_obs  = x_seq[:, :, 3] * NORM_VL_MAX

    v_dot_gt = y_seq[:, :, 0]   # (batch, T) accelerazione GT [m/s²]

    # ── Stima a_l da differenze finite + filtro OU ─────────────────
    # a_l_raw[t] = (v_l[t] - v_l[t-1]) / DT  (prima differenza)
    vl_diff = torch.diff(vl_obs, dim=1) / DT          # (batch, T-1)
    vl_diff = torch.cat([vl_diff[:, :1], vl_diff], dim=1)  # (batch, T)
    # Filtro OU (IIR): y[t] = alpha*y[t-1] + beta*x[t],  y[0] = x[0]
    # Soluzione chiusa (nessun loop Python → un solo pass su GPU):
    #   y[t] = alpha^t * ( alpha*x[0] + beta * cumsum(x[k]/alpha^k)[t] )
    alpha_al = math.exp(-DT / ACC_AL_TAU)
    beta_al  = 1.0 - alpha_al
    t_idx    = torch.arange(T_len, device=vl_diff.device, dtype=vl_diff.dtype)
    inv_pow  = alpha_al ** (-t_idx)               # (T,) = [1, 1/α, 1/α², …]
    fwd_pow  = alpha_al **   t_idx                # (T,) = [1, α,   α², …]
    x_sc     = vl_diff * inv_pow                  # (batch, T)
    cs       = torch.cumsum(x_sc, dim=1)          # (batch, T)
    a_l_filt = fwd_pow * (alpha_al * vl_diff[:, :1] + beta_al * cs)  # (batch, T)

    # ── Accelerazione predetta da ACC-IDM con parametri SNN ────────
    a_pred = CF_FSNN_Net.acc_iidm_accel(
        s_obs.reshape(-1),
        v_obs.reshape(-1),
        dv_obs.reshape(-1),
        a_l_filt.reshape(-1),
        params_seq.reshape(-1, 5),
        coolness=ACC_COOLNESS,
    ).reshape(batch, T_len)

    # ── L_data: masked RMSE(a_pred, a_gt) sui passi con V2X ok ──────
    # NOTA: la precedente formula SRMSE usava denom = v_dot_gt.pow(2).sum() + eps.
    # Quando un intero batch è constant-speed (v_dot_gt ≈ 0 ovunque),
    # denom ≈ eps = 1e-8 → grad esplode a ~1e9+ → pesi corrotti → inf permanente.
    # Fix: normalizzare per numero di campioni V2X validi (sempre ≥ 1), non per
    # energia GT. Gradiente massimo = |a_pred - v_dot_gt| / (N_valid * L_data)
    # ≤ 9 / (1 * 1e-4) = 9e4 — safe per float32 e clip a 1.0.
    eps     = 1e-8
    sq_err  = mask_seq * (a_pred - v_dot_gt) ** 2
    N_valid = mask_seq.sum().clamp(min=1.0)
    L_data  = torch.sqrt(sq_err.sum() / N_valid + eps)

    # ── L_phys: residuo ACC-IDM su TUTTI i passi ──────────────────
    L_phys = torch.mean((a_pred - v_dot_gt) ** 2)

    # ── L_OU: mean-reversion su T(t) ─────────────────────────────
    L_ou = model.ou_residual(params_seq)

    # ── L_bc: crash prevention s >= s0_pred ──────────────────────
    s0_pred = params_seq[:, :, 2]
    L_bc    = torch.mean(torch.relu(s0_pred - s_obs + 0.1) ** 2)

    # ── L_sr (B5): spike-rate regularizer ────────────────────────
    # Spinge spike_rate verso spike_target. Quando lam_sr=0 contributo nullo.
    # Usa il tensor (non .item()) per preservare il gradiente verso i pesi della rete.
    spike_rate_tensor = spike_rates.mean()
    L_sr = (spike_rate_tensor - spike_target) ** 2

    # ── L_T_aux (R25): supervisione diretta su T ─────────────────
    # Forza pred_T(t) ≈ T_true(t) usando il GT per-timestep in y_seq[:, :, 1].
    # Solo se lam_T_aux > 0. Default 0 = backward-compatibile.
    if lam_T_aux > 0.0:
        T_pred = params_seq[:, :, 1]                 # (batch, T)
        T_true = y_seq[:, :, 1]                      # (batch, T) ground truth T
        sq_err_T = mask_seq * (T_pred - T_true) ** 2
        L_T_aux = sq_err_T.sum() / N_valid
    else:
        L_T_aux = torch.zeros((), device=x_seq.device)

    # ── L_<p>_aux (R30 ID-1): supervisione su v0, s0, a, b ──
    # GT params sono COSTANTI per scenario (estratti da generate_dataset dict).
    # params_gt: (batch, 4) = [v0, s0, a, b]. Indici in params_seq: 0=v0, 2=s0, 3=a, 4=b.
    # L_<p>_aux = mean_over_(B,T) (pred_<p>(t) - gt_<p>)^2
    _aux_cfg = [(lam_v0_aux, 0, 0), (lam_s0_aux, 2, 1),
                (lam_a_aux,  3, 2), (lam_b_aux,  4, 3)]
    aux_losses = {}
    L_params_aux_total = torch.zeros((), device=x_seq.device)
    if params_gt is not None and any(lam > 0.0 for lam, _, _ in _aux_cfg):
        for lam_p, idx_pred, idx_gt in _aux_cfg:
            if lam_p > 0.0:
                p_pred = params_seq[:, :, idx_pred]                    # (B, T)
                p_gt   = params_gt[:, idx_gt].unsqueeze(1).expand_as(p_pred)
                sq_err = mask_seq * (p_pred - p_gt) ** 2
                L_p    = sq_err.sum() / N_valid
                aux_losses[idx_pred] = L_p
                L_params_aux_total = L_params_aux_total + lam_p * L_p

    # ── L2 (Dynamic_Study): reparam [a,b] -> (geo-mean, log-ratio) + per-regime ──
    # Diagnosi L1c/L1d: la rete fissa bene √(ab) (via L_data) ma il RAPPORTO a/b e' la
    # direzione molle non vincolata -> b anti-correlato per-driver. Qui si supervisiona
    # ESPLICITAMENTE la decomposizione in log-spazio:
    #   geo   = 0.5*(log a + log b) = log √(ab)   (magnitudine, gia' vincolata da L_data)
    #   ratio = log a - log b        = log(a/b)   (direzione molle: la si vincola QUI)
    # regime_gamma>0 concentra il peso sui TRANSITORI (|v_dot_gt|>regime_thr), dove a/b
    # sono osservabili (Studio B: Fisher cond crolla coi transitori). Default 0 = no-op.
    L_geo = torch.zeros((), device=x_seq.device)
    L_ratio = torch.zeros((), device=x_seq.device)
    if params_gt is not None and (lam_geo_aux > 0.0 or lam_ratio_aux > 0.0):
        eps_p = 1e-3
        log_a_pr = torch.log(params_seq[:, :, 3].clamp_min(eps_p))   # (B,T)
        log_b_pr = torch.log(params_seq[:, :, 4].clamp_min(eps_p))
        log_a_gt = torch.log(params_gt[:, 2].clamp_min(eps_p)).unsqueeze(1)   # (B,1)
        log_b_gt = torch.log(params_gt[:, 3].clamp_min(eps_p)).unsqueeze(1)
        geo_pr = 0.5 * (log_a_pr + log_b_pr); geo_gt = 0.5 * (log_a_gt + log_b_gt)
        rat_pr = log_a_pr - log_b_pr;          rat_gt = log_a_gt - log_b_gt
        if regime_gamma > 0.0:
            w_reg = 1.0 + regime_gamma * (v_dot_gt.abs() > regime_thr).float()   # (B,T)
        else:
            w_reg = torch.ones_like(mask_seq)
        wm = mask_seq * w_reg
        denom_w = wm.sum().clamp(min=1.0)
        L_geo = (wm * (geo_pr - geo_gt) ** 2).sum() / denom_w
        L_ratio = (wm * (rat_pr - rat_gt) ** 2).sum() / denom_w

    # ── L_nll (L3 #5): uncertainty head eteroschedastica ─────────
    # La rete dichiara una log-varianza per-parametro; NLL gaussiana eteroschedastica
    #   0.5*exp(-s)*(μ-gt)^2 + 0.5*s  → impara media E confidenza (b dovrebbe risultare
    # a bassa confidenza = s alto). Supervisione su v0,s0,a,b (costanti). Default 0 = off.
    L_nll = torch.zeros((), device=x_seq.device)
    if (lam_nll > 0.0 and params_gt is not None and getattr(model, 'uncertainty', False)
            and getattr(model, '_last_logvar_seq', None) is not None):
        lv = model._last_logvar_seq.clamp(-7.0, 7.0)            # (B,T,5)
        for pi, gi in [(0, 0), (2, 1), (3, 2), (4, 3)]:         # v0,s0,a,b: pred idx vs gt idx
            mu = params_seq[:, :, pi]
            s  = lv[:, :, pi]
            gt = params_gt[:, gi].unsqueeze(1)
            nll = 0.5 * torch.exp(-s) * (mu - gt) ** 2 + 0.5 * s
            L_nll = L_nll + (mask_seq * nll).sum() / N_valid

    loss = (lam_data * L_data
            + lam_phys * L_phys
            + lam_ou   * L_ou
            + lam_bc   * L_bc
            + lam_sr   * L_sr
            + lam_T_aux * L_T_aux
            + L_params_aux_total
            + lam_geo_aux * L_geo
            + lam_ratio_aux * L_ratio
            + lam_nll * L_nll)

    avg_spike_rate = spike_rate_tensor.item()

    comps_out = {
        'total': loss.item(),
        'data' : L_data.item(),
        'phys' : L_phys.item(),
        'ou'   : L_ou.item(),
        'bc'   : L_bc.item(),
        'sr'   : L_sr.item(),
        'T_aux': L_T_aux.item(),
        # R30 aux losses (0 se non calcolati)
        'v0_aux': aux_losses.get(0, torch.zeros(())).item() if 0 in aux_losses else 0.0,
        's0_aux': aux_losses.get(2, torch.zeros(())).item() if 2 in aux_losses else 0.0,
        'a_aux':  aux_losses.get(3, torch.zeros(())).item() if 3 in aux_losses else 0.0,
        'b_aux':  aux_losses.get(4, torch.zeros(())).item() if 4 in aux_losses else 0.0,
        'geo_aux':   L_geo.item(),
        'ratio_aux': L_ratio.item(),
        'nll':       L_nll.item(),
    }
    return loss, comps_out, avg_spike_rate, params_seq


# ===========================================================
# Train / Val epoch
# ===========================================================

LOG_EVERY           = 50
GRAD_WARN_THRESHOLD = 5.0   # log diagnostica se grad_norm > soglia (anche se finito)


def _log_batch_diagnostics(tag, comps, gn_total, x, pre_norms, model):
    """
    Diagnostica dettagliata per batch anomali. Chiamata in tre casi:
      (a) loss = nan/inf  → before backward, pre_norms=None
      (b) grad_norm = inf → sempre; pre_norms disponibili se has_inf_grad o diag=True
      (c) grad_norm > GRAD_WARN_THRESHOLD e diag=True → smoke/debug mode

    ATTENZIONE: clip_grad_norm_(total=inf) moltiplica tutti i grad per 0 (coeff=0),
    quindi le norme per-layer DEVONO essere calcolate PRIMA del clip per essere utili.
    pre_norms contiene le norme calcolate pre-clip; se None il log salta quella sezione.
    """
    # Loss components
    print(f"{tag} loss: total={comps['total']:.4f}  data={comps['data']:.4f}"
          f"  phys={comps['phys']:.5f}  ou={comps['ou']:.6f}  bc={comps['bc']:.6f}")

    # Input batch stats — x: (B, T, 4) = [s, v_ego, dv, v_l] normalizzati
    with torch.no_grad():
        gap   = x[:, :, 0]
        v_ego = x[:, :, 1]
        dv    = x[:, :, 2]
        print(f"{tag} input:"
              f"  gap=[{gap.min():.3f},{gap.max():.3f}]"
              f"  v_ego=[{v_ego.min():.3f},{v_ego.max():.3f}]"
              f"  dv=[{dv.min():.3f},{dv.max():.3f}] abs_mean={dv.abs().mean():.4f}")

    # Norme per-layer pre-clip (chiave per identificare quale layer esplode)
    if pre_norms is not None:
        def _sort_key(kv):
            return (0, 0) if not math.isfinite(kv[1]) else (1, -kv[1])
        worst = sorted(pre_norms.items(), key=_sort_key)[:12]
        lines = [f"    {'Layer':<42} {'grad_norm':>12}"]
        for name, val in worst:
            mark = "  *** INF ***" if not math.isfinite(val) else ""
            lines.append(f"    {name:<42} {val:>12.3e}{mark}")
        print(f"{tag} grad norms per layer (pre-clip):\n" + "\n".join(lines))

    # Weight stats — identifica pesi corrotti
    bad, wmax_global = [], 0.0
    for name, p in model.named_parameters():
        wmax = p.detach().abs().max().item()
        wmax_global = max(wmax_global, wmax)
        if not p.detach().isfinite().all():
            bad.append(f"    {name:<42} max={wmax:.3e}  *** INF/NAN ***")
        elif wmax > 10.0:
            bad.append(f"    {name:<42} max={wmax:.3e}  (large)")
    if bad:
        print(f"{tag} weight anomalies:\n" + "\n".join(bad))
    else:
        print(f"{tag} weights: all finite, global_max_abs={wmax_global:.3e}")


def adaptive_grad_clip(model, clip_lambda, eps=1e-3, skip_prefixes=('layer_out',)):
    """AGC — Adaptive Gradient Clipping (Brock et al. 2021, NFNets).

    Per ogni parametro multi-dim, clip per-UNITA' (per-riga, dim 0 = unita' di output):
    se ||g_unit|| / max(||w_unit||, eps) > clip_lambda, scala g_unit a clip_lambda*||w_unit||.
    Bound l'update relativamente alla dimensione dei pesi -> doma l'esplosione del gradiente
    su reti grandi. **Optimizer-agnostico** (agisce sui .grad PRIMA dello step) -> compatibile
    con Prodigy/AdamW/Lion senza sostituirli.

    Esclusioni (prassi NFNets + SNN): parametri 1-D (bias, soglie ALIF) e il layer di output
    (decoder dei 5 parametri). Default off; attivo solo con --grad_clip agc.
    inf grad -> scale=max_norm/inf=0 -> grad azzerato (sopprime l'esplosione); nan resta gestito
    dal guard frazione v2.
    """
    for name, p in model.named_parameters():
        if p.grad is None or p.dim() <= 1:
            continue
        if any(name.startswith(pref) for pref in skip_prefixes):
            continue
        dims = tuple(range(1, p.dim()))                                   # tutte tranne dim 0 (unita')
        w_norm = p.detach().norm(dim=dims, keepdim=True).clamp_(min=eps)
        g_norm = p.grad.detach().norm(dim=dims, keepdim=True)
        max_norm = w_norm * clip_lambda
        scale = (max_norm / g_norm.clamp_(min=1e-12)).clamp_(max=1.0)     # clip solo dove g_norm>max_norm
        p.grad.detach().mul_(scale)


def train_epoch(model, loader, optimizer, device, epoch, lam,
                scheduler=None, step_per_batch=False,
                log_every=LOG_EVERY, max_inf_streak=20, diag=False,
                batch_logger=None, max_steps_per_epoch=-1,
                explosion_threshold=float('inf'),
                grad_clip_mode='none', agc_lambda=0.01):
    """
    Esegue un'epoca di training con guardie e diagnostica.

    step_per_batch       — True per OneCycleLR (step dopo ogni batch).
    log_every            — frequenza log batch (1 = ogni batch, per smoke mode).
    max_inf_streak       — n. massimo di batch consecutivi con grad=inf prima di abortire.
    diag                 — True: calcola norme per-layer pre-clip su OGNI batch (smoke mode).
    batch_logger         — BatchCSVLogger opzionale (telemetria T): se non None, logga
                           una riga per OGNI batch (incluse NaN/inf) per analisi post-mortem.
    max_steps_per_epoch  — STEP 2C: cap step processati per epoca (-1 = unlimited).
                           Usato per bound del budget gradient updates quando il windowing
                           genera troppi batch.

    Ritorna dict metriche; se training abortito, include 'aborted': True.
    """
    model.train()
    totals     = {'total': 0.0, 'data': 0.0, 'phys': 0.0, 'ou': 0.0, 'bc': 0.0, 'sr': 0.0}
    spike_acc  = 0.0
    grad_acc   = 0.0
    n_batches  = 0
    inf_streak = 0          # batch consecutivi con grad_norm=inf
    max_gn_preclip = 0.0    # R30 explosion guard: max gn_total_preclip osservato in epoca
    n_seen_gn      = 0      # tutti i batch visti (denominatore frazione, S1b v2)
    n_finite_gn    = 0      # batch con gn_total_preclip finito
    n_expl_gn      = 0      # batch esplosi: finiti-enormi (>soglia) O inf/nan (S1b v2)
    t0         = time.time()

    for batch_idx, batch in enumerate(loader):
        # R30: 4-tuple loader (x, y, mask, params_gt). Backward-compat: se loader
        # ritorna 3-tuple, params_gt resta None e pinn_loss ignora le lambdas R30.
        if len(batch) == 4:
            x, y, mask, params_gt = batch
            params_gt = params_gt.to(device)
        else:
            x, y, mask = batch
            params_gt = None
        # STEP 2C — cap per budget step. Break PRIMA di altre operazioni: il
        # contatore n_batches conta solo step effettivamente eseguiti.
        if max_steps_per_epoch > 0 and batch_idx >= max_steps_per_epoch:
            break
        x    = x.to(device)
        y    = y.to(device)
        mask = mask.to(device)

        optimizer.zero_grad()
        # R25: pinn_loss ritorna anche params_seq con retain_grad → leggibile post backward
        loss, comps, sr, params_seq = pinn_loss(
            model, x, y, mask, *lam, params_gt=params_gt, retain_params_grad=True)

        # ── Guardia NaN loss ──────────────────────────────────────
        if not loss.isfinite():
            tag = f"  [NaN-Guard E{epoch:02d} B{batch_idx+1:04d}]"
            print(f"{tag} loss={loss.item()} — skip backward")
            _log_batch_diagnostics(tag, comps, float('nan'), x, None, model)
            # T: batch_logger anche su NaN loss — la riga ha is_nan_loss=1 e gn_*=NaN
            if batch_logger is not None:
                batch_logger.log(_make_batch_row(
                    epoch, batch_idx + 1, comps, sr, None,
                    float('nan'), float('nan'),
                    model, optimizer, is_nan_loss=True, is_inf_grad=False))
            if step_per_batch and scheduler is not None:
                scheduler.step()
            spike_acc += sr
            n_batches  += 1
            continue

        loss.backward()

        # ── Norme per-layer PRIMA del clip ────────────────────────
        # clip_grad_norm_(total=inf) azzera tutti i grad (coeff = max_norm/inf = 0).
        # Le norme devono essere raccolte ora, altrimenti sono irrecuperabili.
        # Calcola sempre pre_norms prima del clip: overhead trascurabile (6 tensori,
        # 864 parametri totali). Necessario per diagnosticare l'overflow float32:
        # gn=inf può avvenire anche con gradienti finite-ma-enormi (somma quadrati > 3.4e38),
        # caso in cui has_inf_grad=False ma le norme per-layer rivelano il layer esplosivo.
        pre_norms = {
            name: p.grad.detach().norm().item()
            for name, p in model.named_parameters()
            if p.grad is not None
        }

        # R25 — Gradient diagnostics per-canale (15 valori):
        #   Livello 1: gn_out_fc_<param>  = norma del gradient sulla i-esima riga di LI.fc_weight
        #   Livello 2: gn_decoded_<param> = mean|d(loss)/d(params_seq[:,:,i])|
        #   Livello 3: grad_dir_<param>   = sign(d(loss)/d(params_seq[:,:,i])).mean()
        # Catturato via params_seq.retain_grad() + .grad. Costo trascurabile.
        grad_extras = {}
        _PARAM_NAMES = ('v0', 'T', 's0', 'a', 'b')
        # Livello 1: split di gn_out_fc per canale
        li = model.layer_out
        li_w = getattr(li, 'fc_weight', None)
        if li_w is None:
            li_w = getattr(li, 'weight', None)
        if li_w is not None and li_w.grad is not None:
            for i, pn in enumerate(_PARAM_NAMES):
                grad_extras[f'gn_out_fc_{pn}'] = li_w.grad[i].detach().norm().item()
        # Livello 2+3: dal gradient su params_seq (post-decode)
        if params_seq.grad is not None:
            pg = params_seq.grad.detach()  # (batch, T, 5)
            for i, pn in enumerate(_PARAM_NAMES):
                g_i = pg[:, :, i]
                grad_extras[f'gn_decoded_{pn}'] = g_i.abs().mean().item()
                grad_extras[f'grad_dir_{pn}']  = g_i.sign().mean().item()

        # T: gn_total_preclip ricostruito dalle norme per-layer (somma quadratica).
        # Necessario per il batch_log perché clip_grad_norm_ restituisce il valore
        # PRIMA del clip (gn_val), ma se gn=inf perdiamo la decomposizione.
        # Usando pre_norms otteniamo lo stesso numero ma anche le componenti per-layer.
        gn_total_preclip = math.sqrt(sum(v ** 2 for v in pre_norms.values()
                                         if math.isfinite(v))) \
            if all(math.isfinite(v) for v in pre_norms.values()) else float('inf')

        # R30 (2026-06-12) — tracking max gn_total_preclip nell'epoca per
        # explosion guard a livello epoca. Ignora inf (gestito separatamente
        # da inf_streak).
        n_seen_gn += 1   # tutti i batch (denominatore frazione, S1b v2)
        if math.isfinite(gn_total_preclip):
            n_finite_gn += 1
            if gn_total_preclip > max_gn_preclip:
                max_gn_preclip = gn_total_preclip
            if gn_total_preclip > explosion_threshold:
                n_expl_gn += 1   # esploso finito-enorme
        else:
            n_expl_gn += 1   # S1b v2 FIX: inf/nan = esploso (cattura il fallimento "opposto"
            #                  dove x8/x10 giravano 50ep su gradienti inf non contati)

        # AGC (opt-in): clip per-unita relativo a ||w|| PRIMA del clip globale. Optimizer-agnostico
        # -> mantiene Prodigy. gn_total_preclip sopra resta grezzo (failsafe del guard intatto).
        if grad_clip_mode == 'agc':
            adaptive_grad_clip(model, agc_lambda)

        gn     = nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        gn_val = float(gn)

        # ── Guardia NaN gradiente ─────────────────────────────────
        if not math.isfinite(gn_val):
            inf_streak += 1
            tag = f"  [NaN-Grad E{epoch:02d} B{batch_idx+1:04d}]"
            print(f"{tag} grad_norm=inf  streak={inf_streak}/{max_inf_streak}")
            _log_batch_diagnostics(tag, comps, gn_val, x, pre_norms, model)
            # T: batch_logger anche su inf grad — riga con is_inf_grad=1 e per-layer norms
            if batch_logger is not None:
                # gn_postclip è 0 perché clip_grad_norm_ ha azzerato tutti i grad
                # (coeff = max_norm/inf = 0). Lo riportiamo come 0.0 (osservato),
                # non NaN.
                batch_logger.log(_make_batch_row(
                    epoch, batch_idx + 1, comps, sr, pre_norms,
                    gn_total_preclip, 0.0,
                    model, optimizer, is_nan_loss=False, is_inf_grad=True))
            optimizer.zero_grad()
            if step_per_batch and scheduler is not None:
                scheduler.step()
            spike_acc += sr
            n_batches  += 1
            # ── Early stop su esplosione persistente ──────────────
            if inf_streak >= max_inf_streak:
                print(f"\n  [EARLY-STOP] {max_inf_streak} batch consecutivi con"
                      f" grad=inf — training abortito (epoca {epoch},"
                      f" LR={optimizer.param_groups[0]['lr']:.3e})\n")
                nb   = max(n_batches, 1)
                avgs = {k: v / nb for k, v in totals.items()}
                avgs['spike_rate'] = spike_acc / nb
                avgs['grad_norm']  = float('inf')
                avgs['max_gn_preclip'] = max_gn_preclip
                avgs['explosion_frac'] = n_expl_gn / max(n_seen_gn, 1)
                avgs['aborted']    = True
                return avgs
            continue

        # Batch OK: azzera streak
        inf_streak = 0

        # Diagnostica su grad alto ma finito (solo se diag=True)
        if diag and gn_val > GRAD_WARN_THRESHOLD:
            tag = f"  [GRAD-WARN E{epoch:02d} B{batch_idx+1:04d}]"
            print(f"{tag} grad_norm={gn_val:.3e} (>{GRAD_WARN_THRESHOLD})")
            _log_batch_diagnostics(tag, comps, gn_val, x, pre_norms, model)

        optimizer.step()

        # Per-batch scheduler step (OneCycleLR)
        if step_per_batch and scheduler is not None:
            scheduler.step()

        for k in totals:
            totals[k] += comps[k]
        spike_acc += sr
        grad_acc  += gn_val
        n_batches  += 1

        # T: batch_logger sul path normale — riga completa con tutti i campi finiti
        if batch_logger is not None:
            batch_logger.log(_make_batch_row(
                epoch, batch_idx + 1, comps, sr, pre_norms,
                gn_total_preclip, gn_val,
                model, optimizer, is_nan_loss=False, is_inf_grad=False,
                grad_extras=grad_extras))

        if (batch_idx + 1) % log_every == 0:
            elapsed = time.time() - t0
            avg     = totals['total'] / n_batches
            print(f"  [E{epoch:02d} | B{batch_idx+1:04d}/{len(loader):04d}]"
                  f"  loss={avg:.4f}"
                  f"  data={totals['data']/n_batches:.4f}"
                  f"  phys={totals['phys']/n_batches:.5f}"
                  f"  ou={totals['ou']/n_batches:.6f}"
                  f"  spike={spike_acc/n_batches*100:.1f}%"
                  f"  gn={gn_val:.3e}"
                  f"  ({elapsed:.1f}s)")

    nb   = max(n_batches, 1)
    avgs = {k: v / nb for k, v in totals.items()}
    avgs['spike_rate'] = spike_acc / nb
    avgs['grad_norm']  = grad_acc  / nb
    avgs['max_gn_preclip'] = max_gn_preclip   # R30: per explosion guard epoch-level
    avgs['explosion_frac'] = n_expl_gn / max(n_seen_gn, 1)  # S1b: frazione batch esplosi
    avgs['aborted']    = False
    return avgs


@torch.no_grad()
def val_epoch(model, loader, device, lam):
    model.eval()
    totals    = {'total': 0.0, 'data': 0.0, 'phys': 0.0, 'ou': 0.0, 'bc': 0.0, 'sr': 0.0}
    spike_acc = 0.0
    n_batches = 0

    # R25 — accumulatori per metriche per-canale (5 IDM params)
    _PARAM_NAMES = ('v0', 'T', 's0', 'a', 'b')
    # Per T tracking corr serve aggregare T_pred e T_true su tutti i batch (poi corr unica)
    T_pred_all, T_true_all = [], []
    # Per altri canali: per-channel mean predicted (per saturation) + intra-seq std
    chan_pred_mean = {pn: [] for pn in _PARAM_NAMES}
    chan_intra_std = {pn: [] for pn in _PARAM_NAMES}
    # Lente B (Loss_Study) — accumulatori per NRMSE per-canale vs GT.
    # T: GT per-timestep in y[:,:,1] (masked). v0/s0/a/b: GT costante in params_gt.
    _NR_GT_IDX = {'v0': 0, 's0': 1, 'a': 2, 'b': 3}   # colonna in params_gt (T escluso)
    nrmse_se = {pn: 0.0 for pn in _PARAM_NAMES}
    nrmse_n  = {pn: 0   for pn in _PARAM_NAMES}

    for batch in loader:
        # R30: 4-tuple loader (x, y, mask, params_gt). Backward-compat su 3-tuple.
        if len(batch) == 4:
            x, y, mask, params_gt = batch
            params_gt = params_gt.to(device)
        else:
            x, y, mask = batch
            params_gt = None
        x    = x.to(device)
        y    = y.to(device)
        mask = mask.to(device)
        _, comps, sr, params_seq = pinn_loss(model, x, y, mask, *lam, params_gt=params_gt)
        # F2: salta batch degeneri — NaN si propaga in tutti i totals silenziosamente
        if not math.isfinite(comps['total']):
            continue
        for k in totals:
            totals[k] += comps[k]
        spike_acc += sr
        n_batches  += 1

        # R25 — accumula metriche per-canale (no grad needed, già no_grad context)
        # R27 — mantieni shape (batch, T) per consentire T_intra_corr (mean-removed
        # per-sample Pearson). Il flatten viene fatto a fine epoca.
        ps = params_seq.detach()                        # (batch, T, 5)
        T_pred_all.append(ps[:, :, 1])                  # (batch, T)
        T_true_all.append(y[:, :, 1])                   # (batch, T)
        for i, pn in enumerate(_PARAM_NAMES):
            chan_pred_mean[pn].append(ps[:, :, i].mean().item())
            chan_intra_std[pn].append(ps[:, :, i].std(dim=1).mean().item())

        # Lente B — somma errori quadratici vs GT (T: per-timestep masked; v0/s0/a/b: costante)
        nrmse_se['T'] += (mask * (ps[:, :, 1] - y[:, :, 1]) ** 2).sum().item()
        nrmse_n['T']  += mask.sum().item()
        if params_gt is not None:
            for pn, gi in _NR_GT_IDX.items():
                pi = _PARAM_NAMES.index(pn)              # idx canale in params_seq
                gt = params_gt[:, gi].unsqueeze(1)       # (batch, 1) costante per scenario
                nrmse_se[pn] += ((ps[:, :, pi] - gt) ** 2).sum().item()
                nrmse_n[pn]  += ps[:, :, pi].numel()

    nb = max(n_batches, 1)
    avgs = {k: v / nb for k, v in totals.items()}
    avgs['spike_rate'] = spike_acc / nb

    # R25 — Pearson corr(T_pred, T_true) sui campioni val masked-out (no nan se var=0)
    # R27 — aggiunto val_T_intra_corr: Pearson DOPO rimozione media per-sample.
    #   val_T_tracking_corr = corr(T_pred, T_true) flat = CROSS-DRIVER + INTRA-DRIVER mixed
    #   val_T_intra_corr    = corr(T_pred - T̄_pred_per_seq, T_true - T̄_true_per_seq)
    #                       = solo dinamica intra-driver (cross-driver rimosso).
    # Disambigua se la rete impara dinamiche T(t) o solo media-cross-sample.
    if T_pred_all:
        Tp_seq = torch.cat(T_pred_all, dim=0)           # (N_samples, T)
        Tt_seq = torch.cat(T_true_all, dim=0)           # (N_samples, T)
        Tp = Tp_seq.reshape(-1)
        Tt = Tt_seq.reshape(-1)
        # 1) Tracking corr (storica R25, flat cross+intra)
        if Tp.std() > 1e-8 and Tt.std() > 1e-8:
            avgs['val_T_tracking_corr'] = float(((Tp - Tp.mean()) * (Tt - Tt.mean())).mean()
                                                / (Tp.std() * Tt.std() + 1e-8))
        else:
            avgs['val_T_tracking_corr'] = 0.0
        # 2) Intra corr (R27, mean-removed per-sample → dinamica vera)
        Tp_ctr = Tp_seq - Tp_seq.mean(dim=1, keepdim=True)
        Tt_ctr = Tt_seq - Tt_seq.mean(dim=1, keepdim=True)
        Tp_ctr_flat = Tp_ctr.reshape(-1)
        Tt_ctr_flat = Tt_ctr.reshape(-1)
        if Tp_ctr_flat.std() > 1e-8 and Tt_ctr_flat.std() > 1e-8:
            avgs['val_T_intra_corr'] = float(
                ((Tp_ctr_flat - Tp_ctr_flat.mean()) * (Tt_ctr_flat - Tt_ctr_flat.mean())).mean()
                / (Tp_ctr_flat.std() * Tt_ctr_flat.std() + 1e-8))
        else:
            avgs['val_T_intra_corr'] = 0.0
    else:
        avgs['val_T_tracking_corr'] = float('nan')
        avgs['val_T_intra_corr']    = float('nan')
    # Per-channel pred mean + intra-seq std (5 ognuno = 10 metriche)
    for pn in _PARAM_NAMES:
        avgs[f'val_{pn}_pred_mean'] = float(np.mean(chan_pred_mean[pn])) if chan_pred_mean[pn] else float('nan')
        avgs[f'val_{pn}_intra_std'] = float(np.mean(chan_intra_std[pn])) if chan_intra_std[pn] else float('nan')

    # Lente B (Loss_Study) — NRMSE per-canale = RMSE / range_param. Normalizzare per il
    # range rende confrontabili canali su scale diverse (v0~37 vs T~2). Guard hasattr per
    # non rompere training method con modelli privi di param_hi/lo (es. EventProp variants).
    if hasattr(model, 'param_hi') and hasattr(model, 'param_lo'):
        _rng = (model.param_hi - model.param_lo).detach().cpu()
        for i, pn in enumerate(_PARAM_NAMES):
            if nrmse_n[pn] > 0:
                _rmse = math.sqrt(nrmse_se[pn] / nrmse_n[pn])
                avgs[f'val_{pn}_nrmse'] = float(_rmse / (_rng[i].item() + 1e-12))
            else:
                avgs[f'val_{pn}_nrmse'] = float('nan')
    else:
        for pn in _PARAM_NAMES:
            avgs[f'val_{pn}_nrmse'] = float('nan')

    return avgs


# ===========================================================
# Checkpoint e logging
# ===========================================================

def save_checkpoint(model, optimizer, epoch, val_loss, path):
    # Crea la directory solo se il path ha una componente directory
    dir_part = os.path.dirname(path)
    if dir_part:
        os.makedirs(dir_part, exist_ok=True)
    torch.save({
        'epoch'      : epoch,
        'val_loss'   : val_loss,
        'model_state': model.state_dict(),
        'optim_state': optimizer.state_dict(),
    }, path)


def load_checkpoint(model, optimizer, path, device):
    # weights_only=False: il checkpoint contiene anche optimizer state (dict PyTorch)
    ckpt = torch.load(path, map_location=device, weights_only=False)
    model.load_state_dict(ckpt['model_state'])
    optimizer.load_state_dict(ckpt['optim_state'])
    return ckpt['epoch'], ckpt['val_loss']


class CSVLogger:
    """Scrive training_log.csv riga per riga (flush ad ogni epoca)."""

    COLS = [
        'epoch',
        'train_total', 'train_data', 'train_phys', 'train_ou', 'train_bc', 'train_sr',
        'val_total',   'val_data',   'val_phys',   'val_ou',   'val_bc',   'val_sr',
        'lr', 'grad_norm', 'spike_rate', 'time_s',
        # Prodigy: d e' l'adaptive scalar; lr_eff = lr * d e' la "vera" LR (NaN per
        # altri optimizer). Aggiunto 2026-06-01 per visibility schedule Prodigy.
        'prodigy_d', 'prodigy_d_max', 'prodigy_lr_eff',
        # R25 — metriche per-canale val (11 colonne):
        #   1 corr(T_pred, T_true) — solo T (unico canale con GT per-timestep)
        #   5 pred_mean per canale → permette tracking saturazione bound
        #   5 intra_seq std per canale → distingue "varia intra-driver" vs "media globale"
        'val_T_tracking_corr',
        # R27 — intra-driver Pearson (per-sample mean-removed). Disambigua cross vs intra.
        'val_T_intra_corr',
        'val_v0_pred_mean', 'val_T_pred_mean', 'val_s0_pred_mean', 'val_a_pred_mean', 'val_b_pred_mean',
        'val_v0_intra_std', 'val_T_intra_std', 'val_s0_intra_std', 'val_a_intra_std', 'val_b_intra_std',
        # Lente B (Loss_Study) — NRMSE per-canale (RMSE/range): residuo normalizzato confrontabile
        'val_v0_nrmse', 'val_T_nrmse', 'val_s0_nrmse', 'val_a_nrmse', 'val_b_nrmse',
    ]

    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._f = open(path, 'w', newline='', encoding='utf-8')
        self._w = csv.DictWriter(self._f, fieldnames=self.COLS)
        self._w.writeheader()
        self._f.flush()

    def log(self, row: dict):
        self._w.writerow({c: row.get(c, float('nan')) for c in self.COLS})
        self._f.flush()

    def close(self):
        self._f.close()


class BatchCSVLogger:
    """T (telemetria estesa) — scrive training_batch_log.csv riga per riga.

    Differenza con CSVLogger: scrive una riga per BATCH (non per epoca) e flusha ogni
    `flush_every` righe per non killare le perfo I/O. Append-only: anche su crash i
    dati raccolti fino a quel punto restano disponibili.

    Costo: ~16 float/batch ≈ 128 byte; su 1485 batch ≈ 190 KB totali.
    Flush ogni 50 batch ≈ 1 ms. Overhead trascurabile (<1%).

    I dati per le colonne `gn_*` per-layer arrivano dal dict `pre_norms` che è già
    calcolato ad ogni batch da train_epoch (richiesto dalla diagnostica esistente).
    """

    COLS = [
        'epoch', 'batch_idx',
        # Loss components (incl. B5 spike-rate regularizer + R25 T-aux)
        'loss_total', 'loss_data', 'loss_phys', 'loss_ou', 'loss_bc', 'loss_sr',
        'loss_T_aux',
        # Attività spiking
        'spike_rate',
        # Gradient norms
        'gn_total_preclip', 'gn_total_postclip',
        # Per-layer (pre-clip) — chiave per identificare quale layer esplode
        'gn_hidden_fc', 'gn_hidden_recU', 'gn_hidden_recV',
        'gn_hidden_base_threshold', 'gn_hidden_thresh_jump',
        'gn_out_fc',
        # Weight stats
        'weight_max_abs_global',
        # Optimizer
        'lr',
        # Prodigy adapter (NaN per altri ottimizzatori — STEP 2C-ter)
        'prodigy_d', 'prodigy_d_max', 'prodigy_lr_eff',
        # Diagnostic flags
        'is_nan_loss', 'is_inf_grad',
        # R25 — Gradient diagnostics per-canale (15 colonne):
        #   gn_out_fc_<p>  = norma del gradient sulla riga i-esima di LI.fc_weight (LIVELLO 1, RAW)
        #   gn_decoded_<p> = mean|d(loss)/d(params_seq[:,:,i])|  (LIVELLO 2, POST-SIGMOID)
        #   grad_dir_<p>   = sign(d(loss)/d(params_seq[:,:,i])).mean() (LIVELLO 3, DIREZIONE)
        'gn_out_fc_v0', 'gn_out_fc_T', 'gn_out_fc_s0', 'gn_out_fc_a', 'gn_out_fc_b',
        'gn_decoded_v0', 'gn_decoded_T', 'gn_decoded_s0', 'gn_decoded_a', 'gn_decoded_b',
        'grad_dir_v0', 'grad_dir_T', 'grad_dir_s0', 'grad_dir_a', 'grad_dir_b',
    ]

    # Mapping da parametro PyTorch → colonna CSV (parametri non listati → ignorati)
    # STEP 2E: per le varianti architetturali, i nuovi nomi (es. layers_hidden.0.fc_weight,
    # skip_weight, Wq, ...) non sono in questa mappa. Il logger li skippa silenziosamente
    # e registra un warning una sola volta (vedi _make_batch_row). Pattern KISS: niente
    # NaN silenzioso nel CSV, niente crash, ma il diagnostic gradient è limitato ai
    # parametri baseline. Le varianti potranno aggiungere mapping qui se serve.
    LAYER_MAP = {
        # ── Baseline (CF_FSNN_Net, ALIF + surrogate) ──
        'layer_hidden.fc_weight':           'gn_hidden_fc',
        'layer_hidden.rec_U':               'gn_hidden_recU',
        'layer_hidden.rec_V':               'gn_hidden_recV',
        'layer_hidden.cell.base_threshold': 'gn_hidden_base_threshold',
        'layer_hidden.cell.thresh_jump':    'gn_hidden_thresh_jump',
        'layer_out.fc_weight':              'gn_out_fc',
        # ── EventProp F2.0b (LIFLayer_EventProp, LIF simple ref) ──
        # I layer hanno nn.Parameter 'weight' diretto (no .fc_weight).
        'layer_hidden.weight':              'gn_hidden_fc',
        'layer_out.weight':                 'gn_out_fc',
        # ── EventProp F2.1-full (ALIFLayer_EventProp_Full) ──
        # fc_weight, rec_U, rec_V hanno STESSI nomi del baseline (riusano entry sopra).
        # base_threshold, thresh_jump invece sono diretti sul layer (no .cell.)
        # perche' ALIFLayer_EventProp_Full e' un layer monolitico (no cell separata).
        'layer_hidden.base_threshold':      'gn_hidden_base_threshold',
        'layer_hidden.thresh_jump':         'gn_hidden_thresh_jump',
    }
    # Set per loggare il warning UNA SOLA VOLTA per nome param non mappato.
    _UNMAPPED_WARNED = set()

    def __init__(self, path: str, flush_every: int = 50):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._f = open(path, 'w', newline='', encoding='utf-8')
        self._w = csv.DictWriter(self._f, fieldnames=self.COLS)
        self._w.writeheader()
        self._f.flush()
        self._flush_every = flush_every
        self._rows_since_flush = 0

    def log(self, row: dict):
        self._w.writerow({c: row.get(c, float('nan')) for c in self.COLS})
        self._rows_since_flush += 1
        if self._rows_since_flush >= self._flush_every:
            self._f.flush()
            self._rows_since_flush = 0

    def close(self):
        self._f.flush()
        self._f.close()


def _make_batch_row(epoch, batch_idx, comps, sr, pre_norms,
                    gn_total_preclip, gn_total_postclip,
                    model, optimizer, is_nan_loss=False, is_inf_grad=False,
                    grad_extras=None):
    """Costruisce il dict-riga per BatchCSVLogger. Helper riusato dai 3 path di
    train_epoch (batch normale, NaN loss, inf grad)."""
    row = {
        'epoch':             epoch,
        'batch_idx':         batch_idx,
        'loss_total':        comps.get('total', float('nan')),
        'loss_data':         comps.get('data',  float('nan')),
        'loss_phys':         comps.get('phys',  float('nan')),
        'loss_ou':           comps.get('ou',    float('nan')),
        'loss_bc':           comps.get('bc',    float('nan')),
        'loss_sr':           comps.get('sr',    float('nan')),
        'spike_rate':        sr,
        'gn_total_preclip':  gn_total_preclip,
        'gn_total_postclip': gn_total_postclip,
        'weight_max_abs_global': max(
            (p.detach().abs().max().item() for p in model.parameters()), default=0.0),
        'lr':                optimizer.param_groups[0]['lr'],
        # STEP 2C-ter: Prodigy esporta `d` (adapter) e `d_max` (max storico).
        # Per altri ottimizzatori la chiave manca → NaN (gestito da BatchCSVLogger.log).
        # lr_eff = lr × d è la "vera" learning rate di Prodigy.
        'prodigy_d':         optimizer.param_groups[0].get('d', float('nan')),
        'prodigy_d_max':     optimizer.param_groups[0].get('d_max', float('nan')),
        'prodigy_lr_eff':    (optimizer.param_groups[0]['lr']
                              * optimizer.param_groups[0].get('d', float('nan'))),
        'is_nan_loss':       int(is_nan_loss),
        'is_inf_grad':       int(is_inf_grad),
        # R25: include loss_T_aux (NaN se non logged)
        'loss_T_aux':        comps.get('T_aux', float('nan')),
    }
    # R25: merge grad_extras (15 colonne per-canale gradient diagnostics).
    # Se grad_extras None (path NaN/inf grad o val_epoch), tutte → NaN via .get nel logger.
    if grad_extras is not None:
        row.update(grad_extras)
    # Mappa pre_norms ai nomi colonna. STEP 2E: warn-once per param non mappato.
    if pre_norms is not None:
        # R27 FIX: LAYER_MAP contiene piu' pname che mappano alla stessa cname
        # (es. 'layer_hidden.fc_weight' baseline + 'layer_hidden.weight' EventProp →
        # entrambi → 'gn_hidden_fc'). Iterare e assegnare incondizionatamente
        # sovrascriveva il valore baseline con NaN (perche' la pname EventProp non
        # esiste in pre_norms del modello baseline). Fix: "first hit wins" — assegna
        # solo se la pname e' realmente presente in pre_norms E la cname non e' gia'
        # stata scritta. Inizializza poi a NaN tutte le cname non risolte.
        for pname, cname in BatchCSVLogger.LAYER_MAP.items():
            if pname in pre_norms and cname not in row:
                row[cname] = pre_norms[pname]
        for cname in {'gn_hidden_fc', 'gn_hidden_recU', 'gn_hidden_recV',
                      'gn_hidden_base_threshold', 'gn_hidden_thresh_jump', 'gn_out_fc'}:
            row.setdefault(cname, float('nan'))
        # Warning silenzioso una volta per nome non mappato (varianti A2-A8).
        mapped = set(BatchCSVLogger.LAYER_MAP.keys())
        for pname in pre_norms.keys():
            if pname not in mapped and pname not in BatchCSVLogger._UNMAPPED_WARNED:
                BatchCSVLogger._UNMAPPED_WARNED.add(pname)
                print(f"[BatchCSVLogger] WARN: param '{pname}' non in LAYER_MAP "
                      f"-- gradient norm non loggato (variante architetturale)")
    return row


# ===========================================================
# Main
# ===========================================================

def main():
    parser = argparse.ArgumentParser(
        description='CF_FSNN Training — PINN + ACC-IDM (IIDM base) + V2X'
    )
    # Durata e dimensioni
    parser.add_argument('--epochs',      type=int,   default=EPOCHS)
    parser.add_argument('--batch_size',  type=int,   default=BATCH_SIZE)
    parser.add_argument('--lr',          type=float, default=LEARNING_RATE)
    parser.add_argument('--seq_len',     type=int,   default=100,
                        help='Passi per finestra TBPTT')
    # Scheduler
    parser.add_argument('--scheduler',   type=str,   default='plateau',
                        choices=['plateau', 'onecycle', 'cosine', 'cosine_no_restart', 'custom_restart', 'none'],
                        help='Scheduler LR: plateau|onecycle|cosine|cosine_no_restart|custom_restart|none '
                             '(none = nessun adjustment, per ottimizzatori auto-adattivi '
                             'come Prodigy)')
    # R32 (2026-06-15) — Custom restart scheduler con decay + 2-tier + adaptive + warmup.
    # Discovery R31: cosine warm restart standard (T0=15) produce peak T_intra ma poi
    # esplode al 2° restart (lr salta 90× istantaneo). I 5 meccanismi sotto regolano
    # questo restart in modo piu' soft.
    parser.add_argument('--restart_T0', type=int, default=12,
                        help='R32/R33: periodo di restart in epoche per scheduler=custom_restart. '
                             'Default 12 (R33): per epochs=50 dà 4 cicli pieni che chiudono '
                             'esattamente a ep48, evitando il ciclo monco T0=15→ep45→5 ep '
                             'troncati che spreca un restart. Solo se restart_adaptive=0.')
    parser.add_argument('--restart_decay', type=float, default=1.0,
                        help='R32 Opzione 1: decay geometrico per max_lr ad ogni restart. '
                             '1.0 = no decay (Opzione 0 standard). 0.3 = max_lr × 0.3 ogni ciclo.')
    parser.add_argument('--restart_lr_after', type=float, default=-1.0,
                        help='R32 Opzione 2: lr_max fisso dal primo restart in poi. '
                             '-1 (default) = usa restart_decay. >0 (es 0.15) = override per Opzione 2.')
    parser.add_argument('--restart_warmup_epochs', type=int, default=0,
                        help='R32 Opzione 4: epoche di ramp-up lineare DOPO ogni restart. '
                             '0 = no warmup (restart violento). Es 2 = lr cresce '
                             'da max_lr/2 a max_lr nelle prime 2 epoche post-restart.')
    parser.add_argument('--restart_adaptive', type=int, default=0, choices=[0, 1],
                        help='R32 Opzione 3: trigger restart quando val_T_intra_corr '
                             'degrada per 2 epoche consecutive (sovrascrive T0 fisso). '
                             '0 (default) = OFF, 1 = adaptive.')
    parser.add_argument('--max_lr',      type=float, default=5e-3,
                        help='LR massimo per OneCycleLR')
    parser.add_argument('--T0',          type=int,   default=5,
                        help='Periodo per CosineAnnealingWarmRestarts')
    # Pesi PINN loss
    parser.add_argument('--lambda_data', type=float, default=LAMBDA_DATA)
    parser.add_argument('--lambda_phys', type=float, default=LAMBDA_PHYS)
    parser.add_argument('--lambda_ou',   type=float, default=LAMBDA_OU)
    parser.add_argument('--lambda_bc',   type=float, default=LAMBDA_BC)
    parser.add_argument('--lambda_sr',   type=float, default=LAMBDA_SR,
                        help='B5: peso spike-rate regularizer (default da config.py)')
    parser.add_argument('--lambda_T_aux', type=float, default=0.0,
                        help='R25: peso supervisione diretta su T. Aggiunge L_T_aux = '
                             'masked MSE(params_seq[:,:,1], y_seq[:,:,1]) alla loss totale. '
                             'Default 0.0 = backward-compatibile (no aux loss). >0 forza la '
                             'rete a tracciare T dinamico per-timestep.')
    # R30 ID-1 (2026-06-12): supervisione esplicita su v0/s0/a/b (costanti per scenario)
    # GT esposto via dataset CFDataset 4-tuple. Default 0 = backward-compat.
    parser.add_argument('--lambda_v0_aux', type=float, default=0.0,
                        help='R30 ID-1: peso supervisione v0 (cost per scenario). 0 = off.')
    parser.add_argument('--lambda_s0_aux', type=float, default=0.0,
                        help='R30 ID-1: peso supervisione s0 (cost per scenario). 0 = off.')
    parser.add_argument('--lambda_a_aux',  type=float, default=0.0,
                        help='R30 ID-1: peso supervisione a (cost per scenario). 0 = off.')
    parser.add_argument('--lambda_b_aux',  type=float, default=0.0,
                        help='R30 ID-1: peso supervisione b (cost per scenario). 0 = off.')
    # L2 (Dynamic_Study): reparam [a,b] -> (geo-mean, log-ratio) + per-regime weighting.
    # Vincola ESPLICITAMENTE la direzione molle log(a/b) (b anti-correlato in L1d). Default 0 = off.
    parser.add_argument('--cf_extra_channels', type=int, default=0, choices=[0, 1],
                        help='L3 #2 (encoding): 1 = aggiunge 3 canali derivata [ṡ,accel,Δv\'] '
                             'all input (4->7) per dare la firma del transitorio. 0 = off (default).')
    parser.add_argument('--lambda_geo_aux', type=float, default=0.0,
                        help='L2: peso supervisione geo-mean log√(ab) (magnitudine a/b). 0 = off.')
    parser.add_argument('--lambda_ratio_aux', type=float, default=0.0,
                        help='L2: peso supervisione log-ratio log(a/b) (direzione molle). 0 = off.')
    parser.add_argument('--regime_gamma', type=float, default=0.0,
                        help='L2: amplifica il peso di geo/ratio aux sui transitori '
                             '(|v_dot_gt|>regime_thr) di un fattore (1+gamma). 0 = uniforme.')
    parser.add_argument('--regime_thr', type=float, default=0.5,
                        help='L2: soglia |v_dot| [m/s^2] che definisce un transitorio (per regime_gamma).')
    # L3 #5 (uncertainty head): output 5->10 (medie+log-var) + NLL eteroschedastica.
    parser.add_argument('--uncertainty_head', type=int, default=0, choices=[0, 1],
                        help='L3 #5: 1 = output 5->10 (5 medie + 5 log-var), la rete dichiara '
                             'la confidenza per-parametro. Richiede --lambda_nll>0. 0 = off (default).')
    parser.add_argument('--lambda_nll', type=float, default=0.0,
                        help='L3 #5: peso della NLL gaussiana eteroschedastica su v0,s0,a,b. 0 = off.')
    # Ottimizzatore
    parser.add_argument('--optimizer',   type=str,   default='adam',
                        choices=['adam', 'adamw', 'lion', 'prodigy'],
                        help='Ottimizzatore: adam|adamw|lion|prodigy '
                             '(prodigy: LR-free, usa --lr 1.0 come stima iniziale)')
    parser.add_argument('--prodigy_d_coef', type=float, default=1.0,
                        help='Prodigy d_coef: controlla velocita crescita parametro adattivo d. '
                             'Default 1.0 (Prodigy standard). <1.0 = piu cauto (utile se grad '
                             'esplodono), >1.0 = piu aggressivo. Solo per --optimizer prodigy.')
    parser.add_argument('--prodigy_safeguard_warmup', type=int, default=1, choices=[0, 1],
                        help='Prodigy safeguard_warmup: 1=ON (default, rimuove lr dal denominatore '
                             'di d_hat per evitare early-step blowup), 0=OFF (canonical paper '
                             'setting, puo causare frozen d con pochi step). Solo --optimizer prodigy.')
    parser.add_argument('--prodigy_growth_rate', type=float, default=float('inf'),
                        help='Prodigy growth_rate: cap moltiplicativo per-step su d (default inf = '
                             'no cap). Valore 1.02 da "natural warmup" smooth, raccomandato per '
                             'training instabile. Solo --optimizer prodigy.')
    # R2: parametri Prodigy aggiuntivi esposti per lo studio deep
    parser.add_argument('--prodigy_betas', type=str, default='0.9,0.999',
                        help='Prodigy betas come "b1,b2" (default "0.9,0.999"). Community wisdom '
                             '(Issue #8 madman404): "0.9,0.99" produce "dramatic improvement" '
                             'perche\' beta3=beta2**0.5 controlla decay del d_numerator. Solo --optimizer prodigy.')
    parser.add_argument('--prodigy_use_bias_correction', type=int, default=0, choices=[0, 1],
                        help='Prodigy use_bias_correction: 0=OFF (default Prodigy lib), 1=ON '
                             '(raccomandato canonical kohya, applica bias correction Adam-style '
                             'al dlr per boost early steps). Solo --optimizer prodigy.')
    parser.add_argument('--prodigy_d0', type=float, default=1e-6,
                        help='Prodigy d0: stima iniziale di D (default 1e-6, lib default). '
                             'Issue #27 LoganBooker/konstmish: "If d rises very slowly, bump up '
                             'd0 to 1e-5 or 1e-4". Aumentare se d resta frozen. Solo --optimizer prodigy.')
    parser.add_argument('--prodigy_weight_decay', type=float, default=-1.0,
                        help='Prodigy weight_decay: se -1 usa default hardcoded (1e-4 storico). '
                             'Community/konstmish raccomanda 0.01 (AdamW-style). Solo --optimizer prodigy.')
    # Dataset
    parser.add_argument('--load_data',   type=str,   default=None,
                        help='Cartella con train.pkl / val.pkl (legacy, usa --data_cache)')
    parser.add_argument('--data_cache',  type=str,   default=None,
                        help='File .pt cache dataset: carica se esiste, genera e salva se no. '
                             'Es: --data_cache data/cache_1500.pt')
    parser.add_argument('--n_train',     type=int,   default=N_SCENARIOS_TRAIN)
    parser.add_argument('--n_val',       type=int,   default=N_SCENARIOS_VAL)
    # DataLoader
    parser.add_argument('--num_workers', type=int,   default=-1,
                        help='Worker DataLoader (-1=auto, 0=disabilita, Colab usa 0)')
    # Diagnostica e robustezza
    parser.add_argument('--smoke',          action='store_true',
                        help='Smoke diagnostico: n_train≤100, 1 epoca, log ogni batch, '
                             'norme per-layer, max_inf_streak=5')
    parser.add_argument('--max_inf_streak', type=int,   default=20,
                        help='Batch consecutivi con grad=inf prima di abortire (default=20)')
    parser.add_argument('--log_every',      type=int,   default=LOG_EVERY,
                        help='Frequenza log batch (default=50; smoke forza 1)')
    # Dataset scenario override (P10 — CLI controllabili da notebook)
    parser.add_argument('--scenario_mix', type=str, default='default',
                        help="Mix scenari: 'default' (config.py) | 'highway' | 'urban' | "
                             "'truck' | 'mixed' | 'highway:0.7,urban:0.3' (custom)")
    parser.add_argument('--cut_in_ratio', type=float, default=None,
                        help='Frazione cut-in [0,1]. Default None usa CUT_IN_RATIO da config.py')
    parser.add_argument('--noise_scale', type=float, default=1.0,
                        help='STEP 2D: scaler ampiezza rumore OU nel generator '
                             '(NOISE_GAP_REL/VEL_OPT/ACCEL). Default 1.0 = nominale. '
                             '0.0 = dataset deterministico ideale (Floor diagnostic). '
                             'Solo se cache assente (cache esistente NON viene rigenerata).')
    parser.add_argument('--po2_enabled', type=int, default=1, choices=[0, 1],
                        help='STEP 2D-bis: toggle Po2 quantization sui pesi (forward). '
                             '1 = legacy ON (default, deploy PYNQ-Z1). '
                             '0 = passthrough fp32 (Floor diagnostic — quantifica peso Po2). '
                             'Set env PO2_ENABLED → letto live dalla forward di '
                             'core.hardware.PowerOf2Quantize ad ogni chiamata.')
    # Early stopping (P11 — evita training oltre il plateau, fix per P8)
    parser.add_argument('--early_stop_patience', type=int, default=0,
                        help='Stop dopo N epoche senza miglioramento di val_loss. '
                             '0 = disabilitato (default). Tipico: 2.')
    parser.add_argument('--early_stop_delta',    type=float, default=1e-4,
                        help='Soglia minima di miglioramento per resettare patience counter')
    # STEP 2B — capacity sweep (None → usa default da config.py)
    # UNIFIED CLI: scegli UNA variante tra 11 totali (8 architecture + 3 training_method).
    # Manteniamo SOLO --training_method come CLI singolo perche' la factory build_model
    # ora unifica le scelte di entrambi i branch in un singolo namespace.
    parser.add_argument('--training_method', type=str, default='baseline',
        choices=['baseline',
                 # Architecture variants (da Architecture_Exploration)
                 'stacked_2', 'stacked_2_skip', 'stacked_3_thin',
                 'max_delay_12', 'multi_rate', 'wta', 'attn',
                 # Training method variants (da Training_Method_Exploration)
                 'bptt_lif_simple', 'eventprop_lif_simple', 'eventprop_alif_full'],
        help='11 varianti totali: '
             'baseline (ALIF+BPTT prod) | stacked_2/skip/3_thin/max_delay_12/'
             'multi_rate/wta/attn (architecture) | bptt_lif_simple/'
             'eventprop_lif_simple/eventprop_alif_full (training method)')
    parser.add_argument('--cf_hidden_size', type=int, default=None,
                        help='Override CF_HIDDEN_SIZE per sweep parametrico (None=default config)')
    parser.add_argument('--cf_rank',        type=int, default=None,
                        help='Override CF_RANK per sweep parametrico (None=default config)')
    parser.add_argument('--cf_max_delay',   type=int, default=None,
                        help='R25 ablation A4: override max_delay sinaptico (None=default config). '
                             'Solo baseline variant — varianti dedicate (max_delay_12, ecc) hanno '
                             'il loro valore hardcoded.')
    parser.add_argument('--cf_bit_shift',   type=int, default=None,
                        help='R25 ablation A5/A6: override bit_shift LIF leak (None=default 3 = '
                             'leak τ ~80ms). Valori comuni: 2 (leak veloce), 3 (default), 5 (leak '
                             'lento ~320ms). Solo baseline variant.')
    # R29 DEC-1 (logit τ annealing) + DEC-3 (init bias shift) — attacca rank-collapse
    parser.add_argument('--cf_init_bias_shift', type=int, default=0, choices=[0, 1],
                        help='R29 DEC-3: 1 = calibra decode_offset PRIMA del training '
                             'usando il primo batch del train_loader. Centra il raw output '
                             'su 0 -> sigmoid(0)=0.5 -> params al midpoint dei bound al t=0. '
                             '0 (default) = backward-compat (no shift).')
    parser.add_argument('--cf_logit_tau_init',  type=float, default=1.0,
                        help='R29 DEC-1: temperatura iniziale sigmoid per _decode_params. '
                             '1.0 (default) = nessuna modifica. >1.0 = sigmoid piu\' piatta '
                             '(zona lineare estesa, evita saturazione iniziale).')
    parser.add_argument('--cf_logit_tau_final', type=float, default=1.0,
                        help='R29 DEC-1: temperatura finale sigmoid (epoch=epochs). '
                             'Annealed lineare/esp dal valore init a quello final.')
    parser.add_argument('--cf_logit_tau_schedule', type=str, default='const',
                        choices=['const', 'linear', 'exp'],
                        help='R29 DEC-1: schedule annealing della temperatura. '
                             'const=resta al cf_logit_tau_init (ignora _final), '
                             'linear=interpolazione lineare init->final, '
                             'exp=interpolazione esponenziale (geometrica) init->final.')
    parser.add_argument('--cf_logit_tau_per_channel', type=str, default=None,
                        help='R29 DEC-1 advanced: 5 valori comma-separated "v0,T,s0,a,b" '
                             'che SOVRASCRIVONO cf_logit_tau_init come vettore per-canale. '
                             'Es: "10,3,10,3,3" = canali v0/s0 saturati ricevono temperatura '
                             'maggiore (sigmoid piu\' piatta) di T/a/b. None (default) = uso '
                             'cf_logit_tau_init scalare per tutti i 5 canali.')
    # R30 (2026-06-12) — Explosion guard a livello EPOCA (oltre al max_inf_streak per-batch).
    # Discovery 2026-06-12: tutti i baseline lr=1.0 da R25 in poi avevano gn_total_preclip
    # 10^5-10^17, mascherati dal clip_grad_norm_(1.0). Servono detection finita-ma-esplosa.
    parser.add_argument('--max_epoch_explosion_streak', type=int, default=-1,
                        help='R30: N epoche consecutive con max(gn_total_preclip) > soglia '
                             '-> abort training. Difesa contro gradient explosion mascherato '
                             'dal clip. -1 (default) = OFF (backward-compat). Raccomandato per '
                             'studi su baselines instabili: 2.')
    parser.add_argument('--epoch_explosion_threshold', type=float, default=10000.0,
                        help='R30/R33: soglia per gn_total_preclip che definisce "esploding" a '
                             'livello epoca. Default 10000.0 (alzato da 100 in R33 dopo R32: '
                             'soglia 100 era troppo sensibile, un singolo batch rumoroso poteva '
                             'forzare streak=1 e 2 epoche rumorose consecutive triggeravano abort '
                             'precoce di run altrimenti recuperabili. R32_A4 peak gn=1.2e13, '
                             'R32_B5 peak gn=5.3e9, R31_A3 peak gn=4.3e3 — 10000 distingue spike '
                             'transienti da divergenza vera). Solo se --max_epoch_explosion_streak > 0.')
    parser.add_argument('--epoch_explosion_frac', type=float, default=0.5,
                        help='S1b (2026-06): frazione minima di batch con gn_preclip>soglia per '
                             'marcare l epoca come esplosa (default 0.5 = meta epoca). Robustifica '
                             'la guard contro spike isolati: con il vecchio criterio (max>soglia) '
                             'bastava 1 batch su 100 ad abortire una run pulita (vedi Loss_Study S1b, '
                             'mediana gn~0.5 ma abort per spike isolato). Solo se streak>0.')
    parser.add_argument('--grad_clip', type=str, default='none', choices=['none', 'agc'],
                        help='S2 (2026-06): clip gradiente EXTRA prima del clip globale. '
                             'none=solo clip_grad_norm(1.0) esistente. agc=Adaptive Gradient '
                             'Clipping (Brock 2021, NFNets): clip per-unita relativo a ||w|| -> '
                             'doma esplosione su reti grandi MANTENENDO l optimizer (Prodigy). '
                             'Esclude layer_out + param 1-D. Default none = backward-compat.')
    parser.add_argument('--agc_lambda', type=float, default=0.01,
                        help='Soglia AGC: rapporto max ||g_unit||/||w_unit|| ammesso. Tipico 0.01 '
                             '(NFNets). Piu alto = meno aggressivo. Solo se --grad_clip agc.')
    # STEP 2C — Optimizer_Exploration: step budget control + val decoupling
    parser.add_argument('--max_steps_per_epoch', type=int, default=-1,
                        help='Cap step training per epoca, indipendente da len(train_loader). '
                             '-1 = unlimited (default). Usato per bound del budget di gradient '
                             'updates quando il windowing genera troppi batch.')
    parser.add_argument('--val_batch_size',      type=int, default=-1,
                        help='Batch size del val_loader, separato dal training. '
                             '-1 = usa --batch_size (default). Utile per batch_size=1 in train '
                             'quando si vuole validation veloce.')
    # Checkpoint
    parser.add_argument('--resume',      type=str,   default=None,
                        help='Checkpoint .pt da cui riprendere')
    parser.add_argument('--tag',         type=str,   default='run',
                        help='Etichetta cartella output (checkpoints/<tag>/)')
    args = parser.parse_args()

    # ── STEP 2D-bis: propaga --po2_enabled all'env var (letto live da core.hardware) ──
    # Set PRIMA di qualsiasi forward del modello. Sub-process Jupyter eredita env
    # già pulito quindi va sempre re-applicato qui (no contaminazione tra run).
    os.environ['PO2_ENABLED'] = str(args.po2_enabled)
    print(f"[Hardware] PO2_ENABLED={os.environ['PO2_ENABLED']}  "
          f"({'quant fp32->Po2 attiva (legacy)' if args.po2_enabled else 'BYPASS, pesi fp32 puri'})")

    # ── Smoke mode: sovrascrive parametri per run diagnostico rapido ──────────
    # Obiettivo: 1 epoca su ~100 traiettorie con log ogni singolo batch e
    # norme per-layer su ogni anomalia. Dura ~1-2 min su CPU, ~20s su GPU.
    if args.smoke:
        args.n_train        = min(args.n_train, 100)
        args.n_val          = min(args.n_val,   30)
        args.epochs         = 1
        args.log_every      = 1
        args.max_inf_streak = 5
        print("[SMOKE] Modalita diagnostica:"
              f" n_train<={args.n_train}, n_val<={args.n_val},"
              " 1 epoca, LOG_EVERY=1, max_inf_streak=5, norme per-layer attive")

    set_seed(SEED)
    device   = DEVICE
    # cudnn.benchmark: ottimizza i kernel CUDA per le dimensioni fisse dei batch
    # (utile su GPU come T4/V100 con modelli piccoli e batch costanti)
    if device.type == 'cuda':
        torch.backends.cudnn.benchmark = True
    # Percorso assoluto: checkpoints/<tag> accanto a train.py
    # Funziona anche se Azure lancia il job con CWD diverso
    save_dir = os.path.join(_HERE, 'checkpoints', args.tag)
    os.makedirs(save_dir, exist_ok=True)

    print(f"\n[CF_FSNN] Device: {device}  |  Tag: {args.tag}  |  SEED: {SEED}")
    print(f"  Save dir: {save_dir}")

    # ── Salva snapshot della config ───────────────────────────────
    config_snap = vars(args)
    config_snap['device'] = str(device)
    config_snap['seed']   = SEED
    with open(os.path.join(save_dir, 'config_snapshot.json'), 'w') as f:
        json.dump(config_snap, f, indent=2)

    # ── Dataset ───────────────────────────────────────────────────
    from data.generator import generate_dataset, print_dataset_stats, parse_scenario_mix

    # Parse override scenari/cut_in (P10 — risolve P9_S1 con cache=highway senza modifica config.py)
    scenario_mix_dict = parse_scenario_mix(args.scenario_mix)
    cut_in_eff        = args.cut_in_ratio  # None → generator usa CUT_IN_RATIO da config
    print(f"[Dataset config] scenario_mix={scenario_mix_dict}")
    print(f"[Dataset config] cut_in_ratio={cut_in_eff if cut_in_eff is not None else 'default (from config.py)'}")

    # Sanity check: se cache esistente, verifica che sia compatibile con la config corrente
    # (idealmente il tag della cache dovrebbe includere scenario/cut_in, ma per backward
    # compatibility lasciamo la responsabilità all'utente — il print sopra rende esplicito)

    if args.data_cache is not None and os.path.isfile(args.data_cache):
        # ── Carica dalla cache .pt ─────────────────────────────────
        print(f"[Dataset] Caricamento da cache: {args.data_cache}")
        cache      = torch.load(args.data_cache, weights_only=False)
        train_data = cache['train']
        val_data   = cache['val']
        print(f"  Train: {len(train_data)} traiettorie  |  "
              f"Val: {len(val_data)} traiettorie  (seed={cache.get('seed', '?')})")
        # Verifica coerenza cache vs scenario richiesto (warning solo)
        cache_scenarios = set(d['scenario'] for d in train_data[:50])
        requested = {s for s, p in scenario_mix_dict.items() if p > 0}
        unexpected = cache_scenarios - requested
        if unexpected:
            print(f"  ⚠️  ATTENZIONE: cache contiene scenari {unexpected} non in scenario_mix={requested}.")
            print(f"     La cache è stata generata con una config diversa. Considera di rigenerarla:")
            print(f"     !rm {args.data_cache}")

    elif args.load_data is not None:
        # ── Legacy: carica da cartella pkl ────────────────────────
        print(f"[Dataset] Caricamento legacy da {args.load_data} ...")
        with open(os.path.join(args.load_data, 'train.pkl'), 'rb') as f:
            train_data = pickle.load(f)
        with open(os.path.join(args.load_data, 'val.pkl'), 'rb') as f:
            val_data = pickle.load(f)
        print(f"  Train: {len(train_data)} traiettorie  |  Val: {len(val_data)} traiettorie")

    else:
        # ── Genera ex novo ────────────────────────────────────────
        print(f"[Dataset] Generazione sintetica ACC-IDM (noise_scale={args.noise_scale}) ...")
        train_data = generate_dataset(args.n_train, base_seed=SEED,
                                      scenario_mix=scenario_mix_dict,
                                      cut_in_ratio=cut_in_eff,
                                      noise_scale=args.noise_scale)
        val_data   = generate_dataset(args.n_val,   base_seed=SEED + 1,
                                      scenario_mix=scenario_mix_dict,
                                      cut_in_ratio=cut_in_eff,
                                      noise_scale=args.noise_scale)
        print_dataset_stats(train_data, 'train')
        print_dataset_stats(val_data,   'val')

        # Salva cache se richiesto
        if args.data_cache is not None:
            os.makedirs(os.path.dirname(os.path.abspath(args.data_cache)), exist_ok=True)
            torch.save({'train': train_data, 'val': val_data, 'seed': SEED}, args.data_cache)
            print(f"[Dataset] Cache salvata: {args.data_cache}"
                  f"  ({os.path.getsize(args.data_cache) / 1e6:.1f} MB)")

    seq_len    = args.seq_len
    stride_trn = seq_len // 2
    stride_val = seq_len

    _extra_ch = bool(args.cf_extra_channels)
    train_ds = CFDataset(train_data, seq_len=seq_len, stride=stride_trn, extra_channels=_extra_ch)
    val_ds   = CFDataset(val_data,   seq_len=seq_len, stride=stride_val, extra_channels=_extra_ch)

    # num_workers: auto-rilevamento sicuro per ogni piattaforma.
    # Regola: 0 se Windows (fork CUDA non sicuro), 0 se Colab (CUDA già
    # inizializzato da model.to(device) prima del fork), altrimenti min(4, cpu).
    if args.num_workers >= 0:
        _nw = args.num_workers          # override esplicito da CLI
    elif os.name == 'nt':
        _nw = 0                          # Windows — CUDA non fork-safe
    else:
        # Colab detection: se google.colab è importabile siamo su Colab
        try:
            import google.colab          # noqa: F401
            _nw = 0                      # Colab — CUDA inizializzato prima del fork
        except ImportError:
            _nw = min(4, os.cpu_count() or 1)  # Azure/Linux — fork-safe
    _pw = _nw > 0   # persistent_workers riduce overhead di spawn su Azure

    # STEP 2C — val_batch_size separato per non penalizzare validation quando
    # train usa batch=1 (Plan A Prodigy). Default -1 → fallback a --batch_size
    # (retrocompatibile: tutti i run precedenti continuano a funzionare uguali).
    val_bs = args.val_batch_size if args.val_batch_size > 0 else args.batch_size
    train_loader = DataLoader(
        train_ds, batch_size=args.batch_size, shuffle=True,
        num_workers=_nw, pin_memory=(device.type == 'cuda'),
        persistent_workers=_pw,
    )
    val_loader = DataLoader(
        val_ds, batch_size=val_bs, shuffle=False,
        num_workers=_nw, pin_memory=(device.type == 'cuda'),
        persistent_workers=_pw,
    )
    print(f"[Dataset] Finestre train: {len(train_ds)}  |  val: {len(val_ds)}"
          f"  |  batch_train={args.batch_size}  batch_val={val_bs}"
          f"  |  num_workers={_nw}")

    # ── Modello (UNIFIED: hidden_size/rank/training_method via build_model) ──
    # R25: aggiunti max_delay e bit_shift override per ablation asse A4/A5/A6
    model    = build_model(
        variant=args.training_method,
        hidden_size=args.cf_hidden_size,
        rank=args.cf_rank,
        max_delay=args.cf_max_delay,
        bit_shift=args.cf_bit_shift,
        input_size=(7 if bool(args.cf_extra_channels) else None),   # L3 #2: 4->7 con encoding
        uncertainty=bool(args.uncertainty_head),                     # L3 #5: output 5->10 + NLL
    ).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    # Log unificato: max_delay non sempre disponibile (LIF simple non lo espone)
    max_delay_str = f", max_delay={getattr(model, 'max_delay', 'N/A')}"
    print(f"\n[Modello] variant={args.training_method}  class={type(model).__name__}  "
          f"hidden={model.hidden_size}, rank={model.rank}{max_delay_str}, "
          f"parametri totali: {n_params:,}")

    # ── Ottimizzatore ─────────────────────────────────────────────
    if args.optimizer == 'adam':
        optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    elif args.optimizer == 'adamw':
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    elif args.optimizer == 'lion':
        optimizer = LionOptimizer(model.parameters(), lr=args.lr, weight_decay=1e-4)
    elif args.optimizer == 'prodigy':
        # Prodigy (Mishchenko & Defazio, 2024) — LR-free adaptive optimizer.
        # Convention: pass lr=1.0 as the initial estimate; Prodigy auto-tunes.
        # Reference: https://github.com/konstmish/prodigy
        # Designed for batch_size=1 + noise-driven exploration (STEP 2C — P12 anti-local-minima).
        try:
            from prodigyopt import Prodigy
        except ImportError as e:
            raise ImportError(
                "prodigyopt non installato. Su Azure: !pip install prodigyopt\n"
                f"Errore originale: {e}"
            )
        # R2: parse betas string "b1,b2" -> tuple
        try:
            _b1, _b2 = [float(x.strip()) for x in args.prodigy_betas.split(',')]
            _betas = (_b1, _b2)
        except Exception as e:
            raise ValueError(
                f"--prodigy_betas formato non valido: '{args.prodigy_betas}'. "
                f"Atteso 'b1,b2' (es. '0.9,0.99'). Errore: {e}"
            )
        # R2: weight_decay -1 = sentinel "usa default hardcoded storico"
        _wd = 1e-4 if args.prodigy_weight_decay < 0 else args.prodigy_weight_decay
        optimizer = Prodigy(
            model.parameters(),
            lr=args.lr,                                              # raccomandato lr=1.0 (auto-adapt)
            betas=_betas,                                            # R2: CLI tunable (W1 in PRODIGY_DEEP_STUDY.md)
            weight_decay=_wd,                                        # R2: CLI tunable (W4)
            decouple=True,                                           # AdamW-style decoupled wd
            use_bias_correction=bool(args.prodigy_use_bias_correction),  # R2: CLI tunable (W3)
            safeguard_warmup=bool(args.prodigy_safeguard_warmup),    # R2: CLI tunable
            growth_rate=args.prodigy_growth_rate,                    # R2: CLI tunable (default inf)
            d_coef=args.prodigy_d_coef,                              # R2: CLI tunable (W2)
            d0=args.prodigy_d0,                                      # R2: CLI tunable (V2 — fix per frozen)
        )
        # Self-check: verifica che Prodigy abbia recepito esattamente i param richiesti
        _g0 = optimizer.param_groups[0]
        assert _g0['lr'] == args.lr, f"Prodigy lr mismatch: got {_g0['lr']} vs args {args.lr}"
        assert _g0['betas'] == _betas, f"Prodigy betas mismatch: got {_g0['betas']} vs args {_betas}"
        assert _g0['d_coef'] == args.prodigy_d_coef, f"Prodigy d_coef mismatch: got {_g0['d_coef']}"
        assert _g0['d0'] == args.prodigy_d0, f"Prodigy d0 mismatch: got {_g0['d0']}"
        assert _g0['safeguard_warmup'] == bool(args.prodigy_safeguard_warmup), f"Prodigy safeguard mismatch"
        assert _g0['use_bias_correction'] == bool(args.prodigy_use_bias_correction), f"Prodigy bias_corr mismatch"
        assert _g0['weight_decay'] == _wd, f"Prodigy wd mismatch: got {_g0['weight_decay']} vs {_wd}"
        print(f"[Prodigy] lr={_g0['lr']} betas={_g0['betas']} d0={_g0['d0']:.2e} d_coef={_g0['d_coef']} "
              f"wd={_g0['weight_decay']} use_bias_corr={_g0['use_bias_correction']} "
              f"safeguard={_g0['safeguard_warmup']} growth_rate={_g0['growth_rate']}")
    else:
        raise ValueError(f"Ottimizzatore non supportato: {args.optimizer}")

    # ── Scheduler LR ──────────────────────────────────────────────
    # STEP 2C: se max_steps_per_epoch è attivo, OneCycle deve costruire il
    # profilo sul numero EFFETTIVO di step (altrimenti la curva LR finisce
    # tagliata a metà perché interrompiamo prima).
    if args.scheduler == 'none':
        # STEP 2C — nessun scheduler. Usato per ottimizzatori auto-adattivi
        # (Prodigy) che gestiscono internamente il LR e non vogliono interferenze.
        scheduler = None
        sched_per_batch = False
    elif args.scheduler == 'onecycle':
        effective_spe = (min(len(train_loader), args.max_steps_per_epoch)
                         if args.max_steps_per_epoch > 0 else len(train_loader))
        scheduler = torch.optim.lr_scheduler.OneCycleLR(
            optimizer,
            max_lr=args.max_lr,
            epochs=args.epochs,
            steps_per_epoch=effective_spe,
            pct_start=0.30,       # 30% epoche di warmup
            div_factor=10.0,      # lr_start = max_lr / 10
            final_div_factor=100, # lr_end   = lr_start / 100
        )
        sched_per_batch = True
    elif args.scheduler == 'cosine':
        scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            optimizer, T_0=args.T0, T_mult=1, eta_min=1e-6,
        )
        sched_per_batch = False
    elif args.scheduler == 'cosine_no_restart':
        # R2: cosine PURO senza restarts, raccomandato da konstmish per Prodigy
        # (Issue #8, #10). T_max = numero totale di scheduler.step() che faremo.
        # sched_per_batch=False -> step() per-epoca -> T_max = epochs.
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=args.epochs, eta_min=1e-6,
        )
        sched_per_batch = False
    elif args.scheduler == 'custom_restart':
        # R32 (2026-06-15) — Custom restart scheduler gestito MANUALMENTE nel main loop
        # (post val_epoch). Setting None qui significa "no auto scheduler step".
        # La logica vive in main loop: vedi `compute_custom_lr()` + restart trigger.
        scheduler = None
        sched_per_batch = False
        print(f"[R32 Custom Restart] T0={args.restart_T0} decay={args.restart_decay} "
              f"lr_after={args.restart_lr_after} warmup={args.restart_warmup_epochs} "
              f"adaptive={args.restart_adaptive}")
    else:  # plateau (default — usato nel primo run)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=10, min_lr=1e-6,
        )
        sched_per_batch = False

    # ── Resume ────────────────────────────────────────────────────
    start_epoch = 1
    best_val    = float('inf')

    if args.resume is not None:
        start_epoch, best_val = load_checkpoint(model, optimizer, args.resume, device)
        start_epoch += 1
        print(f"[Resume] Ripreso da epoca {start_epoch-1}, val_loss={best_val:.5f}\n")

    # ── Logger CSV ────────────────────────────────────────────────
    log_path = os.path.join(save_dir, 'training_log.csv')
    logger   = CSVLogger(log_path)

    # T (telemetria estesa): logger per-batch — flush ogni 50 righe per perfo I/O.
    # Append-only: anche se il training crasha, il file contiene i dati raccolti
    # fino a quel punto (utile per analisi post-mortem di anomalie come exploding gn).
    batch_log_path = os.path.join(save_dir, 'training_batch_log.csv')
    batch_logger   = BatchCSVLogger(batch_log_path, flush_every=50)

    # Pesi PINN come tupla per pinn_loss() — 14 componenti (B5 + R25 T_aux + R30 4 params
    # + L2 geo/ratio/regime). Ordine MUST match pinn_loss signature: lam_data, lam_phys,
    # lam_ou, lam_bc, lam_sr, lam_T_aux, lam_v0_aux, lam_s0_aux, lam_a_aux, lam_b_aux,
    # lam_geo_aux, lam_ratio_aux, regime_gamma, regime_thr.
    lam = (args.lambda_data, args.lambda_phys, args.lambda_ou, args.lambda_bc,
           args.lambda_sr, args.lambda_T_aux,
           args.lambda_v0_aux, args.lambda_s0_aux, args.lambda_a_aux, args.lambda_b_aux,
           args.lambda_geo_aux, args.lambda_ratio_aux, args.regime_gamma, args.regime_thr,
           args.lambda_nll)

    # ── Training loop ─────────────────────────────────────────────
    print(f"\n[Training] {args.epochs} epoche  |  scheduler={args.scheduler}"
          f"  batch={args.batch_size}  lr={args.lr}")
    print(f"  lam_data={args.lambda_data}  lam_phys={args.lambda_phys}"
          f"  lam_ou={args.lambda_ou}  lam_bc={args.lambda_bc}"
          f"  lam_sr={args.lambda_sr}  lam_T_aux={args.lambda_T_aux}")
    if args.early_stop_patience > 0:
        print(f"  Early stop: patience={args.early_stop_patience}, "
              f"delta={args.early_stop_delta}\n")
    else:
        print("  Early stop: DISABILITATO (patience=0)\n")

    # ── R29 DEC-3: calibrazione decode_offset PRIMA del training ──
    # Backward-compat: skip se --cf_init_bias_shift=0 (default).
    if args.cf_init_bias_shift == 1:
        try:
            # R30 fix: loader e' 4-tuple (x, y, mask, params_gt). Prendi solo x.
            _batch = next(iter(train_loader))
            x_cal = _batch[0]
            x_cal = x_cal.to(device)
            model.calibrate_decode_offset(x_cal)
            print(f"[R29 DEC-3] decode_offset calibrato (batch {x_cal.shape[0]}x{x_cal.shape[1]}):")
            print(f"           {[f'{v:.3f}' for v in model.decode_offset.tolist()]}")
        except Exception as e:
            print(f"[R29 DEC-3] WARN: calibrazione fallita ({e}), uso default 0")

    # ── R29 DEC-1: parse logit_tau init values ──
    # cf_logit_tau_per_channel override (5 valori CSV) ha precedenza su scalare.
    if args.cf_logit_tau_per_channel is not None:
        try:
            tau_init_vec = [float(x.strip()) for x in args.cf_logit_tau_per_channel.split(',')]
            assert len(tau_init_vec) == 5, f'attesi 5 valori, got {len(tau_init_vec)}'
            model.set_logit_tau(tau_init_vec)
            print(f"[R29 DEC-1] logit_tau per-channel init: {tau_init_vec}")
        except Exception as e:
            print(f"[R29 DEC-1] ERR parsing cf_logit_tau_per_channel: {e}")
            raise
    elif args.cf_logit_tau_init != 1.0 or args.cf_logit_tau_schedule != 'const':
        model.set_logit_tau(args.cf_logit_tau_init)
        print(f"[R29 DEC-1] logit_tau init={args.cf_logit_tau_init} final={args.cf_logit_tau_final} schedule={args.cf_logit_tau_schedule}")

    # R32 (2026-06-15) — Custom restart scheduler state + helpers
    cr_last_restart_epoch = 0   # epoca dell'ultimo restart (0 = no restart yet, ciclo 0)
    cr_cycle_num = 0            # numero di restart eseguiti
    cr_T_intra_history = []     # storia val_T_intra_corr per adaptive trigger

    def _custom_restart_lr(epoch):
        """R32: calcola lr per epoca corrente nello scheduler custom_restart.

        epoch:  epoca CORRENTE (1-indexed).
        Usa cr_last_restart_epoch + cr_cycle_num come stato esterno.

        Logica:
          1. cycle_max_lr = lr × decay^cycle (Opzione 1) OR fissato (Opzione 2)
          2. Cosine decay entro il ciclo: cosine_factor = 0.5(1+cos(pi × t/T0))
          3. Warmup (Opzione 4): se warmup_epochs > 0, scala cycle_max_lr
             linearmente nelle prime warmup_epochs DOPO restart.
        """
        epochs_since_restart = epoch - cr_last_restart_epoch - 1  # 0 = epoca subito dopo restart
        # cycle's max_lr
        if cr_cycle_num == 0:
            cycle_max_lr = args.lr
        elif args.restart_lr_after > 0:
            cycle_max_lr = args.restart_lr_after        # Opzione 2: lr fissato
        else:
            cycle_max_lr = args.lr * (args.restart_decay ** cr_cycle_num)  # Opzione 1: decay
        # Warmup ramp (Opzione 4): solo per cicli > 0 (no ramp al primo ciclo)
        if cr_cycle_num > 0 and args.restart_warmup_epochs > 0 \
                and epochs_since_restart < args.restart_warmup_epochs:
            ramp = (epochs_since_restart + 1) / args.restart_warmup_epochs
            cycle_max_lr = cycle_max_lr * ramp
        # Cosine decay entro il ciclo
        cycle_T = max(args.restart_T0, 1)
        e_in_cycle = max(0, min(epochs_since_restart, cycle_T))
        cosine_factor = 0.5 * (1.0 + math.cos(e_in_cycle * math.pi / cycle_T))
        # Floor minimo (evita 0)
        return max(cycle_max_lr * cosine_factor, 1e-6)

    def _check_restart_trigger(epoch, T_intra_history):
        """R32: decide se questo è il momento di un restart.

        Opzione 3 (adaptive): trigger se T_intra cala per 2 epoche consecutive.
        Opzione 0/1/2/4 (fixed): trigger ogni args.restart_T0 epoche.
        """
        if args.restart_adaptive:
            # Adaptive: cala per 2 epoche?
            if len(T_intra_history) >= 3:
                a, b, c = T_intra_history[-3:]
                # NB: nan-safe
                if not (math.isnan(a) or math.isnan(b) or math.isnan(c)):
                    if c < b < a:
                        return True
            return False
        else:
            # Fixed period
            if args.restart_T0 > 0 and (epoch - cr_last_restart_epoch) >= args.restart_T0:
                return True
            return False

    def _logit_tau_at_epoch(epoch):
        """R29: calcola tau per epoca corrente in [1, args.epochs] secondo schedule.

        const  : sempre cf_logit_tau_init
        linear : tau_init + (tau_final - tau_init) * (epoch - 1) / max(epochs - 1, 1)
        exp    : geometric interp: tau_init * (tau_final / tau_init) ** (e_norm)
        """
        if args.cf_logit_tau_schedule == 'const':
            return args.cf_logit_tau_init
        e_norm = (epoch - 1) / max(args.epochs - 1, 1)
        if args.cf_logit_tau_schedule == 'linear':
            return args.cf_logit_tau_init + (args.cf_logit_tau_final - args.cf_logit_tau_init) * e_norm
        # exp
        ratio = args.cf_logit_tau_final / max(args.cf_logit_tau_init, 1e-9)
        return args.cf_logit_tau_init * (ratio ** e_norm)

    # P11 — Early stopping state (attivo solo se patience > 0)
    es_no_improve = 0
    es_best_val   = float('inf')

    # R30 (2026-06-12) — epoch-level explosion guard state
    epoch_explosion_streak = 0

    try:
        for epoch in range(start_epoch, args.epochs + 1):
            t_ep = time.time()
            print(f"-- Epoca {epoch}/{args.epochs} " + "-" * 40)

            # R29 DEC-1: aggiorna logit_tau a inizio epoca (skip se per_channel attivo
            # o schedule=const con default tau=1).
            if (args.cf_logit_tau_per_channel is None
                and args.cf_logit_tau_schedule != 'const'):
                tau_e = _logit_tau_at_epoch(epoch)
                model.set_logit_tau(tau_e)
                print(f"  [R29 DEC-1] epoch {epoch}: logit_tau = {tau_e:.3f}")

            # R32 (2026-06-15) — Custom restart: aggiorna lr a inizio epoca.
            if args.scheduler == 'custom_restart':
                new_lr = _custom_restart_lr(epoch)
                optimizer.param_groups[0]['lr'] = new_lr
                print(f"  [R32 CustomRestart] ep{epoch}: lr={new_lr:.5f} "
                      f"(cycle={cr_cycle_num}, since_restart={epoch-cr_last_restart_epoch-1})")

            train_m = train_epoch(
                model, train_loader, optimizer, device, epoch, lam,
                scheduler=scheduler if sched_per_batch else None,
                step_per_batch=sched_per_batch,
                log_every=args.log_every,
                max_inf_streak=args.max_inf_streak,
                diag=args.smoke,
                batch_logger=batch_logger,
                max_steps_per_epoch=args.max_steps_per_epoch,
                explosion_threshold=args.epoch_explosion_threshold,
                grad_clip_mode=args.grad_clip,
                agc_lambda=args.agc_lambda,
            )

            # R30 (2026-06-12) — Epoch-level explosion guard.
            # Difesa contro gradient explosion mascherato dal clip_grad_norm_(1.0).
            # Solo attivo se --max_epoch_explosion_streak > 0 (default off).
            if args.max_epoch_explosion_streak > 0:
                max_gn_e  = train_m.get('max_gn_preclip', 0.0)
                expl_frac = train_m.get('explosion_frac', 0.0)
                # S1b (2026-06-18): epoca "esplosa" SOLO se una FRAZIONE dei batch supera
                # la soglia (> epoch_explosion_frac), non un singolo spike isolato. Il
                # vecchio criterio (max_gn > soglia) abortiva run pulite per 1 batch su 100.
                if expl_frac > args.epoch_explosion_frac:
                    epoch_explosion_streak += 1
                    print(f"  [ExplosionGuard] epoca {epoch}: frazione batch gn>soglia="
                          f"{expl_frac:.2f} > {args.epoch_explosion_frac} "
                          f"(max_gn={max_gn_e:.2e}, streak {epoch_explosion_streak}/{args.max_epoch_explosion_streak})")
                    if epoch_explosion_streak >= args.max_epoch_explosion_streak:
                        print(f"\n  [EARLY-STOP] {epoch_explosion_streak} epoche consecutive "
                              f"con >{args.epoch_explosion_frac:.0%} batch esplosi. Training abortito.")
                        crash_path = os.path.join(save_dir, 'crash_model.pt')
                        save_checkpoint(model, optimizer, epoch, float('inf'), crash_path)
                        print(f"  Crash dump salvato: {crash_path}")
                        break
                else:
                    if epoch_explosion_streak > 0:
                        print(f"  [ExplosionGuard] reset streak (frazione esplosi={expl_frac:.2f} ok, "
                              f"max_gn={max_gn_e:.2e})")
                    epoch_explosion_streak = 0

            if train_m.get('aborted'):
                print(f"[Training] Abortito per esplosione del gradiente."
                      f" Epoch {epoch}, LR={optimizer.param_groups[0]['lr']:.3e}")
                crash_path = os.path.join(save_dir, 'crash_model.pt')
                save_checkpoint(model, optimizer, epoch, float('inf'), crash_path)
                print(f"  Crash dump salvato: {crash_path}")
                break

            val_m = val_epoch(model, val_loader, device, lam)

            # R32 (2026-06-15) — Custom restart: aggiorna history + trigger check
            if args.scheduler == 'custom_restart':
                cr_T_intra_history.append(val_m.get('val_T_intra_corr', float('nan')))
                if _check_restart_trigger(epoch, cr_T_intra_history):
                    cr_cycle_num += 1
                    cr_last_restart_epoch = epoch
                    trigger_type = 'adaptive(T_intra↓)' if args.restart_adaptive else 'fixed_T0'
                    print(f"  [R32 CustomRestart] RESTART @ epoch {epoch} ({trigger_type}) "
                          f"-> cycle {cr_cycle_num}")

            # Step scheduler per-epoch (plateau e cosine).
            # STEP 2C: guard su scheduler=None (caso --scheduler none o custom_restart).
            if scheduler is not None and not sched_per_batch:
                if args.scheduler == 'plateau':
                    scheduler.step(val_m['total'])
                else:
                    scheduler.step()

            # Leggi lr corrente
            current_lr = optimizer.param_groups[0]['lr']

            ep_time = time.time() - t_ep
            print(f"  > train={train_m['total']:.4f}"
                  f"  val={val_m['total']:.4f}"
                  f"  (data={val_m['data']:.4f}"
                  f"  phys={val_m['phys']:.5f}"
                  f"  ou={val_m['ou']:.6f})"
                  f"  spike={val_m['spike_rate']*100:.1f}%"
                  f"  lr={current_lr:.2e}"
                  f"  [{ep_time:.1f}s]\n")

            # CSV logging (R25 — 11 colonne tracking aggiunte)
            row = {
                'epoch'       : epoch,
                'train_total' : train_m['total'],
                'train_data'  : train_m['data'],
                'train_phys'  : train_m['phys'],
                'train_ou'    : train_m['ou'],
                'train_bc'    : train_m['bc'],
                'train_sr'    : train_m.get('sr', float('nan')),
                'val_total'   : val_m['total'],
                'val_data'    : val_m['data'],
                'val_phys'    : val_m['phys'],
                'val_ou'      : val_m['ou'],
                'val_bc'      : val_m['bc'],
                'val_sr'      : val_m.get('sr', float('nan')),
                'lr'          : current_lr,
                'grad_norm'   : train_m['grad_norm'],
                'spike_rate'  : val_m['spike_rate'],
                'time_s'      : ep_time,
                # Prodigy adapter (NaN per altri optimizer)
                'prodigy_d'      : optimizer.param_groups[0].get('d', float('nan')),
                'prodigy_d_max'  : optimizer.param_groups[0].get('d_max', float('nan')),
                'prodigy_lr_eff' : (current_lr * optimizer.param_groups[0].get('d', float('nan'))),
            }
            # R25 — copia tutte le val_* metric da val_m al row (tracking_corr + per-canale)
            # R27 — aggiunto val_T_intra_corr (Pearson per-sample mean-removed).
            for k in ('val_T_tracking_corr', 'val_T_intra_corr',
                      'val_v0_pred_mean', 'val_T_pred_mean', 'val_s0_pred_mean',
                      'val_a_pred_mean', 'val_b_pred_mean',
                      'val_v0_intra_std', 'val_T_intra_std', 'val_s0_intra_std',
                      'val_a_intra_std', 'val_b_intra_std',
                      'val_v0_nrmse', 'val_T_nrmse', 'val_s0_nrmse',
                      'val_a_nrmse', 'val_b_nrmse'):
                row[k] = val_m.get(k, float('nan'))
            logger.log(row)

            # Checkpoint best model
            if val_m['total'] < best_val:
                best_val = val_m['total']
                ck_path  = os.path.join(save_dir, 'best_model.pt')
                save_checkpoint(model, optimizer, epoch, best_val, ck_path)
                print(f"  ** Nuovo best val_loss={best_val:.5f}  -> {ck_path}\n")

            # Checkpoint finale (sovrascrive ogni epoca)
            save_checkpoint(model, optimizer, epoch, val_m['total'],
                            os.path.join(save_dir, 'last_model.pt'))

            # ── P11 Early Stopping ────────────────────────────────
            # Conta epoche senza miglioramento significativo (> delta).
            # Quando raggiunge patience, ferma il training per:
            #   1) evitare di sprecare compute oltre il plateau (P8/P9)
            #   2) prevenire crash da exploding gradient post-plateau (P6_T2/T3)
            if args.early_stop_patience > 0:
                if val_m['total'] < es_best_val - args.early_stop_delta:
                    es_best_val   = val_m['total']
                    es_no_improve = 0
                    print(f"  [EarlyStop] Miglioramento OK — reset counter "
                          f"(best={es_best_val:.5f})")
                else:
                    es_no_improve += 1
                    print(f"  [EarlyStop] Nessun miglioramento ({es_no_improve}"
                          f"/{args.early_stop_patience}). val={val_m['total']:.5f} "
                          f"vs best={es_best_val:.5f} (delta>{args.early_stop_delta})")
                    if es_no_improve >= args.early_stop_patience:
                        print(f"\n  [EARLY-STOP] {args.early_stop_patience} epoche senza "
                              f"miglioramento — training terminato volontariamente.\n"
                              f"  Best val_loss={es_best_val:.5f} all'epoca "
                              f"{epoch - args.early_stop_patience}.\n")
                        break
    finally:
        # Garantisce chiusura dei CSV anche su Ctrl+C, OOM, CUDA error
        logger.close()
        batch_logger.close()   # T: chiude e flusha training_batch_log.csv

    # ── Raccolta dati G5/G7: un pass finale sul val set ───────────
    # Eseguito sul best_model per dati coerenti con il checkpoint.
    T_pred_arr       = None
    T_true_arr       = None
    param_samples    = None
    g13_trajectories = None   # T (G13): traiettorie val per il plot segnali↔parametri
    # ── Raccolta dati G5/G7: un pass finale sul val set ───────────
    # Solo FileNotFoundError e KeyError sono recuperabili (ckpt mancante/corrotto).
    # Tutto il resto (OOM, CUDA, shape mismatch) viene rilasciato per propagare.
    best_ck_path = os.path.join(save_dir, 'best_model.pt')
    try:
        best_ck = torch.load(best_ck_path, map_location=device, weights_only=False)
        # P2 D2: strict=False per compatibilità con checkpoint pre-F5 (senza decode_scale).
        # `decode_scale` è un buffer derivato deterministicamente dai bounds nel costruttore:
        # se manca nel state_dict caricato, mantiene il valore inizializzato (corretto).
        # Zero rischio funzionale per altri buffer derivati che fossero aggiunti in futuro.
        missing, unexpected = model.load_state_dict(best_ck['model_state'], strict=False)
        if missing:
            print(f"[Checkpoint compat] Buffer mancanti nel checkpoint (ricostruiti dal costruttore): {missing}")
        if unexpected:
            print(f"[Checkpoint compat] Chiavi inattese nel checkpoint (ignorate): {unexpected}")
        model.eval()

        T_pred_list = []
        T_true_list = []
        param_list  = []

        with torch.no_grad():
            for batch in val_loader:
                # R30: 4-tuple loader. mask_v/params_gt non usati in questo collector.
                x_v = batch[0]
                y_v = batch[1]
                x_v = x_v.to(device)
                y_v = y_v.to(device)
                params_seq, _ = model.forward_sequence_with_stats(x_v)
                T_pred_list.append(params_seq[:, :, 1].cpu().numpy())
                T_true_list.append(y_v[:, :, 1].cpu().numpy())
                param_list.append(params_seq.cpu().numpy())

        T_pred_arr = np.concatenate(T_pred_list).ravel()
        T_true_arr = np.concatenate(T_true_list).ravel()
        all_p      = np.concatenate(param_list, axis=0)  # (N_win, T, 5)
        param_samples = {
            'v0': all_p[:, :, 0].ravel(),
            'T':  all_p[:, :, 1].ravel(),
            's0': all_p[:, :, 2].ravel(),
            'a':  all_p[:, :, 3].ravel(),
            'b':  all_p[:, :, 4].ravel(),
        }
        print(f"[Diagnostics] Dati G5/G7 raccolti: {len(T_pred_arr)} campioni.")

        # ── G13: 3 traiettorie val rappresentative ────────────────
        # Selezioniamo: 1 highway-no-cutin, 1 urban-no-cutin, 1 cut_in (qualsiasi).
        # Forward sequence completa (~1000 step post-warmup) sul modello best.
        # `raw` (N,7) contiene già i segnali fisici denormalizzati — niente conversione.
        selectors = [
            ('highway', lambda d: d['scenario'] == 'highway' and not d['cut_in']),
            ('urban',   lambda d: d['scenario'] == 'urban'   and not d['cut_in']),
            ('cut_in',  lambda d: d['cut_in']),
        ]
        used_idx = set()
        g13_trajectories = []
        for label, pred in selectors:
            for i, d in enumerate(val_data):
                if i in used_idx:
                    continue
                if pred(d):
                    used_idx.add(i)
                    _xv = d['x']                                          # (N,4) grezzo
                    if getattr(model, 'input_size', 4) >= 7:             # L3 #2: stessa augmentation di CFDataset
                        _dv = np.zeros((_xv.shape[0], 3), dtype=np.float32)
                        _dv[1:, :] = _xv[1:, :3] - _xv[:-1, :3]
                        _xv = np.concatenate([_xv, _dv], axis=1)         # (N,7)
                    x_norm_t = torch.from_numpy(_xv).unsqueeze(0).to(device)  # (1,N,4|7)
                    with torch.no_grad():
                        params_seq_t, _ = model.forward_sequence_with_stats(x_norm_t)
                    params_np = params_seq_t.squeeze(0).cpu().numpy()    # (N, 5)
                    raw_np    = d['raw']                                  # (N, 7)
                    g13_trajectories.append({
                        's':      raw_np[:, 0],
                        'v':      raw_np[:, 1],
                        'dv':     raw_np[:, 2],
                        'v_l':    raw_np[:, 3],
                        'T_true': raw_np[:, 5],
                        'T_pred': params_np[:, 1],
                        'v0_pred': params_np[:, 0],
                        's0_pred': params_np[:, 2],
                        'a_pred':  params_np[:, 3],
                        'b_pred':  params_np[:, 4],
                        'scenario_params': {
                            'v0': d['params']['v0'],
                            's0': d['params']['s0'],
                            'a':  d['params']['a'],
                            'b':  d['params']['b'],
                        },
                        'scenario':  d['scenario'],
                        'is_cut_in': d['cut_in'],
                    })
                    break
        print(f"[Diagnostics] G13: selezionate {len(g13_trajectories)} traiettorie val "
              f"({', '.join(t['scenario'] + ('-cutin' if t['is_cut_in'] else '') for t in g13_trajectories)})")
    except (FileNotFoundError, KeyError) as e:
        print(f"[Diagnostics] Raccolta G5/G7/G13 saltata (checkpoint non disponibile): {e}")

    # ── Diagnostics (se matplotlib disponibile) ───────────────────
    # Cattura solo ImportError (matplotlib assente); altri errori propagano.
    try:
        from utils.plot_diagnostics import load_training_log, load_batch_log, plot_all
    except ImportError as e:
        print(f"[Diagnostics] matplotlib non disponibile, grafici saltati: {e}")
    else:
        log_data       = load_training_log(log_path)
        batch_log_data = load_batch_log(batch_log_path)   # T: per-batch (G8-G12)
        plot_dir       = os.path.join(save_dir, 'plots')

        # plot_all gestisce internamente log=None e batch_log=None separatamente:
        # se almeno uno dei due è valido, genera i grafici corrispondenti.
        if log_data is not None or batch_log_data is not None:
            plot_all(log_data, plot_dir,
                     T_pred=T_pred_arr, T_true=T_true_arr,
                     param_samples=param_samples,
                     batch_log=batch_log_data,
                     trajectories=g13_trajectories)
        else:
            # F3c esteso: nessun dato né per-epoca né per-batch (caso patologico)
            print("[Diagnostics] Nessun dato (né epoch né batch) — grafici saltati.")

    print(f"\n[Fine training] Best val_loss = {best_val:.5f}")
    print(f"  Checkpoint: {os.path.join(save_dir, 'best_model.pt')}")
    print(f"  Log CSV:    {log_path}")


if __name__ == '__main__':
    main()
