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
