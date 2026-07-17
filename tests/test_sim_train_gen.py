"""The training sink: the 8-key dict train.py's CFDataset eats, built with the champions' real physics."""
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from config import IDM_HWY                                  # noqa: E402
from data.generator import simulate_trajectory              # noqa: E402


def test_an_injected_leader_lands_in_the_trajectory():
    """traj[:,3] IS v_l_true (generator.py:329). Without this check a v_leader silently ignored would give a
    plausible, wrong dataset -- the worst failure available here."""
    v = np.linspace(20.0, 10.0, 400).astype(np.float32)
    traj = simulate_trajectory(dict(IDM_HWY), profile="sinusoidal", seed=1, v_leader=v)
    assert traj.shape == (400, 7)                 # N follows the injected length, not SIM_DURATION/DT
    assert np.allclose(traj[:, 3], v)


def test_v_leader_none_is_exactly_not_passing_it():
    """The default path must not move: the kwarg is additive, not a behaviour change."""
    a = simulate_trajectory(dict(IDM_HWY), profile="sinusoidal", seed=7)
    b = simulate_trajectory(dict(IDM_HWY), profile="sinusoidal", seed=7, v_leader=None)
    assert np.array_equal(a, b)


from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec       # noqa: E402
from sim.train_mix import TrainMixEntry                              # noqa: E402


def _specs(ticks=600):
    return {"mine": ScenarioSpec(name="mine", blocks=(Block("const", ticks, {"v": 21.0}),),
                                 style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)}


def test_the_regime_is_forced_and_gives_the_labels():
    """_sample_scenario is reused VERBATIM by forcing the regime through its own scenario_mix parameter, so the
    per-regime ranges are the champions' -- not a copy of them that can drift."""
    from sim.train_gen import params_for_regime
    rng = np.random.default_rng(0)
    p = params_for_regime("launch", rng)
    assert set(p) >= {"v0", "T", "s0", "a", "b"}
    # launch: p['v0'] = IDM_HWY['v0'] * U(0.60, 1.00)  (generator.py:571-575)
    assert 33.3 * 0.60 <= p["v0"] <= 33.3 * 1.00


def test_a_built_sample_carries_its_own_leader_and_the_regimes_labels():
    from sim.train_gen import draw_training_sample
    d = draw_training_sample(TrainMixEntry("built", "mine", "urban", 100.0), seed=3, strength=0.2,
                             specs=_specs())
    assert d["scenario"] == "urban"           # train.py:1428 compares THIS against the mix -> the regime name
    assert d["leader_family"] == "built" and d["leader_source"] == "mine"
    assert d["cut_in"] is False
    # urban: p['v0'] = IDM_URB['v0'] * U(0.80, 1.10)  (generator.py:545-549)
    assert 15.0 * 0.80 <= d["params"]["v0"] <= 15.0 * 1.10
    assert d["raw"].shape[1] == 7 and d["x"].shape[1] == 4 and d["y"].shape[1] == 2


def test_the_warmup_is_stripped_like_the_real_generator():
    """generate_dataset does traj[warmup_steps:] (:643). 600 built ticks - 200 warmup = 400."""
    from sim.train_gen import draw_training_sample
    d = draw_training_sample(TrainMixEntry("built", "mine", "highway", 100.0), seed=3, strength=0.0,
                             specs=_specs(ticks=600))
    assert d["raw"].shape[0] == 400


def test_the_generator_family_does_not_inject_at_all():
    """generator/cut_in go down the STANDARD path untouched -> a mix of only those reproduces the standard
    dataset. Its leader must therefore be 1200-200=1000 ticks, not a built length."""
    from sim.train_gen import draw_training_sample
    d = draw_training_sample(TrainMixEntry("generator", "sinusoidal", "highway", 100.0), seed=3, strength=0.9,
                             specs={})
    assert d["raw"].shape[0] == 1000
    assert d["cut_in"] is False


def test_the_cut_in_family_uses_the_untouched_cut_in_path():
    from sim.train_gen import draw_training_sample
    d = draw_training_sample(TrainMixEntry("cut_in", "sinusoidal", "urban", 100.0), seed=3, strength=0.0,
                             specs={})
    assert d["cut_in"] is True and d["raw"].shape[0] == 1000


def test_a_scenario_too_short_to_yield_a_window_is_refused_loudly():
    """CFDataset yields ZERO windows for N < seq_len and says nothing. A dataset that generates cleanly and
    trains nothing is the failure we refuse to ship."""
    from sim.train_gen import draw_training_sample
    with pytest.raises(ValueError, match="troppo corto"):
        draw_training_sample(TrainMixEntry("built", "mine", "highway", 100.0), seed=3, strength=0.0,
                             specs=_specs(ticks=250))


