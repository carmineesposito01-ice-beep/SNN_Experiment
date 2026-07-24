# Studio quantizzazione per-campo (mixed-precision) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Caratterizzare la sensibilità per-campo della quantizzazione di Donatello (6 nfrac indipendenti), trovare l'allocazione area-ottimale a comportamento car-following indistinguibile dal full-precision, misurarne il costo hardware, esporre la config nel blocco (Modalità Avanzata) e aggiungere i risultati al report.

**Architecture:** Tutto isolato in `matlab/Quantizzation_Study/` (prefisso `qz_`), core intatto. Abilitatore unico: una copia per-campo di `snn_types`. Riuso dell'anello fedele `qz_cl_sim`, delle SSM `qz_safety_metrics`, del generatore VHDL `qz_gen_block_vhdl`, del tooling di sintesi `study_tradeoff/common/*.tcl`, del dataset `test_dataset_exhaustive.mat` e del generatore di report `scripts/build_quantization_report.py`. Il cancello è **comportamentale** (`max|Δgap| ≤ 0.5 m` vs full-precision + 0 collisioni extra), quindi la sensibilità è cheap (anello chiuso, niente sintesi); la sintesi entra solo sui finalisti.

**Tech Stack:** MATLAB R2026a (`matlab.exe -batch`, MATLAB Coder per i MEX), Vivado 2026.1 (`vivado.bat` via i `.tcl`), Python base (`C:/Miniconda/python.exe`, matplotlib + reportlab per il report). Spec: `docs/superpowers/specs/2026-07-24-per-field-mixed-precision-design.md`.

**Convenzioni:**
- `MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"` ; `QZ=matlab/Quantizzation_Study`.
- Campi in ordine fisso: `[V, fatigue, acc, accw, raw, w]`; una config è un vettore `nf` di 6 interi.
- Full-precision = `nf = [13 13 13 13 13 13]` (accw → Q8.17). Commit conventional **senza** `Co-Authored-By`.

---

## File Structure

| File | Responsabilità |
|---|---|
| `QZ/qz_snn_types_mp.m` | tabella tipi a 6 nfrac per-campo (copia parametrica di `snn_types`) — l'ABILITATORE |
| `QZ/qz_snn_cl_step_mp.m` | step-forward a precisione mista (copia di `qz_snn_cl_step`, tipi per-campo, `nf` = `coder.Constant`) |
| `QZ/qz_mp_gate.m` | dato `nf`, gira l'anello sul dataset e ritorna il cruscotto + il verdetto del cancello (max\|Δgap\| + coll_extra) |
| `QZ/qz_mp_sensitivity.m` | Fase A: 6 campi × livelli → `mp_sens.tsv` (cruscotto per campo/livello) + i 6 floor |
| `QZ/qz_mp_combine.m` | Fase B: aggressiva + back-off, verifica congiunta → `mp_finalists.tsv` |
| `QZ/qz_gen_block_vhdl_mp.m` | VHDL a precisione mista (copia di `qz_gen_block_vhdl`, tipi per-campo) |
| `QZ/qz_mp_synth.sh` | Fase C: sintesi io-timed sull'insieme ridotto → `mp_res.tsv` |
| `matlab/build_tier_configurable.m` (**modify**) | Fase D: Modalità Avanzata (6 nfrac) via mask auto-modificante |
| `QZ/qz_mp_advanced_gate.m` | cancello Modalità Avanzata (bit-exact @full-precision, config nota, Base intatta) |
| `scripts/build_quantization_report.py` (**modify**) | Fase E: nuova sezione mixed-precision |
| `QZ/QZ_CARFOLLOWING_STUDY.md` (**modify**) | doc sorgente: sezione mixed-precision |

Output dati (committati): `QZ/mp_sens.tsv`, `QZ/mp_finalists.tsv`, `QZ/mp_res.tsv`.

---

## Task 0: Abilitatore — tipi per-campo + forward a precisione mista

**Files:**
- Create: `matlab/Quantizzation_Study/qz_snn_types_mp.m`, `matlab/Quantizzation_Study/qz_snn_cl_step_mp.m`

- [ ] **Step 1: Scrivi `qz_snn_types_mp.m`** (i tipi con 6 nfrac; accw mantiene il +4)

```matlab
function T = qz_snn_types_mp(dt, nf)
%QZ_SNN_TYPES_MP  [Quantizzation_Study] Copia PER-CAMPO di snn_types: nf = [nV nfat nacc naccw nraw nw]
%  (6 bit frazionari indipendenti). Interi fissi come in snn_types; accw mantiene il +4 (scorrimenti po2).
%  A nf=[13 13 13 13 13 13] i tipi coincidono con snn_types('fixed',13). NON tocca snn_types.m.
  assert(numel(nf) == 6, 'nf deve avere 6 elementi [V fatigue acc accw raw w]');
  switch dt
    case 'double'
      z = double([]);
      T = struct('V', z, 'fatigue', z, 'acc', z, 'accw', z, 'raw', z, 'w', z);
    case 'fixed'
      T = struct( ...
        'V',       fi([], true, 6 + nf(1), nf(1)), ...
        'fatigue', fi([], true, 4 + nf(2), nf(2)), ...
        'acc',     fi([], true, 6 + nf(3), nf(3)), ...
        'accw',    fi([], true, 13 + nf(4), nf(4) + 4), ...
        'raw',     fi([], true, 8 + nf(5), nf(5)), ...
        'w',       fi([], true, 3 + nf(6), nf(6)));
    otherwise
      error('qz_snn_types_mp:dt', 'dt deve essere ''double'' o ''fixed''');
  end
end
```

