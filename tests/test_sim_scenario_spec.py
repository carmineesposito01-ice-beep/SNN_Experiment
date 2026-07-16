import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from config import DT                                                          # noqa: E402
from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec, materialise    # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])
NORMALE = LeaderStyle(a_max=2.0, b_max=4.0)


def _spec(blocks, style=NORMALE, v_init=21.0):
    return ScenarioSpec(name="test", blocks=tuple(blocks), style=style,
                        s_init=33.5, v_init=v_init)


def test_const_block_holds_after_reaching_the_value():
    sc = materialise(_spec([Block("const", 100, {"v": 21.0})]), _PG, N=100)
    assert sc.v_leader.shape == (100,)
    np.testing.assert_allclose(sc.v_leader, 21.0)


def test_ramp_uses_the_style_rate_and_then_holds():
    """The ramp's slope is b_max, and `ticks` is the SLOT: once it arrives it holds for the rest."""
    sc = materialise(_spec([Block("ramp", 200, {"to_v": 2.0})]), _PG, N=200)
    vl = sc.v_leader
    assert vl[0] < 21.0                                        # already moving on tick 0
    # 21 -> 2 at b_max=4 m/s^2 takes 19/4 = 4.75 s = 47.5 ticks at DT=0.1
    n_ramp = int(np.ceil(19.0 / 4.0 / DT))
    assert abs(vl[n_ramp] - 2.0) < 1e-6                        # arrived
    np.testing.assert_allclose(vl[n_ramp:], 2.0)               # and holds for the rest of the slot
    dv = np.diff(vl[:n_ramp])
    assert np.all(dv >= -4.0 * DT - 1e-9)                      # never steeper than the style


def test_blocks_chain_from_where_the_previous_left_off():
    sc = materialise(_spec([Block("ramp", 30, {"to_v": 2.0}),       # slot too short to arrive
                            Block("const", 70, {"v": 2.0})]), _PG, N=100)
    vl = sc.v_leader
    assert vl[29] > 2.0                                         # cut mid-ramp, as designed
    assert abs(vl[30] - (vl[29] - 4.0 * DT)) < 1e-6             # next block continues from there
    assert abs(vl[-1] - 2.0) < 1e-6                             # and gets there


def test_materialise_is_pure_and_reproducible():
    s = _spec([Block("ramp", 100, {"to_v": 5.0}), Block("const", 100, {"v": 5.0})])
    np.testing.assert_array_equal(materialise(s, _PG, N=200).v_leader,
                                  materialise(s, _PG, N=200).v_leader)


def test_materialise_returns_a_scenario_the_stepper_can_run():
    from sim.stepper import SimStepper
    sc = materialise(_spec([Block("const", 60, {"v": 21.0})]), _PG, N=60)
    st = SimStepper.from_scenario(None, sc)                     # backend=None -> the oracle, no net needed
    for _ in range(60):
        if st.st.collided or st.st.t >= st.N:
            break
        st.step()
    assert st.st.t == 60                                        # it really is a runnable Scenario


# ---- the style is a PLANE, and the axes are independent -------------------------------------------

AGGRESSIVO = LeaderStyle(a_max=4.0, b_max=9.0)
PLACIDO = LeaderStyle(a_max=1.0, b_max=1.0)
GUARDINGO = LeaderStyle(a_max=1.0, b_max=9.0)      # crawls off, slams the brakes
SPAVALDO = LeaderStyle(a_max=4.0, b_max=1.0)       # darts away, coasts down


def test_style_changes_the_trajectory_not_the_label():
    """TEETH: the deceleration must MATCH b_max, not merely differ between styles. A style that
    only renames things gives the same rate for both and fails here.

    NB the LAST step of a ramp is partial by design -- the clip lands exactly on to_v instead of
    overshooting -- so the assertion is on the steepest step, not on every step.
    """
    for style in (PLACIDO, AGGRESSIVO):
        vl = materialise(_spec([Block("ramp", 300, {"to_v": 2.0})], style=style), _PG, N=300).v_leader
        d = np.diff(vl)
        moving = d[d < -1e-9]                                  # the braking samples
        assert abs(moving.min() - (-style.b_max * DT)) < 1e-9  # the steepest step IS b_max
        assert np.all(moving >= -style.b_max * DT - 1e-9)      # and nothing is steeper
        assert abs(vl[-1] - 2.0) < 1e-9                        # and it lands exactly on the target


def test_the_two_axes_are_independent():
    """TEETH, and this is WHY the style is a plane and not a slider: moving a_max must leave every
    braking segment byte-identical, and moving b_max must leave every accelerating segment
    byte-identical. A style that secretly couples them passes the test above and fails here."""
    blocks = [Block("ramp", 150, {"to_v": 2.0}),               # braking
              Block("ramp", 150, {"to_v": 21.0})]              # accelerating
    base = materialise(_spec(blocks, style=LeaderStyle(2.0, 4.0)), _PG, N=300).v_leader
    only_a = materialise(_spec(blocks, style=LeaderStyle(4.0, 4.0)), _PG, N=300).v_leader
    only_b = materialise(_spec(blocks, style=LeaderStyle(2.0, 9.0)), _PG, N=300).v_leader
    np.testing.assert_array_equal(base[:150], only_a[:150])    # a_max moved -> braking untouched
    assert not np.array_equal(base[150:], only_a[150:])        # ...and acceleration DID change
    assert not np.array_equal(base[:150], only_b[:150])        # b_max moved -> braking changed


