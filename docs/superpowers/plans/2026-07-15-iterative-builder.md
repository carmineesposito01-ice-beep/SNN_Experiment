# Iterative Builder Implementation Plan (cycle 4a)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every block its own behaviour as a bias on one neutral driver, and turn the right-hand panel into a composer where you build a block while seeing it.

**Architecture:** `Block` gains an optional `bias`; a pure `effective_style(block, neutral)` clamps `neutral + bias` onto the plane, and `materialise` calls it per block. The page's right half becomes a composer that materialises a one-block spec starting from the speed the previous blocks leave behind.

**Tech Stack:** Python 3, numpy, PySide6, pyqtgraph, pytest. Conda env `cf_sim`.

**Spec:** `docs/superpowers/specs/2026-07-15-iterative-builder-design.md` — read §The split first: the drag, `custom` and the advisory are **cycle 4b**, and that boundary was moved by a measurement, not a preference.

---

## Before you start

**Worktree:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator`, branch `Simulator`.

**Test runner** (⚠️ never `conda run -n cf_sim python -m pytest` — it intermittently crashes conda's plugin system):

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

**Full suite** = the 21 sim files + `tests/test_champion_io.py` (exact command in
`docs/superpowers/plans/2026-07-15-scenario-builder.md`). **Baseline: 224 passed.** No new test file.

**Hard rules:**
- **Frozen core**: `sim/{state,stepper,backend,probe,eventprop_stepper}.py` untouched. (`sim/events.py`
  was unfrozen in cycle 3 for the ramp fix; that was a one-off — do not touch it here.)
- **`utils/closed_loop_eval.py` is INVARIANT.** The reports run on it.
- **No numpy LAPACK** in `cf_sim` → OMP #15 hard abort.
- **Backward compatibility is a requirement, not a nicety**: cycle-3 specs and their JSON must keep
  working byte-identically. Tests 1 and 6 are the gate.
- Commits: conventional, **no `Co-Authored-By`**. Push freely.
- **Do NOT build** the drag, `custom`, or the advisory — cycle 4b owns them, and the spec explains why
  putting the advisory here would paint false red.

---

## File Structure

| File | Responsibility |
|---|---|
| `sim/scenario_spec.py` | `Block.bias` + `effective_style` + per-block dispatch in `materialise` + JSON. Stays pure. ~+30 lines. |
| `sim/ui/scenario_page.py` | The composer, the complete widgets, the neutral's control. The pad switches from editing the style to editing **this block's bias**, with the neutral as a second marker. Qt only. |
| `tests/test_sim_scenario_spec.py` | The bias, purely. |
| `tests/test_sim_ui_smoke.py` | The composer. |

Order: model → JSON → **one owner for the params** → composer → the neutral's control → budget → verification.

---

### Task 1: `Block.bias` and `effective_style`

**Files:**
- Modify: `sim/scenario_spec.py:28-32` (`Block`), `:133-148` (`materialise`)
- Test: `tests/test_sim_scenario_spec.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
# ---- per-block bias on one neutral driver --------------------------------------------------------

def test_unbiased_spec_is_byte_identical_to_cycle_3():
    """Regression on everything already built: bias=None must mean "the neutral", exactly."""
    from sim.scenario_spec import effective_style
    blocks = [Block("ramp", 200, {"to_v": 2.0}), Block("const", 200, {"v": 2.0}),
              Block("sine", 200, {"amp": 3.0, "period": 60})]
    s = _spec(blocks, style=NORMALE)
    for b in blocks:
        assert b.bias is None                                  # the default
        assert effective_style(b, NORMALE) is NORMALE          # and it IS the neutral, not a copy
    # the numbers cycle 3 produced, recomputed here from the same inputs
    vl = materialise(s, _PG, N=600).v_leader
    assert abs(vl[-1] - materialise(_spec(blocks, style=NORMALE), _PG, N=600).v_leader[-1]) < 1e-12


def test_bias_is_additive_on_the_neutral_not_absolute():
    """TEETH: the same bias on two different neutrals must give two different styles. An
    implementation that quietly treats the bias as an absolute passes 'it changed' and fails here."""
    from sim.scenario_spec import effective_style
    b = Block("ramp", 100, {"to_v": 2.0}, bias=(+1.0, +3.0))
    s1 = effective_style(b, LeaderStyle(1.0, 2.0))
    s2 = effective_style(b, LeaderStyle(2.0, 4.0))
    assert (s1.a_max, s1.b_max) == (2.0, 5.0)                  # 1+1, 2+3
    assert (s2.a_max, s2.b_max) == (3.0, 7.0)                  # 2+1, 4+3
    assert s1 != s2                                            # the neutral still matters


def test_bias_is_clamped_to_the_plane_not_rejected():
    from sim.scenario_spec import effective_style
    b = Block("ramp", 100, {"to_v": 2.0}, bias=(+99.0, +99.0))
    st = effective_style(b, NORMALE)                            # must not raise
    assert (st.a_max, st.b_max) == (4.0, 9.0)                  # pinned at the plane's edge
    b2 = Block("ramp", 100, {"to_v": 2.0}, bias=(-99.0, -99.0))
    st2 = effective_style(b2, NORMALE)
    assert (st2.a_max, st2.b_max) == (1.0, 1.0)


def test_a_bias_moves_only_its_own_block():
    """TEETH: per-block scope IS the feature. A bias that leaked into its neighbours would still
    'change the curve' and pass a naive test."""
    plain = [Block("ramp", 200, {"to_v": 2.0}), Block("ramp", 200, {"to_v": 18.0}),
             Block("ramp", 200, {"to_v": 5.0})]
    biased = [plain[0], Block("ramp", 200, {"to_v": 18.0}, bias=(+2.0, 0.0)), plain[2]]
    a = materialise(_spec(plain), _PG, N=600).v_leader
    b = materialise(_spec(biased), _PG, N=600).v_leader
    np.testing.assert_array_equal(a[:200], b[:200])            # block 1 untouched
    assert not np.array_equal(a[200:400], b[200:400])          # block 2 moved
    # block 3 starts from a different speed, so it cannot be byte-equal -- but its RATE must be the
    # neutral's, not the biased one: the bias did not leak.
    d = np.diff(b[400:])
    assert abs(d[d < -1e-9].min() - (-NORMALE.b_max * DT)) < 1e-9


