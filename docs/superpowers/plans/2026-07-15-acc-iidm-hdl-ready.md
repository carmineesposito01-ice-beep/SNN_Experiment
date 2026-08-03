# SP3 — ACC-IIDM HDL-Ready Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** rendere l'ACC-IIDM sintetizzabile in fixed-point, così che `Donatello_ACC_IIDM` (catena
`s,v,dv,v_l → accel`) diventi HDL-Ready e il confronto MPC↔SNN possa contare il costo in silicio del
controllore **completo**, non della sola rete.

**Architettura:** `acc_iidm_open` diventa **type-parametrico** come `snn_core` (una sola fonte: `T=[]` →
double, `T=acc_types('fixed',f)` → fixed). Niente LUT e niente Newton-Raphson: HDL Coder genera `sqrt`, `tanh`
e `x^4` nativamente, e accetta la divisione con `RoundingMethod='Zero'` (misurato). Il numero di bit
frazionari si sceglie con uno **sweep** contro un budget **derivato dalla misura**.

**Tech Stack:** MATLAB R2026a · Fixed-Point Designer (`fi`) · Simulink/Stateflow · HDL Coder · Vivado 2026.1
(`C:\AMDDesignTools\2026.1\Vivado\bin\vivado.bat`, part `xc7z020clg400-1`).

**Spec:** `docs/superpowers/specs/2026-07-15-acc-iidm-hdl-ready-design.md`

---

## Convenzioni (valide per tutti i task)
- **Dir:** `matlab/`. Batch: `matlab -batch "cd('D:/Project_MBSE/1.Reti Neurali/Rete_SNN_Test/CF_FSNN/.worktrees/Simulink_Importer/matlab'); <cmd>"`
- **Commit** conventional, **senza `Co-Authored-By`**; push libero su `Simulink_Importer`.
- **File estranei, MAI nei `git add`**: `closed_loop_demo.slx`, `slblocks.m`, `axi/build/phase_b/results.csv`.
- **Verifiche sul DATASET, mai su un caso singolo**: riportare sempre *quanti su quanti*.
- **Cancelli che devono restare verdi**: `run_plant_parity` · `run_block_sync_check` · `run_block_traj_test` ·
  `run_block_acciidm_test` · `run_block_closed_loop_test` · `run_block_hdl_gate`.
- **Gotcha codegen già pagati** (non ri-scoprirli): `if isempty(<persistent>)` va usato **letteralmente** (un
  test sul valore fallisce con *«undefined on some execution paths»*); una variabile **non può cambiare tipo**
  → usare `x(:) = ...`; il messaggio vero di un errore di chart si ottiene dando lo script a `codegen`.

## File Structure
```
matlab/acc_types.m                   # NUOVO — prototipi di tipo dell'IIDM (modello: snn_types.m)
matlab/acc_iidm_open.m               # MODIFICA — type-parametrico (double + fixed), unica fonte
matlab/run_acc_fixed_sweep.m         # NUOVO — budget derivato + sweep dei bit frazionari
matlab/build_hdl_variants.m          # MODIFICA — Donatello_ACC_IIDM fixed/HDL-ready + Description
matlab/run_block_hdl_gate.m          # MODIFICA — generalizzato ai blocchi a 1 uscita
matlab/snn_cl_step.m                 # MODIFICA — passa i tipi all'IIDM (riferimento = path fixed)
matlab/run_block_acciidm_test.m      # MODIFICA — riferimento = path fixed
matlab/run_block_closed_loop_test.m  # MODIFICA — riferimento = path fixed
matlab/build_traj_mex.m              # (rigenerare snn_cl_step_mex)
scripts/synth_acc_iidm.tcl           # NUOVO — sintesi OOC xc7z020 (LUT/DSP/Fmax/slack/path critico)
document/SP3_ACC_IIDM_HDL.md         # NUOVO — doc di processo, coi numeri OOC
document/SP2_ACC_IIDM.md             # MODIFICA — correggere la claim smentita
matlab/README.md · document/SESSION_RESUME.md   # MODIFICA — allineamento
```

---

## Task 1: `acc_types` — i tipi, sui range MISURATI

**Files:** Create `matlab/acc_types.m`

I range vengono dalla misura su 60 traiettorie × 1000 step (spec §3), **non** da stime. Margine ≥2× sul
massimo osservato, perché il dataset non è il mondo.

- [ ] **Step 1: scrivi `matlab/acc_types.m`**

```matlab
function T = acc_types(dt, nfrac)
%ACC_TYPES  Prototipi di tipo per `acc_iidm_open` type-parametrizzato (modello: snn_types.m).
%  dt = 'double' (riferimento + plant) | 'fixed' (blocco HDL-ready).
%  nfrac (opz., default 13) = bit frazionari del path fixed; i bit INTERI restano FISSI (il range non
%  cambia), varia solo la risoluzione -> e' la manopola dello sweep (run_acc_fixed_sweep), come
%  snn_types/run_fixed_sweep fanno per la rete.
%
%  I bit interi vengono dai range MISURATI sul dataset (60 traj x 1000 step, spec §3), con margine >=2x:
%    st  : s,v,dv,v_l,s_safe,s_star   max misurato  465.77  -> int 10 (|x|<1024)
%    par : v0,T,s0,a,b                max ~45 (bound del decode) -> int  6 (|x|<64)
%    acc : v_free,a_z,a_iidm,a_cah,a_blend,alf,a_l_bar,dd,z,dv2/s
%                                     min misurato -288.33  -> int 10 (|x|<1024)
%    out : accel                      clampata a [-9, a]     -> int  4 (|x|<16)
  if nargin < 2, nfrac = 13; end
  switch dt
    case 'double'
      z = double([]);
      T = struct('st', z, 'par', z, 'acc', z, 'out', z);
    case 'fixed'
      f = nfrac;
      T = struct( ...
        'st',  fi([], true, 11 + f, f), ...   % Q10.f
        'par', fi([], true,  7 + f, f), ...   % Q6.f
        'acc', fi([], true, 11 + f, f), ...   % Q10.f
        'out', fi([], true,  5 + f, f));      % Q4.f
    otherwise
      error('acc_types:dt', 'dt deve essere ''double'' o ''fixed''');
  end
end
```

