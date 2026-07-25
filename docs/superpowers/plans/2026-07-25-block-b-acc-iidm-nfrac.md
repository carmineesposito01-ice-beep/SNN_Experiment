# Blocco B — ACC-IIDM standalone + studio NFRAC — Piano d'implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Caratterizzare il compromesso precisione↔sicurezza↔hardware del controllore ACC-IIDM al variare di `nfrac` (studio SPECCHIATO dell'estimator, SNN congelata / IIDM che varia) e produrre un blocco di libreria `ACC-IIDM` standalone, HDL-ready, con menu NFRAC.

**Architecture:** Studio isolato in `matlab/Quantizzation_Study_IIDM/` (prefisso `qzi_`), che RIUSA l'anello fedele `qz_cl_sim`, le metriche `qz_safety_metrics`, il dataset esaustivo e l'harness di sintesi dell'estimator. L'IIDM in fixed a `nfrac` è già type-parametrico via `acc_iidm_open(...,acc_types('fixed',nfrac))`; l'FSM HDL `acc_iidm_fsm` cuoce `acc_types('fixed')` dentro, quindi per il blocco/hardware l'`nfrac` va **cotto concreto per variante** (sostituzione di sorgente, come il menu NFRAC dell'estimator). Il report diventa una **sezione** del report esistente.

**Tech Stack:** MATLAB R2026a (`/c/Program Files/MATLAB/R2026a/bin/matlab.exe`), MATLAB Coder (MEX per lo sweep, `coder.Constant` per nfrac), HDL Coder + Vivado 2026.1 (`C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat`, sintesi OOC io-timed 125 ns), Python base (`/c/Miniconda/python.exe`, matplotlib+reportlab+fitz) per il report.

---

## Convenzioni operative (valgono per tutti i task)

- **Commit**: messaggi convenzionali, SENZA `Co-Authored-By`. Push SOLO su richiesta.
- **Core intatto**: `acc_iidm_open.m`, `acc_iidm_fsm.m` e le funzioni-fase `iidm_*.m` / `fsm_div.m` NON si modificano in-place. Le varianti nfrac si ottengono per **sostituzione su COPIA** (temp dir o sorgente inlinato).
- **NON toccare**: `closed_loop_demo.slx`, `slblocks.m`, i `*.mexw64` committati, `test_dataset.mat` (il globale, 20+ cancelli).
- **MATLAB lungo in background**: gli sweep in `fi` interpretato costano ~10 ms/chiamata → il dataset intero è ~ore. Si lancia il comando MATLAB con `run_in_background` e si legge il file di output alla notifica; NON ridurre il campione per stare in un timeout (regola: dataset intero). Dove serve velocità, MEX per nfrac (il tipo è compile-time).
- **Un cancello si prova nei due sensi**: deve accettare il caso vero E rifiutare un falso. Un floor/gate mai visto fallire non è un cancello.
- **Isolamento**: tutto lo studio vive in `matlab/Quantizzation_Study_IIDM/`. Il blocco vive in `snn_champions_lib.slx` (la libreria).
- **Path Windows per MATLAB**: quando uno `.sh` passa path ad `addpath`, convertire POSIX→Windows (`cygpath -w` o `/d/..`→`D:/..`), altrimenti MATLAB legge `D:\d\..` e fallisce in silenzio (lezione dell'harness estimator).

---

## File Structure

Tutto nuovo salvo dove indicato "Modify". I file dell'estimator (`Quantizzation_Study/`) sono il template da specchiare, NON si toccano.

| File | Responsabilità |
|---|---|
| `matlab/Quantizzation_Study_IIDM/qzi_cl_step.m` | UN control-step: SNN **congelata @13** (forward full-precision) → decode LUT-64 → `acc_iidm_open` a **nfrac IIDM parametrico**. Ritorna `[p, accel]`. Copia di `qz_snn_cl_step` con SNN fissa a 13 e nfrac che pilota l'IIDM. |
| `matlab/Quantizzation_Study_IIDM/qzi_cl_validate.m` | Studio closed-loop: safety (coll_extra vs oracolo) + fedeltà NRMSE(accel) vs nfrac=13, su dataset esaustivo. Scrive `qzi_cl_sweep.tsv`. Specchio di `qz_cl_validate`. |
| `matlab/Quantizzation_Study_IIDM/qzi_cl_severity.m` | Severità impact_dv sugli inevitabili, per nfrac. Scrive `qzi_sev_sweep.tsv`. Specchio di `qz_cl_severity`. |
| `matlab/Quantizzation_Study_IIDM/qzi_acc_sweep.m` | Studio open-loop: fedeltà NRMSE(accel) + accuratezza max\|d\|(accel) IIDM fixed@nfrac vs IIDM double, stessi ingressi golden. Scrive `qzi_acc_sweep.tsv`. Specchio esteso di `run_acc_fixed_sweep`. |
| `matlab/Quantizzation_Study_IIDM/qzi_iidm_variant_src.m` | Abilitatore: scrive in una temp dir copie di `acc_iidm_fsm.m`+`iidm_*.m`+`fsm_div.m` con `acc_types('fixed')`→`acc_types('fixed',nfrac)`. Ritorna il path della temp dir. Usato da gate/hardware/blocco. |
| `matlab/Quantizzation_Study_IIDM/qzi_enabler_gate.m` | Cancello G0/G1: l'FSM a nfrac cotto == `acc_iidm_open(...,acc_types('fixed',nfrac))` (dmax=0 su dataset); nfrac morde ai bit bassi (controllo negativo). |
| `matlab/Quantizzation_Study_IIDM/qzi_gen_iidm_vhdl.m` | Genera VHDL dell'FSM IIDM a nfrac (via la path HDL provata di `build_hdl_variants` + sorgenti dalla temp dir dell'abilitatore). |
| `matlab/Quantizzation_Study_IIDM/qzi_synth.sh` | Harness Vivado: per ogni nfrac in `qzi_synth_set.txt` genera VHDL + sintesi OOC io-timed 125 ns → `qzi_res_sweep.tsv`. Specchio di `qz_sweep_nfrac.sh`. |
| `matlab/Quantizzation_Study_IIDM/qzi_synth_set.txt` | Insieme nfrac da sintetizzare: `13 8 5 2`. |
| `matlab/build_acc_iidm_block.m` | Costruisce il blocco `ACC-IIDM` in `snn_champions_lib.slx`: Variant Subsystem con 4 varianti nfrac (chart FSM a nfrac cotto), mask popup NFRAC, arrangeSystem, pulizia stray. Specchio di `build_tier_configurable`. |
| `matlab/Quantizzation_Study_IIDM/qzi_block_gate.m` | Cancello G3/G4: blocco no-regressione (default streama == riferimento, dmax=0), 4 varianti compilano, makehdl da una variante → VHDL. |
| `scripts/build_quantization_report.py` | **Modify**: loader `qzi_*.tsv` + 2 figure IIDM + nuova sezione "§N Quantizzazione del controllore IIDM"; cornice allargata a "sistema car-following". |
| `matlab/Quantizzation_Study/QZ_CARFOLLOWING_STUDY.md` | **Modify**: nuova sezione §13 (sorgente della sezione report). |
| `report/QUANTIZATION_STUDY_REPORT.{md,pdf}` | **Modify (rigenerato)**: contiene la sezione IIDM. |

Dati committati (output): `qzi_cl_sweep.tsv`, `qzi_sev_sweep.tsv`, `qzi_acc_sweep.tsv`, `qzi_res_sweep.tsv`.

---

## Task 1: Studio closed-loop — safety + fedeltà (specchio di `qz_cl_validate`)

**Files:**
- Create: `matlab/Quantizzation_Study_IIDM/qzi_cl_step.m`
- Create: `matlab/Quantizzation_Study_IIDM/qzi_cl_validate.m`
- Output: `matlab/Quantizzation_Study_IIDM/qzi_cl_sweep.tsv`

Contesto: l'anello `qz_cl_sim(traj, stepFun)` chiama `stepFun(x_phys,rst)->[p,accel]` una volta per control-step; `x_phys=[s;v;dv;vl]`. L'oracolo (baseline) usa `gt_params` + IIDM double. Per lo studio IIDM la rete è **congelata** e varia solo l'nfrac dell'IIDM.

- [ ] **Step 1: Scrivi lo step con SNN congelata @13 e IIDM a nfrac parametrico**

Create `matlab/Quantizzation_Study_IIDM/qzi_cl_step.m`:

```matlab
function [p, accel] = qzi_cl_step(x_phys, W, rst, nfrac) %#codegen
%QZI_CL_STEP  [Quantizzation_Study_IIDM] UN control-step per lo studio SPECCHIATO:
%  la SNN e' CONGELATA a piena precisione (fixed nfrac=13) e varia SOLO l'nfrac dell'IIDM.
%  normalize (float) -> snn_core (fixed@13) -> decode LUT-64 -> acc_iidm_open (IIDM a nfrac).
%  Specchio di qz_snn_cl_step: li' l'nfrac pilotava la RETE (IIDM fisso@8); qui pilota l'IIDM
%  (RETE fissa@13). nfrac e' coder.Constant nel MEX.
  T = snn_types('fixed', 13);                          % SNN congelata: piena precisione
  if rst
    snn_core(cast(zeros(4, 1), 'like', T.V), W, T, true);
  end
  xn  = cast(snn_normalize(x_phys, W.norm), 'like', T.V);
  raw = snn_core(xn, W, T, false);
  pf  = snn_decode_lut(raw, 64);
  p   = double(pf(:));
  accel = double(acc_iidm_open(x_phys(1), x_phys(2), x_phys(3), x_phys(4), ...
                               p, rst, acc_types('fixed', nfrac)));   % IIDM a nfrac
end
```

- [ ] **Step 2: Scrivi lo studio closed-loop (safety + NRMSE accel), specchio di `qz_cl_validate`**

Create `matlab/Quantizzation_Study_IIDM/qzi_cl_validate.m`. È `qz_cl_validate` con: MEX di `qzi_cl_step` (non `qz_snn_cl_step`); NRMSE calcolato sull'**accel** (`o.series.a`) invece che sui 5 parametri; riferimento nfrac=13 dell'IIDM. La griglia default è quella dello studio: `[13 8 5 2]`.

```matlab
function qzi_cl_validate(levels, trajList)
%QZI_CL_VALIDATE  [Quantizzation_Study_IIDM] Studio SPECCHIATO in anello chiuso fedele (qz_cl_sim),
%  SNN congelata @13, IIDM a nfrac. Su dataset esaustivo, per ogni nfrac:
%   - SICUREZZA vs baseline ORACOLO per-traiettoria (gt_params): coll_extra = collisioni che
%     l'oracolo evita ma la rete+IIDM-quantizzato no -> costo reale della quantizzazione IIDM.
%   - FEDELTA': NRMSE dell'ACCEL (uscita IIDM) vs riferimento IIDM nfrac=13.
%  Anello provato fedele (qz_cl_parity_gate). Ingressi NON quantizzati (come simulate).
  if nargin < 1 || isempty(levels),   levels   = [13 8 5 2]; end
  if nargin < 2 || isempty(trajList), trajList = []; end
  here  = fileparts(mfilename('fullpath')); mroot = fileparts(here);
  qzdir = fullfile(mroot, 'Quantizzation_Study');           % dataset + funzioni condivise
  addpath(mroot); addpath(here); addpath(qzdir);
  dd = load(fullfile(mroot,'champions_export.mat')); ch = dd.champions; if iscell(ch), ch=[ch{:}]; end
  c  = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1)); W = champ_weights(c);
  ds = load(fullfile(qzdir,'test_dataset_exhaustive.mat')); tr = ds.trajectories;
  if isempty(trajList), trajList = 1:numel(tr); end
  T = tr(trajList); nt = numel(T);
  names = cellfun(@(x) x.name, T, 'UniformOutput', false);

  % --- 0) baseline ORACOLO: cosa e' fisicamente evitabile (gt_params + IIDM double) ---
  oracle = @(gtp) @(x,rst) deal(gtp(:), ...
      double(acc_iidm_open(x(1),x(2),x(3),x(4), gtp(:), rst, acc_types('double'))));
  Bcoll = false(1,nt);
  for i = 1:nt, o = qz_cl_sim(T{i}, oracle(T{i}.gt_params)); Bcoll(i) = o.collided; end
  avoid = ~Bcoll;
  fprintf('baseline oracolo: %d/%d traiettorie inevitabili\n', sum(Bcoll), nt);

  % --- 1) MEX per ogni livello IIDM (se manca) ---
  cfg = coder.config('mex'); cfg.GenerateReport = false;
  oldd = cd(here); cu = onCleanup(@() cd(oldd)); %#ok<NASGU>
  for f = levels
    mx = sprintf('qzi_cl_step_n%d_mex', f);
    if isempty(which(mx))
      fprintf('build %s ...\n', mx);
      codegen('qzi_cl_step','-config',cfg, ...
              '-args',{zeros(4,1),coder.typeof(W),true,coder.Constant(f)}, ...
              '-o',mx,'-d',['codegen_ni' num2str(f)]);
    end
  end

  % --- 2) riferimento IIDM nfrac=13 (accel per NRMSE) ---
  assert(ismember(13,levels), 'serve nfrac=13 come riferimento NRMSE');
  fun13 = str2func('qzi_cl_step_n13_mex');
  Aref = cell(1,nt);
  for i = 1:nt, o = qz_cl_sim(T{i}, @(x,rst) fun13(x,W,rst,13)); Aref{i} = o.series.a(:); end
  allA = cell2mat(Aref(:)); arng = max(allA) - min(allA); if arng==0, arng = 1; end

  % --- 3) sweep livelli ---
  rows = [];
  extraNamesByLevel = containers.Map('KeyType','double','ValueType','any');
  for f = levels
    fun = str2func(sprintf('qzi_cl_step_n%d_mex', f));
    coll = false(1,nt); mg = zeros(1,nt); bm = zeros(1,nt); dr = zeros(1,nt);
    num = 0; den = 0;
    for i = 1:nt
      o = qz_cl_sim(T{i}, @(x,rst) fun(x,W,rst,f));
      m = qz_safety_metrics(o.series, o.collided, o.min_gap, o.impact_dv);
      coll(i)=m.collided; mg(i)=m.min_gap; bm(i)=m.brake_margin_min; dr(i)=m.max_DRAC;
      Af = o.series.a(:); Ar = Aref{i}; n = min(numel(Af), numel(Ar));
      num = num + sum((Af(1:n) - Ar(1:n)).^2); den = den + n;
    end
    nrmse = sqrt(num/den) / arng;
    extra = coll & ~Bcoll;
    mgA = mg(avoid); bmA = bm(avoid);
    rows(end+1,:) = [f, sum(coll), sum(extra), min([mgA, inf]), min([bmA, inf]), max([dr,0]), nrmse]; %#ok<AGROW>
    extraNamesByLevel(f) = names(extra);
    fprintf('nfrac=%2d: coll_tot=%d coll_extra=%d NRMSE_accel=%.4f\n', f, sum(coll), sum(extra), nrmse);
  end

  % --- 4) tabella + TSV ---
  rows = sortrows(rows, 1);
  fid = fopen(fullfile(here,'qzi_cl_sweep.tsv'),'w');
  fprintf(fid,'nfrac\tcoll_total\tcoll_extra\tmin_gap_avoid\tbrake_margin_avoid\tmax_DRAC\tNRMSE_accel\n');
  for r = 1:size(rows,1)
    v = rows(r,:);
    fprintf(fid,'%d\t%d\t%d\t%.4f\t%.4f\t%.4f\t%.6g\n', v(1),v(2),v(3),v(4),v(5),v(6),v(7));
  end
  fclose(fid);
  fprintf('scritto %s\n', fullfile(here,'qzi_cl_sweep.tsv'));
end
```

- [ ] **Step 3: Esegui lo studio (background) e verifica il cancello G2 nei due sensi**

Lancia (background — build 4 MEX + anello su 99 traj × 4 livelli):

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "addpath('Quantizzation_Study_IIDM'); qzi_cl_validate" > /tmp/qzi_cl.log 2>&1
```

Alla notifica, leggi `/tmp/qzi_cl.log` e `Quantizzation_Study_IIDM/qzi_cl_sweep.tsv`.
Atteso (cancello G2, DUE sensi):
- **Accetta il vero**: a nfrac=13 `coll_extra=0` e `NRMSE_accel=0` (riferimento con sé stesso).
- **Rileva la degradazione**: `NRMSE_accel` cresce monotòno al scendere di nfrac (13→2); il rilevatore *distingue* i livelli (non tutti 0).
- **Sicurezza**: `coll_extra` riportato per ogni livello (atteso 0 fin giù, coerente con l'estimator; se >0 a 5/2, è il dato che escluderà quei livelli dal menu del blocco).

Se `NRMSE_accel` è 0 ovunque → il rilevatore non morde (bug): l'accel non varia tra i livelli, controlla che `acc_types('fixed',nfrac)` sia effettivamente passato (Step 1).

- [ ] **Step 4: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/Quantizzation_Study_IIDM/qzi_cl_step.m matlab/Quantizzation_Study_IIDM/qzi_cl_validate.m matlab/Quantizzation_Study_IIDM/qzi_cl_sweep.tsv
git commit -m "feat(block-b): studio IIDM closed-loop — safety + fedelta NRMSE(accel) vs nfrac

Specchio di qz_cl_validate: SNN congelata @13, IIDM a nfrac {13,8,5,2}. coll_extra vs oracolo
(gt_params) + NRMSE dell'accel vs riferimento IIDM nfrac=13, su dataset esaustivo (99 traj).
Cancello G2 nei due sensi: nfrac=13 -> 0/0; degrada misurabile al scendere dei bit."
```

---

## Task 2: Studio open-loop — fedeltà + accuratezza accel (specchio di `run_acc_fixed_sweep`)

**Files:**
- Create: `matlab/Quantizzation_Study_IIDM/qzi_acc_sweep.m`
- Create: `matlab/Quantizzation_Study_IIDM/qzi_sev_sweep` (via `qzi_cl_severity.m`)
- Create: `matlab/Quantizzation_Study_IIDM/qzi_cl_severity.m`
- Output: `matlab/Quantizzation_Study_IIDM/qzi_acc_sweep.tsv`, `qzi_sev_sweep.tsv`

Contesto: `run_acc_fixed_sweep` misura già `E_iidm(nfrac) = |accel(IIDM fixed@nfrac) - accel(IIDM double)|` a parità di parametri, sul dataset intero. Questa è la fedeltà PULITA (open-loop, ingressi identici). La estendiamo per scrivere anche NRMSE e max|d| dell'accel su un TSV.

- [ ] **Step 1: Scrivi lo sweep open-loop accel → TSV con NRMSE e max|d|**

Create `matlab/Quantizzation_Study_IIDM/qzi_acc_sweep.m`. Riusa il kernel di `run_acc_fixed_sweep` (SNN fixed@13 via `snn_traj_fixed_r16_mex` → params → IIDM double vs fixed@nfrac), ma raccoglie l'errore per calcolare NRMSE + max|d| e scrive il TSV.

```matlab
function qzi_acc_sweep(fracs, nTraj)
%QZI_ACC_SWEEP  [Quantizzation_Study_IIDM] Fedelta' OPEN-LOOP dell'IIDM: a parita' di parametri (dalla
%  SNN congelata fixed@13), accel(IIDM fixed@nfrac) vs accel(IIDM double), sul dataset INTERO.
%  Metriche sull'ACCEL: NRMSE (normalizzata sull'escursione) + max|d| (worst-case). Specchia il kernel
%  di run_acc_fixed_sweep (che misura il budget E_iidm) e ne scrive lo sweep in qzi_acc_sweep.tsv.
%  LENTO PER COSTRUZIONE (fi interpretato): lanciare in background, NON ridurre il campione.
  if nargin < 1 || isempty(fracs), fracs = [13 8 5 2]; end
  if nargin < 2 || isempty(nTraj), nTraj = 60; end
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here);
  addpath(mroot);
  ds = load(fullfile(mroot,'test_dataset.mat')); tr = ds.trajectories;      % 60 traj (come SP3)
  d  = load(fullfile(mroot,'champions_export.mat')); ch = d.champions; if iscell(ch), ch=[ch{:}]; end
  c  = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1));
  W  = champ_weights(c); Tp = numerictype(1,21,13); Td = acc_types('double');
  nTraj = min(nTraj, numel(tr));

  rows = zeros(numel(fracs), 3);   % nfrac, nrmse, maxd
  fprintf('%-6s %13s %13s\n','nfrac','NRMSE_accel','max|d|_accel');
  for j = 1:numel(fracs)
    Tf = acc_types('fixed', fracs(j)); num = 0; den = 0; mx = 0;
    for i = 1:nTraj
      val = double(tr{i}.val);
      R = double(snn_traj_fixed_r16_mex(val, W));
      P = zeros(size(val,2),5);
      for k = 1:size(val,2), P(k,:) = double(snn_decode_lut(fi(R(k,:).', Tp), 64)).'; end
      clear acc_iidm_open; aD = zeros(size(val,2),1);
      for k = 1:size(val,2)
        aD(k) = acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k), P(k,:).', k==1, Td);
      end
      clear acc_iidm_open; aF = zeros(size(val,2),1);
      for k = 1:size(val,2)
        aF(k) = double(acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k), P(k,:).', k==1, Tf));
      end
      num = num + sum((aF-aD).^2); den = den + numel(aD); mx = max(mx, max(abs(aF-aD)));
    end
    % escursione dell'accel di riferimento sul dataset: usa il range fisico clampato [-9, a<=2.5]
    arng = 9 + 2.5;    % coerente con acc_types out (clamp [-9, a]); costante -> normalizzazione stabile
    rows(j,:) = [fracs(j), sqrt(num/den)/arng, mx];
    fprintf('%-6d %13.6g %13.6g\n', fracs(j), rows(j,2), rows(j,3));
  end

  fid = fopen(fullfile(here,'qzi_acc_sweep.tsv'),'w');
  fprintf(fid,'nfrac\tNRMSE_accel\tmaxd_accel\n');
  for j = 1:numel(fracs), fprintf(fid,'%d\t%.6g\t%.6g\n', rows(j,1), rows(j,2), rows(j,3)); end
  fclose(fid);
  fprintf('scritto %s\n', fullfile(here,'qzi_acc_sweep.tsv'));
end
```

- [ ] **Step 2: Scrivi lo sweep di severità (specchio di `qz_cl_severity`)**

Create `matlab/Quantizzation_Study_IIDM/qzi_cl_severity.m`: è `qz_cl_severity` con la funzione-rete sostituita da `qzi_cl_step_n%d_mex` (SNN@13, IIDM a nfrac) e i livelli `[13 8 5 2]`; scrive `qzi_sev_sweep.tsv`.

```matlab
function qzi_cl_severity(levels)
%QZI_CL_SEVERITY  [Quantizzation_Study_IIDM] Severita' specchiata: sugli inevitabili (l'oracolo collide),
%  l'IIDM quantizzato schianta piu' forte al scendere dei bit? Metrica impact_dv [m/s]. SNN congelata @13.
  if nargin < 1 || isempty(levels), levels = [13 8 5 2]; end
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here);
  qzdir = fullfile(mroot,'Quantizzation_Study'); addpath(mroot); addpath(here); addpath(qzdir);
  dd = load(fullfile(mroot,'champions_export.mat')); ch = dd.champions; if iscell(ch), ch=[ch{:}]; end
  c  = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1)); W = champ_weights(c);
  ds = load(fullfile(qzdir,'test_dataset_exhaustive.mat')); tr = ds.trajectories; nt = numel(tr);
  oracle = @(gtp) @(x,rst) deal(gtp(:), ...
      double(acc_iidm_open(x(1),x(2),x(3),x(4), gtp(:), rst, acc_types('double'))));
  inev = []; oimp = [];
  for i = 1:nt
    o = qz_cl_sim(tr{i}, oracle(tr{i}.gt_params));
    if o.collided, inev(end+1)=i; oimp(end+1)=o.impact_dv; end %#ok<AGROW>
  end
  fprintf('inevitabili (oracolo collide): %d\n', numel(inev));

  IMP = zeros(numel(inev), numel(levels));
  for li = 1:numel(levels)
    f = levels(li); fun = str2func(sprintf('qzi_cl_step_n%d_mex', f));   % MEX gia' costruiti dal Task 1
    for j = 1:numel(inev)
      o = qz_cl_sim(tr{inev(j)}, @(x,rst) fun(x,W,rst,f));
      IMP(j,li) = o.impact_dv;
    end
  end
  fid = fopen(fullfile(here,'qzi_sev_sweep.tsv'),'w'); fprintf(fid,'nfrac\tmax_impact_dv\toracle_max\n');
  for li = 1:numel(levels)
    mx = max([IMP(:,li); 0]);
    fprintf('nfrac=%2d max_impact=%.2f (oracolo=%.2f)\n', levels(li), mx, max([oimp 0]));
    fprintf(fid,'%d\t%.4f\t%.4f\n', levels(li), mx, max([oimp 0]));
  end
  fclose(fid);
  fprintf('scritto %s\n', fullfile(here,'qzi_sev_sweep.tsv'));
end
```

- [ ] **Step 3: Esegui i due sweep (background) e verifica**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "addpath('Quantizzation_Study_IIDM'); qzi_acc_sweep; qzi_cl_severity" > /tmp/qzi_acc.log 2>&1
```

Alla notifica, leggi `/tmp/qzi_acc.log`, `qzi_acc_sweep.tsv`, `qzi_sev_sweep.tsv`.
Atteso:
- `qzi_acc_sweep.tsv`: a nfrac=13 NRMSE≈0 e max|d|≈0; crescono al scendere dei bit (fedeltà degrada — accetta vero / rifiuta falso).
- `qzi_sev_sweep.tsv`: `max_impact_dv` ≈ `oracle_max` a tutti i livelli (la quantizzazione NON aggiunge severità dove la collisione è comunque inevitabile) — coerente con l'estimator.

- [ ] **Step 4: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/Quantizzation_Study_IIDM/qzi_acc_sweep.m matlab/Quantizzation_Study_IIDM/qzi_cl_severity.m matlab/Quantizzation_Study_IIDM/qzi_acc_sweep.tsv matlab/Quantizzation_Study_IIDM/qzi_sev_sweep.tsv
git commit -m "feat(block-b): studio IIDM open-loop (NRMSE+max|d| accel) + severita

qzi_acc_sweep specchia il kernel di run_acc_fixed_sweep (IIDM fixed@nfrac vs double, params dalla
SNN@13) e ne scrive NRMSE+max|d| accel. qzi_cl_severity specchia qz_cl_severity (impact_dv sugli
inevitabili). Dataset intero, livelli {13,8,5,2}."
```

---

## Task 3: Abilitatore — nfrac cotto nell'FSM IIDM (per hardware + blocco)

**Files:**
- Create: `matlab/Quantizzation_Study_IIDM/qzi_iidm_variant_src.m`
- Create: `matlab/Quantizzation_Study_IIDM/qzi_enabler_gate.m`

Contesto: `acc_iidm_fsm.m` e le funzioni-fase `iidm_*.m`/`fsm_div.m` cuociono `acc_types('fixed')` (default nfrac=8) DENTRO, per un vincolo HDL Coder (§6 spec). Per generare l'FSM ad altri nfrac serve **cuocere il valore concreto**. La tecnica: copie con sostituzione `acc_types('fixed')`→`acc_types('fixed',nfrac)`, mantenendo i NOMI originali → precedenza di path per il gate MATLAB, sorgenti inlinati per VHDL/blocco. Prima si prova la sostituzione bit-exact al livello MATLAB (cheap), poi la si usa in Vivado/Simulink.

- [ ] **Step 1: Scrivi l'abilitatore (copie sostituite in temp dir, nomi invariati)**

Create `matlab/Quantizzation_Study_IIDM/qzi_iidm_variant_src.m`:

```matlab
function td = qzi_iidm_variant_src(nfrac)
%QZI_IIDM_VARIANT_SRC  [Quantizzation_Study_IIDM] Abilitatore: scrive in una temp dir copie di
%  acc_iidm_fsm.m + iidm_*.m + fsm_div.m con acc_types('fixed') -> acc_types('fixed',NFRAC), MANTENENDO
%  i nomi originali. Prependendo la temp dir al path, acc_iidm_fsm risolve alle copie -> l'FSM gira a
%  NFRAC senza toccare gli originali. Ritorna il path della temp dir (il chiamante fa addpath/rmpath).
%  Scopre i file da sostituire per GREP (non lista hardcoded): un file dimenticato sarebbe silenzioso.
  assert(isscalar(nfrac) && nfrac==round(nfrac) && nfrac>=2 && nfrac<=13, 'nfrac in [2,13]');
  mroot = fileparts(fileparts(mfilename('fullpath')));        % .../matlab
  cand = [ {fullfile(mroot,'acc_iidm_fsm.m'), fullfile(mroot,'fsm_div.m')}, ...
           cellfun(@(f) fullfile(mroot,f), ...
                   arrayfun(@(d) d.name, dir(fullfile(mroot,'iidm_*.m')), 'UniformOutput',false).', ...
                   'UniformOutput',false) ];
  td = fullfile(tempdir, sprintf('qzi_iidm_n%d_%s', nfrac, 'src'));
  if exist(td,'dir'), rmdir(td,'s'); end; mkdir(td);
  pat = 'acc_types(''fixed'')';
  rep = sprintf('acc_types(''fixed'', %d)', nfrac);
  nsub = 0;
  for i = 1:numel(cand)
    if ~exist(cand{i},'file'), continue; end
    src = fileread(cand{i});
    if contains(src, pat)
      src = strrep(src, pat, rep); nsub = nsub + 1;
    end
    [~, nm, ext] = fileparts(cand{i});
    fid = fopen(fullfile(td, [nm ext]), 'w'); fwrite(fid, src); fclose(fid);
  end
  assert(nsub >= 1, 'nessuna sostituzione acc_types(''fixed'') applicata: pattern cambiato?');
  fprintf('qzi_iidm_variant_src: nfrac=%d, %d file sostituiti -> %s\n', nfrac, nsub, td);
end
```

- [ ] **Step 2: Scrivi il cancello abilitatore G0/G1 (bit-exact + morde), specchio della disciplina G2 dell'FSM**

Create `matlab/Quantizzation_Study_IIDM/qzi_enabler_gate.m`:

```matlab
function qzi_enabler_gate()
%QZI_ENABLER_GATE  [Quantizzation_Study_IIDM] Prova l'abilitatore nei DUE sensi, al livello MATLAB
%  (cheap, prima di Vivado):
%   G1  - a ogni nfrac, l'FSM a nfrac COTTO (copie di qzi_iidm_variant_src) == acc_iidm_open con
%         acc_types('fixed',nfrac), dmax=0 sul dataset intero (stessa disciplina del G2 storico
%         di acc_iidm_fsm, ma parametrico in nfrac).
%   G0  - a nfrac=8 l'FSM cotto == acc_iidm_fsm ORIGINALE (dmax=0): la sostituzione a default e' un no-op.
%   MORDE - a nfrac=2 l'accel differisce da nfrac=13 (controllo negativo: se non morde, non e' un cancello).
  mroot = fileparts(fileparts(mfilename('fullpath')));
  qz = fullfile(mroot,'Quantizzation_Study'); addpath(mroot); addpath(qz);
  ds = load(fullfile(qz,'test_dataset_exhaustive.mat')); tr = ds.trajectories; nt = numel(tr);
  Td = acc_types('double');

  runFSM = @(fun) local_run_all(fun, tr, nt);          % accel dell'FSM su tutto il dataset
  runOpen = @(nf) local_run_all(@(s,v,dv,vl,p,rst) ...
      double(acc_iidm_open(s,v,dv,vl,p,rst,acc_types('fixed',nf))), tr, nt, true);

  levels = [13 8 5 2]; A_fsm = containers.Map('KeyType','double','ValueType','any');
  for f = levels
    td = qzi_iidm_variant_src(f); addpath(td); rehash;
    A_fsm(f) = runFSM(@(s,v,dv,vl,p,rst) double(acc_iidm_fsm(s,v,dv,vl,p,rst)));
    rmpath(td); rehash;
    % G1: FSM cotto == acc_iidm_open a quel nfrac
    d1 = max(abs(A_fsm(f) - runOpen(f)));
    fprintf('G1 nfrac=%2d: dmax(FSM vs acc_iidm_open) = %.3g\n', f, d1);
    assert(d1 == 0, 'G1 FALLITO a nfrac=%d: FSM cotto != acc_iidm_open (dmax=%.3g)', f, d1);
  end

  % G0: a nfrac=8 == acc_iidm_fsm ORIGINALE (senza temp dir)
  A_orig = runFSM(@(s,v,dv,vl,p,rst) double(acc_iidm_fsm(s,v,dv,vl,p,rst)));
  d0 = max(abs(A_fsm(8) - A_orig));
  fprintf('G0 nfrac=8: dmax(FSM cotto vs acc_iidm_fsm originale) = %.3g\n', d0);
  assert(d0 == 0, 'G0 FALLITO: la sostituzione a nfrac=8 non e'' un no-op (dmax=%.3g)', d0);

  % MORDE: nfrac=2 differisce da nfrac=13
  dm = max(abs(A_fsm(2) - A_fsm(13)));
  fprintf('MORDE nfrac=2 vs 13: dmax = %.3g\n', dm);
  assert(dm > 0, 'controllo negativo FALLITO: nfrac non morde (l''FSM non cambia con i bit)');
  fprintf('\nqzi_enabler_gate: G0 + G1(4 livelli) + morde -> TUTTI VERDI\n');
end

function A = local_run_all(fun, tr, nt, isOpen)
  if nargin < 4, isOpen = false; end
  A = [];
  for i = 1:nt
    v = double(tr{i}.val);           % [4 x N] stato; params veri in gt_params
    p = tr{i}.gt_params(:);
    for k = 1:size(v,2)
      if isOpen
        a = fun(v(1,k),v(2,k),v(3,k),v(4,k), p, k==1);
      else
        a = fun(v(1,k),v(2,k),v(3,k),v(4,k), p, k==1);
      end
      A(end+1,1) = a; %#ok<AGROW>
    end
  end
end
```

> Nota: il gate usa `gt_params` come `p` per entrambe le vie (FSM e acc_iidm_open) → confronta le DUE implementazioni della MATEMATICA IIDM a parità di ingressi, che è esattamente la relazione G2 (`acc_iidm_fsm` == `acc_iidm_open`). Non usa la SNN: qui si prova l'abilitatore dell'IIDM, non la rete.

- [ ] **Step 3: Esegui il cancello (background) e verifica i due sensi**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "addpath('Quantizzation_Study_IIDM'); qzi_enabler_gate" > /tmp/qzi_enab.log 2>&1
```

Alla notifica, leggi `/tmp/qzi_enab.log`. Atteso: `G0` dmax=0, `G1` dmax=0 su tutti e 4 i livelli, `MORDE` dmax>0. Se G1 fallisce a un nfrac → la sostituzione non ha coperto un file (controlla lo scoperto-per-grep in `qzi_iidm_variant_src`); se MORDE=0 → l'FSM non usa i tipi cotti (il pattern `acc_types('fixed')` non è quello vero).

- [ ] **Step 4: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/Quantizzation_Study_IIDM/qzi_iidm_variant_src.m matlab/Quantizzation_Study_IIDM/qzi_enabler_gate.m
git commit -m "feat(block-b): abilitatore nfrac dell'FSM IIDM + cancello bit-exact G0/G1

qzi_iidm_variant_src cuoce acc_types('fixed')->acc_types('fixed',nfrac) su copie (nomi invariati,
precedenza di path). qzi_enabler_gate prova nei due sensi: FSM cotto == acc_iidm_open a ogni nfrac
(G1 dmax=0), == acc_iidm_fsm originale a nfrac=8 (G0), e morde a nfrac=2 (controllo negativo)."
```

---

## Task 4: Hardware sweep Vivado (specchio di `qz_sweep_nfrac.sh`)

**Files:**
- Create: `matlab/Quantizzation_Study_IIDM/qzi_gen_iidm_vhdl.m`
- Create: `matlab/Quantizzation_Study_IIDM/qzi_synth.sh`
- Create: `matlab/Quantizzation_Study_IIDM/qzi_synth_set.txt`
- Output: `matlab/Quantizzation_Study_IIDM/qzi_res_sweep.tsv`
- Reference (leggere, NON modificare): `matlab/build_hdl_variants.m` (path IIDM→VHDL provata: inlining di `srcIidm`/`iidm_*`/`fsm_div` nella chart di `Donatello_ACC_IIDM_M`), `matlab/study_tradeoff/common/{synth_point.tcl,impl_point.tcl}`, `matlab/Quantizzation_Study/qz_gen_block_vhdl.m` + il suo harness `.sh` (metodo io-timed 125 ns).

Contesto: la generazione VHDL dell'FSM IIDM è già risolta in `build_hdl_variants.m` (SP4-M). Qui la si richiama con i **sorgenti a nfrac cotto** (dalla temp dir dell'abilitatore) per ottenere 4 VHDL, poi sintesi OOC io-timed 125 ns con l'harness comune, → LUT/FF/DSP/BRAM/WNS/Pdyn per nfrac.

