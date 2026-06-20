"""Dynamic_Study L1.5 — il readout MEMORYLESS di a/b e' un guadagno quasi-gratis?

L1 ha scoperto che la memoria ricorrente e' DANNOSA per a/b: ablandola (stato resettato
a ogni step) a passa 0.331 -> 0.143, b 0.178 -> 0.149 (vicino al LM locale ideale 0.12/0.18).
Prima di impegnare un training (L2), L1.5 verifica SENZA training se questo si traduce in un
guadagno deployabile:

  EXP A  Statico multi-seed: l'ablazione di L1 e' robusta su seed FRESCHI (non SEED+99)?
         Tabella NRMSE per-canale normal vs memoryless vs HYBRID (v0/T/s0 da memoria, a/b memoryless).
  EXP B  Sanity closed-loop: l'ego guidato col readout HYBRID resta SICURO (zero collisioni
         come oracolo/normal) e non peggiora comfort/string-stability? a/b memoryless potrebbe
         introdurre jitter che destabilizza il controller -> e' il rischio da escludere.
         Riusa utils/closed_loop_eval.py (NON lo modifica). Self-test: il loop in modalita'
         'normal' deve riprodurre esattamente simulate() validato (guardia anti-drift fisica).

Esito -> decide se l'ibrido e' un win a costo zero (L2 si riduce/cambia) o se serve il training.
Genera Dynamic_Study_L1p5.ipynb. Checkpoint solo su Azure -> celle col modello saltano se assente.
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


INTRO = """# Dynamic_Study L1.5 — il readout memoryless di a/b e' un guadagno quasi-gratis?

Niente training: solo il checkpoint `LS3_PEAK_R0_launch_d03`. L1 ha mostrato che la memoria
ricorrente DANNEGGIA a/b (ablandola: a 0.33->0.14, b 0.18->0.15, vicino al LM locale ideale).
Qui verifichiamo se l'ibrido (a/b memoryless, v0/T/s0 con memoria) e' un guadagno **deployabile**:

1. **EXP A — statico multi-seed**: l'ablazione e' robusta su seed freschi? NRMSE normal vs memoryless vs hybrid.
2. **EXP B — sanity closed-loop**: l'ego guidato dall'ibrido resta sicuro (0 collisioni) e non perde comfort/string-stability?

Output in `results/Dynamic_Study/L1p5/`. Push automatico finale.
"""

ENV = """# Cell 1 -- ENV
import sys, os, subprocess
import importlib.util as _imu
RESULTS = 'results/Dynamic_Study/L1p5'
BRANCH = 'Dynamic_Study'
os.makedirs(RESULTS, exist_ok=True)
for pkg in ['pandas', 'matplotlib']:
    if _imu.find_spec(pkg) is None:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
for f in ['utils/closed_loop_eval.py', 'core/network.py', 'data/generator.py']:
    assert os.path.isfile(f), 'missing ' + f
br = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True).stdout.strip()
print('[L1.5] ENV OK | branch =', br)
"""

LOAD = """# Cell 2 -- checkpoint + helper di caricamento (servono DUE istanze per l'ibrido closed-loop)
import os, torch, numpy as np
from core.network import build_model

CKPT = 'checkpoints/LS3_PEAK_R0_launch_d03/best_model.pt'
PN = ['v0', 'T', 's0', 'a', 'b']
_BUILD = dict(variant='baseline', hidden_size=32, rank=8, max_delay=6, bit_shift=3)

def load_model():
    # istanza fresca con i pesi del champion (None se checkpoint assente)
    if not os.path.isfile(CKPT):
        return None
    ck = torch.load(CKPT, map_location='cpu', weights_only=False)
    m = build_model(**_BUILD)
    m.load_state_dict(ck['model_state']); m.eval()
    return m

model = load_model()
if model is not None:
    RANGE = (model.param_hi - model.param_lo).detach().cpu().numpy()  # [v0,T,s0,a,b]
    print('[OK] modello', sum(p.numel() for p in model.parameters()), 'param | range', np.round(RANGE, 2))
else:
    RANGE = None
    print('[skip] checkpoint assente:', CKPT, '-> esegui su Azure')
"""

HELP = """# Cell 3 -- helper NRMSE: forward normale (memoria) vs ablato (memoryless), per-canale
import torch, numpy as np
_NR_GT_IDX = {'v0': 0, 's0': 1, 'a': 2, 'b': 3}   # colonna in params_gt (T escluso, e' dinamico in y)