- [ ] **Step 2: verifica che i tipi coprano i range misurati**

Run:
```
matlab -batch "cd('<matlabdir>'); T = acc_types('fixed', 13);
r = @(p) double([lowerbound(p) upperbound(p)]);
fprintf('st  %s\n', mat2str(r(T.st)));  fprintf('par %s\n', mat2str(r(T.par)));
fprintf('acc %s\n', mat2str(r(T.acc))); fprintf('out %s\n', mat2str(r(T.out)));"
```
Expected: `st` e `acc` coprono `[-1024, 1024)` (i massimi misurati sono 465.77 e −288.33 ⇒ margine ≥2×);
`par` copre `[-64, 64)`; `out` copre `[-16, 16)` (accel è clampata a ±9).
Se un range NON copre il massimo misurato con margine ≥2× → **fermarsi**: i bit interi sono sbagliati, non
alzare i frazionari.

- [ ] **Step 3: Commit**

```bash
git add matlab/acc_types.m
git commit -m "feat(sp3): acc_types - prototipi di tipo dell'IIDM sui range misurati (modello snn_types)"
```

---

## Task 2: `acc_iidm_open` type-parametrico — **il double non si muove di un bit**

**Files:** Modify `matlab/acc_iidm_open.m`

Il cancello di questo task è `run_plant_parity`: se cambia anche di `1e-16`, il path double è stato toccato.

- [ ] **Step 1: cattura la BASELINE prima di toccare**

Run: `matlab -batch "cd('<matlabdir>'); run_plant_parity"`
Expected: `s|err|=0.00e+00  v|err|=0.00e+00  [PASS]` su `highway_sinus`, `urban_brake`, `cruise_const` +
`ALL PLANT PARITY PASS`. **Trascrivere l'output**: è il riferimento dello Step 4.

- [ ] **Step 2: aggiungi il parametro `T` mantenendo il double IDENTICO**

In `matlab/acc_iidm_open.m` sostituisci la riga della firma:
```matlab
function accel = acc_iidm_open(s, v, dv, v_l, p, rst) %#codegen
```
con:
```matlab
function accel = acc_iidm_open(s, v, dv, v_l, p, rst, T) %#codegen
```
e, subito **dopo** il blocco di commenti dell'header (prima di `DT = 0.1;`), inserisci:
```matlab
  % Type-parametrico come snn_core: T assente/vuoto -> double (riferimento + plant cf_plant_lib), T
  % popolato -> fixed (blocco HDL-ready). UNICA fonte: due implementazioni divergerebbero in silenzio.
  if nargin < 7 || isempty(T), T = acc_types('double'); end
  isFx = ~isa(T.out, 'double');
```
**Non toccare nient'altro in questo task.** Con `T` double, `isFx` è false e il corpo resta quello di prima.

- [ ] **Step 3: aggiorna i due chiamanti esistenti (firma a 7 argomenti)**

In `matlab/build_plant_lib.m`, funzione `plant_code()`, sostituisci:
```matlab
    '  accel = acc_iidm_open(s, v, dv, vl, [v0; T; s0; a; b], rst);'
```
con:
```matlab
    '  accel = acc_iidm_open(s, v, dv, vl, [v0; T; s0; a; b], rst, acc_types(''double''));'
```
In `matlab/snn_cl_step.m` sostituisci:
```matlab
  accel = acc_iidm_open(x_phys(1), x_phys(2), x_phys(3), x_phys(4), p, rst);
```
con:
```matlab
  accel = acc_iidm_open(x_phys(1), x_phys(2), x_phys(3), x_phys(4), p, rst, acc_types('double'));
```

- [ ] **Step 4: il double NON si è mosso**

Run: `matlab -batch "cd('<matlabdir>'); build_plant_lib; clear PLANT acc_iidm_open; run_plant_parity"`
Expected: **identico allo Step 1**, `ALL PLANT PARITY PASS` con `0.00e+00` su 3/3.
Se cambia anche di poco → **fermarsi**: il type-parametrico ha toccato il double. **Non** aggiustare le
tolleranze; confrontare il corpo con `git diff`.

- [ ] **Step 5: rigenera il MEX e ri-verifica i cancelli a valle**

Run: `matlab -batch "cd('<matlabdir>'); build_traj_mex; run_block_acciidm_test(12,1,400); run_block_closed_loop_test(1,40,400,'train')"`
Expected: `dmax(accel) = 0` e `dmax = 0`. (Il blocco è ancora double: qui non deve cambiare nulla.)

- [ ] **Step 6: Commit**

```bash
git add matlab/acc_iidm_open.m matlab/build_plant_lib.m matlab/snn_cl_step.m matlab/cf_plant_lib.slx
git commit -m "refactor(sp3): acc_iidm_open type-parametrico (T) - path double invariato bit per bit

run_plant_parity identico alla baseline (0.00e+00 su 3/3): prova che l'aggiunta di T non ha
toccato il riferimento. Il corpo fixed arriva nel task successivo."
```

---

## Task 3: il path **fixed** + il budget **derivato** + lo sweep

**Files:** Modify `matlab/acc_iidm_open.m`; Create `matlab/run_acc_fixed_sweep.m`

- [ ] **Step 1: porta il corpo in fixed, dietro `isFx`**

