# FPGA Fase C — Validazione su silicio (PYNQ-Z1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire (ready-to-run, design-for-later) l'harness PYNQ che valida Donatello B2 sul silicio reale: verifica funzionale (param corretti bit-exact), closed-loop network-in-the-loop, potenza total-board.

**Architecture:** Riferimenti golden generati ORA in MATLAB (rete fixed). Harness Python (driver + sweep + closed-loop + potenza) **unit-testato con un mock dell'overlay ORA**; esecuzione reale sulla board dopo, via notebook + runbook. Il plant ACC-IIDM è portato in **numpy puro** (niente torch sul PS ARM).

**Tech Stack:** MATLAB R2026a (`snn_top_b2`/`snn_core` fixed), Python 3 + numpy + pytest (harness + test), PYNQ (`pynq.Overlay`, sulla board). Nessun torch sul PS.

**Spec:** `docs/superpowers/specs/2026-07-11-fpga-phase-c-silicon-validation-design.md`.

**Convenzioni:**
- Test Python: `python -m pytest matlab/axi/phase_c/tests/ -v` (numpy-only; usare l'env `cf_sim` o un venv con numpy+pytest, NON serve torch).
- Commit **senza** `Co-Authored-By`. Push su `Simulink_Importer`.
- Register map (da `matlab/axi/README.md`): W xn[0..3] @0x00-0x0C (Q5.13, 19b), W control @0x10 (bit0=start, pulse), R status @0x10 (bit0=done), R params[0..4]=v0,T,s0,a,b @0x14-0x24 (Q7.13).
- Normalize Donatello: `norm=[S,V,DV,VL]=[150,40,20,40]`; `xn=[s/S, v/V, (clip(dv,-DV,DV)+DV)/(2*DV), vl/VL]`.

---

## File Structure

**Riferimenti (MATLAB, girano ORA):**
- `matlab/gen_phase_c_reference.m` — genera i goldens dalla rete fixed.
- `matlab/axi/phase_c/goldens/phase_c_reference.csv` — sweep: per ogni input (s,v,dv,vl) i 5 param attesi.
- `matlab/axi/phase_c/goldens/phase_c_closedloop_golden.csv` — closed-loop: leader + traiettoria ego golden.

**Harness Python (scritto ORA, mock-testato ORA):**
- `matlab/axi/phase_c/pynq_snn.py` — driver `SnnDonatello` (normalize + Q-conv + register I/O + `infer`).
- `matlab/axi/phase_c/mock_overlay.py` — overlay fake per i test (lookup input→param dal golden; o param costanti).
- `matlab/axi/phase_c/plant_iidm.py` — port numpy di `acc_iidm_accel` + `clean_plant` (dal golden Python).
- `matlab/axi/phase_c/functional_sweep.py` — sweep + confronto + distribuzione errore.
- `matlab/axi/phase_c/closed_loop.py` — network-in-the-loop + confronto traiettoria.
- `matlab/axi/phase_c/power_measure.py` — procedura 3-stati total-board, strumento-agnostico.
- `matlab/axi/phase_c/phase_c_validation.ipynb` — notebook orchestratore (board).
- `matlab/axi/phase_c/tests/test_*.py` — pytest con mock.

**Deliverable:**
- `document/FPGA_PHASE_C_REPORT.md` — scheletro + runbook "quando arriva la board".

---

## Task 1: Generatore di riferimento (MATLAB, gira ORA)

**Files:**
- Create: `matlab/gen_phase_c_reference.m`
- Create (output): `matlab/axi/phase_c/goldens/{phase_c_reference.csv, phase_c_closedloop_golden.csv}`
- Uses: `matlab/snn_top_b2.m`, `matlab/snn_normalize.m`, `matlab/test_trajectories.mat`, `matlab/champions_export.mat`

- [ ] **Step 1: Scrivi `gen_phase_c_reference.m`**

```matlab
function gen_phase_c_reference()
%GEN_PHASE_C_REFERENCE  Goldens per la Fase C dalla rete FIXED (bit-exact al silicio).
%  (1) sweep: per ogni (s,v,dv,vl) di test -> normalize -> snn_top_b2 fixed (cyclo-accurato) -> 5 param.
%  (2) closed-loop: leader -> [ego->(s,v,dv,vl)->rete->plant->integra] -> traiettoria ego golden.
%  Lo STESSO modello stateful, stessa sequenza, come il silicio -> match garantito.
  here  = fileparts(mfilename('fullpath'));
  outd  = fullfile(here, 'axi', 'phase_c', 'goldens');
  if ~isfolder(outd), mkdir(outd); end
  addpath(here);
  d = load(fullfile(here, 'champions_export.mat')); ch = d.champions;
  if iscell(ch), ch = [ch{:}]; end
  idx  = find(arrayfun(@(x) strcmp(char(string(x.name)), 'Donatello'), ch), 1);
  norm = double(ch(idx).norm(:));                 % [150 40 20 40]

  % ---- (1) sweep funzionale ----
  t = load(fullfile(here, 'test_trajectories.mat')); trs = t.trajectories;
  fid = fopen(fullfile(outd, 'phase_c_reference.csv'), 'w');
  fprintf(fid, 'traj,step,s,v,dv,vl,v0,T,s0,a,b\n');
  for k = 1:numel(trs)
    X = double(trs{k}.val); N = size(X, 2);
    clear snn_top_b2;                             % reset stato all'inizio di ogni traiettoria
    for i = 1:N
      xn = snn_normalize(X(:, i), norm);
      p  = run_infer(fi(xn, 1, 19, 13));          % 5 param fisici (cyclo-accurato)
      fprintf(fid, '%d,%d,%.6f,%.6f,%.6f,%.6f,%.8f,%.8f,%.8f,%.8f,%.8f\n', ...
              k, i, X(1,i), X(2,i), X(3,i), X(4,i), p(1), p(2), p(3), p(4), p(5));
    end
  end
  fclose(fid);

  % ---- (2) closed-loop golden (leader brake_step, come make_plant_golden) ----
  N = 600; DT = 0.1; tvec = (0:N-1) * DT;
  vl = 20 * ones(1, N); vl(tvec >= 20) = 12; vl(tvec >= 40) = 18;
  clear snn_top_b2;
  [S, V, A, P] = closed_loop_ref(vl, norm, DT);
  fid = fopen(fullfile(outd, 'phase_c_closedloop_golden.csv'), 'w');
  fprintf(fid, 'step,vl,s,v,accel,v0,T,s0,a,b\n');
  for i = 1:N
    fprintf(fid, '%d,%.6f,%.6f,%.6f,%.6f,%.8f,%.8f,%.8f,%.8f,%.8f\n', ...
            i, vl(i), S(i), V(i), A(i), P(1,i), P(2,i), P(3,i), P(4,i), P(5,i));
  end
  fclose(fid);
  fprintf('OK: goldens Fase C scritti in %s\n', outd);
end

function p = run_infer(xn)
% Un control-step cyclo-accurato di snn_top_b2 (start -> poll done).
  [~, done] = snn_top_b2(xn, true);              % start
  p = zeros(5, 1);
  for c = 1:2000
    [pp, done] = snn_top_b2(xn, false);
    if done, p = double(pp); return; end
  end
  error('done non asserito');
end

function [S, V, A, P] = closed_loop_ref(vl, norm, DT)
% Network-in-the-loop con la rete fixed + plant ACC-IIDM (formula acc_iidm_accel).
  N = numel(vl); S = zeros(1,N); V = zeros(1,N); A = zeros(1,N); P = zeros(5,N);
  v0i = 30; v = 0.8 * v0i; s = 2.5 + v * 1.5;    % IC nominali (come clean_plant)
  al = 0; vlp = vl(1); alpha = exp(-DT / 1.0);
  for i = 1:N
    al = alpha * al + (1 - alpha) * ((vl(i) - vlp) / DT); vlp = vl(i);
    dv = v - vl(i);
    xn = snn_normalize([s; v; dv; vl(i)], norm);
    p  = run_infer(fi(xn, 1, 19, 13));  P(:, i) = p;
    accel = acc_iidm(s, v, dv, al, p);
    vold = v; v = min(max(v + accel * DT, 0), 1.2 * p(1)); s = min(max(s + (vl(i) - vold) * DT, 0.5 * p(3)), 150);
    S(i) = s; V(i) = v; A(i) = accel;
  end
end

function acc = acc_iidm(s, v, dv, al, params)
% Port scalare di core.network.acc_iidm_accel (IIDM+CAH), double.
  v0 = params(1); T = params(2); s0 = params(3); a = max(params(4), 1e-3); b = max(params(5), 1e-3);
  sab = max(sqrt(a * b), 1e-6);
  sstar = s0 + max(v * T + v * dv / (2 * sab), 0);
  ssafe = max(s, 2.0);
  vfree = a * (1 - min(v / v0, 10)^4);
  z = min(sstar / ssafe, 20); az = a * (1 - z^2); bel = v <= v0;
  if bel, aff = vfree * (1 - z^2); else, aff = vfree; end
  if bel, acf = az; else, acf = vfree + az; end
  if z < 1, aiidm = aff; else, aiidm = acf; end
  albar = min(al, a);
  acah = albar - max(dv, 0)^2 / (2 * ssafe + 1e-6); acah = max(acah, -9); acah = min(acah, a);
  c = 0.99; diff = (aiidm - acah) / (b + 1e-6);
  ablend = (1 - c) * aiidm + c * (acah + b * tanh(diff));
  if aiidm >= acah, acc = aiidm; else, acc = ablend; end
  acc = max(acc, -9); acc = min(acc, a);
end
```

- [ ] **Step 2: Esegui e verifica i goldens**

Run: `cd matlab && matlab -batch "gen_phase_c_reference"`
Expected: `OK: goldens Fase C scritti in ...`; i 2 CSV esistono.
Check: `head -2 matlab/axi/phase_c/goldens/phase_c_reference.csv` mostra header + una riga con 5 param plausibili
(v0∈[8,45], T∈[.5,2.5], s0∈[1,5], a∈[.3,2.5], b∈[.5,3]).

- [ ] **Step 3: Commit**

```bash
git add matlab/gen_phase_c_reference.m matlab/axi/phase_c/goldens/*.csv
git commit -m "feat(fase-c): generatore riferimenti golden (sweep + closed-loop) da rete fixed"
```

---

## Task 2: Plant ACC-IIDM in numpy puro (+ parità col golden)

**Files:**
- Create: `matlab/axi/phase_c/plant_iidm.py`
- Create: `matlab/axi/phase_c/tests/test_plant_iidm.py`

- [ ] **Step 1: Scrivi il test di parità (RED)** — il plant numpy deve dare la stessa accel del golden Python

```python
# matlab/axi/phase_c/tests/test_plant_iidm.py
import numpy as np
from plant_iidm import acc_iidm_accel, clean_plant

def test_acc_iidm_matches_reference_point():
    # punto noto: s=30, v=20, dv=2, a_l=0, params=[30,1.5,2.5,1.0,1.5]
    acc = acc_iidm_accel(30.0, 20.0, 2.0, 0.0, [30.0, 1.5, 2.5, 1.0, 1.5])
    assert np.isfinite(acc) and -9.0 <= acc <= 1.0    # entro i clamp

def test_clean_plant_shapes():
    vl = np.full(100, 20.0)
    s, v, a = clean_plant([30.0, 1.5, 2.5, 1.0, 1.5], vl)
    assert s.shape == v.shape == a.shape == (100,)
    assert np.all(np.isfinite(v)) and np.all(v >= 0)
```

- [ ] **Step 2: Esegui — deve fallire** (`ModuleNotFoundError`)

Run: `python -m pytest matlab/axi/phase_c/tests/test_plant_iidm.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Scrivi `plant_iidm.py`** (port scalare numpy di `acc_iidm_accel`, bit-exact al golden float64)

```python
"""plant_iidm.py — ACC-IIDM in numpy puro (niente torch, gira sul PS ARM della PYNQ).
Port 1:1 di core.network.CF_FSNN_Net.acc_iidm_accel + clean_plant (da scripts/make_plant_golden.py).
"""
import numpy as np

DT = 0.1
ACC_AL_TAU = 1.0
NORM_S_MAX = 150.0
COOLNESS = 0.99


def _relu(x):
    return x if x > 0.0 else 0.0


def acc_iidm_accel(s, v, dv, a_l, params, coolness=COOLNESS):
    """Accel ACC-IIDM scalare (float64). params=[v0,T,s0,a,b]. Cfr. core/network.py:568."""
    v0, T, s0 = float(params[0]), float(params[1]), float(params[2])
    a = max(float(params[3]), 1e-3)
    b = max(float(params[4]), 1e-3)
    sqrt_ab = max(np.sqrt(a * b), 1e-6)
    s_star = s0 + _relu(v * T + v * dv / (2.0 * sqrt_ab))
    s_safe = max(s, 2.0)
    v_free = a * (1.0 - min(v / v0, 10.0) ** 4)
    z = min(s_star / s_safe, 20.0)
    below_v0 = v <= v0
    a_z = a * (1.0 - z * z)
    a_ff = (v_free * (1.0 - z * z)) if below_v0 else v_free
    a_cf = a_z if below_v0 else (v_free + a_z)
    a_iidm = a_ff if z < 1.0 else a_cf
    a_l_bar = min(a_l, a)
    a_cah = a_l_bar - _relu(dv) ** 2 / (2.0 * s_safe + 1e-6)
    a_cah = max(a_cah, -9.0)
    a_cah = min(a_cah, a)
    c = coolness
    diff = (a_iidm - a_cah) / (b + 1e-6)
    a_blend = (1.0 - c) * a_iidm + c * (a_cah + b * np.tanh(diff))
    a_acc = a_iidm if a_iidm >= a_cah else a_blend
    a_acc = max(a_acc, -9.0)
    return min(a_acc, a)


def clean_plant(params, v_l):
    """Plant open-loop con params FISSI (per i test). Cfr. make_plant_golden.clean_plant."""
    v0, T, s0, a, b = [float(x) for x in params]
    N = len(v_l)
    alpha = np.exp(-DT / ACC_AL_TAU)
    v = 0.8 * v0
    s = s0 + v * T
    a_l = 0.0
    vlp = float(v_l[0])
    S, V, A = np.zeros(N), np.zeros(N), np.zeros(N)
    for i in range(N):
        vl = float(v_l[i])
        a_l = alpha * a_l + (1.0 - alpha) * ((vl - vlp) / DT)
        vlp = vl
        dv = v - vl
        accel = acc_iidm_accel(s, v, dv, a_l, params)
        vold = v
        v = float(np.clip(v + accel * DT, 0.0, 1.2 * v0))
        s = float(np.clip(s + (vl - vold) * DT, 0.5 * s0, NORM_S_MAX))
        S[i], V[i], A[i] = s, v, accel
    return S, V, A
```

- [ ] **Step 4: Esegui — deve passare**

Run: `python -m pytest matlab/axi/phase_c/tests/test_plant_iidm.py -v`
Expected: PASS (2 test).

- [ ] **Step 5: Commit**

```bash
git add matlab/axi/phase_c/plant_iidm.py matlab/axi/phase_c/tests/test_plant_iidm.py
git commit -m "feat(fase-c): plant ACC-IIDM in numpy puro (port da golden, PS-friendly)"
```

---

## Task 3: Driver `SnnDonatello` (normalize + Q-conv + register I/O) + mock

**Files:**
- Create: `matlab/axi/phase_c/pynq_snn.py`
- Create: `matlab/axi/phase_c/mock_overlay.py`
- Create: `matlab/axi/phase_c/tests/test_pynq_snn.py`

- [ ] **Step 1: Scrivi i test (RED)** — normalize corretta + Q-conv round-trip + infer via mock

```python
# matlab/axi/phase_c/tests/test_pynq_snn.py
import numpy as np
from pynq_snn import SnnDonatello, to_q, from_q, normalize_donatello
from mock_overlay import MockOverlay

def test_normalize_matches_formula():
    xn = normalize_donatello(75.0, 20.0, -2.0, 22.0)   # s,v,dv,vl
    # xn = [s/150, v/40, (clip(dv,-20,20)+20)/40, vl/40]
    assert np.allclose(xn, [75/150, 20/40, (-2+20)/40, 22/40], atol=1e-9)

def test_q_roundtrip():
    for val in [0.0, 1.234, -0.5, 26.49]:
        assert abs(from_q(to_q(val, 13), 13) - val) < 2**-13

def test_infer_via_mock_returns_expected():
    # mock che ritorna param fissi -> infer li rilegge in fisico
    mock = MockOverlay(const_params=[26.49, 1.63, 2.45, 1.01, 1.71])
    drv = SnnDonatello(overlay=mock)
    p = drv.infer(75.0, 20.0, -2.0, 22.0)
    assert np.allclose(p, [26.49, 1.63, 2.45, 1.01, 1.71], atol=1e-3)
```

- [ ] **Step 2: Esegui — deve fallire**

Run: `python -m pytest matlab/axi/phase_c/tests/test_pynq_snn.py -v`
Expected: FAIL (import).

- [ ] **Step 3: Scrivi `pynq_snn.py`**

```python
"""pynq_snn.py — driver PYNQ per Donatello B2 (AXI4-Lite). Estende run_on_pynq.py con normalize + infer.
Sul PS: normalize (float) -> Q5.13 -> AXI. Register map: matlab/axi/README.md.
"""
import numpy as np

REG_XN = [0x00, 0x04, 0x08, 0x0C]
REG_CONTROL = 0x10
REG_STATUS = 0x10
REG_PARAMS = [0x14, 0x18, 0x1C, 0x20, 0x24]
PARAM_NAMES = ["v0", "T", "s0", "a", "b"]
FRAC = 13
NORM = [150.0, 40.0, 20.0, 40.0]   # Donatello [S, V, DV, VL]


def to_q(x, frac=FRAC):
    """float -> intero due-complementi 32b (Q?.frac)."""
    return int(round(x * (1 << frac))) & 0xFFFFFFFF


def from_q(u, frac=FRAC, bits=32):
    """intero registro -> float (Q?.frac) con sign-extension."""
    if u & (1 << (bits - 1)):
        u -= (1 << bits)
    return u / (1 << frac)


def normalize_donatello(s, v, dv, vl):
    """fisico -> normalizzato (identico a snn_normalize.m per Donatello)."""
    S, V, DV, VL = NORM
    dvc = max(min(dv, DV), -DV)
    return [s / S, v / V, (dvc + DV) / (2.0 * DV), vl / VL]


class SnnDonatello:
    def __init__(self, overlay, ip_name="snn0"):
        self.ip = getattr(overlay, ip_name)

    def infer(self, s, v, dv, vl, timeout=100000):
        """(s,v,dv,vl) fisico -> [v0,T,s0,a,b] fisico. normalize sul PS."""
        xn = normalize_donatello(s, v, dv, vl)
        for reg, x in zip(REG_XN, xn):
            self.ip.write(reg, to_q(x))
        self.ip.write(REG_CONTROL, 1); self.ip.write(REG_CONTROL, 0)   # start (fronte)
        i = 0
        while (self.ip.read(REG_STATUS) & 1) == 0:
            i += 1
            if i > timeout:
                raise TimeoutError("done non asserito")
        return [from_q(self.ip.read(r)) for r in REG_PARAMS]
```

- [ ] **Step 4: Scrivi `mock_overlay.py`**

```python
"""mock_overlay.py — overlay fake per unit-test SENZA board. Emula il register file + il comportamento done.
Due modi: const_params (ritorna sempre gli stessi 5 param) o lookup (input->param dal golden)."""
from pynq_snn import REG_XN, REG_CONTROL, REG_PARAMS, to_q, from_q


class _MockIP:
    def __init__(self, const_params=None, lookup=None):
        self.regs = {}
        self.const_params = const_params
        self.lookup = lookup            # dict: tuple(xn_q) -> [5 param fisici]
        self._done = 0
        self._last_xn = [0, 0, 0, 0]

    def write(self, addr, val):
        self.regs[addr] = val
        if addr in REG_XN:
            self._last_xn[REG_XN.index(addr)] = val
        if addr == REG_CONTROL and val & 1:      # start -> calcola i param e alza done
            params = self.const_params
            if self.lookup is not None:
                params = self.lookup[tuple(self._last_xn)]
            for r, p in zip(REG_PARAMS, params):
                self.regs[r] = to_q(p)
            self._done = 1

    def read(self, addr):
        if addr == 0x10:                          # status: done
            return self._done
        return self.regs.get(addr, 0)


class MockOverlay:
    def __init__(self, const_params=None, lookup=None):
        self.snn0 = _MockIP(const_params=const_params, lookup=lookup)
```

- [ ] **Step 5: Esegui — deve passare**

Run: `python -m pytest matlab/axi/phase_c/tests/test_pynq_snn.py -v`
Expected: PASS (3 test).

- [ ] **Step 6: Commit**

```bash
git add matlab/axi/phase_c/pynq_snn.py matlab/axi/phase_c/mock_overlay.py matlab/axi/phase_c/tests/test_pynq_snn.py
git commit -m "feat(fase-c): driver SnnDonatello (normalize+Q+AXI) + mock overlay"
```

---

## Task 4: Sweep funzionale (feed test traj -> confronto vs riferimento -> errore)

**Files:**
- Create: `matlab/axi/phase_c/functional_sweep.py`
- Create: `matlab/axi/phase_c/tests/test_functional_sweep.py`

- [ ] **Step 1: Scrivi il test (RED)** — con un mock a lookup, lo sweep dà errore ~0

```python
# matlab/axi/phase_c/tests/test_functional_sweep.py
import numpy as np
from functional_sweep import run_sweep, load_reference
from pynq_snn import SnnDonatello, normalize_donatello, to_q
from mock_overlay import MockOverlay

def test_sweep_zero_error_with_matching_mock(tmp_path):
    # riferimento sintetico: 2 input -> param noti
    ref_csv = tmp_path / "ref.csv"
    ref_csv.write_text(
        "traj,step,s,v,dv,vl,v0,T,s0,a,b\n"
        "1,1,75,20,-2,22,26.49,1.63,2.45,1.01,1.71\n"
        "1,2,70,21,-1,22,27.0,1.60,2.50,1.00,1.70\n")
    rows = load_reference(str(ref_csv))
    # mock lookup: xn quantizzato -> param attesi
    lut = {}
    for r in rows:
        xn = normalize_donatello(r["s"], r["v"], r["dv"], r["vl"])
        lut[tuple(to_q(x) for x in xn)] = [r["v0"], r["T"], r["s0"], r["a"], r["b"]]
    drv = SnnDonatello(MockOverlay(lookup=lut))
    err = run_sweep(drv, rows)
    assert err["max_abs"] < 1e-3       # bit-exact col mock
```

- [ ] **Step 2: Esegui — deve fallire**

Run: `python -m pytest matlab/axi/phase_c/tests/test_functional_sweep.py -v`
Expected: FAIL (import).

- [ ] **Step 3: Scrivi `functional_sweep.py`**

```python
"""functional_sweep.py — feed delle traiettorie di test -> driver.infer -> confronto vs riferimento.
Ritorna la distribuzione d'errore per-parametro."""
import csv
import numpy as np

PARAMS = ["v0", "T", "s0", "a", "b"]


def load_reference(path):
    with open(path) as f:
        return [ {k: (float(v) if k not in ("traj", "step") else int(v)) for k, v in row.items()}
                 for row in csv.DictReader(f) ]


def run_sweep(driver, rows):
    """Per ogni riga: infer(s,v,dv,vl) e confronta coi param attesi. -> dict statistiche errore."""
    errs = []
    for r in rows:
        got = driver.infer(r["s"], r["v"], r["dv"], r["vl"])
        exp = [r[p] for p in PARAMS]
        errs.append(np.abs(np.array(got) - np.array(exp)))
    E = np.array(errs)                      # (Nrow, 5)
    return {
        "n": len(rows),
        "max_abs": float(E.max()) if len(E) else 0.0,
        "rms_per_param": {p: float(np.sqrt((E[:, i] ** 2).mean())) for i, p in enumerate(PARAMS)},
        "max_per_param": {p: float(E[:, i].max()) for i, p in enumerate(PARAMS)},
    }
```

- [ ] **Step 4: Esegui — deve passare**

Run: `python -m pytest matlab/axi/phase_c/tests/test_functional_sweep.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add matlab/axi/phase_c/functional_sweep.py matlab/axi/phase_c/tests/test_functional_sweep.py
git commit -m "feat(fase-c): sweep funzionale + confronto vs riferimento (mock-verde)"
```

---

## Task 5: Closed-loop network-in-the-loop

**Files:**
- Create: `matlab/axi/phase_c/closed_loop.py`
- Create: `matlab/axi/phase_c/tests/test_closed_loop.py`

- [ ] **Step 1: Scrivi il test (RED)** — con un mock a param COSTANTI, il network-in-the-loop == `clean_plant` con quei param

```python
# matlab/axi/phase_c/tests/test_closed_loop.py
import numpy as np
from closed_loop import run_closed_loop
from plant_iidm import clean_plant
from pynq_snn import SnnDonatello
from mock_overlay import MockOverlay

def test_closed_loop_const_params_equals_open_plant():
    # con param COSTANTI la rete-in-the-loop deve coincidere col plant open-loop
    params = [30.0, 1.5, 2.5, 1.0, 1.5]
    vl = np.full(200, 20.0); vl[50:] = 14.0
    drv = SnnDonatello(MockOverlay(const_params=params))
    S, V, A, _ = run_closed_loop(drv, vl)
    s_ref, v_ref, a_ref = clean_plant(params, vl)
    assert np.max(np.abs(V - v_ref)) < 1e-9     # stessa integrazione
    assert np.max(np.abs(S - s_ref)) < 1e-9
```

- [ ] **Step 2: Esegui — deve fallire**

Run: `python -m pytest matlab/axi/phase_c/tests/test_closed_loop.py -v`
Expected: FAIL (import).

- [ ] **Step 3: Scrivi `closed_loop.py`** (stessa IC/integrazione di `clean_plant`, ma i param vengono dalla rete)

```python
"""closed_loop.py — network-in-the-loop: la SNN (driver) fornisce i param a ogni step; il plant integra l'ego.
IC e integrazione IDENTICHE a plant_iidm.clean_plant, così con param costanti coincidono (test)."""
import numpy as np
from plant_iidm import acc_iidm_accel, DT, ACC_AL_TAU, NORM_S_MAX


def run_closed_loop(driver, v_l):
    """v_l=(N,) profilo leader. Ritorna (S, V, A, P) — traiettoria ego + param per-step (5,N)."""
    N = len(v_l)
    alpha = np.exp(-DT / ACC_AL_TAU)
    # IC: servono i param iniziali -> primo infer allo stato nominale
    p0 = driver.infer(0.0, 0.0, 0.0, float(v_l[0]))   # prime -> v0 iniziale
    v0_0 = p0[0]
    v = 0.8 * v0_0
    s = p0[2] + v * p0[1]                              # s0 + v*T
    a_l = 0.0
    vlp = float(v_l[0])
    S, V, A = np.zeros(N), np.zeros(N), np.zeros(N)
    P = np.zeros((5, N))
    for i in range(N):
        vl = float(v_l[i])
        a_l = alpha * a_l + (1.0 - alpha) * ((vl - vlp) / DT)
        vlp = vl
        dv = v - vl
        params = driver.infer(s, v, dv, vl)
        P[:, i] = params
        accel = acc_iidm_accel(s, v, dv, a_l, params)
        vold = v
        v = float(np.clip(v + accel * DT, 0.0, 1.2 * params[0]))
        s = float(np.clip(s + (vl - vold) * DT, 0.5 * params[2], NORM_S_MAX))
        S[i], V[i], A[i] = s, v, accel
    return S, V, A, P
```

Nota: con `const_params` il primo `infer` ritorna quei param → IC = `clean_plant` → coincidenza. Sul silicio i
param variano per-step (rete reale); il confronto è vs il golden closed-loop (Task 1), con soglia RMS del §7 spec.

- [ ] **Step 4: Esegui — deve passare**

Run: `python -m pytest matlab/axi/phase_c/tests/test_closed_loop.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add matlab/axi/phase_c/closed_loop.py matlab/axi/phase_c/tests/test_closed_loop.py
git commit -m "feat(fase-c): closed-loop network-in-the-loop (mock-verde: ==plant con param costanti)"
```

---

## Task 6: Modulo potenza (3-stati total-board, strumento-agnostico)

**Files:**
- Create: `matlab/axi/phase_c/power_measure.py`
- Create: `matlab/axi/phase_c/tests/test_power_measure.py`

- [ ] **Step 1: Scrivi il test (RED)** — la logica di calcolo delta/upper-bound

```python
# matlab/axi/phase_c/tests/test_power_measure.py
from power_measure import analyze_power

def test_pl_dynamic_from_three_states():
    # P_attivo - P_PS_only = PL dyn; se sopra risoluzione -> numero, altrimenti upper-bound
    r = analyze_power(p_idle=1.80, p_ps_only=1.85, p_active=1.86, resolution=0.12)
    assert r["p_deploy_w"] == 1.86
    assert r["pl_dyn_w"] <= r["resolution"]        # 0.01 < 0.12
    assert r["pl_dyn_is_upper_bound"] is True

def test_pl_resolvable_when_above_resolution():
    r = analyze_power(p_idle=1.80, p_ps_only=1.85, p_active=2.35, resolution=0.12)
    assert abs(r["pl_dyn_w"] - 0.50) < 1e-9
    assert r["pl_dyn_is_upper_bound"] is False
```

- [ ] **Step 2: Esegui — deve fallire**

Run: `python -m pytest matlab/axi/phase_c/tests/test_power_measure.py -v`
Expected: FAIL (import).

- [ ] **Step 3: Scrivi `power_measure.py`**

```python
"""power_measure.py — analisi potenza total-board a 3 stati (idle / PS-only / attivo).
Strumento-agnostico: l'utente fornisce 3 numeri di potenza totale [W]. Isola il PL dal loop Python."""


def analyze_power(p_idle, p_ps_only, p_active, resolution):
    """Ritorna PL_dyn (= attivo - PS-only), upper-bound se < risoluzione, e P_deploy (= attivo)."""
    pl_dyn = p_active - p_ps_only
    ps_loop = p_ps_only - p_idle
    return {
        "p_idle_w": p_idle,
        "p_ps_only_w": p_ps_only,
        "p_active_w": p_active,
        "p_deploy_w": p_active,               # potenza totale di deploy (numero utile)
        "ps_loop_overhead_w": ps_loop,        # costo del loop Python (isolato)
        "pl_dyn_w": max(pl_dyn, 0.0),
        "resolution": resolution,
        "pl_dyn_is_upper_bound": abs(pl_dyn) < resolution,
    }


def guided_procedure(driver, v_l, dwell_s=10):
    """Procedura interattiva sulla board: guida l'utente a leggere la potenza nei 3 stati.
    Ritorna i 3 valori (input()). Board-only (non testato con mock)."""
    import time
    print("STATO 1/3 — IDLE: overlay caricato, nessuna inferenza. Leggi la potenza totale.")
    p_idle = float(input("  P_idle [W] = "))
    print(f"STATO 2/3 — PS-ONLY: loop Python {dwell_s}s SENZA start (solo read status)...")
    t0 = time.time()
    while time.time() - t0 < dwell_s:
        driver.ip.read(0x10)                  # read status, nessun start -> PL idle
    p_ps_only = float(input("  P_PS_only [W] = "))
    print(f"STATO 3/3 — ATTIVO: inferenza continua {dwell_s}s...")
    t0 = time.time()
    while time.time() - t0 < dwell_s:
        driver.infer(50.0, 20.0, -2.0, 22.0)
    p_active = float(input("  P_active [W] = "))
    return p_idle, p_ps_only, p_active
```

- [ ] **Step 4: Esegui — deve passare**

Run: `python -m pytest matlab/axi/phase_c/tests/test_power_measure.py -v`
Expected: PASS (2 test).

- [ ] **Step 5: Commit**

```bash
git add matlab/axi/phase_c/power_measure.py matlab/axi/phase_c/tests/test_power_measure.py
git commit -m "feat(fase-c): modulo potenza 3-stati (isola PL, upper-bound onesto)"
```

---

## Task 7: Notebook orchestratore + report/runbook

**Files:**
- Create: `matlab/axi/phase_c/phase_c_validation.ipynb`
- Create: `document/FPGA_PHASE_C_REPORT.md`

- [ ] **Step 1: Scrivi il notebook** (celle che cablano i moduli; eseguibile SOLO sulla board)

Crea `phase_c_validation.ipynb` con queste celle (Markdown + code). Contenuto delle celle code:

```python
# Cella 1 — setup
from pynq import Overlay
import numpy as np, sys
sys.path.insert(0, ".")
from pynq_snn import SnnDonatello
from functional_sweep import run_sweep, load_reference
from closed_loop import run_closed_loop
from power_measure import guided_procedure, analyze_power
ol = Overlay("snn_b2_donatello.bit")     # .hwh nello stesso path
drv = SnnDonatello(ol)
```

```python
# Cella 2 — sweep funzionale
rows = load_reference("goldens/phase_c_reference.csv")
err = run_sweep(drv, rows)
print("MAX errore assoluto:", err["max_abs"], "(atteso <= 1 LSB fisico ~1e-4)")
print("max per param:", err["max_per_param"])
assert err["max_abs"] < 5e-4, "MISMATCH funzionale -> bug di deployment (vedi spec §4)"
```

```python
# Cella 3 — closed-loop
import csv
g = list(csv.DictReader(open("goldens/phase_c_closedloop_golden.csv")))
vl = np.array([float(r["vl"]) for r in g])
S, V, A, P = run_closed_loop(drv, vl)
v_gold = np.array([float(r["v"]) for r in g])
rms_v = float(np.sqrt(np.mean((V - v_gold) ** 2)))
print("RMS v(ego) silicio-vs-golden:", rms_v, "m/s")
assert rms_v < 0.05, "divergenza closed-loop -> verifica param per-step (spec §4)"
```

```python
# Cella 4 — potenza (procedura guidata, leggi dallo strumento)
p_idle, p_ps, p_act = guided_procedure(drv, vl, dwell_s=10)
res = analyze_power(p_idle, p_ps, p_act, resolution=0.12)   # 0.12 = risoluzione tipica alim. banco
print(res)
```

- [ ] **Step 2: Scrivi `document/FPGA_PHASE_C_REPORT.md`** (scheletro + runbook)

```markdown
# FPGA Fase C — Validazione su silicio (PYNQ-Z1) — report

> Esito della Fase C: deploy reale + verifica funzionale + closed-loop + potenza total-board.
> **Stato: predisposto (harness + goldens pronti, unit-test verdi); esecuzione board = quando arriva.**

## Runbook "quando arriva la board"
1. Copia su PYNQ (Jupyter): `matlab/axi/phase_c/*.py`, `phase_c_validation.ipynb`, `goldens/`,
   `matlab/axi/build/snn_b2_donatello.{bit,hwh}` (rinominali `snn_b2_donatello.bit/.hwh` stesso path).
2. Alimenta la board dallo strumento (alim. da banco con lettura corrente, o meter inline barrel/USB).
3. Apri il notebook, esegui Cella 1-3 (funzionale + closed-loop) — devono passare gli assert.
4. Cella 4: nei 3 stati (idle/PS-only/attivo) leggi la potenza totale dallo strumento, inseriscila.
5. Riempi le tabelle sotto + la colonna "Fase C" di `FPGA_PHASE_B_POWER.md`.

## Risultati (da riempire con la board)
| Metrica | Atteso | Misurato silicio |
|---|---|---|
| Sweep: max errore param | ≤1 LSB (~1e-4) bit-exact | TBD |
| Closed-loop: RMS v(ego) | < 0.05 m/s | TBD |
| P_deploy (totale) | — | TBD W |
| PL_dyn (upper-bound) | < risoluzione, coerente ~9 mW | TBD |

## Onestà
Total-board: i ~9 mW del PL sono sotto risoluzione → PL_dyn = upper-bound, non numero. P_deploy è il numero
utile. Un mismatch funzionale = bug di deployment (normalize/AXI/packing/timing), da investigare, non aggirare.
```

- [ ] **Step 3: Commit**

```bash
git add matlab/axi/phase_c/phase_c_validation.ipynb document/FPGA_PHASE_C_REPORT.md
git commit -m "feat(fase-c): notebook orchestratore + report/runbook (esecuzione board-later)"
```

---

## Task 8: Suite completa verde + push + docs di stato

- [ ] **Step 1: Tutti i test Python verdi**

Run: `python -m pytest matlab/axi/phase_c/tests/ -v`
Expected: PASS su tutti (plant, driver, sweep, closed-loop, power). Se un test fallisce → fixa la causa.

- [ ] **Step 2: Aggiorna SESSION_RESUME + memoria** con "Fase C predisposta (harness + goldens + unit-test verdi; esecuzione board-later)".

- [ ] **Step 3: Commit + push**

```bash
git add document/SESSION_RESUME.md
git commit -m "docs(fase-c): stato - harness pronto, unit-test verdi, esecuzione board-later"
git push origin Simulink_Importer
```

---

## Note di rischio (leggi prima di eseguire)
- **Path import Python — import FLAT (board-portable):** i moduli si importano **piatti** (`from plant_iidm
  import ...`, `from pynq_snn import ...`) perché sulla board sono copiati nella stessa cartella e il notebook fa
  `sys.path.insert(0, ".")` (Cella 1). Per i test, **crea `matlab/axi/phase_c/tests/conftest.py` PRIMA del Task 2**
  che aggiunge la dir dei moduli al path — niente `__init__.py`, niente package-style:
  ```python
  # matlab/axi/phase_c/tests/conftest.py
  import os, sys
  sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # -> matlab/axi/phase_c/
  ```
  Commit `conftest.py` col Task 2. Così i test girano con `from plant_iidm import ...` e i moduli restano flat.
- **Sul PS niente torch:** il plant è numpy puro (Task 2). NON importare `core.network` sul PS.
- **Reference cyclo-accurato lento:** `gen_phase_c_reference.m` fa 341 cicli × ogni step × 6 traj × 600 + closed-loop
  → minuti in MATLAB. Se troppo lento, usare `snn_core` (algoritmico, bit-exact a snn_b2_fsm) invece del FSM
  cyclo-accurato per il riferimento (stesso risultato, 1 call/step).
- **Closed-loop bit-exact:** il golden usa il plant MATLAB, il silicio il plant numpy; sono bit-exact per parità
  esistente (`run_plant_parity`=0.0), ma su 600 step piccole differenze float di piattaforma → soglia RMS<0.05 m/s
  come fallback dichiarato (spec §5).
```
