# IIDM — divisore SEQUENZIALE digit-recurrence in-chart (SP4 #2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps con checkbox (`- [ ]`).

**Goal:** Alzare l'`Fmax` del controllore oltre 15,67 MHz sostituendo la `divide()` combinatoria in-chart
con una **ricorrenza digit-recurrence sequenziale** (1 bit/ciclo) scritta a mano DENTRO la chart —
**bit-exact** (`dmax = 0`) — poi iterare probe-first sul collo successivo.

**Architecture:** Nessun blocco esterno ⇒ **nessuna conversione MATLAB-to-dataflow** (è il motivo per cui
#1 è morta due volte). Lo stadio DIV della FSM itera la ricorrenza un bit per ciclo; `kdiv` resta STATO.

**Tech Stack:** MATLAB R2026a · HDL Coder · Vivado 2026.1 OOC xc7z020 @8 MHz · xsim (Git Bash in PATH).

**Spec:** `docs/superpowers/specs/2026-07-19-iidm-pipelined-divider-design.md` (§4 approccio, §5 algoritmo)

**Principio guida (dall'errore di #1): i DUE RISCHI SI SEPARANO.** Prima si prova l'ALGORITMO come
funzione pura (zero chirurgia), poi lo STAGING nella FSM. Ogni rischio col suo cancello.

---

## File Structure

| file | responsabilità | azione |
|---|---|---|
| `matlab/div_seq.m` | ricorrenza restoring, forma FUNZIONALE (un colpo) — l'ALGORITMO da provare | **Create** |
| `matlab/probe_div_seq.m` | cancello: `div_seq` ≡ `divide()` su 300k coppie reali + sensibilità | **Create** |
| `matlab/build_hdl_variants.m` | stadio DIV della chart → ricorrenza multi-ciclo (solo dopo T1 verde) | **Modify** |
| `matlab/hdl_iidm/RESULTS.txt` | curva `Fmax`(round) + **area** + latenza | **Modify** |

**Non si toccano:** `snn_types`, `acc_types`, `acc_iidm_open`, le funzioni-fase, `snn_b2_fsm`.

---

## Task 1: L'ALGORITMO — make-or-break, zero chirurgia

- [ ] **Step 1: `matlab/div_seq.m`** — ricorrenza restoring sulle magnitudini, segno alla fine
      (= `RoundingMethod='Zero'` per costruzione), saturazione al range di `T.acc`. Vedi spec §5.

- [ ] **Step 2: `matlab/probe_div_seq.m`** — confronto con `divide(numerictype(T.acc),num,den)` sulle
      coppie REALI di `collect_div_pairs` (300k), + **prova di sensibilità** (una variante volutamente
      sbagliata deve DIVERGERE, o il cancello non discrimina).

- [ ] **Step 3: Eseguire il cancello**

```bash
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); P = collect_div_pairs(); d = probe_div_seq(P); assert(d==0,'div_seq NON bit-exact: dmax=%g',d)"
```

Expected: `dmax = 0` su ~300.000 coppie. **Se ≠ 0:** l'errore sarà quasi certamente sui **segni** o sui
casi limite (`den` negativo, `num` minimo, quoziente in saturazione) — isolare stampando le prime coppie
divergenti, NON cambiare il cancello.

- [ ] **Step 4: Commit** (solo se verde)

```bash
git add matlab/div_seq.m matlab/probe_div_seq.m
git commit -m "test(iidm): div_seq digit-recurrence bit-identico a divide() su 300k coppie (make-or-break #2)"
```

---

## Task 2: Lo STAGING nella FSM (solo se T1 è verde)

- [ ] **Step 1:** Nella chart (`acciidm_m_chart_code`), lo stadio `phase == 4` (DIV) diventa multi-ciclo:
      stato aggiuntivo per `R`, `Q`, contatore di bit; avanza a `phase 5` quando il contatore è esaurito.
      `kdiv` resta STATO (un `for` verrebbe srotolato → 5 divisori).
- [ ] **Step 2:** Rebuild + **G3/G4** (`run_block_acciidm_m_test(12,1,hold)`), leggendo la **LATENZA**
      stampata da G4 e alzando `hold` se serve (la ricorrenza aggiunge ~1 ciclo/bit × 5 divisioni).
- [ ] **Step 3:** **Verificare che l'HDL si generi** (`rtl_gen_dut('Donatello_ACC_IIDM_M',[],'Verilog')`)
      — è il gate che #1 non passava; qui NON dovrebbe esserci dataflow, ma si verifica, non si assume.
- [ ] **Step 4:** Commit.

---

## Task 3: Cancelli completi + sintesi

- [ ] **Step 1:** `run_iidm_round('r1', hold)` → G3/G4 + parity 0/60000 + B-1 0/3000 + gen VHDL.
- [ ] **Step 2:** G2 una tantum (`run_acciidm_m_dataset()` → `dmax=0` su 60k).
- [ ] **Step 3:** Sintesi OOC (copia space-free in `/d/zbd_pipe`, `synth_acc_iidm.tcl`) → **Fmax +
      critpath + AREA** (LUT/FF/DSP/BRAM) + latenza. Registrare TUTTO in `hdl_iidm/RESULTS.txt`.
- [ ] **Step 4:** Commit.

---

## Task 4: Round iterativi (probe-first) + Task 5: chiusura

- [ ] Leggere `critpath.rpt` → leva che calza (atteso: `st_sab`/sqrt) → gate → sintesi → registrare.
- [ ] **STOP** quando: collo = op singola non spezzabile · round < ~5% · area fuori budget.
- [ ] Chiusura: curva `Fmax`(round) **+ area + latenza + potenza sui candidati**, verdetto, doc
      (`SP4 §Studio IIDM`, `SESSION_RESUME`, memoria).

---

## Rischi

1. **Segni e casi limite** — dove i divisori a mano rompono. Cancello su 300k coppie **reali** (T1).
2. **Latenza** — cresce (~1 ciclo/bit × 5). Misurarla con G4, propagarla nell'`hold`. Mai assumerla.
3. **HDL gen** — verificarla esplicitamente (T2 Step 3): è il gate che ha smentito #1.
4. **Area** — misurata ad ogni round (il trade-off finale non è solo Fmax).
