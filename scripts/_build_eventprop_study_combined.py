"""EventProp Study — COMBINATO esaustivo (Stadio 1: solo da log gia' pushati, zero Azure).

Aggrega le 5 run dello studio EventProp (Study, Spectral_Sweep, BigSweep, BigSweep2, BigSweep3)
in una cartella unica results/EventProp_Study/combined/ con csv/png "totali" cross-sweep.

Fondazione (questo file, v1): ingestione -> backbone + tassonomia famiglie + manifest copertura.
  - combined_arm_index.csv : 1 riga/arm con metadata (sweep, famiglia, hyperparam) + metriche finali.
  - combined_epoch_long.csv: arm x epoca (tidy) per le curve di dinamica/stabilita'.
Le figure (T1..T8) si aggiungono sopra questi due csv (passate successive, stesso file).

Anti-ambiguita' (dall'audit): namespace <sweep>/<arm>; metrica val_data/NRMSE confrontabile SOLO
sul val comune (cache_1500_launch_cut0.0_ou0.0.pt); DS_* (cache_ds_*) tenuti a parte; flag
aborted = ran_ep < budget_ep; has_diag = la run logga rec_spectral_radius/marginal_frac.
"""
import os
import re
import json
import glob
import csv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, 'results')
OUTDIR = os.path.join(RESULTS, 'EventProp_Study', 'combined')
COMMON_VAL = 'data/cache_1500_launch_cut0.0_ou0.0.pt'
PN = ['v0', 'T', 's0', 'a', 'b']

# Ordine cronologico delle campagne (per la narrativa del progresso).
SWEEPS = [
    ('EventProp_Study', 'Study'),
    ('EventProp_Spectral_Sweep', 'Spectral'),
    ('EventProp_BigSweep', 'BigSweep'),
    ('EventProp_BigSweep2', 'BigSweep2'),
    ('EventProp_BigSweep3', 'BigSweep3'),
]


