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
    """G1 — Curva loss totale train/val per epoca.

    Marker visibili: in smoke mode (1 epoca = 1 punto) la linea non viene resa
    da matplotlib, quindi senza marker il grafico appare vuoto. Con marker='o'
    il valore numerico è sempre visibile, sia in smoke che in FULL training.
    """
    if not _MPL:
        return
    fig, ax = plt.subplots(figsize=(8, 4))
    ep = log['epoch']
    ax.plot(ep, log['train_total'], label='train', color='steelblue',
            linewidth=1.5, marker='o', markersize=5)
    ax.plot(ep, log['val_total'],   label='val',   color='coral',
            linewidth=1.5, marker='s', markersize=5)
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
        ax.plot(ep, vals, label=label, linewidth=1.2, marker='o', markersize=4)
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
    ax.plot(ep, log['lr'], color='green', linewidth=1.5, marker='o', markersize=5)
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
    ax.plot(ep, log['grad_norm'], color='purple', linewidth=1.2, alpha=0.8,
            marker='o', markersize=5)
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
    ax.plot(ep, sr * 100.0, color='darkorange', linewidth=1.5,
            marker='o', markersize=5)
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
# 2b. Telemetria estesa per-batch (T) — G8-G12
# ===========================================================

def load_batch_log(csv_path: str):
    """T: Carica training_batch_log.csv prodotto da BatchCSVLogger.

    Analoga a load_training_log() ma per il file per-batch. Restituisce dict
    {col_name: np.array} oppure None se il file non esiste o è vuoto
    (consistente con load_training_log per gestire training abortiti).
    """
    if not os.path.isfile(csv_path):
        print(f"[plot_diagnostics] Batch log non trovato (skip G8-G12): {csv_path}")
        return None

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print(f"[plot_diagnostics] Batch log vuoto (skip G8-G12): {csv_path}")
        return None

    data = {k: [] for k in rows[0].keys()}
    for row in rows:
        for k, v in row.items():
            try:
                data[k].append(float(v))
            except (ValueError, TypeError):
                data[k].append(float('nan'))
    return {k: np.array(v) for k, v in data.items()}


def _batch_xaxis(log: dict):
    """Indice "tempo training" lineare: per ogni riga, (epoch-1)*N_batch_per_ep + batch_idx.
    Più informativo del solo batch_idx perché distingue epoche diverse.
    Restituisce np.array (N,)."""
    ep = log['epoch'].astype(int)
    bi = log['batch_idx'].astype(int)
    # Numero di batch per epoca = max batch_idx osservato nell'epoca 1 (o nelle altre)
    n_per_ep = int(bi[ep == ep.min()].max()) if (ep == ep.min()).any() else int(bi.max())
    return (ep - 1) * n_per_ep + bi


def plot_g8_gn_per_batch(log: dict, out_path: str):
    """G8 — Norma gradiente per batch (pre + post clip, scala log).

    Mostra l'evoluzione esatta di gn batch-per-batch. I batch con `is_inf_grad=1`
    appaiono come marker rossi sopra una linea orizzontale di riferimento.
    Critico per diagnosticare exploding gradient (capire QUANDO esplode, da quanto sale)."""
    if not _MPL:
        return
    fig, ax = plt.subplots(figsize=(12, 4))
    x = _batch_xaxis(log)
    pre  = log['gn_total_preclip']
    post = log['gn_total_postclip']

    # Sostituisce inf con un valore alto per la visualizzazione log (1e20)
    pre_plot  = np.where(np.isfinite(pre),  pre,  1e20)
    post_plot = np.where(np.isfinite(post), post, 1e20)

    ax.plot(x, pre_plot,  label='gn pre-clip',  color='steelblue', linewidth=0.6, alpha=0.7)
    ax.plot(x, post_plot, label='gn post-clip', color='coral',     linewidth=0.6, alpha=0.7)
    ax.axhline(1.0, color='gray', linestyle='--', linewidth=0.6, label='clip max=1.0')

    # Marker per batch con inf grad
    inf_mask = log.get('is_inf_grad', np.zeros_like(x)).astype(bool)
    if inf_mask.any():
        ax.scatter(x[inf_mask], np.full(inf_mask.sum(), 1e15),
                   color='red', marker='x', s=30, label=f'inf_grad ({inf_mask.sum()})')

    ax.set_xlabel('Step training (epoca·N_batch + batch_idx)')
    ax.set_ylabel('Grad norm')
    ax.set_yscale('log')
    ax.set_title('G8 — Norma gradiente per batch (pre/post clip)')
    ax.legend(fontsize=8, loc='upper left')
    ax.grid(True, alpha=0.3)
    _save(fig, out_path)


