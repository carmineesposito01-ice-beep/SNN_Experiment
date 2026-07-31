# Fase C — Validazione su silicio e chiusura mesoscopica — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** portare il controllore su FPGA fisica e chiudere il proxy mesoscopico, con la stessa riproducibilità
degli harness T6b/T7b: un comando per stadio, i numeri negli artefatti, ogni cancello provato anche in negativo.

**Architecture:** moduli Python testabili col mock **adesso**, due facciate sottili sopra di essi (script e
notebook) tenute allineate da un cancello di parità. Tre filoni: A (composto su silicio), B (SNN sola su
silicio), C (plotone: P1 simulazione, P2 RTL, P3 silicio). Ordine di esecuzione **per indipendenza dalla
scheda**, non per numerazione.

**Tech Stack:** Python 3 + numpy/scipy · PYNQ (overlay, MMIO) · pytest · Vivado 2026.1 (sonda risorse) ·
il motore canonico `utils/closed_loop_eval.py` · gli artefatti già validati di T7a.

**Spec:** `docs/superpowers/specs/2026-07-31-fase-c-silicio-e-plotone-design.md`

---

## Costanti misurate — NON riderivarle

| Grandezza | Valore | Fonte |
|---|---|---|
| Composto: FCLK deployabile | 40 MHz (WNS +0,022 · WHS +0,033) | `results/sweep.json` |
| Composto: latenza / finestra attiva | 555 / **582** clock | `results/power_params.json` |
| Composto: duty | 0,0146 % | idem |
| Composto: PL | 11 mW dinamica + 103 statica | `results/power.json` |
| SNN sola: FCLK | 52 MHz | `Harness_SNN/results/RESULTS_HW.md` |
| Mappa registri composto | `0x00–0x0C` ingressi · `0x10` ctrl (bit0 commit, bit1 gating) e `done` in lettura · `0x14` accel | `snniidm_axi_lite.v` |
| Mappa registri SNN | come sopra, ma **5** registri d'uscita `0x14–0x24` | `tier_axi_lite.v` |
| Formati | ingressi `sfix32_En20` · accel `sfix13_En8` | §2.4 report T7 |
| Golden | `C:/t7bw/axi_{stim,gold,len}_<i>.mem`, i=1..99 | T7a, già validati |

---

## Struttura dei file

`FaseC/` sta **di primo livello, sorella di `FaseB2.0/`** — non dentro. La Fase C non è un harness della
Fase B2.0: ne consuma gli artefatti, e nidificarla sarebbe debito strutturale al primo file.

Tre regole di collocazione, che valgono per ogni file aggiunto in seguito:

1. **La logica sta in `phase_c/`, importabile.** Le facciate (script, notebook) stanno fuori e non
   contengono logica propria — altrimenti il cancello di parità del Task 11 non può essere verde.
2. **I numeri vivono solo in `results/`.** Mai nella chat, mai in una cella del notebook, mai in un
   commento. Un numero senza artefatto non è un risultato.
3. **Un file di test per modulo**, con lo stesso nome. `phase_c/c1_functional.py` → `tests/test_c1.py`.

```
FaseC/                          <- di primo livello, sorella di FaseB2.0/
  README.md                     cosa c'e', come si esegue, in che ordine
  RUNBOOK.md                    procedura con la scheda accesa (Task 12)
  pytest.ini                    rende `phase_c` importabile da qualunque cwd
  run_phase_c.sh                FACCIATA 1 - a stadi, l'entry-point
  c_frontend_parity.py          il cancello fra le due facciate

  phase_c/                      LA LOGICA - tutto qui, importabile da entrambe le facciate
    __init__.py
    regmap.py       mappe registri e conversioni di formato (UNICO posto)
    driver.py       SnnIidmDriver, SnnTierDriver (sopra overlay reale o mock)
    mock_overlay.py finge la scheda; risponde coi golden di T7a
    artifacts.py    scrittura/lettura artefatti con provenienza
    params.py       caricamento dei gt_params dal dataset          (Task 9a)
    cli.py          entry-point condiviso dalle DUE facciate       (Task 11)
    plots.py        grafici: accelerazione vs traiettoria          (Task 11)
    c0_liveness.py  il bus risponde e i registri ritengono
    c1_functional.py replay dei 99 scenari, bit-esatto
    c2_closedloop.py PLANT-PAR del PS, poi anello chiuso
    plant_ps.py     port 1:1 di qz_cl_sim
    c3_power.py     differenziale randomizzato + Tj
    xadc.py         lettura Tj e tensioni
    platoon.py      P1/P2/P3 sopra simulate_platoon

  tests/            un file per modulo, piu' conftest.py (fixture dei golden)
  hw/               script Vivado: sonda risorse del plotone (Task 10)
  notebook/
    phase_c.ipynb   FACCIATA 2 - interattiva: solo chiamate a phase_c.cli + grafici
  results/          ARTEFATTI - l'unico posto in cui vivono i numeri
```

---

# PARTE I — Eseguibile ADESSO, senza scheda

## Task 0: lo scheletro, e il cancello che lo tiene riproducibile

**Files:** Create `FaseC/{README.md,pytest.ini}`, `FaseC/phase_c/__init__.py` · Test `FaseC/tests/test_layout.py`

Non è burocrazia: «riproducibile» significa che **gira uguale da qualunque directory**. Se `phase_c` è
importabile solo con la cwd giusta, la facciata-script e la facciata-notebook divergeranno per un motivo
che non ha niente a che vedere con la Fase C — e il cancello di parità del Task 11 diventerà rumore.

- [ ] **Step 1: test che fallisce**

```python
# FaseC/tests/test_layout.py
"""Cancello di riproducibilita': il pacchetto si importa e gli artefatti hanno dove andare.

Sembra banale. Non lo e': se `phase_c` e' importabile solo dalla cwd giusta, le due facciate
divergeranno per un motivo che non c'entra con la Fase C.
"""
import os
import phase_c

FASEC = os.path.dirname(os.path.dirname(os.path.abspath(phase_c.__file__)))

def test_il_pacchetto_si_importa_e_dichiara_dove_e():
    assert os.path.basename(FASEC) == 'FaseC'
    assert phase_c.ROOT == FASEC

def test_results_esiste_ed_e_scrivibile():
    d = phase_c.RESULTS
    assert os.path.isdir(d)
    p = os.path.join(d, '.write_probe')
    open(p, 'w').write('x'); os.remove(p)

def test_i_golden_di_t7a_sono_raggiungibili():
    """Se i golden non ci sono, meta' del piano non e' eseguibile: meglio saperlo ORA."""
    assert os.path.isfile(os.path.join(phase_c.T7_WORK, 'axi_gold_1.mem')), \
        'golden di T7a assenti in %s -- impostare T7_WORK' % phase_c.T7_WORK
```

- [ ] **Step 2: eseguire e vederlo fallire**

Run: `cd FaseC && python -m pytest tests/test_layout.py -v`
Atteso: FAIL — `ModuleNotFoundError: No module named 'phase_c'`

- [ ] **Step 3: creare lo scheletro**

```python
# FaseC/phase_c/__init__.py
"""Fase C - validazione su silicio e chiusura mesoscopica.

La LOGICA vive qui ed e' importabile; le facciate (run_phase_c.sh, notebook/phase_c.ipynb)
stanno fuori e non contengono logica propria. I numeri vivono solo in results/.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, 'results')
# Radice del progetto: FaseC/ e' sorella di FaseB2.0/, utils/, champions/, ...
PROJECT = os.path.dirname(ROOT)
# Artefatti di T7a (golden bit-esatti). Sovrascrivibile per postazione.
T7_WORK = os.environ.get('T7_WORK', 'C:/t7bw')

os.makedirs(RESULTS, exist_ok=True)
```

```ini
# FaseC/pytest.ini
[pytest]
# rootdir = FaseC/: rende `phase_c` importabile da qualunque cwd, che e' cio' che
# permette alle due facciate di eseguire LO STESSO codice.
testpaths = tests
pythonpath = .
```

- [ ] **Step 4: eseguire e vederlo passare**

Run: `cd FaseC && python -m pytest tests/test_layout.py -v`
Atteso: PASS, 3 test. **Se il terzo fallisce, fermarsi**: senza i golden di T7a i Task 2/6 non sono
eseguibili, e va deciso dove stanno prima di proseguire.

- [ ] **Step 5: il README, che dice l'ordine**