def test_a_bias_on_a_preset_changes_nothing():
    """The cycle-3 invariant survives the new knob: a preset is verbatim, and _preset_samples does
    not even receive a style -- so this holds by construction. The test guards the construction."""
    from sim.scenario import scenario_library
    lib = {s.name: s for s in scenario_library(_PG, N=600, rng=np.random.default_rng(0),
                                               include_tail=True)}
    biased = materialise(_spec([Block("preset", 600, {"name": "stop_and_go"},
                                      bias=(+3.0, +5.0))]), _PG, N=600).v_leader
    np.testing.assert_array_equal(biased, lib["stop_and_go"].v_leader)
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q -k bias
```

Expected: FAIL — `TypeError: Block.__init__() got an unexpected keyword argument 'bias'`.

- [ ] **Step 3: Implement**

In `sim/scenario_spec.py`, extend `Block` (`:28-32`):

```python
@dataclass(frozen=True)
class Block:
    kind: str                 # "preset" | "const" | "ramp" | "sine"
    ticks: int                # the block's SLOT on the timeline -- NOT a ramp's duration
    params: dict              # {"name":…} | {"v":…} | {"to_v":…} | {"amp","period"}
    bias: tuple = None        # (da, db) m/s^2 ON the neutral; None = the neutral itself
```

Add `effective_style` right after `_check_style`:

```python
def effective_style(block, neutral):
    """The style this block actually runs with: neutral + bias, clamped to the plane.

    ADDITIVE on purpose. An absolute per-block style would leave N unrelated styles and no driver at
    all; with a bias there is ONE driver -- the neutral is the character, the bias is the circumstance
    ("in this stretch he is edgier than usual").

    Clamped, not rejected: the bias is a nudge, the plane is physics. A nudge that would leave the
    plane is pinned at the edge rather than raising -- the user is dragging a pad, not typing a config.
    """
    if block.bias is None:
        return neutral
    da, db = block.bias
    return LeaderStyle(a_max=float(np.clip(neutral.a_max + da, *A_MAX_RANGE)),
                       b_max=float(np.clip(neutral.b_max + db, *B_MAX_RANGE)))
```

And in `materialise` (`:142`), dispatch per block:

```python
        seg = _block_samples(block, v, effective_style(block, spec.style), params_gt, N)[: N - i]
```

⚠️ `_check_style(spec.style)` still validates the **neutral** only, and that is right: the neutral is
typed/chosen once and must be legal, while every effective style is clamped by construction.

⚠️ `materialise`'s docstring says "same spec, same v_leader, byte for byte" — still true. And
`spec.style` now means **the neutral**; update that docstring line to say so, since the field name
stays (renaming it would break the cycle-3 JSON for no gain).

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

Expected: PASS (17 existing + 5 new = 22).

- [ ] **Step 5: Commit**

```bash
git add sim/scenario_spec.py tests/test_sim_scenario_spec.py
git commit -m "feat(sim): per-block bias on one neutral driver

Block gains an optional bias (da, db) and effective_style clamps neutral + bias
onto the plane; materialise dispatches it per block.

Additive on purpose, and it is the user's reasoning: an absolute per-block style
would leave N unrelated styles and no driver -- with a bias there is ONE driver,
the neutral is the character and the bias is the circumstance.

bias=None means the neutral, so every cycle-3 spec materialises byte-identically.
Tests have teeth on the two ways this can go quietly wrong: a bias that leaks into
neighbouring blocks, and a bias treated as an absolute (same bias on two neutrals
must give two styles). A bias on a preset changes nothing -- _preset_samples never
receives a style, so it holds by construction; the test guards the construction."
```

---

### Task 2: JSON stays backward-compatible

**Files:**
- Modify: `sim/scenario_spec.py:151-173` (`to_json`, `from_json`)
- Test: `tests/test_sim_scenario_spec.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_cycle3_json_without_bias_still_loads():
    """A file written before the bias existed must load and mean "the neutral" -- no version field,
    no migration."""
    from sim.scenario_spec import from_json
    old = ('{"name":"vecchio","s_init":33.5,"v_init":21.0,'
           '"style":{"a_max":2.0,"b_max":4.0},'
           '"blocks":[{"kind":"ramp","ticks":600,"params":{"to_v":2.0}}]}')
    spec = from_json(old)
    assert spec.blocks[0].bias is None
    np.testing.assert_array_equal(
        materialise(spec, _PG, N=600).v_leader,
        materialise(_spec([Block("ramp", 600, {"to_v": 2.0})], style=LeaderStyle(2.0, 4.0)),
                    _PG, N=600).v_leader)


def test_json_omits_bias_when_absent_and_round_trips_it_when_present():
    from sim.scenario_spec import from_json, to_json
    plain = _spec([Block("ramp", 600, {"to_v": 2.0})])
    assert '"bias"' not in to_json(plain)                       # no noise in files that do not use it
    biased = _spec([Block("ramp", 300, {"to_v": 2.0}, bias=(+1.5, -2.0)),
                    Block("const", 300, {"v": 2.0})])
    back = from_json(to_json(biased))
    assert back == biased                                       # frozen dataclasses compare by value
    assert back.blocks[0].bias == (1.5, -2.0)                   # a TUPLE, not the JSON list
    np.testing.assert_array_equal(materialise(back, _PG, N=600).v_leader,
                                  materialise(biased, _PG, N=600).v_leader)
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q -k json
```

Expected: FAIL — `assert back == biased` fails, because `from_json` drops the bias and `to_json`
never wrote it.

- [ ] **Step 3: Implement**

In `sim/scenario_spec.py`:

```python
def _block_json(b):
    """A block as JSON. `bias` is omitted when absent, so files that do not use it stay exactly as
    cycle 3 wrote them -- backward compatibility without a version field."""
    d = {"kind": b.kind, "ticks": b.ticks, "params": b.params}
    if b.bias is not None:
        d["bias"] = list(b.bias)
    return d


