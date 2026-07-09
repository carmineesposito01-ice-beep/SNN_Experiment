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
    dynamic = spike-driven rec_V (s*rank) + rec_U (H*rank if any spike) + out (s*OUT)."""
    s = int(np.count_nonzero(np.asarray(spikes_row) > 0))
    static = int(n_in * n_hid)
    dynamic = int(s * rank + (n_hid * rank if s else 0) + s * n_out)
    return static, dynamic


def synops_series(spikes_matrix, n_in, n_hid, n_out, rank):
    """Vectorised over frames -> (static[], dynamic[])."""
    sm = np.asarray(spikes_matrix)
    if sm.size == 0:
        return np.empty(0), np.empty(0)
    s = np.count_nonzero(sm > 0, axis=1).astype(float)
    static = np.full(s.shape, float(n_in * n_hid))
    dynamic = s * rank + np.where(s > 0, float(n_hid * rank), 0.0) + s * n_out
    return static, dynamic


def dense_mac(n_in, n_hid, n_out, rank):
    """Clock-driven dense-MAC equivalent per tick (every synapse every tick = param count)."""
    return int(n_in * n_hid + 2 * rank * n_hid + n_hid * n_out)