def _read_csv_rows(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def _fnum(x, default=float('nan')):
    try:
        v = float(x)
        return v
    except (TypeError, ValueError):
        return default


def classify_family(tag, cfg, sweep_label):
    """Famiglia-metodo dell'arm dal config (+ tag/sweep dove il config non basta)."""
    method = (cfg.get('training_method') or '').lower()
    opt = (cfg.get('optimizer') or '').lower()
    tag_l = tag.lower()
    decode_on = bool(cfg.get('cf_init_bias_shift'))
    lam_spec = _fnum(cfg.get('eventprop_lambda_spectral'), 0.0)
    seed = cfg.get('seed', 42)

    # 1) BPTT champion (baseline) — riferimento
    if method == 'baseline' or tag_l.startswith('bptt'):
        return 'BPTT_champion'
    # 2) Dataset study
    if tag.startswith('DS_'):
        return 'Dataset'
    # 3) ProdigyEvent (PE): prodigy come optimizer su eventprop
    if opt == 'prodigy' or tag_l.startswith('pe_') or 'prodigyevent' in tag_l:
        return 'ProdigyEvent'
    # 4) Spectral-constraint sweep (campagna Spectral): griglia lambda x target
    if sweep_label == 'Spectral' or tag_l.startswith('spec_'):
        return 'Spectral_sweep'
    # 5) AdamW (la famiglia di produzione) — distingui decode on/off e seed-variant
    if opt == 'adamw' or method == 'eventprop_alif_full':
        base = 'AdamW_decodeON' if decode_on else 'AdamW_decodeOFF'
        if seed not in (42, '42', None):
            base += '_seed'
        return base
    # 6) resto della Study esplorativa
    return 'Study_misc'


def ingest():
    arms = []
    epoch_rows = []
    for folder, label in SWEEPS:
        for lp in sorted(glob.glob(os.path.join(RESULTS, folder, '*', 'training_log.csv'))):
            armdir = os.path.dirname(lp)
            tag = os.path.basename(armdir)
            cfgp = os.path.join(armdir, 'config_snapshot.json')
            cfg = json.load(open(cfgp)) if os.path.isfile(cfgp) else {}
            rows = _read_csv_rows(lp)
            if not rows:
                continue
            cols = set(rows[0].keys())
            last = rows[-1]
            vdata = [_fnum(r.get('val_data')) for r in rows]
            vdata = [v for v in vdata if v == v]
            val_min = min(vdata) if vdata else float('nan')
            final3 = sum(vdata[-3:]) / len(vdata[-3:]) if vdata else float('nan')
            nrmse = {c: _fnum(last.get('val_%s_nrmse' % c)) for c in PN}
            nrmse_valid = [nrmse[c] for c in PN if nrmse[c] == nrmse[c]]
            cache = cfg.get('data_cache')
            budget = int(cfg.get('epochs', len(rows)))
            ran = len(rows)
            time_total = sum(_fnum(r.get('time_s'), 0.0) for r in rows)
            arm = {
                'key': '%s/%s' % (label, tag),
                'sweep': label, 'arm': tag,
                'family': classify_family(tag, cfg, label),
                'optimizer': cfg.get('optimizer'), 'scheduler': cfg.get('scheduler'),
                'lr': _fnum(cfg.get('lr')),
                'spectral_lambda': _fnum(cfg.get('eventprop_lambda_spectral'), 0.0),
                'spectral_target': _fnum(cfg.get('eventprop_spectral_target')),
                'rank': int(cfg['cf_rank']) if cfg.get('cf_rank') else None,
                'decode_on': bool(cfg.get('cf_init_bias_shift')),
                'seed': cfg.get('seed', 42),
                'cache': cache, 'common_val': (cache == COMMON_VAL),
                'budget_ep': budget, 'ran_ep': ran, 'aborted': ran < budget,
                'has_diag': ('rec_spectral_radius' in cols and 'marginal_frac' in cols),
                'val_data_min': round(val_min, 4) if val_min == val_min else None,
                'val_data_final3': round(final3, 4) if final3 == final3 else None,
                'nrmse_mean': round(sum(nrmse_valid) / len(nrmse_valid), 3) if nrmse_valid else None,
                'time_total_s': round(time_total, 1),
                'final_spectral_radius': round(_fnum(last.get('rec_spectral_radius')), 3)
                if 'rec_spectral_radius' in cols else None,
                'final_spike_rate': round(_fnum(last.get('spike_rate')), 3) if 'spike_rate' in cols else None,
            }
            for c in PN:
                arm['nrmse_' + c] = round(nrmse[c], 3) if nrmse[c] == nrmse[c] else None
            arms.append(arm)
            # epoch long-form (solo le colonne utili alle curve)
            keep = ['epoch', 'train_total', 'train_data', 'val_total', 'val_data', 'val_phys',
                    'val_ou', 'val_bc', 'val_sr', 'lr', 'grad_norm', 'spike_rate', 'time_s',
                    'marginal_frac', 'mean_vth_at_spike', 'mean_spike_margin', 'rec_spectral_radius',
                    'prodigy_d', 'prodigy_lr_eff', 'val_T_tracking_corr']
            for c in PN:
                keep += ['val_%s_nrmse' % c, 'val_%s_intra_std' % c, 'val_%s_pred_mean' % c]
            for i, r in enumerate(rows):
                er = {'key': arm['key'], 'sweep': label, 'arm': tag, 'family': arm['family']}
                for k in keep:
                    er[k] = r.get(k)
                epoch_rows.append(er)
    return arms, epoch_rows


def write_backbone(arms, epoch_rows):
    os.makedirs(OUTDIR, exist_ok=True)
    # arm index
    cols = ['key', 'sweep', 'arm', 'family', 'optimizer', 'scheduler', 'lr', 'spectral_lambda',
            'spectral_target', 'rank', 'decode_on', 'seed', 'cache', 'common_val', 'budget_ep',
            'ran_ep', 'aborted', 'has_diag', 'val_data_min', 'val_data_final3', 'nrmse_mean'] \
        + ['nrmse_' + c for c in PN] + ['time_total_s', 'final_spectral_radius', 'final_spike_rate']
    p1 = os.path.join(OUTDIR, 'combined_arm_index.csv')
    with open(p1, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for a in sorted(arms, key=lambda x: (x['val_data_min'] is None, x['val_data_min'])):
            w.writerow({k: a.get(k) for k in cols})
    # epoch long
    p2 = os.path.join(OUTDIR, 'combined_epoch_long.csv')
    if epoch_rows:
        ecols = list(epoch_rows[0].keys())
        with open(p2, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=ecols)
            w.writeheader()
            w.writerows(epoch_rows)
    return p1, p2


def print_manifest(arms):
    from collections import Counter
    print('=== COPERTURA per sweep ===')
    by_sweep = Counter(a['sweep'] for a in arms)
    for _, label in SWEEPS:
        sub = [a for a in arms if a['sweep'] == label]
        cv = sum(a['common_val'] for a in sub)
        ab = sum(a['aborted'] for a in sub)
        hd = sum(a['has_diag'] for a in sub)
        print('  %-10s arm=%2d  common_val=%2d  aborted=%2d  has_diag=%2d' % (label, len(sub), cv, ab, hd))
    print('  TOTALE arm =', len(arms))
    print('\n=== FAMIGLIE ===')
    for fam, n in Counter(a['family'] for a in arms).most_common():
        print('  %-22s %d' % (fam, n))
    print('\n=== ProdigyEvent (sospetto NRMSE) — arm + NRMSE + val_data ===')
    pe = [a for a in arms if a['family'] == 'ProdigyEvent']
    for a in sorted(pe, key=lambda x: (x['nrmse_mean'] is None, x['nrmse_mean'])):
        print('  %-28s NRMSE=%-6s val_data=%-7s aborted=%s' %
              (a['key'], a['nrmse_mean'], a['val_data_min'], a['aborted']))
    print('\n=== TOP-5 NRMSE assoluti (chi ha la NRMSE piu bassa di tutti?) ===')
    valid = [a for a in arms if a['nrmse_mean'] is not None and a['common_val']]
    for a in sorted(valid, key=lambda x: x['nrmse_mean'])[:5]:
        print('  %-28s NRMSE=%-6s val_data=%-7s fam=%s' %
              (a['key'], a['nrmse_mean'], a['val_data_min'], a['family']))


# ---------------------------------------------------------------------------
# FIGURE — riferimenti champion (dallo storico, per le linee guida)
CHAMP_VAL = 0.1926
CHAMP_NRMSE = 0.258
FAM_COLORS = {
    'BPTT_champion': '#d62728', 'AdamW_decodeON': '#1f77b4', 'AdamW_decodeON_seed': '#17becf',
    'AdamW_decodeOFF': '#7f7f7f', 'ProdigyEvent': '#2ca02c', 'Spectral_sweep': '#9467bd',
    'Dataset': '#8c564b', 'Study_misc': '#bcbd22',
}
SWEEP_ORDER = ['Study', 'Spectral', 'BigSweep', 'BigSweep2', 'BigSweep3']


def _safe(fig_fn):
    def wrap(*a, **k):
        try:
            return fig_fn(*a, **k)
        except Exception as e:
            import traceback
            print('[FIG ERROR] %s -> %s' % (fig_fn.__name__, e))
            traceback.print_exc()
    return wrap


@_safe
def fig_ranking(arms):
    import matplotlib.pyplot as plt
    sub = [a for a in arms if a['common_val'] and a['val_data_min'] is not None]
    sub = sorted(sub, key=lambda x: x['val_data_min'])
    fig, ax = plt.subplots(figsize=(9, max(5, 0.22 * len(sub))))
    ys = range(len(sub))
    colors = [FAM_COLORS.get(a['family'], '#333') for a in sub]
    ax.barh(list(ys), [a['val_data_min'] for a in sub], color=colors,
            hatch=['//' if a['aborted'] else '' for a in sub], edgecolor='white')
    ax.set_yticks(list(ys))
    ax.set_yticklabels(['%s%s' % (a['key'], ' (abort)' if a['aborted'] else '') for a in sub], fontsize=5)
    ax.invert_yaxis()
    ax.axvline(CHAMP_VAL, color='red', ls='--', lw=1, label='champion 0.1926')
    ax.set_xlabel('val_data (FISICA) — piu corto = meglio')
    ax.set_title('F1 — Ranking globale val_data (99 arm su val comune; // = aborted)')
    from matplotlib.patches import Patch
    handles = [Patch(color=c, label=f) for f, c in FAM_COLORS.items() if any(a['family'] == f for a in sub)]
    ax.legend(handles=handles + [plt.Line2D([0], [0], color='red', ls='--', label='champion')],
              fontsize=6, ncol=2, loc='lower right')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, 'combined_F1_ranking.png'), dpi=120)
    plt.close()
    return 'F1_ranking'


@_safe
def fig_pareto(arms):
    import matplotlib.pyplot as plt
    sub = [a for a in arms if a['common_val'] and a['nrmse_mean'] is not None and a['val_data_min'] is not None]
    fig, ax = plt.subplots(figsize=(8, 6))
    for fam in FAM_COLORS:
        fs = [a for a in sub if a['family'] == fam]
        if fs:
            ax.scatter([a['val_data_min'] for a in fs], [a['nrmse_mean'] for a in fs],
                       c=FAM_COLORS[fam], label=fam, s=36, alpha=0.85,
                       edgecolors='k', linewidths=0.3)
    # evidenzia PE (sospetto NRMSE) con anello
    for a in sub:
        if a['family'] == 'ProdigyEvent':
            ax.scatter([a['val_data_min']], [a['nrmse_mean']], facecolors='none',
                       edgecolors='green', s=120, linewidths=1.2)
    ax.scatter([CHAMP_VAL], [CHAMP_NRMSE], marker='*', s=320, c='red', edgecolors='k', label='champion', zorder=5)
    ax.set_xlabel('val_data (FISICA) -> meglio a sinistra')
    ax.set_ylabel('NRMSE medio -> meglio in basso')
    ax.set_title('F2 — Pareto globale: fisica vs identificazione (anello verde = ProdigyEvent)')
    ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, 'combined_F2_pareto.png'), dpi=120)
    plt.close()
    return 'F2_pareto'