def test_the_four_quadrants_are_reachable_and_distinct():
    blocks = [Block("ramp", 150, {"to_v": 2.0}), Block("ramp", 150, {"to_v": 21.0})]
    out = {name: materialise(_spec(blocks, style=s), _PG, N=300).v_leader
           for name, s in (("aggressivo", AGGRESSIVO), ("placido", PLACIDO),
                           ("guardingo", GUARDINGO), ("spavaldo", SPAVALDO))}
    # guardingo brakes like aggressivo but accelerates like placido: the mixed quadrant exists
    np.testing.assert_array_equal(out["guardingo"][:150], out["aggressivo"][:150])
    np.testing.assert_array_equal(out["spavaldo"][:150], out["placido"][:150])
    assert not np.array_equal(out["guardingo"][150:], out["aggressivo"][150:])


def test_style_outside_the_plane_is_rejected():
    with pytest.raises(ValueError, match="a_max"):
        materialise(_spec([Block("const", 10, {"v": 5.0})], style=LeaderStyle(9.0, 4.0)), _PG, N=10)
    with pytest.raises(ValueError, match="b_max"):
        materialise(_spec([Block("const", 10, {"v": 5.0})], style=LeaderStyle(2.0, 20.0)), _PG, N=10)


# ---- preset (as-is), sine (anchored to v0), JSON -------------------------------------------------

def test_preset_block_reproduces_the_library_exactly():
    """TEETH: build_scenarios is INVARIANT (its docstring pins it: the reports run on it), so a
    preset block must be byte-identical to the library's. Fails the moment the style touches it."""
    from sim.scenario import scenario_library
    lib = {s.name: s for s in scenario_library(_PG, N=600, rng=np.random.default_rng(0),
                                               include_tail=True)}
    for style in (PLACIDO, AGGRESSIVO):                        # the style must NOT matter here
        sc = materialise(_spec([Block("preset", 600, {"name": "stop_and_go"})], style=style),
                         _PG, N=600)
        np.testing.assert_array_equal(sc.v_leader, lib["stop_and_go"].v_leader)


def test_preset_block_slice_takes_the_first_ticks_samples():
    from sim.scenario import scenario_library
    lib = {s.name: s for s in scenario_library(_PG, N=600, rng=np.random.default_rng(0),
                                               include_tail=True)}
    sc = materialise(_spec([Block("preset", 200, {"name": "stop_and_go"}),
                            Block("const", 400, {"v": 5.0})]), _PG, N=600)
    np.testing.assert_array_equal(sc.v_leader[:200], lib["stop_and_go"].v_leader[:200])


def test_unknown_preset_name_is_rejected_by_name():
    with pytest.raises(ValueError, match="nonesuch"):
        materialise(_spec([Block("preset", 10, {"name": "nonesuch"})]), _PG, N=10)


def test_sine_amplitude_is_clamped_by_the_style():
    """A sine's steepest slope is amp*2*pi/period. Rather than clipping tick by tick (recursive, and
    it would break the vectorisation the live preview needs), the style CLAMPS the amplitude -- a
    placid driver does not make brusque oscillations."""
    blocks = [Block("sine", 300, {"amp": 10.5, "period": 40})]
    calm = materialise(_spec(blocks, style=PLACIDO), _PG, N=300).v_leader
    hard = materialise(_spec(blocks, style=AGGRESSIVO), _PG, N=300).v_leader
    assert np.ptp(calm) < np.ptp(hard)                          # the calm driver swings less
    for vl, style in ((calm, PLACIDO), (hard, AGGRESSIVO)):
        assert np.abs(np.diff(vl)).max() <= max(style.a_max, style.b_max) * DT + 1e-9


def test_no_block_boundary_ever_teleports_the_leader():
    """TEETH, and it is the test that caught a real design bug: an earlier `sine` oscillated around
    an absolute `mean` and IGNORED v0, so a sine after a ramp ending at 2 m/s jumped straight to
    10.5 -- reproducing, inside the builder, the very teleport Task 4 removes from the events.

    Every junction between blocks must respect the style's rate, not just the inside of each block.
    """
    for style in (PLACIDO, AGGRESSIVO, GUARDINGO, SPAVALDO):
        vl = materialise(_spec([Block("ramp", 100, {"to_v": 2.0}),
                                Block("sine", 100, {"amp": 6.0, "period": 60}),
                                Block("const", 100, {"v": 18.0}),
                                Block("ramp", 100, {"to_v": 4.0}),
                                Block("sine", 200, {"amp": 3.0, "period": 40})],
                               style=style), _PG, N=600).v_leader
        jump = np.abs(np.diff(vl)).max()
        limit = max(style.a_max, style.b_max) * DT + 1e-9
        assert jump <= limit, f"{style}: a {jump:.3f} m/s jump in one tick (limit {limit:.3f})"