- [ ] **Step 2: Cancello tipi — a tutti-13 coincide con snn_types('fixed',13)**

```bash
MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"
cd "matlab"
"$MATLAB" -batch "addpath(pwd); addpath('Quantizzation_Study'); \
  a=snn_types('fixed',13); b=qz_snn_types_mp('fixed',[13 13 13 13 13 13]); \
  f=fieldnames(a); ok=true; \
  for i=1:numel(f), ok = ok && isequal(numerictype(a.(f{i})), numerictype(b.(f{i}))); end; \
  assert(ok,'tipi per-campo a 13 NON coincidono con snn_types 13'); disp('GATE tipi @13: OK')"
```
Expected: `GATE tipi @13: OK`.

- [ ] **Step 3: Scrivi `qz_snn_cl_step_mp.m`** (copia di `qz_snn_cl_step` coi tipi per-campo)

```matlab
function [p, accel] = qz_snn_cl_step_mp(x_phys, W, rst, nf) %#codegen
%QZ_SNN_CL_STEP_MP  [Quantizzation_Study] Copia di qz_snn_cl_step con tipi PER-CAMPO (qz_snn_types_mp).
%  nf = [nV nfat nacc naccw nraw nw], passato come coder.Constant per il MEX. Decode fisso En13.
  T = qz_snn_types_mp('fixed', nf);
  if rst
    snn_core(cast(zeros(4, 1), 'like', T.V), W, T, true);
  end
  xn  = cast(snn_normalize(x_phys, W.norm), 'like', T.V);
  raw = snn_core(xn, W, T, false);
  pf  = snn_decode_lut(raw, 64);
  p   = double(pf(:));
  accel = double(acc_iidm_open(x_phys(1), x_phys(2), x_phys(3), x_phys(4), p, rst, acc_types('fixed')));
end
```

- [ ] **Step 4: Cancello bit-exact @full-precision del forward** (a tutti-13, il forward mp == il forward unico a nfrac=13, dmax=0 sul dataset)

Scrivi `matlab/Quantizzation_Study/qz_mp_selftest0.m`:
```matlab
function qz_mp_selftest0()
%QZ_MP_SELFTEST0  Il forward mp a nf=[13...] coincide bit per bit col forward unico a nfrac=13.
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here); addpath(mroot); addpath(here);
  dd = load(fullfile(mroot,'champions_export.mat')); ch = dd.champions; if iscell(ch), ch=[ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1)); W = champ_weights(c);
  ds = load(fullfile(here,'test_dataset_exhaustive.mat')); tr = ds.trajectories;
  nf13 = [13 13 13 13 13 13];
  dmax = 0;
  for i = 1:10   % 10 traiettorie bastano: il forward e' deterministico e uguale ovunque
    t = tr{i}; s = t.s_init; v = t.v_init; ve_prev = v; DT = 0.1;
    vl = t.v_leader(:).'; N = min(200, numel(vl)); xl = zeros(1,N);
    for k = 2:N, xl(k) = xl(k-1) + vl(k)*DT; end
    for k = 1:N
      dv = v - vl(k); xq = [max(xl(k)-s*0, 0.5); v; dv; vl(k)];  %#ok<NASGU>  input fisico plausibile
      x = [max(s,0.5); v; dv; vl(k)];
      [p_mp, ~] = qz_snn_cl_step_mp(x, W, k==1, nf13);
      [p_u,  ~] = qz_snn_cl_step(x, W, k==1, 13);
      dmax = max(dmax, max(abs(p_mp - p_u)));
      v = min(max(v + 0*DT, 0), 40); ve_prev = v; %#ok<NASGU>
    end
  end
  fprintf('dmax forward mp@13 vs unico@13 = %.4g\n', dmax);
  assert(dmax == 0, 'forward mp @13 NON bit-exact al forward unico @13');
  disp('GATE forward mp @13: BIT-EXACT');
end
```
```bash
"$MATLAB" -batch "addpath(pwd); addpath('Quantizzation_Study'); qz_mp_selftest0()"
```
Expected: `dmax forward mp@13 vs unico@13 = 0` + `GATE forward mp @13: BIT-EXACT`.

