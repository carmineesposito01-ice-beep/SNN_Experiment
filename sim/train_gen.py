"""The training sink: a mix row -> the dict train.py's CFDataset eats, via the champions' real physics.

Two rules shape everything here:
  - The regime gives the params and the params ARE the labels. _sample_scenario is reused VERBATIM (the regime
    forced through its own scenario_mix parameter) so the ranges cannot drift from the champions'.
  - The family gives the leader. built/preset inject; generator/cut_in go down the STANDARD path untouched --
    so a mix of only those reproduces the standard dataset.

The strength slider therefore governs the LEADER only. Jittering the params here would break the
correspondence with the champions' label distribution: closed by construction, not by a warning."""
import os

import numpy as np

from config import DT, WARMUP_DURATION
from data.generator import _sample_scenario, normalize, simulate_cut_in_trajectory, simulate_trajectory
from sim.jitter import jitter_spec
from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec, _PRESET_N, materialise
from sim.train_mix import train_quotas, validate_train_mix

WARMUP_STEPS = int(WARMUP_DURATION / DT)          # 200 -- generator.py:621
SEQ_LEN = 100                                     # train.py's --seq_len default (:1058)
MIN_TICKS = WARMUP_STEPS + SEQ_LEN                # 300: below this NOT ONE window survives the warmup strip


def params_for_regime(regime, rng):
    """The regime's params = THE LABELS.

    `scenario_mix={regime: 1.0}` forces _sample_scenario's own choice (:536); `cut_in_ratio=0.0` because here
    the cut-in is a FAMILY, not a dice roll. The returned `prof` is discarded on purpose: for built/preset the
    leader comes from the scenario, and for generator/cut_in it comes from the row's source."""
    p, _prof, stype, _is_cutin = _sample_scenario(rng, {regime: 1.0}, 0.0)
    if stype != regime:
        raise RuntimeError(f"il regime non e' stato forzato: chiesto {regime!r}, ottenuto {stype!r}")
    return p


def _params_gt(p):
    """The params dict -> the 5-array the simulator uses.

    Order from CF_FSNN_Net._PARAM_BOUNDS (core/network.py:323): [v0, T, s0, a, b]. `delta` (the IDM exponent)
    rides in the dict but is not a learned param and has no slot here."""
    return np.array([p["v0"], p["T"], p["s0"], p["a"], p["b"]], dtype=np.float64)


def _leader_for(entry, rng, strength, specs, p):
    """built/preset -> the v_leader to inject, materialised with the REGIME's params."""
    pg = _params_gt(p)
    if entry.family == "built":
        j = jitter_spec(specs[entry.source], rng, strength)
        n = sum(int(b.ticks) for b in j.blocks)
        return materialise(j, pg, n).v_leader
    spec = ScenarioSpec(name=entry.source, blocks=(Block("preset", _PRESET_N, {"name": entry.source}),),
                        style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)
    return materialise(spec, pg, _PRESET_N).v_leader


def draw_training_sample(entry, seed, strength, specs):
    """(row, seed) -> the 8-key dict. The one funnel every family goes through."""
    rng = np.random.default_rng(seed)
    p = params_for_regime(entry.regime, rng)
    tseed = int(rng.integers(0, 2**31))

    if entry.family in ("built", "preset"):
        v_leader = _leader_for(entry, rng, strength, specs, p)
        if v_leader.size < MIN_TICKS:
            raise ValueError(
                f"scenario {entry.source!r} troppo corto per il training: {v_leader.size} tick, servono "
                f"almeno {MIN_TICKS} ({WARMUP_STEPS} di warmup + {SEQ_LEN} = una finestra). "
                f"CFDataset ne produrrebbe ZERO senza dire niente.")
        traj = simulate_trajectory(p, seed=tseed, v_leader=v_leader)
        is_cutin = False
    elif entry.family == "generator":
        traj = simulate_trajectory(p, profile=entry.source, seed=tseed)
        is_cutin = False
    elif entry.family == "cut_in":
        traj = simulate_cut_in_trajectory(p, profile=entry.source, seed=tseed)
        is_cutin = True
    else:
        raise ValueError(f"famiglia sconosciuta: {entry.family!r}")

    traj = traj[WARMUP_STEPS:]
    x, y, mask = normalize(traj)
    return {
        "x": x, "y": y, "mask": mask, "raw": traj, "params": p,
        "profile": entry.source,        # nothing in the training path reads it; kept for parity with the generator
        "scenario": entry.regime,       # train.py:1428 checks THIS against the mix -> the regime, not our name
        "cut_in": is_cutin,
        "leader_family": entry.family,  # ours, additive: CFDataset ignores keys it does not know
        "leader_source": entry.source,
    }


def windows_per_traj(n_ticks, seq_len=SEQ_LEN, stride=None):
    """How many windows CFDataset cuts from a trajectory of n_ticks.

    This mirrors train.py's loop (`while start + seq_len <= N`, :150-159), and a test pins it against the real
    class. It matters because the user weights TRAJECTORIES while training eats WINDOWS: a 600-tick built
    scenario gives 7 where a 1200-tick generator one gives 19, so "30% built" is 13.6% of what the network sees.
    The share also depends on the stride, and the two batches do not share it (train seq_len//2, val seq_len --
    train.py:1467-1468)."""
    stride = seq_len // 2 if stride is None else stride
    if n_ticks < seq_len:
        return 0
    return (n_ticks - seq_len) // stride + 1