In `matlab/acc_iidm_open.m` sostituisci il blocco costanti + stato persistente:
```matlab
  DT = 0.1; ALPHA = exp(-DT/1.0); COOL = 0.99;
```
con:
```matlab
  % ALPHA = exp(-DT/1.0) e' una COSTANTE: va bakata. `exp` e' l'unica delle operazioni usate che HDL
  % Coder NON genera (verificato 2026-07-15) - ed e' anche il motivo per cui la sigmoide richiese una
  % LUT, mentre `tanh` e `sqrt` sono nativi (spec §2).
  DT = 0.1; ALPHA = 0.90483741803595952; COOL = 0.99;   % ALPHA == exp(-0.1)
```

Poi sostituisci **il corpo aritmetico** (da `sab = ...` fino a `accel = min(max(accel, -9), a);`) con:
```matlab
  % fimath con RoundingMethod 'Zero': e' l'UNICA forma di divisione che HDL Coder genera per tipi
  % SIGNED ('Nearest' -> rifiutata; 'Floor' vale solo per unsigned). Verificato 2026-07-15, spec §2.
  if isFx
    FM = fimath('RoundingMethod', 'Zero', 'OverflowAction', 'Saturate', ...
                'ProductMode', 'SpecifyPrecision', 'ProductWordLength', T.acc.WordLength, ...
                'ProductFractionLength', T.acc.FractionLength, ...
                'SumMode', 'SpecifyPrecision', 'SumWordLength', T.acc.WordLength, ...
                'SumFractionLength', T.acc.FractionLength);
    sq = setfimath(cast(s, 'like', T.st), FM);  vq = setfimath(cast(v, 'like', T.st), FM);
    dq = setfimath(cast(dv, 'like', T.st), FM);
    v0 = setfimath(cast(v0, 'like', T.par), FM); Tt = setfimath(cast(T_, 'like', T.par), FM);
    s0 = setfimath(cast(s0, 'like', T.par), FM); a = setfimath(cast(a, 'like', T.par), FM);
    b  = setfimath(cast(b,  'like', T.par), FM);
  else
    sq = s; vq = v; dq = dv; Tt = T_;
  end

  sab    = cast(max(sqrt(a*b), 1e-6), 'like', T.par);
  s_star = cast(s0 + max(vq*Tt + vq*dq/(2*sab), 0), 'like', T.st);
  s_safe = cast(max(sq, 2.0), 'like', T.st);
  vv0    = cast(min(vq/v0, 10), 'like', T.acc);
  v_free = cast(a*(1 - vv0^4), 'like', T.acc);
  z      = cast(min(s_star/s_safe, 20), 'like', T.acc);
  below  = (vq <= v0);
  a_z    = cast(a*(1 - z^2), 'like', T.acc);
  if z < 1
    if below, a_iidm = cast(v_free*(1 - z^2), 'like', T.acc); else, a_iidm = cast(v_free, 'like', T.acc); end
  else
    if below, a_iidm = cast(a_z, 'like', T.acc); else, a_iidm = cast(v_free + a_z, 'like', T.acc); end
  end
  a_l_bar = cast(min(alf, a), 'like', T.acc);
  a_cah   = cast(a_l_bar - max(dq,0)^2/(2*s_safe + 1e-6), 'like', T.acc);
  a_cah   = cast(min(max(a_cah, -9), a), 'like', T.acc);
  dd      = cast((a_iidm - a_cah)/(b + 1e-6), 'like', T.acc);
  a_blend = cast((1-COOL)*a_iidm + COOL*(a_cah + b*tanh(dd)), 'like', T.acc);
  if a_iidm >= a_cah, ac = cast(a_iidm, 'like', T.out); else, ac = cast(a_blend, 'like', T.out); end
  accel = cast(min(max(ac, -9), a), 'like', T.out);
```
Rinomina la variabile locale `T` (il time-headway IDM) in `T_` **ovunque nel file** — `T` è ora il parametro
dei tipi. Righe da cambiare: `v0 = max(p(1),1e-3); T = max(p(2),1e-3);` → `T_ = max(p(2),1e-3);` e l'uso in
`s_star`. Aggiorna anche il commento dell'header (`p : [v0; T; s0; a; b]` resta, è il vettore).
Adegua l'OU allo stesso schema:
```matlab
  alf = cast(ALPHA*alf + (1-ALPHA)*((cast(v_l,'like',T.st) - vlp)*10), 'like', T.acc);  % /DT == *10
  vlp = cast(v_l, 'like', T.st);
```

- [ ] **Step 2: il double DEVE essere ancora invariato**

Run: `matlab -batch "cd('<matlabdir>'); build_plant_lib; clear PLANT acc_iidm_open; run_plant_parity"`
Expected: **ancora** `ALL PLANT PARITY PASS`, `0.00e+00` su 3/3.
Se si è mosso: i `cast(..., 'like', T.x)` con `T` double sono no-op, quindi un cambio significa che hai
alterato **l'ordine delle operazioni** (es. `(v_l-vlp)*10` vs `(v_l-vlp)/DT` NON sono bit-identici in
floating point). Ripristina la forma originale nel ramo double invece di aggiustare le tolleranze.

> Se `*10` e `/DT` divergono in double: metti `if isFx, dvl = (v_l - vlp)*10; else, dvl = (v_l - vlp)/DT; end`
> e commenta **perché** (`/0.1` non è esatto in binario; `*10` nemmeno, ma non danno lo stesso bit).

- [ ] **Step 3: scrivi `matlab/run_acc_fixed_sweep.m` — il budget si MISURA, non si sceglie**

