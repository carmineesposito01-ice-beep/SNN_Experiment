"""
utils/simulator/engine.py -- CFSimulator engine

Pure-Python class che orchestra:
  1. Load CF_FSNN_Net checkpoint
  2. Load cache dataset (.pt)
  3. Per ogni scenario: forward SNN -> integra traiettoria ego_pred
  4. Calcola traiettoria ego_gt come reference (integra v_dot ground truth)
  5. Ricostruisce traiettoria leader dalla osservazione gap

OPEN-LOOP simulation: SNN vede gli input RECORDED a ogni step (s, v, dv, vl
osservati), NON gli input self-consistent della sua traiettoria predetta.
Questo matcha la semantica di val_data e la fairness col training. Closed-loop
(SNN vede inputs derivati dal pred) e' future extension.
"""

from __future__ import annotations
import os
import sys
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import torch

# Path setup per import core/ + config
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.network import build_model, CF_FSNN_Net
from config import (
    DT, NORM_S_MAX, NORM_V_MAX, NORM_DV_MAX, NORM_VL_MAX,
    ACC_COOLNESS, ACC_AL_TAU,
)


@dataclass
class SimulationResult:
    """Output di CFSimulator.simulate_scenario.

    Tutti gli array hanno length T_sim (subset del raw 1000 step della cache,
    tipicamente 200 = 20 secondi per visualizzazione adeguata).

    Coordinate spaziali x_*: posizione assoluta sulla strada [m], starting from 0.
    Coordinate temporali time: tempo dall'inizio dello scenario [s].
    """
    # Identita' scenario
    idx: int
    scenario_type: str       # 'highway' | 'urban' | 'truck'
    is_cut_in: bool
    params_true: dict        # {'v0', 'T', 's0', 'a', 'b', 'delta'}

    # Time axis
    time: np.ndarray         # (T,) seconds
    DT: float

    # Input osservato (denormalized)
    s_obs: np.ndarray        # (T,) gap [m]
    v_obs: np.ndarray        # (T,) ego velocity [m/s]
    dv_obs: np.ndarray       # (T,) v - v_lead [m/s]
    vl_obs: np.ndarray       # (T,) leader velocity [m/s]
    a_l_filtered: np.ndarray # (T,) leader accel filtered (OU tau=ACC_AL_TAU)
    mask: np.ndarray         # (T,) V2X mask 1=received

    # Ground truth
    a_gt: np.ndarray         # (T,) accelerazione recorded
    params_true_seq: np.ndarray  # (T, 5) constant per scenario, broadcasted

    # SNN predictions
    params_pred: np.ndarray  # (T, 5) [v0, T, s0, a, b] predetti
    a_pred: np.ndarray       # (T,) accelerazione da acc_iidm_accel(params_pred)
    spike_rate: np.ndarray   # (T,) avg spike rate hidden layer
    spike_full: np.ndarray   # (T, hidden) per-neuron spike rate (avg over n_ticks)

    # Trajectories (integrazione ballistica DT=0.1s)
    x_ego_pred: np.ndarray   # (T,) posizione ego con accel predetta
    v_ego_pred: np.ndarray   # (T,) velocita' ego con accel predetta
    x_ego_gt: np.ndarray     # (T,) posizione ego con accel GT (re-integrate v_dot)
    v_ego_gt: np.ndarray     # (T,) velocita' ego GT (riparte da v_obs)
    x_lead: np.ndarray       # (T,) posizione leader (ricostruita da x_ego_gt + s_obs)

    # Derived gaps
    gap_pred: np.ndarray     # (T,) x_lead - x_ego_pred (gap simulato sotto pred)
    gap_gt: np.ndarray       # (T,) x_lead - x_ego_gt (gap simulato sotto GT) -- should ~= s_obs

    # Metadata
    seq_len: int             # T totale (= len di tutti gli array)
    hidden_size: int         # neuroni hidden della rete