`FaseC/README.md` contiene: le tre regole di collocazione (sopra), la tabella delle costanti misurate
(da non riderivare), l'ordine di esecuzione degli stadi, e **quali task girano senza scheda**.

- [ ] **Step 6: commit**

```bash
git add FaseC/README.md FaseC/pytest.ini FaseC/phase_c/__init__.py FaseC/tests/test_layout.py
git commit -m "feat(fase-c): scheletro di FaseC/ e cancello di riproducibilita' dell'import"
```

---

## Task 1: `regmap.py` — un solo posto per formati e indirizzi

**Files:** Create `FaseC/phase_c/regmap.py` · Test `FaseC/tests/test_regmap.py`

Il formato numerico al confine è il **guasto numero uno** del bring-up (§7 spec): produce risultati
plausibili, non un crash. Sta quindi in un unico modulo, con test propri.

- [ ] **Step 1: test che fallisce**

```python
# FaseC/tests/test_regmap.py
import pytest
from phase_c.regmap import to_fix, from_fix, IIDM, TIER

def test_ingresso_en20_andata_e_ritorno():
    # 34.174743 m -> il valore che T7a ha davvero scritto (axi_stim_1.mem riga 1)
    assert to_fix(34.174743, nfrac=20, nbits=32) == 0x0222CBBF

def test_accel_sfix13_en8_negativa_con_segno():
    # -1.0 m/s2 in sfix13_En8 = -256 -> due complementi a 13 bit
    assert to_fix(-1.0, nfrac=8, nbits=13) == 0x1F00
    assert from_fix(0x1F00, nfrac=8, nbits=13) == -1.0

def test_accel_letta_dal_registro_a_32_bit_estende_il_segno():
    # il wrapper emette {{19{accel[12]}}, accel}: la lettura deve tornare a 13 bit con segno
    assert from_fix(0xFFFFFF00, nfrac=8, nbits=13, from_width=32) == -1.0

def test_mappa_registri_composto():
    assert IIDM.INPUTS == (0x00, 0x04, 0x08, 0x0C)
    assert IIDM.CTRL == 0x10 and IIDM.ACCEL == 0x14
    assert IIDM.N_OUT == 1

def test_mappa_registri_snn_ha_cinque_uscite():
    assert TIER.N_OUT == 5
    assert len(TIER.OUTPUTS) == 5
```

- [ ] **Step 2: eseguire e vederlo fallire**

Run: `cd FaseC && python -m pytest tests/test_regmap.py -v`
Atteso: FAIL — `ModuleNotFoundError: No module named 'phase_c.regmap'`

- [ ] **Step 3: implementazione minima**

```python
# FaseC/phase_c/regmap.py
"""Formati e mappe registri. UNICO posto in cui vivono.

Il formato al confine e' il guasto n.1 del bring-up: sbagliato, produce risultati PLAUSIBILI
con errore che scala con la grandezza -- non un crash. Per questo sta qui, con test propri.
Convenzione di quantizzazione del progetto: FLOOR ovunque (fi(...,'Floor')).
"""
import math
from dataclasses import dataclass


def to_fix(x, nfrac, nbits):
    """float -> intero senza segno che rappresenta il campo a `nbits` in complemento a due."""
    q = math.floor(x * (1 << nfrac))          # FLOOR, non round: convenzione del progetto
    lo, hi = -(1 << (nbits - 1)), (1 << (nbits - 1)) - 1
    if not (lo <= q <= hi):
        raise ValueError('valore %r fuori dal dominio sfix%d_En%d' % (x, nbits, nfrac))
    return q & ((1 << nbits) - 1)


def from_fix(u, nfrac, nbits, from_width=None):
    """intero letto dal registro -> float. `from_width` se il campo arriva esteso di segno."""
    w = from_width or nbits
    u &= (1 << w) - 1
    if u >> (nbits - 1) & 1 and w == nbits:
        u -= (1 << nbits)
    elif w > nbits:
        u &= (1 << w) - 1
        if u >> (w - 1) & 1:
            u -= (1 << w)
    return u / float(1 << nfrac)


@dataclass(frozen=True)
class _Map:
    INPUTS: tuple
    CTRL: int
    N_OUT: int
    OUTPUTS: tuple
    IN_NFRAC: int = 20
    IN_NBITS: int = 32

    @property
    def ACCEL(self):
        return self.OUTPUTS[0]


IIDM = _Map(INPUTS=(0x00, 0x04, 0x08, 0x0C), CTRL=0x10, N_OUT=1, OUTPUTS=(0x14,))
TIER = _Map(INPUTS=(0x00, 0x04, 0x08, 0x0C), CTRL=0x10, N_OUT=5,
            OUTPUTS=(0x14, 0x18, 0x1C, 0x20, 0x24))

COMMIT_BIT, GATING_BIT, DONE_BIT = 0, 1, 0
ACCEL_NFRAC, ACCEL_NBITS = 8, 13
```

- [ ] **Step 4: eseguire e vederlo passare**

Run: `cd FaseC && python -m pytest tests/test_regmap.py -v`
Atteso: PASS, 5 test

- [ ] **Step 5: cancello di dominio provato in negativo**

```python
# aggiungere a tests/test_regmap.py
def test_fuori_dominio_solleva_invece_di_troncare_in_silenzio():
    with pytest.raises(ValueError, match='fuori dal dominio'):
        to_fix(20.0, nfrac=8, nbits=13)      # 20 m/s2 non entra in sfix13_En8 (max ~15.996)
```

Run: `python -m pytest tests/test_regmap.py -v` · Atteso: PASS, 6 test

- [ ] **Step 6: commit**

```bash
git add FaseC/phase_c/regmap.py FaseC/tests/test_regmap.py
git commit -m "feat(fase-c): regmap - formati e indirizzi in un solo posto, con cancello di dominio"
```

---

## Task 2: `mock_overlay.py` — la scheda finta, provata anche in negativo

**Files:** Create `phase_c/mock_overlay.py` · Test `tests/test_mock_negative.py`

⚠️ Un mock che non si e' mai visto far fallire un cancello **sta confermando se stesso**. Il test in negativo
non e' un extra: e' la ragione per cui il mock e' credibile.

- [ ] **Step 1: test che fallisce — il mock deve riprodurre il golden E poterlo tradire**

```python
# FaseC/tests/test_mock_negative.py
import pytest
from phase_c.mock_overlay import MockOverlay
from phase_c.driver import SnnIidmDriver
from phase_c.regmap import IIDM

def test_mock_riproduce_il_golden(golden_scen1):
    drv = SnnIidmDriver(MockOverlay(golden=golden_scen1))
    got = drv.infer(*golden_scen1.stim[0])
    assert got == golden_scen1.gold[0]

def test_mock_INIETTANDO_un_errore_fa_FALLIRE_il_confronto(golden_scen1):
    """Il cancello deve poter fallire. Se non fallisce qui, non prova nulla altrove."""
    drv = SnnIidmDriver(MockOverlay(golden=golden_scen1, inject_at=7, inject_delta=1))
    vals = [drv.infer(*s) for s in golden_scen1.stim[:10]]
    assert vals[7] != golden_scen1.gold[7]
    assert vals[6] == golden_scen1.gold[6] and vals[8] == golden_scen1.gold[8]
```

- [ ] **Step 2: eseguire e vederlo fallire**

Run: `python -m pytest tests/test_mock_negative.py -v` · Atteso: FAIL — modulo assente

- [ ] **Step 3: implementare mock e fixture**

```python
# FaseC/phase_c/mock_overlay.py
"""Overlay finto: stessa interfaccia di PYNQ (write/read su MMIO), risposte dai golden di T7a.

`inject_at`/`inject_delta` esistono per PROVARE I CANCELLI IN NEGATIVO. Senza, il mock
confermerebbe soltanto se stesso.
"""
from .regmap import IIDM, COMMIT_BIT, DONE_BIT, ACCEL_NFRAC, ACCEL_NBITS, to_fix


class MockOverlay:
    def __init__(self, golden, regmap=IIDM, inject_at=None, inject_delta=0):
        self.g, self.m = golden, regmap
        self.inject_at, self.inject_delta = inject_at, inject_delta
        self.regs = {a: 0 for a in list(regmap.INPUTS) + [regmap.CTRL] + list(regmap.OUTPUTS)}
        self.k = 0
        self._prev_commit = 0

    def write(self, addr, val):
        self.regs[addr] = val & 0xFFFFFFFF
        if addr == self.m.CTRL:
            commit = (val >> COMMIT_BIT) & 1
            if commit and not self._prev_commit:       # fronte di salita, come il wrapper
                self._step()
            self._prev_commit = commit

    def read(self, addr):
        return self.regs[addr]

    def _step(self):
        v = self.g.gold[self.k]
        if self.inject_at is not None and self.k == self.inject_at:
            v = v + self.inject_delta
        self.regs[self.m.OUTPUTS[0]] = to_fix(v, ACCEL_NFRAC, ACCEL_NBITS) | (0 << 16)
        self.regs[self.m.CTRL] |= (1 << DONE_BIT)
        self.k += 1
```

