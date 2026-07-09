# Phase 3b (rest) — Deep-scrub, Event-timeline, Neuron-inspector — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** ✅ COMPLETE (2026-07-09, commits `b8a406c`..`5f05882`). 83 sim tests green; core bit-identical; render-verified on real `windows` Qt.

**Goal:** Add whole-episode scrub (reconstruct beyond the 500-tick buffer), a clickable event-timeline dock, and a per-neuron inspector dock with graph highlighting — all on top of the 3b.1 scrub cursor.

**Architecture:** A read-only `reconstruct_history` re-runs the episode from the `ReplayLog` into full-length `AttributeProbe`/`TrajectoryBuffer` of the *same types*, so the existing panels render it unchanged; the app gains a `_src_probe/_src_traj` "scrub source" that is the live ring buffer while running and the reconstructed full history when paused-and-wrapped. Two new `panels.py` widgets (`EventTimelinePanel`, `NeuronInspectorPanel`) plus `sigNeuronClicked`/`highlight` on `NeuronGraphPanel` deliver the events + inspector UX.

**Tech Stack:** PySide6 6.11, pyqtgraph 0.14, numpy, torch (via existing sim core), pytest. Conda env `cf_sim`.

**Test invocation:** `conda run -n cf_sim python -m pytest <file> -v` (list sim test files explicitly; never the whole `tests/` dir). For real-window renders, write a script to the scratchpad and run it (no `python -c` inline).

**Core freeze:** `sim/state.py`, `sim/stepper.py`, `sim/backend.py`, `sim/events.py`, `sim/probe.py`, `sim/eventprop_stepper.py`, `sim/replay.py` are NOT edited. The golden sim suite must stay bit-identical.

---

## File structure

- **Create** `sim/ui/reconstruct.py` — `reconstruct_history`.
- **Create** `tests/test_sim_reconstruct.py`.
- **Modify** `sim/ui/panels.py` — add `EventTimelinePanel`, `NeuronInspectorPanel`; add `sigNeuronClicked` + `highlight` + node-click wiring to `NeuronGraphPanel`; add `QLabel`, `Signal` imports.
- **Modify** `tests/test_sim_panels.py` — event-timeline, inspector, highlight, node-click tests.
- **Modify** `sim/ui/layout.py` — `DOCK_ORDER` (+Events,+Inspector) and the 4 presets.
- **Modify** `sim/ui/app.py` — scrub source, reconstruct-on-pause, event/neuron wiring, 13 docks.
- **Modify** `tests/test_sim_ui_smoke.py` — deep-scrub + event-click + neuron-select integration.
- **Modify** docs: study §6, this plan's banner, memory.

---

## Task 1: `reconstruct_history` (deep-scrub foundation)

**Files:**
- Create: `sim/ui/reconstruct.py`
- Test: `tests/test_sim_reconstruct.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_sim_reconstruct.py`:

```python
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.backend import SoftwareBackend               # noqa: E402
from sim.probe import AttributeProbe                   # noqa: E402
from sim.stepper import SimStepper                     # noqa: E402
from sim.events import EventInjector                   # noqa: E402
from sim.replay import ReplayLog                       # noqa: E402
from sim.scenario import manual_scenario               # noqa: E402
from sim.ui.trajectory import TrajectoryBuffer         # noqa: E402
from sim.ui.reconstruct import reconstruct_history     # noqa: E402
from utils.champion_io import load_champion            # noqa: E402

CHAMP = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")
_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


def _short_scenario(n=40):
    v_set = 0.7 * float(_PG[0])
    return manual_scenario(_PG, np.full(n, v_set),
                           s_init=float(_PG[2]) + v_set * float(_PG[1]), v_init=v_set)


def _live_run(champion, scenario, injector, n, capacity):
    backend = SoftwareBackend(champion.model)
    stepper = SimStepper.from_scenario(backend, scenario, injector=injector)
    probe = AttributeProbe(capacity=capacity)
    traj = TrajectoryBuffer(capacity=capacity)
    for _ in range(n):
        if stepper.st.collided or stepper.st.t >= stepper.N:
            break
        r = stepper.step()
        probe.record(r.t, backend.read_probe(), r.params)
        traj.record(r)
    return probe, traj


def test_reconstruct_bit_identical_to_live():
    champion = load_champion(CHAMP)
    scenario = _short_scenario(40)
    inj = EventInjector()
    inj.enqueue(5, "brake_leader", target_v=15.0, duration=10)   # mild brake, no collision in 40 ticks
    live_probe, live_traj = _live_run(champion, scenario, inj, n=40, capacity=40)
    rlog = ReplayLog.from_injector(0, inj)
    rprobe, rtraj = reconstruct_history(champion, scenario, rlog, upto=39)
    lf, rf = live_probe.frames(), rprobe.frames()
    assert len(lf) >= 1 and len(rf) == len(lf)
    for a, b in zip(lf, rf):
        assert a.t == b.t
        np.testing.assert_array_equal(a.spikes, b.spikes)
        np.testing.assert_array_equal(a.v_mem, b.v_mem)
        np.testing.assert_array_equal(a.v_th_eff, b.v_th_eff)
        np.testing.assert_array_equal(a.params, b.params)
        np.testing.assert_array_equal(a.input, b.input)
    np.testing.assert_array_equal(live_traj.arrays()["s"], rtraj.arrays()["s"])


def test_reconstruct_respects_upto():
    champion = load_champion(CHAMP)
    scenario = _short_scenario(40)
    rlog = ReplayLog.from_injector(0, EventInjector())
    rprobe, rtraj = reconstruct_history(champion, scenario, rlog, upto=9)
    assert len(rprobe.frames()) == 10 and len(rtraj) == 10
```