```matlab
function tab = run_acc_fixed_sweep(fracs, nTraj)
%RUN_ACC_FIXED_SWEEP  [SP3] Quanti bit frazionari servono all'IIDM in fixed?
%  Il budget NON e' un numero magico: 0.028 (spec SP2) e' un errore su v0 [m/s], non su accel [m/s^2].
%  Criterio DERIVATO (stesso spirito di DECODE_LUT_SWEEP §5bis: l'approssimazione non deve diventare
%  la fonte d'errore DOMINANTE):
%    E_snn  = |accel(IIDM double, params SNN FIXED) - accel(IIDM double, params SNN DOUBLE)|
%             ... l'errore in accel che il progetto ha GIA' accettato a monte
%    E_iidm = |accel(IIDM FIXED) - accel(IIDM double)|   a parita' di parametri
%  Si passa se E_iidm < E_snn (p99 e max). Si sceglie il MINIMO f che passa.
  if nargin < 1 || isempty(fracs), fracs = 8:2:18; end
  if nargin < 2 || isempty(nTraj), nTraj = 60; end          % dataset intero
  here = fileparts(mfilename('fullpath'));
  ds = load(fullfile(here,'test_dataset.mat')); tr = ds.trajectories;
  d  = load(fullfile(here,'champions_export.mat')); ch = d.champions;
  if iscell(ch), ch = [ch{:}]; end
  c = ch(find(arrayfun(@(x) strcmp(char(string(x.name)),'Donatello'), ch),1));
  W = champ_weights(c); Tp = numerictype(1,21,13); Td = acc_types('double');
  nTraj = min(nTraj, numel(tr));

  % --- E_snn: quanto la quantizzazione GIA' accettata della rete sposta l'accel ---
  Esnn = [];
  for i = 1:nTraj
    val = double(tr{i}.val);
    Rfx = double(snn_traj_fixed_r16_mex(val, W));            % rete FIXED
    clear acc_iidm_open; aF = zeros(size(val,2),1);
    for k = 1:size(val,2)
      p = double(snn_decode_lut(fi(Rfx(k,:).', Tp), 64));
      aF(k) = acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k), p, k==1, Td);
    end
    snn_core([], [], snn_types('fixed',13), 'reset');         %#ok<*NASGU>
    clear acc_iidm_open; aD = zeros(size(val,2),1);
    Tdbl = snn_types('double'); snn_core(zeros(4,1), W, Tdbl, true);
    for k = 1:size(val,2)
      xn  = snn_normalize(val(:,k), W.norm);
      raw = snn_core(xn, W, Tdbl, false);                     % rete DOUBLE
      p   = snn_decode(double(raw), c.param_lo, c.param_hi, c.decode_offset, c.logit_tau);
      aD(k) = acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k), p, k==1, Td);
    end
    Esnn = [Esnn; abs(aF - aD)]; %#ok<AGROW>
  end
  bud_p99 = prctile(Esnn, 99); bud_max = max(Esnn);
  fprintf('BUDGET derivato (footprint in accel della quantizzazione SNN, %d traj):\n', nTraj);
  fprintf('   p99 = %.6g   max = %.6g   [m/s^2]\n\n', bud_p99, bud_max);

  % --- E_iidm(f): errore aggiunto dall'IIDM in fixed, a parita' di parametri ---
  tab = zeros(numel(fracs), 3);
  fprintf('%-6s %12s %12s %8s\n', 'nfrac', 'E_iidm p99', 'E_iidm max', 'esito');
  for j = 1:numel(fracs)
    f = fracs(j); Tf = acc_types('fixed', f); E = [];
    for i = 1:nTraj
      val = double(tr{i}.val);
      R = double(snn_traj_fixed_r16_mex(val, W));
      clear acc_iidm_open; aD = zeros(size(val,2),1);
      for k = 1:size(val,2)
        p = double(snn_decode_lut(fi(R(k,:).', Tp), 64));
        aD(k) = acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k), p, k==1, Td);
      end
      clear acc_iidm_open; aX = zeros(size(val,2),1);
      for k = 1:size(val,2)
        p = double(snn_decode_lut(fi(R(k,:).', Tp), 64));
        aX(k) = double(acc_iidm_open(val(1,k),val(2,k),val(3,k),val(4,k), p, k==1, Tf));
      end
      E = [E; abs(aX - aD)]; %#ok<AGROW>
    end
    tab(j,:) = [f, prctile(E,99), max(E)];
    ok = tab(j,2) < bud_p99 && tab(j,3) < bud_max;
    fprintf('%-6d %12.6g %12.6g %8s\n', f, tab(j,2), tab(j,3), string(ok));
  end
  pass = find(tab(:,2) < bud_p99 & tab(:,3) < bud_max, 1);
  assert(~isempty(pass), ['nessun nfrac in [%s] rispetta il budget derivato (p99<%.4g, max<%.4g): ' ...
         'l''IIDM in fixed sarebbe la fonte d''errore DOMINANTE'], mat2str(fracs), bud_p99, bud_max);
  fprintf('\n>>> MINIMO nfrac che rispetta il budget: %d <<<\n', tab(pass,1));
end
```

- [ ] **Step 4: esegui lo sweep sul dataset intero**

Run: `matlab -batch "cd('<matlabdir>'); run_acc_fixed_sweep(8:2:18, 60)"`
Expected: una riga per `nfrac`, `E_iidm` che **cala** al crescere di `f`, e un `nfrac` minimo che passa.
Se **nessuno** passa nemmeno a `f=18` → **fermarsi**: il problema non è la risoluzione ma i **bit interi**
(saturazione) o l'ordine delle operazioni. Ispezionare con `f=18` quale intermedio satura.

- [ ] **Step 5: fissa `nfrac` scelto come default di `acc_types`**

In `matlab/acc_types.m` sostituisci `if nargin < 2, nfrac = 13; end` con il valore vincitore dello Step 4,
aggiungendo il commento (esempio con 13 — usare il numero VERO misurato):
```matlab
  % nfrac di DEFAULT = il MINIMO che rispetta il budget derivato (run_acc_fixed_sweep, 2026-07-15):
  % E_iidm(p99/max) < E_snn(p99/max) = footprint in accel della quantizzazione della rete, gia'
  % accettata a monte. Sotto questo valore l'IIDM diventerebbe la fonte d'errore dominante.
  if nargin < 2, nfrac = 13; end
```

- [ ] **Step 6: Commit**