def to_json(spec) -> str:
    """Declarative: a list of blocks, human-readable and diffable -- not 600 floats."""
    return json.dumps({
        "name": spec.name,
        "s_init": spec.s_init,
        "v_init": spec.v_init,
        "style": {"a_max": spec.style.a_max, "b_max": spec.style.b_max},   # the NEUTRAL
        "blocks": [_block_json(b) for b in spec.blocks],
    }, indent=2)


def from_json(text) -> ScenarioSpec:
    """Rejects an unknown block kind BY NAME rather than applying the spec partially. A missing
    `bias` means "the neutral": cycle-3 files load unchanged."""
    d = json.loads(text)
    blocks = []
    for b in d["blocks"]:
        if b["kind"] not in _KINDS:
            raise ValueError(f"unknown block kind: {b['kind']!r} (have: {_KINDS})")
        raw = b.get("bias")
        blocks.append(Block(kind=b["kind"], ticks=int(b["ticks"]), params=dict(b["params"]),
                            bias=tuple(float(x) for x in raw) if raw is not None else None))
    return ScenarioSpec(name=d["name"], blocks=tuple(blocks),
                        style=LeaderStyle(a_max=float(d["style"]["a_max"]),
                                          b_max=float(d["style"]["b_max"])),
                        s_init=float(d["s_init"]), v_init=float(d["v_init"]))
```

⚠️ `tuple(float(x) for x in raw)` — JSON gives a **list**, and `Block` is compared by value: a list
would make `from_json(to_json(s)) == s` fail even though the numbers match. That is exactly what the
round-trip test catches.

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_scenario_spec.py -q
```

Expected: PASS (24).

- [ ] **Step 5: Commit**

```bash
git add sim/scenario_spec.py tests/test_sim_scenario_spec.py
git commit -m "feat(sim): bias round-trips through JSON, and cycle-3 files still load

bias is omitted when absent, so a file that does not use it is byte-identical to
what cycle 3 wrote -- backward compatibility with no version field and no migration.
from_json rebuilds it as a TUPLE: JSON hands back a list, and Block compares by
value, so a list would break the round-trip while looking right."
```

---

### Task 3: The params get ONE owner — the widgets

**Files:**
- Modify: `sim/ui/scenario_page.py` (`ScenarioPage.__init__`, `_params_for`)
- Test: `tests/test_sim_ui_smoke.py` (append)

⚠️ **Why this task exists.** The first draft of this plan kept the composed block's params in a
`_composer_params` dict *beside* the widgets. Two owners for one state — the exact defect cycle 3 paid
for (the pad that redrew the curve without moving the dot). It also crashed: MEASURED
`KeyError: 'to_v'` when `compose_new` set the new kind while the dict still held the old kind's params.

The fix is to delete the dict and DERIVE the params from the widgets. That only works if the widgets
can represent every param — and MEASURED, they cannot:

| block reopened | what Apply writes back | |
|---|---|---|
| `preset {"name": "hard_brake"}` | `{"name": "stop_and_go"}` | **lost** |
| `sine {"amp": 5.0, "period": 60}` | `{"amp": 2.5, "period": 80}` | **lost** |

