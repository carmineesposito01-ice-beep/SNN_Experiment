"""
utils/simulator/plots.py -- Figure builders statici per SimulationResult.

Layout A: multi-panel detailed (5 panels + metric overlay) -- per paper figures
Layout B: top-down spatial snapshot (single frame) -- per animation building block
Layout: spike raster -- componente riusabile per Layout A panel 5

Tutte le funzioni accettano un SimulationResult e ritornano matplotlib Figure.
"""

from __future__ import annotations
from typing import Optional, Dict, Any
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Rectangle, FancyArrow

from utils.simulator.engine import SimulationResult
from utils.simulator.metrics import compute_operational_metrics


# ============================================================
# Colors (palette consistente attraverso tutti i plot)
# ============================================================
COLORS = {
    'leader':   '#FFB400',     # giallo ambra
    'ego_gt':   '#2EA3F2',     # blu chiaro
    'ego_pred': '#E64A19',     # arancione vivo
    'gap':      '#888888',     # grigio neutro
    'spike':    '#1B5E20',     # verde scuro (event)
    'param_true':  '#666666',  # grigio dark per linee horizon true
    'param_pred':  '#E64A19',  # stesso del ego_pred
    'cut_in':       '#D32F2F', # rosso intenso per cut-in event
    'cut_in_band':  '#FFCDD2', # rosa pallido per shaded post-cut-in window
}


def _draw_cut_in_marker(ax, r, post_window_s: float = 2.0):
    """Disegna marker cut-in su un Axes con asse x = time.

    - Banda verticale shaded (rosa pallido) dal cut_in_t a cut_in_t + post_window_s
    - Linea verticale rossa al cut_in_t
    - Label 'CUT-IN' in alto a destra della linea

    Se r non ha cut_in_t (= None), no-op.
    """
    if r.cut_in_t is None:
        return
    t_cut = r.time[r.cut_in_t]
    t_end_band = min(t_cut + post_window_s, r.time[-1])
    # Shaded transient window
    ax.axvspan(t_cut, t_end_band, alpha=0.20, color=COLORS['cut_in_band'],
                zorder=0, label=f'cut-in transient ({post_window_s:.0f}s)')
    # Vertical line
    ax.axvline(t_cut, color=COLORS['cut_in'], linewidth=1.6, linestyle='-',
                zorder=1, alpha=0.9)
    # Label CUT-IN
    ax.text(t_cut, ax.get_ylim()[1] * 0.95, ' CUT-IN',
             ha='left', va='top', fontsize=8, fontweight='bold',
             color=COLORS['cut_in'],
             bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                        edgecolor=COLORS['cut_in'], alpha=0.85))


# ============================================================
# Layout A: figura statica multi-pannello (per paper)
# ============================================================
def plot_simulation_static(r: SimulationResult,
                            metrics: Optional[Dict[str, Any]] = None,
                            figsize=(13, 16),
                            title: Optional[str] = None) -> Figure:
    """5-panel + metric overlay statico per uno scenario.

    Panels:
      1. Spaziotemporale x(t): leader, ego_pred, ego_gt + shaded gap
      2. Velocita': v_leader, v_ego_pred, v_ego_gt
      3. Accelerazione: a_pred vs a_gt (line + correlazione)
      4. 5 params IDM: predicted seq vs true constants (small multiples 2x3)
      5. Spike raster: 32 neuroni x T tick (eventplot)

    Args:
        r:        SimulationResult
        metrics:  dict da compute_operational_metrics (se None, ricalcolato)
        figsize:  dimensioni in inches (default 13x16, ottimale A4)
        title:    titolo opzionale (default auto-generato)

    Returns: matplotlib.figure.Figure
    """
    if metrics is None:
        metrics = compute_operational_metrics(r)

    fig = plt.figure(figsize=figsize)
    # GridSpec: 5 zone con altezze diverse
    gs = GridSpec(6, 1, figure=fig,
                  height_ratios=[3.0, 2.0, 2.0, 2.5, 2.0, 0.6],
                  hspace=0.45)

    # ── PANEL 1: Spaziotemporale x(t) ─────────────────────────────
    ax1 = fig.add_subplot(gs[0])
    _plot_spacetime(ax1, r)

    # ── PANEL 2: Velocita' ───────────────────────────────────────
    ax2 = fig.add_subplot(gs[1])
    _plot_velocity(ax2, r)

    # ── PANEL 3: Accelerazione ───────────────────────────────────
    ax3 = fig.add_subplot(gs[2])
    _plot_acceleration(ax3, r)

    # ── PANEL 4: 5 IDM params (small multiples) ──────────────────
    ax4_outer = fig.add_subplot(gs[3])
    _plot_idm_params(fig, gs[3], r)
    ax4_outer.axis('off')  # outer placeholder hidden

    # ── PANEL 5: Spike raster ────────────────────────────────────
    ax5 = fig.add_subplot(gs[4])
    _plot_spike_raster(ax5, r)

    # ── BOTTOM: metric overlay text ──────────────────────────────
    ax6 = fig.add_subplot(gs[5])
    _plot_metrics_overlay(ax6, metrics)

    # Title
    if title is None:
        cut_in_str = ''
        if r.cut_in_t is not None:
            cut_in_str = (f', CUT-IN at t={r.time[r.cut_in_t]:.1f}s '
                          f'(gap drop {r.cut_in_gap_before:.0f}->{r.cut_in_gap_after:.0f}m)')
        elif r.is_cut_in:
            cut_in_str = ', cut-in flagged (outside sim window)'
        title = (f'Scenario idx={r.idx} [{r.scenario_type}{cut_in_str}]  '
                 + f'T={r.seq_len*r.DT:.1f}s  '
                 + f'gap_rmse={metrics["gap_rmse_m"]:.2f}m  '
                 + f'pos_drift={metrics["pos_cum_err_m"]:.2f}m')
    fig.suptitle(title, fontsize=11, fontweight='bold', y=0.995)

    return fig


