# Phase 3b (rest) — Deep-scrub, Event-timeline, Neuron-inspector — Design Spec

**Date:** 2026-07-09
**Branch/worktree:** `Simulator`
**Status:** approved design → implementation plan next

## Goal

Complete Phase 3b of the simulator-extension roadmap with the three remaining
capabilities, all building on the 3b.1 time-scrub cursor:

1. **Replay-beyond-buffer (deep-scrub)** — scrub the *whole* episode, not just the
   last 500 ticks held by the live ring buffer, by deterministically reconstructing
   the run from the `ReplayLog`.
2. **Event-timeline** — a dock showing injected events (`injector.log()`) as
   clickable marks; clicking one seeks the scrub cursor to that tick.
3. **Neuron-inspector** — clicking a hidden neuron in the net-graph opens a dock
   showing that neuron's `v_mem`/threshold/spike history plus its dominant
   connections, and highlights its fan-in/fan-out edges in the graph.

## Non-goals / invariants

- **Core frozen.** `sim/state.py`, `sim/stepper.py`, `sim/backend.py`,
  `sim/events.py`, `sim/probe.py`, `sim/eventprop_stepper.py` are NOT modified.
  Reconstruction only *reads* through the existing public API
  (`SimStepper.from_scenario`, `backend.read_probe()`, `ReplayLog.build_injector()`).
  The full golden sim suite must stay bit-identical after this work.
- No new physics, no new event verbs. `brake_leader` remains the only verb.
- No change to the live rolling-buffer behavior while running.

## Established facts this design relies on

- `EventInjector.log()` → `list[{"tick": int, "verb": str, "params": dict}]`.
- `ReplayLog(seed, events)` exists with `from_injector(seed, injector)`,
  `build_injector()`, `to_json`/`from_json`. Re-running is the "repeatable science
  bench" it was built for.
- `SimStepper.__init__` calls `reset()`, which resets `SimState` **and**
  `backend.reset()`. Therefore a fresh `SoftwareBackend(champion.model)` +
  `from_scenario(...)` + a `build_injector()` of the same logged events reproduces
  the run **bit-identically** (no per-step RNG; the scenario is a fixed array; the
  champion is fixed; `injector.tick` is deterministic given the same events).
- All time-series panels plot `setData(1D array)` → **X = buffer index** `[0..len)`,
  not the absolute tick. The scrub cursor is placed at `x = idx`. Event marks must
  therefore use the same X-convention: `buf_idx = position in frames() whose .t == T`.
- `AttributeProbe(capacity=N, sample_every=1)` and `TrajectoryBuffer(capacity=N)`
  both accept a capacity → a full-length reconstruction uses the *same types*, so
  the existing panels render it unchanged.
- `NeuronGraphPanel._nodes` is already a `pg.ScatterPlotItem` → nodes are naturally
  clickable via `sigClicked`.
- DT = 0.1 s; scenarios are ≤ 600 ticks (≤ 60 s). The live buffer (500) covers the
  last 50 s, so beyond-buffer scrub reaches at most the first ~10 s of a full run —
  cheap to reconstruct (≤ 600 deterministic steps, well under a second).

---

## Component ① — Reconstruction (deep-scrub foundation)

New pure module `sim/ui/reconstruct.py`:

```python
def reconstruct_history(champion, scenario, replaylog, upto):
    """Re-run the episode 0..upto deterministically into FULL-length buffers.

    Returns (probe, traj): an AttributeProbe(capacity=upto+1) and a
    TrajectoryBuffer(capacity=upto+1) filled with every tick, mirroring the live
    loop's record path exactly (same stepper.step(), same backend.read_probe()).
    Stops early on collision / end of scenario.
    """
```

Behavior:
- Build `backend = SoftwareBackend(champion.model)`,
  `injector = replaylog.build_injector()`,
  `stepper = SimStepper.from_scenario(backend, scenario, injector=injector)`.
- `probe = AttributeProbe(capacity=upto+1)`, `traj = TrajectoryBuffer(capacity=upto+1)`.
- Loop `upto+1` times (or until `stepper.st.collided or stepper.st.t >= stepper.N`):
  `r = stepper.step(); probe.record(r.t, backend.read_probe(), r.params); traj.record(r)`.
- Return `(probe, traj)`.

This mirrors `SimLoop.tick`'s record line exactly, guaranteeing bit-identity.

### Trigger — reconstruct automatically on pause (only when needed)

