# Post-run Mode + Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A third mode (Live / Meso-Macro / Post-run) showing an aggregate report card of the episode just run, fed by an incremental accumulator; plus File → Export… (episode CSV + window PNG).

**Architecture:** A pure `EpisodeSummary` accumulator (`sim/ui/episode.py`) folded once per tick from `SimApp._paint`; a `PostRunPage` (`sim/ui/postrun_page.py`) shown as `_mode_stack` page 2; an Export menu. Frozen core only read.

**Tech Stack:** PySide6 6.11, pyqtgraph 0.14, numpy. Env `cf_sim`. ⚠️ NO numpy LAPACK (arithmetic + mean/`**0.5` only here). Commits without `Co-Authored-By`. Full sim suite after changes (now 20 files incl. the two new test files).

---

## Task 1: `EpisodeSummary` accumulator + `write_episode_csv`

**Files:** Create `sim/ui/episode.py`; Test `tests/test_sim_episode.py`.

- [ ] **Step 1: failing test** — `tests/test_sim_episode.py`:
```python
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.state import StepResult                              # noqa: E402
from sim.ui.episode import EpisodeSummary, write_episode_csv  # noqa: E402
from config import DT                                         # noqa: E402

DIMS = (4, 32, 5, 8)   # (n_in, n_hid, n_out, rank) == SynOpsPanel dims


def _step(t, s, v, dv, a, collided=False):
    return StepResult(t=t, s=s, v=v, vl=v - dv, dv=dv, a_ego=a, params=np.array([30., 1.5, 2., 1.5, 1.5]),
                      collided=collided)


def test_episode_summary_aggregates():
    acc = EpisodeSummary(DIMS)
    spikes = np.zeros(32); spikes[:4] = 1.0                   # 4/32 firing = 12.5%
    acc.update(_step(0, s=30.0, v=20.0, dv=0.0, a=0.0), spikes)
    acc.update(_step(1, s=10.0, v=20.0, dv=5.0, a=-3.0, collided=True), spikes)
    s = acc.summary()
    assert s["n_ticks"] == 2 and abs(s["duration_s"] - 2 * DT) < 1e-9
    assert s["collided"] is True
    assert s["min_gap"] == 10.0
    assert abs(s["min_ttc"] - 2.0) < 1e-6                     # 10/5 at tick 1 (tick 0 not closing)
    assert s["max_decel"] == 3.0                             # -min(a) = 3
    assert abs(s["peak_firing_pct"] - 12.5) < 1e-6
    assert s["snn_pj"] > 0 and s["ann_pj"] > s["snn_pj"]      # AC energy < dense-MAC energy
    assert len(acc.rows()) == 2


def test_episode_summary_reset():
    acc = EpisodeSummary(DIMS)
    acc.update(_step(0, 30.0, 20.0, 0.0, 0.0), np.zeros(32))
    acc.reset()
    assert acc.summary()["n_ticks"] == 0 and acc.rows() == []


def test_write_episode_csv(tmp_path):
    acc = EpisodeSummary(DIMS)
    acc.update(_step(0, 30.0, 20.0, 0.0, 0.0), np.zeros(32))
    p = tmp_path / "ep.csv"
    write_episode_csv(acc.rows(), str(p))
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("t,gap,v,v_leader") and len(lines) == 2   # header + 1 row
```

- [ ] **Step 2: run → fail** (`ModuleNotFoundError sim.ui.episode`).