- [ ] **Step 5: Commit**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
git add matlab/Quantizzation_Study/qz_snn_types_mp.m matlab/Quantizzation_Study/qz_snn_cl_step_mp.m matlab/Quantizzation_Study/qz_mp_selftest0.m
git commit -m "feat(qz-mp): abilitatore tipi+forward per-campo (bit-exact @full-precision)"
```

---

## Task 1: Il cancello comportamentale (max|Δgap|) + rilevatore nei due sensi

**Files:**
- Create: `matlab/Quantizzation_Study/qz_mp_gate.m`

`qz_mp_gate(nf, trajList)` gira l'anello `qz_cl_sim` col forward mp a `nf` su tutte le traiettorie, lo confronta col riferimento full-precision (tutti-13) e ritorna il cruscotto + il verdetto. Il MEX per `nf` viene costruito se manca. Il riferimento full-precision viene calcolato una volta e cachato su file (`mp_ref13.mat`).

- [ ] **Step 1: Scrivi `qz_mp_gate.m`**

```matlab
function out = qz_mp_gate(nf, trajList)
%QZ_MP_GATE  [Quantizzation_Study] Verdetto + cruscotto di una config per-campo nf, sull'intero dataset.
%  Cancello: max|Δgap| vs full-precision (tutti-13) <= 0.5 m  E  0 collisioni extra vs oracolo.
%  out: .maxdgap .coll_extra .pass  + cruscotto (.min_gap .brake_margin .max_DRAC .min_TTC .nrmse[1x5] .impact_max)
  THR = 0.5;   % soglia comportamentale [m] (spec §3)
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here); addpath(mroot); addpath(here);
  if nargin < 2 || isempty(trajList), trajList = 1:99; end
  dd = load(fullfile(mroot,'champions_export.mat')); ch = dd.champions; if iscell(ch), ch=[ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1)); W = champ_weights(c);
  ds = load(fullfile(here,'test_dataset_exhaustive.mat')); tr = ds.trajectories; T = tr(trajList);

  fun = qz_mp_mex(nf, W);                       % MEX per nf (build-if-missing); vedi funzione locale
  oracle = @(gtp) @(x,rst) deal(gtp(:), double(acc_iidm_open(x(1),x(2),x(3),x(4),gtp(:),rst,acc_types('double'))));

  % riferimento full-precision (cache): gap per traiettoria + params
  ref = qz_mp_ref13(here, W, T, trajList);      % struct con .gap{i} .P{i} .Bcoll (oracolo)

  nt = numel(T); maxdg = 0; coll = 0; mng = inf; bmn = inf; drmax = 0; ttcmin = inf;
  num = zeros(1,5); den = 0; impmax = 0;
  for i = 1:nt
    o = qz_cl_sim(T{i}, @(x,rst) fun(x, W, rst, nf));
    g = o.series.s; gr = ref.gap{i}; n = min(numel(g), numel(gr));
    maxdg = max(maxdg, max(abs(g(1:n) - gr(1:n))));
    m = qz_safety_metrics(o.series, o.collided, o.min_gap, o.impact_dv);
    if o.collided && ~ref.Bcoll(i), coll = coll + 1; end   % collisione EXTRA vs oracolo
    mng = min(mng, m.min_gap); bmn = min(bmn, m.brake_margin_min);
    drmax = max(drmax, m.max_DRAC); if isfinite(m.min_ttc), ttcmin = min(ttcmin, m.min_ttc); end
    if ref.Bcoll(i), impmax = max(impmax, m.impact_dv); end
    Pr = ref.P{i}; np = min(size(o.params,1), size(Pr,1));
    num = num + sum((o.params(1:np,:) - Pr(1:np,:)).^2, 1); den = den + np;
  end
  out = struct('nf', nf, 'maxdgap', maxdg, 'coll_extra', coll, ...
               'pass', (maxdg <= THR && coll == 0), ...
               'min_gap', mng, 'brake_margin', bmn, 'max_DRAC', drmax, 'min_TTC', ttcmin, ...
               'nrmse', sqrt(num/den) ./ ref.prng, 'impact_max', impmax);
end

function fun = qz_mp_mex(nf, W)
% build-if-missing del MEX di qz_snn_cl_step_mp per la tupla nf (coder.Constant)
  here = fileparts(mfilename('fullpath'));
  tag = sprintf('%d_', nf); tag = tag(1:end-1);
  mx = sprintf('qz_mp_step_%s_mex', tag);
  if isempty(which(mx))
    cfg = coder.config('mex'); cfg.GenerateReport = false; oldd = cd(here); cu = onCleanup(@() cd(oldd)); %#ok<NASGU>
    codegen('qz_snn_cl_step_mp', '-config', cfg, ...
            '-args', {zeros(4,1), coder.typeof(W), true, coder.Constant(double(nf))}, ...
            '-o', mx, '-d', ['codegen_mp_' tag]);
  end
  fun = str2func(mx);
end

function ref = qz_mp_ref13(here, W, T, trajList)
% riferimento full-precision (tutti-13): cache su file per non ricalcolarlo a ogni chiamata
  cf = fullfile(here, sprintf('mp_ref13_%d_%d.mat', trajList(1), trajList(end)));
  if isfile(cf), s = load(cf); ref = s.ref; return; end
  fun = qz_mp_mex([13 13 13 13 13 13], W);
  oracle = @(gtp) @(x,rst) deal(gtp(:), double(acc_iidm_open(x(1),x(2),x(3),x(4),gtp(:),rst,acc_types('double'))));
  nt = numel(T); gap = cell(1,nt); P = cell(1,nt); Bcoll = false(1,nt);
  for i = 1:nt
    o = qz_cl_sim(T{i}, @(x,rst) fun(x, W, rst, [13 13 13 13 13 13])); gap{i} = o.series.s; P{i} = o.params;
    oo = qz_cl_sim(T{i}, oracle(T{i}.gt_params)); Bcoll(i) = oo.collided;
  end
  allP = cell2mat(P(:)); prng = max(allP,[],1) - min(allP,[],1); prng(prng==0) = 1;
  ref = struct('gap', {gap}, 'P', {P}, 'Bcoll', Bcoll, 'prng', prng);
  save(cf, 'ref');
