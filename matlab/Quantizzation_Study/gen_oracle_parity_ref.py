"""[Quantizzation_Study] Cancello-chiave: riferimento ORACOLO dal motore canonico Python (simulate()).

Per provare che qz_cl_sim (port MATLAB) combacia numericamente con utils/closed_loop_eval.simulate():
gira l'ORACOLO (model=None -> usa params_gt costanti) sui 9 scenari della PRIMA estrazione di params del
dataset esaustivo, ed esporta la serie del gap s(t) + collided + min_gap. MATLAB rigira lo stesso oracolo
(qz_cl_sim + acc_iidm_open double) e confronta: se |Δs| e' al livello del float e i flag combaciano, il port
e' fedele. Stesse condizioni iniziali/leader del dataset (rilette dal JSON) -> confronto uno-a-uno.
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import json
import sys

SIM_ROOT = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator"
sys.path.insert(0, SIM_ROOT)

import numpy as np
from utils.closed_loop_eval import simulate

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "exhaustive_scenarios.json"), encoding="utf-8"))
tr = d["trajectories"]

# prima estrazione di params (param_draw == 0): i 9 scenari con lo stesso params_gt
sel = [t for t in tr if t["param_draw"] == 0]
ref = []
for t in sel:
    cut = None if t["cut_in"] is None else (int(t["cut_in"][0]), float(t["cut_in"][1]))
    out = simulate(None, np.asarray(t["gt_params"]), np.asarray(t["v_leader"]),
                   t["s_init"], t["v_init"], cut_in=cut)     # model=None => ORACOLO
    ref.append({"name": t["name"], "s": [float(x) for x in out["s"]],
                "collided": bool(out["collided"]), "min_gap": float(out["min_gap"]),
                "N": int(len(out["s"]))})

path = os.path.join(HERE, "oracle_parity_ref.json")
json.dump({"trajectories": ref}, open(path, "w", encoding="utf-8"))
print(f"wrote {len(ref)} oracle reference series -> {path}")
for r in ref:
    print(f"  {r['name']:18s} N={r['N']:4d} collided={int(r['collided'])} min_gap={r['min_gap']:.4f}")