def forward_ablated(m, x):
    # reset dello stato ricorrente PRIMA di ogni step -> nessuna memoria cross-step (per-istante)
    B, T, _ = x.shape
    out = []
    for t in range(T):
        m.reset_state(B, x.device)
        out.append(m.forward_step(x[:, t, :]).unsqueeze(1))
    return torch.cat(out, dim=1)

def accumulate_nrmse(ps, y, mask, pgt, se, n):
    se['T'] += (mask * (ps[:, :, 1] - y[:, :, 1]) ** 2).sum().item(); n['T'] += mask.sum().item()
    for p, gi in _NR_GT_IDX.items():
        pi = PN.index(p); gt = pgt[:, gi].unsqueeze(1)
        se[p] += ((ps[:, :, pi] - gt) ** 2).sum().item(); n[p] += ps[:, :, pi].numel()

def finalize(se, n):
    return {p: float(np.sqrt(se[p] / max(n[p], 1)) / RANGE[PN.index(p)]) for p in PN}
"""

EXPA = """# Cell 4 -- EXP A: ablazione statica su SEED FRESCHI (robustezza del finding L1) + ibrido
import torch, numpy as np, pandas as pd, matplotlib.pyplot as plt
from IPython.display import display, Markdown
from torch.utils.data import DataLoader
from data.generator import generate_dataset
from train import CFDataset
from config import SEED

if model is not None:
    SEEDS = [SEED + 11, SEED + 23, SEED + 37]   # FRESCHI: L1 usava SEED+99
    rows_norm, rows_abl = [], []
    for sd in SEEDS:
        val = generate_dataset(80, base_seed=sd)
        dl = DataLoader(CFDataset(val, seq_len=100, stride=100), batch_size=64, shuffle=False)
        se_n = {p: 0.0 for p in PN}; n_n = {p: 0 for p in PN}
        se_a = {p: 0.0 for p in PN}; n_a = {p: 0 for p in PN}
        with torch.no_grad():
            for x, y, mask, pgt in dl:
                accumulate_nrmse(model.forward_sequence(x), y, mask, pgt, se_n, n_n)
                accumulate_nrmse(forward_ablated(model, x), y, mask, pgt, se_a, n_a)
        rows_norm.append(finalize(se_n, n_n)); rows_abl.append(finalize(se_a, n_a))
    dfn = pd.DataFrame(rows_norm, index=SEEDS); dfa = pd.DataFrame(rows_abl, index=SEEDS)
    # tabella sintesi: media +/- std su seed, per normal / memoryless / hybrid (a,b<-memoryless)
    summ = pd.DataFrame({
        'normal_mean': dfn.mean(), 'normal_std': dfn.std(),
        'memoryless_mean': dfa.mean(), 'memoryless_std': dfa.std(),
    })
    summ['hybrid_mean'] = summ['normal_mean'].copy()
    for p in ['a', 'b']:
        summ.loc[p, 'hybrid_mean'] = summ.loc[p, 'memoryless_mean']
    summ['gain_memoryless'] = summ['memoryless_mean'] - summ['normal_mean']   # <0 = memoryless meglio
    summ = summ.round(4)
    summ.to_csv(RESULTS + '/l1p5_static.csv')
    display(Markdown('## EXP A - NRMSE per-canale, media su 3 seed freschi (normal vs memoryless vs hybrid)'))
    display(summ)
    # barre: normal vs memoryless con errore std su seed
    x_ = np.arange(len(PN)); w = 0.38
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x_ - w/2, summ['normal_mean'][PN], w, yerr=summ['normal_std'][PN], capsize=4,
           label='normale (memoria)', color='tab:green')
    ax.bar(x_ + w/2, summ['memoryless_mean'][PN], w, yerr=summ['memoryless_std'][PN], capsize=4,
           label='memoryless (stato resettato/step)', color='tab:red')
    ax.set_xticks(x_); ax.set_xticklabels(PN); ax.set_ylabel('NRMSE = RMSE / range')
    ax.set_title('EXP A - ablazione statica su 3 seed freschi (barra = std tra seed)')
    ax.legend(); ax.grid(alpha=0.3, axis='y')
    plt.tight_layout(); plt.savefig(RESULTS + '/l1p5_static.png', dpi=130); plt.show()
    gain_ab = float(0.5 * (summ.loc['a', 'gain_memoryless'] + summ.loc['b', 'gain_memoryless']))
    print('guadagno memoryless medio su a,b =', round(gain_ab, 4), '(negativo = memoryless meglio)')