`_params_for` hardcodes the preset name and the sine period. So **1 of the 9 library presets is
reachable from the builder** — which quietly halves the original request ("combinazione di quelli
esistenti"): today you can only combine `stop_and_go` with itself.

- [ ] **Step 1: Write the failing tests**

```python
def _page():
    from sim.ui.scenario_page import ScenarioPage
    return ScenarioPage(params_gt=np.array([30.0, 1.5, 2.0, 1.5, 1.5]), N=600)


def _spec3(blocks, a=2.0, b=4.0):
    from sim.scenario_spec import LeaderStyle, ScenarioSpec
    return ScenarioSpec(name="x", blocks=tuple(blocks), style=LeaderStyle(a, b),
                        s_init=33.5, v_init=21.0)


def test_every_library_preset_is_reachable_from_the_builder(qapp):
    """MEASURED before this task: _params_for hardcoded "stop_and_go", so 1 preset of 9 was
    reachable and 'combine the existing scenarios' meant combining one with itself."""
    from sim.scenario import scenario_library
    page = _page()
    names = sorted(s.name for s in scenario_library(page._params_gt, N=600,
                                                    rng=np.random.default_rng(0), include_tail=True))
    have = sorted(page._preset.itemText(i) for i in range(page._preset.count()))
    assert have == names, f"{len(have)} presets offered of {len(names)} in the library"
    page._kind.setCurrentText("preset")
    page._preset.setCurrentText("hard_brake")
    assert page._params_for("preset") == {"name": "hard_brake"}     # not the hardcoded default


def test_widgets_can_represent_every_kind_s_params(qapp):
    """TEETH: this is what lets the params have ONE owner. A kind whose params the widgets cannot
    express would force a shadow dict back into existence -- and silently rewrite blocks on Apply."""
    page = _page()
    for kind, params in [("preset", {"name": "cut_in"}), ("const", {"v": 12.0}),
                         ("ramp", {"to_v": 3.5}), ("sine", {"amp": 5.0, "period": 60})]:
        page._load_into_widgets(kind, 200, params, None)
        assert page._params_for(kind) == params, f"{kind}: {page._params_for(kind)} != {params}"


def test_changing_any_input_redraws_the_composer(qapp):
    """'Build the piece while you see it' means every input is live -- not just the pad."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 300, {"to_v": 2.0})]))
    page.compose_new("ramp", ticks=300, params={"to_v": 18.0})
    for widget_change in (lambda: page._value.setValue(4.0),
                          lambda: page._ticks.setValue(200),
                          lambda: page._kind.setCurrentText("const")):
        before = page._composer_curve.getOriginalDataset()[1].copy()
        widget_change()
        after = page._composer_curve.getOriginalDataset()[1]
        assert not np.array_equal(before, after), "an input changed and the preview did not"
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "preset_is_reachable or represent_every_kind or redraws_the_composer"
```

Expected: FAIL — `AttributeError: 'ScenarioPage' object has no attribute '_preset'`.

- [ ] **Step 3: Implement**

In `sim/ui/scenario_page.py`, import the library and the kinds at the top:

```python
from sim.scenario import scenario_library
from sim.scenario_spec import (A_MAX_RANGE, B_MAX_RANGE, _KINDS, Block, LeaderStyle, ScenarioSpec,
                               materialise)
```

In `ScenarioPage.__init__`, replace the controls row (`:70-82`):

```python
        self._loading = False        # re-entrancy guard: setValue() fires valueChanged
        controls = QHBoxLayout()
        self._kind = QComboBox()
        self._kind.addItems(list(_KINDS))
        self._ticks = QSpinBox(); self._ticks.setRange(1, 600); self._ticks.setValue(150)
        self._value = QDoubleSpinBox(); self._value.setRange(0.0, 40.0); self._value.setValue(5.0)
        self._preset = QComboBox()
        self._preset.addItems(sorted(s.name for s in scenario_library(
            self._params_gt, N=self._N, rng=np.random.default_rng(0), include_tail=True)))
        self._period = QSpinBox(); self._period.setRange(4, 600); self._period.setValue(80)
        self._add = QPushButton("Aggiungi blocco"); self._add.clicked.connect(self._on_add)
        self._del = QPushButton("Rimuovi"); self._del.clicked.connect(self._on_del)
        self._use = QPushButton("Usa questo scenario"); self._use.clicked.connect(self._on_use)
        self._value_lbl, self._period_lbl = QLabel("valore"), QLabel("periodo")
        for w in (QLabel("blocco"), self._kind, QLabel("durata"), self._ticks,
                  self._preset, self._value_lbl, self._value, self._period_lbl, self._period,
                  self._add, self._del, self._use):
            controls.addWidget(w)
        controls.addStretch(1)
        root.addLayout(controls)

        # every input is live: "build the piece while you see it" is false if only the pad redraws
        self._kind.currentTextChanged.connect(self._on_kind_changed)
        for sig in (self._ticks.valueChanged, self._value.valueChanged,
                    self._period.valueChanged, self._preset.currentTextChanged):
            sig.connect(self._refresh_composer)
```

⚠️ `scenario_library` is already called on **every** `materialise` with a preset block
(`_preset_samples`), inside the measured 3.68 ms — so calling it once at startup costs nothing new.

Replace `_params_for` (`:129-132`) and add the kind-driven visibility:

```python
    def _params_for(self, kind):
        """The params of the block being composed, DERIVED from the widgets.

        The widgets are the only owner. A shadow dict beside them was tried and it did what two
        owners always do: it crashed (new kind + old params) and it silently rewrote a reopened
        block's params on Apply.
        """
        v = float(self._value.value())
        return {"preset": {"name": self._preset.currentText()},
                "const": {"v": v},
                "ramp": {"to_v": v},
                "sine": {"amp": v, "period": int(self._period.value())}}[kind]

    def _on_kind_changed(self, kind):
        """Show only the inputs this kind actually has: an input that does nothing is a lie."""
        is_preset, is_sine = kind == "preset", kind == "sine"
        self._preset.setVisible(is_preset)
        for w in (self._value_lbl, self._value):
            w.setVisible(not is_preset)
        for w in (self._period_lbl, self._period):
            w.setVisible(is_sine)
        self._value_lbl.setText("ampiezza" if is_sine else "valore")
        self._refresh_composer()

    def _load_into_widgets(self, kind, ticks, params, bias):
        """Write a block INTO the widgets -- they are the owner, so this is how a block is opened.

        Guarded: each setValue/setCurrentText fires its signal, and refreshing four times while the
        widgets are half-written is waste, not a bug (every intermediate state is still VALID,
        because the params are derived, never stored).
        """
        self._loading = True
        try:
            self._kind.setCurrentText(kind)
            self._ticks.setValue(int(ticks))
            if kind == "preset":
                self._preset.setCurrentText(str(params["name"]))
            elif kind == "sine":
                self._value.setValue(float(params["amp"]))
                self._period.setValue(int(params["period"]))
            else:
                self._value.setValue(float(params["v" if kind == "const" else "to_v"]))
            na, nb = self._pad._neutral
            self._pad.set_point(na + (bias[0] if bias else 0.0),
                                nb + (bias[1] if bias else 0.0), emit=False)
        finally:
            self._loading = False
        self._on_kind_changed(kind)          # visibility + one refresh, once, at the end
```

⚠️ `sine`'s amplitude was `0.5 * value`; it is now the value itself. The halving was an arbitrary
indirection that made `amp=5.0` unrepresentable (it needed `value=10.0`) — one number, one meaning.

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "preset_is_reachable or represent_every_kind or redraws_the_composer"
```

Expected: PASS. These call `compose_new` / `_refresh_composer` / `_pad._neutral`, which Task 4 builds —
so **run Tasks 3 and 4 as one red→green cycle** rather than leaving stubs behind. Task 3 is split out
because it is a distinct decision with its own commit, not because it lands alone.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/scenario_page.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): the composed block's params have one owner -- the widgets

Derived from the widgets, never stored beside them. The shadow dict this replaces
did what two owners always do: it crashed (KeyError when the kind changed before
the params did) and it silently rewrote a reopened block on Apply.

One owner forces the widgets to represent every param, which is how this fixes a
measured cycle-3 limitation: the preset name was hardcoded, so 1 of the 9 library
presets was reachable and 'combine the existing scenarios' meant combining
stop_and_go with itself. The sine's period was hardcoded at 80 the same way.

Every input is now live, not just the pad -- 'build the piece while you see it' is
false if changing the duration does nothing."
```

---

### Task 4: The block composer

**Files:**
- Modify: `sim/ui/scenario_page.py` (`StylePad` + `ScenarioPage`)
- Test: `tests/test_sim_ui_smoke.py` (append + rewrite two cycle-3 tests)

- [ ] **Step 1: Write the failing tests**

```python
def test_composer_preview_starts_where_the_previous_blocks_left_off(qapp):
    """TEETH: this is the claim the whole composer rests on. A preview that always started from
    v_init would look plausible and be a lie for every block after the first."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 300, {"to_v": 2.0})]))
    page.compose_new("ramp", ticks=300, params={"to_v": 18.0})
    small = page._composer_curve.getOriginalDataset()[1]
    assert abs(small[0] - 2.0) < 0.5           # starts from ~2 m/s (where block 1 ends), not 21
    assert small[-1] > 15.0                    # and climbs toward 18


def test_composer_preview_equals_the_scenario_slice_after_add(qapp):
    """TEETH: what you judged is what you get."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 300, {"to_v": 2.0})]))
    page.compose_new("ramp", ticks=300, params={"to_v": 18.0})
    small = page._composer_curve.getOriginalDataset()[1].copy()
    page._on_add()
    full = page._curve.getOriginalDataset()[1]
    np.testing.assert_array_equal(full[300:600], small)


def test_composer_pad_edits_the_bias_and_shows_the_neutral(qapp):
    from sim.scenario_spec import Block, LeaderStyle
    page = _page()
    page.set_spec(_spec3([Block("ramp", 600, {"to_v": 2.0})], a=2.0, b=4.0))
    page.compose_new("ramp", ticks=300, params={"to_v": 2.0})
    page._pad.set_point(3.0, 7.0)               # the ABSOLUTE point the user drops
    assert page._composer_bias() == (1.0, 3.0)  # stored as a bias off the neutral (2,4)
    assert page._pad._neutral == (2.0, 4.0)     # and the neutral is on screen as a second marker
    assert page._spec.style == LeaderStyle(2.0, 4.0)   # the pad did NOT move the driver


def test_reopening_a_row_round_trips_the_block_exactly(qapp):
    """TEETH: MEASURED to corrupt before Task 3 -- a reopened preset came back as stop_and_go and a
    sine came back with period 80. Reopen-then-Apply with no edit must be the identity."""
    from sim.scenario_spec import Block
    page = _page()
    blocks = [Block("ramp", 150, {"to_v": 2.0}),
              Block("preset", 150, {"name": "hard_brake"}),
              Block("sine", 150, {"amp": 5.0, "period": 60}, bias=(1.0, 2.0)),
              Block("const", 150, {"v": 8.0})]
    page.set_spec(_spec3(blocks))
    for i, original in enumerate(blocks):
        page._on_row_selected(i)
        assert page._composer_kind() == original.kind
        assert page._composer_bias() == original.bias
        page._on_add()                                    # Add acts as Apply on an open row
        assert len(page._spec.blocks) == 4                # replaced, not appended
        assert page._spec.blocks[i] == original, f"row {i}: {page._spec.blocks[i]} != {original}"


def test_composer_does_not_break_the_existing_flow(qapp):
    win = SimApp(CHAMP)
    before = win._selector.count()
    win.set_mode(3)
    win._scenario_page._on_use()
    assert win._selector.count() == before + 1
    win._advance(0.2)
```

**And rewrite the two cycle-3 tests whose MEANING changed** (`:639` and `:675`). Read them first: they
encode "the pad moves the scenario's style", which is precisely what this cycle replaces. Do not delete
the lesson — move it onto the new state:

```python
def test_scenario_page_style_pad_redraws_the_composer_not_the_scenario(qapp):
    """Cycle 3: the pad WAS the scenario's style. Now it is the composed block's bias, so the
    scenario must NOT move until Add -- and the composer must."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 600, {"to_v": 2.0})]))
    page.compose_new("ramp", ticks=300, params={"to_v": 18.0})
    scen_before = page._curve.getOriginalDataset()[1].copy()
    comp_before = page._composer_curve.getOriginalDataset()[1].copy()
    page.set_style(4.0, 9.0)                              # what dragging the pad calls
    np.testing.assert_array_equal(page._curve.getOriginalDataset()[1], scen_before)
    assert not np.array_equal(page._composer_curve.getOriginalDataset()[1], comp_before)


def test_scenario_page_pad_never_disagrees_with_the_state(qapp):
    """TEETH, carried over from cycle 3 where set_style redrew the curve WITHOUT moving the dot --
    found by looking at a render, not by a test. The state it mirrors is now the BIAS."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 600, {"to_v": 2.0})], a=1.4, b=8.4))
    page.compose_new("ramp", ticks=300, params={"to_v": 2.0})
    page.set_style(3.6, 1.6)
    assert (page._pad._a, page._pad._b) == (3.6, 1.6)               # the dot followed
    assert page._composer_bias() == (2.2, -6.8)                     # 3.6-1.4, 1.6-8.4
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "composer or reopening or pad_never"
```

Expected: FAIL — `AttributeError: 'ScenarioPage' object has no attribute 'compose_new'`.

- [ ] **Step 3: Implement**

**4a — the pad learns about the neutral.** In `StylePad.__init__`, after `self._dot` is added:

```python
        self._neutral = (2.0, 4.0)
        self._neutral_dot = pg.ScatterPlotItem(size=9, brush=pg.mkBrush(120, 120, 120, 110),
                                               pen=pg.mkPen("#6a6a6a", width=1))
        self.addItem(self._neutral_dot)
        self._neutral_dot.setData([self._neutral[0]], [self._neutral[1]])
```

and a setter next to `set_point`:

```python
    def set_neutral(self, a, b):
        """The driver's character, drawn dimmer: the bright dot is where THIS block sits, and the
        distance between the two dots IS the bias."""
        self._neutral = (float(a), float(b))
        self._neutral_dot.setData([self._neutral[0]], [self._neutral[1]])
```

Clamp inside `set_point`, so the bright dot can never leave the plane when it is placed by arithmetic
(`neutral + bias`) rather than by a click:

```python
    def set_point(self, a, b, emit=True):
        """emit=False syncs the dot WITHOUT re-announcing: the page calls it when the point changed
        from elsewhere, so the dot never disagrees with the curve. Announcing there would loop.

        Clamped here, not at the callers: the point is now also placed as neutral+bias, and a bias
        that would leave the plane is pinned at the edge (effective_style clamps identically).
        """
        self._a = float(np.clip(a, *A_MAX_RANGE))
        self._b = float(np.clip(b, *B_MAX_RANGE))
        self._dot.setData([self._a], [self._b])
        if emit:
            self.sigStyleChanged.emit(self._a, self._b)
```

**4b — the composer.** In `ScenarioPage.__init__`, after `self._pad` is wired into `mid`:

```python
        self._composer_row = None            # the timeline row being edited, or None for a new block
        self._composer_plot = pg.PlotWidget()
        self._composer_plot.setLabel("left", "blocco", units="m/s")
        self._composer_plot.setLabel("bottom", "tick del blocco")
        self._composer_plot.showGrid(x=False, y=True, alpha=0.2)
        self._composer_curve = self._composer_plot.plot(pen=pg.mkPen("#e8871e", width=2))
        mid.addWidget(self._composer_plot, stretch=1)
        self._list.currentRowChanged.connect(self._on_row_selected)
```

and the composer's methods:

```python
    # ---- composer ----
    def _composer_kind(self):
        return self._kind.currentText()

    def _composer_bias(self):
        """The pad holds an ABSOLUTE point; the model stores the distance from the neutral. Showing
        the absolute is what one reasons about ("this block brakes at 7"); storing the difference is
        what keeps ONE driver ("...which is 3 more than his usual")."""
        na, nb = self._pad._neutral
        da, db = round(self._pad._a - na, 6), round(self._pad._b - nb, 6)
        return None if (da == 0.0 and db == 0.0) else (da, db)

    def _composer_block(self):
        kind = self._composer_kind()
        return Block(kind, int(self._ticks.value()), self._params_for(kind),
                     bias=self._composer_bias())

    def _start_speed(self, upto):
        """The speed the first `upto` blocks leave behind -- the composer's only coupling to the
        timeline, and what makes the small preview honest instead of decorative."""
        if self._spec is None:
            return 21.0
        if upto <= 0:
            return float(self._spec.v_init)
        prefix = ScenarioSpec(name="_", blocks=self._spec.blocks[:upto], style=self._spec.style,
                              s_init=self._spec.s_init, v_init=self._spec.v_init)
        used = sum(b.ticks for b in prefix.blocks)
        return float(materialise(prefix, self._params_gt,
                                 max(1, min(used, self._N))).v_leader[-1])

    def compose_new(self, kind, ticks, params, bias=None):
        """Open a NEW block in the composer. Nothing reaches the timeline until Add."""
        self._composer_row = None
        self._load_into_widgets(kind, ticks, params, bias)

    def _refresh_composer(self, *_):
        """Materialise a ONE-block spec starting from the speed the previous blocks leave behind."""
        if self._loading or self._spec is None:
            return
        blk = self._composer_block()
        upto = self._composer_row if self._composer_row is not None else len(self._spec.blocks)
        one = ScenarioSpec(name="_", blocks=(blk,), style=self._spec.style,
                           s_init=self._spec.s_init, v_init=self._start_speed(upto))
        self._composer_curve.setData(materialise(one, self._params_gt, blk.ticks).v_leader)

    def _on_row_selected(self, i):
        if self._spec is None or i < 0 or i >= len(self._spec.blocks):
            return
        b = self._spec.blocks[i]
        self._composer_row = i
        self._load_into_widgets(b.kind, b.ticks, b.params, b.bias)
```

⚠️ `_refresh_composer(self, *_)` swallows the argument Qt's `valueChanged(int)` /
`currentTextChanged(str)` pass — it is connected directly to them.

Rewire `set_style` — the pad now edits the block, not the driver:

```python
    def set_style(self, a_max, b_max):
        """The pad moved: that is THIS BLOCK's point, so only the composer redraws. The scenario's
        neutral is unchanged -- it has its own control."""
        self._pad.set_point(a_max, b_max, emit=False)   # the dot must never disagree with the state
        self._refresh_composer()
```

`set_spec` seeds the neutral and opens a fresh block:

```python
    def set_spec(self, spec):
        self._spec = spec
        self._pad.set_neutral(spec.style.a_max, spec.style.b_max)
        self._refresh_list()
        self._refresh()
        self.compose_new(self._kind.currentText(), int(self._ticks.value()),
                         self._params_for(self._kind.currentText()))
```

and `_on_add` appends **or replaces**:

```python
    def _on_add(self):
        if self._spec is None:
            return
        blk = self._composer_block()
        blocks = list(self._spec.blocks)
        if self._composer_row is None:
            blocks.append(blk)
        else:
            blocks[self._composer_row] = blk          # Add acts as Apply on an open row
        self._spec = ScenarioSpec(name=self._spec.name, blocks=tuple(blocks),
                                  style=self._spec.style, s_init=self._spec.s_init,
                                  v_init=self._spec.v_init)
        self._composer_row = None
        self._refresh_list()
        self._refresh()
        self._refresh_composer()                      # the start speed moved
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/scenario_page.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): the right panel becomes a block composer

Build the piece while you see it: the 2-D pad now edits THIS block's bias, with the
neutral drawn dimmer -- the distance between the two dots IS the bias. The pad still
shows an ABSOLUTE point because that is what one reasons about ('this block brakes at
7'); the model stores the difference, which is what keeps one driver.

The small preview materialises a one-block spec starting from the speed the previous
blocks leave behind: that coupling is the only thing that makes it honest instead of
decorative, and a test pins that the slice you judged is the slice you get.

Two cycle-3 tests changed meaning, not lesson: the pad moved the scenario's style and
now moves the block's bias, so they assert the scenario does NOT move until Add. The
'dot never disagrees' teeth carry over onto the bias."
```

---

### Task 5: The neutral gets its own control

**Files:**
- Modify: `sim/ui/scenario_page.py`
- Test: `tests/test_sim_ui_smoke.py` (append)

⚠️ **Why this task exists.** The spec puts it in scope (§Scope IN, point 4) and the first draft of this
plan had no task for it — the self-review checked the spec's 8 tests and never read its Scope. Without
it the pad edits the bias and **nothing edits the neutral**: the driver's character becomes
unreachable, frozen at whatever `set_spec` passed in.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_neutral_has_its_own_control(qapp):
    """The pad edits the block's bias; without this the driver's character is unreachable."""
    from sim.scenario_spec import Block, LeaderStyle
    page = _page()
    page.set_spec(_spec3([Block("ramp", 600, {"to_v": 2.0})], a=2.0, b=4.0))
    before = page._curve.getOriginalDataset()[1].copy()
    page._neu_a.setValue(4.0)
    assert page._spec.style == LeaderStyle(4.0, 4.0)      # the driver really changed
    assert page._pad._neutral == (4.0, 4.0)               # and the dim marker followed
    assert not np.array_equal(page._curve.getOriginalDataset()[1], before)   # so did the scenario


def test_moving_the_neutral_keeps_the_bias_and_carries_the_block(qapp):
    """TEETH: the bias is stored as a DIFFERENCE, so moving the neutral must move every block with
    it -- that is what "one driver" means. An implementation that kept the absolute would silently
    turn the bias into a different number."""
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 600, {"to_v": 2.0})], a=2.0, b=4.0))
    page.compose_new("ramp", ticks=300, params={"to_v": 18.0}, bias=(1.0, 2.0))
    assert (page._pad._a, page._pad._b) == (3.0, 6.0)     # neutral + bias
    page._neu_a.setValue(1.0)                             # the driver gets calmer
    assert page._composer_bias() == (1.0, 2.0)            # the CIRCUMSTANCE is unchanged...
    assert page._pad._a == 2.0                            # ...so the block's absolute followed: 1+1
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k neutral
```

Expected: FAIL — `AttributeError: 'ScenarioPage' object has no attribute '_neu_a'`.

- [ ] **Step 3: Implement**

In `ScenarioPage.__init__`, in the controls row (before `self._add`):

```python
        self._neu_a = QDoubleSpinBox(); self._neu_a.setRange(*A_MAX_RANGE)
        self._neu_b = QDoubleSpinBox(); self._neu_b.setRange(*B_MAX_RANGE)
        self._neu_a.setSingleStep(0.1); self._neu_b.setSingleStep(0.1)
        self._neu_a.setValue(2.0); self._neu_b.setValue(4.0)
        for w in (self._neu_a, self._neu_b):
            w.setToolTip("il neutro del guidatore: il pad muove il bias di QUESTO blocco")
