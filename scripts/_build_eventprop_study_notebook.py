"""EventProp_Study — confronto rigoroso BPTT vs EventProp con ottimizzatori ad-hoc.

Genera EventProp_Study.ipynb. Due paradigmi di training (BPTT+surrogato, EventProp esatto) sulla
STESSA architettura ALIF A1 (864p), a parita' di dati (mix launch/freeflow) e 50 epoche, con
ottimizzatori ottimizzati per ciascuno. Obiettivo: due metodi di training ottimizzati e riutilizzabili
+ il VIEWPOINT (struttura del gradiente esatto vs surrogato su a/b/v0).

Pre-requisiti validati localmente (scout 5ep): EventProp stabile via fix C8 (jump/lv clamp);
Prodigy si congela su EventProp -> ProdigyEvent (stima d su gradiente EMA) lo sblocca; d sovrastima
l'envelope stretto -> throttle adattivo (trend-gradiente) + decay morbido 0.99 lo assesta al confine;
+ ProbeUp (MPPT P&O) come iper-parametro sweepabile.

Arm (EventProp PRIMI -> pushati per primi):
  EVP_ADAMW              EventProp + AdamW 2e-3 + cosine_no_restart + AGC (workhorse)
  EVP_PRODIGYEVENT       + ProdigyEvent (EMA + gate rate + decay 0.99)
  EVP_PRODIGYEVENT_PROBE + ProbeUp 0.01 (candidato canonico)
  PEAK_BASELINE          BPTT champion (Prodigy + custom_restart, grad_clip none) -- riferimento
  PEAK_SINGLECYCLE       BPTT + Prodigy single-cycle canonico (cosine_no_restart + growth 1.05)
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


INTRO = """# EventProp_Study — BPTT vs EventProp (ottimizzatori ad-hoc), 50 epoche

