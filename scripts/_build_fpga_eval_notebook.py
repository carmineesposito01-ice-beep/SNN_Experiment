"""scripts/_build_fpga_eval_notebook.py -- genera Eval_FPGA.ipynb (Fase A software_now).

Orchestra le 46 figure a dati reali (scripts/fpga_figures.py) + i CSV deliverable (§4.3)
nelle 10 sezioni, sui 4 champion. Pattern resiliente come l'evaluate v3 (per-cella try/except
-> ERROR_<sez>.txt, done-skip, csv/figure salvati in results/evaluate/FPGA/, auto-push).
Gira su Azure (checkpoint dei champion). Costruzione: python scripts/_build_fpga_eval_notebook.py
Verifica post-run: python scripts/verify_fpga_eval.py
"""
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def C(src, cid):
    return {'cell_type': 'code', 'id': cid, 'metadata': {}, 'execution_count': None,
            'outputs': [], 'source': src}


def MD(src, cid):
    return {'cell_type': 'markdown', 'id': cid, 'metadata': {}, 'source': src}


def resilient(body, name):
    indented = '\n'.join((('    ' + l) if l.strip() else l) for l in body.splitlines())
    return ('import traceback as _tb, os as _os\ntry:\n' + indented + '\n'
            'except Exception:\n'
            '    _os.makedirs(RESULTS, exist_ok=True)\n'
            "    open(_os.path.join(RESULTS, 'ERROR_" + name + ".txt'), 'w', encoding='utf-8')"
            ".write(_tb.format_exc())\n"
            "    print('[ERROR] " + name + " -> ERROR_" + name + ".txt'); print(_tb.format_exc())\n")


INTRO = ("# FPGA-evaluate — Fase A (software_now)\n\n"
         "Valutazione pre-silicio dell'idoneita' FPGA (Zynq-7020) dei 4 champion, cross-champion.\n"
         "46 figure a **dati reali** (10 sezioni) + CSV deliverable, dalle 5 librerie Fase A "
         "(`weight_profiler`, `state_profiler`, `latency_model`, `seu_inject`, `io_hil`).\n\n"
         "Le figure 🟢 sono calcolate dai tensori/forward reali; le 🟡/🔴 (HDL/board) sono STIME "
         "di progetto marcate. Output in `results/evaluate/FPGA/`.")

ENV = r'''# ENV -- champions + loader robusto + helper
import os, sys, json, glob, subprocess, importlib.util as _imu
sys.path.insert(0, os.getcwd())
for pkg in ['pandas', 'matplotlib', 'numpy', 'torch', 'scipy']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
import numpy as np, pandas as pd, torch
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
import scripts.fpga_figures as FF

RESULTS = 'results/evaluate/FPGA'
BRANCH = 'EventProp_Study'
CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'
os.makedirs(RESULTS, exist_ok=True)
assert os.path.isfile(CACHE), 'manca cache: ' + CACHE
CACHE_DATA = torch.load(CACHE, map_location='cpu', weights_only=False)

# 4 champion (2 BPTT + 2 EventProp). L'oracolo non serve al profilo FPGA.
CHAMPIONS = [
    ('Raffaello',    'R33_C2_A1_T12_fix',      '#d1495b', 'baseline'),
    ('Leonardo',     'LS3_PEAK_R0_launch_d03', '#2a7fb8', 'baseline'),
    ('Donatello',    'PE_t05_gp0002',          '#7b3fa0', 'eventprop_alif_full'),
    ('Michelangelo', 'A_lr1e2_t06_r16',        '#e8871e', 'eventprop_alif_full'),
]
COLORS = {a: c for a, _, c, _ in CHAMPIONS}

def robust_load(tag, variant, device='cpu'):
    from core.network import build_model
    p = os.path.join('checkpoints', tag, 'best_model.pt')
    if not os.path.isfile(p):
        return None
    ck = torch.load(p, map_location=device, weights_only=False)
    state = ck['model_state'] if isinstance(ck, dict) and 'model_state' in ck else ck
    if 'layer_hidden.rec_U' in state:
        hidden = int(state['layer_hidden.rec_U'].shape[0]); rank = int(state['layer_hidden.rec_U'].shape[1])
    else:
        hidden, rank = 32, 8
    v = 'baseline' if 'layer_out.fc_weight' in state else \
        ('eventprop_alif_full' if 'layer_out.weight' in state else variant)
    try:
        m = build_model(variant=v, hidden_size=hidden, rank=rank, max_delay=6, bit_shift=3)
        res = m.load_state_dict(state, strict=False)
    except Exception:
        return None
    if any('layer_out' in k for k in getattr(res, 'missing_keys', [])):
        print('   [WARN] %s: readout non caricato -> scartato' % tag); return None
    m.eval(); return m

MODELS = {}
for alias, tag, _, variant in CHAMPIONS:
    m = robust_load(tag, variant); MODELS[alias] = m
    print('[%-4s] %-14s <- %s' % ('OK' if m is not None else 'FAIL', alias, tag))
AVAIL = [a for a, _, _, _ in CHAMPIONS if MODELS.get(a) is not None]
print('\nChampion disponibili:', AVAIL)

def sub(d):
    p = os.path.join(RESULTS, d); os.makedirs(p, exist_ok=True); return p
def savefig(d, name, fig):
    fig.savefig(os.path.join(sub(d), name), dpi=120, bbox_inches='tight'); plt.close(fig)
def savecsv(d, name, rows):
    pd.DataFrame(rows).to_csv(os.path.join(sub(d), name), index=False)
def done_section(d):
    return os.path.isdir(os.path.join(RESULTS, d)) and \
        len(glob.glob(os.path.join(RESULTS, d, '*.png'))) >= len(FF.SECTIONS[d])

ctx = None
'''