@_safe
def fig_nrmse_heat(arms):
    import numpy as np
    import matplotlib.pyplot as plt
    # media per famiglia + best-arm per famiglia (compatto e leggibile)
    fams = [f for f in FAM_COLORS if any(a['family'] == f and a['common_val'] for a in arms)]
    M = np.full((len(fams), len(PN)), np.nan)
    for i, f in enumerate(fams):
        fs = [a for a in arms if a['family'] == f and a['common_val'] and a['nrmse_' + PN[0]] is not None]
        for j, c in enumerate(PN):
            vals = [a['nrmse_' + c] for a in fs if a['nrmse_' + c] is not None]
            if vals:
                M[i, j] = float(np.mean(vals))
    fig, ax = plt.subplots(figsize=(6, 4.2))
    im = ax.imshow(M, aspect='auto', cmap='YlOrRd')
    ax.set_xticks(range(len(PN)))
    ax.set_xticklabels(PN)
    ax.set_yticks(range(len(fams)))
    ax.set_yticklabels(fams, fontsize=8)
    for i in range(len(fams)):
        for j in range(len(PN)):
            if M[i, j] == M[i, j]:
                ax.text(j, i, '%.2f' % M[i, j], ha='center', va='center', fontsize=7)
    ax.set_title('F3 — NRMSE per-canale, media per famiglia')
    plt.colorbar(im, ax=ax, label='NRMSE')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, 'combined_F3_nrmse_heat.png'), dpi=120)
    plt.close()
    return 'F3_nrmse_heat'


@_safe
def fig_pinn_composition(arms, epoch_rows):
    import pandas as pd
    import matplotlib.pyplot as plt
    df = pd.DataFrame(epoch_rows)
    for c in ['val_data', 'val_phys', 'val_ou', 'val_bc', 'val_sr']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    # best arm per famiglia (min val_data) tra i common-val
    best = {}
    for a in arms:
        if not a['common_val'] or a['val_data_min'] is None:
            continue
        f = a['family']
        if f not in best or a['val_data_min'] < best[f]['val_data_min']:
            best[f] = a
    comps = ['val_data', 'val_phys', 'val_ou', 'val_bc', 'val_sr']
    keys = [best[f]['key'] for f in best]
    rows = []
    for k in keys:
        last = df[df.key == k].iloc[-1]
        rows.append([float(last[c]) for c in comps])
    import numpy as np
    rows = np.array(rows)
    fig, ax = plt.subplots(figsize=(max(7, 1.1 * len(keys)), 4.6))
    bottom = np.zeros(len(keys))
    for j, c in enumerate(comps):
        ax.bar(range(len(keys)), rows[:, j], bottom=bottom, label=c.replace('val_', ''))
        bottom += rows[:, j]
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels(keys, rotation=30, ha='right', fontsize=7)
    ax.set_ylabel('val loss (impilata)')
    ax.set_title('F4 — Composizione PINN (5 comp.) del best per famiglia')
    ax.legend(ncol=5, fontsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, 'combined_F4_pinn_composition.png'), dpi=120)
    plt.close()
    return 'F4_pinn_composition'


@_safe
def fig_progress(arms):
    import matplotlib.pyplot as plt
    # best EventProp (min val_data) per sweep: ESCLUDE BPTT_champion (e' la linea di riferimento,
    # non un risultato EventProp) -> altrimenti BS2/BS3 mostrerebbero 0.193 del champion, non l'EventProp.
    best_vd, best_nr = [], []
    for s in SWEEP_ORDER:
        sub = [a for a in arms if a['sweep'] == s and a['common_val'] and not a['aborted']
               and a['family'] != 'BPTT_champion' and a['val_data_min'] is not None]
        if not sub:
            sub = [a for a in arms if a['sweep'] == s and a['common_val']
                   and a['family'] != 'BPTT_champion' and a['val_data_min'] is not None]
        bv = min(sub, key=lambda x: x['val_data_min']) if sub else None
        nn = [a for a in sub if a['nrmse_mean'] is not None]
        bn = min(nn, key=lambda x: x['nrmse_mean']) if nn else None
        best_vd.append(bv['val_data_min'] if bv else None)
        best_nr.append(bn['nrmse_mean'] if bn else None)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    x = range(len(SWEEP_ORDER))
    ax.plot(x, best_vd, 'o-', color='#1f77b4', label='best val_data (fisica)')
    ax.axhline(CHAMP_VAL, color='red', ls='--', lw=1, label='champion 0.1926')
    ax.set_ylabel('best val_data', color='#1f77b4')
    ax.set_xticks(list(x))
    ax.set_xticklabels(SWEEP_ORDER)
    for xi, v in zip(x, best_vd):
        if v is not None:
            ax.annotate('%.3f' % v, (xi, v), textcoords='offset points', xytext=(0, 7), fontsize=7)
    ax2 = ax.twinx()
    ax2.plot(x, best_nr, 's--', color='#2ca02c', label='best NRMSE')
    ax2.set_ylabel('best NRMSE', color='#2ca02c')
    ax.set_title('F5/F6 — Evoluzione del best per campagna (fisica + NRMSE)')
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=7, loc='upper right')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTDIR, 'combined_F5_progress.png'), dpi=120)
    plt.close()
    return 'F5_progress'


FOLDER_OF = {label: folder for folder, label in SWEEPS}


def _epoch_df(epoch_rows):
    import pandas as pd
    df = pd.DataFrame(epoch_rows)
    num = [c for c in df.columns if c not in ('key', 'sweep', 'arm', 'family')]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


def _best_per_family(arms, exclude_champion=False):
    best = {}
    for a in arms:
        if not a['common_val'] or a['val_data_min'] is None:
            continue
        if exclude_champion and a['family'] == 'BPTT_champion':
            continue
        f = a['family']
        if f not in best or a['val_data_min'] < best[f]['val_data_min']:
            best[f] = a
    return best


def _batch_df(label, tag):
    import pandas as pd
    p = os.path.join(RESULTS, FOLDER_OF[label], tag, 'training_batch_log.csv')
    if not os.path.isfile(p):
        return None
    df = pd.read_csv(p)
    return df


# ---------------- TEMA 3: dinamica & velocita' ----------------
@_safe
def fig_dynamics(arms, epoch_rows):
    import matplotlib.pyplot as plt
    df = _epoch_df(epoch_rows)
    best = _best_per_family(arms)
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    for f, a in best.items():
        d = df[df.key == a['key']].sort_values('epoch')
        ax[0].plot(d['epoch'], d['val_data'], color=FAM_COLORS.get(f, '#333'), label=f, lw=1.6)
        ax[1].plot(d['epoch'], d['val_data'] - d['train_data'], color=FAM_COLORS.get(f, '#333'), lw=1.4)
    ax[0].axhline(CHAMP_VAL, color='red', ls='--', lw=1)
    ax[0].set_xlabel('epoca'); ax[0].set_ylabel('val_data'); ax[0].set_title('F7 — Convergenza val_data (best/famiglia)')
    ax[0].legend(fontsize=7); ax[0].grid(alpha=0.3)
    ax[1].axhline(0, color='k', lw=0.6)
    ax[1].set_xlabel('epoca'); ax[1].set_ylabel('val_data - train_data')
    ax[1].set_title('F8 — Gap generalizzazione (>0 = val peggio di train)'); ax[1].grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F7_dynamics.png'), dpi=120); plt.close()
    return 'F7/F8_dynamics'


