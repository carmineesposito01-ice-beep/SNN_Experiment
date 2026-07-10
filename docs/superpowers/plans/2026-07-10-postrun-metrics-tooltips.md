# Post-run exhaustive metrics + '?' tooltips — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** Enrich the Post-run report card with the single-episode subset of the trio-report metrics
(identification, extended safety/comfort SSM, network-health incl. ρ, energy breakdown) + a '?' hover
tooltip (definition + formula) on every metric. Reuse the project's validated functions; energy stays
on the single existing path (no double-`n_ticks`).

**Architecture:** extend `EpisodeSummary` to keep episode arrays/spikes and, at `summary()`, reuse
`closed_loop_eval.safety_metrics`/`comfort_metrics` + compute identification (vs GT), dead/spike stats,
energy breakdown (same `metrics.synops` path), and ρ via a LAPACK-free power iteration; `PostRunPage`
grows groups + per-metric `?` tooltips.

**Tech Stack:** PySide6/pyqtgraph/numpy/torch, env `cf_sim`. ⚠️ NO numpy LAPACK (ρ = power iteration).
Commits without `Co-Authored-By`. Full sim suite after changes.

---

## Task Q1: `spectral_radius_po2` (LAPACK-free ρ)

**Files:** Modify `sim/ui/episode.py`; Test `tests/test_sim_episode.py`.

- [ ] **Step 1: failing test** — append to `tests/test_sim_episode.py`:
```python
def test_spectral_radius_matches_reports():
    import os
    from utils.champion_io import load_champion
    from sim.ui.episode import spectral_radius_po2
    REPO2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    raff = spectral_radius_po2(load_champion(os.path.join(REPO2, "champions", "R33_C2_A1_T12_fix", "best_model.pt")).model)
    don = spectral_radius_po2(load_champion(os.path.join(REPO2, "champions", "PE_t05_gp0002", "best_model.pt")).model)
    assert abs(raff - 2.99) < 0.35      # VALIDATION §9.3 / FPGA §0: Raffaello ρ≈2.99 (expansive)
    assert 0.0 <= don < 0.5             # Donatello ρ≈0.05 (contractive)
```

- [ ] **Step 2: run → fail** (`ImportError spectral_radius_po2`).

- [ ] **Step 3: implement** — add to `sim/ui/episode.py` (imports at top: `import torch`,
`from core.hardware import po2_quantize`, `from utils.net_diagnostics import _last_hidden`):
```python
def spectral_radius_po2(model, iters=200):
    """ρ(U·V) of the po2 low-rank recurrence via power iteration. LAPACK-free: np.linalg.eigvals/svd
    (as in net_diagnostics.recurrence_spectral) abort with OMP #15 in cf_sim. None if not low-rank."""
    hid = _last_hidden(model)
    if hid is None or not (hasattr(hid, "rec_U") and hasattr(hid, "rec_V")):
        return None
    with torch.no_grad():
        W = (po2_quantize(hid.rec_U).detach().float() @ po2_quantize(hid.rec_V).detach().float())
        v = torch.ones(W.shape[0], dtype=torch.float32); v = v / v.norm()
        lam = 0.0
        for _ in range(int(iters)):
            w = W @ v
            lam = float(w.norm())
            if lam < 1e-30:
                return 0.0                       # strongly contractive
            v = w / lam
        return lam
```

- [ ] **Step 4: run → pass** `conda run -n cf_sim python -m pytest tests/test_sim_episode.py::test_spectral_radius_matches_reports -q`.
- [ ] **Step 5: commit** `feat(sim/ui): spectral_radius_po2 — LAPACK-free ρ(U·V) via power iteration`

---

## Task Q2: `EpisodeSummary` v2 (reuse validated SSM + identification + dead + energy breakdown)

**Files:** Modify `sim/ui/episode.py`; Test `tests/test_sim_episode.py`.

