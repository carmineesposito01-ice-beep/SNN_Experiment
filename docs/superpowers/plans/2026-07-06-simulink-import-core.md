# SNN Champions — Plan 1: Export + Core + Pure-Function Parity

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Portare i 4 champion CF_FSNN in MATLAB come una funzione `snn_core` type-parametrizzata (double/fi) e provarne la **parità float** vs il golden PyTorch — la fondazione della libreria Simulink (fase ②).

**Architecture:** Un export Python (`export_champions.py`, via `champion_io`) scrive pesi po2 + config + **golden** in `champions_export.mat`. In MATLAB, un core type-agnostic (`snn_core.m`, pattern types-table `snn_types.m` + entry-point `snn_entry.m`) replica il forward inference; `run_parity_tests.m` (headless `matlab -batch`) confronta l'output MATLAB in `double` col golden PyTorch. Nessuna libreria/blocco Simulink e nessun fixed-point in questo Plan (→ Plan 2).

**Tech Stack:** Python 3 + PyTorch + scipy.io (export); MATLAB R2026a (core + parità). Nessun toolbox extra richiesto in Plan 1 (base MATLAB). Repo worktree: `.worktrees/Simulink_Importer`.

**Scope (Plan 1):** `scripts/export_champions.py`, `matlab/snn_types.m`, `matlab/snn_entry.m`, `matlab/snn_core.m`, `matlab/run_parity_tests.m`, `tests/test_export_champions.py`. **Fuori Plan 1** (→ Plan 2): `build_library.m` (.slx), parità a livello di blocco, `check_hdl.m`.

**Riferimento matematico autorevole:** `document/SIMULINK_IMPORT_DESIGN.md` §2-3 (forward per-tick, normalizzazione, decode). Tutti i numeri/formule vengono dal codice reale (`core/`, `config.py`) — non inventare.

**Come si eseguono i test MATLAB:** `matlab -batch "cd matlab; run_parity_tests"` dalla root del worktree (exit code ≠0 su fallimento). MATLAB è su PATH (R2026a). Startup ~30-60 s per invocazione.

---

## Task 1: Export champions → `.mat` (Python, TDD locale)

**Files:**
- Create: `scripts/export_champions.py`
- Test: `tests/test_export_champions.py`