- [ ] **Step 3: implement** — `sim/ui/episode.py`:
```python
"""EpisodeSummary -- incremental per-episode aggregator (O(1)/tick, independent of the ring buffer,
no reconstruct). Reads StepResult + per-tick spikes; exposes safety/comfort/network/energy aggregates
and per-tick rows for CSV export. Pure: no Qt."""
import csv

import numpy as np

from config import DT
from sim.ui.metrics import E_AC_PJ, E_MAC_PJ, ann_mac, synops, ttc

CSV_HEADER = ("t", "gap", "v", "v_leader", "dv", "accel", "ttc",
              "v0", "T", "s0", "a", "b", "firing_pct")


class EpisodeSummary:
    def __init__(self, dims):
        self._dims = tuple(int(x) for x in dims)   # (n_in, n_hid, n_out, rank)
        self.reset()

    def reset(self):
        self._n = 0
        self._collided = False
        self._min_gap = float("inf")
        self._min_ttc = float("inf")
        self._max_decel = 0.0
        self._sum_a2 = 0.0
        self._sum_jerk2 = 0.0
        self._prev_a = None
        self._sum_fire = 0.0
        self._peak_fire = 0.0
        self._synops_total = 0.0
        self._rows = []

    def update(self, r, spikes):
        n_in, n_hid, n_out, rank = self._dims
        a = float(r.a_ego)
        gap = float(r.s)
        tval = float(ttc(gap, r.dv))
        fire = float(np.asarray(spikes).mean())
        self._n += 1
        self._collided = self._collided or bool(r.collided)
        self._min_gap = min(self._min_gap, gap)
        if np.isfinite(tval):
            self._min_ttc = min(self._min_ttc, tval)
        self._max_decel = max(self._max_decel, -a)
        self._sum_a2 += a * a
        if self._prev_a is not None:
            j = (a - self._prev_a) / DT
            self._sum_jerk2 += j * j
        self._prev_a = a
        self._sum_fire += fire
        self._peak_fire = max(self._peak_fire, fire)
        static, dynamic = synops(spikes, n_in, n_hid, n_out, rank)
        self._synops_total += static + dynamic
        p = np.asarray(r.params, dtype=float)
        self._rows.append((r.t, round(gap, 3), round(float(r.v), 3), round(float(r.vl), 3),
                           round(float(r.dv), 3), round(a, 3),
                           round(tval, 3) if np.isfinite(tval) else "",
                           *(round(float(x), 4) for x in p[:5]), round(fire * 100, 2)))

    def summary(self):
        n = self._n
        n_in, n_hid, n_out, rank = self._dims
        snn_pj = self._synops_total * E_AC_PJ
        ann_pj = n * ann_mac(n_in, n_hid, n_out) * E_MAC_PJ
        return {
            "n_ticks": n,
            "duration_s": round(n * DT, 2),
            "collided": self._collided,
            "min_gap": round(self._min_gap, 3) if n else 0.0,
            "min_ttc": (round(self._min_ttc, 3) if np.isfinite(self._min_ttc) else float("inf")),
            "max_decel": round(self._max_decel, 3),
            "rms_accel": round((self._sum_a2 / n) ** 0.5, 3) if n else 0.0,
            "rms_jerk": round((self._sum_jerk2 / (n - 1)) ** 0.5, 3) if n > 1 else 0.0,
            "mean_firing_pct": round(self._sum_fire / n * 100, 2) if n else 0.0,
            "peak_firing_pct": round(self._peak_fire * 100, 2),
            "snn_pj": round(snn_pj, 1),
            "ann_pj": round(ann_pj, 1),
            "advantage": round(ann_pj / snn_pj, 2) if snn_pj > 0 else 0.0,
        }

    def rows(self):
        return list(self._rows)


def write_episode_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        w.writerows(rows)
```

- [ ] **Step 4: run → pass** `conda run -n cf_sim python -m pytest tests/test_sim_episode.py -q`.
- [ ] **Step 5: commit** `feat(sim/ui): EpisodeSummary incremental accumulator + episode CSV writer`

---

## Task 2: Feed the accumulator from `SimApp`

**Files:** Modify `sim/ui/app.py`; Test `tests/test_sim_ui_smoke.py`.

- [ ] **Step 1: failing test** — append to `tests/test_sim_ui_smoke.py`:
```python
def test_simapp_feeds_episode_summary(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    assert win._episode.summary()["n_ticks"] == 0        # reset on scenario select
    win._advance(0.5)                                     # a few live ticks
    s = win._episode.summary()
    assert s["n_ticks"] >= 5 and s["min_gap"] < float("inf") and s["ann_pj"] > 0
```

- [ ] **Step 2: run → fail** (`AttributeError: _episode`).

- [ ] **Step 3: implement** — in `sim/ui/app.py`:

Add the import (with the other `sim.ui` imports near the top):
```python
from sim.ui.episode import EpisodeSummary, write_episode_csv
```
Create the accumulator once in `__init__`, right AFTER `apply_overview(...)` (the SynOps dims are set by then). Add:
```python
        self._episode = EpisodeSummary(self._synops._dims)
```
In `select_scenario`, recreate it (fresh, current dims — also refreshes dims after a champion swap since `select_champion` calls `select_scenario`). Add right after `self._recon_key = None`:
```python
        self._episode = EpisodeSummary(self._synops._dims)
```
In `_paint`, feed one tick per result using the aligned probe frames. Inside `if results:`, after the existing `for r in results:` loop (the one doing `update_frame`/`traj.record`), add:
```python
            new_frames = self._probe.frames()[-len(results):]     # probe recorded one frame per result
            for r, f in zip(results, new_frames):
                self._episode.update(r, f.spikes)
```

