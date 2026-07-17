"""The training sink: a mix row -> the dict train.py's CFDataset eats, via the champions' real physics.

Two rules shape everything here:
  - The regime gives the params and the params ARE the labels. _sample_scenario is reused VERBATIM (the regime
    forced through its own scenario_mix parameter) so the ranges cannot drift from the champions'.
  - The family gives the leader. built/preset inject; generator/cut_in go down the STANDARD path untouched --
    so a mix of only those reproduces the standard dataset.

The strength slider therefore governs the LEADER only. Jittering the params here would break the
correspondence with the champions' label distribution: closed by construction, not by a warning."""
import numpy as np

from config import DT, WARMUP_DURATION
from data.generator import _sample_scenario, normalize, simulate_cut_in_trajectory, simulate_trajectory
from sim.jitter import jitter_spec
from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec, _PRESET_N, materialise

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
