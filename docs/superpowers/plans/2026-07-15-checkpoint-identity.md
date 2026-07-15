# Checkpoint Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open any `.pt` and have the simulator state what it loaded and how sure it is — closing a bug that today silently drops 68 of 128 input synapses.

**Architecture:** A pure resolver (state-dict + optional sources → structured verdict with per-value provenance) sits under `load_champion`. The trainer starts writing an `arch` field so future checkpoints self-describe. The GUI gains a file browser and stops guessing the champion's name. No new topologies: unsupported variants are named and refused.

**Tech Stack:** Python 3, PyTorch, PySide6, pytest. Conda env `cf_sim`.

**Spec:** `docs/superpowers/specs/2026-07-15-checkpoint-identity-design.md` — read it first, especially the **asymmetric cross-check** table (an earlier draft had it backwards).

---

## Before you start

**Worktree:** `D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator`, branch `Simulator`, a git repo of its own.

**Test runner** (⚠️ never `conda run -n cf_sim python -m pytest` — it intermittently crashes conda's plugin system):

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_champion_io.py -q
```

**This cycle's full verification** = the 20 sim files **plus** `tests/test_champion_io.py` (which runs green in `cf_sim` — verified, 9 passed):

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest \
  tests/test_sim_state.py tests/test_sim_backend.py tests/test_sim_stepper.py \
  tests/test_sim_scenario.py tests/test_sim_events.py tests/test_sim_probe.py \
  tests/test_sim_replay.py tests/test_sim_loop.py tests/test_sim_eventprop.py \
  tests/test_sim_input_capture.py tests/test_sim_trajectory.py tests/test_sim_layout.py \
  tests/test_sim_panels.py tests/test_sim_ui_smoke.py tests/test_sim_reconstruct.py \
  tests/test_sim_platoon.py tests/test_sim_meso_panels.py tests/test_sim_meso_road.py \
  tests/test_sim_episode.py tests/test_sim_postrun.py tests/test_champion_io.py -q
```

**Baseline: 167 sim + 9 champion_io = 176 passed.**

**Hard rules:**
- **Frozen core** — never touch `sim/{state,stepper,backend,events,probe,eventprop_stepper}.py`. Nothing here needs to.
- **No numpy LAPACK** in `cf_sim` → OMP #15 hard abort.
- **`train.py` is used for the real Azure runs.** Task 1 must stay additive: if you break `save_checkpoint`, you break training, and no sim test would notice.
- Commits: conventional, **no `Co-Authored-By`**. Push freely.
- **Do NOT fix** `ReplayLog.seed` (`app.py:591`) or the `events.py:37-38` ramp bug — cycle 3 owns them.

---

## File Structure

| File | Responsibility |
|---|---|
| `train.py` (root, `:798-808`) | Writes the `arch` field. Three lines, additive, read from the model. |
| `utils/champion_io.py` | **The whole resolver.** `_name_signature` (what is this?), `_resolve_max_delay` (how many ticks, from where, how sure), `resolve_identity` (pure verdict), `load_champion` (uses the verdict). Grows from ~100 to ~220 lines — still one cohesive job: *turn a file into a known model*. |
| `sim/ui/app.py` | File browser, honest header, failure that leaves the cockpit standing. |
| `sim/ui/panels.py` | Two size-adaptivity fixes (`:248`, `:308`). |
| `tests/test_champion_io.py` | Resolver tests (pure, no Qt). |
| `tests/test_sim_ui_smoke.py` | GUI tests (browser, header, survivable failure). |

Task order = dependency order: naming → resolution → wiring into `load_champion` (this is where the bug dies) → trainer → GUI → panels → verification.

---

### Task 1: Name every variant, refuse the unsupported ones by name

**Files:**
- Modify: `utils/champion_io.py:30-52` (`detect_family`)
- Test: `tests/test_champion_io.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_name_signature_recognises_the_two_supported_families():
    from utils.champion_io import _name_signature
    from core.network import build_model
    for variant in ("baseline", "eventprop_alif_full"):
        name, supported, reason = _name_signature(build_model(variant).state_dict())
        assert name == variant and supported is True and reason is None


def test_name_signature_names_unsupported_variants_instead_of_calling_them_baseline():
    """Today attn/wta resolve to 'baseline' and are only saved by a torch RuntimeError about
    tensors; stacked_* raises a generic ValueError. Naming them is what makes an honest refusal
    possible."""
    from utils.champion_io import _name_signature
    from core.network import build_model
    for variant, expected in (("attn", "attn"), ("wta", "wta"),
                              ("stacked_2", "stacked_2"), ("stacked_2_skip", "stacked_2_skip"),
                              ("stacked_3_thin", "stacked_3")):
        name, supported, reason = _name_signature(build_model(variant).state_dict())
        assert name == expected, f"{variant} resolved to {name!r}"
        assert supported is False
        assert reason, f"{variant} refused without a reason"


def test_name_signature_unknown_signature():
    from utils.champion_io import _name_signature
    name, supported, reason = _name_signature({"nonsense.weight": None})
    assert name == "unknown" and supported is False and "signature" in reason.lower()


def test_multi_rate_is_accepted_as_baseline():
    """multi_rate is numerically identical to baseline once loaded (ALIFCell.forward uses only
    leak_div). It needs no dedicated handling -- but the resolver must not claim it recognised
    the variant."""
    from utils.champion_io import _name_signature
    from core.network import build_model
    name, supported, _ = _name_signature(build_model("multi_rate").state_dict())
    assert name == "baseline" and supported is True
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_champion_io.py -q -k name_signature
```

Expected: FAIL — `ImportError: cannot import name '_name_signature'`.

- [ ] **Step 3: Implement**

In `utils/champion_io.py`, add above `detect_family`:

```python
# Signatures of variants build_model can produce but the simulator cannot SHOW. Naming them is what
# separates "I know what this is and cannot serve it" from "I have no idea what this is" -- today
# attn/wta are silently called "baseline" and only strict=True saves us.
_UNSUPPORTED = {
    "attn": ("Wq", "the attention block Wq/Wk/Wv is not on the readout path the viewer draws"),
    "wta": ("inh_w_in", "the lateral-inhibition weight inh_w_in is not shown by the viewer"),
}


def _name_signature(state_dict):
    """(name, supported, reason) for a state-dict. Never raises: the caller decides what to do."""
    keys = set(state_dict.keys())

    # Stacked family: multiple hidden layers. The frozen backend reads model.layer_hidden (singular),
    # so these cannot be observed without a new backend (out of scope -- see the spec).
    stacked_idx = [int(k.split(".")[1]) for k in keys if k.startswith("layers_hidden.")]
    if stacked_idx:
        n = max(stacked_idx) + 1
        return (f"stacked_{n}", False,
                f"stacked variant with {n} hidden layers: the viewer reads a single hidden layer")
    if "skip_weight" in keys and any(k.startswith("layer_hidden_0.") for k in keys):
        return ("stacked_2_skip", False,
                "stacked variant with a skip connection: the viewer reads a single hidden layer")

    # attn/wta carry the baseline signature PLUS an extra block -> must be tested BEFORE baseline.
    for name, (marker, why) in _UNSUPPORTED.items():
        if marker in keys:
            return (name, False, why)

    ep_readout = _EVENTPROP_READOUT in keys
    bl_readout = _BASELINE_READOUT in keys
    flat_alif = "layer_hidden.base_threshold" in keys
    cell_alif = "layer_hidden.cell.base_threshold" in keys
    if ep_readout and not bl_readout and flat_alif and not cell_alif:
        return ("eventprop_alif_full", True, None)
    if bl_readout and not ep_readout and cell_alif and not flat_alif:
        return ("baseline", True, None)
    return ("unknown", False,
            f"unrecognised state-dict signature (readout: eventprop={ep_readout} baseline={bl_readout}; "
            f"alif: flat={flat_alif} cell={cell_alif})")
```

Then make `detect_family` delegate, preserving its contract (raises on anything not loadable):

```python
def detect_family(state_dict) -> str:
    """Return the ``build_model`` variant for a champion ``state_dict``.

    Thin wrapper over ``_name_signature`` kept for callers that just want the family or a loud
    failure. Raises ``ValueError`` on unknown/ambiguous/unsupported signatures.
    """
    name, supported, reason = _name_signature(state_dict)
    if not supported:
        raise ValueError(f"Cannot load this checkpoint: {name} — {reason}")
    return name
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_champion_io.py -q
```

Expected: PASS (9 existing + 4 new = 13).

- [ ] **Step 5: Commit**

```bash
git add utils/champion_io.py tests/test_champion_io.py
git commit -m "feat(champion_io): name every variant instead of mislabelling it baseline

attn and wta carry the baseline signature plus an extra block, so today they are
called 'baseline' and only a torch RuntimeError about tensors stops them; the
stacked family gets a generic ValueError. _name_signature returns (name,
supported, reason) and never raises, so the caller can refuse by name."
```

---

### Task 2: Resolve max_delay from a hierarchy of sources, with an asymmetric cross-check

**Files:**
- Modify: `utils/champion_io.py` (add `_resolve_max_delay`)
- Test: `tests/test_champion_io.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def _sd_with_delays(max_delay, H=32, IN=4, seed=0):
    """A baseline state-dict whose `delays` really come from randint(0, max_delay)."""
    import torch
    from core.network import build_model
    torch.manual_seed(seed)
    return build_model("baseline", hidden_size=H, rank=8, max_delay=max_delay).state_dict()


def test_max_delay_from_arch_field_is_exact_and_skips_inference():
    from utils.champion_io import _resolve_max_delay
    sd = _sd_with_delays(6)
    md, src, p = _resolve_max_delay(sd, "baseline", arch={"max_delay": 6}, sidecar=None)
    assert md == 6 and src == "arch" and p is None


def test_max_delay_from_delay_masks_is_exact_for_eventprop():
    from utils.champion_io import _resolve_max_delay
    from core.network import build_model
    sd = build_model("eventprop_alif_full").state_dict()
    md, src, p = _resolve_max_delay(sd, "eventprop_alif_full", arch=None, sidecar=None)
    assert md == int(sd["layer_hidden.delay_masks"].shape[0])
    assert src == "delay_masks" and p is None


def test_max_delay_from_sidecar():
    from utils.champion_io import _resolve_max_delay
    sd = _sd_with_delays(12)
    md, src, p = _resolve_max_delay(sd, "baseline", arch=None, sidecar={"cf_max_delay": 12})
    assert md == 12 and src == "sidecar" and p is None


def test_max_delay_inferred_reports_its_confidence():
    from utils.champion_io import _resolve_max_delay
    sd = _sd_with_delays(12)
    md, src, p = _resolve_max_delay(sd, "baseline", arch=None, sidecar=None)
    assert md == 12 and src == "inferred"
    assert 0.0 < p < 1e-3                       # 128 samples at k=12 -> ~1.5e-5


def test_cross_check_raises_only_when_the_weights_REFUTE_the_declared_value():
    """TEETH, and the direction is the trap. The inference is a LOWER BOUND:
      declared > inferred  -> normal under-shoot, accept silently
      declared < inferred  -> impossible: a synapse holds a delay that model could not produce
    A test asserting 'differ -> raise' would pass a wrong implementation."""
    import pytest
    from utils.champion_io import _resolve_max_delay
    sd = _sd_with_delays(12)                    # delays.max() == 11 -> inference says 12

    # declared BELOW the inference -> refuted by the weights -> must raise
    with pytest.raises(ValueError, match="refut|impossibil|12"):
        _resolve_max_delay(sd, "baseline", arch=None, sidecar={"cf_max_delay": 6})

    # declared ABOVE the inference -> the expected under-shoot -> must NOT raise
    md, src, p = _resolve_max_delay(sd, "baseline", arch=None, sidecar={"cf_max_delay": 18})
    assert md == 18 and src == "sidecar"
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_champion_io.py -q -k max_delay
```

Expected: FAIL — `ImportError: cannot import name '_resolve_max_delay'`.

- [ ] **Step 3: Implement**

In `utils/champion_io.py`:

```python
def _infer_max_delay(state_dict):
    """(inferred, p_underestimate) from the `delays` buffer, or (None, None) if absent.

    `delays` is randint(0, max_delay, (H, IN)) (core/network.py:26), so its max is a LOWER BOUND of
    max_delay-1: the inference is exact only if some synapse drew the top value. Measured over 20k
    draws: exact for max_delay 6 and 12, fails ~1 in 1333 at max_delay=18 with H=32 (128 samples).
    """
    d = state_dict.get("layer_hidden.delays")
    if d is None:
        return None, None
    k = int(d.max()) + 1
    n = int(d.numel())
    p = ((k - 1) / k) ** n if k > 1 else 0.0     # uses the inferred k: the true one is unknowable
    return k, p


def _resolve_max_delay(state_dict, family, arch=None, sidecar=None):
    """(max_delay, source, p_underestimate). source in {arch, delay_masks, sidecar, inferred}.

    The .pt carries no metadata, so max_delay is unknowable from the baseline signature alone
    (`delays` is (H,IN) whatever max_delay is) -- which is why it used to be silently defaulted to 6,
    dropping 68/128 synapses on a max_delay_12 checkpoint. Hierarchy, most authoritative first.
    """
    declared, source = None, None
    if arch and arch.get("max_delay") is not None:
        declared, source = int(arch["max_delay"]), "arch"
    elif family == "eventprop_alif_full" and "layer_hidden.delay_masks" in state_dict:
        declared, source = int(state_dict["layer_hidden.delay_masks"].shape[0]), "delay_masks"
    elif sidecar and sidecar.get("cf_max_delay") is not None:
        declared, source = int(sidecar["cf_max_delay"]), "sidecar"

    inferred, p = _infer_max_delay(state_dict)

    if declared is not None:
        # Asymmetric cross-check: the inference is a LOWER BOUND, so declared > inferred is the
        # expected under-shoot, NOT a conflict. Only declared < inferred is impossible -- a synapse
        # holds a delay that model could never have produced, so the declared source is refuted by
        # the weights themselves (a sidecar from another run, a copied arch field).
        if inferred is not None and declared < inferred:
            raise ValueError(
                f"max_delay declared as {declared} (source: {source}) is refuted by the weights: "
                f"the delays buffer holds {inferred - 1}, which requires max_delay >= {inferred}. "
                f"The checkpoint and that source do not describe the same model.")
        return declared, source, None

    if inferred is None:
        return None, None, None
    return inferred, "inferred", p
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_champion_io.py -q
```

Expected: PASS (13 + 5 = 18).

- [ ] **Step 5: Commit**

```bash
git add utils/champion_io.py tests/test_champion_io.py
git commit -m "feat(champion_io): resolve max_delay from a hierarchy, with an asymmetric cross-check

arch field -> delay_masks.shape[0] (EventProp, exact) -> config_snapshot sidecar
-> delays.max()+1 (inferred, with P(underestimate) reported).

The cross-check is asymmetric on purpose: the inference is a LOWER BOUND, so a
declared value ABOVE it is the expected under-shoot (measured ~1 in 1333 at
max_delay=18/H=32), while a declared value BELOW it is refuted by the weights --
a synapse holds a delay that model could not have produced."
```

---

### Task 3: `resolve_identity` — the verdict, and `load_champion` uses it (the bug dies here)

**Files:**
- Modify: `utils/champion_io.py:55-103` (`_infer_topology`, `ChampionHandle`, `load_champion`)
- Test: `tests/test_champion_io.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_resolve_identity_verdict_for_a_real_champion():
    import os, torch
    from utils.champion_io import resolve_identity
    REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ckpt = torch.load(os.path.join(REPO, "champions", "R33_C2_A1_T12_fix", "best_model.pt"),
                      map_location="cpu", weights_only=False)
    idy = resolve_identity(ckpt["model_state"], arch=ckpt.get("arch"))
    assert idy.family == "baseline" and idy.supported is True
    assert idy.topology == {"hidden": 32, "input": 4, "rank": 8, "output": 5}
    assert idy.max_delay == 6 and idy.sources["max_delay"] == "inferred"


def test_resolve_identity_refuses_by_name_without_raising():
    from utils.champion_io import resolve_identity
    from core.network import build_model
    idy = resolve_identity(build_model("attn").state_dict())
    assert idy.family == "attn" and idy.supported is False and idy.reason
    assert idy.max_delay is None or idy.max_delay > 0     # no crash either way


def test_load_champion_no_longer_drops_synapses_on_a_max_delay_12_checkpoint(tmp_path):
    """THE BUG THIS CYCLE CLOSES, asserted on the synapse count -- not on a label.

    Before: detect_family said 'baseline', strict=True PASSED, build_model rebuilt with the config
    default 6, and every delay >= 6 never matched `for d in range(max_delay)` -> 68/128 input
    synapses silently dropped, max |diff| on the decoded params = 5.98.
    """
    import torch
    from core.network import build_model
    from utils.champion_io import load_champion

    torch.manual_seed(0)
    original = build_model("baseline", hidden_size=32, rank=8, max_delay=12)
    path = tmp_path / "best_model.pt"
    torch.save({"epoch": 1, "val_loss": 0.1, "model_state": original.state_dict(),
                "optim_state": {}}, path)

    handle = load_champion(str(path))
    assert handle.model.max_delay == 12                    # rebuilt with the RIGHT max_delay
    assert handle.identity.max_delay == 12

    # No synapse is unreachable: every delay must be < the model's max_delay.
    delays = handle.model.layer_hidden.delays
    assert int(delays.max()) < handle.model.max_delay
    dropped = int((delays >= handle.model.max_delay).sum())
    assert dropped == 0, f"{dropped} of {delays.numel()} input synapses are unreachable"

    # And it behaves like the original: same decoded params on the same input.
    obs = torch.zeros(1, 4)
    original.reset_state(1, "cpu"); handle.model.reset_state(1, "cpu")
    torch.testing.assert_close(original.forward_step(obs), handle.model.forward_step(obs))


def test_load_champion_still_loads_the_four_champions_identically(tmp_path):
    """Regression: the four bundled champions must resolve exactly as before."""
    import os
    from utils.champion_io import load_champion
    REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    expected = {"R33_C2_A1_T12_fix": ("baseline", 8), "LS3_PEAK_R0_launch_d03": ("baseline", 8),
                "PE_t05_gp0002": ("eventprop_alif_full", 16), "A_lr1e2_t06_r16": ("eventprop_alif_full", 16)}
    for tag, (fam, rank) in expected.items():
        h = load_champion(os.path.join(REPO, "champions", tag, "best_model.pt"))
        assert h.variant == fam and h.topology["rank"] == rank
        assert h.identity.max_delay == 6
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_champion_io.py -q -k "resolve_identity or synapses or identically"
```

Expected: FAIL — `ImportError: cannot import name 'resolve_identity'`. After it exists, `test_load_champion_no_longer_drops_synapses...` must fail on `handle.model.max_delay == 12` (it will be 6) — **that failure is the bug, reproduced**.

- [ ] **Step 3: Implement**

In `utils/champion_io.py`, replace `_infer_topology`'s docstring lie, add `Identity` + `resolve_identity`, and rewire `load_champion`:

```python
@dataclass(frozen=True)
class Identity:
    """What a checkpoint IS, and how sure we are of each part."""
    family: str                  # build_model variant, or the name of an unsupported one, or "unknown"
    supported: bool
    reason: str | None           # why it cannot be served (None when supported)
    topology: dict | None        # {hidden, input, rank, output}; None when unreadable
    max_delay: int | None
    sources: dict                # {"topology": "weights", "max_delay": "arch"|...}
    max_delay_p_underestimate: float | None   # only when max_delay was inferred


def _infer_topology(state_dict, variant) -> dict:
    """Infer (hidden, input, rank, output) from tensor shapes.

    max_delay is NOT inferable here: it does not change baseline tensor shapes (`delays` is (H,IN)
    whatever it is). It is resolved separately by _resolve_max_delay -- see that function for why
    defaulting it silently was a real bug and not a harmless assumption.
    """
    fc = state_dict["layer_hidden.fc_weight"]        # (hidden, input)
    rec_u = state_dict["layer_hidden.rec_U"]         # (hidden, rank)
    readout_key = _EVENTPROP_READOUT if variant == "eventprop_alif_full" else _BASELINE_READOUT
    readout = state_dict[readout_key]                # (output, hidden)
    return {
        "hidden": int(fc.shape[0]),
        "input": int(fc.shape[1]),
        "rank": int(rec_u.shape[1]),
        "output": int(readout.shape[0]),
    }


def resolve_identity(state_dict, arch=None, sidecar=None) -> Identity:
    """What is this checkpoint? Pure: no torch.load, no filesystem, no GUI -- so it is testable on
    synthetic state-dicts, including the ones that lie today. Never raises for an unsupported but
    nameable variant: it returns supported=False and a reason, and the caller decides.
    """
    family, supported, reason = _name_signature(state_dict)
    if not supported:
        return Identity(family=family, supported=False, reason=reason, topology=None,
                        max_delay=None, sources={}, max_delay_p_underestimate=None)
    topo = _infer_topology(state_dict, family)
    md, md_src, p = _resolve_max_delay(state_dict, family, arch=arch, sidecar=sidecar)
    return Identity(family=family, supported=True, reason=None, topology=topo, max_delay=md,
                    sources={"topology": "weights", "max_delay": md_src},
                    max_delay_p_underestimate=p)


def _read_sidecar(path):
    """config_snapshot.json next to the checkpoint, if any. Coverage in the corpus: cf_hidden_size/
    cf_rank 506/512, cf_max_delay 258/512 -- and absent next to the 4 champions."""
    import json
    import os
    p = os.path.join(os.path.dirname(os.path.abspath(path)), "config_snapshot.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return None      # unreadable/corrupt sidecar must not block a loadable checkpoint
```

Extend `ChampionHandle` with the verdict and rewire `load_champion`:

```python
@dataclass
class ChampionHandle:
    """A strict-verified, ready-to-run champion."""
    model: Any
    variant: str
    topology: dict
    epoch: int
    val_loss: float
    identity: Identity


def load_champion(path, device="cpu") -> ChampionHandle:
    """Load a champion ``.pt`` into a strict-verified, eval-mode model.

    Raises ``ValueError`` on an unrecognised or unsupported family (naming it) and ``RuntimeError``
    (from ``load_state_dict(strict=True)``) on any key/shape mismatch — never a silent partial load.
    """
    ckpt = torch.load(path, map_location=device, weights_only=False)
    state = ckpt["model_state"]
    identity = resolve_identity(state, arch=ckpt.get("arch"), sidecar=_read_sidecar(path))
    if not identity.supported:
        raise ValueError(f"Cannot load this checkpoint: {identity.family} — {identity.reason}")
    model = build_model(identity.family, hidden_size=identity.topology["hidden"],
                        rank=identity.topology["rank"], max_delay=identity.max_delay)
    model.load_state_dict(state, strict=True)   # §9.4 guard: raises on any mismatch
    model.to(device).eval()
    return ChampionHandle(
        model=model,
        variant=identity.family,
        topology=identity.topology,
        epoch=int(ckpt.get("epoch", -1)),
        val_loss=float(ckpt.get("val_loss", float("nan"))),
        identity=identity,
    )
```

⚠️ `build_model(..., max_delay=identity.max_delay)` is the line that closes the bug: today `:94` passes only `hidden_size` and `rank`, so `max_delay` falls back to the config default.

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_champion_io.py -q
```

Expected: PASS (18 + 4 = 22).

- [ ] **Step 5: Commit**

```bash
git add utils/champion_io.py tests/test_champion_io.py
git commit -m "fix(champion_io): stop silently dropping synapses on non-default max_delay

resolve_identity returns a structured verdict (family, topology, max_delay, and
the provenance of each) and load_champion now passes max_delay to build_model.

Before: a max_delay_12 checkpoint has the same keys AND shapes as baseline, so
the family was 'baseline', strict=True passed, the model was rebuilt with the
config default 6, and every delay >= 6 never matched the ring buffer loop -- 68
of 128 input synapses unreachable, max |diff| 5.98 on the decoded params, no
error. The test asserts the synapse count, not a label."
```

---

### Task 4: The trainer writes `arch`

**Files:**
- Modify: `train.py:798-808` (`save_checkpoint`)
- Test: `tests/test_champion_io.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_save_checkpoint_writes_a_self_describing_arch_field(tmp_path):
    import torch
    import train
    from core.network import build_model
    from utils.champion_io import resolve_identity

    model = build_model("baseline", hidden_size=32, rank=8, max_delay=12)
    opt = torch.optim.SGD(model.parameters(), lr=0.1)
    p = tmp_path / "ck.pt"
    train.save_checkpoint(model, opt, epoch=3, val_loss=0.5, path=str(p))

    ck = torch.load(p, map_location="cpu", weights_only=False)
    assert ck["arch"]["max_delay"] == 12          # the RESOLVED value, not the CLI default (None)
    assert ck["arch"]["hidden_size"] == 32 and ck["arch"]["rank"] == 8
    assert ck["arch"]["class"] == "CF_FSNN_Net"
    # level 1 of the hierarchy: nothing is inferred
    idy = resolve_identity(ck["model_state"], arch=ck["arch"])
    assert idy.max_delay == 12 and idy.sources["max_delay"] == "arch"
    assert idy.max_delay_p_underestimate is None


def test_save_checkpoint_does_not_break_any_variant(tmp_path):
    """TEETH: bit_shift exists ONLY on CF_FSNN_Net -- measured absent on 9 of the 10 variants below,
    EventProp included. A plain model.bit_shift raises here and breaks TRAINING: a failure outside
    the simulator that no sim test would ever catch. (hidden_size/rank/max_delay are on all of them.)"""
    import torch
    import train
    from core.network import build_model
    for variant in ("baseline", "eventprop_alif_full", "stacked_2", "stacked_2_skip",
                    "stacked_3_thin", "attn", "wta", "multi_rate", "bptt_lif_simple",
                    "eventprop_lif_simple"):
        model = build_model(variant)
        opt = torch.optim.SGD(model.parameters(), lr=0.1)
        train.save_checkpoint(model, opt, epoch=0, val_loss=1.0,
                              path=str(tmp_path / f"{variant}.pt"))   # must not raise
        ck = torch.load(tmp_path / f"{variant}.pt", map_location="cpu", weights_only=False)
        assert ck["arch"]["class"] == type(model).__name__


def test_load_checkpoint_still_works_with_the_extra_key(tmp_path):
    """Additive: train.py's own resume path reads by key (train.py:811-816)."""
    import torch
    import train
    from core.network import build_model
    model = build_model("baseline")
    opt = torch.optim.SGD(model.parameters(), lr=0.1)
    p = str(tmp_path / "ck.pt")
    train.save_checkpoint(model, opt, epoch=7, val_loss=0.25, path=p)
    epoch, val = train.load_checkpoint(build_model("baseline"), opt, p, "cpu")
    assert epoch == 7 and abs(val - 0.25) < 1e-9
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_champion_io.py -q -k save_checkpoint
```

Expected: FAIL — `KeyError: 'arch'`.

- [ ] **Step 3: Implement**

In `train.py`, `save_checkpoint` (`:798-808`):

```python
def save_checkpoint(model, optimizer, epoch, val_loss, path):
    # Crea la directory solo se il path ha una componente directory
    dir_part = os.path.dirname(path)
    if dir_part:
        os.makedirs(dir_part, exist_ok=True)
    torch.save({
        'epoch'      : epoch,
        'val_loss'   : val_loss,
        'model_state': model.state_dict(),
        'optim_state': optimizer.state_dict(),
        # Checkpoint auto-descrittivo. Il .pt non ha mai portato metadata, e max_delay NON e'
        # deducibile dalla firma baseline (delays e' (H,IN) qualunque esso sia): veniva quindi
        # rimesso al default 6, scartando in silenzio le sinapsi con delay maggiore.
        # Si legge dal MODELLO, non da args: save_checkpoint non ha args, e i default CLI sono
        # None (e' build_model a risolverli contro la config).
        # getattr NON e' cautela di stile: bit_shift esiste SOLO su CF_FSNN_Net (misurato: assente
        # su 9 varianti su 10, EventProp compreso) -> un accesso diretto romperebbe il training.
        'arch'       : {'class'      : type(model).__name__,
                        'hidden_size': getattr(model, 'hidden_size', None),
                        'rank'       : getattr(model, 'rank', None),
                        'max_delay'  : getattr(model, 'max_delay', None),
                        'bit_shift'  : getattr(model, 'bit_shift', None)},
    }, path)
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_champion_io.py -q
```

Expected: PASS (22 + 3 = 25).

- [ ] **Step 5: Commit**

```bash
git add train.py tests/test_champion_io.py
git commit -m "feat(train): write a self-describing arch field into the checkpoint

Purely additive -- every existing reader accesses by key (train.py:811-816,
champion_io.py:91). Becomes level 1 of the identity hierarchy: when present,
nothing is inferred, and the max_delay problem stops existing for everything
trained from now on.

Read from the model, not from args: save_checkpoint has no args, the CLI defaults
are None (build_model resolves them), and getattr is mandatory because
bit_shift exists only on CF_FSNN_Net (measured: absent on 9 of 10 variants,
EventProp included) -- a direct model.bit_shift would break their training."
```

---

### Task 5: File browser, honest header, survivable failure

**Files:**
- Modify: `sim/ui/app.py:41-59` (`_CHAMPIONS`, `__init__` identity), `:186-198` (`_build_menus`), `:422` (header)
- Test: `tests/test_sim_ui_smoke.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_app_header_states_the_real_identity_not_a_guess(qapp):
    win = SimApp(CHAMP)
    h = win._header.text()
    assert "Raffaello" in h                       # this one really IS Raffaello
    assert "baseline" in h and "32" in h          # family + topology stated
    assert "max_delay" in h and "inferito" in h   # and the PROVENANCE of max_delay


def test_app_open_champion_from_an_arbitrary_path(qapp, tmp_path):
    """A .pt outside champions/ must load AND leave the selector usable -- today
    _champ_root = dirname(dirname(path)) empties it."""
    import shutil
    p = tmp_path / "altrove" / "best_model.pt"
    p.parent.mkdir(parents=True)
    shutil.copy(CHAMP, p)
    win = SimApp(CHAMP)
    win.open_champion_path(str(p))
    assert win._champ_selector.count() >= 5       # 4 bundled + the opened one
    assert win.loop.stepper.backend is not None


def test_app_bad_checkpoint_leaves_the_cockpit_standing(qapp, tmp_path):
    """Today load_champion has no try/except (app.py:58): a bad .pt kills the GUI."""
    bad = tmp_path / "rubbish.pt"
    bad.write_bytes(b"not a torch file")
    win = SimApp(CHAMP)
    before = win._champ_name
    ok, msg = win.open_champion_path(str(bad))
    assert ok is False and msg                     # reason reported, no exception
    assert win._champ_name == before               # the running champion is untouched
    win._advance(0.2)                              # and the cockpit still runs


def test_app_unsupported_variant_is_refused_by_name(qapp, tmp_path):
    import torch
    from core.network import build_model
    p = tmp_path / "attn.pt"
    torch.save({"epoch": 0, "val_loss": 0.0, "model_state": build_model("attn").state_dict(),
                "optim_state": {}}, p)
    win = SimApp(CHAMP)
    ok, msg = win.open_champion_path(str(p))
    assert ok is False and "attn" in msg           # named, not "unknown", not "Raffaello"
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q -k "header_states or open_champion or bad_checkpoint or refused_by_name"
```

Expected: FAIL — `AttributeError: 'SimApp' object has no attribute 'open_champion_path'`.

- [ ] **Step 3: Implement**

In `sim/ui/app.py`, replace the launched-champion identification (`:53-59`) so the name never comes from a positional fallback:

```python
        self._champ_root = os.path.dirname(os.path.dirname(champion_path))
        self._champions = [(nick, d) for nick, d, _ in _CHAMPIONS
                           if os.path.isdir(os.path.join(self._champ_root, d))]
        launched = os.path.basename(os.path.dirname(champion_path))
        self._champ_idx = next((i for i, (_, d) in enumerate(self._champions) if d == launched), None)
        self._champ = load_champion(champion_path)
        # The name is the launched tag's nickname ONLY if the tag really matches one. Never fall back
        # to index 0: that is how an unknown tag under champions/ got labelled "Raffaello".
        self._champ_name = (self._champions[self._champ_idx][0] if self._champ_idx is not None
                            else launched)
        self._champ_path = champion_path
```

⚠️ **`_champ_idx` can now be `None`, and one existing line does not expect that.** `app.py:117-118`
does `self._champ_selector.setCurrentIndex(self._champ_idx)`, which raises `TypeError` on `None`.
Change it to select nothing rather than misselecting index 0 — that positional fallback is the whole
bug being removed:

```python
        if self._champions and self._champ_idx is not None:
            self._champ_selector.setCurrentIndex(self._champ_idx)
```

Check every other reader of `_champ_idx` before you finish the task (`grep -n "_champ_idx" sim/ui/app.py`):
`select_champion` assigns it, so it is fine, but do not assume — this is exactly the kind of `None` that
surfaces three weeks later.

Add the loader + the honest header (put `open_champion_path` next to `select_champion`):

```python
    def _identity_line(self):
        """Header text: what is loaded, and where each claim comes from."""
        idy = self._champ.identity
        t = idy.topology
        md = f"max_delay {idy.max_delay}"
        src = idy.sources.get("max_delay")
        if src == "inferred":
            p = idy.max_delay_p_underestimate
            md += f" (inferito, P(sottostima)~{p:.0e})"
        elif src:
            md += f" (da {src})"
        return (f"champion: {self._champ_name}  [{idy.family} · {t['input']}→{t['hidden']}→"
                f"{t['output']} · rank {t['rank']} · {md}]")

    def open_champion_path(self, path):
        """Load a champion from an arbitrary path. Returns (ok, message).

        Nothing is torn down before the new champion is known-good: on failure the running one keeps
        going. Today load_champion is called bare (app.py:58) and a bad .pt kills the GUI.
        """
        try:
            champ = load_champion(path)
        except Exception as exc:                  # ValueError (named refusal) / RuntimeError / torch
            return False, str(exc)
        self._champ = champ
        self._champ_path = path
        self._champ_name = os.path.basename(os.path.dirname(os.path.abspath(path)))
        if self._champ_selector.findText(self._champ_name) < 0:
            self._champ_selector.blockSignals(True)
            self._champ_selector.addItem(self._champ_name)
            self._champ_selector.setCurrentIndex(self._champ_selector.count() - 1)
            self._champ_selector.blockSignals(False)
        self._apply_champion_topology()
        self.select_scenario(self._current_idx)
        return True, ""

    def open_champion_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Apri champion", self._champ_root,
                                              "Checkpoint (*.pt)")
        if not path:
            return
        ok, msg = self.open_champion_path(path)
        if not ok:
            QMessageBox.warning(self, "Champion non caricato", msg)