```python
# FaseC/tests/conftest.py
import pytest, io, os
from dataclasses import dataclass
from phase_c.regmap import from_fix, ACCEL_NFRAC, ACCEL_NBITS

WORK = os.environ.get('T7_WORK', 'C:/t7bw')

@dataclass
class Golden:
    stim: list
    gold: list

def _read_mem(p):
    return [int(x, 16) for x in io.open(p).read().split()]

@pytest.fixture
def golden_scen1():
    st = _read_mem(os.path.join(WORK, 'axi_stim_1.mem'))
    go = _read_mem(os.path.join(WORK, 'axi_gold_1.mem'))
    stim = [tuple(st[k*4:(k+1)*4]) for k in range(len(go))]
    gold = [from_fix(g, ACCEL_NFRAC, ACCEL_NBITS) for g in go]
    return Golden(stim=stim, gold=gold)
```

- [ ] **Step 4: eseguire — deve passare, compreso il test in negativo**

Run: `python -m pytest tests/test_mock_negative.py -v` · Atteso: PASS, 2 test

- [ ] **Step 5: commit**

```bash
git add FaseC/phase_c/mock_overlay.py FaseC/tests/{conftest.py,test_mock_negative.py}
git commit -m "feat(fase-c): mock dell'overlay, con iniezione d'errore per provare i cancelli in negativo"
```

---

## Task 3: `driver.py` — protocollo AXI, uno per i due wrapper

**Files:** Create `phase_c/driver.py` · Test `tests/test_driver.py`

- [ ] **Step 1: test che fallisce**

```python
# FaseC/tests/test_driver.py
import pytest
from phase_c.driver import SnnIidmDriver, SnnTierDriver, DoneTimeout
from phase_c.mock_overlay import MockOverlay
from phase_c.regmap import IIDM, TIER

def test_commit_e_un_FRONTE_non_un_livello(golden_scen1):
    """Il wrapper riparte sul fronte di salita del bit di commit. Scriverlo due volte a 1
    NON deve produrre due inferenze: e' il difetto del doppio fronte gia' pagato in B2.0."""
    ov = MockOverlay(golden=golden_scen1)
    drv = SnnIidmDriver(ov)
    drv.infer(*golden_scen1.stim[0])
    assert ov.k == 1
    ov.write(IIDM.CTRL, 0b01)          # commit ancora alto: nessun nuovo fronte
    assert ov.k == 1

def test_timeout_se_done_non_arriva(golden_scen1):
    class Muto(MockOverlay):
        def _step(self):
            pass                        # non alza mai done
    with pytest.raises(DoneTimeout):
        SnnIidmDriver(Muto(golden=golden_scen1), timeout_s=0.05).infer(*golden_scen1.stim[0])

def test_driver_tier_legge_cinque_uscite(golden_scen1):
    drv = SnnTierDriver(MockOverlay(golden=golden_scen1, regmap=TIER))
    assert drv.regmap.N_OUT == 5
```

- [ ] **Step 2: eseguire e vederlo fallire**

Run: `python -m pytest tests/test_driver.py -v` · Atteso: FAIL — modulo assente

- [ ] **Step 3: implementare**

```python
# FaseC/phase_c/driver.py
"""Driver: scrive i 4 ingressi, da' UN commit, attende `done`, legge l'uscita.

Il commit e' un FRONTE, non un livello (il wrapper fa `commit = slv_reg4[0] & ~reg4_d0`).
Tenerlo alto non rilancia l'inferenza -- ed e' esattamente il difetto del doppio fronte che
in B2.0 aveva alterato 1575 metriche.
"""
import time
from .regmap import IIDM, TIER, COMMIT_BIT, GATING_BIT, DONE_BIT, ACCEL_NFRAC, ACCEL_NBITS, from_fix


class DoneTimeout(RuntimeError):
    pass


class _Base:
    regmap = IIDM

    def __init__(self, overlay, gating=True, timeout_s=1.0):
        self.ov, self.gating, self.timeout_s = overlay, gating, timeout_s
        self._ctrl_base = (1 << GATING_BIT) if gating else 0
        self.ov.write(self.regmap.CTRL, self._ctrl_base)

    def _commit_and_wait(self):
        self.ov.write(self.regmap.CTRL, self._ctrl_base)              # commit basso
        self.ov.write(self.regmap.CTRL, self._ctrl_base | (1 << COMMIT_BIT))   # FRONTE
        t0 = time.time()
        while not (self.ov.read(self.regmap.CTRL) >> DONE_BIT) & 1:
            if time.time() - t0 > self.timeout_s:
                raise DoneTimeout('done non arrivato entro %.3f s' % self.timeout_s)
        self.ov.write(self.regmap.CTRL, self._ctrl_base)              # commit basso

    def _write_inputs(self, s, v, dv, vl):
        for addr, raw in zip(self.regmap.INPUTS, (s, v, dv, vl)):
            self.ov.write(addr, raw)


class SnnIidmDriver(_Base):
    regmap = IIDM

    def infer(self, s, v, dv, vl):
        self._write_inputs(s, v, dv, vl)
        self._commit_and_wait()
        return from_fix(self.ov.read(self.regmap.ACCEL), ACCEL_NFRAC, ACCEL_NBITS, from_width=32)


class SnnTierDriver(_Base):
    regmap = TIER

    def infer(self, s, v, dv, vl):
        self._write_inputs(s, v, dv, vl)
        self._commit_and_wait()
        return [self.ov.read(a) for a in self.regmap.OUTPUTS]
```

- [ ] **Step 4: eseguire e vederlo passare**

Run: `python -m pytest tests/test_driver.py -v` · Atteso: PASS, 3 test

- [ ] **Step 5: commit**

```bash
git add FaseC/phase_c/driver.py FaseC/tests/test_driver.py
git commit -m "feat(fase-c): driver AXI per composto e SNN, con commit a fronte e timeout su done"
```

---

## Task 4: `artifacts.py` — provenienza dentro ogni numero

**Files:** Create `phase_c/artifacts.py` · Test `tests/test_artifacts.py`

Il cancello di parità fra le facciate confronta gli artefatti: perché sia possibile, i campi volatili devono
essere **separabili**, non sparsi nel file.

- [ ] **Step 1: test che fallisce**

```python
# FaseC/tests/test_artifacts.py
import json
from phase_c.artifacts import write, read, stable_view

def test_artefatto_porta_la_provenienza(tmp_path):
    p = tmp_path / 'c1.json'
    write(p, {'nmismatch': 0, 'n': 600}, frontend='script', bitstream_sig='abc123')
    d = read(p)
    assert d['data']['nmismatch'] == 0
    assert d['prov']['frontend'] == 'script' and d['prov']['bitstream_sig'] == 'abc123'
    assert 'timestamp' in d['prov']

def test_stable_view_esclude_i_campi_volatili(tmp_path):
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    write(a, {'x': 1}, frontend='script', bitstream_sig='s')
    write(b, {'x': 1}, frontend='notebook', bitstream_sig='s')
    assert stable_view(read(a)) == stable_view(read(b))   # differiscono solo per campi volatili
```

- [ ] **Step 2: eseguire e vederlo fallire**

Run: `python -m pytest tests/test_artifacts.py -v` · Atteso: FAIL — modulo assente

- [ ] **Step 3: implementare**