def plot_g9_layer_norms_heatmap(log: dict, out_path: str):
    """G9 — Heatmap norme per-layer × batch.

    Vede quale layer esplode per primo e la propagazione dell'esplosione.
    Asse Y = 6 layer; asse X = step training; colore = log10(gn). Valori inf → bianco."""
    if not _MPL:
        return
    layer_cols = [
        'gn_hidden_fc', 'gn_hidden_recU', 'gn_hidden_recV',
        'gn_hidden_base_threshold', 'gn_hidden_thresh_jump', 'gn_out_fc',
    ]
    layer_labels = [
        'hidden.fc', 'hidden.rec_U', 'hidden.rec_V',
        'hidden.base_thresh', 'hidden.thresh_jump', 'out.fc',
    ]
    M = np.stack([log[c] for c in layer_cols], axis=0)   # (6, N_batch)
    # Sostituisci inf/nan con un valore alto per la visualizzazione
    M_safe = np.where(np.isfinite(M), M, 1e10)
    M_log  = np.log10(np.clip(M_safe, 1e-12, 1e10))

    fig, ax = plt.subplots(figsize=(12, 3.5))
    im = ax.imshow(M_log, aspect='auto', cmap='viridis',
                   interpolation='nearest', origin='lower')
    ax.set_yticks(range(len(layer_labels)))
    ax.set_yticklabels(layer_labels, fontsize=8)
    ax.set_xlabel('Batch index (lineare nel tempo training)')
    ax.set_title('G9 — log10(grad_norm) per-layer × batch')
    cbar = plt.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label('log10(gn)', fontsize=8)
    _save(fig, out_path)


def plot_g10_loss_components_per_batch(log: dict, out_path: str):
    """G10 — Componenti loss per batch (4 linee separate, scala log).

    Identifica quale componente diverge se la loss esplode (data/phys/ou/bc)."""
    if not _MPL:
        return
    fig, ax = plt.subplots(figsize=(12, 4))
    x = _batch_xaxis(log)
    ax.plot(x, np.clip(log['loss_data'], 1e-6, None), label='L_data', linewidth=0.6, alpha=0.8)
    ax.plot(x, np.clip(log['loss_phys'], 1e-6, None), label='L_phys', linewidth=0.6, alpha=0.8)
    ax.plot(x, np.clip(log['loss_ou'],   1e-6, None), label='L_OU',   linewidth=0.6, alpha=0.8)
    ax.plot(x, np.clip(log['loss_bc'],   1e-6, None), label='L_bc',   linewidth=0.6, alpha=0.8)
    ax.set_xlabel('Step training')
    ax.set_ylabel('Loss component (non pesata)')
    ax.set_yscale('log')
    ax.set_title('G10 — Componenti loss per batch')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    _save(fig, out_path)


def plot_g11_spike_rate_per_batch(log: dict, out_path: str):
    """G11 — Spike rate per batch (vede oscillazioni rapide o collasso sparsity)."""
    if not _MPL:
        return
    fig, ax = plt.subplots(figsize=(12, 3.5))
    x  = _batch_xaxis(log)
    sr = log['spike_rate'] * 100.0
    ax.plot(x, sr, color='darkorange', linewidth=0.6, alpha=0.8)
    ax.axhspan(10, 25, alpha=0.12, color='green', label='Target 10-25%')
    ax.set_xlabel('Step training')
    ax.set_ylabel('Spike rate [%]')
    ax.set_title('G11 — Spike rate hidden layer per batch')
    ax.set_ylim(0, 100)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    _save(fig, out_path)