else:
    print('[skip] modello assente'); summ = None
"""

EXPB = """# Cell 5 -- EXP B: sanity closed-loop dell'ibrido (riusa closed_loop_eval, NON lo modifica)
import numpy as np, pandas as pd, torch
import matplotlib.pyplot as plt
from IPython.display import display, Markdown
from utils.closed_loop_eval import (simulate, build_scenarios, all_metrics,
                                    string_stability_gain, _norm_obs)
from data.generator import _sample_scenario, parse_scenario_mix
from config import DT, ACC_AL_TAU, ACC_COOLNESS
from core.network import CF_FSNN_Net

def sim_modes(m_prop, m_free, params_gt, v_leader, s_init, v_init, cut_in, mode, device='cpu'):
    # Specchio FEDELE di closed_loop_eval.simulate (stessa fisica balistica, a_l_filt, cut_in,
    # collisione). Differenza SOLO nella sorgente dei 5 parametri:
    #   oracle     -> params veri costanti
    #   normal     -> m_prop, stato propagato (== simulate originale)
    #   memoryless -> m_free, stato resettato a ogni step
    #   hybrid     -> v0,T,s0 da m_prop (propagato); a,b da m_free (memoryless)
    N = len(v_leader); alpha_al = float(np.exp(-DT / ACC_AL_TAU))
    pg = torch.tensor(params_gt, dtype=torch.float32).view(1, 5)
    if m_prop is not None:
        m_prop.eval(); m_prop.reset_state(1, device)
    if m_free is not None:
        m_free.eval()
    s = float(s_init); v = float(v_init); a_l_filt = 0.0; vl_prev = float(v_leader[0])
    series = {k: [] for k in ('s', 'v', 'vl', 'dv', 'a_ego')}; params_used = []; collided = False
    with torch.no_grad():
        for t in range(N):
            if cut_in is not None and t == int(cut_in[0]):
                s = float(cut_in[1])
            vl = float(v_leader[t]); dv = v - vl
            obs = _norm_obs(s, v, dv, vl).to(device)
            if mode == 'oracle':
                params = pg
            elif mode == 'normal':
                params = m_prop.forward_step(obs)
            elif mode == 'memoryless':
                m_free.reset_state(1, device); params = m_free.forward_step(obs)
            elif mode == 'hybrid':
                p_prop = m_prop.forward_step(obs)                       # propaga (v0,T,s0)
                m_free.reset_state(1, device); p_free = m_free.forward_step(obs)  # a,b memoryless
                params = p_prop.clone(); params[0, 3] = p_free[0, 3]; params[0, 4] = p_free[0, 4]
            else:
                raise ValueError(mode)
            a_l_raw = (vl - vl_prev) / DT
            a_l_filt = alpha_al * a_l_filt + (1.0 - alpha_al) * a_l_raw; vl_prev = vl
            a_ego = float(CF_FSNN_Net.acc_iidm_accel(
                torch.tensor([max(s, 1e-3)]), torch.tensor([v]), torch.tensor([dv]),
                torch.tensor([a_l_filt]), params, coolness=ACC_COOLNESS)[0])
            series['s'].append(s); series['v'].append(v); series['vl'].append(vl)
            series['dv'].append(dv); series['a_ego'].append(a_ego)
            params_used.append(params.view(-1).cpu().numpy())
            v = max(0.0, v + a_ego * DT); s = s + (vl - v) * DT
            if s <= 0.0:
                collided = True; break
    out = {k: np.asarray(val, dtype=np.float64) for k, val in series.items()}
    out['params'] = np.asarray(params_used, dtype=np.float64); out['collided'] = collided
    out['min_gap'] = float(s) if collided else float(out['s'].min())
    return out