Confronto rigoroso di due paradigmi di training sulla STESSA arch ALIF A1 (864p), stessi dati
(launch/freeflow), 50 ep. **EventProp ora allenabile** (fix C8) con due ottimizzatori: AdamW e il
nuovo **ProdigyEvent** (Prodigy adattato: stima d su gradiente EMA + throttle adattivo + ProbeUp
MPPT + gate/controllo spike-rate). Arm EventProp per primi (pushati per primi). Metriche: val_data,
NRMSE per-param, spike-rate, stabilita, + **viewpoint** struttura gradiente esatto-vs-surrogato e
correlazione per-driver. Output `results/EventProp_Study/`.
"""

ENV = """# Cell 1 -- ENV
import sys, os, subprocess
import importlib.util as _imu
RESULTS = 'results/EventProp_Study'
BRANCH = 'EventProp_Study'
LAUNCH_MIX = 'highway:0.20,urban:0.15,truck:0.10,mixed:0.05,freeflow:0.15,launch:0.35'
CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'
_TMP_MSG = '/tmp/evp_msg.txt' if os.path.isdir('/tmp') else 'evp_msg.txt'
os.makedirs(RESULTS, exist_ok=True)
for pkg in ['prodigyopt', 'pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
for f in ['core/prodigy_event.py', 'core/eventprop.py']:
    assert os.path.isfile(f), 'missing ' + f
br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
print('[EventProp_Study] ENV OK | branch =', br)
"""

CONFIG = """# Cell 2 -- definizione arm (EventProp PRIMI). Flag comuni + override per-arm.
EPOCHS = 50
COMMON = ['--max_steps_per_epoch', '100', '--batch_size', '8', '--val_batch_size', '32',
          '--seq_len', '50', '--cf_hidden_size', '32', '--cf_rank', '8', '--cf_max_delay', '6',
          '--cf_bit_shift', '3', '--lambda_data', '1.0', '--lambda_phys', '0.1', '--lambda_ou', '0.05',
          '--lambda_bc', '1.0', '--lambda_sr', '0.5', '--scenario_mix', LAUNCH_MIX, '--cut_in_ratio', '0.0',
          '--noise_scale', '0.0', '--po2_enabled', '1', '--n_train', '1500', '--n_val', '300',
          '--data_cache', CACHE, '--max_inf_streak', '99999', '--early_stop_patience', '0',
          '--max_epoch_explosion_streak', '3', '--epoch_explosion_threshold', '10000.0',
          '--epoch_explosion_frac', '0.5', '--grad_clip', 'agc', '--agc_lambda', '0.01']

# ProdigyEvent settings condivisi (canonico single-cycle + throttle adattivo)
PE = ['--optimizer', 'prodigy_event', '--lr', '0.5', '--max_lr', '0.5', '--scheduler', 'cosine_no_restart',
      '--prodigy_growth_rate', '1.05', '--prodigy_betas', '0.9,0.99', '--prodigy_d_coef', '1.0',
      '--prodigy_d0', '1e-6', '--prodigy_weight_decay', '0.01', '--prodigy_use_bias_correction', '1',
      '--prodigy_safeguard_warmup', '1', '--prodigy_ema_beta', '0.9', '--prodigy_instab_kappa', '2.0',
      '--prodigy_rate_band', '0.10,0.25', '--prodigy_d_decay', '0.99']
ADAMW = ['--optimizer', 'adamw', '--lr', '2e-3', '--max_lr', '2e-3', '--scheduler', 'cosine_no_restart']
# BPTT champion (custom_restart) e single-cycle: decode calibrato (init_bias_shift + tau per-channel)
BPTT_DECODE = ['--cf_init_bias_shift', '1', '--cf_logit_tau_per_channel', '10.0,3.0,10.0,3.0,3.0']
PRODIGY_STD = ['--optimizer', 'prodigy', '--lr', '0.5', '--prodigy_betas', '0.9,0.99', '--prodigy_d_coef', '1.0',
               '--prodigy_d0', '1e-6', '--prodigy_weight_decay', '0.01', '--prodigy_use_bias_correction', '1',
               '--prodigy_safeguard_warmup', '1']

# (tag, training_method, [override]) — EventProp PRIMI
ARMS = [
    ('EVP_ADAMW',              'eventprop_alif_full', ADAMW),
    ('EVP_PRODIGYEVENT',       'eventprop_alif_full', PE),
    ('EVP_PRODIGYEVENT_PROBE', 'eventprop_alif_full', PE + ['--prodigy_probe_up', '0.01']),
    # PEAK_BASELINE: replica FEDELE del champion LS3_PEAK_R0_launch_d03 -> grad_clip 'none'
    # (override sull'agc del COMMON). Con growth inf + custom_restart l'agc destabilizzava d.
    ('PEAK_BASELINE',          'baseline', BPTT_DECODE + PRODIGY_STD + ['--scheduler', 'custom_restart',
                                '--restart_T0', '12', '--restart_decay', '0.3', '--restart_warmup_epochs', '2',
                                '--prodigy_growth_rate', 'inf', '--T0', '5', '--grad_clip', 'none']),
    ('PEAK_SINGLECYCLE',       'baseline', BPTT_DECODE + PRODIGY_STD + ['--scheduler', 'cosine_no_restart',
                                '--max_lr', '0.5', '--prodigy_growth_rate', '1.05']),
]
print('Arm (in ordine, EventProp primi):', [a[0] for a in ARMS])
"""

RUN = """# Cell 3 -- esegue ogni arm (subprocess train.py) + push per-arm (EventProp primi -> visibili prima)
import subprocess, sys, time, os, shutil, glob, datetime
import pandas as pd

def build_cli(tag, method, override):
    return ([sys.executable, 'train.py', '--training_method', method, '--epochs', str(EPOCHS)]
            + COMMON + override + ['--tag', tag])

def push_arm(tag, override):
    src = 'checkpoints/' + tag; dst = RESULTS + '/' + tag
    if not os.path.isdir(src):
        return False
    os.makedirs(dst + '/plots', exist_ok=True)
    for f in glob.glob(src + '/*.csv') + glob.glob(src + '/*.json') + glob.glob(src + '/*.pt'):
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
        fp.write('results (EventProp_Study): ' + tag + ' (' + ts + ')\\n\\n' + vs +
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
        try: os.remove(_TMP_MSG)
        except Exception: pass

for tag, method, override in ARMS:
    dst_log = RESULTS + '/' + tag + '/training_log.csv'
    if os.path.isfile(dst_log) and len(pd.read_csv(dst_log)) >= EPOCHS * 0.8:
        print('[SKIP] ' + tag + ' gia presente'); continue
    print('[RUN] ' + tag)
    t0 = time.time()
    r = subprocess.run(build_cli(tag, method, override), capture_output=False)
    print('-> rc=' + str(r.returncode) + ' (' + str(round((time.time()-t0)/60, 1)) + 'min)')
    print('pushed:', push_arm(tag, override))
print('EventProp_Study: tutti gli arm completati.')
"""

DIAG = """# Cell 4 -- diagnostica comparativa + VIEWPOINT (struttura gradiente) + correlazione per-driver
import os, torch, numpy as np, pandas as pd
from core.network import build_model
from data.generator import generate_dataset
from train import CFDataset
from torch.utils.data import DataLoader
from config import SEED
from IPython.display import display, Markdown

PN = ['v0', 'T', 's0', 'a', 'b']
MAP = [('v0', 0, 0), ('s0', 1, 2), ('a', 2, 3), ('b', 3, 4)]
TAGS = [a[0] for a in ARMS]

# dataset di valutazione condiviso (per correlazione per-driver, come L1d)
val = generate_dataset(250, base_seed=SEED + 99)
dl = DataLoader(CFDataset(val, seq_len=100, stride=100), batch_size=64, shuffle=False)

def load_arm(tag, method):
    p = RESULTS + '/' + tag + '/best_model.pt'
    if not os.path.isfile(p):
        return None
    ck = torch.load(p, map_location='cpu', weights_only=False)
    m = build_model(variant=method, hidden_size=32, rank=8, max_delay=6, bit_shift=3)
    m.load_state_dict(ck['model_state']); m.eval()
    return m

def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1]) if a.std() > 1e-9 and b.std() > 1e-9 else 0.0