def plot_g12_weight_max_per_batch(log: dict, out_path: str):
    """G12 — Massimo |peso| globale per batch.

    Detect pesi che si saturano o esplodono. Se i grad esplodono ma i pesi restano
    finiti (caso F1 dell'incidente), la curva resta piatta → conferma che il clip
    sta funzionando."""
    if not _MPL:
        return
    fig, ax = plt.subplots(figsize=(12, 3.5))
    x = _batch_xaxis(log)
    ax.plot(x, log['weight_max_abs_global'], color='purple', linewidth=0.6, alpha=0.8)
    ax.set_xlabel('Step training')
    ax.set_ylabel('max |w| globale')
    ax.set_title('G12 — Massimo valore assoluto pesi (globale)')
    ax.grid(True, alpha=0.3)
    _save(fig, out_path)


def plot_g13_signals_vs_params(traj_data: dict, out_path: str, dt: float = 0.1):
    """G13 — Confronto temporale segnali V2V (input) vs parametri IDM predetti (output).

    Mostra in 3 subplot impilati come il modello "interpreta" una traiettoria di val:

    - TOP:  V2V signals denormalizzati: s [m], v [m/s], dv [m/s], v_l [m/s]
    - MID:  T(t) predicted (linea solida) vs T_true (linea tratteggiata)
            È l'unico parametro con GT per-step (processo OU sul time gap, Ch12).
    - BOT:  v0, s0, a, b predicted (linee) vs scenario params veri (h-lines tratteggiate)
            Questi parametri sono COSTANTI per scenario; il modello dovrebbe scoprirli
            e mantenerli stabili nel tempo.

    traj_data: dict prodotto da train.py main(), contiene:
      's', 'v', 'dv', 'v_l'  — array (N,) fisici
      'T_true'                — array (N,) GT per-step
      'T_pred'                — array (N,) predicted
      'v0_pred', 's0_pred', 'a_pred', 'b_pred'  — array (N,) predicted
      'scenario_params'       — dict {'v0', 's0', 'a', 'b'} GT scenario (h-lines)
      'scenario'              — str (es. 'highway', 'urban', 'cut_in')
      'is_cut_in'             — bool
    dt: passo temporale in secondi (default 0.1)
    """
    if not _MPL:
        return
    N = len(traj_data['s'])
    t = np.arange(N) * dt

    fig = plt.figure(figsize=(13, 9))
    gs  = gridspec.GridSpec(3, 1, height_ratios=[1.0, 0.8, 1.0], hspace=0.35)

    # ── TOP: V2V signals ──────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0])
    ax1.plot(t, traj_data['s'],    label='s [m]',     color='tab:blue',   linewidth=1.1)
    ax1.plot(t, traj_data['v'],    label='v_ego [m/s]', color='tab:orange', linewidth=1.1)
    ax1.plot(t, traj_data['dv'],   label='Δv [m/s]',  color='tab:green',  linewidth=1.1)
    ax1.plot(t, traj_data['v_l'],  label='v_leader [m/s]', color='tab:red',    linewidth=1.1)
    ax1.set_ylabel('V2V signals')
    sc = traj_data.get('scenario', 'unknown')
    ci = ' (cut-in)' if traj_data.get('is_cut_in') else ''
    ax1.set_title(f'G13 — Segnali V2V vs parametri ACC-IDM predetti  |  scenario: {sc}{ci}')
    ax1.legend(fontsize=8, ncol=4, loc='upper right')
    ax1.grid(True, alpha=0.3)

    # ── MID: T predicted vs T_true ────────────────────────────────
    ax2 = fig.add_subplot(gs[1], sharex=ax1)
    ax2.plot(t, traj_data['T_pred'], label='T predicted', color='tab:purple', linewidth=1.2)
    ax2.plot(t, traj_data['T_true'], label='T_true (OU GT)',
             color='black', linewidth=1.0, linestyle='--', alpha=0.7)
    ax2.set_ylabel('Time gap T [s]')
    ax2.legend(fontsize=8, loc='upper right')
    ax2.grid(True, alpha=0.3)
    # Bound fisici di T per riferimento
    ax2.axhline(0.5, color='gray', linestyle=':', linewidth=0.5)
    ax2.axhline(2.5, color='gray', linestyle=':', linewidth=0.5)

    # ── BOT: v0, s0, a, b predicted vs scenario constants ─────────
    ax3 = fig.add_subplot(gs[2], sharex=ax1)
    sp = traj_data.get('scenario_params', {})
    # Coppie (chiave_pred, label, color, h-line value se presente in scenario_params)
    pairs = [
        ('v0_pred', 'v₀ [m/s]', 'tab:blue',   sp.get('v0')),
        ('s0_pred', 's₀ [m]',   'tab:orange', sp.get('s0')),
        ('a_pred',  'a [m/s²]', 'tab:green',  sp.get('a')),
        ('b_pred',  'b [m/s²]', 'tab:red',    sp.get('b')),
    ]
    for key, lbl, col, gt_val in pairs:
        ax3.plot(t, traj_data[key], label=lbl, color=col, linewidth=1.1)
        if gt_val is not None:
            ax3.axhline(gt_val, color=col, linestyle='--', linewidth=0.8, alpha=0.6)
    ax3.set_xlabel('Tempo [s]')
    ax3.set_ylabel('Parametri IDM')
    ax3.legend(fontsize=8, ncol=4, loc='upper right')
    ax3.grid(True, alpha=0.3)

    _save(fig, out_path)


