"""Export a Scenario as the LEADER kinematics (t, v_leader, x_leader, a_leader) + metadata, in .csv and .mat.

This is the scenario DEFINITION expressed as a runnable leader trajectory -- enough to drive an ego in closed
loop downstream and recompute gap and closing speed. x_leader integrates v_leader with the SAME forward-Euler
rule the engine uses for the gap (stepper.py:88), anchored at s_init, so gap = x_leader - x_ego with
x_ego(0)=0. Pure (no Qt). The .mat path uses the dependency-free writer (scipy is absent)."""
import numpy as np

from config import DT
from sim.mat_writer import write_mat


def leader_kinematics(scenario, dt=DT):
    v = np.asarray(scenario.v_leader, dtype=float)
    t = np.arange(v.size) * dt
    x = float(scenario.s_init) + dt * np.concatenate(([0.0], np.cumsum(v)[:-1]))   # forward Euler, x[0]=s_init
    a = np.diff(v, prepend=v[0]) / dt                                              # backward diff, a[0]=0
    return {"t": t, "v_leader": v, "x_leader": x, "a_leader": a}


def scenario_metadata(scenario, dt=DT):
    v = np.asarray(scenario.v_leader, dtype=float)
    meta = {"name": scenario.name, "dt": float(dt), "N": int(v.size),
            "s_init": float(scenario.s_init), "v_init": float(scenario.v_init),
            "params_gt": np.asarray(scenario.params_gt, dtype=float)}
    if scenario.cut_in is not None:
        meta["cut_in"] = np.asarray(scenario.cut_in, dtype=float)
    return meta


def write_scenario_csv(scenario, path, dt=DT):
    k = leader_kinematics(scenario, dt)
    m = scenario_metadata(scenario, dt)
    pg = m["params_gt"]
    cols = np.column_stack([k["t"], k["v_leader"], k["x_leader"], k["a_leader"]])
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(f"# scenario: {m['name']}\n")
        f.write(f"# dt={m['dt']} N={m['N']} s_init={m['s_init']} v_init={m['v_init']}\n")
        f.write(f"# params_gt: v0={pg[0]} T={pg[1]} s0={pg[2]} a={pg[3]} b={pg[4]}\n")
        if "cut_in" in m:
            f.write(f"# cut_in: {m['cut_in'][0]},{m['cut_in'][1]}\n")
        f.write("t,v_leader,x_leader,a_leader\n")
        np.savetxt(f, cols, delimiter=",")


def write_scenario_mat(scenario, path, dt=DT):
    k = leader_kinematics(scenario, dt)
    m = scenario_metadata(scenario, dt)
    variables = {**k, "name": m["name"], "dt": m["dt"], "N": float(m["N"]),
                 "s_init": m["s_init"], "v_init": m["v_init"], "params_gt": m["params_gt"]}
    if "cut_in" in m:
        variables["cut_in"] = m["cut_in"]
    write_mat(path, variables)
