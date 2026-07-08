# Simulator Dockable Shell — Design Spec (Extension Phase 2)

> Design phase (brainstorming output). **No implementation** — the implementation plan follows in
> `docs/superpowers/plans/`. Scoped entirely to `sim/ui/*`; the golden-tested headless core
> (`sim/state.py`, `sim/stepper.py`, `sim/backend.py`, `sim/events.py`, `sim/probe.py`,
> `sim/eventprop_stepper.py`) is a frozen contract and is **not touched**.

**Goal:** Turn the fixed vertical UI into a **customizable dockable workspace**: every graph is an
independent dock the user can drag, resize, tear out into its own window (pop-out), or tab-stack;
plus layout persistence and named preset layouts.

**This is Extension Phase 2** of the study (`docs/superpowers/2026-07-07-simulator-extension-study.md`
§3/§6). Runs in the **`cf_sim`** conda env (offscreen for headless tests). Golden core untouched.

---

## 1. Decisions (locked in brainstorming, 2026-07-08)

| # | Decision | Choice |
|---|---|---|
| D1 | Scope | **Full dockable shell + layout persistence + named presets** (not the minimal no-persistence variant) |
| D2 | Docking library | **pyqtgraph `DockArea`/`Dock`** (not Qt `QDockWidget`, not `QMdiArea`) — pyqtgraph-native, `TopDownView` drops in unchanged, `DockArea` is a `QWidget` |
| D3 | Dock granularity | **8 docks**: `Road`, `Raster`, `v_mem`, and **each of the 5 params as its own dock** (`v0`,`T`,`s0`,`a`,`b`). Max flexibility: pop out a single param |
| D4 | Presets | **4**: `Overview` (default), `Guida`, `Identificazione`, `Neuro-debug` (+ user custom save/restore) |
| D5 | Preset mechanism | **Programmatic arrangement** (`moveDock`/`show`/`hide`), NOT stored `saveState` dicts → robust, version-independent |
| D6 | Persistence mechanism | `DockArea.saveState()`/`restoreState()` **only** for the user's custom layout, guarded (D9) |
| D7 | NetPanel | **Dissolved** into per-graph widgets (`RasterPanel`, `VmemPanel`, `ParamPanel`) — required for 8 docks; cleaner (SRP). `sim/ui/netpanel.py` removed |
| D8 | Firing-% readout | Moved from a NetPanel label into the **status bar** (always visible, layout-independent) |
| D9 | `restoreState` risk mitigation | (a) build **all** docks first, then restore; (b) unique stable dock names; (c) `restoreState` in **try/except → fallback to `Overview`**; (d) round-trip + corrupt-state tests in the suite |
| D10 | Startup layout | Auto-load the saved custom layout **if present** (guarded per D9 → falls back to `Overview`); otherwise `Overview` |

**X-link:** the 5 param plots stay X-linked (`setXLink`) even when torn out into separate windows —
`setXLink` links by `PlotItem` reference, independent of widget/window hierarchy.

---

## 2. Architecture

```
QMainWindow (SimApp)
├─ menuBar
│    ├─ "View"    → 8 checkable actions, one per dock (show/hide; re-show a closed dock)
│    └─ "Layout"  → Overview · Guida · Identificazione · Neuro-debug · │ · Save layout · Reset to saved
├─ centralWidget = QWidget
│    └─ QVBoxLayout:
│         ├─ header QLabel   "champion: … | scenario: …"        (fixed)
│         ├─ controls QHBoxLayout  selector/Run/Step/Reset/Brake/speed   (fixed, wiring unchanged)
│         └─ DockArea  ← the 8 docks                              (stretch)
└─ statusBar   "t=… | ego … | leader … | gap … | firing …% | ok"
```

- Controls + header stay **fixed** above the `DockArea`; their existing signal wiring is untouched.
- `DockArea` fills the rest of the central widget (it is a plain `QWidget`).
- Status bar gains the **firing %** (from `probe.spikes_matrix()[-1].mean()`), so network activity is
  visible regardless of which docks are open.
- The `QTimer` fixed-timestep live loop (`_on_timer` → `_advance` → `_paint`) is unchanged in shape;
  only the paint fan-out changes (updates each live panel + the road, instead of one NetPanel).