- [ ] **Step 1: failing test** — append to `tests/test_sim_episode.py`:
```python
def test_episode_summary_v2_rich():
    acc = EpisodeSummary(DIMS, params_gt=np.array([30., 1.5, 2., 1.5, 1.5]))
    sp = np.zeros(32); sp[:6] = 1.0
    dead_sp = np.zeros(32)                                  # neuron 31 never fires
    for t in range(10):
        acc.update(_step(t, s=30.0 - t, v=20.0, dv=1.0 + t, a=-0.5 * t), sp if t % 2 else dead_sp)
    s = acc.summary()
    # reused safety/comfort keys present + sane
    for k in ("min_ttc", "brake_margin_min", "max_DRAC", "TET", "TIT", "impact_dv",
              "rms_accel", "max_decel", "rms_jerk", "frac_decel_iso_viol"):
        assert k in s
    # identification vs GT
    assert "param_rmse_v0" in s and s["param_rmse_v0"] == 0.0   # pred==GT here
    # network health
    assert s["dead_pct"] > 0.0 and "max_spikes_tick" in s
    # energy consistency: breakdown sums to the total, advantage>1
    assert abs((s["e_fc"] + s["e_recV"] + s["e_recU"] + s["e_out"]) - s["snn_pj"]) < 1e-6
    assert s["advantage"] > 1.0


def test_episode_energy_matches_direct_synops():
    from sim.ui.metrics import synops, ann_mac, E_AC_PJ, E_MAC_PJ
    acc = EpisodeSummary(DIMS)
    spk = [np.array([1.0 if (i + t) % 4 == 0 else 0.0 for i in range(32)]) for t in range(8)]
    for t in range(8):
        acc.update(_step(t, 30.0, 20.0, 0.0, 0.0), spk[t])
    direct = sum(sum(synops(s, 4, 32, 5, 8)) for s in spk) * E_AC_PJ     # same path as the SynOps dock
    assert abs(acc.summary()["snn_pj"] - direct) < 1e-6                   # ONE energy path, no re-derivation
```

- [ ] **Step 2: run → fail** (`TypeError` params_gt / missing keys).