@_safe
def fig_speed(arms, epoch_rows):
    import numpy as np, matplotlib.pyplot as plt
    df = _epoch_df(epoch_rows)
    # F9 epoche-a-90% del miglioramento + F10 velocita'
    rows = []
    for a in arms:
        if not a['common_val']:
            continue
        d = df[df.key == a['key']].sort_values('epoch')
        vd = d['val_data'].dropna().values
        if len(vd) < 3:
            continue
        start, final = vd[0], vd.min()
        thr = start - 0.9 * (start - final)
        hit = next((i + 1 for i, v in enumerate(vd) if v <= thr), len(vd))
        tmean = d['time_s'].dropna().mean()
        rows.append({'key': a['key'], 'family': a['family'], 'ep90': hit,
                     'time_ep': tmean, 'time_tot': a['time_total_s'], 'rank': a['rank']})
    import pandas as pd
    R = pd.DataFrame(rows)
    fams = [f for f in FAM_COLORS if (R.family == f).any()]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    e90 = [R[R.family == f]['ep90'].mean() for f in fams]
    ax[0].bar(fams, e90, color=[FAM_COLORS[f] for f in fams])
    ax[0].set_ylabel('epoche a -90% del gap'); ax[0].set_title('F9 — Velocita di convergenza (media/famiglia)')
    ax[0].tick_params(axis='x', rotation=35, labelsize=7)
    tt = [R[R.family == f]['time_ep'].mean() for f in fams]
    ax[1].bar(fams, tt, color=[FAM_COLORS[f] for f in fams])
    ax[1].set_ylabel('sec / epoca (media)'); ax[1].set_title('F10 — Velocita di training (sec/epoca)')
    ax[1].tick_params(axis='x', rotation=35, labelsize=7)
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F9_speed.png'), dpi=120); plt.close()
    return 'F9/F10_speed'


# ---------------- TEMA 4: stabilita' (core) ----------------
@_safe
def fig_gradnorm(arms, epoch_rows):
    import matplotlib.pyplot as plt
    df = _epoch_df(epoch_rows)
    best = _best_per_family(arms, exclude_champion=True)  # il champion lo aggiungo a parte (no duplicato in legenda)
    champ = next((a for a in arms if a['family'] == 'BPTT_champion' and a['sweep'] == 'BigSweep3'), None)
    fig, ax = plt.subplots(figsize=(9, 5))
    for f, a in best.items():
        d = df[df.key == a['key']].sort_values('epoch')
        ax.plot(d['epoch'], d['grad_norm'].abs(), color=FAM_COLORS.get(f, '#333'), label=f, lw=1.5)
    if champ:
        d = df[df.key == champ['key']].sort_values('epoch')
        ax.plot(d['epoch'], d['grad_norm'].abs(), color='red', lw=2, ls='--', label='BPTT champion')
    ax.set_yscale('log')
    ax.set_xlabel('epoca'); ax.set_ylabel('grad_norm (log)')
    ax.set_title('F11 — Norma del gradiente vs epoca (EventProp ~O(1) vs champion)')
    ax.legend(fontsize=7); ax.grid(alpha=0.3, which='both')
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F11_gradnorm.png'), dpi=120); plt.close()
    return 'F11_gradnorm'


@_safe
def fig_spectral(arms, epoch_rows):
    import matplotlib.pyplot as plt
    df = _epoch_df(epoch_rows)
    # solo has_diag (loggano rec_spectral_radius). Mostra: vincolati (~target) vs no-constraint che esplode.
    show = []
    best = _best_per_family(arms, exclude_champion=True)
    for f, a in best.items():
        if a['has_diag']:
            show.append((a, FAM_COLORS.get(f, '#333'), f))
    noc = next((a for a in arms if 'noconstraint' in a['arm'].lower()), None)
    if noc:
        show.append((noc, 'black', 'no-constraint (SPEC_REF)'))
    champ = next((a for a in arms if a['family'] == 'BPTT_champion' and a['has_diag']), None)
    if champ:
        show.append((champ, 'red', 'BPTT champion'))
    fig, ax = plt.subplots(figsize=(9, 5))
    for a, col, lab in show:
        d = df[df.key == a['key']].sort_values('epoch')
        ax.plot(d['epoch'], d['rec_spectral_radius'], color=col, lw=1.6, label=lab,
                ls='--' if lab.startswith(('no-constraint', 'BPTT')) else '-')
    ax.axhline(1.0, color='gray', ls=':', lw=1, label='|spectral|=1 (soglia stabilita)')
    ax.set_xlabel('epoca'); ax.set_ylabel('raggio spettrale ricorrenza')
    ax.set_title('F12 — Raggio spettrale vs epoca (C11 lo vincola; senza vincolo esplode)')
    ax.legend(fontsize=7); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F12_spectral.png'), dpi=120); plt.close()
    return 'F12_spectral'


@_safe
def fig_aborted_map(arms):
    import matplotlib.pyplot as plt
    # EventProp con spectral_target definito: target vs lr, colore = frazione completata (ran/budget)
    sub = [a for a in arms if a['family'] != 'BPTT_champion' and a['spectral_target'] == a['spectral_target']
           and a['lr'] == a['lr'] and a['spectral_target'] > 0]
    if not sub:
        return 'F13_skip'
    fig, ax = plt.subplots(figsize=(8, 5.5))
    fr = [min(1.0, a['ran_ep'] / max(a['budget_ep'], 1)) for a in sub]
    sc = ax.scatter([a['spectral_target'] for a in sub], [a['lr'] for a in sub], c=fr, cmap='RdYlGn',
                    vmin=0, vmax=1, s=80, edgecolors='k', linewidths=0.4)
    for a in sub:
        if a['aborted']:
            ax.scatter([a['spectral_target']], [a['lr']], marker='x', c='black', s=40)
    ax.set_yscale('log')
    ax.set_xlabel('spectral_target (vincolo C11)'); ax.set_ylabel('lr (log)')
    ax.set_title('F13 — Mappa stabilita: target x lr, colore=frazione epoche completate (x=aborted)')
    plt.colorbar(sc, ax=ax, label='ran_ep / budget')
    ax.grid(alpha=0.3, which='both')
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F13_aborted_map.png'), dpi=120); plt.close()
    return 'F13_aborted_map'


