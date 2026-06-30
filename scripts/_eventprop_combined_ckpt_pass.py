"""EventProp Study combinato — STADIO 2: passo sui CHECKPOINT (gira su AZURE, dove stanno i .pt).

Per ogni arm EventProp + BPTT_REF con checkpoint caricabile, calcola le metriche che richiedono i pesi
(non derivabili dai log) e le emette in results/EventProp_Study/combined/ come csv cross-sweep:
  - combined_ckpt_diag.csv       : eff_rank (U@V), dead_neurons
  - combined_ckpt_perregime.csv  : data/phys/NRMSE per scenario
  - combined_ckpt_closedloop.csv : sicurezza oracolo vs SNN (collisioni/min-gap/decel/jerk)
  - combined_ckpt_pathb.csv      : Path-B refit (NRMSE giu MA fisica su)
  - combined_ckpt_manifest.csv   : copertura (ckpt trovato/caricato + esito per-analisi + errore)

Robustezza (l'idle-shutdown di Azure ci ha gia' morso):
  * config-aware load: hidden/rank/max_delay/bit_shift dal config_snapshot del singolo arm (strict=False).
  * try/except per-arm E per-analisi -> un fallimento non ferma il resto; finisce nel manifest.
  * SKIP-se-fatto: ri-eseguibile, salta le coppie (arm, analisi) gia' presenti nei csv.
  * push periodico (ogni PUSH_EVERY arm) + push finale -> uno shutdown non fa perdere nulla.

Uso (su Azure, dal root del repo):  python scripts/_eventprop_combined_ckpt_pass.py
Opz.: N_DRIVERS=20 (closed-loop), PUSH_EVERY=10, ONLY=<substring> per filtrare gli arm.
"""
import os
import sys
import json
import glob
import csv
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import numpy as np
import torch

OUTDIR = os.path.join('results', 'EventProp_Study', 'combined')
CACHE = 'data/cache_1500_launch_cut0.0_ou0.0.pt'
BRANCH = 'EventProp_Study'
PN = ['v0', 'T', 's0', 'a', 'b']
LAM = (1.0, 0.1, 0.05, 1.0, 0.5)
SWEEPS = ['EventProp_Study', 'EventProp_Spectral_Sweep', 'EventProp_BigSweep',
          'EventProp_BigSweep2', 'EventProp_BigSweep3']  # ordine: l'ultimo vince sui tag duplicati
N_DRIVERS = int(os.environ.get('N_DRIVERS', '20'))
PUSH_EVERY = int(os.environ.get('PUSH_EVERY', '10'))
ONLY = os.environ.get('ONLY', '')


def ckpt_path(tag):
    return os.path.join('checkpoints', tag, 'best_model.pt')


def discover_arms():
    """{tag: (sweep, config)} per gli arm EventProp + BPTT/PEAK; l'ultima campagna vince sui tag duplicati."""
    arms = {}
    for folder in SWEEPS:
        for cfgp in sorted(glob.glob(os.path.join('results', folder, '*', 'config_snapshot.json'))):
            tag = os.path.basename(os.path.dirname(cfgp))
            try:
                cfg = json.load(open(cfgp))
            except Exception:
                cfg = {}
            arms[tag] = (folder.replace('EventProp_', ''), cfg)
    return arms


def build_and_load(tag, cfg):
    from core.network import build_model
    hidden = int(cfg.get('cf_hidden_size') or 32)
    rank = int(cfg.get('cf_rank') or 16)
    max_delay = int(cfg.get('cf_max_delay') or 6)
    bit_shift = int(cfg.get('cf_bit_shift') or 3)
    m = build_model('eventprop_alif_full', hidden_size=hidden, rank=rank,
                    max_delay=max_delay, bit_shift=bit_shift)
    ck = torch.load(ckpt_path(tag), map_location='cpu', weights_only=False)
    state = ck['model_state'] if 'model_state' in ck else ck
    m.load_state_dict(state, strict=False)
    m.eval()
    return m, rank, state


# ---------------- analisi (riusano la logica delle celle BS3) ----------------
def an_diag(tag, cfg, model, state, cache):
    out = {'arm': tag, 'eff_rank': None, 'dead_neurons': None}
    if 'layer_hidden.rec_U' in state:
        R = (state['layer_hidden.rec_U'] @ state['layer_hidden.rec_V']).cpu().numpy()
        sv = np.linalg.svd(R, compute_uv=False)
        out['eff_rank'] = round(float((sv.sum() ** 2) / (sv ** 2).sum()), 2)
    xval = torch.tensor(np.array([it['x'][:50] for it in cache['val'][:64]]), dtype=torch.float32)
    with torch.no_grad():
        sp = model.layer_hidden(xval)
    fr = sp.float().mean(dim=(0, 1))
    out['dead_neurons'] = int((fr < 0.005).sum())
    return [out]


def an_perregime(tag, cfg, model, state, cache):
    from train import CFDataset, val_epoch
    from torch.utils.data import DataLoader
    scen = sorted(set(it.get('scenario', 'NA') for it in cache['val']))
    rows = []
    for sc in scen:
        items = [it for it in cache['val'] if it.get('scenario', 'NA') == sc]
        if len(items) < 2:
            continue
        loader = DataLoader(CFDataset(items, seq_len=50, stride=50), batch_size=32)
        with torch.no_grad():
            a = val_epoch(model, loader, 'cpu', LAM)
        row = {'arm': tag, 'scenario': sc, 'n': len(items),
               'data': round(float(a['data']), 4), 'phys': round(float(a['phys']), 4)}
        for c in PN:
            row['nrmse_' + c] = round(float(a['val_%s_nrmse' % c]), 3)
        rows.append(row)
    return rows