- [ ] **Step 4: run → pass** `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py::test_simapp_feeds_episode_summary -q`.
- [ ] **Step 5: commit** `feat(sim/ui): feed EpisodeSummary from the live loop (reset per scenario)`

---

## Task 3: `PostRunPage` report card

**Files:** Create `sim/ui/postrun_page.py`; Test `tests/test_sim_postrun.py`.

- [ ] **Step 1: failing test** — `tests/test_sim_postrun.py`:
```python
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6.QtWidgets import QApplication          # noqa: E402
from sim.ui.postrun_page import PostRunPage          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_postrun_page_populates(qapp):
    p = PostRunPage()
    s = {"n_ticks": 3, "duration_s": 0.3, "collided": False, "min_gap": 12.5, "min_ttc": 4.0,
         "max_decel": 2.1, "rms_accel": 0.5, "rms_jerk": 1.2, "mean_firing_pct": 9.4,
         "peak_firing_pct": 15.0, "snn_pj": 400.0, "ann_pj": 6000.0, "advantage": 15.0}
    rows = [(0, 30.0, 20.0, 20.0, 0.0, 0.0, "", 30, 1.5, 2, 1.5, 1.5, 9.4),
            (1, 28.0, 20.0, 21.0, -1.0, 0.5, "", 30, 1.5, 2, 1.5, 1.5, 9.4),
            (2, 26.0, 20.5, 21.0, -0.5, 0.3, "", 30, 1.5, 2, 1.5, 1.5, 9.4)]
    p.set_summary(s, rows, "Raffaello", "following")
    assert "Raffaello" in p._header.text() and "following" in p._header.text()
    assert "12.5" in p._values["min_gap"].text()
    assert "ok" in p._values["esito"].text().lower()
    assert len(p._v_curve.getData()[0]) == 3          # speed plot has the episode length
```

- [ ] **Step 2: run → fail** (`ModuleNotFoundError sim.ui.postrun_page`).

- [ ] **Step 3: implement** — `sim/ui/postrun_page.py`:
```python
"""PostRunPage -- aggregate 'report card' of the one episode just run (fed by EpisodeSummary).
Third mode of the simulator (Live / Meso-Macro / Post-run)."""
import pyqtgraph as pg
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

_GROUPS = [
    ("Esito", [("esito", "esito", ""), ("durata", "duration_s", " s")]),
    ("Sicurezza", [("min gap", "min_gap", " m"), ("min TTC", "min_ttc", " s"),
                   ("max decel", "max_decel", " m/s²")]),
    ("Comfort", [("RMS accel", "rms_accel", " m/s²"), ("RMS jerk", "rms_jerk", " m/s³")]),
    ("Efficienza", [("energia SNN", "snn_pj", " pJ"), ("energia ANN", "ann_pj", " pJ"),
                    ("vantaggio", "advantage", "×")]),
    ("Rete", [("firing medio", "mean_firing_pct", " %"), ("firing picco", "peak_firing_pct", " %")]),
]


class PostRunPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        self._header = QLabel("—"); self._header.setStyleSheet("font-weight: bold; font-size: 14px;")
        root.addWidget(self._header)
        grid = QGridLayout(); root.addLayout(grid)
        self._values = {}
        self._suffix = {}
        row = 0
        for group, fields in _GROUPS:
            g = QLabel(group); g.setStyleSheet("font-weight: bold; color: #8a6fb0;")
            grid.addWidget(g, row, 0, 1, 2); row += 1
            for label, key, suffix in fields:
                grid.addWidget(QLabel(label), row, 0)
                v = QLabel("—"); self._values[key] = v; self._suffix[key] = suffix
                grid.addWidget(v, row, 1); row += 1
        self._v_plot = pg.PlotWidget(title="velocità v(t)")
        self._v_plot.setLabel("bottom", "time", units="steps"); self._v_plot.setLabel("left", "v", units="m/s")
        self._gap_plot = pg.PlotWidget(title="gap(t)")
        self._gap_plot.setLabel("bottom", "time", units="steps"); self._gap_plot.setLabel("left", "gap", units="m")
        self._v_plot.setXLink(self._gap_plot)
        self._v_curve = self._v_plot.plot(pen=pg.mkPen("#2a7fb8", width=2))
        self._gap_curve = self._gap_plot.plot(pen=pg.mkPen("#2e8b57", width=2))
        root.addWidget(self._v_plot, stretch=1); root.addWidget(self._gap_plot, stretch=1)

    def set_summary(self, s, rows, champion, scenario):
        self._header.setText(f"{champion} · {scenario}")
        disp = dict(s)
        disp["esito"] = "COLLISIONE" if s.get("collided") else "ok"
        for key, lbl in self._values.items():
            val = disp.get(key)
            if key == "min_ttc" and val == float("inf"):
                text = "∞"
            else:
                text = f"{val}{self._suffix[key]}"
            lbl.setText(text)
        self._values["esito"].setStyleSheet(
            "color: #d1495b; font-weight: bold;" if s.get("collided") else "color: #2e8b57; font-weight: bold;")
        t = [r[0] for r in rows]; v = [r[2] for r in rows]; gap = [r[1] for r in rows]
        self._v_curve.setData(t, v); self._gap_curve.setData(t, gap)
```

