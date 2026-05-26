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
    NORM_S_MAX, NORM_V_MAX, NORM_DV_MAX, NORM_VL_MAX,
    ACC_COOLNESS, ACC_AL_TAU,
    N_SCENARIOS_TRAIN, N_SCENARIOS_VAL,
    DT,
)
from core.network import CF_FSNN_Net


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

    Ogni elemento restituisce:
        x    (seq_len, 4)  -- input normalizzato [s̃, ṽ, Δṽ, ṽ_l]
        y    (seq_len, 2)  -- ground truth [v_dot [m/s²], T_true [s]]
        mask (seq_len,)    -- V2X packet mask (1=ricevuto, 0=lost)
    """

    def __init__(self, dataset_list, seq_len=100, stride=50):
        self.seq_len = seq_len
        self.windows = []

        for item in dataset_list:
            x    = item['x']
            y    = item['y']
            mask = item['mask']
            N     = x.shape[0]
            start = 0
            while start + seq_len <= N:
                self.windows.append((
                    x[start:start + seq_len],
                    y[start:start + seq_len],
                    mask[start:start + seq_len],
                ))
                start += stride

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, idx):
        x, y, mask = self.windows[idx]
        return (
            torch.from_numpy(x),
            torch.from_numpy(y),
            torch.from_numpy(mask),
        )


# ===========================================================
# PINN Loss (ACC-IDM con base IIDM)
# ===========================================================

def pinn_loss(model, x_seq, y_seq, mask_seq,
              lam_data, lam_phys, lam_ou, lam_bc):
    """
    Loss PINN a quattro componenti con ACC-IDM (IIDM base).

    x_seq:    (batch, T, 4)  -- input normalizzato
    y_seq:    (batch, T, 2)  -- [v_dot [m/s²], T_true [s]]
    mask_seq: (batch, T)     -- V2X mask

    Physics: usa CF_FSNN_Net.acc_iidm_accel() con a_l stimata da
    differenze finite su v_l + filtro OU (tau=ACC_AL_TAU).

    Ritorna: (loss_scalare, dict_componenti, spike_rate_media)
    """
    batch, T_len, _ = x_seq.shape

    # ── Forward SNN ────────────────────────────────────────────────
    params_seq, spike_rates = model.forward_sequence_with_stats(x_seq)
    # params_seq: (batch, T, 5)  spike_rates: (batch, T) — hidden layer

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

    loss = (lam_data * L_data
            + lam_phys * L_phys
            + lam_ou   * L_ou
            + lam_bc   * L_bc)

    avg_spike_rate = spike_rates.mean().item()

    return loss, {
        'total': loss.item(),
        'data' : L_data.item(),
        'phys' : L_phys.item(),
        'ou'   : L_ou.item(),
        'bc'   : L_bc.item(),
    }, avg_spike_rate


# ===========================================================
# Patch: forward_sequence_with_stats
# ===========================================================

def _forward_sequence_with_stats(self, x_seq_norm):
    """
    Come forward_sequence ma restituisce anche spike_rate del layer hidden.
    Patch aggiunta a CF_FSNN_Net per il logging diagnostico.
    """
    batch, T_len, _ = x_seq_norm.shape
    self.reset_state(batch, x_seq_norm.device)
    steps  = []
    spikes = []
    for t in range(T_len):
        x_t = x_seq_norm[:, t, :]
        # Ripeti forward_step monitorando gli spike
        raw_out = None
        spike_h_acc = torch.zeros(batch, self.layer_hidden.out_features,
                                  device=x_t.device)
        for tick in range(self.n_ticks):
            spike_h = self.layer_hidden(x_t)
            raw_out = self.layer_out(spike_h)
            spike_h_acc = spike_h_acc + spike_h.float()
        # Media spike rate sul tick
        spike_h_rate = spike_h_acc / self.n_ticks   # (batch, hidden)
        spikes.append(spike_h_rate.mean(dim=1, keepdim=True))  # (batch, 1)
        steps.append(self._decode_params(raw_out).unsqueeze(1))

    params_seq = torch.cat(steps,  dim=1)   # (batch, T, 5)
    spike_rate = torch.cat(spikes, dim=1)   # (batch, T)
    return params_seq, spike_rate

# Monkey-patch sul modello
CF_FSNN_Net.forward_sequence_with_stats = _forward_sequence_with_stats


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


def train_epoch(model, loader, optimizer, device, epoch, lam,
                scheduler=None, step_per_batch=False,
                log_every=LOG_EVERY, max_inf_streak=20, diag=False):
    """
    Esegue un'epoca di training con guardie e diagnostica.

    step_per_batch  — True per OneCycleLR (step dopo ogni batch).
    log_every       — frequenza log batch (1 = ogni batch, per smoke mode).
    max_inf_streak  — n. massimo di batch consecutivi con grad=inf prima di abortire.
    diag            — True: calcola norme per-layer pre-clip su OGNI batch (smoke mode).

    Ritorna dict metriche; se training abortito, include 'aborted': True.
    """
    model.train()
    totals     = {'total': 0.0, 'data': 0.0, 'phys': 0.0, 'ou': 0.0, 'bc': 0.0}
    spike_acc  = 0.0
    grad_acc   = 0.0
    n_batches  = 0
    inf_streak = 0          # batch consecutivi con grad_norm=inf
    t0         = time.time()

    for batch_idx, (x, y, mask) in enumerate(loader):
        x    = x.to(device)
        y    = y.to(device)
        mask = mask.to(device)

        optimizer.zero_grad()
        loss, comps, sr = pinn_loss(model, x, y, mask, *lam)

        # ── Guardia NaN loss ──────────────────────────────────────
        if not loss.isfinite():
            tag = f"  [NaN-Guard E{epoch:02d} B{batch_idx+1:04d}]"
            print(f"{tag} loss={loss.item()} — skip backward")
            _log_batch_diagnostics(tag, comps, float('nan'), x, None, model)
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

        gn     = nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        gn_val = float(gn)

        # ── Guardia NaN gradiente ─────────────────────────────────
        if not math.isfinite(gn_val):
            inf_streak += 1
            tag = f"  [NaN-Grad E{epoch:02d} B{batch_idx+1:04d}]"
            print(f"{tag} grad_norm=inf  streak={inf_streak}/{max_inf_streak}")
            _log_batch_diagnostics(tag, comps, gn_val, x, pre_norms, model)
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
    avgs['aborted']    = False
    return avgs


@torch.no_grad()
def val_epoch(model, loader, device, lam):
    model.eval()
    totals    = {'total': 0.0, 'data': 0.0, 'phys': 0.0, 'ou': 0.0, 'bc': 0.0}
    spike_acc = 0.0
    n_batches = 0

    for x, y, mask in loader:
        x    = x.to(device)
        y    = y.to(device)
        mask = mask.to(device)
        _, comps, sr = pinn_loss(model, x, y, mask, *lam)
        for k in totals:
            totals[k] += comps[k]
        spike_acc += sr
        n_batches  += 1

    nb = max(n_batches, 1)
    avgs = {k: v / nb for k, v in totals.items()}
    avgs['spike_rate'] = spike_acc / nb
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
        'train_total', 'train_data', 'train_phys', 'train_ou', 'train_bc',
        'val_total',   'val_data',   'val_phys',   'val_ou',   'val_bc',
        'lr', 'grad_norm', 'spike_rate', 'time_s',
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
                        choices=['plateau', 'onecycle', 'cosine'],
                        help='Scheduler LR: plateau|onecycle|cosine')
    parser.add_argument('--max_lr',      type=float, default=5e-3,
                        help='LR massimo per OneCycleLR')
    parser.add_argument('--T0',          type=int,   default=5,
                        help='Periodo per CosineAnnealingWarmRestarts')
    # Pesi PINN loss
    parser.add_argument('--lambda_data', type=float, default=LAMBDA_DATA)
    parser.add_argument('--lambda_phys', type=float, default=LAMBDA_PHYS)
    parser.add_argument('--lambda_ou',   type=float, default=LAMBDA_OU)
    parser.add_argument('--lambda_bc',   type=float, default=LAMBDA_BC)
    # Ottimizzatore
    parser.add_argument('--optimizer',   type=str,   default='adam',
                        choices=['adam', 'adamw', 'lion'],
                        help='Ottimizzatore: adam|adamw|lion')
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
    # Checkpoint
    parser.add_argument('--resume',      type=str,   default=None,
                        help='Checkpoint .pt da cui riprendere')
    parser.add_argument('--tag',         type=str,   default='run',
                        help='Etichetta cartella output (checkpoints/<tag>/)')
    args = parser.parse_args()

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
    from data.generator import generate_dataset, print_dataset_stats

    if args.data_cache is not None and os.path.isfile(args.data_cache):
        # ── Carica dalla cache .pt ─────────────────────────────────
        print(f"[Dataset] Caricamento da cache: {args.data_cache}")
        cache      = torch.load(args.data_cache, weights_only=False)
        train_data = cache['train']
        val_data   = cache['val']
        print(f"  Train: {len(train_data)} traiettorie  |  "
              f"Val: {len(val_data)} traiettorie  (seed={cache.get('seed', '?')})")

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
        print("[Dataset] Generazione sintetica ACC-IDM ...")
        train_data = generate_dataset(args.n_train, base_seed=SEED)
        val_data   = generate_dataset(args.n_val,   base_seed=SEED + 1)
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

    train_ds = CFDataset(train_data, seq_len=seq_len, stride=stride_trn)
    val_ds   = CFDataset(val_data,   seq_len=seq_len, stride=stride_val)

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

    train_loader = DataLoader(
        train_ds, batch_size=args.batch_size, shuffle=True,
        num_workers=_nw, pin_memory=(device.type == 'cuda'),
        persistent_workers=_pw,
    )
    val_loader = DataLoader(
        val_ds, batch_size=args.batch_size, shuffle=False,
        num_workers=_nw, pin_memory=(device.type == 'cuda'),
        persistent_workers=_pw,
    )
    print(f"[Dataset] Finestre train: {len(train_ds)}  |  val: {len(val_ds)}"
          f"  |  num_workers={_nw}")

    # ── Modello ───────────────────────────────────────────────────
    model    = CF_FSNN_Net().to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"\n[Modello] CF_FSNN_Net  --  parametri totali: {n_params:,}")

    # ── Ottimizzatore ─────────────────────────────────────────────
    if args.optimizer == 'adam':
        optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    elif args.optimizer == 'adamw':
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    elif args.optimizer == 'lion':
        optimizer = LionOptimizer(model.parameters(), lr=args.lr, weight_decay=1e-4)
    else:
        raise ValueError(f"Ottimizzatore non supportato: {args.optimizer}")

    # ── Scheduler LR ──────────────────────────────────────────────
    if args.scheduler == 'onecycle':
        scheduler = torch.optim.lr_scheduler.OneCycleLR(
            optimizer,
            max_lr=args.max_lr,
            epochs=args.epochs,
            steps_per_epoch=len(train_loader),
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

    # Pesi PINN come tupla per pinn_loss()
    lam = (args.lambda_data, args.lambda_phys, args.lambda_ou, args.lambda_bc)

    # ── Training loop ─────────────────────────────────────────────
    print(f"\n[Training] {args.epochs} epoche  |  scheduler={args.scheduler}"
          f"  batch={args.batch_size}  lr={args.lr}")
    print(f"  lam_data={args.lambda_data}  lam_phys={args.lambda_phys}"
          f"  lam_ou={args.lambda_ou}  lam_bc={args.lambda_bc}\n")

    try:
        for epoch in range(start_epoch, args.epochs + 1):
            t_ep = time.time()
            print(f"-- Epoca {epoch}/{args.epochs} " + "-" * 40)

            train_m = train_epoch(
                model, train_loader, optimizer, device, epoch, lam,
                scheduler=scheduler if sched_per_batch else None,
                step_per_batch=sched_per_batch,
                log_every=args.log_every,
                max_inf_streak=args.max_inf_streak,
                diag=args.smoke,
            )

            if train_m.get('aborted'):
                print(f"[Training] Abortito per esplosione del gradiente."
                      f" Epoch {epoch}, LR={optimizer.param_groups[0]['lr']:.3e}")
                crash_path = os.path.join(save_dir, 'crash_model.pt')
                save_checkpoint(model, optimizer, epoch, float('inf'), crash_path)
                print(f"  Crash dump salvato: {crash_path}")
                break

            val_m = val_epoch(model, val_loader, device, lam)

            # Step scheduler per-epoch (plateau e cosine)
            if not sched_per_batch:
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

            # CSV logging
            logger.log({
                'epoch'       : epoch,
                'train_total' : train_m['total'],
                'train_data'  : train_m['data'],
                'train_phys'  : train_m['phys'],
                'train_ou'    : train_m['ou'],
                'train_bc'    : train_m['bc'],
                'val_total'   : val_m['total'],
                'val_data'    : val_m['data'],
                'val_phys'    : val_m['phys'],
                'val_ou'      : val_m['ou'],
                'val_bc'      : val_m['bc'],
                'lr'          : current_lr,
                'grad_norm'   : train_m['grad_norm'],
                'spike_rate'  : val_m['spike_rate'],
                'time_s'      : ep_time,
            })

            # Checkpoint best model
            if val_m['total'] < best_val:
                best_val = val_m['total']
                ck_path  = os.path.join(save_dir, 'best_model.pt')
                save_checkpoint(model, optimizer, epoch, best_val, ck_path)
                print(f"  ** Nuovo best val_loss={best_val:.5f}  -> {ck_path}\n")

            # Checkpoint finale (sovrascrive ogni epoca)
            save_checkpoint(model, optimizer, epoch, val_m['total'],
                            os.path.join(save_dir, 'last_model.pt'))
    finally:
        # Garantisce chiusura del CSV anche su Ctrl+C, OOM, CUDA error
        logger.close()

    # ── Raccolta dati G5/G7: un pass finale sul val set ───────────
    # Eseguito sul best_model per dati coerenti con il checkpoint.
    T_pred_arr    = None
    T_true_arr    = None
    param_samples = None
    # ── Raccolta dati G5/G7: un pass finale sul val set ───────────
    # Solo FileNotFoundError e KeyError sono recuperabili (ckpt mancante/corrotto).
    # Tutto il resto (OOM, CUDA, shape mismatch) viene rilasciato per propagare.
    best_ck_path = os.path.join(save_dir, 'best_model.pt')
    try:
        best_ck = torch.load(best_ck_path, map_location=device, weights_only=False)
        model.load_state_dict(best_ck['model_state'])
        model.eval()

        T_pred_list = []
        T_true_list = []
        param_list  = []

        with torch.no_grad():
            for x_v, y_v, mask_v in val_loader:
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
    except (FileNotFoundError, KeyError) as e:
        print(f"[Diagnostics] Raccolta G5/G7 saltata (checkpoint non disponibile): {e}")

    # ── Diagnostics (se matplotlib disponibile) ───────────────────
    # Cattura solo ImportError (matplotlib assente); altri errori propagano.
    try:
        from utils.plot_diagnostics import load_training_log, plot_all
    except ImportError as e:
        print(f"[Diagnostics] matplotlib non disponibile, grafici saltati: {e}")
    else:
        log_data = load_training_log(log_path)
        plot_dir = os.path.join(save_dir, 'plots')
        plot_all(log_data, plot_dir,
                 T_pred=T_pred_arr, T_true=T_true_arr,
                 param_samples=param_samples)

    print(f"\n[Fine training] Best val_loss = {best_val:.5f}")
    print(f"  Checkpoint: {os.path.join(save_dir, 'best_model.pt')}")
    print(f"  Log CSV:    {log_path}")


if __name__ == '__main__':
    main()
