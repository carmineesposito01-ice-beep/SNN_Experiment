"""
scripts/preflight.py — Doppio smoke test pre-FULL (PF, regola permanente del workflow)
========================================================================================

Esegue 2 smoke consecutivi e verifica criteri pass su ENTRAMBI prima di autorizzare
un FULL training (≥3 epochs su risorse costose tipo Azure GPU).

Motivazione: un FULL training su Azure costa ~150 min. Un singolo smoke fallisce
silenziosamente per problemi costruttivi (state_dict missing, plot crash, ecc.)
solo dopo aver completato 1 epoca, sprecando ore di compute. Il doppio smoke su
~50 step costa <5 min ma intercetta tutti i problemi a basso ROI.

Uso:
    python scripts/preflight.py --base_tag <runtag>
    # Se exit code 0 → SAFE per lanciare FULL:
    python train.py --epochs 5 ... --tag <runtag>

Criteri pass (ENTRAMBI gli smoke devono soddisfarli):
  1. Exit code 0 di train.py
  2. Nessun "[EARLY-STOP]" nello stdout
  3. training_log.csv ha ≥ 1 riga
  4. training_batch_log.csv ha ≥ 10 righe
  5. ≥ 5 file PNG generati in plots/ (almeno G8-G12 — per-batch sempre disponibili)
  6. best_model.pt esiste e ricaricabile (load_state_dict con strict=False)
  7. Nessun "RuntimeError" / "Traceback" nello stdout
"""

import argparse
import os
import subprocess
import sys
import time

# Aggiungi root al path per importazioni
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)


# ───────────────────────────────────────────────────────────────
# Criteri pass
# ───────────────────────────────────────────────────────────────

def _count_csv_rows(path):
    """Conta righe escludendo header. Restituisce -1 se file inesistente."""
    if not os.path.isfile(path):
        return -1
    with open(path, 'r', encoding='utf-8') as f:
        return sum(1 for _ in f) - 1


def _count_pngs(plots_dir):
    """Conta file PNG nella directory plots/."""
    if not os.path.isdir(plots_dir):
        return 0
    return sum(1 for f in os.listdir(plots_dir) if f.endswith('.png'))


def _checkpoint_loadable(ckpt_path):
    """Verifica che il best_model.pt sia caricabile con strict=False."""
    if not os.path.isfile(ckpt_path):
        return False, 'file not found'
    try:
        import torch
        from core.network import CF_FSNN_Net
        ckpt = torch.load(ckpt_path, map_location='cpu', weights_only=False)
        m = CF_FSNN_Net()
        m.load_state_dict(ckpt['model_state'], strict=False)
        return True, 'ok'
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'


def evaluate_run(save_dir, stdout_text, exit_code):
    """Valuta i 7 criteri pass su un singolo smoke.

    Restituisce (passed_bool, results_list_of_(name, passed, detail)).
    """
    results = []

    # 1. Exit code
    ok1 = exit_code == 0
    results.append(('Exit code 0', ok1, f'exit={exit_code}'))

    # 2. No [EARLY-STOP]
    ok2 = '[EARLY-STOP]' not in stdout_text
    detail2 = 'no EARLY-STOP found' if ok2 else 'EARLY-STOP detected'
    results.append(('No [EARLY-STOP]', ok2, detail2))

    # 3. training_log.csv ha >=1 riga
    log_csv = os.path.join(save_dir, 'training_log.csv')
    n_rows  = _count_csv_rows(log_csv)
    ok3     = n_rows >= 1
    results.append(('training_log.csv >= 1 row', ok3, f'rows={n_rows}'))

    # 4. training_batch_log.csv ha >=10 righe
    blog_csv = os.path.join(save_dir, 'training_batch_log.csv')
    n_brows  = _count_csv_rows(blog_csv)
    ok4      = n_brows >= 10
    results.append(('training_batch_log.csv >= 10 rows', ok4, f'rows={n_brows}'))

    # 5. >= 5 PNG generati
    plots_dir = os.path.join(save_dir, 'plots')
    n_pngs    = _count_pngs(plots_dir)
    ok5       = n_pngs >= 5
    results.append(('>= 5 PNG plots generated', ok5, f'pngs={n_pngs}'))

    # 6. best_model.pt caricabile
    ckpt = os.path.join(save_dir, 'best_model.pt')
    ok6, detail6 = _checkpoint_loadable(ckpt)
    results.append(('best_model.pt loadable', ok6, detail6))

    # 7. No RuntimeError / Traceback
    bad_markers = ['RuntimeError', 'Traceback (most recent call last)']
    found_bad   = [m for m in bad_markers if m in stdout_text]
    ok7         = len(found_bad) == 0
    detail7     = 'no errors found' if ok7 else f'found: {found_bad}'
    results.append(('No RuntimeError/Traceback', ok7, detail7))

    passed = all(r[1] for r in results)
    return passed, results


