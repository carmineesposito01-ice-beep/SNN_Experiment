"""
utils/plot_diagnostics.py — Sistema di diagnostica visiva per CF_FSNN
======================================================================
Genera i 7 grafici standard definiti in optimization_ideas.md dopo ogni run.

Uso:
    from utils.plot_diagnostics import plot_all, load_training_log
    log = load_training_log('checkpoints/my_tag/training_log.csv')
    plot_all(log, out_dir='checkpoints/my_tag/plots')

Grafici prodotti:
    G1 - Curva loss train/val totale
    G2 - Componenti loss (data, phys, ou, bc)
    G3 - Schedule LR nel tempo
    G4 - Norma gradiente per epoca
    G5 - Scatter T_pred vs T_true (sui batch di validazione salvati)
    G6 - Spike rate del layer hidden nel tempo
    G7 - Violin plot delle 5 distribuzioni di parametri predetti [v0,T,s0,a,b]
"""

import csv
import os
from pathlib import Path

import numpy as np

# matplotlib opzionale — fallback testuale se non installato
try:
    import matplotlib
    matplotlib.use('Agg')   # headless — nessun display richiesto
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    _MPL = True
except ImportError:
    _MPL = False
    print("[plot_diagnostics] WARNING: matplotlib non trovato — grafici disabilitati.")


# ===========================================================
# 1. Lettura del CSV di logging
# ===========================================================

def load_training_log(csv_path: str) -> dict:
    """
    Carica training_log.csv prodotto da train.py.

    Colonne attese:
        epoch, train_total, train_data, train_phys, train_ou, train_bc,
        val_total, val_data, val_phys, val_ou, val_bc,
        lr, grad_norm, spike_rate, time_s

    Restituisce dict con chiave = nome colonna, valore = array numpy.
    """
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"Log non trovato: {csv_path}")

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        # F3a: training abortito prima di epoch 1 → CSV ha solo l'header.
        # Restituisce None invece di ValueError; plot_all e main() lo gestiscono.
        print(f"[plot_diagnostics] Log vuoto (training abortito prima di epoch 1): {csv_path}")
        return None

    data = {k: [] for k in rows[0].keys()}
    for row in rows:
        for k, v in row.items():
            try:
                data[k].append(float(v))
            except (ValueError, TypeError):
                data[k].append(float('nan'))

    return {k: np.array(v) for k, v in data.items()}


# ===========================================================
# 2. Singoli grafici
# ===========================================================

