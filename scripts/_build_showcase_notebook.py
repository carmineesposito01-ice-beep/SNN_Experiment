"""Loss_Study Showcase — vetrina quantitativa+qualitativa della SNN car-following.

Tutto cio' che e' mostrabile come dato: accuracy (visiva), attivita' spiking (raster
sincronizzato allo scenario), energia SNN vs ANN, sparsita', animazione auto (GIF),
dashboard riassuntivo. Checkpoint solo su Azure -> celle dipendenti dal modello saltano
con grazia se assente; lo scorecard accuracy usa i results (sempre disponibili).

Genera Loss_Study_Showcase.ipynb.
"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_cell(ctype, src, cid):
    if isinstance(src, list):
        src = '\n'.join(src)
    c = {'cell_type': ctype, 'id': cid, 'metadata': {}, 'source': src}
    if ctype == 'code':
        c['execution_count'] = None; c['outputs'] = []
    return c


def make_notebook(cells):
    return {'cells': cells,
            'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                         'language_info': {'name': 'python', 'version': '3.x'}},
            'nbformat': 4, 'nbformat_minor': 5}


INTRO = """# Loss_Study Showcase — vetrina SNN car-following

Tutto cio' che e' quantitativamente/qualitativamente mostrabile:
1. **Accuracy** identificazione parametri (visiva)
2. **Attivita' spiking** — raster neuroni x tempo, sincronizzato allo scenario
3. **Energia** SNN (event-driven) vs ANN equivalente (dense MAC)
4. **Sparsita'/attivita'** neuronale
5. **Animazione** auto (GIF) durante uno scenario
6. **Dashboard** riassuntivo (un colpo d'occhio)

> Checkpoint solo su Azure. Le celle col modello saltano se assente; lo scorecard accuracy usa i results.
"""

CELL_1 = """# Cell 1 -- ENV
import sys, os, subprocess
import importlib.util as _imu
RESULTS_DIR = 'results/Loss_Study/Showcase'
BRANCH = 'Loss_Study'
os.makedirs(RESULTS_DIR, exist_ok=True)
for pkg in ['pandas', 'matplotlib', 'pillow']:
    if _imu.find_spec(pkg.replace('pillow','PIL')) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
print('[Showcase] ENV OK')"""

CELL_2 = '''# Cell 2 -- Carica il modello consolidato (d0.3) se presente
import os, torch
from core.network import build_model
CKPT = 'checkpoints/LS3_PEAK_R0_launch_d03/best_model.pt'
S3_LOG = 'results/Loss_Study/S3/PEAK/LS3_PEAK_R0_launch_d03/training_log.csv'
model = None
if os.path.isfile(CKPT):
    ck = torch.load(CKPT, map_location='cpu', weights_only=False)
    model = build_model(variant='baseline', hidden_size=32, rank=8, max_delay=6, bit_shift=3)
    model.load_state_dict(ck['model_state']); model.eval()
    print(f'[OK] modello caricato ({sum(p.numel() for p in model.parameters())} param, h={model.hidden_size}, n_ticks={model.n_ticks})')
else:
    print(f'[skip] checkpoint assente ({CKPT}) -> celle spike/energia/animazione saltate. Scorecard accuracy comunque attivo.')'''

CELL_3 = '''# Cell 3 -- ACCURACY scorecard (visiva, dai results S3 d0.3)
import os, pandas as pd, numpy as np
import matplotlib.pyplot as plt
CH = ['v0', 'T', 's0', 'a', 'b']; TRUE = {'v0': 33.3, 'T': 1.2, 's0': 2.5, 'a': 1.1, 'b': 1.5}
if os.path.isfile(S3_LOG):
    e = pd.read_csv(S3_LOG); i = int(e['val_data'].idxmin())
    nrmse = [float(e[f'val_{c}_nrmse'].iloc[i]) for c in CH]
    pred = [float(e[f'val_{c}_pred_mean'].iloc[i]) for c in CH]
    acc = [max(0.0, 1 - n) * 100 for n in nrmse]    # "accuracy" % ~ 1-NRMSE
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5))
    bars = a1.bar(CH, acc, color=['tab:green' if x > 75 else 'tab:orange' if x > 65 else 'tab:red' for x in acc])
    a1.set_ylim(0, 100); a1.set_ylabel('accuracy ~ (1-NRMSE) [%]'); a1.axhline(75, color='gray', ls=':')
    a1.set_title(f'Accuracy identificazione per parametro (media {np.mean(acc):.0f}%)')
    for b, n in zip(bars, nrmse): a1.text(b.get_x()+b.get_width()/2, b.get_height()+1, f'NRMSE\\n{n:.2f}', ha='center', fontsize=8)
    a1.grid(alpha=0.3, axis='y')
    x = np.arange(len(CH)); w = 0.35
    a2.bar(x-w/2, pred, w, label='predetto', color='tab:blue')
    a2.bar(x+w/2, [TRUE[c] for c in CH], w, label='vero', color='tab:gray')
    a2.set_xticks(x); a2.set_xticklabels(CH); a2.set_yscale('log'); a2.set_ylabel('valore (log)')
    a2.set_title('Parametro predetto vs vero'); a2.legend(); a2.grid(alpha=0.3, axis='y')
    plt.tight_layout(); plt.savefig(f'{RESULTS_DIR}/showcase_accuracy.png', dpi=120); plt.show()
    print(f'Accuracy media {np.mean(acc):.0f}% | per-param: ' + ', '.join(f'{c}={a:.0f}%' for c,a in zip(CH,acc)))
else:
    print('S3 log assente -> scorecard accuracy saltato'); nrmse = None'''

CELL_4 = '''# Cell 4 -- SPIKE RASTER + spike-rate(t) sincronizzato allo scenario (cut-in)
import numpy as np, matplotlib.pyplot as plt
if model is not None:
    from utils.closed_loop_eval import build_scenarios
    from utils.snn_showcase import capture_run
    pgt = np.array([33.3, 1.2, 2.5, 1.1, 1.5], dtype=np.float32)
    scen = {s[0]: s for s in build_scenarios(pgt, N=400, rng=np.random.default_rng(1))}
    _, vl, s_i, v_i, cut = scen['cut_in']
    traj, spikes = capture_run(model, pgt, vl, s_i, v_i, cut_in=cut)   # spikes (T,H)
    T = spikes.shape[0]; t = np.arange(T) * 0.1
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True,
                             gridspec_kw={'height_ratios': [2, 1, 1]})
    ys, xs = np.where(spikes.T > 0)                                    # raster
    axes[0].scatter(xs * 0.1, ys, s=6, c='k', marker='|')
    axes[0].set_ylabel('neurone hidden'); axes[0].set_title('Raster spike (cut-in): la rete "spara" piu fitto nei transitori')
    axes[1].plot(t, spikes.sum(1), color='tab:purple'); axes[1].set_ylabel('spike totali / step')
    axes[1].grid(alpha=0.3)
    axes[2].plot(t, traj['s'], label='gap [m]'); axes[2].plot(t, traj['a_ego'], label='a_ego [m/s2]')
    if cut: axes[2].axvline(cut[0]*0.1, color='r', ls='--', alpha=0.6, label='cut-in')
    axes[2].set_xlabel('t [s]'); axes[2].legend(fontsize=8); axes[2].grid(alpha=0.3)
    axes[2].set_title('Scenario (per confronto con l attivita spiking sopra)')
    plt.tight_layout(); plt.savefig(f'{RESULTS_DIR}/showcase_raster.png', dpi=120); plt.show()
    print(f'Raster: {int(spikes.sum())} spike, {(spikes.sum(0)>0).sum()}/{spikes.shape[1]} neuroni attivi')
else:
    print('[skip] modello assente'); spikes = None'''

CELL_5 = '''# Cell 5 -- ENERGIA SNN vs ANN equivalente + sparsita
import numpy as np, matplotlib.pyplot as plt
if model is not None and spikes is not None:
    from utils.snn_showcase import energy_estimate, E_MAC_FP32, E_AC_FP32
    en = energy_estimate(spikes, model)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5))
    a1.bar(['ANN-equiv\\n(dense MAC)', 'SNN\\n(event-driven)'], [en['E_ann_nJ'], en['E_snn_nJ']],
           color=['tab:gray', 'tab:green'])
    a1.set_ylabel('energia / inferenza [nJ]')
    a1.set_title(f"Energia: SNN {en['E_snn_nJ']:.0f} nJ vs ANN {en['E_ann_nJ']:.0f} nJ = {en['energy_advantage_x']:.1f}x")
    for i, val in enumerate([en['E_ann_nJ'], en['E_snn_nJ']]):
        a1.text(i, val, f'{val:.0f} nJ', ha='center', va='bottom')
    a1.grid(alpha=0.3, axis='y')
    a2.bar(['spike rate\\n[%]', 'neuroni\\nattivi [%]', 'vantaggio\\nenergia [x]'],
           [en['mean_spike_rate_pct'], en['active_neuron_frac']*100, en['energy_advantage_x']],
           color=['tab:purple', 'tab:blue', 'tab:green'])
    a2.set_title('Metriche neuromorfiche'); a2.grid(alpha=0.3, axis='y')
    for i, val in enumerate([en['mean_spike_rate_pct'], en['active_neuron_frac']*100, en['energy_advantage_x']]):
        a2.text(i, val, f'{val:.1f}', ha='center', va='bottom')
    plt.tight_layout(); plt.savefig(f'{RESULTS_DIR}/showcase_energy.png', dpi=120); plt.show()
    import json
    json.dump({k: (int(v) if isinstance(v, (int, np.integer)) else float(v)) for k, v in en.items()},
              open(f'{RESULTS_DIR}/showcase_energy.json', 'w'), indent=2)
    print(f"SNN {en['E_snn_nJ']:.1f} nJ vs ANN {en['E_ann_nJ']:.1f} nJ -> {en['energy_advantage_x']:.1f}x | "
          f"sparsita {en['mean_spike_rate_pct']:.1f}% | SynOps {en['snn_synops']} vs MAC {en['ann_macs']}")
    print('NB: stima Horowitz 45nm (E_MAC=4.6pJ, E_AC=0.9pJ), per-inferenza. Po2/FPGA -> AC ancora piu economico.')
else:
    print('[skip] modello/spike assenti')'''

CELL_6 = '''# Cell 6 -- ANIMAZIONE auto (GIF) durante il cut-in
import numpy as np, matplotlib.pyplot as plt
from matplotlib import animation
if model is not None:
    from utils.closed_loop_eval import build_scenarios
    from utils.snn_showcase import capture_run
    pgt = np.array([33.3, 1.2, 2.5, 1.1, 1.5], dtype=np.float32)
    scen = {s[0]: s for s in build_scenarios(pgt, N=400, rng=np.random.default_rng(1))}
    _, vl, s_i, v_i, cut = scen['cut_in']
    traj, _ = capture_run(model, pgt, vl, s_i, v_i, cut_in=cut)
    x_ego = np.cumsum(traj['v']) * 0.1
    x_lead = x_ego + traj['s']                       # leader avanti di gap
    step = max(1, len(x_ego) // 120)                 # ~120 frame
    fig, ax = plt.subplots(figsize=(11, 2.6))
    ax.set_ylim(-1, 1); ax.set_yticks([]); ax.set_xlabel('posizione [m]')
    (ego,) = ax.plot([], [], 's', ms=16, color='tab:blue', label='ego (SNN)')
    (lead,) = ax.plot([], [], 's', ms=16, color='tab:red', label='leader')
    gap_txt = ax.text(0.02, 0.85, '', transform=ax.transAxes)
    ax.legend(loc='upper right')
    def _init():
        ax.set_xlim(x_ego[0] - 10, x_lead[0] + 20); return ego, lead, gap_txt
    def _frame(k):
        i = k * step
        ego.set_data([x_ego[i]], [0]); lead.set_data([x_lead[i]], [0])
        ax.set_xlim(x_ego[i] - 10, x_lead[i] + 20)
        gap_txt.set_text(f't={i*0.1:.1f}s  gap={traj["s"][i]:.1f}m  v_ego={traj["v"][i]:.1f}')
        return ego, lead, gap_txt
    anim = animation.FuncAnimation(fig, _frame, init_func=_init, frames=len(x_ego)//step, blit=True)
    gif = f'{RESULTS_DIR}/showcase_cars.gif'
    anim.save(gif, writer=animation.PillowWriter(fps=15)); plt.close(fig)
    print(f'animazione salvata: {gif}')
    from IPython.display import Image, display; display(Image(gif))
else:
    print('[skip] modello assente')'''

CELL_7 = '''# Cell 7 -- DASHBOARD riassuntivo (un colpo d'occhio)
import os, json, numpy as np, pandas as pd, matplotlib.pyplot as plt
lines = ['CF_FSNN — SNN car-following (PYNQ-Z1 target)', '']
lines.append(f"Parametri rete: {sum(p.numel() for p in model.parameters()) if model else 864}")
if nrmse is not None:
    lines.append(f"Accuracy identificazione (media): {np.mean([max(0,1-n)*100 for n in nrmse]):.0f}%  (5 param IDM)")
ej = f'{RESULTS_DIR}/showcase_energy.json'
if os.path.isfile(ej):
    en = json.load(open(ej))
    lines.append(f"Energia/inferenza: SNN {en['E_snn_nJ']:.0f} nJ  vs  ANN {en['E_ann_nJ']:.0f} nJ  ->  {en['energy_advantage_x']:.0f}x")
    lines.append(f"Sparsita' spiking: {en['mean_spike_rate_pct']:.1f}%   (SynOps {en['snn_synops']} vs MAC {en['ann_macs']})")
safety = 'results/Loss_Study/Eval_ClosedLoop/safety_summary.csv'
if os.path.isfile(safety):
    sdf = pd.read_csv(safety, index_col=0)
    snn_rows = [r for r in sdf.index if r != 'oracle']
    if snn_rows:
        cr = sdf.loc[snn_rows, 'collision_rate'].max()
        lines.append(f"Sicurezza closed-loop: collision rate {cr*100:.0f}%  (0% = nessun incidente)")
else:
    lines.append("Sicurezza closed-loop: (esegui Loss_Study_Eval_ClosedLoop per il verdetto)")
fig, ax = plt.subplots(figsize=(11, 5)); ax.axis('off')
ax.text(0.5, 0.97, 'DASHBOARD CF_FSNN', ha='center', va='top', fontsize=16, weight='bold')
ax.text(0.05, 0.85, '\\n'.join(lines[2:]), va='top', fontsize=12, family='monospace')
plt.savefig(f'{RESULTS_DIR}/showcase_dashboard.png', dpi=120, bbox_inches='tight'); plt.show()
print('\\n'.join(lines))'''

CELL_8 = """# Cell 8 -- Push
import subprocess
subprocess.run(['git', 'add', RESULTS_DIR], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'Showcase: accuracy/raster/energy/animation/dashboard'],
                   capture_output=True, text=True)
print(r.stdout[-200:] if r.returncode == 0 else r.stderr[-200:])
subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
print('Showcase pushed.')"""


def main():
    cells = [make_cell('markdown', INTRO, 'cell-intro')]
    for i, c in enumerate([CELL_1, CELL_2, CELL_3, CELL_4, CELL_5, CELL_6, CELL_7, CELL_8], 1):
        cells.append(make_cell('code', c, f'cell-{i}'))
    nb = make_notebook(cells)
    out = os.path.join(ROOT, 'Loss_Study_Showcase.ipynb')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