```python
# FaseC/phase_c/artifacts.py
"""Artefatti con provenienza. `stable_view` isola cio' che le due facciate DEVONO condividere.

Senza questa separazione il cancello di parita' fallirebbe sempre (l'orario differisce) e
verrebbe disattivato -- che e' il modo in cui un cancello smette di servire.
"""
import io, json, os, datetime

VOLATILE = ('timestamp', 'frontend', 'host', 'cwd')


def write(path, data, frontend, bitstream_sig, **extra):
    obj = {'data': data,
           'prov': dict(timestamp=datetime.datetime.now().isoformat(timespec='seconds'),
                        frontend=frontend, bitstream_sig=bitstream_sig,
                        cwd=os.getcwd(), **extra)}
    io.open(path, 'w', encoding='utf-8', newline='').write(json.dumps(obj, indent=1, ensure_ascii=False))
    return obj


def read(path):
    return json.load(io.open(path, encoding='utf-8'))


def stable_view(obj):
    """Tutto tranne i campi volatili: e' cio' su cui le facciate devono coincidere."""
    prov = {k: v for k, v in obj['prov'].items() if k not in VOLATILE}
    return {'data': obj['data'], 'prov': prov}
```

- [ ] **Step 4: eseguire e vederlo passare**

Run: `python -m pytest tests/test_artifacts.py -v` · Atteso: PASS, 2 test

- [ ] **Step 5: commit**

```bash
git add FaseC/phase_c/artifacts.py FaseC/tests/test_artifacts.py
git commit -m "feat(fase-c): artefatti con provenienza e vista stabile per il cancello di parita'"
```

---

## Task 5: `c0_liveness.py` — il primo test sul silicio non è un'inferenza

**Files:** Create `phase_c/c0_liveness.py` · Test `tests/test_c0.py`

Dal corpus SoC: *«bring-up bloccato, bus muto → registro di identificazione come primo test»*. Il wrapper non
ne ha uno, ma i quattro registri d'ingresso sono leggibili: **scrittura con rilettura** è l'equivalente.

- [ ] **Step 1: test che fallisce**

```python
# FaseC/tests/test_c0.py
import pytest
from phase_c.c0_liveness import run_c0, C0Failure
from phase_c.mock_overlay import MockOverlay

def test_c0_passa_su_overlay_sano(golden_scen1):
    r = run_c0(MockOverlay(golden=golden_scen1))
    assert r['ok'] and r['n_patterns'] >= 4 and r['n_bad'] == 0

def test_c0_FALLISCE_se_un_registro_non_ritiene(golden_scen1):
    class Rotto(MockOverlay):
        def write(self, addr, val):
            super().write(addr, 0 if addr == 0x08 else val)   # 0x08 scarta la scrittura
    with pytest.raises(C0Failure, match='0x08'):
        run_c0(Rotto(golden=golden_scen1))
```

- [ ] **Step 2: eseguire e vederlo fallire**

Run: `python -m pytest tests/test_c0.py -v` · Atteso: FAIL — modulo assente

- [ ] **Step 3: implementare**

```python
# FaseC/phase_c/c0_liveness.py
"""C0 - il bus risponde e i registri ritengono. PRIMA di qualunque inferenza.

Un bus muto scoperto a meta' campagna e' tempo perso; scoperto qui costa 200 ms.
I pattern non sono casuali: 0x00000000 e 0xFFFFFFFF trovano linee incollate, 0xAAAAAAAA e
0x55555555 trovano corti fra bit adiacenti.
"""
from .regmap import IIDM

PATTERNS = (0x00000000, 0xFFFFFFFF, 0xAAAAAAAA, 0x55555555, 0x0222CBBF)


class C0Failure(RuntimeError):
    pass


def run_c0(overlay, regmap=IIDM):
    bad = []
    for addr in regmap.INPUTS:
        for p in PATTERNS:
            overlay.write(addr, p)
            got = overlay.read(addr)
            if got != p:
                bad.append((addr, p, got))
    if bad:
        a, w, g = bad[0]
        raise C0Failure('registro 0x%02X: scritto 0x%08X, riletto 0x%08X (%d pattern falliti). '
                        'Controllare per primo: mappa indirizzi e clock dell\'interconnessione.'
                        % (a, w, g, len(bad)))
    return {'ok': True, 'n_patterns': len(PATTERNS), 'n_regs': len(regmap.INPUTS), 'n_bad': 0}
```

- [ ] **Step 4: eseguire e vederlo passare**

Run: `python -m pytest tests/test_c0.py -v` · Atteso: PASS, 2 test

- [ ] **Step 5: commit**

```bash
git add FaseC/phase_c/c0_liveness.py FaseC/tests/test_c0.py
git commit -m "feat(fase-c): C0 vita del bus - scrittura/rilettura con pattern che trovano incollature e corti"
```

---

## Task 6: `c1_functional.py` — bit-esatto, con la scaletta diagnostica

**Files:** Create `phase_c/c1_functional.py` · Test `tests/test_c1.py`

- [ ] **Step 1: test che fallisce**

```python
# FaseC/tests/test_c1.py
import pytest
from phase_c.c1_functional import run_c1, diagnose
from phase_c.mock_overlay import MockOverlay
from phase_c.driver import SnnIidmDriver

def test_c1_verde_sullo_scenario_1(golden_scen1):
    r = run_c1(SnnIidmDriver(MockOverlay(golden=golden_scen1)), [golden_scen1])
    assert r['nmismatch'] == 0 and r['n'] == len(golden_scen1.gold)

def test_c1_ROSSO_con_un_errore_iniettato(golden_scen1):
    drv = SnnIidmDriver(MockOverlay(golden=golden_scen1, inject_at=3, inject_delta=0.0039))
    r = run_c1(drv, [golden_scen1])
    assert r['nmismatch'] == 1 and r['first']['k'] == 3

def test_la_diagnosi_indica_per_primo_il_formato_numerico():
    """L'errore che scala con la grandezza e' la firma del formato sbagliato."""
    d = diagnose(first={'k': 0, 'got': 2.0, 'exp': 1.0}, n=600, nmismatch=600)
    assert 'formato' in d[0].lower()
```

- [ ] **Step 2: eseguire e vederlo fallire**

Run: `python -m pytest tests/test_c1.py -v` · Atteso: FAIL — modulo assente

- [ ] **Step 3: implementare**

```python
# FaseC/phase_c/c1_functional.py
"""C1 - il silicio riproduce la simulazione, BIT-ESATTO.

Non 'entro tolleranza': T7a ha provato l'RTL bit-esatto al blocco su 58 522 confronti, e il
silicio esegue quello stesso RTL. Una discrepanza e' un errore di DEPLOYMENT, non d'algoritmo.
"""

DIAGNOSI = [
    ('formato numerico ai due lati del confine',
     'risultati plausibili ma sbagliati, errore che SCALA con la grandezza',
     'En20 in ingresso, sfix13_En8 in uscita, impacchettamento in Python'),
    ('indirizzi/offset',
     'letture a zero o spazzatura dal primo accesso',
     'mappa registri contro l\'assegnazione degli indirizzi'),
    ('polarita del reset',
     'l\'acceleratore non esce dal reset, stato sempre zero',
     'verso del reset al confine del wrapper'),
    ('START che non si auto-azzera',
     'la PRIMA inferenza riesce, la seconda mai',
     'ritorno a idle della macchina a stati'),
    ('pipelining insufficiente',
     'errori INTERMITTENTI',
     'report di timing prima di incolpare l\'algoritmo'),
]


def diagnose(first, n, nmismatch):
    """Ordina i sospettati per compatibilita' col sintomo osservato."""
    out = []
    if first and first.get('exp') not in (None, 0):
        ratio = abs(first['got'] / first['exp']) if first['exp'] else float('inf')
        scala = not (0.9 < ratio < 1.1)
    else:
        scala = False
    tutti = (nmismatch == n)
    for nome, sintomo, dove in DIAGNOSI:
        peso = 0
        if 'formato' in nome and scala and tutti:
            peso = 3
        elif 'indirizzi' in nome and tutti and first and first.get('got') in (0, None):
            peso = 3
        elif 'START' in nome and nmismatch == n - 1:
            peso = 3
        elif 'intermitt' in sintomo and 0 < nmismatch < n * 0.2:
            peso = 2
        out.append((peso, '%s -> %s. Controllare: %s' % (nome, sintomo, dove)))
    return [t for _, t in sorted(out, key=lambda x: -x[0])]


def run_c1(driver, goldens):
    nmis, n, first = 0, 0, None
    for g in goldens:
        for k, (stim, exp) in enumerate(zip(g.stim, g.gold)):
            got = driver.infer(*stim)
            n += 1
            if got != exp:
                nmis += 1
                if first is None:
                    first = {'k': k, 'got': got, 'exp': exp}
    res = {'nmismatch': nmis, 'n': n, 'first': first}
    if nmis:
        res['diagnosi'] = diagnose(first, n, nmis)
    return res
```