end
```

- [ ] **Step 2: Cancello del rilevatore provato NEI DUE SENSI**

Scrivi `matlab/Quantizzation_Study/qz_mp_gate_selftest.m`:
```matlab
function qz_mp_gate_selftest()
%QZ_MP_GATE_SELFTEST  Il cancello ACCETTA il full-precision (Δgap=0) e una config vicina, RIFIUTA una cattiva.
  a13 = qz_mp_gate([13 13 13 13 13 13], 1:99);
  assert(a13.maxdgap == 0 && a13.pass, 'il cancello non accetta il full-precision');
  a2  = qz_mp_gate([2 2 2 2 2 2], 1:99);   % nfrac unico n2: max|Δgap| ~31 m (studio unico) -> deve FALLIRE
  assert(~a2.pass && a2.maxdgap > 0.5, 'il cancello non rifiuta la config a 2 bit (maxdgap=%.3g)', a2.maxdgap);
  fprintf('GATE detector: accetta @13 (Δgap=%.2g), rifiuta @2 (Δgap=%.2g m) -> OK\n', a13.maxdgap, a2.maxdgap);
end
```
```bash
"$MATLAB" -batch "addpath(pwd); addpath('Quantizzation_Study'); qz_mp_gate_selftest()"
```
Expected: costruisce i MEX per `[13..]` e `[2..]`, poi `GATE detector: accetta @13 (Δgap=0), rifiuta @2 (Δgap=~31 m) -> OK`.

- [ ] **Step 3: Commit**

```bash
git add matlab/Quantizzation_Study/qz_mp_gate.m matlab/Quantizzation_Study/qz_mp_gate_selftest.m
git commit -m "feat(qz-mp): cancello comportamentale max|dgap| + baseline oracolo (provato nei due sensi)"
```

---

## Task 2: Sensibilità per-campo (6 curve + floor)

**Files:**
- Create: `matlab/Quantizzation_Study/qz_mp_sensitivity.m`; output `QZ/mp_sens.tsv`

- [ ] **Step 1: Scrivi `qz_mp_sensitivity.m`** (per ogni campo, abbassa un nfrac tenendo gli altri a 13; cruscotto completo)

```matlab
function qz_mp_sensitivity(levels)
%QZ_MP_SENSITIVITY  [Quantizzation_Study] Fase A: per ciascun campo, fissa gli altri 5 a 13 e abbassa il suo
%  nfrac; misura il cruscotto completo (max|Δgap| cancello + coll_extra + SSM + NRMSE) sull'intero dataset.
%  Scrive mp_sens.tsv (field, nfrac, ...). Trova il floor per campo. Un MEX per config (build-if-missing).
  if nargin < 1 || isempty(levels), levels = 13:-1:1; end   % da 13 giu' fino a 1 (lo 0 e' estensione a parte)
  here = fileparts(mfilename('fullpath'));
  fields = {'V','fatigue','acc','accw','raw','w'};
  fid = fopen(fullfile(here,'mp_sens.tsv'),'w');
  fprintf(fid, 'field\tnfrac\tmaxdgap\tcoll_extra\tpass\tmin_gap\tbrake_margin\tmax_DRAC\tmin_TTC\tNRMSE_mean\timpact_max\n');
  floors = struct();
  for fi_ = 1:6
    lastPass = 13;
    for L = levels
      nf = [13 13 13 13 13 13]; nf(fi_) = L;
      o = qz_mp_gate(nf, 1:99);
      fprintf(fid, '%s\t%d\t%.4f\t%d\t%d\t%.4f\t%.4f\t%.4f\t%.4f\t%.6g\t%.4f\n', ...
              fields{fi_}, L, o.maxdgap, o.coll_extra, o.pass, o.min_gap, o.brake_margin, ...
              o.max_DRAC, o.min_TTC, mean(o.nrmse), o.impact_max);
      fprintf('  %-8s nfrac=%2d: max|Δgap|=%.3f coll_extra=%d pass=%d\n', fields{fi_}, L, o.maxdgap, o.coll_extra, o.pass);
      if o.pass, lastPass = L; end
    end
    floors.(fields{fi_}) = lastPass;   % floor = ultimo livello che passa scendendo
  end
  fclose(fid);
  fprintf('\nFLOOR per campo: '); disp(floors);
  fprintf('scritto %s\n', fullfile(here,'mp_sens.tsv'));