CTX = r'''# CTX -- contesto reale (una volta) con budget Azure pieno
if not AVAIL:
    print('[skip] nessun champion disponibile'); ctx = None
else:
    _models = {a: MODELS[a] for a in AVAIL}
    ctx = FF.build_ctx(_models, CACHE_DATA, colors={a: COLORS[a] for a in AVAIL}, hb=FF.HB_AZURE)
    ctx['models_ref'] = _models
    print('ctx costruito per', ctx['aliases'])
'''


def SEC(folder):
    return ("# sezione " + folder + "\n"
            "D = " + repr(folder) + "\n"
            "if ctx is None:\n    print('[skip] ctx assente', D)\n"
            "elif done_section(D):\n    print('[SKIP]', D)\n"
            "else:\n    _n = FF.save_section(ctx, D, savefig); print('[OK]', D, '->', _n, 'figure')\n")


CSVCELL = r'''# CSV deliverable (§4.3)
if ctx is not None:
    FF.save_all_csvs(ctx, savecsv); print('[OK] CSV deliverable salvati')
'''

PUSH = r'''# push dei risultati FPGA (robusto, retry)
import subprocess, time
def _git(*a): return subprocess.run(['git', *a], capture_output=True, text=True)
_git('add', RESULTS)
r = _git('commit', '-m', 'eval FPGA Fase A: 46 figure (10 sezioni) + CSV deliverable, cross-champion')
if r.returncode != 0 and 'nothing to commit' in (r.stdout + r.stderr):
    print('niente da committare')
else:
    for k in range(5):
        _git('pull', '--no-rebase', '--no-edit', 'origin', BRANCH)
        p = _git('push', 'origin', BRANCH)
        if p.returncode == 0:
            print('push OK'); break
        print('push retry', k, p.stderr[-160:]); time.sleep(3)
'''

SECTION_ORDER = ['00_Readiness', '01_Weights_po2', '02_FixedPoint', '03_Spiking', '04_Energy',
                 '05_Timing_WCET', '06_Resources_DSE', '07_SEU_ISO26262', '08_IO_HIL', '09_Thermal']

cells = [MD(INTRO, 'intro'), C(ENV, 'env'), C(resilient(CTX, 'ctx'), 'ctx')]
for i, folder in enumerate(SECTION_ORDER):
    cells.append(C(resilient(SEC(folder), folder), 'sec%02d' % i))
cells.append(C(resilient(CSVCELL, 'csv'), 'csv'))
cells.append(C(PUSH, 'push'))

nb = {'cells': cells,
      'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                   'language_info': {'name': 'python', 'version': '3.10'},
                   'execution': {'timeout': -1, 'allow_errors': True}},
      'nbformat': 4, 'nbformat_minor': 5}

out = os.path.join(ROOT, 'Eval_FPGA.ipynb')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print('Wrote', out, '(%d celle)' % len(cells))