@_safe
def fig_batch_stability(arms):
    import matplotlib.pyplot as plt
    stable = ('BigSweep3', 'A_lr7e3_t05_r16')
    champ = ('BigSweep3', 'BPTT_REF')
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, (label, tag), ttl in [(axes[0], stable, 'STABILE: %s' % stable[1]),
                                  (axes[1], champ, 'CHAMPION: %s' % champ[1])]:
        d = _batch_df(label, tag)
        if d is None:
            ax.set_title(ttl + ' (batch-log assente)'); continue
        step = range(len(d))
        ax.plot(step, d['gn_total_preclip'], color='orange', lw=0.7, label='grad pre-clip')
        if 'gn_total_postclip' in d:
            ax.plot(step, d['gn_total_postclip'], color='steelblue', lw=0.7, label='grad post-clip')
        ax.set_yscale('log'); ax.set_xlabel('batch step'); ax.set_ylabel('grad norm (log)')
        # eventi instabilita'
        for flag, col in [('is_inf_grad', 'red'), ('is_nan_loss', 'purple')]:
            if flag in d:
                ev = d.index[d[flag] == 1].tolist()
                for e in ev[:200]:
                    ax.axvline(e, color=col, alpha=0.25, lw=0.5)
        ax.set_title(ttl); ax.legend(fontsize=7); ax.grid(alpha=0.3, which='both')
    plt.suptitle('F14 — Gradiente per-batch pre/post-clip (linee rosse=is_inf_grad, viola=is_nan_loss)')
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F14_batch_stability.png'), dpi=120); plt.close()
    return 'F14_batch_stability'


@_safe
def fig_grad_modules(arms):
    import matplotlib.pyplot as plt
    label, tag = 'BigSweep3', 'A_lr7e3_t05_r16'
    d = _batch_df(label, tag)
    if d is None:
        return 'F15_skip'
    mods = [('gn_hidden_recU', 'rec_U'), ('gn_hidden_recV', 'rec_V'), ('gn_hidden_fc', 'hidden_fc'),
            ('gn_out_fc', 'out_fc'), ('gn_hidden_thresh_jump', 'thresh_jump')]
    fig, ax = plt.subplots(figsize=(9, 5))
    for col, lab in mods:
        if col in d:
            ax.plot(range(len(d)), d[col], lw=0.7, label=lab)
    ax.set_yscale('log'); ax.set_xlabel('batch step'); ax.set_ylabel('grad norm per-modulo (log)')
    ax.set_title('F15 — Flusso del gradiente per-modulo (%s)' % tag)
    ax.legend(fontsize=8); ax.grid(alpha=0.3, which='both')
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F15_grad_modules.png'), dpi=120); plt.close()
    return 'F15_grad_modules'


# ---------------- TEMA 5: meccanismo / correlazioni ----------------
@_safe
def fig_target_stability(arms):
    import matplotlib.pyplot as plt
    sub = [a for a in arms if a['family'] != 'BPTT_champion' and a['spectral_target'] == a['spectral_target']
           and a['spectral_target'] > 0 and a['val_data_min'] is not None and a['common_val']]
    fig, ax = plt.subplots(figsize=(8, 5))
    sr = [a['final_spectral_radius'] if a['final_spectral_radius'] is not None else float('nan') for a in sub]
    sc = ax.scatter([a['spectral_target'] for a in sub], [a['val_data_min'] for a in sub],
                    c=sr, cmap='plasma', s=70, edgecolors='k', linewidths=0.4)
    ax.set_xlabel('spectral_target (vincolo C11)'); ax.set_ylabel('val_data_min (fisica)')
    ax.set_title('F16 — target spettrale vs fisica (colore = raggio spettrale finale)')
    plt.colorbar(sc, ax=ax, label='raggio spettrale finale'); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F16_target_stability.png'), dpi=120); plt.close()
    return 'F16_target_stability'


@_safe
def fig_lr_target_heat(arms):
    import numpy as np, matplotlib.pyplot as plt
    sub = [a for a in arms if a['family'].startswith('AdamW_decodeON') and a['lr'] == a['lr']
           and a['spectral_target'] == a['spectral_target'] and a['val_data_min'] is not None]
    lrs = sorted(set(round(a['lr'], 5) for a in sub))
    tgs = sorted(set(round(a['spectral_target'], 3) for a in sub))
    M = np.full((len(lrs), len(tgs)), np.nan)
    for a in sub:
        i = lrs.index(round(a['lr'], 5)); j = tgs.index(round(a['spectral_target'], 3))
        if np.isnan(M[i, j]) or a['val_data_min'] < M[i, j]:
            M[i, j] = a['val_data_min']
    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(M, aspect='auto', cmap='viridis_r')
    ax.set_xticks(range(len(tgs))); ax.set_xticklabels(tgs); ax.set_xlabel('spectral_target')
    ax.set_yticks(range(len(lrs))); ax.set_yticklabels(['%g' % x for x in lrs]); ax.set_ylabel('lr')
    for i in range(len(lrs)):
        for j in range(len(tgs)):
            if not np.isnan(M[i, j]):
                ax.text(j, i, '%.3f' % M[i, j], ha='center', va='center', fontsize=8)
    ax.set_title('F17 — Operating point: lr x target -> val_data (AdamW decode-ON)')
    plt.colorbar(im, ax=ax, label='val_data')
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F17_lr_target_heat.png'), dpi=120); plt.close()
    return 'F17_lr_target_heat'


@_safe
def fig_efficiency(arms, epoch_rows):
    import matplotlib.pyplot as plt
    df = _epoch_df(epoch_rows)
    sub = [a for a in arms if a['common_val'] and a['val_data_min'] is not None]
    gmean = {}
    for a in sub:
        g = df[df.key == a['key']]['grad_norm'].abs()
        gmean[a['key']] = g.mean()
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    for fam in FAM_COLORS:
        fs = [a for a in sub if a['family'] == fam]
        if not fs:
            continue
        ax[0].scatter([a['lr'] for a in fs], [a['val_data_min'] for a in fs],
                      c=FAM_COLORS[fam], s=40, label=fam, alpha=0.8, edgecolors='k', linewidths=0.3)
        ax[1].scatter([gmean[a['key']] for a in fs], [a['val_data_min'] for a in fs],
                      c=FAM_COLORS[fam], s=40, alpha=0.8, edgecolors='k', linewidths=0.3)
    ax[0].set_xscale('log'); ax[0].set_xlabel('lr (log)'); ax[0].set_ylabel('val_data_min')
    ax[0].set_title('F18a — val_data vs lr'); ax[0].legend(fontsize=6); ax[0].grid(alpha=0.3)
    ax[1].set_xscale('log'); ax[1].set_xlabel('grad_norm medio (log)'); ax[1].set_ylabel('val_data_min')
    ax[1].set_title('F18b — val_data vs gradiente medio (stabilita-accuratezza)'); ax[1].grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F18_efficiency.png'), dpi=120); plt.close()
    return 'F18_efficiency'


@_safe
def fig_sparsity(arms):
    import matplotlib.pyplot as plt
    sub = [a for a in arms if a['common_val'] and a['val_data_min'] is not None
           and a['final_spike_rate'] is not None]
    fig, ax = plt.subplots(figsize=(8, 5))
    for fam in FAM_COLORS:
        fs = [a for a in sub if a['family'] == fam]
        if fs:
            ax.scatter([a['final_spike_rate'] for a in fs], [a['val_data_min'] for a in fs],
                       c=FAM_COLORS[fam], s=45, label=fam, alpha=0.8, edgecolors='k', linewidths=0.3)
    ax.set_xlabel('spike_rate finale'); ax.set_ylabel('val_data_min')
    ax.set_title('F19 — Sparsita (spike_rate) vs fisica'); ax.legend(fontsize=7); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F19_sparsity.png'), dpi=120); plt.close()
    return 'F19_sparsity'


