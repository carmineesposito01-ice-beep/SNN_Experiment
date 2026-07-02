"""utils/seu_inject.py -- Fase A FPGA (F4): Single Event Upset (bit-flip) sui pesi po2.

Sul target FPGA ogni peso sinaptico e' memorizzato come 4 bit: 1 SEGNO + 3 ESPONENTE-offset
(esp in [-4,1] -> offset 0..5; offset >=6 = valore 0). Un SEU inverte 1 bit -> cambia segno
o esponente del peso. Qui:
  * codec peso<->4bit  (encode_po2 / decode_bits / flip_bit);
  * sensitivity_map    (metrica CHEAP = delta errore di identificazione, 1 forward/flip)
                       -> heatmap peso x posizione-bit;
  * collision_vs_flips (metrica di SICUREZZA = collision_rate via eval_safety, Monte Carlo,
                       costo limitato);
  * bit_criticality / hidden_vs_readout (aggregati per la figura seu_sensitivity, sezione 07).

Iniezione FEDELE: si disabilita la ri-quantizzazione (PO2_ENABLED=0) e si scrive il valore
po2 decodificato-DOPO-flip direttamente nel peso raw, cosi' il forward usa il codice "guasto"
come lo leggerebbe l'hardware (nessun clamp che riassorbe il flip). Ripristino garantito
(context manager). Gestisce baseline ed eventprop (naming pesi via weight_profiler).
"""
import os
import numpy as np
import torch

from core.hardware import po2_quantize
from utils.weight_profiler import weight_matrices, PO2_EXP_MIN, PO2_EXP_MAX

SIGN_BIT = 3
MAX_OFFSET = PO2_EXP_MAX - PO2_EXP_MIN       # 5 (esp 1 -> offset 5)
ZERO_CODE = 0b0110                            # offset 6, sign 0 -> valore 0 (sotto soglia)
BIT_LABELS = ['exp_LSB', 'exp_mid', 'exp_MSB', 'segno']   # bit 0..3
PARAM_SCALE = np.array([33.3, 1.2, 2.5, 1.1, 1.5], dtype=np.float64)   # scale fisiche [v0,T,s0,a,b]


# ---------------------------------------------------------------- codec 4-bit
def encode_po2(value):
    """Valore po2 -> codice 4 bit (segno<<3 | offset). 0/non-finito -> ZERO_CODE."""
    if value == 0 or not np.isfinite(value):
        return ZERO_CODE
    sign = 1 if value < 0 else 0
    exp = int(np.clip(round(float(np.log2(abs(value)))), PO2_EXP_MIN, PO2_EXP_MAX))
    return (sign << SIGN_BIT) | (exp - PO2_EXP_MIN)


def decode_bits(code):
    """Codice 4 bit -> valore po2. offset > 5 -> 0."""
    sign = (code >> SIGN_BIT) & 1
    offset = code & 0b111
    if offset > MAX_OFFSET:
        return 0.0
    return (-1.0 if sign else 1.0) * (2.0 ** (PO2_EXP_MIN + offset))


def flip_bit(code, bit):
    """Inverte il bit `bit` (0..3) del codice."""
    return code ^ (1 << bit)


def _po2_hw(t):
    """po2-quantizza col quantizzatore HW (clamp[-4,1]+mask), forzando PO2 abilitato."""
    prev = os.environ.get('PO2_ENABLED')
    os.environ['PO2_ENABLED'] = '1'
    try:
        with torch.no_grad():
            return po2_quantize(t.detach()).detach().cpu().numpy().astype(np.float64)
    finally:
        if prev is None:
            os.environ.pop('PO2_ENABLED', None)
        else:
            os.environ['PO2_ENABLED'] = prev


# -------------------------------------------------- sessione di iniezione fedele
class InjectionSession:
    """Context manager: PO2 off + pesi = valori po2 memorizzati; flip per-elemento; ripristino."""

    def __init__(self, model):
        self.model = model
        _, mats = weight_matrices(model)
        self.entries = {}      # name -> {'param', 'orig', 'po2'(flat np)}
        for name, p in mats.items():
            self.entries[name] = {'param': p, 'orig': p.detach().clone(),
                                  'po2': _po2_hw(p).reshape(-1)}
        self.catalog = [(n, i) for n, e in self.entries.items() for i in range(e['po2'].size)]

    def __enter__(self):
        self._prev_env = os.environ.get('PO2_ENABLED')
        os.environ['PO2_ENABLED'] = '0'                    # forward usa i raw as-is
        with torch.no_grad():
            for e in self.entries.values():
                e['param'].data.copy_(torch.as_tensor(
                    e['po2'], dtype=e['param'].dtype).reshape(e['param'].shape))
        return self

    def __exit__(self, *a):
        with torch.no_grad():
            for e in self.entries.values():
                e['param'].data.copy_(e['orig'])
        if self._prev_env is None:
            os.environ.pop('PO2_ENABLED', None)
        else:
            os.environ['PO2_ENABLED'] = self._prev_env
        return False

    def code_at(self, name, flat_idx):
        return encode_po2(float(self.entries[name]['po2'][flat_idx]))

    def set_element(self, name, flat_idx, value):
        with torch.no_grad():
            self.entries[name]['param'].data.view(-1)[flat_idx] = float(value)

    def restore_element(self, name, flat_idx):
        self.set_element(name, flat_idx, float(self.entries[name]['po2'][flat_idx]))