- [ ] **Step 4: run → pass** `conda run -n cf_sim python -m pytest tests/test_sim_postrun.py -q`.
- [ ] **Step 5: commit** `feat(sim/ui): PostRunPage report card (safety/comfort/energy + summary plots)`

---

## Task 4: Wire the third mode

**Files:** Modify `sim/ui/app.py`; Test `tests/test_sim_ui_smoke.py`.

- [ ] **Step 1: failing test** — append to `tests/test_sim_ui_smoke.py`:
```python
def test_simapp_postrun_mode(qapp):
    win = SimApp(CHAMP)
    assert win._mode_stack.count() == 3                  # Live + Meso/Macro + Post-run
    win.select_scenario(0)
    win._advance(0.5)
    win.set_mode(2)                                       # Post-run
    assert win._mode_stack.currentIndex() == 2
    assert not win._run_btn.isChecked()                  # entering an analysis mode pauses live
    assert win._champ_name in win._postrun_page._header.text()
    assert win._postrun_page._values["min_gap"].text() not in ("—", "")   # report card populated
```

- [ ] **Step 2: run → fail** (`_mode_stack.count() == 2`, no `_postrun_page`).

- [ ] **Step 3: implement** — in `sim/ui/app.py`:

Import `PostRunPage`:
```python
from sim.ui.postrun_page import PostRunPage
```
Where the mode shell is built (currently `self._mode_sel = QComboBox(); self._mode_sel.addItems(["Live", "Meso/Macro"])` and the two `addWidget`s), create the page and add it as page 2:
```python
        self._postrun_page = PostRunPage()
```
right after `self._meso_page = MesoMacroPage(...)` block; then add it to the stack and the selector:
```python
        self._mode_stack.addWidget(self._postrun_page)         # page 2: Post-run
```
(right after `self._mode_stack.addWidget(self._meso_page)`), and change the selector items to:
```python
        self._mode_sel = QComboBox(); self._mode_sel.addItems(["Live", "Meso/Macro", "Post-run"])
```
Replace `set_mode` with the 3-mode version (pauses live on any analysis mode; stops road off the Meso page; suppresses the deep-scrub reconstruct on mode entry via the freeze-fix flag; populates the report card on Post-run):
```python
    def set_mode(self, idx):
        idx = int(idx)
        if idx != 0:
            self._auto_stopping = True             # leaving Live is not a scrub -> skip the eager reconstruct
            self._run_btn.setChecked(False)        # pause the live sim when entering an analysis mode
        if idx != 1:
            self._meso_page.road.stop()            # road playback only lives on the Meso page
        if idx == 2:
            self._postrun_page.set_summary(self._episode.summary(), self._episode.rows(),
                                           self._champ_name, self._scenarios[self._current_idx].name)
        self._mode_stack.setCurrentIndex(idx)
        if self._mode_sel.currentIndex() != idx:
            self._mode_sel.blockSignals(True)
            self._mode_sel.setCurrentIndex(idx)
            self._mode_sel.blockSignals(False)
```

- [ ] **Step 4: run → pass** `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py -q` (mode toggle + freeze tests still green).
- [ ] **Step 5: commit** `feat(sim/ui): Post-run as a third mode; populate the report card on entry`

---

## Task 5: File → Export… (CSV + PNG)

**Files:** Modify `sim/ui/app.py`; Test `tests/test_sim_ui_smoke.py`.