@_safe
def fig_prodigy_d(arms, epoch_rows):
    import matplotlib.pyplot as plt
    df = _epoch_df(epoch_rows)
    pe = [a for a in arms if a['family'] in ('ProdigyEvent', 'BPTT_champion') and not a['aborted']]
    fig, ax = plt.subplots(figsize=(9, 5))
    plotted = 0
    for a in pe:
        d = df[df.key == a['key']].sort_values('epoch')
        if d['prodigy_d'].notna().any():
            ax.plot(d['epoch'], d['prodigy_d'], lw=1.2,
                    color='red' if a['family'] == 'BPTT_champion' else '#2ca02c', alpha=0.7)
            plotted += 1
    ax.set_yscale('log'); ax.set_xlabel('epoca'); ax.set_ylabel('prodigy_d (log)')
    ax.set_title('F20 — Traiettoria prodigy_d (verde=ProdigyEvent, rosso=champion BPTT)')
    ax.grid(alpha=0.3, which='both')
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F20_prodigy_d.png'), dpi=120); plt.close()
    return 'F20_prodigy_d (%d arm)' % plotted


@_safe
def fig_lambda_effect(arms):
    import numpy as np, matplotlib.pyplot as plt
    sub = [a for a in arms if a['family'] == 'Spectral_sweep' and a['spectral_lambda'] > 0
           and a['spectral_target'] == a['spectral_target']]
    lams = sorted(set(a['spectral_lambda'] for a in sub))
    tgs = sorted(set(round(a['spectral_target'], 2) for a in sub))
    M = np.full((len(lams), len(tgs)), np.nan)
    for a in sub:
        i = lams.index(a['spectral_lambda']); j = tgs.index(round(a['spectral_target'], 2))
        v = a['val_data_min'] if a['val_data_min'] is not None else np.nan
        M[i, j] = v
    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(M, aspect='auto', cmap='viridis_r')
    ax.set_xticks(range(len(tgs))); ax.set_xticklabels(tgs); ax.set_xlabel('spectral_target')
    ax.set_yticks(range(len(lams))); ax.set_yticklabels(['%g' % x for x in lams]); ax.set_ylabel('spectral_lambda')
    for i in range(len(lams)):
        for j in range(len(tgs)):
            if not np.isnan(M[i, j]):
                ax.text(j, i, '%.2f' % M[i, j], ha='center', va='center', fontsize=7)
    ax.set_title('F21 — Spectral sweep: lambda x target -> val_data (NaN = aborted)')
    plt.colorbar(im, ax=ax, label='val_data')
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F21_lambda_effect.png'), dpi=120); plt.close()
    return 'F21_lambda_effect'


# ---------------- TEMA 6: diagnostica loggata ----------------
@_safe
def fig_diagnostics(arms):
    import matplotlib.pyplot as plt
    sub = [a for a in arms if a['has_diag'] and a['final_spectral_radius'] is not None and a['common_val']]
    sub = sorted(sub, key=lambda x: x['val_data_min'] if x['val_data_min'] is not None else 9)
    fig, ax = plt.subplots(2, 1, figsize=(max(8, 0.18 * len(sub)), 7))
    keys = [a['key'] for a in sub]
    cols = [FAM_COLORS.get(a['family'], '#333') for a in sub]
    ax[0].bar(range(len(sub)), [a['final_spectral_radius'] for a in sub], color=cols)
    ax[0].axhline(1.0, color='red', ls='--', lw=1)
    ax[0].set_ylabel('raggio spettrale finale'); ax[0].set_title('F22 — Diagnostica per-arm (ordinati per val_data)')
    ax[0].set_xticks([])
    ax[1].bar(range(len(sub)), [a['final_spike_rate'] for a in sub], color=cols)
    ax[1].set_ylabel('spike_rate finale')
    ax[1].set_xticks(range(len(sub))); ax[1].set_xticklabels(keys, rotation=90, fontsize=4)
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F22_diagnostics.png'), dpi=120); plt.close()
    return 'F22_diagnostics'


# ---------------- EXTRA csv-derivati ----------------
@_safe
def fig_intra_std(arms, epoch_rows):
    import numpy as np, matplotlib.pyplot as plt
    df = _epoch_df(epoch_rows)
    fams = [f for f in FAM_COLORS if any(a['family'] == f and a['common_val'] for a in arms)]
    M = np.full((len(fams), len(PN)), np.nan)
    for i, f in enumerate(fams):
        keys = [a['key'] for a in arms if a['family'] == f and a['common_val']]
        for j, c in enumerate(PN):
            vals = []
            for k in keys:
                d = df[df.key == k]
                col = 'val_%s_intra_std' % c
                if col in d and d[col].notna().any():
                    vals.append(d[col].dropna().iloc[-1])
            if vals:
                M[i, j] = float(np.mean(vals))
    fig, ax = plt.subplots(figsize=(6, 4.2))
    im = ax.imshow(M, aspect='auto', cmap='cividis')
    ax.set_xticks(range(len(PN))); ax.set_xticklabels(PN)
    ax.set_yticks(range(len(fams))); ax.set_yticklabels(fams, fontsize=8)
    for i in range(len(fams)):
        for j in range(len(PN)):
            if M[i, j] == M[i, j]:
                ax.text(j, i, '%.3f' % M[i, j], ha='center', va='center', fontsize=7,
                        color='white' if M[i, j] > np.nanmean(M) else 'black')
    ax.set_title('F28 — intra_std per-canale (confidenza identificazione; basso=deciso)')
    plt.colorbar(im, ax=ax, label='intra_std')
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F28_intra_std.png'), dpi=120); plt.close()
    return 'F28_intra_std'


@_safe
def fig_hyperparam_importance(arms):
    import numpy as np, matplotlib.pyplot as plt
    # SOLO arm completi: un aborted ha val_data alto per l'abort, non per l'iperparam -> gonfia le corr.
    sub = [a for a in arms if a['common_val'] and not a['aborted'] and a['val_data_min'] is not None]
    feats = {'lr': [], 'spectral_target': [], 'rank': [], 'decode_on': [], 'spectral_lambda': []}
    y = []
    for a in sub:
        ok = all((a.get(f) is not None and a.get(f) == a.get(f)) for f in ['lr'])
        feats['lr'].append(a['lr']); feats['spectral_target'].append(a['spectral_target'])
        feats['rank'].append(a['rank'] if a['rank'] else np.nan)
        feats['decode_on'].append(1.0 if a['decode_on'] else 0.0)
        feats['spectral_lambda'].append(a['spectral_lambda'])
        y.append(a['val_data_min'])
    y = np.array(y)
    corrs = {}
    for f, v in feats.items():
        v = np.array(v, dtype=float)
        m = ~np.isnan(v) & ~np.isnan(y)
        if m.sum() > 5 and np.std(v[m]) > 0:
            corrs[f] = abs(np.corrcoef(v[m], y[m])[0, 1])
    fig, ax = plt.subplots(figsize=(7, 4.2))
    items = sorted(corrs.items(), key=lambda x: -x[1])
    ax.bar([k for k, _ in items], [v for _, v in items], color='slateblue')
    ax.set_ylabel('|corr| con val_data')
    ax.set_title('F32 — Importanza iperparametri (|corr| globale, solo arm completi)')
    ax.text(0.98, 0.95, 'caveat: corr globale confonde le famiglie;\nlambda/rank variano poco globalmente',
            transform=ax.transAxes, ha='right', va='top', fontsize=6, color='gray')
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F32_hyperparam.png'), dpi=120); plt.close()
    return 'F32_hyperparam'


