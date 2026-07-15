# Checkpoint identity — "load any .pt and show it for what it is" — Design Spec

**Date:** 2026-07-15 · **Branch/worktree:** `Simulator` · **Status:** design approved (user) → spec

## Goal

Let the user open **any** `.pt` — historical checkpoints pulled from Azure, or the ones they will train
tomorrow — and have the simulator **state what it loaded and how sure it is**, instead of guessing and
staying quiet when the guess is wrong.

This is cycle 2 of 3 from the 2026-07-15 request. It merges the user's points 3 (file browser) and 4
(view adaptivity), which are **one feature**: without the browser, adaptivity is YAGNI; with it, it is
mandatory. Cycle 1 (oracle ghost) is done; cycle 3 (scenario builder) is separate.

## The bug this closes is ACTIVE TODAY (measured, not hypothesised)

A `max_delay_12` checkpoint has **the same keys AND the same shapes** as `baseline` — the `delays`
buffer is `torch.randint(0, max_delay, (H, IN))`, shape `(32,4)` whatever `max_delay` is
(`core/network.py:26`). So `detect_family` answers `"baseline"`, `load_state_dict(strict=True)`
**passes**, and the model runs. Verified by execution:

- **68 of 128 input synapses are silently dropped** — delays ≥ 6 never match `for d in range(self.max_delay=6)` (`core/network.py:59-61`).
- **max |Δ| on the decoded parameters = 5.98.**
- Reachable **today**, without any file browser: `scripts/run_simulator.py <path>` takes any path
  (`scripts/run_simulator.py:17`, no validation).
- The checkpoint exists: `cf_max_delay: 18` in **12 of 512** runs (the other 246 that record it say 6).

`_infer_topology`'s docstring (`utils/champion_io.py:57-59`) states the assumption — *"all champions use
the config default (6)"* — which stops being true the moment such a checkpoint is opened.

## Established facts (verified in code, or measured)

- **The `.pt` carries no metadata**: `{epoch, val_loss, model_state, optim_state}` (`train.py:803-808`).
  Family is deduced at runtime from the state-dict signature (`utils/champion_io.py:30-52`).
- **Adding a key is safe**: `load_checkpoint` (`train.py:811-816`) reads `model_state`/`optim_state`/
  `epoch`/`val_loss` **by key**; `champion_io` reads only `model_state` (`:91`). Purely additive.
- **max_delay inference `delays.max()+1` is a LOWER BOUND** — it is exact only if some synapse drew
  `max_delay-1`. Measured over 20 000 draws per cell:

  | max_delay | H | samples | P(fail) theory | P(fail) measured | typical error |
  |---:|---:|---:|---:|---:|---|
  | 6 | 32 | 128 | 7.32e-11 | 0 / 20000 | — |
  | 12 | 32 | 128 | 1.46e-05 | 0 / 20000 | — |
  | **18** | **32** | **128** | **6.65e-04** | **15 / 20000** | **1 tick** |
  | 18 | 64 | 256 | 4.42e-07 | 0 / 20000 | — |

  → Reliable for 6 and 12; **fails ~1 in 1333 for max_delay=18 at H=32**, which is exactly the shape of
  the 12 real runs. Bigger H = more samples = safer.
- **EventProp needs no inference**: `delay_masks` has shape `(max_delay, H, IN)` → exact. Verified:
  Donatello and Michelangelo both report 6.
- **The 4 champions**: `delays.max()=5` → inferred 6 (correct). A purpose-built `build_model(max_delay=12)`
  → `delays.max()=11` → inferred 12 (correct).
- **Sidecar coverage** (`results/<RUN>/config_snapshot.json`, written as `vars(args)` at `train.py:842`):
  `cf_hidden_size`/`cf_rank` **506/512**, `cf_max_delay` **258/512**, `arch_variant` **8/512** — and
  **absent next to the champions** (`champions/<tag>/` holds `best_model.pt` alone).
- **What `detect_family` does today** (verified by execution):

  | variant | `detect_family` | then `strict=True` |
  |---|---|---|
  | `stacked_2`/`_skip`/`_3_thin` | `ValueError` (loud) | — |
  | `attn` / `wta` | **`"baseline"` — wrong** | `RuntimeError` (unexpected `Wq/Wk/Wv`, `inh_w_in`) |
  | `multi_rate` | **`"baseline"` — wrong** | `RuntimeError` (missing `decode_offset`, `logit_tau`) |
  | **`max_delay_12`** | **`"baseline"`** | **PASSES — silently wrong** |