def print_report(label, passed, results, elapsed_s):
    """Stampa report sintetico per uno smoke."""
    status = 'PASS' if passed else 'FAIL'
    print(f"\n{'='*72}")
    print(f"  {label} — {status}  ({elapsed_s:.1f}s)")
    print(f"{'='*72}")
    for name, ok, detail in results:
        mark = '[OK]' if ok else '[FAIL]'
        print(f"  {mark:6} {name:<40} {detail}")
    print()


# ───────────────────────────────────────────────────────────────
# Orchestratore
# ───────────────────────────────────────────────────────────────

def run_smoke(tag, train_py_args, root_dir):
    """Lancia un singolo smoke via subprocess. Cattura stdout completo.

    train_py_args: lista di argomenti EXTRA per train.py oltre a --smoke --tag <tag>
    """
    cmd = [sys.executable, 'train.py', '--smoke', '--tag', tag] + list(train_py_args)
    print(f"\n[preflight] Lancio: {' '.join(cmd)}")
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=root_dir, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')
    elapsed = time.time() - t0

    # Streamiamo lo stdout sul terminale per visibilità
    print(proc.stdout)
    if proc.stderr:
        print('[stderr]', proc.stderr, file=sys.stderr)

    save_dir = os.path.join(root_dir, 'checkpoints', tag)
    return proc.stdout, proc.returncode, elapsed, save_dir


def main():
    parser = argparse.ArgumentParser(
        description='Pre-flight doppio smoke obbligatorio (PF)'
    )
    parser.add_argument('--base_tag', required=True,
                        help='Tag base — i 2 smoke userranno <base_tag>_preflight_1 e _2')
    parser.add_argument('--extra', nargs=argparse.REMAINDER, default=[],
                        help='Argomenti CLI extra da passare a train.py '
                             '(es: --extra --max_lr 2e-3 --seq_len 50)')
    args = parser.parse_args()

    root_dir = _ROOT

    tag1 = f"{args.base_tag}_preflight_1"
    tag2 = f"{args.base_tag}_preflight_2"

    print(f"\n[preflight] Base tag: {args.base_tag}")
    print(f"[preflight] Smoke 1: {tag1}")
    print(f"[preflight] Smoke 2: {tag2}")
    if args.extra:
        print(f"[preflight] Extra args: {args.extra}")

    # ── Smoke 1 ───────────────────────────────────────────────
    out1, exit1, t1, dir1 = run_smoke(tag1, args.extra, root_dir)
    passed1, results1 = evaluate_run(dir1, out1, exit1)
    print_report(f'SMOKE 1 ({tag1})', passed1, results1, t1)

    # ── Smoke 2 ───────────────────────────────────────────────
    out2, exit2, t2, dir2 = run_smoke(tag2, args.extra, root_dir)
    passed2, results2 = evaluate_run(dir2, out2, exit2)
    print_report(f'SMOKE 2 ({tag2})', passed2, results2, t2)

    # ── Verdetto finale ───────────────────────────────────────
    all_pass = passed1 and passed2
    print('=' * 72)
    if all_pass:
        print('  PREFLIGHT: PASS — entrambi gli smoke sono OK.')
        print('             SAFE per lanciare FULL training.')
        print('=' * 72)
        sys.exit(0)
    else:
        print('  PREFLIGHT: FAIL — almeno uno smoke ha fallito.')
        print('             NON LANCIARE FULL training.')
        print('             Esamina i log e i grafici G8-G12 in:')
        print(f'               - {dir1}')
        print(f'               - {dir2}')
        print('             Documenta il fallimento in document/P_S.md.')
        print('=' * 72)
        sys.exit(1)


if __name__ == '__main__':
    main()