def test_our_dict_is_digested_by_the_REAL_CFDataset():
    """Do not trust a remembered contract: hand the dict to train.py's actual class and require windows out.
    (`from train import CFDataset` imports cleanly in ~3.2 s, no side effects -- verified.)"""
    from train import CFDataset
    from sim.train_gen import draw_training_sample
    d = draw_training_sample(TrainMixEntry("generator", "sinusoidal", "highway", 100.0), seed=5, strength=0.0,
                             specs={})
    ds = CFDataset([d], seq_len=100, stride=50)
    assert len(ds) > 0
    x, y, mask, params_gt = ds[0]
    assert tuple(x.shape) == (100, 4) and tuple(y.shape) == (100, 2) and tuple(mask.shape) == (100,)
    # CFDataset extracts [v0, s0, a, b] from item['params'] (train.py:144-149)
    assert np.allclose(params_gt.numpy(),
                       [d["params"]["v0"], d["params"]["s0"], d["params"]["a"], d["params"]["b"]])


@pytest.mark.parametrize("n_ticks,stride,expected", [(1000, 50, 19), (1000, 100, 10), (400, 50, 7), (99, 50, 0)])
def test_windows_per_traj_agrees_with_the_real_CFDataset(n_ticks, stride, expected):
    """The count comes from train.py's loop, not from our arithmetic -- so the UI's honesty column cannot drift
    from what training actually sees."""
    from train import CFDataset
    from sim.train_gen import windows_per_traj
    fake = {"x": np.zeros((n_ticks, 4), dtype=np.float32), "y": np.zeros((n_ticks, 2), dtype=np.float32),
            "mask": np.ones(n_ticks, dtype=np.float32), "params": dict(IDM_HWY)}
    assert len(CFDataset([fake], seq_len=100, stride=stride)) == expected
    assert windows_per_traj(n_ticks, seq_len=100, stride=stride) == expected


def test_the_two_batches_are_disjoint_and_the_cache_is_what_train_py_reads(tmp_path):
    import torch
    from sim.train_gen import build_training_cache
    mix = [TrainMixEntry("generator", "sinusoidal", "highway", 100.0)]
    path = str(tmp_path / "cache.pt")
    man = build_training_cache(mix, n_train=3, n_val=2, seed=11, strength=0.0, specs={}, path=path)
    blob = torch.load(path, weights_only=False)
    assert set(blob) >= {"train", "val", "seed"}            # train.py:1423-1426 reads exactly these
    assert len(blob["train"]) == 3 and len(blob["val"]) == 2 and blob["seed"] == 11
    assert man["quotas"] == [3]
    # seeds S and S+1 -> two i.i.d. samples, nothing shared
    keys_tr = {d["raw"][:, 3].tobytes() for d in blob["train"]}
    keys_va = {d["raw"][:, 3].tobytes() for d in blob["val"]}
    assert keys_tr.isdisjoint(keys_va)


def test_the_new_shapes_gate_catches_a_leader_shared_between_train_and_val(tmp_path):
    """jitter_spec at strength=0 is the IDENTITY (proven in 7a), and a const-only spec does not depend on v0 --
    so train and val would get byte-identical leaders. Mode 2 must refuse instead of quietly weakening the val."""
    from sim.train_gen import VAL_MODE_NEW_SHAPES, build_training_cache
    mix = [TrainMixEntry("built", "mine", "highway", 100.0)]
    with pytest.raises(ValueError, match="STESSO leader"):
        build_training_cache(mix, n_train=2, n_val=2, seed=11, strength=0.0, specs=_specs(),
                             path=str(tmp_path / "c.pt"), val_mode=VAL_MODE_NEW_SHAPES)


def test_the_standard_mode_allows_what_the_new_shapes_mode_refuses(tmp_path):
    """The two modes must actually differ -- otherwise the selector is decoration."""
    from sim.train_gen import build_training_cache
    mix = [TrainMixEntry("built", "mine", "highway", 100.0)]
    man = build_training_cache(mix, n_train=2, n_val=2, seed=11, strength=0.0, specs=_specs(),
                               path=str(tmp_path / "c.pt"))
    assert man["n_train"] == 2


def test_cancelling_writes_nothing(tmp_path):
    """A half dataset that looks whole is the failure this project hunts."""
    from sim.train_gen import build_training_cache
    path = str(tmp_path / "cache.pt")
    mix = [TrainMixEntry("generator", "sinusoidal", "highway", 100.0)]
    seen = []

    def on_progress(done, total):
        seen.append((done, total))
        return False                      # cancel at the first tick
    man = build_training_cache(mix, n_train=3, n_val=2, seed=11, strength=0.0, specs={}, path=path,
                               on_progress=on_progress)
    assert man is None
    assert not os.path.exists(path)
    assert seen[0] == (1, 5)              # progress is over BOTH batches, not per batch
