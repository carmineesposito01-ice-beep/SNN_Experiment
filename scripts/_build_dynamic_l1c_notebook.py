"""Dynamic_Study L1c — PERCHE' la ricorrenza addestrata DANNEGGIA a/b?

L1/L1.5 hanno provato che lo stato propagato peggiora a (0.33 vs 0.15 memoryless), b, s0, v0.
Qui isoliamo il MECCANISMO (niente training, solo il checkpoint). Tre ipotesi:

  H1 ACCUMULO/DERIVA: lo stato ricorrente accumula una componente lenta dopo il reset ->
     il readout deriva (decode_offset e' calibrato solo vicino al reset -> sigmoid satura).
     Firma: NRMSE(a) CRESCE con la posizione-da-reset; il memoryless resta PIATTO.
  H2 CREEP ADATTAMENTO ALIF: la soglia adattativa sale nel tempo -> spike-rate cala ->
     il segnale del transitorio (dove vive 'a') si spegne. Firma: spike-rate decade con la
     posizione, correlato all'errore.
  H3 LOW-PASS/SMOOTHING: la ricorrenza filtra l'input -> il transitorio si smussa -> 'a'
     sottostimato. Firma: traccia 'a' predetta memory ATTENUATA vs memoryless ai transitori.

D1  Curve vs posizione-nella-finestra (steps da reset): NRMSE(a,b) mem vs memoryless, media
    predetta a/b (deriva?), spike-rate (creep?). -> discrimina H1 e H2.
D2  Traccia 'a' allineata sui transitori: memory vs memoryless vs |accel| reale. -> discrimina H3.

Genera Dynamic_Study_L1c.ipynb. Checkpoint solo su Azure -> celle col modello saltano se assente.
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


INTRO = """# Dynamic_Study L1c — perche' la ricorrenza danneggia a/b?

Niente training: solo `LS3_PEAK_R0_launch_d03`. Isoliamo il meccanismo dietro il finding L1
(stato propagato peggiora a/b/s0/v0). Tre ipotesi: **H1 accumulo/deriva**, **H2 creep adattamento
ALIF**, **H3 low-pass/smoothing**.

- **D1** — curve vs posizione-nella-finestra (steps da reset): NRMSE(a,b) mem vs memoryless,
  media predetta a/b (deriva), spike-rate (creep). Discrimina H1 e H2.
- **D2** — traccia 'a' allineata sui transitori: memory vs memoryless vs |accel|. Discrimina H3.

