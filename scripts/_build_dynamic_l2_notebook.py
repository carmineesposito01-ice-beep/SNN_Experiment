"""Dynamic_Study L2 — TRAINING: identificazione di a/b via reparam (geo,ratio) + per-regime.

Primo studio con TRAINING di Dynamic_Study. La diagnosi L1x e' chiusa e CONCLUSIVA:
  - Il champion (LS3_PEAK_R0_launch_d03) NON aveva supervisione su a/b (lambda_a/b_aux=0):
    a/b emergevano solo da L_data (accel), che vincola √(ab) ma NON il rapporto a/b.
  - Risultato: per-driver a debole (r=0.39), b ANTI-correlato (r=-0.37). Soluzione non-workaround:
    supervisionare ESPLICITAMENTE la direzione molle log(a/b), concentrandola dove a/b sono
    osservabili (i transitori, Studio B).

Ablazione (6 varianti, training da zero, ricetta champion identica salvo le leve L2):
  V0_BASELINE    champion as-is (nessuna sup a/b)            -> riproduce il tetto (controllo)
  V1_INDEP_AUX   + aux indipendente su a,b                  -> la sup naive aiuta o insegna un prior?
  V2_GEO_RATIO   + aux geo-mean + log-ratio (lambda 0.3)    -> reparam batte l'indipendente?
  V3_RATIO_STR   geo 0.3 + ratio 1.0                        -> martellare la direzione molle
  V4_REGIME      V3 + regime_gamma 4 (concentra ai transit) -> i transitori sbloccano a/b?
  V5_REGIME_STR  geo 0.3 + ratio 2.0 + regime_gamma 8       -> spinta massima

Per OGNI variante, dopo il training, batteria diagnostica COMPLETA (readout NORMALE = deploy reale,
niente memoryless): NRMSE per-param, correlazione per-driver r (come L1d, metrica chiave: r_b da
-0.37 a positivo?), decomposizione √(ab)/rapporto, NRMSE per-regime (transitorio vs non).

Genera Dynamic_Study_L2.ipynb. Checkpoint/training solo su Azure -> celle saltano con grazia se assente.
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


INTRO = """# Dynamic_Study L2 — TRAINING: identificare a/b via reparam (geo, log-ratio) + per-regime

Primo studio con training. Diagnosi L1x: il champion non supervisionava a/b → b anti-correlato
(vincolato solo via √ab da L_data). Soluzione di principio (no workaround): **supervisionare la
direzione molle log(a/b)**, concentrata ai **transitori** dove a/b sono osservabili (Studio B).

Ablazione 6 varianti (ricetta champion identica, varia solo la leva L2):
**V0** baseline (controllo) · **V1** aux indipendente a,b · **V2** geo+ratio λ0.3 ·
**V3** ratio forte 1.0 · **V4** +regime γ4 (transitori) · **V5** ratio 2.0+regime γ8.

