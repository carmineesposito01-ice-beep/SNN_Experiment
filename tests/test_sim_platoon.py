import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from utils.champion_io import load_champion            # noqa: E402
from sim.ui.platoon import batched_forward, run_platoon, run_ring   # noqa: E402

BASE = os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt")
EVENT = os.path.join(REPO, "champions", "PE_t05_gp0002", "best_model.pt")
_PG = np.array([30.0, 1.5, 2.0, 1.5, 1.5])


def test_batched_forward_batch_independent_eventprop():
    fw = batched_forward(load_champion(EVENT), 3)
    fw.reset(3)
    gap = np.full(3, 20.0); v = np.full(3, 15.0); dv = np.zeros(3); vl = np.full(3, 15.0)
    out = fw.infer(gap, v, dv, vl).detach().cpu().numpy()   # identical obs -> identical rows (batch indep.)
    assert out.shape == (3, 5)
    assert np.allclose(out[0], out[1]) and np.allclose(out[1], out[2])


def test_batched_forward_matches_single_eventprop():
    # a batch-of-1 batched forward must equal the plain single-vehicle EventPropStepper on a sequence
    from sim.eventprop_stepper import EventPropStepper
    import torch
    from utils.platoon_eval import _norm_obs_batch
    m = load_champion(EVENT).model
    ref = EventPropStepper(m); ref.reset(1, "cpu")
    fw = batched_forward(load_champion(EVENT), 1); fw.reset(1)
    for gv in ([20.0, 15.0, 0.0, 15.0], [18.0, 16.0, 1.0, 15.0], [22.0, 14.0, -1.0, 15.0]):
        g, vv, d, vl = ([x] for x in gv)
        r = ref.step(_norm_obs_batch(np.array(g), np.array(vv), np.array(d), np.array(vl)))
        o = fw.infer(np.array(g), np.array(vv), np.array(d), np.array(vl))
        assert np.allclose(r.detach().numpy(), o.detach().numpy())


def test_run_platoon_shapes_both_families():
    for path in (BASE, EVENT):
        rec = run_platoon(load_champion(path), _PG, n_vehicles=6, v_leader_profile=np.full(60, 21.0))
        assert rec["v"].shape == (60, 6) and "gap" in rec and "v_leader" in rec


def test_run_ring_shapes_both_families():
    for path in (BASE, EVENT):
        rec = run_ring(load_champion(path), _PG, n_vehicles=8, ring_length=400.0, n_steps=60)
        assert rec["v"].shape == (60, 8) and "density" in rec


def test_simulate_platoon_records_params():
    # T4: simulate_platoon additively records the 5 params each vehicle's SNN produces (T,N,5)
    rec = run_platoon(load_champion(BASE), _PG, n_vehicles=5, v_leader_profile=np.full(40, 21.0))
    assert rec["params"].shape == (40, 5, 5) and np.isfinite(rec["params"]).all()


def test_run_fundamental_diagram_both_families():
    # T4: family-aware fundamental diagram via run_ring (NOT platoon_eval.fundamental_diagram)
    from sim.ui.platoon import run_fundamental_diagram
    for path in (BASE, EVENT):
        pts = run_fundamental_diagram(load_champion(path), _PG, [20.0, 60.0],
                                      ring_length=300.0, n_steps=60)
        assert len(pts) == 2
        for p in pts:
            assert {"rho_veh_km", "Q_veh_h", "V_km_h", "n", "wave_std", "unstable"} <= p.keys()
            assert p["Q_veh_h"] >= 0.0 and p["n"] >= 2