```

Add `QMessageBox` to the PySide6 import at `app.py:11`. In `_build_menus` (`:187`), under the File menu:

```python
        file_menu.addAction("Apri champion…", self.open_champion_dialog)
```

And use the identity line where the header is set (`:422`):

```python
        self._header.setText(f"{self._identity_line()}    |    scenario: {sc.name}")
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_ui_smoke.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/app.py tests/test_sim_ui_smoke.py
git commit -m "feat(sim): open any checkpoint from the GUI and say what it is

File -> Apri champion. A failure now reports the reason and leaves the running
champion in place; today load_champion is called bare and a bad .pt kills the GUI.

The header states family, topology and max_delay WITH its provenance -- 'max_delay
6 (inferito)' is a different claim from '(da arch)'. The name no longer comes from
next(..., 0), which is how an unknown tag under champions/ was labelled Raffaello."
```

---

### Task 6: Size adaptivity in the network graph

**Files:**
- Modify: `sim/ui/panels.py:248` (`yspread` span), `:308` (hidden label)
- Test: `tests/test_sim_panels.py` (append)

- [ ] **Step 1: Write the failing tests**

```python
def test_neuron_graph_label_states_the_real_hidden_count(qapp):
    """panels.py:308 hardcodes 'hidden · 32 ALIF' -- the only literal 32 in sim/. It lies for any
    H != 32, and the whole point of this cycle is that the cockpit stops lying about what it loaded."""
    import numpy as np
    H, IN, OUT = 48, 4, 5
    rng = np.random.default_rng(0)
    panel = NeuronGraphPanel()
    panel.set_topology(rng.standard_normal((H, IN)), rng.standard_normal((H, H)),
                       rng.standard_normal((OUT, H)))
    labels = [t.toPlainText() for t in panel._plot.items if hasattr(t, "toPlainText")]
    assert any("48" in t for t in labels), labels
    assert not any("32" in t for t in labels), labels