- [ ] **Step 3: implement** — in `sim/ui/episode.py`, extend `EpisodeSummary`. Add imports
`from utils.closed_loop_eval import safety_metrics, comfort_metrics`. Replace the class with:
```python
_PARAM_NAMES = ("v0", "T", "s0", "a", "b")


class EpisodeSummary:
    def __init__(self, dims, params_gt=None, model=None):
        self._dims = tuple(int(x) for x in dims)          # (n_in, n_hid, n_out, rank)
        self._gt = None if params_gt is None else np.asarray(params_gt, dtype=float)
        self._rho = spectral_radius_po2(model) if model is not None else None
        self.reset()

    def reset(self):
        self._n = 0
        self._collided = False
        self._impact_dv = 0.0
        self._s = []; self._v = []; self._vl = []; self._dv = []; self._a = []; self._params = []
        self._sum_fire = 0.0; self._peak_fire = 0.0; self._max_spk = 0
        self._fired = None                                 # (H,) ever-fired mask
        self._e_fc = 0.0; self._e_recV = 0.0; self._e_recU = 0.0; self._e_out = 0.0
        self._rows = []

    def update(self, r, spikes):
        n_in, n_hid, n_out, rank = self._dims
        sp = np.asarray(spikes, dtype=float)
        a = float(r.a_ego); gap = float(r.s)
        self._n += 1
        if bool(r.collided) and not self._collided:        # first collision -> impact Δv (as closed_loop_eval)
            self._impact_dv = max(0.0, float(r.v) - float(r.vl))
        self._collided = self._collided or bool(r.collided)
        self._s.append(gap); self._v.append(float(r.v)); self._vl.append(float(r.vl))
        self._dv.append(float(r.dv)); self._a.append(a); self._params.append(np.asarray(r.params, float)[:5])
        fire = float(sp.mean()); self._sum_fire += fire; self._peak_fire = max(self._peak_fire, fire)
        nsp = int(np.count_nonzero(sp > 0)); self._max_spk = max(self._max_spk, nsp)
        self._fired = (sp > 0) if self._fired is None else (self._fired | (sp > 0))
        # energy breakdown (SAME metrics.synops decomposition; one path, no n_ticks re-normalisation)
        self._e_fc += n_in * n_hid
        self._e_recV += nsp * rank
        self._e_recU += (n_hid * rank) if nsp > 0 else 0
        self._e_out += nsp * n_out
        tval = float(ttc(gap, r.dv))
        self._rows.append((r.t, round(gap, 3), round(float(r.v), 3), round(float(r.vl), 3),
                           round(float(r.dv), 3), round(a, 3),
                           round(tval, 3) if np.isfinite(tval) else "",
                           *(round(float(x), 4) for x in np.asarray(r.params, float)[:5]),
                           round(fire * 100, 2)))

    def summary(self):
        n = self._n
        if n == 0:
            return {"n_ticks": 0}
        a = np.asarray(self._a); v = np.asarray(self._v)
        traj = {"s": np.asarray(self._s), "dv": np.asarray(self._dv), "v": v, "a_ego": a,
                "collided": self._collided, "min_gap": float(np.min(self._s)), "impact_dv": self._impact_dv}
        out = {"n_ticks": n, "duration_s": round(n * DT, 2), "collided": self._collided}
        sm = safety_metrics(traj); cm = comfort_metrics(traj)                # REUSED validated formulas
        for k in ("min_gap", "min_ttc", "brake_margin_min", "max_DRAC", "TET", "TIT", "impact_dv",
                  "TED_drac", "TID_drac"):
            out[k] = round(sm[k], 3) if np.isfinite(sm[k]) else sm[k]
        for k in ("rms_accel", "max_decel", "rms_jerk", "frac_decel_iso_viol", "frac_accel_iso_viol"):
            out[k] = round(cm[k], 3)
        # identification vs ground truth
        params = np.asarray(self._params)                                   # (T, 5)
        rel = []
        for i, name in enumerate(_PARAM_NAMES):
            rmse = float(np.sqrt(np.mean((params[:, i] - (self._gt[i] if self._gt is not None else params[:, i].mean())) ** 2)))
            out[f"param_rmse_{name}"] = round(rmse, 4)
            if self._gt is not None and abs(self._gt[i]) > 1e-9:
                rel.append(rmse / abs(self._gt[i]))
        out["id_accuracy"] = round(100.0 * max(0.0, 1.0 - (np.mean(rel) if rel else 1.0)), 1) if self._gt is not None else None
        # network health + energy (one path)
        out["mean_firing_pct"] = round(self._sum_fire / n * 100, 2)
        out["peak_firing_pct"] = round(self._peak_fire * 100, 2)
        out["dead_pct"] = round(float(np.mean(~self._fired)) * 100, 1) if self._fired is not None else 0.0
        out["max_spikes_tick"] = int(self._max_spk)
        out["rho"] = round(self._rho, 3) if self._rho is not None else None
        # energy UNROUNDED here so the breakdown sums EXACTLY to snn_pj and snn_pj == the direct
        # metrics.synops path (both tests at 1e-6). PostRunPage rounds for display only.
        out["e_fc"] = self._e_fc * E_AC_PJ; out["e_recV"] = self._e_recV * E_AC_PJ
        out["e_recU"] = self._e_recU * E_AC_PJ; out["e_out"] = self._e_out * E_AC_PJ
        out["snn_pj"] = out["e_fc"] + out["e_recV"] + out["e_recU"] + out["e_out"]
        out["ann_pj"] = float(n * ann_mac(self._dims[0], self._dims[1], self._dims[2]) * E_MAC_PJ)
        out["advantage"] = round(out["ann_pj"] / out["snn_pj"], 2) if out["snn_pj"] > 0 else 0.0
        return out

    def rows(self):
        return list(self._rows)
```
(Keep `write_episode_csv` unchanged. Energy stays UNROUNDED in `summary()` for exact consistency; the
display rounds — in `PostRunPage.set_summary`, format float pJ/values with `f"{val:.1f}"` when large,
`round(val,3)` otherwise.)

- [ ] **Step 4: run → pass** `conda run -n cf_sim python -m pytest tests/test_sim_episode.py -q`.
- [ ] **Step 5: commit** `feat(sim/ui): EpisodeSummary v2 — reuse safety/comfort SSM + identification + dead + energy breakdown`

---

## Task Q3: `PostRunPage` v2 (groups + per-param + '?' tooltips)

**Files:** Modify `sim/ui/postrun_page.py`; Test `tests/test_sim_postrun.py`.