When the user pauses (`Run` toggled off):
- `t = head tick` = `self._probe.frames()[-1].t` (or `-1`/no-op if empty).
- **If the buffer has wrapped** (`t + 1 > self._probe.capacity`, i.e. early ticks
  were dropped) → `probe, traj = reconstruct_history(champ, scenario, ReplayLog.from_injector(seed, injector), t)`;
  set the scrub source to the reconstructed pair; redraw all series from it; cursor
  range becomes `[0 .. len-1]` = the whole episode-so-far.
- **Else** (buffer still holds everything) → scrub source = the live buffer
  (`self._probe`, `self._traj`); cursor range `[0 .. buf_len-1]`. Identical result,
  no reconstruction cost.

On `Run` (resume): scrub source reverts to the live buffer; panels redraw from it.

Seed is nominal (the run is deterministic regardless): use the scenario index.

### The "scrub source" indirection

The app gains `self._src_probe` / `self._src_traj`, the pair the panels currently
read from. Live = the ring buffers; paused-and-wrapped = the reconstructed
full-length pair. A single `_redraw_series(probe, traj)` helper repaints every
time-series panel + the event marks + the inspector trace from a given source.
`_render_at_cursor(idx)` reads the *stored* source for the graph/road/readout at
`idx`. The panels themselves are untouched — only the source they are handed changes.

---

## Component ② — Event-timeline (dock "Events")

New `EventTimelinePanel(QWidget)` in `sim/ui/panels.py`:

- A short pyqtgraph plot, X = source index (aligned with the time-series), a single
  lane at `y = 0`. Left axis hidden; bottom axis labelled `time (steps)`.
- Carries a cursor line (`_add_cursor` / `set_cursor`) like every other time-series.
- `set_on_seek(callback)` — the app registers a seek callback `cb(idx)`.
- `update_events(log, frames)`:
  - For each event, map `tick → idx` by locating the frame whose `.t == tick`
    (search the `frames` list). Drop events whose tick is not present (scrolled out
    of the source). Build one `ScatterPlotItem` of clickable marks at `(idx, 0)`,
    storing `idx` (and verb) in each point's `data`. Place a small `TextItem` verb
    label per mark.
  - Wire `ScatterPlotItem.sigClicked` → read the clicked point's `idx` → call the
    seek callback.

App wiring: `update_events(self._injector.log(), <source>.frames())` is called from
`_redraw_series`. The seek callback: **if running, pause first** (`_run_btn.setChecked(False)`),
then `_render_at_cursor(idx)` and sync the cursor slider to `idx`.

---

## Component ③ — Neuron-inspector (dock "Inspector") + graph highlight

### `NeuronGraphPanel` additions (same file)

- `sigNeuronClicked = Signal(int)` — emits the **hidden** index when a hidden node
  is clicked. Wire `self._nodes.sigClicked`: identify the clicked point's node
  index; if it lies in the hidden band (`n_in ≤ node < n_in + n_hid`), emit
  `node - n_in`; otherwise ignore (input/output clicks are no-ops for now).
- `highlight(hidden_index | None)`: draw the selected neuron's fan-in
  (input→neuron and recurrent→neuron edges) and fan-out (neuron→recurrent and
  neuron→output edges) as a distinct-coloured `GraphItem` overlay above the faint
  skeleton (fan-in one colour, fan-out another, matching the input/output label
  hues). `None` clears it. Adjacency is derived once from the topology already built
  in `set_topology` (store per-neuron in/out edge lists, or filter the existing
  `e_in`/`e_rec`/`e_out` by endpoint).
- The existing white spike-pathway overlay (`_active`) is unchanged; highlight is a
  separate, additional `GraphItem`.

### `NeuronInspectorPanel(QWidget)` (same file)

- Built once with the topology weights (`set_topology(w_in, w_rec, w_out)` or via
  constructor) so it can compute dominant connections.
- `set_neuron(i)` — selects hidden neuron `i` (stores it; updates the title
  `Inspector · hidden #i`; recomputes the dominant-connection readout from the
  weights: top-k `|w_in[i, :]|` over the 4 input names, top-k `|w_out[:, i]|` over
  the 5 param names).
- `update_frame(probe)` — plots the selected neuron's `v_mem` and `v_th_eff`
  (dashed) over the source history, plus spike marks (a scatter at the ticks where
  `spikes[i] > 0`). No-op if no neuron selected or no frames.