# ===========================================================
# 3. Funzione principale
# ===========================================================

def plot_all(log: dict, out_dir: str,
             T_pred: np.ndarray = None,
             T_true: np.ndarray = None,
             param_samples: dict = None,
             batch_log: dict = None,
             trajectories: list = None):
    """
    Genera tutti i grafici disponibili con i dati forniti.

    log:           dict da load_training_log() — per-epoca (G1-G7)
    out_dir:       cartella di output
    T_pred/T_true: array per G5 (opzionali — se None G5 viene saltato)
    param_samples: dict per G7 (opzionale — se None G7 viene saltato)
    batch_log:     dict da load_batch_log() — per-batch (G8-G12)
                   T (telemetria estesa): se None i grafici G8-G12 vengono saltati.
                   Indipendente dai G1-G7: anche se log=None ma batch_log esiste,
                   G8-G12 vengono comunque generati (vedi note sotto).
    trajectories:  lista di dict (1 per traiettoria val da plottare) per G13.
                   Ogni dict deve contenere le chiavi documentate in
                   plot_g13_signals_vs_params. Se None, G13 viene saltato.
    """
    if not _MPL:
        print("[plot_diagnostics] matplotlib non disponibile — grafici saltati.")
        return

    od = str(out_dir)
    print(f"[Diagnostics] Generazione grafici in: {od}")

    # G1-G7 (per-epoca) — saltati se log=None (training abortito prima di epoch 1)
    if log is not None:
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
    else:
        print("[plot_diagnostics] log per-epoca vuoto/assente — G1-G7 saltati.")

    # G8-G12 (per-batch — T telemetria estesa) — indipendenti da G1-G7
    # Anche su training abortito a metà E01, batch_log esiste con i dati raccolti.
    if batch_log is not None:
        plot_g8_gn_per_batch(batch_log,             os.path.join(od, 'G8_gn_per_batch.png'))
        plot_g9_layer_norms_heatmap(batch_log,      os.path.join(od, 'G9_layer_norms_heatmap.png'))
        plot_g10_loss_components_per_batch(batch_log, os.path.join(od, 'G10_loss_per_batch.png'))
        plot_g11_spike_rate_per_batch(batch_log,    os.path.join(od, 'G11_spike_rate_per_batch.png'))
        plot_g12_weight_max_per_batch(batch_log,    os.path.join(od, 'G12_weight_max_per_batch.png'))
    else:
        print("  G8-G12 saltati (batch_log non fornito)")

    # G13 (signals vs params) — 1 PNG per traiettoria val
    if trajectories:
        for traj in trajectories:
            sc = traj.get('scenario', 'unknown')
            ci = '_cutin' if traj.get('is_cut_in') else ''
            fname = f'G13_traj_{sc}{ci}.png'
            plot_g13_signals_vs_params(traj, os.path.join(od, fname))
    else:
        print("  G13 saltato (trajectories non fornito)")

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
