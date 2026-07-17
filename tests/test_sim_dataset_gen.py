import json
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from config import DT                                       # noqa: E402
from sim.dataset_mix import MixEntry                        # noqa: E402
from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec   # noqa: E402
from sim.dataset_gen import decimate, draw_scenario, generate_dataset, preview_sample   # noqa: E402

_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


def _specs():
    return {"mine": ScenarioSpec(name="mine", blocks=(Block("const", 120, {"v": 15.0}),),
                                 style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)}


def test_the_generator_family_is_the_REAL_training_randomisation():
    """It must BE _leader_profile with the same seed -- not a re-interpretation of it."""
    from data.generator import _leader_profile
    sc = draw_scenario("generator", "stop_and_go", seed=11, strength=0.4, specs={}, params_gt=_PG)
    expected = _leader_profile("stop_and_go", 600, DT, np.random.default_rng(11), float(_PG[0]))
    assert np.allclose(sc.v_leader, expected)


def test_each_family_yields_a_valid_scenario():
    for fam, src in (("built", "mine"), ("preset", "hard_brake"), ("generator", "constant")):
        sc = draw_scenario(fam, src, seed=3, strength=0.3, specs=_specs(), params_gt=_PG)
        assert sc.v_leader.ndim == 1 and sc.v_leader.size > 0
        assert np.isfinite(sc.v_leader).all()
        assert sc.s_init > 0.0


def test_the_built_family_uses_its_spec_length_and_the_jitter_moves_it():
    a = draw_scenario("built", "mine", seed=1, strength=0.0, specs=_specs(), params_gt=_PG)
    b = draw_scenario("built", "mine", seed=1, strength=0.5, specs=_specs(), params_gt=_PG)
    assert a.v_leader.size == 120                     # strength=0 -> the spec's own length
    # the jitter moves `ticks` too, so the LENGTH itself can change -- compare length-safely
    moved = (a.v_leader.shape != b.v_leader.shape) or not np.allclose(a.v_leader, b.v_leader)
    assert moved                                      # jitter actually moves the profile


def test_preview_sample_is_deterministic():
    a = preview_sample("preset", "hard_brake", seed=9, strength=0.3, specs={}, params_gt=_PG)
    b = preview_sample("preset", "hard_brake", seed=9, strength=0.3, specs={}, params_gt=_PG)
    assert np.allclose(a, b)


def test_decimate_subsamples_and_recomputes_acceleration():
    k = {"t": np.arange(10) * DT, "v_leader": np.arange(10, dtype=float),
         "x_leader": np.arange(10, dtype=float), "a_leader": np.zeros(10)}
    d = decimate(k, 2, DT)
    assert d["v_leader"].size == 5
    assert np.allclose(d["t"], np.arange(5) * (2 * DT))               # dt_out = k*DT
    assert np.allclose(d["a_leader"], np.diff(d["v_leader"], prepend=d["v_leader"][0]) / (2 * DT))


def test_generate_dataset_is_reproducible_and_writes_a_manifest(tmp_path):
    mix = [MixEntry("preset", "hard_brake", 50.0), MixEntry("generator", "constant", 50.0)]
    out_a, out_b = str(tmp_path / "a"), str(tmp_path / "b")
    for out in (out_a, out_b):
        generate_dataset(mix, count=4, seed=5, strength=0.3, k=1, formats=["csv"],
                         out_dir=out, specs={}, params_gt=_PG)
    names = sorted(os.listdir(out_a))
    assert "manifest.json" in names and len([n for n in names if n.endswith(".csv")]) == 4
    with open(os.path.join(out_a, "manifest.json")) as f:
        man = json.load(f)
    assert man["seed"] == 5 and man["count"] == 4 and man["dt_out"] == DT and man["k"] == 1
    assert len(man["trajectories"]) == 4
    assert {t["family"] for t in man["trajectories"]} == {"preset", "generator"}
    # same seed -> byte-identical dataset
    for n in [x for x in names if x.endswith(".csv")]:
        assert open(os.path.join(out_a, n), "rb").read() == open(os.path.join(out_b, n), "rb").read()