- [ ] **Step 1: failing test** — append to `tests/test_sim_ui_smoke.py`:
```python
def test_simapp_export_csv_and_png(qapp, tmp_path):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    csv_p = tmp_path / "episode.csv"
    win._do_export_csv(str(csv_p))
    lines = csv_p.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("t,gap,v") and len(lines) >= 6      # header + >=5 rows
    png_p = tmp_path / "shot.png"
    win._do_export_png(str(png_p))
    assert png_p.exists() and png_p.stat().st_size > 0
```

- [ ] **Step 2: run → fail** (`AttributeError: _do_export_csv`).

- [ ] **Step 3: implement** — in `sim/ui/app.py`:

Add `QFileDialog` to the `PySide6.QtWidgets` import. In `_build_menus`, add a File menu at the start of the method (before the View menu):
```python
        file_menu = self.menuBar().addMenu("File")
        a_csv = QAction("Export CSV…", self); a_csv.triggered.connect(self._export_csv)
        a_png = QAction("Export PNG…", self); a_png.triggered.connect(self._export_png)
        file_menu.addAction(a_csv); file_menu.addAction(a_png)
```
(`QAction` is from `PySide6.QtGui`; add it to that import if not already present.) Add the handlers + testable core:
```python
    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export episode CSV", "episode.csv", "CSV (*.csv)")
        if path:
            self._do_export_csv(path)

    def _do_export_csv(self, path):
        try:
            write_episode_csv(self._episode.rows(), path)
            self._status.showMessage(f"CSV saved to {path}", 3000)
        except OSError as e:
            self._status.showMessage(f"CSV export failed: {e}", 5000)

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export view PNG", "simulator.png", "PNG (*.png)")
        if path:
            self._do_export_png(path)

    def _do_export_png(self, path):
        if self.grab().save(path):
            self._status.showMessage(f"PNG saved to {path}", 3000)
        else:
            self._status.showMessage("PNG export failed", 5000)
```

- [ ] **Step 4: run → pass** `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py::test_simapp_export_csv_and_png -q`.
- [ ] **Step 5: commit** `feat(sim/ui): File -> Export... (episode CSV + window PNG)`

---

## Task 6: Render-verify + golden + docs

- [ ] **Step 1: Full golden suite** — the 20-file sim list (add `tests/test_sim_episode.py` and `tests/test_sim_postrun.py`). Expected: all PASS, single-vehicle golden bit-identical.
- [ ] **Step 2: Render-verify** — scratchpad script (`QT_QPA_PLATFORM=windows`): build `SimApp`, `select_scenario(0)`, run a full episode (small `_advance` chunks, or `_advance(60.0)`), `set_mode(2)`, `win.show()`, grab → PNG; read it and confirm the report card (esito/min gap/min TTC/energy/advantage) + the v(t)/gap(t) plots are populated. Also `win._do_export_csv(<scratch>)` and open the CSV head to confirm real rows. Fix any real issue (investigate the cause).
- [ ] **Step 3: Docs** — update `docs/superpowers/2026-07-07-simulator-extension-study.md` §6 (Phase 4 partially done: post-run seal + export; A/B deferred) and `SIMULATOR_SESSION_RESUME.md` + `SESSION_RESUME.md` (state + next). Commit.
- [ ] **Step 4: Memory** — update `cf-fsnn-parallel-tracks.md` + `MEMORY.md` banner. 
- [ ] **Step 5: Push** `git push`.

---

## Self-Review

**Spec coverage:** post-run 3rd mode (T3+T4) · incremental accumulator source (T1+T2) · report card safety/comfort/energy/network (T3) · CSV+PNG export (T5) · frozen core / golden (T1 pure, T6) · A/B deferred (not in plan) ✓.

**Placeholder scan:** no TBD; every code step has full code; the render script (T6.2) is a throwaway scratchpad harness described procedurally.

**Type consistency:** `EpisodeSummary(dims=(n_in,n_hid,n_out,rank))`, `.reset()`, `.update(r, spikes)`, `.summary()->dict`, `.rows()->list`, `write_episode_csv(rows, path)` — used identically in `episode.py`, `SimApp`, and tests. `PostRunPage.set_summary(s, rows, champion, scenario)` with `_values`/`_header`/`_v_curve` consistent across page + test + `set_mode`. `SimApp._do_export_csv(path)`/`_do_export_png(path)` testable cores under the dialog handlers. `set_mode` uses the existing `_auto_stopping` flag (from the freeze fix) to avoid a reconstruct on mode entry — consistent with `_on_run_toggled`.
