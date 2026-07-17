# Dataset generator 7b — Plan A: the ENGINE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Turn a leader scenario built in the simulator into the `.pt` cache that `train.py --data_cache <ours>`
eats with zero modifications, using the champions' real physics.

**Architecture:** One additive, default-off parameter (`v_leader=None`) opens `simulate_trajectory` to an
external leader. A mix row `(family, source, regime, weight)` says *"this leader, params from this regime, this
weight"*: the regime gives the params (**the labels**) by reusing `_sample_scenario` verbatim; the family gives
the leader. `built`/`preset` inject; `generator`/`cut_in` go down the untouched standard path.

**Tech Stack:** Python, numpy, torch (only to write the `.pt`), pytest. **No scipy, no LAPACK, no new compiled
deps** (this env aborts with OMP #15).

**Spec:** `docs/superpowers/specs/2026-07-17-dataset-generator-7b-design.md` (approved 2026-07-17).

---

## Read before you start

**Runner — never `conda run`** (it crashes conda's plugin system intermittently):

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest <target> -q -p no:cacheprovider
```

**The suite is the SIM glob** — `pytest tests/test_sim_*.py tests/test_champion_io.py`, **NEVER `pytest tests/`**
(`tests/test_fpga_io.py` calls `sys.exit()` at import → `INTERNALERROR> SystemExit`).

⚠️ **The full suite takes ~3–4 min → give it ≥420 s or background it — and run NOTHING else meanwhile.**
`test_custom_composer_refresh_fits_in_a_frame` asserts a wall-clock peak; a render script run in parallel
reddened it once on a diff that cannot touch the composer.

**Commits:** conventional, **no `Co-Authored-By`**. **Do not merge to main** — it is parked.

**The invariant changed shape.** In 7a the gate was an empty `git diff` on `data/generator.py`. Here that file
changes **on purpose** → the gate becomes **`tests/test_sim_provenance.py`** (stronger than a diff: it compares
*output*, not text). Still empty-diff invariants: `sim/{state,stepper,backend,probe,events,eventprop_stepper}.py`,
`utils/closed_loop_eval.py`, `sim/scenario_spec.py`.
**`train.py` is NOT touched.** If a task finds itself editing it, stop — the design was wrong.

**Verified APIs — do not re-derive them:**
- `data/generator.py`: `simulate_trajectory(params, profile='sinusoidal', seed=None, noise_scale=1.0)` (`:252`)
  · `simulate_cut_in_trajectory(params, profile, seed, noise_scale)` (`:338`)
  · `_sample_scenario(rng, scenario_mix=None, cut_in_ratio=None) -> (p, prof, stype, is_cutin)` (`:520`)
  · `normalize(traj) -> (x_norm, y_phys, mask)` (`:447`) · `generate_dataset(n, base_seed, scenario_mix,
  cut_in_ratio, noise_scale, wide_params)` (`:598`).
  **`traj[i] = [s, v, dv_true, v_l_true, v_dot, T_cur, mask]` (`:329`) → column 3 IS the true leader**, not the
  perceived one: that is what makes the injection provable and the shape-gate exact.
- `config.py`: `DT=0.1` (`:63`), `SIM_DURATION=120.0` (`:121`) → N=1200, `WARMUP_DURATION=20.0` (`:122`) → 200
  → **1000 usable ticks**, `IDM_HWY = dict(v0=33.3, T=1.2, s0=2.5, a=1.1, b=1.5, delta=4)` (`:66`).
- `train.py`: `CFDataset(dataset_list, seq_len=100, stride=50)` (`:111`), windows **each trajectory alone**
  (`while start + seq_len <= N`, `:150-159`). `from train import CFDataset` **imports cleanly in ~3.2 s, no side
  effects** (verified). Cache: `torch.save({'train': [...], 'val': [...], 'seed': SEED}, path)` (`:1462`).
- 7a: `sim/dataset_mix.py` → `MixEntry`, `validate_mix(mix)`, `quotas(mix, count)` · `sim/jitter.py` →
  `jitter_spec(spec, rng, strength)` (**strength=0 = the identity**, proven) · `sim/dataset_gen.py` →
  `GENERATOR_PROFILES` · `sim/scenario_spec.py` → `materialise(spec, params_gt, N)`, `Block`, `LeaderStyle`,
  `ScenarioSpec`, `_PRESET_N = 600`.
- **`params_gt` is the 5-array `[v0, T, s0, a, b]`** — order from `CF_FSNN_Net._PARAM_BOUNDS`
  (`core/network.py:323-329`). `_sample_scenario` returns a **dict** that also carries `delta` (the IDM
  exponent, not a learned param): it does **not** go in the array.

**Two traps this plan is built around:**
1. **`quotas()` calls `validate_mix()` internally**, and that rejects any family outside
   `("built","preset","generator")` → passing a `cut_in` row would **raise**. Task 3 adds an additive
   `families=FAMILIES` parameter. **Churn enumerated: 13 call sites** (`dataset_gen.py:81,82`,
   `dataset_page.py:254,275`, `test_sim_dataset_mix.py:16,24,31,32,37,39`, `test_sim_dataset_page.py:89`) —
   **all keep working untouched**, because the default preserves today's behaviour.
2. **The rng is shared** between `_leader_profile` and the OU/packet-loss stream (`generator.py:273-276`), and
   each profile draws a different number of values. Injecting skips those draws → *"same seed, different
   leader, same noise"* is **not true and must not be asserted**: such a test would fail on correct code.

---

## File structure

| File | Responsibility |
|---|---|
| `data/generator.py` **(modify, +4 lines)** | The one injection site: `v_leader=None` on `simulate_trajectory`. Additive, default-off — the `wide_params=False` mould already in this file. |
| `sim/dataset_mix.py` **(modify)** | `families=FAMILIES` parameter on `validate_mix`/`quotas`. Additive; zero churn. |
| `sim/train_mix.py` **(new)** | The 4-field row, the training families/regimes, validation, exact quotas. Pure. |
| `sim/train_gen.py` **(new)** | The sampler (regime → labels, family → leader), the 8-key dict, window counting, the shape gate, the two batches, the `.pt` writer. |
| `tests/test_sim_provenance.py` **(new)** | **The risk guardian.** The live generator still reproduces the champion's dataset byte-for-byte. |
| `tests/test_sim_train_mix.py` **(new)** | The row + quotas + validation. |
| `tests/test_sim_train_gen.py` **(new)** | Injection, labels, the contract against the REAL `CFDataset`, windows, gates, cache. |

**What of the spec is NOT in this plan, and why:** constraint 3 (the frequency knob disabled) needs no engine
work — the training path simply never decimates, so there is nothing to switch off; it is a UI affordance and
belongs to Plan B. The ETA and Cancel *button* are Plan B too, but the engine must give them something to stand
on: **Cancel** is the `on_progress → False` contract (Task 6) and the **ETA** is `SECONDS_PER_TRAJ` (Task 6).
The `.pt` bytes/tick that Plan B's size estimate needs is **printed by Task 7's functional verify** — measured,
like 7a's, never guessed.

---

### Task 1: The risk guardian — before touching anything

The provenance test must exist **before** the edit it guards. It is a **characterisation test**, not a
red-green: it is green today and must stay green. Its RED is produced by sabotage in Step 4.

**Files:**
- Create: `tests/test_sim_provenance.py`

- [ ] **Step 0: Confirm the baseline**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulator"
git log --oneline -1 && git status --short
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -q -p no:cacheprovider
```
Expected: `345 passed`, clean tree, HEAD `f6617c8f`. If not 345, stop and find out why before continuing.

- [ ] **Step 1: Write the test**

```python
"""The risk guardian: data/generator.py is the champions' training-data provenance, and 7b modifies it.

This does not compare TEXT (the live file is already 56 lines ahead of every archived copy -- the `launch`
profile, the `freeflow`/`launch` regimes, `_PHYS_BOUNDS`, `wide_params=False`; all additive, all default-off).
It compares OUTPUT: same seed -> the same dataset the champion was trained on, byte for byte. That is the
question that matters, and this makes it answerable instead of a matter of faith.

Both branches are covered: cut_in_ratio=None is config's 0.20 (which drew 0 cut-ins in 8 scenarios -- the first
run of this probe was incomplete until 1.0 forced the other branch)."""
import importlib.util
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import config                                     # noqa: E402,F401
from data.generator import generate_dataset       # noqa: E402

FROZEN = os.path.join(REPO, "Arch_Tested", "R24F_MIXED_lr0.5_V08_TRUE_CHAMPION", "data", "generator.py")


@pytest.fixture(scope="module")
def frozen():
    """The champion's archived generator, loaded under its own module name.

    It does `from config import ...`; `config` is already in sys.modules (imported above) so it binds to the
    LIVE one -- which is fine and deliberate: the archived config.py is byte-identical to the live one
    (verified), so the generator is the only moving part."""
    assert os.path.isfile(FROZEN), f"copia congelata assente: {FROZEN}"
    spec = importlib.util.spec_from_file_location("frozen_generator", FROZEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _same(a, b):
    return (np.array_equal(a["raw"], b["raw"]) and np.array_equal(a["x"], b["x"])
            and np.array_equal(a["y"], b["y"]) and np.array_equal(a["mask"], b["mask"])
            and a["params"] == b["params"]
            and (a["profile"], a["scenario"], a["cut_in"]) == (b["profile"], b["scenario"], b["cut_in"]))


@pytest.mark.parametrize("cut_in_ratio", [None, 1.0])
def test_the_live_generator_still_reproduces_the_champions_dataset(frozen, cut_in_ratio):
    n = 8
    live = generate_dataset(n, base_seed=42, cut_in_ratio=cut_in_ratio)
    froz = frozen.generate_dataset(n, base_seed=42, cut_in_ratio=cut_in_ratio)
    bad = [i for i in range(n) if not _same(live[i], froz[i])]
    assert bad == [], (f"la provenienza si e' MOSSA su {len(bad)}/{n} scenari (indici {bad}, "
                       f"cut_in_ratio={cut_in_ratio}): data/generator.py non produce piu' il dataset "
                       f"su cui i champion sono stati addestrati.")
```

- [ ] **Step 2: Run it — it must PASS (it is a characterisation test)**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_provenance.py -q -p no:cacheprovider
```
Expected: `2 passed` in ~5 s.

- [ ] **Step 3: Prove it can fail — sabotage BOTH branches, one at a time**

⚠️ **Corrected during execution (2026-07-17):** the two `cut_in_ratio` cases run through **two independent
functions**, each with its own copy of `v = params['v0'] * 0.8` — `simulate_trajectory:280` (the `None` case)
and `simulate_cut_in_trajectory:385` (the `1.0` case). A single edit therefore reddens **only one** parametrised
case, not both. The plan originally said "2 failed" from the line-280 edit alone — that was **unreachable**.
Prove each branch is sensitive to its own path, in isolation:

- Sabotage `data/generator.py:280` (`* 0.8` → `* 0.81`): expect `[None]` **RED `8/8`**, `[1.0]` green. Revert.
- Sabotage `data/generator.py:385` (`* 0.8` → `* 0.81`): expect `[1.0]` **RED `8/8`**, `[None]` green. Revert.

Both use a **value-level** sabotage (a shape-level one would be weak — it would fail on a shape error, not on
the property). The `v = params['v0'] * 0.8` string is **not unique** (two sites) → use Edit with enough
surrounding context to target the right line, never a blind `replace()`.

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_provenance.py -q -p no:cacheprovider
```

The `[None]`-RED-on-line-280 result doubles as proof that all 8 default scenarios route through
`simulate_trajectory` (had any been a cut-in, it would have gone through the untouched twin and stayed
identical) — i.e. "0 cut-ins drawn in 8 scenarios at the default ratio" is **measured, not assumed**.

- [ ] **Step 4: Revert the sabotage and confirm green**

```bash
git checkout data/generator.py
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_provenance.py -q -p no:cacheprovider
```
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_sim_provenance.py
git commit -m "test(sim): il guardiano della provenienza -- il generatore vivo riproduce ancora il dataset del champion

Confronta l'OUTPUT, non il testo: il file vivo e' gia' 56 righe avanti a
ogni copia archiviata (launch, freeflow, _PHYS_BOUNDS, wide_params), tutte
additive e default-off. 8/8 byte-identici su entrambi i rami. Esiste PRIMA
della modifica del 7b, perche' un cancello messo dopo non e' un cancello."
```

---

### Task 2: The injection — one site, additive, default-off

**Files:**
- Modify: `data/generator.py:252-276`
- Create: `tests/test_sim_train_gen.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run — expect FAIL**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_train_gen.py -q -p no:cacheprovider
```
Expected: **2 failed**, `TypeError: simulate_trajectory() got an unexpected keyword argument 'v_leader'`.

- [ ] **Step 3: Implement — use Edit, not `replace()`** (a non-matching `replace()` fails **silently**)

Edit the signature at `data/generator.py:252`:

```python
def simulate_trajectory(params, profile='sinusoidal', seed=None, noise_scale=1.0, v_leader=None):
```

Append to its docstring, before the closing `"""`:

```
    7b — v_leader (default None): un profilo leader ESTERNO. Con None il profilo si costruisce
    internamente esattamente come prima (percorso di default byte-identico: lo tiene
    tests/test_sim_provenance.py contro la copia congelata del champion). Se dato, N segue la sua
    lunghezza e _leader_profile NON viene chiamato -- e siccome l'rng e' CONDIVISO con OU/packet-loss,
    il rumore a valle non e' quello che lo stesso seed darebbe con un profilo.
    Stampo additivo default-off: lo stesso di wide_params in generate_dataset().
```

Replace lines 274-276:

```python
    N   = int(SIM_DURATION / DT) if v_leader is None else len(v_leader)

    if v_leader is None:
        v_l_profile = _leader_profile(profile, N, DT, rng, params['v0'])
    else:
        v_l_profile = np.asarray(v_leader, dtype=np.float32)
```

- [ ] **Step 4: Run — expect PASS, and the guardian must still hold**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_train_gen.py tests/test_sim_provenance.py -q -p no:cacheprovider
```
Expected: `4 passed`. **If the provenance test goes red here, stop**: the injection moved the default path and
the whole risk argument collapses.

- [ ] **Step 5: Commit**

```bash
git add data/generator.py tests/test_sim_train_gen.py
git commit -m "feat(data): simulate_trajectory accetta un leader esterno (additivo, default-off)

v_leader=None -> percorso identico a prima, riga per riga. Un solo sito:
simulate_cut_in_trajectory NON si tocca (il cut-in scarta il leader da
t_cutin in poi, quindi iniettarlo li' sprecherebbe il design).
La prova che l'iniezione attecchisce e' traj[:,3] == v_leader; la prova
che il default non si e' mosso e' il test di provenienza, ancora 8/8."
```

---

### Task 3: The mix — a families parameter, then the 4-field row

**Files:**
- Modify: `sim/dataset_mix.py:18-41`
- Create: `sim/train_mix.py`, `tests/test_sim_train_mix.py`

- [ ] **Step 1: Write the failing test**

```python
"""The training mix: (leader, labels, weight) in one row, with exact quotas."""
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from sim.train_mix import FAMILIES_TRAIN, REGIMES, TrainMixEntry, train_quotas, validate_train_mix  # noqa: E402


def _mix():
    return [TrainMixEntry("built", "mine", "launch", 30.0),
            TrainMixEntry("generator", "sinusoidal", "highway", 50.0),
            TrainMixEntry("cut_in", "sinusoidal", "urban", 20.0)]


def test_cut_in_is_a_family_of_the_training_mix():
    """The user's call: cut-in is a ROW, not a hidden global ratio. quotas() gives exactly 20 of 100 where the
    generator's `rng.random() < 0.20` gives 20 in expectation."""
    assert "cut_in" in FAMILIES_TRAIN
    assert train_quotas(_mix(), 100) == [30, 50, 20]


def test_the_quotas_are_exact_even_when_they_do_not_divide():
    mix = [TrainMixEntry("generator", "constant", "highway", 100.0 / 3),
           TrainMixEntry("generator", "free", "freeflow", 100.0 / 3),
           TrainMixEntry("cut_in", "sinusoidal", "urban", 100.0 / 3)]
    q = train_quotas(mix, 100)
    assert sum(q) == 100 and sorted(q) == [33, 33, 34]


def test_an_unknown_regime_is_refused_by_name():
    with pytest.raises(ValueError, match="regime sconosciuto"):
        validate_train_mix([TrainMixEntry("generator", "constant", "autostrada", 100.0)])


def test_the_regimes_are_the_generators_own():
    assert REGIMES == ("highway", "urban", "truck", "mixed", "freeflow", "launch")


def test_the_7a_mix_is_untouched_by_the_families_parameter():
    """The additive default must leave 7a exactly as it was: cut_in is NOT an analysis family."""
    from sim.dataset_mix import MixEntry, validate_mix
    with pytest.raises(ValueError, match="famiglia sconosciuta"):
        validate_mix([MixEntry("cut_in", "sinusoidal", 100.0)])
```

- [ ] **Step 2: Run — expect FAIL**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_train_mix.py -q -p no:cacheprovider
```
Expected: **collection error**, `ModuleNotFoundError: No module named 'sim.train_mix'`.

- [ ] **Step 3a: Add the additive parameter to `sim/dataset_mix.py`**

Replace `validate_mix` and `quotas` (`:18-41`) with:

```python
def validate_mix(mix, families=FAMILIES):
    """Raise ValueError unless the mix is non-empty, every family is known, and the weights total 100.

    `families` (default: 7a's three) is additive so 7b can reuse this arithmetic with its own vocabulary --
    cut_in is a training family only. Every existing caller passes nothing and gets today's behaviour."""
    if not mix:
        raise ValueError("mix vuoto")
    for e in mix:
        if e.family not in families:
            raise ValueError(f"famiglia sconosciuta: {e.family!r} (valide: {families})")
        if e.weight < 0:
            raise ValueError(f"peso negativo: {e.weight}")
    total = sum(e.weight for e in mix)
    if abs(total - 100.0) > 0.01:
        raise ValueError(f"i pesi non sommano a 100 (somma={total:.2f})")


def quotas(mix, count, families=FAMILIES):
    """Exact per-entry counts summing to `count` (largest remainder for the leftovers)."""
    validate_mix(mix, families)
    raw = [e.weight / 100.0 * count for e in mix]
    base = [int(x) for x in raw]
    left = count - sum(base)
    order = sorted(range(len(mix)), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[:left]:
        base[i] += 1
    return base
```

- [ ] **Step 3b: Create `sim/train_mix.py`**

```python
"""The training mix: one row = one sentence -- "this leader, params from this regime, this weight".

The two axes are orthogonal by construction. In the real generator `_sample_scenario` derives BOTH the params
and the leader profile from the regime; injecting a v_leader overrides the profile half and leaves the params
half -- which is the half that matters here, because in a training set the params ARE the labels.

cut_in is a FAMILY, not a global ratio. Three reasons, in order: quotas() gives exactly 20 of 100 where the
generator's `rng.random() < 0.20` gives 20 in expectation; a row you can see beats a dice roll you cannot; and
it keeps ONE injection site, which is what we want anyway -- a cut-in replaces the leader from t_cutin on, so
injecting a designed profile there would throw most of it away."""
from dataclasses import dataclass

from sim.dataset_mix import quotas as _quotas
from sim.dataset_mix import validate_mix as _validate_families

FAMILIES_TRAIN = ("built", "preset", "generator", "cut_in")
REGIMES = ("highway", "urban", "truck", "mixed", "freeflow", "launch")


@dataclass(frozen=True)
class TrainMixEntry:
    family: str      # one of FAMILIES_TRAIN
    source: str      # a built name | a preset name | a leader profile (generator, and cut_in's leader A)
    regime: str      # one of REGIMES -- gives the params, i.e. THE LABELS
    weight: float    # percent; the mix must total 100


def validate_train_mix(mix):
    """Family + weights via 7a's arithmetic; the regime is 7b's own axis."""
    _validate_families(mix, FAMILIES_TRAIN)
    for e in mix:
        if e.regime not in REGIMES:
            raise ValueError(f"regime sconosciuto: {e.regime!r} (validi: {REGIMES})")


def train_quotas(mix, count):
    """Exact per-row counts summing to `count`."""
    validate_train_mix(mix)
    return _quotas(mix, count, FAMILIES_TRAIN)
```

- [ ] **Step 4: Run — expect PASS, and 7a must be untouched**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_train_mix.py tests/test_sim_dataset_mix.py tests/test_sim_dataset_gen.py -q -p no:cacheprovider
```
Expected: all pass (5 new + 7a's existing). The 13 enumerated call sites are untouched because the default
preserves today's behaviour.

- [ ] **Step 5: Prove the sabotage bites**

In `sim/train_mix.py`, change `_validate_families(mix, FAMILIES_TRAIN)` to `_validate_families(mix)`.
Run the same command: expected **FAIL** with `famiglia sconosciuta: 'cut_in'` — this is the trap the plan is
built around, made visible. Revert it and re-run: green.

- [ ] **Step 6: Commit**

```bash
git add sim/dataset_mix.py sim/train_mix.py tests/test_sim_train_mix.py
git commit -m "feat(sim): il mix di training -- la riga dice leader, etichette e peso

quotas() chiama validate_mix() dentro, che rifiutava ogni famiglia fuori
dalle tre del 7a: con cut_in avrebbe sollevato. Il parametro families e'
additivo col default di oggi -> i 13 siti chiamanti restano intatti."
```

---

### Task 4: The sampler — the regime gives the labels, the family gives the leader

**Files:**
- Create: `sim/train_gen.py`
- Modify: `tests/test_sim_train_gen.py` (append)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_sim_train_gen.py`)

```python
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
```

- [ ] **Step 2: Run — expect FAIL**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_train_gen.py -q -p no:cacheprovider
```
Expected: FAIL, `ModuleNotFoundError: No module named 'sim.train_gen'`.

- [ ] **Step 3: Create `sim/train_gen.py`**

```python
"""The training sink: a mix row -> the dict train.py's CFDataset eats, via the champions' real physics.

Two rules shape everything here:
  - The regime gives the params and the params ARE the labels. _sample_scenario is reused VERBATIM (the regime
    forced through its own scenario_mix parameter) so the ranges cannot drift from the champions'.
  - The family gives the leader. built/preset inject; generator/cut_in go down the STANDARD path untouched --
    so a mix of only those reproduces the standard dataset.

The strength slider therefore governs the LEADER only. Jittering the params here would break the
correspondence with the champions' label distribution: closed by construction, not by a warning."""
import numpy as np

from config import DT, SIM_DURATION, WARMUP_DURATION
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
```

- [ ] **Step 4: Run — expect PASS**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_train_gen.py -q -p no:cacheprovider
```
Expected: `8 passed`.

- [ ] **Step 5: Prove the sabotage bites**

In `params_for_regime`, change `_sample_scenario(rng, {regime: 1.0}, 0.0)` to `_sample_scenario(rng, None, 0.0)`
(config's default mix instead of the forced regime). Run: expected **FAIL** —
`RuntimeError: il regime non e' stato forzato` and/or the `v0` range assertions. This is a **value-level**
sabotage: the labels would be drawn from the wrong regime, which is exactly the silent lie the design fears.
Revert and re-run: green.

- [ ] **Step 6: Commit**

```bash
git add sim/train_gen.py tests/test_sim_train_gen.py
git commit -m "feat(sim): il campionatore -- il regime da' le etichette, la famiglia da' il leader

_sample_scenario riusato VERBATIM forzando il regime col suo stesso
parametro: i range per-regime restano quelli dei champion invece di
diventare una nostra copia che puo' divergere. generator/cut_in non
iniettano affatto -> un mix di sole quelle riproduce il dataset standard.
Uno scenario sotto i 300 tick e' RIFIUTATO: CFDataset ne farebbe zero
finestre in silenzio."
```

---

### Task 5: The windows — counted by the real `CFDataset`, not by our formula

**Files:**
- Modify: `sim/train_gen.py` (append `windows_per_traj`)
- Modify: `tests/test_sim_train_gen.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run — expect FAIL**

Expected: `ImportError: cannot import name 'windows_per_traj'`.

- [ ] **Step 3: Implement** — append to `sim/train_gen.py`:

```python
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
```

- [ ] **Step 4: Run — expect PASS** (`5 passed` for the new ones; the file totals 13)

- [ ] **Step 5: Commit**

```bash
git add sim/train_gen.py tests/test_sim_train_gen.py
git commit -m "feat(sim): il conteggio delle finestre, verificato contro la CFDataset vera

La quota che l'utente sceglie e' in traiettorie; il training mangia
finestre. 1000 tick -> 19 a stride 50 (train) ma 10 a stride 100 (val):
la formula la conta la classe vera, non la mia memoria."
```

---

### Task 6: The batch — two splits, the shape gate, cancel, and the cache

**Files:**
- Modify: `sim/train_gen.py` (append)
- Modify: `tests/test_sim_train_gen.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run — expect FAIL** (`ImportError: cannot import name 'build_training_cache'`)

- [ ] **Step 3: Implement** — append to `sim/train_gen.py`:

```python
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
```

Add to the imports at the top of `sim/train_gen.py`:

```python
import os

from sim.train_mix import train_quotas, validate_train_mix
```

- [ ] **Step 4: Run — expect PASS** (`17 passed` in the file)

- [ ] **Step 5: Prove the sabotage bites**

In `build_training_cache`, change `build_split(effective_val_mix, n_val, seed + 1, ...)` to
`seed` (instead of `seed + 1`). Run: `test_the_two_batches_are_disjoint...` must **FAIL** — train and val would
be the same draws. Revert and re-run: green.

- [ ] **Step 6: Commit**

```bash
git add sim/train_gen.py tests/test_sim_train_gen.py
git commit -m "feat(sim): i due batch, il cancello delle forme, l'annullamento e la cache .pt

Seed S e S+1 come fa train.py: due campioni i.i.d., disgiunti per
costruzione. Il modo new_shapes verifica la PROPRIETA' (nessun leader
del val identico a uno del train) invece del proxy 'jitter > 0', che
sarebbe sbagliato in entrambe le direzioni. Annullare non scrive NULLA:
un dataset a meta' che sembra intero e' il fallimento che cerchiamo.
La cache porta un manifest in una chiave additiva: train.py legge le tre
che conosce e ignora il resto."
```

---

### Task 7: Full suite, functional verify, docs, push

**Files:**
- Modify: `document/SIMULATOR_ARCHITECTURE.md`, `document/SIMULATOR_SESSION_RESUME.md`

- [ ] **Step 1: The full suite — quiet machine, nothing else running**

```bash
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_*.py tests/test_champion_io.py -q -rf -p no:cacheprovider
```
Expected: **345 + ~24 = ~369 passed, 0 failed**. Give it ≥420 s. If the composer budget test is the only red,
re-measure it alone before believing it.

- [ ] **Step 2: The invariants**

```bash
git diff --stat f6617c8f -- sim/state.py sim/stepper.py sim/backend.py sim/probe.py sim/events.py \
  sim/eventprop_stepper.py utils/closed_loop_eval.py sim/scenario_spec.py train.py
```
Expected: **empty**. `data/generator.py` is deliberately NOT in this list — its guard is
`tests/test_sim_provenance.py`. **`train.py` must be empty**; if it is not, the design was violated.

- [ ] **Step 3: Functional verify — a real cache, end to end**

Write `<scratchpad>/verify_7b_engine.py`:

```python
import os, sys, time
REPO = r"D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator"
os.chdir(REPO); sys.path.insert(0, REPO)
import torch
from sim.scenario_spec import Block, LeaderStyle, ScenarioSpec
from sim.train_gen import build_training_cache, windows_per_traj
from sim.train_mix import TrainMixEntry
from train import CFDataset

specs = {"mio": ScenarioSpec(name="mio", blocks=(Block("const", 400, {"v": 21.0}),
                                                 Block("ramp", 400, {"to_v": 8.0}),
                                                 Block("sine", 400, {"amp": 3.0, "period": 60.0})),
                             style=LeaderStyle(2.0, 4.0), s_init=33.5, v_init=21.0)}
mix = [TrainMixEntry("built", "mio", "launch", 40.0),
       TrainMixEntry("generator", "sinusoidal", "highway", 40.0),
       TrainMixEntry("cut_in", "sinusoidal", "urban", 20.0)]
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache_7b.pt")
t0 = time.perf_counter()
man = build_training_cache(mix, n_train=10, n_val=4, seed=42, strength=0.25, specs=specs, path=path,
                           on_progress=lambda d, t: print(f"\r  {d}/{t}", end="") or None)
dt = time.perf_counter() - t0
print(f"\nmanifest quotas : {man['quotas']}  (atteso [4, 4, 2])")
print(f"finestre        : train {man['windows_train']} · val {man['windows_val']}")
print(f"tempo           : {dt:.1f}s per 14 traiettorie -> {dt/14*5500/60:.1f} min per 5000+500")
blob = torch.load(path, weights_only=False)
ds = CFDataset(blob["train"], seq_len=100, stride=50)
print(f"CFDataset vera  : {len(ds)} finestre  (manifest dice {man['windows_train']})")
assert len(ds) == man["windows_train"], "il manifest mente sulle finestre"
fams = {d["leader_family"] for d in blob["train"]}
print(f"famiglie        : {sorted(fams)}")
print(f"scenari (=regimi): {sorted({d['scenario'] for d in blob['train']})}")
size = os.path.getsize(path)
ticks = sum(d["raw"].shape[0] for d in blob["train"]) + sum(d["raw"].shape[0] for d in blob["val"])
print(f"file            : {size/1e6:.1f} MB")
print(f"BYTES/TICK .pt  : {size/ticks:.1f}   <-- serve al Piano B per la stima; MISURATO, non stimato")
print("\nOK: il manifest e la CFDataset vera concordano.")
```

Run it and **paste the real numbers into the commit message**. Expected: quotas `[4, 4, 2]`, the window counts
agree, the scenario names are regimes (not our scenario names).

- [ ] **Step 4: Update the docs**

`document/SIMULATOR_ARCHITECTURE.md`: add rows for `sim/train_mix.py` and `sim/train_gen.py` (the regime→labels
/ family→leader split; injection only for built/preset; the exact-quota cut_in family; the window trap and that
the share depends on the stride; the shape gate checking the property not the proxy). **Add a
`data/generator.py` row**: it is no longer "called, never modified" — it now has ONE additive default-off
parameter, and its guard is `tests/test_sim_provenance.py`, not an empty diff. Update the "**`data/generator.py`
is CALLED, never modified**" paragraph accordingly — that sentence is now false and must not be left standing.
Bump the test count to the real number.

`document/SIMULATOR_SESSION_RESUME.md`: mark **7b Plan A (the engine) done** with the real count and commits;
note that the invariant for `data/generator.py` changed shape (provenance test, not empty diff); leave
**7b Plan B (the UI)** as the next item, pointing at the spec's §UI + the approved mock, and noting that the
mock predates constraint 4 (Cancel + ETA).

- [ ] **Step 5: Commit and push**

```bash
git add document/SIMULATOR_ARCHITECTURE.md document/SIMULATOR_SESSION_RESUME.md
git commit -m "docs(sim): resume + mappa -- il motore del 7b (Piano A) e' completo"
git push origin Simulator
```

- [ ] **Step 6: Report — do NOT merge to main**

Report Plan A complete with: the real test count, the provenance verdict (must be 8/8 **after** the edit — this
is the headline, not a footnote), the measured generation rate, and the functional-verify numbers. Merge → main
stays **parked**. Next: **Plan B (the UI)**, to be written after this lands.