def an_closedloop(tag, cfg, model, state, cache):
    from scripts.closed_loop_identify import eval_safety
    r = eval_safety(model, cache, n_drivers=N_DRIVERS)
    keys = ['collision_rate', 'mean_min_gap', 'mean_max_decel', 'mean_rms_jerk']
    rows = []
    for role, d in [('oracolo', r['oracle']), ('SNN', r['snn'])]:
        row = {'arm': tag, 'role': role}
        for k in keys:
            row[k] = round(float(d[k]), 3)
        rows.append(row)
    return rows


def an_pathb(tag, cfg, model, state, cache):
    from scripts.path_b_validate import validate
    rank = int(cfg.get('cf_rank') or 16)
    res = validate(os.path.join('checkpoints', tag), rank)
    g, rf = res['global'], res['refit']
    return [{'arm': tag, 'nrmse_glob': round(g['nrmse_mean'], 3), 'nrmse_refit': round(rf['nrmse_mean'], 3),
             'data_glob': round(g['comps']['data'], 4), 'data_refit': round(rf['comps']['data'], 4),
             'phys_glob': round(g['comps']['phys'], 4), 'phys_refit': round(rf['comps']['phys'], 4)}]


ANALYSES = [('diag', an_diag), ('perregime', an_perregime), ('closedloop', an_closedloop), ('pathb', an_pathb)]


def _csv_path(name):
    return os.path.join(OUTDIR, 'combined_ckpt_%s.csv' % name)


def _load_done(name):
    p = _csv_path(name)
    if not os.path.isfile(p):
        return set(), []
    with open(p, newline='') as f:
        rows = list(csv.DictReader(f))
    return set(r['arm'] for r in rows), rows


def _write_csv(name, rows):
    if not rows:
        return
    p = _csv_path(name)
    cols = list(rows[0].keys())
    # unione colonne (per-regime/closedloop hanno chiavi extra)
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(p, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _push(msg):
    try:
        subprocess.run(['git', 'add', OUTDIR], check=True, capture_output=True)
        r = subprocess.run(['git', 'commit', '-m', msg], capture_output=True, text=True)
        if r.returncode != 0 and 'nothing to commit' in (r.stdout + r.stderr):
            return
        subprocess.run(['git', 'pull', '--no-rebase', '--no-edit', 'origin', BRANCH], capture_output=True, text=True)
        for _ in range(3):
            p = subprocess.run(['git', 'push', 'origin', BRANCH], capture_output=True, text=True)
            if p.returncode == 0:
                print('   push OK'); return
        print('   push FALLITO (riprovo al prossimo giro):', p.stderr[-200:])
    except Exception as e:
        print('   push err', e)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    assert os.path.isfile(CACHE), 'manca la cache val comune: ' + CACHE
    cache = torch.load(CACHE, map_location='cpu', weights_only=False)
    arms = discover_arms()
    if ONLY:
        arms = {t: v for t, v in arms.items() if ONLY in t}
    print('[STADIO2] %d arm unici da processare (n_drivers=%d)' % (len(arms), N_DRIVERS))

    store = {name: _load_done(name) for name, _ in ANALYSES}
    manifest = []
    processed = 0
    for tag, (sweep, cfg) in sorted(arms.items()):
        # se TUTTE le analisi sono gia' fatte per questo arm -> skip
        if all(tag in store[name][0] for name, _ in ANALYSES):
            continue
        man = {'arm': tag, 'sweep': sweep, 'ckpt_found': os.path.isfile(ckpt_path(tag))}
        if not man['ckpt_found']:
            man['status'] = 'ckpt assente'
            manifest.append(man); print('[skip] %-28s ckpt assente' % tag); continue
        try:
            model, rank, state = build_and_load(tag, cfg)
            man['loaded'] = True
        except Exception as e:
            man['loaded'] = False; man['status'] = 'load FAIL: %s' % str(e)[:120]
            manifest.append(man); print('[FAIL load] %-28s %s' % (tag, str(e)[:80])); continue
        for name, fn in ANALYSES:
            done, rows = store[name]
            if tag in done:
                man[name] = 'skip'; continue
            try:
                new = fn(tag, cfg, model, state, cache)
                rows.extend(new); done.add(tag)
                _write_csv(name, rows)
                man[name] = 'ok'
            except Exception as e:
                man[name] = 'FAIL: %s' % str(e)[:80]
                print('   [%s] %s -> %s' % (name, tag, str(e)[:80]))
        man['status'] = 'ok'
        manifest.append(man)
        processed += 1
        print('[ok] %-28s rank=%s %s' % (tag, rank, {n: man.get(n) for n, _ in ANALYSES}))
        if processed % PUSH_EVERY == 0:
            _write_csv('manifest', manifest_rows(arms, manifest))
            _push('ckpt-pass: progresso (%d arm)' % processed)

    _write_csv('manifest', manifest_rows(arms, manifest))
    _push('ckpt-pass: completato')
    print('\n[STADIO2] fatto. Arm processati ora: %d' % processed)
    print('Manifest:', _csv_path('manifest'))


def manifest_rows(arms, manifest):
    # un manifest completo: tutti gli arm noti + esito (anche quelli skippati perche' gia' fatti)
    seen = {m['arm']: m for m in manifest}
    rows = []
    for tag, (sweep, cfg) in sorted(arms.items()):
        if tag in seen:
            rows.append(seen[tag])
        else:
            rows.append({'arm': tag, 'sweep': sweep, 'ckpt_found': os.path.isfile(ckpt_path(tag)),
                         'status': 'gia fatto (skip)'})
    return rows


if __name__ == '__main__':
    main()