- [ ] **Step 2: Run it to verify it fails**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_reconstruct.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.ui.reconstruct'`.

- [ ] **Step 3: Write the implementation**

Create `sim/ui/reconstruct.py`:

```python
"""reconstruct_history -- deterministic re-run of an episode into FULL-length buffers.

Deep-scrub foundation. The live probe is a 500-tick ring buffer; to scrub ticks
older than that we re-run from the ReplayLog (seed + logged events) into an
AttributeProbe/TrajectoryBuffer sized to the whole episode. Bit-identical to the
live run: same stepper.step(), same backend.read_probe(); no per-step RNG, the
scenario is a fixed array, the champion is fixed, injector.tick is deterministic.
Read-only -- the frozen core is untouched.
"""
from sim.backend import SoftwareBackend
from sim.probe import AttributeProbe
from sim.stepper import SimStepper
from sim.ui.trajectory import TrajectoryBuffer


def reconstruct_history(champion, scenario, replaylog, upto):
    """Re-run scenario 0..upto and return (probe, traj) filled with every tick."""
    n = int(upto) + 1
    backend = SoftwareBackend(champion.model)
    stepper = SimStepper.from_scenario(backend, scenario,
                                       injector=replaylog.build_injector())
    probe = AttributeProbe(capacity=n)
    traj = TrajectoryBuffer(capacity=n)
    for _ in range(n):
        if stepper.st.collided or stepper.st.t >= stepper.N:
            break
        r = stepper.step()
        probe.record(r.t, backend.read_probe(), r.params)
        traj.record(r)
    return probe, traj
```

- [ ] **Step 4: Run test to verify it passes**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_reconstruct.py -v`
Expected: PASS (2 tests). If `test_reconstruct_bit_identical_to_live` fails on an array-equal, that is a real determinism regression — investigate, do NOT loosen to `allclose`.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/reconstruct.py tests/test_sim_reconstruct.py
git commit -m "feat(sim/ui): reconstruct_history — bit-identical full-episode replay for deep-scrub"
```

---

## Task 2: `EventTimelinePanel` (dock "Events")

**Files:**
- Modify: `sim/ui/panels.py`
- Test: `tests/test_sim_panels.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sim_panels.py`:

```python
# --- Phase 3b (rest): event timeline ---
from sim.ui.panels import EventTimelinePanel   # noqa: E402
from sim.probe import ProbeFrame               # noqa: E402


def _pf(ticks):
    return [ProbeFrame(t=t, spikes=np.zeros(2), v_mem=np.zeros(2), v_th_eff=np.ones(2),
                       params=np.zeros(5)) for t in ticks]


def test_event_timeline_maps_ticks_and_drops_out_of_range(qapp):
    panel = EventTimelinePanel()
    frames = _pf(range(100, 200))                          # ticks 100..199 -> idx 0..99
    log = [{"tick": 130, "verb": "brake_leader", "params": {}},
           {"tick": 400, "verb": "brake_leader", "params": {}},   # dropped (out of range)
           {"tick": 50,  "verb": "brake_leader", "params": {}}]   # dropped (out of range)
    panel.update_events(log, frames)
    xs = sorted(p.pos().x() for p in panel._marks.points())
    assert xs == [30.0]                                    # only tick 130 -> idx 30


def test_event_timeline_click_seeks_by_tick(qapp):
    panel = EventTimelinePanel()
    seen = []
    panel.set_on_seek(lambda tick: seen.append(tick))
    panel.update_events([{"tick": 105, "verb": "brake_leader", "params": {}}], _pf(range(100, 110)))
    panel._on_click(panel._marks, list(panel._marks.points()))
    assert seen == [105]                                   # seeks by absolute tick, not buffer index


def test_event_timeline_has_cursor(qapp):
    panel = EventTimelinePanel()
    panel.set_cursor(4)
    assert panel._cursors[0].isVisible() and abs(panel._cursors[0].value() - 4.0) < 1e-6
    panel.set_cursor(None)
    assert not panel._cursors[0].isVisible()
```