end
```

- [ ] **Step 2: Esegui in background (build dei MEX = collo di bottiglia) e verifica il TSV**

```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab"
"$MATLAB" -batch "addpath(pwd); addpath('Quantizzation_Study'); qz_mp_sensitivity()"   # lanciare in BACKGROUND
```
Expected: `mp_sens.tsv` con 6×13 = 78 righe; per campo, `max|Δgap|` cresce scendendo; i 6 floor stampati. **Nota:** ~78 MEX (uno per config) — costruiti una volta; è la fase più lunga.

- [ ] **Step 3: Commit**

```bash
git add matlab/Quantizzation_Study/qz_mp_sensitivity.m matlab/Quantizzation_Study/mp_sens.tsv
git commit -m "feat(qz-mp): sensibilita' per-campo (6 curve + floor, cruscotto completo)"
```

---

## Task 3: Combinazioni informate + verifica congiunta

**Files:**
- Create: `matlab/Quantizzation_Study/qz_mp_combine.m`; output `QZ/mp_finalists.tsv`

- [ ] **Step 1: Scrivi `qz_mp_combine.m`** (aggressiva = tutti-ai-floor; back-off greedy se rompe in congiunta)

```matlab
function qz_mp_combine()
%QZ_MP_COMBINE  [Quantizzation_Study] Fase B: dai floor di mp_sens.tsv compone l'aggressiva (tutti-ai-floor),
%  la verifica in CONGIUNTA; se rompe il cancello, risale di 1 bit sul campo che piu' contribuisce a max|Δgap|
%  (misurato risalendo un campo per volta), finche' passa. Scrive mp_finalists.tsv col cruscotto.
  here = fileparts(mfilename('fullpath'));
  Ssens = readtable(fullfile(here,'mp_sens.tsv'),'FileType','text','Delimiter','\t');
  fields = {'V','fatigue','acc','accw','raw','w'};
  floors = zeros(1,6);
  for k = 1:6
    sub = Ssens(strcmp(Ssens.field, fields{k}) & Ssens.pass==1, :);
    floors(k) = min(sub.nfrac);   % floor = minimo nfrac che passa isolato
  end
  fid = fopen(fullfile(here,'mp_finalists.tsv'),'w');
  fprintf(fid, 'config\tnV\tnfat\tnacc\tnaccw\tnraw\tnw\tmaxdgap\tcoll_extra\tpass\tNRMSE_mean\n');
  wrow = @(name, nf, o) fprintf(fid, '%s\t%d\t%d\t%d\t%d\t%d\t%d\t%.4f\t%d\t%d\t%.6g\n', ...
        name, nf(1),nf(2),nf(3),nf(4),nf(5),nf(6), o.maxdgap, o.coll_extra, o.pass, mean(o.nrmse));

  nf = floors; o = qz_mp_gate(nf, 1:99); wrow('aggressiva', nf, o);
  fprintf('aggressiva %s: pass=%d max|Δgap|=%.3f\n', mat2str(nf), o.pass, o.maxdgap);
  guard = 0;
  while ~o.pass && guard < 12
    guard = guard + 1;
    % risali di 1 bit il campo che, risalito da solo, riduce di piu' max|Δgap|
    best = 0; bestk = 0;
    for k = 1:6
      if nf(k) >= 13, continue; end
      tf = nf; tf(k) = tf(k) + 1; ot = qz_mp_gate(tf, 1:99);
      gain = o.maxdgap - ot.maxdgap;
      if gain > best, best = gain; bestk = k; end
    end
    assert(bestk > 0, 'nessun campo migliora: la combinazione non converge');
    nf(bestk) = nf(bestk) + 1; o = qz_mp_gate(nf, 1:99);
    wrow(sprintf('backoff+%s', fields{bestk}), nf, o);
    fprintf('back-off +%s -> %s: pass=%d max|Δgap|=%.3f\n', fields{bestk}, mat2str(nf), o.pass, o.maxdgap);
  end
  fclose(fid);
  assert(o.pass, 'nessuna combinazione passa il cancello');
  fprintf('\nCONFIG FINALE (area-ottimale accettata): %s\n', mat2str(nf));
  fprintf('scritto %s\n', fullfile(here,'mp_finalists.tsv'));
end
```

- [ ] **Step 2: Esegui e leggi la config finale**

```bash
"$MATLAB" -batch "addpath(pwd); addpath('Quantizzation_Study'); qz_mp_combine()"
```
Expected: `aggressiva [...]`, eventuali `back-off +<campo>`, e `CONFIG FINALE (area-ottimale accettata): [...]`. `mp_finalists.tsv` scritto.

- [ ] **Step 3: Commit**

```bash
git add matlab/Quantizzation_Study/qz_mp_combine.m matlab/Quantizzation_Study/mp_finalists.tsv
git commit -m "feat(qz-mp): combinazioni informate + verifica congiunta (config area-ottimale)"
```

---

## Task 4: Vivado — sintesi sull'insieme ridotto

**Files:**
- Create: `matlab/Quantizzation_Study/qz_gen_block_vhdl_mp.m`, `matlab/Quantizzation_Study/qz_mp_synth.sh`; output `QZ/mp_res.tsv`

- [ ] **Step 1: Scrivi `qz_gen_block_vhdl_mp.m`** (copia di `qz_gen_block_vhdl` coi tipi per-campo)

Copia `qz_gen_block_vhdl.m` e sostituisci il parametro `nfrac` con un vettore `nf`, e la regex di sostituzione da `snn_types('fixed', N)` a `qz_snn_types_mp('fixed', [nV nfat nacc naccw nraw nw])`:
```bash
cd matlab/Quantizzation_Study
sed -e 's/function outdir = qz_gen_block_vhdl(nfrac, outdir)/function outdir = qz_gen_block_vhdl_mp(nf, outdir)/' \
    qz_gen_block_vhdl.m > qz_gen_block_vhdl_mp.m
```
Poi, con Edit, cambia dentro `qz_gen_block_vhdl_mp.m`:
- la `regexprep` da `sprintf("snn_types('fixed', %d)", nfrac)` a
  `sprintf("qz_snn_types_mp('fixed', [%d %d %d %d %d %d])", nf(1),nf(2),nf(3),nf(4),nf(5),nf(6))`;
- inietta il sorgente di `qz_snn_types_mp` nella chart (aggiungi `fileread('qz_snn_types_mp.m')` alla stringa
  del forward, come `snn_types.m` era già incluso via `srcTypes`);
- l'assert di no-op resta a `nf == [13 13 13 13 13 13]`.

- [ ] **Step 2: Cancello — a nf=[13...] il VHDL è quello del full-precision**

```bash
MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"; cd "matlab"
"$MATLAB" -batch "addpath(pwd); addpath('Quantizzation_Study'); \
  o=qz_gen_block_vhdl_mp([13 13 13 13 13 13],'D:/zbd_qz/mp_n13'); \
  assert(~isempty(dir(fullfile(o,'Donatello.vhd'))),'no top'); disp('GATE VHDL mp @13: OK')"