```

adding `QLabel("neutro a/b"), self._neu_a, self._neu_b` to the widget loop, and wiring after it:

```python
        for sig in (self._neu_a.valueChanged, self._neu_b.valueChanged):
            sig.connect(self._on_neutral_changed)
```

and the method:

```python
    def _on_neutral_changed(self, *_):
        """The driver's character moved. The bias is a DIFFERENCE, so every block moves with him --
        that is exactly what having one driver means, and it is why the block's absolute point on
        the pad has to follow rather than stay put.
        """
        if self._loading or self._spec is None:
            return
        bias = self._composer_bias()                       # read BEFORE the neutral moves under it
        a, b = float(self._neu_a.value()), float(self._neu_b.value())
        self._spec = ScenarioSpec(name=self._spec.name, blocks=self._spec.blocks,
                                  style=LeaderStyle(a, b), s_init=self._spec.s_init,
                                  v_init=self._spec.v_init)
        self._pad.set_neutral(a, b)
        self._pad.set_point(a + (bias[0] if bias else 0.0),
                            b + (bias[1] if bias else 0.0), emit=False)
        self._refresh()
        self._refresh_composer()
```

and make `set_spec` seed the two spinboxes without re-entering (add inside its body, before
`_refresh_list`):

```python
        self._loading = True
        self._neu_a.setValue(spec.style.a_max)
        self._neu_b.setValue(spec.style.b_max)
        self._loading = False
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/scenario_page.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): the neutral gets its own control