```bash
git add matlab/acc_iidm_open.m matlab/acc_types.m matlab/run_acc_fixed_sweep.m matlab/cf_plant_lib.slx
git commit -m "feat(sp3): path fixed dell'IIDM + budget DERIVATO dalla misura (niente numero magico)

RoundingMethod 'Zero' sulle divisioni (l'unica forma che HDL Coder genera per signed) e
ALPHA=exp(-0.1) bakata (exp e' l'unica op non generabile). run_plant_parity invariato: il
double non si e' mosso di un bit."
```

---

## Task 4: `Donatello_ACC_IIDM` **diventa HDL-ready**

**Files:** Modify `matlab/build_hdl_variants.m`, `matlab/run_block_hdl_gate.m`

- [ ] **Step 1: generalizza `run_block_hdl_gate` ai blocchi a 1 uscita**

In `matlab/run_block_hdl_gate.m` sostituisci il blocco dell'assert su `nOut` (introdotto il 2026-07-15) con:
```matlab
  % Il gate cabla tante uscite quante ne ha il blocco: i blocchi HDL-ready ne hanno 5 (v0,T,s0,a,b),
  % Donatello_ACC_IIDM una sola (accel). Prima era fissato a 5 e falliva sull'HARNESS, dando una
  % conferma FALSA del "non sintetizzabile" (SP2_ACC_IIDM.md).
  nOut = numel(find_system([lib '/' blockName], 'SearchDepth', 1, 'BlockType', 'Outport'));
  assert(nOut >= 1, 'il blocco "%s" non ha uscite', blockName);
```
e sostituisci il ciclo `for j = 1:5` che aggiunge gli Outport con:
```matlab
  for j = 1:nOut
    add_block('built-in/Outport', [mdl '/o' num2str(j)], 'Port', num2str(j));
    add_line(mdl, ['DUT/' num2str(j)], ['o' num2str(j) '/1']);
  end
```
Sostituisci infine l'assert finale:
```matlab
  assert(ok && hasRAM, 'gate fallito: VHDL assente o architettura non time-mux');
```
con:
```matlab
  % DualPortRAM = l'hdl.RAM della FSM time-mux: atteso nei blocchi che contengono la SNN. Non lo si
  % pretende dai blocchi che non la contengono (oggi nessuno, ma l'assert deve dire il vero).
  assert(ok, 'gate fallito: nessun VHDL generato per %s', blockName);
  assert(hasRAM, ['gate fallito: VHDL generato ma senza DualPortRAM -> non e'' l''architettura ' ...
         'time-mux del deployato (HDL_PHASE §3.1.1)']);
```

- [ ] **Step 2: il blocco SP2 passa in fixed**

In `matlab/build_hdl_variants.m`, funzione `acciidm_chart_code`, sostituisci la riga della chiamata IIDM:
```matlab
    '    acc = acc_iidm_open(double(s), double(v), double(dv), double(v_l), double(pv(:)), false);'
```
con:
```matlab
    '    acc = acc_iidm_open(s, v, dv, v_l, pv(:), false, acc_types(''fixed''));'
```
e la riga di init di `acc`:
```matlab
    '    acc = 0; go = true;'
```
con:
```matlab
    '    acc = cast(0, ''like'', getfield(acc_types(''fixed''), ''out'')); go = true;'
```
Nella lista dei sorgenti inlinati (funzione `build_hdl_variants`, dopo `srcIidm`) aggiungi:
```matlab
  srcAccT = fileread(fullfile(here, 'acc_types.m'));       % SP3: tipi dell'IIDM (single source)
```
e in `acciidm_chart_code` cambia la firma e la coda:
```matlab
function code = acciidm_chart_code(N, srcRom, srcTypes, srcFsm, srcLut, srcIidm, srcAccT, nrm)
```
```matlab
  code = [code newline newline srcRom newline newline srcTypes newline newline srcFsm ...
          newline newline srcLut newline newline srcIidm newline newline srcAccT];
```
e la chiamata:
```matlab
  chart.Script = acciidm_chart_code(NCHAMP, srcRom, srcTypes, srcFsm, srcLut, srcIidm, srcAccT, nrm);
```

- [ ] **Step 3: riscrivi la Description (la vecchia dichiara il falso)**

In `acciidm_description(N)` sostituisci il blocco `⚠️ BLOCCO DI SOLA SIMULAZIONE …` con:
```matlab
    'HDL-READY (dal 2026-07-15, SP3): HDL Coder genera il VHDL dal solo .slx. Prima l''IIDM girava in'
    '   double e il blocco era di sola simulazione; ora l''IIDM e'' fixed-point (acc_types).'
    '   ⚠️ HDL-ready NON vuol dire deployato: il bitstream PYNQ-Z1 resta la sola SNN.'
```
e la riga finale dei riferimenti:
```matlab
    '  docs/superpowers/specs/2026-07-15-acc-iidm-hdl-ready-design.md · document/SP3_ACC_IIDM_HDL.md'
```

- [ ] **Step 4: rigenera e passa il gate «altro PC»**

Run: `matlab -batch "cd('<matlabdir>'); build_hdl_variants; run_block_hdl_gate('Donatello_ACC_IIDM')"`
Expected: `isolamento OK` + `GATE PASSATO: Donatello_ACC_IIDM e' self-contained e HDL-ready`.
Se `makehdl` rifiuta: leggere il **messaggio vero** dando lo script della chart a `codegen` (il metodo di
SP2_ACC_IIDM.md §Gotcha) — Simulink stampa solo «Errors occurred during parsing of …».

- [ ] **Step 5: i blocchi HDL-ready esistenti NON sono rotti**

Run: `matlab -batch "cd('<matlabdir>'); run_block_hdl_gate('Donatello_Champion'); run_block_sync_check"`
Expected: `GATE PASSATO` + `blocchi self-contained controllati: 8 — stale: 0`.

- [ ] **Step 6: Commit**