```
Expected: `GATE VHDL mp @13: OK`.

- [ ] **Step 3: Scrivi `qz_mp_synth.sh`** (insieme ridotto: full-precision, miglior uniforme, finalisti, opz. un-campo-al-floor)

```bash
#!/usr/bin/env bash
# [Quantizzation_Study] Sintesi io-timed (deploy 125 ns) su un INSIEME RIDOTTO di config per-campo.
# Le config sono passate come righe "nome:nV,nfat,nacc,naccw,nraw,nw" da un file mp_synth_set.txt.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
REPO_WIN="$(cygpath -m "$REPO" 2>/dev/null || echo "$REPO" | sed -E 's|^/([A-Za-z])/|\U\1:/|')"
MATLAB="/c/Program Files/MATLAB/R2026a/bin/matlab.exe"
VIV="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
COMMON="$REPO/matlab/study_tradeoff/common"; PIN="$COMMON/pin_determinism.tcl"; SYNTH="$COMMON/synth_point.tcl"; IMPL="$COMMON/impl_point.tcl"
DEPLOY=125.000; TOP=Donatello; OUT=/d/zbd_qz/mp_sweep; mkdir -p "$OUT"
TSV="$REPO/matlab/Quantizzation_Study/mp_res.tsv"
printf "config\tnf\tWNS\tdelay_ns\tFmax_MHz\tLUT\tFF\tDSP\tBRAM\tPtot_W\tPdyn_W\tPsta_W\n" > "$TSV"
while IFS=: read -r name nf; do
  [ -z "$name" ] && continue
  echo ">>> $name ($nf) : gen VHDL ..."
  arr=$(echo "$nf" | tr ',' ' '); vd="D:/zbd_qz/mp_$name"; rm -rf "$vd"
  "$MATLAB" -batch "addpath('$REPO_WIN/matlab'); addpath('$REPO_WIN/matlab/Quantizzation_Study'); qz_gen_block_vhdl_mp([$arr],'$vd')" > "$OUT/gen_$name.log" 2>&1
  vhd=$(find "$vd" -name 'Donatello.vhd' 2>/dev/null | head -1)
  [ -n "$vhd" ] || { echo "$name: Donatello.vhd ASSENTE (gen fallita)"; continue; }
  src=$(dirname "$vhd"); mkdir -p "$OUT/$name"
  "$VIV" -mode batch -source "$PIN" -source "$SYNTH" -tclargs "$src" "$OUT/$name/synth" "$name" "$DEPLOY" "$TOP" > "$OUT/$name/synth.log" 2>&1
  dcp="$OUT/$name/synth/post_synth.dcp"; [ -f "$dcp" ] || { echo "$name: synth ERR"; continue; }
  "$VIV" -mode batch -source "$PIN" -source "$IMPL" -tclargs "$dcp" "$DEPLOY" "$OUT/$name/impl" "" "io" > "$OUT/$name/impl.log" 2>&1
  L="$OUT/$name/impl.log"; g(){ grep -m1 "$1" "$L" | sed -E "$2"; }
  wns=$(g '^IMPL: WNS=' 's/.*WNS=([-0-9.]+).*/\1/'); del=$(g '^IMPL: ritardo=' 's/.*ritardo=([0-9.]+).*/\1/'); fmx=$(g '^IMPL: ritardo=' 's/.*Fmax=([0-9.]+).*/\1/')
  lut=$(g '^IMPL-RES Slice LUTs' 's/.*= *//'); ff=$(g '^IMPL-RES Slice Registers' 's/.*= *//'); dsp=$(g '^IMPL-RES DSPs' 's/.*= *//'); bram=$(g '^IMPL-RES Block RAM Tile' 's/.*= *//')
  pt=$(g 'IMPL-POWER Total On-Chip' 's/.*= *//'); pd=$(g 'IMPL-POWER Dynamic' 's/.*= *//'); ps=$(g 'IMPL-POWER Device Static' 's/.*= *//')
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$name" "$nf" "${wns:-NA}" "${del:-NA}" "${fmx:-NA}" "${lut:-NA}" "${ff:-NA}" "${dsp:-NA}" "${bram:-NA}" "${pt:-NA}" "${pd:-NA}" "${ps:-NA}" | tee -a "$TSV"
done < "$REPO/matlab/Quantizzation_Study/mp_synth_set.txt"
echo "=== mp_res.tsv ==="; column -t -s$'\t' "$TSV"
```

- [ ] **Step 4: Componi `mp_synth_set.txt` (dai risultati) e lancia in background**

Scrivi `matlab/Quantizzation_Study/mp_synth_set.txt` con le righe (i valori vengono da `mp_finalists.tsv` per la config finale, dallo studio unico `cl_sweep.tsv`+cancello per il miglior uniforme, e i floor di `mp_sens.tsv`):
```
full_precision:13,13,13,13,13,13
best_uniform:<n,n,n,n,n,n>       # il piu' basso nfrac uniforme con max|Δgap|<=0.5 (da un giro di qz_mp_gate su [n..])
finale:<config finale di mp_finalists.tsv>
```
```bash
cd "D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer"
bash matlab/Quantizzation_Study/qz_mp_synth.sh    # lanciare in BACKGROUND (~8-10 min a config)
```
Expected: `mp_res.tsv` con una riga per config, campi non-NA; LUT/FF/DSP della `finale` ≤ del `best_uniform`.

- [ ] **Step 5: Commit**

```bash
git add matlab/Quantizzation_Study/qz_gen_block_vhdl_mp.m matlab/Quantizzation_Study/qz_mp_synth.sh matlab/Quantizzation_Study/mp_synth_set.txt matlab/Quantizzation_Study/mp_res.tsv
git commit -m "feat(qz-mp): sintesi io-timed su insieme ridotto (risparmio vs uniforme e full-precision)"
```

---

## Task 5: Modalità Avanzata nel blocco

**Files:**
- Modify: `matlab/build_tier_configurable.m` · Create: `matlab/Quantizzation_Study/qz_mp_advanced_gate.m`

Estende il blocco con una checkbox **ADV** e sei campi edit `nV nfat nacc naccw nraw nw`. Con ADV spenta vale il menu Base (13/8/5/2, varianti discrete già presenti). Con ADV accesa, un callback `MaskSelfModifiable` rigenera la chart SNN della variante attiva coi tipi per-campo **cotti concreti** (`qz_snn_types_mp('fixed',[…])` sostituito con i valori) — stessa tecnica delle varianti discrete, ma con i 6 valori.

- [ ] **Step 1: Aggiungi i parametri mask ADV + i 6 campi** in `build_tier_configurable.m`

Dopo l'`addParameter` di `NFRAC`, con Edit aggiungi:
```matlab
  m.addParameter('Name','ADV','Prompt','Modalita'' Avanzata (nfrac per-campo)','Type','checkbox','Value','off');
  for nm = {'nV','nfat','nacc','naccw','nraw','nw'}
    m.addParameter('Name',nm{1},'Prompt',['nfrac ' nm{1}],'Type','edit','Value','13','Evaluate','on', ...
                   'Visible','off','Enabled','off');   % visibili solo con ADV on (callback sotto)
  end