# ============================================================
# Helper: filtro OU su leader accel (replica train.py:193-200)
# ============================================================
def _ou_filter_leader_accel(vl: np.ndarray, dt: float, tau: float) -> np.ndarray:
    """Stima a_l da differenze finite su v_l + filtro OU IIR.

    y[t] = alpha * y[t-1] + beta * x[t],  y[0] = x[0]
    alpha = exp(-dt/tau)

    Replica esattamente quanto fatto in train.py pinn_loss (riga 186-205).
    """
    n = len(vl)
    a_l_raw = np.zeros(n, dtype=np.float32)
    a_l_raw[1:] = np.diff(vl) / dt
    a_l_raw[0] = a_l_raw[1]   # padding causale

    alpha = math.exp(-dt / tau)
    beta = 1.0 - alpha
    y = np.zeros(n, dtype=np.float32)
    y[0] = a_l_raw[0]
    for t in range(1, n):
        y[t] = alpha * y[t-1] + beta * a_l_raw[t]
    return y


# ============================================================
# CFSimulator
# ============================================================
class CFSimulator:
    """Engine per simulazione visiva CF_FSNN.

    Args:
        checkpoint_path: path a `best_model.pt` (dict con 'model_state', 'epoch', 'val_loss').
        cache_path: path a `cache_*.pt` (dict con 'train', 'val' liste di scenari).
        variant: nome variante per build_model (default 'baseline'; deve matchare il
                 checkpoint -- per checkpoint baseline lascia default).
        device: 'cpu' | 'cuda' | None (autodetect).
        seq_len: lunghezza simulazione [step], default 200 (= 20s a DT=0.1).
                 Massimo 1000 (= length recorded trajectories).
        split: 'val' (default) | 'train' -- da quale partizione del cache prendere scenari.

    Esempio:
        sim = CFSimulator('checkpoints/GRID2x2_baseline/best_model.pt',
                          'data/cache_1500_highway_cut0.0_ou0.0.pt')
        df = sim.list_scenarios()        # DataFrame indice scenari
        result = sim.simulate_scenario(0)  # SimulationResult per idx=0
    """

    def __init__(self,
                 checkpoint_path: str,
                 cache_path: str,
                 variant: str = 'baseline',
                 device: Optional[str] = None,
                 seq_len: int = 200,
                 split: str = 'val'):
        self.checkpoint_path = checkpoint_path
        self.cache_path = cache_path
        self.variant = variant
        self.seq_len = seq_len
        self.split = split
        self.DT = DT

        # Device
        if device is None:
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device = torch.device(device)

        # Load checkpoint + build model
        if not os.path.isfile(checkpoint_path):
            raise FileNotFoundError(f'Checkpoint non trovato: {checkpoint_path}')
        ckpt = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
        if not isinstance(ckpt, dict) or 'model_state' not in ckpt:
            raise ValueError(f'Checkpoint formato inatteso: keys={list(ckpt.keys()) if isinstance(ckpt, dict) else type(ckpt)}')

        self.model = build_model(variant)
        # strict=False: buffer derivati (es. leak_div) sono auto-init, non in state_dict
        missing, unexpected = self.model.load_state_dict(ckpt['model_state'], strict=False)
        self.model = self.model.to(self.device).eval()

        self.ckpt_epoch = ckpt.get('epoch', -1)
        self.ckpt_val_loss = ckpt.get('val_loss', float('nan'))
        self.hidden_size = self.model.hidden_size

        # Load cache
        if not os.path.isfile(cache_path):
            raise FileNotFoundError(f'Cache non trovata: {cache_path}')
        cache = torch.load(cache_path, map_location='cpu', weights_only=False)
        if not isinstance(cache, dict) or split not in cache:
            raise ValueError(f'Cache non ha split "{split}". Keys: {list(cache.keys()) if isinstance(cache, dict) else type(cache)}')
        self.scenarios = cache[split]
        if len(self.scenarios) == 0:
            raise ValueError(f'Cache split "{split}" vuoto')
        self.n_scenarios = len(self.scenarios)

        # Validate seq_len
        max_traj_len = self.scenarios[0]['raw'].shape[0]
        if seq_len > max_traj_len:
            print(f'[WARN] seq_len={seq_len} > traj_len={max_traj_len}, clipping a {max_traj_len}')
            self.seq_len = max_traj_len

        # Validate model has acc_iidm_accel (richiesto per integrazione)
        if not hasattr(self.model, 'acc_iidm_accel'):
            raise ValueError(
                f'Model {type(self.model).__name__} non ha acc_iidm_accel(). '
                'Solo i variants che ereditano da CF_FSNN_Net sono supportati.')

        # Verbose init summary
        print(f'[CFSimulator] checkpoint: {checkpoint_path}')
        print(f'  epoch={self.ckpt_epoch}  val_loss={self.ckpt_val_loss:.4f}'
              if isinstance(self.ckpt_val_loss, (int, float)) and not math.isnan(self.ckpt_val_loss)
              else f'  epoch={self.ckpt_epoch}  val_loss=N/A')
        print(f'  variant={variant}  class={type(self.model).__name__}')
        print(f'  hidden={self.hidden_size}  rank={self.model.rank}  '
              f'max_delay={getattr(self.model, "max_delay", "N/A")}  '
              f'n_ticks={getattr(self.model, "n_ticks", "N/A")}')
        if missing:
            print(f'  missing keys (OK, buffer derivati): {missing}')
        if unexpected:
            print(f'  unexpected keys: {unexpected}')
        print(f'[CFSimulator] cache: {cache_path}')
        print(f'  split={split}  n_scenarios={self.n_scenarios}  '
              f'raw_traj_len={max_traj_len}  sim_seq_len={self.seq_len}')
        print(f'[CFSimulator] device={self.device}  DT={DT}s')

    # ------------------------------------------------------------
    # Index scenarios
    # ------------------------------------------------------------
    def list_scenarios(self) -> pd.DataFrame:
        """Returns DataFrame indice scenari con metadata utili per selezione."""
        rows = []
        for i, sc in enumerate(self.scenarios):
            p = sc.get('params', {})
            rows.append({
                'idx':           i,
                'scenario_type': sc.get('scenario', 'unknown'),
                'is_cut_in':     bool(sc.get('cut_in', False)),
                'profile':       sc.get('profile', '?'),
                'v0_true':       float(p.get('v0', np.nan)),
                'T_true':        float(p.get('T', np.nan)),
                's0_true':       float(p.get('s0', np.nan)),
                'a_true':        float(p.get('a', np.nan)),
                'b_true':        float(p.get('b', np.nan)),
                'v_mean_obs':    float(sc['raw'][:self.seq_len, 1].mean()),  # ego v mean
                'mask_pct':      float(sc['raw'][:self.seq_len, 6].mean()),  # mask ratio
            })
        return pd.DataFrame(rows)

    # ------------------------------------------------------------
    # Main entry: simulate single scenario
    # ------------------------------------------------------------
    @torch.no_grad()
    def simulate_scenario(self, idx: int) -> SimulationResult:
        """Esegue simulazione completa scenario [idx], restituisce SimulationResult."""
        if idx < 0 or idx >= self.n_scenarios:
            raise IndexError(f'idx={idx} fuori range [0, {self.n_scenarios})')

        sc = self.scenarios[idx]
        T = self.seq_len

        # Estrai input (normalized) + raw (denormalized)
        x_norm = sc['x'][:T]          # (T, 4) normalized
        raw    = sc['raw'][:T]        # (T, 7) [s, v, dv, vl, v_dot, T_true, mask]
        mask   = raw[:, 6]
        scenario_type = sc.get('scenario', 'unknown')
        is_cut_in = bool(sc.get('cut_in', False))
        params_true = sc.get('params', {})

        # Denorm shorthand
        s_obs  = raw[:, 0].astype(np.float32)
        v_obs  = raw[:, 1].astype(np.float32)
        dv_obs = raw[:, 2].astype(np.float32)
        vl_obs = raw[:, 3].astype(np.float32)
        a_gt   = raw[:, 4].astype(np.float32)
        # T_true = raw[:, 5]  (constant)

        # ── Forward SNN (whole sequence as batch=1) ─────────────────
        x_t = torch.from_numpy(x_norm).unsqueeze(0).float().to(self.device)  # (1, T, 4)
        params_seq_t, sr_t = self.model.forward_sequence_with_stats(x_t)
        params_seq = params_seq_t.squeeze(0).cpu().numpy()                  # (T, 5)
        spike_rate = sr_t.squeeze(0).cpu().numpy()                          # (T,)

        # Per-neuron spike rate: ri-forward salvando spike per ogni neurone.
        # Workaround: forward_sequence_with_stats restituisce mean over neurons.
        # Per il raster plot dettagliato facciamo manualmente.
        spike_full = self._extract_full_spike_rate(x_t, T)                  # (T, hidden)

        # ── Filtra leader acceleration (OU, come train.py) ─────────
        a_l_filtered = _ou_filter_leader_accel(vl_obs, dt=self.DT, tau=ACC_AL_TAU)

        # ── Compute predicted acceleration via acc_iidm_accel ──────
        # Per ogni t, chiama acc_iidm_accel(s,v,dv,a_l, params_pred[t]) -> a_pred[t]
        a_pred = self._compute_predicted_accel(
            s_obs, v_obs, dv_obs, a_l_filtered, params_seq)                # (T,)

        # ── Integrate ego trajectories (ballistic, DT=0.1) ─────────
        # Ego PRED (using a_pred), starting from v_obs[0] at x=0
        x_ego_pred, v_ego_pred = self._integrate_ballistic(
            v0=v_obs[0], accel=a_pred, dt=self.DT)
        # Ego GT (using a_gt = v_dot recorded), starting from v_obs[0] at x=0
        x_ego_gt, v_ego_gt = self._integrate_ballistic(
            v0=v_obs[0], accel=a_gt, dt=self.DT)
        # Leader trajectory: ricostruita da x_ego_gt + s_obs (gap recorded)
        # Nota: usiamo x_ego_gt come reference perche' la coppia (s_obs, v_ego_gt)
        # corrisponde alla realta'. x_ego_pred puo' divergere -> gap_pred = x_lead - x_ego_pred
        x_lead = x_ego_gt + s_obs

        # Derived gaps
        gap_gt   = x_lead - x_ego_gt   # = s_obs by construction (sanity)
        gap_pred = x_lead - x_ego_pred

        # Time axis
        time = np.arange(T, dtype=np.float32) * self.DT

        # params_true_seq (constant broadcast)
        pt_arr = np.array([
            params_true.get('v0', np.nan),
            params_true.get('T',  np.nan),
            params_true.get('s0', np.nan),
            params_true.get('a',  np.nan),
            params_true.get('b',  np.nan),
        ], dtype=np.float32)
        params_true_seq = np.tile(pt_arr, (T, 1))

        return SimulationResult(
            idx=idx, scenario_type=scenario_type, is_cut_in=is_cut_in,
            params_true=dict(params_true),
            time=time, DT=self.DT,
            s_obs=s_obs, v_obs=v_obs, dv_obs=dv_obs, vl_obs=vl_obs,
            a_l_filtered=a_l_filtered, mask=mask,
            a_gt=a_gt, params_true_seq=params_true_seq,
            params_pred=params_seq, a_pred=a_pred,
            spike_rate=spike_rate, spike_full=spike_full,
            x_ego_pred=x_ego_pred, v_ego_pred=v_ego_pred,
            x_ego_gt=x_ego_gt, v_ego_gt=v_ego_gt, x_lead=x_lead,
            gap_pred=gap_pred, gap_gt=gap_gt,
            seq_len=T, hidden_size=self.hidden_size,
        )

    # ------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------
    def _extract_full_spike_rate(self, x_t: torch.Tensor, T: int) -> np.ndarray:
        """Ri-forward salvando spike rate per-neurone (T, hidden).

        Approccio pulito: monkeypatch temporaneo del hidden layer per catturare
        spike. Funziona per CF_FSNN_Net standard (HiddenLayer_ALIF).
        Per altri variant (eventprop) ritorna mean (broadcasted).
        """
        if not hasattr(self.model, 'layer_hidden') or not hasattr(self.model.layer_hidden, 'cell'):
            # Fallback: broadcast spike_rate mean a (T, hidden)
            with torch.no_grad():
                _, sr_t = self.model.forward_sequence_with_stats(x_t)
            sr_mean = sr_t.squeeze(0).cpu().numpy()                        # (T,)
            return np.tile(sr_mean[:, None], (1, self.hidden_size))

        # Hook: registra spike per ogni call al layer_hidden.cell
        captured = []
        def _hook(module, inputs, output):
            # output di ALIFCell.forward e' (B, num_neurons) di spikes
            captured.append(output.detach().cpu().numpy())
        handle = self.model.layer_hidden.cell.register_forward_hook(_hook)

        try:
            with torch.no_grad():
                self.model.forward_sequence_with_stats(x_t)
        finally:
            handle.remove()

        if not captured:
            return np.zeros((T, self.hidden_size), dtype=np.float32)

        # captured ha n_ticks * T entries (uno per ogni call). Aggregate per step.
        n_ticks = getattr(self.model, 'n_ticks', 1)
        spike_stack = np.concatenate(captured, axis=0)                     # (T*n_ticks, hidden) for B=1
        if spike_stack.ndim == 3:
            spike_stack = spike_stack[:, 0, :]                              # squeeze batch dim if present
        # Reshape: (T, n_ticks, hidden) -> mean su n_ticks
        if spike_stack.shape[0] != T * n_ticks:
            # Mismatch, fallback
            return np.zeros((T, self.hidden_size), dtype=np.float32)
        spike_per_step = spike_stack.reshape(T, n_ticks, self.hidden_size).mean(axis=1)
        return spike_per_step.astype(np.float32)

    def _compute_predicted_accel(self, s, v, dv, a_l, params_pred) -> np.ndarray:
        """Calcola a_pred[t] = acc_iidm_accel(s,v,dv,a_l, params_pred[t]) per ogni t.

        Vettorizzato via torch (acc_iidm_accel e' implementato in torch).
        """
        s_t  = torch.from_numpy(s).float().to(self.device)
        v_t  = torch.from_numpy(v).float().to(self.device)
        dv_t = torch.from_numpy(dv).float().to(self.device)
        al_t = torch.from_numpy(a_l).float().to(self.device)
        pp_t = torch.from_numpy(params_pred).float().to(self.device)
        with torch.no_grad():
            a_pred = self.model.acc_iidm_accel(s_t, v_t, dv_t, al_t, pp_t,
                                                coolness=ACC_COOLNESS)
        return a_pred.cpu().numpy().astype(np.float32)

    @staticmethod
    def _integrate_ballistic(v0: float, accel: np.ndarray, dt: float):
        """Integrazione ballistica per ego (matches generator + Treiber Ch11).

            v[t+1] = v[t] + a[t] * dt
            x[t+1] = x[t] + v[t] * dt + 0.5 * a[t] * dt^2

        Returns (x_arr, v_arr) entrambi (T,).
        """
        T = len(accel)
        v_arr = np.zeros(T, dtype=np.float32)
        x_arr = np.zeros(T, dtype=np.float32)
        v_arr[0] = v0
        # x_arr[0] = 0 (default)
        for t in range(T - 1):
            x_arr[t+1] = x_arr[t] + v_arr[t] * dt + 0.5 * accel[t] * dt * dt
            v_arr[t+1] = max(0.0, v_arr[t] + accel[t] * dt)  # crash provision: v >= 0
        return x_arr, v_arr