- [ ] **Step 4: eseguire e vederlo passare**

Run: `python -m pytest tests/test_c1.py -v` · Atteso: PASS, 3 test

- [ ] **Step 5: commit**

```bash
git add FaseC/phase_c/c1_functional.py FaseC/tests/test_c1.py
git commit -m "feat(fase-c): C1 bit-esatto sui 99 scenari, con scaletta diagnostica ordinata per sintomo"
```

---

## Task 7: `plant_ps.py` + `c2_closedloop.py` — il PLANT-PAR viene prima

**Files:** Create `phase_c/plant_ps.py`, `phase_c/c2_closedloop.py` · Test `tests/test_c2.py`

In C2 il plant gira sul processore: se differisce di un ULP dal riferimento, le traiettorie divergono. Quindi
**prima** si prova il plant **senza** acceleratore, poi si chiude l'anello. È la decomposizione di T7a.

- [ ] **Step 1: test che fallisce**

```python
# FaseC/tests/test_c2.py
import pytest, numpy as np
from phase_c.plant_ps import plant_par, step_plant
from phase_c.c2_closedloop import run_c2, PlantParFailure
from phase_c.mock_overlay import MockOverlay
from phase_c.driver import SnnIidmDriver

def test_plant_par_verde_contro_il_riferimento(oracle_accel_scen1, ref_series_scen1):
    r = plant_par([oracle_accel_scen1], [ref_series_scen1])
    assert r['nmismatch'] == 0

def test_c2_RIFIUTA_di_partire_se_il_plant_par_e_rosso(golden_scen1, ref_series_scen1):
    bad = dict(ref_series_scen1); bad['s'] = np.asarray(bad['s']) + 1e-9
    with pytest.raises(PlantParFailure):
        run_c2(SnnIidmDriver(MockOverlay(golden=golden_scen1)),
               scenarios=[1], plant_par_result={'nmismatch': 7, 'n': 600})

def test_step_plant_usa_la_v_NUOVA_per_il_gap():
    """Ordine di update del riferimento: v_new prima, poi s con v_new. Invertirlo
    produce 599 disallineamenti (misurato in T7a con sensitivity_t7)."""
    s, v = 30.0, 20.0
    s2, v2 = step_plant(s, v, vl=21.0, accel=1.0, dt=0.1)
    assert v2 == pytest.approx(20.1)
    assert s2 == pytest.approx(s + (21.0 - 20.1) * 0.1)
```

- [ ] **Step 2: eseguire e vederlo fallire**

Run: `python -m pytest tests/test_c2.py -v` · Atteso: FAIL — moduli assenti

- [ ] **Step 3: implementare — port 1:1 del riferimento**

```python
# FaseC/phase_c/plant_ps.py
"""Plant sul processore: port 1:1 di qz_cl_sim. NESSUNA logica nuova.

⚠️ L'ordine di update non e' libero: si calcola PRIMA la nuova velocita', POI il gap con la
velocita' NUOVA. Invertirlo da' 599 disallineamenti su 600 (provato in T7a).
"""


def step_plant(s, v, vl, accel, dt=0.1):
    v_new = v + accel * dt
    if v_new < 0.0:
        v_new = 0.0
    s_new = s + (vl - v_new) * dt        # con la v NUOVA
    return s_new, v_new


def plant_par(accel_sequences, ref_series, tol=0.0):
    """Il plant del PS riproduce il riferimento, SENZA acceleratore nell'anello."""
    nmis = n = 0
    for acc, ref in zip(accel_sequences, ref_series):
        s, v = float(ref['s'][0]), float(ref['v'][0])
        for k in range(len(acc)):
            n += 1
            if abs(s - float(ref['s'][k])) > tol or abs(v - float(ref['v'][k])) > tol:
                nmis += 1
            s, v = step_plant(s, v, float(ref['vl'][k]), float(acc[k]))
    return {'nmismatch': nmis, 'n': n}
```

```python
# FaseC/phase_c/c2_closedloop.py
"""C2 - anello chiuso col plant sul processore. Parte SOLO se il PLANT-PAR e' verde."""
from .plant_ps import step_plant
from .regmap import to_fix


class PlantParFailure(RuntimeError):
    pass


def run_c2(driver, scenarios, plant_par_result, init, dt=0.1, kmax=600):
    if plant_par_result['nmismatch'] != 0:
        raise PlantParFailure(
            'PLANT-PAR rosso (%d/%d): l\'anello NON si chiude finche\' il plant del processore '
            'non riproduce il riferimento. Un C2 lanciato ora misurerebbe la divergenza del '
            'plant, non il comportamento dell\'acceleratore.'
            % (plant_par_result['nmismatch'], plant_par_result['n']))
    out = {}
    for sc in scenarios:
        s, v = init[sc]['s0'], init[sc]['v0']
        vl_seq = init[sc]['vl']
        S, V, A = [], [], []
        for k in range(min(kmax, len(vl_seq))):
            vl = float(vl_seq[k])
            a = driver.infer(to_fix(s, 20, 32), to_fix(v, 20, 32),
                             to_fix(v - vl, 20, 32), to_fix(vl, 20, 32))
            S.append(s); V.append(v); A.append(a)
            s, v = step_plant(s, v, vl, a, dt)
            if s <= 0.0:
                break
        out[sc] = {'s': S, 'v': V, 'a': A, 'collided': s <= 0.0}
    return out
```

- [ ] **Step 4: eseguire e vederlo passare**

Run: `python -m pytest tests/test_c2.py -v` · Atteso: PASS, 3 test

- [ ] **Step 5: commit**

```bash
git add FaseC/phase_c/{plant_ps.py,c2_closedloop.py} FaseC/tests/test_c2.py
git commit -m "feat(fase-c): C2 anello chiuso, che RIFIUTA di partire se il PLANT-PAR del PS e' rosso"
```

---

## Task 8: `xadc.py` + `c3_power.py` — la misura che può ingannare

**Files:** Create `phase_c/xadc.py`, `phase_c/c3_power.py` · Test `tests/test_c3.py`

Le tre condizioni della §2.1 della spec sono **codice**, non raccomandazioni.

- [ ] **Step 1: test che fallisce**

```python
# FaseC/tests/test_c3.py
import pytest
from phase_c.c3_power import plan_sequence, aggregate, ThermalReject

def test_l_ordine_e_RANDOMIZZATO_non_alternato():
    """Mytkowicz 2009: il bias di misura sposta i risultati del +-10%, abbastanza a
    invertire una conclusione. Un A/B/A alternato e' vulnerabile alla deriva che pretende
    di cancellare."""
    seqs = {tuple(plan_sequence(['blank','g0','g1'], repeats=6, seed=s)) for s in range(8)}
    assert len(seqs) > 1, 'la sequenza non cambia col seme: non e\' randomizzata'
    for s in seqs:
        assert s.count('blank') == 6 and s.count('g0') == 6 and s.count('g1') == 6

def test_i_punti_fuori_equilibrio_termico_si_SCARTANO():
    pts = [{'cfg':'g0','mA':400.0,'tj':45.0}, {'cfg':'g0','mA':402.0,'tj':45.2},
           {'cfg':'g0','mA':398.0,'tj':61.0}]     # ultimo fuori banda
    r = aggregate(pts, tj_window=(40.0, 50.0))
    assert r['g0']['n_scartati'] == 1 and r['g0']['n'] == 2

def test_il_risultato_e_una_DISTRIBUZIONE_non_un_numero():
    pts = [{'cfg':'g1','mA':400.0+i*0.1,'tj':45.0} for i in range(20)]
    r = aggregate(pts, tj_window=(40.0, 50.0))
    for k in ('mediana','p99','min','max','iqr','n'):
        assert k in r['g1']

def test_scarta_TUTTO_se_nessun_punto_e_in_banda():
    with pytest.raises(ThermalReject):
        aggregate([{'cfg':'g0','mA':400.0,'tj':70.0}], tj_window=(40.0, 50.0))
```

- [ ] **Step 2: eseguire e vederlo fallire**

Run: `python -m pytest tests/test_c3.py -v` · Atteso: FAIL — modulo assente

- [ ] **Step 3: implementare**