- [ ] **Step 2: Run to verify it fails**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -k event_timeline -v`
Expected: FAIL — `ImportError: cannot import name 'EventTimelinePanel'`.

- [ ] **Step 3: Write the implementation**

In `sim/ui/panels.py`, add the class (e.g. after `SpikeRatePanel`). It reuses the module-level `_add_cursor`/`_set_cursor` helpers:

```python
class EventTimelinePanel(QWidget):
    """Injected events (injector.log()) as clickable marks on the source-index axis.
    Marks store the ABSOLUTE tick; clicking calls the seek callback with that tick."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget(title="events")
        self._plot.hideAxis("left")
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setMouseEnabled(x=True, y=False)
        self._plot.setYRange(-1, 1)
        layout.addWidget(self._plot)
        self._marks = pg.ScatterPlotItem(symbol="t", size=14, brush=pg.mkBrush("#EF9F27"),
                                         pen=pg.mkPen("#0e1116"), hoverable=True)
        self._marks.sigClicked.connect(self._on_click)
        self._plot.addItem(self._marks)
        self._labels = []
        self._on_seek = None
        self._cursors = [_add_cursor(self._plot.getPlotItem())]

    def set_cursor(self, x):
        _set_cursor(self._cursors, x)

    def set_on_seek(self, cb):
        self._on_seek = cb

    def _clear_labels(self):
        for t in self._labels:
            self._plot.removeItem(t)
        self._labels = []

    def update_events(self, log, frames):
        self._clear_labels()
        tick_to_idx = {f.t: i for i, f in enumerate(frames)}
        spots = []
        for e in log:
            idx = tick_to_idx.get(e["tick"])
            if idx is None:
                continue                                   # scrolled out of the source -> skip
            spots.append({"pos": (idx, 0.0), "data": e["tick"]})
            lbl = pg.TextItem(e["verb"], color="#EF9F27", anchor=(0.5, 1.4))
            lbl.setPos(float(idx), 0.0)
            self._plot.addItem(lbl)
            self._labels.append(lbl)
        self._marks.setData(spots)

    def _on_click(self, scatter, points):
        if points and self._on_seek is not None:
            self._on_seek(int(points[0].data()))
```

- [ ] **Step 4: Run to verify it passes**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -k event_timeline -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add sim/ui/panels.py tests/test_sim_panels.py
git commit -m "feat(sim/ui): EventTimelinePanel — clickable event marks, seek by tick"
```

---

## Task 3: `NeuronGraphPanel` — `sigNeuronClicked` + `highlight`

**Files:**
- Modify: `sim/ui/panels.py`
- Test: `tests/test_sim_panels.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sim_panels.py`:

```python
# --- Phase 3b (rest): graph click + highlight ---
def test_neuron_graph_highlight_fan_in_out(qapp):
    H, IN, OUT = 6, 4, 5
    rng = np.random.default_rng(2)
    panel = NeuronGraphPanel()
    panel.set_topology(rng.standard_normal((H, IN)), rng.standard_normal((H, H)),
                       rng.standard_normal((OUT, H)))
    panel.highlight(2)
    node = IN + 2
    adj = panel._highlight.adjacency
    assert adj.shape[0] == IN + (H - 1) + (H - 1) + OUT      # fan-in(in+rec) + fan-out(rec+out)
    assert np.all((adj[:, 1] == node) | (adj[:, 0] == node))
    panel.highlight(None)
    assert panel._highlight.adjacency.shape[0] == 0


def test_neuron_graph_click_emits_hidden_index(qapp):
    H, IN, OUT = 6, 4, 5
    rng = np.random.default_rng(3)
    panel = NeuronGraphPanel()
    panel.set_topology(rng.standard_normal((H, IN)), rng.standard_normal((H, H)),
                       rng.standard_normal((OUT, H)))
    got = []
    panel.sigNeuronClicked.connect(lambda i: got.append(i))

    class _Spot:
        def index(self_):
            return IN + 3                                   # node index of hidden neuron 3

    panel._on_node_click(panel._nodes, [_Spot()])
    assert got == [3]


def test_neuron_graph_click_ignores_non_hidden(qapp):
    H, IN, OUT = 6, 4, 5
    rng = np.random.default_rng(4)
    panel = NeuronGraphPanel()
    panel.set_topology(rng.standard_normal((H, IN)), rng.standard_normal((H, H)),
                       rng.standard_normal((OUT, H)))
    got = []
    panel.sigNeuronClicked.connect(lambda i: got.append(i))

    class _Spot:
        def index(self_):
            return 0                                        # an input node

    panel._on_node_click(panel._nodes, [_Spot()])
    assert got == []                                        # input/output clicks are no-ops
```

- [ ] **Step 2: Run to verify it fails**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -k "highlight or click_emits or click_ignores" -v`
Expected: FAIL — `AttributeError: 'NeuronGraphPanel' object has no attribute 'sigNeuronClicked'`.

- [ ] **Step 3: Write the implementation**

3a. In `sim/ui/panels.py`, extend the `PySide6.QtCore` import:

```python
from PySide6.QtCore import Qt, Signal
```

3b. Add `sigNeuronClicked` as a class attribute of `NeuronGraphPanel` and create the highlight overlay + wire node clicks in `__init__`. Replace the `__init__` item-creation block:

```python
    sigNeuronClicked = Signal(int)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._plot = pg.PlotWidget()
        self._plot.hideAxis("left")
        self._plot.hideAxis("bottom")
        self._plot.setMenuEnabled(False)
        layout.addWidget(self._plot)
        self._lut = pg.colormap.get("viridis").getLookupTable(0.0, 1.0, 256)
        self._skeleton = pg.GraphItem()
        self._highlight = pg.GraphItem()
        self._active = pg.GraphItem()
        self._nodes = pg.ScatterPlotItem()
        for it in (self._skeleton, self._highlight, self._active, self._nodes):
            self._plot.addItem(it)
        self._nodes.sigClicked.connect(self._on_node_click)
        self._pos = None
        self._last_vals = None
        self._n_in = self._n_hid = self._n_out = 0
        self._rec_out_adj = None
        self._rec_out_src = None
        self._e_in = self._e_rec = self._e_out = None
```

3c. In `set_topology`, after the existing `all_adj`/`self._skeleton.setData(...)` lines, store the raw edge arrays (they are already built as `e_in`, `e_rec`, `e_out` python lists in that method):

```python
        self._e_in = np.array(e_in, dtype=int)
        self._e_rec = np.array(e_rec, dtype=int)
        self._e_out = np.array(e_out, dtype=int)
```

Add `self.highlight(None)` at the very end of `set_topology` (initialise the empty overlay once positions exist).

3d. Add the two methods to `NeuronGraphPanel`:

```python
    def _on_node_click(self, scatter, points):
        if not points:
            return
        node = points[0].index()
        if self._n_in <= node < self._n_in + self._n_hid:
            self.sigNeuronClicked.emit(node - self._n_in)

    def highlight(self, i):
        if i is None or self._pos is None or self._e_in is None:
            self._highlight.setData(pos=(self._pos if self._pos is not None
                                         else np.zeros((1, 2))),
                                    adj=np.empty((0, 2), dtype=int), pen=pg.mkPen(None), size=0)
            return
        node = self._n_in + int(i)
        allin = np.vstack([self._e_in, self._e_rec])
        allout = np.vstack([self._e_rec, self._e_out])
        fanin = allin[allin[:, 1] == node]
        fanout = allout[allout[:, 0] == node]
        adj = np.vstack([fanin, fanout]).astype(int)
        pens = np.zeros(len(adj), dtype=[('red', np.ubyte), ('green', np.ubyte),
                                         ('blue', np.ubyte), ('alpha', np.ubyte), ('width', float)])
        ni = len(fanin)
        pens['red'][:ni], pens['green'][:ni], pens['blue'][:ni] = 0x8f, 0xb7, 0xe0   # fan-in blue
        pens['red'][ni:], pens['green'][ni:], pens['blue'][ni:] = 0x88, 0xd6, 0xa0   # fan-out green
        pens['alpha'][:] = 255
        pens['width'][:] = 2.0
        self._highlight.setData(pos=self._pos, adj=adj, pen=pens, size=0)
```

- [ ] **Step 4: Run to verify it passes**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -k "highlight or click_emits or click_ignores" -v`
Expected: PASS (3 tests). Also re-run the existing graph tests to confirm no regression:
`conda run -n cf_sim python -m pytest tests/test_sim_panels.py -k neuron_graph -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/panels.py tests/test_sim_panels.py
git commit -m "feat(sim/ui): NeuronGraphPanel sigNeuronClicked + fan-in/out highlight overlay"
```

---

## Task 4: `NeuronInspectorPanel` (dock "Inspector")

**Files:**
- Modify: `sim/ui/panels.py`
- Test: `tests/test_sim_panels.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sim_panels.py`:

```python
# --- Phase 3b (rest): neuron inspector ---
from sim.ui.panels import NeuronInspectorPanel   # noqa: E402


def test_inspector_dominant_connections(qapp):
    H, IN, OUT = 6, 4, 5
    w_in = np.zeros((H, IN)); w_in[3, 2] = 5.0; w_in[3, 0] = 3.0     # #3 driven by input 2 (Δv) then 0 (s)
    w_out = np.zeros((OUT, H)); w_out[4, 3] = 7.0; w_out[3, 3] = 4.0  # #3 drives out 4 (b) then 3 (a)
    panel = NeuronInspectorPanel()
    panel.set_topology(w_in, np.zeros((H, H)), w_out)
    panel.set_neuron(3)
    txt = panel._conn.text()
    assert "#3" in panel._title.text()
    assert txt.index("Δv") < txt.index("s")     # input 2 ranked before input 0
    assert txt.index("b") < txt.index("a")      # out 4 (b) ranked before out 3 (a)


def test_inspector_traces_selected_neuron(qapp):
    panel = NeuronInspectorPanel()
    panel.set_topology(np.zeros((6, 4)), np.zeros((6, 6)), np.zeros((5, 6)))
    panel.set_neuron(2)
    pr = AttributeProbe(capacity=10)
    for t in range(4):
        spk = np.zeros(6); spk[2] = 1.0 if t == 2 else 0.0
        pr.record(t, {"spikes": spk, "v_mem": np.full(6, float(t)), "v_th_eff": np.ones(6)},
                  np.zeros(5))
    panel.update_frame(pr)
    y = panel._vmem.getData()[1]
    assert list(y) == [0.0, 1.0, 2.0, 3.0]      # neuron 2's v_mem over the buffer
    assert len(panel._spk.points()) == 1        # one spike, at t=2


def test_inspector_clear_none(qapp):
    panel = NeuronInspectorPanel()
    panel.set_topology(np.zeros((6, 4)), np.zeros((6, 6)), np.zeros((5, 6)))
    panel.set_neuron(1)
    panel.set_neuron(None)
    assert panel.neuron is None and panel._conn.text() == ""
```

- [ ] **Step 2: Run to verify it fails**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -k inspector -v`
Expected: FAIL — `ImportError: cannot import name 'NeuronInspectorPanel'`.

- [ ] **Step 3: Write the implementation**

3a. Extend the `PySide6.QtWidgets` import in `sim/ui/panels.py`:

```python
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
```

3b. Add the class (e.g. after `NeuronGraphPanel`). `_INPUT_NAMES` and `PARAM_NAMES` are already module-level:

```python
class NeuronInspectorPanel(QWidget):
    """Selected hidden neuron: v_mem + effective threshold + spike marks over the source
    history, plus a readout of its dominant input/output connections (from topology weights)."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel("Inspector · (nessun neurone)")
        self._title.setContentsMargins(6, 3, 6, 0)
        self._plot = pg.PlotWidget()
        self._plot.setLabel("bottom", "time", units="steps")
        self._plot.setLabel("left", "v_mem")
        self._plot.setDownsampling(auto=True, mode="peak")
        self._plot.setClipToView(True)
        self._vmem = self._plot.plot(pen=pg.mkPen("#8fd6ff", width=2))
        self._vth = self._plot.plot(pen=pg.mkPen("#e8871e", width=1, style=Qt.DashLine))
        self._spk = pg.ScatterPlotItem(symbol="t", size=8, brush=pg.mkBrush("#ffffff"),
                                       pen=pg.mkPen(None))
        self._plot.addItem(self._spk)
        self._conn = QLabel("")
        self._conn.setContentsMargins(6, 0, 6, 4)
        layout.addWidget(self._title)
        layout.addWidget(self._plot, stretch=1)
        layout.addWidget(self._conn)
        self._cursors = [_add_cursor(self._plot.getPlotItem())]
        self._w_in = self._w_out = None
        self._i = None

    @property
    def neuron(self):
        return self._i

    def set_cursor(self, x):
        _set_cursor(self._cursors, x)

    def set_topology(self, w_in, w_rec, w_out):
        self._w_in = np.asarray(w_in, dtype=np.float64)      # (H, IN)
        self._w_out = np.asarray(w_out, dtype=np.float64)    # (OUT, H)

    def set_neuron(self, i):
        if i is None:
            self._i = None
            self._title.setText("Inspector · (nessun neurone)")
            self._conn.setText("")
            self._vmem.setData([]); self._vth.setData([]); self._spk.setData([])
            return
        self._i = int(i)
        self._title.setText(f"Inspector · hidden #{self._i}")
        self._conn.setText(self._dominant_text(self._i))

    def _dominant_text(self, i, k=2):
        if self._w_in is None:
            return ""
        win, wout = np.abs(self._w_in[i]), np.abs(self._w_out[:, i])
        ins = ", ".join(f"{_INPUT_NAMES[j] if j < len(_INPUT_NAMES) else j}·{win[j]:.2f}"
                        for j in np.argsort(win)[::-1][:k])
        outs = ", ".join(f"{PARAM_NAMES[j] if j < len(PARAM_NAMES) else j}·{wout[j]:.2f}"
                         for j in np.argsort(wout)[::-1][:k])
        return f"in: {ins}   →   out: {outs}"

    def update_frame(self, probe):
        if self._i is None:
            return
        frames = probe.frames()
        if not frames:
            return
        vm = np.array([f.v_mem[self._i] for f in frames])
        vth = np.array([f.v_th_eff[self._i] for f in frames])
        spk = np.array([f.spikes[self._i] for f in frames]) > 0
        self._vmem.setData(vm)
        self._vth.setData(vth)
        idx = np.nonzero(spk)[0]
        self._spk.setData([{"pos": (float(x), float(vm[x]))} for x in idx])