def _hidden_col_ys(panel):
    """Y positions of the first hidden column (x = 1.0)."""
    return sorted(y for x, y in panel._pos if abs(x - 1.0) < 1e-9)


def test_neuron_graph_nodes_do_not_overlap_at_larger_H(qapp):
    """yspread's span=32.0 is tuned for 16 nodes/column; at H=64 the spacing halves and the 13 px
    markers collide."""
    import numpy as np
    rng = np.random.default_rng(0)
    spacing = {}
    for H in (32, 64):
        panel = NeuronGraphPanel()
        panel.set_topology(rng.standard_normal((H, 4)), rng.standard_normal((H, H)),
                           rng.standard_normal((5, H)))
        ys = _hidden_col_ys(panel)
        spacing[H] = min(b - a for a, b in zip(ys, ys[1:]))
    assert spacing[64] >= spacing[32] * 0.9      # spacing must not collapse with H


def test_neuron_graph_columns_stay_aligned_and_H32_is_unchanged(qapp):
    """TEETH: the span must stay GLOBAL. Giving each column a span from its own node count would
    spread 4 inputs over 6.4 while the hidden go to 66 -- the columns would stop lining up. And at
    H=32 the layout must be pixel-identical to what it has always been (span 32.0)."""
    import numpy as np
    rng = np.random.default_rng(0)
    panel = NeuronGraphPanel()
    panel.set_topology(rng.standard_normal((32, 4)), rng.standard_normal((32, 32)),
                       rng.standard_normal((5, 32)))
    ys_in = sorted(y for x, y in panel._pos if abs(x - 0.0) < 1e-9)
    ys_hid = _hidden_col_ys(panel)
    ys_out = sorted(y for x, y in panel._pos if abs(x - 2.6) < 1e-9)
    for ys in (ys_in, ys_hid, ys_out):
        assert abs(ys[0] - 0.0) < 1e-6 and abs(ys[-1] - 32.0) < 0.1   # same span, all columns