Output in `results/Dynamic_Study/L1c/`. Push automatico finale.
"""

ENV = """# Cell 1 -- ENV
import sys, os, subprocess
import importlib.util as _imu
RESULTS = 'results/Dynamic_Study/L1c'
BRANCH = 'Dynamic_Study'
os.makedirs(RESULTS, exist_ok=True)
for pkg in ['pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
print('[L1c] ENV OK | branch =', br)
"""

LOAD = """# Cell 2 -- checkpoint + dataset (stesso seed di L1 per comparabilita')
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
    RANGE = (model.param_hi - model.param_lo).detach().cpu().numpy()
    print('[OK] modello', sum(p.numel() for p in model.parameters()), 'param | range', np.round(RANGE, 2))
else:
    RANGE = None
    print('[skip] checkpoint assente:', CKPT, '-> esegui su Azure')

if model is not None:
    SEQ = 100
    val = generate_dataset(120, base_seed=SEED + 99)
    dl = DataLoader(CFDataset(val, seq_len=SEQ, stride=SEQ), batch_size=64, shuffle=False)
    print('[dataset] finestre:', len(dl.dataset), '| seq_len:', SEQ)
"""

HELP = """# Cell 3 -- helper: forward ablato (memoryless) per-canale
import torch
IA, IB = PN.index('a'), PN.index('b')

def forward_ablated(m, x):
    B, T, _ = x.shape
    out = []
    for t in range(T):
        m.reset_state(B, x.device)
        out.append(m.forward_step(x[:, t, :]).unsqueeze(1))
    return torch.cat(out, dim=1)
"""

D1 = """# Cell 4 -- D1: curve vs posizione-nella-finestra (steps da reset)
import torch, numpy as np, pandas as pd, matplotlib.pyplot as plt
from IPython.display import display, Markdown
if model is not None:
    T = SEQ
    se_a = np.zeros(T); se_b = np.zeros(T)          # memory
    se_am = np.zeros(T); se_bm = np.zeros(T)        # memoryless
    pa = np.zeros(T); pb = np.zeros(T); spk = np.zeros(T)
    N = 0; gta_sum = 0.0; gtb_sum = 0.0
    with torch.no_grad():
        for x, y, mask, pgt in dl:
            ps_mem, spk_h = model.forward_sequence_with_stats(x)   # (B,T,5),(B,T)
            ps_abl = forward_ablated(model, x)
            B = x.shape[0]
            gta = pgt[:, 2:3]; gtb = pgt[:, 3:4]                   # params_gt: a=2,b=3
            se_a += ((ps_mem[:, :, IA] - gta) ** 2).sum(0).numpy()
            se_b += ((ps_mem[:, :, IB] - gtb) ** 2).sum(0).numpy()
            se_am += ((ps_abl[:, :, IA] - gta) ** 2).sum(0).numpy()
            se_bm += ((ps_abl[:, :, IB] - gtb) ** 2).sum(0).numpy()
            pa += ps_mem[:, :, IA].sum(0).numpy(); pb += ps_mem[:, :, IB].sum(0).numpy()
            spk += spk_h.sum(0).numpy()
            N += B; gta_sum += float(pgt[:, 2].sum()); gtb_sum += float(pgt[:, 3].sum())
    pos = np.arange(T)
    nrmse_a = np.sqrt(se_a / N) / RANGE[IA]; nrmse_b = np.sqrt(se_b / N) / RANGE[IB]
    nrmse_am = np.sqrt(se_am / N) / RANGE[IA]; nrmse_bm = np.sqrt(se_bm / N) / RANGE[IB]
    mean_pa = pa / N; mean_pb = pb / N; spike = spk / N
    gta_mean = gta_sum / N; gtb_mean = gtb_sum / N
    dfd = pd.DataFrame({'pos': pos, 'nrmse_a_mem': nrmse_a, 'nrmse_a_memless': nrmse_am,
                        'nrmse_b_mem': nrmse_b, 'nrmse_b_memless': nrmse_bm,
                        'mean_pred_a': mean_pa, 'mean_pred_b': mean_pb, 'spike_rate': spike})
    dfd.to_csv(RESULTS + '/l1c_position.csv', index=False)
    fig, ax = plt.subplots(1, 3, figsize=(18, 4.6))
    ax[0].plot(pos, nrmse_a, '-', color='tab:red', label='a memory')
    ax[0].plot(pos, nrmse_am, '--', color='tab:red', alpha=0.6, label='a memoryless')
    ax[0].plot(pos, nrmse_b, '-', color='tab:purple', label='b memory')
    ax[0].plot(pos, nrmse_bm, '--', color='tab:purple', alpha=0.6, label='b memoryless')
    ax[0].set_xlabel('posizione nella finestra (steps da reset)'); ax[0].set_ylabel('NRMSE')
    ax[0].set_title('D1a - errore vs posizione (mem CRESCE? memoryless piatto?)')
    ax[0].legend(fontsize=7); ax[0].grid(alpha=0.3)
    ax[1].plot(pos, mean_pa, color='tab:red', label='a predetto (memory)')
    ax[1].axhline(gta_mean, color='k', ls=':', label='a GT medio')
    ax[1].plot(pos, mean_pb, color='tab:purple', label='b predetto (memory)')
    ax[1].axhline(gtb_mean, color='gray', ls=':', label='b GT medio')
    ax[1].set_xlabel('posizione nella finestra'); ax[1].set_ylabel('valore predetto [m/s2]')
    ax[1].set_title('D1b - deriva della predizione (H1: deriva verso un valore fisso?)')
    ax[1].legend(fontsize=7); ax[1].grid(alpha=0.3)
    ax[2].plot(pos, spike, color='tab:green')
    ax[2].set_xlabel('posizione nella finestra'); ax[2].set_ylabel('spike-rate hidden (memory)')
    ax[2].set_title('D1c - spike-rate vs posizione (H2: creep adattamento ALIF?)')
    ax[2].grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(RESULTS + '/l1c_position.png', dpi=130); plt.show()
    display(Markdown('## D1 - sintesi (early=pos 5-25, late=pos 75-95)'))
    ea = slice(5, 25); la = slice(75, 95)
    summ = {'rise_nrmse_a_mem': float(nrmse_a[la].mean() - nrmse_a[ea].mean()),
            'rise_nrmse_a_memless': float(nrmse_am[la].mean() - nrmse_am[ea].mean()),
            'rise_nrmse_b_mem': float(nrmse_b[la].mean() - nrmse_b[ea].mean()),
            'pred_a_drift': float(mean_pa[la].mean() - mean_pa[ea].mean()),
            'spike_drop': float(spike[ea].mean() - spike[la].mean()),
            'spike_early': float(spike[ea].mean()), 'spike_late': float(spike[la].mean())}
    for k, v in summ.items():
        print(' ', k, '=', round(v, 4))
else:
    print('[skip] modello assente'); summ = None
"""

D2 = """# Cell 5 -- D2: traccia 'a' allineata sui transitori (memory vs memoryless vs |accel|)
import torch, numpy as np, pandas as pd, matplotlib.pyplot as plt
from IPython.display import display, Markdown
if model is not None:
    W = 10; off = np.arange(-W, W + 1)
    acc_mem = np.zeros(2 * W + 1); acc_abl = np.zeros(2 * W + 1); acc_ax = np.zeros(2 * W + 1)
    ne = 0
    with torch.no_grad():
        for x, y, mask, pgt in dl:
            ps_mem = model.forward_sequence(x)[:, :, IA].numpy()
            ps_abl = forward_ablated(model, x)[:, :, IA].numpy()
            vdot = y[:, :, 0].numpy(); B, T, _ = x.shape
            for b in range(B):
                idx = np.where(np.abs(vdot[b]) > 0.5)[0]
                for ti in idx:
                    if ti - W >= 0 and ti + W < T:
                        acc_mem += ps_mem[b, ti - W:ti + W + 1]
                        acc_abl += ps_abl[b, ti - W:ti + W + 1]
                        acc_ax += np.abs(vdot[b, ti - W:ti + W + 1]); ne += 1
    m_mem = acc_mem / max(ne, 1); m_abl = acc_abl / max(ne, 1); m_ax = acc_ax / max(ne, 1)
    amp_mem = float(m_mem.max() - m_mem.min()); amp_abl = float(m_abl.max() - m_abl.min())
    atten = amp_mem / amp_abl if amp_abl > 1e-9 else float('nan')
    df2 = pd.DataFrame({'offset': off, 'a_mem': m_mem, 'a_memless': m_abl, 'abs_accel': m_ax})
    df2.to_csv(RESULTS + '/l1c_transient.csv', index=False)
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(off, m_mem, 'o-', color='tab:red', label='a predetto (memory)')
    ax1.plot(off, m_abl, 's--', color='tab:orange', label='a predetto (memoryless)')
    ax1.set_xlabel('offset dal transitorio [step]'); ax1.set_ylabel('a predetto [m/s2]')
    ax1.axvline(0, color='gray', ls=':')
    ax2 = ax1.twinx(); ax2.plot(off, m_ax, color='tab:blue', alpha=0.5, label='|accel| reale')
    ax2.set_ylabel('|accel| [m/s2]', color='tab:blue')
    ax1.set_title('D2 - risposta di a al transitorio: attenuazione mem/memless = %.2f' % atten)
    ax1.legend(loc='upper left', fontsize=8)
    fig.tight_layout(); fig.savefig(RESULTS + '/l1c_transient.png', dpi=130); plt.show()
    display(Markdown('## D2 - eventi-transitorio aggregati: %d | attenuazione (amp_mem/amp_memless) = %.3f' % (ne, atten)))
    print('amp_mem =', round(amp_mem, 4), '| amp_memless =', round(amp_abl, 4), '| atten =', round(atten, 3))
else:
    print('[skip] modello assente'); atten = None; ne = 0
"""

VERDICT = """# Cell 6 -- verdetto meccanismo + push
import json, subprocess
if model is not None:
    H1 = bool(summ['rise_nrmse_a_mem'] > 0.05 and abs(summ['rise_nrmse_a_memless']) < 0.02)
    H2 = bool(summ['spike_drop'] > 0.02 and summ['spike_early'] > 1e-6 and
              (summ['spike_drop'] / summ['spike_early']) > 0.15)
    H3 = bool(atten is not None and atten < 0.85)
    v = []
    if H1:
        v.append('H1 ACCUMULO/DERIVA confermata: NRMSE(a) memory sale di %.3f da early a late mentre '
                 'il memoryless resta piatto (%.3f). La predizione a deriva di %.3f. Lo stato propagato '
                 'inietta un bias che cresce dopo il reset.'
                 % (summ['rise_nrmse_a_mem'], summ['rise_nrmse_a_memless'], summ['pred_a_drift']))
    else:
        v.append('H1 non confermata: NRMSE(a) memory non cresce nettamente con la posizione '
                 '(rise %.3f). Il danno non e\\' accumulo posizionale.' % summ['rise_nrmse_a_mem'])
    if H2:
        v.append('H2 CREEP ADATTAMENTO contribuisce: spike-rate cala da %.3f a %.3f (-%.0f%%) lungo la '
                 'finestra -> il transitorio si spegne.'
                 % (summ['spike_early'], summ['spike_late'], 100 * summ['spike_drop'] / max(summ['spike_early'], 1e-9)))
    else:
        v.append('H2 non dominante: spike-rate stabile lungo la finestra (drop %.3f).' % summ['spike_drop'])
    if H3:
        v.append('H3 SMOOTHING confermata: la risposta di a al transitorio in memory e\\' attenuata '
                 '(amp mem/memless = %.2f < 1) -> la ricorrenza fa low-pass e smussa il picco.' % atten)
    else:
        v.append('H3 non dominante: la risposta di a al transitorio non e\\' attenuata in memory '
                 '(atten = %s).' % (round(atten, 2) if atten is not None else 'NA'))
    dom = [n for n, f in [('H1-accumulo', H1), ('H2-creep', H2), ('H3-smoothing', H3)] if f]
    v.append('=> MECCANISMO dominante: ' + (', '.join(dom) if dom else 'nessuna firma netta - rivedere') +
             '. Implicazione: il memoryless evita il difetto resettando lo stato a ogni step; '
             'il training L2 dovrebbe o adottare il readout memoryless o regolarizzare la ricorrenza '
             'contro questo difetto.')
    out = {'D1_summary': summ, 'D2_atten': atten, 'D2_n_events': ne,
           'H1_accumulo': H1, 'H2_creep': H2, 'H3_smoothing': H3, 'verdict': v}
    json.dump(out, open(RESULTS + '/l1c_results.json', 'w'), indent=2)
    print('VERDETTO L1c:')
    for s in v:
        print(' -', s)
    subprocess.run(['git', 'add', RESULTS], capture_output=True)
    r = subprocess.run(['git', 'commit', '-m', 'Dynamic_Study L1c: meccanismo del danno ricorrenza su a/b (H1 accumulo / H2 creep / H3 smoothing)'],
                       capture_output=True, text=True)
    print(r.stdout[-200:] if r.returncode == 0 else r.stderr[-200:])
    subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True)
    subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
    print('L1c pushed.')
else:
    print('[skip] niente da pushare (checkpoint assente)')
"""


def main():
    cells = [cell(INTRO, 'intro', 'markdown'),
             cell(ENV, 'env'), cell(LOAD, 'load'), cell(HELP, 'help'),
             cell(D1, 'd1'), cell(D2, 'd2'), cell(VERDICT, 'verdict')]
    nb = {'cells': cells,
          'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                       'language_info': {'name': 'python', 'version': '3.x'}},
          'nbformat': 4, 'nbformat_minor': 5}
    out = os.path.join(ROOT, 'Dynamic_Study_L1c.ipynb')
    json.dump(nb, open(out, 'w', encoding='utf-8'), indent=1)
    print('Wrote', out)


if __name__ == '__main__':
    main()
