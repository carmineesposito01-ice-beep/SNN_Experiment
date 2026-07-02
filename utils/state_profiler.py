"""utils/state_profiler.py -- Fase A FPGA (fondazione F2/F3): range degli stati interni.

Istrumenta il FORWARD reale via forward-hook per loggare, per tick, i tensori di stato
GIA' calcolati (o ricostruiti con le STESSE formule del forward, senza duplicare la logica):
  potential (membrana ALIF pre-reset), fatigue, eff_thresh, current (sinaptico in ingresso),
  rec_curr (ricorrente), rec_int (accumulatore low-rank tra i due linear V->U), raw_out
  (potenziale LI = pre-sigmoid del readout).

Da questi range NumPy discendono: formato fixed-point Qm.n per stato, soglia anti
leak-underflow, istogrammi, ISI. Foundation di 02_FixedPoint, 03_Spiking, 04_Energy.

Copertura: PIENA per la famiglia baseline (ALIFCell hookabile). Per eventprop
(ALIFLayer_EventProp_Full, stati dentro un autograd.Function) si catturano solo readout +
spike; il flag `baseline` lo dichiara. Modello primario del profilo = baseline 4->32->5.
"""
import numpy as np
import torch
import torch.nn.functional as F

from core.hardware import po2_quantize
from utils.net_diagnostics import _last_hidden
from utils.quantize import fake_quant

# stati con significato per il datapath fixed-point
STATE_ORDER = ['current', 'rec_int', 'rec_curr', 'potential', 'fatigue',
               'eff_thresh', 'raw_out']


def _range_stats(arr):
    """min/max/p0.1/p99.9/std/absmax su tutti gli elementi finiti di arr (N, dim)."""
    a = np.asarray(arr, dtype=np.float64).reshape(-1)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {k: float('nan') for k in ('min', 'max', 'p01', 'p999', 'std', 'absmax')}
    return {
        'min': float(a.min()), 'max': float(a.max()),
        'p01': float(np.percentile(a, 0.1)), 'p999': float(np.percentile(a, 99.9)),
        'std': float(a.std()), 'absmax': float(np.abs(a).max()),
    }


def suggest_fixed_point(stats, bit_shift=3, max_frac=16):
    """Formato Qm.n proposto da un range di stato (STIMA di progetto).

    int_bits: bit interi per coprire absmax (con segno). frac_bits: risoluzione per il
    minimo significativo. min_frac_anti_underflow: sotto questo, il leak (stato>>bit_shift)
    arrotonda a 0 -> il potenziale si "incastra" (serve >= bit_shift + margine).
    """
    absmax = stats.get('absmax', float('nan'))
    std = stats.get('std', float('nan'))
    int_bits = int(max(1, np.ceil(np.log2(absmax + 1e-9)))) + 1 if np.isfinite(absmax) and absmax > 0 else 1
    # risoluzione: copre ~1/8 di deviazione standard
    frac_bits = int(np.clip(np.ceil(-np.log2(max(std, 1e-9) / 8.0)), 2, max_frac)) if np.isfinite(std) else 8
    min_frac_anti_underflow = int(bit_shift + 2)   # leak = x/2^bit_shift deve restare rappresentabile
    return {'int_bits': int_bits, 'frac_bits': max(frac_bits, min_frac_anti_underflow),
            'min_frac_anti_underflow': min_frac_anti_underflow,
            'total_bits': int_bits + max(frac_bits, min_frac_anti_underflow) + 1}


