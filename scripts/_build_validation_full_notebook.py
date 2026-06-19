"""Loss_Study Validation FULL — eval sicurezza + showcase in UN notebook (un solo run).

Carica il checkpoint UNA volta, esegue la validazione closed-loop (sicurezza) e poi la
vetrina (accuracy/raster/energia/animazione/dashboard). Il dashboard legge il verdetto di
sicurezza prodotto dall'eval (eseguito prima) -> riassunto completo. Push unico finale.

Riusa le celle gia' validate dei due build-script (no duplicazione/drift), rimappando
RESULTS_DIR -> EVAL_DIR / SHOW_DIR. Genera Loss_Study_Validation_Full.ipynb.
"""
import json, os, importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


EV = _load('scripts/_build_eval_closedloop_notebook.py', 'ev')
SH = _load('scripts/_build_showcase_notebook.py', 'sh')


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


INTRO = """# Loss_Study — Validazione COMPLETA (un solo run, ~5-7 min)

Carica il checkpoint **una volta** ed esegue tutto in sequenza:
1. **Sicurezza closed-loop** (scenari avversari) → 4 grafici + 4 CSV
2. **Vetrina**: accuracy, raster spike, energia SNN vs ANN, animazione auto (GIF), dashboard

Il **dashboard** finale include anche il verdetto di sicurezza (prodotto al passo 1).
Niente training → tempi brevi. Checkpoint solo su Azure; le celle col modello saltano se assente.
"""

ENV = """# Cell 1 -- ENV + cartelle
import sys, os, subprocess
import importlib.util as _imu
EVAL_DIR = 'results/Loss_Study/Eval_ClosedLoop'
SHOW_DIR = 'results/Loss_Study/Showcase'
BRANCH = 'Loss_Study'
_TMP_MSG = '/tmp/valfull.txt' if os.path.isdir('/tmp') else 'valfull.txt'
for d in (EVAL_DIR, SHOW_DIR):
    os.makedirs(d, exist_ok=True)
for pkg in ['pandas', 'matplotlib', 'pillow']:
    if _imu.find_spec(pkg.replace('pillow', 'PIL')) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
assert br == BRANCH, f'branch={br} != {BRANCH}'
print('[ValidationFull] ENV OK — eval + showcase in un solo run')"""

LOAD = '''# Cell 2 -- carica checkpoint -> models (eval) + model primario (showcase)
import os, torch, shutil
from core.network import build_model
CANDIDATES = [
    ('S3 d0.3 (launch)', 'checkpoints/LS3_PEAK_R0_launch_d03/best_model.pt', 32, 8),
    ('S3 d1.0 (launch)', 'checkpoints/LS3_PEAK_R0_launch/best_model.pt',     32, 8),
    ('R33_C2 CLEAN',     'checkpoints/R33_C2_A1_T12_fix/best_model.pt',       32, 8),
]
S3_LOG = 'results/Loss_Study/S3/PEAK/LS3_PEAK_R0_launch_d03/training_log.csv'
CKPT = CANDIDATES[0][1]
models = {}
for label, path, h, rk in CANDIDATES:
    if not os.path.isfile(path):
        print(f'  [skip] {label}: checkpoint assente ({path})'); continue
    ck = torch.load(path, map_location='cpu', weights_only=False)
    m = build_model(variant='baseline', hidden_size=h, rank=rk, max_delay=6, bit_shift=3)
    m.load_state_dict(ck['model_state']); m.eval(); models[label] = m
    dst = f'{EVAL_DIR}/checkpoints/{label.replace(" ", "_").replace("(", "").replace(")", "")}.pt'
    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(path, dst)
    print(f'  [OK] {label} ({sum(p.numel() for p in m.parameters())} param)')
model = next(iter(models.values())) if models else None     # showcase usa il primario
print(f'Modelli eval: {list(models.keys())} (+ oracolo) | showcase: {list(models.keys())[0] if models else "NESSUNO"}')
if not models:
    print('NB: nessun checkpoint -> eval gira solo oracolo; showcase fa accuracy+dashboard.')'''

PUSH = """# Cell -- push finale (eval + showcase insieme)
import subprocess
subprocess.run(['git', 'add', EVAL_DIR, SHOW_DIR], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'Validation full: safety eval + showcase'],
                   capture_output=True, text=True)
print(r.stdout[-200:] if r.returncode == 0 else r.stderr[-200:])
subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
print('Validation full pushed.')"""


def _remap(src, newdir):
    return src.replace('RESULTS_DIR', newdir)


def main():
    cells = [
        make_cell('markdown', INTRO, 'cell-intro'),
        make_cell('code', ENV, 'cell-env'),
        make_cell('code', LOAD, 'cell-load'),
        # --- EVAL (sicurezza) ---
        make_cell('code', _remap(EV.CELL_3_RUN, 'EVAL_DIR'), 'cell-ev-run'),
        make_cell('code', _remap(EV.CELL_4_SUMMARY, 'EVAL_DIR'), 'cell-ev-summary'),
        make_cell('code', _remap(EV.CELL_5_PLOTS, 'EVAL_DIR'), 'cell-ev-plots'),
        # --- SHOWCASE (vetrina) ---
        make_cell('code', _remap(SH.CELL_3, 'SHOW_DIR'), 'cell-sh-accuracy'),
        make_cell('code', _remap(SH.CELL_4, 'SHOW_DIR'), 'cell-sh-raster'),
        make_cell('code', _remap(SH.CELL_5, 'SHOW_DIR'), 'cell-sh-energy'),
        make_cell('code', _remap(SH.CELL_6, 'SHOW_DIR'), 'cell-sh-anim'),
        make_cell('code',
                  _remap(SH.CELL_7, 'SHOW_DIR').replace(
                      "'results/Loss_Study/Eval_ClosedLoop/safety_summary.csv'",
                      "f'{EVAL_DIR}/safety_summary.csv'"),
                  'cell-sh-dashboard'),
        make_cell('code', PUSH, 'cell-push'),
    ]
    nb = make_notebook(cells)
    out = os.path.join(ROOT, 'Loss_Study_Validation_Full.ipynb')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