@_safe
def fig_compute_pareto(arms):
    import matplotlib.pyplot as plt
    sub = [a for a in arms if a['common_val'] and a['val_data_min'] is not None and a['time_total_s'] > 0]
    fig, ax = plt.subplots(figsize=(8, 5))
    for fam in FAM_COLORS:
        fs = [a for a in sub if a['family'] == fam]
        if fs:
            ax.scatter([a['time_total_s'] / 60 for a in fs], [a['val_data_min'] for a in fs],
                       c=FAM_COLORS[fam], s=45, label=fam, alpha=0.8, edgecolors='k', linewidths=0.3)
    ax.set_xlabel('wall-clock totale [min]'); ax.set_ylabel('val_data_min')
    ax.set_title('F33 — Pareto compute-efficiency (accuratezza per minuto)')
    ax.legend(fontsize=7); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F33_compute_pareto.png'), dpi=120); plt.close()
    return 'F33_compute_pareto'


@_safe
def fig_decode_delta(arms):
    import numpy as np, matplotlib.pyplot as plt
    on = [a for a in arms if a['family'] == 'AdamW_decodeON' and a['common_val']]
    off = [a for a in arms if a['family'] == 'AdamW_decodeOFF' and a['common_val']]

    def mean_ch(group):
        return [np.nanmean([a['nrmse_' + c] for a in group if a['nrmse_' + c] is not None]) for c in PN]
    m_on, m_off = mean_ch(on), mean_ch(off)
    x = np.arange(len(PN)); w = 0.38
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.bar(x - w / 2, m_off, w, label='decode OFF', color='#7f7f7f')
    ax.bar(x + w / 2, m_on, w, label='decode ON', color='#1f77b4')
    ax.set_xticks(x); ax.set_xticklabels(PN); ax.set_ylabel('NRMSE medio')
    ax.set_title('F34 — Effetto del decode per-canale (ON de-satura T/s0)'); ax.legend()
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F34_decode_delta.png'), dpi=120); plt.close()
    return 'F34_decode_delta'


@_safe
def fig_pe_dissection(arms):
    import numpy as np, matplotlib.pyplot as plt
    pe = [a for a in arms if a['family'] == 'ProdigyEvent' and not a['aborted'] and a['nrmse_mean'] is not None]
    adam = [a for a in arms if a['family'] == 'AdamW_decodeON' and a['val_data_min'] is not None]
    champ = next((a for a in arms if a['arm'] == 'BPTT_REF' and a['sweep'] == 'BigSweep3'), None)
    best_pe = min(pe, key=lambda x: x['nrmse_mean']) if pe else None
    best_adam = min(adam, key=lambda x: x['val_data_min']) if adam else None
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    # sx: PE su piano NRMSE-val_data con etichette
    for a in pe:
        ax[0].scatter(a['val_data_min'], a['nrmse_mean'], c='#2ca02c', s=50, edgecolors='k', linewidths=0.3)
        ax[0].annotate(a['arm'].replace('PE_', ''), (a['val_data_min'], a['nrmse_mean']), fontsize=6)
    if best_adam:
        ax[0].scatter(best_adam['val_data_min'], best_adam['nrmse_mean'], c='#1f77b4', s=90, marker='D', label='best AdamW')
    ax[0].scatter(CHAMP_VAL, CHAMP_NRMSE, c='red', marker='*', s=200, label='champion')
    ax[0].set_xlabel('val_data (fisica)'); ax[0].set_ylabel('NRMSE'); ax[0].legend(fontsize=7)
    ax[0].set_title('F37a — ProdigyEvent: NRMSE bassa MA fisica peggiore'); ax[0].grid(alpha=0.3)
    # dx: NRMSE per-canale best-PE vs best-AdamW vs champion
    x = np.arange(len(PN)); w = 0.27
    groups = [(best_pe, 'best PE', '#2ca02c'), (best_adam, 'best AdamW', '#1f77b4')]
    for k, (g, lab, col) in enumerate(groups):
        if g:
            ax[1].bar(x + (k - 0.5) * w, [g['nrmse_' + c] for c in PN], w, label='%s' % lab, color=col)
    ax[1].set_xticks(x); ax[1].set_xticklabels(PN); ax[1].set_ylabel('NRMSE per-canale')
    ax[1].set_title('F37b — Da dove viene la NRMSE bassa PE'); ax[1].legend(fontsize=7)
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F37_pe_dissection.png'), dpi=120); plt.close()
    return 'F37_pe_dissection'


# ---------------- EXTRA addizionali ----------------
@_safe
def fig_t_tracking(arms, epoch_rows):
    import numpy as np, matplotlib.pyplot as plt
    df = _epoch_df(epoch_rows)
    fams = [f for f in FAM_COLORS if any(a['family'] == f and a['common_val'] for a in arms)]
    vals = []
    for f in fams:
        keys = [a['key'] for a in arms if a['family'] == f and a['common_val']]
        v = []
        for k in keys:
            d = df[df.key == k]
            if 'val_T_tracking_corr' in d and d['val_T_tracking_corr'].notna().any():
                v.append(d['val_T_tracking_corr'].dropna().iloc[-1])
        vals.append(np.mean(v) if v else np.nan)
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.bar(fams, vals, color=[FAM_COLORS[f] for f in fams])
    ax.set_ylabel('val_T_tracking_corr (finale, media)')
    ax.set_title('F29 — Tracking del parametro dinamico T (corr; alto=meglio)')
    ax.tick_params(axis='x', rotation=35, labelsize=7); ax.grid(alpha=0.3, axis='y')
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F29_t_tracking.png'), dpi=120); plt.close()
    return 'F29_t_tracking'


@_safe
def fig_alif_threshold(arms, epoch_rows):
    import matplotlib.pyplot as plt
    df = _epoch_df(epoch_rows)
    best = _best_per_family(arms, exclude_champion=True)
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
    for f, a in best.items():
        d = df[df.key == a['key']].sort_values('epoch')
        if 'mean_vth_at_spike' in d and d['mean_vth_at_spike'].notna().any():
            ax[0].plot(d['epoch'], d['mean_vth_at_spike'], color=FAM_COLORS.get(f, '#333'), label=f, lw=1.4)
        if 'mean_spike_margin' in d and d['mean_spike_margin'].notna().any():
            ax[1].plot(d['epoch'], d['mean_spike_margin'], color=FAM_COLORS.get(f, '#333'), lw=1.4)
    ax[0].set_xlabel('epoca'); ax[0].set_ylabel('mean_vth_at_spike'); ax[0].set_title('F30a — soglia ALIF allo spike')
    ax[0].legend(fontsize=7); ax[0].grid(alpha=0.3)
    ax[1].set_xlabel('epoca'); ax[1].set_ylabel('mean_spike_margin'); ax[1].set_title('F30b — margine di spike')
    ax[1].grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F30_alif_threshold.png'), dpi=120); plt.close()
    return 'F30_alif_threshold'