---

## 3. Components

### 3.1 New: `sim/ui/panels.py` (dissolved NetPanel)

Three focused `QWidget`s, each with one responsibility and a `update_frame(probe)` method:

```python
class RasterPanel(QWidget):
    """Spike raster (pg.ImageItem)."""
    def update_frame(self, probe): ...   # probe.spikes_matrix().T

class VmemPanel(QWidget):
    """v_mem sample-neuron traces + effective threshold (dashed)."""
    def update_frame(self, probe): ...

class ParamPanel(QWidget):
    """ONE identified param, physical units, dashed GT reference line, value in the title."""
    def __init__(self, index: int, name: str, unit: str, color: str): ...
    @property
    def plot_item(self): ...                  # the pg.PlotItem, for cross-dock setXLink
    def set_ground_truth(self, value_or_none): ...   # dashed InfiniteLine at value; None hides
    def update_frame(self, probe): ...        # probe.params_matrix()[:, index]; title "name = val unit"
```

Phase-1 functionality is **preserved**, just relocated: physical-unit per-param plots, dashed GT
reference, value-in-title → `ParamPanel`; firing-% → status bar (§2). Phase-1 constants
(`_PARAM_NAMES`, `_PARAM_UNITS`, `_PARAM_COLORS`) move here.

### 3.2 New: `sim/ui/layout.py` (presets + persistence)

```python
DOCK_ORDER = ["Road", "Raster", "v_mem", "v0", "T", "s0", "a", "b"]
LAYOUT_PATH = os.path.expanduser("~/.cf_fsnn_sim/layout.json")

def apply_overview(area, docks): ...          # all visible, balanced (road top; raster|v_mem; 5 params row)
def apply_guida(area, docks): ...             # Road large; params tab-stacked; raster/v_mem small
def apply_identificazione(area, docks): ...   # 5 param docks dominate; road/raster small; v_mem hidden
def apply_neuro_debug(area, docks): ...       # Raster + v_mem large; params compact; road small
PRESETS = {"Overview": apply_overview, "Guida": apply_guida,
           "Identificazione": apply_identificazione, "Neuro-debug": apply_neuro_debug}

def save_layout(area, path=LAYOUT_PATH): ...  # json.dump(area.saveState()); mkdir parent
def load_layout(area, docks, path=LAYOUT_PATH) -> bool:
    """Guarded restore. Returns True if a saved layout was applied, False if it fell back to Overview.
    On missing file OR any restoreState exception -> apply_overview(area, docks)."""
```

Presets arrange via `area.moveDock(dock, position, neighbor)` + `dock.show()/hide()` — no dependency
on the fragile `saveState` format. Only the user's explicit "Save layout" writes `saveState()` JSON;
only "Reset to saved" / startup reads it (guarded).

### 3.3 Rewrite: `sim/ui/app.py` (SimApp)

- Build the 8 dock widgets: `TopDownView` + `RasterPanel` + `VmemPanel` + 5×`ParamPanel`.
- Wrap each in a `Dock(name)`; add all to a `DockArea`; **build all before any restore** (D9a).
- X-link: `for p in params[1:]: p.plot_item.setXLink(params[0].plot_item)`.
- `menuBar`: View menu (checkable per-dock visibility, synced to `dock.sigClosed`), Layout menu
  (apply each preset via `PRESETS`, `save_layout`, `load_layout`).
- `select_scenario`: unchanged loop/probe rebuild; now calls `set_ground_truth(sc.params_gt[i])` on
  each `ParamPanel`.
- `_paint`: updates `TopDownView` from the last result, and calls `update_frame(self._probe)` on every
  live panel (`self._live_panels = [raster, vmem, *params]`).
- `status_text`: appends `firing {pct}%`.
- Startup: `load_layout(area, docks)` (D10) → Overview if none/failure.

### 3.4 Removed: `sim/ui/netpanel.py`

Superseded by `panels.py`. Its Phase-1 tests are rewritten against the new panel classes (§5).

---

## 4. Data flow