VAL_MODE_STANDARD = "standard"
VAL_MODE_NEW_SHAPES = "new_shapes"
VAL_MODE_DIFFERENT_MIX = "different_mix"
VAL_MODES = (VAL_MODE_STANDARD, VAL_MODE_NEW_SHAPES, VAL_MODE_DIFFERENT_MIX)

# Measured on the dev machine: 20 trajectories of 1200 ticks in 1.22 s. simulate_trajectory is a Python loop,
# so this is ~110x a 7a batch and the default 5000+500 is ~5.6 minutes. The UI needs it to show an ETA BEFORE
# the click -- a 5-minute job is acceptable when announced and refusable, not when it arrives as a surprise.
# DELIBERATELY NOT pinned by a test: it measures the MACHINE, and this repo already owns one wall-clock
# assertion (test_custom_composer_refresh_fits_in_a_frame) that reddens under load on innocent diffs. It is an
# order of magnitude for a "≈" label; the UI refines it live from the real rate once the run starts.
SECONDS_PER_TRAJ = 0.061


def build_split(mix, count, seed, strength, specs, on_progress=None):
    """`count` dicts drawn from the mix with EXACT quotas. Returns None if on_progress returns False (cancel)."""
    qs = train_quotas(mix, count)
    root = np.random.default_rng(seed)
    seeds = [int(s) for s in root.integers(0, 2**31 - 1, size=count)]
    plan = [e for e, q in zip(mix, qs) for _ in range(q)]
    out = []
    for entry, tseed in zip(plan, seeds):
        out.append(draw_training_sample(entry, tseed, strength, specs))
        if on_progress is not None and on_progress(len(out), count) is False:
            return None
    return out


def _leader_key(d):
    """The leader's identity. raw[:,3] is v_l_TRUE (generator.py:329) -- the profile itself, untouched by the
    OU noise -- so equal bytes mean the same leader, exactly."""
    return np.ascontiguousarray(d["raw"][:, 3]).tobytes()


def assert_disjoint_shapes(train, val):
    """Validation mode 2: no val leader is a copy of a train one.

    It checks the PROPERTY, not a proxy: "force jitter > 0" would be wrong in both directions -- a const/ramp
    built spec does not depend on v0, while a preset or a sine is anchored to v0, which the regime already
    jitters per trajectory. It catches EXACT copies, not near-copies."""
    seen = {_leader_key(d) for d in train}
    for i, d in enumerate(val):
        if _leader_key(d) in seen:
            raise ValueError(
                f"val[{i}] ({d['leader_family']}/{d['leader_source']}) ha lo STESSO leader di una traiettoria "
                f"di train: la validazione misurerebbe la generalizzazione su params e rumore, non su leader "
                f"nuovi. Alza il jitter, oppure usa la famiglia generator.")


def build_training_cache(mix, n_train, n_val, seed, strength, specs, path,
                         val_mode=VAL_MODE_STANDARD, val_mix=None, on_progress=None):
    """The whole sink: two i.i.d. batches (seeds S and S+1, mirroring train.py:1448-1455) -> the .pt cache.

    Returns the manifest, or None if cancelled -- in which case NOTHING is written.
    `on_progress(done, total)` counts over both batches and may return False to cancel.

    val_mode:
      standard       -- same mix, seed S+1. The train-val gap measures overfitting. What train.py does natively.
      new_shapes     -- same, plus the verified gate that no leader shape is shared.
      different_mix  -- val from `val_mix`. The gap stops measuring overfitting, and val_loss SELECTS the
                        checkpoint (train.py:798), drives early stopping (:1218) and commands ReduceLROnPlateau
                        (:1659) -- an out-of-distribution probe, to be chosen knowingly.
    """
    if val_mode not in VAL_MODES:
        raise ValueError(f"val_mode sconosciuto: {val_mode!r} (validi: {VAL_MODES})")
    if val_mode == VAL_MODE_DIFFERENT_MIX and not val_mix:
        raise ValueError("val_mode='different_mix' richiede val_mix")
    validate_train_mix(mix)
    effective_val_mix = val_mix if val_mode == VAL_MODE_DIFFERENT_MIX else mix
    validate_train_mix(effective_val_mix)

    total = n_train + n_val
    done = [0]

    def _relay(_done_in_batch, _count_in_batch):
        done[0] += 1
        return None if on_progress is None else on_progress(done[0], total)

    train = build_split(mix, n_train, seed, strength, specs, _relay)
    if train is None:
        return None
    val = build_split(effective_val_mix, n_val, seed + 1, strength, specs, _relay)
    if val is None:
        return None
    if val_mode == VAL_MODE_NEW_SHAPES:
        assert_disjoint_shapes(train, val)

    manifest = {
        "seed": seed, "n_train": n_train, "n_val": n_val, "strength": strength, "val_mode": val_mode,
        "quotas": train_quotas(mix, n_train),
        "mix": [{"family": e.family, "source": e.source, "regime": e.regime, "weight": e.weight} for e in mix],
        "windows_train": sum(windows_per_traj(d["raw"].shape[0]) for d in train),
        "windows_val": sum(windows_per_traj(d["raw"].shape[0], stride=SEQ_LEN) for d in val),
    }
    write_cache(path, train, val, seed, manifest)
    return manifest


def write_cache(path, train, val, seed, manifest=None):
    """The cache train.py reads: torch.save({'train', 'val', 'seed'}) (train.py:1462). `manifest` is an extra
    key -- train.py reads the three it knows and ignores the rest, so the dataset can carry its own provenance
    for free."""
    import torch
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)
    blob = {"train": train, "val": val, "seed": seed}
    if manifest is not None:
        blob["manifest"] = manifest
    torch.save(blob, path)
    return path