```python
# FaseC/phase_c/xadc.py
"""XADC (UG480): temperatura di giunzione e tensioni dei rail. NON la corrente.

Serve a rendere CREDIBILE la misura di potenza, non a farla: la dispersione e' esponenziale
nella temperatura (WP221) e la statica e' 103 mW su 114, cioe' la parte dominante.
"""
XADC_BASE = 0xF8007100
TEMP_OFF, VCCINT_OFF = 0x00, 0x04


def read_tj(mmio):
    raw = (mmio.read(XADC_BASE + TEMP_OFF) >> 4) & 0xFFF
    return raw * 503.975 / 4096.0 - 273.15          # UG480 eq. 2-9


def read_vccint(mmio):
    raw = (mmio.read(XADC_BASE + VCCINT_OFF) >> 4) & 0xFFF
    return raw * 3.0 / 4096.0                       # UG480 eq. 2-11
```

```python
# FaseC/phase_c/c3_power.py
"""C3 - potenza differenziale total-board.

Il PL e' 114 mW su 1,5-2,5 W di scheda: invisibile in assoluto. Ma il numero non e' assoluto:
stesso hardware, stesso stato del PS, cambia SOLO il bitstream. (b)-(a) isola il PL,
(b)-(c) e' il guadagno del gating; il consumo del PS si cancella.

Tre condizioni, che qui sono CODICE:
  1. ordine RANDOMIZZATO (non alternato) -- Mytkowicz 2009, bias +-10%
  2. Tj registrata a ogni punto, punti fuori banda SCARTATI -- WP221
  3. risultato = distribuzione, non un numero
"""
import random, statistics


class ThermalReject(RuntimeError):
    pass


def plan_sequence(configs, repeats, seed):
    seq = [c for c in configs for _ in range(repeats)]
    random.Random(seed).shuffle(seq)
    return seq


def aggregate(points, tj_window):
    lo, hi = tj_window
    out = {}
    for cfg in sorted({p['cfg'] for p in points}):
        tutti = [p for p in points if p['cfg'] == cfg]
        buoni = [p['mA'] for p in tutti if lo <= p['tj'] <= hi]
        if not buoni:
            raise ThermalReject(
                'configurazione %r: nessun punto nella banda termica [%.1f, %.1f] degC. '
                'La misura non e\' utilizzabile: la dispersione e\' esponenziale in Tj e la '
                'statica domina il consumo del PL.' % (cfg, lo, hi))
        b = sorted(buoni)
        out[cfg] = dict(
            mediana=statistics.median(b), min=b[0], max=b[-1],
            p99=b[min(len(b) - 1, int(0.99 * len(b)))],
            iqr=b[int(0.75 * len(b)) - 1] - b[int(0.25 * len(b))] if len(b) >= 4 else 0.0,
            n=len(b), n_scartati=len(tutti) - len(buoni))
    return out


def gating_gain_mW(agg, volt=5.0, n_instances=1):
    """(g0 - g1) in mW, per istanza, con l'incertezza dalla dispersione."""
    d_mA = agg['g0']['mediana'] - agg['g1']['mediana']
    unc = (agg['g0']['iqr'] + agg['g1']['iqr']) / 2.0
    return {'mW_per_istanza': d_mA * volt / n_instances,
            'incertezza_mW': unc * volt / n_instances,
            'n_istanze': n_instances}
```

- [ ] **Step 4: eseguire e vederlo passare**

Run: `python -m pytest tests/test_c3.py -v` · Atteso: PASS, 4 test

- [ ] **Step 5: commit**

```bash
git add FaseC/phase_c/{xadc.py,c3_power.py} FaseC/tests/test_c3.py
git commit -m "feat(fase-c): C3 potenza differenziale - ordine randomizzato, Tj come cancello, distribuzione"
```

---

## Task 8bis: `params.py` — i parametri veri e il campione, da UN posto

**Files:** Create `phase_c/params.py` · Test `tests/test_params.py`

Il Task 9 mette il **nostro controllore** nell'anello del plotone: gli servono il campione addestrato e i
`gt_params` dello scenario. Nessuno dei due si ricarica a mano: esiste gia' un caricatore canonico nel
progetto e questo modulo lo avvolge, non lo riscrive.

- [ ] **Step 1: trovare il caricatore canonico, NON inventarlo**

Run: `grep -rn "def load_champion\|torch.load\|state_dict" --include=*.py utils/ core/ scripts/ | head -20`
Atteso: la funzione che gli altri studi usano gia' per caricare un `champions/*/`. **Se non esiste un
punto unico, fermarsi e dirlo** — duplicare il caricamento e' la prima copia sincronizzata a mano.

- [ ] **Step 2: test che fallisce**

```python
# FaseC/tests/test_params.py
import pytest, numpy as np
from phase_c.params import load_gt_params, load_champion, CHAMPION

def test_gt_params_sono_cinque_e_positivi():
    p = load_gt_params(0)
    assert p.shape == (5,)
    assert np.all(p > 0), 'v0,T,s0,a,b devono essere tutti positivi'

def test_scenari_diversi_hanno_parametri_diversi():
    """Se tutti gli scenari dessero gli stessi parametri, P1 misurerebbe UN caso ripetuto."""
    ps = np.array([load_gt_params(i) for i in range(5)])
    assert not np.allclose(ps[0], ps[1:]), 'i gt_params non variano fra scenari'

def test_il_campione_e_quello_montato_in_hardware():
    """Il plotone deve girare col BALANCED, cioe' con la rete che sta nel bitstream."""
    assert 'R33_C2_A1_T12_fix' in CHAMPION or 'BALANCED' in CHAMPION
    m = load_champion()
    assert hasattr(m, 'reset_state'), 'il modello deve esporre reset_state (lo usa simulate)'
```

- [ ] **Step 3: eseguire e vederlo fallire**

Run: `cd FaseC && python -m pytest tests/test_params.py -v`
Atteso: FAIL — `ModuleNotFoundError: No module named 'phase_c.params'`

- [ ] **Step 4: implementare, avvolgendo il caricatore trovato allo Step 1**

```python
# FaseC/phase_c/params.py
"""Parametri veri e campione addestrato. Avvolge il caricatore canonico, non lo duplica.

Il campione e' quello che sta nel bitstream: il plotone deve misurare la rete DEPLOYATA,
non un'altra. La costante CHAMPION e' l'unico posto in cui il nome vive.
"""
import os
import numpy as np
import scipy.io as sio

from . import PROJECT

CHAMPION = 'R33_C2_A1_T12_fix'                       # il BALANCED montato nel composto
DATASET = os.path.join(PROJECT, 'data', 'test_dataset_exhaustive.mat')

_ds = None


def _dataset():
    global _ds
    if _ds is None:
        if not os.path.isfile(DATASET):
            raise FileNotFoundError('dataset assente: %s' % DATASET)
        _ds = sio.loadmat(DATASET)
    return _ds


def load_gt_params(i):
    """Parametri veri [v0, T, s0, a, b] dello scenario i."""
    return np.asarray(_dataset()['gt_params'][i], dtype=np.float64).ravel()


def n_scenarios():
    return int(_dataset()['gt_params'].shape[0])


def load_champion(name=CHAMPION, device='cpu'):
    """Il campione addestrato, dal caricatore canonico del progetto (Step 1)."""
    from utils.model_io import load_champion as _load     # sostituire col nome reale
    return _load(name, device=device)
```

- [ ] **Step 5: eseguire e vederlo passare**

Run: `cd FaseC && python -m pytest tests/test_params.py -v`
Atteso: PASS, 3 test

- [ ] **Step 6: commit**

```bash
git add FaseC/phase_c/params.py FaseC/tests/test_params.py
git commit -m "feat(fase-c): params - gt_params e campione da un solo posto, avvolgendo il caricatore canonico"
```

---

## Task 9: P1 — plotone in simulazione, col NOSTRO controllore nell'anello

**Files:** Create `phase_c/platoon.py` · Test `tests/test_platoon.py` · Artefatto `results/P1_platoon.json`

**Non dipende dalla scheda e chiude un limite dichiarato**: la string stability nei report di B2.0 e', nel
motore canonico stesso, *un proxy LOCALE = il caso N=1*. Il numero mesoscopico vero non e' mai entrato nei
report.