```bash
git add matlab/build_hdl_variants.m matlab/run_block_hdl_gate.m matlab/snn_champions_lib.slx
git commit -m "feat(sp3): Donatello_ACC_IIDM e' HDL-ready (IIDM in fixed); hdl_gate generalizzato alle N uscite

Il gate cablava 5 uscite: sul blocco SP2 (1 uscita) falliva sull'HARNESS, dando una conferma
FALSA del 'non sintetizzabile'. Ora cabla nOut. HDL-ready != deployato: il bitstream resta la SNN."
```

---

## Task 5: adatta i cancelli — il riferimento diventa il **path fixed**

**Files:** Modify `matlab/snn_cl_step.m`, `matlab/run_block_acciidm_test.m`, `matlab/run_block_closed_loop_test.m`

Col blocco in fixed, confrontarlo col double renderebbe `dmax = 0` **impossibile**. Il riferimento diventa il
path fixed (`dmax = 0` resta il criterio); la distanza fixed↔double è già coperta da `run_acc_fixed_sweep`.

- [ ] **Step 1: `snn_cl_step` usa il path fixed**

In `matlab/snn_cl_step.m` sostituisci:
```matlab
  accel = acc_iidm_open(x_phys(1), x_phys(2), x_phys(3), x_phys(4), p, rst, acc_types('double'));
```
con:
```matlab
  % IIDM in FIXED: e' il riferimento del BLOCCO, che dal 2026-07-15 (SP3) e' fixed. Il confronto
  % fixed-vs-double e' un cancello a se': run_acc_fixed_sweep.
  accel = double(acc_iidm_open(x_phys(1), x_phys(2), x_phys(3), x_phys(4), p, rst, acc_types('fixed')));
```

- [ ] **Step 2: `run_block_acciidm_test` usa il path fixed**

In `matlab/run_block_acciidm_test.m` sostituisci:
```matlab
    a_ref(k) = acc_iidm_open(val(1,k), val(2,k), val(3,k), val(4,k), p, k == 1);
```
con:
```matlab
    a_ref(k) = double(acc_iidm_open(val(1,k), val(2,k), val(3,k), val(4,k), p, k == 1, acc_types('fixed')));
```

- [ ] **Step 3: rigenera il MEX ed esegui i due cancelli sul dataset**