- **`multi_rate` is numerically identical to `baseline`** once loaded (verified): `ALIFCell.forward`
  uses only `leak_div` (`core/neurons.py:54,65`) and `_HiddenLayer_ALIF_MultiRate.forward` matches
  `HiddenLayer_ALIF.forward`. It needs no dedicated handling.
- **`reset`/`infer` already work for every variant** (polymorphic `model.reset_state`/`forward_step`).
  Only **observability** (`read_probe`/`read_weights`) is family-bound.
- **`_infer_topology` already computes all four dims** (`champion_io.py:55-70`) and **discards two**:
  `:94` passes only `hidden_size` and `rank`. `build_model` **already accepts `max_delay`** (`:1469-1470`).
- **app.py's identity is broken twice** (`sim/ui/app.py:53-59`): `_champ_root = dirname(dirname(path))`
  assumes the `<root>/<tag>/best_model.pt` layout (a `.pt` elsewhere empties the champion selector), and
  `next(..., 0)` falls back to index 0 → an unknown tag under `champions/` is labelled **"Raffaello"**.
  There is no try/except around `load_champion` (`:58`) → an incompatible `.pt` kills the GUI.

## Scope

**IN**
1. `arch` field written by the trainer (root `train.py`).
2. A **pure identity resolver**: state-dict (+ optional sidecar) → structured verdict with per-value
   **source and confidence**.
3. **Honest refusal**: variants we cannot serve are named and refused, not mislabelled.
4. **File browser** in the GUI + failure that leaves the cockpit standing.
5. **Adaptivity for size only**: dynamic hidden label, H-aware graph spread.

**OUT — and why**
- **New topologies** (`stacked_*`, `attn`, `wta`). User decision. They are *refused by name*, not
  supported. Note for whoever revisits: `attn`/`wta` would actually **load** through the frozen backend,
  but `read_weights` returns `layer_out.fc_weight` while **ignoring `Wq/Wk/Wv` and `inh_w_in`** — the
  graph would not crash, it would **lie**. Refusing is the honest option until the view can show them.
  The `stacked_*` family additionally needs a new backend; that is doable without touching the frozen
  core (`make_backend` is dead code, all three `SoftwareBackend` call sites are under `sim/ui/`, and
  `read_probe`/`read_weights` are duck-typed, not in the `Protocol`) — recorded for a future cycle.
- **OUT=5 / IN=4** stay invariants: they are the ACC-IIDM physical model, not view dimensions.
- **`multi_rate`**: needs nothing (numerically identical to baseline); it is accepted as `baseline`, and
  the resolver says so rather than pretending it recognised it.

## Design

### ① `arch` in the checkpoint (root `train.py:798-808`)

Read the values **from the model, not from `args`** — three verified reasons:

1. `save_checkpoint(model, optimizer, epoch, val_loss, path)` (`train.py:798`) **has no `args`**.
2. `--cf_max_delay` and friends default to **`None`** (`train.py:1224-1232`); `build_model` resolves
   them against the config (`core/network.py:349-352`). Saving the arg would write `None` in the normal
   case — the one case that matters.
3. The model already exposes the **resolved** values, and says so: `self.hidden_size / rank / max_delay
   / bit_shift`, commented *"esposto per logging/diagnostica"* (`core/network.py:353-356`).

```python
    torch.save({
        'epoch'      : epoch,
        'val_loss'   : val_loss,
        'model_state': model.state_dict(),
        'optim_state': optimizer.state_dict(),
        # Self-describing checkpoint: the .pt carries no metadata today, so max_delay is
        # unknowable for the baseline family (delays is (H,IN) whatever max_delay is) and gets
        # silently defaulted to 6. Read from the MODEL: it holds the values already resolved
        # against config defaults, which args does not. getattr: _CF_FSNN_VariantBase exposes
        # only hidden_size/max_delay, so a plain attribute read would break stacked/attn/wta training.
        'arch'       : {'class'      : type(model).__name__,
                        'hidden_size': getattr(model, 'hidden_size', None),
                        'rank'       : getattr(model, 'rank', None),
                        'max_delay'  : getattr(model, 'max_delay', None),
                        'bit_shift'  : getattr(model, 'bit_shift', None)},
    }, path)
```