def profile_states(model, x_batch, device='cpu', max_steps=None):
    """Esegue un forward strumentato e restituisce i range per stato.

    x_batch: (B, T, 4) tensor/array normalizzato. Ritorna
      {'baseline': bool, 'states': {nome_stato: range_stats}}.
    """
    x = torch.as_tensor(x_batch, dtype=torch.float32)
    if x.ndim == 2:
        x = x[None]
    x = x.to(device)
    if max_steps is not None:
        x = x[:, :int(max_steps), :]
    B = x.shape[0]

    hid = _last_hidden(model)
    baseline = hid is not None and hasattr(hid, 'cell')
    caps = {}

    def _stash(key, t):
        caps.setdefault(key, []).append(t.detach().reshape(-1, t.shape[-1]).cpu())

    handles = []
    if baseline:
        cell = hid.cell

        def pre_layer(mod, inp):
            with torch.no_grad():
                v_po2 = po2_quantize(mod.rec_V)
                rec_int = F.linear(cell.prev_spike, v_po2)   # STESSA formula del layer
            _stash('rec_int', rec_int)

        def pre_cell(mod, inp):
            cur, rec = inp[0], inp[1]
            with torch.no_grad():
                leak = mod.potential / mod.leak_div
                pot_int = mod.potential - leak + cur + rec       # membrana pre-reset
                eff = mod.base_threshold + mod.fatigue.clamp(min=0)
            _stash('current', cur)
            _stash('rec_curr', rec)
            _stash('potential', pot_int)
            _stash('eff_thresh', eff)
            _stash('fatigue', mod.fatigue)

        handles.append(hid.register_forward_pre_hook(pre_layer))
        handles.append(cell.register_forward_pre_hook(pre_cell))

    out_layer = getattr(model, 'layer_out', None)
    if out_layer is not None:
        def post_out(mod, inp, out):
            if torch.is_tensor(out):
                _stash('raw_out', out)
        handles.append(out_layer.register_forward_hook(post_out))

    model.eval()
    try:
        if hasattr(model, 'reset_state'):
            model.reset_state(B, device)
        with torch.no_grad():
            model.forward_sequence(x)
    finally:
        for h in handles:
            h.remove()

    states = {}
    for k, lst in caps.items():
        if lst:
            arr = torch.cat(lst, dim=0).numpy()
            states[k] = _range_stats(arr)
    return {'baseline': baseline, 'states': states}


def state_ranges_rows(model, x_batch, bit_shift=3, **kw):
    """Righe per state_ranges.csv: per stato -> range + Qm.n proposto."""
    prof = profile_states(model, x_batch, **kw)
    rows = []
    for name in STATE_ORDER:
        st = prof['states'].get(name)
        if st is None:
            continue
        fp = suggest_fixed_point(st, bit_shift=bit_shift)
        rows.append({'state': name, **{k: st[k] for k in ('min', 'max', 'p01', 'p999', 'std', 'absmax')}, **fp})
    return prof['baseline'], rows


def leak_underflow_curve(v0=2.0, bit_shift=3, frac_bits_list=(4, 6, 8), n_steps=40):
    """Decadimento del potenziale: float (esatto) vs fixed Qm.n che si INCASTRA.

    leak = pot / 2^bit_shift a ogni passo. In fixed-point con pochi frac_bits il leak
    arrotonda a 0 sotto una soglia -> il potenziale non decade piu' (bias residuo).
    Ritorna {'float': [...], 'fixed_<b>': [...]} per la figura leak_decay (sezione 02).
    """
    div = 2.0 ** bit_shift
    out = {'steps': list(range(n_steps))}
    pf = v0
    fl = []
    for _ in range(n_steps):
        fl.append(pf)
        pf = pf - pf / div
    out['float'] = fl
    for fb in frac_bits_list:
        p = float(fake_quant(v0, frac_bits=fb))
        ser = []
        for _ in range(n_steps):
            ser.append(p)
            leak = float(fake_quant(p / div, frac_bits=fb))   # leak quantizzato -> puo' essere 0
            p = float(fake_quant(p - leak, frac_bits=fb))
        out[f'fixed_{fb}b'] = ser
    return out


def isi_stats(raster):
    """Statistiche Inter-Spike-Interval dal raster (n_tick, hidden): min ISI (worst-case
    back-to-back), media, e distribuzione aggregata. Base della figura isi_dist (sezione 03)."""
    r = np.asarray(raster)
    if r.size == 0 or r.ndim != 2:
        return {'min_isi': float('nan'), 'mean_isi': float('nan'), 'isi_all': []}
    all_isi = []
    for j in range(r.shape[1]):
        idx = np.where(r[:, j] > 0.5)[0]
        if idx.size >= 2:
            all_isi.extend(np.diff(idx).tolist())
    if not all_isi:
        return {'min_isi': float('nan'), 'mean_isi': float('nan'), 'isi_all': []}
    a = np.asarray(all_isi)
    return {'min_isi': int(a.min()), 'mean_isi': float(a.mean()),
            'max_isi': int(a.max()), 'n_intervals': int(a.size), 'isi_all': a.tolist()}
