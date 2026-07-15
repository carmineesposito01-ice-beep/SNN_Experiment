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
| `sim/ui/scenario_page.py` | The composer. The pad switches from editing the style to editing **this block's bias**, with the neutral as a second marker. Qt only. |
| `tests/test_sim_scenario_spec.py` | The bias, purely. |
| `tests/test_sim_ui_smoke.py` | The composer. |

Order: model → JSON → composer → verification.

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

### Task 3: The block composer

**Files:**
- Modify: `sim/ui/scenario_page.py` (whole page: `StylePad` + `ScenarioPage`)
- Test: `tests/test_sim_ui_smoke.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def _page():
    from sim.ui.scenario_page import ScenarioPage
    return ScenarioPage(params_gt=np.array([30.0, 1.5, 2.0, 1.5, 1.5]), N=600)


def _spec3(blocks, a=2.0, b=4.0):
    from sim.scenario_spec import LeaderStyle, ScenarioSpec
    return ScenarioSpec(name="x", blocks=tuple(blocks), style=LeaderStyle(a, b),
                        s_init=33.5, v_init=21.0)


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
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 600, {"to_v": 2.0})], a=2.0, b=4.0))
    page.compose_new("ramp", ticks=300, params={"to_v": 2.0})
    page._pad.set_point(3.0, 7.0)              # the ABSOLUTE point the user drops
    assert page._composer_bias() == (1.0, 3.0)  # stored as a bias off the neutral (2,4)
    assert page._pad._neutral == (2.0, 4.0)     # and the neutral is on screen as a second marker


def test_clicking_a_timeline_row_reopens_it_in_the_composer(qapp):
    from sim.scenario_spec import Block
    page = _page()
    page.set_spec(_spec3([Block("ramp", 300, {"to_v": 2.0}),
                          Block("const", 300, {"v": 8.0}, bias=(1.0, 2.0))]))
    page._list.setCurrentRow(1)
    page._on_row_selected(1)
    assert page._composer_kind() == "const"
    assert page._composer_bias() == (1.0, 2.0)  # its bias came back too
    page._on_add()                              # Add acts as Apply on an open row
    assert len(page._spec.blocks) == 2          # replaced, not appended


def test_composer_does_not_break_the_existing_flow(qapp):
    win = SimApp(CHAMP)
    before = win._selector.count()
    win.set_mode(3)
    win._scenario_page._on_use()
    assert win._selector.count() == before + 1
    win._advance(0.2)
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k composer
```

Expected: FAIL — `AttributeError: 'ScenarioPage' object has no attribute 'compose_new'`.

- [ ] **Step 3: Implement**

**3a — the pad learns about the neutral.** In `sim/ui/scenario_page.py`, `StylePad.__init__`, after the
dot is created:

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
        distance between them IS the bias."""
        self._neutral = (float(a), float(b))
        self._neutral_dot.setData([self._neutral[0]], [self._neutral[1]])
```

**3b — the composer.** Replace `ScenarioPage`'s action half. Add to `__init__`, after `self._pad` is
wired:

```python
        self._composer_row = None            # the timeline row being edited, or None for a new block
        self._composer_params = None         # the params of the block being composed
        self._composer_plot = pg.PlotWidget()
        self._composer_plot.setLabel("left", "blocco", units="m/s")
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
        the absolute is what the user reasons about ("this block brakes at 7"); storing the bias is
        what keeps one driver ("...which is 3 more than his usual")."""
        a, b = self._pad._a, self._pad._b
        na, nb = self._pad._neutral
        da, db = round(a - na, 6), round(b - nb, 6)
        return None if (da == 0.0 and db == 0.0) else (da, db)

    def _start_speed(self, upto):
        """The speed the first `upto` blocks leave behind -- the composer's only coupling to the
        timeline, and what makes the small preview honest instead of decorative."""
        if self._spec is None or upto <= 0:
            return float(self._spec.v_init) if self._spec else 21.0
        prefix = ScenarioSpec(name="_", blocks=self._spec.blocks[:upto], style=self._spec.style,
                              s_init=self._spec.s_init, v_init=self._spec.v_init)
        used = sum(b.ticks for b in prefix.blocks)
        return float(materialise(prefix, self._params_gt, max(1, min(used, self._N))).v_leader[-1])

    def compose_new(self, kind, ticks, params, bias=None):
        """Open a NEW block in the composer (does not touch the timeline until Add)."""
        self._composer_row = None
        self._kind.setCurrentText(kind)
        self._ticks.setValue(int(ticks))
        na, nb = self._pad._neutral
        self._pad.set_point(na + (bias[0] if bias else 0.0), nb + (bias[1] if bias else 0.0))
        self._composer_params = dict(params)
        self._refresh_composer()

    def _composer_block(self):
        return Block(self._composer_kind(), int(self._ticks.value()),
                     dict(self._composer_params or self._params_for(self._composer_kind())),
                     bias=self._composer_bias())

    def _refresh_composer(self):
        """Materialise a ONE-block spec from the speed the previous blocks leave behind."""
        if self._spec is None:
            self._composer_curve.setData([])
            return
        blk = self._composer_block()
        upto = self._composer_row if self._composer_row is not None else len(self._spec.blocks)
        v0 = self._start_speed(upto)
        one = ScenarioSpec(name="_", blocks=(blk,), style=self._spec.style,
                           s_init=self._spec.s_init, v_init=v0)
        self._composer_curve.setData(materialise(one, self._params_gt, blk.ticks).v_leader)

    def _on_row_selected(self, i):
        if self._spec is None or i < 0 or i >= len(self._spec.blocks):
            return
        b = self._spec.blocks[i]
        self._composer_row = i
        self._kind.setCurrentText(b.kind)
        self._ticks.setValue(int(b.ticks))
        self._composer_params = dict(b.params)
        na, nb = self._pad._neutral
        self._pad.set_point(na + (b.bias[0] if b.bias else 0.0), nb + (b.bias[1] if b.bias else 0.0))
        self._refresh_composer()
