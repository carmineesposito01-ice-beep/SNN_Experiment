"""Dynamic_Study L1 — la rete addestrata USA la sua memoria ricorrente per a/b?

Due esperimenti sul checkpoint esistente (NIENTE training):
  EXP1  Ablazione della memoria: NRMSE per-canale con stato ricorrente PROPAGATO (normale)
        vs stato RESETTATO a ogni step (memoryless). Se a/b peggiorano molto senza memoria,
        la rete la usa; se non cambiano, non la usa (-> il collo e' altrove).
  EXP2  Decadimento: NRMSE(a,b) in funzione di "step dall'ultimo transitorio" (accel/brake).
        Cresce con la distanza -> memoria leaky (porta l'info ma la dimentica); piatto-alto ->
        non usa memoria; piatto-basso -> memoria forte.

Genera Dynamic_Study_L1.ipynb. Checkpoint solo su Azure -> celle col modello saltano se assente.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cell(src, cid, ctype='code'):
    c = {'cell_type': ctype, 'id': cid, 'metadata': {}, 'source': src}
    if ctype == 'code':
        c['execution_count'] = None
        c['outputs'] = []
    return c


INTRO = """# Dynamic_Study L1 — la rete usa la memoria ricorrente per a/b?

Niente training: solo il checkpoint `LS3_PEAK_R0_launch_d03`. Due esperimenti:
1. **Ablazione memoria** — NRMSE per-canale con stato propagato (normale) vs resettato a ogni step.
2. **Decadimento** — NRMSE(a,b) vs step dall'ultimo transitorio.

Esito -> decide se la leva e' la **ritenzione** (memoria) o il **gap-SNN** al contesto attuale.
Output in `results/Dynamic_Study/L1/`. Push automatico finale.
"""

ENV = """# Cell 1 -- ENV
import sys, os, subprocess
import importlib.util as _imu
RESULTS = 'results/Dynamic_Study/L1'
BRANCH = 'Dynamic_Study'
os.makedirs(RESULTS, exist_ok=True)
for pkg in ['pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
print('[L1] ENV OK | branch =', br)
"""

LOAD = """# Cell 2 -- carica checkpoint + dataset di validazione
import os, torch, numpy as np
from core.network import build_model
from data.generator import generate_dataset
from train import CFDataset
from torch.utils.data import DataLoader
from config import SEED

CKPT = 'checkpoints/LS3_PEAK_R0_launch_d03/best_model.pt'
PN = ['v0', 'T', 's0', 'a', 'b']
model = None
if os.path.isfile(CKPT):
    ck = torch.load(CKPT, map_location='cpu', weights_only=False)
    model = build_model(variant='baseline', hidden_size=32, rank=8, max_delay=6, bit_shift=3)
    model.load_state_dict(ck['model_state']); model.eval()
    RANGE = (model.param_hi - model.param_lo).detach().cpu().numpy()  # [37,2,4,2.2,2.5]
    print('[OK] modello', sum(p.numel() for p in model.parameters()), 'param | range', np.round(RANGE, 2))
else:
    print('[skip] checkpoint assente:', CKPT, '-> esegui su Azure')

if model is not None:
    val_data = generate_dataset(120, base_seed=SEED + 99)
    ds = CFDataset(val_data, seq_len=100, stride=100)
    dl = DataLoader(ds, batch_size=64, shuffle=False)
    print('[dataset] finestre:', len(ds), '| batch:', len(dl))
"""

HELP = """# Cell 3 -- helper: forward normale vs ablato + NRMSE per-canale
import torch, numpy as np
_NR_GT_IDX = {'v0': 0, 's0': 1, 'a': 2, 'b': 3}   # colonna in params_gt (T escluso)

def forward_ablated(model, x):
    # reset dello stato ricorrente PRIMA di ogni step -> nessuna memoria cross-step
    B, T, _ = x.shape
    out = []
    for t in range(T):
        model.reset_state(B, x.device)
        out.append(model.forward_step(x[:, t, :]).unsqueeze(1))
    return torch.cat(out, dim=1)

def accumulate_nrmse(ps, y, mask, pgt, se, n):
    # T: GT per-timestep (masked); v0/s0/a/b: GT costante in params_gt
    se['T'] += (mask * (ps[:, :, 1] - y[:, :, 1]) ** 2).sum().item(); n['T'] += mask.sum().item()
    for p, gi in _NR_GT_IDX.items():
        pi = PN.index(p); gt = pgt[:, gi].unsqueeze(1)
        se[p] += ((ps[:, :, pi] - gt) ** 2).sum().item(); n[p] += ps[:, :, pi].numel()

def finalize(se, n):
    return {p: float(np.sqrt(se[p] / max(n[p], 1)) / RANGE[PN.index(p)]) for p in PN}
"""

EXP1 = """# Cell 4 -- EXP1: ablazione della memoria (normale vs stato resettato a ogni step)
import torch, numpy as np, pandas as pd, matplotlib.pyplot as plt
from IPython.display import display, Markdown
if model is not None:
    se_n = {p: 0.0 for p in PN}; n_n = {p: 0 for p in PN}
    se_a = {p: 0.0 for p in PN}; n_a = {p: 0 for p in PN}
    with torch.no_grad():
        for x, y, mask, pgt in dl:
            ps_norm = model.forward_sequence(x)        # stato propagato (memoria attiva)
            ps_abl = forward_ablated(model, x)         # stato resettato (memoria spenta)
            accumulate_nrmse(ps_norm, y, mask, pgt, se_n, n_n)
            accumulate_nrmse(ps_abl, y, mask, pgt, se_a, n_a)
    nrmse_norm = finalize(se_n, n_n); nrmse_abl = finalize(se_a, n_a)
    df1 = pd.DataFrame({'normale (memoria)': nrmse_norm, 'ablato (no memoria)': nrmse_abl})
    df1['guadagno_memoria'] = df1['ablato (no memoria)'] - df1['normale (memoria)']
    df1.to_csv(RESULTS + '/l1_ablation.csv')
    x_ = np.arange(len(PN)); w = 0.38
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x_ - w/2, [nrmse_norm[p] for p in PN], w, label='normale (memoria attiva)', color='tab:green')
    ax.bar(x_ + w/2, [nrmse_abl[p] for p in PN], w, label='ablato (stato resettato/step)', color='tab:red')
    ax.set_xticks(x_); ax.set_xticklabels(PN); ax.set_ylabel('NRMSE = RMSE / range')
    ax.set_title('EXP1 - Ablazione memoria: se ablato >> normale la rete USA la ricorrenza')
    ax.legend(); ax.grid(alpha=0.3, axis='y')
    plt.tight_layout(); plt.savefig(RESULTS + '/l1_ablation.png', dpi=130); plt.show()
    display(Markdown('## EXP1 - guadagno della memoria per canale (ablato - normale)'))
    display(df1.round(3))
    gain_ab = 0.5 * (df1.loc['a', 'guadagno_memoria'] + df1.loc['b', 'guadagno_memoria'])
    print('guadagno memoria medio su a,b =', round(gain_ab, 3))