- [ ] **Step 1: Scrivi il generatore VHDL a nfrac (riusa la path IIDM di `build_hdl_variants`)**

Leggi `build_hdl_variants.m` e individua il ramo che monta la chart `Donatello_ACC_IIDM_M` (inlining di `srcIidm`/`iidm_*`/`fsm_div` + `makehdl` con l'handshake `HDLMathLib/Divide`). Create `matlab/Quantizzation_Study_IIDM/qzi_gen_iidm_vhdl.m` che replica QUELLA path ma legge i sorgenti dalla temp dir di `qzi_iidm_variant_src(nfrac)` invece che da `matlab/`, e scrive il VHDL in `hdl_iidm_n<nfrac>/`:

```matlab
function outdir = qzi_gen_iidm_vhdl(nfrac)
%QZI_GEN_IIDM_VHDL  [Quantizzation_Study_IIDM] Genera il VHDL dell'FSM IIDM a nfrac cotto, riusando la
%  path HDL PROVATA di build_hdl_variants (chart Donatello_ACC_IIDM_M: chart SOLA nel subsystem +
%  UNA divide() + FSM a stadi -> l'unica forma che genera VHDL con tanh fixed, lezione SP4 §9).
%  I sorgenti IIDM vengono dalla temp dir dell'abilitatore (acc_types cotto a nfrac).
%  ⚠️ La chart deve restare SOLA nel subsystem: non aggiungere blocchi accanto, o scatta la
%     conversione MATLAB-to-dataflow che vieta tanh fixed (SP4 §9).
  td = qzi_iidm_variant_src(nfrac);
  outdir = fullfile(fileparts(mfilename('fullpath')), sprintf('hdl_iidm_n%d', nfrac));
  if exist(outdir,'dir'), rmdir(outdir,'s'); end
  % <<< qui il corpo replica il ramo ACC_IIDM_M di build_hdl_variants.m, con `here := td`
  %     per i fileread dei sorgenti IIDM, e hdlset_param(...,'TargetDirectory',outdir).
  %     Vedi build_hdl_variants.m: assemblaggio srcIidm/srcAb/srcSabx/iidm_* -> chart -> makehdl. >>>
  fprintf('qzi_gen_iidm_vhdl: nfrac=%d -> %s\n', nfrac, outdir);
end
```

> Questo è l'UNICO punto del piano che non riproduce codice verbatim: la path IIDM→VHDL è lunga e già provata in `build_hdl_variants.m`. Copiare il ramo `Donatello_ACC_IIDM_M` da lì (leggendo i sorgenti da `td`) è più sicuro che reinventarlo. Se la lettura di `build_hdl_variants.m` mostra che l'inlining assume `here = fileparts(mfilename)`, basta ridefinire la base dei `fileread` su `td`.

- [ ] **Step 2: Scrivi l'insieme e l'harness di sintesi (specchio di `qz_sweep_nfrac.sh`)**

Create `matlab/Quantizzation_Study_IIDM/qzi_synth_set.txt`:

```
13
8
5
2
```

Create `matlab/Quantizzation_Study_IIDM/qzi_synth.sh` specchiando `Quantizzation_Study/qz_sweep_nfrac.sh` (STESSA sequenza: per ogni nfrac, `rm -rf` del VHDL vecchio → `matlab -batch qzi_gen_iidm_vhdl(nfrac)` → `vivado -mode batch` con `synth_point.tcl` + `impl_point.tcl` (5° arg `io` per il timing io-timed a 125 ns) → estrai LUT/FF/DSP/BRAM/WNS/Pdyn → append a `qzi_res_sweep.tsv`). Punti chiave da rispettare (dall'harness estimator):
- **PATH POSIX→Windows** per gli `addpath` di MATLAB (`cygpath -w` o `/d/`→`D:/`), sennò gen silenziosamente fallita.
- **`rm -rf` del VHDL a monte** di ogni gen, sennò un VHDL stantìo maschera.
- **smoke su un livello NON pre-generato** prima del ciclo intero.
- periodo target **125 ns** (deploy), non un clock vincolato; **riporta lo SLACK (WNS)** e la potenza **dinamica**.

Header del TSV: `nfrac\tLUT\tFF\tDSP\tBRAM\tWNS_ns\tPdyn_mW`.

- [ ] **Step 3: Smoke di UN livello (gen + sintesi) prima del ciclo intero**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/Quantizzation_Study_IIDM"
# genera il VHDL del solo nfrac=5 (livello non ancora generato) e ispezionalo
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "addpath('..'); qzi_gen_iidm_vhdl(5)" > /tmp/qzi_gen5.log 2>&1
```

Alla notifica, verifica che `hdl_iidm_n5/` contenga i `.vhd` attesi (l'FSM + il wrapper divisione). Se vuoto o errore → risolvi la path IIDM→VHDL (Step 1) prima di lanciare lo sweep.

- [ ] **Step 4: Esegui lo sweep hardware completo (background)**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab/Quantizzation_Study_IIDM"
bash qzi_synth.sh > /tmp/qzi_synth.log 2>&1
```

Alla notifica, leggi `/tmp/qzi_synth.log` e `qzi_res_sweep.tsv`. Atteso: 4 righe (13/8/5/2), WNS>0 (timing chiude a 125 ns con margine largo), LUT/FF/DSP che si muovono col nfrac (il confine DSP↔LUT), Pdyn pochi mW. Verifica che il VHDL@13 corrisponda al riferimento (bit-exact già provato al Task 3 per la matematica; qui basta che la sintesi produca numeri, non un secondo gate funzionale).

- [ ] **Step 5: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/Quantizzation_Study_IIDM/qzi_gen_iidm_vhdl.m matlab/Quantizzation_Study_IIDM/qzi_synth.sh matlab/Quantizzation_Study_IIDM/qzi_synth_set.txt matlab/Quantizzation_Study_IIDM/qzi_res_sweep.tsv
git commit -m "feat(block-b): sweep hardware IIDM (Vivado io-timed 125ns) vs nfrac

qzi_gen_iidm_vhdl riusa la path IIDM->VHDL di build_hdl_variants coi sorgenti a nfrac cotto;
qzi_synth.sh (specchio di qz_sweep_nfrac.sh) sintetizza {13,8,5,2} -> LUT/FF/DSP/BRAM/WNS/Pdyn
in qzi_res_sweep.tsv. Metodo: periodo 125 ns, riporta slack e potenza dinamica."
```

---

## Task 5: Blocco `ACC-IIDM` configurabile (menu NFRAC)

**Files:**
- Create: `matlab/build_acc_iidm_block.m`
- Create: `matlab/Quantizzation_Study_IIDM/qzi_block_gate.m`
- Modify: `matlab/snn_champions_lib.slx` (aggiunta del blocco — via lo script builder, non a mano)
- Reference (leggere): `matlab/build_tier_configurable.m` (Variant Subsystem + mask popup + tipi cotti + `arrangeSystem` + pulizia stray), `build_hdl_variants.m` (chart IIDM).

Contesto: il blocco `ACC-IIDM` è generico (9 ingressi `s,v,dv,v_l,v0,T,s0,a,b` → 1 uscita `accel`), architettura M (la migliore), con menu NFRAC {13,8,5,2}. **Dipendenza dai dati (Task 1)**: i livelli 5/2 si includono nel menu SOLO se `qzi_cl_sweep.tsv` conferma `coll_extra=0` a quei livelli; altrimenti il menu si ferma a `{13,8}` (o `{13,10,8}`). Decisione ancorata al TSV, non a priori. Sotto si assume l'esito atteso {13,8,5,2}; se il Task 1 dà coll_extra>0 a 5/2, riduci `NFRAC_LEVELS` di conseguenza e marca "oltre budget E_iidm" nella descrizione.

- [ ] **Step 1: Scrivi il builder del blocco (specchio di `build_tier_configurable`)**

Create `matlab/build_acc_iidm_block.m`. Struttura da specchiare da `build_tier_configurable.m`, con le differenze:
- **I/O**: 9 Inport (`s,v,dv,v_l,v0,T,s0,a,b`), 1 Outport (`accel`). Porte `Inherit: auto` (config-independent).
- **Varianti**: una per nfrac ∈ `NFRAC_LEVELS` (default `[13 8 5 2]`); ogni variante è la chart FSM IIDM con `acc_types('fixed')`→`acc_types('fixed',nfrac)` cotto (sorgenti da `qzi_iidm_variant_src(nfrac)` o inlining diretto come `build_hdl_variants`). VariantControl: `NFRAC==<level>`.
- **Chart SOLA nel subsystem** di variante (lezione SP4 §9: nessun blocco accanto, o salta la conversione dataflow che vieta `tanh` fixed).
- **Mask**: un popup `NFRAC` con le voci di `NFRAC_LEVELS`; descrizione che marca i livelli sotto il floor E_iidm come "solo-sicurezza / oltre budget" secondo `qzi_cl_sweep.tsv`.
- **Pulizia**: `Simulink.BlockDiagram.arrangeSystem` sul blocco e sul Variant Subsystem prima del salvataggio; rimozione robusta dello stray `Subsystem1` (stessa tecnica di `build_tier_configurable`: `getSimulinkBlockHandle` + `find_system(...,'MatchFilter',@Simulink.match.allVariants,'BlockType','SubSystem')`, cancella i figli con handle diverso dal Variant Subsystem).
- Nome del blocco: `ACC-IIDM` (senza prefisso Donatello).

```matlab
function build_acc_iidm_block(nfracLevels)
%BUILD_ACC_IIDM_BLOCK  Costruisce il blocco di libreria 'ACC-IIDM' (controllore standalone, 9 in -> accel)
%  in snn_champions_lib.slx: Variant Subsystem con una variante per nfrac, mask popup NFRAC, chart FSM
%  IIDM (architettura M) a nfrac cotto. Specchio di build_tier_configurable per l'IIDM.
%  nfracLevels: default [13 8 5 2]; RIDURRE a [13 8] se qzi_cl_sweep.tsv mostra coll_extra>0 a 5/2.
  if nargin < 1 || isempty(nfracLevels), nfracLevels = [13 8 5 2]; end
  % <<< corpo: apri/carica snn_champions_lib.slx (unlock), crea il subsystem 'ACC-IIDM',
  %     9 Inport + 1 Outport, un Variant Subsystem con numel(nfracLevels) varianti; per ogni
  %     livello monta la chart IIDM (inlining come build_hdl_variants) con acc_types cotto a quel
  %     nfrac; imposta VariantControl 'NFRAC==<level>'; aggiungi la mask popup NFRAC; arrangeSystem;
  %     rimuovi lo stray Subsystem1; salva la libreria. Vedi build_tier_configurable.m per il
  %     boilerplate Variant+Mask+arrange+pulizia (identico salvo I/O e sorgente chart). >>>
  fprintf('build_acc_iidm_block: blocco ACC-IIDM con NFRAC in [%s] scritto in snn_champions_lib.slx\n', ...
          num2str(nfracLevels));
end
```

- [ ] **Step 2: Scrivi il cancello del blocco G3/G4**

Create `matlab/Quantizzation_Study_IIDM/qzi_block_gate.m`:

```matlab
function qzi_block_gate()
%QZI_BLOCK_GATE  [Quantizzation_Study_IIDM] Cancelli del blocco ACC-IIDM:
%  G3a  - la variante di DEFAULT (nfrac=8) streama == acc_iidm_open(...,acc_types('fixed',8)) sul
%         dataset, dmax=0 (no-regressione: il blocco non cambia il comportamento validato).
%  G3b  - tutte le varianti NFRAC compilano (set_param NFRAC=<lvl> + un passo di simulazione).
%  G4   - makehdl da una variante genera VHDL (con l'handshake divisione), senza errori.
  mroot = fileparts(fileparts(mfilename('fullpath'))); addpath(mroot);
  lib = 'snn_champions_lib'; blk = [lib '/ACC-IIDM'];
  load_system(lib);
  % --- G3a: no-regressione della variante default vs acc_iidm_open@8 su un sottoinsieme del dataset ---
  % (guida un harness minimale: alimenta 9 ingressi da alcune traiettorie, confronta l'uscita accel
  %  con acc_iidm_open double? No: vs acc_types('fixed',8) — la forma FSM del blocco. dmax deve essere 0.)
  % <<< implementa l'harness di streaming: costruisci un model temporaneo con il blocco, From Workspace
  %     sui 9 ingressi da N traiettorie del dataset, confronta l'uscita con
  %     acc_iidm_open(...,acc_types('fixed',8)) -> assert dmax==0. >>>
  % --- G3b: ogni variante compila ---
  levels = [13 8 5 2];
  for f = levels
    set_param(blk, 'NFRAC', num2str(f));   % nome esatto del popup dal builder
    % un update/compile del blocco in un model temporaneo -> nessun errore
  end
  % --- G4: makehdl da una variante ---
  % <<< set NFRAC=8, makehdl sul subsystem del blocco -> VHDL generato, nessun errore. >>>
  fprintf('qzi_block_gate: G3a (dmax=0) + G3b (4 varianti) + G4 (makehdl) -> VERDI\n');
end
```

> Il corpo `<<< >>>` degli harness di streaming/makehdl va modellato su quelli già esistenti per `Donatello_Tier`: cerca `run_block_*_test` / `qz_tier_nfrac_gate.m` / `run_block_hdl_gate` e riusa lo scheletro (model temporaneo + From Workspace + confronto; `makehdl` sul path del subsystem). Non reinventare l'harness: adatta quello dell'estimator.

- [ ] **Step 3: Costruisci il blocco e passa il cancello (usa `qzi_cl_sweep.tsv` per i livelli)**

Prima leggi `qzi_cl_sweep.tsv` (Task 1): se `coll_extra`>0 a nfrac 5 o 2, invoca `build_acc_iidm_block([13 8])`; altrimenti `build_acc_iidm_block` (default `[13 8 5 2]`).

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
"/c/Program Files/MATLAB/R2026a/bin/matlab.exe" -batch "build_acc_iidm_block; addpath('Quantizzation_Study_IIDM'); qzi_block_gate" > /tmp/qzi_block.log 2>&1
```

Alla notifica, leggi `/tmp/qzi_block.log`. Atteso: builder OK + `qzi_block_gate` G3a dmax=0, G3b 4 varianti, G4 makehdl OK. Controlla anche a occhio l'ordine visivo (niente sovrapposizioni — lezione Blocco A): apri la libreria e verifica il layout del blocco.

- [ ] **Step 4: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/build_acc_iidm_block.m matlab/Quantizzation_Study_IIDM/qzi_block_gate.m matlab/snn_champions_lib.slx
git commit -m "feat(block-b): blocco ACC-IIDM configurabile (menu NFRAC) + cancello G3/G4

Blocco standalone 9 in -> accel, architettura M, Variant Subsystem con menu NFRAC (livelli dai dati
di qzi_cl_sweep.tsv). Chart FSM sola nel subsystem (SP4 §9), arrangeSystem + pulizia stray. Cancello:
default streama == acc_iidm_open@8 (dmax=0), varianti compilano, makehdl genera VHDL."
```

---

## Task 6: Report — sezione IIDM (specchio della disciplina dell'estimator)

**Files:**
- Modify: `scripts/build_quantization_report.py`
- Modify: `matlab/Quantizzation_Study/QZ_CARFOLLOWING_STUDY.md` (nuova §13, sorgente della sezione)
- Modify (rigenerato): `report/QUANTIZATION_STUDY_REPORT.{md,pdf}` + `report/figures_quant/{iidm_fidelity,iidm_area}.png`

Contesto: il report esistente (`build_quantization_report.py`) genera §1–9 dell'estimator (uniforme + mixed-precision). Aggiungiamo una sezione IIDM (studio specchiato) e allarghiamo la cornice a "sistema car-following (estimator + controllore)".

- [ ] **Step 1: Aggiungi i loader `qzi_*.tsv` + 2 figure**

Modify `scripts/build_quantization_report.py`: aggiungi (mirando i loader esistenti `_mp_rows`/`MP_*`):
- `QZI_CL`, `QZI_ACC`, `QZI_SEV`, `QZI_RES` = path ai TSV in `matlab/Quantizzation_Study_IIDM/`.
- `fig_iidm_fidelity`: NRMSE(accel) + max|d| vs nfrac (da `qzi_acc_sweep.tsv` e `qzi_cl_sweep.tsv`) — figura specchiata di quella dell'estimator.
- `fig_iidm_area`: barre % LUT/FF/DSP vs full (nfrac=13) da `qzi_res_sweep.tsv` — specchiata della figura hardware.
Scrivi le figure in `report/figures_quant/iidm_fidelity.png` e `iidm_area.png`.

- [ ] **Step 2: Aggiungi la sezione + allarga la cornice**

Modify `build_quantization_report.py`: nuova sezione "§N Quantizzazione del controllore IIDM (studio specchiato)" che riporta: safety (coll_extra da `qzi_cl_sweep.tsv`), fedeltà (NRMSE/max|d| accel), severità (`qzi_sev_sweep.tsv`), hardware (`qzi_res_sweep.tsv` con WNS e Pdyn), e la lente E_iidm vs E_snn (floor 8). Aggiorna il titolo/introduzione: da "quantizzazione della rete spiking" a "quantizzazione del **sistema** car-following (estimator + controllore IIDM)". Aggiorna la lista sorgenti in copertina con i `qzi_*.tsv`.

- [ ] **Step 3: Scrivi la §13 nel doc sorgente**

Modify `matlab/Quantizzation_Study/QZ_CARFOLLOWING_STUDY.md`: nuova §13 "Quantizzazione del controllore IIDM" che documenta lo studio specchiato (SNN congelata, IIDM varia), le metriche, i floor, il menu del blocco, l'hardware. Stessa disciplina delle §1–12 (numeri dai TSV, lettura onesta).

- [ ] **Step 4: Rigenera il report e verifica (determinismo + QC)**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
"/c/Miniconda/python.exe" scripts/build_quantization_report.py
"/c/Miniconda/python.exe" scripts/build_quantization_report.py   # 2a volta: il .md deve essere IDENTICO
git diff --stat report/QUANTIZATION_STUDY_REPORT.md
```

Atteso: la seconda esecuzione NON cambia il `.md` (determinismo). Apri il PDF e verifica QC visiva: le 2 figure IIDM rese, tabelle allineate, numeri coerenti coi TSV, nessun apostrofo-residuo. Confronta i numeri stampati con `qzi_*.tsv` (verifica l'artefatto, non l'intenzione).

- [ ] **Step 5: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add scripts/build_quantization_report.py matlab/Quantizzation_Study/QZ_CARFOLLOWING_STUDY.md report/QUANTIZATION_STUDY_REPORT.md report/QUANTIZATION_STUDY_REPORT.pdf report/figures_quant/iidm_fidelity.png report/figures_quant/iidm_area.png
git commit -m "docs(block-b): sezione IIDM nel report di quantizzazione (studio specchiato)

Nuova sezione: safety+fedelta(NRMSE/max|d| accel)+severita+hardware dell'IIDM vs nfrac, con la lente
E_iidm vs E_snn (floor 8). Cornice allargata a 'sistema car-following (estimator + controllore)'.
2 figure specchiate (fedelta, area). Sorgente in QZ_CARFOLLOWING_STUDY.md §13. Determinismo verificato."
```

---

## Self-Review

**1. Copertura della spec** (`docs/superpowers/specs/2026-07-25-block-b-iidm-nfrac-design.md`):
- §3.1 Studio (safety, fedeltà NRMSE, severità, accuratezza open-loop, hardware) → Task 1 (safety+NRMSE cl), Task 2 (open-loop NRMSE+max|d|, severità), Task 4 (hardware). ✓
- §3.1 lente E_iidm vs E_snn → riusata da `run_acc_fixed_sweep`; riportata in §report Task 6. ✓
- §3.1 Report come SEZIONE del report esistente → Task 6. ✓
- §3.2 Blocco ACC-IIDM (9 in→accel, menu NFRAC, arch M, arrangeSystem+pulizia stray) → Task 5. ✓
- §3.2 Abilitatore nfrac cotto nell'FSM → Task 3. ✓
- §4 Cancelli G0/G1 (abilitatore bit-exact + morde) → Task 3; G2 (studio due sensi) → Task 1; G3 (blocco no-reg) + G4 (HDL da blocco) → Task 5; G5 (report determinismo+QC) → Task 6. ✓
- §3.2 livelli 5/2 nel menu SOLO se lo studio conferma sicurezza → Task 5 Step 3 (ancorato a `qzi_cl_sweep.tsv`). ✓
- §6 rischio: FSM fixed-only, sostituzione senza reintrodurre il vincolo → Task 3 (cotto concreto, non runtime). ✓
- §6 rischio: chart sola nel subsystem (divisione/tanh) → Task 4 Step 1 + Task 5 Step 1 (nota esplicita). ✓

**2. Placeholder scan:** i tre corpi `<<< >>>` (Task 4 Step 1 `qzi_gen_iidm_vhdl`, Task 5 Step 1 `build_acc_iidm_block`, Task 5 Step 2 harness del gate) NON sono placeholder di logica da inventare: rimandano a codice PROVATO ed esistente (`build_hdl_variants.m` per la path IIDM→VHDL, `build_tier_configurable.m` per Variant+Mask+arrange, `qz_tier_nfrac_gate.m`/`run_block_hdl_gate` per l'harness), da COPIARE con la sostituzione indicata. Riprodurli verbatim sarebbe indovinare una path HDL lunga anziché riusarne una provata (peggiore per rule 5). Ogni `<<< >>>` nomina il file sorgente e la modifica esatta. Il resto del piano è codice reale.

**3. Coerenza dei tipi/nomi:** `qzi_cl_step` firma `[p,accel]=qzi_cl_step(x,W,rst,nfrac)` coerente col MEX `qzi_cl_step_n%d_mex(x,W,rst,f)` (Task 1, 2). `qzi_iidm_variant_src(nfrac)->td` usato da Task 3 (gate), Task 4 (gen), Task 5 (blocco) con la stessa firma. `champ_weights(c)` (non `to_weights`) — la funzione usata dagli script closed-loop. TSV: nomi colonna coerenti tra scrittura (Task 1/2/4) e lettura (Task 6). Livello riferimento NRMSE = nfrac=13 in tutti i task. Nome blocco `ACC-IIDM` coerente Task 5/6.

**4. Note verificate (rule 5):** `acc_iidm_open(s,v,dv,v_l,p,rst,T)` firma reale (letta); `acc_types(dt,nfrac,recipN)` default nfrac=8 (letto); `qz_cl_sim` ritorna `.series.a` (accel per-step, letto); `qz_safety_metrics(series,collided,min_gap,impact_dv)->{.collided,.min_gap,.brake_margin_min,.max_DRAC}` (dai siti di chiamata); i file con `acc_types('fixed')` scoperti per grep (8: acc_iidm_fsm + 7 fase) — l'abilitatore li scopre per grep, non hardcoded, così un file nuovo non sfugge.
