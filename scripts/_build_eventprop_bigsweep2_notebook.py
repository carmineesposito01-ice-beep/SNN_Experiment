"""EventProp Big Sweep 2 — conclude AdamW spettrale + Parte 2 con TUTTE le correzioni (decode, rank).

Genera EventProp_BigSweep2.ipynb. Due parti, 50 epoche, EventProp + vincolo spettrale C11:

  PARTE 1 — Conclude AdamW spettrale (decode OFF, isola lo spettrale): griglia lr x spectral_target
            ESTESA verso il basso (0.5-0.8, dove e' il vero ottimo). Evita gli arm gia' visti fallire
            (target alti 1.2/1.4 = esplodono; lr 5e-4 = sotto-performa).

  PARTE 2 — Nuova config + TUTTE le correzioni (per vedere "cosa cambia") sui migliori di Adam:
            * DECODER FIX (cf_init_bias_shift 1 + logit_tau 10,3,10,3,3) — sblocca T/s0 (NRMSE crolla,
              T-scatter segue y=x; a 10ep gia' batte BPTT-ref su ogni canale).
            * RANK 16 (vs 8) — la ricorrenza usa quanto rank le dai, rank 16 migliora il val.
            AdamW (decode+rank) sui migliori lr/target + ProdigyEvent LOSS-AWARE (decode+rank16).

Riferimento BPTT (champion single-cycle, gia' con la sua calibrazione). Best-first + SKIP+RESUME
(ri-eseguire la cella RUN continua). Diagnostica: per-canale (effetto decode), heatmap, verdetto vs BPTT.
Output in results/EventProp_BigSweep2/.
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


INTRO = """# EventProp Big Sweep 2 — AdamW concluso + correzioni complete (decode + rank)