# ============================================================
# Internal panel helpers
# ============================================================
def _plot_spacetime(ax, r: SimulationResult):
    """Panel 1: x(t) leader vs ego_pred vs ego_gt + gap area."""
    ax.plot(r.time, r.x_lead, '-', color=COLORS['leader'], linewidth=2.0, label='Leader')
    ax.plot(r.time, r.x_ego_gt, '--', color=COLORS['ego_gt'], linewidth=1.8, label='Ego (GT)')
    ax.plot(r.time, r.x_ego_pred, '-', color=COLORS['ego_pred'], linewidth=2.0, label='Ego (SNN-pred)')
    # Shaded gap (ego_gt -> leader)
    ax.fill_between(r.time, r.x_ego_gt, r.x_lead, color=COLORS['gap'], alpha=0.15, label='Gap (GT)')
    ax.set_xlabel('time [s]')
    ax.set_ylabel('position x [m]')
    ax.set_title('Panel 1: Spazio-temporale  (leader, ego GT, ego predetto)')
    ax.legend(loc='upper left', fontsize=9, framealpha=0.85)
    ax.grid(alpha=0.3)
    _draw_cut_in_marker(ax, r)


def _plot_velocity(ax, r: SimulationResult):
    """Panel 2: velocita' nel tempo."""
    ax.plot(r.time, r.vl_obs, '-', color=COLORS['leader'], linewidth=1.8, label='v_leader')
    ax.plot(r.time, r.v_ego_gt, '--', color=COLORS['ego_gt'], linewidth=1.5, label='v_ego (GT)')
    ax.plot(r.time, r.v_ego_pred, '-', color=COLORS['ego_pred'], linewidth=1.8, label='v_ego (pred)')
    ax.set_xlabel('time [s]')
    ax.set_ylabel('velocity [m/s]')
    ax.set_title('Panel 2: Velocita\' temporale')
    ax.legend(loc='best', fontsize=9, framealpha=0.85)
    ax.grid(alpha=0.3)
    _draw_cut_in_marker(ax, r)


def _plot_acceleration(ax, r: SimulationResult):
    """Panel 3: a_pred vs a_gt time series + correlation inset."""
    ax.plot(r.time, r.a_gt, '--', color=COLORS['ego_gt'], linewidth=1.5, label='a (GT)')
    ax.plot(r.time, r.a_pred, '-', color=COLORS['ego_pred'], linewidth=1.5, label='a (pred via acc_iidm_accel)')
    ax.set_xlabel('time [s]')
    ax.set_ylabel('accel [m/s²]')
    ax.set_title('Panel 3: Accelerazione predetta vs ground-truth')
    ax.legend(loc='best', fontsize=9, framealpha=0.85)
    ax.grid(alpha=0.3)
    _draw_cut_in_marker(ax, r)
    # Inset: scatter correlation
    from mpl_toolkits.axes_grid1.inset_locator import inset_axes
    iax = inset_axes(ax, width='25%', height='40%', loc='upper right',
                      bbox_to_anchor=(-0.02, -0.05, 1, 1), bbox_transform=ax.transAxes)
    iax.scatter(r.a_gt, r.a_pred, s=8, c=r.time, cmap='viridis', alpha=0.6)
    lim = [min(r.a_gt.min(), r.a_pred.min()), max(r.a_gt.max(), r.a_pred.max())]
    iax.plot(lim, lim, 'k--', linewidth=0.8, alpha=0.5)
    iax.set_xlabel('GT', fontsize=7)
    iax.set_ylabel('pred', fontsize=7)
    iax.tick_params(labelsize=6)
    iax.grid(alpha=0.2)
    iax.set_title('scatter', fontsize=7)


