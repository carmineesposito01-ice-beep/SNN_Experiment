# SP4-M-FSM — ACC-IIDM time-mux via FSM + blocco Divide pipelinato — Implementation Plan

> # 🗄️ PIANO ESEGUITO E CHIUSO (2026-07-17) — NON RI-ESEGUIRE
> **Task 1-3: FATTI e VERDI.** T1/G1: blocco `Divide` == `divide()`-SP3, **dmax=0 su 300.000 coppie reali**
> (sensibile: 'Nearest' → 1 LSB) · T2/G2: model FSM == SP3, **0/60000 control-step** (sensibile: q2↔q3 →
> 1990/2000) · T3/G3-G4: blocco M == model == SP3 su **5/5 traiettorie**, latenza **misurata 509 clk**,
> edge-triggered. Commit: `e31c6b3d`, `a910934f`, `02813818`, `f430aad0`, `c32a9619`.
>
> **Task 4 (G5/G6): BLOCCATO DEFINITIVAMENTE — il design è morto.** Il blocco M **non genera VHDL**: il blocco
> `Divide` accanto alla chart impone la conversione MATLAB-to-dataflow, che **vieta `tanh` in fixed-point**,
> e `tanh` è nel cuore dell'IIDM. Aggirarla = approssimare = `dmax≠0` = ciò che M esiste per evitare.
> **Il verdetto OOC (Fmax ≥ 11,65?) non è mai stato raggiunto**: si è fermati prima, alla generazione.
>
> **Resta l'approccio #2** (divisore dentro la chart) → nuovo ciclo `brainstorming → spec → piano`.
> Funzioni-fase, model, G2, G3/G4 e infrastruttura di verifica **si riusano identici**.
> Dettaglio: `document/SP4_ACC_IIDM_FAST.md` §Variante M-FSM · gotcha: `document/HDL_PHASE.md` §9.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) o
> superpowers:executing-plans, task-by-task. Steps in checkbox (`- [ ]`).

**Goal:** portare l'ACC-IIDM fixed a **Fmax ≥ 11,65 MHz** con area ridotta, sequenziando le 5 divisioni su **un
solo blocco `Divide` HDL pipelinato** guidato da una FSM, **bit-identico a SP3 (`dmax=0`)**.