@_safe
def fig_grad_equalization(arms):
    import numpy as np, matplotlib.pyplot as plt
    import pandas as pd
    pairs = [('AdamW_decodeON', 'A_lr7e3_t05_r16', 'BigSweep3', 'decode ON'),
             ('AdamW_decodeOFF', 'A_lr7e3_t05_r16_noDEC', 'BigSweep3', 'decode OFF')]
    cols = ['gn_out_fc_%s' % c for c in PN]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    x = np.arange(len(PN)); w = 0.38
    for k, (fam, tag, label, lab) in enumerate(pairs):
        d = _batch_df(label, tag)
        if d is None or not all(c in d.columns for c in cols):
            continue
        means = [d[c].abs().mean() for c in cols]
        ax.bar(x + (k - 0.5) * w, means, w, label=lab, color='#1f77b4' if k == 0 else '#7f7f7f')
    ax.set_xticks(x); ax.set_xticklabels(PN); ax.set_ylabel('grad per-canale medio (out_fc)')
    ax.set_yscale('log')
    ax.set_title('F31 — Equalizzazione gradiente per-canale: decode ON vs OFF')
    ax.legend()
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F31_grad_equalization.png'), dpi=120); plt.close()
    return 'F31_grad_equalization'


@_safe
def fig_instability_timeline(arms):
    import pandas as pd, matplotlib.pyplot as plt
    rows = []
    for a in arms:
        p = os.path.join(RESULTS, FOLDER_OF[a['sweep']], a['arm'], 'training_batch_log.csv')
        if not os.path.isfile(p):
            continue
        try:
            d = pd.read_csv(p, usecols=lambda c: c in ('is_nan_loss', 'is_inf_grad'))
        except Exception:
            continue
        n_inf = int(d['is_inf_grad'].sum()) if 'is_inf_grad' in d else 0
        n_nan = int(d['is_nan_loss'].sum()) if 'is_nan_loss' in d else 0
        if n_inf + n_nan > 0:
            rows.append({'key': a['key'], 'inf': n_inf, 'nan': n_nan, 'aborted': a['aborted']})
    if not rows:
        # nessun evento: figura informativa "zero instabilita' numerica"
        fig, ax = plt.subplots(figsize=(7, 2.2))
        ax.text(0.5, 0.5, 'Nessun arm con eventi is_nan_loss / is_inf_grad\n(stabilita numerica su tutte le campagne)',
                ha='center', va='center', fontsize=11)
        ax.axis('off')
        plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F35_instability.png'), dpi=120); plt.close()
        return 'F35_instability (0 eventi)'
    rows = sorted(rows, key=lambda r: -(r['inf'] + r['nan']))
    import numpy as np
    fig, ax = plt.subplots(figsize=(max(7, 0.3 * len(rows)), 4.6))
    x = np.arange(len(rows))
    ax.bar(x, [r['inf'] for r in rows], label='is_inf_grad', color='crimson')
    ax.bar(x, [r['nan'] for r in rows], bottom=[r['inf'] for r in rows], label='is_nan_loss', color='purple')
    ax.set_xticks(x); ax.set_xticklabels([r['key'] for r in rows], rotation=90, fontsize=5)
    ax.set_ylabel('# eventi (su tutto il training)')
    ax.set_title('F35 — Eventi di instabilita numerica per-arm')
    ax.legend()
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F35_instability.png'), dpi=120); plt.close()
    return 'F35_instability (%d arm)' % len(rows)


@_safe
def fig_settling(arms, epoch_rows):
    import numpy as np, matplotlib.pyplot as plt
    df = _epoch_df(epoch_rows)
    sub = [a for a in arms if a['common_val'] and not a['aborted'] and a['val_data_min'] is not None]
    fig, ax = plt.subplots(figsize=(8, 5))
    for fam in FAM_COLORS:
        fs = [a for a in sub if a['family'] == fam]
        xs, ys = [], []
        for a in fs:
            d = df[df.key == a['key']].sort_values('epoch')['val_data'].dropna().values
            if len(d) >= 5:
                xs.append(a['val_data_min']); ys.append(float(np.std(d[-5:])))
        if xs:
            ax.scatter(xs, ys, c=FAM_COLORS[fam], s=45, label=fam, alpha=0.8, edgecolors='k', linewidths=0.3)
    ax.set_xlabel('val_data_min'); ax.set_ylabel('std val_data (ultime 5 epoche)')
    ax.set_title('F36 — Settling di convergenza (basso = stabile a fine training)')
    ax.legend(fontsize=7); ax.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(OUTDIR, 'combined_F36_settling.png'), dpi=120); plt.close()
    return 'F36_settling'


if __name__ == '__main__':
    arms, epoch_rows = ingest()
    p1, p2 = write_backbone(arms, epoch_rows)
    print('Wrote', p1)
    print('Wrote', p2, '(%d righe epoca)' % len(epoch_rows))
    print()
    print_manifest(arms)
    print('\n=== FIGURE ===')
    jobs = [
        (fig_ranking, (arms,)), (fig_pareto, (arms,)), (fig_nrmse_heat, (arms,)),
        (fig_pinn_composition, (arms, epoch_rows)), (fig_progress, (arms,)),
        (fig_dynamics, (arms, epoch_rows)), (fig_speed, (arms, epoch_rows)),
        (fig_gradnorm, (arms, epoch_rows)), (fig_spectral, (arms, epoch_rows)),
        (fig_aborted_map, (arms,)), (fig_batch_stability, (arms,)), (fig_grad_modules, (arms,)),
        (fig_target_stability, (arms,)), (fig_lr_target_heat, (arms,)), (fig_efficiency, (arms, epoch_rows)),
        (fig_sparsity, (arms,)), (fig_prodigy_d, (arms, epoch_rows)), (fig_lambda_effect, (arms,)),
        (fig_diagnostics, (arms,)), (fig_intra_std, (arms, epoch_rows)),
        (fig_hyperparam_importance, (arms,)), (fig_compute_pareto, (arms,)),
        (fig_decode_delta, (arms,)), (fig_pe_dissection, (arms,)),
        (fig_t_tracking, (arms, epoch_rows)), (fig_alif_threshold, (arms, epoch_rows)),
        (fig_grad_equalization, (arms,)), (fig_instability_timeline, (arms,)),
        (fig_settling, (arms, epoch_rows)),
    ]
    ok = 0
    for fn, args in jobs:
        r = fn(*args)
        if r:
            ok += 1; print('  OK', r)
    print('\n%d/%d figure generate' % (ok, len(jobs)))