Per ogni variante: training + batteria diagnostica completa (readout NORMALE = deploy reale).
Metrica chiave: **r_b da -0.37 → positivo** (e r_a su), NRMSE a/b giù, senza danneggiare v0/T/s0.
Output in `results/Dynamic_Study/L2/`. Push per-variante.
"""

ENV = """# Cell 1 -- ENV
import sys, os, subprocess
import importlib.util as _imu
RESULTS = 'results/Dynamic_Study/L2'
BRANCH = 'Dynamic_Study'
LAUNCH_MIX = 'highway:0.20,urban:0.15,truck:0.10,mixed:0.05,freeflow:0.15,launch:0.35'
CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'
_TMP_MSG = '/tmp/l2_msg.txt' if os.path.isdir('/tmp') else 'l2_msg.txt'
os.makedirs(RESULTS, exist_ok=True)
for pkg in ['prodigyopt', 'pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
print('[L2] ENV OK | branch =', br)
"""

CONFIG = """# Cell 2 -- ricetta champion (BASE) + 6 varianti L2 (override delle sole leve)
# BASE = LS3_PEAK_R0_launch_d03 ESATTO (cosi' V0 riproduce il champion).
BASE = dict(
    optimizer='prodigy', lr=0.5, d0=1e-6, d_coef=1.0, growth_rate='inf',
    epochs=50, max_steps_per_epoch=100, seq_len=50,
    hidden_size=32, rank=8, max_delay=6, bit_shift=3,
    lambda_data=1.0, lambda_phys=0.1, lambda_ou=0.05, lambda_bc=1.0, lambda_sr=0.5,
    lambda_T_aux=0.0, lambda_v0_aux=0.0, lambda_s0_aux=0.0, lambda_a_aux=0.0, lambda_b_aux=0.0,
    lambda_geo_aux=0.0, lambda_ratio_aux=0.0, regime_gamma=0.0, regime_thr=0.5,
    scenario_mix=LAUNCH_MIX, cut_in_ratio=0.0, noise_scale=0.0, po2_enabled=1,
    init_bias_shift=1, tau_init=1.0, tau_final=1.0, tau_schedule='const',
    tau_per_channel='10.0,3.0,10.0,3.0,3.0',
    scheduler='custom_restart', T0=5, restart_T0=12, restart_decay=0.3,
    restart_lr_after=-1.0, restart_warmup_epochs=2, restart_adaptive=0,
    max_epoch_explosion_streak=2, epoch_explosion_threshold=10000.0, epoch_explosion_frac=0.5,
    grad_clip='none', agc_lambda=0.01, cache_path=CACHE, n_train=1500, n_val=300,
)
# (tag, override) — solo le leve L2 cambiano tra varianti
VARIANTS = [
    ('L2_V0_BASELINE',   {}),
    ('L2_V1_INDEP_AUX',  dict(lambda_a_aux=0.3, lambda_b_aux=0.3)),
    ('L2_V2_GEO_RATIO',  dict(lambda_geo_aux=0.3, lambda_ratio_aux=0.3)),
    ('L2_V3_RATIO_STR',  dict(lambda_geo_aux=0.3, lambda_ratio_aux=1.0)),
    ('L2_V4_REGIME',     dict(lambda_geo_aux=0.3, lambda_ratio_aux=1.0, regime_gamma=4.0)),
    ('L2_V5_REGIME_STR', dict(lambda_geo_aux=0.3, lambda_ratio_aux=2.0, regime_gamma=8.0)),
]
print('Varianti L2:', [t for t, _ in VARIANTS])
"""

RUN = """# Cell 3 -- training di ogni variante (subprocess train.py) + push per-variante
import subprocess, sys, time, os, shutil, glob, datetime
import pandas as pd

def build_cli(tag, ov):
    e = dict(BASE); e.update(ov)
    cli = [sys.executable, 'train.py', '--training_method', 'baseline',
        '--epochs', str(e['epochs']), '--max_steps_per_epoch', str(e['max_steps_per_epoch']),
        '--batch_size', '8', '--val_batch_size', '32', '--seq_len', str(e['seq_len']),
        '--cf_hidden_size', str(e['hidden_size']), '--cf_rank', str(e['rank']),
        '--cf_max_delay', str(e['max_delay']), '--cf_bit_shift', str(e['bit_shift']),
        '--cf_init_bias_shift', str(e['init_bias_shift']),
        '--cf_logit_tau_init', str(e['tau_init']), '--cf_logit_tau_final', str(e['tau_final']),
        '--cf_logit_tau_schedule', e['tau_schedule'], '--cf_logit_tau_per_channel', e['tau_per_channel'],
        '--lambda_data', str(e['lambda_data']), '--lambda_phys', str(e['lambda_phys']),
        '--lambda_ou', str(e['lambda_ou']), '--lambda_bc', str(e['lambda_bc']),
        '--lambda_sr', str(e['lambda_sr']), '--lambda_T_aux', str(e['lambda_T_aux']),
        '--lambda_v0_aux', str(e['lambda_v0_aux']), '--lambda_s0_aux', str(e['lambda_s0_aux']),
        '--lambda_a_aux', str(e['lambda_a_aux']), '--lambda_b_aux', str(e['lambda_b_aux']),
        '--lambda_geo_aux', str(e['lambda_geo_aux']), '--lambda_ratio_aux', str(e['lambda_ratio_aux']),
        '--regime_gamma', str(e['regime_gamma']), '--regime_thr', str(e['regime_thr']),
        '--scenario_mix', e['scenario_mix'], '--cut_in_ratio', str(e['cut_in_ratio']),
        '--noise_scale', str(e['noise_scale']), '--po2_enabled', str(e['po2_enabled']),
        '--n_train', str(e['n_train']), '--n_val', str(e['n_val']),
        '--max_inf_streak', '99999', '--early_stop_patience', '0',
        '--data_cache', e['cache_path'], '--optimizer', e['optimizer'],
        '--lr', str(e['lr']), '--max_lr', str(e['lr']), '--scheduler', e['scheduler'],
        '--T0', str(e['T0']), '--restart_T0', str(e['restart_T0']),
        '--restart_decay', str(e['restart_decay']), '--restart_lr_after', str(e['restart_lr_after']),
        '--restart_warmup_epochs', str(e['restart_warmup_epochs']),
        '--restart_adaptive', str(e['restart_adaptive']),
        '--prodigy_betas', '0.9,0.99', '--prodigy_d_coef', str(e['d_coef']),
        '--prodigy_d0', str(e['d0']), '--prodigy_weight_decay', '0.01',
        '--prodigy_use_bias_correction', '1', '--prodigy_safeguard_warmup', '1',
        '--prodigy_growth_rate', str(e['growth_rate']),
        '--max_epoch_explosion_streak', str(e['max_epoch_explosion_streak']),
        '--epoch_explosion_threshold', str(e['epoch_explosion_threshold']),
        '--epoch_explosion_frac', str(e['epoch_explosion_frac']),
        '--grad_clip', e['grad_clip'], '--agc_lambda', str(e['agc_lambda']), '--tag', tag]
    return cli

def push_run(tag, ov):
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
        fp.write('results (Dynamic_Study L2): ' + tag + ' (' + ts + ')\\n\\n' + vs +
                 '\\nleve=' + str(ov) + '\\nBranch: ' + BRANCH + '\\n')
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

for tag, ov in VARIANTS:
    dst_log = RESULTS + '/' + tag + '/training_log.csv'
    if os.path.isfile(dst_log) and len(pd.read_csv(dst_log)) >= BASE['epochs'] * 0.8:
        print('[SKIP] ' + tag + ' gia presente'); continue
    print('[RUN] ' + tag + ' | leve=' + str(ov))
    t0 = time.time()
    r = subprocess.run(build_cli(tag, ov), capture_output=False)
    print('-> rc=' + str(r.returncode) + ' (' + str(round((time.time()-t0)/60, 1)) + 'min)')
    print('pushed:', push_run(tag, ov))
print('Training L2 completato.')
"""

DIAG = """# Cell 4 -- batteria diagnostica per variante (readout NORMALE = deploy reale)
import os, torch, numpy as np, pandas as pd
from core.network import build_model
from data.generator import generate_dataset
from train import CFDataset
from torch.utils.data import DataLoader
from config import SEED, NORM_DV_MAX
from IPython.display import display, Markdown

PN = ['v0', 'T', 's0', 'a', 'b']
# mappa (nome, col GT in params_gt, col pred in params_seq). GT: v0=0,s0=1,a=2,b=3
MAP = [('v0', 0, 0), ('s0', 1, 2), ('a', 2, 3), ('b', 3, 4)]

# dataset di valutazione condiviso (stesso seed di L1d per comparabilita')
val = generate_dataset(250, base_seed=SEED + 99)
dl = DataLoader(CFDataset(val, seq_len=100, stride=100), batch_size=64, shuffle=False)

def load_variant(tag):
    p = RESULTS + '/' + tag + '/best_model.pt'
    if not os.path.isfile(p):
        return None
    ck = torch.load(p, map_location='cpu', weights_only=False)
    m = build_model(variant='baseline', hidden_size=32, rank=8, max_delay=6, bit_shift=3)
    m.load_state_dict(ck['model_state']); m.eval()
    return m

def diagnose(m):
    RANGE = (m.param_hi - m.param_lo).detach().cpu().numpy()
    # accumula: per-finestra media (per r); per-step se (per NRMSE per-param e per-regime)
    PMu, GTw = [], []
    se = {p: 0.0 for p in PN}; n = {p: 0 for p in PN}
    se_tr = {'a': 0.0, 'b': 0.0}; n_tr = {'a': 0, 'b': 0}     # transitorio
    se_nt = {'a': 0.0, 'b': 0.0}; n_nt = {'a': 0, 'b': 0}     # non-transitorio
    with torch.no_grad():
        for x, y, mask, pgt in dl:
            ps = m.forward_sequence(x)                         # (B,T,5) readout NORMALE
            PMu.append(ps.mean(dim=1).numpy()); GTw.append(pgt.numpy())
            # NRMSE per-param (T da y[:,:,1]; v0/s0/a/b da pgt costante)
            se['T'] += (mask * (ps[:, :, 1] - y[:, :, 1]) ** 2).sum().item(); n['T'] += mask.sum().item()
            for nm, gi, pi in MAP:
                gt = pgt[:, gi].unsqueeze(1)
                se[nm] += ((ps[:, :, pi] - gt) ** 2).sum().item(); n[nm] += ps[:, :, pi].numel()
            # NRMSE per-regime su a,b (transitorio = |v_dot|>0.5)
            vdot = y[:, :, 0].numpy(); trans = np.abs(vdot) > 0.5
            for nm, gi, pi in [('a', 2, 3), ('b', 3, 4)]:
                err2 = (ps[:, :, pi].numpy() - pgt[:, gi:gi+1].numpy()) ** 2
                se_tr[nm] += err2[trans].sum(); n_tr[nm] += trans.sum()
                se_nt[nm] += err2[~trans].sum(); n_nt[nm] += (~trans).sum()
    PMu = np.concatenate(PMu); GTw = np.concatenate(GTw)
    nrmse = {p: float(np.sqrt(se[p] / max(n[p], 1)) / RANGE[PN.index(p)]) for p in PN}
    def corr(gt, pr):
        return float(np.corrcoef(gt, pr)[0, 1]) if gt.std() > 1e-9 and pr.std() > 1e-9 else 0.0
    r = {nm: corr(GTw[:, gi], PMu[:, pi]) for nm, gi, pi in MAP}
    # decomposizione √(ab) e rapporto a/b (per-finestra, dalla media)
    pa, pb = PMu[:, 3], PMu[:, 4]; ga, gb = GTw[:, 2], GTw[:, 3]
    geo_p = np.sqrt(np.clip(pa*pb, 1e-6, None)); geo_g = np.sqrt(np.clip(ga*gb, 1e-6, None))
    rat_p = np.log(np.clip(pa, 1e-3, None)/np.clip(pb, 1e-3, None))
    rat_g = np.log(np.clip(ga, 1e-3, None)/np.clip(gb, 1e-3, None))
    nrmse_a_tr = float(np.sqrt(se_tr['a']/max(n_tr['a'], 1)) / RANGE[3])
    nrmse_a_nt = float(np.sqrt(se_nt['a']/max(n_nt['a'], 1)) / RANGE[3])
    nrmse_b_tr = float(np.sqrt(se_tr['b']/max(n_tr['b'], 1)) / RANGE[4])
    nrmse_b_nt = float(np.sqrt(se_nt['b']/max(n_nt['b'], 1)) / RANGE[4])
    return dict(
        nrmse_v0=round(nrmse['v0'], 3), nrmse_T=round(nrmse['T'], 3), nrmse_s0=round(nrmse['s0'], 3),
        nrmse_a=round(nrmse['a'], 3), nrmse_b=round(nrmse['b'], 3),
        r_v0=round(r['v0'], 3), r_s0=round(r['s0'], 3), r_a=round(r['a'], 3), r_b=round(r['b'], 3),
        r_geo=round(corr(geo_g, geo_p), 3), r_ratio=round(corr(rat_g, rat_p), 3),
        nrmse_a_transient=round(nrmse_a_tr, 3), nrmse_a_nontrans=round(nrmse_a_nt, 3),
        nrmse_b_transient=round(nrmse_b_tr, 3), nrmse_b_nontrans=round(nrmse_b_nt, 3),
    )

rows = {}
for tag, ov in VARIANTS:
    m = load_variant(tag)
    if m is None:
        print('[skip] ' + tag + ' (checkpoint assente)'); continue
    rows[tag] = diagnose(m)
    print('[OK] diagnosticata ' + tag)
if rows:
    dfL2 = pd.DataFrame(rows).T
    dfL2.to_csv(RESULTS + '/l2_diagnostics.csv')
    display(Markdown('## L2 — diagnostica per variante (readout normale). Baseline L1d: r_a=0.39, r_b=-0.37'))
    display(dfL2)
else:
    print('[skip] nessuna variante diagnosticata'); dfL2 = None
"""

PLOTVERDICT = """# Cell 5 -- grafici comparativi + verdetto + push
import json, subprocess
import numpy as np, pandas as pd, matplotlib.pyplot as plt
from IPython.display import display, Markdown
if 'dfL2' in dir() and dfL2 is not None and len(dfL2) > 0:
    tags = list(dfL2.index)
    fig, ax = plt.subplots(1, 3, figsize=(19, 5))
    # P1: r_a, r_b per variante (metrica chiave: b da negativo a positivo)
    xb = np.arange(len(tags)); w = 0.38
    ax[0].bar(xb - w/2, dfL2['r_a'].values, w, label='r_a', color='tab:blue')
    ax[0].bar(xb + w/2, dfL2['r_b'].values, w, label='r_b', color='tab:red')
    ax[0].axhline(0, color='k', lw=0.8); ax[0].axhline(0.39, color='tab:blue', ls=':', lw=1, label='r_a baseline L1d')
    ax[0].axhline(-0.37, color='tab:red', ls=':', lw=1, label='r_b baseline L1d')
    ax[0].set_xticks(xb); ax[0].set_xticklabels(tags, rotation=30, ha='right', fontsize=7)
    ax[0].set_ylabel('correlazione per-driver r'); ax[0].set_title('P1 - discriminazione a/b (r_b>0 = b sanato)')
    ax[0].legend(fontsize=7); ax[0].grid(alpha=0.3, axis='y')
    # P2: NRMSE a,b per variante
    ax[1].bar(xb - w/2, dfL2['nrmse_a'].values, w, label='NRMSE a', color='tab:blue')
    ax[1].bar(xb + w/2, dfL2['nrmse_b'].values, w, label='NRMSE b', color='tab:red')
    ax[1].set_xticks(xb); ax[1].set_xticklabels(tags, rotation=30, ha='right', fontsize=7)
    ax[1].set_ylabel('NRMSE'); ax[1].set_title('P2 - NRMSE a/b (giu = meglio)')
    ax[1].legend(fontsize=7); ax[1].grid(alpha=0.3, axis='y')
    # P3: NRMSE a transitorio vs non (legge i transitori?)
    ax[2].bar(xb - w/2, dfL2['nrmse_a_transient'].values, w, label='a transitorio', color='tab:green')
    ax[2].bar(xb + w/2, dfL2['nrmse_a_nontrans'].values, w, label='a non-trans', color='tab:olive')
    ax[2].set_xticks(xb); ax[2].set_xticklabels(tags, rotation=30, ha='right', fontsize=7)
    ax[2].set_ylabel('NRMSE a'); ax[2].set_title('P3 - a ai transitori vs no (legge il segnale dove c-e?)')
    ax[2].legend(fontsize=7); ax[2].grid(alpha=0.3, axis='y')
    fig.suptitle('Dynamic_Study L2 - ablazione reparam/regime per identificare a/b')
    fig.tight_layout(); fig.savefig(RESULTS + '/l2_comparison.png', dpi=130); plt.show()

    base = dfL2.loc['L2_V0_BASELINE'] if 'L2_V0_BASELINE' in dfL2.index else dfL2.iloc[0]
    # criterio: b sanato (r_b>0.15) senza danneggiare v0/T/s0 (NRMSE entro +0.03 del baseline)
    def healthy(row):
        return (row['nrmse_v0'] <= base['nrmse_v0'] + 0.03 and row['nrmse_T'] <= base['nrmse_T'] + 0.03 and
                row['nrmse_s0'] <= base['nrmse_s0'] + 0.03)
    cand = [(t, dfL2.loc[t]) for t in tags if healthy(dfL2.loc[t])]
    fixed_b = [(t, row) for t, row in cand if row['r_b'] > 0.15]
    v = []
    v.append('Baseline V0: r_a=%.2f r_b=%.2f | NRMSE a=%.2f b=%.2f (riproduce il tetto)'
             % (base['r_a'], base['r_b'], base['nrmse_a'], base['nrmse_b']))
    if fixed_b:
        best = max(fixed_b, key=lambda tr: tr[1]['r_b'])
        bt, br = best
        v.append('=> b SANATO: %s porta r_b da %.2f a %.2f (r_a %.2f), NRMSE b %.2f->%.2f, '
                 'senza danneggiare v0/T/s0. La reparam/regime FUNZIONA.'
                 % (bt, base['r_b'], br['r_b'], br['r_a'], base['nrmse_b'], br['nrmse_b']))
    else:
        best_r = max(tags, key=lambda t: dfL2.loc[t]['r_b'])
        v.append('=> b NON sanato: miglior r_b = %.2f (%s), ancora <=0.15. La sola supervisione '
                 'reparam/regime non basta a rendere a/b identificabili dal readout per-istante -> '
                 'serve la leva architetturale (encoding transitorio/derivata) = L2b.' % (dfL2.loc[best_r]['r_b'], best_r))
    # legge i transitori? a_transient deve scendere sotto a_nontrans nelle varianti regime
    for t in tags:
        rr = dfL2.loc[t]
        if rr['nrmse_a_transient'] < rr['nrmse_a_nontrans'] - 0.02:
            v.append('   %s: a piu accurato AI TRANSITORI (%.2f < %.2f) -> inizia a leggere il segnale dove c-e.'
                     % (t, rr['nrmse_a_transient'], rr['nrmse_a_nontrans']))
    out = {'table': json.loads(dfL2.to_json()), 'verdict': v}
    json.dump(out, open(RESULTS + '/l2_results.json', 'w'), indent=2)
    print('VERDETTO L2:')
    for s in v:
        print(' -', s)
    subprocess.run(['git', 'add', RESULTS], capture_output=True)
    r = subprocess.run(['git', 'commit', '-m', 'Dynamic_Study L2: ablazione reparam/regime per identificare a/b - diagnostica + verdetto'],
                       capture_output=True, text=True)
    print(r.stdout[-200:] if r.returncode == 0 else r.stderr[-200:])
    subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True)
    subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
    print('L2 verdict pushed.')
else:
    print('[skip] nessuna diagnostica da riassumere')
"""


def main():
    cells = [cell(INTRO, 'intro', 'markdown'),
             cell(ENV, 'env'), cell(CONFIG, 'config'), cell(RUN, 'run'),
             cell(DIAG, 'diag'), cell(PLOTVERDICT, 'verdict')]
    nb = {'cells': cells,
          'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                       'language_info': {'name': 'python', 'version': '3.x'}},
          'nbformat': 4, 'nbformat_minor': 5}
    out = os.path.join(ROOT, 'Dynamic_Study_L2.ipynb')
    json.dump(nb, open(out, 'w', encoding='utf-8'), indent=1)
    print('Wrote', out)


if __name__ == '__main__':
    main()