```

- [ ] **Step 2: Run to verify they fail**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_panels.py -q -k "real_hidden_count or do_not_overlap"
```

Expected: FAIL — the label says `32`, and the H=64 spacing is half of H=32's.

- [ ] **Step 3: Implement**

In `sim/ui/panels.py`, `NeuronGraphPanel.set_topology`, replace the `yspread` helper (`:248-250`).

⚠️ **The span must stay GLOBAL, not per-column.** All four columns (input, the two hidden halves,
output) currently share `span=32.0`, which is what keeps them vertically aligned. Giving each column a
span proportional to *its own* count would spread 4 inputs over 6.4 while the hidden go to 66 — the
columns would no longer line up. So: compute one span from the **busiest** column and hand it to every
call, exactly as today — only the number stops being a constant.

```python
        # The busiest column is a hidden half; keep a constant per-node spacing so the layout GROWS
        # with the network instead of squeezing N nodes into a fixed height (at H=64 the 13 px markers
        # collided). 2.13 = the old 32.0 over the 15 gaps of a 16-node column -> at H=32 the span comes
        # back to 32.0 and the familiar view is unchanged by construction.
        half = (H + 1) // 2
        span = 2.13 * max(1, half - 1)

        def yspread(n, span=span):
            return np.linspace(0.0, span, n) if n > 1 else np.array([span / 2])
```

