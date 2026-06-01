"""
utils/simulator/anim.py -- Animazione replay scenario (Layout C).

Layout C: 2-subplot side-by-side
  LEFT:  top-down view che si aggiorna frame-by-frame (Layout B in tempo)
  RIGHT: time series stack (gap/v/a) + linea verticale al frame corrente
         + progressive spike raster (eventi visualizzati fino al frame)

Export: save_animation(anim, 'output.gif', fps=10)
         save_animation(anim, 'output.mp4', fps=10)  -- richiede ffmpeg
"""

from __future__ import annotations
from typing import Optional
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as manim
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Rectangle, FancyArrow

from utils.simulator.engine import SimulationResult
from utils.simulator.plots import COLORS


def animate_scenario(r: SimulationResult,
                       fps: int = 10,
                       figsize=(14, 7),
                       title: Optional[str] = None) -> manim.FuncAnimation:
    """Costruisce matplotlib FuncAnimation per replay scenario.

    L'animazione ha T frames (= seq_len), uno per ogni tick DT.
    fps default 10 = real-time (DT=0.1s => 10 frames/sec).

    Args:
        r: SimulationResult
        fps: frame-per-second (default 10 = real-time)
        figsize: figura (default 14x7 inches)
        title: titolo opzionale (auto-generato)

    Returns: matplotlib.animation.FuncAnimation (richiamabile con HTML5() o save)
    """
    T = r.seq_len
    fig = plt.figure(figsize=figsize)
    gs = GridSpec(4, 2, figure=fig, hspace=0.55, wspace=0.25,
                  height_ratios=[1.8, 1.5, 1.5, 1.8],
                  width_ratios=[1.4, 1.0])

    # ── LEFT: top-down (occupa tutte le righe) ──────────────────
    ax_top = fig.add_subplot(gs[:, 0])
    # ── RIGHT: 4 sub-panel impilati ────────────────────────────
    ax_gap   = fig.add_subplot(gs[0, 1])
    ax_v     = fig.add_subplot(gs[1, 1])
    ax_a     = fig.add_subplot(gs[2, 1])
    ax_spike = fig.add_subplot(gs[3, 1])

    # ── Setup top-down (sfondo: strada, range x) ────────────────
    x_min = min(r.x_ego_pred.min(), r.x_ego_gt.min()) - 10
    x_max = r.x_lead.max() + 10
    ax_top.set_xlim(x_min, x_max)
    ax_top.set_ylim(-1.5, 1.5)
    ax_top.set_yticks([])
    ax_top.axhline(0, color='#bbbbbb', linewidth=0.8, alpha=0.7)
    ax_top.axhline(-0.7, color='#888888', linewidth=0.4, alpha=0.5)
    ax_top.axhline(+0.7, color='#888888', linewidth=0.4, alpha=0.5)
    ax_top.set_xlabel('position x [m]')
    ax_top.set_title('Replay 1D top-down')

    # Patches (created once, updated per frame)
    veh_w, veh_h = 4.0, 0.6
    rect_lead = Rectangle((0, -veh_h/2), veh_w, veh_h,
                            facecolor=COLORS['leader'], edgecolor='black', linewidth=1.2, alpha=0.9,
                            label='Leader')
    rect_ego_gt = Rectangle((0, -veh_h/2), veh_w, veh_h,
                              facecolor=COLORS['ego_gt'], edgecolor='black', linewidth=0.8, alpha=0.35,
                              linestyle='--', label='Ego GT (fantasma)')
    rect_ego_pred = Rectangle((0, -veh_h/2), veh_w, veh_h,
                                facecolor=COLORS['ego_pred'], edgecolor='black', linewidth=1.2, alpha=0.9,
                                label='Ego pred')
    ax_top.add_patch(rect_lead)
    ax_top.add_patch(rect_ego_gt)
    ax_top.add_patch(rect_ego_pred)
    gap_text = ax_top.text(0, 0.95, '', ha='center', va='center', fontsize=9,
                             bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#888'))
    title_top = ax_top.text(0.5, 1.05, '', transform=ax_top.transAxes,
                              ha='center', va='bottom', fontsize=9)
    ax_top.legend(loc='lower right', fontsize=8, framealpha=0.85)

    # ── Setup right panels (curve complete + linea verticale dinamica) ──
    # Gap
    ax_gap.plot(r.time, r.gap_gt, '--', color=COLORS['ego_gt'], linewidth=1.2, label='gap GT')
    ax_gap.plot(r.time, r.gap_pred, '-', color=COLORS['ego_pred'], linewidth=1.5, label='gap pred')
    ax_gap.set_ylabel('gap [m]'); ax_gap.set_title('Gap nel tempo', fontsize=10)
    ax_gap.legend(fontsize=8); ax_gap.grid(alpha=0.3)
    vline_gap = ax_gap.axvline(r.time[0], color='red', linewidth=1.2)

    # Velocity
    ax_v.plot(r.time, r.vl_obs, '-', color=COLORS['leader'], linewidth=1.2, label='v_lead')
    ax_v.plot(r.time, r.v_ego_gt, '--', color=COLORS['ego_gt'], linewidth=1.2, label='v_ego GT')
    ax_v.plot(r.time, r.v_ego_pred, '-', color=COLORS['ego_pred'], linewidth=1.5, label='v_ego pred')
    ax_v.set_ylabel('v [m/s]'); ax_v.set_title('Velocita\'', fontsize=10)
    ax_v.legend(fontsize=8); ax_v.grid(alpha=0.3)
    vline_v = ax_v.axvline(r.time[0], color='red', linewidth=1.2)

    # Accel
    ax_a.plot(r.time, r.a_gt, '--', color=COLORS['ego_gt'], linewidth=1.2, label='a GT')
    ax_a.plot(r.time, r.a_pred, '-', color=COLORS['ego_pred'], linewidth=1.5, label='a pred')
    ax_a.set_ylabel('a [m/s²]'); ax_a.set_title('Accelerazione', fontsize=10)
    ax_a.legend(fontsize=8); ax_a.grid(alpha=0.3)
    vline_a = ax_a.axvline(r.time[0], color='red', linewidth=1.2)

    # Spike raster (progressive: solo eventi fino a t corrente)
    hidden = r.spike_full.shape[1]
    threshold = 0.05
    # Pre-compute event times per neuron
    events_all = []
    for n in range(hidden):
        active_t = r.time[r.spike_full[:, n] > threshold]
        events_all.append(active_t)
    # Initial empty eventplot — will be redrawn each frame
    ax_spike.set_ylabel('neuron'); ax_spike.set_title('Spike raster (progressivo)', fontsize=10)
    ax_spike.set_xlim(r.time[0], r.time[-1]); ax_spike.set_ylim(-0.5, hidden - 0.5)
    ax_spike.set_xlabel('time [s]')
    ax_spike.grid(alpha=0.3, axis='x')
    spike_collections = ax_spike.eventplot([[] for _ in range(hidden)],
                                              colors=COLORS['spike'],
                                              linewidths=0.6, linelengths=0.7)
    vline_spike = ax_spike.axvline(r.time[0], color='red', linewidth=1.2)

    # Suptitle
    if title is None:
        title = (f'CF_FSNN replay: scenario idx={r.idx} [{r.scenario_type}'
                 + (', cut-in' if r.is_cut_in else '')
                 + f']  T={T*r.DT:.1f}s')
    fig.suptitle(title, fontsize=11, fontweight='bold', y=0.995)

    # ── Update function ────────────────────────────────────────
    def update(frame):
        t = frame  # 0..T-1
        # Top-down rectangles
        xl  = r.x_lead[t]
        xeg = r.x_ego_gt[t]
        xep = r.x_ego_pred[t]
        rect_lead.set_x(xl - veh_w)
        rect_ego_gt.set_x(xeg - veh_w)
        rect_ego_pred.set_x(xep - veh_w)
        # Gap label position + text
        gap_text.set_x((xep + xl) / 2)
        gap_text.set_text(f'gap_pred={r.gap_pred[t]:.1f}m')
        # Title with time + state
        title_top.set_text(f't={r.time[t]:.1f}s  '
                            f'v_pred={r.v_ego_pred[t]:.1f}m/s  '
                            f'a_pred={r.a_pred[t]:+.2f}m/s²  '
                            f'sr={r.spike_rate[t]*100:.1f}%')

        # Vertical lines on right panels
        for vl in [vline_gap, vline_v, vline_a, vline_spike]:
            vl.set_xdata([r.time[t], r.time[t]])

        # Progressive eventplot: rebuild with events up to current t
        events_partial = [evts[evts <= r.time[t]] for evts in events_all]
        # Remove old eventplot collections + redraw
        for c in spike_collections:
            c.remove()
        spike_collections[:] = ax_spike.eventplot(events_partial,
                                                     colors=COLORS['spike'],
                                                     linewidths=0.6, linelengths=0.7)

        # Return all artists (richiesto da blit=False, OK lasciamo None)
        return [rect_lead, rect_ego_gt, rect_ego_pred, gap_text, title_top,
                vline_gap, vline_v, vline_a, vline_spike, *spike_collections]

    interval_ms = 1000 // fps
    anim = manim.FuncAnimation(fig, update, frames=T, interval=interval_ms,
                                  blit=False, repeat=True)
    return anim


def save_animation(anim: manim.FuncAnimation, output_path: str, fps: int = 10):
    """Salva animation in formato dedotto da estensione.

    Estensioni supportate:
      .gif  -- pillow writer (default, no extra deps)
      .mp4  -- ffmpeg writer (richiede ffmpeg installato e in PATH)
      .html -- HTMLWriter (embed in notebook)

    Args:
        anim: FuncAnimation
        output_path: path di destinazione
        fps: frame-per-second per encoding
    """
    ext = output_path.lower().rsplit('.', 1)[-1]
    if ext == 'gif':
        writer = manim.PillowWriter(fps=fps)
    elif ext == 'mp4':
        writer = manim.FFMpegWriter(fps=fps, bitrate=1800)
    elif ext == 'html':
        writer = manim.HTMLWriter(fps=fps, embed_frames=True)
    else:
        raise ValueError(f'Extension non supportata: .{ext}. Use .gif | .mp4 | .html')
    print(f'[save_animation] writing {output_path} ({writer.__class__.__name__}, fps={fps})...')
    anim.save(output_path, writer=writer)
    import os
    sz = os.path.getsize(output_path) / 1024 / 1024
    print(f'[save_animation] DONE: {output_path} ({sz:.1f} MB)')