rows = []; grad_struct = {}
arm_method = {a[0]: a[1] for a in ARMS}
for tag in TAGS:
    lp = RESULTS + '/' + tag + '/training_log.csv'
    bp = RESULTS + '/' + tag + '/training_batch_log.csv'
    if not os.path.isfile(lp):
        print('[skip] ' + tag + ' (assente)'); continue
    e = pd.read_csv(lp)
    row = {'arm': tag, 'epochs': len(e), 'val_data_min': round(float(e.val_data.min()), 4),
           'spike_rate': round(float(e.spike_rate.iloc[-1]), 3)}
    for p in ['v0', 'T', 's0', 'a', 'b']:
        c = 'val_' + p + '_nrmse'
        if c in e.columns:
            row['nrmse_' + p] = round(float(e[c].iloc[e.val_data.idxmin()]), 3)
    if os.path.isfile(bp):
        b = pd.read_csv(bp)
        gn = pd.to_numeric(b.gn_total_preclip, errors='coerce')
        row['gn_max'] = float(gn.max()); row['n_expl'] = int((gn > 100).sum())
        gc = [c for c in b.columns if 'gn_decoded' in c]
        if gc:
            m = b[gc].apply(pd.to_numeric, errors='coerce').tail(500).mean()
            tot = m.sum()
            grad_struct[tag] = {c.replace('gn_decoded_', ''): (100 * m[c] / tot if tot > 0 else 0) for c in gc}
    # correlazione per-driver sul best_model
    mdl = load_arm(tag, arm_method[tag])
    if mdl is not None:
        PMu, GT = [], []
        with torch.no_grad():
            for x, y, mask, pgt in dl:
                PMu.append(mdl.forward_sequence(x).mean(dim=1).numpy()); GT.append(pgt.numpy())
        PMu = np.concatenate(PMu); GT = np.concatenate(GT)
        for nm, gi, pi in MAP:
            row['r_' + nm] = round(corr(GT[:, gi], PMu[:, pi]), 3)
    rows.append(row)

dfE = pd.DataFrame(rows).set_index('arm')
dfE.to_csv(RESULTS + '/eventprop_summary.csv')
display(Markdown('## EventProp_Study — sintesi per arm (val_data, NRMSE, stabilita, correlazione per-driver)'))
display(dfE)
print('Baseline storico: BPTT~0.22; EventProp storico best 0.2226 (ma fragile 6/11). r_a~0.39 r_b~-0.37 (L1d).')
"""

PLOTVERDICT = """# Cell 5 -- grafici (val curves, viewpoint gradiente, d-trajectory) + verdetto + push
import os, json, subprocess
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from IPython.display import display, Markdown
TAGS = [a[0] for a in ARMS]

# P1: curve val_data per arm
fig, ax = plt.subplots(1, 2, figsize=(17, 5))
for tag in TAGS:
    lp = RESULTS + '/' + tag + '/training_log.csv'
    if os.path.isfile(lp):
        e = pd.read_csv(lp); ax[0].plot(e.epoch, e.val_data, marker='.', label=tag, alpha=0.85)