- `set_cursor(x)` — cursor line, like the other time-series.
- `neuron` property → the selected index or `None`.

App wiring: `self._netstate.sigNeuronClicked.connect(self._on_neuron_selected)`,
which calls `self._inspector.set_neuron(i)`, `self._netstate.highlight(i)`, and
`self._inspector.update_frame(self._src_probe)`.

---

## App integration & layout

- **DOCK_ORDER (13)**:
  `["Road","NetState","SpikeRate","v_mem","Trajectory","Safety","Events","Inspector","v0","T","s0","a","b"]`.
- `widgets` dict gains `"Events": self._timeline`, `"Inspector": self._inspector`.
- `_ts_panels` gains the timeline and the inspector (they carry cursor lines).
- **Presets** (`sim/ui/layout.py`): `neuro_debug` foregrounds
  NetState + SpikeRate + v_mem + Inspector + Events; `identificazione` adds Events
  next to the params; `overview` places all 13; `guida` unchanged (Road+Trajectory+Safety).
- View menu picks up the two new docks automatically (driven by `DOCK_ORDER`).
- `_on_run_toggled`, `_render_at_cursor`, `_on_cursor`, `_step_cursor`,
  `keyPressEvent` updated to use `self._src_probe`/`self._src_traj` and the new
  reconstruct-on-pause path. `select_scenario` resets the source to the live buffers
  and clears the inspector selection + graph highlight.

---

## File structure

- **Create** `sim/ui/reconstruct.py` — `reconstruct_history`.
- **Modify** `sim/ui/panels.py` — `EventTimelinePanel`, `NeuronInspectorPanel`;
  `NeuronGraphPanel` gains `sigNeuronClicked` + `highlight`.
- **Modify** `sim/ui/app.py` — scrub source, reconstruct-on-pause, event/neuron
  wiring, 13 docks.
- **Modify** `sim/ui/layout.py` — `DOCK_ORDER` + presets.
- **Tests** — `tests/test_reconstruct.py`, `tests/test_event_timeline.py`,
  `tests/test_inspector.py`; extend the net-graph test with `highlight`; extend the
  app integration test (pause-after->500-ticks scrub range, event click seek,
  neuron click populates inspector + highlight).

## Testing strategy (TDD)

1. **Reconstruction golden (the anchor).** Run a live sim > 500 ticks (buffer
   wraps); build `ReplayLog.from_injector`; `reconstruct_history(..., upto=t)`.
   Assert: reconstructed length == `t+1`; and for every live buffer frame, the
   reconstructed frame with the same `.t` has **array-equal** `spikes`, `v_mem`,
   `v_th_eff`, `params`, `input` (strict `assert_array_equal` — bit-identity). Also
   assert the reconstructed `traj.arrays()` matches the live overlap.
2. **Event-timeline.** Fake frames with ticks `100..599`; events at ticks `130` and
   `400` → marks at idx `30`, `300`; an event at tick `50` (out of range) dropped.
   Clicking a mark invokes the seek callback with the right idx.
3. **Inspector.** With a known weight matrix, `set_neuron(3)` lists the correct
   top-k input and output connection indices; `update_frame(probe)` sets the curve
   to neuron 3's `v_mem` series and marks its spike ticks.
4. **Graph highlight.** After `set_topology`, `highlight(5)` sets the overlay
   adjacency to exactly neuron 5's fan-in + fan-out edges; `highlight(None)` clears it.
5. **App integration (offscreen).** Advance > 500 ticks, pause → scrub range spans
   the whole episode (0..t) and reconstruction ran; scrub to idx 0 renders
   (`readout t=0`); click an event → cursor seeks; click a hidden neuron → inspector
   populated and graph highlighted; resume → source back to live buffer.
6. **Golden suite re-run.** The full sim golden suite stays bit-identical (core
   untouched; reconstruction is read-only).
7. **Render-verify.** Real `windows` Qt render of the two new docks + a deep-scrub
   past the buffer, PNG to the user.

## Implementation phases (for the plan)

- T1 `reconstruct_history` + golden test.
- T2 `EventTimelinePanel` + test.
- T3 `NeuronGraphPanel.highlight` + `sigNeuronClicked` + test.
- T4 `NeuronInspectorPanel` + test.
- T5 app + layout wiring (scrub source, reconstruct-on-pause, click wiring, 13
  docks) + integration test.
- T6 render-verify + golden suite re-run + docs/memory update.