**Parte 1**: conclude AdamW spettrale (decode OFF), griglia `lr x target` estesa in basso (0.5-0.8, l'ottimo
vero), senza gli arm gia' visti fallire. **Parte 2**: TUTTE le correzioni sui migliori — **decoder fix**
(sblocca T/s0) + **rank 16** + ProdigyEvent loss-aware. Riferimento BPTT champion. 50 ep, launch n1500.
Best-first, SKIP+RESUME. Diagnostica per-canale (effetto decode) + heatmap + verdetto vs BPTT.
Output `results/EventProp_BigSweep2/`.
"""

ENV = """# Cell 1 -- ENV
import sys, os, subprocess
import importlib.util as _imu
RESULTS = 'results/EventProp_BigSweep2'
BRANCH = 'EventProp_Study'
LAUNCH_MIX = 'highway:0.20,urban:0.15,truck:0.10,mixed:0.05,freeflow:0.15,launch:0.35'
CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'
_TMP_MSG = '/tmp/bigsweep2_msg.txt' if os.path.isdir('/tmp') else 'bigsweep2_msg.txt'
os.makedirs(RESULTS, exist_ok=True)
for pkg in ['pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
for f in ['core/eventprop.py', 'core/prodigy_event.py']:
    assert os.path.isfile(f), 'missing ' + f
assert os.path.isfile(CACHE), 'missing cache: ' + CACHE
br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
print('[BigSweep2] ENV OK | branch =', br, '| cache OK')
"""

CONFIG = """# Cell 2 -- arm: Parte 1 (AdamW concludi, decode OFF) + Parte 2 (correzioni: decode + rank)
EPOCHS = 50
COMMON = ['--max_steps_per_epoch', '100', '--batch_size', '8', '--val_batch_size', '32',
          '--seq_len', '50', '--cf_hidden_size', '32', '--cf_max_delay', '6',
          '--cf_bit_shift', '3', '--lambda_data', '1.0', '--lambda_phys', '0.1', '--lambda_ou', '0.05',
          '--lambda_bc', '1.0', '--lambda_sr', '0.5', '--scenario_mix', LAUNCH_MIX, '--cut_in_ratio', '0.0',
          '--noise_scale', '0.0', '--po2_enabled', '1', '--n_train', '1500', '--n_val', '300',
          '--data_cache', CACHE, '--max_inf_streak', '99999', '--early_stop_patience', '0',
          '--max_epoch_explosion_streak', '3', '--epoch_explosion_threshold', '10000.0',
          '--epoch_explosion_frac', '0.5', '--grad_clip', 'agc', '--agc_lambda', '0.01']

# Correzioni Parte 2
DECODE = ['--cf_init_bias_shift', '1', '--cf_logit_tau_per_channel', '10.0,3.0,10.0,3.0,3.0']
SPEC = lambda t: ['--eventprop_lambda_spectral', '1.0', '--eventprop_spectral_target', str(t)]

def _f(x):
    return str(x).replace('.', '').replace('-', '')

# ===== PARTE 1: AdamW spettrale concluso (decode OFF) =====
# Dal BigSweep: ottimo a lr alto (3e-3)+target basso (0.8=0.2161), monotono verso il basso ->
# concludo SOLO la regione vincente per target<0.8. Scartati lr 5e-4/1e-3 (0.24/0.23, inutili)
# e t0.8 (gia' fatto). lr alto+target alto esplode; i target bassi sono stabili anche a 5e-3.
P1_LRS = ['2e-3', '3e-3', '5e-3']
P1_TARGETS = [0.5, 0.6, 0.7]
def p1_arm(lr, t):
    return ('P1_lr' + _f(lr) + '_t' + _f(t), 'eventprop_alif_full',
            ['--optimizer', 'adamw', '--lr', lr, '--max_lr', lr, '--scheduler', 'cosine_no_restart'] + SPEC(t))

# ===== PARTE 2: correzioni complete (decode + rank), migliori lr/target =====
P2_LRS = ['2e-3', '3e-3']
P2_TARGETS = [0.5, 0.6, 0.7]
P2_RANKS = ['8', '16']
def p2_adam(lr, t, r):
    return ('P2_lr' + _f(lr) + '_t' + _f(t) + '_r' + r, 'eventprop_alif_full',
            ['--optimizer', 'adamw', '--lr', lr, '--max_lr', lr, '--scheduler', 'cosine_no_restart',
             '--cf_rank', r] + DECODE + SPEC(t))

# ProdigyEvent loss-aware con decode + rank 16. Dal BigSweep PE NON e' competitivo (plateau ~0.29 vs
# AdamW 0.216; lr/growth alti esplodono). Ultimo tentativo con tutte le correzioni: lr basso (0.3) +
# bad_decay aggressivo (0.3, il migliore tra i PE) per frenare il d. Se ancora ~0.29 -> PE archiviato.
PE = ['--optimizer', 'prodigy_event', '--lr', '0.3', '--max_lr', '0.3', '--scheduler', 'cosine_no_restart',
      '--cf_rank', '16', '--prodigy_growth_rate', '1.02', '--prodigy_betas', '0.9,0.99', '--prodigy_d0', '1e-6',
      '--prodigy_weight_decay', '0.01', '--prodigy_use_bias_correction', '1', '--prodigy_safeguard_warmup', '1',
      '--prodigy_ema_beta', '0.9', '--prodigy_rate_band', '0.10,0.25',
      '--prodigy_loss_aware', '1', '--prodigy_po_period', '25', '--prodigy_po_bad_decay', '0.3'] + DECODE
def pe_arm(t, gp):
    return ('PE_t' + _f(t) + '_gp' + _f(gp), 'eventprop_alif_full',
            list(PE) + ['--prodigy_po_good_probe', gp] + SPEC(t))

# ===== Riferimento BPTT = CHAMPION ESATTO (LS3_PEAK_R0_launch_d03, min val_data 0.1926) =====
# Config replicata dal config_snapshot del champion: Prodigy + custom_restart (T0 12, decay 0.3,
# warmup 2), growth INF (lo doma il restart, non il cap), grad_clip NONE (override dell'agc di COMMON).
# Il BPTT_REF del BigSweep era sbagliato (cosine_no_restart + growth 1.05) -> esplose. Questo e' il vero.
BPTT_DECODE = ['--cf_init_bias_shift', '1', '--cf_logit_tau_per_channel', '10.0,3.0,10.0,3.0,3.0']
CHAMPION = ['--optimizer', 'prodigy', '--lr', '0.5', '--max_lr', '0.5',
            '--scheduler', 'custom_restart', '--restart_T0', '12', '--restart_decay', '0.3',
            '--restart_warmup_epochs', '2', '--restart_adaptive', '0', '--restart_lr_after', '-1.0',
            '--prodigy_growth_rate', 'inf', '--prodigy_betas', '0.9,0.99', '--prodigy_d_coef', '1.0',
            '--prodigy_d0', '1e-6', '--prodigy_weight_decay', '0.01', '--prodigy_use_bias_correction', '1',
            '--prodigy_safeguard_warmup', '1', '--grad_clip', 'none', '--cf_rank', '8']
BPTT_REF = ('BPTT_REF', 'baseline', BPTT_DECODE + CHAMPION)

# ===== Assemblaggio (best-first): ref, teaser correzioni, Parte 1 (conclude Adam), Parte 2 =====
ARMS = []
_seen = set()
def _add(a):
    if a[0] not in _seen:
        _seen.add(a[0]); ARMS.append(a)

_add(BPTT_REF)                              # riferimento
_add(p2_adam('3e-3', 0.6, '16'))            # teaser: nuovo champion candidato (decode+rank16)
# Parte 1: conclude Adam (decode off)
for _lr in P1_LRS:
    for _t in P1_TARGETS:
        _add(p1_arm(_lr, _t))
# Parte 2: correzioni complete
for _lr in P2_LRS:
    for _t in P2_TARGETS:
        for _r in P2_RANKS:
            _add(p2_adam(_lr, _t, _r))
for _gp in ['0.0', '0.002']:        # PE non competitivo: solo 2 arm (t0.5) come ultimo tentativo
    _add(pe_arm(0.5, _gp))

print('BigSweep2:', len(ARMS), 'arm |',
      sum(1 for a in ARMS if a[0].startswith('P1')), 'Parte1(AdamW decode-off),',
      sum(1 for a in ARMS if a[0].startswith('P2')), 'Parte2(AdamW decode+rank),',
      sum(1 for a in ARMS if a[0].startswith('PE')), 'ProdigyEvent, 1 BPTT-ref')
print([a[0] for a in ARMS])
"""

RUN = """# Cell 3 -- esegue gli arm + push per-arm. SKIP+RESUME: ri-esegui per continuare.
import subprocess, sys, time, os, shutil, glob, datetime
import pandas as pd

def build_cli(tag, method, override):
    return ([sys.executable, 'train.py', '--training_method', method, '--epochs', str(EPOCHS)]
            + COMMON + override + ['--tag', tag])

def push_arm(tag, override):
    src = 'checkpoints/' + tag
    dst = RESULTS + '/' + tag
    if not os.path.isdir(src):
        return False
    os.makedirs(dst + '/plots', exist_ok=True)
    for f in glob.glob(src + '/*.csv') + glob.glob(src + '/*.json'):
        shutil.copy2(f, dst)
    for f in glob.glob(src + '/plots/*.png'):
        shutil.copy2(f, dst + '/plots/')
    vs = ''
    lp = dst + '/training_log.csv'
    if os.path.isfile(lp):
        edf = pd.read_csv(lp)
        if len(edf) > 0:
            vs = 'min val_data=' + str(round(edf.val_data.min(), 4)) + ' (' + str(len(edf)) + 'ep)'
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    with open(_TMP_MSG, 'w', encoding='utf-8') as fp:
        fp.write('bigsweep2: ' + tag + ' (' + ts + ')\\n\\n' + vs +
                 '\\noverride=' + ' '.join(override) + '\\nBranch: ' + BRANCH + '\\n')
    try:
        subprocess.run(['git', 'add', dst], check=True, capture_output=True)
        r = subprocess.run(['git', 'commit', '-F', _TMP_MSG], capture_output=True, text=True)
        if r.returncode != 0 and 'nothing to commit' not in (r.stdout + r.stderr):
            print('commit fail', r.stderr[-200:]); return False
        subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True, text=True)
        r2 = subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True, text=True)
        print('push OK' if r2.returncode == 0 else 'push fail ' + r2.stderr[-200:])
        return r2.returncode == 0
    finally:
        try:
            os.remove(_TMP_MSG)
        except Exception:
            pass