⚠️ `half` is already computed at `panels.py:251`, right below the old `yspread`. Move that line **above**
the helper rather than computing it twice, and delete the duplicate.

and the hardcoded label (`:308`):

```python
        self._text(f"hidden · {H} ALIF", 1.2, top, "#b0b0b0")
```

- [ ] **Step 4: Run to verify they pass**

```bash
ENV=C:/Miniconda/envs/cf_sim
PATH="$ENV:$ENV/Library/bin:$ENV/Scripts:$PATH" "$ENV/python.exe" -m pytest tests/test_sim_panels.py -q
```

Expected: PASS. ⚠️ If a pre-existing test asserted on the old positions, read it before touching it: the H=32 layout must be unchanged, so a failure there means `per_node` is wrong, not that the test is.

- [ ] **Step 5: Commit**

```bash
git add sim/ui/panels.py tests/test_sim_panels.py
git commit -m "feat(sim): network graph adapts to the real hidden size

The 'hidden · 32 ALIF' label was the only literal 32 left in sim/ and lied for any
other H. yspread now keeps a constant per-node spacing instead of squeezing N nodes
into a fixed span, so H=64 no longer overlaps; the H=32 layout is unchanged by
construction (2.13 = 32.0 / 15 gaps)."
```

---

### Task 7: Full verification and docs