The pad now edits the block's bias, so without this the driver's character is
unreachable -- frozen at whatever set_spec passed in. The spec had it in scope and
the plan's self-review missed it: it checked the spec's tests and never read its Scope.

Moving the neutral carries every block with it, because the bias is stored as a
difference. That is what one driver means, and a test has teeth on it: the block's
absolute point on the pad must follow the neutral while its bias stays put."
```

---

### Task 6: The refresh still fits in a frame

**Files:**
- Test: `tests/test_sim_ui_smoke.py` (append)

⚠️ **Why this is a task and not a footnote.** The composer adds materialise calls to a budget that was
already measured tight: `materialise` costs **3.68 ms** and the whole frame has **16.7 ms**.
`_refresh_composer` calls it **twice** (`_start_speed` on the prefix, then the one-block preview) and
`_on_neutral_changed` adds `_refresh` on top. That is ~11 ms of numpy before pyqtgraph draws anything.
It may fit — but "may" is exactly the word that has been wrong all session.

- [ ] **Step 1: Write the test**

```python
def test_composer_refresh_fits_in_a_frame(qapp):
    """The composer adds materialise calls to an already-tight budget: 3.68 ms each, 16.7 ms a frame,
    and a refresh does up to three (prefix + block + full scenario). Assert the PEAK, not the mean --
    it is the peak the eye sees as a stutter."""
    import time
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("preset", 150, {"name": "stop_and_go"}),
                          Block("ramp", 150, {"to_v": 2.0}),
                          Block("const", 150, {"v": 2.0}),
                          Block("sine", 150, {"amp": 5.0, "period": 60})]))
    page.compose_new("ramp", ticks=150, params={"to_v": 18.0})
    for _ in range(3):
        page.set_style(3.0, 7.0)                      # warm up
    ts = []
    for k in range(40):
        a = 1.0 + 3.0 * (k / 39.0)
        t0 = time.perf_counter()
        page.set_style(a, 5.0)                        # what dragging the pad calls, live
        ts.append((time.perf_counter() - t0) * 1000)
    peak = max(ts)
    assert peak < 16.7, f"composer refresh peaks at {peak:.2f} ms, over the 60 fps budget"