- [ ] **Step 1: failing test** — append to `tests/test_sim_postrun.py`:
```python
def test_postrun_page_v2_groups_and_tooltips(qapp):
    from sim.ui.postrun_page import PostRunPage, _METRIC_HELP
    p = PostRunPage()
    s = {"n_ticks": 5, "duration_s": 0.5, "collided": False, "min_gap": 12.5, "min_ttc": 4.0,
         "brake_margin_min": 8.1, "max_DRAC": 2.2, "TET": 0.0, "TIT": 0.0, "impact_dv": 0.0,
         "rms_accel": 0.5, "max_decel": 2.0, "rms_jerk": 1.2, "frac_decel_iso_viol": 0.0,
         "frac_accel_iso_viol": 0.0, "param_rmse_v0": 1.2, "param_rmse_T": 0.1, "param_rmse_s0": 0.1,
         "param_rmse_a": 0.2, "param_rmse_b": 0.3, "id_accuracy": 84.0, "mean_firing_pct": 15.0,
         "peak_firing_pct": 40.0, "dead_pct": 0.0, "max_spikes_tick": 12, "rho": 0.05,
         "snn_pj": 400.0, "ann_pj": 6000.0, "advantage": 15.0, "e_fc": 100.0, "e_recV": 150.0,
         "e_recU": 100.0, "e_out": 50.0}
    rows = [(t, 30.0 - t, 20.0, 20.0, 0.0, 0.0, "", 30, 1.5, 2, 1.5, 1.5, 15.0) for t in range(5)]
    p.set_summary(s, rows, "Donatello", "cut_in")
    assert "0.05" in p._values["rho"].text()
    assert "84" in p._values["id_accuracy"].text()
    assert p._help_labels["rho"].toolTip() and "ρ" in p._help_labels["rho"].toolTip()
    assert "min_ttc" in _METRIC_HELP and "advantage" in _METRIC_HELP     # every shown metric documented
```

- [ ] **Step 2: run → fail.**