def test_json_round_trip_is_byte_exact_on_every_kind():
    from sim.scenario_spec import from_json, to_json
    s = _spec([Block("preset", 100, {"name": "stop_and_go"}),
               Block("const", 100, {"v": 8.0}),
               Block("ramp", 100, {"to_v": 2.0}),
               Block("sine", 300, {"amp": 4.0, "period": 80})],
              style=GUARDINGO)
    back = from_json(to_json(s))
    assert back == s                                            # frozen dataclasses compare by value
    np.testing.assert_array_equal(materialise(back, _PG, N=600).v_leader,
                                  materialise(s, _PG, N=600).v_leader)


def test_json_rejects_an_unknown_block_kind_by_name():
    from sim.scenario_spec import from_json
    bad = '{"name":"x","s_init":33.5,"v_init":21.0,"style":{"a_max":2.0,"b_max":4.0},' \
          '"blocks":[{"kind":"teleport","ticks":10,"params":{}}]}'
    with pytest.raises(ValueError, match="teleport"):
        from_json(bad)


def test_materialise_holds_the_60fps_budget():
    """The live preview redraws on every drag step. Assert the PEAK, not the mean: it is the peak
    the eye sees. A per-tick Python loop (the first prototype) costs ~3.7 ms and fails this on a
    busy timeline -- which is why the materialiser is vectorised."""
    import time
    s = _spec([Block("preset", 150, {"name": "stop_and_go"}), Block("ramp", 150, {"to_v": 2.0}),
               Block("const", 150, {"v": 2.0}), Block("sine", 150, {"amp": 5.0, "period": 60})])
    for _ in range(3):
        materialise(s, _PG, N=600)                       # warm up
    ts = []
    for _ in range(60):
        t0 = time.perf_counter()
        materialise(s, _PG, N=600)
        ts.append((time.perf_counter() - t0) * 1000)
    peak = max(ts)
    assert peak < 16.7, f"materialise peaks at {peak:.2f} ms, over the 60 fps budget"


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


# ---- custom: a hand-drawn polyline -------------------------------------------------------------

def test_custom_is_a_linear_polyline_anchored_at_v0():
    """Node 0 IS v0 (not stored); the nodes are SPEEDS on a derived, evenly-spaced tick grid."""
    from sim.scenario_spec import _custom_node_ticks, _custom_samples
    v = _custom_samples([10.0, 10.0, 4.0], n=90, v0=21.0)
    assert v.shape == (90,)
    assert v[0] == 21.0                                   # anchored at v0
    assert abs(v[-1] - 4.0) < 1e-9                        # last node is the last sample
    # linear between anchor (0,21) and first node (~30,10): midpoint ~ (21+10)/2
    assert abs(v[15] - (21.0 + (10.0 - 21.0) * 15 / 30.0)) < 0.2


def test_custom_with_zero_nodes_is_flat_at_v0():
    from sim.scenario_spec import _custom_samples
    v = _custom_samples([], n=50, v0=13.5)
    np.testing.assert_array_equal(v, np.full(50, 13.5))   # np.interp on a single point


def test_custom_clips_speeds_to_v_range_no_reverse_leader():
    """A hand-edited node beyond the physical range is pinned: v<0 is the leader in reverse, which is
    not a scenario. Clipping the NODES (not the samples) keeps the polyline linear in-range."""
    from sim.scenario_spec import _custom_samples, V_RANGE
    v = _custom_samples([-5.0, 99.0], n=40, v0=10.0)
    assert v.min() >= V_RANGE[0] - 1e-9 and v.max() <= V_RANGE[1] + 1e-9


def test_moving_one_node_changes_only_its_two_segments():
    """TEETH: interp locality IS the drawing model. A change that leaked past the neighbouring nodes
    would still 'change the curve' and pass a naive test."""
    from sim.scenario_spec import _custom_samples
    base = _custom_samples([10.0, 10.0, 10.0, 10.0], n=200, v0=21.0)
    moved = _custom_samples([10.0, 4.0, 10.0, 10.0], n=200, v0=21.0)   # node index 1 moved
    d = np.flatnonzero(np.abs(base - moved) > 1e-9)
    # node 1 sits at tick ~ linspace(0,199,5)[2]=99.5; its neighbours at ~49.75 and ~149.25.
    assert d.min() > 45 and d.max() < 155                 # untouched outside [node0..node2]


def test_a_custom_block_joins_continuously():
    """Extends cycle 3's boundary property to custom: node-0-is-v0 means a custom never teleports at a
    junction (materialise threads v as each block's v0). preset is the ONLY kind that may seam."""
    prev_last = materialise(_spec([Block("ramp", 200, {"to_v": 6.0})]), _PG, N=200).v_leader[-1]
    two = materialise(_spec([Block("ramp", 200, {"to_v": 6.0}),
                             Block("custom", 200, {"nodes": [18.0, 18.0]})]), _PG, N=400).v_leader
    assert abs(two[200] - prev_last) < 1e-9               # first custom sample == previous last: no jump