```

- [ ] **Step 2: Run it**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k fits_in_a_frame
```

Expected: PASS.

**If it FAILS, do not delete the test and do not raise the number.** The fix is to stop recomputing
what has not changed: `_start_speed` only depends on the blocks *before* the composed one, so it can be
cached and invalidated when the timeline changes — dragging the pad does not move the prefix. Measure
again after.

- [ ] **Step 3: Commit**

```bash
git add tests/test_sim_ui_smoke.py
git commit -m "test(sim): the composer refresh must fit in a frame

The composer adds materialise calls to a budget already measured tight: 3.68 ms
each against 16.7 ms a frame, and one refresh does up to three (prefix + block +
full scenario). Asserts the PEAK, which is what the eye sees as a stutter."
```

---

### Task 7: Full verification and docs

**Files:**
- Modify: `document/SIMULATOR_SESSION_RESUME.md`

- [ ] **Step 1: Run the full suite** — the 21 sim files + `tests/test_champion_io.py`.

Expected: **PASS**, 224 baseline + the new ones (T1: 5, T2: 2, T3: 3, T4: 5, T5: 2, T6: 1 → expect
**242**; two cycle-3 tests are rewritten, not added). Write the **real** number everywhere, never the
predicted one.

- [ ] **Step 2: Verify the frozen core and the invariant source**

