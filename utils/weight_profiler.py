"""utils/weight_profiler.py -- Fase A FPGA (fondazione F1/F4): profilo dei pesi po2.

Opera su un MODELLO VIVO (build_model + checkpoint caricato), non sul checkpoint grezzo,
cosi' il naming e' coerente. Gestisce ENTRAMBE le famiglie di champion:
  * baseline  (HiddenLayer_ALIF + ALIFCell + OutputLayer_LI):
        hidden.fc_weight/rec_U/rec_V/delays, hidden.cell.{base_threshold,thresh_jump}, out.fc_weight
  * eventprop (ALIFLayer_EventProp_Full + LILayer_BitShift_Po2):
        hidden.fc_weight/rec_U/rec_V/delays/delay_masks/{base_threshold,thresh_jump}, out.weight

Tutto software-only sui tensori. Usa il VERO quantizzatore po2 del deploy
(core.hardware.po2_quantize: esponenti clamp [-4, 1] -> alfabeto di 13 livelli).
Ogni peso sul target FPGA = segno + esponente offset -> BITS_PER_WEIGHT = 4 bit.

Base di: 01_Weights_po2 (istogramma esponenti, sparsita', footprint, spettro ricorrenza),
e la decodifica peso->bit riusata da seu_inject (F4).
"""
import numpy as np
import torch

from core.hardware import po2_quantize
from utils.net_diagnostics import _last_hidden, recurrence_spectral

# Dal PowerOf2Quantize.forward (core/hardware.py): log2(|w|) clampato a [-4, 1],
# maschera w_abs > 2^-5 -> altrimenti 0.
PO2_EXP_MIN, PO2_EXP_MAX = -4, 1
PO2_N_EXP = PO2_EXP_MAX - PO2_EXP_MIN + 1          # 6 esponenti
BITS_PER_WEIGHT = 4                                 # 1 segno + 3 esponente (6 valori -> 3 bit)


def _readout_weight(model):
    """Peso del readout, robusto al naming: OutputLayer_LI.fc_weight vs LILayer_BitShift_Po2.weight."""
    lo = getattr(model, 'layer_out', None)
    if lo is None:
        return None
    w = getattr(lo, 'fc_weight', None)
    return w if w is not None else getattr(lo, 'weight', None)


def _thresholds(hidden):
    """(base_threshold, thresh_jump) robusti: direttamente sul layer (eventprop) o su .cell (baseline)."""
    bt = getattr(hidden, 'base_threshold', None)
    tj = getattr(hidden, 'thresh_jump', None)
    if bt is None and getattr(hidden, 'cell', None) is not None:
        bt = getattr(hidden.cell, 'base_threshold', None)
        tj = getattr(hidden.cell, 'thresh_jump', None)
    return bt, tj


def weight_matrices(model):
    """dict {nome -> Parameter} dei 4 tensori sinaptici del datapath. hidden restituito a parte."""
    hid = _last_hidden(model)
    mats = {}
    if hid is not None:
        if getattr(hid, 'fc_weight', None) is not None:
            mats['fc'] = hid.fc_weight
        if getattr(hid, 'rec_U', None) is not None:
            mats['rec_U'] = hid.rec_U
        if getattr(hid, 'rec_V', None) is not None:
            mats['rec_V'] = hid.rec_V
    out = _readout_weight(model)
    if out is not None:
        mats['out'] = out
    return hid, mats


def _po2_np(w):
    """po2-quantizza un tensore/peso e ritorna numpy float64 (no grad)."""
    with torch.no_grad():
        return po2_quantize(w.detach()).cpu().numpy().astype(np.float64)


def po2_exponents(wq_abs):
    """Esponenti interi dei valori po2 non-nulli (|wq| -> round(log2))."""
    nz = wq_abs > 0
    if not np.any(nz):
        return np.array([], dtype=int)
    return np.round(np.log2(wq_abs[nz])).astype(int)


def _entropy_bits(counts):
    """Entropia di Shannon (bit) di una distribuzione discreta (array di conteggi)."""
    c = np.asarray(counts, dtype=np.float64)
    tot = c.sum()
    if tot <= 0:
        return 0.0
    p = c[c > 0] / tot
    return float(-(p * np.log2(p)).sum())