**Files:**
- Modify: `document/SIMULATOR_SESSION_RESUME.md`

- [ ] **Step 1: Run the full suite** — the 20 sim files + `tests/test_champion_io.py` (command in the header).

Expected: **PASS**, 176 baseline + the new ones (Task 1: 4, Task 2: 5, Task 3: 4, Task 4: 3, Task 5: 4, Task 6: 2 → expect **198**). If the number differs, write the **real** one everywhere — never the predicted one.

- [ ] **Step 2: Verify the frozen core is untouched**

```bash
git diff --stat origin/Simulator -- sim/state.py sim/stepper.py sim/backend.py sim/events.py sim/probe.py sim/eventprop_stepper.py
```

Expected: **empty**.

- [ ] **Step 3: Prove the bug is dead, end to end**

Write to your scratchpad (not the repo) `verify_identity.py`:

```python
import os, sys, torch
W = r"D:\Project_MBSE\1.Reti Neurali\Rete_SNN_Test\CF_FSNN\.worktrees\Simulator"
sys.path.insert(0, W)
from core.network import build_model
from utils.champion_io import load_champion

torch.manual_seed(0)
m = build_model("baseline", hidden_size=32, rank=8, max_delay=12)
p = os.path.join(W, "verify_md12.pt")
torch.save({"epoch": 1, "val_loss": 0.1, "model_state": m.state_dict(), "optim_state": {}}, p)
h = load_champion(p)
d = h.model.layer_hidden.delays
print(f"max_delay ricostruito: {h.model.max_delay} (era 6 = il bug)")
print(f"fonte: {h.identity.sources['max_delay']}")
print(f"sinapsi irraggiungibili: {int((d >= h.model.max_delay).sum())} su {d.numel()} (era 68/128)")
os.remove(p)
```