⚠️ **`getattr` is not defensive padding, it is required**: `_CF_FSNN_VariantBase._init_common`
(`core/network.py:703-713`) sets **only** `hidden_size` and `max_delay` — `rank` and `bit_shift` do not
exist on the stacked/attn/wta/multi_rate variants. `model.rank` would raise and break their training.

`class` rather than `variant`: `save_checkpoint` cannot see `--training_method` (`train.py:1213`, the
single unified CLI for all 11 variants — note `--arch_variant` **does not exist** in the current trainer;
it survives only in 8 old `config_snapshot.json` from before the CLI was unified). The class name is
equivalent for our purpose and comes free from the object. It does not separate `baseline` from
`max_delay_12` — and it does not need to: they *are* the same class, and the thing that differs is
`max_delay`, which is now saved explicitly.

Additive: every existing reader accesses by key (`train.py:811-816`, `champion_io.py:91`). Becomes
**level 1** of the hierarchy — when present, nothing is inferred. Solves the root cause for everything
trained from now on; the hierarchy below still exists because the historical checkpoints never will.

### ② The identity resolver (`utils/champion_io.py`)

A **pure function**: `resolve_identity(state_dict, arch=None, sidecar=None) -> Identity`. No `torch.load`,
no GUI, no filesystem — so it is testable on synthetic state-dicts, including the ones that lie today.

`Identity` (frozen dataclass) carries `family`, `topology` (in/hidden/out/rank), `max_delay`, plus
`sources: dict[str, str]` and `max_delay_confidence: float | None`. Resolution order for `max_delay`:

| # | source | exactness |
|---|---|---|
| 1 | `arch['max_delay']` in the `.pt` | exact |
| 2 | `delay_masks.shape[0]` (EventProp only) | exact |
| 3 | `config_snapshot.json` next to the file → `cf_max_delay` | authoritative |
| 4 | `delays.max() + 1` | **inferred** — reports `P(underestimate) ≈ ((k-1)/k) ** (H*IN)` |

> The reported probability uses the **inferred** `k`, since the true value is by definition unknown; it
> is therefore an estimate of the right order, not a guarantee. Measured against the truth it tracks it
> well (6.65e-4 predicted vs 7.5e-4 observed at k=18, H=32). Report it as an order of magnitude, and
> never round it to "certain".

**Cross-check — but the test is asymmetric, not equality.** ⚠️ An earlier draft of this spec said "if the
declared source and the inference disagree, raise". **That is wrong and would have failed a normal case.**
The inference is a **lower bound**: `delays.max()+1 ≤ max_delay`, with equality only if some synapse drew
the top value. So:

| relation | meaning | action |
|---|---|---|
| `declared == inferred` | agreement | use declared |
| `declared > inferred` | **normal** — the inference underestimated (measured: happens ~1 in 1333 at 18/H=32) | use declared, no complaint |
| `declared < inferred` | **impossible** — a synapse holds a delay ≥ declared, which that model could never have produced | **raise**, naming both values and both sources |

The third row is the real cross-check: it is not "the two differ", it is "the declared value is refuted by
the weights themselves". That is what catches a sidecar belonging to a different run, or an `arch` field
copied from elsewhere. Silently preferring either source is how the current bug behaves.

Family/variant detection is extended to **name** what it sees: `Wq/Wk/Wv` → `attn`, `inh_w_in` → `wta`,
`layers_hidden.N.*` → `stacked_N`, `layer_hidden_0.*` + `skip_weight` → `stacked_2_skip`. Naming them is
what makes an honest refusal possible; today they are silently called `baseline`.

### ③ Honest refusal

`resolve_identity` never raises for an unknown-but-nameable variant: it returns an `Identity` with
`supported=False` and a `reason`. The caller decides. `load_champion` raises with that reason; the GUI
shows it. Distinguishing *"I know what this is and cannot serve it"* from *"I have no idea what this is"*
is the whole point.

### ④ File browser + survivable failure (`sim/ui/app.py`)

**File → Apri champion…** → `QFileDialog.getOpenFileName(filter="Checkpoint (*.pt)")` → resolve → load.
On failure: a `QMessageBox` with the reason, and **the current champion keeps running** — nothing is torn
down before the new one is known-good.

Identity in the UI replaces the guess: `_champ_name` comes from the resolved identity and the file path,
never from `next(..., 0)`. The header states family, topology and `max_delay` **with its source** —
`max_delay 6 (inferito)` is a different claim from `max_delay 6 (dal checkpoint)` and must read
differently. An externally-opened champion is appended to the selector as its own entry, so swapping back
to the four bundled ones keeps working; a `.pt` outside `champions/` no longer empties the selector.