def _plot_idm_params(fig: Figure, outer_gs_slot, r: SimulationResult):
    """Panel 4: small multiples 2x3 dei 5 params IDM (predicted seq vs true const)."""
    # Sub-gridspec 2x3 dentro lo slot
    from matplotlib.gridspec import GridSpecFromSubplotSpec
    sub_gs = GridSpecFromSubplotSpec(2, 3, subplot_spec=outer_gs_slot,
                                       hspace=0.5, wspace=0.35)
    param_info = [
        ('v0', 0, 'v0 [m/s]', [8.0, 45.0]),
        ('T',  1, 'T [s]',    [0.5, 2.5]),
        ('s0', 2, 's0 [m]',   [1.0, 5.0]),
        ('a',  3, 'a [m/s²]', [0.3, 2.5]),
        ('b',  4, 'b [m/s²]', [0.5, 3.0]),
    ]
    for i, (name, col_idx, ylabel, bounds) in enumerate(param_info):
        sub_ax = fig.add_subplot(sub_gs[i // 3, i % 3])
        pred_seq = r.params_pred[:, col_idx]
        true_val = r.params_true.get(name, np.nan)
        sub_ax.plot(r.time, pred_seq, '-', color=COLORS['param_pred'],
                     linewidth=1.5, label='pred')
        if not np.isnan(true_val):
            sub_ax.axhline(true_val, ls='--', color=COLORS['param_true'],
                            linewidth=1.5, label=f'true={true_val:.2f}')
        # Range bounds
        sub_ax.axhline(bounds[0], ls=':', color='#cccccc', linewidth=0.7)
        sub_ax.axhline(bounds[1], ls=':', color='#cccccc', linewidth=0.7)
        sub_ax.set_ylim(bounds[0] - 0.1*(bounds[1]-bounds[0]),
                        bounds[1] + 0.1*(bounds[1]-bounds[0]))
        sub_ax.set_ylabel(ylabel, fontsize=9)
        sub_ax.set_title(name, fontsize=10, fontweight='bold')
        sub_ax.legend(fontsize=7, loc='best', framealpha=0.85)
        sub_ax.grid(alpha=0.3)
        if i // 3 == 1:
            sub_ax.set_xlabel('time [s]', fontsize=8)
    # Hide 6th slot
    sub_ax6 = fig.add_subplot(sub_gs[1, 2])
    sub_ax6.text(0.5, 0.5, 'Panel 4: IDM params\n(predicted seq vs true)',
                  ha='center', va='center', transform=sub_ax6.transAxes,
                  fontsize=9, style='italic', color='#888')
    sub_ax6.axis('off')


def _plot_spike_raster(ax, r: SimulationResult):
    """Panel 5: spike raster hidden layer (T tick x hidden neurons).

    Usa matplotlib.eventplot per stile neuroscience standard.
    spike_full ha shape (T, hidden) con valori in [0,1] (mean over n_ticks).
    Per il raster: per ogni neurone, lista dei time-steps dove spike_rate > 0.05.
    """
    T = r.spike_full.shape[0]
    hidden = r.spike_full.shape[1]
    threshold = 0.05  # soglia per considerare "spike attivo" in quel macro-tick

    events_per_neuron = []
    for n in range(hidden):
        active_t = r.time[r.spike_full[:, n] > threshold]
        events_per_neuron.append(active_t)

    if any(len(e) > 0 for e in events_per_neuron):
        ax.eventplot(events_per_neuron, colors=COLORS['spike'], linewidths=0.6, linelengths=0.7)
    else:
        ax.text(0.5, 0.5, '(no spike attivi sopra threshold 0.05)',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=10, style='italic', color='#888')

    ax.set_xlabel('time [s]')
    ax.set_ylabel('neuron idx')
    ax.set_title(f'Panel 5: Spike raster hidden layer ({hidden} neuroni)  '
                 f'avg_sr={r.spike_rate.mean()*100:.1f}%')
    ax.set_xlim(r.time[0], r.time[-1])
    ax.set_ylim(-0.5, hidden - 0.5)
    ax.grid(alpha=0.3, axis='x')
    _draw_cut_in_marker(ax, r)


def _plot_metrics_overlay(ax, metrics: Dict[str, Any]):
    """Bottom text overlay con le metriche chiave."""
    ax.axis('off')
    txt = (
        f"gap_rmse = {metrics['gap_rmse_m']:.3f} m  |  "
        f"gap_max_err = {metrics['gap_max_err_m']:.3f} m  |  "
        f"pos_cum_err = {metrics['pos_cum_err_m']:.3f} m  |  "
        f"accel_rmse = {metrics['accel_rmse_masked']:.4f} m/s²  |  "
        f"jerk_max = {metrics['jerk_max_pred']:.2f}  |  "
        f"TTC_min = "
        + (f"{metrics['ttc_min_pred_s']:.2f} s" if np.isfinite(metrics['ttc_min_pred_s']) else "inf")
        + f"  |  spike_avg = {metrics['spike_rate_avg']*100:.1f}%"
    )
    ax.text(0.5, 0.5, txt, ha='center', va='center', transform=ax.transAxes,
             fontsize=9, family='monospace',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='#f5f5f5', edgecolor='#aaaaaa'))


# ============================================================
# Layout B: top-down spatial snapshot (single frame, per animation)
# ============================================================
def plot_topdown_snapshot(r: SimulationResult, t_frame: int,
                            ax=None, figsize=(12, 3.5)) -> Figure:
    """Snapshot top-down al tick t_frame.

    Mostra leader (giallo) + ego_pred (arancione) + ego_gt (blu trasparente
    "fantasma") su una strada 1D orizzontale, con frecce velocity.

    Args:
        r: SimulationResult
        t_frame: indice temporale (0..T-1)
        ax: matplotlib Axes (se None, crea Figure)
        figsize: (W, H) inches solo se ax=None

    Returns: matplotlib.figure.Figure
    """
    own_fig = False
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
        own_fig = True
    else:
        fig = ax.figure

    # Range strada: da min(x_ego_pred) - 10m a max(x_lead) + 10m (intera durata)
    x_min = min(r.x_ego_pred.min(), r.x_ego_gt.min()) - 10
    x_max = r.x_lead.max() + 10
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(-1.5, 1.5)
    ax.set_yticks([])
    # Linea strada
    ax.axhline(0, color='#bbbbbb', linewidth=0.8, alpha=0.7)
    ax.axhline(-0.7, color='#888888', linewidth=0.4, alpha=0.5)
    ax.axhline(+0.7, color='#888888', linewidth=0.4, alpha=0.5)

    # Vehicle rectangles (size ~4m x 0.6 lane width)
    veh_w = 4.0
    veh_h = 0.6

    # Leader (giallo)
    xl = r.x_lead[t_frame]
    ax.add_patch(Rectangle((xl - veh_w, -veh_h/2), veh_w, veh_h,
                            facecolor=COLORS['leader'], edgecolor='black', linewidth=1.2, alpha=0.9))
    # Vec velocita' leader
    vl = r.vl_obs[t_frame]
    if vl > 0:
        ax.add_patch(FancyArrow(xl + 0.5, 0, vl * 0.5, 0,
                                  width=0.15, head_width=0.4, head_length=1.5,
                                  facecolor=COLORS['leader'], edgecolor='black', linewidth=0.5, alpha=0.7))

    # Ego GT (blu trasparente, "fantasma")
    xeg = r.x_ego_gt[t_frame]
    ax.add_patch(Rectangle((xeg - veh_w, -veh_h/2), veh_w, veh_h,
                            facecolor=COLORS['ego_gt'], edgecolor='black', linewidth=0.8, alpha=0.35,
                            linestyle='--'))

    # Ego PRED (arancione vivo, principale)
    xep = r.x_ego_pred[t_frame]
    ax.add_patch(Rectangle((xep - veh_w, -veh_h/2), veh_w, veh_h,
                            facecolor=COLORS['ego_pred'], edgecolor='black', linewidth=1.2, alpha=0.9))
    vep = r.v_ego_pred[t_frame]
    if vep > 0:
        ax.add_patch(FancyArrow(xep + 0.5, 0, vep * 0.5, 0,
                                  width=0.15, head_width=0.4, head_length=1.5,
                                  facecolor=COLORS['ego_pred'], edgecolor='black', linewidth=0.5, alpha=0.7))

    # Gap label
    gap = r.gap_pred[t_frame]
    ax.text((xep + xl) / 2, 0.95, f'gap={gap:.1f}m', ha='center', va='center',
             fontsize=8, bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#888'))

    # Cut-in status (se applicable)
    cut_in_status = ''
    if r.cut_in_t is not None:
        if t_frame < r.cut_in_t:
            cut_in_status = f'  | pre-cut-in ({r.cut_in_t-t_frame} ticks to event)'
        elif t_frame == r.cut_in_t:
            cut_in_status = '  | >>> CUT-IN EVENT <<<'
        else:
            elapsed = (t_frame - r.cut_in_t) * r.DT
            cut_in_status = f'  | post-cut-in (+{elapsed:.1f}s)'

    # Time + metric info
    ax.set_title(f't = {r.time[t_frame]:.1f}s  |  '
                  f'v_ego_pred={vep:.1f} m/s  v_lead={vl:.1f} m/s  '
                  f'a_pred={r.a_pred[t_frame]:+.2f} m/s²{cut_in_status}', fontsize=9)
    ax.set_xlabel('position x [m]')

    return fig