# ---------------------------------------------------------------- analisi F4
def sensitivity_map(model, x_win, per_matrix_sample=16, seed=0):
    """Heatmap sensibilita' peso x bit (delta relativo dei 5 param identificati per ogni flip).

    x_win: (1,T,4). Campiona fino a per_matrix_sample pesi per matrice. Metrica cheap
    (1 forward/flip). Ritorna base_params, righe per peso, e la matrice heatmap (n_pesi x 4).
    """
    from scripts.closed_loop_identify import identify
    x = torch.as_tensor(x_win, dtype=torch.float32)
    if x.ndim == 2:
        x = x[None]
    rng = np.random.default_rng(seed)
    rows = []
    with InjectionSession(model) as inj:
        base = np.asarray(identify(model, x), dtype=np.float64)
        for name, e in inj.entries.items():
            n = e['po2'].size
            idxs = rng.choice(n, size=min(per_matrix_sample, n), replace=False)
            for fi in idxs:
                code = inj.code_at(name, int(fi))
                errs = []
                for bit in range(4):
                    inj.set_element(name, int(fi), decode_bits(flip_bit(code, bit)))
                    p_new = np.asarray(identify(model, x), dtype=np.float64)
                    inj.restore_element(name, int(fi))
                    errs.append(float(np.mean(np.abs(p_new - base) / PARAM_SCALE)))
                rows.append({'matrix': name, 'flat_idx': int(fi), 'code': int(code),
                             'bit0': errs[0], 'bit1': errs[1], 'bit2': errs[2], 'bit3': errs[3]})
    heatmap = np.array([[r['bit0'], r['bit1'], r['bit2'], r['bit3']] for r in rows]) \
        if rows else np.zeros((0, 4))
    return {'base_params': base.tolist(), 'rows': rows, 'heatmap': heatmap}


def bit_criticality(sens):
    """Sensibilita' media per posizione-bit (quali bit dominano il rischio -> ECC mirata)."""
    hm = sens['heatmap']
    if hm.size == 0:
        return {}
    return {BIT_LABELS[b]: float(hm[:, b].mean()) for b in range(4)}


def hidden_vs_readout(sens):
    """Sensibilita' media hidden (fc/rec_U/rec_V) vs readout (out) -> dove mettere il TMR."""
    hid, out = [], []
    for r in sens['rows']:
        v = float(np.mean([r['bit0'], r['bit1'], r['bit2'], r['bit3']]))
        (out if r['matrix'] == 'out' else hid).append(v)
    return {'hidden_mean': float(np.mean(hid)) if hid else float('nan'),
            'readout_mean': float(np.mean(out)) if out else float('nan')}


def collision_vs_flips(model, cache, n_flips_list=(1, 2, 4, 8), n_mc=20,
                       n_drivers=8, seq_len=50, seed=0, device='cpu'):
    """collision_rate closed-loop vs numero di SEU simultanei (Monte Carlo).

    Baseline (0 flip) + per ogni livello n_flips, n_mc realizzazioni casuali (peso, bit).
    Usa eval_safety -> costo = (1 + len(n_flips_list)*n_mc) valutazioni. Ritorna righe pronte
    per la curva degrade_vs_flips (sezione 07). Quanti SEU prima dell'insicurezza -> scrubbing.
    """
    from scripts.closed_loop_identify import eval_safety
    rng = np.random.default_rng(seed)
    rows = []
    with InjectionSession(model) as inj:
        base = eval_safety(model, cache, n_drivers=n_drivers, seq_len=seq_len, device=device)
        base_cr = float(base['snn']['collision_rate'])
        rows.append({'n_flips': 0, 'collision_rate_mean': base_cr, 'collision_rate_std': 0.0, 'n_mc': 1})
        for nf in n_flips_list:
            crs = []
            for _ in range(n_mc):
                picks = [inj.catalog[j] for j in rng.choice(len(inj.catalog), size=int(nf), replace=False)]
                for name, fi in picks:
                    inj.set_element(name, fi, decode_bits(flip_bit(inj.code_at(name, fi),
                                                                   int(rng.integers(0, 4)))))
                res = eval_safety(model, cache, n_drivers=n_drivers, seq_len=seq_len, device=device)
                crs.append(float(res['snn']['collision_rate']))
                for name, fi in picks:
                    inj.restore_element(name, fi)
            rows.append({'n_flips': int(nf), 'collision_rate_mean': float(np.mean(crs)),
                         'collision_rate_std': float(np.std(crs)), 'n_mc': int(n_mc)})
    return {'baseline_collision_rate': base_cr, 'rows': rows}