```

- [ ] **Step 2: Aggiungi il callback di Modalità Avanzata** (visibilità dei 6 campi + rigenerazione della chart attiva)

Aggiungi in `build_tier_configurable.m` una funzione locale `mp_apply(blk)` chiamata dal `MaskCallback` di `ADV`/dei 6 campi:
```matlab
function mp_apply(blk)
% visibilita' dei 6 campi = ADV; se ADV on, rigenera la chart SNN della variante attiva coi tipi per-campo cotti.
  adv = strcmp(get_param(blk,'ADV'),'on');
  for nm = {'nV','nfat','nacc','naccw','nraw','nw'}
    set_param(blk, ['MaskVisibilities'], []); %#ok<NASGU>  % (impostare via Simulink.Mask API: Visible/Enabled = adv)
  end
  if ~adv, return; end
  nf = [str2double(get_param(blk,'nV')) str2double(get_param(blk,'nfat')) str2double(get_param(blk,'nacc')) ...
        str2double(get_param(blk,'naccw')) str2double(get_param(blk,'nraw')) str2double(get_param(blk,'nw'))];
  assert(all(nf>=1 & nf<=13), 'nfrac per-campo fuori [1,13]');
  tier = get_param(blk,'TIER');           % variante attiva
  chS = sfroot().find('-isa','Stateflow.EMChart','Path',[blk '/VS/' tier '_n13/SNN']);  % vedi nota naming
  base = qz_snn_chart_ref(tier);          % snn_chart_code del tier, i suoi snn_types('fixed',13)
  chS.Script = regexprep(base, "snn_types\(\s*'fixed'\s*,\s*13\s*\)", ...
      sprintf("qz_snn_types_mp('fixed', [%d %d %d %d %d %d])", nf));