for tag, method, override in ARMS:
    dst_log = RESULTS + '/' + tag + '/training_log.csv'
    if os.path.isfile(dst_log) and len(pd.read_csv(dst_log)) >= EPOCHS * 0.8:
        print('[SKIP] ' + tag + ' gia presente'); continue
    print('[RUN] ' + tag)
    t0 = time.time()
    r = subprocess.run(build_cli(tag, method, override), capture_output=False)
    print('-> rc=' + str(r.returncode) + ' (' + str(round((time.time() - t0) / 60, 1)) + 'min)')
    print('pushed:', push_arm(tag, override))
print('BigSweep2: passata completata (ri-esegui per gli arm mancanti).')
"""

DIAG = """# Cell 4 -- diagnostica: per-canale (effetto decode), heatmap Parte1, verdetto vs BPTT
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display, Markdown

def _grp(t):
    if t.startswith('P1'): return 'P1_AdamW_decodeOFF'
    if t.startswith('P2'): return 'P2_AdamW_decodeON'
    if t.startswith('PE'): return 'PE_lossaware'
    return 'BPTT'

PN = ['v0', 'T', 's0', 'a', 'b']
rows = []
for tag, method, override in ARMS:
    lp = RESULTS + '/' + tag + '/training_log.csv'
    if not os.path.isfile(lp):
        rows.append({'arm': tag, 'group': _grp(tag), 'status': 'MISSING'}); continue
    d = pd.read_csv(lp); last = d.iloc[-1]
    row = {'arm': tag, 'group': _grp(tag), 'ep': len(d),
           'min_val': round(float(d.val_data.min()), 4),
           'max_grad': round(float(d.grad_norm.max()), 1),
           'completed': bool(len(d) >= EPOCHS * 0.8)}
    for c in PN:
        row['nrmse_' + c] = round(float(last.get('val_' + c + '_nrmse', float('nan'))), 3)
    rows.append(row)