- [ ] **Step 3: implement** — rewrite `sim/ui/postrun_page.py`. Groups list drives the grid; a `_METRIC_HELP`
dict holds the tooltip HTML (definition + formula) for every key; each value row gets a `?` `QLabel`
with `setToolTip(_METRIC_HELP[key])`. Example structure (fill ALL keys shown):
```python
_GROUPS = [
    ("Identificazione", [("accuratezza", "id_accuracy", " %"), ("err v0", "param_rmse_v0", ""),
                         ("err T", "param_rmse_T", ""), ("err s0", "param_rmse_s0", ""),
                         ("err a", "param_rmse_a", ""), ("err b", "param_rmse_b", "")]),
    ("Sicurezza", [("esito", "esito", ""), ("min gap", "min_gap", " m"), ("min TTC", "min_ttc", " s"),
                   ("brake margin", "brake_margin_min", " m"), ("max DRAC", "max_DRAC", " m/s²"),
                   ("TET", "TET", " s"), ("TIT", "TIT", " s·s"), ("impact Δv", "impact_dv", " m/s")]),
    ("Comfort", [("RMS accel", "rms_accel", " m/s²"), ("max decel", "max_decel", " m/s²"),
                 ("RMS jerk", "rms_jerk", " m/s³"), ("frac decel ISO", "frac_decel_iso_viol", ""),
                 ("frac accel ISO", "frac_accel_iso_viol", "")]),
    ("Salute rete / FPGA", [("firing medio", "mean_firing_pct", " %"), ("firing picco", "peak_firing_pct", " %"),
                            ("neuroni morti", "dead_pct", " %"), ("spike max/tick", "max_spikes_tick", ""),
                            ("ρ(U·V)", "rho", "")]),
    ("Efficienza", [("energia SNN", "snn_pj", " pJ"), ("energia ANN", "ann_pj", " pJ"),
                    ("vantaggio", "advantage", "×"), ("  fc", "e_fc", " pJ"), ("  rec_V", "e_recV", " pJ"),
                    ("  rec_U", "e_recU", " pJ"), ("  out", "e_out", " pJ")]),
]

_METRIC_HELP = {
    "id_accuracy": "<b>Accuratezza identificazione</b><br>Quanto la SNN indovina i 5 parametri ACC-IIDM veri.<br>"
                   "formula: 100·(1 − media_i(RMSE_i/|GT_i|)), RMSE_i = √⟨(pred_i−GT_i)²⟩",
    "param_rmse_v0": "<b>Errore v0</b> (velocità desiderata) — RMSE della predizione vs il valore vero.<br>"
                     "RMSE = √⟨(v0_pred(t) − v0_GT)²⟩",
    # ... (param_rmse_T/s0/a/b analoghi) ...
    "esito": "<b>Esito</b> — collisione se il gap tocca 0 in questo episodio.",
    "min_gap": "<b>Gap minimo</b> [m] — distanza minima ego↔leader nell'episodio.",
    "min_ttc": "<b>Time-To-Collision minimo</b> [s].<br>TTC = gap/Δv (se Δv>0, avvicinamento); min sull'episodio.",
    "brake_margin_min": "<b>Margine di frenata</b> [m, con segno] — distanza dal confine di evitabilità fisica.<br>"
                        "brake_margin = s − max(0,Δv)²/(2·B_MAX), B_MAX=9 m/s²; <0 = collisione inevitabile.",
    "max_DRAC": "<b>DRAC massimo</b> [m/s²] — decelerazione richiesta per evitare l'urto.<br>DRAC = Δv²/(2·gap) (soglia critica 3.35).",
    "TET": "<b>Time Exposed TTC</b> [s] — tempo con TTC sotto la soglia critica (1.5 s).",
    "TIT": "<b>Time Integrated TTC</b> [s·s] — integrale di (TTC*−TTC) sotto soglia (severità×durata).",
    "impact_dv": "<b>Δv d'impatto</b> [m/s] — velocità relativa al contatto in caso di collisione (0 se nessuna).",
    "rms_accel": "<b>RMS accelerazione</b> [m/s²] — √⟨a²⟩ sull'episodio (proxy ISO 2631).",
    "max_decel": "<b>Decelerazione massima</b> [m/s²] — la frenata più forte (= −min a).",
    "rms_jerk": "<b>RMS jerk</b> [m/s³] — √⟨(da/dt)²⟩; comfort (oltre 2 = scomodo).",
    "frac_decel_iso_viol": "<b>Frazione decel oltre ISO</b> — quota di tempo con a < −3.5 m/s² (ISO 15622).",
    "frac_accel_iso_viol": "<b>Frazione accel oltre ISO</b> — quota di tempo con a > +2.0 m/s² (ISO 15622).",
    "mean_firing_pct": "<b>Firing medio</b> [%] — quota media di neuroni hidden che sparano per passo.",
    "peak_firing_pct": "<b>Firing di picco</b> [%] — massimo per passo.",
    "dead_pct": "<b>Neuroni morti</b> [%] — hidden mai sparati in questo episodio (capacità inutilizzata).",
    "max_spikes_tick": "<b>Spike max per tick</b> — dimensiona l'albero di accumulo (AC) in hardware.",
    "rho": "<b>ρ(U·V)</b> — raggio spettrale della ricorrenza low-rank (po2).<br>"
           "ρ<1 = contrattivo (stato limitato, sicuro in fixed-point); ρ>1 = espansivo (rischio overflow). "
           "Calcolato con power-iteration (no LAPACK).",
    "snn_pj": "<b>Energia SNN</b> [pJ] — Σ_passo SynOps · E_AC (E_AC=0.9 pJ, accumulo).",
    "ann_pj": "<b>Energia ANN densa</b> [pJ] — n_passi · MAC_densi · E_MAC (E_MAC=4.6 pJ, ricorrenza piena H·H).",
    "advantage": "<b>Vantaggio energetico</b> ×.<br>= energia_ANN/energia_SNN. Viene da <b>AC&lt;MAC</b> (accumulo &lt; molt.-accum.), "
                 "NON dalla sparsità (la rete spara ~15%). Conteggio per passo reale (nessuna doppia norm. per n_ticks). Varia tipico↔worst-case.",
    "e_fc": "<b>Energia fc</b> — ingresso sempre-on (IN·H) · E_AC.",
    "e_recV": "<b>Energia rec_V</b> — ricorrenza spike-driven (Σ spike·rank) · E_AC.",
    "e_recU": "<b>Energia rec_U</b> — ricorrenza (H·rank se c'è spike) · E_AC.",
    "e_out": "<b>Energia out</b> — uscita spike-driven (Σ spike·OUT) · E_AC.",
}
```
`set_summary` maps `esito` = "COLLISIONE"/"ok" (coloured), `rho` shows the value + verdict, `min_ttc`=∞→"∞";
builds `self._values[key]` + `self._help_labels[key]` (a `?` QLabel with the tooltip); feeds the v(t)/gap(t)
plots from rows. (Fill in the remaining `param_rmse_*` help entries by the shown pattern.)