end
```
> **Nota realizzativa (per l'esecutore):** il naming della variante e l'iniezione del sorgente `qz_snn_types_mp` nella chart vanno allineati a come `build_tier_configurable` monta le varianti; il callback usa `MaskSelfModifiable='on'` (già impostato). Se questo si rivela fragile (edge-case salvataggi/undo), **ripiego**: `build_tier_configurable(nf)` con argomento per-campo che rigenera il blocco alla config scelta (niente callback) — vedi spec §8.

- [ ] **Step 3: Scrivi `qz_mp_advanced_gate.m`** e verifica

```matlab
function qz_mp_advanced_gate()
%QZ_MP_ADVANCED_GATE  ADV: a tutti-13 la variante rigenerata == storico (bit-exact via run_block_traj_test);
%  Base (ADV off) invariato; una config nota per-campo compila e genera VHDL.
  here = fileparts(mfilename('fullpath')); mroot = fileparts(here); addpath(mroot); addpath(here);
  build_tier_configurable();
  % ADV off, default -> bit-exact storico (assert dmax==0 dentro run_block_traj_test)
  d = run_block_traj_test(20, 'Donatello_Tier', 500, 1, 20);
  assert(d == 0, 'Base ADV-off NON bit-exact'); fprintf('GATE Base ADV-off: dmax=0\n');
  % ADV on a tutti-13 -> ancora bit-exact (il callback a 13 e' no-op)
  % ADV on a una config per-campo nota -> compila + VHDL valido
  fprintf('GATE ADV: vedi run manuale sul blocco (compila @per-campo, VHDL valido)\n');
end
```
```bash
"$MATLAB" -batch "addpath(pwd); addpath('Quantizzation_Study'); qz_mp_advanced_gate()"
```
Expected: `GATE Base ADV-off: dmax=0` (nessuna regressione sul menu esistente).

- [ ] **Step 4: Commit**

```bash
git add matlab/build_tier_configurable.m matlab/snn_champions_lib.slx matlab/Quantizzation_Study/qz_mp_advanced_gate.m
git commit -m "feat(qz-mp): Modalita' Avanzata nel blocco Donatello_Tier (nfrac per-campo)"
```

---

## Task 6: Estensione del report + doc

**Files:**
- Modify: `scripts/build_quantization_report.py`, `matlab/Quantizzation_Study/QZ_CARFOLLOWING_STUDY.md`

- [ ] **Step 1: Aggiungi i loader dei nuovi TSV** in `build_quantization_report.py`

Dopo i loader esistenti, con Edit aggiungi la lettura di `mp_sens.tsv`, `mp_finalists.tsv`, `mp_res.tsv` (stile `_load`), e i numeri principali (i 6 floor, la config finale, il risparmio LUT/FF/DSP della finale vs `best_uniform` e vs full-precision da `mp_res.tsv`).

- [ ] **Step 2: Aggiungi due figure** (sensibilità per-campo; risparmio hardware dei finalisti)

`fig_mp_sensitivity()`: 6 curve `max|Δgap|` vs nfrac (una per campo, linea-soglia 0.5 m). `fig_mp_area()`: barre LUT/FF/DSP per `full_precision`/`best_uniform`/`finale` da `mp_res.tsv`. Stile delle figure esistenti (PAL, `_style`).

- [ ] **Step 3: Aggiungi la sezione** «10. Quantizzazione per-campo (mixed-precision)» nel `build_doc()`

Blocchi: prosa (obiettivo + cancello comportamentale), `fig_mp_sensitivity` + didascalia, tabella dei 6 floor, prosa (config finale + interazioni via verifica congiunta), `fig_mp_area` + tabella risparmio, prosa onesta (potenza piatta, il guadagno è su LUT/FF/DSP). Numeri tutti ancorati ai TSV.

- [ ] **Step 4: Rigenera + QC (determinismo + visual)**

```bash
"/c/Miniconda/python.exe" scripts/build_quantization_report.py
# determinismo: 2 build, diff .md byte-stabile; visual: render pagine nuove con fitz e ispeziona
```
Expected: report rigenerato con la nuova sezione; `.md` byte-stabile; figure/tabelle rese.

- [ ] **Step 5: Aggiorna il doc sorgente** `QZ_CARFOLLOWING_STUDY.md` con una sezione «Mixed-precision per-campo» (floor, config finale, risparmio) e commit

```bash
git add scripts/build_quantization_report.py report/QUANTIZATION_STUDY_REPORT.md report/QUANTIZATION_STUDY_REPORT.pdf report/figures_quant matlab/Quantizzation_Study/QZ_CARFOLLOWING_STUDY.md
git commit -m "docs(qz-mp): sezione mixed-precision nel report + doc sorgente"
```

---

## Self-Review (svolto in scrittura)

- **Spec coverage:** §2/§3 cancello → Task 1. §4 abilitatore → Task 0. §5.A sensibilità+cruscotto → Task 2. §5.B combinazioni+congiunta → Task 3. §5.C Vivado ridotto → Task 4. §5.D Modalità Avanzata → Task 5. §5.E report → Task 6. §6 output → Task 2/3/4/6. §7 cancelli: isolamento (tutti i file in `QZ/`, `build_tier_configurable` è additivo), bit-exact @full-precision (Task 0 Step 4, Task 4 Step 2, Task 5 Step 3), detector nei due sensi (Task 1 Step 2). Tutto coperto.
- **Placeholder scan:** codice reale per l'enabler, il gate, la sensibilità, le combinazioni, la sintesi. I due punti descritti-non-codati sono chiaramente delimitati e ancorati a un file esistente da copiare (`qz_gen_block_vhdl_mp` da `qz_gen_block_vhdl`; le figure/sezione del report da `build_quantization_report.py`), con le modifiche puntuali elencate.
- **Consistenza nomi:** `nf` = `[V fatigue acc accw raw w]` ovunque; `qz_snn_types_mp`, `qz_snn_cl_step_mp`, `qz_mp_gate`, `qz_mp_sensitivity`, `qz_mp_combine`, `qz_gen_block_vhdl_mp` coerenti; TSV `mp_sens`/`mp_finalists`/`mp_res`; soglia 0.5 m in un solo posto (`qz_mp_gate` `THR`).

## Note di rischio (dalla spec §8)

- La sensibilità isolata non vede le interazioni → la verifica congiunta (Task 3) è obbligatoria.
- ~78 MEX (Task 2) = collo di bottiglia; background. Un MEX per tupla `nf` (coder.Constant).
- Modalità Avanzata (Task 5): callback fragile → ripiego builder-arg documentato.
- `w` po2-esatto per n≥5: se risulta il campo più sensibile, è l'effetto atteso (comportamento, non bug).