summ = pd.DataFrame(rows)
summ.to_csv(RESULTS + '/bigsweep2_summary.csv', index=False)

bptt = summ[summ.group == 'BPTT']
bptt_val = float(bptt['min_val'].iloc[0]) if len(bptt) and bptt['min_val'].notna().any() else float('nan')
display(Markdown('## Riferimento BPTT: min_val = **' + str(bptt_val) + '**'))

if 'min_val' in summ.columns:
    for grp in ['P1_AdamW_decodeOFF', 'P2_AdamW_decodeON', 'PE_lossaware']:
        sub = summ[(summ.group == grp) & summ.min_val.notna()]
        if len(sub):
            display(Markdown('### ' + grp + ' (per min_val)'))
            cols = ['arm', 'ep', 'min_val', 'max_grad', 'completed'] + ['nrmse_' + c for c in PN]
            display(sub.sort_values('min_val')[cols])

# Effetto DECODE: confronto per-canale Parte1(off) vs Parte2(on) a parita' di lr/target (rank 8)
display(Markdown('### Effetto decode (Parte1 OFF vs Parte2 ON, lr3e-3 rank8)'))
cmp = []
for t in [0.5, 0.6, 0.7]:
    ts = str(t).replace('.', '')
    for tag, lab in [('P1_lr3e3_t' + ts, 'OFF'), ('P2_lr3e3_t' + ts + '_r8', 'ON')]:
        lp = RESULTS + '/' + tag + '/training_log.csv'
        if os.path.isfile(lp):
            last = pd.read_csv(lp).iloc[-1]
            cmp.append({'target': t, 'decode': lab, 'val': round(float(last.val_data), 4),
                        **{c: round(float(last.get('val_' + c + '_nrmse', float('nan'))), 3) for c in PN}})