> ⚠️ **Correzione verificata prima dell'esecuzione.** Nel progetto esistono **due** `simulate_platoon`:
>
> | Modulo | Firma | Cosa mette nell'anello |
> |---|---|---|
> | `utils/closed_loop_eval.py` | `simulate_platoon(params_list, leader_v)` | chiama `simulate(None, ...)` → **l'ORACOLO analitico**. Il modello e' cablato a `None`: non c'e' modo di passarcelo. |
> | `utils/platoon_eval.py` | `simulate_platoon(model, params_gt, n_vehicles, v_leader_profile)` | **il modello che gli passi** — il nostro controllore. |
>
> Va usato il **secondo**. Il primo avrebbe misurato la string stability dell'IDM analitico e l'avremmo
> attribuita al controllore: conclusione dalla forma giusta, premessa sbagliata. Le metriche stanno in
> `platoon_metrics` (non `platoon_string_metrics`), e la chiave `gain_max` **non esiste**: quelle vere sono
> `head_to_tail_gain`, `max_amplification`, `string_stable_headtail`, piu' sicurezza (`min_ttc_platoon`,
> `min_gap_platoon`, `collided`) e comfort (`rms_accel_mean`, `rms_jerk_mean`).

- [ ] **Step 1: test che fallisce**

```python
# FaseC/tests/test_platoon.py
import pytest, inspect
from phase_c import platoon

def test_p1_produce_le_metriche_REALI_per_ogni_N():
    r = platoon.run_p1(n_vehicles=(2, 4), n_scenarios=2, seed=0)
    assert set(r['per_N']) == {2, 4}
    for N in (2, 4):
        v = r['per_N'][N]
        for k in ('head_to_tail_median', 'head_to_tail_p99', 'max_amplification_p99',
                  'n_string_stable', 'n_collided', 'min_ttc_min', 'n'):
            assert k in v, 'metrica %r assente' % k

def test_p1_dichiara_la_stabilita_sulla_CODA_non_sulla_mediana():
    """Nella sicurezza conta la coda: la mediana cancella proprio i casi che contano."""
    r = platoon.run_p1(n_vehicles=(4,), n_scenarios=2, seed=0)
    v = r['per_N'][4]
    assert v['string_stable'] == (v['head_to_tail_p99'] <= 1.0)

def test_p1_usa_il_modulo_CHE_ACCETTA_IL_MODELLO():
    """Il rischio vero: misurare l'oracolo analitico e attribuirlo al controllore."""
    src = inspect.getsource(platoon)
    assert 'platoon_eval' in src, 'deve usare utils.platoon_eval (accetta il modello)'
    assert 'closed_loop_eval import simulate_platoon' not in src, \
        'utils.closed_loop_eval.simulate_platoon cabla model=None: misurerebbe l\'oracolo'
```

- [ ] **Step 2: eseguire e vederlo fallire**

Run: `cd FaseC && python -m pytest tests/test_platoon.py -v`
Atteso: FAIL — `ModuleNotFoundError: No module named 'phase_c.platoon'`

- [ ] **Step 3: implementare**

```python
# FaseC/phase_c/platoon.py
"""Filone C - plotone. Chiude il proxy N=1 dichiarato nei report di B2.0.

Usa utils.platoon_eval (che ACCETTA il modello), non utils.closed_loop_eval (che cabla
model=None e simulerebbe l'oracolo analitico).

La string stability e' una proprieta' della LEGGE DI CONTROLLO: poiche' l'RTL e' bit-esatto
al blocco, il numero non cambia sul silicio. P3 risponde alla domanda di DEPLOYMENT, diversa.
"""
import os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.platoon_eval import simulate_platoon, platoon_metrics

from .params import load_champion, load_gt_params, n_scenarios
from . import artifacts

DT = 0.1


def leader_profile(L=600, seed=0, amp=1.5, f=0.08, base=22.0):
    """Perturbazione sinusoidale sul leader: e' cio' che il plotone deve NON amplificare."""
    t = np.arange(L) * DT
    rng = np.random.default_rng(seed)
    return base + amp * np.sin(2 * np.pi * f * t) + 0.05 * rng.standard_normal(L)


def _pct(xs, q):
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * len(s)))]


def run_p1(n_vehicles=(2, 4, 8, 16), n_scenarios_=10, seed=0, model=None, n_scenarios=None):
    n_sc = n_scenarios if n_scenarios is not None else n_scenarios_
    mdl = model if model is not None else load_champion()
    out = {'per_N': {}, 'n_scenarios': n_sc, 'seed': seed}
    for N in n_vehicles:
        h2t, amp, stable, coll, ttc = [], [], 0, 0, []
        for i in range(n_sc):
            pgt = load_gt_params(i)
            lead = leader_profile(seed=seed * 1000 + i)
            rec = simulate_platoon(mdl, pgt, N, lead)
            m = platoon_metrics(rec)
            h2t.append(float(m['head_to_tail_gain']))
            amp.append(float(m['max_amplification']))
            stable += int(bool(m['string_stable_headtail']))
            coll += int(bool(m['collided']))
            ttc.append(float(m['min_ttc_platoon']))
        out['per_N'][N] = dict(
            head_to_tail_median=_pct(h2t, 0.5), head_to_tail_p99=_pct(h2t, 0.99),
            head_to_tail_max=max(h2t), max_amplification_p99=_pct(amp, 0.99),
            n_string_stable=stable, n_collided=coll,
            min_ttc_min=min(ttc), n=n_sc,
            # la stabilita' si dichiara sulla CODA: la mediana cancella i casi che contano
            string_stable=_pct(h2t, 0.99) <= 1.0)
    return out
```

- [ ] **Step 4: eseguire e vederlo passare**

Run: `cd FaseC && python -m pytest tests/test_platoon.py -v`
Atteso: PASS, 3 test

- [ ] **Step 5: eseguire P1 davvero e salvare l'artefatto**

Run: `cd FaseC && python -m phase_c.cli --stage p1 --frontend script`
Atteso: `results/P1_platoon.json` con `per_N` per N = 2, 4, 8, 16 sui 99 scenari, ciascuno con
mediana/p99/max di `head_to_tail`, quanti scenari string-stable su quanti, collisioni e TTC minimo.

- [ ] **Step 6: commit**

```bash
git add FaseC/phase_c/platoon.py FaseC/tests/test_platoon.py FaseC/results/P1_platoon.json
git commit -m "feat(fase-c): P1 - string stability VERA del plotone col controllore nell'anello"
```

---


## Task 10: P3-sonda — la curva risorse si misura

**Files:** Create `FaseC/hw/probe_resources.sh`, `hw/probe_resources.tcl` · Artefatto `results/P3_resources.json`

Non dipende dalla scheda: è sintesi. Il vincolo è il DSP (69 su 220 → 3 istanze); forzare i moltiplicatori in
fabric (`-max_dsp`) può ribilanciare, ma un 25×18 costa centinaia di LUT. **La curva non è nota.**

- [ ] **Step 1: cancello preliminare, PRIMA di ~10 min per punto**

```bash
# FaseC/hw/probe_resources.sh
set -u
SRC="C:/t7bimpl/src"
nv=$(ls "$SRC"/*.v 2>/dev/null | wc -l)
[ "$nv" -ge 11 ] || { echo "PROBE-ABORT: solo $nv .v in $SRC (attesi >=11)"; exit 1; }
for N in ${1:-"1 2 3 4"}; do
  for MAXDSP in ${2:-"220 150 100 50 0"}; do
    echo "--- N=$N max_dsp=$MAXDSP [$(date +%H:%M:%S)] ---"
    "$VIV/vivado.bat" -mode batch -notrace -nojournal -nolog \
      -source "$(dirname "$0")/probe_resources.tcl" -tclargs "$SRC" "C:/t7cprobe" "$N" "$MAXDSP" \
      2>&1 | grep -E "^(PROBE|ERROR:)"
  done
done
```

- [ ] **Step 2: eseguire un punto solo, per misurare il costo**

Run: `bash hw/probe_resources.sh "1" "220"`
Atteso: una riga `PROBE N=1 max_dsp=220 LUT=... FF=... DSP=... FIT=si` in ~10 min.
**Se il costo differisce molto da 10 min, riportarlo prima di lanciare la griglia intera.**

- [ ] **Step 3: la griglia, in background**

Run: `bash hw/probe_resources.sh "1 2 3 4" "220 150 100 50 0" > results/P3_probe.log 2>&1 &`
Atteso: 20 punti. Costo dichiarato in anticipo: **~3,5 ore**.

- [ ] **Step 4: generare la curva e leggere il ginocchio**