Unchanged upstream: `SimLoop.tick` → `SimStepper.step` → `AttributeProbe.record`. The probe remains the
single source the panels read (`spikes_matrix`, `params_matrix`, `frames`). The only change is
**fan-out**: `_paint` now pushes the probe to N small panels instead of one NetPanel. No new coupling to
the core; panels depend only on the probe's public accessors.

## 5. Testing (headless, `QT_QPA_PLATFORM=offscreen`, in `cf_sim`)

Append/adjust in `tests/test_sim_ui_smoke.py` (+ maybe a new `tests/test_sim_layout.py`):

- **Panels** (replacing NetPanel tests): `RasterPanel`/`VmemPanel`/`ParamPanel` instantiate + `update_frame`
  without raising; `ParamPanel` plots raw physical value (`> 40` for v0=44), title shows `v0 = 44.00 m/s`,
  `set_ground_truth` shows/hides the dashed line at the right value.
- **Docks**: `SimApp` builds 8 docks with the expected names; all present in the `DockArea`.
- **X-link**: after `params[0].plot_item.setXRange(a, b)`, `params[3]` reports the same X range (linked).
- **View menu**: toggling a dock action hides/shows that dock.
- **Presets**: each `PRESETS[name](area, docks)` runs without raising and yields the expected visible set
  (e.g. `Neuro-debug` → Raster+v_mem visible; `Identificazione` → 5 params visible, v_mem hidden).
- **Persistence round-trip**: `save_layout` then `load_layout` returns `True` and raises nothing.
- **Corrupt-state fallback**: `load_layout` on a malformed JSON returns `False` (fell back to Overview),
  no exception — the D9c safety net.
- **Regression**: full golden suite (`test_sim_state/backend/stepper/scenario/events/probe/replay/loop/
  eventprop/champion_io`) stays green — core untouched.
- **Render check**: windowed render (`QT_QPA_PLATFORM=windows`) of Overview + one preset, visual inspect.

## 6. Error handling

- `restoreState` and `load_layout`: wrapped in try/except → `apply_overview` fallback (D9c). A user's
  stale/corrupt saved layout can never brick the UI; worst case it opens in Overview.
- `save_layout`: creates `~/.cf_fsnn_sim/` if missing; failure to write is surfaced (status message), not
  silently swallowed.
- Dock close via the `×`: the View-menu checkbox re-syncs (via `dock.sigClosed`), so a closed dock is
  always re-openable.

## 7. Scope boundaries (explicitly OUT — later phases)

- **New live metric panels** (trajectory, safety strip, per-neuron inspector, event timeline) → Phase 3.
- **Time-scrub / global time cursor** (pause + seek through the ring buffer) → Phase 3.
- **Float-vs-fixed A/B, post-run seal, export** → Phase 4.
- This phase delivers **only** the dockable shell + persistence + the 4 presets.

## 8. File structure

| File | Change |
|---|---|
| `sim/ui/panels.py` | **Create** — `RasterPanel`, `VmemPanel`, `ParamPanel` |
| `sim/ui/layout.py` | **Create** — 4 preset functions + `save_layout`/`load_layout` (guarded) |
| `sim/ui/app.py` | **Rewrite** — `DockArea` shell, menuBar (View/Layout), 8 docks, X-link, firing-in-statusbar, startup load |
| `sim/ui/netpanel.py` | **Remove** — dissolved into `panels.py` |
| `tests/test_sim_ui_smoke.py` | **Modify** — NetPanel tests → panel tests; add dock/X-link/View tests |
| `tests/test_sim_layout.py` | **Create** — presets, persistence round-trip, corrupt-state fallback |
| `scripts/run_simulator.py` | Unchanged (still `SimApp(champion)`) |

## 9. Library risk (pyqtgraph 0.14 `restoreState`)

Known bugs GH #2887 (sole-child container silently drops docks) and #3125 (`TypeError` on
tear-out-then-redock before save). Mitigation is D9 (build-all-first, unique names, guarded restore +
fallback, round-trip + corrupt-state tests). Shipped presets avoid `restoreState` entirely (programmatic),
so the risky path is confined to the user's optional custom-layout save/restore, which always falls back
to `Overview`. `Dock(size=…)` is a stretch hint, not pixels; tune with the arrangement, not exact sizes.
