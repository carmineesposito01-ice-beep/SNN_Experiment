# Post-run Dashboard (PostRunPage v3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** Replace the bland columnar report card with a **dark pyqtgraph card dashboard**: a verdict
header + a multi-column grid of styled cards, each with a mini bar/marker plot (visual) AND the metric
values with '?' formula tooltips. Same data (`EpisodeSummary.summary()`), richer presentation,
consistent with the rest of the simulator.

**Architecture:** rewrite `sim/ui/postrun_page.py` only. Keep `_METRIC_HELP` (tooltips) and
`set_summary(s, rows, champion, scenario)` (same signature — the app is unchanged). Add per-group card
builders using pyqtgraph `BarGraphItem` + `InfiniteLine`. `_values`/`_help_labels` dicts stay (tests +
tooltips rely on them). Energy display stays consistent (rounds only for display; summary is the source).

**Tech Stack:** PySide6 (QFrame cards, QGridLayout), pyqtgraph (bars/markers), env `cf_sim`.
Commits without `Co-Authored-By`. No core touch → golden unaffected.

---

## Task D1: PostRunPage v3 dashboard

**Files:** Modify `sim/ui/postrun_page.py`; Test `tests/test_sim_postrun.py`.

**Design (approved):**
- **Header**: a large verdict badge (`ok` green / `COLLISIONE` red) + `champion · scenario · durata`.
- **Cards** (dark `QFrame`, thin border, title with a `?`), in a `QGridLayout` (~3 columns), full width:
  1. **Identificazione** — horizontal `BarGraphItem` of the 5 per-param errors (v0/T/s0/a/b), coloured
     green→red by magnitude; a big `accuratezza X%` label. Values as `?`-tooltipped labels beside.
  2. **Sicurezza** — bars vs thresholds: min TTC (line @1.5 s), max DRAC (line @3.35), brake-margin
     (line @0), min gap; bar green if safe / red if past the line.
  3. **Comfort** — RMS accel / max decel / RMS jerk bars vs ISO lines (3.5 / 2.0).
  4. **Salute rete / FPGA** — ρ on a [0..max(2,ρ)] scale with a marker + a `1.0` line (green region
     ρ<1 / red ρ>1) = the FPGA discriminant; firing% / dead% bars.
  5. **Efficienza** — SNN vs ANN energy as two bars (advantage obvious) + a stacked breakdown bar
     (fc/rec_V/rec_U/out); `vantaggio ×` label.
  6. **Andamento** — the existing `v(t)` and `gap(t)` plots, in a card.
- Every metric keeps its `?` tooltip (`_METRIC_HELP`), shown on a small label next to its value inside
  each card (so `_values[key]`/`_help_labels[key]` remain populated for all keys).
- Dark styling via a stylesheet on the page + cards; pyqtgraph plots are dark by default.

- [ ] **Step 1 — update the test** (`tests/test_sim_postrun.py`): the existing
  `test_postrun_page_populates` and `test_postrun_page_v2_groups_and_tooltips` must still pass
  (same `set_summary` signature, same `_values`/`_help_labels`/`_METRIC_HELP`, `_v_curve` present).
  Add a v3 test:
```python
def test_postrun_page_v3_cards(qapp):
    p = PostRunPage()
    assert len(p._cards) >= 5                      # dashboard is card-based
    assert p._verdict is not None                  # big verdict badge exists
```
- [ ] **Step 2 — run → fail** (`_cards`/`_verdict` missing).
- [ ] **Step 3 — implement** the v3 dashboard in `sim/ui/postrun_page.py` (keep `_GROUPS`/`_METRIC_HELP`,
  rebuild the widget tree into cards + header badge + per-card bar plots; `set_summary` fills `_values`
  (all keys), `_help_labels`, `_verdict`, and the bar/marker data). Store cards in `self._cards`.
- [ ] **Step 4 — run → pass** `conda run -n cf_sim python -m pytest tests/test_sim_postrun.py -q`.
- [ ] **Step 5 — commit** `feat(sim/ui): PostRunPage v3 — dark pyqtgraph card dashboard (bars/markers), tooltips kept`

---

## Task D2: Render-verify (iterate) + golden + docs + push

- [ ] **Step 1 — render-verify** — scratchpad script **with `apply_dark_theme`** (fixes the earlier
  light-bg artefact): run a full cut_in episode for Raffaello (ρ>1) + Donatello (ρ<1), `set_mode(2)`,
  grab. Read the PNGs; iterate on layout/spacing/colours until it reads as a proper dark dashboard
  (cards fill the width, bars legible, verdict badge, ρ scale clear). This is the main effort — loop
  until it looks right, investigating any glitch (no papering over).
- [ ] **Step 2 — full golden suite** (all `test_sim_*.py`). Expected: PASS, core bit-identical.
- [ ] **Step 3 — docs + memory** — note the dashboard redesign in the resume trio + memory.
- [ ] **Step 4 — push.**

---

## Self-Review

- **Coverage:** dark card dashboard (D1) with all 5 metric groups + andamento; verdict badge; per-metric
  `?` tooltips preserved (`_METRIC_HELP`, `_help_labels`); `set_summary` signature unchanged (app untouched).
- **Energy:** display-only rounding; the summary (single reused path) is unchanged → the advantage still
  matches the SynOps dock. No new energy calc.
- **No core touch:** only `postrun_page.py`; golden unaffected. Tests keep `_values`/`_v_curve` so v1/v2
  tests still pass.
- **Types:** `set_summary(s, rows, champion, scenario)`, `_values[key]`, `_help_labels[key]`, `_cards`,
  `_verdict`, `_v_curve`/`_gap_curve` consistent across page + tests.