ax[0].set_xlabel('epoca'); ax[0].set_ylabel('val_data'); ax[0].set_title('P1 - val_data per arm')
ax[0].legend(fontsize=7); ax[0].grid(alpha=0.3); ax[0].set_ylim(0.15, 0.5)
# P2: VIEWPOINT - struttura gradiente per-canale (esatto EventProp vs surrogato BPTT)
if 'grad_struct' in dir() and grad_struct:
    arms_g = list(grad_struct.keys()); chans = ['v0', 'T', 's0', 'a', 'b']
    xb = np.arange(len(chans)); w = 0.8 / max(len(arms_g), 1)
    for i, tag in enumerate(arms_g):
        vals = [grad_struct[tag].get(c, 0) for c in chans]
        ax[1].bar(xb + i * w, vals, w, label=tag, alpha=0.8)
    ax[1].set_xticks(xb + w * len(arms_g) / 2); ax[1].set_xticklabels(chans)
    ax[1].set_ylabel('% gradiente decoded per canale'); ax[1].set_title('P2 - VIEWPOINT: struttura gradiente (esatto vs surrogato)')
    ax[1].legend(fontsize=6); ax[1].grid(alpha=0.3, axis='y')
fig.tight_layout(); fig.savefig(RESULTS + '/eventprop_curves_viewpoint.png', dpi=130); plt.show()

# P3: traiettoria d per gli arm ProdigyEvent
fig2, axd = plt.subplots(figsize=(9, 4.5))
for tag in TAGS:
    bp = RESULTS + '/' + tag + '/training_batch_log.csv'
    if os.path.isfile(bp):
        b = pd.read_csv(bp); d = pd.to_numeric(b.prodigy_d, errors='coerce')
        if d.notna().any() and d.max() > 0:
            axd.plot(np.arange(len(d)), d, label=tag, alpha=0.85)
axd.set_xlabel('batch'); axd.set_ylabel('prodigy d'); axd.set_yscale('log')
axd.set_title('P3 - traiettoria adattatore d (ProdigyEvent: si assesta? Prodigy-std: frozen?)')
axd.legend(fontsize=7); axd.grid(alpha=0.3)
fig2.tight_layout(); fig2.savefig(RESULTS + '/eventprop_d_trajectory.png', dpi=130); plt.show()

# Verdetto
v = []
if 'dfE' in dir() and dfE is not None and len(dfE) > 0:
    best = dfE['val_data_min'].idxmin()
    v.append('Miglior val_data: %s = %.4f' % (best, dfE.loc[best, 'val_data_min']))
    evp = [t for t in dfE.index if t.startswith('EVP')]
    bptt = [t for t in dfE.index if t.startswith('PEAK')]
    if evp and bptt:
        be = dfE.loc[evp, 'val_data_min'].min(); bb = dfE.loc[bptt, 'val_data_min'].min()
        v.append('EventProp best %.4f vs BPTT best %.4f -> %s' % (be, bb,
                 'EventProp pareggia/batte' if be <= bb + 0.005 else 'BPTT meglio di %.4f' % (be - bb)))
    pe = [t for t in dfE.index if 'PRODIGYEVENT' in t or 'PE_' in t]
    if pe:
        v.append('ProdigyEvent arm: ' + ', '.join('%s=%.4f' % (t, dfE.loc[t, 'val_data_min']) for t in pe))
    if 'r_b' in dfE.columns:
        v.append('Correlazione per-driver r_b: ' + ', '.join('%s=%.2f' % (t, dfE.loc[t, 'r_b']) for t in dfE.index))
    out = {'summary': json.loads(dfE.to_json()),
           'grad_struct': grad_struct if 'grad_struct' in dir() else {}, 'verdict': v}
    json.dump(out, open(RESULTS + '/eventprop_results.json', 'w'), indent=2)
print('VERDETTO EventProp_Study:')
for s in v:
    print(' -', s)
subprocess.run(['git', 'add', RESULTS], capture_output=True)
r = subprocess.run(['git', 'commit', '-m', 'EventProp_Study: confronto BPTT vs EventProp (AdamW/ProdigyEvent) - diagnostica + viewpoint'],
                   capture_output=True, text=True)
print(r.stdout[-200:] if r.returncode == 0 else r.stderr[-200:])
subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True)
subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
print('EventProp_Study verdict pushed.')
"""


def main():
    cells = [cell(INTRO, 'intro', 'markdown'),
             cell(ENV, 'env'), cell(CONFIG, 'config'), cell(RUN, 'run'),
             cell(DIAG, 'diag'), cell(PLOTVERDICT, 'verdict')]
    nb = {'cells': cells,
          'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                       'language_info': {'name': 'python', 'version': '3.x'}},
          'nbformat': 4, 'nbformat_minor': 5}
    out = os.path.join(ROOT, 'EventProp_Study.ipynb')
    json.dump(nb, open(out, 'w', encoding='utf-8'), indent=1)
    print('Wrote', out)


if __name__ == '__main__':
    main()