def matrix_stats(name, w):
    """Statistiche po2 per una matrice di pesi (nome + Parameter). Dict pronto per CSV."""
    raw = w.detach().cpu().numpy().astype(np.float64)
    wq = _po2_np(w)
    n = int(raw.size)
    wq_abs = np.abs(wq)
    n_zero = int((wq_abs == 0).sum())
    exps = po2_exponents(wq_abs)
    hist = {e: int((exps == e).sum()) for e in range(PO2_EXP_MIN, PO2_EXP_MAX + 1)}
    qerr = np.abs(raw - wq)
    return {
        'matrix': name,
        'shape': tuple(raw.shape),
        'n_weights': n,
        'frac_zero': n_zero / n if n else float('nan'),
        'exp_hist': hist,                                   # {esp -> conteggio}
        'entropy_bits': _entropy_bits(list(hist.values())),  # ~informazione per peso
        'bits_per_weight': BITS_PER_WEIGHT,
        'footprint_bits': n * BITS_PER_WEIGHT,
        'qerr_mean': float(qerr.mean()) if n else float('nan'),
        'qerr_max': float(qerr.max()) if n else float('nan'),
        'w_absmax': float(np.abs(raw).max()) if n else float('nan'),
    }


def _delay_report(hidden):
    """Distribuzione dei ritardi assonali + verifica ridondanza delay_masks == (delays==d)."""
    delays = getattr(hidden, 'delays', None)
    if delays is None:
        return {}
    d = delays.detach().cpu().numpy().astype(int)
    md = int(d.max()) + 1 if d.size else 0
    hist = {k: int((d == k).sum()) for k in range(md)}
    out = {'max_delay': md, 'hist': hist}
    masks = getattr(hidden, 'delay_masks', None)      # solo eventprop
    if masks is not None:
        m = masks.detach().cpu().numpy()
        ok = all(np.allclose(m[k], (d == k).astype(m.dtype)) for k in range(min(md, m.shape[0])))
        out['delay_masks_redundant'] = bool(ok)
    return out


def profile_weights(model):
    """Profilo completo dei pesi po2 del modello vivo. Ritorna dict strutturato.

    - matrices: lista di matrix_stats per fc/rec_U/rec_V/out
    - recurrence: rho / norm / eff_rank della ricorrenza U@V po2 (da net_diagnostics)
    - thresholds: statistiche base_threshold / thresh_jump
    - delays: distribuzione + check ridondanza delay_masks
    - totals: pesi sinaptici totali e footprint bit
    """
    hid, mats = weight_matrices(model)
    order = ['fc', 'rec_U', 'rec_V', 'out']
    stats = [matrix_stats(k, mats[k]) for k in order if k in mats]
    total_w = int(sum(s['n_weights'] for s in stats))
    total_bits = int(sum(s['footprint_bits'] for s in stats))

    thr = {}
    bt, tj = _thresholds(hid) if hid is not None else (None, None)
    if bt is not None:
        a = bt.detach().cpu().numpy()
        thr['base_threshold_mean'] = float(a.mean())
        thr['base_threshold_std'] = float(a.std())
    if tj is not None:
        a = tj.detach().cpu().numpy()
        thr['thresh_jump_mean'] = float(a.mean())
        thr['thresh_jump_std'] = float(a.std())

    return {
        'matrices': stats,
        'recurrence': recurrence_spectral(model),
        'thresholds': thr,
        'delays': _delay_report(hid) if hid is not None else {},
        'total_synaptic_weights': total_w,
        'total_footprint_bits': total_bits,
        'total_footprint_bytes': total_bits / 8.0,
    }


def weight_stats_rows(model):
    """Righe piatte (una per matrice) per weight_stats.csv, con l'istogramma esponenti espanso."""
    prof = profile_weights(model)
    rows = []
    for s in prof['matrices']:
        row = {k: v for k, v in s.items() if k != 'exp_hist' and k != 'shape'}
        row['shape'] = 'x'.join(str(d) for d in s['shape'])
        for e in range(PO2_EXP_MIN, PO2_EXP_MAX + 1):
            row[f'exp_{e}'] = s['exp_hist'].get(e, 0)
        rows.append(row)
    return rows