```

Rewire `set_style` so the pad's movement now edits the **bias** and refreshes the composer, while the
neutral keeps driving the scenario:

```python
    def set_style(self, a_max, b_max):
        """The pad moved: that is THIS BLOCK's point. The scenario's neutral is unchanged."""
        self._pad.set_point(a_max, b_max, emit=False)
        self._refresh_composer()
```

and make `set_spec` seed the neutral:

```python
    def set_spec(self, spec):
        self._spec = spec
        self._pad.set_neutral(spec.style.a_max, spec.style.b_max)
        self._pad.set_point(spec.style.a_max, spec.style.b_max, emit=False)
        self._refresh_list()
        self._refresh()
        self._refresh_composer()
```

Finally `_on_add` appends **or replaces**:

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
```

⚠️ `set_spec` no longer emits through the pad (`emit=False`), so the old `sigStyleChanged` → `set_style`
path no longer re-enters. Check `_refresh` is still called on every mutation — the cycle-3 tests
(`test_scenario_page_preview_is_the_real_materialised_profile`, `..._style_pad_redraws_the_preview`)
will tell you; **read them before adapting them**, because `set_style` deliberately no longer changes
the scenario's style, and those two tests encode the old meaning.

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q
```

Expected: PASS. Two cycle-3 tests will need their meaning updated (the pad edits a bias now, not the
style) — that is intended blast radius, not breakage.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/scenario_page.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): the right panel becomes a block composer

Build the piece while you see it: kind, params, and the 2-D pad now editing THIS
block's bias with the neutral drawn dimmer -- the distance between the two dots IS
the bias. The pad still shows an ABSOLUTE point because that is what one reasons
about ('this block brakes at 7'); the model stores the difference, which is what
keeps one driver.

The small preview materialises a one-block spec starting from the speed the previous
blocks leave behind: that coupling is the only thing that makes it honest instead of
decorative, and a test pins that the slice you judged is the slice you get."
```

---

### Task 4: The refresh still fits in a frame

**Files:**
- Test: `tests/test_sim_ui_smoke.py` (append)

⚠️ **Why this is a task and not a footnote.** The composer adds materialise calls to a budget that was
already measured tight: `materialise` costs **3.68 ms** and the whole frame has **16.7 ms**.
`_refresh_composer` calls it **twice** (`_start_speed` on the prefix, then the one-block preview) and
`_refresh` a third time for the full scenario. That is ~11 ms of numpy before pyqtgraph draws anything.
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

### Task 5: Full verification and docs

**Files:**
- Modify: `document/SIMULATOR_SESSION_RESUME.md`

- [ ] **Step 1: Run the full suite** — the 21 sim files + `tests/test_champion_io.py`.

Expected: **PASS**, 224 baseline + the new ones (Task 1: 5, Task 2: 2, Task 3: 5, Task 4: 1 → expect **237**).
Write the **real** number everywhere, never the predicted one.

- [ ] **Step 2: Verify the frozen core and the invariant source**

```bash
git diff --stat origin/Simulator -- sim/state.py sim/stepper.py sim/backend.py sim/probe.py sim/eventprop_stepper.py utils/closed_loop_eval.py
```

Expected: **empty**.

- [ ] **Step 3: Prove backward compatibility on a real cycle-3 file**

Write to your scratchpad a script that builds a cycle-3 spec (no bias), `to_json`s it, checks the text
contains no `"bias"`, `from_json`s it back, and asserts `materialise` is byte-identical. Run it with the
env python. This is the claim that protects everything already built.

- [ ] **Step 4: Render-verify — actually look at it**

`QT_QPA_PLATFORM=windows`, build `SimApp`, `set_mode(3)`, `compose_new("ramp", 300, {"to_v": 2.0})`,
move the pad off the neutral, grab and **Read the PNG**. Check: two dots on the pad (bright = block,
dim = neutral), the composer curve starting from the right speed, the scenario curve below.

- [ ] **Step 5: Update the resume and commit**

Mark cycle 4a done with the **real** test count; note that `ScenarioSpec.style` now means the neutral;
leave cycle 4b (drag + `custom` + advisory) as the next open item.

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
- **Do not add the advisory here.** It looks trivial (`diff(v)/DT > style`) and it is measured to be
  false red on presets: `cut_in` demands −75 m/s² because it is a *different vehicle*, and `following`
  "violates" in 503 of 599 steps because of its noise. It belongs with the drag, in 4b.
- **`_preset_samples` never receives a style**, so a bias cannot touch a preset by construction. Keep it
  that way: the test guards the construction, not a convention.