else:
    print('[skip] modello assente'); nrmse_norm = None
"""

EXP2 = """# Cell 5 -- EXP2: decadimento NRMSE(a,b) vs step dall'ultimo transitorio
import torch, numpy as np, pandas as pd, matplotlib.pyplot as plt
from IPython.display import display, Markdown
if model is not None:
    # transitorio = forte accel/brake (|v_dot|>0.5) o avvicinamento (|dv|>1.0).
    # Layout: y[:,:,0]=v_dot (fisico), y[:,:,1]=T; x[:,:,2]=dv NORMALIZZATO -> dv_fis=(dv_n-0.5)*2*NORM_DV_MAX
    from config import NORM_DV_MAX
    bins = [(0, 0), (1, 2), (3, 5), (6, 10), (11, 20), (21, 9999)]
    blab = ['0', '1-2', '3-5', '6-10', '11-20', '21+']
    se_a = np.zeros(len(bins)); se_b = np.zeros(len(bins)); cnt = np.zeros(len(bins))
    ia, ib = PN.index('a'), PN.index('b')
    with torch.no_grad():
        for x, y, mask, pgt in dl:
            ps = model.forward_sequence(x).numpy()
            yv = y.numpy(); xv = x.numpy(); B, T, _ = yv.shape
            dv_phys = (xv[:, :, 2] - 0.5) * 2.0 * NORM_DV_MAX
            transient = (np.abs(yv[:, :, 0]) > 0.5) | (np.abs(dv_phys) > 1.0)
            sst = np.full((B, T), 9999, dtype=np.int64)     # steps since last transient (causale)
            for b in range(B):
                c = 9999
                for t in range(T):
                    c = 0 if transient[b, t] else c + 1
                    sst[b, t] = c
            ea = (ps[:, :, ia] - pgt.numpy()[:, 2:3]) ** 2
            eb = (ps[:, :, ib] - pgt.numpy()[:, 3:4]) ** 2
            for j, (lo, hi) in enumerate(bins):
                m = (sst >= lo) & (sst <= hi)
                se_a[j] += ea[m].sum(); se_b[j] += eb[m].sum(); cnt[j] += m.sum()
    nrmse_a = np.sqrt(se_a / np.maximum(cnt, 1)) / RANGE[ia]
    nrmse_b = np.sqrt(se_b / np.maximum(cnt, 1)) / RANGE[ib]
    df2 = pd.DataFrame({'bin_step_da_transitorio': blab, 'n': cnt.astype(int),
                        'nrmse_a': nrmse_a.round(3), 'nrmse_b': nrmse_b.round(3)})
    df2.to_csv(RESULTS + '/l1_decay.csv', index=False)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(range(len(bins)), nrmse_a, 'o-', color='tab:red', label='a')
    ax.plot(range(len(bins)), nrmse_b, 's-', color='tab:purple', label='b')
    ax.set_xticks(range(len(bins))); ax.set_xticklabels(blab)
    ax.set_xlabel('step dall\\'ultimo transitorio (accel/brake)'); ax.set_ylabel('NRMSE = RMSE / range')
    ax.set_title('EXP2 - decadimento: NRMSE(a,b) cresce lontano dai transitori? (leaky vs forte)')
    ax.legend(); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(RESULTS + '/l1_decay.png', dpi=130); plt.show()
    display(Markdown('## EXP2 - NRMSE(a,b) vs distanza dal transitorio'))
    display(df2)
else:
    print('[skip] modello assente')
"""

VERDICT = """# Cell 6 -- verdetto + push
import json, subprocess, os
if model is not None:
    gain_ab = 0.5 * ((nrmse_abl['a'] - nrmse_norm['a']) + (nrmse_abl['b'] - nrmse_norm['b']))
    rise_a = float(nrmse_a[-1] - nrmse_a[0]); rise_b = float(nrmse_b[-1] - nrmse_b[0])
    v = []
    if gain_ab < 0.02:
        v.append('Memoria POCO USATA su a/b (guadagno %.3f): la rete predice quasi context-free '
                 '-> leva = far USARE la ricorrenza (loss per-regime/latch) NON allungare seq_len.' % gain_ab)
    else:
        v.append('Memoria USATA su a/b (guadagno %.3f): la ricorrenza contribuisce.' % gain_ab)
    if rise_a > 0.03 or rise_b > 0.03:
        v.append('NRMSE(a,b) CRESCE lontano dai transitori (a +%.3f, b +%.3f): memoria LEAKY '
                 '-> la ritenzione (canale lento) puo aiutare.' % (rise_a, rise_b))
    else:
        v.append('NRMSE(a,b) PIATTO vs distanza dal transitorio: niente decadimento da memoria '
                 '-> il collo e il gap-SNN al contesto attuale, non la ritenzione.')
    out = {'nrmse_normal': nrmse_norm, 'nrmse_ablated': nrmse_abl, 'gain_ab': gain_ab,
           'decay_nrmse_a': [float(x) for x in nrmse_a], 'decay_nrmse_b': [float(x) for x in nrmse_b],
           'verdict': v}
    json.dump(out, open(RESULTS + '/l1_results.json', 'w'), indent=2)
    print('VERDETTO L1:')
    for s in v:
        print(' -', s)
    subprocess.run(['git', 'add', RESULTS], capture_output=True)
    r = subprocess.run(['git', 'commit', '-m', 'Dynamic_Study L1: ablazione memoria + decadimento (a/b)'],
                       capture_output=True, text=True)
    print(r.stdout[-200:] if r.returncode == 0 else r.stderr[-200:])
    subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True)
    subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
    print('L1 pushed.')
else:
    print('[skip] niente da pushare (checkpoint assente)')
"""


def main():
    cells = [cell(INTRO, 'intro', 'markdown'),
             cell(ENV, 'env'), cell(LOAD, 'load'), cell(HELP, 'help'),
             cell(EXP1, 'exp1'), cell(EXP2, 'exp2'), cell(VERDICT, 'verdict')]
    nb = {'cells': cells,
          'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                       'language_info': {'name': 'python', 'version': '3.x'}},
          'nbformat': 4, 'nbformat_minor': 5}
    out = os.path.join(ROOT, 'Dynamic_Study_L1.ipynb')
    json.dump(nb, open(out, 'w', encoding='utf-8'), indent=1)
    print('Wrote', out)


if __name__ == '__main__':
    main()