**Architecture:** nuovo blocco `Donatello_ACC_IIDM_M` = MATLAB Function `IIDM_CTRL` (matematica IIDM non-÷
**verbatim** da `acc_iidm_open` + FSM di scheduling) che riusa **1 blocco `Divide` HDL** (ShiftAdd, latency custom)
per le 5 divisioni. Bit-identità dimostrata per **transitività** su 3 gate (G1 `Divide`==`divide()`, G2 parità
dataset, G3 blocco==model). **Task 1 = make-or-break**: se il blocco `Divide` non è bit-identico a `divide()`-SP3, il
piano si ferma (fallback #2/#3 = piano a sé).

**Tech Stack:** MATLAB R2026a + HDL Coder (blocco `Divide`, `makehdl`, `hdllib`) · Fixed-Point Designer (`divide`,
`fi`) · Vivado 2026.1 (`C:\AMDDesignTools\2026.1\Vivado\bin\vivado.bat`, `xc7z020clg400-1`).

**Spec:** `docs/superpowers/specs/2026-07-16-acc-iidm-fsm-design.md`

---

## Convenzioni (valide per tutti i task)
- **Dir:** `matlab/`. Batch: `"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); <cmd>"` (Bash tool, path POSIX, quota bene: la dir ha spazi). Lavoro lungo (MATLAB/Vivado) → **background** + checkpoint.
- **Commit** conventional, **senza `Co-Authored-By`**; push libero su `Simulink_Importer`.
- **File estranei, MAI nei `git add`**: `matlab/closed_loop_demo.slx`, `matlab/slblocks.m`, `matlab/*.mexw64`.
- **Cancelli:** sul **DATASET intero** (riportare *quanti su quanti*), **`assert`** (non solo stampa), **provati
  sensibili** (rotti apposta → devono fallire). Stato `clear`ato, campionamento deterministico.
- **Numeri di riferimento (misurati):** SP3 catena IIDM = **10846 LUT · 69 DSP · WNS −373 ns · Fmax 2,0 MHz · 1077
  liv.**; M-config share5_cp = **25557 LUT · 22922 FF · 38 DSP · 9,51 MHz · 172 liv.** (area esplosa). Bersaglio:
  **Fmax ≥ 11,65 MHz** con **LUT/FF ≪ M-config**.
- **Gotcha già pagati** (`document/HDL_PHASE.md` §9, `document/SP3_ACC_IIDM_HDL.md`): fimath **parte del tipo**;
  una variabile non cambia tipo/fimath (`x(:)=…`); `if isempty(<persistent>)` letterale; range dei `fi` costanti
  (saturazione silenziosa); il messaggio VERO di un errore di chart si ha da
  `codegen('-config:lib','SNN_ACC','-args',{a,a,a,a})` con `a=fi(0,1,32,20)`, non da Simulink; **niente LAPACK
  numpy** nei test Python (OMP #15). **Bug §2.1 da NON ripetere:** mai un cast che stringe un valore prima di una
  decisione.

## File Structure
```
matlab/acc_iidm_open.m            # MODIFICA minima (Task 1): output opzionale delle 5 coppie (num,den) per G1
matlab/collect_div_pairs.m        # NUOVO (Task 1): estrae ~300k coppie (num,den) reali dal dataset
matlab/probe_divide_bitexact.m    # NUOVO (Task 1, make-or-break): blocco Divide vs divide()-SP3 su quelle coppie
matlab/acc_iidm_fsm.m             # NUOVO (Task 2): matematica non-÷ verbatim (funzioni locali) + FSM, divide() inline
matlab/build_acc_iidm_fsm_mex.m   # NUOVO (Task 2): MEX del model per G2 sul dataset
matlab/run_acciidm_m_dataset.m    # NUOVO (Task 2): G2 - parità dataset (60x1000) model vs acc_iidm_open
matlab/build_hdl_variants.m       # MODIFICA (Task 3): costruisce Donatello_ACC_IIDM_M (chart + blocco Divide + feedback)
matlab/run_block_acciidm_m_test.m # NUOVO (Task 3): G3 (blocco vs model) + G4 (edge-trigger)
matlab/run_block_hdl_gate.m       # MODIFICA (Task 4): criterio M (VHDL + Divide pipelinato)
scripts/synth_acc_iidm.tcl        # RIUSO (Task 4): OOC -> RESULT/CRITPATH
document/SP4_ACC_IIDM_FAST.md     # MODIFICA (Task 5): sezione esito FSM
document/SESSION_RESUME.md        # MODIFICA (Task 5): stato
```

---

## Task 1: G1 — bit-identità del blocco Divide vs `divide()`-SP3 (MAKE-OR-BREAK)

**Files:** Modify `matlab/acc_iidm_open.m`; Create `matlab/collect_div_pairs.m`, `matlab/probe_divide_bitexact.m`;
riuso `scripts/synth_acc_iidm.tcl` (non in questo task).

> **Obiettivo:** rispondere a UNA domanda con la sintesi-verità: il blocco `Divide` HDL (ShiftAdd, rounding→'Zero',
> I/O `T.acc`) è **bit-identico** a `divide(numerictype(T.acc),num,den)` su **tutte** le coppie reali? Se sì, la FSM
> è bit-identica by construction; se no, STOP → fallback #2/#3. Le coppie sono **reali** (dal dataset), non
> sintetiche: il bug vive nelle code (lezione §2.1).

- [ ] **Step 1: trova il blocco `Divide` di HDL Coder e i suoi parametri**

Run (Bash, background non serve):
`"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "hdllib('off'); open_system('hdlcoderdivideandsqrtlib'); disp('---'); b='hdlcoderdivideandsqrtlib/Divide'; if getSimulinkBlockHandle(b)>0, disp(b); else, hdllib; end"`
Expected: conferma il **path del blocco `Divide`** (candidati: `hdlcoderdivideandsqrtlib/Divide`,
`hdlcoderoperationslib/Divide`). Annota il path esatto e i nomi dei parametri HDL (`Architecture='ShiftAdd'`,
`LatencyStrategy`, `IterationsPerPipeline`, `RoundingMethod` se esiste). Se `hdllib` apre la libreria, ispeziona il
blocco `Divide` sotto "Math"/"HDL Operations". **Questo path alimenta lo Step 3.**

- [ ] **Step 2: esponi le 5 coppie (num,den) reali da `acc_iidm_open` + collect sul dataset**

In `matlab/acc_iidm_open.m`: aggiungi un **output opzionale** `pairs` (5×2, `[num den]` di q1..q5) **senza cambiare
il calcolo** (backward-compat: `nargout<2` non lo produce). Modifica chirurgica — dopo ogni `acc_div` variabile,
salva `num,den` in una riga di `pairs`; ritorna `pairs` solo se `nargout>=2`. NON toccare la matematica esistente.

Poi `matlab/collect_div_pairs.m`:
```matlab
function P = collect_div_pairs(maxTraj)
%COLLECT_DIV_PAIRS  [SP4-M-FSM G1] Estrae le coppie (num,den) REALI che le 5 divisioni dell'ACC-IIDM fixed
%  assumono sul dataset. Riferimento: MEX(snn_core)+decode-64 -> acc_iidm_open fixed (la stessa catena di
%  run_block_acciidm_test). Ritorna P (M x 2) = [num den] impilate per tutte le divisioni/step/traiettorie.
  here = fileparts(mfilename('fullpath'));
  if nargin<1 || isempty(maxTraj), maxTraj = inf; end
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here,'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs = [champs{:}]; end
  c  = champs(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), champs),1));
  W  = champ_weights(c); Tp = numerictype(1,21,13); Tt = acc_types('fixed');
  nT = min(numel(tr), maxTraj);
  P = [];
  for t = 1:nT
    R = double(snn_traj_fixed_r16_mex(tr{t}.val, W));   % MEX: forward fixed
    val = double(fi(double(tr{t}.val),1,32,20));
    clear acc_iidm_open;                                 % stato OU pulito per traiettoria
    K = size(val,2);
    Pt = zeros(5*K,2);
    for k = 1:K
      p = double(snn_decode_lut(fi(R(k,:).',Tp),64));
      [~, pairs] = acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k), p, k==1, Tt);
      Pt((k-1)*5+(1:5), :) = double(pairs);
    end
    P = [P; Pt]; %#ok<AGROW>
  end
  fprintf('collect_div_pairs: %d coppie da %d traiettorie\n', size(P,1), nT);
end
```
Run (dry, 2 traj): `matlab -batch "cd('<matlabdir>'); P=collect_div_pairs(2); assert(all(isfinite(P(:)))); disp(size(P))`
Expected: `~10000  2` (2 traj × 1000 × 5), tutti finiti. Poi run completo salvato: `P=collect_div_pairs(); save('scratch_divpairs.mat','P')` → **~300k coppie**.

- [ ] **Step 3: scrivi `matlab/probe_divide_bitexact.m` (blocco Divide vs divide() sulle coppie)**

Costruisce un modello con le coppie in streaming attraverso il **blocco `Divide`** (path dallo Step 1, ShiftAdd,
rounding→'Zero', I/O `T.acc`) e confronta col riferimento `divide(numerictype(T.acc),num,den)` calcolato in MATLAB.
`assert(dmax==0)`.
```matlab
function dmax = probe_divide_bitexact(P, latStrategy, rounding)
%PROBE_DIVIDE_BITEXACT  [SP4-M-FSM G1, make-or-break] Il blocco Divide HDL e' bit-identico a divide()-SP3
%  sulle coppie reali P (Nx2)? Riferimento: divide(numerictype(T.acc),num,den) di Fixed-Point Designer.
%  latStrategy es. 'Max' | 'Custom(PerIteration)'; rounding es. 'Zero' (matcha SP3) | 'Nearest' (per la prova
%  di sensibilita': DEVE divergere).
  if nargin<2||isempty(latStrategy), latStrategy='Max'; end
  if nargin<3||isempty(rounding),    rounding='Zero';   end
  Tt = acc_types('fixed'); acc = Tt.acc;
  num = fi(P(:,1),'like',acc); den = fi(P(:,2),'like',acc);
  % riferimento SP3 (la STESSA divide del path fixed di acc_iidm_open):
  qref = divide(numerictype(acc), num, den);
  % blocco Divide in streaming: From Workspace (num,den) -> Divide -> To Workspace
  q_blk = run_divide_block(num, den, acc, latStrategy, rounding);   % helper sotto (usa il path Step 1)
  dmax = max(abs(double(q_blk) - double(qref)));
  fprintf('probe_divide_bitexact: %d coppie, lat=%s round=%s -> dmax = %.6g\n', numel(qref), latStrategy, rounding, dmax);
end
```
> **NOTA (esplorativo, come SP4-M config):** `run_divide_block` incapsula `add_block(<path Step1>)`,
> `hdlset_param(...,'LatencyStrategy',latStrategy)`, il `RoundingMethod`, e l'eventuale **pre-scaling** degli
> operandi (num/den nascono con tipi diversi — §spec: G1 determina il pre-scaling che rende il risultato ==
> `divide()`). Se il primo tentativo dà `dmax>0`, **la prima ipotesi da verificare è il pre-scaling/rounding**, non
> il blocco. Il messaggio d'errore vero di un mismatch di tipo si ha da `codegen`, non da Simulink.

- [ ] **Step 4: giro G1 e DECIDO (il verdetto)**

Run: `matlab -batch "cd('<matlabdir>'); load scratch_divpairs.mat P; dmax=probe_divide_bitexact(P,'Max','Zero'); assert(dmax==0, 'G1 FALLITO: blocco Divide != divide() (dmax=%.6g)', dmax); disp('G1 PASSATO')"`
Expected: `dmax = 0` su ~300k coppie → `G1 PASSATO`.
- **`dmax==0`** → il blocco Divide è un rimpiazzo bit-esatto → **Task 1 riuscito**, prosegui al Task 2. Annota
  `LatencyStrategy`/rounding/pre-scaling vincenti (li eredita il Task 3).
- **`dmax>0`** dopo aver escluso pre-scaling/rounding → **STOP**: G1 dice "blocco Divide non bit-identico". Documenta
  i numeri e **fermati** — il fallback #2 (divisore a mano) o #3 (ri-baselinare SP3) è un **piano a sé**, non
  improvvisato qui. Salta al Task 5 (doc dell'esito).

- [ ] **Step 5: prova di SENSIBILITÀ del gate (obbligatoria)**

Run: `matlab -batch "cd('<matlabdir>'); load scratch_divpairs.mat P; dN=probe_divide_bitexact(P,'Max','Nearest'); assert(dN>0, 'G1 NON SENSIBILE: anche Nearest da dmax=0 -> il gate non discrimina il rounding'); fprintf('sensibile: Nearest dmax=%.6g > 0\n', dN)"`
Expected: `Nearest` → `dmax > 0`. Se fosse 0, il gate **non prova nulla** (è il tipo di cecità del bug §2.1) → va
irrobustito prima di fidarsene.

- [ ] **Step 6: Commit**

```bash
git add matlab/acc_iidm_open.m matlab/collect_div_pairs.m matlab/probe_divide_bitexact.m
git commit -m "test(sp4-m-fsm): G1 bit-identita blocco Divide vs divide()-SP3 su coppie reali (make-or-break)"
```
(Verifica prima che `run_plant_parity` sia invariato: `matlab -batch "cd('<matlabdir>'); run_plant_parity"` →
`ALL PLANT PARITY PASS` — la modifica a `acc_iidm_open` è solo un output opzionale, il double non si muove.)

---

## Task 2: `acc_iidm_fsm.m` (model) + MEX + G2 (parità dataset)  — SOLO se Task 1 riuscito

**Files:** Create `matlab/acc_iidm_fsm.m`, `matlab/build_acc_iidm_fsm_mex.m`, `matlab/run_acciidm_m_dataset.m`

> `acc_iidm_fsm` è il **model single-source** della FSM: la matematica non-÷ come **funzioni locali copiate verbatim
> da `acc_iidm_open`** (stessi cast/tipi `acc_types`), l'ordine q1→q5, e `divide()` **inline** (non il blocco — qui è
> il model). Lo stesso file alimenterà la chart del blocco (Task 3) inlinandone le funzioni locali → single-source,
> difesa anti-§2.1. G2 prova che la ristrutturazione FSM non cambia il risultato.

- [ ] **Step 1: scrivi `matlab/acc_iidm_fsm.m`**

Struttura (codegen-safe, `%#codegen`): `function accel = acc_iidm_fsm(s,v,dv,v_l,p,rst,T)` che calcola l'IIDM come
`acc_iidm_open` **ma** con i risultati intermedi ottenuti nell'**ordine q1→q5** e i parziali in variabili tipizzate
`acc_types`. Le funzioni locali (guardie, `sab`, `s_safe`, `s_star`, `v_free`, `z`, `a_iidm`, `a_cah`, `a_blend`)
sono **copiate verbatim** da `acc_iidm_open` (stesse righe, stessi cast). La `divide()` resta inline
(`divide(numerictype(T.acc),num,den)`), come in `acc_div` con `recipN==0`. **Nessun cast che stringe un parziale
prima di usarlo** (bug §2.1). Output `accel` in `T.out`.
Verifica singola: `matlab -batch "cd('<matlabdir>'); T=acc_types('fixed'); a1=acc_iidm_fsm(10,6,2,4,[30 1.5 2 1.2 1.5].',true,T); a2=acc_iidm_open(10,6,2,4,[30 1.5 2 1.2 1.5].',true,T); fprintf('fsm=%.6g open=%.6g diff=%.3g\n',double(a1),double(a2),double(a1)-double(a2))"`
Expected: `diff = 0` (un caso; il dataset lo prova G2).

- [ ] **Step 2: MEX del model** — `matlab/build_acc_iidm_fsm_mex.m` (modello: `build_traj_mex.m`/`build_acc_sweep_mex.m`)

`codegen acc_iidm_fsm -args {0,0,0,0,zeros(5,1),true,acc_types('fixed')} -o acc_iidm_fsm_mex`. Run:
`matlab -batch "cd('<matlabdir>'); build_acc_iidm_fsm_mex; disp('mex ok')"` → `mex ok`.

- [ ] **Step 3: G2 — parità dataset** `matlab/run_acciidm_m_dataset.m`

Gira, sul **dataset intero** (60×1000): riferimento `acc_iidm_open` fixed vs `acc_iidm_fsm_mex`, **`assert dmax==0`**.
Modello: `run_block_acciidm_test` (per la catena MEX+decode) esteso a tutte le traiettorie, MA confronto **model vs
open** (nessun Simulink → veloce). Riporta *quanti su quanti*.
```matlab
function dmax = run_acciidm_m_dataset()
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here,'champions_export.mat')); champs = d.champions;
  if iscell(champs), champs=[champs{:}]; end
  c = champs(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'),champs),1));
  W = champ_weights(c); Tp = numerictype(1,21,13); Tt = acc_types('fixed');
  dmax = 0; nstep = 0;
  for t = 1:numel(tr)
    R = double(snn_traj_fixed_r16_mex(tr{t}.val, W));
    val = double(fi(double(tr{t}.val),1,32,20)); K = size(val,2);
    clear acc_iidm_open;                          % stato OU pulito
    for k = 1:K
      p = double(snn_decode_lut(fi(R(k,:).',Tp),64));
      aOpen = double(acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k),p,k==1,Tt));
      aFsm  = double(acc_iidm_fsm_mex(val(1,k),val(2,k),val(3,k),val(4,k),p,k==1,Tt));
      dmax = max(dmax, abs(aFsm-aOpen)); nstep = nstep+1;
    end
  end
  fprintf('G2 run_acciidm_m_dataset: dmax=%.6g su %d control-step (%d traj)\n', dmax, nstep, numel(tr));
  assert(dmax==0, 'G2 FALLITO: acc_iidm_fsm != acc_iidm_open (dmax=%.6g)', dmax);
  fprintf('=== G2 PASSATO: model FSM bit-identico al riferimento sul dataset ===\n');
end
```
Run: `matlab -batch "cd('<matlabdir>'); run_acciidm_m_dataset"` → `dmax=0 su 60000 control-step` → `G2 PASSATO`.
Sensibilità: temporaneamente inverti due divisioni (q2↔q3) → G2 **deve** fallire (prova che l'ordine conta); poi
ripristina.

- [ ] **Step 4: Commit**
```bash
git add matlab/acc_iidm_fsm.m matlab/build_acc_iidm_fsm_mex.m matlab/run_acciidm_m_dataset.m
git commit -m "feat(sp4-m-fsm): acc_iidm_fsm model + G2 parita dataset (0/60000 vs acc_iidm_open)"
```

---

## Task 3: blocco `Donatello_ACC_IIDM_M` + G3 (blocco vs model) + G4 (edge-trigger)

**Files:** Modify `matlab/build_hdl_variants.m`; Create `matlab/run_block_acciidm_m_test.m`

> Il subsystem = chart che **inlina le funzioni locali di `acc_iidm_fsm`** (single-source della matematica non-÷) +
> **1 blocco `Divide`** (config vincente del Task 1) + linee di feedback (`num/den/validIn → quot/validOut`). La chart
> emette gli operandi e consuma `quot` con l'handshake `validOut`; edge-trigger sull'ingresso (§3.1.4), niente
> `start` esposto (§3.1.2).

- [ ] **Step 1: costruisci il blocco in `build_hdl_variants.m`**

Dopo `Donatello_ACC_IIDM` (SP3), aggiungi `Donatello_ACC_IIDM_M`: subsystem con MATLAB Function `IIDM_CTRL` (chart
generata inlinando le funzioni locali di `acc_iidm_fsm` + la FSM di scheduling che dialoga col blocco Divide) + il
blocco `Divide` (path/config dal Task 1) + feedback. I/O fisico `s,v,dv,v_l → accel`. **La chart NON chiama `divide()`
sulle 5 divisioni variabili**: emette `(num,den,validIn)` e riceve `(quot,validOut)`. Rigenera la libreria.
Run: `matlab -batch "cd('<matlabdir>'); build_hdl_variants; disp('rigenerata')"` → `rigenerata`, 0 errori.
> Diagnosi errori chart: `codegen('-config:lib','IIDM_CTRL','-args',{a,a,a,a})` con `a=fi(0,1,32,20)` (Simulink
> stampa solo "Errors occurred during parsing").

- [ ] **Step 2: G3 + G4** — `matlab/run_block_acciidm_m_test.m` (modello: `run_block_acciidm_test.m`)

Estende `run_block_acciidm_test` al blocco `_M`: **G4** (latenza misurata + ingresso costante → **1 sola** inferenza,
`assert`; forzato-free-running deve fallire) e **G3** (blocco Simulink `_M` reale vs `acc_iidm_fsm_mex` su K
control-step in streaming, `assert dmax==0`, campionamento deterministico). Riusa `drive_acciidm` puntando a
`Donatello_ACC_IIDM_M`.
Run: `matlab -batch "cd('<matlabdir>'); for t=[1 6 12 20 30], run_block_acciidm_m_test(12,t,600); end"`
Expected: `latenza = <L> clock ; edge-triggered OK` e `dmax(accel)=0` su **5/5** traiettorie.
Sensibilità già coperta in G4 (free-running → fallisce).

- [ ] **Step 3: Commit**
```bash
git add matlab/build_hdl_variants.m matlab/snn_champions_lib.slx matlab/run_block_acciidm_m_test.m
git commit -m "feat(sp4-m-fsm): blocco Donatello_ACC_IIDM_M (FSM + Divide) + G3/G4 (dmax=0, edge-trigger)"
```

---

## Task 4: G5 (hdl gate) + G6 (OOC) — il verdetto Fmax

**Files:** Modify `matlab/run_block_hdl_gate.m`; riuso `scripts/synth_acc_iidm.tcl`

- [ ] **Step 1: G5 — hdl gate su `Donatello_ACC_IIDM_M`**

Estendi `run_block_hdl_gate` perché accetti `Donatello_ACC_IIDM_M`: criterio = VHDL generato dal solo `.slx` **+**
presenza dell'entità del **Divide pipelinato** (nome dallo Step 1 Task 1; non `DualPortRAM` come i blocchi SNN).
Run: `matlab -batch "cd('<matlabdir>'); run_block_hdl_gate('Donatello_ACC_IIDM_M')"` → `GATE PASSATO`.

- [ ] **Step 2: G6 — OOC (il verdetto)**

Genera il VHDL del blocco e sintetizza OOC (background). Modello: il loop del piano SP4-M config.
Run generazione: `matlab -batch "cd('<matlabdir>'); load_system('snn_champions_lib'); makehdl('snn_champions_lib/Donatello_ACC_IIDM_M','TargetLanguage','VHDL','TargetDirectory',fullfile(pwd,'hdl_sp4mfsm','m'),'GenerateHDLTestBench','off'); close_system('snn_champions_lib',0)"`
Run sintesi (background, log nello scratchpad):
`"C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat" -mode batch -notrace -source scripts/synth_acc_iidm.tcl -tclargs "matlab/hdl_sp4mfsm/m" "matlab/hdl_sp4mfsm/out" "fsm" | grep -E "^RESULT|^CRITPATH"`
Expected: `RESULT fsm LUT=… DSP=… Fmax=…` con **Fmax ≥ 11,65 MHz** e **LUT/FF ≪ M-config** (25557/22922). Confronta
con SP3 (baseline) e M-config. **Checkpoint utente** coi numeri prima di proseguire.
> Se `Fmax < 11,65`: **non aggirare**. Il collo è nel `CRITPATH` — se è ancora nel divisore, si alza
> `IterationsPerPipeline` (più stadi, path più corto) e si ri-sintetizza; se è nella logica non-÷, è un dato per il
> checkpoint. `.gitignore`: aggiungi `matlab/hdl_sp4mfsm/` se non coperto.

- [ ] **Step 3: Commit**
```bash
git add matlab/run_block_hdl_gate.m .gitignore
git commit -m "feat(sp4-m-fsm): G5 hdl gate esteso a _M + G6 OOC (Fmax=<misurato>, area vs M-config)"
```

---

## Task 5: doc + G7 + cancelli finali

**Files:** Modify `document/SP4_ACC_IIDM_FAST.md`, `document/SESSION_RESUME.md`

- [ ] **Step 1: G7 + cancelli finali (tutti verdi, sul dataset dove previsto)**

Run: `matlab -batch "cd('<matlabdir>'); run_plant_parity; run_acciidm_m_dataset; run_block_acciidm_m_test(12,1,600); run_block_hdl_gate('Donatello_ACC_IIDM_M'); run_block_hdl_gate('Donatello_Champion'); disp('>>>> VERDI <<<<')"`
Expected: `ALL PLANT PARITY PASS` (G7) · `G2 PASSATO` (0/60000) · `dmax=0` (G3/G4) · `GATE PASSATO` ×2 · `VERDI`.

- [ ] **Step 2: aggiorna `document/SP4_ACC_IIDM_FAST.md`**

Aggiungi **`### Variante M — FSM + blocco Divide (esito)`**: meccanismo (FSM + Divide pipelinato ShiftAdd),
config vincente del Task 1 (LatencyStrategy/pre-scaling), tabella OOC `SP3` vs `M-config` vs `M-FSM`
(LUT/FF/DSP/Fmax/CRITPATH), verdetto (11,65 centrato? area vs M-config?), e le parità G1/G2/G3 (*quanti su quanti*).
Numeri VERI dai Task 1-4.

- [ ] **Step 3: aggiorna `document/SESSION_RESUME.md`** (blocco ▶ + sezione `## SP4`): da "FSM = prossimo piano" a
"M-FSM fatto (Fmax=…, area…, dmax=0)" **oppure** "G1 fallito → fallback #2/#3 = prossimo piano".

- [ ] **Step 4: Commit + push**
```bash
git add document/SP4_ACC_IIDM_FAST.md document/SESSION_RESUME.md
git commit -m "docs(sp4-m-fsm): esito FSM + blocco Divide (Fmax, area, bit-identita) + stato"
git push origin Simulink_Importer
```

---

## Self-review (copertura della spec)
- **§1 scopo** (Fmax≥11,65 + area giù + dmax=0): Task 4 G6 (Fmax/area) + Task 1-3 G1/G2/G3 (dmax=0). ✓
- **§3 approccio** (blocco Divide ShiftAdd, gate bit-identità PRIMA): Task 1 = make-or-break G1. ✓
- **§4 architettura** (IIDM_CTRL + 1 Divide + feedback, no start, edge-trigger): Task 3 Step 1 + G4. ✓
- **§5 data flow** (q1→q5, validOut, DT inline, budget 341): Task 2 (ordine nel model) + Task 3 (handshake). ✓
- **§6 batteria G1-G7 + transitività + anti-§2.1 (single-source, MEX, tipi)**: G1 T1 · G2 T2 · G3/G4 T3 · G5/G6 T4 ·
  G7 T5; single-source = funzioni locali condivise (T2→T3); MEX per il dataset (T2); disciplina tipi (T2 Step1). ✓
- **§7 file**: tutti i file dello spec hanno un task. ✓
- **§8 ordine** (Task 1 make-or-break, STOP se fallisce): Task 1 Step 4. ✓
- **§9 fuori scope** (overlap, slack, bitstream, promozione deploy, v2): nessun task li tocca. ✓
- **Coerenza nomi**: `acc_iidm_fsm`/`acc_iidm_fsm_mex` · `Donatello_ACC_IIDM_M` · `run_acciidm_m_dataset` ·
  `run_block_acciidm_m_test` · `probe_divide_bitexact` · G1..G7 — usati coerentemente in tutti i task. ✓
```