```

- [ ] **Step 4: Run to verify it passes**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_panels.py -k inspector -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add sim/ui/panels.py tests/test_sim_panels.py
git commit -m "feat(sim/ui): NeuronInspectorPanel — per-neuron scope + dominant connections"
```

---

## Task 5: App + layout wiring (13 docks, scrub source, reconstruct-on-pause)

**Files:**
- Modify: `sim/ui/layout.py`
- Modify: `sim/ui/app.py`
- Test: `tests/test_sim_ui_smoke.py`

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_sim_ui_smoke.py`:

```python
# --- Phase 3b (rest): deep-scrub + events + inspector ---
def test_simapp_builds_13_docks(qapp):
    win = SimApp(CHAMP)
    assert "Events" in win._docks and "Inspector" in win._docks
    assert len(win._docks) == 13


def test_simapp_deep_scrub_reconstructs_beyond_buffer(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)                       # scenario 0: gentle following, runs to completion
    win._advance(60.0)                           # whole episode -> buffer (500) wraps
    assert win.loop.stepper.st.t > win._probe.capacity
    win._run_btn.setChecked(False)               # pause -> reconstruct full episode
    n = len(win._src_probe.frames())
    assert n == win.loop.stepper.st.t            # full episode reconstructed
    assert n > len(win._probe.frames())          # more than the live ring buffer
    win._render_at_cursor(0)                     # scrub to tick 0 (outside the live buffer)
    assert win._cursor == 0 and win._cursor_readout.text().startswith("t=0")