Run it with the env python. Expected: `max_delay ricostruito: 12`, `sinapsi irraggiungibili: 0 su 128`.

- [ ] **Step 4: Render-verify the header — actually look at it**

Build `SimApp` with `QT_QPA_PLATFORM=windows` (see the cycle-1 plan for the pattern), grab the window, **Read the PNG** and check the header states family, topology and the max_delay provenance.

- [ ] **Step 5: Update the resume and commit**

In `document/SIMULATOR_SESSION_RESUME.md`: mark cycle 2 done, put the **real** test count in §How to work, note that this cycle's suite is the 20 sim files **+ `test_champion_io.py`**, and record that `train.py` now writes `arch`. Leave cycle 3 untouched.

```bash
git add document/SIMULATOR_SESSION_RESUME.md
git commit -m "docs(sim): resume — cycle 2 (checkpoint identity) done"
git push origin Simulator
```

---

## Notes for whoever executes this

- **The cross-check direction is the trap.** The inference is a lower bound. `declared > inferred` is normal; only `declared < inferred` is impossible. An earlier draft of the spec had this backwards and would have failed a normal case — the test in Task 2 pins both directions on purpose.
- **`train.py` is not the simulator.** It runs the real Azure trainings. The `getattr` is not defensive padding — but mind WHICH attribute: `hidden_size`/`rank`/`max_delay` are on every variant, while **`bit_shift` exists only on `CF_FSNN_Net`** (measured: absent on 9 of 10, EventProp included). A direct `model.bit_shift` breaks training. An earlier draft of this plan blamed `rank`, and the test written against that wrong reason **passed a broken implementation** — right conclusion, wrong reason.
- **Do not "support" the refused variants** because it looks easy. `attn`/`wta` do load through the frozen backend — and the graph then draws a readout path that ignores `Wq/Wk/Wv` and `inh_w_in`. It would not crash; it would lie. That is why they are refused.
