"""utils/snn_showcase.py — Vetrina neuromorfica della SNN durante la guida closed-loop.

Cattura l'attivita' spiking per-neurone (raster) durante uno scenario, stima il consumo
energetico SNN (event-driven, SynOps x E_AC) vs una ANN equivalente (dense, MAC x E_MAC),
e fornisce le quantita' neuromorfiche da mostrare (spike rate, sparsita', SynOps, energia,
vantaggio). Riferimenti energia: Horowitz 2014 (45nm). NB: STIMA trasparente, non misura HW.

Per FPGA/Po2 (target PYNQ-Z1) l'AC e' uno shift-add -> ancora piu' economico dell'E_AC FP32.
"""
import numpy as np
import torch

from config import (NORM_S_MAX, NORM_V_MAX, NORM_DV_MAX, NORM_VL_MAX, DT,
                    ACC_AL_TAU, ACC_COOLNESS)
from core.network import CF_FSNN_Net

# Energia per operazione [pJ] — Horowitz 2014, 45nm (ampiamente citato in letteratura SNN)
E_MAC_FP32 = 4.6   # multiply-accumulate 32b float (operazione ANN densa)
E_AC_FP32  = 0.9   # accumulate/add 32b float (operazione SNN, guidata da spike)


def capture_run(model, params_gt, v_leader, s_init, v_init, cut_in=None, device='cpu'):
    """Come closed_loop_eval.simulate() ma CATTURA gli spike per-neurone del layer hidden.

    Ritorna (traj: dict serie temporali, spikes: array (T, H) = conteggio spike per neurone
    per timestep, sommato sui n_ticks tick interni dello step).
    """
    from utils.closed_loop_eval import _norm_obs
    H = model.hidden_size
    captured = []

    def _hook(mod, inp, out):
        captured.append(out.detach().view(-1).cpu().numpy())   # (H,) vettore spike per tick

    handle = model.layer_hidden.register_forward_hook(_hook)
    model.eval(); model.reset_state(1, device)
    alpha_al = float(np.exp(-DT / ACC_AL_TAU)); a_l_filt = 0.0; vl_prev = float(v_leader[0])
    s = float(s_init); v = float(v_init)
    series = {k: [] for k in ('s', 'v', 'vl', 'dv', 'a_ego')}
    spikes_per_step = []
    collided = False
    try:
        with torch.no_grad():
            for t in range(len(v_leader)):
                if cut_in is not None and t == int(cut_in[0]):
                    s = float(cut_in[1])
                vl = float(v_leader[t]); dv = v - vl
                captured.clear()
                params = model.forward_step(_norm_obs(s, v, dv, vl).to(device))
                sp = np.sum(captured, axis=0) if captured else np.zeros(H)   # spike/neurone in questo step
                spikes_per_step.append(sp)
                a_l_raw = (vl - vl_prev) / DT
                a_l_filt = alpha_al * a_l_filt + (1.0 - alpha_al) * a_l_raw; vl_prev = vl
                a_ego = float(CF_FSNN_Net.acc_iidm_accel(
                    torch.tensor([max(s, 1e-3)]), torch.tensor([v]), torch.tensor([dv]),
                    torch.tensor([a_l_filt]), params, coolness=ACC_COOLNESS)[0])
                for k, val in zip(('s', 'v', 'vl', 'dv', 'a_ego'), (s, v, vl, dv, a_ego)):
                    series[k].append(val)
                v = max(0.0, v + a_ego * DT); s = s + (vl - v) * DT
                if s <= 0.0:
                    collided = True; break
    finally:
        handle.remove()
    traj = {k: np.asarray(val) for k, val in series.items()}
    traj['collided'] = collided
    return traj, np.asarray(spikes_per_step)            # (T, H)


def energy_estimate(spikes, model):
    """Stima energetica SNN (event-driven) vs ANN equivalente (dense). Trasparente.

    spikes: (T, H) conteggi spike per neurone per timestep.
    Modello ANN equivalente (stessa topologia, ma MAC densi ogni step):
      MAC/step = input(4*H) + recurrent low-rank(2*H*r) + output(5*H).
    SNN: input denso (Po2->AC) sempre + recurrent/output guidati da spike (AC, fanout ~ r+5).
    """
    T, H = spikes.shape
    r = int(model.rank)
    n_ticks = int(getattr(model, 'n_ticks', 1))
    total_spikes = float(spikes.sum())

    ann_macs = T * (4 * H + 2 * H * r + 5 * H)
    snn_static_ac = T * 4 * H                    # input fc, denso ogni step (Po2 = shift-add)
    snn_dynamic_ac = total_spikes * (r + 5)      # synaptic ops guidate da spike (fanout ~ rank+output)
    snn_ac = snn_static_ac + snn_dynamic_ac

    e_ann = ann_macs * E_MAC_FP32                # pJ
    e_snn = snn_ac * E_AC_FP32                   # pJ
    return {
        'T': T, 'H': H, 'rank': r,
        'total_spikes': total_spikes,
        'mean_spike_rate_pct': 100.0 * total_spikes / (T * H * n_ticks),
        'active_neuron_frac': float((spikes.sum(axis=0) > 0).mean()),
        'ann_macs': int(ann_macs), 'snn_synops': int(snn_ac),
        'E_ann_nJ': e_ann / 1e3, 'E_snn_nJ': e_snn / 1e3,
        'energy_advantage_x': e_ann / max(e_snn, 1e-9),
    }
