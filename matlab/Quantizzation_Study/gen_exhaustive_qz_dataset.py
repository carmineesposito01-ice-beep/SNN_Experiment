"""[Quantizzation_Study] Genera il dataset ESAUSTIVO per la validazione car-following della quantizzazione.

USA IL GENERATORE CANONICO del Simulator (nessuna copia, nessun drift):
  - utils.closed_loop_eval.build_scenarios  -> i 9 scenari canonici (5 storici + 4 coda/OoD), INCLUSI
    i 3 cut-in a teletrasporto di gap (cut_in, cut_out, aggressive_cut_in) e le frenate estreme
    (hard_brake -7, panic_stop -9). E' la funzione su cui girano i report del progetto (INVARIANTE).
  - data.generator._sample_scenario         -> campionatore realistico di params_gt (v0,T,s0,a,b) per
    regime (highway/urban/truck/mixed), la stessa distribuzione-label del champion.

Output: exhaustive_scenarios.json (letto poi da qz_build_exhaustive_dataset.m che assembla il .mat).
Il .mat NON si scrive qui: il writer dependency-free del Simulator appiattisce a 1xN (niente cell/struct).

Provenienza: richiede il worktree Simulator sul path (canonical build_scenarios). Argomento opzionale = SIM_ROOT.
Esecuzione:  set KMP_DUPLICATE_LIB_OK=TRUE (OMP #15: torch porta il suo OMP) & python gen_exhaustive_qz_dataset.py
"""
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")   # OMP #15 guard (torch import)
os.environ.setdefault("OMP_NUM_THREADS", "1")
import json
import sys
from collections import Counter

SIM_ROOT = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator"
sys.path.insert(0, SIM_ROOT)

import numpy as np
from utils.closed_loop_eval import build_scenarios      # canonical, invariant
from data.generator import _sample_scenario             # realistic params_gt sampler

N = 600            # lunghezza canonica di build_scenarios (cut-in a t=N//2=300)
SEED = 12345
HERE = os.path.dirname(os.path.abspath(__file__))

# 11 estrazioni di params_gt che coprono i regimi (label-distribution del champion) -> 11 x 9 = 99 traiettorie
REGIMES = ["highway"] * 3 + ["urban"] * 3 + ["truck"] * 2 + ["mixed"] * 3
rng = np.random.default_rng(SEED)
draws = []
for reg in REGIMES:
    p, _prof, _stype, _cut = _sample_scenario(rng, {reg: 1.0}, 0.0)
    draws.append((reg, [float(p["v0"]), float(p["T"]), float(p["s0"]), float(p["a"]), float(p["b"])]))

trajs = []
for di, (reg, pg) in enumerate(draws):
    scen = build_scenarios(np.asarray(pg, dtype=float), N=N,
                           rng=np.random.default_rng(SEED + 1 + di), include_tail=True)
    for (name, vl, s_i, v_i, cut) in scen:
        trajs.append({
            "name": name, "regime": reg, "param_draw": di,
            "v_leader": [float(x) for x in np.asarray(vl)],
            "s_init": float(s_i), "v_init": float(v_i),
            "gt_params": [float(x) for x in pg],           # v0,T,s0,a,b
            "cut_in": ([int(cut[0]), float(cut[1])] if cut is not None else None),
        })

scen_names = [t["name"] for t in trajs[:9]]
out = {"meta": {"N": N, "dt": 0.1, "seed": SEED, "n_traj": len(trajs),
                "n_param_draws": len(draws), "regimes": REGIMES,
                "scenarios": scen_names, "source": "utils.closed_loop_eval.build_scenarios (canonical)"},
       "trajectories": trajs}
path = os.path.join(HERE, "exhaustive_scenarios.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(out, f)

print(f"wrote {len(trajs)} trajectories -> {path}")
print("composizione per scenario:", dict(Counter(t["name"] for t in trajs)))
print("con evento cut-in (teletrasporto gap):",
      dict(Counter(t["name"] for t in trajs if t["cut_in"] is not None)))
print("regimi params_gt:", dict(Counter(t["regime"] for t in trajs)))