if cmp:
    display(pd.DataFrame(cmp))

# Heatmap Parte 1 (lr x target, decode off)
Ha = np.full((len(P1_LRS), len(P1_TARGETS)), np.nan)
for i, lr in enumerate(P1_LRS):
    for j, t in enumerate(P1_TARGETS):
        lp = RESULTS + '/' + p1_arm(lr, t)[0] + '/training_log.csv'
        if os.path.isfile(lp):
            Ha[i, j] = float(pd.read_csv(lp).val_data.min())
fig, ax = plt.subplots(figsize=(6, 4.5))
im = ax.imshow(Ha, aspect='auto', cmap='viridis_r')
ax.set_title('Parte1 AdamW min_val (lr x target, decode OFF)')
ax.set_xticks(range(len(P1_TARGETS))); ax.set_xticklabels([str(t) for t in P1_TARGETS]); ax.set_xlabel('target')
ax.set_yticks(range(len(P1_LRS))); ax.set_yticklabels(P1_LRS); ax.set_ylabel('lr')
for i in range(len(P1_LRS)):
    for j in range(len(P1_TARGETS)):
        if not np.isnan(Ha[i, j]):
            ax.text(j, i, str(round(Ha[i, j], 3)), ha='center', va='center', fontsize=8)
plt.colorbar(im, ax=ax); plt.tight_layout(); plt.savefig(RESULTS + '/bigsweep2_heatmap_p1.png', dpi=110); plt.show()

# Verdetto
if 'min_val' in summ.columns:
    ev = summ[(summ.group != 'BPTT') & summ.completed.fillna(False) & summ.min_val.notna()]
    if len(ev):
        best = ev.sort_values('min_val').iloc[0]
        verdetto = 'BATTE' if best['min_val'] < bptt_val else ('PAREGGIA' if best['min_val'] <= bptt_val + 0.01 else 'sotto')
        display(Markdown('## Migliore EventProp stabile: **' + str(best['arm']) + '** min_val=' +
                         str(best['min_val']) + ' (' + verdetto + ' il BPTT ' + str(bptt_val) + ')'))
"""

PUSH_DIAG = """# Cell 5 -- push diagnostica
import subprocess, os
for f in ['bigsweep2_summary.csv', 'bigsweep2_heatmap_p1.png']:
    p = RESULTS + '/' + f
    if os.path.isfile(p):
        subprocess.run(['git', 'add', p], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'bigsweep2: diagnostica'], capture_output=True, text=True)
if r.returncode == 0 or 'nothing to commit' in (r.stdout + r.stderr):
    subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True, text=True)
    r2 = subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True, text=True)
    print('push diagnostica:', 'OK' if r2.returncode == 0 else r2.stderr[-200:])
else:
    print('commit fail', r.stderr[-200:])
"""

cells = [
    cell(INTRO, 'intro', 'markdown'),
    cell(ENV, 'env'),
    cell(CONFIG, 'config'),
    cell(RUN, 'run'),
    cell(DIAG, 'diag'),
    cell(PUSH_DIAG, 'pushdiag'),
]

nb = {
    'cells': cells,
    'metadata': {
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python', 'version': '3.10'},
    },
    'nbformat': 4,
    'nbformat_minor': 5,
}

out = os.path.join(ROOT, 'EventProp_BigSweep2.ipynb')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
print('Wrote', out)