Run:
```
matlab -batch "cd('<matlabdir>'); build_traj_mex; for t=[1 6 12 20 30], run_block_acciidm_test(12,t,400); end"
```
Expected: `dmax(accel) = 0` su **5/5**.
Run:
```
matlab -batch "cd('<matlabdir>'); for t=[1 6 12], for m={'train','inst'}, run_block_closed_loop_test(t,40,400,m{1}); end, end"
```
Expected: `dmax = 0` su **6/6**, e `comportamento:` con gap limitati (nessun NaN, l'ego segue il leader).
Se `dmax > 0`: **non allargare la tolleranza**. Il sospetto n°1 è che il blocco e il riferimento usino un
`nfrac` diverso — entrambi devono chiamare `acc_types('fixed')` **senza argomento** (default unico).

- [ ] **Step 4: il test ha ancora POTERE (non e' diventato cieco passando al fixed)**

La variante mis-gated deve ancora far fallire il test (metodo di `document/SP2_ACC_IIDM.md` §Il punto critico):
sposta a mano la chiamata `acc = acc_iidm_open(...)` FUORI da `if valid` nella chart di
`snn_champions_lib/Donatello_ACC_IIDM`, salva la libreria, rilancia `run_block_acciidm_test(12,1,400)`,
poi **ripristina** con `git checkout -- matlab/snn_champions_lib.slx`.
Expected: il test **FALLISCE** (atteso `dmax` dell'ordine di 0.1 m/s²; nel 2026-07-15 era 0.1836).
Se passasse → il test è cieco: **fermarsi** e rafforzarlo prima di fidarsene.

- [ ] **Step 5: Commit**

```bash
git add matlab/snn_cl_step.m matlab/run_block_acciidm_test.m
git commit -m "test(sp3): riferimento dei cancelli SP2 = path fixed (il blocco ora e' fixed); dmax=0 resta il criterio

Col blocco in fixed, confrontarlo col double renderebbe dmax=0 impossibile. La distanza
fixed-vs-double e' un cancello a se' (run_acc_fixed_sweep). Verificato che il test NON e'
diventato cieco: la variante mis-gated lo fa ancora fallire."
```

---

## Task 6: sintesi **OOC** — i numeri per il Piano 2 del confronto MPC

**Files:** Create `scripts/synth_acc_iidm.tcl`

Non si ottimizza: si **misura e si registra** (baseline per lo sweep a slack minima, previsto ma non ora).

- [ ] **Step 1: genera il VHDL dei due DUT**

Run:
```
matlab -batch "cd('<matlabdir>'); build_hdl_variants;
load_system('snn_champions_lib');
makehdl('snn_champions_lib/Donatello_ACC_IIDM','TargetLanguage','VHDL','TargetDirectory',fullfile(pwd,'hdl_sp3','chain'),'GenerateHDLTestBench','off');
makehdl('snn_champions_lib/Donatello_Champion','TargetLanguage','VHDL','TargetDirectory',fullfile(pwd,'hdl_sp3','snn'),'GenerateHDLTestBench','off');
close_system('snn_champions_lib',0)"
```
Expected: due alberi VHDL in `matlab/hdl_sp3/chain` e `matlab/hdl_sp3/snn`, 0 errori.

- [ ] **Step 2: scrivi `scripts/synth_acc_iidm.tcl`**

```tcl
# Sintesi OOC su xc7z020 del DUT indicato. Uso:
#   vivado -mode batch -source synth_acc_iidm.tcl -tclargs <srcdir> <top> <outdir>
# Registra: LUT/FF/DSP/BRAM + WNS/Fmax + il path critico (baseline per lo sweep futuro).
set srcdir [lindex $argv 0]
set top    [lindex $argv 1]
set outdir [lindex $argv 2]
file mkdir $outdir
create_project -in_memory -part xc7z020clg400-1
foreach f [glob -nocomplain $srcdir/*.vhd] { read_vhdl $f }
synth_design -top $top -part xc7z020clg400-1 -mode out_of_context
create_clock -name clk -period 125.0 [get_ports clk]   ;# 8 MHz = il clock del bitstream Fase B
report_utilization -file $outdir/util.rpt
report_timing_summary -file $outdir/timing.rpt
report_timing -max_paths 1 -nworst 1 -delay_type max -file $outdir/critpath.rpt
set wns [get_property SLACK [get_timing_paths -delay_type max]]
set fmax [expr {1000.0 / (125.0 - $wns)}]
puts "RESULT top=$top WNS=$wns ns  Fmax=$fmax MHz"
```

- [ ] **Step 3: sintetizza catena e SNN da sola**

Run (Git Bash):
```bash
V="C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat"
cd "<worktree>"
"$V" -mode batch -source scripts/synth_acc_iidm.tcl -tclargs matlab/hdl_sp3/chain Donatello_ACC_IIDM matlab/hdl_sp3/out_chain | grep RESULT
"$V" -mode batch -source scripts/synth_acc_iidm.tcl -tclargs matlab/hdl_sp3/snn Donatello_Champion matlab/hdl_sp3/out_snn | grep RESULT
```
Expected: due righe `RESULT top=… WNS=… Fmax=…`.
**Numero di riferimento:** la Fase B misura **4223 LUT (7,94%)** e **Fmax 8,5 MHz** per la sola SNN. La
differenza `chain − snn` è il **costo dell'IIDM**: è il numero che serve al Piano 2 del confronto MPC.
Se l'Fmax della catena crolla → **è un risultato, non un problema** (spec §7): registrarlo e guardare
`critpath.rpt` per dire **quale** operazione è sul path critico (attesa: una divisione).

- [ ] **Step 4: Commit**

```bash
git add scripts/synth_acc_iidm.tcl
git commit -m "feat(sp3): sintesi OOC xc7z020 dell'ACC-IIDM - LUT/DSP/Fmax/WNS + path critico

Non si ottimizza: si misura e si registra. La differenza catena-vs-SNN e' il costo in silicio
dell'IIDM, cioe' il numero che manca al Piano 2 del confronto MPC (senza, il confronto conta
solo la rete e omette la legge che produce a_cmd)."
```

---

## Task 7: documentazione — **correggere la claim smentita**

**Files:** Create `document/SP3_ACC_IIDM_HDL.md`; Modify `document/SP2_ACC_IIDM.md`,
`docs/superpowers/specs/2026-07-14-sp2-donatello-acc-iidm-design.md`, `matlab/README.md`,
`document/SESSION_RESUME.md`

- [ ] **Step 1: crea `document/SP3_ACC_IIDM_HDL.md`**

Struttura (riempire coi numeri VERI dei Task 3 e 6, mai con segnaposto):
```markdown
# SP3 — ACC-IIDM HDL-Ready

> Doc di processo. Spec: `docs/superpowers/specs/2026-07-15-acc-iidm-hdl-ready-design.md`.

## Cos'è
`Donatello_ACC_IIDM` è **HDL-Ready** dal 2026-07-15: l'IIDM gira in fixed-point e HDL Coder ne genera il
VHDL dal solo `.slx`. ⚠️ **HDL-ready ≠ deployato**: il bitstream PYNQ-Z1 resta la sola SNN.

## Perché: il buco di equità del confronto MPC
[spec §1 — con l'IIDM in double il Piano 2 contava solo la rete e ometteva la legge che produce a_cmd]

## La premessa era falsa (e per questo l'SP è piccolo)
[spec §2 — tabella sqrt/tanh/x^4 nativi · divisione OK con RoundingMethod 'Zero' · exp l'unica non
supportata, ed è il motivo per cui la sigmoide richiese la LUT ma tanh no]

## Tipi e budget
[nfrac scelto + E_snn(p99/max) + E_iidm(p99/max) dallo sweep — Task 3]

## Numeri OOC (baseline per lo sweep a slack minima)
| DUT | LUT | FF | DSP | BRAM | WNS | Fmax |
[dal Task 6; + la riga «costo dell'IIDM» = chain − snn; + quale op è sul path critico]

## Verifiche
[run_plant_parity invariato · sweep · run_block_acciidm_test 5/5 · closed_loop 6/6 · hdl_gate · sync_check]
```

- [ ] **Step 2: correggi la claim smentita in `document/SP2_ACC_IIDM.md`**

Nella sezione `## Fuori scope`, sostituisci:
```markdown
ACC-IIDM su FPGA (fixed): è un **SP a sé** — `sqrt(a·b)` e le divisioni sono lo stesso genere di problema che
per la sigmoide ha richiesto una LUT; avrà i suoi numeri e i suoi cancelli.
```
con:
```markdown
~~ACC-IIDM su FPGA (fixed): è un SP a sé — `sqrt(a·b)` e le divisioni sono lo stesso genere di problema che
per la sigmoide ha richiesto una LUT.~~ **SUPERATO e SMENTITO (2026-07-15, SP3).** Era una claim mai
verificata: HDL Coder genera `sqrt`, `tanh` e `x^4` **nativamente**, e accetta la divisione con
`RoundingMethod='Zero'` (rifiutava solo per l'arrotondamento). Il precedente della sigmoide era reale ma
**non trasferibile**: `exp` è l'unica non supportata, e σ(x)=1/(1+exp(−x)). Fatto in
**`document/SP3_ACC_IIDM_HDL.md`**: nessuna LUT, solo tipizzazione fixed.
```
Nella sezione `## Sintetizzabilità — misurata, non assunta`, aggiungi in cima:
```markdown
> **🔄 SUPERATO dal 2026-07-15 (SP3): il blocco È ora HDL-ready** (IIDM in fixed). Quanto segue resta come
> **record**: è la misura che dimostrò il rifiuto *finché l'IIDM era in double*, e ne spiega la causa.
```

- [ ] **Step 3: correggi la spec SP2 §7**

In `docs/superpowers/specs/2026-07-14-sp2-donatello-acc-iidm-design.md`, sezione `## 7. Fuori scope`,
sotto la riga dell'ACC-IIDM su FPGA aggiungi:
```markdown
> **🔄 2026-07-15 — questa riga è SMENTITA.** «Lo stesso genere di problema della sigmoide» era una claim mai
> verificata: `sqrt` e `tanh` sono nativi in HDL Coder, la divisione passa con `RoundingMethod='Zero'`.
> Fatto in SP3: `docs/superpowers/specs/2026-07-15-acc-iidm-hdl-ready-design.md`.
```

- [ ] **Step 4: aggiorna `matlab/README.md`**

Nella sezione «Librerie Simulink», sostituisci il paragrafo di `Donatello_ACC_IIDM` («⚠️ **Sola simulazione:
NON sintetizzabile**…») con:
```markdown
Lo stesso builder aggiunge **`Donatello_ACC_IIDM`** (SP2/SP3): campione LUT-64 + ACC-IIDM **open-loop**,
`s,v,dv,v_l → accel`. **HDL-Ready dal 2026-07-15** (IIDM in fixed, `acc_types.m`) — ⚠️ HDL-ready **≠
deployato**: il bitstream resta la sola SNN. Doc: `../document/SP3_ACC_IIDM_HDL.md`.
Cancelli: `run_block_acciidm_test` · `run_block_closed_loop_test` · `run_acc_fixed_sweep` (bit frazionari
vs budget derivato) · `run_block_hdl_gate`.
```
Nella sezione «Core single-source», dopo `acc_iidm_open.m`, aggiungi:
```markdown
`acc_types.m` (prototipi di tipo dell'IIDM: `double` e `fixed`, `nfrac` sweepabile — modello `snn_types.m`) ·
```

- [ ] **Step 5: aggiorna `document/SESSION_RESUME.md`**

Nel blocco **SP2 — FATTO**, dopo il capoverso «NON sintetizzabile» ora è MISURATO…», aggiungi:
```markdown
**🔄 SUPERATO da SP3 (2026-07-15): il blocco È HDL-ready.** L'IIDM è in fixed (`acc_types.m`) e HDL Coder ne
genera il VHDL. La premessa «serve una LUT come per la sigmoide» era **falsa**: `sqrt`/`tanh` sono nativi,
la divisione passa con `RoundingMethod='Zero'`. Numeri OOC e dettagli → **`document/SP3_ACC_IIDM_HDL.md`**.
```
e nella riga **Prossimi:** togli l'eventuale menzione dell'IIDM fixed come lavoro futuro.

- [ ] **Step 6: cancelli finali + Commit + push**

Run:
```
matlab -batch "cd('<matlabdir>'); run_plant_parity; run_block_sync_check; run_block_traj_test(10,'Donatello_Champion',400,1); run_block_acciidm_test(12,1,400); run_block_closed_loop_test(1,40,400,'train'); run_block_hdl_gate('Donatello_ACC_IIDM'); run_block_hdl_gate('Donatello_Champion'); disp('>>>> TUTTI VERDI <<<<')"
```
Expected: `ALL PLANT PARITY PASS` · `8 blocchi, 0 stale` · `dmax = 0` (×3) · `GATE PASSATO` (×2) · `TUTTI VERDI`.
```bash
git add document/SP3_ACC_IIDM_HDL.md document/SP2_ACC_IIDM.md document/SESSION_RESUME.md matlab/README.md docs/superpowers/specs/2026-07-14-sp2-donatello-acc-iidm-design.md
git commit -m "docs(sp3): SP3_ACC_IIDM_HDL.md + correzione della claim smentita in SP2/README/RESUME

'sqrt e le divisioni sono lo stesso problema della sigmoide' era una claim mai verificata ed e'
FALSA: sqrt/tanh sono nativi in HDL Coder, la divisione passa con RoundingMethod 'Zero'. Il
verdetto 'sola simulazione' di SP2 e' superato: il blocco e' HDL-ready."
git push origin Simulink_Importer
```

---

## Self-review (copertura della spec)
- **§1 scopo** (HDL-ready + OOC, niente bitstream): Task 4 (HDL-ready) + Task 6 (OOC). ✓
- **§2 premessa smentita** (`Zero` sulle divisioni · `exp` bakata · niente LUT): Task 3 Step 1 + Task 7. ✓
- **§3 dinamica misurata** (bit interi dai range): Task 1. ✓
- **§4 type-parametrico** (unica fonte; `run_plant_parity` invariato = la prova): Task 2. ✓
- **§5 budget derivato** (E_iidm < E_snn, sweep, minimo che passa): Task 3 Steps 3-5. ✓
- **§6 verifiche** (plant_parity · sweep · acciidm_test · closed_loop · hdl_gate esteso · OOC · sync_check):
  Task 2 Step 4 · Task 3 Step 4 · Task 5 · Task 4 Step 1 · Task 6 · Task 4 Step 5. ✓
- **§7 fuori scope** (niente ottimizzazione; registrare Fmax/slack/path critico): Task 6 Step 3. ✓
- **§8 file**: tutti coperti; `run_block_hdl_gate` generalizzato in Task 4 Step 1. ✓
- **Coerenza dei tipi**: `acc_types(dt, nfrac)` con campi `st/par/acc/out` — usati con gli stessi nomi in
  Task 1, 3, 4, 5. `acc_iidm_open(s,v,dv,v_l,p,rst,T)` — 7 argomenti in Task 2, 3, 5 e nella chart (Task 4). ✓