if model is not None:
    # --- SELF-TEST: sim_modes('normal') deve riprodurre simulate() validato (guardia anti-drift) ---
    m_prop = load_model(); m_free = load_model()
    _r = np.random.default_rng(7)
    p0, _, _, _ = _sample_scenario(_r, scenario_mix=parse_scenario_mix('highway:1.0'))
    pgt0 = np.array([p0['v0'], p0['T'], p0['s0'], p0['a'], p0['b']], dtype=np.float32)
    _scen = build_scenarios(pgt0, N=600, rng=np.random.default_rng(123))
    ok = True
    for sname, vl, s_i, v_i, cut in _scen[:3]:
        ref = simulate(load_model(), pgt0, vl, s_i, v_i, cut_in=cut)        # originale validato
        mine = sim_modes(m_prop, m_free, pgt0, vl, s_i, v_i, cut, 'normal') # mio loop, modalita' normal
        same = (ref['collided'] == mine['collided']) and np.isclose(ref['min_gap'], mine['min_gap'], atol=1e-6)
        ok = ok and same
        print('self-test', sname, '| collided', ref['collided'], '==', mine['collided'],
              '| min_gap', round(ref['min_gap'], 4), 'vs', round(mine['min_gap'], 4), '|', 'OK' if same else 'MISMATCH')
    assert ok, 'self-test FALLITO: sim_modes(normal) != simulate() -> la fisica e\\' divergente, STOP'
    print('[self-test OK] il loop ibrido riproduce la fisica di simulate() validato\\n')

    # --- sanity: 4 modalita' x N_DRIVERS x scenari avversari ---
    N_DRIVERS = 12; N_STEPS = 600
    MIX = parse_scenario_mix('highway:0.4,urban:0.3,truck:0.2,mixed:0.1')
    _rd = np.random.default_rng(7)
    drivers = []
    for _ in range(N_DRIVERS):
        p, _, stype, _ = _sample_scenario(_rd, scenario_mix=MIX)
        drivers.append((stype, np.array([p['v0'], p['T'], p['s0'], p['a'], p['b']], dtype=np.float32)))
    MODES = ['oracle', 'normal', 'memoryless', 'hybrid']
    rows = []
    for di, (dtype, pgt) in enumerate(drivers):
        scen = build_scenarios(pgt, N=N_STEPS, rng=np.random.default_rng(100 + di))
        for sname, vl, s_i, v_i, cut in scen:
            for mode in MODES:
                tr = sim_modes(m_prop, m_free, pgt, vl, s_i, v_i, cut, mode)
                mt = all_metrics(tr)
                mt['string_gain'] = string_stability_gain(tr) if sname == 'sinusoidal' else float('nan')
                mt.update({'mode': mode, 'scenario': sname, 'driver': di, 'driver_type': dtype})
                rows.append(mt)
    dfB = pd.DataFrame(rows)
    dfB.to_csv(RESULTS + '/l1p5_closedloop_raw.csv', index=False)
    cl = dfB.groupby('mode').agg(
        n=('collided', 'size'),
        collision_rate=('collided', 'mean'),
        worst_min_gap=('min_gap', 'min'),
        max_DRAC=('max_DRAC', 'max'),
        rms_accel=('rms_accel', 'mean'),
        rms_jerk=('rms_jerk', 'mean'),
        rms_gap_error=('rms_gap_error', 'mean'),
        string_gain=('string_gain', 'mean'),
    ).reindex(MODES).round(3)
    cl.to_csv(RESULTS + '/l1p5_closedloop_summary.csv')
    display(Markdown('## EXP B - sanity closed-loop per modalita di readout (oracle / normal / memoryless / hybrid)'))
    display(cl)
    print('CRITERIO ibrido OK: collision_rate ~ normal/oracle, worst_min_gap non peggiore, '
          'string_gain<1, rms_jerk non >> normal (no jitter da a/b memoryless).')
    # plot: collision rate + jerk + string gain per modalita'
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    for ax, col, ttl in [(axes[0], 'collision_rate', 'collision rate (0 = sicuro)'),
                         (axes[1], 'rms_jerk', 'rms jerk (comfort; alto = jitter)'),
                         (axes[2], 'string_gain', 'string gain (<1 stabile)')]:
        ax.bar(range(len(cl)), cl[col].values, color='tab:blue', alpha=0.8)
        ax.set_xticks(range(len(cl))); ax.set_xticklabels(cl.index, rotation=20, ha='right')
        ax.set_title(ttl); ax.grid(alpha=0.3, axis='y')
    axes[2].axhline(1.0, color='r', ls='--', lw=1)
    fig.suptitle('EXP B - sanity closed-loop: l\\'ibrido resta sicuro/stabile come normal?')
    fig.tight_layout(); fig.savefig(RESULTS + '/l1p5_closedloop.png', dpi=130); plt.show()
else:
    print('[skip] modello assente'); cl = None
"""

VERDICT = """# Cell 6 -- verdetto combinato + push
import json, subprocess
if model is not None:
    gain_ab = float(0.5 * (summ.loc['a', 'gain_memoryless'] + summ.loc['b', 'gain_memoryless']))
    # robustezza statica: memoryless meglio su a E b in media (margine oltre la std tra seed)
    static_robust = bool(
        (summ.loc['a', 'gain_memoryless'] < 0) and (summ.loc['b', 'gain_memoryless'] < 0) and
        (abs(summ.loc['a', 'gain_memoryless']) > summ.loc['a', 'memoryless_std'])
    )
    # closed-loop: l'ibrido non aggiunge collisioni e non peggiora gap/jitter/string vs normal
    c_h = float(cl.loc['hybrid', 'collision_rate']); c_n = float(cl.loc['normal', 'collision_rate'])
    g_h = float(cl.loc['hybrid', 'worst_min_gap']); g_n = float(cl.loc['normal', 'worst_min_gap'])
    j_h = float(cl.loc['hybrid', 'rms_jerk']); j_n = float(cl.loc['normal', 'rms_jerk'])
    s_h = float(cl.loc['hybrid', 'string_gain'])
    cl_safe = bool((c_h <= c_n + 1e-9) and (g_h >= g_n - 0.5) and (j_h <= 1.25 * j_n + 1e-9) and (s_h < 1.0))
    v = []
    if static_robust:
        v.append('STATICO: ablazione ROBUSTA su 3 seed freschi (guadagno memoryless a,b = %.3f, oltre la std). '
                 'Il finding L1 non era seed-specifico.' % gain_ab)
    else:
        v.append('STATICO: guadagno memoryless su a,b NON robusto tra seed (%.3f) -> L1 forse seed-specifico, '
                 'rivedere prima di sfruttarlo.' % gain_ab)
    if cl_safe:
        v.append('CLOSED-LOOP: l\\'ibrido e\\' SICURO/STABILE come normal (coll %.3f vs %.3f, min_gap %.2f vs %.2f, '
                 'jerk %.2f vs %.2f, string_gain %.2f<1). a/b memoryless NON destabilizza il controller.'
                 % (c_h, c_n, g_h, g_n, j_h, j_n, s_h))
    else:
        v.append('CLOSED-LOOP: l\\'ibrido PEGGIORA sicurezza/comfort/stabilita\\' (coll %.3f vs %.3f, min_gap %.2f vs %.2f, '
                 'jerk %.2f vs %.2f, string_gain %.2f). a/b memoryless introduce jitter -> serve L2 (consistency reg).'
                 % (c_h, c_n, g_h, g_n, j_h, j_n, s_h))
    if static_robust and cl_safe:
        v.append('=> DECISIONE: readout IBRIDO = guadagno a/b a costo zero, deployabile. '
                 'L2 si concentra su uncertainty head (+ eventuale recupero v0/s0), non sul recupero a/b via training.')
    elif static_robust and not cl_safe:
        v.append('=> DECISIONE: a/b memoryless e\\' accurato ma non deployabile cosi\\'. L2 = training con '
                 'regolarizzatore di consistenza memoryless + loss per-regime + uncertainty head.')
    else:
        v.append('=> DECISIONE: rivedere il finding L1 prima di L2.')
    out = {'gain_ab': gain_ab, 'static_robust': static_robust, 'closedloop_hybrid_safe': cl_safe,
           'static': json.loads(summ.to_json()), 'closedloop': json.loads(cl.to_json()), 'verdict': v}
    json.dump(out, open(RESULTS + '/l1p5_results.json', 'w'), indent=2)
    print('VERDETTO L1.5:')
    for s in v:
        print(' -', s)
    subprocess.run(['git', 'add', RESULTS], capture_output=True)
    r = subprocess.run(['git', 'commit', '-m', 'Dynamic_Study L1.5: readout ibrido (a/b memoryless) - statico multi-seed + sanity closed-loop'],
                       capture_output=True, text=True)
    print(r.stdout[-200:] if r.returncode == 0 else r.stderr[-200:])
    subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True)
    subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True)
    print('L1.5 pushed.')
else:
    print('[skip] niente da pushare (checkpoint assente)')
"""


def main():
    cells = [cell(INTRO, 'intro', 'markdown'),
             cell(ENV, 'env'), cell(LOAD, 'load'), cell(HELP, 'help'),
             cell(EXPA, 'expa'), cell(EXPB, 'expb'), cell(VERDICT, 'verdict')]
    nb = {'cells': cells,
          'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                       'language_info': {'name': 'python', 'version': '3.x'}},
          'nbformat': 4, 'nbformat_minor': 5}
    out = os.path.join(ROOT, 'Dynamic_Study_L1p5.ipynb')
    json.dump(nb, open(out, 'w', encoding='utf-8'), indent=1)
    print('Wrote', out)


if __name__ == '__main__':
    main()
