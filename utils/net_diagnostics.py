"""utils/net_diagnostics.py — diagnostica interna della SNN per l'evaluate.

Nessun helper equivalente esisteva nelle librerie eval (dead-neuron, effective rank, raster completo,
raggio spettrale della ricorrenza). Questi operano sul FORWARD reale del modello (CF_FSNN_Net e sottoclassi)
istrumentando l'ALIFCell dell'hidden layer via forward-hook, quindi sono robusti a come e' scritto
forward_step. Tutto software-only sui tensori esistenti (nessun checkpoint speciale, nessun HW).
"""
import numpy as np
import torch


def _last_hidden(model):
    """Restituisce l'ultimo HiddenLayer_ALIF (quello che alimenta l'output) per baseline e varianti."""
    if getattr(model, 'layer_hidden', None) is not None:
        return model.layer_hidden
    if getattr(model, 'layer_hidden_1', None) is not None:   # StackedSkip
        return model.layer_hidden_1
    if getattr(model, 'layers_hidden', None) is not None:    # Stacked
        return model.layers_hidden[-1]
    return None


def spike_raster(model, x_seq, device='cpu', max_steps=None):
    """Raster COMPLETO per-neurone x tick dell'hidden layer su UNA sequenza.

    x_seq: (T,4) o (1,T,4). Istrumenta ALIFCell.forward via hook -> cattura gli spike {0,1} ad OGNI tick
    interno (n_ticks per step). Ritorna array (n_righe, hidden) con n_righe = T * n_ticks (batch 0).
    """
    x = torch.as_tensor(x_seq, dtype=torch.float32)
    if x.ndim == 2:
        x = x[None]
    x = x.to(device)
    if max_steps is not None:
        x = x[:, :int(max_steps), :]
    B = x.shape[0]
    hid = _last_hidden(model)
    if hid is None or not hasattr(hid, 'cell'):
        return np.zeros((0, 0))
    caps = []

    def _hook(_mod, _inp, out):
        caps.append(out.detach()[0].float().cpu().numpy())   # (hidden,) spike binari del campione 0

    h = hid.cell.register_forward_hook(_hook)
    try:
        model.eval()
        model.reset_state(B, device)
        with torch.no_grad():
            model.forward_sequence(x)                          # forward pieno: il hook scatta a ogni tick
    finally:
        h.remove()
    if not caps:
        return np.zeros((0, 0))
    return np.stack(caps, axis=0)                              # (T*n_ticks, hidden)


def spike_stats(raster):
    """Statistiche di attivita' dal raster (n_righe, hidden): dead/saturi/rate + rate per-neurone + eventi totali."""
    if raster.size == 0:
        return {'dead_frac': float('nan'), 'sat_frac': float('nan'), 'mean_rate': float('nan'),
                'total_spikes': float('nan'), 'per_neuron_rate': []}
    fr = raster.mean(axis=0)                                   # firing rate per-neurone in [0,1]
    return {'dead_frac': float((fr <= 1e-9).mean()),          # neuroni che non sparano MAI
            'sat_frac': float((fr >= 1.0 - 1e-9).mean()),     # neuroni SEMPRE attivi
            'mean_rate': float(fr.mean()),
            'total_spikes': float(raster.sum()),
            'per_neuron_rate': fr.tolist()}


def effective_rank(raster):
    """Rank effettivo dell'attivita' = participation ratio degli autovalori della covarianza per-neurone.
    eff_rank = (Σλ)² / Σλ² ∈ [1, hidden]. Basso = attivita' ridondante/degenerata (pochi modi indipendenti)."""
    if raster.size == 0 or raster.shape[0] < 2:
        return float('nan')
    X = raster - raster.mean(axis=0, keepdims=True)
    C = X.T @ X / max(1, X.shape[0] - 1)
    ev = np.linalg.eigvalsh(C)
    ev = ev[ev > 1e-12]
    if ev.size == 0:
        return float('nan')
    return float((ev.sum() ** 2) / (np.sum(ev ** 2) + 1e-12))


def recurrence_spectral(model):
    """Raggio spettrale e norma-2 della ricorrenza EFFETTIVA U@V (po2) + eff_rank dei valori singolari.
    Rilevante per la stabilita' del loop ricorrente in fixed-point (framework FPGA). {} se non low-rank."""
    hid = _last_hidden(model)
    if hid is None or not (hasattr(hid, 'rec_U') and hasattr(hid, 'rec_V')):
        return {}
    from core.hardware import po2_quantize
    U = po2_quantize(hid.rec_U).detach().cpu().numpy()
    V = po2_quantize(hid.rec_V).detach().cpu().numpy()
    W = U @ V
    eig = np.abs(np.linalg.eigvals(W))
    sv = np.linalg.svd(W, compute_uv=False)
    return {'spectral_radius': float(eig.max()),
            'spectral_norm': float(sv[0]),
            'eff_rank_W': float((sv.sum() ** 2) / (np.sum(sv ** 2) + 1e-12))}


def net_diagnostics(model, x_seq, device='cpu', max_steps=None):
    """Bundle: raster + spike_stats + effective_rank(attivita') + recurrence_spectral. Ritorna dict + raster."""
    raster = spike_raster(model, x_seq, device=device, max_steps=max_steps)
    out = {**spike_stats(raster), 'eff_rank_activity': effective_rank(raster), **recurrence_spectral(model)}
    return out, raster
