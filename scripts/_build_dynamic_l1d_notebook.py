"""Dynamic_Study L1d — il memoryless DISCRIMINA a/b per-driver o e' solo un prior meglio centrato?

L1c ha mostrato che ne' memory ne' memoryless decodificano a/b dal transitorio (emettono una
quasi-costante per finestra). Domanda decisiva: la quasi-costante VARIA col driver (= discrimina)
o e' la stessa per tutti (= prior)? Niente training, solo il checkpoint.

Per ogni finestra (un driver-scenario, a/b GT costanti): media la predizione sui 100 step ->
1 punto. Scatter (pred medio) vs (GT) su molti driver, per memory e memoryless, per v0/s0/a/b
(v0/s0 come riferimento: piu' osservabili). Metriche: Pearson r, pendenza, frazione di varianza
spiegata r^2, rapporto std(pred)/std(GT).

  r ~ 0, pendenza ~ 0  -> la rete emette un PRIOR (il win memoryless e' solo bias-centering).
  r > 0, pendenza > 0  -> DISCRIMINAZIONE reale per-driver.

Genera Dynamic_Study_L1d.ipynb. Checkpoint solo su Azure -> celle col modello saltano se assente.
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


INTRO = """# Dynamic_Study L1d — memoryless: discriminazione per-driver o prior?

Niente training, solo `LS3_PEAK_R0_launch_d03`. L1c: ne' memory ne' memoryless decodificano a/b dal
transitorio (quasi-costante per finestra). Qui: quella costante **varia col driver** (discrimina) o
e' la stessa per tutti (prior)?