Contesto API (già esistente): `from utils.champion_io import load_champion` → `handle` con `.model` (nn.Module in eval), `.variant` (`'baseline'`|`'eventprop_alif_full'`), `.topology` (`{'hidden','input','rank','output'}`). Costanti champion→dir in `document/SIMULINK_IMPORT_DESIGN.md` §0. `po2_quantize` sta in `core.hardware` (`from core.hardware import po2_quantize` — è `PowerOf2Quantize.apply`). Normalizzazione: `core`/`data/generator.py` costanti `NORM_S_MAX=150, NORM_V_MAX=40, NORM_DV_MAX=20, NORM_VL_MAX=40` (`config.py:110-113`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_export_champions.py
import os, sys
import numpy as np
import pytest
from scipy.io import loadmat

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from scripts.export_champions import export_all, CHAMPIONS  # noqa: E402

OUT = os.path.join(REPO, "matlab", "champions_export.mat")

@pytest.fixture(scope="module")
def mat():
    export_all(OUT, n_test=16, seed=0)
    return loadmat(OUT, struct_as_record=False, squeeze_me=True)

def test_all_four_present(mat):
    champs = mat["champions"]
    names = {c.name for c in np.atleast_1d(champs)}
    assert names == {"Donatello", "Michelangelo", "Raffaello", "Leonardo"}

@pytest.mark.parametrize("name,rank", [("Donatello",16),("Michelangelo",16),("Raffaello",8),("Leonardo",8)])
def test_topology_and_fields(mat, name, rank):
    c = {x.name: x for x in np.atleast_1d(mat["champions"])}[name]
    assert int(c.rank) == rank
    assert c.fc_weight.shape == (32, 4)
    assert c.rec_U.shape == (32, rank)
    assert c.rec_V.shape == (rank, 32)
    assert c.readout.shape == (5, 32)
    assert c.delays.shape == (32, 4)
    assert c.base_threshold.shape == (32,)
    assert c.leak_div.shape == (32,)
    # golden
    assert c.x_phys.shape == (16, 4)
    assert c.x_norm.shape == (16, 4)
    assert c.y_params.shape == (16, 5)

def test_weights_are_po2(mat):
    # ogni peso non-zero deve essere ±2^k con k intero in [-4,1]
    c = np.atleast_1d(mat["champions"])[0]
    for W in (c.fc_weight, c.rec_U, c.rec_V, c.readout):
        nz = W[W != 0]
        k = np.log2(np.abs(nz))
        assert np.allclose(k, np.round(k)), "pesi non potenza-di-2"
        assert k.min() >= -4 - 1e-9 and k.max() <= 1 + 1e-9

def test_params_in_physical_bounds(mat):
    lo = np.array([8,0.5,1.0,0.3,0.5]); hi = np.array([45,2.5,5.0,2.5,3.0])
    for c in np.atleast_1d(mat["champions"]):
        assert (c.y_params >= lo - 1e-3).all() and (c.y_params <= hi + 1e-3).all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd .worktrees/Simulink_Importer && python -m pytest tests/test_export_champions.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'scripts.export_champions'`.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/export_champions.py
"""Esporta i 4 champion in champions_export.mat per la libreria Simulink (fase 2).

Per ogni champion: pesi po2 (via la vera PowerOf2Quantize) + delays (esplicito!) +
soglie + leak_div + readout + decode + costanti di normalizzazione + GOLDEN
(input fisici, input normalizzati, output PyTorch dei 5 parametri).
"""
import os
import numpy as np
import torch
from scipy.io import savemat

from utils.champion_io import load_champion
from core.hardware import po2_quantize

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# nome blocco -> dir champion (document/SIMULINK_IMPORT_DESIGN.md §0)
CHAMPIONS = {
    "Donatello":    "PE_t05_gp0002",
    "Michelangelo": "A_lr1e2_t06_r16",
    "Raffaello":    "R33_C2_A1_T12_fix",
    "Leonardo":     "LS3_PEAK_R0_launch_d03",
}

# normalizzazione (config.py:110-113)
NORM = dict(S=150.0, V=40.0, DV=20.0, VL=40.0)
PHYS_LO = np.array([0.0, 0.0, -20.0, 0.0])     # range fisici plausibili di [s, v, dv, v_l]
PHYS_HI = np.array([150.0, 40.0, 20.0, 40.0])


def _np(t):
    return t.detach().cpu().numpy().astype(np.float64)


def _readout_key(sd):
    return "layer_out.weight" if "layer_out.weight" in sd else "layer_out.fc_weight"


def _thr_keys(sd):
    if "layer_hidden.base_threshold" in sd:      # eventprop (flat)
        return "layer_hidden.base_threshold", "layer_hidden.thresh_jump"
    return "layer_hidden.cell.base_threshold", "layer_hidden.cell.thresh_jump"


def normalize(x_phys):
    """x_phys (N,4) fisico -> (N,4) normalizzato [0,1]. Identico a data/generator.py."""
    s, v, dv, vl = x_phys[:, 0], x_phys[:, 1], x_phys[:, 2], x_phys[:, 3]
    return np.stack([
        s / NORM["S"],
        v / NORM["V"],
        (np.clip(dv, -NORM["DV"], NORM["DV"]) + NORM["DV"]) / (2 * NORM["DV"]),
        vl / NORM["VL"],
    ], axis=1)


def _leak_div(sd, hidden):
    for k in ("layer_hidden.cell.leak_div", "layer_hidden.leak_div"):
        if k in sd:
            return _np(sd[k]).reshape(-1)[:hidden]
    return np.full(hidden, 8.0)   # default 2^bit_shift, bit_shift=3


def export_champion(name, folder, n_test=16, seed=0):
    path = os.path.join(REPO, "champions", folder, "best_model.pt")
    h = load_champion(path)
    sd = h.model.state_dict()
    hidden, rank = h.topology["hidden"], h.topology["rank"]
    rk = _readout_key(sd)
    thr_k, tj_k = _thr_keys(sd)

    # pesi po2 (applica la vera quantizzazione una volta)
    with torch.no_grad():
        fc = _np(po2_quantize(sd["layer_hidden.fc_weight"]))
        U = _np(po2_quantize(sd["layer_hidden.rec_U"]))
        V = _np(po2_quantize(sd["layer_hidden.rec_V"]))
        Wout = _np(po2_quantize(sd[rk]))

    # golden: input fisico deterministico -> normalizza -> forward PyTorch
    rng = np.random.default_rng(seed)
    x_phys = rng.uniform(PHYS_LO, PHYS_HI, size=(n_test, 4))
    x_norm = normalize(x_phys)
    with torch.no_grad():
        xt = torch.tensor(x_norm, dtype=torch.float32).unsqueeze(0)   # (1, N, 4)
        y = h.model.forward_sequence(xt)[0].cpu().numpy().astype(np.float64)   # (N, 5)

    def buf(key, default):
        b = dict(h.model.named_buffers())
        return _np(b[key]) if key in b else default

    return {
        "name": name, "variant": h.variant,
        "hidden": np.int32(hidden), "rank": np.int32(rank),
        "n_ticks": np.int32(10), "max_delay": np.int32(6),
        "fc_weight": fc, "rec_U": U, "rec_V": V, "readout": Wout,
        "delays": _np(sd["layer_hidden.delays"]).astype(np.float64),
        "base_threshold": _np(sd[thr_k]).reshape(-1),
        "thresh_jump": _np(sd[tj_k]).reshape(-1),
        "leak_div": _leak_div(sd, hidden),
        "param_lo": buf("param_lo", np.array([8,0.5,1.0,0.3,0.5])),
        "param_hi": buf("param_hi", np.array([45,2.5,5.0,2.5,3.0])),
        "decode_offset": buf("decode_offset", np.zeros(5)),
        "logit_tau": buf("logit_tau", np.ones(5)),
        "norm": np.array([NORM["S"], NORM["V"], NORM["DV"], NORM["VL"]]),
        "x_phys": x_phys, "x_norm": x_norm, "y_params": y,
    }


def export_all(out_path, n_test=16, seed=0):
    champs = [export_champion(n, f, n_test, seed) for n, f in CHAMPIONS.items()]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    savemat(out_path, {"champions": champs}, format="5", oned_as="column", do_compression=True)
    return out_path


if __name__ == "__main__":
    p = export_all(os.path.join(REPO, "matlab", "champions_export.mat"))
    print(f"Wrote {p}")
```

> **Nota `delays`:** il test assume che `layer_hidden.delays` sia nello state_dict. Se `load_champion` mostra
> che manca (è un buffer), estrarlo da `dict(h.model.named_buffers())["layer_hidden.delays"]` invece che da `sd`.
> Verificare con: `python -c "from utils.champion_io import load_champion as L; import numpy as np; h=L('champions/R33_C2_A1_T12_fix/best_model.pt'); print([k for k in h.model.state_dict() if 'delay' in k], [k for k,_ in h.model.named_buffers() if 'delay' in k])"`

- [ ] **Step 4: Run test to verify it passes**

Run: `cd .worktrees/Simulink_Importer && python -m pytest tests/test_export_champions.py -q`
Expected: PASS (5 test). Se `test_topology_and_fields` fallisce su `delays`, applicare la nota sopra.

- [ ] **Step 5: Commit**

```bash
git add scripts/export_champions.py tests/test_export_champions.py matlab/champions_export.mat
git commit -m "feat(fase2): export champion -> champions_export.mat (pesi po2 + golden)"
```

---

## Task 2: MATLAB scaffolding — types-table, normalize, decode, entry-point

**Files:**
- Create: `matlab/snn_types.m`, `matlab/snn_entry.m`, `matlab/snn_normalize.m`, `matlab/snn_decode.m`

Questi sono gli stadi I/O + il meccanismo type-parametrizzato. Il core (Task 3) sta in mezzo.

- [ ] **Step 1: Write `snn_types.m`**

```matlab
function T = snn_types(dt)
%SNN_TYPES Prototipi di tipo per il core type-parametrizzato.
%  dt = 'double' (parita' vs golden) | 'fixed' (HDL, Qm.n da FPGA_REPORT).
  switch dt
    case 'double'
      z = double([]);
      T = struct('V',z,'fatigue',z,'acc',z,'raw',z,'w',z);
    case 'fixed'
      T = struct( ...
        'V',       fi([], true, 11, 5), ...   % Q5.5
        'fatigue', fi([], true,  9, 5), ...   % Q3.5
        'acc',     fi([], true,  9, 5), ...   % accumulatori Q3.5
        'raw',     fi([], true, 13, 5), ...   % readout LI Q7.5
        'w',       fi([], true,  8, 5));      % pesi po2 (placeholder Plan-2 HDL)
    otherwise
      error('snn_types:dt','dt deve essere ''double'' o ''fixed''');
  end
end
```

- [ ] **Step 2: Write `snn_normalize.m`**

```matlab
function xn = snn_normalize(x_phys, norm)
%SNN_NORMALIZE  x_phys [4x1] fisico -> xn [4x1] normalizzato. norm=[S V DV VL].
%  Identico a data/generator.py (config.py:110-113).
  S = norm(1); V = norm(2); DV = norm(3); VL = norm(4);
  dv = min(max(x_phys(3), -DV), DV);
  xn = [ x_phys(1)/S; x_phys(2)/V; (dv + DV)/(2*DV); x_phys(4)/VL ];
end
```

- [ ] **Step 3: Write `snn_decode.m`**

```matlab
function p = snn_decode(raw, param_lo, param_hi, decode_offset, logit_tau)
%SNN_DECODE  raw [5x1] (potenziale LI) -> p [5x1] parametri fisici IDM.
%  p = lo + (hi-lo).*sigmoid((raw-offset)./tau)  (network.py:437-438)
  adj = (raw - decode_offset) ./ logit_tau;
  s   = 1 ./ (1 + exp(-adj));
  p   = param_lo + (param_hi - param_lo) .* s;
end
```

- [ ] **Step 4: Write `snn_entry.m`**

```matlab
function p = snn_entry(dt, x_phys, W)
%SNN_ENTRY  Entry-point type-parametrizzato: cast ai bordi -> core -> decode.
%  dt: 'double'|'fixed'. x_phys [4x1] fisico. W: struct pesi/config del champion.
%  Ritorna p [5x1] parametri fisici. Lo stato persistente vive dentro snn_core.
  T  = snn_types(dt);
  xn = snn_normalize(x_phys, W.norm);
  xn = cast(xn, 'like', T.V);
  raw = snn_core(xn, W, T);                        % [5x1] potenziale LI (ultimo tick)
  p   = snn_decode(double(raw), W.param_lo, W.param_hi, W.decode_offset, W.logit_tau);
end
```

> Il decode gira in `double` in Plan 1 (stadio isolato; LUT/CORDIC sono Plan-2 HDL). Il core riceve `T` per
> castare gli stati interni; in `'double'` è un no-op.

- [ ] **Step 5: Commit**

```bash
git add matlab/snn_types.m matlab/snn_normalize.m matlab/snn_decode.m matlab/snn_entry.m
git commit -m "feat(fase2): scaffolding MATLAB (types-table, normalize, decode, entry)"
```

---

## Task 3: `snn_core.m` — il forward ALIF (type-agnostic, stato persistente)

**Files:**
- Create: `matlab/snn_core.m`

Traduzione 1:1 del forward per-tick (`document/SIMULINK_IMPORT_DESIGN.md` §2.2). Stato `persistent`,
read-before-write. In Plan 1 gira in `double`; la forma è già HDL-idiomatica (leak via `bitsra`-equivalente,
ricorrenza low-rank a 2 passi). `snn_core` viene chiamato **una volta per step di controllo** (x normalizzato
costante sui 10 tick interni); lo stato persiste tra chiamate; reset con `snn_core([], [], [], 'reset')`.

- [ ] **Step 1: Write the implementation**

```matlab
function raw = snn_core(xn, W, T, cmd)
%SNN_CORE  Un passo di controllo = n_ticks tick SNN interni. Ritorna raw [5x1] (LI).
%  Stato persistente (V, fatigue, s_prev, V_LI, x_buf) tra chiamate. 'reset' azzera.
  persistent V fatigue s_prev V_LI x_buf inited
  hidden = double(W.hidden); rank = double(W.rank);
  maxd = double(W.max_delay); nt = double(W.n_ticks); out = 5;

  if nargin >= 4 && strcmp(cmd, 'reset')
    inited = [];
  end
  if isempty(inited)
    V = zeros(hidden,1,'like',T.V); fatigue = zeros(hidden,1,'like',T.fatigue);
    s_prev = zeros(hidden,1,'like',T.V); V_LI = zeros(out,1,'like',T.raw);
    x_buf = zeros(4, maxd, 'like',T.V);   % ring buffer: colonna d = ritardo d
    inited = true;
  end
  if nargin < 2, raw = double(V_LI); return; end   % reset-only

  % pesi (gia' po2). In 'double' matmul diretto; in HDL i po2-constant -> shift (CSD).
  W_po2 = cast(W.fc_weight, 'like', T.w);   % 32x4
  U = cast(W.rec_U, 'like', T.w); Vr = cast(W.rec_V, 'like', T.w);   % 32xR, Rx32
  Wout = cast(W.readout, 'like', T.w);      % 5x32
  base_th = cast(W.base_threshold(:), 'like', T.V);
  tjump   = max(cast(W.thresh_jump(:), 'like', T.V), 0);
  ld = cast(W.leak_div(:), 'like', T.V);    % 32x1 (=8)
  delays = double(W.delays);                % 32x4 interi in [0,6)

  for k = 1:nt
    % 1. shift del ring-buffer + inserimento x corrente in colonna 1 (ritardo 0)
    x_buf(:, 2:end) = x_buf(:, 1:end-1);
    x_buf(:, 1) = xn;

    % 2. corrente sinaptica ritardata: per ogni sinapsi (i,j) usa x_buf(:, delays+1)
    I_input = zeros(hidden,1,'like',T.acc);
    for d = 0:maxd-1
      mask = (delays == d);                 % 32x4
      I_input = I_input + sum((W_po2 .* mask) .* x_buf(:, d+1).', 2);
    end

    % 3. ricorrenza LOW-RANK in 2 passi (mai densa)
    t_lr = Vr * s_prev;                      % Rx1
    rec  = U * t_lr;                          % 32x1

    % 4. membrana: leak bit-shift (V/ld) + drive. In double: V - V./ld.
    drive = I_input + rec;
    V(:) = V - V ./ ld + drive;              % ld=8 -> 7/8 V

    % 5. soglia adattiva (fatigue pre-update)
    eff_th = base_th + max(fatigue, 0);

    % 6. spike (comparatore hard >=)
    s = cast(V >= eff_th, 'like', T.V);

    % 7. fatigue: leak + salto
    fatigue(:) = fatigue - fatigue ./ ld + s .* tjump;

    % 8. soft reset
    V(:) = V - s .* eff_th;
    s_prev = s;

    % 9. output LI: leak + readout
    V_LI(:) = V_LI - V_LI ./ 8 + Wout * s;   % LI bit_shift=3 fisso (7/8)
  end
  raw = V_LI;
end
```

> **Nota bit-shift in Plan 1:** in `double` la divisione `V./ld` (ld potenza di 2) è esatta e = shift. Nel build
> HDL (Plan 2) si sostituisce con `bitsra` esplicito + si verifica 0-DSP. Non cambiare ora: Plan 1 valida la
> **matematica**, non la forma di sintesi.
> **Nota ring-buffer/delays:** questo assume che `delays(i,j)` selezioni il tick di ritardo per la sinapsi
> input-j → hidden-i, come in `network.py:59-61`. Se la parità (Task 4) fallisce sul solo termine sinaptico,
> ispezionare l'ordine esatto di `appendleft`/indicizzazione del ring-buffer in `core/neurons.py` e allineare.

- [ ] **Step 2: Commit (l'implementazione si valida in Task 4)**

```bash
git add matlab/snn_core.m
git commit -m "feat(fase2): snn_core forward ALIF type-agnostic (double, stato persistente)"
```

---

## Task 4: `run_parity_tests.m` — parità float vs golden (headless)

**Files:**
- Create: `matlab/run_parity_tests.m`

Test d'accettazione di Plan 1: per ogni champion, `snn_entry('double', x_phys(t,:), W)` sui campioni golden
deve riprodurre `y_params` entro tolleranza stretta. **Prima** la parità di `snn_normalize` (isola bug di
scala/trasposizione), poi il forward completo.

- [ ] **Step 1: Write the test harness**

```matlab
function run_parity_tests()
%RUN_PARITY_TESTS  Parita' float del core MATLAB vs golden PyTorch. Exit code !=0 su fail.
  here = fileparts(mfilename('fullpath'));
  d = load(fullfile(here, 'champions_export.mat'));
  champs = d.champions;
  tolN = 1e-9;    % normalizzazione: deve essere ~esatta
  tolY = 1e-4;    % forward float: tolleranza stretta
  failed = false;

  for i = 1:numel(champs)
    c = champs(i);
    W = to_weights(c);
    N = size(c.x_phys, 1);

    % (a) parita' normalizzazione
    en = 0;
    for t = 1:N
      en = max(en, max(abs(snn_normalize(c.x_phys(t,:).', W.norm) - c.x_norm(t,:).')));
    end

    % (b) parita' forward completo (reset stato tra i campioni: sono indipendenti)
    ey = 0;
    for t = 1:N
      snn_core([], [], snn_types('double'), 'reset');
      p = snn_entry('double', c.x_phys(t,:).', W);
      ey = max(ey, max(abs(p(:) - c.y_params(t,:).')));
    end

    okN = en < tolN; okY = ey < tolY;
    fprintf('%-13s  norm|err|=%.2e [%s]   fwd|err|=%.2e [%s]\n', ...
            char(c.name), en, tf(okN), ey, tf(okY));
    failed = failed || ~okN || ~okY;
  end
  if failed, error('run_parity_tests:FAIL', 'Parita'' fallita'); end
  disp('ALL PARITY PASS');
end

function W = to_weights(c)
  W = struct('hidden',c.hidden,'rank',c.rank,'n_ticks',c.n_ticks,'max_delay',c.max_delay, ...
    'fc_weight',c.fc_weight,'rec_U',c.rec_U,'rec_V',c.rec_V,'readout',c.readout, ...
    'delays',c.delays,'base_threshold',c.base_threshold,'thresh_jump',c.thresh_jump, ...
    'leak_div',c.leak_div,'param_lo',c.param_lo,'param_hi',c.param_hi, ...
    'decode_offset',c.decode_offset,'logit_tau',c.logit_tau,'norm',c.norm);
end

function s = tf(b), if b, s='PASS'; else, s='FAIL'; end, end
```

- [ ] **Step 2: Run to verify it fails (core non ancora corretto / stato)**

Run: `matlab -batch "cd matlab; run_parity_tests"` (dalla root del worktree)
Expected: gira e stampa gli errori per-champion. Verosimilmente `norm PASS` e `fwd FAIL` al primo giro
(differenze di indicizzazione ring-buffer / ordine tick). Questo è il segnale TDD per correggere `snn_core`.

- [ ] **Step 3: Debug loop fino a parità**

Iterare su `snn_core.m` (indicizzazione `delays`/ring-buffer, ordine leak/threshold/reset, uso di `s_prev`)
confrontando col riferimento `core/neurons.py:49-88` finché `fwd|err| < 1e-4` per **tutti e 4**. Se serve
isolare, esportare da PyTorch anche il `raw` pre-decode (aggiungere `raw_out` al golden in Task 1) e confrontare
`snn_core` direttamente col `raw`, così il decode non maschera l'errore.

- [ ] **Step 4: Run to verify it passes**

Run: `matlab -batch "cd matlab; run_parity_tests"`
Expected: `ALL PARITY PASS`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add matlab/run_parity_tests.m
git commit -m "test(fase2): parita' float core MATLAB vs golden PyTorch (4 champion)"
```

---

## Self-review (fatta)

- **Spec coverage (Plan 1):** export+po2+delays+golden (§5.1 ✓ Task 1); normalize (§3.1 ✓ Task 2); decode (§3.2 ✓ Task 2); core forward+low-rank 2-passi+leak+ALIF+LI (§2.2 ✓ Task 3); type-parametrizzato types-table+entry (§1 ✓ Task 2/3); parità golden pura (§6 ✓ Task 4). **Fuori Plan 1 (→ Plan 2):** libreria `.slx`/blocchi, parità di blocco, `check_hdl` (screener/checkhdl), fixed-point `fi`, `makehdl` — coperti da §5.2/§6/§7 dello spec, non da questo plan.
- **Placeholder scan:** nessun TBD; ogni step ha codice/comando reale. Due note esplicite di verifica (delays buffer; ring-buffer indexing) sono guardrail di debug, non placeholder.
- **Type consistency:** `snn_types` (V/fatigue/acc/raw/w) usati coerentemente in `snn_core`/`snn_entry`; campi di `W` (`to_weights`) = chiavi scritte da `export_champion`; `snn_normalize(x,norm)` firma coerente entry↔test.

## Execution handoff

Vedi in chat le due opzioni di esecuzione.