def test_simapp_event_click_and_neuron_select(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    win.inject_brake()
    win._advance(0.5)
    win._run_btn.setChecked(False)               # pause
    log = win._injector.log()
    assert log
    win._seek_to(log[0]["tick"])                 # click the brake mark -> seek to its tick
    assert win._src_probe.frames()[win._cursor].t == log[0]["tick"]
    win._on_neuron_selected(1)                   # select hidden neuron 1
    assert win._inspector.neuron == 1
    assert win._netstate._highlight.adjacency.shape[0] > 0


def test_simapp_resume_reverts_to_live_source(qapp):
    win = SimApp(CHAMP)
    win.select_scenario(0)
    win._advance(0.5)
    win._run_btn.setChecked(False)
    win._run_btn.setChecked(True)                # resume
    assert win._src_probe is win._probe and win._src_traj is win._traj
```

- [ ] **Step 2: Run to verify it fails**

Run: `conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py -k "13_docks or deep_scrub or event_click or resume_reverts" -v`
Expected: FAIL — `KeyError: 'Events'` / `AttributeError: ... _src_probe`.

- [ ] **Step 3a: Update `sim/ui/layout.py`**

Replace `DOCK_ORDER` (line 9-10):

```python
DOCK_ORDER = ["Road", "NetState", "SpikeRate", "v_mem", "Trajectory", "Safety",
              "Events", "Inspector", "v0", "T", "s0", "a", "b"]
```

Add Events + Inspector placement at the end of `apply_overview` (before the final `SpikeRate` split line stays last is fine; append after it):

```python
    _show(area, docks, "Inspector", "right", "SpikeRate")
    _show(area, docks, "Events", "bottom", "Safety")
```

In `apply_guida`, extend the hide loop so the two new docks are hidden (driving story):

```python
    for d in ("NetState", "SpikeRate", "v_mem", "Inspector", "Events"):
        _hide(docks, d)
```

In `apply_identificazione`, hide Inspector and show Events beside the params — replace the hide line and add Events after the param stack:

```python
    for d in ("v_mem", "NetState", "SpikeRate", "Trajectory", "Safety", "Inspector"):
        _hide(docks, d)
```
and after the params `for` loop:
```python
    _show(area, docks, "Events", "bottom", "b")
```

In `apply_neuro_debug`, show Inspector + Events (neuro debug wants them). After the existing `_show(... "v_mem" ...)` line add:

```python
    _show(area, docks, "Inspector", "bottom", "v_mem")
    _show(area, docks, "Events", "bottom", "Road")
```

- [ ] **Step 3b: Update `sim/ui/app.py` — imports**

Extend the panels import and add reconstruct + ReplayLog:

```python
from sim.ui.panels import (PARAM_COLORS, PARAM_NAMES, PARAM_UNITS, EventTimelinePanel,
                           NeuronGraphPanel, NeuronInspectorPanel, ParamPanel, SafetyPanel,
                           SpikeRatePanel, TrajectoryPanel, VmemPanel)
from sim.ui.reconstruct import reconstruct_history
from sim.replay import ReplayLog
```

- [ ] **Step 3c: Update `__init__` — build panels, wire, `_ts_panels`, widgets, source defaults**

After `self._safety = SafetyPanel()` add:

```python
        self._timeline = EventTimelinePanel()
        self._inspector = NeuronInspectorPanel()
```

Replace the `_ts_panels` assignment (line 61) with:

```python
        self._ts_panels = [*self._params, self._vmem, self._spikerate, self._trajectory,
                           self._safety, self._timeline, self._inspector]
```

Remove the `self._live_panels = [...]` line (line 60) — it is superseded by `_redraw_series`.

After the topology block (`self._netstate.set_topology(...)`) add:

```python
        self._inspector.set_topology(_w["w_in"], _w["w_rec"], _w["w_out"])
        self._timeline.set_on_seek(self._seek_to)
        self._netstate.sigNeuronClicked.connect(self._on_neuron_selected)
        self._src_probe = None
        self._src_traj = None
```

Extend the `widgets` dict with the two new docks:

```python
        widgets = {"Road": self._topdown, "NetState": self._netstate, "SpikeRate": self._spikerate,
                   "v_mem": self._vmem, "Trajectory": self._trajectory, "Safety": self._safety,
                   "Events": self._timeline, "Inspector": self._inspector,
                   "v0": self._params[0], "T": self._params[1],
                   "s0": self._params[2], "a": self._params[3], "b": self._params[4]}
```

- [ ] **Step 3d: Update `select_scenario`**

After `self._traj = TrajectoryBuffer()` add:

```python
        self._src_probe = self._probe
        self._src_traj = self._traj
```

Before the final `self._refresh_status()` add (clear selection + highlight on scenario change):

```python
        self._inspector.set_neuron(None)
        self._netstate.highlight(None)
```

- [ ] **Step 3e: Replace `_paint`, add `_redraw_series`**

```python
    def _paint(self, results):
        if results:
            self._last_result = results[-1]
            self._topdown.update_frame(results[-1])
            for r in results:
                self._traj.record(r)
            self._redraw_series(self._probe, self._traj)
            if self._run_btn.isChecked():                 # live: slider tracks the head
                self._cursor_slider.blockSignals(True)
                self._cursor_slider.setRange(0, max(0, self._buf_len() - 1))
                self._cursor_slider.setValue(max(0, self._buf_len() - 1))
                self._cursor_slider.blockSignals(False)
        self._refresh_status()

    def _redraw_series(self, probe, traj):
        for p in self._params:
            p.update_frame(probe)
        self._vmem.update_frame(probe)
        self._spikerate.update_frame(probe)
        self._trajectory.update_frame(traj)
        self._safety.update_frame(traj)
        self._netstate.update_frame(probe)                # head; scrub overrides via _render_at_cursor
        self._timeline.update_events(self._injector.log(), probe.frames())
        if self._inspector.neuron is not None:
            self._inspector.update_frame(probe)
```

- [ ] **Step 3f: Replace `_on_run_toggled`, `_buf_len`, `_render_at_cursor`; add `_seek_to`, `_on_neuron_selected`**

```python
    def _on_run_toggled(self, running: bool):
        if running:                                       # live: hide cursors, disable slider
            self._cursor = None
            self._src_probe, self._src_traj = self._probe, self._traj
            self._cursor_slider.setEnabled(False)
            for p in self._ts_panels:
                p.set_cursor(None)
            self._cursor_readout.setText("live")
            self._clock.restart()
            self._timer.start(_UI_FPS_MS)
        else:                                             # paused: scrub over the whole episode
            self._timer.stop()
            frames = self._probe.frames()
            if frames and frames[-1].t + 1 > self._probe.capacity:   # buffer wrapped -> reconstruct
                rlog = ReplayLog.from_injector(self._current_idx, self._injector)
                self._src_probe, self._src_traj = reconstruct_history(
                    self._champ, self._scenarios[self._current_idx], rlog, frames[-1].t)
            else:
                self._src_probe, self._src_traj = self._probe, self._traj
            self._redraw_series(self._src_probe, self._src_traj)
            n = len(self._src_probe.frames())
            self._cursor_slider.setEnabled(n > 0)
            self._cursor_slider.blockSignals(True)
            self._cursor_slider.setRange(0, max(0, n - 1))
            self._cursor_slider.setValue(max(0, n - 1))
            self._cursor_slider.blockSignals(False)

    def _buf_len(self):
        return len(self._src_probe.frames()) if self._src_probe is not None else 0

    def _render_at_cursor(self, idx):
        frames = self._src_probe.frames()
        if not frames:
            return
        idx = max(0, min(int(idx), len(frames) - 1))
        self._cursor = idx
        for p in self._ts_panels:
            p.set_cursor(idx)
        self._netstate.update_frame(self._src_probe, idx)
        self._topdown.render_at(self._src_traj, idx)
        self._cursor_readout.setText(f"t={frames[idx].t} ({frames[idx].t * DT:.1f}s)")

    def _seek_to(self, tick):
        if self._run_btn.isChecked():
            self._run_btn.setChecked(False)               # pause -> builds the scrub source
        frames = self._src_probe.frames()
        idx = next((i for i, f in enumerate(frames) if f.t == tick), None)
        if idx is None:
            return
        self._render_at_cursor(idx)
        self._cursor_slider.blockSignals(True)
        self._cursor_slider.setValue(idx)
        self._cursor_slider.blockSignals(False)

    def _on_neuron_selected(self, i):
        self._inspector.set_neuron(i)
        self._netstate.highlight(i)
        self._inspector.update_frame(self._src_probe)
        if self._cursor is not None:
            self._inspector.set_cursor(self._cursor)
```

- [ ] **Step 4: Run the integration tests + the full sim UI suite**

```
conda run -n cf_sim python -m pytest tests/test_sim_ui_smoke.py tests/test_sim_layout.py tests/test_sim_panels.py -v
```
Expected: PASS (existing + new). Note `test_simapp_builds_docks` in the smoke suite asserts `set(win._docks.keys()) == set(DOCK_ORDER)` and `visible_docks == set(DOCK_ORDER)` — both still hold with 13 docks because `apply_overview` places all 13.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/app.py sim/ui/layout.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim/ui): wire deep-scrub + Events + Inspector docks (13 docks, reconstruct-on-pause)"
```

---

## Task 6: Render-verify, golden re-run, docs

**Files:**
- Scratch: a render script (scratchpad, not committed)
- Modify: `docs/superpowers/2026-07-07-simulator-extension-study.md`, this plan's banner
- Modify: memory `cf-fsnn-parallel-tracks.md`

- [ ] **Step 1: Golden bit-identity — full sim suite**

```
conda run -n cf_sim python -m pytest tests/test_sim_state.py tests/test_sim_backend.py tests/test_sim_stepper.py tests/test_sim_scenario.py tests/test_sim_events.py tests/test_sim_probe.py tests/test_sim_replay.py tests/test_sim_loop.py tests/test_sim_eventprop.py tests/test_sim_input_capture.py tests/test_sim_trajectory.py tests/test_sim_layout.py tests/test_sim_panels.py tests/test_sim_ui_smoke.py tests/test_sim_reconstruct.py -q
```
Expected: all green. The core is untouched → the stepper/backend/eventprop goldens stay bit-identical.

- [ ] **Step 2: Real-window render (deep-scrub + events + inspector)**

Write `scratchpad/render_3b_rest.py` (mirrors `render_scrub.py`): `QT_QPA_PLATFORM=windows`, build `SimApp`, select scenario 0, `_advance` past 500 ticks, `inject_brake()` partway, `_run_btn.setChecked(False)`, `_seek_to(brake_tick)`, `_on_neuron_selected(k)`, `processEvents`, `win.grab().save("sim_3b_rest.png")`. Run it, then `SendUserFile` the PNG with `display="render"` (keep the file — do NOT delete before sending).

- [ ] **Step 3: Update docs + memory**

- `docs/superpowers/2026-07-07-simulator-extension-study.md` §6: mark 3b.2 + 3b.3 (+ replay-beyond-buffer) DONE.
- This plan header: add a `**Status:** COMPLETE (<commit>)` banner line.
- Memory `cf-fsnn-parallel-tracks.md`: append a one-paragraph 3b-rest note (deep-scrub / Events / Inspector; 13 docks; golden preserved).

- [ ] **Step 4: Commit + push**

```bash
git add docs/superpowers/2026-07-07-simulator-extension-study.md docs/superpowers/plans/2026-07-09-scrub-events-inspector.md
git commit -m "docs(sim): mark Phase 3b (rest) complete — deep-scrub, events, inspector"
git push
```
Clean up stray PNGs after sending.

---

## Self-review

- **Spec coverage:** ① reconstruct (T1) · ② event-timeline (T2, click-seek-by-tick) · ③ inspector (T4) + graph highlight/click (T3) · deep-scrub trigger + scrub-source + 13 docks (T5) · golden + render + docs (T6). All spec sections mapped.
- **Placeholder scan:** none — every step has concrete code/commands.
- **Type consistency:** `reconstruct_history(champion, scenario, replaylog, upto)` used identically in test + app. Panels expose `set_cursor`/`update_frame`/`set_topology`/`neuron`/`highlight`/`set_on_seek`/`set_neuron` consistently across tests and app wiring. `_src_probe`/`_src_traj` set in `select_scenario` and both `_on_run_toggled` branches; read in `_buf_len`/`_render_at_cursor`/`_seek_to`/`_redraw_series`/`_on_neuron_selected`. Marks store the absolute tick; `_seek_to(tick)` maps tick→idx in the current source (robust to the pause-time source swap).
- **Ordering:** T1→T2→T3→T4 are independent leaf units; T5 depends on all four; T6 verifies. Each task ends green + committed.