- [ ] **Step 4: run → pass.**
- [ ] **Step 5: commit** `feat(sim/ui): PostRunPage v2 — full metric groups + '?' definition/formula tooltips`

---

## Task Q4: App wiring (GT + model into the accumulator) + summary CSV export

**Files:** Modify `sim/ui/app.py`; Test `tests/test_sim_ui_smoke.py`.

- [ ] **Step 1: failing test** — append:
```python
def test_simapp_episode_has_gt_and_rho(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    s = win._episode.summary()
    assert "id_accuracy" in s and s["rho"] is not None      # GT + model wired into the accumulator
```

- [ ] **Step 2: run → fail** (`id_accuracy` None / KeyError).

- [ ] **Step 3: implement** — in `sim/ui/app.py`, build the accumulator with GT + model. Where it is created
(both in `__init__` after `apply_overview` and in `select_scenario`), change to:
```python
        self._episode = EpisodeSummary(self._synops._dims,
                                       params_gt=self._scenarios[self._current_idx].params_gt,
                                       model=self._champ.model)
```
(in `__init__` use `self._scenarios[self._current_idx]`; `_current_idx` is 0 at that point.) For the summary
CSV export, add alongside `_do_export_csv` a summary writer:
```python
    def _do_export_csv(self, path):
        try:
            write_episode_csv(self._episode.rows(), path)
            import csv as _csv
            with open(path.rsplit(".", 1)[0] + "_summary.csv", "w", newline="", encoding="utf-8") as f:
                w = _csv.writer(f); w.writerow(("metric", "value"))
                for k, val in self._episode.summary().items():
                    w.writerow((k, val))
            self._status.showMessage(f"CSV saved to {path}", 3000)
        except OSError as e:
            self._status.showMessage(f"CSV export failed: {e}", 5000)
```

- [ ] **Step 4: run → pass** `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py -q`.
- [ ] **Step 5: commit** `feat(sim/ui): wire GT + model into EpisodeSummary; export episode + summary CSV`

---

## Task Q5: Render-verify + golden + docs

- [ ] **Step 1: Full golden suite** (all sim `test_sim_*.py`). Expected: PASS, core bit-identical.
- [ ] **Step 2: Render-verify** — scratchpad script (`windows`): run a full cut_in episode for **Raffaello**
  (BPTT, ρ>1) and **Donatello** (EventProp, ρ<1); `set_mode(2)`; grab the report card; hover N/A headless so
  assert the tooltips programmatically (`_help_labels["rho"].toolTip()`), and print `summary()` to confirm
  the ρ verdict, identification error, SSM, and that `advantage` equals the SynOps dock's for that champion.
  Read the PNGs. Fix any real discrepancy (esp. energy — investigate the cause, do not paper over).
- [ ] **Step 3: Docs** — update the resume trio + study §6 (post-run now exhaustive; A/B still the last piece).
- [ ] **Step 4: Memory** — `cf-fsnn-parallel-tracks.md` + `MEMORY.md`.
- [ ] **Step 5: Push.**

---

## Self-Review

- **Spec coverage:** ρ LAPACK-free (Q1) · reuse safety/comfort + identification + dead + energy breakdown (Q2) ·
  groups + tooltips (Q3) · GT/model wiring + summary CSV (Q4) · verify (Q5). ✓
- **Energy discipline:** ONE path (`metrics.synops`/`ann_mac`), breakdown sums to `snn_pj`,
  `test_episode_energy_matches_direct_synops` guards equality with the dock's path; tooltip states the AC<MAC
  / no-n_ticks caveat. ✓
- **No LAPACK:** ρ via power iteration; `safety_metrics`/`comfort_metrics` are arithmetic; no eigvals/svd. ✓
- **Types:** `EpisodeSummary(dims, params_gt, model)`, `.summary()` dict keys used identically in
  `PostRunPage._GROUPS`/`_METRIC_HELP` and the tests; `spectral_radius_po2(model)`. ✓
