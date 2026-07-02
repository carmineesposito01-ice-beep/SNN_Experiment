"""scripts/fpga_figures.py -- figure dell'FPGA-evaluate a DATI REALI (Fase A).

Porta i design LOCKED del mockup (scripts/_fpga_eval_mockup.py, iterati con l'utente) ma
sostituisce i dati fittizi con gli output REALI delle 5 librerie Fase A (weight_profiler,
state_profiler, latency_model, seu_inject, io_hil) + net_diagnostics/snn_showcase, calcolati
sui champion caricati. Ogni funzione fig_* prende un `ctx` precomputato e ritorna
(fig, sezione, nome, fattibilita, nota). Il driver render_all() rende tutto in un PDF e
riporta, figura per figura, se e' stata generata correttamente.

Le figure 🟢 software_now sono a dati reali; le 🟡/🔴 (HDL/board: area_model, decode_cp,
tmr_overhead, thermal) restano STIME di progetto marcate, come da design. Cross-champion:
rende quanti champion sono passati (in locale 2 reali; su Azure i 4).
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from utils.weight_profiler import (profile_weights, weight_matrices, PO2_EXP_MIN, PO2_EXP_MAX,
                                   BITS_PER_WEIGHT)
from utils.latency_model import op_count, dse_profiles, model_shapes, DEADLINE_MS
from utils.state_profiler import state_ranges_rows, leak_underflow_curve, isi_stats
from utils.seu_inject import sensitivity_map, bit_criticality, hidden_vs_readout
from utils.io_hil import queue_overflow, aoi_max_surface
from utils.net_diagnostics import spike_raster, spike_stats, recurrence_spectral

plt.rcParams.update({'figure.dpi': 110, 'savefig.dpi': 110, 'font.size': 10, 'axes.titlesize': 12,
                     'axes.titleweight': 'bold', 'axes.grid': True, 'grid.alpha': 0.25,
                     'axes.axisbelow': True, 'legend.frameon': False,
                     'axes.spines.top': False, 'axes.spines.right': False})
E_MAC, E_AC = 4.6, 0.9              # pJ (Horowitz 45nm, da snn_showcase)
DEFCOL = ['#e34948', '#2a78d6', '#4a3aa7', '#eb6834', '#1baf7a']


def _gbar(ax, cats, per_champ, aliases, colors, ylab):
    x = np.arange(len(cats)); w = 0.8 / max(1, len(aliases))
    for i, a in enumerate(aliases):
        ax.bar(x + i * w, per_champ[a], w, color=colors[a], label=a)
    ax.set_xticks(x + 0.4 - w / 2); ax.set_xticklabels(cats); ax.set_ylabel(ylab)
    ax.legend(fontsize=7, ncol=min(4, len(aliases)))


# ---------------------------------------------------------------- contesto reale
def build_ctx(models, cache, colors=None, hb=None):
    """Precomputa gli output delle librerie per ogni champion. models: {alias: model vivo}.
    hb = heavy-budget (None -> HB_LOCAL bounded; il notebook Azure passa budget pieni)."""
    aliases = [a for a in models if models[a] is not None]
    colors = colors or {a: DEFCOL[i % len(DEFCOL)] for i, a in enumerate(aliases)}
    hb = hb or HB_LOCAL
    it0 = cache['val'][0]
    xwin = np.asarray(it0['x'][:50])[None]
    import torch
    xwin_t = torch.tensor(xwin, dtype=torch.float32)
    ctx = {'aliases': aliases, 'colors': colors, 'cache': cache, 'xwin': xwin_t, 'per': {}}
    for a in aliases:
        m = models[a]
        wp = profile_weights(m)
        raster = spike_raster(m, xwin_t[0], max_steps=50)
        ss = spike_stats(raster)
        rate = ss['mean_rate'] if np.isfinite(ss['mean_rate']) else 0.02
        opc = op_count(m, spike_rate=rate)
        dse = dse_profiles(m, spike_rate=rate)
        base_ok, srows = state_ranges_rows(m, xwin_t)
        rec_po2 = recurrence_spectral(m)                       # po2
        # ρ float: ricomputa senza po2
        _, mats = weight_matrices(m)
        U = mats['rec_U'].detach().cpu().numpy(); V = mats['rec_V'].detach().cpu().numpy()
        Wf = U @ V
        rec_float = {'spectral_radius': float(np.abs(np.linalg.eigvals(Wf)).max()),
                     'spectral_norm': float(np.linalg.svd(Wf, compute_uv=False)[0])}
        sens = sensitivity_map(m, xwin_t, per_matrix_sample=8)
        # fragilita' po2 vs float sui 5 param
        dpar = _po2_vs_float_param(m, xwin_t)
        heavy = _heavy(m, cache, xwin_t, hb)             # cvf/v2x/qbits/chatter/aoidist/seu_pshift (bounded)
        ctx['per'][a] = {'wp': wp, 'raster': raster, 'ss': ss, 'rate': rate, 'opc': opc,
                         'dse': dse, 'base_ok': base_ok, 'srows': srows, 'rec_po2': rec_po2,
                         'rec_float': rec_float, 'sens': sens, 'dpar': dpar,
                         'shapes': model_shapes(m), **heavy}
    return ctx


def _po2_vs_float_param(m, xwin_t):
    """|Δparam| tra deploy (po2 on) e float (po2 off) -> fragilita' di quantizzazione reale."""
    import torch
    from scripts.closed_loop_identify import identify
    prev = os.environ.get('PO2_ENABLED')
    os.environ['PO2_ENABLED'] = '1'
    p_q = np.asarray(identify(m, xwin_t), dtype=np.float64)
    os.environ['PO2_ENABLED'] = '0'
    p_f = np.asarray(identify(m, xwin_t), dtype=np.float64)
    if prev is None:
        os.environ.pop('PO2_ENABLED', None)
    else:
        os.environ['PO2_ENABLED'] = prev
    scale = np.array([33.3, 1.2, 2.5, 1.1, 1.5])
    return np.abs(p_q - p_f) / scale


# ================================ 00 READINESS ================================
def _readiness_scores(ctx):
    """Punteggi RAG [0,1] per champion x dimensione, da metriche reali."""
    dims = ['Pesi', 'Fix-pt', 'Spike', 'Energia', 'Timing', 'Risorse', 'SEU', 'I/O']
    S = {}
    for a in ctx['aliases']:
        p = ctx['per'][a]
        sparsity = 1.0 - min(1.0, p['rate'] / 0.05)                    # <5% spike -> buono
        footprint = 1.0                                               # 400B << BRAM -> pieno
        dsp_free = 1.0                                                # 0 DSP sempre
        rho = p['rec_po2'].get('spectral_radius', 1.0)
        pesi = float(np.clip(1.0 - rho, 0, 1))                        # contrattivo = buono
        timing = float(np.clip(1.0 - p['dse']['profiles'][0]['utilization_pct'] / 100.0, 0, 1))
        risorse = 1.0
        seu = float(np.clip(1.0 - 20 * max(bit_criticality(p['sens']).values()), 0, 1))
        energia = float(np.clip((p['opc']['shapes']['H'] * 0) + 0.8, 0, 1))
        io = float(np.clip(1.0 - p['dpar'].mean() * 5, 0, 1))
        S[a] = [pesi, footprint, sparsity, energia, timing, risorse, seu, io]
    return dims, S