### ⑤ Size adaptivity (`sim/ui/panels.py`)

`"hidden · 32 ALIF"` (`panels.py:308`, the only literal `32` in `sim/`) → built from the real H.
`yspread`'s `span=32.0` (`panels.py:248`) is tuned for 16 nodes per column; make it scale with the
per-column count so H=64 does not overlap. Everything else in the panels is already shape-driven.

## Errors and edge cases

| case | behaviour |
|---|---|
| `.pt` of a nameable but unsupported variant (`stacked_*`, `attn`, `wta`) | refused by name, with the reason; cockpit untouched |
| `.pt` with an unrecognisable signature | refused as "unknown signature"; cockpit untouched |
| declared `max_delay` **below** the inference | raise: the weights refute it (a synapse holds a delay that model could not produce) |
| declared `max_delay` **above** the inference | normal — the inference underestimated; use declared, silently |
| no sidecar, baseline family | inferred; UI labels it inferred and reports the confidence |
| `.pt` outside `champions/` | loads; selector keeps the 4 bundled + the opened one |
| corrupt / non-torch file | refused with the torch error surfaced, cockpit untouched |

## Testing

The resolver is pure → tested without Qt on synthetic state-dicts:

1. **The active bug, closed** — build `build_model('baseline', max_delay=12)`, save, resolve, load: the
   reconstructed model must use `max_delay=12` and **drop zero synapses**. Today this silently drops
   68/128 with max |Δ| = 5.98 on the decoded params. Assert on the synapse count, not on a label.
2. **EventProp is exact** — `delay_masks.shape[0]` wins; the inference is never consulted.
3. **Cross-check has teeth, in the right direction** — two cases, and getting them backwards is the
   trap: sidecar says **6** while `delays` holds a 17 (inference 18) → **raises**, naming both, because
   the weights refute the sidecar. Sidecar says **18** while the inference says 17 → **passes silently**
   and uses 18, because a lower bound under-shooting is the expected behaviour, not a conflict. A test
   that only checks "differ → raise" would pass a wrong implementation and fail a right one.
4. **Naming, not mislabelling** — `attn`/`wta`/`stacked_2_skip` state-dicts resolve to their own names
   with `supported=False`; none of them comes back as `"baseline"`.
5. **`multi_rate` is accepted as baseline** and the resolver says the family was matched by signature,
   not that it recognised the variant.
6. **The 4 champions still resolve identically** to today (regression: family, topology, rank).
7. **GUI survives a bad file** — opening a rubbish `.pt` shows a message and leaves the running champion
   in place (no torn-down cockpit, no traceback).
8. **`arch` round-trip** — a checkpoint saved by the trainer resolves at level 1 with nothing inferred.
9. **`save_checkpoint` survives every variant (teeth)** — call it on a model of each of the 11 variants
   `build_model` can produce and assert it does not raise. `_CF_FSNN_VariantBase` has no `rank`/
   `bit_shift`, so a plain `model.rank` breaks stacked/attn/wta **training** — a failure outside the
   simulator entirely, which no sim test would ever catch.
10. **Core bit-identity** — the frozen six untouched; full sim suite green.

**Where the tests live**: `tests/test_champion_io.py` — `champion_io` is `utils/`, not `sim/`, and that
file already exists and **runs green in `cf_sim`** (verified: 9 passed). The resume's blanket warning
that "non-sim tests fail in that env" does **not** hold for it. So the cycle's verification command is
the 20 sim files **plus** `tests/test_champion_io.py`; the list of 20 stays 20.

Baseline: **167 sim tests green** + **9 champion_io tests green** (2026-07-15, after cycle 1).
No LAPACK (OMP #15).

## Known debt (out of scope, do NOT fix here)

- `sim/ui/app.py:591` — `ReplayLog.seed` is fed the **scenario index**. Cycle 3 (scenario builder).
- `sim/events.py:37-38` — two sequential brakes make the leader jump **+16 m/s in one tick** (measured).
  Cycle 3.
- `core/network.py:1506` — `stacked_3_thin` hardcodes `[24,24,24]`/`[6,6,6]` and ignores
  `hidden_size`/`rank`, so such a champion is not reconstructible via `build_model`. Only matters if a
  future cycle takes on the stacked family.
