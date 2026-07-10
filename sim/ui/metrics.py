"""Pure car-following safety metrics (vectorised, scalar-friendly). Closing speed dv>0 = approaching."""
import numpy as np


def ttc(s, dv):
    s = np.asarray(s, dtype=float)
    dv = np.asarray(dv, dtype=float)
    return np.where(dv > 0, s / np.where(dv > 0, dv, 1.0), np.inf)


def drac(s, dv):
    s = np.asarray(s, dtype=float)
    dv = np.asarray(dv, dtype=float)
    return np.where(dv > 0, dv ** 2 / (2.0 * np.where(s > 0, s, 1e-9)), 0.0)


def time_headway(s, v):
    s = np.asarray(s, dtype=float)
    v = np.asarray(v, dtype=float)
    return np.where(v > 0, s / np.where(v > 0, v, 1.0), np.inf)


# --- SynOps / energy model (FPGA scorecard: static fc vs dynamic spike-driven; AC<MAC not sparsity) ---
def synops(spikes_row, n_in, n_hid, n_out, rank):
    """(static, dynamic) SynOps for one tick. static = fc input (always-on);
    dynamic = spike-driven rec_V (s*rank) + rec_U (H*rank if any spike) + out (s*OUT).
    Delegates to synops_series (single source of truth for the formula)."""
    static, dynamic = synops_series(np.asarray(spikes_row)[None, :], n_in, n_hid, n_out, rank)
    return int(static[0]), int(dynamic[0])


def synops_series(spikes_matrix, n_in, n_hid, n_out, rank):
    """Vectorised over frames -> (static[], dynamic[])."""
    sm = np.asarray(spikes_matrix)
    if sm.size == 0:
        return np.empty(0), np.empty(0)
    s = np.count_nonzero(sm > 0, axis=1).astype(float)
    static = np.full(s.shape, float(n_in * n_hid))
    dynamic = s * rank + np.where(s > 0, float(n_hid * rank), 0.0) + s * n_out
    return static, dynamic


def synops_breakdown(nsp, n_in, n_hid, n_out, rank):
    """Per-tick SynOps split (fc, rec_V, rec_U, out) for ONE tick with `nsp` spikes -- the single
    source the EpisodeSummary energy breakdown delegates to (same decomposition as synops_series)."""
    return (n_in * n_hid, nsp * rank, (n_hid * rank if nsp > 0 else 0), nsp * n_out)


def dense_mac(n_in, n_hid, n_out, rank):
    """Clock-driven dense-MAC equivalent per tick for THIS (low-rank) net = param count."""
    return int(n_in * n_hid + 2 * rank * n_hid + n_hid * n_out)


# Per-synaptic-op energy (Horowitz 45nm; from snn_showcase / scripts/fpga_figures.py: E_MAC, E_AC)
E_AC_PJ = 0.9      # accumulate — SNN spike-driven op (po2 shift-add on FPGA, 0 DSP)
E_MAC_PJ = 4.6     # multiply-accumulate — dense ANN op


def ann_mac(n_in, n_hid, n_out):
    """Dense-ANN-equivalent MACs/tick: a same-size dense recurrent RNN (FULL H*H recurrent)."""
    return int(n_in * n_hid + n_hid * n_hid + n_hid * n_out)
