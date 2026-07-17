"""The dataset engine: a 3-family sampler + decimation + the reproducible batch loop.

One product, three families -- each randomises its own way, all yield a Scenario, so nothing downstream knows
the origin:
  built     -> jitter the spec's blocks + neutral, then materialise (its own length)
  preset    -> jitter params_gt (a preset is verbatim; v_set = 0.7*v0 is its only real knob), then materialise
               a one-preset-block spec (600 = the canonical library length)
  generator -> _leader_profile(...) from data/generator.py, CALLED READ-ONLY: that module is the frozen
               provenance of the champions' training data (a copy is archived with the champion). Its own
               seeded jitter (base/amp/freq/cycle_len) IS the training randomisation -- so the strength slider
               deliberately does NOT govern this family; re-interpreting it would make the dataset a lie.

Frequency: the physics is ALWAYS 10 Hz (DT=0.1 is the V2X rate, hardcoded into the frozen core,
closed_loop_eval and materialise -- not a knob). The export may be DECIMATED by an integer k; a_leader is
recomputed at dt_out because the 0.2 s acceleration is not the 0.1 s one. Upsampling is not offered: it would
invent data the physics never produced."""
import json
import os

import numpy as np

from config import DT
from data.generator import _leader_profile          # read-only: the real training randomisation
from sim.dataset_mix import quotas, validate_mix
from sim.export_formats import FORMATS
from sim.jitter import jitter_params_gt, jitter_spec
from sim.scenario import manual_scenario
from sim.scenario_export import leader_kinematics, scenario_metadata
from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec, _PRESET_N, materialise

GENERATOR_PROFILES = ("constant", "sinusoidal", "stop_and_go", "free", "launch")


def draw_scenario(family, source, seed, strength, specs, params_gt):
    """(family, source, seed) -> a Scenario. The one entry point every family funnels through."""
    rng = np.random.default_rng(seed)
    if family == "built":
        j = jitter_spec(specs[source], rng, strength)
        n = sum(int(b.ticks) for b in j.blocks)
        return materialise(j, params_gt, n)
    if family == "preset":
        pg = jitter_params_gt(params_gt, rng, strength)
        spec = ScenarioSpec(name=source, blocks=(Block("preset", _PRESET_N, {"name": source}),),
                            style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)
        return materialise(spec, pg, _PRESET_N)
    if family == "generator":
        v0 = float(params_gt[0])
        v_l = _leader_profile(source, _PRESET_N, DT, rng, v0)
        return manual_scenario(params_gt, np.asarray(v_l, dtype=float),
                               s_init=33.5, v_init=0.8 * v0, name=source)
    raise ValueError(f"famiglia sconosciuta: {family!r}")


def preview_sample(family, source, seed, strength, specs, params_gt):
    """The v_leader the eye shows. For `generator` and for jittered `built` this is ONE representative sample
    (the scenario there IS a distribution), not 'the' scenario -- the popup says so."""
    return draw_scenario(family, source, seed, strength, specs, params_gt).v_leader


def decimate(kin, k, dt=DT):
    """Take every k-th sample; a_leader is RECOMPUTED at dt_out (it is a different quantity there)."""
    k = int(k)
    if k <= 1:
        return kin
    dt_out = k * dt
    v = kin["v_leader"][::k]
    return {"t": np.arange(v.size) * dt_out, "v_leader": v, "x_leader": kin["x_leader"][::k],
            "a_leader": np.diff(v, prepend=v[0]) / dt_out}


def _as_scenario(sc, kin, k):
    """The writers take a Scenario and re-derive the kinematics at the dt they are given. When k>1 the
    decimated v_leader IS the scenario at dt_out, so hand them that -- one path, no second kinematics."""
    if k <= 1:
        return sc
    return manual_scenario(sc.params_gt, kin["v_leader"], s_init=sc.s_init, v_init=sc.v_init, name=sc.name)


def generate_dataset(mix, count, seed, strength, k, formats, out_dir, specs, params_gt, on_progress=None):
    """Write `count` trajectories + manifest.json into out_dir. Same seed -> identical dataset."""
    validate_mix(mix)
    qs = quotas(mix, count)
    os.makedirs(out_dir, exist_ok=True)
    root = np.random.default_rng(seed)
    seeds = [int(s) for s in root.integers(0, 2**31 - 1, size=count)]
    plan = [(e.family, e.source) for e, q in zip(mix, qs) for _ in range(q)]

    records = []
    for i, ((family, source), tseed) in enumerate(zip(plan, seeds)):
        sc = draw_scenario(family, source, tseed, strength, specs, params_gt)
        kin = decimate(leader_kinematics(sc, DT), k, DT)
        meta = scenario_metadata(sc, DT)
        for fmt in formats:
            path = os.path.join(out_dir, f"traj_{i:04d}.{fmt}")
            FORMATS[fmt].writer(_as_scenario(sc, kin, k), path, k * DT)
        records.append({"index": i, "family": family, "source": source, "seed": tseed,
                        "N": int(kin["v_leader"].size), "params_gt": [float(x) for x in meta["params_gt"]],
                        "s_init": meta["s_init"], "v_init": meta["v_init"]})
        if on_progress is not None:
            on_progress(i + 1, count)

    manifest = {"seed": seed, "count": count, "strength": strength, "k": k, "dt_out": k * DT,
                "decimated_from": DT, "formats": list(formats),
                "mix": [{"family": e.family, "source": e.source, "weight": e.weight} for e in mix],
                "quotas": qs, "trajectories": records}
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest
