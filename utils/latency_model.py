"""utils/latency_model.py -- Fase A FPGA (F5): conteggio operazioni + WCET.

Separa i CONTEGGI GREZZI (questo modulo) dalla monetizzazione in pJ
(utils/snn_showcase.energy_estimate) e in cicli/us (qui). Rispetto al solo
conteggio sinaptico:
  * contabilizza le op NON-sinaptiche (leak, fatica, reset, confronto-soglia);
  * modella la cascata ricorrente V->U come 2 STADI SERIALI (rec_int = V@s poi
    rec_curr = U@rec_int -- non sovrapponibili, dipendenza dati);
  * distingue worst-case (denso / tutti gli spike) da tipico (gated da spike_rate).

Tutto ANALITICO dalle shape dei pesi (nessun forward). I numeri in cicli/us/mW sono
STIME di progetto (STIMA), non misure di silicio: veri SE l'RTL segue questo datapath.
Deriva le shape dai pesi -> robusto a baseline vs eventprop.
"""
import math

from utils.weight_profiler import weight_matrices

# Op non-sinaptiche per neurone e per tick (dal forward reale di ALIFCell/LICell):
#   ALIF: leak(1 shift +1 sub) + integra(2 add) + soglia-eff(1 add) + confronto(1) +
#         fatica(1 shift +1 sub +1 mul +1 add) + soft-reset(1 mul +1 sub) ~= 12
#   LI:   leak(1 shift +1 sub) + integra(1 add) ~= 3
NONSYN_PER_HIDDEN = 12
NONSYN_PER_OUT = 3

DEADLINE_MS = 100.0          # un'inferenza per passo di controllo (DT = 0.1 s)
FMAX_PROFILES_MHZ = (100.0, 150.0, 200.0)
DSE_UNITS = {'serial': 1, '8-unit': 8, '32-unit': 32, 'full-unroll': None}  # None = 1 ciclo/stadio


def model_shapes(model):
    """(IN, H, R, O, max_delay, n_ticks) derivati dai pesi -> robusto a entrambe le famiglie."""
    hid, mats = weight_matrices(model)
    fc = mats['fc']
    H, IN = int(fc.shape[0]), int(fc.shape[1])
    R = int(mats['rec_U'].shape[1]) if 'rec_U' in mats else 0
    O = int(mats['out'].shape[0]) if 'out' in mats else 0
    delays = getattr(hid, 'delays', None)
    max_delay = (int(delays.max().item()) + 1) if delays is not None and delays.numel() else \
        int(getattr(hid, 'max_delay', 1) or 1)
    n_ticks = int(getattr(model, 'n_ticks', None) or getattr(hid, 'n_ticks', None) or 10)
    return {'IN': IN, 'H': H, 'R': R, 'O': O, 'max_delay': max_delay, 'n_ticks': n_ticks}


def op_count(model, spike_rate=None):
    """Conteggio operazioni per PASSO (n_ticks tick interni), per componente del datapath.

    Ritorna worst-case (denso / tutti attivi) e, se spike_rate in [0,1] e' dato, tipico
    (le componenti guidate dagli spike -- rec_V, out -- scalate da spike_rate).
    Le componenti:
      input_syn : fc (H*IN)          -- input continuo, denso (NON gated)
      rec_V     : V@prev_spike (R*H) -- stadio 1, gated dagli spike hidden
      rec_U     : U@rec_int  (H*R)   -- stadio 2, rec_int e' denso (NON gated)
      out_syn   : readout (O*H)      -- gated dagli spike hidden
      nonsyn    : H*NONSYN_HIDDEN + O*NONSYN_OUT
    """
    s = model_shapes(model)
    H, IN, R, O, nt = s['H'], s['IN'], s['R'], s['O'], s['n_ticks']
    comp_wc = {
        'input_syn': H * IN,
        'rec_V': R * H,
        'rec_U': H * R,
        'out_syn': O * H,
        'nonsyn': H * NONSYN_PER_HIDDEN + O * NONSYN_PER_OUT,
    }
    per_step_wc = {k: v * nt for k, v in comp_wc.items()}
    syn_wc = sum(per_step_wc[k] for k in ('input_syn', 'rec_V', 'rec_U', 'out_syn'))
    out = {
        'shapes': s,
        'per_tick_worstcase': comp_wc,
        'per_step_worstcase': per_step_wc,
        'synaptic_ac_per_step_worstcase': syn_wc,
        'nonsyn_per_step': per_step_wc['nonsyn'],
    }
    if spike_rate is not None:
        r = float(spike_rate)
        comp_typ = dict(comp_wc)
        comp_typ['rec_V'] = comp_wc['rec_V'] * r      # gated dagli spike
        comp_typ['out_syn'] = comp_wc['out_syn'] * r
        per_step_typ = {k: v * nt for k, v in comp_typ.items()}
        out['spike_rate'] = r
        out['per_step_typical'] = per_step_typ
        out['synaptic_ac_per_step_typical'] = sum(
            per_step_typ[k] for k in ('input_syn', 'rec_V', 'rec_U', 'out_syn'))
    return out


def wcet_cycles(counts, n_units, fmax_mhz=100.0):
    """Cicli e us per PASSO con n_units corsie shift-add in serial-reuse.

    Per tick gli stadi girano in sequenza (cascata dati): input -> rec_V -> rec_U ->
    out -> non-sinaptico; ogni stadio impiega ceil(ops/n_units) cicli. n_units=None
    (full-unroll) = 1 ciclo per stadio. Ritorna cicli/passo, us/passo, margine vs deadline.
    """
    pt = counts['per_tick_worstcase']
    nt = counts['shapes']['n_ticks']
    stages = ('input_syn', 'rec_V', 'rec_U', 'out_syn', 'nonsyn')
    if n_units is None:
        cyc_tick = len(stages)                                  # 1 ciclo/stadio
    else:
        cyc_tick = sum(math.ceil(pt[s] / n_units) for s in stages)
    cyc_step = cyc_tick * nt
    us_step = cyc_step / fmax_mhz                                # cicli / (MHz) = us
    return {
        'n_units': n_units,
        'fmax_mhz': fmax_mhz,
        'cycles_per_tick': cyc_tick,
        'cycles_per_step': cyc_step,
        'us_per_step': us_step,
        'deadline_us': DEADLINE_MS * 1000.0,
        'margin_x': (DEADLINE_MS * 1000.0) / us_step if us_step > 0 else float('inf'),
        'utilization_pct': 100.0 * us_step / (DEADLINE_MS * 1000.0),
    }


def dse_profiles(model, spike_rate=None, fmax_mhz=100.0):
    """Sweep DSE: per ogni profilo di parallelismo (serial/8/32/full-unroll) i cicli/us/margine.
    Base della figura latency_dse (Pareto area<->latenza). I numeri sono STIME di progetto.
    """
    counts = op_count(model, spike_rate=spike_rate)
    rows = []
    for name, units in DSE_UNITS.items():
        w = wcet_cycles(counts, units, fmax_mhz=fmax_mhz)
        rows.append({'profile': name, 'n_units': units, **{k: w[k] for k in
                    ('cycles_per_step', 'us_per_step', 'margin_x', 'utilization_pct')}})
    return {'counts': counts, 'profiles': rows, 'fmax_mhz': fmax_mhz}