def _save(fig, path: str):
    """Salva figura e chiude per liberare memoria."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Salvato: {path}")


def plot_g1_loss_curve(log: dict, out_path: str):
    """G1 — Curva loss totale train/val per epoca."""
    if not _MPL:
        return
    fig, ax = plt.subplots(figsize=(8, 4))
    ep = log['epoch']
    ax.plot(ep, log['train_total'], label='train', color='steelblue', linewidth=1.5)
    ax.plot(ep, log['val_total'],   label='val',   color='coral',     linewidth=1.5)
    ax.set_xlabel('Epoca')
    ax.set_ylabel('Loss totale')
    ax.set_title('G1 — Curva loss train/val')
    ax.legend()
    ax.grid(True, alpha=0.3)
    _save(fig, out_path)


def plot_g2_components(log: dict, out_path: str):
    """G2 — Componenti loss di validazione (data, phys, ou, bc)."""
    if not _MPL:
        return
    fig, ax = plt.subplots(figsize=(8, 4))
    ep = log['epoch']
    comps = {
        'L_data (Masked RMSE)':  log['val_data'],
        'L_phys (residuo ACC-IDM)': log['val_phys'],
        'L_OU (vincolo T)':  log['val_ou'],
        'L_bc (crash pen.)': log['val_bc'],
    }
    for label, vals in comps.items():
        ax.plot(ep, vals, label=label, linewidth=1.2)
    ax.set_xlabel('Epoca')
    ax.set_ylabel('Loss (non pesata)')
    ax.set_title('G2 — Componenti loss (validazione)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_yscale('log')
    _save(fig, out_path)


def plot_g3_lr_schedule(log: dict, out_path: str):
    """G3 — Learning rate per epoca (schedule)."""
    if not _MPL:
        return
    fig, ax = plt.subplots(figsize=(8, 3))
    ep = log['epoch']
    ax.plot(ep, log['lr'], color='green', linewidth=1.5)
    ax.set_xlabel('Epoca')
    ax.set_ylabel('Learning Rate')
    ax.set_title('G3 — Schedule LR')
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3)
    _save(fig, out_path)


def plot_g4_grad_norm(log: dict, out_path: str):
    """G4 — Norma gradiente per epoca (diagnosi exploding/vanishing)."""
    if not _MPL:
        return
    fig, ax = plt.subplots(figsize=(8, 3))
    ep = log['epoch']
    ax.plot(ep, log['grad_norm'], color='purple', linewidth=1.2, alpha=0.8)
    ax.axhline(1.0, color='red', linestyle='--', linewidth=0.8, label='clip max=1.0')
    ax.set_xlabel('Epoca')
    ax.set_ylabel('Grad norm (pre-clip)')
    ax.set_title('G4 — Norma gradiente')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    _save(fig, out_path)


def plot_g5_T_scatter(T_pred: np.ndarray, T_true: np.ndarray, out_path: str):
    """
    G5 — Scatter T predetto vs T vero.
    T_pred, T_true: array 1D di valori [s].
    """
    if not _MPL:
        return
    fig, ax = plt.subplots(figsize=(5, 5))
    # Campiona max 5000 punti per leggibilità
    n = min(len(T_pred), 5000)
    idx = np.random.choice(len(T_pred), n, replace=False)
    ax.scatter(T_true[idx], T_pred[idx], alpha=0.3, s=4, color='teal')
    lo = min(T_true.min(), T_pred.min()) - 0.05
    hi = max(T_true.max(), T_pred.max()) + 0.05
    ax.plot([lo, hi], [lo, hi], 'r--', linewidth=1.0, label='y=x (perfetto)')
    ax.set_xlabel('T_true [s]')
    ax.set_ylabel('T_pred [s]')
    ax.set_title('G5 — Scatter T_pred vs T_true')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    _save(fig, out_path)


def plot_g6_spike_rate(log: dict, out_path: str):
    """G6 — Spike rate del layer hidden (diagnostica dead/saturated neurons)."""
    if not _MPL:
        return
    fig, ax = plt.subplots(figsize=(8, 3))
    ep = log['epoch']
    sr = log['spike_rate']
    ax.plot(ep, sr * 100.0, color='darkorange', linewidth=1.5)
    ax.axhspan(10, 20, alpha=0.12, color='green', label='Target 10–20%')
    ax.set_xlabel('Epoca')
    ax.set_ylabel('Spike rate medio [%]')
    ax.set_title('G6 — Spike rate layer hidden (ALIF)')
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    _save(fig, out_path)


def plot_g7_violin_params(param_samples: dict, out_path: str):
    """
    G7 — Violin plot delle 5 distribuzioni di parametri predetti.

    param_samples: dict con chiavi ['v0','T','s0','a','b'],
                   ognuna array 1D di valori fisici.
    """
    if not _MPL:
        return
    labels = ['v₀ [m/s]', 'T [s]', 's₀ [m]', 'a [m/s²]', 'b [m/s²]']
    keys   = ['v0', 'T', 's0', 'a', 'b']
    data   = [param_samples[k] for k in keys]

    # Range fisici di riferimento (da CF_FSNN_Net._PARAM_BOUNDS)
    bounds = [(8, 45), (0.5, 2.5), (1.0, 5.0), (0.3, 2.5), (0.5, 3.0)]

    fig, axes = plt.subplots(1, 5, figsize=(14, 4))
    for ax, d, lbl, (lo, hi) in zip(axes, data, labels, bounds):
        parts = ax.violinplot([d], showmeans=True, showmedians=True)
        for pc in parts['bodies']:
            pc.set_facecolor('steelblue')
            pc.set_alpha(0.5)
        ax.axhline(lo, color='red',   linestyle='--', linewidth=0.8)
        ax.axhline(hi, color='green', linestyle='--', linewidth=0.8)
        ax.set_title(lbl, fontsize=9)
        ax.set_xticks([])
    fig.suptitle('G7 — Distribuzioni parametri predetti (val set)', fontsize=10)
    plt.tight_layout()
    _save(fig, out_path)


# ===========================================================
# 3. Funzione principale
# ===========================================================

def plot_all(log: dict, out_dir: str,
             T_pred: np.ndarray = None,
             T_true: np.ndarray = None,
             param_samples: dict = None):
    """
    Genera tutti i grafici disponibili con i dati forniti.

    log:           dict da load_training_log()
    out_dir:       cartella di output
    T_pred/T_true: array per G5 (opzionali — se None G5 viene saltato)
    param_samples: dict per G7 (opzionale — se None G7 viene saltato)
    """
    # F3b: training abortito → log=None, nessun dato da plottare
    if log is None:
        print("[plot_diagnostics] Nessun log da plottare (log=None). Grafici saltati.")
        return
    if not _MPL:
        print("[plot_diagnostics] matplotlib non disponibile — grafici saltati.")
        return

    od = str(out_dir)
    print(f"[Diagnostics] Generazione grafici in: {od}")

    plot_g1_loss_curve(log,  os.path.join(od, 'G1_loss_curve.png'))
    plot_g2_components(log,  os.path.join(od, 'G2_components.png'))
    plot_g3_lr_schedule(log, os.path.join(od, 'G3_lr_schedule.png'))
    plot_g4_grad_norm(log,   os.path.join(od, 'G4_grad_norm.png'))
    plot_g6_spike_rate(log,  os.path.join(od, 'G6_spike_rate.png'))

    if T_pred is not None and T_true is not None:
        plot_g5_T_scatter(T_pred, T_true, os.path.join(od, 'G5_T_scatter.png'))
    else:
        print("  G5 saltato (T_pred/T_true non forniti)")

    if param_samples is not None:
        plot_g7_violin_params(param_samples, os.path.join(od, 'G7_violin_params.png'))
    else:
        print("  G7 saltato (param_samples non fornito)")

    print("[Diagnostics] Completato.")


# ===========================================================
# MAIN — test standalone
# ===========================================================

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Uso: python -m utils.plot_diagnostics checkpoints/<tag>/training_log.csv")
        sys.exit(0)

    csv_path = sys.argv[1]
    tag_dir  = os.path.dirname(csv_path)
    out_dir  = os.path.join(tag_dir, 'plots')

    log = load_training_log(csv_path)
    print(f"[plot_diagnostics] Log caricato: {len(log['epoch'])} epoche")
    plot_all(log, out_dir)