```bash
git diff --stat origin/Simulator -- sim/state.py sim/stepper.py sim/backend.py sim/probe.py sim/eventprop_stepper.py sim/events.py utils/closed_loop_eval.py
```

Expected: **empty**.

- [ ] **Step 3: Prove backward compatibility on a real cycle-3 file**

Write to your scratchpad a script that builds a cycle-3 spec (no bias), `to_json`s it, checks the text
contains no `"bias"`, `from_json`s it back, and asserts `materialise` is byte-identical. Run it with the
env python. This is the claim that protects everything already built.

- [ ] **Step 4: Render-verify — actually look at it**

`QT_QPA_PLATFORM=windows` (offscreen renders text as tofu), build `SimApp`, `set_mode(3)`,
`compose_new("ramp", 300, {"to_v": 2.0})`, move the pad off the neutral, grab and **Read the PNG**.
Check: two dots on the pad (bright = block, dim = neutral), the composer curve starting from the right
speed, the scenario curve below, and — with kind=`preset` — the preset combo visible and the value box
gone.

- [ ] **Step 5: Update the resume and commit**

Mark cycle 4a done with the **real** test count; note that `ScenarioSpec.style` now means the neutral,
and that the builder now reaches all 9 presets (it reached 1). Leave cycle 4b (drag + `custom` +
advisory) as the next open item.

```bash
git add document/SIMULATOR_SESSION_RESUME.md
git commit -m "docs(sim): resume — cycle 4a (iterative builder) done"
git push origin Simulator
```

---

## Notes for whoever executes this

- **The bias is a difference, the pad shows a point.** If you find yourself storing an absolute per
  block, you have removed the driver: that is the one thing this cycle exists to preserve.
- **`bias=None` must stay byte-identical to cycle 3.** It is not a nicety — scenarios and JSON already
  exist. Task 1's first test and Task 2's are the gate.
- **One owner for the params: the widgets.** A dict beside them was tried in the first draft of this
  plan and MEASURED to crash (`KeyError: 'to_v'`) and to silently rewrite reopened blocks. If a param
  cannot be expressed by a widget, add the widget — do not add a dict.
- **Do not add the advisory here.** It looks trivial (`diff(v)/DT > style`) and it is measured to be
  false red on presets: `cut_in` demands −75 m/s² because it is a *different vehicle*, and `following`
  "violates" in 503 of 599 steps because of its noise. It belongs with the drag, in 4b.
- **`_preset_samples` never receives a style**, so a bias cannot touch a preset by construction. Keep it
  that way: the test guards the construction, not a convention.