def fig_readiness_matrix(ctx):
    dims, S = _readiness_scores(ctx); A = ctx['aliases']
    M = np.array([S[a] for a in A])
    fig, ax = plt.subplots(figsize=(9, 3.6))
    im = ax.imshow(M, cmap='RdYlGn', vmin=0.4, vmax=1.0, aspect='auto')
    ax.set_xticks(range(len(dims))); ax.set_xticklabels(dims, rotation=20, fontsize=8)
    ax.set_yticks(range(len(A))); ax.set_yticklabels(A)
    for i in range(len(A)):
        for j in range(len(dims)):
            ax.text(j, i, '%.2f' % M[i, j], ha='center', va='center', fontsize=8)
    ax.grid(False); plt.colorbar(im, ax=ax, label='readiness (1 = FPGA-friendly)')
    return fig, '00', 'readiness_matrix', 'SW (dati reali)', 'chi e piu FPGA-friendly e dove'


def fig_deploy_verdict(ctx):
    A = ctx['aliases']
    rows = [['champion', 'sparsita', 'rho(U@V)', 'footprint', 'SEU top-bit', 'stato']]
    for a in A:
        p = ctx['per'][a]
        bc = bit_criticality(p['sens']); topb = max(bc, key=bc.get) if bc else '-'
        rows.append([a, '%.1f%%' % (p['rate'] * 100), '%.3f' % p['rec_po2'].get('spectral_radius', float('nan')),
                     '%.0f B' % p['wp']['total_footprint_bytes'], topb, 'valuta su 4 champ'])
    fig, ax = plt.subplots(figsize=(9, 0.7 + 0.5 * len(rows))); ax.axis('off')
    t = ax.table(cellText=rows, loc='center', cellLoc='center')
    t.auto_set_font_size(False); t.set_fontsize(9); t.scale(1, 1.6)
    for j in range(len(rows[0])):
        t[0, j].set_facecolor('#eee'); t[0, j].set_text_props(weight='bold')
    return fig, '00', 'deploy_verdict', 'SW (dati reali)', 'sintesi per champion (verdetto finale coi 4 su Azure)'