Per ogni finestra (driver-scenario, a/b GT costanti) medio la predizione sui 100 step -> 1 punto.
Scatter (pred) vs (GT) su molti driver, memory vs memoryless, per v0/s0/a/b. Metriche: Pearson r,
pendenza, r^2, std(pred)/std(GT). Output in `results/Dynamic_Study/L1d/`. Push automatico finale.
"""

ENV = """# Cell 1 -- ENV
import sys, os, subprocess
import importlib.util as _imu
RESULTS = 'results/Dynamic_Study/L1d'
BRANCH = 'Dynamic_Study'
os.makedirs(RESULTS, exist_ok=True)
for pkg in ['pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
print('[L1d] ENV OK | branch =', br)
"""

LOAD = """# Cell 2 -- checkpoint + dataset ampio (tanti driver diversi -> spread in GT)
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
    print('[OK] modello', sum(p.numel() for p in model.parameters()), 'param')
else:
    print('[skip] checkpoint assente:', CKPT, '-> esegui su Azure')

if model is not None:
    SEQ = 100
    val = generate_dataset(250, base_seed=SEED + 99)   # tanti scenari -> spread GT su a/b
    dl = DataLoader(CFDataset(val, seq_len=SEQ, stride=SEQ), batch_size=64, shuffle=False)
    print('[dataset] finestre:', len(dl.dataset))
"""

HELP = """# Cell 3 -- helper: forward ablato (memoryless)
import torch
def forward_ablated(m, x):
    B, T, _ = x.shape
    out = []
    for t in range(T):
        m.reset_state(B, x.device)
        out.append(m.forward_step(x[:, t, :]).unsqueeze(1))
    return torch.cat(out, dim=1)
"""

EXP = """# Cell 4 -- predizione media per-finestra (memory & memoryless) vs GT, per v0/s0/a/b
import torch, numpy as np, pandas as pd, matplotlib.pyplot as plt
from IPython.display import display, Markdown
if model is not None:
    PM, PA, GT = [], [], []
    with torch.no_grad():
        for x, y, mask, pgt in dl:
            PM.append(model.forward_sequence(x).mean(dim=1).numpy())   # (B,5) media sui 100 step
            PA.append(forward_ablated(model, x).mean(dim=1).numpy())   # (B,5)
            GT.append(pgt.numpy())                                     # (B,4) [v0,s0,a,b]
    PM = np.concatenate(PM); PA = np.concatenate(PA); GT = np.concatenate(GT)
    # mappa: (nome, col GT, col pred). pred: v0=0,T=1,s0=2,a=3,b=4 ; GT: v0=0,s0=1,a=2,b=3
    MAP = [('v0', 0, 0), ('s0', 1, 2), ('a', 2, 3), ('b', 3, 4)]

    def stats(gt, pr):
        r = float(np.corrcoef(gt, pr)[0, 1]) if gt.std() > 1e-9 and pr.std() > 1e-9 else 0.0
        slope = float(np.polyfit(gt, pr, 1)[0]) if gt.std() > 1e-9 else 0.0
        return r, slope, float(pr.std() / gt.std()) if gt.std() > 1e-9 else 0.0

    rows = []
    for name, gi, pi in MAP:
        gt = GT[:, gi]
        r_m, sl_m, sr_m = stats(gt, PM[:, pi])
        r_a, sl_a, sr_a = stats(gt, PA[:, pi])
        rows.append({'param': name, 'gt_std': round(float(gt.std()), 3),
                     'r_memory': round(r_m, 3), 'r2_memory': round(r_m**2, 3), 'slope_memory': round(sl_m, 3),
                     'r_memoryless': round(r_a, 3), 'r2_memoryless': round(r_a**2, 3),
                     'slope_memoryless': round(sl_a, 3), 'stdratio_memoryless': round(sr_a, 3)})
    dfr = pd.DataFrame(rows).set_index('param')
    dfr.to_csv(RESULTS + '/l1d_correlation.csv')
    display(Markdown('## L1d - correlazione pred-vs-GT per-driver (r=0 prior, r>0 discrimina)'))
    display(dfr)

    fig, axes = plt.subplots(2, 2, figsize=(12, 11))
    for ax, (name, gi, pi) in zip(axes.ravel(), MAP):
        gt = GT[:, gi]; pa = PA[:, pi]
        ax.scatter(gt, pa, s=14, alpha=0.4, color='tab:orange', label='memoryless')
        lo = min(gt.min(), pa.min()); hi = max(gt.max(), pa.max())
        ax.plot([lo, hi], [lo, hi], 'k--', lw=1, label='identita (pred=GT)')
        if gt.std() > 1e-9:
            c = np.polyfit(gt, pa, 1); xs = np.linspace(gt.min(), gt.max(), 50)
            ax.plot(xs, c[0]*xs + c[1], 'r-', lw=1.5, label='fit memoryless')
        r_a = float(np.corrcoef(gt, pa)[0, 1]) if gt.std() > 1e-9 and pa.std() > 1e-9 else 0.0
        ax.set_xlabel(name + ' GT'); ax.set_ylabel(name + ' predetto (memoryless)')
        ax.set_title('%s: r=%.2f, pendenza=%.2f' % (name, r_a, (np.polyfit(gt, pa, 1)[0] if gt.std() > 1e-9 else 0)))
        ax.legend(fontsize=7); ax.grid(alpha=0.3)
    fig.suptitle('L1d - discriminazione per-driver (memoryless): nuvola piatta=prior, allineata su fit=discrimina')
    fig.tight_layout(); fig.savefig(RESULTS + '/l1d_scatter.png', dpi=120); plt.show()
else:
    print('[skip] modello assente'); dfr = None
"""

VERDICT = """# Cell 5 -- verdetto + push
import json, subprocess
if model is not None:
    ra = float(dfr.loc['a', 'r_memoryless']); rb = float(dfr.loc['b', 'r_memoryless'])
    rv0 = float(dfr.loc['v0', 'r_memoryless']); rs0 = float(dfr.loc['s0', 'r_memoryless'])
    def lab(r):
        return 'PRIOR (nessuna discriminazione)' if abs(r) < 0.15 else \
               ('discriminazione DEBOLE' if abs(r) < 0.4 else 'discriminazione REALE')
    v = []
    v.append('a memoryless: r=%.2f (r2=%.2f) -> %s.' % (ra, ra*ra, lab(ra)))
    v.append('b memoryless: r=%.2f (r2=%.2f) -> %s.' % (rb, rb*rb, lab(rb)))
    v.append('riferimento osservabili: v0 r=%.2f (%s), s0 r=%.2f (%s).' % (rv0, lab(rv0), rs0, lab(rs0)))
    weak_ab = (abs(ra) < 0.4 and abs(rb) < 0.4)
    if abs(ra) < 0.15 and abs(rb) < 0.15:
        v.append('=> a/b sono un PRIOR: il win memoryless e\\' bias-centering, NON identificazione per-driver. '
                 'Per a/b reali serve training mirato (loss per-regime + encoding transitorio) O dichiararli '
                 'come prior con incertezza (uncertainty head). Deploy memoryless resta valido (NRMSE+sicurezza).')
    elif weak_ab:
        v.append('=> a/b discriminazione DEBOLE: il memoryless cattura un po\\' di segnale ma resta vicino al prior. '
                 'L2: uncertainty head + eventuale loss per-regime per rinforzare; deploy memoryless valido.')
    else:
        v.append('=> a/b DISCRIMINAZIONE REALE col memoryless: il win e\\' identificazione genuina, non solo prior. '
                 'L2 puo\\' limitarsi a uncertainty head; deploy memoryless forte.')
    out = {'r_a': ra, 'r_b': rb, 'r_v0': rv0, 'r_s0': rs0,
           'table': json.loads(dfr.to_json()), 'verdict': v}
    json.dump(out, open(RESULTS + '/l1d_results.json', 'w'), indent=2)
    print('VERDETTO L1d:')
    for s in v:
        print(' -', s)
    subprocess.run(['git', 'add', RESULTS], capture_output=True)
    r = subprocess.run(['git', 'commit', '-m', 'Dynamic_Study L1d: a/b prior vs discriminazione per-driver (scatter pred-vs-GT, memoryless vs memory)'],
                       capture_output=True, text=True)
    print(r.stdout[-200:] if r.returncode == 0 else r.stderr[-200:])
    subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True)
    subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
    print('L1d pushed.')
else:
    print('[skip] niente da pushare (checkpoint assente)')
"""


def main():
    cells = [cell(INTRO, 'intro', 'markdown'),
             cell(ENV, 'env'), cell(LOAD, 'load'), cell(HELP, 'help'),
             cell(EXP, 'exp'), cell(VERDICT, 'verdict')]
    nb = {'cells': cells,
          'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                       'language_info': {'name': 'python', 'version': '3.x'}},
          'nbformat': 4, 'nbformat_minor': 5}
    out = os.path.join(ROOT, 'Dynamic_Study_L1d.ipynb')
    json.dump(nb, open(out, 'w', encoding='utf-8'), indent=1)
    print('Wrote', out)


if __name__ == '__main__':
    main()