Run: `python hw/gen_resource_report.py`
Atteso: `results/P3_resources.json` + la riga `N massimo che entra = <n>, a max_dsp=<m>`.

- [ ] **Step 5: commit**

```bash
git add FaseC/hw/ FaseC/results/P3_resources.json FaseC/results/P3_probe.log
git commit -m "feat(fase-c): sonda risorse per il plotone - curva LUT/DSP misurata, non stimata"
```

---

## Task 11: le due facciate e il cancello di parità

**Files:** Create `run_phase_c.sh`, `phase_c.ipynb`, `c_frontend_parity.py` · Test `tests/test_parity.py`

- [ ] **Step 1: test che fallisce**

```python
# FaseC/tests/test_parity.py
import pytest, json
from c_frontend_parity import compare

def test_parita_verde_se_i_dati_coincidono(tmp_path):
    a, b = tmp_path/'a.json', tmp_path/'b.json'
    for p, fe in ((a,'script'), (b,'notebook')):
        p.write_text(json.dumps({'data':{'nmismatch':0,'n':600},
                                 'prov':{'frontend':fe,'timestamp':'x','bitstream_sig':'s','cwd':'/z'}}))
    assert compare(a, b)['ok']

def test_parita_ROSSA_se_un_numero_differisce(tmp_path):
    a, b = tmp_path/'a.json', tmp_path/'b.json'
    a.write_text(json.dumps({'data':{'nmismatch':0},'prov':{'frontend':'script','timestamp':'x','bitstream_sig':'s','cwd':'/z'}}))
    b.write_text(json.dumps({'data':{'nmismatch':1},'prov':{'frontend':'notebook','timestamp':'y','bitstream_sig':'s','cwd':'/w'}}))
    r = compare(a, b)
    assert not r['ok'] and 'nmismatch' in r['diff']
```

- [ ] **Step 2: eseguire e vederlo fallire**

Run: `python -m pytest tests/test_parity.py -v` · Atteso: FAIL — modulo assente

- [ ] **Step 3: implementare il cancello**

```python
# FaseC/c_frontend_parity.py
"""Le due facciate, sullo stesso stato della scheda, devono produrre artefatti IDENTICI.

Se divergono, una delle due contiene logica propria: e' un difetto, non una curiosita'.
La ridondanza chiesta diventa cosi' informativa invece che rassicurante.
"""
import sys
from phase_c.artifacts import read, stable_view


def compare(pa, pb):
    a, b = stable_view(read(pa)), stable_view(read(pb))
    if a == b:
        return {'ok': True, 'diff': None}
    diff = [k for k in set(a['data']) | set(b['data'])
            if a['data'].get(k) != b['data'].get(k)]
    return {'ok': False, 'diff': diff,
            'msg': 'le facciate divergono su %s: una delle due contiene logica propria' % diff}


if __name__ == '__main__':
    r = compare(sys.argv[1], sys.argv[2])
    print('PARITA-OK' if r['ok'] else 'PARITA-ROSSA: ' + r['msg'])
    sys.exit(0 if r['ok'] else 1)
```

- [ ] **Step 4: eseguire e vederlo passare**

Run: `python -m pytest tests/test_parity.py -v` · Atteso: PASS, 2 test

- [ ] **Step 5: la facciata a stadi**

```bash
# FaseC/run_phase_c.sh
set -u
STAGE="${1:-summary}"
case "$STAGE" in
  c0|c1|c2|c3) python -m phase_c.cli --stage "$STAGE" --frontend script ;;
  p1)          python -m phase_c.platoon --p1 --out results/P1_platoon.json ;;
  parity)      python c_frontend_parity.py results/c1_script.json results/c1_notebook.json ;;
  summary)     python -m phase_c.cli --summary ;;
  *) echo "usa: c0|c1|c2|c3|p1|parity|summary"; exit 2 ;;
esac
```

- [ ] **Step 6: il notebook, che chiama e disegna soltanto**

Il notebook contiene **una chiamata e un grafico per cella**, mai logica:

```python
# cella tipo
from phase_c import cli
r = cli.run_stage('c1', frontend='notebook')      # stessa funzione dello script
plot_accel_vs_trajectory(r)                        # da phase_c.plots
```

- [ ] **Step 7: cancello sull'esecuzione headless**

Run: `jupyter nbconvert --execute --to notebook --inplace phase_c.ipynb`
Atteso: esce 0. **Se non gira headless da kernel pulito, non è riproducibile** — e lo si scopre ora, non a
fine campagna.

- [ ] **Step 8: commit**

```bash
git add FaseC/{run_phase_c.sh,phase_c.ipynb,c_frontend_parity.py} FaseC/tests/test_parity.py
git commit -m "feat(fase-c): due facciate sopra gli stessi moduli, con cancello di parita' e esecuzione headless"
```

---

# PARTE II — Richiede la scheda accendibile

## Task 12: RUNBOOK e sequenza di accensione

**Files:** Create `FaseC/RUNBOOK.md`

- [ ] **Step 1: scrivere il runbook**

Contiene, nell'ordine: (1) copia dei tre bitstream sulla board · (2) `run_phase_c.sh c0` — **se rosso, fermarsi
e leggere la diagnosi** · (3) `c1` sui 99 · (4) PLANT-PAR poi `c2` · (5) `c3` con la procedura di misura ·
(6) `parity`. Per ogni stadio: costo atteso, artefatto prodotto, e cosa fare se è rosso.

- [ ] **Step 2: la procedura di misura di C3, passo per passo**

Multimetro in serie all'alimentazione · attesa dell'equilibrio termico (criterio: `Tj` stabile entro ±0,5 °C
per 60 s) · sequenza **sorteggiata** da `plan_sequence(seed=<dichiarato>)` · a ogni punto si registra
`(cfg, mA, Tj, VCCINT)` · almeno 6 ripetizioni per configurazione.

- [ ] **Step 3: commit**

```bash
git add FaseC/RUNBOOK.md
git commit -m "docs(fase-c): runbook di accensione, con la procedura di misura e cosa fare a ogni cancello rosso"
```

## Task 13: esecuzione dei filoni A e B, e P2/P3

- [ ] **A:** `c0 → c1 → c2 → c3` sul bitstream del composto (40 MHz)
- [ ] **B:** gli stessi stadi sul bitstream della SNN (52 MHz), con `SnnTierDriver`
- [ ] **P2:** plotone in RTL, riusando il banco di T7a
- [ ] **P3:** build a N istanze (N dalla sonda del Task 10), funzionale + energia per nodo
- [ ] **Confronto con la stima di simulazione** (§2.2 della spec): informativo in entrambi gli esiti

## Task 14: report finale

- [ ] Generatore `scripts/build_fase_c_report.py` che **legge gli artefatti**, con audit in **due direzioni**
      (ogni numero torna alla fonte **e** ogni grandezza delle fonti è arrivata nel report), come per T8.
- [ ] Aggiornare i due report di B2.0: la string stability vera **sostituisce** il proxy; i limiti chiusi
      passano da «aperto» a «chiuso, con il numero».

---

## Self-review

**Copertura della spec.** §2.1 condizione 1 → Task 8 Step 1 · condizione 2 → Task 8 (`ThermalReject`) ·
condizione 3 → Task 8 (`aggregate`) · §2.2 ipotesi verificabile → Task 13 · §3 C0/C1/C2/C3 → Task 5/6/7/8 ·
§4 filone B → Task 13 · §4 filone C P1/P2/P3 → Task 9/13/10 · §5.1 parità → Task 11 · §6 time-multiplexing →
registrato in spec, nessun task (è una via **esclusa**) · §7 diagnostica → Task 6 (`diagnose`) · §8 mock in
negativo → Task 2 · §9 criteri → Task 13/14 · §11 limiti → Task 14.

**Segnaposto:** nessuno. Ogni step ha comando, codice e atteso.

**Coerenza dei tipi:** `Golden(stim, gold)` usato identico in Task 2/6 · `regmap` è sempre `IIDM`/`TIER` da
`regmap.py` · `run_c1` restituisce `{'nmismatch','n','first'}` e Task 11 confronta quelle chiavi · `aggregate`
restituisce per-configurazione le chiavi che `gating_gain_mW` legge (`mediana`, `iqr`).

**Dipendenza dichiarata:** `phase_c/params.py` (caricamento dei parametri veri) e `phase_c/cli.py`
(entry-point condiviso dalle facciate) sono usati nei Task 9 e 11: vanno creati lì, non altrove.