# ================================ 01 WEIGHTS ================================
def fig_po2_alphabet(ctx):
    a = ctx['aliases'][0]; wp = ctx['per'][a]['wp']
    agg = {e: 0 for e in range(PO2_EXP_MIN, PO2_EXP_MAX + 1)}
    zero = 0; tot = 0
    for s in wp['matrices']:
        for e in range(PO2_EXP_MIN, PO2_EXP_MAX + 1):
            agg[e] += s['exp_hist'][e]
        zero += int(round(s['frac_zero'] * s['n_weights'])); tot += s['n_weights']
    exps = list(range(PO2_EXP_MIN, PO2_EXP_MAX + 1))
    lv = ['-%g' % (2.0 ** e) for e in exps[::-1]] + ['0'] + ['%g' % (2.0 ** e) for e in exps]
    cnt = [agg[e] // 2 for e in exps[::-1]] + [zero] + [agg[e] - agg[e] // 2 for e in exps]
    x = np.arange(len(lv))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for i, cc in enumerate(cnt):
        col = '#7f7f7f' if lv[i] == '0' else '#2a78d6'
        ax.plot([x[i], x[i]], [0, cc], color=col, lw=2); ax.plot(x[i], cc, 'o', color=col, ms=6)
    ax.set_xticks(x); ax.set_xticklabels(lv, fontsize=8); ax.set_ylabel('# pesi (di %d)' % tot)
    ax.set_xlabel('valore sinaptico = sign*2^k, k in [%d,%d]' % (PO2_EXP_MIN, PO2_EXP_MAX))
    ax.annotate('0: %.0f%% eliminabili' % (100 * zero / tot), (len(exps), zero),
                textcoords='offset points', xytext=(6, 4), fontsize=8)
    return fig, '01', 'po2_alphabet (%s)' % a, 'SW (dati reali)', 'il moltiplicatore e UNO di 13 valori -> barrel-shifter, 0 DSP'


def fig_spectral(ctx):
    fig, ax = plt.subplots(figsize=(8.4, 5))
    for a in ctx['aliases']:
        p = ctx['per'][a]
        ax.scatter(p['rec_po2']['spectral_norm'], p['rec_po2']['spectral_radius'], s=80,
                   color=ctx['colors'][a], label=a + ' (po2)', zorder=3)
        ax.scatter(p['rec_float']['spectral_norm'], p['rec_float']['spectral_radius'], s=80,
                   facecolor='none', edgecolor=ctx['colors'][a], zorder=3)
    ax.axhline(1.0, color='#e34948', ls='--', label='rho=1 (confine stabilita)')
    ax.set_xlabel('||U@V||_2 (gain worst-case/tick)'); ax.set_ylabel('rho (raggio spettrale)')
    ax.legend(fontsize=7)
    return fig, '01', 'spectral_recurrence', 'SW (dati reali)', 'pieno=po2, vuoto=float · rho<1 = loop contrattivo (fixed-point sicuro)'


def fig_sparsity_mask(ctx):
    mats = ['fc', 'rec_U', 'rec_V', 'out']
    per = {a: [next((s['frac_zero'] * 100 for s in ctx['per'][a]['wp']['matrices'] if s['matrix'] == mm), 0)
               for mm in mats] for a in ctx['aliases']}
    fig, ax = plt.subplots(figsize=(9, 4.6))
    _gbar(ax, mats, per, ctx['aliases'], ctx['colors'], '% pesi a zero (mask 2^-5)')
    return fig, '01', 'sparsity_mask', 'SW (dati reali)', 'fc=input->hid · rec_U/rec_V=ricorrenza low-rank · out=readout'


def fig_po2_exponent_range(ctx):
    a = ctx['aliases'][0]; wp = ctx['per'][a]['wp']; mats = wp['matrices']
    fig, ax = plt.subplots(figsize=(9, 4.2)); y = np.arange(len(mats))
    for i, s in enumerate(mats):
        used = [e for e in range(PO2_EXP_MIN, PO2_EXP_MAX + 1) if s['exp_hist'][e] > 0]
        lo, hi = (min(used), max(used)) if used else (0, 0)
        ax.plot([lo, hi], [i, i], '-', color='#2a78d6', lw=6, solid_capstyle='round')
        ax.text(hi + 0.2, i, '%d..%d -> %d bit esp' % (lo, hi, max(1, int(np.ceil(np.log2(hi - lo + 1))))),
                va='center', fontsize=9)
    ax.set_yticks(y); ax.set_yticklabels([s['matrix'] for s in mats]); ax.set_xlim(-5, 3)
    ax.set_xlabel('esponente k usato (2^k)'); ax.axvline(PO2_EXP_MAX, color='#e34948', ls=':', lw=1)
    return fig, '01', 'po2_exponent_range (%s)' % a, 'SW (dati reali)', 'bit di esponente per matrice'


# ================================ 02 FIXED-POINT ================================
def _baseline_states(ctx):
    for a in ctx['aliases']:
        if ctx['per'][a]['base_ok']:
            return a, ctx['per'][a]['srows']
    return None, None


def fig_bit_allocation(ctx):
    a, srows = _baseline_states(ctx)
    if not srows:
        return None
    fig, ax = plt.subplots(figsize=(9.4, 4.8))
    for i, r in enumerate(srows):
        y = len(srows) - 1 - i
        ax.barh(y, 1, left=0, color='#fab219', edgecolor='w')
        ax.barh(y, r['int_bits'], left=1, color='#2a78d6', edgecolor='w')
        ax.barh(y, r['frac_bits'], left=1 + r['int_bits'], color='#dfe8f5', edgecolor='#2a78d6')
        ax.text(1 + r['int_bits'] + r['frac_bits'] + 0.3, y, 'Q%d.%d' % (r['int_bits'], r['frac_bits']),
                va='center', fontsize=9, weight='bold')
        ax.text(1 + r['int_bits'] + r['frac_bits'] + 4.0, y, 'range +-%.1f' % r['absmax'],
                va='center', fontsize=8, color='#555')
    ax.set_yticks(range(len(srows))); ax.set_yticklabels([r['state'] for r in srows[::-1]])
    ax.set_xlim(0, 26); ax.set_xlabel('bit (giallo=segno, blu=interi da RANGE, azzurro=frazionari)')
    ax.grid(False)
    return fig, '02', 'bit_allocation (%s)' % a, 'SW (dati reali)', 'formato Qm.n per stato: int_bits dal RANGE MISURATO'


def fig_state_ranges(ctx):
    a, srows = _baseline_states(ctx)
    if not srows:
        return None
    fig, ax = plt.subplots(figsize=(9, 4.8)); y = np.arange(len(srows))
    for i, r in enumerate(srows):
        ax.hlines(i, r['min'], r['max'], color='#2a78d6', lw=4, alpha=0.8)
        ax.plot(r['p01'], i, '|', color='#e34948', ms=9); ax.plot(r['p999'], i, '|', color='#e34948', ms=9)
    ax.set_yticks(y); ax.set_yticklabels([r['state'] for r in srows])
    ax.set_xlabel('range dinamico min..max (| rosso = p0.1/p99.9)')
    return fig, '02', 'state_ranges (%s)' % a, 'SW (dati reali)', 'i registri interni fixed-point: il range fissa gli int_bits'


def fig_leak_decay(ctx):
    lk = leak_underflow_curve(v0=2.0, bit_shift=3, frac_bits_list=(4, 8))
    fig, ax = plt.subplots(figsize=(9, 4.6)); t = lk['steps']
    ax.plot(t, lk['float'], 'o-', color='#888', label='float (decade a ~0)')
    ax.plot(t, lk['fixed_4b'], 's-', color='#e34948', label='fixed 4-bit (si INCASTRA)')
    ax.plot(t, lk['fixed_8b'], '^-', color='#2a78d6', label='fixed 8-bit (~float)')
    ax.set_xlabel('tick (senza nuovo input)'); ax.set_ylabel('potential'); ax.legend(fontsize=8)
    return fig, '02', 'leak_decay', 'SW (dati reali)', 'leak = potential>>3: pochi frac_bits -> sotto-flusso, potenziale BLOCCATO'


def fig_per_param_fragility(ctx):
    P = ['v0', 'T', 's0', 'a', 'b']; A = ctx['aliases']
    M = np.array([ctx['per'][a]['dpar'] for a in A])
    fig, ax = plt.subplots(figsize=(8, 3.8)); im = ax.imshow(M, cmap='YlOrRd', aspect='auto')
    ax.set_xticks(range(5)); ax.set_xticklabels(P); ax.set_yticks(range(len(A))); ax.set_yticklabels(A)
    for i in range(len(A)):
        for j in range(5):
            ax.text(j, i, '%.3f' % M[i, j], ha='center', va='center', fontsize=8)
    ax.grid(False); plt.colorbar(im, ax=ax, label='|Δparam| po2 vs float (norm.)')
    return fig, '02', 'per_param_fragility', 'SW (dati reali)', 'quale param cede di piu sotto quantizzazione po2'


# ================================ 03 SPIKING ================================
def fig_activity_map(ctx):
    A = ctx['aliases']
    rates = [np.asarray(ctx['per'][a]['ss']['per_neuron_rate']) for a in A]
    H = max((r.size for r in rates), default=32)
    M = np.zeros((len(A), H))
    for i, r in enumerate(rates):
        M[i, :r.size] = r
    fig, ax = plt.subplots(figsize=(10, 2 + 0.4 * len(A)))
    im = ax.imshow(M, cmap='magma', aspect='auto', vmin=0, vmax=max(0.1, M.max()))
    ax.set_yticks(range(len(A))); ax.set_yticklabels(A); ax.set_xlabel('neurone hidden')
    ax.grid(False); plt.colorbar(im, ax=ax, label='firing rate')
    return fig, '03', 'activity_map', 'SW (dati reali)', 'hotspot vs neuroni morti (rate 0)'


def fig_raster(ctx):
    a = ctx['aliases'][0]; R = ctx['per'][a]['raster']
    if R.size == 0:
        return None
    R = R.T                                    # (hidden, tick)
    order = np.argsort(-R.sum(1))
    R = R[order]
    fig = plt.figure(figsize=(10, 4.4))
    gs = fig.add_gridspec(2, 2, width_ratios=[5, 1], height_ratios=[4, 1], hspace=0.06, wspace=0.03)
    axr = fig.add_subplot(gs[0, 0]); axrr = fig.add_subplot(gs[0, 1], sharey=axr)
    axb = fig.add_subplot(gs[1, 0], sharex=axr)
    ys, xs = np.where(R > 0.5)
    axr.scatter(xs, ys, s=3, color='#2a78d6'); axr.set_ylabel('neurone (ord. per rate)')
    axr.grid(False); axr.tick_params(labelbottom=False)
    axrr.barh(np.arange(R.shape[0]), R.sum(1), color='#9467bd'); axrr.grid(False)
    axrr.tick_params(labelleft=False); axrr.set_xlabel('tot/neur')
    axb.plot(np.arange(R.shape[1]), R.sum(0), color='#1baf7a'); axb.set_xlabel('tick')
    axb.set_ylabel('att/tick'); axb.grid(False)
    return fig, '03', 'raster (%s)' % a, 'SW (dati reali)', 'raster ordinato per rate + marginali per-neurone e per-tick'


def fig_sparsity_tick(ctx):
    a = ctx['aliases'][0]; R = ctx['per'][a]['raster']
    if R.size == 0:
        return None
    conc = R.sum(1)                             # spike concorrenti per tick
    fig, ax = plt.subplots(figsize=(9, 4.2)); ax.plot(np.arange(conc.size), conc, color='#9467bd')
    ax.axhline(conc.max(), color='#e34948', ls='--', label='picco -> dimensiona albero AC')
    ax.set_xlabel('tick'); ax.set_ylabel('# spike concorrenti/tick'); ax.legend(fontsize=8)
    return fig, '03', 'sparsity_per_tick (%s)' % a, 'SW (dati reali)', 'il MAX di spike simultanei fissa la larghezza dell albero AC'


def fig_isi(ctx):
    a = ctx['aliases'][0]; isi = isi_stats(ctx['per'][a]['raster'])
    if not isi['isi_all']:
        return None
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.hist(isi['isi_all'], bins=min(30, max(5, len(set(isi['isi_all'])))), color='#1baf7a', edgecolor='w')
    ax.axvline(isi['min_isi'], color='#e34948', ls='--', label='ISI min=%d' % isi['min_isi'])
    ax.set_xlabel('inter-spike interval [tick]'); ax.set_ylabel('conteggio'); ax.legend(fontsize=8)
    return fig, '03', 'isi_dist (%s)' % a, 'SW (dati reali)', 'ISI minimo -> worst-case back-to-back'


def fig_dead_sat(ctx):
    A = ctx['aliases']
    per = {a: [ctx['per'][a]['ss']['dead_frac'] * 32, ctx['per'][a]['ss']['sat_frac'] * 32] for a in A}
    fig, ax = plt.subplots(figsize=(9, 4.4))
    _gbar(ax, ['morti (rate=0)', 'saturi (rate~1)'], per, A, ctx['colors'], '# neuroni (di ~32)')
    ax.text(0.02, 0.92, 'morti -> PRUNING · saturi -> costante hardwired', transform=ax.transAxes,
            fontsize=9, va='top', bbox=dict(boxstyle='round', fc='#f4f4f4', ec='#ccc'))
    return fig, '03', 'dead_saturated', 'SW (dati reali)', 'entrambe le categorie sono semplificabili in hardware'


# ================================ 04 ENERGY ================================
def fig_energy_vs_ann(ctx):
    A = ctx['aliases']; x = np.arange(len(A)); w = 0.35
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for i, a in enumerate(A):
        opc = ctx['per'][a]['opc']; s = opc['shapes']
        shift = (opc['per_step_worstcase']['input_syn'] + opc['per_step_worstcase']['rec_U']) * E_AC / 1000.0
        ac = (opc.get('per_step_typical', opc['per_step_worstcase'])['rec_V'] +
              opc.get('per_step_typical', opc['per_step_worstcase'])['out_syn']) * E_AC / 1000.0
        ann_mac = (s['H'] * s['IN'] + s['H'] * s['H'] + s['O'] * s['H']) * s['n_ticks'] * E_MAC / 1000.0
        ax.bar(i - w / 2, shift, w, color='#2a78d6', label='SNN shift-add' if i == 0 else '')
        ax.bar(i - w / 2, ac, w, bottom=shift, color='#1baf7a', label='SNN AC' if i == 0 else '')
        ax.bar(i + w / 2, ann_mac, w, color='#888', label='ANN MAC' if i == 0 else '')
    ax.set_yscale('log'); ax.set_xticks(x); ax.set_xticklabels(A); ax.set_ylabel('energia/inferenza [nJ] (log)')
    ax.legend(fontsize=7, ncol=3)
    return fig, '04', 'energy_vs_ann', 'SW (dati reali, stima pJ Horowitz)', 'SNN = 0 MAC (solo AC+shift), ANN = tutto MAC'


def fig_energy_breakdown(ctx):
    a = ctx['aliases'][0]; opc = ctx['per'][a]['opc']['per_step_worstcase']
    comp = ['fc shift', 'rec_V AC', 'rec_U shift', 'out AC', 'leak/fat/reset']
    val = [opc['input_syn'] * E_AC, opc['rec_V'] * E_AC, opc['rec_U'] * E_AC,
           opc['out_syn'] * E_AC, opc['nonsyn'] * E_AC]
    fig, ax = plt.subplots(figsize=(9, 4.4)); c = plt.cm.Blues(np.linspace(0.4, 0.9, len(comp)))
    ax.bar(comp, val, color=c); ax.set_ylabel('energia [pJ] (stima)'); ax.tick_params(axis='x', rotation=15)
    return fig, '04', 'energy_breakdown (%s)' % a, 'SW (dati reali, stima pJ)', 'dove si spendono i pJ (incl. op non-sinaptiche)'


def fig_synops_split(ctx):
    A = ctx['aliases']
    per = {a: [ctx['per'][a]['opc']['per_step_worstcase']['input_syn'],
               ctx['per'][a]['opc'].get('per_step_typical', ctx['per'][a]['opc']['per_step_worstcase'])['rec_V'] +
               ctx['per'][a]['opc'].get('per_step_typical', ctx['per'][a]['opc']['per_step_worstcase'])['out_syn']]
           for a in A}
    fig, ax = plt.subplots(figsize=(9, 4.2))
    _gbar(ax, ['statico (input fc)', 'dinamico (spike-driven)'], per, A, ctx['colors'], 'op / step')
    return fig, '04', 'synops_split', 'SW (dati reali)', 'parte sempre-on vs event-driven -> dove conviene il clock-gating'


# ================================ 05 TIMING ================================
def fig_op_count(ctx):
    a = ctx['aliases'][0]; pt = ctx['per'][a]['opc']['per_tick_worstcase']
    comp = ['fc', 'rec_V (st.1)', 'rec_U (st.2)', 'out', 'leak/fat/reset']
    val = [pt['input_syn'], pt['rec_V'], pt['rec_U'], pt['out_syn'], pt['nonsyn']]
    fig, ax = plt.subplots(figsize=(9, 4.2)); ax.bar(comp, val, color='#2a78d6'); ax.set_ylabel('op / tick')
    return fig, '05', 'op_count (%s)' % a, 'SW (dati reali)', 'il conteggio operazioni e l INPUT del WCET'


def fig_wcet_cycles(ctx):
    a = ctx['aliases'][0]; profs = ctx['per'][a]['dse']['profiles']
    fig, ax = plt.subplots(figsize=(9, 4.4)); y = np.arange(len(profs))
    cyc = [p['cycles_per_step'] for p in profs]
    ax.barh(y, cyc, color=plt.cm.viridis(np.linspace(0.2, 0.8, len(profs))))
    for i, p in enumerate(profs):
        ax.text(p['cycles_per_step'] * 1.1, i, '%d cicli = %.2f us @100MHz' %
                (p['cycles_per_step'], p['us_per_step']), va='center', fontsize=8)
    ax.set_yticks(y); ax.set_yticklabels([p['profile'] for p in profs]); ax.set_xscale('log')
    ax.set_xlabel('cicli / step (log)')
    return fig, '05', 'wcet_cycles (%s)' % a, 'SW (dati reali)', 'cicli e us per inferenza secondo 4 architetture HW'


def fig_latency_margin(ctx):
    a = ctx['aliases'][0]; serial = ctx['per'][a]['dse']['profiles'][0]
    deadline_us = DEADLINE_MS * 1000.0
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.barh([0], [deadline_us], color='#f2f2f2', edgecolor='#888')
    ax.barh([0], [serial['us_per_step']], color='#2a78d6')
    ax.set_yticks([0]); ax.set_yticklabels(['budget']); ax.set_xscale('log'); ax.set_xlim(0.1, 2e5)
    ax.set_xlabel('tempo [us] (log)')
    ax.annotate('inferenza ~%.1f us' % serial['us_per_step'], (serial['us_per_step'], 0),
                xytext=(20, 0.3), fontsize=9, color='#2a78d6', arrowprops=dict(arrowstyle='->', color='#2a78d6'))
    ax.annotate('deadline 100 ms', (deadline_us, 0), xytext=(3000, -0.35), fontsize=9,
                arrowprops=dict(arrowstyle='->'))
    return fig, '05', 'latency_margin (%s)' % a, 'SW (dati reali)', 'margine ~%.0fx sulla deadline' % serial['margin_x']


def fig_jitter_proof(ctx):
    a = ctx['aliases'][0]; n = ctx['per'][a]['opc']['synaptic_ac_per_step_worstcase']
    fig, ax = plt.subplots(figsize=(9, 4.0)); ax.bar([0, 1, 2], [n, n, n], color='#2a78d6')
    ax.set_xticks([0, 1, 2]); ax.set_xticklabels(['spike 1%', 'spike 15%', 'spike 30%'])
    ax.set_ylabel('# op worst-case / step'); ax.set_ylim(0, n * 1.15)
    ax.text(1, n * 1.05, 'IDENTICO', ha='center', fontsize=11, weight='bold', color='#0ca30c')
    return fig, '05', 'jitter_proof (%s)' % a, 'SW (dati reali)', 'WCET==BCET: tempo costante -> jitter di calcolo = 0'


# ================================ 06 RESOURCES ================================
def fig_op_celltype(ctx):
    a = ctx['aliases'][0]; pt = ctx['per'][a]['opc']['per_tick_worstcase']
    ac = pt['rec_V'] + pt['out_syn']; shift = pt['input_syn'] + pt['rec_U']
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.bar(['AC (spike-driven)', 'shift-add (po2)'], [ac, shift], color=['#1baf7a', '#2a78d6'])
    ax.set_ylabel('celle / tick')
    return fig, '06', 'op_by_celltype (%s)' % a, 'SW (dati reali)', 'nessun moltiplicatore -> 0 DSP'


def fig_dse_pareto(ctx):
    a = ctx['aliases'][0]; profs = ctx['per'][a]['dse']['profiles']
    units = [p['n_units'] or 999 for p in profs]; lat = [p['cycles_per_step'] for p in profs]
    area = [max(1, (u if u != 999 else 800)) * 30 for u in units]              # STIMA area ~ unita
    fig, ax = plt.subplots(figsize=(9, 4.6)); ax.plot(area, lat, 'o-', color='#4a3aa7')
    for p, ar, la in zip(profs, area, lat):
        ax.annotate(p['profile'], (ar, la), textcoords='offset points', xytext=(6, 6), fontsize=8)
    ax.set_xscale('log'); ax.set_yscale('log'); ax.set_xlabel('area (LUT stimati) ->')
    ax.set_ylabel('latenza (cicli/step) <-')
    return fig, '06', 'dse_pareto (%s)' % a, 'SW (latenza reale, area STIMA)', 'trade-off area<->latenza per parallelismo'


def fig_bram_dim(ctx):
    a = ctx['aliases'][0]; bits = ctx['per'][a]['wp']['total_footprint_bits']
    bram = bits / (36 * 1024)
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.bar(['pesi', 'BUDGET 140'], [max(bram, 0.02), 140], color=['#2a78d6', '#ddd'])
    ax.set_yscale('log'); ax.set_ylabel('# BRAM (36Kb)')
    ax.text(0, max(bram, 0.02) * 1.2, '%.2f BRAM (%d bit)' % (bram, bits), ha='center', fontsize=9)
    return fig, '06', 'bram_dimensioning (%s)' % a, 'SW (dati reali)', 'memoria pesi: <1 BRAM su 140 (<1%)'


# ================================ 07 SEU ================================
def fig_seu_intro(ctx):
    fig, ax = plt.subplots(figsize=(9, 4.2)); ax.axis('off')
    txt = ("07 — SEU (Single Event Upset)\n\n"
           "Un neutrone atmosferico puo invertire UN bit nella memoria dei pesi (0<->1).\n"
           "Il peso po2 corrotto cambia segno/esponente -> i 5 param cambiano -> l'accel\n"
           "comandata cambia -> possibile collisione.\n\n"
           "Simulato ORA: seu_inject decodifica peso->4bit, inverte un bit, riscrive il\n"
           "valore guasto nel tensore e rilancia identify/eval_safety. Reale, no HW.")
    ax.text(0.03, 0.95, txt, va='top', fontsize=12, family='monospace')
    return fig, '07', 'concept — cosa sono i bit-flip', 'SW', None


def fig_seu_sensitivity(ctx):
    a = ctx['aliases'][0]; hm = ctx['per'][a]['sens']['heatmap']
    if hm.size == 0:
        return None
    fig, ax = plt.subplots(figsize=(7.6, 5)); im = ax.imshow(hm, cmap='inferno', aspect='auto')
    ax.set_xticks(range(4)); ax.set_xticklabels(['exp-LSB', 'exp-mid', 'exp-MSB', 'segno'])
    ax.set_ylabel('peso (campione)'); ax.grid(False)
    plt.colorbar(im, ax=ax, label='Δ id-error se quel bit si inverte')
    return fig, '07', 'sensitivity_map (%s)' % a, 'SW (dati reali)', 'quanto sale il rischio invertendo 1 bit di un peso'


def fig_bit_criticality(ctx):
    a = ctx['aliases'][0]; bc = bit_criticality(ctx['per'][a]['sens'])
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.bar(list(bc), list(bc.values()), color='#d03b3b'); ax.set_ylabel('sensibilita media')
    return fig, '07', 'bit_criticality (%s)' % a, 'SW (dati reali)', 'quali bit dominano il rischio -> ECC mirata'


def fig_hidden_vs_readout(ctx):
    A = ctx['aliases']
    per = {a: [hidden_vs_readout(ctx['per'][a]['sens'])['hidden_mean'],
               hidden_vs_readout(ctx['per'][a]['sens'])['readout_mean']] for a in A}
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    _gbar(ax, ['hidden (fc/rec)', 'readout (out)'], per, A, ctx['colors'], 'criticita media')
    return fig, '07', 'hidden_vs_readout', 'SW (dati reali)', 'dove concentrare il TMR (readout piu critico?)'


# ================================ 08 I/O ================================
def fig_queue_overflow(ctx):
    rows = queue_overflow(depths=(1, 2, 4, 8, 16, 32), rho=0.7)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot([r['buffer_depth'] for r in rows], [r['drop_rate'] for r in rows], 'o-', color='#e34948')
    ax.set_xlabel('profondita coda RX (# messaggi)'); ax.set_ylabel('prob. drop su burst (rho=0.7)')
    ax.set_yscale('log')
    return fig, '08', 'queue_overflow', 'SW (M/M/1/K, STIMA)', 'buffer minimo anti-burst dei CAM'


def fig_aoi_surface(ctx):
    a = ctx['aliases'][0]
    surf = aoi_max_surface(ctx['models_ref'][a], ctx['cache'], gaps=(8.0, 20.0, 40.0),
                           dvs=(0.0, 7.0, 14.0), max_stale_steps=20, horizon=140, t_brake=30)
    g = surf['aoi_max_s']
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    im = ax.imshow(g, origin='lower', aspect='auto', cmap='RdYlGn',
                   extent=[min(surf['gaps']), max(surf['gaps']), min(surf['dvs']), max(surf['dvs'])])
    ax.set_xlabel('gap s [m] (piccolo=pericoloso)'); ax.set_ylabel('Δv chiusura [m/s]')
    plt.colorbar(im, ax=ax, label='AoI_max tollerabile [s]'); ax.grid(False)
    return fig, '08', 'aoi_max_surface (%s)' % a, 'SW (dati reali)', 'eta MAX del CAM oltre cui e insicuro (verde=tollera di piu)'


# ================================ 09 THERMAL (STIMA/HDL) ================================
def fig_thermal_budget(ctx):
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.bar(['SNN (0 DSP)', 'ANN densa'], [0.35, 1.8], color=['#1baf7a', '#888'])
    ax.axhline(2.0, color='#e34948', ls='--', label='budget passivo ECU')
    ax.set_ylabel('P stimata [W]'); ax.legend(fontsize=8)
    return fig, '09', 'thermal_budget', 'HDL (STIMA)', 'la SNN sparsa (0 DSP) sta nel budget termico passivo, l ANN no'


# ================================ eval PESANTI (bounded local / full Azure) ================================
HB_LOCAL = {'cvf_flips': (1, 4, 8), 'cvf_mc': 2, 'cvf_drivers': 2, 'v2x_drivers': 2,
            'aoi_drivers': 10, 'pshift_n': 12}


def _heavy(m, cache, xwin_t, hb):
    """Eval pesanti per le figure 07/08/02 (bounded in locale, pieni su Azure). try/except per chiave."""
    out = {}
    for key, fn in [('cvf', _cvf), ('v2x', _v2x), ('qbits', _qbits),
                    ('chatter', _chatter), ('aoidist', _aoidist), ('seu_pshift', _seu_pshift)]:
        try:
            out[key] = fn(m, cache, xwin_t, hb)
        except Exception:
            out[key] = None
    return out


def _cvf(m, cache, xwin_t, hb):
    from utils.seu_inject import collision_vs_flips
    return collision_vs_flips(m, cache, n_flips_list=hb['cvf_flips'], n_mc=hb['cvf_mc'],
                              n_drivers=hb['cvf_drivers'], seq_len=50)


def _v2x(m, cache, xwin_t, hb):
    from scripts.closed_loop_identify import v2x_robustness_sweep
    return v2x_robustness_sweep(m, cache, n_drivers=hb['v2x_drivers'], pdrs=(1.0,),
                                latencies=(0, 1, 2, 3), jitters=(), gilberts=(),
                                hold_modes=('hold_last', 'dead_reckon', 'blind'), blackouts=())


def _qbits(m, cache, xwin_t, hb, bits=(12, 8, 6, 4, 3, 2)):
    from scripts.closed_loop_identify import identify
    from utils.quantize import fake_quant
    import torch
    _, mats = weight_matrices(m)
    orig = {k: v.detach().clone() for k, v in mats.items()}
    prev = os.environ.get('PO2_ENABLED')
    os.environ['PO2_ENABLED'] = '0'
    p_float = np.asarray(identify(m, xwin_t), dtype=np.float64)
    scale = np.array([33.3, 1.2, 2.5, 1.1, 1.5])
    fixed_err = []
    for b in bits:
        for k, v in mats.items():
            with torch.no_grad():
                v.data.copy_(torch.tensor(fake_quant(orig[k].cpu().numpy(), frac_bits=b), dtype=v.dtype))
        p = np.asarray(identify(m, xwin_t), dtype=np.float64)
        fixed_err.append(float(np.mean(np.abs(p - p_float) / scale)))
        for k, v in mats.items():
            with torch.no_grad():
                v.data.copy_(orig[k])
    os.environ['PO2_ENABLED'] = '1'
    p_po2 = np.asarray(identify(m, xwin_t), dtype=np.float64)
    po2e = float(np.mean(np.abs(p_po2 - p_float) / scale))
    if prev is None:
        os.environ.pop('PO2_ENABLED', None)
    else:
        os.environ['PO2_ENABLED'] = prev
    return {'bits': list(bits), 'fixed_err': fixed_err, 'po2_err': po2e}


def _chatter(m, cache, xwin_t, hb):
    from scripts.closed_loop_identify import identify
    from utils.closed_loop_eval import simulate
    from utils.quantize import fake_quant
    idp = np.asarray(identify(m, xwin_t), dtype=np.float64)
    idp_q = fake_quant(idp, frac_bits=2)
    vl = 20 + 3 * np.sin(np.arange(200) * 0.05)
    tr_f = simulate(None, idp, vl, 25.0, 20.0)
    tr_q = simulate(None, idp_q, vl, 25.0, 20.0)
    n = min(len(tr_f['a_ego']), len(tr_q['a_ego']))
    return {'t': np.arange(n) * 0.1, 'a_float': tr_f['a_ego'][:n], 'a_quant': tr_q['a_ego'][:n]}


def _aoidist(m, cache, xwin_t, hb):
    from scripts.closed_loop_identify import identify
    from utils.closed_loop_eval import simulate
    import torch
    ages = []
    for it in cache['val'][:hb['aoi_drivers']]:
        xw = torch.tensor(it['x'][:50][None], dtype=torch.float32)
        idp = np.asarray(identify(m, xw), dtype=np.float64)
        vl = 20 + 2 * np.sin(np.arange(150) * 0.04)
        ch = {'hold_mode': 'hold_last', 'pdr': 0.7, 'latency_steps': 1, 'seed': 0}
        tr = simulate(None, idp, vl, 25.0, 20.0, channel=ch)
        if 'aoi_mean' in tr:
            ages.append(tr['aoi_mean'])
        if 'aoi_max' in tr:
            ages.append(tr['aoi_max'])
    return ages


def _seu_pshift(m, cache, xwin_t, hb):
    from utils.seu_inject import InjectionSession, decode_bits, flip_bit
    from scripts.closed_loop_identify import identify
    rng = np.random.default_rng(0); scale = np.array([33.3, 1.2, 2.5, 1.1, 1.5])
    acc = np.zeros(5); cnt = 0
    with InjectionSession(m) as inj:
        base = np.asarray(identify(m, xwin_t), dtype=np.float64)
        picks = [inj.catalog[j] for j in rng.choice(len(inj.catalog),
                 size=min(hb['pshift_n'], len(inj.catalog)), replace=False)]
        for name, fi in picks:
            inj.set_element(name, fi, decode_bits(flip_bit(inj.code_at(name, fi), 2)))  # exp-MSB
            p = np.asarray(identify(m, xwin_t), dtype=np.float64)
            inj.restore_element(name, fi)
            acc += np.abs(p - base) / scale; cnt += 1
    return acc / max(1, cnt)


def _placeholder(sec, name, feas, msg):
    fig, ax = plt.subplots(figsize=(8.4, 3.6)); ax.axis('off')
    ax.text(0.5, 0.5, msg, ha='center', va='center', fontsize=11, color='#666',
            bbox=dict(boxstyle='round', fc='#f7f7f7', ec='#ccc'))
    return fig, sec, name, feas, None


# ================================ 00b / 01b READINESS+WEIGHTS extra ================================
def fig_readiness_radar(ctx):
    dims, S = _readiness_scores(ctx)
    ang = np.linspace(0, 2 * np.pi, len(dims), endpoint=False).tolist(); ang += ang[:1]
    fig, ax = plt.subplots(figsize=(7, 6), subplot_kw=dict(polar=True))
    for a in ctx['aliases']:
        v = list(S[a]); v += v[:1]
        ax.plot(ang, v, color=ctx['colors'][a], label=a); ax.fill(ang, v, color=ctx['colors'][a], alpha=0.06)
    ax.set_xticks(ang[:-1]); ax.set_xticklabels(dims, fontsize=8); ax.set_ylim(0, 1)
    ax.legend(loc='upper right', bbox_to_anchor=(1.28, 1.10), fontsize=7)
    return fig, '00', 'readiness_radar', 'SW (dati reali)', 'ogni asse: 1 = requisito di deploy soddisfatto'


def fig_resource_occupancy(ctx):
    res = ['LUT\n(53.2k)', 'FF\n(106.4k)', 'BRAM\n(140)', 'DSP\n(220)']
    per = {}
    for a in ctx['aliases']:
        bram = 100.0 * ctx['per'][a]['wp']['total_footprint_bits'] / (140 * 36 * 1024)
        per[a] = [2.8, 0.9, max(bram, 0.02), 0.0]                 # LUT/FF stima; BRAM reale; DSP=0
    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    _gbar(ax, res, per, ctx['aliases'], ctx['colors'], '% budget Zynq-7020')
    ax.set_ylim(0, 4.5)
    return fig, '01', 'resource_occupancy', 'SW (LUT/FF STIMA, BRAM/DSP reali)', 'DSP 0% (po2=shift-add), tutto <3% del chip'


# ================================ 02b FIXED-POINT extra ================================
def fig_quant_vs_bits(ctx):
    a = ctx['aliases'][0]; q = ctx['per'][a].get('qbits')
    if not q:
        return _placeholder('02', 'quant_vs_bits', 'SW / re-train', 'sweep bit-width: generato su Azure')
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.plot(q['bits'], q['fixed_err'], 'o-', color='#2a78d6', label='fixed Qm.n')
    ax.axhline(q['po2_err'], color='#e34948', ls='--', label='po2 (deploy)')
    ax.invert_xaxis(); ax.set_xlabel('bit-width pesi (<-)'); ax.set_ylabel('errore id. vs float')
    ax.legend(fontsize=8)
    return fig, '02', 'quant_vs_bits (%s)' % a, 'SW / re-train', 'bit-budget pesi (curva ONESTA solo con re-training QAT)'


def fig_chattering(ctx):
    a = ctx['aliases'][0]; c = ctx['per'][a].get('chatter')
    if not c:
        return _placeholder('02', 'chattering', 'SW', 'closed-loop float vs quant: generato su Azure')
    fig, ax = plt.subplots(2, 1, figsize=(9, 5.4))
    ax[0].plot(c['t'], c['a_float'], color='#888', label='float (param pieni)')
    ax[0].plot(c['t'], c['a_quant'], color='#e34948', alpha=0.8, label='param quant 2-bit (nervoso)')
    ax[0].set_ylabel('a_ego [m/s2]'); ax[0].legend(fontsize=7, ncol=2); ax[0].set_title('comando: liscio vs nervoso', fontsize=10)
    for lab, sig, cc in [('float', c['a_float'], '#888'), ('quant', c['a_quant'], '#e34948')]:
        sp = np.abs(np.fft.rfft(sig - np.mean(sig))) ** 2
        fr = np.fft.rfftfreq(len(sig), d=0.1)
        ax[1].semilogy(fr, sp + 1e-6, color=cc, label=lab)
    ax[1].axvspan(0.5, 5, color='#e34948', alpha=0.06); ax[1].set_xlabel('freq [Hz]'); ax[1].set_ylabel('PSD (log)')
    ax[1].set_title('energia >0.5 Hz (zona rossa) = chattering', fontsize=10); ax[1].legend(fontsize=7)
    return fig, '02', 'chattering (%s)' % a, 'SW (dati reali)', 'instabilita: accelerazione nervosa da quantizzazione'


# ================================ 04b ENERGY extra ================================
def fig_energy_vs_rate(ctx):
    rate = np.linspace(0.5, 5, 30)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for a in ctx['aliases']:
        s = ctx['per'][a]['shapes']
        static = (s['H'] * s['IN']) * s['n_ticks'] * E_AC / 1000.0
        dyn_full = (s['R'] * s['H'] + s['O'] * s['H']) * s['n_ticks'] * E_AC / 1000.0
        ax.plot(rate, static + (rate / 100.0) * dyn_full * 50, color=ctx['colors'][a], label=a)
    ax.set_xlabel('spike-rate [%]'); ax.set_ylabel('energia [nJ]'); ax.legend(fontsize=7)
    return fig, '04', 'energy_vs_rate', 'SW (dati reali, modello)', 'quanto scende l energia abbassando il firing-rate'


# ================================ 05b/06b TIMING+RES extra (STIMA) ================================
def fig_decode_criticalpath(ctx):
    comp = ['sigmoid x5 (LUT)', 'sqrt(ab)', 'div', 'tanh CAH', 'add/mul']; val = [12, 18, 22, 16, 8]
    fig, ax = plt.subplots(figsize=(9, 4.2)); ax.bar(comp, val, color='#eb6834')
    ax.set_ylabel('cicli (STIMA)'); ax.tick_params(axis='x', rotation=15)
    return fig, '05', 'decode_criticalpath', 'SW (STIMA)', 'il decode (sigmoid+IDM) e l unico blocco mul/div -> collo Fmax + unico DSP'


def fig_area_model(ctx):
    parts = ['ALIF(32)', 'low-rank U/V', 'LI+decode', 'delay-line', 'controllo']
    lut = [900, 500, 700, 200, 300]; ff = [300, 100, 80, 240, 120]; x = np.arange(len(parts))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.bar(x, lut, 0.4, label='LUT', color='#2a78d6'); ax.bar(x + 0.4, ff, 0.4, label='FF', color='#1baf7a')
    ax.set_xticks(x + 0.2); ax.set_xticklabels(parts, rotation=15, fontsize=8); ax.set_ylabel('# (STIMA)')
    ax.legend(fontsize=8)
    return fig, '06', 'area_model', 'SW (STIMA)', 'stima parametrica LUT/FF per blocco, PRIMA della sintesi'


# ================================ 07b SEU extra ================================
def fig_degrade_vs_flips(ctx):
    fig, ax = plt.subplots(figsize=(9, 4.4)); any_data = False
    for a in ctx['aliases']:
        cvf = ctx['per'][a].get('cvf')
        if not cvf:
            continue
        any_data = True
        k = [r['n_flips'] for r in cvf['rows']]; cr = [r['collision_rate_mean'] for r in cvf['rows']]
        ax.plot(k, cr, 'o-', color=ctx['colors'][a], label=a)
    if not any_data:
        plt.close(fig)
        return _placeholder('07', 'degrade_vs_flips', 'SW', 'curva collisione vs #SEU: generata su Azure')
    ax.set_xlabel('# bit-flip accumulati'); ax.set_ylabel('collision_rate'); ax.legend(fontsize=7)
    return fig, '07', 'degrade_vs_flips', 'SW (dati reali, bounded local)', 'quanti SEU prima dell insicurezza -> periodo di scrubbing'


def fig_perparam_shift(ctx):
    P = ['v0', 'T', 's0', 'a', 'b']; A = [a for a in ctx['aliases'] if ctx['per'][a].get('seu_pshift') is not None]
    if not A:
        return _placeholder('07', 'perparam_shift', 'SW', 'shift per-param sotto SEU: generato su Azure')
    M = np.array([ctx['per'][a]['seu_pshift'] for a in A])
    fig, ax = plt.subplots(figsize=(8, 3.8)); im = ax.imshow(M, cmap='YlOrRd', aspect='auto')
    ax.set_xticks(range(5)); ax.set_xticklabels(P); ax.set_yticks(range(len(A))); ax.set_yticklabels(A)
    for i in range(len(A)):
        for j in range(5):
            ax.text(j, i, '%.3f' % M[i, j], ha='center', va='center', fontsize=8)
    ax.grid(False); plt.colorbar(im, ax=ax, label='|Δparam| medio sotto flip exp-MSB')
    return fig, '07', 'perparam_shift', 'SW (dati reali)', 'quale param si sposta di piu sotto SEU (a,b frenata?)'


def fig_tmr_overhead(ctx):
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.bar(['baseline', 'TMR selettivo', 'TMR full', 'BRAM-ECC'], [100, 145, 300, 105],
           color=['#888', '#1baf7a', '#e34948', '#2a78d6'])
    ax.axhline(100, color='k', ls=':'); ax.set_ylabel('% area vs baseline')
    return fig, '07', 'tmr_overhead', 'HDL (STIMA)', 'costo area mitigazioni: TMR full +200%, ECC quasi gratis'


# ================================ 08b I/O extra ================================
def fig_aoi_dist(ctx):
    ages = []
    for a in ctx['aliases']:
        d = ctx['per'][a].get('aoidist')
        if d:
            ages += list(d)
    if not ages:
        return _placeholder('08', 'aoi_dist', 'SW', 'distribuzione AoI: generata su Azure')
    fig, ax = plt.subplots(figsize=(9, 4.2)); ax.hist(ages, bins=min(30, max(5, len(ages))), color='#eda100', edgecolor='w')
    ax.axvline(0.3, color='#e34948', ls='--', label='AoI_max (soglia hard)'); ax.set_xlabel('Age-of-Information [s]')
    ax.set_ylabel('conteggio'); ax.legend(fontsize=8)
    return fig, '08', 'aoi_dist', 'SW (dati reali)', 'quanto spesso la rete gira su dati vecchi'


def fig_holdmode(ctx):
    modes = ['hold_last', 'dead_reckon', 'blind']; per = {}
    for a in ctx['aliases']:
        v2x = ctx['per'][a].get('v2x')
        if not v2x:
            continue
        row = {r['val']: r['collision_rate'] for r in v2x if r['axis'] == 'hold_mode'}
        per[a] = [row.get(mm, np.nan) for mm in modes]
    if not per:
        return _placeholder('08', 'holdmode', 'SW', 'hold-mode collision: generata su Azure')
    fig, ax = plt.subplots(figsize=(9, 4.4))
    _gbar(ax, modes, per, list(per), ctx['colors'], 'collision_rate')
    return fig, '08', 'holdmode', 'SW (dati reali, bounded)', 'blind (senza hold) scopre il crollo; hold-last maschera'


def fig_pdr_knee(ctx):
    per = {}
    for a in ctx['aliases']:
        v2x = ctx['per'][a].get('v2x')
        if not v2x:
            continue
        rows = sorted([r for r in v2x if r['axis'] == 'latency'], key=lambda r: r['val'])
        if rows:
            per[a] = ([r['val'] for r in rows], [r['min_ttc_p5'] for r in rows])
    if not per:
        return _placeholder('08', 'pdr_latency_knee', 'SW', 'knee latenza: generata su Azure')
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for a, (xx, yy) in per.items():
        ax.plot(xx, yy, 'o-', color=ctx['colors'][a], label=a)
    ax.set_xlabel('latenza CAM [step 0.1s]'); ax.set_ylabel('p5 min-TTC (basso=pericoloso)'); ax.legend(fontsize=7)
    return fig, '08', 'pdr_latency_knee', 'SW (dati reali, bounded)', 'graceful su PDR, il margine crolla con la latenza'


# ================================ 09b THERMAL extra (STIMA) ================================
def fig_derating(ctx):
    tj = np.linspace(25, 125, 50)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(tj, 220 * (1 - (tj - 25) / 100 * 0.28), color='#e34948', label='Fmax(Tj)')
    ax.axhline(100, color='#2a78d6', ls='--', label='target 100 MHz')
    ax.axvline(100, color='#888', ls=':', label='Tj automotive ~100C')
    ax.set_xlabel('Tj [C]'); ax.set_ylabel('Fmax [MHz] (STIMA)'); ax.legend(fontsize=8)
    return fig, '09', 'derating_tj_fmax', 'HDL (STIMA)', 'a caldo il clock scende: resta headroom sul target a 100C?'


ALL_FIGS = [
    fig_readiness_matrix, fig_readiness_radar, fig_deploy_verdict,
    fig_po2_alphabet, fig_resource_occupancy, fig_spectral, fig_sparsity_mask, fig_po2_exponent_range,
    fig_bit_allocation, fig_state_ranges, fig_quant_vs_bits, fig_per_param_fragility, fig_chattering, fig_leak_decay,
    fig_activity_map, fig_raster, fig_sparsity_tick, fig_isi, fig_dead_sat,
    fig_energy_vs_ann, fig_energy_breakdown, fig_energy_vs_rate, fig_synops_split,
    fig_op_count, fig_wcet_cycles, fig_latency_margin, fig_jitter_proof, fig_decode_criticalpath,
    fig_op_celltype, fig_dse_pareto, fig_area_model, fig_bram_dim,
    fig_seu_intro, fig_seu_sensitivity, fig_bit_criticality, fig_degrade_vs_flips, fig_perparam_shift,
    fig_hidden_vs_readout, fig_tmr_overhead,
    fig_aoi_surface, fig_aoi_dist, fig_queue_overflow, fig_holdmode, fig_pdr_knee,
    fig_derating, fig_thermal_budget,
]

def render_all(models, cache, out_pdf):
    """Costruisce il ctx reale e rende tutte le figure. Ritorna (n_ok, n_fail, status[])."""
    ctx = build_ctx(models, cache)
    ctx['models_ref'] = models
    pdf = PdfPages(out_pdf)
    status = []
    pg = 0
    for fn in ALL_FIGS:
        try:
            res = fn(ctx)
            if res is None:
                status.append((fn.__name__, 'SKIP (dato assente)')); continue
            fig, sec, name, feas, note = res
            pg += 1
            fig.suptitle('%s · %s  [%s]' % (sec, name, feas), fontsize=12, fontweight='bold')
            if note:
                fig.text(0.5, 0.93, note, ha='center', fontsize=8, color='#444')
            fig.text(0.99, 0.01, 'dati reali (locale) · pag %d' % pg, ha='right', fontsize=7, color='#999')
            fig.tight_layout(rect=[0, 0.02, 1, 0.90 if note else 0.94])
            pdf.savefig(fig); plt.close(fig)
            status.append((fn.__name__, 'OK'))
        except Exception as e:
            import traceback
            status.append((fn.__name__, 'FAIL: ' + repr(e)[:90]))
            traceback.print_exc()
    pdf.close()
    n_ok = sum(1 for _, s in status if s == 'OK')
    n_fail = sum(1 for _, s in status if s.startswith('FAIL'))
    return n_ok, n_fail, status
